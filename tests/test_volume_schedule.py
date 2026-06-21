import httpx
import pytest

from irrigationd.config import Config, StorageConfig
from irrigationd.web.app import create_app


@pytest.mark.asyncio
async def test_volume_schedule_uses_zone_area_and_maximum_duration(tmp_path) -> None:
    app = create_app(
        Config(storage=StorageConfig(path=str(tmp_path / "irrigation.db")))
    )
    relay = app.state.container.relays.create({
        "name": "Клапан",
        "relay_state_topic": "/relay",
        "relay_set_topic": "/relay/on",
    })
    app.state.container.zones.create({
        "name": "Газон", "enabled": True, "relay_ids": [relay.id],
        "ignore_rain_sensor": False, "max_duration_sec": 1800,
        "cooldown_sec": 0, "area_m2": 25,
    })
    app.state.container.flow_meter.update({
        "enabled": True, "topic": "/flow",
        "min_flow_l_min": 0.1, "startup_grace_sec": 5,
        "stale_timeout_sec": 10,
    })
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/schedules", json={
            "zone_id": 1, "days_of_week": "0", "start_time": "06:00",
            "watering_mode": "volume", "liters_per_m2": 4,
        })

    assert response.status_code == 201
    assert response.json()["watering_mode"] == "volume"
    assert response.json()["liters_per_m2"] == 4
    assert app.state.container.schedules.get(1).duration_sec == 1800
