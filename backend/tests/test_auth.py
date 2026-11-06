import pytest
from app.models.login_attempt import LoginAttempt


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "leakcheck-api"


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "finance_exec@company-a.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "csrf_token" in data
    assert data["user"]["email"] == "finance_exec@company-a.com"
    assert data["user"]["role"] == "finance_exec"
    assert "access_token" in response.cookies
    assert "csrf_token" in response.cookies


def test_login_invalid_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "finance_exec@company-a.com",
            "password": "WrongPassword!"
        }
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@company-a.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 401


def test_login_rate_limiting(client, db_session):
    # Simulate 5 failed attempts from test IP
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "rate_limited_test@company-a.com",
                "password": "BadPassword"
            }
        )

    # 6th attempt should be blocked with 429 Too Many Requests
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "rate_limited_test@company-a.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 429
    assert "Too many failed login attempts" in response.json()["detail"]

    # Clean up test attempts so other tests are not impacted
    db_session.query(LoginAttempt).filter(
        LoginAttempt.email == "rate_limited_test@company-a.com"
    ).delete()
    db_session.commit()


def test_get_current_user_me(client, finance_exec_cookies):
    response = client.get("/api/v1/auth/me", cookies=finance_exec_cookies)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "finance_exec@company-a.com"
    assert data["role"] == "finance_exec"


def test_logout(client, finance_exec_cookies):
    response = client.post("/api/v1/auth/logout", cookies=finance_exec_cookies)
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully signed out."
