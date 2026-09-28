# Architecture Decision Records (ADRs)

Project: **StockPulse — AI Inventory & Dynamic Pricing Engine**

---

## ADR-001: Why FastAPI + Simple Architecture

### Context
StockPulse requires a backend capable of handling synchronous REST operations (catalog queries, stock mutations, order simulations) alongside non-blocking background task execution for LLM and rule evaluations. The solution must be easily maintainable and explainable by an individual engineer during a live hackathon demonstration without enterprise framework bloat.

### Options
1. **Spring Boot (Java)**: High boilerplate, complex configuration, heavy memory footprint, and outside developer core fluency.
2. **Django + Celery + Redis**: Comprehensive batteries-included framework, but requires separate worker processes, message broker infrastructure, and heavyweight ORM overhead.
3. **FastAPI + SQLAlchemy + Psycopg**: High-performance async Python framework, automatic OpenAPI documentation, clean Pydantic type validation, and built-in background tasks without external brokers.

### Decision
Adopt **FastAPI** with a clean, monolithic single-service architecture using **SQLAlchemy** and **Neon PostgreSQL**.

### Tradeoffs
- **Pros**:
  - Native asynchronous support and clean async HTTP client integrations (`httpx.AsyncClient`).
  - Automatic Swagger/OpenAPI documentation (`/docs`) for rapid endpoint testing.
  - Zero external worker or broker dependencies for background task orchestration.
  - Clean, concise codebase easily defensible in 5 minutes.
- **Cons**:
  - Background tasks run within the same application process; not suited for distributed multi-node clusters without migrating to Celery/Kafka later.

---

## ADR-002: Why Strategy Pattern for Commerce Advisors

### Context
Merchandising decisions require diverse operational modes:
1. Fast, deterministic, predictable heuristics for low-latency operational environments or offline situations.
2. Context-aware, natural-language reasoned recommendations powered by large language models (LLMs).
Furthermore, administrators must be able to switch between AI and deterministic modes at runtime without restarting servers or losing session state.

### Options
1. **Scattered `if/else` checks**: Interleave conditional checks in every endpoint and service function.
2. **Separate microservice endpoints**: Expose independent `/ai-pricing` and `/rule-pricing` endpoints.
3. **Strategy Pattern**: Define a shared `CommerceAdvisor` interface with concrete implementations (`RuleBasedAdvisor`, `AIAdvisor`) governed by a `CommerceAdvisorManager`.

### Decision
Implement the **Strategy Pattern** with an abstract `CommerceAdvisor` base class and a singleton `CommerceAdvisorManager`.

### Tradeoffs
- **Pros**:
  - Complete decoupling of recommendation algorithms from API routing and persistence logic.
  - Runtime dynamic strategy switching via `PATCH /settings/strategy`.
  - Simplifies testing and mocking: unit tests verify rule mechanics and AI fallback independently.
- **Cons**:
  - Introduces class abstraction layers, though kept minimal and straightforward.

---

## ADR-003: Unified AI Recommendation vs Separate Calls

### Context
When an inventory signal fires (such as `INVENTORY_LOW` or `DEMAND_SPIKE`), the merchant needs both dynamic pricing guidance (to regulate demand elasticity and protect margin) and replenishment guidance (reorder quantity and lead times). We must decide whether to query the LLM twice or synthesize both recommendations in a single prompt.

### Options
1. **Two sequential LLM calls**: First prompt for pricing, wait for response, then prompt for replenishment.
2. **Two concurrent LLM calls**: Launch two parallel asynchronous requests to the LLM.
3. **Unified single prompt and response**: Pass complete product inventory and demand context to a single LLM prompt that returns both pricing and reorder suggestions in one JSON object.

### Decision
Adopt a **unified single LLM prompt and response** returning paired recommendations.

### Tradeoffs
- **Pros**:
  - Halves network round-trips and LLM token overhead, reducing latency from ~4-6s to ~2-3s.
  - Contextual coherence: the LLM considers inventory scarcity simultaneously when setting price and calculating replenishment volume.
  - Avoids partial failure states where pricing succeeds but replenishment fails.
- **Cons**:
  - Prompt requires strict JSON schema definition containing fields for both pricing and reordering.

