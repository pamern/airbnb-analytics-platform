with date_values as (
    select calendar_date as date_day
    from {{ ref('silver_calendar') }}
    where calendar_date is not null

    union

    select review_date as date_day
    from {{ ref('silver_reviews') }}
    where review_date is not null

    union

    select last_scraped as date_day
    from {{ ref('silver_listings') }}
    where last_scraped is not null

    union

    select host_since as date_day
    from {{ ref('silver_listings') }}
    where host_since is not null

    union

    select last_review as date_day
    from {{ ref('silver_listings') }}
    where last_review is not null
)

select
    cast(strftime(date_day, '%Y%m%d') as integer) as date_key,
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    strftime(date_day, '%B') as month_name,
    extract(day from date_day) as day,
    strftime(date_day, '%A') as day_of_week,
    extract(week from date_day) as week_of_year,
    extract(isodow from date_day) in (6, 7) as is_weekend
from date_values
