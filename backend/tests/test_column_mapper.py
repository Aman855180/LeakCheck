import pytest
from app.services.column_mapper import (
    suggest_column_mappings,
    validate_mapping_completeness,
    normalize_header
)


def test_normalize_header():
    assert normalize_header("Order ID") == "order_id"
    assert normalize_header("TOTAL-PRICE ") == "total_price"
    assert normalize_header("  Tracking__Number ") == "tracking_number"


def test_suggest_column_mappings_exact():
    source_cols = ["order_id", "order_value", "payment_mode", "order_date"]
    result = suggest_column_mappings(source_cols, source_type="orders")

    suggestions = result["suggestions"]
    assert suggestions["external_order_id"]["column"] == "order_id"
    assert suggestions["external_order_id"]["match_type"] == "EXACT"
    assert suggestions["external_order_id"]["confidence"] == 1.0

    assert suggestions["order_value"]["column"] == "order_value"
    assert suggestions["order_value"]["match_type"] == "EXACT"
    assert suggestions["order_value"]["confidence"] == 1.0

    assert suggestions["payment_mode"]["column"] == "payment_mode"
    assert suggestions["payment_mode"]["match_type"] == "EXACT"

    assert len(result["missing_required"]) == 0


def test_suggest_column_mappings_fuzzy():
    # Subtle typo / alternative naming
    source_cols = ["ord_number", "sale_amt", "courier_status"]
    result = suggest_column_mappings(source_cols, source_type="orders")

    suggestions = result["suggestions"]
    # ord_number should fuzzy match external_order_id
    assert suggestions["external_order_id"]["column"] == "ord_number"
    assert suggestions["external_order_id"]["match_type"] == "FUZZY"
    assert suggestions["external_order_id"]["confidence"] >= 0.70

    # sale_amt should fuzzy match order_value
    assert suggestions["order_value"]["column"] == "sale_amt"
    assert suggestions["order_value"]["confidence"] >= 0.70


def test_validate_mapping_completeness():
    # Orders requires external_order_id, order_value, order_date
    complete_mapping = {
        "external_order_id": "Order_No",
        "order_value": "Amount",
        "order_date": "Timestamp"
    }
    is_valid, missing = validate_mapping_completeness(complete_mapping, "orders")
    assert is_valid is True
    assert len(missing) == 0

    # Missing order_date
    incomplete_mapping = {
        "external_order_id": "Order_No",
        "order_value": "Amount"
    }
    is_valid, missing = validate_mapping_completeness(incomplete_mapping, "orders")
    assert is_valid is False
    assert "order_date" in missing


def test_validate_mapping_completeness_settlement():
    mapping = {"external_order_id": "Order_No", "settlement_amount": "Bank_Payout"}
    is_valid, missing = validate_mapping_completeness(mapping, "settlement")
    assert is_valid is True

    bad_mapping = {"settlement_amount": "Bank_Payout"}
    is_valid, missing = validate_mapping_completeness(bad_mapping, "settlement")
    assert is_valid is False
    assert "external_order_id" in missing
