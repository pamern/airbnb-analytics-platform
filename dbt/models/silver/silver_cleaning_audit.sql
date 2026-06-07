with audit_rows as (
    select
        'silver_listings_cleaned' as model_name,
        count(*) as row_count,
        count(*) - count(distinct listing_id) as duplicate_key_count,
        sum(case when listing_id is null then 1 else 0 end) as null_key_count,
        sum(case when price is not null and price < 0 then 1 else 0 end) as invalid_metric_count
    from {{ ref('silver_listings_cleaned') }}

    union all

    select
        'silver_hosts' as model_name,
        count(*) as row_count,
        count(*) - count(distinct host_id) as duplicate_key_count,
        sum(case when host_id is null then 1 else 0 end) as null_key_count,
        0 as invalid_metric_count
    from {{ ref('silver_hosts') }}

    union all

    select
        'silver_locations' as model_name,
        count(*) as row_count,
        count(*) - count(distinct location_key) as duplicate_key_count,
        sum(case when location_key is null then 1 else 0 end) as null_key_count,
        0 as invalid_metric_count
    from {{ ref('silver_locations') }}

    union all

    select
        'silver_calendar' as model_name,
        count(*) as row_count,
        count(*) - count(distinct cast(listing_id as varchar) || '|' || cast(calendar_date as varchar)) as duplicate_key_count,
        sum(case when listing_id is null or calendar_date is null then 1 else 0 end) as null_key_count,
        sum(case when price is not null and price < 0 then 1 else 0 end) as invalid_metric_count
    from {{ ref('silver_calendar') }}

    union all

    select
        'silver_reviews' as model_name,
        count(*) as row_count,
        count(*) - count(distinct review_id) as duplicate_key_count,
        sum(case when review_id is null or listing_id is null then 1 else 0 end) as null_key_count,
        0 as invalid_metric_count
    from {{ ref('silver_reviews') }}
)

select
    current_timestamp as audited_at,
    model_name,
    row_count,
    duplicate_key_count,
    null_key_count,
    invalid_metric_count
from audit_rows
