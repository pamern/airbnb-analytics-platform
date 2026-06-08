# Bangkok Airbnb Price & Market Intelligence Dashboard

## 1. De bai va muc tieu he thong

De tai cua du an la xay dung **Bangkok Airbnb Price & Market Intelligence Dashboard**. He thong dung de phan tich thi truong Airbnb tai Bangkok, danh gia hieu qua host, so sanh doi thu canh tranh va ho tro du doan gia de xuat cho mot listing moi.

Dashboard duoc thiet ke theo 3 phan he chinh:

| Tab | Noi dung phan tich | Gia tri mang lai |
|---|---|---|
| Market Overview & Geospatial Analysis | KPI tong quan, ban do listing, heatmap gia, top khu vuc dat/re, co cau room type, xu huong gia theo thoi gian | Giup nguoi dung hieu tong quan thi truong Airbnb Bangkok |
| Host Performance & Competitor Benchmarking | So sanh Superhost voi host thuong, danh gia hieu qua host, goi y doi thu canh tranh truc tiep | Giup host biet vi tri canh tranh cua minh |
| ML Simulator & LLM Insights | Mo phong gia de xuat bang ML, dien giai insight bang LLM | Tao diem nhan premium cho dashboard |

Luong du lieu tong the:

```text
Raw Airbnb Data
    -> Bronze
    -> Silver
    -> Gold Kimball
    -> Mart
    -> Streamlit / ML / LLM
```

## 2. Giai phap su dung

| Thanh phan | Giai phap |
|---|---|
| Data Warehouse | Thiet ke Gold layer theo mo hinh Kimball |
| Transform | dbt theo 3 layer Bronze, Silver, Gold |
| Dashboard | Streamlit |
| Machine Learning | Random Forest Regressor de du doan `price` |
| LLM | Sinh insight tu du lieu khu vuc, listing va review |
| Storage | MinIO va DuckDB/MotherDuck |
| Orchestration | Airflow |

## 3. Vi sao dung Kimball

Mo hinh Kimball phu hop voi bai nay vi dashboard can phan tich du lieu theo nhieu goc nhin: listing, host, khu vuc va thoi gian. Trong Kimball, cac bang Dimension dung de mo ta ngu canh phan tich, con cac bang Fact dung de luu chi so do luong.

Trong bai ban hang truyen thong, Kimball thuong co `dim_product`, `dim_customer`, `fact_sales`. Voi bai Airbnb, co the anh xa nhu sau:

| Kimball truyen thong | Bai Airbnb |
|---|---|
| Product Dimension | `dim_listing`: phong/can ho Airbnb |
| Customer Dimension | Khong dung vi dataset khong co du lieu khach dat phong that |
| Supplier/Seller Dimension | `dim_host`: chu nha Airbnb |
| Location Dimension | `dim_location`: khu vuc/neighbourhood |
| Date Dimension | `dim_date`: ngay, thang, mua |
| Transaction/Snapshot Fact | `fact_listing_snapshot`, `fact_calendar_daily`, `fact_review` |

Tom lai, **Dimension dung de loc va chia nhom**, con **Fact dung de tinh so lieu**. Vi du, neu muon biet khu vuc nao dat nhat, dashboard se dung `dim_location` de biet khu vuc va `fact_listing_snapshot` de tinh `avg(price)`.

## 4. Thiet ke Dimension tables

### 4.1 Tong quan Dimension

| Bang | Loai bang | Grain | Y nghia |
|---|---|---|---|
| `dim_listing` | Dimension | 1 dong / listing | Mo ta san pham Airbnb la phong/can ho cho thue |
| `dim_host` | Dimension | 1 dong / host | Mo ta chu nha Airbnb |
| `dim_location` | Dimension | 1 dong / neighbourhood | Mo ta khu vuc dia ly |
| `dim_date` | Dimension | 1 dong / ngay | Mo ta thoi gian de phan tich theo ngay, thang, quy, mua |

### 4.2 `dim_listing`

Grain: **1 dong / listing**.

Bang nay mo ta tung listing Airbnb. Day la bang tuong duong voi `dim_product` trong bai ban hang.

