select
    md5(cast(listing_id as varchar)) as listing_key,
    listing_id,
    listing_name,
    latitude,
    longitude,
    property_type,
    room_type,
    accommodates,
    bathrooms,
    bedrooms,
    beds,
    minimum_nights as listing_default_minimum_nights,
    maximum_nights as listing_default_maximum_nights,
    instant_bookable
from {{ ref('silver_listings') }}
