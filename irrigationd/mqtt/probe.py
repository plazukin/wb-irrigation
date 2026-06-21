from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .client import MqttClient
from .topics import validate_concrete_topic


@dataclass(frozen=True)
class RelayValidationResult:
    ok: bool
    message: str
    state_topic: Optional[str] = None
    set_topic: Optional[str] = None
    current_value: Optional[str] = None
    type: Optional[str] = None
    readonly: Optional[bool] = None

    def dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class RainValidationResult:
    ok: bool
    message: str
    topic: Optional[str] = None
    current_value: Optional[str] = None

    def dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


class MqttProbe:
    def __init__(self, client: MqttClient, timeout: float = 5) -> None:
        self.client = client
        self.timeout = timeout

    async def validate_relay(self, state_topic: str, set_topic: str) -> RelayValidationResult:
        try:
            state_topic = validate_concrete_topic(state_topic)
            set_topic = validate_concrete_topic(set_topic)
        except ValueError as exc:
            return RelayValidationResult(False, str(exc))
        meta_topic = f"{state_topic}/meta"
        await self.client.subscribe(state_topic)
        await self.client.subscribe(meta_topic)
        try:
            try:
                value = await self.client.wait_for(state_topic, timeout=self.timeout)
            except asyncio.TimeoutError:
                return RelayValidationResult(False, "Нет данных о состоянии реле")
            if value not in {"0", "1"}:
                return RelayValidationResult(False, "Состояние реле должно быть 0 или 1")
            relay_type: Optional[str] = None
            readonly: Optional[bool] = None
            try:
                raw_meta = await self.client.wait_for(meta_topic, timeout=min(1, self.timeout))
                meta = json.loads(raw_meta)
                relay_type = meta.get("type")
                readonly = meta.get("readonly")
                if readonly is True:
                    return RelayValidationResult(
                        False, "Канал реле доступен только для чтения", state_topic, set_topic,
                        value, relay_type, readonly,
                    )
                if relay_type is not None and relay_type != "switch":
                    return RelayValidationResult(
                        False, "Тип канала реле должен быть switch", state_topic, set_topic,
                        value, relay_type, readonly,
                    )
            except (asyncio.TimeoutError, json.JSONDecodeError, TypeError):
                pass
            return RelayValidationResult(
                True, "Реле доступно", state_topic, set_topic, value,
                relay_type, readonly,
            )
        finally:
            await self.client.unsubscribe(meta_topic)
            await self.client.unsubscribe(state_topic)

    async def validate_rain_sensor(self, topic: str) -> RainValidationResult:
        try:
            topic = validate_concrete_topic(topic)
        except ValueError as exc:
            return RainValidationResult(False, str(exc))
        await self.client.subscribe(topic)
        try:
            try:
                raw = await self.client.wait_for(topic, timeout=self.timeout)
            except asyncio.TimeoutError:
                return RainValidationResult(False, "Нет данных от датчика дождя", topic)
            if raw not in {"0", "1"}:
                return RainValidationResult(
                    False, "Значение датчика дождя должно быть 0 или 1", topic, raw
                )
            return RainValidationResult(True, "Датчик дождя доступен", topic, raw)
        finally:
            await self.client.unsubscribe(topic)

    async def test_relay(self, state_topic: str, set_topic: str) -> dict[str, Any]:
        await self.client.subscribe(state_topic)
        try:
            validation = await self.validate_relay(state_topic, set_topic)
            if not validation.ok:
                return validation.dict()
            if validation.current_value == "1":
                return {"ok": False, "message": "Реле уже включено"}
            on_confirmation = asyncio.create_task(self.client.wait_for(
                state_topic, lambda value: value == "1", self.timeout, accept_cached=False
            ))
            await asyncio.sleep(0)
            await self.client.publish(set_topic, "1")
            await on_confirmation
            await asyncio.sleep(1)
            off_confirmation = asyncio.create_task(self.client.wait_for(
                state_topic, lambda value: value == "0", self.timeout, accept_cached=False
            ))
            await asyncio.sleep(0)
            await self.client.publish(set_topic, "0")
            await off_confirmation
            return {"ok": True, "message": "Проверка реле завершена"}
        except asyncio.TimeoutError:
            return {"ok": False, "message": "Реле не подтвердило команду"}
        finally:
            with suppress(Exception):
                await self.client.publish(set_topic, "0")
            await self.client.unsubscribe(state_topic)
