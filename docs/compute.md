Hãy tối ưu mức sử dụng MotherDuck compute trong project hiện tại.

## Bối cảnh

Project sử dụng:

* MotherDuck làm data warehouse.
* DuckDB Python client để query.
* Streamlit làm dashboard.
* dbt tạo các bảng Bronze, Silver và Gold.
* Dagster chạy daily pipeline lúc 13:35.
* Dashboard đang phát sinh nhiều query lặp lại, làm tiêu hao MotherDuck compute.

Mục tiêu là giảm:

* Số lần query MotherDuck.
* Các query trùng lặp do Streamlit rerun.
* Query riêng cho từng KPI hoặc biểu đồ.
* Query metadata lặp lại.
* Việc mở nhiều connection không cần thiết.

Không được làm thay đổi số liệu, business logic hoặc giao diện hiện tại.

---

# Phạm vi ưu tiên

Thực hiện theo thứ tự:

1. Audit toàn bộ query MotherDuck trong dashboard.
2. Chuẩn hóa connection dùng chung.
3. Cache kết quả query bằng `st.cache_data`.
4. Cache connection bằng `st.cache_resource` nếu phù hợp.
5. Ngăn query lại khi người dùng thay đổi từng filter.
6. Gộp các query trùng lặp.
7. Tái sử dụng một DataFrame cho nhiều KPI và biểu đồ.
8. Cache các query metadata/filter options.
9. Chỉ đề xuất, chưa tự động thay đổi dbt incremental hoặc materialization nếu việc đó có nguy cơ thay đổi dữ liệu.

---

# Giới hạn thay đổi bắt buộc

Không được thay đổi:

* Công thức KPI.
* SQL business logic.
* Điều kiện filter.
* Tên bảng hoặc schema.
* Cấu trúc dữ liệu đầu ra.
* Nội dung biểu đồ.
* Bố cục giao diện.
* Model registry.
* Logic Champion/Candidate/Archived.
* Logic prediction.
* Logic segmentation.
* Dagster asset.
* Dagster schedule.
* dbt model SQL.
* dbt test.
* Training pipeline.
* Môi trường hoặc dependency nếu không thật sự cần thiết.

Không được refactor diện rộng.

Không được tạo dữ liệu giả.

Không được che giấu lỗi bằng `try/except Exception` chung chung.

---

# Bước 1: Audit query

Tìm toàn bộ code có liên quan đến:

```text
duckdb.connect
connection.execute
conn.execute
query
fetchdf
fetch_df
fetchone
fetchall
sql(
st.cache_data
st.cache_resource
st.connection
```

Lập danh sách:

* File chứa query.
* Tên hàm query.
* Bảng MotherDuck được truy cập.
* Query có phụ thuộc filter hay không.
* Query có bị gọi nhiều lần trong một lần render không.
* Query có trùng với query khác không.
* Query có dùng chỉ để lấy một KPI không.
* Query metadata như:

  * `SHOW TABLES`
  * `DESCRIBE`
  * `SELECT DISTINCT`
  * `SELECT MAX(...)`

Đặc biệt kiểm tra các trang:

* Market Overview.
* Model Lab.
* Prediction.
* Segmentation.
* Model metrics.
* Model registry.

---

# Bước 2: Chuẩn hóa connection

Project hiện dùng MotherDuck nên phải giữ nguyên cơ chế kết nối cloud hiện tại.

Nếu đã có connection helper dùng chung, tất cả module phải tái sử dụng helper đó.

Không được tự tạo thêm nhiều connection bằng:

```python
duckdb.connect(...)
```

trong từng component hoặc từng hàm query.

Ưu tiên cấu trúc tương đương:

```python
import duckdb
import streamlit as st


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(
        database=MOTHERDUCK_DATABASE_URI,
        read_only=False,
    )
```

Chỉ dùng cấu trúc này nếu tương thích với code hiện tại.

Phải giữ:

```python
read_only=False
```

để thống nhất với cơ chế connection trước khi merge.

Không hard-code token, database name hoặc đường dẫn.

Không log MotherDuck token.

---

# Bước 3: Cache kết quả query

