{% set neighbourhoods_source = source('airbnb_bronze', 'bronze_neighbourhoods') %}

with neighbourhoods as (
    select
        {{ clean_text(source_column(neighbourhoods_source, 'neighbourhood')) }} as neighbourhood,
        {{ clean_text(source_column(neighbourhoods_source, 'neighbourhood_group')) }} as neighbourhood_group
    from {{ neighbourhoods_source }} as src
),

listing_geo as (
    select
        neighbourhood,
        max(neighbourhood_group) as listing_neighbourhood_group,
        avg(latitude) as avg_latitude,
        avg(longitude) as avg_longitude,
        count(distinct listing_id) as listing_count
    from {{ ref('silver_listings_cleaned') }}
    where neighbourhood is not null
    group by neighbourhood
),

combined as (
    select
        coalesce(n.neighbourhood, g.neighbourhood) as neighbourhood,
        coalesce(n.neighbourhood_group, g.listing_neighbourhood_group) as neighbourhood_group,
        g.avg_latitude,
        g.avg_longitude,
        coalesce(g.listing_count, 0) as listing_count
    from neighbourhoods as n
    full outer join listing_geo as g
        on lower(n.neighbourhood) = lower(g.neighbourhood)
)

select
    md5(lower(coalesce(neighbourhood, 'unknown'))) as location_key,
    'bangkok' as city,
    neighbourhood,
    neighbourhood_group,
    avg_latitude,
    avg_longitude,
    listing_count
from combined
where neighbourhood is not null
qualify row_number() over (
    partition by lower(neighbourhood)
    order by listing_count desc, neighbourhood_group nulls last
) = 1
