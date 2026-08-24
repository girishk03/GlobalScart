from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from spark_session import create_spark_session

# Project root paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"
PROCESSED_PATH = PROJECT_ROOT / "data_platform" / "data" / "processed" / "parquet"

def main():
    spark = create_spark_session()
    print("=" * 40)
    print("GlobalScart Spark Data Validation")
    print("=" * 40)

    # Load raw and processed datasets
    raw_items = spark.read.option("header", "true").csv(str(RAW_PATH / "fact_order_items"))
    fact_sales = spark.read.parquet(str(PROCESSED_PATH / "fact_sales"))
    dim_customer = spark.read.parquet(str(PROCESSED_PATH / "dim_customer"))
    dim_product = spark.read.parquet(str(PROCESSED_PATH / "dim_product"))
    dim_geo = spark.read.parquet(str(PROCESSED_PATH / "dim_geo"))

    raw_items_count = raw_items.count()
    sales_count = fact_sales.count()

    # 1. Row Count Checks
    print("\nRow Count Checks")
    print("-" * 16)
    print(f"fact_order_items → {raw_items_count}")
    print(f"fact_sales       → {sales_count}")
    row_count_passed = raw_items_count == sales_count
    print("PASS" if row_count_passed else "FAIL")

    # 2. Referential Integrity
    print("\nReferential Integrity")
    print("-" * 21)
    
    # Customer ID check
    missing_customers = fact_sales.join(dim_customer, on="customer_id", how="left_anti").count()
    cust_passed = missing_customers == 0
    print(f"customer_id → {'PASS' if cust_passed else f'FAIL (missing {missing_customers} matches)'}")

    # Product ID check
    missing_products = fact_sales.join(dim_product, on="product_id", how="left_anti").count()
    prod_passed = missing_products == 0
    print(f"product_id  → {'PASS' if prod_passed else f'FAIL (missing {missing_products} matches)'}")

    # Geo ID check
    missing_geos = fact_sales.join(dim_geo, on="geo_id", how="left_anti").count()
    geo_passed = missing_geos == 0
    print(f"geo_id      → {'PASS' if geo_passed else f'FAIL (missing {missing_geos} matches)'}")

    # 3. Null Checks
    print("\nNull Checks")
    print("-" * 11)
    null_fields = ["order_id", "customer_id", "product_id", "order_date", "qty", "calculated_net_revenue"]
    nulls_found = {}
    nulls_passed = True
    for field in null_fields:
        null_count = fact_sales.filter(F.col(field).isNull()).count()
        nulls_found[field] = null_count
        if null_count > 0:
            nulls_passed = False
        print(f"{field:<12} → {'PASS' if null_count == 0 else f'FAIL ({null_count} nulls)'}")

    # 4. Duplicate Checks
    print("\nDuplicate Checks")
    print("-" * 16)
    # Grain check on order_item_id
    duplicate_items = fact_sales.groupBy("order_item_id").count().filter("count > 1").count()
    dup_item_passed = duplicate_items == 0
    print(f"order_item_id unique → {'PASS' if dup_item_passed else f'FAIL ({duplicate_items} duplicate IDs)'}")

    # 5. Financial Reconciliation
    print("\nFinancial Reconciliation")
    print("-" * 24)
    # SUM(fact_order_items.line_net_revenue) vs SUM(fact_sales.calculated_net_revenue)
    raw_revenue = raw_items.select(F.sum(F.col("line_net_revenue").cast("double"))).collect()[0][0] or 0.0
    processed_revenue = fact_sales.select(F.sum(F.col("calculated_net_revenue").cast("double"))).collect()[0][0] or 0.0
    
    diff = abs(raw_revenue - processed_revenue)
    financial_passed = diff < 0.01 # minor floating point tolerance
    
    print(f"Source revenue  : {raw_revenue:.2f}")
    print(f"Sales revenue   : {processed_revenue:.2f}")
    print(f"Difference      : {diff:.2f}")
    print("PASS" if financial_passed else "FAIL")

    print("=" * 40)
    all_passed = (
        row_count_passed and cust_passed and prod_passed and geo_passed and
        nulls_passed and dup_item_passed and financial_passed
    )
    if all_passed:
        print("ALL SPARK VALIDATION CHECKS PASSED")
    else:
        print("SPARK VALIDATION CHECKS FAILED")
    print("=" * 40)

    spark.stop()
    if not all_passed:
        raise SystemExit("Spark validation failed.")

if __name__ == "__main__":
    main()
