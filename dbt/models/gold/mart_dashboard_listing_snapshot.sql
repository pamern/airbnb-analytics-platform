{{ config(materialized='table', schema='gold') }}

with snapshot as (
    select
        fact.listing_id,
        listing_dim.listing_name,
        host_dim.host_id,
        host_dim.host_name,
        coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
        coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
        coalesce(listing_dim.property_type, 'UNKNOWN') as property_type,
        listing_dim.accommodates,
        listing_dim.latitude,
        listing_dim.longitude,
        fact.listing_snapshot_price as price,
        fact.availability_30,
        fact.availability_60,
        fact.availability_90,
        fact.availability_365,
        fact.estimated_occupancy_l365d,
        fact.estimated_revenue_l365d,
        fact.number_of_reviews,
        fact.number_of_reviews_l30d,
        fact.number_of_reviews_ltm,
        fact.number_of_reviews_ly,
        fact.reviews_per_month,
        fact.review_scores_rating,
        fact.review_scores_accuracy,
        fact.review_scores_cleanliness,
        fact.review_scores_checkin,
        fact.review_scores_communication,
        fact.review_scores_location,
        fact.review_scores_value,
        host_dim.host_response_rate,
        host_dim.host_acceptance_rate,
        host_dim.host_is_superhost,
        host_dim.host_identity_verified,
        host_dim.host_listings_count,
        host_dim.host_total_listings_count
    from {{ ref('fact_listing_current_snapshot') }} as fact
    inner join {{ ref('dim_listing') }} as listing_dim
        on fact.listing_key = listing_dim.listing_key
    left join {{ ref('dim_host') }} as host_dim
        on fact.host_key = host_dim.host_key
    left join {{ ref('dim_location') }} as location_dim
        on fact.location_key = location_dim.location_key
)

select
    *,
    price / nullif(case when accommodates > 0 then accommodates end, 0) as price_per_person,
    case
        when estimated_occupancy_l365d between 0 and 365
            then estimated_occupancy_l365d / 365.0
    end as estimated_occupancy_rate_l365d,
    case
        when host_total_listings_count is null then 'Unknown'
        when host_total_listings_count <= 1 then 'Solo'
        when host_total_listings_count <= 5 then 'Small'
        when host_total_listings_count <= 20 then 'Medium'
        else 'Large'
    end as host_size_group,
    review_scores_rating is not null
        and coalesce(number_of_reviews, 0) >= 5 as is_reliable_review,
    case
        when coalesce(number_of_reviews, 0) < 5 or review_scores_rating is null
            then 'Insufficient Evidence'
        when review_scores_rating < 4.0 then 'Low Rating'
        when review_scores_rating < 4.5 then 'Moderate'
        when review_scores_rating < 4.8 then 'Good'
        else 'Excellent'
    end as review_quality_band
from snapshot
