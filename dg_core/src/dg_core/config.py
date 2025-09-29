"""Configuration loading utilities for DG Core."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError
from platformdirs import user_config_dir


class NetworkConfig(BaseModel):
    allow: bool = Field(default=False, description="Allow outbound network calls")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO", description="Logging verbosity level")

    def normalized_level(self) -> str:
        return self.level.upper()


class IPCConfig(BaseModel):
    transport: str = Field(default="uds", description="Transport to use: uds|pipe|tcp")
    socket_path: Optional[Path] = Field(default=None)
    named_pipe: Optional[str] = Field(default=None)
    tcp_host: str = Field(default="127.0.0.1")
    tcp_port: Optional[int] = Field(default=None, ge=1, le=65535)

    def resolved_transport(self) -> str:
        return self.transport.lower()


class AppConfig(BaseModel):
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ipc: IPCConfig = Field(default_factory=IPCConfig)


DEFAULT_CONFIG = AppConfig()


def config_search_paths(explicit: Optional[Path] = None) -> Iterable[Path]:
    if explicit:
        yield explicit
    cwd_config = Path.cwd() / ".dg" / "config.yaml"
    yield cwd_config
    yield Path(user_config_dir("dg", roaming=True)) / "config.yaml"


def load_config(path: Optional[Path] = None) -> AppConfig:
    for candidate in config_search_paths(path):
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            try:
                return AppConfig.model_validate(data)
            except ValidationError as exc:
                raise ValueError(f"Invalid configuration in {candidate}: {exc}") from exc
    return DEFAULT_CONFIG.model_copy(deep=True)


def dump_default_config(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(DEFAULT_CONFIG.model_dump(mode="json"), handle, sort_keys=False)
