# EGO Marketplace API

FastAPI backend for the EGO marketplace application.

## Architecture

```
Flutter Mobile App
      |
   FastAPI            <- application/business logic layer
      |
Supabase PostgreSQL   <- managed relational database only
```

Supabase is used **only** as a managed PostgreSQL host (plus, in later tasks,
possibly Auth/Storage). All application/business logic lives in FastAPI.
Supabase Edge Functions are not part of this architecture.

## Stack

- **FastAPI** - web framework
- **SQLAlchemy 2.x (async)** - ORM, using the `asyncpg` driver
- **Alembic** - database migrations
- **Pydantic / Pydantic Settings** - request/response validation and configuration
- **Supabase PostgreSQL** - primary relational database (managed Postgres)

## Project structure

```
app/
  main.py            FastAPI app factory and entry point
  core/
    config.py         Settings loaded from environment variables (.env)
    logging.py         Logging configuration
    exceptions.py       App exception types + global exception handlers
  db/
    database.py          Async engine + session factory (Supabase connection, pooling, SSL)
    dependencies.py       Reusable FastAPI dependency (`get_db` / `DBSession`) for a DB session
    base.py               Declarative base (target for future ORM models)
  models/              SQLAlchemy ORM models (empty - added in a later task)
  schemas/             Pydantic request/response schemas (empty - added in a later task)
  repositories/         Data-access layer (empty - added in a later task)
  services/             Business logic layer (empty - added in a later task)
  api/
    deps.py              Shared FastAPI dependencies (re-exports DB session dep, settings dep)
    health.py            Unversioned GET /health (liveness) and GET /health/db (DB connectivity)
    v1/
      api.py              Aggregator router for all v1 endpoints (empty for now)
      endpoints/          Versioned endpoint modules (added in later tasks)
  utils/                Shared helper utilities (empty - added in a later task)
tests/                  Test suite
alembic/                Migration environment (env.py wired to app settings/models)
```

## Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and fill in real values:

   ```bash
   cp .env.example .env
   ```

### Getting your Supabase database connection string

1. Open your project in the [Supabase dashboard](https://supabase.com/dashboard).
2. Go to **Project Settings > Database**.
3. Under **Connection string**, select the **URI** tab. You'll see something like:

   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```

4. Replace `[YOUR-PASSWORD]` with your database password (set/reset on the same
   page), and paste the full string into `DATABASE_URL` in your `.env`.
5. Supabase also shows pooled connection strings (Supavisor), typically on
   port `6543` for the **transaction** pooler or port `5432` for the
   **session** pooler. If you use the transaction pooler, set
   `DB_POOL_MODE=transaction` in `.env` (see below for why).

**Never commit `.env`** - it's already in `.gitignore`. Only `.env.example`
(with placeholder values) is committed.

### Where `DATABASE_URL` is configured

- `.env` (local, gitignored) / your deployment platform's environment
  variables (production) - the actual value.
- `.env.example` - documents the variable with a placeholder, no real credentials.
- `app/core/config.py` (`Settings.DATABASE_URL`) - loaded via Pydantic Settings,
  required (the app refuses to start without it).
- `Settings.sqlalchemy_database_url` - a derived property that rewrites the
  `postgresql://`/`postgres://` scheme Supabase gives you into
  `postgresql+asyncpg://`, which is what SQLAlchemy's async engine needs. You
  never need to edit the scheme yourself.

### Connection pooling modes

| `DB_POOL_MODE` | Use when...                                             | How pooling works |
|----------------|----------------------------------------------------------|--------------------|
| `session` (default) | Connecting directly to Supabase (port 5432) or via the Supavisor **session** pooler | SQLAlchemy's own `QueuePool` manages a pool sized by `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` |
| `transaction` | Connecting via the Supavisor **transaction** pooler (port 6543) | SQLAlchemy uses `NullPool` (no local pooling - the pooler already multiplexes connections) and asyncpg's server-side statement cache is disabled, since transaction-mode pooling doesn't support prepared statements across requests |

For a long-running FastAPI process (not serverless), `session` mode against a
direct connection is the simplest default and what `.env.example` assumes.

## How FastAPI connects to Supabase PostgreSQL

1. `app/core/config.py` loads `DATABASE_URL` (and the `DB_*` pooling/SSL
   settings) from the environment via Pydantic Settings.
2. `app/db/database.py` builds a single async SQLAlchemy engine
   (`create_async_engine`) at import time, using the `asyncpg` driver and:
   - `connect_args={"ssl": "require"}` when `DB_SSL_REQUIRE=true` (default),
     since Supabase requires TLS on external connections.
   - `pool_pre_ping=True` so a stale/dropped connection is detected and
     replaced before use, and `pool_recycle` so idle pooled connections are
     periodically refreshed - both important for a network-hosted database
     that may close idle connections.
   - Pool class/sizing chosen per `DB_POOL_MODE` (see table above).
   - Engine creation itself does not open a connection - the app can start
     even if the database is briefly unreachable; the first real query is
     what would fail.
3. `AsyncSessionLocal` (an `async_sessionmaker`) produces `AsyncSession`
   instances bound to that engine.
4. `app/db/dependencies.py` exposes `get_db()` / `DBSession`, a FastAPI
   dependency that yields one `AsyncSession` per request and closes it
   afterwards. Future route handlers depend on `DBSession` (via
   `app/api/deps.py`) rather than talking to the engine directly.
5. `GET /health/db` (`app/api/health.py`) calls
   `check_database_connection()`, which runs `SELECT 1` against the engine,
   to give an HTTP-visible confirmation that Supabase is reachable.

No application tables or models exist yet - this task only wires up the
connection itself.

## Running the app

```bash
uvicorn app.main:app --reload
```

Then check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/health/db
# {"status":"ok","database":"connected"}          <- if Supabase is reachable
# {"status":"error","database":"unreachable"}  (503) <- if it is not
```

Interactive API docs are available at `http://localhost:8000/docs`.

## Testing the Supabase connection

With `DATABASE_URL` in `.env` pointed at your Supabase project:

```bash
pytest tests/test_database_connection.py -v
```

This runs a real `SELECT 1` round-trip against the configured database (via
the same engine the app uses) and also exercises `GET /health/db` through the
FastAPI test client. Both require a reachable database - they are
connectivity tests, not mocked unit tests.

For a quick manual check without starting the server:

```bash
python -c "import asyncio; from app.db.database import check_database_connection; print(asyncio.run(check_database_connection()))"
# True
```

## Migrations

Alembic is configured but there are no models/migrations yet (added in a later
task). Once models exist under `app/models/`, generate a migration with:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

`alembic/env.py` connects using the same `DATABASE_URL`/SSL settings as the
app, so it also targets Supabase.

## Tests

```bash
pytest
```