Thêm `@st.cache_data` vào các hàm chỉ đọc dữ liệu và trả về:

* DataFrame.
* dict.
* list.
* tuple.
* scalar KPI.

Ví dụ:

```python
@st.cache_data(ttl=3600, show_spinner=False)
def get_market_overview(
    city: str,
    date_from: str | None,
    date_to: str | None,
) -> pd.DataFrame:
    conn = get_connection()
    return conn.execute(
        MARKET_OVERVIEW_QUERY,
        [city, date_from, date_to],
    ).fetchdf()
```

## TTL đề xuất

Áp dụng TTL phù hợp:

```text
Market overview              3600 giây
Dashboard aggregates         3600 giây
Filter options               3600 giây
Model metrics                900 giây
Model registry               300 giây
Champion information         300 giây
Archived/Candidate versions  300 giây
Prediction input lookup      1800 giây
```

Nếu hàm đã có cache, không tạo cache lồng nhau không cần thiết.

Cache key phải phụ thuộc đúng vào các filter đầu vào.

Không cache các thao tác ghi dữ liệu.

Không cache connection bằng `st.cache_data`.

---

# Bước 4: Ngăn Streamlit rerun gây query liên tục

Các bộ lọc có nhiều widget phải được gom vào `st.form` nếu hiện tại mỗi thay đổi widget làm query lại MotherDuck.

Ví dụ:

```python
with st.form("market_filters"):
    city = st.selectbox(...)
    date_range = st.date_input(...)
    room_type = st.multiselect(...)

    apply_filters = st.form_submit_button("Apply")

if apply_filters:
    ...
```

Phải giữ nguyên giá trị mặc định và hành vi filter hiện tại.

Không làm mất khả năng chọn filter.

Không thay đổi giao diện nếu không cần thiết.

Nếu trang đã có nút Apply hoặc cơ chế session state phù hợp thì tái sử dụng, không tạo thêm UI dư thừa.

---

# Bước 5: Gộp query trùng lặp

Tìm các trường hợp dạng:

```text
KPI 1 → query A
KPI 2 → query B
KPI 3 → query C
Chart → query D
```

trong khi đều lấy từ cùng bảng và cùng filter.

Gộp thành một query trả về dataset đủ dùng:

```text
Một query tổng hợp
    ↓
DataFrame
    ↓
KPI + chart + table
```

Sau đó tính các KPI từ DataFrame trong Python khi việc đó không làm thay đổi kết quả.

Không gộp query nếu:

* Grain dữ liệu khác nhau.
* Filter khác nhau.
* Cách aggregate khác nhau.
* Có nguy cơ thay đổi số liệu.

---

# Bước 6: Cache metadata và filter options

Các hàm lấy:

* Danh sách neighbourhood.
* Room type.
* Property type.
* Model version.
* Stage.
* Snapshot date.
* Min/max date.
* `MAX(updated_at)`.
* `MAX(snapshot_date)`.

phải được cache hợp lý.

Ví dụ:

```python
@st.cache_data(ttl=3600, show_spinner=False)
def get_neighbourhood_options() -> list[str]:
    ...
```

Không query lại những danh sách này tại mỗi component render.

---

# Bước 7: Giảm query không cần thiết theo tab

Nếu một trang có nhiều tab:

```python
tab1, tab2, tab3 = st.tabs(...)
```

hãy kiểm tra xem dữ liệu của tất cả tab có đang được query ngay khi mở trang hay không.

Nếu có thể thực hiện an toàn, chỉ query dữ liệu khi tab hoặc section đó thực sự cần dùng.

Không thay đổi UX hiện tại nếu Streamlit không hỗ trợ lazy tab hoàn toàn.

Ít nhất phải tránh gọi cùng một query trong nhiều tab.

---

# Bước 8: Tối ưu SQL an toàn

Chỉ thực hiện các thay đổi không làm thay đổi kết quả:

* Thay `SELECT *` bằng đúng các cột đang sử dụng.
* Đẩy điều kiện `WHERE` vào query sớm.
* Không cast cột filter nếu không cần thiết.
* Dùng parameter binding thay vì nối chuỗi SQL.
* Không query toàn bộ bảng rồi mới filter trong pandas nếu có thể filter ngay trong SQL.
* Không gọi cùng query nhiều lần để lấy `.head()`, `.shape`, `.sum()` riêng biệt.

