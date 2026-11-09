import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class UploadMappingSuggestion(Base):
    __tablename__ = "upload_mapping_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(
        UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    file_name = Column(String(255), nullable=False)
    source_type = Column(String(32), nullable=False)
    total_rows = Column(Integer, default=0, nullable=False)

    # Persisted review metadata
    detected_columns = Column(JSONB, nullable=False)  # List[str]
    dropped_pii_columns = Column(JSONB, nullable=False, default=list)  # List[str]
    preview_rows = Column(JSONB, nullable=False, default=list)  # List[Dict[str, Any]] (PII sanitized)
    suggested_mapping = Column(JSONB, nullable=False)  # Dict[canonical_field, suggestion_obj]
    missing_required = Column(JSONB, nullable=False, default=list)  # List[str]
    canonical_fields = Column(JSONB, nullable=False, default=list)  # List[Dict[str, Any]]

    # Compatibility and version context
    is_mapping_compatible = Column(Boolean, default=False, nullable=False)
    incompatibility_reasons = Column(JSONB, nullable=False, default=list)  # List[str]
    active_mapping_version = Column(Integer, nullable=True)

    # Status tracking
    generation_status = Column(String(32), default="completed", nullable=False)  # 'completed', 'failed', 'partial'
    generation_error = Column(String(1000), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    upload = relationship("Upload", backref="mapping_suggestion", uselist=False)
    source = relationship("Source")
