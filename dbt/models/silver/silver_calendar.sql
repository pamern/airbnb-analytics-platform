{% set calendar_source = source('airbnb_bronze', 'bronze_calendar') %}

with source_data as (
    select *
    from {{ calendar_source }} as src
),

cleaned as (
    select
        try_cast({{ source_column(calendar_source, 'listing_id') }} as bigint) as listing_id,
        try_cast({{ source_column(calendar_source, 'date') }} as date) as calendar_date,
        {{ clean_boolean(source_column(calendar_source, 'available')) }} as is_available,
        try_cast({{ source_column(calendar_source, 'minimum_nights') }} as integer) as minimum_nights,
        try_cast({{ source_column(calendar_source, 'maximum_nights') }} as integer) as maximum_nights
    from source_data as src
),

deduplicated as (
    select *
    from cleaned
    where listing_id is not null
      and calendar_date is not null
    qualify row_number() over (
        partition by listing_id, calendar_date
        order by
            case when is_available is not null then 1 else 0 end desc,
            case when minimum_nights is not null then 1 else 0 end desc,
            case when maximum_nights is not null then 1 else 0 end desc
    ) = 1
)

select *
from deduplicated
