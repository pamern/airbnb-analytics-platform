Hãy rà soát toàn bộ code hiện tại liên quan đến:

* huấn luyện mô hình dự báo giá bằng `XGBRegressor`;
* pipeline preprocessing và tên feature sau transform;
* cơ chế tính feature importance hiện tại;
* lưu metadata vào `mlops.model_feature_importance`;
* lưu artifact của model;
* Streamlit Model Performance Dashboard;
* trang dự báo giá nếu hiện tại đã có phần giải thích prediction.

Mục tiêu là thay cơ chế feature importance chính của XGBoost sang **SHAP**, đồng thời lưu đủ dữ liệu mẫu để có thể phân tích:

1. Feature nào quan trọng nhất với model.
2. Giá trị feature cao hoặc thấp thường làm prediction tăng hay giảm.
3. Mức độ và chiều tác động của feature trên từng listing mẫu.
4. Giải thích cục bộ cho một prediction cụ thể.

Không phá vỡ logic training, evaluation, artifact hoặc model registry hiện tại.

# 1. Phạm vi chỉnh sửa

Pipeline hiện tại chỉ sử dụng:

```text
XGBRegressor
```

Chỉ triển khai SHAP cho model này.

Không cần hỗ trợ:

```text
HistGradientBoostingRegressor
RandomForestRegressor
CatBoostRegressor
```

Không tạo abstraction phức tạp để hỗ trợ các model chưa được sử dụng.

# 2. Kết quả SHAP cần tạo

Pipeline phải tạo ba nhóm kết quả:

## 2.1 Global importance

Trả lời:

> Feature nào quan trọng nhất với model?

Cách tính:

```python
mean_abs_shap = np.abs(shap_values).mean(axis=0)
```

Lưu hai mức:

```text
TRANSFORMED
ORIGINAL
```

Trong đó:

* `TRANSFORMED`: từng cột sau One-Hot Encoding.
* `ORIGINAL`: gộp các cột One-Hot về feature đầu vào gốc.

## 2.2 SHAP sample chi tiết

Trả lời:

> Với từng giá trị feature trong tập mẫu, feature đó kéo prediction tăng hay giảm?

Mỗi record cần có tối thiểu:

```text
sample_id
listing_id
run_id
model_name
model_version
feature_name
source_feature
feature_level
feature_value
feature_value_display
shap_value
direction
base_value
prediction_log_price
predicted_price
dataset_split
```

Trong đó:

```text
direction = INCREASE nếu shap_value > 0
direction = DECREASE nếu shap_value < 0
direction = NEUTRAL nếu shap_value = 0
```

SHAP sample phải cho phép tạo:

* SHAP beeswarm plot;
* SHAP dependence plot;
* phân tích feature value cao/thấp;
* phân tích chiều tác động;
* local explanation cho listing thuộc sample.

## 2.3 Local explanation helper

Trả lời:

> Vì sao model đưa ra prediction cho một listing cụ thể?

Tạo helper tái sử dụng:

```python
explain_single_prediction(
    fitted_pipeline,
    raw_input,
)
```

Không cần lưu local explanation của toàn bộ batch prediction vào database.

# 3. Không dùng native XGBoost importance làm kết quả chính

Không sử dụng các cơ chế sau làm feature importance chính:

```python
model.feature_importances_
model.get_booster().get_score(importance_type="gain")
```

Có thể giữ native importance làm dữ liệu tham khảo nếu code hiện tại đã dùng, nhưng kết quả SHAP chính phải được đánh dấu:

```text
importance_method = 'shap'
```

Streamlit không được fallback ngầm từ SHAP sang native importance.

# 4. SHAP explainer

Vì model là `XGBRegressor`, sử dụng:

```python
shap.TreeExplainer(model)
```

Có thể sử dụng:

```python
shap.Explainer(model)
```

chỉ khi xác nhận explainer thực tế là tree-based và tương thích với XGBoost.

Không sử dụng:

```text
KernelExplainer
```

Lưu metadata:

```text
explainer_type = TreeExplainer
explanation_output_space = log_price
```

# 5. Dataset dùng để tính SHAP

Không tính SHAP trên toàn bộ tập train hoặc toàn bộ dataset.

Cấu hình:

```python
SHAP_SAMPLE_SIZE = 1000
SHAP_RANDOM_STATE = 42
```

Yêu cầu:

* Ưu tiên lấy mẫu từ `X_test`.
* Nếu tập test nhỏ hơn 1000 dòng thì dùng toàn bộ.
* Sampling phải reproducible.
* Giữ lại index để liên kết với `listing_id`.
* Không thay đổi train/test split hiện tại.
* Không đưa target vào input SHAP.
* Không fit lại preprocessor.
* Dùng chính preprocessor đã fit trong training pipeline.

