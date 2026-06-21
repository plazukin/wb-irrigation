import asyncio

import pytest

from irrigationd.config import SafetyConfig
from irrigationd.domain.irrigation_service import IrrigationService
from irrigationd.domain.state import ServiceState
from irrigationd.mqtt.client import MqttClient


class HandlerOnlyMqtt:
    def add_handler(self, handler) -> None:
        self.handler = handler


# Объекты создаются до цикла событий, как при запуске Uvicorn.
MQTT_CREATED_BEFORE_EVENT_LOOP = MqttClient("localhost", 1883, "loop-test")
SERVICE_CREATED_BEFORE_EVENT_LOOP = IrrigationService(
    zones=None,
    runs=None,
    events=None,
    rain_sensor=None,
    pump=None,
    flow_meter=None,
    mqtt=HandlerOnlyMqtt(),
    config=SafetyConfig(),
    state=ServiceState(),
)


@pytest.mark.asyncio
async def test_mqtt_event_is_created_in_running_loop(monkeypatch) -> None:
    client = MQTT_CREATED_BEFORE_EVENT_LOOP
    assert client._connected is None

    def connect_async(host: str, port: int, keepalive: int) -> None:
        assert client._loop is asyncio.get_running_loop()
        assert client._connected is not None
        client._loop.call_soon(client._connected.set)

    monkeypatch.setattr(client._client, "connect_async", connect_async)
    monkeypatch.setattr(client._client, "loop_start", lambda: None)
    monkeypatch.setattr(client._client, "disconnect", lambda: None)
    monkeypatch.setattr(client._client, "loop_stop", lambda: None)

    await client.connect(timeout=0.1)
    assert client._is_connected()
    await client.disconnect()
    assert client._connected is None


@pytest.mark.asyncio
async def test_irrigation_lock_is_bound_during_lifespan() -> None:
    service = SERVICE_CREATED_BEFORE_EVENT_LOOP
    assert service._lock is None
    service.bind_event_loop()
    assert service._lock is not None
