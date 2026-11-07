import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class UploadRowError(Base):
    __tablename__ = "upload_row_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True)
    source_row_number = Column(Integer, nullable=False)
    error_code = Column(String(64), nullable=False, index=True)  # 'MISSING_ORDER_ID', 'INVALID_NUMERIC', 'QUARANTINED', etc.
    error_message = Column(Text, nullable=False)
    raw_record = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
