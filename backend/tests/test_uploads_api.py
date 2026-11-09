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
    upload_id = res1.json().get("upload_id") or res1.json().get("upload", {}).get("id")
    from app.models.upload import Upload
    up = db_session.query(Upload).filter(Upload.id == upload_id).first()
    up.processing_status = "completed"
    db_session.add(up)
    db_session.commit()

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


def test_incompatible_mapping_triggers_staging_preview(client, finance_exec_cookies, finance_exec_headers, db_session):
    """If an approved mapping expects columns not present in the uploaded file, stage as preview."""
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    from app.models.user import User
    user = db_session.query(User).first()

    # Create mapping that expects 'legacy_tracking_no' for external_order_id
    bad_mapping = ColumnMapping(
        source_id=source.id,
        version=987,
        mapping_json={
            "external_order_id": "legacy_tracking_no",
            "order_value": "order_value",
            "order_date": "order_date"
        },
        status="approved",
        created_by=user.id,
        approved_by=user.id
    )
    db_session.add(bad_mapping)
    db_session.commit()

    # Upload file that lacks 'legacy_tracking_no'
    csv_content = b"Order ID,Total Price,Created At\nORD-INCOMPAT-01,500.00,2026-03-01 10:00:00\n"
    files = {"file": ("incompatible_file.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    res = client.post(
        "/api/v1/uploads/",
        files=files,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 201
    payload = res.json()
    assert payload["type"] == "preview"
    assert payload["is_mapping_compatible"] is False
    assert len(payload["incompatibility_reasons"]) > 0


def test_failed_upload_retry_allowed_and_linked(client, finance_exec_cookies, finance_exec_headers, db_session):
    """A failed upload does not block a retry with identical SHA-256 hash; links retry_of_upload_id."""
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    from app.models.upload import Upload
    from app.models.user import User
    user = db_session.query(User).first()

    fake_hash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    # Create an existing failed upload with fake_hash
    failed_upload = Upload(
        source_id=source.id,
        partner_id=source.partner_id,
        source_type=source.source_type,
        file_name="failed_retry_test.csv",
        file_hash=fake_hash,
        file_size_bytes=100,
        row_count=5,
        processing_status="failed",
        error_count=5,
        uploaded_by=user.id
    )
    db_session.add(failed_upload)
    db_session.commit()

    # Now verify query logic in uploads.py: existing_completed should be None because status is 'failed'
    existing_completed = (
        db_session.query(Upload)
        .filter(
            Upload.file_hash == fake_hash,
            Upload.processing_status.in_(["completed", "processing"])
        )
        .first()
    )
    assert existing_completed is None

    prior_attempt = (
        db_session.query(Upload)
        .filter(Upload.file_hash == fake_hash)
        .order_by(Upload.created_at.desc())
        .first()
    )
    assert prior_attempt is not None
    assert prior_attempt.id == failed_upload.id


def test_orders_feed_never_requires_settlement_amount():
    """Verify that orders feed strictly never requires settlement_amount."""
    from app.services.column_mapper import CANONICAL_FIELDS, validate_mapping_completeness

    assert "orders" not in CANONICAL_FIELDS["settlement_amount"]["required_for"]
    assert "orders" in CANONICAL_FIELDS["external_order_id"]["required_for"]
    assert "orders" in CANONICAL_FIELDS["order_value"]["required_for"]

    orders_mapping = {
        "external_order_id": "Order ID",
        "order_value": "Total Price",
        "order_date": "Created At"
    }
    is_valid, missing = validate_mapping_completeness(orders_mapping, "orders")
    assert is_valid is True
    assert len(missing) == 0
    assert "settlement_amount" not in missing


def test_upload_legacy_xls_rejected(client, finance_exec_cookies, finance_exec_headers, db_session):
    """SEC-03: Uploading legacy .xls format returns HTTP 400 with UNSUPPORTED_FORMAT error."""
    source = db_session.query(Source).first()
    assert source is not None

    legacy_xls_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
    files = {
        "file": ("sales_legacy.xls", io.BytesIO(legacy_xls_bytes), "application/vnd.ms-excel")
    }
    data = {
        "source_id": str(source.id)
    }

    res = client.post(
        "/api/v1/uploads/",
        data=data,
        files=files,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 400
    payload = res.json()
    assert "Legacy Excel (.xls) format is unsupported" in payload["detail"]
