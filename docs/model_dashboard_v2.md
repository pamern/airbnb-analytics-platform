Hãy trực tiếp chỉnh sửa giao diện **Model Performance** trong:

```text
app/pages/03_Model_Lab.py
```

hoặc đúng file tương ứng trong `app/` nếu cấu trúc thực tế khác.

Chỉ được sửa file bên trong:

```text
app/
```

Không được sửa bất kỳ logic hoặc file nào ngoài `app/`.

Giữ nguyên navigation chính hiện tại.

# 1. Bỏ điều hướng trùng giữa selectbox và tabs

Hiện tại người dùng chọn:

```text
Price Model
Segmentation Model
```

trong selectbox nhưng vẫn phải bấm thêm tab tương ứng.

Hãy bỏ tabs `Price Model` / `Segmentation Model`.

Chỉ giữ một selector duy nhất:

```python
model_type = st.selectbox(
    "Model",
    ["Price Model", "Segmentation Model"],
    key="model_performance_model_type",
)
```

Hoặc dùng `st.segmented_control` nếu Streamlit version hiện tại hỗ trợ ổn định.

Render conditionally:

```python
if model_type == "Price Model":
    render_price_model_performance(...)
else:
    render_segmentation_model_performance(...)
```

Khi đổi selector, giao diện phải tự chuyển ngay sang dashboard tương ứng.

Các filter còn lại như:

```text
Stage
Model Version
Run Type
Date Range
```

phải tự cập nhật option phù hợp theo model đã chọn.

Không hiển thị thêm title tab trùng lặp bên dưới.

# 2. Cải thiện Predicted vs Actual

Giữ dữ liệu thật, không xóa outlier khỏi metric.

Bổ sung hai control:

```text
Display Scale
Display Range
```

## Display Scale

```text
Log Price
Raw Price
```

Mặc định:

```text
Log Price
```

Nếu chọn Log Price:

```python
x = np.log1p(actual_price)
y = np.log1p(predicted_price)
```

Axis label:

```text
Actual Log Price
Predicted Log Price
```

Nếu chọn Raw Price:

```text
Actual Price
Predicted Price
```

## Display Range

```text
P95
P99
All
```

Mặc định:

```text
P99
```

Với P95 hoặc P99:

* chỉ giới hạn vùng hiển thị biểu đồ;
* không loại các dòng khỏi metric tổng;
* hiển thị caption số lượng điểm đang được hiển thị và số outlier nằm ngoài vùng nhìn.

Luôn giữ đường tham chiếu:

```text
y = x
```

Thêm annotation hoặc warning nếu tỷ lệ underprediction ở nhóm giá cao lớn.

Ví dụ:

```text
The model tends to underpredict extreme high-price listings.
```

Tính thêm các chỉ số nhỏ phía trên hoặc dưới chart:

```text
Underprediction Rate
Median Residual
P90 Absolute Error
```

Không hard-code số liệu.

# 3. Residual Distribution

Residual vẫn tính:

```python
residual = predicted_price - actual_price
```

Nếu display đang ở Log Price, có thể cho phép residual chart dùng:

```text
Raw Residual
Log Residual
```

nhưng mặc định giữ Raw Residual.

Thêm:

* vertical line tại `0`;
* median residual line;
* caption giải thích dấu:

  ```text
  Negative residual means underprediction.
  Positive residual means overprediction.
  ```

Không để một outlier làm toàn bộ histogram bị dồn.

Có thể dùng percentile range cho chart display, nhưng không xóa dữ liệu khỏi metric.

# 4. Bổ sung Price Error by Price Band

Thêm một chart mới trong Price Model:

```text
Error by Price Band
```

Chia actual price theo các band phù hợp, ví dụ:

```text
Low
Mid
High
Premium
Extreme
```

Hoặc dùng quantile-based bins.

Hiển thị ít nhất:

```text
MAE
Median Absolute Error
Underprediction Rate
Sample Count
```

Mục tiêu là cho thấy model hoạt động kém ở nhóm giá nào.

Không hard-code ngưỡng nếu có thể dùng quantile.

# 5. Bổ sung PCA Cluster Projection

Trong Segmentation Model, thêm section:

```text
PCA Cluster Projection
```

Dữ liệu cần:

```text
gold.gold_cluster_model_features
gold.gold_listing_cluster_assignments
```

Chỉ thực hiện trong `app/`.

Không sửa ML pipeline hoặc artifact.

Flow:

```text
load selected model version assignments
→ join feature table theo listing_id
→ lấy đúng feature clustering
→ preprocess trong app ở mức phù hợp để visualization
→ PCA(n_components=2)
→ Plotly scatter
```

Nếu trong app có thể load persisted preprocessing artifact an toàn bằng helper hiện tại thì tái sử dụng.

Nếu không, chỉ dùng một preprocessing visualization độc lập trong app:

* One-Hot categorical;
* StandardScaler numeric;
* PCA 2 components.

Phải ghi chú rõ:

```text
PCA is used only for two-dimensional visualization.
Cluster assignments come from the persisted KMeans model.
```

Biểu đồ:

```text
X = PCA Component 1
Y = PCA Component 2
Color = cluster_id hoặc cluster_name
```

Tooltip:

```text
listing_id
cluster_id
cluster_name nếu có
distance_to_centroid nếu có
```

Giới hạn tối đa khoảng 2.000–3.000 listing để tránh chậm.

