with review_fact as (
    select
        md5(cast(review.review_id as varchar)) as review_key,
        dim.listing_key,
        cast(strftime(review.review_date, '%Y%m%d') as integer) as review_date_key,
        review.review_id,
        review.listing_id,
        review.reviewer_id,
        review.has_comment,
        1 as review_count
    from {{ ref('silver_reviews') }} as review
    inner join {{ ref('dim_listing') }} as dim
        on review.listing_id = dim.listing_id
)

select *
from review_fact