Ví dụ:

```python
sample_size = min(SHAP_SAMPLE_SIZE, len(X_test))

sample_indices = X_test.sample(
    n=sample_size,
    random_state=SHAP_RANDOM_STATE,
).index

X_shap_raw = X_test.loc[sample_indices]
```

Nếu `listing_id` đã được tách khỏi model features, lấy lại từ metadata bằng cùng index:

```python
listing_ids = test_metadata.loc[sample_indices, "listing_id"]
```

Không đưa `listing_id` vào preprocessor hoặc model.

# 6. Transform SHAP sample

Nếu model và preprocessor nằm trong một pipeline:

```python
preprocessor = fitted_pipeline.named_steps["preprocessor"]
model = fitted_pipeline.named_steps["model"]
```

Tên step phải lấy theo code thực tế, không hard-code nếu project đang dùng tên khác.

Transform:

```python
X_shap_transformed = preprocessor.transform(X_shap_raw)
```

Nếu output là sparse matrix:

* ưu tiên truyền sparse input trực tiếp nếu SHAP version hiện tại hỗ trợ;
* chỉ chuyển tối đa SHAP sample sang dense nếu cần;
* không chuyển toàn bộ train/test dataset sang dense.

Ví dụ:

```python
from scipy import sparse

if sparse.issparse(X_shap_transformed):
    X_shap_input = X_shap_transformed.toarray()
else:
    X_shap_input = np.asarray(X_shap_transformed)
```

# 7. Lấy đúng tên feature sau preprocessing

Sử dụng:

```python
feature_names = preprocessor.get_feature_names_out()
```

Yêu cầu:

* Không dùng tên giả như `feature_0`.
* Giữ nguyên thứ tự feature.
* Hỗ trợ numeric, boolean, One-Hot Encoding và passthrough.
* Không tự sắp xếp lại feature names.

Validate:

```python
len(feature_names) == X_shap_input.shape[1]
```

Nếu không khớp, raise lỗi có:

```text
run_id
model_version
feature_name_count
transformed_column_count
```

Không fallback sang tên feature giả.

# 8. Mapping transformed feature về source feature

Phải tạo mapping chính xác:

```text
transformed_feature → source_feature
```

Ví dụ:

```text
categorical__neighbourhood_Vadhana → neighbourhood
categorical__room_type_Private room → room_type
numeric__accommodates              → accommodates
```

Không xác định source feature bằng cách cắt chuỗi đơn giản theo `_`, vì tên cột và category có thể chứa dấu gạch dưới.

Mapping phải dựa trên:

* cấu hình `ColumnTransformer`;
* danh sách input columns của từng transformer;
* `OneHotEncoder.categories_`;
* `OneHotEncoder.get_feature_names_out()`;
* numeric columns;
* boolean columns;
* passthrough columns.

Mỗi transformed feature phải map về đúng một source feature.

Nếu không map được, raise lỗi rõ ràng.

# 9. Tính SHAP values

Sau khi model fit và evaluation thành công:

```python
explainer = shap.TreeExplainer(model)
shap_output = explainer(X_shap_input)
```

Hỗ trợ nhiều version SHAP.

Nếu là `shap.Explanation`:

```python
shap_values = np.asarray(shap_output.values)
base_values = np.asarray(shap_output.base_values)
```

Nếu API trả NumPy array:

```python
shap_values = np.asarray(shap_output)
base_values = np.asarray(explainer.expected_value)
```

Nếu có dimension dư bằng 1, chỉ squeeze dimension đó an toàn.

Validate:

```python
shap_values.shape[0] == X_shap_input.shape[0]
shap_values.shape[1] == X_shap_input.shape[1]
```

Đối với từng sample, kiểm tra tính cộng:

```python
base_value + shap_values.sum(axis=1)
≈ model.predict(X_shap_input)
```

Dùng tolerance phù hợp với floating-point.

# 10. Global transformed importance

Tính:

```python
mean_abs_shap = np.abs(shap_values).mean(axis=0)
```

Kết quả:

```text
feature_name
source_feature
feature_level = TRANSFORMED
importance_value
importance_rank
importance_method = shap
```

Sắp xếp giảm dần và đánh rank từ 1.

# 11. Global original importance

Gộp transformed importance về feature gốc:

```python
original_importance = (
    transformed_importance
    .groupby("source_feature", as_index=False)["importance_value"]
    .sum()
)
```

