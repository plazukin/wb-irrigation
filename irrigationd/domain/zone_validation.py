from __future__ import annotations

from dataclasses import asdict

from irrigationd.mqtt.probe import MqttProbe
from irrigationd.storage.models import RelayModel

from .zone import ZoneInput


class ZoneValidationError(ValueError):
    pass


def normalize_zone(data: ZoneInput) -> dict[str, object]:
    name = data.name.strip()
    if not name:
        raise ZoneValidationError("Укажите название зоны")
    if data.max_duration_sec <= 0:
        raise ZoneValidationError("Максимальная длительность должна быть больше нуля")
    if data.cooldown_sec < 0:
        raise ZoneValidationError("Пауза между запусками не может быть отрицательной")
    if data.area_m2 <= 0:
        raise ZoneValidationError("Площадь зоны должна быть больше нуля")
    if not data.relay_ids:
        raise ZoneValidationError("Добавьте хотя бы одно реле")
    if len(set(data.relay_ids)) != len(data.relay_ids):
        raise ZoneValidationError("Одно реле указано несколько раз")
    values = asdict(data)
    values.update(name=name)
    return values


async def validate_zone_relays(
    relays: list[RelayModel], probe: MqttProbe,
) -> tuple[str, str]:
    for relay in relays:
        result = await probe.validate_relay(
            relay.relay_state_topic, relay.relay_set_topic
        )
        if not result.ok:
            raise ZoneValidationError(result.message)
    return "ok", f"Проверено реле: {len(relays)}"
