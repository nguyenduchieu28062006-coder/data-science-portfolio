"""Full-file source audit. Original CSV is never modified or cleaned.

The small derived outputs are audit evidence, not a training dataset or features.
Requires existing pandas/numpy; parsing and transaction rules are independent
from TiniX, Health, Data Analyzer and prediction code.
"""
from collections import Counter
from datetime import date
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import time

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
from qmanh_audit_rules import classify, parse_prices, text_reference, audit_target, normalize, RULE_VERSION

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs'
CACHE = Path(tempfile.gettempdir())/'qmanhbeo-v3-source-audit-20261004'
SEED = 42
LABELS = ['SALE_HIGH_CONFIDENCE', 'RENT_HIGH_CONFIDENCE', 'AMBIGUOUS']
MISSING = {'', 'nan', 'null', 'none', 'n/a'}
NUMERIC = ['Price','Area','Listing ID','Width','Length','Bedrooms','Bathrooms','Floors','Alley Width','Latitude','Longitude','Agent Listing Count']


def csv_write(name, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else [])
    with (DOCS/name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def distribution(series):
    values = series[np.isfinite(series)]
    q = values.quantile([.01,.05,.25,.50,.75,.95,.99]).tolist() if len(values) else [None]*7
    return {'finite_count':len(values), 'undefined_or_nonfinite_count':len(series)-len(values),
            'min':float(values.min()) if len(values) else None,
            **dict(zip(['p1','p5','p25','p50','p75','p95','p99'], q)),
            'max':float(values.max()) if len(values) else None}


def current_location(raw, lookup):
    token = normalize(raw.split(',')[-1]).replace('(moi)', '').strip()
    for prefix in ('thanh pho ', 'tinh ', 'tp. ', 'tp ', 'tp.'):
        if token.startswith(prefix):
            token = token[len(prefix):].strip()
            break
    if token in ('ho chi minh', 'hcm', 'tphcm'):
        token = 'tp-ho-chi-minh'
    else:
        token = '-'.join(token.split())
    if token == 'hue': token = 'thua-thien-hue'
    return lookup.get(token, 'Unknown')


def main():
    started = time.time()
    manifest = json.loads((DOCS/'qmanhbeo-download-manifest.json').read_text(encoding='utf-8'))
    entry = manifest['files'][0]
    path = Path(entry['local_cache_path'])
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert original_hash == entry['sha256']
    print('Reading every CSV record, retaining raw strings', flush=True)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding='utf-8-sig')
    assert len(frame.columns) == 28
    count = len(frame)
    summary = {'dataset':manifest['dataset'], 'version':3, 'file_count':manifest['file_count'],
               'source_sha256':original_hash, 'review_date':'2026-10-04', 'row_count':count,
               'schema_columns':list(frame.columns), 'parser_dtypes':{k:str(frame[k].dtype) for k in frame},
               'seed':SEED, 'rule_version':RULE_VERSION,
               'rule_sha256':hashlib.sha256((ROOT/'scripts/qmanh_audit_rules.py').read_bytes()).hexdigest(),
               'raw_values_modified':0, 'raw_rows_removed':0, 'training_performed':False, 'model_created':False,
               'sampling':'random.Random(42), without replacement per audit class; separate all-row and parse-eligible price samples'}
    missing = {key:frame[key].str.strip().str.lower().isin(MISSING) for key in frame}
    summary['missing_counts'] = {k:int(v.sum()) for k,v in missing.items()}
    summary['blank_counts'] = {k:int(frame[k].str.strip().eq('').sum()) for k in frame}
    summary['all_fields_blank_count'] = int(pd.concat(missing.values(), axis=1).all(axis=1).sum())
    values = {key:pd.to_numeric(frame[key], errors='coerce') for key in NUMERIC}
    summary['numeric_columns'] = {key:{'missing_or_unparseable':int(s.isna().sum()),
                                     'unparseable_nonmissing':int((s.isna() & ~missing[key]).sum()),
                                     'nonfinite_nonnull':int((s.notna() & ~np.isfinite(s)).sum()),
                                     'nonpositive':int((s<=0).sum()), 'zero':int(s.eq(0).sum()),
                                     'min':float(s.min()) if s.notna().any() else None,
                                     'max':float(s.max()) if s.notna().any() else None} for key,s in values.items()}
    exact = frame.duplicated(keep=False)
    duplicate_extra = int(frame.duplicated().sum())
    summary['duplicates'] = {'exact_extra_rows':duplicate_extra, 'exact_rows_in_groups':int(exact.sum()),
                             'listing_id_unique_nonmissing':int(frame.loc[~missing['Listing ID'],'Listing ID'].nunique()),
                             'listing_id_repeated_extra':int(frame.loc[~missing['Listing ID'],'Listing ID'].duplicated().sum()),
                             'listing_id_rows_in_repeat_groups':int(frame.loc[~missing['Listing ID'],'Listing ID'].duplicated(keep=False).sum())}
    stable = ['Title','Price','Area','Location','Listing ID','Property Type','Province','Property Type Slug','Description']
    summary['duplicates']['same_listing_core_extra'] = int(frame.duplicated(subset=stable).sum())
    duplicate_indices = frame.index[frame['Listing ID'].duplicated(keep=False)].tolist()[:20]
    csv_write('qmanhbeo-duplicate-examples.csv', [audit_row(frame,i) for i in duplicate_indices])
    summary['dates'] = {}
    monthly = []
    parsed_dates = {}
    for key,fmt in [('Scraped At','%Y-%m-%d %H:%M:%S'),('Last Updated Date','%d/%m/%Y %H:%M')]:
        s = pd.to_datetime(frame[key], format=fmt, errors='coerce')
        parsed_dates[key] = s
        summary['dates'][key] = {'min':s.min().isoformat() if s.notna().any() else None,
                                'max':s.max().isoformat() if s.notna().any() else None,
                                'null_or_blank':int(missing[key].sum()), 'invalid_nonmissing':int((s.isna() & ~missing[key]).sum()),
                                'future_after_review_day':int((s>=pd.Timestamp('2026-10-05')).sum()),
                                'future_after_version_upload_day':int((s>=pd.Timestamp('2025-10-01')).sum()),
                                'timezone_in_source':None}
        for month,n in s.dt.strftime('%Y-%m').fillna('INVALID').value_counts().sort_index().items():
            monthly.append({'date_column':key,'month':month,'row_count':int(n),'percentage':n*100/count})
    summary['dates']['updated_after_scraped'] = int((parsed_dates['Last Updated Date']>parsed_dates['Scraped At']).sum())
    summary['last_updated_relative_text_top20'] = frame['Last Updated'].value_counts().head(20).to_dict()
    csv_write('qmanhbeo-monthly-counts.csv', monthly)
    print(f'Counted {count:,} records; computing coverage and distributions', flush=True)
    aliases = json.loads((DOCS/'qmanhbeo-province-coverage-aliases.json').read_text(encoding='utf-8'))
    lookup = {slug:name for name,slugs in aliases['groups'].items() for slug in slugs}
    assert len(lookup)==63 and len(aliases['groups'])==34
    province_current = frame['Province'].map(lookup).fillna('Unknown')
    location_current = frame['Location'].map(lambda x:current_location(x,lookup))
    summary['coverage'] = {'original_province_labels':int(frame['Province'].nunique()),
                            'current_units_with_rows':int(province_current[province_current!='Unknown'].nunique()),
                            'unknown_province_rows':int(province_current.eq('Unknown').sum()),
                            'location_unknown_rows':int(location_current.eq('Unknown').sum()),
                            'province_location_disagreement_rows':int(((location_current!=province_current)&location_current.ne('Unknown')).sum())}
    original_coverage = [{'province_original':p,'row_count':int(n),'percentage':n*100/count,'province_current_for_coverage':lookup.get(p,'Unknown')}
                         for p,n in frame['Province'].value_counts().items()]
    csv_write('qmanhbeo-province-original-coverage.csv', original_coverage)
    current_coverage = []
    for name in aliases['groups']:
        n = int(province_current.eq(name).sum())
        assessment = 'Chưa đủ mẫu' if n<100 else 'Rất hạn chế' if n<500 else 'Có mẫu; cần kiểm định theo loại và phường' if n<2000 else 'Nhiều mẫu thô; chưa chứng minh model hỗ trợ'
        current_coverage.append({'province':name,'row_count':n,'percentage':n*100/count,'coverage_assessment':assessment,
                                 'original_labels':' | '.join(aliases['groups'][name])})
    csv_write('qmanhbeo-province-current-coverage.csv', current_coverage)
    summary['coverage']['original_counts'] = original_coverage
    summary['coverage']['current_counts'] = current_coverage
    mismatch_idx = frame.index[(location_current!=province_current)&location_current.ne('Unknown')].tolist()[:20]
    csv_write('qmanhbeo-location-disagreements.csv', [audit_row(frame,i, {'province_current_audit':province_current[i],'location_current_audit':location_current[i]}) for i in mismatch_idx])
    ratio = values['Price'].div(values['Area']).where((values['Area']>0)&np.isfinite(values['Area']))
    summary['distributions_raw'] = {'Price':distribution(values['Price']), 'Area':distribution(values['Area']),
                                   'Price_div_Area_raw':distribution(ratio)}
    props = []
    for property_type,indices in frame.groupby('Property Type',sort=True).groups.items():
        props.append({'property_type':property_type,'row_count':len(indices),
                      'median_price_raw':float(values['Price'].loc[indices].median()),
                      'median_area_m2':float(values['Area'].loc[indices].median()),
                      'price_missing':int(values['Price'].loc[indices].isna().sum()),
                      'price_nonpositive':int(values['Price'].loc[indices].le(0).sum()),
                      'area_missing':int(values['Area'].loc[indices].isna().sum()),
                      'area_nonpositive':int(values['Area'].loc[indices].le(0).sum()),
                      'property_type_slugs':' | '.join(frame.loc[indices,'Property Type Slug'].unique())})
    summary['property_types'] = props
    csv_write('qmanhbeo-property-type-summary.csv', props)
    extremes = []
    for metric,series in [('Price',values['Price']),('Area',values['Area']),('Price_div_Area',ratio),('Width',values['Width']),('Alley Width',values['Alley Width'])]:
        for direction,inds in [('largest',series[np.isfinite(series)].nlargest(5).index),('smallest',series[np.isfinite(series)].nsmallest(5).index)]:
            extremes.extend(audit_row(frame,i,{'metric':metric,'direction':direction,'value':float(series[i])}) for i in inds)
    csv_write('qmanhbeo-extreme-examples.csv', extremes)
    labels = []
    reasons = []
    target_labels = []
    references = []
    reference_sources = []
    candidates_all = []
    for i,(title,description) in enumerate(zip(frame['Title'],frame['Description'])):
        label,reason = classify(title,description)
        area = float(values['Area'][i]) if pd.notna(values['Area'][i]) else None
        price = float(values['Price'][i]) if pd.notna(values['Price'][i]) else None
        candidates = parse_prices(title,description,area)
        reference,refreason = text_reference(candidates)
        target,target_reason = audit_target(price,area,candidates)
        labels.append(label);reasons.append(reason);target_labels.append(target)
        references.append(reference);reference_sources.append(refreason);candidates_all.append(candidates)
        if (i+1)%25000==0: print(f'Text audit {i+1:,}/{count:,}',flush=True)
    summary['transaction_labels'] = [{ 'label':k,'row_count':v,'percentage':v*100/count} for k,v in Counter(labels).items()]
    summary['transaction_reasons'] = dict(Counter(reasons))
    summary['target_labels_under_million_hypothesis'] = [{'label':k,'row_count':v,'percentage':v*100/count} for k,v in Counter(target_labels).items()]
    summary['text_reference_counts'] = dict(Counter(reference_sources))
    transaction_samples = []
    transaction_full = []
    previous_samples = None
    review_cache = CACHE/'transaction-review-full-text.json'
    if review_cache.exists():
        previous_samples = json.loads(review_cache.read_text(encoding='utf-8'))
    for label in LABELS:
        indices = [i for i,v in enumerate(labels) if v==label]
        sampled = random.Random(SEED).sample(indices, min(100,len(indices)))
        if label in ('SALE_HIGH_CONFIDENCE','AMBIGUOUS') and previous_samples:
            reused = [r['source_record_1based']-1 for r in previous_samples if r['rule_label']==label
                      and labels[r['source_record_1based']-1]==label]
            if len(reused)==100: sampled=reused
        for rank,i in enumerate(sampled,1):
            extra = {'rule_label':label,'rule_reason':reasons[i],'review_group_rank':rank}
            transaction_samples.append(audit_row(frame,i,extra))
            transaction_full.append(audit_row(frame,i,extra,full=True))
    csv_write('qmanhbeo-transaction-audit-sample.csv', transaction_samples)
    (CACHE/'transaction-review-full-text.json').write_text(json.dumps(transaction_full,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary['transaction_sample_counts'] = dict(Counter(r['rule_label'] for r in transaction_samples))
    summary['transaction_review_sample_note'] = 'SALE and AMBIGUOUS samples retained from seeded v2 diagnostic strata when still in same v3 label; RENT freshly sampled from v3 primary rental-offer stratum. AMBIGUOUS review is diagnostic, not an unbiased estimate of the expanded v3 stratum.'
    eligible = [i for i,reference in enumerate(references) if reference is not None and pd.notna(values['Price'][i]) and values['Price'][i]>0]
    eligible_set = set(eligible)
    required = random.Random(17042).sample(eligible,min(1500,len(eligible)))
    all_row_sample = random.Random(SEED).sample(list(range(count)),min(2000,count))
    sets = {'parse_eligible_1500':required,'unconditional_2000':all_row_sample,'all_parse_eligible':eligible}
    summary['price_comparisons'] = {}
    for name,indices in sets.items():
        comparable = [i for i in indices if i in eligible_set] if name=='unconditional_2000' else indices
        stats = {'sample_rows':len(indices),'comparable_rows':len(comparable),'interpretations':{}}
        for interpretation,multiplier in [('million_vnd_total',1e6),('billion_vnd_total',1e9),('vnd_total',1.0),
                                           ('hundred_thousand_vnd_total',1e5),('ten_thousand_vnd_total',1e4)]:
            errors = [abs(float(values['Price'][i])*multiplier-references[i])/references[i] for i in comparable]
            stats['interpretations'][interpretation] = {str(tol):{'matched':sum(e<=tol for e in errors),'denominator':len(errors),'match_rate':sum(e<=tol for e in errors)/len(errors) if errors else None} for tol in (.01,.02,.05)}
        summary['price_comparisons'][name] = stats
    ratio_factors = Counter()
    exact_reference_rows = []
    for i in eligible:
        preferred = [x for x in candidates_all[i] if x['source']=='title'] or candidates_all[i]
        if not any(x['approximate'] for x in preferred): exact_reference_rows.append(i)
        factor = float(values['Price'][i])*1e6/references[i]
        for scale in (.001,.01,.1,1,10,100,1000):
            if abs(factor-scale)/scale<=.02:
                ratio_factors[str(scale)]+=1
                break
        else: ratio_factors['other']+=1
    summary['stored_million_div_text_total_factors_2pct'] = dict(ratio_factors)
    summary['exact_reference_million_matches'] = {str(tol):{'matched':sum(abs(float(values['Price'][i])*1e6-references[i])/references[i]<=tol for i in exact_reference_rows),
                                                          'denominator':len(exact_reference_rows)} for tol in (.01,.02,.05)}
    per_valid = [i for i in eligible if pd.notna(values['Area'][i]) and values['Area'][i]>0]
    summary['million_vnd_per_m2_interpretation_all_comparable'] = {str(tol):{'matched':sum(abs(float(values['Price'][i])*float(values['Area'][i])*1e6-references[i])/references[i]<=tol for i in per_valid),
                                                                       'denominator':len(per_valid)} for tol in (.01,.02,.05)}
    def price_row(i):
        p = float(values['Price'][i]) if pd.notna(values['Price'][i]) else None
        ref = references[i]
        return audit_row(frame,i,{'rule_label':labels[i],'target_audit_label':target_labels[i],
                                 'text_reference_total_vnd':ref,'reference_reason':reference_sources[i],
                                 'million_relative_error':abs(p*1e6-ref)/ref if p is not None and ref else None,
                                 'billion_relative_error':abs(p*1e9-ref)/ref if p is not None and ref else None,
                                 'parsed_candidates':json.dumps(candidates_all[i],ensure_ascii=False)})
    csv_write('qmanhbeo-text-price-audit-1500.csv',[price_row(i) for i in required])
    csv_write('qmanhbeo-text-price-unconditional-2000.csv',[price_row(i) for i in all_row_sample])
    problem_indices = [i for i in required if references[i] and abs(float(values['Price'][i])*1e6-references[i])/references[i]>.05]
    csv_write('qmanhbeo-text-price-mismatch-examples.csv',[price_row(i) for i in problem_indices[:100]])
    per_indices = [i for i,t in enumerate(target_labels) if t=='PRICE_PER_M2']
    csv_write('qmanhbeo-price-per-m2-evidence.csv',[price_row(i) for i in random.Random(SEED).sample(per_indices,min(100,len(per_indices)))])
    validation = []
    for prop,indices in frame.groupby('Property Type').groups.items():
        idx = list(indices)
        validation.append({'property_type':prop,'row_count':len(idx),
                            'sale_high_confidence':sum(labels[i]=='SALE_HIGH_CONFIDENCE' for i in idx),
                            'rent_high_confidence':sum(labels[i]=='RENT_HIGH_CONFIDENCE' for i in idx),
                            'transaction_ambiguous':sum(labels[i]=='AMBIGUOUS' for i in idx),
                            'total_price_evidence':sum(target_labels[i]=='TOTAL_PRICE' for i in idx),
                            'price_per_m2_evidence':sum(target_labels[i]=='PRICE_PER_M2' for i in idx),
                            'target_ambiguous':sum(target_labels[i]=='AMBIGUOUS' for i in idx)})
    csv_write('qmanhbeo-property-type-audit.csv',validation)
    summary['property_type_audit'] = validation
    source_after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert source_after == original_hash
    summary['source_hash_after_audit'] = source_after
    summary['elapsed_seconds'] = round(time.time()-started,2)
    (DOCS/'qmanhbeo-source-audit-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    # Full original texts and parser evidence remain local, outside the repo.
    (CACHE/'price-review-evidence.json').write_text(json.dumps([audit_row(frame,i,{'candidates':candidates_all[i],'reference':references[i]},full=True) for i in problem_indices[:100]],ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('row_count','transaction_labels','target_labels_under_million_hypothesis','price_comparisons','elapsed_seconds')},ensure_ascii=False),flush=True)


def audit_row(frame,i,extra=None,full=False):
    original = frame.iloc[i]
    row = {'source_record_1based':int(i)+1,'listing_id':original['Listing ID'],'title':original['Title'],
           'description':original['Description'] if full else original['Description'][:700],
           'price_raw':original['Price'],'area_raw':original['Area'],'location':original['Location'],
           'province_original':original['Province'],'property_type':original['Property Type'],
           'property_type_slug':original['Property Type Slug'],'scraped_at':original['Scraped At'],
           'last_updated_date':original['Last Updated Date']}
    if extra: row.update(extra)
    return row


if __name__=='__main__':
    main()
