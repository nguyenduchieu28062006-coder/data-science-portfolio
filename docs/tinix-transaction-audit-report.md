**Thẩm định TiniX Vietnam Real Estate Listings — 04/10/2026**

Phạm vi lịch sử: raw TiniX và quyết định không train nguyên bộ. BETA mới dùng median thống kê của subset căn hộ, không phải model ML; xem [báo cáo subset](verified-vietnam-house-data-report.md). Không thay đổi bằng chứng hoặc kết luận audit raw bên dưới.

**Kết luận duy nhất: C. REJECT.** Chưa đề xuất train giá bán bằng tập SALE do bộ quy tắc hiện tại tạo ra. Ý định bán trong mẫu khá tốt, nhưng nhãn RENT sai nghiêm trọng, target chưa được xác minh đủ tin cậy và nguồn thu thập/quyền phát hành từ website gốc vẫn unresolved. Kết luận áp dụng cho dataset và quy trình tại revision được kiểm tra; không có nghĩa mọi tin của TiniX đều sai hoặc không thể xây dựng một tập hợp đạt yêu cầu sau một vòng thẩm định khác.

Đã quét **3.500.744 dòng / 10 Parquet gốc**, revision `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`. SHA256 và kích thước cả 10 file khớp manifest trước và sau audit. Không train, không sửa/xóa bản ghi gốc, không tạo dataset sạch, không mapping địa danh, không sửa website, không commit/push/deploy. Dữ liệu và DuckDB dùng để kiểm tra nằm trong TEMP, ngoài project. Chỉ scripts, CSV mẫu và báo cáo được lưu trong project.

**1–3. Nhãn và tỷ lệ trên toàn bộ dữ liệu**

| Nhãn do rule v1 gán | Dòng | Tỷ lệ full scan | Mẫu review |
| --- | ---: | ---: | ---: |
| SALE_HIGH_CONFIDENCE | 1.747.762 | 49,9254% | 100 |
| RENT_HIGH_CONFIDENCE | 31.052 | 0,8870% | 100 |
| AMBIGUOUS | 1.721.930 | 49,1875% | 100 |

Đây là số lượng **nhãn rule**, chưa phải số tin bán/thuê được xác thực. Mẫu phân tầng có 100 dòng mỗi nhãn nên tỷ lệ trong CSV đều 33,33%; không dùng tỷ lệ mẫu này làm tỷ lệ thị trường.

Rule `title-intent-v1` bỏ dấu/chuyển chữ thường để nhận diện ý định; giữ nguyên title/description gốc. Dấu hiệu bán phải có cụm rõ như cần bán/chính chủ bán/bán nhà/bán căn hộ/bán đất/chuyển nhượng/giá bán. Cho thuê hoặc biểu thức theo tháng chỉ thành RENT khi không có dấu hiệu dòng tiền trong title hay đề nghị bán ở đầu description. Hai đề nghị hoặc xung đột thành AMBIGUOUS. Không dùng mức giá, tỉnh hoặc category để quyết định ý định. Không dùng quy tắc “description có thuê thì RENT”. Description chỉ được xét 240 ký tự đầu cho dấu hiệu đề nghị đối lập; đây là một hạn chế đáng kể.

Rule giữ được 47.185 tin SALE có ngữ cảnh dòng tiền trong title. Tuy nhiên kiểm tra thủ công phát hiện các biến thể `CCMN`, `CHDV`, `HĐT`, “bán căn…”, “bán 60m²…” và khoản trả góp chưa được xử lý đầy đủ. RENT v1 không đạt độ tin cậy để sử dụng. Quy tắc được giữ nguyên sau review; không tinh chỉnh trên mẫu rồi báo precision cải thiện.

Mẫu lấy bằng xếp hạng hash giả ngẫu nhiên `md5(42|source_shard|source_row)`, lấy 100 dòng đầu mỗi nhãn. `source_row` bắt đầu từ 0 trong Parquet gốc. Mẫu giá dùng prefix `price-42`, 1.000 dòng SALE, được lấy riêng với mẫu ý định; không bảo đảm hai mẫu không giao nhau. Cách lấy mẫu không xét title/price để chọn những tin đẹp.

