from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, get_current_user_optional
from app.models import Booking, BookingStatus, ParkingSlot, User, Vehicle
from app.schemas import BookCreate, BookingStatusResponse, ExitRequest, ExtendBooking, normalize_plate
from app.services.booking_logic import (
    compute_exit_charges,
    remaining_seconds_until,
    slot_tier_allowed_for_vehicle_group,
    to_local_display,
    total_exit_amount,
    utc_now,
    vehicle_booking_group,
    vehicle_ids_with_active_booking_for_user,
    warning_active,
)
from app.services.qr_service import generate_qr

router = APIRouter(tags=["bookings"])


def book_form_context(
    request: Request,
    db: Session,
    user: User,
    settings,
    *,
    error: str | None = None,
) -> dict:
    vehicles = db.scalars(select(Vehicle).where(Vehicle.user_id == user.id)).all()
    slots = db.scalars(
        select(ParkingSlot).where(ParkingSlot.is_available == True).order_by(ParkingSlot.slot_number)  # noqa: E712
    ).all()
    all_occupied_slots = db.scalars(
        select(ParkingSlot).where(ParkingSlot.is_available == False).order_by(ParkingSlot.slot_number)  # noqa: E712
    ).all()
    return {
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "slots": slots,
        "all_occupied_slots": all_occupied_slots,
        "price_per_hour": settings.default_price_per_hour,
        "error": error,
        "vehicles_with_active_booking": vehicle_ids_with_active_booking_for_user(db, user.id),
        "vehicles_booking": [{"id": v.id, "g": vehicle_booking_group(v)} for v in vehicles],
        "slots_booking": [
            {"id": s.id, "n": s.slot_number, "t": (s.slot_tier or "car")} for s in slots
        ],
    }


def _get_booking_for_user(db: Session, booking_id: int, user_id: int) -> Booking:
    b = db.scalars(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user_id)
        .options(joinedload(Booking.vehicle), joinedload(Booking.slot))
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    return b


@router.post("/book", name="create_booking")
async def create_booking(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    settings = get_settings()
    ctype = request.headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            body = await request.json()
            data = BookCreate.model_validate(body)
        else:
            form = await request.form()
            data = BookCreate(
                vehicle_id=int(form.get("vehicle_id", 0)),
                slot_id=int(form.get("slot_id", 0)),
                duration_hours=float(form.get("duration_hours", 0)),
            )
    except (ValidationError, ValueError, TypeError) as e:
        if "application/json" in request.headers.get("content-type", ""):
            if isinstance(e, ValidationError):
                raise HTTPException(status_code=422, detail=e.errors()) from e
            raise HTTPException(status_code=422, detail=str(e)) from e
        msg = "Invalid booking data."
        if isinstance(e, ValidationError) and e.errors():
            msg = str(e.errors()[0].get("msg", msg))
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(request, db, user, settings, error=msg),
            status_code=422,
        )

    vehicle = db.get(Vehicle, data.vehicle_id)
    if not vehicle or vehicle.user_id != user.id:
        if "application/json" in ctype:
            raise HTTPException(status_code=400, detail="Invalid vehicle")
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(request, db, user, settings, error="Invalid vehicle selected."),
            status_code=400,
        )

    price_per_hour = Decimal(str(settings.default_price_per_hour))
    hours = Decimal(str(data.duration_hours))
    base_price = (hours * price_per_hour).quantize(Decimal("0.01"))

    start = utc_now()
    end = start + timedelta(hours=float(data.duration_hours))

    slot = db.scalars(
        select(ParkingSlot).where(ParkingSlot.id == data.slot_id).with_for_update()
    ).first()
    if not slot or not slot.is_available:
        db.rollback()
        if "application/json" in ctype:
            raise HTTPException(status_code=400, detail="Slot not available")
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(request, db, user, settings, error="That slot is no longer available."),
            status_code=400,
        )

    v_group = vehicle_booking_group(vehicle)
    if not slot_tier_allowed_for_vehicle_group(slot.slot_tier, v_group):
        db.rollback()
        if "application/json" in ctype:
            raise HTTPException(
                status_code=400,
                detail="Slot tier does not match vehicle type (bike vs car/truck).",
            )
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(
                request,
                db,
                user,
                settings,
                error="That slot is not valid for this vehicle. Bikes use B slots; cars and trucks use A or C slots.",
            ),
            status_code=400,
        )

    if user.wallet_balance < base_price:
        db.rollback()
        if "application/json" in ctype:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(
                request, db, user, settings, error="Insufficient wallet balance. Top up first."
            ),
            status_code=400,
        )

    already = db.scalars(
        select(Booking).where(
            Booking.vehicle_id == vehicle.id,
            Booking.status == BookingStatus.active,
        )
    ).first()
    if already:
        db.rollback()
        if "application/json" in ctype:
            raise HTTPException(
                status_code=400,
                detail="This vehicle already has an active booking. Extend or cancel from the dashboard.",
            )
        return request.app.state.templates.TemplateResponse(
            "book.html",
            book_form_context(
                request,
                db,
                user,
                settings,
                error="This vehicle already has an active booking. Extend time or cancel from the dashboard.",
            ),
            status_code=400,
        )

    user.wallet_balance = user.wallet_balance - base_price
    slot.is_available = False

    booking = Booking(
        user_id=user.id,
        vehicle_id=vehicle.id,
        slot_id=slot.id,
        start_time_utc=start,
        end_time_utc=end,
        price_per_hour=price_per_hour,
        base_price=base_price,
        extra_charge=Decimal("0"),
        status=BookingStatus.active,
    )
    db.add(booking)
    db.flush()

    qr_payload = {
        "email": user.email,
        "vehicle_number": vehicle.plate_number,
        "slot": slot.slot_number,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "price_per_hour": float(price_per_hour),
    }
    qr_rel_path = generate_qr(qr_payload, filename=f"booking_{booking.id}.png")
    booking.qr_code_path = qr_rel_path
    db.add(booking)
    db.add(user)
    db.add(slot)
    db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse(
            {
                "id": booking.id,
                "qr_code_path": qr_rel_path,
                "base_price": str(base_price),
                "message": "Booked",
            }
        )
    return RedirectResponse(url=f"/booking/{booking.id}/success", status_code=303)


