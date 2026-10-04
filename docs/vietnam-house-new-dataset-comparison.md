# Khảo sát nguồn mới cho Vietnam House Price Prediction

Khảo sát lịch sử này không đánh giá BETA mới. Andy vẫn REJECT cho ML; TiniX raw không được approve nguyên bộ. Sản phẩm mới dùng thống kê BETA từ subset căn hộ. Xem [báo cáo subset](verified-vietnam-house-data-report.md); gate ML FAIL và không train.

Đối chiếu artifact hiện tại ngày 04/10/2026: **Andy model v1 — MODEL NOT SAFE TO PUBLISH / NOT READY**. Có artifact đã train không thay đổi quyết định REJECT; chưa xác minh nghĩa tổng giá bán và phân loại giao dịch từng dòng. Xem [đối chiếu hiện tại](vietnam-house-model-reconciliation.md) để biết rows, features, metrics và blocker chính xác.

Ngày kiểm tra: **04/10/2026**. Phạm vi: lựa chọn nguồn và đọc dữ liệu để kiểm chứng, không cleaning hoặc training.

**Kết luận: chưa tìm được dataset đủ bằng chứng đáp ứng toàn bộ tiêu chí bắt buộc.** Sáu ứng viên trong bảng dưới đều **REJECT cho training ở trạng thái hiện tại**. Không dùng nhãn APPROVE WITH LIMITATIONS để bỏ qua điều kiện bắt buộc về bán–thuê, target, đơn vị hoặc provenance.

