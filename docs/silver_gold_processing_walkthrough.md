# Silver and Gold Processing Walkthrough

This document describes the current end-to-end processing logic for the Airbnb warehouse from Bronze into Silver and Gold.

It is intended as a practical review guide so the project owner can quickly check:

- what each model reads
- how each field is cleaned or derived
- what grain each model keeps
- where deduplication happens
- how Silver feeds Gold
- what tests protect the contracts

This walkthrough reflects the dbt models and tests that passed on MotherDuck on June 16, 2026.

## 1. Overall Flow

The current warehouse flow is:

1. `bronze_listings` -> `silver_listings`
2. `bronze_calendar` -> `silver_calendar`
3. `bronze_reviews` -> `silver_reviews`
4. `bronze_neighbourhoods` -> `silver_neighbourhoods`
5. Silver models feed Gold dimensions:
   - `silver_listings` -> `dim_listing`
   - `silver_listings` -> `dim_host`
   - `silver_listings` -> `dim_location`
   - `silver_calendar`, `silver_reviews`, `silver_listings` -> `dim_date`
6. Silver models feed Gold facts:
   - `silver_listings` -> `fact_listing_current_snapshot`
   - `silver_calendar` + `silver_listings` -> `fact_availability_daily`
   - `silver_reviews` + `silver_listings` -> `fact_review`

The design intent is:

- Silver is the cleaned and standardized layer
- Gold is the business-facing dimensional layer
- Silver keeps natural business keys
- Gold introduces surrogate keys and star-schema joins

## 2. Shared Macros Used in Silver

Several reusable macros standardize raw source values before they reach Silver:

### `clean_money(expression)`

- strips currency symbols and non-numeric characters
- returns a numeric `double`
- used for listing prices and calendar prices

Example:

- `"$145.00"` -> `145.0`

### `clean_percent(expression)`

- strips non-numeric characters
- casts to `double`
- divides by `100`

Example:

- `"95%"` -> `0.95`

### `clean_boolean(expression)`

- maps common true-like values to `true`
- maps common false-like values to `false`
- returns `null` when the text is not recognized

Recognized true values:

- `t`
- `true`
- `1`
- `yes`
- `y`

Recognized false values:

- `f`
- `false`
- `0`
- `no`
- `n`

### `clean_text(expression)`

- trims text
- converts empty strings to `null`

### `source_column(relation, column_name, alias='src', default=none)`

- checks whether a column actually exists in the source relation
- returns the quoted source column name if found
- returns the supplied default if the column is optional and missing
- raises a compiler error if a required source column is missing

This macro is important because it prevents silent schema drift from Bronze into Silver.

## 3. Silver Layer

## 3.1 `silver_listings`

### Purpose

`silver_listings` is the cleaned listing-level master table.

It is the main parent model for:

- listing dimensions
- host dimensions
- location dimensions
- snapshot facts
- reference joins from calendar and reviews

### Input

- `bronze_listings`

### Output Grain

- one row per `listing_id`

### Key Cleaning and Standardization Steps

#### Identifiers

- raw `id` -> `listing_id` as `bigint`
- raw `host_id` -> `host_id` as `bigint`

#### Text fields

The following are trimmed and empty values become `null`:

- `listing_name`
- `host_name`
- `host_location`
- `host_response_time`
- `property_type`
- `room_type`
- `amenities`

#### Dates

These are cast to `date`:

- `host_since`
- `last_review`
- `last_scraped`

#### Rates and booleans

- `host_response_rate` uses `clean_percent`
- `host_acceptance_rate` uses `clean_percent`
- `host_is_superhost` uses `clean_boolean`
- `host_identity_verified` uses `clean_boolean`
- `instant_bookable` uses `clean_boolean`

#### Numeric listing attributes

These are cast to numeric types:

- `host_listings_count`
- `host_total_listings_count`
- `accommodates`
- `bathrooms`
- `bedrooms`
- `beds`
- `minimum_nights`
- `maximum_nights`
- `availability_30`
- `availability_60`
- `availability_90`
- `availability_365`
- `number_of_reviews`
- `number_of_reviews_ltm`
- `review_scores_rating`
- `review_scores_accuracy`
- `review_scores_cleanliness`
- `review_scores_checkin`
- `review_scores_communication`
- `review_scores_location`
- `review_scores_value`
- `reviews_per_month`
- `calculated_host_listings_count`

#### Bathroom fallback logic

Bathrooms use a fallback strategy:

1. try `bathrooms`
2. if missing, extract a numeric value from `bathrooms_text`

This helps preserve a usable `bathrooms` field even when the raw feed is inconsistent.

#### Location fallback logic

Neighbourhood fields are standardized with fallback:

- `neighbourhood` = `neighbourhood_cleansed`, else `neighbourhood`
- `neighbourhood_group` = `neighbourhood_group_cleansed`, else `neighbourhood_group`

#### Prices

- raw `price` -> numeric `price` using `clean_money`

### Deduplication Logic

This is the only Silver model with material deduplication logic.

Steps:

1. discard rows where `listing_id` is null
2. partition by `listing_id`
3. rank rows by:
   - `last_scraped desc nulls last`
   - `listing_name`
4. keep only the top-ranked row

Meaning:

- if a listing appears multiple times in Bronze, Silver keeps the latest scraped version
- if `last_scraped` ties, `listing_name` acts as a deterministic tie-breaker

### Important Business Meaning

`silver_listings` is a current-state listing table, not a historical snapshot table.

### Tests Protecting `silver_listings`

- `listing_id` is `not_null`
- `listing_id` is `unique`
- `host_id` is `not_null`
- `price` is positive or null
- `host_response_rate` is between `0` and `1`
- `host_acceptance_rate` is between `0` and `1`
- `availability_365` is between `0` and `365`
- `room_type` is in the accepted Airbnb room-type set
- `latitude` is between `-90` and `90`
- `longitude` is between `-180` and `180`
- `minimum_nights` is positive or null
- `maximum_nights` is positive or null
- `minimum_nights <= maximum_nights`
- `neighbourhood` must exist in `silver_neighbourhoods` when populated

## 3.2 `silver_neighbourhoods`

### Purpose

`silver_neighbourhoods` is the cleaned geography reference table used to validate listing neighbourhood values.

### Input

- `bronze_neighbourhoods`

### Output Grain

- one row per `neighbourhood`

### Cleaning Logic

- clean and trim `neighbourhood`
- clean and trim `neighbourhood_group`

### Deduplication Logic

1. drop rows where `neighbourhood` is null
2. partition by `lower(neighbourhood)`
3. order by `neighbourhood_group nulls last`
4. keep the first row

Meaning:

- duplicate neighbourhood names that differ only by case are collapsed
- one representative `neighbourhood_group` is retained

### Tests Protecting `silver_neighbourhoods`

- `neighbourhood` is `not_null`
- `neighbourhood` is `unique`

## 3.3 `silver_calendar`

### Purpose

`silver_calendar` is the cleaned day-level availability table.

### Input

- `bronze_calendar`

### Output Grain

- one row per `listing_id + calendar_date`

### Cleaning Logic

- `listing_id` cast to `bigint`
- raw `date` cast to `calendar_date`
- `available` cleaned into boolean `is_available`
- `price` cleaned into numeric
- `adjusted_price` cleaned into numeric
- `minimum_nights` cast to integer
- `maximum_nights` cast to integer

### Filtering Logic

Rows are kept only when:

- `listing_id` is not null
- `calendar_date` is not null

### Deduplication

No heuristic deduplication is applied in this model.

The project intentionally relies on the Bronze uniqueness assumption and tests the final Silver grain instead.

### Tests Protecting `silver_calendar`

- `listing_id + calendar_date` is unique
- `listing_id` is `not_null`
- `calendar_date` is `not_null`
- `price` is positive or null
- `adjusted_price` is positive or null
- `minimum_nights <= maximum_nights`
- `listing_id` must exist in `silver_listings`

## 3.4 `silver_reviews`

### Purpose

`silver_reviews` is the cleaned review-level event table.

### Input

- `bronze_reviews`

### Output Grain

- one row per `review_id`

### Cleaning Logic

- raw `id` -> `review_id` as `bigint`
- `listing_id` cast to `bigint`
- raw `date` -> `review_date`
- `reviewer_id` cast to `bigint`
- `reviewer_name` cleaned and trimmed
- `comments` cleaned and trimmed

### Derived Field

- `has_comment` is `true` when `comments` is not null

### Filtering Logic

Rows are kept only when:

- `review_id` is not null
- `listing_id` is not null

### Deduplication

No heuristic deduplication is applied in this model because the current Bronze contract assumes one row per raw review id.

### Tests Protecting `silver_reviews`

- `review_id` is `not_null`
- `review_id` is `unique`
- `listing_id` is `not_null`
- `review_date` is `not_null`
- `listing_id` must exist in `silver_listings`

## 4. Gold Layer

The Gold layer reorganizes Silver data into a star schema.

Current Gold models are split into:

- dimensions: descriptive attributes
- facts: measurable events and snapshots

## 4.1 `dim_listing`

### Purpose

`dim_listing` stores descriptive listing attributes only.

### Input

- `silver_listings`

### Output Grain

- one row per `listing_id`

### Key Logic

