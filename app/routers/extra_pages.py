"""
Extra page routes: AI Vision, Booking History.
"""
from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, ParkingSlot, User
from app.services.booking_logic import to_local_display, utc_now

router = APIRouter(tags=["pages"])


@router.get("/ai-vision", name="ai_vision")
def ai_vision_page(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    return request.app.state.templates.TemplateResponse(
        "ai_vision.html",
        {"request": request, "user": user},
    )


@router.get("/history", name="history_page")
def history_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    bookings_raw = db.scalars(
        select(Booking)
        .where(Booking.user_id == user.id)
        .options(joinedload(Booking.vehicle), joinedload(Booking.slot))
        .order_by(Booking.start_time_utc.desc())
    ).all()

    bookings = []
    for b in bookings_raw:
        bookings.append({
            "id": b.id,
            "slot": b.slot,
            "vehicle": b.vehicle,
            "start_local": to_local_display(b.start_time_utc),
            "end_local": to_local_display(b.end_time_utc),
            "price_per_hour": b.price_per_hour,
            "status": b.status.value if hasattr(b.status, "value") else str(b.status),
            "qr_url": b.qr_code_path,
        })

    return request.app.state.templates.TemplateResponse(
        "history.html",
        {"request": request, "user": user, "bookings": bookings},
    )