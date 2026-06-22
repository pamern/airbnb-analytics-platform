Hãy trực tiếp xây dựng lại giao diện tab **Model Performance** trong trang Streamlit:

```text
app/pages/03_Model_Lab.py
```

Nếu tên file hoặc cấu trúc tab hiện tại khác đôi chút, hãy rà soát trong thư mục `app/` và sửa đúng trang **Model Lab**, tab dùng để đánh giá hiệu suất mô hình.

# 1. Phạm vi bắt buộc

Chỉ được sửa, tạo hoặc tái cấu trúc file bên trong:

```text
app/
```

Không được sửa bất kỳ file nào ngoài `app/`, bao gồm:

```text
orchestration/
ml/
dbt/
tests/
.github/
pyproject.toml
uv.lock
```

Không thay đổi:

* logic huấn luyện;
* logic inference;
* candidate scoring;
* model registry backend;
* schema database;
* SQL ghi dữ liệu;
* artifact;
* SHAP computation;
* Dagster jobs.

Chỉ xây dựng UI và logic đọc/biểu diễn dữ liệu trong `app/`.

# 2. Giữ nguyên navigation chính

Không được:

* đổi tên menu chính;
* đổi thứ tự menu;
* đổi icon;
* thay đổi routing;
* tạo navigation mới;
* thay đổi sidebar navigation hiện tại.

Chỉ được bổ sung bộ lọc bên trong trang hoặc tab **Model Performance**.

Nếu Model Lab đang có nhiều tab, giữ nguyên các tab khác. Chỉ sửa tab đánh giá hiệu suất mô hình.

Tên tab có thể chuẩn hóa thành:

```text
Model Performance
```

# 3. Ngôn ngữ giao diện

Toàn bộ chữ hiển thị trên giao diện phải bằng tiếng Anh.

Ví dụ:

```text
Model Performance
Track model runs, evaluation metrics, registry status and SHAP explanations
Price Model
Segmentation Model
Model Version
Run Type
Date Range
Predicted vs Actual
Residual Distribution
Metric Trend
Feature Importance
Recent Runs
Model Registry
```

Tên cột kỹ thuật trong bảng có thể giữ nguyên nếu cần.

# 4. Design tokens

Tạo một nguồn design token duy nhất bên trong `app/`, ví dụ:

```text
app/styles/design_tokens.py
```

hoặc tái sử dụng file token hiện có nếu đã có.

Không rải hard-coded CSS color khắp nhiều file.

Dùng bộ token sau:

```python
DESIGN_TOKENS = {
    # Background
    "color_bg": "#F7F9FC",
    "color_surface": "#FFFFFF",
    "color_surface_subtle": "#F8FAFC",
    "color_surface_hover": "#F1F5F9",

    # Text
    "color_text_primary": "#0F172A",
    "color_text_secondary": "#475569",
    "color_text_muted": "#64748B",
    "color_text_inverse": "#FFFFFF",

    # Border
    "color_border": "#E2E8F0",
    "color_border_strong": "#CBD5E1",

    # Brand
    "color_primary": "#4F8EF7",
    "color_primary_hover": "#3B7BE5",
    "color_primary_soft": "#EAF2FF",

    # Semantic
    "color_success": "#22C55E",
    "color_success_soft": "#DCFCE7",
    "color_warning": "#F59E0B",
    "color_warning_soft": "#FEF3C7",
    "color_danger": "#EF4444",
    "color_danger_soft": "#FEE2E2",
    "color_info": "#6366F1",
    "color_info_soft": "#EEF2FF",

    # Chart
    "chart_primary": "#4F8EF7",
    "chart_secondary": "#F59E0B",
    "chart_success": "#22C55E",
    "chart_danger": "#EF4444",
    "chart_neutral": "#94A3B8",
    "chart_reference": "#64748B",

    # Typography
    "font_family": "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "font_size_xs": "0.75rem",
    "font_size_sm": "0.875rem",
    "font_size_md": "1rem",
    "font_size_lg": "1.125rem",
    "font_size_xl": "1.5rem",
    "font_size_2xl": "2rem",

    # Radius
    "radius_sm": "6px",
    "radius_md": "10px",
    "radius_lg": "14px",
    "radius_pill": "999px",

    # Spacing
    "space_1": "4px",
    "space_2": "8px",
    "space_3": "12px",
    "space_4": "16px",
    "space_5": "20px",
    "space_6": "24px",
    "space_8": "32px",

    # Shadows
    "shadow_sm": "0 1px 2px rgba(15, 23, 42, 0.05)",
    "shadow_md": "0 4px 14px rgba(15, 23, 42, 0.06)",
}
```

