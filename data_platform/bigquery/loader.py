import sys
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from schemas import TABLE_SCHEMAS

# Project root paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_PATH = PROJECT_ROOT / "data_platform" / "data" / "processed" / "parquet"

DATASET_ID = "globalcart_analytics"

def load_table(client: bigquery.Client, table_name: str):
    """Load processed local Parquet dataset into BigQuery as a single atomic transaction."""
    dataset_ref = client.dataset(DATASET_ID)
    table_ref = dataset_ref.table(table_name)
    
    table_folder = PROCESSED_PATH / table_name
    if not table_folder.exists():
        print(f"Directory not found: {table_folder}. Skipping.")
        return
        
    print(f"\nLoading table {table_name} into BigQuery...")
    
    # Read the entire Parquet dataset (including partition columns if partitioned)
    try:
        df = pd.read_parquet(table_folder)
    except Exception as e:
        print(f"✕ Failed to read Parquet dataset {table_name}: {e}")
        return

    if df.empty:
        print(f"Dataset {table_name} is empty. Skipping.")
        return

    print(f"  Read {len(df):,} rows from local Parquet files.")
    
    # Set up load job configuration (atomic WRITE_TRUNCATE ensures idempotency)
    schema = TABLE_SCHEMAS.get(table_name)
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    # Load the dataframe in a single atomic transaction
    load_job = client.load_table_from_dataframe(
        df, table_ref, job_config=job_config
    )
    load_job.result() # Wait for job completion
            
    # Verify table row count
    table = client.get_table(table_ref)
    print(f"✓ Successfully loaded {table_name}. Row count in BigQuery: {table.num_rows}")

def main():
    print("=" * 50)
    print("GlobalScart BigQuery Loader (Atomic DataFrame Ingest)")
    print("=" * 50)
    
    try:
        client = bigquery.Client()
    except Exception as e:
        print(f"Error initializing BigQuery Client: {e}")
        print("Please authenticate using 'gcloud auth application-default login'")
        sys.exit(1)
        
    project = client.project
    print(f"Target GCP Project: {project}")
    print(f"Target Dataset:     {DATASET_ID}")
    
    # Create dataset if not exists
    dataset_ref = client.dataset(DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset '{DATASET_ID}' already exists.")
    except NotFound:
        print(f"Dataset '{DATASET_ID}' not found. Creating...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset)
        print(f"✓ Created dataset '{dataset.dataset_id}' in {dataset.location}")
    except Exception as e:
        print(f"Error checking/creating dataset: {e}")
        print("\nNote: This is expected if your GCP billing account is disabled.")
        sys.exit(1)

    # Load all tables
    for table_name in TABLE_SCHEMAS.keys():
        try:
            load_table(client, table_name)
        except Exception as e:
            print(f"✕ Failed to load {table_name}: {e}")
            
    print("\nBigQuery Loader run completed.")
    print("=" * 50)

if __name__ == "__main__":
    main()
