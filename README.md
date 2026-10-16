# Expense Tracker API

A backend API for managing personal expenses, built with **Python, FastAPI, PostgreSQL, and SQLAlchemy**.

The project has evolved from a basic CRUD API into a practical backend-engineering application covering authentication, authorization, database transactions, reporting, validation, testing, performance optimization, observability, and Docker-based deployment.

## Tech Stack

* **Python 3.12+**
* **FastAPI** — REST API framework
* **Pydantic** — request/response validation
* **SQLAlchemy 2** — ORM and database interaction
* **PostgreSQL 16+** — relational database
* **Alembic** — database schema migrations
* **Pytest** — automated API and database integration testing
* **Ruff** — linting and formatting
* **uv** — Python project and dependency management
* **Uvicorn** — ASGI server
* **Docker / Docker Compose** — containerized application and database environment

## Features

### Expense Management

* Create, retrieve, update, partially update, and delete expenses
* User-specific expense ownership and access control
* Category filtering
* Pagination with `limit` and `offset`
* Amount/date-based ordering
* Date-range queries and reports
* Monthly expense reports
* Bulk expense creation

### Authentication & Security

* User registration and login
* Password hashing
* JWT-based authentication
* Bearer-token authorization
* User-level resource isolation
* Password change endpoint
* Token-version-based JWT revocation after password changes
* Rejection of stale/revoked access tokens

### Data Integrity & Transactions

* Pydantic request validation
* PostgreSQL `NOT NULL`, `UNIQUE`, foreign-key, and `CHECK` constraints
* Transactional bulk creation
* Explicit rollback handling for database failures
* Atomic password and token-version updates
* Alembic-managed schema evolution

### Reporting & Query Performance

* Category-based expense aggregation
* Daily expense reporting
* Monthly reporting with category and daily views
* Half-open date-range handling
* PostgreSQL indexing for user/date access patterns
* Query-plan analysis with `EXPLAIN`
* Performance measurement before optimization
* Removal of unjustified experimental indexes

### Reliability & Observability

* Centralized application configuration
* Structured application logging
* Database health/readiness check
* Appropriate HTTP error handling
* Server-side exception logging without exposing internal database details

### Testing & Quality

* Automated API test suite
* Separate PostgreSQL test database
* Test isolation using database transactions/savepoints
* Authentication and authorization tests
* Validation and error-path tests
* Database rollback/integration tests
* Token revocation tests
* Ruff linting and formatting checks

### Deployment

* Dockerized FastAPI application
* Dockerized PostgreSQL
* Persistent PostgreSQL volume
* PostgreSQL healthcheck
* API startup dependency on database health
* Environment-specific configuration
* Verified application behavior across container restarts

## Architecture

```text
Client
  │
  ▼
FastAPI
  │
  ├── Routers
  │     ├── Expenses
  │     ├── Users
  │     └── Health
  │
  ├── Pydantic Schemas
  │
  ├── Security / JWT
  │
  ├── Application Configuration
  │
  └── SQLAlchemy Session
          │
          ▼
     SQLAlchemy ORM
          │
          ▼
      PostgreSQL

Alembic
  │
  └── Database schema migrations

Pytest
  │
  ├── API tests
  └── Database integration tests

Docker Compose
  ├── API container
  └── PostgreSQL container
```

## Project Structure

```text
awesome-project/
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── ...
├── src/
│   └── awesome_project/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── logging_config.py
│       ├── main.py
│       ├── models.py
│       ├── schemas.py
│       ├── security.py
│       └── routers/
│           ├── __init__.py
│           ├── expenses.py
│           ├── health.py
│           └── users.py
├── tests/
│   ├── conftest.py
│   └── test_main.py
├── docker/
│   └── postgres/
│       └── init/
├── .dockerignore
├── .gitignore
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── uv.lock
└── README.md
```

## API Overview

### Health

| Method | Endpoint  | Description                            |
| ------ | --------- | -------------------------------------- |
| GET    | `/health` | Database-backed health/readiness check |

### Users

| Method | Endpoint                 | Description                                                         |
| ------ | ------------------------ | ------------------------------------------------------------------- |
| POST   | `/users/register`        | Register a new user                                                 |
| POST   | `/users/login`           | Authenticate and receive an access token                            |
| POST   | `/users/change-password` | Change the authenticated user's password and revoke previous tokens |

### Expenses

