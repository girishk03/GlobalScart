import os
import sys
import logging
import time
import uuid
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load env variables from root or parents
load_dotenv()

# Logger setup
logger = logging.getLogger("globalcart-pipeline")
logger.setLevel(logging.INFO)

# Avoid adding duplicate handlers if logger is already configured
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# DB config for logging audits
DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "database": os.getenv("PGDATABASE", "globalcart"),
    "user": os.getenv("PGUSER", "globalcart"),
    "password": os.getenv("PGPASSWORD", "globalcart"),
}

RUN_ID_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "metadata",
    "observability_run_id.txt"
)

def get_current_run_id(step_name: str) -> str:
    """Get or generate a unique run ID for linking pipeline steps."""
    # 1. Check Airflow environment context
    airflow_run_id = os.getenv("AIRFLOW_CTX_DAG_RUN_ID") or os.getenv("AIRFLOW_CTX_RUN_ID")
    if airflow_run_id:
        return airflow_run_id

    # 2. If ingestion, always generate a new local run ID
    if step_name == "ingestion":
        new_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        try:
            os.makedirs(os.path.dirname(RUN_ID_FILE), exist_ok=True)
            with open(RUN_ID_FILE, "w") as f:
                f.write(new_id)
        except Exception:
            pass
        return new_id
    
    # 3. For other steps, try to read the currently active local run ID
    if os.path.exists(RUN_ID_FILE):
        try:
            with open(RUN_ID_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            pass
            
    # Fallback if no run ID file exists
    return f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

def _write_audit_log(run_id: str, step_name: str, status: str, rows_processed: int = None, duration_seconds: float = None, error_message: str = None):
    """Write execution metrics to PostgreSQL audit log table."""
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO globalcart.pipeline_audit (
                        run_id, step_name, status, rows_processed, duration_seconds, error_message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (run_id, step_name, status, rows_processed, duration_seconds, error_message)
                )
    except Exception as e:
        logger.warning(f"Failed to write pipeline audit log to PostgreSQL: {e}")

class PipelineObserver:
    """Class to context-manage logging and audits of pipeline steps."""
    def __init__(self, step_name: str):
        self.step_name = step_name
        self.run_id = get_current_run_id(step_name)
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"[{self.step_name.upper()}] Run {self.run_id} - STARTED")
        _write_audit_log(self.run_id, self.step_name, "STARTED")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = round(time.time() - self.start_time, 2)
        if exc_type is not None:
            err_msg = str(exc_val)
            logger.error(f"[{self.step_name.upper()}] Run {self.run_id} - FAILED ({duration}s): {err_msg}")
            _write_audit_log(self.run_id, self.step_name, "FAILED", duration_seconds=duration, error_message=err_msg)
        else:
            logger.info(f"[{self.step_name.upper()}] Run {self.run_id} - COMPLETED ({duration}s)")
            
    def complete(self, rows_processed: int):
        """Mark step as successfully completed with rows count."""
        duration = round(time.time() - self.start_time, 2)
        _write_audit_log(self.run_id, self.step_name, "SUCCESS", rows_processed=rows_processed, duration_seconds=duration)
