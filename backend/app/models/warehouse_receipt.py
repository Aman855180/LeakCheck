import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class WarehouseReceipt(Base):
    __tablename__ = "warehouse_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(128), nullable=False, index=True)
    tracking_number = Column(String(128), nullable=True, index=True)
    warehouse_id = Column(String(64), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    receipt_status = Column(String(32), default="delivered", nullable=False)  # 'delivered', 'damaged', 'qc_rejected', 'lost'
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    source_row_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_wh_receipt_order_wh", "order_id", "warehouse_id"),
    )
