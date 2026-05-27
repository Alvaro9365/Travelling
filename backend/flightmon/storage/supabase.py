"""Thin Supabase wrapper.

Postgres `daterange` and `int4range` are serialized by PostgREST as strings
like ``"[2026-07-10,2026-07-21)"``. We translate to/from our pydantic
DateWindow / DurationRange here so the rest of the code works with native
types.
"""
from __future__ import annotations

import re
from datetime import date

from supabase import Client, create_client

from ..models import DateWindow, DurationRange, FlightResult, Search

_RANGE_RE = re.compile(r"^([\[\(])([^,]*),([^\]\)]*)([\]\)])$")


def _parse_daterange(raw: str | None) -> DateWindow | None:
    if not raw:
        return None
    m = _RANGE_RE.match(raw)
    if not m:
        return None
    lower_inc, lo, hi, upper_inc = m.groups()
    start = date.fromisoformat(lo)
    end = date.fromisoformat(hi)
    if lower_inc == "(":
        start = date.fromordinal(start.toordinal() + 1)
    if upper_inc == ")":
        end = date.fromordinal(end.toordinal() - 1)
    return DateWindow(start=start, end=end)


def _parse_int4range(raw: str | None) -> DurationRange | None:
    if not raw:
        return None
    m = _RANGE_RE.match(raw)
    if not m:
        return None
    lower_inc, lo, hi, upper_inc = m.groups()
    mn = int(lo)
    mx = int(hi)
    if lower_inc == "(":
        mn += 1
    if upper_inc == ")":
        mx -= 1
    return DurationRange(min=mn, max=mx)


def _fmt_daterange(w: DateWindow) -> str:
    return f"[{w.start.isoformat()},{w.end.isoformat()}]"


def _fmt_int4range(d: DurationRange) -> str:
    return f"[{d.min},{d.max}]"


class SupabaseStore:
    def __init__(self, url: str, service_key: str) -> None:
        self._client: Client = create_client(url, service_key)

    def list_active_searches(self) -> list[Search]:
        rows = (
            self._client.table("searches")
            .select("*")
            .eq("active", True)
            .execute()
            .data
        ) or []
        return [self._row_to_search(r) for r in rows]

    def get_search(self, search_id: str) -> Search | None:
        rows = (
            self._client.table("searches")
            .select("*")
            .eq("id", search_id)
            .limit(1)
            .execute()
            .data
        ) or []
        return self._row_to_search(rows[0]) if rows else None

    def insert_results(self, results: list[FlightResult]) -> None:
        if not results:
            return
        payload = [
            {
                **r.model_dump(mode="json", exclude_none=True),
                "departure_date": r.departure_date.isoformat(),
                "return_date": r.return_date.isoformat() if r.return_date else None,
            }
            for r in results
        ]
        self._client.table("flight_results").insert(payload).execute()

    def lowest_price(self, search_id: str) -> float | None:
        rows = (
            self._client.table("flight_results")
            .select("price_eur")
            .eq("search_id", search_id)
            .order("price_eur")
            .limit(1)
            .execute()
            .data
        ) or []
        return float(rows[0]["price_eur"]) if rows else None

    def notification_seen(self, dedup_key: str) -> bool:
        rows = (
            self._client.table("notifications_sent")
            .select("id")
            .eq("dedup_key", dedup_key)
            .limit(1)
            .execute()
            .data
        ) or []
        return bool(rows)

    def mark_notification(self, search_id: str, dedup_key: str) -> None:
        self._client.table("notifications_sent").insert(
            {"search_id": search_id, "dedup_key": dedup_key}
        ).execute()

    @staticmethod
    def _row_to_search(row: dict) -> Search:
        return Search.model_validate(
            {
                **row,
                "outbound_window": _parse_daterange(row.get("outbound_window")),
                "duration_days": _parse_int4range(row.get("duration_days")),
            }
        )

    # Helpers for the (rare) case a script writes searches directly.
    @staticmethod
    def serialize_search_ranges(payload: dict) -> dict:
        out = dict(payload)
        if isinstance(out.get("outbound_window"), DateWindow):
            out["outbound_window"] = _fmt_daterange(out["outbound_window"])
        if isinstance(out.get("duration_days"), DurationRange):
            out["duration_days"] = _fmt_int4range(out["duration_days"])
        return out
