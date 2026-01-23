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


def _ensure_stock(product_id: int, on_hand: int) -> None:
    with psycopg.connect(_dsn()) as conn:
        conn.execute("SET TIME ZONE 'UTC';", prepare=False)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO globalcart.product_inventory (product_id, on_hand_qty, reserved_qty)
                VALUES (%s, %s, 0)
                ON CONFLICT (product_id) DO UPDATE
                SET on_hand_qty = GREATEST(globalcart.product_inventory.on_hand_qty, EXCLUDED.on_hand_qty),
                    reserved_qty = 0,
                    updated_at = NOW();
                """,
                (int(product_id), int(on_hand)),
            )
        conn.commit()


@pytest.fixture(scope="session")
def client():
    if not _db_available():
        pytest.skip("PostgreSQL not reachable; set PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD to run API tests")

    with TestClient(app) as c:
        yield c


def test_products_returns_list(client: TestClient):
    r = client.get("/api/customer/products?limit=3&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 3


def test_orders_inserts_order(client: TestClient):
    products = client.get("/api/customer/products?limit=1&offset=0").json()
    assert products and isinstance(products, list)
    pid = int(products[0]["product_id"])

    _ensure_stock(pid, on_hand=20)

    # Resolve a stable customer_id for tests
    rr = client.post("/api/customer/resolve", json={"email": "test@example.com"})
    assert rr.status_code == 200
    customer_id = int(rr.json()["customer_id"])

    # Use the transactional checkout flow (creates ORDER_CREATED + PAYMENT_PENDING)
    r = client.post(
        "/api/customer/checkout/start",
        json={"customer_id": customer_id, "items": [{"product_id": pid, "qty": 1}], "channel": "WEB"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "order_id" in data
    assert "payment_id" in data


def test_kpis_latest(client: TestClient):
    r = client.get("/api/admin/kpis/latest", headers={"X-Admin-Key": os.getenv("ADMIN_KEY", "admin")})
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "metrics" in data
        assert "orders_total" in data["metrics"]