Dùng token để tạo CSS chung cho:

* page background;
* card;
* KPI card;
* status badge;
* tab section;
* table container;
* filter container;
* empty state;
* section heading.

Không override CSS quá sâu theo class nội bộ dễ thay đổi của Streamlit nếu không cần thiết.

# 5. Bố cục trang

## 5.1 Header

Hiển thị:

```text
Model Performance
Track model runs, evaluation metrics, registry status and SHAP explanations
```

Header phải gọn, không quá cao.

## 5.2 Filter bar

Tạo filter bar nằm ngang bằng `st.columns`.

Các filter:

```text
Model
Stage
Model Version
Run Type
Date Range
```

Giá trị model:

```text
Price Model
Segmentation Model
```

Stage:

```text
All
CHAMPION
CANDIDATE
ARCHIVED
```

Run type phải lấy từ dữ liệu hiện có, ví dụ:

```text
TRAINING
PRICE_PREDICTION
SEGMENTATION_TRAINING
SEGMENTATION_ASSIGNMENT
```

Bộ lọc phải ảnh hưởng đến KPI, bảng và biểu đồ bên dưới.

Không tạo filter theo city, room type hoặc price range trong trang Model Performance vì đây là trang đánh giá model, không phải BI listing dashboard.

# 6. Tabs trong Model Performance

Tạo hai tab con:

```python
price_tab, segmentation_tab = st.tabs(
    ["Price Model", "Segmentation Model"]
)
```

Mỗi tab chỉ hiển thị metric phù hợp với loại model.

# 7. Price Model tab

## 7.1 KPI cards

Hiển thị tối đa 5 KPI:

1. Active Champion
2. RMSE — TEST
3. MAE — TEST
4. R² — TEST
5. SHAP Sample Size

Nguồn dữ liệu:

```text
mlops.model_registry
mlops.model_metrics
mlops.model_feature_importance
```

Champion phải lấy record:

```text
model_name = 'price_model'
stage = 'CHAMPION'
is_active = TRUE
```

Metric phải lấy đúng:

```text
model_version
dataset_split = 'TEST'
```

Không trộn metric của nhiều model version.

Nếu không có Champion, hiển thị warning card thay vì làm trang lỗi.

## 7.2 Predicted vs Actual

Nguồn:

```text
gold.gold_listing_price_predictions
```

Chỉ lấy các record có:

```text
actual_price IS NOT NULL
predicted_price IS NOT NULL
```

Lọc theo model version được chọn.

Vẽ scatter plot bằng Plotly:

```text
X = actual_price
Y = predicted_price
```

Thêm đường tham chiếu:

```text
y = x
```

Tooltip tối thiểu:

```text
listing_id
actual_price
predicted_price
prediction_error
model_version
```

## 7.3 Residual Distribution

Residual:

```text
predicted_price - actual_price
```

Vẽ histogram.

Thêm đường dọc tại:

```text
residual = 0
```

Không dùng residual trên `log_price` nếu bảng Gold đang lưu giá đã back-transform.

## 7.4 Metric Trend

Nguồn:

```text
mlops.model_metrics
mlops.model_runs
```

Vẽ line chart theo thời gian cho:

```text
RMSE
MAE
R2
```

Chỉ lấy:

```text
model_name = 'price_model'
dataset_split = 'TEST'
run status = 'SUCCESS'
```

Có thể cho phép người dùng chọn metric bằng multiselect.

