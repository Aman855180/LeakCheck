import re
from typing import Dict, List, Optional, Tuple, Any
from rapidfuzz import fuzz
from app.services.ai_column_mapper import AIFallbackMapper

# 13 Canonical fields defined in the build specification
CANONICAL_FIELDS: Dict[str, Dict[str, Any]] = {
    "external_order_id": {
        "display_name": "Order ID / External Reference",
        "required_for": ["orders", "settlement", "cod", "freight", "receipts"],
        "description": "Unique order identifier across channels or marketplaces",
        "aliases": [
            "order_id", "order id", "orderid", "order no", "order_number", "order ref",
            "external_id", "channel_order_id", "sub_order_id", "po_number", "bill_of_lading",
            "order #", "order_no", "marketplace_order_id", "amazon_order_id", "order_name"
        ]
    },
    "order_value": {
        "display_name": "Order Value / GMV",
        "required_for": ["orders"],
        "description": "Gross invoice amount of the order",
        "aliases": [
            "order_value", "order value", "order amount", "gross_amount", "gmv", "total",
            "total_price", "grand_total", "total_amount", "sale_amount", "item_total",
            "invoice_amount", "invoice_value", "total_order_amount", "subtotal"
        ]
    },
    "payment_mode": {
        "display_name": "Payment Mode (Prepaid/COD)",
        "required_for": [],
        "description": "Payment mode: PREPAID or COD",
        "aliases": [
            "payment_mode", "payment method", "pay_mode", "payment_type", "type",
            "prepaid/cod", "gateway", "channel", "financial_status", "payment_status"
        ]
    },
    "order_date": {
        "display_name": "Order Date",
        "required_for": ["orders"],
        "description": "Timestamp when the customer placed the order",
        "aliases": [
            "order_date", "order date", "created_at", "date", "purchase_date",
            "placed_at", "timestamp", "booking_date", "order_datetime", "ordered_at"
        ]
    },
    "settlement_amount": {
        "display_name": "Settlement Amount",
        "required_for": ["settlement"],
        "description": "Net payout amount received or credited in settlement report",
        "aliases": [
            "settlement_amount", "settled_amount", "net_amount", "net_payable",
            "bank_payout", "payout_amount", "disbursement", "remittance_amount",
            "settlement amount", "credit_amount", "bank_settlement_value", "net_credit"
        ]
    },
    "cod_amount": {
        "display_name": "COD Amount",
        "required_for": ["cod"],
        "description": "COD cash amount collected and remitted by courier partner",
        "aliases": [
            "cod_amount", "cod collected", "cod_remitted", "cash_collected",
            "remittance_val", "cod_value", "cod_dep", "cod_receivable", "cod_payable"
        ]
    },
    "freight_amount": {
        "display_name": "Freight Amount",
        "required_for": ["freight"],
        "description": "Freight and logistics charges billed by the carrier",
        "aliases": [
            "freight_amount", "freight_charges", "freight_charge", "shipping_fee", "courier_charge",
            "logistics_fee", "shipping_charges", "total_freight", "forward_charge",
            "rto_charge", "shipping_amount", "total_shipping_charges"
        ]
    },
    "commission": {
        "display_name": "Marketplace Commission",
        "required_for": [],
        "description": "Platform or PG fee deducted from order gross amount",
        "aliases": [
            "commission", "marketplace_fee", "platform_fee", "commission_amount",
            "commission_rate", "pg_fee", "pg_charges", "service_fee", "referral_fee"
        ]
    },
    "tcs": {
        "display_name": "TCS (Tax Collected at Source)",
        "required_for": [],
        "description": "Tax Collected at Source deducted by marketplace",
        "aliases": ["tcs", "tcs_amount", "tcs_igst", "tcs_cgst", "tcs_sgst", "tcs_tax", "tcs_deduction"]
    },
    "tds": {
        "display_name": "TDS (Tax Deducted at Source)",
        "required_for": [],
        "description": "Tax Deducted at Source under section 194-O",
        "aliases": ["tds", "tds_amount", "tds_u_s_194o", "tds_194o", "tax_deducted", "tds_section_194o"]
    },
    "tracking_number": {
        "display_name": "AWB / Waybill / Tracking #",
        "required_for": [],
        "description": "Airway bill or shipment tracking number",
        "aliases": [
            "tracking_number", "awb", "awb_number", "waybill", "waybill_no",
            "tracking_no", "consignment_no", "docket_number", "airway_bill"
        ]
    },
    "delivery_status": {
        "display_name": "Delivery Status",
        "required_for": [],
        "description": "Current status of the shipment (DELIVERED, RTO, IN_TRANSIT)",
        "aliases": [
            "delivery_status", "status", "order_status", "shipment_status",
            "courier_status", "current_status", "ndr_status", "fulfillment_status"
        ]
    },
    "receipt_date": {
        "display_name": "Warehouse Receipt Date",
        "required_for": ["receipts"],
        "description": "Date goods inwarded or received at warehouse",
        "aliases": [
            "receipt_date", "received_date", "inward_date", "delivery_date",
            "delivered_at", "delivered_on", "grn_date", "inward_time"
        ]
    }
}


