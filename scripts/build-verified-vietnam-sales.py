"""One streaming pass over local TiniX Parquet; no downloads or model fitting."""
import hashlib,json,math,random,re,sys
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local-deps'))
sys.stdout.reconfigure(encoding='utf-8');sys.dont_write_bytecode=True
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from verified_sale_rules import sale_intent,verified_price,total_prices
from tinix_audit_rules import normalize

def main():
    manifest=json.loads((ROOT/'docs/tinix-download-manifest.json').read_text(encoding='utf-8'))
    admin=json.loads((ROOT/'data/vietnam-admin-aliases.json').read_text(encoding='utf-8'))
    def slug(s):return re.sub(r'[^a-z0-9]+','-',normalize(s)).strip('-')
    aliases=admin['province_aliases'];aliases.update({slug(p):p for p in admin['current_provinces']})
    paths=[r['local_cache_path'] for r in manifest['files']];assert all(Path(p).is_file() for p in paths)
    raw=sum(pq.ParquetFile(p).metadata.num_rows for p in paths)
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=2')
    names=','.join("'"+p.replace("'","''")+"'" for p in paths)
    sql=f"""SELECT *,parse_filename(filename) AS shard FROM read_parquet([{names}],filename=true,file_row_number=true)
       WHERE property_type_name IN ('Nhà','Nhà riêng','Căn hộ chung cư','Nhà mặt phố','Biệt thự/Nhà liền kề')
       AND regexp_matches(replace(strip_accents(lower(coalesce(name,''))),'đ','d'),'\\b(ban|chuyen nhuong)\\b')
       AND area BETWEEN 15 AND 1500 AND try_cast(price AS DOUBLE) BETWEEN 200000000 AND 100000000000
       AND isfinite(area) AND isfinite(try_cast(price AS DOUBLE))"""
    schema=pa.schema([('listing_id',pa.string()),('listing_date',pa.string()),('province',pa.string()),('area_name',pa.string()),
      ('property_type',pa.string()),('price_vnd',pa.float64()),('area_m2',pa.float64()),('price_per_m2',pa.float64()),
      ('bedrooms',pa.float64()),('bathrooms',pa.float64()),('floors',pa.float64()),('frontage_m',pa.float64()),('road_width_m',pa.float64()),('source',pa.string())])
    target=ROOT/'data/verified-vietnam-house-sales.parquet'
    assert not target.exists(),'Canonical output already exists; inspect and reuse rather than rescan.'
    rng=random.Random(42);sample=[];seen=set();counts=Counter();accepted=0
    start=None;end=None
    def optional(value,maximum,integer=False):
        if value is None or not math.isfinite(value) or value<=0 or value>maximum:return None
        if integer and not float(value).is_integer():return None
        return float(value)
    with pq.ParquetWriter(target,schema,compression='zstd') as writer:
        for batch in con.execute(sql).fetch_record_batch(4096):
            output=[]
            for r in batch.to_pylist():
                counts['prefilter_candidates']+=1
                if not sale_intent(r['name']):counts['intent']+=1;continue
                price=verified_price(r['name'],r['description'],r['price'])
                if price is None:counts['unverified_total_price']+=1;continue
                area=float(r['area']);unit=price/area
                if not 2e6<=unit<=500e6:counts['unit_price_scope']+=1;continue
                province=aliases.get(slug(r['province_name']))
                if not province:counts['unknown_province']+=1;continue
                # District context remains historical; ward names are never remapped by guesswork.
                area_name=str(r['district_name'] or '').strip()
                if not area_name or len(area_name)>100:counts['unknown_area']+=1;continue
                try:
                    date=datetime.fromisoformat(str(r['published_at']).replace('Z','+00:00')).isoformat()
                    if not '2025-06-01'<=date[:10]<='2026-03-31':raise ValueError()
                except ValueError:counts['date']+=1;continue
                fingerprint=hashlib.sha256(json.dumps([r.get(k) for k in ['name','description','property_type_name','province_name','district_name','ward_name','price','area','bedroom_count','bathroom_count','floor_count']],ensure_ascii=False).encode()).hexdigest()
                if fingerprint in seen:counts['duplicates']+=1;continue
                seen.add(fingerprint)
                row={'listing_id':fingerprint,'listing_date':date,'province':province,'area_name':area_name,'property_type':r['property_type_name'],
                     'price_vnd':price,'area_m2':area,'price_per_m2':unit,'bedrooms':optional(r['bedroom_count'],20,True),
                     'bathrooms':optional(r['bathroom_count'],20,True),'floors':optional(r['floor_count'],30,True),
                     'frontage_m':optional(r['frontage_width'],100),'road_width_m':optional(r['road_width'],100),'source':'TiniX AI'}
                output.append(row);accepted+=1
                start=min(start or date,date);end=max(end or date,date)
                evidence={'listing_id':fingerprint,'title':r['name'],'description':r['description'],'structured_price_vnd':price,
                          'text_prices_vnd':total_prices(r['name'],r['description']),'source_shard':r['shard'],'source_row':r['file_row_number']}
                if len(sample)<200:sample.append(evidence)
                else:
                    index=rng.randrange(accepted)
                    if index<200:sample[index]=evidence
            if output:writer.write_table(pa.Table.from_pylist(output,schema=schema))
            if counts['prefilter_candidates']%100000<4096:print('Candidates',counts['prefilter_candidates'],'verified',accepted,flush=True)
    report={'dataset':manifest['dataset'],'revision':manifest['revision'],'source':'TiniX AI','license':'CC-BY-NC-4.0',
            'raw_rows':raw,'verified_rows':accepted,'rejected_rows':raw-accepted,'date_start':start,'date_end':end,'reasons':dict(counts),
            'scope':{'area_m2':[15,1500],'price_vnd':[2e8,1e11],'price_per_m2':[2e6,5e8]},
            'quality_gate':{'status':'PENDING','sample_count':len(sample),'seed':42,'method':'Uniform reservoir sample of retained records; semantic review required before training'},
            'date_limitation':'Publisher listing timestamps, not independently validated collection times; no timezone inferred.',
            'dedup':'Exact title/description/location/price/physical-feature fingerprint excluding date; ID is derived, not source listing ID.'}
    (ROOT/'docs/verified-vietnam-house-data-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/verified-vietnam-house-quality-sample.json').write_text(json.dumps(sample,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
