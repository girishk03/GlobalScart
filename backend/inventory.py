from __future__ import annotations

from typing import Iterable, Tuple

from fastapi import HTTPException


def _require_inventory_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('globalcart.product_inventory');")
        if cur.fetchone()[0] is None:
            raise HTTPException(
                status_code=500,
                detail="Inventory tables not found. Run: python3 -m src.run_sql --sql sql/12_inventory.sql",
            )
        cur.execute("SELECT to_regclass('globalcart.order_inventory_reservations');")
        if cur.fetchone()[0] is None:
            raise HTTPException(
                status_code=500,
                detail="Inventory tables not found. Run: python3 -m src.run_sql --sql sql/12_inventory.sql",
            )


def reserve_inventory(conn, *, order_id: int, items: Iterable[Tuple[int, int]]) -> None:
    _require_inventory_tables(conn)

    item_list = [(int(pid), int(qty)) for (pid, qty) in items]
    if not item_list:
        raise HTTPException(status_code=400, detail="No items to reserve")

    qty_by_product = {}
    for pid, qty in item_list:
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Invalid qty")
        qty_by_product[pid] = qty_by_product.get(pid, 0) + qty

    product_ids = sorted(qty_by_product.keys())
    placeholders = ",".join(["%s"] * len(product_ids))

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT product_id, on_hand_qty, reserved_qty
            FROM globalcart.product_inventory
            WHERE product_id IN ({placeholders})
            FOR UPDATE;
            """,
            tuple(product_ids),
        )
        rows = cur.fetchall()

        found = {int(r[0]) for r in rows}
        missing = [pid for pid in product_ids if pid not in found]
        if missing:
            raise HTTPException(status_code=409, detail=f"Inventory missing for product_ids: {missing}")

        insufficient = []
        for r in rows:
            pid = int(r[0])
            on_hand = int(r[1])
            reserved = int(r[2])
            available = on_hand - reserved
            need = int(qty_by_product.get(pid, 0))
            if available < need:
                insufficient.append({"product_id": pid, "available": available, "requested": need})

        if insufficient:
            raise HTTPException(status_code=409, detail={"message": "Insufficient stock", "items": insufficient})

        for pid, need in qty_by_product.items():
            cur.execute(
                """
                UPDATE globalcart.product_inventory
                SET reserved_qty = reserved_qty + %s, updated_at = NOW()
                WHERE product_id = %s;
                """,
                (int(need), int(pid)),
            )

            cur.execute(
                """
                INSERT INTO globalcart.order_inventory_reservations (order_id, product_id, qty, status)
                VALUES (%s, %s, %s, 'RESERVED')
                ON CONFLICT (order_id, product_id) DO UPDATE
                SET qty = EXCLUDED.qty,
                    status = CASE WHEN globalcart.order_inventory_reservations.status = 'RESERVED' THEN 'RESERVED' ELSE globalcart.order_inventory_reservations.status END,
                    updated_at = NOW();
                """,
                (int(order_id), int(pid), int(need)),
            )


def consume_inventory(conn, *, order_id: int) -> None:
    _require_inventory_tables(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT product_id, qty
            FROM globalcart.order_inventory_reservations
            WHERE order_id = %s AND status = 'RESERVED'
            ORDER BY product_id
            FOR UPDATE;
            """,
            (int(order_id),),
        )
        rows = cur.fetchall()

        if not rows:
            return

        pids = [int(r[0]) for r in rows]
        placeholders = ",".join(["%s"] * len(pids))
        cur.execute(
            f"""
            SELECT product_id, on_hand_qty, reserved_qty
            FROM globalcart.product_inventory
            WHERE product_id IN ({placeholders})
            FOR UPDATE;
            """,
            tuple(pids),
        )

        inv = {int(r[0]): (int(r[1]), int(r[2])) for r in cur.fetchall()}

        for pid, qty in rows:
            pid = int(pid)
            qty = int(qty)
            if pid not in inv:
                raise HTTPException(status_code=500, detail=f"Inventory row missing for product_id={pid}")
            on_hand, reserved = inv[pid]
            if on_hand < qty:
                raise HTTPException(status_code=409, detail=f"Insufficient on_hand during consume for product_id={pid}")
            if reserved < qty:
                raise HTTPException(status_code=409, detail=f"Insufficient reserved during consume for product_id={pid}")

        for pid, qty in rows:
            cur.execute(
                """
                UPDATE globalcart.product_inventory
                SET on_hand_qty = on_hand_qty - %s,
                    reserved_qty = reserved_qty - %s,
                    updated_at = NOW()
                WHERE product_id = %s;
                """,
                (int(qty), int(qty), int(pid)),
            )

        cur.execute(
            """
            UPDATE globalcart.order_inventory_reservations
            SET status = 'CONSUMED', updated_at = NOW()
            WHERE order_id = %s AND status = 'RESERVED';
            """,
            (int(order_id),),
        )


def release_inventory(conn, *, order_id: int) -> None:
    _require_inventory_tables(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT product_id, qty
            FROM globalcart.order_inventory_reservations
            WHERE order_id = %s AND status = 'RESERVED'
            ORDER BY product_id
            FOR UPDATE;
            """,
            (int(order_id),),
        )
        rows = cur.fetchall()

        if not rows:
            return

        for pid, qty in rows:
            cur.execute(
                """
                UPDATE globalcart.product_inventory
                SET reserved_qty = GREATEST(0, reserved_qty - %s), updated_at = NOW()
                WHERE product_id = %s;
                """,
                (int(qty), int(pid)),
            )

        cur.execute(
            """
            UPDATE globalcart.order_inventory_reservations
            SET status = 'RELEASED', updated_at = NOW()
            WHERE order_id = %s AND status = 'RESERVED';
            """,
            (int(order_id),),
        )
