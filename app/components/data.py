from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.paths import ML_OUTPUTS_DIR


PRICE_OUTPUT_DIR = ML_OUTPUTS_DIR / "price_modeling"
PRICE_CSV_DIR = PRICE_OUTPUT_DIR / "csv"
PRICE_CHART_DIR = PRICE_OUTPUT_DIR / "charts"
PRICE_METADATA_DIR = PRICE_OUTPUT_DIR / "metadata"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def get_price_model_metadata() -> dict[str, Any]:
    return load_json(PRICE_METADATA_DIR / "02_modeling_run_metadata.json", {})


def get_selected_features() -> dict[str, Any]:
    return load_json(PRICE_METADATA_DIR / "01_selected_features.json", {})


def get_feature_selection_summary() -> pd.DataFrame:
    return load_csv(str(PRICE_CSV_DIR / "13_feature_selection_model_summary.csv"))


def get_price_model_charts() -> list[Path]:
    if not PRICE_CHART_DIR.exists():
        return []
    return sorted(PRICE_CHART_DIR.glob("*.png"))
