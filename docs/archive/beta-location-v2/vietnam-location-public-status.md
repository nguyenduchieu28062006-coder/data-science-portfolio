# PUBLIC STATUS: READY — statistical BETA with limitations

Version: `beta-location-v2`, 04/10/2026. This approval applies to the descriptive apartment estimator, not an ML model, completed transactions, current market prices, or independently verified addresses. No new training, full audit, bulk scraping, commit, push or deployment occurred.

| Required item | Current result |
|---|---|
| 1. ENABLED types | APARTMENT — Căn hộ chung cư |
| 2. DISABLED types | HOUSE, STREET_HOUSE, VILLA, LAND, SHOPHOUSE |
| 3. Provinces | 27 with records; 19 have at least 80 samples |
| 4. Wards/communes | 730 scoped historical source labels; 396 meet 30 samples |
| 5. Sub-areas | 2,372 project-within-ward groups; 1,340 meet 20 samples |
| 6. Project/building | 2,372 PROJECT groups; no independently structured BUILDING/HAMLET/NEIGHBORHOOD fields, none invented |
| 7. Verified rows | 290,282, unchanged canonical apartment IDs |
| 8. Exact sub-area statistics | 2,372 records, 1,340 eligible; descriptive price/m² quantiles |
| 9. Ward statistics | 730 records, 396 eligible |
| 10. Province statistics | 27 records, 19 eligible |
| 11. Thresholds | SUB_AREA 20, WARD 30, PROVINCE 80; HIGH ≥1,000, MEDIUM ≥200, LOW if eligible below 200, otherwise INSUFFICIENT |
| 12. Map | Leaflet 1.9.4 + OpenStreetMap; 3 sourced city representative points, no ward/project coordinates, polygons or invented heat surfaces |
| 13. API | Shared exact resolver, unknown location → NONE/no price, known sparse selections disclose fallback; live_connected=false |
| 14. History | Exact selection, used location, resolution, count, coverage, method, date and P25/P75 stored in input_data.metadata; optional inputs separate |
| 15. Same-city test | Three Hanoi wards resolve distinct WARD statistic keys; medians 118,412,942.99 / 77,479,338.84 / 87,847,490.35 VND/m² |
| 16. Invalid location test | Unknown province/ward/project/legacy district rejected; pending autocomplete blocks submit; sparse known selections alone may fallback |
| 17. Added files | Shared core/page JS; location/map JSON; enrichment + aggregation scripts; pinned Leaflet assets/license; location browser runner; enrichment, gate/count and upgrade reports |
| 18. Updated files | Page HTML/CSS, model metadata, static stats/parity, API, history saver/rendering, Home title, existing browser/pipeline tests, updater/legacy aggregate guard, setup/current reports; old JS archived and retired |
| 19. SQL migration | No location migration. Existing house_price_history JSON column suffices. If the table is absent, run supabase/vietnam-house-price.sql once. SQL has not been executed against a real project here |
| 20. Live Server | Open project root with Live Server, then vietnam-house-price.html. All estimation/search/map and static statistics run locally; Vercel API requires a compatible function runtime, not plain Live Server |

Threshold analysis was performed once over the verified enriched dataset. Group sample-count quartiles: province 26.5 / 232 / 1,001.5; ward 6 / 41 / 269.5; project 4 / 29 / 103. Thresholds balance observed sparsity and descriptive granularity; they are not guarantees of accuracy. Sparse groups stay in the location index so their explicit fallbacks can be explained.

Property type evidence is in `vietnam-location-upgrade-report.json`: apartment raw 762,800, retained 290,282, reviewed 72/72; HOUSE raw 1,575,536, candidate 521,217, reviewed 109/115 (94.78%); combined villa/terraced raw 269,782, candidate 76,163, reviewed 13/13 (too small and combined semantics); land raw 832,766 and shophouse raw 59,860 have no approved subset. The source has no separate street-house category, so its raw_rows is null rather than an invented count. Disabled-type verified geographic counts are zero because none are published. The apartment observations are members of the previous uniform mixed sample, not an independent 200-row type gate or proof of population accuracy. The original mixed ML gate remains FAIL at 194/200 (97%).

The enrichment matched all 290,282 existing hashes using 762,800 apartment records in the read-only cached audit database. It did not read raw Parquet shards or rerun sale/price rules. 1,089 IDs had conflicting project metadata across duplicates and their project fields were withheld. 52,044 records have no usable ward. 28,924 records have a project but no ward and contribute only to province statistics. Canonical data and all existing raw files remain unchanged; the local enriched Parquet is ignored by Git and excluded from public bundles.

