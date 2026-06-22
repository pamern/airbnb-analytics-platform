Hãy rà soát toàn bộ code hiện tại của dự án trước khi chỉnh sửa, đặc biệt các phần liên quan đến:

* Dagster jobs, assets, ops và resources
* dbt models phục vụ price prediction và segmentation assignment
* logic đọc/ghi MotherDuck
* model registry
* batch prediction
* các bảng metadata ML hiện đang được ghi vào schema `gold`

Mục tiêu là thiết kế lại pipeline theo hai yêu cầu dưới đây.

# 1. Bổ sung logic xác định listing cần scoring

Hiện tại `price_prediction_job` đang dự báo tối đa 100 listing. Hãy sửa logic để job không lấy ngẫu nhiên hoặc lấy cố định 100 listing từ toàn bộ bảng feature.

Job chỉ được scoring các listing thỏa ít nhất một trong ba điều kiện:

1. Listing chưa từng có prediction.
2. Listing đã có prediction nhưng `feature_hash` hiện tại khác với `feature_hash` tại lần prediction gần nhất.
3. Listing đã được prediction nhưng `model_version` của prediction gần nhất khác Champion hiện tại.

Không dùng `feature_updated_at` làm điều kiện chính để phát hiện thay đổi, vì mỗi lần chạy lại dbt có thể làm timestamp thay đổi dù feature thực tế không đổi.

## 1.1 Feature hash

Trong bảng/model dbt chứa feature dùng cho price prediction, bổ sung cột:

```sql
feature_hash
```

`feature_hash` phải được tính từ đúng các feature đầu vào thực sự được truyền vào model.

Yêu cầu:

* Không đưa `listing_id`, target `price`, `log_price`, timestamp hoặc metadata vào hash.
* Xử lý `NULL` nhất quán bằng `coalesce`.
* Ép kiểu dữ liệu nhất quán trước khi hash.
* Thứ tự các feature trong chuỗi hash phải cố định.
* Dùng hàm hash tương thích với DuckDB/MotherDuck, ưu tiên `md5(concat_ws(...))`.

Không hard-code một danh sách feature mới nếu project đã có constant/config xác định model features. Hãy tái sử dụng nguồn cấu hình hiện có nếu hợp lý.

## 1.2 Xác định prediction gần nhất

Từ bảng lưu prediction, xác định prediction mới nhất của từng `listing_id` bằng:

```sql
row_number() over (
    partition by listing_id
    order by predicted_at desc
)
```

Mỗi prediction phải lưu tối thiểu:

* `listing_id`
* `run_id`
* `model_version`
* `predicted_price`
* `feature_hash`
* `predicted_at`

Nếu project có thêm các cột như `actual_price`, `prediction_error`, `batch_id` hoặc `created_at`, giữ nguyên nếu chúng còn phù hợp.

## 1.3 Candidate query

Logic candidate tương đương:

```sql
WHERE
       latest_prediction.listing_id IS NULL
    OR latest_prediction.feature_hash <> current_features.feature_hash
    OR latest_prediction.model_version <> champion.model_version
```

Cần xử lý `NULL` an toàn. Không để phép so sánh `NULL <> value` làm bỏ sót candidate.

Thứ tự ưu tiên:

1. Listing chưa từng được predict.
2. Listing chưa được predict bởi Champion hiện tại.
3. Listing có feature thay đổi.

Sau khi sắp xếp, chỉ lấy tối đa 100 listing cho mỗi lần chạy.

Nếu không có candidate:

* Job phải kết thúc thành công.
* Ghi log rõ rằng không có listing cần scoring.
* Không tạo run lỗi.
* Không ghi prediction rỗng hoặc bản ghi giả.

## 1.4 Champion

`price_prediction_job` phải:

* Chỉ load model có trạng thái `CHAMPION`.
* Chỉ có đúng một Champion cho từng `model_name`.
* Báo lỗi rõ ràng nếu không tìm thấy Champion.
* Báo lỗi nếu có nhiều hơn một Champion đang active.
* Không retrain model.
* Không thay đổi registry.
* Không fit lại preprocessor.
* Load đúng artifact và preprocessor đã lưu cùng Champion.

Khi Champion mới được chọn, tất cả listing có prediction từ model cũ sẽ trở thành candidate thông qua điều kiện `model_version` khác Champion. Job vẫn chỉ xử lý tối đa 100 listing mỗi batch.

## 1.5 Segmentation assignment

Áp dụng cùng nguyên tắc cho `segmentation_assignment_job`.

Một listing cần được assign cluster khi:

1. Chưa từng có cluster assignment.
2. `feature_hash` của feature phân cụm đã thay đổi.
3. Assignment gần nhất dùng `model_version` khác Segmentation Champion hiện tại.

