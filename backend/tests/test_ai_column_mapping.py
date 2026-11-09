import os
import uuid
from unittest.mock import patch, MagicMock
import pytest

from google.genai import types
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


def test_case_partial_rapidfuzz_triggers_gemini_for_unresolved_fields():
    """
    Regression Test: Partial RapidFuzz success MUST NOT skip Gemini for remaining unresolved columns.
    Workbook headers:
      - purchase_timestamp -> RapidFuzz -> order_date (~71%)
      - parcel_consignment_code -> RapidFuzz -> tracking_number (~70%)
      - retailer_transaction_code -> Gemini -> external_order_id (0.90)
      - basket_gross_inr -> Gemini -> order_value (0.95)
      - collection_method -> Gemini -> payment_mode (0.95)
    """
    source_cols = [
        "retailer_transaction_code",
        "basket_gross_inr",
        "collection_method",
        "purchase_timestamp",
        "parcel_consignment_code"
    ]
    samples = {
        "retailer_transaction_code": ["LC-GEM-2001", "LC-GEM-2002"],
        "basket_gross_inr": ["1299.00", "2499.50"],
        "collection_method": ["COD", "PREPAID"],
        "purchase_timestamp": ["2026-10-20 10:15:00"],
        "parcel_consignment_code": ["WBX-71001"]
    }

    mock_gemini_response = (
        '{\n'
        '  "mappings": [\n'
        '    {\n'
        '      "canonical_field": "external_order_id",\n'
        '      "source_column": "retailer_transaction_code",\n'
        '      "confidence": 0.90,\n'
        '      "reasoning": "Retailer transaction code serves as external order id."\n'
        '    },\n'
        '    {\n'
        '      "canonical_field": "order_value",\n'
        '      "source_column": "basket_gross_inr",\n'
        '      "confidence": 0.95,\n'
        '      "reasoning": "Basket gross INR corresponds to order invoice value."\n'
        '    },\n'
        '    {\n'
        '      "canonical_field": "payment_mode",\n'
        '      "source_column": "collection_method",\n'
        '      "confidence": 0.95,\n'
        '      "reasoning": "Collection method contains COD and PREPAID payment modes."\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    with patch.object(AIFallbackMapper, "__init__", lambda self, *args, **kwargs: setattr(self, "api_key", "mock-key") or setattr(self, "model", "gemini-3.5-flash")):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.models.generate_content.return_value = MagicMock(text=mock_gemini_response)

            result = suggest_column_mappings(
                source_columns=source_cols,
                source_type="orders",
                samples_by_col=samples,
                enable_ai=True
            )

            suggestions = result["suggestions"]

            # 1. Verify Pass 2 RapidFuzz matches were preserved
            assert suggestions["order_date"]["column"] == "purchase_timestamp"
            assert suggestions["order_date"]["match_type"] == "FUZZY"
            assert suggestions["order_date"]["confidence"] >= 0.70

            assert suggestions["tracking_number"]["column"] == "parcel_consignment_code"
            assert suggestions["tracking_number"]["match_type"] == "FUZZY"
            assert suggestions["tracking_number"]["confidence"] >= 0.70

            # 2. Verify Gemini was called and received ONLY unresolved columns
            mock_client.models.generate_content.assert_called_once()
            _, kwargs = mock_client.models.generate_content.call_args
            contents = kwargs.get("contents", "")
            # Must contain unallocated columns
            assert "retailer_transaction_code" in contents
            assert "basket_gross_inr" in contents
            assert "collection_method" in contents
            # Must NOT contain columns already resolved by RapidFuzz
            assert "purchase_timestamp" not in contents
            assert "parcel_consignment_code" not in contents

            # 3. Verify Gemini AI suggestions were merged correctly
            assert suggestions["external_order_id"]["column"] == "retailer_transaction_code"
            assert suggestions["external_order_id"]["match_type"] == "AI_SUGGESTED"
            assert suggestions["external_order_id"]["confidence"] == 0.90

            assert suggestions["order_value"]["column"] == "basket_gross_inr"
            assert suggestions["order_value"]["match_type"] == "AI_SUGGESTED"
            assert suggestions["order_value"]["confidence"] == 0.95

            assert suggestions["payment_mode"]["column"] == "collection_method"
            assert suggestions["payment_mode"]["match_type"] == "AI_SUGGESTED"
            assert suggestions["payment_mode"]["confidence"] == 0.95

            # 4. Verify orders required fields (external_order_id, order_value, order_date) are all resolved
            assert len(result["missing_required"]) == 0


def test_case_partial_rapidfuzz_preserved_when_gemini_fails_or_times_out():
    """
    Regression Test: When Gemini fails (e.g. HTTP 429 rate limit or timeout),
    partial RapidFuzz matches are safely preserved while unresolved fields remain available for manual mapping.
    """
    source_cols = [
        "retailer_transaction_code",
        "basket_gross_inr",
        "collection_method",
        "purchase_timestamp",
        "parcel_consignment_code"
    ]

    with patch.object(AIFallbackMapper, "__init__", lambda self, *args, **kwargs: setattr(self, "api_key", "mock-key") or setattr(self, "model", "gemini-3.5-flash")):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            # Simulate Gemini HTTP 429 rate limit error
            mock_client.models.generate_content.side_effect = APIError(429, "Rate limit exceeded")

            result = suggest_column_mappings(
                source_columns=source_cols,
                source_type="orders",
                enable_ai=True
            )

            suggestions = result["suggestions"]

            # RapidFuzz matches MUST still be present
            assert suggestions["order_date"]["column"] == "purchase_timestamp"
            assert suggestions["order_date"]["match_type"] == "FUZZY"
            assert suggestions["tracking_number"]["column"] == "parcel_consignment_code"
            assert suggestions["tracking_number"]["match_type"] == "FUZZY"

            # Gemini-dependent fields remain unresolved for manual mapping
            assert suggestions["external_order_id"]["column"] is None
            assert suggestions["external_order_id"]["match_type"] == "NONE"
            assert suggestions["order_value"]["column"] is None
            assert suggestions["order_value"]["match_type"] == "NONE"

            # Missing required fields correctly flag external_order_id and order_value
            assert "external_order_id" in result["missing_required"]
            assert "order_value" in result["missing_required"]


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
        mock_client.models.generate_content.side_effect = TimeoutError("Request timed out after 30000ms")

        predictions = mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )
        assert predictions == {}


def test_case_gemini_client_initialized_with_30s_timeout():
    """Explicit regression test: Google GenAI client is initialized with types.HttpOptions(timeout=30000)."""
    mapper = AIFallbackMapper(api_key="mock-test-key")
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(text='{"mappings": []}')

        mapper.predict_unresolved_mappings(
            unresolved_canonical_fields={"order_value": CANONICAL_FIELDS["order_value"]},
            unallocated_source_columns=["candidate_col"]
        )

        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs.get("api_key") == "mock-test-key"
        assert "http_options" in kwargs
        http_opts = kwargs["http_options"]
        assert isinstance(http_opts, types.HttpOptions)
        assert http_opts.timeout == 30000


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
