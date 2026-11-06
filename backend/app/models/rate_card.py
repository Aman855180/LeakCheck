import uuid
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, DATERANGE
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from app.models.base import Base


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False)
    channel = Column(String(64), nullable=False)
    rule_type = Column(String(64), nullable=False)  # e.g., 'marketplace_standard', 'courier_standard', 'd2c_standard'
    params_json = Column(JSONB, nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=True)  # NULL represents open-ended infinity
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        # PostgreSQL half-open range: daterange(valid_from, COALESCE(valid_until, 'infinity'), '[)')
        # Validates no overlapping effective periods for the same (partner, channel, rule_type)
        ExcludeConstraint(
            (partner_id, "="),
            (channel, "="),
            (rule_type, "="),
            (
                text("daterange(valid_from, COALESCE(valid_until, 'infinity'::date), '[)')"),
                "&&"
            ),
            where=(is_active == True),
            name="uq_rate_card_no_overlap"
        ),
    )

    def __repr__(self) -> str:
        return f"<RateCard partner={self.partner_id} channel={self.channel} from={self.valid_from} until={self.valid_until}>"
