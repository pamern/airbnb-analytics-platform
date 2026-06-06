# AGENTS.md

## Tổng quan dự án

Đây là project **Airbnb Analytics Platform** cho môn Data Warehouse.

Mục tiêu của project là xây dựng một pipeline phân tích dữ liệu Airbnb theo hướng end-to-end:

- Lưu trữ dữ liệu với MinIO và MotherDuck/DuckDB.
- Transform dữ liệu bằng dbt theo 3 layer: Bronze, Silver, Gold.
- Huấn luyện mô hình Machine Learning từ dữ liệu Gold layer.
- Sử dụng LLM để diễn giải insight và kết quả dự đoán.
- Xây dựng dashboard bằng Streamlit.
- Điều phối pipeline bằng Airflow.
- Quản lý môi trường Python bằng uv.
- Chạy local bằng Docker Compose.

---

## Tech stack chính

Project sử dụng các công nghệ chính:

- Python
- uv
- Docker / Docker Compose
- MinIO
- DuckDB / MotherDuck
- dbt
- Airflow
- Streamlit
- Machine Learning
- LLM API
- GitHub Actions

---

## Cấu trúc thư mục chính
```
airbnb-analytics-platform/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
├── .github/
├── data/
├── ingestion/
├── dbt/
├── ml/
├── llm/
├── app/
├── airflow/
├── configs/
├── utils/
├── notebooks/
├── scripts/
├── reports/
└── docs/
```
---

## Vai trò các thư mục

### `data/`

Chứa dữ liệu local phục vụ phát triển và kiểm thử.

- `raw/`: dữ liệu gốc.
- `sample/`: dữ liệu mẫu nhỏ để test nhanh.
- `external/`: dữ liệu bổ sung từ nguồn ngoài nếu có.

Không nên commit dataset quá lớn lên GitHub. Nếu dữ liệu lớn, chỉ commit sample và ghi rõ nguồn dữ liệu trong `README.md`.

### `ingestion/`

Chứa script nạp dữ liệu.

- Nạp dữ liệu raw vào MinIO.
- Nạp dữ liệu từ MinIO hoặc local vào MotherDuck.
- Validate dữ liệu đầu vào ở mức cơ bản.

Ingestion không nên chứa quá nhiều business logic. Logic transform chính nên nằm trong dbt.

### `dbt/`

Chứa project dbt và là phần trung tâm của Data Warehouse.

dbt dùng mô hình 3 layer:

Bronze → Silver → Gold

- Bronze: giữ dữ liệu raw, không thực hiện chuẩn hoá.
- Silver: làm sạch dữ liệu, xử lý null, duplicate, chuẩn hóa kiểu dữ liệu và tách entity.
- Gold: tạo fact, dimension và mart phục vụ dashboard, ML và LLM.

### `ml/`

Chứa module Machine Learning.

Vai trò:

- Build feature từ Gold layer.
- Train model.
- Evaluate model.
- Generate prediction.
- Lưu output phục vụ Streamlit dashboard và LLM.

Output ML nên đặt trong `ml/outputs/`.

### `llm/`

Chứa module diễn giải bằng LLM.

Vai trò:

- Tạo insight từ dữ liệu Gold layer.
- Giải thích kết quả ML.
- Sinh báo cáo hoặc đoạn diễn giải phục vụ dashboard.

Output LLM nên đặt trong `llm/outputs/`.

Không đưa API key trực tiếp vào code. Prompt nên được tách rõ trong file riêng nếu cần.

### `app/`

Chứa Streamlit dashboard.

Vai trò:

- Hiển thị KPI tổng quan.
- Hiển thị phân tích thị trường Airbnb.
- Hiển thị kết quả ML.
- Hiển thị insight được tạo bởi LLM.
- Có thể deploy lên cloud.

Không nên viết transform phức tạp trong Streamlit. Dashboard nên đọc dữ liệu từ Gold layer, ML outputs hoặc LLM outputs.

### `airflow/`

Chứa DAG điều phối pipeline.

Airflow là công cụ orchestration chính. DAG nên gọi các script hoặc command độc lập thay vì chứa toàn bộ business logic.

Pipeline tổng quát:

load_to_minio
    ↓
load_to_motherduck
    ↓
dbt build
    ↓
train / predict ML
    ↓
generate LLM insights

### `configs/`

Chứa cấu hình dùng chung.

Ví dụ:

- Đường dẫn project.
- Biến môi trường.
- Tên bucket MinIO.
- Thông tin kết nối MotherDuck.
- Cấu hình logging.

Không đặt helper function phức tạp trong `configs/`.

### `utils/`

Chứa helper dùng chung.

Ví dụ:

- Kết nối MotherDuck.
- Kết nối MinIO.
- Đọc/ghi file.
- Chạy SQL.
- Tạo logger.

`utils/` chỉ nên chứa function hỗ trợ, không nên chứa cấu hình chính hoặc business logic lớn.

### `notebooks/`

Chứa notebook để EDA, thử nghiệm ML và thử nghiệm LLM.

Notebook chỉ phục vụ phân tích/thử nghiệm, không phải pipeline chính.

### `scripts/`

Chứa script shell để chạy lẻ từng phần khi debug.

Ví dụ:

- Chạy ingestion.
- Chạy dbt.
- Chạy ML.
- Chạy LLM.
- Chạy Streamlit app.

Không cần `run_all_pipeline.sh` vì Airflow đảm nhiệm orchestration chính.

### `reports/`

