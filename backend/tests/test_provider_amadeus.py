from datetime import date
from unittest.mock import MagicMock

from flightmon.providers.amadeus import AmadeusProvider, _fmt_date_param, _fmt_duration_param, _parse_offers


def test_fmt_date_param_single_day():
    d = date(2026, 7, 10)
    assert _fmt_date_param((d, d)) == "2026-07-10"


def test_fmt_date_param_range():
    assert _fmt_date_param((date(2026, 7, 10), date(2026, 7, 20))) == "2026-07-10,2026-07-20"


def test_fmt_duration_param_handles_none_and_singletons():
    assert _fmt_duration_param(None) is None
    assert _fmt_duration_param((7, 7)) == "7"
    assert _fmt_duration_param((5, 10)) == "5,10"


def test_parse_offers_pulls_fields_and_skips_bad_rows():
    payload = [
        {
            "destination": "LIS",
            "departureDate": "2026-07-12",
            "returnDate": "2026-07-19",
            "price": {"total": "123.45"},
            "links": {"flightOffers": "https://x"},
        },
        {"destination": "BAD", "departureDate": "2026-07-12"},  # no price → skipped
    ]
    offers = _parse_offers(payload, "MAD")
    assert len(offers) == 1
    assert offers[0].destination_iata == "LIS"
    assert offers[0].price_eur == 123.45
    assert offers[0].deep_link == "https://x"


def test_inspiration_passes_max_price_and_duration():
    p = AmadeusProvider.__new__(AmadeusProvider)
    p._client = MagicMock()
    p._client.shopping.flight_destinations.get.return_value = MagicMock(data=[])
    p.inspiration(
        origin="MAD",
        departure_window=(date(2026, 7, 10), date(2026, 7, 20)),
        duration_days=(7, 7),
        max_price=200,
    )
    kwargs = p._client.shopping.flight_destinations.get.call_args.kwargs
    assert kwargs["origin"] == "MAD"
    assert kwargs["departureDate"] == "2026-07-10,2026-07-20"
    assert kwargs["duration"] == "7"
    assert kwargs["maxPrice"] == 200
    assert kwargs["oneWay"] == "false"


def test_cheapest_dates_one_way_omits_duration():
    p = AmadeusProvider.__new__(AmadeusProvider)
    p._client = MagicMock()
    p._client.shopping.flight_dates.get.return_value = MagicMock(data=[])
    p.cheapest_dates(
        origin="MAD",
        destination="LIS",
        departure_window=(date(2026, 7, 10), date(2026, 7, 10)),
        duration_days=None,
        max_price=None,
    )
    kwargs = p._client.shopping.flight_dates.get.call_args.kwargs
    assert kwargs["destination"] == "LIS"
    assert kwargs["oneWay"] == "true"
    assert "duration" not in kwargs
    assert "maxPrice" not in kwargs
