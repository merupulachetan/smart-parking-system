from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services import prediction_service

router = APIRouter(tags=["predictions"])


@router.get("/predictions")
def predictions_api(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    try:
        rows, _ = prediction_service.compute_predictions_cached(db, hours=6)
    except Exception:
        return JSONResponse({"predictions": [], "error": "prediction_failed"})
    return JSONResponse(
        {
            "predictions": [
                {"hour": r["hour"], "value": r["predicted"]} for r in rows
            ],
        }
    )


@router.get("/predictions/view", name="predictions_view")
def predictions_view(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    templates = request.app.state.templates
    try:
        rows, threshold = prediction_service.compute_predictions_cached(db, hours=6)
    except Exception:
        rows = []
        threshold = 2.0
    chart_labels = [r["hour"] for r in rows]
    chart_values = [r["predicted"] for r in rows]
    try:
        vehicle_mix = prediction_service.booking_vehicle_category_mix(db)
    except Exception:
        vehicle_mix = []
    pie_labels = [x["label"] for x in vehicle_mix]
    pie_values = [x["count"] for x in vehicle_mix]
    return templates.TemplateResponse(
        "predictions.html",
        {
            "request": request,
            "user": user,
            "predictions": rows,
            "threshold": threshold,
            "tz_label": prediction_service.display_tz_label(),
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "vehicle_mix": vehicle_mix,
            "pie_labels": pie_labels,
            "pie_values": pie_values,
        },
    )
