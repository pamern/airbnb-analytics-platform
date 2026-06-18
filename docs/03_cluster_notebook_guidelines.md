# Huong dan notebook 03_cluster.ipynb

## Muc tieu

Notebook `03_cluster.ipynb` thuc hien Giai doan 2: Phan nhom thi truong listing Airbnb.

Muc tieu cua giai doan nay khong phai la du doan gia ngay, ma la:

```text
Phan nhom cac listing co dac diem tuong tu nhau
-> sau do so sanh gia trong tung segment
```

Cach hieu ngan gon:

```text
Tim listing giong nhau truoc, roi moi so gia.
```

Vi vay, `price` khong duoc dua vao K-means. `price` chi duoc dung sau khi da co cluster de danh gia listing dang re hay cao so voi cac listing tuong tu.

## Nguon du lieu

Dung data tu tang Silver, khong dung Gold cho notebook nay.

Ly do:

- Silver la data da duoc clean co ban tu Bronze/raw.
- Silver da chuan hoa kieu du lieu, gia tien, percent, boolean, date va duplicate.
- Silver van giu nhieu cot goc can cho clustering nhu `latitude`, `longitude`, `amenities`, `minimum_nights`, `neighbourhood`.
- Gold hien phu hop hon cho ML feature mart hoac dashboard, nhung khong day du cac cot can cho ban clustering nay.

Bang uu tien:

```text
silver.silver_listings_cleaned
```

Neu chay lai dbt theo repo hien tai va ten bang thay doi, co the dung:

```text
silver.silver_listings
```

Khong doc truc tiep tu raw/Bronze vi raw con nhieu van de nhu `price` dang text, percent dang chuoi, boolean/date chua chuan hoa.

## Cot can doc

Doc cac cot sau tu Silver:

```text
listing_id
price
neighbourhood
room_type
property_type
latitude
longitude
accommodates
bedrooms
bathrooms
beds
amenities
minimum_nights
number_of_reviews
review_scores_rating
host_is_superhost
```

Luu y:

- `listing_id` la khoa cua listing, khong dung `id`.
- `price` duoc doc vao de phan tich sau cluster, khong dua vao K-means.
- `neighbourhood` duoc doc vao de dien giai cluster, khong dua vao K-means trong ban chinh.

## Bien dua vao clustering

Feature matrix cho K-means nen gom:

```text
room_type
property_base_group
latitude
longitude
accommodates
bedrooms
bathrooms
beds
amenities_count
minimum_nights_log
review_scores_rating
has_review
host_is_superhost
```

Khong dung trong K-means:

```text
price
neighbourhood
listing_id
```

Trong do:

- `price`: dung sau cluster de so sanh gia trong segment.
- `neighbourhood`: la text/category nhieu gia tri, neu one-hot se tao nhieu cot va co the lam cluster bi chi phoi boi khu vuc. Trong ban chinh, chi dung de dien giai sau khi cluster.
- `listing_id`: chi la dinh danh, khong co y nghia khoang cach.

## Xu ly property_type

Khong nen dung truc tiep `property_type` goc vi cot nay co nhieu gia tri va co the trung y nghia voi `room_type`.

Tao bien moi:

```text
property_base_group
```

Gom nhom theo loai tai san:

| Nhom | Vi du keyword |
| --- | --- |
| Apartment / Condo | rental unit, condo, apartment |
| House / Home | home, house, townhouse |
| Serviced apartment | serviced apartment |
| Hotel / Hostel / Guesthouse | hotel, hostel, guesthouse, bed and breakfast |
| Villa | villa |
| Other / Unique | cac loai hiem hoac kho phan loai |

Can viet function:

```python
def group_property_type(value):
    ...
```

Sau khi tao cot, can in `value_counts()` de kiem tra ket qua gom nhom.

## Xu ly amenities

Cot `amenities` la text dang list, khong dua truc tiep vao K-means.

Tao bien:

```text
amenities_count
```

Y nghia:

```text
amenities_count = so luong tien nghi cua listing
```

Neu `amenities` rong, null hoac parse loi thi tra ve 0.

Day la ban clustering dau tien nen chi dung so luong tien nghi de giu mo hinh gon va de giai thich. Cac phien ban sau co the tach them cac tien nghi quan trong nhu pool, kitchen, wifi, gym.

## Xu ly missing value

Quy tac xu ly missing:

| Bien | Cach xu ly |
| --- | --- |
| `price` | Loai dong thieu price, vi price can de so sanh sau cluster |
| `bedrooms` | Dien median theo `room_type` |
| `bathrooms` | Dien median theo `room_type` |
| `beds` | Dien median theo `room_type` |
| `review_scores_rating` | Tao `has_review` truoc, sau do dien 0 |
| `host_is_superhost` | Missing -> False/0 |
| `minimum_nights_log` | Tao tu `log1p(minimum_nights)` sau khi doc data |

Voi data Silver hien tai, cac dong `review_scores_rating` null trung voi cac listing co `number_of_reviews = 0`. Dieu nay co nghia la null rating chu yeu dai dien cho listing chua co review, khong phai loi du lieu ngau nhien.

