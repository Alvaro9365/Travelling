"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


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
    supabase_url: str
    supabase_service_key: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            amadeus_client_id=_required("AMADEUS_CLIENT_ID"),
            amadeus_client_secret=_required("AMADEUS_CLIENT_SECRET"),
            amadeus_hostname=os.environ.get("AMADEUS_HOSTNAME", "test"),
            supabase_url=_required("SUPABASE_URL"),
            supabase_service_key=_required("SUPABASE_SERVICE_KEY"),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        )
