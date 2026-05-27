"""Translate a flexible Search into concrete provider calls + result filter."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from ..models import Filters, PriceRange, Search


@dataclass(frozen=True)
class ProviderCall:
    kind: str  # "inspiration" | "cheapest_dates"
    origin: str
    destination: str | None
    departure_window: tuple[date, date]
    duration_days: tuple[int, int] | None
    max_price: float | None


def plan_calls(search: Search) -> list[ProviderCall]:
    window = (search.outbound_window.start, search.outbound_window.end)
    duration = (
        (search.duration_days.min, search.duration_days.max)
        if search.duration_days and search.trip_type == "round_trip"
        else None
    )
    max_price = search.price_range.max if search.price_range else None
    dest = search.destinations

    if dest.mode == "include":
        return [
            ProviderCall(
                kind="cheapest_dates",
                origin=search.origin_iata,
                destination=iata,
                departure_window=window,
                duration_days=duration,
                max_price=max_price,
            )
            for iata in dest.iatas
        ]

    # "any" or "exclude" both use the inspiration endpoint; exclude filters later.
    return [
        ProviderCall(
            kind="inspiration",
            origin=search.origin_iata,
            destination=None,
            departure_window=window,
            duration_days=duration,
            max_price=max_price,
        )
    ]


def apply_filters(offers, search: Search) -> list:
    """Drop offers that violate the search's filters / price / dest exclusions."""
    filters = search.filters
    price = search.price_range
    dest = search.destinations
    excluded_iatas = set(dest.iatas) if dest.mode == "exclude" else set()
    excluded_airlines = set(filters.excluded_airlines)

    kept = []
    for o in offers:
        if excluded_iatas and o.destination_iata in excluded_iatas:
            continue
        if price and not _price_in_range(o.price_eur, price):
            continue
        if filters.max_stops is not None and o.stops is not None and o.stops > filters.max_stops:
            continue
        if (
            filters.max_duration_minutes is not None
            and o.duration_minutes is not None
            and o.duration_minutes > filters.max_duration_minutes
        ):
            continue
        if excluded_airlines and o.airline and o.airline in excluded_airlines:
            continue
        kept.append(o)
    return kept


def _price_in_range(p: float, r: PriceRange) -> bool:
    if r.min is not None and p < r.min:
        return False
    if r.max is not None and p > r.max:
        return False
    return True
