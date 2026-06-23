"""Shared data loading helpers for the Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.sql import query_dataframe
from configs.paths import DATA_DIR

GOLD_DIR = (DATA_DIR / "gold").as_posix()


PRICING_DATASET_SQL = """
select
    listing_id,
    host_id,
    neighbourhood,
    room_type,
    accommodates,
    price,
    price_per_person,
    estimated_occupancy_l365d,
    estimated_occupancy_rate_l365d,
    estimated_revenue_l365d,
    review_scores_rating,
    number_of_reviews,
    number_of_reviews_l30d,
    number_of_reviews_ly
from '{GOLD_DIR}/mart_dashboard_listing_snapshot.parquet'
""".format(GOLD_DIR=GOLD_DIR)

HOST_QUALITY_DATASET_SQL = """
select
    listing_id,
    neighbourhood,
    room_type,
    host_id,
    host_response_rate,
    host_acceptance_rate,
    host_is_superhost,
    host_identity_verified,
    host_listings_count,
    host_total_listings_count,
    host_size_group,
    price,
    number_of_reviews,
    review_scores_rating,
    review_scores_accuracy,
    review_scores_cleanliness,
    review_scores_checkin,
    review_scores_communication,
    review_scores_location,
    review_scores_value,
    is_reliable_review,
    review_quality_band,
    availability_30
from '{GOLD_DIR}/mart_dashboard_listing_snapshot.parquet'
""".format(GOLD_DIR=GOLD_DIR)

REVIEW_RECENCY_DATASET_SQL = """
select
    listing_id,
    last_review_date,
    review_event_count,
    comment_count,
    has_any_comment,
    global_latest_review_date,
    days_since_last_review
from '{GOLD_DIR}/mart_dashboard_listing_review_recency.parquet'
""".format(GOLD_DIR=GOLD_DIR)

OVERVIEW_DATASET_SQL = """
select
    listing_id,
    host_id,
    neighbourhood,
    room_type,
    price,
    latitude,
    longitude,
    estimated_occupancy_l365d,
    estimated_revenue_l365d,
    estimated_occupancy_rate_l365d,
    number_of_reviews,
    review_scores_rating,
    is_reliable_review
from '{GOLD_DIR}/mart_dashboard_listing_snapshot.parquet'
""".format(GOLD_DIR=GOLD_DIR)

LISTING_AVAILABILITY_MONTHLY_DATASET_SQL = """
select
    listing_id,
    listing_key,
    calendar_month,
    neighbourhood,
    room_type,
    available_days,
    observed_days,
    availability_share,
    median_calendar_minimum_nights,
    price,
    latitude,
    longitude,
    calendar_start_date,
    calendar_end_date