Không dùng trung bình.

Kết quả:

```text
feature_name = source_feature
source_feature
feature_level = ORIGINAL
importance_value
importance_rank
importance_method = shap
```

Lưu ý: tổng mean absolute SHAP của các One-Hot columns phù hợp để tổng hợp mức đóng góp của categorical feature, nhưng categorical feature có nhiều category vẫn có thể nhận tổng importance lớn hơn. Ghi chú giới hạn này trong báo cáo kỹ thuật.

# 12. Tạo SHAP sample chi tiết

Tạo file dạng long format, mỗi dòng tương ứng:

```text
một sample × một transformed feature
```

Cấu trúc:

```text
sample_id
listing_id
run_id
model_name
model_version
feature_name
source_feature
feature_level
feature_value
feature_value_display
shap_value
abs_shap_value
direction
base_value
prediction_log_price
predicted_price
dataset_split
```

Trong đó:

```python
abs_shap_value = abs(shap_value)
predicted_price = np.expm1(prediction_log_price)
```

`feature_value` là giá trị sau transform dùng trực tiếp bởi model.

`feature_value_display` là giá trị dễ hiểu hơn nếu có thể xác định an toàn:

* Numeric: giá trị raw ban đầu.
* Boolean: `True` hoặc `False`.
* One-Hot: tên category active.
* Missing indicator: biểu diễn rõ giá trị thiếu.
* Không tự suy đoán giá trị nếu mapping không chắc chắn.

Đối với One-Hot transformed column:

```text
feature_value = 0 hoặc 1
feature_value_display = category tương ứng nếu active
```

Ngoài transformed long format, có thể tạo thêm một bản gộp theo source feature để dùng cho local explanation, nhưng không cộng SHAP một cách làm mất thông tin category nếu dashboard cần hiển thị chi tiết.

# 13. Lưu dữ liệu SHAP

## 13.1 Database

Chỉ lưu global importance vào:

```text
mlops.model_feature_importance
```

Schema:

```text
run_id
model_name
model_version
feature_name
source_feature
feature_level
importance_value
importance_rank
importance_method
created_at
```

Không lưu toàn bộ SHAP sample chi tiết vào MotherDuck, trừ khi project hiện tại đã có yêu cầu rõ ràng.

Lý do: sample 1000 dòng nhân với hàng chục hoặc hàng trăm transformed features có thể tạo rất nhiều record metadata.

## 13.2 Artifact

Lưu SHAP sample chi tiết dưới dạng Parquet:

```text
ml/artifacts/price_modeling/<model_version>/
├── model.joblib
├── preprocessor.joblib
├── shap_original_importance.csv
├── shap_transformed_importance.csv
├── shap_sample_values.parquet
├── shap_sample_summary.json
└── feature_names.json
```

Nếu model và preprocessor đang nằm chung trong một pipeline artifact, giữ nguyên cách hiện tại.

Không cần tách model/preprocessor nếu không phù hợp kiến trúc project.

Không lưu absolute path vào database.

Sử dụng relative path:

```text
ml/artifacts/price_modeling/<model_version>/...
```

# 14. SHAP sample summary

Lưu:

```json
{
  "run_id": "...",
  "model_name": "...",
  "model_version": "...",
  "sample_size": 1000,
  "transformed_feature_count": 0,
  "original_feature_count": 0,
  "dataset_split": "TEST",
  "random_state": 42,
  "explainer_type": "TreeExplainer",
  "importance_method": "shap",
  "explanation_output_space": "log_price",
  "detail_artifact": "ml/artifacts/price_modeling/<model_version>/shap_sample_values.parquet",
  "created_at": "..."
}
```

Không lưu hard path.

# 15. Xử lý target log_price

Model dự báo:

```text
log_price = log1p(price)
```

Vì vậy:

```text
base_value
shap_value
prediction
```

đều nằm trên không gian `log_price`.

Phải lưu:

```text
explanation_output_space = log_price
```

Không diễn giải:

```text
SHAP value = 0.2
```

thành:

```text
giá tăng 0.2 THB
```

Quan hệ đúng:

```text
base_value + tổng shap_value
≈ prediction_log_price
```

Prediction cuối:

```python
predicted_price = np.expm1(prediction_log_price)
```

Không back-transform từng SHAP value riêng lẻ rồi cộng lại vì `expm1` là hàm phi tuyến.

Có thể diễn giải SHAP theo hướng tương đối:

```text
SHAP dương  → đẩy prediction cao hơn giá trị nền
SHAP âm     → kéo prediction thấp hơn giá trị nền
```

# 16. Helper local explanation

