# ML Model Comparison Lab

Module độc lập: `ml-model-comparison.html` gọi cùng origin `/api/ml-compare`.
Python 3.12 + scikit-learn 1.8.0 + pandas 2.3.3/openpyxl 3.1.5; không có kết quả ML giả lập ở frontend.

## Chạy và kiểm tra

```powershell
python -m pip install -r requirements.txt
python -B api/ml-compare.py --serve
# http://127.0.0.1:8000/ml-model-comparison.html
python -B tests/test_ml_model_comparison.py
# Chỉ backend:
python -B tests/test_ml_model_comparison.py --backend-only
```

Server local dùng cùng `handler` và worker huấn luyện với production. Nó chỉ giúp
QA; production dùng file-based Python Function của Vercel, không gọi localhost.
Thư mục `api` đã có CommonJS `market-data.js`; function mới không thay file đó.

## Kế hoạch Vercel

Framework preset hiện tại nên giữ `Other` cho portfolio static. Không thêm web
framework Python để tránh autodetection thay entrypoint toàn project. Vercel
tự nhận `api/ml-compare.py` (class `handler`, BaseHTTPRequestHandler), với dependency
trong `requirements.txt` root. `vercel.json` chỉ cấu hình function mới; không có
rewrite, route hay build command thay thế các trang và API cũ. Python mặc định
3.12; các pin hiện tại phục vụ runtime này. Không chuyển sang Python 3.14 với
numpy 1.26.4. Không dùng large-functions beta.

`excludeFiles` chỉ áp dụng function mới, bỏ data/model/static asset cũ khỏi bundle
Python. `.vercelignore` cũ vẫn giữ nguyên. scikit-learn mang theo dataset mẫu nhỏ.
Kiểm tra build Vercel thật trước khi tuyên bố READY: source/config compatibility
không chứng minh project settings, Linux wheel install và bundle triển khai.
Không commit, push hay deploy trong task này.

Tài liệu đã kiểm tra ngày 2026-10-07:

