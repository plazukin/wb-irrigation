from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from irrigationd.domain.safety import SafetyError

from .routes_schedules import create_schedule, update_schedule
from .routes_relays import create_relay, update_relay
from .routes_settings import update_flow_meter, update_pump, update_rain_sensor
from .routes_zones import create_zone, delete_zone, start_zone, update_zone
from .schedule_overview import WEEKDAYS, build_dashboard, build_weekly_map
from .schemas import (
    FlowMeterRequest, PumpRequest, RainSensorRequest, RelayPatch, RelayRequest,
    SchedulePatch, ScheduleRequest, StartRequest,
    ZonePatch, ZoneRequest,
)

router = APIRouter(tags=["web"])


def templates(request: Request):
    return request.app.state.container.templates


def _zones_context(container, **extra):
    context = {
        "zones": container.zones.list(),
        "relays": container.relays.list(),
        "active_zone_ids": {run.zone_id for run in container.runs.active()},
        "flow_meter_configured": bool(
            container.flow_meter.get().enabled and container.flow_meter.get().topic
        ),
        "create_zone": None,
        "create_error": None,
        "edit_zone": None,
        "edit_zone_id": None,
        "edit_error": None,
        "default_max_duration_min": (
            container.config.safety.default_max_duration_min
        ),
    }
    context.update(extra)
    return context


def _schedules_context(container, **extra):
    zones = container.zones.list()
    context = {
        "schedules": container.schedules.list(),
        "zones": zones,
        "zone_names": {zone.id: zone.name for zone in zones},
        "weekdays": WEEKDAYS,
        "flow_meter_configured": bool(
            container.flow_meter.get().enabled and container.flow_meter.get().topic
        ),
        "schedule_error": None,
        "schedule_data": None,
        "edit_schedule_error": None,
        "edit_schedule_data": None,
        "edit_schedule_id": None,
    }
    context.update(extra)
    return context


def _settings_context(container, **extra):
    context = {
        "rain": container.rain_sensor.get(),
        "pump": container.pump.get(),
        "has_active_zones": bool(container.runs.active()),
        "flow_meter": container.flow_meter.get(),
        "relays": container.relays.list(),
        "error": None,
        "create_relay": None,
        "create_relay_error": None,
        "edit_relay": None,
        "edit_relay_id": None,
        "edit_relay_error": None,
        "pump_error": None,
        "flow_meter_error": None,
    }
    context.update(extra)
    return context


@router.get("/", include_in_schema=False)
def index(request: Request) -> RedirectResponse:
    return RedirectResponse(str(request.url_for("zones_page")), status_code=303)


@router.get("/zones", response_class=HTMLResponse, include_in_schema=False)
def zones_page(request: Request):
    container = request.app.state.container
    return templates(request).TemplateResponse(
        request, "zones.html", _zones_context(container),
    )


@router.post("/ui/zones", include_in_schema=False)
async def create_zone_form(
    request: Request, name: str = Form(...), relay_ids: list[int] = Form(...),
    max_duration_min: float = Form(15),
    cooldown_min: float = Form(0), area_m2: float = Form(1),
    enabled: Optional[str] = Form(None),
    ignore_rain_sensor: Optional[str] = Form(None),
):
    try:
        payload = ZoneRequest(
            name=name, enabled=enabled is not None,
            relay_ids=relay_ids,
            ignore_rain_sensor=ignore_rain_sensor is not None,
            max_duration_min=max_duration_min, cooldown_min=cooldown_min,
            area_m2=area_m2,
        )
        await create_zone(payload, request)
    except (HTTPException, ValidationError) as exc:
        container = request.app.state.container
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки реле"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        form_data = {
            "name": name, "enabled": enabled is not None,
            "relay_ids": relay_ids,
            "ignore_rain_sensor": ignore_rain_sensor is not None,
            "max_duration_min": max_duration_min, "cooldown_min": cooldown_min,
            "area_m2": area_m2,
        }
        return templates(request).TemplateResponse(
            request, "zones.html",
            _zones_context(
                container, create_zone=form_data, create_error=detail
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("zones_page")), status_code=303)


