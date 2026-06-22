"""Shared data loading helpers for the Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.motherduck import close_connection, connect_motherduck
from utils.sql import query_dataframe


PRICING_DATASET_SQL = """
select
    listing_dim.listing_id,
    listing_dim.listing_name,
    coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
    coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
    coalesce(listing_dim.property_type, 'UNKNOWN') as property_type,
    listing_dim.accommodates,
    fact.listing_snapshot_price as price,
    fact.estimated_occupancy_l365d,
    fact.estimated_revenue_l365d,
    fact.review_scores_rating,
    fact.number_of_reviews,
    fact.number_of_reviews_l30d,
    fact.number_of_reviews_ly,
    host_dim.host_name
from gold.fact_listing_current_snapshot as fact
inner join gold.dim_listing as listing_dim
    on fact.listing_key = listing_dim.listing_key
left join gold.dim_host as host_dim
    on fact.host_key = host_dim.host_key
left join gold.dim_location as location_dim
    on fact.location_key = location_dim.location_key
"""

HOST_QUALITY_DATASET_SQL = """
select
    fact.listing_id,
    listing_dim.listing_name,
    coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
    coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
    host_dim.host_id,
    host_dim.host_name,
    host_dim.host_response_rate,
    host_dim.host_acceptance_rate,
    host_dim.host_is_superhost,
    host_dim.host_identity_verified,
    host_dim.host_listings_count,
    host_dim.host_total_listings_count,
    fact.listing_snapshot_price as price,
    fact.number_of_reviews,
    fact.review_scores_rating,
    fact.review_scores_accuracy,
    fact.review_scores_cleanliness,
    fact.review_scores_checkin,
    fact.review_scores_communication,
    fact.review_scores_location,
    fact.review_scores_value,
    fact.availability_30
from gold.fact_listing_current_snapshot as fact
inner join gold.dim_listing as listing_dim
    on fact.listing_key = listing_dim.listing_key
inner join gold.dim_host as host_dim
    on fact.host_key = host_dim.host_key
left join gold.dim_location as location_dim
    on fact.location_key = location_dim.location_key
"""

REVIEW_EVENTS_DATASET_SQL = """
select
    review_fact.review_id,
    review_fact.listing_id,
    coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
    coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
    date_dim.date_day as review_date,
    coalesce(review_fact.has_comment, false) as has_comment
from gold.fact_review as review_fact
inner join gold.dim_date as date_dim
    on review_fact.review_date_key = date_dim.date_key
inner join gold.dim_listing as listing_dim
    on review_fact.listing_key = listing_dim.listing_key
left join gold.dim_location as location_dim
    on review_fact.location_key = location_dim.location_key
"""

OVERVIEW_DATASET_SQL = """
select
    fact.listing_id,
    listing_dim.listing_name,
    host_dim.host_id,
    coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
    coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
    fact.listing_snapshot_price as price,
    listing_dim.latitude,
    listing_dim.longitude,
    fact.estimated_occupancy_l365d,
    fact.estimated_revenue_l365d,
    fact.review_scores_rating,
    fact.number_of_reviews
from gold.fact_listing_current_snapshot as fact
inner join gold.dim_listing as listing_dim
    on fact.listing_key = listing_dim.listing_key
left join gold.dim_host as host_dim
    on fact.host_key = host_dim.host_key
left join gold.dim_location as location_dim
    on fact.location_key = location_dim.location_key
"""

FORWARD_AVAILABILITY_MONTHLY_DATASET_SQL = """
with calendar_bounds as (
    select
        min(date_dim.date_day) as calendar_start_date,
        max(date_dim.date_day) as calendar_end_date
    from gold.fact_availability_daily as fact
    inner join gold.dim_date as date_dim
        on fact.calendar_date_key = date_dim.date_key
)

select
    date_trunc('month', date_dim.date_day) as calendar_month,
    coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
    coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
    count(distinct fact.listing_id) as distinct_listings,
    sum(case when fact.is_available then 1 else 0 end) as available_listing_days,
    count(*) as observed_listing_days,
    bounds.calendar_start_date,
    bounds.calendar_end_date