@router.get("/booking/{booking_id}", name="booking_detail")
def get_booking(
    request: Request,
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = _get_booking_for_user(db, booking_id, user.id)
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse(
            {
                "id": b.id,
                "vehicle_plate": b.vehicle.plate_number,
                "slot_number": b.slot.slot_number,
                "start_time_utc": b.start_time_utc.isoformat(),
                "end_time_utc": b.end_time_utc.isoformat(),
                "price_per_hour": str(b.price_per_hour),
                "base_price": str(b.base_price),
                "extra_charge": str(b.extra_charge),
                "status": b.status.value,
                "qr_code_url": b.qr_code_path,
            }
        )
    settings = get_settings()
    return request.app.state.templates.TemplateResponse(
        "booking_detail.html",
        {
            "request": request,
            "user": user,
            "booking": b,
            "start_local": to_local_display(b.start_time_utc),
            "end_local": to_local_display(b.end_time_utc),
            "tz_label": settings.display_timezone,
        },
    )


@router.get("/booking/{booking_id}/success", name="booking_success")
def booking_success(
    request: Request,
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = _get_booking_for_user(db, booking_id, user.id)
    settings = get_settings()
    return request.app.state.templates.TemplateResponse(
        "booking_success.html",
        {
            "request": request,
            "user": user,
            "booking": b,
            "start_local": to_local_display(b.start_time_utc),
            "end_local": to_local_display(b.end_time_utc),
            "tz_label": settings.display_timezone,
            "qr_url": b.qr_code_path,
        },
    )


@router.get("/booking/{booking_id}/preview", name="booking_preview")
def booking_preview(
    request: Request,
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = _get_booking_for_user(db, booking_id, user.id)
    settings = get_settings()
    return request.app.state.templates.TemplateResponse(
        "booking_preview.html",
        {
            "request": request,
            "user": user,
            "booking": b,
            "start_local": to_local_display(b.start_time_utc),
            "end_local": to_local_display(b.end_time_utc),
            "tz_label": settings.display_timezone,
            "qr_url": b.qr_code_path,
        },
    )


@router.get("/booking/{booking_id}/status", name="booking_status")
def booking_status_api(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = _get_booking_for_user(db, booking_id, user.id)
    settings = get_settings()
    now = utc_now()
    rem = remaining_seconds_until(b.end_time_utc, now)
    warn = warning_active(rem, settings.warning_minutes_before_end)
    msg = None
    if warn:
        msg = "Your booking will expire soon"
    if b.status != BookingStatus.active:
        rem = 0
        warn = False
        msg = "Booking is not active"
    body = BookingStatusResponse(
        booking_id=b.id,
        status=b.status.value,
        remaining_seconds=rem,
        warning=warn,
        message=msg,
    )
    return JSONResponse(body.model_dump())


@router.get("/booking/{booking_id}/qr/download", name="booking_qr_download")
def download_qr(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = _get_booking_for_user(db, booking_id, user.id)
    if not b.qr_code_path:
        raise HTTPException(status_code=404, detail="No QR code")
    base = Path(__file__).resolve().parent.parent.parent
    fname = b.qr_code_path.rsplit("/", 1)[-1]
    path = base / "static" / "qr" / fname
    if not path.is_file():
        raise HTTPException(status_code=404, detail="QR file missing")
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"booking_{booking_id}_qr.png",
    )


@router.post("/booking/{booking_id}/extend", name="extend_booking")
async def extend_booking(
    request: Request,
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    form = await request.form()
    try:
        data = ExtendBooking(extend_hours=float(form.get("extend_hours", 0)))
    except (ValidationError, ValueError, TypeError):
        return RedirectResponse(url="/dashboard?notice=invalid_extend", status_code=303)

    b = db.scalars(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user.id)
        .with_for_update()
    ).first()
    if not b or b.status != BookingStatus.active:
        db.rollback()
        return RedirectResponse(url="/dashboard?notice=booking_not_found", status_code=303)

    additional = (Decimal(str(data.extend_hours)) * b.price_per_hour).quantize(Decimal("0.01"))
    if user.wallet_balance < additional:
        db.rollback()
        return RedirectResponse(url="/dashboard?notice=no_balance", status_code=303)

    user.wallet_balance = user.wallet_balance - additional
    b.base_price = b.base_price + additional
    b.end_time_utc = b.end_time_utc + timedelta(hours=float(data.extend_hours))

    vehicle = db.get(Vehicle, b.vehicle_id)
    slot = db.get(ParkingSlot, b.slot_id)
    qr_payload = {
        "email": user.email,
        "vehicle_number": vehicle.plate_number,
        "slot": slot.slot_number,
        "start_time": b.start_time_utc.isoformat(),
        "end_time": b.end_time_utc.isoformat(),
        "price_per_hour": float(b.price_per_hour),
    }
    b.qr_code_path = generate_qr(qr_payload, filename=f"booking_{b.id}.png")

    db.add(b)
    db.add(user)
    db.commit()
    return RedirectResponse(url="/dashboard?notice=extended", status_code=303)


@router.post("/booking/{booking_id}/cancel", name="cancel_booking")
def cancel_booking(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    b = db.scalars(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user.id)
        .with_for_update()
    ).first()
    if not b or b.status != BookingStatus.active:
        db.rollback()
        return RedirectResponse(url="/dashboard?notice=booking_not_found", status_code=303)

    slot = db.get(ParkingSlot, b.slot_id)
    if not slot:
        db.rollback()
        return RedirectResponse(url="/dashboard?notice=booking_not_found", status_code=303)

    user.wallet_balance = (user.wallet_balance or Decimal("0")) + b.base_price
    b.status = BookingStatus.cancelled
    slot.is_available = True

    db.add(user)
    db.add(b)
    db.add(slot)
    db.commit()
    return RedirectResponse(url="/dashboard?notice=cancelled", status_code=303)


@router.get("/exit", name="exit_page")
def exit_page(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user_optional)],
):
    return request.app.state.templates.TemplateResponse(
        "exit.html",
        {"request": request, "user": user, "error": None, "result": None},
    )


@router.post("/exit", name="exit_parking")
async def exit_parking(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user_optional)],
):
    ctype = request.headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            body = await request.json()
            data = ExitRequest.model_validate(body)
            plate = data.plate_number
        else:
            form = await request.form()
            raw = str(form.get("plate_number", "")).strip()
            if len(raw) < 2:
                raise ValueError("Plate number is required")
            plate = normalize_plate(raw)
    except (ValidationError, ValueError) as e:
        if "application/json" in ctype:
            if isinstance(e, ValidationError):
                raise HTTPException(status_code=422, detail=e.errors()) from e
            raise HTTPException(status_code=422, detail=str(e)) from e
        msg = str(e)
        if isinstance(e, ValidationError) and e.errors():
            msg = str(e.errors()[0].get("msg", msg))
        return request.app.state.templates.TemplateResponse(
            "exit.html",
            {"request": request, "user": user, "error": msg, "result": None},
            status_code=422,
        )

    booking = db.scalars(
        select(Booking)
        .join(Vehicle)
        .where(Booking.status == BookingStatus.active, Vehicle.plate_number == plate)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.slot),
            joinedload(Booking.vehicle),
        )
    ).first()

    if not booking:
        if "application/json" in ctype:
            raise HTTPException(status_code=404, detail="No active booking for this plate")
        return request.app.state.templates.TemplateResponse(
            "exit.html",
            {
                "request": request,
                "user": user,
                "error": "No active booking found for that plate.",
                "result": None,
            },
            status_code=404,
        )

    now = utc_now()
    extra_charge, extra_minutes = compute_exit_charges(
        booking.end_time_utc,
        booking.base_price,
        booking.price_per_hour,
        now_utc=now,
    )
    owner = booking.user
    if owner.wallet_balance < extra_charge:
        if "application/json" in ctype:
            raise HTTPException(
                status_code=400,
                detail="Insufficient wallet balance for overstay charges",
            )
        return request.app.state.templates.TemplateResponse(
            "exit.html",
            {
                "request": request,
                "user": user,
                "error": f"Insufficient balance for overstay (₹{extra_charge}). Please top up.",
                "result": None,
            },
            status_code=400,
        )

    owner.wallet_balance = owner.wallet_balance - extra_charge
    booking.extra_charge = extra_charge
    booking.actual_exit_time = now
    booking.status = BookingStatus.completed
    booking.slot.is_available = True
    db.add(owner)
    db.add(booking.slot)
    db.add(booking)
    db.commit()

    total = total_exit_amount(booking.base_price, extra_charge)
    payload = {
        "plate_number": plate,
        "base_price": str(booking.base_price),
        "extra_charge": str(extra_charge),
        "extra_minutes": extra_minutes,
        "total_billed": str(total),
        "exit_time_utc": now.isoformat(),
        "slot_freed": booking.slot.slot_number,
    }

    if "application/json" in ctype and "text/html" not in request.headers.get("accept", ""):
        return JSONResponse(payload)

    return request.app.state.templates.TemplateResponse(
        "exit.html",
        {"request": request, "user": user, "error": None, "result": payload},
    )