[CSV 300 dòng](tinix-transaction-audit-sample.csv) có đủ 9 cột được yêu cầu, thêm shard/dòng để truy vết. Description trong CSV cắt ở 900 ký tự; review đã đọc **title và full description** trong cache. `price` trong CSV giữ nguyên chuỗi ở Parquet, không thay bằng giá đọc từ text.

**4. Precision ước tính của SALE**

| Nhãn rule trong mẫu | Review: bán | Review: thuê | Review: chưa chắc |
| --- | ---: | ---: | ---: |
| SALE_HIGH_CONFIDENCE | 99 | 0 | 1 |
| RENT_HIGH_CONFIDENCE | 96 | 0 | 4 |
| AMBIGUOUS | 93 | 0 | 7 |

SALE có **precision ước tính 99/100 = 99% về ý định trong text**. Một tin tổng quan Alluvia City có từ “giá bán” nhưng chưa xác định đề nghị bán một tài sản được tính là chưa chắc, không tính true positive. Một số tin bán còn là giỏ hàng nhiều căn, nhà đang khai thác phòng thuê, khách sạn hoặc chuyển nhượng tài sản kinh doanh; nhãn ý định không đủ bảo đảm một dòng là một căn nhà dân dụng với giá tổng chuẩn.

Điểm ước tính vượt mục tiêu 98%, nhưng Wilson 95% là **94,55%–99,82%**. Không thể khẳng định precision toàn bộ ≥98% từ 100 dòng. Review do trợ lý đọc nội dung thực hiện, **không phải bộ ground truth do người độc lập gán nhãn**, không xác minh giao dịch thực, giá chốt hay tính xác thực ngoài website. Không ước tính recall từ mẫu phân tầng này. Không đánh đồng precision ý định với precision target giá bán.

Trong mẫu RENT, **0/100 xác nhận được đề nghị thuê chính**; phần lớn là bán tài sản có doanh thu thuê hoặc trả góp. Ví dụ `Bán CCMN … 90tr/tháng`: description nói doanh thu và sổ đỏ, vẫn bị rule v1 gán RENT. Kết quả này không chứng minh cả dataset không có tin thuê; nó chứng minh nhãn RENT hiện tại thất bại. AMBIGUOUS bỏ sót nhiều tin bán, phù hợp hướng ưu tiên precision hơn recall nhưng chưa phải classifier ba nhãn đủ tin cậy.

Chi tiết: [review 300 dòng](tinix-transaction-manual-review.csv), [summary và khoảng Wilson](tinix-manual-review-summary.json). **Trạng thái sẵn sàng train: FAIL**, dù điểm ước tính SALE intent đạt 99%.

**5. Giá, diện tích và đối chiếu với text**

Parquet gốc có `price: VARCHAR`, trong khi schema/viewer mô tả `float64`. Audit chỉ `try_cast` sang DOUBLE trong view tính thống kê, không sửa chuỗi gốc. Không có giá khác NULL bị lỗi chuyển số; điều đó chỉ xác nhận cú pháp số, không xác nhận đơn vị hay giá trị đúng.

Phân phối dưới đây dùng toàn bộ SALE v1, không loại outlier và **vẫn gồm giá 0**. NULL/nonfinite không tham gia quantile; số lượng được báo riêng. `price_per_m2 = price / area` là phép chia số liệu, chưa chứng minh price luôn là giá tổng hoặc area luôn đúng đơn vị. p50 và median cùng một giá trị.

| Chỉ số | min | p1 | p5 | p25 | p50 / median | p75 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| price, tỷ VNĐ | 0 | 0 | 1,2 | 4 | 7,2 | 14 | 48 | 137 | 26.597.191 |
| area, m² | 1,141 | 25 | 35 | 57,4 | 80 | 120 | 419 | 2.600 | 66.879.000 |
| price/area, triệu VNĐ/m² | 0 | 0 | 6,226 | 49,138 | 92,222 | 181,707 | 366 | 603,112 | 27.045.454,545 |

