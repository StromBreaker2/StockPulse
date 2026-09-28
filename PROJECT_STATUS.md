# StockPulse — Project Implementation Status

**Project**: StockPulse — AI Inventory & Dynamic Pricing Engine  
**Last Updated**: Current Active Build  
**Maintainer**: Lead Developer  

---

## 1. Implemented

- [x] **FastAPI REST API Backend**:
  - `/health` status check
  - Product catalog CRUD (`POST /products`, `GET /products`, `GET /products/{id}`)
  - Direct stock update (`PATCH /products/{id}/stock`)
  - Order simulation (`POST /products/{id}/orders`)
  - On-demand suggestions (`POST /products/{id}/suggest-pricing`, `POST /products/{id}/suggest-reorder`)
  - Pending recommendations query (`GET /suggestions/pending`)
  - Human approval workflow (`PATCH /pricing-suggestions/{id}`, `PATCH /reorder-suggestions/{id}`)
  - Strategy inspection and switching (`GET /settings/strategy`, `PATCH /settings/strategy`)
- [x] **SQLAlchemy 2.0 ORM & Neon PostgreSQL**:
  - Models for `Product`, `PricingSuggestion`, `ReorderSuggestion` with native relationship cascade bindings
  - Portable enum handling for PostgreSQL and SQLite
  - Automatic table generation and initial 8-product seeding on application launch
  - Safe database URL normalization (`postgresql://` -> `postgresql+psycopg://`) and credential protection
- [x] **Signal & Trigger Detectors**:
  - `INVENTORY_LOW`: Fires when `stock_level < reorder_threshold`
  - `DEMAND_SPIKE`: Dynamic calculation comparing `demand_velocity` against category average `func.avg()` with configurable multiplier (`DEMAND_SPIKE_MULTIPLIER`)
- [x] **Strategy Pattern**:
  - `CommerceAdvisor` interface
  - `RuleBasedAdvisor`: Deterministic 10% scarcity markup, 5% demand surge markup, buffer stock reorder calculation
  - `AIAdvisor`: Asynchronous OpenAI-compatible Zycus LLM integration (`qwen-cursor`)
  - `AIAdvisorManager`: Runtime strategy switching without application restarts
- [x] **Robust AI Validation & Fallback**:
  - Schema extraction from pure JSON, markdown fences, or text
  - Upper/lower bound checks on recommended price (<= 2x current price, > 0)
  - Automatic fallback to `RuleBasedAdvisor` on network timeouts, missing API keys, HTTP errors, or validation exceptions
- [x] **Duplicate Prevention**:
  - Suppression of duplicate `PENDING` suggestions for the same product, trigger reason, and suggestion type
- [x] **React 18 Dashboard**:
  - Product catalog table with real-time stock levels, demand velocity, and status badges
  - Strategy selector dropdown in header
  - Pending Human Approvals card deck displaying paired pricing and reorder suggestions with confidence and reasoning
  - One-click **Accept Price**, **Reject Price**, **Accept Reorder**, **Reject Reorder** buttons
  - Real-time auto-polling every 3 seconds
  - Built with Vite and plain CSS for clean styling
- [x] **Automated Pytest Suite**:
  - 20 unit and integration tests covering the complete domain logic, API routes, strategy execution, AI validation, and approval transitions

---

## 2. Working & Verified

- **Backend Startup & Auto-Seeding**: Successfully boots and populates initial 8 products (`PRD-001` through `PRD-008`).
- **Order Simulation & Background Tasks**: `POST /products/{id}/orders` decrements stock, raises demand velocity, schedules background task, and returns immediately (<20ms).
- **Signal Triggers**: Both `INVENTORY_LOW` and `DEMAND_SPIKE` reliably trigger suggestion creation.
- **Rule-Based Engine**: Accurately computes 10% price markup on low stock and target buffer replenishment quantities.
- **AI Advisor with Fallback**: Transparently provides valid recommendations via rule fallback when LLM keys are absent, ensuring continuous operations.
- **Human Approval State Machine**: `ACCEPT` updates product price or increments stock; `REJECT` leaves product unchanged; suggestions cannot be re-decided once resolved.
- **Frontend Dashboard Build**: `npm run build` succeeds in <1s producing optimized production assets.
- **Test Suite**: 20/20 tests passing via `python -m pytest -v`.