**Đề xuất duy nhất để ưu tiên xác minh tiếp: [Vietnamese Real Estate Listings 2025 — qmanhbeo](https://www.kaggle.com/datasets/qmanhbeo/vietnamese-real-estate-listings-may-2024), version 3.** Đây là ứng viên có nguồn gốc được nêu tên, schema và thời gian hữu ích nhất trong nhóm khảo sát; **chưa được đề xuất dùng để train**. Điểm chặn là mâu thuẫn đơn vị giá và chưa có bằng chứng xác nhận tập bán thuần hoặc cột transaction_type. Không chọn bộ này vì kích thước lớn.

TiniX tiếp tục **REJECT cho House Price Prediction**; chỉ giữ tư cách ứng viên dashboard/EDA phi thương mại cho bước sau. Các bản sao hoặc bộ dẫn xuất từ TiniX không được coi là nguồn thay thế độc lập.

## Phương pháp và giới hạn kiểm chứng

- Đọc metadata/file list qua API công khai của Kaggle; lưu phản hồi, version và SHA-256. Không crawl website rao bán.
- Đọc trọn bốn CSV nhỏ: Catalyst buying, Andy sale, Vietnam 2024 và Hanoi. File nguồn giữ nguyên trong TEMP; không tạo bản cleaned, không sửa giá hoặc gán transaction label.
- Với qmanhbeo, chỉ đọc **128 KiB** đầu file **220.057.487 byte**, kiểm tra 203 record hoàn chỉnh. Với cnglmph, chỉ đọc **128 KiB** đầu file **46.033.823 byte**, kiểm tra 148 record hoàn chỉnh. Đây là prefix, không phải mẫu ngẫu nhiên hay đại diện cho toàn dataset. Record cuối có thể bị cắt nên không tính.
- Số dòng được ghi là **đếm thực tế**, **tác giả nghiên cứu công bố**, hoặc **chưa xác minh**. Không suy số dòng từ dung lượng. Tổng payload các CSV đã đọc khoảng **25,87 MB**; không tải toàn bộ hai file lớn.
- Ngày upload, tên file và tên dataset được phân biệt với ngày tin gốc. Các timestamp không kèm timezone trong CSV không được tự coi là UTC. Last Updated Date là ngày cập nhật tin, chưa chứng minh là ngày đăng lần đầu.
- License dưới đây là license publisher khai báo. Không có tài liệu xác minh riêng quyền cấp phép nội dung của website nguồn; không suy rằng license khai báo chứng minh được quyền đó, và cũng không kết luận có vi phạm khi chưa có bằng chứng.
- Với các nguồn khai báo tin thật, chưa thấy công bố synthetic/proxy trong metadata đã đọc. Điều này không xác minh được mọi dòng là thật. Các trường hợp công bố synthetic hoặc dẫn xuất TiniX được loại riêng.

## Bảng so sánh đủ 13 trường — nhóm đa tỉnh

| Trường | Vietnamese Real Estate Listings 2025 | Vietnam Real Estate Datasets — Catalyst | Real Estate in Vietnam |
|---|---|---|---|
| **Dataset** | qmanhbeo, v3; `VN-real-estate-Apr-Sept-2025.csv` | cresht2606, v1; chỉ xét `house_buying_dec29th_2025.csv` | andyvo1009, v1; chỉ xét `sale_real_estate.csv` |
| **Source** | [Kaggle](https://www.kaggle.com/datasets/qmanhbeo/vietnamese-real-estate-listings-may-2024); publisher nêu **Guland.vn** | [Kaggle](https://www.kaggle.com/datasets/cresht2606/vietnam-real-estate-datasets-catalyst); publisher nêu **batdongsan.vn** | [Kaggle](https://www.kaggle.com/datasets/andyvo1009/real-estate-in-vietnam); chưa nêu website thu thập |
| **License** | CC BY-NC 4.0; mô tả giới hạn giáo dục/nghiên cứu và giữ quyền cho nền tảng/chủ nội dung | MIT khai báo trên Kaggle | Apache 2.0 khai báo trên Kaggle |
| **Row count** | Tổng chưa xác minh; 203 record được đọc trong prefix | **66.912** record buying, đếm toàn file; không cộng file rental | **42.257** record sale, đếm toàn file; **39.920** product_id riêng biệt; không cộng rental |
| **Date range** | Tên file công bố Apr–Sept 2025, chưa xác minh min/max toàn file. Prefix có Last Updated Date **16/04–13/09/2025**, Scraped At **13/09/2025**. Upload **30/09/2025**, không phải ngày tin | Snapshot theo glossary **29/12/2025**. Chỉ có timeline_hours **2–26.280 giờ**, không có ngày đăng tuyệt đối; khoảng ngày tin chưa xác minh. Upload **02/01/2026**, không phải dữ liệu 2026 | Publisher mô tả **Feb 2025**; upload **12/02/2025**. Không có ngày tin/thu thập từng dòng, khoảng ngày dữ liệu thực chưa xác minh |
| **Geographic coverage** | Dữ liệu Việt Nam, có Province và Location theo publisher; prefix chỉ xác minh **An Giang (Mới)**. Chưa đếm đủ các tỉnh, chưa chứng minh phủ toàn quốc/34 tỉnh | **57 nhãn tỉnh/thành gốc** từ token cuối location; HCM **32.625**, Hà Nội **25.708**, Đà Nẵng **1.857**; nhiều tên trước sắp xếp | **58 nhãn tỉnh/thành gốc**; HCM **14.613**, Hà Nội **14.169**, Đà Nẵng **2.472**; chủ yếu tỉnh + quận/huyện, chưa có ward riêng |
| **Property types** | Có Property Type/Slug; prefix thấy **Nhà riêng, Đất**. Chưa xác minh danh sách toàn file | **Không có cột property type**. Title có thông tin nhưng chưa được xác thực thành category | **Không có property type**; không thể phân biệt nhà, căn hộ, đất, thương mại chỉ từ 0 phòng |
| **Target** | Có Price, Area. Metadata ghi **tỷ VNĐ**, nhưng Price=2700 đi với title ghi **2,7 tỷ**, Price=600 đi với **600 triệu**: mẫu khớp **triệu VNĐ**. Đơn vị toàn cột chưa được xác nhận. Area khớp m² trong title kiểm tra. Không thấy cột price/m² riêng trong header | `price_million_vnd` được mô tả là **tổng giá triệu VNĐ**, `area_m2` là m². Tuy nhiên file buying có tin giá thuê theo tháng, nên target không đồng nhất với total sale price | `price` giữ chuỗi có **tỷ/triệu/nghìn VNĐ**, publisher mô tả sale price trong file sale. `area` có **m² ở toàn bộ 42.257 dòng**. Có giá thỏa thuận; chưa đối chiếu được với tin gốc |
| **Feature columns** | Title, Description, Location, Province, Property Type/Slug, Listing ID, Area, Width, Length, Bedrooms, Bathrooms, Floors, Position, Direction, Alley Width, Road Type, Last Updated, Scraped At, Last Updated Date; thêm tọa độ và thông tin tài khoản. Không có pháp lý riêng; Width chưa thể tự gọi là frontage | id, detail_url, title, location, timeline_hours, area_m2, bedrooms, bathrooms, floors, **frontage boolean**, price_million_vnd. Frontage là vị trí mặt tiền, **không phải chiều rộng mặt tiền (m)**. Không có pháp lý hoặc road width | **Đúng 6 cột:** product_id, address, price, area, bedrooms_num, bathrooms_num. Không có floors, frontage, road width, pháp lý, property type, date, title, description, URL |
| **Missing/quality issues** | Chỉ tính trong 203 prefix: thiếu Bedrooms **122**, Bathrooms **162**, Floors **118**, Width **33**, Alley Width **145**. Mâu thuẫn đơn vị là điểm chặn; không ngoại suy tỷ lệ toàn file | Thiếu Area **16.568**, Price **2.103**; **362 giá bằng 0**. Area lớn nhất **62.000.000 m²**, Floors lớn nhất **772.221.339** cho thấy cần kiểm tra lỗi extraction. 86 title có dấu hiệu bắt đầu bằng cho thuê; chưa coi 86 là số rent đã audit | **2.264 dòng trùng toàn bộ**; **2.337 lần product_id lặp thêm**; **4.253 giá thỏa thuận**. Bedrooms=0 **18.318**, Bathrooms=0 **19.783**, chưa biết missing hay không áp dụng. Có product_id 42141375 giá **5 nghìn**. Không có cột trống không đồng nghĩa đủ thông tin |
| **Sale/rent distinction** | Không có transaction_type trong schema. Title mẫu có bán; metadata chưa cam kết sales-only và chưa có collection manifest tách bán–thuê | Tách tên file buying/rental **không đảm bảo tách đúng**: ID **134081** trong buying ghi cho thuê **15 triệu/tháng**, Price=15. Không có transaction_type | Có file sale/rental riêng và tên file sale rõ. Mô tả tổng lại gọi dữ liệu rental; không có transaction_type/title/URL để kiểm tra phân loại của từng dòng |
| **Provenance** | Tác giả Quang Manh Nguyen, nguồn Guland.vn được nêu trực tiếp, ID + title/description + dấu thời gian; chưa có URL gốc hoặc code/manifest thu thập để xác nhận sale-only | Nêu BeautifulSoup4 và HTTP, **66.905 URL không trống thuộc batdongsan.vn**, ID riêng biệt; có truy vết tốt hơn TiniX, nhưng việc tách transaction và extraction có lỗi | Có publisher, version, product_id; thiếu tên website, URL, code, thời gian và quy trình thu thập. **Chưa đạt yêu cầu provenance rõ hơn TiniX** |
| **Suitability for ML** | **REJECT hiện tại**: đơn vị giá mâu thuẫn và sale-only chưa được chứng minh. **Ứng viên ưu tiên duy nhất để xác minh tiếp**, chưa train | **REJECT**: đã xác nhận rent trong buying, target sai nghĩa và lỗi feature rõ | **REJECT hiện tại**: chưa đủ provenance và bằng chứng kiểm chứng target/tập sale; thiếu feature để kiểm soát khác biệt loại tài sản |

## Bảng so sánh đủ 13 trường — nhóm 2024 và nguồn theo thành phố

| Trường | House Price Prediction Dataset Vietnam — 2024 | Ho Chi Minh City Real Estate Data 2025 | Vietnam Housing Dataset (Hanoi) |
|---|---|---|---|
| **Dataset** | nguyentiennhan, v8; `vietnam_housing_dataset.csv` | cnglmph, v1; `data_public.csv` | ladcva, v1; `VN_housing_dataset.csv` |
| **Source** | [Kaggle](https://www.kaggle.com/datasets/nguyentiennhan/vietnam-housing-dataset-2024); publisher nêu **batdongsan.vn** | [Kaggle](https://www.kaggle.com/datasets/cnglmph/ho-chi-minh-city-real-estate-data-2025); publisher chỉ nêu public listings và người hướng dẫn qmanhbeo, không chỉ rõ website | [Kaggle](https://www.kaggle.com/datasets/ladcva/vietnam-housing-dataset-hanoi); description trống; chưa xác minh website/collector code ở nguồn sơ cấp |
| **License** | **CC0** khai báo trên Kaggle | **CC BY-NC 4.0**, chỉ giáo dục/nghiên cứu | **CC BY-NC-SA 4.0** |
| **Row count** | **30.229**, đếm toàn file | **51.304** theo tác giả nghiên cứu sử dụng bộ này, **chưa đếm toàn file**; đọc 148 record prefix. **41.555** là số sau cleaning của nghiên cứu khác, không phải số nguồn đã xác minh tại đây | **82.496 record có dữ liệu + 1 record toàn trường rỗng**; parser đọc 82.497 record CSV sau header |
| **Date range** | **Không có cột date**. Upload **22/09/2024**; không xác nhận được ngày bắt đầu/kết thúc tin, không coi tên 2024 là khoảng ngày tin | Nghiên cứu mô tả năm **2025**. Prefix có Last Updated Date **09/09–30/09/2025**, Scraped At **30/09/2025**. Khoảng toàn file chưa xác minh; upload **30/09/2025** | Cột Ngày parse được ở **82.496** record: **05/08/2019–05/08/2020**. Upload **31/01/2021**. Các bản reupload 2025 không làm dữ liệu mới hơn |
| **Geographic coverage** | Đa tỉnh; token gốc HCM **11.628**, Hà Nội **9.996**, ngoài ra có **150** nhãn `Hồ Chí Minh.` và **461** nhãn `Hà Nội.`. Không dùng số token khác nhau để tuyên bố số tỉnh | TP.HCM theo publisher; prefix có tên phường/xã mới lẫn quận/địa danh cũ. Chưa xác minh bao phủ TP.HCM sau sắp xếp hoặc tính đúng từng ward | Hà Nội; có địa chỉ/quận/phường cũ. **82.006** record có token cuối đúng `Hà Nội`; một số địa chỉ thiếu/không chứa đầy đủ tỉnh |
| **Property types** | **Không có property type** | Prefix chỉ có **Nhà riêng**; nghiên cứu dùng **căn hộ chung cư, đất, nhà riêng**. Chưa xác minh toàn bộ category nguồn; không coi số loại đã nghiên cứu là toàn bộ danh sách | Có **Nhà ngõ, hẻm; Nhà mặt phố, mặt tiền; Nhà phố liền kề; Nhà biệt thự**; thiếu type ở 32 record tính cả record rỗng |
| **Target** | Price là **tỷ VNĐ**, Area là **m²** theo glossary publisher; giá quan sát **1–11,5 tỷ**, diện tích **3,1–595 m²**. Chưa có chứng cứ sales-only để gọi chắc là total sale price | Price số không kèm đơn vị trong header/glossary. Mẫu Price=5700 đi với **5,7 tỷ**, gợi ý Price là triệu VNĐ; Area=50 đi với **50 m²**, gợi ý Area là m². **Chưa có data dictionary xác nhận tổng giá và hệ số đơn vị toàn cột**; nghiên cứu báo đơn giá triệu VNĐ/m² | Giá/m2 giữ đơn vị **triệu/m²** và **tỷ/m²**; Diện tích có m². Có thể suy total price cho record có cả hai trường hợp lệ, sau khi xác nhận sale và xử lý các đơn vị khác/target lỗi |
| **Feature columns** | **12 cột:** Address, Area, Frontage (m), Access Road (m), House direction, Balcony direction, Floors, Bedrooms, Bathrooms, Legal status, Furniture state, Price | **28 cột** như qmanhbeo: Title, Price, Area, Location, Listing ID, Last Updated, Property Type, Width, Length, Bedrooms, Bathrooms, Floors, Position, Direction, Alley Width, Road Type, Description, Latitude, Longitude, VIP Account, Avatar, Agent Role, Agent Name, Agent Listing Count, Province, Property Type Slug, Scraped At, Last Updated Date | Ngày, Địa chỉ, Quận, **Huyện (giá trị thực là phường ở mẫu)**, Loại hình nhà ở, Giấy tờ pháp lý, Số tầng, Số phòng ngủ, Diện tích, Dài, Rộng, Giá/m2 và cột index không tên. Không có bathrooms/road width riêng |
| **Missing/quality issues** | Thiếu Frontage **11.564**, Access Road **13.297**, Floors **3.603**, Bedrooms **5.162**, Bathrooms **7.074**, Legal status **4.506**. Không thiếu Price/Area, không trùng toàn dòng; không có listing ID để tìm trùng tin đáng tin cậy; dải giá hẹp chưa có tài liệu giải thích việc chọn mẫu | Chỉ tính trong 148 prefix: thiếu Bedrooms **85**, Bathrooms **116**, Floors **73**, Width **52**, Alley Width **130**. Property Type và Slug có mức chi tiết khác nhau; có địa chỉ mới/cũ. Không suy chất lượng toàn file từ prefix | Thiếu Số tầng **46.098**, pháp lý **28.887**, Dài **62.670**, Rộng **47.052**, Giá/m2 **13**, tính cả record rỗng. Cột Huyện có tên không đúng ngữ nghĩa. Chưa có ID/URL để kiểm tra trùng listing |
| **Sale/rent distinction** | Không có transaction_type, title, description, URL hoặc cam kết sale-only rõ trong mô tả. Không suy bán chỉ vì giá tính tỷ hay có Sale contract | [Tác giả nghiên cứu](https://nghiencuu.tapchikinhtetaichinh.vn/dinh-gia-bat-dong-san-tai-tp-ho-chi-minh-tren-co-so-ngon-ngu-bang-chung-tu-mo-hinh-tf-idf-phobert-xgboost-va-shap-164897.html) gọi tập gốc là tin rao bán; CSV không có transaction_type; chưa kiểm chứng tất cả source rows hoặc quy trình thu thập | Không có transaction_type/title/URL. Đơn giá không tự chứng minh sales-only; chưa có provenance sơ cấp xác nhận tập bán |
| **Provenance** | Có publisher, source website, glossary và version; không có date/ID/URL/code thu thập để đối chiếu từng tin hoặc selection rules | Có publisher, project đại học và người hướng dẫn; bài nghiên cứu dẫn đúng dataset. **Người hướng dẫn qmanhbeo và schema giống nhau chưa đủ chứng minh lấy dữ liệu từ dataset Guland của qmanhbeo** | Publisher Le Anh Duc; mô tả Kaggle trống. Các repo bên thứ ba gọi dữ liệu Chợ Tốt/AloNhaDat không được dùng để xác nhận nguồn khi chưa liên kết với collector gốc |
| **Suitability for ML** | **REJECT hiện tại**: thiếu chứng cứ bán–thuê, khoảng ngày và truy vết tin. Có feature tốt nhưng chưa đủ điều kiện nguồn | **REJECT hiện tại**: đơn vị target chưa được publisher xác nhận, nguồn website/transaction pipeline thiếu, chỉ mới kiểm tra prefix | **REJECT cho mục tiêu hiện tại**: dữ liệu kết thúc năm 2020, quá cũ; provenance và sales-only vẫn chưa xác nhận |

## Bằng chứng quyết định

**Catalyst: tên file buying không bảo đảm là tin bán.** Record id **134081** có title/URL nói cho thuê, phần giá ghi **15 triệu/1 tháng** nhưng `price_million_vnd=15`. Record id **129928** cũng có title và URL cho thuê với Price=15. Việc nhìn giá nhỏ để tự chuyển label sang rent hoặc loại bằng ngưỡng tiền sẽ không đủ để chứng minh toàn tập sạch rent. Bộ này vi phạm điều kiện bắt buộc số 1 ở trạng thái nguồn hiện có.

**qmanhbeo: sai khác đơn vị có thể làm target lệch 1.000 lần.** Record Listing ID **1241101** có title ghi **2,7 tỷ**, `Price=2700`, `Area=78.7`. Record **1182246** ghi **600 triệu**, `Price=600`, `Area=34.2`. Hai mẫu khớp cách lưu triệu VNĐ, trái với metadata ghi tỷ VNĐ. Không tự nhân 10⁹ theo metadata hoặc nhân 10⁶ trên toàn tập khi chưa xác nhận một quy ước đơn vị nhất quán. Việc title có giá bán ở các mẫu không chứng minh toàn bộ nguồn sales-only.

**Andy: đơn vị văn bản rõ, provenance chưa rõ.** File sale có giá/diện tích nguyên văn và id; có thể audit parser về sau. Hiện không có title, URL, date, property_type hoặc source website nên không kiểm tra được nguồn, loại tài sản, đúng tổng giá hay phân loại transaction từ tin gốc. Không tự nhận source là batdongsan.com.vn từ kiểu product_id.

**Vietnam 2024: nhiều feature không giải quyết thiếu transaction metadata.** Publisher nêu website và đơn vị rõ. Tuy nhiên, không có bằng chứng sơ cấp đủ để xác nhận tập bán thuần, dải ngày tin hay lý do giá bị giới hạn 1–11,5 tỷ. Không gọi đây là synthetic chỉ vì dải giá hẹp; cũng không giả định đây là giá mới.

**HCM 2025: bài nghiên cứu hỗ trợ, không thay thế data dictionary nguồn.** Bài nghiên cứu công bố 51.304 tin nguồn, 41.555 quan sát sau cleaning và sử dụng đơn giá triệu VNĐ/m². Đây là thông tin của tác giả nghiên cứu, chưa phải số dòng/đơn vị toàn cột Price được xác minh ở lần khảo sát này. Không áp dụng quy tắc cắt phân vị của nghiên cứu hay lấy R² của nghiên cứu làm kết quả model project.

## Các ứng viên khác đã sàng lọc

| Ứng viên | Kiểm tra và quyết định |
|---|---|
| [Hanoi Housing price 2024 — huytrngquc](https://www.kaggle.com/datasets/huytrngquc/hanoi-housing-price-2024) | v9, `HN_Houseprice.csv` 4.657.394 byte; CDLA-Sharing 1.0; upload 22/12/2024. Description chỉ ghi tên, thiếu source, sale/rent, đơn vị và ngày tin. **REJECT hiện tại**; không cần tải CSV khi provenance đã chưa đạt |
| [Vietnam Housing Dataset HN — quoctrong04](https://www.kaggle.com/datasets/quoctrong04/vietnam-housing-dataset-hn) | Upload 08/05/2025; description trống, license Other không có điều khoản trong description. File cùng tên/dung lượng với nguồn Hanoi cũ, chưa xác minh byte-identical. **REJECT**, không lấy ngày reupload làm ngày dữ liệu |
| [VietNam Housing HCM — lammike](https://www.kaggle.com/datasets/lammike/vietnam-housing-hcm) | Upload 20/11/2024; license Other nhưng description không xác định điều khoản; giá chỉ mô tả local currency, nguồn chỉ gọi một website. **REJECT**, không tải thêm |
| [Ho Chi Minh House Esate 2025 — huyle411](https://www.kaggle.com/datasets/huyle411/data-moi-ne) | Metadata nói dẫn xuất **TiniX**; MIT do người reupload khai báo không tự thay thế license/quyết định nguồn trước. **REJECT cho training**, không tải |
| [vietnam-real-estate — locngodev](https://www.kaggle.com/datasets/locngodev/vietnam-real-estate) | MIT khai báo, description trống; một file CSV **3.239.272.435 byte**, upload 25/05/2026. Không có provenance/đơn vị/transaction được giải thích. **REJECT hiện tại**, không tải file lớn |
| Vietnam Room Rental Prices 2026 và Vietnam House Rent Dataset | **REJECT theo phạm vi**: dữ liệu thuê, không phải sale prediction; không tải |

## Xếp hạng và đề xuất duy nhất

| Nhãn | Kết quả cho training tại thời điểm khảo sát |
|---|---|
| **APPROVE** | Không có |
| **APPROVE WITH LIMITATIONS** | Không có; chưa ứng viên nào được chứng minh đạt đủ các điều kiện bắt buộc để dùng nhãn này |
| **REJECT** | Cả sáu ứng viên chính; lý do phân biệt cụ thể trong bảng trên |

**Chỉ ưu tiên qmanhbeo / Vietnamese Real Estate Listings 2025, v3 để hoàn tất xác minh nguồn.** Bộ này nêu Guland.vn trực tiếp, giữ title/description/ID, có feature vật lý, Property Type, Province và timestamp. Các mẫu có tên địa phương mới. Đây là lợi thế bằng chứng so với nguồn không nêu website hoặc mất nội dung tin; chưa chứng minh bao phủ toàn quốc hoặc tính đúng của mapping địa giới.

Các điểm phải được giải quyết trước khi có thể đổi quyết định training:

1. Data dictionary/collection evidence xác nhận `Price` là **total sale price**, đơn vị nhất quán; giải thích mâu thuẫn tỷ–triệu giữa metadata và CSV.
2. Chứng cứ collection chỉ lấy mục **bán**, hoặc transaction_type được xác thực. Không dùng title keyword hoặc giá cao để âm thầm coi mọi dòng là sale.
3. Xác nhận đơn vị Area/Width/Length/Alley Width, nguồn và selection rules; kiểm chứng min/max ngày và số dòng trên phạm vi đủ sau khi các điểm chặn nguồn đã được giải quyết.
4. Phạm vi sử dụng dự kiến tuân theo CC BY-NC 4.0 và giới hạn giáo dục/nghiên cứu được publisher nêu; không coi dataset này là lựa chọn cho thương mại.

Đây là các điều kiện đánh giá, **chưa liên hệ publisher, chưa tải toàn bộ, chưa cleaning/training**. Chưa có nguồn nào được xác minh là tin 2026. Những record kiểm tra mới nhất có thời gian trong **2025**; không có căn cứ gọi “giá mới nhất 2026”, realtime hay giá thị trường hiện tại.

## Địa danh sau sắp xếp

Chưa nguồn nào được xác minh có mapping đầy đủ và đáng tin cậy về 34 tỉnh/thành cùng phường/xã hiện hành. Catalyst, Andy, Vietnam 2024 và Hanoi giữ nhiều tên cũ. Prefix Guland/HCM 2025 có cả tên mới và tên cũ; hậu tố `(Mới)` không chứng minh mapping đúng từng tin. Chưa tạo mapping, chưa gán địa phương khác, chưa thiết kế UX quận/huyện. Nếu tiếp tục sau này, giữ tên gốc và dùng Unknown cho địa danh chưa xác định.

## Artifacts và trạng thái thực thi

- [Metadata ban đầu](vietnam-house-new-candidates-kaggle-metadata.json), [discovery](vietnam-house-new-candidates-discovery.json), [metadata bổ sung](vietnam-house-new-candidates-extra-metadata.json), [qmanhbeo/Andy metadata](vietnam-house-new-candidates-further-metadata.json), [sàng lọc cuối](vietnam-house-new-candidates-final-discovery.json), [Hanoi 2024 metadata](vietnam-house-new-candidates-hanoi-2024-metadata.json).
- [Manifest file/version/SHA-256/phạm vi đọc](vietnam-house-new-candidates-file-manifest.json).
- [Profile nguồn: số dòng, schema, missing, date, inspection leads và mẫu seed 42](vietnam-house-new-candidates-profiles.json).
- [Script đọc file có giới hạn](../scripts/review-vietnam-house-candidate-files.py), [script profile chỉ đọc](../scripts/profile-vietnam-house-candidates.py).
- Nguồn sơ cấp bổ trợ HCM: [nghiên cứu dẫn chính dataset cnglmph](https://nghiencuu.tapchikinhtetaichinh.vn/dinh-gia-bat-dong-san-tai-tp-ho-chi-minh-tren-co-so-ngon-ngu-bang-chung-tu-mo-hinh-tf-idf-phobert-xgboost-va-shap-164897.html).

Không train TiniX hoặc nguồn mới. Không clean toàn bộ TiniX. Không sửa website, Health, Data Analyzer, Auth hoặc History. Không git commit, push hoặc deploy. **Dừng tại báo cáo này.**
