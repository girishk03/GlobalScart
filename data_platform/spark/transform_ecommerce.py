import sys
from pathlib import Path
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    StringType,
    StructType,
    StructField,
    TimestampType,
    DateType,
    BooleanType,
)

# Add parent directory to sys.path to import utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from data_platform.spark.spark_session import create_spark_session
from data_platform.utils.observability import PipelineObserver, logger

# Project root paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"
PROCESSED_PATH = PROJECT_ROOT / "data_platform" / "data" / "processed" / "parquet"

# Define raw schemas for all 6 tables to enforce types on read
FACT_ORDERS_SCHEMA = StructType([
    StructField("order_id", IntegerType(), False),
    StructField("customer_id", IntegerType(), False),
    StructField("geo_id", IntegerType(), False),
    StructField("order_ts", TimestampType(), False),
    StructField("order_status", StringType(), True),
    StructField("channel", StringType(), True),
    StructField("currency", StringType(), True),
    StructField("gross_amount", DecimalType(18, 2), True),
    StructField("discount_amount", DecimalType(18, 2), True),
    StructField("tax_amount", DecimalType(18, 2), True),
    StructField("net_amount", DecimalType(18, 2), True),
    StructField("created_at", TimestampType(), False),
    StructField("updated_at", TimestampType(), True),
])

FACT_ORDER_ITEMS_SCHEMA = StructType([
    StructField("order_item_id", IntegerType(), False),
    StructField("order_id", IntegerType(), False),
    StructField("product_id", IntegerType(), False),
    StructField("qty", IntegerType(), False),
    StructField("unit_list_price", DecimalType(12, 2), False),
    StructField("unit_sell_price", DecimalType(12, 2), False),
    StructField("unit_cost", DecimalType(12, 2), False),
    StructField("line_discount", DecimalType(14, 2), False),
    StructField("line_tax", DecimalType(14, 2), False),
    StructField("line_net_revenue", DecimalType(14, 2), False),
    StructField("created_at", TimestampType(), False),
    StructField("updated_at", TimestampType(), True),
])

DIM_CUSTOMER_SCHEMA = StructType([
    StructField("customer_id", IntegerType(), False),
    StructField("customer_created_ts", TimestampType(), False),
    StructField("geo_id", IntegerType(), False),
    StructField("acquisition_channel", StringType(), True),
    StructField("created_at", TimestampType(), False),
    StructField("updated_at", TimestampType(), True),
])

DIM_PRODUCT_SCHEMA = StructType([
    StructField("product_id", IntegerType(), False),
    StructField("sku", StringType(), False),
    StructField("product_name", StringType(), False),
    StructField("category_l1", StringType(), False),
    StructField("category_l2", StringType(), False),
    StructField("brand", StringType(), False),
    StructField("unit_cost", DecimalType(12, 2), False),
    StructField("list_price", DecimalType(12, 2), False),
    StructField("created_at", TimestampType(), False),
    StructField("updated_at", TimestampType(), True),
])

DIM_GEO_SCHEMA = StructType([
    StructField("geo_id", IntegerType(), False),
    StructField("country", StringType(), False),
    StructField("region", StringType(), False),
    StructField("city", StringType(), False),
    StructField("currency", StringType(), False),
    StructField("created_at", TimestampType(), False),
    StructField("updated_at", TimestampType(), True),
])

DIM_DATE_SCHEMA = StructType([
    StructField("date_id", IntegerType(), False),
    StructField("date_value", DateType(), False),
    StructField("year", IntegerType(), False),
    StructField("quarter", IntegerType(), False),
    StructField("month", IntegerType(), False),
    StructField("month_name", StringType(), False),
    StructField("week_of_year", IntegerType(), False),
    StructField("day_of_month", IntegerType(), False),
    StructField("day_of_week", IntegerType(), False),
    StructField("day_name", StringType(), False),
    StructField("is_weekend", BooleanType(), False),
])

# Read and validate functions
def read_table(spark, file_name, schema):
    input_path = str(RAW_PATH / file_name)
    return (
        spark.read
        .option("header", "true")
        .schema(schema)
        .csv(input_path)
    )

