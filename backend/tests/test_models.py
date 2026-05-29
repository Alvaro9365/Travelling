from datetime import date

import pytest
from pydantic import ValidationError

from flightmon.models import (
    DateWindow,
    DestinationsAny,
    DurationRange,
    Search,
)


def _base(**o):
    defaults = dict(
        id="s1",
        name="t",
        origin_iata="MAD",
        outbound_window=DateWindow(start=date(2026, 7, 10), end=date(2026, 7, 20)),
        destinations=DestinationsAny(mode="any"),
    )
    defaults.update(o)
    return defaults


def test_round_trip_requires_duration_days():
    with pytest.raises(ValidationError, match="duration_days"):
        Search(**_base(trip_type="round_trip", duration_days=None))


def test_round_trip_with_duration_is_valid():
    s = Search(**_base(trip_type="round_trip", duration_days=DurationRange(min=5, max=10)))
    assert s.duration_days is not None


def test_one_way_does_not_require_duration():
    s = Search(**_base(trip_type="one_way", duration_days=None))
    assert s.duration_days is None
