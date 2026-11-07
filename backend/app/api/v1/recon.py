import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, and_

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.order_recon import OrderRecon
from app.models.order_event import OrderEvent
from app.models.tracking_event import TrackingEvent
from app.models.warehouse_receipt import WarehouseReceipt
from app.schemas.recon import (
    ReconRunRequest,
    OrderReconResponse,
    ReconSummaryResponse,
    PaginatedOrderReconResponse,
    OrderTimelineResponse,
    TimelineEventItem
)
from app.services.recon_engine import ReconciliationEngine, DEFAULT_AS_OF_DATE
from app.services.claims_generator import ClaimsGenerator
from app.services.rate_card_calculator import quantize_amount

router = APIRouter(prefix="/recon", tags=["Reconciliation"])


@router.post("/run", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def trigger_reconciliation(
    payload: ReconRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec"]))
):
    """
    Triggers end-to-end financial reconciliation across all feeds.
    RBAC: Finance Executive only (Co-founders have audit read-only access, returns 403).
    """
    as_of = payload.as_of or DEFAULT_AS_OF_DATE
    engine = ReconciliationEngine(db=db, as_of=as_of)
    result = engine.run_reconciliation(order_ids=payload.order_ids)

    # Automatically generate draft claims for confirmed discrepancies
    claims_gen = ClaimsGenerator(db=db)
    generated_claims = claims_gen.generate_draft_claims(order_ids=payload.order_ids)
    result["draft_claims_generated"] = len(generated_claims)

    return result


@router.get("/orders", response_model=Union[PaginatedOrderReconResponse, List[OrderReconResponse]])
def list_reconciled_orders(
    response: Response,
    status_filter: Optional[str] = Query(None, alias="status"),
    partner_id: Optional[str] = None,
    has_risk: Optional[bool] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    reason_code: Optional[str] = None,
    age_bucket: Optional[str] = None,
    sort_by: Optional[str] = Query("money_at_risk"),
    sort_dir: Optional[str] = Query("desc"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=500),
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=500),
    envelope: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    List reconciled orders with robust full-text search, multi-filter criteria,
    sorting, and server-side pagination.
    Accessible by both Finance Executives and Co-founders (read-only audit).
    """
    query = db.query(OrderRecon)

    # 1. Identifier / Free-text Search
    if search and search.strip():
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                OrderRecon.external_order_id.ilike(s_term),
                OrderRecon.order_id.ilike(s_term),
                OrderRecon.channel.ilike(s_term)
            )
        )

    # 2. Status & Risk Filters
    if status_filter and status_filter.upper() != "ALL":
        if status_filter.upper() == "RISK_ONLY":
            query = query.filter(OrderRecon.money_at_risk > 0)
        else:
            query = query.filter(OrderRecon.status == status_filter.lower())

    if partner_id and partner_id.upper() != "ALL":
        query = query.filter(OrderRecon.partner_id == partner_id.lower())

    if has_risk is True:
        query = query.filter(OrderRecon.money_at_risk > 0)
    elif has_risk is False:
        query = query.filter(OrderRecon.money_at_risk == 0)

    # 3. Date Range Filter
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.filter(OrderRecon.order_date >= start_dt)

    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.filter(OrderRecon.order_date <= end_dt)

    # 4. Reason Code Filter
    if reason_code and reason_code.upper() != "ALL":
        query = query.filter(OrderRecon.reason_codes.contains([reason_code.lower()]))

    # 5. Age Bucket Filter
    if age_bucket and age_bucket.upper() != "ALL":
        query = query.filter(OrderRecon.age_bucket == age_bucket)

    total_count = query.count()

    # 6. Sorting
    sort_column = OrderRecon.money_at_risk
    if sort_by == "order_date":
        sort_column = OrderRecon.order_date
    elif sort_by == "order_value":
        sort_column = OrderRecon.order_value
    elif sort_by == "difference":
        sort_column = OrderRecon.difference
    elif sort_by == "expected_amount":
        sort_column = OrderRecon.expected_amount
    elif sort_by == "received_amount":
        sort_column = OrderRecon.received_amount
    elif sort_by == "age_days":
        sort_column = OrderRecon.age_days
    elif sort_by == "status":
        sort_column = OrderRecon.status
    elif sort_by in ("external_order_id", "order_id"):
        sort_column = OrderRecon.external_order_id

    is_asc = (sort_dir or "").lower() == "asc"
    order_clause = asc(sort_column) if is_asc else desc(sort_column)

    # 7. Pagination
    effective_limit = page_size if page_size is not None else (limit if limit is not None else 50)
    effective_limit = min(max(1, effective_limit), 500)

    if page is not None:
        effective_page = max(1, page)
        effective_offset = (effective_page - 1) * effective_limit
    else:
        effective_offset = max(0, skip if skip is not None else 0)
        effective_page = (effective_offset // effective_limit) + 1

    total_pages = max(1, (total_count + effective_limit - 1) // effective_limit) if total_count > 0 else 1

    orders = (
        query
        .order_by(order_clause, desc(OrderRecon.order_date))
        .offset(effective_offset)
        .limit(effective_limit)
        .all()
    )

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(effective_page)
    response.headers["X-Page-Size"] = str(effective_limit)
    response.headers["X-Total-Pages"] = str(total_pages)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Page, X-Page-Size, X-Total-Pages"

    if envelope:
        return PaginatedOrderReconResponse(
            items=orders,
            total=total_count,
            page=effective_page,
            page_size=effective_limit,
            pages=total_pages
        )
    return orders


@router.get("/orders/{order_id}", response_model=OrderReconResponse)
def get_order_recon_detail(
    order_id: str,
    partner_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Get full financial reconciliation detail and deduction breakdown for an order."""
    query = db.query(OrderRecon)
    recon = None
    
    # Try UUID lookup first
    try:
        val_uuid = uuid.UUID(order_id)
        recon = query.filter(OrderRecon.id == val_uuid).first()
    except (ValueError, AttributeError):
        recon = None

    if not recon:
        filter_cond = or_(OrderRecon.external_order_id == order_id, OrderRecon.order_id == order_id)
        if partner_id:
            filter_cond = filter_cond & (OrderRecon.partner_id == partner_id)
        recon = query.filter(filter_cond).first()

    if not recon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation record for order '{order_id}' not found"
        )
    return recon


