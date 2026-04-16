"""
YOLO-based parking slot detection API.
Accepts a base64 image, runs YOLOv8 inference, and returns detected objects
with bounding boxes. The frontend renders annotations + slot occupancy logic.
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.deps import get_current_user
from app.models import User
from typing import Annotated

logger = logging.getLogger(__name__)

router = APIRouter(tags=["yolo"])

# Path to the trained best.pt inside the package
_WEIGHTS = Path(__file__).resolve().parent.parent / "ml_models" / "best.pt"

# Cache the model so it loads once
_model_cache: Any = None


def _load_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    try:
        from ultralytics import YOLO
        weights = str(_WEIGHTS) if _WEIGHTS.exists() else "yolov8n.pt"
        _model_cache = YOLO(weights)
        logger.info("YOLO model loaded from: %s", weights)
    except Exception as e:
        logger.warning("Could not load YOLO: %s — using mock detections", e)
        _model_cache = None
    return _model_cache


class DetectRequest(BaseModel):
    image: str  # data:image/jpeg;base64,<data>  OR raw base64


def _parse_image(data_url: str) -> bytes:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


def _run_yolo(model, img_bytes: bytes) -> list[dict]:
    import cv2
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Cannot decode image")
    results = model(img, verbose=False)
    detections = []
    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = model.names[cls_id]
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append({
            "cls_id": cls_id,
            "name": name,
            "conf": round(conf, 3),
            "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
        })
    return detections


def _mock_detections(img_bytes: bytes) -> list[dict]:
    """Return plausible mock detections when YOLO is unavailable (e.g. server env)."""
    import struct
    seed = int.from_bytes(img_bytes[100:104], "big") if len(img_bytes) > 104 else 42
    rng = __import__("random").Random(seed)
    classes = [
        ("car", 2), ("car", 2), ("car", 2),
        ("motorcycle", 3), ("truck", 7),
    ]
    out = []
    for name, cls_id in classes[:rng.randint(2, 5)]:
        x1 = rng.randint(30, 600)
        y1 = rng.randint(100, 250)
        w  = rng.randint(80, 160)
        h  = rng.randint(60, 110)
        out.append({
            "cls_id": cls_id,
            "name": name,
            "conf": round(rng.uniform(0.55, 0.95), 3),
            "box": [float(x1), float(y1), float(x1+w), float(y1+h)],
        })
    return out


@router.post("/api/yolo-detect")
async def yolo_detect(
    req: DetectRequest,
    _: Annotated[User, Depends(get_current_user)],
):
    try:
        img_bytes = _parse_image(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    model = _load_model()
    try:
        if model is not None:
            detections = _run_yolo(model, img_bytes)
        else:
            detections = _mock_detections(img_bytes)
    except Exception as e:
        logger.exception("YOLO inference error")
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

    return JSONResponse({
        "detections": detections,
        "model": "yolov8n-best.pt" if (_WEIGHTS.exists() and model is not None) else "yolov8n (mock)",
        "count": len(detections),
    })
