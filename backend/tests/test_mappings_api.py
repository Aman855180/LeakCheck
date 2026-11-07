import pytest
from sqlalchemy import text
from app.models.source import Source
from app.models.column_mapping import ColumnMapping
from app.models.user import User


def test_suggest_mappings_api(client, finance_exec_cookies, finance_exec_headers, db_session):
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    payload = {
        "source_id": str(source.id),
        "source_columns": ["order_id", "total_price", "purchase_date", "buyer_name"]
    }
    response = client.post(
        "/api/v1/mappings/suggest",
        json=payload,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "orders"
    assert data["suggestions"]["external_order_id"]["column"] == "order_id"
    assert data["suggestions"]["order_value"]["column"] == "total_price"
    assert data["suggestions"]["order_date"]["column"] == "purchase_date"


def test_cofounder_can_approve_and_rollback_mapping(client, cofounder_cookies, cofounder_headers, db_session):
    """Verify co-founder can approve and rollback column mappings per agreed RBAC."""
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    # 1. Co-founder approves mapping v1
    payload_v1 = {
        "source_id": str(source.id),
        "mapping_json": {
            "external_order_id": "order_id",
            "order_value": "gross_amount",
            "order_date": "order_date"
        }
    }
    res_v1 = client.post(
        "/api/v1/mappings/approve",
        json=payload_v1,
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_v1.status_code == 201
    mapping_v1 = res_v1.json()
    assert mapping_v1["status"] == "approved"
    assert mapping_v1["version"] >= 1
    v1_id = mapping_v1["id"]

    # 2. Co-founder approves mapping v2
    payload_v2 = {
        "source_id": str(source.id),
        "mapping_json": {
            "external_order_id": "order_number",
            "order_value": "total_price",
            "order_date": "created_at"
        }
    }
    res_v2 = client.post(
        "/api/v1/mappings/approve",
        json=payload_v2,
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_v2.status_code == 201
    mapping_v2 = res_v2.json()
    assert mapping_v2["version"] == mapping_v1["version"] + 1

    # 3. Co-founder rolls back to v1
    res_rollback = client.post(
        f"/api/v1/mappings/{v1_id}/rollback",
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_rollback.status_code == 200
    rolled_back = res_rollback.json()
    # Rollback creates a new version matching v1 configuration
    assert rolled_back["version"] == mapping_v2["version"] + 1
    assert rolled_back["mapping_json"]["external_order_id"] == "order_id"
    assert rolled_back["status"] == "approved"


def test_incomplete_mapping_rejected_400(client, finance_exec_cookies, finance_exec_headers, db_session):
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    # Missing mandatory order_date and order_value for orders
    payload = {
        "source_id": str(source.id),
        "mapping_json": {
            "external_order_id": "order_id"
        }
    }
    response = client.post(
        "/api/v1/mappings/approve",
        json=payload,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert response.status_code == 400
    assert "Missing mandatory fields" in response.json()["detail"]


def test_approved_mapping_immutability_trigger(db_session):
    source = db_session.query(Source).first()
    user = db_session.query(User).first()

    mapping = ColumnMapping(
        source_id=source.id,
        version=999,
        mapping_json={"external_order_id": "order_id"},
        status="approved",
        created_by=user.id,
        approved_by=user.id
    )
    db_session.add(mapping)
    db_session.commit()

    # Attempting to directly alter mapping_json on an approved mapping must trigger exception
    nested = db_session.begin_nested()
    with pytest.raises(Exception) as exc:
        db_session.execute(
            text("UPDATE column_mappings SET mapping_json = '{\"external_order_id\": \"mutated\"}' WHERE id = :id"),
            {"id": mapping.id}
        )
        db_session.flush()
    nested.rollback()
    assert "is immutable" in str(exc.value)
