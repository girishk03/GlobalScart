# Security Notes

This project is a demo but implements several production-style security patterns.

## Authentication

- JWT bearer tokens:
  - Issued by `POST /api/auth/token`
  - Validated by `backend/security.py`
  - Customer identity (`customer_id`) is derived from JWT in customer APIs.

## Password hashing

- Passwords are stored as PBKDF2-SHA256 hashes:
  - Implemented in `backend/routes/api_auth.py`
  - Stored in `globalcart.app_users.password_hash`

## Rate limiting

- Demo-grade in-memory rate limiting middleware for `/api/*`:
  - Configured with `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`
  - Implemented in `backend/main.py`

## CORS

- Dev mode uses permissive CORS.
- For production, restrict origins to your deployed frontend domain.

## Webhooks

- Razorpay webhook endpoint verifies signature:
  - Header: `X-Razorpay-Signature`
  - Secret: `RAZORPAY_WEBHOOK_SECRET`
  - Idempotency: stored in `globalcart.payment_webhook_events`.

## Production hardening (recommended)

- Use HTTPS only.
- Prefer HTTP-only secure cookies instead of localStorage for JWT.
- Replace in-memory rate limit with Redis.
- Add refresh tokens + rotation.
