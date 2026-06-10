with calendar_fact as (
    select
        md5(cast(calendar.listing_id as varchar) || '||' || cast(calendar.calendar_date as varchar)) as availability_daily_key,
        dim.listing_key,
        cast(strftime(calendar.calendar_date, '%Y%m%d') as integer) as calendar_date_key,
        calendar.listing_id,
        calendar.is_available,
        calendar.price as calendar_price,
        calendar.adjusted_price as calendar_adjusted_price,
        calendar.minimum_nights as calendar_minimum_nights,
        calendar.maximum_nights as calendar_maximum_nights
    from {{ ref('silver_calendar') }} as calendar
    inner join {{ ref('dim_listing') }} as dim
        on calendar.listing_id = dim.listing_id
)

select *
from calendar_fact
