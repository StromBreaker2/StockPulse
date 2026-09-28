# StockPulse — AI Inventory & Dynamic Pricing Engine

StockPulse is a reactive merchandising advisor for modern e-commerce stores. It observes inventory movements and sales velocity signals, applies automated intelligence (rule-based or AI) to compute dynamic pricing and reorder suggestions, and holds recommendations in a pending approval state for human review.

---

## Problem

E-commerce merchants lose margins and sales from two common operational failures:
1. **Stockouts during demand spikes**: Fast-moving items sell out before purchase orders are issued, forfeiting revenue and hurting search ranking.
2. **Delayed pricing adjustments**: Under inventory scarcity, prices remain static instead of capturing premium demand and throttling stock depletion. Conversely, over-stocked inventory sits idle without proactive price intervention.

Traditional enterprise ERPs are either overly complex, slow, or lack intelligent human-in-the-loop workflows.

---

## Solution

StockPulse implements a reactive, human-governed advisory loop:
1. **Observe**: Sales and inventory updates occur via simple REST endpoints.
2. **Detect Signals**: Background detectors immediately spot critical conditions (inventory below threshold or velocity demand spikes).
3. **Reason & Advise**: A unified Commerce Advisor generates paired recommendations (Price Adjustment + Replenishment Quantity).
4. **Human Checkpoint**: Recommendations are created in a `PENDING` state. Prices are never changed automatically; orders are never placed automatically.
5. **Enact**: Merchandisers accept or reject suggestions from a real-time dashboard, applying changes directly to product state upon approval.

---

## Architecture

```
                    React Frontend (Vite)
                             │
                        REST API
                             │
                             ▼
                      FastAPI Server
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   SQLAlchemy ORM      CommerceAdvisor       BackgroundTasks
        │                    │                    │
        ▼              ┌─────┴─────┐              ▼
Neon PostgreSQL        │           │     Asynchronous Reactive
                       ▼           ▼        Advisory Loop
                  RuleBased    AIAdvisor
                   Advisor         │
                                   ▼
                             Zycus LLM API
```

### Asynchronous Event Loop

```
Order / Stock Update (POST /products/{id}/orders)
        │
        ▼
Synchronous Stock Deduction & Velocity Increment
        │
        ▼
Signal Detection (INVENTORY_LOW or DEMAND_SPIKE)
        │
        ▼
FastAPI BackgroundTasks.add_task(...) ──► Returns HTTP 200 Immediately
        │
        ▼ (Background Worker)
CommerceAdvisor (AI or RuleBased)
        │
        ▼
Persist PricingSuggestion & ReorderSuggestion (Status: PENDING)
        │
        ▼
Merchandiser UI polls and presents suggestions for 1-click Accept / Reject
```

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.0, Psycopg 3, Pydantic v2, Python-Dotenv, Httpx, Pytest
- **Frontend**: React 18, Vite, Axios, Plain CSS
- **Database**: Neon PostgreSQL (Serverless PostgreSQL)
- **AI Integration**: OpenAI-compatible LLM endpoint (qwen-cursor / Zycus LiteLLM)

---

## Project Structure

```
stockpulse/
│
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application, routing & background tasks
│   │   ├── database.py      # SQLAlchemy engine & session management
│   │   ├── config.py        # Environment settings & configuration
│   │   ├── models.py        # SQLAlchemy ORM models (Product, Suggestions)
│   │   ├── schemas.py       # Pydantic validation schemas
│   │   ├── services.py      # Business logic, stock updates, approval flows
│   │   ├── strategies.py    # Strategy Pattern (RuleBased & AI advisors)
│   │   ├── ai.py            # Async LLM client, prompt engineering, validation
│   │   └── seed.py          # Automatic seed data loader (8 demo products)
│   │
│   ├── tests/
│   │   ├── conftest.py          # Pytest fixtures & test database setup
│   │   ├── test_products.py     # Product CRUD & order simulation tests
│   │   ├── test_strategy.py     # Rule-based, AI validation & fallback tests
│   │   └── test_suggestions.py  # Suggestions, duplicate prevention & approvals
│   │
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Template for environment variables
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Merchandising dashboard UI
│   │   ├── api.js           # Axios API client
│   │   ├── styles.css       # Clean dashboard styling
│   │   └── main.jsx         # React application entry point
│   ├── package.json
│   └── vite.config.js       # Vite configuration with /api proxy to FastAPI
│
├── ADR.md                   # Architecture Decision Records (ADR 001 - 006)
├── README.md                # Project documentation & walkthrough
├── PROJECT_STATUS.md        # Comprehensive implementation status & checklist
└── .gitignore               # Strict ignore rules (preventing credential leaks)
```

