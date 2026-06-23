# AGENTS.md

## Tổng quan dự án

Đây là project **Airbnb Analytics Platform** cho môn Data Warehouse.

Mục tiêu của project là xây dựng một pipeline phân tích dữ liệu Airbnb theo hướng end-to-end:

- Lưu trữ và phân tích dữ liệu với MotherDuck/DuckDB.
- Transform dữ liệu bằng dbt theo 3 layer: Bronze, Silver, Gold.
- Huấn luyện mô hình Machine Learning từ dữ liệu Gold layer.
- Sử dụng LLM/Groq để diễn giải insight từ dữ liệu tổng hợp.
- Xây dựng dashboard bằng Streamlit.
- Quản lý môi trường Python bằng uv.
- Chạy local bằng Docker Compose khi cần demo hoặc đóng gói app.

---

## Tech stack chính

Project sử dụng các công nghệ chính:

- Python
- uv
- Docker / Docker Compose
- DuckDB / MotherDuck
- dbt
- Streamlit
- Machine Learning
- Groq LLM API
- GitHub Actions

---

## Cấu trúc thư mục chính

```text
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

- `raw/`: dữ liệu gốc (không commit lên GitHub nếu quá lớn).
- `gold_ai_listings_snapshot.csv`: cache dữ liệu Gold layer phục vụ dashboard và LLM local.


### `ingestion/`

Chứa script nạp dữ liệu.

- Nạp dữ liệu raw từ local vào MotherDuck.
- Validate dữ liệu đầu vào ở mức cơ bản.

Ingestion không nên chứa quá nhiều business logic. Logic transform chính nên nằm trong dbt.

### `dbt/`

Chứa project dbt và là phần trung tâm của Data Warehouse.

dbt dùng mô hình 3 layer:

```text
Bronze -> Silver -> Gold
```

- Bronze: giữ dữ liệu raw, không thực hiện chuẩn hoá.
- Silver: làm sạch dữ liệu, xử lý null, duplicate, chuẩn hóa kiểu dữ liệu và tách entity.
- Gold: tạo fact, dimension và mart phục vụ dashboard, ML và LLM.

Các Gold model quan trọng hiện gồm:

- `dim_date`
- `dim_host`
- `dim_listing`
- `dim_location`
- `fact_availability_daily`
- `fact_listing_current_snapshot`
- `fact_review`
- `gold_price_model_features`
- `gold_cluster_model_features`

### `ml/`

Chứa module Machine Learning.

Vai trò:

- Build feature từ Gold layer.
- Train model.
- Evaluate model.
- Generate prediction.
- Lưu output phục vụ Streamlit dashboard và LLM.

Output ML nên đặt trong `ml/outputs/`. Artifact/model lớn không nên commit nếu không cần thiết.

### `llm/`

Chứa module diễn giải bằng LLM.

Vai trò hiện tại:

- Gọi Groq Chat Completions API trong `llm/groq_insights.py`.
- Nhận summary markdown từ Gold layer, không gửi raw dataset trực tiếp lên LLM.
- Sinh 3 insight bằng tiếng Việt cho dashboard AI Q&A.

Luồng Groq hiện tại:

```text
Gold tables
    -> app/data_access.py::load_pricing_insight_context()
    -> summary markdown
    -> llm/groq_insights.py::generate_airbnb_insights()
    -> Streamlit AI Q&A page
```

Không đưa API key trực tiếp vào code. Các biến cần nằm trong `.env`, ví dụ `GROQ_API_KEY` và `LLM_MODEL`.

### `app/`

Chứa Streamlit dashboard.

Entry point chính:

```bash
uv run streamlit run app/streamlit_dashboard.py
```

Cấu trúc app hiện tại:

- `app/streamlit_dashboard.py`: cấu hình Streamlit multipage, sidebar, preload cache dữ liệu.
- `app/pages/01_dashboard.py`: dashboard phân tích chính.
- `app/pages/02_ai_qa.py`: trang AI Q&A/Groq insight demo.
- `app/pages/03_model_lab.py`: trang thử nghiệm model/dự báo.
- `app/components/`: component UI, dashboard section, model lab, AI chat.
- `app/data_access.py`: lớp đọc dữ liệu cho Streamlit từ Gold layer và summary cho LLM.

Dashboard hiện có các nhóm phân tích chính:

- Executive Overview.
- Pricing & Listing Performance.
- Location & Availability Performance.
- Host & Review Quality.
- AI Q&A dùng Groq để giải thích insight từ summary Gold pricing data.
- Model Lab cho phần dự báo/model demo.

Không nên viết transform phức tạp trong Streamlit. Dashboard nên đọc dữ liệu từ Gold layer, ML outputs hoặc LLM outputs. SQL phục vụ dashboard nên được gom vào `app/data_access.py` hoặc đẩy xuống dbt nếu logic trở nên quan trọng/tái sử dụng nhiều.

### `configs/`

Chứa cấu hình dùng chung.

Ví dụ:

- Đường dẫn project trong `configs/paths.py`.
- Biến môi trường và validate setting trong `configs/settings.py`.
- Cấu hình logging trong `configs/logging.py`.
- Thông tin kết nối MotherDuck.
- Cấu hình LLM/Groq.

Không đặt helper function phức tạp trong `configs/`.

### `utils/`

Chứa helper dùng chung.

Ví dụ:

- Kết nối MotherDuck.
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

Các script nên chạy được độc lập để dễ debug và demo từng phần của pipeline.

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
- Orchestration/Dagster notes.

---

## Luồng dữ liệu tổng thể

Pipeline chính đi theo luồng:

```text
Raw Airbnb Data
    -> MotherDuck
    -> dbt Bronze
    -> dbt Silver
    -> dbt Gold
    -> ML / LLM / Streamlit
