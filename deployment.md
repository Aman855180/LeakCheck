# LeakCheck — Deployment & Operations Guide

**Platform:** LeakCheck — Intelligent Payment Reconciliation & Financial Leakage Detection
**Client Scenario:** Company A, Bengaluru D2C Brand (₹43.2 Cr GMV)
**System Version:** `1.0.0 (Release Candidate / Staging Ready)`
**GitHub Repository:** [https://github.com/Aman855180/LeakCheck](https://github.com/Aman855180/LeakCheck)

---

## 1. System Overview & Architecture

LeakCheck is an automated, multi-feed financial reconciliation engine engineered to detect revenue leakage across e-commerce marketplaces (Amazon, Flipkart, Myntra), quick commerce (Blinkit, Zepto), and logistics partners (Delhivery, Blue Dart).

### Core Components
- **Backend API:** FastAPI (Python 3.11+ / 3.13) with asynchronous endpoints, SQLAlchemy 2.0 ORM, Alembic migrations, and Psycopg 3 streaming driver.
- **Frontend SPA:** React 18, TypeScript, Tailwind CSS, Lucide icons, Vite 5, TanStack Table & Query.
- **Database:** PostgreSQL 16+ with ACID append-only event lineage, advisory locking, composite partner keys, and SQL window analytics.
- **Mapping & AI Engine:** Exact dictionary + RapidFuzz fuzzy matcher with Google Gemini 2.5 Flash fallback via official `google-genai` SDK (with pre-LLM PII scrubbing, structured schema enforcement, and mandatory human approval).
- **Supported Statement Formats:** `.csv` (text/csv) and `.xlsx` (OpenXML Spreadsheet) with magic-byte validation. Legacy `.xls` (pre-2007 BIFF8) is explicitly rejected with HTTP 400 `UNSUPPORTED_FORMAT`.

---

## 2. Prerequisites & System Requirements

- **Operating System:** Linux (Ubuntu 22.04+ recommended), macOS, or Windows 10/11
- **Python:** 3.11, 3.12, or 3.13
- **Node.js:** v18.x or v20.x+ (npm 9+)
- **PostgreSQL:** Version 15 or 16+
- **Docker & Docker Compose:** Optional for containerized deployment (Engine 24.0+, Compose v2.20+)

---

## 3. Environment Variables

Create `.env` in the root directory (or in `backend/` and `frontend/` respectively). In accordance with security standards, only environment variable names and descriptions are listed below (no secrets, credentials, or actual values):

| Variable Name | Required | Purpose & Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | Application execution mode (`development`, `production`, `test`) |
| `LOG_LEVEL` | Yes | Logging verbosity level (`INFO`, `DEBUG`, `WARNING`, `ERROR`) |
| `SECRET_KEY` | Yes | Secret cryptographic key used to sign session JWTs |
| `JWT_ALGORITHM` | Yes | JWT cryptographic algorithm (e.g., `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Lifetime of session tokens in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Yes | Lifetime of refresh tokens in days |
| `POSTGRES_USER` | Yes | Username for PostgreSQL database connection |
| `POSTGRES_PASSWORD` | Yes | Password for PostgreSQL database connection |
| `POSTGRES_HOST` | Yes | Hostname or IP address of the PostgreSQL database server |
| `POSTGRES_PORT` | Yes | Port of the PostgreSQL database server |
| `POSTGRES_DB` | Yes | Name of the PostgreSQL database |
| `DATABASE_URL` | Yes | Full SQLAlchemy database connection URI |
| `ALLOWED_ORIGINS` | Yes | Comma-separated list of allowed CORS client origins |
| `DEFAULT_AS_OF_DATE` | Yes | Baseline reconciliation reference date (e.g., `2026-11-01`) |
| `GEMINI_API_KEY` | Optional | API key for AI fallback column mapping (Google Gemini 2.5 Flash) |
| `GEMINI_MODEL` | Optional | Model identifier for Google Gemini fallback (default: gemini-2.5-flash) |

---

## 4. Local / Bare-Metal Deployment Steps

### Step 1: Database Setup
1. Ensure the PostgreSQL service is active:
   ```bash
   # Linux / macOS
   sudo systemctl start postgresql

   # Windows PowerShell
   Start-Service postgresql-x64-16
   ```
2. Create database and user:
   ```sql
   CREATE USER postgres WITH PASSWORD 'postgres';
   CREATE DATABASE leakcheck OWNER postgres;
   GRANT ALL PRIVILEGES ON DATABASE leakcheck TO postgres;
   ```

### Step 2: Backend Setup & Migrations
1. Navigate to `backend`:
   ```bash
   cd backend
   python -m venv venv

   # Linux / macOS
   source venv/bin/activate
   # Windows PowerShell
   .\venv\Scripts\Activate.ps1
   ```
2. Install Python dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Run Alembic Database Migrations:
   ```bash
   alembic upgrade head
   ```
4. Seed Master Data (Users, Rate Cards, Partners, Sources):
   ```bash
   python -m app.db.seed
   ```
5. Start Backend Server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   Backend will be operational at `http://127.0.0.1:8000`. Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

### Step 3: Frontend Setup
1. Open a new terminal and navigate to `frontend`:
   ```bash
   cd frontend
   npm install
   ```
2. Start Development Server:
   ```bash
   npm run dev
   ```
   Frontend will be accessible at `http://localhost:5173`.

---

## 5. Docker Compose Deployment (Alternative)

For fully containerized, reproducible deployment:
```bash
docker compose up -d --build
```
This automatically spins up:
- PostgreSQL 16 on port 5432
- FastAPI backend on port 8000
- React frontend on port 5173

---

## 6. Tested Demo Login Credentials

The following pre-configured demo user accounts are seeded and tested:

| Role | Email / Username | Password | Permissions & Scope |
| :--- | :--- | :--- | :--- |
| **Finance Executive** | `finance_exec@company-a.com` | `Password123!` | Full administrative capabilities: file uploads, rate-card creation, claims resolution, recovery recording, mapping approval |
| **Co-founder** | `cofounder@company-a.com` | `Password123!` | Read-only audit mode: executive dashboard, reconciliation orders ledger, claims review, mapping approval, CSV report exports |

---

## 7. Operational Verification & Testing

### Backend Test Suite
Run the complete regression and AI fallback test suite:
```bash
cd backend
python -m pytest tests/ -v
```
**Expected Result:** `106 passed, 1 skipped` (the real API call test is skipped when `GEMINI_API_KEY` is not provided, with 14 mocked unit tests fully validating client initialization, PII scrubbing, schema validation, confidence thresholds, error handling, rate limits, and timeouts).

### Frontend Build Verification
Verify production TypeScript compilation:
```bash
cd frontend
npm run build
```
**Expected Result:** Clean compilation with `0 errors`.

---

## 8. Ingestion & Security Safeguards

- **Supported Ingestion Formats:** `.csv` and `.xlsx` only. Legacy `.xls` uploads are rejected with HTTP 400 `UNSUPPORTED_FORMAT`.
- **Upload Size & Row Limits:** Enforced 25 MB max upload limit and 150,000 row limits per statement file.
- **CSV Formula Injection Sanitization:** Exported CSV files automatically neutralize dangerous spreadsheet formula triggers (`=`, `+`, `-`, `@`) even when preceded by whitespace or control characters, while strictly preserving negative numbers and legitimate currency values.
- **XLSX Decompression Protection:** Calamine/fastexcel streaming parser handles standard OpenXML workbooks. For production hardening against malicious compression ratios, host container memory quotas (e.g. Docker `mem_limit: 1g`) should be enforced.


---

## 9. AI Column Mapping & Data Privacy (Google Gemini)

LeakCheck implements a three-tier column mapping architecture:
1. **Pass 1 — Exact Dictionary:** Instant deterministic matching against known canonical aliases (O(1)).
2. **Pass 2 — RapidFuzz Similarity:** Token sort and normalized ratio matching (threshold >= 80).
3. **Pass 3 — Google Gemini Semantic Fallback:** Invokes Google Gemini 2.5 Flash via the official `google-genai` SDK (`gemini-2.5-flash`) exclusively for remaining unresolved fields.

### Privacy, PII Scrubbing & Security
- **Strict Pre-LLM Sanitization:** `sanitize_columns_and_samples` drops all known customer PII fields (customer names, recipient details, addresses) and scrubs phone numbers (`+91...`), email addresses, and payment card numbers from cell samples before payload dispatch.
- **Strict Structured Outputs:** Uses Pydantic schema validation (`AIColumnMappingResponse`) to enforce strict type constraints and disallow hallucinated canonical fields.
- **Confidence Scoring & Approval:** Suggestions with confidence < 0.60 are rejected. Suggestions between 0.60 and 0.80 are marked with `uncertain: True` ("AI Review Required"). All AI suggestions require mandatory human approval by a Finance Executive or Co-founder before staging or committing.
- **Free-Tier Data Handling Notice:** Google Gemini's free tier terms may permit data usage for model improvements. Production environments handling sensitive financial records should configure a paid/enterprise Google Cloud Gemini API key with enterprise privacy terms, or operate purely using deterministic Pass 1 & Pass 2 matching.