| Method | Endpoint                 | Description                         |
| ------ | ------------------------ | ----------------------------------- |
| GET    | `/expenses`              | List the current user's expenses    |
| GET    | `/expenses/{expense_id}` | Retrieve a single expense           |
| POST   | `/expenses`              | Create an expense                   |
| POST   | `/expenses/bulk`         | Create multiple expenses atomically |
| PUT    | `/expenses/{expense_id}` | Replace an expense                  |
| PATCH  | `/expenses/{expense_id}` | Partially update an expense         |
| DELETE | `/expenses/{expense_id}` | Delete an expense                   |

### Reporting

The API also provides expense summary and reporting endpoints covering:

* Expense totals
* Category-based summaries
* Daily reporting
* Date-range reporting
* Monthly reporting
* Optional daily/monthly views

Examples:

```text
GET /expenses/summary
GET /expenses/report/categories
GET /expenses/report/daily?from_date=2026-09-01&to_date=2026-09-30
GET /expenses/report/monthly?year=2026&month=9
GET /expenses/report/monthly?year=2026&month=9&daily=true
```

Reporting endpoints require authentication. Date-range parameters use ISO dates (`YYYY-MM-DD`).

## Quick API Example

Start the API, then register a user. Use your own email and a password of at least eight characters:

```bash
curl -X POST http://127.0.0.1:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","email":"demo@example.com","password":"change-this-password"}'
```

Log in to receive a bearer token:

```bash
curl -X POST http://127.0.0.1:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"change-this-password"}'
```

Copy the returned `access_token` value into the next request:

```bash
curl http://127.0.0.1:8000/expenses \
  -H "Authorization: Bearer <access-token>"
```

Create an expense using the same authorization header:

```bash
curl -X POST http://127.0.0.1:8000/expenses \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Groceries","amount":"450.00","category":"Food","expense_date":"2026-09-30"}'
```

The API returns an expense object that includes its `id` and `version`. These examples create a real user and data in the configured database; use a development database, not production credentials.

## Authentication

Protected endpoints use JWT Bearer authentication.

A successful login issues an access token containing the authenticated user's identity and current token version.

```text
Login
  ↓
JWT issued with token_version
  ↓
Protected request
  ↓
JWT decoded
  ↓
User loaded from PostgreSQL
  ↓
JWT token_version compared with DB token_version
  ↓
Match → request allowed
Mismatch → 401 Unauthorized
```

When a user changes their password:

```text
hashed_password updated
+
token_version incremented
        ↓
      COMMIT
```

Previously issued tokens therefore become invalid even if their normal JWT expiration time has not yet been reached.

## Concurrent Updates

Each expense response includes a `version` number. When updating an expense with `PUT` or `PATCH`, send the version you last retrieved as `expected_version`. If another request has changed that expense in the meantime, the API responds with `409 Conflict` rather than silently overwriting the newer data.

For example, an update body can include:

```json
{
  "title": "Groceries",
  "amount": "475.00",
  "category": "Food",
  "expense_date": "2026-09-30",
  "expected_version": 1
}
```

Use the current version returned by the API; `1` above is illustrative. After a `409 Conflict`, fetch the latest expense, reconcile the changes, and retry with its current version.

## Database & Migrations

The project uses PostgreSQL with SQLAlchemy 2 for database interaction and Alembic for schema migrations.

Apply migrations:

```bash
uv run alembic upgrade head
```

Check the current migration:

```bash
uv run alembic current
```

For the test database:

```bash
uv run alembic -x test=true upgrade head
```

Database constraints and indexes are maintained through the schema/migration workflow rather than relying solely on application-level validation.

## Running Locally

### Requirements

* Python 3.12+
* PostgreSQL 16+
* `uv`

Clone the repository:

```bash
git clone https://github.com/AshishNayke/expense-tracker-api.git
cd expense-tracker-api
```

Install dependencies:

```bash
uv sync
```

Create your local environment file from the example template:

```bash
cp .env.example .env
```

Edit `.env` and configure your database credentials and a unique secret key. Your local PostgreSQL server must have both `expense_tracker` and `expense_tracker_test` databases, and the configured database role must have the required permissions.

The database URLs must match your local PostgreSQL role, password, and database names. URL-encode special characters in the password when placing it in a connection URL.

Generate a development secret key with:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Set the generated value as `SECRET_KEY` in `.env`. The secret key must be at least 64 characters long. Keep `.env` private; it is excluded from Git.

Apply the schema migrations to the development database:

```bash
uv run alembic upgrade head
```

Apply migrations to the test database when preparing it independently:

```bash
uv run alembic -x test=true upgrade head
```

