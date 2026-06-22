Hãy chỉnh lớp orchestration Dagster hiện tại theo hướng tách rõ **training/retraining** và **inference/assignment** cho hai bài toán ML.

## 0. Mục tiêu

Giữ lại bốn job độc lập:

```text
price_retraining_job
price_prediction_job
segmentation_retraining_job
segmentation_assignment_job
```

Xóa hoàn toàn:

```text
full_ml_pipeline_job
```

Lý do:

* price prediction và listing segmentation có lifecycle khác nhau;
* không nên retrain cả hai model trong cùng một job;
* inference/assignment cần chạy thường xuyên hơn retraining;
* tránh tạo artifact và model version không cần thiết;
* dễ kiểm tra, debug và vận hành từng pipeline riêng.

Không thêm schedule hoặc sensor trong nhiệm vụ này.

---

# 1. Phạm vi chỉnh sửa

Khảo sát và chỉnh các file liên quan:

* `orchestration/assets/`
* `orchestration/jobs/`
* `orchestration/checks/`
* `orchestration/definitions.py`
* `orchestration/resources/`
* `ml/price_modeling/`
* `ml/listing_segmentation/`
* `ml/common/`
* các test orchestration hiện có.

Không thay đổi:

* thuật toán;
* preprocessing;
* feature set;
* hyperparameter;
* random seed;
* metric;
* model artifact format;
* dbt SQL model;
* schema registry hiện có;
* logic retraining đang chạy ổn.

Không commit hoặc push.

---

# 2. Bắt buộc dùng CodeGraph trước

Trước khi sửa:

1. Dùng CodeGraph xác định:

   * asset graph hiện tại;
   * bốn entry point ML hiện có hoặc gần tương đương;
   * cách lấy model `CHAMPION`;
   * cách load artifact;
   * cách đọc feature tables;
   * cách ghi predictions và cluster assignments;
   * dependency của jobs hiện tại;
   * nơi khai báo `full_ml_pipeline_job`.
2. Tìm tất cả reference tới:

   * `full_ml_pipeline_job`;
   * `price_retraining_job`;
   * `segmentation_retraining_job`;
   * `run_price_prediction_pipeline`;
   * `predict_price`;
   * `run_segmentation_assignment_pipeline`;
   * `assign_clusters`;
   * `model_status = 'CHAMPION'`;
   * artifact URI.
3. Đọc file gốc trước khi sửa.

Không materialize remote pipeline trong giai đoạn phân tích.

---

# 3. Quy trình thực hiện

Thực hiện thành hai giai đoạn.

## Giai đoạn 1: Phân tích

Chưa sửa code.

Báo cáo:

* các asset hiện tại;
* job hiện tại;
* entry point ML có thể tái sử dụng;
* phần nào còn thiếu cho inference/assignment;
* file cần tạo;
* file cần sửa;
* file cần xóa reference;
* schema input/output dự kiến;
* rủi ro tương thích.

Dừng lại chờ chấp thuận.

## Giai đoạn 2: Triển khai

Sau khi được chấp thuận:

1. Tạo price prediction assets.
2. Tạo segmentation assignment assets.
3. Tạo hai jobs mới.
4. Xóa full job.
5. Cập nhật Definitions.
6. Cập nhật checks.
7. Chạy validation và test.
8. Báo cáo kết quả.

---

# 4. Price retraining job

Giữ nguyên hành vi hiện tại:

```text
gold_price_model_features
→ price_training_result
→ price_model_artifact
→ price_registry_records
→ gold_price_predictions
```

Job:

```text
price_retraining_job
```

Phải tiếp tục:

* train lại champion algorithm;
* tạo model version mới;
* lưu artifact mới;
* ghi training run;
* ghi model registry;
* ghi metrics;
* ghi test/batch predictions nếu logic hiện tại đang làm.

Không thay đổi logic retraining hiện có.

---

# 5. Price prediction job

Tạo job mới:

```text
price_prediction_job
```

