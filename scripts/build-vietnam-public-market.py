"""Aggregate retained local outputs only. No raw scan, network, or training."""
import sys,json,hashlib,unicodedata,math
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local-deps'));sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from shapely.geometry import shape
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p,obj,pretty=False):(ROOT/p).write_text(json.dumps(obj,ensure_ascii=False,indent=2 if pretty else None,separators=None if pretty else (',',':'),allow_nan=False),encoding='utf-8')
def norm(v):return ' '.join(unicodedata.normalize('NFC',str(v or '')).split()).casefold()
def uid(prefix,*parts):return prefix+hashlib.sha256('|'.join(norm(v) for v in parts).encode()).hexdigest()[:16]
def distance(a,b):
    lon1,lat1,lon2,lat2=map(math.radians,[a.x,a.y,b.x,b.y])
    return 6371*2*math.asin(min(1,math.sqrt(math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)))
def main():
    if read('data/vietnam-market-stats.json').get('schema_version')==3 and '--refresh-aggregates' not in sys.argv:
        print('Existing public aggregates reused; no retained-data rescan.');return
    index=read('data/vietnam-location-index.json');mapping=index['historical_to_canonical']
    apartment=pd.read_parquet(ROOT/'data/verified-vietnam-house-locations.parquet')
    apartment['property_type']='APARTMENT'
    extra=pd.read_parquet(ROOT/'data/verified-vietnam-extra-types.parquet')
    # Bounded review found unresolved subtype / sale-versus-rental ambiguity.
    # Disable the entire affected category; never remove just sampled failures.
    failed={'STREET_HOUSE':'Mẫu kiểm tra còn nhầm biệt thự với nhà mặt phố; chưa đủ dữ liệu xác minh loại.',
            'SHOPHOUSE':'Mẫu kiểm tra còn giá thuê trong mô tả đối chiếu giá bán; chưa đủ dữ liệu xác minh.'}
    labels={'APARTMENT':'Căn hộ chung cư','HOUSE':'Nhà riêng','STREET_HOUSE':'Nhà mặt phố','VILLA':'Biệt thự / Liền kề','LAND':'Đất / Đất nền','SHOPHOUSE':'Shophouse'}
    raw={'APARTMENT':762800,'HOUSE':1575536,'STREET_HOUSE':None,'VILLA':269782,'LAND':832766,'SHOPHOUSE':59860}
    df=pd.concat([apartment,extra[~extra.property_type.isin(failed)]],ignore_index=True).fillna('')
    locs=df[['province','area_name','ward_name']].drop_duplicates()
    lookup={(r.province,r.area_name,r.ward_name):mapping.get(uid('w_',r.province,r.area_name,r.ward_name),'') for r in locs.itertuples()}
    df['ward']=[lookup[(p,d,w)] for p,d,w in zip(df.province,df.area_name,df.ward_name)]
    df['sub_area']=[uid('s_',w,s) if w and norm(s) else '' for w,s in zip(df.ward,df.project_name)]
    subs={}
    for r in df[df.sub_area!=''][['province','ward','sub_area','project_name']].drop_duplicates().itertuples():
        subs.setdefault(r.sub_area,{'id':r.sub_area,'name':r.project_name,'label':r.project_name,'province':r.province,'ward':r.ward,'level':'SUB_AREA','type':'PROJECT'})
    index['sub_areas']=list(subs.values());thresholds={'SUB_AREA':20,'WARD':30,'PROVINCE':80};stats=[]
    def coverage(n,minimum):return 'INSUFFICIENT' if n<minimum else 'HIGH' if n>=1000 else 'MEDIUM' if n>=200 else 'LOW'
    for level,keys in [('PROVINCE',['province','property_type']),('WARD',['province','ward','property_type']),('SUB_AREA',['province','ward','sub_area','property_type'])]:
        subset=df if level=='PROVINCE' else df[df['ward' if level=='WARD' else 'sub_area']!='']
        for values,g in subset.groupby(keys,sort=True):
            d=dict(zip(keys,values));w=d.get('ward','');s=d.get('sub_area','');n=len(g);q=g.price_per_m2.quantile([.25,.5,.75]).tolist()
            stats.append({'stat_key':'|'.join([d['province'],w,s,d['property_type']]),'province':d['province'],'ward':w,'sub_area':s,'property_type':d['property_type'],
                'resolution_level':level,'sample_count':n,'coverage':coverage(n,thresholds[level]),'p25_price_per_m2':float(q[0]),'median_price_per_m2':float(q[1]),'p75_price_per_m2':float(q[2]),'latest_date':str(g.listing_date.max())})
    direct={r['stat_key']:r for r in stats};geo=read('data/vietnam-provinces.geojson')
    bycode={p['code']:p['id'] for p in index['provinces']}
    points={bycode[str(f['properties']['province_code'])]:shape(f['geometry']).representative_point() for f in geo['features']}
    regional=[];groups={key:g for key,g in df.groupby(['province','property_type']) if len(g)>=80}
    for p in index['provinces']:
        for kind in labels:
            if kind in failed or (p['id'],kind) in groups:continue
            nearest=sorted((distance(points[p['id']],points[donor]),donor,g) for (donor,t),g in groups.items() if t==kind)
            nearest=[row for row in nearest if row[0]<=500][:3]
            if len(nearest)<2:continue # At least two distinct nearby sources.
            vals=[];weights=[];donors=[];latest=[]
            total_weight=sum(1/max(d,25) for d,_,_ in nearest)
            for d,name,g in nearest:
                vals.append(g.price_per_m2.to_numpy());weights.append(np.full(len(g),1/(max(d,25)*len(g))))
                donors.append({'province':name,'property_type':kind,'sample_count':len(g),'distance_km':round(d,1),'province_weight':(1/max(d,25))/total_weight})
                latest.append(str(g.listing_date.max()))
            v=np.concatenate(vals);weight=np.concatenate(weights);order=np.argsort(v);v=v[order];cdf=np.cumsum(weight[order]);cdf/=cdf[-1]
            q=[float(v[min(len(v)-1,np.searchsorted(cdf,x))]) for x in [.25,.5,.75]]
            regional.append({'stat_key':'REGIONAL|'+p['id']+'|'+kind,'province':p['id'],'ward':'','sub_area':'','property_type':kind,'resolution_level':'REGIONAL_ESTIMATE',
                'sample_count':len(v),'coverage':'ESTIMATED','p25_price_per_m2':q[0],'median_price_per_m2':q[1],'p75_price_per_m2':q[2],'latest_date':max(latest),'donors':donors})
    gates=[]
    for kind,label in labels.items():
        rows=df[df.property_type==kind];eligible=[s for s in stats if s['property_type']==kind and s['coverage']!='INSUFFICIENT']
        gates.append({'code':kind,'label':label,'status':'DISABLED' if kind in failed else 'ENABLED','reason':failed.get(kind),
            'raw_rows':raw[kind],'raw_scope':'HOUSE and STREET_HOUSE share source category Nhà; no independent street raw count' if kind in ['HOUSE','STREET_HOUSE'] else 'source structured category',
            'candidate_rows':int((extra.property_type==kind).sum()) if kind!='APARTMENT' else len(apartment),'verified_rows':len(rows),
            'sample_review_size':72 if kind=='APARTMENT' else 12,'sample_findings':'previous 72/72 observations reused' if kind=='APARTMENT' else failed.get(kind,'12 observed samples: sale intent and total price plausible; not population accuracy'),
            'province_count':rows.province.nunique(),'ward_count':rows[rows.ward!=''].ward.nunique(),'sub_area_count':rows[rows.sub_area!=''].sub_area.nunique(),
            'province_eligible':sum(s['resolution_level']=='PROVINCE' for s in eligible),'ward_eligible':sum(s['resolution_level']=='WARD' for s in eligible),'sub_area_eligible':sum(s['resolution_level']=='SUB_AREA' for s in eligible)})
    index['property_types']=gates
    summary={'verified_rows':len(df),'canonical_provinces':34,'canonical_wards':3321,'known_sub_areas':len(subs),'supported_provinces':df.province.nunique(),
        'direct_wards':df[df.ward!=''].ward.nunique(),'enabled_types':sum(g['status']=='ENABLED' for g in gates),'mapped_rows':int((df.ward!='').sum()),
        'eligible_sub_area_stats':sum(s['resolution_level']=='SUB_AREA' and s['coverage']!='INSUFFICIENT' for s in stats),
        'eligible_ward_stats':sum(s['resolution_level']=='WARD' and s['coverage']!='INSUFFICIENT' for s in stats),
        'eligible_province_stats':sum(s['resolution_level']=='PROVINCE' and s['coverage']!='INSUFFICIENT' for s in stats),'regional_stats':len(regional)}
    generated=datetime.now(timezone.utc).isoformat()
    data={'schema_version':3,'mode':'VERIFIED MARKET ESTIMATE BETA','source':'TiniX AI','dataset':'tinixai/vietnam-real-estates','license':'CC-BY-NC-4.0',
        'source_url':'https://huggingface.co/datasets/tinixai/vietnam-real-estates','generated_at':generated,'verified_rows':len(df),'thresholds':thresholds,'summary':summary,'stats':stats,'regional_stats':regional,
        'regional_method':{'formula':'Each listing weight = 1 / (max(distance_km,25) * donor_province_listing_count). Weighted empirical CDF quantiles P25/P50/P75.',
          'donors':'Nearest up to 3 province polygon representative points within 500 km, same property type, >=80 listings, at least 2 donor provinces.',
          'limitation':'Geographic proximity does not establish market similarity; no urban/rural, legal or economic matching. Reference estimate only, no accuracy claim.'}}
    m=read('docs/archive/beta-location-v2/vietnam-house-model.json')
    m.update(schema_version=5,model_version='beta-public-v3',generated_at=generated,dataset_name='TiniX filtered sale subset: apartment, private house, villa/linked house, land',
        verified_rows=len(df),sample_count=len(df),data_start_date=str(df.listing_date.min())[:10],data_end_date=str(df.listing_date.max())[:10],property_types=[g['code'] for g in gates if g['status']=='ENABLED'],property_type_gates=gates,location_counts=summary,location_thresholds=thresholds)
    m['data_source']['files']=['data/verified-vietnam-house-locations.parquet','data/verified-vietnam-extra-types.parquet'];m['data_source']['file']='retained files (see files)'
    m['model_review']['report']='docs/vietnam-public-status.md'
    m['limitations']=['Ước tính thống kê BETA; không train ML và không có MAE/RMSE/R²/MAPE.',
       'Kiểm tra mẫu hữu hạn, không chứng minh độ chính xác toàn dataset. Gate ML gốc 194/200 vẫn FAIL; không đổi thành PASS.',
       'Giá rao bán, không phải giá giao dịch hoàn tất; không realtime. Ngày tin do publisher khai báo, chưa xác minh độc lập.',
       'TiniX AI · CC BY-NC 4.0: portfolio phi thương mại; nguồn upstream chưa được xác minh độc lập.',
       'Chỉ mapping các đơn vị cũ nhập toàn bộ có bằng chứng tại Hà Nội; đơn vị bị chia hoặc chưa mapping dùng tỉnh, không đoán phường.',
       'Ward/project và diện tích do publisher khai báo; chưa xác minh địa chỉ từng tin. Loại nhà/đất có thể khác diện tích đất, sử dụng hoặc sàn.',
       'Median không điều chỉnh pháp lý, đất thổ cư/nông nghiệp, mặt tiền, đường, tầng, phòng hoặc nội thất; LAND gồm các loại đất khác nhau.',
       'REGIONAL_ESTIMATE dùng phân vị có trọng số các tỉnh gần cùng loại; gần về địa lý không chứng minh tương đồng thị trường.',
       'P25/P75 là phân vị rao bán, không phải khoảng tin cậy. Giá cho diện tích khác chỉ thay theo công thức tuyến tính.']
    m['samples']=[];fixtures=[]
    def resolved(r):
        for w,s in [(r.ward,r.sub_area),(r.ward,''),('','')]:
            out=direct.get('|'.join([r.province,w,s,r.property_type]))
            if out and out['coverage']!='INSUFFICIENT':return out
        return next((x for x in regional if x['province']==r.province and x['property_type']==r.property_type),None)
    for r in df.sample(n=250,random_state=42).itertuples():
        s=resolved(r)
        if s:fixtures.append({'listing_id':r.listing_id,'input':{'province':r.province,'ward':r.ward,'sub_area':r.sub_area,'property_type':r.property_type,'area_m2':r.area_m2},'expected_vnd':r.area_m2*s['median_price_per_m2'],'stat_key':s['stat_key']})
    # Real retained records at direct mapped project, private-house ward, province.
    for kind in ['APARTMENT','HOUSE','LAND']:
        candidates=df[(df.property_type==kind)&(df.ward!='')] if kind!='LAND' else df[df.property_type==kind]
        for r in candidates.itertuples():
            s=resolved(r)
            if s and (kind!='APARTMENT' or s['resolution_level']=='SUB_AREA'):
                m['samples'].append({'input':{'province':r.province,'ward':r.ward,'sub_area':r.sub_area,'property_type':kind,'area_m2':r.area_m2},'listed_price_vnd':r.price_vnd});break
    write('data/vietnam-location-index.json',index);write('data/vietnam-market-stats.json',data);write('vietnam-house-model.json',m,True)
    write('data/vietnam-house-parity-fixtures.json',{'source':'250 real retained records seed42; Python quantile resolution, no ML','fixtures':fixtures})
    review=read('docs/vietnam-property-one-pass.json');review.update(status='COMPLETE — bounded spot-check, statistical BETA only',property_type_gates=gates,summary=summary)
    write('docs/vietnam-property-one-pass.json',review,True)
    print(json.dumps(summary));print(json.dumps(gates,ensure_ascii=False))
if __name__=='__main__':main()
