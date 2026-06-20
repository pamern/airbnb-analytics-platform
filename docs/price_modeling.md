Hãy tái cấu trúc phần `price_modeling` của repository theo hướng module hóa, dễ kiểm thử, dễ tái sử dụng và có thể được Dagster gọi lại trong giai đoạn sau.

## 0. Phạm vi nhiệm vụ

Phạm vi chính:

* `notebooks/03_price_modeling.ipynb`
* `ml/price_modeling/`
* `ml/common/`
* `ml/outputs/price_modeling/`
* `ml/artifacts/price_modeling/`

Chỉ khảo sát để đảm bảo tương thích:

* `ml/listing_segmentation/`
* `dbt/models/gold/`
* `pyproject.toml`
* các test và file cấu hình liên quan.

Hiện tại:

* không tích hợp Dagster;
* không tạo Dagster asset, job, schedule hoặc sensor;
* không triển khai MLOps production đầy đủ;
* không commit;
* không push;
* không sửa lịch sử Git.

---

# 1. Bắt buộc sử dụng CodeGraph trước

Trước khi đọc tuần tự nhiều file hoặc chỉnh sửa code, hãy sử dụng CodeGraph để:

1. Lập bản đồ cấu trúc thư mục `ml/`.
2. Xác định import và dependency trong:

   * `ml/listing_segmentation/`
   * `notebooks/03_price_modeling.ipynb`
   * các module price modeling hiện có.
3. Tìm tất cả reference tới:

   * `ml/outputs/price_modeling`
   * `ml/artifacts/price_modeling`
   * `gold_price_model_features`
   * `03_price_modeling.ipynb`
4. Xác định file nào đang được notebook, script hoặc module khác import.
5. Xác định nguy cơ circular import hoặc breaking change khi tái cấu trúc.
6. Chỉ mở chi tiết những file thực sự liên quan sau khi có kết quả từ CodeGraph.

Không dựa hoàn toàn vào CodeGraph đối với:

* nội dung cell notebook;
* YAML;
* SQL;
* JSON metadata;
* file cấu hình.

Phải đọc file gốc trước khi sửa.

---

# 2. Tuyệt đối không truy cập MotherDuck

Trong toàn bộ nhiệm vụ này, không được:

* kết nối MotherDuck;
* sử dụng token MotherDuck;
* gọi `duckdb.connect()` tới MotherDuck;
* thực thi SQL trên MotherDuck;
* tải bảng Gold từ MotherDuck;
* đọc toàn bộ dữ liệu warehouse;
* kiểm tra schema bằng query database;
* chạy dbt để lấy dữ liệu;
* gọi API hoặc dịch vụ dữ liệu từ xa.

Không đọc dữ liệu production hoặc full dataset chỉ để tái cấu trúc code.

Chỉ được sử dụng:

* code hiện có trong repository;
* source code notebook;
* metadata local;
* CSV hoặc JSON local nhỏ nếu thực sự cần;
* dữ liệu synthetic;
* fixture tự tạo;
* schema suy ra từ code, dbt YAML hoặc tài liệu local.

Nếu cần biết schema đầu vào, ưu tiên theo thứ tự:

1. danh sách feature trong code;
2. validation hiện có;
3. dbt YAML local;
4. metadata JSON local;
5. header của CSV local nhỏ;
6. synthetic DataFrame đúng schema.

Nếu không thể xác minh vì không được đọc MotherDuck, ghi rõ là chưa được xác minh, không tự suy đoán.

---

# 3. Quy trình thực hiện bắt buộc

Thực hiện thành hai giai đoạn.

## Giai đoạn 1: Phân tích, chưa sửa code

1. Dùng CodeGraph khảo sát repository.
2. Đọc các file nguồn thực sự liên quan.
3. Phân tích notebook theo các nhóm:

   * cấu hình;
   * load và validation;
   * preprocessing;
   * baseline;
   * feature selection;
   * tuning;
   * training;
   * evaluation;
   * error analysis;
   * explainability;
   * lưu output;
   * lưu artifact.
