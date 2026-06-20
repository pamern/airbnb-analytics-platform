Hãy tích hợp Dagster vào repository để điều phối hai pipeline Machine Learning hiện có:

* `price_modeling`
* `listing_segmentation`

Các pipeline ML đã được module hóa trong `ml/` và phải tiếp tục là nơi chứa toàn bộ logic xử lý dữ liệu, training, evaluation, prediction, artifact và metadata. Dagster chỉ chịu trách nhiệm orchestration.

## 0. Mục tiêu

Xây dựng lớp orchestration bằng Dagster để:

* chạy dbt Gold model cần thiết;
* đọc feature table từ MotherDuck;
* truyền DataFrame vào pipeline ML;
* train hoặc retrain model;
* lưu artifact;
* ghi metadata model;
* ghi metric;
* ghi prediction hoặc cluster assignment;
* kiểm tra chất lượng đầu ra;
* cho phép chạy thủ công từng pipeline từ Dagster UI.

Trong nhiệm vụ này:

* chưa tạo schedule tự động;
* chưa tạo sensor;
* chưa tự động retrain theo drift;
* chưa triển khai production deployment;
* không commit;
* không push.

---

# 1. Bắt buộc dùng CodeGraph trước

Trước khi chỉnh sửa:

1. Dùng CodeGraph khảo sát:

   * `ml/common/`
   * `ml/price_modeling/`
   * `ml/listing_segmentation/`
   * thư mục Dagster hiện có nếu có;
   * `dbt/models/gold/`
   * `pyproject.toml`
   * các script chạy pipeline hiện tại.
2. Xác định:

   * entry point của price pipeline;
   * entry point của segmentation pipeline;
   * kiểu dữ liệu đầu vào;
   * kiểu `TrainingResult` đầu ra;
   * cách lưu artifact;
   * cách tạo run ID và model version;
   * schema metadata;
   * dependency với dbt;
   * các kết nối MotherDuck hiện có.
3. Tìm tất cả reference tới:

   * `gold_price_model_features`;
   * feature table của segmentation;
   * `gold_ml_training_runs`;
   * `gold_ml_model_registry`;
   * `gold_ml_model_metrics`;
   * `gold_price_predictions`;
   * `gold_listing_segments`;
   * `gold_segment_profiles`.
4. Chỉ đọc sâu các file thực sự liên quan sau khi có kết quả từ CodeGraph.

Không dựa hoàn toàn vào CodeGraph đối với YAML, SQL, notebook và cấu hình. Phải đọc file gốc trước khi sửa.

---

# 2. Quy trình thực hiện bắt buộc

Thực hiện thành hai giai đoạn.

## Giai đoạn 1: Phân tích, chưa sửa code

1. Khảo sát repository bằng CodeGraph.
2. Đọc các module ML và dbt liên quan.
3. Xác định:

   * Dagster đã được cài chưa;
   * cấu trúc orchestration hiện tại;
   * resource nào đã tồn tại;
   * schema MotherDuck hiện tại;
   * dbt project path;
   * cách truyền DataFrame vào ML pipeline;
   * cách ghi kết quả trở lại database.
4. Đề xuất:

   * file cần tạo;
   * file cần sửa;
   * asset graph;
   * resource;
   * job;
   * asset check;
   * cách test.
5. Dừng lại sau khi trình bày kế hoạch.
6. Không sửa file trong giai đoạn này.

Chỉ triển khai sau khi người dùng chấp thuận.

## Giai đoạn 2: Triển khai

Sau khi được chấp thuận:

1. Tạo lớp resource.
2. Tạo dbt assets.
3. Tạo price assets.
4. Tạo segmentation assets.
5. Tạo registry writer.
6. Tạo asset checks.
7. Tạo jobs.
8. Tạo `Definitions`.
9. Chạy import check.
10. Chạy Dagster dev server.
11. Materialize thủ công từng pipeline.
12. Báo cáo kết quả.

