import httpx
import pytest

from irrigationd.config import Config, StorageConfig
from irrigationd.web.app import create_app


@pytest.mark.asyncio
async def test_entity_operations_use_modals(tmp_path) -> None:
    app = create_app(
        Config(storage=StorageConfig(path=str(tmp_path / "irrigation.db")))
    )
    relay = app.state.container.relays.create({
        "name": "Клапан",
        "relay_device_id": "wb-test",
        "relay_control_id": "K1",
        "relay_state_topic": "/devices/wb-test/controls/K1",
        "relay_set_topic": "/devices/wb-test/controls/K1/on",
    })
    app.state.container.zones.create({
        "name": "Газон",
        "enabled": True,
        "relay_ids": [relay.id],
        "ignore_rain_sensor": False,
        "max_duration_sec": 900,
        "cooldown_sec": 0,
    })
    app.state.container.schedules.create({
        "zone_id": 1,
        "enabled": True,
        "days_of_week": "0,2",
        "start_time": "06:30",
        "duration_sec": 300,
    })
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        zones = await client.get("/zones")
        assert zones.status_code == 200
        for dialog_id in (
            "zone-create-dialog", "zone-start-dialog-1", "zone-stop-dialog-1",
            "zone-edit-dialog-1", "zone-delete-dialog-1",
        ):
            assert f'id="{dialog_id}"' in zones.text
        assert 'class="relay-choice"' in zones.text
        assert 'class="zone-grid"' in zones.text
        assert 'class="zone-card ' in zones.text
        assert 'class="zone-card-actions"' in zones.text
        assert "Готова" in zones.text
        assert "/zones/1/edit" not in zones.text
        assert 'hx-swap="delete"' in zones.text
        assert 'hx-on::before-swap=' in zones.text

        schedules = await client.get("/schedules")
        assert schedules.status_code == 200
        for dialog_id in (
            "schedule-create-dialog", "schedule-edit-dialog-1",
            "schedule-delete-dialog-1",
        ):
            assert f'id="{dialog_id}"' in schedules.text

        settings = await client.get("/settings")
        assert settings.status_code == 200
        assert 'class="settings-grid"' in settings.text
        assert 'class="relay-settings-section"' in settings.text
        assert 'class="settings-relay-grid"' in settings.text
        assert settings.text.count("settings-widget") >= 4
        assert "settings-relay-widget" in settings.text
        assert 'id="rain-settings-dialog"' in settings.text
        assert 'id="relay-create-dialog"' in settings.text
        assert 'id="relay-edit-dialog-1"' in settings.text
        assert 'id="pump-settings-dialog"' in settings.text
        assert 'class="stack relay-form pump-form"' in settings.text
        assert "Задержка перед открытием реле" in settings.text
        assert 'id="flow-meter-settings-dialog"' in settings.text
        assert 'class="stack flow-meter-form"' in settings.text
        assert "Минимальный расход" in settings.text
        assert "Выбор из устройств Wiren Board" in settings.text
        assert 'class="relay-manual" hidden' in settings.text
        assert 'class="stack rain-form"' in settings.text
        assert 'class="rain-basic"' in settings.text
        assert 'class="rain-manual" hidden' in settings.text
        assert "/api/topics/input-controls" in settings.text
        assert "/static/rain-form.js" in settings.text

        overview = await client.get("/overview")
        assert overview.status_code == 200
        assert 'class="overview-status-grid"' in overview.text
        assert "overview-next" in overview.text
        assert "overview-rain" in overview.text
        assert "overview-pump" in overview.text
        assert "overview-flow" in overview.text
        assert "overview-zones" in overview.text
        assert 'class="dashboard-widget dashboard-wide overview-chart"' in overview.text
        assert "Датчик дождя не настроен." in overview.text
        assert "Расходомер не настроен." in overview.text
        assert 'class="overview-zone-list"' in overview.text

        deleted = await client.delete("/ui/zones/1")
        assert deleted.status_code == 200
        assert app.state.container.zones.get(1) is None
        assert app.state.container.schedules.list() == []
        assert app.state.container.relays.get(relay.id).zone_id is None
