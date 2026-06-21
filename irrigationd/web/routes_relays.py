from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from irrigationd.domain.zone import jsonable_model
from irrigationd.mqtt.topics import relay_topics

from .schemas import RelayPatch, RelayRequest

router = APIRouter(prefix="/api/relays", tags=["relays"])


async def _relay_values(payload: RelayRequest, request: Request) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Укажите название реле")
    try:
        state_topic, set_topic = relay_topics(
            payload.relay_device_id, payload.relay_control_id,
            payload.relay_state_topic, payload.relay_set_topic,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result = await request.app.state.container.probe.validate_relay(
        state_topic, set_topic
    )
    if not result.ok:
        raise HTTPException(422, result.message)
    return {
        "name": name,
        "relay_device_id": payload.relay_device_id,
        "relay_control_id": payload.relay_control_id,
        "relay_state_topic": state_topic,
        "relay_set_topic": set_topic,
        "last_validation_status": "ok",
        "last_validation_message": result.message,
        "last_validated_at": datetime.now(timezone.utc),
    }


@router.get("")
def list_relays(request: Request) -> list[dict]:
    return [jsonable_model(item) for item in request.app.state.container.relays.list()]


@router.post("", status_code=201)
async def create_relay(payload: RelayRequest, request: Request) -> dict:
    container = request.app.state.container
    values = await _relay_values(payload, request)
    if container.relays.get_by_state_topic(values["relay_state_topic"]):
        raise HTTPException(409, "Реле с таким топиком уже существует")
    return jsonable_model(container.relays.create(values))


@router.patch("/{relay_id}")
async def update_relay(
    relay_id: int, payload: RelayPatch, request: Request,
) -> dict:
    container = request.app.state.container
    relay = container.relays.get(relay_id)
    if relay is None:
        raise HTTPException(404, "Реле не найдено")
    if relay.zone_id is not None and container.runs.active(relay.zone_id):
        raise HTTPException(409, "Остановите зону перед изменением реле")
    merged = {
        "name": relay.name,
        "relay_device_id": relay.relay_device_id,
        "relay_control_id": relay.relay_control_id,
        "relay_state_topic": relay.relay_state_topic,
        "relay_set_topic": relay.relay_set_topic,
    }
    merged.update(payload.model_dump(exclude_unset=True))
    values = await _relay_values(RelayRequest(**merged), request)
    duplicate = container.relays.get_by_state_topic(values["relay_state_topic"])
    if duplicate and duplicate.id != relay_id:
        raise HTTPException(409, "Реле с таким топиком уже существует")
    updated = container.relays.update(relay_id, values)
    await container.runtime.reconcile(
        container.zones.list(), container.rain_sensor.get(), container.pump.get(),
        container.flow_meter.get(),
    )
    return jsonable_model(updated)


@router.delete("/{relay_id}", status_code=204, response_class=Response)
def delete_relay(relay_id: int, request: Request) -> Response:
    container = request.app.state.container
    relay = container.relays.get(relay_id)
    if relay is None:
        raise HTTPException(404, "Реле не найдено")
    if relay.zone_id is not None:
        raise HTTPException(409, "Реле используется зоной")
    container.relays.delete(relay_id)
    return Response(status_code=204)
