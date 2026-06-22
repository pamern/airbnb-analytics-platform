```
uv run python ingestion/validate_raw_data.py
uv run python ingestion/load_to_motherduck.py
```

## Promote a model to Champion in MotherDuck

Retraining writes a `CANDIDATE` to `mlops.model_registry`; it never promotes the
model automatically. Until the Streamlit control is added, use the following
transaction in MotherDuck after replacing the two placeholder values. It archives
only the previous Champion for the chosen logical model (`price_model` or
`segmentation_model`) and guarantees that the selected version is the sole active
Champion for that model.

```sql
BEGIN TRANSACTION;

UPDATE mlops.model_registry
SET stage = 'ARCHIVED',
    is_active = FALSE
WHERE model_name = '<model_name>'
  AND stage = 'CHAMPION'
  AND is_active = TRUE;

UPDATE mlops.model_registry
SET stage = 'CHAMPION',
    is_active = TRUE,
    promoted_at = current_timestamp,
    promoted_by = '<your_name>'
WHERE model_name = '<model_name>'
  AND model_version = '<candidate_model_version>'
  AND stage = 'CANDIDATE';

COMMIT;
```

Verify the result before running inference:

```sql
SELECT model_name, model_version, stage, is_active, promoted_at
FROM mlops.model_registry
WHERE model_name = '<model_name>'
ORDER BY created_at DESC;
```

## Check the SHAP importance table

Inspect the physical column order and types before running `price_retraining_job`:

```sql
SELECT ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'mlops'
  AND table_name = 'model_feature_importance'
ORDER BY ordinal_position;
```

If the old table has an incompatible schema and its historical data may be removed,
recreate it explicitly before the job is run:

```sql
DROP TABLE IF EXISTS mlops.model_feature_importance;

CREATE TABLE mlops.model_feature_importance (
    run_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    feature_name VARCHAR NOT NULL,
    source_feature VARCHAR NOT NULL,
    feature_level VARCHAR NOT NULL,
    importance_value DOUBLE NOT NULL,
    importance_rank INTEGER NOT NULL,
    importance_method VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

The writer maps DataFrame columns by name, not the physical table order. Verify
the most recent SHAP records after retraining:

```sql
SELECT run_id, model_name, model_version, feature_name, source_feature,
       feature_level, importance_value, importance_rank, importance_method, created_at
FROM mlops.model_feature_importance
ORDER BY created_at DESC, importance_rank
LIMIT 50;
```
