"""Real Edge/Chrome checks; no production auth, history or customer writes.

python -B tests/test_customer_return.py
Checks temporal cohorts, exported inference against 250 sklearn-generated
probabilities, explanation reconstruction, all result bands and five viewports.
Browser profiles and screenshots are written to the OS temporary directory.
"""
import base64
import csv
import functools
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_vietnam_map_online import CDP

CREATED = {
    'customer-return.html', 'customer-return.css', 'customer-return.js',
    'customer-return-inference.js', 'customer-return-model.json',
    'requirements-customer-return.txt', 'scripts/train-customer-return.py',
    'data/NOTICE-customer-return.txt', 'data/customer-return-cohorts.csv',
    'data/customer-return-parity-fixtures.json', 'docs/customer-return-model-report.json',
    'docs/customer-return-methodology.md', 'tests/test_customer_return.py',
    'customer-return-batch.js', 'tests/customer-return-batch-browser.js',
}


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.references, self.stack = set(), [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, 'Duplicate ID'
            self.ids.add(attrs['id'])
        for key in ['for', 'aria-labelledby', 'aria-describedby']:
            self.references.extend(attrs.get(key, '').split())
        if tag not in ['meta', 'link', 'input', 'br', 'hr', 'img']:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack.pop() == tag, 'Mismatched HTML: ' + tag


def static_checks():
    parser = Parser()
    parser.feed((ROOT / 'customer-return.html').read_text(encoding='utf-8'))
    assert not parser.stack and all(ref in parser.ids for ref in parser.references)
    model = json.loads((ROOT / 'customer-return-model.json').read_text(encoding='utf-8'))
    report = json.loads((ROOT / 'docs/customer-return-model-report.json').read_text(encoding='utf-8'))
    cohorts = pd.read_csv(ROOT / 'data/customer-return-cohorts.csv')
    assert len(cohorts) == report['cohort_rows'] == 11606
    assert not cohorts.duplicated(['cutoff', 'customer_key']).any()
    assert not cohorts.isna().any().any()
    assert cohorts.returned_60d.isin([0, 1]).all()
    assert all(report['leakage_checks'][key] for key in ['feature_dates_strictly_before_cutoff', 'targets_only_from_future_window', 'labels_mature_before_next_split', 'customer_id_excluded_from_features', 'train_only_scaling_encoding', 'calibration_selection_customers_disjoint', 'test_not_used_for_model_calibration_threshold_or_band_selection'])
    spec = importlib.util.spec_from_file_location('customer_training', ROOT / 'scripts/train-customer-return.py')
    training = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(training)
    train = cohorts.loc[cohorts.cutoff.isin(training.CUTOFFS[:2])]
    np.testing.assert_allclose(training.prepare(train)['scaler_mean'], model['preprocessing']['scaler_mean'], atol=1e-12)
    np.testing.assert_allclose(training.prepare(train)['scaler_scale'], model['preprocessing']['scaler_scale'], atol=1e-12)
    assert training.prepare(train)['categories'] == model['preprocessing']['categories']
    assert set(model['preprocessing']['numeric_features']) == set(training.FEATURES)
    assert 'returned_60d' not in model['preprocessing']['feature_order']
    assert 'customer_key' not in model['preprocessing']['feature_order']
    assert pd.to_datetime(train.label_end_exclusive).max() <= pd.Timestamp('2011-08-01')
    assert pd.to_datetime(cohorts.loc[cohorts.cutoff == '2011-08-01', 'label_end_exclusive']).max() <= pd.Timestamp('2011-10-01')
    # Causal feature invariance: adding/changing future purchases may alter target
    # but must not change any feature at the earlier scoring date.
    sample = pd.DataFrame({
        'CustomerID': ['a', 'b', 'a', 'b'], 'InvoiceNo': ['1', '2', '3', '4'],
        'InvoiceDate': pd.to_datetime(['2011-03-01', '2011-03-15', '2011-04-10', '2011-06-10']),
        'StockCode': ['10001'] * 4, 'Country': ['United Kingdom'] * 4,
        'amount': [10., 20., 30., 40.],
    })
    before = training.make_cohort(sample, '2011-04-01')
    altered = sample.copy()
    altered.loc[2:, 'amount'] = 1000000
    altered.loc[2:, 'Country'] = 'France'
    after = training.make_cohort(altered, '2011-04-01')
    pd.testing.assert_frame_equal(before[training.FEATURES + ['country']], after[training.FEATURES + ['country']])
    assert model['threshold'] == report['threshold']
    assert model['recommendation_policy'] == report['recommendation_policy']
    assert model['evaluation']['metrics'] == report['test_metrics']
    assert model['evaluation']['metrics']['pr_auc_definition'].startswith('Average precision')
    assert len(model['evaluation']['model_comparison']) == 3
    assert sum(map(sum, model['evaluation']['metrics']['confusion_matrix'])) == model['evaluation']['split_counts']['test']['rows']
    fixtures = json.loads((ROOT / 'data/customer-return-parity-fixtures.json').read_text(encoding='utf-8'))
    assert len(fixtures) == 250
    quality_checks(training, model, report)
    assert not re.search(r'alert\s*\(|localStorage|sessionStorage|sendBeacon|\.from\(', (ROOT / 'customer-return.js').read_text(encoding='utf-8'))
    return model


def quality_checks(training, model, report):
    """Verify the frozen production decision and fail closed on repeat/tampering."""
    upgrade = report['quality_upgrade']
    assert upgrade['phase'] == 'FINAL_EVALUATED'
    freeze = upgrade['selection_freeze']
    payload = freeze['payload']
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == freeze['sha256']
    assert freeze['test_evaluated'] is True
    assert upgrade['final_test']['rejected_candidates_evaluated'] == 0
    assert upgrade['final_test']['selection_changes_after_test'] == 0
    assert hashlib.sha256((ROOT / 'data/customer-return-cohorts.csv').read_bytes()).hexdigest() == upgrade['cohorts_sha256']
    for key in ['estimator', 'calibration', 'preprocessing', 'threshold', 'model_name']:
        assert model[key] == payload[key], 'Production does not match frozen ' + key
    for key, value in payload['bands'].items():
        assert model['recommendation_policy'][key] == value
    if upgrade['decision'] == 'BASELINE RETAINED':
        assert hashlib.sha256((ROOT / 'customer-return-model.json').read_bytes()).hexdigest() == upgrade['baseline_model_sha256']
    methods = set(upgrade['policy']['calibration_methods'])
    assert {'none', 'sigmoid', 'isotonic'} <= methods
    assert len(upgrade['trials']) == len(upgrade['policy']['candidate_ids']) * len(methods)
    for trial in upgrade['trials']:
        folds = trial['rolling_folds']
        assert len(folds) >= 3
        for fold in folds:
            assert max(pd.Timestamp(date) + pd.Timedelta(days=60) for date in fold['train']) <= pd.Timestamp(fold['calibration'])
            assert pd.Timestamp(fold['calibration']) + pd.Timedelta(days=60) <= pd.Timestamp(fold['validation'])
            assert pd.Timestamp(fold['validation']) + pd.Timedelta(days=60) <= pd.Timestamp(upgrade['policy']['test_cutoff'])
            assert sum(b['count'] for b in fold['metrics']['bins']) == fold['rows']['validation']
        assert sum(b['count'] for b in trial['selection_metrics']['bins']) == report['split_counts']['selection']['rows']
    eligible = [trial for trial in upgrade['trials'] if all(trial['acceptance_gates'].values())]
    assert bool(eligible) == (upgrade['decision'] == 'UPGRADE_SELECTED')
    # A repeat evaluation or modified frozen decision must fail before reading
    # any test rows or calculating probabilities, even in a different process.
    with tempfile.TemporaryDirectory(prefix='customer-return-freeze-test-') as temp:
        test_root = Path(temp)
        (test_root / 'docs').mkdir()
        report_path = test_root / 'docs/customer-return-model-report.json'
        for tamper in [False, True]:
            altered = json.loads(json.dumps(report))
            if tamper:
                altered['quality_upgrade']['phase'] = 'SELECTION_FROZEN'
                altered['quality_upgrade']['selection_freeze']['payload']['threshold'] += .01
            report_path.write_text(json.dumps(altered), encoding='utf-8')
            with patch.object(training, 'ROOT', test_root), patch.object(training, 'predict_exported') as inference:
                try:
                    training.quality_finalize()
                except AssertionError as error:
                    assert ('Selection changed' if tamper else 'already been evaluated') in str(error)
                else:
                    raise AssertionError('Unsafe final-test evaluation was accepted')
                inference.assert_not_called()


def batch_fixture():
    """In-memory transactions and features computed by the actual training code."""
    spec = importlib.util.spec_from_file_location('batch_training', ROOT / 'scripts/train-customer-return.py')
    training = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(training)
    rows = []
    def add(customer, order, date, quantity=2, price=12.5, country='United Kingdom', sku='10001', rating=4, feedback=''):
        rows.append([customer, order, date, quantity, price, country, sku, rating, feedback])
    for i, country in enumerate(['Vietnam', 'Viet Nam', 'Việt Nam', 'VN', 'United Kingdom']):
        add('active-' + str(i), 'A' + str(i), '2011-01-01', country=country)
        for j in range(6):
            add('active-' + str(i), f'B{i}-{j}', f'2011-09-{20+j:02d} 10:00:00', quantity=5, price=20, country=country, sku=str(10001+j), rating=1 if i < 2 else 5, feedback='A "quoted", multi-line\nreview')
    add('old', 'OLD', '2011-02-01')
    add('=1+1', 'FORMULA', '2011-03-01')
    add('<img src=x onerror="window.__batchInjected=true">', 'HTML', '2011-03-01')
    add('boundary90', 'EDGE', '2011-07-03', quantity=1, price=2.675)
    add('half-round', 'ROUND', '2011-09-01', quantity=1, price=.125)
    add('bad-date', 'BAD', '2011-02-30')
    add('cancelled', 'C999', '2011-09-01')
    add('refund', 'REF', '2011-09-01', quantity=-1)
    add('zero-price', 'ZERO', '2011-09-01', price=0)
    add('adjustment', 'POSTAGE', '2011-09-01', sku='POST')
    rows.append(rows[1].copy())
    add('future-only', 'AT-CUTOFF', '2011-10-01')
    add('future-only', 'FUTURE', '2011-12-01')  # only to mature make_cohort's label assertion
    columns = ['CustomerID', 'InvoiceNo', 'InvoiceDate', 'Quantity', 'UnitPrice', 'Country', 'StockCode', 'rating', 'feedback']
    raw = pd.DataFrame(rows, columns=columns).drop_duplicates().copy()
    raw.InvoiceDate = pd.to_datetime(raw.InvoiceDate, format='mixed', errors='coerce')
    clean = raw.loc[raw.InvoiceDate.notna() & ~raw.InvoiceNo.str.upper().str.startswith('C') & (raw.Quantity > 0) & (raw.UnitPrice > 0) & raw.StockCode.str.match(r'^\d{5}[A-Za-z]?$')].copy()
    clean['amount'] = clean.Quantity * clean.UnitPrice
    cutoff = '2011-10-01'
    expected = training.make_cohort(clean, cutoff)
    model = json.loads((ROOT / 'customer-return-model.json').read_text(encoding='utf-8'))
    probabilities = training.predict_exported(model, expected)
    ids = {hashlib.sha256(('uci-retail:' + str(value)).encode()).hexdigest()[:16]: str(value) for value in clean.CustomerID.unique()}
    features = [{'id': ids[row.customer_key], 'features': {name: str(row[name]) if name == 'country' else float(row[name]) for name in training.FEATURES + ['country']}, 'probability': float(probabilities[i])} for i, row in expected.iterrows()]
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)
    return {'csv': output.getvalue(), 'snapshot': cutoff, 'features': features, 'rawRows': len(rows)}


