import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.partner import Partner
from app.models.rate_card import RateCard
from app.main import app


import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.partner import Partner
from app.models.rate_card import RateCard
from app.main import app


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def finance_exec_token():
    return create_access_token({
        "sub": "finance_exec@company-a.com",
        "role": "finance_exec"
    })


@pytest.fixture
def cofounder_token():
    return create_access_token({
        "sub": "cofounder@company-a.com",
        "role": "cofounder"
    })


@pytest.fixture
def finance_exec_headers(finance_exec_token):
    return {
        "Authorization": f"Bearer {finance_exec_token}",
        "X-CSRF-Token": "test-csrf-token"
    }


@pytest.fixture
def finance_exec_cookies(finance_exec_token):
    return {
        "access_token": finance_exec_token,
        "csrf_token": "test-csrf-token"
    }


@pytest.fixture
def cofounder_headers(cofounder_token):
    return {
        "Authorization": f"Bearer {cofounder_token}",
        "X-CSRF-Token": "test-csrf-token"
    }


@pytest.fixture
def cofounder_cookies(cofounder_token):
    return {
        "access_token": cofounder_token,
        "csrf_token": "test-csrf-token"
    }