```

Streamlit dashboard là nơi hiển thị kết quả cuối và có thể deploy lên cloud.

---

## Luồng dữ liệu cho dashboard và Groq

Dashboard đọc dữ liệu chủ yếu qua `app/data_access.py`:

- `load_pricing_dataset()` đọc listing-level pricing data từ `gold.fact_listing_current_snapshot`, `gold.dim_listing`, `gold.dim_host`, `gold.dim_location`.
- `load_host_quality_dataset()` đọc dữ liệu host/review quality từ Gold layer.
- `load_review_events_dataset()` đọc review events từ `gold.fact_review`, `gold.dim_date`, `gold.dim_listing`, `gold.dim_location` và `silver.silver_reviews`.
- `load_pricing_insight_context()` tạo summary markdown cho Groq từ các query tổng hợp trên Gold layer.

Groq chỉ nhận summary ngắn, gồm:

- Overall pricing snapshot.
- Top neighbourhoods by median estimated revenue.
- Room type performance.
- Reliable review score by room type.

Nguyên tắc: không gửi raw dataset hoặc credential lên LLM.

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

```bash
uv run python ingestion/load_to_motherduck.py
uv run dbt build --project-dir dbt
uv run python ml/train_model.py
uv run python llm/insight_generator.py
uv run streamlit run app/streamlit_dashboard.py
```

---

## Quy ước Docker

Docker Compose dùng để chạy stack local.

Các service có thể gồm:

- Streamlit app.
- Các service hỗ trợ khác nếu cần.

`Dockerfile` dùng để đóng gói app hoặc runtime cần thiết cho project.

Không nên đưa secret trực tiếp vào Dockerfile hoặc docker-compose. Secret nên lấy từ `.env` hoặc environment variables.

---

## Quy ước Streamlit

Streamlit app nằm trong `app/`.

Nguyên tắc:

- `streamlit_dashboard.py` là entrypoint chính.
- Các page phụ đặt trong `app/pages/`.
- Component tái sử dụng đặt trong `app/components/`.
- Data loading tập trung trong `app/data_access.py`.
- Dashboard nên đọc dữ liệu từ Gold layer hoặc output ML/LLM.
- Không viết SQL/transform quá phức tạp trực tiếp trong UI component.
- Không hard-code credential trong app.
- Với dữ liệu nặng, ưu tiên `st.cache_data`, `st.cache_resource` và preload có kiểm soát.

---

## Quy ước bảo mật

Không commit các thông tin sau:

- `.env`
- API key
- MotherDuck token
- Groq/LLM API key
- Password
- Dữ liệu quá lớn nếu không cần thiết

Chỉ commit `.env.example` để mô tả các biến môi trường cần có.

Các biến môi trường thường dùng:

- `MOTHERDUCK_TOKEN`
- `MOTHERDUCK_DATABASE`
- `MOTHERDUCK_SCHEMA`
- `GROQ_API_KEY`
- `LLM_MODEL`
- `STREAMLIT_SERVER_PORT`
- `AIRBNB_CITY`

---

## Quy ước Git

Commit message nên ngắn gọn, rõ chức năng.

Ví dụ:

```text
feat: add MotherDuck ingestion script
feat: create dbt bronze models
feat: add Streamlit overview dashboard
feat: add Groq insight generator
perf: optimize dashboard data loading
fix: correct MotherDuck connection helper
docs: update architecture documentation
```

Không commit:

- `.env`
- file cache
- `__pycache__/`
- file dữ liệu lớn
- model/artifact quá lớn nếu không cần thiết

---

## Nguyên tắc cho AI agent

Khi chỉnh sửa project này, hãy tuân thủ:

1. Giữ cấu trúc tổng thể của repo nếu không có yêu cầu thay đổi.
2. Ưu tiên thay đổi nhỏ, rõ ràng, dễ kiểm tra.
3. Không tự ý xóa file hoặc đổi tên thư mục quan trọng.
4. Không đưa secret vào code.
5. Không trộn lẫn vai trò giữa `configs/` và `utils/`.
6. Không viết transform phức tạp trong Streamlit app.
7. Không trộn ML, LLM và app vào cùng một module.
8. Nếu thêm dependency, cập nhật `pyproject.toml`.
9. Nếu thêm model dbt quan trọng, bổ sung test hoặc tài liệu liên quan khi phù hợp.
10. Nếu chưa chắc hướng xử lý, chọn phương án đơn giản, dễ demo trước.
11. Nếu cần thay đổi cấu trúc để project chạy đúng hơn, có thể đề xuất thay đổi nhưng phải giải thích lý do.
12. Nếu cập nhật luồng Groq/LLM, đảm bảo tài liệu nói rõ dữ liệu gửi lên LLM là summary từ Gold layer, không phải raw dataset.
13. Nếu cập nhật dashboard, giữ data access tách khỏi UI component.

---

## Ghi chú

Tài liệu này là hướng dẫn định hướng cho agent, không phải luật cứng tuyệt đối.

Nếu cần thay đổi cấu trúc hoặc cách triển khai để project chạy đúng hơn, có thể thay đổi nhưng cần giữ tinh thần:

- Rõ ràng.
- Dễ bảo trì.
- Dễ demo.
- Không hard-code thông tin nhạy cảm.
- Không làm phức tạp project nếu chưa cần thiết.
