from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .client import MqttClient

DEVICE_META_TOPIC = "/devices/+/meta"
CONTROL_META_TOPIC = "/devices/+/controls/+/meta"
_DEVICE_META = re.compile(r"^/devices/(wb-[^/+#\x00]+)/meta$")
_CONTROL_META = re.compile(
    r"^/devices/(wb-[^/+#\x00]+)/controls/([^/+#\x00]+)/meta$"
)


def _title(meta: dict[str, Any], fallback: str) -> str:
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    if isinstance(title, dict):
        for language in ("ru", "en"):
            value = title.get(language)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


@dataclass(frozen=True)
class DiscoveredItem:
    id: str
    title: str

    def dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title}


class WbDeviceDiscovery:
    def __init__(self, client: MqttClient) -> None:
        self.client = client
        self._devices: dict[str, str] = {}
        self._controls: dict[str, dict[str, str]] = {}
        self._input_controls: dict[str, dict[str, str]] = {}
        self._value_controls: dict[str, dict[str, str]] = {}

    async def start(self) -> None:
        self.client.add_handler(self._on_message)
        await self.client.subscribe(DEVICE_META_TOPIC)
        await self.client.subscribe(CONTROL_META_TOPIC)

    async def stop(self) -> None:
        await self.client.unsubscribe(CONTROL_META_TOPIC)
        await self.client.unsubscribe(DEVICE_META_TOPIC)
        self.client.remove_handler(self._on_message)

    def devices(self) -> list[DiscoveredItem]:
        device_ids = (
            set(self._devices) | set(self._controls) | set(self._input_controls)
            | set(self._value_controls)
        )
        return [
            DiscoveredItem(device_id, self._devices.get(device_id, device_id))
            for device_id in sorted(device_ids)
        ]

    def controls(self, device_id: str) -> list[DiscoveredItem]:
        if not _DEVICE_META.fullmatch(f"/devices/{device_id}/meta"):
            return []
        return [
            DiscoveredItem(control_id, title)
            for control_id, title in sorted(self._controls.get(device_id, {}).items())
        ]

    def input_controls(self, device_id: str) -> list[DiscoveredItem]:
        if not _DEVICE_META.fullmatch(f"/devices/{device_id}/meta"):
            return []
        return [
            DiscoveredItem(control_id, title)
            for control_id, title in sorted(
                self._input_controls.get(device_id, {}).items()
            )
        ]

    def value_controls(self, device_id: str) -> list[DiscoveredItem]:
        if not _DEVICE_META.fullmatch(f"/devices/{device_id}/meta"):
            return []
        return [
            DiscoveredItem(control_id, title)
            for control_id, title in sorted(
                self._value_controls.get(device_id, {}).items()
            )
        ]

    def _on_message(self, topic: str, value: str) -> None:
        device_match = _DEVICE_META.fullmatch(topic)
        control_match = _CONTROL_META.fullmatch(topic)
        if not device_match and not control_match:
            return
        if not value:
            if device_match:
                self._devices.pop(device_match.group(1), None)
            elif control_match:
                self._controls.get(control_match.group(1), {}).pop(
                    control_match.group(2), None
                )
                self._input_controls.get(control_match.group(1), {}).pop(
                    control_match.group(2), None
                )
                self._value_controls.get(control_match.group(1), {}).pop(
                    control_match.group(2), None
                )
            return
        try:
            meta = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(meta, dict):
            return
        if device_match:
            device_id = device_match.group(1)
            self._devices[device_id] = _title(meta, device_id)
            return
        assert control_match is not None
        device_id, control_id = control_match.groups()
        controls = self._controls.setdefault(device_id, {})
        input_controls = self._input_controls.setdefault(device_id, {})
        value_controls = self._value_controls.setdefault(device_id, {})
        if meta.get("type") == "switch":
            title = _title(meta, control_id)
            input_controls[control_id] = title
            if meta.get("readonly") is not True:
                controls[control_id] = title
            else:
                controls.pop(control_id, None)
        else:
            controls.pop(control_id, None)
            input_controls.pop(control_id, None)
        if meta.get("type") == "value":
            value_controls[control_id] = _title(meta, control_id)
        else:
            value_controls.pop(control_id, None)
