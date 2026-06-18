"""File này chạy backend của listing_segment"""
from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.k_means.listing_segment_service import analyze_user_listing


sample_listing = {
    "room_type": "Entire home/apt",
    "property_type": "Entire rental unit",
    "accommodates": 4,
    "bedrooms": 2,
    "bathrooms": 2,
    "beds": 2,
    "amenities_count": 35,
    "minimum_nights": 3,
    "current_price": 2500,
}


def main() -> None:
    os.environ.setdefault("AIRBNB_DB_TARGET", "local")
    os.environ.setdefault("ALLOW_MOTHERDUCK_WRITE", "0")
    result = analyze_user_listing(sample_listing)
    for key, value in result.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
