# GlobalScart Data Engineering Interview & Resume Guide

This guide compiles high-impact resume bullets, system topology, and system design Q&As based on the actual verified results and layout of the GlobalScart Data Engineering Platform.

---

## 1. Metric-Focused Resume Bullets

* **Data Ingestion & Extraction**:
  > Engineered an incremental, watermark-based ETL pipeline in Python using `updated_at` timestamps to capture daily transaction deltas from PostgreSQL, tracking watermark states locally to enable resume-from-failure logic.

* **Dimensional Modeling & PySpark Processing**:
  > Developed a distributed PySpark data processing engine to ingest, clean, and deduplicate e-commerce records, transforming them into a structured Star Schema (customer, product, location, date dimensions and a centralized `fact_sales` table of 179K+ rows). Capped local PySpark driver/executor memory at 2GB and configured 8 shuffle partitions to optimize memory overhead.

* **Warehouse Optimization & Ingestion**:
  > Designed a Google Cloud BigQuery data warehouse (globalcart_analytics) with daily time partitioning on `order_date` and clustering on `['customer_id', 'product_id']` for the `fact_sales` table to minimize query data scanning. Built an atomic loader using `WRITE_TRUNCATE` to guarantee run-level idempotency.

* **End-to-End Auditing & Reconciliation**:
  > Built a multi-stage validation suite comprising data quality constraints, Spark referential integrity validation, and end-to-end active-window reconciliations, achieving **0-row discrepancy** and **$0.00 financial variance** between source transactional PostgreSQL tables and the BigQuery warehouse (reconciling 179,814 fact rows and $7.996B of transactional volume).

* **Orchestration, Observability, & CI/CD**:
  > Orchestrated the ETL pipeline across 6 standalone stages using Apache Airflow. Built a logging auditing context-manager (`PipelineObserver`) to record duration, row counts, and exceptions into a Postgres audit table, and automated regression checks via GitHub Actions CI/CD to yield a **green 4m 52s build**.

---

## 2. Technical System Design Q&A

### Q1: Why PySpark instead of Pandas?
* **Answer**: *"While Pandas is ideal for single-node datasets that fit comfortably in memory, it loads the entire dataset into the driver process, causing it to crash with Out of Memory (OOM) errors as volume scales. PySpark builds a directed acyclic graph (DAG) of transformations and executes lazily, distributing processing partitions across a cluster. This allows us to scale processing capacity simply by adding nodes to a Dataproc cluster without changing our codebase."*

### Q2: Why Parquet?
* **Answer**: *"Parquet is a columnar storage format optimized for heavy read operations:
  1. **Column projection**: It reads only the bytes of the specific columns requested in a query, which is a major performance boost over parsing entire lines in CSV formats.
  2. **Metadata blocks**: Parquet stores min/max statistics for every row group, allowing Spark or BigQuery to skip scanning irrelevant blocks (predicate pushdown).
  3. **Schema encapsulation**: Parquet embeds data type definitions, avoiding data type mismatch issues during ingestion."*

### Q3: How does your watermarking differ from Change Data Capture (CDC)?
* **Answer**: *"My pipeline uses **watermark-based incremental ingestion**. The extractor queries PostgreSQL for records updated since the last recorded watermark (`WHERE updated_at > last_watermark`) and updates the state with the maximum timestamp in the batch. 
  
  This is different from **CDC**, which captures transactions at the database log level (e.g., streaming WAL write-ahead log updates via Debezium and Kafka). Watermarking is simpler to implement and debug for batch architectures but requires an index on `updated_at` and does not natively capture hard deletes or intermediary state updates."*

### Q4: Why did you partition `fact_sales` on `order_date` and cluster on `customer_id` and `product_id`?
* **Answer**: *"I partitioned by `order_date` daily because analytical queries almost always filter by date ranges (e.g., monthly sales). BigQuery only scans the specific partitions matching the filter rather than full tables. 
  
  Inside each daily partition, I clustered on `customer_id` and `product_id` to physically sort the rows by those columns. This allows BigQuery to skip blocks within the partition when queries query specific users or items."*

### Q5: What is the limitation of GCS in your current architecture?
* **Answer**: *"I designed and validated the raw landing zone GCS bucket using Terraform (including versioning, lifecycles, and uniform bucket access). However, due to sandbox billing account restrictions on my GCP project, I bypassed bucket creation. The pipeline instead writes raw CSVs locally, runs PySpark, and loads dataframes directly into BigQuery. This demonstrated the exact same logic and schemas, while operating within local resource sandbox constraints."*

### Q6: How do you handle schema updates in your BigQuery Loader?
* **Answer**: *"In our loader (`loader.py`), we use the `WRITE_TRUNCATE` write disposition, which ensures run-level idempotency by overwriting the table. If a schema change (like partitioning or clustering) is made, BigQuery will reject loading due to layout mismatch. To solve this, the loader inspects the existing table layout, detects partition scheme differences, and automatically deletes the table before reload, allowing the new schema to deploy without manual DBA interventions."*

### Q7: Why is WRITE_TRUNCATE not a complete enterprise incremental strategy?
* **Answer**: *"In this project, `WRITE_TRUNCATE` is used to load data cleanly and ensure idempotency during reruns. However, at enterprise scale (with billions of rows), full table truncation and rebuilds are too slow and expensive. A production incremental loading strategy would load raw data into a staging table and execute a SQL `MERGE` statement (upsert) to apply updates and inserts to the production target table."*

### Q8: How did you debug mixed timestamp formats in validation?
* **Answer**: *"During data quality validation of raw CSVs in `data_quality.py`, I encountered a real parsing error due to mixed timestamp formatting in the transactional database (some logs had fractional seconds like `.000000` while others did not). Rather than stripping the data, I resolved the parsing error by updating the pandas validation converter to use `format="mixed"`, ensuring all formats parsed safely."*

### Q9: How did you perform end-to-end reconciliation?
* **Answer**: *"I implemented a dual-validation layer. `spark_validation.py` performs in-engine count checks and financial totals matches. Then `reconciler.py` connects PostgreSQL OLTP directly with BigQuery. To handle BigQuery Sandbox's automatic 60-day partition expiration limits, the reconciler queries BigQuery's minimum partition date, filters the PostgreSQL query to matching dates (`WHERE order_ts::date >= bq_min_date`), and matches counts and revenues. This confirmed a 0-row discrepancy and $0.00 difference for the active window."*
