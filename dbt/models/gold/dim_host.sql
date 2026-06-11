with ranked_hosts as (
    select
        md5(cast(host_id as varchar)) as host_key,
        host_id,
        host_name,
        host_since,
        host_location as host_reported_location,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        host_is_superhost,
        host_identity_verified,
        host_listings_count,
        host_total_listings_count,
        last_scraped as source_last_scraped_date,
        row_number() over (
            partition by host_id
            order by last_scraped desc nulls last, listing_id
        ) as row_num
    from {{ ref('silver_listings') }}
    where host_id is not null
)

select
    host_key,
    host_id,
    host_name,
    host_since,
    host_reported_location,
    host_response_time,
    host_response_rate,
    host_acceptance_rate,
    host_is_superhost,
    host_identity_verified,
    host_listings_count,
    host_total_listings_count,
    source_last_scraped_date
from ranked_hosts
where row_num = 1
