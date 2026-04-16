import json
import uuid
from pathlib import Path
from typing import Any

import qrcode

from app.config import get_settings


def generate_qr(data: dict[str, Any], filename: str | None = None) -> str:
    """
    Encode JSON in QR, save under static/qr/, return web-relative path (e.g. /static/qr/xxx.png).
    """
    settings = get_settings()
    out_dir = Path(settings.qr_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    name = filename or f"{uuid.uuid4().hex}.png"
    if not name.lower().endswith(".png"):
        name = f"{name}.png"

    path = out_dir / name
    payload = json.dumps(data, separators=(",", ":"), default=str)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img.save(path, format="PNG")

    rel = f"/static/qr/{path.name}"
    return rel