- `listing_key = md5(cast(listing_id as varchar))`
- keeps only descriptive listing fields:
  - listing name
  - latitude
  - longitude
  - property type
  - room type
  - accommodates
  - bathrooms
  - bedrooms
  - beds
  - default minimum nights
  - default maximum nights
  - instant bookable

### What Is Intentionally Excluded

These are not stored here because they are fact-like or volatile:

- listing price
- review counts
- review scores
- availability metrics

### Tests

- `listing_key` is `not_null`
- `listing_key` is `unique`
- `listing_id` is `not_null`
- `listing_id` is `unique`

## 4.2 `dim_host`

### Purpose

`dim_host` stores host-level descriptive attributes in current-state form.

### Input

- `silver_listings`

### Output Grain

- one row per `host_id`

### Key Logic

- `host_key = md5(cast(host_id as varchar))`
- rows are ranked by:
  - `last_scraped desc nulls last`
  - `listing_id`
- only the latest row per `host_id` is kept

This means `dim_host` behaves like:

- SCD Type 1
- latest observed host record wins

### Included Attributes

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
- `source_last_scraped_date`

### Tests

- `host_key` is `not_null`
- `host_key` is `unique`
- `host_id` is `not_null`
- `host_id` is `unique`
- `source_last_scraped_date` is `not_null`

## 4.3 `dim_location`

### Purpose

`dim_location` is the geography dimension for Gold facts.

### Input

- `silver_listings`

### Output Grain

- one row per `city + neighbourhood`

### Key Logic

- `city` comes from `env_var('AIRBNB_CITY', 'Bangkok')`
- all distinct non-null listing neighbourhoods are collected
- one additional reserved row is always added:
  - `neighbourhood = 'UNKNOWN'`
- `location_key = md5(city || '||' || neighbourhood)`

### Why `UNKNOWN` Exists

Without an `UNKNOWN` member, any fact row whose parent listing has a null neighbourhood could be lost during the join to location.

The `UNKNOWN` row allows:

- fact row preservation
- referential integrity
- visibility into incomplete source geography

### Tests

- `(city, neighbourhood)` is unique
- `location_key` is `not_null`
- `location_key` is `unique`
- `city` is `not_null`
- `neighbourhood` is `not_null`
- the reserved member `(AIRBNB_CITY, 'UNKNOWN')` must exist

## 4.4 `dim_date`

### Purpose

`dim_date` is a conformed calendar dimension shared across Gold facts.

### Inputs

Date values are collected from:

- `silver_calendar.calendar_date`
- `silver_reviews.review_date`
- `silver_listings.last_scraped`
- `silver_listings.host_since`
- `silver_listings.last_review`

### Output Grain

- one row per distinct date

### Key Logic

- `date_key = YYYYMMDD` as integer
- attributes derived:
  - year
  - quarter
  - month
  - month name
  - day
  - day of week
  - week of year
  - weekend flag

### Tests

- `date_key` is `not_null`
- `date_key` is `unique`
- `date_day` is `not_null`
- `date_day` is `unique`

## 4.5 `fact_listing_current_snapshot`

### Purpose

This is the Gold listing snapshot fact.

It captures the current listing state after Silver deduplication.

### Inputs

- `silver_listings`
- `dim_listing`
- `dim_host`
- `dim_location`
- `dim_date`

### Output Grain

- one row per listing in `silver_listings`

### Key Logic

- `listing_snapshot_key = md5(listing_id || '||' || last_scraped)`
- join to `dim_listing` on `listing_id`
- join to `dim_host` on `host_id`
- join to `dim_location` on:
  - city = configured city
  - `coalesce(listing.neighbourhood, 'UNKNOWN') = location_dim.neighbourhood`
- `snapshot_date_key` derives from `last_scraped`
- `last_review_date_key` derives from `last_review` if present

### Measures / Attributes Stored in the Fact

- listing price snapshot
- availability metrics
- review counts
- review score metrics
- calculated host listings count
- constant additive measure `listing_count = 1`

### Why It Is a Fact, Not a Dimension

These values change over time or behave like measured listing state, so they are treated as snapshot data rather than stable descriptors.

### Tests

- unique grain on `listing_key + snapshot_date_key`
- row count must match `silver_listings`
- unknown-location ratio must remain below threshold
- primary key `listing_snapshot_key` is unique and not null
- all foreign keys point to valid dimensions
- `listing_id` remains traceable and valid
- numeric sanity checks on snapshot price

## 4.6 `fact_availability_daily`

### Purpose

This is the daily listing availability fact.

### Inputs

- `silver_calendar`
- `silver_listings` via a lightweight `listing_lookup`
- `dim_listing`
- `dim_host`
- `dim_location`
- `dim_date`

