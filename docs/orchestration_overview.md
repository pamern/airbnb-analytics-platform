# Orchestration overview

## Mục đích

`orchestration/` dùng Dagster để điều phối dbt, hai pipeline ML và MotherDuck. Logic train, preprocessing, prediction và lưu artifact vẫn thuộc `ml/`; orchestration chỉ quản lý dependency, materialization, validation và persistence vào warehouse.

Entry point:

```bash
uv run dagster dev -m orchestration.definitions
```

Hệ thống có bốn job chạy thủ công. Chưa có schedule hoặc sensor.

## Luồng dữ liệu

```text
Silver listings
    |
    v
dbt Gold feature models (+ feature_hash)
    |
    +-- price_retraining_job ---------> ML train/evaluate
    |                                     |-> artifact
    |                                     |-> mlops metadata (CANDIDATE)
    |                                     `-> Gold evaluation predictions
    |
    +-- segmentation_retraining_job --> KMeans train/evaluate
    |                                     |-> artifact
    |                                     |-> mlops metadata (CANDIDATE)
    |                                     `-> Gold assignments + profiles
    |
    +-- price_prediction_job --------> active Price CHAMPION
    |                                     `-> incremental Gold predictions
    |
    `-- segmentation_assignment_job -> active Segmentation CHAMPION
                                          `-> incremental Gold assignments
