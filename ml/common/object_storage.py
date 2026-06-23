"""S3-compatible storage for versioned ML artifact directories."""

from __future__ import annotations

import logging
import shutil
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from configs.settings import OBJECT_STORAGE
from ml.common.paths import REPO_ROOT

LOGGER = logging.getLogger(__name__)
CACHE_ROOT = REPO_ROOT / ".cache" / "model_artifacts"
MAX_CACHED_VERSIONS_PER_MODEL = 10


class ObjectStorageError(RuntimeError):
    """Raised for a safe, user-actionable artifact-storage failure."""


def _require_configuration() -> None:
    values = {
        "OBJECT_STORAGE_ENDPOINT_URL": OBJECT_STORAGE.endpoint_url,
        "OBJECT_STORAGE_ACCESS_KEY_ID": OBJECT_STORAGE.access_key_id,
        "OBJECT_STORAGE_SECRET_ACCESS_KEY": OBJECT_STORAGE.secret_access_key,
        "OBJECT_STORAGE_BUCKET_NAME": OBJECT_STORAGE.bucket_name,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ObjectStorageError("Missing required Object Storage configuration: " + ", ".join(missing))


def create_object_storage_client():
    """Create one lazy S3 client without exposing credentials in logs."""
    _require_configuration()
    import boto3

    return boto3.client("s3", endpoint_url=OBJECT_STORAGE.endpoint_url, aws_access_key_id=OBJECT_STORAGE.access_key_id, aws_secret_access_key=OBJECT_STORAGE.secret_access_key, region_name=OBJECT_STORAGE.region)


def build_object_key(model_name: str, model_version: str, relative_path: str) -> str:
    if not model_name or not model_version or not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise ValueError("Object storage key requires safe model_name, model_version, and relative_path")
    return "/".join(part for part in (OBJECT_STORAGE.prefix, model_name, model_version, Path(relative_path).as_posix()) if part)


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri.strip())
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ValueError("Artifact URI must use s3://bucket/object-key")
    return parsed.netloc, parsed.path.lstrip("/")


def object_exists(bucket: str, key: str) -> bool:
    try:
        create_object_storage_client().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise ObjectStorageError("Unable to check artifact object") from error


def upload_artifact_directory(artifact_dir: Path, model_name: str, model_version: str) -> str:
    if not artifact_dir.is_dir() or not (artifact_dir / "model.joblib").is_file():
        raise ObjectStorageError(f"Artifact directory is incomplete for {model_name} version {model_version}")
    client = create_object_storage_client()
    for path in artifact_dir.rglob("*"):
        if path.is_file():
            key = build_object_key(model_name, model_version, path.relative_to(artifact_dir).as_posix())
            try:
                client.upload_file(str(path), OBJECT_STORAGE.bucket_name, key)
            except ClientError as error:
                raise ObjectStorageError(f"Failed to upload artifact for {model_name} version {model_version}") from error
    model_key = build_object_key(model_name, model_version, "model.joblib")
    if not object_exists(OBJECT_STORAGE.bucket_name, model_key):
        raise ObjectStorageError(f"Artifact not found after upload for model_name={model_name} model_version={model_version}")
    return f"s3://{OBJECT_STORAGE.bucket_name}/{model_key}"


def materialize_artifact(uri: str, model_name: str, model_version: str) -> Path:
    """Return local model.joblib, downloading only its version prefix on first use."""
    uri = uri.strip()
    if not uri.startswith("s3://"):
        path = Path(uri); return path if path.is_absolute() else (REPO_ROOT / path).resolve()
    bucket, model_key = parse_s3_uri(uri)
    uri_hash = sha256(uri.encode("utf-8")).hexdigest()[:16]
    cache_dir = CACHE_ROOT / model_name / model_version / uri_hash
    model_path = cache_dir / "model.joblib"
    if model_path.is_file():
        return model_path
    prefix = model_key.rstrip("/") + "/" if not model_key.endswith(".joblib") else model_key.rsplit("/", 1)[0] + "/"
    client = create_object_storage_client()
    temporary = cache_dir.with_name(cache_dir.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True); temporary.mkdir(parents=True, exist_ok=True)
    try:
        if model_key.endswith(".joblib"):
            keys = [model_key, *[prefix + name for name in ("feature_schema.json", "cluster_mapping.json", "shap_sample_values.parquet", "shap_original_importance.csv", "shap_sample_summary.json")]]
            for index, key in enumerate(keys):
                destination = temporary / key.removeprefix(prefix); destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    client.download_file(bucket, key, str(destination))
                except ClientError as error:
                    if index == 0:
                        raise ObjectStorageError(f"Artifact not found for model_name={model_name} model_version={model_version} object_key={model_key}") from error
                    if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                        raise
        else:
            response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            for item in response.get("Contents", []):
                key = item["Key"]; destination = temporary / key.removeprefix(prefix); destination.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(bucket, key, str(destination))
        if not (temporary / "model.joblib").is_file():
            raise ObjectStorageError(f"Artifact model.joblib is unavailable for model_name={model_name} model_version={model_version}")
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(cache_dir, ignore_errors=True); temporary.replace(cache_dir)
        versions = sorted((path for path in cache_dir.parent.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
        for stale in versions[MAX_CACHED_VERSIONS_PER_MODEL:]:
            shutil.rmtree(stale, ignore_errors=True)
    except ClientError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ObjectStorageError(f"Failed to download artifact for model_name={model_name} model_version={model_version}") from error
    return model_path
