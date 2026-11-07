import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class Claim(Base):
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(128), nullable=False, index=True)
    partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False, index=True)
    claim_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    recovered_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    claim_reason = Column(String(64), nullable=False, index=True)
    evidence_json = Column(JSONB, nullable=False, default=dict)
    claim_status = Column(String(32), default="draft", nullable=False, index=True)  # 'draft', 'submitted', 'in_review', 'approved', 'rejected', 'recovered'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("order_id", "claim_reason", name="uq_order_claim_reason"),
    )