@router.post("/ui/zones/{zone_id}", include_in_schema=False)
async def update_zone_form(
    zone_id: int, request: Request, name: str = Form(...),
    relay_ids: list[int] = Form(...),
    max_duration_min: float = Form(15), cooldown_min: float = Form(0),
    area_m2: float = Form(1),
    enabled: Optional[str] = Form(None), ignore_rain_sensor: Optional[str] = Form(None),
):
    try:
        payload = ZonePatch(
            name=name, enabled=enabled is not None, relay_ids=relay_ids,
            ignore_rain_sensor=ignore_rain_sensor is not None,
            max_duration_min=max_duration_min, cooldown_min=cooldown_min,
            area_m2=area_m2,
        )
        await update_zone(zone_id, payload, request)
    except (HTTPException, ValidationError) as exc:
        container = request.app.state.container
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки реле"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        form_data = {
            "name": name, "enabled": enabled is not None,
            "relay_ids": relay_ids,
            "ignore_rain_sensor": ignore_rain_sensor is not None,
            "max_duration_min": max_duration_min, "cooldown_min": cooldown_min,
            "area_m2": area_m2,
        }
        return templates(request).TemplateResponse(
            request, "zones.html",
            _zones_context(
                container, edit_zone=form_data, edit_zone_id=zone_id,
                edit_error=detail,
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("zones_page")), status_code=303)


@router.post("/ui/zones/{zone_id}/start", response_class=HTMLResponse, include_in_schema=False)
async def ui_start(
    zone_id: int, request: Request, watering_mode: str = Form("timer"),
    duration_min: Optional[float] = Form(None),
    liters_per_m2: Optional[float] = Form(None),
):
    try:
        payload = StartRequest(
            watering_mode=watering_mode,
            duration_min=duration_min,
            liters_per_m2=liters_per_m2,
        )
        await start_zone(zone_id, payload, request)
        return HTMLResponse('<span class="ok">Запущено</span>')
    except (HTTPException, SafetyError, ValidationError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return HTMLResponse(f'<span class="error">{detail}</span>', status_code=409)


@router.post("/ui/zones/{zone_id}/stop", response_class=HTMLResponse, include_in_schema=False)
async def ui_stop(zone_id: int, request: Request):
    try:
        await request.app.state.container.service.stop_zone(zone_id)
        return HTMLResponse('<span class="ok">Остановлено</span>')
    except SafetyError as exc:
        return HTMLResponse(f'<span class="error">{exc}</span>', status_code=409)


@router.delete("/ui/zones/{zone_id}", response_class=HTMLResponse, include_in_schema=False)
async def ui_delete(zone_id: int, request: Request):
    try:
        await delete_zone(zone_id, request)
    except HTTPException as exc:
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)
    return HTMLResponse("")


@router.get("/schedules", response_class=HTMLResponse, include_in_schema=False)
def schedules_page(request: Request):
    container = request.app.state.container
    return templates(request).TemplateResponse(
        request, "schedules.html", _schedules_context(container),
    )


@router.get("/overview", response_class=HTMLResponse, include_in_schema=False)
def overview_page(request: Request):
    container = request.app.state.container
    zones = container.zones.list()
    schedules = container.schedules.list()
    rain = container.rain_sensor.get()
    cached_rain = container.mqtt.cached(rain.topic) if rain.topic else None
    flow_meter = container.flow_meter.get()
    cached_flow = container.mqtt.cached(flow_meter.topic) if flow_meter.topic else None
    pump = container.pump.get()
    cached_pump = container.mqtt.cached(
        pump.relay_state_topic
    ) if pump.relay_state_topic else None
    return templates(request).TemplateResponse(
        request, "overview.html",
        {
            "dashboard": build_dashboard(
                zones, schedules, container.runs.active(), rain,
                cached_rain.value if cached_rain else None,
            ),
            "weekly_map": build_weekly_map(zones, schedules),
            "flow_meter": flow_meter,
            "flow_value": cached_flow.value if cached_flow else None,
            "pump": pump,
            "pump_value": cached_pump.value if cached_pump else None,
        },
    )


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
def settings_page(request: Request):
    container = request.app.state.container
    return templates(request).TemplateResponse(
        request, "settings.html", _settings_context(container),
    )


