Hãy trực tiếp thiết kế và triển khai tab dự báo trong:

```text
app/pages/03_model_lab.py
```

Có thể đặt tên tab là:

```text
Price Prediction
```

Tên này rõ hơn `Prediction` vì trang tập trung vào dự báo giá listing.

Chỉ được sửa file bên trong:

```text
app/
```

Không sửa bất kỳ logic hoặc file nào ngoài `app/`.

Giữ nguyên navigation chính hiện tại.

# 1. Mục tiêu giao diện

Xây dựng tab dự báo giá theo bố cục đã chốt:

```text
Price Prediction
├── Listing Inputs
├── Prediction Result
├── Model Champion
├── Top Drivers
├── Comparable Listings
├── Prediction Notes
└── Price Position vs Market
```

Toàn bộ chữ hiển thị trên giao diện phải bằng tiếng Anh.

# 2. Bố cục tổng thể

Dùng layout hai cột:

```text
Left column  : Listing Inputs
Right column : Prediction Result + Model Champion + Insights
```

Tỷ lệ gợi ý:

```python
left_col, right_col = st.columns([0.95, 1.65], gap="large")
```

Không thay đổi sidebar navigation.

# 3. Listing Inputs

Tạo form nhập liệu chia theo section.

## Location

```text
Neighbourhood
Room Type
Property Group
```

## Capacity & Space

```text
Accommodates
Bedrooms
Bathrooms
Beds
```

## Booking Rules

```text
Minimum Nights
Maximum Nights
Instant Bookable
```

## Host Information

```text
Host Response Time
Host Response Rate
Host Acceptance Rate
Superhost
Host Listings Count
Host Total Listings Count
Calculated Host Listings Count
```

## Availability

```text
Availability 30
Availability 60
Availability 90
Availability 365
```

## Reviews

```text
Number of Reviews
Number of Reviews LTM
Reviews per Month
Review Scores Rating
Review Scores Accuracy
Review Scores Cleanliness
Review Scores Check-in
Review Scores Communication
Review Scores Location
Review Scores Value
```

Chỉ hiển thị field thực sự được model sử dụng.

Rà soát feature schema hiện tại trong `app/` hoặc helper có sẵn, không hard-code sai feature.

Dùng:

```python
with st.form("price_prediction_form"):
```

Buttons:

```text
Reset Inputs
Predict Price
```

`Predict Price` là primary button.

Validate:

* bedrooms, bathrooms, beds không âm;
* maximum nights >= minimum nights;
* rate nằm trong miền hợp lệ;
* review score nằm trong thang điểm thực tế;
* required categorical field không rỗng.

Không hiển thị traceback.

# 4. Model Champion header

Ở đầu phần kết quả, hiển thị:

```text
Active Model
Model Version
Stage
```

Chỉ dùng model:

```text
model_name = 'price_model'
stage = 'CHAMPION'
is_active = TRUE
```

Nếu không có Champion hoặc có nhiều Champion active:

* không cho chạy prediction;
* hiển thị error rõ ràng bằng tiếng Anh.

Không fallback sang Candidate.

# 5. Prediction Result

Sau khi bấm `Predict Price`, hiển thị:

```text
Predicted Nightly Price
Suggested Range
Confidence
```

Không hard-code giá trị.

Predicted price lấy từ model artifact Champion hiện tại.

Nếu model dự báo `log_price`, phải back-transform:

```python
predicted_price = np.expm1(predicted_log_price)
```

Không diễn giải SHAP contribution trực tiếp thành THB.

## Suggested Range

Nếu backend hiện tại đã có prediction interval thì dùng trực tiếp.

Nếu chưa có interval thật:

* không giả vờ là confidence interval thống kê;
* dùng range mô tả dựa trên residual distribution hoặc MAE nếu dữ liệu có sẵn;
* ghi chú rõ đây là estimated range.

Ví dụ:

```text
Estimated range based on historical model error.
```

## Confidence

Chỉ hiển thị nếu có rule rõ ràng.

Ví dụ dựa trên:

* khoảng cách với phân phối training;
* residual band;
* mức độ đầy đủ của input;
* số comparable listings.

Nếu chưa có logic đáng tin cậy, hiển thị:

```text
Confidence: Not available
```

