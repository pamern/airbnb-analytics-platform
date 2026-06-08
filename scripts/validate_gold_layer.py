"""Validate and visualize Gold-layer dim/fact tables.

Usage:
    uv run python scripts/validate_gold_layer.py

Environment:
    DUCKDB_LOCAL_PATH: path to local DuckDB file, default airbnb_analytics.duckdb
    DBT_GOLD_SCHEMA: schema containing Gold models, default gold
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "gold_validation_figures"
REPORT_PATH = REPORTS_DIR / "gold_validation_report.md"

DUCKDB_PATH = os.getenv("DUCKDB_LOCAL_PATH", "airbnb_analytics.duckdb")
GOLD_SCHEMA = os.getenv("DBT_GOLD_SCHEMA", "gold")


TABLES = [
    "dim_listing",
    "dim_host",
    "dim_location",
    "dim_date",
    "fact_listing_snapshot",
    "fact_calendar_daily",
    "fact_review",
    "mart_neighbourhood_market",
    "mart_host_performance",
    "mart_competitor_benchmark",
    "mart_ml_price_features",
    "mart_llm_area_summary",
]


GRAIN_CHECKS = {
    "dim_listing": ["listing_key"],
    "dim_host": ["host_key"],
    "dim_location": ["location_key"],
    "dim_date": ["date_key"],
    "fact_listing_snapshot": ["listing_key"],
    "fact_calendar_daily": ["listing_key", "date_key"],
    "fact_review": ["review_key"],
    "mart_neighbourhood_market": ["location_key", "room_type"],
    "mart_host_performance": ["host_key"],
    "mart_competitor_benchmark": ["listing_id", "competitor_listing_id"],
    "mart_ml_price_features": ["listing_id"],
    "mart_llm_area_summary": ["location_key", "room_type"],
}


RELATIONSHIP_CHECKS = [
    (
        "fact_listing_snapshot.listing_key -> dim_listing.listing_key",
        "fact_listing_snapshot",
        "listing_key",
        "dim_listing",
        "listing_key",
    ),
    (
        "fact_listing_snapshot.host_key -> dim_host.host_key",
        "fact_listing_snapshot",
        "host_key",
        "dim_host",
        "host_key",
    ),
    (
        "fact_listing_snapshot.location_key -> dim_location.location_key",
        "fact_listing_snapshot",
        "location_key",
        "dim_location",
        "location_key",
    ),
    (
        "fact_calendar_daily.listing_key -> dim_listing.listing_key",
        "fact_calendar_daily",
        "listing_key",
        "dim_listing",
        "listing_key",
    ),
    (
        "fact_calendar_daily.date_key -> dim_date.date_key",
        "fact_calendar_daily",
        "date_key",
        "dim_date",
        "date_key",
    ),
    (
        "fact_review.listing_key -> dim_listing.listing_key",
        "fact_review",
        "listing_key",
        "dim_listing",
        "listing_key",
    ),
    (
        "fact_review.date_key -> dim_date.date_key",
        "fact_review",
        "date_key",
        "dim_date",
        "date_key",
    ),
]


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_ref(table: str) -> str:
    return f"{qident(GOLD_SCHEMA)}.{qident(table)}"


def query_df(conn: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return conn.execute(sql).fetchdf()


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    rendered = df.fillna("missing").astype(str)
    header = "| " + " | ".join(rendered.columns) + " |"
    separator = "| " + " | ".join("---" for _ in rendered.columns) + " |"
    rows = [
        "| " + " | ".join(row[column] for column in rendered.columns) + " |"
        for _, row in rendered.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    result = conn.execute(
        """
        select count(*) as table_count
        from information_schema.tables
        where table_schema = ?
          and table_name = ?
        """,
        [GOLD_SCHEMA, table],
    ).fetchone()
    return bool(result and result[0] > 0)


def count_rows(conn: duckdb.DuckDBPyConnection, table: str) -> int | None:
    if not table_exists(conn, table):
        return None
    return int(conn.execute(f"select count(*) from {table_ref(table)}").fetchone()[0])


def duplicate_count(conn: duckdb.DuckDBPyConnection, table: str, columns: list[str]) -> int | None:
    if not table_exists(conn, table):
        return None
    column_expr = ", ".join(qident(column) for column in columns)
    sql = f"""
        select count(*) as duplicate_groups
        from (
            select {column_expr}, count(*) as row_count
            from {table_ref(table)}
            group by {column_expr}
            having count(*) > 1
        )
    """
    return int(conn.execute(sql).fetchone()[0])


def orphan_count(
    conn: duckdb.DuckDBPyConnection,
    fact_table: str,
    fact_key: str,
    dim_table: str,
    dim_key: str,
) -> int | None:
    if not table_exists(conn, fact_table) or not table_exists(conn, dim_table):
        return None
    sql = f"""
        select count(*) as orphan_count
        from {table_ref(fact_table)} as f
        left join {table_ref(dim_table)} as d
            on f.{qident(fact_key)} = d.{qident(dim_key)}
        where f.{qident(fact_key)} is not null
          and d.{qident(dim_key)} is null
    """
    return int(conn.execute(sql).fetchone()[0])


def save_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, path: Path) -> None:
    if df.empty:
        return
    plt.figure(figsize=(10, 5))
    plt.bar(df[x].astype(str), df[y])
    plt.title(title)
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def create_visualizations(conn: duckdb.DuckDBPyConnection) -> list[Path]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    required = {"dim_listing", "fact_listing_snapshot", "dim_location", "dim_host"}
    if not all(table_exists(conn, table) for table in required):
        return created

    room_type_df = query_df(
        conn,
        f"""
        select
            coalesce(dl.room_type, 'unknown') as room_type,
            count(*) as listing_count
        from {table_ref('fact_listing_snapshot')} as fls
        inner join {table_ref('dim_listing')} as dl
            on fls.listing_key = dl.listing_key
        group by 1
        order by listing_count desc
        """,
    )
    path = FIGURES_DIR / "listing_count_by_room_type.png"
    save_bar_chart(room_type_df, "room_type", "listing_count", "Listing Count by Room Type", path)
    if path.exists():
        created.append(path)

    neighbourhood_df = query_df(
        conn,
        f"""
        select
            coalesce(loc.neighbourhood, 'unknown') as neighbourhood,
            avg(fls.price) as avg_price
        from {table_ref('fact_listing_snapshot')} as fls
        inner join {table_ref('dim_location')} as loc
            on fls.location_key = loc.location_key
        where fls.price is not null
        group by 1
        order by avg_price desc
        limit 10
        """,
    )
    path = FIGURES_DIR / "top_neighbourhood_avg_price.png"
    save_bar_chart(neighbourhood_df, "neighbourhood", "avg_price", "Top Neighbourhoods by Average Price", path)
    if path.exists():
        created.append(path)

    superhost_df = query_df(
        conn,
        f"""
        select
            case
                when dh.host_is_superhost then 'superhost'
                else 'regular_host'
            end as host_group,
            avg(fls.price) as avg_price
        from {table_ref('fact_listing_snapshot')} as fls
        inner join {table_ref('dim_host')} as dh
            on fls.host_key = dh.host_key
        where fls.price is not null
        group by 1
        order by 1
        """,
    )
    path = FIGURES_DIR / "avg_price_by_host_group.png"
    save_bar_chart(superhost_df, "host_group", "avg_price", "Average Price by Host Group", path)
    if path.exists():
        created.append(path)

    return created


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    db_path = Path(DUCKDB_PATH)

    lines = [
        "# Gold Layer Validation Report",
        "",
        f"- DuckDB path: `{db_path}`",
        f"- Gold schema: `{GOLD_SCHEMA}`",
        "",
    ]

    if not db_path.exists() and not str(db_path).startswith("md:"):
        lines.extend(
            [
                "## Status",
                "",
                "DuckDB file was not found. Run dbt build with the local target first:",
                "",
                "```bash",
                "uv run dbt build --project-dir dbt --profiles-dir dbt --target local --select gold",
                "```",
                "",
            ]
        )
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {REPORT_PATH}")
        return

    conn = duckdb.connect(str(db_path), read_only=True)

    rows = []
    for table in TABLES:
        rows.append({"table": table, "row_count": count_rows(conn, table)})
    row_counts = pd.DataFrame(rows)

    lines.extend(["## Row Counts", "", markdown_table(row_counts), ""])

    grain_rows = []
    for table, columns in GRAIN_CHECKS.items():
        grain_rows.append(
            {
                "table": table,
                "grain_columns": ", ".join(columns),
                "duplicate_groups": duplicate_count(conn, table, columns),
            }
        )
    grain_df = pd.DataFrame(grain_rows)
    lines.extend(["## Grain Checks", "", markdown_table(grain_df), ""])

    rel_rows = []
    for label, fact_table, fact_key, dim_table, dim_key in RELATIONSHIP_CHECKS:
        rel_rows.append(
            {
                "relationship": label,
                "orphan_count": orphan_count(conn, fact_table, fact_key, dim_table, dim_key),
            }
        )
    rel_df = pd.DataFrame(rel_rows)
    lines.extend(["## Relationship Checks", "", markdown_table(rel_df), ""])

    figures = create_visualizations(conn)
    lines.extend(["## Visual Checks", ""])
    if figures:
        for figure in figures:
            rel_path = figure.relative_to(PROJECT_ROOT).as_posix()
            lines.append(f"- `{rel_path}`")
    else:
        lines.append("No figures were created because required Gold tables are missing or empty.")

    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
