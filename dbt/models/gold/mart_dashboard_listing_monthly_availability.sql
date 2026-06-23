{{ config(materialized='table', schema='gold') }}

with calendar_bounds as (
    select
        min(date_dim.date_day) as calendar_start_date,
        max(date_dim.date_day) as calendar_end_date
    from {{ ref('fact_availability_daily') }} as fact
    inner join {{ ref('dim_date') }} as date_dim
        on fact.calendar_date_key = date_dim.date_key
),

listing_monthly as (
    select
        fact.listing_id,
        fact.listing_key,
        date_trunc('month', date_dim.date_day) as calendar_month,
        coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
        coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
        listing_dim.latitude,
        listing_dim.longitude,
        snapshot_fact.listing_snapshot_price as price,
        sum(case when fact.is_available then 1 else 0 end) as available_days,
        count(*) as observed_days,
        median(
            case
                when fact.calendar_minimum_nights > 0 then fact.calendar_minimum_nights
            end
        ) as median_calendar_minimum_nights
    from {{ ref('fact_availability_daily') }} as fact
    inner join {{ ref('dim_date') }} as date_dim
        on fact.calendar_date_key = date_dim.date_key
    inner join {{ ref('dim_listing') }} as listing_dim
        on fact.listing_key = listing_dim.listing_key
    left join {{ ref('dim_location') }} as location_dim
        on fact.location_key = location_dim.location_key
    left join {{ ref('fact_listing_current_snapshot') }} as snapshot_fact
        on fact.listing_id = snapshot_fact.listing_id
    group by 1, 2, 3, 4, 5, 6, 7, 8
)

select
    listing_monthly.listing_id,
    listing_monthly.listing_key,
    listing_monthly.calendar_month,
    listing_monthly.neighbourhood,
    listing_monthly.room_type,
    listing_monthly.latitude,
    listing_monthly.longitude,
    listing_monthly.price,
    listing_monthly.available_days,
    listing_monthly.observed_days,
    listing_monthly.available_days / nullif(listing_monthly.observed_days, 0) as availability_share,
    listing_monthly.median_calendar_minimum_nights,
    calendar_bounds.calendar_start_date,
    calendar_bounds.calendar_end_date
from listing_monthly
cross join calendar_bounds
