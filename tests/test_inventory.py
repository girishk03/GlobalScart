import os

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


def _dsn() -> str:
    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    database = os.getenv("PGDATABASE", "globalcart")
    user = os.getenv("PGUSER", "globalcart")
    password = os.getenv("PGPASSWORD", "globalcart")
    return f"host={host} port={port} dbname={database} user={user} password={password}"


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


def _set_stock(product_id: int, on_hand: int, reserved: int = 0) -> None:
    with psycopg.connect(_dsn()) as conn:
        conn.execute("SET TIME ZONE 'UTC';", prepare=False)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO globalcart.product_inventory (product_id, on_hand_qty, reserved_qty)
                VALUES (%s, %s, %s)
                ON CONFLICT (product_id) DO UPDATE
                SET on_hand_qty = EXCLUDED.on_hand_qty,
                    reserved_qty = EXCLUDED.reserved_qty,
                    updated_at = NOW();
                """,
                (int(product_id), int(on_hand), int(reserved)),
            )
        conn.commit()


def _get_stock(product_id: int) -> tuple[int, int]:
    with psycopg.connect(_dsn()) as conn:
        conn.execute("SET TIME ZONE 'UTC';", prepare=False)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT on_hand_qty, reserved_qty FROM globalcart.product_inventory WHERE product_id=%s;",
                (int(product_id),),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row[0]), int(row[1])


def test_inventory_prevents_oversell_and_releases_on_failure(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    _set_stock(product_id, on_hand=1, reserved=0)

    r = client.post(
        "/api/customer/checkout/start",
        json={"customer_id": customer_id, "items": [{"product_id": product_id, "qty": 1}], "channel": "WEB"},
    )
    assert r.status_code == 200
    order_id_1 = int(r.json()["order_id"])

    r = client.post(
        "/api/customer/checkout/start",
        json={"customer_id": customer_id, "items": [{"product_id": product_id, "qty": 1}], "channel": "WEB"},
    )
    assert r.status_code == 409

    r = client.post(
        f"/api/customer/orders/{order_id_1}/simulate-payment?customer_id={customer_id}",
        json={"success": False, "failure_reason": "BANK_DOWN"},
    )
    assert r.status_code == 200

    on_hand, reserved = _get_stock(product_id)
    assert on_hand == 1
    assert reserved == 0

    r = client.post(
        "/api/customer/checkout/start",
        json={"customer_id": customer_id, "items": [{"product_id": product_id, "qty": 1}], "channel": "WEB"},
    )
    assert r.status_code == 200


def test_inventory_decrements_on_payment_success(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    _set_stock(product_id, on_hand=2, reserved=0)

    r = client.post(
        "/api/customer/checkout/start",
        json={"customer_id": customer_id, "items": [{"product_id": product_id, "qty": 2}], "channel": "WEB"},
    )
    assert r.status_code == 200
    order_id = int(r.json()["order_id"])

    r = client.post(
        f"/api/customer/orders/{order_id}/simulate-payment?customer_id={customer_id}",
        json={"success": True},
    )
    assert r.status_code == 200

    on_hand, reserved = _get_stock(product_id)
    assert on_hand == 0
    assert reserved == 0