Assignment phải lưu tối thiểu:

* `listing_id`
* `run_id`
* `model_version`
* `cluster_id`
* `feature_hash`
* `assigned_at`

Không được fit lại scaler, encoder, preprocessing hoặc KMeans trong assignment job.

Với Champion KMeans mới, toàn bộ listing cũ phải dần trở thành candidate để được assign lại. Có thể xử lý theo batch nếu kiến trúc hiện tại có batch limit.

# 2. Chuyển thiết kế metadata model sang schema `mlops`

Thiết kế lại toàn bộ flow mới để các bảng sau được tạo và ghi vào schema `mlops`:

```text
mlops.model_runs
mlops.model_metrics
mlops.model_registry
mlops.model_feature_importance
```

Không cần viết migration để chuyển dữ liệu hoặc rename các bảng cũ trong `gold`.

Tôi sẽ tự xóa các bảng metadata cũ trong schema `gold`.

Chỉ cần:

* Tạo schema `mlops` nếu chưa tồn tại.
* Tạo mới hoặc cập nhật các model/table definition để pipeline từ nay ghi vào `mlops`.
* Cập nhật toàn bộ code Python, SQL, dbt, Dagster và Streamlit đang tham chiếu các bảng metadata cũ.
* Không thay đổi các bảng nghiệp vụ Gold không liên quan.

## 2.1 Phân chia trách nhiệm schema

Schema `gold` chỉ giữ dữ liệu nghiệp vụ và đầu ra dùng cho dashboard, ví dụ:

```text
gold.gold_price_model_features
gold.gold_cluster_model_features
gold.gold_listing_price_predictions
gold.gold_listing_cluster_assignments
gold.gold_cluster_profiles
```

Schema `mlops` giữ metadata quản lý vòng đời model:

```text
mlops.model_runs
mlops.model_metrics
mlops.model_registry
mlops.model_feature_importance
```

Không đưa prediction nghiệp vụ hoặc cluster assignment vào `mlops`.

## 2.2 `mlops.model_runs`

Bảng này quản lý mỗi lần train hoặc inference.

Thiết kế tối thiểu:

```text
run_id
job_name
model_name
run_type
status
data_version hoặc feature_snapshot
started_at
completed_at
artifact_path
error_message
created_at
```

`run_type` có thể gồm:

```text
TRAINING
PRICE_PREDICTION
SEGMENTATION_TRAINING
SEGMENTATION_ASSIGNMENT
```

Có thể điều chỉnh enum/value để phù hợp code hiện tại, nhưng phải thống nhất toàn pipeline.

## 2.3 `mlops.model_metrics`

Thiết kế tối thiểu:

```text
run_id
model_name
model_version
metric_name
metric_value
dataset_split
created_at
```

Ví dụ metric:

* RMSE
* MAE
* R2
* silhouette_score
* davies_bouldin_score
* inertia
* fit_time
* predict_time

Không tạo mỗi metric thành một cột riêng nếu code hiện tại có thể chuyển sang dạng long format hợp lý.

## 2.4 `mlops.model_registry`

Thiết kế tối thiểu:

```text
model_name
model_version
run_id
stage
is_active
artifact_path
preprocessor_path
created_at
promoted_at
promoted_by
```
Lưu ý: artifact_path: relative path tính từ project root
Stage gồm:

```text
CANDIDATE
CHAMPION
ARCHIVED
```

Luồng đơn giản:

```text
Retraining
→ lưu artifact
→ tạo registry record với stage = CANDIDATE
→ người dùng chọn model trên Streamlit
→ Set CHAMPION
→ Champion cũ chuyển ARCHIVED
```

Không cần tạo promotion job riêng.

Khi Streamlit set Champion:

* Thực hiện trong transaction nếu MotherDuck hỗ trợ flow hiện tại.
* Champion cũ cùng `model_name` chuyển thành `ARCHIVED`, `is_active = false`.
* Model được chọn chuyển thành `CHAMPION`, `is_active = true`.
* Ghi `promoted_at`.
* Không ảnh hưởng Champion của loại model khác.
* Đảm bảo tối đa một Champion active cho mỗi `model_name`.

Ví dụ:

```text
price_model        → tối đa 1 Champion
segmentation_model → tối đa 1 Champion
```
Cái streamlit set champion hiện tại chưa cần sửa, chỉ cần append đoạn sql vào README để t testr tên motherduck trước, sau đó mới xây trên streamlit sau
## 2.5 `mlops.model_feature_importance`

Thiết kế tối thiểu:

```text
run_id
model_name
model_version
feature_name
importance_value
importance_rank
importance_method
created_at
```

