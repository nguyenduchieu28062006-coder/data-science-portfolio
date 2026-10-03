# Health Prediction

An educational Logistic Regression model trained on the original processed UCI
Cleveland Heart Disease dataset. The deployed website is entirely static: it loads
`health-model.json` and calculates predictions in JavaScript. Python is needed only
to retrain, not on Vercel. No health form data is saved or sent to a server.

## Training

Use Python 3.11 or newer. From the repository directory:

```powershell
python -m pip install -r requirements-health.txt
python train-health-model.py
```

On Windows, `py` can replace `python`. The script uses `data/heart.csv` if present;
otherwise it downloads `processed.cleveland.data` directly from UCI and saves a CSV
with headers. The target is mapped from 0–4 to 0/1 during training, with values > 0
mapped to 1. All 303 rows are used; missing `?` values become NaN.

The split is stratified 80/20, `random_state=42` (242 train, 61 test).
`SimpleImputer(strategy="median")`, `StandardScaler`, and
`LogisticRegression(random_state=42, max_iter=2000)` are fitted only on train.
The exported model remains the evaluated train model; it is not refitted on test.
Metrics are computed from held-out labels, using threshold 0.5; ROC-AUC uses probabilities.
The JSON includes training settings, package version, dataset checksum, and source.

To add confusion matrix and ROC data to an existing export without training:

```powershell
python train-health-model.py --evaluation-only
```

This mode reconstructs the original held-out split, predicts with the existing JSON
parameters, verifies the dataset checksum and all existing metrics, and adds only
`confusion_matrix` (rows actual, columns predicted, classes 0/1) and `roc_curve`
(`fpr`, `tpr`). Coefficients, intercept, medians, scaler and metrics stay unchanged.
Normal training also exports these evaluation fields for future retraining.

Original Cleveland codes are preserved, including cp=1/2/3/4, slope=1/2/3,
thal=3/6/7. Categorical features are used as their original numeric codes in the
requested standardized Logistic Regression, without one-hot encoding.

The trainer verifies exported arithmetic against sklearn on all test rows and an
entirely missing row. Browser inference performs median replacement, scaling, a
dot product plus intercept, and a numerically stable sigmoid.

## Local test

1. In VS Code, use Live Server to open `index.html`.
2. Click **Khám phá** on the Health Prediction card.
3. Wait for the ready message and model metrics.
4. Enter all 13 required fields, or click **Điền mẫu 1** / **Điền mẫu 2**, then
   click **Dự đoán**. Missing or invalid fields show inline errors and block submit.
   Use **Xóa dữ liệu nhập** to clear the form/result.
5. Check desktop/tablet and mobile widths. Browser Network should contain only the
   page, CSS, script, and model GET requests; predicting sends no requests.

Alternative: `python -m http.server 8000`, then visit `http://localhost:8000`.
Do not open the HTML with `file://`: browsers may block the model fetch.

Automated checks (Edge/Chrome/Chromium required):

```powershell
python tests/test_health_prediction.py
```

The test runner checks held-out metrics, all 303 predictions against sklearn,
missing-input inference, category codes, probability messages, reset/edit behavior,
model-load failure, no prediction network requests, and layout at 1440/768/390/320px.
It also checks both sample buttons, Top 5 contribution ordering/signs, the sum of
all 13 contributions plus intercept, confusion matrix, ROC coordinates and AUC,
and fingerprints of all original model fields and the unchanged inference function.
It uses a temporary HTTP server and headless browser; no test files or profiles are
left in the project. Set `HEALTH_TEST_BROWSER` if the browser is installed elsewhere.

## Explainability

Each feature contribution is `(value - scaler_mean) / scaler_scale * coefficient`.
Positive values push the linear score toward class 1; negative values toward class
0. The UI orders the five largest absolute contributions and draws signed bars
around a central zero line. All 13 contributions plus intercept reconstruct the
linear score; Top 5 alone are not the full score. These are model contributions,
not causal or medical conclusions. The original prediction function, including
its median fallback for programmatic missing inputs, is preserved; the UI now
requires all 13 fields to make sample exploration explicit.

Performance charts use native HTML/SVG and the result chart uses HTML/CSS; there
are no external chart scripts, backend, or additional frontend dependencies.

## Deployment

Commit the new HTML, JS, JSON, training script, requirements, dataset and this guide,
plus the changes to `index.html` and `style.css`. Push to the existing GitHub repo
when ready. Keep the current Vercel configuration. No API, Python runtime, model
training build step, secrets, or new dependencies are needed to serve the website.
After deployment, verify the homepage link and that `/health-model.json` responds
with JSON. The model is included in the repository, so visitors do not download the
dataset or train it themselves. No push is performed automatically.

## Source and limitations

Janosi, A., Steinbrunn, W., Pfisterer, M., & Detrano, R. (1989). *Heart Disease*.
[UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/45/heart+disease),
[DOI: 10.24432/C52P4X](https://doi.org/10.24432/C52P4X).
Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
`data/heart.csv` adds headers and represents missing values as `?`; original feature
and target values are preserved. Target binarization is performed in the trainer.

This small historical cohort and a single holdout split are not clinical validation.
The displayed probability is a model classification probability, not a calibrated
personal medical risk. Categorical numeric encoding and median imputation are
educational simplifications. The on-page medical disclaimer must remain visible.
