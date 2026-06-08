select
    md5(cast(host_id as varchar)) as host_key,
    host_id,
    host_name,
    host_since,
    host_location,
    host_is_superhost,
    host_identity_verified,
    host_response_time,
    host_response_rate,
    host_acceptance_rate,
    observed_listing_count
from {{ ref('silver_hosts') }}
where host_id is not null
