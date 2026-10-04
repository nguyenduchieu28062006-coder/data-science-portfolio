# Verified Vietnam house data — 04/10/2026

Mode cuối: **VERIFIED MARKET ESTIMATE BETA**, chỉ căn hộ chung cư. Không train model.

| Chỉ số | Kết quả |
|---|---:|
| Raw rows — TiniX local, 10 shard | 3.500.744 |
| Candidate qua rule trước gate | 887.662 |
| Verified rows dùng BETA | 290.282 |
| Rejected / ngoài phạm vi BETA | 3.210.462 |
| Data range — timestamp publisher | 01/06/2025–30/03/2026 |
| Property type | Căn hộ chung cư |
| Tỉnh có dữ liệu / hỗ trợ estimate | 27 / 19 |
| Ninh Bình | 568 |
| Sơn La | 0 — không estimate |
| Quality gate ML — random 200, seed 42 | 194/200 = 97% — FAIL |
| Căn hộ trong cùng mẫu | 72/72 không thấy lỗi intent/total-price |

TiniX AI, `tinixai/vietnam-real-estates`, revision `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`, CC BY-NC 4.0 do publisher khai báo. Dùng portfolio phi thương mại. Không xác minh độc lập quyền upstream, tin gốc hoặc giao dịch.

Một pass raw bằng DuckDB streaming batches, không load toàn bộ raw vào RAM. Title bán rõ, loại primary offer thuê; giá tổng văn bản khớp structured ±5%; không dùng giá/m² hoặc thuê tháng làm tổng giá. Diện tích 15–1.500 m², tổng giá 0,2–100 tỷ, giá/m² 2–500 triệu. Dedup theo title/description/location/price/physical features, không theo ngày; listing_id là hash dẫn xuất, không tự nhận là ID nguồn.

Gate FAIL do 2 primary title false positives (“bàn cờ”, “buôn bán”) và 4 shorthand bị đọc thiếu phần lẻ (“9 tỷ 3”, “7 tỷ 1”, “7 tỷ 2”, “15 tỷ 7”). Không đổi gate thành PASS hoặc chạy training.

Fallback giới hạn canonical vào căn hộ chung cư; các lỗi đã thấy thuộc nhóm nhà. Quan sát 72 căn hộ trong mẫu gốc hỗ trợ BETA, **không phải gate mới 200 dòng**, không chứng minh population chính xác. “Verified” nghĩa là vượt qua rule consistency bán/giá, không phải xác minh thực địa. Median giảm ảnh hưởng sai số lẻ nhưng không đảm bảo định giá từng căn hộ.

Coverage HIGH ≥1.000, MEDIUM ≥200, LOW ≥30, INSUFFICIENT <30. Khu vực <30 mẫu dùng tỉnh cùng loại tài sản; tỉnh <80 mẫu không estimate. Dropdown chỉ hiện 19 tỉnh đủ mẫu. Static stats có 210 nhóm; P25/P75 là VNĐ/m².

Output local: `data/verified-vietnam-house-sales.parquet` (14.236.568 byte); public: artifact BETA và `data/vietnam-market-stats.json`. Candidate Parquet và Andy ở `docs/archive/`, không ship lên frontend. Ngày tin theo publisher, không đoán timezone, không tuyên bố realtime.

Evidence: `verified-vietnam-house-data-summary.json`, `verified-vietnam-house-quality-review.json`, sample local seed 42, manifest raw. Không quét lại hoặc train khi resume.
