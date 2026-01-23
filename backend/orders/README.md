# Orders module

Implementation lives in:
- `backend/routes/api_customer.py` (checkout + order lifecycle)

Endpoints:
- `POST /api/customer/checkout/start`
- `GET /api/customer/orders/{order_id}`
- `GET /api/customer/orders/by-customer/{customer_id}`
- `POST /api/customer/orders/{order_id}/simulate-payment`
- `POST /api/customer/orders/{order_id}/cancel`
