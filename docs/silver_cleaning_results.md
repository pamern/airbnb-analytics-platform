# Silver Layer Cleaning Results

## Muc tieu

Tang Silver chuan hoa 4 bang Bronze cua Airbnb thanh 4 bang sach hon, giu nguyen grain nguon va chua tach entity. Viec tach dimension/fact va aggregate KPI se thuc hien o tang Gold.

- `bronze_listings` -> `silver_listings`
- `bronze_calendar` -> `silver_calendar`
- `bronze_reviews` -> `silver_reviews`
- `bronze_neighbourhoods` -> `silver_neighbourhoods`

## Ket qua model Silver

| Model | Grain | Noi dung clean chinh |
| --- | --- | --- |
| `silver_listings` | 1 dong / listing | Chuan hoa `listing_id`, `host_id`, gia tien, phan tram, boolean, ngay, toa do, review score; loai duplicate theo `listing_id`. |
| `silver_calendar` | 1 dong / listing / ngay | Chuan hoa ngay, availability boolean, gia tien, minimum/maximum nights; loai duplicate theo `listing_id + calendar_date`. |
| `silver_reviews` | 1 dong / review | Chuan hoa `review_id`, `listing_id`, `review_date`, reviewer va comment; loai duplicate theo `review_id`. |
| `silver_neighbourhoods` | 1 dong / neighbourhood | Chuan hoa ten neighbourhood va neighbourhood group; loai duplicate theo `neighbourhood`. |

## Quy tac clean da ap dung

- Currency text nhu `$1,234.00` duoc chuyen thanh so bang macro `clean_money`.
- Percent text nhu `95%` duoc chuyen thanh ty le decimal bang macro `clean_percent`, vi du `0.95`.
- Boolean dang `t/f`, `true/false`, `1/0`, `yes/no` duoc chuan hoa thanh boolean.
- Date text duoc ep kieu ve `date`.
- ID chinh duoc ep kieu numeric khi phu hop.
- Cac bang duoc deduplicate theo grain cua tung bang.
- Silver khong aggregate KPI lon va khong tach host/location dimension; phan do danh cho Gold.

## Cach chay

Chay Silver len MotherDuck:

```bash
dbt build --project-dir dbt --profiles-dir dbt --select silver
```

Neu dung `uv`:

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt --select silver
```

Chay local DuckDB thay vi MotherDuck:

```bash
dbt build --project-dir dbt --profiles-dir dbt --target local --select silver
```

## Cach kiem tra ket qua

Sau khi `dbt build` thanh cong, kiem tra danh sach bang Silver:

```sql
show tables from silver;
```

Ky vong Silver chi co 4 bang:

- `silver_listings`
- `silver_calendar`
- `silver_reviews`
- `silver_neighbourhoods`
