import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from app.services.rate_card_calculator import RateCardCalculator, quantize_amount
from app.models.rate_card import RateCard


def test_quantize_amount():
    assert quantize_amount(1409) == Decimal("1409.00")
    assert quantize_amount("1409.555") == Decimal("1409.56")
    assert quantize_amount("1409.554") == Decimal("1409.55")
    assert quantize_amount(None) == Decimal("0.00")


def test_benchmark_sample_1_website_cod(db_session):
    """
    Sample 1 — ORD-W-204118
    Website COD, Order Value ₹1,499.00 -> Net Expected ₹1,409.00.
    """
    calculator = RateCardCalculator(db_session)
    result = calculator.calculate_expected_settlement(
        partner_id="shopify",
        channel="d2c",
        order_date=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        order_value=Decimal("1499.00"),
        payment_mode="COD",
        is_returned=False
    )
    assert result.rate_card is not None
    assert result.expected_amount == Decimal("1409.00")
    assert result.expected_freight == Decimal("60.00")
    assert result.expected_cod_fee == Decimal("30.00")
    assert result.expected_commission == Decimal("0.00")
    assert result.due_days == 7


def test_benchmark_sample_2_marketplace_standard(db_session):
    """
    Sample 2 — ORD-M-88120
    Marketplace Prepaid, Order Value ₹1,199.00 -> Net Expected ₹899.00.
    15% comm (₹179.85) + ₹30.15 fixed + ₹90 shipping = ₹300 deductions.
    """
    calculator = RateCardCalculator(db_session)
    result = calculator.calculate_expected_settlement(
        partner_id="amazon",
        channel="marketplace",
        order_date=datetime(2026, 3, 2, 11, 30, tzinfo=timezone.utc),
        order_value=Decimal("1199.00"),
        payment_mode="PREPAID",
        is_returned=False
    )
    assert result.rate_card is not None
    assert result.expected_commission == Decimal("179.85")
    assert result.expected_fixed_fee == Decimal("30.15")
    assert result.expected_freight == Decimal("90.00")
    assert result.expected_amount == Decimal("899.00")
    assert result.due_days == 10


def test_benchmark_sample_3_website_prepaid_return(db_session):
    """
    Sample 3 — ORD-W-204377
    Website Prepaid Return, Order Value ₹2,398.00 -> Net Expected -₹96.00.
    -₹60 forward shipping - ₹36 reverse shipping = -₹96.00.
    """
    calculator = RateCardCalculator(db_session)
    result = calculator.calculate_expected_settlement(
        partner_id="shopify",
        channel="d2c",
        order_date=datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc),
        order_value=Decimal("2398.00"),
        payment_mode="PREPAID",
        is_returned=True
    )
    assert result.rate_card is not None
    assert result.expected_amount == Decimal("-96.00")
    assert result.expected_freight == Decimal("96.00")  # 60 + 36


def test_missing_rate_card_returns_none(db_session):
    """
    When no rate card exists for a partner/date combination,
    expected_amount must be None (nullable) per Phase 0 agreement.
    """
    calculator = RateCardCalculator(db_session)
    result = calculator.calculate_expected_settlement(
        partner_id="unknown_unregistered_partner",
        channel="unknown_channel",
        order_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        order_value=Decimal("500.00")
    )
    assert result.rate_card is None
    assert result.expected_amount is None
    assert result.breakdown.get("error") == "NO_VALID_RATE_CARD"
