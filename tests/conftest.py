import os 
from dotenv import load_dotenv

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from awesome_project.database import get_db
from awesome_project.main import app

load_dotenv()
TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

test_engine = create_engine(TEST_DATABASE_URL)

@pytest.fixture
def client():
    with test_engine.connect() as connection:
        transaction = connection.begin()
        
        db = Session(
            bind = connection,
            join_transaction_mode="create_savepoint"
        )
        
        def get_test_db():
            yield db 
        
        app.dependency_overrides[get_db] = get_test_db
    
        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.pop(get_db,None)
            db.close()
            transaction.rollback()