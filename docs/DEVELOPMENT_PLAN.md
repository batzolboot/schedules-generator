# Drexel Schedule Generator — Development Plan

## 1. Delivery principles

- Build a narrow anonymous planning workflow before expanding features.
- Prove domain correctness with saved fixtures before integrating the live source.
- Complete and verify the application locally before doing deployment work.
- Keep the backend a modular monolith and add infrastructure only in response to measured needs.
- Treat each phase as a scope gate: unfinished acceptance criteria block work that depends on them.
- Prefer a polished, tested primary journey over a large feature count.

## 2. Phase overview

| Phase | Outcome |
| --- | --- |
| Phase 1 | Local foundation and end-to-end course discovery using fixtures |
| Phase 2 | Correct, bounded scheduling engine and generation API |
| Phase 3 | Complete local schedule-planning user experience |
| Phase 4 | Production-shaped importer and ICS export, still verified locally |
| Phase 5 | Local hardening and portfolio polish |
| Phase 6 | Deployment and CI/CD deployment automation, only after local approval |

## 3. Phase 1 — Foundation and domain proof

### Goal

Establish a reproducible repository and prove the term → search → course detail flow against representative saved data. Schedule generation is not part of this phase.

### Work

#### Data discovery

- Identify the intended Drexel data source without building repeated live access into development.
- Confirm that use, storage, and redistribution are permitted.
- Capture a small, sanitized, representative fixture set.
- Document observed fields, component types, relationship rules, missing values, and time formats.
- Include at least one synthetic fixture set that is safe to commit and stable for tests.

#### Repository foundation

- Establish the frontend and backend directories in the approved monorepo structure.
- Configure React, Vite, TypeScript, FastAPI, and Python packaging.
- Configure formatting, linting, and type checking.
- Provide `.env.example` and a concise local setup guide.
- Add Docker Compose for local services.

#### Persistence

- Start PostgreSQL locally through Docker Compose.
- Define the Phase 1 SQLAlchemy models.
- Create the first Alembic migration.
- Add an importer entry point that loads saved fixtures.
- Make fixture loading deterministic and repeatable.

#### Backend discovery API

- Add health/readiness behavior.
- List available terms.
- Search courses within one term.
- Retrieve course details with sections, components, instructors, and meetings.
- Retrieve last-successful-import freshness information.
- Return validated, documented response schemas.

#### Frontend discovery flow

- Select a term.
- Search courses by code or title.
- View course and section details.
- Display data freshness and the official-source disclaimer.
- Handle loading, empty, invalid, and failed-request states.

#### Testing and CI

- Add backend unit, repository, migration, importer-fixture, and API tests appropriate to Phase 1.
- Add frontend interaction tests for term selection and course search.
- Add GitHub Actions for formatting, linting, type checking, tests, and builds.
- CI must not access the live course-data source.

### Definition of done

Phase 1 is complete only when all of the following are true:

#### Product behavior

- A user can open the frontend locally.
- The frontend retrieves available fixture terms from the backend.
- The user can select a term, search by course code or title, and inspect a course's sections and meetings.
- The interface displays the dataset's last successful update time.
- Loading, no-results, unavailable-data, and API-error states are understandable and recoverable where possible.

#### Data and backend

- PostgreSQL starts through Docker Compose.
- Alembic creates the approved Phase 1 schema from an empty database.
- A documented command loads deterministic saved fixtures without network access.
- Fixtures include at least:
  - Two subjects
  - Multiple courses and sections
  - A lecture plus lab or recitation example
  - A section meeting on multiple weekdays
  - An online, asynchronous, or arranged section
- Health, terms, course search, course detail, and freshness APIs work and have validated schemas.
- Search is scoped by term and uses parameterized SQLAlchemy queries.
- Generated OpenAPI documentation accurately represents these APIs.

#### Quality

- Backend formatting, linting, type checking, and tests pass.
- Frontend formatting, linting, type checking, tests, and production build pass.
- API integration tests run against a test PostgreSQL database.
- Importer tests read saved fixtures and perform no live requests.
- At least one frontend test covers the term-selection and course-search flow.
- No secrets or machine-specific settings are committed.
- A clean checkout can be started using the documented commands.

#### Documentation and scope

- The README explains purpose, scope, stack, setup, test commands, and known limitations.
- Architecture and data assumptions reflect the implementation.
- Schedule generation remains explicitly deferred to Phase 2.
- No deployment resources or deployment workflows have been created.

### Phase 1 approval gate

Before Phase 2, review the local discovery flow and confirm that the data model accurately represents representative Drexel sections and component relationships.

## 4. Phase 2 — Scheduling engine

### Goal

Implement and prove scheduling correctness independently of a polished results interface.

### Work

- Define generation request and response schemas.
- Resolve required components and valid linked-section combinations.
- Implement date-aware meeting interval overlap detection.
- Implement bounded backtracking with early conflict rejection.
- Apply excluded-day and earliest/latest-time hard filters before expansion.
- Calculate campus-day, gap, start-time, and end-time metrics.
- Implement deterministic default ranking and approved predefined alternatives.
- Add selected-course, search-space, and result limits.
- Return truncation metadata and structured no-result reasons.
- Expose generation through the API.

### Required tests

- Exact overlap, partial overlap, containment, and adjacent meetings
- Same time on different weekdays
- Same weekday/time with non-overlapping date ranges
- Multiple meeting patterns per section
- Valid and invalid lecture/lab or lecture/recitation relationships
- Asynchronous and arranged meetings
- Hard day/time filters
- Deterministic ranking and tie-breaking
- Result and exploration limits
- Invalid or cross-term section identifiers

### Exit criteria

