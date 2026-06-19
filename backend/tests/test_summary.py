from datetime import datetime

from flightmon.summary import RunSummary, SearchRunSummary, to_markdown, to_oneline


def _summary(*searches):
    return RunSummary(
        started_at=datetime(2026, 6, 19, 14, 0, 0),
        finished_at=datetime(2026, 6, 19, 14, 0, 12),
        searches=list(searches),
    )


def test_totals_are_sums():
    s = _summary(
        SearchRunSummary("a", "A", offers_returned=10, offers_kept=3, notifications_fired=1),
        SearchRunSummary("b", "B", offers_returned=8, offers_kept=2, provider_errors=1),
    )
    assert s.total_returned == 18
    assert s.total_kept == 5
    assert s.total_notifications == 1
    assert s.total_provider_errors == 1
    assert s.failed_searches == []


def test_failed_searches_isolated_from_total():
    s = _summary(
        SearchRunSummary("a", "A", offers_kept=3),
        SearchRunSummary("b", "B", error="db down"),
    )
    assert len(s.failed_searches) == 1
    assert s.failed_searches[0].search_id == "b"


def test_markdown_includes_table_and_header():
    s = _summary(
        SearchRunSummary("a", "Escapada verano", offers_returned=48, offers_kept=12, min_price=187.5, notifications_fired=1),
        SearchRunSummary("b", "Lisboa", offers_returned=8, offers_kept=2),
    )
    md = to_markdown(s)
    assert "## Flight monitor run — 2026-06-19 14:00 UTC" in md
    assert "Ran **2** searches" in md
    assert "| Search | Returned | Kept |" in md
    assert "| Escapada verano | 48 | 12 | 187.50 | 1 |" in md
    assert "| Lisboa | 8 | 2 | — | 0 |" in md


def test_markdown_calls_out_crashes():
    s = _summary(SearchRunSummary("a", "X", error="db down"))
    md = to_markdown(s)
    assert "❌" in md
    assert "Crashed searches" in md
    assert "db down" in md


def test_oneline_format():
    s = _summary(
        SearchRunSummary("a", "A", offers_returned=10, offers_kept=3, notifications_fired=1, provider_errors=2),
        SearchRunSummary("b", "B", error="boom"),
    )
    line = to_oneline(s)
    assert "2 searches" in line
    assert "10 offers" in line
    assert "3 kept" in line
    assert "1 notified" in line
    assert "2 provider errors" in line
    assert "1 failed" in line
