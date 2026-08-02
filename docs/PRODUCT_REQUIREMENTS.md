# Drexel Schedule Generator — Product Requirements

## 1. Purpose

The Drexel Schedule Generator is a portfolio-quality web application that helps Drexel students explore course-section combinations and produce conflict-free weekly schedules. It is a planning aid, not an official registration system. Drexel's official registration information remains authoritative.

The MVP should demonstrate a complete, dependable anonymous planning workflow while remaining achievable for one student developer.

## 2. Product goals

- Make it easy to find courses offered in a selected academic term.
- Correctly represent lecture, lab, recitation, and other required components.
- Generate valid section combinations without meeting-time conflicts.
- Let students narrow and rank results using a small set of useful preferences.
- Present each result clearly on a weekly calendar.
- Export a chosen schedule to an ICS calendar file.
- Communicate when the underlying course data was last updated.
- Demonstrate thoughtful product design, testing, and engineering in a portfolio project.

## 3. Non-goals for the MVP

The MVP will not include:

- User accounts, authentication, or cloud-saved schedules
- Notifications, alerts, or messaging
- Instructor ratings or third-party review data
- AI recommendations or natural-language schedule generation
- Direct course registration or Drexel account integration
- Degree audits, prerequisite validation, or major planning
- Seat-availability prediction or real-time enrollment guarantees
- Multiple institutions
- Collaboration or schedule sharing
- Native mobile applications

Planner state may be retained locally in the browser or represented in the URL, but it will not be associated with an account.

## 4. Target user and primary journey

The initial user is a Drexel student planning classes for one academic term.

The primary journey is:

1. The student opens the application and sees the available academic terms and data freshness.
2. The student selects a term.
3. The student searches for and adds courses.
4. The student reviews required component types and chooses acceptable sections.
5. The student optionally excludes days or restricts acceptable start and end times.
6. The application generates conflict-free schedules.
7. The student reviews schedules ordered by practical ranking criteria.
8. The student views a chosen result on a weekly calendar.
9. The student exports that result as an ICS file if desired.

## 5. MVP functional requirements

### 5.1 Academic terms and data freshness

- The application must list every published term available in the local database.
- The user must select one term before searching or generating schedules.
- The interface must display when the selected term's data was last successfully updated.
- The application must distinguish a successful published import from a failed or incomplete import.
- The interface must state that course data may be stale and that official registration data is authoritative.

### 5.2 Course search and details

- A user must be able to search within the selected term by subject/course number, title, or keyword.
- Search results must show enough information to distinguish courses, including subject, number, and title.
- Course details must expose available sections and their known metadata, including:
  - CRN or equivalent external identifier
  - Section code
  - Component type
  - Instructor, when available
  - Campus or delivery method, when available
  - Meeting days, times, date range, and location, when available
  - Canceled, online, asynchronous, or arranged status, when applicable
- Empty and no-result states must explain what the user can do next.

### 5.3 Course and section selection

- The user must be able to add and remove courses from a temporary planning workspace.
- The application must show the component types required for each selected course.
- The user must be able to include or exclude acceptable sections for each component.
- All eligible sections should initially be accepted unless doing so would be misleading.
- The application must not silently combine sections that are known to be incompatible.
- When component relationships cannot be determined reliably, the application must communicate the limitation and avoid claiming that an uncertain combination is registerable.

### 5.4 Schedule generation

- A generated schedule must contain one valid selection for every required component of every chosen course.
- A generated schedule must not contain overlapping timed meetings.
- Conflict checks must account for sections with multiple meeting patterns and date ranges.
- Asynchronous meetings must not create artificial time conflicts.
- Arranged meetings must be identified in results and must not be treated as confirmed conflict-free time blocks.
- The generation request must support these hard filters:
  - Excluded weekdays
  - Earliest acceptable start time
  - Latest acceptable end time
- The service must enforce reasonable input and result limits.
- If results are truncated, the response and interface must say so.
- If no schedules are possible, the interface must provide a useful explanation rather than a generic failure.

