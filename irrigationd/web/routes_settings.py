from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from irrigationd.domain.zone import jsonable_model
from irrigationd.mqtt.topics import input_topic, relay_topics

from .schemas import FlowMeterRequest, PumpRequest, RainSensorRequest

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/rain-sensor")
def get_rain_sensor(request: Request) -> dict:
    return jsonable_model(request.app.state.container.rain_sensor.get())


@router.put("/rain-sensor")
async def update_rain_sensor(payload: RainSensorRequest, request: Request) -> dict:
    container = request.app.state.container
    try:
        topic = input_topic(payload.device_id, payload.control_id, payload.topic)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    status = None
    message = None
    validated_at = None
    if payload.enabled:
        assert topic is not None
        result = await container.probe.validate_rain_sensor(topic)
        if not result.ok:
            raise HTTPException(422, result.message)
        status = "ok"
        message = result.message
        validated_at = datetime.now(timezone.utc)

    settings = container.rain_sensor.update({
        "enabled": payload.enabled,
        "device_id": payload.device_id,
        "control_id": payload.control_id,
        "topic": topic,
        "active_value": payload.active_value,
        "last_validation_status": status,
        "last_validation_message": message,
        "last_validated_at": validated_at,
    })
    await container.runtime.reconcile(
        container.zones.list(), settings, container.pump.get(),
        container.flow_meter.get(),
    )
    container.events.add(
        "info", "rain_sensor_updated", "Настройки датчика дождя обновлены"
    )
    return jsonable_model(settings)


@router.post("/rain-sensor/validate")
async def validate_saved_rain_sensor(request: Request) -> dict:
    settings = request.app.state.container.rain_sensor.get()
    if not settings.topic:
        raise HTTPException(422, "Топик датчика дождя не настроен")
    result = await request.app.state.container.probe.validate_rain_sensor(settings.topic)
    return result.dict()


@router.get("/pump")
def get_pump(request: Request) -> dict:
    return jsonable_model(request.app.state.container.pump.get())


@router.put("/pump")
async def update_pump(payload: PumpRequest, request: Request) -> dict:
    container = request.app.state.container
    if container.runs.active():
        raise HTTPException(409, "Остановите полив перед изменением насоса")
    state_topic = None
    set_topic = None
    configured = any((
        payload.relay_device_id, payload.relay_control_id,
        payload.relay_state_topic, payload.relay_set_topic,
    ))
    if configured:
        try:
            state_topic, set_topic = relay_topics(
                payload.relay_device_id, payload.relay_control_id,
                payload.relay_state_topic, payload.relay_set_topic,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    status = None
    message = None
    validated_at = None
    if payload.enabled:
        assert state_topic is not None and set_topic is not None
        result = await container.probe.validate_relay(state_topic, set_topic)
        if not result.ok:
            raise HTTPException(422, result.message)
        status = "ok"
        message = result.message
        validated_at = datetime.now(timezone.utc)

    pump = container.pump.update({
        "enabled": payload.enabled,
        "relay_device_id": payload.relay_device_id,
        "relay_control_id": payload.relay_control_id,
        "relay_state_topic": state_topic,
        "relay_set_topic": set_topic,
        "start_delay_sec": payload.start_delay_sec,
        "last_validation_status": status,
        "last_validation_message": message,
        "last_validated_at": validated_at,
    })
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(), pump,
        container.flow_meter.get(),
    )
    container.events.add("info", "pump_updated", "Настройки насоса обновлены")
    return jsonable_model(pump)


@router.get("/flow-meter")
def get_flow_meter(request: Request) -> dict:
    return jsonable_model(request.app.state.container.flow_meter.get())


@router.put("/flow-meter")
async def update_flow_meter(payload: FlowMeterRequest, request: Request) -> dict:
    container = request.app.state.container
    if container.runs.active():
        raise HTTPException(409, "Остановите полив перед изменением расходомера")
    try:
        topic = input_topic(payload.device_id, payload.control_id, payload.topic)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    meter = container.flow_meter.update({
        "enabled": payload.enabled,
        "device_id": payload.device_id,
        "control_id": payload.control_id,
        "topic": topic,
        "min_flow_l_min": payload.min_flow_l_min,
        "startup_grace_sec": payload.startup_grace_sec,
        "stale_timeout_sec": payload.stale_timeout_sec,
    })
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(),
        container.pump.get(), meter,
    )
    container.events.add("info", "flow_meter_updated", "Настройки расходомера обновлены")
    return jsonable_model(meter)
