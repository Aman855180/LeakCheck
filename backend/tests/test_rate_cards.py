import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError
from app.models.rate_card import RateCard


def test_consecutive_rate_cards_no_overlap(db_session):
    """Verify half-open [) interval allows consecutive rate cards to touch dates without error."""
    card1 = RateCard(
        partner_id="myntra",
        channel="marketplace",
        rule_type="apparel_standard",
        params_json={"commission_pct": 14.0},
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 7, 1),
        is_active=True
    )
    card2 = RateCard(
        partner_id="myntra",
        channel="marketplace",
        rule_type="apparel_standard",
        params_json={"commission_pct": 16.0},
        valid_from=date(2026, 7, 1),
        valid_until=None,
        is_active=True
    )

    db_session.add(card1)
    db_session.commit()

    db_session.add(card2)
    db_session.commit()

    assert card1.id is not None
    assert card2.id is not None


def test_overlapping_rate_cards_rejected(db_session):
    """Verify overlapping effective rate cards trigger btree_gist exclusion constraint."""
    base_card = RateCard(
        partner_id="myntra",
        channel="marketplace",
        rule_type="apparel_overlap_test",
        params_json={"commission_pct": 14.0},
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 7, 1),
        is_active=True
    )
    db_session.add(base_card)
    db_session.flush()

    overlapping_card = RateCard(
        partner_id="myntra",
        channel="marketplace",
        rule_type="apparel_overlap_test",
        params_json={"commission_pct": 20.0},
        valid_from=date(2026, 5, 1),
        valid_until=date(2026, 8, 1),
        is_active=True
    )

    with pytest.raises(IntegrityError) as exc_info:
        with db_session.begin_nested():
            db_session.add(overlapping_card)
            db_session.flush()

    assert "uq_rate_card_no_overlap" in str(exc_info.value)


def test_rate_card_lookup_endpoint(client, finance_exec_cookies):
    # Lookup Amazon marketplace rate card for 2026-10-18
    response = client.get(
        "/api/v1/rate-cards/lookup",
        params={
            "partner_id": "amazon",
            "channel": "marketplace",
            "rule_type": "marketplace_standard",
            "target_date": "2026-10-18"
        },
        cookies=finance_exec_cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["partner_id"] == "amazon"
    assert data["params_json"]["commission_pct"] == 15.0
    assert data["params_json"]["fixed_fee"] == 30.15
    assert data["params_json"]["forward_shipping_fee"] == 90.00
