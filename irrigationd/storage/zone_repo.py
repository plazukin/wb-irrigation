from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .models import RelayModel, ZoneModel


class ZoneRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def list(self) -> list[ZoneModel]:
        with self.sessions() as session:
            statement = (
                select(ZoneModel).options(selectinload(ZoneModel.relays))
                .order_by(ZoneModel.id)
            )
            return list(session.scalars(statement))

    def get(self, zone_id: int) -> Optional[ZoneModel]:
        with self.sessions() as session:
            statement = (
                select(ZoneModel).options(selectinload(ZoneModel.relays))
                .where(ZoneModel.id == zone_id)
            )
            return session.scalar(statement)

    def get_by_state_topic(self, topic: str) -> Optional[ZoneModel]:
        with self.sessions() as session:
            statement = (
                select(ZoneModel).join(ZoneModel.relays)
                .options(selectinload(ZoneModel.relays))
                .where(RelayModel.relay_state_topic == topic)
            )
            return session.scalar(statement)

    def create(self, values: dict[str, Any]) -> ZoneModel:
        values = dict(values)
        relay_ids = values.pop("relay_ids")
        with self.sessions.begin() as session:
            zone = ZoneModel(**values)
            zone.relays = list(session.scalars(
                select(RelayModel).where(RelayModel.id.in_(relay_ids))
            ))
            session.add(zone)
            session.flush()
            return zone

    def update(self, zone_id: int, values: dict[str, Any]) -> Optional[ZoneModel]:
        values = dict(values)
        relay_ids = values.pop("relay_ids", None)
        with self.sessions.begin() as session:
            statement = (
                select(ZoneModel).options(selectinload(ZoneModel.relays))
                .where(ZoneModel.id == zone_id)
            )
            zone = session.scalar(statement)
            if zone is None:
                return None
            for key, value in values.items():
                setattr(zone, key, value)
            if relay_ids is not None:
                zone.relays = list(session.scalars(
                    select(RelayModel).where(RelayModel.id.in_(relay_ids))
                ))
            session.flush()
            return zone

    def delete(self, zone_id: int) -> bool:
        with self.sessions.begin() as session:
            zone = session.get(ZoneModel, zone_id)
            if zone is None:
                return False
            session.delete(zone)
            return True
