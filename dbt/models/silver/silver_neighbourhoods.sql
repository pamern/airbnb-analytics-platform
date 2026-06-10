{% set neighbourhoods_source = source('airbnb_bronze', 'bronze_neighbourhoods') %}

with source_data as (
    select *
    from {{ neighbourhoods_source }} as src
),

cleaned as (
    select
        {{ clean_text(source_column(neighbourhoods_source, 'neighbourhood')) }} as neighbourhood,
        {{ clean_text(source_column(neighbourhoods_source, 'neighbourhood_group')) }} as neighbourhood_group
    from source_data as src
),

deduplicated as (
    select *
    from cleaned
    where neighbourhood is not null
    qualify row_number() over (
        partition by lower(neighbourhood)
        order by neighbourhood_group nulls last
    ) = 1
)

select *
from deduplicated
