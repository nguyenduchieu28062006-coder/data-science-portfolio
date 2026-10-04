# Audit nguồn: Vietnamese Real Estate Listings 2025 — qmanhbeo v3

Ngày thẩm định: **04/10/2026**. Quyết định: **C. REJECT cho nguồn chính của Vietnam House Price Prediction**.

Giá có bằng chứng mạnh nghiêng về triệu VNĐ, nhưng không có một representation đáng tin cho toàn cột. Đã thấy lỗi lệch 10–100 lần, trộn tổng giá với đơn giá, diện tích sai nghiêm trọng, tin thuê và tin chào cả hai. Quyền thu thập/tái sử dụng từ upstream chưa xác minh. Các điều kiện bắt buộc để approve chưa đạt.

Audit đọc toàn bộ nguồn; không sửa giá/diện tích, không bỏ bản ghi, không clean dataset, không tạo feature huấn luyện, không train hoặc tạo model, không sửa website. Các bảng dẫn xuất chỉ là bằng chứng thẩm định. TiniX không được sử dụng.

## 1. File, số bản ghi và khả năng truy vết

| Mục | Kết quả |
| --- | --- |
| Dataset/version | qmanhbeo/vietnamese-real-estate-listings-may-2024 / 3 |
| File | VN-real-estate-Apr-Sept-2025.csv |
| Số file | 1 |
| Bản ghi CSV thực tế, không gồm header | 236.226 |
| Số cột | 28 |
| Kích thước CSV đầy đủ | 220.057.487 bytes |
| SHA-256 | 5ad0a02a28eafdfe169307816bff908c2007e75860a595506d630569e7a812c1 |
| Bản ghi bị sửa/xóa | 0 / 0 |
| Hash nguồn trước và sau audit | Giống nhau |