Ví dụ parameter binding:

```python
conn.execute(
    """
    SELECT column_a, column_b
    FROM gold.some_table
    WHERE city = ?
      AND snapshot_date BETWEEN ? AND ?
    """,
    [city, date_from, date_to],
)
```

Không thay đổi logic join hoặc aggregate nếu chưa có test xác nhận.

---

# Bước 9: Theo dõi số query

Trong môi trường development, thêm logging tối thiểu để biết:

* Tên hàm query.
* Thời gian thực thi.
* Cache hit/miss nếu có thể.
* Không log SQL parameter nhạy cảm.
* Không log MotherDuck token.

Logging không được gây thêm query.

Không hiển thị log kỹ thuật lên giao diện người dùng.

Nếu project đã có logger chung thì dùng lại logger hiện có.

---

# Không thực hiện tự động trong lần này

Không tự động:

* Chuyển dbt model thành incremental.
* Chuyển view thành table.
* Tạo Gold mart mới.
* Sửa `dbt build --select`.
* Thay đổi Dagster selection.
* Thay đổi lịch pipeline.
* Thay đổi MotherDuck database/schema.

Thay vào đó, sau khi tối ưu dashboard, hãy lập một mục đề xuất riêng cho các tối ưu cấp dbt gồm:

* Model nào nên thành incremental.
* View nào nên thành table.
* Dashboard mart nào nên tạo.
* Query nào nên được pre-aggregate.
* Ước tính lợi ích và rủi ro.

Chỉ đề xuất, không chỉnh sửa các phần này.

---

# Kiểm tra bắt buộc

Sau khi sửa:

1. Dashboard khởi động thành công.
2. Không phát sinh lỗi connection MotherDuck.
3. Market Overview hiển thị đúng.
4. Model Lab hiển thị đúng.
5. Prediction và Segmentation không bị ảnh hưởng.
6. Các filter vẫn hoạt động đúng.
7. Giá trị KPI trước và sau phải giống nhau với cùng input.
8. Các biểu đồ giữ nguyên dữ liệu.
9. Không có connection `read_only=True` nếu cùng database đang dùng `read_only=False`.
10. Không có nhiều connection factory trùng chức năng.
11. Không query lại khi chỉ rerender từ dữ liệu đã cache.
12. Không làm mất schedule hoặc Definitions của Dagster.
13. Không thay đổi dbt SQL hoặc schema.

Nếu có test hiện có, hãy chạy các test liên quan.

Nếu không có test, tạo kiểm tra tối thiểu cho:

* Cache key theo filter.
* Hàm query trả đúng schema.
* KPI trước/sau không thay đổi.

Không tạo test cần gọi MotherDuck production nhiều lần.

---

# Kết quả cần báo cáo

Sau khi hoàn thành, trả về:

## 1. Nguyên nhân tiêu compute

* Query nào bị gọi lặp.
* Component nào gây rerun nhiều.
* Query metadata nào bị gọi thường xuyên.
* Có bao nhiêu connection khác nhau.

## 2. File đã sửa

Liệt kê từng file và thay đổi ngắn gọn.

## 3. Cache đã thêm

Bảng gồm:

```text
Function | TTL | Parameters used as cache key
```

## 4. Query đã gộp

Nêu rõ:

* Số query trước.
* Số query sau.
* Các KPI/biểu đồ dùng chung DataFrame nào.

## 5. Kết quả kiểm tra

* Dashboard load.
* Market Overview.
* Model Lab.
* Prediction.
* Segmentation.
* Số liệu trước/sau.

## 6. Đề xuất dbt riêng

Chỉ đề xuất, không chỉnh sửa:

* Incremental models.
* Dashboard marts.
* Materialization.
* Dagster/dbt selector.

Chỉ sửa trong phạm vi tối ưu compute. Không tự ý thay đổi business logic, dữ liệu hoặc kiến trúc ngoài yêu cầu.
