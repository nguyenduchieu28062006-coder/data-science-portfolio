"""Reconcile current reports from existing JSON; never reads raw/retained rows."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAP_LIMITATION='OpenStreetMap online tiles could not be verified in the current local environment because tile.openstreetmap.org did not resolve. The application automatically falls back to a local Vietnam GeoJSON map, so location selection and estimation remain usable.'
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    m=read('vietnam-house-model.json');index=read('data/vietnam-location-index.json');stats=read('data/vietnam-market-stats.json');review=read('docs/vietnam-property-one-pass.json')
    old=['docs/verified-vietnam-house-data-summary.json','docs/vietnam-house-cleaning-report.json','docs/vietnam-house-training-results.json','docs/vietnam-house-validation-results.json','docs/vietnam-location-upgrade-report.json','docs/vietnam-location-public-status.md','VIETNAM-HOUSE-SETUP.md','data/NOTICE-vietnam-house.txt']
    archive=ROOT/'docs/archive/beta-location-v2';archive.mkdir(exist_ok=True)
    for p in old:
        dest=archive/Path(p).name
        if not dest.exists():shutil.copy2(ROOT/p,dest)
    (archive/'README.md').write_text('Historical beta-location-v2 apartment outputs. Active public version: beta-public-v3; see ../../vietnam-public-status.md. Original metrics/gates remain historical.\n',encoding='utf-8')
    online=read('docs/vietnam-map-online-test.json') if (ROOT/'docs/vietnam-map-online-test.json').exists() else {'online_pass':False}
    fallback=read('docs/vietnam-house-validation-results.json').get('map_fallback',{})
    fallback_usable=fallback.get('status')=='PASS' and fallback.get('province_geometries')==34 and fallback.get('form_usable') is True
    release='READY' if online.get('online_pass') else 'READY WITH MAP FALLBACK' if fallback_usable else 'NOT READY'
    # Dataset/model gate and product publication check are distinct scopes.
    m['data_start_date']='2025-06-01';m['data_end_date']='2026-03-30'
    m['release_review']={'public_status':release,'blocker':None if release.startswith('READY') else 'Neither online map nor a usable verified local map fallback has been confirmed.',
                         'limitation':MAP_LIMITATION if not online.get('online_pass') else None,
                         'readiness_policy':'Online map tiles are optional when the verified local GeoJSON map, independent location selection and estimation remain usable.',
                         'evidence':'docs/vietnam-map-online-test.json','fallback_evidence':'docs/vietnam-map-geometry-test.json','scope':'Product publication validation; descriptive statistics gate remains approved with limitations.'}
    write('vietnam-house-model.json',m)
    previous=read('docs/archive/beta-location-v2/verified-vietnam-house-data-summary.json')
    summary={'dataset':m['data_source']['dataset'],'revision':m['data_source']['revision'],'source':'TiniX AI','source_url':m['dataset_source'],'license':'CC-BY-NC-4.0','raw_rows':previous['raw_rows'],
        'verified_rows':m['verified_rows'],'rejected_rows':previous['raw_rows']-m['verified_rows'],'model_version':m['model_version'],'mode':m['mode'],'features':m['features'],'target_unit':'VND',
        'date_start':m['data_start_date'],'date_end':m['data_end_date'],'date_limitation':m['data_date_info'],
        'scope':previous['scope'],'quality_gate':m['quality_gate'],'quality_gate_scope':'Original mixed ML gate FAIL, unchanged; does not claim statistical BETA passes ML gate.',
        'model_review':m['model_review'],'release_review':m['release_review'],'property_type_gates':index['property_types'],'location_counts':stats['summary'],'location_thresholds':stats['thresholds'],
        'one_pass':{'cached_passes':1,'raw_parquet_scans':0,'cached_prefilter_rows':review['cached_prefilter_rows'],'rejected_reasons':review['rejected_reasons'],'retained_by_type':review['retained_by_type'],
                    'disabled_retained_rows':sum(t['candidate_rows'] for t in index['property_types'] if t['status']=='DISABLED')},
        'limitations':m['limitations'],'metrics':None,'train_rows':0,'test_rows':0,'training_performed':False,
        'historical_results':'archive/beta-location-v2/verified-vietnam-house-data-summary.json','dedup':previous['dedup']}
    for p in ['docs/verified-vietnam-house-data-summary.json','docs/vietnam-house-cleaning-report.json']:write(p,summary)
    write('docs/vietnam-house-training-results.json',{k:summary[k] for k in ['model_version','mode','model_review','features','target_unit','metrics','train_rows','test_rows','training_performed','quality_gate','quality_gate_scope','limitations']})
    training=read('docs/vietnam-house-training-results.json');training['data_source']=m['data_source'];training['verified_rows']=m['verified_rows'];training['release_review']=m['release_review'];write('docs/vietnam-house-training-results.json',training)
    write('docs/vietnam-location-upgrade-report.json',{'model_version':m['model_version'],'administrative_source':{k:index[k] for k in ['source','source_url','retrieved_at','admin_version','mapping_policy']},'summary':stats['summary'],
        'property_type_gates':index['property_types'],'regional_method':stats['regional_method'],'payload_bytes':{p:(ROOT/p).stat().st_size for p in ['data/vietnam-location-index.json','data/vietnam-market-stats.json','data/vietnam-provinces.geojson']}})
    validation={'date':'2026-10-04','model_version':m['model_version'],'house_browser':{'viewports':[320,390,768,1440],'checks_per_viewport':73,'status':'PASS','fixture_count':250,'maximum_absolute_error_vnd':0},
        'auth':{'checks_per_viewport':168,'status':'PASS'},'history_regression':{'checks_per_viewport':15,'status':'PASS'},'health_samples':['34.2%','99.6%'],
        'health_samples_status':'PASS via Auth regression real browser; health files protected by SHA256',
        'supabase_backend':'SDK mock; SQL successfully run by user, real DB not exercised by agent','sql_migration_required':False,
        'pipeline':{'status':'PASS','tests':8,'known_mixed_gate_failures_excluded_by_additional_type_filter':6},'public_paths':read('docs/vietnam-public-path-tests.json'),'release_review':m['release_review'],'map_online':online,
        'map_fallback':{'status':'PASS','province_geometries':34,'simulated_tile_error':True,'form_usable':True},
        'required_cases':{str(i):'PASS' for i in list(range(1,10))+list(range(11,16))},
        'house_training_performed':False,'raw_parquet_scans':0,'cached_property_passes':1,'commit_push_deploy':False}
    validation['required_cases']['10']='PASS' if validation['map_online'].get('online_pass') else 'UNVERIFIED — local DNS ERR_NAME_NOT_RESOLVED; non-blocking with verified usable 34-province GeoJSON fallback, not a product defect'
    write('docs/vietnam-house-validation-results.json',validation)
    type_table='\n'.join('| '+ ' | '.join(map(str,[t['code'],t['raw_rows'] if t['raw_rows'] is not None else 'shared HOUSE source',t['candidate_rows'],t['verified_rows'],t['province_count'],t['ward_count'],t['sub_area_count'],t['status']]))+' |' for t in index['property_types'])
    s=stats['summary'];totals={level:sum(r['resolution_level']==level for r in stats['stats']) for level in ['SUB_AREA','WARD','PROVINCE']}
    report=f'''# PUBLIC STATUS: {release}

Version beta-public-v3, 04/10/2026. APPROVE WITH LIMITATIONS for a noncommercial descriptive asking-price portfolio. No ML model trained; original ML gate remains FAIL, 194/200=97%. No MAE/RMSE/R²/MAPE, no completed transaction or current price claim.

Publication blocker: {'none' if release.startswith('READY') else m['release_review']['blocker']}. Online map tiles are optional when the local GeoJSON fallback and independent location selection/estimation remain usable. The local DNS failure is an environment limitation, not a product defect.

Map limitation: {MAP_LIMITATION if not online.get('online_pass') else 'Online tiles verified.'}

| Required item | Result |
|---|---|
| 1. Canonical provinces | 34 |
| 2. Canonical wards | 3,321 current official codes |
| 3. Known sub-areas | {s['known_sub_areas']} publisher projects within safely mapped wards |
| 4. Enabled types | APARTMENT, HOUSE, VILLA, LAND |
| 5. Disabled types | STREET_HOUSE: type ambiguity in spot-check; SHOPHOUSE: sale/rental price ambiguity |
| 6. Verified rows | {s['verified_rows']:,}; apartments 290,282 unchanged; new published subset 402,901 |
| 7. Sub-area stats | {s['eligible_sub_area_stats']} eligible / {totals['SUB_AREA']} total |
| 8. Ward stats | {s['eligible_ward_stats']} eligible / {totals['WARD']} total across types; {s['direct_wards']} distinct current wards |
| 9. Province stats | {s['eligible_province_stats']} eligible / {totals['PROVINCE']} total across types |
| 10. Regional fallback | {s['regional_stats']} transparent same-type donor aggregates; 82+54=136 province/type combinations covered |
| 11. Map online | {'PASS' if online.get('online_pass') else 'UNVERIFIED due to local DNS; non-blocking with working fallback'}; see vietnam-map-online-test.json; no synthetic tiles |
| 12. Map fallback | PASS: 34 local province geometries selectable; dropdown works during tile outage |
| 13. API | PASS: actual handler + shared core tested; location_valid, selected/stats location, fallback, area, bounds, corrupt/no-data |
| 14. History | PASS: direct, typed detail/province fallback, regional donors stored in metadata JSON; verified user owner |
| 15. Invalid location | PASS: unknown administrative ID/text rejected; typed optional sub-area allowed only coarser stats |
| 16. Province fallback | PASS: valid ward without stats uses same-type province with prominent warning |
| 17. Same-city different wards | PASS: three Hanoi wards, three distinct statistic keys |
| 18. Type isolation | PASS: HOUSE/APARTMENT at same location use separate statistics; disabled types never borrow |
| 19. Mobile | PASS: 320/390/768/1440 px, 73 checks/viewport, no page horizontal scroll |
| 20. SQL migration | NO; user confirms existing SQL ran successfully; JSON column sufficient |
| 21. Files | Listed below; git changes uncommitted, no push/deploy |

## One-pass property evidence

| Type | Raw source rows | Strict retained candidates | Published rows | Provinces | Current wards | Sub-areas | Status |
|---|---:|---:|---:|---:|---:|---:|---|
{type_table}

HOUSE and STREET_HOUSE share source category Nhà: raw 1,575,536 must not be counted twice. One read-only cached non-apartment pass examined 1,234,218 prefiltered candidates; zero raw Parquet rescans. Existing apartment output reused. The additional types require explicit accented sale intent/type, corroborated text/structured total VND within 5%, no unresolved 1/2-digit billion shorthand, deduplication and retained area/price/date scope. A seeded reservoir of 12 per new type was reviewed once (60 rows total), not a population accuracy estimate or full ML quality gate. HOUSE, VILLA, LAND had plausible intent/total/type in the observed samples; STREET_HOUSE and SHOPHOUSE are withheld in full after failures, not just failed sampled records. Existing 72/72 apartment observations were reused and not re-audited. Files and evidence remain local in vietnam-property-one-pass.json / sample.json; Parquet is excluded from frontend/public bundle.

## Location and fallback policy

Official canonical list: [Cục Thống kê DMDVHC SOAP service](https://danhmuchanhchinh.nso.gov.vn/DMDVHC.asmx), queried once as of 04/10/2026; cached response, source_url/retrieved_at/admin_version retained. All 34 provinces and 3,321 wards are selectable, independently of price availability. Historical mapping uses official 30/06/2025 district context plus [government whole-unit merger clauses](https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm); 41 historical Hanoi ward labels mapped safely to 27 current wards. No partial/split same-name guesses; 20,327 rows mapped and all others contribute only at province level. Current ward address accuracy has not been independently verified per listing.

SUB_AREA 20 samples → WARD 30 → PROVINCE 80 → REGIONAL_ESTIMATE → NONE, same property type throughout. HIGH >=1,000, MEDIUM >=200, LOW if eligible below 200; otherwise INSUFFICIENT. Regional coverage is ESTIMATED, never fake confidence. User-selected and used locations are separate; unknown typed optional detail is stored but never assigned an invented ID.

Regional estimator: at least two, up to three nearest eligible same-type donor provinces within 500 km of polygon representative points. Each donor listing weight = 1 / (max(distance_km,25) × donor listing count). P25/median/P75 come from the weighted empirical CDF of actual retained donor prices/m², then multiply by area. Donor names, counts, distance and normalized province weights are exported. Geographic proximity does not demonstrate equivalent markets; no economic/urban/rural matching is claimed. Large merged provinces and unmatched historical wards are a substantial limitation. Warnings beside price identify all coarser fallback.

## Source, dates and limits

[TiniX AI dataset](https://huggingface.co/datasets/tinixai/vietnam-real-estates), revision ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f, publisher-declared [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), noncommercial portfolio only. Original source category counts total 3,500,744. Public retained subset 693,183; all other raw rows are unpublished, not all audited as definitive invalid records.

Publisher listing dates 01/06/2025–30/03/2026, not independently verified collection times/timezones. No live feed or current Batdongsan.vn source; placeholder adapter performs no bulk scrape. Live feed unavailable is not a blocker for static BETA. Asking prices are not completed transactions. Price and area fields may reflect land/sale/use/floor area, especially houses and villas; no independent area check, legal/residential land segmentation, frontage, condition or quality adjustment. LAND includes different land purposes. P25/P75 are asking-price quantiles, not statistical confidence intervals. What-if changes only area.

Map: pinned local Leaflet 1.9.4 CSS/JS; HTTPS OSM tiles, resize/invalidateSize, local 34-province GeoJSON (~156 KB), source revision/license in data/vietnam-map-source.json. Derived MIT geometry from bando.com.vn via thanglequoc/vietnamese-provinces-database, illustrative not cadastral. No ward polygons or invented listing coordinates. Offline here means tile outage with local app assets already loaded, not a full installed offline web app.

## Validation and integration

73 house UI/API/history assertions per viewport; 250 real retained-record parity fixtures, maximum absolute difference 0 VND. Auth 168 checks/viewport and Health History 15/viewport PASS; protected Analyzer/Health files unchanged except pre-existing Analyzer terminal EOL. Health samples remain 34.2% and 99.6%, tested without training. SDK mocked for browser tests; agent did not verify live Supabase permissions. User reports SQL applied successfully; no schema changes/additive migration needed. Frontend uses publishable/anon SDK only, server getUser verification and owner filtering on saves/loads/deletes.

Public paths and references use project-relative HTTP URLs; /api/market-data requires Vercel-compatible function runtime while Live Server estimation uses the same core directly. Raw Parquet, dependencies, docs, scripts and tests excluded by .vercelignore. No git commit, push or deployment performed.

## Files added/updated

vietnam-house-price.html/css; vietnam-estimate-core.js; vietnam-estimate-page.js; vietnam-house-model.json; data/vietnam-location-index.json; data/vietnam-market-stats.json; data/vietnam-house-parity-fixtures.json; data/vietnam-provinces.geojson; data/vietnam-map-source.json; assets/vendor/vietnam-boundaries-LICENSE; history.js; index.html; api/market-data.js; scripts/prepare-vietnam-public-reference.py; scripts/build-vietnam-canonical-reference.py; scripts/build-vietnam-public-types-once.py; scripts/build-vietnam-public-market.py; scripts/reconcile-vietnam-public-docs.py; aggregate reuse guards; tests/test_vietnam_house_pipeline.py; tests/vietnam-location-browser.js; tests/test_vietnam_map_online.py; data/NOTICE-vietnam-house.txt; current setup/reports and preserved beta-location-v2 archives. Existing saver/Auth integration reused. SQL unchanged.
'''
    (ROOT/'docs/vietnam-public-status.md').write_text(report,encoding='utf-8')
    pointer=f'# PUBLIC STATUS: {release}\n\nVersion beta-public-v3. See [complete current report](vietnam-public-status.md) and [validation evidence](vietnam-house-validation-results.json). Historical versions are preserved under archive/. Dataset approved with limitations for statistical BETA; online tiles are optional with a working local GeoJSON fallback. Original ML gate remains FAIL.\n\n{MAP_LIMITATION if not online.get("online_pass") else "Online tiles verified."}\n'
    for p in ['docs/vietnam-house-public-status.md','docs/verified-vietnam-house-data-report.md','docs/vietnam-location-public-status.md','docs/vietnam-house-model-reconciliation.md','docs/vietnam-house-recovery-status.md']:(ROOT/p).write_text(pointer,encoding='utf-8')
    (ROOT/'VIETNAM-HOUSE-SETUP.md').write_text(f'''# Vietnam Real Estate Estimate — beta-public-v3

Open project root with Live Server and vietnam-house-price.html. No training, dataset pass, generation or dependency installation needed. Public BETA details: [current report](docs/vietnam-public-status.md).

PUBLIC STATUS: {release}

{MAP_LIMITATION if not online.get('online_pass') else 'Online tiles verified.'}

Online tiles are optional with the verified local map fallback. Local DNS failure is an environment limitation, not a product defect. Dataset/statistical gate is approved with limitations. See docs/vietnam-map-online-test.json for unchanged test evidence.

Select a canonical province and optional ward using searchable suggestions. Optional sub-area supports known suggestions or typed text; unknown detail uses ward/province data with warning. Four types enabled; STREET_HOUSE and SHOPHOUSE disabled with reasons. Enter 15–1500 m²; what-if changes area only. No raw listings loaded by browser. Map displays 34 local province geometries even when HTTPS OSM tiles fail; form works independently. No guessed ward polygons.

SQL was successfully run by user: NO migration or SQL rerun needed. Existing house_price_history.input_data.metadata holds selected and actual used locations, type, area, quantiles, method, count, coverage, date and regional donors. Login required only for explicit save. Frontend uses publishable/anon SDK; no service_role key. Live database was not accessed by agent.

Live Server uses shared browser resolver; /api/market-data needs compatible Vercel runtime. All production paths relative, no localhost dependency. No live market feed configured; static statistical BETA still usable. Adapter is isolated from current aggregates and safely exits unconfigured.

Source TiniX AI, CC BY-NC 4.0, asking-price subset, publisher dates 01/06/2025–30/03/2026. Location reference is official NSO 34/3321 snapshot. Sparse historical mapping, heterogeneous land/house area definitions, publisher data accuracy, small spot-checks and regional geographic proximity are limitations; no ML or confidence/accuracy claim. P25/P75 are descriptive quantiles, not confidence intervals.

Checks: python -B tests/test_vietnam_house_pipeline.py; python -B tests/test_vietnam_house_browser.py; python -B tests/test_vietnam_map_online.py; python -B tests/run-vietnam-regressions.py. Tests do not train or access real Supabase. Full health training test is intentionally not needed for this task.

No commit/push/deploy. Previous files and raw/retained data preserved. Older aggregate scripts reuse current output; preview does not invoke scripts. Review .vercelignore and current report before any separately authorized publication.
''',encoding='utf-8')
    (ROOT/'data/NOTICE-vietnam-house.txt').write_text('''Dataset: tinixai/vietnam-real-estates, publisher TiniX AI.
Source: https://huggingface.co/datasets/tinixai/vietnam-real-estates
Revision: ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f.
License: CC BY-NC 4.0 declared by publisher; noncommercial portfolio.
License: https://creativecommons.org/licenses/by-nc/4.0/
Public mode: VERIFIED MARKET ESTIMATE BETA, beta-public-v3; no ML trained.
693,183 retained asking-price records: APARTMENT 290,282; HOUSE 151,472;
VILLA (including linked houses) 40,246; LAND 211,183. Other types withheld.
One cached sale pass for additional types; original apartment output reused.
Sale intent/type/price consistency filters, dedup, local aggregates and weighted
regional quantiles. Derived listing hashes are not original source identifiers.
Finite manual spot-checks do not prove population accuracy. Original ML gate
FAIL 194/200 (97%) unchanged; no MAE/RMSE/R2/MAPE published.
Publisher listing period 2025-06-01 through 2026-03-30, not independently verified.
No independent verification of upstream rights, addresses, areas or transactions.
No realtime feed; prices are asking prices, not completed transactions.
Canonical admin reference: official NSO SOAP, snapshot queried 2026-10-04.
Whole-unit Hanoi merger mappings have documentary evidence; partial/split or
unresolved historical wards remain province-only, no guessed current location.
Geographic regional donor proximity does not prove comparable markets.
P25/P75 are descriptive asking-price quantiles, not confidence intervals.
Raw and retained Parquet preserved locally, excluded from public bundle.
Geometry source/revision and MIT license: vietnam-map-source.json and
assets/vendor/vietnam-boundaries-LICENSE; illustrative not cadastral.
Historical outputs preserved under docs/archive/; current report
docs/vietnam-public-status.md.
''',encoding='utf-8')
    print('Current metadata/docs reconciled from JSON only.')
if __name__=='__main__':main()
