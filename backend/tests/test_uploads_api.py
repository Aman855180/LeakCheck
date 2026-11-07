import io
import pytest
from app.models.source import Source
from app.models.column_mapping import ColumnMapping


def test_cofounder_cannot_upload_file(client, cofounder_cookies, cofounder_headers, db_session):
    source = db_session.query(Source).first()
    assert source is not None

    csv_content = b"order_id,order_value\nORD-1,100\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    response = client.post(
        "/api/v1/uploads/",
        files=files,
        data=data,
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    # Co-founder is read-only for uploads; must receive 403 Forbidden
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_finance_exec_can_upload_and_preview(client, finance_exec_cookies, finance_exec_headers, db_session):
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    csv_content = (
        b"order_id,order_value,order_date,customer_name\n"
        b"ORD-TEST-100,1499.00,2026-03-01 10:00:00,Ravi Kumar\n"
        b"ORD-TEST-101,899.00,2026-03-01 11:00:00,Sneha Reddy\n"
    )
    files = {"file": ("test_orders_upload.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    response = client.post(
        "/api/v1/uploads/",
        files=files,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert response.status_code == 201
    payload = response.json()

    # If mapping is pending, it should return preview with dropped PII
    if payload.get("type") == "preview":
        assert "customer_name" in payload["dropped_pii_columns"]
        assert len(payload["preview_rows"]) == 2
        assert "suggested_mapping" in payload
        assert payload["suggested_mapping"]["external_order_id"]["column"] == "order_id"
    else:
        assert payload.get("type") == "completed"


def test_duplicate_file_upload_rejected_409(client, finance_exec_cookies, finance_exec_headers, db_session):
    source = db_session.query(Source).first()
    assert source is not None

    csv_content = b"order_id,order_value,order_date\nORD-DUP-01,500,2026-03-01\n"
    files1 = {"file": ("dup_file.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    # First upload
    res1 = client.post(
        "/api/v1/uploads/",
        files=files1,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res1.status_code == 201

    # Second upload with identical bytes
    files2 = {"file": ("dup_file.csv", io.BytesIO(csv_content), "text/csv")}
    res2 = client.post(
        "/api/v1/uploads/",
        files=files2,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res2.status_code == 409
    assert "Duplicate file detected" in res2.json()["detail"]


def test_quarantined_rows_recorded(client, finance_exec_cookies, finance_exec_headers, db_session):
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    from app.models.user import User
    user = db_session.query(User).first()
    assert user is not None

    mapping = ColumnMapping(
        source_id=source.id,
        version=99,
        mapping_json={
            "external_order_id": "order_id",
            "order_value": "order_value",
            "order_date": "order_date"
        },
        status="approved",
        created_by=user.id,
        approved_by=user.id
    )
    db_session.add(mapping)
    db_session.commit()

    # CSV with row 1 valid, row 2 missing order_id, row 3 invalid numeric amount
    csv_content = (
        b"order_id,order_value,order_date\n"
        b"ORD-VALID-01,999.00,2026-03-01 10:00:00\n"
        b",1200.00,2026-03-01 10:05:00\n"
        b"ORD-VALID-03,NOT_A_NUMBER,2026-03-01 10:10:00\n"
    )
    files = {"file": ("corrupted_rows.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    res = client.post(
        "/api/v1/uploads/",
        files=files,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 201
    upload_data = res.json()["upload"]
    upload_id = upload_data["id"]

    # Check errors endpoint
    err_res = client.get(
        f"/api/v1/uploads/{upload_id}/errors",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert err_res.status_code == 200
    errors = err_res.json()
    assert len(errors) == 2
    error_codes = [e["error_code"] for e in errors]
    assert "MISSING_ORDER_ID" in error_codes
    assert "INVALID_NUMERIC" in error_codes