Mục tiêu là **không train lại model**.

Flow đề xuất:

```text
gold_price_model_features
→ current_price_champion
→ price_batch_predictions
→ gold_price_predictions
```

Có thể đặt asset names khác nếu phù hợp với convention hiện tại, nhưng trách nhiệm phải rõ.

## 5.1. Load champion model

Tạo asset hoặc helper lấy model hiện tại từ registry:

```text
model_task = 'price_prediction'
model_status = 'CHAMPION'
```

Nếu hiện tại chưa có model `CHAMPION`, cho phép fallback có kiểm soát:

1. ưu tiên `CHAMPION`;
2. nếu không có, có thể dùng model `CANDIDATE` mới nhất chỉ khi cấu hình explicit cho phép;
3. mặc định nên fail rõ ràng nếu không tìm thấy champion.

Không tự promote model.

Phải lấy:

* `model_version`;
* `artifact_uri`;
* feature set version;
* algorithm;
* metadata cần thiết.

## 5.2. Prediction

Tái sử dụng API trong `ml.price_modeling`, ví dụ:

```python
load_price_model(...)
predict_price(...)
run_price_prediction_pipeline(...)
```

Không copy preprocessing hoặc prediction logic vào Dagster asset.

Không gọi:

* training;
* tuning;
* feature selection;
* baseline;
* evaluation bằng target nếu inference input không có target.

## 5.3. Output

Ghi vào:

```text
gold_price_predictions
```

Tối thiểu:

```text
prediction_run_id
model_version
listing_id
predicted_log_price
predicted_price
prediction_type
predicted_at
```

Nếu input có actual price và pipeline hiện tại hỗ trợ đánh giá batch, có thể bổ sung:

```text
actual_price
actual_log_price
residual
absolute_error
```

Nhưng không bắt buộc target cho prediction job.

`prediction_type` nên là:

```text
batch
```

Không tạo model registry record mới vì model không được train lại.

Có thể tạo một inference run record riêng nếu schema hiện tại hỗ trợ. Nếu chưa hỗ trợ, chỉ log Dagster run ID và prediction run ID trong output, không nhét inference run vào training table một cách sai nghĩa.

---

# 6. Segmentation retraining job

Giữ nguyên hành vi hiện tại:

```text
gold_cluster_model_features
→ segmentation_training_result
→ segmentation_model_artifact
→ segmentation_registry_records
→ gold_listing_segments
→ gold_segment_profiles
```

Job:

```text
segmentation_retraining_job
```

Phải tiếp tục:

* fit lại preprocessor và KMeans;
* tạo model version mới;
* lưu artifact;
* ghi metrics;
* tạo cluster assignments;
* tạo cluster profiles.

Không thay đổi:

* algorithm;
* n_clusters;
* random seed;
* cluster mapping;
* feature set.

---

# 7. Segmentation assignment job

Tạo job mới:

```text
segmentation_assignment_job
```

Mục tiêu là **không fit lại KMeans**.

Flow đề xuất:

```text
gold_cluster_model_features
→ current_segmentation_champion
→ segmentation_assignments
→ gold_listing_segments
```

`gold_segment_profiles` không nhất thiết phải tạo lại trong assignment job, vì profile mô tả model/cluster definition đã có từ lúc retrain.

Chỉ cập nhật profile nếu code hiện tại có yêu cầu rõ ràng và không làm đổi ý nghĩa cluster.

## 7.1. Load champion segmentation model

Tìm:

```text
model_task = 'listing_segmentation'
model_status = 'CHAMPION'
```

Lấy:

* `model_version`;
* `artifact_uri`;
* cluster mapping;
* feature schema;
* metadata.

Nếu không có champion, mặc định fail rõ ràng.

Không tự promote candidate.

## 7.2. Assignment

Tái sử dụng:

```python
load_segmentation_model(...)
assign_clusters(...)
run_segmentation_assignment_pipeline(...)
```

Không:

