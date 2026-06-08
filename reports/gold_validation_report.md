# Gold Layer Validation Report

- DuckDB path: `airbnb_analytics.duckdb`
- Gold schema: `gold`

## Row Counts

| table | row_count |
| --- | --- |
| dim_listing | missing |
| dim_host | missing |
| dim_location | missing |
| dim_date | missing |
| fact_listing_snapshot | missing |
| fact_calendar_daily | missing |
| fact_review | missing |
| mart_neighbourhood_market | missing |
| mart_host_performance | missing |
| mart_competitor_benchmark | missing |
| mart_ml_price_features | missing |
| mart_llm_area_summary | missing |

## Grain Checks

| table | grain_columns | duplicate_groups |
| --- | --- | --- |
| dim_listing | listing_key | missing |
| dim_host | host_key | missing |
| dim_location | location_key | missing |
| dim_date | date_key | missing |
| fact_listing_snapshot | listing_key | missing |
| fact_calendar_daily | listing_key, date_key | missing |
| fact_review | review_key | missing |
| mart_neighbourhood_market | location_key, room_type | missing |
| mart_host_performance | host_key | missing |
| mart_competitor_benchmark | listing_id, competitor_listing_id | missing |
| mart_ml_price_features | listing_id | missing |
| mart_llm_area_summary | location_key, room_type | missing |

## Relationship Checks

| relationship | orphan_count |
| --- | --- |
| fact_listing_snapshot.listing_key -> dim_listing.listing_key | missing |
| fact_listing_snapshot.host_key -> dim_host.host_key | missing |
| fact_listing_snapshot.location_key -> dim_location.location_key | missing |
| fact_calendar_daily.listing_key -> dim_listing.listing_key | missing |
| fact_calendar_daily.date_key -> dim_date.date_key | missing |
| fact_review.listing_key -> dim_listing.listing_key | missing |
| fact_review.date_key -> dim_date.date_key | missing |

## Visual Checks

No figures were created because required Gold tables are missing or empty.
