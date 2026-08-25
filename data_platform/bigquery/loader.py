import sys
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Add parent directory to sys.path to import schemas and utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from data_platform.bigquery.schemas import TABLE_SCHEMAS
from data_platform.utils.observability import PipelineObserver, logger

DATASET_ID = "globalcart_analytics"
PROCESSED_PATH = PROJECT_ROOT / "data_platform" / "data" / "processed" / "parquet"

def load_table(client: bigquery.Client, table_name: str) -> int:
    """Load processed local Parquet dataset into BigQuery as a single atomic transaction. Returns row count loaded."""
    dataset_ref = client.dataset(DATASET_ID)
    table_ref = dataset_ref.table(table_name)
    
    table_folder = PROCESSED_PATH / table_name
    if not table_folder.exists():
        logger.info(f"Directory not found: {table_folder}. Skipping.")
        return 0
        
    logger.info(f"Loading table {table_name} into BigQuery...")
    
    # Read the entire Parquet dataset (including partition columns if partitioned)
    try:
        df = pd.read_parquet(table_folder)
    except Exception as e:
        logger.error(f"✕ Failed to read Parquet dataset {table_name}: {e}")
        raise e

    if df.empty:
        logger.info(f"Dataset {table_name} is empty. Skipping.")
        return 0

    logger.info(f"  Read {len(df):,} rows from local Parquet files.")
    
    # If the partitioning/clustering is changed, delete the table first to recreate it cleanly
    if table_name == "fact_sales":
        try:
            existing_table = client.get_table(table_ref)
            if existing_table.time_partitioning is None:
                logger.info(f"  Existing table {table_name} is not partitioned. Deleting to apply new partitioning/clustering spec.")
                client.delete_table(table_ref, not_found_ok=True)
        except NotFound:
            pass

    # Set up load job configuration (atomic WRITE_TRUNCATE ensures idempotency)
    schema = TABLE_SCHEMAS.get(table_name)
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    # Configure daily partitioning and clustering for fact_sales
    if table_name == "fact_sales":
        job_config.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="order_date"
        )
        job_config.clustering_fields = ["customer_id", "product_id"]
        logger.info("  Configured daily time partitioning on 'order_date' and clustering on ['customer_id', 'product_id'] for fact_sales.")
    
    # Load the dataframe in a single atomic transaction
    load_job = client.load_table_from_dataframe(
        df, table_ref, job_config=job_config
    )
    load_job.result() # Wait for job completion
             
    # Verify table row count
    table = client.get_table(table_ref)
    logger.info(f"✓ Successfully loaded {table_name}. Row count in BigQuery: {table.num_rows}")
    return table.num_rows

def main() -> int:
    logger.info("========================================")
    logger.info("GlobalScart BigQuery Loader (Atomic DataFrame Ingest)")
    logger.info("========================================")
    
    try:
        client = bigquery.Client()
    except Exception as e:
        logger.error(f"Error initializing BigQuery Client: {e}")
        logger.error("Please authenticate using 'gcloud auth application-default login'")
        raise e
        
    project = client.project
    logger.info(f"Target GCP Project: {project}")
    logger.info(f"Target Dataset:     {DATASET_ID}")
    
    # Create dataset if not exists
    dataset_ref = client.dataset(DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        logger.info(f"Dataset '{DATASET_ID}' already exists.")
    except NotFound:
        logger.info(f"Dataset '{DATASET_ID}' not found. Creating...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset)
        logger.info(f"✓ Created dataset '{dataset.dataset_id}' in {dataset.location}")
    except Exception as e:
        logger.error(f"Error checking/creating dataset: {e}")
        logger.info("Note: This is expected if your GCP billing account is disabled.")
        raise e

    # Load all tables
    total_loaded = 0
    for table_name in TABLE_SCHEMAS.keys():
        try:
            rows = load_table(client, table_name)
            total_loaded += rows
        except Exception as e:
            logger.error(f"✕ Failed to load {table_name}: {e}")
            raise e
            
    logger.info(f"BigQuery Loader completed. Total rows loaded: {total_loaded:,}")
    logger.info("========================================")
    return total_loaded

if __name__ == "__main__":
    with PipelineObserver("bigquery_load") as observer:
        rows = main()
        observer.complete(rows)
