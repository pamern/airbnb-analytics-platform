Hãy tái cấu trúc phần `listing_segmentation` của repository theo cùng quy ước kiến trúc đã áp dụng cho `price_modeling`, nhưng phải giữ nguyên thuật toán, preprocessing, số cluster, kết quả clustering và logic nghiệp vụ hiện tại.

## 0. Mục tiêu

Mục tiêu chính:

* chuẩn hóa cấu trúc module Python;
* chuẩn hóa output và artifact;
* tái sử dụng đúng các helper trong `ml/common`;
* tạo metadata tương thích với:

  * `gold_ml_training_runs`;
  * `gold_ml_model_registry`;
  * `gold_ml_model_metrics`;
* chuẩn hóa kết quả cluster để truy vết theo `model_version`;
* chuẩn bị cho việc tích hợp Dagster sau này.

Không được:

* viết lại toàn bộ clustering;
* thay đổi thuật toán;
* thay đổi số cluster;
* thay đổi feature;
* thay đổi preprocessing;
* thay đổi random seed;
* thay đổi cách đặt tên cluster;
* thay đổi kết quả hiện tại nếu không thực sự cần thiết;
* tích hợp Dagster trong nhiệm vụ này;
* kết nối hoặc đọc MotherDuck;
* commit hoặc push.

---

# 1. Phạm vi nhiệm vụ

Phạm vi chính:

* `ml/listing_segmentation/`
* notebook hoặc script đang chạy clustering;
* `ml/outputs/listing_segmentation/`
* `ml/artifacts/listing_segmentation/`
* `ml/common/`

Chỉ khảo sát để đảm bảo tương thích:

* `ml/price_modeling/`
* `dbt/models/gold/`
* `pyproject.toml`
* test và cấu hình liên quan.

Không sửa `price_modeling` trừ khi phát hiện lỗi trực tiếp trong helper dùng chung và thay đổi đó phải được nêu rõ trước.

---

# 2. Bắt buộc dùng CodeGraph trước

Trước khi chỉnh sửa:

1. Dùng CodeGraph lập bản đồ:

   * `ml/listing_segmentation/`;
   * notebook hoặc script đang gọi pipeline clustering;
   * `ml/common/`;
   * các reference tới output và artifact clustering.
2. Xác định:

   * import hiện tại;
   * dependency giữa notebook, script và module;
   * nơi đang lưu model;
   * nơi đang lưu scaler hoặc preprocessor;
   * nơi đang sinh cluster assignment;
   * nơi đang sinh cluster profile;
   * nơi đang lưu metric;
   * nguy cơ circular import;
   * nguy cơ breaking change.
3. Tìm tất cả reference tới:

   * `ml/outputs/listing_segmentation`;
   * `ml/artifacts/listing_segmentation`;
   * `gold_listing_segments`;
   * `gold_segment_profiles`;
   * file notebook hoặc script clustering;
   * các file `.joblib` hiện có.
4. Chỉ mở chi tiết những file thực sự liên quan sau khi đã có kết quả từ CodeGraph.

Không dựa hoàn toàn vào CodeGraph đối với:

* notebook cell;
* YAML;
* SQL;
* JSON;
* cấu hình;
* file output.

Phải đọc file gốc trước khi sửa.

---

# 3. Tuyệt đối không truy cập MotherDuck

Trong toàn bộ nhiệm vụ này, không được:

* kết nối MotherDuck;
* dùng token MotherDuck;
* gọi `duckdb.connect()` tới remote database;
* chạy SQL trên MotherDuck;
* tải dữ liệu Gold;
* đọc warehouse;
* chạy dbt để lấy dữ liệu;
* kiểm tra schema bằng query database;
* gọi API hoặc dịch vụ từ xa.

Chỉ được dùng:

* code local;
* notebook local;
* metadata local;
* CSV hoặc JSON local nhỏ;
* synthetic DataFrame;
* fixture;
* schema từ code hoặc dbt YAML local.

Nếu thiếu dữ liệu để xác minh đầy đủ, phải ghi rõ giới hạn thay vì tự suy đoán.

---

# 4. Quy trình bắt buộc

Thực hiện thành hai giai đoạn.

## Giai đoạn 1: Phân tích, chưa sửa code

1. Dùng CodeGraph khảo sát repository.
2. Đọc các file liên quan.
3. Phân loại logic hiện tại thành:

   * cấu hình;
   * đọc dữ liệu;
   * validation;
   * preprocessing;
   * feature engineering;
   * lựa chọn số cluster;
   * training;
   * evaluation;
   * gán cluster;
   * đặt tên cluster;
   * cluster profile;
   * visualization;
   * lưu output;
   * lưu artifact.
