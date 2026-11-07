from datetime import date
from decimal import Decimal
from typing import Dict, Any, List
from pydantic import BaseModel
from app.schemas.claim import ClaimsSummaryResponse


class DashboardMetricsResponse(BaseModel):
    as_of: str
    total_orders: int
    total_money_at_risk: Decimal
    
    # Financial Leakage Components (Strictly non-overlapping)
    total_settlement_gap: Decimal
    total_freight_excess: Decimal
    total_return_loss: Decimal
    
    # Status Counts
    status_counts: Dict[str, int]
    
    # Aging Buckets: counts and money at risk
    age_bucket_counts: Dict[str, int]
    age_bucket_risk: Dict[str, Decimal]
    
    # Risk Breakdown by Partner
    partner_risk_breakdown: Dict[str, Decimal]
    partner_order_counts: Dict[str, int]
    
    # Risk Breakdown by Discrepancy Reason Code
    reason_code_risk_breakdown: Dict[str, Decimal]
    reason_code_counts: Dict[str, int]
    
    # Claims Metrics
    claims_summary: ClaimsSummaryResponse
