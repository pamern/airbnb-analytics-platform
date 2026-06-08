with host_listing_metrics as (
    select
        dh.host_key,
        dh.host_id,
        dh.host_name,
        dh.host_is_superhost,
        dh.host_response_rate,
        dh.host_acceptance_rate,
        dh.observed_listing_count,
        dl.listing_id,
        fls.price,
        fls.review_scores_rating,
        fls.reviews_per_month
    from {{ ref('dim_host') }} as dh
    left join {{ ref('fact_listing_snapshot') }} as fls
        on dh.host_key = fls.host_key
    left join {{ ref('dim_listing') }} as dl
        on fls.listing_key = dl.listing_key
)

select
    host_key,
    host_id,
    host_name,
    host_is_superhost,
    observed_listing_count,
    count(distinct listing_id) as listing_count,
    avg(price) as avg_price,
    avg(review_scores_rating) as avg_rating,
    avg(reviews_per_month) as avg_reviews_per_month,
    max(host_response_rate) as avg_response_rate,
    max(host_acceptance_rate) as avg_acceptance_rate
from host_listing_metrics
group by
    host_key,
    host_id,
    host_name,
    host_is_superhost,
    observed_listing_count
