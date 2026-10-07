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

For example:

```text
GET /expenses/report/monthly?year=2026&month=9
```

and:

```text
GET /expenses/report/monthly?year=2026&month=9&daily=true
```

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
git clone <repository-url>
cd awesome-project
```

Install dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://expense_user:<password>@localhost:5432/expense_tracker
TEST_DATABASE_URL=postgresql+psycopg://expense_user:<password>@localhost:5432/expense_tracker_test
SECRET_KEY=<your-secret-key>
APP_ENV=development
```

Apply migrations:

```bash
uv run alembic upgrade head
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

The Compose PostgreSQL service is published on port `5433` on the host to avoid conflicting with a locally installed PostgreSQL instance.

Database migrations are applied separately from the Docker image build; rebuilding the application image does not automatically change the database schema.

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
