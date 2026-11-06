import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.models.user import User
from app.models.tracking_rule import (
    CourierTrackingRule,
    CourierRuleActivation,
    CourierRuleActivationHistory
)


def test_approved_tracking_rule_immutable(db_session):
    """Verify approved courier tracking rule cannot be modified in place."""
    user = db_session.query(User).filter(User.role == "finance_exec").first()
    rule_v1 = CourierTrackingRule(
        courier_partner_id="delhivery",
        raw_status_code="DLV_DOCK_01",
        raw_facility_code="BLR_HUB",
        normalized_status="delivered_to_warehouse",
        registered_facility_id="BLR-WH-01",
        version=1,
        approved_by=user.id,
        approved_at=datetime.now(timezone.utc)
    )
    db_session.add(rule_v1)
    db_session.commit()

    # Attempt in-place update on approved rule -> must raise trigger exception
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(
            text("UPDATE courier_tracking_rules SET normalized_status = 'in_transit' WHERE id = :id"),
            {"id": rule_v1.id}
        )
        db_session.commit()

    db_session.rollback()
    assert "immutable" in str(exc_info.value)


def test_tracking_rule_activation_and_view(db_session):
    """Verify version activation registry and active_courier_tracking_rules view."""
    user = db_session.query(User).filter(User.role == "finance_exec").first()
    rule_v1 = CourierTrackingRule(
        courier_partner_id="bluedart",
        raw_status_code="BD_WH_SCAN",
        raw_facility_code="BLR_MAIN",
        normalized_status="delivered_to_warehouse",
        registered_facility_id="BLR-WH-01",
        version=1,
        approved_by=user.id,
        approved_at=datetime.now(timezone.utc)
    )
    db_session.add(rule_v1)
    db_session.commit()

    # Activate version 1
    activation = CourierRuleActivation(
        courier_partner_id=rule_v1.courier_partner_id,
        raw_status_code=rule_v1.raw_status_code,
        raw_facility_code=rule_v1.raw_facility_code,
        active_rule_id=rule_v1.id,
        activated_by=user.id
    )
    history = CourierRuleActivationHistory(
        courier_partner_id=rule_v1.courier_partner_id,
        raw_status_code=rule_v1.raw_status_code,
        raw_facility_code=rule_v1.raw_facility_code,
        rule_id=rule_v1.id,
        action="ACTIVATED",
        performed_by=user.id
    )
    db_session.add(activation)
    db_session.add(history)
    db_session.commit()

    # Query view
    result = db_session.execute(
        text("SELECT id, normalized_status FROM active_courier_tracking_rules WHERE courier_partner_id = 'bluedart'")
    ).fetchone()

    assert result is not None
    assert str(result.id) == str(rule_v1.id)
    assert result.normalized_status == "delivered_to_warehouse"
