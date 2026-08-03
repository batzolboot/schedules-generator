# Authenticated WebTMS Client

## Security boundary

The maintainer authenticates in a visible Playwright Chromium window directly on Drexel Connect and completes MFA normally. The application does not locate, read, autofill, or log credential fields. After WebTMS loads, Playwright storage state is saved to `.private/webtms/storage-state.json`. The whole `.private/` tree is Git-ignored; repository-local state paths are rejected unless Git confirms they are ignored. Restrictive directory and file modes are requested where the operating system supports them.

Storage state is an authentication secret. Never copy it into fixtures, logs, issues, CI, cloud storage, or a deployment image. Use `delete-session` when the session is no longer needed.

## Maintainer commands

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands authenticate
.\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands validate-session
.\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands inspect
.\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands delete-session
```

`authenticate` is the only command that opens a visible browser. A redirect to `connect.drexel.edu` during validation or navigation is treated as an expired session, and collection stops without exposing redirect parameters.

## Module boundaries

- `auth.py`: interactive login, ignored-path enforcement, state lifecycle, and validation.
- `browser_client.py`: authenticated, host-restricted navigation with request delays.
- `records.py`: immutable source records with no SQLAlchemy dependency.
- `parser.py`: network-independent sanitization and parsing; every table row is returned.
- `commands.py`: maintainer entry points.
- `importer.py`: intentionally absent until the database-write phase.

## Investigation status

Phase 3A established that direct HTTP is redirected to Drexel Connect. The authorized Phase 3B pass confirmed this application flow:

```text
GET /webtms_du/
GET /webtms_du/collegesSubjects/{termCode}
GET /webtms_du/collegesSubjects/{termCode}?collCode={collegeCode}
GET /webtms_du/courseList/{subjectCode}
GET /webtms_du/courseDetails/{crn}?crseNumb={courseNumber}
```

Term and college selection establish server-side navigation context, so a client must retain the same browser context through course navigation. Query strings are required for college and course-detail navigation but are deliberately omitted from request logs.

The home page contains quarter and semester term links. The investigated term was Summer Quarter 25-26 (`202545`), college code `CI`, and subject `CS`. A course list is one table with one row per section and columns for subject, course number, instruction type/method, section, CRN, title, combined days/time, and instructor. Course details are separate requests keyed by CRN plus course number.

The detail page uses label/value rows for CRN, subject, course number, section, credits, title, campus, instructor, instruction type, instruction method, enrollment, comments, and textbooks. Its meeting table columns are `Start Date`, `End Date`, `Times`, `Days`, `Building`, and `Room`. CS 172 lecture contains an ordinary class row and a one-time final-exam row; the parser recognizes both source rows but excludes the final from recurring schedule meetings. Online-asynchronous CS 504 uses real start/end dates, `Asynchronous` in both time and day cells, and `None` for building and room.

The page header displayed `Last Updated: August 1, 09:00 pm` without a year or timezone. The detail page also exposes description, college, department, restrictions, prerequisites, co-requisites, cross-listed/also-meets-with text, repeat status, and offering history. These are useful evidence but not all belong in the MVP schema.

Component compatibility is only partly explicit. CS 172 lecture comments say `Also register for a lab & EXAM 080`; the lab detail does not provide a machine-readable compatibility set. This text proves a requirement exists but is not sufficient to infer every allowed lecture/lab pairing.

## Complete-term crawler

The crawler resolves terms from the authenticated live term list, retains one
browser context through college and subject navigation, and stages normalized
records under ignored `.private/webtms/crawls/` files. It never stores protected
HTML in a checkpoint. Fall Quarter 2026-2027 was verified live as `Fall Quarter
26-27`, source term code `202615`, on August 2, 2026.

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term --resume
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-term --term-code 202615
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term --dry-run
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands discard-checkpoint --term-code 202615
```

Defaults are a two-second sequential delay and two bounded retries. HTTP 429
responses trigger exponential slowdown. Authentication redirects stop without
import or deactivation. A complete crawl is validated before one transactional
upsert and same-term-only deactivation.

Where explicit level data is unavailable, numeric 100-499 course numbers are
conservative undergraduate candidates, 500 and above are graduate/unsupported,
and nonstandard or lower numbers are ambiguous. Detail-level metadata remains
authoritative. Final-exam rows are counted as skipped source rows but excluded
from recurring meetings and weekly schedule generation.
