import sys
from pathlib import Path
from pyspark.sql import functions as F

# Add parent directory to sys.path to import utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from data_platform.spark.spark_session import create_spark_session
from data_platform.utils.observability import PipelineObserver, logger

def main() -> int:
    spark = create_spark_session()
    logger.info("========================================")
    logger.info("GlobalScart Spark Data Validation")
    logger.info("========================================")

    # Load raw and processed datasets
    raw_items = spark.read.option("header", "true").csv(str(RAW_PATH / "fact_order_items"))
    fact_sales = spark.read.parquet(str(PROCESSED_PATH / "fact_sales"))
    dim_customer = spark.read.parquet(str(PROCESSED_PATH / "dim_customer"))
    dim_product = spark.read.parquet(str(PROCESSED_PATH / "dim_product"))
    dim_geo = spark.read.parquet(str(PROCESSED_PATH / "dim_geo"))

    raw_items_count = raw_items.count()
    sales_count = fact_sales.count()

    # 1. Row Count Checks
    logger.info("Row Count Checks")
    logger.info(f"  fact_order_items → {raw_items_count}")
    logger.info(f"  fact_sales       → {sales_count}")
    row_count_passed = raw_items_count == sales_count
    logger.info(f"  Result: {'PASS' if row_count_passed else 'FAIL'}")

    # 2. Referential Integrity
    logger.info("Referential Integrity Checks")
    
    # Customer ID check
    missing_customers = fact_sales.join(dim_customer, on="customer_id", how="left_anti").count()
    cust_passed = missing_customers == 0
    logger.info(f"  customer_id → {'PASS' if cust_passed else f'FAIL (missing {missing_customers} matches)'}")

    # Product ID check
    missing_products = fact_sales.join(dim_product, on="product_id", how="left_anti").count()
    prod_passed = missing_products == 0
    logger.info(f"  product_id  → {'PASS' if prod_passed else f'FAIL (missing {missing_products} matches)'}")

    # Geo ID check
    missing_geos = fact_sales.join(dim_geo, on="geo_id", how="left_anti").count()
    geo_passed = missing_geos == 0
    logger.info(f"  geo_id      → {'PASS' if geo_passed else f'FAIL (missing {missing_geos} matches)'}")

    # 3. Null Checks
    logger.info("Null Checks")
    null_fields = ["order_id", "customer_id", "product_id", "order_date", "qty", "calculated_net_revenue"]
    nulls_passed = True
    for field in null_fields:
        null_count = fact_sales.filter(F.col(field).isNull()).count()
        if null_count > 0:
            nulls_passed = False
        logger.info(f"  {field:<24} → {'PASS' if null_count == 0 else f'FAIL ({null_count} nulls)'}")

    # 4. Duplicate Checks
    logger.info("Duplicate Checks")
    # Grain check on order_item_id
    duplicate_items = fact_sales.groupBy("order_item_id").count().filter("count > 1").count()
    dup_item_passed = duplicate_items == 0
    logger.info(f"  order_item_id unique → {'PASS' if dup_item_passed else f'FAIL ({duplicate_items} duplicate IDs)'}")

    # 5. Financial Reconciliation
    logger.info("Financial Reconciliation")
    # SUM(fact_order_items.line_net_revenue) vs SUM(fact_sales.calculated_net_revenue)
    raw_revenue = raw_items.select(F.sum(F.col("line_net_revenue").cast("double"))).collect()[0][0] or 0.0
    processed_revenue = fact_sales.select(F.sum(F.col("calculated_net_revenue").cast("double"))).collect()[0][0] or 0.0
    
    diff = abs(raw_revenue - processed_revenue)
    financial_passed = diff < 0.01 # minor floating point tolerance
    
    logger.info(f"  Source revenue  : {raw_revenue:.2f}")
    logger.info(f"  Sales revenue   : {processed_revenue:.2f}")
    logger.info(f"  Difference      : {diff:.2f}")
    logger.info(f"  Result          : {'PASS' if financial_passed else 'FAIL'}")

    logger.info("========================================")
    all_passed = (
        row_count_passed and cust_passed and prod_passed and geo_passed and
        nulls_passed and dup_item_passed and financial_passed
    )
    
    spark.stop()
    
    if not all_passed:
        raise ValueError("Spark validation suite failed due to integrity checks or financial mismatch.")
        
    logger.info("ALL SPARK VALIDATION CHECKS PASSED")
    logger.info("========================================")
    return sales_count

# Re-define raw/processed paths inside script scope
RAW_PATH = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"
PROCESSED_PATH = PROJECT_ROOT / "data_platform" / "data" / "processed" / "parquet"

if __name__ == "__main__":
    with PipelineObserver("spark_validation") as observer:
        rows = main()
        observer.complete(rows)
