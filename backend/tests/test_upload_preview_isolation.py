import io
import uuid
from unittest.mock import patch
import pytest

from app.models.source import Source
from app.models.upload import Upload
from app.models.column_mapping import ColumnMapping
from app.models.upload_mapping_suggestion import UploadMappingSuggestion
from app.models.order_recon import OrderRecon
from app.api.v1.uploads import _PENDING_FILE_CACHE
from app.services.pending_file_storage import read_pending_file_from_disk, delete_pending_file_from_disk


def test_upload_mapping_persistence_and_preview_retrieval(
    client, finance_exec_cookies, finance_exec_headers, db_session
):
    """
    Verify that an upload with unmapped/new headers persists its suggestions
    into upload_mapping_suggestions and is retrievable via GET /api/v1/uploads/{id}/preview.
    """
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    csv_content = (
        b"custom_order_ref,custom_order_total,custom_order_ts\n"
        b"ORD-ISO-001,1599.00,2026-03-01 10:00:00\n"
        b"ORD-ISO-002,2499.00,2026-03-01 11:00:00\n"
    )
    files = {"file": ("custom_orders_isolated.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"source_id": str(source.id)}

    upload_res = client.post(
        "/api/v1/uploads/",
        files=files,
        data=data,
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    assert upload_data.get("type") == "preview"
    upload_id = upload_data["upload_id"]

    # 1. Verify DB persistence in upload_mapping_suggestions
    persisted = db_session.query(UploadMappingSuggestion).filter(
        UploadMappingSuggestion.upload_id == uuid.UUID(upload_id)
    ).first()
    assert persisted is not None
    assert persisted.file_name == "custom_orders_isolated.csv"
    assert persisted.detected_columns == ["custom_order_ref", "custom_order_total", "custom_order_ts"]
    assert persisted.total_rows == 2
    assert "suggested_mapping" in persisted.__dict__ or persisted.suggested_mapping is not None

    # 2. Retrieve via GET /api/v1/uploads/{upload_id}/preview
    preview_res = client.get(
        f"/api/v1/uploads/{upload_id}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["upload_id"] == upload_id
    assert preview_data["file_name"] == "custom_orders_isolated.csv"
    assert preview_data["detected_columns"] == ["custom_order_ref", "custom_order_total", "custom_order_ts"]
    assert preview_data["total_rows"] == 2
    assert len(preview_data["preview_rows"]) == 2
    assert "suggested_mapping" in preview_data


def test_repeated_preview_get_does_not_call_gemini(
    client, finance_exec_cookies, finance_exec_headers, db_session
):
    """
    Verify that subsequent GET /api/v1/uploads/{id}/preview calls retrieve from DB
    and do not call the Gemini API or column mapper again.
    """
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    csv_content = b"ref_num,amt,created_date\nORD-GEM-1,500,2026-03-01\n"
    files = {"file": ("gem_cache_test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = client.post(
        "/api/v1/uploads/",
        files=files,
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["upload_id"]

    # Mock AIFallbackMapper.predict_unresolved_mappings to ensure it is NOT called on GET
    with patch("app.services.column_mapper.AIFallbackMapper.predict_unresolved_mappings") as mock_ai:
        for _ in range(3):
            preview_res = client.get(
                f"/api/v1/uploads/{upload_id}/preview",
                cookies=finance_exec_cookies,
                headers=finance_exec_headers
            )
            assert preview_res.status_code == 200
            assert preview_res.json()["detected_columns"] == ["ref_num", "amt", "created_date"]

        mock_ai.assert_not_called()


def test_durable_retrieval_after_memory_cache_cleared(
    client, finance_exec_cookies, finance_exec_headers, db_session
):
    """
    Verify that even if _PENDING_FILE_CACHE is wiped (simulating server restart),
    the persisted suggestion and durable disk storage allow preview and processing.
    """
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    csv_content = b"invoice_id,invoice_total,invoice_time\nINV-900,1200,2026-03-01\n"
    files = {"file": ("restart_sim.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = client.post(
        "/api/v1/uploads/",
        files=files,
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["upload_id"]

    # Clear memory cache
    _PENDING_FILE_CACHE.clear()

    # Disk file must exist
    disk_bytes = read_pending_file_from_disk(upload_id)
    assert disk_bytes == csv_content

    # GET /preview must succeed from database
    preview_res = client.get(
        f"/api/v1/uploads/{upload_id}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert preview_res.status_code == 200
    assert preview_res.json()["file_name"] == "restart_sim.csv"


def test_preview_missing_and_invalid_upload_ids(client, finance_exec_cookies, finance_exec_headers):
    """Verify 400 for invalid UUID and 404 for non-existent upload ID."""
    # Invalid UUID
    res_bad = client.get(
        "/api/v1/uploads/not-a-valid-uuid/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_bad.status_code == 400
    assert "Invalid upload_id format" in res_bad.json()["detail"]

    # Non-existent UUID
    fake_id = str(uuid.uuid4())
    res_missing = client.get(
        f"/api/v1/uploads/{fake_id}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_missing.status_code == 404
    assert f"Upload {fake_id} not found" in res_missing.json()["detail"]


def test_preview_rbac(client, finance_exec_cookies, finance_exec_headers, cofounder_cookies, cofounder_headers, db_session):
    """Verify that finance_exec and cofounder can view preview, while unauthenticated gets 401."""
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    csv_content = b"c1,c2,c3\nv1,v2,v3\n"
    files = {"file": ("rbac_preview.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = client.post(
        "/api/v1/uploads/",
        files=files,
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["upload_id"]

    # Co-founder can view preview
    res_co = client.get(
        f"/api/v1/uploads/{upload_id}/preview",
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_co.status_code == 200

    # Unauthenticated gets 401
    res_unauth = client.get(f"/api/v1/uploads/{upload_id}/preview")
    assert res_unauth.status_code == 401


def test_cross_upload_isolation_file_a_and_file_b(
    client, finance_exec_cookies, finance_exec_headers, db_session
):
    """
    CRITICAL ISOLATION TEST:
    Upload File A, then File B.
    Verify that Preview(A) returns File A headers and suggestions,
    and Preview(B) returns File B headers and suggestions.
    Verify that neither upload affects the active database mapping v7.
    """
    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    # Record active mapping before uploads
    active_before = (
        db_session.query(ColumnMapping)
        .filter(ColumnMapping.source_id == source.id, ColumnMapping.status == "approved")
        .order_by(ColumnMapping.version.desc())
        .first()
    )
    active_version_before = active_before.version if active_before else None

    # File A: Classic headers
    file_a_content = (
        b"Order ID,Total Price,Payment Method,Created At\n"
        b"ORD-A-01,1000.00,Prepaid,2026-03-01\n"
        b"ORD-A-02,2000.00,COD,2026-03-02\n"
    )
    # File B: Unfamiliar test headers
    file_b_content = (
        b"retailer_transaction_code,basket_gross_inr,collection_method,purchase_timestamp,parcel_consignment_code\n"
        b"RTX-B-99,4999.00,NetBanking,2026-03-05 14:00:00,TRACK-B-001\n"
    )

    # Upload A
    res_a = client.post(
        "/api/v1/uploads/",
        files={"file": ("file_a_classic.csv", io.BytesIO(file_a_content), "text/csv")},
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_a.status_code == 201
    upload_id_a = res_a.json()["upload_id"]

    # Upload B
    res_b = client.post(
        "/api/v1/uploads/",
        files={"file": ("file_b_unfamiliar.csv", io.BytesIO(file_b_content), "text/csv")},
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_b.status_code == 201
    upload_id_b = res_b.json()["upload_id"]

    assert upload_id_a != upload_id_b

    # Inspect Preview A
    prev_a = client.get(
        f"/api/v1/uploads/{upload_id_a}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    ).json()
    assert prev_a["file_name"] == "file_a_classic.csv"
    assert prev_a["detected_columns"] == ["Order ID", "Total Price", "Payment Method", "Created At"]
    assert prev_a["total_rows"] == 2

    # Inspect Preview B
    prev_b = client.get(
        f"/api/v1/uploads/{upload_id_b}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    ).json()
    assert prev_b["file_name"] == "file_b_unfamiliar.csv"
    assert prev_b["detected_columns"] == [
        "retailer_transaction_code",
        "basket_gross_inr",
        "collection_method",
        "purchase_timestamp",
        "parcel_consignment_code"
    ]
    assert prev_b["total_rows"] == 1

    # Strict isolation: Preview A does NOT contain B's headers, Preview B does NOT contain A's headers
    assert "retailer_transaction_code" not in prev_a["detected_columns"]
    assert "Order ID" not in prev_b["detected_columns"]

    # Verify active source mapping version remains completely unchanged
    active_after = (
        db_session.query(ColumnMapping)
        .filter(ColumnMapping.source_id == source.id, ColumnMapping.status == "approved")
        .order_by(ColumnMapping.version.desc())
        .first()
    )
    active_version_after = active_after.version if active_after else None
    assert active_version_after == active_version_before

    # Verify no records were ingested into OrderRecon automatically
    order_recon_a = db_session.query(OrderRecon).filter(OrderRecon.external_order_id == "ORD-A-01").first()
    order_recon_b = db_session.query(OrderRecon).filter(OrderRecon.external_order_id == "RTX-B-99").first()
    assert order_recon_a is None
    assert order_recon_b is None


def test_cross_upload_isolation_file_b_then_file_a_with_reloads(
    client, finance_exec_cookies, finance_exec_headers, db_session
):
    """
    CRITICAL ISOLATION TEST (Sequence 2):
    Upload File B first, then File A second.
    Verify:
    - Unique upload IDs
    - Correct filename & SHA-256
    - Correct detected headers & preview rows
    - Re-querying/reloading each upload maintains strict isolation with zero crosstalk.
    """
    import hashlib

    source = db_session.query(Source).filter(Source.source_type == "orders").first()
    assert source is not None

    file_b_content = (
        b"retailer_transaction_code,basket_gross_inr,collection_method,purchase_timestamp,parcel_consignment_code\n"
        b"RTX-SEQ2-01,7500.00,UPI,2026-03-08 11:30:00,TRACK-SEQ2-B1\n"
    )
    file_a_content = (
        b"Order ID,Total Price,Payment Method,Created At\n"
        b"ORD-SEQ2-A1,3500.00,COD,2026-03-09 15:00:00\n"
    )

    sha_b = hashlib.sha256(file_b_content).hexdigest()
    sha_a = hashlib.sha256(file_a_content).hexdigest()

    # 1. Upload B first
    res_b = client.post(
        "/api/v1/uploads/",
        files={"file": ("file_b_second_run.csv", io.BytesIO(file_b_content), "text/csv")},
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_b.status_code == 201
    upload_id_b = res_b.json()["upload_id"]

    # 2. Upload A second
    res_a = client.post(
        "/api/v1/uploads/",
        files={"file": ("file_a_second_run.csv", io.BytesIO(file_a_content), "text/csv")},
        data={"source_id": str(source.id)},
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_a.status_code == 201
    upload_id_a = res_a.json()["upload_id"]

    assert upload_id_b != upload_id_a

    # Verify SHA-256 in DB
    up_b = db_session.query(Upload).filter(Upload.id == uuid.UUID(upload_id_b)).first()
    up_a = db_session.query(Upload).filter(Upload.id == uuid.UUID(upload_id_a)).first()
    assert up_b.file_hash == sha_b
    assert up_a.file_hash == sha_a

    # Refresh/Reload simulations: Retrieve B, then A, then B again
    prev_b1 = client.get(
        f"/api/v1/uploads/{upload_id_b}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    ).json()
    assert prev_b1["file_name"] == "file_b_second_run.csv"
    assert prev_b1["detected_columns"] == [
        "retailer_transaction_code",
        "basket_gross_inr",
        "collection_method",
        "purchase_timestamp",
        "parcel_consignment_code"
    ]
    assert "external_order_id" in prev_b1["suggested_mapping"]
    assert "order_value" in prev_b1["suggested_mapping"]

    prev_a1 = client.get(
        f"/api/v1/uploads/{upload_id_a}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    ).json()
    assert prev_a1["file_name"] == "file_a_second_run.csv"
    assert prev_a1["detected_columns"] == ["Order ID", "Total Price", "Payment Method", "Created At"]

    # Reload B again to prove persistence stability
    prev_b2 = client.get(
        f"/api/v1/uploads/{upload_id_b}/preview",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    ).json()
    assert prev_b2["detected_columns"] == prev_b1["detected_columns"]
    assert prev_b2["file_name"] == "file_b_second_run.csv"

