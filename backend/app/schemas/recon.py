import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class ReconRunRequest(BaseModel):
    as_of: Optional[date] = None
    order_ids: Optional[List[str]] = None


class OrderReconResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_order_id: str
    order_id: str
    partner_id: str
    channel: str
    payment_mode: str
    order_date: datetime
    order_value: Decimal
    rate_card_id: Optional[uuid.UUID] = None
    expected_amount: Optional[Decimal] = None
    received_amount: Decimal
    settlement_credit: Decimal
    cod_remittance: Decimal
    expected_commission: Decimal
    actual_commission: Decimal
    expected_fixed_fee: Decimal
    actual_fixed_fee: Decimal
    expected_freight: Decimal
    actual_freight: Decimal
    expected_cod_fee: Decimal
    actual_cod_fee: Decimal
    tcs_amount: Decimal
    tds_amount: Decimal
    difference: Optional[Decimal] = None
    status: str
    reason_codes: List[str]
    due_date: Optional[datetime] = None
    age_days: int
    age_bucket: str
    money_at_risk: Decimal
    settlement_gap_component: Decimal
    freight_excess_component: Decimal
    return_loss_component: Decimal
    breakdown_json: Dict[str, Any]
    source_events_count: int
    computed_at: datetime


class PaginatedOrderReconResponse(BaseModel):
    items: List[OrderReconResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TimelineEventItem(BaseModel):
    id: str
    feed_type: str  # 'orders' | 'settlement' | 'cod' | 'freight' | 'tracking' | 'warehouse' | 'reversal'
    event_type: str
    event_timestamp: datetime
    source_partner_id: str
    amount: Optional[Decimal] = None
    transaction_reference: Optional[str] = None
    status: Optional[str] = None
    details: Dict[str, Any] = {}


class OrderTimelineResponse(BaseModel):
    order_id: str
    external_order_id: str
    partner_id: str
    total_events: int
    timeline: List[TimelineEventItem]


class ReconSummaryResponse(BaseModel):
    as_of: str
    total_orders: int
    total_money_at_risk: Decimal
    settled_count: int
    short_paid_count: int
    unpaid_past_due_count: int
    freight_overcharged_count: int
    return_not_received_count: int
    pending_count: int
    age_bucket_counts: Dict[str, int]
    partner_risk_breakdown: Dict[str, Decimal]