Giá và giá/m² có 1.642.753 giá trị hữu hạn, 105.009 NULL; diện tích có 1.747.759 giá trị hữu hạn, 3 thiếu. Số liệu được làm tròn chỉ trong bảng này; CSV lưu kết quả số đầy đủ.

| Category đúng nguyên văn trong dataset | Dòng SALE | Median price, tỷ VNĐ | Median area, m² | Median price/area, triệu VNĐ/m² |
| --- | ---: | ---: | ---: | ---: |
| Nhà | 767.680 | 8,8 | 63 | 162 |
| Đất | 469.193 | 4,7055 | 112 | 38,636 |
| Căn hộ chung cư | 372.162 | 5 | 75 | 68,5 |
| Biệt thự/Nhà liền kề | 116.257 | 21 | 144 | 160 |
| Shophouse | 22.470 | 10 | 100 | 98,789 |

Đã xuất **1.065 dòng phân phối** cho ba chỉ số, gồm toàn tập, từng property type, từng tỉnh và tổ hợp property type × tỉnh: [CSV phân phối](tinix-sale-price-distributions.csv). CSV có min/median/p1/p5/p25/p50/p75/p95/p99/max và số dòng hữu hạn/thiếu. Có 668.098 SALE ở Hồ Chí Minh và 592.458 ở Hà Nội; dữ liệu lệch mạnh về hai địa phương này. Không gọi median trên đây là giá thị trường hiện tại.

Mẫu riêng **1.000 SALE** dùng parser text hỗ trợ tỷ/triệu, dấu thập phân, một số dạng ghép và giá/m². Loại tiền thuê theo kỳ, tiền cọc/trả trước có ngữ cảnh nhận diện được. Ưu tiên ứng viên title; nhiều mức khác nhau giữ unresolved, không chọn mức gần `price` nhất để làm đẹp tỷ lệ. Ngưỡng khớp được đặt 2% để chấp nhận làm tròn, không phải chuẩn xác minh giá.

| Kết quả tự động | Dòng |
| --- | ---: |
| Có ít nhất một ứng viên giá text | 828 |
| Một mức tổng tương đương theo parser | 784 |
| So sánh được với price có số | 759 |
| Khớp trong 2% | 640 |
| Lệch trên 2% | 119 |
| Không có dạng giá hỗ trợ | 172 |
| Có một mức text nhưng price thiếu | 25 |
| Nhiều mức giá text, không tự chọn | 44 |

**640/759 = 84,32% là tỷ lệ tương thích parser v1**, không phải tỷ lệ price đúng. Parser có lỗi đọc mức giảm, quà/nội thất, trả trước và `1,363 tỷ` thành 1363 tỷ, có thể nhầm viết tắt dòng tiền hoặc thiếu `/m²`. Giá “nhỉnh”, “từ”, “dưới” và giỏ nhiều căn cũng không xác định một target chính xác.

Đã đọc lại full text của **30 trường hợp sai lệch tự động lớn nhất**: 10 trường hợp thực tế khớp trong 2% sau hiểu ngữ cảnh; 8 parser đọc nhầm tiền không phải giá tổng nhưng không có giá tổng để xác minh; 4 chưa xác định cơ sở đơn vị; 3 số cấu trúc khác số chào trong text; 5 price bằng 0 dù text có giá bán. Đây là nhóm được chọn theo cực trị, **không dùng 8/30 hay 10/30 suy ra tỷ lệ lỗi toàn bộ dữ liệu**. Giá đọc tay chỉ là cột kiểm tra, không ghi đè target.

Ví dụ có thể kiểm chứng bằng số và nội dung:

| Parquet gốc / dòng 0-based | Text | Giá/diện tích cấu trúc | Nhận định |
| --- | --- | --- | --- |
| shard_0008 / 119705 | Giá bán 370 tỷ, 71.884,3 m² | price 26.597.191 tỷ | Lệch 71.884,3 lần; price bằng giá tổng trong text nhân diện tích. Đây là quan sát số học, nguyên nhân upstream chưa biết. |
| shard_0000 / 163378 | Nhà 21,8 m², giá 5,95 tỷ | price 595.000 tỷ; area 22 m² | Giá lệch 100.000 lần. Không sửa giá theo text. |
| shard_0000 / 93225 | 66,5 triệu/m² × 54 m² = 3,591 tỷ | price 3,59 triệu | Sai lệch gần 1.000 lần giữa cột và text. |
| shard_0009 / 193557 | Giá 4,95 tỷ | price 0 | Target không dùng được như giá tổng. |
| shard_0009 / 165232 | 3,450 tỷ; mô tả xác nhận 3 tỷ 450 triệu | price 3,45 tỷ | Lỗi parser dấu phẩy, không phải lỗi price này. |
| shard_0006 / 42706 | Text ghi nguyên văn 16.5tr | price 16 tỷ | Mâu thuẫn giá/đơn vị. Không đoán rằng tr thực ra là tỷ. |

Chi tiết: [1.000 mẫu giá](tinix-text-price-audit.csv), [30 lệch tự động lớn nhất](tinix-text-price-largest-mismatches.csv), [review giá thủ công](tinix-price-mismatch-manual-review.csv), [summary review giá](tinix-price-manual-review-summary.json).

**6. Thời gian được kiểm tra độc lập**

`published_at` thực tế min **2025-06-01 00:01:38.762**, max **2026-03-30 23:59:56.217**. Riêng SALE max **2026-03-30 23:55:51.948**. Metadata khai báo đến 31/03/2026; scan không thấy dòng ngày 31/03. Có dữ liệu trong cả 10 tháng từ 06/2025 đến 03/2026, nhưng không phải giá cập nhật 10/2026 hay realtime. Ngày bài đăng không chứng minh mọi giá được cập nhật vào cùng thời điểm, hoặc là giá giao dịch thành công. Timestamp không có offset; không tự gán múi giờ.

| Tháng | Tất cả dòng | SALE v1 | RENT v1 | AMBIGUOUS v1 |
| --- | ---: | ---: | ---: | ---: |
| 06/2025 | 257.726 | 139.427 | 2.334 | 115.965 |
| 07/2025 | 364.215 | 192.185 | 3.164 | 168.866 |
| 08/2025 | 365.761 | 187.507 | 2.837 | 175.417 |
| 09/2025 | 352.239 | 180.831 | 2.862 | 168.546 |
| 10/2025 | 415.170 | 207.906 | 3.563 | 203.701 |
| 11/2025 | 407.202 | 194.794 | 3.742 | 208.666 |
| 12/2025 | 444.361 | 216.898 | 4.191 | 223.272 |
| 01/2026 | 283.760 | 136.104 | 2.635 | 145.021 |
| 02/2026 | 186.331 | 88.838 | 1.567 | 95.926 |
| 03/2026 | 423.979 | 203.272 | 4.157 | 216.550 |

Date NULL: **0**; parse lỗi: **0**; ngoài khoảng metadata: **0**; sau ngày review 04/10/2026: **0**. Không coi những mốc tương lai trong mô tả tiến độ dự án là `published_at`. [CSV tháng](tinix-monthly-counts.csv) và [summary full scan](tinix-transaction-audit-summary.json) là số liệu gốc của bảng.

**7. Chất lượng và cực trị**

| Kiểm tra | Full scan | SALE v1 nếu đã đo |
| --- | ---: | ---: |
| price NULL | 218.494 | 105.009 |
| price ≤ 0 | 57.320 | 25.545 |
| price = 0 | 57.320 | — |
| price < 0 | 0 | — |
| area thiếu | 4 | 3 |
| area ≤ 0 | 0 | 0 |
| province NULL hoặc rỗng | 0 | — |
| district NULL | 101.933 | — |
| ward NULL hoặc rỗng | 496.716 | 245.487 |