Dùng `st.cache_data`.

Hiển thị:

```text
Explained variance PC1
Explained variance PC2
```

Nếu thiếu dữ liệu hoặc join rỗng, hiển thị empty state bằng tiếng Anh.

# 6. Mở rộng SHAP để thể hiện chiều tác động

Giữ biểu đồ hiện tại:

```text
Global SHAP Feature Importance
```

vì nó trả lời feature nào quan trọng.

Bổ sung dữ liệu chi tiết từ artifact:

```text
shap_sample_values.parquet
```

Artifact path lấy từ model registry hoặc helper hiện có trong `app/`.

Không sửa artifact backend.

## 6.1 SHAP Beeswarm

Thêm section:

```text
SHAP Impact Overview
```

Hiển thị beeswarm hoặc scatter tương đương:

```text
X = shap_value
Y = source_feature hoặc feature_name
Color = feature_value
```

Chỉ dùng top 10–15 feature.

Giải thích:

```text
Positive SHAP values push the predicted log-price upward.
Negative SHAP values push it downward.
```

Nếu categorical feature khó tô màu theo numeric value, có thể dùng màu trung tính và category trong hover.

## 6.2 SHAP Dependence Plot

Thêm selector:

```text
Feature to explain
```

Với numeric feature:

```text
X = feature_value
Y = shap_value
```

Với categorical feature:

* group theo category;
* hiển thị:

  ```text
  Mean SHAP
  Median SHAP
  Sample Count
  ```

Không dùng category code như biến liên tục.

## 6.3 SHAP Direction Summary

Thêm bảng:

```text
Feature
Mean |SHAP|
Mean SHAP
Positive Impact Rate
Negative Impact Rate
Sample Count
```

Công thức:

```python
positive_impact_rate = (shap_value > 0).mean()
negative_impact_rate = (shap_value < 0).mean()
```

Không dùng `mean_shap` để xếp hạng importance.

Xếp hạng theo:

```text
Mean |SHAP|
```

Ghi chú rõ SHAP đang giải thích trên:

```text
log-price scale
```

Không diễn giải trực tiếp thành THB.

# 7. Layout mới

## Price Model

Bố cục đề xuất:

```text
KPI cards

Display controls

Predicted vs Actual
Residual Distribution

Error by Price Band
Metric Trend

Global SHAP Feature Importance
SHAP Impact Overview

SHAP Dependence Plot
SHAP Direction Summary

Model Registry
Recent Runs
```

## Segmentation Model

```text
KPI cards

PCA Cluster Projection
Cluster Distribution

Cluster Profiles
Segmentation Metric Trend

Model Registry
Recent Runs
```

# 8. Design consistency

Tiếp tục dùng design tokens đã có trong `app/`.

Không hard-code màu mới nếu token đã tồn tại.

Plotly charts phải:

* dùng cùng font;
* dùng cùng surface/background;
* dùng cùng primary color;
* có margin và height đồng nhất;
* `use_container_width=True`;
* có gridline nhẹ;
* không dùng màu mặc định ngẫu nhiên.

# 9. Data loading và error handling

Tái sử dụng data service/helper hiện có trong `app/`.

Có thể bổ sung hàm mới trong:

```text
app/services/
```

nhưng không sửa ngoài `app/`.

Bổ sung helper nếu cần:

```python
get_shap_sample_artifact(model_version)
get_price_predictions(model_version)
get_cluster_pca_data(model_version)
```

Phải xử lý:

```text
artifact không tồn tại
Parquet không đọc được
không có SHAP sample
không có assignment
không có feature table
join rỗng
```

Không hiển thị traceback trực tiếp.

Thông báo UI bằng tiếng Anh.

# 10. Không được làm

* Không sửa navigation chính.
* Không sửa file ngoài `app/`.
* Không sửa ML pipeline.
* Không sửa dbt.
* Không sửa Dagster.
* Không sửa schema database.
* Không thay đổi artifact generation.
* Không tính lại cluster assignment.
* Không retrain PCA/KMeans trong backend.
* Không xóa outlier khỏi metric.
* Không hard-code metrics.
* Không thêm dependency mới ngoài project nếu không thật sự cần.
* Không sửa lock file hoặc `pyproject.toml`.

# 11. Kiểm tra cuối

Sau khi sửa:

* đổi Model selector phải tự render đúng giao diện;
* không còn tabs trùng lặp;
* Price Model không hiển thị component Segmentation;
* Segmentation Model không hiển thị component Price;
* scatter plot đọc được ở Log Price và Raw Price;
* P95/P99/All hoạt động;
* PCA chart render được hoặc có empty state;
* SHAP importance, beeswarm, dependence và direction summary hoạt động;
* app không crash khi artifact SHAP không tồn tại;
* không có file ngoài `app/` bị sửa.

Chạy:

```powershell
git status --short
```

Nếu có file ngoài `app/` bị thay đổi, revert chúng.

# 12. Báo cáo ngắn

Sau khi sửa, báo cáo:

1. File trong `app/` đã sửa hoặc tạo.
2. Cách điều hướng Model selector mới.
3. Cách xử lý outlier trên Predicted vs Actual.
4. PCA Cluster Projection đã thêm.
5. Các phần SHAP mới.
6. Empty/error states.
7. Xác nhận không sửa ngoài `app/`.

Hãy trực tiếp chỉnh sửa code, không chỉ mô tả.
