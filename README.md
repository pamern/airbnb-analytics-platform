```
docker compose up -d minio
uv run python ingestion/validate_raw_data.py
uv run python ingestion/load_to_minio.py
uv run python ingestion/load_to_motherduck.py
```