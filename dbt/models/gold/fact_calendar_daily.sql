with calendar as (
    select *
    from {{ ref('silver_calendar') }}
),

listings as (
    select
        listing_id,
        neighbourhood
    from {{ ref('silver_listings_cleaned') }}
),

locations as (
    select
        location_key,
        neighbourhood
    from {{ ref('silver_locations') }}
)

select
    md5(cast(c.listing_id as varchar)) as listing_key,
    coalesce(
        loc.location_key,
        md5(lower(coalesce(l.neighbourhood, 'unknown')))
    ) as location_key,
    cast(strftime(c.calendar_date, '%Y%m%d') as integer) as date_key,
    c.is_available,
    c.price,
    c.adjusted_price,
    c.minimum_nights,
    c.maximum_nights
from calendar as c
left join listings as l
    on c.listing_id = l.listing_id
left join locations as loc
    on lower(l.neighbourhood) = lower(loc.neighbourhood)
where c.listing_id is not null
  and c.calendar_date is not null
