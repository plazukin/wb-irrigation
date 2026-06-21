from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import EventModel, WateringRunModel


class EventRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def add(
        self, level: str, event_type: str, message: str,
        zone_id: Optional[int] = None, payload: Optional[dict[str, Any]] = None,
    ) -> EventModel:
        with self.sessions.begin() as session:
            event = EventModel(
                level=level, event_type=event_type, zone_id=zone_id, message=message,
                payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
            )
            session.add(event)
            session.flush()
            session.refresh(event)
            return event

    def list(self, limit: int = 200) -> list[EventModel]:
        with self.sessions() as session:
            return list(session.scalars(select(EventModel).order_by(EventModel.id.desc()).limit(limit)))


class WateringRunRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def create(
        self, zone_id: int, duration: int, source: str,
        target_liters: Optional[float] = None,
    ) -> WateringRunModel:
        with self.sessions.begin() as session:
            run = WateringRunModel(
                zone_id=zone_id, planned_duration_sec=duration, source=source,
                status="running", target_liters=target_liters,
                delivered_liters=0 if target_liters is not None else None,
            )
            session.add(run)
            session.flush()
            session.refresh(run)
            return run

    def active(self, zone_id: Optional[int] = None) -> list[WateringRunModel]:
        statement = select(WateringRunModel).where(WateringRunModel.status == "running")
        if zone_id is not None:
            statement = statement.where(WateringRunModel.zone_id == zone_id)
        with self.sessions() as session:
            return list(session.scalars(statement.order_by(WateringRunModel.id)))

    def latest_finished(self, zone_id: int) -> Optional[WateringRunModel]:
        statement = (
            select(WateringRunModel)
            .where(
                WateringRunModel.zone_id == zone_id,
                WateringRunModel.stopped_at.is_not(None),
            )
            .order_by(WateringRunModel.stopped_at.desc())
            .limit(1)
        )
        with self.sessions() as session:
            return session.scalar(statement)

    def finish(
        self, run_id: int, status: str, reason: str,
        delivered_liters: Optional[float] = None,
    ) -> Optional[WateringRunModel]:
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            run = session.get(WateringRunModel, run_id)
            if run is None:
                return None
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            run.stopped_at = now
            run.actual_duration_sec = max(0, int((now - started).total_seconds()))
            run.status = status
            run.stop_reason = reason
            if delivered_liters is not None:
                run.delivered_liters = delivered_liters
            session.flush()
            session.refresh(run)
            return run
