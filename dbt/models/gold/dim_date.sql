with dates as (
    select calendar_date as date_value
    from {{ ref('silver_calendar') }}
    where calendar_date is not null

    union

    select review_date as date_value
    from {{ ref('silver_reviews') }}
    where review_date is not null

    union

    select last_scraped as date_value
    from {{ ref('silver_listings_cleaned') }}
    where last_scraped is not null
)

select
    cast(strftime(date_value, '%Y%m%d') as integer) as date_key,
    date_value as date,
    extract(day from date_value) as day,
    extract(month from date_value) as month,
    strftime(date_value, '%B') as month_name,
    extract(quarter from date_value) as quarter,
    extract(year from date_value) as year,
    strftime(date_value, '%A') as day_of_week,
    extract(dow from date_value) in (0, 6) as is_weekend,
    case
        when extract(month from date_value) in (11, 12, 1, 2) then 'peak'
        when extract(month from date_value) in (3, 4, 5) then 'hot'
        when extract(month from date_value) in (6, 7, 8, 9, 10) then 'rainy'
        else 'unknown'
    end as season
from dates
qualify row_number() over (
    partition by date_value
    order by date_value
) = 1
