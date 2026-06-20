"""Entrypoint invoked by the GitHub Actions cron and local debugging."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .config import Config, ConfigError
from .notifier.telegram import TelegramNotifier
from .providers.amadeus import AmadeusProvider
from .search.runner import run_all, run_search
from .storage.jsonfile import JsonFileStore, build_dashboard, _atomic_write_json
from .summary import RunSummary, SearchRunSummary, to_markdown, to_oneline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flightmon")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Execute all active searches (or one).")
    run.add_argument("--search-id", help="Run only the given search id.")
    run.add_argument(
        "--dashboard-out",
        type=Path,
        help="Path to write dashboard.json (defaults to data/dashboard.json).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    provider = AmadeusProvider(cfg.amadeus_client_id, cfg.amadeus_client_secret, cfg.amadeus_hostname)
    store = JsonFileStore(cfg.data_dir)
    notifier = (
        TelegramNotifier(cfg.telegram_bot_token, cfg.telegram_chat_id, store)
        if cfg.telegram_bot_token and cfg.telegram_chat_id
        else None
    )

    if args.cmd == "run":
        if args.search_id:
            search = store.get_search(args.search_id)
            if not search:
                print(f"No such search: {args.search_id}", file=sys.stderr)
                return 1
            started = datetime.utcnow()
            single = run_search(search, provider, store, notifier)
            summary = RunSummary(started_at=started, finished_at=datetime.utcnow(), searches=[single])
        else:
            summary = run_all(provider, store, notifier)

        store.append_run(_run_log_entry(summary))
        dashboard_path = args.dashboard_out or (cfg.data_dir / "dashboard.json")
        _atomic_write_json(dashboard_path, build_dashboard(store))

        _emit_summary(summary)
        if summary.searches and len(summary.failed_searches) == len(summary.searches):
            return 1
    return 0


def _run_log_entry(summary: RunSummary) -> dict:
    return {
        "started_at": summary.started_at.isoformat(timespec="seconds") + "Z",
        "finished_at": (summary.finished_at or datetime.utcnow()).isoformat(timespec="seconds") + "Z",
        "duration_seconds": round(summary.duration_seconds(), 1),
        "totals": {
            "searches": len(summary.searches),
            "offers_returned": summary.total_returned,
            "offers_kept": summary.total_kept,
            "notifications": summary.total_notifications,
            "provider_errors": summary.total_provider_errors,
            "failed_searches": len(summary.failed_searches),
        },
        "searches": [asdict(s) for s in summary.searches],
    }


def _emit_summary(summary: RunSummary) -> None:
    print(to_oneline(summary))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        try:
            with open(step_summary, "a", encoding="utf-8") as fh:
                fh.write(to_markdown(summary))
        except OSError as exc:
            logging.getLogger(__name__).warning("Could not write GITHUB_STEP_SUMMARY: %s", exc)


if __name__ == "__main__":
    raise SystemExit(main())
