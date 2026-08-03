from __future__ import annotations

from datetime import date, time
from pathlib import Path

from drexel_schedule_generator.webtms import commands
from drexel_schedule_generator.webtms.crawler import CrawlResult, CrawlStats
from drexel_schedule_generator.webtms.records import (
    DiscoveredTerm,
    ParsedCourse,
    ParsedFixtureDataset,
    ParsedMeeting,
    ParsedSection,
    ParsedTerm,
)


def result() -> CrawlResult:
    meeting = ParsedMeeting(frozenset({1}), time(9), time(10), date(2026, 9, 22), date(2026, 12, 5), None, None)
    course = ParsedCourse(None, "TEST", None, "101", "Test", None, None, None, True,
                          ParsedSection("1", "1", "A", "Lecture", "active", None, None, meetings=(meeting,)))
    return CrawlResult(
        DiscoveredTerm("202615", "Fall Quarter 26-27", "quarter", "2026-2027", 0, "/term"),
        ParsedFixtureDataset(ParsedTerm("202615", "Fall Quarter 26-27"), (course,)),
        CrawlStats(colleges=1, subjects=1, courses_discovered=1, sections_discovered=1, sections_usable=1),
        True,
    )


def test_live_dry_run_does_not_open_database(monkeypatch, tmp_path: Path, capsys) -> None:
    class Client:
        def __init__(self, *_args, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): pass

    monkeypatch.setattr(commands, "validate_stored_session", lambda *_: True)
    monkeypatch.setattr(commands, "WebTMSBrowserClient", Client)
    monkeypatch.setattr(commands, "crawl_term", lambda *_args, **_kwargs: result())

    assert commands.main(["--state-path", str(tmp_path / "state.json"), "import-next-term", "--dry-run"]) == 0
    assert "PostgreSQL was not modified" in capsys.readouterr().out


def test_explicit_term_command_requires_code() -> None:
    parser = commands.build_parser()
    args = parser.parse_args(["import-term", "--term-code", "202615", "--dry-run"])
    assert args.term_code == "202615"

