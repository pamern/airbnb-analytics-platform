{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

with listing_base as (
    select
        md5(cast(listing_id as varchar)) as listing_key,
        listing_id,
        listing_name,
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bedrooms,
        beds,
        minimum_nights as listing_default_minimum_nights,
        maximum_nights as listing_default_maximum_nights,
        instant_bookable,
        host_id,
        neighbourhood
    from {{ ref('silver_listings') }}
),

listing_with_keys as (
    select
        listing.listing_key,
        listing.listing_id,
        listing.listing_name,
        listing.property_type,
        listing.room_type,
        listing.accommodates,
        listing.bathrooms,
        listing.bedrooms,
        listing.beds,
        listing.listing_default_minimum_nights,
        listing.listing_default_maximum_nights,
        listing.instant_bookable,
        host.host_key,
        location.location_key
    from listing_base as listing
    left join {{ ref('dim_host') }} as host
        on listing.host_id = host.host_id
    left join {{ ref('dim_location') }} as location
        on location.city = '{{ city_name }}'
       and listing.neighbourhood = location.neighbourhood
)

select *
from listing_with_keys