```

Retraining không tự promote model. Model mới luôn được đăng ký với `stage = CANDIDATE`. Inference chỉ dùng đúng một model `CHAMPION` đang `is_active = TRUE`; không có fallback sang Candidate.

## Resources

| Resource | Vai trò |
| --- | --- |
| `dbt` | `DbtCliResource` chạy hai Gold feature model qua manifest dbt. |
| `motherduck` | Kết nối MotherDuck, đọc DataFrame, ghi DataFrame và quản lý transaction. Token lấy từ `MOTHERDUCK_TOKEN`. |
| `inference_config` | Resource cấu hình hiện được đăng ký trong Definitions; inference hiện không dùng candidate fallback. |

`MotherDuckResource` mở kết nối theo thời gian chạy asset; transaction rollback khi có exception. Hàm `append_dataframe` từ chối DataFrame rỗng và kiểm tra tên bảng trước khi insert.

## dbt assets và feature hash

Asset `airbnb_gold_dbt_assets` chạy:

```text
dbt build --select gold_price_model_features gold_cluster_model_features
```

| Gold model | Mục đích | `feature_hash` |
| --- | --- | --- |
| `gold.gold_price_model_features` | Feature train/scoring cho price model. | MD5 của đúng raw feature dùng bởi price pipeline, gồm `property_base_group` được chuẩn hóa theo cùng rule với preprocessing Python. Không gồm `listing_id`, price, log-price hay metadata. |
| `gold.gold_cluster_model_features` | Feature train/scoring cho KMeans. | MD5 của hai categorical feature và sáu numeric feature dùng bởi KMeans. Không gồm `listing_id`, price hay metadata. |

Hash được tạo với `md5(concat_ws(...))`, `coalesce(..., '__NULL__')`, và thứ tự feature cố định. `schema.yml` kiểm tra `feature_hash` không null cho cả hai model.

## MLOps và business tables

`ensure_mlops_tables()` tự tạo schema/table khi một asset ghi lần đầu. Không có migration hay rename bảng metadata cũ trong `gold`.

### Metadata trong `mlops`

| Table | Nội dung |
| --- | --- |
| `mlops.model_runs` | Mỗi run orchestration: job/model/version, loại run, trạng thái (`RUNNING`, `SUCCESS`, `FAILED`), thời gian, artifact path và lỗi nếu có. |
| `mlops.model_metrics` | Metric ở dạng long format: run, model/version, metric name/value và dataset split. |
| `mlops.model_registry` | Registry model với stage `CANDIDATE`, `CHAMPION`, `ARCHIVED`; có `is_active`, artifact/preprocessor path, người và thời gian promote. Artifact path là đường dẫn tương đối từ project root. |
| `mlops.model_feature_importance` | Global SHAP importance của price model ở hai cấp `TRANSFORMED` và `ORIGINAL`: feature nguồn, value, rank, method `shap` và model/run liên quan. |

Tên logical model trong registry là `price_model` và `segmentation_model`, tách biệt với tên thuật toán như XGBRegressor hay KMeans.

### Output nghiệp vụ trong `gold`

| Table | Nội dung |
| --- | --- |
| `gold.gold_listing_price_predictions` | Prediction evaluation hoặc batch: `listing_id`, `run_id`, `model_version`, `feature_hash`, prediction, actual/error (nếu có) và `predicted_at`. |
| `gold.gold_listing_cluster_assignments` | Cluster assignment: `listing_id`, `run_id`, `model_version`, `feature_hash`, cluster, distance và `assigned_at`. |
| `gold.gold_cluster_profiles` | Profile tổng hợp của cluster theo model version, được tạo khi segmentation retraining. |

### Các bảng Gold được orchestration tạo

`ensure_mlops_tables()` tạo ba bảng dưới đây bằng `CREATE TABLE IF NOT EXISTS`. Đây là **business output tables**; chúng không phải metadata MLOps và không tự xóa hay đổi tên các bảng Gold cũ.

| Bảng | Được ghi bởi | Hạt dữ liệu |
| --- | --- | --- |
| `gold.gold_listing_price_predictions` | `gold_price_predictions` (evaluation) và `write_price_batch_predictions` (inference batch). | Một dòng prediction cho một listing, model version và feature hash. |
| `gold.gold_listing_cluster_assignments` | `gold_listing_segments` (sau retraining) và `write_segmentation_assignments` (inference batch). | Một dòng cluster assignment cho một listing, model version và feature hash. |
| `gold.gold_cluster_profiles` | `gold_listing_segments`. | Một dòng profile cho mỗi `model_version + cluster_id`. |

Hai bảng Gold dưới đây được **dbt materialize**, không được tạo bởi Python orchestration:

| Bảng | Vai trò |
| --- | --- |
| `gold.gold_price_model_features` | Feature source cho price training và price scoring. |
| `gold.gold_cluster_model_features` | Feature source cho segmentation training và assignment scoring. |

## Candidate scoring

Hai inference job không còn đọc cố định 100 dòng. Chúng dùng query parameterized với `row_number()` để lấy result mới nhất của từng listing:

```sql
row_number() over (
    partition by listing_id
    order by predicted_at_or_assigned_at desc
)
```

Một listing là candidate nếu:

1. chưa có result trước đó;
2. result mới nhất dùng model version khác Champion;
3. `feature_hash` mới khác hash của result mới nhất.

So sánh dùng `IS DISTINCT FROM` để an toàn với `NULL`. Query ưu tiên listing mới, sau đó listing từ model cũ, rồi giới hạn `LIMIT 100`. Một anti-join lịch sử ngăn duplicate cho cùng bộ `listing_id + model_version + feature_hash`, kể cả khi feature quay về giá trị đã scoring trước đó.

Khi không có candidate, asset log rõ ràng, writer không ghi result rỗng và job hoàn thành `SUCCESS` với 0 dòng.

## Assets theo nhánh

### Price

| Asset | Tác vụ |
| --- | --- |
| `price_training_result` | Đọc toàn bộ Gold price features và gọi price retraining pipeline. |
| `price_model_artifact` | Xác minh artifact tồn tại và có `predict`. |
| `price_registry_records` | Ghi training run, long-format metric, global SHAP importance và registry Candidate vào `mlops`. |
| `gold_price_predictions` | Ghi held-out evaluation predictions có `feature_hash` vào Gold. |
| `current_price_champion` | Chọn chính xác một active Champion từ registry, rồi kiểm tra artifact. |
| `price_batch_predictions` | Tạo run metadata, chọn candidate, load pipeline artifact (gồm preprocessor) và predict. Không retrain. |
| `write_price_batch_predictions` | Ghi batch vào Gold trong transaction; cập nhật run `SUCCESS` hoặc `FAILED`. |

Sau evaluation, price retraining lấy mẫu reproducible tối đa 1.000 dòng từ `X_test`, transform bằng preprocessor đã fit và tính `TreeExplainer` trên không gian `log_price`. Artifact của mỗi price model có thêm `shap_transformed_importance.csv`, `shap_original_importance.csv`, `shap_sample_values.parquet`, `shap_sample_summary.json` và `feature_names.json`. Parquet giữ detail theo từng sample × transformed feature, gồm `listing_id`, feature value, SHAP value, direction và prediction để dashboard có thể dựng beeswarm/dependence/local explanation mà không ghi detail lớn vào MotherDuck.

### Segmentation

| Asset | Tác vụ |
| --- | --- |
| `segmentation_training_result` | Đọc toàn bộ Gold segmentation features và train KMeans pipeline. |
| `segmentation_model_artifact` | Xác minh KMeans artifact load được và có `predict`. |
| `segmentation_registry_records` | Ghi training metadata và Candidate registry vào `mlops`. |
| `gold_listing_segments` | Ghi assignment và profile của run training vào Gold trong một transaction. |
| `gold_segment_profiles` | Asset dependency đại diện cho profile đã được persist cùng assignment. |
| `current_segmentation_champion` | Chọn đúng một active Champion và kiểm tra `cluster_mapping.json`. |
| `segmentation_assignments` | Chọn tối đa 100 candidate, load persisted pipeline và gán cluster; không fit scaler, encoder hay KMeans. |
| `write_segmentation_assignments` | Ghi assignment Gold trong transaction; cập nhật trạng thái run. |

## Jobs

| Job | Flow |
| --- | --- |
| `price_retraining_job` | dbt price feature → retrain/evaluate → artifact validation → MLOps Candidate/metrics/importance → evaluation predictions. |
| `segmentation_retraining_job` | dbt cluster feature → KMeans train/evaluate → artifact validation → MLOps Candidate/metrics → assignments và profiles. |
| `price_prediction_job` | dbt price feature → active Price Champion → candidate query → tối đa 100 batch predictions → Gold output + run status. |
| `segmentation_assignment_job` | dbt cluster feature → active Segmentation Champion → candidate query → tối đa 100 assignments → Gold output + run status. |

## Asset checks

| Check | Điều kiện |
| --- | --- |
| `price_training_check` | Artifact tồn tại, RMSE hữu hạn, predictions hợp lệ và không âm. |
| `segmentation_training_check` | Artifact tồn tại, listing duy nhất, cluster id/tên/version hợp lệ. |
| `price_prediction_check` | Batch rỗng được xem là hợp lệ; nếu có dữ liệu, listing duy nhất, một version, hash không null và giá hợp lệ. |
| `segmentation_assignment_check` | Batch rỗng được xem là hợp lệ; nếu có dữ liệu, listing/hash/version/cluster hợp lệ. |

Checks chỉ đọc và đánh giá output, không sửa artifact hay dữ liệu.

## Promote Champion

Promotion hiện chưa có Streamlit control. SQL transaction mẫu nằm trong `README.md`: archive Champion cũ cùng `model_name`, sau đó đổi Candidate được chọn thành `CHAMPION`, `is_active = TRUE`, kèm `promoted_at` và `promoted_by`.

Trước khi chạy inference, xác nhận mỗi `model_name` chỉ có một record active Champion. Nếu thiếu hoặc có nhiều hơn một, inference dừng với lỗi rõ ràng.

## Vận hành và kiểm tra

```bash
# Build feature models sau khi Bronze/Silver đã tồn tại trong database target
uv run dbt build --project-dir dbt --profiles-dir dbt --target local --select +gold_price_model_features +gold_cluster_model_features

# Mở Dagster UI và chạy một trong bốn job
uv run dagster dev -m orchestration.definitions

# Unit test registry selection, candidate SQL và Dagster topology
uv run python -m unittest tests.test_orchestration_inference
```

Database target phải có nguồn Bronze/Silver trước khi chạy dbt; orchestration không thực hiện ingestion.
