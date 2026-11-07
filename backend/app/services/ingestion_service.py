import uuid
import re
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Tuple
import polars as pl
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.upload import Upload
from app.models.column_mapping import ColumnMapping
from app.models.job import Job
from app.models.upload_row_error import UploadRowError
from app.models.order_event import OrderEvent
from app.models.warehouse_receipt import WarehouseReceipt
from app.models.tracking_event import TrackingEvent
from app.models.tracking_rule import CourierTrackingRule, CourierRuleActivation


def clean_decimal(val: Any) -> Optional[Decimal]:
    """Clean and parse numeric value to Decimal."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "-", "na"):
        return None
    # Strip currency symbols, commas, spaces
    s = re.sub(r"[₹$,\s]", "", s)
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Cannot parse '{val}' as numeric amount")


def parse_timestamp(val: Any) -> Optional[datetime]:
    """Parse various timestamp formats into UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "-", "na"):
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        raise ValueError(f"Cannot parse '{val}' as date/timestamp")


def compute_event_idempotency_key(
    source_id: str,
    external_order_id: str,
    event_type: str,
    amount: Optional[Decimal],
    source_row_num: int
) -> str:
    """
    Computes unambiguous SHA-256 idempotency key:
    b"{source_id}:{order_id}:{event_type}:{amount}:{source_row}"
    """
    amt_str = f"{amount:.2f}" if amount is not None else "NULL"
    payload = f"{source_id}|{external_order_id}|{event_type}|{amt_str}|{source_row_num}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def process_upload(
        self,
        upload: Upload,
        df: pl.DataFrame,
        mapping: ColumnMapping,
        job: Optional[Job] = None
    ) -> Dict[str, Any]:
        """
        Executes ingestion of parsed DataFrame rows according to approved column mapping.
        Handles row validation, error quarantine, and event insertion.
        """
        upload.processing_status = "processing"
        if job:
            job.status = "running"
            job.total_rows = len(df)
            self.db.add(job)
        self.db.add(upload)
        self.db.commit()

        mapping_dict = mapping.mapping_json  # canonical_field -> source_column
        source_type = upload.source_type
        processed_count = 0
        failed_count = 0

        # Pre-fetch active tracking rules if source_type == 'freight'
        active_rules = {}
        if source_type in ("freight", "receipts"):
            stmt = (
                select(CourierTrackingRule)
                .join(CourierRuleActivation, CourierTrackingRule.id == CourierRuleActivation.active_rule_id)
                .where(CourierTrackingRule.courier_partner_id == upload.partner_id)
            )
            rules = self.db.execute(stmt).scalars().all()
            for r in rules:
                key = (r.raw_status_code.lower().strip(), r.raw_facility_code.lower().strip() if r.raw_facility_code else "")
                active_rules[key] = r

        rows = df.to_dicts()

        for idx, row in enumerate(rows, start=1):
            source_row_num = idx
            try:
                # 1. Extract Order ID
                order_id_col = mapping_dict.get("external_order_id")
                order_id = str(row.get(order_id_col, "")).strip() if order_id_col and row.get(order_id_col) is not None else ""

                if not order_id or order_id.lower() in ("nan", "none", "null", ""):
                    err = UploadRowError(
                        upload_id=upload.id,
                        source_row_number=source_row_num,
                        error_code="MISSING_ORDER_ID",
                        error_message="Missing external order identifier",
                        raw_record=row
                    )
                    self.db.add(err)
                    failed_count += 1
                    continue

                # 2. Extract and Validate Source Type Specific Attributes
                if source_type == "orders":
                    val_col = mapping_dict.get("order_value")
                    date_col = mapping_dict.get("order_date")
                    pm_col = mapping_dict.get("payment_mode")

                    try:
                        order_val = clean_decimal(row.get(val_col)) if val_col else Decimal("0.00")
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_NUMERIC",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    try:
                        event_date = parse_timestamp(row.get(date_col)) if date_col else datetime.now(timezone.utc)
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_DATE",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    pay_mode = str(row.get(pm_col, "PREPAID")).upper() if pm_col and row.get(pm_col) else "PREPAID"
                    if "COD" in pay_mode or "CASH" in pay_mode:
                        pay_mode = "COD"
                    else:
                        pay_mode = "PREPAID"

                    idempotency_key = compute_event_idempotency_key(
                        str(upload.source_id), order_id, "order_placed", order_val, source_row_num
                    )

                    event_id = uuid.uuid4()
                    event = OrderEvent(
                        id=event_id,
                        lineage_root_id=event_id,
                        external_order_id=order_id,
                        source_partner_id=upload.partner_id,
                        event_type="order_placed",
                        amount=order_val,
                        event_date=event_date or datetime.now(timezone.utc),
                        upload_id=upload.id,
                        source_row_number=source_row_num,
                        idempotency_key=idempotency_key,
                        raw_data=row
                    )
                    self.db.add(event)
                    processed_count += 1

                elif source_type == "settlement":
                    settle_col = mapping_dict.get("settlement_amount")
                    try:
                        settle_amt = clean_decimal(row.get(settle_col)) if settle_col else Decimal("0.00")
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_NUMERIC",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    idempotency_key = compute_event_idempotency_key(
                        str(upload.source_id), order_id, "settlement_credit", settle_amt, source_row_num
                    )

                    event_id = uuid.uuid4()
                    event = OrderEvent(
                        id=event_id,
                        lineage_root_id=event_id,
                        external_order_id=order_id,
                        source_partner_id=upload.partner_id,
                        event_type="settlement_credit",
                        settlement_credit=settle_amt,
                        amount=settle_amt,
                        event_date=datetime.now(timezone.utc),
                        upload_id=upload.id,
                        source_row_number=source_row_num,
                        idempotency_key=idempotency_key,
                        raw_data=row
                    )
                    self.db.add(event)
                    processed_count += 1

                elif source_type == "cod":
                    cod_col = mapping_dict.get("cod_amount")
                    try:
                        cod_amt = clean_decimal(row.get(cod_col)) if cod_col else Decimal("0.00")
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_NUMERIC",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    idempotency_key = compute_event_idempotency_key(
                        str(upload.source_id), order_id, "cod_remittance", cod_amt, source_row_num
                    )

                    event_id = uuid.uuid4()
                    event = OrderEvent(
                        id=event_id,
                        lineage_root_id=event_id,
                        external_order_id=order_id,
                        source_partner_id=upload.partner_id,
                        event_type="cod_remittance",
                        amount=cod_amt,
                        event_date=datetime.now(timezone.utc),
                        upload_id=upload.id,
                        source_row_number=source_row_num,
                        idempotency_key=idempotency_key,
                        raw_data=row
                    )
                    self.db.add(event)
                    processed_count += 1

                elif source_type == "freight":
                    freight_col = mapping_dict.get("freight_amount")
                    awb_col = mapping_dict.get("tracking_number")
                    status_col = mapping_dict.get("delivery_status")

                    try:
                        freight_amt = clean_decimal(row.get(freight_col)) if freight_col else Decimal("0.00")
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_NUMERIC",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    awb = str(row.get(awb_col, "")).strip() if awb_col and row.get(awb_col) else f"AWB-{order_id}"
                    raw_status = str(row.get(status_col, "DELIVERED")).strip() if status_col and row.get(status_col) else "DELIVERED"

                    idempotency_key = compute_event_idempotency_key(
                        str(upload.source_id), order_id, "freight_charge", freight_amt, source_row_num
                    )

                    event_id = uuid.uuid4()
                    event = OrderEvent(
                        id=event_id,
                        lineage_root_id=event_id,
                        external_order_id=order_id,
                        source_partner_id=upload.partner_id,
                        event_type="freight_charge",
                        freight_amount=freight_amt,
                        amount=freight_amt,
                        tracking_number=awb,
                        event_date=datetime.now(timezone.utc),
                        upload_id=upload.id,
                        source_row_number=source_row_num,
                        idempotency_key=idempotency_key,
                        raw_data=row
                    )
                    self.db.add(event)

                    rule_key = (raw_status.lower(), "")
                    rule = active_rules.get(rule_key)
                    outcome = rule.normalized_status if rule else "VALID_DELIVERY"

                    trk_event = TrackingEvent(
                        order_id=order_id,
                        tracking_number=awb,
                        courier_code=upload.partner_id,
                        event_timestamp=datetime.now(timezone.utc),
                        raw_status_code=raw_status,
                        raw_facility_code=None,
                        raw_telemetry=row,
                        mapping_rule_id=rule.id if rule else None,
                        mapping_version=rule.version if rule else None,
                        verification_outcome=outcome,
                        upload_id=upload.id,
                        source_row_number=source_row_num
                    )
                    self.db.add(trk_event)
                    processed_count += 1

                elif source_type == "receipts":
                    date_col = mapping_dict.get("receipt_date")
                    awb_col = mapping_dict.get("tracking_number")

                    try:
                        rcpt_date = parse_timestamp(row.get(date_col)) if date_col else datetime.now(timezone.utc)
                    except ValueError as e:
                        self.db.add(UploadRowError(
                            upload_id=upload.id,
                            source_row_number=source_row_num,
                            error_code="INVALID_DATE",
                            error_message=str(e),
                            raw_record=row
                        ))
                        failed_count += 1
                        continue

                    awb = str(row.get(awb_col, "")).strip() if awb_col and row.get(awb_col) else None

                    wh_rcpt = WarehouseReceipt(
                        order_id=order_id,
                        tracking_number=awb,
                        warehouse_id="WH-BLR-01",
                        received_at=rcpt_date or datetime.now(timezone.utc),
                        receipt_status="delivered",
                        upload_id=upload.id,
                        source_row_number=source_row_num
                    )
                    self.db.add(wh_rcpt)
                    processed_count += 1

                if idx % 100 == 0:
                    self.db.flush()

            except Exception as e:
                self.db.add(UploadRowError(
                    upload_id=upload.id,
                    source_row_number=source_row_num,
                    error_code="ROW_PROCESSING_FAILED",
                    error_message=str(e),
                    raw_record=row
                ))
                failed_count += 1

        self.db.commit()

        upload.row_count = len(rows)
        upload.error_count = failed_count
        upload.processing_status = "completed" if processed_count > 0 else "failed"
        if job:
            job.processed_rows = processed_count
            job.failed_rows = failed_count
            job.status = "completed" if processed_count > 0 else "failed"
            self.db.add(job)

        self.db.add(upload)
        self.db.commit()

        return {
            "upload_id": str(upload.id),
            "status": upload.processing_status,
            "total_rows": len(rows),
            "processed_rows": processed_count,
            "failed_rows": failed_count
        }
