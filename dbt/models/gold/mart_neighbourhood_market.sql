with listing_metrics as (
    select
        dl.location_key,
        dl.room_type,
        dl.listing_id,
        dh.host_id,
        fls.price,
        fls.availability_365,
        fls.reviews_per_month,
        fls.review_scores_rating
    from {{ ref('fact_listing_snapshot') }} as fls
    inner join {{ ref('dim_listing') }} as dl
        on fls.listing_key = dl.listing_key
    left join {{ ref('dim_host') }} as dh
        on fls.host_key = dh.host_key
),

aggregated as (
    select
        location_key,
        room_type,
        count(distinct listing_id) as listing_count,
        count(distinct host_id) as host_count,
        avg(price) as avg_price,
        median(price) as median_price,
        min(price) as min_price,
        max(price) as max_price,
        avg(review_scores_rating) as avg_rating,
        avg(availability_365) as avg_availability_365,
        avg(reviews_per_month) as avg_reviews_per_month
    from listing_metrics
    group by location_key, room_type
)

select
    a.location_key,
    loc.city,
    loc.neighbourhood,
    loc.neighbourhood_group,
    a.room_type,
    a.listing_count,
    a.host_count,
    a.avg_price,
    a.median_price,
    a.min_price,
    a.max_price,
    a.avg_rating,
    a.avg_availability_365,
    a.avg_reviews_per_month,
    loc.avg_latitude,
    loc.avg_longitude
from aggregated as a
left join {{ ref('dim_location') }} as loc
    on a.location_key = loc.location_key
