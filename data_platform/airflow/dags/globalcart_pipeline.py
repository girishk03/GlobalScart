from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Resolve paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHON_EXEC = str(PROJECT_ROOT / ".venv" / "bin" / "python")

# Resolve dbt binary dynamically for local and container environments
DBT_LOCAL_PATH = PROJECT_ROOT.parent / "CascadeProjects" / "windsurf-project" / "globalcart-360" / ".venv" / "bin" / "dbt"
DBT_EXEC = str(DBT_LOCAL_PATH) if DBT_LOCAL_PATH.exists() else "dbt"

default_args = {
    "owner": "globalcart",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    "globalcart_data_engineering_pipeline",
    default_args=default_args,
    description="Orchestrates the incremental ETL pipeline from PostgreSQL to BigQuery",
    schedule=None,  # Triggered manually or scheduled on cron e.g., '0 * * * *' (hourly)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["globalcart", "ecommerce", "pyspark", "bigquery", "dbt", "sqlserver"],
) as dag:

    # Task 1a: Extract tables incrementally from PostgreSQL to raw CSV folders
    extract_task = BashOperator(
        task_id="extract_postgresql",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/ingestion/postgres_extractor.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 1b: Extract tables incrementally from MS SQL Server to raw CSV folders
    extract_sqlserver_task = BashOperator(
        task_id="extract_sqlserver",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/ingestion/sqlserver_extractor.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 2: Validate raw landing zone CSVs (Uniqueness, Non-negativity, Null counts)
    quality_task = BashOperator(
        task_id="data_quality_check",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/validation/data_quality.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 2.5a: Compile and run dbt transformation models
    dbt_run_task = BashOperator(
        task_id="dbt_run_transformations",
        bash_command=f"cd {PROJECT_ROOT}/data_platform/dbt && {DBT_EXEC} run --profiles-dir .",
        cwd=str(PROJECT_ROOT / "data_platform" / "dbt"),
    )

    # Task 2.5b: Execute dbt constraints tests (unique, not_null)
    dbt_test_task = BashOperator(
        task_id="dbt_test_constraints",
        bash_command=f"cd {PROJECT_ROOT}/data_platform/dbt && {DBT_EXEC} test --profiles-dir .",
        cwd=str(PROJECT_ROOT / "data_platform" / "dbt"),
    )

    # Task 3: Run PySpark job to clean, deduplicate, and join tables into Star Schema Parquet
    transform_task = BashOperator(
        task_id="pyspark_star_schema_transform",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/spark/transform_ecommerce.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 4: Validate Parquet outputs (Financial reconciliation & referential integrity)
    validation_task = BashOperator(
        task_id="spark_output_validation",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/spark/spark_validation.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 5: Load local Parquet datasets into Google Cloud BigQuery
    load_task = BashOperator(
        task_id="bigquery_load",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/bigquery/loader.py",
        cwd=str(PROJECT_ROOT),
    )

    # Task 6: Run End-to-End Migration Audit and Reconciliation
    reconcile_task = BashOperator(
        task_id="bigquery_warehouse_reconciliation",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_EXEC} data_platform/migration/reconciler.py",
        cwd=str(PROJECT_ROOT),
    )

    # Define DAG task execution dependencies
    [extract_task, extract_sqlserver_task] >> quality_task >> dbt_run_task >> dbt_test_task >> transform_task >> validation_task >> load_task >> reconcile_task
