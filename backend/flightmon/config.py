"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Config:
    amadeus_client_id: str
    amadeus_client_secret: str
    amadeus_hostname: str  # "test" or "production"
    data_dir: Path
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "Config":
        root = repo_root or Path(os.environ.get("FLIGHTMON_REPO_ROOT", Path.cwd()))
        return cls(
            amadeus_client_id=_required("AMADEUS_CLIENT_ID"),
            amadeus_client_secret=_required("AMADEUS_CLIENT_SECRET"),
            amadeus_hostname=os.environ.get("AMADEUS_HOSTNAME", "test"),
            data_dir=root / "data",
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        )
