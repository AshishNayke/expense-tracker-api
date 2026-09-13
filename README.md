# Expense Tracker API

A REST API for managing personal expenses, built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**.

The project is built as a practical backend-engineering learning project, with database migrations, automated API tests, validation, pagination, filtering, and code-quality tooling.

## Tech Stack

* **Python 3.12+**
* **FastAPI** — REST API framework
* **Pydantic** — request/response validation
* **SQLAlchemy 2** — ORM and database interaction
* **PostgreSQL** — relational database
* **Alembic** — database migrations
* **Pytest** — automated testing
* **Ruff** — linting and formatting
* **uv** — Python project and dependency management
* **Uvicorn** — ASGI server

## Features

* Create, read, update, partially update, and delete expenses
* Input validation with Pydantic
* Database-level validation with PostgreSQL constraints
* Category filtering
* Amount-based descending ordering
* Pagination with `limit` and `offset`
* PostgreSQL database integration
* Alembic database migrations
* Automated API tests with an isolated test database
* Ruff linting and formatting

## Project Structure

```text
awesome-project/
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── ...
├── src/
│   └── awesome_project/
│       ├── main.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       └── routers/
│           └── expenses.py
├── tests/
│   ├── conftest.py
│   └── test_main.py
├── .env
├── pyproject.toml
├── uv.lock
└── README.md
```

### Architecture

```text
Client
  ↓
FastAPI
  ↓
Pydantic schemas
  ↓
SQLAlchemy Session
  ↓
SQLAlchemy ORM
  ↓
PostgreSQL
```

Alembic manages database schema changes, while Pytest verifies API behavior.

## Requirements

* Python 3.12+
* PostgreSQL
* `uv`

## Setup

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd awesome-project
```

Install the project dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://expense_user:<password>@localhost:5432/expense_tracker
TEST_DATABASE_URL=postgresql+psycopg://expense_user:<password>@localhost:5432/expense_tracker_test
```

Replace the credentials with your local PostgreSQL configuration.

## Database Setup

Apply the existing Alembic migrations:

```bash
uv run alembic upgrade head
```

To check the current migration:

```bash
uv run alembic current
```

## Running the API

Start the development server:

```bash
uv run uvicorn awesome_project.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

| Method | Endpoint                 | Description                 |
| ------ | ------------------------ | --------------------------- |
| GET    | `/`                      | API status                  |
| GET    | `/expenses`              | List expenses               |
| GET    | `/expenses/{expense_id}` | Get a single expense        |
| POST   | `/expenses`              | Create an expense           |
| PUT    | `/expenses/{expense_id}` | Replace an expense          |
| PATCH  | `/expenses/{expense_id}` | Partially update an expense |
| DELETE | `/expenses/{expense_id}` | Delete an expense           |

### Filtering and Pagination

Expenses can be filtered by category:

```text
GET /expenses?category=Food
```

Pagination is supported through `limit` and `offset`:

```text
GET /expenses?limit=10&offset=20
```

Results are ordered by amount in descending order.

## Running Tests

Run the complete test suite:

```bash
uv run pytest
```

The tests use a separate PostgreSQL test database and isolate each test using transaction rollback.

## Code Quality

Run Ruff's linter:

```bash
uv run ruff check .
```

Format the project:

```bash
uv run ruff format .
```

## Development Philosophy

This project focuses on learning practical backend engineering concepts rather than adding architecture for its own sake.

The current structure separates:

* HTTP routing
* API schemas
* Database models
* Database/session configuration
* Database migrations
* Automated tests

Additional architectural layers such as repositories or service modules can be introduced when the project's complexity actually justifies them.

## License

This project is currently for learning and development purposes.