Tạo helper:

```python
explain_single_prediction(
    fitted_pipeline,
    raw_input,
)
```

Helper phải:

1. Validate raw input schema.
2. Transform bằng fitted preprocessor.
3. Lấy đúng transformed feature names.
4. Map về source feature.
5. Tính SHAP bằng `TreeExplainer`.
6. Kiểm tra tính cộng SHAP.
7. Trả contribution đã sắp xếp theo `abs(shap_value)`.

Output:

```text
base_value
prediction_log_price
predicted_price
feature_name
source_feature
feature_value
feature_value_display
shap_value
abs_shap_value
direction
importance_rank
explanation_output_space
```

Không lưu local explanation cho toàn bộ batch prediction.

Local SHAP chỉ tính khi người dùng mở hoặc yêu cầu giải thích một prediction cụ thể.

# 17. Streamlit Model Performance Dashboard

Dashboard phải đọc global importance từ:

```text
mlops.model_feature_importance
```

Điều kiện:

```sql
importance_method = 'shap'
AND feature_level = 'ORIGINAL'
AND model_version = ?
```

Hiển thị:

1. Top 10 hoặc Top 15 feature theo mean absolute SHAP.
2. Bar chart theo `importance_value`.
3. Model version và run ID.
4. Ghi chú:

   ```text
   Mean absolute SHAP value trên mẫu của tập TEST.
   ```
5. Ghi chú:

   ```text
   SHAP values giải thích prediction trên log_price scale.
   ```

Không trộn nhiều model version hoặc nhiều run.

Nếu chưa có dữ liệu:

```text
Chưa có SHAP feature importance cho model này.
Hãy chạy lại price retraining job để tạo dữ liệu.
```

Không fallback sang gain.

# 18. Biểu đồ chiều tác động trên Streamlit

Nếu artifact `shap_sample_values.parquet` tồn tại, bổ sung phần phân tích SHAP sample.

Tối thiểu hỗ trợ:

## 18.1 SHAP beeswarm hoặc biểu đồ tương đương

Hiển thị:

* feature value;
* SHAP value;
* chiều tăng hoặc giảm;
* top feature được chọn.

Không bắt buộc dùng trực tiếp `shap.summary_plot` nếu khó tích hợp với Streamlit. Có thể xây biểu đồ Plotly/Matplotlib từ dữ liệu Parquet.

## 18.2 Dependence plot

Cho phép chọn một feature gốc.

Biểu đồ:

```text
trục X = feature value
trục Y = SHAP value
```

Mục tiêu:

* biết giá trị thấp/cao làm prediction tăng hay giảm;
* phát hiện tác động phi tuyến;
* phát hiện ngưỡng thay đổi.

Đối với categorical feature, có thể hiển thị:

```text
category
mean SHAP
median SHAP
sample count
```

Không coi category code là biến số liên tục.

## 18.3 Direction summary

Tạo bảng cho mỗi source feature:

```text
source_feature
mean_abs_shap
mean_shap
positive_effect_rate
negative_effect_rate
sample_count
```

Trong đó:

```python
positive_effect_rate = mean(shap_value > 0)
negative_effect_rate = mean(shap_value < 0)
```

Bảng này chỉ mang tính mô tả trên SHAP sample, không thay thế dependence plot.

Không dùng riêng `mean_shap` để xếp hạng importance vì giá trị dương và âm có thể triệt tiêu nhau.

# 19. Lưu `mlops.model_feature_importance`

Mỗi lần retraining:

1. SHAP chỉ chạy sau khi training và evaluation thành công.
2. Original và transformed importance phải được validate trước khi ghi.
3. Xóa hoặc upsert đúng record của cùng `run_id`.
4. Không ảnh hưởng run khác.
5. Không ghi dữ liệu một phần.
6. Ghi database trong transaction nếu flow hiện tại hỗ trợ.

Unique logic:

```text
run_id
+ feature_name
+ importance_method
+ feature_level
```

Nếu SHAP thất bại:

* không đăng ký model thành `CANDIDATE`;
* cập nhật `mlops.model_runs.status = FAILED`;
* lưu error message;
* raise lại exception để Dagster đánh dấu failure;
* không thay đổi Champion;
* không để lại artifact SHAP chưa hoàn chỉnh.

Có thể ghi artifact vào thư mục tạm trước, sau đó rename/move sang thư mục version chính thức khi toàn bộ SHAP pipeline thành công.

# 20. Validation

Bổ sung validation:

