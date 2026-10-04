"""Export the assistant's completed text review of the frozen 300-row sample.

The decisions below were recorded after reading titles and full descriptions.
This is a review log, not another classifier and not independent human truth.
It must never relabel the dataset or rewrite the sampled rule labels.
"""
import csv
import json
import math
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
REVISION = 'ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f'
SAMPLE = Path(tempfile.gettempdir())/'tinix-transaction-audit'/REVISION/'manual-review-full-text.json'

# Conservative unresolved decisions; indexes refer to the fixed seed-42 sample.
UNRESOLVED = {
    8: 'Bài tổng quan dự án Alluvia: vị trí/quy mô/giá dự kiến/tiến độ, chưa xác định một đề nghị bán tài sản; không tính là true positive chắc chắn.',
    107: 'Tiêu đề có hợp đồng thuê hiện có; nội dung không xác định đề nghị bán hay thuê mới; giá cấu trúc thiếu.',
    172: 'Chỉ mô tả căn nhà và dòng tiền cho thuê; không thấy đề nghị bán hoặc thuê mới đủ rõ trong text.',
    182: 'Tin ghi cho thuê 25 triệu nhưng cũng hỗ trợ vay mua; ý định chính chưa chắc chắn, giá cấu trúc thiếu.',
    195: 'Tiêu đề Bán & cho thuê; mô tả có cả giá bán 6,99 tỷ và thuê 37 triệu/tháng. Đề nghị kép.',
    230: 'Mô tả tính năng và vay ngân hàng, chưa xác định ý định giao dịch chỉ từ text.',
    262: 'Giới thiệu căn hộ nghỉ dưỡng và tư vấn, chưa có đề nghị giao dịch đủ rõ trong text.',
    266: 'Giới thiệu CCMN và dòng tiền, chưa có đề nghị bán hoặc cho thuê mới đủ rõ trong text.',
    267: 'Mô tả đang rao thuê 100 triệu/tháng và giá rao 48 tỷ; title 33,5 tỷ. Chưa xác định một đề nghị chính.',
    282: 'Mô tả hạ tầng/tiện ích; không có đề nghị bán hay thuê đủ rõ trong text.',
    288: 'Giới thiệu nhà, pháp lý và hỗ trợ vay; không đủ chắc chắn về đề nghị giao dịch chỉ từ text.',
    298: 'Title và description đều rỗng; không suy đoán ý định từ price hay property type.'
}
NOTES = {
    11: 'Tin bán nhà có thu nhập cho thuê; thuê không phải đề nghị chính.',
    15: 'Tin bán tài sản tạo dòng tiền; không chuyển thành RENT.',
    16: 'Đất đang cho thuê 4 triệu/tháng nhưng có giá bán 7,4 tỷ.',
    22: 'Giá bán 2 tỷ 890; cho thuê 17 triệu là thu nhập từ nhà.',
    30: 'Tin bán có thu nhập 7,5 triệu/tháng; xác nhận ý định, không xác nhận target còn thiếu.',
    31: 'HĐT 170 triệu là thu nhập, giá bán 41 tỷ.',
    38: 'Nội dung bán căn hộ; footer giới thiệu dịch vụ thuê không đổi ý định chính.',
    43: 'Ý định bán rõ; title giá/m² và giá tổng trong mô tả cần đối chiếu riêng.',
    46: 'Tin bán 26 tỷ 500, hợp đồng thuê 50 triệu/tháng.',
    57: 'Rao bán mặt bằng thương mại; nhãn SALE không đảm bảo cùng phân khúc nhà ở.',
    64: 'Tin bán đất hỗn hợp đất ở/đất khác; không đánh đồng toàn bộ diện tích là đất ở.',
    71: 'Rao bán biệt thự 44 tỷ; 150 triệu/tháng là thuê hiện có.',
    79: '450 triệu nhận nhà là khoản thanh toán đầu; mô tả giá tổng 1,85 tỷ. Ý định SALE, không xác nhận target từ title.',
    84: 'Rao bán khách sạn; không cùng bài toán căn nhà dân dụng.',
    90: 'Rao bán căn hộ. Link quảng cáo/agent trong mô tả không chứng minh nguồn thu thập.',
    91: 'Diện tích text 63,375 m² là dấu thập phân; phải đọc theo ngữ cảnh, không mặc định dấu nghìn.',
    92: 'Rao bán; giá cũ 8 tỷ và mới 7,8 tỷ cùng xuất hiện, 23 triệu là thuê hiện có.',
    96: 'Rao bán, 25 triệu/tháng là thu nhập; nhỉnh 8 tỷ là giá xấp xỉ.',
    98: 'Rao bán tòa CHDV 28,5 tỷ; 150 triệu/tháng là thu nhập.',
    100: 'Title Bán CCMN; 90 triệu/tháng là doanh thu. Rule RENT sai vì từ viết tắt và CASHFLOW chỉ xét title.',
    103: 'Nội dung bán building, giá 47 tỷ 9; HĐT là thuê hiện có. Không xác nhận target 47 tỷ.',
    111: 'Chính sách bán căn hộ kèm cam kết thuê lại 2 năm; không phải đề nghị thuê chính.',
    118: 'Title Bán Toà VP; mô tả Bán Nhà Toà Nhà và giá bán 13X tỷ, thuê chỉ một phần tài sản.',
    119: 'Title bán liền kề; 40 triệu/tháng là thu nhập kinh doanh.',
    125: '9 triệu/tháng là trả góp sở hữu căn hộ, không phải tiền thuê.',
    137: '7 triệu/tháng là tài chính mua căn hộ theo chương trình mở bán.',
    147: 'Bán shophouse; vốn 3 tỷ là một phần thanh toán, thu nhập thuê không phải giá thuê chính.',
    148: 'Bán CHDV; 145 triệu/tháng là dòng tiền, giá bán 24,3 tỷ.',
    150: '6,8 triệu/tháng là trả góp; giá bán từ 1,68 tỷ.',
    151: 'Bán tòa CCMN/CHDV, thu 220 triệu/tháng là dòng tiền.',
    162: 'Chính sách bán và vay căn hộ; 450 triệu là 15% thanh toán ban đầu.',
    164: 'Title Bán CCMN; DT 50 triệu/tháng là doanh thu, không phải chào thuê mới.',
    166: 'Mua đất trả góp 1,9 triệu/tháng; target 0 không dùng được nhưng ý định bán rõ.',
    169: '186 triệu là vốn đầu, 5 triệu/tháng là thanh toán; giá tổng từ 1,164 tỷ.',
    170: 'Rao bán căn hộ nhưng text mô tả 75m²/3,9 tỷ, cấu trúc 50m²/2,7 tỷ: chưa xác nhận target.',
    177: 'Trả góp 9 triệu/tháng để mua căn hộ; không phải thuê.',
    187: 'Bán shophouse 450 tỷ; HĐ thuê 1 tỷ/tháng là hợp đồng hiện có.',
    194: 'Trả trước 777 triệu và thanh toán 6 triệu/tháng theo chính sách bán.',
    196: 'Title che dấu chữ bán B.A’N; mô tả giá 9,2 tỷ và nhà 8 phòng đang cho thuê.',
    197: 'Chủ đầu tư mở bán, cam kết/khả năng cho thuê; target 0 không được coi là giá bán thật.',
    200: 'Bán CC mini, 150 triệu/tháng là dòng tiền; rule bỏ sót do cách viết tắt.',
    210: 'Bán diện tích đất 60m², rule bỏ sót vì sau bán là số.',
    214: 'Bán căn 2 ngủ, giá 6,85 tỷ; rule bỏ sót do biến thể title.',
    215: 'Chủ cần bán gấp, có giá tổng 2,7 tỷ; thu nhập thuê không đổi ý định.',
    219: '500 triệu là mức giảm giá; giá bán mô tả 7,9 tỷ.',
    225: 'Chào bán nhiều lô đất; ý định bán rõ nhưng một dòng chưa chắc đại diện một tài sản.',
    231: '400 triệu nhận nhà là thanh toán trước, có giá/m² và chính sách mua.',
    255: '5 tỷ title là 30% vốn; giá bán mô tả 16,5 tỷ.',
    269: 'Chào bán theo sào; không tự đổi sào ra m² hoặc xác nhận target 8,5 tỷ.',
    281: 'Chào bán dãy trọ; text diện tích 200m² khác title/cấu trúc 155m².',
    294: 'Chào bán nhà; có nhiều giá theo phương án thanh toán và VAT, không một target chắc chắn.',
    296: 'Giỏ 10 lô bán trong một tin; giá cấu trúc ứng với lô đầu, không phải 10 tài sản độc lập.'
}


