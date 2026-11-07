import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(128), nullable=False, index=True)
    tracking_number = Column(String(128), nullable=False, index=True)
    courier_code = Column(String(64), nullable=False, index=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    raw_status_code = Column(String(64), nullable=False)
    raw_facility_code = Column(String(64), nullable=True)
    raw_telemetry = Column(JSONB, nullable=False)
    mapping_rule_id = Column(UUID(as_uuid=True), ForeignKey("courier_tracking_rules.id", ondelete="SET NULL"), nullable=True)
    mapping_version = Column(Integer, nullable=True)
    verification_outcome = Column(String(64), nullable=False)  # 'VALID_DELIVERY', 'IN_TRANSIT', 'RTO', 'UNDELIVERED', 'UNMAPPED'
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    source_row_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_tracking_order_courier", "order_id", "courier_code"),
    )
