# --- Builder: resolve and install dependencies with uv ----------------------
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Runtime -----------------------------------------------------------------
FROM python:3.13-slim

RUN groupadd -r taskhub && useradd -r -g taskhub taskhub

WORKDIR /srv
COPY --from=builder /srv/.venv .venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1

RUN mkdir -p /srv/uploads && chown -R taskhub:taskhub /srv/uploads
USER taskhub

EXPOSE 8000

# Compose/Kubernetes override the command to run migrations first.
# Worker count: match to available CPU cores in your deployment.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
