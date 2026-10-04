# PUBLIC STATUS: READY WITH MAP FALLBACK

Version beta-public-v3, 04/10/2026. APPROVE WITH LIMITATIONS for a noncommercial descriptive asking-price portfolio. No ML model trained; original ML gate remains FAIL, 194/200=97%. No MAE/RMSE/R²/MAPE, no completed transaction or current price claim.

Publication blocker: none. Online map tiles are optional when the local GeoJSON fallback and independent location selection/estimation remain usable. The local DNS failure is an environment limitation, not a product defect.

Map limitation: OpenStreetMap online tiles could not be verified in the current local environment because tile.openstreetmap.org did not resolve. The application automatically falls back to a local Vietnam GeoJSON map, so location selection and estimation remain usable.

| Required item | Result |
|---|---|
| 1. Canonical provinces | 34 |
| 2. Canonical wards | 3,321 current official codes |
| 3. Known sub-areas | 75 publisher projects within safely mapped wards |
| 4. Enabled types | APARTMENT, HOUSE, VILLA, LAND |
| 5. Disabled types | STREET_HOUSE: type ambiguity in spot-check; SHOPHOUSE: sale/rental price ambiguity |
| 6. Verified rows | 693,183; apartments 290,282 unchanged; new published subset 402,901 |
| 7. Sub-area stats | 46 eligible / 75 total |
| 8. Ward stats | 65 eligible / 103 total across types; 27 distinct current wards |
| 9. Province stats | 82 eligible / 126 total across types |
| 10. Regional fallback | 54 transparent same-type donor aggregates; 82+54=136 province/type combinations covered |
| 11. Map online | UNVERIFIED due to local DNS; non-blocking with working fallback; see vietnam-map-online-test.json; no synthetic tiles |
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
| APARTMENT | 762800 | 290282 | 290282 | 27 | 27 | 75 | ENABLED |
| HOUSE | 1575536 | 151472 | 151472 | 34 | 27 | 0 | ENABLED |
| STREET_HOUSE | shared HOUSE source | 34129 | 0 | 0 | 0 | 0 | DISABLED |
| VILLA | 269782 | 40246 | 40246 | 31 | 24 | 0 | ENABLED |
| LAND | 832766 | 211183 | 211183 | 34 | 25 | 0 | ENABLED |
| SHOPHOUSE | 59860 | 8854 | 0 | 0 | 0 | 0 | DISABLED |

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
