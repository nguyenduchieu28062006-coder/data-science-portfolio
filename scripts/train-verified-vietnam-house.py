"""Bounded training on the gated canonical subset, never reads original shards."""
import importlib.util,json,sys,time,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local-deps'));sys.stdout.reconfigure(encoding='utf-8');sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor,RandomForestRegressor
spec=importlib.util.spec_from_file_location('legacy_house',ROOT/'scripts/train-vietnam-house-model.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
FIELDS=['province','area_name','property_type','area_m2','bedrooms','bathrooms']

class Prep(legacy.HousePreprocessor):
    def cats(self,x):
        base=super().cats(x);base['property_type']=x.property_type.to_numpy();return base
    def artifact(self):
        p=super().artifact();p['categorical_features']=['province','area_name','property_type'];return p

def main():
    summary=json.loads((ROOT/'docs/verified-vietnam-house-data-summary.json').read_text(encoding='utf-8'))
    assert summary['quality_gate']['status']=='PASS' and summary['quality_gate']['accuracy']>=.98,'Quality gate required'
    data=pd.read_parquet(ROOT/'data/verified-vietnam-house-sales.parquet')
    # Fitting is bounded; static market aggregates retain every verified row.
    if len(data)>60000:data=data.sample(60000,random_state=42)
    data=data.sort_values(['listing_date','listing_id']).reset_index(drop=True)
    groups=pd.util.hash_pandas_object(data[FIELDS+['price_vnd']],index=False).to_numpy()
    # Equal timestamp cohorts stay intact. Repeated identical feature/price groups
    # are removed from earlier train if they appear in the later holdout.
    cutoff=data.listing_date.iloc[int(len(data)*.8)]
    test=np.flatnonzero(data.listing_date.ge(cutoff));train=np.flatnonzero(data.listing_date.lt(cutoff))
    held=set(groups[test]);train=np.array([i for i in train if groups[i] not in held])
    assert len(train)>1000 and len(test)>200
    a,b=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(data.iloc[train],groups=groups[train]))
    p=Prep().fit(data.iloc[train[a]]);xa=p.transform(data.iloc[train[a]]);xb=p.transform(data.iloc[train[b]])
    y=data.price_vnd.to_numpy();comparisons=[]
    candidates=[('Median baseline',DummyRegressor(strategy='median')),('Ridge',Ridge(alpha=25)),
                ('Gradient Boosting',GradientBoostingRegressor(n_estimators=80,max_depth=3,min_samples_leaf=30,learning_rate=.08,random_state=42)),
                ('Random Forest',RandomForestRegressor(n_estimators=60,max_depth=12,min_samples_leaf=10,max_features=.6,n_jobs=2,random_state=42))]
    for name,m in candidates:
        started=time.time();m.fit(xa,np.log1p(y[train[a]]));scores=legacy.metrics(y[train[b]],np.expm1(m.predict(xb)))
        comparisons.append({'model_name':name,'target_transform':'log1p_vnd','validation':scores,'fit_seconds':round(time.time()-started,2)})
        print(name,scores,flush=True)
    selected=min((r for r in comparisons if r['model_name']!='Median baseline'),key=lambda r:r['validation']['mae'])
    p=Prep().fit(data.iloc[train]);xa=p.transform(data.iloc[train]);xb=p.transform(data.iloc[test]);model=None
    for (name,m),result in zip(candidates,comparisons):
        m.fit(xa,np.log1p(y[train]));result['holdout']=legacy.metrics(y[test],np.expm1(m.predict(xb)))
        if name==selected['model_name']:model=m
    pred=np.expm1(model.predict(xb));training=data.iloc[train];coverage=[]
    for province,rows in training.groupby('province'):
        areas=[]
        for area,rs in rows.groupby('area_name'):
            areas.append({'name':area,'sample_count':len(rs),'latest_date':rs.listing_date.max(),'coverage':legacy.coverage(len(rs)),
                          'supported':len(rs)>=30,'median_price_per_m2_vnd':float(rs.price_per_m2.median())})
        coverage.append({'name':province,'sample_count':len(rows),'latest_date':rows.listing_date.max(),'coverage':legacy.coverage(len(rows)),
                         'supported':len(rows)>=80,'median_price_per_m2_vnd':float(rows.price_per_m2.median()),'areas':sorted(areas,key=lambda r:-r['sample_count'])})
    def inp(i):return {k:None if pd.isna(data.iloc[i][k]) else float(data.iloc[i][k]) if k in ['area_m2','bedrooms','bathrooms'] else data.iloc[i][k] for k in FIELDS}
    samples=[]
    for province in ['Hà Nội','TP. Hồ Chí Minh','Đà Nẵng']:
        choices=[i for i in test if data.iloc[i].province==province and p.area_counts_.get((province,data.iloc[i].area_name),0)>=30 and 30<=data.iloc[i].area_m2<=150]
        if choices:
            i=choices[0];samples.append({'input':inp(i),'listed_price_vnd':float(y[i]),'prediction_vnd':float(np.expm1(model.predict(p.transform(data.iloc[[i]])))[0]),'source_listing_id':data.iloc[i].listing_id})
    split={'kind':'temporal_80_20','cutoff':cutoff,'train_rows':len(train),'test_rows':len(test),'excluded_duplicate_groups':len(data)-len(train)-len(test),
           'limitation':'Published timestamps are publisher values, not independently verified; no timezone inferred. Equal timestamp cohorts stay together. Identical feature/target groups cannot cross train/test.'}
    artifact={'schema_version':2,'model_name':selected['model_name'],'model_version':'v1','mode':'ML MODEL','trained_at':datetime.now(timezone.utc).isoformat(),
       'model_review':{'status':'APPROVE WITH LIMITATIONS','public_status':'READY','report':'docs/verified-vietnam-house-data-report.md'},
       'dataset_name':'TiniX verified Vietnam house sales','dataset_source':'https://huggingface.co/datasets/tinixai/vietnam-real-estates',
       'data_source':{'dataset':summary['dataset'],'revision':summary['revision'],'publisher':'TiniX AI','license':'CC-BY-NC-4.0','file':'verified-vietnam-house-sales.parquet'},
       'data_start_date':summary['date_start'],'data_end_date':summary['date_end'],
       'data_date_info':{'listing_dates_verified':False,'display':summary['date_start'][:10]+' – '+summary['date_end'][:10]+' (ngày tin theo publisher)'},
       'sample_count':len(train)+len(test),'verified_rows':summary['verified_rows'],'train_rows':len(train),'test_rows':len(test),
       'features':FIELDS,'target':'total_price_vnd','target_unit':'VND','target_transform':'log1p_vnd','preprocessing':p.artifact(),
       'regressor':legacy.export_model(model,selected['model_name']),'metrics':selected['holdout'],'model_comparison':comparisons,
       'split':split,'selection':'Lowest MAE on grouped validation within temporal train, seed 42; holdout not used for selection.',
       'coverage':coverage,'coverage_thresholds':{'HIGH':1000,'MEDIUM':200,'LOW':30,'province_min':80,'area_min':30},
       'property_types':sorted(training.property_type.unique()),'input_bounds':{'area_m2':[15,1500],'bedrooms':[1,20],'bathrooms':[1,20]},
       'reference_input':inp(int(train[0])),'samples':samples,'scatter':[{'actual_vnd':float(y[test[j]]),'predicted_vnd':float(pred[j])} for j in np.random.default_rng(42).choice(len(test),min(180,len(test)),replace=False)],
       'quality_gate':summary['quality_gate'],
       'limitations':['Giá là giá rao bán, không phải giá giao dịch hoàn tất. Dữ liệu không phải realtime.',
          'Chỉ sử dụng tập con vượt qua kiểm tra title bán và giá tổng văn bản khớp structured ±5%; không xác minh độc lập tin gốc.',
          'TiniX AI khai báo CC BY-NC 4.0: portfolio phi thương mại; quyền nguồn upstream chưa được xác minh độc lập.',
          'Ngày tin do publisher cung cấp, chưa xác minh độc lập; dữ liệu không phản ánh biến động sau thời kỳ này.',
          'Khu vực là quận/huyện lịch sử; không đoán mapping phường/xã. Tỉnh dưới 80 mẫu train không dự đoán.',
          'Training giới hạn 60.000 dòng lấy mẫu seed 42 để triển khai nhanh; thống kê thị trường dùng toàn bộ verified subset.',
          'Không dùng đất. Phòng thiếu dùng median train và cờ missing. V1 không dùng tầng, mặt tiền, đường hay pháp lý.',
          'Sai số trung bình không phải khoảng đảm bảo giá; kết quả không thay thế định giá chuyên nghiệp.'],
       'contribution_method':'Exact grouped Shapley across six fields in VND space, relative to a real train row; association not causation.'}
    archive=ROOT/'docs/archive/andy-v1';archive.mkdir(parents=True,exist_ok=True)
    for path in [ROOT/'vietnam-house-model.json',ROOT/'docs/vietnam-house-training-results.json',ROOT/'docs/vietnam-house-cleaning-report.json',ROOT/'data/vietnam-house-parity-fixtures.json']:
        dest=archive/path.name
        if not dest.exists():shutil.copy2(path,dest)
    legacy.dump(ROOT/'vietnam-house-model.json',artifact)
    fixtures=[{'input':inp(int(i)),'prediction_vnd':float(np.expm1(model.predict(p.transform(data.iloc[[i]])))[0])} for i in np.random.default_rng(142).choice(test,min(250,len(test)),replace=False)]
    legacy.dump(ROOT/'data/vietnam-house-parity-fixtures.json',fixtures)
    legacy.dump(ROOT/'docs/vietnam-house-training-results.json',{k:artifact[k] for k in ['model_name','trained_at','data_source','features','target','target_unit','metrics','model_comparison','split','limitations','model_review','quality_gate','train_rows','test_rows']})
    legacy.dump(ROOT/'docs/vietnam-house-cleaning-report.json',summary)
    print('EXPORTED',artifact['model_name'],artifact['metrics'],len(train),len(test),flush=True)
if __name__=='__main__':main()
