import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(r"D:\airbnb-analytics-platform")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_access import load_pricing_dataset, load_overview_dataset, load_listing_availability_monthly_dataset, load_listing_review_recency_dataset

try:
    print("Testing load_pricing_dataset...")
    df1 = load_pricing_dataset()
    print("load_pricing_dataset SUCCESS, shape:", df1.shape)
except Exception as e:
    print("load_pricing_dataset FAILED:", str(e))

try:
    print("Testing load_overview_dataset...")
    df2 = load_overview_dataset()
    print("load_overview_dataset SUCCESS, shape:", df2.shape)
except Exception as e:
    print("load_overview_dataset FAILED:", str(e))

try:
    print("Testing load_listing_availability_monthly_dataset...")
    df3 = load_listing_availability_monthly_dataset()
    print("load_listing_availability_monthly_dataset SUCCESS, shape:", df3.shape)
except Exception as e:
    print("load_listing_availability_monthly_dataset FAILED:", str(e))

try:
    print("Testing load_listing_review_recency_dataset...")
    df4 = load_listing_review_recency_dataset()
    print("load_listing_review_recency_dataset SUCCESS, shape:", df4.shape)
except Exception as e:
    print("load_listing_review_recency_dataset FAILED:", str(e))
