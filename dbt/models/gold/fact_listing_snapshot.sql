with listings as (
    select *
    from {{ ref('silver_listings_cleaned') }}
),

locations as (
    select
        location_key,
        neighbourhood
    from {{ ref('silver_locations') }}
)

select
    md5(cast(l.listing_id as varchar)) as listing_key,
    md5(cast(l.host_id as varchar)) as host_key,
    coalesce(
        loc.location_key,
        md5(lower(coalesce(l.neighbourhood, 'unknown')))
    ) as location_key,
    case
        when l.last_scraped is not null
            then cast(strftime(l.last_scraped, '%Y%m%d') as integer)
    end as date_key,
    l.price,
    l.availability_30,
    l.availability_60,
    l.availability_90,
    l.availability_365,
    l.number_of_reviews,
    l.number_of_reviews_ltm,
    l.reviews_per_month,
    l.review_scores_rating,
    l.review_scores_accuracy,
    l.review_scores_cleanliness,
    l.review_scores_checkin,
    l.review_scores_communication,
    l.review_scores_location,
    l.review_scores_value
from listings as l
left join locations as loc
    on lower(l.neighbourhood) = lower(loc.neighbourhood)
where l.listing_id is not null
