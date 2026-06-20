import json
from datetime import date
from pathlib import Path

import pytest

from flightmon.models import FlightResult
from flightmon.storage.jsonfile import JsonFileStore, build_dashboard


@pytest.fixture
def store(tmp_path: Path) -> JsonFileStore:
    data_dir = tmp_path / "data"
    return JsonFileStore(data_dir)


def _result(price: float, dest: str = "LIS") -> FlightResult:
    return FlightResult(
        search_id="s1",
        origin_iata="MAD",
        destination_iata=dest,
        departure_date=date(2026, 7, 12),
        return_date=date(2026, 7, 19),
        price_eur=price,
    )


def test_yaml_searches_round_trip(store, tmp_path):
    yaml_text = """
searches:
  - id: s1
    name: Test
    origin_iata: MAD
    trip_type: round_trip
    outbound_window:
      start: 2026-07-10
      end: 2026-07-20
    duration_days:
      min: 5
      max: 10
    destinations:
      mode: any
      region: EUROPE
""".strip()
    store.searches_yaml.parent.mkdir(parents=True, exist_ok=True)
    store.searches_yaml.write_text(yaml_text)
    searches = store.list_searches()
    assert len(searches) == 1
    assert searches[0].destinations.mode == "any"
    assert store.get_search("s1") is not None


def test_insert_results_writes_snapshot_and_history(store):
    store.insert_results("s1", [_result(150.0), _result(180.0, "FCO")])
    snapshot = json.loads(store.results_path.read_text())
    assert "s1" in snapshot
    assert len(snapshot["s1"]["offers"]) == 2
    assert (store.history_dir / "s1.jsonl").exists()
    lines = (store.history_dir / "s1.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_lowest_price_from_history(store):
    store.insert_results("s1", [_result(200.0)])
    store.insert_results("s1", [_result(150.0)])
    assert store.lowest_price("s1") == 150.0
    assert store.lowest_price("missing") is None


def test_notifications_dedup(store):
    assert not store.notification_seen("abc")
    store.mark_notification("abc")
    assert store.notification_seen("abc")
    # Persists across re-instantiation.
    store2 = JsonFileStore(store.data_dir)
    assert store2.notification_seen("abc")


def test_run_log_append_and_read(store):
    store.append_run({"i": 1})
    store.append_run({"i": 2})
    recent = store.read_recent_runs()
    assert [r["i"] for r in recent] == [2, 1]


def test_build_dashboard_shape(store):
    store.searches_yaml.parent.mkdir(parents=True, exist_ok=True)
    store.searches_yaml.write_text(
        """
searches:
  - id: s1
    name: Verano Europa
    origin_iata: MAD
    trip_type: round_trip
    outbound_window: {start: 2026-07-10, end: 2026-07-20}
    duration_days: {min: 5, max: 10}
    destinations: {mode: any, region: EUROPE}
    notify_on: {price_under: 200}
""".strip()
    )
    store.insert_results("s1", [_result(150.0), _result(220.0, "FCO")])
    dash = build_dashboard(store)
    assert dash["totals"]["searches"] == 1
    assert dash["totals"]["offers"] == 2
    assert any(d["price_eur"] == 150.0 for d in dash["deals"])
    s = dash["searches"][0]
    assert s["name"] == "Verano Europa"
    assert s["offers"][0]["price_eur"] == 150.0  # sorted ascending
    assert s["history"]  # has at least one day point
    assert s["stats"]["last_min"] == 150.0
    assert s["config"]["destinations_label"] == "cualquier EUROPE"
