from __future__ import annotations

import re
from typing import Optional

_SEGMENT = re.compile(r"^[^/+#\x00]+$")


def _check_segment(value: str, label: str) -> str:
    value = value.strip()
    if not value or not _SEGMENT.fullmatch(value):
        raise ValueError(f"Некорректное значение: {label}")
    return value


def build_state_topic(device_id: str, control_id: str) -> str:
    device = _check_segment(device_id, "идентификатор устройства")
    control = _check_segment(control_id, "идентификатор канала")
    return f"/devices/{device}/controls/{control}"


def build_set_topic(device_id: str, control_id: str) -> str:
    return f"{build_state_topic(device_id, control_id)}/on"


def validate_concrete_topic(topic: str) -> str:
    topic = topic.strip()
    if not topic.startswith("/") or "+" in topic or "#" in topic or "\x00" in topic:
        raise ValueError("MQTT-топик должен начинаться с / и не содержать + или #")
    if topic.endswith("/") or "//" in topic:
        raise ValueError("Некорректный MQTT-топик")
    return topic


def relay_topics(
    device_id: Optional[str], control_id: Optional[str],
    state_topic: Optional[str], set_topic: Optional[str],
) -> tuple[str, str]:
    if state_topic or set_topic:
        if not state_topic or not set_topic:
            raise ValueError("Укажите оба топика реле")
        return validate_concrete_topic(state_topic), validate_concrete_topic(set_topic)
    if not device_id or not control_id:
        raise ValueError("Укажите устройство и канал реле")
    if not device_id.startswith("wb-"):
        raise ValueError("Идентификатор устройства реле должен начинаться с wb-")
    return build_state_topic(device_id, control_id), build_set_topic(device_id, control_id)


def input_topic(
    device_id: Optional[str], control_id: Optional[str], topic: Optional[str]
) -> Optional[str]:
    if topic:
        return validate_concrete_topic(topic)
    if device_id or control_id:
        if not device_id or not control_id:
            raise ValueError("Укажите устройство и канал")
        return build_state_topic(device_id, control_id)
    return None
