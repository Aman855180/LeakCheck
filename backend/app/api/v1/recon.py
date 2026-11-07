import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.order_recon import OrderRecon
from app.schemas.recon import (
    ReconRunRequest,
    OrderReconResponse,
    ReconSummaryResponse
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


@router.get("/orders", response_model=List[OrderReconResponse])
def list_reconciled_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    partner_id: Optional[str] = None,
    has_risk: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    List reconciled orders with discrepancy filters.
    Accessible by both Finance Executives and Co-founders.
    """
    query = db.query(OrderRecon)

    if status_filter:
        query = query.filter(OrderRecon.status == status_filter)
    if partner_id:
        query = query.filter(OrderRecon.partner_id == partner_id)
    if has_risk is True:
        query = query.filter(OrderRecon.money_at_risk > 0)
    elif has_risk is False:
        query = query.filter(OrderRecon.money_at_risk == 0)

    orders = (
        query
        .order_by(desc(OrderRecon.money_at_risk), desc(OrderRecon.order_date))
        .offset(skip)
        .limit(limit)
        .all()
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