## 7.5 Global SHAP Feature Importance

Nguồn:

```text
mlops.model_feature_importance
```

Điều kiện:

```text
model_name = 'price_model'
model_version = selected version
importance_method = 'shap'
feature_level = 'ORIGINAL'
```

Vẽ horizontal bar chart Top 10 hoặc Top 15:

```text
Y = feature_name
X = importance_value
```

Sắp xếp rank tăng dần hoặc importance giảm dần.

Ghi chú:

```text
Mean absolute SHAP value on the evaluation sample.
SHAP values explain predictions on the log-price scale.
```

Không fallback ngầm sang XGBoost gain nếu không có SHAP.

Nếu không có dữ liệu:

```text
No SHAP feature importance is available for this model version.
```

## 7.6 Model Registry

Nguồn:

```text
mlops.model_registry
```

Hiển thị các cột phù hợp:

```text
model_version
stage
is_active
created_at
promoted_at
promoted_by
artifact_path
```

Dùng badge cho:

```text
CHAMPION
CANDIDATE
ARCHIVED
```

Trang này chỉ đọc dữ liệu.

Không thêm hoặc thay đổi logic Set Champion trong tab Performance.

## 7.7 Recent Runs

Nguồn:

```text
mlops.model_runs
```

Hiển thị:

```text
run_id
run_type
status
started_at
completed_at
artifact_path
error_message
```

Ưu tiên 10 run mới nhất.

Badge trạng thái:

```text
SUCCESS
RUNNING
FAILED
```

Nếu FAILED, cho phép xem `error_message` trong expander.

# 8. Segmentation Model tab

## 8.1 KPI cards

Hiển thị:

1. Active Champion
2. Silhouette Score
3. Davies–Bouldin Score
4. Inertia
5. Number of Clusters

Nguồn:

```text
mlops.model_registry
mlops.model_metrics
gold.gold_cluster_profiles
```

Chỉ lấy metric của:

```text
model_name = 'segmentation_model'
selected model_version
```

## 8.2 Cluster Distribution

Nguồn:

```text
gold.gold_listing_cluster_assignments
```

Vẽ bar chart:

```text
cluster_id hoặc cluster_name
listing_count
```

Lọc theo selected model version.

## 8.3 Cluster Profiles

Nguồn:

```text
gold.gold_cluster_profiles
```

Hiển thị table hoặc chart các profile theo cluster.

Chỉ dùng những cột thực sự tồn tại trong bảng.

Không hard-code profile columns khi chưa kiểm tra schema.

## 8.4 Segmentation Metric Trend

Nguồn:

```text
mlops.model_metrics
mlops.model_runs
```

Vẽ trend:

```text
silhouette_score
davies_bouldin_score
inertia
```

## 8.5 Registry và Recent Runs

Tái sử dụng component của Price Model nhưng lọc:

```text
model_name = 'segmentation_model'
```

# 9. Data access

Rà soát cơ chế kết nối database hiện có trong `app/`.

Phải tái sử dụng:

* connection helper;
* repository;
* query service;
* cache function;

nếu đã tồn tại.

Không tạo kết nối MotherDuck mới rải rác trong page.

Có thể tạo trong `app/`:

```text
app/services/model_performance_service.py
```

với các hàm đọc dữ liệu, ví dụ:

```python
get_model_registry(model_name: str)
get_model_runs(model_name: str, date_from, date_to)
get_model_metrics(model_name: str, model_version: str)
get_price_evaluation_predictions(model_version: str)
get_feature_importance(model_version: str)
get_cluster_assignments(model_version: str)
get_cluster_profiles(model_version: str)
```

Yêu cầu:

* query parameterized;
* không dùng `SELECT *` nếu không cần;
* không sửa database;
* không ghi dữ liệu;
* xử lý bảng rỗng;
* xử lý bảng chưa tồn tại;
* xử lý connection error bằng thông báo UI rõ ràng.

Dùng `st.cache_data` với TTL hợp lý cho read query nếu app hiện tại đã dùng caching.

# 10. UI components

Có thể tạo reusable components trong:

```text
app/components/
```

Ví dụ:

```text
metric_card.py
status_badge.py
empty_state.py
section_card.py
model_tables.py
```

Nhưng không tách file quá mức.

Ưu tiên các helper:

```python
render_metric_card(...)
render_status_badge(...)
render_empty_state(...)
render_registry_table(...)
render_run_table(...)
```

# 11. Plotly styling

Tất cả biểu đồ phải dùng design tokens.

Cấu hình chung:

```python
fig.update_layout(
    paper_bgcolor=DESIGN_TOKENS["color_surface"],
    plot_bgcolor=DESIGN_TOKENS["color_surface"],
    font={
        "family": DESIGN_TOKENS["font_family"],
        "color": DESIGN_TOKENS["color_text_primary"],
    },
    margin={"l": 20, "r": 20, "t": 40, "b": 20},
    hoverlabel={
        "bgcolor": DESIGN_TOKENS["color_surface"],
        "font_color": DESIGN_TOKENS["color_text_primary"],
    },
)
```

Yêu cầu:

* gridline nhẹ;
* không dùng màu mặc định ngẫu nhiên;
* legend gọn;
* height đồng đều;
* `use_container_width=True`;
* không tạo biểu đồ quá cao.

# 12. Responsive layout

Dùng `st.columns` theo bố cục:

```text
KPI: 5 columns
Main charts: 2 columns
Lower section: 2 hoặc 3 columns
```

Không cố định pixel width.

Trang phải đọc được trên màn hình laptop phổ biến.

# 13. Empty, loading và error states

Mỗi section phải xử lý:

```text
No data
Table not available
No Champion
No successful run
No SHAP data
Database connection failed
```

Không để traceback hiển thị trực tiếp cho người dùng.

Có thể dùng:

```python
st.info(...)
st.warning(...)
st.error(...)
```

Thông báo phải bằng tiếng Anh.

# 14. Không tạo số liệu giả

Không hard-code:

```text
RMSE = 0.423
MAE = 0.289
R2 = 0.684
```

Các số trong mockup chỉ là ví dụ hình ảnh.

Giao diện thực tế phải đọc dữ liệu từ database.

Chỉ được dùng mock data khi app hiện tại đã có explicit demo mode. Nếu có demo mode, phải tách rõ khỏi production query.

# 15. Không được làm

* Không sửa navigation chính.
* Không sửa file ngoài `app/`.
* Không sửa Dagster.
* Không sửa dbt.
* Không sửa ML pipeline.
* Không sửa registry backend.
* Không thêm logic promote model.
* Không thêm logic retraining.
* Không ghi dữ liệu vào MotherDuck.
* Không thay đổi schema.
* Không hard-code metrics.
* Không thay đổi các tab khác trong Model Lab ngoài phần cần thiết.
* Không cài thêm package nếu package hiện có đã đủ.
* Không sửa `pyproject.toml` hoặc lock file.

# 16. Kiểm tra

Sau khi sửa, chạy các kiểm tra phù hợp hiện có trong project.

Tối thiểu:

* import page không lỗi;
* app khởi động được;
* tab Model Performance render được khi dữ liệu có;
* tab render empty state khi query trả về rỗng;
* filter thay đổi đúng model version;
* Price và Segmentation không trộn dữ liệu;
* không có file nào ngoài `app/` bị thay đổi.

Kiểm tra Git:

```powershell
git status --short
```

Nếu có file ngoài `app/` bị sửa, phải revert các file đó.

# 17. Kết quả cần báo cáo

Báo cáo ngắn:

1. Danh sách file trong `app/` đã sửa hoặc tạo.
2. Design token đã tạo hoặc tái sử dụng.
3. Các section đã triển khai trong Price Model.
4. Các section đã triển khai trong Segmentation Model.
5. Các query/table được sử dụng.
6. Empty/error states đã xử lý.
7. Command chạy Streamlit.
8. Xác nhận không sửa file ngoài `app/`.

Hãy trực tiếp chỉnh sửa code, không chỉ mô tả giải pháp.