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
from app.models.upload_mapping_suggestion import UploadMappingSuggestion
from app.models.column_mapping import ColumnMapping
from app.models.upload_row_error import UploadRowError
from app.schemas.upload import UploadResponse, UploadPreviewResponse, UploadRowErrorResponse
from app.services.file_parser import (
    parse_tabular_file,
    compute_sha256,
    FileValidationError
)
from app.services.column_mapper import suggest_column_mappings, CANONICAL_FIELDS
from app.services.ingestion_service import IngestionService
from app.services.pending_file_storage import (
    save_pending_file_to_disk,
    read_pending_file_from_disk,
    delete_pending_file_from_disk
)

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
    # Only block if an existing upload with this SHA-256 hash is already COMPLETED or currently PROCESSING
    existing_completed = (
        db.query(Upload)
        .filter(
            Upload.file_hash == file_hash,
            Upload.processing_status.in_(["completed", "processing"])
        )
        .first()
    )
    if existing_completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate file detected. File '{file.filename}' with SHA-256 {file_hash[:12]}... was already uploaded on {existing_completed.created_at} (ID: {existing_completed.id}) with status '{existing_completed.processing_status}'."
        )

    # If there was a prior failed attempt for this file, link the new attempt to it for complete audit lineage
    prior_attempt = (
        db.query(Upload)
        .filter(Upload.file_hash == file_hash)
        .order_by(desc(Upload.created_at))
        .first()
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

    # Verify mapping compatibility against actual columns in the uploaded file
    is_compatible = True
    incompatibility_reasons: List[str] = []
    if mapping and mapping.mapping_json:
        col_set = {c.lower().strip() for c in columns}
        for field_key, meta in CANONICAL_FIELDS.items():
            if source.source_type in meta.get("required_for", []):
                mapped_col = mapping.mapping_json.get(field_key)
                if not mapped_col or str(mapped_col).strip() == "":
                    is_compatible = False
                    incompatibility_reasons.append(
                        f"Required field '{meta['display_name']}' is not mapped in version v{mapping.version}."
                    )
                elif str(mapped_col).lower().strip() not in col_set:
                    is_compatible = False
                    incompatibility_reasons.append(
                        f"Required field '{meta['display_name']}' is mapped to column '{mapped_col}', which does not exist in the uploaded file headers."
                    )
    else:
        is_compatible = False
        incompatibility_reasons.append("No approved column mapping found for this source.")

    upload = Upload(
        source_id=source.id,
        partner_id=source.partner_id,
        source_type=source.source_type,
        file_name=file.filename or "uploaded_file",
        file_hash=file_hash,
        file_size_bytes=len(content),
        row_count=total_rows,
        mapping_version=mapping.version if (mapping and is_compatible) else None,
        processing_status="processing" if (mapping and is_compatible) else "mapping_pending",
        error_count=0,
        retry_of_upload_id=prior_attempt.id if prior_attempt else None,
        uploaded_by=current_user.id
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    if mapping and is_compatible:
        # Persist upload-specific mapping review information for complete auditability
        db_suggestion = UploadMappingSuggestion(
            upload_id=upload.id,
            source_id=source.id,
            file_name=upload.file_name,
            source_type=upload.source_type,
            total_rows=total_rows,
            detected_columns=columns,
            dropped_pii_columns=dropped_pii,
            preview_rows=preview_rows[:10],
            suggested_mapping={
                f_key: {
                    "column": mapping.mapping_json.get(f_key),
                    "confidence": 1.0,
                    "match_type": "EXACT" if mapping.mapping_json.get(f_key) in columns else "APPROVED_VERSION"
                }
                for f_key in CANONICAL_FIELDS.keys()
                if mapping.mapping_json.get(f_key)
            },
            missing_required=[],
            canonical_fields=[
                {
                    "key": k,
                    "display_name": v["display_name"],
                    "required_for": v["required_for"],
                    "description": v["description"]
                }
                for k, v in CANONICAL_FIELDS.items()
            ],
            is_mapping_compatible=True,
            incompatibility_reasons=[],
            active_mapping_version=mapping.version,
            generation_status="completed"
        )
        db.add(db_suggestion)
        db.commit()

        # Ingest immediately with approved, verified compatible mapping
        ingestion_service = IngestionService(db)
        result = ingestion_service.process_upload(upload, df, mapping)
        return {
            "type": "completed",
            "upload_id": upload.id,
            "upload": UploadResponse.model_validate(upload).model_dump(),
            "summary": result,
            "dropped_pii_columns": dropped_pii
        }
    else:
        # Store in cache and durable disk storage so user can review, map, and approve mapping
        save_pending_file_to_disk(str(upload.id), content)
        _PENDING_FILE_CACHE[str(upload.id)] = content

        # Extract representative samples for candidate columns from preview rows
        samples_by_col = {
            c: [row[c] for row in preview_rows if c in row and row[c] is not None][:5]
            for c in columns
        }

        # Generate automated suggestions (Exact -> Fuzzy -> AI Fallback)
        mapping_suggestions = suggest_column_mappings(columns, source.source_type, samples_by_col=samples_by_col)

        # Persist upload-specific mapping review suggestion to database
        db_suggestion = UploadMappingSuggestion(
            upload_id=upload.id,
            source_id=source.id,
            file_name=upload.file_name,
            source_type=upload.source_type,
            total_rows=total_rows,
            detected_columns=columns,
            dropped_pii_columns=dropped_pii,
            preview_rows=preview_rows[:10],
            suggested_mapping=mapping_suggestions["suggestions"],
            missing_required=mapping_suggestions["missing_required"],
            canonical_fields=mapping_suggestions["canonical_fields"],
            is_mapping_compatible=is_compatible,
            incompatibility_reasons=incompatibility_reasons,
            active_mapping_version=mapping.version if mapping else None,
            generation_status="completed"
        )
        db.add(db_suggestion)
        db.commit()

        partner_display = f"{source.partner_id.title()} ({source.source_type.title()} Feed)"
        return {
            "type": "preview",
            "upload_id": upload.id,
            "source_id": source.id,
            "source_name": partner_display,
            "file_name": upload.file_name,
            "source_type": upload.source_type,
            "total_rows": total_rows,
            "detected_columns": columns,
            "dropped_pii_columns": dropped_pii,
            "preview_rows": preview_rows[:10],
            "suggested_mapping": mapping_suggestions["suggestions"],
            "missing_required": mapping_suggestions["missing_required"],
            "canonical_fields": mapping_suggestions["canonical_fields"],
            "active_mapping_version": mapping.version if mapping else None,
            "is_mapping_compatible": is_compatible,
            "incompatibility_reasons": incompatibility_reasons,
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


@router.get("/{upload_id}/preview", response_model=UploadPreviewResponse)
def get_upload_preview(
    upload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["finance_exec", "cofounder"]))
):
    """
    Retrieve persisted column mapping review and preview details for an upload.
    Enforces RBAC: Both finance_exec and cofounder can view preview data.
    Never approves mappings, never triggers ingestion, and never calls Gemini if
    suggestions already exist for this upload.
    """
    try:
        u_uuid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload_id format")

    upload = db.query(Upload).filter(Upload.id == u_uuid).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Upload {upload_id} not found")

    source = db.query(Source).filter(Source.id == upload.source_id).first()
    partner_display = f"{source.partner_id.title()} ({source.source_type.title()} Feed)" if source else upload.source_type.title()

    # 1. First check persisted suggestion record in database
    suggestion = db.query(UploadMappingSuggestion).filter(UploadMappingSuggestion.upload_id == upload.id).first()
    if suggestion:
        return UploadPreviewResponse(
            type="preview",
            upload_id=upload.id,
            source_id=upload.source_id,
            source_name=partner_display,
            file_name=upload.file_name,
            source_type=upload.source_type,
            processing_status=upload.processing_status,
            total_rows=upload.row_count,
            detected_columns=suggestion.detected_columns,
            dropped_pii_columns=suggestion.dropped_pii_columns,
            preview_rows=suggestion.preview_rows,
            suggested_mapping=suggestion.suggested_mapping,
            missing_required=suggestion.missing_required,
            canonical_fields=suggestion.canonical_fields,
            is_mapping_compatible=suggestion.is_mapping_compatible,
            incompatibility_reasons=suggestion.incompatibility_reasons,
            active_mapping_version=suggestion.active_mapping_version,
            upload=UploadResponse.model_validate(upload)
        )

    # 2. If not yet in DB, check memory cache then durable disk storage
    content = _PENDING_FILE_CACHE.get(str(upload.id))
    if not content:
        content = read_pending_file_from_disk(str(upload.id))
        if content:
            _PENDING_FILE_CACHE[str(upload.id)] = content

    if not content:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Raw file content expired from temporary buffer and no persisted suggestions exist. Please re-upload the file."
        )

    # Parse and compute suggestions once, then persist in DB
    try:
        df, columns, preview_rows, total_rows, dropped_pii = parse_tabular_file(content, upload.file_name)
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    samples_by_col = {
        c: [row[c] for row in preview_rows if c in row and row[c] is not None][:5]
        for c in columns
    }
    mapping_suggestions = suggest_column_mappings(columns, upload.source_type, samples_by_col=samples_by_col)

    # Check compatibility with active mapping if any
    active_map = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_id == upload.source_id, ColumnMapping.status == "approved")
        .order_by(desc(ColumnMapping.version))
        .first()
    )
    is_compat = True if active_map else False
    incompat_reasons: List[str] = []
    if active_map and active_map.mapping_json:
        col_set = {c.lower().strip() for c in columns}
        for field_key, meta in CANONICAL_FIELDS.items():
            if upload.source_type in meta.get("required_for", []):
                mapped_col = active_map.mapping_json.get(field_key)
                if not mapped_col or str(mapped_col).strip() == "":
                    is_compat = False
                    incompat_reasons.append(f"Required field '{meta['display_name']}' is not mapped.")
                elif str(mapped_col).lower().strip() not in col_set:
                    is_compat = False
                    incompat_reasons.append(f"Required field '{meta['display_name']}' mapped to '{mapped_col}' missing.")
    else:
        is_compat = False
        incompat_reasons.append("No approved column mapping found for this source.")

    new_suggestion = UploadMappingSuggestion(
        upload_id=upload.id,
        source_id=upload.source_id,
        file_name=upload.file_name,
        source_type=upload.source_type,
        total_rows=total_rows,
        detected_columns=columns,
        dropped_pii_columns=dropped_pii,
        preview_rows=preview_rows[:10],
        suggested_mapping=mapping_suggestions["suggestions"],
        missing_required=mapping_suggestions["missing_required"],
        canonical_fields=mapping_suggestions["canonical_fields"],
        is_mapping_compatible=is_compat,
        incompatibility_reasons=incompat_reasons,
        active_mapping_version=active_map.version if active_map else None,
        generation_status="completed"
    )
    db.add(new_suggestion)
    db.commit()
    db.refresh(new_suggestion)

    return UploadPreviewResponse(
        type="preview",
        upload_id=upload.id,
        source_id=upload.source_id,
        source_name=partner_display,
        file_name=upload.file_name,
        source_type=upload.source_type,
        processing_status=upload.processing_status,
        total_rows=total_rows,
        detected_columns=columns,
        dropped_pii_columns=dropped_pii,
        preview_rows=preview_rows[:10],
        suggested_mapping=mapping_suggestions["suggestions"],
        missing_required=mapping_suggestions["missing_required"],
        canonical_fields=mapping_suggestions["canonical_fields"],
        is_mapping_compatible=is_compat,
        incompatibility_reasons=incompat_reasons,
        active_mapping_version=active_map.version if active_map else None,
        upload=UploadResponse.model_validate(upload)
    )


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
        content = read_pending_file_from_disk(str(upload.id))
        if content:
            _PENDING_FILE_CACHE[str(upload.id)] = content

    if not content:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Raw file content expired from temporary buffer. Please re-upload the file."
        )

    df, _, _, _, _ = parse_tabular_file(content, upload.file_name)
    upload.mapping_version = mapping.version

    ingestion_service = IngestionService(db)
    result = ingestion_service.process_upload(upload, df, mapping)

    # Clean up memory buffer and disk file
    _PENDING_FILE_CACHE.pop(str(upload.id), None)
    delete_pending_file_from_disk(str(upload.id))

    return {
        "status": "success",
        "upload": UploadResponse.model_validate(upload).model_dump(),
        "summary": result
    }
