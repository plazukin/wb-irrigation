import httpx
import pytest

from irrigationd.config import Config, StorageConfig
from irrigationd.mqtt.probe import RelayValidationResult
from irrigationd.web.app import create_app


@pytest.mark.asyncio
async def test_relay_can_belong_to_only_one_zone(tmp_path) -> None:
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
        relay = await client.post("/api/relays", json={
            "name": "Клапан",
            "relay_device_id": "wb-test",
            "relay_control_id": "K1",
        })
        assert relay.status_code == 201

        first_zone = await client.post("/api/zones", json={
            "name": "Газон",
            "relay_ids": [1],
            "max_duration_min": 10,
        })
        assert first_zone.status_code == 201

        second_zone = await client.post("/api/zones", json={
            "name": "Теплица",
            "relay_ids": [1],
            "max_duration_min": 10,
        })
        assert second_zone.status_code == 422
        assert "другой зоной" in second_zone.text

        assigned_delete = await client.delete("/api/relays/1")
        assert assigned_delete.status_code == 409

        assert (await client.delete("/api/zones/1")).status_code == 204
        assert app.state.container.relays.get(1).zone_id is None
        assert (await client.delete("/api/relays/1")).status_code == 204