- Representative fixture requests produce only valid combinations.
- Domain tests cover documented scheduling semantics.
- Typical fixture benchmarks complete within the agreed local response target.
- Limits prevent unbounded work and are visible to API consumers.
- No worker queue, cache, or deployment dependency is required.

## 5. Phase 3 — Complete local planning experience

### Goal

Deliver the full anonymous planning workflow in the browser.

### Work

- Add and remove courses in a temporary planner.
- Display required components and allow acceptable-section selection.
- Add excluded-day and earliest/latest-time controls.
- Add the approved predefined ranking choices.
- Request and display generated schedules.
- Build an accessible weekly calendar plus textual schedule list.
- Support previous/next result navigation and result counts.
- Explain no-result cases and suggest which constraints to relax.
- Show truncation and arranged-meeting warnings.
- Persist anonymous planner state using the approved local-storage/URL policy.
- Polish responsive behavior and keyboard interaction.

### Exit criteria

- A user can complete the full term-to-calendar workflow locally.
- Core interactions have React Testing Library coverage.
- The calendar is usable without relying on color alone and has a textual equivalent.
- Refresh behavior matches the approved planner-state policy.
- No accounts, notifications, ratings, or AI features exist.

## 6. Phase 4 — Import reliability and ICS export

### Goal

Finish the data-update and calendar-export capabilities while keeping development deterministic and local.

### Work

#### Importer

- Finalize the source-adapter interface.
- Implement validation and the chosen atomic publication strategy.
- Retain the last known-good dataset after failures.
- Record import status, timestamps, counts, warnings, and errors.
- Add an explicit manual command for approved live-source access.
- Add safeguards that prevent routine tests and application startup from accessing the live source.
- Expand saved fixtures for edge cases discovered during controlled source validation.

#### ICS

- Generate recurring ICS events for timed meetings.
- Use term date ranges and the `America/New_York` time zone.
- Include course, component, section, and location metadata.
- Apply the approved arranged-meeting policy.
- Omit fabricated events for asynchronous meetings.
- Test generated calendars with an independent ICS parser and representative calendar clients.

### Exit criteria

- Failed imports cannot replace a published valid dataset.
- Importer tests are deterministic and network-free.
- Live access is opt-in, documented, and used sparingly.
- ICS output passes structural tests and manual import checks.
- The interface accurately reports freshness and export limitations.

## 7. Phase 5 — Local hardening and portfolio polish

### Goal

Make the locally running application reliable, understandable, and presentation-ready before approving deployment.

### Work

- Measure and improve course-search and generation performance where necessary.
- Conduct keyboard, screen-reader, responsive-layout, and cross-browser checks.
- Add a small number of end-to-end critical-path tests if approved.
- Improve structured local logging and error messages.
- Verify clean-database migrations and fixture loading.
- Document architecture decisions and important tradeoffs.
- Provide screenshots or a short demo walkthrough.
- Review dependencies, secrets handling, and source-data licensing constraints.
- Run the complete workflow from a clean checkout.

### Local application acceptance gate

Deployment work may begin only after the user approves a demonstration showing:

1. Local installation from documented steps
2. Fixture import with no live-source request
3. Term selection and course search
4. Component-aware course selection
5. Conflict-free generation with filters and ranking
6. Accessible weekly-calendar review
7. Successful ICS export
8. Accurate freshness and limitation messaging
9. Passing automated checks

## 8. Phase 6 — Deployment, deferred until approved

### Goal

Deploy the already-working application without changing its core architecture.

This phase must not start until the Phase 5 local acceptance gate is approved.

Anticipated work, subject to a separate deployment plan and approval:

- Select static frontend hosting.
- Provision managed PostgreSQL.
- Deploy FastAPI to Google Cloud Run.
- Package the importer as a separate Cloud Run Job.
- Configure secrets, database connectivity, and migration execution.
- Add deployment environments and rollback procedures.
- Extend GitHub Actions from CI to approved CD workflows.
- Add production health checks, logs, and basic monitoring.
- Perform a controlled first data update and smoke test.

No cloud resources or deployment configuration are included in Phases 1–5.

## 9. Features postponed beyond the MVP

- Accounts and authentication
- Notifications or availability alerts
- Instructor ratings
- AI recommendations
- Direct registration
- Degree and prerequisite planning
- Third-party calendar ingestion
- Travel-time optimization
- Arbitrary weighted scoring
- Collaboration and sharing
- Multi-institution support
- Native mobile applications

Adding any of these requires a separately approved scope change.

## 10. Decisions requiring approval

### Needed before or during Phase 1

1. The permitted course-data source and what source-derived fixture data may be committed.
2. Whether Phase 1 uses only synthetic fixtures initially or also includes a sanitized real-data sample.
3. The Python and Node.js version policy once the initial toolchain is selected.

### Needed before Phase 3

4. The predefined ranking modes beyond the default.
5. Whether planner state is stored in local storage, encoded in a URL, or both.
6. The weekly-calendar implementation after an accessibility-focused comparison.

### Needed before Phase 4

7. The treatment of arranged meetings in ICS exports.
8. Whether potentially stale seat availability is shown in the MVP.

### Needed before Phase 6

9. Explicit approval that the application meets the local acceptance gate.
10. Frontend host, cloud budget, environments, domain, and operational expectations.

## 11. Scope-control checklist

Before adding work to an active phase, ask:

- Is it required for that phase's exit criteria?
- Does it improve correctness or the primary anonymous planning journey?
- Can it be deferred without invalidating existing work?
- Does it introduce a new service, external dependency, or ongoing operational burden?
- Has any necessary product decision been approved?

If it is not required for the current exit criteria, place it in a later phase or the postponed-features list.

