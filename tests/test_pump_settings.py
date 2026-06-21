import httpx
import pytest

from irrigationd.config import Config, StorageConfig
from irrigationd.mqtt.probe import RelayValidationResult
from irrigationd.web.app import create_app


@pytest.mark.asyncio
async def test_pump_settings_are_validated_and_subscribed(tmp_path) -> None:
    app = create_app(
        Config(storage=StorageConfig(path=str(tmp_path / "irrigation.db")))
    )

    async def validate(state_topic, set_topic):
        return RelayValidationResult(
            True, "Реле доступно", state_topic, set_topic, "0"
        )

    app.state.container.probe.validate_relay = validate
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put("/api/settings/pump", json={
            "enabled": True,
            "relay_device_id": "wb-pump",
            "relay_control_id": "K1",
            "start_delay_sec": 1.5,
        })

    assert response.status_code == 200
    assert response.json()["relay_state_topic"] == "/devices/wb-pump/controls/K1"
    assert response.json()["start_delay_sec"] == 1.5
    assert "/devices/wb-pump/controls/K1" in app.state.container.runtime.topics


@pytest.mark.asyncio
async def test_flow_meter_settings_are_subscribed(tmp_path) -> None:
    app = create_app(
        Config(storage=StorageConfig(path=str(tmp_path / "irrigation.db")))
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put("/api/settings/flow-meter", json={
            "enabled": True,
            "device_id": "wb-flow",
            "control_id": "Flow",
            "min_flow_l_min": 0.2,
            "startup_grace_sec": 5,
            "stale_timeout_sec": 10,
        })

    assert response.status_code == 200
    assert response.json()["topic"] == "/devices/wb-flow/controls/Flow"
    assert "/devices/wb-flow/controls/Flow" in app.state.container.runtime.topics
