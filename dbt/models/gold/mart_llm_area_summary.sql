with market as (
    select *
    from {{ ref('mart_neighbourhood_market') }}
),

review_samples as (
    select
        dl.location_key,
        dl.room_type,
        string_agg(left(fr.comments, 240), ' || ' order by fr.date_key desc) as review_comment_sample
    from {{ ref('fact_review') }} as fr
    inner join {{ ref('dim_listing') }} as dl
        on fr.listing_key = dl.listing_key
    where fr.comments is not null
    group by dl.location_key, dl.room_type
)

select
    m.location_key,
    m.neighbourhood,
    m.room_type,
    m.listing_count,
    m.avg_price,
    m.median_price,
    m.avg_rating,
    m.avg_availability_365,
    m.avg_reviews_per_month,
    rs.review_comment_sample,
    case
        when m.avg_price > m.median_price * 1.2 then 'Average price is above the median, suggesting premium outliers in this segment.'
        when m.avg_availability_365 > 240 then 'High availability may indicate softer demand or room for pricing adjustments.'
        when m.avg_reviews_per_month > 2 then 'Review velocity suggests relatively active guest demand.'
        else 'Market indicators are balanced for this neighbourhood and room type.'
    end as pricing_note
from market as m
left join review_samples as rs
    on m.location_key = rs.location_key
    and m.room_type = rs.room_type