4. Liệt kê:

   * file hiện tại và trách nhiệm;
   * logic đang nằm trong notebook;
   * logic đã nằm trong Python module;
   * file cần tạo;
   * file cần sửa;
   * file giữ nguyên;
   * helper nào có thể tái sử dụng từ `ml/common`;
   * nguy cơ thay đổi kết quả.
5. Đề xuất cấu trúc tối thiểu.
6. Dừng lại sau khi trình bày kế hoạch.
7. Không chỉnh sửa file trong giai đoạn này.

Chỉ triển khai sau khi người dùng chấp thuận.

## Giai đoạn 2: Triển khai

Sau khi kế hoạch được chấp thuận:

1. Chuẩn hóa module.
2. Tách logic khỏi notebook nếu cần.
3. Chuẩn hóa path.
4. Chuẩn hóa artifact.
5. Chuẩn hóa output.
6. Chuẩn hóa metadata.
7. Chỉnh notebook hoặc script thành thin runner.
8. Chạy import check.
9. Chạy smoke test với synthetic data hoặc local sample nhỏ.
10. Báo cáo kết quả.

---

# 5. Nguyên tắc bắt buộc

1. Không đổi thuật toán clustering.
2. Không đổi số cluster đã chốt.
3. Không đổi random seed.
4. Không đổi feature set.
5. Không đổi preprocessing.
6. Không đổi scaler hoặc encoder hiện tại.
7. Không đổi cách gán cluster.
8. Không đổi cách đặt tên cluster nếu đang có.
9. Không đổi metric chính.
10. Không làm thay đổi cluster assignment ngoài sai số hợp lý nếu thuật toán có tính ngẫu nhiên nhưng đã khóa seed.
11. Không viết lại toàn bộ notebook.
12. Không xóa output lịch sử.
13. Không ghi đè artifact cũ.
14. Không hard-code đường dẫn tuyệt đối.
15. Không thêm dependency mới nếu không cần.
16. Không để code tự chạy khi import.
17. Dùng type hints và docstring cho public function.
18. Dùng `logging`, không dùng `print` trong module lõi.
19. Phải chạy được từ root repository trên Windows.
20. Không sửa file ngoài phạm vi nếu không có lý do trực tiếp.
21. Không tự động format hoặc rewrite file không liên quan.
22. Nếu logic chưa đủ rõ để tách an toàn, giữ nguyên và ghi chú.

---

# 6. Cấu trúc thư mục định hướng

Đây là định hướng, không phải danh sách file bắt buộc:

```text
ml/
├── common/
│   ├── __init__.py
│   ├── paths.py
│   ├── artifact_manager.py
│   ├── run_manager.py
│   └── model_registry.py
│
├── listing_segmentation/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── preprocessing.py
│   ├── training.py
│   ├── evaluation.py
│   ├── prediction.py
│   ├── profiles.py
│   ├── visualization.py
│   └── pipeline.py
│
├── artifacts/
│   └── listing_segmentation/
│
└── outputs/
    └── listing_segmentation/
        ├── charts/
        ├── csv/
        ├── metadata/
        └── profiles/
```

Không tạo module nếu:

* chỉ có một hàm rất nhỏ;
* trách nhiệm chưa rõ;
* logic chưa tồn tại;
* làm tăng circular import;
* không được pipeline dùng;
* có thể gộp hợp lý vào module khác.

Ưu tiên ít module nhưng rõ trách nhiệm.

---

# 7. Tái sử dụng `ml/common`

Ưu tiên tái sử dụng:

* `ml.common.paths`;
* `ml.common.artifact_manager`;
* `ml.common.run_manager`;
* `ml.common.model_registry`.

Không copy lại code chung vào `listing_segmentation`.

Chỉ dùng common cho phần thực sự dùng chung:

* path;
* versioning;
* run ID;
* model version;
* artifact save/load;
* metadata record;
* registry record;
* metric record.

Không đưa vào common:

* logic KMeans;
* cluster naming;
* centroid analysis;
* segmentation feature engineering;
* cluster profile;
* metric riêng của clustering.

Nếu `ml/common` chưa đủ tổng quát, chỉ mở rộng tối thiểu và không làm hỏng `price_modeling`.

---

# 8. `config.py`

Chứa cấu hình bất biến:

* `model_task = "listing_segmentation"`;
* random seed;
* algorithm;
* số cluster đã chốt;
* feature list;
* feature set version;
* metric chính;
* metric phụ;
* đường dẫn output;
* đường dẫn artifact;
* các cờ tùy chọn.