| Cot | Y nghia |
|---|---|
| `listing_key` | Surrogate key cua listing |
| `listing_id` | Natural key tu Airbnb |
| `host_key` | Khoa lien ket den `dim_host` |
| `location_key` | Khoa lien ket den `dim_location` |
| `listing_name` | Ten listing |
| `property_type` | Loai bat dong san |
| `room_type` | Loai phong |
| `accommodates` | So khach toi da |
| `bathrooms` | So phong tam |
| `bedrooms` | So phong ngu |
| `beds` | So giuong |
| `amenities` | Danh sach tien nghi |
| `instant_bookable` | Co cho dat ngay hay khong |
| `latitude` | Vi do cua tung listing |
| `longitude` | Kinh do cua tung listing |

Luu y: `latitude` va `longitude` can nam o cap listing de ve chinh xac vi tri tung can tren ban do. `dim_location` chi co toa do trung binh cua khu vuc nen khong du cho ban do chi tiet.

### 4.3 `dim_host`

Grain: **1 dong / host**.

Bang nay mo ta chu nha Airbnb. Day la bang tuong duong voi supplier/seller dimension.

| Cot | Y nghia |
|---|---|
| `host_key` | Surrogate key cua host |
| `host_id` | Natural key cua host tu Airbnb |
| `host_name` | Ten host |
| `host_since` | Ngay host tham gia Airbnb |
| `host_location` | Vi tri host khai bao |
| `host_is_superhost` | Host co phai Superhost khong |
| `host_identity_verified` | Host da xac minh danh tinh chua |
| `host_response_time` | Thoi gian phan hoi |
| `host_response_rate` | Ty le phan hoi |
| `host_acceptance_rate` | Ty le chap nhan booking |
| `observed_listing_count` | So listing quan sat duoc trong du lieu |

### 4.4 `dim_location`

Grain: **1 dong / neighbourhood**.

Bang nay mo ta khu vuc dia ly cua listing.

| Cot | Y nghia |
|---|---|
| `location_key` | Surrogate key cua khu vuc |
| `city` | Thanh pho, hien la Bangkok |
| `neighbourhood` | Ten khu vuc/quang |
| `neighbourhood_group` | Nhom khu vuc neu co |
| `avg_latitude` | Vi do trung binh cua cac listing trong khu vuc |
| `avg_longitude` | Kinh do trung binh cua cac listing trong khu vuc |
| `listing_count` | So listing trong khu vuc |

### 4.5 `dim_date`

Grain: **1 dong / ngay**.

Bang nay dung de phan tich theo ngay, thang, quy, nam va mua.

| Cot | Y nghia |
|---|---|
| `date_key` | Khoa ngay dang `yyyymmdd` |
| `date` | Ngay day du |
| `day` | Ngay trong thang |
| `month` | Thang |
| `month_name` | Ten thang |
| `quarter` | Quy |
| `year` | Nam |
| `day_of_week` | Thu trong tuan |
| `is_weekend` | Co phai cuoi tuan khong |
| `season` | Mua/nhom thang phuc vu phan tich |

## 5. Thiet ke Fact tables

### 5.1 Tong quan Fact

| Bang | Loai fact | Grain | Y nghia |
|---|---|---|---|
| `fact_listing_snapshot` | Snapshot fact | 1 dong / listing / lan scrape gan nhat | Luu trang thai hien tai cua listing |
| `fact_calendar_daily` | Periodic snapshot fact | 1 dong / listing / ngay | Luu gia va tinh trang con trong theo tung ngay |
| `fact_review` | Transaction fact | 1 dong / review | Luu su kien review cua khach |

### 5.2 `fact_listing_snapshot`

Grain: **1 dong / listing / lan scrape gan nhat**.

Bang nay luu cac chi so hien tai cua listing tai thoi diem du lieu duoc crawl. Trong source hien tai, `silver_listings_cleaned` da dedupe theo `listing_id`, nen fact nay dang dai dien cho snapshot moi nhat cua moi listing, chua phai lich su nhieu lan scrape.

