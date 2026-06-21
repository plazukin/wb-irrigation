from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from irrigationd.storage.models import WateringRunModel, ZoneModel


class SafetyError(RuntimeError):
    pass


def validate_start(
    zone: ZoneModel, duration_sec: Optional[int],
    relay_values: list[Optional[str]],
    active_runs: list[WateringRunModel], allow_parallel: bool,
) -> int:
    if not zone.enabled:
        raise SafetyError("Зона отключена")
    if duration_sec is None or duration_sec <= 0:
        raise SafetyError("Длительность должна быть больше нуля")
    if duration_sec > zone.max_duration_sec:
        raise SafetyError("Превышена максимальная длительность для зоны")
    if not relay_values or any(value is None for value in relay_values):
        raise SafetyError("Состояние реле неизвестно")
    if any(value != "0" for value in relay_values):
        raise SafetyError("Одно из реле уже включено")
    if any(run.zone_id == zone.id for run in active_runs):
        raise SafetyError("Зона уже запущена")
    if active_runs and not allow_parallel:
        raise SafetyError("Уже запущена другая зона")
    return duration_sec


def cooldown_remaining(zone: ZoneModel, latest_finished_at: Optional[datetime]) -> int:
    if not latest_finished_at or zone.cooldown_sec <= 0:
        return 0
    if latest_finished_at.tzinfo is None:
        latest_finished_at = latest_finished_at.replace(tzinfo=timezone.utc)
    elapsed = int((datetime.now(timezone.utc) - latest_finished_at).total_seconds())
    return max(0, zone.cooldown_sec - elapsed)
