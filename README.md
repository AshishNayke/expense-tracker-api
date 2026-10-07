# Expense Tracker API

A Python backend API for personal expense management, built with FastAPI and PostgreSQL and developed as a practical backend-engineering project. The project started as a simple CRUD API and evolved into a more complete backend system focused on authentication, authorization, database transactions, reporting, testing, performance, and Docker-based deployment.

## Overview

The goal of this project is to practice backend engineering beyond basic CRUD by designing and implementing realistic API, database, security, testing, and deployment concerns.

### Core Stack

* **Python 3.12**
* **FastAPI**
* **Pydantic**
* **PostgreSQL 16**
* **SQLAlchemy**
* **Alembic**
* **PyJWT**
* **Pytest**
* **Ruff**
* **Docker / Docker Compose**
* **uv**

## Features

### Expense Management

* Create, read, update, and delete expenses
* Partial expense updates
* Pagination and filtering
* Expense ownership and user isolation
* Positive-amount validation
* Expense dates

### Authentication & Security

* User registration and login
* Password hashing
* JWT-based authentication
* Bearer-token authorization
* User-level resource ownership
* Password change
* JWT token-version based revocation after password changes
* Expiring access tokens

### Reporting

* Expense summaries
* Date-range reports
* Category-based reports
* Daily reports
* Monthly reports grouped by category or day

### Transaction Handling

* Bulk expense creation
* Atomic database operations
* Explicit rollback handling
* Database constraint handling
* Transaction-focused integration tests

### Database & Performance

* PostgreSQL relational schema
* Foreign keys and unique constraints
* Database `CHECK` constraints
* Alembic migrations
* Composite indexing
* Query execution-plan analysis
* Performance measurement and profiling
* Optimization based on measured query behavior

### Reliability & Observability

* Centralized application configuration
* Environment-based settings
* Application logging
* Database health/readiness check
* Graceful application startup/shutdown logging
* Safe handling of unexpected database errors

### Testing

The project includes automated API and database integration tests covering:

* Authentication
* Authorization and user isolation
* Request validation
* CRUD behavior
* Reporting
* Pagination
* Date boundaries
* Empty-result behavior
* Bulk transactions
* Database rollback
* Password changes
* JWT token revocation

## Architecture

The current application follows a simple layered structure:

```text
Client
  ↓
FastAPI Routers
  ↓
Pydantic Validation
  ↓
Authentication / Authorization
  ↓
SQLAlchemy Session
  ↓
PostgreSQL
```

Supporting components include:

```text
Alembic      → Database schema migrations
Pytest       → Automated testing
Ruff         → Linting and code quality
Docker       → Reproducible runtime environment
```

## Project Structure

```text
awesome-project/
├── alembic/
│   └── versions/
├── src/
│   └── awesome_project/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── logging_config.py
│       ├── models.py
│       ├── schemas.py
│       ├── security.py
│       └── routers/
│           ├── expenses.py
│           ├── users.py
│           └── health.py
├── tests/
│   ├── conftest.py
│   └── test_main.py
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── uv.lock
```

## Compact API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/expenses` | List current user's expenses |
| POST | `/expenses` | Create expense |
| PATCH | `/expenses/{id}` | Partial update |
| GET | `/expenses/report/monthly` | Monthly report |
| POST | `/expenses/bulk` | Atomic bulk creation |
| POST | `/users/register` | Register |
| POST | `/users/login` | Login |
| POST | `/users/change-password` | Change password / revoke old tokens |
| GET | `/health` | Database readiness check |

## Running Locally

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

Create a `.env` file containing the required application settings:

```text
DATABASE_URL=...
TEST_DATABASE_URL=...
SECRET_KEY=...
APP_ENV=development
```

### 3. Apply database migrations

```bash
uv run alembic upgrade head
```

### 4. Start the API

```bash
uv run uvicorn awesome_project.main:app --reload
```

The development API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Running Tests

Run the complete test suite:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
```

## Running with Docker

The project includes a Docker Compose environment containing:

* FastAPI application
* PostgreSQL database
* Persistent PostgreSQL volume
* PostgreSQL health check
* API dependency on database health

Build and start the environment:

```bash
docker compose build
docker compose up -d
```

Check container status:

```bash
docker compose ps
```

Check API health:

```bash
curl http://127.0.0.1:8000/health
```

The Docker PostgreSQL service is exposed on port `5433` on the host.

Database migrations are managed separately through Alembic.

## Engineering Focus

This project is intentionally focused on learning and demonstrating practical backend engineering concepts rather than simply implementing CRUD endpoints.

Key areas explored include:

```text
API design
HTTP semantics
Authentication and authorization
Database modeling
Transactions and rollback
Schema migrations
Query optimization
Automated testing
Logging and health checks
Containerization
```

## Current Status

The backend is actively being developed.

The current implementation provides a functional expense-management API with authentication, reporting, transactional operations, automated testing, performance work, and Docker support.

Further development will focus on additional backend engineering challenges, production hardening, and continued improvement of the application's architecture and reliability.
