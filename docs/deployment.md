# Deployment

This repo is a combined analytics + transactional demo. In production you would typically split these concerns, but this guide shows a simple deploy of the FastAPI app with Postgres.

## Quick deploy options

### Option A: Render (recommended for FastAPI demo)

- Create a **PostgreSQL** instance.
- Create a **Web Service** from this repo.
- Build command:
  - `pip install -r requirements.txt`
- Start command:
  - `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`

Then run the SQL setup once against the provisioned database:
- `sql/00_schema.sql`
- `sql/02_views.sql`
- `sql/07_app_auth.sql`
- `sql/10_shop_features.sql`
- `sql/11_razorpay.sql`

### Option B: Railway

- Provision Postgres.
- Deploy the service using the included `Dockerfile`.

## Required environment variables

### Database
- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

### App
- `ENV` (`dev` or `prod`)
- `JWT_SECRET` (required when `ENV=prod`)
- `JWT_ISSUER` (default `globalcart`)
- `JWT_AUDIENCE` (default `globalcart`)

### Razorpay (optional)
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

## Razorpay webhook configuration

- Webhook URL:
  - `https://<your-domain>/api/payments/razorpay/webhook`
- Configure the webhook secret to match `RAZORPAY_WEBHOOK_SECRET`.

## Production notes

- Restrict CORS to your real frontend origin.
- Put the service behind HTTPS.
- Do not store JWT in localStorage for production; use secure cookies if possible.
- The in-memory rate limiter is demo-grade; replace with Redis in production.
