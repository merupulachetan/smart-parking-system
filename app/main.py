from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.templating import Jinja2Templates

from app.database import Base, SessionLocal, engine
from app.db_migrate import (
    ensure_parking_slot_tier,
    ensure_vehicle_detail_columns,
    ensure_vehicle_plate_globally_unique,
    normalize_vehicle_plates_storage,
)
from app.models import ParkingSlot
from app.routers import auth, bookings, predictions, user_features, yolo_detect, extra_pages

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_vehicle_detail_columns()
    normalize_vehicle_plates_storage()
    ensure_vehicle_plate_globally_unique()
    ensure_parking_slot_tier()
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(ParkingSlot)) or 0
        if count == 0:
            for i in range(1, 16):
                db.add(ParkingSlot(slot_number=f"B{i:02d}", is_available=True, slot_tier="bike"))
            for i in range(1, 11):
                db.add(ParkingSlot(slot_number=f"A{i:02d}", is_available=True, slot_tier="car"))
            for i in range(1, 6):
                db.add(ParkingSlot(slot_number=f"C{i:02d}", is_available=True, slot_tier="commercial"))
            db.commit()
    (STATIC_DIR / "qr").mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Smart Parking", lifespan=lifespan)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Custom Jinja2 filter: vehicle_group_attr
    from app.services.booking_logic import vehicle_booking_group
    templates.env.filters["vehicle_group_attr"] = vehicle_booking_group

    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.exception_handler(HTTPException)
    async def http_exc_handler(request: Request, exc: HTTPException):
        accept = request.headers.get("accept", "")
        if exc.status_code == 401 and "text/html" in accept:
            return RedirectResponse(url="/login", status_code=303)
        detail = exc.detail
        body = {"detail": detail} if isinstance(detail, str) else {"detail": detail}
        return JSONResponse(body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    app.include_router(auth.router)
    app.include_router(user_features.router)
    app.include_router(bookings.router)
    app.include_router(predictions.router)
    app.include_router(yolo_detect.router)
    app.include_router(extra_pages.router)

    return app


app = create_app()