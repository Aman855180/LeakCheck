# LeakCheck — Engineering Assumptions & Regulatory Decisions Log

**Project:** LeakCheck  
**Client:** Company A, Bengaluru  
**Status:** Phase 1 Foundation Reference Document  

---

## 1. Classification Methodology

In strict compliance with Section 24.1 of the Product Build Specification, every configuration value, financial tariff, timeline, and deduction rule is classified into one of three binding categories:

1. **[Confirmed by Brief]**: Explicitly stated by the client in the core RFP/specification.
2. **[Engineering Assumption]**: Provisional parameter or deterministic logic required to build, test, and benchmark the platform end-to-end.
3. **[Requires Client Confirmation]**: Contractual, commercial, or tax treatment that must be confirmed by Company A's chartered accountants or partner business teams before production deployment.

---

## 2. Comprehensive Assumptions & Parameters Matrix

| Domain | Parameter / Rule | Value | Classification | Derivation / Notes |
|---|---|:---:|:---:|---|
| **Timeline Baseline** | Fixed Reconciliation Date (`as_of`) | `2026-11-01` | **[Engineering Assumption]** | Deterministic baseline required for automated regression suites, age calculation, and seed oracle testing. The UI passes current date by default. |
| **SLA & Due Dates** | Website COD Due Days ($N$) | **7 calendar days** post-delivery | **[Engineering Assumption]** | Standard D2C courier cash turnaround and remittance cycle across Indian aggregators (e.g. Delhivery, Shiprocket). |
| **SLA & Due Dates** | D2C Prepaid Settlement Due Days ($M_{\text{d2c}}$) | **3 calendar days** post-delivery | **[Engineering Assumption]** | Standard payment gateway batch settlement cycle (Razorpay / Cashfree T+2 to T+3). |
| **SLA & Due Dates** | Quick-Commerce Due Days ($M_{\text{qcom}}$) | **7 calendar days** post-delivery | **[Engineering Assumption]** | Typical weekly payout schedule for quick-commerce vendor portals (Blinkit, Zepto). |
| **SLA & Due Dates** | Marketplace Due Days ($M_{\text{mkt}}$) | **10 calendar days** post-delivery | **[Engineering Assumption]** | Standard 7-day customer return policy window plus 3 days payment clearance on Amazon / Flipkart. |
| **SLA & Due Dates** | Warehouse Receipt Grace Period ($R$) | **7 calendar days** post-dock delivery | **[Engineering Assumption]** | Measured strictly from courier dock arrival (`courier_delivered_to_wh_date`). In-transit returns are never missing. |
| **Tax Deductions** | GST TCS (Sec 52 CGST Act) | **0.5%** (0.25% CGST + 0.25% SGST or 0.5% IGST) | **[Engineering Assumption]** / **[Requires Client Confirmation]** | Provisional statutory assumption effective from 10-Jul-2024. Excluded 100% from leakage and Money at Risk. |
| **Tax Deductions** | Income Tax TDS (Sec 194-O) | **0.1%** | **[Engineering Assumption]** / **[Requires Client Confirmation]** | Statutory e-commerce operator withholding tax. Excluded 100% from leakage and Money at Risk. |
| **Variance Threshold** | Materiality Flagging Threshold | **₹10.00** | **[Confirmed by Brief]** | Variances where $\|Difference\| \le ₹10.00$ are treated as immaterial and classified as `settled`. Variances $> ₹10.00$ are flagged. |
| **Financial Precision** | Precision & Rounding | 2 decimal places (`NUMERIC(12,2)`) | **[Confirmed by Brief]** | Python `Decimal` with `ROUND_HALF_UP` paise precision. Nearest-rupee rounding applied only if contractually mandated by rate card. |
| **Overpayment Policy** | Overpayment Handling | Tagged `overpaid_review`, ₹0 Risk | **[Confirmed by Brief]** | An order where received exceeds expected by $> ₹10.00$ remains `settled` with non-risk reason code `overpaid_review`. |
| **Sample Rate Card 1** | Website COD (`ORD-W-204118`) | Fwd Ship ₹60, COD Fee ₹30 | **[Engineering Assumption]** | Calibrated to yield ₹1,409.00 net expected from ₹1,499.00 gross order value. |
| **Sample Rate Card 2** | Marketplace 1 (`ORD-M-88120`) | Comm 15% (₹179.85), Fix ₹30.15, Ship ₹90 | **[Engineering Assumption]** | Calibrated to yield ₹899.00 net expected from ₹1,199.00 gross order value (deductions total ₹300.00). |
| **Sample Rate Card 3** | Returned D2C (`ORD-W-204377`) | Fwd Ship ₹60, Rev Ship ₹36 | **[Engineering Assumption]** | Calibrated to yield $-₹96.00$ net expected from ₹2,398.00 gross order value (+₹2,398 credit, -₹2,398 refund, -₹60 fwd, -₹36 rev). |
| **Rate Card Interval** | Date Range Semantics | Half-open intervals $[)$ | **[Engineering Assumption]** | `valid_from` is inclusive; `valid_until` is exclusive. Enables seamless transition across consecutive tariffs without overlap collisions. |
| **Worker Architecture** | Background Job Processing | PostgreSQL Transactional Worker | **[Confirmed by Brief]** | Uses `SELECT ... FOR UPDATE SKIP LOCKED` on the `jobs` table with atomic lease renewal, avoiding external broker overhead. |

---

## 3. Data Integrity & Auditing Safeguards

1. **Strictly Immutable Event Ledger:**
   - Table `order_events` is append-only. Triggers block all `UPDATE` and `DELETE` operations.
   - Supersession chains are linear (in-degree $\le 1$) and validated against circular references.
   - Original events establish a lineage lock in `event_lineage_locks` in an `AFTER INSERT` trigger. Subsequent corrections and reversals serialize via `FOR UPDATE` on that lock.
2. **Event Identity vs. Statement Batch Identity:**
   - Statement identity (`canonical_stmt_id`) represents the upload batch envelope (order-independent multiset hash of row fingerprints).
   - Event identity (`idempotency_key`) represents the transaction itself, computed from stable business identifiers:
     $$\text{Scope} = (source\_partner\_id, external\_order\_id, event\_type, fee\_type, partner\_reference, amendment\_ref)$$
   - Mutable values (`amount`, `transaction_date`) are excluded from the identity key.
3. **Courier Tracking Safeguards:**
   - Approved courier mapping rules in `courier_tracking_rules` are immutable.
   - Version activation is tracked in `courier_rule_activations` with a historical audit log in `courier_rule_activation_history`.
   - Every tracking scan records `mapping_rule_id` linking to the exact rule version that evaluated it.
   - The 7-day grace period for `return_not_received` is strictly gated on `verification_outcome = 'verified_dock_delivery'`. Unverified scans never trigger claims.
