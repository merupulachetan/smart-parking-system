import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookingStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Vehicle(Base):
    __tablename__ = "vehicles"
    # One plate number = one vehicle in the system (not per user).

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plate_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="vehicles")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="vehicle")


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slot_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    # bike = two-wheelers · car = cars/SUV · commercial = trucks/tempo (cars & trucks both use car+commercial bays)
    slot_tier: Mapped[str] = mapped_column(String(16), default="car", index=True)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="slot")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("parking_slots.id", ondelete="CASCADE"))

    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    price_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    extra_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    qr_code_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    actual_exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.active,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="bookings")
    vehicle: Mapped["Vehicle"] = relationship(back_populates="bookings")
    slot: Mapped["ParkingSlot"] = relationship(back_populates="bookings")
