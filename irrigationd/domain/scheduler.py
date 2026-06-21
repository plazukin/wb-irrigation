from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional

from irrigationd.storage.schedule_repo import ScheduleRepository

from .irrigation_service import IrrigationService
from .safety import SafetyError


class IrrigationScheduler:
    def __init__(self, schedules: ScheduleRepository, service: IrrigationService) -> None:
        self.schedules = schedules
        self.service = service
        self._fired: set[str] = set()
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(5)

    async def tick(self, now: Optional[datetime] = None) -> None:
        now = now or datetime.now().astimezone()
        minute = now.strftime("%Y-%m-%dT%H:%M")
        weekday = str(now.weekday())
        self._fired = {key for key in self._fired if key.endswith(minute)}
        for schedule in self.schedules.list(enabled_only=True):
            days = {part.strip() for part in schedule.days_of_week.split(",")}
            key = f"{schedule.id}:{minute}"
            if weekday not in days or schedule.start_time != now.strftime("%H:%M") or key in self._fired:
                continue
            self._fired.add(key)
            try:
                target_liters = None
                if schedule.watering_mode == "volume":
                    zone = self.service.zones.get(schedule.zone_id)
                    if zone is None or schedule.liters_per_m2 is None:
                        raise SafetyError("Некорректные параметры полива по объёму")
                    target_liters = zone.area_m2 * schedule.liters_per_m2
                await self.service.start_zone(
                    schedule.zone_id, schedule.duration_sec, "schedule",
                    target_liters,
                )
            except SafetyError as exc:
                self.service._event("warning", "schedule_start_failed", str(exc), schedule.zone_id)
        for run in self.service.runs.active():
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - started).total_seconds() >= run.planned_duration_sec:
                with suppress(SafetyError):
                    await self.service.stop_zone(run.zone_id, "duration_elapsed")
