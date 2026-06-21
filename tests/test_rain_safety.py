from types import SimpleNamespace

import pytest

from irrigationd.config import SafetyConfig
from irrigationd.domain.irrigation_service import IrrigationService
from irrigationd.domain.safety import SafetyError
from irrigationd.domain.state import ServiceState
class FakeMqtt:
    def __init__(self) -> None:
        self.values = {
            "/relay": SimpleNamespace(value="0"),
            "/rain": SimpleNamespace(value="1"),
        }

    def add_handler(self, handler) -> None:
        self.handler = handler

    def cached(self, topic: str):
        return self.values.get(topic)


class FakeRuns:
    def active(self):
        return []

    def latest_finished(self, zone_id: int):
        return None


class FakeEvents:
    def __init__(self) -> None:
        self.items = []

    def add(self, level, event_type, message, zone_id=None):
        self.items.append((level, event_type, message, zone_id))


@pytest.mark.asyncio
async def test_rain_blocks_zone_that_does_not_ignore_sensor() -> None:
    zone = SimpleNamespace(
        id=1, name="Lawn", enabled=True, max_duration_sec=300, cooldown_sec=0,
        relays=[SimpleNamespace(
            relay_state_topic="/relay", relay_set_topic="/relay/on",
        )],
        ignore_rain_sensor=False,
    )
    events = FakeEvents()
    service = IrrigationService(
        zones=SimpleNamespace(get=lambda zone_id: zone),
        runs=FakeRuns(),
        events=events,
        rain_sensor=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=True, topic="/rain", active_value="1"
        )),
        pump=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, relay_state_topic=None, relay_set_topic=None,
            start_delay_sec=0,
        )),
        flow_meter=SimpleNamespace(get=lambda: SimpleNamespace(
            enabled=False, topic=None,
        )),
        mqtt=FakeMqtt(),
        config=SafetyConfig(),
        state=ServiceState(),
    )

    with pytest.raises(SafetyError, match="идёт дождь"):
        await service.start_zone(1, 60, "schedule")
    assert events.items[0][1] == "watering_skipped_rain"
