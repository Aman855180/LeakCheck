# LeakCheck — Intelligent Payment Reconciliation & Financial Leakage Detection

[![Tests](https://img.shields.io/badge/pytest-116%20passed-brightgreen.svg)](backend/tests)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](backend)
[![React](https://img.shields.io/badge/react-18.3-blue.svg)](frontend)
[![TypeScript](https://img.shields.io/badge/typescript-5.5-blue.svg)](frontend)
[![PostgreSQL](https://img.shields.io/badge/postgresql-16%2B-blue.svg)](docker-compose.yml)
[![Repository](https://img.shields.io/badge/github-Aman855180%2FLeakCheck-blue.svg)](https://github.com/Aman855180/LeakCheck)

---

## 1. Executive Summary

**LeakCheck** is an intelligent, high-throughput payment reconciliation and financial leakage detection engine built for **Company A** (Bengaluru-based D2C brand operating at ₹43.2 Cr GMV across Shopify, marketplaces, quick commerce, and national courier networks).

The platform ingests heterogeneous transactional feeds across 5 sources:
1. **Sales Orders** (Shopify, Amazon, Flipkart, Blinkit, Zepto)
2. **Payment Gateway & Marketplace Settlements** (Razorpay, Cashfree, Amazon Pay, Flipkart Settlement)
3. **Logistics Courier Invoices** (Delhivery, BlueDart, Shadowfax)
4. **COD Remittance Advices** (Cash on delivery collections)
5. **Warehouse Returns & Receipts** (WMS dock acknowledgments)

LeakCheck matches transactions deterministically against contractually calibrated rate cards, isolates every rupee of financial exposure, and automatically compiles dispute-ready claim packages with complete evidentiary audit trails.

---

## 2. Core Architectural Guarantees

- **Mutually Exclusive Leakage Partitioning (Zero Double Counting):** Financial exposure is rigorously partitioned into non-overlapping buckets:
  $$\text{Money at Risk} = \text{Settlement Gap} + \text{Freight Excess} + \text{Return Loss}$$
- **Statutory Tax Ledger Isolation:** GST TCS (0.5% IGST / 0.25% CGST+SGST) and Income Tax TDS u/s 194-O (0.10%) are segregated into dedicated tax accounts and never flagged as leakage.
- **Append-Only Immutable Event Ledger:** All raw ingested transactions are preserved with cryptographic hashes (`file_hash` / row fingerprints). Reversals and adjustments are recorded as new immutable events.
- **Multi-Partner Composite Identity:** Eliminates collision risk when multiple platforms use colliding order identifiers (`ORD-101` on Shopify vs. `ORD-101` on Amazon) by keying on `(partner_id, external_order_id)`.
- **Pre-LLM PII Sanitization (DPDP Act 2023):** Column mapping fallback strips names, emails, addresses, and phone numbers before fuzzy or LLM fallback processing.

---

## 3. Tech Stack

- **Backend:** FastAPI (Python 3.11+ / 3.13), SQLAlchemy 2.0 ORM, Alembic migrations, Psycopg 3 streaming driver, Pydantic v2.
- **Reconciliation Engine:** Pure in-memory vectorized calculations using high-precision `Decimal` arithmetic.
- **Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS, TanStack Table & Lucide Icons.
- **Database:** PostgreSQL 16+ with ACID advisory locks, partial indexes, and window analytics.
- **Column Mapping:** RapidFuzz token matching (70% runtime acceptance threshold) + Google Gemini fallback via official `google-genai` SDK with 30,000ms timeout and strict JSON schema enforcement.

---

## 4. Quick Start

### Local Bare-Metal Setup (Verified)

#### 1. Backend Setup
```bash
cd backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt

# Run migrations & seed master data
alembic upgrade head
python -m app.db.seed

# Start backend server (port 8000)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Backend will be operational at `http://127.0.0.1:8000`. Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend will be accessible at `http://localhost:5173`.

### Docker Compose Deployment (Alternative)
```bash
docker compose up -d --build
```
> **Note:** Public cloud live hosting is not deployed for this release; local bare-metal and Docker Compose environments have been fully tested and verified.

---

## 5. Tested Demo Credentials (Demo-Only)

> **Important:** The credentials below are pre-configured, tested demo accounts for local evaluation only. Do not use in production.

| Role | Username / Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Finance Executive** | `finance_exec@company-a.com` | `Password123!` | Full upload, rate-card creation, claims resolution, mapping approval |
| **Co-Founder** | `cofounder@company-a.com` | `Password123!` | Executive dashboard, read-only audit & approvals, CSV exports |

---

## 6. Three-Tier Column Mapping Architecture

LeakCheck employs a resilient three-tier column mapping hierarchy:

1. **Pass 1 — Exact Dictionary:** Instant deterministic matching against known canonical aliases (O(1)).
2. **Pass 2 — RapidFuzz Similarity:** Token sort and normalized ratio matching with a **70% runtime acceptance threshold**. Fuzzy matches scoring between 70% and below 80% are accepted as candidate suggestions but remain flagged with confidence < 0.80 for mandatory human review in the UI.
3. **Pass 3 — Google Gemini Semantic Fallback:** Invokes Google Gemini (configurable via `GEMINI_MODEL`, e.g. `gemini-3.5-flash`) via the official `google-genai` SDK with a 30,000ms HTTP timeout exclusively for remaining unresolved fields.

### Privacy, Governance & Resilience
- **Mandatory Human Approval:** AI column mapping suggestions are **never** auto-committed or auto-ingested. A Finance Executive or Co-founder must explicitly review and approve mappings before any workbook can be ingested.
- **PII Scrubbing:** All customer personal data (names, emails, phone numbers, delivery addresses) is stripped prior to LLM dispatch.
- **Quota & Timeout Resilience:** If the Gemini API encounters rate limits (HTTP 429), quota exhaustion, or request timeouts, it gracefully falls back to deterministic matching. Existing RapidFuzz matches are safely preserved while remaining unresolved fields are left unmapped for manual assignment.

---

## 7. Verification & Testing

### Backend Test Suite
Run the 117-test regression suite covering authentication, RBAC, ingestion, rate cards, reconciliation, and AI fallback:
```bash
cd backend
python -m pytest tests/ -v
```
**Expected Result:** `116 passed, 1 skipped` (the real API call test is skipped when `GEMINI_API_KEY` is not provided, with 16 unit tests fully validating client initialization, PII scrubbing, schema validation, confidence thresholds, error handling, rate limits, and timeouts).

### Frontend Test Suite & Build Verification
```bash
cd frontend
npm test -- --run
npm run build
```
**Expected Result:** `10 passed (100%)`, Vite production build completed with `0 errors`.

---

## 8. Technical Design & Repository

- **Public GitHub Repository:** [https://github.com/Aman855180/LeakCheck](https://github.com/Aman855180/LeakCheck)
- **Deployment & Operations Guide:** [deployment.md](deployment.md)
- **Technical Design Document (DOCX):** [Technical_Design_Document.docx](Technical_Design_Document.docx)
- **Database Migrations:** [backend/migrations/](backend/migrations/)

---

## 9. Known System Limitations & Future Scope

- **Asynchronous Task Queue:** Processing very large statement files (>150,000 rows) would benefit from an asynchronous worker queue (Celery/ARQ with Redis) to prevent client HTTP timeouts during file upload.
- **Multi-Tenant SaaS Isolation:** The platform currently provides logical partner partitioning for Company A. Enterprise multi-tenancy requires PostgreSQL Row-Level Security (RLS) or tenant-per-schema isolation.
- **Gemini Free-Tier Rate Limits:** The Google Gemini free tier enforces strict per-minute request limits (HTTP 429). Production environments should configure a paid Google Cloud Vertex AI / Gemini key or rely on deterministic Passes 1 & 2.
- **Direct Carrier API Webhooks:** Future milestones can integrate direct carrier tracking webhooks (Delhivery, BlueDart) to eliminate manual CSV/XLSX statement uploads.