---

# 3. Nguyên tắc kiến trúc

Dagster không được chứa logic ML.

Không viết lại trong Dagster:

* preprocessing;
* feature engineering;
* training;
* tuning;
* evaluation;
* error analysis;
* explainability;
* cluster profiling;
* prediction logic.

Dagster chỉ được:

* gọi dbt;
* đọc dữ liệu;
* truyền DataFrame;
* gọi entry point ML;
* ghi kết quả;
* quản lý dependency;
* log;
* kiểm tra output;
* quản lý run status.

Luồng đúng:

```text
Dagster asset
→ MotherDuck/dbt resource
→ DataFrame
→ ml.price_modeling hoặc ml.listing_segmentation
→ TrainingResult
→ artifact + database records
```

Không để module trong `ml/` import ngược Dagster.

---

# 4. Cấu trúc thư mục định hướng

Ưu tiên cấu trúc:

```text
orchestration/
├── __init__.py
├── definitions.py
│
├── resources/
│   ├── __init__.py
│   ├── motherduck.py
│   └── dbt.py
│
├── assets/
│   ├── __init__.py
│   ├── dbt_assets.py
│   ├── price_assets.py
│   ├── segmentation_assets.py
│   └── registry_assets.py
│
├── checks/
│   ├── __init__.py
│   ├── price_checks.py
│   └── segmentation_checks.py
│
└── jobs/
    ├── __init__.py
    ├── price_job.py
    ├── segmentation_job.py
    └── full_ml_job.py
```

Đây là định hướng, không bắt buộc tạo file rỗng.

Không tạo module nếu trách nhiệm quá nhỏ hoặc có thể gộp hợp lý.

Nếu repository đã có cấu trúc Dagster khác, ưu tiên mở rộng cấu trúc hiện có thay vì tạo song song.

---

# 5. MotherDuck resource

Tạo resource riêng cho MotherDuck.

Yêu cầu:

* đọc token hoặc connection string từ environment variable;
* không hard-code secret;
* không log token;
* quản lý connection an toàn;
* đóng connection đúng cách;
* hỗ trợ:

  * query thành DataFrame;
  * execute SQL;
  * append DataFrame;
  * transaction;
  * upsert khi thực sự cần.
* dùng type hints và docstring;
* xử lý lỗi rõ ràng.

API định hướng:

```python
class MotherDuckResource(ConfigurableResource):
    def query_df(self, sql: str, parameters: Sequence[Any] | None = None) -> pd.DataFrame:
        ...

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None:
        ...

    def append_dataframe(self, table_name: str, df: pd.DataFrame) -> None:
        ...
```

Không đặt logic nghiệp vụ trong resource.

Không tự động kết nối khi import module.

---

# 6. dbt resource và dbt assets

Tích hợp dbt theo cách phù hợp với repository hiện tại.

Nếu đã dùng `dagster-dbt`, ưu tiên dùng `DbtCliResource` và `@dbt_assets`.

Nếu chưa có dependency nhưng repository đã có Dagster, chỉ thêm dependency cần thiết sau khi kiểm tra `pyproject.toml`.

Các Gold model đầu vào tối thiểu:

```text
gold_price_model_features
gold_segmentation_model_features
```

Nếu bảng segmentation dùng tên khác, phải đọc code và dbt hiện tại để xác định đúng tên. Không tự đặt tên mới nếu chưa tồn tại.

Yêu cầu:

* dbt project path lấy từ cấu hình;
* profiles path lấy từ cấu hình;
* không hard-code path tuyệt đối;
* hỗ trợ Windows;
* Dagster phải biết dependency từ dbt asset tới ML asset;
* không chạy toàn bộ dbt project nếu chỉ cần một số Gold model.

Có thể dùng selection rõ ràng:

```text
gold_price_model_features
gold_segmentation_model_features
```

Không thêm schedule ở bước này.

---

# 7. Price pipeline assets