Location names are structured publisher claims. They have not been independently confirmed against current legal ward boundaries or listing addresses. Ward IDs include province + historical district + normalized ward; project IDs include ward + normalized project, preventing duplicate names from merging across districts. Normalization uses NFC, whitespace and case-insensitive exact matching; ambiguous names require an ID or full ward label. No prefix stripping, fuzzy matches, guessed current wards or parsed project names.

Formula: area × median asking price/m² from the finest eligible group. P25/P75 totals are area × corresponding asking-price quantiles, not confidence intervals. All statistical keys include property type. Other physical features and legal status do not affect the formula. This is not investment advice or a professional valuation.

Data source: TiniX AI, `tinixai/vietnam-real-estates`, revision `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`, publisher-declared CC BY-NC 4.0, noncommercial portfolio use. Period: 01/06/2025–30/03/2026, publisher listing timestamps, not verified collection timestamps. TiniX is not asserted to be the original transaction website; upstream provenance and rights were not independently established. MAE/RMSE/R²/MAPE, train/test split and training date are not applicable.

Map anchors use reviewed [Hanoi](https://www.wikidata.org/wiki/Q1858), [Ho Chi Minh City](https://www.wikidata.org/wiki/Q1854), [Da Nang](https://www.wikidata.org/wiki/Q25282) coordinate claims. These are representative city points rather than centroids of merged provinces. Only province statistics appear on markers. Finer dropdown selections zoom to an available coarse anchor with a visible notice; other provinces have no guessed coordinates. Leaflet is pinned according to its [official download documentation](https://leafletjs.com/download.html), with SHA256 checks and the library license retained. Tiles need internet; dropdown estimation does not depend on map tiles.

Frontend ships only metadata and 3,129 aggregate groups: location index approximately 479 KB and statistics 1,170 KB, no raw listings. Exact payload sizes are recorded in `vietnam-location-upgrade-report.json`. The complete aggregates also support the local API fallback through the same resolver. Future approved feeds write a separate staging file and cannot overwrite schema2 estimator statistics. No live feed is connected, no live figures are invented, and this does not block the static BETA.

Validation: 71 browser checks at each of 320/390/768/1440; 250 retained-record Python/JS parity fixtures with 0 VND difference; API tests execute the actual function with module data supplied locally. Auth regression 168 checks and Health History 15 checks per viewport. Health Prediction 57/59 checks per viewport, its original sample outputs (~34.2% and ~99.6%) remain unchanged. Browser database tests use a mock SDK; real Supabase SQL/RLS and real Vercel hosting remain unexecuted. See `vietnam-house-validation-results.json` for current evidence. Home/Analyzer/Health retain their separate behavior; Analyzer content checked against HEAD ignoring the pre-existing terminal newline difference.

Added in this upgrade: `vietnam-estimate-core.js`, `vietnam-estimate-page.js`, `data/vietnam-location-index.json`, `data/vietnam-map-coordinates.json`, `scripts/enrich-vietnam-locations.py`, `scripts/build-vietnam-location-stats.py`, `scripts/fetch-leaflet-assets.py`, `scripts/reconcile-vietnam-location-docs.py`, `tests/vietnam-location-browser.js`, `assets/vendor/leaflet/{leaflet.js,leaflet.css,LICENSE}`, `docs/vietnam-property-raw-counts.json`, `docs/vietnam-location-enrichment.json`, `docs/vietnam-location-upgrade-report.json`, this report, and local ignored `data/verified-vietnam-house-locations.parquet`. Earlier beta-v1 code/docs were copied into `docs/archive/beta-v1/` before retirement/reconciliation.

Updated in this upgrade: `vietnam-house-price.html`, `vietnam-house-price.css`, `vietnam-house-inference.js`, `vietnam-house-price.js`, `vietnam-house-model.json`, `vietnam-house-history-save.js`, `api/market-data.js`, `history.js`, `history.html` (module navigation label), `index.html`, `data/vietnam-market-stats.json`, `data/vietnam-house-parity-fixtures.json`, `data/NOTICE-vietnam-house.txt`, `scripts/update-vietnam-market.py`, `scripts/build-vietnam-market-stats.py`, both existing Vietnam browser/pipeline tests, `VIETNAM-HOUSE-SETUP.md`, the current data summary/cleaning/training/validation reports and their public status/data report links. `auth.js` and the Analyzer newline diff were already modified on recovery and were not edited by this upgrade. No Health implementation or model files were edited.

Live Server steps: select a source sample and estimate; choose three wards and compare resolution/used location; choose a sparse project and check warning; type an unmatched search string and verify disabled estimate; click a map marker and inspect province-only selection; sign in and explicitly save exact and fallback results after setting up the existing SQL; inspect History details. Market connection text must remain “Dữ liệu thị trường cập nhật tự động chưa được kết nối.”
