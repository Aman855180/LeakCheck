import io
import pytest
import polars as pl
from app.services.file_parser import (
    parse_tabular_file,
    validate_file_metadata,
    sanitize_dataframe_pii,
    compute_sha256,
    FileValidationError,
    MAX_FILE_SIZE_BYTES
)


def test_compute_sha256():
    data = b"order_id,amount\nORD-001,100"
    digest = compute_sha256(data)
    assert len(digest) == 64
    assert digest == compute_sha256(data)


def test_validate_file_metadata_csv():
    valid_csv = b"order_id,amount\nORD-001,500\n"
    ext = validate_file_metadata("orders.csv", len(valid_csv), valid_csv)
    assert ext == "csv"


def test_validate_file_metadata_xlsx():
    # Valid ZIP header
    valid_xlsx = b"PK\x03\x04\x14\x00\x00\x00" + b"\x00" * 50
    ext = validate_file_metadata("settlement.xlsx", len(valid_xlsx), valid_xlsx)
    assert ext == "xlsx"


def test_validate_file_metadata_invalid_extension():
    content = b"some data"
    with pytest.raises(FileValidationError) as exc:
        validate_file_metadata("report.pdf", len(content), content)
    assert exc.value.code == "UNSUPPORTED_FORMAT"


def test_validate_file_metadata_legacy_xls_rejected():
    # Legacy OLE2 BIFF8 Excel file
    content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 50
    with pytest.raises(FileValidationError) as exc:
        validate_file_metadata("legacy_sheet.xls", len(content), content)
    assert exc.value.code == "UNSUPPORTED_FORMAT"
    assert "Legacy Excel (.xls) format is unsupported" in exc.value.message


def test_validate_file_metadata_oversized():
    fake_size = MAX_FILE_SIZE_BYTES + 1024
    with pytest.raises(FileValidationError) as exc:
        validate_file_metadata("orders.csv", fake_size, b"1")
    assert exc.value.code == "FILE_TOO_LARGE"


def test_validate_file_metadata_empty():
    with pytest.raises(FileValidationError) as exc:
        validate_file_metadata("orders.csv", 0, b"")
    assert exc.value.code == "EMPTY_FILE"


def test_validate_file_metadata_corrupted_csv_binary():
    # CSV containing null bytes
    binary_content = b"order_id\x00\x01\x02amount\n"
    with pytest.raises(FileValidationError) as exc:
        validate_file_metadata("orders.csv", len(binary_content), binary_content)
    assert exc.value.code == "INVALID_SIGNATURE"


def test_dpdp_act_pii_sanitization():
    # Construct DataFrame with sensitive PII columns
    df = pl.DataFrame({
        "order_id": ["ORD-101", "ORD-102"],
        "customer_name": ["Rahul Sharma", "Priya Verma"],
        "customer_phone": ["+919876543210", "+919123456789"],
        "buyer_email": ["rahul@example.com", "priya@example.com"],
        "shipping_address_line1": ["123 MG Road", "456 Indiranagar"],
        "order_value": [1499.0, 899.0]
    })

    sanitized_df, dropped = sanitize_dataframe_pii(df)

    assert "customer_name" in dropped
    assert "customer_phone" in dropped
    assert "buyer_email" in dropped
    assert "shipping_address_line1" in dropped
    assert len(sanitized_df.columns) == 2
    assert "order_id" in sanitized_df.columns
    assert "order_value" in sanitized_df.columns


def test_parse_tabular_csv_success():
    csv_bytes = (
        b"order_id,order_value,order_date,customer_name\n"
        b"ORD-204118,1409.00,2026-03-01 10:00:00,Aman Kumar\n"
        b"ORD-M-88120,899.00,2026-03-02 11:30:00,Sneha Patel\n"
    )
    df, cols, preview, total_rows, dropped_pii = parse_tabular_file(csv_bytes, "orders_sample.csv")

    assert total_rows == 2
    assert "customer_name" in dropped_pii
    assert "customer_name" not in cols
    assert "order_id" in cols
    assert "order_value" in cols
    assert len(preview) == 2
    assert preview[0]["order_id"] == "ORD-204118"