| Cot | Vai tro | Y nghia |
|---|---|---|
| `listing_key` | Foreign key | Lien ket den `dim_listing` |
| `host_key` | Foreign key | Lien ket den `dim_host` |
| `location_key` | Foreign key | Lien ket den `dim_location` |
| `date_key` | Foreign key | Ngay scrape, lay tu `last_scraped` |
| `price` | Measure | Gia listing |
| `availability_30` | Measure | So ngay con trong trong 30 ngay |
| `availability_60` | Measure | So ngay con trong trong 60 ngay |
| `availability_90` | Measure | So ngay con trong trong 90 ngay |
| `availability_365` | Measure | So ngay con trong trong 365 ngay |
| `number_of_reviews` | Measure | Tong so review |
| `number_of_reviews_ltm` | Measure | So review trong 12 thang gan nhat |
| `reviews_per_month` | Measure | So review trung binh moi thang |
| `review_scores_rating` | Measure | Diem rating tong the |
| `review_scores_cleanliness` | Measure | Diem sach se |
| `review_scores_location` | Measure | Diem vi tri |
| `review_scores_value` | Measure | Diem dang tien |

Neu sau nay muon phan tich lich su bien dong qua nhieu dot scrape, can thay doi grain thanh **1 dong / listing / last_scraped** va khong dedupe chi giu listing moi nhat o Silver.

### 5.3 `fact_calendar_daily`

Grain: **1 dong / listing / ngay**.

Bang nay luu du lieu lich theo tung ngay, phu hop de phan tich xu huong gia theo thang/mua va tinh trang con trong.

| Cot | Vai tro | Y nghia |
|---|---|---|
| `listing_key` | Foreign key | Lien ket den `dim_listing` |
| `location_key` | Foreign key | Lien ket den `dim_location` |
| `date_key` | Foreign key | Ngay trong lich |
| `is_available` | Measure/flag | Ngay do listing co con trong khong |
| `price` | Measure | Gia theo ngay |
| `adjusted_price` | Measure | Gia dieu chinh theo ngay |
| `minimum_nights` | Measure | So dem toi thieu |
| `maximum_nights` | Measure | So dem toi da |

### 5.4 `fact_review`

Grain: **1 dong / review**.

Bang nay luu moi review nhu mot su kien. No phuc vu phan tich chat luong listing va cung cap comment cho LLM.

| Cot | Vai tro | Y nghia |
|---|---|---|
| `review_key` | Surrogate key | Khoa cua review |
| `review_id` | Natural key | ID review tu Airbnb |
| `listing_key` | Foreign key | Lien ket den `dim_listing` |
| `host_key` | Foreign key | Lien ket den `dim_host` |
| `location_key` | Foreign key | Lien ket den `dim_location` |
| `date_key` | Foreign key | Ngay review |
| `reviewer_id` | Degenerate attribute | ID nguoi review tu source |
| `reviewer_name` | Degenerate attribute | Ten nguoi review |
| `has_comment` | Measure/flag | Review co comment hay khong |
| `comment_length` | Measure | Do dai comment |
| `comments` | Text attribute | Noi dung comment cho LLM |

Luu y: `comments` la text attribute phuc vu LLM, khong phai measure so. Neu trinh bay Kimball chat che, co the giai thich day la thuoc tinh cua su kien review.

## 6. Thiet ke Mart tables

Mart la bang tong hop san de dashboard, ML va LLM doc nhanh hon. Mart khong thay the Kimball core, ma nam sau cac bang Dimension va Fact.

| Mart | Grain | Muc dich |
|---|---|---|
| `mart_neighbourhood_market` | 1 dong / neighbourhood / room_type | Tong hop thi truong theo khu vuc va loai phong |
| `mart_host_performance` | 1 dong / host | Tong hop hieu qua hoat dong cua host |
| `mart_competitor_benchmark` | 1 dong / listing / top N competitor | So sanh listing voi doi thu truc tiep |
| `mart_ml_price_features` | 1 dong / listing | Dataset sach de train ML du doan gia |
| `mart_llm_area_summary` | 1 dong / neighbourhood / room_type | Context tom tat cho LLM sinh insight |

### 6.1 `mart_neighbourhood_market`

Grain: **1 dong / neighbourhood / room_type**.

