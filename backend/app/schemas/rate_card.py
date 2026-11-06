import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RateCardCreate(BaseModel):
    partner_id: str
    channel: str
    rule_type: str
    params_json: Dict[str, Any]
    valid_from: date
    valid_until: Optional[date] = None
    is_active: bool = True


class RateCardResponse(BaseModel):
    id: uuid.UUID
    partner_id: str
    channel: str
    rule_type: str
    params_json: Dict[str, Any]
    valid_from: date
    valid_until: Optional[date] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