Chứa báo cáo, hình ảnh, bảng kết quả và file tổng kết cuối.

### `docs/`

Chứa tài liệu dự án.

Ví dụ:

- Kiến trúc hệ thống.
- Data dictionary.
- Dimensional model.
- ML methodology.
- LLM interpretation.

---

## Luồng dữ liệu tổng thể

Pipeline chính đi theo luồng:

Raw Airbnb Data
    ↓
MinIO
    ↓
MotherDuck
    ↓
dbt Bronze
    ↓
dbt Silver
    ↓
dbt Gold
    ↓
ML / LLM / Streamlit

Airflow điều phối các bước chính của pipeline.

Streamlit dashboard là nơi hiển thị kết quả cuối và có thể deploy lên cloud.

---

## Quy ước dbt

- Bronze giữ dữ liệu gần raw nhất.
- Silver xử lý cleaning và chuẩn hóa.
- Gold tạo fact, dimension và mart.
- Model SQL nên rõ ràng, dễ đọc, ưu tiên chia CTE hợp lý.
- Các model quan trọng nên có test khi phù hợp.
- Không nên xử lý logic chính ở notebook hoặc Streamlit nếu logic đó thuộc về data warehouse.

---

## Quy ước Python

- Dùng Python 3.11 trở lên nếu có thể.
- Dùng `uv` để quản lý dependency.
- Không hard-code credential, token hoặc API key.
- Không hard-code path nếu có thể dùng `configs/paths.py`.
- Code nên dễ đọc, dễ chạy, dễ demo.
- Mỗi module nên có trách nhiệm rõ ràng.
- Nếu thêm dependency, cập nhật `pyproject.toml`.

Ví dụ chạy script:

uv run python ingestion/load_to_minio.py
uv run python ingestion/load_to_motherduck.py
uv run dbt build --project-dir dbt
uv run python ml/train_model.py
uv run python llm/insight_generator.py
uv run streamlit run app/streamlit_dashboard.py

---

## Quy ước Docker

Docker Compose dùng để chạy stack local.

Các service có thể gồm:

- MinIO
- Airflow
- Streamlit app
- Các service hỗ trợ khác nếu cần

`Dockerfile` dùng để đóng gói app hoặc runtime cần thiết cho project.

Không nên đưa secret trực tiếp vào Dockerfile hoặc docker-compose. Secret nên lấy từ `.env` hoặc environment variables.

---

## Quy ước Airflow

Airflow dùng để điều phối pipeline, không dùng để chứa business logic lớn.

DAG nên:

- Gọi script hoặc command độc lập.
- Có thứ tự task rõ ràng.
- Có retry cơ bản nếu cần.
- Không chứa logic transform phức tạp.
- Không chứa credential hard-code.

---

## Quy ước Streamlit

Streamlit app nằm trong `app/`.

Nguyên tắc:

- `streamlit_dashboard.py` là entrypoint chính.
- Các page phụ đặt trong `app/pages/`.
- Component tái sử dụng đặt trong `app/components/`.
- Dashboard nên đọc dữ liệu từ Gold layer hoặc output ML/LLM.
- Không viết SQL/transform quá phức tạp trực tiếp trong UI.
- Không hard-code credential trong app.

---

## Quy ước bảo mật

Không commit các thông tin sau:

- `.env`
- API key
- MotherDuck token
- MinIO secret key
- LLM API key
- Password
- Dữ liệu quá lớn nếu không cần thiết

Chỉ commit `.env.example` để mô tả các biến môi trường cần có.

---

## Quy ước Git

Commit message nên ngắn gọn, rõ chức năng.

Ví dụ:

feat: add MinIO ingestion script
feat: create dbt bronze models
feat: add Streamlit overview dashboard
fix: correct MotherDuck connection helper
docs: update architecture documentation

Không commit:

- `.env`
- file cache
- `__pycache__/`
- file dữ liệu lớn
- model quá lớn nếu không cần thiết

---

## Nguyên tắc cho AI agent

Khi chỉnh sửa project này, hãy tuân thủ:

1. Giữ cấu trúc tổng thể của repo nếu không có yêu cầu thay đổi.
2. Ưu tiên thay đổi nhỏ, rõ ràng, dễ kiểm tra.
3. Không tự ý xóa file hoặc đổi tên thư mục quan trọng.
4. Không đưa secret vào code.
5. Không trộn lẫn vai trò giữa `configs/` và `utils/`.
6. Không viết transform phức tạp trong Streamlit app.
7. Không viết business logic lớn trực tiếp trong Airflow DAG.
8. Không trộn ML, LLM và app vào cùng một module.
9. Nếu thêm dependency, cập nhật `pyproject.toml`.
10. Nếu thêm model dbt quan trọng, bổ sung test hoặc tài liệu liên quan khi phù hợp.
11. Nếu chưa chắc hướng xử lý, chọn phương án đơn giản, dễ demo trước.
12. Nếu cần thay đổi cấu trúc để project chạy đúng hơn, có thể đề xuất thay đổi nhưng phải giải thích lý do.

---

## Ghi chú

Tài liệu này là hướng dẫn định hướng cho agent, không phải luật cứng tuyệt đối.

Nếu cần thay đổi cấu trúc hoặc cách triển khai để project chạy đúng hơn, có thể thay đổi nhưng cần giữ tinh thần:

- Rõ ràng.
- Dễ bảo trì.
- Dễ demo.
- Không hard-code thông tin nhạy cảm.
- Không làm phức tạp project nếu chưa cần thiết.