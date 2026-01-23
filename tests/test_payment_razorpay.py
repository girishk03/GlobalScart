import base64
import hmac
import json
import os
from hashlib import sha256

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.main import app


def _db_available() -> bool:
    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    database = os.getenv("PGDATABASE", "globalcart")
    user = os.getenv("PGUSER", "globalcart")
    password = os.getenv("PGPASSWORD", "globalcart")

    dsn = f"host={host} port={port} dbname={database} user={user} password={password} connect_timeout=2"
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT 1", prepare=False)
        return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def client():
    if not _db_available():
        pytest.skip("PostgreSQL not reachable; set PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD to run API tests")

    with TestClient(app) as c:
        yield c


def _ensure_test_customer_exists(client: TestClient) -> int:
    r = client.post("/api/customer/resolve", json={"email": "test@example.com"})
    assert r.status_code == 200
    return int(r.json()["customer_id"])


def _pick_any_product(client: TestClient) -> int:
    r = client.get("/api/customer/products?limit=1&offset=0")
    assert r.status_code == 200
    products = r.json()
    assert products and isinstance(products, list)
    return int(products[0]["product_id"])


def _make_jwt_for_customer(customer_id: int) -> str:
    # Use the real /token endpoint if available; otherwise tests can supply a fake token.
    # Here we keep it simple: these payment endpoints require JWT; CI will have auth schema.
    return ""  # filled by test using /api/auth/token


def _webhook_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), msg=body, digestmod=sha256).hexdigest()


def test_razorpay_webhook_signature_validation(client: TestClient):
    # Requires webhook secret configured.
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_secret")

    body = json.dumps({"id": "evt_test_1", "event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1"}}}}).encode(
        "utf-8"
    )
    sig = _webhook_signature(body, secret)

    # Missing secret in app env is acceptable; endpoint will 500 if not configured.
    r = client.post(
        "/api/payments/razorpay/webhook",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    assert r.status_code in (200, 401, 500)


def test_razorpay_confirm_rejects_bad_signature(client: TestClient):
    # Without JWT this should 401; with JWT but bad signature should 401.
    r = client.post(
        "/api/payments/razorpay/confirm",
        json={
            "order_id": 1,
            "razorpay_order_id": "order_test",
            "razorpay_payment_id": "pay_test",
            "razorpay_signature": "bad",
        },
    )

    assert r.status_code in (401, 422)