@router.post("/ui/settings/rain-sensor", include_in_schema=False)
async def rain_sensor_form(
    request: Request, device_id: str = Form(""), control_id: str = Form(""),
    topic: str = Form(""), active_value: str = Form("1"),
    enabled: Optional[str] = Form(None),
):
    payload = RainSensorRequest(
        enabled=enabled is not None,
        device_id=device_id or None,
        control_id=control_id or None,
        topic=topic or None,
        active_value=active_value,
    )
    try:
        await update_rain_sensor(payload, request)
    except HTTPException as exc:
        container = request.app.state.container
        return templates(request).TemplateResponse(
            request, "settings.html",
            _settings_context(container, rain=payload, error=exc.detail),
            status_code=exc.status_code,
        )
    return RedirectResponse(str(request.url_for("settings_page")), status_code=303)


@router.post("/ui/settings/pump", include_in_schema=False)
async def pump_form(
    request: Request, relay_device_id: str = Form(""),
    relay_control_id: str = Form(""), relay_state_topic: str = Form(""),
    relay_set_topic: str = Form(""), start_delay_sec: float = Form(1),
    enabled: Optional[str] = Form(None),
):
    try:
        payload = PumpRequest(
            enabled=enabled is not None,
            relay_device_id=relay_device_id or None,
            relay_control_id=relay_control_id or None,
            relay_state_topic=relay_state_topic or None,
            relay_set_topic=relay_set_topic or None,
            start_delay_sec=start_delay_sec,
        )
        await update_pump(payload, request)
    except (HTTPException, ValidationError) as exc:
        container = request.app.state.container
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки насоса"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        pump = locals().get("payload", container.pump.get())
        return templates(request).TemplateResponse(
            request, "settings.html",
            _settings_context(container, pump=pump, pump_error=detail),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("settings_page")), status_code=303)


@router.post("/ui/settings/flow-meter", include_in_schema=False)
async def flow_meter_form(
    request: Request, device_id: str = Form(""), control_id: str = Form(""),
    topic: str = Form(""), min_flow_l_min: float = Form(0.1),
    startup_grace_sec: float = Form(10), stale_timeout_sec: float = Form(15),
    enabled: Optional[str] = Form(None),
):
    try:
        payload = FlowMeterRequest(
            enabled=enabled is not None,
            device_id=device_id or None, control_id=control_id or None,
            topic=topic or None, min_flow_l_min=min_flow_l_min,
            startup_grace_sec=startup_grace_sec,
            stale_timeout_sec=stale_timeout_sec,
        )
        await update_flow_meter(payload, request)
    except (HTTPException, ValidationError) as exc:
        container = request.app.state.container
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки расходомера"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        meter = locals().get("payload", container.flow_meter.get())
        return templates(request).TemplateResponse(
            request, "settings.html",
            _settings_context(
                container, flow_meter=meter, flow_meter_error=detail,
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("settings_page")), status_code=303)


