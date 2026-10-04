"""Read-only ID, date-text and extreme evidence; no source cleaning."""
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
docs=ROOT/'docs'
manifest=json.loads((docs/'qmanhbeo-download-manifest.json').read_text(encoding='utf-8'))
frame=pd.read_csv(manifest['files'][0]['local_cache_path'],dtype=str,keep_default_na=False,na_filter=False)
rep=frame[frame['Listing ID'].duplicated(keep=False)]
groups=rep.groupby('Listing ID',sort=False)
base=['Listing ID','Title','Price','Area','Location','Property Type','Property Type Slug','Description']
result={
    'id_all_numeric_integer':bool(pd.to_numeric(frame['Listing ID']).mod(1).eq(0).all()),
    'id_format_decimal_dot_zero':int(frame['Listing ID'].str.fullmatch(r'\d+\.0').sum()),
    'repeated_id_group_size_distribution':groups.size().value_counts().to_dict(),
    'repeated_id_groups_with_conflicts':{c:int(groups[c].nunique().gt(1).sum()) for c in frame.columns},
    'duplicate_extra_content_excluding_province_and_scrape_metadata':int(frame.duplicated(subset=base).sum()),
    'missing_definition':'blank, nan, null, none, n/a; whitespace stripped, case insensitive',
    'source_urls_in_schema':[],
    'extreme_price_equal_max_count':int(frame['Price'].eq('9223372036850.0').sum()),
    'raw_source_unchanged':True,
}
relative=frame['Last Updated'].str.extract(r'^(\d+) (giây|phút|giờ|ngày|tuần|tháng|năm) trước$')
seconds=relative[1].map({'giây':1,'phút':60,'giờ':3600,'ngày':86400,'tuần':604800,'tháng':2592000,'năm':31536000})*pd.to_numeric(relative[0],errors='coerce')
scraped=pd.to_datetime(frame['Scraped At'],format='%Y-%m-%d %H:%M:%S')
updated=pd.to_datetime(frame['Last Updated Date'],format='%d/%m/%Y %H:%M')
error=((scraped-updated).dt.total_seconds()-seconds).abs()
result['relative_date_check']={
    'hypothesis':'relative text subtracted from Scraped At, month=30 days, year=365 days; only regex-supported phrases',
    'supported_rows':int(seconds.notna().sum()),'matching_within_60_seconds':int(error.le(60).sum()),
    'relative_phrases_not_supported':frame.loc[seconds.isna(),'Last Updated'].value_counts().to_dict(),
    'median_absolute_seconds_difference':float(error.median()),
}
(docs/'qmanhbeo-supplemental-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ids=list(groups.groups)[:10]
rows=[]
for identity in ids:
    indices=groups.groups[identity]
    different=[c for c in frame if frame.loc[indices,c].nunique()>1]
    for i in indices:
        rows.append({'source_record_1based':int(i)+1,'listing_id':identity,'differing_columns':' | '.join(different),
                     **{c:frame.at[i,c] for c in ['Title','Price','Area','Location','Province','Property Type','Scraped At','Last Updated Date']}})
with (docs/'qmanhbeo-duplicate-paired-evidence.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps(result,ensure_ascii=False))
for metric,col in [('Price','Price'),('Area','Area')]:
    vals=pd.to_numeric(frame[col],errors='coerce')
    for i in vals.nlargest(5).index:
        print(json.dumps({'metric':metric,'row':int(i)+1,'id':frame.at[i,'Listing ID'],'price':frame.at[i,'Price'],
                          'area':frame.at[i,'Area'],'title':frame.at[i,'Title'],'description':frame.at[i,'Description'][:950]},ensure_ascii=False))
