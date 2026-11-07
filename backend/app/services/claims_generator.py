from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.claim import Claim
from app.models.order_recon import OrderRecon
from app.services.rate_card_calculator import quantize_amount


class ClaimsGenerator:
    def __init__(self, db: Session):
        self.db = db

    def generate_draft_claims(self, order_ids: Optional[List[str]] = None) -> List[Claim]:
        """
        Generates draft claims for all orders with confirmed discrepancies and money at risk > 0.
        Preserves existing executive-entered notes, recovered amounts, and modified claim statuses.
        """
        stmt = (
            select(OrderRecon)
            .where(
                OrderRecon.money_at_risk > 0,
                OrderRecon.status.notin_(["settled", "pending"])
            )
        )
        if order_ids:
            stmt = stmt.where(OrderRecon.order_id.in_(order_ids))

        discrepant_orders = self.db.execute(stmt).scalars().all()
        generated_claims: List[Claim] = []

        for recon in discrepant_orders:
            # Determine claim reason based on primary status
            claim_reason = recon.status
            if recon.reason_codes:
                claim_reason = recon.reason_codes[0]

            existing_claim = (
                self.db.query(Claim)
                .filter(
                    Claim.order_id == recon.order_id,
                    Claim.claim_reason == claim_reason
                )
                .first()
            )

            evidence = {
                "order_value": str(recon.order_value),
                "expected_amount": str(recon.expected_amount) if recon.expected_amount is not None else None,
                "received_amount": str(recon.received_amount),
                "difference": str(recon.difference) if recon.difference is not None else None,
                "due_date": recon.due_date.isoformat() if recon.due_date else None,
                "age_days": recon.age_days,
                "settlement_gap": str(recon.settlement_gap_component),
                "freight_excess": str(recon.freight_excess_component),
                "return_loss": str(recon.return_loss_component),
                "reason_codes": recon.reason_codes,
                "breakdown": recon.breakdown_json
            }

            if existing_claim:
                # Update evidence, but NEVER overwrite manual notes, recovered_amount, or non-draft status
                existing_claim.evidence_json = evidence
                if existing_claim.claim_status == "draft":
                    existing_claim.claim_amount = quantize_amount(recon.money_at_risk)
                self.db.add(existing_claim)
                generated_claims.append(existing_claim)
            else:
                claim = Claim(
                    order_id=recon.order_id,
                    partner_id=recon.partner_id,
                    claim_amount=quantize_amount(recon.money_at_risk),
                    recovered_amount=quantize_amount(0.00),
                    claim_reason=claim_reason,
                    evidence_json=evidence,
                    claim_status="draft",
                    notes=None
                )
                self.db.add(claim)
                generated_claims.append(claim)

        self.db.commit()
        return generated_claims
