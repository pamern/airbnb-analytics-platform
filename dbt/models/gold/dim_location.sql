{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

with known_locations as (
    select distinct
        neighbourhood
    from {{ ref('silver_listings') }}
    where neighbourhood is not null
),

all_locations as (
    select neighbourhood
    from known_locations

    union all

    select 'UNKNOWN' as neighbourhood
)

select
    md5('{{ city_name }}' || '||' || neighbourhood) as location_key,
    '{{ city_name }}' as city,
    neighbourhood
from all_locations
