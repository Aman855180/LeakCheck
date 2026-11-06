from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.api.deps import require_role
from app.models.rate_card import RateCard
from app.schemas.rate_card import RateCardCreate, RateCardResponse

router = APIRouter(prefix="/rate-cards", tags=["Rate Cards"])


@router.get("/", response_model=List[RateCardResponse])
def list_rate_cards(
    partner_id: Optional[str] = None,
    channel: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db),
    _user=Depends(require_role(["finance_exec", "cofounder"]))
):
    query = db.query(RateCard).filter(RateCard.is_active == is_active)
    if partner_id:
        query = query.filter(RateCard.partner_id == partner_id)
    if channel:
        query = query.filter(RateCard.channel == channel)
    return query.order_by(RateCard.valid_from.desc()).all()


@router.post("/", response_model=RateCardResponse, status_code=status.HTTP_201_CREATED)
def create_rate_card(
    card_data: RateCardCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role(["finance_exec"]))  # Only finance_exec can create/modify
):
    rate_card = RateCard(
        partner_id=card_data.partner_id,
        channel=card_data.channel,
        rule_type=card_data.rule_type,
        params_json=card_data.params_json,
        valid_from=card_data.valid_from,
        valid_until=card_data.valid_until,
        is_active=card_data.is_active
    )
    try:
        db.add(rate_card)
        db.commit()
        db.refresh(rate_card)
        return rate_card
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rate card creation failed. Overlapping effective date range or invalid partner: {str(e)}"
        )


@router.get("/lookup", response_model=RateCardResponse)
def lookup_rate_card(
    partner_id: str = Query(...),
    channel: str = Query(...),
    rule_type: str = Query(...),
    target_date: date = Query(default=date(2026, 11, 1)),
    db: Session = Depends(get_db),
    _user=Depends(require_role(["finance_exec", "cofounder"]))
):
    # Lookup using half-open interval [valid_from, valid_until)
    card = db.query(RateCard).filter(
        RateCard.partner_id == partner_id,
        RateCard.channel == channel,
        RateCard.rule_type == rule_type,
        RateCard.is_active == True,
        RateCard.valid_from <= target_date,
        text("valid_until IS NULL OR valid_until > :t_date").bindparams(t_date=target_date)
    ).first()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active rate card found for partner '{partner_id}', channel '{channel}', rule '{rule_type}' on date '{target_date}'."
        )

    return card