Không hard-code `High`, `Medium`, `Low`.

# 6. Model Champion management

Bổ sung card:

```text
Model Champion
```

Hiển thị Champion hiện tại:

```text
Model Version
Run ID
Created At
Promoted At
RMSE
MAE
R²
```

Nguồn:

```text
mlops.model_registry
mlops.model_metrics
```

Bên dưới có:

```text
Select Candidate Version
Set as Champion
```

Candidate dropdown chỉ lấy:

```text
model_name = 'price_model'
stage = 'CANDIDATE'
is_active = FALSE
```

Khi người dùng bấm:

```text
Set as Champion
```

phải hiển thị confirm step:

```text
The current Champion will be archived and the selected Candidate will become active.
```

Chỉ sau khi xác nhận mới update.

Transaction logic:

```text
Current active Champion
→ ARCHIVED
→ is_active = FALSE

Selected Candidate
→ CHAMPION
→ is_active = TRUE
→ promoted_at = current timestamp
→ promoted_by = current user hoặc 'streamlit'
```

Không ảnh hưởng segmentation model.

Phải đảm bảo tối đa một active Champion cho `price_model`.

Nếu update thất bại:

* rollback;
* hiển thị error;
* không để registry ở trạng thái dở dang.

Chỉ viết code này trong `app/`, không sửa backend ngoài `app/`.

Nếu app hiện tại đã có service/repository database, tái sử dụng.

# 7. Top Drivers

Dùng local SHAP explanation cho prediction hiện tại.

Hiển thị hai nhóm:

```text
Top Positive Drivers
Top Negative Drivers
```

Mỗi dòng gồm:

```text
Feature
Feature Value
SHAP Value
Direction
```

Ví dụ:

```text
Neighbourhood = Vadhana   +0.28
Bedrooms = 2              +0.14
Minimum Nights = 30       -0.08
```

SHAP value đang ở:

```text
log-price scale
```

Ghi chú rõ:

```text
Positive values push the predicted log-price upward.
Negative values push it downward.
```

Không hiển thị SHAP value như số THB.

Chỉ lấy top 5 positive và top 5 negative.

# 8. Comparable Listings

Dùng dữ liệu hiện có từ:

```text
gold.gold_price_model_features
gold.gold_listing_price_predictions
```

hoặc bảng Gold phù hợp hiện có.

Comparable listing nên dựa trên:

* cùng neighbourhood;
* cùng room type;
* accommodates gần nhau;
* bedrooms/bathrooms gần nhau;
* actual price hoặc latest predicted price có sẵn.

Hiển thị tối đa 5–10 dòng:

```text
Listing ID
Neighbourhood
Room Type
Actual Price
Predicted Price
Difference
```

Không xây recommender phức tạp.

Nếu không có đủ dữ liệu:

```text
No comparable listings are available for the selected input.
```

# 9. Expected Segment

Nếu Segmentation Champion tồn tại, có thể hiển thị:

```text
Expected Segment
Cluster Name
```

Flow:

```text
raw input
→ load Segmentation Champion artifact
→ assign cluster
```

Chỉ thực hiện nếu các feature đầu vào đủ và helper hiện tại trong `app/` có thể tái sử dụng.

Nếu không thể tái sử dụng an toàn, hiển thị:

```text
Segment prediction is not available.
```

Không fit lại KMeans.

Không thay đổi cluster model.

# 10. Price Percentile và Market Position

Tính theo neighbourhood hoặc nhóm comparable listing.

Hiển thị:

```text
Price Percentile
Market Position
```

Ví dụ:

```text
72nd percentile
Above Median
```

Không hard-code.

Tính bằng predicted price so với phân phối giá của nhóm tham chiếu.

Nếu sample quá nhỏ, hiển thị:

```text
Insufficient market data
```

# 11. Price Position vs Market

Thêm biểu đồ ngang:

```text
Price Position vs Market
```

Hiển thị:

* min;
* Q1;
* median;
* Q3;
* max hoặc whisker phù hợp;
* predicted price marker.

Có thể dùng Plotly box plot hoặc custom horizontal distribution chart.

Nguồn so sánh ưu tiên:

```text
same neighbourhood + same room type
```

Nếu sample quá nhỏ, fallback chỉ về neighbourhood.

