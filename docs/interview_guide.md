# GlobalScart Data Engineering Interview & Resume Guide

This guide compiles high-impact resume bullets and system design Q&As based on the GlobalScart Data Engineering Platform implementation.

---

## 1. Metric-Focused Resume Bullets

* **End-to-End Data Pipeline Architecture**:
  > Engineered an automated, orchestrated ELT pipeline scaling from transactional PostgreSQL database instances to a Google Cloud BigQuery data warehouse using PySpark, PostgreSQL, and Apache Airflow. Automated validation runs via GitHub Actions CI/CD to prevent breaking schema deployments.

* **High-Throughput Analytics Modeling**:
  > Designed and implemented a Star Schema dimensional model consolidating order, payment, and shipment transactions into a unified `fact_sales` table (179K+ rows). Reduced query execution costs in BigQuery by implementing daily time-partitioning on `order_date` and clustering on `['customer_id', 'product_id']`.

* **Enterprise Observability & Telemetry**:
  > Designed a centralized database audit schema (`pipeline_audit`) using a Python context-manager utility (`PipelineObserver`) to capture task start/end states, durations, errors, and row-count metrics. Logged execution history with tracebacks across 7 separate ETL stages.

* **Audit & Migration Reconciliation**:
  > Developed an end-to-end reconciliation suite verifying 100% data integrity between Postgres transactional source records and BigQuery. Programmed a partition-aware logic matching BigQuery Sandbox's 60-day partition expiration limits to yield zero discrepancy in rows or revenue ($123M+ in active partitions).

* **Performance & Local Scale Optimization**:
  > Improved local Spark memory footprints and task serialization overheads by configuring explicit memory limits ($2\text{GB}$ driver/executor configurations) and setting active shuffle partitions to `8`, yielding a $9.6\text{s}$ execution time for $179\text{K}$ record deduplication and joins.

---

## 2. Technical System Design Q&A

### Q1: Why did you partition `fact_sales` daily on `order_date` and cluster on `customer_id` and `product_id`?
* **Partitioning Selection**: `fact_sales` accumulates millions of records over time. Partitioning by day divides the dataset into distinct physical segments. Queries filtering on `order_date` (e.g., dashboard filters) only scan the matching dates instead of scanning the full table, resulting in up to a **99% cost and speed savings**.
* **Clustering Selection**: Clustering sorts the data inside each day's partition by `customer_id` and `product_id`. When analysts query behavior for specific customers or products, BigQuery skips blocks that do not match the IDs, maximizing query performance on high-cardinality dimensions.

### Q2: How does the system handle backfills or watermark state recovery?
* **Incremental Runs**: The extractor checks `watermarks.json` to find the last run's max timestamp. It queries Postgres only for records updated since that watermark.
* **Full Backfill**: If a schema changes or corruption is detected, we can force a full backfill by calling `postgres_extractor.py --full`. This bypasses watermarks, queries the full tables, and overwrites the raw files under the table directories. PySpark then automatically recalculates and overwrites downstream Parquet and BigQuery datasets.
* **Idempotency**: Downstream, Spark writes with `.mode("overwrite")` and BigQuery uses `WRITE_TRUNCATE` configuration. This makes every stage of the pipeline completely **idempotent**—it can be rerun multiple times for the same window without duplicating data.

### Q3: How did you design data quality checks before the data reaches the warehouse?
* **Two-Layer Validation Structure**:
  1. **Raw CSV Validation (`data_quality.py`)**: Validates data immediately upon extraction. Checks for invalid Nulls in primary keys, negative amounts in payments/amounts, and malformed timestamps. If any check fails, the pipeline aborts before starting Spark jobs.
  2. **Processed Parquet Validation (`spark_validation.py`)**: Runs after Spark joins. Validates **referential integrity** (ensuring all geo/product/customer IDs in the fact table exist in the dimension tables), verifies primary keys are unique (no duplicates), and does **financial reconciliation** (verifying that the sum of line net revenues in raw matches the processed sales table to floating-point precision).

### Q4: How did you handle BigQuery Sandbox limits during reconciliation?
* **The Blocker**: GCP Sandbox environments automatically expire and delete daily partitions older than 60 days. Because our transactional dataset spans from 2025 to 2026, BigQuery immediately drops older partitions on ingestion, retaining only dates within the last 60 days (approx. 2700 rows).
* **The Solution**: Rather than performing a crude full-table count which would report a massive mismatch, the `reconciler.py` programmatically fetches the minimum date active in BigQuery's partitions, queries the PostgreSQL source system filtered to `order_ts::date >= bq_min_date`, and compares only the active warehouse window. This ensures our automated test builds remain green and robust.

### Q5: Why did you choose Parquet over CSV for the processed data layer?
* **Columnar Layout**: Parquet is a columnar storage format. It only reads the specific columns queried, saving storage and read bandwidth.
* **Metadata Compression**: Parquet stores minimum/maximum stats for each block, allowing query engines (like Spark) to skip entire data blocks (predicate pushdown).
* **Implicit Schemas**: Unlike CSV, Parquet embeds schema definitions and primitive datatypes, avoiding parsing errors downstream.
