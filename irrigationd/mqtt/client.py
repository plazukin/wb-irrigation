from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)
MessageHandler = Callable[[str, str], Optional[Awaitable[None]]]


@dataclass(frozen=True)
class CachedValue:
    value: str
    updated_at: datetime


class MqttClient:
    """Клиент paho с интерфейсом asyncio и учётом подписок."""

    def __init__(self, host: str, port: int, client_id: str) -> None:
        self.host = host
        self.port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # На Python 3.9 Event должен создаваться в рабочем цикле событий.
        self._connected: Optional[asyncio.Event] = None
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._subscription_refs: dict[str, int] = {}
        self._handlers: set[MessageHandler] = set()
        self._cache: dict[str, CachedValue] = {}
        self._waiters: dict[str, list[tuple[Callable[[str], bool], asyncio.Future[str]]]] = {}
        self._lock = Lock()

    async def connect(self, timeout: float = 10) -> None:
        self._loop = asyncio.get_running_loop()
        self._connected = asyncio.Event()
        self._client.connect_async(self.host, self.port, keepalive=30)
        self._client.loop_start()
        try:
            await asyncio.wait_for(self._connected.wait(), timeout)
        except BaseException:
            self._client.disconnect()
            self._client.loop_stop()
            self._connected = None
            self._loop = None
            raise

    async def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        if self._connected is not None:
            self._connected.clear()
        self._connected = None
        self._loop = None

    def _is_connected(self) -> bool:
        return self._connected is not None and self._connected.is_set()

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: object,
                    reason_code: mqtt.ReasonCode, properties: object = None) -> None:
        if reason_code != 0:
            logger.error("Ошибка подключения к MQTT: %s", reason_code)
            return
        with self._lock:
            topics = tuple(self._subscription_refs)
        for topic in topics:
            client.subscribe(topic)
        loop = self._loop
        connected = self._connected
        if loop is not None and connected is not None:
            loop.call_soon_threadsafe(connected.set)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, flags: object,
                       reason_code: mqtt.ReasonCode, properties: object = None) -> None:
        loop = self._loop
        connected = self._connected
        if loop is not None and connected is not None:
            loop.call_soon_threadsafe(connected.clear)

    def _on_message(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            value = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("Пропущено значение MQTT не в UTF-8: %s", message.topic)
            return
        if self._loop:
            self._loop.call_soon_threadsafe(self._dispatch, message.topic, value)

    def _dispatch(self, topic: str, value: str) -> None:
        self._cache[topic] = CachedValue(value, datetime.now(timezone.utc))
        waiting = self._waiters.get(topic, [])
        remaining: list[tuple[Callable[[str], bool], asyncio.Future[str]]] = []
        for predicate, future in waiting:
            if not future.done() and predicate(value):
                future.set_result(value)
            elif not future.done():
                remaining.append((predicate, future))
        self._waiters[topic] = remaining
        for handler in tuple(self._handlers):
            result = handler(topic, value)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    async def subscribe(self, topic: str) -> None:
        with self._lock:
            is_new = topic not in self._subscription_refs
            self._subscription_refs[topic] = self._subscription_refs.get(topic, 0) + 1
        if is_new and self._is_connected():
            result, _ = self._client.subscribe(topic)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"Не удалось подписаться на {topic}: {result}")

    async def unsubscribe(self, topic: str) -> None:
        with self._lock:
            count = self._subscription_refs.get(topic, 0)
            remove = count == 1
            if remove:
                del self._subscription_refs[topic]
            elif count > 1:
                self._subscription_refs[topic] = count - 1
        if remove and self._is_connected():
            self._client.unsubscribe(topic)

    async def publish(self, topic: str, value: str, retain: bool = False) -> None:
        info = self._client.publish(topic, value, qos=0, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Не удалось отправить значение в {topic}: {info.rc}")

    def cached(self, topic: str) -> Optional[CachedValue]:
        return self._cache.get(topic)

    async def wait_for(
        self, topic: str, predicate: Callable[[str], bool] = lambda _: True,
        timeout: float = 5, accept_cached: bool = True,
    ) -> str:
        cached = self.cached(topic)
        if accept_cached and cached is not None and predicate(cached.value):
            return cached.value
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._waiters.setdefault(topic, []).append((predicate, future))
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            items = self._waiters.get(topic, [])
            self._waiters[topic] = [(p, f) for p, f in items if f is not future]

    def add_handler(self, handler: MessageHandler) -> None:
        self._handlers.add(handler)

    def remove_handler(self, handler: MessageHandler) -> None:
        self._handlers.discard(handler)

    @property
    def subscriptions(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._subscription_refs)
