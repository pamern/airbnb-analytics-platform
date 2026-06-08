select
    location_key,
    city,
    neighbourhood,
    neighbourhood_group,
    avg_latitude,
    avg_longitude,
    listing_count
from {{ ref('silver_locations') }}
where location_key is not null
