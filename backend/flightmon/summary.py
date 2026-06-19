"""Run-level summary used by the CLI and emitted to GitHub step summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchRunSummary:
    search_id: str
    search_name: str
    offers_returned: int = 0      # raw from provider, before filters
    offers_kept: int = 0          # after filters / exclusions
    provider_errors: int = 0      # exceptions from provider calls
    notifications_fired: int = 0
    min_price: float | None = None
    error: str | None = None      # set when the search itself crashed


@dataclass
class RunSummary:
    started_at: datetime
    finished_at: datetime | None = None
    searches: list[SearchRunSummary] = field(default_factory=list)

    @property
    def total_returned(self) -> int:
        return sum(s.offers_returned for s in self.searches)

    @property
    def total_kept(self) -> int:
        return sum(s.offers_kept for s in self.searches)

    @property
    def total_provider_errors(self) -> int:
        return sum(s.provider_errors for s in self.searches)

    @property
    def total_notifications(self) -> int:
        return sum(s.notifications_fired for s in self.searches)

    @property
    def failed_searches(self) -> list[SearchRunSummary]:
        return [s for s in self.searches if s.error]

    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


def to_markdown(summary: RunSummary) -> str:
    started = summary.started_at.strftime("%Y-%m-%d %H:%M UTC")
    duration = summary.duration_seconds()
    lines = [
        f"## Flight monitor run — {started}",
        "",
        f"- Ran **{len(summary.searches)}** searches in {duration:.1f}s.",
        f"- {summary.total_returned} offers retrieved · "
        f"{summary.total_kept} kept · "
        f"{summary.total_notifications} notifications sent.",
    ]
    if summary.total_provider_errors:
        lines.append(f"- ⚠️ {summary.total_provider_errors} provider call error(s).")
    if summary.failed_searches:
        lines.append(f"- ❌ {len(summary.failed_searches)} search(es) crashed.")
    lines.append("")
    if summary.searches:
        lines += [
            "| Search | Returned | Kept | Min € | Notified | Errors |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for s in summary.searches:
            min_p = f"{s.min_price:.2f}" if s.min_price is not None else "—"
            errors = s.provider_errors + (1 if s.error else 0)
            name = s.search_name if not s.error else f"{s.search_name} ⚠️"
            lines.append(
                f"| {name} | {s.offers_returned} | {s.offers_kept} "
                f"| {min_p} | {s.notifications_fired} | {errors} |"
            )
    if summary.failed_searches:
        lines += ["", "### Crashed searches", ""]
        for s in summary.failed_searches:
            lines.append(f"- **{s.search_name}** (`{s.search_id}`): {s.error}")
    return "\n".join(lines) + "\n"


def to_oneline(summary: RunSummary) -> str:
    return (
        f"{len(summary.searches)} searches · "
        f"{summary.total_returned} offers · "
        f"{summary.total_kept} kept · "
        f"{summary.total_notifications} notified · "
        f"{summary.total_provider_errors} provider errors · "
        f"{len(summary.failed_searches)} failed"
    )