Tao `has_review` nhu sau:

```python
df["has_review"] = df["review_scores_rating"].notna().astype(int)
df["review_scores_rating"] = df["review_scores_rating"].fillna(0)
```

Hoac co the dung `number_of_reviews`:

```python
df["has_review"] = (df["number_of_reviews"].fillna(0) > 0).astype(int)
df["review_scores_rating"] = df["review_scores_rating"].fillna(0)
```

Trong du lieu hien tai, hai cach nay cho ket qua tuong duong.

Can giai thich ro:

```text
review_scores_rating = 0 khong co nghia la rating kem.
Gia tri 0 chi dai dien cho listing chua co review de mo hinh xu ly duoc du lieu so.
```

## Xu ly categorical va boolean

Categorical variables:

```text
room_type
property_base_group
```

Xu ly bang one-hot encoding.

Khong dung label encoding vi label encoding tao thu tu gia giua cac nhom.

Boolean variable:

```text
host_is_superhost
```

Chuyen ve 0/1:

```text
True -> 1
False -> 0
missing -> 0
```

## Xu ly numeric va scale

Numeric variables:

```text
latitude
longitude
accommodates
bedrooms
bathrooms
beds
amenities_count
minimum_nights_log
review_scores_rating
has_review
host_is_superhost
```

Tao `minimum_nights_log = log1p(minimum_nights)` va dung bien log trong K-means de giam anh huong outlier. Khi dien giai cluster va luu output, van hien thi `minimum_nights` goc cho de hieu.

Can scale cac bien numeric truoc khi chay K-means vi K-means dua tren khoang cach.

Khuyen nghi:

```text
StandardScaler
```

Luu y:

- Scale chi dung cho model.
- Khi dien giai cluster, quay lai dataframe goc chua scale de doc median/mean.

## Tao feature matrix

Feature matrix `X_cluster` gom:

```text
one-hot room_type
one-hot property_base_group
scaled latitude
scaled longitude
scaled accommodates
scaled bedrooms
scaled bathrooms
scaled beds
scaled amenities_count
scaled minimum_nights_log
scaled review_scores_rating
has_review
host_is_superhost
```

Can kiem tra:

```python
X_cluster.shape
X_cluster.isna().sum().sum()
X_cluster.dtypes
```

Dam bao:

- Khong con missing value.
- Tat ca cot deu la numeric.
- `price` khong nam trong `X_cluster`.
- `neighbourhood` khong nam trong `X_cluster`.

## Chon so cum K

Thu nhieu gia tri K, vi du:

```text
k = 2 den 10
```

Tinh:

```text
inertia
silhouette_score
```

Chon K dua tren:

- Elbow method.
- Silhouette score.
- Kich thuoc cluster khong qua lech.
- Kha nang dien giai ve mat business.

Khong chon K chi vi score cao. Cluster phai co y nghia voi bai toan Airbnb.

## Chay K-means final

Sau khi chon K:

- Chay K-means final.
- Set `random_state` de tai lap ket qua.
- Tao cot `cluster`.
- In so luong listing moi cluster.
- Kiem tra co cluster nao qua nho hay khong.
- Kiem tra centroid/tam cum sau khi train.

Vi du:

```python
kmeans = KMeans(n_clusters=selected_k, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_cluster)
```

## Kiem tra centroid va listing dai dien

Sau khi chon K va chay K-means final, can xem tam cum de hieu moi cluster dai dien cho dang listing nao.

Do feature matrix da one-hot va scale, centroid trong khong gian model khong nen doc truc tiep nhu dataframe goc. Can lam 2 viec:

1. Chuyen phan numeric cua centroid ve lai thang do goc bang scaler inverse transform.
2. Tim mot vai listing gan centroid nhat trong moi cluster de lam listing dai dien.

Can tao bang:

```text
centroid_numeric
```

Gom cac cot numeric o thang do goc:

```text
cluster
latitude
longitude
accommodates
bedrooms
bathrooms
beds
amenities_count
minimum_nights_log
review_scores_rating
has_review
host_is_superhost
```

Can tao them bang:

```text
representative_listings
```

Gom 3 listing gan centroid nhat trong moi cluster, de kiem tra cluster co hop ly khong truoc khi dat ten segment.

## Dien giai cluster

Dien giai tren dataframe goc, khong dung du lieu scaled.

Tinh summary theo cluster:

```text
listing_count
median_price
mean_price
median_accommodates
median_bedrooms
median_bathrooms
median_beds
median_amenities_count
median_minimum_nights
median_review_scores_rating
has_review_rate
superhost_rate
top_room_type
top_property_base_group
top_neighbourhood
```

`neighbourhood` chi dung o buoc nay de tra loi:

```text
Cluster nay tap trung nhieu o khu vuc nao?
```

Vi du:

```python
df.groupby("cluster")["neighbourhood"].agg(
    lambda x: x.value_counts().head(3).index.tolist()
)
```

## Dat ten segment

Sau khi co summary, dat ten segment dua tren dac diem thuc te cua cluster.

