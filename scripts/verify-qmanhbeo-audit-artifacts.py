"""Verify audit evidence integrity and source immutability; no cleaning."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/'docs'
def read_csv(name):
    with (DOCS/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
s=json.loads((DOCS/'qmanhbeo-source-audit-summary.json').read_text(encoding='utf-8'))
manifest=json.loads((DOCS/'qmanhbeo-download-manifest.json').read_text(encoding='utf-8'))
n=s['row_count']
assert n==236226 and s['file_count']==1 and len(s['schema_columns'])==28
assert len(s['missing_counts'])==28
assert sum(r['row_count'] for r in s['transaction_labels'])==n
assert sum(r['row_count'] for r in s['target_labels_under_million_hypothesis'])==n
assert sum(r['row_count'] for r in s['property_types'])==n
for filename,length in [('qmanhbeo-province-original-coverage.csv',63),('qmanhbeo-province-current-coverage.csv',34)]:
    rows=read_csv(filename);assert len(rows)==length and sum(int(r['row_count']) for r in rows)==n
monthly=read_csv('qmanhbeo-monthly-counts.csv')
for col in ('Scraped At','Last Updated Date'):
    assert sum(int(r['row_count']) for r in monthly if r['date_column']==col)==n
for name,length in [('qmanhbeo-text-price-audit-1500.csv',1500),('qmanhbeo-text-price-unconditional-2000.csv',2000)]:
    rows=read_csv(name);assert len(rows)==length
    assert len({r['source_record_1based'] for r in rows})==length
sample=read_csv('qmanhbeo-transaction-audit-sample.csv')
manual=read_csv('qmanhbeo-transaction-manual-review.csv')
assert len(sample)==len(manual)==300
assert Counter(r['rule_label'] for r in sample)=={'SALE_HIGH_CONFIDENCE':100,'RENT_HIGH_CONFIDENCE':100,'AMBIGUOUS':100}
assert [(r['source_record_1based'],r['listing_id'],r['rule_label']) for r in sample]==[(r['source_record_1based'],r['listing_id'],r['rule_label']) for r in manual]
price_manual=read_csv('qmanhbeo-price-manual-diagnostic-review.csv')
assert len(price_manual)==30 and price_manual[0]['source_record_1based']=='80761'
confirmed=[r for r in price_manual if r['finding']=='PRICE_SCALE_INCONSISTENCY']
assert len(confirmed)==16
for r in confirmed:
    factor=float(r['price_raw'])*1e6/float(r['text_reference_vnd_v4'])
    assert any(abs(factor-f)/f<.02 for f in (10,100)),(r['source_record_1based'],factor)
rules=ROOT/'scripts/qmanh_audit_rules.py'
assert hashlib.sha256(rules.read_bytes()).hexdigest()==s['rule_sha256']
original=Path(manifest['files'][0]['local_cache_path'])
assert original.stat().st_size==manifest['files'][0]['actual_raw_bytes']
hasher=hashlib.sha256()
with original.open('rb') as f:
    while chunk:=f.read(1024*1024):hasher.update(chunk)
assert hasher.hexdigest()==manifest['files'][0]['sha256']==s['source_sha256']==s['source_hash_after_audit']
assert s['raw_values_modified']==s['raw_rows_removed']==0
for path in DOCS.glob('qmanhbeo-*.json'):json.loads(path.read_text(encoding='utf-8'))
report=(DOCS/'qmanhbeo-source-audit-report.md').read_text(encoding='utf-8')
assert '46.887' not in report and '1387144' not in report
assert '30.003' in report and '1493810' in report
assert s['rule_version']=='qmanh-source-audit-v5'
print(json.dumps({'checks':'PASS','source_rows':n,'schema_columns':28,'source_sha256':hasher.hexdigest(),
                  'raw_source_unchanged':True,'manual_transaction_records':300,'manual_price_diagnostics':30,
                  'rule_version':s['rule_version'],'training_performed':False},ensure_ascii=False))
