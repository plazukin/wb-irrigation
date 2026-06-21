from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

WEEKDAYS = (
    ("Пн", "Понедельник"),
    ("Вт", "Вторник"),
    ("Ср", "Среда"),
    ("Чт", "Четверг"),
    ("Пт", "Пятница"),
    ("Сб", "Суббота"),
    ("Вс", "Воскресенье"),
)
DAY_SECONDS = 24 * 60 * 60
MAX_VISIBLE_IDLE_SECONDS = 5 * 60


def _datetime_label(value: datetime) -> str:
    day_name = WEEKDAYS[value.weekday()][1]
    return f"{day_name}, {value:%d.%m.%Y %H:%M}"


def _next_occurrence(schedule: Any, now: datetime) -> datetime:
    days = {int(value) for value in schedule.days_of_week.split(",")}
    hour, minute = (int(part) for part in schedule.start_time.split(":"))
    for offset in range(8):
        date = now.date() + timedelta(days=offset)
        if date.weekday() not in days:
            continue
        candidate = datetime.combine(
            date, time(hour, minute), tzinfo=now.tzinfo
        )
        if candidate >= now:
            return candidate
    raise RuntimeError("Не удалось определить следующий запуск")


def build_dashboard(
    zones: list[Any], schedules: list[Any], active_runs: list[Any],
    rain_sensor: Any, rain_value: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    active_by_zone = {run.zone_id: run for run in active_runs}
    zone_by_id = {zone.id: zone for zone in zones}
    next_by_zone: dict[int, tuple[datetime, Any]] = {}
    for schedule in schedules:
        zone = zone_by_id.get(schedule.zone_id)
        if not schedule.enabled or zone is None or not zone.enabled:
            continue
        candidate = _next_occurrence(schedule, now)
        current = next_by_zone.get(zone.id)
        if current is None or candidate < current[0]:
            next_by_zone[zone.id] = (candidate, schedule)

    zone_cards = []
    for zone in zones:
        active = active_by_zone.get(zone.id)
        next_item = next_by_zone.get(zone.id)
        if active:
            started = active.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            finish = started + timedelta(seconds=active.planned_duration_sec)
            status = "Полив"
            status_class = "active"
            detail = f"до {finish.astimezone(now.tzinfo):%H:%M}"
        elif not zone.enabled:
            status = "Отключена"
            status_class = "disabled"
            detail = "Запуски запрещены"
        else:
            status = "Готова"
            status_class = "ready"
            detail = "Ожидает запуска"
        zone_cards.append({
            "name": zone.name,
            "status": status,
            "status_class": status_class,
            "detail": detail,
            "relay_count": len(zone.relays),
            "next": _datetime_label(next_item[0]) if next_item else None,
        })

    all_next = [
        (candidate, schedule, zone_by_id[zone_id])
        for zone_id, (candidate, schedule) in next_by_zone.items()
    ]
    nearest = min(all_next, default=None, key=lambda item: item[0])
    next_card = None
    if nearest:
        candidate, schedule, zone = nearest
        next_card = {
            "zone_name": zone.name,
            "datetime": _datetime_label(candidate),
            "duration": f"{schedule.duration_sec / 60:g}",
            "watering_mode": getattr(schedule, "watering_mode", "timer"),
            "liters_per_m2": getattr(schedule, "liters_per_m2", None),
        }

    rain_card = None
    if rain_sensor.topic:
        if not rain_sensor.enabled:
            rain_status, rain_class, rain_detail = (
                "Отключён", "disabled", "Датчик не учитывается"
            )
        elif rain_value is None:
            rain_status, rain_class, rain_detail = (
                "Нет данных", "warning", "Запуск полива заблокирован"
            )
        elif rain_value not in {"0", "1"}:
            rain_status, rain_class, rain_detail = (
                "Ошибка", "warning", f"Получено значение {rain_value}"
            )
        elif rain_value == rain_sensor.active_value:
            rain_status, rain_class, rain_detail = (
                "Дождь", "rain", "Полив с учётом датчика заблокирован"
            )
        else:
            rain_status, rain_class, rain_detail = (
                "Сухо", "ready", "Полив разрешён"
            )
        rain_card = {
            "status": rain_status,
            "status_class": rain_class,
            "detail": rain_detail,
            "topic": rain_sensor.topic,
        }

    return {
        "now": _datetime_label(now),
        "next": next_card,
        "rain": rain_card,
        "zones": zone_cards,
    }


def _clock(seconds: int, end_of_day: bool = False) -> str:
    if end_of_day and seconds == DAY_SECONDS:
        return "24:00"
    seconds %= DAY_SECONDS
    hour, remainder = divmod(seconds, 3600)
    minute, second = divmod(remainder, 60)
    value = f"{hour:02d}:{minute:02d}"
    return f"{value}:{second:02d}" if second else value


def _segments(schedule: Any, zone: Any):
    hour, minute = (int(part) for part in schedule.start_time.split(":"))
    start_in_day = (hour * 60 + minute) * 60
    for day_value in schedule.days_of_week.split(","):
        start = int(day_value) * DAY_SECONDS + start_in_day
        end = start + schedule.duration_sec
        cursor = start
        first = True
        while cursor < end:
            absolute_day = cursor // DAY_SECONDS
            day_end = (absolute_day + 1) * DAY_SECONDS
            segment_end = min(end, day_end)
            local_start = cursor % DAY_SECONDS
            local_end = segment_end - absolute_day * DAY_SECONDS
            yield {
                "day": absolute_day % 7,
                "zone_id": zone.id,
                "zone_name": zone.name,
                "start_second": local_start,
                "end_second": local_end,
                "start": _clock(local_start),
                "end": _clock(local_end, end_of_day=True),
                "duration": f"{schedule.duration_sec / 60:g}",
                "continuation": not first,
            }
            cursor = segment_end
            first = False


def build_weekly_map(zones: list[Any], schedules: list[Any]) -> dict[str, Any]:
    zone_by_id = {zone.id: zone for zone in zones if zone.enabled}
    days = [
        {"short": short, "name": name, "events": []}
        for short, name in WEEKDAYS
    ]
    zone_order = {zone.id: index for index, zone in enumerate(zones)}
    for schedule in schedules:
        zone = zone_by_id.get(schedule.zone_id)
        if not schedule.enabled or zone is None:
            continue
        for event in _segments(schedule, zone):
            event["hue"] = (zone_order[zone.id] * 67 + 138) % 360
            days[event["day"]]["events"].append(event)

    events = [event for day in days for event in day["events"]]
    if not events:
        return {
            "days": days, "ticks": [], "breaks": [],
            "compressed": False, "has_events": False, "width": 600,
        }

    intervals = []
    for event in sorted(events, key=lambda item: item["start_second"]):
        start, end = event["start_second"], event["end_second"]
        if intervals and start <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], end)
        else:
            intervals.append([start, end])

    display_intervals = []
    breaks = []
    cursor = 0
    compressed = False
    previous_end = None
    for start, end in intervals:
        if previous_end is not None:
            actual_gap = start - previous_end
            visible_gap = min(actual_gap, MAX_VISIBLE_IDLE_SECONDS)
            if actual_gap > MAX_VISIBLE_IDLE_SECONDS:
                compressed = True
                breaks.append(cursor + visible_gap / 2)
            cursor += visible_gap
        display_start = cursor
        cursor += end - start
        display_intervals.append((start, end, display_start, cursor))
        previous_end = end

    span = max(cursor, 1)

    def display_position(value: int) -> float:
        for start, end, display_start, display_end in display_intervals:
            if start <= value <= end:
                return display_start + value - start
        raise RuntimeError("Время события отсутствует на шкале")

    ticks = []
    for index, (start, end, display_start, display_end) in enumerate(
        display_intervals
    ):
        ticks.append({"label": _clock(start), "left": display_start / span * 100})
        if index == len(display_intervals) - 1:
            ticks.append({
                "label": _clock(end, end_of_day=True),
                "left": display_end / span * 100,
            })

    for day in days:
        day["events"].sort(key=lambda item: item["start_second"])
        for order, event in enumerate(day["events"], 1):
            event["order"] = order
            start = display_position(event["start_second"])
            end = display_position(event["end_second"])
            event["left"] = start / span * 100
            event["width"] = (end - start) / span * 100

    return {
        "days": days,
        "ticks": ticks,
        "breaks": [position / span * 100 for position in breaks],
        "compressed": compressed,
        "has_events": True,
        "width": max(600, min(1200, int(span / 60 * 4))),
    }
