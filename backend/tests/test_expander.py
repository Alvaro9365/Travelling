from datetime import date

from flightmon.models import (
    DateWindow,
    DestinationsAny,
    DestinationsExclude,
    DestinationsInclude,
    DurationRange,
    Filters,
    PriceRange,
    Search,
)
from flightmon.providers.base import ProviderOffer
from flightmon.search.expander import apply_filters, plan_calls


def _base_search(**overrides) -> Search:
    defaults = dict(
        id="s1",
        name="test",
        origin_iata="MAD",
        outbound_window=DateWindow(start=date(2026, 7, 10), end=date(2026, 7, 20)),
        duration_days=DurationRange(min=5, max=10),
        destinations=DestinationsAny(mode="any"),
    )
    defaults.update(overrides)
    return Search(**defaults)


def test_plan_include_emits_one_call_per_destination():
    s = _base_search(destinations=DestinationsInclude(mode="include", iatas=["LIS", "CDG"]))
    calls = plan_calls(s)
    assert [c.kind for c in calls] == ["cheapest_dates", "cheapest_dates"]
    assert {c.destination for c in calls} == {"LIS", "CDG"}
    assert all(c.duration_days == (5, 10) for c in calls)


def test_plan_any_uses_inspiration_with_max_price():
    s = _base_search(price_range=PriceRange(max=200))
    calls = plan_calls(s)
    assert len(calls) == 1
    assert calls[0].kind == "inspiration"
    assert calls[0].max_price == 200
    assert calls[0].destination is None


def test_plan_one_way_drops_duration():
    s = _base_search(trip_type="one_way", duration_days=None)
    calls = plan_calls(s)
    assert calls[0].duration_days is None


def test_filters_drop_excluded_destinations():
    s = _base_search(destinations=DestinationsExclude(mode="exclude", iatas=["LHR"]))
    offers = [
        ProviderOffer("MAD", "LHR", date(2026, 7, 12), date(2026, 7, 19), 150.0),
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 120.0),
    ]
    kept = apply_filters(offers, s)
    assert [o.destination_iata for o in kept] == ["LIS"]


def test_filters_apply_price_and_advanced_filters():
    s = _base_search(
        price_range=PriceRange(min=50, max=200),
        filters=Filters(max_stops=1, max_duration_minutes=400, excluded_airlines=["RYR"]),
    )
    offers = [
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 250.0),   # too expensive
        ProviderOffer("MAD", "CDG", date(2026, 7, 12), date(2026, 7, 19), 120.0, stops=2),  # too many stops
        ProviderOffer("MAD", "FCO", date(2026, 7, 12), date(2026, 7, 19), 120.0, duration_minutes=600),  # too long
        ProviderOffer("MAD", "OPO", date(2026, 7, 12), date(2026, 7, 19), 120.0, airline="RYR"),  # excluded airline
        ProviderOffer("MAD", "AMS", date(2026, 7, 12), date(2026, 7, 19), 120.0, stops=1, duration_minutes=300, airline="KLM"),  # passes
    ]
    kept = apply_filters(offers, s)
    assert [o.destination_iata for o in kept] == ["AMS"]
