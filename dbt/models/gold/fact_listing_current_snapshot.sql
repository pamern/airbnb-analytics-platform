{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

with listing_snapshot as (
    select
        md5(cast(listing.listing_id as varchar) || '||' || cast(listing.last_scraped as varchar)) as listing_snapshot_key,
        listing_dim.listing_key,
        host_dim.host_key,
        location_dim.location_key,
        cast(strftime(listing.last_scraped, '%Y%m%d') as integer) as snapshot_date_key,
        case
            when listing.last_review is not null then cast(strftime(listing.last_review, '%Y%m%d') as integer)
            else null
        end as last_review_date_key,
        listing.listing_id,
        listing.price as listing_snapshot_price,
        listing.availability_30,
        listing.availability_60,
        listing.availability_90,
        listing.availability_365,
        listing.number_of_reviews,
        listing.number_of_reviews_ltm,
        listing.reviews_per_month,
        listing.review_scores_rating,
        listing.review_scores_accuracy,
        listing.review_scores_cleanliness,
        listing.review_scores_checkin,
        listing.review_scores_communication,
        listing.review_scores_location,
        listing.review_scores_value,
        listing.calculated_host_listings_count,
        1 as listing_count
    from {{ ref('silver_listings') }} as listing
    inner join {{ ref('dim_listing') }} as listing_dim
        on listing.listing_id = listing_dim.listing_id
    inner join {{ ref('dim_host') }} as host_dim
        on listing.host_id = host_dim.host_id
    inner join {{ ref('dim_location') }} as location_dim
        on location_dim.city = '{{ city_name }}'
       and coalesce(listing.neighbourhood, 'UNKNOWN') = location_dim.neighbourhood
)

select *
from listing_snapshot