@router.get("/orders/{order_id}/timeline", response_model=OrderTimelineResponse)
def get_order_timeline(
    order_id: str,
    partner_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Returns an itemized chronological cross-feed evidence audit trail:
    Order Events, Courier Tracking Telemetry, and Warehouse Receipts.
    """
    query = db.query(OrderRecon)
    recon = None
    try:
        val_uuid = uuid.UUID(order_id)
        recon = query.filter(OrderRecon.id == val_uuid).first()
    except (ValueError, AttributeError):
        recon = None

    if not recon:
        filter_cond = or_(OrderRecon.external_order_id == order_id, OrderRecon.order_id == order_id)
        if partner_id:
            filter_cond = filter_cond & (OrderRecon.partner_id == partner_id)
        recon = query.filter(filter_cond).first()

    if not recon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation record for order '{order_id}' not found"
        )

    ext_id = recon.external_order_id
    timeline_items: List[TimelineEventItem] = []

    # 1. Source Order Events
    events = (
        db.query(OrderEvent)
        .filter(or_(OrderEvent.external_order_id == ext_id, OrderEvent.order_id == recon.id))
        .order_by(OrderEvent.event_date.asc())
        .all()
    )

    for ev in events:
        feed = "settlement"
        if ev.event_type == "order_placed":
            feed = "orders"
        elif ev.event_type == "cod_remittance":
            feed = "cod"
        elif ev.event_type in ("freight_charge", "shipping_fee"):
            feed = "freight"
        elif ev.event_type == "settlement_reversal" or ev.reverses_event_id:
            feed = "reversal"

        timeline_items.append(
            TimelineEventItem(
                id=str(ev.id),
                feed_type=feed,
                event_type=ev.event_type,
                event_timestamp=ev.event_date or ev.created_at,
                source_partner_id=ev.source_partner_id,
                amount=ev.amount,
                transaction_reference=ev.transaction_reference,
                status="SUPERSEDED" if ev.supersedes_event_id else ("REVERSED" if ev.reverses_event_id else "RECORDED"),
                details={
                    "fee_type": ev.fee_type,
                    "amendment_reference": ev.amendment_reference,
                    "settlement_credit": str(ev.settlement_credit or Decimal("0.00")),
                    "commission": str(ev.commission or Decimal("0.00")),
                    "freight_amount": str(ev.freight_amount or Decimal("0.00")),
                    "tracking_number": ev.tracking_number,
                    "tcs": str(ev.tcs or Decimal("0.00")),
                    "tds": str(ev.tds or Decimal("0.00")),
                    "lineage_root_id": str(ev.lineage_root_id) if ev.lineage_root_id else None
                }
            )
        )

    # 2. Courier Tracking Events
    tracking_events = (
        db.query(TrackingEvent)
        .filter(TrackingEvent.order_id == ext_id)
        .order_by(TrackingEvent.event_timestamp.asc())
        .all()
    )
    for tr in tracking_events:
        timeline_items.append(
            TimelineEventItem(
                id=str(tr.id),
                feed_type="tracking",
                event_type=f"Tracking: {tr.raw_status_code}",
                event_timestamp=tr.event_timestamp,
                source_partner_id=tr.courier_code,
                amount=None,
                transaction_reference=tr.tracking_number,
                status=tr.verification_outcome,
                details={
                    "courier_code": tr.courier_code,
                    "tracking_number": tr.tracking_number,
                    "verification_outcome": tr.verification_outcome,
                    "facility_code": tr.raw_facility_code,
                    "mapping_version": tr.mapping_version
                }
            )
        )

    # 3. Warehouse Receipts
    wh_receipts = (
        db.query(WarehouseReceipt)
        .filter(WarehouseReceipt.order_id == ext_id)
        .order_by(WarehouseReceipt.received_at.asc())
        .all()
    )
    for wh in wh_receipts:
        timeline_items.append(
            TimelineEventItem(
                id=str(wh.id),
                feed_type="warehouse",
                event_type=f"Dock Receipt: {wh.receipt_status}",
                event_timestamp=wh.received_at,
                source_partner_id=wh.warehouse_id,
                amount=None,
                transaction_reference=wh.tracking_number,
                status=wh.receipt_status.upper(),
                details={
                    "warehouse_id": wh.warehouse_id,
                    "tracking_number": wh.tracking_number,
                    "receipt_status": wh.receipt_status
                }
            )
        )

    # Chronological sort across feeds
    timeline_items.sort(key=lambda x: x.event_timestamp)

    return OrderTimelineResponse(
        order_id=recon.order_id,
        external_order_id=recon.external_order_id,
        partner_id=recon.partner_id,
        total_events=len(timeline_items),
        timeline=timeline_items
    )


@router.get("/summary", response_model=ReconSummaryResponse)
def get_reconciliation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Aggregates high-level reconciliation KPIs, non-overlapping Money at Risk,
    status counts, standardized age buckets (0-7, 8-15, 16-30, 31+), and partner breakdowns.
    """
    all_recons = db.query(OrderRecon).all()
    
    total_orders = len(all_recons)
    total_risk = Decimal("0.00")

    status_counts = {
        "settled": 0,
        "short_paid": 0,
        "unpaid_past_due": 0,
        "freight_overcharged": 0,
        "return_not_received": 0,
        "pending": 0
    }

    age_buckets = {
        "0-7": 0,
        "8-15": 0,
        "16-30": 0,
        "31+": 0
    }

    partner_breakdown: Dict[str, Decimal] = {}

    for r in all_recons:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        total_risk += quantize_amount(r.money_at_risk)

        if r.money_at_risk > 0:
            age_bucket_key = r.age_bucket if r.age_bucket in age_buckets else ("31+" if "30" in r.age_bucket or "+" in r.age_bucket else "0-7")
            age_buckets[age_bucket_key] = age_buckets.get(age_bucket_key, 0) + 1
            partner_breakdown[r.partner_id] = partner_breakdown.get(r.partner_id, Decimal("0.00")) + quantize_amount(r.money_at_risk)

    return ReconSummaryResponse(
        as_of=DEFAULT_AS_OF_DATE.isoformat(),
        total_orders=total_orders,
        total_money_at_risk=quantize_amount(total_risk),
        settled_count=status_counts["settled"],
        short_paid_count=status_counts["short_paid"],
        unpaid_past_due_count=status_counts["unpaid_past_due"],
        freight_overcharged_count=status_counts["freight_overcharged"],
        return_not_received_count=status_counts["return_not_received"],
        pending_count=status_counts["pending"],
        age_bucket_counts=age_buckets,
        partner_risk_breakdown=partner_breakdown
    )
