# Payments module

Implementation lives in:
- `backend/routes/api_payments.py` (Razorpay sandbox + webhook)
- `backend/routes/api_customer.py` (simulated payment endpoint)

Endpoints:
- `POST /api/payments/razorpay/order`
- `POST /api/payments/razorpay/confirm`
- `POST /api/payments/razorpay/webhook`