* SHAP sample không rỗng.
* Sample size không vượt quá `SHAP_SAMPLE_SIZE`.
* Không có duplicate sample index.
* `listing_id` map đúng với sample index.
* Số feature names bằng số transformed columns.
* Số SHAP columns bằng số transformed columns.
* Số SHAP rows bằng số sample rows.
* Base value có shape hợp lệ.
* Phép cộng SHAP khớp prediction trong tolerance.
* Không có NaN hoặc infinity trong importance.
* Không có NaN hoặc infinity trong SHAP values.
* Tất cả global `importance_value >= 0`.
* Tổng global importance lớn hơn 0.
* Mỗi transformed feature map về đúng một source feature.
* `importance_rank` không trùng trong cùng `run_id + feature_level`.
* Không duplicate global record theo:

  ```text
  run_id + feature_name + importance_method + feature_level
  ```
* Không duplicate detail record theo:

  ```text
  sample_id + feature_name + feature_level
  ```
* `importance_method = shap`.
* `feature_level` chỉ gồm:

  ```text
  ORIGINAL
  TRANSFORMED
  ```
* Artifact Parquet đọc lại được sau khi ghi.
* Số record trong Parquet bằng:

  ```text
  sample_size × transformed_feature_count
  ```

  nếu chỉ lưu transformed long format.

# 21. Flow mới của price_retraining_job

```text
dbt price training features
→ load training dataset và metadata listing_id
→ train/test split hiện tại
→ fit preprocessing + XGBRegressor
→ evaluate RMSE, MAE, R2
→ validate model artifact
→ lấy mẫu tối đa 1000 dòng từ X_test
→ giữ mapping sample index với listing_id
→ transform SHAP sample
→ lấy transformed feature names
→ map transformed feature về source feature
→ tính SHAP bằng TreeExplainer
→ validate SHAP additivity
→ tạo transformed global importance
→ tạo original global importance
→ tạo SHAP detail long-format
→ validate toàn bộ SHAP result
→ lưu global importance CSV
→ lưu SHAP sample Parquet
→ lưu summary JSON
→ ghi mlops.model_feature_importance
→ ghi metrics và run metadata
→ đăng ký model thành CANDIDATE
```

Không tự động đổi Champion.

Nếu bất kỳ bước SHAP bắt buộc nào thất bại:

```text
run → FAILED
model không được đăng ký CANDIDATE
Champion hiện tại giữ nguyên
```

# 22. Không được làm

* Không sửa notebook EDA.
* Không thay đổi train/test split.
* Không thay đổi RMSE, MAE, R2.
* Không thay đổi hyperparameter XGBoost nếu không cần.
* Không đổi Champion.
* Không tự động promote model.
* Không tính SHAP trên target.
* Không tính SHAP trên toàn bộ dataset.
* Không lưu absolute path.
* Không dùng XGBoost gain làm importance chính.
* Không gọi global SHAP trong `price_prediction_job`.
* Không tính local SHAP cho toàn bộ batch prediction.
* Không lưu toàn bộ SHAP detail vào MotherDuck.
* Không diễn giải SHAP value trực tiếp thành THB.
* Không bổ sung model khác ngoài XGBoost.
* Không tạo abstraction phức tạp không cần thiết.

# 23. Kết quả cần trả về

Sau khi chỉnh sửa, báo cáo:

1. Danh sách file đã sửa hoặc tạo.
2. Helper tính global SHAP.
3. Helper tạo SHAP sample chi tiết.
4. Helper map transformed feature về source feature.
5. Helper local explanation.
6. Cách liên kết SHAP sample với `listing_id`.
7. Cách lấy feature names sau preprocessing.
8. Cách sample tập test.
9. Cách tính transformed importance.
10. Cách gộp original importance.
11. Cấu trúc `shap_sample_values.parquet`.
12. Cách lưu relative artifact path.
13. Cách ghi `mlops.model_feature_importance`.
14. Các biểu đồ SHAP được bổ sung trên dashboard.
15. Validation đã bổ sung.
16. Command chạy `price_retraining_job`.
17. Dependency hoặc version được cập nhật.
18. Giới hạn còn tồn tại.

Ví dụ query kiểm tra global importance:

```sql
SELECT
    run_id,
    model_name,
    model_version,
    feature_name,
    source_feature,
    feature_level,
    importance_value,
    importance_rank,
    importance_method
FROM mlops.model_feature_importance
WHERE model_version = ?
  AND importance_method = 'shap'
  AND feature_level = 'ORIGINAL'
ORDER BY importance_rank;
```

Không chỉ mô tả giải pháp. Hãy trực tiếp chỉnh sửa code trong repository và giữ nguyên các phần không liên quan.
