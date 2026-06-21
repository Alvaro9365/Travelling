from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from flightmon.providers.fastflights import (
    EUROPE_HUBS,
    FastFlightsProvider,
    _date_samples,
    _duration_samples,
    _flights_to_offer,
)


def test_date_samples_endpoints_and_count():
    start, end = date(2026, 7, 10), date(2026, 7, 20)
    samples = _date_samples(start, end, 3)
    assert samples[0] == start
    assert samples[-1] == end
    assert len(samples) == 3


def test_date_samples_single_day():
    d = date(2026, 7, 10)
    assert _date_samples(d, d, 4) == [d]


def test_duration_samples_handles_none_and_singletons():
    assert _duration_samples(None, 3) == [None]
    assert _duration_samples((7, 7), 3) == [7]
    out = _duration_samples((5, 10), 2)
    assert out == [5, 10]


def test_flights_to_offer_round_trip_two_legs_no_stops():
    flights = SimpleNamespace(
        price=199,
        airlines=["IB"],
        flights=[
            SimpleNamespace(duration=160),
            SimpleNamespace(duration=170),
        ],
    )
    o = _flights_to_offer(
        origin="MAD",
        destination="LIS",
        outbound=date(2026, 7, 12),
        return_date=date(2026, 7, 19),
        flights=flights,
    )
    assert o.price_eur == 199.0
    assert o.airline == "IB"
    assert o.stops == 0
    assert o.duration_minutes == 330
    assert o.return_date == date(2026, 7, 19)


def test_flights_to_offer_one_way_with_one_stop():
    flights = SimpleNamespace(
        price=120,
        airlines=["FR"],
        flights=[SimpleNamespace(duration=100), SimpleNamespace(duration=120)],
    )
    o = _flights_to_offer(
        origin="MAD",
        destination="VIE",
        outbound=date(2026, 7, 12),
        return_date=None,
        flights=flights,
    )
    assert o.stops == 1
    assert o.return_date is None


def _airport_code(airport) -> str:
    # In FlightQuery the protobuf field is `airport`; in our domain it's a string.
    if isinstance(airport, str):
        return airport
    return getattr(airport, "airport", None) or getattr(airport, "code", str(airport))


def _fake_get_flights_factory(prices_by_dest: dict[str, int]):
    def fake(query, **_kwargs):
        # Inspect the first leg's destination from the query string repr.
        # Simpler: stash the inputs by patching create_query separately.
        return None
    return fake


def test_cheapest_dates_samples_and_returns_offers():
    captured_args: list[dict] = []

    def fake_get_flights(query, **kwargs):
        # Build a result list with one fake "Flights" item priced by dest.
        leg = query.flight_data[0]
        captured_args.append({"date": leg.date, "from": _airport_code(leg.from_airport), "to": _airport_code(leg.to_airport)})
        result = [SimpleNamespace(
            price=180,
            airlines=["IB"],
            flights=[SimpleNamespace(duration=150), SimpleNamespace(duration=160)],
        )]
        return result

    p = FastFlightsProvider(date_samples=2, duration_samples=1, throttle_seconds=0)
    with patch("flightmon.providers.fastflights.get_flights", side_effect=fake_get_flights):
        offers = p.cheapest_dates(
            origin="MAD",
            destination="LIS",
            departure_window=(date(2026, 7, 10), date(2026, 7, 20)),
            duration_days=(7, 7),
            max_price=None,
        )

    assert len(offers) == 2
    assert {a["date"] for a in captured_args} == {"2026-07-10", "2026-07-20"}
    assert all(o.destination_iata == "LIS" for o in offers)
    assert all(o.return_date and (o.return_date - o.departure_date).days == 7 for o in offers)


def test_cheapest_dates_filters_by_max_price():
    def fake_get_flights(query, **kwargs):
        return [SimpleNamespace(
            price=300,
            airlines=["IB"],
            flights=[SimpleNamespace(duration=150), SimpleNamespace(duration=160)],
        )]

    p = FastFlightsProvider(date_samples=1, duration_samples=1, throttle_seconds=0)
    with patch("flightmon.providers.fastflights.get_flights", side_effect=fake_get_flights):
        offers = p.cheapest_dates(
            origin="MAD", destination="LIS",
            departure_window=(date(2026, 7, 12), date(2026, 7, 12)),
            duration_days=(7, 7), max_price=200,
        )
    assert offers == []


def test_cheapest_dates_handles_provider_exception():
    def fake_get_flights(query, **kwargs):
        raise RuntimeError("google said no")

    p = FastFlightsProvider(date_samples=1, duration_samples=1, throttle_seconds=0)
    with patch("flightmon.providers.fastflights.get_flights", side_effect=fake_get_flights):
        offers = p.cheapest_dates(
            origin="MAD", destination="LIS",
            departure_window=(date(2026, 7, 12), date(2026, 7, 12)),
            duration_days=(7, 7), max_price=None,
        )
    assert offers == []


def test_inspiration_uses_pool_and_skips_origin():
    pool = ("MAD", "LIS", "CDG")
    captured_destinations: list[str] = []

    def fake_get_flights(query, **kwargs):
        captured_destinations.append(_airport_code(query.flight_data[0].to_airport))
        return [SimpleNamespace(
            price=150,
            airlines=["VY"],
            flights=[SimpleNamespace(duration=140), SimpleNamespace(duration=150)],
        )]

    p = FastFlightsProvider(
        date_samples=1, duration_samples=1, throttle_seconds=0,
        inspiration_pool=pool,
    )
    with patch("flightmon.providers.fastflights.get_flights", side_effect=fake_get_flights):
        offers = p.inspiration(
            origin="MAD",
            departure_window=(date(2026, 7, 12), date(2026, 7, 12)),
            duration_days=(7, 7), max_price=None,
        )
    assert set(captured_destinations) == {"LIS", "CDG"}
    assert {o.destination_iata for o in offers} == {"LIS", "CDG"}


def test_europe_hubs_have_real_iatas():
    assert all(len(c) == 3 and c.isupper() for c in EUROPE_HUBS)
