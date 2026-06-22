Hãy rà soát kiến trúc Dagster hiện tại của repository và bổ sung đúng 3 job mới sau:

```text
bronze_ingestion_job
dbt_analytics_build_job
data_refresh_job
```

Bốn job ML dưới đây đã hoàn thành và không được chỉnh sửa logic, asset selection, dependency hoặc tên job:

```text
price_retraining_job
segmentation_retraining_job
price_prediction_job
segmentation_assignment_job
```

Mục tiêu là hoàn thiện flow dữ liệu từ ingestion đến dbt analytics và inference, nhưng không đụng vào flow training/inference ML đã có.

# 1. Rà soát trước khi sửa

Trước khi chỉnh sửa, hãy kiểm tra:

* cấu trúc thư mục `orchestration/`;
* các Dagster assets, jobs, definitions, schedules và resources;
* ingestion code hiện tại;
* dbt integration hiện tại;
* `airbnb_gold_dbt_assets`;
* các dbt assets thuộc Bronze, Silver và Gold;
* dependency giữa dbt assets và bốn job ML hiện có;
* resource kết nối MotherDuck;
* cách project hiện tại load definitions.

Không viết lại kiến trúc từ đầu nếu repository đã có asset hoặc helper phù hợp.

# 2. Giữ nguyên bốn job ML

Không sửa các job:

```text
price_retraining_job
segmentation_retraining_job
price_prediction_job
segmentation_assignment_job
```

Cụ thể không được:

* đổi tên job;
* đổi asset selection;
* đổi dependency;
* sửa logic training;
* sửa logic scoring candidate;
* sửa SHAP;
* sửa registry;
* sửa Champion;
* sửa artifact;
* sửa MLOps metadata;
* đổi thứ tự asset trong các job này.

Chỉ được tham chiếu hoặc tái sử dụng các inference assets hiện có khi xây `data_refresh_job`.

# 3. `bronze_ingestion_job`

Tạo hoặc hoàn thiện job:

```text
bronze_ingestion_job
```

Mục tiêu:

```text
nguồn dữ liệu thô
→ validate đầu vào
→ load vào Bronze
→ kiểm tra kết quả ingestion
```

Job phải chọn đúng các ingestion assets hiện có.

Nếu repository đã có các asset cho:

```text
listings
calendar
reviews
neighbourhoods
neighbourhoods_geojson
```

hãy tái sử dụng, không tạo duplicate.

Flow mong muốn:

```text
raw source files
→ source validation
→ bronze tables
→ ingestion validation
```

Yêu cầu:

* dùng asset-based job;
* không gọi job khác từ bên trong job;
* không gọi `dagster job execute` bằng subprocess;
* không chạy dbt trong job này;
* không chạy ML;
* không thay đổi Champion;
* không xóa dữ liệu Bronze ngoài logic hiện có;
* dùng resource MotherDuck hiện tại;
* giữ cơ chế idempotent hiện có nếu đã có;
* log số lượng record được đọc và ghi;
* fail rõ ràng nếu source file bắt buộc không tồn tại hoặc schema không hợp lệ.

Nếu ingestion hiện tại đã bao gồm validation, chỉ cần chọn đúng asset set vào job.

# 4. `dbt_analytics_build_job`

Tạo hoặc hoàn thiện job:

```text
dbt_analytics_build_job
```

Mục tiêu:

```text
Bronze
→ Silver
→ Gold dimensions/facts/marts
→ Gold ML feature tables
→ dbt tests
```

Job phải dùng Dagster dbt assets hiện có, không dùng Python op gọi thủ công:

```bash
dbt build
```

Nếu project đã load dbt assets qua:

```text
airbnb_dbt_assets
airbnb_gold_dbt_assets
```

hoặc tên tương đương, hãy dùng asset selection dựa trên đúng object hiện có.

Job nên materialize:

* toàn bộ Silver models;
* Gold dimensions;
* Gold facts;
* Gold marts dùng cho dashboard;
* `gold.gold_price_model_features`;
* `gold.gold_cluster_model_features`;
* dbt tests gắn với các model được chọn.

Không chạy:

* `price_training_result`;
* `segmentation_training_result`;
* prediction asset;
* assignment asset;
* MLOps registry asset.

Hai Gold feature tables vẫn được build trong analytics job vì chúng là một phần của data warehouse, nhưng build feature không đồng nghĩa retrain model.

Ưu tiên dùng asset selection theo group, tag hoặc dbt translator metadata hiện có.

Ví dụ định hướng:

```python
dbt_analytics_selection = (
    AssetSelection.groups("silver", "gold")
)
```

hoặc selection theo dbt assets hiện có.

Không hard-code asset keys nếu project đã có helper selection tốt hơn.

# 5. `data_refresh_job`

Tạo job tổng hợp:

```text
data_refresh_job
```

Flow nghiệp vụ:

```text
Bronze ingestion
→ dbt analytics build
→ price inference bằng Champion hiện tại
→ segmentation assignment bằng Champion hiện tại
```

Job này không được retrain model.

Flow cụ thể:

```text
raw source
→ Bronze
→ Silver
→ Gold analytics/features
→ price scoring candidates
→ load Price Champion
→ price prediction
→ segmentation candidates
→ load Segmentation Champion
→ cluster assignment
```

Không chứa:

```text
price_training_result
segmentation_training_result
SHAP training
model registration
CANDIDATE creation
Champion promotion
```

# 6. Cách xây `data_refresh_job`

Không gọi trực tiếp các job sau từ bên trong job:

```text
bronze_ingestion_job
dbt_analytics_build_job
price_prediction_job
segmentation_assignment_job
```

Dagster job không nên gọi job khác như function.

Thay vào đó, tạo `data_refresh_job` bằng một asset selection tổng hợp gồm:

1. ingestion assets;
2. dbt Silver/Gold analytics assets;
3. các inference assets hiện đang nằm trong:

   * `price_prediction_job`;
   * `segmentation_assignment_job`.

Phải tái sử dụng đúng asset definitions hiện có.

Không duplicate asset implementation.

Ví dụ định hướng:

```python
data_refresh_selection = (
    bronze_selection
    | dbt_analytics_selection
    | price_inference_selection
    | segmentation_inference_selection
)
```

Sau đó:

```python
define_asset_job(
    name="data_refresh_job",
    selection=data_refresh_selection,
)
```

Tên biến và selection phải theo code thực tế của repository.

# 7. Dependency

Đảm bảo dependency đúng:

```text
bronze assets
→ dbt Silver assets
→ dbt Gold assets
→ Gold feature assets
→ inference assets
```

Price inference phải chờ:

```text
gold.gold_price_model_features
```

Segmentation inference phải chờ:

```text
gold.gold_cluster_model_features
```

Không tạo dependency giả bằng cách chỉ dựa vào thứ tự selection.

Dagster phải nhìn thấy dependency qua:

* asset input;
* AssetKey dependency;
* dbt asset dependency;
* hoặc `deps` hiện có.

Nếu inference assets hiện tại đã có dependency đúng với Gold feature assets, giữ nguyên.

Nếu chưa có dependency rõ ràng nhưng bốn ML job đang chạy đúng, không được sửa trực tiếp bốn job. Chỉ báo cáo vấn đề thay vì thay đổi ngoài phạm vi.

# 8. Trường hợp không có Champion

Trong `data_refresh_job`, giữ nguyên behavior hiện tại của inference assets.

Nếu Price Champion hoặc Segmentation Champion chưa tồn tại:

* không tự retrain;
* không tự promote;
* không tạo Champion mặc định.

Nếu inference asset hiện tại fail khi thiếu Champion, giữ nguyên behavior đó.