Ví dụ:

```python
@dataclass(frozen=True)
class SegmentationConfig:
    model_task: str = "listing_segmentation"
    algorithm: str = "KMeans"
    n_clusters: int = 5
    random_state: int = 42
    feature_set_version: str = "segment_features_v001"
```

Không đặt trong config:

* DataFrame;
* fitted model;
* fitted scaler;
* database connection;
* MotherDuck token;
* code có side effect.

---

# 9. `data.py`

Chịu trách nhiệm:

* nhận DataFrame từ caller;
* hoặc đọc local CSV khi explicit path được truyền;
* validate cột bắt buộc;
* kiểm tra DataFrame rỗng;
* kiểm tra duplicate columns;
* kiểm tra listing ID;
* trả về DataFrame chuẩn hóa nhẹ.

Không được:

* kết nối MotherDuck;
* chạy SQL;
* đọc Gold table;
* tải dữ liệu internet;
* ghi output;
* thực hiện clustering.

API dự kiến:

```python
load_local_segmentation_data(path: Path) -> pd.DataFrame
validate_segmentation_schema(
    df: pd.DataFrame,
    required_columns: Sequence[str],
) -> None
```

Pipeline phải hỗ trợ:

```python
run_segmentation_pipeline(
    data=df,
    config=config,
)
```

---

# 10. `preprocessing.py`

Tách đúng preprocessing hiện tại:

* chọn feature;
* imputation;
* scaling;
* encoding;
* feature engineering;
* xử lý categorical;
* lấy tên feature sau transform;
* tạo sklearn preprocessor hoặc pipeline.

API dự kiến:

```python
prepare_segmentation_frame(...)
build_segmentation_preprocessor(...)
get_transformed_feature_names(...)
```

Không thay đổi:

* scaler;
* encoder;
* cách xử lý missing;
* feature engineering;
* thứ tự feature;
* random seed.

Không fit trên dữ liệu ngoài input được caller cung cấp.

---

# 11. `training.py`

Chứa logic training clustering.

API dự kiến:

```python
build_segmentation_estimator(...)
build_segmentation_pipeline(...)
train_segmentation_model(...)
```

Phải tạo đúng:

* thuật toán hiện tại;
* số cluster hiện tại;
* random seed hiện tại;
* hyperparameter hiện tại.

Ưu tiên lưu preprocessor và clustering model trong cùng sklearn Pipeline nếu tương thích với logic hiện tại.

Không tự:

* ghi database;
* promote model;
* chạy notebook;
* sinh chart;
* ghi output;
* chạy pipeline toàn phần.

---

# 12. `evaluation.py`

Tách metric clustering hiện tại.

Metric có thể gồm:

* silhouette score;
* Davies–Bouldin score;
* Calinski–Harabasz score;
* inertia;
* cluster count.

API dự kiến:

```python
evaluate_segmentation_model(...)
build_segmentation_metrics_long_format(...)
```

Schema metric tối thiểu:

```text
model_version
dataset_type
metric_name
metric_value
metric_std
evaluated_at
```

Không tạo metric giả.

Không so sánh metric clustering với metric price prediction.

Không tự ghi MotherDuck.

---

# 13. `prediction.py`

Cung cấp API gán cluster cho listing mới hoặc batch mới.

API dự kiến:

```python
load_segmentation_model(...)
validate_segmentation_input(...)
assign_clusters(...)
```

Kết quả tối thiểu:

```text
listing_id
model_version
cluster_id
cluster_name
distance_to_centroid
assigned_at
```

Yêu cầu:

* nhận DataFrame hoặc dictionary hợp lệ;
* dùng đúng preprocessor đã fit;
* không fit lại model;
* không đổi cluster labels;
* không kết nối database;
* không phụ thuộc notebook.

Nếu model hiện tại không hỗ trợ `distance_to_centroid`, hãy dùng phương pháp hiện có hoặc ghi rõ chưa hỗ trợ, không tự suy đoán.

---

# 14. `profiles.py`

Tách logic tạo cluster profile hiện tại.

API dự kiến:

```python
build_cluster_assignments(...)
build_cluster_profiles(...)
apply_cluster_names(...)
```

Schema `gold_listing_segments` dự kiến:

```text
listing_id
model_version
cluster_id
cluster_name
distance_to_centroid
assigned_at
```

Schema `gold_segment_profiles` dự kiến:

```text
model_version
cluster_id
cluster_name
listing_count
median_price
avg_price
avg_accommodates
avg_rating
avg_availability_365
dominant_room_type
dominant_neighbourhood
created_at
```

