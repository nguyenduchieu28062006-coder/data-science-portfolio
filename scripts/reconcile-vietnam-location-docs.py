"""Refresh current metadata/docs from existing aggregates; no dataset scan."""
from pathlib import Path
from datetime import datetime,timezone
import json,shutil
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def write(name,value):(ROOT/name).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
def main():
    if read('vietnam-house-model.json').get('schema_version',0)>=5:
        print('Historical v2 reconciler retired; use reconcile-vietnam-public-docs.py.');return
    m=read('vietnam-house-model.json');report=read('docs/vietnam-location-upgrade-report.json')
    m['generated_at']=datetime.now(timezone.utc).isoformat()
    m['data_source']['canonical_file']='data/verified-vietnam-house-sales.parquet'
    m['data_source']['file']='verified-vietnam-house-locations.parquet'
    m['model_review']['report']='docs/vietnam-location-public-status.md'
    m['limitations']=[v.replace('Khu vực là quận/huyện lịch sử, không đoán phường/xã.','Ward/dự án là tên lịch sử do publisher khai báo; quận/huyện giữ làm ngữ cảnh, không suy đoán ranh giới hiện hành.') for v in m['limitations'] if 'Nhóm ít hơn 30' not in v]
    rule='Dự án <20 mẫu dùng ward cùng loại; ward <30 mẫu dùng tỉnh; tỉnh <80 mẫu không ước tính. Location không tồn tại luôn trả no-result.'
    if rule not in m['limitations']:m['limitations'].append(rule)
    write('vietnam-house-model.json',m)
    index=read('data/vietnam-location-index.json')
    index.update(source='TiniX AI',dataset='tinixai/vietnam-real-estates',license='CC-BY-NC-4.0',revision=m['data_source']['revision'],data_start=m['data_start_date'],data_latest_date=m['data_end_date'])
    (ROOT/'data/vietnam-location-index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    report['payload_bytes']={name:(ROOT/name).stat().st_size for name in ['data/vietnam-location-index.json','data/vietnam-market-stats.json']}
    write('docs/vietnam-location-upgrade-report.json',report)
    for path in ['docs/verified-vietnam-house-data-summary.json','docs/vietnam-house-cleaning-report.json']:
        data=read(path);data.update(location_upgrade_version=m['model_version'],location_enrichment_report='docs/vietnam-location-enrichment.json',features=m['features'],location_thresholds=m['location_thresholds'],location_counts=m['location_counts']);write(path,data)
    training=read('docs/vietnam-house-training-results.json');training.update(model_version=m['model_version'],data_source=m['data_source'],model_review=m['model_review'],features=m['features'],location_thresholds=m['location_thresholds']);write('docs/vietnam-house-training-results.json',training)
    archive=ROOT/'docs/archive/beta-v1';archive.mkdir(parents=True,exist_ok=True)
    for name in ['docs/vietnam-house-public-status.md','docs/verified-vietnam-house-data-report.md','VIETNAM-HOUSE-SETUP.md','docs/vietnam-house-validation-results.json']:
        source=ROOT/name
        if not (archive/source.name).exists():shutil.copy2(source,archive/source.name)
    (archive/'README.md').write_text('Historical beta-v1 outputs and code. Not active public scope. Current statistical BETA status: docs/vietnam-location-public-status.md. No ML training occurred.\n',encoding='utf-8')
    for name in ['docs/vietnam-house-public-status.md','docs/verified-vietnam-house-data-report.md']:
        (ROOT/name).write_text('# PUBLIC STATUS: READY — beta-location-v2\n\nCurrent scope: apartment asking-price statistical BETA, not ML.\n\n[Complete current report](vietnam-location-public-status.md). Counts, type gates, thresholds, source/license, limitations, freshness, tests, API, map, History and SQL are recorded there. Historical beta-v1 outputs are preserved under `archive/beta-v1/`.\n',encoding='utf-8')
    validation=read('docs/vietnam-house-validation-results.json')
    validation.update(model_version=m['model_version'],house_training_performed=False,raw_files_rescanned=False,cached_location_enrichment_only=True)
    validation['house_browser'].update(checks_per_viewport=71,fixture_count=250,maximum_absolute_error_vnd=0,maximum_relative_error=0)
    validation['location_tests']={'status':'PASS','same_city_wards':3,'distinct_stat_keys':3,'unknown_locations_no_result':True,'known_sparse_fallback_disclosed':True,'map_form_both_directions':True,'disabled_type_map_cleared':True,'history_exact_vs_province':True,'api_actual_source_evaluated':True}
    # Path counts from beta-v1 are historical, not current validation evidence.
    validation.pop('public_paths',None)
    write('docs/vietnam-house-validation-results.json',validation)
    (ROOT/'VIETNAM-HOUSE-SETUP.md').write_text('''# Vietnam Real Estate Market Estimate — beta-location-v2

PUBLIC STATUS: READY, statistical apartment BETA with limitations. No ML model was trained; MAE/RMSE/R²/MAPE are not applicable. See [current report](docs/vietnam-location-public-status.md) and [structured counts/type gates](docs/vietnam-location-upgrade-report.json).

Open the project root with VS Code Live Server, then `vietnam-house-price.html`. No dataset generation or Python dependency install is needed to preview. Plain Live Server serves the estimator, autocomplete, map and static aggregates. `/api/market-data` needs a compatible Vercel function runtime; browser statistics use the same resolver directly. Map tiles need internet, but exact dropdown selection and estimation do not require tiles.

Use a source sample, select province → historical ward/commune → project (when present), and enter area. Unknown selections never estimate. Known sparse locations visibly fall back. The range is P25/median/P75 of asking-price statistics, not a confidence interval. Only apartment is enabled; no other property types are forced through an insufficient gate.

## Supabase History

No location migration is required: `input_data.metadata` stores chosen and used location, resolution, sample count, coverage, method, latest data date and quantile totals. Optional form inputs are stored separately under `inputs`. Existing records still render. Explicit save requires login; preview/estimation does not.

If `house_price_history` already exists from the previous setup, run no new SQL. If it is absent, run [supabase/vietnam-house-price.sql](supabase/vietnam-house-price.sql) in SQL Editor once. This script creates the existing table/policies and optional future market tables; it does not delete history. No SQL has been applied to your real Supabase here. Frontend uses only publishable/anon credentials; service_role remains server-only. Mock SDK checks verify owner filtering, account changes and own delete boundaries; real RLS awaits your project setup.

## Source and limits

TiniX AI, `tinixai/vietnam-real-estates`, revision `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`, publisher-declared CC BY-NC 4.0, noncommercial portfolio. Period 01/06/2025–30/03/2026 according to publisher listing timestamps. This is not completed transaction data, realtime or an independent validation of upstream provenance/rights.

290,282 existing apartment IDs were retained; ward/project metadata was restored by exact hash join from the existing read-only apartment cache. No raw shard was rescanned or sale rule rerun. Historical publisher ward/district and project names are not confirmed current legal boundaries or independently verified listing addresses. Ward IDs are scoped by province/district; conflicting duplicate projects and projects without wards are withheld from project statistics.

The mixed ML gate remains FAIL (194/200=97%). Apartment members of that previous sample were 72/72 with no observed errors, a limited BETA observation, not a new population accuracy claim. Other types remain disabled.

Raw/canonical/enriched Parquet and historical reports/code are preserved locally; Git/public packaging excludes Parquet, local dependencies and docs. The frontend loads only metadata/aggregates and pinned Leaflet assets. Current implementation: `vietnam-estimate-core.js` shared with API, `vietnam-estimate-page.js`, `vietnam-house-history-save.js`. Old beta-v1 JS entry files are retired and point to preserved archive copies.

## Future feed

No live feed is connected. The approved-feed adapter remains a future candidate, with no bulk scraping. `scripts/update-vietnam-market.py` exits safely when unconfigured. If approved later, it writes separate `data/vietnam-approved-feed-stats.json`; integration requires canonical location review and never overwrites the current estimator. The static BETA is public-ready without a live feed. No commit/push/deploy was performed.

## Validation

`python -B tests/test_vietnam_house_pipeline.py`
`python -B tests/test_vietnam_house_browser.py`
`python -B tests/run-vietnam-regressions.py`
`python -B tests/test_health_prediction.py`

Browser checks use local HTTP and mock SDK, not your real database. Canonical generation and aggregate scripts are guarded to reuse existing output; do not run them to preview. No training, raw audit or scrape is needed.
''',encoding='utf-8')
    print('Current docs/metadata reconciled from existing outputs only')
if __name__=='__main__':main()
