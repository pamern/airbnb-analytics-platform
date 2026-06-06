# -*- coding: utf-8 -*-
"""Helper đọc ghi file local cho pipeline."""

import json
from pathlib import Path
from typing import Any

import pandas as pd


def read_json(path: str | Path) -> dict[str, Any]:
    """Đọc file JSON và trả về dict."""
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(data: dict[str, Any], path: str | Path) -> Path:
    """Ghi dict thành file JSON, tự tạo thư mục cha nếu cần."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    return output_path


def read_csv(path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Đọc CSV thành DataFrame."""
    return pd.read_csv(path, **kwargs)


def write_csv(dataframe: pd.DataFrame, path: str | Path, **kwargs: Any) -> Path:
    """Ghi DataFrame thành CSV, tự tạo thư mục cha nếu cần."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, **kwargs)
    return output_path


def read_parquet(path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Đọc Parquet thành DataFrame."""
    return pd.read_parquet(path, **kwargs)


def write_parquet(dataframe: pd.DataFrame, path: str | Path, **kwargs: Any) -> Path:
    """Ghi DataFrame thành Parquet, tự tạo thư mục cha nếu cần."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_parquet(output_path, index=False, **kwargs)
    return output_path