Chỉ giữ các cột profile thực sự có trong logic hiện tại.

Không tự tạo thêm KPI không có cơ sở.

Không ghi MotherDuck.

Chỉ trả về DataFrame hoặc dictionary.

---

# 15. `visualization.py`

Chỉ chứa logic visualization nếu hiện tại đang có nhiều hàm vẽ.

Ví dụ:

```python
plot_cluster_distribution(...)
plot_cluster_profiles(...)
plot_pca_projection(...)
```

Không trộn:

* plotting;
* training;
* metric calculation;
* artifact saving;
* database writing.

Không bắt buộc tạo module này nếu plotting hiện tại ít.

---

# 16. `pipeline.py`

Đây là entry point chính.

API dự kiến:

```python
run_segmentation_training_pipeline(...)
run_segmentation_assignment_pipeline(...)
run_segmentation_profile_pipeline(...)
```

Training flow:

```text
receive DataFrame
→ validate schema
→ preprocess
→ build estimator
→ train
→ assign clusters
→ evaluate
→ build cluster profiles
→ save artifact
→ build TrainingResult
```

Ví dụ:

```python
run_segmentation_training_pipeline(
    data: pd.DataFrame,
    config: SegmentationConfig,
)
```

Không:

* đọc MotherDuck;
* chạy dbt;
* chạy notebook;
* ghi Gold table;
* thay đổi thuật toán;
* thay đổi số cluster.

CLI nếu có:

```bash
python -m ml.listing_segmentation.pipeline \
  --input path/to/local_sample.csv
```

Không có default đọc MotherDuck.

---

# 17. Artifact management

Artifact deployable lưu tại:

```text
ml/artifacts/listing_segmentation/<model_version>/
```

Ví dụ:

```text
segment_v001/
├── model.joblib
├── feature_schema.json
├── training_config.json
├── metrics.json
└── cluster_mapping.json
```

Nếu preprocessor không nằm trong cùng pipeline:

```text
segment_v001/
├── model.joblib
├── preprocessor.joblib
├── feature_schema.json
├── training_config.json
├── metrics.json
└── cluster_mapping.json
```

Yêu cầu:

* không ghi đè version cũ;
* dùng helper trong `ml/common/artifact_manager.py`;
* JSON UTF-8;
* serialize numpy scalar;
* kiểm tra load lại được;
* assignment trước và sau load phải nhất quán;
* giữ artifact cũ nguyên trạng.

Không lưu vào artifact:

* PNG;
* CSV phân tích;
* full dataset;
* notebook output;
* cluster assignment toàn bộ nếu đã có output riêng.

---

# 18. Output management

Chuẩn hóa output tại:

```text
ml/outputs/listing_segmentation/
├── charts/
├── csv/
├── metadata/
└── profiles/
```

Ví dụ:

```text
csv/
├── cluster_assignments.csv
├── segmentation_metrics.csv
└── cluster_summary.csv

profiles/
└── cluster_profiles.csv

metadata/
├── training_run_metadata.json
└── model_registry_record.json
```

Không di chuyển hàng loạt file cũ nếu có nguy cơ phá reference.

Không xóa output lịch sử.

Không ghi đè output cũ nếu chưa có version hoặc timestamp.

Nếu đổi path:

* cập nhật reference;
* giữ compatibility nếu cần;
* báo cáo rõ thay đổi.

---

# 19. Run metadata và model registry

Tái sử dụng các dataclass hoặc helper đã có trong `ml/common`:

```python
TrainingRun
RegisteredModel
ModelMetric
TrainingResult
```

`TrainingResult` có thể chứa:

```python
run
model
metrics
artifact_paths
assignments
profiles
```

Tạo record tương thích:

```text
gold_ml_training_runs
gold_ml_model_registry
gold_ml_model_metrics
```

Ví dụ:

```python
build_training_run_record(...)
build_model_registry_record(...)
build_model_metric_records(...)
```

Trong nhiệm vụ này:

* chỉ trả về DataFrame/dictionary;
* có thể export JSON hoặc CSV local;
* không insert MotherDuck;
* không tạo bảng;
* không chạy dbt;
* không promote production tự động.

`model_task` phải là:

```text
listing_segmentation
```

---

# 20. Model version và run ID

Sử dụng quy ước rõ ràng:

```text
run_segment_YYYYMMDD_HHMMSS
segment_v001
segment_v002
```

Không hard-code version nếu helper common đã có cách sinh version.

Mỗi artifact và output mới phải liên kết được với:

