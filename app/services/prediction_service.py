"""
Booking demand prediction from historical `bookings.start_time_utc`.

This app has statuses: active | completed | cancelled (no "confirmed").
We use **completed** and **active** as demand signals (bookings that started).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Booking, BookingStatus, Vehicle
from app.services.booking_logic import utc_now

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {"ts": 0.0, "hours": 6, "rows": None, "threshold": 2.0}
CACHE_TTL_SEC = 300


def fetch_booking_data(db: Session) -> list[Booking]:
    stmt = select(Booking).where(
        Booking.status.in_([BookingStatus.completed, BookingStatus.active])
    )
    return list(db.scalars(stmt).all())


def preprocess_data(bookings: list[Booking]) -> np.ndarray:
    """
    Map each booking start to display timezone; hour (0–23) and weekday (0–6 Mon=0).
    Aggregate counts by clock hour.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.display_timezone)
    counts = np.zeros(24, dtype=float)
    for b in bookings:
        st: datetime = b.start_time_utc
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        local = st.astimezone(tz)
        _ = local.weekday()
        counts[local.hour] += 1
    return counts


def load_model() -> Any:
    try:
        from transformers import pipeline

        return pipeline("time-series-forecasting")
    except Exception as e:
        logger.debug("transformers pipeline unavailable: %s", e)
        return None


def _regression_hourly_profile(hourly_counts: np.ndarray) -> np.ndarray:
    y = hourly_counts.astype(float).copy()
    x = np.arange(24, dtype=float)
    if float(y.sum()) == 0:
        return np.full(24, 0.25)
    nonzero = int((y > 0).sum())
    if nonzero <= 1:
        mean = float(y.mean())
        return np.full(24, max(mean, 0.1))
    deg = min(3, nonzero - 1)
    coef = np.polyfit(x, y, deg)
    pred = np.poly1d(coef)(x)
    return np.clip(pred, 0.0, None)


def _extract_float_sequence(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        raw = raw.tolist()
    if isinstance(raw, (list, tuple)):
        out: list[float] = []
        for x in raw:
            if isinstance(x, dict):
                inner = _extract_float_sequence(x)
                if inner:
                    return inner
            try:
                out.append(float(x))
            except (TypeError, ValueError):
                continue
        return out if out else None
    if isinstance(raw, dict):
        for k in ("forecast", "predictions", "mean", "target", "values"):
            if k in raw:
                return _extract_float_sequence(raw[k])
    return None


def _try_hf_predict(model: Any, hourly_24: np.ndarray, hours: int) -> list[float] | None:
    if model is None:
        return None
    series = hourly_24.astype(float).tolist()
    for attempt in (
        lambda: model(series),
        lambda: model({"target": series}),
        lambda: model({"past_values": series}),
    ):
        try:
            raw = attempt()
            seq = _extract_float_sequence(raw)
            if seq and len(seq) >= hours:
                return [max(0.0, float(v)) for v in seq[:hours]]
        except Exception:
            continue
    return None


def predict_next_hours(data: np.ndarray, hours: int = 6) -> list[dict[str, Any]]:
    settings = get_settings()
    tz = ZoneInfo(settings.display_timezone)
    now = utc_now()
    model = load_model()
    hf = _try_hf_predict(model, data, hours)
    baseline = _regression_hourly_profile(data)
    out: list[dict[str, Any]] = []
    for i in range(hours):
        t_local = (now + timedelta(hours=i)).astimezone(tz)
        h = t_local.hour
        hist = float(data[h])
        reg = float(baseline[h])
        blend = max(0.0, 0.5 * hist + 0.5 * reg)
        if hf is not None:
            predicted = max(0.0, 0.35 * hf[i] + 0.65 * blend)
        else:
            predicted = blend
        out.append(
            {
                "hour": t_local.strftime("%H:%M"),
                "predicted": round(predicted, 2),
            }
        )
    return out


def demand_threshold(hourly_counts: np.ndarray) -> float:
    if hourly_counts.size == 0 or float(hourly_counts.sum()) == 0:
        return 2.0
    m = float(hourly_counts.mean())
    return max(2.0, m * 1.25 + 0.5)


def _compute_predictions_uncached(db: Session, hours: int = 6) -> tuple[list[dict[str, Any]], float]:
    bookings = fetch_booking_data(db)
    counts = preprocess_data(bookings)
    preds = predict_next_hours(counts, hours=hours)
    thresh = demand_threshold(counts)
    for p in preds:
        p["demand"] = "High Demand" if p["predicted"] >= thresh else "Low Demand"
    return preds, thresh


def compute_predictions_cached(db: Session, hours: int = 6) -> tuple[list[dict[str, Any]], float]:
    now = time.time()
    if (
        _cache["rows"] is not None
        and int(_cache["hours"]) == int(hours)
        and (now - float(_cache["ts"])) < CACHE_TTL_SEC
    ):
        return _cache["rows"], float(_cache["threshold"])
    rows, thresh = _compute_predictions_uncached(db, hours=hours)
    _cache["ts"] = now
    _cache["hours"] = hours
    _cache["rows"] = rows
    _cache["threshold"] = thresh
    return rows, thresh


def display_tz_label() -> str:
    return get_settings().display_timezone


def _category_from_slot_prefix(slot_number: str | None) -> str:
    sn = (slot_number or "").strip().upper()
    if sn.startswith("B"):
        return "Two-wheeler (bike / scooter)"
    if sn.startswith("C"):
        return "Commercial (truck / tempo)"
    return "Car"


def _category_from_vehicle_type(vehicle: Vehicle | None, slot_number: str) -> str:
    """Prefer registered vehicle type; fall back to slot zone (B / A / C style)."""
    slot_guess = _category_from_slot_prefix(slot_number)
    if not vehicle:
        return slot_guess
    vt = (vehicle.vehicle_type or "").strip().lower()
    if not vt:
        return slot_guess
    if any(k in vt for k in ("bike", "motor", "scooter", "two-wheel", "twowheel", "moped", "cycle")):
        return "Two-wheeler (bike / scooter)"
    if any(k in vt for k in ("truck", "commercial", "tempo", "van", "loader", "goods", "lorry")):
        return "Commercial (truck / tempo)"
    if any(k in vt for k in ("car", "suv", "hatch", "sedan")):
        return "Car"
    # Custom catalog label (e.g. "Motorcycle") — show as-is, trimmed
    label = (vehicle.vehicle_type or "").strip()
    return label[:56] if label else slot_guess


def booking_vehicle_category_mix(db: Session) -> list[dict[str, Any]]:
    """
    Count completed + active bookings by vehicle category for the pie chart.
    """
    stmt = (
        select(Booking)
        .options(joinedload(Booking.vehicle), joinedload(Booking.slot))
        .where(Booking.status.in_([BookingStatus.completed, BookingStatus.active]))
    )
    rows = list(db.scalars(stmt).unique().all())
    counts: dict[str, int] = {}
    for b in rows:
        slot_num = b.slot.slot_number if b.slot else ""
        cat = _category_from_vehicle_type(b.vehicle, slot_num)
        counts[cat] = counts.get(cat, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"label": k, "count": v} for k, v in ordered]
