"""Reproducible, time-separated repeat-purchase experiment (UCI Online Retail).

python -B scripts/train-customer-return.py --source <UCI online+retail.zip>
--quality-upgrade compares calibration/rolling folds without evaluating test;
--finalize-quality-upgrade evaluates the frozen retained artifact once.
Reads the XLSX with the standard library. Only Customer Return artifacts are written.
No customer identifiers are exported
to the browser. Source dates, exclusions and training-only transforms are audited.
"""
import argparse
import hashlib
import inspect
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.preprocessing import StandardScaler
from scipy.optimize import minimize
from scipy.special import expit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['recency_days', 'tenure_days', 'orders_90d', 'monetary_90d',
            'products_90d', 'avg_purchase_gap_days']
LABELS = ['Ngày từ lần mua gần nhất', 'Thời gian đã là khách hàng',
          'Số đơn mua trong 90 ngày', 'Tổng chi tiêu trong 90 ngày',
          'Số sản phẩm khác nhau trong 90 ngày', 'Khoảng cách trung bình giữa các đơn']
CUTOFFS = ['2011-04-01', '2011-06-01', '2011-08-01', '2011-10-01']
SOURCE = 'https://archive.ics.uci.edu/static/public/352/online+retail.zip'
SEED = 42


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read_source(path):
    """Stream the official XLSX without installing an Excel runtime."""
    source = path.read_bytes()
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            name = next(name for name in archive.namelist() if name.endswith('.xlsx'))
            excel = archive.read(name)
    else:
        excel = source
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    records = []
    with zipfile.ZipFile(io.BytesIO(excel)) as book:
        strings = []
        with book.open('xl/sharedStrings.xml') as stream:
            for _, element in ET.iterparse(stream, events=['end']):
                if element.tag == ns + 'si':
                    strings.append(''.join(element.itertext()))
                    element.clear()
        with book.open('xl/worksheets/sheet1.xml') as stream:
            for _, row in ET.iterparse(stream, events=['end']):
                if row.tag != ns + 'row':
                    continue
                values = [None] * 8
                for cell in row:
                    value = cell.find(ns + 'v')
                    if value is None:
                        continue
                    col = ord(re.sub('[0-9]', '', cell.attrib['r'])) - ord('A')
                    if col >= 8:
                        continue
                    text = value.text
                    values[col] = strings[int(text)] if cell.attrib.get('t') == 's' else text
                records.append(values)
                row.clear()
    frame = pd.DataFrame(records[1:], columns=records[0])
    for name in ['Quantity', 'UnitPrice', 'CustomerID', 'InvoiceDate']:
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    frame.InvoiceDate = pd.to_datetime(frame.InvoiceDate, unit='D', origin='1899-12-30').dt.round('s')
    return frame, {'archive_sha256': hashlib.sha256(source).hexdigest(),
                   'xlsx_sha256': hashlib.sha256(excel).hexdigest()}


def clean_transactions(raw, hashes):
    audit = {'dataset': 'UCI Online Retail', 'source': SOURCE,
             'source_page': 'https://archive.ics.uci.edu/dataset/352/online%2Bretail',
             'doi': '10.24432/C5BW33', 'license': 'CC BY 4.0',
             'raw_rows': len(raw), 'raw_columns': list(raw.columns), 'source_hashes': hashes,
             'missing': {k: int(v) for k, v in raw.isna().sum().items()},
             'exact_duplicate_rows': int(raw.duplicated().sum()),
             'date_range': [str(raw.InvoiceDate.min()), str(raw.InvoiceDate.max())],
             'country_counts': {str(k): int(v) for k, v in raw.Country.value_counts().items()},
             'numeric_ranges': {k: {'min': float(raw[k].min()), 'max': float(raw[k].max()),
                                    'q99': float(raw[k].quantile(.99))}
                                for k in ['Quantity', 'UnitPrice']}}
    frame = raw.drop_duplicates().copy()
    filters = [
        ('missing_customer_or_date', frame.CustomerID.isna() | frame.InvoiceDate.isna()),
        ('cancellations', frame.InvoiceNo.astype(str).str.upper().str.startswith('C')),
        ('nonpositive_quantity_or_price', (frame.Quantity <= 0) | (frame.UnitPrice <= 0) |
         frame.Quantity.isna() | frame.UnitPrice.isna()),
        ('nonproduct_lines', ~frame.StockCode.astype(str).str.match(r'^\d{5}[A-Za-z]?$')),
        ('missing_country', frame.Country.isna()),
    ]
    exclusions = {}
    for name, invalid in filters:
        excluded = invalid.reindex(frame.index)
        exclusions[name] = int(excluded.sum())
        frame = frame.loc[~excluded].copy()
    frame.CustomerID = frame.CustomerID.astype(int).astype(str)
    frame.InvoiceNo = frame.InvoiceNo.astype(str)
    frame['amount'] = frame.Quantity * frame.UnitPrice
    assert np.isfinite(frame.amount).all() and (frame.amount > 0).all()
    assert len(raw) == 541909 and len(raw.columns) == 8, 'Unexpected source schema'
    audit.update({'sequential_exclusions': exclusions, 'clean_rows': len(frame),
                  'clean_customers': int(frame.CustomerID.nunique()),
                  'clean_invoices': int(frame.InvoiceNo.nunique()),
                  'outlier_policy': 'Keep legitimate wholesale/high-value orders. Log1p compresses skew; fit scaling only on training cohorts. No quantile filtering from test data.',
                  'duplicate_policy': 'Drop exact duplicate source rows before aggregation.',
                  'purchase_definition': 'Non-cancelled product invoice with identified customer, positive quantity and positive unit price. Non-product adjustments/postage are excluded. Later returns are not used to revise earlier purchases.'})
    return frame, audit


