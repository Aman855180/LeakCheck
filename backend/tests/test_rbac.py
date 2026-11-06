import pytest


def test_unauthenticated_request_rejected(client):
    response = client.get("/api/v1/rate-cards/")
    assert response.status_code == 401


def test_cofounder_can_view_rate_cards(client, cofounder_cookies):
    response = client.get("/api/v1/rate-cards/", cookies=cofounder_cookies)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_finance_exec_can_create_rate_card(client, finance_exec_cookies, finance_exec_headers):
    # Pass headers with X-CSRF-Token and cookies with csrf_token/access_token
    headers = {"X-CSRF-Token": finance_exec_cookies["csrf_token"]}
    response = client.post(
        "/api/v1/rate-cards/",
        json={
            "partner_id": "flipkart",
            "channel": "marketplace",
            "rule_type": "flipkart_standard",
            "params_json": {
                "commission_pct": 12.0,
                "fixed_fee": 25.00,
                "forward_shipping_fee": 70.00
            },
            "valid_from": "2026-02-01",
            "valid_until": None,
            "is_active": True
        },
        cookies=finance_exec_cookies,
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["partner_id"] == "flipkart"
    assert data["rule_type"] == "flipkart_standard"


def test_cofounder_cannot_create_rate_card(client, cofounder_cookies):
    headers = {"X-CSRF-Token": cofounder_cookies["csrf_token"]}
    response = client.post(
        "/api/v1/rate-cards/",
        json={
            "partner_id": "flipkart",
            "channel": "marketplace",
            "rule_type": "flipkart_standard_v2",
            "params_json": {"commission_pct": 10.0},
            "valid_from": "2026-03-01",
            "valid_until": None,
            "is_active": True
        },
        cookies=cofounder_cookies,
        headers=headers
    )
    # Must return 403 Forbidden because cofounder is read-only for rate cards and operational modifications
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]
