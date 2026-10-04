"""Aggregate the canonical verified subset, not raw listings; static fallback."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.local-deps'));sys.dont_write_bytecode=True
import pandas as pd
def main():
    existing=ROOT/'data/vietnam-market-stats.json'
    if existing.exists() and json.loads(existing.read_text(encoding='utf-8')).get('schema_version',0)>=2:
        print('Hierarchical statistics already exist; legacy district generator is retired.');return
    df=pd.read_parquet(ROOT/'data/verified-vietnam-house-sales.parquet');rows=[]
    for columns in [['province'],['province','property_type'],['province','area_name'],['province','area_name','property_type']]:
        for key,g in df.groupby(columns):
            if len(g)<30:continue
            key=key if isinstance(key,tuple) else (key,);scope=dict(zip(columns,key))
            rows.append({'province':scope['province'],'area':scope.get('area_name',''),'property_type':scope.get('property_type',''),
                         'sample_count':len(g),'median_price_vnd':float(g.price_vnd.median()),'median_price_per_m2':float(g.price_per_m2.median()),
                         'p25_price_per_m2':float(g.price_per_m2.quantile(.25)),'p75_price_per_m2':float(g.price_per_m2.quantile(.75)),
                         'latest_listing_date':g.listing_date.max(),'coverage':'HIGH' if len(g)>=1000 else 'MEDIUM' if len(g)>=200 else 'LOW',
                         'source':'TiniX AI verified sale subset','data_mode':'static_dataset'})
    out={'schema_version':1,'source':'TiniX AI','license':'CC-BY-NC-4.0','dataset':'tinixai/vietnam-real-estates','verified_rows':len(df),
         'thresholds':{'HIGH':1000,'MEDIUM':200,'LOW':30,'minimum':30},'live_connected':False,'stats':rows}
    (ROOT/'data/vietnam-market-stats.json').write_text(json.dumps(out,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    print('Static aggregates',len(rows),'verified records',len(df))
if __name__=='__main__':main()
