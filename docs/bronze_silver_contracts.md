# Bronze and Silver Data Contracts

This document records the current data contracts for the core Airbnb warehouse tables.

It is based on the dbt models and tests that passed against MotherDuck on June 16, 2026.

## Bronze Layer

### `bronze_listings`

- Purpose: raw listing-level Airbnb data loaded from the ingestion layer.
- Expected grain: one row per raw `id`.
- Primary raw key: `id`.
- Current assumptions:
  - `id` is present.
  - `id` is unique in the current raw load.
  - `host_id` is present.
- Current source tests:
  - `id` is `not_null`
  - `id` is `unique`
  - `host_id` is `not_null`

### `bronze_calendar`

- Purpose: raw daily calendar data by listing and date, mainly used for availability analysis. Price-related fields are retained when available but are not treated as the primary pricing source in the current dataset.
- Expected grain: one row per `listing_id + date`.
- Primary raw key: `listing_id + date`.
- Current assumptions:
  - `listing_id` is present.
  - `date` is present.
  - `listing_id + date` is unique in the current raw load.
- Current source tests:
  - `listing_id` is `not_null`
  - `date` is `not_null`
  - `listing_id + date` is unique

### `bronze_reviews`

- Purpose: raw review-level Airbnb data.
- Expected grain: one row per raw `id`.
- Primary raw key: `id`.
- Current assumptions:
  - `id` is present.
  - `id` is unique in the current raw load.
  - `listing_id` is present.
- Current source tests:
  - `id` is `not_null`
  - `id` is `unique`
  - `listing_id` is `not_null`

## Silver Layer

### `silver_listings`

- Purpose: cleaned and standardized listing-level table.
- Expected grain: one row per `listing_id`.
- Primary key: `listing_id`.
- Core transformations:
  - normalize ids, dates, booleans, percentages, and monetary fields
  - fallback between related raw columns where appropriate
  - keep the latest row per `listing_id` using `last_scraped`
- Current assumptions:
  - `listing_id` is unique after cleaning
  - `host_id` is present
  - numeric and geographic fields fall within expected ranges
- Current tests:
  - `listing_id` is `not_null`
  - `listing_id` is `unique`
  - `host_id` is `not_null`
  - `price` is positive or null
  - `host_response_rate` is between `0` and `1`
  - `host_acceptance_rate` is between `0` and `1`
  - `availability_365` is between `0` and `365`
  - `room_type` is in the accepted set
  - `latitude` is between `-90` and `90`
  - `longitude` is between `-180` and `180`
  - `minimum_nights` is positive or null
  - `maximum_nights` is positive or null
  - `minimum_nights <= maximum_nights`

### `silver_calendar`

- Purpose: cleaned and standardized daily listing availability and pricing table.
- Expected grain: one row per `listing_id + calendar_date`.
- Primary key: `listing_id + calendar_date`.
- Core transformations:
  - cast raw text into numeric, boolean, and date fields
  - keep only rows with valid `listing_id` and `calendar_date`
  - do not apply heuristic deduplication because the current Bronze data has no duplicate keys
- Current assumptions:
  - Bronze currently preserves uniqueness for `listing_id + date`
  - each Silver calendar row should reference a valid listing
- Current tests:
  - `listing_id + calendar_date` is unique
  - `listing_id` is `not_null`
  - `calendar_date` is `not_null`
  - `price` is positive or null
  - `adjusted_price` is positive or null
  - `minimum_nights <= maximum_nights`
  - `listing_id` has a relationship to `silver_listings.listing_id`

### `silver_reviews`

- Purpose: cleaned and standardized review-level table.
- Expected grain: one row per `review_id`.
- Primary key: `review_id`.
- Core transformations:
  - normalize ids, dates, and text fields
  - keep only rows with valid `review_id` and `listing_id`
  - do not apply heuristic deduplication because the current Bronze data has no duplicate `review_id`
- Current assumptions:
  - Bronze currently preserves uniqueness for `id`
  - each Silver review row should reference a valid listing
- Current tests:
  - `review_id` is `not_null`
  - `review_id` is `unique`
  - `listing_id` is `not_null`
  - `review_date` is `not_null`
  - `listing_id` has a relationship to `silver_listings.listing_id`

## Operational Notes

- Bronze tests protect raw-layer data contracts and catch upstream issues early.
- Silver tests protect cleaned-layer grain, referential integrity, and sanity constraints.
- `source_column()` now fails fast for required columns. Optional raw columns must explicitly pass `default='NULL'`.
- If a future data refresh breaks one of these assumptions, the expected response is:
  1. let the failing test surface the contract change
  2. profile the affected source data
  3. update the model or contract intentionally