from gold.fact_availability_daily as fact
inner join gold.dim_date as date_dim
    on fact.calendar_date_key = date_dim.date_key
inner join gold.dim_listing as listing_dim
    on fact.listing_key = listing_dim.listing_key
left join gold.dim_location as location_dim
    on fact.location_key = location_dim.location_key
cross join calendar_bounds as bounds
group by 1, 2, 3, 7, 8
"""

LISTING_AVAILABILITY_SUMMARY_SQL = """
with listing_availability as (
    select
        fact.listing_id,
        coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
        coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
        sum(case when fact.is_available then 1 else 0 end) as available_days,
        count(*) as observed_days,
        median(case when fact.calendar_minimum_nights > 0 then fact.calendar_minimum_nights end)
            as median_minimum_nights
    from gold.fact_availability_daily as fact
    inner join gold.dim_listing as listing_dim
        on fact.listing_key = listing_dim.listing_key
    left join gold.dim_location as location_dim
        on fact.location_key = location_dim.location_key
    group by 1, 2, 3
),
calendar_bounds as (
    select
        min(date_dim.date_day) as calendar_start_date,
        max(date_dim.date_day) as calendar_end_date
    from gold.fact_availability_daily as fact
    inner join gold.dim_date as date_dim
        on fact.calendar_date_key = date_dim.date_key
)
select
    availability.listing_id,
    availability.neighbourhood,
    availability.room_type,
    availability.available_days,
    availability.observed_days,
    availability.median_minimum_nights,
    fact.listing_snapshot_price as price,
    bounds.calendar_start_date,
    bounds.calendar_end_date
from listing_availability as availability
left join gold.fact_listing_current_snapshot as fact
    on availability.listing_id = fact.listing_id
cross join calendar_bounds as bounds
"""

LISTING_AVAILABILITY_MONTHLY_DATASET_SQL = """
with calendar_bounds as (
    select
        min(date_dim.date_day) as calendar_start_date,
        max(date_dim.date_day) as calendar_end_date
    from gold.fact_availability_daily as fact
    inner join gold.dim_date as date_dim
        on fact.calendar_date_key = date_dim.date_key
),
listing_monthly as (
    select
        fact.listing_id,
        fact.listing_key,
        date_trunc('month', date_dim.date_day) as calendar_month,
        coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
        coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
        sum(case when fact.is_available then 1 else 0 end) as available_days,
        count(*) as observed_days,
        median(
            case
                when fact.calendar_minimum_nights > 0 then fact.calendar_minimum_nights
            end
        ) as median_calendar_minimum_nights,
        snapshot_fact.listing_snapshot_price as price,
        listing_dim.latitude,
        listing_dim.longitude
    from gold.fact_availability_daily as fact
    inner join gold.dim_date as date_dim
        on fact.calendar_date_key = date_dim.date_key
    inner join gold.dim_listing as listing_dim
        on fact.listing_key = listing_dim.listing_key
    left join gold.dim_location as location_dim
        on fact.location_key = location_dim.location_key
    left join gold.fact_listing_current_snapshot as snapshot_fact
        on fact.listing_id = snapshot_fact.listing_id
    group by 1, 2, 3, 4, 5, 9, 10, 11
)
select
    monthly.listing_id,
    monthly.listing_key,
    monthly.calendar_month,
    monthly.neighbourhood,
    monthly.room_type,
    monthly.available_days,
    monthly.observed_days,
    monthly.median_calendar_minimum_nights,
    monthly.price,
    monthly.latitude,
    monthly.longitude,
    bounds.calendar_start_date,
    bounds.calendar_end_date
from listing_monthly as monthly
cross join calendar_bounds as bounds
"""


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


@st.cache_data(ttl=900, show_spinner=False)
def load_pricing_dataset() -> pd.DataFrame:
    """Load the listing-level dataset used by the pricing dashboard page."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, PRICING_DATASET_SQL)
    finally:
        close_connection(connection)

    _validate_unique_listing_grain(
        dataset,
        "Pricing dataset",
    )
    dataset = dataset.copy()
    dataset["listing_name"] = dataset["listing_name"].fillna("Unnamed listing")
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["property_type"] = dataset["property_type"].fillna("UNKNOWN")
    dataset["host_name"] = dataset["host_name"].fillna("Unknown host")
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


