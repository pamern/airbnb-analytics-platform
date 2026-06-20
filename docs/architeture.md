# Kiến trúc Airbnb Analytics Platform

## Kiến trúc tổng quan

| Thành phần | Công nghệ | Vai trò | Đầu vào | Đầu ra |
|---|---|---|---|---|
| Nguồn dữ liệu | Inside Airbnb | Cung cấp dữ liệu listings, calendar, reviews, neighbourhoods và GeoJSON khu vực. | CSV, GeoJSON | Dữ liệu thô phục vụ ingestion |
| Ingestion | Python | Nạp dữ liệu gần nguyên bản vào Bronze, kiểm tra cơ bản trước khi lưu. | File Inside Airbnb | Bảng Bronze trên MotherDuck |
| Data transformation | dbt Core | Quản lý transform Bronze → Silver → Gold; làm sạch, chuẩn hóa và xây dựng dimension, fact, ML features. | Bronze/Silver tables | Gold marts, `gold_price_model_features`, `gold_cluster_model_features` |
| Data warehouse | MotherDuck / DuckDB | Lưu trữ dữ liệu theo các layer và cung cấp dữ liệu Gold cho ML, dashboard. | Bronze, Silver, Gold data | Bảng phân tích và bảng kết quả ML |
| Orchestration | Dagster | Điều phối thứ tự chạy dbt và ML, theo dõi asset/run, retry và asset checks; không chứa logic huấn luyện. | dbt assets, Gold tables, ML pipelines | Các run có kiểm soát và kết quả được ghi đúng thứ tự |
| Price Modeling | Python, scikit-learn, XGBoost | Retrain XGBRegressor hoặc dự báo giá bằng model đã được chọn. | `gold_price_model_features`, artifact CHAMPION | Artifact, metadata, `gold_price_predictions` |
| Listing Segmentation | Python, scikit-learn KMeans | Retrain KMeans hoặc gán cluster bằng model đã được chọn. | `gold_cluster_model_features`, artifact CHAMPION | Artifact, cluster profile, `gold_listing_segments`, `gold_segment_profiles` |
| Model Management | MotherDuck, joblib, JSON | Theo dõi training run, registry, metric và artifact theo `model_version`. | Kết quả retraining | `gold_ml_training_runs`, `gold_ml_model_registry`, `gold_ml_model_metrics`, `ml/artifacts/` |
| Dashboard | Streamlit | Hiển thị KPI/insight từ Gold và dùng model CHAMPION để dự báo từ dữ liệu người dùng nhập. | Gold tables, ML outputs, artifact CHAMPION | Dashboard và dự báo tương tác |

## Luồng chạy pipeline

| Pipeline/Job | Các bước chính | Có huấn luyện model không? | Kết quả tạo ra | Khi nào nên chạy |
|---|---|---|---|---|
| Ingestion | Đọc file Inside Airbnb → nạp Bronze | Không | Dữ liệu Bronze gần nguồn gốc | Khi có dữ liệu nguồn mới |
| dbt transformation | Bronze → Silver → Gold → tạo feature tables | Không | Dimension, fact và Gold ML features | Sau ingestion hoặc khi logic dữ liệu thay đổi |
| `price_retraining_job` | Build Gold price features → train XGBRegressor đã chọn → đánh giá → lưu artifact/metadata → ghi test predictions | Có | Model version mới, registry, metric, `gold_price_predictions` | Khi cần cập nhật model giá có chủ đích |
| `price_prediction_job` | Build/đọc Gold price features → load CHAMPION → dự báo batch → ghi predictions | Không | Batch predictions với model version hiện hành | Khi cần dự báo mới thường xuyên |
| `segmentation_retraining_job` | Build Gold cluster features → fit KMeans → đánh giá cluster → lưu artifact/profile | Có | Model version mới, metric, cluster assignments và profiles | Khi cần cập nhật phân khúc có chủ đích |
| `segmentation_assignment_job` | Build/đọc Gold cluster features → load CHAMPION → gán cluster | Không | `gold_listing_segments` theo model version hiện hành | Khi cần gán cluster cho dữ liệu mới |
| Streamlit dashboard | Đọc Gold/ML outputs → hiển thị KPI và nhận dữ liệu người dùng | Không | Dashboard và dự báo giá tương tác | Khi người dùng truy cập dashboard |

## Các bảng liên quan đến Machine Learning

