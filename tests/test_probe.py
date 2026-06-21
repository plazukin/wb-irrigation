import asyncio
import json

import pytest

from irrigationd.mqtt.probe import MqttProbe


class FakeMqtt:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.subscriptions: set[str] = set()
        self.published: list[tuple[str, str]] = []

    async def subscribe(self, topic: str) -> None:
        self.subscriptions.add(topic)

    async def unsubscribe(self, topic: str) -> None:
        self.subscriptions.discard(topic)

    async def wait_for(self, topic, predicate=lambda _: True, timeout=5, accept_cached=True):
        if topic not in self.values or not predicate(self.values[topic]):
            raise asyncio.TimeoutError
        return self.values[topic]

    async def publish(self, topic: str, value: str, retain: bool = False) -> None:
        self.published.append((topic, value))


@pytest.mark.asyncio
async def test_relay_validation() -> None:
    topic = "/devices/relay/controls/K1"
    fake = FakeMqtt({topic: "0", topic + "/meta": json.dumps({"type": "switch", "readonly": False})})
    result = await MqttProbe(fake).validate_relay(topic, topic + "/on")
    assert result.ok and result.current_value == "0" and result.type == "switch"


@pytest.mark.asyncio
async def test_relay_validation_rejects_readonly() -> None:
    topic = "/devices/relay/controls/K1"
    fake = FakeMqtt({topic: "0", topic + "/meta": json.dumps({"type": "switch", "readonly": True})})
    assert not (await MqttProbe(fake).validate_relay(topic, topic + "/on")).ok


@pytest.mark.asyncio
async def test_relay_timeout_returns_validation_error() -> None:
    topic = "/devices/missing/controls/K1"
    result = await MqttProbe(FakeMqtt({}), timeout=0.01).validate_relay(
        topic, topic + "/on"
    )
    assert not result.ok
    assert result.message == "Нет данных о состоянии реле"


@pytest.mark.asyncio
async def test_rain_sensor_validation() -> None:
    topic = "/devices/weather/controls/rain"
    result = await MqttProbe(FakeMqtt({topic: "1"})).validate_rain_sensor(topic)
    assert result.ok and result.current_value == "1"


@pytest.mark.asyncio
async def test_rain_sensor_rejects_non_binary_value() -> None:
    topic = "/devices/weather/controls/rain"
    result = await MqttProbe(FakeMqtt({topic: "37.5"})).validate_rain_sensor(topic)
    assert not result.ok
