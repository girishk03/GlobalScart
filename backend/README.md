# Backend: FastAPI APIs (Analytics + Transactional E-commerce)

## Overview
- FastAPI server at `/` serves both analytics and transactional e-commerce features.
- All APIs are documented via OpenAPI/Swagger at `http://localhost:8000/docs`.

## Key Transactional E-commerce APIs

### Cart (persistent per customer)
- `GET /api/customer/cart?customer_id=...` → cart summary with totals
- `POST /api/customer/cart?customer_id=...` → add/increment item
- `PUT /api/customer/cart?customer_id=...` → set item qty
- `DELETE /api/customer/cart/{product_id}?customer_id=...` → remove item
- `DELETE /api/customer/cart?customer_id=...` → clear cart

**Implementation file**: `routes/api_customer.py`  
**DB table**: `globalcart.customer_cart_items` (created in `../sql/10_shop_features.sql`)

### Checkout & Order Lifecycle (atomic transactions)
- `POST /api/customer/checkout/start` → creates `ORDER_CREATED` + `PAYMENT_PENDING`
  - Returns `{order_id, payment_id, order_status, payment_status, amount}`
- `POST /api/customer/orders/{order_id}/simulate-payment?customer_id=...` → simulate payment result
  - Body: `{ "success": true }` or `{ "success": false, "failure_reason": "BANK_DOWN" }`
  - Success: `ORDER_CONFIRMED` + `PAYMENT_SUCCESS` + creates shipment
  - Failure: `ORDER_CANCELLED` + `PAYMENT_FAILED` + records cancellation

**State machine**: `ORDER_CREATED → PAYMENT_PENDING → {PAYMENT_SUCCESS → ORDER_CONFIRMED} | {PAYMENT_FAILED → ORDER_CANCELLED}`  
**Implementation file**: `routes/api_customer.py`  
**DB tables**: `globalcart.fact_orders`, `globalcart.fact_payments`, `globalcart.fact_shipments`, `globalcart.order_cancellations`

### Auth (OTP + JWT + roles)
- `POST /api/auth/request-otp` → send OTP
- `POST /api/auth/verify-otp` → verify OTP, returns user info
- `POST /api/auth/token` → issue JWT (includes role)
- `GET /api/auth/me` → get current user from JWT

**Roles**: `customer` (default), `admin`  
**Implementation files**: `routes/api_auth.py`, `security.py`  
**DB table**: `globalcart.app_users` (created in `../sql/07_app_auth.sql`)

### Admin APIs (JWT or admin-key)
- Admin endpoints accept either:
  - `Authorization: Bearer <JWT>` with role `admin`
  - `X-Admin-Key: <ADMIN_KEY>` header (legacy)
- Example: `GET /api/admin/kpis/latest` (protected)

**Implementation file**: `routes/api_admin.py`

## Where to Find Code

| Feature | File(s) | Notes |
|---------|---------|-------|
| Cart APIs | `routes/api_customer.py` | `/cart` endpoints |
| Checkout & payment lifecycle | `routes/api_customer.py` | `/checkout/start`, `/orders/{id}/simulate-payment` |
| Auth (OTP + JWT) | `routes/api_auth.py`, `security.py` | `/auth/*` |
| Admin APIs | `routes/api_admin.py` | JWT or admin-key auth |
| Pydantic models | `models.py` | `CheckoutStartOut`, `PaymentSimulateIn/Out`, `CartSummaryOut`, `CartItemIn/Out` |
| DB schemas | `../sql/00_schema.sql`, `../sql/07_app_auth.sql`, `../sql/10_shop_features.sql` | orders/payments, auth, cart |

## Running the Backend

```bash
# From repo root (ensure PostgreSQL is running)
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/docs` for interactive API docs.

## Testing the Transaction Flow (Example)

```bash
# 1) Add to cart
curl -X POST http://localhost:8000/api/customer/cart?customer_id=1 \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1001, "qty": 2}'

# 2) Start checkout (creates order + payment pending)
curl -X POST http://localhost:8000/api/customer/checkout/start \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "items": [{"product_id": 1001, "qty": 2}], "channel": "WEB"}'

# 3) Simulate payment success
curl -X POST http://localhost:8000/api/customer/orders/12345/simulate-payment?customer_id=1 \
  -H "Content-Type: application/json" \
  -d '{"success": true}'
```

## Notes
- All transactional operations use explicit DB transactions with rollback on error.
- Cart data is persistent per customer.
- Payment simulation is for demo/interview purposes; in production replace with Stripe/Razorpay webhooks.
