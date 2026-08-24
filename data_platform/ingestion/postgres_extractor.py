from pathlib import Path
from datetime import datetime
import pandas as pd
import psycopg2
from config import DB_CONFIG
from watermark import get_watermark, update_watermark

TABLES = [
    "dim_customer",
    "dim_product",
    "dim_geo",
    "dim_date",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "fact_shipments",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"

def get_connection():
    """Create a PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)

def extract_table(table_name: str, force_full: bool = False):
    """Extract a PostgreSQL table incrementally or fully into CSV files inside directories."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    table_dir = RAW_DIR / table_name
    table_dir.mkdir(parents=True, exist_ok=True)
    
    # dim_date has no updated_at column and is static
    is_static = (table_name == "dim_date")
    
    if is_static or force_full:
        print(f"Extracting (FULL): {table_name}")
        query = f'SELECT * FROM globalcart."{table_name}"'
        output_path = table_dir / "load_initial.csv"
        
        with get_connection() as connection:
            dataframe = pd.read_sql_query(query, connection)
        
        dataframe.to_csv(output_path, index=False)
        print(f"✓ {table_name}: {len(dataframe):,} rows → {output_path}")
        return

    # Incremental extract based on watermark
    watermark = get_watermark(table_name)
    is_initial = (watermark == "1970-01-01 00:00:00")
    
    if is_initial:
        print(f"Extracting (INITIAL): {table_name}")
        query = f'SELECT * FROM globalcart."{table_name}"'
        output_path = table_dir / "load_initial.csv"
    else:
        print(f"Extracting (INCREMENTAL since {watermark}): {table_name}")
        query = f"SELECT * FROM globalcart.\"{table_name}\" WHERE updated_at > '{watermark}'"
        output_path = table_dir / f"load_{timestamp}.csv"

    with get_connection() as connection:
        dataframe = pd.read_sql_query(query, connection)

    if len(dataframe) == 0:
        print(f"✓ {table_name}: 0 new/updated rows found. Skipping write.")
        return

    dataframe.to_csv(output_path, index=False)
    print(f"✓ {table_name}: {len(dataframe):,} rows → {output_path}")
    
    # Calculate and update new watermark based on max updated_at in the extracted batch
    max_updated = dataframe["updated_at"].max()
    if pd.notna(max_updated):
        if isinstance(max_updated, str):
            new_watermark = max_updated
        else:
            new_watermark = max_updated.strftime("%Y-%m-%d %H:%M:%S.%f")
        update_watermark(table_name, new_watermark)
        print(f"  Watermark updated to: {new_watermark}")

def main():
    import sys
    force_full = "--full" in sys.argv
    print("Starting GlobalScart PostgreSQL extraction...\n")
    for table in TABLES:
        extract_table(table, force_full=force_full)
    print("\nExtraction completed successfully.")

if __name__ == "__main__":
    main()
