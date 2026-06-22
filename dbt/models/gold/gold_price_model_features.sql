{{ config(materialized='table', schema='gold') }}

with listings as (
    select
        listing_id,
        host_id,
        neighbourhood,
        property_type,
        room_type,
        price,
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
        amenities
    from {{ ref('silver_listings') }}
    where price is not null
      and price > 0
),

engineered as (
    select
        listing_id,
        host_id,
        neighbourhood,
        property_type,
        room_type,
        price,
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
),

model_features as (
    select
        *,
        case
            when property_type is null then 'Unknown'
            when lower(trim(property_type)) like '%serviced apartment%'
              or lower(trim(property_type)) like '%aparthotel%' then 'Serviced Apartment / Aparthotel'
            when lower(trim(property_type)) like '%hostel%' then 'Hostel'
            when lower(trim(property_type)) like '%guesthouse%'
              or lower(trim(property_type)) like '%guest house%'
              or lower(trim(property_type)) like '%bed and breakfast%' then 'Guesthouse / B&B'
            when lower(trim(property_type)) like '%hotel%'
              or lower(trim(property_type)) like '%resort%'
              or lower(trim(property_type)) like '%ryokan%'
              or lower(trim(property_type)) like '%kezhan%' then 'Hotel / Resort'
            when lower(trim(property_type)) like '%villa%' then 'Villa'
            when lower(trim(property_type)) like '%loft%' then 'Loft'
            when lower(trim(property_type)) like '%rental unit%'
              or lower(trim(property_type)) like '%condo%'
              or lower(trim(property_type)) like '%apartment%' then 'Apartment / Condo'
            when lower(trim(property_type)) like '%treehouse%'
              or lower(trim(property_type)) like '%tiny home%'
              or lower(trim(property_type)) like '%earthen home%'
              or lower(trim(property_type)) like '%earth home%'
              or lower(trim(property_type)) like '%dome%'
              or lower(trim(property_type)) like '%tower%'
              or lower(trim(property_type)) like '%lighthouse%'
              or lower(trim(property_type)) like '%castle%'
              or lower(trim(property_type)) like '%shipping container%'
              or lower(trim(property_type)) like '%container%'
              or lower(trim(property_type)) like '%hut%'
              or lower(trim(property_type)) like '%tent%' then 'Unique Stay'
            when lower(trim(property_type)) like '%cabin%'
              or lower(trim(property_type)) like '%nature lodge%'
              or lower(trim(property_type)) like '%farm stay%'
              or lower(trim(property_type)) like '%barn%'
              or lower(trim(property_type)) like '%houseboat%'
              or lower(trim(property_type)) like '%boat%'
              or lower(trim(property_type)) like '%island%'
              or lower(trim(property_type)) like '%camper/rv%' then 'Special Stay'
            when lower(trim(property_type)) like '%townhouse%'
              or lower(trim(property_type)) like '%guest suite%'
              or lower(trim(property_type)) like '%vacation home%'
              or lower(trim(property_type)) like '%casa particular%'
              or lower(trim(property_type)) like '%bungalow%'
              or lower(trim(property_type)) like '%cottage%'
              or lower(trim(property_type)) like '%chalet%'
              or lower(trim(property_type)) like '%house%'
              or lower(trim(property_type)) like '%home%' then 'House / Home'
            else 'Other'
        end as property_base_group
    from engineered
)

select
    *,
    md5(concat_ws('|',
        coalesce(cast(neighbourhood as varchar), '__NULL__'),
        coalesce(cast(bedrooms as varchar), '__NULL__'),
        coalesce(cast(room_type as varchar), '__NULL__'),
        coalesce(cast(property_base_group as varchar), '__NULL__'),
        coalesce(cast(host_response_time as varchar), '__NULL__'),
        coalesce(cast(bathrooms as varchar), '__NULL__'),
        coalesce(cast(accommodates as varchar), '__NULL__'),
        coalesce(cast(review_scores_location as varchar), '__NULL__'),
        coalesce(cast(host_response_rate as varchar), '__NULL__'),
        coalesce(cast(host_listings_count as varchar), '__NULL__'),
        coalesce(cast(calculated_host_listings_count as varchar), '__NULL__'),
        coalesce(cast(host_total_listings_count as varchar), '__NULL__'),
        coalesce(cast(host_acceptance_rate as varchar), '__NULL__'),
        coalesce(cast(number_of_reviews_ltm as varchar), '__NULL__'),
        coalesce(cast(minimum_nights as varchar), '__NULL__')
    )) as feature_hash
from model_features