Phải ghi rõ nhóm tham chiếu đang sử dụng.

# 12. Prediction Notes

Sinh notes bằng rule-based explanation, không gọi LLM trong lần này.

Ví dụ:

```text
Larger capacity contributes positively to the estimate.
Low review volume slightly reduces the predicted price.
The selected neighbourhood is priced above the city median.
```

Notes phải dựa trên:

* SHAP local drivers;
* market percentile;
* comparable listings;
* missing input.

Không tạo nhận xét không có dữ liệu hỗ trợ.

# 13. Recent Prediction History

Có thể thêm section gọn ở cuối hoặc sidebar phải:

```text
Recent Predictions
```

Chỉ lưu trong session state hoặc đọc từ Gold nếu đã có logic.

Hiển thị:

```text
Time
Model Version
Predicted Price
Neighbourhood
Room Type
```

Không ghi dữ liệu mới vào bảng Gold nếu backend hiện tại không có flow ghi single prediction.

# 14. Data access

Tái sử dụng helper/service hiện có trong `app/`.

Có thể tạo thêm:

```text
app/services/price_prediction_service.py
```

Các hàm gợi ý:

```python
get_active_price_champion()
get_price_candidates()
set_price_champion(candidate_version, promoted_by)
load_price_model_artifact(model_version)
predict_single_listing(input_data)
explain_single_listing(input_data)
get_comparable_listings(input_data)
get_market_distribution(input_data)
get_price_model_metrics(model_version)
```

Yêu cầu:

* query parameterized;
* không dùng `SELECT *` không cần thiết;
* handle connection error;
* handle missing artifact;
* validate relative artifact path;
* không cho path traversal;
* cache read-only data hợp lý;
* không cache thao tác promotion.

# 15. Design consistency

Tái sử dụng design tokens hiện có trong `app/`.

Không tạo bộ màu mới nếu token đã tồn tại.

Dùng card style thống nhất cho:

* Listing Inputs;
* Prediction Result;
* Model Champion;
* Top Drivers;
* Comparable Listings;
* Prediction Notes;
* Price Position vs Market.

Toàn bộ chữ giao diện bằng tiếng Anh.

Plotly phải dùng token hiện có.

# 16. Empty và error states

Xử lý:

```text
No Champion found
Multiple active Champions found
Artifact missing
Artifact load failed
Prediction failed
SHAP explanation unavailable
No comparable listings
Insufficient market data
Candidate list empty
Promotion failed
```

Không hiển thị traceback.

# 17. Không được làm

* Không sửa navigation chính.
* Không sửa file ngoài `app/`.
* Không sửa Dagster.
* Không sửa dbt.
* Không sửa ML training.
* Không sửa inference jobs.
* Không sửa schema database.
* Không tự retrain model.
* Không tự promote khi chưa confirm.
* Không fallback sang Candidate để predict.
* Không hard-code prediction.
* Không hard-code metrics.
* Không gọi LLM.
* Không thêm dependency mới nếu package hiện có đã đủ.
* Không sửa `pyproject.toml` hoặc lock file.

# 18. Kiểm tra cuối

Kiểm tra:

* form render đúng;
* validation hoạt động;
* prediction dùng đúng Price Champion;
* local SHAP hiển thị đúng chiều;
* market comparison hoạt động;
* Champion card đọc đúng registry;
* Candidate dropdown chỉ có Candidate;
* Set as Champion archive Champion cũ;
* chỉ có một active Price Champion sau update;
* segmentation registry không bị ảnh hưởng;
* app không crash khi thiếu artifact;
* không có file ngoài `app/` bị sửa.

Chạy:

```powershell
git status --short
```

Nếu có file ngoài `app/` bị thay đổi, revert.

# 19. Báo cáo ngắn

Sau khi sửa, báo cáo:

1. File trong `app/` đã sửa hoặc tạo.
2. Tên tab cuối cùng.
3. Input fields đã triển khai.
4. Logic prediction được tái sử dụng.
5. Local SHAP explanation.
6. Comparable listings và market position.
7. Champion management flow.
8. Error states.
9. Xác nhận không sửa ngoài `app/`.

Hãy trực tiếp chỉnh sửa code, không chỉ mô tả.
