import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.source import Source
from app.models.column_mapping import ColumnMapping
from app.schemas.column_mapping import (
    ColumnMappingCreate,
    ColumnMappingResponse,
    ColumnMappingSuggestionResponse
)
from app.services.column_mapper import (
    suggest_column_mappings,
    validate_mapping_completeness,
    CANONICAL_FIELDS
)

router = APIRouter(prefix="/mappings", tags=["Column Mappings"])


class SuggestionRequest(BaseModel):
    source_id: uuid.UUID
    source_columns: List[str]
    samples_by_col: Optional[Dict[str, List[Any]]] = None
    enable_ai: bool = True


@router.post("/suggest", response_model=ColumnMappingSuggestionResponse)
def get_column_mapping_suggestions(
    payload: SuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Generate automatic exact, fuzzy, and AI fallback column mapping suggestions.
    Accessible by both Finance Executives and Co-founders.
    """
    source = db.query(Source).filter(Source.id == payload.source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source {payload.source_id} not found")

    result = suggest_column_mappings(
        source_columns=payload.source_columns,
        source_type=source.source_type,
        samples_by_col=payload.samples_by_col,
        enable_ai=payload.enable_ai
    )
    return {
        "source_id": source.id,
        "source_type": source.source_type,
        "source_columns": payload.source_columns,
        "suggestions": result["suggestions"],
        "missing_required": result["missing_required"],
        "canonical_fields": result["canonical_fields"]
    }


@router.post("/approve", response_model=ColumnMappingResponse, status_code=status.HTTP_201_CREATED)
def approve_column_mapping(
    payload: ColumnMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Approve and activate a column mapping version.
    Per specification: Both Finance Executives and Co-founders have permission to approve column mappings.
    Enforces that all mandatory canonical fields for the source type are mapped.
    """
    source = db.query(Source).filter(Source.id == payload.source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source {payload.source_id} not found")

    # Validate completeness
    is_valid, missing = validate_mapping_completeness(payload.mapping_json, source.source_type)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete column mapping: Missing mandatory fields for {source.source_type}: {missing}"
        )

    # Determine next version
    max_ver = (
        db.query(func.max(ColumnMapping.version))
        .filter(ColumnMapping.source_id == source.id)
        .scalar()
    ) or 0
    next_ver = max_ver + 1

    # Mark prior approved mappings as superseded
    prior_approved = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == source.id, ColumnMapping.status == "approved")
        .all()
    )
    for p in prior_approved:
        p.status = "superseded"
        db.add(p)

    now = datetime.now(timezone.utc)
    new_mapping = ColumnMapping(
        source_id=source.id,
        version=next_ver,
        mapping_json=payload.mapping_json,
        status="approved",
        created_by=current_user.id,
        approved_by=current_user.id,
        approved_at=now
    )
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)
    return new_mapping


@router.get("/source/{source_id}", response_model=ColumnMappingResponse)
def get_active_mapping_for_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Get the currently active approved column mapping for a source."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source_id format")

    mapping = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == s_uuid, ColumnMapping.status == "approved")
        .order_by(desc(ColumnMapping.version))
        .first()
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approved column mapping found for source {source_id}"
        )
    return mapping


@router.get("/source/{source_id}/versions", response_model=List[ColumnMappingResponse])
def get_mapping_versions_for_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Get all historical versions of column mappings for a source."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source_id format")

    versions = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == s_uuid)
        .order_by(desc(ColumnMapping.version))
        .all()
    )
    return versions


@router.post("/{mapping_id}/rollback", response_model=ColumnMappingResponse)
def rollback_column_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Roll back to a previous column mapping configuration.
    Per specification: Both Finance Executives and Co-founders have permission to roll back mappings.
    Creates a new active approved version matching the target historical configuration.
    """
    try:
        m_uuid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mapping_id format")

    target_mapping = db.query(ColumnMapping).filter(ColumnMapping.id == m_uuid).first()
    if not target_mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target column mapping {mapping_id} not found")

    source_id = target_mapping.source_id

    # Determine next version
    max_ver = (
        db.query(func.max(ColumnMapping.version))
        .filter(ColumnMapping.source_id == source_id)
        .scalar()
    ) or 0
    next_ver = max_ver + 1

    # Mark current active mapping as superseded
    prior_approved = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == source_id, ColumnMapping.status == "approved")
        .all()
    )
    now = datetime.now(timezone.utc)
    for p in prior_approved:
        p.status = "superseded"
        p.rolled_back_at = now
        db.add(p)

    restored_mapping = ColumnMapping(
        source_id=source_id,
        version=next_ver,
        mapping_json=target_mapping.mapping_json,
        status="approved",
        created_by=current_user.id,
        approved_by=current_user.id,
        approved_at=now
    )
    db.add(restored_mapping)
    db.commit()
    db.refresh(restored_mapping)
    return restored_mapping
