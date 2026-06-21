from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import RelayModel


class RelayRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def list(self) -> list[RelayModel]:
        with self.sessions() as session:
            return list(session.scalars(select(RelayModel).order_by(RelayModel.id)))

    def get(self, relay_id: int) -> Optional[RelayModel]:
        with self.sessions() as session:
            return session.get(RelayModel, relay_id)

    def get_many(self, relay_ids: list[int]) -> list[RelayModel]:
        with self.sessions() as session:
            return list(session.scalars(
                select(RelayModel).where(RelayModel.id.in_(relay_ids))
                .order_by(RelayModel.id)
            ))

    def get_by_state_topic(self, topic: str) -> Optional[RelayModel]:
        with self.sessions() as session:
            return session.scalar(select(RelayModel).where(
                RelayModel.relay_state_topic == topic
            ))

    def create(self, values: dict[str, Any]) -> RelayModel:
        with self.sessions.begin() as session:
            relay = RelayModel(**values)
            session.add(relay)
            session.flush()
            session.refresh(relay)
            return relay

    def update(self, relay_id: int, values: dict[str, Any]) -> Optional[RelayModel]:
        with self.sessions.begin() as session:
            relay = session.get(RelayModel, relay_id)
            if relay is None:
                return None
            for key, value in values.items():
                setattr(relay, key, value)
            session.flush()
            session.refresh(relay)
            return relay

    def delete(self, relay_id: int) -> bool:
        with self.sessions.begin() as session:
            relay = session.get(RelayModel, relay_id)
            if relay is None:
                return False
            session.delete(relay)
            return True
