"""Read-only full-file audit. Writes reports/samples, never cleans or trains.

Run after download-tinix-audit.py. Requires duckdb==1.5.6.
All raw values are preserved; internal normalized text is only for audit rules.
"""
import csv
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.audit-deps'))
sys.path.insert(0, str(Path(tempfile.gettempdir()) / 'tinix-transaction-audit' / 'deps'))
import duckdb
from tinix_audit_rules import classifier_sql, sql_literal, parse_text_prices, RULE_VERSION

DOCS = ROOT / 'docs'
SEED = 42
REVIEW_DATE = date(2026, 10, 4)
LABELS = ['SALE_HIGH_CONFIDENCE', 'RENT_HIGH_CONFIDENCE', 'AMBIGUOUS']


def csv_write(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def records(connection, sql):
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reuse-label-cache',action='store_true')
    options=parser.parse_args()
    manifest = json.loads((DOCS / 'tinix-download-manifest.json').read_text(encoding='utf-8'))
    evidence = json.loads((DOCS / 'vietnam-house-price-source-evidence.json').read_text(encoding='utf-8'))
    assert evidence['revision'] == manifest['revision']
    declared_start = evidence['data_start_date_declared_by_publisher']
    declared_end = evidence['data_end_date_declared_by_publisher']
    rules_hash = hashlib.sha256((ROOT/'scripts/tinix_audit_rules.py').read_bytes()).hexdigest()
    paths = [entry['local_cache_path'] for entry in manifest['files']]
    cache = Path(paths[0]).parent
    db = cache / 'read-only-audit-v1.duckdb'
    connection = duckdb.connect(str(db))
    connection.execute("SET memory_limit='2GB'")
    connection.execute('SET threads=4')
    connection.execute(f'SET temp_directory={sql_literal(str(cache / "spill"))}')
    path_list = '[' + ','.join(sql_literal(path) for path in paths) + ']'
    print('Starting raw full scan', flush=True)
    connection.execute(f"CREATE OR REPLACE VIEW raw_files AS SELECT * FROM read_parquet({path_list}, filename=true, file_row_number=true)")
    columns = [row[0] for row in connection.execute('DESCRIBE raw_files').fetchall() if row[0] not in ('filename', 'file_row_number')]
    assert len(columns) == 19, columns
    exact_struct = 'struct_pack(' + ','.join(f'{column}:={column}' for column in columns) + ')'
    near_struct = 'struct_pack(' + ','.join(
        f"{column}:=regexp_replace(lower(trim({column})), '\\s+', ' ', 'g')" if column in ('name','description') else f'{column}:={column}'
        for column in columns if column != 'published_at') + ')'
    connection.execute(f"""CREATE OR REPLACE VIEW raw AS SELECT * EXCLUDE(filename,file_row_number),
        parse_filename(filename) AS _shard, file_row_number AS _source_row,
        sha256(to_json({exact_struct})) AS _exact_hash,
        sha256(to_json({near_struct})) AS _near_hash FROM raw_files""")
    # The table is an audit cache, retaining every row and all original fields.
    if options.reuse_label_cache:
        previous = json.loads((DOCS/'tinix-transaction-audit-summary.json').read_text(encoding='utf-8'))
        assert previous['revision'] == manifest['revision']
        assert previous['rule_script_sha256'] == rules_hash, 'Rules changed; rescan required'
        tables={row[0]:row[1] for row in connection.execute("SELECT table_name,table_type FROM information_schema.tables").fetchall()}
        if tables.get('audit')=='BASE TABLE' and 'audit_raw' not in tables:
            connection.execute('ALTER TABLE audit RENAME TO audit_raw')
        assert connection.execute('SELECT count(*) FROM audit_raw').fetchone()[0]==3500744
    else:
        connection.execute('CREATE OR REPLACE TABLE audit_raw AS ' + classifier_sql())
    connection.execute("""CREATE OR REPLACE VIEW audit AS SELECT * EXCLUDE(price),
        price AS price_raw,try_cast(price AS DOUBLE) AS price FROM audit_raw""")
    print('Rule scan complete; computing reports', flush=True)
    total = connection.execute('SELECT count(*) FROM audit').fetchone()[0]
    assert total == 3500744, total
    summary = {'dataset': manifest['dataset'], 'revision': manifest['revision'],
               'duckdb_version': duckdb.__version__, 'rule_version': RULE_VERSION,
               'seed': SEED, 'review_date': REVIEW_DATE.isoformat(), 'scan_scope': 'all_10_original_parquet_files',
               'row_count': total, 'raw_rows_deleted': 0, 'raw_values_modified': 0, 'training_performed': False}
    summary['declared_date_range'] = {'start': declared_start, 'end': declared_end}
    summary['sampling_method'] = 'Top 100 per rule label ordered by md5(42|source_shard|zero_based_source_row); independent price sample uses price-42 prefix.'
    summary['source_column_types']={row[0]:row[1] for row in connection.execute('DESCRIBE raw_files').fetchall() if row[0] in columns}
    summary['labels'] = records(connection, 'SELECT rule_label,count(*) AS count, count(*)*100.0/(SELECT count(*) FROM audit) AS percentage FROM audit GROUP BY rule_label ORDER BY rule_label')
    summary['reasons'] = records(connection, 'SELECT rule_label,rule_reason,count(*) AS count FROM audit GROUP BY ALL ORDER BY count DESC')
    summary['quality'] = records(connection, """SELECT
        count(*) FILTER(WHERE price_raw IS NULL) AS price_raw_null,
        count(*) FILTER(WHERE price_raw IS NOT NULL AND price IS NULL) AS price_numeric_parse_failed,
        count(*) FILTER(WHERE price IS NULL OR isnan(price)) AS price_missing,
        count(*) FILTER(WHERE price IS NOT NULL AND price<=0) AS price_nonpositive,
        count(*) FILTER(WHERE price=0) AS price_zero,
        count(*) FILTER(WHERE price<0) AS price_negative,
        count(*) FILTER(WHERE price IS NOT NULL AND NOT isfinite(price)) AS price_nonfinite,
        count(*) FILTER(WHERE area IS NULL OR isnan(area)) AS area_missing,
        count(*) FILTER(WHERE area IS NOT NULL AND area<=0) AS area_nonpositive,
        count(*) FILTER(WHERE area IS NOT NULL AND NOT isfinite(area)) AS area_nonfinite,
        count(*) FILTER(WHERE province_name IS NULL) AS province_null,
        count(*) FILTER(WHERE trim(coalesce(province_name,''))='') AS province_missing_or_blank,
        count(*) FILTER(WHERE district_name IS NULL) AS district_null,
        count(*) FILTER(WHERE ward_name IS NULL) AS ward_null,
        count(*) FILTER(WHERE trim(coalesce(ward_name,''))='') AS ward_missing_or_blank,
        count(DISTINCT province_name) AS province_names_distinct,
        count(DISTINCT district_name) AS district_names_distinct,
        count(DISTINCT (province_name,district_name)) FILTER(WHERE district_name IS NOT NULL) AS province_district_keys,
        count(DISTINCT ward_name) AS ward_names_distinct,
        count(DISTINCT (province_name,district_name,ward_name)) FILTER(WHERE ward_name IS NOT NULL) AS province_district_ward_keys
        FROM audit""")[0]
    summary['sale_quality'] = records(connection, """SELECT count(*) AS rows,
        count(*) FILTER(WHERE price IS NULL) AS price_missing,
        count(*) FILTER(WHERE price<=0) AS price_nonpositive,
        count(*) FILTER(WHERE area IS NULL OR isnan(area)) AS area_missing,
        count(*) FILTER(WHERE area<=0) AS area_nonpositive,
        count(*) FILTER(WHERE ward_name IS NULL) AS ward_null
        FROM audit WHERE rule_label='SALE_HIGH_CONFIDENCE'""")[0]
    summary['dates'] = records(connection, f"""SELECT
        min(try_cast(published_at AS TIMESTAMP)) AS min_timestamp,
        max(try_cast(published_at AS TIMESTAMP)) AS max_timestamp,
        count(*) FILTER(WHERE published_at IS NULL) AS null_dates,
        count(*) FILTER(WHERE published_at IS NOT NULL AND try_cast(published_at AS TIMESTAMP) IS NULL) AS unparseable_dates,
        count(*) FILTER(WHERE try_cast(published_at AS TIMESTAMP) >= TIMESTAMP '{REVIEW_DATE.isoformat()}' + INTERVAL 1 DAY) AS future_after_review_date,
        count(*) FILTER(WHERE try_cast(published_at AS DATE) < DATE '{declared_start}' OR try_cast(published_at AS DATE) > DATE '{declared_end}') AS outside_declared_dates
        FROM audit""")[0]
    monthly = records(connection, "SELECT strftime(try_cast(published_at AS TIMESTAMP),'%Y-%m') AS month,rule_label,count(*) AS count FROM audit GROUP BY ALL ORDER BY month,rule_label")
    csv_write(DOCS / 'tinix-monthly-counts.csv', monthly)
    for label in LABELS:
        summary['dates'][label] = records(connection, f"SELECT min(try_cast(published_at AS TIMESTAMP)) AS min_timestamp,max(try_cast(published_at AS TIMESTAMP)) AS max_timestamp FROM audit WHERE rule_label={sql_literal(label)}")[0]
    print('Computing exact and conservative near duplicates', flush=True)
    for key in ['exact', 'near']:
        summary[f'{key}_duplicates'] = records(connection, f"""SELECT count(*) AS groups,
            coalesce(sum(n-1),0) AS excess_rows,coalesce(sum(n),0) AS rows_in_groups,max(n) AS max_group_size
            FROM (SELECT _{key}_hash,count(*) AS n FROM audit GROUP BY _{key}_hash HAVING count(*)>1)""")[0]
    near_examples = records(connection, """SELECT _shard,_source_row,name,left(description,700) AS description_excerpt,price_raw AS price,area,province_name,property_type_name,published_at,_near_hash FROM audit
        WHERE _near_hash IN (SELECT _near_hash FROM audit GROUP BY _near_hash HAVING count(*)>1 ORDER BY count(*) DESC LIMIT 3)
        ORDER BY _near_hash,published_at LIMIT 30""")
    csv_write(DOCS / 'tinix-duplicate-examples.csv', near_examples)
    sample = []
    for label in LABELS:
        rows = records(connection, f"""SELECT _shard,_source_row,name,description,price_raw AS price,area,province_name,property_type_name,published_at,rule_label,rule_reason
            FROM audit WHERE rule_label={sql_literal(label)}
            ORDER BY md5('{SEED}|' || _shard || '|' || CAST(_source_row AS VARCHAR)) LIMIT 100""")
        sample.extend(rows)
    sample_fields = ['name','description_excerpt','price','area','province_name','property_type_name','published_at','rule_label','rule_reason','source_shard','source_row']
    public_sample = [{**{key: row[key] for key in sample_fields if key in row},
                      'description_excerpt': (row['description'] or '')[:900],
                      'source_shard':row['_shard'], 'source_row':row['_source_row']} for row in sample]
    csv_write(DOCS / 'tinix-transaction-audit-sample.csv', public_sample, sample_fields)
    # Full sample text remains in TEMP for review only; no full descriptions in repo.
    (cache / 'manual-review-full-text.json').write_text(json.dumps(sample,ensure_ascii=False,default=str),encoding='utf-8')
    summary['sample_counts'] = {label: sum(row['rule_label']==label for row in sample) for label in LABELS}
    print('Computing SALE quantiles without deleting outliers', flush=True)
    distribution = []
    for metric, expression in [('price', 'price'), ('area', 'area'), ('price_per_m2', 'CASE WHEN area>0 AND isfinite(area) THEN price/area END')]:
        rows = records(connection, f"""WITH sale AS (SELECT property_type_name,province_name,{expression} AS value FROM audit WHERE rule_label='SALE_HIGH_CONFIDENCE')
            SELECT CASE WHEN grouping(property_type_name)=1 AND grouping(province_name)=1 THEN 'all'
                        WHEN grouping(property_type_name)=0 AND grouping(province_name)=1 THEN 'property_type'
                        WHEN grouping(property_type_name)=1 THEN 'province' ELSE 'property_type_and_province' END AS scope,
                property_type_name,province_name,count(*) AS sale_rows,
                count(*) FILTER(WHERE value IS NULL) AS undefined_count,
                count(*) FILTER(WHERE value IS NOT NULL AND NOT isfinite(value)) AS nonfinite_count,
                count(*) FILTER(WHERE value IS NOT NULL AND isfinite(value)) AS finite_count,
                min(value) FILTER(WHERE isfinite(value)) AS min,
                quantile_cont(value,[0.01,0.05,0.25,0.50,0.75,0.95,0.99]) FILTER(WHERE isfinite(value)) AS percentiles,
                max(value) FILTER(WHERE isfinite(value)) AS max
            FROM sale GROUP BY GROUPING SETS((),(property_type_name),(province_name),(property_type_name,province_name))
            ORDER BY scope,property_type_name,province_name""")
        for row in rows:
            quantiles = row.pop('percentiles') or [None]*7
            row.update(zip(['p1','p5','p25','p50','p75','p95','p99'], quantiles))
            row['median'] = row['p50']; row['metric'] = metric
        distribution.extend(rows)
    csv_write(DOCS / 'tinix-sale-price-distributions.csv', distribution)
    extremes=[]
    for metric,expr in [('price','price'),('area','area'),('price_per_m2','price/nullif(area,0)'),('frontage_width','frontage_width'),('road_width','road_width')]:
        extremes.extend(records(connection,f"""SELECT {sql_literal(metric)} AS extreme_metric,{expr} AS extreme_value,
            _shard,_source_row,name,left(description,900) AS description_excerpt,price_raw AS price,area,frontage_width,road_width,province_name,property_type_name,published_at,rule_label
            FROM audit WHERE isfinite({expr}) ORDER BY {expr} DESC LIMIT 5"""))
    csv_write(DOCS / 'tinix-extreme-examples.csv',extremes)
    print('Parsing text prices in independent seeded SALE sample',flush=True)
    price_rows = records(connection, """SELECT _shard,_source_row,name,description,price,price_raw,area,province_name,property_type_name FROM audit
        WHERE rule_label='SALE_HIGH_CONFIDENCE' ORDER BY md5('price-42|' || _shard || '|' || CAST(_source_row AS VARCHAR)) LIMIT 1000""")
    price_results=[]
    for row in price_rows:
        candidates=parse_text_prices(row['name'],row['description'],row['area'])
        # Prefer title amounts when present. Contradictory amounts are reported,
        # not resolved by choosing whichever happens to match the numeric column.
        preferred=[item for item in candidates if item['source']=='title'] or candidates
        values=[item['total_equivalent_vnd'] for item in preferred]
        unique=[]
        for value in values:
            if not any(abs(value-existing)/max(value,existing)<=.02 for existing in unique): unique.append(value)
        parsed=unique[0] if len(unique)==1 else None
        stored=row['price']
        relative_error=abs(stored-parsed)/parsed if parsed and stored is not None and math.isfinite(stored) else None
        label='matched_2pct' if relative_error is not None and relative_error<=.02 else 'mismatch' if relative_error is not None else 'multiple_text_prices' if len(unique)>1 else 'missing_structured_price' if parsed else 'no_supported_price'
        price_results.append({'source_shard':row['_shard'],'source_row':row['_source_row'],'name':row['name'],
            'description_excerpt':(row['description'] or '')[:900], 'province_name':row['province_name'],'property_type_name':row['property_type_name'],
            'price':row['price_raw'],'area':row['area'],'parsed_total_vnd':parsed,'relative_error':relative_error,'comparison':label,
            'parsed_candidates':json.dumps(candidates,ensure_ascii=False)})
    csv_write(DOCS / 'tinix-text-price-audit.csv',price_results)
    from collections import Counter
    counts=Counter(row['comparison'] for row in price_results)
    comparable=counts['matched_2pct']+counts['mismatch']
    summary['text_price_audit']={'sample_rows':len(price_rows),'counts':dict(counts),'tolerance':.02,
        'comparable_rows':comparable,'match_rate':counts['matched_2pct']/comparable if comparable else None,
        'records_with_candidates':sum(bool(json.loads(row['parsed_candidates'])) for row in price_results),
        'single_candidate_total':sum(row['parsed_total_vnd'] is not None for row in price_results),
        'limitations':'Parser compatibility only, not source accuracy. Known false mismatches: discounts, furniture gifts, down payments, rental abbreviations, omitted per-m2 units, decimal commas with 3 digits. Unsupported/no-price rows are not treated as matches.'}
    csv_write(DOCS / 'tinix-text-price-largest-mismatches.csv', sorted([row for row in price_results if row['comparison']=='mismatch'],key=lambda row:row['relative_error'],reverse=True)[:30])
    summary['rule_script_sha256']=rules_hash
    (DOCS/'tinix-transaction-audit-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    connection.close()
    print(json.dumps(summary,ensure_ascii=True,default=str),flush=True)
    print('PASS: full audit completed, raw source untouched; manual sample review still required.',flush=True)


if __name__=='__main__':
    main()
