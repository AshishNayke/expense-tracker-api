import os
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from awesome_project.database import get_db
from awesome_project.main import app
from awesome_project.models import User
from awesome_project.rate_limiting import limiter
from awesome_project.security import create_access_token, hash_password

load_dotenv()

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

test_engine = create_engine(TEST_DATABASE_URL)

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()

@pytest.fixture
def independent_session_factory():
    return sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )

@pytest.fixture
def db():
    with test_engine.connect() as connection:
        transaction = connection.begin()

        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            session.close()
            transaction.rollback()

@pytest.fixture
def broken_db():
    mock_session = MagicMock()
    mock_session.execute.side_effect = SQLAlchemyError("Database is down")

    try:
        yield mock_session
    finally:
        pass

@pytest.fixture
def test_user(db):
    user = User(
        username="test_user",
        email="test_user@example.com",
        hashed_password=hash_password("test_password"),
    )

    db.add(user)
    db.flush()
    db.commit()

    return user


@pytest.fixture
def auth_headers(test_user):
    access_token = create_access_token(
        {"sub": str(test_user.id), "token_version": test_user.token_version}
    )

    return {
        "Authorization": f"Bearer {access_token}",
    }


@pytest.fixture
def client(db, auth_headers):
    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db

    try:
        with TestClient(app, headers=auth_headers) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def unauthenticated_client(db):
    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)