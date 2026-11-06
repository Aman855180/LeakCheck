import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Numeric, ForeignKey, Index, UniqueConstraint, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class EventLineageLock(Base):
    __tablename__ = "event_lineage_locks"

    lineage_root_id = Column(UUID(as_uuid=True), ForeignKey("order_events.id", ondelete="RESTRICT"), primary_key=True)
    locked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text("NOW()"), nullable=False)


class OrderEvent(Base):
    __tablename__ = "order_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(64), unique=True, nullable=False)
    external_order_id = Column(String(128), nullable=False, index=True)
    order_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Populated when linked
    source_partner_id = Column(String(64), ForeignKey("partners.id"), nullable=False)
    event_type = Column(String(32), nullable=False)  # 'settlement_credit', 'cod_remittance', 'freight_charge', 'settlement_reversal'
    fee_type = Column(String(64), nullable=True)     # 'commission', 'shipping_fee', 'fixed_fee', etc.
    transaction_reference = Column(String(128), nullable=True)
    amendment_reference = Column(String(128), nullable=False, default="ORIGINAL")
    event_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    settlement_credit = Column(Numeric(12, 2), default=0.00)
    commission = Column(Numeric(12, 2), default=0.00)
    fixed_fee = Column(Numeric(12, 2), default=0.00)
    shipping_fee = Column(Numeric(12, 2), default=0.00)
    cod_fee = Column(Numeric(12, 2), default=0.00)
    return_fee = Column(Numeric(12, 2), default=0.00)
    other_fee = Column(Numeric(12, 2), default=0.00)
    freight_amount = Column(Numeric(12, 2), default=0.00)
    tcs = Column(Numeric(12, 2), default=0.00)
    tds = Column(Numeric(12, 2), default=0.00)
    tracking_number = Column(String(128), nullable=True)
    upload_id = Column(UUID(as_uuid=True), nullable=True)
    source_row_number = Column(Integer, nullable=True)
    lineage_root_id = Column(UUID(as_uuid=True), nullable=False)
    supersedes_event_id = Column(UUID(as_uuid=True), ForeignKey("order_events.id", ondelete="RESTRICT"), nullable=True)
    reverses_event_id = Column(UUID(as_uuid=True), ForeignKey("order_events.id", ondelete="RESTRICT"), nullable=True)
    raw_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("supersedes_event_id", name="uq_order_events_single_successor"),
        CheckConstraint("id <> supersedes_event_id", name="chk_no_self_supersession"),
        Index("idx_order_events_lookup", "source_partner_id", "external_order_id", "event_type"),
        Index("idx_order_events_lineage", "lineage_root_id"),
    )
