# Vietnam Real Estate Estimate — beta-public-v3

Open project root with Live Server and vietnam-house-price.html. No training, dataset pass, generation or dependency installation needed. Public BETA details: [current report](docs/vietnam-public-status.md).

PUBLIC STATUS: READY WITH MAP FALLBACK

OpenStreetMap online tiles could not be verified in the current local environment because tile.openstreetmap.org did not resolve. The application automatically falls back to a local Vietnam GeoJSON map, so location selection and estimation remain usable.

Online tiles are optional with the verified local map fallback. Local DNS failure is an environment limitation, not a product defect. Dataset/statistical gate is approved with limitations. See docs/vietnam-map-online-test.json for unchanged test evidence.

Select a canonical province and optional ward using searchable suggestions. Optional sub-area supports known suggestions or typed text; unknown detail uses ward/province data with warning. Four types enabled; STREET_HOUSE and SHOPHOUSE disabled with reasons. Enter 15–1500 m²; what-if changes area only. No raw listings loaded by browser. Map displays 34 local province geometries even when HTTPS OSM tiles fail; form works independently. No guessed ward polygons.

SQL was successfully run by user: NO migration or SQL rerun needed. Existing house_price_history.input_data.metadata holds selected and actual used locations, type, area, quantiles, method, count, coverage, date and regional donors. Login required only for explicit save. Frontend uses publishable/anon SDK; no service_role key. Live database was not accessed by agent.

Live Server uses shared browser resolver; /api/market-data needs compatible Vercel runtime. All production paths relative, no localhost dependency. No live market feed configured; static statistical BETA still usable. Adapter is isolated from current aggregates and safely exits unconfigured.

Source TiniX AI, CC BY-NC 4.0, asking-price subset, publisher dates 01/06/2025–30/03/2026. Location reference is official NSO 34/3321 snapshot. Sparse historical mapping, heterogeneous land/house area definitions, publisher data accuracy, small spot-checks and regional geographic proximity are limitations; no ML or confidence/accuracy claim. P25/P75 are descriptive quantiles, not confidence intervals.

Checks: python -B tests/test_vietnam_house_pipeline.py; python -B tests/test_vietnam_house_browser.py; python -B tests/test_vietnam_map_online.py; python -B tests/run-vietnam-regressions.py. Tests do not train or access real Supabase. Full health training test is intentionally not needed for this task.

No commit/push/deploy. Previous files and raw/retained data preserved. Older aggregate scripts reuse current output; preview does not invoke scripts. Review .vercelignore and current report before any separately authorized publication.
