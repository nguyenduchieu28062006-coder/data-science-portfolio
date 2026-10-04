# Thẩm định nguồn dữ liệu Vietnam House Price Prediction

Đây là review raw/metadata lịch sử. Quyết định không train raw vẫn giữ nguyên. BETA mới chỉ dùng thống kê subset căn hộ đã lọc; xem [báo cáo subset](verified-vietnam-house-data-report.md). Không approve hoặc train nguyên bộ TiniX.

Vòng khảo sát metadata dưới đây được giữ làm bằng chứng lịch sử. Kết quả quét toàn bộ và review mẫu ở [báo cáo audit tiếp theo](tinix-transaction-audit-report.md) đã xác nhận ngày cuối thực tế là **30/03/2026**, `price` trong Parquet gốc là chuỗi, và kết luận **C. REJECT** cho việc train ở trạng thái hiện tại.

Ngày khảo sát: 04/10/2026, Asia/Saigon. Trạng thái: chưa được người dùng chấp nhận; chưa cleaning, training, evaluation, export hoặc triển khai frontend.

Ứng viên có khoảng dữ liệu gần hiện tại nhất xác minh được trong khảo sát này là **Tinix Vietnam Real Estate Listings (2025–2026)**. Chưa đủ cơ sở để đưa thẳng vào train: publisher ghi dữ liệu gồm cả bán và thuê nhưng không có cột phân biệt; nguồn website gốc và quyền thu thập chưa được mô tả rõ. Không suy diễn rằng dataset mới đăng lên đồng nghĩa dữ liệu mới.

## 10 thông tin để duyệt dataset