| Cot | Y nghia |
|---|---|
| `neighbourhood` | Khu vuc |
| `room_type` | Loai phong |
| `listing_count` | So listing |
| `host_count` | So host |
| `avg_price` | Gia trung binh |
| `median_price` | Gia trung vi |
| `min_price` | Gia thap nhat |
| `max_price` | Gia cao nhat |
| `avg_rating` | Rating trung binh |
| `avg_availability_365` | So ngay con trong trung binh |
| `avg_reviews_per_month` | Review/thang trung binh |
| `avg_latitude` | Toa do trung binh khu vuc |
| `avg_longitude` | Toa do trung binh khu vuc |

### 6.2 `mart_host_performance`

Grain: **1 dong / host**.

| Cot | Y nghia |
|---|---|
| `host_id` | ID host |
| `host_name` | Ten host |
| `host_is_superhost` | Co phai Superhost khong |
| `observed_listing_count` | So listing cua host |
| `avg_price` | Gia trung binh cac listing cua host |
| `avg_rating` | Rating trung binh |
| `avg_reviews_per_month` | Review/thang trung binh |
| `avg_response_rate` | Ty le phan hoi trung binh |
| `avg_acceptance_rate` | Ty le chap nhan trung binh |

### 6.3 `mart_competitor_benchmark`

Grain: **1 dong / listing / 1 competitor trong Top N**.

Bang nay khong nen cross join tat ca listing trong cung khu vuc vi se gay bung no du lieu. Vi du, mot khu co 3,000 listing thi cross join co the tao 9,000,000 dong.

Quy tac nen dung:

| Tieu chi | Y nghia |
|---|---|
| Cung `neighbourhood` | Cung khu vuc canh tranh |
| Cung `room_type` | Cung loai phong |
| `accommodates` gan nhau | Suc chua tuong duong |
| Gan ve dia ly | Tinh bang Haversine tu `latitude`, `longitude` |
| Chi lay Top N | Nen lay Top 5 hoac Top 10 competitor cho moi listing |

| Cot | Y nghia |
|---|---|
| `listing_id` | Listing goc |
| `competitor_listing_id` | Listing doi thu |
| `neighbourhood` | Khu vuc |
| `room_type` | Loai phong |
| `price` | Gia listing goc |
| `competitor_price` | Gia listing doi thu |
| `price_difference` | Chenh lech gia |
| `rating` | Rating listing goc |
| `competitor_rating` | Rating doi thu |
| `reviews_per_month` | Review/thang cua listing goc |
| `competitor_reviews_per_month` | Review/thang cua doi thu |
| `distance_km` | Khoang cach dia ly |
| `benchmark_rank` | Thu hang doi thu gan/phu hop nhat |

### 6.4 `mart_ml_price_features`

Grain: **1 dong / listing**.

Bang nay la dataset train model du doan gia.

| Cot | Vai tro |
|---|---|
| `listing_id` | ID |
| `price` | Target |
| `neighbourhood` | Feature categorical |
| `room_type` | Feature categorical |
| `property_type` | Feature categorical |
| `accommodates` | Feature numeric |
| `bathrooms` | Feature numeric |
| `bedrooms` | Feature numeric |
| `beds` | Feature numeric |
| `availability_365` | Feature numeric |
| `review_scores_rating` | Feature numeric |
| `reviews_per_month` | Feature numeric |
| `host_is_superhost` | Feature boolean |
| `host_response_rate` | Feature numeric |
| `instant_bookable` | Feature boolean |

### 6.5 `mart_llm_area_summary`

Grain: **1 dong / neighbourhood / room_type**.

Bang nay cung cap context ngan gon de LLM sinh insight.

| Cot | Y nghia |
|---|---|
| `neighbourhood` | Khu vuc |
| `room_type` | Loai phong |
| `listing_count` | So listing |
| `avg_price` | Gia trung binh |
| `median_price` | Gia trung vi |
| `avg_rating` | Rating trung binh |
| `avg_availability_365` | So ngay con trong trung binh |
| `avg_reviews_per_month` | Demand proxy bang review/thang |
| `review_comment_sample` | Mau comment review |
| `pricing_note` | Ghi chu rule-based de LLM doc |