@router.post("/detect-plate")
async def detect_plate(file: UploadFile = File(...)):
    from app.services.plate_service import extract_plate_from_image

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB)")
    plate = extract_plate_from_image(data)
    if not plate:
        return JSONResponse({"plate_number": None, "message": "Could not read a plate. Try a clearer photo."})
    return JSONResponse({"plate_number": plate})


@router.post("/exit/{booking_id}", name="exit_by_id")
async def exit_by_id(
    booking_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Quick exit from history page — marks booking completed."""
    from app.services.booking_logic import compute_exit_charges, total_exit_amount
    b = _get_booking_for_user(db, booking_id, user.id)
    if b.status != BookingStatus.active:
        return RedirectResponse(url="/history", status_code=303)
    settings = get_settings()
    now = utc_now()
    charges = compute_exit_charges(b, now, settings.extra_rate_per_minute)
    due = total_exit_amount(charges)
    b.status = BookingStatus.completed
    b.end_time_utc = now
    b.slot.is_available = True
    if due > 0:
        from decimal import Decimal
        user.wallet_balance = (user.wallet_balance or Decimal("0")) - Decimal(str(due))
    db.commit()
    return RedirectResponse(url="/history", status_code=303)


@router.post("/booking/{booking_id}/generate-qr", name="generate_qr_for_booking")
def generate_qr_for_booking(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Regenerate (or generate for first time) QR for any booking owned by user."""
    b = _get_booking_for_user(db, booking_id, user.id)
    vehicle = db.get(Vehicle, b.vehicle_id)
    slot = db.get(ParkingSlot, b.slot_id)
    qr_payload = {
        "booking_id": b.id,
        "email": user.email,
        "vehicle_number": vehicle.plate_number if vehicle else "N/A",
        "slot": slot.slot_number if slot else "N/A",
        "start_time": b.start_time_utc.isoformat(),
        "end_time": b.end_time_utc.isoformat(),
        "price_per_hour": float(b.price_per_hour),
        "status": b.status.value,
    }
    qr_path = generate_qr(qr_payload, filename=f"booking_{b.id}.png")
    b.qr_code_path = qr_path
    db.add(b)
    db.commit()
    return JSONResponse({"qr_url": qr_path, "booking_id": b.id})