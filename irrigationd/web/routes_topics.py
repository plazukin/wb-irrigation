from fastapi import APIRouter, HTTPException, Request

from irrigationd.mqtt.topics import input_topic, relay_topics

from .schemas import RainTopicRequest, RelayTopicRequest

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/devices")
def devices(request: Request) -> dict:
    items = request.app.state.container.discovery.devices()
    return {"devices": [item.dict() for item in items]}


@router.get("/controls")
def controls(device_id: str, request: Request) -> dict:
    if not device_id.startswith("wb-"):
        raise HTTPException(422, "Идентификатор устройства должен начинаться с wb-")
    items = request.app.state.container.discovery.controls(device_id)
    return {"controls": [item.dict() for item in items]}


@router.get("/input-controls")
def input_controls(device_id: str, request: Request) -> dict:
    if not device_id.startswith("wb-"):
        raise HTTPException(422, "Идентификатор устройства должен начинаться с wb-")
    items = request.app.state.container.discovery.input_controls(device_id)
    return {"controls": [item.dict() for item in items]}


@router.get("/value-controls")
def value_controls(device_id: str, request: Request) -> dict:
    if not device_id.startswith("wb-"):
        raise HTTPException(422, "Идентификатор устройства должен начинаться с wb-")
    items = request.app.state.container.discovery.value_controls(device_id)
    return {"controls": [item.dict() for item in items]}


def _relay(payload: RelayTopicRequest) -> tuple[str, str]:
    try:
        return relay_topics(
            payload.relay_device_id, payload.relay_control_id,
            payload.relay_state_topic, payload.relay_set_topic,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/validate-relay")
async def validate_relay(payload: RelayTopicRequest, request: Request) -> dict:
    state, setter = _relay(payload)
    return (await request.app.state.container.probe.validate_relay(state, setter)).dict()


@router.post("/validate-rain")
async def validate_rain(payload: RainTopicRequest, request: Request) -> dict:
    try:
        topic = input_topic(payload.device_id, payload.control_id, payload.topic)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not topic:
        raise HTTPException(422, "Укажите топик датчика дождя")
    return (await request.app.state.container.probe.validate_rain_sensor(topic)).dict()


@router.post("/test-relay")
async def test_relay(payload: RelayTopicRequest, request: Request) -> dict:
    state, setter = _relay(payload)
    return await request.app.state.container.probe.test_relay(state, setter)
