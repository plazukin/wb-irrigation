from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

import yaml


@dataclass(frozen=True)
class MqttConfig:
    host: str = "localhost"
    port: int = 1883
    client_id: str = "wb-irrigationd"


@dataclass(frozen=True)
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8088
    root_path: str = ""

    def __post_init__(self) -> None:
        if self.root_path and (
            not self.root_path.startswith("/") or self.root_path.endswith("/")
        ):
            raise ValueError("web.root_path должен начинаться с / и не заканчиваться на /")


@dataclass(frozen=True)
class StorageConfig:
    path: str = "/var/lib/wb-irrigation/irrigation.db"


@dataclass(frozen=True)
class SafetyConfig:
    stop_all_on_startup: bool = True
    stop_all_on_shutdown: bool = True
    default_max_duration_min: float = 15
    relay_confirm_timeout_sec: float = 5
    allow_parallel_zones: bool = False


@dataclass(frozen=True)
class Config:
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    web: WebConfig = field(default_factory=WebConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Раздел конфигурации {name!r} должен быть объектом")
    return value


def load_config(path: Union[str, Path] = "/etc/wb-irrigation/config.yaml") -> Config:
    config_path = Path(path)
    data: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Корень конфигурации должен быть объектом")
        data = loaded
    return Config(
        mqtt=MqttConfig(**_section(data, "mqtt")),
        web=WebConfig(**_section(data, "web")),
        storage=StorageConfig(**_section(data, "storage")),
        safety=SafetyConfig(**_section(data, "safety")),
    )
