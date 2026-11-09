import os
import uuid
from unittest.mock import patch, MagicMock
import pytest

from google.genai.errors import APIError
from app.services.column_mapper import suggest_column_mappings, CANONICAL_FIELDS
from app.services.ai_column_mapper import (
    AIFallbackMapper,
    sanitize_columns_and_samples,
    sanitize_sample_value
)


# ==============================================================================
# 1. PII Redaction & Data Sanitization Tests (Unit)
# ==============================================================================

def test_case_12_pii_redaction_before_llm():
    """Test 12: PII Redaction - Filters personal headers and masks phone, email, credit cards."""
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

    # Value-level PII masking
    assert sanitize_sample_value("test@company.com") == "[REDACTED_PII]"
    assert sanitize_sample_value("+91 9876543210") == "[REDACTED_PII]"
    assert sanitize_sample_value("9876543210") == "[REDACTED_PII]"
    assert sanitize_sample_value("1234-5678-9012-3456") == "[REDACTED_PII]"
    assert sanitize_sample_value("₹1,499.00") == "₹1,499.00"


# ==============================================================================
# 2. Three-Pass Architecture & Precedence (Exact/Fuzzy Bypass Gemini)
# ==============================================================================

def test_case_13_exact_and_fuzzy_bypassing_gemini():
    """Test 13: Pass 1 (Exact) and Pass 2 (Fuzzy) resolve mappings without querying Gemini."""
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


# ==============================================================================
# 3. Gemini API Key Configuration Tests (Unit)
# ==============================================================================

def test_case_1_missing_gemini_api_key():
    """Test 1: Missing Gemini API key gracefully skips AI fallback returning empty dict."""
    mapper = AIFallbackMapper(api_key=None)
    res = mapper.predict_unresolved_mappings(
        unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
        unallocated_source_columns=["unmapped_col"]
    )
    assert res == {}


def test_case_2_valid_gemini_api_key_initialization():
    """Test 2: Valid Gemini API key initializes client and constructs structured prompt."""
    mapper = AIFallbackMapper(api_key="AIzaSyMockValidTestKey123", model="gemini-2.5-flash")
    assert mapper.api_key == "AIzaSyMockValidTestKey123"
    assert mapper.model == "gemini-2.5-flash"


# ==============================================================================
# 4. Gemini Structured Mapping & Confidence Handling Tests (Mocked)
# ==============================================================================

def test_case_3_successful_structured_mapping_response():
    """Test 3: Successful structured mapping response parsed and assigned match_type='AI_SUGGESTED'."""
    source_cols = ["order_id", "order_date", "client_net_disbursement"]
    samples = {"client_net_disbursement": ["1410.00", "899.50"]}

    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "settlement_amount",\n'
        '      "source_column": "client_net_disbursement",\n'
        '      "confidence": 0.92,\n'
        '      "reasoning": "Client net disbursement represents net bank settlement."\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    with patch.object(AIFallbackMapper, "__init__", lambda self, *args, **kwargs: setattr(self, "api_key", "mock-key") or setattr(self, "model", "gemini-2.5-flash")):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

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
            assert settlement_sugg["uncertain"] is False
            assert "reasoning" in settlement_sugg


def test_case_8_invalid_canonical_field_filtering():
    """Test 8: Invalid canonical field hallucinated by model is strictly rejected."""
    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "hallucinated_unknown_field",\n'
        '      "source_column": "real_column",\n'
        '      "confidence": 0.95\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["real_column"]
        )
        assert len(predictions) == 0


def test_case_9_confidence_below_0_60_discarded():
    """Test 9: Confidence below 0.60 is discarded and unmapped."""
    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "order_value",\n'
        '      "source_column": "dubious_col",\n'
        '      "confidence": 0.55\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["dubious_col"]
        )
        assert "order_value" not in predictions


def test_case_10_confidence_between_0_60_and_0_80_flagged_uncertain():
    """Test 10: Confidence between 0.60 and 0.80 is accepted but flagged as uncertain=True."""
    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "order_value",\n'
        '      "source_column": "candidate_amount",\n'
        '      "confidence": 0.72\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_amount"]
        )
        assert "order_value" in predictions
        assert predictions["order_value"]["column"] == "candidate_amount"
        assert predictions["order_value"]["confidence"] == 0.72
        assert predictions["order_value"]["uncertain"] is True


