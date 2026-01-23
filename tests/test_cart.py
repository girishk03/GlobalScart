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


def test_cart_add_update_remove(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    client.delete(f"/api/customer/cart?customer_id={customer_id}")

    r = client.post(f"/api/customer/cart?customer_id={customer_id}", json={"product_id": product_id, "qty": 2})
    assert r.status_code == 200

    r = client.put(f"/api/customer/cart?customer_id={customer_id}", json={"product_id": product_id, "qty": 3})
    assert r.status_code == 200

    r = client.get(f"/api/customer/cart?customer_id={customer_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["customer_id"] == customer_id
    assert len(data["items"]) == 1
    assert int(data["items"][0]["qty"]) == 3

    r = client.delete(f"/api/customer/cart?customer_id={customer_id}&product_id={product_id}")
    assert r.status_code == 200

    r = client.get(f"/api/customer/cart?customer_id={customer_id}")
    assert r.status_code == 200
    assert r.json()["items"] == []
