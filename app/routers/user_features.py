from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, ParkingSlot, User, Vehicle
from app.schemas import VehicleRegistration, WalletTopUp, normalize_plate
from app.routers.bookings import book_form_context
from app.vehicle_catalog import catalog_json_string, validate_selection
from app.services.booking_logic import (
    remaining_seconds_until as rem_secs,
    to_local_display,
    utc_now,
    vehicle_ids_with_active_booking_for_user,
    warning_active,
)

router = APIRouter(tags=["user"])

_STATIC_IMAGES = Path(__file__).resolve().parent.parent.parent / "static" / "images"


def _vehicle_with_same_canonical_plate(db: Session, canonical_plate: str) -> Vehicle | None:
    """Any row whose plate normalizes the same way counts as a duplicate (one plate system-wide)."""
    for row in db.scalars(select(Vehicle)).all():
        if normalize_plate(row.plate_number) == canonical_plate:
            return row
    return None


def _vehicle_page_context(
    request: Request,
    user: User,
    db: Session,
    *,
    error: str | None = None,
    just_added: bool = False,
) -> dict:
    vehicles = db.scalars(select(Vehicle).where(Vehicle.user_id == user.id)).all()
    return {
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "catalog_json": catalog_json_string(),
        "just_added": just_added,
        "error": error,
        "has_vehicle_side_image": (_STATIC_IMAGES / "vehicle-side.jpg").is_file(),
    }


@router.get("/", name="home")
def home(request: Request):
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", name="dashboard")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    settings = get_settings()
    notice = request.query_params.get("notice")
    active = db.scalars(
        select(Booking)
        .where(Booking.user_id == user.id, Booking.status == BookingStatus.active)
        .options(joinedload(Booking.vehicle), joinedload(Booking.slot))
        .order_by(Booking.end_time_utc.asc())
    ).all()

    warnings: list[dict] = []
    booking_cards: list[dict] = []
    now = utc_now()
    for b in active:
        rem = rem_secs(b.end_time_utc, now)
        warn = warning_active(rem, settings.warning_minutes_before_end)
        booking_cards.append(
            {
                "id": b.id,
                "plate": b.vehicle.plate_number,
                "slot": b.slot.slot_number,
                "end_local": to_local_display(b.end_time_utc),
                "remaining_seconds": rem,
                "warning": warn,
                "qr_url": b.qr_code_path,
                "price_per_hour": b.price_per_hour,
            }
        )
        if warn:
            warnings.append(
                {
                    "booking_id": b.id,
                    "message": "Your booking will expire soon",
                    "minutes_left": max(0, rem // 60),
                }
            )

    all_slots = db.scalars(select(ParkingSlot).order_by(ParkingSlot.slot_number)).all()
    total_slots = len(all_slots)
    available_count = sum(1 for s in all_slots if s.is_available)
    occupied_count = total_slots - available_count

    display_warnings = []
    for b in active:
        rem2 = rem_secs(b.end_time_utc, now)
        if warning_active(rem2, settings.warning_minutes_before_end):
            display_warnings.append({
                "slot": b.slot.slot_number if b.slot else "?",
                "plate": b.vehicle.plate_number if b.vehicle else "?",
            })

    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "booking_cards": booking_cards,
            "warnings": display_warnings,
            "balance": user.wallet_balance,
            "tz_label": settings.display_timezone,
            "notice": notice,
            "all_slots": all_slots,
            "total_slots": total_slots,
            "available_count": available_count,
            "occupied_count": occupied_count,
        },
    )


@router.get("/vehicles", name="vehicles_page")
def vehicles_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return request.app.state.templates.TemplateResponse(
        "vehicles.html",
        _vehicle_page_context(
            request,
            user,
            db,
            error=None,
            just_added=request.query_params.get("added") == "1",
        ),
    )


@router.post("/vehicles", name="vehicles_add")
def vehicles_add(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    vehicle_type: str = Form(...),
    vehicle_subtype: str = Form(""),
    brand: str = Form(""),
    model: str = Form(""),
    plate_number: str = Form(...),
    color: str = Form(""),
    after_save: str = Form("stay"),
):
    try:
        data = VehicleRegistration(
            vehicle_type=vehicle_type,
            vehicle_subtype=vehicle_subtype,
            brand=brand,
            model=model,
            plate_number=plate_number,
            color=color,
        )
        validate_selection(
            data.vehicle_type,
            data.vehicle_subtype,
            data.brand,
            data.model,
        )
    except ValidationError as e:
        err = e.errors()
        msg = err[0].get("msg", "Invalid vehicle details.") if err else "Invalid vehicle details."
        return request.app.state.templates.TemplateResponse(
            "vehicles.html",
            _vehicle_page_context(request, user, db, error=msg),
            status_code=422,
        )
    except ValueError as e:
        return request.app.state.templates.TemplateResponse(
            "vehicles.html",
            _vehicle_page_context(request, user, db, error=str(e)),
            status_code=400,
        )

    existing = _vehicle_with_same_canonical_plate(db, data.plate_number)
    if existing:
        msg = (
            "That plate is already registered on your account."
            if existing.user_id == user.id
            else "This number plate is already registered to another user."
        )
        return request.app.state.templates.TemplateResponse(
            "vehicles.html",
            _vehicle_page_context(request, user, db, error=msg),
            status_code=400,
        )

    label = " ".join(filter(None, [data.brand, data.model])) or data.vehicle_type
    db.add(
        Vehicle(
            user_id=user.id,
            plate_number=data.plate_number,
            label=label,
            vehicle_type=data.vehicle_type,
            vehicle_subtype=data.vehicle_subtype,
            brand=data.brand,
            model=data.model,
            color=data.color,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return request.app.state.templates.TemplateResponse(
            "vehicles.html",
            _vehicle_page_context(
                request,
                user,
                db,
                error="This registration number is already in use.",
            ),
            status_code=400,
        )

    if after_save == "wallet":
        return RedirectResponse(url="/wallet", status_code=303)
    return RedirectResponse(url="/vehicles?added=1", status_code=303)


@router.get("/wallet", name="wallet_page")
def wallet_page(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    return request.app.state.templates.TemplateResponse(
        "wallet.html",
        {"request": request, "user": user, "error": None},
    )


@router.post("/wallet/topup", name="wallet_topup")
def wallet_topup(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    amount: str = Form(...),
):
    try:
        data = WalletTopUp(amount=Decimal(amount))
    except Exception:
        return request.app.state.templates.TemplateResponse(
            "wallet.html",
            {"request": request, "user": user, "error": "Enter a valid positive amount."},
            status_code=422,
        )
    user.wallet_balance = (user.wallet_balance or Decimal("0")) + data.amount
    db.add(user)
    db.commit()
    return RedirectResponse(url="/wallet", status_code=303)


@router.get("/book", name="book_page")
def book_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    settings = get_settings()
    return request.app.state.templates.TemplateResponse(
        "book.html",
        book_form_context(request, db, user, settings, error=None),
    )


@router.post("/vehicles/{vehicle_id}/delete", name="vehicle_delete")
def vehicle_delete(
    vehicle_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from fastapi import HTTPException
    v = db.scalars(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.user_id == user.id)).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()
    return RedirectResponse(url="/vehicles", status_code=303)