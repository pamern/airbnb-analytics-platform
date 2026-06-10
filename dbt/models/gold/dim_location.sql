{% set city_name = env_var('AIRBNB_CITY', 'Bangkok') %}

select
    md5('{{ city_name }}' || '||' || coalesce(neighbourhood, 'UNKNOWN')) as location_key,
    '{{ city_name }}' as city,
    neighbourhood,
    avg(latitude) as estimated_centroid_latitude,
    avg(longitude) as estimated_centroid_longitude
from {{ ref('silver_listings') }}
where neighbourhood is not null
group by 1, 2, 3
