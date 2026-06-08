with listing_base as (
    select
        dl.listing_key,
        dl.listing_id,
        dl.location_key,
        loc.neighbourhood,
        dl.room_type,
        dl.accommodates,
        dl.latitude,
        dl.longitude,
        fls.price,
        fls.review_scores_rating as rating,
        fls.reviews_per_month
    from {{ ref('dim_listing') }} as dl
    inner join {{ ref('fact_listing_snapshot') }} as fls
        on dl.listing_key = fls.listing_key
    left join {{ ref('dim_location') }} as loc
        on dl.location_key = loc.location_key
    where dl.latitude is not null
      and dl.longitude is not null
      and dl.room_type is not null
),

candidate_pairs as (
    select
        base.listing_id,
        comp.listing_id as competitor_listing_id,
        base.neighbourhood,
        base.room_type,
        base.price,
        comp.price as competitor_price,
        comp.price - base.price as price_difference,
        base.rating,
        comp.rating as competitor_rating,
        base.reviews_per_month,
        comp.reviews_per_month as competitor_reviews_per_month,
        6371.0 * 2.0 * asin(sqrt(
            pow(sin(radians(comp.latitude - base.latitude) / 2.0), 2)
            + cos(radians(base.latitude))
            * cos(radians(comp.latitude))
            * pow(sin(radians(comp.longitude - base.longitude) / 2.0), 2)
        )) as distance_km
    from listing_base as base
    inner join listing_base as comp
        on base.listing_id != comp.listing_id
        and base.location_key = comp.location_key
        and base.room_type = comp.room_type
        and abs(coalesce(base.accommodates, 0) - coalesce(comp.accommodates, 0)) <= 2
),

ranked as (
    select
        *,
        row_number() over (
            partition by listing_id
            order by distance_km, abs(price_difference), competitor_listing_id
        ) as benchmark_rank
    from candidate_pairs
)

select *
from ranked
where benchmark_rank <= 10
