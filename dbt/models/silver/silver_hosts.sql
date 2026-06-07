with listings as (
    select *
    from {{ ref('silver_listings_cleaned') }}
    where host_id is not null
)

select
    host_id,
    max(host_name) as host_name,
    min(host_since) as host_since,
    max(host_location) as host_location,
    max(host_response_time) as host_response_time,
    max(host_response_rate) as host_response_rate,
    max(host_acceptance_rate) as host_acceptance_rate,
    bool_or(coalesce(host_is_superhost, false)) as host_is_superhost,
    max(host_listings_count) as host_listings_count,
    max(host_total_listings_count) as host_total_listings_count,
    bool_or(coalesce(host_identity_verified, false)) as host_identity_verified,
    count(distinct listing_id) as observed_listing_count
from listings
group by host_id