def make_cohort(transactions, date):
    cutoff = pd.Timestamp(date)
    end = cutoff + pd.Timedelta(days=60)
    assert transactions.InvoiceDate.max() >= end, 'Incomplete outcome window'
    history = transactions.loc[transactions.InvoiceDate < cutoff]
    recent = history.loc[history.InvoiceDate >= cutoff - pd.Timedelta(days=90)]
    invoices = history.groupby(['CustomerID', 'InvoiceNo']).agg(date=('InvoiceDate', 'min'), amount=('amount', 'sum')).reset_index()
    lifetime = invoices.groupby('CustomerID').agg(first=('date', 'min'), last=('date', 'max'), n=('InvoiceNo', 'size'))
    result = pd.DataFrame(index=lifetime.index)
    result['recency_days'] = (cutoff - lifetime['last']).dt.days
    result['tenure_days'] = (cutoff - lifetime['first']).dt.days
    activity = recent.groupby('CustomerID').agg(orders_90d=('InvoiceNo', 'nunique'), monetary_90d=('amount', 'sum'), products_90d=('StockCode', 'nunique'))
    result = result.join(activity).fillna(0)
    span = (lifetime['last'] - lifetime['first']).dt.total_seconds() / 86400
    result['avg_purchase_gap_days'] = (span / (lifetime.n - 1).replace(0, np.nan)).fillna(0).round(4)
    result['monetary_90d'] = result.monetary_90d.round(2)
    for name in ['orders_90d', 'products_90d']:
        result[name] = result[name].astype(int)
    result['country'] = history.sort_values('InvoiceDate', kind='stable').groupby('CustomerID').Country.last()
    future_customers = set(transactions.loc[(transactions.InvoiceDate >= cutoff) & (transactions.InvoiceDate < end), 'CustomerID'])
    result['returned_60d'] = result.index.isin(future_customers).astype(int)
    result['cutoff'] = date
    result['label_end_exclusive'] = end.strftime('%Y-%m-%d')
    result['customer_key'] = [hashlib.sha256(('uci-retail:' + value).encode()).hexdigest()[:16] for value in result.index]
    assert result[FEATURES].notna().all().all() and (result[FEATURES] >= 0).all().all()
    return result.reset_index(drop=True)


def prepare(frame):
    scaler = StandardScaler().fit(np.log1p(frame[FEATURES]))
    categories = sorted(frame.country.unique().tolist())
    return {'numeric_features': FEATURES, 'numeric_transform': 'log1p',
            'scaler_mean': scaler.mean_.tolist(), 'scaler_scale': scaler.scale_.tolist(),
            'categorical_feature': 'country', 'categories': categories,
            'unknown_category_policy': 'all-zero one-hot vector; display out-of-domain warning',
            'feature_order': FEATURES + ['country=' + value for value in categories]}


def encode(frame, preprocessing):
    numeric = (np.log1p(frame[FEATURES].to_numpy(dtype=float)) - np.array(preprocessing['scaler_mean'])) / np.array(preprocessing['scaler_scale'])
    encoded = np.column_stack([(frame.country == value).to_numpy(dtype=float) for value in preprocessing['categories']])
    return np.column_stack([numeric, encoded])


def candidates():
    return {
        'Logistic Regression': LogisticRegression(C=1.0, max_iter=2000, random_state=SEED),
        'Random Forest': RandomForestClassifier(n_estimators=160, max_depth=8, min_samples_leaf=25, max_features=.8, random_state=SEED, n_jobs=2),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=140, max_depth=2, learning_rate=.04, min_samples_leaf=25, random_state=SEED),
    }


def score_input(estimator, values):
    if hasattr(estimator, 'decision_function'):
        return estimator.decision_function(values)
    return estimator.predict_proba(values)[:, 1]


def probability(estimator, values, calibration):
    if calibration['method'] == 'none':
        return estimator.predict_proba(values)[:, 1]
    margin = calibration['coefficient'] * score_input(estimator, values) + calibration['intercept']
    return 1 / (1 + np.exp(-margin))


def calibration_stats(y, p):
    bins = []
    for i in range(10):
        mask = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        if mask.any():
            bins.append({'count': int(mask.sum()), 'predicted': float(p[mask].mean()), 'observed': float(y[mask].mean())})
    return {'brier': float(brier_score_loss(y, p)),
            'ece_10_bins': float(sum(b['count'] * abs(b['predicted'] - b['observed']) for b in bins) / len(y)),
            'bins': bins}


def metrics(y, p, threshold):
    pred = p >= threshold
    return {'accuracy': float(accuracy_score(y, pred)), 'precision': float(precision_score(y, pred, zero_division=0)),
            'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)),
            'macro_f1': float(f1_score(y, pred, average='macro', zero_division=0)),
            'roc_auc': float(roc_auc_score(y, p)), 'pr_auc': float(average_precision_score(y, p)),
            'pr_auc_definition': 'Average precision (non-interpolated PR area)',
            'confusion_matrix': confusion_matrix(y, pred, labels=[0, 1]).tolist(),
            **calibration_stats(y, p)}


def export_tree(tree, forest=False):
    values = tree.value[:, 0, :]
    values = values[:, 1] / values.sum(axis=1) if forest else values[:, 0]
    return {'left': tree.children_left.tolist(), 'right': tree.children_right.tolist(),
            'feature': tree.feature.tolist(), 'threshold': tree.threshold.tolist(), 'value': values.tolist()}


def export_estimator(estimator, name):
    if name == 'Logistic Regression':
        return {'kind': 'logistic_regression', 'coefficients': estimator.coef_[0].tolist(), 'intercept': float(estimator.intercept_[0])}
    if name == 'Gradient Boosting':
        return {'kind': 'gradient_boosting', 'intercept': float(estimator._raw_predict_init(np.zeros((1, estimator.n_features_in_)))[0, 0]),
                'learning_rate': float(estimator.learning_rate), 'trees': [export_tree(e[0].tree_) for e in estimator.estimators_]}
    return {'kind': 'random_forest', 'trees': [export_tree(e.tree_, forest=True) for e in estimator.estimators_]}


QUALITY_POLICY = {
    'candidate_ids': ['gb_baseline', 'gb_120_subsample', 'gb_180_slow', 'logistic', 'forest'],
    'calibration_methods': ['none', 'sigmoid', 'isotonic', 'beta'],
    'selection_cutoff': '2011-08-01', 'test_cutoff': '2011-10-01',
    'threshold_grid': {'min': .10, 'max': .90, 'step': .01},
    'threshold_change_min_macro_f1_gain': .005,
    'minimum_brier_improvement': .002, 'minimum_ece_improvement': .01,
    'ece_alternative_max_brier_increase': .001,
    'max_auc_drop': .005, 'max_ap_drop': .01,
    'max_f1_drop': .01, 'max_recall_drop': .02,
    'max_rolling_mean_brier_increase': .003, 'max_rolling_mean_ece_increase': .01,
    'max_rolling_worst_auc_drop': .02,
    'max_artifact_size_multiplier': 2,
    'paired_brier_bootstrap_samples': 1000,
    'band_share_range': [.15, .55],
    'test_policy': 'Production decision frozen on selection/rolling data before final evaluation. Only frozen winner is evaluated on test; no test-driven promotion, rejection or retuning.',
}


