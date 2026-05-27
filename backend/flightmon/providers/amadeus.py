"""Amadeus Self-Service implementation of FlightProvider.

Uses the official `amadeus` SDK. We deliberately stick to the lightweight
"shopping" endpoints (flight_destinations / flight_dates) so we don't burn
the free-tier quota on combinatorial flight-offers queries. Those endpoints
do not return airline/stops/duration — those fields stay None until v2.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from amadeus import Client, ResponseError  # type: ignore[import-untyped]

from .base import FlightProvider, ProviderOffer

log = logging.getLogger(__name__)


def _fmt_date_param(window: tuple[date, date]) -> str:
    start, end = window
    return start.isoformat() if start == end else f"{start.isoformat()},{end.isoformat()}"


def _fmt_duration_param(duration: tuple[int, int] | None) -> str | None:
    if duration is None:
        return None
    lo, hi = duration
    return str(lo) if lo == hi else f"{lo},{hi}"


def _parse_offers(payload: list[dict], origin: str) -> list[ProviderOffer]:
    offers: list[ProviderOffer] = []
    for item in payload:
        try:
            price = float(item["price"]["total"])
        except (KeyError, TypeError, ValueError):
            continue
        offers.append(
            ProviderOffer(
                origin_iata=item.get("origin", origin),
                destination_iata=item["destination"],
                departure_date=date.fromisoformat(item["departureDate"]),
                return_date=date.fromisoformat(item["returnDate"]) if item.get("returnDate") else None,
                price_eur=price,
                deep_link=item.get("links", {}).get("flightOffers"),
                raw=item,
            )
        )
    return offers


class AmadeusProvider(FlightProvider):
    def __init__(self, client_id: str, client_secret: str, hostname: str = "test") -> None:
        self._client = Client(client_id=client_id, client_secret=client_secret, hostname=hostname)

    def _call(self, endpoint, **params):
        # Single retry on rate-limit; Amadeus returns 429 with Retry-After.
        for attempt in (1, 2):
            try:
                return endpoint.get(**params)
            except ResponseError as exc:
                if attempt == 1 and getattr(exc.response, "status_code", None) == 429:
                    wait = int(exc.response.result.get("retry_after", 5)) if exc.response.result else 5
                    log.warning("Amadeus 429, retrying in %ss", wait)
                    time.sleep(wait)
                    continue
                raise

    def inspiration(
        self,
        *,
        origin: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        params: dict = {
            "origin": origin,
            "departureDate": _fmt_date_param(departure_window),
            "oneWay": "false" if duration_days else "true",
        }
        if duration_days and (d := _fmt_duration_param(duration_days)):
            params["duration"] = d
        if max_price is not None:
            params["maxPrice"] = int(max_price)
        response = self._call(self._client.shopping.flight_destinations, **params)
        return _parse_offers(response.data or [], origin)

    def cheapest_dates(
        self,
        *,
        origin: str,
        destination: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        params: dict = {
            "origin": origin,
            "destination": destination,
            "departureDate": _fmt_date_param(departure_window),
            "oneWay": "false" if duration_days else "true",
        }
        if duration_days and (d := _fmt_duration_param(duration_days)):
            params["duration"] = d
        if max_price is not None:
            params["maxPrice"] = int(max_price)
        response = self._call(self._client.shopping.flight_dates, **params)
        return _parse_offers(response.data or [], origin)
