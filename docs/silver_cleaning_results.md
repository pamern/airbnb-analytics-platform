# Silver Layer Cleaning Results

## Mục tiêu

Tầng Silver chuẩn hóa 4 bảng Bronze của Airbnb thành các bảng sạch hơn để dùng cho Gold, ML, LLM và Streamlit:

- `bronze_listings` -> `silver_listings_cleaned`, `silver_hosts`, `silver_locations`
- `bronze_calendar` -> `silver_calendar`
- `bronze_reviews` -> `silver_reviews`
- `bronze_neighbourhoods` -> `silver_locations`

## Kết quả model Silver

| Model | Grain | Nội dung clean chính |
| --- | --- | --- |
| `silver_listings_cleaned` | 1 dòng / listing | Chuẩn hóa `listing_id`, `host_id`, giá tiền, phần trăm, boolean, ngày, tọa độ, review score; loại duplicate theo `listing_id`. |
| `silver_hosts` | 1 dòng / host | Tách thông tin host từ listing sạch; gom số listing quan sát được cho từng host. |
| `silver_locations` | 1 dòng / neighbourhood | Chuẩn hóa neighbourhood Bangkok, enrich listing count và tọa độ trung bình từ listings. |
| `silver_calendar` | 1 dòng / listing / ngày | Chuẩn hóa ngày, availability boolean, giá tiền, minimum/maximum nights; loại duplicate theo `listing_id + calendar_date`. |
| `silver_reviews` | 1 dòng / review | Chuẩn hóa `review_id`, `listing_id`, `review_date`, reviewer và comment; loại duplicate theo `review_id`. |
| `silver_cleaning_audit` | 1 dòng / Silver model | Ghi lại `row_count`, `duplicate_key_count`, `null_key_count`, `invalid_metric_count`. |

## Quy tắc clean đã áp dụng

- Currency text như `$1,234.00` được chuyển thành số bằng macro `clean_money`.
- Percent text như `95%` được chuyển thành tỷ lệ decimal bằng macro `clean_percent`, ví dụ `0.95`.
- Boolean dạng `t/f`, `true/false`, `1/0`, `yes/no` được chuẩn hóa thành boolean.
- Date text được ép kiểu về `date`.
- ID chính được ép kiểu numeric khi phù hợp.
- Các bảng chính được deduplicate theo grain của bảng.
- Silver không aggregate KPI lớn; phần đó dành cho Gold.

## Cách chạy

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt --target dev
```

Chạy local DuckDB thay vì MotherDuck:

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt --target local
```

## Cách xem kết quả sau khi clean

Sau khi `dbt build` thành công, kiểm tra audit:

```sql
select *
from silver.silver_cleaning_audit
order by model_name;
```

Các cột audit:

- `row_count`: số dòng sau khi clean.
- `duplicate_key_count`: số dòng duplicate còn lại theo khóa chính/grain.
- `null_key_count`: số dòng thiếu khóa chính.
- `invalid_metric_count`: số giá trị metric bất thường đang được kiểm tra, ví dụ price âm.

Kỳ vọng sau clean:

- `duplicate_key_count = 0` cho các bảng Silver chính.
- `null_key_count = 0` cho các khóa bắt buộc.
- `invalid_metric_count = 0` với các metric đã kiểm tra.
