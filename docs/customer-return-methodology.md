# Customer Return Prediction / Customer Retention Intelligence

Module public: `customer-return.html`. This project predicts an **observed repeat
purchase within 60 days**, rather than permanent loyalty or subscription churn.
Inputs and prediction remain in the browser. No customer data is stored, no shared
History schema is added, and no campaign is sent automatically.

## Data and provenance

| Item | Value |
| --- | --- |
| Dataset | Online Retail, UCI dataset 352 |
| Creator | Daqing Chen, donated 2015 |
| Source | [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online%2Bretail) |
| DOI | [10.24432/C5BW33](https://doi.org/10.24432/C5BW33) |
| License | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Original shape | 541,909 transaction lines × 8 columns |
| Source interval | 2010-12-01 08:26:00 to 2011-12-09 12:50:00 |
| Clean product lines | 390,859 |
| Clean customers / invoices | 4,334 / 18,401 |
| Derived snapshots | 11,606 rows × 11 columns, with 7 model inputs |

The source describes UK non-store gift retail, including many wholesalers.
Amounts are GBP; the model is not validated for Vietnamese prices or another
business. The official ZIP is downloaded to temporary storage, not shipped with
the public website. The adapted cohort CSV carries pseudonymous SHA-256 keys for
grouping; these keys never enter the model or browser samples.

Official ZIP SHA-256:
`f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`

XLSX SHA-256:
`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`

## Audit and cleaning

Audit the actual downloaded file; the source website's missing-value flag is not
treated as a substitute for inspection. Missing CustomerID: 135,080; missing
Description: 1,454. Other source columns have zero missing values.

Exclusions below are sequential and therefore do not double-count a row:

| Rule | Excluded rows |
| --- | ---: |
| Exact duplicate rows | 5,268 |
| Missing customer or date | 135,037 |
| Cancelled invoices (`C` prefix) | 8,872 |
| Nonpositive/missing quantity or price | 40 |
| Non-product lines | 1,833 |
| Missing country | 0 |

Product codes must match `^\d{5}[A-Za-z]?$`. This excludes postage, adjustments and
discount lines. A purchase is an identified, non-cancelled product invoice with
positive quantity and unit price. Later returns do not retrospectively change a
historical feature or purchase label: that would use information unavailable at
the scoring date. Thus the target measures observed purchase, not net retained
revenue after returns.

Keep legitimate large/wholesale transactions rather than trimming future-derived
quantiles. Apply log1p to nonnegative numeric inputs and standardize using train
only. Full missing counts, source ranges, country frequencies, training feature
ranges and exclusion counts are recorded in
[the machine-readable report](customer-return-model-report.json).

## Target, features and temporal split

At cutoff `t`, eligible customers have at least one valid purchase before `t`.
Class 1 means at least one valid purchase in `[t, t + 60 days)`. Class 0 means no
observed valid purchase in that window. Cold-start customers are out of scope.

| Input | Definition at scoring date |
| --- | --- |
| recency_days | Whole days since most recent historical valid invoice |
| tenure_days | Whole days since first observed valid invoice |
| orders_90d | Distinct invoices in `[t − 90 days, t)` |
| monetary_90d | Positive product revenue in that window, GBP |
| products_90d | Distinct valid StockCode values in that window |
| avg_purchase_gap_days | Mean gap between all historical invoices; 0 if only one invoice |
| country | Last historical country; one-hot categories fit only on train |

No invented satisfaction, complaint, support, discount or campaign features.
Customer ID/key, future transactions and the target are excluded from features.
Tenure is left-censored at dataset start: it is observed purchase tenure, not a
verified registration date. Recent purchase frequency and monetary are raw
aggregates, not subjective scorecards.

| Split | Cutoffs | Rows | Class 0 | Class 1 | Unique customers |
| --- | --- | ---: | ---: | ---: | ---: |
| Train | 2011-04-01, 2011-06-01 | 4,848 | 2,765 | 2,083 | 2,716 |
| Calibration | 2011-08-01 | 1,560 | 933 | 627 | 1,560 |
| Model/threshold selection | 2011-08-01 | 1,585 | 929 | 656 | 1,585 |
| Held-out test | 2011-10-01 | 3,613 | 1,905 | 1,708 | 3,613 |

Calibration and selection are disjoint customer groups within the earlier August
cohort (deterministic hash parity). All June training labels mature before August;
all August labels mature before October. Test outcomes finish at 2011-11-30,
before the source ends. No random transaction split is used.

The same customer may appear at different dates, as in deployment to an existing
customer base; the model has no ID feature. Snapshot rows are correlated, so
unique-customer counts are reported. A temporal stability check trains only on
April, then evaluates June, with April-only preprocessing.

No test resampling. Class 1 prevalence is 42.97% in train and 47.27% in test;
PR-AUC, macro-F1 and class-specific precision/recall supplement accuracy. Natural
prevalence is retained, without class weights that would alter probability priors.

## Comparison and frozen model selection

All candidates use identical real inputs and training-only preprocessing. For
each, fit a sigmoid calibrator on the separate calibration cohort; keep it only
if selection-cohort Brier improves over the raw model.

| Candidate | Validation ROC-AUC | PR-AUC (AP) | F1 | Brier | April→June AUC | Estimator JSON bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.732207 | 0.694153 | 0.635225 | 0.200270 | 0.726942 | 891 |
| Random Forest | 0.746749 | 0.713144 | 0.608197 | 0.195618 | 0.745846 | 797,626 |
| **Gradient Boosting** | **0.750489** | **0.714351** | **0.631179** | **0.195000** | **0.747509** | **46,366** |

Selection rule is declared in the training script: prefer LR, then GB, then RF
if within 0.015 ROC-AUC, 0.02 average precision and 0.01 Brier of the best
selection results. If none qualify jointly, use ROC-AUC + AP − Brier. LR misses
the ROC-AUC tolerance. GB offers better discrimination/calibration than RF here
and a much smaller artifact. Selection never uses held-out test metrics.

Final: GradientBoostingClassifier, 140 trees, depth 2, learning rate 0.04,
minimum leaf size 25, random_state 42. Numeric transform: log1p + StandardScaler;
35 train-country indicators. Export includes every split, threshold, value,
feature order, scaler, categories, version and calibration parameters.

Sigmoid calibration uses raw GB margin:
`p = sigmoid(0.9843683705531893 × margin − 0.14633054252847638)`.
This is an explicitly exported calibrator fit on the calibration cohort, not an
adjustment based on test outcomes.

## Held-out metrics and probability limits

| Metric | October test |
| --- | ---: |
| Accuracy | 0.670634 |
| Precision, class 1 | 0.687139 |
| Recall, class 1 | 0.556792 |
| F1, class 1 | 0.615136 |
| ROC-AUC | 0.728352 |
| PR-AUC | 0.733974 |
| Brier Score | 0.214076 |
| ECE, 10 equal-width bins | 0.087397 |
| Constant train-prevalence Brier | 0.251112 |

Confusion matrix, rows actual and columns predicted, in order `[0,1]`:
`[[1472, 433], [757, 951]]`.

PR-AUC is **average precision**, the non-interpolated weighted precision/recall
area, not trapezoidal interpolation. The UI also shows actual ROC/PR curves and
calibration bins from the held-out predictions.

**CALIBRATION: WARNING.** The operational check requires ECE ≤ 0.05 and Brier
better than the constant training-prevalence baseline. Brier improves, but ECE
does not pass. Holiday-period test customers buy more often than forecast across
the bins. The UI warns beside each result, not only in methodology. No model
retuning on test is performed to hide this limitation. Probabilities are checked
estimates, not guaranteed frequencies for another retailer. Recalibrate on a new
held-out cohort from the intended business and re-evaluate before budget use.

## Classification and recommendation bands

Classification threshold **0.38** maximizes macro-F1 over 0.10–0.90 in steps of
0.01 on selection; ties prefer proximity to 0.50. This weighs the two classes
equally without inventing campaign costs. The complete precision/recall/F1/Brier
threshold comparison is in the report. A real business should choose its
threshold from measured cost, margin and campaign performance.

Recommendation bands are frozen from the selection probability distribution:

| Band | Rule | Selection rows | Observed return rate |
| --- | --- | ---: | ---: |
| Low | `p < 0.2302687157944977` | 520 | 18.65% |
| Medium | Between low and high boundaries | 536 | 38.81% |
| High | `p >= 0.4536477550365929` | 529 | 66.35% |

Low boundary = min(classification threshold, selection q33); high boundary =
max(classification threshold, selection q67). This keeps low below and high above
the model's class threshold. “High” describes relative position in this cohort,
not a universal promise above 70%. UI descriptions expose the boundaries and
warn about calibration. Bands are illustrative triage, not validated ROI policy.
No feature is treated as proven treatment sensitivity or campaign uplift.

High: protect experience, appropriate cross/upsell, loyalty, feedback/referral.
Medium: moderate offers, purchase reminders, recommendations, loyalty, surveys.
Low: controlled reactivation, relevant offers, after-purchase experience and
barrier reduction. Each action states its objective and how to measure it.
Recommendations require permission to contact customers and business A/B tests;
the website does not send any outreach.

## Local explanation and browser inference

For each tree, follow the customer's split path and sum the child-minus-parent
node values for each splitting feature. The root value is its reference score;
the changes telescope exactly to the terminal leaf value. Sum across trees with
the exported learning rate, add GB intercept, then scale every contribution and
the baseline by the sigmoid coefficient and add the calibration intercept.

Thus `baseline + sum(all feature contributions) = calibrated log-odds`.
Country indicator contributions are grouped back into the one country input.
Top 5 uses absolute magnitude; positive/negative direction is the actual model
score direction. This is **tree path decomposition**, not SHAP, percentage
uplift or causal attribution. Zero contributions are reported as zero.

Tree split inputs use float32, matching sklearn. Probability calculation uses a
stable sigmoid. The non-return probability is the exact complement. Display
rounding is paired in tenths so the two displayed labels total exactly 100.0%.
Unseen countries use all-zero country indicators with an explicit domain warning;
values outside train numeric ranges also trigger warnings.

250 actual, evenly spaced October customer vectors have saved Python sklearn
probabilities for an independent JavaScript parity check. The browser suite also
reconstructs the score from explanations and checks sample probabilities, all
three branches, invalid inputs, stale result clearing, charts, tooltips, metrics,
auth-aware public access, failure/reload and five responsive sizes.

## Reproduce

Tested with Python 3.12.6, numpy 1.26.4, pandas 2.3.3, sklearn 1.8.0. Use a separate
compatible Python environment; packages are listed in
`requirements-customer-return.txt`. Excel parsing uses the standard library.

PowerShell, from the project root:

```powershell
python -m pip install -r requirements-customer-return.txt
curl.exe -L --fail --max-time 600 -o "$env:TEMP/customer-return-online-retail.zip" "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
python -B scripts/train-customer-return.py --source "$env:TEMP/customer-return-online-retail.zip"
python -B tests/test_customer_return.py
```

`--audit-only` inspects the source without training/writing artifacts. Training
writes only customer-return model, cohort, report and parity artifacts. Browser
tests use a temporary local HTTP server and Edge/Chrome, an in-memory auth mock,
and temporary screenshots. They do not modify any production records.

## Calibration and temporal quality audit, October 2026

**BASELINE RETAINED.** The production JSON, inference, samples, cohort CSV,
250 sklearn parity fixtures, threshold, recommendation bands and public UI remain
byte-identical to the start of this audit. No candidate met the joint acceptance
criteria below. The existing ECE warning remains visible. This is a completed
comparison, not a claim that calibration improved.

The `quality_upgrade` object in the report contains all 20 trials, reliability
bins, threshold grids, fold results, acceptance gates and the frozen decision.
Production selection used only the existing August selection customers and
earlier rolling evaluations. Previously published October baseline metrics were
not inputs to the selector. The decision was written as `SELECTION_FROZEN`, with
a SHA-256 of model parameters, preprocessing, calibration, threshold and bands,
before the separate final-test command. Only the retained model was then scored
on October; rejected candidates were never scored there. The report now records
`FINAL_EVALUATED`, zero post-test selection changes, and zero rejected candidates
evaluated on test. Repeat final evaluation and changed frozen parameters fail
before test access.

### Predeclared comparison and acceptance

The small pool is the current GB (140 trees/depth 2/rate 0.04), GB with 120 trees,
rate 0.05 and subsample 0.8, GB with 180 trees/rate 0.03, existing LR, and existing
RF. Tree candidates keep minimum leaf size 25. Seed 42, original seven inputs,
train-only transforms and natural class prevalence are preserved. Each model is
fit once on production training and once per temporal fold: 20 model fits, not
an exhaustive parameter grid.

For each model compare raw probabilities, sigmoid, isotonic and monotone beta.
Calibrators fit only past calibration labels; August calibrators never fit August
selection labels. Beta uses the already-installed SciPy dependency, bounded
positive coefficients, and fixed regularization `1e-4`:
`sigmoid(a*log(p) - b*log(1-p) + c)`, clipping p to `[1e-12, 1-1e-12]`.
Isotonic exports its knots and clips out-of-range inputs.

All gates must pass before considering a replacement:

- Brier improves by at least 0.002 with ECE worsening by at most 0.005 and a paired
  95% Brier-difference bootstrap interval entirely below zero; **or** ECE improves
  by at least 0.010 with Brier worsening by at most 0.001 and the interval upper
  bound at most 0.001. The bootstrap uses 1,000 paired draws of the 1,585 distinct
  selection customers, seed 42. Intervals are exploratory, without a multiple
  comparison correction; they do not estimate future temporal uncertainty.
- ROC-AUC drops by at most 0.005, AP by 0.010, F1 by 0.010 and recall by 0.020.
- Rolling mean Brier increases by at most 0.003, mean ECE by 0.010, and worst
  fold AUC drops by at most 0.020 versus current GB/sigmoid.
- Estimated full browser artifact is at most twice the original 280,548 bytes;
  each validation recommendation band holds 15–55% of customers.

Among eligible trials select the lowest selection Brier, then ECE, then artifact
size. There were **zero eligible trials**. No criteria were loosened after
looking at results. Every trial failed the meaningful calibration gain gate;
some also failed discrimination, classification, temporal or size checks.

### Validation calibration comparison

These are **August selection** metrics, not test results. Thresholds are
rechecked separately for each probability mapping. PR-AUC means average precision.

| Current GB calibration | Threshold | Brier | ECE | ROC-AUC | AP | F1 | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 0.42 | 0.195012 | 0.034976 | 0.750489 | 0.714351 | 0.626357 | 0.615854 |
| **Sigmoid, retained** | **0.38** | **0.195000** | **0.035922** | **0.750489** | **0.714351** | **0.631179** | **0.632622** |
| Isotonic | 0.39 | 0.194592 | 0.033764 | 0.746578 | 0.693329 | 0.601958 | 0.562500 |
| Beta | 0.38 | 0.194999 | 0.035386 | 0.750489 | 0.714351 | 0.630137 | 0.631098 |

Isotonic improves Brier by only 0.000408, with paired difference CI
`[-0.001772, 0.001016]`, while AP falls by 0.021022 and recall by 0.070122.
Beta's Brier difference is about -0.00000134, CI
`[-0.00002526, 0.00002094]`. Neither is sufficient evidence to replace production.
Isotonic can introduce tied predictions; sigmoid preserves ordering when its
coefficient is positive. Brier and ECE must be read alongside discrimination.
See [sklearn's calibration documentation](https://scikit-learn.org/stable/modules/calibration.html).

The best selection Brier across all trials is 0.194294 (180-tree GB/isotonic),
only 0.000706 better than baseline, with CI `[-0.002132, 0.000834]`; AP is 0.691565.
RF/beta has the lowest selection ECE, 0.029136, but the improvement is only
0.006786, its Brier-difference CI crosses zero, and its estimated pretty-printed
artifact is 2,091,050 bytes (7.45 times current). LR's best Brier is 0.200078,
with AUC 0.732207. Full results for each of the 20 trials are in the JSON report.

Reliability analysis uses 10 equal-width bins; empty bins are omitted. Current
GB/sigmoid on selection:

| Customers | Mean predicted probability | Observed return rate |
| ---: | ---: | ---: |
| 288 | 0.180367 | 0.184028 |
| 428 | 0.234916 | 0.240654 |
| 275 | 0.351670 | 0.421818 |
| 123 | 0.451329 | 0.495935 |
| 147 | 0.546246 | 0.517007 |
| 120 | 0.664297 | 0.566667 |
| 102 | 0.746149 | 0.823529 |
| 50 | 0.846177 | 0.880000 |
| 52 | 0.922096 | 0.980769 |

### Three past-only temporal folds

All features use the unchanged `make_cohort` function. Only transactions before
2011-10-01 enter the extra rolling-cohort construction. Every training label
finishes before its calibration date; every calibration label finishes before
its validation date; every validation label finishes before October test.
Fit scaler/country categories on each fold's own training customers. Fit its
calibrator and choose its threshold using past calibration labels, then evaluate
the future validation window. These fold-specific thresholds never replace the
production threshold. Reusing calibration labels for fold threshold choice can
be optimistic; production threshold assessment uses disjoint selection customers.

| Fold | Train cutoffs | Calibration | Validation | Train / cal / val rows | Threshold |
| --- | --- | --- | --- | --- | ---: |
| 1 | Jan 1 | Mar 2 | May 1 | 883 / 1,701 / 2,432 | 0.57 |
| 2 | Jan 1, Feb 1 | Apr 2 | Jun 1 | 2,182 / 2,148 / 2,716 | 0.47 |
| 3 | Jan 1, Feb 1, Apr 1 | Jun 1 | Aug 1 | 4,314 / 2,716 / 3,145 | 0.44 |

All dates are in 2011. Current GB/sigmoid results:

| Fold | ROC-AUC | AP | F1 | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.717220 | 0.653888 | 0.568501 | 0.211644 | 0.024664 |
| 2 | 0.728804 | 0.689413 | 0.636091 | 0.204141 | 0.059615 |
| 3 | 0.752795 | 0.706133 | 0.616260 | 0.192434 | 0.019512 |

| Metric | Mean | Std (population) | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| ROC-AUC | 0.732939 | 0.014815 | 0.717220 | 0.752795 |
| AP | 0.683144 | 0.021785 | 0.653888 | 0.706133 |
| F1 | 0.606951 | 0.028368 | 0.568501 | 0.636091 |
| Brier | 0.202740 | 0.007905 | 0.192434 | 0.211644 |
| ECE | 0.034597 | 0.017815 | 0.019512 | 0.059615 |

**TEMPORAL ROBUSTNESS: WARNING.** Fold 1 has the lowest discrimination and worst
Brier; January training observes just 31 days of a nominal 90-day feature window.
This left censoring and smaller training population make early folds stress
tests, rather than equivalent mature production cohorts. Fold 2 has the worst
ECE. Customers recur and adjacent validation outcome windows overlap, so the
reported standard deviations describe variation; they are not independent-fold
standard errors or a guarantee for another season.

### Threshold, bands, country and leakage re-audit

Rechecking all 81 thresholds on August selection confirms **0.38** is still the
macro-F1 maximum: 0.684862, precision 0.629742, recall 0.632622, class-1 F1
0.631179. The predeclared threshold-change rule requires macro-F1 gain ≥ 0.005.
There is no gain here. Original bands remain unchanged: 520/536/529 customers,
shares 32.81%/33.82%/33.38%, observed returns 18.65%/38.81%/66.35%.
The groups are balanced, ordered by observed return and straddle 0.38. Boundaries
stay below 0.2302687157944977 and at/above 0.4536477550365929. No test quantiles
are used. Business recommendations still require controlled intervention tests.

Country categories are still training-only. With rare defined as fewer than 20
unique training customers, 32 of 35 countries are rare and 81 selection rows are
in those countries. Replacing their country indicators with unseen/all-zero
encoding changes current GB probabilities by **0.0** on selection, providing no
evidence for a necessary rare-country grouping change in this artifact. This
does not validate future rare-country behavior. Unseen-category and input-range
warnings remain; browser checks include an unseen country.

Every original feature remains historical: recency, tenure and gap use invoices
before cutoff; order count, monetary and product diversity use the preceding
90 days; country is the last historical country. Labels begin at cutoff and
end exclusively 60 days later, without overlap. The automated causal invariance
test changes future purchase amounts/countries and confirms historical features
do not change. No feature, target, scaler, encoding or dataset was changed.

### Final test and observed drift

The separate final evaluation reproduces every baseline metric exactly:
accuracy 0.670634, precision 0.687139, recall 0.556792, F1 0.615136,
AUC 0.728352, AP 0.733974, Brier 0.214076, ECE 0.087397 and confusion matrix
`[[1472,433],[757,951]]`. No new model was evaluated and subsequently rejected
because of October results. The production file's SHA-256 remains
`eeb355f0ec5e70fb4f188fe38bc4cf8f30eea4a832d204ee8f75b346c34a0d51`.

Drift statistics were computed **after the decision freeze**, for explanation:

| Cutoff | Return rate | Recency median / p90 (days) | Orders median / p90 | Spend median / p90 (GBP) | UK share |
| --- | ---: | --- | --- | --- | ---: |
| Apr 1 | 44.56% | 35 / 110.8 | 1 / 3 | 312.605 / 1,286.223 | 90.53% |
| Jun 1 | 41.72% | 49 / 145 | 1 / 3 | 267.095 / 1,246.250 | 90.68% |
| Aug 1 | 40.79% | 61 / 187.6 | 1 / 3 | 201.270 / 1,141.974 | 90.46% |
| Oct 1 | 47.27% | 64 / 232 | 1 / 3 | 177.850 / 1,154.568 | 90.29% |

October outcomes cover October/November and rise 6.48 percentage points above
August despite an older recency tail and lower median past spend. Order-count
quantiles and UK share are comparatively stable. This is consistent with a
seasonal/customer-composition change that may help explain underprediction;
it does not establish causation. A fresh untouched cohort from the intended
business is needed to validate any future recalibration. Do not tune on the
already-reported October cohort.

### Reproduce the quality audit and verify deployment

From an unaudited baseline report, execute phase 1, inspect the frozen decision,
then execute phase 2. The completed report intentionally rejects reopening
selection or re-running final evaluation; do not remove this guard to tune on
test. The original rebuild command above is retained for baseline reproduction,
not for iterating against October metrics.

```powershell
python -B scripts/train-customer-return.py --source "$env:TEMP/customer-return-online-retail.zip" --quality-upgrade
python -B scripts/train-customer-return.py --finalize-quality-upgrade
python -B tests/test_customer_return.py
```

The source archive is reused. Extra pre-test cohorts are cached only in the OS
temporary directory (8,463 rows; 739,985 bytes), keyed by source/cohort-function
hashes. There is no new raw-dataset copy in the repository. The final-test command
supports the retained artifact; a future frozen replacement must first have
matching browser export and parity support, before any final-test access.

Edge checks passed at 320/390/768/1024/1440: 250 sklearn parity samples,
maximum probability error `1.1102230246251565e-16`, explanation reconstruction
error `1.9984014443252818e-15`, three sample buttons, chart complement exactly
100.0%, original recommendations, public auth behavior, failure/reload,
accessibility and no overflow. Model JSON remains **280,548 bytes**.
After 250 warm-up predictions, 1,000 browser predictions per viewport measured
mean **0.0164–0.1189 ms** and p95 **0.10–0.30 ms**, including input validation,
feature contributions and band calculation. These are desktop headless Edge
measurements at mobile viewport sizes, not timings on physical mobile hardware.
Browser timing records are included in `quality_upgrade.verification`.
