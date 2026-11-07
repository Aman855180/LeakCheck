import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.source import Source
from app.models.partner import Partner

router = APIRouter(prefix="/sources", tags=["Sources"])


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partner_id: str
    source_type: str
    name: str
    partner_name: str
    file_format: str = "csv/xlsx"
    is_active: bool = True


@router.get("/", response_model=List[SourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all registered ingestion sources with human-readable partner names."""
    rows = (
        db.query(Source, Partner)
        .join(Partner, Source.partner_id == Partner.id)
        .order_by(Partner.name, Source.source_type)
        .all()
    )
    result = []
    for src, partner in rows:
        display_name = f"{partner.name} ({src.source_type.capitalize()} Feed)"
        result.append(
            SourceResponse(
                id=src.id,
                partner_id=src.partner_id,
                source_type=src.source_type,
                name=display_name,
                partner_name=partner.name,
                is_active=partner.is_active
            )
        )
    return result