4. Liệt kê:

   * file hiện tại và trách nhiệm;
   * logic đang nằm trong notebook;
   * logic đã nằm trong module Python;
   * file cần tạo;
   * file cần sửa;
   * file giữ nguyên;
   * thay đổi import dự kiến;
   * nguy cơ làm thay đổi kết quả.
5. Đề xuất cấu trúc tối thiểu.
6. Dừng lại sau khi trình bày kế hoạch.
7. Không sửa bất kỳ file nào trong giai đoạn này.

Chỉ bắt đầu Giai đoạn 2 sau khi người dùng chấp thuận kế hoạch.

## Giai đoạn 2: Triển khai

Sau khi kế hoạch được chấp thuận:

1. Tạo các module cần thiết.
2. Tách logic từ notebook.
3. Chuẩn hóa path.
4. Chuẩn hóa artifact và metadata.
5. Chỉnh notebook thành thin notebook.
6. Chạy import check.
7. Chạy smoke test bằng synthetic data hoặc local sample nhỏ.
8. Báo cáo kết quả.

---

# 4. Nguyên tắc bắt buộc khi chỉnh sửa

1. Không thay đổi thuật toán hiện tại nếu không cần.
2. Không thay đổi feature set đã chốt.
3. Không thay đổi hyperparameter đã chốt.
4. Không thay đổi random seed.
5. Không thay đổi cách chia train/test.
6. Không thay đổi target `log_price`.
7. Không thay đổi cách back-transform bằng `np.expm1`.
8. Không làm thay đổi metric ngoài sai số floating-point hợp lý.
9. Không viết lại toàn bộ notebook.
10. Không xóa markdown hoặc kết luận quan trọng.
11. Không sửa trực tiếp output lịch sử.
12. Không ghi đè artifact cũ.
13. Không hard-code đường dẫn tuyệt đối.
14. Không thêm dependency mới nếu chưa cần.
15. Không để code tự chạy khi import.
16. Mọi hàm public mới phải có:

    * type hints;
    * docstring;
    * validation phù hợp;
    * tên rõ nghĩa.
17. Dùng `logging`, không dùng `print` trong module lõi.
18. Phải chạy được từ root repository trên Windows.
19. Không sửa file ngoài phạm vi nếu không có lý do trực tiếp.
20. Không tự format hoặc rewrite file không liên quan.
21. Nếu logic chưa đủ rõ để tách an toàn, giữ nguyên và ghi chú.

---

# 5. Phạm vi đối với `listing_segmentation`

Không tái cấu trúc pipeline clustering trong nhiệm vụ này.

Chỉ được:

* khảo sát để nhận diện helper dùng chung;
* kiểm tra quy ước path;
* kiểm tra cách lưu artifact;
* kiểm tra API đang được sử dụng;
* tái sử dụng thiết kế tốt nếu phù hợp.

Không được:

* đổi tên file;
* di chuyển file;
* chia nhỏ module;
* sửa thuật toán clustering;
* sửa import;
* đổi artifact cũ;
* xóa artifact timestamp;
* chỉnh output clustering;
* thay đổi kết quả clustering.

Chỉ sửa `listing_segmentation` khi có helper dùng chung thực sự cần thiết và phải nêu rõ trong kế hoạch trước.

---

# 6. Cấu trúc thư mục định hướng

Đây là định hướng, không phải danh sách file bắt buộc:

```text
ml/
├── common/
│   ├── __init__.py
│   ├── paths.py
│   ├── artifact_manager.py
│   ├── run_manager.py
│   └── model_registry.py
│
├── listing_segmentation/
│   └── giữ nguyên cấu trúc hiện tại
│
├── price_modeling/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── preprocessing.py
│   ├── feature_selection.py
│   ├── tuning.py
│   ├── training.py
│   ├── evaluation.py
│   ├── error_analysis.py
│   ├── explainability.py
│   ├── prediction.py
│   └── pipeline.py
│
├── artifacts/
│   ├── listing_segmentation/
│   └── price_modeling/
│
└── outputs/
    ├── listing_segmentation/
    └── price_modeling/
        ├── charts/
        ├── csv/
        ├── metadata/
        ├── error_analysis/
        └── explainability/
```

Không tạo module riêng nếu:

