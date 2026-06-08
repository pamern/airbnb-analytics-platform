from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DEFAULT_DB_PATH = PROJECT_ROOT / "airbnb_analytics.duckdb"
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN", "")
MOTHERDUCK_DATABASE = os.getenv("MOTHERDUCK_DATABASE", "airbnb_analytics")
USE_MOTHERDUCK = os.getenv("STREAMLIT_USE_MOTHERDUCK", "true").lower() in {"1", "true", "yes", "y"}
CONNECTION_PATH = (
    f"md:{MOTHERDUCK_DATABASE}"
    if USE_MOTHERDUCK and MOTHERDUCK_TOKEN
    else os.getenv("DUCKDB_LOCAL_PATH", str(DEFAULT_DB_PATH))
)
GOLD_SCHEMA = os.getenv("DBT_GOLD_SCHEMA", "gold")

GOLD_TABLES = [
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


st.set_page_config(
    page_title="Bangkok Airbnb Analytics",
    page_icon="",
    layout="wide",
)


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_ref(table: str) -> str:
    return f"{qident(GOLD_SCHEMA)}.{qident(table)}"


@st.cache_resource
def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(CONNECTION_PATH, read_only=True)


def table_exists(table: str) -> bool:
    con = connect()
    row = con.execute(
        """
        select count(*) as table_count
        from information_schema.tables
        where table_schema = ?
          and table_name = ?
        """,
        [GOLD_SCHEMA, table],
    ).fetchone()
    return bool(row and row[0] > 0)


def query(sql: str) -> pd.DataFrame:
    return connect().execute(sql).fetchdf()


def row_count(table: str) -> int | None:
    if not table_exists(table):
        return None
    return int(query(f"select count(*) as row_count from {table_ref(table)}")["row_count"].iloc[0])


def table_status() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "table": table,
                "status": "ready" if table_exists(table) else "missing",
                "row_count": row_count(table),
            }
            for table in GOLD_TABLES
        ]
    )


def render_missing_state(status: pd.DataFrame) -> None:
    st.warning("Gold tables are not built in the local DuckDB file yet.")
    st.dataframe(status, use_container_width=True, hide_index=True)
    st.code(
        "uv run dbt build --project-dir dbt --profiles-dir dbt --target local --select gold\n"
        "uv run python scripts/validate_gold_layer.py",
        language="bash",
    )


def render_market_overview() -> None:
    kpi = query(
        f"""
        select
            count(distinct dl.listing_id) as total_listings,
            count(distinct dh.host_id) as total_hosts,
            avg(fls.price) as avg_price,
            median(fls.price) as median_price,
            avg(fls.review_scores_rating) as avg_rating,
            avg(fls.availability_365) as avg_availability_365
        from {table_ref('fact_listing_snapshot')} as fls
        left join {table_ref('dim_listing')} as dl
            on fls.listing_key = dl.listing_key
        left join {table_ref('dim_host')} as dh
            on fls.host_key = dh.host_key
        """
    ).iloc[0]

    cols = st.columns(6)
    cols[0].metric("Listings", f"{kpi['total_listings']:,.0f}")
    cols[1].metric("Hosts", f"{kpi['total_hosts']:,.0f}")
    cols[2].metric("Avg Price", f"{kpi['avg_price']:,.2f}")
    cols[3].metric("Median Price", f"{kpi['median_price']:,.2f}")
    cols[4].metric("Avg Rating", f"{kpi['avg_rating']:,.2f}")
    cols[5].metric("Avg Avail 365", f"{kpi['avg_availability_365']:,.0f}")

    left, right = st.columns(2)

    room_type = query(
        f"""
        select dl.room_type, count(*) as listing_count
        from {table_ref('fact_listing_snapshot')} as fls
        inner join {table_ref('dim_listing')} as dl
            on fls.listing_key = dl.listing_key
        group by 1
        order by listing_count desc
        """
    )
    left.plotly_chart(
        px.bar(room_type, x="room_type", y="listing_count", title="Listing by Room Type"),
        use_container_width=True,
    )

    top_area = query(
        f"""
        select neighbourhood, room_type, avg_price, listing_count
        from {table_ref('mart_neighbourhood_market')}
        where avg_price is not null
        order by avg_price desc
        limit 15
        """
    )
    right.plotly_chart(
        px.bar(top_area, x="neighbourhood", y="avg_price", color="room_type", title="Top Areas by Avg Price"),
        use_container_width=True,
    )

    listings_geo = query(
        f"""
        select
            dl.latitude,
            dl.longitude,
            dl.room_type,
            fls.price,
            fls.review_scores_rating
        from {table_ref('dim_listing')} as dl
        inner join {table_ref('fact_listing_snapshot')} as fls
            on dl.listing_key = fls.listing_key
        where dl.latitude is not null
          and dl.longitude is not null
        limit 5000
        """
    )
    st.plotly_chart(
        px.scatter_map(
            listings_geo,
            lat="latitude",
            lon="longitude",
            color="room_type",
            size="price",
            hover_data=["price", "review_scores_rating"],
            zoom=10,
            title="Listing Map",
        ),
        use_container_width=True,
    )


