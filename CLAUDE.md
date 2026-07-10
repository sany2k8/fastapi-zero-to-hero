# CLAUDE.md

Production-style FastAPI REST API ("TaskHub"): users → projects → tasks →
attachments, with JWT auth and RBAC. Managed with **uv**.

## Commands

```bash
uv sync                                        # install (incl. dev deps)
uv run pytest                                  # run tests (in-memory SQLite, no services needed)
uv run pytest tests/test_tasks.py -k upload    # single test
uv run ruff check .                            # lint
uv run alembic upgrade head                    # apply migrations (SQLite ./taskhub.db by default)
uv run alembic revision --autogenerate -m "…"  # new migration after model changes
uv run uvicorn app.main:app --reload           # dev server on :8000 (docs at /docs)
```

Docker: `SECRET_KEY=… docker compose up --build` (Postgres + migrations + JSON logs).

## Architecture (strict layering)

route (`app/api/v1/routes/`) → service (`app/services/`) → repository
(`app/repositories/`) → model (`app/models/`).

- **Routes** never touch the DB session; they call services and declare
  Pydantic response models. Register new routers in `app/api/v1/router.py`.
- **Services** own business rules, ownership/RBAC checks, and **commits**.
  They raise domain exceptions from `app/core/exceptions.py`
  (NotFoundError/ConflictError/…) — global handlers render the standard
  `{"error": {code, message, details}, "request_id"}` envelope. Never raise
  bare HTTPException in services.
- **Repositories** extend `BaseRepository` (`list_paginated` = filter +
  search + sort + count; soft-deleted rows excluded by default).
- **Models** compose mixins from `app/models/mixins.py` (UUID PK, timestamps,
  audit, soft delete). New models must be imported in `app/models/__init__.py`
  or Alembic autogenerate won't see them.

Dependencies (DB session, current user, `require_roles`, pagination, service
factories) all live in `app/api/deps.py`. Configuration is env-driven via
`app/core/config.py` (`get_settings()` is cached — tests set env vars *before*
importing app modules; see `tests/conftest.py`).

## Gotchas

- After changing models: generate a migration AND run `uv run alembic upgrade head`.
- List-endpoint sort fields are whitelisted twice: the `Query(pattern=…)` in
  the route and `SORT_FIELDS` in the repository — keep them in sync.
- Rate limiter and metrics are in-process singletons (fine for one worker;
  see README for the scale-out story).
