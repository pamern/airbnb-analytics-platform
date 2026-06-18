from datetime import datetime
from pathlib import Path

import duckdb


PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
OUTPUT_CSV_PATH = PROJECT_ROOT / "ml" / "outputs" / "gold_listing_cluster_features.csv"

con = duckdb.connect(str(PROJECT_ROOT / "airbnb_analytics.duckdb"))

df = con.execute("""
    SELECT *
    FROM gold.gold_listing_cluster_features
""").df()

OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
try:
    df.to_csv(OUTPUT_CSV_PATH, index=False)
    saved_path = OUTPUT_CSV_PATH
except PermissionError:
    saved_path = OUTPUT_CSV_PATH.with_name(
        f"{OUTPUT_CSV_PATH.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    df.to_csv(saved_path, index=False)

print(f"Rows: {len(df):,}")
print(f"Saved CSV: {saved_path}")
print(df.head(10).to_string(index=False))

con.close()
