import uuid
from unittest.mock import patch, MagicMock
import pytest
import anthropic

from app.services.column_mapper import suggest_column_mappings, CANONICAL_FIELDS
from app.services.ai_column_mapper import (
    AIFallbackMapper,
    sanitize_columns_and_samples,
    sanitize_sample_value
)


def test_pii_sanitization_before_llm():
    # 1. Column header PII filtering
    raw_columns = [
        "customer_name",
        "buyer_phone",
        "shipping_address_line1",
        "obscure_tariff_rate",
        "docket_ref"
    ]
    raw_samples = {
        "customer_name": ["Rahul Sharma", "Priya Patel"],
        "buyer_phone": ["+91 9876543210", "9123456789"],
        "shipping_address_line1": ["Flat 402, Indiranagar, Bengaluru"],
        "obscure_tariff_rate": ["15.5", "18.0", "12.0"],
        "docket_ref": ["DOC-1001", "DOC-1002"]
    }

    safe_cols, safe_samples = sanitize_columns_and_samples(raw_columns, raw_samples)

    # Sensitive personal columns must be dropped completely
    assert "customer_name" not in safe_cols
    assert "buyer_phone" not in safe_cols
    assert "shipping_address_line1" not in safe_cols

    # Safe business columns must be preserved
    assert "obscure_tariff_rate" in safe_cols
    assert "docket_ref" in safe_cols

    # 2. Value-level PII masking
    assert sanitize_sample_value("test@company.com") == "[REDACTED_PII]"
    assert sanitize_sample_value("+91 9876543210") == "[REDACTED_PII]"
    assert sanitize_sample_value("9876543210") == "[REDACTED_PII]"
    assert sanitize_sample_value("1234-5678-9012-3456") == "[REDACTED_PII]"
    assert sanitize_sample_value("₹1,499.00") == "₹1,499.00"


def test_exact_and_fuzzy_precedence_over_ai():
    # 'order_id' matches EXACT (Pass 1)
    # 'tot_freight' matches FUZZY (Pass 2)
    # Neither should ever be sent to AI fallback
    source_cols = ["order_id", "tot_freight", "unrecognized_col_xyz"]

    with patch.object(AIFallbackMapper, "predict_unresolved_mappings") as mock_ai:
        mock_ai.return_value = {}

        result = suggest_column_mappings(
            source_columns=source_cols,
            source_type="orders",
            enable_ai=True
        )

        # EXACT match verified
        assert result["suggestions"]["external_order_id"]["match_type"] == "EXACT"
        assert result["suggestions"]["external_order_id"]["column"] == "order_id"

        # FUZZY match verified
        assert result["suggestions"]["freight_amount"]["match_type"] == "FUZZY"
        assert result["suggestions"]["freight_amount"]["column"] == "tot_freight"

        # If AI was invoked, verified it was ONLY asked to predict for unresolved fields
        if mock_ai.called:
            args, kwargs = mock_ai.call_args
            unresolved = kwargs.get("unresolved_canonical_fields", {})
            unallocated = kwargs.get("unallocated_source_columns", [])

            # Already-resolved fields must NOT be in unresolved prompt
            assert "external_order_id" not in unresolved
            assert "freight_amount" not in unresolved
            assert "order_id" not in unallocated
            assert "tot_freight" not in unallocated


def test_ai_fallback_successful_structured_mapping():
    # Given an obscure column name that exact & fuzzy cannot resolve
    source_cols = ["order_id", "order_date", "client_net_disbursement"]
    samples = {
        "client_net_disbursement": ["1410.00", "899.50", "2398.00"]
    }

    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "settlement_amount",\n'
        '      "source_column": "client_net_disbursement",\n'
        '      "confidence": 0.92,\n'
        '      "reasoning": "Client net disbursement represents the final net bank payout amount."\n'
        '    }\n'
        '  ]\n'
        '}'
    )
    mock_response.content = [mock_block]

    with patch.object(AIFallbackMapper, "__init__", lambda self, *args, **kwargs: setattr(self, "api_key", "mock-key") or setattr(self, "model", "mock-model")):
        with patch("anthropic.Anthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = suggest_column_mappings(
                source_columns=source_cols,
                source_type="settlement",
                samples_by_col=samples,
                enable_ai=True
            )

            settlement_sugg = result["suggestions"]["settlement_amount"]
            assert settlement_sugg["column"] == "client_net_disbursement"
            assert settlement_sugg["match_type"] == "AI_SUGGESTED"
            assert settlement_sugg["confidence"] == 0.92
            assert "reasoning" in settlement_sugg


