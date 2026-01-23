# Shop UI (Demo) — Evidence of customer flow

The FastAPI server serves a minimal storefront UI under `/shop/`.

## Pages

- `GET /shop/index.html`
  - Product browsing + search/filter
- `GET /shop/cart.html`
  - Cart review + quantity changes
- `GET /shop/checkout.html`
  - Checkout + payment method selection
  - Supports:
    - Simulated payment flow
    - Razorpay sandbox flow
- `GET /shop/order.html?order_id=...`
  - Order detail + payment status
- `GET /shop/login.html`
  - Signup/Login and JWT storage

## Demo flow to show a recruiter

1. Open `/shop/`
2. Login (creates/stores JWT)
3. Browse products and add to cart
4. Go to cart and proceed to checkout
5. Checkout:
   - Simulated payment: confirms/cancels immediately
   - Razorpay sandbox: opens Razorpay Checkout and confirms via `/api/payments/razorpay/confirm`
6. Land on order confirmation page

## Notes

This UI is intentionally simple (HTML/JS) to keep the repo self-contained and easy to run.
A React/Next.js frontend would be a separate track.