### 5.5 Ranking

- Valid schedules must be ranked deterministically.
- The MVP must calculate at least:
  - Number of days with in-person timed meetings
  - Total gap time between meetings
  - Earliest daily start
  - Latest daily end
- The default ranking must prefer fewer campus days, then less total gap time.
- The user must be able to choose from a small, predefined set of ranking priorities rather than configure arbitrary scoring weights.

### 5.6 Schedule display

- Each result must be viewable on a weekly calendar.
- Calendar entries must identify the course, section/component, and meeting time.
- The result view must also provide a compact textual list of selected sections.
- The user must be able to move between generated results.
- The calendar must remain usable on common desktop and mobile viewport sizes.
- Meaning must not be conveyed by color alone.

### 5.7 ICS export

- The user must be able to download an ICS file for one selected schedule.
- Timed recurring meetings must use the selected term's dates and the `America/New_York` time zone.
- Asynchronous meetings must not be exported as invented timed events.
- Arranged meetings must either be omitted with a warning or represented without a fabricated time; the final behavior requires product approval.
- Exported events must include identifying course and section information.

### 5.8 Local data updates

- Course data must be imported by a separate updater command/process that reuses backend domain and persistence code.
- Development and automated tests must use saved fixtures instead of repeatedly requesting the live data source.
- A live-source import must be an explicit manual action during local development.
- A failed import must not replace the last known-good published dataset.
- Import history must record status, timestamps, record counts, and a useful error summary.

## 6. Quality requirements

### Correctness

- Scheduling behavior must be covered by deterministic unit tests, including overlaps, adjacent classes, multiple meeting days, date ranges, component relationships, asynchronous sections, and arranged sections.
- Import normalization must be tested using committed, sanitized fixtures whose use is permitted.
- API behavior must be covered by integration tests against a test database.

### Performance

- Course search should feel immediate for a term-sized local dataset.
- Typical schedule-generation requests should return within a few seconds in local development.
- Generation must prune invalid partial combinations and stop at configured limits rather than exhaustively materialize an unbounded result set.

### Accessibility and usability

- Core workflows must be operable by keyboard.
- Interactive controls must have accessible names and visible focus states.
- Calendar information must have a usable non-visual/textual representation.
- Errors must explain recovery steps when possible.

### Security and privacy

- The MVP must collect no account credentials or personal profile data.
- All query inputs must be validated and database queries parameterized through SQLAlchemy.
- Secrets must not be committed to the repository.
- Source data must not be retained or redistributed beyond what its terms permit.

### Reliability

- Local services must start through documented Docker Compose commands.
- Database schema changes must be managed by Alembic.
- The last successful dataset must remain available after a failed importer run.

## 7. MVP success criteria

The MVP succeeds when a new user can complete the term → course search → section selection → schedule generation → calendar review → ICS export workflow locally using representative data, with clear freshness information and without needing an account.

The result must be credible as a portfolio project: reproducible setup, automated critical-path tests, documented tradeoffs, and a polished primary workflow are more important than a broad feature count.

## 8. Constraints and assumptions

- The application will be developed and proven locally before any deployment work begins.
- The architecture may anticipate Cloud Run and PostgreSQL hosting, but no cloud resources, deployment workflows, or production infrastructure will be implemented until the local application works end to end.
- The availability, permitted use, and structure of the Drexel course-data source must be validated before production importer work.
- Development should continue to work with saved fixtures if the live source is unavailable.
- The first release supports Drexel only and plans one term at a time.

## 9. Open product decisions

The following decisions still require approval before their associated feature is finalized:

1. Whether seat availability should be shown in the MVP when the data is available but may be stale.
2. Whether arranged meetings should be omitted from ICS export with a warning or exported as untimed informational entries.
3. Which predefined alternate ranking choices should accompany the default of fewer campus days followed by shorter gaps.
4. Whether anonymous planner state should use browser local storage, a shareable URL, or both.

