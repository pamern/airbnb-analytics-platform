Hãy bổ sung cơ chế lưu và tải các file model `.joblib` bằng **Object Storage tương thích S3**, thay cho việc phụ thuộc vào thư mục artifact local.

## Bối cảnh

Project hiện có:

* Dagster orchestration.
* Price prediction model.
* Segmentation model.
* Model registry.
* Các artifact `.joblib`.
* Object Storage tương thích S3, ví dụ Cloudflare R2.
* Toàn bộ endpoint, access key, secret key, bucket và thông tin kết nối sẽ được cấu hình trong `.env`.

Mục tiêu:

```text
Training
→ lưu model tạm local
→ upload .joblib lên Object Storage
→ lưu artifact URI/object key vào model registry
→ Prediction/Dashboard tải model từ Object Storage khi cần
```

Không được commit API key, token hoặc secret vào source code.

---

# Yêu cầu cấu hình `.env`

Hãy kiểm tra các biến môi trường đang có trong project.

Có thể đổi tên để chuẩn hóa nếu cần, nhưng phải:

1. Cập nhật toàn bộ code liên quan.
2. Cập nhật `.env.example`.
3. Không đưa giá trị secret thật vào repository.
4. Giữ tương thích ngược nếu việc đổi tên có thể làm hỏng môi trường hiện tại, hoặc báo cáo rõ biến cũ và biến mới.

Ưu tiên chuẩn hóa thành:

```env
OBJECT_STORAGE_ENDPOINT_URL=
OBJECT_STORAGE_ACCESS_KEY_ID=
OBJECT_STORAGE_SECRET_ACCESS_KEY=
OBJECT_STORAGE_BUCKET_NAME=
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_PREFIX=airbnb-models
```

Nếu project đã dùng tên như:

```env
R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
```

có thể tiếp tục sử dụng hoặc đổi sang tên chung `OBJECT_STORAGE_*`.

Nếu đổi tên, nên hỗ trợ fallback:

```python
endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT_URL") or os.getenv("R2_ENDPOINT_URL")
```

Không log:

* Access key.
* Secret key.
* Token.
* Connection string đầy đủ.

---

# Phạm vi thực hiện

Chỉ bổ sung hoặc sửa các phần liên quan trực tiếp đến:

* Object Storage client.
* Upload artifact `.joblib`.
* Download artifact `.joblib`.
* Tạo object key.
* Lưu artifact URI/object key vào model registry.
* Load model cho prediction.
* Load model cho segmentation.
* Cleanup file tạm.
* Cấu hình `.env.example`.
* Dependency cần thiết cho S3-compatible storage.

Không được thay đổi:

* Thuật toán training.
* Feature engineering.
* Model parameters.
* Metric calculation.
* Champion/Candidate/Archived logic.
* Promotion logic.
* Dataset.
* dbt models.
* Dagster schedule.
* Dashboard business logic.
* Prediction output.
* Segmentation output.
* SQL không liên quan đến artifact location.

Không refactor diện rộng.

---

# Bước 1: Audit artifact hiện tại

Tìm toàn bộ code liên quan đến:

```text
joblib.dump
joblib.load
pickle
artifact_path
artifact_uri
model_path
ml/artifacts
price_modeling
segmentation
model_registry
```

Xác định:

* File nào lưu model.
* File nào load model.
* Model registry đang lưu trường nào.
* Dashboard/prediction đang đọc model từ đâu.
* Có artifact metadata nào ngoài `.joblib` không.
* Có nhiều cách lưu artifact khác nhau không.

Không sửa ngay trước khi xác định đầy đủ flow hiện tại.

---

# Bước 2: Tạo Object Storage client dùng chung

Tạo module dùng chung, ví dụ:

đặt theo cấu trúc hiện tại của project.

Ưu tiên sử dụng `boto3` vì Object Storage tương thích S3.

Client phải được tạo từ biến môi trường:

```python
import boto3


def create_object_storage_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name=settings.region,
    )
```

Yêu cầu:

* Không tạo client riêng lẻ ở nhiều module.
* Không hard-code endpoint hoặc bucket.
* Có validation rõ khi thiếu biến môi trường.
* Error message không được chứa secret.
* Có type hints.
* Có logging phù hợp.

---

# Bước 3: Chuẩn hóa object key

Object key phải rõ ràng và không ghi đè model version khác.

Đề xuất:

```text
{prefix}/{model_name}/{model_version}/model.joblib
```

Ví dụ:

```text
airbnb-models/price_model/price_v20260623_133500/model.joblib
airbnb-models/segmentation_model/seg_v20260623_140000/model.joblib
```