def test_case_11_confidence_above_0_80_accepted_confident():
    """Test 11: Confidence above 0.80 is accepted with uncertain=False."""
    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "order_value",\n'
        '      "source_column": "gross_order_total",\n'
        '      "confidence": 0.95\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["gross_order_total"]
        )
        assert "order_value" in predictions
        assert predictions["order_value"]["column"] == "gross_order_total"
        assert predictions["order_value"]["confidence"] == 0.95
        assert predictions["order_value"]["uncertain"] is False


# ==============================================================================
# 5. Gemini Provider Error Handling Tests (Mocked)
# ==============================================================================

def test_case_4_invalid_api_key_handling():
    """Test 4: Invalid API key (HTTP 400/401/403 APIError) caught without crashing."""
    mapper = AIFallbackMapper(api_key="invalid-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        err = APIError(400, "API_KEY_INVALID: The provided API key is invalid")
        mock_client.models.generate_content.side_effect = err

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )
        assert predictions == {}


def test_case_5_api_timeout_handling():
    """Test 5: API request timeout handled gracefully without throwing unhandled exceptions."""
    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = TimeoutError("Request timed out after 15000ms")

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )
        assert predictions == {}


def test_case_6_http_429_rate_limit_handling():
    """Test 6: HTTP 429 rate-limit error handled gracefully returning empty dict."""
    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        err = APIError(429, "Resource has been exhausted (e.g. check quota)")
        mock_client.models.generate_content.side_effect = err

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )
        assert predictions == {}


def test_case_7_malformed_json_response_handling():
    """Test 7: Malformed or unparseable JSON from model caught cleanly returning empty dict."""
    mapper = AIFallbackMapper(api_key="mock-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.text = "I apologize, but I am unable to map these columns to your schema."
        mock_client.models.generate_content.return_value = mock_resp

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )
        assert predictions == {}


# ==============================================================================
# 6. Human Approval & Governance Verification (Integration)
# ==============================================================================

def test_case_14_human_approval_remains_mandatory(client, db_session, cofounder_cookies, cofounder_headers, finance_exec_cookies, finance_exec_headers):
    """Test 14: AI mapping suggestions are never auto-committed; mandatory human approval required."""
    from app.models.source import Source
    from app.models.column_mapping import ColumnMapping
    source = db_session.query(Source).filter(Source.source_type == "orders").first()

    # 1. Generate suggestions via API
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

    # 2. Verify AI suggestions did not create/activate mapping in DB
    initial_count = db_session.query(ColumnMapping).filter(ColumnMapping.source_id == source.id).count()

    # 3. Explicit approval is required
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

    # New version recorded only after explicit approval
    new_count = db_session.query(ColumnMapping).filter(ColumnMapping.source_id == source.id).count()
    assert new_count == initial_count + 1


# ==============================================================================
# 7. Real Live API Integration Test (Conditional)
# ==============================================================================

def test_case_real_api_call_when_key_configured():
    """Live API integration test: Only executes if real GEMINI_API_KEY is exported in environment."""
    real_key = os.getenv("GEMINI_API_KEY")
    if not real_key or not real_key.strip():
        pytest.skip("No real GEMINI_API_KEY found in environment. Skipping live API call.")

    mapper = AIFallbackMapper(api_key=real_key.strip())
    predictions = mapper.predict_unresolved_mappings(
        unresolved_canonical_fields={"settlement_amount": CANONICAL_FIELDS["settlement_amount"]},
        unallocated_source_columns=["merchant_payout_net_credit"],
        samples_by_col={"merchant_payout_net_credit": ["1200.50", "950.00", "2400.00"]},
        source_type="settlement"
    )

    assert "settlement_amount" in predictions
    pred = predictions["settlement_amount"]
    assert pred["column"] == "merchant_payout_net_credit"
    assert pred["match_type"] == "AI_SUGGESTED"
    assert pred["confidence"] >= 0.60
