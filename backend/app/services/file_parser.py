import io
import hashlib
import re
from typing import Tuple, List, Dict, Any, Optional
import polars as pl

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_ROW_COUNT = 150_000

# DPDP Act: Sensitive PII columns to drop immediately at parse time
PII_COLUMN_PATTERNS = [
    r"^customer[_\s]?name$",
    r"^buyer[_\s]?name$",
    r"^recipient[_\s]?name$",
    r"^customer[_\s]?phone$",
    r"^buyer[_\s]?phone$",
    r"^mobile[_\s]?(no|number)?$",
    r"^contact[_\s]?(no|number)?$",
    r"^customer[_\s]?email$",
    r"^buyer[_\s]?email$",
    r"^personal[_\s]?email$",
    r"^shipping[_\s]?address.*$",
    r"^delivery[_\s]?address.*$",
    r"^billing[_\s]?address.*$",
    r"^address[_\s]?(line[_\s]?\d|1|2)?$",
    r"^street.*$",
    r"^landmark.*$",
]

PII_REGEX = re.compile("|".join(PII_COLUMN_PATTERNS), re.IGNORECASE)


class FileValidationError(Exception):
    def __init__(self, message: str, code: str = "INVALID_FILE"):
        super().__init__(message)
        self.message = message
        self.code = code


def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 digest of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()


def validate_file_metadata(file_name: str, file_size: int, content: bytes) -> str:
    """
    Validates file size, extension, and magic byte signature.
    Returns detected extension ('csv' or 'xlsx').
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"File size exceeds 25 MB limit ({file_size} bytes)",
            code="FILE_TOO_LARGE"
        )
    if file_size == 0 or len(content) == 0:
        raise FileValidationError("File is empty", code="EMPTY_FILE")

    lower_name = file_name.lower()
    if lower_name.endswith(".csv"):
        # CSV signature validation: basic text / no non-printable null bytes
        if b"\x00" in content[:1024]:
            raise FileValidationError("Invalid CSV format (binary characters detected)", code="INVALID_SIGNATURE")
        return "csv"
    elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        # XLSX ZIP magic bytes: 0x50 0x4B 0x03 0x04 ("PK\x03\x04")
        if not content.startswith(b"PK\x03\x04"):
            raise FileValidationError("Invalid XLSX format (corrupted file signature)", code="INVALID_SIGNATURE")
        return "xlsx"
    else:
        raise FileValidationError(
            f"Unsupported file format '{file_name}'. Only CSV and XLSX are supported.",
            code="UNSUPPORTED_FORMAT"
        )


def sanitize_dataframe_pii(df: pl.DataFrame) -> Tuple[pl.DataFrame, List[str]]:
    """
    Identifies and purges any DPDP Act sensitive PII columns from the DataFrame.
    Returns sanitized DataFrame and list of dropped PII columns.
    """
    dropped_columns: List[str] = []
    keep_columns: List[str] = []

    for col in df.columns:
        norm_col = col.strip()
        if PII_REGEX.match(norm_col):
            dropped_columns.append(col)
        else:
            keep_columns.append(col)

    if dropped_columns:
        df = df.select(keep_columns)

    return df, dropped_columns


def parse_tabular_file(
    content: bytes,
    file_name: str
) -> Tuple[pl.DataFrame, List[str], List[Dict[str, Any]], int, List[str]]:
    """
    Parses a CSV or XLSX file using Polars.
    Returns:
      (sanitized_df, clean_columns, preview_rows_20, total_row_count, dropped_pii_columns)
    """
    file_type = validate_file_metadata(file_name, len(content), content)

    try:
        if file_type == "csv":
            # Attempt standard UTF-8 parsing, with fallback to Latin-1
            try:
                df = pl.read_csv(io.BytesIO(content), infer_schema_length=1000, ignore_errors=True)
            except Exception:
                df = pl.read_csv(io.BytesIO(content), encoding="latin1", infer_schema_length=1000, ignore_errors=True)
        else:
            # Excel parsing
            try:
                df = pl.read_excel(io.BytesIO(content), engine="calamine")
            except Exception:
                df = pl.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as e:
        raise FileValidationError(f"Failed to parse tabular file: {str(e)}", code="PARSE_FAILED")

    total_rows = len(df)
    if total_rows == 0:
        raise FileValidationError("File contains no data rows", code="EMPTY_DATA")
    if total_rows > MAX_ROW_COUNT:
        raise FileValidationError(
            f"File exceeds maximum allowed row count of {MAX_ROW_COUNT:,} rows (found {total_rows:,})",
            code="ROW_LIMIT_EXCEEDED"
        )

    # Sanitize PII
    sanitized_df, dropped_pii = sanitize_dataframe_pii(df)
    columns = list(sanitized_df.columns)

    # 20-row preview with string conversions for JSON-safe serialization
    preview_df = sanitized_df.head(20)
    # Convert dates/floats/None cleanly to python primitives
    preview_rows = preview_df.to_dicts()

    return sanitized_df, columns, preview_rows, total_rows, dropped_pii