@router.post("/ui/relays", include_in_schema=False)
async def create_relay_form(
    request: Request, name: str = Form(...), relay_device_id: str = Form(""),
    relay_control_id: str = Form(""), relay_state_topic: str = Form(""),
    relay_set_topic: str = Form(""),
):
    data = {
        "name": name,
        "relay_device_id": relay_device_id or None,
        "relay_control_id": relay_control_id or None,
        "relay_state_topic": relay_state_topic or None,
        "relay_set_topic": relay_set_topic or None,
    }
    try:
        await create_relay(RelayRequest(**data), request)
    except (HTTPException, ValidationError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки реле"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        container = request.app.state.container
        return templates(request).TemplateResponse(
            request, "settings.html",
            _settings_context(
                container, create_relay=data, create_relay_error=detail,
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("settings_page")), status_code=303)


@router.post("/ui/relays/{relay_id}", include_in_schema=False)
async def update_relay_form(
    relay_id: int, request: Request, name: str = Form(...),
    relay_device_id: str = Form(""), relay_control_id: str = Form(""),
    relay_state_topic: str = Form(""), relay_set_topic: str = Form(""),
):
    data = {
        "name": name,
        "relay_device_id": relay_device_id or None,
        "relay_control_id": relay_control_id or None,
        "relay_state_topic": relay_state_topic or None,
        "relay_set_topic": relay_set_topic or None,
    }
    try:
        await update_relay(relay_id, RelayPatch(**data), request)
    except (HTTPException, ValidationError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте настройки реле"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        container = request.app.state.container
        return templates(request).TemplateResponse(
            request, "settings.html",
            _settings_context(
                container, edit_relay=data, edit_relay_id=relay_id,
                edit_relay_error=detail,
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("settings_page")), status_code=303)


@router.delete(
    "/ui/relays/{relay_id}", response_class=HTMLResponse,
    include_in_schema=False,
)
def delete_relay_form(relay_id: int, request: Request):
    relay = request.app.state.container.relays.get(relay_id)
    if relay is None:
        return HTMLResponse("Реле не найдено", status_code=404)
    if relay.zone_id is not None:
        return HTMLResponse("Реле используется зоной", status_code=409)
    request.app.state.container.relays.delete(relay_id)
    return HTMLResponse("")


@router.post("/ui/schedules", include_in_schema=False)
def schedule_form(
    request: Request, zone_id: int = Form(...), days_of_week: list[str] = Form(...),
    start_time: str = Form(...), watering_mode: str = Form("timer"),
    duration_min: Optional[float] = Form(None),
    liters_per_m2: Optional[float] = Form(None),
    enabled: Optional[str] = Form(None),
):
    container = request.app.state.container
    zone = container.zones.get(zone_id)
    form_data = {
        "zone_id": zone_id,
        "days_of_week": days_of_week,
        "start_time": start_time,
        "duration_min": duration_min,
        "watering_mode": watering_mode,
        "liters_per_m2": liters_per_m2,
        "enabled": enabled is not None,
    }
    if zone is None:
        return templates(request).TemplateResponse(
            request, "schedules.html",
            _schedules_context(
                container, schedule_error="Зона не найдена",
                schedule_data=form_data,
            ),
            status_code=422,
        )
    try:
        payload = ScheduleRequest(
            zone_id=zone_id, days_of_week=",".join(days_of_week),
            start_time=start_time, duration_min=duration_min,
            watering_mode=watering_mode, liters_per_m2=liters_per_m2,
            enabled=enabled is not None,
        )
    except ValidationError:
        return templates(request).TemplateResponse(
            request, "schedules.html",
            _schedules_context(
                container, schedule_error="Проверьте параметры расписания",
                schedule_data=form_data,
            ),
            status_code=422,
        )
    try:
        create_schedule(payload, request)
    except HTTPException as exc:
        return templates(request).TemplateResponse(
            request, "schedules.html",
            _schedules_context(
                container, schedule_error=exc.detail,
                schedule_data=form_data,
            ),
            status_code=exc.status_code,
        )
    return RedirectResponse(str(request.url_for("schedules_page")), status_code=303)


@router.post("/ui/schedules/{schedule_id}", include_in_schema=False)
def update_schedule_form(
    schedule_id: int, request: Request, zone_id: int = Form(...),
    days_of_week: list[str] = Form(...), start_time: str = Form(...),
    watering_mode: str = Form("timer"),
    duration_min: Optional[float] = Form(None),
    liters_per_m2: Optional[float] = Form(None),
    enabled: Optional[str] = Form(None),
):
    container = request.app.state.container
    data = {
        "zone_id": zone_id,
        "days_of_week": days_of_week,
        "start_time": start_time,
        "duration_min": duration_min,
        "watering_mode": watering_mode,
        "liters_per_m2": liters_per_m2,
        "enabled": enabled is not None,
    }
    try:
        payload = SchedulePatch(
            zone_id=zone_id, days_of_week=",".join(days_of_week),
            start_time=start_time, duration_min=duration_min,
            watering_mode=watering_mode, liters_per_m2=liters_per_m2,
            enabled=enabled is not None,
        )
        update_schedule(schedule_id, payload, request)
    except (HTTPException, ValidationError, ValueError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else "Проверьте параметры расписания"
        status_code = exc.status_code if isinstance(exc, HTTPException) else 422
        return templates(request).TemplateResponse(
            request, "schedules.html",
            _schedules_context(
                container, edit_schedule_error=detail,
                edit_schedule_data=data, edit_schedule_id=schedule_id,
            ),
            status_code=status_code,
        )
    return RedirectResponse(str(request.url_for("schedules_page")), status_code=303)


@router.delete(
    "/ui/schedules/{schedule_id}", response_class=HTMLResponse,
    include_in_schema=False,
)
def delete_schedule_form(schedule_id: int, request: Request):
    if not request.app.state.container.schedules.delete(schedule_id):
        return HTMLResponse("Расписание не найдено", status_code=404)
    return HTMLResponse("")


@router.get("/events", response_class=HTMLResponse, include_in_schema=False)
def events_page(request: Request):
    return templates(request).TemplateResponse(
        request, "events.html", {"events": request.app.state.container.events.list()}
    )
