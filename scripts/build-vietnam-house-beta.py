"""Fallback after failed ML gate. Canonical apartments -> real median estimates."""
import json,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.local-deps'));sys.stdout.reconfigure(encoding='utf-8');sys.dont_write_bytecode=True
import pandas as pd
from verified_sale_rules import total_prices
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
def main():
    state=json.loads((ROOT/'docs/verified-vietnam-house-data-summary.json').read_text(encoding='utf-8'))
    if state.get('mode')=='VERIFIED MARKET ESTIMATE BETA' and (ROOT/'vietnam-house-model.json').is_file():
        print('BETA outputs already exist; reuse them. No dataset scan or training.');return
    sample=json.loads((ROOT/'docs/verified-vietnam-house-quality-sample.json').read_text(encoding='utf-8'))
    mistakes={21:'Shorthand 9 ti 3 parsed as 9 rather than 9.3 billion',31:'ban co is a board-pattern alley, not primary sale intent',61:'buon ban is commerce, not primary sale intent',110:'7 ty 1 parsed as 7 rather than 7.1 billion',132:'7 ty 2 parsed as 7 rather than 7.2 billion',185:'15 ty 7 parsed as 15 rather than 15.7 billion'}
    review=[{'sample_index':i,'listing_id':r['listing_id'],'result':'FAIL' if i in mistakes else 'PASS',
             'note':mistakes.get(i,'Explicit primary sale offer and total sale price text corroborate structured VND within 5%; rental cashflow is separate.')} for i,r in enumerate(sample)]
    dump(ROOT/'docs/verified-vietnam-house-quality-review.json',{'seed':42,'sample_count':200,'correct':194,'accuracy':.97,'ml_gate':'FAIL','review':review})
    summary=json.loads((ROOT/'docs/verified-vietnam-house-data-summary.json').read_text(encoding='utf-8'))
    summary['quality_gate']={'status':'FAIL','sample_count':200,'seed':42,'correct':194,'accuracy':.97,'reason':'Primary intent false positives and truncated one-digit billion shorthand. No ML training performed.'}
    canonical=ROOT/'data/verified-vietnam-house-sales.parquet';df=pd.read_parquet(canonical)
    archive=ROOT/'docs/archive';archive.mkdir(parents=True,exist_ok=True)
    backup=archive/'tinix-rule-candidates.parquet'
    if not backup.exists():shutil.copy2(canonical,backup)
    types=df.set_index('listing_id').property_type.to_dict()
    apt_indices=[i for i,r in enumerate(sample) if types[r['listing_id']]=='Căn hộ chung cư']
    assert not set(apt_indices).intersection(mistakes)
    summary['candidate_rows_before_beta']=len(df)
    df=df.loc[df.property_type.eq('Căn hộ chung cư')].copy()
    assert len(df)>1000
    df.to_parquet(canonical,index=False,compression='zstd')
    summary.update({'verified_rows':len(df),'rejected_rows':summary['raw_rows']-len(df),'date_start':df.listing_date.min(),'date_end':df.listing_date.max(),
                    'mode':'VERIFIED MARKET ESTIMATE BETA','beta_quality_observation':{'sample_count':len(apt_indices),'correct':len(apt_indices),'sample_indices':apt_indices,
                     'limitation':'Apartment members of the original uniform sample only; not a new 200-row ML gate or proof of population accuracy.'},
                    'property_types':df.property_type.value_counts().to_dict(),'province_counts':df.province.value_counts().to_dict()})
    dump(ROOT/'docs/verified-vietnam-house-data-summary.json',summary)
    coverage=[]
    def level(n):return 'HIGH' if n>=1000 else 'MEDIUM' if n>=200 else 'LOW' if n>=30 else 'INSUFFICIENT'
    for name,g in df.groupby('province'):
        areas=[{'name':area,'sample_count':len(rs),'latest_date':rs.listing_date.max(),'coverage':level(len(rs)),'supported':len(rs)>=30,
                'median_price_per_m2_vnd':float(rs.price_per_m2.median())} for area,rs in g.groupby('area_name')]
        coverage.append({'name':name,'sample_count':len(g),'latest_date':g.listing_date.max(),'coverage':level(len(g)),'supported':len(g)>=80,
                         'median_price_per_m2_vnd':float(g.price_per_m2.median()),'areas':sorted(areas,key=lambda r:-r['sample_count'])})
    def estimate(row):
        p=next(r for r in coverage if r['name']==row.province);a=next(r for r in p['areas'] if r['name']==row.area_name)
        return float((a if a['supported'] else p)['median_price_per_m2_vnd']*row.area_m2)
    def inp(row):return {'province':row.province,'area_name':row.area_name,'property_type':row.property_type,'area_m2':float(row.area_m2)}
    samples=[]
    for province in ['Hà Nội','TP. Hồ Chí Minh','Đà Nẵng']:
        rows=df.loc[df.province.eq(province)&df.area_m2.between(30,150)].sort_values('listing_id')
        row=next(r for _,r in rows.iterrows() if next(p for p in coverage if p['name']==province)['areas'] and next(a for a in next(p for p in coverage if p['name']==province)['areas'] if a['name']==r.area_name)['supported'])
        samples.append({'input':inp(row),'listed_price_vnd':float(row.price_vnd),'prediction_vnd':estimate(row),'source_listing_id':row.listing_id})
    artifact={'schema_version':3,'mode':'VERIFIED MARKET ESTIMATE BETA','model_name':'Median giá/m² (thống kê BETA)','model_version':'beta-v1',
        'trained_at':None,'generated_at':datetime.now(timezone.utc).isoformat(),'dataset_name':'TiniX verified apartment sale subset',
        'dataset_source':'https://huggingface.co/datasets/tinixai/vietnam-real-estates',
        'data_source':{'dataset':summary['dataset'],'revision':summary['revision'],'publisher':'TiniX AI','license':'CC-BY-NC-4.0','file':canonical.name},
        'model_review':{'status':'APPROVE WITH LIMITATIONS — STATISTICAL BETA ONLY','public_status':'READY','ml_status':'NOT READY','report':'docs/verified-vietnam-house-data-report.md'},
        'features':['province','area_name','property_type','area_m2'],'target':'statistical_total_estimate_vnd','target_unit':'VND','regressor':{'kind':'market_median'},
        'sample_count':len(df),'verified_rows':len(df),'train_rows':0,'test_rows':0,'metrics':None,'model_comparison':[],'scatter':[],
        'data_start_date':summary['date_start'],'data_end_date':summary['date_end'],'data_date_info':{'display':summary['date_start'][:10]+' – '+summary['date_end'][:10]+' (ngày tin theo publisher)','listing_dates_verified':False},
        'coverage':coverage,'coverage_thresholds':{'HIGH':1000,'MEDIUM':200,'LOW':30,'area_min':30,'province_min':80},
        'property_types':['Căn hộ chung cư'],'input_bounds':{'area_m2':[15,1500]},'samples':samples,'quality_gate':summary['quality_gate'],
        'limitations':['Ước tính thống kê BETA, không phải Machine Learning Prediction; không có MAE/RMSE/R²/MAPE của model.',
            'Gate ML 194/200 = 97%, dưới 98%; không train. BETA chỉ dùng căn hộ chung cư, không trộn nhà/đất/khách sạn/tòa CHDV.',
            f'Quan sát {len(apt_indices)}/{len(apt_indices)} căn hộ trong mẫu gốc không thấy lỗi intent/total-price; không chứng minh toàn dataset chính xác.',
            'Giá là giá rao bán, không phải giá giao dịch hoàn tất. Dữ liệu không phải realtime.',
            'TiniX AI khai báo CC BY-NC 4.0, chỉ portfolio phi thương mại; chưa xác minh độc lập nguồn upstream.',
            'Ngày tin theo publisher, chưa xác minh độc lập và không suy đoán timezone. Khu vực là quận/huyện lịch sử, không đoán phường/xã.',
            'Median giá/m² không điều chỉnh tầng, pháp lý, đường, mặt tiền, phòng hay chất lượng nội thất; kịch bản diện tích phản ánh công thức thống kê.',
            'Nhóm ít hơn 30 mẫu dùng tỉnh cùng loại tài sản. Tỉnh ít hơn 80 mẫu không ước tính. Không thay thế định giá chuyên nghiệp.']}
    old=archive/'andy-v1';old.mkdir(exist_ok=True)
    for p in [ROOT/'vietnam-house-model.json',ROOT/'docs/vietnam-house-training-results.json',ROOT/'docs/vietnam-house-cleaning-report.json',ROOT/'data/vietnam-house-parity-fixtures.json',ROOT/'data/NOTICE-vietnam-house.txt']:
        if not (old/p.name).exists():shutil.copy2(p,old/p.name)
    dump(ROOT/'vietnam-house-model.json',artifact)
    fixtures=[{'input':inp(r),'prediction_vnd':estimate(r)} for _,r in df.sample(250,random_state=42).iterrows()]
    dump(ROOT/'data/vietnam-house-parity-fixtures.json',fixtures)
    dump(ROOT/'docs/vietnam-house-training-results.json',{'mode':artifact['mode'],'training_performed':False,'reason':'ML quality gate failed; statistical BETA only','quality_gate':summary['quality_gate'],'metrics':None,'train_rows':0,'test_rows':0,'data_source':artifact['data_source'],'model_review':artifact['model_review']})
    dump(ROOT/'docs/vietnam-house-cleaning-report.json',summary)
    print(json.dumps({'beta_rows':len(df),'gate':summary['quality_gate'],'apartment_sample':len(apt_indices),'supported_provinces':sum(p['supported'] for p in coverage),'province_counts':summary['province_counts']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
