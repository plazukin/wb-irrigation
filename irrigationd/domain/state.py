from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceState:
    last_event: str = ""
    alarm: str = ""