MOCK = r'''
window.__customerErrors=[];
addEventListener('error',e=>window.__customerErrors.push(e.message));
addEventListener('unhandledrejection',e=>window.__customerErrors.push(String(e.reason)));
window.__customerAuthCallback=null;
window.supabase={createClient:()=>({auth:{
onAuthStateChange(fn){window.__customerAuthCallback=fn;return {data:{subscription:{unsubscribe(){}}}}},
async getSession(){return {data:{session:null},error:null}},
async getUser(){return {data:{user:null},error:null}}
}})};
'''

CHECKS = r'''(async()=>{
const checks=[],assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name)},$=id=>document.getElementById(id);
await CustomerReturnPage.ready;await PortfolioAuth.ready;
const model=CustomerReturnPage.getModel();
assert(model&&!$('customerFields').disabled,'model and form ready');
assert($('customerResult').hidden&&$('customerAdvice').children.length===0,'no result before prediction');
const fixtures=await(await fetch('/data/customer-return-parity-fixtures.json')).json();
let maxError=0,maxExplanationError=0;
for(const fixture of fixtures){
const p=CustomerReturnModel.predict(model,fixture.input);
maxError=Math.max(maxError,Math.abs(p.probability-fixture.probability));
maxExplanationError=Math.max(maxExplanationError,Math.abs(p.baseline+p.factors.reduce((s,f)=>s+f.contribution,0)-p.explanationScore));
assert(p.probability+p.nonReturnProbability===1,'exact complement');
}
assert(fixtures.length===250&&maxError<1e-12,'Python vs JavaScript on 250 real test customers');
assert(maxExplanationError<1e-12,'signed local contributions reconstruct calibrated model score');
for(let i=0;i<250;i++)CustomerReturnModel.predict(model,fixtures[i%fixtures.length].input);
const durations=[],benchmarkStart=performance.now();
for(let i=0;i<1000;i++){
const start=performance.now();CustomerReturnModel.predict(model,fixtures[i%fixtures.length].input);durations.push(performance.now()-start);
}
const inferenceMeanMs=(performance.now()-benchmarkStart)/durations.length;
durations.sort((a,b)=>a-b);
const inferenceP95Ms=durations[Math.floor(durations.length*.95)];
assert(Number.isFinite(inferenceMeanMs)&&inferenceMeanMs<10&&inferenceP95Ms<20,'local inference within interactive latency budget');
assert([...$('customerForm').querySelectorAll('[name]')].length===7,'exact seven real input features');
for(const [mutate,name] of [[m=>m.threshold=NaN,'invalid threshold'],[m=>m.preprocessing.scaler_scale[0]=0,'invalid scaler'],[m=>m.preprocessing.categories.push(m.preprocessing.categories[0]),'duplicate categories'],[m=>m.estimator.trees[0].left[0]=0,'tree cycle'],[m=>m.evaluation.metrics.roc_auc=NaN,'invalid metrics']]){
const malformed=structuredClone(model);mutate(malformed);let failed=false;try{CustomerReturnModel.validateModel(malformed)}catch{failed=true}assert(failed,name+' rejected');
}
const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
const noOverflow=()=>{
assert(document.documentElement.scrollWidth<=innerWidth,'no horizontal page overflow');
for(const e of $('customerResult').querySelectorAll('*'))if(vis(e)&&!e.closest('svg')){
const r=e.getBoundingClientRect();assert(r.left>=0&&r.right<=innerWidth+1,'result element inside viewport');
assert(e.scrollWidth<=e.clientWidth+1,'result text does not overflow');
}
};
const originalFetch=window.fetch,originalSend=XMLHttpRequest.prototype.send;
let predictionRequests=0;window.fetch=(...args)=>{predictionRequests++;return originalFetch(...args)};
XMLHttpRequest.prototype.send=function(...args){predictionRequests++;return originalSend.apply(this,args)};
const observations=[];
const headings={high:'Khả năng quay lại cao',medium:'Cần chăm sóc thêm',low:'Nguy cơ không quay lại cao'};
const adviceTitles={high:['Duy trì trải nghiệm tốt','Cross-sell phù hợp','Upsell hợp lý','VIP / loyalty rewards','Thu thập feedback','Referral / giới thiệu bạn bè'],medium:['Ưu đãi vừa phải','Nhắc mua lại đúng nhịp','Sản phẩm đề xuất','Khuyến khích tích lũy loyalty','Khảo sát hài lòng ngắn','Chăm sóc cá nhân hóa'],low:['Ưu đãi cá nhân hóa','Chiến dịch tái kích hoạt','Cải thiện trải nghiệm sau mua','Gợi ý sản phẩm phù hợp','Chương trình khách hàng thân thiết','Giảm rào cản quay lại mua']};
for(const band of ['high','medium','low','high','low','medium']){
document.querySelector('[data-customer-sample="'+band+'"]').click();assert($('customerResult').hidden,'sample hides stale result');
const sample=model.samples.find(s=>s.band===band);
assert(Object.entries(sample.input).every(([k,v])=>String($('customerForm').elements.namedItem(k).value)===String(v)),'sample fills actual validation customer');
$('customerForm').requestSubmit();const prediction=CustomerReturnPage.getResult();
assert(prediction&&!$('customerResult').hidden&&prediction.band===band,'correct '+band+' branch');
assert(Math.abs(prediction.probability-sample.probability)<1e-12,'sample exact Python output');
const a=$('customerReturnProbability').textContent,b=$('customerNonReturnProbability').textContent;
assert(Math.round(parseFloat(a)*10)+Math.round(parseFloat(b)*10)===1000,'rounded labels total 100.0%');
assert($('customerBandBadge').textContent===headings[band],'text risk semantics '+band);
assert($('customerClassification').textContent.includes('Class '+Number(prediction.probability>=model.threshold)),'classification uses exported threshold');
assert($('customerChartReturnLabel').textContent===a&&$('customerChartNonReturnLabel').textContent===b,'visible chart data labels');
const chart=$('customerProbabilityChart').getBoundingClientRect(),returnBar=$('customerReturnSegment').getBoundingClientRect(),otherBar=$('customerNonReturnSegment').getBoundingClientRect();
assert(Math.abs(returnBar.width/chart.width-prediction.probability)<.001&&Math.abs(returnBar.width+otherBar.width-chart.width)<1,'100 percent stacked horizontal bar geometry');
assert(getComputedStyle($('customerReturnSegment')).backgroundImage.includes('linear-gradient')&&getComputedStyle($('customerNonReturnSegment')).backgroundImage.includes('linear-gradient'),'Power BI palette gradients');
$('customerReturnSegment').focus();assert(!$('customerChartTooltip').hidden&&$('customerChartTooltip').textContent==='Quay lại mua: '+a,'keyboard accessible modern tooltip '+JSON.stringify({hidden:$('customerChartTooltip').hidden,text:$('customerChartTooltip').textContent,expected:'Quay lại mua: '+a,active:document.activeElement.id,hasResult:Boolean(CustomerReturnPage.getResult())}));
$('customerReturnSegment').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert($('customerChartTooltip').hidden,'Escape dismisses tooltip');
$('customerNonReturnSegment').focus();assert(!$('customerChartTooltip').hidden&&$('customerChartTooltip').textContent==='Không quay lại: '+b,'non return tooltip');$('customerNonReturnSegment').blur();
const factors=[...$('customerFactors').children],expected=prediction.factors.slice(0,5);
assert(factors.length===5&&factors.every((e,i)=>e.dataset.feature===expected[i].feature&&Number(e.dataset.contribution)===expected[i].contribution),'Top 5 real signed model factors');
assert($('customerExplanationNote').textContent.includes('không phải SHAP')&&$('customerExplanationNote').textContent.includes('log-odds'),'explanation method and units explicit');
const cards=[...$('customerAdvice').children];assert(cards.length===6&&cards.every((c,i)=>c.querySelector('h4').textContent===adviceTitles[band][i]&&c.querySelector('p').textContent.length>60),'six business recommendations '+band);
assert(cards.every(c=>c.querySelector('.cr-advice-icon').getAttribute('aria-hidden')==='true'),'decorative advice icons');
assert(getComputedStyle($('customerAdvice')).gridTemplateColumns.split(' ').length===(innerWidth<=600?1:innerWidth<=1100?2:3),'recommendation responsive grid');
assert(!$('customerProbabilityCaution').hidden&&$('customerProbabilityCaution').textContent.includes('calibration'),'calibration WARNING close to probabilities');
assert(!/chắc chắn quay lại|chắc chắn rời bỏ/i.test($('customerResult').innerText),'no guaranteed business outcome');
noOverflow();observations.push({band,return:a,nonReturn:b});
}
await new Promise(r=>setTimeout(r,50));window.fetch=originalFetch;XMLHttpRequest.prototype.send=originalSend;
assert(predictionRequests===0,'prediction makes no network request');
const field=$('customerForm').elements.namedItem('recency_days');field.dispatchEvent(new Event('input',{bubbles:true}));
assert($('customerResult').hidden&&$('customerAdvice').children.length===0&&CustomerReturnPage.getResult()===null,'input edit clears old result and recommendations');
$('customerForm').requestSubmit();assert(!$('customerResult').hidden,'repredict after edit');
$('customerForm').elements.namedItem('country').dispatchEvent(new Event('change',{bubbles:true}));assert($('customerResult').hidden,'select change clears result');
$('customerForm').reset();$('customerForm').requestSubmit();assert($('customerResult').hidden&&!$('customerInputError').hidden&&document.querySelectorAll('.cr-field [aria-invalid="true"]').length===7,'empty form blocked inline');
const fill=()=>document.querySelector('[data-customer-sample="high"]').click();
for(const [name,value] of [['tenure_days',-1],['orders_90d',1.5],['monetary_90d',-1],['recency_days',500],['avg_purchase_gap_days',500]]){
fill();$('customerForm').elements.namedItem(name).value=value;$('customerForm').requestSubmit();assert($('customerResult').hidden&&!$('customerInputError').hidden,'invalid '+name+' rejected');
}
fill();$('customerForm').elements.namedItem('orders_90d').value=0;$('customerForm').requestSubmit();assert($('customerResult').hidden&&!$('customerInputError').hidden,'inconsistent activity fields blocked');
fill();$('customerForm').elements.namedItem('recency_days').value=100;$('customerForm').requestSubmit();assert($('customerResult').hidden&&!$('customerInputError').hidden,'inconsistent recency blocked');
fill();$('customerForm').elements.namedItem('country').value='__UNKNOWN__';$('customerForm').requestSubmit();assert(!$('customerResult').hidden&&!$('customerDomainWarning').hidden&&CustomerReturnPage.getResult().warnings.includes('Quốc gia chưa xuất hiện trong tập huấn luyện'),'unseen category uses training encoder with warning');
fill();$('customerForm').elements.namedItem('tenure_days').value=5000;$('customerForm').requestSubmit();assert(!$('customerResult').hidden&&!$('customerDomainWarning').hidden,'numeric domain warning');
const metrics=[...document.querySelectorAll('[data-customer-metric]')];
assert(metrics.length===8&&metrics.every(e=>e.textContent===(['accuracy','precision','recall','f1'].includes(e.dataset.customerMetric)?(model.evaluation.metrics[e.dataset.customerMetric]*100).toFixed(1)+'%':model.evaluation.metrics[e.dataset.customerMetric].toFixed(3))),'all metrics from evaluated artifact');
assert([...document.querySelectorAll('[data-customer-cm]')].every(e=>{const [a,b]=e.dataset.customerCm.split(',').map(Number);return Number(e.textContent)===model.evaluation.metrics.confusion_matrix[a][b]}),'confusion matrix matches held-out test');
assert($('customerRocChart').querySelector('[data-curve]').getAttribute('points').split(' ').length===model.evaluation.roc_curve.fpr.length,'ROC uses real test curve');
assert($('customerPrChart').querySelector('[data-curve]').getAttribute('points').split(' ').length===model.evaluation.pr_curve.recall.length,'PR uses real test curve');
assert($('customerCalibrationChart').querySelectorAll('circle').length===model.evaluation.metrics.bins.length,'actual calibration bins');
assert($('customerComparison').children.length===3&&$('customerComparison').querySelector('[data-selected="true"]').textContent.includes(model.model_name),'three model comparison and selected candidate');
window.__customerAuthCallback('SIGNED_IN',{user:{id:'mock-customer-user',email:'customer@example.test'}});await new Promise(r=>setTimeout(r,30));
assert(!document.querySelector('[data-auth-user]').hidden&&$('customerResult').hidden===false,'auth aware navigation preserves public prediction');
window.__customerAuthCallback('SIGNED_OUT',null);await new Promise(r=>setTimeout(r,30));fill();$('customerForm').requestSubmit();assert(!document.querySelector('[data-auth-guest]').hidden&&!$('customerResult').hidden,'guest public prediction works after signout');
document.querySelector('.cr-methodology').open=true;assert(document.documentElement.scrollWidth<=innerWidth,'expanded methodology scroll stays inside table');
window.fetch=async()=>({ok:false,status:404});await CustomerReturnPage.reload();assert($('customerFields').disabled&&$('customerResult').hidden&&CustomerReturnPage.getModel()===null&&!$('customerRocChart').children.length,'failed model blocks inference and clears evaluation');
window.fetch=originalFetch;await CustomerReturnPage.reload();assert(!$('customerFields').disabled&&CustomerReturnPage.getModel(),'model reload recovery');
assert(window.__customerErrors.length===0,'no JavaScript or promise errors');
return {ok:true,width:innerWidth,checks:checks.length,paritySamples:fixtures.length,maxError,maxExplanationError,inferenceMeanMs,inferenceP95Ms,samples:observations.slice(0,3)};
})()'''


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    static_checks()
    fixture = batch_fixture()
    batch_checks = (ROOT / 'tests/customer-return-batch-browser.js').read_text(encoding='utf-8')
    print('PASS: HTML references, audited temporal cohorts, train-only preprocessing, leakage invariance and evaluation consistency.', flush=True)
    browser = os.environ.get('HEALTH_TEST_BROWSER', r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not Path(browser).exists():
        browser = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    output = Path(tempfile.gettempdir()) / 'customer-return-browser-review'
    output.mkdir(exist_ok=True)
    methods = []

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            methods.append(('GET', self.path))
            path = self.path.split('?')[0]
            if path.endswith('.html') and (ROOT / path.lstrip('/')).is_file():
                raw = (ROOT / path.lstrip('/')).read_text(encoding='utf-8').replace('<head>', '<head><script>' + MOCK + '</script>').encode()
                mime = 'text/html; charset=utf-8'
            elif path == '/supabase-config.js':
                raw = b'window.PORTFOLIO_SUPABASE_CONFIG={url:"https://customer-test.supabase.co",key:"sb_publishable_test_only"};'
                mime = 'text/javascript'
            else:
                return super().do_GET()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            methods.append(('POST', self.path))
            self.send_error(405, 'Tests cannot write to external applications')

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    process = None
    reports = []
    try:
        with tempfile.TemporaryDirectory(prefix='customer-return-browser-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([browser, '--headless=new', '--disable-gpu', '--no-first-run', '--disable-extensions', '--no-default-browser-check', '--disable-background-networking', '--remote-debugging-port=0', '--remote-allow-origins=*', '--user-data-dir=' + profile, 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            portfile = Path(profile) / 'DevToolsActivePort'
            for _ in range(150):
                if portfile.exists():
                    break
                if process.poll() is not None:
                    raise RuntimeError('Headless browser exited')
                time.sleep(.1)
            port = int(portfile.read_text().splitlines()[0])
            target = json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT')))
            cdp = CDP(target['webSocketDebuggerUrl'])
            cdp.s.settimeout(25)
            cdp.call('Page.enable')
            # Headless targets may start as background tabs: emulate a focused
            # foreground page so native .focus() dispatches real focus events.
            cdp.call('Emulation.setFocusEmulationEnabled', {'enabled': True})

            def js(code):
                response = cdp.call('Runtime.evaluate', {'expression': code, 'returnByValue': True, 'awaitPromise': True})
                if 'exceptionDetails' in response:
                    raise RuntimeError(str(response['exceptionDetails']))
                return response.get('result', {}).get('value')

            def navigate(page):
                cdp.call('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/{page}'})
                for _ in range(150):
                    if js("document.readyState==='complete' && location.pathname.endsWith(" + json.dumps(page) + ")"):
                        return
                    time.sleep(.05)
                raise RuntimeError('Page load timed out')

            for width in [320, 390, 768, 1024, 1440]:
                cdp.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 960, 'deviceScaleFactor': 1, 'mobile': width <= 390})
                navigate('customer-return.html')
                report = js(CHECKS)
                assert report['ok'] and report['width'] == width
                reports.append(report)
                print(json.dumps(report, ensure_ascii=False), flush=True)
                js('window.__batchFixture=' + json.dumps(fixture, ensure_ascii=False))
                batch_report = js(batch_checks)
                assert batch_report['ok'] and batch_report['width'] == width
                report['batch'] = batch_report
                print(json.dumps(batch_report, ensure_ascii=False), flush=True)
                y = js("window.scrollTo(0,0);document.getElementById('customerBatchDashboard').getBoundingClientRect().top+scrollY")
                dimensions = cdp.call('Page.getLayoutMetrics')['cssContentSize']
                shot = cdp.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True, 'clip': {'x': 0, 'y': max(0, y - 10), 'width': width, 'height': min(2000, dimensions['height'] - y), 'scale': 1}})
                (output / f'batch-{width}.png').write_bytes(base64.b64decode(shot['data']))
                js('CustomerReturnBatchPage.selectTab(0)')
                js('window.scrollTo(0,0)')
                shot = cdp.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
                (output / f'page-{width}.png').write_bytes(base64.b64decode(shot['data']))
                for band in ['high', 'medium', 'low']:
                    y = js("document.querySelector('[data-customer-sample=\"" + band + "\"]').click();document.getElementById('customerForm').requestSubmit();window.scrollTo(0,0);document.getElementById('customerResult').getBoundingClientRect().top+scrollY")
                    time.sleep(.1)
                    dimensions = cdp.call('Page.getLayoutMetrics')['cssContentSize']
                    clip = {'x': 0, 'y': max(0, y - 10), 'width': width, 'height': min(2400, dimensions['height'] - y), 'scale': 1}
                    shot = cdp.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True, 'clip': clip})
                    (output / f'result-{width}-{band}.png').write_bytes(base64.b64decode(shot['data']))
                cdp.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
                assert js("matchMedia('(prefers-reduced-motion: reduce)').matches && getComputedStyle(document.getElementById('customerReturnSegment')).transitionDuration==='0s'")
                cdp.call('Emulation.setEmulatedMedia', {'features': []})
                navigate('index.html')
                assert js("document.querySelector('a[href=\"customer-return.html\"]').textContent==='Thử dự đoán' && document.querySelector('a[href=\"health-prediction.html\"]') && document.querySelector('a[href=\"vietnam-house-price.html\"]') && document.querySelector('a[href=\"data-analyzer.html\"]') && document.documentElement.scrollWidth<=innerWidth")
            cdp.call('Browser.close')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Edge may retain background profile processes after CDP closes
                # the tested browser. Terminate only our launched test process.
                process.terminate()
                process.wait(timeout=10)
        assert all(method == 'GET' for method, _ in methods)
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        server.shutdown()
        server.server_close()
    (output / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS: five real browser viewports, 250-sample Python/JS parity, all risk bands, charts, accessibility, local prediction and public auth behavior. Screenshots: ' + str(output))


if __name__ == '__main__':
    main()
