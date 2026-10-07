# ML Model Comparison Lab

Module hiện tại: `ml-model-comparison.html` gọi same-origin `/api/ml-compare`.
NumPy/scikit-learn và openpyxl; không cần pandas hoặc framework web mới.

## Chạy và kiểm tra

```powershell
python -B api/ml-compare.py --serve
python -B tests/test_ml_model_comparison.py --backend-only
python -B tests/test_ml_model_comparison.py
npx vercel build
```

Tests tạo fixture tổng hợp, không ghi raw file của người dùng vào repository.
Fixture linelist tương đương 28 cột, dấu chấm phẩy, decimal comma, outcome,
ID/date/location; chưa có `linelist_raw.csv` trong workspace để kiểm tra file thật.

## Đọc bảng và làm sạch

CSV/TSV UTF-8 hoặc UTF-8 BOM: Sniffer nhận `,`, `;`, tab, `|`; khi Sniffer
không nhận được bảng ngắn/ragged, fallback so sánh các record đã parse theo
từng delimiter, vẫn tôn trọng quoting. Bỏ dòng trắng; loại duplicate; pad dòng
thiếu ô. Header cắt whitespace, header trống thành `unnamed_N`, trùng thành
`col_2`, `col_3` với kiểm tra collision. Quá nhiều ô ở một dòng trả validation error.

Giữ giới hạn file 2 MiB, 20.000 dòng dữ liệu, 100 cột, 4.096 ký tự/ô;
request JSON 4 MiB. XLSX base64 được kiểm tra ZIP/OOXML trước khi mở bằng
`openpyxl.load_workbook(read_only=True, data_only=True)`. Không chạy công thức:
dùng cached value hoặc missing. Kiểm tra mọi sheet, 32 MiB giải nén, 512 mục,
không chấp nhận DTD/entity. Multi-sheet cho chọn sheet, đổi sheet reset kết quả.

Số hữu hạn với decimal dot/exponent được đọc trực tiếp. Hỗ trợ `123,45`,
`1,234.56`, `1.234,56`, `-13,21573511` khi định dạng không mơ hồ.
`1,234` không được tự đoán decimal/thousands khi đứng riêng. Format được suy ra
theo cột với ít nhất hai giá trị decimal comma rõ ràng, nhất quán; nếu không đủ
bằng chứng giữ categorical / loại khỏi numeric target và cảnh báo. Không tự suy đoán mọi locale. Feature types suy ra trên
train; scaler/imputer/OHE chỉ fit trên train của mỗi CV fold.

Target không được impute. Bỏ rows target missing hoặc numeric target không
hợp lệ; audit.numeric_target báo total_rows, nonblank_target_rows,
valid_numeric_target_rows, missing_target_rows, invalid_numeric_target_rows,
unique_numeric_target_values. Missing gồm `--`. Reject target không tồn tại, toàn missing,
một giá trị, dưới 2 mẫu hợp lệ hoặc không còn feature. Classification có
giới hạn serverless 30 lớp. Date/ID target nhiều lớp có validation riêng; raw date
Regression gợi ý duration giữa hai mốc, không tự tạo target số.

ID/email/UUID/product code và categorical nhiều unique mặc định bỏ chọn;
user có thể override. OHE học rare groups trên train từng fold, mặc định tối
đa 32 nhóm/cột, unknown ignore. Ước lượng giới hạn 500 feature / 3 triệu ô:
giảm cap category, hoặc bỏ bớt categorical nếu cần và báo rõ. Cột toàn thiếu
trong train tự bỏ; ngày mơ hồ ở chế độ extract tự bỏ với warning. ISO/date
không mơ hồ có thể tách year/month/day/day_of_week; mặc định bỏ khỏi features.

Leakage info gồm column/reason/severity. Exact target-copy (hard) luôn bị loại;
không còn feature thì validation cụ thể. Correlation, mapping quan sát, tên đáng
nghi chỉ là warning: mặc định exclude + continue hoặc confirm + continue.
Không permanent 422 cho heuristic. Benchmark kiểm tra trên train, không dùng
test để chọn feature. Tên cột không chứng minh leakage; chưa hỗ trợ group split/embargo.
Feature guard báo estimated_before/after, excluded_columns, reason. Raw HH:MM
cũng bị bỏ để tránh OHE time. CSV export gồm cả status/reason các model bỏ qua.

Large data >4.000 rows bỏ SVM RBF/KNN để giới hạn chi phí, không thay ranking.
Không khởi chạy model mới sau 35s; dừng CV gần 44s, fit deadline 45s. Linux
worker dùng POSIX timer tối đa 15s/fit, vẫn giữ hard subprocess timeout 55s.
Trả partial leaderboard với SKIPPED_TIME_BUDGET / FAILED_SAFE. RF 60 cây,
depth 12, min_samples_leaf 2; Gradient Boosting 60 cây depth 2, seed 42.

