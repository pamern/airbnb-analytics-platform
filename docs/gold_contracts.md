# Gold Data Contracts

This document records the current Gold-layer contracts for the Airbnb warehouse.

It reflects the dbt models and tests that passed against MotherDuck on June 16, 2026.

## Design Intent

The Gold layer follows a Kimball-style star schema for the current project scope:

- dimensions store descriptive attributes
- facts store event or snapshot measures
- joins are driven by surrogate keys in Gold
- dimensions retain their natural keys where needed for business traceability
- facts retain selected natural identifiers for traceability and debugging

## Dimensions

### `dim_listing`

- Purpose: current-state listing dimension.
- Grain: one row per `listing_id`.
- Primary key: `listing_key`.
- Natural key: `listing_id`.
- Core attributes:
  - `listing_name`
  - `latitude`
  - `longitude`
  - `property_type`
  - `room_type`
  - `accommodates`
  - `bathrooms`
  - `bedrooms`
  - `beds`
  - `listing_default_minimum_nights`
  - `listing_default_maximum_nights`
  - `instant_bookable`
- Current assumptions:
  - the table represents the latest observed state of each listing
  - pricing, review scores, review counts, and availability measures do not belong in this dimension

### `dim_host`

- Purpose: current-state host dimension.
- Grain: one row per `host_id`.
- Primary key: `host_key`.
- Natural key: `host_id`.
- Core attributes:
  - `host_name`
  - `host_since`
  - `host_reported_location`
  - `host_response_time`
  - `host_response_rate`
  - `host_acceptance_rate`
  - `host_is_superhost`
  - `host_identity_verified`
  - `host_listings_count`
  - `host_total_listings_count`
- Technical metadata:
  - `source_last_scraped_date`
- Modeling note:
  - this is a current-state SCD Type 1 dimension
  - new host attribute values overwrite prior ones in Gold v1

### `dim_location`

- Purpose: location dimension for listing geography.
- Grain: one row per `city + neighbourhood`.
- Primary key: `location_key`.
- Core attributes:
  - `city`
  - `neighbourhood`
- Current assumptions:
  - Gold v1 does not include `neighbourhood_group`
  - Gold includes a reserved `neighbourhood = 'UNKNOWN'` row for each configured city
  - listings with missing `neighbourhood` values are intentionally mapped to `UNKNOWN` instead of being dropped from Gold facts

### `dim_date`

- Purpose: reusable calendar dimension for Gold facts.
- Grain: one row per date.
- Primary key: `date_key` in `YYYYMMDD` format.
- Core attributes:
  - `date_day`
  - `year`
  - `quarter`
  - `month`
  - `month_name`
  - `day`
  - `day_of_week`
  - `week_of_year`
  - `is_weekend`
- Current assumptions:
  - holiday and peak-travel enrichments are intentionally out of scope for Gold v1

## Facts

### `fact_listing_current_snapshot`

- Purpose: latest current-state listing snapshot fact.
- Grain: one row per `listing_id` at the latest scrape date kept in Silver.
- Primary key: `listing_snapshot_key`.
- Foreign keys:
  - `listing_key` -> `dim_listing`
  - `host_key` -> `dim_host`
  - `location_key` -> `dim_location`
  - `snapshot_date_key` -> `dim_date`
  - `last_review_date_key` -> `dim_date` (nullable)
- Degenerate identifiers:
  - `listing_id`
- Core measures:
  - `listing_snapshot_price`
  - `availability_30`
  - `availability_60`
  - `availability_90`
  - `availability_365`
  - `number_of_reviews`
  - `number_of_reviews_ltm`
  - `reviews_per_month`
  - `review_scores_rating`
  - `review_scores_accuracy`
  - `review_scores_cleanliness`
  - `review_scores_checkin`
  - `review_scores_communication`
  - `review_scores_location`
  - `review_scores_value`
  - `calculated_host_listings_count`
  - `listing_count` = 1
- Modeling note:
  - this is not a multi-snapshot historical fact
  - it represents the current listing state only
  - when `silver_listings.neighbourhood` is null, the fact row is preserved and mapped to `dim_location.neighbourhood = 'UNKNOWN'`

### `fact_availability_daily`

- Purpose: listing availability fact at daily grain.
- Grain: one row per `listing_id + calendar_date`.
- Primary key: `availability_daily_key`.
- Foreign keys:
  - `listing_key` -> `dim_listing`
  - `host_key` -> `dim_host`
  - `location_key` -> `dim_location`
  - `calendar_date_key` -> `dim_date`
- Degenerate identifiers:
  - `listing_id`
- Core measures and indicators:
  - `is_available`
  - `calendar_minimum_nights`
  - `calendar_maximum_nights`
- Modeling note:
  - Gold v1 does not expose daily calendar price fields because the current calendar pricing data is fully null
  - listing-level pricing analytics should use the snapshot price in `fact_listing_current_snapshot`
  - when the parent listing has a null `neighbourhood`, the row is preserved and mapped to `UNKNOWN` in `dim_location`

### `fact_review`

- Purpose: review event fact.
- Grain: one row per `review_id`.
- Primary key: `review_key`.
- Foreign keys:
  - `listing_key` -> `dim_listing`
  - `host_key` -> `dim_host`
  - `location_key` -> `dim_location`
  - `review_date_key` -> `dim_date`
- Degenerate identifiers:
  - `review_id`
  - `listing_id`
- Core measures and indicators:
  - `reviewer_id`
  - `has_comment`
  - `review_count` = 1
- Modeling note:
  - long free-text review comments are intentionally excluded from Gold v1
  - if text analytics is needed later, that should be modeled separately
  - when the parent listing has a null `neighbourhood`, the row is preserved and mapped to `UNKNOWN` in `dim_location`

## Operational Notes

- Gold joins should use surrogate keys:
  - `listing_key`
  - `host_key`
  - `location_key`
  - `date_key`
- Facts join directly to all conformed dimensions they need:
  - `dim_listing`
  - `dim_host`
  - `dim_location`
  - `dim_date`
- Natural identifiers may appear in both dimensions and facts for traceability, but they are not the primary join keys in Gold.
- `dim_location` contains an `UNKNOWN` fallback member so fact grains are preserved even when source geography is incomplete.
- Gold monitoring includes:
  - a singular test that asserts the `UNKNOWN` member exists in `dim_location`
  - row-preservation tests that compare each fact row count with its Silver parent input
  - a ratio test `unknown_location_ratio_below` on each fact, with default threshold `0.01` and optional override via `GOLD_UNKNOWN_LOCATION_MAX_RATIO`
- Baseline on June 16, 2026 after the fallback change:
  - `fact_listing_current_snapshot` unknown ratio = `0.0`
  - `fact_availability_daily` unknown ratio = `0.0`
  - `fact_review` unknown ratio = `0.0`
- If a source refresh breaks one of these assumptions:
  1. let Bronze or Silver tests fail
  2. profile the changed source pattern
  3. update the Gold contract intentionally
