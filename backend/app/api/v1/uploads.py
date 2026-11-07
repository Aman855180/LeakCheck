import os
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.database import get_db
from app.api.deps import require_role
from app.models.user import User
from app.models.source import Source
from app.models.upload import Upload
from app.models.column_mapping import ColumnMapping
from app.models.upload_row_error import UploadRowError
from app.schemas.upload import UploadResponse, UploadPreviewResponse, UploadRowErrorResponse
from app.services.file_parser import (
    parse_tabular_file,
    compute_sha256,
    FileValidationError
)
from app.services.column_mapper import suggest_column_mappings
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# In-memory storage for raw preview contents of pending uploads
_PENDING_FILE_CACHE: Dict[str, bytes] = {}

SAMPLE_FILES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "sample_files")
)


@router.get("/sample-file/{filename}")
def get_sample_file(
    filename: str,
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Retrieve sample test CSV file for quick testing in UI."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(SAMPLE_FILES_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sample file {safe_name} not found")
    return FileResponse(file_path, media_type="text/csv", filename=safe_name)


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    source_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec"]))
):
    """
    Upload a financial or logistics file (CSV/XLSX).
    Enforces RBAC: Finance Executive only (Co-founder gets 403 Forbidden).
    Enforces file size (<25MB), signature, row limits (<150k), DPDP Act PII dropping,
    and SHA-256 duplicate upload prevention.
    """
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source_id format")

    source = db.query(Source).filter(Source.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with ID {source_id} not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    file_hash = compute_sha256(content)

    # Check for duplicate file upload
    existing_upload = db.query(Upload).filter(Upload.file_hash == file_hash).first()
    if existing_upload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate file detected. File '{file.filename}' with SHA-256 {file_hash[:12]}... was already uploaded on {existing_upload.created_at} (ID: {existing_upload.id})."
        )

    # Parse file & sanitize PII
    try:
        df, columns, preview_rows, total_rows, dropped_pii = parse_tabular_file(content, file.filename or "unknown.csv")
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    # Check if there is an approved ColumnMapping for this source
    mapping = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == source.id, ColumnMapping.status == "approved")
        .order_by(desc(ColumnMapping.version))
        .first()
    )

    upload = Upload(
        source_id=source.id,
        partner_id=source.partner_id,
        source_type=source.source_type,
        file_name=file.filename or "uploaded_file",
        file_hash=file_hash,
        file_size_bytes=len(content),
        row_count=total_rows,
        mapping_version=mapping.version if mapping else None,
        processing_status="processing" if mapping else "mapping_pending",
        error_count=0,
        uploaded_by=current_user.id
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    if mapping:
        # Ingest immediately with approved mapping
        ingestion_service = IngestionService(db)
        result = ingestion_service.process_upload(upload, df, mapping)
        return {
            "type": "completed",
            "upload": UploadResponse.model_validate(upload).model_dump(),
            "summary": result,
            "dropped_pii_columns": dropped_pii
        }
    else:
        # Store in cache so user can review and approve mapping
        _PENDING_FILE_CACHE[str(upload.id)] = content

        # Extract representative samples for candidate columns from preview rows
        samples_by_col = {
            c: [row[c] for row in preview_rows if c in row and row[c] is not None][:5]
            for c in columns
        }

        # Generate automated suggestions (Exact -> Fuzzy -> AI Fallback)
        mapping_suggestions = suggest_column_mappings(columns, source.source_type, samples_by_col=samples_by_col)

        return {
            "type": "preview",
            "upload_id": upload.id,
            "file_name": upload.file_name,
            "source_type": upload.source_type,
            "total_rows": total_rows,
            "detected_columns": columns,
            "dropped_pii_columns": dropped_pii,
            "preview_rows": preview_rows,
            "suggested_mapping": mapping_suggestions["suggestions"],
            "missing_required": mapping_suggestions["missing_required"],
            "canonical_fields": mapping_suggestions["canonical_fields"],
            "upload": UploadResponse.model_validate(upload).model_dump()
        }


@router.get("/", response_model=List[UploadResponse])
def list_uploads(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """List all file uploads. Both finance_exec and cofounder can view uploads."""
    uploads = (
        db.query(Upload)
        .order_by(desc(Upload.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return uploads


@router.get("/{upload_id}", response_model=UploadResponse)
def get_upload_details(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Retrieve details for a single upload."""
    try:
        u_uuid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload_id format")

    upload = db.query(Upload).filter(Upload.id == u_uuid).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload {upload_id} not found")
    return upload


@router.get("/{upload_id}/errors", response_model=List[UploadRowErrorResponse])
def get_upload_row_errors(
    upload_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """Retrieve quarantined rows and validation error logs for an upload."""
    try:
        u_uuid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload_id format")

    errors = (
        db.query(UploadRowError)
        .filter(UploadRowError.upload_id == u_uuid)
        .order_by(UploadRowError.source_row_number)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return errors


@router.post("/{upload_id}/process", response_model=Dict[str, Any])
def process_pending_upload(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec"]))
):
    """
    Process an upload that was previously in 'mapping_pending' status,
    using the newly approved ColumnMapping for its source.
    """
    try:
        u_uuid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload_id format")

    upload = db.query(Upload).filter(Upload.id == u_uuid).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload {upload_id} not found")

    mapping = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == upload.source_id, ColumnMapping.status == "approved")
        .order_by(desc(ColumnMapping.version))
        .first()
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot process upload: No approved column mapping found for this source. Please approve a column mapping first."
        )

    content = _PENDING_FILE_CACHE.get(str(upload.id))
    if not content:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Raw file content expired from temporary buffer. Please re-upload the file."
        )

    df, _, _, _, _ = parse_tabular_file(content, upload.file_name)
    upload.mapping_version = mapping.version

    ingestion_service = IngestionService(db)
    result = ingestion_service.process_upload(upload, df, mapping)

    # Clean up memory buffer
    _PENDING_FILE_CACHE.pop(str(upload.id), None)

    return {
        "status": "success",
        "upload": UploadResponse.model_validate(upload).model_dump(),
        "summary": result
    }
