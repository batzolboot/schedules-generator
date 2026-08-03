# Drexel Schedule Generator

A local, anonymous schedule-planning portfolio application. It imports sanitized saved WebTMS fixtures into PostgreSQL, searches undergraduate courses, generates conflict-free lecture/lab combinations, ranks results, and renders a weekly calendar. It is a planning aid; Drexel's official registration system remains authoritative.

The local demo never requires a live WebTMS login. Authentication state under `.private/` is unrelated to the API and is never read by fixture import, tests, or the frontend.

## Prerequisites

- Node.js 24+ and npm 11+
- Python 3.12+
- Docker Desktop with Docker Compose

Run all commands below from the repository root in Windows PowerShell.

## 1. Install dependencies

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm --prefix frontend install
```

Playwright Chromium is only needed for an explicitly authorized live maintenance session, not the local demo.

## 2. Start PostgreSQL and detect its host port

Another local project may own port 5432. Compose can use an alternate port, for example:

```powershell
$env:POSTGRES_PORT = "5433"
docker compose up -d db
docker compose ps
$postgresPort = ((docker compose port db 5432) -split ':')[-1]
$env:DATABASE_URL = "postgresql+psycopg://drexel:local-development-only@127.0.0.1:$postgresPort/drexel_schedule_generator"
```

Keep `DATABASE_URL` set in every backend terminal. PostgreSQL is bound only to `127.0.0.1` for local development.

## 3. Apply migrations and import fixtures

```powershell
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-fixtures
```

`import-fixtures` is deterministic and network-free. It imports the sanitized Summer Quarter 25-26 WebTMS fixtures. The graduate asynchronous example is intentionally skipped because the MVP supports undergraduate courses with usable timed meetings only.

For a richer multi-course local demonstration, run the separate seed command:

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.dev.seed_demo
```

Courses under subject `DEMO` are explicitly synthetic and are not presented as Drexel source data.

## 4. Start FastAPI

In a backend terminal with `DATABASE_URL` set:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn drexel_schedule_generator.main:app --reload --app-dir backend\src
```

Open <http://127.0.0.1:8000/health> or <http://127.0.0.1:8000/docs>.

## 5. Start React

In another terminal:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

Open <http://127.0.0.1:5174>. Port 5174 is used to avoid a common local conflict on 5173.

## Local demo flow

1. Select **Summer Quarter 25-26**.
2. Search for `CS 172` and add the real sanitized course.
3. If the demo seed was run, search for `DEMO`, then add one or both clearly synthetic courses.
4. Generate schedules.
5. Review the ranked calendar, section list, metrics, freshness timestamp, and component-compatibility notice.

The importer permits lecture/lab combinations across component groups when authoritative compatibility mappings are unavailable. Always verify a result in Drexel's official system.

## Verification commands

```powershell
$postgresPort = ((docker compose port db 5432) -split ':')[-1]
$env:DATABASE_URL = "postgresql+psycopg://drexel:local-development-only@127.0.0.1:$postgresPort/drexel_schedule_generator"

backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\python.exe -m pip check
backend\.venv\Scripts\python.exe -m compileall -q backend\src backend\tests

npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
docker compose config
```

## API endpoints

- `GET /health`
- `GET /api/v1/terms`
- `GET /api/v1/terms/{term_id}/courses`
- `GET /api/v1/terms/{term_id}/courses/{course_id}/sections`
- `GET /api/v1/data-freshness`
- `POST /api/v1/schedules/generate`

## Current limitations

- Undergraduate courses only
- Saved sanitized fixtures or explicit synthetic demo data; no automatic live updates
- No accounts, notifications, ratings, AI, deployment, or background updater
- No authoritative component compatibility mapping in the current source sample
- Sections without at least one usable timed meeting are excluded
- Schedule generation accepts up to eight courses and returns every distinct meeting-time combination found before the 100,000-step exploration guard
- Same-course sections with identical component and recurring meeting patterns are consolidated before generation
- Image and PDF exports capture the styled timetable; Outlook calendar export uses ICS

## Refresh authenticated WebTMS data

The maintainer enters credentials only in a visible Drexel Connect browser and
approves MFA normally. Session and checkpoint files stay under the ignored
`.private/webtms/` directory.

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands authenticate
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term
```

Resume an interruption or select a verified term explicitly:

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term --resume
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-term --term-code 202615 --resume
```

Remove only synthetic development courses:

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.dev.seed_demo --remove
```
