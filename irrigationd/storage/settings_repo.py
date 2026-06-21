from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from .models import FlowMeterModel, PumpModel, RainSensorModel


class RainSensorRepository:
    SETTINGS_ID = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self) -> RainSensorModel:
        with self.sessions.begin() as session:
            settings = session.get(RainSensorModel, self.SETTINGS_ID)
            if settings is None:
                settings = RainSensorModel(id=self.SETTINGS_ID)
                session.add(settings)
                session.flush()
                session.refresh(settings)
            return settings

    def update(self, values: dict[str, Any]) -> RainSensorModel:
        with self.sessions.begin() as session:
            settings = session.get(RainSensorModel, self.SETTINGS_ID)
            if settings is None:
                settings = RainSensorModel(id=self.SETTINGS_ID)
                session.add(settings)
            for key, value in values.items():
                setattr(settings, key, value)
            session.flush()
            session.refresh(settings)
            return settings


class PumpRepository:
    SETTINGS_ID = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self) -> PumpModel:
        with self.sessions.begin() as session:
            settings = session.get(PumpModel, self.SETTINGS_ID)
            if settings is None:
                settings = PumpModel(id=self.SETTINGS_ID)
                session.add(settings)
                session.flush()
                session.refresh(settings)
            return settings

    def update(self, values: dict[str, Any]) -> PumpModel:
        with self.sessions.begin() as session:
            settings = session.get(PumpModel, self.SETTINGS_ID)
            if settings is None:
                settings = PumpModel(id=self.SETTINGS_ID)
                session.add(settings)
            for key, value in values.items():
                setattr(settings, key, value)
            session.flush()
            session.refresh(settings)
            return settings


class FlowMeterRepository:
    SETTINGS_ID = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self) -> FlowMeterModel:
        with self.sessions.begin() as session:
            settings = session.get(FlowMeterModel, self.SETTINGS_ID)
            if settings is None:
                settings = FlowMeterModel(id=self.SETTINGS_ID)
                session.add(settings)
                session.flush()
                session.refresh(settings)
            return settings

    def update(self, values: dict[str, Any]) -> FlowMeterModel:
        with self.sessions.begin() as session:
            settings = session.get(FlowMeterModel, self.SETTINGS_ID)
            if settings is None:
                settings = FlowMeterModel(id=self.SETTINGS_ID)
                session.add(settings)
            for key, value in values.items():
                setattr(settings, key, value)
            session.flush()
            session.refresh(settings)
            return settings
