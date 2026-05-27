"""Entrypoint invoked by the GitHub Actions cron and local debugging."""
from __future__ import annotations

import argparse
import logging
import sys

from .config import Config, ConfigError
from .notifier.telegram import TelegramNotifier
from .providers.amadeus import AmadeusProvider
from .search.runner import run_all, run_search
from .storage.supabase import SupabaseStore


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
            count = run_search(search, provider, store, notifier)
        else:
            count = run_all(provider, store, notifier)
        print(f"Stored {count} results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
