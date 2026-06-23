# Dashboard Mart Optimization Plan

## Goal

Speed up the Streamlit dashboard by moving expensive joins and repeated derived-column logic into new dbt Gold mart tables.

Important rule:

- Do not change the current data processing logic.
- Do not change KPI definitions, thresholds, labels, or business rules.
- Only move the existing logic from Streamlit query-time processing into dbt Gold mart models.
- Streamlit should read prepared mart tables, then only filter, sort, and render charts.

## Current Problem

The Dashboard page currently loads data from Gold fact and dimension tables, then performs joins, derived-column creation, and some aggregation during Streamlit rendering.

This is slow because the app repeatedly queries and joins:

- `gold.fact_listing_current_snapshot`
- `gold.fact_availability_daily`
- `gold.fact_review`
- `gold.dim_listing`
- `gold.dim_host`
- `gold.dim_location`
- `gold.dim_date`

The heaviest part is the Location & Availability tab because it aggregates daily calendar rows into listing-month rows while the dashboard is loading.

## Proposed Gold Mart Tables

Create 3 new dbt Gold models:

```text
dbt/models/gold/mart_dashboard_listing_snapshot.sql
dbt/models/gold/mart_dashboard_listing_monthly_availability.sql
dbt/models/gold/mart_dashboard_listing_review_recency.sql
```

These should materialize as tables in the `gold` schema:

```text
gold.mart_dashboard_listing_snapshot
gold.mart_dashboard_listing_monthly_availability
gold.mart_dashboard_listing_review_recency
```

## Implementation Files

Code changes should be made in these files:

```text
dbt/models/gold/mart_dashboard_listing_snapshot.sql
dbt/models/gold/mart_dashboard_listing_monthly_availability.sql
dbt/models/gold/mart_dashboard_listing_review_recency.sql
dbt/models/gold/schema.yml
app/data_access.py
app/components/host_review_quality.py
```

The first 3 files create the mart tables. `schema.yml` documents and tests them. `app/data_access.py` switches Streamlit reads from joined fact/dim queries to mart queries. `host_review_quality.py` only needs a small change so it uses listing-level review recency instead of grouping full review events.

## MotherDuck Upload / Materialization

No separate upload script is needed for these mart tables.

Because these are dbt Gold models, they are created directly in MotherDuck when dbt runs with the MotherDuck profile:

```powershell
uv run dbt build --project-dir dbt --profiles-dir dbt
```

Expected result:

```text
gold.mart_dashboard_listing_snapshot
gold.mart_dashboard_listing_monthly_availability
gold.mart_dashboard_listing_review_recency
```

Important:

- `MOTHERDUCK_TOKEN` must be set in `.env`.
- `MOTHERDUCK_DATABASE` should point to the target database, currently `airbnb_analytics`.
- The dbt profile path uses `md:` so dbt materializes tables directly in MotherDuck.
- After dbt build succeeds, Streamlit can query the mart tables from MotherDuck.

## 1. `gold.mart_dashboard_listing_snapshot`

Grain:

```text
1 row / listing
```

Used by:

- Market Overview
- Pricing & Performance
- Most of Host & Review Quality

Source tables:

```text
gold.fact_listing_current_snapshot
gold.dim_listing
gold.dim_host
gold.dim_location
```

Columns:

```text
listing_id
listing_name
host_id
host_name
neighbourhood
room_type
property_type
accommodates
latitude
longitude

price
price_per_person

availability_30
availability_60
availability_90
availability_365

estimated_occupancy_l365d
estimated_occupancy_rate_l365d
estimated_revenue_l365d

number_of_reviews
number_of_reviews_l30d
number_of_reviews_ltm
number_of_reviews_ly
reviews_per_month

review_scores_rating
review_scores_accuracy
review_scores_cleanliness
review_scores_checkin
review_scores_communication
review_scores_location
review_scores_value

host_response_rate
host_acceptance_rate
host_is_superhost
host_identity_verified
host_listings_count
host_total_listings_count
host_size_group

is_reliable_review
review_quality_band
```

Processing rules to keep unchanged:

```text
price = listing_snapshot_price
price_per_person = price / accommodates, using the same valid-capacity behavior as the current dashboard
estimated_occupancy_rate_l365d = estimated_occupancy_l365d / 365.0, with the same valid range handling
is_reliable_review = review_scores_rating is not null and number_of_reviews >= 5
host_size_group = same bucket logic currently used in Host & Review Quality
review_quality_band = same band logic currently used in Host & Review Quality
```

Do not aggregate this mart above listing grain. The dashboard still needs listing-level rows for filtering, maps, scatter plots, and watchlists.

## 2. `gold.mart_dashboard_listing_monthly_availability`

Grain:

```text
1 row / listing / calendar_month
```

Used by:

- Location & Availability

Source tables:

```text
gold.fact_availability_daily
gold.dim_date
gold.dim_listing
gold.dim_location
gold.fact_listing_current_snapshot
```

Columns:

```text
listing_id
calendar_month
neighbourhood
room_type
latitude
longitude
price

available_days
observed_days
availability_share
median_calendar_minimum_nights

calendar_start_date
calendar_end_date
```

Processing rules to keep unchanged:

```text
calendar_month = date_trunc('month', date_day)
available_days = sum(case when is_available then 1 else 0 end)
observed_days = count(*)
availability_share = available_days / observed_days
median_calendar_minimum_nights = median positive calendar_minimum_nights values
price = current listing snapshot price
calendar_start_date = minimum available calendar date in the source
calendar_end_date = maximum available calendar date in the source
```

This mart replaces the expensive runtime aggregation from daily calendar rows to listing-month rows.

Do not aggregate this mart directly to neighbourhood-month only. The dashboard still needs listing-month grain so filters can remain dynamic.

## 3. `gold.mart_dashboard_listing_review_recency`

Grain:

```text
1 row / listing
```

Used by:

- Review Watchlist in Host & Review Quality

Source tables:

```text
gold.fact_review
gold.dim_date
```

Columns:

```text
listing_id
last_review_date
review_event_count
comment_count
has_any_comment
global_latest_review_date
days_since_last_review
```

Processing rules to keep unchanged:

```text
last_review_date = max(review_date)
review_event_count = count(review_id)
comment_count = count or sum of review rows with has_comment = true, matching current semantics
has_any_comment = comment_count > 0
global_latest_review_date = max(review_date) over the full review dataset
days_since_last_review = global_latest_review_date - last_review_date
```

The current dashboard mainly uses review events to derive listing-level last review date. This mart should avoid loading all review events into Streamlit.

## Streamlit Read Pattern After Mart Creation

Streamlit should read:

```sql
select * from gold.mart_dashboard_listing_snapshot;
select * from gold.mart_dashboard_listing_monthly_availability;
select * from gold.mart_dashboard_listing_review_recency;
```

Then Streamlit should only:

- apply user-selected filters
- calculate lightweight filtered medians/counts/ranks
- sort rows
- render charts and tables

Streamlit should no longer:

- join fact and dimension tables for dashboard pages
- aggregate daily calendar rows into monthly rows
- load full review event rows just to compute `last_review_date`

## Validation Rules

The new mart-based dashboard should match the current dashboard outputs under the same filters.

Before replacing the dashboard queries, compare:

- listing counts
- host counts
- median price
- price coverage
- occupancy coverage
- reliable review coverage
- monthly availability share
- listing-month row counts
- last review date by listing

Any mismatch should be treated as a migration bug unless intentionally approved.
