"""Chart generation for listing segmentation outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline

from ml.listing_segmentation.config import CHART_OUTPUT_DIR, MODEL_FEATURES
from ml.listing_segmentation.evaluate import transform_features
from ml.listing_segmentation.preprocessing import build_listing_segment_pipeline


def save_cluster_size_chart(clustered: pd.DataFrame, output_path: Path) -> None:
    counts = clustered["cluster_id"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 5))
    counts.plot(kind="bar", ax=ax, color="#4c78a8")
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Listing count")
    ax.set_title("Listing count by cluster")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_pca_cluster_plot(model: Pipeline, clustered: pd.DataFrame, output_path: Path) -> None:
    transformed = transform_features(model, clustered)
    pca = PCA(n_components=2, random_state=42)
    coordinates = pca.fit_transform(transformed)
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(
        coordinates[:, 0],
        coordinates[:, 1],
        c=clustered["cluster_id"],
        cmap="tab10",
        alpha=0.7,
        s=18,
    )
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.set_title("PCA projection of listing clusters")
    fig.colorbar(scatter, ax=ax, label="Cluster")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_cluster_profile_heatmap(profiles: pd.DataFrame, output_path: Path) -> None:
    numeric_profiles = profiles.select_dtypes(include=[np.number]).set_index(profiles["cluster_id"])
    normalized = (numeric_profiles - numeric_profiles.mean()) / numeric_profiles.std(ddof=0).replace(0, 1)
    fig, ax = plt.subplots(figsize=(10, 5))
    image = ax.imshow(normalized.fillna(0), aspect="auto", cmap="coolwarm")
    ax.set_xticks(range(len(normalized.columns)))
    ax.set_xticklabels(normalized.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(normalized.index)))
    ax.set_yticklabels(normalized.index)
    ax.set_xlabel("Profile metric")
    ax.set_ylabel("Cluster")
    ax.set_title("Normalized cluster profile heatmap")
    fig.colorbar(image, ax=ax, label="z-score")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_elbow_curve(features: pd.DataFrame, output_path: Path, max_k: int = 8) -> None:
    upper_k = min(max_k, len(features) - 1)
    if upper_k < 2:
        return

    ks = list(range(2, upper_k + 1))
    inertias = []
    for k in ks:
        pipeline = build_listing_segment_pipeline()
        pipeline.named_steps["kmeans"].set_params(n_clusters=k)
        pipeline.fit(features[MODEL_FEATURES])
        inertias.append(pipeline.named_steps["kmeans"].inertia_)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ks, inertias, marker="o", color="#f58518")
    ax.set_xlabel("Number of clusters")
    ax.set_ylabel("Inertia")
    ax.set_title("Elbow curve")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_all_charts(model: Pipeline, clustered: pd.DataFrame, profiles: pd.DataFrame) -> None:
    CHART_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_elbow_curve(clustered, CHART_OUTPUT_DIR / "01_elbow_curve.png")
    save_cluster_size_chart(clustered, CHART_OUTPUT_DIR / "02_cluster_size.png")
    save_pca_cluster_plot(model, clustered, CHART_OUTPUT_DIR / "03_pca_cluster_plot.png")
    save_cluster_profile_heatmap(profiles, CHART_OUTPUT_DIR / "04_cluster_profile_heatmap.png")
