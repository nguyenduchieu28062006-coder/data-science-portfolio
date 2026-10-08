# Sales Forecasting methodology

This stateless module predicts one selected sales series from uploaded CSV/XLSX or a clearly labeled synthetic input. All displayed models, metrics, forecasts and diagnostics are computed from that input. The sample has 1,096 daily observations with trend, weekly seasonality, annual variation, noise and occasional promotion spikes. No forecast results are hardcoded.

## Input and cleaning

CSV accepts UTF-8/BOM and comma, semicolon, tab or pipe delimiters. XLSX uses read-only openpyxl with sheet selection and cached formula values; formulas are never executed. Blank rows/columns are removed, headers trimmed and deduplicated, exact duplicate records removed. A selected group is filtered before temporal aggregation. Invalid dates and missing/invalid numeric targets are dropped and counted. Most invalid dates/targets cause a 422 validation error. At least three valid aggregated periods are required.

ISO dates/timestamps, YYYY/MM/DD, YYYY-MM, DD/MM/YYYY, DD-MM-YYYY, sufficiently evidenced MM/DD/YYYY, Excel datetimes and serial dates are supported. Offset timestamps are converted to UTC; naive timestamps retain their clock time. Dates with ambiguous day/month order require the user to choose an interpretation; mixed conflicting orders must be normalized to ISO. Lone separators with three following digits (1,234 / 1.234) also require an explicit number convention. The UI supports dot-decimal and comma-decimal formats including thousands separators and negative returns. Missing tokens include empty, NA, N/A, null, None, nan, - and --. Nonfinite or excessively large numeric values are rejected.

## Frequency, aggregation and data quality

Sorted unique timestamps are examined for calendar alignment and modal time deltas. Hourly, daily, weekly, monthly and quarterly grids are supported. The inferred frequency, source interval and confidence are reported. `interval=1` refers to the normalized grid; larger source gaps become missing periods. Confidence below 0.8 warns about irregularity. Users can override the grid. Hourly buckets start at the hour; weeks start Monday; months and quarters start on their calendar first day. Future months/quarters advance by calendar months rather than a fixed number of days. All sales aggregation uses SUM.

Missing periods are filled with zero and explicitly reported. This assumes absence of a record means zero sales, which is unsuitable for missing sensor measurements or incomplete reporting. No two-sided interpolation is offered, so resampling cannot inject future values into past target features. Exact duplicate removal assumes a repeated full record is accidental; indistinguishable legitimate transactions need a unique identifier column to avoid removal. Anomalies are flagged using a robust score on the detrended series and retained in training.

Quality includes history span, observation count, missing periods, duplicate removal, mean, median, standard deviation, minimum, maximum and trend. The trend is a descriptive least-squares line, not causal evidence. Seasonality uses detrended lag correlation with at least three cycles; correlation of at least 0.5 is labeled Detected, lower evidence Weak, and insufficient history Not enough data. This is exploratory evidence rather than a hypothesis test.

## Features and temporal validation

Calendar features: time index, year, month, quarter, day, weekday, ISO week, weekend and hour. Lag features start with 1/2/3 and frequency-appropriate seasonal lags. Rolling means use available 3/7/12 windows and rolling standard deviations 3/7. The schema is fixed from the smallest training window, independent of holdout targets. Features at time t consume the exclusive history prefix `y[:t]`: rolling is equivalent to shift(1) followed by rolling. Training matrix construction uses vectorized prefix sums; tests compare it against the exclusive-prefix reference implementation.

There is no random train/test split, shuffled KFold or shuffled inner early stopping. The last approximately 20% (maximum 90 periods) is the final holdout. All ranking folds occur before it. Expanding-window validation uses 5 folds for at least 300 observations, 3 for 60–299, 2 for 24–59, and a separate inner validation block for 12–23. Block length is adaptive, limited by the requested horizon, available history and 60 steps. The evaluation report records exact fold boundaries and the ranking source. Folds are consecutive and train always precedes validation. Each validation block is forecast recursively without consuming its observed target values between steps. Scaling is refit inside each train fold.

Below 12 periods, Naive produces an explicitly exploratory forecast without a fabricated leaderboard score, independent holdout or uncertainty interval. The 12–23 regime can skip ML models when fewer than 8 train rows remain after warmup. A model that lacks enough history is skipped without failing the request.

## Models, metrics and selection

Naive repeats the last observed value. Seasonal Naive recursively repeats the frequency's canonical cycle (24 hours, 7 days, 52 weeks, 12 months, 4 quarters), requiring at least two cycles in the smallest training window. It remains a benchmark even when descriptive seasonality evidence is weak.

Linear Regression and Ridge use standardized lag/calendar/rolling features. Random Forest uses 32 trees, maximum depth 9, minimum leaf size 3, seed 42 and one worker. Gradient Boosting uses 45 trees, depth 2, minimum leaf size 3 and seed 42. Hist Gradient Boosting uses 50 iterations and 15 leaves with early stopping disabled to avoid randomized internal validation. There is no heavy tuning or added runtime dependency.

