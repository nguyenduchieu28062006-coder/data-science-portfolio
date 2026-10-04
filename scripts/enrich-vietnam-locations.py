"""Recover structured locations by exact existing IDs from a read-only audit cache.
No sale filtering, price reinterpretation, raw-file scan or training is performed.
Existing canonical records and audit database remain untouched.
"""
import sys, json, hashlib, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local-deps'))
sys.dont_write_bytecode = True
import duckdb
import pandas as pd

def norm(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).split())

def main():
    target = ROOT / 'data/verified-vietnam-house-locations.parquet'
    if target.exists():
        print('Reuse existing location enrichment; no cache read.')
        return
    df = pd.read_parquet(ROOT / 'data/verified-vietnam-house-sales.parquet')
    wanted = set(df.listing_id)
    keys = ['name','description','property_type_name','province_name','district_name','ward_name','price','area','bedroom_count','bathroom_count','floor_count']
    cache = Path.home() / 'AppData/Local/Temp/tinix-transaction-audit/ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f/read-only-audit-v1.duckdb'
    con = duckdb.connect(str(cache), read_only=True)
    # Only the enabled type; use already cached columns. Hash format is the
    # exact original canonical fingerprint, including default JSON spacing.
    cursor = con.execute('SELECT '+','.join(keys)+',project_name FROM audit_raw WHERE property_type_name=?', ['Căn hộ chung cư'])
    matches = {}; conflicts = set(); read = 0
    for batch in cursor.fetch_record_batch(4096):
        for r in batch.to_pylist():
            read += 1
            identity = hashlib.sha256(json.dumps([r[k] for k in keys], ensure_ascii=False).encode()).hexdigest()
            if identity not in wanted:
                continue
            location = (norm(r['ward_name']), norm(r['project_name']))
            if identity in matches and matches[identity] != location:
                conflicts.add(identity)
            else:
                matches[identity] = location
    assert wanted == matches.keys(), f'Missing exact matches: {len(wanted-matches.keys())}'
    df['ward_name'] = [matches[k][0] for k in df.listing_id]
    # Project is not part of the original dedup hash. Conflicting duplicate
    # projects must never be assigned by guesswork.
    df['project_name'] = [matches[k][1] if k not in conflicts else '' for k in df.listing_id]
    df.to_parquet(target, index=False, compression='zstd')
    report = {'method':'Exact original canonical SHA256 join; cached apartment columns only', 'canonical_rows':len(df),
              'exact_matches':len(matches),'cached_apartment_rows_read':read,'conflicting_project_ids':len(conflicts),
              'ward_rows':int((df.ward_name!='').sum()),'project_rows':int((df.project_name!='').sum()),
              'raw_files_read':False,'sale_rules_rerun':False,'training_performed':False,
              'limitation':'Ward and district labels are publisher historical locations, not verified current administrative boundaries. Projects are structured source fields; no NLP.'}
    (ROOT/'docs/vietnam-location-enrichment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))

if __name__ == '__main__':
    main()
