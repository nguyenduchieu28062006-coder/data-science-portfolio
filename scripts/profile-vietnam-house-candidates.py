"""Read-only CSV source profiles for a dataset selection report.

No cleaned dataset, training, administrative mapping or prediction is produced.
Keyword hits are inspection leads, not transaction labels or quality estimates.
"""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
MISSING = {'', 'nan', 'null', 'none', 'n/a'}


def numeric_profile(values):
    parsed = []
    unparsed = 0
    for value in values:
        if value.strip().lower() in MISSING:
            continue
        try:
            number = float(value)
            if not math.isfinite(number):
                unparsed += 1
            else:
                parsed.append(number)
        except ValueError:
            unparsed += 1
    return {'numeric_count': len(parsed), 'unparsed_nonmissing_count': unparsed,
            'nonpositive_count': sum(x <= 0 for x in parsed),
            'min': min(parsed) if parsed else None, 'max': max(parsed) if parsed else None}


def main():
    manifest = json.loads((ROOT/'docs/vietnam-house-new-candidates-file-manifest.json').read_text(encoding='utf-8'))
    results = []
    for entry in manifest['files']:
        if 'error' in entry:
            continue
        raw = Path(entry['local_cache_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['inspection_sha256']
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', errors='strict')))
        rows = list(reader)
        # A truncated prefix may end inside a record; do not count that record.
        if not entry['complete_source_file']:
            rows = rows[:-1]
        assert all(None not in row for row in rows), 'Unexpected extra CSV fields'
        columns = reader.fieldnames
        result = {'dataset': entry['dataset'], 'filename': entry['filename'],
                  'complete_source_file': entry['complete_source_file'],
                  'verified_row_count': len(rows) if entry['complete_source_file'] else None,
                  'inspected_prefix_rows': len(rows) if not entry['complete_source_file'] else None,
                  'columns': columns,
                  'all_fields_blank_count': sum(all((r.get(k) or '').strip() == '' for k in columns) for r in rows),
                  'missing_counts': {key: sum((r.get(key) or '').strip().lower() in MISSING for r in rows) for key in columns},
                  'exact_duplicate_rows': len(rows) - len({tuple(r.get(k) for k in columns) for r in rows})}
        for key in ('id', 'product_id', 'Listing ID'):
            if key in columns:
                ids = [r[key] for r in rows if r[key].strip().lower() not in MISSING]
                result['identifier'] = {'column': key, 'unique_nonmissing': len(set(ids)), 'repeated_occurrences': len(ids)-len(set(ids))}
        location_key = next((k for k in ('location', 'address', 'Address', 'Province') if k in columns), None)
        if location_key:
            # Original final address token only; no assumption about current borders.
            tokens = Counter(r[location_key].split(',')[-1].strip() for r in rows)
            result['original_location_final_token_counts'] = dict(tokens.most_common())
        result['numeric_fields'] = {k: numeric_profile([r[k] for r in rows]) for k in
                                    ('price_million_vnd', 'area_m2', 'timeline_hours', 'bedrooms', 'bathrooms', 'floors',
                                     'Price', 'Area', 'Frontage', 'Access Road', 'Floors', 'Bedrooms', 'Bathrooms',
                                     'bedrooms_num', 'bathrooms_num') if k in columns}
        result['distinct_values'] = {k: dict(Counter(r[k] for r in rows).most_common(30)) for k in
                                     ('frontage', 'Loại hình nhà ở', 'Property Type', 'Property Type Slug', 'Legal status', 'Giấy tờ pháp lý') if k in columns}
        result['date_fields'] = {}
        for key in ('Ngày', 'Scraped At', 'Last Updated Date'):
            if key in columns:
                dates = [r[key] for r in rows if r[key].strip().lower() not in MISSING]
                result['date_fields'][key] = {'raw_min_lexical': min(dates) if dates else None, 'raw_max_lexical': max(dates) if dates else None,
                                             'distinct_count': len(set(dates)), 'examples': dates[:5]}
                parsed = []
                for value in dates:
                    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M'):
                        try:
                            parsed.append(datetime.strptime(value, fmt))
                            break
                        except ValueError:
                            continue
                result['date_fields'][key].update({'parsed_min': min(parsed).isoformat() if parsed else None,
                                                  'parsed_max': max(parsed).isoformat() if parsed else None,
                                                  'parsed_count': len(parsed), 'unparsed_nonmissing_count': len(dates)-len(parsed),
                                                  'timezone_in_source': None})
        if 'detail_url' in columns:
            result['detail_url_domains'] = dict(Counter(re.sub(r'^https?://', '', r['detail_url']).split('/')[0] for r in rows))
            leads = {'title_starts_rental': [], 'title_price_per_m2_text': []}
            for row in rows:
                title = row['title'].lower().strip()
                if re.match(r'^(?:\W|\d)*(?:cho thuê|cần cho thuê|căn hộ cho thuê|nhà cho thuê)', title):
                    leads['title_starts_rental'].append(row)
                if re.search(r'(?:triệu|tr|tỷ|ty)\s*/\s*(?:m2|m²)|(?:giá|triệu)\s*(?:m2|m²)', title):
                    leads['title_price_per_m2_text'].append(row)
            result['keyword_inspection_leads'] = {k: {'count': len(v), 'first_12_rows': v[:12]} for k, v in leads.items()}
        if 'price' in columns:
            result['price_text_patterns'] = dict(Counter('negotiable' if 'thỏa thuận' in r['price'].lower() else
                                                         'per_m2' if '/m' in r['price'].lower() else
                                                         'billion_total_text' if 'tỷ' in r['price'].lower() else
                                                         'million_total_text' if 'triệu' in r['price'].lower() else 'other' for r in rows))
        if 'Giá/m2' in columns:
            result['price_text_patterns'] = dict(Counter('million_per_m2' if 'triệu/m' in r['Giá/m2'].lower() else
                                                         'billion_per_m2' if 'tỷ/m' in r['Giá/m2'].lower() else 'other' for r in rows))
        samples = random.Random(42).sample(rows, min(12, len(rows)))
        result['seed42_sample_rows'] = [{k: v for k, v in r.items() if k not in
                                         ('Latitude', 'Longitude', 'VIP Account', 'Avatar', 'Agent Role', 'Agent Name', 'Agent Listing Count')}
                                        for r in samples]
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k not in ('seed42_sample_rows', 'keyword_inspection_leads', 'original_location_final_token_counts')}, ensure_ascii=False))
        print(json.dumps({'dataset': entry['dataset'], 'coverage': result.get('original_location_final_token_counts')}, ensure_ascii=False))
        if 'keyword_inspection_leads' in result:
            print(json.dumps({'dataset': entry['dataset'], 'leads': result['keyword_inspection_leads']}, ensure_ascii=False))
    output = {'review_date': '2026-10-04', 'scope': 'source inspection only', 'training_performed': False,
              'cleaning_performed': False, 'location_mapping_performed': False, 'profiles': results}
    (ROOT/'docs/vietnam-house-new-candidates-profiles.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
