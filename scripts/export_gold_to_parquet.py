import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.motherduck import connect_motherduck, close_connection
from configs.paths import DATA_DIR
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GOLD_DIR = DATA_DIR / "gold"
GOLD_DIR.mkdir(parents=True, exist_ok=True)

TABLES_TO_EXPORT = [
    "mart_dashboard_listing_snapshot",
    "mart_dashboard_listing_review_recency",
    "mart_dashboard_listing_monthly_availability"
]

def chunk_export(conn, table_name: str, out_path: Path, chunk_size: int = 50000):
    logger.info(f"Getting row count for {table_name}...")
    total_rows = conn.execute(f"SELECT COUNT(*) FROM gold.{table_name}").fetchone()[0]
    logger.info(f"Table {table_name} has {total_rows} rows. Fetching in chunks of {chunk_size}...")
    
    dfs = []
    for offset in range(0, total_rows, chunk_size):
        logger.info(f"  Fetching offset {offset}...")
        df_chunk = conn.execute(f"SELECT * FROM gold.{table_name} LIMIT {chunk_size} OFFSET {offset}").fetchdf()
        dfs.append(df_chunk)
        
    logger.info(f"Concatenating and saving to {out_path.name}...")
    final_df = pd.concat(dfs, ignore_index=True)
    final_df.to_parquet(out_path)
    logger.info(f"Saved {table_name} successfully.")

def main():
    logger.info("Connecting to MotherDuck...")
    conn = connect_motherduck(read_only=True)
    
    try:
        for table in TABLES_TO_EXPORT:
            parquet_path = GOLD_DIR / f"{table}.parquet"
            chunk_export(conn, table, parquet_path, chunk_size=5000)
    except Exception as e:
        logger.error(f"Error exporting tables: {e}")
        sys.exit(1)
    finally:
        close_connection(conn)
        
    logger.info("All exports completed successfully.")

if __name__ == "__main__":
    main()
