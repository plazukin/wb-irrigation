import json

import pytest

from irrigationd.mqtt.discovery import (
    CONTROL_META_TOPIC, DEVICE_META_TOPIC, WbDeviceDiscovery,
)


class FakeMqtt:
    def __init__(self) -> None:
        self.handlers = set()
        self.subscriptions = set()

    def add_handler(self, handler) -> None:
        self.handlers.add(handler)

    def remove_handler(self, handler) -> None:
        self.handlers.discard(handler)

    async def subscribe(self, topic: str) -> None:
        self.subscriptions.add(topic)

    async def unsubscribe(self, topic: str) -> None:
        self.subscriptions.discard(topic)

    def emit(self, topic: str, value: str) -> None:
        for handler in tuple(self.handlers):
            handler(topic, value)


@pytest.mark.asyncio
async def test_discovery_returns_wb_devices_and_writable_switches() -> None:
    mqtt = FakeMqtt()
    discovery = WbDeviceDiscovery(mqtt)
    await discovery.start()

    assert mqtt.subscriptions == {DEVICE_META_TOPIC, CONTROL_META_TOPIC}
    mqtt.emit(
        "/devices/wb-mr6c_42/meta",
        json.dumps({"title": {"ru": "Релейный модуль"}}),
    )
    mqtt.emit("/devices/weather/meta", json.dumps({"title": "Погода"}))
    mqtt.emit(
        "/devices/wb-mr6c_42/controls/K1/meta",
        json.dumps({"type": "switch", "readonly": False, "title": "Канал 1"}),
    )
    mqtt.emit(
        "/devices/wb-mr6c_42/controls/Input 1/meta",
        json.dumps({"type": "switch", "readonly": True, "title": "Вход 1"}),
    )
    mqtt.emit(
        "/devices/wb-mr6c_42/controls/Flow/meta",
        json.dumps({"type": "value", "readonly": True, "title": "Расход"}),
    )

    assert [item.dict() for item in discovery.devices()] == [
        {"id": "wb-mr6c_42", "title": "Релейный модуль"}
    ]
    assert [item.dict() for item in discovery.controls("wb-mr6c_42")] == [
        {"id": "K1", "title": "Канал 1"}
    ]
    assert [item.dict() for item in discovery.input_controls("wb-mr6c_42")] == [
        {"id": "Input 1", "title": "Вход 1"},
        {"id": "K1", "title": "Канал 1"},
    ]
    assert [item.dict() for item in discovery.value_controls("wb-mr6c_42")] == [
        {"id": "Flow", "title": "Расход"}
    ]
    assert discovery.controls("weather") == []

    await discovery.stop()
    assert not mqtt.handlers
    assert not mqtt.subscriptions