Tạo asset graph định hướng:

```text
gold_price_model_features
        ↓
price_training_result
        ↓
price_model_artifact
        ↓
price_registry_records
        ↓
gold_price_predictions
```

Có thể gộp asset nếu tách nhỏ làm tăng phức tạp không cần thiết.

## `price_training_result`

Asset này phải:

1. Đọc dữ liệu từ `gold_price_model_features`.
2. Validate DataFrame không rỗng.
3. Truyền DataFrame vào:

```python
run_price_training_pipeline(
    data=df,
    config=config,
    training_mode="retrain",
)
```

4. Mặc định chỉ retrain champion model.
5. Không chạy:

   * baseline comparison;
   * research mode;
   * nhiều model family;
   * feature selection;
   * tuning.
6. Trả về `TrainingResult`.

Không copy logic ML vào asset.

## `price_model_artifact`

Nếu artifact đã được lưu trong ML pipeline, asset chỉ:

* kiểm tra artifact tồn tại;
* kiểm tra load lại được;
* trả về metadata artifact.

Không lưu model lần hai.

## `price_registry_records`

Chuyển `TrainingResult` thành các record:

```text
gold_ml_training_runs
gold_ml_model_registry
gold_ml_model_metrics
```

Phải tái sử dụng helper trong `ml/common/model_registry.py`.

Không dựng lại schema thủ công nếu helper đã tồn tại.

## `gold_price_predictions`

Ghi prediction cần thiết vào bảng:

```text
gold_price_predictions
```

Schema phải được đọc từ code hoặc dbt hiện tại.

Tối thiểu nên có:

```text
model_version
listing_id
actual_price
predicted_price
actual_log_price
predicted_log_price
residual
absolute_error
prediction_date
```

Không ghi toàn bộ dữ liệu trung gian không cần thiết.

---

# 8. Segmentation pipeline assets

Tạo asset graph định hướng:

```text
gold_segmentation_model_features
        ↓
segmentation_training_result
        ↓
segmentation_model_artifact
        ↓
segmentation_registry_records
        ↓
gold_listing_segments
        ↓
gold_segment_profiles
```

## `segmentation_training_result`

Asset phải:

1. Đọc dữ liệu feature.
2. Validate schema.
3. Gọi đúng entry point:

```python
run_segmentation_training_pipeline(
    data=df,
    config=config,
)
```

4. Giữ nguyên:

   * algorithm;
   * n_clusters;
   * random seed;
   * feature set;
   * preprocessing;
   * cluster mapping.
5. Trả về `TrainingResult`.

Không chạy lại nghiên cứu chọn số cluster.

## `segmentation_model_artifact`

Chỉ kiểm tra artifact đã được tạo và load lại được.

## `segmentation_registry_records`

Ghi metadata dùng chung vào:

```text
gold_ml_training_runs
gold_ml_model_registry
gold_ml_model_metrics
```

`model_task` phải là:

```text
listing_segmentation
```

## `gold_listing_segments`

Tối thiểu:

```text
listing_id
model_version
cluster_id
cluster_name
distance_to_centroid
assigned_at
```

## `gold_segment_profiles`

Tối thiểu:

```text
model_version
cluster_id
cluster_name
listing_count
created_at
```

Chỉ thêm các KPI profile thực sự có trong pipeline hiện tại.

---

# 9. Ghi dữ liệu vào MotherDuck

Việc ghi dữ liệu phải:

* dùng transaction khi nhiều bảng liên quan;
* tránh trạng thái ghi một nửa;
* validate schema trước khi ghi;
* log số dòng;
* không ghi khi DataFrame rỗng;
* không ghi record `CHAMPION` nếu training thất bại;
* không ghi artifact không hoàn chỉnh;
* không hard-code database name hoặc schema nếu đã có config.

## Chiến lược ghi

Đối với bảng lịch sử:

```text
gold_ml_training_runs
gold_ml_model_registry
gold_ml_model_metrics
```

