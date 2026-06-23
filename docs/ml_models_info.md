# Thông tin về 2 Mô hình Machine Learning trong Dự án

Dự án này tích hợp 2 luồng/mô hình Machine Learning chính nằm trong thư mục `ml/` để phân tích dữ liệu Airbnb:
1. **Mô hình Dự báo Giá (Price Prediction Model)**
2. **Mô hình Phân cụm Danh sách (Listing Segmentation / Clustering Model)**

Dưới đây là chi tiết về cấu trúc, thuật toán, dữ liệu đầu vào và đầu ra của từng mô hình.

---

## 1. Mô hình Dự báo Giá (Price Prediction Model)
**Thư mục mã nguồn:** `ml/price_modeling/`

### Mục tiêu
Dự đoán giá thuê phòng mỗi đêm (`price`) của một listing Airbnb dựa trên các thuộc tính của phòng và của host. Mô hình này giúp các nhà đầu tư hoặc host tối ưu hóa chiến lược định giá của họ.

### Pipeline xử lý
1. **Feature Engineering & Preprocessing (`preprocessing.py`, `feature_selection.py`):**
   - Làm sạch dữ liệu, xử lý giá trị khuyết (missing values).
   - Mã hóa các biến phân loại (Categorical variables) như `room_type`, `neighbourhood`, `property_base_group`, `host_response_time`.
   - Chuẩn hóa các biến số liên tục (Numerical variables) như số khách chứa (`accommodates`), số phòng ngủ (`bedrooms`), phòng tắm (`bathrooms`), số giường (`beds`), số đêm tối thiểu/tối đa, số lượng tiện ích (`amenities_count`), tỷ lệ phản hồi (`host_response_rate`).
2. **Huấn luyện & Lựa chọn Mô hình (`pipeline.py`, `training.py`):**
   - So sánh giữa các thuật toán:
     - **HistGradientBoostingRegressor** (HGB - Thường là mô hình mặc định do hỗ trợ tốt dữ liệu dạng bảng có giá trị khuyết).
     - **RandomForestRegressor**
     - **XGBoost Regressor**
   - Phân chia tập huấn luyện (Train/Test Split) và đánh giá chéo (Cross-Validation).
3. **Đánh giá & Giải thích (`evaluation.py`, `explainability.py`):**
   - Các chỉ số đánh giá: **RMSE** (Root Mean Squared Error), **MAE** (Mean Absolute Error), và **R²** (R-squared).
   - Xuất các biểu đồ phân tích sai số (Residual Plots, Feature Importance) lưu vào thư mục `ml/outputs/price_modeling/charts/`.

---

## 2. Mô hình Phân cụm Danh sách (Listing Segmentation / Clustering Model)
**Thư mục mã nguồn:** `ml/listing_segmentation/`

### Mục tiêu
Phân cụm các listings Airbnb thành các nhóm/phân khúc thị trường riêng biệt (Segmentation) dựa trên hiệu suất hoạt động, giá cả, và đặc điểm vị trí. Giúp nhà đầu tư nhận diện cấu trúc phân khúc thị trường (ví dụ: phân khúc cao cấp, phân khúc bình dân, phân khúc phòng tập thể, v.v.).

### Pipeline xử lý
1. **Thu thập dữ liệu (`data.py`, `data_loader.py`):**
   - Đọc dữ liệu từ bảng Gold layer trên MotherDuck/DuckDB.
2. **Thuật toán Phân cụm (`pipeline.py`, `training.py`):**
   - Sử dụng thuật toán **KMeans** làm mặc định và hỗ trợ cấu hình **DBSCAN** cho các trường hợp phân cụm theo mật độ địa lý.
   - Tìm số cụm tối ưu bằng phương pháp Elbow hoặc Silhouette Score.
3. **Đánh giá & Định hình phân khúc (`evaluate.py`, `profiles.py`):**
   - Tính toán **Silhouette Score** để đánh giá chất lượng phân cụm.
   - Định hình hồ sơ từng phân cụm (Segment Profiling): xác định giá trung vị, tỷ lệ lấp đầy (occupancy rate), doanh thu ước tính, loại phòng phổ biến của từng cụm.
4. **Trực quan hóa & Lưu trữ (`visualization.py`, `database_writer.py`):**
   - Tạo biểu đồ phân cụm (Scatter Plot 2D/3D bằng PCA hoặc t-SNE) và ghi kết quả phân cụm ngược lại database phục vụ cho việc hiển thị trên Dashboard.

---

## Cách chạy Pipelines ML dưới Terminal
Bạn có thể chạy các pipeline huấn luyện mô hình thông qua môi trường `uv`:

```bash
# Chạy pipeline huấn luyện mô hình dự báo giá
uv run python ml/price_modeling/pipeline.py

# Chạy pipeline phân cụm danh sách listings
uv run python ml/listing_segmentation/pipeline.py
```
