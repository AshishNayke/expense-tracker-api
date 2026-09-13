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

    assert response.status_code == 200

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

    assert create_response.status_code == 200

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

    assert create_response.status_code == 200

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

    assert create_response.status_code == 200

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
