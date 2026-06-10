{% set listings_source = source('airbnb_bronze', 'bronze_listings') %}

with source_data as (
    select *
    from {{ listings_source }} as src
),

renamed as (
    select
        try_cast({{ source_column(listings_source, 'id') }} as bigint) as listing_id,
        {{ clean_text(source_column(listings_source, 'name')) }} as listing_name,
        try_cast({{ source_column(listings_source, 'host_id') }} as bigint) as host_id,
        {{ clean_text(source_column(listings_source, 'host_name')) }} as host_name,
        try_cast({{ source_column(listings_source, 'host_since') }} as date) as host_since,
        {{ clean_text(source_column(listings_source, 'host_location')) }} as host_location,
        {{ clean_text(source_column(listings_source, 'host_response_time')) }} as host_response_time,
        {{ clean_percent(source_column(listings_source, 'host_response_rate')) }} as host_response_rate,
        {{ clean_percent(source_column(listings_source, 'host_acceptance_rate')) }} as host_acceptance_rate,
        {{ clean_boolean(source_column(listings_source, 'host_is_superhost')) }} as host_is_superhost,
        try_cast({{ source_column(listings_source, 'host_listings_count') }} as integer) as host_listings_count,
        try_cast({{ source_column(listings_source, 'host_total_listings_count') }} as integer) as host_total_listings_count,
        {{ clean_boolean(source_column(listings_source, 'host_identity_verified')) }} as host_identity_verified,

        coalesce(
            {{ clean_text(source_column(listings_source, 'neighbourhood_cleansed')) }},
            {{ clean_text(source_column(listings_source, 'neighbourhood')) }}
        ) as neighbourhood,
        coalesce(
            {{ clean_text(source_column(listings_source, 'neighbourhood_group_cleansed')) }},
            {{ clean_text(source_column(listings_source, 'neighbourhood_group')) }}
        ) as neighbourhood_group,
        try_cast({{ source_column(listings_source, 'latitude') }} as double) as latitude,
        try_cast({{ source_column(listings_source, 'longitude') }} as double) as longitude,

        {{ clean_text(source_column(listings_source, 'property_type')) }} as property_type,
        {{ clean_text(source_column(listings_source, 'room_type')) }} as room_type,
        try_cast({{ source_column(listings_source, 'accommodates') }} as integer) as accommodates,
        coalesce(
            try_cast({{ source_column(listings_source, 'bathrooms') }} as double),
            try_cast(regexp_extract(cast({{ source_column(listings_source, 'bathrooms_text') }} as varchar), '[0-9]+(\\.[0-9]+)?') as double)
        ) as bathrooms,
        try_cast({{ source_column(listings_source, 'bedrooms') }} as double) as bedrooms,
        try_cast({{ source_column(listings_source, 'beds') }} as double) as beds,
        {{ clean_text(source_column(listings_source, 'amenities')) }} as amenities,
        {{ clean_money(source_column(listings_source, 'price')) }} as price,
        try_cast({{ source_column(listings_source, 'minimum_nights') }} as integer) as minimum_nights,
        try_cast({{ source_column(listings_source, 'maximum_nights') }} as integer) as maximum_nights,
        try_cast({{ source_column(listings_source, 'availability_30') }} as integer) as availability_30,
        try_cast({{ source_column(listings_source, 'availability_60') }} as integer) as availability_60,
        try_cast({{ source_column(listings_source, 'availability_90') }} as integer) as availability_90,
        try_cast({{ source_column(listings_source, 'availability_365') }} as integer) as availability_365,
        {{ clean_boolean(source_column(listings_source, 'instant_bookable')) }} as instant_bookable,

        try_cast({{ source_column(listings_source, 'number_of_reviews') }} as integer) as number_of_reviews,
        try_cast({{ source_column(listings_source, 'number_of_reviews_ltm') }} as integer) as number_of_reviews_ltm,
        try_cast({{ source_column(listings_source, 'last_review') }} as date) as last_review,
        try_cast({{ source_column(listings_source, 'review_scores_rating') }} as double) as review_scores_rating,
        try_cast({{ source_column(listings_source, 'review_scores_accuracy') }} as double) as review_scores_accuracy,
        try_cast({{ source_column(listings_source, 'review_scores_cleanliness') }} as double) as review_scores_cleanliness,
        try_cast({{ source_column(listings_source, 'review_scores_checkin') }} as double) as review_scores_checkin,
        try_cast({{ source_column(listings_source, 'review_scores_communication') }} as double) as review_scores_communication,
        try_cast({{ source_column(listings_source, 'review_scores_location') }} as double) as review_scores_location,
        try_cast({{ source_column(listings_source, 'review_scores_value') }} as double) as review_scores_value,
        try_cast({{ source_column(listings_source, 'reviews_per_month') }} as double) as reviews_per_month,
        try_cast({{ source_column(listings_source, 'calculated_host_listings_count') }} as integer) as calculated_host_listings_count,
        try_cast({{ source_column(listings_source, 'last_scraped') }} as date) as last_scraped
    from source_data as src
),

deduplicated as (
    select *
    from renamed
    where listing_id is not null
    qualify row_number() over (
        partition by listing_id
        order by last_scraped desc nulls last, listing_name
    ) = 1
)

select *
from deduplicated
