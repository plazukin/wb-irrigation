from fastapi import APIRouter, HTTPException, Request, Response

from irrigationd.domain.duration import minutes_to_seconds, seconds_to_minutes
from irrigationd.domain.schedule_validation import find_schedule_overlap

from .schemas import SchedulePatch, ScheduleRequest
from .serializers import schedule_json

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("")
def list_schedules(request: Request) -> list[dict]:
    return [schedule_json(item) for item in request.app.state.container.schedules.list()]


@router.post("", status_code=201)
def create_schedule(payload: ScheduleRequest, request: Request) -> dict:
    container = request.app.state.container
    zone = container.zones.get(payload.zone_id)
    if zone is None:
        raise HTTPException(404, "Зона не найдена")
    if payload.watering_mode == "volume":
        meter = container.flow_meter.get()
        if not (meter.enabled and meter.topic):
            raise HTTPException(422, "Полив по объёму требует настроенный расходомер")
        duration_sec = zone.max_duration_sec
    else:
        assert payload.duration_min is not None
        duration_sec = minutes_to_seconds(payload.duration_min)
    if duration_sec > zone.max_duration_sec:
        raise HTTPException(422, "Превышена максимальная длительность для зоны")
    with container.schedules.write_lock:
        overlap = find_schedule_overlap(
            payload.days_of_week, payload.start_time, duration_sec,
            payload.enabled, container.schedules.list(),
        )
        if overlap:
            raise HTTPException(409, f"Расписание пересекается с расписанием #{overlap.id}")
        values = payload.model_dump(exclude={"duration_min"})
        values["duration_sec"] = duration_sec
        return schedule_json(container.schedules.create(values))


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: int, payload: SchedulePatch, request: Request) -> dict:
    container = request.app.state.container
    with container.schedules.write_lock:
        item = container.schedules.get(schedule_id)
        if item is None:
            raise HTTPException(404, "Расписание не найдено")
        values = payload.model_dump(exclude_unset=True)
        merged = {
            "zone_id": item.zone_id, "enabled": item.enabled,
            "days_of_week": item.days_of_week, "start_time": item.start_time,
            "duration_min": seconds_to_minutes(item.duration_sec),
            "watering_mode": item.watering_mode,
            "liters_per_m2": item.liters_per_m2,
        }
        merged.update(values)
        validated = ScheduleRequest(**merged)
        zone = container.zones.get(validated.zone_id)
        if zone is None:
            raise HTTPException(404, "Зона не найдена")
        if validated.watering_mode == "volume":
            meter = container.flow_meter.get()
            if not (meter.enabled and meter.topic):
                raise HTTPException(
                    422, "Полив по объёму требует настроенный расходомер"
                )
            duration_sec = zone.max_duration_sec
        else:
            assert validated.duration_min is not None
            duration_sec = minutes_to_seconds(validated.duration_min)
        if duration_sec > zone.max_duration_sec:
            raise HTTPException(422, "Превышена максимальная длительность для зоны")
        overlap = find_schedule_overlap(
            validated.days_of_week, validated.start_time, duration_sec,
            validated.enabled, container.schedules.list(), schedule_id,
        )
        if overlap:
            raise HTTPException(409, f"Расписание пересекается с расписанием #{overlap.id}")
        update_values = validated.model_dump(exclude={"duration_min"})
        update_values["duration_sec"] = duration_sec
        updated = container.schedules.update(schedule_id, update_values)
        return schedule_json(updated)


@router.delete("/{schedule_id}", status_code=204, response_class=Response)
def delete_schedule(schedule_id: int, request: Request) -> Response:
    if not request.app.state.container.schedules.delete(schedule_id):
        raise HTTPException(404, "Расписание не найдено")
    return Response(status_code=204)
