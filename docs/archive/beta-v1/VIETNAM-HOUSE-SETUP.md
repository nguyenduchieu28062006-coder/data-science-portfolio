# Vietnam House Price — chạy và public v1

**Mode hiện tại: VERIFIED MARKET ESTIMATE BETA, beta-v1.** Gate ML 97% nên không train; chỉ dùng 290.282 căn hộ chung cư. MAE/RMSE/R²/MAPE không áp dụng. Xem `docs/verified-vietnam-house-data-report.md`.

Trang HTML, model JSON và static market stats chạy độc lập với Python/Supabase. Dùng HTTP server để preview; Vercel tự nhận `api/market-data.js` khi project root là thư mục này. Không cần environment secret cho prediction hoặc API static. Không deploy trong lượt hoàn thiện.

## Lịch sử cá nhân

Chạy toàn bộ `supabase/vietnam-house-price.sql` trong Supabase SQL Editor. SQL tạo `house_price_history`, RLS SELECT/INSERT/DELETE own, hai bảng market và RPC server-only. Không có quyền UPDATE lịch sử cho client. SQL thiết lập lại policy cùng tên, không xóa bản ghi lịch sử.

Giữ cấu hình public hiện có ở `supabase-config.js` (publishable/anon key), cấu hình Auth redirect URL theo `AUTH-SETUP.md` cho domain production khi có domain thật. Dự đoán không yêu cầu login. Lưu lịch sử yêu cầu login và bảng SQL; input chi tiết mặc định không lưu. Backend thật cần kiểm tra sau khi chủ project chạy SQL; các test local dùng mock.

## Dữ liệu và license

Nguồn public mới là tập con verified TiniX AI, CC BY-NC 4.0 theo publisher, dành cho portfolio phi thương mại. Đây là kiểm tra consistency giữa ý định bán, text giá tổng và structured price, không phải xác minh giao dịch hoàn tất hoặc quyền upstream độc lập. Ngày tin do publisher cung cấp, không phải chứng cứ realtime.

Andy v1 không được dùng cho public. Model/report/parity cũ được giữ tại `docs/archive/andy-v1/`; các báo cáo audit raw trước đây là lịch sử, không phải đánh giá subset verified mới.

`data/verified-vietnam-house-sales.parquet` chỉ dùng local; `.gitignore` và `.vercelignore` loại file này khỏi Git/bundle. `.vercelignore` cũng loại thư viện Python, docs, scripts, tests và SQL. Public chỉ cần model, metadata/aggregate JSON, HTML/CSS/JS và API tổng hợp. Không ship mô tả/raw listings lên frontend.

## Reproduce khi chủ động muốn tạo lại

Dependencies: `requirements-vietnam-house.txt`. Build script đọc đường cache từ manifest, kiểm tra output đã tồn tại để tránh chạy lại pass vô tình. Không tải hoặc scrape dữ liệu.

1. `python -B scripts/build-verified-vietnam-sales.py` — một pass raw local, chỉ khi chưa có canonical output.
2. Kiểm tra sample 200 seed 42, lưu kết quả gate thật. Không đánh dấu PASS chỉ vì parser chạy thành công.
3. `python -B scripts/build-vietnam-market-stats.py` — aggregate canonical.
4. `python -B scripts/train-verified-vietnam-house.py` — chỉ chạy khi gate PASS ≥98%; bounded training và JSON export.

Phiên hiện tại đi nhánh BETA bằng `scripts/build-vietnam-house-beta.py` sau bước review, rồi tạo market stats. Các output đã tồn tại; không cần chạy lại. Script training sẽ từ chối gate FAIL hiện tại.

Không chạy các bước này để preview website. Báo cáo kết quả tại `docs/verified-vietnam-house-data-report.md` và `docs/vietnam-house-public-status.md`.

## Adapter tương lai

`scripts/sources/batdongsan_source.py` có `fetch_listings()`; requires approved API/feed or explicit permission. Không crawl HTML/bulk scrape. `scripts/update-vietnam-market.py` exit 0 với “No approved live market source configured.” khi chưa có cấu hình.

Khi có feed được phép: normalize → validate → aggregate → static market JSON; Supabase upsert là tùy chọn nếu có server credentials. Các biến feed và service_role chỉ đặt trong môi trường server/CI, không trong frontend. Workflow hiện chỉ chuẩn bị chạy job; JSON được tạo trong CI chưa tự publish vào Vercel vì không có bước commit/deploy. Kết nối publish live sau này là công việc riêng.

## Kiểm thử

`python -B tests/test_vietnam_house_pipeline.py`, `python -B tests/test_vietnam_house_browser.py`, `python -B tests/run-vietnam-regressions.py`, `python -B tests/test_health_prediction.py`.

Các test browser dùng HTTP server local và SDK mock, không ghi Supabase thật. Nếu sandbox chặn GPU/browser, chạy ngoài sandbox theo quyền môi trường.
