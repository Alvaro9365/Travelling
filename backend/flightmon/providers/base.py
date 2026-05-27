"""Abstract flight provider interface.

Designed so that future providers (Kiwi, SerpAPI, mocks) plug in without
touching the search runner. The same shape also leaves room for sibling
HotelProvider / TransitProvider implementations in later versions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProviderOffer:
    origin_iata: str
    destination_iata: str
    departure_date: date
    return_date: date | None
    price_eur: float
    airline: str | None = None
    stops: int | None = None
    duration_minutes: int | None = None
    deep_link: str | None = None
    raw: dict | None = None


class FlightProvider(ABC):
    @abstractmethod
    def inspiration(
        self,
        *,
        origin: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        """Open-destination discovery search."""

    @abstractmethod
    def cheapest_dates(
        self,
        *,
        origin: str,
        destination: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        """Cheapest dates for a fixed origin/destination pair."""
