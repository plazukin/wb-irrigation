from __future__ import annotations

import math


def minutes_to_seconds(minutes: float, allow_zero: bool = False) -> int:
    if not math.isfinite(minutes):
        raise ValueError("Укажите конечное значение длительности")
    if minutes < 0 or (minutes == 0 and not allow_zero):
        raise ValueError("Длительность должна быть больше нуля")
    return max(0 if allow_zero else 1, int(round(minutes * 60)))


def seconds_to_minutes(seconds: int) -> float:
    return round(seconds / 60, 3)
