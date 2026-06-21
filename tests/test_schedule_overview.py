from datetime import datetime, timezone
from types import SimpleNamespace

from irrigationd.web.schedule_overview import build_dashboard, build_weekly_map


def test_gantt_orders_zones_by_start_time() -> None:
    zones = [
        SimpleNamespace(id=1, name="Газон", enabled=True),
        SimpleNamespace(id=2, name="Теплица", enabled=True),
    ]
    schedules = [
        SimpleNamespace(
            id=1, zone_id=2, enabled=True, days_of_week="0",
            start_time="06:20", duration_sec=300,
        ),
        SimpleNamespace(
            id=2, zone_id=1, enabled=True, days_of_week="0,2",
            start_time="06:00", duration_sec=600,
        ),
    ]

    result = build_weekly_map(zones, schedules)
    monday = result["days"][0]["events"]

    assert result["has_events"] is True
    assert [event["zone_name"] for event in monday] == ["Газон", "Теплица"]
    assert [event["order"] for event in monday] == [1, 2]
    assert monday[0]["start"] == "06:00"
    assert monday[0]["end"] == "06:10"
    assert monday[0]["left"] < monday[1]["left"]
    assert result["days"][2]["events"][0]["zone_name"] == "Газон"


def test_gantt_splits_watering_at_midnight() -> None:
    zones = [SimpleNamespace(id=1, name="Газон", enabled=True)]
    schedules = [SimpleNamespace(
        id=1, zone_id=1, enabled=True, days_of_week="6",
        start_time="23:55", duration_sec=600,
    )]

    result = build_weekly_map(zones, schedules)

    sunday = result["days"][6]["events"][0]
    monday = result["days"][0]["events"][0]
    assert (sunday["start"], sunday["end"]) == ("23:55", "24:00")
    assert (monday["start"], monday["end"]) == ("00:00", "00:05")
    assert monday["continuation"] is True


def test_gantt_ignores_disabled_zones_and_schedules() -> None:
    zones = [SimpleNamespace(id=1, name="Газон", enabled=False)]
    schedules = [SimpleNamespace(
        id=1, zone_id=1, enabled=True, days_of_week="0",
        start_time="06:00", duration_sec=600,
    )]

    assert build_weekly_map(zones, schedules)["has_events"] is False


def test_gantt_compresses_long_idle_periods() -> None:
    zones = [SimpleNamespace(id=1, name="Газон", enabled=True)]
    schedules = [
        SimpleNamespace(
            id=1, zone_id=1, enabled=True, days_of_week="0",
            start_time="06:00", duration_sec=600,
        ),
        SimpleNamespace(
            id=2, zone_id=1, enabled=True, days_of_week="0",
            start_time="18:00", duration_sec=600,
        ),
    ]

    result = build_weekly_map(zones, schedules)
    events = result["days"][0]["events"]

    assert result["compressed"] is True
    assert len(result["breaks"]) == 1
    assert [tick["label"] for tick in result["ticks"]] == [
        "06:00", "18:00", "18:10",
    ]
    assert events[1]["left"] < 80
    assert result["width"] == 600


def test_dashboard_shows_nearest_watering_and_zone_status() -> None:
    zones = [
        SimpleNamespace(id=1, name="Газон", enabled=True, relays=[1, 2]),
        SimpleNamespace(id=2, name="Теплица", enabled=False, relays=[3]),
    ]
    schedules = [SimpleNamespace(
        id=1, zone_id=1, enabled=True, days_of_week="0",
        start_time="06:00", duration_sec=600,
    )]
    rain = SimpleNamespace(enabled=True, topic="/rain", active_value="1")

    dashboard = build_dashboard(
        zones, schedules, [], rain, "1",
        datetime(2026, 6, 22, 5, 0, tzinfo=timezone.utc),
    )

    assert dashboard["next"]["zone_name"] == "Газон"
    assert dashboard["next"]["datetime"] == "Понедельник, 22.06.2026 06:00"
    assert dashboard["zones"][0]["status"] == "Готова"
    assert dashboard["zones"][0]["relay_count"] == 2
    assert dashboard["zones"][1]["status"] == "Отключена"
    assert dashboard["rain"]["status"] == "Дождь"


def test_dashboard_marks_active_zone_and_omits_unconfigured_rain_sensor() -> None:
    zone = SimpleNamespace(id=1, name="Газон", enabled=True, relays=[1])
    run = SimpleNamespace(
        zone_id=1,
        started_at=datetime(2026, 6, 22, 5, 0, tzinfo=timezone.utc),
        planned_duration_sec=600,
    )
    rain = SimpleNamespace(enabled=False, topic=None, active_value="1")

    dashboard = build_dashboard(
        [zone], [], [run], rain, None,
        datetime(2026, 6, 22, 5, 5, tzinfo=timezone.utc),
    )

    assert dashboard["zones"][0]["status"] == "Полив"
    assert dashboard["zones"][0]["detail"] == "до 05:10"
    assert dashboard["rain"] is None
