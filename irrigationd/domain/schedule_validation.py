from __future__ import annotations

from typing import Any, Optional

WEEK_SECONDS = 7 * 24 * 60 * 60


def _intervals(days_of_week: str, start_time: str, duration_sec: int):
    hour, minute = (int(part) for part in start_time.split(":"))
    start_in_day = (hour * 60 + minute) * 60
    for day in days_of_week.split(","):
        start = int(day) * 24 * 60 * 60 + start_in_day
        yield start, start + duration_sec


def find_schedule_overlap(
    days_of_week: str, start_time: str, duration_sec: int,
    enabled: bool, schedules: list[Any], exclude_id: Optional[int] = None,
) -> Optional[Any]:
    if not enabled:
        return None
    candidate_intervals = list(_intervals(
        days_of_week, start_time, duration_sec
    ))
    for schedule in schedules:
        if not schedule.enabled or schedule.id == exclude_id:
            continue
        for start, end in candidate_intervals:
            for other_start, other_end in _intervals(
                schedule.days_of_week, schedule.start_time,
                schedule.duration_sec,
            ):
                for shift in (-WEEK_SECONDS, 0, WEEK_SECONDS):
                    shifted_start = other_start + shift
                    shifted_end = other_end + shift
                    if start < shifted_end and shifted_start < end:
                        return schedule
    return None
