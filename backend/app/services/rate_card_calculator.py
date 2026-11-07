from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.models.rate_card import RateCard


class CalculationResult:
    def __init__(
        self,
        rate_card: Optional[RateCard],
        expected_amount: Optional[Decimal],
        expected_commission: Decimal,
        expected_fixed_fee: Decimal,
        expected_freight: Decimal,
        expected_cod_fee: Decimal,
        due_days: int,
        return_grace_days: int,
        breakdown: Dict[str, Any]
    ):
        self.rate_card = rate_card
        self.expected_amount = expected_amount
        self.expected_commission = expected_commission
        self.expected_fixed_fee = expected_fixed_fee
        self.expected_freight = expected_freight
        self.expected_cod_fee = expected_cod_fee
        self.due_days = due_days
        self.return_grace_days = return_grace_days
        self.breakdown = breakdown


def quantize_amount(val: Any) -> Decimal:
    """Format decimal to 2 decimal places using standard ROUND_HALF_UP."""
    if val is None:
        return Decimal("0.00")
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class RateCardCalculator:
    def __init__(self, db: Session):
        self.db = db

    def resolve_rate_card(
        self,
        partner_id: str,
        channel: str,
        target_date: date,
        payment_mode: str = "PREPAID",
        is_returned: bool = False
    ) -> Optional[RateCard]:
        """
        Resolves the applicable approved rate card using half-open date interval [valid_from, valid_until).
        """
        # Base query for active rate cards matching partner
        stmt = (
            select(RateCard)
            .where(
                RateCard.partner_id == partner_id,
                RateCard.is_active == True,
                RateCard.valid_from <= target_date,
                or_(
                    RateCard.valid_until.is_(None),
                    RateCard.valid_until > target_date
                )
            )
        )
        candidates = self.db.execute(stmt).scalars().all()
        if not candidates:
            # Fallback to channel-level rate card
            stmt_fallback = (
                select(RateCard)
                .where(
                    RateCard.channel == channel,
                    RateCard.is_active == True,
                    RateCard.valid_from <= target_date,
                    or_(
                        RateCard.valid_until.is_(None),
                        RateCard.valid_until > target_date
                    )
                )
            )
            candidates = self.db.execute(stmt_fallback).scalars().all()

        if not candidates:
            return None

        # Prefer specific rule types based on order characteristics
        if is_returned:
            for c in candidates:
                if "return" in c.rule_type.lower() or c.params_json.get("reverse_shipping_fee"):
                    return c

        if payment_mode.upper() == "COD":
            for c in candidates:
                if "cod" in c.rule_type.lower():
                    return c

        # Next prefer prepaid or standard
        for c in candidates:
            if "prepaid" in c.rule_type.lower() or "standard" in c.rule_type.lower():
                return c

        return candidates[0]

    def calculate_expected_settlement(
        self,
        partner_id: str,
        channel: str,
        order_date: datetime,
        order_value: Decimal,
        payment_mode: str = "PREPAID",
        is_returned: bool = False,
        explicit_rate_card: Optional[RateCard] = None
    ) -> CalculationResult:
        """
        Calculates expected settlement amount and itemized deductions using Decimal arithmetic.
        If no rate card is found, returns expected_amount=None per Phase 0 agreement.
        """
        target_date = order_date.date() if isinstance(order_date, datetime) else order_date
        rate_card = explicit_rate_card or self.resolve_rate_card(
            partner_id=partner_id,
            channel=channel,
            target_date=target_date,
            payment_mode=payment_mode,
            is_returned=is_returned
        )

        if not rate_card:
            return CalculationResult(
                rate_card=None,
                expected_amount=None,  # Explicitly nullable per Phase 0 decision #3
                expected_commission=Decimal("0.00"),
                expected_fixed_fee=Decimal("0.00"),
                expected_freight=Decimal("0.00"),
                expected_cod_fee=Decimal("0.00"),
                due_days=7,
                return_grace_days=7,
                breakdown={"error": "NO_VALID_RATE_CARD", "message": "No active rate card for partner/date"}
            )

        params = rate_card.params_json or {}
        order_val = quantize_amount(order_value)

        comm_pct = Decimal(str(params.get("commission_pct", 0.0)))
        fixed_fee = quantize_amount(params.get("fixed_fee", 0.0))
        fwd_shipping = quantize_amount(params.get("forward_shipping_fee", 0.0))
        rev_shipping = quantize_amount(params.get("reverse_shipping_fee", 0.0))
        cod_fee = quantize_amount(params.get("cod_handling_fee", 0.0))

        # Default due days
        cod_due_days = int(params.get("cod_due_days", 7))
        settlement_due_days = int(params.get("settlement_due_days", 10 if channel == "marketplace" else 3))
        return_grace_days = int(params.get("return_receipt_grace_days", 7))

        due_days = cod_due_days if payment_mode.upper() == "COD" else settlement_due_days

        if is_returned:
            # For returned orders, merchandise revenue is credited back (0), but shipping and reverse fees remain
            expected_commission = Decimal("0.00")
            expected_fixed = Decimal("0.00")
            expected_freight = quantize_amount(fwd_shipping + rev_shipping)
            expected_cod = Decimal("0.00")
            expected_net = quantize_amount(-expected_freight)

            breakdown = {
                "rate_card_id": str(rate_card.id),
                "rule_type": rate_card.rule_type,
                "order_value": str(order_val),
                "status": "RETURNED",
                "forward_shipping_fee": str(fwd_shipping),
                "reverse_shipping_fee": str(rev_shipping),
                "total_deductions": str(expected_freight),
                "expected_net_settlement": str(expected_net)
            }
        else:
            expected_commission = quantize_amount(order_val * comm_pct / Decimal("100.0"))
            expected_fixed = fixed_fee
            expected_freight = fwd_shipping
            expected_cod = cod_fee if payment_mode.upper() == "COD" else Decimal("0.00")

            total_deductions = expected_commission + expected_fixed + expected_freight + expected_cod
            expected_net = quantize_amount(order_val - total_deductions)

            breakdown = {
                "rate_card_id": str(rate_card.id),
                "rule_type": rate_card.rule_type,
                "order_value": str(order_val),
                "commission_pct": float(comm_pct),
                "commission_amount": str(expected_commission),
                "fixed_fee": str(expected_fixed),
                "forward_shipping_fee": str(expected_freight),
                "cod_handling_fee": str(expected_cod),
                "total_deductions": str(total_deductions),
                "expected_net_settlement": str(expected_net)
            }

        return CalculationResult(
            rate_card=rate_card,
            expected_amount=expected_net,
            expected_commission=expected_commission,
            expected_fixed_fee=expected_fixed,
            expected_freight=expected_freight,
            expected_cod_fee=expected_cod,
            due_days=due_days,
            return_grace_days=return_grace_days,
            breakdown=breakdown
        )
