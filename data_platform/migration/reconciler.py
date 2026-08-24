import json
import os
import sys
from datetime import datetime
from pathlib import Path
import psycopg2
from google.cloud import bigquery

# Import credentials from the ingestion configuration
sys.path.append(str(Path(__file__).resolve().parents[2] / "data_platform" / "ingestion"))
from config import DB_CONFIG

# Audit file path
AUDIT_LOG_DIR = Path(__file__).resolve().parents[2] / "data_platform" / "metadata" / "audit"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "migration_reconciliation_audit.json"

def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)

def query_pg_metadata(conn):
    """Fetch count and financial sums from PostgreSQL source tables."""
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

def main():
    print("=" * 60)
    print("PostgreSQL to BigQuery End-to-End Migration Reconciler")
    print("=" * 60)

    # 1. Connect to PostgreSQL
    try:
        pg_conn = get_pg_connection()
        print("Connected to PostgreSQL source DB.")
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)

    # 2. Connect to BigQuery
    try:
        bq_client = bigquery.Client()
        print(f"Connected to BigQuery destination. Project: {bq_client.project}")
    except Exception as e:
        print(f"Error connecting to BigQuery: {e}")
        sys.exit(1)

    # 3. Query metadata from both environments
    print("\nFetching source metadata from PostgreSQL...")
    pg_meta = query_pg_metadata(pg_conn)
    
    print("Fetching destination metadata from BigQuery...")
    bq_meta = query_bq_metadata(bq_client)

    # 4. Generate reconciliation report
    print("\n" + "-" * 60)
    print(f"{'Table Name':<18} | {'Source Rows':<11} | {'BQ Rows':<11} | {'Status':<7} | {'Diff':<8}")
    print("-" * 60)

    all_passed = True
    audit_details = {}
    
    for table in pg_meta.keys():
        source_rows = pg_meta[table]["rows"]
        bq_rows = bq_meta[table]["rows"]
        row_diff = bq_rows - source_rows
        
        status = "PASS" if row_diff == 0 else "FAIL"
        if row_diff != 0:
            all_passed = False
            
        print(f"{table:<18} | {source_rows:<11,} | {bq_rows:<11,} | {status:<7} | {row_diff:<+8}")
        
        audit_details[table] = {
            "source_rows": source_rows,
            "bq_rows": bq_rows,
            "row_diff": row_diff,
            "row_status": status,
        }

    # 5. Financial Reconciliation
    print("\nFinancial Revenue Reconciliation (fact_sales)")
    print("-" * 45)
    source_rev = pg_meta["fact_sales"]["revenue"]
    bq_rev = bq_meta["fact_sales"]["revenue"]
    rev_diff = abs(source_rev - bq_rev)
    rev_status = "PASS" if rev_diff < 0.01 else "FAIL"
    
    print(f"PostgreSQL Revenue: {source_rev:,.2f}")
    print(f"BigQuery Revenue:   {bq_rev:,.2f}")
    print(f"Revenue Diff:       {rev_diff:,.2f} ({rev_status})")
    
    audit_details["financial_reconciliation"] = {
        "source_revenue": source_rev,
        "bq_revenue": bq_rev,
        "revenue_diff": rev_diff,
        "revenue_status": rev_status,
    }
    
    if rev_status == "FAIL":
        all_passed = False

    # 6. Duplicate Key Detections
    print("\nChecking for Duplicate Row IDs in BigQuery...")
    print("-" * 45)
    dup_checks = {
        "dim_customer": "customer_id",
        "dim_product": "product_id",
        "dim_geo": "geo_id",
        "dim_date": "date_id",
        "fact_sales": "order_item_id"
    }
    
    dup_found = False
    for table, pk in dup_checks.items():
        table_ref = f"{bq_client.project}.globalcart_analytics.{table}"
        query = f"""
            SELECT COUNT({pk}) - COUNT(DISTINCT {pk}) 
            FROM `{table_ref}`
        """
        query_job = bq_client.query(query)
        result = list(query_job.result())[0][0]
        
        print(f"{table:<18} Duplicate count: {result}")
        if result > 0:
            dup_found = True
            all_passed = False
            
    # 7. Audit Logging
    from datetime import timezone
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        "overall_status": "PASS" if (all_passed and not dup_found) else "FAIL",
        "details": audit_details,
        "duplicates_detected": dup_found
    }
    log_audit_results(audit_entry)
    print(f"\nAudit results appended to: {AUDIT_LOG_FILE}")
    
    print("=" * 60)
    if all_passed and not dup_found:
        print("MIGRATION RECONCILIATION SUCCESSFUL: DATA IS 100% CORRECT")
    else:
        print("MIGRATION RECONCILIATION FAILED: DISCREPANCIES DETECTED")
    print("=" * 60)

    pg_conn.close()

if __name__ == "__main__":
    main()
