"""One read-only cached sale pass for additional types; reuse apartment output.
Writes a separate local retained file and bounded review sample; never trains.
"""
import sys,json,re,math,hashlib,unicodedata,random
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.local-deps'));sys.dont_write_bytecode=True;sys.stdout.reconfigure(encoding='utf-8')
import duckdb,pyarrow as pa,pyarrow.parquet as pq
from verified_sale_rules import verified_price,total_prices
from tinix_audit_rules import normalize
def norm(v):return ' '.join(unicodedata.normalize('NFC',str(v or '')).split())
def classify(title,source):
    t=norm(title).casefold();n=normalize(t)
    if not re.search(r'\b(?:bán|chuyển nhượng)\b',t) or re.search(r'\b(?:cho thuê|cần thuê|tìm thuê|cần mua|tìm mua|không bán|chưa bán)\b',t):return None
    if re.search(r'\b(?:bán (?:hoặc|và|hay) thuê|bán/cho thuê|nhà xưởng|khách sạn|nhà máy)\b',t):return None
    if source=='Nhà':
        street=bool(re.search(r'\bnhà (?:mặt phố|mặt tiền|mặt đường)\b',t))
        private=bool(re.search(r'\b(?:nhà riêng|hẻm|ngõ)\b',t))
        if street and private:return None
        return 'STREET_HOUSE' if street else 'HOUSE' if private else None
    if source=='Biệt thự/Nhà liền kề':return 'VILLA' if re.search(r'\b(?:biệt thự|liền kề)\b',t) else None
    if source=='Đất':return 'LAND' if re.search(r'\b(?:đất|lô|nền)\b',t) else None
    if source=='Shophouse':return 'SHOPHOUSE' if 'shophouse' in t else None
    return None
def price(title,description,structured):
    # Unresolved 1/2-digit shorthand is excluded, never truncated to billions.
    if re.search(r'\b(?:ty|ti)\s+\d{1,2}(?!\d)',normalize(title+' '+description)):return None
    return verified_price(title,description,structured)
def main():
    target=ROOT/'data/verified-vietnam-extra-types.parquet'
    if target.exists():print('Existing one-pass type output reused; no cache read.');return
    aliases=json.loads((ROOT/'data/vietnam-admin-aliases.json').read_text(encoding='utf-8'))
    pm=aliases['province_aliases'];pm.update({re.sub('[^a-z0-9]+','-',normalize(p)).strip('-'):p for p in aliases['current_provinces']})
    cache=Path.home()/'AppData/Local/Temp/tinix-transaction-audit/ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f/read-only-audit-v1.duckdb'
    con=duckdb.connect(str(cache),read_only=True);con.execute("SET threads=2")
    keys=['name','description','property_type_name','province_name','district_name','ward_name','price','area','bedroom_count','bathroom_count','floor_count']
    cursor=con.execute('SELECT '+','.join(keys)+",project_name,published_at FROM audit_raw WHERE property_type_name <> ? AND rule_label='SALE_HIGH_CONFIDENCE' AND area BETWEEN 15 AND 1500 AND try_cast(price AS DOUBLE) BETWEEN 200000000 AND 100000000000",['Căn hộ chung cư'])
    schema=pa.schema([(k,pa.string()) for k in ['listing_id','listing_date','province','area_name','ward_name','project_name','property_type']]+[(k,pa.float64()) for k in ['price_vnd','area_m2','price_per_m2']])
    seen=set();counts=Counter();reject=Counter();samples={};rng=random.Random(2704)
    with pq.ParquetWriter(target,schema,compression='zstd') as writer:
        for batch in cursor.to_arrow_reader(4096):
            output=[]
            for r in batch.to_pylist():
                counts['cached_prefilter_rows']+=1;kind=classify(r['name'] or '',r['property_type_name'])
                if not kind:reject['unresolved_type_or_primary_intent']+=1;continue
                amount=price(r['name'] or '',r['description'] or '',r['price'])
                if amount is None:reject['uncorroborated_or_shorthand_price']+=1;continue
                area=float(r['area']);ppm=amount/area
                if not math.isfinite(ppm) or not 2e6<=ppm<=500e6:reject['unit_scope']+=1;continue
                p=pm.get(re.sub('[^a-z0-9]+','-',normalize(r['province_name'])).strip('-'))
                date=str(r['published_at'] or '')
                if not p or not '2025-06-01'<=date[:10]<='2026-03-30':reject['location_or_date_scope']+=1;continue
                identity=hashlib.sha256(json.dumps([r[k] for k in keys],ensure_ascii=False).encode()).hexdigest()
                if identity in seen:reject['duplicate']+=1;continue
                seen.add(identity);counts[kind]+=1
                row={'listing_id':identity,'listing_date':date,'province':p,'area_name':norm(r['district_name']),'ward_name':norm(r['ward_name']),'project_name':'',
                     'property_type':kind,'price_vnd':amount,'area_m2':area,'price_per_m2':ppm}
                # Additional types do not get an inferred project/building.
                output.append(row)
                evidence={'listing_id':identity,'property_type':kind,'title':r['name'],'description_excerpt':(r['description'] or '')[:1400],
                          'price_vnd':amount,'text_prices_vnd':total_prices(r['name'],r['description']),'province':p,'ward':row['ward_name']}
                sample=samples.setdefault(kind,[])
                if len(sample)<12:sample.append(evidence)
                else:
                    i=rng.randrange(counts[kind])
                    if i<12:sample[i]=evidence
            if output:writer.write_table(pa.Table.from_pylist(output,schema=schema))
            if counts['cached_prefilter_rows']%100000<4096:print('Cached candidates',counts['cached_prefilter_rows'],'retained',len(seen),flush=True)
    report={'cached_passes':1,'raw_parquet_scans':0,'apartment_rows_reused':290282,'retained_by_type':{k:v for k,v in counts.items() if k!='cached_prefilter_rows'},
            'cached_prefilter_rows':counts['cached_prefilter_rows'],'rejected_reasons':dict(reject),'review_seed':2704,'sample_size_per_type':12,
            'status':'PENDING bounded semantic spot-check','scope':'Strict title type separation, accent-preserving sale intent, unresolved short billion suffix excluded, all text totals within 5% of structured VND. Apartment retained output reused unchanged.'}
    (ROOT/'docs/vietnam-property-one-pass.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/vietnam-property-one-pass-sample.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
