from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ml.common import object_storage


class ObjectStorageTests(unittest.TestCase):
    def test_parse_uri_and_versioned_key(self) -> None:
        self.assertEqual(object_storage.parse_s3_uri("s3://bucket/models/price/v1/model.joblib"), ("bucket", "models/price/v1/model.joblib"))
        self.assertNotEqual(
            object_storage.build_object_key("price_model", "v1", "model.joblib"),
            object_storage.build_object_key("segmentation_model", "v1", "model.joblib"),
        )

    @patch("ml.common.object_storage.object_exists", return_value=True)
    @patch("ml.common.object_storage.create_object_storage_client")
    def test_upload_uses_versioned_keys(self, client_factory: MagicMock, _: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "model.joblib").write_bytes(b"model"); (root / "feature_schema.json").write_text("{}")
            object_storage.upload_artifact_directory(root, "price_model", "v1")
        keys = [call.args[2] for call in client_factory.return_value.upload_file.call_args_list]
        self.assertIn("airbnb-models/price_model/v1/model.joblib", keys)
        self.assertIn("airbnb-models/price_model/v1/feature_schema.json", keys)

    @patch("ml.common.object_storage.create_object_storage_client")
    def test_remote_artifact_is_downloaded_once(self, client_factory: MagicMock) -> None:
        client = client_factory.return_value
        client.list_objects_v2.return_value = {"Contents": [{"Key": "airbnb-models/price_model/v1/model.joblib"}]}
        def download(bucket: str, key: str, target: str) -> None: Path(target).write_bytes(b"model")
        client.download_file.side_effect = download
        with tempfile.TemporaryDirectory() as directory, patch.object(object_storage, "CACHE_ROOT", Path(directory)):
            first = object_storage.materialize_artifact("s3://bucket/airbnb-models/price_model/v1/model.joblib", "price_model", "v1")
            first_download_count = client.download_file.call_count
            second = object_storage.materialize_artifact("s3://bucket/airbnb-models/price_model/v1/model.joblib", "price_model", "v1")
        self.assertEqual(first, second)
        self.assertEqual(client.download_file.call_count, first_download_count)


if __name__ == "__main__":
    unittest.main()
