"""Google Flights provider backed by the `fast-flights` library.

Strategy notes
--------------
Google Flights only answers *origin → destination* queries; there's no
inspiration endpoint. To map our `FlightProvider` interface:

* `cheapest_dates(origin, destination, …)` samples a handful of outbound
  dates from the window (and durations from the range, for round trips)
  and dispatches one Google query per sample. The cheapest itinerary
  returned for each sample becomes one `ProviderOffer`.

* `inspiration(origin, …)` iterates a small curated pool of European
  hubs and reuses `cheapest_dates` for each. Use the `include` destination
  mode if you want broader/different coverage.

To stay below Google's rate limits we throttle ~1 s between requests and
sample sparingly (2 outbound dates × 2 durations by default = 4 calls per
destination).
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from fast_flights import (  # type: ignore[import-untyped]
    FlightQuery,
    FlightsNotFound,
    Passengers,
    create_query,
    get_flights,
)

from .base import FlightProvider, ProviderOffer

log = logging.getLogger(__name__)


# A small curated list of popular European airports. Good defaults for
# `mode: any` searches; users wanting more can switch to `mode: include`.
EUROPE_HUBS: tuple[str, ...] = (
    "LIS", "CDG", "FCO", "AMS", "BER", "LHR", "DUB", "OPO", "MXP",
    "BCN", "VLC", "AGP", "PMI", "ATH", "VIE", "PRG", "BUD", "CPH",
    "ARN", "OSL", "ZRH", "BRU", "MUC", "HEL", "NAP",
)


def _sample(values: list, n: int) -> list:
    """Return up to *n* evenly spread items from *values* (always includes ends)."""
    if not values:
        return []
    if len(values) <= n:
        return values
    step = (len(values) - 1) / (n - 1)
    return [values[round(i * step)] for i in range(n)]


def _date_samples(start: date, end: date, n: int) -> list[date]:
    if start == end:
        return [start]
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return _sample(days, n)


def _duration_samples(duration: tuple[int, int] | None, n: int) -> list[int | None]:
    if duration is None:
        return [None]
    lo, hi = duration
    if lo == hi:
        return [lo]
    return _sample(list(range(lo, hi + 1)), n)


class FastFlightsProvider(FlightProvider):
    """Google Flights via `fast-flights`.

    Parameters
    ----------
    date_samples, duration_samples:
        How many outbound dates / round-trip durations to probe per
        destination. Defaults keep call count low.
    throttle_seconds:
        Seconds to sleep between requests to avoid hammering Google.
    inspiration_pool:
        IATA codes used when the search asks for "any" destinations.
    """

    def __init__(
        self,
        *,
        date_samples: int = 2,
        duration_samples: int = 2,
        throttle_seconds: float = 1.0,
        inspiration_pool: tuple[str, ...] = EUROPE_HUBS,
        currency: str = "EUR",
    ) -> None:
        self.date_samples = date_samples
        self.duration_samples = duration_samples
        self.throttle = throttle_seconds
        self.inspiration_pool = inspiration_pool
        self.currency = currency

    # --- FlightProvider --------------------------------------------------

    def inspiration(
        self,
        *,
        origin: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        offers: list[ProviderOffer] = []
        for dest in self.inspiration_pool:
            if dest == origin:
                continue
            try:
                offers.extend(
                    self.cheapest_dates(
                        origin=origin,
                        destination=dest,
                        departure_window=departure_window,
                        duration_days=duration_days,
                        max_price=max_price,
                    )
                )
            except Exception:  # noqa: BLE001
                log.exception("inspiration query failed for %s→%s", origin, dest)
        return offers

    def cheapest_dates(
        self,
        *,
        origin: str,
        destination: str,
        departure_window: tuple[date, date],
        duration_days: tuple[int, int] | None,
        max_price: float | None,
    ) -> list[ProviderOffer]:
        dates = _date_samples(departure_window[0], departure_window[1], self.date_samples)
        durations = _duration_samples(duration_days, self.duration_samples)
        offers: list[ProviderOffer] = []

        for outbound in dates:
            for dur in durations:
                offer = self._query_one(origin, destination, outbound, dur)
                if self.throttle:
                    time.sleep(self.throttle)
                if offer is None:
                    continue
                if max_price is not None and offer.price_eur > max_price:
                    continue
                offers.append(offer)
        return offers

    # --- internals -------------------------------------------------------

    def _query_one(
        self,
        origin: str,
        destination: str,
        outbound: date,
        duration_days: int | None,
    ) -> ProviderOffer | None:
        trip_type = "round-trip" if duration_days else "one-way"
        return_date = outbound + timedelta(days=duration_days) if duration_days else None
        legs = [FlightQuery(date=outbound.isoformat(), from_airport=origin, to_airport=destination)]
        if return_date:
            legs.append(FlightQuery(date=return_date.isoformat(), from_airport=destination, to_airport=origin))

        query = create_query(
            flights=legs,
            seat="economy",
            trip=trip_type,  # type: ignore[arg-type]
            passengers=Passengers(adults=1),
            currency=self.currency,
            language="en-US",
        )
        try:
            result = get_flights(query)
        except FlightsNotFound:
            return None
        except Exception as exc:  # noqa: BLE001
            log.warning("Google query failed (%s→%s %s): %s", origin, destination, outbound, exc)
            return None

        if not result:
            return None
        cheapest = min(result, key=lambda f: f.price)
        return _flights_to_offer(
            origin=origin,
            destination=destination,
            outbound=outbound,
            return_date=return_date,
            flights=cheapest,
        )


def _flights_to_offer(*, origin, destination, outbound, return_date, flights) -> ProviderOffer:
    legs = flights.flights or []
    expected_legs = 2 if return_date else 1
    stops = max(len(legs) - expected_legs, 0)
    duration_minutes = sum(getattr(leg, "duration", 0) or 0 for leg in legs) or None
    airline = flights.airlines[0] if flights.airlines else None
    return ProviderOffer(
        origin_iata=origin,
        destination_iata=destination,
        departure_date=outbound,
        return_date=return_date,
        price_eur=float(flights.price),
        airline=airline,
        stops=stops,
        duration_minutes=duration_minutes,
        deep_link=None,  # fast-flights doesn't expose a booking URL
        raw=None,        # Flights dataclass isn't JSON-serializable; skip
    )