def normalize_header(header: str) -> str:
    """Normalize column header for exact alias matching."""
    s = header.lower().strip()
    s = re.sub(r"[\s\-_]+", "_", s)
    return s


def suggest_column_mappings(
    source_columns: List[str],
    source_type: Optional[str] = None,
    samples_by_col: Optional[Dict[str, List[Any]]] = None,
    enable_ai: bool = True
) -> Dict[str, Any]:
    """
    Computes suggestions matching source columns to the 13 canonical fields using:
    1. Exact alias dictionary matching (Confidence = 1.0)
    2. RapidFuzz token/string similarity (Confidence = ratio / 100)
    Returns:
      {
        "suggestions": { canonical_field: { "column": str, "confidence": float, "match_type": str } },
        "missing_required": [canonical_field, ...],
        "all_canonical": [ ... ]
      }
    """
    normalized_source = {col: normalize_header(col) for col in source_columns}
    allocated_columns = set()
    suggestions: Dict[str, Dict[str, Any]] = {}

    # Pass 1: Exact alias matching
    for field_key, meta in CANONICAL_FIELDS.items():
        matched_col = None
        aliases_norm = [normalize_header(a) for a in meta["aliases"]]

        for orig_col, norm_col in normalized_source.items():
            if orig_col in allocated_columns:
                continue
            if norm_col == field_key or norm_col in aliases_norm:
                matched_col = orig_col
                allocated_columns.add(orig_col)
                break

        if matched_col:
            suggestions[field_key] = {
                "column": matched_col,
                "confidence": 1.0,
                "match_type": "EXACT"
            }

    # Pass 2: Fuzzy matching with RapidFuzz for unmapped fields
    for field_key, meta in CANONICAL_FIELDS.items():
        if field_key in suggestions:
            continue

        best_score = 0.0
        best_col = None
        target_tokens = [field_key] + meta["aliases"]

        for orig_col, norm_col in normalized_source.items():
            if orig_col in allocated_columns:
                continue
            # Compare with each alias and the canonical field
            for target in target_tokens:
                score = fuzz.token_sort_ratio(norm_col, normalize_header(target))
                if score > best_score:
                    best_score = score
                    best_col = orig_col

        if best_col and best_score >= 70.0:
            confidence = round(best_score / 100.0, 2)
            suggestions[field_key] = {
                "column": best_col,
                "confidence": confidence,
                "match_type": "FUZZY"
            }
            allocated_columns.add(best_col)
        else:
            suggestions[field_key] = {
                "column": None,
                "confidence": 0.0,
                "match_type": "NONE"
            }

    # Pass 3: AI Fallback (Anthropic LLM) ONLY for fields that remain unresolved
    if enable_ai:
        unresolved_fields = {
            k: CANONICAL_FIELDS[k]
            for k, s in suggestions.items()
            if not s.get("column")
        }
        unallocated_cols = [col for col in source_columns if col not in allocated_columns]

        if unresolved_fields and unallocated_cols:
            ai_mapper = AIFallbackMapper()
            ai_predictions = ai_mapper.predict_unresolved_mappings(
                unresolved_canonical_fields=unresolved_fields,
                unallocated_source_columns=unallocated_cols,
                samples_by_col=samples_by_col,
                source_type=source_type
            )
            for f_key, pred in ai_predictions.items():
                suggestions[f_key] = pred
                allocated_columns.add(pred["column"])

    # Check required fields for this source type
    missing_required = []
    if source_type:
        for field_key, meta in CANONICAL_FIELDS.items():
            if source_type in meta.get("required_for", []):
                if not suggestions.get(field_key) or not suggestions[field_key].get("column"):
                    missing_required.append(field_key)

    return {
        "suggestions": suggestions,
        "missing_required": missing_required,
        "source_columns": source_columns,
        "canonical_fields": [
            {
                "key": k,
                "display_name": v["display_name"],
                "required_for": v["required_for"],
                "description": v["description"]
            }
            for k, v in CANONICAL_FIELDS.items()
        ]
    }


def validate_mapping_completeness(mapping: Dict[str, str], source_type: str) -> Tuple[bool, List[str]]:
    """
    Validates whether the provided mapping meets all required fields for source_type.
    """
    missing = []
    for field_key, meta in CANONICAL_FIELDS.items():
        if source_type in meta.get("required_for", []):
            mapped_col = mapping.get(field_key)
            if not mapped_col or not str(mapped_col).strip():
                missing.append(field_key)

    is_valid = len(missing) == 0
    return is_valid, missing
