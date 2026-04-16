"""Add columns / constraints to existing SQLite or PostgreSQL tables when models change."""

import logging
import re

from sqlalchemy import inspect, select, text

from app.database import engine

_log = logging.getLogger(__name__)


def _normalized_plate_key(plate: str) -> str:
    return re.sub(r"\s+", "", (plate or "").strip().upper())


def ensure_vehicle_detail_columns() -> None:
    try:
        insp = inspect(engine)
        if not insp.has_table("vehicles"):
            return
    except Exception:
        return
    cols = {c["name"] for c in insp.get_columns("vehicles")}
    specs = [
        ("vehicle_type", "VARCHAR(64)"),
        ("vehicle_subtype", "VARCHAR(64)"),
        ("brand", "VARCHAR(100)"),
        ("model", "VARCHAR(100)"),
        ("color", "VARCHAR(64)"),
    ]
    with engine.begin() as conn:
        for name, ddl in specs:
            if name not in cols:
                conn.execute(text(f"ALTER TABLE vehicles ADD COLUMN {name} {ddl}"))


def normalize_vehicle_plates_storage() -> None:
    """Store plates in canonical form (uppercase, no spaces). Skips groups that still logically duplicate."""
    try:
        insp = inspect(engine)
        if not insp.has_table("vehicles"):
            return
    except Exception:
        return

    from app.database import SessionLocal
    from app.models import Vehicle

    try:
        with SessionLocal() as db:
            rows = list(db.scalars(select(Vehicle)).all())
            by_key: dict[str, list] = {}
            for v in rows:
                by_key.setdefault(_normalized_plate_key(v.plate_number), []).append(v)
            for key, group in by_key.items():
                if len(group) > 1:
                    _log.warning(
                        "vehicles: %d rows share normalized plate %r — remove duplicates then restart",
                        len(group),
                        key,
                    )
                    continue
                v = group[0]
                if v.plate_number != key:
                    v.plate_number = key
            db.commit()
    except Exception as e:
        _log.warning("normalize_vehicle_plates_storage: %s", e)


def ensure_vehicle_plate_globally_unique() -> None:
    """
    Enforce unique plate_number across all users (drop old per-user composite if present).
    Skips the unique index if duplicate plates already exist — fix data, then restart.
    """
    try:
        insp = inspect(engine)
        if not insp.has_table("vehicles"):
            return
    except Exception:
        return

    try:
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE vehicles DROP CONSTRAINT IF EXISTS uq_user_plate"))
            except Exception:
                pass
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_vehicles_plate_number"))
            except Exception:
                pass
    except Exception as e:
        _log.debug("vehicle plate migrate (drop old constraints): %s", e)

    try:
        from app.database import SessionLocal
        from app.models import Vehicle

        with SessionLocal() as db:
            rows = list(db.scalars(select(Vehicle)).all())
            buckets: dict[str, list] = {}
            for v in rows:
                buckets.setdefault(_normalized_plate_key(v.plate_number), []).append(v.id)
        dup_key = next((k for k, ids in buckets.items() if len(ids) > 1), None)
        if dup_key:
            _log.warning(
                "vehicles: duplicate normalized plate_number %r (vehicle ids %s); remove duplicates "
                "then restart to add unique index uq_vehicles_plate_number",
                dup_key,
                buckets[dup_key],
            )
            return
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicles_plate_number "
                    "ON vehicles (plate_number)"
                )
            )
    except Exception as e:
        _log.warning("vehicles: could not ensure global unique plate_number: %s", e)


def ensure_parking_slot_tier() -> None:
    """Add slot_tier, backfill from slot_number (B=bike, C=commercial, else car), seed B/C rows if missing."""
    try:
        insp = inspect(engine)
        if not insp.has_table("parking_slots"):
            return
    except Exception:
        return

    cols = {c["name"] for c in insp.get_columns("parking_slots")}
    with engine.begin() as conn:
        if "slot_tier" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE parking_slots ADD COLUMN slot_tier VARCHAR(16) DEFAULT 'car'"
                )
            )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE parking_slots SET slot_tier = CASE
                    WHEN UPPER(slot_number) LIKE 'B%%' THEN 'bike'
                    WHEN UPPER(slot_number) LIKE 'C%%' THEN 'commercial'
                    ELSE 'car'
                END
                """
            )
        )

    from app.database import SessionLocal
    from app.models import ParkingSlot

    with SessionLocal() as db:
        existing = set(db.scalars(select(ParkingSlot.slot_number)).all())
        for i in range(1, 16):
            sn = f"B{i:02d}"
            if sn not in existing:
                db.add(ParkingSlot(slot_number=sn, is_available=True, slot_tier="bike"))
                existing.add(sn)
        for i in range(1, 6):
            sn = f"C{i:02d}"
            if sn not in existing:
                db.add(ParkingSlot(slot_number=sn, is_available=True, slot_tier="commercial"))
                existing.add(sn)
        db.commit()