---

## 3. Known Issues / Limitations

- **Background Tasks**: FastAPI `BackgroundTasks` executes in-memory. If the server process crashes while a task is queued, that specific run is lost. (For enterprise scaling, migrate to Celery/Kafka).
- **Authentication**: Intentionally omitted per hackathon scope to simplify pairing and judging review.
- **Single Currency**: All prices are formatted in USD ($).

---

## 4. Architecture Summary

```
[Merchandiser React UI]
        │
    REST / Axios (Proxy /api -> :8000)
        ▼
[FastAPI Server :8000] ──► [Neon PostgreSQL (SQLAlchemy 2.0 + Psycopg 3)]
        │
   (Order Event)
        ▼
[Signal Detection] ──► [FastAPI BackgroundTasks] ──► [CommerceAdvisor]
                                                           ├── AIAdvisor (Zycus LLM)
                                                           └── Fallback: RuleBasedAdvisor
                                                                   │
                                                                   ▼
                                                     [Persist PENDING Suggestions]
                                                                   │
                                                                   ▼
                                                     [Merchandiser Accept / Reject]
```

---

## 5. Environment Variables

Store in `backend/.env`:

| Variable | Description | Example / Default |
|---|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection URI | `postgresql://user:pass@ep-host.neon.tech/neondb?sslmode=require` |
| `LLM_API_KEY` | Zycus / LiteLLM API Key | `your_api_key_here` |
| `LLM_BASE_URL` | Base URL for LLM completions | `https://litellm-qc.zycus.net/v1` |
| `LLM_MODEL` | LLM model identifier | `qwen-cursor` |
| `LLM_PRODUCT` | Product identifier header | `PC1` |
| `LLM_COOKIE` | Optional session cookie | `""` |
| `DEMAND_SPIKE_MULTIPLIER` | Velocity threshold multiplier | `3.0` |
| `DEFAULT_STRATEGY` | Active advisor on boot | `AI` |

---

## 6. How to Run

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Web UI: `http://localhost:5173`

### Run Tests

```bash
cd backend
python -m pytest -v
```

---

## 7. Recommended Demo Steps (5-Minute Walkthrough)

1. **Open Dashboard**: Navigate to `http://localhost:5173`.
2. **Review Initial Catalog**:
   - Point out **PRD-003: Organic Cotton T-Shirt** with Stock = 8, Reorder Threshold = 15.
   - Note that no pending recommendations exist initially.
3. **Simulate Customer Sale**:
   - Click **Simulate Sale** next to PRD-003.
   - Stock decrements to 7 (triggering `7 < 15` -> `INVENTORY_LOW`).
4. **Observe Reactive Recommendations**:
   - Within 1-2 seconds, two cards appear under **Pending Human Approvals**:
     1. **Pricing Recommendation**: Suggests raising price from \$24.99 to \$27.49 with business justification to throttle demand and protect scarce inventory.
     2. **Replenishment Order**: Suggests reordering +38 units to restore target buffer stock.
5. **Approve Pricing**:
   - Click **Accept Price**.
   - Note the catalog table immediately updates PRD-003 price to \$27.49.
6. **Approve Reorder**:
   - Click **Accept Reorder**.
   - Note the catalog table immediately updates PRD-003 stock to 45 units.
7. **Switch Strategy**:
   - In the top header, switch the dropdown to **Rule-Based Advisor**.
   - Simulate a sale on **PRD-008: Hoodie** (velocity = 15.0).
   - Observe deterministic rule generation in real time.