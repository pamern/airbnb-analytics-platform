{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

with listing_lookup as (
    select
        listing_id,
        host_id,
        neighbourhood
    from {{ ref('silver_listings') }}
),

review_fact as (
    select
        md5(cast(review.review_id as varchar)) as review_key,
        listing_dim.listing_key,
        host_dim.host_key,
        location_dim.location_key,
        cast(strftime(review.review_date, '%Y%m%d') as integer) as review_date_key,
        review.review_id,
        review.listing_id,
        review.reviewer_id,
        review.has_comment,
        1 as review_count
    from {{ ref('silver_reviews') }} as review
    inner join listing_lookup as listing
        on review.listing_id = listing.listing_id
    inner join {{ ref('dim_listing') }} as listing_dim
        on review.listing_id = listing_dim.listing_id
    inner join {{ ref('dim_host') }} as host_dim
        on listing.host_id = host_dim.host_id
    inner join {{ ref('dim_location') }} as location_dim
        on location_dim.city = '{{ city_name }}'
       and listing.neighbourhood = location_dim.neighbourhood
)

select *
from review_fact