### Output Grain

- one row per `listing_id + calendar_date`

### Key Logic

- `availability_daily_key = md5(listing_id || '||' || calendar_date)`
- join calendar rows to listing parent data through `listing_lookup`
- join to dimensions:
  - `dim_listing` by `listing_id`
  - `dim_host` by `host_id`
  - `dim_location` by `coalesce(neighbourhood, 'UNKNOWN')`
- `calendar_date_key` derives from `calendar_date`

### Measures / Attributes Stored

- `is_available`
- `calendar_minimum_nights`
- `calendar_maximum_nights`

### Intentional Design Choice

Daily calendar prices are not currently exposed in this fact because the present dataset has null pricing coverage and snapshot listing price is treated as the more reliable pricing source.

### Tests

- unique grain on `listing_key + calendar_date_key`
- row count must match `silver_calendar`
- unknown-location ratio must remain below threshold
- primary key is unique and not null
- all foreign keys point to valid dimensions

## 4.7 `fact_review`

### Purpose

This is the review event fact.

### Inputs

- `silver_reviews`
- `silver_listings` via `listing_lookup`
- `dim_listing`
- `dim_host`
- `dim_location`
- `dim_date`

### Output Grain

- one row per `review_id`

### Key Logic

- `review_key = md5(review_id)`
- parent listing lookup supplies:
  - `host_id`
  - `neighbourhood`
- join to dimensions:
  - `dim_listing` by `listing_id`
  - `dim_host` by `host_id`
  - `dim_location` by `coalesce(neighbourhood, 'UNKNOWN')`
- `review_date_key` derives from `review_date`

### Measures / Attributes Stored

- `reviewer_id`
- `has_comment`
- `review_count = 1`

### Intentional Exclusion

Raw review comments are excluded from Gold because:

- they are long free text
- they do not fit well in the current star schema
- text analytics can be modeled separately later

### Tests

- unique grain on `review_id`
- row count must match `silver_reviews`
- unknown-location ratio must remain below threshold
- primary key is unique and not null
- all foreign keys point to valid dimensions

## 5. Current Quality Controls

The current custom and built-in dbt tests protect the warehouse in four main ways.

### Contract and Grain Protection

- source columns must exist through `source_column()`
- Silver primary grains are enforced
- Gold fact grains are enforced

### Referential Integrity

- Silver calendar and reviews must point to valid listings
- Gold facts must point to valid dimensions

### Data Sanity Checks

- prices must be positive when present
- percentages must stay in `[0, 1]`
- latitudes and longitudes must stay in valid ranges
- `minimum_nights <= maximum_nights`

### Preservation and Monitoring Checks

- `dim_location` must contain the reserved `UNKNOWN` member
- each Gold fact row count must match its Silver parent input
- each Gold fact must keep the ratio of `UNKNOWN` location usage below the configured threshold

Current default threshold:

- `GOLD_UNKNOWN_LOCATION_MAX_RATIO = 0.01` if not overridden

## 6. Important Design Decisions to Remember

These are the main design choices behind the current implementation:

### Silver keeps business keys, Gold adds surrogate keys

- Silver is easier to debug and compare against raw source tables
- Gold is easier to use in BI, metrics, and star-schema joins

### `silver_listings` is current-state, not historical

- only one row per listing is retained
- latest `last_scraped` wins

### `dim_host` is also current-state

- the latest host attributes overwrite older observed values

### Gold preserves fact grain even when geography is incomplete

- missing listing neighbourhoods do not drop rows anymore
- they are mapped to `UNKNOWN`

### Gold facts keep selected natural identifiers

- this helps debugging and traceability
- but analytical joins should still prefer surrogate keys

## 7. How to Review This Layer Quickly

If you want to check whether the layer is still healthy after a source refresh, this is the fastest review order:

1. check Bronze source assumptions first
2. check whether `silver_listings` still keeps one row per listing
3. check whether `silver_calendar` and `silver_reviews` still link to valid listings
4. check whether Gold facts still preserve Silver row counts
5. check whether any meaningful share of rows is now mapped to `UNKNOWN`
6. check whether all dbt tests still pass on MotherDuck

## 8. Practical Summary

In plain language, the current pipeline does this:

- clean and standardize raw Airbnb tables in Silver
- reduce listings to one latest row per listing
- keep calendar and review data at their natural event grain
- reshape the cleaned data into a Gold star schema
- preserve all valid facts even when location data is incomplete
- guard the result with tests for uniqueness, relationships, value ranges, row preservation, and `UNKNOWN` monitoring

This makes the current Silver and Gold layers suitable for:

- dashboarding
- dimensional analysis
- downstream ML feature building
- LLM-generated business explanations based on structured warehouse outputs
