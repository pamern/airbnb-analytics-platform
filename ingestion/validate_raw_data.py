# -*- coding: utf-8 -*-
"""Kiểm tra các file raw bắt buộc trước khi ingestion."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.paths import RAW_CITY_DATA_DIR
from utils.logger import get_logger


LOGGER = get_logger(__name__)
RAW_CITY_DIR = RAW_CITY_DATA_DIR
REQUIRED_FILES: tuple[str, ...] = (
    "listings.csv",
    "calendar.csv",
    "reviews.csv",
    "neighbourhoods.csv",
    "neighbourhoods.geojson",
)


def format_file_size(size_bytes: int) -> str:
    """Đổi dung lượng byte sang chuỗi dễ đọc khi log."""
    units = ("B", "KB", "MB", "GB")
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def validate_required_files(raw_dir: Path = RAW_CITY_DIR) -> list[Path]:
    """Kiểm tra file raw bắt buộc và trả về danh sách file đang thiếu."""
    missing_files: list[Path] = []

    LOGGER.info("Kiểm tra dữ liệu raw tại: %s", raw_dir)
    for filename in REQUIRED_FILES:
        file_path = raw_dir / filename
        if file_path.is_file():
            LOGGER.info(
                "Tồn tại: %s | dung lượng: %s",
                file_path.name,
                format_file_size(file_path.stat().st_size),
            )
        else:
            LOGGER.error("Thiếu file: %s", file_path)
            missing_files.append(file_path)

    return missing_files


def main() -> None:
    """Chạy kiểm tra raw data và raise lỗi nếu thiếu file."""
    missing_files = validate_required_files()
    if missing_files:
        missing_text = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"Thiếu file raw bắt buộc: {missing_text}")

    LOGGER.info("Raw data hợp lệ.")


if __name__ == "__main__":
    main()