* module chỉ chứa một hàm nhỏ;
* trách nhiệm chưa rõ;
* logic chưa tồn tại;
* làm tăng circular dependency;
* không được pipeline sử dụng;
* có thể gộp hợp lý vào module khác.

Ưu tiên số module tối thiểu nhưng rõ trách nhiệm.

---

# 7. Chế độ huấn luyện

Pipeline phải hỗ trợ ba chế độ:

```python
training_mode: Literal["retrain", "tune", "research"] = "retrain"
```

## 7.1. `retrain`

Đây là chế độ mặc định.

Chỉ train lại champion model đã được chọn trong giai đoạn nghiên cứu.

Phải sử dụng:

* champion algorithm đã chốt;
* selected feature set đã chấp nhận;
* best hyperparameters đã tuning;
* random seed hiện tại;
* cùng cách preprocessing hiện tại.

Không chạy:

* baseline comparison;
* DummyRegressor;
* Ridge;
* RandomForest;
* XGBoost;
* CatBoost;
* các model candidate khác;
* feature selection;
* Optuna tuning;
* model family selection.

Flow:

```text
receive DataFrame
→ validate
→ preprocess
→ selected features
→ build champion model
→ train
→ evaluate
→ save artifact
→ build metadata
```

## 7.2. `tune`

Chỉ chạy khi người dùng chủ động yêu cầu.

Chỉ tuning champion algorithm hiện tại.

Không tự động thử lại toàn bộ nhiều thuật toán.

Flow:

```text
receive DataFrame
→ preprocess
→ selected features
→ tune champion algorithm
→ train best trial
→ evaluate
→ save candidate artifact
```

## 7.3. `research`

Chỉ phục vụ nghiên cứu hoặc chạy lại baseline.

Có thể:

* so sánh nhiều model;
* chạy feature selection;
* thử model family;
* tái lập benchmark.

Không được chạy mặc định.

Không được gọi từ production retraining pipeline.

Các kết quả baseline trong notebook là kết quả nghiên cứu, không phải bước bắt buộc khi retrain.

---

# 8. `ml/common/paths.py`

Tạo helper xác định repository root bằng `pathlib.Path`.

Không dùng:

```python
"../../ml/outputs/..."
```

Cung cấp path cần thiết:

```python
REPO_ROOT
ML_ROOT
ARTIFACTS_ROOT
OUTPUTS_ROOT
PRICE_ARTIFACTS_DIR
PRICE_OUTPUTS_DIR
SEGMENTATION_ARTIFACTS_DIR
SEGMENTATION_OUTPUTS_DIR
```

Yêu cầu:

* tương thích Windows;
* không phụ thuộc mơ hồ vào current working directory;
* không tự tạo thư mục khi import;
* chỉ tạo thư mục khi ghi file.

---

# 9. `ml/price_modeling/config.py`

Chứa cấu hình bất biến:

* `model_task = "price_prediction"`;
* target column;
* random seed;
* test size;
* số fold;
* primary metric: RMSE;
* secondary metrics: MAE, R², adjusted R²;
* danh sách feature;
* selected feature set;
* feature set version;
* champion algorithm;
* best parameters;
* training mode;
* đường dẫn output;
* đường dẫn artifact;
* các cờ tùy chọn.

Ví dụ:

```python
@dataclass(frozen=True)
class PriceModelConfig:
    training_mode: Literal["retrain", "tune", "research"] = "retrain"
    champion_algorithm: str = "HistGradientBoostingRegressor"
    run_error_analysis: bool = True
    run_explainability: bool = True
```

Không đặt trong config:

* database connection;
* MotherDuck token;
* DataFrame;
* fitted estimator;
* fitted preprocessor;
* code có side effect.

---

# 10. `ml/price_modeling/data.py`

Chịu trách nhiệm:

* nhận DataFrame do caller truyền vào;
* hoặc đọc local file khi explicit path được truyền;
* validate cột bắt buộc;
* kiểm tra DataFrame rỗng;
* kiểm tra target;
* kiểm tra duplicate column;
* trả về DataFrame chuẩn hóa nhẹ.

Không được:

* kết nối MotherDuck;
* tự chạy SQL;
* tự đọc Gold table;
* đoán connection string;
* tải dữ liệu internet;
* ghi output;
* feature engineering phức tạp.

