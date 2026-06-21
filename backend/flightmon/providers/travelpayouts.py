"""Travelpayouts / Aviasales provider.

Uses the public Flight Data API to retrieve cached cheap fares from the
Aviasales aggregator. Free to use after registering as an affiliate at
https://www.travelpayouts.com — no credit card required.

Important caveat:
    Travelpayouts returns prices that were last seen by REAL users
    searching on Aviasales / Jetradar in the last ~48 h, cached for up
    to 7 days. Coverage is excellent for popular routes (MAD–LIS, etc.)
    and patchy for obscure ones. Prices may be slightly stale; the
    booking link sends the user to Aviasales to confirm the live price.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

import httpx

from .base import FlightProvider, ProviderOffer

log = logging.getLogger(__name__)

BASE_URL = "https://api.travelpayouts.com"
AVIASALES_DEEPLINK = "https://www.aviasales.com/search/{route}{depart}{ret}1"


def _months_in_window(window: tuple[date, date]) -> list[str]:
    start, end = window
    out: list[str] = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur.strftime("%Y-%m"))
        # Step to first day of next month.
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def _deeplink(origin: str, destination: str, depart: date, return_date: date | None) -> str:
    # Aviasales URL shape: e.g. https://www.aviasales.com/search/MAD0509LIS12091
    # = MAD + DDMM(depart) + LIS + DDMM(return) + passengers(1)
    depart_str = depart.strftime("%d%m")
    if return_date:
        ret_str = return_date.strftime("%d%m")
        return f"https://www.aviasales.com/search/{origin}{depart_str}{destination}{ret_str}1"
    return f"https://www.aviasales.com/search/{origin}{depart_str}{destination}1"


class TravelpayoutsProvider(FlightProvider):
    """Travelpayouts/Aviasales cached price provider."""

    def __init__(
        self,
        *,
        token: str,
        marker: str | None = None,
        currency: str = "eur",
        timeout: float = 15.0,
    ) -> None:
        self.token = token
        self.marker = marker
        self.currency = currency
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"X-Access-Token": token, "Accept-Encoding": "gzip, deflate"},
        )

    # --- FlightProvider --------------------------------------------------

    def cheapest_dates(
        self,
        *,
        origin: str,
        destination: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        offers: list[ProviderOffer] = []
        for ym in _months_in_window(departure_window):
            offers.extend(self._fetch_cheap(origin, destination, ym))
        return list(self._filter(offers, departure_window, duration_days, max_price))

    def inspiration(
        self,
        *,
        origin: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        offers: list[ProviderOffer] = []
        for ym in _months_in_window(departure_window):
            offers.extend(self._fetch_cheap(origin, destination=None, depart_month=ym))
        return list(self._filter(offers, departure_window, duration_days, max_price))

    # --- internals -------------------------------------------------------

    def _fetch_cheap(
        self,
        origin: str,
        destination: str | None,
        depart_month: str,
    ) -> list[ProviderOffer]:
        params: dict[str, str] = {
            "origin": origin,
            "depart_date": depart_month,
            "currency": self.currency,
        }
        if destination:
            params["destination"] = destination
        try:
            resp = self._client.get("/v1/prices/cheap", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Travelpayouts cheap %s→%s %s: %s", origin, destination, depart_month, exc)
            return []
        payload = resp.json()
        if not payload.get("success"):
            log.warning("Travelpayouts cheap returned success=false: %s", payload.get("error"))
            return []
        return list(self._parse_cheap(origin, payload.get("data") or {}))

    def _parse_cheap(self, origin: str, data: dict) -> Iterable[ProviderOffer]:
        # Shape: data[destination_iata][index] = {price, airline, departure_at, return_at, ...}
        for dest, entries in (data or {}).items():
            if not isinstance(entries, dict):
                continue
            for entry in entries.values():
                try:
                    price = float(entry["price"])
                    depart = datetime.fromisoformat(entry["departure_at"].replace("Z", "+00:00")).date()
                except (KeyError, TypeError, ValueError):
                    continue
                ret_iso = entry.get("return_at")
                return_date = None
                if ret_iso:
                    try:
                        return_date = datetime.fromisoformat(ret_iso.replace("Z", "+00:00")).date()
                    except ValueError:
                        return_date = None
                yield ProviderOffer(
                    origin_iata=origin,
                    destination_iata=dest,
                    departure_date=depart,
                    return_date=return_date,
                    price_eur=price,
                    airline=entry.get("airline"),
                    stops=entry.get("transfers"),
                    duration_minutes=entry.get("duration_to"),  # outbound only; round-trip = duration field
                    deep_link=_deeplink(origin, dest, depart, return_date),
                    raw=entry,
                )

    @staticmethod
    def _filter(
        offers: Iterable[ProviderOffer],
        window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> Iterable[ProviderOffer]:
        start, end = window
        for o in offers:
            if not (start <= o.departure_date <= end):
                continue
            if duration_days and o.return_date:
                dur = (o.return_date - o.departure_date).days
                lo, hi = duration_days
                if not (lo <= dur <= hi):
                    continue
            if max_price is not None and o.price_eur > max_price:
                continue
            yield o

    def close(self) -> None:
        self._client.close()
