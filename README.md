# TaskHub API — FastAPI zero to hero

A production-style task management REST API that demonstrates most of FastAPI's
feature surface in a realistic, layered architecture. Users register and log in,
create **projects**, fill them with **tasks**, and attach **files** to tasks.
Admins manage users; members only ever see their own data.

## Stack

· FastAPI 
· SQLAlchemy 2.0 (async) 
· Alembic 
· Pydantic v2 + pydantic-settings 
· PyJWT + Argon2 (pwdlib) 
· structlog 
· pytest + httpx 
· uv 
· Docker/Postgres


## Project Structure

```
fastapi-zero-to-hero
├── Dockerfile
├── README.md
├── alembic
├── alembic.ini
├── api-documentation.png
├── app
├── docker-compose.yml
├── pyproject.toml
├── taskhub.db
├── tests
├── uploads
└── uv.lock
```

## Running the Project

You can run TaskHub using a manual local process, Docker Compose, or Kubernetes.

### 1. Manual Process (Local Development)

#### Quick Start with SQLite
This is the simplest way to get up and running without setting up external databases:
```bash
# 1. Create and activate a virtual environment
uv venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# 2. Install dependencies
uv sync

# 3. Copy example environment file
cp .env.example .env

# 4. Run database migrations (this creates the local sqlite file ./taskhub.db)
uv run alembic upgrade head

# 5. Start the FastAPI development server
uv run uvicorn app.main:app --reload
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) or `/redoc` in your browser. Register via `POST /api/v1/auth/register`, log in via `POST /api/v1/auth/login`, then use Swagger's **Authorize** button with the access token.

![API Documentation](./api-documentation.png)

#### Running with PostgreSQL
If you want to run the application manually but connect to a PostgreSQL database instead of SQLite:
1. Ensure you have a running PostgreSQL instance (with database name, user, and password set).
2. Configure `.env` with your Postgres connection details (refer to [app/core/config.py](file:///Users/sany/Projects/fastapi-zero-to-hero/app/core/config.py) for the schema):
   ```env
   DATABASE_HOST=localhost
   DATABASE_PORT=5432
   DATABASE_NAME=taskhub
   DATABASE_USER=taskhub
   DATABASE_PASSWORD=your_password
   ```
3. Run migrations and start the server:
   ```bash
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```

To make a user an admin (roles can't be self-assigned):
```bash
uv run python -c "
import asyncio, sqlalchemy as sa
from app.db.session import engine
async def main():
    async with engine.begin() as c:
        await c.execute(sa.text(\"UPDATE users SET role='admin' WHERE email='you@example.com'\"))
asyncio.run(main())"
```

### 2. Docker (Docker Compose)
To run the full stack (FastAPI app + PostgreSQL database) inside containers:
```bash
# Generate a secret key and boot the stack
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))') docker compose up --build
```
This command:
- Starts a PostgreSQL database container.
- Builds the FastAPI application Docker image.
- Performs Alembic migrations on startup.
- Exposes the application on [http://localhost:8000](http://localhost:8000).

To shut down the stack:
```bash
docker compose down -v
```

### 3. Kubernetes (Docker Desktop / AWS EC2)
For production-grade deployments, Kubernetes configurations are provided in the [fastapi-on-k8s](file:///Users/sany/Projects/fastapi-zero-to-hero/fastapi-on-k8s) directory.

1. **Navigate to the Kubernetes folder**:
   ```bash
   cd fastapi-on-k8s
   ```
2. **Review the deployment guide**: Read the detailed instructions in [fastapi-on-k8s/README.md](file:///Users/sany/Projects/fastapi-zero-to-hero/fastapi-on-k8s/README.md).
3. **Deploy the stack**:
   - Create namespace, secrets, configmap, and persistent volume claim:
     ```bash
     kubectl apply -f namespace.yaml
     kubectl apply -f secret.yaml
     kubectl apply -f configmap.yaml
     kubectl apply -f postgres/
     ```
   - Run the database migrations job:
     ```bash
     kubectl apply -f api/migration-job.yaml
     ```
   - Deploy the API, service, and HPA:
     ```bash
     kubectl apply -f api/deployment.yaml
     kubectl apply -f api/service.yaml
     kubectl apply -f api/hpa.yaml
     ```
4. **Access the application**:
   - **Local Development**: Forward traffic to your localhost:
     ```bash
     kubectl port-forward svc/api 8000:8000 -n taskhub
     ```
     Open [http://localhost:8000/docs](http://localhost:8000/docs).
   - **AWS EC2**: Access directly using port `30080` (NodePort):
     `http://<EC2_PUBLIC_IP>:30080/docs`


