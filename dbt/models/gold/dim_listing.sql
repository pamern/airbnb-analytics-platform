with listings as (
    select *
    from {{ ref('silver_listings_cleaned') }}
),

locations as (
    select
        location_key,
        neighbourhood
    from {{ ref('silver_locations') }}
)

select
    md5(cast(l.listing_id as varchar)) as listing_key,
    l.listing_id,
    md5(cast(l.host_id as varchar)) as host_key,
    coalesce(
        loc.location_key,
        md5(lower(coalesce(l.neighbourhood, 'unknown')))
    ) as location_key,
    l.listing_name,
    l.property_type,
    l.room_type,
    l.accommodates,
    l.bathrooms,
    l.bedrooms,
    l.beds,
    l.amenities,
    l.instant_bookable,
    l.latitude,
    l.longitude
from listings as l
left join locations as loc
    on lower(l.neighbourhood) = lower(loc.neighbourhood)
where l.listing_id is not null