---

## Neon Setup

1. Create a free PostgreSQL database on [Neon](https://neon.tech).
2. Copy the connection string provided in your Neon console. It will resemble:
   ```text
   postgresql://username:password@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Set `DATABASE_URL` in `backend/.env`.
4. When FastAPI starts, SQLAlchemy creates all tables automatically. If the `products` table is empty, seed data is inserted automatically. No manual SQL scripts are required.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

Configuration variables:

```ini
# Neon PostgreSQL Connection String
DATABASE_URL=postgresql://username:password@hostname/database_name?sslmode=require

# LLM Configuration (OpenAI-compatible Zycus endpoint)
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://litellm-qc.zycus.net/v1
LLM_MODEL=qwen-cursor
LLM_PRODUCT=PC1
LLM_COOKIE=

# Business Signal Multipliers
DEMAND_SPIKE_MULTIPLIER=3

# Default Advisory Strategy (AI or RULE_BASED)
DEFAULT_STRATEGY=AI
```

> **Security Note**: Never commit `.env` or hardcode credentials. All sensitive variables are excluded via `.gitignore`.

---

## Backend Setup

1. Open a terminal in the `backend` folder:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Run database migrations / initialize seed data (automatic on launch, or manual):
   ```bash
   python -m app.seed
   ```
4. Start the backend server:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
5. Check backend health:
   Navigate to `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/docs` (Swagger UI).

---

## Frontend Setup

1. Open a terminal in the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Access the dashboard at `http://localhost:5173`.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status check |
| `POST` | `/products` | Create a product with schema validation |
| `GET` | `/products` | List all products (supports `?category=` and `?status=`) |
| `GET` | `/products/{id}` | Get product details |
| `PATCH` | `/products/{id}/stock` | Update stock level and trigger evaluation |
| `POST` | `/products/{id}/orders` | Simulate sale, decrement stock, increase velocity, launch async advisor |
| `POST` | `/products/{id}/suggest-pricing` | Generate on-demand pricing recommendation |
| `POST` | `/products/{id}/suggest-reorder` | Generate on-demand reorder recommendation |
| `GET` | `/suggestions/pending` | Fetch pending pricing and reorder suggestions |
| `PATCH` | `/pricing-suggestions/{id}` | Human review: `{"action": "ACCEPT"}` or `{"action": "REJECT"}` |
| `PATCH` | `/reorder-suggestions/{id}` | Human review: `{"action": "ACCEPT"}` or `{"action": "REJECT"}` |
| `GET` | `/settings/strategy` | View active advisor strategy (`AI` or `RULE_BASED`) |
| `PATCH` | `/settings/strategy` | Switch active advisor strategy at runtime |

---

## Strategy Pattern

The recommendation engine implements the **Strategy Pattern**:
- `CommerceAdvisor`: Abstract base interface requiring `get_recommendations()`, `get_pricing_recommendation()`, and `get_reorder_recommendation()`.
- `RuleBasedAdvisor`: Deterministic retail heuristics:
  - Low stock (`stock < threshold`): +10% price adjustment, `INCREASE`, 90% confidence.
  - High demand (`velocity > 2 * category_avg`): +5% price adjustment, `INCREASE`, 90% confidence.
  - Normal condition: current price, `HOLD`, 90% confidence.
  - Reorder calculation: `(threshold * 3) - current_stock` (buffer replenishment).
- `AIAdvisor`: LLM-powered context analysis with dynamic reasoning.
- `CommerceAdvisorManager`: Thread-safe manager holding advisor instances and allowing runtime switching without application restarts.

---

## AI Integration

- Connects to the OpenAI-compatible Zycus endpoint (`https://litellm-qc.zycus.net/v1/chat/completions`) using `httpx.AsyncClient` with non-blocking async execution.
- Generates tailored prompts with distinct business context:
  - `INVENTORY_LOW`: Emphasizes scarcity, margin protection, and replenishment urgencies.
  - `DEMAND_SPIKE`: Emphasizes price elasticity, capturing revenue momentum, and bulk reorder.
- Strictly validates JSON outputs:
  - `recommendedPrice > 0` and `<= 2 * current_price`
  - `direction` in `['INCREASE', 'DECREASE', 'HOLD']`
  - `0 <= priceConfidence <= 1`
  - `recommendedQuantity >= 1`
  - `0 <= reorderConfidence <= 1`
  - Non-empty explanatory reasonings

---

## AI Fallback

If the LLM endpoint experiences a timeout, connection failure, HTTP error, missing environment key, or produces malformed JSON:
1. `AIAdvisor` catches the error.
2. Logs `AI advisor failed; using rule-based fallback.` (without exposing credentials).
3. Executes `RuleBasedAdvisor` immediately.
4. Returns a valid, deterministic recommendation so operations never freeze.

---

## Agentic Loop

StockPulse realizes a practical **Autonomous Agentic Loop with Human Checkpoint**:
1. **Sense**: Incoming customer order decrements inventory.
2. **Detect**: Signal detector notices threshold breach (`INVENTORY_LOW`).
3. **Decide**: `CommerceAdvisor` evaluates category velocity and recommends actions.
4. **Prevent Duplication**: Idempotency check prevents duplicate pending suggestions for the same product and trigger condition.
5. **Checkpoint**: Suggestions remain in `PENDING` state until merchandiser review.
6. **Actuate**: Upon clicking **Accept Price** or **Accept Reorder**, database models update atomically.

---

## Demo Walkthrough

### Primary Demo: Inventory Scarcity & Dynamic Price Adjustment
1. Launch both backend (`http://127.0.0.1:8000`) and frontend (`http://localhost:5173`).
2. On the dashboard, locate **PRD-003: Organic Cotton T-Shirt** (Stock: 8, Reorder Threshold: 15).
3. Click **Simulate Sale**.
4. Stock immediately drops to 7.
5. Within 1-2 seconds, the background advisor generates recommendations under **Pending Human Approvals**:
   - **Pricing Recommendation**: Recommends increasing price from \$24.99 to \$27.49 with business justification.
   - **Replenishment Order**: Recommends reordering 38 units to restore target buffer.
   - **Trigger Badge**: `INVENTORY_LOW`.
6. Click **Accept Price**: Product price immediately updates to \$27.49 in the catalog.
7. Click **Accept Reorder**: Product stock immediately increases by +38 units.

### Secondary Demo: Strategy Switch & Demand Spike
1. Use the header dropdown to switch Advisor Strategy to **Rule-Based Advisor**.
2. Locate **PRD-008: Hoodie - Heather Grey** (Demand velocity: 15.0).
3. Click **Simulate Sale** to trigger demand evaluation.
4. Verify that deterministic rule-based suggestions are produced and displayed.
5. Switch strategy back to **AI** at will.

---

## Testing

Run the test suite with pytest:

```bash
cd backend
python -m pytest -v
```

### Verified Test Coverage (20 Tests):
- `test_health_endpoint`: Health check API verification.
- `test_create_product`: Validates product constraints, positive price, and non-negative stock.
- `test_list_products`: Category filtering and inventory listing.
- `test_simulated_order_decreases_stock`: Order execution and velocity incrementing.
- `test_inventory_low_detection`: Threshold detection heuristics.
- `test_demand_spike_detection`: Multiplier velocity spike detection.
- `test_rule_based_pricing_inventory_low`: 10% price markup on low stock.
- `test_rule_based_pricing_high_demand`: 5% price markup on demand surge.
- `test_rule_based_pricing_normal`: Neutral hold recommendation under normal conditions.
- `test_rule_based_reorder`: Buffer stock replenishment calculation.
- `test_ai_validation_success`: Schema parsing and constraint validation.
- `test_ai_validation_failures`: Safe rejection of invalid quantities or runaway prices.
- `test_ai_advisor_fallback_on_failure`: Transparent fallback to rule-based advisor when AI fails.
- `test_strategy_manager_switching`: Dynamic strategy switching at runtime.
- `test_duplicate_prevention`: Duplicate pending suggestion suppression.
- `test_pricing_accept_updates_product_price`: Human price approval workflow.
- `test_pricing_reject_leaves_product_price_unchanged`: Human price rejection workflow.
- `test_reorder_accept_updates_product_stock`: Human reorder approval workflow.
- `test_reorder_reject_leaves_stock_unchanged`: Human reorder rejection workflow.
- `test_cannot_re_decide_suggestion`: Immutability of finalized suggestions.

---

## Future Scope

- **Multi-location inventory tracking**: Route reorder suggestions to regional distribution centers.
- **Supplier lead time learning**: Dynamically adjust reorder lead times based on historical vendor fulfillment records.
- **Competitor price elasticity integration**: Incorporate competitive pricing feeds to constrain price increases.
- **Bulk purchase order export**: Generate standardized EDI or PDF purchase orders upon batch reorder approval.