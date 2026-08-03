"""Sequential authenticated WebTMS discovery and normalized crawl staging."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from time import monotonic
from collections.abc import Callable

from .auth import WEBTMS_URL
from .browser_client import WebTMSBrowserClient
from .checkpoint import CrawlCheckpoint, default_checkpoint_path
from .parser import normalize_term_name, parse_colleges, parse_course_links, parse_course_page, parse_subjects, parse_terms, select_term_by_name
from .records import DiscoveredTerm, ParsedFixtureDataset, ParsedTerm

TARGET_TERM_NAME = "Fall Quarter 2026-2027"
TARGET_TERM_START_DATE = date(2026, 9, 22)


@dataclass(slots=True)
class CrawlStats:
    colleges: int = 0
    subjects: int = 0
    courses_discovered: int = 0
    undergraduate_courses: int = 0
    graduate_skipped: int = 0
    ambiguous_skipped: int = 0
    sections_discovered: int = 0
    sections_usable: int = 0
    sections_unusable: int = 0
    recurring_meetings: int = 0
    invalid_meetings: int = 0
    malformed_pages: int = 0
    retries: int = 0
    duration_seconds: float = 0


@dataclass(frozen=True, slots=True)
class CrawlResult:
    term: DiscoveredTerm
    dataset: ParsedFixtureDataset
    stats: CrawlStats
    complete: bool


def resolve_term(html: str, *, term_code: str | None = None) -> DiscoveredTerm:
    terms = parse_terms(html)
    if not terms:
        raise ValueError("The authenticated page is not a recognizable WebTMS term page.")
    if term_code:
        matches = [term for term in terms if term.source_id == term_code]
        if len(matches) != 1:
            raise ValueError(f"Term code {term_code!r} was not uniquely present on the authenticated term page.")
        return matches[0]
    return select_term_by_name(terms, TARGET_TERM_NAME)


def crawl_term(client: WebTMSBrowserClient, *, term_code: str | None = None, delay_checkpoint: Path | None = None,
               resume: bool = False, college_filter: str | None = None, subject_filter: str | None = None,
               progress: Callable[[str], None] | None = None) -> CrawlResult:
    started = monotonic()
    home = client.navigate(WEBTMS_URL)
    selected = resolve_term(home.html, term_code=term_code)
    if selected.calendar_type != "quarter":
        raise ValueError("The selected term is not identified as a quarter term.")
    checkpoint = CrawlCheckpoint(delay_checkpoint or default_checkpoint_path(selected.source_id), selected.source_id, resume=resume)
    term_page = client.navigate(selected.path)
    colleges = list(parse_colleges(term_page.html, term_code=selected.source_id))
    if college_filter:
        colleges = [item for item in colleges if item.code.casefold() == college_filter.casefold()]
    if not colleges:
        raise ValueError("No matching colleges were discovered for the selected term.")
    staged_courses = tuple(checkpoint.courses.values())
    stats = CrawlStats(
        colleges=len(colleges),
        undergraduate_courses=len(staged_courses),
        sections_usable=len(staged_courses),
        recurring_meetings=sum(len(course.section.meetings) for course in staged_courses),
        invalid_meetings=sum(course.section.skipped_meeting_rows for course in staged_courses),
    )
    visited_subjects: set[str] = set()
    seen_crns: dict[str, tuple[str, str]] = {}
    for college_index, college in enumerate(colleges, 1):
        if progress: progress(f"College {college_index}/{len(colleges)}: {college.name}")
        college_page = client.navigate(college.path)
        subjects = parse_subjects(college_page.html, college_code=college.code)
        for subject in subjects:
            if subject.code in visited_subjects or (subject_filter and subject.code.casefold() != subject_filter.casefold()):
                continue
            visited_subjects.add(subject.code)
            stats.subjects += 1
            if progress: progress(f"  Subject {subject.code}: discovering sections")
            course_list = client.navigate(subject.path)
            links = parse_course_links(course_list.html)
            stats.sections_discovered += len(links)
            stats.courses_discovered += len({(link.subject, link.course_number) for link in links})
            for link in links:
                identity = (link.subject, link.course_number)
                previous = seen_crns.get(link.crn)
                if previous and previous != identity:
                    raise ValueError(f"CRN {link.crn} conflicts across course-list pages.")
                seen_crns[link.crn] = identity
                if link.level == "graduate":
                    stats.graduate_skipped += 1
                    checkpoint.completed_crns.add(link.crn)
                    checkpoint.outcomes[link.crn] = "graduate"
                    continue
                if link.level == "ambiguous":
                    stats.ambiguous_skipped += 1
                    checkpoint.completed_crns.add(link.crn)
                    checkpoint.outcomes[link.crn] = "ambiguous"
                    continue
                if link.crn in checkpoint.completed_crns:
                    staged = checkpoint.courses.get(link.crn)
                    if staged and staged.section.maximum_enrollment != link.maximum_enrollment:
                        checkpoint.courses[link.crn] = replace(
                            staged,
                            section=replace(staged.section, maximum_enrollment=link.maximum_enrollment),
                        )
                    if staged:
                        checkpoint.outcomes.setdefault(link.crn, "accepted")
                    outcome = checkpoint.outcomes.get(link.crn)
                    if outcome == "ambiguous":
                        stats.ambiguous_skipped += 1
                    elif link.crn not in checkpoint.courses:
                        stats.sections_unusable += 1
                        checkpoint.outcomes.setdefault(link.crn, "unusable")
                    continue
                try:
                    detail = client.navigate(link.path)
                    parsed_term, course = parse_course_page(detail.html)
                    if parsed_term.source_id != selected.source_id or course.section.crn != link.crn or course.subject != link.subject:
                        raise ValueError("Course detail identity did not match its discovery record.")
                    if not course.is_undergraduate:
                        stats.ambiguous_skipped += 1
                        checkpoint.outcomes[link.crn] = "ambiguous"
                    elif not course.section.meetings:
                        stats.sections_unusable += 1
                        checkpoint.outcomes[link.crn] = "unusable"
                    else:
                        course = replace(
                            course,
                            section=replace(course.section, maximum_enrollment=link.maximum_enrollment),
                        )
                        checkpoint.courses[link.crn] = course
                        checkpoint.outcomes[link.crn] = "accepted"
                        stats.undergraduate_courses += 1
                        stats.sections_usable += 1
                        stats.recurring_meetings += len(course.section.meetings)
                        stats.invalid_meetings += course.section.skipped_meeting_rows
                    checkpoint.completed_crns.add(link.crn)
                    checkpoint.save()
                except ValueError:
                    stats.malformed_pages += 1
                    checkpoint.failures.append(f"CRN {link.crn}: malformed detail page")
                    checkpoint.save()
            checkpoint.save()
    stats.retries = client.retry_count
    stats.duration_seconds = monotonic() - started
    if stats.subjects < 1 or stats.courses_discovered < 1 or stats.sections_usable < 1:
        raise ValueError("Crawl failed structural completeness checks.")
    attempted = stats.sections_usable + stats.sections_unusable + stats.malformed_pages
    if attempted and stats.malformed_pages / attempted > 0.20:
        raise ValueError("Crawl malformed-page rate exceeded the safe threshold.")
    dataset = ParsedFixtureDataset(
        term=ParsedTerm(
            selected.source_id,
            selected.name,
            start_date=TARGET_TERM_START_DATE
            if normalize_term_name(selected.name) == normalize_term_name(TARGET_TERM_NAME)
            else None,
        ),
        courses=tuple(checkpoint.courses.values()),
        malformed_records=stats.malformed_pages,
        courses_seen_override=stats.courses_discovered,
        sections_seen_override=stats.sections_discovered,
        sections_skipped_override=(
            stats.sections_unusable + stats.graduate_skipped + stats.ambiguous_skipped
        ),
    )
    complete = not college_filter and not subject_filter and stats.malformed_pages == 0
    return CrawlResult(selected, dataset, stats, complete=complete)
