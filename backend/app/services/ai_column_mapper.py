import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError
import anthropic

from app.core.config import settings
from app.services.file_parser import PII_REGEX

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^(?:\+?91[\-\s]?)?[6-9]\d{9}$")
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
CARD_REGEX = re.compile(r"^\d{4}[\-\s]?\d{4}[\-\s]?\d{4}[\-\s]?\d{4}$")


class AIMappingItem(BaseModel):
    canonical_field: str
    source_column: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class AIColumnMappingResponse(BaseModel):
    mappings: List[AIMappingItem]


def sanitize_sample_value(val: Any) -> Optional[str]:
    """
    Sanitizes sample column values, masking personal data (phone, email, payment cards).
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    if PHONE_REGEX.match(s) or EMAIL_REGEX.match(s) or CARD_REGEX.match(s):
        return "[REDACTED_PII]"
    if len(s) > 80:
        return s[:80] + "..."
    return s


def sanitize_columns_and_samples(
    unallocated_columns: List[str],
    samples_by_col: Optional[Dict[str, List[Any]]] = None
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Purges sensitive PII columns from LLM candidate list and masks PII in sample values.
    Returns:
      (sanitized_columns, sanitized_samples)
    """
    sanitized_cols: List[str] = []
    sanitized_samples: Dict[str, List[str]] = {}

    for col in unallocated_columns:
        norm_col = col.strip()
        # Strictly skip any column header identifying PII
        if PII_REGEX.match(norm_col):
            logger.info("Skipping sensitive PII column '%s' from AI fallback prompt", col)
            continue

        sanitized_cols.append(col)
        raw_vals = (samples_by_col or {}).get(col, [])
        clean_vals = []
        for v in raw_vals[:5]:
            clean_v = sanitize_sample_value(v)
            if clean_v:
                clean_vals.append(clean_v)
        sanitized_samples[col] = clean_vals

    return sanitized_cols, sanitized_samples


class AIFallbackMapper:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL

    def predict_unresolved_mappings(
        self,
        unresolved_canonical_fields: Dict[str, Dict[str, Any]],
        unallocated_source_columns: List[str],
        samples_by_col: Optional[Dict[str, List[Any]]] = None,
        source_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Invokes Anthropic Claude to predict mappings ONLY for unresolved canonical fields
        against unallocated, sanitized source columns.
        Returns:
          { canonical_field: { "column": str, "confidence": float, "match_type": "AI_SUGGESTED", "reasoning": str } }
        """
        # If no API key configured, gracefully fallback without error
        if not self.api_key:
            logger.info("No ANTHROPIC_API_KEY configured. Skipping AI column mapping fallback.")
            return {}

        if not unresolved_canonical_fields or not unallocated_source_columns:
            return {}

        # 1. PII detection and sanitization
        safe_columns, safe_samples = sanitize_columns_and_samples(
            unallocated_source_columns,
            samples_by_col
        )
        if not safe_columns:
            return {}

        # 2. Build structured prompt for Claude
        system_prompt = (
            "You are a specialized e-commerce financial reconciliation schema mapper for the Indian D2C domain.\n"
            "Your task is to map ambiguous or non-standard source file columns to unresolved canonical fields.\n"
            "Respond strictly in structured JSON format matching the schema:\n"
            "{\n"
            '  "mappings": [\n'
            '    {\n'
            '      "canonical_field": "field_key",\n'
            '      "source_column": "exact_column_header",\n'
            '      "confidence": 0.85,\n'
            '      "reasoning": "Brief explanation"\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Rules:\n"
            "- Only map to canonical fields explicitly listed in the prompt.\n"
            "- Only choose source columns explicitly listed in the prompt.\n"
            "- Assign confidence between 0.0 and 1.0 based on semantic and sample value evidence.\n"
            "- Do not map any column if uncertain (confidence < 0.60)."
        )

        canonical_desc = [
            f"- '{k}': {meta.get('display_name')} (Description: {meta.get('description')}, Required for: {meta.get('required_for')})"
            for k, meta in unresolved_canonical_fields.items()
        ]

        source_desc = []
        for col in safe_columns:
            vals = safe_samples.get(col, [])
            val_str = f"Sample values: {vals}" if vals else "No sample values available"
            source_desc.append(f"- Column '{col}': {val_str}")

        user_prompt = (
            f"Source Report Feed Type: {source_type or 'general'}\n\n"
            f"Unresolved Target Canonical Fields:\n" + "\n".join(canonical_desc) + "\n\n"
            f"Candidate Source File Columns to map from:\n" + "\n".join(source_desc) + "\n\n"
            "Predict the best mappings for these unresolved fields."
        )

        try:
            client = anthropic.Anthropic(api_key=self.api_key, timeout=10.0)
            message = client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = ""
            for block in message.content:
                if block.type == "text":
                    response_text += block.text

            # Strip markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\n?", "", cleaned_text)
                cleaned_text = re.sub(r"\n?```$", "", cleaned_text).strip()

            parsed = AIColumnMappingResponse.model_validate_json(cleaned_text)

            # 3. Disambiguation, validation, and threshold filtering
            results: Dict[str, Dict[str, Any]] = {}
            allocated_source_cols = set()

            # Sort by confidence descending to allocate highest-confidence first
            sorted_items = sorted(parsed.mappings, key=lambda x: x.confidence, reverse=True)

            for item in sorted_items:
                # Must be in requested unresolved fields
                if item.canonical_field not in unresolved_canonical_fields:
                    logger.warning("AI suggested invalid canonical field '%s'. Rejected.", item.canonical_field)
                    continue

                # Must be in requested unallocated columns
                if item.source_column not in safe_columns:
                    logger.warning("AI suggested invalid source column '%s'. Rejected.", item.source_column)
                    continue

                # Reject low confidence (< 0.60)
                if item.confidence < 0.60:
                    logger.info("AI suggested '%s' -> '%s' with low confidence %.2f. Rejected.",
                                item.source_column, item.canonical_field, item.confidence)
                    continue

                # Reject duplicate source column allocation
                if item.source_column in allocated_source_cols:
                    logger.info("Source column '%s' already allocated. Rejected duplicate.", item.source_column)
                    continue

                # Reject duplicate canonical field allocation
                if item.canonical_field in results:
                    continue

                results[item.canonical_field] = {
                    "column": item.source_column,
                    "confidence": round(float(item.confidence), 2),
                    "match_type": "AI_SUGGESTED",
                    "reasoning": item.reasoning
                }
                allocated_source_cols.add(item.source_column)

            return results

        except anthropic.APIConnectionError as e:
            logger.warning("Anthropic connection failed: %s. Falling back to deterministic matching.", e)
            return {}
        except anthropic.RateLimitError as e:
            logger.warning("Anthropic rate limit exceeded: %s. Falling back to deterministic matching.", e)
            return {}
        except anthropic.APIStatusError as e:
            logger.warning("Anthropic API error HTTP %s: %s. Falling back to deterministic matching.", e.status_code, e.message)
            return {}
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning("Invalid structured JSON output from LLM: %s. Falling back to deterministic matching.", e)
            return {}
        except Exception as e:
            logger.warning("Unexpected error during AI column mapping: %s. Falling back.", e)
            return {}
