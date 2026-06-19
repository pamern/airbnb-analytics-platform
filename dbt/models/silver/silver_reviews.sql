{% set reviews_source = source('airbnb_bronze', 'bronze_reviews') %}

with source_data as (
    select *
    from {{ reviews_source }} as src
),

cleaned as (
    select
        try_cast({{ source_column(reviews_source, 'id') }} as bigint) as review_id,
        try_cast({{ source_column(reviews_source, 'listing_id') }} as bigint) as listing_id,
        try_cast({{ source_column(reviews_source, 'date') }} as date) as review_date,
        try_cast({{ source_column(reviews_source, 'reviewer_id') }} as bigint) as reviewer_id,
        {{ clean_text(source_column(reviews_source, 'reviewer_name')) }} as reviewer_name,
        {{ clean_text(source_column(reviews_source, 'comments')) }} as comments
    from source_data as src
)

select
    *,
    comments is not null as has_comment
from cleaned
where review_id is not null
  and listing_id is not null
