# AGENTS.md

## Project scope

Build the Drexel Schedule Generator according to `docs/PRODUCT_REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, and `docs/DEVELOPMENT_PLAN.md`. Keep the MVP manageable for one developer and working locally before beginning deployment work. Routine development and importer tests must use saved fixtures; live-source access must be explicit and infrequent.

## Architecture

- Keep FastAPI routes thin: validate transport input, call services, and map responses.
- Put business logic in service modules.
- Keep the scheduling algorithm independent from FastAPI and SQLAlchemy so it can be tested as pure domain logic.
- Keep the course importer separate from the web API; do not expose importing as a public API route.
- Keep frontend API requests in a dedicated API module.
- Use Alembic for every database schema change.
- Do not run a permanent background loop inside the API service.
- Preserve the modular-monolith boundaries described in the architecture document.
- Do not add accounts, notifications, instructor ratings, or AI recommendations to the MVP.
- Do not begin deployment work until the local application acceptance gate is approved.

## Working behavior

- Inspect relevant files before modifying them.
- Make focused changes and do not rewrite unrelated files.
- Do not add dependencies without explaining why they are needed.
- Do not change an API contract silently; update consumers, tests, and documentation, and report the change.
- Do not commit unless explicitly instructed.
- Never include secrets or `.env` files in Git. Commit only safe examples such as `.env.example`.
- Warn before running destructive commands and confirm the exact target.
- Preserve user changes and avoid destructive Git operations.

## Testing and verification

- Add deterministic tests for scheduling rules and every bug fix.
- Use saved, permitted fixtures for importer tests; automated tests must not call the live source.
- Run the relevant tests, linters, and type checks after changes.
- Run the frontend production build after frontend work.
- Do not claim a task works without running its verification commands.
- If verification cannot run, state exactly what was not run and why.

## Completion report

Every implementation handoff must include:

- Changed files
- Commands run
- Test, type-check, lint, and build results as applicable
- Remaining limitations, risks, or unverified behavior

