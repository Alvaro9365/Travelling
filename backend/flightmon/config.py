"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    data_dir: Path
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "Config":
        root = repo_root or Path(os.environ.get("FLIGHTMON_REPO_ROOT", Path.cwd()))
        return cls(
            data_dir=root / "data",
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        )
