import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class CourierTrackingRule(Base):
    __tablename__ = "courier_tracking_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    courier_partner_id = Column(String(64), ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False)
    raw_status_code = Column(String(64), nullable=False)
    raw_facility_code = Column(String(64), nullable=False)
    normalized_status = Column(String(64), nullable=False)
    registered_facility_id = Column(String(64), nullable=True)  # e.g., 'WH-BLR-01'
    version = Column(Integer, nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("courier_partner_id", "raw_status_code", "raw_facility_code", "version", name="uq_courier_mapping"),
    )


class CourierRuleActivation(Base):
    __tablename__ = "courier_rule_activations"

    courier_partner_id = Column(String(64), nullable=False, primary_key=True)
    raw_status_code = Column(String(64), nullable=False, primary_key=True)
    raw_facility_code = Column(String(64), nullable=False, primary_key=True)
    active_rule_id = Column(UUID(as_uuid=True), ForeignKey("courier_tracking_rules.id", ondelete="RESTRICT"), nullable=False)
    activated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    activated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CourierRuleActivationHistory(Base):
    __tablename__ = "courier_rule_activation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    courier_partner_id = Column(String(64), nullable=False)
    raw_status_code = Column(String(64), nullable=False)
    raw_facility_code = Column(String(64), nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("courier_tracking_rules.id", ondelete="RESTRICT"), nullable=False)
    action = Column(String(32), nullable=False)  # 'ACTIVATED', 'RETIRED'
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