| Bảng | Vai trò | Trường dữ liệu chính | Mô tả ngắn |
|---|---|---|---|
| `gold_price_model_features` | Feature table cho dự báo giá | `listing_id`, `price`, `log_price`, `neighbourhood`, `room_type`, `property_type`, sức chứa, phòng ngủ, review, host metrics | Một dòng cho mỗi listing; chứa target và các đặc trưng đầu vào cho Price Modeling. |
| `gold_cluster_model_features` | Feature table cho phân khúc listing | `listing_id`, `price`, `room_type`, `property_base_group`, `accommodates`, `bedrooms`, `bathrooms`, `beds`, `amenities_count`, `minimum_nights_log` | Một dòng cho mỗi listing; chứa các đặc trưng đã chuẩn bị cho KMeans. |
| `gold_ml_training_runs` | Lịch sử lần huấn luyện | `run_id`, `model_version`, `model_task`, `training_mode`, `model_name`, `started_at`, `status` | Ghi nhận thời điểm, loại model và trạng thái của mỗi lần retraining. |
| `gold_ml_model_registry` | Danh mục model đã lưu | `model_version`, `model_task`, `model_name`, `artifact_path`, `status`, `created_at` | Xác định artifact cần load; status có thể là `CANDIDATE` hoặc `CHAMPION`. |
| `gold_ml_model_metrics` | Metric theo model version | `model_version`, `model_task`, `dataset_type`, `metric_name`, `metric_value`, `metric_std`, `evaluated_at` | Lưu RMSE, MAE, R² hoặc các metric clustering để so sánh model. |
| `gold_price_predictions` | Kết quả dự báo giá | `prediction_run_id`, `model_version`, `listing_id`, `predicted_log_price`, `predicted_price`, `prediction_type`, `predicted_at` | Lưu dự báo batch; có thể kèm `actual_price`, residual và absolute error khi có target. |
| `gold_listing_segments` | Kết quả gán phân khúc | `assignment_run_id`, `listing_id`, `model_version`, `cluster_id`, `cluster_name`, `distance_to_centroid`, `assigned_at` | Lưu cluster của từng listing và khoảng cách đến tâm cụm. |
| `gold_segment_profiles` | Hồ sơ mô tả cluster | `model_version`, `cluster_id`, `cluster_name`, `listing_count`, `median_price`, `avg_price`, `listing_share`, `created_at` | Tổng hợp đặc điểm của từng cluster tại thời điểm retraining. |

## Chi tiết pipeline Machine Learning

| Pipeline | Luồng xử lý | Quy tắc quan trọng |
|---|---|---|
| Price retraining | `gold_price_model_features` → validation → preprocessing → train XGBRegressor → evaluation → artifact/version → registry, metrics, predictions | Chỉ retrain champion algorithm đã chọn; target là `log_price`; tạo model version mới. |
| Price inference | Gold price features → lookup `CHAMPION` → load artifact và feature schema → prediction batch → `gold_price_predictions` | Không train lại, không tạo artifact hoặc registry record mới; chỉ dùng model version đã đăng ký. |
| Segmentation retraining | `gold_cluster_model_features` → validation → encode/scale → fit KMeans → cluster evaluation → profile → artifact/version → registry, assignments | Giữ nguyên số cluster, seed, feature set và cluster-name mapping; tạo model version mới. |
| Segmentation assignment | Gold cluster features → lookup `CHAMPION` → load artifact/mapping → assign cluster → `gold_listing_segments` | Không fit lại KMeans hoặc preprocessor; không tạo profile, artifact hay registry record mới. |

Khi inference chạy, registry ưu tiên model có trạng thái `CHAMPION`. Nếu chưa có CHAMPION, pipeline mặc định dừng rõ ràng để tránh dùng nhầm model. Candidate mới nhất chỉ được dùng khi cấu hình fallback được bật tường minh. Điều này giúp retraining và inference có vòng đời riêng, đồng thời truy vết được model version đã tạo ra mỗi output.

Hệ thống bắt đầu từ dữ liệu Inside Airbnb, sau đó Python ingestion nạp dữ liệu thô vào Bronze trên MotherDuck. dbt quản lý toàn bộ transformation từ Bronze sang Silver và Gold, bao gồm hai bảng feature cho ML. Dagster điều phối dbt và các pipeline ML theo asset/job, nhưng không chứa thuật toán huấn luyện. Retraining tạo model version, artifact và metadata mới; inference chỉ load model CHAMPION để dự báo hoặc gán cluster. Registry và artifact giúp truy vết model nào đã tạo ra từng kết quả. Streamlit đọc dữ liệu Gold và kết quả ML để cung cấp dashboard cùng chức năng dự báo cho người dùng.