Nếu có artifact bổ sung:

```text
airbnb-models/price_model/{version}/metadata.json
airbnb-models/price_model/{version}/metrics.json
airbnb-models/price_model/{version}/feature_schema.json
```

Trong lần này, ưu tiên bắt buộc cho `.joblib`. Chỉ upload artifact khác nếu flow hiện tại đã có và cần thiết để load model đúng.

Object key phải được tạo bằng một helper duy nhất.

---

# Bước 4: Upload model sau training

Sau khi model được train và lưu bằng:

```python
joblib.dump(model, local_path)
```

hãy upload file đó lên Object Storage.

Cần có helper tương đương:

```python
def upload_file(
    local_path: Path,
    object_key: str,
) -> str:
    ...
```

Kết quả trả về nên là một artifact reference chuẩn, ví dụ:

```text
s3://bucket-name/airbnb-models/price_model/version/model.joblib
```

Hoặc lưu riêng:

```text
bucket_name
object_key
```

Ưu tiên không lưu URL có signed token.

Sau upload thành công:

* Cập nhật model registry với artifact URI/object key.
* Không đánh dấu training thành công nếu upload artifact thất bại.
* Không promotion model nếu artifact chưa tồn tại.
* Xóa file tạm local nếu file đó chỉ dùng để upload.
* Nếu project cần local artifact để debug thì chỉ giữ khi có config cho phép.

Không upload bằng tên cố định như:

```text
model.joblib
```

ở root bucket vì sẽ ghi đè model cũ.

---

# Bước 5: Lưu artifact location vào model registry

Kiểm tra schema model registry hiện tại.

Nếu đã có cột:

```text
artifact_path
artifact_uri
model_path
```

hãy tái sử dụng cột phù hợp.

Giá trị nên lưu dạng:

```text
s3://<bucket>/<object_key>
```

Ví dụ:

```text
s3://airbnb-artifacts/airbnb-models/price_model/price_v20260623_133500/model.joblib
```

Không lưu:

* Secret.
* Signed URL có thời hạn.
* Local temporary path.
* Endpoint kèm credential.

Nếu registry chỉ chấp nhận local path, hãy thực hiện migration nhỏ nhất cần thiết hoặc bổ sung parsing tương thích, nhưng không thay đổi logic registry ngoài artifact reference.

---

# Bước 6: Download và load model

Prediction và segmentation phải có thể tải model từ Object Storage dựa trên artifact URI trong model registry.

Tạo helper tương đương:

```python
def download_file(
    object_key: str,
    destination: Path,
) -> Path:
    ...
```

Và:

```python
def load_joblib_artifact(
    artifact_uri: str,
):
    ...
```

Flow:

```text
Đọc Champion/Candidate được chọn
→ lấy artifact_uri
→ xác định bucket và object key
→ download về cache/local temp
→ joblib.load()
→ trả model
```

Yêu cầu:

* Không download lại model mỗi lần prediction nếu cùng version.
* Có cache theo `model_name + model_version + artifact_uri`.
* Cache phải được invalidated khi artifact URI hoặc version thay đổi.
* Không dùng Streamlit cache trong core training code.
* Nếu dashboard cần cache model, dùng cơ chế phù hợp với cấu trúc hiện tại.
* Không giữ file tạm không giới hạn.
* Không tải toàn bộ bucket.

---

# Bước 7: Cache artifact local

Có thể sử dụng cache directory như:

```text
.cache/model_artifacts/
```

hoặc thư mục cache hiện có của project.

Tên file cache phải bao gồm model version hoặc hash của artifact URI:

```text
.cache/model_artifacts/price_model/price_v20260623_133500/model.joblib
```

Trước khi download:

1. Kiểm tra file cache tồn tại.
2. Nếu tồn tại và hợp lệ thì load trực tiếp.
3. Nếu chưa có thì download.
4. Download vào file `.tmp`.
5. Sau khi thành công mới rename sang file chính thức.

Điều này tránh load file tải dở.

Thư mục cache phải được thêm vào `.gitignore`.

---

# Bước 8: Kiểm tra artifact tồn tại

Trước khi:

* Set Champion.
* Prediction.
* Batch prediction.
* Segmentation inference.

hãy kiểm tra artifact tồn tại trên Object Storage.

Có thể dùng `head_object`.

Nếu artifact không tồn tại, trả lỗi rõ:

```text
Artifact not found for model:
model_name=...
model_version=...
object_key=...
```

Không fallback âm thầm sang model version khác.

Không tự động promotion model khác.

---

# Bước 9: Xử lý lỗi

