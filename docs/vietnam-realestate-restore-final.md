# Real Estate V1 restored; V2 visual map retained

Audit date: 2026-10-08.

V1 source: `7df25a7a3d1b30addf667bed131cfbc4d9674440` (HEAD).
The Real Estate implementation in that snapshot was introduced at `cea69b6`.

The estimate core, market API, model, location index, price aggregates,
Auth/History and history save script match the Git V1 snapshot. The V1 form,
result renderer, search, what-if calculation, explorer and event handlers are
unchanged. Users select a location, property type and area, then estimate using
V1's existing data. Sale price, comparables and CSV/XLSX input are not required.

Only the map section, scoped map styles and map initialization/synchronization
were adapted. `vietnam-commune-map.js` keeps the actual V2 Leaflet map, OSM
background, province/commune polygons, colors, hover tooltips, click selection,
zoom, back control, commune search/list, bounded cache and download fallback.
It no longer references the V2 price result renderer or V2 valuation API.
Map callbacks pass through V1's original `selectLocation` function; the map's
commune code `00466` maps to V1 ward ID `vn_00466`, for example.

Map dependencies retained:

- Existing local Leaflet and province GeoJSON.
- `data/vietnam-administrative-v2.json`: map-only code/name dictionary.
- `data/vietnam-commune-map-source.json`: provenance, license and file hashes.
- `data/vietnam-communes/*.geojson`: verified snapshot, loaded by viewed province.
- `scripts/build-vietnam-commune-map.py`: explicit map snapshot refresh utility.

All 3,321 codes join to V1's existing canonical IDs with no province mismatch.
V2 valuation/import runtime, its deployment function and its inactive UI were
removed. Replaced/removed files were backed up outside the repository at
`%TEMP%/realestate-v1-restore-backup`. No Git index or other module was changed.

Validation:

- `tests/test_vietnam_house_pipeline.py`: 8 checks passed.
- `tests/test_vietnam_restore.py --browser`: 84 checks per width at
  320/390/768/1440px, including original V1 estimate, search, what-if,
  explorer, API, and authenticated/guest History flows using a memory SDK mock.
- 250 original parity fixtures per width: maximum difference **0 VNĐ**.
- `tests/test_vietnam_commune_map.py --browser`: 259 assertions at
  320/390/1440px; actual touch/click, Phúc Thịnh/Thư Lâm, all 34 province joins,
  form synchronization, cache, rapid switching and download fallback passed.
- SHA-256 and code/name checks passed for all 3,321 real polygons.
- Original V1 HTML/CSS/logic and unrelated tracked files were checked against
  Git/task baseline. No estimate algorithm was rewritten.
- `tests/test_vietnam_public_paths.py`: 83 local references passed.
- `git diff --check`: passed.
- `npx vercel build`: passed; Preview deployment cloud build also passed.

Preview: https://data-science-portfolio-25vsj9nkq-nguyen-duc-hieu2.vercel.app

Preview deployment: `dpl_CiF9Vr8N5wN7RHHDADDkT83peyTN`.
Production URL is null; Vercel authentication protection remains enabled.
Preview verification passed: deployed V1 estimate/data/Auth/History assets match
local files byte for byte, the V1 market API returns the original price, and
259 map/estimate assertions plus real tap/click passed at 320/390/1440px.
All 34 provinces were exercised on Preview; no module console/JS errors or
horizontal overflow were observed. History writes were tested with a memory
SDK mock locally; no real user history rows were written or deleted.
Final status: **READY**. V2 visual map preserved: **YES**.
No staging, commit, push or production deployment was performed.
