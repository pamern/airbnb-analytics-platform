with reviews as (
    select *
    from {{ ref('silver_reviews') }}
),

listings as (
    select
        listing_id,
        host_id,
        neighbourhood
    from {{ ref('silver_listings_cleaned') }}
),

locations as (
    select
        location_key,
        neighbourhood
    from {{ ref('silver_locations') }}
)

select
    md5(cast(r.review_id as varchar)) as review_key,
    r.review_id,
    md5(cast(r.listing_id as varchar)) as listing_key,
    md5(cast(l.host_id as varchar)) as host_key,
    coalesce(
        loc.location_key,
        md5(lower(coalesce(l.neighbourhood, 'unknown')))
    ) as location_key,
    cast(strftime(r.review_date, '%Y%m%d') as integer) as date_key,
    r.reviewer_id,
    r.reviewer_name,
    r.has_comment,
    length(r.comments) as comment_length,
    r.comments
from reviews as r
left join listings as l
    on r.listing_id = l.listing_id
left join locations as loc
    on lower(l.neighbourhood) = lower(loc.neighbourhood)
where r.review_id is not null