* fit preprocessor;
* fit KMeans;
* tính lại n_clusters;
* chọn lại số cluster;
* benchmark thuật toán;
* tạo model version mới.

## 7.3. Output

Ghi vào:

```text
gold_listing_segments
```

Tối thiểu:

```text
assignment_run_id
listing_id
model_version
cluster_id
cluster_name
distance_to_centroid
assigned_at
```

Không tạo model registry record mới.

Không ghi metric training mới.

---

# 8. Xử lý model status

Hiện retraining đang ghi model mới là:

```text
CANDIDATE
```

Inference jobs cần model `CHAMPION`.

Khảo sát logic hiện tại và thực hiện một trong hai phương án:

## Phương án ưu tiên

Giữ retraining tạo `CANDIDATE`, và inference chỉ chạy khi đã có champion được chọn thủ công.

## Phương án tạm thời cho đồ án

Nếu chưa có champion nào trong database, cho phép cấu hình explicit:

```python
allow_latest_candidate_fallback: bool = False
```

Mặc định là `False`.

Khi bật:

* chỉ chọn candidate mới nhất đúng `model_task`;
* log cảnh báo rõ ràng;
* không đổi status trong registry;
* output vẫn ghi đúng `model_version` đã dùng.

Không âm thầm dùng candidate.

---

# 9. dbt assets

Tái sử dụng dbt assets hiện tại:

```text
gold_price_model_features
gold_cluster_model_features
```

Không tạo dbt wrapper mới.

Không chạy toàn bộ dbt project.

* `price_prediction_job` chỉ phụ thuộc `gold_price_model_features`.
* `segmentation_assignment_job` chỉ phụ thuộc `gold_cluster_model_features`.

---

# 10. Jobs

Sau chỉnh sửa phải có đúng bốn job:

```text
price_retraining_job
price_prediction_job
segmentation_retraining_job
segmentation_assignment_job
```

Xóa:

```text
full_ml_pipeline_job
```

Xóa tất cả:

* import;
* export;
* asset selection;
* test;
* documentation;
* Definitions reference

liên quan tới full job.

Không để dead code.

---

# 11. Asset selection

## `price_retraining_job`

Chỉ select:

* price dbt feature asset;
* price training assets;
* price registry;
* price training predictions;
* price checks.

## `price_prediction_job`

Chỉ select:

* price dbt feature asset;
* champion model lookup;
* batch prediction asset;
* prediction writer;
* prediction checks.

## `segmentation_retraining_job`

Chỉ select:

* segmentation dbt feature asset;
* segmentation training;
* artifact;
* registry;
* assignments;
* profiles;
* training checks.

## `segmentation_assignment_job`

Chỉ select:

* segmentation dbt feature asset;
* champion model lookup;
* assignment;
* assignment writer;
* assignment checks.

Không có job nào tự chạy cả price và segmentation.

---

# 12. Checks cho price prediction

Tạo hoặc tái sử dụng checks:

1. Feature input không rỗng.
2. Required columns đầy đủ.
3. Champion model tồn tại.
4. Artifact tồn tại.
5. Artifact load được.
6. `model_version` chỉ có một giá trị trong batch.
7. Prediction không NaN.
8. Prediction không infinity.
9. Predicted price không âm.
10. Mỗi listing có đúng một prediction.
11. Số output row bằng số input row nếu không có rule lọc.

---

# 13. Checks cho segmentation assignment

Kiểm tra:

1. Feature input không rỗng.
2. Required columns đầy đủ.
3. Champion model tồn tại.
4. Artifact load được.
5. Cluster mapping tồn tại.
6. Mỗi listing có đúng một assignment.
7. Cluster ID hợp lệ.
8. Cluster name không null.
9. `model_version` chỉ có một giá trị.
10. Số output row bằng số input row nếu không có rule lọc.
11. Không tạo artifact mới.
12. Không tạo registry record mới.

---

# 14. Definitions

Cập nhật `orchestration/definitions.py`:

* đăng ký assets mới;
* đăng ký checks mới;
* đăng ký bốn jobs;
* xóa full job;
* giữ resources hiện tại;
* không thêm schedule;
* không thêm sensor.

Entry point vẫn phải chạy:

```powershell
uv run dagster dev -m orchestration.definitions
```

---

# 15. Logging

Prediction/assignment assets phải log:

* Dagster run ID;
* prediction hoặc assignment run ID;
* model task;
* model version;
* artifact URI;
* algorithm;
* số dòng input;
* số dòng output;
* thời gian inference;
* số lỗi validation.

Không log:

* token;
* full DataFrame;
* secret;
* dữ liệu nhạy cảm.

---

# 16. Transaction và ghi dữ liệu

Prediction và assignment writer phải:

* validate DataFrame trước khi ghi;
* không ghi nếu rỗng;
* chống duplicate theo run ID và listing ID;
* dùng transaction;
* rollback khi lỗi;
* không xóa output model version cũ;
* không sửa model registry;
* không tạo model artifact.

Nếu chạy lại cùng Dagster run hoặc cùng inference run ID, phải tránh ghi trùng.

---

# 17. Kiểm thử bắt buộc

Không tự materialize remote pipeline.

Chạy:

```powershell
uv run dagster definitions validate -m orchestration.definitions
```

```powershell
uv run python -m compileall -q orchestration
```

```powershell
uv run python -c "from orchestration.definitions import defs; print('definitions loaded')"
```

Chạy unit tests ML hiện có:

```powershell
uv run python -m unittest tests.test_price_modeling tests.test_listing_segmentation
```

Thêm test cục bộ hoặc mock cho các điều kiện:

1. `price_prediction_job` không gọi hàm train.
2. `segmentation_assignment_job` không gọi hàm fit/train.
3. Prediction dùng đúng champion model version.
4. Assignment dùng đúng champion model version.
5. Không có `full_ml_pipeline_job` trong Definitions.
6. Có đúng bốn jobs.
7. Prediction output schema đúng.
8. Assignment output schema đúng.
9. Không tạo registry record trong inference jobs.
10. Không tạo artifact mới trong inference jobs.
11. Missing champion làm job fail rõ ràng.
12. Candidate fallback chỉ hoạt động khi explicit config bật.

Không query MotherDuck trong unit test. Dùng mock/fake resource.

---

# 18. Không làm trong nhiệm vụ này

Không:

* thêm schedule;
* thêm sensor;
* thêm auto-promotion;
* thêm drift detection;
* thêm MLflow;
* thêm Docker;
* sửa model training logic;
* tuning lại;
* chọn lại model;
* chọn lại n_clusters;
* thay đổi schema dbt nghiệp vụ;
* chạy remote job;
* commit;
* push.

---

# 19. Báo cáo cuối cùng

Sau khi hoàn thành, báo cáo:

1. CodeGraph xác định dependency gì.
2. File tạo mới.
3. File sửa.
4. File xóa hoặc bỏ reference.
5. Bốn jobs cuối cùng.
6. `full_ml_pipeline_job` đã được loại bỏ ở đâu.
7. Asset graph của `price_prediction_job`.
8. Asset graph của `segmentation_assignment_job`.
9. Cách tìm champion model.
10. Cách xử lý khi không có champion.
11. Có fallback candidate hay không.
12. Output schema của prediction.
13. Output schema của assignment.
14. Checks mới.
15. Tests đã chạy.
16. Tests chưa chạy.
17. Có thay đổi logic training hay không.
18. Có tạo artifact mới trong inference jobs hay không.
19. Có tạo registry record mới trong inference jobs hay không.
20. Rủi ro còn lại.

Ưu tiên:

* training và inference tách biệt;
* không retrain ngoài chủ đích;
* không fit lại KMeans trong assignment;
* không train lại XGBoost trong prediction;
* không giữ full pipeline;
* orchestration mỏng;
* tái sử dụng ML API hiện có;
* sửa tối thiểu;
* không over-engineer.