| Mục | Kết quả thẩm định |
| --- | --- |
| 1. Dataset | `tinixai/vietnam-real-estates`, do TiniX AI công bố; chỉ là ứng viên, chưa chọn train. |
| 2. Source | [Dataset gốc](https://huggingface.co/datasets/tinixai/vietnam-real-estates). Revision kiểm tra: `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`. README không chỉ rõ các website cung cấp tin gốc hoặc quy trình xác minh tin. |
| 3. License | Publisher công bố CC BY-NC 4.0: cần attribution; chỉ sử dụng phi thương mại theo license, sử dụng thương mại cần xin phép. Không coi license của người đăng dataset là bằng chứng đã có mọi quyền từ nguồn upstream. |
| 4. Số dòng | Dataset server báo **3.500.744**, thống kê `partial=false`; đây là số dòng trước cleaning của project, không phải số tin bán hợp lệ hoặc số tài sản duy nhất. Dữ liệu đã được publisher xử lý trước. |
| 5. Ngày dữ liệu | README của revision trên ghi **01/06/2025–31/03/2026**. Chưa quét toàn bộ `published_at` để kiểm tra min/max; thống kê server chỉ cung cấp độ dài chuỗi ngày. Repository sửa lần cuối 14/04/2026; ngày này không thay thế ngày dữ liệu. |
| 6. Tỉnh/thành | Thống kê server có **63 tên theo hệ cũ**; danh sách đầy đủ và số dòng từng tỉnh trong file evidence. Nhiều nhất: Hồ Chí Minh, Hà Nội, Đà Nẵng, Bình Dương, Khánh Hòa. Có tên cũ như Long An, Hải Dương, Bà Rịa - Vũng Tàu. |
| 7. Feature thật | Có địa chỉ tỉnh/huyện/phường/đường/dự án, loại tài sản, diện tích, phòng ngủ, phòng tắm, số tầng, mặt tiền, độ sâu nhà, đường trước nhà, hướng nhà/ban công, tiêu đề/mô tả và ngày đăng. **Không có cột pháp lý riêng**, chiều rộng nhà riêng, ID tin, URL tin gốc, tọa độ, cờ bán/thuê, đơn vị tiền/chu kỳ thuê. Danh sách 19 cột nguyên gốc nằm trong evidence. |
| 8. Target | `price` được publisher mô tả là giá rao VNĐ; dự kiến đổi thành `total_price_vnd` **chỉ cho tin xác minh là bán**. `price_per_m2_vnd = price / area` là giá tham khảo suy ra. Chưa xác minh tổng giá cho tất cả bản ghi; giá thuê hoặc giá rao theo m² phải tách trước. Đây là giá rao, chưa phải giá giao dịch. |
| 9. Địa giới | Cần mapping từ hệ cũ sang 34 tỉnh/thành và phường/xã hiện hành. Tên phường đơn lẻ không đủ định danh; quận/huyện cũ chỉ dùng làm ngữ cảnh mapping/trace, không là input bắt buộc. Chưa tạo alias suy đoán. |
| 10. Độ mới | Đến 03/2026 theo metadata, khoảng 6 tháng trước ngày khảo sát. Có bản ghi năm 2026 theo công bố, nhưng **không gọi là giá mới nhất 2026, giá hiện tại hoặc realtime**. Phạm vi thực dùng sau kiểm định có thể ngắn hơn metadata. |

Nguồn bằng chứng: [README cố định theo revision](https://huggingface.co/datasets/tinixai/vietnam-real-estates/blob/ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f/README.md), [API thông tin](https://datasets-server.huggingface.co/info?dataset=tinixai%2Fvietnam-real-estates), [API thống kê](https://datasets-server.huggingface.co/statistics?dataset=tinixai%2Fvietnam-real-estates&config=default&split=train), [snapshot chọn lọc](vietnam-house-price-source-evidence.json).

## Các điểm ảnh hưởng trực tiếp đến khả năng dùng

- Không được lọc bán/thuê chỉ bằng mức giá. Tin bán có thể nhắc thu nhập cho thuê, tin thuê có thể nhắc giá trị căn nhà; tìm chữ “thuê” đơn lẻ cũng không đủ tin cậy. Cần xác minh nguồn hoặc định nghĩa tập tin bán với quy tắc rõ, kiểm tra thủ công và loại bản ghi mơ hồ. Số mẫu đủ train chưa xác định.
- Schema không có pháp lý riêng; chưa có cơ sở bắt người dùng nhập pháp lý hoặc tạo mức đóng góp “Pháp lý”. Không đưa mô tả/tiêu đề chứa giá vào feature train, để tránh leakage.
- Thống kê có giá 0, giá cực lớn, diện tích và mặt tiền rất lớn. Đây là dấu hiệu cần kiểm tra đơn vị và lỗi nhập, chưa phải căn cứ tự xóa mọi outlier. Không tính metrics hoặc giá dự đoán trong giai đoạn này.
- Có nhiều cột thiếu dữ liệu. Nếu được chấp nhận, chỉ dùng feature hữu ích được kiểm chứng; không bắt người dùng nhập tất cả các trường thưa dữ liệu.
- Thống kê loại tài sản thật có **5 category**: Nhà, Căn hộ chung cư, Đất, Biệt thự/Nhà liền kề, Shophouse. Bảng minh họa README liệt kê thêm Nhà mặt phố nhưng thống kê không có category này; không tạo thêm category trên UI.
- Không có ID/URL tin nên không thể khẳng định mọi bản ghi trùng là cùng tài sản. Dedup cần chứng cứ đủ mạnh, và kiểm soát cùng tài sản xuất hiện giữa train/test theo thời gian.

## Kiểm tra chất lượng từ server, chưa cleaning

| Cột | Số bản ghi thiếu | Tỷ lệ xấp xỉ |
| --- | ---: | ---: |
| price | 218.494 | 6,24% |
| ward_name | 496.716 | 14,19% |
| bedroom_count | 1.600.361 | 45,72% |
| bathroom_count | 1.720.974 | 49,16% |
| frontage_width | 1.726.424 | 49,32% |
| floor_count | 2.691.982 | 76,90% |
| road_width | 2.830.873 | 80,87% |
| house_depth | 3.432.288 | 98,05% |

Thiếu pháp lý có nghĩa không có cột, không phải giá trị pháp lý “Unknown” đã được thu thập. Đây là báo cáo thẩm định metadata; cleaning report raw/clean/duplicates/invalid sẽ chỉ có sau khi dataset được chấp nhận và xử lý.

## Nguồn khác đã xem

1. [SpringWang08/hanoi-hcmc-real-estate](https://huggingface.co/datasets/SpringWang08/hanoi-hcmc-real-estate): publisher báo 106.205 dòng, upload sửa lần cuối 07/05/2026. [README](https://huggingface.co/datasets/SpringWang08/hanoi-hcmc-real-estate/blob/ac8f07b8ae211e1422a875a66195cfacb75c7a29/README.md) thừa nhận synthetic enrichment, giá proxy và có thể có synthesized listings; license `other`, ngày tin gốc chưa xác định. **Loại** vì không đáp ứng dữ liệu thật, provenance và license rõ.
2. [sarahooker/vietnam-real-estate-listings](https://huggingface.co/datasets/sarahooker/vietnam-real-estate-listings): viewer có 400 dòng, dữ liệu preference-training và phần nội dung sinh cho LLM, không thấy license rõ trên card. Không chọn làm nguồn regression.
3. [Vietnam Housing Dataset 2024 trên Kaggle](https://www.kaggle.com/datasets/nguyentiennhan/vietnam-housing-dataset-2024): nguồn cũ hơn; trang dataset không trả đủ metadata trong lần khảo sát này. Không dùng tên dataset để tự xác nhận ngày thực tế, số dòng hoặc license.

Không tìm được trong khảo sát này một nguồn tin bán thuần mới hơn 03/2026 có đồng thời provenance, ngày dữ liệu và license đủ rõ. Điều này không khẳng định rằng không có nguồn khác ngoài phạm vi tìm kiếm.

## Nguồn chuẩn hóa địa danh dự kiến

- [Nghị quyết 202/2025/QH15](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-quyet-so-202-2025-qh15-ve-sap-xep-don-vi-hanh-chinh-cap-tinh-119250612174148722.htm) cho mapping cấp tỉnh.
- [Quyết định 19/2025/QĐ-TTg và bảng mã](https://xaydungchinhsach.chinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-cac-don-vi-hanh-chinh-cap-xa-moi-11925070418263625.htm) cho danh mục hiện hành: 34 tỉnh/thành và 3.321 xã/phường/đặc khu được ban hành từ 01/07/2025. Cần kiểm tra văn bản sửa đổi nếu có khi triển khai.
- Mapping phường/xã cần nghị quyết sắp xếp tương ứng từng địa phương. Nếu đơn vị cũ bị chia một phần và không có địa chỉ đủ chi tiết, giữ Unknown; không gán toàn bộ đơn vị cũ vào một đơn vị mới.
- Danh mục 34 tỉnh/thành không đồng nghĩa model đã hỗ trợ dự đoán mọi phường/xã. Chỉ mở khu vực đủ dữ liệu train và mapping xác minh được.

## Quyết định hiện tại

Dừng trước train đúng cổng duyệt dataset người dùng yêu cầu ở mục 26–27. TiniX là ứng viên cho **thẩm định sâu tiếp theo**, chưa là dataset được duyệt để training. Cần làm rõ provenance/quyền sử dụng từ nguồn gốc, tách tập bán có tổng giá VNĐ đáng tin cậy và xác minh địa danh trước khi có thể train.

Không sửa index, history, Auth, Health Prediction, Data Analyzer hoặc stylesheet trong giai đoạn này. Không commit, push hay deploy.

Script tái kiểm tra: `python scripts/review-vietnam-house-data.py`. Script chỉ đọc API metadata/statistics và README, kiểm tra revision ổn định, lưu JSON; không tải toàn bộ 1,67 GB Parquet và không gọi `.fit()`.