`importance_method` có thể gồm:

```text
native
permutation
shap
```

Giữ đúng method đang được project sử dụng. Không tự chuyển sang SHAP nếu code hiện tại chưa dùng SHAP.

# 3. Cập nhật các pipeline hiện tại

Cập nhật bốn job theo flow:

## `price_retraining_job`

```text
dbt price training features
→ training
→ evaluation
→ artifact validation
→ lưu model_runs vào mlops
→ lưu model_metrics vào mlops
→ lưu feature importance vào mlops
→ đăng ký model_registry với trạng thái CANDIDATE
```

Không tự động đổi Champion.

## `segmentation_retraining_job`

```text
dbt cluster training features
→ preprocessing + KMeans training
→ evaluation
→ artifact validation
→ lưu model_runs vào mlops
→ lưu model_metrics vào mlops
→ lưu feature importance hoặc cluster-related importance nếu hiện có
→ đăng ký model_registry với trạng thái CANDIDATE
```

Không tự động đổi Champion.

## `price_prediction_job`

```text
dbt price scoring features
→ lấy Price Champion từ mlops.model_registry
→ xác định scoring candidates bằng listing_id + feature_hash + model_version
→ lấy tối đa 100 candidates
→ load artifact
→ predict
→ ghi kết quả vào Gold
→ ghi trạng thái run vào mlops.model_runs
```

Không retrain và không thay đổi registry.

## `segmentation_assignment_job`

```text
dbt cluster scoring features
→ lấy Segmentation Champion từ mlops.model_registry
→ xác định assignment candidates bằng listing_id + feature_hash + model_version
→ load artifact
→ assign cluster
→ ghi kết quả vào Gold
→ ghi trạng thái run vào mlops.model_runs
```

Không fit lại KMeans hoặc preprocessing.



# 5. Yêu cầu kỹ thuật

* Không sửa các notebook EDA hoặc model experimentation không liên quan.
* Không thay đổi logic huấn luyện đã ổn định ngoài những phần cần thiết cho metadata flow.
* Không xóa code cũ một cách mù quáng; rà soát tất cả import và references trước.
* Không tạo duplicate helper nếu project đã có repository/service cho MotherDuck.
* Tái sử dụng connection pool hoặc database connection hiện có.
* Dùng parameterized query cho các giá trị động.
* Không dùng string interpolation trực tiếp cho dữ liệu người dùng.
* Các thao tác ghi run phải cập nhật trạng thái:

  * `RUNNING`
  * `SUCCESS`
  * `FAILED`
* Khi lỗi, lưu `error_message` vào `mlops.model_runs` rồi raise lại lỗi để Dagster ghi nhận failure.
* Việc ghi prediction và assignment nên có transaction hoặc cơ chế tránh ghi dở dang.
* Không tạo prediction trùng cho cùng:

  * `listing_id`
  * `model_version`
  * `feature_hash`
* Nếu chạy lại job với cùng Champion và feature không đổi, listing đó không được scoring lại.

# 6. dbt tests và kiểm tra dữ liệu

Bổ sung test phù hợp nếu chưa có, còn nếu có rồi thì khỏi:

* `run_id` không null.
* `model_version` không null trong registry, metrics và prediction.
* `feature_hash` không null trong scoring feature và prediction/assignment.
* `stage` chỉ nhận các giá trị hợp lệ.
* `metric_value` không null.
* Quan hệ `run_id` giữa metrics, registry, feature importance và model_runs.
* Kiểm tra không có nhiều hơn một Champion active cho cùng `model_name`.
* Kiểm tra không có duplicate prediction theo `listing_id + model_version + feature_hash`.
* Kiểm tra không có duplicate assignment theo `listing_id + model_version + feature_hash`.

Nếu dbt không phù hợp để enforce một số rule trên bảng được Python ghi trực tiếp, hãy đặt validation ở repository/service layer và ghi chú rõ.

# 7. Kết quả cần trả về

Sau khi chỉnh sửa, hãy báo cáo:

1. Danh sách file đã sửa hoặc tạo mới.
2. Flow mới của bốn Dagster jobs.
3. Schema và cấu trúc các bảng `mlops`.
4. Logic SQL hoặc Python xác định scoring candidates.
5. Logic Set Champion trên Streamlit.
6. Các test đã bổ sung.
7. Những command cần chạy để:

   * tạo schema/bảng mới;
   * chạy dbt build;
   * chạy từng Dagster job;
   * kiểm tra candidate query.
8. Các giả định hoặc giới hạn còn tồn tại.

Không chỉ mô tả giải pháp. Hãy trực tiếp sửa code trong repository.