## 7. Mapping bang voi dashboard

| Dashboard tab | Bang su dung |
|---|---|
| Market Overview & Geospatial Analysis | `fact_listing_snapshot`, `fact_calendar_daily`, `dim_listing`, `dim_location`, `dim_date`, `mart_neighbourhood_market` |
| Host Performance & Competitor Benchmarking | `dim_host`, `dim_listing`, `dim_location`, `fact_listing_snapshot`, `mart_host_performance`, `mart_competitor_benchmark` |
| ML Simulator & LLM Insights | `mart_ml_price_features`, `mart_llm_area_summary`, `fact_review`, `dim_listing`, `dim_location` |

## 8. Quy tac tao Surrogate Key

Theo Kimball, Gold layer nen dung surrogate key thay vi chi dung natural key tu source.

| Key | Cach tao goi y |
|---|---|
| `listing_key` | `md5(cast(listing_id as varchar))` |
| `host_key` | `md5(cast(host_id as varchar))` |
| `location_key` | `md5(lower(coalesce(neighbourhood, 'unknown')))` |
| `review_key` | `md5(cast(review_id as varchar))` |
| `date_key` | `yyyymmdd` tu cot ngay |

## 9. Vi sao dung Random Forest Regressor

ML Simulator trong dashboard se du doan gia listing bang Random Forest Regressor.

| Ly do | Giai thich |
|---|---|
| Phu hop du lieu tabular | Du lieu Airbnb gom numeric, categorical va boolean |
| Bat duoc quan he phi tuyen | Gia phu thuoc phuc tap vao khu vuc, loai phong, rating, so giuong |
| De demo | Nguoi dung nhap thong tin listing, model tra gia de xuat |
| Co feature importance | Co the hien thi yeu to nao anh huong nhieu nhat den gia |
| Khong can target tu che | `price` co san trong du lieu |

## 10. Luu y ve grain va uniqueness

Theo logic Silver hien tai:

| Silver table | Grain | Co so de tin grain unique |
|---|---|---|
| `silver_listings_cleaned` | 1 dong / `listing_id` | Dedupe theo `listing_id`, co test unique |
| `silver_hosts` | 1 dong / `host_id` | Group by `host_id`, co test unique |
| `silver_locations` | 1 dong / `neighbourhood` | Dedupe theo `lower(neighbourhood)`, `location_key` unique |
| `silver_calendar` | 1 dong / `listing_id` / `calendar_date` | Co test unique combination |
| `silver_reviews` | 1 dong / `review_id` | Co test unique |

Vi vay cac grain Gold de xuat la hop ly:

| Gold table | Grain de xuat | Trang thai |
|---|---|---|
| `dim_listing` | 1 dong / listing | On |
| `dim_host` | 1 dong / host | On |
| `dim_location` | 1 dong / neighbourhood | On |
| `dim_date` | 1 dong / ngay | On |
| `fact_listing_snapshot` | 1 dong / listing / lan scrape gan nhat | On, nhung hien chua co lich su nhieu scrape |
| `fact_calendar_daily` | 1 dong / listing / ngay | On |
| `fact_review` | 1 dong / review | On |
| `mart_competitor_benchmark` | 1 dong / listing / top N competitor | On neu gioi han Top N, khong cross join toan bo |

## 11. Ket luan

Thiet ke nay dap ung dung yeu cau cua mo hinh Kimball: Dimension luu thong tin mo ta, Fact luu chi so do luong, Mart tong hop du lieu de phuc vu dashboard, ML va LLM. Viec khong tao `dim_customer` la hop ly vi dataset Airbnb hien tai khong co du lieu khach dat phong that.

He thong co the phan tich duoc day du 3 nhom noi dung: tong quan thi truong va dia ly, hieu qua host va doi thu canh tranh, mo phong gia bang ML va dien giai bang LLM. Hai diem can chu y khi trien khai la them `latitude`, `longitude` o cap `dim_listing` va gioi han `mart_competitor_benchmark` thanh Top 5 hoac Top 10 competitor cho moi listing de tranh bung no du lieu.
