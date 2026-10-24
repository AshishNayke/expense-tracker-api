from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
from conftest import test_engine
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from awesome_project.config import Settings, settings
from awesome_project.database import get_db
from awesome_project.main import app
from awesome_project.models import Expense, IdempotencyOperation, User
from awesome_project.schemas import PasswordChange
from awesome_project.security import (
    ALGORITHM,
    create_access_token,
    hash_password,
    verify_password,
)


class SynchronizedSession(Session):
    def __init__(self, *args, lookup_barrier: Barrier, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookup_barrier = lookup_barrier
        self.waited_at_initial_lookup = False

    def scalar(self, statement, *args, **kwargs):
        result = super().scalar(statement, *args, **kwargs)

        descriptions = getattr(statement, "column_descriptions", ())
        is_operation_lookup = any(
            description.get("entity") is IdempotencyOperation
            for description in descriptions
        )

        if (
            is_operation_lookup
            and result is None
            and not self.waited_at_initial_lookup
        ):
            self.waited_at_initial_lookup = True
            self.lookup_barrier.wait(timeout=10)

        return result


def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Expense Tracker API is running"}


def test_get_expenses(client):
    response = client.get("/expenses")

    assert response.status_code == 200
    assert response.json() == []


def test_create_expense(client):
    response = client.post(
        "/expenses",
        json={
            "title": "Test lunch",
            "amount": "150.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Test lunch"
    assert data["amount"] == "150.00"
    assert data["category"] == "Food"
    assert data["expense_date"] == "2026-09-20"
    assert "id" in data


def test_get_expense(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Test dinner",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201

    expense_id = create_response.json()["id"]

    response = client.get(f"/expenses/{expense_id}")

    assert response.status_code == 200
    assert response.json()["id"] == expense_id
    assert response.json()["title"] == "Test dinner"
    assert response.json()["amount"] == "250.00"
    assert response.json()["category"] == "Food"
    assert response.json()["expense_date"] == "2026-09-20"


def test_get_expense_not_found(client):
    response = client.get("/expenses/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Expense not found"}


def test_update_expense(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Old title",
            "amount": "100.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201

    expense_id = create_response.json()["id"]

    update_response = client.put(
        f"/expenses/{expense_id}",
        json={
            "title": "Updated dinner",
            "amount": "350.00",
            "category": "Restaurant",
            "expense_date": "2026-09-21",
            "expected_version": create_response.json()["version"],
        },
    )

    assert update_response.status_code == 200

    data = update_response.json()

    assert data["id"] == expense_id
    assert data["title"] == "Updated dinner"
    assert data["amount"] == "350.00"
    assert data["category"] == "Restaurant"
    assert data["expense_date"] == "2026-09-21"
    assert data["version"] == 2

    get_response = client.get(f"/expenses/{expense_id}")

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Updated dinner"
    assert get_response.json()["amount"] == "350.00"
    assert get_response.json()["category"] == "Restaurant"
    assert get_response.json()["expense_date"] == "2026-09-21"

def test_update_expense_not_found(client):
    response = client.put(
        "/expenses/999999",
        json={
            "title": "Updated dinner",
            "amount": "350.00",
            "category": "Restaurant",
            "expense_date": "2026-09-20",
            "expected_version": 1,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Expense not found"}


def test_patch_expense(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Original dinner",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201

    expense_id = create_response.json()["id"]

    # Update only the amount.
    patch_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "300.00",
            "expected_version": create_response.json()["version"],
        },
    )

    assert patch_response.status_code == 200

    data = patch_response.json()

    assert data["id"] == expense_id
    assert data["title"] == "Original dinner"
    assert data["amount"] == "300.00"
    assert data["category"] == "Food"
    assert data["expense_date"] == "2026-09-20"

    # Update only the expense date.
    patch_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "expense_date": "2026-09-23",
            "expected_version": patch_response.json()["version"],
        },
    )

    assert patch_response.status_code == 200

    data = patch_response.json()

    assert data["id"] == expense_id
    assert data["title"] == "Original dinner"
    assert data["amount"] == "300.00"
    assert data["category"] == "Food"
    assert data["expense_date"] == "2026-09-23"

    # Verify the date change persisted.
    get_response = client.get(f"/expenses/{expense_id}")

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Original dinner"
    assert get_response.json()["amount"] == "300.00"
    assert get_response.json()["category"] == "Food"
    assert get_response.json()["expense_date"] == "2026-09-23"


def test_patch_expense_not_found(client):
    response = client.patch(
        "/expenses/999999",
        json={
            "amount": "300.00",
            "expected_version": 1,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Expense not found"}


def test_get_expense_by_category(client):
    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus ticket",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2026-09-21",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Restaurant",
            "amount": "300.00",
            "category": "Food",
            "expense_date": "2026-09-22",
        },
    )
    response = client.get("/expenses?category=Food")
    assert response.status_code == 200

    data = response.json()
    for item in data:
        assert item["category"] == "Food"
    assert len(data) == 2

def test_user_cannot_access_another_users_expense(
    client,
    auth_headers,
):
    # User A creates an expense.
    create_response = client.post(
        "/expenses",
        json={
            "title": "User A expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201
    expense_id = create_response.json()["id"]

    # Create User B.
    register_response = client.post(
        "/users/register",
        json={
            "username": "user_b",
            "email": "user_b@example.com",
            "password": "password123",
        },
    )

    assert register_response.status_code == 201

    # Log in as User B.
    login_response = client.post(
        "/users/login",
        json={
            "username": "user_b",
            "password": "password123",
        },
    )

    assert login_response.status_code == 200

    user_b_token = login_response.json()["access_token"]

    # Switch from User A to User B.
    client.headers["Authorization"] = f"Bearer {user_b_token}"

    # User B cannot read User A's expense.
    response = client.get(f"/expenses/{expense_id}")
    assert response.status_code == 404

    # User B cannot replace User A's expense.
    response = client.put(
        f"/expenses/{expense_id}",
        json={
            "title": "Hacked expense",
            "amount": "9999.00",
            "category": "Other",
            "expense_date": "2026-09-21",
            "expected_version": 1,
        },
    )
    assert response.status_code == 404

    # User B cannot partially modify User A's expense.
    response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "9999.00",
            "expected_version": 1,
        },
    )
    assert response.status_code == 404

    # User B cannot delete User A's expense.
    response = client.delete(f"/expenses/{expense_id}")
    assert response.status_code == 404

    # Switch back to User A.
    client.headers["Authorization"] = auth_headers["Authorization"]

    # The original expense still exists and is unchanged.
    response = client.get(f"/expenses/{expense_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": expense_id,
        "title": "User A expense",
        "amount": "500.00",
        "category": "Food",
        "expense_date": "2026-09-20",
        "version": 1,
    }

def test_expenses_require_authentication(unauthenticated_client):
    response = unauthenticated_client.get("/expenses")

    assert response.status_code == 401


def test_expenses_reject_invalid_token(unauthenticated_client):
    unauthenticated_client.headers["Authorization"] = (
        "Bearer this-is-not-a-valid-token"
    )

    response = unauthenticated_client.get("/expenses")

    assert response.status_code == 401


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/users/login",
        json={
            "username": "test_user",
            "password": "wrong_password",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid username or password"
    }


def test_login_rejects_unknown_user(client):
    response = client.post(
        "/users/login",
        json={
            "username": "does_not_exist",
            "password": "password123",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid username or password"
    }

def test_register_user(client):
    response = client.post(
        "/users/register",
        json={
            "username": "new_user",
            "email": "new_user@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "new_user"
    assert response.json()["email"] == "new_user@example.com"
    assert "password" not in response.json()
    assert "hashed_password" not in response.json()


def test_register_duplicate_user(client, test_user):
    response = client.post(
        "/users/register",
        json={
            "username": test_user.username,
            "email": "different@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Username or email already exists"
    }


def test_expenses_reject_token_with_invalid_user_id(unauthenticated_client):
    token = create_access_token({"sub": "not-a-number"})

    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"

    response = unauthenticated_client.get("/expenses")

    assert response.status_code == 401

def test_create_expense_rejects_non_positive_amount(client):
    response = client.post(
        "/expenses",
        json={
            "title": "Invalid expense",
            "amount": "0",
            "category": "Test",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 422

def test_create_expense_rejects_invalid_expense_date(client):
    response = client.post(
        "/expenses",
        json={
            "title": "Invalid date expense",
            "amount": "100.00",
            "category": "Food",
            "expense_date": "not-a-date",
        },
    )

    assert response.status_code == 422

def test_create_expense_rejects_missing_fields(client):
    response = client.post(
        "/expenses",
        json={
            "title": "Incomplete expense",
        },
    )

    assert response.status_code == 422

def test_get_expenses_rejects_invalid_pagination(client):
    response = client.get("/expenses?limit=0")
    assert response.status_code == 422

    response = client.get("/expenses?limit=101")
    assert response.status_code == 422

    response = client.get("/expenses?offset=-1")
    assert response.status_code == 422

def test_patch_expense_updates_only_provided_field(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Original expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201
    expense_id = create_response.json()["id"]

    response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "750.00",
            "expected_version": create_response.json()["version"]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": expense_id,
        "title": "Original expense",
        "amount": "750.00",
        "category": "Food",
        "expense_date": "2026-09-20",
        "version": 2,

    }

def test_patch_expense_rejects_empty_update(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Original expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert create_response.status_code == 201
    expense_id = create_response.json()["id"]

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"expected_version": 1},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "At least one field must be provided"
    }

def test_register_login_and_create_expense(client):
    # Register a new user.
    register_response = client.post(
        "/users/register",
        json={
            "username": "lifecycle_user",
            "email": "lifecycle@example.com",
            "password": "password123",
        },
    )

    assert register_response.status_code == 201

    # Log in as the newly registered user.
    login_response = client.post(
        "/users/login",
        json={
            "username": "lifecycle_user",
            "password": "password123",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    # Authenticate as the newly registered user.
    client.headers["Authorization"] = f"Bearer {access_token}"

    # Create an expense using the authenticated identity.
    expense_response = client.post(
        "/expenses",
        json={
            "title": "First expense",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert expense_response.status_code == 201
    assert expense_response.json()["title"] == "First expense"
    assert expense_response.json()["amount"] == "250.00"
    assert expense_response.json()["category"] == "Food"
    assert expense_response.json()["expense_date"] == "2026-09-20"

def test_get_expense_summary(client):
    client.post(
        "/expenses",
        json={
            "title": "Lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-21",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2026-09-22",
        },
    )

    response = client.get("/expenses/summary")

    assert response.status_code == 200
    assert response.json() == {"total": "800.00"}

    response = client.get("/expenses/summary?category=Food")

    assert response.status_code == 200
    assert response.json() == {"total": "750.00"}

    response = client.get("/expenses/summary?category=Nonexistent")

    assert response.status_code == 200
    assert response.json() == {"total": "0.00"}

def test_expense_summary_only_includes_current_users_expenses(
    client,
    auth_headers,
):
    # User A creates an expense.
    response = client.post(
        "/expenses",
        json={
            "title": "User A expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 201

    # Create User B.
    response = client.post(
        "/users/register",
        json={
            "username": "user_b_summary",
            "email": "user_b_summary@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201

    # Log in as User B.
    response = client.post(
        "/users/login",
        json={
            "username": "user_b_summary",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    user_b_token = response.json()["access_token"]

    # Switch to User B.
    client.headers["Authorization"] = f"Bearer {user_b_token}"

    # User B creates their own expense.
    response = client.post(
        "/expenses",
        json={
            "title": "User B expense",
            "amount": "200.00",
            "category": "Transport",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 201

    # User B's summary must contain only User B's expense.
    response = client.get("/expenses/summary")

    assert response.status_code == 200
    assert response.json() == {"total": "200.00"}

    # Switch back to User A.
    client.headers["Authorization"] = auth_headers["Authorization"]

    # User A's summary must contain only User A's expense.
    response = client.get("/expenses/summary")

    assert response.status_code == 200
    assert response.json() == {"total": "500.00"}

def test_get_expense_summary_by_date_range(client):
    client.post(
        "/expenses",
        json={
            "title": "September lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-10",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "September groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "October dinner",
            "amount": "700.00",
            "category": "Food",
            "expense_date": "2026-10-05",
        },
    )
    client.post(
        "/expenses",
        json={
            "title": "September start",
            "amount": "100.00",
            "category": "Food",
            "expense_date": "2026-09-01",
        },
    )


    response = client.get(
        "/expenses/summary"
        "?from_date=2026-09-01&to_date=2026-09-30"
    )

    assert response.status_code == 200
    assert response.json() == {"total": "850.00"}

def test_get_expense_summary_rejects_invalid_date_range(client):
    response = client.get(
        "/expenses/summary"
        "?from_date=2026-09-30&to_date=2026-09-01"
    )

    assert response.status_code == 422

def test_get_expense_summary_requires_both_dates(client):
    response = client.get(
        "/expenses/summary"
        "?from_date=2026-09-01"
    )

    assert response.status_code == 422

    response = client.get(
        "/expenses/summary"
        "?to_date=2026-09-30"
    )

    assert response.status_code == 422

def test_get_expense_category_report_by_date_range(
    client,
    auth_headers,
):
    client.post(
        "/expenses",
        json={
            "title": "Lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-10",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus",
            "amount": "200.00",
            "category": "Transport",
            "expense_date": "2026-09-20",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Electricity",
            "amount": "1000.00",
            "category": "Bills",
            "expense_date": "2026-10-01",
        },
        headers=auth_headers,
    )

    response = client.get(
        "/expenses/report/categories",
        params={
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {"category": "Food", "total": "750.00"},
        {"category": "Transport", "total": "200.00"},
    ]

def test_expense_category_report_only_includes_current_users_expenses(
    client,
    auth_headers,
    test_user,
):
    client.post(
        "/expenses",
        json={
            "title": "User A Food",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
        headers=auth_headers,
    )

    client.post(
        "/users/register",
        json={
            "username": "reportuser",
            "email": "reportuser@example.com",
            "password": "password123",
        },
    )

    login_response = client.post(
        "/users/login",
        json={
            "username": "reportuser",
            "password": "password123",
        },
    )

    user_b_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    client.post(
        "/expenses",
        json={
            "title": "User B Food",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
        headers=user_b_headers,
    )

    response = client.get(
        "/expenses/report/categories",
        headers=user_b_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {"category": "Food", "total": "200.00"},
    ]

def test_expense_category_report_rejects_invalid_date_range(
    client,
    auth_headers,
):
    response = client.get(
        "/expenses/report/categories",
        params={"from_date": "2026-09-30"},
        headers=auth_headers,
    )

    assert response.status_code == 422

    response = client.get(
        "/expenses/report/categories",
        params={
            "from_date": "2026-09-30",
            "to_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422

def test_get_daily_expense_report_by_date_range(
    client,
    auth_headers,
):
    client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-10",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Electricity",
            "amount": "1000.00",
            "category": "Bills",
            "expense_date": "2026-09-30",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Outside Range",
            "amount": "700.00",
            "category": "Food",
            "expense_date": "2026-10-01",
        },
        headers=auth_headers,
    )

    response = client.get(
        "/expenses/report/daily",
        params={
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {"date": "2026-09-01", "total": "250.00"},
        {"date": "2026-09-10", "total": "500.00"},
        {"date": "2026-09-30", "total": "1000.00"},
    ]

def test_daily_expense_report_rejects_invalid_date_range(
    client,
    auth_headers,
):
    response = client.get(
        "/expenses/report/daily",
        params={"from_date": "2026-09-01"},
        headers=auth_headers,
    )

    assert response.status_code == 422

    response = client.get(
        "/expenses/report/daily",
        params={
            "from_date": "2026-09-30",
            "to_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422

def test_monthly_expense_report_by_categories_and_daily(
    client,
    auth_headers,
):
    client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2026-09-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-10",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Electricity",
            "amount": "1000.00",
            "category": "Bills",
            "expense_date": "2026-09-30",
        },
        headers=auth_headers,
    )
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2026" ,"month":"9",},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "month": 9,
        "total": "1750.00",
        "categories": [
        {
            "category": "Bills",
            "total": "1000.00",
        },
        {
            "category": "Food",
            "total": "700.00",
        },
        {
            "category": "Transport",
            "total": "50.00",
        },
        ]
    }
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2026" ,"month":"9","daily":"True"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "month": 9,
        "total": "1750.00",
        "daily": [
        {
            "date": "2026-09-01",
            "total": "250.00",
        },
        {
            "date": "2026-09-10",
            "total": "500.00",
        },
        {
            "date": "2026-09-30",
            "total": "1000.00",
        },
        ]
    }


def test_monthly_expense_report_empty_report(
    client,
    auth_headers
):
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2029" ,"month":"1","daily":"True"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2029,
        "month": 1,
        "total": "0",
        "daily": []
    }
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2029" ,"month":"1"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2029,
        "month": 1,
        "total": "0",
        "categories": []
    }

def test_monthly_expense_report_validates_year_and_month(
    client,
    auth_headers,
):
    response = client.get(
        "/expenses/report/monthly",
        params={"year": "0","month":"1"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    response = client.get(
        "/expenses/report/monthly",
        params={"year": "10000","month":"1"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    response = client.get(
        "/expenses/report/monthly",
        params={"year": "2026","month":"13","daily":"True"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    response = client.get(
        "/expenses/report/monthly",
        params={"year": "2026","month":"-9","daily":"True"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_monthly_expense_report_user_isolation(
    client,
    auth_headers,
):
    # User A creates an expense.
    response = client.post(
        "/expenses",
        json={
            "title": "User A expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 201

    # Create User B.
    response = client.post(
        "/users/register",
        json={
            "username": "user_b_summary",
            "email": "user_b_summary@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201

    # Log in as User B.
    response = client.post(
        "/users/login",
        json={
            "username": "user_b_summary",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    user_b_token = response.json()["access_token"]

    # Switch to User B.
    client.headers["Authorization"] = f"Bearer {user_b_token}"

    # User B creates their own expense.
    response = client.post(
        "/expenses",
        json={
            "title": "User B expense",
            "amount": "200.00",
            "category": "Transport",
            "expense_date": "2026-09-20",
        },
    )

    assert response.status_code == 201

    # User B's summary must contain only User B's expense.
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2026","month":"9"},
    )

    assert response.status_code == 200
    assert response.json() == {"year":2026,"month":9,"total":"200.00","categories":[{"category":"Transport","total":"200.00"}]}

    # Switch back to User A.
    client.headers["Authorization"] = auth_headers["Authorization"]

    # User A's summary must contain only User A's expense.
    response = client.get("/expenses/report/monthly",params={"year":"2026","month":"9","daily":"True"})

    assert response.status_code == 200
    assert response.json() == {"year":2026,"month":9,"total":"500.00","daily":[{"date":"2026-09-20","total":"500.00"}]}


def test_monthly_expense_report_month_bound_aries(
    client,
    auth_headers
):
    client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2027-01-01",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-12-10",
        },
        headers=auth_headers,
    )

    client.post(
        "/expenses",
        json={
            "title": "Electricity",
            "amount": "1000.00",
            "category": "Bills",
            "expense_date": "2026-12-30",
        },
        headers=auth_headers,
    )
    client.post(
        "/expenses",
        json={
            "title": "New year party",
            "amount": "500.00",
            "category": "Fun",
            "expense_date": "2026-12-31",
        },
        headers=auth_headers,
    )
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2026" ,"month":"12",},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "month": 12,
        "total": "2200.00",
        "categories": [
        {
            "category": "Bills",
            "total": "1000.00",
        },
        {
            "category": "Food",
            "total": "700.00",
        },
        {
            "category": "Fun",
            "total": "500.00",
        },
        ]
    }
    response = client.get(
        "/expenses/report/monthly",
        params={"year":"2026" ,"month":"12","daily":"True"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "month": 12,
        "total": "2200.00",
        "daily": [
        {
            "date": "2026-12-01",
            "total": "200.00",
        },
        {
            "date": "2026-12-10",
            "total": "500.00",
        },
        {
            "date": "2026-12-30",
            "total": "1000.00",
        },
        {
            "date": "2026-12-31",
            "total": "500.00",
        },
        ]
    }

def test_create_expenses_in_bulk(
    client,
    auth_headers
):
    input_data = [
        {
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        {
            "title": "Bus",
            "amount": "50.00",
            "category": "Transport",
            "expense_date": "2027-01-01",
        },
        {
            "title": "Groceries",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-12-10",
        },
        {
            "title": "Electricity",
            "amount": "1000.00",
            "category": "Bills",
            "expense_date": "2026-12-30",
        },
    ]
    response = client.post(
        "/expenses/bulk",
        json=input_data,
        headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
    )
    assert response.status_code == 201

    data = response.json()

    assert len(data) == len(input_data)
    assert all(isinstance(expense["id"], int) for expense in data)
    assert all(expense["id"] > 0 for expense in data)
    generated={"id","version"}
    for sent, received in zip(input_data, data):
        stripped = {k:v for k,v in received.items() if k not in  generated}
        assert stripped == sent

def test_create_expenses_in_bulk_validation(
    client,
    auth_headers
):
    response = client.post(
        "/expenses/bulk",
        json=[
        {
            "title": "Breakfast",
            "amount": "-200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        ],
        headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
    )
    assert response.status_code == 422
    response = client.post(
        "/expenses/bulk",
        json=[
        {
            "title": "",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        ],
        headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
    )
    assert response.status_code == 422
    response = client.post(
        "/expenses/bulk",
        json=[
        {
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        {
            "title": "Bus",
            "amount": "50.00",
        },
        ],
        headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
    )
    assert response.status_code == 422

    response = client.post(
        "/expenses/bulk",
        json=[
        {},
        ],
        headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
    )
    assert response.status_code == 422




def test_bulk_create_rolls_back_on_database_error(
    client,
    auth_headers,
    test_user,
    db,
):
    valid_expense_1 = Expense(
        title="Breakfast",
        amount=200,
        category="Food",
        user_id=test_user.id,
        expense_date=date(2026, 12, 1),
)

    valid_expense_2 = Expense(
        title="Bus",
        amount=50,
        category="Transport",
        user_id=test_user.id,
        expense_date=date(2027, 1, 1),
)

    invalid_expense = Expense(
        title="Invalid",
        amount=-10,
        category="Test",
        user_id=test_user.id,
        expense_date=date(2026, 12, 2),
)
    try:
        db.add_all([
            valid_expense_1,
            valid_expense_2,
            invalid_expense,
        ])
        db.flush()
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    count = (
        db.query(Expense)
        .filter(Expense.user_id == test_user.id)
        .count()
    )

    assert count == 0


def test_login_success(client):
    # ---- registration -------------------------------------------------
    register_resp = client.post(
        "/users/register",
        json={
            "username": "usertest12",
            "email": "usertest@testuser.com",
            "password": "UserTest12",
        },
        headers={"Content-Type": "application/json"},
    )
    assert register_resp.status_code == 201

    # ---- login --------------------------------------------------------
    login_resp = client.post(
        "/users/login",
        json={
            "username": "usertest12",
            "password": "UserTest12",
        },
        headers={"Content-Type": "application/json"},
    )
    assert login_resp.status_code == 200

    payload = login_resp.json()
    assert "access_token" in payload
    assert payload.get("token_type") == "bearer"

    # ---- JWT verification ---------------------------------------------
    decoded = jwt.decode(
        payload["access_token"],
        settings.secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
    )
    assert decoded["token_version"] == 0

    # ---- cleanup -------------------------------------------------------
    # (add a delete request or fixture teardown here)

def test_password_change_invalidates_old_token(
    client
):
    register=client.post(
        "/users/register",
        json={
            "username": "Test_1",
            "email": "testuser@test.com",
            "password": "TestUser123",
        },
    )
    assert register.status_code == 201
    login=client.post(
        "/users/login",
        json={
            "username":"Test_1",
            "password": "TestUser123",
        },
    )
    assert login.status_code == 200
    access_token1 = login.json()["access_token"]

    changepwd=client.post(
        "/users/change-password",
        json={
            "current_password":"TestUser123",
            "new_password":"UserTest123",
        },
        headers={
            "Authorization": f"Bearer {access_token1}"
        },
    )
    assert changepwd.status_code == 200

    create=client.post(
        "/expenses",
        json={
            "title": "Lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-10-06",
        },
        headers={
            "Authorization": f"Bearer {access_token1}"
        },
    )
    assert create.status_code == 401

    login=client.post(
        "/users/login",
        json={
            "username":"Test_1",
            "password": "UserTest123",
        },
    )
    assert login.status_code == 200
    access_token2 = login.json()["access_token"]

    create=client.post(
        "/expenses",
        json={
            "title": "Lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-10-06",
        },
        headers={
            "Authorization": f"Bearer {access_token2}"
        },
    )
    assert create.status_code == 201

def test_password_change_rolls_back_on_database_error(
    test_user,
    db,
):
    hashed_password = test_user.hashed_password
    token_version = test_user.token_version

    db.commit()

    pwdchange = PasswordChange(
        current_password="TestUser123",
        new_password="UserTest123",
    )

    new_hashed_password = hash_password(pwdchange.new_password)

    test_user.hashed_password = new_hashed_password
    test_user.token_version = None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("Expected IntegrityError")

    db.refresh(test_user)

    assert test_user.hashed_password == hashed_password
    assert test_user.token_version == token_version

def test_password_hashing_at_rest(client,db):
    password="plain-text-password"
    response=client.post(
        "/users/register",
        json={
            "username":"testuser",
            "email": "testuser@testuser.com",
            "password":password,
        }
    )
    assert response.status_code == 201

    user_record=db.query(User).filter(User.username == "testuser").first()
    assert user_record is not None

    assert user_record.hashed_password != password

    assert verify_password(password, user_record.hashed_password) is True

def test_delete_expense_database_error(
    client,
    db,

):
    response=client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
    )
    assert response.status_code == 201

    expense_id = response.json()["id"]

    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.delete(f"/expenses/{expense_id}")

    assert response.status_code == 500

    response=client.get(f"/expenses/{expense_id}")
    assert response.status_code == 200

def test_patch_expense_rejects_null(
    client,
    db
):
    response = client.post("/expenses", json={
        "title": "Breakfast",
        "amount": "200.00",
        "category": "Food",
        "expense_date": "2026-12-01",
    })
    assert response.status_code == 201
    expense_id = response.json()["id"]

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": None, "expected_version": 1},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": "Breakfast","amount": "200.00","category":None,"expected_version": 1},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": None,"amount": None,"category": None,"expense_date": None,"expected_version": 1},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": "Breakfast","amount": "200.00","category": "Food","expense_date": None,"expected_version": 1},
    )
    assert response.status_code == 422

def test_create_expense_database_error(
    client,
    db,
    auth_headers
):
    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.post(
            "/expenses",
            json={
                "title": "Breakfast",
                "amount": "200.00",
                "category": "Food",
                "expense_date": "2026-12-01",
            },
            headers=auth_headers,
        )

    assert response.status_code == 500

    response = client.get("/expenses", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []

def test_update_expense_database_error(
    client,
    db,
    auth_headers
):
    response = client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    expense_id = response.json()["id"]

    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.put(
            f"/expenses/{expense_id}",
            json={
                "title": "Untitled",
                "amount": "2000.00",
                "category": "Food",
                "expense_date": "2026-12-01",
                "expected_version": 1
            },
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Breakfast"

def test_patch_expense_database_error(
    client,
    db,
    auth_headers
):
    response = client.post(
        "/expenses",
        json={
            "title": "Breakfast",
            "amount": "200.00",
            "category": "Food",
            "expense_date": "2026-12-01",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    expense_id = response.json()["id"]

    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.patch(
            f"/expenses/{expense_id}",
            json={
                "title": "Dinner",
                "amount": "2000.00",
                "expected_version": 1
            },
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Breakfast"

def test_create_expense_bulk_database_error(
    client,
    db,
    auth_headers
):
    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.post(
            "/expenses/bulk",
            json=[
                {
                    "title": "Bulk Breakfast",
                    "amount": "100.00",
                    "category": "Food",
                    "expense_date": "2026-12-01",
                },
                {
                    "title": "Bulk Lunch",
                    "amount": "250.00",
                    "category": "Food",
                    "expense_date": "2026-12-01",
                },
            ],
            headers={**auth_headers, "Idempotency-Key": "test-bulk-create-success"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}

    response = client.get("/expenses", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []

def test_monthly_expense_report_december_9999_edge_case(
    client,
    auth_headers
):
    response = client.get(
        "/expenses/report/monthly",
        params={"year": 9999, "month": 12},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "december 9999" in response.json()["detail"].lower()

def test_get_expenses_deterministic_pagination(client, auth_headers):
    created_ids = []
    for i in range(3):
        response = client.post(
            "/expenses",
            json={
                "title": f"Expense {i + 1}",
                "amount": "150.00",
                "category": "Food",
                "expense_date": "2026-12-01",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    response = client.get("/expenses?limit=2&offset=0", headers=auth_headers)
    assert response.status_code == 200
    page_1 = response.json()
    assert len(page_1) == 2

    response = client.get("/expenses?limit=2&offset=2", headers=auth_headers)
    assert response.status_code == 200
    page_2 = response.json()
    assert len(page_2) == 1

    all_returned_ids = [e["id"] for e in (page_1 + page_2)]

    relevant_ids = [eid for eid in all_returned_ids if eid in created_ids]

    assert relevant_ids == sorted(relevant_ids)

def test_token_missing_exp_claim(
    client,
    test_user,
    auth_headers
):
    # sub and token_version but no exp
    bad_payload = {
        "sub": str(test_user.id),
        "token_version": test_user.token_version,
    }
    bad_token = jwt.encode(bad_payload, settings.secret_key.get_secret_value(), algorithm=ALGORITHM)

    # Attempt to access a protected endpoint using the bad token
    response = client.get(
        "/expenses/me",
        headers={"Authorization": f"Bearer {bad_token}"},
    )

    assert response.status_code == 401

def test_expired_token(
    client,
    test_user
):
    #Ensure a correctly signed token with a past expiration timestamp is rejected with 401
    payload = {
        "sub": str(test_user.id),
        "token_version": test_user.token_version,
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    #and this is the under lieing way to
    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=ALGORITHM)

    response = client.get(
        "/expenses",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_tampered_signature(
    client,
    test_user
):
    #Ensure a token with a modified signature fails signature verification with 401
    # creating token using helper function we created
    token = create_access_token(
        {"sub": str(test_user.id), "token_version": test_user.token_version}
    )

    # Tamper with the signature component (the third part after the second dot)
    parts = token.split(".")
    parts[2] = parts[2][:-4] + "XXXX"
    tampered_token = ".".join(parts)

    response = client.get(
        "/expenses",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert response.status_code == 401

def test_settings_rejects_short_secret():
    try:
        Settings(secret_key="too_short_secret_string_less_than_sixty_four_chars")
        assert False, "Expected ValidationError was not raised"
    except ValidationError:
        pass

def test_settings_masks_secret_key():
    valid_secret = "a" * 64
    settings = Settings(secret_key=valid_secret)
    assert valid_secret not in str(settings.secret_key)


def test_login_rate_limit(client):
    login_data = {
        "username": "unknown_user",
        "password": "wrongpassword123",
    }

    # The first five requests reach the login handler.
    for _ in range(5):
        response = client.post("/users/login", json=login_data)
        assert response.status_code == 401

    # The sixth request exceeds the limit.
    response = client.post("/users/login", json=login_data)
    assert response.status_code == 429

    # Verify the Retry-After header exists and is a positive integer
    retry_after = response.headers.get("Retry-After")
    assert retry_after is not None, "Retry-After header is missing"
    assert int(retry_after) > 0, "Retry-After value must be a positive integer"

def test_update_expense_rejects_stale_version(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Original expense",
            "amount": "500.00",
            "category": "Food",
            "expense_date": "2026-10-15",
        },
    )

    assert create_response.status_code == 201
    expense_id = create_response.json()["id"]
    original_version = create_response.json()["version"]

    # First client updates the expense successfully.
    update_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "600.00",
            "expected_version": original_version,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["version"] == original_version + 1

    # A second client submits an update based on stale data.
    stale_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "700.00",
            "expected_version": original_version,
        },
    )

    assert stale_response.status_code == 409
    assert "modified by another request" in stale_response.json()["detail"]

    # Confirm that the stale request did not overwrite the newer value.
    get_response = client.get(f"/expenses/{expense_id}")

    assert get_response.status_code == 200
    assert get_response.json()["amount"] == "600.00"
    assert get_response.json()["version"] == original_version + 1

def test_expense_update_returns_conflict_on_stale_data(
    client, db, monkeypatch
):
    for method in ["put", "patch"]:
        create_response = client.post(
            "/expenses",
            json={
                "title": "Original expense",
                "amount": "500.00",
                "category": "Food",
                "expense_date": "2026-10-15",
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()
        expense_id = created["id"]

        def raise_stale_data_error():
            raise StaleDataError("Simulated concurrent update")

        monkeypatch.setattr(db, "commit", raise_stale_data_error)

        if method == "put":
            response = client.put(
                f"/expenses/{expense_id}",
                json={
                    "title": "Updated expense",
                    "amount": "600.00",
                    "category": "Food",
                    "expense_date": "2026-10-15",
                    "expected_version": created["version"],
                },
            )
        else:
            response = client.patch(
                f"/expenses/{expense_id}",
                json={
                    "amount": "600.00",
                    "expected_version": created["version"],
                },
            )

        assert response.status_code == 409
        assert "modified by another request" in response.json()["detail"]

        # The failed update must not change the stored expense.
        monkeypatch.undo()

        get_response = client.get(f"/expenses/{expense_id}")

        assert get_response.status_code == 200
        assert get_response.json()["amount"] == "500.00"
        assert get_response.json()["version"] == created["version"]


def test_bulk_create_idempotency_replay(client, auth_headers, db, test_user):
    """Test that retrying with the same key and payload replays the original response."""
    input_data = [
        {
            "title": "Idempotent Coffee",
            "amount": "15.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]
    headers = {**auth_headers, "Idempotency-Key": "key-replay-test"}

    # First request (creates the expenses)
    response_1 = client.post("/expenses/bulk", json=input_data, headers=headers)
    assert response_1.status_code == 201
    data_1 = response_1.json()

    # Second request (should replay from cache)
    response_2 = client.post("/expenses/bulk", json=input_data, headers=headers)
    assert response_2.status_code == 201
    data_2 = response_2.json()

    # Responses should be identical
    assert data_1 == data_2

    # Verify that exactly ONE idempotency record was stored for this key/user
    op_count = (
        db.query(IdempotencyOperation)
        .filter(
            IdempotencyOperation.user_id == test_user.id,
            IdempotencyOperation.idempotency_key == "key-replay-test",
        )
        .count()
    )
    assert op_count == 1

    response_3=client.post(
        "/expenses/bulk", json=input_data , headers={**auth_headers,"Idempotency-Key":"key-replay-test-2"}
    )
    assert response_3.status_code == 201

    op_count = (
        db.query(IdempotencyOperation)
        .filter(
            IdempotencyOperation.user_id == test_user.id,
        )
        .count()
    )
    assert op_count == 2

def test_bulk_create_idempotency_conflict(client, auth_headers):
    """Test that reusing an idempotency key with a different payload returns 409 Conflict."""
    headers = {**auth_headers, "Idempotency-Key": "key-conflict-test"}

    payload_a = [
        {
            "title": "Item A",
            "amount": "50.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]
    payload_b = [
        {
            "title": "Item B",
            "amount": "100.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]

    # First request with payload A
    response_1 = client.post("/expenses/bulk", json=payload_a, headers=headers)
    assert response_1.status_code == 201

    # Second request with payload B using the same key
    response_2 = client.post("/expenses/bulk", json=payload_b, headers=headers)
    assert response_2.status_code == 409
    assert "different request payload" in response_2.json()["detail"]

def test_bulk_create_idempotency_user_scope(client, auth_headers, db, test_user):
    input_data = [
        {
            "title": "User Scope Item",
            "amount": "25.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]
    shared_key = "multi-tenant-key-123"
    headers_1 = {**auth_headers, "Idempotency-Key": shared_key}

    # 1. First user sends request with the shared key
    response_1 = client.post("/expenses/bulk", json=input_data, headers=headers_1)
    assert response_1.status_code == 201

    # 2. Create a second distinct user in the database
    user_2 = User(
        username="other_user",
        email="other_user@example.com",
        hashed_password=hash_password("other_password"),
    )
    db.add(user_2)
    db.flush()
    db.commit()

    # Generate auth headers for the second user
    token_2 = create_access_token(
        {"sub": str(user_2.id), "token_version": user_2.token_version}
    )
    headers_2 = {
        "Authorization": f"Bearer {token_2}",
        "Idempotency-Key": shared_key,
    }

    # 3. Second user sends request with the EXACT SAME key
    response_2 = client.post("/expenses/bulk", json=input_data, headers=headers_2)
    assert response_2.status_code == 201  # Should succeed independently!

    # 4. Verify that two distinct operation records exist for this key across users
    op_count = (
        db.query(IdempotencyOperation)
        .filter(IdempotencyOperation.idempotency_key == shared_key)
        .count()
    )
    assert op_count == 2

def test_bulk_create_missing_or_invalid_idempotency_key(client, auth_headers):
    """Test validation rules for the Idempotency-Key header."""
    input_data = [
        {
            "title": "Test",
            "amount": "10.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]

    # 1. Missing header
    response = client.post("/expenses/bulk", json=input_data, headers=auth_headers)
    assert response.status_code == 400
    assert "Idempotency-Key header is required" in response.json()["detail"]

    # 2. Empty/Whitespace header
    response = client.post(
        "/expenses/bulk",
        json=input_data,
        headers={**auth_headers, "Idempotency-Key": "   "},
    )
    assert response.status_code == 400

    # 3. Key too long (> 255 chars)
    long_key = "a" * 256
    response = client.post(
        "/expenses/bulk",
        json=input_data,
        headers={**auth_headers, "Idempotency-Key": long_key},
    )
    assert response.status_code == 400
    assert "must not exceed 255 characters" in response.json()["detail"]


def test_bulk_create_rollback_and_retry(
    client,
    auth_headers,
    db,
    test_user,
):
    input_data=[
        {
            "title":"Lunch",
            "amount":"250.00",
            "category":"Food",
            "expense_date":"2026-12-10"
        },
    ]
    header={**auth_headers,"Idempotency-Key":"test-idempotency-key"}

    with patch.object(db, "commit", side_effect=SQLAlchemyError("boom")):
        response = client.post("/expenses/bulk", json=input_data, headers=header)
    assert response.status_code == 500

    op_count = (
        db.query(IdempotencyOperation)
        .filter(
            IdempotencyOperation.user_id == test_user.id,
            IdempotencyOperation.idempotency_key == "test-idempotency-key",
        )
        .count()
    )
    assert not op_count

    response = client.post("/expenses/bulk", json=input_data, headers=header)
    assert response.status_code == 201

    op_count = (
        db.query(IdempotencyOperation)
        .filter(
            IdempotencyOperation.user_id == test_user.id,
            IdempotencyOperation.idempotency_key == "test-idempotency-key",
        )
        .count()
    )
    assert op_count == 1


def test_bulk_hash_normalization(
    client,
    auth_headers,
):
    input_data=[
        {
            "title":"Lunch",
            "amount":"250.00",
            "category":"Food",
            "expense_date":"2026-12-10"
        },
    ]
    header={**auth_headers,"Idempotency-Key":"test-idempotency-key"}

    response=client.post("/expenses/bulk",json=input_data,headers=header,)
    assert response.status_code==201
    data1=response.json()

    input_data=[
        {
            "title":"Lunch",
            "amount":"250.0",
            "category":"Food",
            "expense_date":"2026-12-10"
        },
    ]
    header={**auth_headers,"Idempotency-Key":"test-idempotency-key"}

    response=client.post("/expenses/bulk",json=input_data,headers=header,)
    assert response.status_code==201
    data2=response.json()

    assert data1 == data2

def test_bulk_create_other_integrity_error_bubbles_up(client, auth_headers, db):
    input_data = [
        {
            "title": "Unrelated Constraint Item",
            "amount": "10.00",
            "category": "Food",
            "expense_date": "2026-12-10",
        }
    ]
    header = {**auth_headers, "Idempotency-Key": "some-key"}

    # Mock the database error's underlying driver exception to have a different constraint name
    mock_orig = MagicMock()
    mock_orig.diag.constraint_name =(
        "some_completely_unrelated_constraint"
    )

    # Construct the IntegrityError with the mock origin
    integrity_exc = IntegrityError("statement", "params", mock_orig)

    # Allow auth and initial lookup autoflushes to pass, then raise on the insert flush
    original_flush = db.flush
    call_count = 0

    def mock_flush(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise integrity_exc
        return original_flush(*args, **kwargs)

    with patch.object(db, "flush", side_effect=mock_flush):
        response = client.post("/expenses/bulk", json=input_data, headers=header)

    # It should bubble up as a 500 error instead of being caught as an idempotency conflict
    assert response.status_code == 500

def test_bulk_create_same_key_concurrently(independent_session_factory):
    suffix = uuid4().hex
    key = f"concurrent-{suffix}"

    payload = [
        {
            "title": f"Concurrent Coffee {suffix}",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-12-05",
        }
    ]

    # Create a user that is committed and visible to both request sessions.
    with independent_session_factory() as setup_db:
        user = User(
            username=f"race_{suffix[:12]}",
            email=f"race_{suffix}@example.com",
            hashed_password=hash_password("test-password-123"),
            token_version=0,
        )
        setup_db.add(user)
        setup_db.commit()
        setup_db.refresh(user)
        user_id = user.id

    token = create_access_token(
        {
            "sub": str(user_id),
            "token_version": 0,
        }
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": key,
    }

    lookup_barrier = Barrier(2)

    def override_get_db():
        with SynchronizedSession(
            bind=test_engine,
            lookup_barrier=lookup_barrier,
            expire_on_commit=False,
        ) as request_db:
            yield request_db

    # Preserve any previous override so this test doesn't affect other tests.
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    try:
        # Separate TestClients avoid sharing one HTTP client across threads.

        with TestClient(app) as client_a, TestClient(app) as client_b, ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(
                client_a.post,
                "/expenses/bulk",
                json=payload,
                headers=headers,
            )
            future_b = executor.submit(
                client_b.post,
                "/expenses/bulk",
                json=payload,
                headers=headers,
            )

            response_a = future_a.result(timeout=20)
            response_b = future_b.result(timeout=20)

        # Both callers should receive the same successful outcome.
        assert response_a.status_code == 201
        assert response_b.status_code == 201
        assert response_a.json() == response_b.json()

        # Both responses should refer to the same created expense.
        expense_ids_a = [item["id"] for item in response_a.json()]
        expense_ids_b = [item["id"] for item in response_b.json()]
        assert expense_ids_a == expense_ids_b

        # Verify the durable database state using another session.
        with independent_session_factory() as verify_db:
            operation_count = verify_db.scalar(
                select(func.count())
                .select_from(IdempotencyOperation)
                .where(
                    IdempotencyOperation.user_id == user_id,
                    IdempotencyOperation.idempotency_key == key,
                )
            )

            expense_count = verify_db.scalar(
                select(func.count())
                .select_from(Expense)
                .where(
                    Expense.user_id == user_id,
                    Expense.title == f"Concurrent Coffee {suffix}",
                )
            )

        assert operation_count == 1
        assert expense_count == len(payload)

    finally:
        # Restore the dependency override even if an assertion fails.
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

        # This test commits real data, so clean up its records explicitly.
        with independent_session_factory() as cleanup_db:
            cleanup_db.execute(
                delete(IdempotencyOperation).where(
                    IdempotencyOperation.user_id == user_id
                )
            )
            cleanup_db.execute(
                delete(Expense).where(Expense.user_id == user_id)
            )
            cleanup_db.execute(
                delete(User).where(User.id == user_id)
            )
            cleanup_db.commit()

def test_expense_update_empty_title_rejected(client):
    """PUT and PATCH must reject empty titles."""

    create_response = client.post(
        "/expenses",
        json={
            "title": "Lunch",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-10-23",
        },
    )

    assert create_response.status_code == 201

    expense = create_response.json()
    expense_id = expense["id"]
    version = expense["version"]

    # PUT: all required fields are valid except the title.
    put_response = client.put(
        f"/expenses/{expense_id}",
        json={
            "title": "",
            "amount": "250.00",
            "category": "Food",
            "expense_date": "2026-10-23",
            "expected_version": version,
        },
    )

    assert put_response.status_code == 422
    assert any(
        error["loc"][-1] == "title"
        for error in put_response.json()["detail"]
    )

    # PATCH: the version is valid, but the supplied title is empty.
    patch_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "title": "",
            "expected_version": version,
        },
    )

    assert patch_response.status_code == 422
    assert any(
        error["loc"][-1] == "title"
        for error in patch_response.json()["detail"]
    )