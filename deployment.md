# LeakCheck — Deployment & Operations Guide

**Platform:** LeakCheck — Intelligent Payment Reconciliation & Financial Leakage Detection  
**Client Scenario:** Company A, Bengaluru D2C Brand (₹43.2 Cr GMV)  
**System Version:** `1.0.0 (Production Delivery)`

---

## 1. System Overview & Architecture

LeakCheck is an automated, multi-feed financial reconciliation engine engineered to detect revenue leakage across e-commerce marketplaces (Amazon, Flipkart, Myntra), quick commerce (Blinkit, Zepto), and logistics partners (Delhivery, Blue Dart).

### Core Components
- **Backend API:** FastAPI (Python 3.13 / 3.11) with asynchronous endpoints, SQLAlchemy 2.0 ORM, Alembic migrations, and Psycopg 3 streaming driver.
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

Create `.env` in the root directory (or in `backend/` and `frontend/` respectively):

```ini
# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# Security & Session Authentication
SECRET_KEY=your-secure-random-secret-key-at-least-32-chars-long
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database Connection (PostgreSQL)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=leakcheck
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/leakcheck

# CORS Allowed Origins
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173

# Baseline Reconciliation Date
DEFAULT_AS_OF_DATE=2026-11-01

# AI Fallback Column Mapping (Anthropic Claude - Optional)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

---

## 4. Local / Bare-Metal Deployment Steps

### Step 1: Database Setup
1. Ensure PostgreSQL service is active:
   ```bash
   # Linux / macOS
   sudo systemctl start postgresql
   
   # Or Windows PowerShell
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
   # Linux/macOS:
   source venv/bin/activate
   # Windows:
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
4. Seed Initial Data (demo accounts & rate cards):
   ```bash
   python init_db.py
   ```
5. Launch FastAPI Backend Server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

### Step 3: Frontend Setup
1. Navigate to `frontend`:
   ```bash
   cd frontend
   npm ci
   ```
2. Build for production:
   ```bash
   npm run build
   ```
3. Run in development or preview mode:
   ```bash
   # Development server:
   npm run dev
   # Or serve production build:
   npm run preview -- --port 5173 --host
   ```

---

## 5. Docker Compose Deployment

Run the complete stack (PostgreSQL, Backend API, and Nginx SPA) in one command:

```bash
docker-compose up -d --build
```

### Container Status Verification:
```bash
docker-compose ps
docker-compose logs -f backend
```

- **Frontend Application:** `http://localhost:5173`
- **Backend API & Swagger Docs:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432`

---

## 6. Seeded Demo Accounts & RBAC Matrix

The system includes pre-configured RBAC accounts for review and evaluation:

| Account Role | Email | Password | Allowed Permissions |
| :--- | :--- | :--- | :--- |
| **Finance Executive** | `finance_exec@company-a.com` | `FinanceExec123!` | Full Access: Multi-feed file uploads, column mapping approvals, rate-card calibration, running reconciliation, batch generating claims, updating claim statuses, recording recovery amounts. |
| **Finance Co-founder** | `cofounder@company-a.com` | `Cofounder123!` | Read-Only Audit: View Executive Dashboard, inspect reconciled orders and tariffs, view claims & dispute dockets, download evidence CSVs. Cannot modify rate cards, trigger reconciliation, or edit claims. |

*Note: For testing, the login screen includes One-Click Quick Sign-In buttons for both accounts.*

---

## 7. Verification & Benchmark Execution

### 1. Run Complete Backend Test Suite (89 Tests)
```bash
cd backend
python -m pytest tests/ -v
```

### 2. Run Frontend Smoke Tests
```bash
cd frontend
npm test
```

### 3. Run 100,000-Order Production Benchmark & Oracle
```bash
cd backend
python -u benchmark/run_100k_benchmark.py
```
**Measured Results (Windows 11 / AMD Ryzen):**
- **100,000 CSV Orders Streaming Ingestion:** 35.50 seconds (2,817 orders/sec)
- **Set-Based SQL Reconciliation:** 11.16 seconds (8,957 orders/sec)
- **Draft Claims Generation:** 0.26 seconds (1,150 claims)
- **Total Pipeline Execution:** 50.26 seconds (< 60.00s threshold)
- **Independent Oracle Precision / Recall:** 100.00% / 100.00% (Zero false positives, zero false negatives)

---

## 8. Operational Safeguards & Security Checklist

1. **Session Cookies & CSRF Protection:** Authentication uses `HttpOnly`, `SameSite=Lax` cookies with cryptographically signed tokens.
2. **Formula Injection (CWE-1236):** CSV exports pass through `sanitize_csv_cell`, escaping formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) while preserving legitimate negative numeric values (`-150.00`).
3. **Data Loss Prevention:** Audit events and line-item events are append-only; reversal events reference original lineage roots with advisory concurrency locking.
4. **PII Sanitization:** Uploaded customer data (phone, email, PAN) is masked before optional LLM mapping fallback.

---

## 9. Troubleshooting & FAQ

- **Database Connection Refused:** Ensure PostgreSQL is running on the port configured in `.env` (`5432` or `5433`). Check `pg_isready`.
- **Alembic Migration Error:** If migrating an existing database, ensure `alembic upgrade head` is executed; migration `002` safely backfills existing order claims without loss.
- **Frontend Port Conflict:** Vite defaults to port `5173`. If unavailable, pass `--port <PORT>` or update `vite.config.ts`.
- **LLM Mapping Fallback:** If `ANTHROPIC_API_KEY` is not provided, the platform operates in 100% deterministic mode using exact alias dictionary and RapidFuzz matching.
