{{ config(materialized='table', schema='gold') }}

with listings as (
    select
        listing_id,
        host_id,
        neighbourhood,
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bedrooms,
        beds,
        price,
        minimum_nights,
        maximum_nights,
        instant_bookable,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        host_is_superhost,
        host_listings_count,
        host_total_listings_count,
        calculated_host_listings_count,
        number_of_reviews,
        number_of_reviews_ltm,
        reviews_per_month,
        review_scores_rating,
        review_scores_accuracy,
        review_scores_cleanliness,
        review_scores_checkin,
        review_scores_communication,
        review_scores_location,
        review_scores_value,
        amenities
    from {{ ref('silver_listings') }}
    where price is not null
),

engineered as (
    select
        listing_id,
        host_id,
        neighbourhood,
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bedrooms,
        beds,
        minimum_nights,
        maximum_nights,
        instant_bookable,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        host_is_superhost,
        host_listings_count,
        host_total_listings_count,
        calculated_host_listings_count,
        number_of_reviews,
        number_of_reviews_ltm,
        reviews_per_month,
        review_scores_rating,
        review_scores_accuracy,
        review_scores_cleanliness,
        review_scores_checkin,
        review_scores_communication,
        review_scores_location,
        review_scores_value,
        cast(number_of_reviews > 0 as tinyint) as has_reviews,
        cast(
            case
                when amenities is null then null
                when try(json_array_length(amenities)) is not null then try(json_array_length(amenities))
                else null
            end
            as integer
        ) as amenities_count,
        ln(1 + price) as log_price
    from listings
)

select *
from engineered
