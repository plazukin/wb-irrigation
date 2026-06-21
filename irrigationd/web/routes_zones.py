from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from irrigationd.domain.duration import minutes_to_seconds, seconds_to_minutes
from irrigationd.domain.safety import SafetyError
from irrigationd.domain.zone import ZoneInput
from irrigationd.domain.zone_validation import (
    ZoneValidationError, normalize_zone, validate_zone_relays,
)

from .schemas import StartRequest, ZonePatch, ZoneRequest
from .serializers import run_json, zone_json

router = APIRouter(prefix="/api/zones", tags=["zones"])


async def _validated_values(request: Request, payload: ZoneRequest) -> dict[str, object]:
    container = request.app.state.container
    try:
        data = payload.model_dump(exclude={"max_duration_min", "cooldown_min"})
        max_minutes = payload.max_duration_min
        if "max_duration_min" not in payload.model_fields_set:
            max_minutes = container.config.safety.default_max_duration_min
        data["max_duration_sec"] = minutes_to_seconds(max_minutes)
        data["cooldown_sec"] = minutes_to_seconds(
            payload.cooldown_min, allow_zero=True
        )
        values = normalize_zone(ZoneInput(**data))
        relay_ids = values["relay_ids"]
        relays = container.relays.get_many(relay_ids)
        if len(relays) != len(relay_ids):
            raise ZoneValidationError("Одно из реле не найдено")
        if any(relay.zone_id is not None for relay in relays):
            raise ZoneValidationError("Одно из реле уже используется другой зоной")
        status, message = await validate_zone_relays(relays, container.probe)
    except (ZoneValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    values.update(
        last_validation_status=status,
        last_validation_message=message,
        last_validated_at=datetime.now(timezone.utc),
    )
    return values


@router.get("")
def list_zones(request: Request) -> list[dict]:
    return [zone_json(zone) for zone in request.app.state.container.zones.list()]


@router.post("", status_code=201)
async def create_zone(payload: ZoneRequest, request: Request) -> dict:
    container = request.app.state.container
    values = await _validated_values(request, payload)
    zone = container.zones.create(values)
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(), container.pump.get(),
        container.flow_meter.get(),
    )
    container.events.add("info", "zone_created", f"Зона «{zone.name}» создана", zone.id)
    return zone_json(zone)


@router.get("/{zone_id}")
def get_zone(zone_id: int, request: Request) -> dict:
    zone = request.app.state.container.zones.get(zone_id)
    if zone is None:
        raise HTTPException(404, "Зона не найдена")
    return zone_json(zone)


@router.patch("/{zone_id}")
async def update_zone(zone_id: int, payload: ZonePatch, request: Request) -> dict:
    container = request.app.state.container
    existing = container.zones.get(zone_id)
    if existing is None:
        raise HTTPException(404, "Зона не найдена")
    request_data = {
        "name": existing.name,
        "enabled": existing.enabled,
        "relay_ids": [relay.id for relay in existing.relays],
        "ignore_rain_sensor": existing.ignore_rain_sensor,
        "max_duration_min": seconds_to_minutes(existing.max_duration_sec),
        "cooldown_min": seconds_to_minutes(existing.cooldown_sec),
        "area_m2": existing.area_m2,
    }
    request_data.update(payload.model_dump(exclude_unset=True))
    try:
        validated = ZoneRequest(**request_data)
        data = validated.model_dump(exclude={"max_duration_min", "cooldown_min"})
        data["max_duration_sec"] = minutes_to_seconds(validated.max_duration_min)
        data["cooldown_sec"] = minutes_to_seconds(
            validated.cooldown_min, allow_zero=True
        )
        values = normalize_zone(ZoneInput(**data))
        relay_ids = values["relay_ids"]
        relays = container.relays.get_many(relay_ids)
        if len(relays) != len(relay_ids):
            raise ZoneValidationError("Одно из реле не найдено")
        if any(
            relay.zone_id is not None and relay.zone_id != zone_id
            for relay in relays
        ):
            raise ZoneValidationError("Одно из реле уже используется другой зоной")
        status, message = await validate_zone_relays(relays, container.probe)
    except (ZoneValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    values.update(last_validation_status=status, last_validation_message=message,
                  last_validated_at=datetime.now(timezone.utc))
    updated = container.zones.update(zone_id, values)
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(), container.pump.get(),
        container.flow_meter.get(),
    )
    return zone_json(updated)


@router.delete("/{zone_id}", status_code=204, response_class=Response)
async def delete_zone(zone_id: int, request: Request) -> Response:
    container = request.app.state.container
    if container.runs.active(zone_id):
        raise HTTPException(409, "Остановите зону перед удалением")
    if not container.zones.delete(zone_id):
        raise HTTPException(404, "Зона не найдена")
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(), container.pump.get(),
        container.flow_meter.get(),
    )
    return Response(status_code=204)


@router.post("/{zone_id}/validate")
async def validate_zone(zone_id: int, request: Request) -> dict:
    container = request.app.state.container
    zone = container.zones.get(zone_id)
    if zone is None:
        raise HTTPException(404, "Зона не найдена")
    results = []
    for relay in zone.relays:
        results.append(await container.probe.validate_relay(
            relay.relay_state_topic, relay.relay_set_topic
        ))
    ok = all(result.ok for result in results)
    failed = next((result for result in results if not result.ok), None)
    message = failed.message if failed else f"Проверено реле: {len(results)}"
    container.zones.update(zone_id, {
        "last_validation_status": "ok" if ok else "error",
        "last_validation_message": message,
        "last_validated_at": datetime.now(timezone.utc),
    })
    return {
        "ok": ok, "message": message,
        "relays": [result.dict() for result in results],
    }


@router.post("/{zone_id}/start")
async def start_zone(zone_id: int, payload: StartRequest, request: Request) -> dict:
    container = request.app.state.container
    try:
        zone = container.zones.get(zone_id)
        if zone is None:
            raise SafetyError("Зона не найдена")
        target_liters = None
        if payload.watering_mode == "volume":
            meter = container.flow_meter.get()
            if not (meter.enabled and meter.topic):
                raise SafetyError("Полив по объёму требует настроенный расходомер")
            assert payload.liters_per_m2 is not None
            duration_sec = zone.max_duration_sec
            target_liters = zone.area_m2 * payload.liters_per_m2
        else:
            assert payload.duration_min is not None
            duration_sec = minutes_to_seconds(payload.duration_min)
        run = await container.service.start_zone(
            zone_id, duration_sec, "manual", target_liters,
        )
    except SafetyError as exc:
        raise HTTPException(409, str(exc)) from exc
    return run_json(run)


@router.post("/{zone_id}/stop")
async def stop_zone(zone_id: int, request: Request) -> dict:
    try:
        run = await request.app.state.container.service.stop_zone(zone_id, "manual")
    except SafetyError as exc:
        raise HTTPException(409, str(exc)) from exc
    return run_json(run)