def quality_candidates():
    return {
        'gb_baseline': ('Gradient Boosting', candidates()['Gradient Boosting']),
        'gb_120_subsample': ('Gradient Boosting', GradientBoostingClassifier(n_estimators=120, max_depth=2, learning_rate=.05, subsample=.8, min_samples_leaf=25, random_state=SEED)),
        'gb_180_slow': ('Gradient Boosting', GradientBoostingClassifier(n_estimators=180, max_depth=2, learning_rate=.03, min_samples_leaf=25, random_state=SEED)),
        'logistic': ('Logistic Regression', candidates()['Logistic Regression']),
        'forest': ('Random Forest', candidates()['Random Forest']),
    }


def fit_quality_calibrator(method, raw_p, margin, y):
    if method == 'none':
        return {'method': 'none', 'coefficient': 1., 'intercept': 0.}
    if method == 'sigmoid':
        calibrator = LogisticRegression(C=100, max_iter=1000).fit(margin.reshape(-1, 1), y)
        assert calibrator.coef_[0, 0] > 0
        return {'method': 'sigmoid', 'coefficient': float(calibrator.coef_[0, 0]), 'intercept': float(calibrator.intercept_[0])}
    if method == 'isotonic':
        calibrator = IsotonicRegression(out_of_bounds='clip').fit(raw_p, y)
        return {'method': 'isotonic', 'input': 'uncalibrated_probability',
                'x': calibrator.X_thresholds_.tolist(), 'y': calibrator.y_thresholds_.tolist()}
    # Monotone beta mapping: positive coefficients preserve ranking. SciPy is
    # already a sklearn dependency. Objective and bounds are fixed in advance.
    p = np.clip(raw_p, 1e-12, 1 - 1e-12)
    a, b = np.log(p), -np.log1p(-p)
    def objective(theta):
        z = theta[0] * a + theta[1] * b + theta[2]
        loss = np.mean(np.logaddexp(0, z) - y * z) + 1e-4 * np.sum((theta[:2] - 1) ** 2)
        residual = expit(z) - y
        gradient = np.array([np.mean(residual * a), np.mean(residual * b), np.mean(residual)])
        gradient[:2] += 2e-4 * (theta[:2] - 1)
        return loss, gradient
    solution = minimize(objective, np.array([1., 1., 0.]), jac=True, method='L-BFGS-B', bounds=[(1e-6, 20), (1e-6, 20), (-20, 20)])
    assert solution.success, solution.message
    return {'method': 'beta', 'a': float(solution.x[0]), 'b': float(solution.x[1]), 'intercept': float(solution.x[2])}


def quality_probability(raw_p, margin, calibrator):
    method = calibrator['method']
    if method == 'none':
        return raw_p
    if method == 'sigmoid':
        return expit(calibrator['coefficient'] * margin + calibrator['intercept'])
    if method == 'isotonic':
        return np.interp(raw_p, calibrator['x'], calibrator['y'])
    p = np.clip(raw_p, 1e-12, 1 - 1e-12)
    return expit(calibrator['a'] * np.log(p) - calibrator['b'] * np.log1p(-p) + calibrator['intercept'])


def predict_exported(model, frame):
    """Independent Python evaluation of the frozen production JSON, not refit."""
    matrix = encode(frame, model['preprocessing'])
    estimator = model['estimator']
    if estimator['kind'] == 'logistic_regression':
        margin = matrix @ np.array(estimator['coefficients']) + estimator['intercept']
        raw_p = expit(margin)
    else:
        matrix = matrix.astype(np.float32)
        margin = np.repeat(estimator.get('intercept', 0.), len(matrix))
        weight = estimator.get('learning_rate', 1 / len(estimator['trees']))
        for tree in estimator['trees']:
            for i, values in enumerate(matrix):
                node = 0
                while tree['left'][node] != -1:
                    node = tree['left'][node] if values[tree['feature'][node]] <= tree['threshold'][node] else tree['right'][node]
                margin[i] += weight * tree['value'][node]
        raw_p = margin if estimator['kind'] == 'random_forest' else expit(margin)
    return quality_probability(raw_p, margin, model['calibration'])


def quality_threshold(y, p, old):
    grid = np.linspace(.1, .9, 81)
    rows = []
    for threshold in grid:
        pred = p >= threshold
        rows.append({'threshold': float(threshold), 'precision': float(precision_score(y, pred, zero_division=0)),
                     'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)),
                     'macro_f1': float(f1_score(y, pred, average='macro', zero_division=0))})
    best = max(rows, key=lambda r: (r['macro_f1'], -abs(r['threshold'] - old)))
    old_score = float(f1_score(y, p >= old, average='macro', zero_division=0))
    change = best['macro_f1'] - old_score >= QUALITY_POLICY['threshold_change_min_macro_f1_gain']
    return (best['threshold'] if change else old), {'old_threshold': old, 'old_macro_f1': old_score, 'best': best,
        'changed': bool(change), 'reason': 'Only change if selection macro-F1 gain is at least 0.005.', 'grid': rows}


def quality_bands(y, p, threshold, old_policy):
    low, high = old_policy['low_upper_exclusive'], old_policy['high_lower_inclusive']
    def summarize(a, b):
        masks = {'low': p < a, 'medium': (p >= a) & (p < b), 'high': p >= b}
        return {label: {'rows': int(mask.sum()), 'share': float(mask.mean()),
                        'observed_return_rate': float(y[mask].mean()) if mask.any() else None}
                for label, mask in masks.items()}
    original = summarize(low, high)
    ordered = all(original[label]['observed_return_rate'] is not None for label in original) and original['low']['observed_return_rate'] < original['medium']['observed_return_rate'] < original['high']['observed_return_rate']
    balanced = all(.15 <= item['share'] <= .55 for item in original.values())
    retain = ordered and balanced and low <= threshold <= high
    if not retain:
        low, high = float(min(threshold, np.quantile(p, 1 / 3))), float(max(threshold, np.quantile(p, 2 / 3)))
    return {'low_upper_exclusive': low, 'high_lower_inclusive': high}, {
        'old': original, 'final': summarize(low, high), 'changed': not retain,
        'reason': 'Keep old bands if validation shares are 15–55%, return rates increase by band, and boundaries straddle classification threshold; otherwise reuse validation-only tercile rule.'}


