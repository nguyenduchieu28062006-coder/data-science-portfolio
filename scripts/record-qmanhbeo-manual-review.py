"""Persist assistant's read-through observations, never training labels."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys
import tempfile
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
docs=ROOT/'docs'; cache=Path(tempfile.gettempdir())/'qmanhbeo-v3-source-audit-20261004'
records=json.loads((cache/'transaction-review-full-text.json').read_text(encoding='utf-8'))
sale_exceptions={22:'Chào bán và cho thuê 12 triệu, có điều kiện đặt cọc; không xác nhận sale-only.',
                 56:'Có giá bán và cho thuê 15 triệu/tháng; không ghi rõ hợp đồng thuê đang tồn tại.',
                 92:'Tiêu đề bán; mô tả ghi giá thuê 3,9 tỷ. Không tự sửa lỗi chữ.'}
rent_exceptions={21:'Có giá thuê và chuyển nhượng 130 tỷ.',32:'Tiêu đề cho thuê, giá theo tỷ; mô tả có căn cần bán.',
                 56:'Mô tả CHO THUÊ / BÁN cùng căn hộ.',73:'Cho thuê và sang nhượng; có cả bảng giá cần bán.',
                 74:'Tiêu đề thuê đất công nghiệp; mô tả giá bán/m², quyền đất chưa rõ.'}
confirmed_amb_sale={1,2,3,4,5,7,10,11,15,17,18,21,22,23,24,27,31,32,33,35,36,38,40,41,43,45,47,48,50,51,52,53,54,56,60,64,65,66,68,71,72,73,74,75,77,78,80,81,83,84,86,88,90,91,92,94,96,99,100}
output=[]
for record in records:
    rank=record['review_group_rank'];group=record['rule_label']
    if group=='SALE_HIGH_CONFIDENCE':
        label='AMBIGUOUS' if rank in sale_exceptions else 'SALE'
        reason=sale_exceptions.get(rank,'Lời chào bán hoặc chuyển nhượng rõ; dòng tiền thuê không đổi ý định giao dịch.')
    elif group=='RENT_HIGH_CONFIDENCE':
        label='AMBIGUOUS' if rank in rent_exceptions else 'RENT'
        reason=rent_exceptions.get(rank,'Chào thuê trực tiếp; mô tả hoặc giá theo tháng hỗ trợ ý định thuê.')
    else:
        label='SALE' if rank in confirmed_amb_sale else 'AMBIGUOUS'
        reason='Có lời chào bán, người mua hoặc chuyển quyền sở hữu trong nội dung đã đọc.' if label=='SALE' else 'Chưa đủ bằng chứng giao dịch chính từ nội dung đã đọc; giữ nhãn không rõ.'
        if rank==19: reason='Sang nhượng nhà hàng đang thuê mặt bằng; chưa chứng minh bán quyền sở hữu bất động sản.'
    output.append({'rule_label':group,'review_group_rank':rank,'source_record_1based':record['source_record_1based'],
                   'listing_id':record['listing_id'],'assistant_review_label':label,'reason':reason,
                   'reviewer':'assistant','review_method':'title, description opening and relevant offer contexts; full descriptions for disputed SALE 22/56/92; unresolved retained ambiguous'})
with (docs/'qmanhbeo-transaction-manual-review.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
stats={'reviewer':'assistant, not independent human ground truth','reviewed_records':len(output),
       'counts_by_rule_group':{group:dict(Counter(r['assistant_review_label'] for r in output if r['rule_label']==group)) for group in ['SALE_HIGH_CONFIDENCE','RENT_HIGH_CONFIDENCE','AMBIGUOUS']},
       'limitations':['Review uses displayed contexts, not a claim that every long description was read in full.',
                      'Unresolved counted as non-confirmed for conservative confirmation rate, not known false positives.',
                      'SALE sample labels stable; AMBIGUOUS diagnostic sample retained from prior rule stratum. No population estimate of true sale prevalence.',
                      'Rules revised during diagnostic review; these records are not an independent final validation holdout.'],
       'sale_conservative_confirmation_rate':.97,'rent_conservative_confirmation_rate':.95,
       'sale_precision_98pct_verified':False}
(docs/'qmanhbeo-manual-review-summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(stats,ensure_ascii=False))

# Mismatch observations refer to the v4 diagnostic sample read before the final
# parser run. Their source record IDs stay valid across parser versions.
# Pin identities explicitly: a later background parser run may replace its
# random sample cache. Manual notes must never follow a mutable rank sequence.
pinned=[(80761,'1336547.0',31.5e9),(99050,'1343341.0',6.1e9),(8753,'1333135.0',1.72e9),
        (46438,'1315193.0',1.1e9),(27403,'1348760.0',1.65e9),(230829,'1302434.0',8.5e9),
        (120632,'1333571.0',2e9),(183402,'1310805.0',3e9),(150436,'1208552.0',2e9),
        (158603,'1369594.0',710e6),(110983,'1307470.0',5.6e9),(143293,'1371803.0',570e6),
        (81946,'1309712.0',2.85e9),(228747,'1361245.0',2.39e9),(28183,'1310489.0',150e6),
        (216642,'1389123.0',59.7e9),(228611,'1365143.0',3.65e9),(227929,'1374646.0',7.5e9),
        (136901,'13130.0',3.9e9),(108228,'1387911.0',8.69e9),(12698,'1303228.0',2.99e9),
        (228419,'1369531.0',3.35e9),(150046,'1381926.0',135.31e9),(40770,'1230962.0',1.5e12),
        (221960,'1207988.0',9e9),(158672,'1308100.0',1.725e9),(101657,'1248243.0',6e9),
        (9858,'1508175.0',1.8e9),(208194,'1001759.0',200e6),(118326,'1410338.0',30e6)]
import pandas as pd
manifest=json.loads((docs/'qmanhbeo-download-manifest.json').read_text(encoding='utf-8'))
source=pd.read_csv(manifest['files'][0]['local_cache_path'],dtype=str,keep_default_na=False,
                   usecols=['Listing ID','Price','Area'])
price_records=[]
for row,identity,reference in pinned:
    original=source.iloc[row-1]
    assert original['Listing ID']==identity
    price_records.append({'source_record_1based':row,'listing_id':identity,'price_raw':original['Price'],
                          'area_raw':original['Area'],'reference':reference})
strong={1,2,3,4,5,6,11,13,14,17,18,20,21,22,23,26}
notes={7:'Giá hơn 2 tỷ là cận dưới; 2,4 tỷ chưa chứng minh lỗi.',8:'Hơn/nhỉnh 3 tỷ là khoảng; chưa chứng minh lỗi.',
       9:'Giá chỉ từ 2 tỷ và nhiều loại sản phẩm; chưa biết tổng giá căn cụ thể.',10:'710 triệu là vốn ban đầu, không phải tổng giá; lỗi tham chiếu audit v4.',
       12:'570 triệu là giá quảng cáo/vốn có thể là một phần; mô tả 19,5 triệu/m².',15:'Giá khởi điểm 150 triệu; chưa chứng minh tổng giá.',
       16:'Giá chưa đến 30 triệu/m² là cận trên, không phải giá chính xác.',19:'Price 5700, tiêu đề 3,9 tỷ, không có mô tả; xung đột chưa xác định bên đúng.',
       24:'Raw 150000 so với mô tả 1500 tỷ: khác hệ số triệu; có thể khác representation, không xác nhận giá nguồn.',
       25:'Ngang/nhỉnh 9 tỷ; 9,6 tỷ có thể là báo giá cụ thể.',27:'6 tỷ x là khoảng ẩn; parser v4 đọc sai thành 6 tỷ.',
       28:'Giá chỉ từ 18 triệu/m² là giá bắt đầu, không xác nhận tổng.',29:'Giảm 200 triệu bị v4 dùng làm tổng giá; giá thực trong mô tả khác.',
       30:'30 triệu VND/m² chưa được v4 nhận rate; được xử lý trong v5.'}
price_output=[]
for n,record in enumerate(price_records[:30],1):
    price_output.append({'diagnostic_sample_rule_version':'v4','review_rank':n,'source_record_1based':record['source_record_1based'],
                         'listing_id':record['listing_id'],'price_raw':record['price_raw'],'area_raw':record['area_raw'],
                         'text_reference_vnd_v4':record['reference'],
                         'finding':'PRICE_SCALE_INCONSISTENCY' if n in strong else 'UNRESOLVED_OR_AUDIT_PARSER_LIMITATION',
                         'note':'Price × 1.000.000 lệch gần 10/100 lần so với giá có đơn vị rõ trong tin; nguyên nhân pipeline chưa xác minh.' if n in strong else notes[n]})
with (docs/'qmanhbeo-price-manual-diagnostic-review.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(price_output[0]));writer.writeheader();writer.writerows(price_output)
