# HOUSE PUBLIC STATUS: READY

Ngày hoàn thiện: 04/10/2026 (Asia/Saigon). **Mode: VERIFIED MARKET ESTIMATE BETA — beta-v1**, chỉ căn hộ chung cư. ML chưa READY; không train và không dùng Andy public.

| Yêu cầu | Trạng thái |
|---|---|
| Raw rows | 3.500.744 TiniX local, một pass |
| Verified rows | 290.282 canonical căn hộ |
| Quality gate | ML: 194/200 = 97%, FAIL; BETA fallback. 72/72 căn hộ trong mẫu gốc không thấy lỗi, không phải gate mới hoặc bảo đảm population |
| Property types | Căn hộ chung cư |
| Provinces supported | 19 (27 có record, tỉnh dưới 80 mẫu bị chặn) |
| Ninh Bình / Sơn La | 568 / 0 |
| Model name | Không có model ML; median giá/m² × diện tích |
| MAE / RMSE / R² / MAPE | Không áp dụng; UI ẩn dashboard ML, không tạo metrics/scatter/contribution giả |
| Data dates | 01/06/2025–30/03/2026, timestamp publisher chưa xác minh độc lập |
| Coverage | HIGH ≥1.000; MEDIUM ≥200; LOW ≥30; area <30 fallback cùng tỉnh/loại, province <80 không estimate |
| Market API | `/api/market-data`: static verified aggregates, 210 nhóm, no-data an toàn; live feed chưa kết nối |
| History | Code insert/load/delete/clear có owner filters và opt-in inputs; browser SDK mock pass, backend thật cần SQL |
| Secrets trước public | Không cần cho estimate/API static. Auth dùng public config hiện có; service_role chỉ server/CI tùy chọn cho feed tương lai |
| Supabase SQL | `supabase/vietnam-house-price.sql`; chủ project chạy SQL Editor. Chưa chạy trên dịch vụ thật |
| House browser | 57 checks × 320/390/768/1440, gồm clear toàn bộ history và API missing-data; 250 Python/JS fixtures, sai lệch 0 |
| Pipeline | 7 tests pass |
| Regression | Auth 168 checks/viewport; History 15/viewport; Health 57/59 checks theo viewport, đều pass; Analyzer content so với HEAD giữ nguyên |
| Public bundle | BETA artifact 31.472 byte, static stats 79.495 byte; raw/canonical Parquet, archive, Python deps/docs/scripts/tests/SQL bị loại bằng `.vercelignore` |
| Publish action | Không commit, push hoặc deploy; dừng để người dùng kiểm tra |

Kiểm tra cuối: 68 relative asset/link của 7 public pages hợp lệ; metadata median/count khớp static aggregates; House runtime không có server secret hoặc URL localhost. `git diff --check` pass. Harness iframe được sửa để chờ script khởi tạo trước khi đọc trang; sau sửa cả 4 viewport pass.

## File mới trong fast-track

- `data/verified-vietnam-house-sales.parquet` (local, Git/bundle ignore), `data/vietnam-market-stats.json`.
- `scripts/verified_sale_rules.py`, `scripts/build-verified-vietnam-sales.py`, `scripts/build-vietnam-house-beta.py`, `scripts/build-vietnam-market-stats.py`.
- `scripts/train-verified-vietnam-house.py` chỉ chuẩn bị, **chưa chạy**, gate FAIL ngăn training.
- `docs/verified-vietnam-house-data-summary.json`, `docs/verified-vietnam-house-quality-review.json`, sample local, `docs/verified-vietnam-house-data-report.md`, báo cáo này.
- `docs/archive/andy-v1/`, candidate Parquet archive local; `.gitignore`, `.vercelignore`, `VIETNAM-HOUSE-SETUP.md`.

## File sửa từ recovery

- Trang/inference/save: `vietnam-house-price.html`, `vietnam-house-price.js`, `vietnam-house-inference.js`, `vietnam-house-history-save.js`.
- Artifact/parity: `vietnam-house-model.json`, `data/vietnam-house-parity-fixtures.json`; training/cleaning reports.
- `history.js`, `index.html`, `api/market-data.js`, `supabase/vietnam-house-price.sql`, `requirements-vietnam-house.txt`.
- Adapter/update scripts, test House browser/pipeline, current source notice và các report lịch sử để phân biệt scope Andy/raw với BETA.
- CSS dashboard, auth.js và history.html đã có từ recovery. `data-analyzer.html` chỉ khác newline cuối file trước recovery; không đổi logic Health/Analyzer.

Thiết lập/giới hạn: [hướng dẫn](../VIETNAM-HOUSE-SETUP.md), [dữ liệu](verified-vietnam-house-data-report.md). READY cho portfolio phi thương mại và estimate thống kê; không tuyên bố giá giao dịch, realtime hoặc định giá chuyên nghiệp.
