# GlobalScart Data Engineering Platform Architecture

This document details the production-grade data platform architecture designed for GlobalScart. It covers the data lifecycle from the transactional PostgreSQL database through to the Google Cloud BigQuery data warehouse.

---

## 1. System Topology & Pipeline Flow

The platform implements an automated, orchestrated, and validated ELT (Extract-Load-Transform) architecture:

```mermaid
sequenceDiagram
    autonumber
    participant PG as PostgreSQL (OLTP)
    participant Ext as Python Ingestion (postgres_extractor)
    participant Raw as Raw Zone (CSVs)
    participant DQ as Python Validation (data_quality)
    participant Spark as PySpark Engine (transform_ecommerce)
    participant Proc as Processed Zone (Parquet)
    participant SV as Spark Validation (spark_validation)
    participant BQ as Google BigQuery (DWH)
    participant Rec as Migration Reconciler (reconciler)
    participant Audit as DB Audit (pipeline_audit)

    Note over PG, Audit: Orchestrated by Apache Airflow (hourly schedules)

    Ext->>PG: Query incremental changes since last watermark
    PG-->>Ext: Return delta records
    Ext->>Raw: Write CSV files (dim_customer, fact_orders, etc.)
    Ext->>Audit: Record step telemetry (STARTED/SUCCESS, duration, row counts)
    
    DQ->>Raw: Read CSVs and apply checks (Null, Unique, Range)
    DQ-->>Audit: Record validation stats
    
    Spark->>Raw: Load raw tables from directory
    Spark->>Spark: Deduplicate & join (Star Schema fact_sales)
    Spark->>Proc: Write partitioned Parquet files (by order_year, order_month)
    Spark-->>Audit: Record transformation row counts
    
    SV->>Proc: Load Parquet files
    SV->>SV: Validate referential integrity & financial totals
    SV-->>Audit: Record validation telemetry
    
    BQ->>Proc: Read Parquet files
    BQ->>BQ: Atomic load (truncate & replace), partition (order_date), cluster (customer_id, product_id)
    BQ-->>Audit: Record load telemetry
    
    Rec->>PG: Query active window transactional aggregates
    Rec->>BQ: Query active window warehouse aggregates
    Rec->>Rec: Reconcile row counts & financial sums
    Rec-->>Audit: Record final reconciliation telemetry
```

---

## 2. Ingestion & Incrementality (Watermarking)

Transactional source tables (`dim_customer`, `fact_orders`, `fact_order_items`, `fact_payments`, `fact_shipments`) are extracted incrementally using **updated_at watermarks**. 
* **State Management**: Watermarks are tracked locally in `data_platform/metadata/watermarks.json` to allow checkpoint restarts.
* **Extraction Strategy**:
  - Incremental extracts read changes since `max(updated_at)` of the previous run.
  - Raw files are written to table-specific timestamped files: `load_YYYYMMDD_HHMMSS.csv`.
  - PySpark reads the entire folder matching `data_platform/data/raw/postgres/<table>/*.csv`, automatically consolidating past runs with incremental delta records.

---

## 3. Data Processing & Optimizations (PySpark)

PySpark transformations convert raw transactional tables into an analytical **Star Schema**:
* **Deduplication**: Resolves duplicate records from multiple source runs using window functions ordered by `updated_at DESC`.
* **Fact Table Generation**: Links orders, items, payments, and shipments together into a consolidated `fact_sales` grain.
* **Spark Local Performance Optimizations**:
  - `spark.sql.shuffle.partitions` is set to `8` to minimize task serialization/network overhead in single-node/local simulation runs.
  - Adaptive Query Execution (AQE) is enabled (`spark.sql.adaptive.enabled = true`) for dynamic partition coalescing.
  - Local memory allocations are explicitly limited (`spark.driver.memory = 2g`, `spark.executor.memory = 2g`) to prevent out-of-memory heap space exhaustion.

---

## 4. Analytical Warehouse Layout (BigQuery)

Analytical datasets are ingested into **Google Cloud BigQuery** under the `globalcart_analytics` dataset:
* **Partitioning**: The `fact_sales` table is partitioned daily on the `order_date` column. This minimizes query scan costs by restricting reads to active date partitions.
* **Clustering**: Configured with cluster keys `['customer_id', 'product_id']`. This clusters rows with matching IDs within each partition block to optimize drill-down queries.
* **Atomic Transactions**: Ingestion uses BigQuery `WRITE_TRUNCATE` configuration to ensure loads are idempotent, safe for retries, and completely atomic.

---

## 5. Observability, Auditing, & Self-Healing

The system includes a centralized PostgreSQL audit logger (`globalcart.pipeline_audit`) driven by a context manager (`PipelineObserver`):
* **Telemetry Fields**:
  - `run_id`: Unique identifier sharing run scope between standalone steps (local runtime state file or Airflow execution run ID).
  - `step_name`: The pipeline module (e.g. `ingestion`, `spark_transformation`, `bigquery_load`).
  - `status`: Execution state (`STARTED`, `SUCCESS`, `FAILED`).
  - `rows_processed`: Row counts or metric tallies.
  - `duration_seconds`: Step duration.
  - `error_message`: Stack trace captures on exception.
* **Active Partition Reconciliation**: The BigQuery Sandbox environment enforces a strict 60-day partition expiration limit. The end-to-end `reconciler.py` handles this dynamically:
  1. Fetches the minimum partition date present in BigQuery.
  2. Queries PostgreSQL source database aggregates matching only that active date window.
  3. Reconciles BigQuery warehouse aggregates with Postgres, achieving a 100% accurate reconciliation matrix.
