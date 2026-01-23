CREATE SCHEMA IF NOT EXISTS globalcart;

CREATE TABLE IF NOT EXISTS globalcart.product_inventory (
  product_id BIGINT PRIMARY KEY REFERENCES globalcart.dim_product(product_id),
  on_hand_qty INTEGER NOT NULL CHECK (on_hand_qty >= 0),
  reserved_qty INTEGER NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_inventory_updated_at
ON globalcart.product_inventory (updated_at DESC);

CREATE TABLE IF NOT EXISTS globalcart.order_inventory_reservations (
  reservation_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES globalcart.fact_orders(order_id) ON DELETE CASCADE,
  product_id BIGINT NOT NULL REFERENCES globalcart.dim_product(product_id),
  qty INTEGER NOT NULL CHECK (qty >= 1),
  status VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_order_inventory_reservations_order_status
ON globalcart.order_inventory_reservations (order_id, status);

INSERT INTO globalcart.product_inventory (product_id, on_hand_qty, reserved_qty)
SELECT p.product_id,
       (25 + (p.product_id % 25))::int AS on_hand_qty,
       0
FROM globalcart.dim_product p
ON CONFLICT (product_id) DO NOTHING;
