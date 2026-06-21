from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RelayTopicRequest(BaseModel):
    relay_device_id: Optional[str] = None
    relay_control_id: Optional[str] = None
    relay_state_topic: Optional[str] = None
    relay_set_topic: Optional[str] = None


class RainTopicRequest(BaseModel):
    device_id: Optional[str] = None
    control_id: Optional[str] = None
    topic: Optional[str] = None


class RelayRequest(RelayTopicRequest):
    name: str


class RelayPatch(BaseModel):
    name: Optional[str] = None
    relay_device_id: Optional[str] = None
    relay_control_id: Optional[str] = None
    relay_state_topic: Optional[str] = None
    relay_set_topic: Optional[str] = None


class ZoneRequest(BaseModel):
    name: str
    enabled: bool = True
    relay_ids: list[int] = Field(min_length=1)
    ignore_rain_sensor: bool = False
    max_duration_min: float = Field(default=15, gt=0, allow_inf_nan=False)
    cooldown_min: float = Field(default=0, ge=0, allow_inf_nan=False)
    area_m2: float = Field(default=1, gt=0, allow_inf_nan=False)


class ZonePatch(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    relay_ids: Optional[list[int]] = Field(default=None, min_length=1)
    ignore_rain_sensor: Optional[bool] = None
    max_duration_min: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    cooldown_min: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    area_m2: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)


class StartRequest(BaseModel):
    watering_mode: Literal["timer", "volume"] = "timer"
    duration_min: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    liters_per_m2: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_mode(self) -> StartRequest:
        if self.watering_mode == "timer" and self.duration_min is None:
            raise ValueError("Укажите длительность полива")
        if self.watering_mode == "volume" and self.liters_per_m2 is None:
            raise ValueError("Укажите норму расхода воды")
        return self


class ScheduleRequest(BaseModel):
    zone_id: int
    enabled: bool = True
    days_of_week: str
    start_time: str
    watering_mode: Literal["timer", "volume"] = "timer"
    duration_min: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    liters_per_m2: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_format(self) -> ScheduleRequest:
        if self.watering_mode == "timer" and self.duration_min is None:
            raise ValueError("Укажите длительность полива")
        if self.watering_mode == "volume" and self.liters_per_m2 is None:
            raise ValueError("Укажите норму расхода воды")
        days = {item.strip() for item in self.days_of_week.split(",")}
        if not days or not days <= {str(i) for i in range(7)}:
            raise ValueError("Укажите дни недели числами от 0 до 6 через запятую")
        try:
            hour, minute = (int(part) for part in self.start_time.split(":"))
        except (ValueError, TypeError) as exc:
            raise ValueError("Укажите время в формате ЧЧ:ММ") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Укажите время в формате ЧЧ:ММ")
        self.start_time = f"{hour:02d}:{minute:02d}"
        self.days_of_week = ",".join(sorted(days))
        return self


class SchedulePatch(BaseModel):
    zone_id: Optional[int] = None
    enabled: Optional[bool] = None
    days_of_week: Optional[str] = None
    start_time: Optional[str] = None
    duration_min: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    watering_mode: Optional[Literal["timer", "volume"]] = None
    liters_per_m2: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)


class RainSensorRequest(RainTopicRequest):
    enabled: bool = False
    active_value: str = "1"

    @model_validator(mode="after")
    def validate_active_value(self) -> RainSensorRequest:
        if self.active_value not in {"0", "1"}:
            raise ValueError("active_value должен быть равен 0 или 1")
        if self.enabled and not self.topic and not (self.device_id and self.control_id):
            raise ValueError("Укажите MQTT-топик или устройство и канал датчика дождя")
        return self


class PumpRequest(RelayTopicRequest):
    enabled: bool = False
    start_delay_sec: float = Field(default=1, ge=0, le=60, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_topics(self) -> PumpRequest:
        configured = (
            self.relay_state_topic and self.relay_set_topic
        ) or (self.relay_device_id and self.relay_control_id)
        if self.enabled and not configured:
            raise ValueError("Укажите устройство и канал насоса или MQTT-топики")
        return self


class FlowMeterRequest(RainTopicRequest):
    enabled: bool = False
    min_flow_l_min: float = Field(default=0.1, gt=0, allow_inf_nan=False)
    startup_grace_sec: float = Field(default=10, ge=0, le=120, allow_inf_nan=False)
    stale_timeout_sec: float = Field(default=15, gt=0, le=300, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_topic(self) -> FlowMeterRequest:
        if self.enabled and not self.topic and not (self.device_id and self.control_id):
            raise ValueError("Укажите MQTT-топик или устройство и канал расходомера")
        return self
