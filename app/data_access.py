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
where fact.listing_snapshot_price is not null
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
    coalesce(silver_review.has_comment, false) as has_comment
from gold.fact_review as review_fact
inner join gold.dim_date as date_dim
    on review_fact.review_date_key = date_dim.date_key
inner join gold.dim_listing as listing_dim
    on review_fact.listing_key = listing_dim.listing_key
left join gold.dim_location as location_dim
    on review_fact.location_key = location_dim.location_key
left join silver.silver_reviews as silver_review
    on review_fact.review_id = silver_review.review_id
"""


@st.cache_data(ttl=900, show_spinner=False)
def load_pricing_dataset() -> pd.DataFrame:
    """Load the listing-level dataset used by the pricing dashboard page."""
    connection = connect_motherduck(read_only=False)
    try:
        dataset = query_dataframe(connection, PRICING_DATASET_SQL)
    finally:
        close_connection(connection)

    dataset = dataset.drop_duplicates(subset=["listing_id"]).copy()
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
    connection = connect_motherduck(read_only=False)
    try:
        dataset = query_dataframe(connection, HOST_QUALITY_DATASET_SQL)
    finally:
        close_connection(connection)

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
    connection = connect_motherduck(read_only=False)
    try:
        dataset = query_dataframe(connection, REVIEW_EVENTS_DATASET_SQL)
    finally:
        close_connection(connection)

    dataset["neighbourhood"] = dataset["neighbourhood"].fillna("UNKNOWN")
    dataset["room_type"] = dataset["room_type"].fillna("UNKNOWN")
    dataset["review_date"] = pd.to_datetime(dataset["review_date"], errors="coerce")
    dataset["has_comment"] = dataset["has_comment"].fillna(False).astype(bool)
    return dataset
