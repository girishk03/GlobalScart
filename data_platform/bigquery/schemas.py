from google.cloud import bigquery

DIM_CUSTOMER_SCHEMA = [
    bigquery.SchemaField("customer_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("customer_created_ts", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("acquisition_channel", "STRING", mode="NULLABLE"),
]

DIM_PRODUCT_SCHEMA = [
    bigquery.SchemaField("product_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("sku", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("product_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("category_l1", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("category_l2", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("brand", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("catalog_unit_cost", "NUMERIC", mode="NULLABLE"),
    bigquery.SchemaField("catalog_list_price", "NUMERIC", mode="NULLABLE"),
]

DIM_GEO_SCHEMA = [
    bigquery.SchemaField("geo_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("region", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("city", "STRING", mode="NULLABLE"),
]

DIM_DATE_SCHEMA = [
    bigquery.SchemaField("date_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("date_value", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("year", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("quarter", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("month", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("month_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("week_of_year", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("day_of_month", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("day_of_week", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("day_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("is_weekend", "BOOLEAN", mode="NULLABLE"),
]

FACT_SALES_SCHEMA = [
    bigquery.SchemaField("order_item_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("order_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("customer_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("product_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("geo_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("order_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("order_year", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("order_month", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("order_week", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("order_ts", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("order_status", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("channel", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("currency", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("qty", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("unit_list_price", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("unit_sell_price", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("unit_cost", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("gross_item_amount", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("line_discount", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("line_tax", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("calculated_net_revenue", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("total_item_cost", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("item_profit", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("item_profit_margin", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("discount_percentage", "NUMERIC", mode="REQUIRED"),
]

TABLE_SCHEMAS = {
    "dim_customer": DIM_CUSTOMER_SCHEMA,
    "dim_product": DIM_PRODUCT_SCHEMA,
    "dim_geo": DIM_GEO_SCHEMA,
    "dim_date": DIM_DATE_SCHEMA,
    "fact_sales": FACT_SALES_SCHEMA,
}