def render_host_competitor() -> None:
    left, right = st.columns(2)

    superhost = query(
        f"""
        select
            case when host_is_superhost then 'Superhost' else 'Regular host' end as host_group,
            avg(avg_price) as avg_price,
            avg(avg_rating) as avg_rating,
            avg(avg_reviews_per_month) as avg_reviews_per_month
        from {table_ref('mart_host_performance')}
        group by 1
        """
    )
    left.plotly_chart(
        px.bar(superhost, x="host_group", y="avg_price", title="Average Price by Host Group"),
        use_container_width=True,
    )
    right.plotly_chart(
        px.bar(superhost, x="host_group", y="avg_rating", title="Average Rating by Host Group"),
        use_container_width=True,
    )

    hosts = query(
        f"""
        select host_name, observed_listing_count, avg_price, avg_rating, avg_reviews_per_month
        from {table_ref('mart_host_performance')}
        order by observed_listing_count desc nulls last
        limit 20
        """
    )
    st.dataframe(hosts, use_container_width=True, hide_index=True)

    if table_exists("mart_competitor_benchmark") and row_count("mart_competitor_benchmark"):
        st.subheader("Competitor Benchmark Sample")
        competitors = query(
            f"""
            select *
            from {table_ref('mart_competitor_benchmark')}
            order by listing_id, benchmark_rank
            limit 100
            """
        )
        st.dataframe(competitors, use_container_width=True, hide_index=True)


def render_ml_llm() -> None:
    st.subheader("ML Price Feature Dataset")
    features = query(
        f"""
        select *
        from {table_ref('mart_ml_price_features')}
        limit 100
        """
    )
    st.dataframe(features, use_container_width=True, hide_index=True)

    st.subheader("LLM Area Context")
    llm_context = query(
        f"""
        select neighbourhood, room_type, listing_count, avg_price, median_price,
               avg_rating, avg_availability_365, avg_reviews_per_month, pricing_note
        from {table_ref('mart_llm_area_summary')}
        order by listing_count desc
        limit 50
        """
    )
    st.dataframe(llm_context, use_container_width=True, hide_index=True)


st.title("Bangkok Airbnb Price & Market Intelligence")
source_label = f"MotherDuck database `{MOTHERDUCK_DATABASE}`" if CONNECTION_PATH.startswith("md:") else f"DuckDB `{CONNECTION_PATH}`"
st.caption(f"Reading {source_label} schema `{GOLD_SCHEMA}`")

status_df = table_status()
ready_tables = set(status_df.loc[status_df["status"] == "ready", "table"])

with st.expander("Gold table status", expanded=len(ready_tables) < len(GOLD_TABLES)):
    st.dataframe(status_df, use_container_width=True, hide_index=True)

required_core = {
    "dim_listing",
    "dim_host",
    "dim_location",
    "fact_listing_snapshot",
    "mart_neighbourhood_market",
    "mart_host_performance",
    "mart_ml_price_features",
    "mart_llm_area_summary",
}

if not required_core.issubset(ready_tables):
    render_missing_state(status_df)
else:
    tab_market, tab_host, tab_ml = st.tabs(
        [
            "Market Overview & Geospatial",
            "Host & Competitor",
            "ML & LLM",
        ]
    )
    with tab_market:
        render_market_overview()
    with tab_host:
        render_host_competitor()
    with tab_ml:
        render_ml_llm()
