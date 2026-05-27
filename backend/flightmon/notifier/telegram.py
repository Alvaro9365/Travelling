"""Telegram notifier with per-offer deduplication."""
from __future__ import annotations

import hashlib
import logging

import httpx

from ..models import FlightResult, Search
from ..storage.supabase import SupabaseStore

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"


def dedup_key(search_id: str, r: FlightResult) -> str:
    raw = f"{search_id}|{r.destination_iata}|{r.departure_date}|{r.return_date}|{r.price_eur:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _format(search: Search, r: FlightResult, reason: str) -> str:
    dates = r.departure_date.isoformat()
    if r.return_date:
        dates += f" → {r.return_date.isoformat()}"
    msg = (
        f"*{search.name}* — {reason}\n"
        f"{r.origin_iata} → {r.destination_iata}\n"
        f"{dates}\n"
        f"*{r.price_eur:.2f} €*"
    )
    if r.deep_link:
        msg += f"\n[Ver oferta]({r.deep_link})"
    return msg


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, store: SupabaseStore) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._store = store

    def maybe_notify(self, search: Search, result: FlightResult, reason: str) -> bool:
        key = dedup_key(search.id, result)
        if self._store.notification_seen(key):
            return False
        text = _format(search, result, reason)
        resp = httpx.post(
            API.format(token=self._token),
            json={
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15.0,
        )
        if resp.status_code >= 400:
            log.error("Telegram error %s: %s", resp.status_code, resp.text)
            return False
        self._store.mark_notification(search.id, key)
        return True
