import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class ColumnMappingBase(BaseModel):
    mapping_json: Dict[str, str]  # canonical_field -> source_column


class ColumnMappingCreate(ColumnMappingBase):
    source_id: uuid.UUID


class ColumnMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    version: int
    mapping_json: Dict[str, Any]
    status: str
    created_by: uuid.UUID
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    created_at: datetime


class ColumnMappingSuggestionResponse(BaseModel):
    source_id: uuid.UUID
    source_type: str
    source_columns: List[str]
    suggestions: Dict[str, Any]
    missing_required: List[str]
    canonical_fields: List[Dict[str, Any]]
