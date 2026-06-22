"""In-memory DuckDB tests for name-based DataFrame appends."""

from __future__ import annotations

import unittest

import duckdb
import pandas as pd

from orchestration.assets.ml_assets import _prepare_shap_importance_rows
from orchestration.resources.motherduck import MotherDuckResource, quote_table_name


class MotherDuckDataFrameWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = duckdb.connect(":memory:")
        self.resource = MotherDuckResource()

    def tearDown(self) -> None:
        self.connection.close()

    def test_appends_columns_by_name_not_physical_order(self) -> None:
        self.connection.execute("CREATE TABLE target (id INTEGER NOT NULL, name VARCHAR NOT NULL, value DOUBLE NOT NULL)")
        rows = pd.DataFrame({"value": [2.5], "id": [7], "name": ["listing"]})
        self.assertEqual(self.resource.append_dataframe("target", rows, connection=self.connection), 1)
        self.assertEqual(self.connection.execute("SELECT id, name, value FROM target").fetchone(), (7, "listing", 2.5))

    def test_unknown_column_fails_before_insert(self) -> None:
        self.connection.execute("CREATE TABLE target (id INTEGER NOT NULL)")
        with self.assertRaisesRegex(ValueError, "Unknown dataframe columns"):
            self.resource.append_dataframe("target", pd.DataFrame({"id": [1], "unexpected": [2]}), connection=self.connection)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM target").fetchone()[0], 0)

    def test_missing_required_column_fails_before_insert(self) -> None:
        self.connection.execute("CREATE TABLE target (id INTEGER NOT NULL, name VARCHAR NOT NULL)")
        with self.assertRaisesRegex(ValueError, "Missing target columns"):
            self.resource.append_dataframe("target", pd.DataFrame({"id": [1]}), connection=self.connection)

    def test_empty_dataframe_is_a_noop(self) -> None:
        self.connection.execute("CREATE TABLE target (id INTEGER NOT NULL)")
        self.assertEqual(self.resource.append_dataframe("target", pd.DataFrame({"id": pd.Series(dtype="int64")}), connection=self.connection), 0)

    def test_schema_qualified_table_is_quoted_and_written(self) -> None:
        self.connection.execute("CREATE SCHEMA mlops")
        self.connection.execute("CREATE TABLE mlops.model_feature_importance (run_id VARCHAR NOT NULL, importance_value DOUBLE NOT NULL)")
        self.resource.append_dataframe("mlops.model_feature_importance", pd.DataFrame({"importance_value": [0.4], "run_id": ["run-1"]}), connection=self.connection)
        self.assertEqual(quote_table_name("mlops.model_feature_importance"), '"mlops"."model_feature_importance"')
        self.assertEqual(self.connection.execute("SELECT run_id, importance_value FROM mlops.model_feature_importance").fetchone(), ("run-1", 0.4))

    def test_invalid_shap_numeric_value_fails_before_duckdb_insert(self) -> None:
        rows = pd.DataFrame([{"run_id": "run", "model_name": "price_model", "model_version": "v1", "feature_name": "numeric__bedrooms", "source_feature": "bedrooms", "feature_level": "TRANSFORMED", "importance_value": "bedrooms", "importance_rank": 1, "importance_method": "shap", "created_at": "2026-06-22T00:00:00Z"}])
        with self.assertRaisesRegex(ValueError, "Invalid SHAP importance dtype"):
            _prepare_shap_importance_rows(rows)


if __name__ == "__main__":
    unittest.main()