from '{GOLD_DIR}/mart_dashboard_listing_monthly_availability.parquet'
""".format(GOLD_DIR=GOLD_DIR)


def _validate_unique_listing_grain(dataset: pd.DataFrame, dataset_name: str) -> None:
    """Fail fast when a listing-level dataset unexpectedly returns duplicate listings."""
    if "listing_id" not in dataset.columns:
        raise ValueError(f"{dataset_name} is missing required column listing_id.")

    duplicate_mask = dataset["listing_id"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_count = int(duplicate_mask.sum())
        sample_ids = (
            dataset.loc[duplicate_mask, "listing_id"]
            .dropna()
            .astype(str)
            .drop_duplicates()
            .head(5)
            .tolist()
        )
        raise ValueError(
            f"{dataset_name} returned duplicate listing_id rows "
            f"({duplicate_count} duplicate rows; sample listing_id values: {', '.join(sample_ids) or 'N/A'})."
        )


def _validate_unique_combination_grain(
    dataset: pd.DataFrame,
    dataset_name: str,
    grain_columns: list[str],
) -> None:
    missing_columns = [column for column in grain_columns if column not in dataset.columns]
    if missing_columns:
        raise ValueError(
            f"{dataset_name} is missing required grain columns: {', '.join(missing_columns)}."
        )

    null_mask = dataset[grain_columns].isna().any(axis=1)
    if null_mask.any():
        raise ValueError(
            f"{dataset_name} returned null values in grain columns {', '.join(grain_columns)}."
        )

    duplicate_mask = dataset.duplicated(subset=grain_columns, keep=False)
    if duplicate_mask.any():
        duplicate_rows = dataset.loc[duplicate_mask, grain_columns].drop_duplicates().head(5)
        raise ValueError(
            f"{dataset_name} returned duplicate rows at grain "
            f"{' + '.join(grain_columns)}. Sample duplicates: "
            f"{duplicate_rows.to_dict(orient='records')}"
        )


@st.cache_data(ttl=3600, show_spinner=False)
def load_pricing_dataset() -> pd.DataFrame:
    """Load the listing-level dataset used by the pricing dashboard page."""
    connection = duckdb.connect(":memory:")
    try:
        dataset = query_dataframe(connection, PRICING_DATASET_SQL)
    finally:
        connection.close()

    _validate_unique_listing_grain(
        dataset,
        "Pricing dataset",
    )
    dataset = dataset.copy()
    if "listing_name" not in dataset.columns:
        dataset["listing_name"] = "Listing " + dataset["listing_id"].astype("string")
    else:
        dataset["listing_name"] = dataset["listing_name"].fillna("Unnamed listing")
    if "host_name" not in dataset.columns:
        dataset["host_name"] = "Host " + dataset["host_id"].astype("string")
    else:
        dataset["host_name"] = dataset["host_name"].fillna("Unknown host")
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    if "property_type" in dataset.columns:
        dataset["property_type"] = dataset["property_type"].fillna("UNKNOWN")
    dataset["accommodates"] = pd.to_numeric(dataset["accommodates"], errors="coerce")
    dataset["price"] = pd.to_numeric(dataset["price"], errors="coerce")
    dataset["estimated_occupancy_l365d"] = pd.to_numeric(
        dataset["estimated_occupancy_l365d"],
        errors="coerce",
    )
    dataset["estimated_revenue_l365d"] = pd.to_numeric(
        dataset["estimated_revenue_l365d"],
        errors="coerce",
    )
    dataset["review_scores_rating"] = pd.to_numeric(
        dataset["review_scores_rating"],
        errors="coerce",
    )
    dataset["number_of_reviews"] = pd.to_numeric(
        dataset["number_of_reviews"],
        errors="coerce",
    ).fillna(0)
    dataset["number_of_reviews_l30d"] = pd.to_numeric(
        dataset["number_of_reviews_l30d"],
        errors="coerce",
    ).fillna(0)
    dataset["number_of_reviews_ly"] = pd.to_numeric(
        dataset["number_of_reviews_ly"],
        errors="coerce",
    ).fillna(0)

    valid_capacity = dataset["accommodates"].where(dataset["accommodates"] > 0)
    dataset["price_per_person"] = dataset["price"] / valid_capacity
    return dataset


@st.cache_data(ttl=3600, show_spinner=False)
def load_host_quality_dataset() -> pd.DataFrame:
    """Load the listing-host snapshot dataset used by the host quality page."""
    connection = duckdb.connect(":memory:")
    try:
        dataset = query_dataframe(connection, HOST_QUALITY_DATASET_SQL)
    finally:
        connection.close()

    _validate_unique_listing_grain(dataset, "Host quality dataset")
    dataset = dataset.copy()
    if "listing_name" not in dataset.columns:
        dataset["listing_name"] = "Listing " + dataset["listing_id"].astype("string")
    else:
        dataset["listing_name"] = dataset["listing_name"].fillna("Unnamed listing")
    if "host_name" not in dataset.columns:
        dataset["host_name"] = "Host " + dataset["host_id"].astype("string")
    else:
        dataset["host_name"] = dataset["host_name"].fillna("Unknown host")
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    numeric_columns = [
        "host_response_rate",
        "host_acceptance_rate",
        "host_listings_count",
        "host_total_listings_count",
        "price",
        "price_per_person",
        "number_of_reviews",
        "number_of_reviews_l30d",
        "number_of_reviews_ltm",
        "number_of_reviews_ly",
        "reviews_per_month",
        "review_scores_rating",
        "review_scores_accuracy",
        "review_scores_cleanliness",
        "review_scores_checkin",
        "review_scores_communication",
        "review_scores_location",
        "review_scores_value",
        "availability_30",
        "availability_60",
        "availability_90",
        "availability_365",
        "estimated_occupancy_l365d",
        "estimated_occupancy_rate_l365d",
        "estimated_revenue_l365d",
    ]
    for column in numeric_columns:
        if column in dataset.columns:
            dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    boolean_columns = ["host_is_superhost", "host_identity_verified"]
    for column in boolean_columns:
        dataset[column] = dataset[column].fillna(False).astype(bool)
    if "is_reliable_review" in dataset.columns:
        dataset["is_reliable_review"] = dataset["is_reliable_review"].fillna(False).astype(bool)
    return dataset


@st.cache_data(ttl=3600, show_spinner=False)
def load_listing_review_recency_dataset() -> pd.DataFrame:
    """Load listing-level review recency data for the host quality page."""
    connection = duckdb.connect(":memory:")
    try:
        dataset = query_dataframe(connection, REVIEW_RECENCY_DATASET_SQL)
    finally:
        connection.close()

    dataset = dataset.copy()
    date_columns = ["last_review_date", "global_latest_review_date"]
    for column in date_columns:
        dataset[column] = pd.to_datetime(dataset[column], errors="coerce")
    numeric_columns = ["listing_id", "review_event_count", "comment_count", "days_since_last_review"]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    dataset["has_any_comment"] = dataset["has_any_comment"].fillna(False).astype(bool)
    _validate_unique_listing_grain(dataset, "Listing review recency dataset")
    return dataset


@st.cache_data(ttl=3600, show_spinner=False)
def load_overview_dataset() -> pd.DataFrame:
    """Load the listing snapshot dataset used by the market overview page."""
    connection = duckdb.connect(":memory:")
    try:
        dataset = query_dataframe(connection, OVERVIEW_DATASET_SQL)
    finally:
        connection.close()

    _validate_unique_listing_grain(
        dataset,
        "Market overview dataset",
    )
    dataset = dataset.copy()
    if "listing_name" in dataset.columns:
        dataset["listing_name"] = dataset["listing_name"].fillna("Unnamed listing")
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")

    numeric_columns = [
        "host_id",
        "price",
        "latitude",
        "longitude",
        "estimated_occupancy_l365d",
        "estimated_revenue_l365d",
        "review_scores_rating",
        "number_of_reviews",
    ]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")

    dataset["estimated_occupancy_rate_l365d"] = (
        dataset["estimated_occupancy_l365d"] / 365.0
    )
    dataset["estimated_occupancy_rate_l365d"] = dataset[
        "estimated_occupancy_rate_l365d"
    ].where(
        dataset["estimated_occupancy_l365d"].between(0, 365, inclusive="both")
    )
    dataset["is_reliable_review"] = (
        dataset["review_scores_rating"].notna()
        & dataset["number_of_reviews"].fillna(0).ge(5)
    )
    return dataset


@st.cache_data(ttl=3600, show_spinner=False)
def load_listing_availability_monthly_dataset() -> pd.DataFrame:
    """Load listing-by-month forward availability data from the dashboard mart."""
    parquet_path = DATA_DIR / "gold" / "mart_dashboard_listing_monthly_availability.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            "Local data cache not ready yet. Run `uv run python scripts/export_gold_to_parquet.py` "
            "to sync data from MotherDuck, then refresh the page."
        )

    connection = duckdb.connect(":memory:")
    try:
        dataset = query_dataframe(connection, LISTING_AVAILABILITY_MONTHLY_DATASET_SQL)
    finally:
        connection.close()

    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["calendar_month"] = pd.to_datetime(dataset["calendar_month"], errors="coerce")
    dataset["calendar_start_date"] = pd.to_datetime(dataset["calendar_start_date"], errors="coerce")
    dataset["calendar_end_date"] = pd.to_datetime(dataset["calendar_end_date"], errors="coerce")

    numeric_columns = [
        "listing_id",
        "available_days",
        "observed_days",
        "median_calendar_minimum_nights",
        "price",
        "latitude",
        "longitude",
    ]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    dataset["listing_key"] = dataset["listing_key"].astype("string")

    _validate_unique_combination_grain(
        dataset,
        "Listing availability monthly dataset",
        ["listing_id", "calendar_month"],
    )

    dataset["availability_share"] = (
        dataset["available_days"] / dataset["observed_days"].replace(0, pd.NA)
    )
    return dataset
