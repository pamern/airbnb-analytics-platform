{{ config(materialized='table', schema='gold') }}

with source_listings as (
    select
        listing_id,
        price,
        room_type,
        property_type,
        accommodates,
        bedrooms,
        bathrooms,
        beds,
        amenities,
        minimum_nights
    from {{ ref('silver_listings') }}
),

prepared as (
    select
        *,
        lower(trim(property_type)) as property_type_normalized,
        trim(amenities) as amenities_trimmed
    from source_listings
    where price is not null
      and price > 0
),

feature_base as (
    select
        listing_id,
        price,
        room_type,
        property_type,
        case
            when property_type is null then 'Unspecified Property Type'
            when property_type_normalized in ('private room', 'entire place', 'entire home/apt')
                then 'Unspecified Property Type'
            when property_type_normalized like '%serviced apartment%'
                or property_type_normalized like '%aparthotel%'
                then 'Serviced Apartment / Aparthotel'
            when property_type_normalized like '%hostel%'
                then 'Hostel'
            when property_type_normalized like '%guesthouse%'
                or property_type_normalized like '%bed and breakfast%'
                then 'Guesthouse / B&B'
            when property_type_normalized like '%boutique hotel%'
                or property_type_normalized like '%hotel%'
                or property_type_normalized like '%resort%'
                or property_type_normalized like '%ryokan%'
                or property_type_normalized like '%kezhan%'
                then 'Hotel / Resort'
            when property_type_normalized like '%villa%'
                then 'Villa'
            when property_type_normalized like '%rental unit%'
                or property_type_normalized like '%condo%'
                or property_type_normalized like '%apartment%'
                or property_type_normalized like '%loft%'
                then 'Apartment / Condo'
            when property_type_normalized like '%townhouse%'
                or property_type_normalized like '%guest suite%'
                or property_type_normalized like '%vacation home%'
                or property_type_normalized like '%casa particular%'
                or property_type_normalized like '%bungalow%'
                or property_type_normalized like '%cottage%'
                or property_type_normalized like '%chalet%'
                or property_type_normalized like '%entire home%'
                or property_type_normalized like '%in home%'
                or property_type_normalized like '%home/apt%'
                then 'House / Home'
            when property_type_normalized like '%tiny home%'
                or property_type_normalized like '%treehouse%'
                or property_type_normalized like '%earthen home%'
                or property_type_normalized like '%dome%'
                or property_type_normalized like '%tower%'
                or property_type_normalized like '%lighthouse%'
                or property_type_normalized like '%castle%'
                or property_type_normalized like '%shipping container%'
                or property_type_normalized like '%hut%'
                or property_type_normalized like '%tent%'
                or property_type_normalized like '%cabin%'
                or property_type_normalized like '%nature lodge%'
                or property_type_normalized like '%farm stay%'
                or property_type_normalized like '%barn%'
                or property_type_normalized like '%houseboat%'
                or property_type_normalized like '%boat%'
                or property_type_normalized like '%island%'
                or property_type_normalized like '%camper/rv%'
                then 'Niche / Special Stay'
            else 'Unspecified Property Type'
        end as property_base_group,
        accommodates,
        bedrooms,
        bathrooms,
        beds,
        case
            when amenities is null then 0
            when amenities_trimmed in ('', '[]', '{}') then 0
            when json_valid(amenities) then cast(json_array_length(amenities) as integer)
            else cast(
                len(
                    list_filter(
                        string_split(trim(amenities_trimmed, '[]{}'), ','),
                        item -> trim(item) <> ''
                    )
                ) as integer
            )
        end as amenities_count,
        minimum_nights,
        greatest(coalesce(minimum_nights, 0), 0) as minimum_nights_clean
    from prepared
),

medians as (
    select
        *,
        median(bedrooms) over (partition by room_type) as bedrooms_room_type_median,
        median(bathrooms) over (partition by room_type) as bathrooms_room_type_median,
        median(beds) over (partition by room_type) as beds_room_type_median,
        median(bedrooms) over () as bedrooms_global_median,
        median(bathrooms) over () as bathrooms_global_median,
        median(beds) over () as beds_global_median
    from feature_base
),

imputed as (
    select
        listing_id,
        price,
        room_type,
        property_type,
        property_base_group,
        accommodates,
        coalesce(bedrooms, bedrooms_room_type_median, bedrooms_global_median) as bedrooms,
        coalesce(bathrooms, bathrooms_room_type_median, bathrooms_global_median) as bathrooms,
        coalesce(beds, beds_room_type_median, beds_global_median) as beds,
        amenities_count,
        minimum_nights,
        ln(1 + minimum_nights_clean) as minimum_nights_log
    from medians
)

select
    listing_id,
    price,
    room_type,
    property_type,
    property_base_group,
    accommodates,
    bedrooms,
    bathrooms,
    beds,
    amenities_count,
    minimum_nights,
    minimum_nights_log
from imputed
where listing_id is not null
  and price is not null
  and room_type is not null
  and property_base_group is not null
  and accommodates is not null
  and bedrooms is not null
  and bathrooms is not null
  and beds is not null
  and amenities_count is not null
  and minimum_nights_log is not null
