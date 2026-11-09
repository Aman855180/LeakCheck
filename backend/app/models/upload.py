import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False)
    partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False)
    source_type = Column(String(32), nullable=False)  # 'orders', 'settlement', 'cod', 'freight', 'receipts'
    file_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    file_size_bytes = Column(BigInteger, nullable=False)
    row_count = Column(Integer, default=0, nullable=False)
    mapping_version = Column(Integer, nullable=True)
    processing_status = Column(String(32), default="uploaded", nullable=False)  # 'uploaded', 'mapping_pending', 'processing', 'completed', 'failed'
    error_count = Column(Integer, default=0, nullable=False)
    retry_of_upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
