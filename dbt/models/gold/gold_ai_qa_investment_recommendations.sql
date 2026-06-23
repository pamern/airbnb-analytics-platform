{{ config(materialized='table', schema='gold') }}

with listing_market_ml as (
    select
        coalesce(location_dim.neighbourhood, 'UNKNOWN') as neighbourhood,
        coalesce(listing_dim.room_type, 'UNKNOWN') as room_type,
        fact.listing_id,
        fact.listing_snapshot_price as price,
        fact.estimated_occupancy_l365d / 365.0 as estimated_occupancy_rate,
        fact.estimated_revenue_l365d as estimated_revenue,
        fact.review_scores_rating,
        fact.number_of_reviews,
        pred.predicted_price,
        seg.cluster_name
    from {{ ref('fact_listing_current_snapshot') }} as fact
    inner join {{ ref('dim_listing') }} as listing_dim
        on fact.listing_key = listing_dim.listing_key
    left join {{ ref('dim_location') }} as location_dim
        on fact.location_key = location_dim.location_key
    left join gold.gold_listing_price_predictions as pred
        on listing_dim.listing_id = pred.listing_id
    left join gold.gold_listing_cluster_assignments as seg
        on listing_dim.listing_id = seg.listing_id
    where fact.listing_snapshot_price is not null
      and fact.listing_snapshot_price > 0
),

neighbourhood_summary as (
    select
        neighbourhood,
        count(distinct listing_id) as neighbourhood_listing_count,
        median(price) as neighbourhood_median_price,
        median(estimated_occupancy_rate) as neighbourhood_median_occupancy_rate,
        median(estimated_revenue) as neighbourhood_median_estimated_revenue,
        median(review_scores_rating)
            filter (where review_scores_rating is not null and number_of_reviews >= 5)
            as neighbourhood_median_review_score,
        count(distinct listing_id)
            filter (where review_scores_rating is not null and number_of_reviews >= 5)
            as neighbourhood_reliable_review_listing_count,
        median(predicted_price) as neighbourhood_median_predicted_price,
        mode(cluster_name) as neighbourhood_dominant_segment,
        count(case when price > predicted_price * 1.5 then 1 end) as neighbourhood_overpriced_listings_count
    from listing_market_ml
    group by 1
),

room_type_summary as (
    select
        neighbourhood,
        room_type,
        count(distinct listing_id) as room_type_listing_count,
        median(price) as room_type_median_price,
        median(estimated_occupancy_rate) as room_type_median_occupancy_rate,
        median(estimated_revenue) as room_type_median_estimated_revenue,
        median(review_scores_rating)
            filter (where review_scores_rating is not null and number_of_reviews >= 5)
            as room_type_median_review_score,
        count(distinct listing_id)
            filter (where review_scores_rating is not null and number_of_reviews >= 5)
            as room_type_reliable_review_listing_count,
        median(predicted_price) as room_type_median_predicted_price,
        mode(cluster_name) as room_type_dominant_segment
    from listing_market_ml
    group by 1, 2
),

cohort_summary as (
    select
        room_type_summary.neighbourhood,
        room_type_summary.room_type,
        neighbourhood_summary.neighbourhood_listing_count,
        neighbourhood_summary.neighbourhood_median_price,
        neighbourhood_summary.neighbourhood_median_occupancy_rate,
        neighbourhood_summary.neighbourhood_median_estimated_revenue,
        neighbourhood_summary.neighbourhood_median_review_score,
        neighbourhood_summary.neighbourhood_reliable_review_listing_count,
        neighbourhood_summary.neighbourhood_median_predicted_price,
        neighbourhood_summary.neighbourhood_dominant_segment,
        neighbourhood_summary.neighbourhood_overpriced_listings_count,
        room_type_summary.room_type_listing_count,
        room_type_summary.room_type_median_price,
        room_type_summary.room_type_median_occupancy_rate,
        room_type_summary.room_type_median_estimated_revenue,
        room_type_summary.room_type_median_review_score,
        room_type_summary.room_type_reliable_review_listing_count,
        room_type_summary.room_type_median_predicted_price,
        room_type_summary.room_type_dominant_segment
    from room_type_summary
    inner join neighbourhood_summary
        on room_type_summary.neighbourhood = neighbourhood_summary.neighbourhood
),

market_baseline as (
    select
        median(neighbourhood_median_price) as market_median_price,
        median(neighbourhood_median_occupancy_rate) as market_median_occupancy_rate,
        median(neighbourhood_median_estimated_revenue) as market_median_estimated_revenue
    from (
        select distinct
            neighbourhood,
            neighbourhood_median_price,
            neighbourhood_median_occupancy_rate,
            neighbourhood_median_estimated_revenue
        from cohort_summary
    )
),

