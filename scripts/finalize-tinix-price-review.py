"""Log completed text review of the 30 largest automatic price mismatches.

These are selected extremes, not a random validation set. No source corrections.
"""
import csv
import json
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
REVISION='ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f'
SOURCE=Path(tempfile.gettempdir())/'tinix-transaction-audit'/REVISION/'price-largest-mismatches-full.json'
# Tuple: finding, manually interpretable total (if supported), reason.
REVIEW={
    0: ('literal_text_disagreement',16.5e6,'Text ghi 16.5tr, price 16 tỷ. Không tự đoán text nhầm tr thành tỷ.'),
    1: ('unresolved_price_basis',None,'50 triệu/m, không ghi rõ m². price đúng bằng 50 triệu × 720; không tự thêm đơn vị.'),
    2: ('unresolved_price_basis',None,'Title 17.5tr/m, description 1x triệu/m; chưa xác định đơn vị hoặc một giá chính xác.'),
    3: ('parser_false_mismatch_confirmed_match',26.5e9,'TN 100tr là thu nhập, không phải giá tổng. Text CHỈ 26 TỶ 5 tương ứng 26,5 tỷ; nhiều diện tích không khớp.'),
    4: ('parser_false_candidate_total_unverified',None,'34 triệu là giá trị quà tặng 2 chỉ vàng; không thấy giá tổng để xác minh.'),
    5: ('parser_false_mismatch_confirmed_match',57.2e6*185.2,'Title bỏ /m² nhưng mô tả ghi rõ 57,2tr/m²; tổng 10,59304 tỷ lệch price 10,64 tỷ dưới 2%. Giá VNĐ bị che một phần bởi [phone_number].'),
    6: ('unresolved_price_basis',None,'Title 9 triệu thiếu đơn vị; description chỉ dưới 1 tỷ. Không dùng khoảng giá để xác nhận một giá chính xác.'),
    7: ('parser_false_candidate_total_unverified',None,'280 triệu là quà tặng. Full description không công bố giá tổng.'),
    8: ('unresolved_price_basis',None,'72 triệu thiếu /m²; price bằng 72 triệu × 40,7. Có thể là giá đơn vị bị mất trong text, chưa kết luận.'),
    9: ('literal_text_disagreement',4.1e9,'Parser nhầm chiết khấu 150 triệu; nhưng full text cũng chào 4,1 tỷ/căn, khác price 5 tỷ. Không tự chọn giá đúng.'),
    10: ('parser_false_mismatch_confirmed_match',1.69e9,'100 triệu là chênh/giảm giá; mô tả ghi giá bán 1,690 tỷ, khớp price.'),
    11: ('parser_false_candidate_total_unverified',None,'1,2 tỷ là hạ chào, không thấy giá tổng để xác minh.'),
    12: ('parser_false_candidate_total_unverified',None,'600 triệu là nội thất/thiết kế, không thấy giá tổng để xác minh.'),
    13: ('parser_false_candidate_total_unverified',None,'500 triệu là gói nội thất; không thấy giá tổng để xác minh.'),
    14: ('parser_false_candidate_total_unverified',None,'300 triệu là thanh toán đầu. Không suy ra giá bán từ tỷ lệ/vốn hoặc giá cấu trúc.'),
    15: ('parser_false_mismatch_confirmed_match',7e9,'1 tỷ là nội thất tặng kèm; mô tả giá tổng 7 tỷ khớp price.'),
    16: ('parser_false_candidate_total_unverified',None,'8 tỷ là hạ giá. Không thấy giá tổng để xác minh.'),
    17: ('parser_false_mismatch_confirmed_match',200e9,'40 tỷ là mức giảm; mô tả ghi giá bán 200 tỷ khớp price.'),
    18: ('parser_false_candidate_total_unverified',None,'Chuỗi 152,7m2 tỷ lệ 2% bị đọc thành 2 tỷ. Vốn trả trước 1 tỷ không phải giá tổng.'),
    19: ('parser_false_mismatch_confirmed_match',3172460325,'1 tỷ là chiết khấu. Full text ghi GIÁ BÁN 3,172,460,325 VNĐ, price làm tròn 3,17 tỷ, lệch dưới 2%.'),
    20: ('nonpositive_target',4.95e9,'price 0 nhưng mô tả ghi giá 4,95 tỷ.'),
    21: ('nonpositive_target',9.7e9,'price 0 nhưng mô tả ghi giá bán 9,7 tỷ; nhỉnh 9 tỷ title là xấp xỉ.'),
    22: ('nonpositive_target',None,'price 0 nhưng text nhỉnh 7 tỷ. Không gán đúng 7 tỷ cho giá xấp xỉ.'),
    23: ('nonpositive_target',None,'price 0 nhưng title giá chỉ từ 8,2 tỷ: mức khởi điểm, không một target xác định.'),
    24: ('nonpositive_target',None,'price 0 nhưng text nhỉnh 1 tỷ. Không gán đúng 1 tỷ cho giá xấp xỉ.'),
    25: ('parser_false_mismatch_confirmed_match',1.363e9,'1,363 tỷ là thập phân theo ngữ cảnh căn hộ, không phải 1363 tỷ. price 1,36 tỷ lệch dưới 2%.'),
    26: ('literal_text_disagreement',66.5e6*54,'Text ghi rõ 66,5 triệu/m² và 54m²: tổng 3,591 tỷ; price 3,59 triệu, lệch gần 1000 lần.'),
    27: ('parser_false_mismatch_confirmed_match',3.45e9,'Title 3,450 tỷ được mô tả xác nhận lại 3 tỷ 450 triệu; khớp price 3,45 tỷ.'),
    28: ('parser_false_mismatch_confirmed_match',6.15e9,'6,150 tỷ dùng dấu phẩy thập phân theo ngữ cảnh nhà 75m²; price 6,15 tỷ khớp.'),
    29: ('parser_false_mismatch_confirmed_match',2.15e9,'2,150 tỷ theo ngữ cảnh căn hộ là 2,15 tỷ, khớp price; 440 triệu là thanh toán 20%.')
}


def main():
    rows=json.loads(SOURCE.read_text(encoding='utf-8'))
    assert len(rows)==30 and set(REVIEW)==set(range(30))
    public=list(csv.DictReader((DOCS/'tinix-text-price-largest-mismatches.csv').open(encoding='utf-8-sig')))
    assert [(r['source_shard'],r['source_row']) for r in rows]==[(r['source_shard'],r['source_row']) for r in public]
    result=[];counts={}
    for i,row in enumerate(rows):
        finding,total,reason=REVIEW[i]
        counts[finding]=counts.get(finding,0)+1
        result.append({'mismatch_rank':i+1,'source_shard':row['source_shard'],'source_row':row['source_row'],
            'name':row['name'],'price_original':row['price'],'automatic_total_vnd':row['parsed_total_vnd'],
            'reviewed_total_vnd':total,'finding':finding,'review_reason':reason,
            'reviewer':'assistant_text_review','review_scope':'title_and_full_description'})
    with (DOCS/'tinix-price-mismatch-manual-review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    summary={'rows':30,'sampling':'30 largest automatic relative errors; selected, nonrepresentative',
        'counts':counts,'raw_prices_corrected':0,'population_error_rate_estimated':False,
        'notes':'Literal text disagreement does not establish which value is the true asking price. Missing per-m2 units and approximate/from prices remain unresolved.'}
    (DOCS/'tinix-price-manual-review-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':
    main()
