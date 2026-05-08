# GlobalCart 360: Backend Commerce & Analytics Engine

[**🚀 API Documentation**](http://localhost:8000/docs) | [**🛒 Shop Demo**](http://localhost:8000/shop/) | [**📊 Admin Dashboard**](http://localhost:8000/admin/)

## 🔥 Why This Project Matters
- **Transactional Integrity**: Engineered a multi-stage checkout lifecycle (`ORDER_CREATED → PAYMENT_PENDING → SUCCESS/FAIL`) using PostgreSQL transactions for atomic consistency.
- **Production-Style Backend**: Implemented FastAPI with structured middleware, Request ID tracing, and centralized configuration.
- **Data Engineering**: Built a near real-time analytics pipeline with star-schema processing, idempotent upserts, and incremental refresh logic.
- **Security & RBAC**: Developed JWT-secured API flows with Role-Based Access Control and OTP-based verification.
- **Containerization**: Fully containerized environment using Docker Compose for reproducible deployment.

## 📸 System Preview (High-Impact UI)

### 🛠️ Backend Observability & Admin Analytics
<p align="center">
  <img src="screenshots/12-admin-analytics.png" width="32%" alt="Analytics Dashboard" />
  <img src="screenshots/13-admin-audit.png" width="32%" alt="Audit Log" />
  <img src="screenshots/15-journey-replay.png" width="32%" alt="User Journey" />
</p>

### 🛒 Transactional Storefront
<p align="center">
  <img src="screenshots/04-shop-home.png" width="32%" alt="Shop" />
  <img src="screenshots/06-cart.png" width="32%" alt="Cart" />
  <img src="screenshots/07-checkout-top.png" width="32%" alt="Checkout" />
</p>

---

## 🏗️ Technical Architecture Details
<details>
<summary><b>View System Overview</b></summary>
- **Transaction processing**: cart → checkout → payment lifecycle → order confirmation/cancellation
- **Analytics**: star schema + KPI views + incremental refresh + BI marts
- **Admin vs customer flows**: role-based access + protected admin endpoints
- **Evidence**:
  - API docs: `http://localhost:8000/docs`
  - API reference (repo): `docs/api.md`
  - UI flow (repo): `docs/ui.md`
  - Security notes (repo): `docs/security.md`
  - Transaction lifecycle code: `backend/routes/api_customer.py`
  - Lifecycle tests: `tests/test_checkout_lifecycle.py`
  - Storefront UI calling the lifecycle: `frontend/shop/checkout.html` + `frontend/shop/shop.js`

**Scope note:** this repository is not positioned as a full production e-commerce store (real payment provider integration, inventory reservation/stock deduction, fraud, PCI/compliance, etc.). Instead, it is a resume-ready **analytics + transactional demo** with a clear lifecycle and realistic architecture patterns.

For the “mixed concerns” story (analytics + APIs + UI + BI assets), see: `docs/architecture.md`.

</details>

<details>
<summary><b>View All Screenshots (Full Gallery)</b></summary>

### Customer Storefront
...
</details>

## 🛠️ Tech Stack & Implementation Details
- SQL: PostgreSQL
- Python: FastAPI, pandas, numpy, seaborn/matplotlib, scikit-learn, statsmodels
- Frontend: HTML/CSS/JavaScript with Bootstrap, voice search
- Auth: OTP + JWT + role-based access
- Excel: KPI + pivot-based management report (generated/extracted from the same KPI definitions)
- Power BI / Tableau: dashboard specs + DAX measures (ready to implement in BI)

## Repository Structure
- `sql/`: star schema DDL, views, KPI queries, BI marts, cart/order/payment tables
- `src/`: data generator, loaders, extractors, analytics pipeline
- `backend/`: FastAPI server for admin/customer APIs and web UIs
  - `backend/routes/api_customer.py`: cart, checkout, order/payment lifecycle
  - `backend/routes/api_auth.py`: OTP + JWT auth, `/me` endpoint
  - `backend/routes/api_admin.py`: admin APIs (JWT or admin-key auth)
  - `backend/routes/api_payments.py`: Razorpay sandbox (order + confirm + webhook)
- `frontend/`: customer storefront (/shop) and admin UI assets
- `notebooks/`: EDA, RFM segmentation, forecasting (notebook-friendly)
- `docs/`: data dictionary, KPI definitions, architecture
- `dashboards/`: Power BI/Tableau specs + DAX measures
- `data/`: generated raw and processed extracts (created at runtime)

## ⚙️ Core Backend Architecture

### Transactional E-commerce Features
- **Atomic Order Creation**: Handled via `POST /api/customer/checkout/start` within a single DB transaction.
- **State Machine**: `ORDER_CREATED → PAYMENT_PENDING → {PAYMENT_SUCCESS → ORDER_CONFIRMED} | {PAYMENT_FAILED → ORDER_CANCELLED}`.
- **Inventory Locking**: Row-level locking to prevent overselling during high-concurrency checkouts.

### Data Engineering & Analytics
- **Star Schema**: Optimized PostgreSQL schema for analytical queries.
- **Incremental Refresh**: Efficient data updates using `updated_at` watermarks and staging tables.
- **BI Marts**: Materialized views for executive KPIs and performance trends.

---

## 🛠️ Technical Stack & Implementation Details
- **Backend**: FastAPI (Python), Pydantic, SQLAlchemy.
- **Database**: PostgreSQL (Star Schema).
- **Auth**: JWT + OTP-based verification.
- **Observability**: Structured logging + Request ID middleware.

<details>
<summary><b>View Full Repository Structure</b></summary>

- `sql/`: DDL, views, KPI queries, BI marts.
- `backend/`: FastAPI server, routes, security.
- `src/`: Data generator, loaders, analytics pipeline.
- `docs/`: Architecture, API spec, security notes.
</details>

<details>
<summary><b>View Step-by-Step Installation</b></summary>