## Tests

```bash
uv run pytest            # 54 tests: auth, RBAC, CRUD, filtering, uploads…
uv run ruff check .      # lint
```

Tests run against in-memory SQLite with the DB dependency overridden — no
external services needed.

## Architecture Diagram

The end-to-end request flow through the application:

```mermaid
flowchart TB
    subgraph Host Machine
        Client["API Client (Browser/curl)"]
    end

    Client -->|"Port 8000"| MW

    subgraph Docker["Docker Virtualization Network Space"]

        subgraph AppContainer["App Container (FastAPI)"]
            MW["Middleware Stack\n(CORS · GZip · RequestID · RateLimit)"]
            MW --> Router["API Router (app/api/v1/)"]
            Router -->|"Depends(...)"| Auth["Auth & RBAC\n(JWT · OAuth2 · role check)"]
            Auth --> Services["Service Layer\n(business logic · transactions)"]
            Services --> Repos["Repository Layer\n(queries · pagination · filters)"]
        end

        Repos -->|"SQLAlchemy async"| DB
        Services -->|"Local File IO"| Uploads

        subgraph DBContainer["DB Container (postgres)"]
            DB[("PostgreSQL")]
        end

        Uploads[("Uploads Volume\n(./uploads)")]

    end
```

- **Routes** validate input with Pydantic schemas and declare response models;
  they never touch the session directly.
- **Services** own commits and raise domain exceptions (`NotFoundError`,
  `ConflictError`, …) that global handlers turn into a standard error envelope.
- **Repositories** are thin generic query helpers (`list_paginated` does
  filter + search + sort + count in one place).

### Standard formats

Every list endpoint returns `{items, total, page, page_size, pages}`.
Every error returns:

```json
{"error": {"code": "not_found", "message": "Project not found"}, "request_id": "…"}
```

## Feature map

| Feature | Where |
|---|---|
| API versioning | `app/api/v1/` mounted at `/api/v1` (`app/main.py`) |
| CRUD + soft delete/restore | `app/api/v1/routes/projects.py`, `tasks.py` |
| Validation (constraints, custom validators, sanitization) | `app/schemas/` (`str_strip_whitespace`, password strength, future `due_date`) |
| Response models / hidden fields | `UserRead` omits `hashed_password` |
| JWT auth (access + refresh, rotation) | `app/core/security.py`, `app/services/auth.py` |
| RBAC + ownership checks | `require_roles` in `app/api/deps.py`; `get_accessible` in services |
| Async SQLAlchemy 2.0, pooling, transactions | `app/db/session.py`, services commit explicitly |
| Alembic migrations (async, autogenerate) | `alembic/` |
| Dependency injection | `app/api/deps.py` (session, settings, current user, services, pagination) |
| Global exception handling, error envelope | `app/core/exceptions.py` |
| Structured logging + request logging | `app/core/logging.py`, `app/middleware/request_context.py` |
| Pagination / filtering / sorting / search | `BaseRepository.list_paginated` + query params on list routes |
| Config management (.env, per-environment) | `app/core/config.py` |
| CORS, trusted hosts, GZip | `app/main.py` |
| Rate limiting (global per-IP + per-endpoint) | `app/middleware/rate_limit.py`, `login_rate_limit` dep |
| OpenAPI docs (tags, summaries, examples, error models) | route decorators throughout |
| Health probes | `/health`, `/live`, `/ready` (DB check) |
| Request ID + timing middleware | `app/middleware/request_context.py` |
| File upload (multipart, type + size limits, streaming) | `TaskService.add_attachment` |
| Background tasks | welcome email in `routes/auth.py` + `app/services/email.py` |
| Metrics endpoint | `/metrics` (`app/utils/metrics.py`) |
| Audit fields, UUID PKs, timestamps | `app/models/mixins.py` |
| Test suite w/ test DB | `tests/` |
| Docker + Compose + prod ASGI server | `Dockerfile`, `docker-compose.yml` |

## Deliberate scope cuts (and how to grow them)

- **Rate limiting & metrics are in-process.** Multi-worker/multi-replica
  deployments need Redis for the limiter and prometheus-client for metrics —
  both are isolated behind single integration points (`SlidingWindowRateLimiter.check`,
  `MetricsCollector.record`).
- **Refresh tokens are stateless** (no server-side revocation list). Add a
  `refresh_tokens` table keyed by `jti` if you need logout-everywhere.
- **Caching** is omitted; add Redis + a cache-aside decorator in services if
  list endpoints get hot.
- **File storage is local disk.** Swap `TaskService.add_attachment` internals
  for S3/GCS; the API contract doesn't change.
