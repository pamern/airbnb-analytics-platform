{{ config(materialized='table', schema='gold') }}

with review_events as (
    select
        review_fact.listing_id,
        date_dim.date_day as review_date,
        review_fact.review_id,
        coalesce(review_fact.has_comment, false) as has_comment
    from {{ ref('fact_review') }} as review_fact
    inner join {{ ref('dim_date') }} as date_dim
        on review_fact.review_date_key = date_dim.date_key
),

global_reference as (
    select max(review_date) as global_latest_review_date
    from review_events
)

select
    review_events.listing_id,
    max(review_events.review_date) as last_review_date,
    count(review_events.review_id) as review_event_count,
    sum(case when review_events.has_comment then 1 else 0 end) as comment_count,
    sum(case when review_events.has_comment then 1 else 0 end) > 0 as has_any_comment,
    global_reference.global_latest_review_date,
    date_diff(
        'day',
        max(review_events.review_date),
        global_reference.global_latest_review_date
    ) as days_since_last_review
from review_events
cross join global_reference
group by 1, 6