Start the development server:

```bash
uv run uvicorn awesome_project.main:app --reload
```

The API is available at:

```text
http://127.0.0.1:8000
```

Interactive Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

## Running with Docker

The project includes a Docker Compose environment containing:

* FastAPI application
* PostgreSQL database
* Persistent database storage
* PostgreSQL healthcheck
* API dependency on database health

Before starting Docker, create the environment files from their templates:

```bash
cp .env.postgres.example .env.postgres
cp .env.docker.example .env.docker
```

Replace the placeholders in `.env.postgres` and `.env.docker` with your own values. The PostgreSQL password in `.env.postgres` must match the password in the Docker API's `DATABASE_URL` and `TEST_DATABASE_URL`. URL-encode the password when placing it in a database URL if it contains reserved URL characters.

Set a unique `SECRET_KEY` in `.env.docker`, using the same generation command shown in the local setup section. Keep these local environment files private; they are excluded from Git.

Start the environment:

```bash
docker compose up -d --build
```

Check container status:

```bash
docker compose ps
```

Check application health:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status": "ok"}
```

The Docker API connects to PostgreSQL using the Compose service hostname `db` on port `5432`. The database is published on host port `5433` for connections from your computer.

Database migrations are applied separately from the Docker image build; rebuilding the application image does not automatically change the database schema.

### Apply migrations to the Docker database

The API container image intentionally excludes development dependencies and the Alembic migration directory, so run migrations from your host while the Compose database is running. The host port is `5433`; inside Docker, the database is reachable as `db:5432`.

The `.env.docker` file already contains the Docker database URL. The following command reads that URL and changes only its host and port for a host-side migration. It does not print the URL or require you to copy the password into the command:

```bash
DATABASE_URL="$(uv run python -c 'from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values(".env.docker")["DATABASE_URL"]).set(host="127.0.0.1", port=5433).render_as_string(hide_password=False))')" uv run alembic upgrade head
```

Verify the revision applied to the Docker database:

```bash
DATABASE_URL="$(uv run python -c 'from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values(".env.docker")["DATABASE_URL"]).set(host="127.0.0.1", port=5433).render_as_string(hide_password=False))')" uv run alembic current
```

Run these commands from the project root after `docker compose up -d --build`. They require the host development dependencies installed by `uv sync` and the database credentials configured in `.env.docker`.

## Continuous Integration

GitHub Actions runs the backend quality checks on pushes to `main` and pull requests targeting `main`. The workflow starts a PostgreSQL 16 service, installs the project with development dependencies, applies migrations, runs Ruff, and executes the pytest suite.

You can run the same core checks locally:

```bash
uv run alembic -x test=true upgrade head
uv run ruff check .
uv run pytest -q
```

## Testing

Run the complete test suite:

```bash
uv run pytest
```

The test suite uses a separate PostgreSQL test database and isolates tests using transaction/savepoint-based fixtures.

The suite covers:

* Successful API operations
* Request validation
* Authentication
* Authorization and user isolation
* Expense CRUD behavior
* Reporting behavior
* Bulk transaction behavior
* Database rollback
* Password changes
* JWT token revocation
* Error responses
* Date and month boundary cases

## Code Quality

Run Ruff:

```bash
uv run ruff check .
```

Format the project:

```bash
uv run ruff format .
```

A typical development checkpoint is:

```text
Feature
  ↓
Tests
  ↓
Ruff
  ↓
Git commit
  ↓
Docker verification when applicable
```

## Key Engineering Concepts

This project intentionally focuses on understanding backend fundamentals before introducing unnecessary architectural complexity.

Core areas practiced include:

* REST API design and HTTP semantics
* Request/response validation
* Dependency injection
* SQLAlchemy sessions and ORM behavior
* Database transactions, `flush`, `commit`, and `rollback`
* Relational database constraints
* Database migrations
* Authentication vs. authorization
* JWT expiration and server-side token revocation
* Query planning and indexing
* API and database integration testing
* Logging and health checks
* Containerized application deployment

The architecture is intentionally kept simple. Additional layers such as repositories, service modules, caching, background processing, or distributed components should only be introduced when the application's actual complexity justifies them.

## Project Status

This project is actively developed as a backend-engineering project.

The current implementation includes a complete expense-management API with authentication, reporting, transactional operations, automated tests, performance work, observability, and Docker deployment.

Further development will focus on additional backend features, production hardening, and progressively more advanced engineering concepts.

## License

No open-source license is currently specified. This repository is primarily a learning and portfolio project.
