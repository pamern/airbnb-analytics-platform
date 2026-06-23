"""Leakage-safe feature preparation and sklearn preprocessing."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


NUMERIC_FEATURES = {"bedrooms", "bathrooms", "accommodates", "host_response_rate", "host_listings_count", "calculated_host_listings_count", "host_total_listings_count", "host_acceptance_rate", "number_of_reviews_ltm", "minimum_nights"}
CATEGORICAL_FEATURES = {"neighbourhood", "room_type", "property_base_group", "host_response_time"}
NATIVE_MISSING_FEATURES = {"review_scores_location"}


def group_property_type(value: object) -> str:
    """Apply the existing notebook property-type grouping rule."""
    if pd.isna(value): return "Unknown"
    text = str(value).lower().strip()
    groups = [(("serviced apartment", "aparthotel"), "Serviced Apartment / Aparthotel"),
              (("hostel",), "Hostel"), (("guesthouse", "guest house", "bed and breakfast"), "Guesthouse / B&B"),
              (("hotel", "resort", "ryokan", "kezhan"), "Hotel / Resort"), (("villa",), "Villa"),
              (("loft",), "Loft"), (("rental unit", "condo", "apartment"), "Apartment / Condo"),
              (("treehouse", "tiny home", "earthen home", "earth home", "dome", "tower", "lighthouse", "castle", "shipping container", "container", "hut", "tent"), "Unique Stay"),
              (("cabin", "nature lodge", "farm stay", "barn", "houseboat", "boat", "island", "camper/rv"), "Special Stay"),
              (("townhouse", "guest suite", "vacation home", "casa particular", "bungalow", "cottage", "chalet", "house", "home"), "House / Home")]
    return next((label for keywords, label in groups if any(keyword in text for keyword in keywords)), "Other")


def prepare_modeling_frame(df: pd.DataFrame, *, price_column: str = "price", target_column: str = "log_price") -> pd.DataFrame:
    """Clean target rows and retain the notebook's deterministic feature engineering."""
    frame = df.copy()
    price = pd.to_numeric(frame[price_column], errors="coerce")
    frame = frame.loc[price.notna() & (price > 0)].copy()
    frame[price_column] = price.loc[frame.index]
    frame[target_column] = np.log1p(frame[price_column])
    if "property_type" in frame:
        frame["property_base_group"] = frame["property_type"].map(group_property_type)
    if {"has_reviews", "reviews_per_month"}.issubset(frame.columns):
        frame.loc[frame["has_reviews"].eq(0), "reviews_per_month"] = 0
    return frame


def split_train_test(frame: pd.DataFrame, features: Sequence[str], *, target_column: str, test_size: float, random_seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    """Split raw selected features before any fitted transformation."""
    metadata_columns = [column for column in ("listing_id", "host_id") if column in frame]
    return train_test_split(frame.loc[:, list(features)], frame[target_column], frame.loc[:, metadata_columns], test_size=test_size, random_state=random_seed)


def split_train_calibration_test(frame: pd.DataFrame, features: Sequence[str], *, target_column: str, test_size: float, calibration_size: float, random_seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split raw data 64/16/20 by default, before fitting any preprocessing."""
    if not 0 < test_size < 1 or not 0 < calibration_size < 1 or test_size + calibration_size >= 1:
        raise ValueError("test_size and calibration_size must be positive and sum to less than one")
    metadata_columns = [column for column in ("listing_id", "host_id") if column in frame]
    development, test = train_test_split(frame, test_size=test_size, random_state=random_seed)
    calibration_fraction = calibration_size / (1 - test_size)
    train, calibration = train_test_split(development, test_size=calibration_fraction, random_state=random_seed)
    def parts(values: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        return values.loc[:, list(features)], values[target_column], values.loc[:, metadata_columns]
    X_train, y_train, meta_train = parts(train)
    X_calibration, y_calibration, meta_calibration = parts(calibration)
    X_test, y_test, meta_test = parts(test)
    return X_train, X_calibration, X_test, y_train, y_calibration, y_test, meta_train, meta_calibration, meta_test


def build_preprocessor(features: Sequence[str], *, native_missing: bool = True) -> ColumnTransformer:
    """Build the existing imputation, encoding and scaling policy for selected features."""
    selected = set(features)
    numeric = sorted(selected & NUMERIC_FEATURES)
    categorical = sorted(selected & CATEGORICAL_FEATURES)
    native = sorted(selected & NATIVE_MISSING_FEATURES)
    transformers: list[tuple[str, object, list[str]]] = []
    if numeric:
        transformers.append(("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric))
    if categorical:
        transformers.append(("categorical", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")), ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=30, sparse_output=True))]), categorical))
    if native:
        transformer: object = "passthrough" if native_missing else Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
        transformers.append(("review_score", transformer, native))
    return ColumnTransformer(transformers=transformers, remainder="drop", sparse_threshold=0.0)


def get_transformed_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Return transformed feature names after the preprocessor has been fitted."""
    return preprocessor.get_feature_names_out().tolist()
