import asyncio
from types import SimpleNamespace

import pytest

from irrigationd.config import SafetyConfig
from irrigationd.domain.irrigation_service import IrrigationService
from irrigationd.domain.state import ServiceState


class FakeMqtt:
    def __init__(self) -> None:
        self.values = {
            "/relay/1": SimpleNamespace(value="0"),
            "/relay/2": SimpleNamespace(value="0"),
        }
        self.events = {topic: asyncio.Event() for topic in self.values}
        self.published = []

    def add_handler(self, handler) -> None:
        self.handler = handler

    def cached(self, topic: str):
        return self.values.get(topic)

    async def wait_for(
        self, topic, predicate, timeout, accept_cached=True,
    ) -> str:
        if not accept_cached:
            await asyncio.wait_for(self.events[topic].wait(), timeout)
        value = self.values[topic].value
        if not predicate(value):
            raise asyncio.TimeoutError
        return value

    async def publish(self, topic: str, value: str) -> None:
        self.published.append((topic, value))
        state_topic = topic.removesuffix("/on")
        self.values[state_topic] = SimpleNamespace(value=value)
        self.events[state_topic].set()


class FakeRuns:
    def __init__(self) -> None:
        self.created = None

    def active(self, zone_id=None):
        return []

    def latest_finished(self, zone_id):
        return None

    def create(self, zone_id, duration, source, target_liters=None):
        self.created = SimpleNamespace(
            id=1, zone_id=zone_id, planned_duration_sec=duration,
            source=source,
        )
        return self.created


@pytest.mark.asyncio
async def test_zone_starts_all_relays() -> None:
    zone = SimpleNamespace(
        id=1, name="Газон", enabled=True, ignore_rain_sensor=False,
        max_duration_sec=300, cooldown_sec=0,
        relays=[
            SimpleNamespace(relay_state_topic="/relay/1", relay_set_topic="/relay/1/on"),
            SimpleNamespace(relay_state_topic="/relay/2", relay_set_topic="/relay/2/on"),
        ],
    )
    mqtt = FakeMqtt()
    runs = FakeRuns()
    service = IrrigationService(
        zones=SimpleNamespace(get=lambda zone_id: zone),
        runs=runs,
        events=SimpleNamespace(add=lambda *args: None),
        rain_sensor=SimpleNamespace(get=lambda: SimpleNamespace(enabled=False)),
        pump=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, relay_state_topic=None, relay_set_topic=None,
            start_delay_sec=0,
        )),
        flow_meter=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, topic=None,
        )),
        mqtt=mqtt,
        config=SafetyConfig(),
        state=ServiceState(),
    )

    await service.start_zone(1, 60)

    assert mqtt.published == [
        ("/relay/1/on", "1"),
        ("/relay/2/on", "1"),
    ]
    assert runs.created.planned_duration_sec == 60
