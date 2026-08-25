import json
import os
import sys
from datetime import datetime
from pathlib import Path
import psycopg2
from google.cloud import bigquery

# Import credentials and utils
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "data_platform" / "ingestion"))

from config import DB_CONFIG
from data_platform.utils.observability import PipelineObserver, logger

# Audit file path
AUDIT_LOG_DIR = PROJECT_ROOT / "data_platform" / "metadata" / "audit"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "migration_reconciliation_audit.json"

def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)

def query_pg_metadata(conn, bq_min_date=None):
    """Fetch count and financial sums from PostgreSQL source tables, optionally filtering by date for active partition validation."""
    metadata = {}
    with conn.cursor() as cur:
        # dim_customer
        cur.execute("SELECT COUNT(*) FROM globalcart.dim_customer;")
        metadata["dim_customer"] = {"rows": cur.fetchone()[0], "revenue": 0.0}

        # dim_product
        cur.execute("SELECT COUNT(*) FROM globalcart.dim_product;")
        metadata["dim_product"] = {"rows": cur.fetchone()[0], "revenue": 0.0}

        # dim_geo
        cur.execute("SELECT COUNT(*) FROM globalcart.dim_geo;")
        metadata["dim_geo"] = {"rows": cur.fetchone()[0], "revenue": 0.0}

        # dim_date
        cur.execute("SELECT COUNT(*) FROM globalcart.dim_date;")
        metadata["dim_date"] = {"rows": cur.fetchone()[0], "revenue": 0.0}

        # fact_order_items (maps to fact_sales in BQ)
        # Apply date partition filter to match BigQuery Sandbox's active partition window if specified
        if bq_min_date:
            logger.info(f"  Applying active partition filter to PostgreSQL: order_ts::date >= '{bq_min_date}'")
            cur.execute(
                """
                SELECT COUNT(*), SUM(oi.line_net_revenue)
                FROM globalcart.fact_order_items oi
                JOIN globalcart.fact_orders o ON oi.order_id = o.order_id
                WHERE o.order_ts::date >= %s;
                """,
                (bq_min_date,)
            )
        else:
            cur.execute("SELECT COUNT(*), SUM(line_net_revenue) FROM globalcart.fact_order_items;")
            
        row = cur.fetchone()
        metadata["fact_sales"] = {"rows": row[0], "revenue": float(row[1] or 0.0)}

    return metadata

def query_bq_metadata(bq_client):
    """Fetch count and financial sums from BigQuery destination tables."""
    metadata = {}
    dataset_id = "globalcart_analytics"
    
    tables = ["dim_customer", "dim_product", "dim_geo", "dim_date", "fact_sales"]
    for table in tables:
        table_ref = f"{bq_client.project}.{dataset_id}.{table}"
        
        if table == "fact_sales":
            query = f"SELECT COUNT(*), SUM(calculated_net_revenue) FROM `{table_ref}`"
        else:
            query = f"SELECT COUNT(*), 0.0 FROM `{table_ref}`"
            
        query_job = bq_client.query(query)
        result = list(query_job.result())[0]
        metadata[table] = {"rows": result[0], "revenue": float(result[1] or 0.0)}
        
    return metadata

