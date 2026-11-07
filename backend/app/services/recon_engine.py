from datetime import datetime, date, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, desc

from app.models.order_event import OrderEvent
from app.models.order_recon import OrderRecon
from app.models.partner import Partner
from app.models.warehouse_receipt import WarehouseReceipt
from app.models.tracking_event import TrackingEvent
from app.services.rate_card_calculator import RateCardCalculator, quantize_amount

MATERIALITY_THRESHOLD = Decimal("10.00")
DEFAULT_AS_OF_DATE = date(2026, 11, 1)


def get_age_bucket(days: int) -> str:
    """
    Standardized Age Bucketing:
    - 0 to 7 days: '0-7'
    - 8 to 15 days: '8-15'
    - 16 to 30 days: '16-30'
    - 31+ days: '31+'
    """
    if days <= 7:
        return "0-7"
    elif days <= 15:
        return "8-15"
    elif days <= 30:
        return "16-30"
    else:
        return "31+"


class ReconciliationEngine:
    def __init__(self, db: Session, as_of: Optional[date] = None):
        self.db = db
        self.as_of = as_of or DEFAULT_AS_OF_DATE
        self.rate_calculator = RateCardCalculator(db)

    def run_reconciliation(self, order_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Executes end-to-end reconciliation across all uploaded events or specified order_ids.
        Recomputes order_recon records idempotently using Decimal precision and canonical partner namespaces.
        """
        # 1. Fetch distinct (partner_id, external_order_id) pairs
        stmt = select(OrderEvent.source_partner_id, OrderEvent.external_order_id).distinct()
        if order_ids:
            stmt = stmt.where(OrderEvent.external_order_id.in_(order_ids))
        
        pairs = self.db.execute(stmt).all()

        reconciled_records: List[OrderRecon] = []
        summary_counts = {
            "settled": 0,
            "short_paid": 0,
            "unpaid_past_due": 0,
            "freight_overcharged": 0,
            "return_not_received": 0,
            "pending": 0
        }
        total_risk = Decimal("0.00")

        # Reconcile each partner + external_order_id pair
        # Track pairs processed to prevent duplicate reconciliation if courier feeds also contain external_order_id
        processed_pairs = set()

        for partner_id, ext_order_id in pairs:
            # If partner is a courier or warehouse, find the primary sales partner for this order if exists
            partner = self.db.query(Partner).filter(Partner.id == partner_id).first()
            if partner and partner.partner_type in ("courier", "warehouse"):
                # Check if there is a sales partner for this order
                sales_event = (
                    self.db.query(OrderEvent)
                    .filter(
                        OrderEvent.external_order_id == ext_order_id,
                        OrderEvent.source_partner_id != partner_id
                    )
                    .first()
                )
                if sales_event:
                    partner_id = sales_event.source_partner_id

            pair_key = (partner_id, ext_order_id)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            recon_entry = self.reconcile_single_order(partner_id=partner_id, external_order_id=ext_order_id)
            if recon_entry:
                reconciled_records.append(recon_entry)
                summary_counts[recon_entry.status] = summary_counts.get(recon_entry.status, 0) + 1
                total_risk += recon_entry.money_at_risk

        self.db.commit()

        return {
            "as_of": self.as_of.isoformat(),
            "total_orders_reconciled": len(reconciled_records),
            "status_counts": summary_counts,
            "total_money_at_risk": str(quantize_amount(total_risk)),
            "reconciled_orders": [r.external_order_id for r in reconciled_records]
        }

    def reconcile_single_order(self, external_order_id: str, partner_id: Optional[str] = None) -> Optional[OrderRecon]:
        """
        Reconciles a single order for a specific partner across orders, settlements, COD, freight, tracking, and warehouse feeds.
        """
        # Fetch all active/effective events for this order
        events_query = self.db.query(OrderEvent).filter(OrderEvent.external_order_id == external_order_id)
        if partner_id:
            # Match events from the specified partner or general logistics events matching external_order_id
            events_query = events_query.filter(
                or_(
                    OrderEvent.source_partner_id == partner_id,
                    OrderEvent.event_type.in_(["freight_charge", "cod_remittance"])
                )
            )

        events = events_query.order_by(OrderEvent.event_date.asc()).all()
        if not events:
            return None

        # Determine primary order event and partner
        order_event = next((e for e in events if e.event_type.lower() in ("order_placed", "orders")), None)
        resolved_partner_id = partner_id or (order_event.source_partner_id if order_event else events[0].source_partner_id)
        
        # Get partner channel
        partner = self.db.query(Partner).filter(Partner.id == resolved_partner_id).first()
        channel = partner.channel if partner else "marketplace"

        # Determine core order properties
        order_date = order_event.event_date if order_event else events[0].event_date
        order_value = quantize_amount(order_event.amount if order_event else Decimal("0.00"))
        
        # Extract payment mode
        payment_mode = "PREPAID"
        if order_event and order_event.raw_data:
            pm = str(order_event.raw_data.get("Payment Method", "")).upper()
            if "COD" in pm or "CASH" in pm:
                payment_mode = "COD"
        elif any("cod" in e.event_type.lower() for e in events):
            payment_mode = "COD"

        # Aggregate received financial amounts pre-TCS/TDS
        settlement_credit = Decimal("0.00")
        cod_remittance = Decimal("0.00")
        actual_commission = Decimal("0.00")
        actual_fixed_fee = Decimal("0.00")
        actual_freight = Decimal("0.00")
        actual_cod_fee = Decimal("0.00")
        tcs_amount = Decimal("0.00")
        tds_amount = Decimal("0.00")

        # Source-evidenced refund events
        refund_events: List[OrderEvent] = []

        for ev in events:
            ev_type = ev.event_type.lower()
            if "settlement" in ev_type:
                # Capture settlement credit
                credit_val = ev.settlement_credit if ev.settlement_credit is not None and ev.settlement_credit != Decimal("0.00") else ev.amount
                settlement_credit += quantize_amount(credit_val)
                actual_commission += quantize_amount(ev.commission)
                actual_fixed_fee += quantize_amount(ev.fixed_fee)
                actual_freight += quantize_amount(ev.shipping_fee)
                tcs_amount += quantize_amount(ev.tcs)
                tds_amount += quantize_amount(ev.tds)

                if ev_type in ("settlement_reversal", "refund", "customer_refund") or (ev.amount < 0) or (credit_val < 0):
                    refund_events.append(ev)
            elif "cod" in ev_type:
                cod_remittance += quantize_amount(ev.amount)
                actual_cod_fee += quantize_amount(ev.cod_fee)
            elif "freight" in ev_type:
                actual_freight += quantize_amount(ev.freight_amount if ev.freight_amount else ev.amount)

        received_amount = quantize_amount(settlement_credit + cod_remittance)

        # Inspect tracking & delivery state
        latest_tracking = (
            self.db.query(TrackingEvent)
            .filter(TrackingEvent.order_id == external_order_id)
            .order_by(TrackingEvent.event_timestamp.desc())
            .first()
        )
        tracking_status = latest_tracking.raw_status_code.upper() if latest_tracking else "DELIVERED"
        delivery_timestamp = latest_tracking.event_timestamp if latest_tracking else order_date

        is_returned = ("RTO" in tracking_status or "RETURN" in tracking_status)
        
        # Check warehouse receipt
        warehouse_receipt = (
            self.db.query(WarehouseReceipt)
            .filter(WarehouseReceipt.order_id == external_order_id)
            .first()
        )

        # Rate Card Calculation
        calc = self.rate_calculator.calculate_expected_settlement(
            partner_id=resolved_partner_id,
            channel=channel,
            order_date=order_date,
            order_value=order_value,
            payment_mode=payment_mode,
            is_returned=is_returned
        )

        expected_amount = calc.expected_amount
        expected_commission = calc.expected_commission
        expected_fixed_fee = calc.expected_fixed_fee
        expected_freight = calc.expected_freight
        expected_cod_fee = calc.expected_cod_fee

        # Due Date Calculation relative to delivery / event
        due_date = delivery_timestamp + timedelta(days=calc.due_days)

        # Difference
        difference: Optional[Decimal] = None
        if expected_amount is not None:
            difference = quantize_amount(received_amount - expected_amount)

        # Calculate Age Days
        as_of_dt = datetime(self.as_of.year, self.as_of.month, self.as_of.day, tzinfo=timezone.utc)
        age_days = 0
        if due_date and as_of_dt > due_date:
            age_days = (as_of_dt.date() - due_date.date()).days
        age_bucket = get_age_bucket(age_days)

        # Status & Reason Codes Determination
        reason_codes: List[str] = []

        # Check return not received
        return_grace_deadline = delivery_timestamp + timedelta(days=calc.return_grace_days)
        is_return_missing = False
        if is_returned and not warehouse_receipt:
            if as_of_dt > return_grace_deadline:
                is_return_missing = True
                reason_codes.append("return_receipt_missing")

        # Check discrepancies
        has_freight_overcharge = (actual_freight - expected_freight > MATERIALITY_THRESHOLD)
        if has_freight_overcharge:
            reason_codes.append("freight_overcharge")

        if actual_commission - expected_commission > MATERIALITY_THRESHOLD:
            reason_codes.append("excess_commission")

        is_unpaid = False
        is_short_paid = False

        if difference is not None and difference < -MATERIALITY_THRESHOLD:
            if received_amount == Decimal("0.00"):
                if as_of_dt > due_date:
                    is_unpaid = True
                    if payment_mode.upper() == "COD":
                        reason_codes.append("cod_remittance_missing")
                    else:
                        reason_codes.append("settlement_shortfall")
                else:
                    # Legitimate waiting window
                    pass
            else:
                is_short_paid = True
                if is_returned and actual_freight > expected_freight:
                    reason_codes.append("excess_return_deduction")
                else:
                    reason_codes.append("settlement_shortfall")

        # STATUS PRECEDENCE HIERARCHY (Section 24.9):
        # return_not_received > unpaid_past_due > freight_overcharged > short_paid > settled
        # pending applies only when no confirmed discrepancy exists
        if expected_amount is None:
            status = "pending"
            reason_codes.append("missing_rate_card")
        elif is_return_missing:
            status = "return_not_received"
        elif is_unpaid:
            status = "unpaid_past_due"
        elif has_freight_overcharge and not is_short_paid:
            status = "freight_overcharged"
        elif is_short_paid:
            status = "short_paid"
        elif difference is not None and difference > MATERIALITY_THRESHOLD:
            status = "settled"
            reason_codes.append("overpaid_review")
        elif received_amount == Decimal("0.00") and as_of_dt <= due_date and expected_amount > Decimal("0.00"):
            status = "pending"
        else:
            status = "settled"

        # NON-OVERLAPPING MONEY AT RISK CALCULATION
        settlement_gap_comp = Decimal("0.00")
        freight_excess_comp = Decimal("0.00")
        return_loss_comp = Decimal("0.00")
        money_at_risk = Decimal("0.00")

        # 1. Freight excess component (max(actual - expected, 0) if > threshold)
        if has_freight_overcharge:
            freight_excess_comp = quantize_amount(actual_freight - expected_freight)

        # 2. Raw Settlement shortfall component
        raw_settlement_gap = Decimal("0.00")
        if difference is not None and difference < -MATERIALITY_THRESHOLD:
            raw_settlement_gap = quantize_amount(expected_amount - received_amount)

        # 3. Source-evidenced return loss component
        evidenced_refund_exposure = Decimal("0.00")
        gross_return_loss = Decimal("0.00")
        cap_applied = False
        refund_overlap_subtracted = Decimal("0.00")
        source_refund_event_ids = [str(ev.id) for ev in refund_events]

        if is_return_missing:
            # Sum of source-evidenced refund deductions
            total_refund_amount = sum(abs(ev.amount) for ev in refund_events)
            evidenced_refund_exposure = quantize_amount(total_refund_amount)

            if evidenced_refund_exposure > Decimal("0.00"):
                # Cap at order_value
                if evidenced_refund_exposure > order_value:
                    gross_return_loss = order_value
                    cap_applied = True
                else:
                    gross_return_loss = evidenced_refund_exposure

                return_loss_comp = gross_return_loss

        # 4. Deduplicate overlap between settlement gap and other components
        # A. Deduct freight excess from settlement gap if freight was already deducted in settlement
        gap_after_freight = max(raw_settlement_gap - freight_excess_comp, Decimal("0.00"))

        # B. Deduct only the settlement gap attributable to the same underlying refund exposure
        if evidenced_refund_exposure > Decimal("0.00"):
            # The portion of the settlement gap caused by this refund deduction
            refund_overlap_subtracted = min(gap_after_freight, evidenced_refund_exposure)
            settlement_gap_comp = max(gap_after_freight - refund_overlap_subtracted, Decimal("0.00"))
        else:
            settlement_gap_comp = gap_after_freight

        # Total non-overlapping exposure
        if status not in ("settled", "pending"):
            money_at_risk = quantize_amount(settlement_gap_comp + freight_excess_comp + return_loss_comp)

        # Build detailed audit breakdown JSON
        audit_details = {
            "order_value": str(order_value),
            "expected": {
                "net": str(expected_amount) if expected_amount is not None else None,
                "commission": str(expected_commission),
                "freight": str(expected_freight),
                "fixed_fee": str(expected_fixed_fee),
                "cod_fee": str(expected_cod_fee),
                "rate_card_version": calc.rate_card.rule_type if calc.rate_card else None
            },
            "received": {
                "net": str(received_amount),
                "settlement_credit": str(settlement_credit),
                "cod_remittance": str(cod_remittance),
                "actual_commission": str(actual_commission),
                "actual_freight": str(actual_freight),
                "actual_fixed_fee": str(actual_fixed_fee),
                "actual_cod_fee": str(actual_cod_fee)
            },
            "statutory_taxes_isolated": {
                "tcs": str(tcs_amount),
                "tds": str(tds_amount),
                "treatment": "Excluded 100% from leakage calculation"
            },
            "risk_decomposition": {
                "settlement_gap": str(settlement_gap_comp),
                "freight_excess": str(freight_excess_comp),
                "return_loss": str(return_loss_comp),
                "total_money_at_risk": str(money_at_risk)
            },
            "return_loss_breakdown": {
                "is_return_missing": is_return_missing,
                "evidenced_refund_exposure": str(evidenced_refund_exposure),
                "gross_return_loss": str(gross_return_loss),
                "cap_applied": cap_applied,
                "source_refund_event_ids": source_refund_event_ids,
                "refund_overlap_subtracted_from_gap": str(refund_overlap_subtracted),
                "unrelated_settlement_gap_retained": str(settlement_gap_comp),
                "net_return_loss": str(return_loss_comp)
            },
            "precedence_resolution": {
                "evaluated_status": status,
                "all_reason_codes": reason_codes
            }
        }

        # Upsert into order_recon using (partner_id, external_order_id)
        existing_recon = (
            self.db.query(OrderRecon)
            .filter(
                OrderRecon.partner_id == resolved_partner_id,
                OrderRecon.external_order_id == external_order_id
            )
            .first()
        )

        if not existing_recon:
            recon = OrderRecon(
                external_order_id=external_order_id,
                order_id=external_order_id,
                partner_id=resolved_partner_id,
                channel=channel,
                payment_mode=payment_mode,
                order_date=order_date,
                order_value=order_value,
                rate_card_id=calc.rate_card.id if calc.rate_card else None,
                expected_amount=expected_amount,
                received_amount=received_amount,
                settlement_credit=settlement_credit,
                cod_remittance=cod_remittance,
                expected_commission=expected_commission,
                actual_commission=actual_commission,
                expected_fixed_fee=expected_fixed_fee,
                actual_fixed_fee=actual_fixed_fee,
                expected_freight=expected_freight,
                actual_freight=actual_freight,
                expected_cod_fee=expected_cod_fee,
                actual_cod_fee=actual_cod_fee,
                tcs_amount=tcs_amount,
                tds_amount=tds_amount,
                difference=difference,
                status=status,
                reason_codes=reason_codes,
                due_date=due_date,
                age_days=age_days,
                age_bucket=age_bucket,
                money_at_risk=money_at_risk,
                settlement_gap_component=settlement_gap_comp,
                freight_excess_component=freight_excess_comp,
                return_loss_component=return_loss_comp,
                breakdown_json=audit_details,
                source_events_count=len(events),
                computed_at=datetime.now(timezone.utc)
            )
            self.db.add(recon)
            self.db.flush()
            return recon
        else:
            existing_recon.channel = channel
            existing_recon.payment_mode = payment_mode
            existing_recon.order_date = order_date
            existing_recon.order_value = order_value
            existing_recon.rate_card_id = calc.rate_card.id if calc.rate_card else None
            existing_recon.expected_amount = expected_amount
            existing_recon.received_amount = received_amount
            existing_recon.settlement_credit = settlement_credit
            existing_recon.cod_remittance = cod_remittance
            existing_recon.expected_commission = expected_commission
            existing_recon.actual_commission = actual_commission
            existing_recon.expected_fixed_fee = expected_fixed_fee
            existing_recon.actual_fixed_fee = actual_fixed_fee
            existing_recon.expected_freight = expected_freight
            existing_recon.actual_freight = actual_freight
            existing_recon.expected_cod_fee = expected_cod_fee
            existing_recon.actual_cod_fee = actual_cod_fee
            existing_recon.tcs_amount = tcs_amount
            existing_recon.tds_amount = tds_amount
            existing_recon.difference = difference
            existing_recon.status = status
            existing_recon.reason_codes = reason_codes
            existing_recon.due_date = due_date
            existing_recon.age_days = age_days
            existing_recon.age_bucket = age_bucket
            existing_recon.money_at_risk = money_at_risk
            existing_recon.settlement_gap_component = settlement_gap_comp
            existing_recon.freight_excess_component = freight_excess_comp
            existing_recon.return_loss_component = return_loss_comp
            existing_recon.breakdown_json = audit_details
            existing_recon.source_events_count = len(events)
            existing_recon.computed_at = datetime.now(timezone.utc)
            self.db.add(existing_recon)
            self.db.flush()
            return existing_recon
