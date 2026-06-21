from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from irrigationd.config import Config, load_config
from irrigationd.domain.irrigation_service import IrrigationService
from irrigationd.domain.scheduler import IrrigationScheduler
from irrigationd.domain.state import ServiceState
from irrigationd.domain.zone import jsonable_model
from irrigationd.mqtt.client import MqttClient
from irrigationd.mqtt.discovery import WbDeviceDiscovery
from irrigationd.mqtt.probe import MqttProbe
from irrigationd.mqtt.runtime_subscriptions import RuntimeSubscriptionManager
from irrigationd.mqtt.wb_virtual_device import WbVirtualDevice
from irrigationd.storage.db import create_db_engine, create_session_factory
from irrigationd.storage.event_repo import EventRepository, WateringRunRepository
from irrigationd.storage.init_db import init_db
from irrigationd.storage.relay_repo import RelayRepository
from irrigationd.storage.schedule_repo import ScheduleRepository
from irrigationd.storage.settings_repo import (
    FlowMeterRepository, PumpRepository, RainSensorRepository,
)
from irrigationd.storage.zone_repo import ZoneRepository

from .routes_pages import router as pages_router
from .routes_relays import router as relays_router
from .routes_schedules import router as schedules_router
from .routes_settings import router as settings_router
from .routes_topics import router as topics_router
from .routes_zones import router as zones_router


@dataclass
class Container:
    config: Config
    zones: ZoneRepository
    relays: RelayRepository
    schedules: ScheduleRepository
    events: EventRepository
    runs: WateringRunRepository
    rain_sensor: RainSensorRepository
    pump: PumpRepository
    flow_meter: FlowMeterRepository
    mqtt: MqttClient
    discovery: WbDeviceDiscovery
    probe: MqttProbe
    runtime: RuntimeSubscriptionManager
    service: IrrigationService
    scheduler: IrrigationScheduler
    virtual_device: WbVirtualDevice
    templates: Jinja2Templates


def build_container(config: Config) -> Container:
    engine = create_db_engine(config.storage.path)
    init_db(engine)
    sessions = create_session_factory(engine)
    zones = ZoneRepository(sessions)
    relays = RelayRepository(sessions)
    schedules = ScheduleRepository(sessions)
    events = EventRepository(sessions)
    runs = WateringRunRepository(sessions)
    rain_sensor = RainSensorRepository(sessions)
    pump = PumpRepository(sessions)
    flow_meter = FlowMeterRepository(sessions)
    mqtt = MqttClient(config.mqtt.host, config.mqtt.port, config.mqtt.client_id)
    discovery = WbDeviceDiscovery(mqtt)
    probe = MqttProbe(mqtt, config.safety.relay_confirm_timeout_sec)
    runtime = RuntimeSubscriptionManager(mqtt)
    state = ServiceState()
    service = IrrigationService(
        zones, runs, events, rain_sensor, pump, flow_meter,
        mqtt, config.safety, state
    )
    scheduler = IrrigationScheduler(schedules, service)
    virtual_device = WbVirtualDevice(mqtt, service.status)
    directory = Path(__file__).parent
    return Container(
        config, zones, relays, schedules, events, runs, rain_sensor, pump,
        flow_meter, mqtt, discovery, probe,
        runtime, service, scheduler, virtual_device,
        Jinja2Templates(directory=str(directory / "templates")),
    )


def create_app(config: Optional[Config] = None) -> FastAPI:
    resolved = config or load_config()
    container = build_container(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container.service.bind_event_loop()
        await container.mqtt.connect()
        try:
            await container.discovery.start()
            await container.runtime.reconcile(
                container.zones.list(), container.rain_sensor.get(),
                container.pump.get(), container.flow_meter.get(),
            )
            if resolved.safety.stop_all_on_startup:
                await container.service.stop_all("startup")
            container.scheduler.start()
            await container.virtual_device.start()
            yield
        finally:
            await container.scheduler.stop()
            if resolved.safety.stop_all_on_shutdown:
                await container.service.stop_all("shutdown")
            await container.virtual_device.stop()
            await container.discovery.stop()
            await container.mqtt.disconnect()

    app = FastAPI(
        title="Полив Wiren Board",
        version="0.1.0",
        root_path=resolved.web.root_path,
        lifespan=lifespan,
    )
    app.state.container = container
    app.include_router(topics_router)
    app.include_router(relays_router)
    app.include_router(zones_router)
    app.include_router(schedules_router)
    app.include_router(settings_router)

    @app.get("/api/events", tags=["events"])
    def api_events(request: Request, limit: int = 200) -> list[dict]:
        return [jsonable_model(item) for item in container.events.list(min(max(limit, 1), 1000))]

    app.include_router(pages_router)
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app