scored as (
    select
        cohort_summary.*,
        market_baseline.market_median_price,
        market_baseline.market_median_occupancy_rate,
        market_baseline.market_median_estimated_revenue,
        percent_rank() over (
            order by cohort_summary.room_type_median_estimated_revenue
        ) as revenue_percentile,
        percent_rank() over (
            order by cohort_summary.room_type_median_occupancy_rate
        ) as occupancy_percentile,
        case
            when cohort_summary.neighbourhood_listing_count < 30 then 0.25
            when cohort_summary.neighbourhood_listing_count between 30 and 150 then 1.00
            when cohort_summary.neighbourhood_listing_count between 151 and 300 then 0.65
            else 0.35
        end as competition_score,
        case
            when cohort_summary.room_type_listing_count < 10 then 0.30
            when cohort_summary.room_type_listing_count between 10 and 40 then 0.75
            else 1.00
        end as room_type_confidence_score
    from cohort_summary
    cross join market_baseline
    where cohort_summary.room_type_median_estimated_revenue is not null
      and cohort_summary.room_type_median_occupancy_rate is not null
),

classified as (
    select
        *,
        round(
            100 * (
                0.40 * coalesce(revenue_percentile, 0)
                + 0.30 * coalesce(occupancy_percentile, 0)
                + 0.20 * competition_score
                + 0.10 * room_type_confidence_score
            ),
            2
        ) as opportunity_score,
        round(
            100 * (
                case when neighbourhood_listing_count < 30 then 0.25 else 0 end
                + case when neighbourhood_listing_count > 300 then 0.20 else 0 end
                + case when room_type_listing_count < 10 then 0.20 else 0 end
                + case when room_type_median_occupancy_rate < market_median_occupancy_rate then 0.20 else 0 end
                + case
                    when room_type_median_price > market_median_price
                     and room_type_median_occupancy_rate < market_median_occupancy_rate
                        then 0.15
                    else 0
                end
            ),
            2
        ) as risk_score,
        concat_ws(
            '; ',
            case when neighbourhood_listing_count < 30 then 'Data Trap: neighbourhood sample below 30 listings' end,
            case when neighbourhood_listing_count > 300 then 'Saturation Trap: neighbourhood has more than 300 listings' end,
            case when room_type_listing_count < 10 then 'Room Type Confidence Risk: room type sample below 10 listings' end,
            case when room_type_median_occupancy_rate < market_median_occupancy_rate then 'Low Demand Risk: occupancy below market median' end,
            case
                when room_type_median_price > market_median_price
                 and room_type_median_occupancy_rate < market_median_occupancy_rate
                    then 'Price Trap: price above market median while occupancy is below market median'
            end,
            case
                when room_type_median_occupancy_rate > market_median_occupancy_rate
                 and room_type_median_estimated_revenue < market_median_estimated_revenue
                    then 'Cheap Demand Trap: occupancy above market median but revenue below market median'
            end
        ) as risk_flags
    from scored
),

tiered as (
    select
        *,
        case
            when opportunity_score >= 70 then 'High'
            when opportunity_score >= 45 then 'Medium'
            else 'Low'
        end as opportunity_level,
        case
            when risk_score >= 45 then 'High'
            when risk_score >= 20 then 'Medium'
            else 'Low'
        end as risk_level,
        case
            when room_type_listing_count < 10 or neighbourhood_listing_count < 30 then 'Low'
            when risk_score >= 45 then 'Medium'
            else 'High'
        end as confidence_level
    from classified
)

select
    neighbourhood,
    room_type as recommended_room_type,
    neighbourhood_listing_count as listing_count,
    room_type_listing_count,
    neighbourhood_median_price as median_price,
    neighbourhood_median_occupancy_rate as median_occupancy_rate,
    neighbourhood_median_estimated_revenue as median_estimated_revenue,
    neighbourhood_median_review_score,
    neighbourhood_reliable_review_listing_count,
    neighbourhood_median_predicted_price,
    neighbourhood_dominant_segment,
    neighbourhood_overpriced_listings_count,
    room_type_median_price,
    room_type_median_occupancy_rate,
    room_type_median_estimated_revenue,
    room_type_median_review_score,
    room_type_reliable_review_listing_count,
    room_type_median_predicted_price,
    room_type_dominant_segment,
    market_median_price,
    market_median_occupancy_rate,
    market_median_estimated_revenue,
    opportunity_score,
    risk_score,
    opportunity_level,
    risk_level,
    case
        when opportunity_level = 'High' and risk_level in ('Low', 'Medium') then 'Strong Invest'
        when opportunity_level = 'High' and risk_level = 'High' then 'Investigate Further'
        when opportunity_level in ('Low', 'Medium') and risk_level in ('Low', 'Medium') then 'Stable but Low Priority'
        else 'Avoid'
    end as action_tier,
    confidence_level,
    risk_flags
from tiered