- [Python functions trong /api](https://vercel.com/docs/functions/runtimes/python/api-directory)
- [Runtime, dependency và bundle Python](https://vercel.com/docs/functions/runtimes/python)
- [Giới hạn Vercel Functions](https://vercel.com/docs/functions/limitations)

Request/response Vercel giới hạn 4.5 MB. Lab dùng tệp CSV/XLSX **2 MiB**, JSON **4 MiB**
(UTF-8 sau escape), tối đa **20.000 dòng / 100 cột**, một ô tối đa 4.096 ký tự,
tối đa 30 lớp classification. Đây là giới hạn cố ý thấp hơn đề xuất 10 MB.
Native dense output giới hạn 500 feature và 3 triệu ô ước tính, tránh OOM.
`maxDuration=60`; request benchmark chạy worker process bị kill sau 55 giây.
Trước mỗi model, nếu quá 35 giây thì skip; giữa các fold nếu quá 44 giây thì
skip model đang chạy. Native fit không bị hủy giữa hàm C, nhưng watchdog process
chặn toàn request, trả 504 thân thiện. Không hứa thời gian chạy chính xác.

## CSV, Excel và chất lượng

UTF-8, BOM, comma/semicolon/tab, quoted cells, header trim, header rỗng được đặt tên,
header trùng có suffix `__2`… Dòng trắng bị bỏ; exact duplicate row bị bỏ trước split
và số lượng được hiển thị. Dòng thiếu ô được pad missing; dư ô hoặc quote sai bị reject.
Missing tokens không phân biệt hoa thường: rỗng, NA, N/A, null, None, nan, `-`.
Preview tối đa 12 dòng; tổng dòng/cột/missing/numeric/category, ID/date/cardinality
và target candidates được hiển thị. Không tự chọn target.

XLSX gửi base64 trong JSON, kiểm tra ZIP/OOXML thực tế trước khi đọc bằng
`pandas.read_excel(engine="openpyxl")`. Không hỗ trợ .xls/.xlsm. Một sheet dùng
sheet đó; nhiều sheet mặc định sheet đầu và cho đổi bằng selector. Đổi sheet xóa
target/config/result cũ; inspect/benchmark luôn gửi đúng sheet đã chọn.

Mọi sheet (cả sheet chưa chọn) tối đa 20.000 dòng dữ liệu + header / 100 cột.
Archive thêm giới hạn 32 MiB sau giải nén / 512 mục; từ chối DTD/entity XML.
Kiểm tra tọa độ ô/dòng trước pandas, đọc tối đa 20.002 dòng để bảo vệ bước đọc.
Không giải nén ra filesystem. DataFrame chuẩn hóa qua cùng parser làm sạch CSV
(không áp giới hạn 2 MiB lên văn bản nội bộ), rồi cùng profile/prepare/benchmark.
Excel native date chuyển thành chuỗi ISO. Không thực thi công thức, chỉ đọc cached
value hoặc missing khi chưa có cache. Tệp/sheet lỗi trả 400/422; vượt limit trả 413.

Numeric parsing không tự đoán dấu thập phân hoặc hàng nghìn: hỗ trợ dạng số hữu hạn
với dấu chấm/exponent. Cột có ≥90% giá trị parse thành số là numeric; ô malformed
được báo và coi missing, không bịa giá trị. Các cột khác là categorical.
Phân loại phục vụ preview/gợi ý dùng dữ liệu upload; **kiểu feature thực sự trong
model được suy ra chỉ từ train**. Target missing/invalid numeric regression bị bỏ
và số lượng có trong báo cáo. Reject target toàn missing, một giá trị, ID/ngày,
regression không numeric, quá nhiều lớp hoặc không đủ usable rows.

ID nhận diện từ tên, UUID, chuỗi gần unique hoặc số nguyên monotonic gần unique;
không coi số liên tục unique bất kỳ là ID. ID/cardinality cao mặc định bỏ chọn,
có thể override. High-cardinality OHE học nhóm hiếm trên mỗi train fold,
`min_frequency=2,max_categories=32,handle_unknown='ignore'`.

Target string/category gợi ý classification; numeric ít unique xét cả số lớp,
ratio và số mẫu; numeric liên tục gợi ý regression. Người dùng phải chọn radio
để xác nhận và luôn có thể đổi. Heuristic không thay kiến thức nghiệp vụ.

Potential leakage: exact target copy bị chặn; mapping category → target deterministic,
tương quan |r|≥.995 và tên gợi ý dữ liệu sau outcome được cảnh báo, cần xác nhận.
Tên cột không chứng minh leakage. Người dùng phải kiểm tra feature có tồn tại ở
thời điểm dự đoán không. Không thể tự phát hiện mọi leakage hay repeated entity;
group-aware split chưa hỗ trợ. Tránh benchmark khi nhiều dòng cùng entity cần
group split để phản ánh triển khai thật.

## Split, preprocessing và CV

Random split: 75/25, seed 42; classification stratify. Nếu không khả thi, reject
thay vì cho benchmark gây hiểu nhầm. Classification train dùng StratifiedKFold,
regression KFold, shuffle/seed 42. Mặc định 5 folds; dưới 100 dòng dùng 3;
class ít mẫu giảm fold tới tối thiểu 2 hoặc reject.

Ngày ISO `YYYY-MM-DD`/ISO datetime và chuỗi ngày phổ biến dùng dấu / hoặc - được
nhận diện; không one-hot raw date. Ngày year-first hoặc day/month không mơ hồ
(một phần >12) được parse. Day/month mơ hồ phải chuyển ISO trước extraction/temporal.
Người dùng chọn bỏ ngày hoặc year/month/day/day_of_week. Mặc định bỏ ngày và có
warning khi random split. Temporal yêu cầu cột ngày đầy đủ, sort theo UTC timestamp,
75% cũ train / 25% mới test, không shuffle/stratify; boundary được dịch khi có
timestamp bằng nhau để cùng timestamp không xuất hiện cả hai phía.
TimeSeriesSplit chỉ chạy trên train. Reject khi training fold có một lớp hoặc
validation/test có lớp chưa xuất hiện trong train. Không hỗ trợ rolling forecast,
gap/embargo hoặc chuỗi phân nhóm. Ngày numeric epoch không tự coi là datetime.

Split trước, fit sklearn Pipeline/ColumnTransformer trong từng CV training fold,
không fit imputer/scaler/OHE vào test hay validation. Numeric median, categorical
most_frequent, OHE dense bị giới hạn tài nguyên. Linear/KNN/SVM có StandardScaler;
tree và GaussianNB không cần scaling. `keep_empty_features=True` giữ schema nếu
cột toàn thiếu trong một fold; cột toàn thiếu trong full train bị reject rõ ràng.
Không resample test. Models hỗ trợ dùng class_weight=balanced cho classification.

## Models và lựa chọn

Classification: Logistic Regression, KNN, SVC RBF, Decision Tree, Random Forest,
Gaussian Naive Bayes, Gradient Boosting. Regression: Linear, Ridge, Lasso, KNN,
SVR RBF, Decision Tree, Random Forest, Gradient Boosting. Forest 60 cây, độ sâu 12;
boosting 60 cây sâu 2. Hyperparameters được trả trong detail/report. Không grid search.
Dataset >4.000 dòng skip KNN/SVM với lý do. Dưới 50 dòng chỉ chạy 3 baseline/task,
cảnh báo thăm dò; dưới 20 dòng reject. GaussianNB dùng dense matrix đã được giới hạn,
không nhận sparse không tương thích. Models lỗi/bị skip được báo riêng.

Classification rank theo **CV F1 Macro cao**, regression **CV RMSE thấp**;
tie chính xác dùng CV std thấp, CV fit time thấp, cuối cùng tên để ổn định.
Không dùng test AUC, test MAE hay test generalization gap làm tie-break: giữ lựa chọn
độc lập test quan trọng hơn mọi cân nhắc hậu kiểm. CV mean/std (population std)
và fold scores được trả. Std là biến động fold, không phải confidence interval.
Recommended bị đóng băng trước khi tính test metrics cho mọi model trên cùng test.

## Metrics, biểu đồ và giải thích

Classification: accuracy, macro precision/recall/F1, weighted F1, confusion matrix,
per-class report. Binary score dùng predict_proba hoặc decision_function;
positive class là `classes_[1]`, hiển thị rõ. ROC-AUC, ROC/PR curve tính thật.
PR-AUC là trapezoidal area under PR curve, không phải average precision.
Log loss chỉ có khi có probability. Multiclass ROC-AUC OVR macro chỉ tính khi
predict_proba khả dụng và test đủ các lớp; không vẽ binary curve cho multiclass.
Không áp dụng hoặc không tính được: null/N/A, không số giả.

Regression: MAE/MSE/RMSE/R²; MAPE chỉ khi mọi |target test|>1e-8, không dùng để rank.
Predicted vs Actual có y=x; residual=actual−predicted, reference y=0.
Plot tối đa 250 test samples; metric/residual summary tính trên toàn test.
CV, train vs test, grouped metric bars, radar thang 0–1 (không min-max normalize),
model vs model đều lấy kết quả backend. Radar tối đa 3 model, bỏ AUC axis nếu
có model được chọn thiếu AUC. Feature importance tree hoặc mean absolute linear
coefficient với transformed feature names OHE; global, không phải local/causal.
Hệ số của các feature không cùng đơn vị không thể so sánh như causal effect.

Overfit heuristic: gap=train F1−test F1 hoặc train R²−test R². Low ≤.05,
Medium >.05 tới .15, High >.15; không chứng minh model overfit. Fit/predict dùng
perf_counter; fit time là full train final fit, CV fit time riêng. Model size là
pickle bytes trong memory, không phải serving RAM; không trả serialized model.
Report JSON chứa bảng, cấu hình, metric và chart samples, không chứa full CSV.

## Chất lượng tuyệt đối và báo cáo

Recommendation chỉ có nghĩa tốt nhất trong các model đã benchmark theo train CV.
Sau khi chốt model: regression Test R² < 0 cảnh báo mạnh “Chất lượng mô hình thấp”;
0 ≤ R² < 0,1 cảnh báo nhẹ. Classification Test F1 Macro < 0,4 hoặc không vượt
baseline + 0,05 cảnh báo mạnh. Baseline dự đoán lớp phổ biến nhất của train,
đánh giá macro F1 trên test; chỉ để cảnh báo, không ranking/tuning.
Đây là heuristic đơn giản, không bảo đảm chất lượng triển khai.

Preview dưới 100 dòng cảnh báo mẫu nhỏ, dưới 50 cảnh báo mạnh. Backend kiểm tra
lại số usable rows sau loại target missing/invalid và ghi warning trong report.
Giữ 3-fold dưới 100, baseline-only dưới 50 và reject dưới 20 dòng.
Không đổi recommendation vì Test R² âm hoặc Test F1 thấp.

Giữ JSON; thêm CSV leaderboard đầy đủ CV/test/train metrics, fit/predict ms,
model size bytes, overfit risk và Recommended. CSV UTF-8 BOM, CRLF, quote/escape;
null là ô trống. Text bắt đầu =/+/-/@ sau whitespace được prefix apostrophe
chống formula injection; số âm giữ numeric. Không có raw rows trong CSV report.
Report chỉ tải về máy khi người dùng bấm nút, không ghi DB/History.

## Privacy và an toàn

CSV hoặc Excel gửi tới backend. Không filesystem, Supabase, DB, analytics, raw request logging
hay cache. Worker nhận payload qua stdin, không argv/file; stderr bỏ, trả lỗi đã lọc,
không raw traceback. Không job lưu dài hạn. CPU thread giới hạn 1 để giảm tài nguyên.
JSON response no-store/nosniff. Frontend không localStorage/sessionStorage, render
text/cell/header/label đều escape để chống HTML injection. JSON download theo
hành động user chứa kết quả trên thiết bị của họ. Metrics/curves/label/feature name
cũng có thể tiết lộ thông tin; không tải PII không cần thiết.

Endpoint public không có Supabase history/auth mới. Hosting firewall/rate-limit là
phần vận hành Vercel, không khẳng định đã cấu hình từ source. Mỗi request được giới
hạn nhưng traffic đồng thời vẫn cần quản lý theo quota của hosting.

## Kết quả kiểm thử và trạng thái chấp nhận

**ML MODEL COMPARISON FINALIZATION: NOT READY** cho production vì Vercel
build/dev còn BLOCKED; chức năng local đã hoàn thiện. Cập nhật 2026-10-07.
Không commit, push, deploy hoặc đổi project link.

- Backend/HTTP: 27 tests PASS. CV-only selection, train/fold preprocessing,
  7 classification / 8 regression models, 5 demos, Content-Type contract,
  XLSX numeric/mixed/missing/native date/cleaning, multi-sheet/selected sheet,
  malformed files/limits, small-data và model-quality warnings.
- Browser HTTP thật: 74 checks/viewport PASS ở 320, 390, 768, 1024, 1440.
  CSV/XLSX classification/regression, sheet selector, target/manual task/features,
  dates/random/temporal, charts/detail/versus, JSON/CSV/BOM/formula protection,
  Test R² âm. Không mock ML results; mock riêng 413 để kiểm tra error UI.
- Không global overflow; table scroll nội bộ. Live resize 1440 → 320 giữ model
  selections và vẽ lại charts. Console errors: NONE.
- Entry point handler(BaseHTTPRequestHandler) và same-origin /api/ml-compare:
  source contract/local HTTP PASS, không chứng minh deployment PASS.
- Vercel CLI 62.7.0: build BLOCKED `project_settings_required`:
  “No project settings found locally.” Không pull/--yes để đổi project link.
- Vercel dev BLOCKED: “No existing credentials found. Starting login flow...”;
  tiến trình chờ xác thực đã dừng, không đăng nhập.
- Linux CPython 3.12 dependency wheels/transitives ở OS temp: tổng uncompressed
  entries khoảng 243,86 MiB, dưới Python limit 500 MB theo tài liệu Vercel.
  Đây là ước tính dependency size, không phải bundle build thật.
- CV-selection test có thể flake vì NB/SVM bằng CV mean/std, timing tie-break thay
  đổi giữa runs. Test dùng hai estimator thật có CV khác nhau và ép model thua
  CV thắng test. Recommendation vẫn theo CV; production methodology không đổi.
- Protected files Analyzer/Health/Customer Return/Real Estate/Auth/History/
  Supabase/SQL không sửa. Health mobile failure giữ PRE-EXISTING / STALE BASELINE
  theo xác minh trước; không sửa/run lại Health để ép task xanh.
  Outputs 34,2% / 99,6% là bằng chứng lượt trước.

Artifacts/screenshots: OS temp ml-model-comparison-qa; không thêm fixtures lớn.
Source đã có trước lượt này vẫn untracked. index.html giữ nguyên diff card/link
ML từ lượt trước. Lượt này chỉnh API, HTML/CSS/JS module, requirements, tests và
documentation; không tạo file source mới. git diff --check: PASS.

Blocker còn lại: Vercel project settings/credentials để xác minh build/dev và
bundle production. Không sửa bằng hardcode localhost hoặc local-only entrypoint.
