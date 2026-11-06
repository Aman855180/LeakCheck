import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False)
    source_type = Column(String(32), nullable=False)  # 'orders', 'settlement', 'cod', 'freight', 'receipts'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("partner_id", "source_type", name="uq_partner_source"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} partner={self.partner_id} type={self.source_type}>"
