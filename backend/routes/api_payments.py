from __future__ import annotations

import base64
import hmac
import json
import os
from hashlib import sha256
from typing import Any, Dict, Optional

import httpx
import psycopg
from fastapi import APIRouter, Header, HTTPException, Request

from ..db import get_conn
from ..inventory import consume_inventory, release_inventory
from ..models import RazorpayConfirmIn, RazorpayConfirmOut, RazorpayCreateOrderOut
from ..security import decode_access_token, parse_bearer_token


router = APIRouter(prefix="/api/payments", tags=["payments"])


def _customer_id_from_authorization(authorization: str | None) -> int:
    token_str = parse_bearer_token(authorization)
    if not token_str:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    payload = decode_access_token(token_str)
    cid = payload.get("customer_id")
    if cid is None:
        raise HTTPException(status_code=401, detail="Invalid token (missing customer_id)")
    return int(cid)


def _razorpay_key_id() -> str:
    v = (os.getenv("RAZORPAY_KEY_ID", "") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Razorpay not configured (missing RAZORPAY_KEY_ID)")
    return v


def _razorpay_key_secret() -> str:
    v = (os.getenv("RAZORPAY_KEY_SECRET", "") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Razorpay not configured (missing RAZORPAY_KEY_SECRET)")
    return v


def _razorpay_webhook_secret() -> str:
    v = (os.getenv("RAZORPAY_WEBHOOK_SECRET", "") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Razorpay not configured (missing RAZORPAY_WEBHOOK_SECRET)")
    return v


def _basic_auth_header(user: str, password: str) -> str:
    raw = f"{user}:{password}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"Basic {b64}"


def _verify_razorpay_signature(*, body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), msg=body, digestmod=sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@router.post("/razorpay/order")
def razorpay_create_order(
    order_id: int,
    authorization: str | None = Header(None, alias="Authorization"),
 ) -> RazorpayCreateOrderOut:
    customer_id = _customer_id_from_authorization(authorization)

    with get_conn() as conn:
        conn.execute("SET TIME ZONE 'UTC';", prepare=False)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.customer_id, o.order_status, o.net_amount,
                       p.payment_id, p.payment_status
                FROM globalcart.fact_orders o
                JOIN globalcart.fact_payments p ON p.order_id = o.order_id
                WHERE o.order_id = %s
                ORDER BY p.payment_id DESC
                LIMIT 1;
                """,
                (int(order_id),),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Order not found")

            if int(row[0]) != int(customer_id):
                raise HTTPException(status_code=403, detail="Order does not belong to this customer")

            order_status = str(row[1] or "").upper()
            amount = float(row[2] or 0.0)
            payment_id = int(row[3])
            payment_status = str(row[4] or "").upper()

            if order_status not in {"ORDER_CREATED"}:
                raise HTTPException(status_code=400, detail=f"Order not in payable state: {order_status}")
            if payment_status not in {"PAYMENT_PENDING"}:
                raise HTTPException(status_code=400, detail=f"Payment not pending: {payment_status}")

    # Razorpay expects amount in paise.
    amount_paise = int(round(amount * 100))

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"gc_order_{int(order_id)}",
        "notes": {"globalcart_order_id": str(int(order_id)), "customer_id": str(int(customer_id))},
    }

    auth = _basic_auth_header(_razorpay_key_id(), _razorpay_key_secret())

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.razorpay.com/v1/orders",
                headers={"Authorization": auth, "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Razorpay order create failed: {resp.text}")
        data = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Razorpay request failed: {e}")

    rp_order_id = str(data.get("id") or "").strip()
    if not rp_order_id:
        raise HTTPException(status_code=502, detail="Razorpay response missing order id")

    now_sql = "NOW() AT TIME ZONE 'UTC'"

    try:
        with get_conn() as conn:
            conn.execute("SET TIME ZONE 'UTC';", prepare=False)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE globalcart.fact_payments
                    SET payment_provider = 'RAZORPAY', payment_provider_order_id = %s, updated_at = NOW()
                    WHERE payment_id = %s;
                    """,
                    (rp_order_id, int(payment_id)),
                )

                cur.execute(
                    """
                    INSERT INTO globalcart.payment_provider_refs (payment_id, provider, provider_order_id, created_at, updated_at)
                    VALUES (%s, 'RAZORPAY', %s, NOW(), NOW())
                    ON CONFLICT (payment_id) DO UPDATE SET
                      provider = EXCLUDED.provider,
                      provider_order_id = EXCLUDED.provider_order_id,
                      updated_at = EXCLUDED.updated_at;
                    """,
                    (int(payment_id), rp_order_id),
                )

            conn.commit()
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "order_id": int(order_id),
        "payment_id": int(payment_id),
        "razorpay_key_id": _razorpay_key_id(),
        "razorpay_order_id": rp_order_id,
        "amount_paise": amount_paise,
        "currency": "INR",
    }


@router.post("/razorpay/confirm", response_model=RazorpayConfirmOut)
def razorpay_confirm_payment(
    req: RazorpayConfirmIn,
    authorization: str | None = Header(None, alias="Authorization"),
) -> RazorpayConfirmOut:
    customer_id = _customer_id_from_authorization(authorization)

    order_id = int(req.order_id)
    rp_order_id = str(req.razorpay_order_id or "").strip()
    rp_payment_id = str(req.razorpay_payment_id or "").strip()
    rp_signature = str(req.razorpay_signature or "").strip()
    if not (rp_order_id and rp_payment_id and rp_signature):
        raise HTTPException(status_code=400, detail="Missing Razorpay confirmation fields")

    # Razorpay checkout signature verification
    msg = f"{rp_order_id}|{rp_payment_id}".encode("utf-8")
    digest = hmac.new(_razorpay_key_secret().encode("utf-8"), msg=msg, digestmod=sha256).hexdigest()
    if not hmac.compare_digest(digest, rp_signature):
        raise HTTPException(status_code=401, detail="Invalid Razorpay signature")

    try:
        with get_conn() as conn:
            conn.execute("SET TIME ZONE 'UTC';", prepare=False)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.customer_id,
                           o.order_status,
                           p.payment_id,
                           p.payment_status
                    FROM globalcart.fact_orders o
                    JOIN globalcart.fact_payments p ON p.order_id = o.order_id
                    WHERE o.order_id = %s
                    ORDER BY p.payment_id DESC
                    LIMIT 1;
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="Order not found")
                if int(row[0]) != int(customer_id):
                    raise HTTPException(status_code=403, detail="Order does not belong to this customer")

                existing_order_status = str(row[1] or "").upper()
                payment_id = int(row[2])
                existing_payment_status = str(row[3] or "").upper()

                # Idempotency: if already success/confirmed, just return current state.
                if existing_payment_status == "PAYMENT_SUCCESS" and existing_order_status == "ORDER_CONFIRMED":
                    return RazorpayConfirmOut(
                        order_id=order_id,
                        payment_id=payment_id,
                        order_status=existing_order_status,
                        payment_status=existing_payment_status,
                    )

                if existing_payment_status not in {"PAYMENT_PENDING"}:
                    raise HTTPException(status_code=400, detail=f"Payment not pending: {existing_payment_status}")
                if existing_order_status not in {"ORDER_CREATED"}:
                    raise HTTPException(status_code=400, detail=f"Order not in payable state: {existing_order_status}")

                consume_inventory(conn, order_id=int(order_id))

                cur.execute(
                    """
                    UPDATE globalcart.fact_payments
                    SET payment_provider = 'RAZORPAY',
                        payment_provider_order_id = %s,
                        payment_provider_payment_id = %s,
                        payment_provider_signature = %s,
                        payment_status = 'PAYMENT_SUCCESS',
                        captured_ts = NOW(),
                        updated_at = NOW()
                    WHERE payment_id = %s;
                    """,
                    (rp_order_id, rp_payment_id, rp_signature, payment_id),
                )

                cur.execute(
                    """
                    INSERT INTO globalcart.payment_provider_refs (payment_id, provider, provider_order_id, provider_payment_id, provider_signature, updated_at)
                    VALUES (%s, 'RAZORPAY', %s, %s, %s, NOW())
                    ON CONFLICT (payment_id) DO UPDATE SET
                      provider='RAZORPAY',
                      provider_order_id=EXCLUDED.provider_order_id,
                      provider_payment_id=EXCLUDED.provider_payment_id,
                      provider_signature=EXCLUDED.provider_signature,
                      updated_at=EXCLUDED.updated_at;
                    """,
                    (payment_id, rp_order_id, rp_payment_id, rp_signature),
                )

                cur.execute(
                    """
                    UPDATE globalcart.fact_orders
                    SET order_status = 'ORDER_CONFIRMED', updated_at = NOW()
                    WHERE order_id = %s;
                    """,
                    (order_id,),
                )

            conn.commit()

        return RazorpayConfirmOut(
            order_id=order_id,
            payment_id=payment_id,
            order_status="ORDER_CONFIRMED",
            payment_status="PAYMENT_SUCCESS",
        )

    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(None, alias="X-Razorpay-Signature")):
    body = await request.body()
    secret = _razorpay_webhook_secret()

    if not _verify_razorpay_signature(body=body, signature=x_razorpay_signature, secret=secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = str(payload.get("id") or "").strip()
    event_type = str(payload.get("event") or "").strip()
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    entity = (((payload.get("payload") or {}).get("payment") or {}).get("entity") or {})
    rp_order_id = str(entity.get("order_id") or "").strip() or None
    rp_payment_id = str(entity.get("id") or "").strip() or None

    new_payment_status: Optional[str] = None
    new_order_status: Optional[str] = None
    failure_reason: Optional[str] = None

    if event_type == "payment.captured":
        new_payment_status = "PAYMENT_SUCCESS"
        new_order_status = "ORDER_CONFIRMED"
    elif event_type == "payment.failed":
        new_payment_status = "PAYMENT_FAILED"
        new_order_status = "ORDER_CANCELLED"
        failure_reason = str(entity.get("error_description") or entity.get("error_reason") or "PAYMENT_FAILED")[:80]
    else:
        # Store event for audit but do not change states
        new_payment_status = None
        new_order_status = None

    order_id: Optional[int] = None
    payment_id: Optional[int] = None

    try:
        with get_conn() as conn:
            conn.execute("SET TIME ZONE 'UTC';", prepare=False)
            with conn.cursor() as cur:
                # Insert event (idempotency). If already processed, return early.
                cur.execute(
                    """
                    INSERT INTO globalcart.payment_webhook_events (provider, event_id, event_type, payload, signature)
                    VALUES ('RAZORPAY', %s, %s, %s::jsonb, %s)
                    ON CONFLICT (provider, event_id) DO NOTHING
                    RETURNING event_id;
                    """,
                    (event_id, event_type, json.dumps(payload), x_razorpay_signature),
                )
                inserted = cur.fetchone() is not None
                if not inserted:
                    conn.commit()
                    return {"received": True, "event_id": event_id, "duplicate": True}

                if rp_order_id:
                    cur.execute(
                        """
                        SELECT p.order_id, p.payment_id
                        FROM globalcart.fact_payments p
                        WHERE p.payment_provider_order_id = %s
                        ORDER BY p.payment_id DESC
                        LIMIT 1;
                        """,
                        (rp_order_id,),
                    )
                    ref = cur.fetchone()
                    if ref is not None:
                        order_id = int(ref[0])
                        payment_id = int(ref[1])

                # Backfill event linkage once we know the internal ids.
                cur.execute(
                    """
                    UPDATE globalcart.payment_webhook_events
                    SET order_id = %s, payment_id = %s
                    WHERE provider='RAZORPAY' AND event_id=%s;
                    """,
                    (order_id, payment_id, event_id),
                )

                if payment_id is not None and order_id is not None:
                    if new_payment_status == "PAYMENT_SUCCESS":
                        consume_inventory(conn, order_id=int(order_id))
                    elif new_payment_status == "PAYMENT_FAILED":
                        release_inventory(conn, order_id=int(order_id))

                    cur.execute(
                        """
                        UPDATE globalcart.fact_payments
                        SET payment_status = COALESCE(%s, payment_status),
                            payment_provider = 'RAZORPAY',
                            payment_provider_order_id = COALESCE(%s, payment_provider_order_id),
                            payment_provider_payment_id = COALESCE(%s, payment_provider_payment_id),
                            payment_provider_signature = COALESCE(%s, payment_provider_signature),
                            failure_reason = COALESCE(%s, failure_reason),
                            captured_ts = CASE WHEN %s = 'PAYMENT_SUCCESS' THEN NOW() ELSE captured_ts END,
                            updated_at = NOW()
                        WHERE payment_id = %s;
                        """,
                        (
                            new_payment_status,
                            rp_order_id,
                            rp_payment_id,
                            x_razorpay_signature,
                            failure_reason,
                            new_payment_status,
                            int(payment_id),
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO globalcart.payment_provider_refs (payment_id, provider, provider_order_id, provider_payment_id, provider_signature, updated_at)
                        VALUES (%s, 'RAZORPAY', %s, %s, %s, NOW())
                        ON CONFLICT (payment_id) DO UPDATE SET
                          provider='RAZORPAY',
                          provider_order_id=EXCLUDED.provider_order_id,
                          provider_payment_id=EXCLUDED.provider_payment_id,
                          provider_signature=EXCLUDED.provider_signature,
                          updated_at=EXCLUDED.updated_at;
                        """,
                        (int(payment_id), rp_order_id, rp_payment_id, x_razorpay_signature),
                    )

                if order_id is not None and new_order_status is not None:
                    cur.execute(
                        """
                        UPDATE globalcart.fact_orders
                        SET order_status = %s, updated_at = NOW()
                        WHERE order_id = %s;
                        """,
                        (new_order_status, int(order_id)),
                    )

            conn.commit()

    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "received": True,
        "event_id": event_id,
        "event_type": event_type,
        "order_id": order_id,
        "payment_id": payment_id,
    }