def main():
    rows = json.loads(SAMPLE.read_text(encoding='utf-8'))
    assert len(rows) == 300
    expected = ['SALE_HIGH_CONFIDENCE']*100+['RENT_HIGH_CONFIDENCE']*100+['AMBIGUOUS']*100
    assert [r['rule_label'] for r in rows] == expected
    public = list(csv.DictReader((DOCS/'tinix-transaction-audit-sample.csv').open(encoding='utf-8-sig')))
    assert [(r['_shard'],str(r['_source_row'])) for r in rows] == [(r['source_shard'],r['source_row']) for r in public]
    reviews = []
    for index,row in enumerate(rows):
        label = 'AMBIGUOUS' if index in UNRESOLVED else 'SALE_HIGH_CONFIDENCE'
        reason = UNRESOLVED.get(index) or NOTES.get(index) or (
            'Nội dung rao bán/nhận quyền sở hữu; đề cập thuê là khai thác tài sản hoặc thanh toán. Chỉ xác minh ý định trong text.'
            if 100<=index<200 else 'Nội dung chào bán/nhận quyền sở hữu. Chỉ xác minh ý định trong text, chưa xác minh giao dịch hoặc giá thật.')
        reviews.append({'sample_index':index,'source_shard':row['_shard'],'source_row':row['_source_row'],
            'name':row['name'],'rule_label':row['rule_label'],'review_label':label,
            'review_reason':reason,'reviewer':'assistant_text_review',
            'review_scope':'title_and_full_description','review_date':'2026-10-04'})
    with (DOCS/'tinix-transaction-manual-review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(reviews[0]));writer.writeheader();writer.writerows(reviews)
    confusion={}
    for row in reviews:
        counts=confusion.setdefault(row['rule_label'],{})
        counts[row['review_label']]=counts.get(row['review_label'],0)+1
    correct=sum(r['review_label']=='SALE_HIGH_CONFIDENCE' for r in reviews[:100])
    n=100;z=1.959963984540054;p=correct/n
    center=(p+z*z/(2*n))/(1+z*z/n)
    margin=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    result={'reviewer':'assistant_text_review','independent_human_ground_truth':False,
        'review_scope':'titles_and_full_original_descriptions; observed_text_intent_only',
        'rule_frozen_before_review':True,'classifier_tuned_on_this_sample':False,
        'sample_rows':len(reviews),'confusion_counts':confusion,
        'sale_true_positive':correct,'sale_sample_size':n,'sale_precision_point_estimate':p,
        'sale_wilson_95pct_interval':[center-margin,center+margin],
        'sale_point_estimate_meets_98pct':p>=.98,
        'sale_95pct_lower_bound_meets_98pct':center-margin>=.98,
        'rent_confirmed_in_rent_sample':0,
        'limitations':['Not independent human review or verified transaction truth.',
            '100 SALE rows do not establish a population precision of at least 98%.',
            'Precision concerns intent only, not target price, legal status or individual-unit identity.',
            'Equal-size stratified sample does not represent overall market proportions; recall not estimated.']}
    (DOCS/'tinix-manual-review-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