API dự kiến:

```python
load_local_price_data(path: Path) -> pd.DataFrame
validate_input_schema(
    df: pd.DataFrame,
    required_columns: Sequence[str],
) -> None
```

Pipeline phải hỗ trợ:

```python
run_price_training_pipeline(
    data=df,
    config=config,
)
```

---

# 11. `ml/price_modeling/preprocessing.py`

Tách logic:

* chọn feature;
* làm sạch target;
* tạo `log_price = np.log1p(price)`;
* xử lý boolean;
* imputation;
* encoding;
* xử lý review missing;
* property grouping nếu đang sử dụng;
* chia train/test đúng random seed;
* tạo transformer hoặc pipeline;
* lấy tên feature sau transform.

API dự kiến:

```python
prepare_modeling_frame(...)
split_train_test(...)
build_preprocessor(...)
get_transformed_feature_names(...)
```

Bắt buộc chống leakage:

* chia train/test trước khi fit preprocessor;
* không fit encoder hoặc imputer trên toàn dataset;
* không dùng test để feature selection;
* không dùng test trong tuning;
* không dùng test để chọn champion.

---

# 12. `ml/price_modeling/feature_selection.py`

Chỉ tách đúng logic feature selection hiện có.

Yêu cầu:

* không sáng tạo phương pháp mới;
* giữ metric RMSE;
* giữ tiêu chí chấp nhận selected subset;
* trả về danh sách feature;
* trả về summary DataFrame;
* không tự ghi file nếu caller không truyền path.

API dự kiến:

```python
run_feature_selection(...)
evaluate_feature_subset(...)
select_accepted_feature_set(...)
```

Module này chỉ được gọi trong:

* `research`;
* hoặc khi có cờ explicit.

Không được gọi trong `retrain`.

---

# 13. `ml/price_modeling/tuning.py`

Tách logic tuning hiện tại.

Yêu cầu:

* search space giống notebook;
* tối ưu RMSE;
* giữ random seed;
* giữ early stopping nếu đang dùng;
* không đánh giá test trong từng trial;
* không ghi đè model cuối;
* không tự chạy khi import.

API dự kiến:

```python
build_optuna_objective(...)
tune_model(...)
```

Module này:

* chỉ tuning champion algorithm;
* chỉ được gọi trong `tune`;
* không tự chạy nhiều model family.

Kết quả trả về:

* best parameters;
* best validation hoặc CV score;
* trials DataFrame;
* metadata cần thiết.

---

# 14. `ml/price_modeling/training.py`

Chứa logic huấn luyện model cuối cùng.

API dự kiến:

```python
build_price_pipeline(...)
build_champion_estimator(...)
train_price_model(...)
```

`build_champion_estimator()` phải tạo đúng champion algorithm từ config.

Ưu tiên lưu preprocessor và estimator trong cùng sklearn Pipeline nếu tương thích.

Không tự:

* đăng ký model;
* promote champion;
* kết nối database;
* chạy toàn pipeline;
* chạy baseline.

---

# 15. `ml/price_modeling/evaluation.py`

Tách logic:

* prediction;
* RMSE;
* MAE;
* R²;
* adjusted R²;
* fit time;
* predict time;
* cross-validation hiện tại;
* metric dạng dài.

API dự kiến:

```python
evaluate_regression_model(...)
cross_validate_model(...)
build_metrics_long_format(...)
```

Schema metric tối thiểu:

```text
model_version
dataset_type
metric_name
metric_value
metric_std
evaluated_at
```

Không tạo metric giả.

Trong `retrain`, chỉ đánh giá champion model.

---

# 16. `ml/price_modeling/error_analysis.py`

Tách logic:

* residual;
* absolute error;
* percentage error khi hợp lệ;
* underprediction;
* overprediction;
* lỗi theo neighbourhood;
* lỗi theo room type;
* lỗi theo price range;
* nhóm lỗi đang có trong notebook.

API dự kiến:

```python
build_prediction_error_frame(...)
summarize_errors_by_group(...)
```

Không tự ghi Gold table.

Không chạy nếu `run_error_analysis=False`.

---

# 17. `ml/price_modeling/explainability.py`