Exact duplicate: **36 nhóm / 86 dòng tham gia / 50 dòng dư**, nhóm lớn nhất 6. Kiểm tra SHA256 của serialization cả 19 cột gốc, bao gồm ngày đăng. Near duplicate candidate: **137.978 nhóm / 308.602 dòng tham gia / 170.624 dòng dư**, nhóm lớn nhất 30. Nhóm gần giống yêu cầu mọi trường khác giữ nguyên, chỉ bỏ `published_at` và chuẩn hóa hoa/thường/khoảng trắng trong name/description. Không dùng fuzzy match hoặc khoảng cách địa lý để tự gộp tài sản. Hai thống kê có phần giao nhau, không cộng số dòng dư. Không xóa duplicate. ID/URL gốc thiếu nên chưa xác minh cùng tài sản thực tế. [Ví dụ nhóm lặp](tinix-duplicate-examples.csv).

Cực trị full scan: price **26.597.191 tỷ**, area **82.000.000 m²**, frontage **9.080.000 m**, road width **103.000 m**. Căn hộ ở shard_0007 / 260658 ghi **82 m²** trong title/description nhưng `area` là 82.000.000; đây là sai lệch rõ với text, không chỉ một tài sản rất lớn hợp lệ. Road width 103.000 ở shard_0005 / 317726 khác mô tả ngõ 10 m. SALE có diện tích cực đại 66.879.000 m² trong một tin chuyển nhượng cổ phần sở hữu resort; nội dung công ty/tài sản kinh doanh vượt phạm vi nhà dân dụng. [25 ví dụ cực trị](tinix-extreme-examples.csv). Không cắt percentile hoặc loại giá cao chỉ vì cao.

**8. Provenance và license**