Khong dat ten truoc khi xem data.

Vi du ten segment:

```text
Budget private rooms
Central entire apartments
Large family listings
Hotel/serviced stays
Long-stay listings
```

Tao cot:

```text
segment_name
```

## So sanh gia trong segment

Sau khi co cluster, moi dung `price`.

Tinh:

```text
segment_median_price
segment_mean_price
price_vs_segment_median
price_percentile_in_segment
```

Cong thuc:

```text
price_vs_segment_median = price / segment_median_price - 1
```

Dien giai:

```text
> 0: listing cao hon median cua segment
< 0: listing thap hon median cua segment
= 0: listing gan median cua segment
```

Co the gan nhan tham khao:

```text
price_vs_segment_median > 0.2  -> higher than segment median
-0.2 den 0.2                   -> near segment median
price_vs_segment_median < -0.2 -> lower than segment median
```

Day khong phai ket luan tuyet doi dung/sai ve gia, ma la tin hieu de ho tro danh gia chien luoc dinh gia.

## Output

Luu ket qua vao:

```text
ml/outputs/listings_with_segments.csv
ml/outputs/cluster_summary.csv
```

`listings_with_segments.csv` nen gom:

```text
listing_id
price
cluster
segment_name
segment_median_price
price_vs_segment_median
price_percentile_in_segment
neighbourhood
room_type
property_base_group
accommodates
bedrooms
bathrooms
beds
minimum_nights_log
review_scores_rating
has_review
host_is_superhost
```

`cluster_summary.csv` nen gom:

```text
cluster
segment_name
listing_count
median_price
mean_price
top_room_type
top_property_base_group
top_neighbourhood
median_accommodates
median_bedrooms
median_bathrooms
median_beds
median_amenities_count
median_minimum_nights
median_review_scores_rating
has_review_rate
superhost_rate
```

## Ket luan can co trong notebook

Cuoi notebook can co markdown ket luan:

1. Da tao duoc bao nhieu segment.
2. Moi segment co dac diem gi.
3. Segment nao co gia cao/thap.
4. Phan nhom giup so sanh gia cong bang hon nhu the nao.
5. Han che cua phuong phap:
   - Khong dung `price` de cluster.
   - `neighbourhood` khong dua vao K-means ban chinh de tranh one-hot qua nhieu cot.
   - `review_scores_rating` null duoc dien 0 sau khi tao `has_review`, can giai thich ro 0 la chua co review.
   - K-means nhay voi scale va outlier.
   - Cluster la cong cu ho tro so sanh, khong phai ket luan dinh gia tuyet doi.

## Cập nhật cải thiện (v2)

Dựa trên kết quả chạy thử nghiệm ban đầu, cần thực hiện một số cải tiến sau trong notebook:

1. **Thêm PCA 2D visualization**: Sử dụng `sklearn.decomposition.PCA` để giảm chiều dữ liệu xuống 2D và vẽ scatter plot thể hiện các cluster. Điều này giúp trực quan hóa mức độ tách biệt giữa các nhóm.
2. **Thêm giải thích lý do chọn K=5**: Mặc dù K=3 có Silhouette score cao nhất, nhưng K=5 giúp tách được các nhóm có ý nghĩa kinh doanh đặc thù (ví dụ: nhóm "Premium large family/group stays" gia đình/nhóm lớn). Cần ghi rõ lý do này bằng markdown để tránh việc chỉ chọn K theo điểm số.
3. **Sửa logic hàm đặt tên segment (`build_segment_name`)**: Hiện tại hàm đang bị trùng lặp tên giữa 2 cluster có đặc điểm `room_type` và `property_base_group` tương tự nhau (ví dụ: 2 cụm đều tên "Value entire apartment stays"). Cần bổ sung thêm tiêu chí như kích thước tập dữ liệu (`listing_count`), tiện nghi (`median_amenities_count`), hoặc chính sách lưu trú để tên gọi có tính phân biệt rõ ràng hơn.

## Checklist

```text
[ ] Da doc data tu Silver
[ ] Da dung listing_id thay cho id
[ ] Da giu price ngoai feature matrix
[ ] Da giu neighbourhood ngoai feature matrix va chi dung de dien giai
[ ] Da tao property_base_group
[ ] Da tao amenities_count
[ ] Da tao has_review
[ ] Da xu ly missing value
[ ] Da encode room_type va property_base_group
[ ] Da scale numeric variables
[ ] Da tao minimum_nights_log cho K-means va van giu minimum_nights goc de dien giai
[ ] Da thu nhieu K
[ ] Da chon K co giai thich
[ ] Da chay K-means final
[ ] Da kiem tra centroid/tam cum
[ ] Da lay listing dai dien gan centroid nhat
[ ] Da phan tich cluster bang du lieu goc
[ ] Da dat ten segment dua tren summary
[ ] Da tinh price_vs_segment_median
[ ] Da luu listings_with_segments.csv vao ml/outputs
[ ] Da luu cluster_summary.csv vao ml/outputs
[ ] Notebook co markdown giai thich tung buoc ngan gon
```