Tách đúng logic hiện tại:

* native importance;
* permutation importance;
* SHAP nếu đã có và dependency tồn tại;
* global importance DataFrame.

API dự kiến:

```python
calculate_native_importance(...)
calculate_permutation_importance(...)
```

Không:

* tự thêm SHAP nếu notebook chưa dùng;
* lưu toàn bộ SHAP từng listing;
* chạy explainability nặng trong smoke test;
* ghi MotherDuck.

Không chạy nếu `run_explainability=False`.

---

# 18. `ml/price_modeling/prediction.py`

Cung cấp API cho Streamlit sau này.

API dự kiến:

```python
load_price_model(...)
validate_prediction_input(...)
predict_price(...)
```

`predict_price()` phải:

* nhận dictionary hoặc DataFrame;
* validate feature;
* dùng đúng fitted pipeline;
* trả `predicted_log_price`;
* back-transform bằng `np.expm1`;
* kiểm tra NaN, infinity và giá âm;
* không phụ thuộc notebook;
* không kết nối database.

---

# 19. `ml/price_modeling/pipeline.py`

Đây là entry point cấp cao.

API dự kiến:

```python
run_price_training_pipeline(...)
run_price_evaluation_pipeline(...)
run_price_prediction_pipeline(...)
```

Ví dụ:

```python
run_price_training_pipeline(
    data: pd.DataFrame,
    config: PriceModelConfig,
    training_mode: Literal["retrain", "tune", "research"] = "retrain",
)
```

## Với `retrain`

```text
receive DataFrame
→ validate schema
→ prepare target/features
→ split train/test
→ build preprocessor
→ selected features
→ build champion estimator
→ train
→ evaluate
→ optional error analysis
→ optional explainability
→ save artifact
→ build TrainingResult
```

Không chạy:

* baseline;
* feature selection;
* tuning;
* model family comparison.

## Với `tune`

```text
receive DataFrame
→ validate
→ preprocess
→ selected features
→ tune champion algorithm
→ train best result
→ evaluate
→ save candidate artifact
```

## Với `research`

Cho phép gọi các bước nghiên cứu riêng nhưng không được là mặc định.

CLI nếu có:

```bash
python -m ml.price_modeling.pipeline \
  --input path/to/local_sample.csv \
  --mode retrain
```

Không có default đọc MotherDuck.

---

# 20. Artifact management

Artifact deployable lưu tại:

```text
ml/artifacts/price_modeling/<model_version>/
```

Ví dụ:

```text
price_v001/
├── model.joblib
├── feature_schema.json
├── training_config.json
└── metrics.json
```

Yêu cầu:

* không ghi đè version đã tồn tại;
* lưu bằng joblib;
* JSON UTF-8;
* serialize được numpy scalar;
* kiểm tra load lại được;
* prediction trước và sau load phải nhất quán.

Không lưu:

* PNG;
* CSV phân tích;
* notebook output;
* full trials;
* train/test data.

---

# 21. Run metadata và model registry

Chưa tự động ghi database.

Tạo object hoặc DataFrame tương ứng:

```text
gold_ml_training_runs
gold_ml_model_registry
gold_ml_model_metrics
```

Có thể dùng dataclass:

```python
TrainingRun
RegisteredModel
ModelMetric
TrainingResult
```

`TrainingResult` có thể chứa:

```python
run
model
metrics
artifact_paths
predictions
```

Tạo helper:

```python
build_training_run_record(...)
build_model_registry_record(...)
build_model_metric_records(...)
```

Trong nhiệm vụ này:

* chỉ trả về DataFrame hoặc dictionary;
* có thể export JSON/CSV local;
* không insert MotherDuck;
* không tạo bảng;
* không chạy dbt;
* không promote production tự động.

Không tạo `database.py` hoặc `motherduck_writer.py` nếu chưa có use case thật.

---

# 22. Output phân tích

Giữ output tại:

```text
ml/outputs/price_modeling/
```

Có thể chuẩn hóa:

```text
charts/
csv/
metadata/
error_analysis/
explainability/
```

Không di chuyển hàng loạt file cũ nếu có nguy cơ phá reference.

Không xóa hoặc ghi đè output lịch sử.

Nếu tạo output mới:

