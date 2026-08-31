import sys
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add parent directory to sys.path to import config and utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from data_platform.ingestion.config import DB_CONFIG
from data_platform.ingestion.watermark import get_watermark, update_watermark
from data_platform.utils.observability import PipelineObserver, logger

# SQL Server Connection Config
SQLSERVER_CONFIG = {
    "host": "localhost",
    "port": 1433,
    "user": "sa",
    "password": "Globalcart_password123!",
    "database": "globalcart"
}

TABLES = [
    "dim_customer",
    "dim_product",
    "dim_geo",
    "dim_date",
    "fact_orders",
    "fact_order_items",
]

RAW_DIR = PROJECT_ROOT / "data_platform" / "data" / "raw" / "sqlserver"
POSTGRES_RAW_DIR = PROJECT_ROOT / "data_platform" / "data" / "raw" / "postgres"

def get_connection():
    """Create a SQL Server connection. Fallback to None if not available."""
    try:
        import pymssql
        return pymssql.connect(
            server=SQLSERVER_CONFIG["host"],
            port=SQLSERVER_CONFIG["port"],
            user=SQLSERVER_CONFIG["user"],
            password=SQLSERVER_CONFIG["password"],
            database=SQLSERVER_CONFIG["database"],
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Could not import pymssql or connect to SQL Server: {e}")
        return None

def extract_table(table_name: str, force_full: bool = False) -> int:
    """Extract SQL Server table incrementally or fully, with graceful fallback to PostgreSQL raw files if SQL Server is offline."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    table_dir = RAW_DIR / table_name
    table_dir.mkdir(parents=True, exist_ok=True)
    
    connection = get_connection()
    
    # Graceful Fallback Mode: Copy matching local raw Postgres CSV files
    if connection is None:
        logger.warning(f"SQL Server offline. Running mock fallback for {table_name}...")
        pg_src_dir = POSTGRES_RAW_DIR / table_name
        if not pg_src_dir.exists() or not list(pg_src_dir.glob("*.csv")):
            logger.error(f"PostgreSQL raw landing files not found for fallback in {pg_src_dir}")
            return 0
            
        # Copy CSV files to SQL Server raw directory
        copied_rows = 0
        for csv_file in pg_src_dir.glob("*.csv"):
            dest_file = table_dir / csv_file.name
            shutil.copy(csv_file, dest_file)
            try:
                df = pd.read_csv(csv_file)
                copied_rows += len(df)
            except Exception:
                pass
        logger.info(f"✓ {table_name} (FALLBACK): copied raw Postgres source data → {table_dir}")
        return copied_rows

    # Standard SQL Server extraction
    try:
        is_static = (table_name == "dim_date")
        if is_static or force_full:
            logger.info(f"Extracting SQL Server (FULL): {table_name}")
            query = f"SELECT * FROM globalcart.dim_date" if is_static else f"SELECT * FROM globalcart.{table_name}"
            output_path = table_dir / "load_initial.csv"
            dataframe = pd.read_sql_query(query, connection)
            dataframe.to_csv(output_path, index=False)
            logger.info(f"✓ {table_name}: {len(dataframe):,} rows → {output_path}")
            return len(dataframe)

        # Incremental watermark query
        watermark = get_watermark(f"sqlserver_{table_name}")
        is_initial = (watermark == "1970-01-01 00:00:00")
        
        if is_initial:
            logger.info(f"Extracting SQL Server (INITIAL): {table_name}")
            query = f"SELECT * FROM globalcart.{table_name}"
            output_path = table_dir / "load_initial.csv"
        else:
            logger.info(f"Extracting SQL Server (INCREMENTAL since {watermark}): {table_name}")
            query = f"SELECT * FROM globalcart.{table_name} WHERE updated_at > '{watermark}'"
            output_path = table_dir / f"load_{timestamp}.csv"

        dataframe = pd.read_sql_query(query, connection)
        if len(dataframe) == 0:
            logger.info(f"✓ {table_name}: 0 new/updated rows found. Skipping write.")
            return 0

        dataframe.to_csv(output_path, index=False)
        logger.info(f"✓ {table_name}: {len(dataframe):,} rows → {output_path}")
        
        max_updated = dataframe["updated_at"].max()
        if pd.notna(max_updated):
            if isinstance(max_updated, str):
                new_watermark = max_updated
            else:
                new_watermark = max_updated.strftime("%Y-%m-%d %H:%M:%S.%f")
            update_watermark(f"sqlserver_{table_name}", new_watermark)
            logger.info(f"  Watermark updated to: {new_watermark}")
        return len(dataframe)
    finally:
        connection.close()

def main():
    force_full = "--full" in sys.argv
    total_rows = 0
    
    with PipelineObserver("sqlserver_ingestion") as observer:
        logger.info("Starting GlobalScart MS SQL Server extraction...")
        for table in TABLES:
            rows = extract_table(table, force_full=force_full)
            total_rows += rows
        observer.complete(total_rows)
        logger.info(f"SQL Server extraction completed. Total rows: {total_rows:,}")

if __name__ == "__main__":
    main()
