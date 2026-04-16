from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/smart_parking"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    default_price_per_hour: float = 50.0
    extra_rate_per_minute: float = 2.0
    warning_minutes_before_end: int = 10

    display_timezone: str = "Asia/Kolkata"

    tesseract_cmd: str | None = None
    yolo_plate_weights: str | None = None

    qr_output_dir: Path = BASE_DIR / "static" / "qr"


@lru_cache
def get_settings() -> Settings:
    return Settings()
