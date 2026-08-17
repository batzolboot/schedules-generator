# Drexel Schedule Generator

[![CI](https://github.com/batzolboot/schedules-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/batzolboot/schedules-generator/actions/workflows/ci.yml)

A full-stack schedule-planning application for Drexel students. Search current course offerings, choose acceptable delivery formats, generate conflict-free combinations, compare weekly timetables, and export a preferred schedule—without creating an account.

**[Open the live application](https://schedules-generator.buildproject.workers.dev)**

> This is an independent planning aid, not an official Drexel University service. Course availability and registration details should always be verified in Drexel's official systems.

## Highlights

- Search undergraduate courses by subject, catalog number, or title
- Select up to eight courses and generate conflict-free section combinations
- Handle lecture, lab, recitation, asynchronous, and in-person components
- Choose online or in-person delivery independently for eligible courses
- Filter schedules by Monday–Friday, with Saturday shown only when a selected course offers it
- Restrict class times with an accessible dual-handle time-range slider
- Rank schedules by total gap time and compare up to six options
- Review responsive weekly calendars in light or dark mode
- Export a schedule as an image, PDF, or Outlook-compatible ICS file
- Display course-data freshness and preserve the last successful import

## Architecture

```mermaid
flowchart LR
    Browser["Student browser"] --> Frontend["React + TypeScript\nCloudflare"]
    Frontend -->|"HTTPS / JSON"| API["FastAPI\nGoogle Cloud Run"]
    API --> Database[("PostgreSQL\nNeon")]
    Maintainer["Authorized maintainer"] -->|"Interactive login + MFA"| Importer["WebTMS importer"]
    Importer --> Database
```

The backend is a modular monolith. FastAPI routes handle transport concerns, service modules coordinate application workflows, and the scheduling engine remains independent of FastAPI and SQLAlchemy. The authenticated WebTMS importer is a separate maintainer command and never runs as a permanent API background process.

## Technology

| Area | Technology |
| --- | --- |
| Frontend | React, Vite, TypeScript |
| Frontend testing | Vitest, React Testing Library |
| Backend | FastAPI, Pydantic, Python |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Backend testing | Pytest |
| Local infrastructure | Docker Compose |
| Production | Cloudflare, Google Cloud Run, Neon |
| CI | GitHub Actions |

## How scheduling works

The API resolves each course into its required component groups, consolidates sections with identical recurring meeting patterns, and uses bounded backtracking to build combinations. A partial combination is rejected as soon as its active date ranges, weekdays, and meeting times conflict. Asynchronous sections remain part of the schedule but do not create invented time blocks.

Results are deterministic and include gap-time, start-time, end-time, and campus-day metrics. A 100,000-step exploration guard protects the API from unbounded requests.

## Run locally

### Requirements

- Python 3.12+
- Node.js 24+ and npm 11+
- Docker Desktop with Docker Compose

All commands below are for Windows PowerShell and run from the repository root.

### 1. Install dependencies

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm --prefix frontend ci
```

### 2. Start PostgreSQL

```powershell
$env:POSTGRES_PORT = "5433"
docker compose up -d db
$postgresPort = ((docker compose port db 5432) -split ':')[-1]
$env:DATABASE_URL = "postgresql+psycopg://drexel:local-development-only@127.0.0.1:$postgresPort/drexel_schedule_generator"
```

PostgreSQL binds to `127.0.0.1` only. The password above is exclusively for the local Docker database.

### 3. Create and populate the database

```powershell
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-fixtures
```

The fixture import is deterministic and makes no network requests. To add clearly labeled synthetic demonstration courses:

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.dev.seed_demo
```

### 4. Start the applications

Backend terminal, with `DATABASE_URL` still set:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn drexel_schedule_generator.main:app --reload --app-dir backend\src
```

Frontend terminal:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

Open <http://127.0.0.1:5174>. API documentation is available at <http://127.0.0.1:8000/docs>.

## Configuration

- `backend/.env.example` documents `APP_ENV` and `DATABASE_URL`. The backend reads shell environment variables directly; it does not automatically load a `.env` file.
- `frontend/.env.example` documents `VITE_API_BASE_URL`. Vite supports a local `frontend/.env` file during frontend development.

Real `.env` files, browser storage state, cookies, tokens, and credentials are ignored by Git. Production credentials should be stored in the hosting provider's secret manager, never in this repository.

## Verification

With the local database running and `DATABASE_URL` set:

```powershell
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\python.exe -m pip check

npm --prefix frontend test -- --run
npm --prefix frontend audit --audit-level=moderate
npm --prefix frontend run lint
npm --prefix frontend run build

docker compose config
docker build -f backend\Dockerfile -t drexel-schedule-generator-api:local backend
git diff --check
```

GitHub Actions runs the same critical backend, frontend, migration, and container checks for pushes and pull requests.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/api/v1/terms` | Published academic terms |
| `GET` | `/api/v1/terms/{term_id}/courses` | Course search |
| `GET` | `/api/v1/terms/{term_id}/courses/{course_id}/sections` | Course sections and meetings |
| `GET` | `/api/v1/data-freshness` | Last successful imports |
| `POST` | `/api/v1/schedules/generate` | Conflict-free schedule generation |

Interactive OpenAPI documentation is exposed at `/docs` by FastAPI.

## Course-data maintenance

Routine development and automated tests use saved sanitized fixtures. Live WebTMS access is explicit and infrequent. An authorized maintainer authenticates in a visible Playwright browser, enters credentials directly on Drexel's page, and completes MFA normally. The application never reads or autofills the password.

```powershell
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands authenticate
backend\.venv\Scripts\python.exe -m drexel_schedule_generator.webtms.commands import-next-term
```

Private browser state and resumable checkpoints remain under the ignored `.private/webtms/` directory. Failed or incomplete imports do not deactivate sections or replace the last successfully published dataset.

## Project documentation

- [Product requirements](docs/PRODUCT_REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development plan](docs/DEVELOPMENT_PLAN.md)
- [WebTMS source investigation](docs/WEBTMS_DATA_SOURCE.md)
- [WebTMS field mapping](docs/WEBTMS_FIELD_MAPPING.md)
- [Authenticated client design](docs/WEBTMS_AUTHENTICATED_CLIENT.md)

## Current limitations

- Supports Drexel undergraduate course planning for one term at a time
- Accepts at most eight selected courses per request
- Depends on periodic maintainer-run WebTMS imports rather than real-time registration data
- Does not validate prerequisites, degree requirements, seats, or registration eligibility
- Component-link information is limited when WebTMS does not publish an authoritative relationship
- Sections without a usable timed meeting or an explicit asynchronous meeting are excluded
- No accounts, cloud-saved schedules, notifications, ratings, or AI recommendations

## Privacy

The student-facing application requires no account and collects no Drexel credentials. Generated schedules are computed from the request and are not saved as user records. Maintainer authentication state is local, private, and separate from the public API.
