from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Callable, Optional

from .client import MqttClient


class WbVirtualDevice:
    BASE = "/devices/irrigation"

    def __init__(self, client: MqttClient, status_provider: Callable[[], dict[str, str]]) -> None:
        self.client = client
        self.status_provider = status_provider
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        meta = {
            "driver": "wb-irrigationd",
            "title": {"en": "Irrigation", "ru": "Полив"},
        }
        await self.client.publish(f"{self.BASE}/meta", json.dumps(meta, ensure_ascii=False), True)
        controls_meta = {
            "service_alive": {"type": "switch", "readonly": True},
            "active_zone": {"type": "text", "readonly": True},
            "active_runs": {"type": "value", "readonly": True},
            "last_event": {"type": "text", "readonly": True},
            "alarm": {"type": "text", "readonly": True},
        }
        for name, value in controls_meta.items():
            await self.client.publish(
                f"{self.BASE}/controls/{name}/meta", json.dumps(value), True
            )
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            values = self.status_provider()
            values["service_alive"] = "1"
            for name, value in values.items():
                await self.client.publish(f"{self.BASE}/controls/{name}", str(value), True)
            await asyncio.sleep(10)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        await self.client.publish(f"{self.BASE}/controls/service_alive", "0", True)
