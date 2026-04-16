import re
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


def normalize_plate(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().upper())


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Full name is required")
        return s


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class VehicleCreate(BaseModel):
    plate_number: str = Field(..., min_length=2, max_length=32)
    label: str | None = Field(None, max_length=100)

    @field_validator("plate_number")
    @classmethod
    def plate_ok(cls, v: str) -> str:
        p = normalize_plate(v)
        if len(p) < 2:
            raise ValueError("Invalid plate number")
        if not re.match(r"^[A-Z0-9\-]+$", p):
            raise ValueError("Plate may only contain letters, digits, and hyphen")
        return p


class VehicleRegistration(BaseModel):
    vehicle_type: str = Field(..., min_length=1, max_length=64)
    vehicle_subtype: str | None = Field(None, max_length=64)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    plate_number: str = Field(..., min_length=2, max_length=32)
    color: str | None = Field(None, max_length=64)

    @field_validator("plate_number")
    @classmethod
    def plate_ok(cls, v: str) -> str:
        p = normalize_plate(v)
        if len(p) < 2:
            raise ValueError("Invalid plate number")
        if not re.match(r"^[A-Z0-9\-]+$", p):
            raise ValueError("Plate may only contain letters, digits, and hyphen")
        return p

    @field_validator("vehicle_type")
    @classmethod
    def strip_type(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Vehicle type is required")
        return s

    @field_validator("color", "vehicle_subtype", "brand", "model", mode="before")
    @classmethod
    def empty_to_none(cls, v) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class WalletTopUp(BaseModel):
    amount: Decimal = Field(..., gt=0)


class BookCreate(BaseModel):
    vehicle_id: int = Field(..., ge=1)
    slot_id: int = Field(..., ge=1)
    duration_hours: float = Field(..., gt=0, le=168)

    @field_validator("duration_hours")
    @classmethod
    def duration_round(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Duration must be positive")
        return round(v, 2)


class ExitRequest(BaseModel):
    plate_number: str = Field(..., min_length=2, max_length=32)

    @field_validator("plate_number")
    @classmethod
    def plate_ok(cls, v: str) -> str:
        return normalize_plate(v)


class ExtendBooking(BaseModel):
    extend_hours: float = Field(..., ge=0.25, le=168)

    @field_validator("extend_hours")
    @classmethod
    def hours_round(cls, v: float) -> float:
        return round(v, 2)


class BookingStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    booking_id: int
    status: str
    remaining_seconds: int
    warning: bool
    message: str | None = None