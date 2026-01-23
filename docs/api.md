# API Reference

This repo exposes both:
- a **customer storefront API** (catalog/cart/checkout/orders)
- an **admin API** (analytics + admin operations)

Interactive OpenAPI/Swagger:
- Local: `http://localhost:8000/docs`

---

## Authentication

### JWT token

Get an access token:

```bash
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"YourPassword"}'
```

Use it:

```http
Authorization: Bearer <access_token>
```

### OTP signup/login

- `POST /api/auth/request-otp`
- `POST /api/auth/verify-otp`
- `POST /api/auth/signup/request-otp`
- `POST /api/auth/signup/verify-otp`

---

## Customer APIs (`/api/customer/*`)

### Catalog

- `GET /api/customer/products`
  - Query: `q`, `category_l1`, `category_l2`, `min_price`, `max_price`, `sort`, `limit`, `offset`
- `GET /api/customer/products/{product_id}`

### Cart

- `GET /api/customer/cart`
- `POST /api/customer/cart`
- `PUT /api/customer/cart`
- `DELETE /api/customer/cart`

Auth:
- Recommended: JWT bearer token (customer_id taken from JWT)
- Backward-compatible fallback: `?customer_id=...`

Example:

```bash
curl -X POST http://localhost:8000/api/customer/cart \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1001, "qty": 2}'
```

### Checkout

- `POST /api/customer/checkout/start`
  - Creates an order + payment row atomically:
    - `fact_orders.order_status = ORDER_CREATED`
    - `fact_payments.payment_status = PAYMENT_PENDING`

### Inventory / Stock handling (current limitation)

This demo does **not** implement real inventory reservation or stock decrement.

Current behavior:
- Products are treated as always available (no oversell prevention).
- Checkout and payment flows do not mutate stock levels.

If you want to extend this into a production-like flow, the minimum acceptable pattern is:
- Stock check + reservation during `POST /api/customer/checkout/start`
- Final decrement on payment success (`/api/customer/orders/{order_id}/simulate-payment` success path or Razorpay confirm/webhook)
- Release reservation on payment failure/cancel

### Orders

- `GET /api/customer/orders/{order_id}`
- `GET /api/customer/orders/by-customer/{customer_id}` (legacy param; JWT recommended)
- `POST /api/customer/orders/{order_id}/simulate-payment`
- `POST /api/customer/orders/{order_id}/cancel`

---

## Payments (`/api/payments/*`)

### Razorpay (sandbox)

Implementation:
- Routes: `backend/routes/api_payments.py`
- DB migration: `sql/11_razorpay.sql`

- `POST /api/payments/razorpay/order?order_id=...`
  - Creates a Razorpay Order for an existing GlobalCart `order_id`.

- `POST /api/payments/razorpay/confirm`
  - Verifies Razorpay Checkout signature (`HMAC_SHA256(razorpay_order_id|razorpay_payment_id, key_secret)`) and transitions:
    - `PAYMENT_PENDING → PAYMENT_SUCCESS`
    - `ORDER_CREATED → ORDER_CONFIRMED`

- `POST /api/payments/razorpay/webhook`
  - Provider-signed webhook ingestion with idempotency (events stored in `globalcart.payment_webhook_events`).

Required env vars:
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

---

## Admin APIs

- Admin key header:
  - `X-Admin-Key: <key>`

Key examples:
- `POST /api/admin/login`
- `GET /api/admin/kpis/latest`

See `backend/routes/api_admin.py` and Swagger for the full list.
