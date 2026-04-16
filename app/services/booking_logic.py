from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Booking, BookingStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_local_display(dt: datetime, tz_name: str | None = None) -> datetime:
    settings = get_settings()
    name = tz_name or settings.display_timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(name))


def remaining_seconds_until(end_utc: datetime, now_utc: datetime | None = None) -> int:
    now = now_utc or utc_now()
    if end_utc.tzinfo is None:
        end_utc = end_utc.replace(tzinfo=timezone.utc)
    delta = end_utc - now
    sec = int(delta.total_seconds())
    return max(0, sec)


def warning_active(remaining_seconds: int, warning_minutes: int | None = None) -> bool:
    settings = get_settings()
    m = warning_minutes if warning_minutes is not None else settings.warning_minutes_before_end
    return 0 < remaining_seconds <= m * 60


def compute_exit_charges(
    end_time_utc: datetime,
    base_price: Decimal,
    price_per_hour: Decimal,
    now_utc: datetime | None = None,
    extra_rate_per_minute: Decimal | None = None,
) -> tuple[Decimal, int]:
    """
    If exit is after booked end: extra minutes * rate. Returns (extra_charge, extra_minutes).
    """
    settings = get_settings()
    now = now_utc or utc_now()
    if end_time_utc.tzinfo is None:
        end_time_utc = end_time_utc.replace(tzinfo=timezone.utc)

    rate = (
        extra_rate_per_minute
        if extra_rate_per_minute is not None
        else Decimal(str(settings.extra_rate_per_minute))
    )

    if now <= end_time_utc:
        return Decimal("0"), 0

    extra = now - end_time_utc
    extra_minutes = int(extra.total_seconds() // 60)
    if extra.total_seconds() % 60 > 0:
        extra_minutes += 1

    extra_charge = Decimal(extra_minutes) * rate
    return extra_charge.quantize(Decimal("0.01")), extra_minutes


def total_exit_amount(base_price: Decimal, extra_charge: Decimal) -> Decimal:
    return (base_price + extra_charge).quantize(Decimal("0.01"))


def vehicle_booking_group(vehicle: Any) -> str:
    """
    bike → only bike-tier slots (B… bays).
    motor → car + commercial tiers (A… and C…); cars, trucks, SUVs share this pool.
    """
    vt = (getattr(vehicle, "vehicle_type", None) or "").strip().lower()
    if any(
        k in vt
        for k in (
            "bike",
            "motorcycle",
            "scooter",
            "two-wheel",
            "twowheel",
            "moped",
            "cycle",
        )
    ):
        return "bike"
    return "motor"


def slot_tier_allowed_for_vehicle_group(slot_tier: str | None, group: str) -> bool:
    tier = (slot_tier or "car").lower()
    if group == "bike":
        return tier == "bike"
    return tier in ("car", "commercial")


def vehicle_ids_with_active_booking_for_user(db: Session, user_id: int) -> set[int]:
    rows = db.scalars(
        select(Booking.vehicle_id).where(
            Booking.user_id == user_id,
            Booking.status == BookingStatus.active,
        )
    ).all()
    return set(rows)
