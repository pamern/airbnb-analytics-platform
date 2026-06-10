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
        {{ clean_money(source_column(calendar_source, 'price')) }} as price,
        {{ clean_money(source_column(calendar_source, 'adjusted_price')) }} as adjusted_price,
        try_cast({{ source_column(calendar_source, 'minimum_nights') }} as integer) as minimum_nights,
        try_cast({{ source_column(calendar_source, 'maximum_nights') }} as integer) as maximum_nights
    from source_data as src
)

select
    listing_id,
    calendar_date,
    is_available,
    price,
    adjusted_price,
    minimum_nights,
    maximum_nights
from cleaned
where listing_id is not null
  and calendar_date is not null