# Deduplication helper
def deduplicate_by_id(df, id_column, sort_column="updated_at"):
    return (
        df
        .withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy(id_column)
                .orderBy(F.col(sort_column).desc_nulls_last())
            ),
        )
        .filter(F.col("rn") == 1)
        .drop("rn")
    )

def main() -> int:
    spark = create_spark_session()
    logger.info("Starting Star Schema PySpark pipeline...")

    # 1. READ RAW TABLES
    logger.info("Reading raw datasets...")
    raw_orders = read_table(spark, "fact_orders", FACT_ORDERS_SCHEMA)
    raw_items = read_table(spark, "fact_order_items", FACT_ORDER_ITEMS_SCHEMA)
    raw_customer = read_table(spark, "dim_customer", DIM_CUSTOMER_SCHEMA)
    raw_product = read_table(spark, "dim_product", DIM_PRODUCT_SCHEMA)
    raw_geo = read_table(spark, "dim_geo", DIM_GEO_SCHEMA)
    raw_date = read_table(spark, "dim_date", DIM_DATE_SCHEMA)

    print(f"Raw orders count: {raw_orders.count()}")
    print(f"Raw items count: {raw_items.count()}")

    # 2. DEDUPLICATE AND CLEAN DIMENSIONS
    print("\nCleaning & deduplicating dimensions...")
    
    # Customer - Select only attributes needed downstream (avoid geo_id collision with orders)
    dim_customer_cleaned = deduplicate_by_id(raw_customer, "customer_id")
    dim_customer_prep = (
        dim_customer_cleaned
        .withColumn("acquisition_channel", F.lower(F.trim("acquisition_channel")))
        .select("customer_id", "customer_created_ts", "acquisition_channel")
    )
    
    # Product - Rename unit_cost/list_price to catalog_ equivalents to avoid collision with item costs
    dim_product_cleaned = deduplicate_by_id(raw_product, "product_id")
    dim_product_prep = (
        dim_product_cleaned
        .withColumn("category_l1", F.upper(F.trim("category_l1")))
        .withColumn("category_l2", F.upper(F.trim("category_l2")))
        .withColumn("brand", F.upper(F.trim("brand")))
        .withColumn("product_name", F.trim("product_name"))
        .select(
            "product_id", "sku", "product_name", "category_l1", "category_l2", "brand",
            F.col("unit_cost").alias("catalog_unit_cost"),
            F.col("list_price").alias("catalog_list_price")
        )
    )

    # Geo - Select attributes and drop currency/metadata to avoid collisions
    dim_geo_cleaned = deduplicate_by_id(raw_geo, "geo_id")
    dim_geo_prep = (
        dim_geo_cleaned
        .withColumn("country", F.upper(F.trim("country")))
        .withColumn("region", F.upper(F.trim("region")))
        .withColumn("city", F.trim("city"))
        .select("geo_id", "country", "region", "city")
    )

    # Date
    dim_date_cleaned = raw_date # Dates don't require deduplication as date_value is unique

    # 3. DEDUPLICATE AND CLEAN ORDERS
    print("Cleaning & deduplicating orders...")
    orders_dedup = deduplicate_by_id(raw_orders, "order_id")
    orders_cleaned = (
        orders_dedup
        .withColumn("order_status", F.upper(F.trim("order_status")))
        .withColumn("channel", F.lower(F.trim("channel")))
        .withColumn("currency", F.upper(F.trim("currency")))
        # Keep positive amounts only
        .filter(
            (F.col("gross_amount") >= 0) &
            (F.col("discount_amount") >= 0) &
            (F.col("tax_amount") >= 0) &
            (F.col("net_amount") >= 0)
        )
        # Select required order attributes (to drop metadata/duplicate columns before join)
        .select(
            "order_id", "customer_id", "geo_id", "order_ts", "order_status", "channel", "currency"
        )
    )

    # 4. JOIN AND CONSTRUCT FACT_SALES (Star Schema)
    print("\nConstructing fact_sales (Star Schema Joins)...")
    
    # Start with fact_order_items and deduplicate line items
    items_dedup = deduplicate_by_id(raw_items, "order_item_id")
    
    # Join items with orders (inner join since an item must have an order)
    sales = items_dedup.join(orders_cleaned, on="order_id", how="inner")
    
    # Join with product catalog
    sales = sales.join(dim_product_prep, on="product_id", how="left")
    
    # Join with customer registry
    sales = sales.join(dim_customer_prep, on="customer_id", how="left")

    # Join with geography registry
    sales = sales.join(dim_geo_prep, on="geo_id", how="left")

    # Derive core analytical columns
    sales_enriched = (
        sales
        .withColumn("order_date", F.to_date("order_ts"))
        .withColumn("order_year", F.year("order_ts"))
        .withColumn("order_month", F.month("order_ts"))
        .withColumn("order_week", F.weekofyear("order_ts"))
        
        # Calculate totals using transaction-level unit costs/prices from fact_order_items
        .withColumn("gross_item_amount", F.col("qty").cast("decimal(18,2)") * F.col("unit_list_price"))
        .withColumn("total_item_cost", F.col("qty").cast("decimal(18,2)") * F.col("unit_cost"))
        
        # Line-level financial calculations
        .withColumn("calculated_net_revenue", F.col("gross_item_amount") - F.col("line_discount") + F.col("line_tax"))
        .withColumn("item_profit", F.col("calculated_net_revenue") - F.col("total_item_cost"))
        .withColumn(
            "item_profit_margin",
            F.when(F.col("calculated_net_revenue") > 0, 
                   ((F.col("item_profit") / F.col("calculated_net_revenue")) * 100).cast("decimal(18,2)")
            ).otherwise(F.lit(0).cast("decimal(18,2)"))
        )
        .withColumn(
            "discount_percentage",
            F.when(F.col("gross_item_amount") > 0,
                   ((F.col("line_discount") / F.col("gross_item_amount")) * 100).cast("decimal(18,2)")
            ).otherwise(F.lit(0).cast("decimal(18,2)"))
        )
    )

    # Select final columns to export as the fact table
    fact_sales = sales_enriched.select(
        "order_item_id",
        "order_id",
        "customer_id",
        "product_id",
        "geo_id",
        "order_date",
        "order_year",
        "order_month",
        "order_week",
        "order_ts",
        "order_status",
        "channel",
        "currency",
        "qty",
        "unit_list_price",
        "unit_sell_price",
        "unit_cost",
        "gross_item_amount",
        "line_discount",
        "line_tax",
        "calculated_net_revenue",
        "total_item_cost",
        "item_profit",
        "item_profit_margin",
        "discount_percentage"
    )

    fact_sales_count = fact_sales.count()
    logger.info(f"Constructed fact_sales row count: {fact_sales_count}")

    # 5. WRITE PROCESSED PARQUET DATASETS
    logger.info("Writing processed datasets to Parquet...")
    
    # Dimensions (overwrite, regular parquet files)
    dim_customer_prep.write.mode("overwrite").parquet(str(PROCESSED_PATH / "dim_customer"))
    dim_product_prep.write.mode("overwrite").parquet(str(PROCESSED_PATH / "dim_product"))
    dim_geo_prep.write.mode("overwrite").parquet(str(PROCESSED_PATH / "dim_geo"))
    dim_date_cleaned.write.mode("overwrite").parquet(str(PROCESSED_PATH / "dim_date"))
    logger.info("✓ Successfully wrote processed dimensions (customer, product, geo, date).")

    # Fact sales (overwrite, partitioned by year and month)
    (
        fact_sales
        .write
        .mode("overwrite")
        .partitionBy("order_year", "order_month")
        .parquet(str(PROCESSED_PATH / "fact_sales"))
    )
    logger.info("✓ Successfully wrote processed fact_sales (partitioned by year/month).")

    # Print out summary
    logger.info("Transformation pipeline completed successfully.")
    logger.info(f"Processed Parquet output root: {PROCESSED_PATH}")
    spark.stop()
    return fact_sales_count

if __name__ == "__main__":
    with PipelineObserver("spark_transformation") as observer:
        rows = main()
        observer.complete(rows)
