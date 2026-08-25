CREATE SCHEMA IF NOT EXISTS globalcart;

CREATE TABLE IF NOT EXISTS globalcart.pipeline_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(50) NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    rows_processed INTEGER,
    duration_seconds DOUBLE PRECISION,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_audit_run_id ON globalcart.pipeline_audit (run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_audit_created_at ON globalcart.pipeline_audit (created_at DESC);
