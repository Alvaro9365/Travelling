"""Entrypoint invoked by the GitHub Actions cron and local debugging."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

from .config import Config, ConfigError
from .notifier.telegram import TelegramNotifier
from .providers.amadeus import AmadeusProvider
from .search.runner import run_all, run_search
from .storage.supabase import SupabaseStore
from .summary import RunSummary, SearchRunSummary, to_markdown, to_oneline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flightmon")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Execute all active searches (or one).")
    run.add_argument("--search-id", help="Run only the given search id.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    provider = AmadeusProvider(cfg.amadeus_client_id, cfg.amadeus_client_secret, cfg.amadeus_hostname)
    store = SupabaseStore(cfg.supabase_url, cfg.supabase_service_key)
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

        _emit_summary(summary)
        # Non-zero exit when every search crashed, so the workflow turns red.
        if summary.searches and len(summary.failed_searches) == len(summary.searches):
            return 1
    return 0


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


# Re-export so existing imports keep working in tests that reach for the type.
__all__ = ["main", "SearchRunSummary"]
