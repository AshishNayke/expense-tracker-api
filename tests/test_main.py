from datetime import date
from unittest.mock import patch

import jwt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from awesome_project.config import settings
from awesome_project.models import Expense
from awesome_project.schemas import PasswordChange
from awesome_project.security import ALGORITHM, create_access_token, hash_password


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
        },
    )

    assert update_response.status_code == 200

    data = update_response.json()

    assert data["id"] == expense_id
    assert data["title"] == "Updated dinner"
    assert data["amount"] == "350.00"
    assert data["category"] == "Restaurant"
    assert data["expense_date"] == "2026-09-21"

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
        },
    )
    assert response.status_code == 404

    # User B cannot partially modify User A's expense.
    response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": "9999.00",
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
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": expense_id,
        "title": "Original expense",
        "amount": "750.00",
        "category": "Food",
        "expense_date": "2026-09-20",
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
        json={},
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
        headers=auth_headers,
    )
    assert response.status_code == 201

    data = response.json()

    assert len(data) == len(input_data)
    assert all(isinstance(expense["id"], int) for expense in data)
    assert all(expense["id"] > 0 for expense in data)
    generated={"id"}
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
        headers=auth_headers,
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
        headers=auth_headers,
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
        headers=auth_headers,
    )
    assert response.status_code == 422

    response = client.post(
        "/expenses/bulk",
        json=[
        {},
        ],
        headers=auth_headers,
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
        settings.secret_key,
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
        json={"title": None},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": "Breakfast","amount": "200.00","category":None},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": None,"amount": None,"category": None,"expense_date": None},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/expenses/{expense_id}",
        json={"title": "Breakfast","amount": "200.00","category": "Food","expense_date": None},
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
            headers=auth_headers,
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
