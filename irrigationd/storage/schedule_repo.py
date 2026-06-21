from __future__ import annotations

from threading import RLock
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import ScheduleModel


class ScheduleRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions
        self.write_lock = RLock()

    def list(self, enabled_only: bool = False) -> list[ScheduleModel]:
        statement = select(ScheduleModel).order_by(ScheduleModel.id)
        if enabled_only:
            statement = statement.where(ScheduleModel.enabled.is_(True))
        with self.sessions() as session:
            return list(session.scalars(statement))

    def get(self, schedule_id: int) -> Optional[ScheduleModel]:
        with self.sessions() as session:
            return session.get(ScheduleModel, schedule_id)

    def create(self, values: dict[str, Any]) -> ScheduleModel:
        with self.sessions.begin() as session:
            item = ScheduleModel(**values)
            session.add(item)
            session.flush()
            session.refresh(item)
            return item

    def update(self, schedule_id: int, values: dict[str, Any]) -> Optional[ScheduleModel]:
        with self.sessions.begin() as session:
            item = session.get(ScheduleModel, schedule_id)
            if item is None:
                return None
            for key, value in values.items():
                setattr(item, key, value)
            session.flush()
            session.refresh(item)
            return item

    def delete(self, schedule_id: int) -> bool:
        with self.sessions.begin() as session:
            item = session.get(ScheduleModel, schedule_id)
            if item is None:
                return False
            session.delete(item)
            return True
