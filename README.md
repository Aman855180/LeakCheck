# LeakCheck — Intelligent Payment Reconciliation & Financial Leakage Detection

[![Tests](https://img.shields.io/badge/pytest-106%20passed-brightgreen.svg)](backend/tests)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](backend)
[![React](https://img.shields.io/badge/react-18.3-blue.svg)](frontend)
[![TypeScript](https://img.shields.io/badge/typescript-5.5-blue.svg)](frontend)
[![PostgreSQL](https://img.shields.io/badge/postgresql-16%2B-blue.svg)](docker-compose.yml)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](#)

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
- **Append-Only Immutable Event Ledger:** All raw ingested transactions are preserved with cryptographic hashes (`sha256_hash`). Reversals and adjustments are recorded as new immutable events.
- **Multi-Partner Composite Identity:** Eliminates collision risk when multiple platforms use colliding order identifiers (`ORD-101` on Shopify vs. `ORD-101` on Amazon) by keying on `(partner_id, external_order_id)`.
- **Pre-LLM PII Sanitization (DPDP Act 2023):** Column mapping fallback strips names, emails, and phone numbers before fuzzy or LLM fallback processing.

---

## 3. Tech Stack

- **Backend:** FastAPI (Python 3.11+ / 3.13), SQLAlchemy 2.0 ORM, Alembic migrations, Psycopg 3 streaming driver, Pydantic v2.
- **Reconciliation Engine:** Pure in-memory vectorized calculations using high-precision `Decimal` arithmetic.
- **Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS, TanStack Table & Lucide Icons.
- **Database:** PostgreSQL 16+ with ACID advisory locks, partial indexes, and window analytics.
- **Column Mapping:** RapidFuzz token matching + Google Gemini 2.5 Flash fallback.

---

## 4. Quick Start

### Option A: Local Bare-Metal Setup

#### 1. Backend Setup
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt

# Run migrations & seed data
alembic upgrade head
python -m app.seeds.seed_all

# Start backend server (port 8000)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
# App will be accessible at http://localhost:5173
```

### Option B: Docker Compose
```bash
docker compose up -d --build
```

---

## 5. Verification & Testing

The backend includes a comprehensive 106-test regression suite covering:
- Ingestion idempotent hashing & quarantine
- Dynamic column mapping & version approval triggers
- Rate card fee calculations (marketplace, COD, courier freight tariffs)
- Three-way reconciliation engine & status precedence
- Claims lifecycle, duplicate prevention, and CSV evidence packages
- Role-based access control (RBAC: `finance_exec` vs `cofounder`)

Run the test suite:
```bash
cd backend
python -m pytest tests/ -v
```
**Result:** `106 passed, 1 skipped` (mocked unit tests passing, real API integration test conditionally skipped without API key).

---

## 6. Default Demo Credentials

| Role | Username / Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Finance Executive** | `finance_exec@company-a.com` | `FinanceExec#2026` | Full upload, rate-card creation, claims resolution |
| **Co-Founder** | `cofounder@company-a.com` | `CoFounder#2026` | Executive dashboard, read-only audit & approvals |

---

## 7. Project Documentation

- [Deployment & Operations Guide](deployment.md)
- [Technical Design Document (DOCX)](Technical_Design_Document.docx)
- [Database Migrations](backend/migrations/)
- [Sample Input Feeds](sample_files/)
