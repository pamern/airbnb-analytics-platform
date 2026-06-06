# -*- coding: utf-8 -*-
"""Helper kết nối và thao tác cơ bản với MinIO."""

from pathlib import Path

from minio import Minio

from configs.settings import MINIO, validate_required_settings


def get_minio_client() -> Minio:
    """Tạo MinIO client sau khi kiểm tra cấu hình cần thiết."""
    missing = validate_required_settings("minio")
    if missing:
        raise ValueError(f"Thiếu biến môi trường cho MinIO: {', '.join(missing)}")

    return Minio(
        endpoint=MINIO.endpoint,
        access_key=MINIO.access_key,
        secret_key=MINIO.secret_key,
        secure=MINIO.secure,
    )


def ensure_bucket(client: Minio, bucket_name: str = MINIO.bucket) -> None:
    """Tạo bucket nếu bucket chưa tồn tại."""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_file(
    client: Minio,
    local_path: str | Path,
    object_name: str,
    bucket_name: str = MINIO.bucket,
) -> None:
    """Upload một file local lên MinIO."""
    ensure_bucket(client, bucket_name=bucket_name)
    client.fput_object(bucket_name, object_name, str(local_path))


def download_file(
    client: Minio,
    object_name: str,
    local_path: str | Path,
    bucket_name: str = MINIO.bucket,
) -> Path:
    """Tải một object từ MinIO về local."""
    output_path = Path(local_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client.fget_object(bucket_name, object_name, str(output_path))
    return output_path
