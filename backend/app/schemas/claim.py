import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.schemas.recon import OrderReconResponse


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_recon_id: uuid.UUID
    external_order_id: str
    order_id: str
    partner_id: str
    claim_amount: Decimal
    recovered_amount: Decimal
    recovered_at: Optional[datetime] = None
    claim_reason: str
    evidence_json: Dict[str, Any]
    claim_status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClaimDetailResponse(ClaimResponse):
    order: Optional[OrderReconResponse] = None


class ClaimUpdateRequest(BaseModel):
    claim_status: Optional[str] = None
    notes: Optional[str] = None
    recovered_amount: Optional[Decimal] = None
    recovered_at: Optional[datetime] = None


class PaginatedClaimResponse(BaseModel):
    items: List[ClaimResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ClaimsSummaryResponse(BaseModel):
    total_claims: int
    total_claim_amount: Decimal
    total_recovered_amount: Decimal
    total_outstanding_amount: Decimal
    status_counts: Dict[str, int]
    recovery_rate_pct: Decimal
    partner_claims_summary: Dict[str, Dict[str, Any]]
