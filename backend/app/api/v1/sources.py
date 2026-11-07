from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.source import Source

router = APIRouter(prefix="/sources", tags=["Sources"])


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partner_id: str
    source_type: str
    name: str
    file_format: str
    is_active: bool


@router.get("/", response_model=List[SourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all registered ingestion sources."""
    sources = db.query(Source).filter(Source.is_active == True).order_by(Source.partner_id, Source.source_type).all()
    return sources
