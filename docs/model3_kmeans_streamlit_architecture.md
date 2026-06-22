# Model 3 KMeans Streamlit Architecture

## Scope

Trang `Model 3` trong `app/components/model_lab.py` se hien thi giao dien giong mau Price Forecast, nhung phase hien tai chi xu ly phan KMeans.

Trong phase nay:

- Price forecast trong o ket qua du bao duoc phep dung gia mock/fake de demo UI.
- KMeans phai dung model da train san, khong train lai trong Streamlit.
- Dropdown/input options khong doc tu `data/raw`.
- Dropdown/input options lay tu `silver.silver_listings`.
- Input cua user duoc transform lai theo logic tao `gold.gold_cluster_model_features`.
- Ket qua KMeans tra ve segment va cac chi so gia theo segment.
- Hinh visualize va giai thich cluster hien thi tu output/artifact da co, hoac tu logic visualize hien co.

## Existing Contracts

### Silver input for UI options

Nguon option cho form la bang:

```text
silver.silver_listings
```

Cac cot dung cho dropdown:

```text
neighbourhood
room_type
property_type
```

Bang nay duoc tao trong:

```text
dbt/models/silver/silver_listings.sql
```

### Gold feature contract for KMeans

Bang feature KMeans hien co la:

```text
gold.gold_cluster_model_features
```

Bang nay duoc tao trong:

```text
dbt/models/gold/gold_cluster_model_features.sql
```

SQL hien tai lay input tu:

```sql
from {{ ref('silver_listings') }}
```

Feature dua vao KMeans:

```text
room_type
property_base_group
accommodates
bedrooms
bathrooms
beds
amenities_count
minimum_nights_log
```

`price` khong dung de tao cluster, nhung duoc giu de tinh chi so gia theo segment.

### Trained KMeans model

Model da train san nam trong:

```text
ml/artifacts/listing_segmentation/<model_version>/model.joblib
```

Vi du artifact hien co:

```text
ml/artifacts/listing_segmentation/segment_v20260620_070427_641255/model.joblib
```

Khong train lai KMeans trong Streamlit.

## Proposed File Structure

Them cac file sau:

```text
app/
|-- data_access.py
|-- components/
|   |-- model_lab.py
|   `-- model3_kmeans.py
`-- services/
    `-- model3_kmeans_service.py
```

Vai tro tung file:

- `app/data_access.py`: doc option tu `silver.silver_listings`.
- `app/services/model3_kmeans_service.py`: transform input, load model da train, predict cluster, tinh chi so gia.
- `app/components/model3_kmeans.py`: render UI Model 3 va hien thi ket qua.
- `app/components/model_lab.py`: gan tab `Model 3` vao component moi.

## Data Access Layer

Them ham vao `app/data_access.py`:

```python
load_model3_dropdown_options()
```

Ham nay query `silver.silver_listings` de lay:

```sql
select distinct neighbourhood
from silver.silver_listings
where neighbourhood is not null
order by neighbourhood;
```

```sql
select distinct room_type
from silver.silver_listings
where room_type is not null
order by room_type;
```

```sql
select distinct property_type
from silver.silver_listings
where property_type is not null
order by property_type;
```

Ham nay chi phuc vu UI option. Khong chua business logic KMeans.

## Service Layer

Tao file:

```text
app/services/model3_kmeans_service.py
```

Service nay nen chua cac ham sau.

### `build_user_listing_frame`

Input la payload tu form Streamlit.

Ham nay transform input thanh DataFrame dung schema KMeans:

```text
listing_id
price
room_type
property_base_group
accommodates
bedrooms
bathrooms
beds
amenities_count
minimum_nights
minimum_nights_log
```

Logic can copy theo `gold_cluster_model_features.sql`:

- `property_type` thanh `property_base_group`.
- `minimum_nights` thanh `minimum_nights_log = log1p(max(minimum_nights, 0))`.
- `amenities_count` lay tu input UI.
- Numeric input duoc cast thanh number.

### `load_trained_kmeans_model`

Load model da train san tu:

```text
ml/artifacts/listing_segmentation/<model_version>/model.joblib
```

Co the chon latest folder trong `ml/artifacts/listing_segmentation/`, hoac dung mot version cu the neu can demo on dinh.

Neu tai su dung code hien co, ham load model nam o:

```text
ml/listing_segmentation/prediction.py
```

Ham lien quan:

```python
load_segmentation_model(path)
```

### `query_segment_prices`

Tinh price stats cho cluster duoc predict.

Can co bang/view reference chua it nhat:

```text
cluster
price
```

Neu bang assignment hien co khong co `price`, can query bang cach join assignment voi feature table:

```sql
gold.gold_listing_segments
join gold.gold_cluster_model_features using (listing_id)
```

Hoac tao view rieng cho Streamlit:

```text
gold.gold_listing_segment_prices
```

Ham mong muon:

```python
def query_segment_prices(connection, cluster: int, current_price: float) -> dict[str, float]:
    prices = connection.execute(
        f"SELECT price FROM {SEGMENT_TABLE} WHERE cluster = ? AND price IS NOT NULL",
        [int(cluster)],
    ).fetchdf()["price"]
    if prices.empty:
        raise ValueError(f"No reference prices found for cluster {cluster}")

    return {
        "segment_median_price": float(prices.median()),
        "segment_p25_price": float(prices.quantile(0.25)),
        "segment_p75_price": float(prices.quantile(0.75)),
        "segment_mean_price": float(prices.mean()),
        "price_percentile_in_segment": float((prices <= current_price).mean()),
    }
