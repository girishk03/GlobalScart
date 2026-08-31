# GlobalCart-360 Personal Portfolio Project: Interview & Resume Guide

This guide compiles technical resume points, system design Q&As, and architecture walk-throughs for the **GlobalCart-360 Personal Portfolio Capstone Project**.

---

## 1. Technical Resume Points

* **Batch & Watermark Ingestion**:
  > Engineered a dual-source batch ETL pipeline in Python using `updated_at` watermarks to capture daily transaction deltas from PostgreSQL and Azure SQL Database, staging raw transactional batches locally for downstream consumption.

* **Dimensional Modeling & PySpark Transformations**:
  > Configured a local PySpark processing engine to clean, deduplicate, and join e-commerce entities into a structured Star Schema (179K+ fact records), constraining driver/executor memory allocations to 2GB to optimize single-node system footprint.

* **SQL-Based Modeling with dbt**:
  > Built a modular dbt (Data Build Tool) project to manage SQL transformations in PostgreSQL, defining staging views and final analytical marts (`fct_sales`), and automated data integrity validations using dbt schema assertions (uniqueness, not_null).

* **Warehouse Optimization & Loading**:
  > Designed the destination analytics layout for Google Cloud BigQuery with daily partitioning on `order_date` and clustering on `customer_id` and `product_id` to optimize scanned bytes, using `WRITE_TRUNCATE` loads to enforce run-level idempotency.

* **Orchestration & Automated Testing**:
  > Orchestrated the linear ETL tasks using Apache Airflow. Built a logging observer (`PipelineObserver`) to log run-level execution statuses and tracebacks into an audit table, and integrated GitHub Actions CI/CD to validate codebase logic.

---

## 2. Technical System Design Q&A

### Q1: Why PySpark instead of Pandas?
* **Answer**: *"While Pandas is ideal for in-memory manipulation of single-node datasets, it lacks horizontal scaling capabilities and easily crashes due to out-of-memory errors on large files. PySpark builds a lazy-evaluated execution DAG (directed acyclic graph) and handles data in distributed partitions. This design ensures that the pipeline's core logic can transition to a managed cloud cluster (like GCP Dataproc) without refactoring the codebase."*

### Q2: Why Parquet?
* **Answer**: *"Parquet is a columnar storage format optimized for read-heavy analytical workloads:
  1. **Column projection**: It reads only the byte segments of the specific columns requested in a query, which is a major performance boost over parsing entire lines in CSV formats.
  2. **Metadata blocks**: Parquet stores min/max statistics for every row group, allowing Spark or BigQuery to skip scanning irrelevant blocks (predicate pushdown).
  3. **Schema encapsulation**: Parquet embeds data type definitions, avoiding data type mismatch issues during ingestion."*

### Q3: How does your watermarking differ from Change Data Capture (CDC)?
* **Answer**: *"My pipeline uses **watermark-based incremental ingestion**. The extractor queries the database for records updated since the last recorded watermark (`WHERE updated_at > last_watermark`) and updates the state with the maximum timestamp in the batch. 
  
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

### Q10: Walk me through your Airflow DAG. What are the tasks, dependencies, schedule, retries, and failure handling?
* **Answer**: *"The pipeline is orchestrated by a single DAG, [`globalcart_data_engineering_pipeline`](file:///Users/saigirish050704/Documents/globalcart-360/data_platform/airflow/dags/globalcart_pipeline.py). It consists of 6 sequential tasks executed via `BashOperator` tasks to isolate the compute execution environments:
  1. `extract_postgresql` & `extract_sqlserver`: Ingest transactional database tables in parallel using watermark boundaries.
  2. `data_quality_check`: Validates raw CSV landing files against nullability, uniqueness, and timestamp range constraints.
  3. `dbt_run_transformations` & `dbt_test_constraints`: Runs dbt models to compile staging views and fct_sales tables in PostgreSQL, running automated unique/not_null tests.
  4. `pyspark_star_schema_transform`: Triggers PySpark transformations to deduplicate records, build dimensions, and output partitioned Parquet datasets.
  5. `spark_output_validation`: Runs in-engine validation checks for referential integrity and financial revenue counts.
  6. `bigquery_load`: Loads Parquet dataframes atomically into daily-partitioned and clustered BigQuery tables.
  7. `bigquery_warehouse_reconciliation`: Reconciles transactional Postgres rows and revenue against the BigQuery active partition window.
  
  The dependency chain is strictly sequential to prevent processing data downstream if any step fails. For failure recovery, the DAG is configured with `retries: 1` and a `retry_delay: timedelta(minutes=2)`. We use a custom `PipelineObserver` context manager that intercepts exceptions, writes a `FAILED` record with full traceback details to our PostgreSQL audit table, and exits with a non-zero code to alert Airflow."*

### Q11: Why did you choose BigQuery? How did you load/update the data, and how would you reduce query cost?
* **Answer**: *"I chose Google Cloud BigQuery as the analytics warehouse for its serverless compute engine and separate pricing models for compute and storage. It offers high-performance columnar execution, making it highly cost-effective for aggregations across specific columns.
  
  We load the datasets atomically via `loader.py` using Pandas and PyArrow. Ingestion uses the `WRITE_TRUNCATE` write disposition. This guarantees run-level idempotency by replacing the table on reload, ensuring we never duplicate rows on retry. (At higher scale, we would load to staging and execute a SQL `MERGE` to update the production fact).
  
  To minimize query scan costs and optimize performance, we configure:
  1. **Daily time partitioning** on `order_date`: Queries filtering on date ranges perform partition pruning, scanning only relevant partition blocks.
  2. **Clustering** on `customer_id` and `product_id`: BigQuery physically sorts the rows within each partition by these keys, allowing it to skip reading unrelated data blocks during analytical filters."*

### Q12: How did you implement dbt and why is it included in your project?
* **Answer**: *"I set up dbt (Data Build Tool) to manage SQL-based transformations inside our PostgreSQL local warehouse layer. I structured the project into staging models (which perform initial column renaming, type casting, and data cleaning) and analytical marts (such as `fct_sales`, which consolidates e-commerce orders, items, products, and customer dimensions into a unified analytical schema). This decoupled modeling logic from our PySpark and ingestion tasks, and allowed us to run automated constraint tests (`dbt test`) to verify primary key uniqueness and non-null values before loading the data into BigQuery."*

### Q13: What is the design footprint of the Power BI integration?
* **Answer**: *"I mapped out the semantic data model and wrote visual specifications for Power BI dashboards in `docs/powerbi_design.md`. This details our Star Schema relationships, configure import mode with incremental refreshes on `order_date`, and defines key DAX measures for business metrics, including:
  * Customer Lifetime Value (CLV) cohort calculations using `CALCULATE` and `ALLSELECTED` filters.
  * Delivery SLA compliance rates comparing order status and delivery delays.
  * Executive sales KPIs and gross profit margins."*
