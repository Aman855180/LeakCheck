from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.order_recon import OrderRecon
from app.models.claim import Claim
from app.schemas.dashboard import DashboardMetricsResponse
from app.schemas.claim import ClaimsSummaryResponse
from app.services.rate_card_calculator import quantize_amount
from app.services.recon_engine import DEFAULT_AS_OF_DATE

router = APIRouter(prefix="/dashboard", tags=["Money-at-Risk Dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Returns complete Money-at-Risk Dashboard metrics derived dynamically from persisted
    reconciliation orders and claims records.
    Strictly preserves Phase 3 non-overlapping financial leakage calculations and statutory tax isolation.
    """
    all_recons = db.query(OrderRecon).all()

    total_orders = len(all_recons)
    total_risk = Decimal("0.00")
    total_settlement_gap = Decimal("0.00")
    total_freight_excess = Decimal("0.00")
    total_return_loss = Decimal("0.00")

    status_counts = {
        "settled": 0,
        "short_paid": 0,
        "unpaid_past_due": 0,
        "freight_overcharged": 0,
        "return_not_received": 0,
        "pending": 0
    }

    age_bucket_counts = {
        "0-7": 0,
        "8-15": 0,
        "16-30": 0,
        "31+": 0
    }

    age_bucket_risk = {
        "0-7": Decimal("0.00"),
        "8-15": Decimal("0.00"),
        "16-30": Decimal("0.00"),
        "31+": Decimal("0.00")
    }

    partner_risk_breakdown: Dict[str, Decimal] = {}
    partner_order_counts: Dict[str, int] = {}

    reason_code_risk_breakdown: Dict[str, Decimal] = {}
    reason_code_counts: Dict[str, int] = {}

    for r in all_recons:
        # Status counts
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        partner_order_counts[r.partner_id] = partner_order_counts.get(r.partner_id, 0) + 1

        # Non-overlapping leakage calculations (Excludes pending & settled orders)
        risk = quantize_amount(r.money_at_risk)
        total_risk += risk
        total_settlement_gap += quantize_amount(r.settlement_gap_component)
        total_freight_excess += quantize_amount(r.freight_excess_component)
        total_return_loss += quantize_amount(r.return_loss_component)

        # Aging buckets
        bucket = r.age_bucket if r.age_bucket in age_bucket_counts else ("31+" if "30" in r.age_bucket or "+" in r.age_bucket else "0-7")
        age_bucket_counts[bucket] = age_bucket_counts.get(bucket, 0) + 1

        if risk > Decimal("0.00"):
            age_bucket_risk[bucket] = age_bucket_risk.get(bucket, Decimal("0.00")) + risk
            partner_risk_breakdown[r.partner_id] = partner_risk_breakdown.get(r.partner_id, Decimal("0.00")) + risk

            # Reason codes breakdown
            codes = r.reason_codes if r.reason_codes else [r.status]
            for rc in codes:
                reason_code_counts[rc] = reason_code_counts.get(rc, 0) + 1
                reason_code_risk_breakdown[rc] = reason_code_risk_breakdown.get(rc, Decimal("0.00")) + risk

    # Claims metrics
    all_claims = db.query(Claim).all()
    total_claims = len(all_claims)
    total_claim_amount = Decimal("0.00")
    total_recovered_amount = Decimal("0.00")

    claim_status_counts = {
        "draft": 0,
        "submitted": 0,
        "in_review": 0,
        "approved": 0,
        "rejected": 0,
        "recovered": 0
    }

    partner_claims_summary: Dict[str, Dict[str, Any]] = {}

    for c in all_claims:
        total_claim_amount += quantize_amount(c.claim_amount)
        total_recovered_amount += quantize_amount(c.recovered_amount)
        claim_status_counts[c.claim_status] = claim_status_counts.get(c.claim_status, 0) + 1

        p_info = partner_claims_summary.setdefault(c.partner_id, {
            "total_claims": 0,
            "claimed_amount": Decimal("0.00"),
            "recovered_amount": Decimal("0.00"),
            "outstanding_amount": Decimal("0.00")
        })
        p_info["total_claims"] += 1
        p_info["claimed_amount"] += quantize_amount(c.claim_amount)
        p_info["recovered_amount"] += quantize_amount(c.recovered_amount)
        p_info["outstanding_amount"] = quantize_amount(p_info["claimed_amount"] - p_info["recovered_amount"])

    total_outstanding = quantize_amount(max(Decimal("0.00"), total_claim_amount - total_recovered_amount))
    recovery_rate = Decimal("0.00")
    if total_claim_amount > 0:
        recovery_rate = quantize_amount((total_recovered_amount / total_claim_amount) * Decimal("100.00"))

    claims_summary = ClaimsSummaryResponse(
        total_claims=total_claims,
        total_claim_amount=quantize_amount(total_claim_amount),
        total_recovered_amount=quantize_amount(total_recovered_amount),
        total_outstanding_amount=total_outstanding,
        status_counts=claim_status_counts,
        recovery_rate_pct=recovery_rate,
        partner_claims_summary=partner_claims_summary
    )

    return DashboardMetricsResponse(
        as_of=DEFAULT_AS_OF_DATE.isoformat(),
        total_orders=total_orders,
        total_money_at_risk=quantize_amount(total_risk),
        total_settlement_gap=quantize_amount(total_settlement_gap),
        total_freight_excess=quantize_amount(total_freight_excess),
        total_return_loss=quantize_amount(total_return_loss),
        status_counts=status_counts,
        age_bucket_counts=age_bucket_counts,
        age_bucket_risk=age_bucket_risk,
        partner_risk_breakdown=partner_risk_breakdown,
        partner_order_counts=partner_order_counts,
        reason_code_risk_breakdown=reason_code_risk_breakdown,
        reason_code_counts=reason_code_counts,
        claims_summary=claims_summary
    )