```

### `analyze_user_listing`

Ham tong cho button `Predict Price`:

```text
user input
-> build_user_listing_frame
-> load trained KMeans model
-> predict cluster
-> query segment prices
-> calculate price position
-> return result dict
```

Ket qua tra ve:

```text
cluster
segment_name
current_price
segment_median_price
segment_p25_price
segment_p75_price
segment_mean_price
price_vs_segment_median
price_percentile_in_segment
price_position
```

`price_vs_segment_median` tinh theo:

```python
current_price / segment_median_price - 1
```

`price_position`:

```text
current_price < segment_p25_price  -> Below segment range
current_price > segment_p75_price  -> Above segment range
otherwise                          -> Within segment range
```

## UI Layer

Tao file:

```text
app/components/model3_kmeans.py
```

File nay render giao dien Model 3.

Form input gom:

```text
Neighbourhood
Room Type
Property Type
Accommodates
Bedrooms
Bathrooms
Beds
Amenities Count
Minimum Nights
Number of Reviews
Reviews per Month
Review Score Rating
Superhost
Instant Bookable
```

Trong phase KMeans:

- `Neighbourhood` chi phuc vu UI/context, khong dua vao KMeans.
- `Number of Reviews`, `Reviews per Month`, `Review Score Rating`, `Superhost`, `Instant Bookable` chi phuc vu UI/context, khong dua vao KMeans.
- `Room Type`, `Property Type`, `Accommodates`, `Bedrooms`, `Bathrooms`, `Beds`, `Amenities Count`, `Minimum Nights` duoc dung de build feature KMeans.

Button van co the la:

```text
Predict Price
```

Nhung logic hien tai:

- Price forecast mock/fake de hien thi UI.
- Segment prediction dung KMeans that.

## Model Lab Integration

Trong:

```text
app/components/model_lab.py
```

Tab hien co:

```python
overview_tab, run_tab, cluster_tab, future_tab = st.tabs(
    ["Tong quan", "Chay du bao", "Cluster", "Model 3"]
)
```

Trong `future_tab`, thay placeholder bang:

```python
from components.model3_kmeans import render_model3_kmeans_page

with future_tab:
    render_model3_kmeans_page()
```

## Visualization

Logic visualize KMeans hien co nam o:

```text
ml/listing_segmentation/visualization.py
```

Ham lien quan:

```python
save_pca_cluster_plot(...)
save_all_charts(...)
```

Notebook:

```text
notebooks/06_listing_segmentation.ipynb
```

co logic PCA visualization tu `cluster_listing.csv`.

Huong cho Streamlit:

- Neu da co PNG chart, UI doc va hien bang `st.image`.
- Neu chua co PNG chart, tach/generate tu logic hien co trong `ml/listing_segmentation/visualization.py`.
- Duong dan output de tham chieu:

```text
ml/outputs/listing_segmentation/charts/
```

## Final Runtime Flow

```text
silver.silver_listings
    -> dropdown options

User nhap form Model 3
    -> app/services/model3_kmeans_service.py
    -> transform input theo gold_cluster_model_features
    -> load trained KMeans artifact
    -> predict cluster
    -> query segment prices
    -> calculate price stats and price position
    -> app/components/model3_kmeans.py render result
```

## Guardrails

- Khong doc `data/raw` trong Streamlit.
- Khong train KMeans trong Streamlit.
- Khong dua cac field review/host/neighbourhood vao KMeans neu model hien tai khong dung chung.
- Khong viet lai pipeline encode/scale/KMeans trong UI.
- Khong viet business logic lon trong `model_lab.py`; chi goi component.
- Neu can logic transform, dat trong `app/services/model3_kmeans_service.py`.
- Neu can option cho dropdown, lay tu `silver.silver_listings`.
- Neu can price stats theo segment, dung bang/view co `cluster` va `price`, hoac join assignment voi `gold.gold_cluster_model_features`.
