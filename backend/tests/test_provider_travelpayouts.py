from datetime import date

import httpx
import pytest
import respx

from flightmon.providers.travelpayouts import (
    BASE_URL,
    TravelpayoutsProvider,
    _months_in_window,
    _deeplink,
)


def test_months_in_window_single_month():
    out = _months_in_window((date(2026, 9, 5), date(2026, 9, 20)))
    assert out == ["2026-09"]


def test_months_in_window_spans_multiple():
    out = _months_in_window((date(2026, 9, 25), date(2026, 11, 5)))
    assert out == ["2026-09", "2026-10", "2026-11"]


def test_deeplink_round_trip():
    link = _deeplink("MAD", "LIS", date(2026, 9, 5), date(2026, 9, 12))
    assert link == "https://www.aviasales.com/search/MAD0509LIS12091"


def test_deeplink_one_way():
    link = _deeplink("MAD", "LIS", date(2026, 9, 5), None)
    assert link == "https://www.aviasales.com/search/MAD0509LIS1"


SAMPLE_RESPONSE = {
    "success": True,
    "data": {
        "LIS": {
            "0": {
                "price": 145,
                "airline": "TP",
                "departure_at": "2026-09-12T07:30:00+00:00",
                "return_at": "2026-09-19T19:00:00+00:00",
                "transfers": 0,
                "expires_at": "2026-06-25T10:00:00Z",
            },
            "1": {
                "price": 320,
                "airline": "IB",
                "departure_at": "2026-09-30T15:00:00+00:00",  # outside window
                "return_at": "2026-10-05T10:00:00+00:00",
                "transfers": 0,
            },
        }
    },
}


@respx.mock
def test_cheapest_dates_parses_and_filters_window():
    respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    p = TravelpayoutsProvider(token="t1")
    offers = p.cheapest_dates(
        origin="MAD",
        destination="LIS",
        departure_window=(date(2026, 9, 5), date(2026, 9, 20)),
        duration_days=(5, 10),
        max_price=None,
    )
    assert len(offers) == 1
    o = offers[0]
    assert o.destination_iata == "LIS"
    assert o.price_eur == 145.0
    assert o.airline == "TP"
    assert o.stops == 0
    assert o.deep_link.startswith("https://www.aviasales.com/search/MAD1209LIS1909")


@respx.mock
def test_cheapest_dates_respects_max_price():
    respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    p = TravelpayoutsProvider(token="t1")
    offers = p.cheapest_dates(
        origin="MAD", destination="LIS",
        departure_window=(date(2026, 9, 1), date(2026, 9, 30)),
        duration_days=(5, 10),
        max_price=200,
    )
    assert len(offers) == 1   # the 320€ one is filtered (and outside window anyway)
    assert offers[0].price_eur == 145.0


@respx.mock
def test_cheapest_dates_filters_duration():
    respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    p = TravelpayoutsProvider(token="t1")
    offers = p.cheapest_dates(
        origin="MAD", destination="LIS",
        departure_window=(date(2026, 9, 1), date(2026, 9, 30)),
        duration_days=(2, 3),  # the only in-window offer is 7 days
        max_price=None,
    )
    assert offers == []


@respx.mock
def test_cheapest_dates_handles_failure_gracefully():
    respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(500, text="boom")
    )
    p = TravelpayoutsProvider(token="t1")
    offers = p.cheapest_dates(
        origin="MAD", destination="LIS",
        departure_window=(date(2026, 9, 1), date(2026, 9, 30)),
        duration_days=(5, 10),
        max_price=None,
    )
    assert offers == []


@respx.mock
def test_cheapest_dates_spans_multiple_months():
    route = respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {}})
    )
    p = TravelpayoutsProvider(token="t1")
    p.cheapest_dates(
        origin="MAD", destination="LIS",
        departure_window=(date(2026, 9, 25), date(2026, 11, 5)),
        duration_days=(5, 10),
        max_price=None,
    )
    assert route.call_count == 3
    months = [call.request.url.params["depart_date"] for call in route.calls]
    assert months == ["2026-09", "2026-10", "2026-11"]


@respx.mock
def test_inspiration_omits_destination_param():
    INSP = {
        "success": True,
        "data": {
            "LIS": {"0": {"price": 120, "airline": "TP",
                          "departure_at": "2026-09-10T07:00:00+00:00",
                          "return_at": "2026-09-17T19:00:00+00:00",
                          "transfers": 0}},
            "CDG": {"0": {"price": 220, "airline": "AF",
                          "departure_at": "2026-09-12T08:00:00+00:00",
                          "return_at": "2026-09-19T20:00:00+00:00",
                          "transfers": 0}},
        },
    }
    route = respx.get(f"{BASE_URL}/v1/prices/cheap").mock(
        return_value=httpx.Response(200, json=INSP)
    )
    p = TravelpayoutsProvider(token="t1")
    offers = p.inspiration(
        origin="MAD",
        departure_window=(date(2026, 9, 1), date(2026, 9, 30)),
        duration_days=(5, 10),
        max_price=200,  # CDG (220) gets filtered
    )
    # Destination param NOT sent — open-ended query.
    assert "destination" not in route.calls[0].request.url.params
    assert {o.destination_iata for o in offers} == {"LIS"}