Metrics are MAE, RMSE, sMAPE, MAPE and R². MAPE is N/A when any actual is zero. sMAPE gives zero error to pairs where actual and prediction are both zero. R² is N/A for constant or fewer than two actual observations. Fold metric means are unweighted; RMSE standard deviation describes variation between origins. Ranking uses mean backtest RMSE, then mean MAE. With one inner fold, the ranking source is `inner_validation_rmse`; this block remains distinct from final holdout.

Selection is frozen before holdout evaluation. Leaderboard holdout metrics are descriptive and never used for ranking. Backtest improvement over Naive below 5% produces a warning. A zero-error Naive baseline yields N/A improvement, avoiding division by zero. Tests include opposed backtest/holdout rankings and an end-to-end mutation of only holdout targets proving ranking stays unchanged.

## Recursive future forecast and intervals

The selected model is refit on all historical observations before generating 1–90 future periods. Each prediction is appended to the recursive history for the next step. No unknown target is used. If refitting fails, the forecast falls back to Naive with a clear warning and distinct `forecast_model`, while retaining the originally selected `best_model`.

Estimated forecast intervals use the selected forecasting model's absolute backtest residual quantiles at 0.80 and 0.95, placed symmetrically around each forecast. This guarantees ordered nested intervals containing the point estimate. Beyond the validated block length, widths grow by `sqrt(step / validated_steps)`; this is a conservative heuristic, not calibrated probability coverage. Residuals from different forecast leads are pooled; changing distributions and dependent errors can invalidate nominal coverage. Fewer than 30 residuals produces a warning. With no independent residuals, interval fields are null and the UI explains their absence. Holdout errors do not calibrate intervals or choose models.

Point estimates are not clipped by default. The optional nonnegative clamp only applies if all historical targets are nonnegative; any actual clipping is reported. Historical negative returns disable it. Interval endpoints stay symmetric and may be negative even when point estimates are clamped; they are not blindly clipped to zero.

## Interpretation, privacy and limits

Forecast insights use the actual predicted total, mean, extrema and change versus the previous equally long history segment. Change is N/A if the previous segment is unavailable or zero. Reliability is High only for at least 120 observations, relative backtest RMSE below 0.15, fold std/RMSE below 0.3 and horizon/history at most 0.15; Medium requires at least 60, relative RMSE below 0.4, stability below 0.7 and horizon/history at most 0.3; otherwise Low. This is a heuristic, not a probability.

Tree importance is impurity importance; linear importance is absolute coefficients on standardized features. Neither establishes causality. Hist Gradient Boosting and baseline models gracefully omit importance. Final holdout residuals describe actual minus prediction, mean bias, MAE and RMSE. No exogenous future promotions, stockouts, holidays or regime changes are modeled.

Uploads and models remain in memory, including the worker stdin. No database, Supabase, auth requirement, stored history or persisted raw upload exists. Forecast CSV uses UTF-8 BOM, CRLF and escaped cells with formula-injection protection for text. JSON contains metadata, quality, series, leaderboard, metrics, forecasts, intervals and warnings rather than the raw uploaded table.

Limits: 2 MiB file, 4 MiB JSON request, 50,000 source rows/regularized periods, 60 columns, 1.5 million cells, 40 sheets, 500 selectable groups, 25 MiB XLSX expanded contents and 1,000 zip entries. XLSX bounds are checked before opening. Exact duplicate records are removed before SUM. Chart min/max sampling bounds SVG rendering to approximately 700 path vertices per line; the backend, state and downloads retain all data.

The HTTP forecast runs in a subprocess killed after 55 seconds; function maxDuration is 60. The soft budget is 45 seconds, reserving time for evaluation/refit/forecast. Budget checks occur between models and recursive steps, not during a native fit; the hard worker deadline bounds an individual hung fit. Failed/budget-limited models return safe statuses and a partial leaderboard. Baseline remains available. Dependent numpy/BLAS/OpenMP pools are limited to one thread. Long histories can exhaust the budget; no silent training subsampling occurs.

## Verification

Run `python -B tests/test_sales_forecasting.py` for backend, real worker HTTP and browser checks. `--backend-only`, `--browser-only`, and `--cloud <preview-url>` isolate stages. Fixtures are generated in tests; screenshots/reports use the OS temporary directory. Browser checks cover actual sample training, uploads, sheet/group choices, all charts, model details, downloadable contents, inline failures, request guards and widths 320/390/768/1024/1440. Smoke checks load all existing modules and follow Home/module links.

For a protected Preview, supply `VERCEL_AUTOMATION_BYPASS_SECRET` through the environment, or set `SALES_QA_VERCEL_CLI` to an already authenticated Vercel CLI's `dist/vc.js` and optionally `SALES_QA_NODE` to its Node executable. The harness captures CLI diagnostics only in memory, extracts the existing bypass header without printing it, and sets an origin-scoped browser cookie. It does not add authentication headers to requests for external CDN resources. Deployment Protection settings remain enabled. Cloud reports and screenshots contain no credentials.

Reference: [scikit-learn 1.8 lagged time-series example](https://scikit-learn.org/1.8/auto_examples/applications/plot_time_series_lagged_features.html) explains the bias of random splitting and temporal validation. This module additionally evaluates whole blocks recursively rather than feeding true targets from inside the validation block.
