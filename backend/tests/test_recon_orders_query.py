import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
import pytest
from app.models.order_recon import OrderRecon
from app.models.order_event import OrderEvent
from app.models.tracking_event import TrackingEvent
from app.models.warehouse_receipt import WarehouseReceipt
from app.models.upload import Upload


def test_recon_orders_search_filter_pagination(client, db_session, finance_exec_cookies, finance_exec_headers):
    # Setup test orders
    suffix = uuid.uuid4().hex[:6]
    base_date = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    order1_id = f"ORD-P4-A1-{suffix}"
    order2_id = f"ORD-P4-A2-{suffix}"
    order3_id = f"ORD-P4-B1-{suffix}"

    recon1 = OrderRecon(
        external_order_id=order1_id,
        order_id=order1_id,
        partner_id="shopify",
        channel="d2c",
        payment_mode="COD",
        order_date=base_date,
        order_value=Decimal("1500.00"),
        expected_amount=Decimal("1410.00"),
        received_amount=Decimal("0.00"),
        cod_remittance=Decimal("0.00"),
        difference=Decimal("-1410.00"),
        status="unpaid_past_due",
        reason_codes=["cod_remittance_missing"],
        age_days=17,
        age_bucket="16-30",
        money_at_risk=Decimal("1410.00"),
        settlement_gap_component=Decimal("1410.00")
    )

    recon2 = OrderRecon(
        external_order_id=order2_id,
        order_id=order2_id,
        partner_id="amazon",
        channel="marketplace",
        payment_mode="PREPAID",
        order_date=base_date + timedelta(days=5),
        order_value=Decimal("2000.00"),
        expected_amount=Decimal("1700.00"),
        received_amount=Decimal("1650.00"),
        difference=Decimal("-50.00"),
        status="short_paid",
        reason_codes=["excess_commission"],
        age_days=12,
        age_bucket="8-15",
        money_at_risk=Decimal("50.00"),
        settlement_gap_component=Decimal("50.00")
    )

    recon3 = OrderRecon(
        external_order_id=order3_id,
        order_id=order3_id,
        partner_id="shopify",
        channel="d2c",
        payment_mode="PREPAID",
        order_date=base_date + timedelta(days=10),
        order_value=Decimal("800.00"),
        expected_amount=Decimal("740.00"),
        received_amount=Decimal("740.00"),
        difference=Decimal("0.00"),
        status="settled",
        reason_codes=[],
        age_days=2,
        age_bucket="0-7",
        money_at_risk=Decimal("0.00")
    )

    db_session.add_all([recon1, recon2, recon3])
    db_session.commit()

    # 1. Search by order ID substring
    res = client.get(
        f"/api/v1/recon/orders?search={order1_id}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order1_id

    # 2. Filter by Partner
    res = client.get(
        f"/api/v1/recon/orders?partner_id=amazon&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order2_id

    # 3. Filter by Status
    res = client.get(
        f"/api/v1/recon/orders?status=short_paid&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order2_id

    # 4. Filter by has_risk
    res = client.get(
        f"/api/v1/recon/orders?has_risk=true&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    ids = [i["order_id"] for i in items]
    assert order1_id in ids and order2_id in ids

    # 5. Filter by Reason Code
    res = client.get(
        f"/api/v1/recon/orders?reason_code=cod_remittance_missing&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order1_id

    # 6. Filter by Date Range
    res = client.get(
        f"/api/v1/recon/orders?start_date=2026-10-24&end_date=2026-10-26&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order3_id

    # 7. Filter by Age Bucket
    res = client.get(
        f"/api/v1/recon/orders?age_bucket=16-30&search={suffix}",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["order_id"] == order1_id

    # 8. Sorting by order_value ascending
    res = client.get(
        f"/api/v1/recon/orders?search={suffix}&sort_by=order_value&sort_dir=asc",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 3
    assert Decimal(items[0]["order_value"]) <= Decimal(items[1]["order_value"]) <= Decimal(items[2]["order_value"])

    # 9. Sorting by money_at_risk descending
    res = client.get(
        f"/api/v1/recon/orders?search={suffix}&sort_by=money_at_risk&sort_dir=desc",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 3
    assert items[0]["order_id"] == order1_id  # 1410.00
    assert items[1]["order_id"] == order2_id  # 50.00
    assert items[2]["order_id"] == order3_id  # 0.00

    # 10. Envelope Pagination
    res = client.get(
        f"/api/v1/recon/orders?search={suffix}&envelope=true&page=1&page_size=2",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["pages"] == 2
    assert len(data["items"]) == 2
    assert res.headers["X-Total-Count"] == "3"
    assert res.headers["X-Total-Pages"] == "2"


def test_recon_orders_timeline(client, db_session, finance_exec_cookies, finance_exec_headers, cofounder_cookies, cofounder_headers):
    suffix = uuid.uuid4().hex[:6]
    order_id = f"ORD-TIME-{suffix}"
    t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Order Recon Record
    recon = OrderRecon(
        external_order_id=order_id,
        order_id=order_id,
        partner_id="shopify",
        channel="d2c",
        payment_mode="COD",
        order_date=t0,
        order_value=Decimal("1200.00"),
        expected_amount=Decimal("1110.00"),
        received_amount=Decimal("0.00"),
        difference=Decimal("-1110.00"),
        status="unpaid_past_due",
        reason_codes=["cod_remittance_missing"],
        age_days=10,
        age_bucket="8-15",
        money_at_risk=Decimal("1110.00")
    )
    db_session.add(recon)

    # 1. Source Event: order_placed
    ev_placed = OrderEvent(
        idempotency_key=f"idemp-placed-{suffix}",
        external_order_id=order_id,
        source_partner_id="shopify",
        event_type="order_placed",
        event_date=t0,
        amount=Decimal("1200.00"),
        lineage_root_id=uuid.uuid4()
    )
    ev_placed.lineage_root_id = ev_placed.id
    db_session.add(ev_placed)

    # We need an Upload record for tracking event foreign key
    from app.models.source import Source
    from app.models.user import User

    source = db_session.query(Source).first()
    user = db_session.query(User).first()

    test_upload = Upload(
        source_id=source.id,
        partner_id="shopify",
        source_type="orders",
        file_name="test.csv",
        file_hash=f"hash-{suffix}",
        file_size_bytes=100,
        row_count=1,
        processing_status="completed",
        uploaded_by=user.id
    )
    db_session.add(test_upload)
    db_session.commit()

    # 2. Tracking Event
    tr_ev = TrackingEvent(
        order_id=order_id,
        tracking_number=f"TRK-{suffix}",
        courier_code="delhivery",
        event_timestamp=t0 + timedelta(days=1),
        raw_status_code="DELIVERED",
        raw_facility_code="BLR_HUB",
        raw_telemetry={"status": "Delivered to customer"},
        verification_outcome="VALID_DELIVERY",
        upload_id=test_upload.id,
        source_row_number=1
    )
    db_session.add(tr_ev)

    # 3. Warehouse Receipt
    wh_rcpt = WarehouseReceipt(
        order_id=order_id,
        tracking_number=f"TRK-{suffix}",
        warehouse_id="blr_warehouse",
        received_at=t0 + timedelta(days=2),
        receipt_status="delivered",
        upload_id=test_upload.id,
        source_row_number=1
    )
    db_session.add(wh_rcpt)
    db_session.commit()

    # Finance Exec can query timeline
    res = client.get(
        f"/api/v1/recon/orders/{order_id}/timeline",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res.status_code == 200
    timeline_data = res.json()
    assert timeline_data["order_id"] == order_id
    assert timeline_data["total_events"] == 3
    
    events = timeline_data["timeline"]
    assert len(events) == 3
    # Check chronological order: t0 < t0+1d < t0+2d
    assert events[0]["feed_type"] == "orders"
    assert events[0]["event_type"] == "order_placed"
    assert events[1]["feed_type"] == "tracking"
    assert events[1]["status"] == "VALID_DELIVERY"
    assert events[2]["feed_type"] == "warehouse"
    assert events[2]["status"] == "DELIVERED"

    # Co-founder can also query timeline (read-only audit role)
    res_co = client.get(
        f"/api/v1/recon/orders/{order_id}/timeline",
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_co.status_code == 200
    assert res_co.json()["total_events"] == 3

    # Unauthenticated rejected
    res_unauth = client.get(f"/api/v1/recon/orders/{order_id}/timeline")
    assert res_unauth.status_code == 401

    # Nonexistent order returns 404
    res_404 = client.get(
        "/api/v1/recon/orders/ORD-NONEXISTENT-9999/timeline",
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_404.status_code == 404
