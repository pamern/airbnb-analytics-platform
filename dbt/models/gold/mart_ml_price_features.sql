select
    dl.listing_id,
    fls.price,
    loc.neighbourhood,
    dl.room_type,
    dl.property_type,
    dl.accommodates,
    dl.bathrooms,
    dl.bedrooms,
    dl.beds,
    fls.availability_365,
    fls.review_scores_rating,
    fls.reviews_per_month,
    dh.host_is_superhost,
    dh.host_response_rate,
    dl.instant_bookable
from {{ ref('dim_listing') }} as dl
inner join {{ ref('fact_listing_snapshot') }} as fls
    on dl.listing_key = fls.listing_key
left join {{ ref('dim_host') }} as dh
    on fls.host_key = dh.host_key
left join {{ ref('dim_location') }} as loc
    on dl.location_key = loc.location_key
where fls.price is not null
  and fls.price > 0
