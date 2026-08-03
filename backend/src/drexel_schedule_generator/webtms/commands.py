"""Maintainer-only commands for WebTMS authentication and investigation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .auth import AuthenticationRequired, authenticate_interactively, default_state_path, delete_storage_state, validate_stored_session
from .browser_client import WebTMSBrowserClient
from .checkpoint import CrawlCheckpoint, default_checkpoint_path
from .crawler import TARGET_TERM_NAME, crawl_term
from .importer import import_dataset
from .parser import page_structure, sanitize_html, webtms_route_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authorized WebTMS maintenance tools")
    parser.add_argument("--state-path", type=Path, default=default_state_path())
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("authenticate")
    subcommands.add_parser("validate-session")
    subcommands.add_parser("delete-session")
    fixture_import = subcommands.add_parser("import-fixtures")
    fixture_import.add_argument(
        "--fixtures",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "webtms",
    )
    fixture_import.add_argument("--term")
    for name in ("import-next-term", "import-term"):
        live = subcommands.add_parser(name)
        if name == "import-term":
            live.add_argument("--term-code", required=True)
        live.add_argument("--delay-seconds", type=float, default=2.0)
        live.add_argument("--max-retries", type=int, default=2)
        live.add_argument("--resume", action="store_true")
        live.add_argument("--college")
        live.add_argument("--subject")
        live.add_argument("--dry-run", action="store_true")
    discard = subcommands.add_parser("discard-checkpoint")
    discard.add_argument("--term-code", required=True)
    inspect = subcommands.add_parser("inspect")
    inspect.add_argument("url", nargs="*")
    fixture = subcommands.add_parser("save-sanitized-fixture")
    fixture.add_argument("--via", action="append", default=[])
    fixture.add_argument("url")
    fixture.add_argument("output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "authenticate":
            authenticate_interactively(args.state_path)
            print("Authentication succeeded; local ignored session state was saved.")
            return 0
        if args.command == "validate-session":
            valid = validate_stored_session(args.state_path)
            print("Session is valid." if valid else "Session is missing or expired.")
            return 0 if valid else 1
        if args.command == "delete-session":
            deleted = delete_storage_state(args.state_path)
            print("Local session state deleted." if deleted else "No local session state existed.")
            return 0
        if args.command == "discard-checkpoint":
            checkpoint = CrawlCheckpoint(default_checkpoint_path(args.term_code), args.term_code)
            print("Crawl checkpoint deleted." if checkpoint.discard() else "No crawl checkpoint existed.")
            return 0
        if args.command == "import-fixtures":
            from drexel_schedule_generator.db.session import session_scope

            from .parser import parse_fixture_directory

            dataset = parse_fixture_directory(args.fixtures.resolve(), term_code=args.term)
            failure = False
            with session_scope() as session:
                try:
                    summary = import_dataset(
                        session,
                        dataset,
                        fixture_name=args.fixtures.resolve().name,
                    )
                except Exception:
                    failure = True
            if failure:
                print("Fixture import failed; previous successful course data was preserved.")
                return 1
            print(
                f"Imported term {summary.term_code}: "
                f"{summary.sections_imported}/{summary.sections_seen} sections, "
                f"{summary.meetings_imported} meetings, "
                f"{summary.sections_skipped} skipped, "
                f"{summary.sections_deactivated} deactivated."
            )
            return 0
        if args.command in {"import-next-term", "import-term"}:
            if args.delay_seconds < 0.5 or args.max_retries < 0 or args.max_retries > 5:
                raise ValueError("Use a delay of at least 0.5 seconds and between 0 and 5 retries.")
            if not validate_stored_session(args.state_path):
                print("The saved session is missing or expired; opening Drexel Connect for authentication.")
                authenticate_interactively(args.state_path)
            requested_code = args.term_code if args.command == "import-term" else None
            with WebTMSBrowserClient(args.state_path, delay_seconds=args.delay_seconds, max_retries=args.max_retries) as client:
                result = crawl_term(
                    client,
                    term_code=requested_code,
                    resume=args.resume,
                    college_filter=args.college,
                    subject_filter=args.subject,
                    progress=print,
                )
            stats = result.stats
            print(f"Selected term: {result.term.name} ({result.term.source_id})")
            print(
                "Pre-import summary: "
                f"{stats.colleges} colleges, {stats.subjects} subjects, "
                f"{stats.sections_discovered} sections discovered, {stats.sections_usable} usable, "
                f"{stats.sections_unusable} unusable, {stats.graduate_skipped} graduate/unsupported, "
                f"{stats.ambiguous_skipped} ambiguous, {stats.malformed_pages} malformed."
            )
            if args.dry_run:
                print("Dry run complete; PostgreSQL was not modified.")
                return 0
            if not result.complete:
                raise ValueError(
                    "The crawl is scoped, partial, or contains malformed pages; refusing database publication."
                )
            from drexel_schedule_generator.db.session import session_scope
            with session_scope() as session:
                summary = import_dataset(
                    session,
                    result.dataset,
                    fixture_name=None,
                    source_name="authenticated_webtms_live",
                )
            print(
                f"Imported {result.term.name} ({summary.term_code}): "
                f"{summary.sections_imported}/{summary.sections_seen} sections, "
                f"{summary.meetings_imported} recurring meetings, "
                f"{summary.sections_deactivated} deactivated; {stats.retries} retries."
            )
            return 0
        with WebTMSBrowserClient(args.state_path) as client:
            if args.command == "inspect":
                urls = args.url or [None]
            else:
                urls = [*args.via, args.url]
            for url in urls:
                snapshot = client.navigate(url)
            sanitized = sanitize_html(snapshot.html)
            if args.command == "inspect":
                print(json.dumps({
                    "url": snapshot.url,
                    **page_structure(sanitized),
                    "webtms_paths": webtms_route_paths(snapshot.html),
                }, indent=2))
            else:
                output = args.output.resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(sanitized, encoding="utf-8")
                print(f"Saved sanitized fixture: {output.name}")
            print("Top-level live requests:")
            for url in client.requested_urls:
                print(f"- {url}")
            return 0
    except AuthenticationRequired as error:
        print(str(error))
        return 2
    except (ValueError, RuntimeError) as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