---

## ADR-004: LLM Failure Fallback to Deterministic Rules

### Context
External LLM endpoints are inherently non-deterministic and susceptible to network latency, gateway timeouts (HTTP 504), rate limits (HTTP 429), missing API keys, or malformed JSON responses. Merchandising workflows cannot afford silent failures or corrupted application states when third-party services degrade.

### Options
1. **Fail-Fast with HTTP Error**: Return error status to the client or log failure and discard the event.
2. **Retry Loop**: Retry LLM requests with exponential backoff (risks request timeouts and background backlog).
3. **Transparent Rule-Based Fallback**: Catch LLM errors, log a clear warning (`AI advisor failed; using rule-based fallback.`), and automatically generate valid recommendations using `RuleBasedAdvisor`.

### Decision
Implement **transparent rule-based fallback** inside `AIAdvisor`.

### Tradeoffs
- **Pros**:
  - High availability: the application never drops signals or fails to produce recommendations.
  - Zero sensitive credential exposure in exception traces.
  - Enables local offline development and automated CI testing even when LLM keys are absent.
- **Cons**:
  - In degraded network conditions, recommendations silently switch to deterministic calculations (observable through logged warnings and confidence score characteristics).

---

## ADR-005: FastAPI BackgroundTasks for the Reactive Loop

### Context
Simulating sales (`POST /products/{id}/orders`) or manually editing inventory (`PATCH /products/{id}/stock`) are high-frequency merchant operations. Generating recommendations involves signal evaluation and potential LLM API calls that can take 1 to 5 seconds. Merchandisers and checkout systems must receive immediate confirmation without waiting for advisory synthesis.

### Options
1. **Synchronous in-line generation**: Compute recommendations directly in the order request thread before returning HTTP 200.
2. **Full Distributed Task Queue (Celery + RabbitMQ/Redis)**: Offload tasks to external worker pools.
3. **FastAPI BackgroundTasks**: Enqueue task execution onto the server event loop to run immediately after returning the HTTP response.

### Decision
Use **FastAPI `BackgroundTasks`** for the reactive recommendation loop.

### Tradeoffs
- **Pros**:
  - Instant client response times (<20ms) for checkout and order simulations.
  - Zero extra infrastructure (no Redis daemon, no Celery workers, no message broker configurations).
  - Background workers utilize independent SQLAlchemy sessions (`SessionLocal()`) ensuring thread-safe database commits.
- **Cons**:
  - In-memory tasks do not persist across hard server crashes; acceptable for hackathon MVP scope.

---

## ADR-006: Extensibility and Deferred Features

### Context
Hackathon delivery constraints require focusing strictly on the core problem: inventory monitoring, dynamic signal detection, intelligent pricing/reorder advisory, and human approval checkpoints. We must explicitly establish project boundaries to prevent scope creep.

### Options
1. **Full E-Commerce ERP Suite**: Implement user authentication, multi-tenant RBAC, payment gateway integrations, consumer cart/checkout, automated supplier EDI ordering, and vector-database semantic search.
2. **Laser-Focused MVP with Clean Extensibility Points**: Build the essential reactive commerce loop with clear separation of concerns, leaving explicit seams for future modules.

### Decision
Build the **focused reactive merchandising engine** and deliberately defer non-core enterprise features.

### Specific Deferrals:
- **Authentication & RBAC**: Deferred; currently open for rapid internal merchandising demonstration.
- **Automated Purchase Orders**: Replaced by mandatory human approval (`PATCH /reorder-suggestions/{id}`).
- **Vector Databases / RAG / Multi-agent Frameworks**: Excluded; prompt engineering with exact real-time SQL aggregates (category average demand velocity, stock levels, thresholds) completely satisfies LLM context requirements without vector overhead.
- **Microservices & Kubernetes**: Excluded in favor of a clean, portable single-service deployment.

### Tradeoffs
- **Pros**:
  - Delivers a rock-solid, fully functioning demo without half-implemented abstractions or fragile multi-service dependencies.
  - Easily understandable and defendable by a single developer.
- **Cons**:
  - Production enterprise deployment will require introducing auth middleware and audit trails.