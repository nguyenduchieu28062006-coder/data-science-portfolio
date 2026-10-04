# Vietnam Real Estate Market Estimate — beta-location-v2

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
