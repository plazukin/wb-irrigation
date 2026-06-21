from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from irrigationd.config import SafetyConfig
from irrigationd.mqtt.client import MqttClient
from irrigationd.storage.event_repo import EventRepository, WateringRunRepository
from irrigationd.storage.models import WateringRunModel, ZoneModel
from irrigationd.storage.settings_repo import PumpRepository, RainSensorRepository
from irrigationd.storage.settings_repo import FlowMeterRepository
from irrigationd.storage.zone_repo import ZoneRepository

from .safety import SafetyError, cooldown_remaining, validate_start
from .state import ServiceState


class _RainStartedError(SafetyError):
    pass


@dataclass
class _FlowRunState:
    started: float
    started_at_utc: datetime
    last_check: float
    target_liters: Optional[float]
    delivered_liters: float = 0


class IrrigationService:
    def __init__(
        self, zones: ZoneRepository, runs: WateringRunRepository,
        events: EventRepository, rain_sensor: RainSensorRepository,
        pump: PumpRepository, flow_meter: FlowMeterRepository,
        mqtt: MqttClient, config: SafetyConfig, state: ServiceState,
    ) -> None:
        self.zones = zones
        self.runs = runs
        self.events = events
        self.rain_sensor = rain_sensor
        self.pump = pump
        self.flow_meter = flow_meter
        self.mqtt = mqtt
        self.config = config
        self.state = state
        # На Python 3.9 блокировка должна создаваться в рабочем цикле событий.
        self._lock: Optional[asyncio.Lock] = None
        self._stopping_zone_ids: set[int] = set()
        self._flow_states: dict[int, _FlowRunState] = {}
        self._flow_tasks: dict[int, asyncio.Task[None]] = {}
        self.mqtt.add_handler(self._on_message)

    def bind_event_loop(self) -> None:
        asyncio.get_running_loop()
        self._lock = asyncio.Lock()

    def _operation_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self.bind_event_loop()
        assert self._lock is not None
        return self._lock

    async def _set_pump(self, value: str, zone_id: Optional[int] = None) -> None:
        pump = self.pump.get()
        if not (
            pump.enabled and pump.relay_state_topic and pump.relay_set_topic
        ):
            return
        cached = self.mqtt.cached(pump.relay_state_topic)
        if cached is not None and cached.value == value:
            return
        confirmation = asyncio.create_task(self.mqtt.wait_for(
            pump.relay_state_topic, lambda current: current == value,
            self.config.relay_confirm_timeout_sec, accept_cached=False,
        ))
        await asyncio.sleep(0)
        try:
            await self.mqtt.publish(pump.relay_set_topic, value)
            await confirmation
        except Exception as exc:
            confirmation.cancel()
            await asyncio.gather(confirmation, return_exceptions=True)
            action = "включение" if value == "1" else "отключение"
            self._event(
                "alarm", "pump_command_failed",
                f"Насос не подтвердил {action}", zone_id,
            )
            raise SafetyError(f"Насос не подтвердил {action}") from exc

    def _pump_used_by_other_zone(self, zone_id: int) -> bool:
        return any(run.zone_id != zone_id for run in self.runs.active())

    async def _clear_flow_monitor(self, zone_id: int) -> None:
        task = self._flow_tasks.get(zone_id)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self._flow_tasks.pop(zone_id, None)
            self._flow_states.pop(zone_id, None)

    def _rain_error(self, zone: ZoneModel) -> Optional[str]:
        rain = self.rain_sensor.get()
        if not rain.enabled or not rain.topic or zone.ignore_rain_sensor:
            return None
        value = self.mqtt.cached(rain.topic)
        if value is None:
            return "Нет данных от датчика дождя"
        if value.value not in {"0", "1"}:
            return "Некорректное значение датчика дождя"
        if value.value == rain.active_value:
            return "Полив отменён: идёт дождь"
        return None

    async def _cancel_start_for_rain(self, zone: ZoneModel) -> None:
        if not self._pump_used_by_other_zone(zone.id):
            with suppress(SafetyError):
                await self._set_pump("0", zone.id)
        await asyncio.gather(*(
            self.mqtt.publish(relay.relay_set_topic, "0")
            for relay in zone.relays
        ), return_exceptions=True)
        self._event(
            "info", "watering_skipped_rain",
            "Полив остановлен датчиком дождя", zone.id,
        )

    def _event(
        self, level: str, kind: str, message: str, zone_id: Optional[int] = None
    ) -> None:
        self.events.add(level, kind, message, zone_id)
        self.state.last_event = message
        if level == "alarm":
            self.state.alarm = message

    async def start_zone(
        self, zone_id: int, duration_sec: int, source: str = "manual",
        target_liters: Optional[float] = None,
    ) -> WateringRunModel:
        async with self._operation_lock():
            zone = self.zones.get(zone_id)
            if zone is None:
                raise SafetyError("Зона не найдена")
            relay_values = []
            for relay in zone.relays:
                cached = self.mqtt.cached(relay.relay_state_topic)
                relay_values.append(cached.value if cached else None)
            duration = validate_start(
                zone, duration_sec, relay_values,
                self.runs.active(), self.config.allow_parallel_zones,
            )
            meter = self.flow_meter.get()
            if target_liters is not None and not (meter.enabled and meter.topic):
                raise SafetyError("Полив по объёму требует настроенный расходомер")
            latest = self.runs.latest_finished(zone.id)
            remaining = cooldown_remaining(zone, latest.stopped_at if latest else None)
            if remaining:
                remaining_min = (remaining + 59) // 60
                raise SafetyError(f"Пауза перед запуском: {remaining_min} мин")
            rain_error = self._rain_error(zone)
            if rain_error:
                if "дождь" in rain_error:
                    self._event(
                        "info", "watering_skipped_rain", rain_error, zone.id,
                    )
                raise SafetyError(rain_error)
            pump = self.pump.get()
            await self._set_pump("1", zone.id)
            if pump.enabled and pump.relay_state_topic:
                await asyncio.sleep(pump.start_delay_sec)
            rain_error = self._rain_error(zone)
            if rain_error:
                await self._cancel_start_for_rain(zone)
                raise SafetyError(rain_error)
            confirmations = [asyncio.create_task(self.mqtt.wait_for(
                relay.relay_state_topic, lambda value: value == "1",
                self.config.relay_confirm_timeout_sec, accept_cached=False,
            )) for relay in zone.relays]
            await asyncio.sleep(0)
            try:
                await asyncio.gather(*(
                    self.mqtt.publish(relay.relay_set_topic, "1")
                    for relay in zone.relays
                ))
                await asyncio.gather(*confirmations)
                rain_error = self._rain_error(zone)
                if rain_error:
                    raise _RainStartedError(rain_error)
            except _RainStartedError as exc:
                await self._cancel_start_for_rain(zone)
                raise SafetyError(str(exc)) from exc
            except Exception as exc:
                for confirmation in confirmations:
                    confirmation.cancel()
                await asyncio.gather(*confirmations, return_exceptions=True)
                if not self._pump_used_by_other_zone(zone.id):
                    with suppress(SafetyError):
                        await self._set_pump("0", zone.id)
                await asyncio.gather(*(
                    self.mqtt.publish(relay.relay_set_topic, "0")
                    for relay in zone.relays
                ), return_exceptions=True)
                self._event("error", "relay_confirm_failed", "Не все реле подтвердили включение", zone.id)
                raise SafetyError("Не все реле подтвердили включение") from exc
            run = self.runs.create(zone.id, duration, source, target_liters)
            if meter.enabled and meter.topic:
                now = asyncio.get_running_loop().time()
                self._flow_states[zone.id] = _FlowRunState(
                    started=now, started_at_utc=datetime.now(timezone.utc),
                    last_check=now, target_liters=target_liters,
                )
                self._flow_tasks[zone.id] = asyncio.create_task(
                    self._monitor_flow(zone.id)
                )
            self._event("info", "watering_started", f"Зона «{zone.name}» запущена", zone.id)
            return run

    async def stop_zone(self, zone_id: int, reason: str = "manual") -> WateringRunModel:
        async with self._operation_lock():
            zone = self.zones.get(zone_id)
            active = self.runs.active(zone_id)
            if zone is None or not active:
                raise SafetyError("Зона не запущена")
            run = active[0]
            try:
                self._stopping_zone_ids.add(zone.id)
                if not self._pump_used_by_other_zone(zone.id):
                    with suppress(SafetyError):
                        await self._set_pump("0", zone.id)
                confirmations = [asyncio.create_task(self.mqtt.wait_for(
                    relay.relay_state_topic, lambda value: value == "0",
                    self.config.relay_confirm_timeout_sec, accept_cached=False,
                )) for relay in zone.relays]
                await asyncio.sleep(0)
                await asyncio.gather(*(
                    self.mqtt.publish(relay.relay_set_topic, "0")
                    for relay in zone.relays
                ))
                status = "finished" if reason == "duration_elapsed" else "stopped"
                try:
                    await asyncio.gather(*confirmations)
                except asyncio.TimeoutError:
                    for confirmation in confirmations:
                        confirmation.cancel()
                    await asyncio.gather(*confirmations, return_exceptions=True)
                    self._event("alarm", "relay_stop_failed", "Не все реле отключились", zone.id)
                    status = "error"
            finally:
                self._stopping_zone_ids.discard(zone.id)
            flow_state = self._flow_states.get(zone.id)
            finished = self.runs.finish(
                run.id, status, reason,
                flow_state.delivered_liters if flow_state else None,
            )
            assert finished is not None
            reasons = {
                "manual": "вручную", "duration_elapsed": "время истекло",
                "rain": "начался дождь",
                "dry_run": "защита от сухого хода",
                "volume_reached": "заданный объём подан",
            }
            self._event(
                "info", "watering_stopped",
                f"Зона «{zone.name}» остановлена: {reasons.get(reason, reason)}", zone.id,
            )
            await self._clear_flow_monitor(zone.id)
            return finished

    async def stop_all(self, reason: str) -> None:
        with suppress(SafetyError):
            await self._set_pump("0")
        for zone in self.zones.list():
            await asyncio.gather(*(
                self.mqtt.publish(relay.relay_set_topic, "0")
                for relay in zone.relays
            ))
        for run in self.runs.active():
            flow_state = self._flow_states.get(run.zone_id)
            self.runs.finish(
                run.id, "stopped", reason,
                flow_state.delivered_liters if flow_state else None,
            )
        for zone_id in tuple(self._flow_tasks):
            await self._clear_flow_monitor(zone_id)
        reasons = {"startup": "запуск службы", "shutdown": "остановка службы"}
        self._event("info", "stop_all", f"Все реле отключены: {reasons.get(reason, reason)}")

    async def _on_message(self, topic: str, value: str) -> None:
        rain = self.rain_sensor.get()
        if rain.enabled and rain.topic == topic:
            if value != rain.active_value:
                return
            for run in self.runs.active():
                zone = self.zones.get(run.zone_id)
                if zone is None or zone.ignore_rain_sensor:
                    continue
                with suppress(SafetyError):
                    await self.stop_zone(zone.id, "rain")
            return
        if value != "0":
            return
        zone = self.zones.get_by_state_topic(topic)
        if zone is None:
            return
        if zone.id in self._stopping_zone_ids:
            return
        active = self.runs.active(zone.id)
        if active:
            self._stopping_zone_ids.add(zone.id)
            try:
                if not self._pump_used_by_other_zone(zone.id):
                    with suppress(SafetyError):
                        await self._set_pump("0", zone.id)
                await asyncio.gather(*(
                    self.mqtt.publish(relay.relay_set_topic, "0")
                    for relay in zone.relays
                ), return_exceptions=True)
                flow_state = self._flow_states.get(zone.id)
                self.runs.finish(
                    active[0].id, "interrupted", "relay_turned_off",
                    flow_state.delivered_liters if flow_state else None,
                )
            finally:
                self._stopping_zone_ids.discard(zone.id)
            self._event("warning", "watering_interrupted", "Реле отключилось во время полива", zone.id)
            await self._clear_flow_monitor(zone.id)

    async def _monitor_flow(self, zone_id: int) -> None:
        state = self._flow_states[zone_id]
        try:
            while self.runs.active(zone_id):
                await asyncio.sleep(1)
                meter = self.flow_meter.get()
                if not meter.enabled or not meter.topic:
                    return
                now = asyncio.get_running_loop().time()
                elapsed = max(0, now - state.last_check)
                state.last_check = now
                cached = self.mqtt.cached(meter.topic)
                flow = None
                stale = True
                if cached is not None:
                    try:
                        flow = float(cached.value)
                    except (TypeError, ValueError):
                        flow = None
                    updated_at = getattr(cached, "updated_at", None)
                    if updated_at is not None:
                        if updated_at.tzinfo is None:
                            updated_at = updated_at.replace(tzinfo=timezone.utc)
                        stale = (
                            datetime.now(timezone.utc) - updated_at
                        ).total_seconds() > meter.stale_timeout_sec
                        stale = stale or updated_at < state.started_at_utc
                    else:
                        stale = False
                if flow is not None and flow >= 0 and not stale:
                    state.delivered_liters += flow * elapsed / 60

                grace_elapsed = now - state.started >= meter.startup_grace_sec
                pump = self.pump.get()
                needs_flow = pump.enabled or state.target_liters is not None
                if grace_elapsed and needs_flow and (
                    flow is None or stale or flow < meter.min_flow_l_min
                ):
                    self._event(
                        "alarm", "dry_run_detected",
                        "Полив остановлен: расход воды отсутствует", zone_id,
                    )
                    with suppress(SafetyError):
                        await self.stop_zone(zone_id, "dry_run")
                    return
                if (
                    state.target_liters is not None
                    and state.delivered_liters >= state.target_liters
                ):
                    with suppress(SafetyError):
                        await self.stop_zone(zone_id, "volume_reached")
                    return
        finally:
            self._flow_states.pop(zone_id, None)
            self._flow_tasks.pop(zone_id, None)

    def status(self) -> dict[str, str]:
        active = self.runs.active()
        zone_names = [self.zones.get(item.zone_id).name for item in active if self.zones.get(item.zone_id)]
        return {
            "active_zone": ", ".join(zone_names),
            "active_runs": str(len(active)),
            "last_event": self.state.last_event,
            "alarm": self.state.alarm,
        }
