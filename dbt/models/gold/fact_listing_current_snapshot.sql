with listing_snapshot as (
    select
        md5(cast(listing.listing_id as varchar) || '||' || cast(listing.last_scraped as varchar)) as listing_snapshot_key,
        dim.listing_key,
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
    inner join {{ ref('dim_listing') }} as dim
        on listing.listing_id = dim.listing_id
)

select *
from listing_snapshot
