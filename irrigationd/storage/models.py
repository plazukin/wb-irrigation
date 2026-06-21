from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ignore_rain_sensor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    cooldown_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    last_validation_status: Mapped[Optional[str]] = mapped_column(Text)
    last_validation_message: Mapped[Optional[str]] = mapped_column(Text)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    schedules: Mapped[list[ScheduleModel]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
    relays: Mapped[list[RelayModel]] = relationship(back_populates="zone")


class RelayModel(Base):
    __tablename__ = "relays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    zone_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"), index=True
    )
    relay_device_id: Mapped[Optional[str]] = mapped_column(Text)
    relay_control_id: Mapped[Optional[str]] = mapped_column(Text)
    relay_state_topic: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    relay_set_topic: Mapped[str] = mapped_column(Text, nullable=False)
    last_validation_status: Mapped[Optional[str]] = mapped_column(Text)
    last_validation_message: Mapped[Optional[str]] = mapped_column(Text)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    zone: Mapped[Optional[ZoneModel]] = relationship(back_populates="relays")


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    watering_mode: Mapped[str] = mapped_column(
        String(10), nullable=False, default="timer"
    )
    liters_per_m2: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    zone: Mapped[ZoneModel] = relationship(back_populates="schedules")


class WateringRunModel(Base):
    __tablename__ = "watering_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    planned_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    stop_reason: Mapped[Optional[str]] = mapped_column(Text)
    target_liters: Mapped[Optional[float]] = mapped_column(Float)
    delivered_liters: Mapped[Optional[float]] = mapped_column(Float)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    zone_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)


class RainSensorModel(Base):
    __tablename__ = "rain_sensor_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    device_id: Mapped[Optional[str]] = mapped_column(Text)
    control_id: Mapped[Optional[str]] = mapped_column(Text)
    topic: Mapped[Optional[str]] = mapped_column(Text)
    active_value: Mapped[str] = mapped_column(String(1), nullable=False, default="1")
    last_validation_status: Mapped[Optional[str]] = mapped_column(Text)
    last_validation_message: Mapped[Optional[str]] = mapped_column(Text)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PumpModel(Base):
    __tablename__ = "pump_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    relay_device_id: Mapped[Optional[str]] = mapped_column(Text)
    relay_control_id: Mapped[Optional[str]] = mapped_column(Text)
    relay_state_topic: Mapped[Optional[str]] = mapped_column(Text)
    relay_set_topic: Mapped[Optional[str]] = mapped_column(Text)
    start_delay_sec: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    last_validation_status: Mapped[Optional[str]] = mapped_column(Text)
    last_validation_message: Mapped[Optional[str]] = mapped_column(Text)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class FlowMeterModel(Base):
    __tablename__ = "flow_meter_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    device_id: Mapped[Optional[str]] = mapped_column(Text)
    control_id: Mapped[Optional[str]] = mapped_column(Text)
    topic: Mapped[Optional[str]] = mapped_column(Text)
    min_flow_l_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    startup_grace_sec: Mapped[float] = mapped_column(Float, nullable=False, default=10)
    stale_timeout_sec: Mapped[float] = mapped_column(Float, nullable=False, default=15)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
