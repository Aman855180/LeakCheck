# LeakCheck — Deployment & Operations Guide

**Platform:** LeakCheck — Intelligent Payment Reconciliation & Financial Leakage Detection  
**Client Scenario:** Company A, Bengaluru D2C Brand (₹43.2 Cr GMV)  
**System Version:** `1.0.0 (Production Delivery)`  
**GitHub Repository:** [https://github.com/Aman855180/LeakCheck](https://github.com/Aman855180/LeakCheck)

---

## 1. System Overview & Architecture

LeakCheck is an automated, multi-feed financial reconciliation engine engineered to detect revenue leakage across e-commerce marketplaces (Amazon, Flipkart, Myntra), quick commerce (Blinkit, Zepto), and logistics partners (Delhivery, Blue Dart).

### Core Components
- **Backend API:** FastAPI (Python 3.11+ / 3.13) with asynchronous endpoints, SQLAlchemy 2.0 ORM, Alembic migrations, and Psycopg 3 streaming driver.
- **Frontend SPA:** React 18, TypeScript, Tailwind CSS, Lucide icons, Vite 5, TanStack Table & Query.
- **Database:** PostgreSQL 16+ with ACID append-only event lineage, advisory locking, composite partner keys, and SQL window analytics.
- **Mapping & AI Engine:** Exact dictionary + RapidFuzz fuzzy matcher with Anthropic Claude 3.5 Sonnet fallback (with pre-LLM PII scrubbing).

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
| `ANTHROPIC_API_KEY` | Optional | API key for AI fallback column mapping (Claude 3.5 Sonnet) |
| `ANTHROPIC_MODEL` | Optional | Model identifier for Anthropic Claude fallback |

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
Run the 94-test regression suite covering authentication, RBAC, ingestion, rate cards, and reconciliation:
```bash
cd backend
python -m pytest tests/ -v
```
**Expected Result:** `94 passed, 0 failures`.

### Frontend Build Verification
Verify production TypeScript compilation:
```bash
cd frontend
npm run build
```
**Expected Result:** Clean compilation with `0 errors`.
