import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from irrigationd.config import SafetyConfig
from irrigationd.domain.irrigation_service import IrrigationService
from irrigationd.domain.state import ServiceState


class TraceMqtt:
    def __init__(self) -> None:
        self.values = {
            "/pump": SimpleNamespace(value="0"),
            "/zone": SimpleNamespace(value="0"),
            "/rain": SimpleNamespace(value="0"),
            "/flow": SimpleNamespace(
                value="0", updated_at=datetime.now(timezone.utc),
            ),
        }
        self.events = {topic: asyncio.Event() for topic in self.values}
        self.published = []

    def add_handler(self, handler) -> None:
        self.handler = handler

    def cached(self, topic):
        return self.values.get(topic)

    async def wait_for(self, topic, predicate, timeout, accept_cached=True):
        if accept_cached and predicate(self.values[topic].value):
            return self.values[topic].value
        event = self.events[topic]
        await asyncio.wait_for(event.wait(), timeout)
        value = self.values[topic].value
        self.events[topic] = asyncio.Event()
        if not predicate(value):
            raise asyncio.TimeoutError
        return value

    async def publish(self, topic, value, retain=False) -> None:
        self.published.append((topic, value))
        state_topic = topic.removesuffix("/on")
        self.values[state_topic] = SimpleNamespace(value=value)
        self.events[state_topic].set()


class FakeRuns:
    def __init__(self) -> None:
        self.items = []

    def active(self, zone_id=None):
        return [
            run for run in self.items
            if run.status == "running" and (zone_id is None or run.zone_id == zone_id)
        ]

    def latest_finished(self, zone_id):
        return None

    def create(self, zone_id, duration, source, target_liters=None):
        run = SimpleNamespace(
            id=len(self.items) + 1, zone_id=zone_id,
            started_at=datetime.now(timezone.utc),
            planned_duration_sec=duration, status="running", source=source,
            target_liters=target_liters, delivered_liters=0,
        )
        self.items.append(run)
        return run

    def finish(self, run_id, status, reason, delivered_liters=None):
        run = next(item for item in self.items if item.id == run_id)
        run.status = status
        run.stop_reason = reason
        run.delivered_liters = delivered_liters
        return run


@pytest.mark.asyncio
async def test_pump_wraps_zone_relay_commands() -> None:
    zone = SimpleNamespace(
        id=1, name="Газон", enabled=True, ignore_rain_sensor=False,
        max_duration_sec=300, cooldown_sec=0,
        relays=[SimpleNamespace(
            relay_state_topic="/zone", relay_set_topic="/zone/on",
        )],
    )
    mqtt = TraceMqtt()
    runs = FakeRuns()
    service = IrrigationService(
        zones=SimpleNamespace(get=lambda zone_id: zone, list=lambda: [zone]),
        runs=runs,
        events=SimpleNamespace(add=lambda *args: None),
        rain_sensor=SimpleNamespace(get=lambda: SimpleNamespace(enabled=False)),
        pump=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=True, relay_state_topic="/pump", relay_set_topic="/pump/on",
            start_delay_sec=0,
        )),
        flow_meter=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, topic=None,
        )),
        mqtt=mqtt,
        config=SafetyConfig(relay_confirm_timeout_sec=0.1),
        state=ServiceState(),
    )

    await service.start_zone(1, 60)
    await service.stop_zone(1)

    assert mqtt.published == [
        ("/pump/on", "1"),
        ("/zone/on", "1"),
        ("/pump/on", "0"),
        ("/zone/on", "0"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ignore_rain", "expected_status"),
    [(False, "stopped"), (True, "running")],
)
async def test_rain_stops_only_zone_using_sensor(
    ignore_rain, expected_status,
) -> None:
    zone = SimpleNamespace(
        id=1, name="Газон", enabled=True, ignore_rain_sensor=ignore_rain,
        max_duration_sec=300, cooldown_sec=0,
        relays=[SimpleNamespace(
            relay_state_topic="/zone", relay_set_topic="/zone/on",
        )],
    )
    mqtt = TraceMqtt()
    runs = FakeRuns()
    service = IrrigationService(
        zones=SimpleNamespace(
            get=lambda zone_id: zone, list=lambda: [zone],
            get_by_state_topic=lambda topic: None,
        ),
        runs=runs,
        events=SimpleNamespace(add=lambda *args: None),
        rain_sensor=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=True, topic="/rain", active_value="1",
        )),
        pump=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=True, relay_state_topic="/pump", relay_set_topic="/pump/on",
            start_delay_sec=0,
        )),
        flow_meter=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, topic=None,
        )),
        mqtt=mqtt,
        config=SafetyConfig(relay_confirm_timeout_sec=0.1),
        state=ServiceState(),
    )

    await service.start_zone(1, 60)
    mqtt.values["/rain"] = SimpleNamespace(value="1")
    await service._on_message("/rain", "1")

    assert runs.items[0].status == expected_status
    expected_commands = [
        ("/pump/on", "1"),
        ("/zone/on", "1"),
    ]
    if not ignore_rain:
        assert runs.items[0].stop_reason == "rain"
        expected_commands.extend([
            ("/pump/on", "0"),
            ("/zone/on", "0"),
        ])
    assert mqtt.published == expected_commands


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flow", "target_liters", "expected_reason"),
    [("120", 0.5, "volume_reached"), ("0", None, "dry_run")],
)
async def test_flow_meter_stops_watering(
    flow, target_liters, expected_reason,
) -> None:
    zone = SimpleNamespace(
        id=1, name="Газон", enabled=True, ignore_rain_sensor=False,
        max_duration_sec=300, cooldown_sec=0,
        relays=[SimpleNamespace(
            relay_state_topic="/zone", relay_set_topic="/zone/on",
        )],
    )
    mqtt = TraceMqtt()
    mqtt.values["/flow"] = SimpleNamespace(
        value=flow, updated_at=datetime.now(timezone.utc),
    )
    runs = FakeRuns()
    meter = SimpleNamespace(
        enabled=True, topic="/flow", min_flow_l_min=0.1,
        startup_grace_sec=0, stale_timeout_sec=10,
    )
    service = IrrigationService(
        zones=SimpleNamespace(
            get=lambda zone_id: zone, list=lambda: [zone],
            get_by_state_topic=lambda topic: None,
        ),
        runs=runs,
        events=SimpleNamespace(add=lambda *args: None),
        rain_sensor=SimpleNamespace(get=lambda: SimpleNamespace(enabled=False)),
        pump=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=True, relay_state_topic="/pump", relay_set_topic="/pump/on",
            start_delay_sec=0,
        )),
        flow_meter=SimpleNamespace(get=lambda: meter),
        mqtt=mqtt,
        config=SafetyConfig(relay_confirm_timeout_sec=0.1),
        state=ServiceState(),
    )

    await service.start_zone(1, 60, target_liters=target_liters)
    mqtt.values["/flow"] = SimpleNamespace(
        value=flow, updated_at=datetime.now(timezone.utc),
    )
    for _ in range(20):
        if runs.items[0].status != "running":
            break
        await asyncio.sleep(0.1)

    assert runs.items[0].stop_reason == expected_reason
    assert mqtt.published[-2:] == [
        ("/pump/on", "0"),
        ("/zone/on", "0"),
    ]
    if target_liters is not None:
        assert runs.items[0].delivered_liters >= target_liters
