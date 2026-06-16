with bronze_calendar as (
    select *
    from {{ source('airbnb_bronze', 'bronze_calendar') }}
),

typed as (
    select
        try_cast({{ source_column(source('airbnb_bronze', 'bronze_calendar'), 'listing_id') }} as bigint) as listing_id,
        try_cast({{ source_column(source('airbnb_bronze', 'bronze_calendar'), 'date') }} as date) as calendar_date,
        {{ clean_boolean(source_column(source('airbnb_bronze', 'bronze_calendar'), 'available')) }} as is_available,
        {{ clean_money(source_column(source('airbnb_bronze', 'bronze_calendar'), 'price')) }} as price,
        {{ clean_money(source_column(source('airbnb_bronze', 'bronze_calendar'), 'adjusted_price')) }} as adjusted_price,
        try_cast({{ source_column(source('airbnb_bronze', 'bronze_calendar'), 'minimum_nights') }} as integer) as minimum_nights,
        try_cast({{ source_column(source('airbnb_bronze', 'bronze_calendar'), 'maximum_nights') }} as integer) as maximum_nights
    from bronze_calendar as src
),

duplicate_keys as (
    select
        listing_id,
        calendar_date,
        count(*) as duplicate_count,
        count(distinct price) as distinct_price_count,
        count(distinct adjusted_price) as distinct_adjusted_price_count,
        count(distinct is_available) as distinct_availability_count,
        count(distinct minimum_nights) as distinct_minimum_nights_count,
        count(distinct maximum_nights) as distinct_maximum_nights_count
    from typed
    where listing_id is not null
      and calendar_date is not null
    group by 1, 2
    having count(*) > 1
),

summary as (
    select 'total_rows' as metric, cast(count(*) as varchar) as value
    from typed

    union all

    select 'rows_with_valid_key' as metric, cast(count(*) as varchar) as value
    from typed
    where listing_id is not null
      and calendar_date is not null

    union all

    select 'duplicate_keys' as metric, cast(count(*) as varchar) as value
    from duplicate_keys

    union all

    select 'rows_in_duplicate_keys' as metric, cast(coalesce(sum(duplicate_count), 0) as varchar) as value
    from duplicate_keys

    union all

    select 'duplicate_keys_with_price_conflict' as metric, cast(count(*) as varchar) as value
    from duplicate_keys
    where distinct_price_count > 1

    union all

    select 'duplicate_keys_with_adjusted_price_conflict' as metric, cast(count(*) as varchar) as value
    from duplicate_keys
    where distinct_adjusted_price_count > 1

    union all

    select 'duplicate_keys_with_availability_conflict' as metric, cast(count(*) as varchar) as value
    from duplicate_keys
    where distinct_availability_count > 1

    union all

    select 'duplicate_keys_with_minimum_nights_conflict' as metric, cast(count(*) as varchar) as value
    from duplicate_keys
    where distinct_minimum_nights_count > 1

    union all

    select 'duplicate_keys_with_maximum_nights_conflict' as metric, cast(count(*) as varchar) as value
    from duplicate_keys
    where distinct_maximum_nights_count > 1
)

select *
from summary
order by metric
