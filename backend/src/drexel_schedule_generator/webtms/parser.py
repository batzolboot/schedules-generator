"""Network-independent HTML inspection, sanitization, and row preservation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment

from .records import (
    DiscoveredCollege,
    DiscoveredSection,
    DiscoveredSubject,
    DiscoveredTerm,
    ParsedCourse,
    ParsedFixtureDataset,
    ParsedInstructor,
    ParsedMeeting,
    ParsedSection,
    ParsedTerm,
)

SECRET_NAME = re.compile(r"(csrf|token|secret|session|password|saml)", re.IGNORECASE)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WEBTMS_PATH = re.compile(r"/webtms_du/[A-Za-z0-9_./-]+")
TERM_HEADING = re.compile(r"Schedule for (.+?) \((\d{6})\)")
TIME_RANGE = re.compile(
    r"(?:(Final Exam):\s*)?(\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)",
    re.IGNORECASE,
)
DAY_CODES = {"M": 1, "T": 2, "W": 3, "R": 4, "F": 5, "S": 6, "U": 7}
TERM_PATH = re.compile(r"^/webtms_du/collegesSubjects/(\d{6})$")
COLLEGE_PATH = re.compile(r"^/webtms_du/collegesSubjects/(\d{6})$")
SUBJECT_PATH = re.compile(r"^/webtms_du/courseList/([A-Za-z0-9]+)$")
DETAIL_PATH = re.compile(r"^/webtms_du/courseDetails/(\d+)$")


def _strip_query(value: str) -> str:
    if value.startswith(("http://", "https://")):
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return value.split("?", 1)[0].split("#", 1)[0]


def sanitize_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()
    for node in soup.select("script, noscript, iframe"):
        node.decompose()
    for node in list(soup.find_all(["input", "meta"])):
        attributes = " ".join(str(value) for value in node.attrs.values())
        if SECRET_NAME.search(attributes) or node.get("type") == "hidden":
            node.decompose()
    for node in soup.find_all(True):
        for attribute in tuple(node.attrs):
            if SECRET_NAME.search(attribute) or attribute.lower().startswith("on"):
                del node.attrs[attribute]
        for attribute in ("href", "src", "action"):
            value = node.get(attribute)
            if isinstance(value, str):
                node[attribute] = _strip_query(value)
        identity = " ".join([node.get("id", ""), " ".join(node.get("class", []))])
        if re.search(r"instructor|faculty", identity, re.IGNORECASE):
            node.string = "[REDACTED INSTRUCTOR]"
    for table in soup.find_all("table"):
        instructor_indexes: set[int] = set()
        for row in table.find_all("tr"):
            direct_cells = row.find_all(["th", "td"], recursive=False)
            labels = [cell.get_text(" ", strip=True) for cell in direct_cells]
            found = {
                index
                for index, label in enumerate(labels)
                if re.fullmatch(r"Instructor(?:\(s\))?|Faculty", label, re.IGNORECASE)
            }
            if found:
                if len(direct_cells) == 2 and 0 in found:
                    direct_cells[1].string = "[REDACTED INSTRUCTOR]"
                    instructor_indexes = set()
                    continue
                instructor_indexes = found
                continue
            for index in instructor_indexes:
                if index < len(direct_cells):
                    direct_cells[index].string = "[REDACTED INSTRUCTOR]"
    for value in soup.find_all(string=True):
        if EMAIL.search(value):
            value.replace_with(EMAIL.sub("[REDACTED EMAIL]", value))
    return str(soup)


def table_rows(html: str, *, header_contains: Iterable[str]) -> tuple[dict[str, str], ...]:
    expected = {item.casefold() for item in header_contains}
    soup = BeautifulSoup(html, "html.parser")
    for header_row in soup.find_all("tr"):
        header_cells = header_row.find_all(["th", "td"], recursive=False)
        headers = [cell.get_text(" ", strip=True) for cell in header_cells]
        if not expected.issubset({value.casefold() for value in headers}):
            continue
        rows: list[dict[str, str]] = []
        for row in header_row.find_next_siblings("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != len(headers):
                break
            rows.append({header: cell.get_text(" ", strip=True) for header, cell in zip(headers, cells, strict=True)})
        return tuple(rows)
    return ()


def webtms_route_paths(html: str) -> tuple[str, ...]:
    """Extract only query-free WebTMS-local paths from markup and handlers."""
    return tuple(dict.fromkeys(WEBTMS_PATH.findall(html)))


def page_structure(html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "headings": [node.get_text(" ", strip=True) for node in soup.find_all(re.compile("^h[1-6]$"))],
        "table_headers": [[cell.get_text(" ", strip=True) for cell in table.find_all("th")] for table in soup.find_all("table")],
        "form_methods": [form.get("method", "get").lower() for form in soup.find_all("form")],
        "links": [
            {
                "text": link.get_text(" ", strip=True),
                "path": link.get("href"),
            }
            for link in soup.find_all("a", href=True)
            if link.get_text(" ", strip=True)
        ],
        "forms": [
            {
                "method": form.get("method", "get").lower(),
                "action": form.get("action"),
                "controls": [
                    {"name": control.get("name"), "type": control.name}
                    for control in form.find_all(["select", "button"])
                    if control.get("name")
                ],
            }
            for form in soup.find_all("form")
        ],
    }


def _academic_year(name: str) -> str | None:
    match = re.search(r"\b(\d{2,4})\s*[-\u2013\u2014/]\s*(\d{2,4})\b", name)
    if not match:
        return None
    first, second = match.groups()
    if len(first) == 2:
        first = "20" + first
    if len(second) == 2:
        second = first[:2] + second
    return f"{first}-{second}"


def parse_terms(html: str) -> tuple[DiscoveredTerm, ...]:
    """Parse authenticated term links in source order."""
    soup = BeautifulSoup(html, "html.parser")
    found: list[DiscoveredTerm] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.find_all("a", href=True):
        path = urlsplit(str(link["href"])).path
        match = TERM_PATH.match(path)
        name = link.get_text(" ", strip=True)
        if not match or not name:
            continue
        key = (match.group(1), name.casefold())
        if key in seen:
            continue
        seen.add(key)
        lowered = name.casefold()
        calendar_type = "quarter" if "quarter" in lowered else "semester" if "semester" in lowered else "unknown"
        found.append(DiscoveredTerm(match.group(1), name, calendar_type, _academic_year(name), len(found), path))
    return tuple(found)


def normalize_term_name(value: str) -> str:
    normalized = value.casefold().replace("\u2013", "-").replace("\u2014", "-")
    normalized = re.sub(r"\b(20)?(\d{2})\s*-\s*(20)?(\d{2})\b", lambda m: f"{m.group(2)}-{m.group(4)}", normalized)
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def select_term_by_name(terms: tuple[DiscoveredTerm, ...], target: str) -> DiscoveredTerm:
    wanted = normalize_term_name(target)
    matches = [term for term in terms if normalize_term_name(term.name) == wanted]
    if not matches:
        raise ValueError(f"No authenticated WebTMS term matches {target!r}.")
    if len(matches) != 1:
        raise ValueError(f"Multiple authenticated WebTMS terms match {target!r}.")
    return matches[0]


def parse_colleges(html: str, *, term_code: str) -> tuple[DiscoveredCollege, ...]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, DiscoveredCollege] = {}
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        parts = urlsplit(href)
        if not COLLEGE_PATH.match(parts.path) or not parts.path.endswith(term_code):
            continue
        code = parse_qs(parts.query).get("collCode", [""])[0].strip()
        name = link.get_text(" ", strip=True)
        if code and name:
            found.setdefault(code, DiscoveredCollege(code, name, href))
    return tuple(found.values())


def parse_subjects(html: str, *, college_code: str) -> tuple[DiscoveredSubject, ...]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, DiscoveredSubject] = {}
    for link in soup.find_all("a", href=True):
        path = urlsplit(str(link["href"])).path
        match = SUBJECT_PATH.match(path)
        if not match:
            continue
        code = match.group(1).upper()
        label = link.get_text(" ", strip=True)
        name_match = re.match(r"(.+?)\s*\([A-Za-z0-9]+\)\s*$", label)
        found.setdefault(code, DiscoveredSubject(code, name_match.group(1).strip() if name_match else label, college_code, path))
    return tuple(found.values())


def classify_course_number(value: str) -> str:
    """Conservative fallback: Drexel 100-499 are undergraduate; all else is unsupported/ambiguous."""
    match = re.fullmatch(r"(\d{3})(?:[A-Za-z]*)", value.strip())
    if not match:
        return "ambiguous"
    number = int(match.group(1))
    if 100 <= number <= 499:
        return "undergraduate"
    if number >= 500:
        return "graduate"
    return "ambiguous"


def parse_course_links(html: str) -> tuple[DiscoveredSection, ...]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, DiscoveredSection] = {}
    table = soup.find("table", id="sortableTable")
    if table is None:
        return ()
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 7:
            continue
        link = cells[5].find("a", href=True)
        if link is None:
            continue
        path = urlsplit(str(link["href"])).path
        match = DETAIL_PATH.match(path)
        crn = link.get_text(" ", strip=True)
        if not match or match.group(1) != crn:
            continue
        course_number = cells[1].get_text(" ", strip=True)
        detail_path = f"{path}?crseNumb={course_number}"
        enrollment_source = link.parent.get("title", "") if link.parent else ""
        enrollment_match = re.search(r"Max\s*enroll\s*=\s*(\d+)", str(enrollment_source), re.IGNORECASE)
        item = DiscoveredSection(
            crn, cells[0].get_text(" ", strip=True).upper(), course_number,
            cells[6].get_text(" ", strip=True), detail_path,
            classify_course_number(course_number),
            int(enrollment_match.group(1)) if enrollment_match else None,
        )
        existing = found.get(crn)
        if existing and existing != item:
            raise ValueError(f"Conflicting duplicate CRN {crn} in course list.")
        found[crn] = item
    return tuple(found.values())


def _label_values(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 2:
            label = cells[0].get_text(" ", strip=True)
            if label:
                values.setdefault(label, cells[1].get_text(" ", strip=True))
    return values


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%b %d, %Y").date()
    except ValueError:
        return None


def _parse_days(value: str, start_date: date | None, end_date: date | None) -> frozenset[int]:
    compact = value.strip().upper()
    if compact and all(character in DAY_CODES for character in compact):
        return frozenset(DAY_CODES[character] for character in compact)
    explicit = _parse_date(value)
    if explicit is not None and explicit == start_date == end_date:
        return frozenset({explicit.isoweekday()})
    return frozenset()


def _parse_credits(value: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not value:
        return None, None
    candidates = re.findall(r"\d+(?:\.\d+)?", value)
    try:
        parsed = [Decimal(candidate) for candidate in candidates[:2]]
    except InvalidOperation:
        return None, None
    if len(parsed) == 1:
        return parsed[0], parsed[0]
    if len(parsed) == 2 and parsed[1] >= parsed[0]:
        return parsed[0], parsed[1]
    return None, None


def parse_course_page(html: str) -> tuple[ParsedTerm, ParsedCourse]:
    """Parse one sanitized detail page without network or database access."""
    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text(" ", strip=True)
    heading_match = TERM_HEADING.search(text_content)
    if not heading_match:
        raise ValueError("Course fixture does not contain a recognizable term heading.")
    term_name, term_code = heading_match.groups()
    values = _label_values(soup)
    required = ("CRN", "Subject Code", "Course Number", "Section", "Title", "Instruction Type")
    if any(not values.get(field) for field in required):
        raise ValueError("Course fixture is missing required section fields.")

    meeting_rows = table_rows(
        html,
        header_contains=("Start Date", "End Date", "Times", "Days", "Building", "Room"),
    )
    meetings: list[ParsedMeeting] = []
    skipped_rows = 0
    for row in meeting_rows:
        start_date = _parse_date(row["Start Date"])
        end_date = _parse_date(row["End Date"])
        match = TIME_RANGE.search(row["Times"])
        asynchronous = "asynchronous" in (row["Times"] + row["Days"]).casefold()
        arranged = any(marker in (row["Times"] + row["Days"]).casefold() for marker in ("arranged", "tba"))
        start_time = datetime.strptime(match.group(2).replace(" ", ""), "%I:%M%p").time() if match else None
        end_time = datetime.strptime(match.group(3).replace(" ", ""), "%I:%M%p").time() if match else None
        days = _parse_days(row["Days"], start_date, end_date)
        meeting = ParsedMeeting(
            days=days,
            start_time=start_time,
            end_time=end_time,
            start_date=start_date,
            end_date=end_date,
            building=None if row["Building"].casefold() == "none" else row["Building"] or None,
            room=None if row["Room"].casefold() == "none" else row["Room"] or None,
            meeting_type="exam" if match and match.group(1) else "class",
            is_arranged=arranged,
            is_asynchronous=asynchronous,
        )
        # A one-time final is useful source metadata but is not a weekly recurring block.
        # Preserve explicitly asynchronous rows, but do not import genuinely
        # blank or merely TBA/arranged rows without a usable day/time pattern.
        if (meeting.is_schedulable or meeting.is_asynchronous) and meeting.meeting_type == "class":
            meetings.append(meeting)
        else:
            skipped_rows += 1

    instructor_name = values.get("Instructor(s)")
    instructors = ()
    if instructor_name and instructor_name != "[REDACTED INSTRUCTOR]":
        instructors = (ParsedInstructor(source_id=None, display_name=instructor_name),)
    credits_min, credits_max = _parse_credits(values.get("Credits"))
    description_match = re.search(r"Course Description:\s*(.*?)\s+Credits:", text_content)
    level_text = text_content.casefold()
    undergraduate = "undergraduate quarter" in level_text and not re.search(
        r"\bgraduate quarter\b", level_text
    )
    section = ParsedSection(
        source_id=values["CRN"],
        crn=values["CRN"],
        number=values["Section"],
        component=values["Instruction Type"],
        status="active",
        instructional_method=values.get("Instruction Method"),
        campus=values.get("Campus"),
        instructors=instructors,
        meetings=tuple(meetings),
        notes=values.get("Section Comments"),
        skipped_meeting_rows=skipped_rows,
        maximum_enrollment=int(values["Max Enroll"]) if values.get("Max Enroll", "").isdigit() else None,
    )
    course = ParsedCourse(
        source_id=f"{values['Subject Code']}-{values['Course Number']}",
        subject=values["Subject Code"],
        subject_name=None,
        number=values["Course Number"],
        title=values["Title"],
        description=description_match.group(1).strip() if description_match else None,
        credits_min=credits_min,
        credits_max=credits_max,
        is_undergraduate=undergraduate,
        section=section,
    )
    return ParsedTerm(source_id=term_code, name=term_name), course


def parse_fixture_directory(path: Path, *, term_code: str | None = None) -> ParsedFixtureDataset:
    courses: list[ParsedCourse] = []
    term: ParsedTerm | None = None
    malformed = 0
    for fixture in sorted(path.glob("*.html")):
        html = fixture.read_text(encoding="utf-8")
        if "WebTMS - Course Schedule and Description" not in html:
            continue
        try:
            parsed_term, course = parse_course_page(html)
        except ValueError:
            malformed += 1
            continue
        if term_code and parsed_term.source_id != term_code:
            continue
        if term is not None and term.source_id != parsed_term.source_id:
            raise ValueError("Fixture directory contains more than one term; pass an explicit term.")
        term = parsed_term
        courses.append(course)
    if term is None:
        raise ValueError("No recognizable course-detail fixtures were found.")
    return ParsedFixtureDataset(term=term, courses=tuple(courses), malformed_records=malformed)
