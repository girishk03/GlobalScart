# GlobalCart 360: Backend Commerce & Analytics Engine

[![Live Demo](https://img.shields.io/badge/demo-live-green.svg)](https://globalscart.onrender.com/shop/)
[![Admin Dashboard](https://img.shields.io/badge/admin-dashboard-blue.svg)](https://globalscart.onrender.com/admin/)
[![API Docs](https://img.shields.io/badge/api-docs-orange.svg)](https://globalscart.onrender.com/docs)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-009688.svg?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-20.10+-2496ED.svg?style=flat&logo=docker&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Auth-black.svg?style=flat&logo=json-web-tokens&logoColor=white)

## 🔥 Why This Project Matters
- **Transactional Integrity**: Engineered a multi-stage checkout lifecycle (`ORDER_CREATED → PAYMENT_PENDING → SUCCESS/FAIL`) using PostgreSQL transactions for atomic consistency.
- **Production-Style Backend**: Implemented FastAPI with structured middleware, Request ID tracing, and centralized configuration.
- **Data Engineering**: Built a near real-time analytics pipeline with star-schema processing, idempotent upserts, and incremental refresh logic.
- **Security & RBAC**: Developed JWT-secured API flows with Role-Based Access Control and OTP-based verification.
- **Containerization**: Fully containerized environment using Docker Compose for reproducible deployment.

## 📸 System Preview (High-Impact UI)

<p align="center">
  <img src="screenshots/12-admin-analytics.png" width="90%" alt="Admin Analytics Dashboard" />
</p>

### 🛠️ Backend Observability & Admin Analytics
<p align="center">
  <img src="screenshots/13-admin-audit.png" width="48%" alt="Audit Log" />
  <img src="screenshots/15-journey-replay.png" width="48%" alt="User Journey" />
</p>

## 🚀 Live Links
- **🛒 [Storefront (Customer Flow)](https://globalscart.onrender.com/shop/)**
- **📊 [Admin Analytics Dashboard](https://globalscart.onrender.com/admin/)**
- **📜 [Swagger API Documentation](https://globalscart.onrender.com/docs)**

## ⚡ Quick Start (Local Demo)
```bash
# 1. Clone & Setup
git clone https://github.com/girishk03/GlobalScart.git
cd GlobalScart

# 2. Start Database
docker-compose up -d

# 3. Run Pipeline (Generate & Load Data)
python -m src.pipeline --scale small --truncate

# 4. Start Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
*Access Shop at `http://localhost:8000/shop/` | Admin at `http://localhost:8000/admin/`*

## 🛠️ Engineering Decisions (Tradeoffs & Solutions)

| Challenge | Solution | Engineering Impact |
| :--- | :--- | :--- |
| **Inventory Overselling** | Row-level locking + `reserved_qty` | Prevents race conditions during high-concurrency checkouts. |
| **Idempotency** | Webhook idempotency table | Ensures payment processing is safe against network retries. |
| **Observability** | Request-ID middleware | Allows end-to-end tracing of API calls across logs. |
| **Data Scalability** | Incremental Star Schema | Enables performant analytics on millions of rows without full reloads. |

---

## 🏗️ Technical Architecture Details

<details>
<summary><b>View System Design & Implementation Deep Dive</b></summary>

### 🛒 Transactional Storefront
- **Atomic Order Creation**: Handled via `POST /api/customer/checkout/start` within a single DB transaction.
- **State Machine**: `ORDER_CREATED → PAYMENT_PENDING → {PAYMENT_SUCCESS → ORDER_CONFIRMED} | {PAYMENT_FAILED → ORDER_CANCELLED}`.
- **Inventory Locking**: Row-level locking to prevent overselling during high-concurrency checkouts.

### 📊 Data Engineering & Analytics
- **Star Schema**: Optimized PostgreSQL schema for analytical queries.
- **Incremental Refresh**: Efficient data updates using `updated_at` watermarks and staging tables.
- **BI Marts**: Materialized views for executive KPIs and performance trends.

**Evidence**:
- API reference (repo): `docs/api.md`
- UI flow (repo): `docs/ui.md`
- Security notes (repo): `docs/security.md`
- Transaction lifecycle code: `backend/routes/api_customer.py`
- Lifecycle tests: `tests/test_checkout_lifecycle.py`

**Scope note:** This repository is a resume-ready **analytics + transactional demo** with a clear lifecycle and realistic architecture patterns. It is not a production store (missing PCI compliance, etc.).

For the “mixed concerns” story (analytics + APIs + UI + BI assets), see: `docs/architecture.md`.

</details>

<details>
<summary><b>View API Reference & Examples (CURL)</b></summary>

### Auth (JWT)
1) Get a JWT token:
```bash
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"YourPassword"}'
```

### Create an order
```bash
curl -X POST http://localhost:8000/api/customer/checkout/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "items": [{"product_id": 1001, "qty": 2}],
    "channel": "WEB",
    "currency": "INR",
    "payment_method": "UPI"
  }'
```
</details>

<details>
<summary><b>View Step-by-Step Installation & Full Gallery</b></summary>

### Customer Storefront
**Welcome / Landing**
<img src="screenshots/01-welcome-screen.png" width="800"/>

**Sign Up (OTP-based)**
<img src="screenshots/02-signup.png" width="800"/>

**Log In**
<img src="screenshots/03-login.png" width="800"/>

**Shop Home — Product Catalog & Filters**
<img src="screenshots/04-shop-home.png" width="800"/>

**Wishlist**
<img src="screenshots/05-wishlist.png" width="800"/>

**Cart**
<img src="screenshots/06-cart.png" width="800"/>

**Checkout — Delivery & Payment**
<img src="screenshots/07-checkout-top.png" width="800"/>
<img src="screenshots/08-checkout-bottom.png" width="800"/>

**Order History**
<img src="screenshots/09-orders.png" width="800"/>

**Inbox / Notifications**
<img src="screenshots/10-inbox.png" width="800"/>

### Admin Dashboard
**Admin Login**
<img src="screenshots/11-admin-login.png" width="800"/>

**Analytics — Revenue, Funnel & Top Products**
<img src="screenshots/12-admin-analytics.png" width="800"/>

**Audit Log — Order State Changes**
<img src="screenshots/13-admin-audit.png" width="800"/>

**User Journey Replay**
<img src="screenshots/14-admin-journey.png" width="800"/>

**Journey Replay - Timeline Detail**
<img src="screenshots/15-journey-replay.png" width="800"/>

</details>

## 🛠️ Tech Stack & Implementation Details
- **SQL**: PostgreSQL (Star Schema, Transactional Store)
- **Python**: FastAPI, Pydantic, SQLAlchemy, Pandas
- **Auth**: JWT + OTP-based Role-Based Access Control (RBAC)
- **Observability**: Structured Logging, Request ID Tracing, Security Middleware
- **Deployment**: Docker, Docker Compose

<details>
<summary><b>View Full Repository Structure</b></summary>

- `sql/`: Star schema DDL, views, KPI queries, BI marts.
- `backend/`: FastAPI server, routes, security modules.
- `src/`: Data generator, loaders, analytics pipeline.
- `docs/`: Architecture diagrams, API spec, security notes.
</details>
