from datetime import date
from unittest.mock import MagicMock

from flightmon.models import (
    DateWindow,
    DestinationsAny,
    DurationRange,
    NotifyOn,
    Search,
)
from flightmon.providers.base import ProviderOffer
from flightmon.search.runner import run_search


def _make_search(**overrides) -> Search:
    defaults = dict(
        id="s1",
        name="t",
        origin_iata="MAD",
        outbound_window=DateWindow(start=date(2026, 7, 10), end=date(2026, 7, 20)),
        duration_days=DurationRange(min=5, max=10),
        destinations=DestinationsAny(mode="any"),
        notify_on=NotifyOn(new_lowest=True),
    )
    defaults.update(overrides)
    return Search(**defaults)


def test_new_lowest_does_not_fire_when_batch_only_matches_previous_min():
    """Regression: previous_min must be snapshotted BEFORE insert; otherwise the
    cheapest row of the batch becomes its own previous and the alert fires.
    """
    search = _make_search()
    provider = MagicMock()
    provider.inspiration.return_value = [
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 200.0),
    ]
    store = MagicMock()
    store.lowest_price.return_value = 200.0  # previously seen minimum
    notifier = MagicMock()

    run_search(search, provider, store, notifier)

    notifier.maybe_notify.assert_not_called()


def test_new_lowest_fires_when_offer_beats_previous_min():
    search = _make_search()
    provider = MagicMock()
    provider.inspiration.return_value = [
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 150.0),
    ]
    store = MagicMock()
    store.lowest_price.return_value = 200.0
    notifier = MagicMock()

    run_search(search, provider, store, notifier)

    notifier.maybe_notify.assert_called_once()
    reason = notifier.maybe_notify.call_args.args[2]
    assert "nuevo mínimo" in reason


def test_new_lowest_fires_when_no_history():
    search = _make_search()
    provider = MagicMock()
    provider.inspiration.return_value = [
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 150.0),
    ]
    store = MagicMock()
    store.lowest_price.return_value = None  # no previous results
    notifier = MagicMock()

    run_search(search, provider, store, notifier)

    notifier.maybe_notify.assert_called_once()
