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
from flightmon.search.runner import run_all, run_search


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


def _provider_with(offers):
    p = MagicMock()
    p.inspiration.return_value = offers
    return p


def test_new_lowest_does_not_fire_when_batch_only_matches_previous_min():
    """Regression: previous_min must be snapshotted BEFORE insert."""
    provider = _provider_with([
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 200.0),
    ])
    store = MagicMock()
    store.lowest_price.return_value = 200.0
    notifier = MagicMock()
    notifier.maybe_notify.return_value = True

    summary = run_search(_make_search(), provider, store, notifier)

    notifier.maybe_notify.assert_not_called()
    assert summary.offers_kept == 1
    assert summary.notifications_fired == 0


def test_new_lowest_fires_when_offer_beats_previous_min():
    provider = _provider_with([
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 150.0),
    ])
    store = MagicMock()
    store.lowest_price.return_value = 200.0
    notifier = MagicMock()
    notifier.maybe_notify.return_value = True

    summary = run_search(_make_search(), provider, store, notifier)

    notifier.maybe_notify.assert_called_once()
    reason = notifier.maybe_notify.call_args.args[2]
    assert "nuevo mínimo" in reason
    assert summary.notifications_fired == 1
    assert summary.min_price == 150.0


def test_new_lowest_fires_when_no_history():
    provider = _provider_with([
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 150.0),
    ])
    store = MagicMock()
    store.lowest_price.return_value = None
    notifier = MagicMock()
    notifier.maybe_notify.return_value = True

    summary = run_search(_make_search(), provider, store, notifier)

    notifier.maybe_notify.assert_called_once()
    assert summary.notifications_fired == 1


def test_summary_counts_provider_errors():
    provider = MagicMock()
    provider.inspiration.side_effect = RuntimeError("boom")
    store = MagicMock()
    summary = run_search(_make_search(), provider, store, notifier=None)
    assert summary.provider_errors == 1
    assert summary.offers_returned == 0
    assert summary.offers_kept == 0


def test_run_all_isolates_search_crashes():
    s1 = _make_search(id="s1", name="s1")
    s2 = _make_search(id="s2", name="s2")
    store = MagicMock()
    store.list_active_searches.return_value = [s1, s2]
    store.insert_results.side_effect = [RuntimeError("db down"), None]
    store.lowest_price.return_value = None
    provider = _provider_with([
        ProviderOffer("MAD", "LIS", date(2026, 7, 12), date(2026, 7, 19), 150.0),
    ])
    summary = run_all(provider, store, notifier=None)
    assert len(summary.searches) == 2
    assert summary.failed_searches[0].search_id == "s1"
    assert summary.searches[1].offers_kept == 1
