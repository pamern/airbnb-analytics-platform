# -*- coding: utf-8 -*-
"""Các đường dẫn dùng chung cho project."""

from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
RAW_CITY_NAME: str = "bangkok"
RAW_CITY_DATA_DIR: Path = RAW_DATA_DIR / RAW_CITY_NAME
RAW_CITY_OBJECT_PREFIX: str = f"raw/{RAW_CITY_NAME}"
SAMPLE_DATA_DIR: Path = DATA_DIR / "sample"
EXTERNAL_DATA_DIR: Path = DATA_DIR / "external"

INGESTION_DIR: Path = PROJECT_ROOT / "ingestion"
DBT_DIR: Path = PROJECT_ROOT / "dbt"
ML_DIR: Path = PROJECT_ROOT / "ml"
ML_OUTPUTS_DIR: Path = ML_DIR / "outputs"
LLM_DIR: Path = PROJECT_ROOT / "llm"
LLM_OUTPUTS_DIR: Path = LLM_DIR / "outputs"
APP_DIR: Path = PROJECT_ROOT / "app"
AIRFLOW_DIR: Path = PROJECT_ROOT / "airflow"
CONFIGS_DIR: Path = PROJECT_ROOT / "configs"
UTILS_DIR: Path = PROJECT_ROOT / "utils"
NOTEBOOKS_DIR: Path = PROJECT_ROOT / "notebooks"
SCRIPTS_DIR: Path = PROJECT_ROOT / "scripts"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
DOCS_DIR: Path = PROJECT_ROOT / "docs"

ENV_FILE: Path = PROJECT_ROOT / ".env"
ENV_EXAMPLE_FILE: Path = PROJECT_ROOT / ".env.example"


def ensure_directory(path: Path) -> Path:
    """Tạo thư mục nếu chưa tồn tại và trả về chính đường dẫn đó."""
    path.mkdir(parents=True, exist_ok=True)
    return path
