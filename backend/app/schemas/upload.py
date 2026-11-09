import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    partner_id: str
    source_type: str
    file_name: str
    file_hash: str
    file_size_bytes: int
    row_count: int
    mapping_version: Optional[int] = None
    processing_status: str
    error_count: int
    retry_of_upload_id: Optional[uuid.UUID] = None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UploadPreviewResponse(BaseModel):
    upload_id: uuid.UUID
    file_name: str
    source_type: str
    total_rows: int
    detected_columns: List[str]
    dropped_pii_columns: List[str]
    preview_rows: List[Dict[str, Any]]
    suggested_mapping: Dict[str, Any]


class UploadRowErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    upload_id: uuid.UUID
    source_row_number: int
    error_code: str
    error_message: str
    raw_record: Dict[str, Any]
    created_at: datetime