Ưu tiên append theo:

* `run_id`;
* `model_version`.

Phải chống trùng khóa.

Đối với kết quả theo model version:

```text
gold_price_predictions
gold_listing_segments
gold_segment_profiles
```

Có thể:

* append theo `model_version`;
* hoặc delete chính model version rồi insert lại trong cùng transaction.

Không xóa kết quả model version cũ.

---

# 10. Trạng thái model

Sử dụng trạng thái đã chuẩn hóa:

```text
CANDIDATE
CHAMPION
REJECTED
ARCHIVED
```

Trong giai đoạn đầu:

* model mới tạo là `CANDIDATE`;
* chưa tự động promote thành `CHAMPION` nếu chưa có rule rõ ràng;
* nếu code hiện tại đã có logic champion–challenger, tái sử dụng logic đó;
* không tự sáng tạo tiêu chí promote mới.

Nếu chưa có cơ chế promote, giữ model mới ở `CANDIDATE` và ghi rõ trong báo cáo.

Không để nhiều model `CHAMPION` cho cùng `model_task`.

---

# 11. Asset checks

Tạo asset checks tối thiểu.

## Price checks

Kiểm tra:

1. Feature table không rỗng.
2. Có đủ required columns.
3. `listing_id` không null.
4. Target hợp lệ.
5. Artifact tồn tại.
6. Artifact load được.
7. Metrics không null.
8. RMSE hữu hạn.
9. Prediction không NaN hoặc infinity.
10. Không có predicted price âm.
11. Có đúng một model version trong batch output.

## Segmentation checks

Kiểm tra:

1. Feature table không rỗng.
2. Có đủ required columns.
3. `listing_id` không null.
4. `listing_id` không trùng nếu pipeline yêu cầu unique.
5. Artifact tồn tại.
6. Artifact load được.
7. Metrics hữu hạn.
8. Số cluster đúng config.
9. Không có cluster ID ngoài phạm vi.
10. Mỗi listing có đúng một cluster.
11. Cluster mapping không rỗng.
12. Có đúng một model version trong batch output.

Check không được sửa dữ liệu.

---

# 12. Jobs

Tạo ba job:

```text
price_retraining_job
segmentation_retraining_job
full_ml_pipeline_job
```

## `price_retraining_job`

Chỉ materialize:

* Gold feature cần thiết;
* price training;
* price artifact;
* price registry;
* price predictions;
* price checks.

## `segmentation_retraining_job`

Chỉ materialize:

* Gold feature cần thiết;
* segmentation training;
* artifact;
* registry;
* assignments;
* profiles;
* checks.

## `full_ml_pipeline_job`

Chạy cả hai pipeline.

Không tạo schedule trong nhiệm vụ này.

Không tự chạy job khi import.

---

# 13. Definitions

Tạo `Definitions` tập trung:

```python
defs = Definitions(
    assets=[...],
    asset_checks=[...],
    jobs=[...],
    resources={
        "motherduck": ...,
        "dbt": ...,
    },
)
```

Không tạo nhiều `Definitions` cạnh tranh nếu repository chỉ cần một entry point.

Entry point phải rõ để chạy:

```bash
dagster dev -m orchestration.definitions
```

Nếu repository dùng `dg` hoặc cấu trúc Dagster khác, dùng đúng convention hiện tại.

---

# 14. Logging

Dagster asset phải log:

* asset name;
* run ID;
* model version;
* model task;
* algorithm;
* số dòng đọc;
* số dòng ghi;
* artifact URI;
* metric chính;
* thời gian train;
* trạng thái.

Không log:

* token;
* secret;
* full DataFrame;
* toàn bộ hyperparameter dài không cần thiết;
* dữ liệu cá nhân.

---

# 15. Xử lý lỗi

Nếu pipeline ML lỗi:

* Dagster asset phải fail rõ ràng;
* giữ exception gốc;
* không ghi model registry thành công;
* không ghi prediction hoặc cluster output;
* không promote model;
* có thể ghi một record training run trạng thái `FAILED` nếu transaction và thiết kế cho phép.

Nếu dbt thất bại:

* không chạy ML asset downstream.

Nếu artifact không tồn tại sau training:

* asset phải fail.

Nếu ghi một trong các bảng output thất bại:

* rollback transaction liên quan.

---

# 16. Kiểm thử

Không chạy schedule.

Thực hiện kiểm thử theo thứ tự:

## 16.1 Import check

```bash
python -c "import orchestration.definitions"
```

## 16.2 Definitions load

Kiểm tra Dagster có load được:

```bash
dagster definitions validate -m orchestration.definitions
```

Nếu phiên bản Dagster hiện tại không có lệnh này, dùng lệnh tương đương được hỗ trợ.

## 16.3 Dev server

```bash
dagster dev -m orchestration.definitions
```

Kiểm tra:

* UI load được;
* assets xuất hiện;
* dependency đúng;
* jobs xuất hiện;
* resources load được.

## 16.4 Materialize price thủ công

Chạy `price_retraining_job`.

Kiểm tra:

* dbt Gold model thành công;
* DataFrame được đọc;
* champion model được retrain;
* artifact được tạo;
* metadata được ghi;
* predictions được ghi;
* checks pass.

## 16.5 Materialize segmentation thủ công

Chạy `segmentation_retraining_job`.

Kiểm tra:

* feature table;
* model training;
* artifact;
* assignments;
* profiles;
* registry;
* checks.

## 16.6 Full pipeline

Chỉ chạy sau khi hai job riêng đã pass.

---

# 17. Dependency

Kiểm tra `pyproject.toml` trước khi thêm dependency.

Có thể cần:

```text
dagster
dagster-webserver
dagster-dbt
duckdb
```

Chỉ thêm package thiếu thực sự.

Sau khi sửa:

```bash
uv lock
uv sync
```

Không tự nâng version các package không liên quan.

Không thay đổi toàn bộ lockfile ngoài phần dependency cần thiết.

---

# 18. Không làm trong nhiệm vụ này

Không:

* thêm schedule;
* thêm sensor;
* thêm drift detection;
* thêm automatic retraining;
* thêm automatic champion promotion nếu chưa có rule;
* thêm MLflow;
* thêm Docker;
* thêm CI/CD;
* thêm Kubernetes;
* thêm cloud deployment;
* sửa thuật toán ML;
* chạy lại research mode;
* tuning lại model;
* chọn lại n_clusters;
* thay đổi dbt model nghiệp vụ ngoài phần cần thiết;
* sửa notebook không liên quan;
* commit;
* push.

---

# 19. Báo cáo cuối cùng

Sau khi triển khai, báo cáo:

1. CodeGraph xác định dependency gì.
2. File tạo mới.
3. File sửa.
4. File giữ nguyên.
5. Cấu trúc orchestration cuối cùng.
6. Asset graph của price.
7. Asset graph của segmentation.
8. Resources đã tạo.
9. Jobs đã tạo.
10. Asset checks đã tạo.
11. Bảng nào được đọc.
12. Bảng nào được ghi.
13. Chiến lược transaction.
14. Cách chạy Dagster UI.
15. Cách chạy price job.
16. Cách chạy segmentation job.
17. Cách chạy full job.
18. Test nào đã pass.
19. Test nào chưa chạy.
20. Có thay đổi logic ML hay không.
21. Có thay đổi metric hay không.
22. Rủi ro còn lại.
23. Schedule chưa được tạo và lý do.

Ưu tiên:

* orchestration mỏng;
* ML logic nằm trong `ml/`;
* resource tách biệt;
* asset dependency rõ;
* chạy thủ công trước;
* không over-engineer;
* không thêm schedule quá sớm;
* không làm thay đổi kết quả mô hình.