## Chiến lược đánh giá adaptive

| Dữ liệu dùng được | Chiến lược mặc định |
| --- | --- |
| >=100 | Normal Holdout + CV: 75/25, tối đa 5 folds |
| 30–99 | Small Data: ưu tiên 75/25, tối đa 3 folds |
| 10–29 | Tiny Data Adaptive CV-only, tối đa 3 folds |
| <10 | CV-only nếu vẫn đủ mẫu, nếu không Exploratory Only |

Classification CV dùng StratifiedKFold, `folds <= min_class_count`. Holdout
chỉ được giữ khi mỗi lớp còn >=2 mẫu trong train và random test có đủ các lớp.
Nếu không khả thi, dùng CV-only trên full usable dataset với tối đa số folds
an toàn. Không dùng non-stratified folds có một lớp hoặc lớp validation chưa
xuất hiện trong train. Nếu class chỉ có một mẫu và không thể stratified CV,
chuyển Exploratory, không giả tạo đánh giá độc lập.

Regression dùng adaptive KFold (không LOOCV trên hàng nghìn mẫu); dưới 4 mẫu
chuyển Exploratory. Seed 42. Temporal giữ thứ tự thời gian, chia nhóm timestamp
để các dòng cùng timestamp không nằm hai phía CV/holdout. Bỏ CV fold chưa đủ
lớp train hoặc có lớp validation mới; dưới 2 fold hợp lệ chuyển Exploratory
và cảnh báo. Không tự đổi temporal thành random.

CV-only trả `test: null`, không held-out diagnostics/gap/overfit heuristic.
Leaderboard vẫn chọn bằng CV F1 Macro cao nhất / CV RMSE thấp nhất, tie dùng
CV std, CV fit time rồi tên. Normal/small giữ selection_source `train_cv`;
CV-only là `cv_only`. Không dùng test score để rank hoặc thay recommendation.

Exploratory chỉ fit và đo train-resubstitution: `cv_mean/std: null`, không
test, `recommended: null`, `best_exploratory_model` và selection_source
`exploratory_train`. UI ghi “Mô hình có kết quả tốt nhất trong thử nghiệm này”
và “Exploratory / không có đánh giá độc lập”. Không gọi train score là CV/test.

## Models, kết quả và độ bất định

Giữ 7 classification models và 8 regression models hiện tại; không grid search.
KNN tự giảm neighbors theo training fold nhỏ nhất. Mỗi model có SUCCESS,
SKIPPED hoặc FAILED_SAFE; một model lỗi không làm cả benchmark 500.
Diagnostics lỗi được báo partial, không thay CV ranking. Trên 4.000 mẫu vẫn
skip KNN/SVM theo giới hạn thời gian hiện tại, ghi lý do. Worker isolation,
55 giây timeout và CPU thread limit 1 được giữ. Không cache dữ liệu người dùng.

Holdout giữ các metric/biểu đồ classification/regression thật, null khi không
áp dụng. R² âm hoặc F1 thấp/gần majority baseline vẫn cảnh báo mạnh; không
đổi thứ hạng dựa test. Tiny/extreme tiny luôn có uncertainty warning. CV std
là biến động giữa folds, không phải confidence interval. Thời gian/model size
là measurement trên baseline, không đại diện toàn bộ chi phí production.

Hero/card đánh giá ghi mode, usable rows, số lớp và folds. Không có test thì
biểu đồ test/gap/radar báo không có dữ liệu độc lập. JSON/CSV report bao gồm
mode/selection source, để CV-only/Exploratory không bị hiểu là holdout.
CSV UTF-8 BOM/CRLF, quote, chống formula injection; metric thiếu là ô trống.

## Worker, logging và privacy

Worker env sao chép environment và truyền parent sys.path + existing PYTHONPATH
qua os.pathsep, giữ thứ tự/loại trùng. Không hardcode /tmp hoặc Python version.
Điều này bảo đảm worker thấy dependency path được Vercel inject lúc runtime.
Server log stage/algorithm và exception; client chỉ nhận sanitized response.
Không log raw CSV, user rows, toàn bộ environment hoặc PYTHONPATH.
Input worker qua stdin, không argv/file. Không lưu DB, Supabase, History,
localStorage/sessionStorage, không gửi serialized model về browser.

Các response no-store/nosniff. Tất cả text/cell/header/label frontend escape.
Result chứa target labels/feature names và mẫu diagnostic, vì vậy người dùng
vẫn cần tránh upload PII không cần thiết. Không hứa “mọi file đều chạy được”.
Không sửa các module khác; không commit/push/deploy production trong task này.
