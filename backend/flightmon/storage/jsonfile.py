"""File-backed storage replacing Supabase.

Layout under `data/`:

    data/
        searches.yaml             # user-edited config (source of truth)
        results.json              # latest snapshot per search (overwritten)
        notifications.json        # dedup_keys for sent Telegram alerts
        runs.jsonl                # one line per cron execution
        history/<search_id>.jsonl # per-search append-only price history

All writes are atomic (tmp file + rename) so concurrent reads from the
dashboard never see a partially-written file.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import yaml

from ..models import FlightResult, Search


class JsonFileStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.searches_yaml = data_dir / "searches.yaml"
        self.results_path = data_dir / "results.json"
        self.notifications_path = data_dir / "notifications.json"
        self.runs_path = data_dir / "runs.jsonl"
        self.history_dir = data_dir / "history"

    # --- searches -----------------------------------------------------------

    def list_active_searches(self) -> list[Search]:
        return [s for s in self.list_searches() if s.active]

    def list_searches(self) -> list[Search]:
        if not self.searches_yaml.exists():
            return []
        with self.searches_yaml.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        items = raw.get("searches", [])
        return [Search.model_validate(item) for item in items]

    def get_search(self, search_id: str) -> Search | None:
        return next((s for s in self.list_searches() if s.id == search_id), None)

    # --- results ------------------------------------------------------------

    def insert_results(self, search_id: str, results: list[FlightResult]) -> None:
        """Overwrite latest snapshot + append to history."""
        if not results:
            return
        self.history_dir.mkdir(parents=True, exist_ok=True)
        captured_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        snapshot = self._read_snapshot()
        snapshot[search_id] = {
            "captured_at": captured_at,
            "offers": [self._serialize_result(r) for r in results],
        }
        _atomic_write_json(self.results_path, snapshot)

        history_file = self.history_dir / f"{search_id}.jsonl"
        with history_file.open("a", encoding="utf-8") as fh:
            for r in results:
                fh.write(
                    json.dumps(
                        {
                            "captured_at": captured_at,
                            **self._serialize_result(r),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    def _read_snapshot(self) -> dict:
        if not self.results_path.exists():
            return {}
        with self.results_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def lowest_price(self, search_id: str) -> float | None:
        history_file = self.history_dir / f"{search_id}.jsonl"
        if not history_file.exists():
            return None
        lowest: float | None = None
        with history_file.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                price = row.get("price_eur")
                if price is None:
                    continue
                if lowest is None or price < lowest:
                    lowest = float(price)
        return lowest

    # --- notifications dedup ------------------------------------------------

    def notification_seen(self, dedup_key: str) -> bool:
        return dedup_key in self._read_notifications()

    def mark_notification(self, dedup_key: str) -> None:
        keys = self._read_notifications()
        keys.add(dedup_key)
        _atomic_write_json(self.notifications_path, sorted(keys))

    def _read_notifications(self) -> set[str]:
        if not self.notifications_path.exists():
            return set()
        with self.notifications_path.open(encoding="utf-8") as fh:
            try:
                return set(json.load(fh))
            except json.JSONDecodeError:
                return set()

    # --- runs log -----------------------------------------------------------

    def append_run(self, payload: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.runs_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_recent_runs(self, limit: int = 20) -> list[dict]:
        if not self.runs_path.exists():
            return []
        with self.runs_path.open(encoding="utf-8") as fh:
            lines = fh.readlines()
        out: list[dict] = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(out) >= limit:
                break
        return out

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def _serialize_result(r: FlightResult) -> dict:
        # `model_dump(mode="json")` handles date / datetime → ISO strings.
        # Drop the heavy raw_offer payload to keep results.json small.
        data = r.model_dump(mode="json", exclude_none=True, exclude={"raw_offer"})
        data.pop("search_id", None)  # implicit by file/snapshot keying
        return data


def _atomic_write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# --- dashboard JSON builder ------------------------------------------------


def build_dashboard(store: JsonFileStore) -> dict:
    """Produce the single JSON the static dashboard fetches."""
    searches = store.list_searches()
    snapshot = store._read_snapshot()
    runs = store.read_recent_runs(limit=30)

    per_search: list[dict] = []
    deals: list[dict] = []
    for s in searches:
        snap = snapshot.get(s.id) or {}
        offers = snap.get("offers") or []
        offers_sorted = sorted(offers, key=lambda o: o["price_eur"])
        history = _aggregate_history(store, s.id)
        min_seen = min((p["min_price"] for p in history), default=None)
        last_min = offers_sorted[0]["price_eur"] if offers_sorted else None
        per_search.append(
            {
                "id": s.id,
                "name": s.name,
                "active": s.active,
                "config": _summarize_config(s),
                "captured_at": snap.get("captured_at"),
                "offers": offers_sorted,
                "history": history,
                "stats": {
                    "min_seen": min_seen,
                    "last_min": last_min,
                    "offers_count": len(offers),
                },
            }
        )
        threshold = s.notify_on.price_under
        for o in offers_sorted[:5]:
            is_under_threshold = threshold is not None and o["price_eur"] <= threshold
            is_new_low = min_seen is not None and o["price_eur"] <= min_seen
            if is_under_threshold or is_new_low:
                deals.append(
                    {
                        "search_id": s.id,
                        "search_name": s.name,
                        "reason": "≤ umbral" if is_under_threshold else "mínimo histórico",
                        **o,
                    }
                )

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "totals": {
            "searches": len(searches),
            "active_searches": sum(1 for s in searches if s.active),
            "offers": sum(len(s["offers"]) for s in per_search),
            "deals": len(deals),
        },
        "deals": sorted(deals, key=lambda d: d["price_eur"]),
        "searches": per_search,
        "recent_runs": runs,
    }


def _summarize_config(s: Search) -> dict:
    dest = s.destinations
    if dest.mode == "any":
        dest_label = f"cualquier {dest.region}" if dest.region else "cualquier destino"
    elif dest.mode == "include":
        dest_label = "solo " + ", ".join(dest.iatas)
    else:
        dest_label = "cualquiera salvo " + (", ".join(dest.iatas) or "—")
    return {
        "origin_iata": s.origin_iata,
        "destinations_label": dest_label,
        "outbound_window": f"{s.outbound_window.start} → {s.outbound_window.end}",
        "duration_days": (
            f"{s.duration_days.min}–{s.duration_days.max} días"
            if s.duration_days
            else None
        ),
        "trip_type": s.trip_type,
        "price_max": s.price_range.max if s.price_range else None,
        "price_under_alert": s.notify_on.price_under,
    }


def _aggregate_history(store: JsonFileStore, search_id: str) -> list[dict]:
    history_file = store.history_dir / f"{search_id}.jsonl"
    if not history_file.exists():
        return []
    by_day: dict[str, float] = {}
    with history_file.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            day = row.get("captured_at", "")[:10]
            price = row.get("price_eur")
            if not day or price is None:
                continue
            cur = by_day.get(day)
            if cur is None or price < cur:
                by_day[day] = float(price)
    return [{"day": d, "min_price": p} for d, p in sorted(by_day.items())]
