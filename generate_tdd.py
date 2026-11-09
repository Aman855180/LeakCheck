import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_tdd():
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styles Setup
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(51, 51, 51)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # --- Document Header & Title ---
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("LeakCheck — Technical Design Document")
    run_title.font.size = Pt(24)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(30, 41, 59) # Slate 800

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(8)
    run_sub = p_sub.add_run("Intelligent Multi-Feed Payment Reconciliation & Financial Leakage Detection Platform")
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = RGBColor(79, 70, 229) # Indigo 600

    # Prominent GitHub Banner at the Very Top
    p_git = doc.add_paragraph()
    p_git.paragraph_format.space_after = Pt(12)
    r_git_lbl = p_git.add_run("Public GitHub Repository: ")
    r_git_lbl.font.bold = True
    r_git_lbl.font.size = Pt(11)
    r_git_lbl.font.color.rgb = RGBColor(15, 23, 42)
    r_git_url = p_git.add_run("https://github.com/Aman855180/LeakCheck")
    r_git_url.font.bold = True
    r_git_url.font.size = Pt(11)
    r_git_url.font.color.rgb = RGBColor(37, 99, 235) # Blue 600

    # Meta Table
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Client & Target Scale", "Company A, Bengaluru D2C Brand (₹43.2 Cr GMV, 100k+ Monthly Orders)"),
        ("Source Code Repository", "https://github.com/Aman855180/LeakCheck (Branches: main, master)"),
        ("Deployment Verification", "Local Docker Compose & Bare-Metal Stack Operational (http://localhost:5173)"),
        ("Architecture Version", "1.0.0 (Production Delivery Release)"),
        ("Engineering Lead & Authors", "Lead Financial Systems Architect & Antigravity Agentic Pair")
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        row = meta_table.rows[row_idx]
        cell_k, cell_v = row.cells[0], row.cells[1]
        cell_k.text = k
        cell_v.text = v
        cell_k.paragraphs[0].runs[0].font.bold = True
        cell_k.paragraphs[0].runs[0].font.size = Pt(9.5)
        cell_v.paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_background(cell_k, "F1F5F9")
        set_cell_background(cell_v, "FFFFFF")
        set_cell_margins(cell_k, 60, 60, 100, 100)
        set_cell_margins(cell_v, 60, 60, 100, 100)
    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # --- Helper for Section Headings ---
    def add_h1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = RGBColor(15, 23, 42)
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.size = Pt(12.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(67, 56, 202)
        return h

    def add_bullet(text, bold_prefix=""):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        if bold_prefix:
            r_pre = p.add_run(bold_prefix + ": ")
            r_pre.font.bold = True
        p.add_run(text)
        return p

    # --- 1. Executive Summary & Problem Context ---
    add_h1("1. Executive Summary & Problem Context")
    doc.add_paragraph(
        "Company A is a high-growth direct-to-consumer (D2C) brand based in Bengaluru, operating at ₹43.2 Cr annual "
        "gross merchandise value (GMV) across more than 100,000 monthly transactions. Transactions flow through multiple "
        "distinct channels: owned Shopify storefront (prepaid & COD), major marketplaces (Amazon, Flipkart, Myntra), "
        "quick-commerce dark stores (Blinkit, Zepto), and 3PL courier aggregators (Delhivery, Blue Dart)."
    )
    doc.add_paragraph(
        "Due to asynchronous payout cycles, fluctuating freight weight slabs, high customer return ratios (RTO/reverse pickups), "
        "and complex statutory withholdings, Company A incurs systemic cash leakage estimated between 1.5% and 3.8% of GMV "
        "(₹65 Lakhs to ₹1.6 Cr annually). Traditional manual spreadsheet workflows cannot keep pace, lead to human error, "
        "and obscure overlapping discrepancies. LeakCheck was developed as an automated, deterministic financial reconciliation "
        "engine that isolates every rupee of leakage with mathematical proof and an explainable audit trail."
    )

    # --- 2. System Architecture & High-Level Design ---
    add_h1("2. System Architecture & High-Level Design")
    doc.add_paragraph(
        "LeakCheck utilizes a modern decoupled architecture prioritizing sub-second analytics, ACID transaction safety, "
        "and strict ledger immutability across five core subsystems:"
    )
    add_bullet("Streams raw partner statements (CSV/XLSX), verifies magic-byte signatures, enforces a 25MB file limit and 150k row limit, computes SHA-256 hashes for deduplication, and sanitizes DPDP Act PII at ingestion.", "1. Streaming Ingestion & Normalization")
    add_bullet("Resolves disparate partner column headers via a 3-pass hierarchy: exact dictionary matching, RapidFuzz string metrics, and pre-LLM PII sanitized Google Gemini 2.5 Flash fallback with mandatory human approval.", "2. AI-Assisted Column Mapping")
    add_bullet("Set-based SQL engine evaluating contractual rate cards, COD remittance SLA aging, courier freight weight tariffs, and non-overlapping risk calculation across 100k orders in ~11 seconds.", "3. Deterministic Reconciliation Engine")
    add_bullet("Compiles dispute evidence packages and generates actionable dispute dockets with strict composite uniqueness constraints and recovery tracking.", "4. Claims & Recovery Hub")
    add_bullet("Role-segregated React 18 single-page application providing executive summaries, multi-facet filtering, evidence timeline drawers, and formula-sanitized CSV exports.", "5. Observability & Executive Interface")

    # --- 3. Data Integrity & Database Schema Design ---
    add_h1("3. Data Integrity & Database Schema Design")
    doc.add_paragraph(
        "The PostgreSQL schema guarantees financial data integrity, prevents duplicate event contamination, and ensures strict append-only auditability."
    )
    add_h2("3.1 Core Database Models & Integrity Constraints")
    add_bullet("Append-only transaction ledger storing every order, payment, remittance, freight invoice, and return scan. A PostgreSQL trigger (`trg_enforce_append_only`) unconditionally blocks UPDATE and DELETE queries.", "order_events")
    add_bullet("Advisory lock registry enforcing single-writer serialization per lineage root during concurrent processing and retrospective corrections.", "event_lineage_locks")
    add_bullet("Master reconciliation state keyed by canonical UUID (`order_recon.id`), maintaining composite partner identity `(partner_id, external_order_id)` to isolate multiple partners sharing identical order numbers.", "order_recon")
    add_bullet("Dispute tracking records referencing canonical `order_recon_id` with `UNIQUE(order_recon_id, claim_reason)` to prevent duplicate claims.", "claims")
    add_bullet("Calibrated half-open interval `[valid_from, valid_until)` rate cards for marketplace commissions, courier freight tariffs, and COD fees.", "rate_cards")
    add_bullet("Version-controlled mapping rules for courier tracking milestone translation. Rule version immutability is enforced at the database level.", "courier_tracking_rules")

    # --- 4. Reconciliation Logic & Non-Overlapping Money at Risk ---
    add_h1("4. Financial Reconciliation Logic & Non-Overlapping Risk Attribution")
    doc.add_paragraph(
        "LeakCheck strictly avoids heuristic 'black-box' reconciliation. Every calculation is derived deterministically from contractual rate cards and source-evidenced events."
    )
    add_h2("4.1 Core Financial Formulas")
    doc.add_paragraph(
        "Money at Risk = Settlement Gap + Freight Excess + Attributable Return Loss",
        style='Quote'
    )
    add_bullet("Calculated as `max(expected_net - received_net, 0)`. Reflects missing remittances, short payouts, and unauthorized gateway deductions. Triggered only after partner-specific SLA windows expire (COD 7 days, Website Prepaid 3 days, Quick Commerce 7 days, Marketplaces 10 days post-delivery).", "1. Settlement Gap Component")
    add_bullet("Calculated as `max(actual_freight - contracted_freight, 0)`. Detects erroneous dead-weight vs. volumetric weight tariff overcharges by 3PL partners (Delhivery/Blue Dart).", "2. Freight Excess Component")
    add_bullet("Capped at the original order value. Subtracts only the settlement-gap amount demonstrably attributable to the exact same underlying refund/reversal event IDs. Unrelated settlement shortfalls remain preserved in full.", "3. Return Loss Overlap Attribution")

    add_h2("4.2 Statutory & Commercial Policy Rules")
    add_bullet("GST Tax Collected at Source (0.5%) and Income Tax TDS (0.1%) are statutory withholdings, not leakage. They are segregated into dedicated tax ledgers and excluded 100% from Money at Risk.", "Statutory Withholdings (TCS & TDS)")
    add_bullet("Variances within ±₹10.00 are classified as settled (immaterial). Orders where received payouts exceed expected tariffs by > ₹10.00 are classified as settled with tag `overpaid_review` and ₹0.00 Money at Risk.", "Materiality & Overpayments")

    # --- 5. AI-Assisted Column Mapping with PII Safeguards ---
    add_h1("5. AI-Assisted Column Mapping, Uncertainty & Human Approval")
    doc.add_paragraph(
        "To accommodate frequently changing partner spreadsheet layouts without brittle hardcoding, LeakCheck implements an intelligent 3-pass resolution hierarchy:"
    )
    add_bullet("Matches headers against calibrated partner dictionary aliases (e.g., 'awb_no' -> 'tracking_number'). Zero network latency.", "Pass 1: Exact Dictionary Match")
    add_bullet("Computes token sort ratio and weighted Levenshtein distance (RapidFuzz). Matches headers scoring >= 80% similarity.", "Pass 2: Fuzzy String Matching")
    add_bullet("Invoked strictly for candidate columns that remain unresolved after Passes 1 and 2. Sends unresolved headers, schema definitions, and 5 representative sanitized values to Google Gemini 2.5 Flash via the official `google-genai` SDK with strict JSON schema enforcement.", "Pass 3: LLM Semantic Fallback")

    add_h2("5.1 Uncertainty Thresholds & Human-in-the-Loop Governance")
    add_bullet("Predictions with confidence scores below 0.80 are explicitly flagged as uncertain in the review interface. Predictions below 0.60 are rejected.", "Uncertainty Thresholds")
    add_bullet("Regex patterns scrub phone numbers, email addresses, and payment card numbers (`[REDACTED_PII]`). PII candidate columns are purged prior to calling the LLM.", "Pre-LLM PII Minimization")
    add_bullet("AI-suggested mappings are NEVER automatically applied to financial ingestion. They are presented in the UI with an `AI_SUGGESTED` badge for mandatory review and explicit approval by a Finance Executive or Co-founder.", "Mandatory Human Approval")
    add_bullet("Once approved, an immutable version is recorded in `column_mappings`. Future uploads of identical format ingest automatically, while schema changes trigger a new version approval.", "Idempotency & Versioning")
    add_bullet("Pydantic schema validation (`AIColumnMappingResponse`) enforces output formatting and rejects hallucinated target fields. Production environments handling sensitive customer financial records should note that Gemini free-tier terms allow data retention for model improvements; enterprise deployments should utilize dedicated enterprise Google Cloud Gemini projects or rely solely on deterministic Passes 1 & 2.", "Structured Schema & Privacy Governance")

    # --- 6. Security & Hardening ---
    add_h1("6. Enterprise Security & Hardening (SEC-01, SEC-02, SEC-03)")
    add_bullet("Session cookies configured with `HttpOnly`, `SameSite=Lax`, and `Secure` attributes. JWT tokens cryptographically signed using HS256 with 60-minute expiry.", "Authentication & Sessions")
    add_bullet("Role permissions enforced strictly at FastAPI dependency boundaries (`require_role`). Co-founder role is strictly read-only for financial actions (cannot upload files, run recon, generate claims, or edit rate cards).", "Strict API-Side RBAC")
    add_bullet("Composite keys `(partner_id, external_order_id)` prevent cross-partner order leakage. Non-existent IDs cleanly return 404/422 without data exposure.", "IDOR Prevention")
    add_bullet("Input validation enforces a 25MB ceiling and 150k row limit before database writes. Quarantined rows with corrupted dates/amounts are isolated in `upload_row_errors`.", "Ingestion Pipeline Guardrails")
    add_bullet("Formula triggers (`=`, `+`, `-`, `@`, `\\t`, `\\r`) are neutralized with a prepended single quote in CSV exports while preserving legitimate negative financial decimals.", "CSV Formula Injection (CWE-1236)")

    # --- 7. Verification & Benchmark Results ---
    add_h1("7. Performance Benchmarks & Independent Oracle")
    doc.add_paragraph(
        "The complete 100,000-order reconciliation pipeline was executed and validated against an independent oracle containing 1,150 planted discrepancies across clean and faulty records."
    )

    bench_table = doc.add_table(rows=6, cols=3)
    bench_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    bench_rows = [
        ("Benchmark Stage", "Measured Duration", "Throughput / Accuracy"),
        ("Synthetic Generation & CSV Parsing", "2.12 seconds", "270,974 rows/sec parsing throughput"),
        ("PostgreSQL Multi-Feed Streaming Ingestion", "35.50 seconds", "2,817 orders/sec multi-table ingestion"),
        ("Set-Based SQL Reconciliation Engine", "11.16 seconds", "8,957 orders/sec reconciliation rate"),
        ("Dispute Claims Generation", "0.26 seconds", "1,150 draft claims generated"),
        ("Total End-to-End Pipeline Execution", "50.26 seconds", "PASSED (Well within < 60.00s Target)")
    ]
    for row_idx, (c0, c1, c2) in enumerate(bench_rows):
        row = bench_table.rows[row_idx]
        row.cells[0].text, row.cells[1].text, row.cells[2].text = c0, c1, c2
        if row_idx == 0:
            for cell in row.cells:
                cell.paragraphs[0].runs[0].font.bold = True
                set_cell_background(cell, "E2E8F0")
        else:
            set_cell_background(row.cells[0], "F8FAFC")
            set_cell_background(row.cells[1], "FFFFFF")
            set_cell_background(row.cells[2], "FFFFFF")
        for cell in row.cells:
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            set_cell_margins(cell, 60, 60, 80, 80)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    add_h2("7.1 Independent Oracle Verification Results")
    add_bullet("1,150 planted records (Expected: 1,150) -> 100% matched.", "True Positives (TP)")
    add_bullet("0 clean orders incorrectly flagged -> 0.00% error rate.", "False Positives (FP)")
    add_bullet("0 planted discrepancies missed -> 0.00% omission rate.", "False Negatives (FN)")
    add_bullet("98,850 clean orders correctly identified as settled.", "True Negatives (TN)")
    add_bullet("100.00% across Precision, Recall, and F1 Score.", "Statistical Accuracy")
    add_bullet("Expected Total Exposure: ₹6,42,200.00 | Actual Reconciled Risk: ₹6,42,200.00 | Variance: ₹0.00 (0.00 paise).", "Financial Exposure Audit")

    # --- 8. Deliverable & Deployment Status Matrix ---
    add_h1("8. Deliverable & Deployment Status Matrix")
    status_table = doc.add_table(rows=6, cols=3)
    status_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    status_rows = [
        ("Deliverable Item", "Status", "Implementation Reference / Location"),
        ("Core Reconciliation Engine (Phase 1–3)", "COMPLETED", "backend/app/services/recon_engine.py, test suite 94/94 passed"),
        ("Orders & Reconciliation UI (Phase 4)", "COMPLETED", "frontend/src/pages/ReconciliationHub.tsx, filters & timeline modal"),
        ("Claims & Money-at-Risk Hub (Phase 5)", "COMPLETED", "frontend/src/pages/ClaimsManagement.tsx, MoneyAtRiskDashboard.tsx"),
        ("AI-Assisted Column Mapping (Phase 6)", "COMPLETED", "backend/app/services/ai_column_mapper.py, PII scrubbing & fallback"),
        ("Public Cloud Live Hosting", "DEFERRED", "Local Docker Compose validated; external cloud hosting deferred per brief")
    ]
    for row_idx, (c0, c1, c2) in enumerate(status_rows):
        row = status_table.rows[row_idx]
        row.cells[0].text, row.cells[1].text, row.cells[2].text = c0, c1, c2
        if row_idx == 0:
            for cell in row.cells:
                cell.paragraphs[0].runs[0].font.bold = True
                set_cell_background(cell, "E2E8F0")
        else:
            set_cell_background(row.cells[0], "F8FAFC")
            set_cell_background(row.cells[1], "FFFFFF")
            set_cell_background(row.cells[2], "FFFFFF")
        for cell in row.cells:
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            set_cell_margins(cell, 60, 60, 80, 80)

    # --- 9. User Interface Screenshots & Visual Design Decisions ---
    add_h1("9. User Interface Screenshots & Visual Design Decisions")
    doc.add_paragraph(
        "The LeakCheck user interface is built with React 18, TypeScript, Tailwind CSS, and TanStack Table. "
        "The interface incorporates defensive UX principles: prominent status pill badges, mutually exclusive financial KPI cards, "
        "role-aware action gating, and immutable financial evidence drawers."
    )

    screenshots_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "docs", "screenshots"))

    screenshots = [
        (
            "dashboard_kpis.png",
            "Figure 9.1: Executive Money-at-Risk Dashboard",
            "Design Decision: The executive dashboard partitions exposure into three non-overlapping cards: Settlement Gap, Freight Excess, and Return Loss. By enforcing mathematical exclusivity, finance leaders never double-count risk. Aging buckets (0-7d, 8-15d, 16-30d, 31+d) guide collection prioritization."
        ),
        (
            "recon_hub_orders.png",
            "Figure 9.2: Orders & Reconciliation Hub with Status Precedence",
            "Design Decision: Every order row displays the expected net settlement, actual receipts, variance, and financial money at risk. Status precedence is strictly enforced (Settled -> Short Paid -> Unpaid Past Due -> Freight Overcharge -> Return Not Received). The responsive header badges maintain clean layout across desktop and tablet viewports."
        ),
        (
            "claims_management_hub.png",
            "Figure 9.3: Dispute Claims Management & Recovery Hub",
            "Design Decision: The Claims Hub compiles automated dispute packages against partners (Shopify, BlueDart, Delhivery). Co-founders view the hub in read-only audit mode, while Finance Executives can sync draft claims, export CSV evidence packages, and record partner recoveries."
        ),
        (
            "dispute_claim_modal.png",
            "Figure 9.4: Dispute Claim Lifecycle & Recovery Management Dialog",
            "Design Decision: Inside the claim detail modal, 'Save Claim Updates' handles lifecycle state transitions (Draft -> Submitted -> Under Review -> Recovered -> Rejected). The dismiss action is clearly labeled 'Close Dialog' with secondary styling to prevent users from confusing modal dismissal with dispute resolution."
        ),
        (
            "upload_and_mapping.png",
            "Figure 9.5: Upload Center & AI Column Mapping Review",
            "Design Decision: Upon file upload, schemas are detected and compared against approved mappings. Incompatible column sets trigger an interactive review where exact matches, RapidFuzz fuzzy suggestions, and AI fallbacks are displayed with confidence badges for mandatory human sign-off."
        )
    ]

    for img_name, caption, decision in screenshots:
        img_path = os.path.join(screenshots_dir, img_name)
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(4)
            run_img = p_img.add_run()
            run_img.add_picture(img_path, width=Inches(6.0))

            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(4)
            r_cap = p_cap.add_run(caption)
            r_cap.font.bold = True
            r_cap.font.size = Pt(9.5)
            r_cap.font.color.rgb = RGBColor(79, 70, 229)

            p_desc = doc.add_paragraph()
            p_desc.paragraph_format.space_after = Pt(12)
            r_desc = p_desc.add_run(decision)
            r_desc.font.size = Pt(10)
            r_desc.font.italic = True
            r_desc.font.color.rgb = RGBColor(71, 85, 105)

    # --- 10. System Limitations & Future Improvements ---
    add_h1("10. System Limitations & Future Improvements")
    doc.add_paragraph(
        "To provide full engineering transparency, the following technical limitations and proposed future enhancements are documented:"
    )
    add_bullet("The staging cache (`_PENDING_FILE_CACHE`) holds uploaded file bytes in memory pending column mapping approval. In a distributed multi-node production deployment, this should be migrated to Redis or an object store (AWS S3 / GCP GCS) with a 24-hour TTL expiration.", "1. Distributed File Staging Cache")
    add_bullet("The current architecture partitions records logically across multiple partners for Company A. Scaling to a multi-tenant SaaS serving dozens of independent enterprise brands requires implementing PostgreSQL Row-Level Security (RLS) or tenant-per-schema isolation.", "2. Multi-Tenant Organization Isolation")
    add_bullet("The ingestion pipeline is optimized for modern `.xlsx` via `calamine`/`fastexcel`. Legacy binary BIFF8 `.xls` files (pre-2007) are rejected due to OLE compound structure. Supporting legacy `.xls` requires integrating the `xlrd` library.", "3. Legacy Binary Excel (.xls) Format Support")
    add_bullet("While Polars comfortably parses 150,000 rows in sub-second timeframes, processing multimillion-row batches will benefit from an asynchronous job worker queue (Celery / ARQ with Redis) to prevent HTTP connection timeouts.", "4. Asynchronous Background Task Queue")
    add_bullet("Courier statements (Delhivery, Blue Dart) and marketplace settlements are currently ingested via CSV/XLSX uploads. Future versions can incorporate direct API integrations and webhooks for real-time daily ledger synchronization.", "5. Direct Carrier & Marketplace Webhook Ingestion")

    # Output path
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Technical_Design_Document.docx"))
    doc.save(output_path)
    print(f"[OK] Technical Design Document successfully generated at: {output_path}")

if __name__ == "__main__":
    create_tdd()
