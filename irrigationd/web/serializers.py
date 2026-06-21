from __future__ import annotations

from typing import Any

from irrigationd.domain.duration import seconds_to_minutes
from irrigationd.domain.zone import jsonable_model


def zone_json(model: Any) -> dict[str, Any]:
    data = jsonable_model(model)
    data["relay_ids"] = [relay.id for relay in model.relays]
    data["relays"] = [jsonable_model(relay) for relay in model.relays]
    data["max_duration_min"] = seconds_to_minutes(data.pop("max_duration_sec"))
    data["cooldown_min"] = seconds_to_minutes(data.pop("cooldown_sec"))
    return data


def schedule_json(model: Any) -> dict[str, Any]:
    data = jsonable_model(model)
    data["duration_min"] = seconds_to_minutes(data.pop("duration_sec"))
    return data


def run_json(model: Any) -> dict[str, Any]:
    data = jsonable_model(model)
    data["planned_duration_min"] = seconds_to_minutes(
        data.pop("planned_duration_sec")
    )
    return data
