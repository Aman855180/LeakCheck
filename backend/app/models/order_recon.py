import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class OrderRecon(Base):
    __tablename__ = "order_recon"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(128), unique=True, nullable=False, index=True)
    partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False, index=True)
    channel = Column(String(64), nullable=False)
    payment_mode = Column(String(32), default="PREPAID", nullable=False)
    order_date = Column(DateTime(timezone=True), nullable=False, index=True)
    order_value = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    rate_card_id = Column(UUID(as_uuid=True), ForeignKey("rate_cards.id", ondelete="SET NULL"), nullable=True)
    expected_amount = Column(Numeric(12, 2), nullable=True)  # Nullable when no valid rate card exists
    received_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    settlement_credit = Column(Numeric(12, 2), nullable=False, default=0.00)
    cod_remittance = Column(Numeric(12, 2), nullable=False, default=0.00)
    expected_commission = Column(Numeric(12, 2), nullable=False, default=0.00)
    actual_commission = Column(Numeric(12, 2), nullable=False, default=0.00)
    expected_fixed_fee = Column(Numeric(12, 2), nullable=False, default=0.00)
    actual_fixed_fee = Column(Numeric(12, 2), nullable=False, default=0.00)
    expected_freight = Column(Numeric(12, 2), nullable=False, default=0.00)
    actual_freight = Column(Numeric(12, 2), nullable=False, default=0.00)
    expected_cod_fee = Column(Numeric(12, 2), nullable=False, default=0.00)
    actual_cod_fee = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    tcs_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    tds_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    difference = Column(Numeric(12, 2), nullable=True)  # received - expected
    status = Column(String(32), nullable=False, index=True)  # 'settled', 'short_paid', 'unpaid_past_due', 'freight_overcharged', 'return_not_received', 'pending'
    reason_codes = Column(JSONB, nullable=False, default=list)  # ['cod_remittance_missing', ...]
    
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    age_days = Column(Integer, nullable=False, default=0)
    age_bucket = Column(String(32), nullable=False, default="0-7")  # '0-7', '8-15', '16-30', '30+'
    
    # Non-overlapping Money at Risk components
    money_at_risk = Column(Numeric(12, 2), nullable=False, default=0.00, index=True)
    settlement_gap_component = Column(Numeric(12, 2), nullable=False, default=0.00)
    freight_excess_component = Column(Numeric(12, 2), nullable=False, default=0.00)
    return_loss_component = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    breakdown_json = Column(JSONB, nullable=False, default=dict)
    source_events_count = Column(Integer, nullable=False, default=0)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_order_recon_partner_status", "partner_id", "status"),
        Index("ix_order_recon_computed_at", "computed_at"),
    )
