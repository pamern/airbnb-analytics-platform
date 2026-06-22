from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
from duckdb import DuckDBPyConnection
from sklearn.decomposition import PCA

from ml.common.paths import SEGMENTATION_ARTIFACTS_DIR
from ml.listing_segmentation.config import MODEL_FEATURES, SEGMENT_MAP
from ml.listing_segmentation.prediction import load_segmentation_model
from utils.motherduck import close_connection, connect_motherduck
from utils.sql import query_dataframe


MOCK_PREDICTED_PRICE = 2450.0
FEATURE_TABLE = "gold.gold_cluster_model_features"
ASSIGNMENT_TABLES = [
    "gold.gold_listing_cluster_assignments",
    "gold.gold_listing_segments",
]


def build_user_listing_frame(user_listing: dict[str, Any]) -> pd.DataFrame:
    """Build one KMeans-compatible row from Model 3 form input."""
    minimum_nights = max(float(user_listing["minimum_nights"]), 0.0)
    return pd.DataFrame(
        [
            {
                "listing_id": "manual_input",
                "price": float(user_listing.get("price", MOCK_PREDICTED_PRICE)),
                "room_type": str(user_listing["room_type"]),
                "property_type": str(user_listing["property_type"]),
                "property_base_group": map_property_base_group(user_listing["property_type"]),
                "accommodates": int(user_listing["accommodates"]),
                "bedrooms": float(user_listing["bedrooms"]),
                "bathrooms": float(user_listing["bathrooms"]),
                "beds": float(user_listing["beds"]),
                "amenities_count": int(user_listing["amenities_count"]),
                "minimum_nights": int(minimum_nights),
                "minimum_nights_log": math.log1p(minimum_nights),
            }
        ]
    )


def map_property_base_group(property_type: object) -> str:
    """Mirror the property grouping rules used by gold_cluster_model_features.sql."""
    value = "" if property_type is None else str(property_type).strip().lower()
    if not value or value in {"private room", "entire place", "entire home/apt"}:
        return "Unspecified Property Type"
    if "serviced apartment" in value or "aparthotel" in value:
        return "Serviced Apartment / Aparthotel"
    if "hostel" in value:
        return "Hostel"
    if "guesthouse" in value or "bed and breakfast" in value:
        return "Guesthouse / B&B"
    if (
        "boutique hotel" in value
        or "hotel" in value
        or "resort" in value
        or "ryokan" in value
        or "kezhan" in value
    ):
        return "Hotel / Resort"
    if "villa" in value:
        return "Villa"
    if (
        "rental unit" in value
        or "condo" in value
        or "apartment" in value
        or "loft" in value
    ):
        return "Apartment / Condo"
    if (
        "townhouse" in value
        or "guest suite" in value
        or "vacation home" in value
        or "casa particular" in value
        or "bungalow" in value
        or "cottage" in value
        or "chalet" in value
        or "entire home" in value
        or "in home" in value
        or "home/apt" in value
    ):
        return "House / Home"
    if (
        "tiny home" in value
        or "treehouse" in value
        or "earthen home" in value
        or "dome" in value
        or "tower" in value
        or "lighthouse" in value
        or "castle" in value
        or "shipping container" in value
        or "hut" in value
        or "tent" in value
        or "cabin" in value
        or "nature lodge" in value
        or "farm stay" in value
        or "barn" in value
        or "houseboat" in value
        or "boat" in value
        or "island" in value
        or "camper/rv" in value
    ):
        return "Niche / Special Stay"
    return "Unspecified Property Type"


def load_trained_kmeans_model() -> tuple[Any, str, Path]:
    """Load the latest persisted listing-segmentation artifact."""
    candidates = sorted(
        SEGMENTATION_ARTIFACTS_DIR.glob("*/model.joblib"),
        key=lambda path: path.parent.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No KMeans artifacts found under {SEGMENTATION_ARTIFACTS_DIR}"
        )
    model_path = candidates[0]
    return load_segmentation_model(model_path), model_path.parent.name, model_path


def analyze_user_listing(user_listing: dict[str, Any]) -> dict[str, Any]:
    """Assign a user listing to a trained KMeans segment and compare its price."""
    listing = build_user_listing_frame(user_listing)
    current_price = float(listing.loc[0, "price"])
    model, model_version, model_path = load_trained_kmeans_model()
    cluster = int(model.predict(listing[MODEL_FEATURES])[0])

    connection = connect_motherduck(read_only=True)
    try:
        price_stats = query_segment_prices(connection, model, cluster, current_price)
    finally:
        close_connection(connection)

    segment_median = price_stats["segment_median_price"]
    price_vs_segment_median = (
        current_price / segment_median - 1 if segment_median else None
    )
    if current_price < price_stats["segment_p25_price"]:
        price_position = "Below segment range"
    elif current_price > price_stats["segment_p75_price"]:
        price_position = "Above segment range"
    else:
        price_position = "Within segment range"

    return {
        "cluster": cluster,
        "segment_name": SEGMENT_MAP.get(cluster, "Unknown"),
        "current_price": current_price,
        "model_version": model_version,
        "model_path": str(model_path),
        "price_vs_segment_median": price_vs_segment_median,
        "price_position": price_position,
        **price_stats,
    }


