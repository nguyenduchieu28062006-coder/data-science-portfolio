"""Aggregate enriched VERIFIED records only; never read raw/cache or train."""
import sys,json,hashlib,unicodedata,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local-deps'));sys.dont_write_bytecode=True
import pandas as pd
def norm(v):return ' '.join(unicodedata.normalize('NFC',str(v or '')).split())
def uid(prefix,*parts):return prefix+hashlib.sha256('|'.join(norm(v).casefold() for v in parts).encode()).hexdigest()[:16]
def write(path,obj): (ROOT/path).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
def main():
    existing=ROOT/'data/vietnam-market-stats.json'
    if existing.exists() and json.loads(existing.read_text(encoding='utf-8')).get('schema_version',0)>=2:
        print('Hierarchical outputs already exist; reuse them, do not regenerate.');return
    df=pd.read_parquet(ROOT/'data/verified-vietnam-house-locations.parquet')
    thresholds={'SUB_AREA':20,'WARD':30,'PROVINCE':80}
    provinces={};wards={};subs={}
    for r in df[['province','area_name','ward_name','project_name']].drop_duplicates().to_dict('records'):
        p=r['province'];provinces[p]={'id':p,'name':p,'level':'PROVINCE'}
        w=norm(r['ward_name']);s=norm(r['project_name'])
        if not w or w.casefold() in {'null','none','n/a','nan'}:continue
        wid=uid('w_',p,r['area_name'],w)
        wards.setdefault(wid,{'id':wid,'name':w,'label':w+' · '+r['area_name'],'province':p,'historical_district':r['area_name'],'level':'WARD'})
        if not s or s.casefold() in {'null','none','n/a','nan'}:continue
        sid=uid('s_',wid,s)
        subs.setdefault(sid,{'id':sid,'name':s,'ward':wid,'province':p,'type':'PROJECT','level':'SUB_AREA'})
    df['ward']=df.apply(lambda r:uid('w_',r.province,r.area_name,r.ward_name) if norm(r.ward_name) else '',axis=1)
    df['ward']=df.ward.where(df.ward.isin(wards),'')
    df['sub_area']=df.apply(lambda r:uid('s_',r.ward,r.project_name) if r.ward and norm(r.project_name) else '',axis=1)
    df['sub_area']=df.sub_area.where(df.sub_area.isin(subs),'')
    df['property_type']='APARTMENT'
    stats=[];distributions={}
    for level,cols in [('PROVINCE',['province','property_type']),('WARD',['province','ward','property_type']),('SUB_AREA',['province','ward','sub_area','property_type'])]:
        part=df if level=='PROVINCE' else df[df[cols[-2]]!='']
        counts=[]
        for key,g in part.groupby(cols,sort=True):
            scope=dict(zip(cols,key));n=len(g);counts.append(n)
            row={**scope,'ward':scope.get('ward',''),'sub_area':scope.get('sub_area',''),'resolution_level':level,
                 'sample_count':n,'median_price_per_m2':round(float(g.price_per_m2.median()),2),
                 'p25_price_per_m2':round(float(g.price_per_m2.quantile(.25)),2),'p75_price_per_m2':round(float(g.price_per_m2.quantile(.75)),2),
                 'latest_date':g.listing_date.max()[:10],'coverage':'INSUFFICIENT' if n<thresholds[level] else 'HIGH' if n>=1000 else 'MEDIUM' if n>=200 else 'LOW'}
            row['stat_key']='|'.join([scope['province'],row['ward'],row['sub_area'],scope['property_type']])
            stats.append(row)
        series=pd.Series(counts)
        distributions[level]={'groups':len(counts),'supported':sum(n>=thresholds[level] for n in counts),'count_quantiles':{str(q):float(series.quantile(q)) for q in [0,.25,.5,.75,1]}}
    # Use the existing semantic sample, not a new audit. Other source types
    # remain disabled: failed gate, inadequate review or unsplit semantics.
    raw=json.loads((ROOT/'docs/vietnam-property-raw-counts.json').read_text(encoding='utf-8'))
    candidates=pd.read_parquet(ROOT/'docs/archive/tinix-rule-candidates.parquet')
    review=json.loads((ROOT/'docs/verified-vietnam-house-quality-review.json').read_text(encoding='utf-8'))['review']
    types=candidates.set_index('listing_id').property_type.to_dict();gates=[]
    for code,label,source in [('APARTMENT','Căn hộ chung cư','Căn hộ chung cư'),('HOUSE','Nhà (chưa phân biệt nhà riêng/mặt phố)','Nhà'),('STREET_HOUSE','Nhà mặt phố',None),('VILLA','Biệt thự / Nhà liền kề','Biệt thự/Nhà liền kề'),('LAND','Đất / Đất nền','Đất'),('SHOPHOUSE','Shophouse','Shophouse')]:
        sampled=[r for r in review if source and types.get(r['listing_id'])==source]
        n=len(sampled);correct=sum(r['result']=='PASS' for r in sampled)
        enabled=code=='APARTMENT'
        gates.append({'code':code,'label':label,'status':'ENABLED' if enabled else 'DISABLED','raw_rows':raw.get(source) if source else None,
                      'candidate_rows':int((candidates.property_type==source).sum()) if source else 0,'verified_rows':len(df) if enabled else 0,
                      'sample_review_size':n,'verification_score':correct/n if n else None,
                      'province_count':len(provinces) if enabled else 0,'ward_count':len(wards) if enabled else 0,'sub_area_count':len(subs) if enabled else 0,
                      'limitation':'72 apartment observations from original sample, not population accuracy or an ML quality gate' if enabled else 'No independently approved type subset; original mixed-type gate FAIL. Source categories may combine market segments; no guessed split.'})
    index={'schema_version':2,'location_basis':'Publisher historical ward/district labels, not current legal administrative boundaries',
           'normalization':'NFC, whitespace, case-insensitive exact match; opaque scoped IDs; no fuzzy or guessed ward aliases',
           'provinces':list(provinces.values()),'wards':list(wards.values()),'sub_areas':list(subs.values()),'property_types':gates}
    data={'schema_version':2,'mode':'VERIFIED MARKET ESTIMATE BETA','source':'TiniX AI','license':'CC-BY-NC-4.0','dataset':'tinixai/vietnam-real-estates',
          'verified_rows':len(df),'thresholds':thresholds,'coverage_thresholds':{'HIGH':1000,'MEDIUM':200},'live_connected':False,'stats':stats}
    write('data/vietnam-location-index.json',index);write('data/vietnam-market-stats.json',data)
    report={'verified_rows':len(df),'province_count':len(provinces),'ward_count':len(wards),'sub_area_count':len(subs),'project_count':len(subs),
            'thresholds':thresholds,'distribution':distributions,'property_types':gates,
            'threshold_reason':'Minimum 20 project / 30 ward / 80 province observations balances observed sparse group distribution; descriptive reliability limits only, not accuracy guarantees.',
            'missing_ward_rows':int((df.ward=='').sum()),'project_without_ward_rows':int(((df.ward=='')&(df.project_name!='')).sum()),
            'data_start':df.listing_date.min(),'data_latest_date':df.listing_date.max(),'training_performed':False}
    write('docs/vietnam-location-upgrade-report.json',report)
    m=json.loads((ROOT/'vietnam-house-model.json').read_text(encoding='utf-8'))
    m.update(schema_version=4,model_version='beta-location-v2',features=['province','ward','sub_area','property_type','area_m2'],
             location_index='data/vietnam-location-index.json',statistics='data/vietnam-market-stats.json',location_thresholds=thresholds,location_counts={k:report[k] for k in ['province_count','ward_count','sub_area_count']},property_type_gates=gates)
    m['coverage']=[]
    samples=[]
    for p in ['Hà Nội','TP. Hồ Chí Minh','Đà Nẵng']:
        row=df[(df.province==p)&(df.ward!='')].iloc[0]
        samples.append({'input':{k:row[k] for k in ['province','ward','sub_area','property_type','area_m2']},'listed_price_vnd':float(row.price_vnd)})
    m['samples']=samples;m['property_types']=['APARTMENT']
    m['limitations']+=['Phường/xã và dự án là trường có cấu trúc do publisher khai báo; chưa kiểm chứng ranh giới hành chính hiện hành hoặc địa chỉ từng listing.', 'Dự án thiếu ward hoặc có bản trùng xung đột không được đưa vào thống kê dự án. Phân vị P25/P75 không phải khoảng tin cậy.']
    write('vietnam-house-model.json',m)
    fixtures=[]
    for row in df.sample(250,random_state=42).to_dict('records'):
        point={k:row[k] for k in ['province','ward','sub_area','property_type','area_m2']}
        chosen=next((s for level in ['SUB_AREA','WARD','PROVINCE'] for s in stats if s['resolution_level']==level and s['province']==point['province'] and s['property_type']==point['property_type'] and (level=='PROVINCE' or s['ward']==point['ward']) and (level!='SUB_AREA' or s['sub_area']==point['sub_area']) and s['sample_count']>=thresholds[level]),None)
        if chosen:fixtures.append({'input':point,'expected_vnd':point['area_m2']*chosen['median_price_per_m2'],'stat_key':chosen['stat_key']})
    write('data/vietnam-house-parity-fixtures.json',{'model_version':m['model_version'],'fixtures':fixtures})
    print(json.dumps({k:v for k,v in report.items() if k!='property_types'},ensure_ascii=True))
if __name__=='__main__':main()