* dùng tên rõ;
* dùng version hoặc timestamp khi cần;
* tách output phân tích khỏi artifact.

---

# 23. Chỉnh notebook

Sau khi module hóa:

* giữ markdown;
* giữ thứ tự phân tích;
* giữ output quan trọng;
* giữ kết luận;
* thay implementation lặp bằng import;
* notebook chỉ điều phối và hiển thị;
* không chứa lại toàn bộ implementation;
* không sửa cell không liên quan;
* không rewrite toàn bộ notebook JSON;
* không chạy lại notebook bằng MotherDuck.

Nếu notebook không thể chạy đầy đủ do thiếu local data:

* chỉ kiểm tra import;
* kiểm tra cell độc lập;
* báo rõ giới hạn.

---

# 24. Logging và lỗi

Dùng `logging`.

Các bước cần log:

* run ID;
* model version;
* training mode;
* champion algorithm;
* số dòng input;
* số feature;
* feature set version;
* thời gian train;
* primary metric;
* artifact path;
* trạng thái success/failed.

Khi lỗi:

* không tạo `CHAMPION`;
* không ghi artifact không hoàn chỉnh;
* giữ error message;
* không che giấu exception quan trọng;
* không retry kết nối database.

---

# 25. Kiểm thử

Không dùng MotherDuck hoặc full dataset.

Ưu tiên:

1. synthetic DataFrame đúng schema;
2. fixture local;
3. CSV local nhỏ.

Kiểm tra tối thiểu:

1. Import module không lỗi.
2. Repository root đúng.
3. Schema validation hoạt động.
4. Preprocessor chỉ fit train.
5. `retrain` chỉ train champion model.
6. `retrain` không gọi feature selection.
7. `retrain` không gọi tuning.
8. `retrain` không gọi baseline comparison.
9. `tune` chỉ tuning champion algorithm.
10. Synthetic pipeline train được.
11. Model save/load được.
12. Prediction trước/sau load nhất quán.
13. JSON metadata serialize được.
14. Metric DataFrame đúng schema.
15. Artifact version không bị ghi đè.
16. `predict_price()` xử lý một bản ghi.
17. Không có MotherDuck connection.
18. Không có network call.
19. Không có side effect khi import.

Không chạy:

* full CV trên full dataset;
* Optuna nhiều trial;
* SHAP toàn dataset;
* full notebook;
* dbt build;
* MotherDuck query.

---

# 26. Lệnh chạy mong muốn

Import check:

```bash
python -c "import ml.price_modeling"
```

Smoke test:

```bash
python -m ml.price_modeling.pipeline --smoke-test
```

Retrain bằng local CSV:

```bash
python -m ml.price_modeling.pipeline \
  --input path/to/local_sample.csv \
  --mode retrain
```

Tune champion model:

```bash
python -m ml.price_modeling.pipeline \
  --input path/to/local_sample.csv \
  --mode tune
```

Không tạo lệnh mặc định tự đọc MotherDuck.

---

# 27. Báo cáo cuối cùng

Sau khi triển khai, báo cáo:

* CodeGraph xác định dependency gì;
* file tạo mới;
* file sửa;
* file giữ nguyên;
* cấu trúc cuối;
* entry point;
* champion algorithm đang dùng;
* selected features lấy từ đâu;
* best parameters lấy từ đâu;
* cách truyền DataFrame;
* cách chạy local CSV;
* cách chạy `retrain`;
* cách chạy `tune`;
* cách chạy smoke test;
* cách lưu/load artifact;
* output/artifact ở đâu;
* test đã chạy;
* test chưa chạy;
* phần chưa xác minh vì không truy cập MotherDuck;
* metric có thay đổi không;
* rủi ro tương thích còn lại.

Không tuyên bố đã xác minh production nếu chỉ dùng synthetic hoặc local sample.

Ưu tiên:

* đơn giản;
* rõ trách nhiệm;
* ít module nhưng hợp lý;
* giữ nguyên hành vi hiện tại;
* retrain mặc định chỉ chạy champion model;
* không over-engineer;
* không truy cập MotherDuck;
* không đọc dữ liệu lớn;
* không tiêu tốn token không cần thiết.
