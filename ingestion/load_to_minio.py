# -*- coding: utf-8 -*-
"""Upload raw data Bangkok lên MinIO."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.paths import RAW_CITY_DATA_DIR, RAW_CITY_OBJECT_PREFIX
from configs.settings import MINIO
from utils.logger import get_logger
from utils.minio_client import ensure_bucket, get_minio_client, upload_file


LOGGER = get_logger(__name__)
RAW_CITY_DIR = RAW_CITY_DATA_DIR
OBJECT_PREFIX = RAW_CITY_OBJECT_PREFIX


def iter_raw_files(raw_dir: Path = RAW_CITY_DIR) -> list[Path]:
    """Lấy danh sách file trực tiếp trong thư mục raw, bỏ qua thư mục con."""
    if not raw_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục raw: {raw_dir}")

    return sorted(path for path in raw_dir.iterdir() if path.is_file())


def upload_raw_files(raw_dir: Path = RAW_CITY_DIR) -> None:
    """Upload toàn bộ file raw Bangkok lên bucket MinIO."""
    client = get_minio_client()
    ensure_bucket(client, bucket_name=MINIO.bucket)

    for file_path in iter_raw_files(raw_dir):
        object_name = f"{OBJECT_PREFIX}/{file_path.name}"
        upload_file(
            client=client,
            local_path=file_path,
            object_name=object_name,
            bucket_name=MINIO.bucket,
        )
        LOGGER.info("Đã upload: %s -> %s/%s", file_path.name, MINIO.bucket, object_name)


def main() -> None:
    """Chạy upload raw data lên MinIO."""
    upload_raw_files()
    LOGGER.info("Upload raw data lên MinIO hoàn tất.")


if __name__ == "__main__":
    main()