Phân biệt rõ:

* Thiếu environment variable.
* Không kết nối được Object Storage.
* Access denied.
* Bucket không tồn tại.
* Object không tồn tại.
* Upload thất bại.
* Download thất bại.
* File `.joblib` lỗi hoặc không load được.

Không dùng:

```python
except Exception:
    return None
```

Không che giấu lỗi.

Không in secret trong traceback tùy chỉnh hoặc log.

---

# Bước 10: Dependency

Nếu project chưa có, bổ sung dependency tối thiểu:

```text
boto3
```

Không thêm SDK Cloudflare riêng nếu không cần thiết.

Không tự động thay đổi phiên bản các package khác.

Cập nhật file dependency đúng theo project:

* `pyproject.toml`
* `requirements.txt`
* hoặc file quản lý package hiện tại.

---

# Bước 11: `.env.example`

Cập nhật `.env.example`:

```env
# S3-compatible Object Storage
OBJECT_STORAGE_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
OBJECT_STORAGE_ACCESS_KEY_ID=
OBJECT_STORAGE_SECRET_ACCESS_KEY=
OBJECT_STORAGE_BUCKET_NAME=
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_PREFIX=airbnb-models
```

Không đưa credential thật.

Nếu dùng Cloudflare R2, không dùng public bucket URL để upload artifact.

---

# Bước 12: Tương thích artifact cũ

Kiểm tra model registry có các version cũ đang lưu local path hay không.

Phải hỗ trợ rõ một trong hai phương án:

## Phương án ưu tiên

Hỗ trợ cả:

```text
local path
s3:// artifact URI
```

trong giai đoạn chuyển đổi.

Ví dụ:

```python
if artifact_uri.startswith("s3://"):
    return load_from_object_storage(artifact_uri)

return joblib.load(artifact_uri)
```

Không tự động xóa artifact cũ.

Không sửa registry cũ nếu chưa có migration được yêu cầu.

---

# Bước 13: Tests

Tạo unit tests không gọi Object Storage production thật.

Dùng mock cho boto3 để kiểm tra:

1. Tạo client đúng config.
2. Upload đúng bucket và object key.
3. Download đúng object.
4. Parse đúng `s3://bucket/key`.
5. Không ghi đè model version khác.
6. Load được `.joblib` sau download.
7. Cache ngăn download lặp lại.
8. Thiếu environment variable thì báo lỗi rõ.
9. Artifact không tồn tại thì báo lỗi.
10. Local artifact cũ vẫn load được nếu cần tương thích.

Không dùng credential thật trong test.

---

# Kiểm tra tích hợp

Sau khi sửa, kiểm tra:

* Price model training upload `.joblib` thành công.
* Segmentation model training upload `.joblib` thành công.
* Model registry lưu đúng artifact URI.
* Champion price model load được từ Object Storage.
* Champion segmentation model load được từ Object Storage.
* Candidate/Archived model được chọn vẫn load đúng artifact riêng.
* Prediction không download lại cùng model ở mỗi request.
* Không còn phụ thuộc bắt buộc vào `ml/artifacts/...` để inference.
* Không có secret trong source code.
* Không có secret trong Git diff.
* Dagster Definitions vẫn load.
* Schedule 13:35 không bị thay đổi.
* Business logic và metric không đổi.

Không cần chạy toàn bộ production pipeline nếu việc đó phát sinh compute hoặc ghi dữ liệu thật. Có thể dùng mock/local integration test.

---

# Kết quả cần báo cáo

Trả về:

## 1. Kiến trúc artifact mới

```text
Training
→ joblib dump tạm
→ upload Object Storage
→ registry artifact_uri
→ download/cache
→ joblib load
```

## 2. File đã sửa

Liệt kê từng file và mục đích thay đổi.

## 3. Environment variables

Nêu:

* Tên cũ.
* Tên mới nếu có.
* Biến fallback nếu có.
* Không hiển thị giá trị secret.

## 4. Object key convention

Nêu format đã sử dụng.

## 5. Registry

Nêu cột lưu artifact URI và ví dụ định dạng, không chứa credential.

## 6. Kết quả test

* Upload.
* Download.
* Cache.
* Price model.
* Segmentation model.
* Tương thích artifact cũ.

## 7. Xác nhận phạm vi

Xác nhận không thay đổi:

* Training logic.
* Prediction logic.
* Segmentation logic.
* Model promotion logic.
* dbt.
* Dagster schedule.
* Dashboard business logic.

Chỉ thực hiện đúng phạm vi lưu và tải artifact `.joblib` bằng Object Storage.
