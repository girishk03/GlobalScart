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
    # Resolve or create a test customer; reuse existing if present
    r = client.post(
        "/api/customer/resolve",
        json={"email": "test@example.com"},
    )
    assert r.status_code == 200
    return int(r.json()["customer_id"])


def _pick_any_product(client: TestClient) -> int:
    r = client.get("/api/customer/products?limit=1&offset=0")
    assert r.status_code == 200
    products = r.json()
    assert products and isinstance(products, list)
    return int(products[0]["product_id"])


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


def _get_inventory(product_id: int) -> tuple[int, int]:
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT on_hand_qty, reserved_qty FROM globalcart.product_inventory WHERE product_id = %s;",
                (int(product_id),),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row[0]), int(row[1])


def _get_reservation(order_id: int, product_id: int) -> tuple[int, str]:
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT qty, status
                FROM globalcart.order_inventory_reservations
                WHERE order_id = %s AND product_id = %s;
                """,
                (int(order_id), int(product_id)),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row[0]), str(row[1])


def _get_order_payment_state(order_id: int, payment_id: int) -> tuple[str, str]:
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.order_status, p.payment_status
                FROM globalcart.fact_orders o
                JOIN globalcart.fact_payments p ON p.order_id = o.order_id
                WHERE o.order_id = %s AND p.payment_id = %s;
                """,
                (int(order_id), int(payment_id)),
            )
            row = cur.fetchone()
            assert row is not None
            return str(row[0]), str(row[1])


def _count_customer_orders(customer_id: int) -> int:
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM globalcart.fact_orders WHERE customer_id = %s;",
                (int(customer_id),),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row[0])


def test_checkout_success_flow(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    _ensure_stock(product_id, on_hand=20)

    # Add to cart
    r = client.post(
        f"/api/customer/cart?customer_id={customer_id}",
        json={"product_id": product_id, "qty": 2},
    )
    assert r.status_code == 200

    # Start checkout (creates ORDER_CREATED + PAYMENT_PENDING)
    r = client.post(
        "/api/customer/checkout/start",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "qty": 2}],
            "channel": "WEB",
        },
    )
    assert r.status_code == 200
    checkout = r.json()
    assert "order_id" in checkout
    assert "payment_id" in checkout
    assert checkout["order_status"] == "ORDER_CREATED"
    assert checkout["payment_status"] == "PAYMENT_PENDING"
    order_id = int(checkout["order_id"])
    payment_id = int(checkout["payment_id"])

    reserved_qty, reservation_status = _get_reservation(order_id, product_id)
    assert reserved_qty == 2
    assert reservation_status == "RESERVED"

    # Simulate payment success
    r = client.post(
        f"/api/customer/orders/{order_id}/simulate-payment?customer_id={customer_id}",
        json={"success": True},
    )
    assert r.status_code == 200
    result = r.json()
    assert result["order_status"] == "ORDER_CONFIRMED"
    assert result["payment_status"] == "PAYMENT_SUCCESS"
    assert result["order_id"] == order_id
    assert result["payment_id"] == payment_id

    order_status, payment_status = _get_order_payment_state(order_id, payment_id)
    assert order_status == "ORDER_CONFIRMED"
    assert payment_status == "PAYMENT_SUCCESS"

    _, reserved_after_payment = _get_inventory(product_id)
    assert reserved_after_payment == 0


def test_checkout_cancellation_releases_inventory(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)
    _ensure_stock(product_id, on_hand=20)
    on_hand_before, _ = _get_inventory(product_id)

    response = client.post(
        "/api/customer/checkout/start",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "qty": 1}],
            "channel": "WEB",
        },
    )
    assert response.status_code == 200
    order_id = int(response.json()["order_id"])
    assert _get_reservation(order_id, product_id) == (1, "RESERVED")

    response = client.post(
        f"/api/customer/orders/{order_id}/cancel",
        json={"customer_id": customer_id, "reason": "Test cancellation"},
    )
    assert response.status_code == 200
    assert response.json()["order_status"] == "CANCELLED"

    assert _get_reservation(order_id, product_id) == (1, "RELEASED")
    on_hand_after, reserved_after = _get_inventory(product_id)
    assert on_hand_after == on_hand_before
    assert reserved_after == 0


def test_checkout_failure_flow(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    _ensure_stock(product_id, on_hand=20)

    # Start checkout
    r = client.post(
        "/api/customer/checkout/start",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "qty": 1}],
            "channel": "WEB",
        },
    )
    assert r.status_code == 200
    checkout = r.json()
    order_id = int(checkout["order_id"])

    # Simulate payment failure
    r = client.post(
        f"/api/customer/orders/{order_id}/simulate-payment?customer_id={customer_id}",
        json={"success": False, "failure_reason": "BANK_DOWN"},
    )
    assert r.status_code == 200
    result = r.json()
    assert result["order_status"] == "ORDER_CANCELLED"
    assert result["payment_status"] == "PAYMENT_FAILED"
    assert result["order_id"] == order_id


def test_checkout_rollback_on_invalid_product(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    orders_before = _count_customer_orders(customer_id)

    # Attempt checkout with an invalid product_id (should rollback)
    r = client.post(
        "/api/customer/checkout/start",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": 999999, "qty": 1}],
            "channel": "WEB",
        },
    )
    assert r.status_code == 400
    assert _count_customer_orders(customer_id) == orders_before


def test_cart_persistence_and_totals(client: TestClient):
    customer_id = _ensure_test_customer_exists(client)
    product_id = _pick_any_product(client)

    _ensure_stock(product_id, on_hand=50)

    # Clear cart first
    client.delete(f"/api/customer/cart?customer_id={customer_id}")

    # Add items
    client.post(
        f"/api/customer/cart?customer_id={customer_id}",
        json={"product_id": product_id, "qty": 2},
    )
    client.post(
        f"/api/customer/cart?customer_id={customer_id}",
        json={"product_id": product_id, "qty": 1},
    )

    # Get cart summary
    r = client.get(f"/api/customer/cart?customer_id={customer_id}")
    assert r.status_code == 200
    cart = r.json()
    assert cart["customer_id"] == customer_id
    assert isinstance(cart["items"], list)
    # Expect one line item (merged qty)
    assert len(cart["items"]) == 1
    line = cart["items"][0]
    assert line["product_id"] == product_id
    assert line["qty"] == 3
    assert "gross_amount" in cart
    assert "net_amount" in cart
    assert isinstance(cart["gross_amount"], (int, float))
    assert isinstance(cart["net_amount"], (int, float))

    # Clear cart
    r = client.delete(f"/api/customer/cart?customer_id={customer_id}")
    assert r.status_code == 200

    # Verify empty
    r = client.get(f"/api/customer/cart?customer_id={customer_id}")
    assert r.status_code == 200
    assert r.json()["items"] == []
