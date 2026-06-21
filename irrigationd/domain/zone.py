from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class ZoneInput:
    name: str
    enabled: bool = True
    relay_ids: list[int] = field(default_factory=list)
    ignore_rain_sensor: bool = False
    max_duration_sec: int = 900
    cooldown_sec: int = 0
    area_m2: float = 1


def model_dict(model: Any) -> dict[str, Any]:
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
    }


def jsonable_model(model: Any) -> dict[str, Any]:
    result = model_dict(model)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result
