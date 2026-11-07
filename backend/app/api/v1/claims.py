import uuid
import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, and_

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.claim import Claim
from app.models.order_recon import OrderRecon
from app.schemas.claim import (
    ClaimResponse,
    ClaimDetailResponse,
    ClaimUpdateRequest,
    PaginatedClaimResponse,
    ClaimsSummaryResponse
)
from app.schemas.recon import OrderReconResponse
from app.services.claims_generator import ClaimsGenerator
from app.services.rate_card_calculator import quantize_amount

router = APIRouter(prefix="/claims", tags=["Claims Management"])


@router.get("/", response_model=Union[PaginatedClaimResponse, List[ClaimResponse]])
def list_claims(
    response: Response,
    search: Optional[str] = None,
    partner_id: Optional[str] = None,
    claim_reason: Optional[str] = None,
    claim_status: Optional[str] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    sort_by: Optional[str] = Query("created_at"),
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
    List claims with server-side search, multi-facet filtering, sorting, and pagination.
    Accessible to both Finance Executives and Co-founders (read-only audit).
    """
    query = db.query(Claim)

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Claim.external_order_id.ilike(s),
                Claim.order_id.ilike(s),
                Claim.notes.ilike(s),
                Claim.claim_reason.ilike(s)
            )
        )

    if partner_id and partner_id.upper() != "ALL":
        query = query.filter(Claim.partner_id == partner_id.lower())

    if claim_reason and claim_reason.upper() != "ALL":
        query = query.filter(Claim.claim_reason == claim_reason.lower())

    if claim_status and claim_status.upper() != "ALL":
        query = query.filter(Claim.claim_status == claim_status.lower())

    if min_amount is not None:
        query = query.filter(Claim.claim_amount >= min_amount)

    if max_amount is not None:
        query = query.filter(Claim.claim_amount <= max_amount)

    total_count = query.count()

    # Sorting
    sort_col = Claim.created_at
    if sort_by == "claim_amount":
        sort_col = Claim.claim_amount
    elif sort_by == "recovered_amount":
        sort_col = Claim.recovered_amount
    elif sort_by == "claim_status":
        sort_col = Claim.claim_status
    elif sort_by in ("order_id", "external_order_id"):
        sort_col = Claim.external_order_id
    elif sort_by == "partner_id":
        sort_col = Claim.partner_id
    elif sort_by == "claim_reason":
        sort_col = Claim.claim_reason

    is_asc = (sort_dir or "").lower() == "asc"
    order_clause = asc(sort_col) if is_asc else desc(sort_col)

    # Pagination
    effective_limit = page_size if page_size is not None else (limit if limit is not None else 50)
    effective_limit = min(max(1, effective_limit), 500)

    if page is not None:
        effective_page = max(1, page)
        effective_offset = (effective_page - 1) * effective_limit
    else:
        effective_offset = max(0, skip if skip is not None else 0)
        effective_page = (effective_offset // effective_limit) + 1

    total_pages = max(1, (total_count + effective_limit - 1) // effective_limit) if total_count > 0 else 1

    claims = (
        query
        .order_by(order_clause, desc(Claim.created_at))
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
        return PaginatedClaimResponse(
            items=claims,
            total=total_count,
            page=effective_page,
            page_size=effective_limit,
            pages=total_pages
        )
    return claims


@router.get("/summary", response_model=ClaimsSummaryResponse)
def get_claims_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Aggregates overall claims KPIs: counts by status, claimed amount,
    recovered amount, outstanding balance, and recovery rate.
    """
    all_claims = db.query(Claim).all()

    total_claims = len(all_claims)
    total_claim_amount = Decimal("0.00")
    total_recovered_amount = Decimal("0.00")

    status_counts = {
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
        status_counts[c.claim_status] = status_counts.get(c.claim_status, 0) + 1

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

    return ClaimsSummaryResponse(
        total_claims=total_claims,
        total_claim_amount=quantize_amount(total_claim_amount),
        total_recovered_amount=quantize_amount(total_recovered_amount),
        total_outstanding_amount=total_outstanding,
        status_counts=status_counts,
        recovery_rate_pct=recovery_rate,
        partner_claims_summary=partner_claims_summary
    )


def sanitize_csv_cell(val: Any) -> str:
    """
    Prevents CSV injection attacks (CWE-1236) by escaping leading formula triggers.
    """
    s = str(val) if val is not None else ""
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


@router.get("/export/csv")
def export_claims_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Exports all claims and supporting financial evidence to CSV.
    Accessible to both Finance Executives and Co-founders.
    Includes formula-injection sanitization for safe opening in Excel.
    """
    claims = (
        db.query(Claim)
        .order_by(desc(Claim.created_at))
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV Header
    writer.writerow([
        "Claim ID",
        "Order ID",
        "Partner",
        "Claim Reason",
        "Claim Status",
        "Claim Amount (INR)",
        "Recovered Amount (INR)",
        "Outstanding Amount (INR)",
        "Recovered Date",
        "Created Date",
        "Notes",
        "Settlement Gap (INR)",
        "Freight Excess (INR)",
        "Return Loss (INR)"
    ])

    for c in claims:
        ev = c.evidence_json or {}
        outstanding = quantize_amount(max(Decimal("0.00"), c.claim_amount - c.recovered_amount))
        writer.writerow([
            str(c.id),
            sanitize_csv_cell(c.external_order_id),
            sanitize_csv_cell(c.partner_id),
            sanitize_csv_cell(c.claim_reason),
            sanitize_csv_cell(c.claim_status),
            f"{c.claim_amount:.2f}",
            f"{c.recovered_amount:.2f}",
            f"{outstanding:.2f}",
            c.recovered_at.isoformat() if c.recovered_at else "N/A",
            c.created_at.isoformat(),
            sanitize_csv_cell(c.notes or ""),
            ev.get("settlement_gap", "0.00"),
            ev.get("freight_excess", "0.00"),
            ev.get("return_loss", "0.00")
        ])

    output.seek(0)
    filename = f"leakcheck_claims_evidence_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/generate", response_model=Dict[str, Any])
def trigger_claims_generation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec"]))
):
    """
    Generates draft claims for all orders with confirmed discrepancies and money at risk > 0.
    RBAC: Finance Executive only (Co-founders have read-only audit access, returns 403).
    """
    generator = ClaimsGenerator(db)
    generated = generator.generate_draft_claims()
    return {
        "status": "success",
        "claims_generated_or_updated": len(generated)
    }


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
def get_claim_detail(
    claim_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Get full claim details including linked order reconciliation breakdown.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found"
        )

    linked_order = db.query(OrderRecon).filter(OrderRecon.id == claim.order_recon_id).first()

    return ClaimDetailResponse(
        id=claim.id,
        order_recon_id=claim.order_recon_id,
        external_order_id=claim.external_order_id,
        order_id=claim.order_id,
        partner_id=claim.partner_id,
        claim_amount=claim.claim_amount,
        recovered_amount=claim.recovered_amount,
        recovered_at=claim.recovered_at,
        claim_reason=claim.claim_reason,
        evidence_json=claim.evidence_json,
        claim_status=claim.claim_status,
        notes=claim.notes,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        order=OrderReconResponse.model_validate(linked_order) if linked_order else None
    )


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: uuid.UUID,
    payload: ClaimUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec"]))
):
    """
    Update permitted claim fields: status, notes, recovery amount, and recovery date.
    RBAC: Finance Executive only (Co-founders cannot modify claims).
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found"
        )

    # 1. Update Notes if provided
    if payload.notes is not None:
        claim.notes = payload.notes

    # 2. Update Recovery Details if provided
    if payload.recovered_amount is not None:
        if payload.recovered_amount < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recovered amount cannot be negative"
            )
        if payload.recovered_amount > claim.claim_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Recovered amount (₹{payload.recovered_amount}) cannot exceed claim amount (₹{claim.claim_amount})"
            )
        claim.recovered_amount = quantize_amount(payload.recovered_amount)

        # Set recovery date
        if payload.recovered_at is not None:
            claim.recovered_at = payload.recovered_at
        elif claim.recovered_amount > Decimal("0.00") and claim.recovered_at is None:
            claim.recovered_at = datetime.now(timezone.utc)
        elif claim.recovered_amount == Decimal("0.00"):
            claim.recovered_at = None

        # Auto-advance to recovered if 100% recovered and status was not explicitly overridden
        if claim.recovered_amount == claim.claim_amount and payload.claim_status is None:
            claim.claim_status = "recovered"

    # 3. Update Status if provided
    if payload.claim_status is not None:
        valid_statuses = ["draft", "submitted", "in_review", "approved", "rejected", "recovered"]
        status_norm = payload.claim_status.lower()
        if status_norm not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid claim status '{payload.claim_status}'. Must be one of: {valid_statuses}"
            )
        claim.claim_status = status_norm

    claim.updated_at = datetime.now(timezone.utc)
    db.add(claim)
    db.commit()
    db.refresh(claim)

    return claim