def temporal_summary(folds):
    return {key: {'mean': float(np.mean([f['metrics'][key] for f in folds])), 'std': float(np.std([f['metrics'][key] for f in folds])),
                  'min': float(min(f['metrics'][key] for f in folds)), 'max': float(max(f['metrics'][key] for f in folds))}
            for key in ['roc_auc', 'pr_auc', 'f1', 'recall', 'brier', 'ece_10_bins']}


def quality_cache(source, original_report, pretest):
    dates = ['2011-01-01', '2011-02-01', '2011-03-02', '2011-04-02', '2011-05-01']
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest() + ':' + hashlib.sha256(inspect.getsource(make_cohort).encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / 'customer-return-upgrade-pretest-cache.csv'
    meta = path.with_suffix('.json')
    if path.exists() and meta.exists() and json.loads(meta.read_text())['fingerprint'] == fingerprint:
        additional = pd.read_csv(path)
        print('Reuse small, pre-test-only temporal cohort cache.', flush=True)
    else:
        raw, hashes = read_source(source)
        assert hashes['xlsx_sha256'] == original_report['dataset_audit']['source_hashes']['xlsx_sha256'], 'Source dataset changed'
        transactions, _ = clean_transactions(raw, hashes)
        # No October/November transactions enter the rolling analysis.
        transactions = transactions.loc[transactions.InvoiceDate < pd.Timestamp('2011-10-01')]
        additional = pd.concat([make_cohort(transactions, date) for date in dates], ignore_index=True)
        additional.to_csv(path, index=False, float_format='%.6f')
        write_json(meta, {'fingerprint': fingerprint, 'rows': len(additional), 'bytes': path.stat().st_size})
        print('Created pre-test-only cache:', len(additional), 'rows,', path.stat().st_size, 'bytes.', flush=True)
    assert additional.cutoff.max() < '2011-10-01' and additional.label_end_exclusive.max() <= '2011-10-01'
    return pd.concat([pretest, additional], ignore_index=True)


def quality_select(source):
    """Phase 1: no test frame/labels/probabilities are passed to the selector."""
    model_path = ROOT / 'customer-return-model.json'
    baseline_bytes = model_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    report_path = ROOT / 'docs/customer-return-model-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert 'quality_upgrade' not in report, 'Quality selection already frozen; do not reopen selection after final-test evaluation'
    # Existing cohort file is reused unchanged. Discard the test rows immediately.
    pretest = pd.concat([chunk.loc[chunk.cutoff < '2011-10-01'] for chunk in pd.read_csv(ROOT / 'data/customer-return-cohorts.csv', chunksize=2048)], ignore_index=True)
    assert set(pretest.cutoff) == set(CUTOFFS[:3])
    train = pretest.loc[pretest.cutoff.isin(CUTOFFS[:2])]
    validation = pretest.loc[pretest.cutoff == CUTOFFS[2]]
    mask = validation.customer_key.map(lambda key: int(key[:8], 16) % 2 == 0)
    cal, select = validation.loc[mask], validation.loc[~mask]
    assert set(cal.customer_key).isdisjoint(select.customer_key)
    pre = prepare(train)
    assert pre['categories'] == baseline['preprocessing']['categories']
    np.testing.assert_allclose(pre['scaler_mean'], baseline['preprocessing']['scaler_mean'], atol=1e-12)
    matrices = {'train': encode(train, pre), 'calibration': encode(cal, pre), 'selection': encode(select, pre)}
    y_train, y_cal, y_select = train.returned_60d.to_numpy(), cal.returned_60d.to_numpy(), select.returned_60d.to_numpy()
    baseline_p = predict_exported(baseline, select)
    baseline_metrics = metrics(y_select, baseline_p, baseline['threshold'])
    temporal = quality_cache(source, report, pretest)
    definitions = [
        {'id': 'fold_1', 'train': ['2011-01-01'], 'calibration': '2011-03-02', 'validation': '2011-05-01'},
        {'id': 'fold_2', 'train': ['2011-01-01', '2011-02-01'], 'calibration': '2011-04-02', 'validation': '2011-06-01'},
        {'id': 'fold_3', 'train': ['2011-01-01', '2011-02-01', '2011-04-01'], 'calibration': '2011-06-01', 'validation': '2011-08-01'},
    ]
    folds = []
    for definition in definitions:
        frames = [temporal.loc[temporal.cutoff.isin(definition['train'])], temporal.loc[temporal.cutoff == definition['calibration']], temporal.loc[temporal.cutoff == definition['validation']]]
        assert frames[0].label_end_exclusive.max() <= definition['calibration']
        assert frames[1].label_end_exclusive.max() <= definition['validation']
        assert frames[2].label_end_exclusive.max() <= '2011-10-01'
        fold_pre = prepare(frames[0])
        folds.append((definition, frames, [encode(frame, fold_pre) for frame in frames]))
    rng = np.random.default_rng(SEED)
    bootstrap = rng.integers(0, len(select), size=(QUALITY_POLICY['paired_brier_bootstrap_samples'], len(select)))
    trials, candidates_by_id = [], {}
    for model_id, (name, estimator) in quality_candidates().items():
        estimator.fit(matrices['train'], y_train)
        raw_cal, margin_cal = estimator.predict_proba(matrices['calibration'])[:, 1], score_input(estimator, matrices['calibration'])
        raw_select, margin_select = estimator.predict_proba(matrices['selection'])[:, 1], score_input(estimator, matrices['selection'])
        temporal_models = []
        for definition, frames, arrays in folds:
            fold_estimator = quality_candidates()[model_id][1].fit(arrays[0], frames[0].returned_60d)
            temporal_models.append((definition, frames, fold_estimator.predict_proba(arrays[1])[:, 1], score_input(fold_estimator, arrays[1]),
                                    fold_estimator.predict_proba(arrays[2])[:, 1], score_input(fold_estimator, arrays[2])))
        for method in QUALITY_POLICY['calibration_methods']:
            calibration = fit_quality_calibrator(method, raw_cal, margin_cal, y_cal)
            p = quality_probability(raw_select, margin_select, calibration)
            threshold, threshold_check = quality_threshold(y_select, p, baseline['threshold'])
            band_policy, band_check = quality_bands(y_select, p, threshold, baseline['recommendation_policy'])
            selection_metrics = metrics(y_select, p, threshold)
            rolling = []
            for definition, frames, raw_c, margin_c, raw_v, margin_v in temporal_models:
                fold_cal = fit_quality_calibrator(method, raw_c, margin_c, frames[1].returned_60d.to_numpy())
                fold_p = quality_probability(raw_v, margin_v, fold_cal)
                # Fold threshold is chosen on its past calibration cohort, never
                # on the fold's future validation outcomes.
                past_p = quality_probability(raw_c, margin_c, fold_cal)
                fold_threshold, _ = quality_threshold(frames[1].returned_60d.to_numpy(), past_p, baseline['threshold'])
                rolling.append({**definition, 'rows': {key: len(frame) for key, frame in zip(['train', 'calibration', 'validation'], frames)},
                                'threshold': fold_threshold, 'class_rate': float(frames[2].returned_60d.mean()),
                                'metrics': metrics(frames[2].returned_60d.to_numpy(), fold_p, fold_threshold)})
            difference = (p - y_select) ** 2 - (baseline_p - y_select) ** 2
            ci = np.quantile(difference[bootstrap].mean(axis=1), [.025, .975]).tolist()
            serialized = export_estimator(estimator, name)
            estimated_bytes = len(json.dumps({**baseline, 'estimator': serialized, 'calibration': calibration}, ensure_ascii=False, indent=2).encode()) + 1
            trial_id = model_id + '/' + method
            trial = {'id': trial_id, 'model': name, 'parameters': estimator.get_params(), 'calibration': calibration,
                     'selection_metrics': selection_metrics, 'threshold': threshold, 'threshold_check': threshold_check,
                     'band_policy': band_policy, 'band_check': band_check, 'rolling_folds': rolling, 'rolling_summary': temporal_summary(rolling),
                     'paired_brier_delta_ci95': ci, 'estimated_artifact_bytes': estimated_bytes}
            trials.append(trial)
            candidates_by_id[trial_id] = {'estimator': serialized, 'calibration': calibration, 'probabilities': p, 'model_name': name}
            print(json.dumps({'trial': trial_id, 'brier': selection_metrics['brier'], 'ece': selection_metrics['ece_10_bins'], 'auc': selection_metrics['roc_auc'], 'ap': selection_metrics['pr_auc'], 'rolling_ece': trial['rolling_summary']['ece_10_bins']['mean']}, ensure_ascii=False), flush=True)
    reference = next(t for t in trials if t['id'] == 'gb_baseline/sigmoid')
    for trial in trials:
        m, b, policy = trial['selection_metrics'], baseline_metrics, QUALITY_POLICY
        calibration_gain = ((m['brier'] <= b['brier'] - policy['minimum_brier_improvement'] and m['ece_10_bins'] <= b['ece_10_bins'] + .005 and trial['paired_brier_delta_ci95'][1] < 0) or
                            (m['ece_10_bins'] <= b['ece_10_bins'] - policy['minimum_ece_improvement'] and m['brier'] <= b['brier'] + policy['ece_alternative_max_brier_increase'] and trial['paired_brier_delta_ci95'][1] <= policy['ece_alternative_max_brier_increase']))
        summary, old = trial['rolling_summary'], reference['rolling_summary']
        gates = {'meaningful_calibration_gain': bool(calibration_gain),
                 'discrimination': m['roc_auc'] >= b['roc_auc'] - policy['max_auc_drop'] and m['pr_auc'] >= b['pr_auc'] - policy['max_ap_drop'],
                 'classification': m['f1'] >= b['f1'] - policy['max_f1_drop'] and m['recall'] >= b['recall'] - policy['max_recall_drop'],
                 'temporal': summary['brier']['mean'] <= old['brier']['mean'] + policy['max_rolling_mean_brier_increase'] and summary['ece_10_bins']['mean'] <= old['ece_10_bins']['mean'] + policy['max_rolling_mean_ece_increase'] and summary['roc_auc']['min'] >= old['roc_auc']['min'] - policy['max_rolling_worst_auc_drop'],
                 'deployable_size': trial['estimated_artifact_bytes'] <= len(baseline_bytes) * policy['max_artifact_size_multiplier'],
                 'bands': all(.15 <= row['share'] <= .55 for row in trial['band_check']['final'].values())}
        trial['acceptance_gates'] = {key: bool(value) for key, value in gates.items()}
        trial['eligible'] = all(gates.values())
    eligible = [trial for trial in trials if trial['eligible']]
    winner = min(eligible, key=lambda t: (t['selection_metrics']['brier'], t['selection_metrics']['ece_10_bins'], t['estimated_artifact_bytes'])) if eligible else None
    chosen = winner or reference
    decision = 'UPGRADE_SELECTED' if winner else 'BASELINE RETAINED'
    threshold = chosen['threshold'] if winner else baseline['threshold']
    bands = chosen['band_policy'] if winner else {key: baseline['recommendation_policy'][key] for key in ['low_upper_exclusive', 'high_lower_inclusive']}
    payload = {'decision': decision, 'chosen_id': chosen['id'], 'model_name': chosen['model'], 'threshold': threshold, 'bands': bands,
               'estimator': candidates_by_id[chosen['id']]['estimator'] if winner else baseline['estimator'],
               'calibration': chosen['calibration'] if winner else baseline['calibration'], 'preprocessing': pre if winner else baseline['preprocessing']}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    country_counts = train.groupby('country').customer_key.nunique()
    rare = country_counts[country_counts < 20].index.tolist()
    rare_selection = select.country.isin(rare)
    changed_country = select.copy()
    changed_country.loc[rare_selection, 'country'] = '__UNKNOWN__'
    country_effect = abs(baseline_p - predict_exported(baseline, changed_country))
    upgrade = {'phase': 'SELECTION_FROZEN', 'policy': QUALITY_POLICY, 'baseline_model_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
               'cohorts_sha256': hashlib.sha256((ROOT / 'data/customer-return-cohorts.csv').read_bytes()).hexdigest(),
               'baseline_selection_metrics': baseline_metrics, 'trials': trials, 'decision': decision,
               'selection_freeze': {'payload': payload, 'sha256': hashlib.sha256(canonical).hexdigest(), 'test_evaluated': False},
               'country_audit': {'unique_train_customers_by_country': country_counts.to_dict(), 'rare_definition': '<20 unique training customers',
                                 'rare_countries': rare, 'selection_rare_rows': int(rare_selection.sum()),
                                 'rare_encoding_counterfactual_max_probability_delta': float(country_effect.max()),
                                 'encoding_changed': False, 'unseen_policy': 'Train-only one-hot, all-zero encoding for unseen values; browser warns.'},
               'leakage_reaudit': {'target_60_days_unchanged': True, 'cohort_function_unchanged': True, 'feature_end_exclusive': 'cutoff',
                                  'label_start_inclusive': 'cutoff', 'feature_label_windows_do_not_overlap': True,
                                  'fold_training_labels_mature_before_calibration': True, 'fold_calibration_labels_mature_before_validation': True,
                                  'all_rolling_outcomes_end_before_test_cutoff': True, 'test_not_used_for_candidate_or_policy_selection': True,
                                  'features': {name: report['feature_definitions'][name] for name in FEATURES + ['country']}},
               'temporal_limitations': ['January training has 31 observed days and a left-censored 90-day window; early folds are stress tests.',
                                        'Customers recur across cohorts; validation outcome windows of neighboring folds overlap. Summary std is descriptive, not an independent-fold standard error.',
                                        'Fold thresholds use past calibration labels; calibration-fitted threshold assessment can be optimistic. Selection threshold uses disjoint selection customers.'],
               'final_test': None}
    report['quality_upgrade'] = upgrade
    write_json(report_path, report)
    print('FROZEN BEFORE TEST:', json.dumps({'decision': decision, 'chosen': chosen['id'], 'freeze_sha256': upgrade['selection_freeze']['sha256'], 'eligible': [t['id'] for t in eligible]}, ensure_ascii=False), flush=True)


def quality_finalize():
    """Phase 2: final test only; never calls fitting or candidate selection."""
    report_path = ROOT / 'docs/customer-return-model-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    upgrade = report['quality_upgrade']
    assert upgrade['phase'] == 'SELECTION_FROZEN', 'Final test has already been evaluated or no decision is frozen'
    freeze = upgrade['selection_freeze']
    payload = freeze['payload']
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == freeze['sha256'], 'Selection changed after freezing'
    # The completed experiment retained production. An alternative calibration
    # would require a matching browser artifact and parity verification before
    # any test access; never score it first and then reject it for deployability.
    assert payload['decision'] == 'BASELINE RETAINED', 'Verify/export the frozen replacement in the browser before final-test evaluation'
    model_path = ROOT / 'customer-return-model.json'
    baseline_bytes = model_path.read_bytes()
    assert hashlib.sha256(baseline_bytes).hexdigest() == upgrade['baseline_model_sha256']
    assert hashlib.sha256((ROOT / 'data/customer-return-cohorts.csv').read_bytes()).hexdigest() == upgrade['cohorts_sha256']
    final = json.loads(baseline_bytes)
    # Only the frozen winner is evaluated. Rejected candidates never see test.
    final.update({key: payload[key] for key in ['estimator', 'calibration', 'preprocessing', 'threshold', 'model_name']})
    cohorts = pd.read_csv(ROOT / 'data/customer-return-cohorts.csv')
    test = cohorts.loc[cohorts.cutoff == '2011-10-01']
    p = predict_exported(final, test)
    final_metrics = metrics(test.returned_60d.to_numpy(), p, final['threshold'])
    upgrade['final_test'] = {'baseline': report['test_metrics'], 'final': final_metrics,
                             'rows': len(test), 'rejected_candidates_evaluated': 0, 'selection_changes_after_test': 0}
    drift = []
    for date, frame in cohorts.groupby('cutoff', sort=True):
        drift.append({'cutoff': date, 'rows': len(frame), 'class_rate': float(frame.returned_60d.mean()),
                      'features': {name: {'q10': float(frame[name].quantile(.1)), 'median': float(frame[name].median()), 'q90': float(frame[name].quantile(.9))} for name in ['recency_days', 'orders_90d', 'monetary_90d']},
                      'uk_share': float((frame.country == 'United Kingdom').mean())})
    upgrade['drift'] = {'cohorts': drift, 'test_statistics_used_only_after_freeze': True,
                         'interpretation': 'Temporal changes describe possible seasonality/customer mix effects; observational shifts do not prove their causal contribution to calibration error.'}
    freeze['test_evaluated'] = True
    upgrade['phase'] = 'FINAL_EVALUATED'
    # Retention means production JSON, examples and parity fixtures stay byte-identical.
    assert upgrade['decision'] == 'BASELINE RETAINED'
    write_json(report_path, report)
    print(json.dumps({'decision': upgrade['decision'], 'final_test': final_metrics, 'production_model_changed': False}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--quality-upgrade', action='store_true', help='Pre-test comparison and immutable selection freeze; does not evaluate test')
    parser.add_argument('--finalize-quality-upgrade', action='store_true', help='Evaluate only the frozen decision on final test, without fitting')
    args = parser.parse_args()
    if args.finalize_quality_upgrade:
        quality_finalize()
        return
    if not args.source:
        parser.error('--source is required for training/audit/quality selection')
    if args.quality_upgrade:
        quality_select(args.source)
        return
    started = time.monotonic()
    raw, hashes = read_source(args.source)
    transactions, audit = clean_transactions(raw, hashes)
    print(json.dumps({'raw_rows': audit['raw_rows'], 'missing': audit['missing'], 'duplicates': audit['exact_duplicate_rows'], 'exclusions': audit['sequential_exclusions'], 'clean_rows': audit['clean_rows']}, ensure_ascii=False), flush=True)
    if args.audit_only:
        return
    cohorts = pd.concat([make_cohort(transactions, date) for date in CUTOFFS], ignore_index=True)
    train = cohorts.loc[cohorts.cutoff.isin(CUTOFFS[:2])].copy()
    validation = cohorts.loc[cohorts.cutoff == CUTOFFS[2]].copy()
    test = cohorts.loc[cohorts.cutoff == CUTOFFS[3]].copy()
    # Deterministic customer-level split within the earlier validation date;
    # calibration customers and model-selection customers are disjoint.
    calibration_mask = validation.customer_key.map(lambda key: int(key[:8], 16) % 2 == 0)
    cal, select = validation.loc[calibration_mask], validation.loc[~calibration_mask]
    assert set(cal.customer_key).isdisjoint(select.customer_key)
    assert train.label_end_exclusive.max() <= validation.cutoff.min()
    assert validation.label_end_exclusive.max() <= test.cutoff.min()
    preprocessing = prepare(train)
    matrices = {name: encode(frame, preprocessing) for name, frame in [('train', train), ('calibration', cal), ('selection', select), ('test', test)]}
    targets = {name: frame.returned_60d.to_numpy() for name, frame in [('train', train), ('calibration', cal), ('selection', select), ('test', test)]}
    comparisons, fitted = [], {}
    for name, estimator in candidates().items():
        estimator.fit(matrices['train'], targets['train'])
        calibrator = LogisticRegression(C=100, max_iter=1000).fit(score_input(estimator, matrices['calibration']).reshape(-1, 1), targets['calibration'])
        calibrated = {'method': 'sigmoid', 'coefficient': float(calibrator.coef_[0, 0]), 'intercept': float(calibrator.intercept_[0])}
        assert calibrated['coefficient'] > 0, 'Calibration must preserve risk ordering'
        raw_p = estimator.predict_proba(matrices['selection'])[:, 1]
        cal_p = probability(estimator, matrices['selection'], calibrated)
        raw_stats = calibration_stats(targets['selection'], raw_p)
        cal_stats = calibration_stats(targets['selection'], cal_p)
        calibration = calibrated if cal_stats['brier'] < raw_stats['brier'] else {'method': 'none', 'coefficient': 1.0, 'intercept': 0.0}
        p = probability(estimator, matrices['selection'], calibration)
        threshold_grid = np.linspace(.1, .9, 81)
        threshold = float(max(threshold_grid, key=lambda t: (f1_score(targets['selection'], p >= t, average='macro'), -abs(t - .5))))
        first, later = train.loc[train.cutoff == CUTOFFS[0]], train.loc[train.cutoff == CUTOFFS[1]]
        fold_preprocessing = prepare(first)
        fold_estimator = candidates()[name].fit(encode(first, fold_preprocessing), first.returned_60d)
        fold_p = fold_estimator.predict_proba(encode(later, fold_preprocessing))[:, 1]
        validation_metrics = metrics(targets['selection'], p, threshold)
        item = {'model': name, 'validation_metrics': validation_metrics, 'threshold': threshold,
                'uncalibrated_brier': raw_stats['brier'], 'sigmoid_brier': cal_stats['brier'],
                'calibration': calibration, 'temporal_stability_auc': float(roc_auc_score(later.returned_60d, fold_p)),
                'parameters': estimator.get_params(), 'browser_bytes': len(json.dumps(export_estimator(estimator, name), separators=(',', ':')))}
        comparisons.append(item)
        fitted[name] = (estimator, calibration, threshold, p)
        print(json.dumps({k: item[k] for k in ['model', 'validation_metrics', 'calibration', 'temporal_stability_auc', 'browser_bytes']}, ensure_ascii=False), flush=True)
    best_auc = max(c['validation_metrics']['roc_auc'] for c in comparisons)
    best_ap = max(c['validation_metrics']['pr_auc'] for c in comparisons)
    best_brier = min(c['validation_metrics']['brier'] for c in comparisons)
    eligible = [c for c in comparisons if c['validation_metrics']['roc_auc'] >= best_auc - .015 and c['validation_metrics']['pr_auc'] >= best_ap - .02 and c['validation_metrics']['brier'] <= best_brier + .01]
    # Predeclared deployability preference within explicit validation tolerances.
    order = ['Logistic Regression', 'Gradient Boosting', 'Random Forest']
    winner = min(eligible, key=lambda c: order.index(c['model'])) if eligible else max(comparisons, key=lambda c: c['validation_metrics']['roc_auc'] + c['validation_metrics']['pr_auc'] - c['validation_metrics']['brier'])
    name = winner['model']
    estimator, calibration, threshold, selection_p = fitted[name]
    low = float(min(threshold, np.quantile(selection_p, 1 / 3)))
    high = float(max(threshold, np.quantile(selection_p, 2 / 3)))
    assert 0 < low < high < 1
    test_p = probability(estimator, matrices['test'], calibration)
    test_metrics = metrics(targets['test'], test_p, threshold)
    baseline_brier = float(brier_score_loss(targets['test'], np.repeat(targets['train'].mean(), len(test))))
    calibration_status = 'PASS' if test_metrics['ece_10_bins'] <= .05 and test_metrics['brier'] < baseline_brier else 'WARNING'
    threshold_analysis = [{'threshold': float(t), **metrics(targets['selection'], selection_p, float(t))} for t in [.2, .3, .4, .5, .6, .7, .8, threshold]]
    split_counts = {split: {'rows': len(frame), 'class_0': int((frame.returned_60d == 0).sum()), 'class_1': int(frame.returned_60d.sum()), 'unique_customers': int(frame.customer_key.nunique())}
                    for split, frame in [('train', train), ('calibration', cal), ('selection', select), ('test', test)]}
    band_stats = {}
    for label, mask in [('low', selection_p < low), ('medium', (selection_p >= low) & (selection_p < high)), ('high', selection_p >= high)]:
        band_stats[label] = {'selection_rows': int(mask.sum()), 'observed_return_rate': float(targets['selection'][mask].mean())}
    policy = {'low_upper_exclusive': low, 'high_lower_inclusive': high,
              'basis': 'Selection-cohort probability terciles, expanded to straddle the validation-selected classification threshold. Low < min(threshold,q33); high >= max(threshold,q67); medium lies between. Illustrative triage, not proven intervention ROI.',
              'selection_band_statistics': band_stats}
    ranges = {feature: {'min': float(train[feature].min()), 'max': float(train[feature].max()), 'q01': float(train[feature].quantile(.01)), 'q99': float(train[feature].quantile(.99))} for feature in FEATURES}
    feature_metadata = [{'name': feature, 'label': label, 'unit': 'GBP' if feature == 'monetary_90d' else ('ngày' if feature.endswith('days') else 'số lượng'),
                         'training_range': ranges[feature]} for feature, label in zip(FEATURES, LABELS)]
    # Anonymized, actual selection-cohort examples. No test targets used for selection.
    samples = []
    for label, desired in [('high', .9), ('medium', (low + high) / 2), ('low', .1)]:
        eligible_rows = np.flatnonzero(selection_p >= high if label == 'high' else (selection_p < low if label == 'low' else ((selection_p >= low) & (selection_p < high))))
        index = int(eligible_rows[np.argmin(abs(selection_p[eligible_rows] - desired))])
        row = select.iloc[index]
        samples.append({'band': label, 'input': {k: (str(row[k]) if k == 'country' else float(row[k])) for k in FEATURES + ['country']}, 'probability': float(selection_p[index])})
    fpr, tpr, _ = roc_curve(targets['test'], test_p)
    precision, recall, _ = precision_recall_curve(targets['test'], test_p)
    report = {'schema_version': 1, 'dataset_audit': audit,
              'target': '1 = at least one valid product purchase in [cutoff, cutoff + 60 days); 0 = no observed valid purchase in that window. Class 0 is not permanent churn.',
              'feature_definitions': {'recency_days': 'Whole days since last historical valid invoice', 'tenure_days': 'Whole days since first observed historical valid invoice (left-censored at dataset start)',
                                      'orders_90d': 'Distinct valid invoices in [cutoff - 90 days, cutoff)', 'monetary_90d': 'Positive product line revenue in the prior 90 days, GBP',
                                      'products_90d': 'Distinct valid StockCode values in the prior 90 days', 'avg_purchase_gap_days': 'Mean time in days between historical invoices; zero for one invoice',
                                      'country': 'Last observed historical country'},
              'cohort_dates': CUTOFFS, 'split_counts': split_counts,
              'cohort_rows': len(cohorts), 'cohort_columns': list(cohorts.columns),
              'leakage_checks': {'feature_dates_strictly_before_cutoff': True, 'targets_only_from_future_window': True,
                                 'labels_mature_before_next_split': True, 'customer_id_excluded_from_features': True,
                                 'train_only_scaling_encoding': True, 'calibration_selection_customers_disjoint': True,
                                 'test_not_used_for_model_calibration_threshold_or_band_selection': True,
                                 'temporal_stability_fold': 'Train 2011-04-01; validate 2011-06-01. Fit preprocessing only on April.',
                                 'same_customer_across_time': 'Allowed: deployment predicts existing customers again. No ID feature. Scores across snapshots are correlated; unique-customer counts are reported.'},
              'imbalance': 'Report PR-AUC, macro-F1, precision/recall and prevalence. No resampling or class weighting so natural probability prevalence is retained.',
              'model_comparison': comparisons, 'final_model': name,
              'selection_reason': 'Prefer the simplest browser-deployable candidate within 0.015 ROC-AUC, 0.02 average precision and 0.01 Brier of the best validation results. Otherwise maximize validation ROC-AUC + average precision - Brier. Test untouched until selection is frozen.',
              'threshold': threshold, 'threshold_reason': 'Maximize macro-F1 over 0.10–0.90 in steps of 0.01 on selection cohort; tie-break nearest 0.50. Equal class emphasis without inventing business costs. Business deployment must retune on measured campaign cost/benefit.',
              'threshold_analysis': threshold_analysis, 'recommendation_policy': policy,
              'test_metrics': test_metrics, 'calibration_status': calibration_status, 'constant_baseline_brier': baseline_brier,
              'calibration_status_rule': 'PASS if held-out ECE (10 equal-width bins) <= 0.05 and Brier beats training-prevalence constant baseline; otherwise WARNING. This is an operational check, not proof of calibration.',
              'feature_ranges': ranges, 'software': {'python': sys.version.split()[0], 'sklearn': sklearn.__version__, 'pandas': pd.__version__},
              'limitations': ['UK gift retail, 2010–2011, many wholesale customers; no claim of transfer to another business.', 'Observed purchase within 60 days, not loyalty forever or campaign causal uplift.', 'Holiday-period test creates temporal/seasonal distribution shift.', 'Short observation period left-censors customer tenure; inactive customers remain eligible.', 'No satisfaction, support, complaint, discount or campaign features in the source.']}
    artifact = {'schema_version': 1, 'model_version': 'customer-return-uci-60d-v1', 'model_name': name,
                'target': report['target'], 'horizon_days': 60, 'lookback_days': 90, 'preprocessing': preprocessing,
                'feature_metadata': feature_metadata, 'estimator': export_estimator(estimator, name), 'calibration': calibration,
                'threshold': threshold, 'recommendation_policy': policy, 'samples': samples,
                'evaluation': {'split_counts': split_counts, 'metrics': test_metrics, 'calibration_status': calibration_status,
                               'constant_baseline_brier': baseline_brier, 'roc_curve': {'fpr': fpr.tolist(), 'tpr': tpr.tolist()},
                               'pr_curve': {'precision': precision.tolist(), 'recall': recall.tolist()}, 'model_comparison': comparisons},
                'dataset': {key: audit[key] for key in ['dataset', 'source_page', 'doi', 'license', 'raw_rows', 'clean_rows', 'clean_customers']}}
    cohorts.to_csv(ROOT / 'data/customer-return-cohorts.csv', index=False, float_format='%.6f')
    write_json(ROOT / 'customer-return-model.json', artifact)
    write_json(ROOT / 'docs/customer-return-model-report.json', report)
    indices = np.unique(np.linspace(0, len(test) - 1, 250).astype(int))
    fixtures = [{'input': {k: (str(test.iloc[i][k]) if k == 'country' else float(test.iloc[i][k])) for k in FEATURES + ['country']},
                 'probability': float(test_p[i])} for i in indices]
    write_json(ROOT / 'data/customer-return-parity-fixtures.json', fixtures)
    print(json.dumps({'final_model': name, 'threshold': threshold, 'bands': [low, high], 'splits': split_counts,
                      'test_metrics': test_metrics, 'calibration_status': calibration_status,
                      'seconds': round(time.monotonic() - started, 1)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
