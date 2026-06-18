"""
File clean feature chuẩn bị cho KMeans matrix, dùng để def hàm chứ không chạy.

File này chỉ xử lý feature:
- clean price
- drop price bị thiếu hoặc <= 0
- group property_type thành property_base_group
- count amenities thành amenities_count
- log minimum_nights thành minimum_nights_log
- fill median cho bedrooms, bathrooms, beds theo room_type
- drop dòng thiếu feature bắt buộc để train cluster
"""

from __future__ import annotations

import ast

import numpy as np
import pandas as pd


NUMERIC_COLUMNS = [
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities_count",
    "minimum_nights",
    "price",
]

OUTPUT_COLUMNS = [
    "listing_id",
    "price",
    "room_type",
    "property_type",
    "property_base_group",
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities_count",
    "minimum_nights",
    "minimum_nights_log",
]

ROOM_SIZE_COLUMNS = ["bedrooms", "bathrooms", "beds"]

CLUSTER_REQUIRED_COLUMNS = [
    "room_type",
    "property_base_group",
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities_count",
    "minimum_nights_log",
]


def clean_price(value: object) -> float:
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)
    return pd.to_numeric(str(value).replace("$", "").replace(",", "").strip(), errors="coerce")


def group_property_type_for_model(value: object) -> str:
    """Gom property_type thành nhóm dùng cho KMeans."""
    if pd.isna(value):
        return "Unspecified Property Type"

    text = str(value).lower().strip()

    if text in ["private room", "entire place", "entire home/apt"]:
        return "Unspecified Property Type"

    if "serviced apartment" in text or "aparthotel" in text:
        return "Serviced Apartment / Aparthotel"

    if "hostel" in text:
        return "Hostel"

    if "guesthouse" in text or "bed and breakfast" in text:
        return "Guesthouse / B&B"

    if any(k in text for k in ["boutique hotel", "hotel", "resort", "ryokan", "kezhan"]):
        return "Hotel / Resort"

    if "villa" in text:
        return "Villa"

    if any(k in text for k in ["rental unit", "condo", "apartment", "loft"]):
        return "Apartment / Condo"

    if any(
        k in text
        for k in [
            "townhouse",
            "guest suite",
            "vacation home",
            "casa particular",
            "bungalow",
            "cottage",
            "chalet",
            "entire home",
            "in home",
            "home/apt",
        ]
    ):
        return "House / Home"

    if any(
        k in text
        for k in [
            "tiny home",
            "treehouse",
            "earthen home",
            "dome",
            "tower",
            "lighthouse",
            "castle",
            "shipping container",
            "hut",
            "tent",
            "cabin",
            "nature lodge",
            "farm stay",
            "barn",
            "houseboat",
            "boat",
            "island",
            "camper/rv",
        ]
    ):
        return "Niche / Special Stay"

    return "Unspecified Property Type"


def count_amenities(value: object) -> int:
    """Đếm số amenities từ chuỗi/list amenities."""
    if pd.isna(value):
        return 0

    text = str(value).strip()
    if not text or text in ["[]", "{}"]:
        return 0

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple, set)):
            return len(parsed)
    except (ValueError, SyntaxError):
        pass

    return len([item for item in text.strip("[]{}").split(",") if item.strip()])


def prepare_listing_cluster_features(
    listings_raw: pd.DataFrame,
    drop_invalid_price: bool = True,
) -> pd.DataFrame:
    """Tạo các feature cơ bản giống notebook."""
    listings = listings_raw.copy()

    if "price" in listings.columns:
        listings["price"] = listings["price"].apply(clean_price)
        if drop_invalid_price:
            listings = listings.dropna(subset=["price"]).copy()
            listings = listings[listings["price"] > 0].copy()

    if "property_type" in listings.columns:
        listings["property_base_group"] = listings["property_type"].apply(
            group_property_type_for_model
        )

    if "amenities" in listings.columns:
        listings["amenities_count"] = listings["amenities"].apply(count_amenities)
    elif "amenities_count" not in listings.columns:
        listings["amenities_count"] = 0

    for column in NUMERIC_COLUMNS:
        if column in listings.columns:
            listings[column] = pd.to_numeric(listings[column], errors="coerce")

    if "minimum_nights" in listings.columns:
        minimum_nights = listings["minimum_nights"].fillna(0).clip(lower=0)
        listings["minimum_nights_log"] = np.log1p(minimum_nights)

    return listings


def fill_room_size_by_room_type(listings: pd.DataFrame) -> pd.DataFrame:
    """Điền median theo room_type cho bedrooms, bathrooms, beds."""
    listings = listings.copy()

    for column in ROOM_SIZE_COLUMNS:
        listings[column] = listings[column].fillna(
            listings.groupby("room_type")[column].transform("median")
        )
        listings[column] = listings[column].fillna(listings[column].median())

    return listings


def select_valid_cluster_feature_rows(listings: pd.DataFrame) -> pd.DataFrame:
    """Chỉ giữ cột Gold feature và drop dòng thiếu feature bắt buộc."""
    missing_columns = [column for column in OUTPUT_COLUMNS if column not in listings.columns]
    if missing_columns:
        raise ValueError(f"Missing required feature columns: {missing_columns}")

    return listings[OUTPUT_COLUMNS].dropna(
        subset=["listing_id", "price", *CLUSTER_REQUIRED_COLUMNS]
    )


def build_gold_cluster_feature_frame(listings_raw: pd.DataFrame) -> pd.DataFrame:
    """Full flow xử lý feature cho bảng gold_listing_cluster_features."""
    listings = prepare_listing_cluster_features(listings_raw, drop_invalid_price=True)
    listings = fill_room_size_by_room_type(listings)
    listings = select_valid_cluster_feature_rows(listings)

    return listings