def query_segment_prices(
    connection: DuckDBPyConnection,
    model: Any,
    cluster: int,
    current_price: float,
) -> dict[str, float]:
    """Calculate segment price statistics for the predicted cluster."""
    prices = _query_persisted_segment_prices(connection, cluster)
    if prices.empty:
        prices = _score_gold_features_for_segment(connection, model, cluster)
    if prices.empty:
        raise ValueError(f"No reference prices found for cluster {cluster}")

    return {
        "segment_median_price": float(prices.median()),
        "segment_p25_price": float(prices.quantile(0.25)),
        "segment_p75_price": float(prices.quantile(0.75)),
        "segment_mean_price": float(prices.mean()),
        "price_percentile_in_segment": float((prices <= current_price).mean()),
    }


def build_cluster_visualization_figure() -> Any:
    """Build a PCA scatter plot from Gold features and the trained KMeans model."""
    model, _, _ = load_trained_kmeans_model()
    connection = connect_motherduck(read_only=True)
    try:
        features = _load_gold_cluster_features(connection)
    finally:
        close_connection(connection)

    labels = model.predict(features[MODEL_FEATURES]).astype(int)
    transformed = model.named_steps["preprocessor"].transform(features[MODEL_FEATURES])
    points = PCA(n_components=2, random_state=42).fit_transform(transformed)
    view = pd.DataFrame(
        {
            "PCA 1": points[:, 0],
            "PCA 2": points[:, 1],
            "cluster": labels.astype(str),
            "segment": pd.Series(labels).map(SEGMENT_MAP).fillna("Unknown"),
            "price": features["price"].to_numpy(),
        }
    )
    fig = px.scatter(
        view,
        x="PCA 1",
        y="PCA 2",
        color="segment",
        hover_data={"segment": True, "price": ":,.0f", "cluster": False},
        color_discrete_map={
            "Standard short-stay listings": "#7FB3D5",
            "Long-stay standard apartments": "#BF6C32",
            "Large short-stay group homes": "#1F7A8C",
        },
    )
    fig.update_traces(marker=dict(size=5, opacity=0.58))
    fig.update_layout(
        title="KMeans Cluster Visualization",
        title_font=dict(size=18, color="#0F2742"),
        height=330,
        margin=dict(l=0, r=0, t=48, b=0),
        legend_title_text="Cluster",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def _query_persisted_segment_prices(
    connection: DuckDBPyConnection,
    cluster: int,
) -> pd.Series:
    for assignment_table in ASSIGNMENT_TABLES:
        if not _table_exists(connection, assignment_table):
            continue
        cluster_column = _first_existing_column(connection, assignment_table, ["cluster", "cluster_id"])
        if cluster_column is None:
            continue
        query = f"""
            select features.price
            from {assignment_table} as segments
            inner join {FEATURE_TABLE} as features
                on segments.listing_id = features.listing_id
            where segments.{cluster_column} = ?
              and features.price is not null
        """
        prices = connection.execute(query, [int(cluster)]).fetchdf()["price"]
        if not prices.empty:
            return pd.to_numeric(prices, errors="coerce").dropna()
    return pd.Series(dtype=float)


def _score_gold_features_for_segment(
    connection: DuckDBPyConnection,
    model: Any,
    cluster: int,
) -> pd.Series:
    features = _load_gold_cluster_features(connection)
    labels = model.predict(features[MODEL_FEATURES]).astype(int)
    prices = features.loc[labels == int(cluster), "price"]
    return pd.to_numeric(prices, errors="coerce").dropna()


def _load_gold_cluster_features(connection: DuckDBPyConnection) -> pd.DataFrame:
    query = f"""
        select
            listing_id,
            price,
            room_type,
            property_base_group,
            accommodates,
            bedrooms,
            bathrooms,
            beds,
            amenities_count,
            minimum_nights_log
        from {FEATURE_TABLE}
        where price is not null
          and room_type is not null
          and property_base_group is not null
          and accommodates is not null
          and bedrooms is not null
          and bathrooms is not null
          and beds is not null
          and amenities_count is not null
          and minimum_nights_log is not null
    """
    features = query_dataframe(connection, query)
    numeric_columns = [
        "price",
        "accommodates",
        "bedrooms",
        "bathrooms",
        "beds",
        "amenities_count",
        "minimum_nights_log",
    ]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    return features.dropna(subset=["price", *MODEL_FEATURES])


def _table_exists(connection: DuckDBPyConnection, table_name: str) -> bool:
    schema_name, short_name = table_name.split(".", 1)
    count = connection.execute(
        """
        select count(*)
        from information_schema.tables
        where table_schema = ?
          and table_name = ?
        """,
        [schema_name, short_name],
    ).fetchone()[0]
    return bool(count)


def _first_existing_column(
    connection: DuckDBPyConnection,
    table_name: str,
    candidates: list[str],
) -> str | None:
    columns = {
        row[1]
        for row in connection.execute(f"pragma table_info('{table_name}')").fetchall()
    }
    return next((column for column in candidates if column in columns), None)