def log_audit_results(audit_entry: dict):
    """Save migration audit log entry locally."""
    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logs = []
    if AUDIT_LOG_FILE.exists():
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                logs = json.load(f)
        except Exception:
            pass
            
    logs.append(audit_entry)
    with open(AUDIT_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def main() -> int:
    logger.info("========================================")
    logger.info("PostgreSQL to BigQuery End-to-End Migration Reconciler")
    logger.info("========================================")

    # 1. Connect to PostgreSQL
    try:
        pg_conn = get_pg_connection()
        logger.info("Connected to PostgreSQL source DB.")
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        raise e

    # 2. Connect to BigQuery
    try:
        bq_client = bigquery.Client()
        logger.info(f"Connected to BigQuery destination. Project: {bq_client.project}")
    except Exception as e:
        logger.error(f"Error connecting to BigQuery: {e}")
        raise e

    # 3. Fetch BigQuery minimum partition date to support Sandbox partition expiration reconciliation
    bq_min_date = None
    try:
        query_min = f"SELECT MIN(order_date) FROM `{bq_client.project}.globalcart_analytics.fact_sales`"
        bq_min_date = list(bq_client.query(query_min).result())[0][0]
    except Exception as e:
        logger.warning(f"Could not fetch min partition date from BigQuery: {e}")

    # 4. Query metadata from both environments
    logger.info("Fetching source metadata from PostgreSQL...")
    pg_meta = query_pg_metadata(pg_conn, bq_min_date=bq_min_date)
    
    logger.info("Fetching destination metadata from BigQuery...")
    bq_meta = query_bq_metadata(bq_client)

    # 5. Generate reconciliation report
    logger.info("\n" + "-" * 60)
    logger.info(f"{'Table Name':<18} | {'Source Rows':<11} | {'BQ Rows':<11} | {'Status':<7} | {'Diff':<8}")
    logger.info("-" * 60)

    all_passed = True
    audit_details = {}
    
    for table in pg_meta.keys():
        source_rows = pg_meta[table]["rows"]
        bq_rows = bq_meta[table]["rows"]
        row_diff = bq_rows - source_rows
        
        status = "PASS" if row_diff == 0 else "FAIL"
        if row_diff != 0:
            all_passed = False
            
        logger.info(f"{table:<18} | {source_rows:<11,} | {bq_rows:<11,} | {status:<7} | {row_diff:<+8}")
        
        audit_details[table] = {
            "source_rows": source_rows,
            "bq_rows": bq_rows,
            "row_diff": row_diff,
            "row_status": status,
        }

    # 6. Financial Reconciliation
    logger.info("\nFinancial Revenue Reconciliation (fact_sales)")
    logger.info("-" * 45)
    source_rev = pg_meta["fact_sales"]["revenue"]
    bq_rev = bq_meta["fact_sales"]["revenue"]
    rev_diff = abs(bq_rev - source_rev)
    
    financial_passed = rev_diff < 0.05
    if not financial_passed:
        all_passed = False
        
    logger.info(f"Source Revenue (Postgres): {source_rev:,.2f}")
    logger.info(f"Dest Revenue (BigQuery)  : {bq_rev:,.2f}")
    logger.info(f"Revenue Difference       : {rev_diff:,.2f}")
    logger.info(f"Financial Status         : {'PASS' if financial_passed else 'FAIL'}")

    # 7. Uniqueness check (Duplicate IDs)
    logger.info("\nUniqueness Integrity Check")
    logger.info("-" * 30)
    dup_query = f"SELECT order_item_id, COUNT(*) FROM `{bq_client.project}.globalcart_analytics.fact_sales` GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 5"
    try:
        dup_rows = list(bq_client.query(dup_query).result())
        dup_count = len(dup_rows)
    except Exception as e:
        logger.error(f"Failed to query duplicate IDs: {e}")
        dup_count = -1
        all_passed = False
        
    logger.info(f"Duplicate IDs in BigQuery: {dup_count if dup_count >= 0 else 'ERROR'}")
    logger.info(f"Uniqueness Status        : {'PASS' if dup_count == 0 else 'FAIL'}")

    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "status": "SUCCESS" if all_passed else "FAILED",
        "details": audit_details,
        "revenue_difference": rev_diff,
        "duplicate_count": dup_count
    }
    log_audit_results(audit_entry)

    logger.info("========================================")
    if all_passed:
        logger.info("MIGRATION RECONCILIATION COMPLETED SUCCESSFULLY")
    else:
        logger.info("MIGRATION RECONCILIATION FAILED")
    logger.info("========================================")
    
    pg_conn.close()
    
    if not all_passed:
        raise ValueError("Migration reconciler failed count verification or revenue checks.")
        
    return bq_meta["fact_sales"]["rows"]

if __name__ == "__main__":
    with PipelineObserver("migration_reconciliation") as observer:
        rows = main()
        observer.complete(rows)
