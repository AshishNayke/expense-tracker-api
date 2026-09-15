from awesome_project.security import create_access_token


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
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Test lunch"
    assert data["amount"] == "150.00"
    assert data["category"] == "Food"
    assert "id" in data


def test_get_expense(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Test dinner",
            "amount": "250.00",
            "category": "Food",
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
        },
    )

    assert update_response.status_code == 200

    data = update_response.json()

    assert data["id"] == expense_id
    assert data["title"] == "Updated dinner"
    assert data["amount"] == "350.00"
    assert data["category"] == "Restaurant"

    get_response = client.get(f"/expenses/{expense_id}")

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Updated dinner"
    assert get_response.json()["amount"] == "350.00"
    assert get_response.json()["category"] == "Restaurant"


def test_update_expense_not_found(client):
    response = client.put(
        "/expenses/999999",
        json={
            "title": "Updated dinner",
            "amount": "350.00",
            "category": "Restaurant",
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
        },
    )

    assert create_response.status_code == 201

    expense_id = create_response.json()["id"]

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

    get_response = client.get(f"/expenses/{expense_id}")

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Original dinner"
    assert get_response.json()["amount"] == "300.00"
    assert get_response.json()["category"] == "Food"


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
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Bus ticket",
            "amount": "50.00",
            "category": "Transport",
        },
    )

    client.post(
        "/expenses",
        json={
            "title": "Restaurant",
            "amount": "300.00",
            "category": "Food",
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
    }

def test_patch_expense_rejects_empty_update(client):
    create_response = client.post(
        "/expenses",
        json={
            "title": "Original expense",
            "amount": "500.00",
            "category": "Food",
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
        },
    )

    assert expense_response.status_code == 201
    assert expense_response.json()["title"] == "First expense"
    assert expense_response.json()["amount"] == "250.00"
    assert expense_response.json()["category"] == "Food"