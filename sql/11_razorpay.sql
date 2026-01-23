CREATE SCHEMA IF NOT EXISTS globalcart;

CREATE TABLE IF NOT EXISTS globalcart.payment_provider_refs (
  payment_id BIGINT PRIMARY KEY REFERENCES globalcart.fact_payments(payment_id) ON DELETE CASCADE,
  provider VARCHAR(30) NOT NULL,
  provider_order_id VARCHAR(80) NULL,
  provider_payment_id VARCHAR(80) NULL,
  provider_signature VARCHAR(256) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_provider_refs_provider_order
ON globalcart.payment_provider_refs (provider, provider_order_id);

CREATE TABLE IF NOT EXISTS globalcart.payment_webhook_events (
  provider VARCHAR(30) NOT NULL,
  event_id VARCHAR(120) NOT NULL,
  event_type VARCHAR(120) NOT NULL,
  order_id BIGINT NULL,
  payment_id BIGINT NULL,
  payload JSONB NOT NULL,
  signature VARCHAR(256) NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (provider, event_id)
);

ALTER TABLE IF EXISTS globalcart.fact_payments
  ADD COLUMN IF NOT EXISTS payment_provider_order_id VARCHAR(80);

ALTER TABLE IF EXISTS globalcart.fact_payments
  ADD COLUMN IF NOT EXISTS payment_provider_payment_id VARCHAR(80);

ALTER TABLE IF EXISTS globalcart.fact_payments
  ADD COLUMN IF NOT EXISTS payment_provider_signature VARCHAR(256);
