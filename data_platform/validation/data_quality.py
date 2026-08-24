from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
        validate_not_null(df, "order_status"),
        validate_timestamp(df, "order_ts"),
        validate_timestamp(df, "created_at"),
        validate_timestamp(df, "updated_at"),
        validate_non_negative(df, "gross_amount"),
        validate_non_negative(df, "discount_amount"),
        validate_non_negative(df, "tax_amount"),
        validate_non_negative(df, "net_amount"),
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

def print_results(table_name, checks):
    print(f"\n{table_name}")
    print("-" * len(table_name))
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(
            f"{status}: "
            f"{check['check']} "
            f"(failed records: "
            f"{check['failed_records']})"
        )

def main():
    print("Starting GlobalScart data-quality validation...")
    order_results = validate_orders()
    customer_results = validate_customers()
    print_results("fact_orders", order_results)
    print_results("dim_customer", customer_results)
    
    all_checks = order_results + customer_results
    failed = [check for check in all_checks if not check["passed"]]
    
    print("\nValidation summary")
    print("------------------")
    print(f"Total checks: {len(all_checks)}")
    print(f"Passed:       {len(all_checks) - len(failed)}")
    print(f"Failed:       {len(failed)}")
    
    if failed:
        raise SystemExit("Data-quality validation failed.")
    print("\nAll validation checks passed.")

if __name__ == "__main__":
    main()