[Dataset chính thức](https://www.kaggle.com/datasets/qmanhbeo/vietnamese-real-estate-listings-may-2024), [metadata API](https://www.kaggle.com/api/v1/datasets/view/qmanhbeo/vietnamese-real-estate-listings-may-2024). Metadata hiện hành vẫn là version 3, upload ngày **30/09/2025**. Ngày upload không phải ngày dữ liệu thị trường. Manifest lưu response, đường dẫn cache, URL download có khóa version và checksum trong [qmanhbeo-download-manifest.json](qmanhbeo-download-manifest.json).

Nguồn CSV đầy đủ lưu trong TEMP, ngoài repository. `source_record_1based` trong các bảng audit là thứ tự bản ghi CSV sau header, không phải số dòng vật lý; mô tả có thể chứa xuống dòng.

## 2. Schema đầy đủ và missing

CSV không có hệ thống kiểu dữ liệu native. Audit giữ nguyên chuỗi; 12 cột dưới đây parse được thành số tại các ô không missing. Missing là ô rỗng hoặc chuỗi `nan/null/none/n/a`, bỏ khoảng trắng và không phân biệt hoa thường. Không coi 0 là missing.

| Cột | Kiểu đọc/diễn giải trong audit | Missing | % |
| --- | --- | --- | --- |
| Title | Chuỗi/text/category | 0 | 0,000% |
| Price | Chuỗi → số (ID vẫn là định danh) | 0 | 0,000% |
| Area | Chuỗi → số (ID vẫn là định danh) | 296 | 0,125% |
| Location | Chuỗi/text/category | 0 | 0,000% |
| Listing ID | Chuỗi → số (ID vẫn là định danh) | 0 | 0,000% |
| Last Updated | Chuỗi/text/category | 0 | 0,000% |
| Property Type | Chuỗi/text/category | 0 | 0,000% |
| Width | Chuỗi → số (ID vẫn là định danh) | 62.082 | 26,281% |
| Length | Chuỗi → số (ID vẫn là định danh) | 137.461 | 58,190% |
| Bedrooms | Chuỗi → số (ID vẫn là định danh) | 170.337 | 72,108% |
| Bathrooms | Chuỗi → số (ID vẫn là định danh) | 198.062 | 83,844% |
| Floors | Chuỗi → số (ID vẫn là định danh) | 187.512 | 79,378% |
| Position | Chuỗi/text/category | 95.690 | 40,508% |
| Direction | Chuỗi/text/category | 164.444 | 69,613% |
| Alley Width | Chuỗi → số (ID vẫn là định danh) | 165.236 | 69,948% |
| Road Type | Chuỗi/text/category | 158.469 | 67,084% |
| Description | Chuỗi/text/category | 23.881 | 10,109% |
| Latitude | Chuỗi → số (ID vẫn là định danh) | 160.456 | 67,925% |
| Longitude | Chuỗi → số (ID vẫn là định danh) | 160.456 | 67,925% |
| VIP Account | Chuỗi/text/category | 0 | 0,000% |
| Avatar | Chuỗi/text/category | 0 | 0,000% |
| Agent Role | Chuỗi/text/category | 0 | 0,000% |
| Agent Name | Chuỗi/text/category | 100 | 0,042% |
| Agent Listing Count | Chuỗi → số (ID vẫn là định danh) | 0 | 0,000% |
| Province | Chuỗi/text/category | 0 | 0,000% |
| Property Type Slug | Chuỗi/text/category | 0 | 0,000% |
| Scraped At | Chuỗi → timestamp, không timezone | 0 | 0,000% |
| Last Updated Date | Chuỗi → timestamp, không timezone | 0 | 0,000% |

Feature thật có: loại tài sản, Area, Width, Length, Bedrooms, Bathrooms, Floors, Direction, Alley Width, Road Type, Position và location. **Không có cột `transaction_type`, URL nguồn, pháp lý riêng hoặc hướng ban công riêng.** Không đồng nhất `Width` với mặt tiền khi chưa xác minh nghĩa. Pháp lý hoặc hướng ban công xuất hiện trong text không đồng nghĩa đã có feature chuẩn hóa. Không trích feature ở bước này.

## 3. Duplicate, ID và kiểm chứng nguồn

| Kiểm tra | Số lượng |
| --- | --- |
| Duplicate toàn bộ 28 cột (bản ghi dư) | 0 |
| Listing ID khác nhau | 216.714 |
| ID có 2 bản ghi | 19.512 |
| Bản ghi nằm trong nhóm ID lặp | 39.024 |
| Bản ghi dư nếu xét cùng ID và nội dung chính, bỏ Province/thời gian/agent metadata | 19.508 |
| Nhóm ID có khác Price / Area / Property Type | 3 / 2 / 1 |

Nội dung chính dùng để kiểm tra trùng gồm ID, Title, Price, Area, Location, Property Type, Property Type Slug, Description. 19.511/19.512 nhóm ID lặp khác `Province`; mọi nhóm khác `Scraped At`. Có bằng chứng sao lặp cùng tin ở các nhóm tỉnh cũ/mới; nguyên nhân pipeline chưa có mã nguồn để kết luận. Không xóa các bản ghi trong audit. Đếm ID không chứng minh số bất động sản độc lập: cùng bất động sản vẫn có thể có nhiều ID.

Tất cả ID là số nguyên dương được serialize dạng `digits.0`, phạm vi **10.820–1.511.829**. Không có URL Guland hoặc bảng nối ID → URL. Không tự dựng URL từ ID và không xác nhận ID là khóa bất biến của Guland. Đối chiếu giá/diện tích/location/type với trang tin gốc: **UNRESOLVED**, thiếu URL gốc và quyền kiểm tra tự động chưa xác định. Chỉ đọc trang điều khoản công khai; không crawl tin đăng, không login hoặc bypass.

Bằng chứng ghép cặp: [qmanhbeo-duplicate-paired-evidence.csv](qmanhbeo-duplicate-paired-evidence.csv); toàn bộ thống kê ID/date: [qmanhbeo-supplemental-audit.json](qmanhbeo-supplemental-audit.json).

## 4. Date range thực và độ mới

| Cột timestamp | Min | Max | Missing | Invalid | Future |
| --- | --- | --- | --- | --- | --- |
| Last Updated Date | 2025-03-17T00:25:00 | 2025-09-14T00:05:00 | 0 | 0 | 0 |
| Scraped At | 2025-09-12T21:32:52 | 2025-09-14T00:46:10 | 0 | 0 | 0 |

| Cột | Tháng | Số bản ghi | % dataset |
| --- | --- | --- | --- |
| Scraped At | 2025-09 | 236.226 | 100,000% |
| Last Updated Date | 2025-03 | 6 | 0,002540% |
| Last Updated Date | 2025-04 | 12.154 | 5,145% |
| Last Updated Date | 2025-05 | 11.586 | 4,905% |
| Last Updated Date | 2025-06 | 12.713 | 5,382% |
| Last Updated Date | 2025-07 | 28.640 | 12,124% |
| Last Updated Date | 2025-08 | 77.224 | 32,691% |
| Last Updated Date | 2025-09 | 93.903 | 39,751% |

**236.226/236.226** timestamp `Last Updated Date` khớp trong 60 giây với `Scraped At` trừ thời gian tương đối `Last Updated` (tháng = 30 ngày; năm = 365 ngày). Sai lệch trung vị 30 giây phù hợp độ chính xác phút của cột. Đây là bằng chứng rất mạnh ngày đã được suy ra từ text tương đối; chưa xác minh ngày đăng/cập nhật tuyệt đối từ tin gốc. Không dùng nó như ngày giao dịch hoặc chuỗi lịch sử giá đã được xác nhận.

Future sau ngày upload version: 0; cập nhật sau lúc scrape: 0; timestamp không có timezone. Tên file “Apr–Sept” không đúng hoàn toàn: thực tế có **6 bản ghi tháng 03/2025**. Mốc lấy dữ liệu xác định được là **12–14/09/2025**, không phải 30/09/2025 và không phải 2026. Một tiêu đề nói bàn giao 04/2026 chỉ là lịch dự kiến, không biến snapshot thành dữ liệu 2026.

Nếu cần mô tả độ mới trong báo cáo sau này: **Dữ liệu được thu thập đến 14/09/2025; ngày cập nhật suy ra trong dataset: 17/03/2025–14/09/2025.** Tại 04/10/2026 dữ liệu đã hơn một năm tuổi, không phù hợp gọi là thị trường mới nhất/realtime.

## 5. Price representation: kiểm tra số lượng lớn

Parser audit xử lý số thập phân dấu chấm/phẩy, `2 tỷ 700 triệu`, `12 tỷ 500 triệu`, giá triệu và triệu/m²; hỗ trợ một số cách viết rút gọn. Có 13 kiểm tra parser/intent đã pass. Test fixture chỉ kiểm tra logic, không được thêm vào dataset.

Giá tham chiếu lấy độc lập với `Price`: ưu tiên title nếu có giá đọc được, nếu không mới dùng description; giá mâu thuẫn trong nhóm tham chiếu giữ không rõ. Loại khỏi tham chiếu các khoản thuê theo kỳ, vốn ban đầu, vay, đặt cọc, giảm giá và khoảng giá ẩn. Giá/sào, giá/công, giá/ha, giá/mét ngang được đánh dấu chưa hỗ trợ; không đoán diện tích một sào/công. Khi có cùng con số nhưng mâu thuẫn giữa tổng giá và giá/m², giữ không rõ.

Có **168.230** bản ghi có Price > 0 và một tham chiếu quy đổi tổng giá đọc được. Mẫu bắt buộc: **1.500 bản ghi**, lấy không hoàn lại từ nhóm này, seed 17042. Mẫu độc lập không điều kiện: 2.000 bản ghi, seed 42. Bản ghi lặp vẫn giữ nguyên trong mọi mẫu và thống kê.

### Mẫu 1.500 record có thể parse

| Interpretation | ±1% | ±2% | ±5% |
| --- | --- | --- | --- |
| Price × 1.000.000 (triệu VNĐ, tổng giá) | 1.190/1.500 (79,333%) | 1.210/1.500 (80,667%) | 1.244/1.500 (82,933%) |
| Price × 1.000.000.000 (tỷ VNĐ, tổng giá) | 1/1.500 (0,067%) | 1/1.500 (0,067%) | 1/1.500 (0,067%) |
| Price × 1 (VNĐ) | 0/1.500 (0,000%) | 0/1.500 (0,000%) | 0/1.500 (0,000%) |
| Price × 100.000 | 87/1.500 (5,800%) | 88/1.500 (5,867%) | 90/1.500 (6,000%) |
| Price × 10.000 | 49/1.500 (3,267%) | 50/1.500 (3,333%) | 54/1.500 (3,600%) |

### Toàn bộ nhóm có tham chiếu

| Interpretation | ±1% | ±2% | ±5% |
| --- | --- | --- | --- |
| Price × 1.000.000 (triệu VNĐ, tổng giá) | 133.358/168.230 (79,271%) | 134.830/168.230 (80,146%) | 138.030/168.230 (82,048%) |
| Price × 1.000.000.000 (tỷ VNĐ, tổng giá) | 55/168.230 (0,033%) | 55/168.230 (0,033%) | 56/168.230 (0,033%) |
| Price × 1 (VNĐ) | 0/168.230 (0,000%) | 0/168.230 (0,000%) | 0/168.230 (0,000%) |
| Price × 100.000 | 9.777/168.230 (5,812%) | 9.908/168.230 (5,890%) | 10.298/168.230 (6,121%) |
| Price × 10.000 | 5.370/168.230 (3,192%) | 5.514/168.230 (3,278%) | 5.712/168.230 (3,395%) |

### Mẫu không điều kiện

Trong 2.000 record, 1.457 có tham chiếu dùng được; các hàng còn lại **không tính là match**. Bảng sau dùng mẫu số 1.457, không phải 2.000.

| Interpretation | ±1% | ±2% | ±5% |
| --- | --- | --- | --- |
| Price × 1.000.000 (triệu VNĐ, tổng giá) | 1.151/1.457 (78,998%) | 1.164/1.457 (79,890%) | 1.182/1.457 (81,126%) |
| Price × 1.000.000.000 (tỷ VNĐ, tổng giá) | 0/1.457 (0,000%) | 0/1.457 (0,000%) | 0/1.457 (0,000%) |
| Price × 1 (VNĐ) | 0/1.457 (0,000%) | 0/1.457 (0,000%) | 0/1.457 (0,000%) |
| Price × 100.000 | 93/1.457 (6,383%) | 93/1.457 (6,383%) | 96/1.457 (6,589%) |
| Price × 10.000 | 48/1.457 (3,294%) | 50/1.457 (3,432%) | 51/1.457 (3,500%) |

Loại riêng các tham chiếu được nhận diện là gần đúng: ±1%: 130.675/157.699 (82,864%), ±2%: 131.817/157.699 (83,588%), ±5%: 133.604/157.699 (84,721%). Đây vẫn là kết quả parser, không phải nhãn giá chuẩn từ nguồn gốc.

**Kết luận:** triệu VNĐ là giả thuyết chủ đạo, trái mô tả metadata “billion VND”. Tỷ lệ khớp khoảng 80% chưa chứng minh toàn cột dùng thống nhất đơn vị triệu. Không thể đổi mọi hàng bằng một hệ số hoặc suy giá không khớp từ model.

Tỷ lệ không khớp không đồng nghĩa toàn bộ là lỗi dữ liệu: có quảng cáo “chỉ từ”, khoảng giá, nhiều căn trong một tin, text cũ, hoặc parser chưa hiểu ngữ cảnh. Audit không phải parser sản xuất; ưu tiên title có thể bỏ sót xung đột với description. Các kết quả sau là bằng chứng định lượng có giới hạn, không thay kiểm tra upstream.

30 mismatch chẩn đoán đã đọc theo mẫu parser v4; **16 trường hợp** có bằng chứng lệch gần 10/100 lần so với giá có đơn vị rõ, còn lại giữ lỗi parser/quảng cáo/không rõ. Ghi chép được khóa theo source record và ID, độc lập với mẫu v5 cuối. Không dùng 30 mẫu này để ước lượng tỷ lệ lỗi toàn dataset.

| Source record / ID | Price raw | Giá trong text | Đánh giá |
| --- | --- | --- | --- |
| 99.050 / 1343341 | 61.000 | 6,1 tỷ; kèm 112,97 triệu/m² × 54m² | Hệ số triệu cho 61 tỷ, lệch 10× |
| 8.753 / 1333135 | 172.000 | 1,72 tỷ | Hệ số triệu cho 172 tỷ, lệch 100× |
| 108.228 / 1387911 | 869.000 | 8,69 tỷ | Hệ số triệu cho 869 tỷ, lệch 100× |
| 150.046 / 1381926 | 13.531.000 | 35 triệu/m² × 3.866m² ≈ 135,31 tỷ | Lệch 100× dưới giả thuyết triệu |
| 118.326 / 1410338 | 1.200 | 30 triệu VND/m² × 40m² | Tổng 1,2 tỷ phù hợp; parser v4 từng hiểu sai đơn vị |

Nguyên nhân parser của publisher chưa xác minh vì thiếu mã thu thập/chuyển đổi. Không gọi mọi nhóm hệ số 10/100 là đơn vị thị trường hợp lệ. Xem [price audit 1500](qmanhbeo-text-price-audit-1500.csv), [sample 2000](qmanhbeo-text-price-unconditional-2000.csv), [ghi chép đọc mẫu](qmanhbeo-price-manual-diagnostic-review.csv).

## 6. Tổng giá hay giá/m²

Nhãn dưới đây dùng **giả thuyết triệu VNĐ và tolerance ±2%**; là nhãn bằng chứng audit, chưa phải ground truth. `TOTAL_PRICE` cũng bao gồm trường hợp text là giá/m² nhưng `Price` khớp rate × Area. Khi `Price` chỉ khớp rate, giữ `PRICE_PER_M2`. Giá không đọc được, sai khác, hoặc không xác định basis giữ `AMBIGUOUS`.

| Nhãn target audit | Bản ghi | % toàn dataset |
| --- | --- | --- |
| TOTAL_PRICE | 134.830 | 57,077% |
| AMBIGUOUS | 101.230 | 42,853% |
| PRICE_PER_M2 | 166 | 0,070% |

Trộn basis đã được xác nhận ở mẫu: source record **100.631**, ID **1293587**, `Price=62`, `Area=70`, mô tả giá bán **62 triệu/m²**; không phải tổng 62 triệu. Source record **23.511**, ID **1326422**, `Price=8` nhưng text là **8 triệu/m²**. Mặt khác nhiều bản ghi khớp tổng giá tỷ/triệu. Có giá/sào trong source record **30.003**, ID **1493810**, `Price=190`, `Area=5514,6`, mô tả **190 triệu/sào**, được giữ không rõ thay vì đoán diện tích một sào (mẫu AMBIGUOUS rank 65).

Không được kết luận chỉ 0,07% toàn bộ dữ liệu dùng price/m²: hàng không đọc được vẫn có thể chứa rate. Mẫu rate còn có dự án nhiều căn, giá “chỉ từ” và Area sai; ngay cả phép rate × Area đúng số học cũng chưa đảm bảo tổng giá một tài sản thật. **Target chưa đủ rõ để làm nguồn train chính.** Xem [bằng chứng rate](qmanhbeo-price-per-m2-evidence.csv).

## 7. Sale/rent và review 300 record

Rule yêu cầu lời chào thuê chính để gán RENT; không coi từ “thuê”, dòng tiền một tài sản đang cho thuê, hoặc trả góp/tháng là tin thuê. SALE đòi bằng chứng rao bán trong title; title/mô tả mở đầu có xung đột, mua/thuê cần tìm hoặc thiếu bằng chứng giữ không rõ. Đây là rule bảo thủ, có recall thấp; một số lời chào bán trong description vẫn nằm ở AMBIGUOUS.

| Nhãn giao dịch audit | Bản ghi | % toàn dataset |
| --- | --- | --- |
| SALE_HIGH_CONFIDENCE | 144.918 | 61,347% |
| AMBIGUOUS | 91.179 | 38,598% |
| RENT_HIGH_CONFIDENCE | 129 | 0,055% |

| Nhóm rule được review | Số đọc | Xác nhận SALE | Xác nhận RENT | Còn AMBIGUOUS |
| --- | --- | --- | --- | --- |
| SALE_HIGH_CONFIDENCE | 100 | 97 | 0 | 3 |
| RENT_HIGH_CONFIDENCE | 100 | 0 | 95 | 5 |
| AMBIGUOUS | 100 | 59 | 0 | 41 |

Review do **trợ lý đọc title, mở đầu mô tả và ngữ cảnh chào bán/thuê**, đọc toàn mô tả cho các SALE có tranh chấp rank 22/56/92. Không khẳng định đã đọc toàn bộ mọi mô tả dài; nội dung chưa đủ rõ giữ không xác nhận. Không có reviewer con người độc lập. Nhóm AMBIGUOUS là mẫu chẩn đoán được giữ từ strata phiên bản rule trước; không dùng suy ra tỷ lệ sale thực. Các mẫu đã hỗ trợ chỉnh rule, không phải holdout độc lập.

**SALE: 97/100 được xác nhận bán riêng; 3 còn mâu thuẫn/không rõ.** Đây là tỷ lệ xác nhận bảo thủ 97%, không phải ước lượng chắc chắn precision thật 97%. Chưa chứng minh đạt yêu cầu ≥98%. RENT: 95/100 được xác nhận thuê riêng; 5 trộn/chưa rõ. Toàn dataset **không sales-only**; 61,347% là tỷ lệ rule SALE, không phải tỷ lệ sale thật. Tỷ lệ RENT 0,055% là tỷ lệ phát hiện bằng rule hẹp, không phải chứng minh chỉ có 129 tin thuê.

Ví dụ source record 194.664 / ID 1201982: chào bán 5,8 tỷ và thuê 12 triệu có điều kiện cọc. Record 230.189 / ID 1325310: title bán căn hộ, description ghi “giá thuê” 3,9 tỷ; không tự sửa chữ. Record 168.544 / ID 1506756: thuê biệt thự 60 triệu/tháng, `Price=60` — xác nhận có thuê thực. Giá thuê có cả VNĐ và USD trong text của kho xưởng; không quy đổi USD và không dùng làm target bán.

[Mẫu giao dịch](qmanhbeo-transaction-audit-sample.csv), [ghi chép 300 record](qmanhbeo-transaction-manual-review.csv), [giới hạn review](qmanhbeo-manual-review-summary.json).

## 8. Coverage địa lý

`Province` có **63 nhãn tỉnh/thành cũ**. Gộp ở cấp tỉnh theo 23 nhóm sắp xếp và 11 đơn vị không sáp nhập cho ra **34 đơn vị hiện hành có ít nhất một bản ghi**. Chỉ gộp để đếm coverage; chưa mapping phường/xã hoặc tạo location feature. Tên gốc giữ nguyên; nhóm không xác định phải Unknown.

Nguồn đối chiếu nhóm cấp tỉnh: [toàn văn Nghị quyết 202/2025/QH15](https://m.mattran.org.vn/chuong-trinh-phoi-hop/toan-van-nghi-quyet-so-2022025qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-64083.html), [danh mục hành chính NSO](https://danhmuchanhchinh.nso.gov.vn/). File riêng [qmanhbeo-province-coverage-aliases.json](qmanhbeo-province-coverage-aliases.json) chỉ có ánh xạ cấp tỉnh phục vụ audit.

Thống kê này gồm toàn bộ bản ghi thô, kể cả thuê, target không rõ và duplicate. Các mức <100, 100–499, 500–1.999 và ≥2.000 chỉ giúp đọc mật độ mẫu, **không phải ngưỡng đủ train được kiểm định**. Không thể quảng cáo model hỗ trợ 34 tỉnh từ bảng này.

### Theo 34 đơn vị hiện hành

| Province | Sample count | % dataset | Coverage assessment |
| --- | --- | --- | --- |
| Hà Nội | 45.762 | 19,372% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Cao Bằng | 1 | 0,000423% | Chưa đủ mẫu |
| Tuyên Quang | 62 | 0,026% | Chưa đủ mẫu |
| Điện Biên | 1.673 | 0,708% | Có mẫu; cần kiểm định theo loại và phường |
| Lai Châu | 10 | 0,004233% | Chưa đủ mẫu |
| Sơn La | 78 | 0,033% | Chưa đủ mẫu |
| Lào Cai | 353 | 0,149% | Rất hạn chế |
| Thái Nguyên | 424 | 0,179% | Rất hạn chế |
| Lạng Sơn | 13 | 0,005503% | Chưa đủ mẫu |
| Quảng Ninh | 2.779 | 1,176% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Bắc Ninh | 2.292 | 0,970% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Phú Thọ | 2.569 | 1,088% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Hải Phòng | 4.480 | 1,896% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Hưng Yên | 2.300 | 0,974% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Ninh Bình | 1.641 | 0,695% | Có mẫu; cần kiểm định theo loại và phường |
| Thanh Hóa | 818 | 0,346% | Có mẫu; cần kiểm định theo loại và phường |
| Nghệ An | 280 | 0,119% | Rất hạn chế |
| Hà Tĩnh | 106 | 0,045% | Rất hạn chế |
| Quảng Trị | 423 | 0,179% | Rất hạn chế |
| Huế | 1.220 | 0,516% | Có mẫu; cần kiểm định theo loại và phường |
| Đà Nẵng | 11.242 | 4,759% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Quảng Ngãi | 463 | 0,196% | Rất hạn chế |
| Gia Lai | 894 | 0,378% | Có mẫu; cần kiểm định theo loại và phường |
| Khánh Hòa | 8.290 | 3,509% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Đắk Lắk | 6.458 | 2,734% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Lâm Đồng | 9.223 | 3,904% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Đồng Nai | 15.937 | 6,747% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Hồ Chí Minh | 97.808 | 41,404% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Tây Ninh | 10.316 | 4,367% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Đồng Tháp | 1.573 | 0,666% | Có mẫu; cần kiểm định theo loại và phường |
| Vĩnh Long | 1.766 | 0,748% | Có mẫu; cần kiểm định theo loại và phường |
| An Giang | 2.467 | 1,044% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Cần Thơ | 2.283 | 0,966% | Nhiều mẫu thô; chưa chứng minh model hỗ trợ |
| Cà Mau | 222 | 0,094% | Rất hạn chế |

Hà Nội gốc/hiện hành: **45.762**. TP.HCM gốc: **72.442**; TP.HCM sau gộp Bình Dương **19.566** và Bà Rịa–Vũng Tàu **5.800**: **97.808**. Hà Nội + TP.HCM hiện hành: **143.570 / 236.226 = 60,777%**. Chưa suy ra model ngoài hai thành phố lớn; Đà Nẵng, Đồng Nai, Tây Ninh, Lâm Đồng… có nhiều hàng thô nhưng cần xác minh từng nhóm sale/target/type và phường/xã.

Ninh Bình gốc **348**, sau gộp Hà Nam **685** và Nam Định **608**: **1.641**. Hà Giang gốc **19**, Tuyên Quang gốc **43**, nhóm hiện hành **62**. Cao Bằng **1**, Lai Châu **10**, Sơn La **78**, Điện Biên **1.673**: dữ liệu tỉnh nhỏ rất lệch, không đủ chứng minh khả năng dự đoán địa phương.

Đối chiếu thô token tỉnh cuối `Location` với nhóm `Province`: **60** bất đồng xác định và **3.048** không parse được. Đây là kiểm tra bảo thủ về tỉnh, không xác nhận chính xác phường/xã. Tên Location có cả dạng cũ và hậu tố `(Mới)`; không mặc nhiên tin mọi ánh xạ ward của upstream.

### Theo toàn bộ nhãn tỉnh/thành gốc

| Province gốc | Sample count | % dataset | Nhóm hiện hành cho audit |
| --- | --- | --- | --- |
| tp-ho-chi-minh | 72.442 | 30,666% | Hồ Chí Minh |
| ha-noi | 45.762 | 19,372% | Hà Nội |
| binh-duong | 19.566 | 8,283% | Hồ Chí Minh |
| dong-nai | 11.443 | 4,844% | Đồng Nai |
| da-nang | 9.898 | 4,190% | Đà Nẵng |
| khanh-hoa | 7.620 | 3,226% | Khánh Hòa |
| long-an | 6.991 | 2,959% | Tây Ninh |
| dak-lak | 6.101 | 2,583% | Đắk Lắk |
| lam-dong | 6.064 | 2,567% | Lâm Đồng |
| ba-ria-vung-tau | 5.800 | 2,455% | Hồ Chí Minh |
| binh-phuoc | 4.494 | 1,902% | Đồng Nai |
| hai-phong | 4.196 | 1,776% | Hải Phòng |
| tay-ninh | 3.325 | 1,408% | Tây Ninh |
| quang-ninh | 2.779 | 1,176% | Quảng Ninh |
| binh-thuan | 2.778 | 1,176% | Lâm Đồng |
| hung-yen | 2.051 | 0,868% | Hưng Yên |
| dien-bien | 1.673 | 0,708% | Điện Biên |
| bac-ninh | 1.570 | 0,665% | Bắc Ninh |
| can-tho | 1.494 | 0,632% | Cần Thơ |
| kien-giang | 1.392 | 0,589% | An Giang |
| quang-nam | 1.344 | 0,569% | Đà Nẵng |
| thua-thien-hue | 1.220 | 0,516% | Huế |
| vinh-long | 1.174 | 0,497% | Vĩnh Long |
| hoa-binh | 1.089 | 0,461% | Phú Thọ |
| an-giang | 1.075 | 0,455% | An Giang |
| tien-giang | 981 | 0,415% | Đồng Tháp |
| phu-tho | 871 | 0,369% | Phú Thọ |
| thanh-hoa | 818 | 0,346% | Thanh Hóa |
| bac-giang | 722 | 0,306% | Bắc Ninh |
| soc-trang | 697 | 0,295% | Cần Thơ |
| ha-nam | 685 | 0,290% | Ninh Bình |
| ninh-thuan | 670 | 0,284% | Khánh Hòa |
| vinh-phuc | 609 | 0,258% | Phú Thọ |
| nam-dinh | 608 | 0,257% | Ninh Bình |
| dong-thap | 592 | 0,251% | Đồng Tháp |
| gia-lai | 558 | 0,236% | Gia Lai |
| ben-tre | 493 | 0,209% | Vĩnh Long |
| thai-nguyen | 421 | 0,178% | Thái Nguyên |
| quang-ngai | 418 | 0,177% | Quảng Ngãi |
| dak-nong | 381 | 0,161% | Lâm Đồng |
| phu-yen | 357 | 0,151% | Đắk Lắk |
| ninh-binh | 348 | 0,147% | Ninh Bình |
| binh-dinh | 336 | 0,142% | Gia Lai |
| hai-duong | 284 | 0,120% | Hải Phòng |
| nghe-an | 280 | 0,119% | Nghệ An |
| thai-binh | 249 | 0,105% | Hưng Yên |
| quang-binh | 218 | 0,092% | Quảng Trị |
| lao-cai | 216 | 0,091% | Lào Cai |
| quang-tri | 205 | 0,087% | Quảng Trị |
| ca-mau | 149 | 0,063% | Cà Mau |
| yen-bai | 137 | 0,058% | Lào Cai |
| ha-tinh | 106 | 0,045% | Hà Tĩnh |
| tra-vinh | 99 | 0,042% | Vĩnh Long |
| hau-giang | 92 | 0,039% | Cần Thơ |
| son-la | 78 | 0,033% | Sơn La |
| bac-lieu | 73 | 0,031% | Cà Mau |
| kon-tum | 45 | 0,019% | Quảng Ngãi |
| tuyen-quang | 43 | 0,018% | Tuyên Quang |
| ha-giang | 19 | 0,008043% | Tuyên Quang |
| lang-son | 13 | 0,005503% | Lạng Sơn |
| lai-chau | 10 | 0,004233% | Lai Châu |
| bac-kan | 3 | 0,001270% | Thái Nguyên |
| cao-bang | 1 | 0,000423% | Cao Bằng |

Bảng có thể đọc máy: [63 nhãn gốc](qmanhbeo-province-original-coverage.csv), [34 nhóm hiện hành](qmanhbeo-province-current-coverage.csv), [mẫu bất đồng location](qmanhbeo-location-disagreements.csv).

## 9. Property types và khả năng train

Median bên dưới là **Price raw**, chưa thể gán một đơn vị VNĐ thống nhất; median Area là giá trị raw được hiểu m² theo tin, chưa validation toàn bộ. Median không loại 0, outlier, thuê hay duplicate; ô missing không tham gia median. Không gọi chúng là giá thị trường.

| Loại theo dataset | Bản ghi | Median Price raw | Median Area raw | Slug |
| --- | --- | --- | --- | --- |
| Căn hộ chung cư | 28.387 | 6.300 | 72 | can-ho-chung-cu |
| Kho, nhà xưởng | 4.884 | 24.000 | 2.000 | kho-nha-xuong |
| Khách sạn | 717 | 20.800 | 172 | khach-san |
| Nhà riêng | 72.821 | 9.980 | 81 | nha-mat-pho-mat-tien |
| Nhà trọ | 1.719 | 5.450 | 82 | phong-tro |
| Văn phòng | 400 | 48.500 | 144 | van-phong |
| Đất | 127.298 | 3.400 | 186 | dat-tho-cu |

| Loại | SALE rule | RENT rule | TOTAL evidence | RATE evidence | Target chưa rõ |
| --- | --- | --- | --- | --- | --- |
| Căn hộ chung cư | 13.416 | 6 | 10.359 | 50 | 17.978 |
| Kho, nhà xưởng | 3.216 | 85 | 2.677 | 16 | 2.191 |
| Khách sạn | 291 | 0 | 444 | 0 | 273 |
| Nhà riêng | 41.163 | 34 | 44.801 | 12 | 28.008 |
| Nhà trọ | 677 | 0 | 1.003 | 0 | 716 |
| Văn phòng | 71 | 1 | 247 | 0 | 153 |
| Đất | 86.084 | 3 | 75.299 | 88 | 51.911 |

Căn hộ chung cư, Nhà riêng và Đất có đủ hàng thô để thẩm định tiếp nếu nguồn/quyền được giải quyết; **chưa loại nào được approve train**. Kho/xưởng, văn phòng, khách sạn, nhà trọ có cấu trúc giá và quyền khai thác khác nhau, đồng thời có thuê/chuyển nhượng hoạt động; đề xuất không đưa vào model nhà ở chung ở trạng thái hiện tại.

**Nhà mặt phố và Biệt thự không phải category riêng của cột Property Type.** Toàn bộ category “Nhà riêng” lại có slug `nha-mat-pho-mat-tien`; không thể xác nhận nhãn đồng nhất hoặc tự tạo hai category mới. Có từ biệt thự trong title/description, kể cả tin thuê, nhưng chưa có nhãn đáng tin và chưa trích category.

## 10. Chất lượng và extreme outlier

| Chỉ tiêu | Price | Area |
| --- | --- | --- |
| Null/missing | 0 | 296 |
| Không parse được ở ô không missing | 0 | 0 |
| ≤ 0 | 611 | 4 |
| = 0 | 611 | 0 |
| Âm | 0 | 4 |

| Quantile | Price raw | Area raw | Price / Area raw |
| --- | --- | --- | --- |
| p1 | 180 | 30 | 0,1111 |
| p5 | 490 | 41 | 0,8155 |
| p25 | 2.250 | 73 | 10 |
| p50 | 6.000 | 115 | 44,4444 |
| p75 | 18.000 | 300 | 144,4444 |
| p95 | 179.000 | 4.100 | 1.401,7792 |
| p99 | 698.000 | 21.097,129 | 7.510,7843 |
| max | 9.223.372.036.850 | 1e+18 | 105.772.615.101,4908 |

Price/Area chỉ tính khi Area hữu hạn và >0; có **235.926** giá trị hữu hạn, **300** không xác định. Price=0 vẫn giữ. Đây là phân phối raw, **không phải phân phối triệu VNĐ/m² đã xác minh**. Không cắt outlier theo percentile.

Ví dụ extreme được phân biệt theo bằng chứng:

| Source record / ID | Quan sát | Đánh giá |
| --- | --- | --- |
| 48.466 / 1461435 | Price=9.223.372.036.850; mô tả giá 4 tỷ 2 | Xung đột số rõ ràng; nguyên nhân overflow/parser chỉ là giả thuyết |
| 155.706 / 1382656 | Area=10^18, title 10^19m²; mô tả 10 ha, 60 tỷ | Lỗi cấu trúc/đơn vị; 10ha=100.000m², không sửa nguồn |
| 171.707 / 1469729 | Area=75.900.001.525.879; title/mô tả 75,9m² | Sai giá trị Area rõ ràng |
| 215.386 / 1163163 | Area=1.578.861.169,7; mô tả 1.331m² | Area không phù hợp mô tả; title có thể đã lấy giá trị hỏng |
| 40.770 / 1230962 | Khách sạn 24 tầng, 212 phòng; text 1.500 tỷ | Giá rất lớn có mô tả quy mô hỗ trợ; không mặc nhiên xóa, Price raw vẫn lệch hệ số |
| 115.007 (mẫu SALE rank 3) | Area=752; title/mô tả 75,2m² | Sai diện tích khoảng 10×; giá/m² và phép tính tổng sẽ bị ảnh hưởng |
| 123.819 / 1504862 | Area=4.325; villa title 432m², tin thuê | Mâu thuẫn diện tích và loại giao dịch; chưa chọn số đúng |

4 bản ghi có cùng Price cực đại 9.223.372.036.850, trong đó có cả tin booking và tin giá thương lượng. Không coi đó là giá tài sản đã kiểm chứng. Cũng có Floors âm/max 919.168.799, Bedrooms max 20.224, Length max 210.963.269.466m, Alley Width max 357.201.974.105m; tọa độ vượt giới hạn địa lý hợp lệ. Việc “parse được số” hoặc Area > 0 chưa đủ validation. Không xác minh được Area hợp lý trên một cohort train.

Xem [các cực trị](qmanhbeo-extreme-examples.csv); [summary số học, missing và phân phối](qmanhbeo-source-audit-summary.json).

## 11. License và provenance

Kaggle metadata khai báo **CC BY-NC 4.0**, publisher Quang Manh Nguyen/qmanhbeo; card nói dữ liệu được scrape từ Guland cho giáo dục/nghiên cứu, quyền gốc thuộc nền tảng/chủ nội dung. Card có nói dữ liệu đã xử lý và engineered, nhưng không có mã thu thập/chuyển đổi, danh sách URL, bằng chứng quyền scrape hoặc giấy phép upstream. Chưa xác minh giá/diện tích nào là raw hay đã được biến đổi. Không thấy khai báo synthetic/proxy trong card; điều đó không chứng minh toàn bộ hàng được truy vết độc lập.

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) có điều kiện phi thương mại và ghi nguồn; nhãn do publisher chọn không chứng minh họ có quyền cấp phép mọi nội dung upstream. [Điều khoản Guland](https://guland.vn/dieu-khoan-thoa-thuan), mục 2.3 và 5, hạn chế thu thập và tái sử dụng trái phép; việc dùng dữ liệu cần nằm trong phạm vi được đồng ý hoặc pháp luật cho phép. Chưa có bằng chứng đáp ứng quyền đó cho dataset này.

Đây là điều khoản truy cập ngày 04/10/2026, không có bản lưu điều khoản tại lúc thu thập 09/2025. **Không kết luận publisher chắc chắn vi phạm pháp luật hoặc điều khoản năm 2025.** Kết luận audit là quyền upstream/redistribution **UNRESOLVED**; portfolio phi thương mại không tự giải quyết khoảng trống này. Không liên hệ publisher hoặc gửi thông tin ra ngoài.

Không dùng R² do card tự nêu làm bằng chứng: chưa biết split, leakage, units, baseline hoặc validation độc lập. Audit không train để tái lập con số đó.

## 12. Quyết định theo tiêu chí bắt buộc

| Tiêu chí để approve | Kết quả |
| --- | --- |
| Price representation xác minh | Chỉ xác định hệ số triệu là chủ đạo, không đáng tin cho toàn cột |
| Target chủ yếu total sale price rõ ràng | Có bằng chứng tổng giá, rate và nhiều không rõ; không có transaction_type |
| Tách sale/rent đáng tin, precision SALE ≥98% | Chưa chứng minh; mẫu SALE có 3/100 chưa xác nhận |
| Area hợp lý sau validation | Không đạt: nhiều sai số nghiêm trọng; chưa có cohort sạch đã xác minh |
| Provenance đủ cho portfolio phi thương mại | UNRESOLVED: nguồn tự khai, quyền upstream chưa xác định |
| Coverage biết rõ | Đã đếm 63 nhãn gốc/34 nhóm hiện hành; độ lệch lớn, còn ID trùng |

**C. REJECT. Không nên train qmanhbeo v3 cho House Price Prediction hiện tại.** Không có property type hoặc vùng nào được phê duyệt để train từ audit này. Có thể giữ hồ sơ thẩm định, nhưng việc cân nhắc lại cần giải quyết riêng quyền nguồn, đường dẫn tin và lỗi representation/Area; không tự tiến hành cleaning để “cứu” dữ liệu.

Không tạo model, metrics ML hoặc frontend prediction. Các module Data Analyzer, Health Prediction, Auth và History không sửa; không commit, push hoặc deploy. Dừng sau báo cáo.

## Hồ sơ và tái lập audit

- [Download manifest](qmanhbeo-download-manifest.json): file v3, metadata, size, hash.
- [Summary toàn file](qmanhbeo-source-audit-summary.json): 28 cột, missing, duplicates, dates, coverage, phân phối, đối chiếu Price.
- [Supplement](qmanhbeo-supplemental-audit.json): ID trùng nội dung, kiểm tra ngày tương đối.
- [Manual review](qmanhbeo-manual-review-summary.json): 300 record và giới hạn kết luận.
- Script download: `scripts/download-qmanhbeo-audit.py`; audit: `scripts/audit-qmanhbeo-source.py`; supplement: `scripts/supplement-qmanhbeo-audit.py`; parser: `scripts/qmanh_audit_rules.py`.
- Test logic audit: `python -B -m unittest discover -s tests -p test_qmanh_audit.py -v` (13 tests).
- `record-qmanhbeo-manual-review.py` chỉ lưu ghi chép đã đọc, không tạo nhãn train; price notes khóa theo source record/ID. Không thay thế một lần đọc mẫu độc lập.

Kết quả parser cuối: `qmanh-source-audit-v5`. Không tính kiểm thử rule là kiểm định thực địa. Nhãn giao dịch, target và ánh xạ tỉnh trong audit không được xuất làm feature/model dataset.
