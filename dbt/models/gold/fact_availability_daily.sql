{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

with listing_lookup as (
    select
        listing_id,
        host_id,
        neighbourhood
    from {{ ref('silver_listings') }}
),

calendar_fact as (
    select
        md5(cast(calendar.listing_id as varchar) || '||' || cast(calendar.calendar_date as varchar)) as availability_daily_key,
        listing_dim.listing_key,
        host_dim.host_key,
        location_dim.location_key,
        cast(strftime(calendar.calendar_date, '%Y%m%d') as integer) as calendar_date_key,
        calendar.listing_id,
        calendar.is_available,
        calendar.minimum_nights as calendar_minimum_nights,
        calendar.maximum_nights as calendar_maximum_nights
    from {{ ref('silver_calendar') }} as calendar
    inner join listing_lookup as listing
        on calendar.listing_id = listing.listing_id
    inner join {{ ref('dim_listing') }} as listing_dim
        on calendar.listing_id = listing_dim.listing_id
    inner join {{ ref('dim_host') }} as host_dim
        on listing.host_id = host_dim.host_id
    inner join {{ ref('dim_location') }} as location_dim
        on location_dim.city = '{{ city_name }}'
       and listing.neighbourhood = location_dim.neighbourhood
)

select *
from calendar_fact