* `run_id`;
* `model_version`;
* `feature_set_version`;
* algorithm;
* created_at.

Không đổi version artifact cũ.

---

# 21. Chỉnh notebook hoặc script hiện tại

Sau khi module hóa:

* giữ markdown;
* giữ thứ tự phân tích;
* giữ kết luận;
* giữ visualization quan trọng;
* thay implementation lặp bằng import;
* notebook chỉ điều phối và hiển thị;
* không chứa lại toàn bộ logic;
* không rewrite toàn bộ notebook JSON;
* không chạy lại bằng MotherDuck;
* không xóa output lịch sử.

Nếu không có dữ liệu local để chạy full notebook:

* chỉ kiểm tra import;
* kiểm tra cell độc lập;
* chạy synthetic smoke test;
* báo rõ giới hạn.

---

# 22. Logging và xử lý lỗi

Dùng `logging`.

Các bước cần log:

* run ID;
* model version;
* algorithm;
* n_clusters;
* số dòng input;
* số feature;
* feature set version;
* thời gian train;
* silhouette score;
* artifact path;
* trạng thái success/failed.

Khi lỗi:

* không tạo status `CHAMPION`;
* không ghi artifact không hoàn chỉnh;
* giữ error message;
* không che exception quan trọng;
* không retry database;
* không ghi output nửa chừng nếu có thể tránh.

---

# 23. Kiểm thử

Không dùng MotherDuck hoặc full dataset.

Ưu tiên:

1. synthetic DataFrame đúng schema;
2. fixture local;
3. CSV local nhỏ.

Kiểm tra tối thiểu:

1. Import module không lỗi.
2. Repository root đúng.
3. Schema validation hoạt động.
4. Preprocessor hoạt động.
5. Số cluster đúng config.
6. Random seed được giữ.
7. Synthetic pipeline train được.
8. Metric clustering tính được.
9. Model save/load được.
10. Assignment trước/sau load nhất quán.
11. `cluster_id` không thay đổi ngoài điều kiện cho phép.
12. `cluster_name` mapping được giữ.
13. Metadata serialize được.
14. Metric DataFrame đúng schema.
15. Assignment DataFrame đúng schema.
16. Profile DataFrame đúng schema.
17. Artifact cũ không bị ghi đè.
18. Không có MotherDuck connection.
19. Không có network call.
20. Không có side effect khi import.

Không chạy:

* full dataset;
* full notebook;
* dbt build;
* MotherDuck query;
* re-tuning số cluster;
* benchmark nhiều thuật toán;
* PCA hoặc visualization nặng nếu không cần cho smoke test.

---

# 24. Lệnh chạy mong muốn

Import check:

```bash
python -c "import ml.listing_segmentation"
```

Smoke test:

```bash
python -m ml.listing_segmentation.pipeline --smoke-test
```

Chạy bằng local CSV:

```bash
python -m ml.listing_segmentation.pipeline \
  --input path/to/local_sample.csv
```

Gán cluster bằng artifact có sẵn:

```bash
python -m ml.listing_segmentation.pipeline \
  --input path/to/local_sample.csv \
  --mode assign \
  --model-version segment_v001
```

Không tạo default đọc MotherDuck.

---

# 25. Báo cáo cuối cùng

Sau khi triển khai, báo cáo:

* CodeGraph xác định dependency gì;
* file tạo mới;
* file sửa;
* file giữ nguyên;
* cấu trúc cuối;
* helper common đã tái sử dụng;
* algorithm hiện tại;
* n_clusters hiện tại;
* feature set lấy từ đâu;
* cách truyền DataFrame;
* cách chạy local CSV;
* cách chạy smoke test;
* cách train;
* cách assign cluster;
* cách lưu/load artifact;
* output nằm ở đâu;
* artifact nằm ở đâu;
* metadata nào được tạo;
* test nào đã chạy;
* test nào chưa chạy;
* phần chưa xác minh vì không truy cập MotherDuck;
* kết quả clustering có thay đổi không;
* cluster mapping có thay đổi không;
* rủi ro tương thích còn lại.

Không tuyên bố đã xác minh production nếu chỉ dùng synthetic hoặc local sample.

Ưu tiên:

* giữ nguyên hành vi hiện tại;
* không thay đổi thuật toán;
* không thay đổi số cluster;
* dùng chung đúng phần cần thiết trong `ml/common`;
* tách artifact khỏi output;
* thêm `model_version` vào assignment và profile;
* không over-engineer;
* không truy cập MotherDuck;
* không đọc dữ liệu lớn;
* không tiêu tốn token không cần thiết.
