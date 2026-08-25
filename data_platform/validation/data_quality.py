import sys
from pathlib import Path
import pandas as pd

# Add parent directory to sys.path to import utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from data_platform.utils.observability import PipelineObserver, logger

RAW_DIR = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"

def read_raw_table(table_name: str) -> pd.DataFrame:
    """Read and concatenate all raw CSV files inside the table's landing directory."""
    table_dir = RAW_DIR / table_name
    if not table_dir.exists():
        raise FileNotFoundError(f"Raw directory not found: {table_dir}")
    csv_files = list(table_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {table_dir}")
    
    # Concatenate all loads (initial + incremental batches)
    dfs = [pd.read_csv(f) for f in csv_files]
    return pd.concat(dfs, ignore_index=True)

def validate_not_null(df, column):
    null_count = df[column].isna().sum()
    return {
        "check": f"{column}_not_null",
        "passed": null_count == 0,
        "failed_records": int(null_count),
    }

def validate_unique(df, column):
    duplicate_count = df[column].duplicated().sum()
    return {
        "check": f"{column}_unique",
        "passed": duplicate_count == 0,
        "failed_records": int(duplicate_count),
    }

def validate_non_negative(df, column):
    invalid_count = (df[column] < 0).sum()
    return {
        "check": f"{column}_non_negative",
        "passed": invalid_count == 0,
        "failed_records": int(invalid_count),
    }

def validate_timestamp(df, column):
    converted = pd.to_datetime(
        df[column],
        errors="coerce",
        format="mixed"
    )
    invalid_count = converted.isna().sum()
    return {
        "check": f"{column}_valid_timestamp",
        "passed": invalid_count == 0,
        "failed_records": int(invalid_count),
    }

def validate_orders():
    df = read_raw_table("fact_orders")
    checks = [
        validate_not_null(df, "order_id"),
        validate_unique(df, "order_id"),
        validate_not_null(df, "customer_id"),
        validate_not_null(df, "geo_id"),
        validate_non_negative(df, "net_amount"),
        validate_timestamp(df, "order_ts"),
        validate_timestamp(df, "created_at"),
        validate_timestamp(df, "updated_at"),
    ]
    return checks

def validate_customers():
    df = read_raw_table("dim_customer")
    checks = [
        validate_not_null(df, "customer_id"),
        validate_unique(df, "customer_id"),
        validate_not_null(df, "geo_id"),
        validate_timestamp(df, "customer_created_ts"),
        validate_timestamp(df, "created_at"),
        validate_timestamp(df, "updated_at"),
    ]
    return checks

def log_results(table_name, checks):
    logger.info(f"Results for {table_name}:")
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        logger.info(
            f"  {status}: {check['check']} (failed records: {check['failed_records']})"
        )

def main():
    with PipelineObserver("data_quality") as observer:
        logger.info("Starting GlobalScart data-quality validation...")
        order_results = validate_orders()
        customer_results = validate_customers()
        
        log_results("fact_orders", order_results)
        log_results("dim_customer", customer_results)
        
        all_checks = order_results + customer_results
        failed = [check for check in all_checks if not check["passed"]]
        
        logger.info(f"DQ Summary: Total checks={len(all_checks)}, Passed={len(all_checks) - len(failed)}, Failed={len(failed)}")
        
        if failed:
            raise ValueError(f"Data-quality validation failed. {len(failed)} check(s) failed.")
        
        observer.complete(len(all_checks))
        logger.info("All validation checks passed.")

if __name__ == "__main__":
    main()