Không thêm fallback sang Candidate.

# 9. Trường hợp không có scoring candidate

Giữ nguyên logic hiện tại:

```text
không có candidate
→ asset thành công
→ ghi log
→ không ghi record giả
```

Không sửa candidate selection.

# 10. Definitions

Cập nhật nơi đăng ký Dagster definitions để expose đủ 7 jobs:

```text
bronze_ingestion_job
dbt_analytics_build_job
price_retraining_job
segmentation_retraining_job
price_prediction_job
segmentation_assignment_job
data_refresh_job
```

Không làm mất:

* assets hiện có;
* schedules;
* sensors;
* resources;
* dbt resource;
* MotherDuck resource.

Không đăng ký job trùng tên.

# 11. Job selection gợi ý

Sau khi rà soát code, tổ chức selection thành các biến dùng lại được:

```text
bronze_ingestion_selection
dbt_analytics_selection
price_inference_selection
segmentation_inference_selection
```

Sau đó:

```text
bronze_ingestion_job
= bronze_ingestion_selection
```

```text
dbt_analytics_build_job
= dbt_analytics_selection
```

```text
data_refresh_job
= bronze_ingestion_selection
| dbt_analytics_selection
| price_inference_selection
| segmentation_inference_selection
```

Không đưa training selection vào `data_refresh_job`.

# 12. Không được làm

* Không sửa bốn job ML đã hoàn thành.
* Không đổi tên asset ML.
* Không đổi logic inference.
* Không đổi candidate query.
* Không đổi registry.
* Không đổi schema `mlops`.
* Không sửa SHAP.
* Không sửa artifact path.
* Không tạo `price_feature_build_job`.
* Không tạo `segmentation_feature_build_job`.
* Không tạo `full_ml_retraining_job`.
* Không dùng subprocess để gọi dbt.
* Không gọi job từ bên trong job.
* Không duplicate assets.
* Không tự động retrain trong `data_refresh_job`.
* Không tự động set Champion.

# 13. Tests

Bổ sung hoặc cập nhật test cho:

## `bronze_ingestion_job`

* selection chỉ chứa ingestion assets;
* không chứa dbt hoặc ML assets.

## `dbt_analytics_build_job`

* chứa Silver và Gold dbt assets;
* chứa hai Gold ML feature assets;
* không chứa training/inference Python assets.

## `data_refresh_job`

* chứa ingestion assets;
* chứa dbt analytics assets;
* chứa price inference assets;
* chứa segmentation inference assets;
* không chứa price training;
* không chứa segmentation training;
* không chứa registry Candidate creation;
* không chứa SHAP training.

Nếu project chưa có test asset selection, tạo test tối thiểu dựa trên asset keys hoặc graph structure.

# 14. Kết quả cần trả về

Sau khi chỉnh sửa, báo cáo:

1. Danh sách file đã sửa hoặc tạo.
2. Các asset selection được định nghĩa.
3. Flow của `bronze_ingestion_job`.
4. Flow của `dbt_analytics_build_job`.
5. Flow của `data_refresh_job`.
6. Xác nhận bốn job ML không bị sửa.
7. Danh sách 7 jobs hiện được expose trong Dagster.
8. Dependency graph giữa Bronze, dbt và inference.
9. Tests đã thêm và kết quả.
10. Command chạy từng job.

Ví dụ command, điều chỉnh theo cấu trúc thực tế:

```bash
dagster job execute -f orchestration/definitions.py -j bronze_ingestion_job
```

```bash
dagster job execute -f orchestration/definitions.py -j dbt_analytics_build_job
```

```bash
dagster job execute -f orchestration/definitions.py -j data_refresh_job
```

11. Các giới hạn hoặc vấn đề dependency còn tồn tại.

Không chỉ mô tả. Hãy trực tiếp chỉnh sửa code trong repository và giữ nguyên toàn bộ phần ML đã hoàn thành.