@st.cache_data(ttl=900, show_spinner=False)
def load_host_quality_dataset() -> pd.DataFrame:
    """Load the listing-host snapshot dataset used by the host quality page."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, HOST_QUALITY_DATASET_SQL)
    finally:
        close_connection(connection)

    _validate_unique_listing_grain(dataset, "Host quality dataset")
    dataset = dataset.copy()
    dataset["listing_name"] = dataset["listing_name"].fillna("Unnamed listing")
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["host_name"] = dataset["host_name"].fillna("Unknown host")
    numeric_columns = [
        "host_response_rate",
        "host_acceptance_rate",
        "host_listings_count",
        "host_total_listings_count",
        "price",
        "number_of_reviews",
        "review_scores_rating",
        "review_scores_accuracy",
        "review_scores_cleanliness",
        "review_scores_checkin",
        "review_scores_communication",
        "review_scores_location",
        "review_scores_value",
        "availability_30",
    ]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    boolean_columns = ["host_is_superhost", "host_identity_verified"]
    for column in boolean_columns:
        dataset[column] = dataset[column].fillna(False).astype(bool)
    return dataset


@st.cache_data(ttl=900, show_spinner=False)
def load_review_events_dataset() -> pd.DataFrame:
    """Load review-event data for trend and comment-rate analysis."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, REVIEW_EVENTS_DATASET_SQL)
    finally:
        close_connection(connection)

    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["review_date"] = pd.to_datetime(dataset["review_date"], errors="coerce")
    dataset["has_comment"] = dataset["has_comment"].fillna(False).astype(bool)
    return dataset


@st.cache_data(ttl=900, show_spinner=False)
def load_overview_dataset() -> pd.DataFrame:
    """Load the listing snapshot dataset used by the market overview page."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, OVERVIEW_DATASET_SQL)
    finally:
        close_connection(connection)

    _validate_unique_listing_grain(
        dataset,
        "Market overview dataset",
    )
    dataset = dataset.copy()
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


@st.cache_data(ttl=900, show_spinner=False)
def load_forward_availability_monthly_dataset() -> pd.DataFrame:
    """Load forward-looking monthly availability aggregates for the location page."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, FORWARD_AVAILABILITY_MONTHLY_DATASET_SQL)
    finally:
        close_connection(connection)

    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["calendar_month"] = pd.to_datetime(dataset["calendar_month"], errors="coerce")
    dataset["calendar_start_date"] = pd.to_datetime(dataset["calendar_start_date"], errors="coerce")
    dataset["calendar_end_date"] = pd.to_datetime(dataset["calendar_end_date"], errors="coerce")
    numeric_columns = [
        "distinct_listings",
        "available_listing_days",
        "observed_listing_days",
    ]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    return dataset


@st.cache_data(ttl=900, show_spinner=False)
def load_listing_availability_summary() -> pd.DataFrame:
    """Load listing-level forward availability summaries for the location page."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, LISTING_AVAILABILITY_SUMMARY_SQL)
    finally:
        close_connection(connection)

    _validate_unique_listing_grain(
        dataset,
        "Listing availability summary dataset",
    )
    dataset = dataset.copy()
    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["calendar_start_date"] = pd.to_datetime(dataset["calendar_start_date"], errors="coerce")
    dataset["calendar_end_date"] = pd.to_datetime(dataset["calendar_end_date"], errors="coerce")
    numeric_columns = [
        "available_days",
        "observed_days",
        "median_minimum_nights",
        "price",
    ]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    dataset["availability_share"] = (
        dataset["available_days"] / dataset["observed_days"].replace(0, pd.NA)
    )
    return dataset


@st.cache_data(ttl=900, show_spinner=False)
def load_listing_availability_monthly_dataset() -> pd.DataFrame:
    """Load listing-by-month forward availability data from Gold facts."""
    connection = connect_motherduck(read_only=True)
    try:
        dataset = query_dataframe(connection, LISTING_AVAILABILITY_MONTHLY_DATASET_SQL)
    finally:
        close_connection(connection)

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
