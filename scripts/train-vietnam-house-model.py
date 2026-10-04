"""Portfolio v1: published SALE CSV only, explicit VND units, reproducible holdout.

No website scraping. Raw inputs stay in cache; only model/aggregate metadata and
three real source examples are exported. Derived model modified by this project.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';DOCS=ROOT/'docs'
REF='andyvo1009/real-estate-in-vietnam'
NUMERIC=['log_area','bedrooms','bathrooms','bedrooms_missing','bathrooms_missing']
FEATURES=['province','area_name','area_m2','bedrooms','bathrooms']
MODEL_REVIEW={'status':'MODEL NOT SAFE TO PUBLISH','public_status':'NOT READY',
              'reason':'Currency units are explicit, but sale-only membership and total sale price semantics are not verified per record; no transaction classifier exists in this pipeline.',
              'report':'docs/vietnam-house-model-reconciliation.md','reviewed_on':'2026-10-04'}
def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
def slug(s):
    s=''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn').replace('đ','d')
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')
def vi_number(raw):
    # Vietnam comma decimals, dot-separated groups. Never guess bare currency.
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?',raw):raw=raw.replace('.','')
    elif '.' in raw and ',' in raw:return None
    try:return float(raw.replace(',','.'))
    except ValueError:return None
def money(raw):
    match=re.fullmatch(r'\s*([\d.,]+)\s+(tỷ|triệu)\s*',str(raw))
    if not match:return None
    amount=vi_number(match[1])
    return amount*(1e9 if match[2]=='tỷ' else 1e6) if amount is not None else None
def area(raw):
    match=re.fullmatch(r'\s*([\d.,]+)\s*m²\s*',str(raw))
    return vi_number(match[1]) if match else None
def coverage(count):return 'HIGH' if count>=1000 else 'MEDIUM' if count>=200 else 'LOW' if count>=30 else 'INSUFFICIENT'

class HousePreprocessor(BaseEstimator,TransformerMixin):
    """All imputation, scaling, vocabularies and rare-area groups fit on train."""
    def fit(self,x,y=None):
        self.medians_={c:float(x[c].median()) for c in ['bedrooms','bathrooms']}
        self.area_counts_=x.groupby(['province','area_name']).size().to_dict()
        self.encoder_=OneHotEncoder(handle_unknown='ignore',sparse_output=False,dtype=np.float32)
        self.encoder_.fit(self.cats(x))
        self.scaler_=StandardScaler().fit(self.nums(x))
        return self
    def cats(self,x):
        region=[name if self.area_counts_.get((p,name),0)>=30 else '__province__' for p,name in zip(x.province,x.area_name)]
        # Province and area form a composite nominal string, never ordinal codes.
        return pd.DataFrame({'province':x.province.to_numpy(),'area_name':[p+'|'+r for p,r in zip(x.province,region)]})
    def nums(self,x):
        return np.column_stack([np.log1p(x.area_m2.to_numpy()),
            x.bedrooms.fillna(self.medians_['bedrooms']),x.bathrooms.fillna(self.medians_['bathrooms']),
            x.bedrooms.isna().astype(int),x.bathrooms.isna().astype(int)])
    def transform(self,x):
        return np.asarray(np.column_stack([self.scaler_.transform(self.nums(x)),self.encoder_.transform(self.cats(x))]),dtype=np.float32)
    def artifact(self):
        return {'numeric_features':NUMERIC,'medians':self.medians_,'mean':self.scaler_.mean_.tolist(),'scale':self.scaler_.scale_.tolist(),
                'categorical_features':['province','area_name'],'categories':[c.tolist() for c in self.encoder_.categories_],
                'area_min_train_count':30,'unseen_area_policy':'Explicit province fallback using __province__ bucket; no other locality substituted.'}

def inverse(pred,transform):return np.maximum(0,np.expm1(pred) if transform=='log1p_vnd' else pred*1e9)
def metrics(y,p):
    return {'mae':float(mean_absolute_error(y,p)),'rmse':float(np.sqrt(mean_squared_error(y,p))),
            'r2':float(r2_score(y,p)),'mape':float(mean_absolute_percentage_error(y,p))}
def estimator(name):
    if name=='Median baseline':return DummyRegressor(strategy='median')
    if name=='Ridge':return Ridge(alpha=25)
    if name=='Random Forest':return RandomForestRegressor(n_estimators=100,max_depth=12,min_samples_leaf=10,max_features=.8,n_jobs=2,random_state=42)
    return GradientBoostingRegressor(n_estimators=160,max_depth=3,min_samples_leaf=35,learning_rate=.065,subsample=.85,random_state=42)
def tree_export(tree):
    t=tree.tree_
    return {'left':t.children_left.tolist(),'right':t.children_right.tolist(),'feature':t.feature.tolist(),
            'threshold':t.threshold.tolist(),'value':t.value[:,0,0].tolist()}
def export_model(m,name):
    if name=='Gradient Boosting':return {'kind':'gradient_boosting','base':float(m.init_.constant_[0,0]),'learning_rate':m.learning_rate,
                                         'trees':[tree_export(t[0]) for t in m.estimators_]}
    if name=='Random Forest':return {'kind':'random_forest','trees':[tree_export(t) for t in m.estimators_]}
    if name=='Ridge':return {'kind':'ridge','coefficients':m.coef_.tolist(),'intercept':float(m.intercept_)}
    return {'kind':'median','value':float(m.constant_[0,0])}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);args=parser.parse_args()
    DATA.mkdir(exist_ok=True);DOCS.mkdir(exist_ok=True)
    manifest=json.loads((DOCS/'vietnam-house-new-candidates-file-manifest.json').read_text(encoding='utf-8'))
    entry=next(r for r in manifest['files'] if r['dataset']==REF and r['filename']=='sale_real_estate.csv')
    source=args.source or Path(entry['local_cache_path'])
    raw=pd.read_csv(source,dtype=str,keep_default_na=False)
    sha=hashlib.sha256(source.read_bytes()).hexdigest();assert sha==entry['inspection_sha256']
    assert list(raw.columns)==['product_id','address','price','area','bedrooms_num','bathrooms_num']
    print('SALE source loaded:',len(raw),'explicit currency and area units; no timestamp/type fields',flush=True)
    mapping=json.loads((DOCS/'qmanhbeo-province-coverage-aliases.json').read_text(encoding='utf-8'))
    province_groups={('TP. Hồ Chí Minh' if name=='Hồ Chí Minh' else name):olds for name,olds in mapping['groups'].items()}
    aliases={old:current for current,olds in province_groups.items() for old in olds}
    aliases.update({'ho-chi-minh':'TP. Hồ Chí Minh','ba-ria-vung-tau':'TP. Hồ Chí Minh','thua-thien-hue':'Huế'})
    admin={'sources':mapping['sources'],'province_aliases':aliases,'current_provinces':list(province_groups),
           'ward_mapping':{},'policy':'Province-only verified administrative grouping; historical area names are retained, not mapped to current wards.'}
    dump(DATA/'vietnam-admin-aliases.json',admin)
    f=raw.drop_duplicates().copy();exact_removed=len(raw)-len(f)
    conflicts=f['product_id'].duplicated(keep=False);conflicting=int(conflicts.sum());f=f.loc[~conflicts].copy()
    f['source_record_1based']=f.index+1
    f['province_original']=f.address.map(lambda v:v.split(',')[-1].strip())
    f['province']=f.province_original.map(lambda v:aliases.get(slug(v),'Unknown'))
    f['area_name']=f.address.map(lambda v:re.sub(r'^[·\s]+','',v.rsplit(',',1)[0]).strip())
    f['total_price_vnd']=f.price.map(money);f['area_m2']=f.area.map(area)
    f['bedrooms']=pd.to_numeric(f.bedrooms_num,errors='coerce');f['bathrooms']=pd.to_numeric(f.bathrooms_num,errors='coerce')
    # Broad published v1 scope limits: exclude ambiguity, not arbitrary percentile cuts.
    conditions={
        'target_without_supported_unit':f.total_price_vnd.isna(),
        'area_without_supported_unit':f.area_m2.isna(),
        'nonpositive_price_or_area':f.total_price_vnd.le(0)|f.area_m2.le(0),
        'unknown_province_or_area':f.province.eq('Unknown')|f.area_name.eq(''),
        'invalid_room_count':f[['bedrooms','bathrooms']].isna().any(axis=1)|f[['bedrooms','bathrooms']].lt(0).any(axis=1)|f[['bedrooms','bathrooms']].gt(30).any(axis=1)|(f.bedrooms.mod(1).ne(0)|f.bathrooms.mod(1).ne(0)),
        'outside_v1_area_price_scope':~f.area_m2.between(5,10000)|~f.total_price_vnd.between(50e6,500e9),
        'extreme_unit_price_outside_scope':~(f.total_price_vnd/f.area_m2).between(1e5,2e9),
    }
    reason={};keep=pd.Series(True,index=f.index)
    for label,bad in conditions.items():
        removed=keep & bad;reason[label]=int(removed.sum());keep &= ~bad
    clean=f.loc[keep].copy().reset_index(drop=True)
    assert len(admin['current_provinces'])==34
    assert set(clean.province).issubset(admin['current_provinces']), 'Province categories must match coverage and UI names'
    # Source zeros may mean no room or unavailable; no invented property type.
    clean.loc[clean.bedrooms.eq(0),'bedrooms']=np.nan
    clean.loc[clean.bathrooms.eq(0),'bathrooms']=np.nan
    cleaning={'dataset':REF,'file':'sale_real_estate.csv','source_sha256':sha,'raw_rows':len(raw),'clean_rows':len(clean),
              'rows_removed':len(raw)-len(clean),'duplicates_removed':exact_removed,'conflicting_id_rows_removed':conflicting,
              'invalid_or_outside_scope_removed':reason,'raw_missing':{c:int(raw[c].str.strip().eq('').sum()) for c in raw},
              'clean_missing':{c:int(clean[c].isna().sum()) for c in FEATURES},
              'scope':{'area_m2':[5,10000],'total_price_vnd':[50e6,500e9],'price_per_m2_vnd':[1e5,2e9],'room_counts':[0,30]},
              'policy':'No percentile clipping; all ambiguous price strings and ID conflicts excluded. Original zeros for rooms treated as unspecified, not invented property categories.'}
    cleaning.update({'model_review':MODEL_REVIEW,'target_unit':'VND'})
    dump(DOCS/'vietnam-house-cleaning-report.json',cleaning)
    assert len(clean)>1000
    x=clean[FEATURES];y=clean.total_price_vnd.to_numpy(float)
    # Exact feature/target replicas across different IDs never cross the holdout.
    groups=pd.util.hash_pandas_object(clean[FEATURES+['total_price_vnd']],index=False).to_numpy()
    train,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(x,y,groups))
    assert set(groups[train]).isdisjoint(groups[test])
    folds=list(GroupKFold(n_splits=3).split(x.iloc[train],y[train],groups[train]))
    prepared=[]
    for a,b in folds:
        prep=HousePreprocessor().fit(x.iloc[train[a]])
        prepared.append((prep.transform(x.iloc[train[a]]),prep.transform(x.iloc[train[b]]),y[train[a]],y[train[b]]))
    comparisons=[]
    for name in ['Median baseline','Ridge','Random Forest','Gradient Boosting']:
        for transform in (['raw_vnd'] if name=='Median baseline' else ['raw_vnd','log1p_vnd']):
            started=time.time();scores=[]
            for xa,xb,ya,yb in prepared:
                m=estimator(name);m.fit(xa,np.log1p(ya) if transform=='log1p_vnd' else ya/1e9)
                scores.append(metrics(yb,inverse(m.predict(xb),transform)))
            result={'model_name':name,'target_transform':transform,'cv':{k:float(np.mean([r[k] for r in scores])) for k in scores[0]},
                    'cv_mae_std':float(np.std([r['mae'] for r in scores])), 'fit_seconds':round(time.time()-started,2)}
            comparisons.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    viable=[r for r in comparisons if r['model_name']!='Median baseline']
    best=min(viable,key=lambda r:r['cv']['mae'])
    candidates=[r for r in viable if r['cv']['mae']<=best['cv']['mae']*1.05 and r['cv']['rmse']<=best['cv']['rmse']*1.1]
    # Prefer compact GB/Ridge when effectively tied; final holdout is not selection data.
    selected=min(candidates,key=lambda r:({'Gradient Boosting':0,'Ridge':1,'Random Forest':2}[r['model_name']],r['cv_mae_std']))
    prep=HousePreprocessor().fit(x.iloc[train]);xa=prep.transform(x.iloc[train]);xb=prep.transform(x.iloc[test])
    final_models={}
    for result in comparisons:
        name=result['model_name'];transform=result['target_transform'];m=estimator(name)
        m.fit(xa,np.log1p(y[train]) if transform=='log1p_vnd' else y[train]/1e9)
        result['holdout']=metrics(y[test],inverse(m.predict(xb),transform))
        if result is selected:final_models['selected']=m
    model=final_models['selected'];pred=inverse(model.predict(xb),selected['target_transform'])
    training=clean.iloc[train];prov=[]
    for name in admin['current_provinces']:
        subset=training.loc[training.province.eq(name)];areas=[]
        for area_name,rows in subset.groupby('area_name'):
            areas.append({'name':area_name,'sample_count':len(rows),'coverage':coverage(len(rows)),
                          'median_price_per_m2_vnd':float((rows.total_price_vnd/rows.area_m2).median()),'supported':len(rows)>=30})
        prov.append({'name':name,'sample_count':len(subset),'coverage':coverage(len(subset)), 'supported':len(subset)>=80,
                     'median_price_per_m2_vnd':float((subset.total_price_vnd/subset.area_m2).median()) if len(subset) else None,
                     'areas':sorted(areas,key=lambda r:(-r['sample_count'],r['name']))})
    sample_indices=[]
    for province in ['Hà Nội','TP. Hồ Chí Minh','Đà Nẵng']:
        eligible=[i for i in test if clean.iloc[i].province==province and prep.area_counts_.get((province,clean.iloc[i].area_name),0)>=200
                  and pd.notna(clean.iloc[i].bedrooms) and pd.notna(clean.iloc[i].bathrooms) and 30<=clean.iloc[i].area_m2<=150]
        if eligible:sample_indices.append(eligible[0])
    def input_row(i):
        return {c:(None if pd.isna(clean.iloc[i][c]) else float(clean.iloc[i][c]) if c in ['area_m2','bedrooms','bathrooms'] else clean.iloc[i][c]) for c in FEATURES}
    samples=[{'input':input_row(i),'listed_price_vnd':float(y[i]),'prediction_vnd':float(inverse(model.predict(prep.transform(x.iloc[[i]])),selected['target_transform'])[0]),
              'source_listing_id':str(clean.iloc[i].product_id),'source_record_1based':int(clean.iloc[i].source_record_1based),
              'province_original':clean.iloc[i].province_original} for i in sample_indices]
    scatter_indices=np.random.default_rng(42).choice(len(test),min(180,len(test)),replace=False)
    artifact={'schema_version':1,'model_name':selected['model_name'],'model_version':'v1','trained_at':datetime.now(timezone.utc).isoformat(),
              'dataset_name':'Real Estate in Vietnam','dataset_source':'https://www.kaggle.com/datasets/'+REF,
              'data_source':{'publisher':'andyvo1009','dataset':REF,'version':1,'file':'sale_real_estate.csv','license':'Apache-2.0','source_sha256':sha,
                             'listing_kind':'sale asking price; file-level declaration; individual sale intent not independently verifiable without title/URL'},
              'data_start_date':None,'data_end_date':None,'data_date_info':{'publisher_period':'2025-02','listing_dates_verified':False,
                'display':'Tháng 02/2025 theo mô tả publisher; không có ngày từng tin','dataset_uploaded_at':'2025-02-12T10:01:01.477Z'},
              'sample_count':len(clean),'train_rows':len(train),'test_rows':len(test),'features':FEATURES,
              'target':'total_price_vnd','target_transform':selected['target_transform'],'preprocessing':prep.artifact(),'regressor':export_model(model,selected['model_name']),
              'metrics':selected['holdout'],'model_comparison':comparisons,'selection':'3-fold grouped CV on train only; compact deployment preferred within 5% MAE and 10% RMSE of best; holdout not used to choose.',
              'split':{'kind':'random_grouped_80_20','random_state':42,'train_rows':len(train),'test_rows':len(test),'groups_train':len(set(groups[train])),'groups_test':len(set(groups[test])),
                       'limitation':'No trustworthy listing date. Identical feature/price groups stay together; random holdout cannot assess future price changes.'},
              'coverage':prov,'cleaning':cleaning,'input_bounds':{'area_m2':[5,10000],'bedrooms':[1,30],'bathrooms':[1,30]},
              'reference_input':input_row(int(train[0])),'samples':samples,
              'scatter':[{'actual_vnd':float(y[test[j]]),'predicted_vnd':float(pred[j])} for j in scatter_indices],
              'limitations':['Giá rao bán, chưa xác minh là giao dịch hoàn tất. File SALE không có title, URL hoặc transaction_type để xác minh từng tin.',
                'Tháng dữ liệu do publisher công bố; không có timestamp từng tin và không realtime.',
                'Không có property type, tầng, mặt tiền, đường hoặc pháp lý; các loại tài sản có thể bị trộn.',
                'Tỉnh/thành được chuẩn hóa; khu vực là tên quận/huyện lịch sử, chưa mapping sang phường/xã hiện hành.',
                'Phòng bằng 0 trong nguồn được xem là chưa xác định, impute bằng median train và cờ missing.',
                'Coverage chỉ đếm dữ liệu train, chưa đảm bảo chất lượng dự đoán từng vùng. Tỉnh dưới 80 mẫu bị chặn.',
                'Định giá tham khảo portfolio; không phản ánh biến động sau thời kỳ dữ liệu hoặc thay thế định giá chuyên nghiệp.',
                'License Apache-2.0 do publisher khai báo; provenance upstream chưa được xác minh độc lập.'],
              'contribution_method':'Exact grouped Shapley over five input fields relative to a real train reference, computed after inverse transform in VND output space; explanatory association, not causality.'}
    artifact.update({'model_review':MODEL_REVIEW,'target_unit':'VND'})
    dump(ROOT/'vietnam-house-model.json',artifact)
    fixtures=[{'input':input_row(int(i)),'prediction_vnd':float(inverse(model.predict(prep.transform(x.iloc[[i]])),selected['target_transform'])[0])} for i in np.random.default_rng(142).choice(test,250,replace=False)]
    dump(DATA/'vietnam-house-parity-fixtures.json',fixtures)
    dump(DOCS/'vietnam-house-training-results.json',{'selected':selected,'comparisons':comparisons,'cleaning':cleaning,'split':artifact['split'],'samples':samples,
                                                   'artifact_bytes':(ROOT/'vietnam-house-model.json').stat().st_size,
                                                   'model_review':MODEL_REVIEW,'data_source':artifact['data_source'],
                                                   'features':FEATURES,'target':artifact['target'],'target_unit':'VND',
                                                   'trained_at':artifact['trained_at'],'data_date_info':artifact['data_date_info'],
                                                   'limitations':artifact['limitations']})
    print('EXPORT',json.dumps({'model':selected['model_name'],'transform':selected['target_transform'],'metrics':selected['holdout'],'train_rows':len(train),'test_rows':len(test),'samples':samples},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