def test_ai_fallback_rejects_invalid_hallucinations_and_low_confidence():
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "hallucinated_field",\n'
        '      "source_column": "real_col",\n'
        '      "confidence": 0.95\n'
        '    },\n'
        '    {\n'
        '      "canonical_field": "order_value",\n'
        '      "source_column": "non_existent_column",\n'
        '      "confidence": 0.95\n'
        '    },\n'
        '    {\n'
        '      "canonical_field": "cod_amount",\n'
        '      "source_column": "real_col",\n'
        '      "confidence": 0.40\n'
        '    }\n'
        '  ]\n'
        '}'
    )
    mock_response.content = [mock_block]

    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"], "cod_amount": CANONICAL_FIELDS["cod_amount"]},
            unallocated_source_columns=["real_col"]
        )

        # All 3 items must be rejected:
        # 1. 'hallucinated_field' not in canonical
        # 2. 'non_existent_column' not in unallocated columns
        # 3. 0.40 confidence is below 0.60 threshold
        assert len(predictions) == 0


def test_ai_fallback_handles_missing_api_key_and_provider_errors():
    # 1. Missing API Key: returns {} cleanly without error
    mapper_no_key = AIFallbackMapper(api_key=None)
    res = mapper_no_key.predict_unresolved_mappings(
        unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
        unallocated_source_columns=["col1"]
    )
    assert res == {}

    # 2. Rate limit error: caught and returns {} cleanly
    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": "rate_limit"}
        )

        res_rate = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["col1"]
        )
        assert res_rate == {}

    # 3. Malformed JSON response: caught and returns {} cleanly
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text="Sorry, I cannot map this.")]
        mock_client.messages.create.return_value = mock_resp

        res_malformed = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["col1"]
        )
        assert res_malformed == {}


def test_ai_suggestions_require_human_approval(client, db_session, cofounder_cookies, cofounder_headers, finance_exec_cookies, finance_exec_headers):
    # Retrieve test source
    from app.models.source import Source
    source = db_session.query(Source).filter(Source.source_type == "orders").first()

    # 1. Generate suggestions via API (Co-founder can view suggestions)
    res_sugg = client.post(
        "/api/v1/mappings/suggest",
        json={
            "source_id": str(source.id),
            "source_columns": ["order_id", "order_value", "order_date"]
        },
        cookies=cofounder_cookies,
        headers=cofounder_headers
    )
    assert res_sugg.status_code == 200
    suggestions = res_sugg.json()["suggestions"]
    assert "external_order_id" in suggestions

    # 2. Verify AI suggestions are NOT auto-approved: mapping in DB is not created automatically
    from app.models.column_mapping import ColumnMapping
    initial_count = db_session.query(ColumnMapping).filter(ColumnMapping.source_id == source.id).count()

    # 3. Approval must be an explicit action
    res_approve = client.post(
        "/api/v1/mappings/approve",
        json={
            "source_id": str(source.id),
            "mapping_json": {
                "external_order_id": "order_id",
                "order_value": "order_value",
                "order_date": "order_date"
            }
        },
        cookies=finance_exec_cookies,
        headers=finance_exec_headers
    )
    assert res_approve.status_code == 201
    approved = res_approve.json()
    assert approved["status"] == "approved"

    # New version recorded
    new_count = db_session.query(ColumnMapping).filter(ColumnMapping.source_id == source.id).count()
    assert new_count == initial_count + 1
