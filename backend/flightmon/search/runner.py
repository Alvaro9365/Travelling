"""Orchestrates a full run: searches → provider → filters → DB → notify."""
from __future__ import annotations

import logging
from datetime import datetime

from ..models import FlightResult, Search
from ..notifier.telegram import TelegramNotifier
from ..providers.base import FlightProvider, ProviderOffer
from ..storage.jsonfile import JsonFileStore
from ..summary import RunSummary, SearchRunSummary
from .expander import apply_filters, plan_calls

log = logging.getLogger(__name__)


def _execute_call(provider: FlightProvider, call) -> list[ProviderOffer]:
    if call.kind == "inspiration":
        return provider.inspiration(
            origin=call.origin,
            departure_window=call.departure_window,
            duration_days=call.duration_days,
            max_price=call.max_price,
        )
    return provider.cheapest_dates(
        origin=call.origin,
        destination=call.destination,  # type: ignore[arg-type]
        departure_window=call.departure_window,
        duration_days=call.duration_days,
        max_price=call.max_price,
    )


def _to_result(search_id: str, o: ProviderOffer) -> FlightResult:
    return FlightResult(
        search_id=search_id,
        origin_iata=o.origin_iata,
        destination_iata=o.destination_iata,
        departure_date=o.departure_date,
        return_date=o.return_date,
        price_eur=o.price_eur,
        airline=o.airline,
        stops=o.stops,
        duration_minutes=o.duration_minutes,
        deep_link=o.deep_link,
        raw_offer=o.raw,
    )


def run_search(
    search: Search,
    provider: FlightProvider,
    store: JsonFileStore,
    notifier: TelegramNotifier | None,
) -> SearchRunSummary:
    """Execute one search end-to-end and return a structured summary."""
    log.info("Running search %s (%s)", search.id, search.name)
    summary = SearchRunSummary(search_id=search.id, search_name=search.name)

    offers: list[ProviderOffer] = []
    for call in plan_calls(search):
        try:
            offers.extend(_execute_call(provider, call))
        except Exception as exc:  # noqa: BLE001 — never fail the whole run for one call
            log.exception("Provider call failed for %s: %s", search.id, exc)
            summary.provider_errors += 1

    summary.offers_returned = len(offers)
    results = [_to_result(search.id, o) for o in apply_filters(offers, search)]
    summary.offers_kept = len(results)
    if results:
        summary.min_price = min(r.price_eur for r in results)

    # Snapshot the previous min BEFORE inserting; otherwise the cheapest row
    # of the current batch becomes its own "previous" and `new_lowest` fires
    # on every run that returns results.
    previous_min = store.lowest_price(search.id) if notifier and results else None
    store.insert_results(search.id, results)

    if notifier and results:
        threshold = search.notify_on.price_under
        for r in results:
            reasons = []
            if threshold is not None and r.price_eur <= threshold:
                reasons.append(f"≤ {threshold:.0f} €")
            if (
                search.notify_on.new_lowest
                and (previous_min is None or r.price_eur < previous_min)
            ):
                reasons.append("nuevo mínimo")
            if reasons and notifier.maybe_notify(search, r, ", ".join(reasons)):
                summary.notifications_fired += 1

    return summary


def run_all(
    provider: FlightProvider,
    store: JsonFileStore,
    notifier: TelegramNotifier | None,
) -> RunSummary:
    run = RunSummary(started_at=datetime.utcnow())
    for s in store.list_active_searches():
        try:
            run.searches.append(run_search(s, provider, store, notifier))
        except Exception as exc:  # noqa: BLE001
            log.exception("Search %s failed", s.id)
            run.searches.append(
                SearchRunSummary(search_id=s.id, search_name=s.name, error=str(exc))
            )
    run.finished_at = datetime.utcnow()
    return run
