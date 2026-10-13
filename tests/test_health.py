def test_health_check_success(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status":"ok"}

def test_health_check_fails_when_db_is_down(
    client,
    broken_db,
    monkeypatch,
):
    # 1. Import the original dependency function
    from awesome_project.database import get_db
    from awesome_project.main import app

    # 2. Tell FastAPI to use the broken session instead///doesn't require app.dependency.overrides.clear() at the end
    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        lambda: broken_db,
    )

    # 3. Now call the endpoint
    response = client.get("/health")         # use your real path

    assert response.status_code == 503
    assert response.json() == {"detail":"Database unavailable"}