Nguồn phát hành được xác định là **TiniX AI**, repo [Vietnam Real Estate Listings](https://huggingface.co/datasets/tinixai/vietnam-real-estates), license publisher khai báo **CC BY-NC 4.0**. Theo license hiện tại, chỉ phù hợp phạm vi phi thương mại; phải ghi attribution, nguồn, license và nêu các thay đổi. License declaration không xác minh thay quyền đối với dữ liệu upstream. [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

Đã xem dataset card/metadata, README hiện tại, README lịch sử, commit history và publisher profile. [Commit history](https://huggingface.co/datasets/tinixai/vietnam-real-estates/commits/main) cho thấy bản 3,5 triệu dòng upload 14/04/2026; đây là ngày upload, không phải ngày thị trường. README tại [640eaf2](https://huggingface.co/datasets/tinixai/vietnam-real-estates/blob/640eaf23419f03bec40e495a3591af9d28807c45/README.md) có mô tả xử lý HTML, che số điện thoại, chuẩn hóa số, lọc theo ngày và bỏ `source`/`source_id`; phần mô tả xử lý/limitations bị bỏ ở commit 42426fa ngày 04/04. Đó là tuyên bố preprocessing của phiên bản cũ, không xác minh phương pháp thu thập hoặc tính đúng của mọi giá ở revision mới.

| Hạng mục | Mức xác minh |
| --- | --- |
| Publisher/repo/license declaration | Đã tìm thấy và lưu bằng chứng |
| Ngày và số dòng ở revision hiện tại | Quét độc lập được |
| Preprocessing | Có tuyên bố lịch sử, chưa tái tạo/xác minh toàn bộ |
| Website rao bán gốc | **unresolved** |
| Phương pháp thu thập, điều kiện truy cập/ToS | **unresolved** |
| Quyền phát hành từ nguồn website/chủ sở hữu upstream | **unresolved** |
| Listing URL/ID gốc để đối chiếu | Không có trong 19 cột hiện tại |

Link agent, website dự án hoặc quảng cáo trong description không chứng minh website nguồn. Không suy đoán xuất xứ và không scrape website rao bán. Publisher website `tinix.ai` không truy cập được trong lần kiểm tra; dùng các nguồn Hugging Face đã truy cập. [Bằng chứng provenance](tinix-provenance-review.json).

Attribution cho báo cáo/CSV dẫn xuất: **TiniX AI — Vietnam Real Estate Listings — CC BY-NC 4.0**, revision ở đầu báo cáo. Thay đổi chỉ gồm lấy mẫu/cắt excerpt, tính thống kê và bổ sung nhãn/nhận xét audit; chưa sửa giá, địa danh hoặc dữ liệu gốc.

**Địa giới: chỉ thống kê, chưa mapping**

Full scan có **63 giá trị tỉnh/thành cũ**; **626 tên district khác nhau**, tương ứng **649 khóa tỉnh + district**; **4.416 tên ward khác nhau**, tương ứng **6.301 khóa tỉnh + district + ward**. Các tên số như phường 1/5 lặp giữa địa phương nên đếm tên riêng và đếm khóa có ngữ cảnh khác nhau. Đây là các giá trị xuất hiện trong dữ liệu, không phải số đơn vị hành chính chính thức hiện hành. Khóa ward có thể chứa district NULL; chưa xác minh mã địa danh hay tính hợp lệ.

Province thiếu 0, district thiếu 101.933, ward thiếu 496.716. Không tạo alias cho phường/xã, không suy đoán mapping từ tên. Mapping 63 → 34 và xác minh cấp xã bằng nguồn chính thức chỉ được xem xét sau khi dataset được chấp nhận. Không dùng địa danh cũ để tuyên bố model hỗ trợ tất cả địa phương hiện hành.

**9–10. Khuyến nghị train và property type**

**Không đề xuất train ở vòng này.** Nhãn SALE chỉ xác minh ý định, không xác minh total price; dữ liệu còn giá bằng 0, sai khác đơn vị/hệ số, diện tích bất thường, giỏ nhiều căn và cổ phần/tài sản thương mại. Tỷ lệ khớp tự động bị ảnh hưởng parser nên chưa có tỷ lệ đúng target đáng tin. Nguồn upstream và quyền phát hành chưa được giải quyết. Không có property type nào được phê duyệt train trong kết luận này.

Nếu một vòng thẩm định sau giải quyết các vấn đề và được chấp nhận, nên ưu tiên đúng category **Căn hộ chung cư** cho một tài sản đơn lẻ, rồi xem xét **Nhà** sau khi tách được nhà dân dụng khỏi khách sạn/tòa CHDV/văn phòng. Đây là hướng xem xét, chưa phải tập train đã được duyệt. Không tạo category “nhà riêng/nhà mặt phố” vì dataset gốc chỉ có “Nhà”. Chưa đề xuất trộn Đất, Shophouse, Biệt thự/Nhà liền kề với hai loại trên; cần audit riêng mục đích sử dụng, cơ sở diện tích/giá, số lượng hỗ trợ và dòng tiền kinh doanh.

Để đánh giá lại sau này cần một classifier sửa các lỗi được ghi nhận, một mẫu giữ riêng mới/nhãn người review độc lập, kiểm chứng giá tổng với text/nguồn thực, tiêu chí xử lý giá và đơn vị có bằng chứng, và xác minh provenance. Đây chỉ là yêu cầu đánh giá lại, **chưa thực hiện cleaning hay training**.

**Tái lập và kiểm tra**

Scripts: `scripts/download-tinix-audit.py`, `scripts/tinix_audit_rules.py`, `scripts/audit-tinix-transactions.py`. Python + DuckDB 1.5.6; manifest chỉ rõ revision, kích thước và SHA256. `--reuse-label-cache` yêu cầu revision và hash rule khớp báo cáo trước. Quyết định review được ghi tại `scripts/finalize-tinix-audit-review.py` và `scripts/finalize-tinix-price-review.py`; đây là log review đã đọc text, không phải classifier thứ hai.

Test rule: **5 test pass, 2 expected failures** để ghi nhận lỗi monthly-income title và dấu phẩy thập phân ba chữ số; không che chúng thành test thành công về chất lượng. Không test hoặc thay model Health vì không có thay đổi sản phẩm. `git diff --name-only` không có file tracked thay đổi. Kiểm tra [integrity sau audit](tinix-source-integrity-check.json) xác nhận 10/10 file gốc còn nguyên. Dừng ở báo cáo này.
