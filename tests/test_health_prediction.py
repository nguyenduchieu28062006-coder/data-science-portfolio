"""Regression tests using real sklearn and a local headless Edge/Chrome browser.

Run: python tests/test_health_prediction.py
No third-party browser automation package is needed. Test pages/profiles are temporary.
"""

import functools
import hashlib
import html
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve, auc
from sklearn.model_selection import train_test_split

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("health_training", ROOT / "train-health-model.py")
training = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.names = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("input", "select") and "name" in attrs:
            self.names.append(attrs["name"])
        if tag not in ("meta", "link", "input", "br", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack.pop() == tag, f"Mismatched HTML tag: {tag}"


BROWSER_TEST = r"""
window.addEventListener('DOMContentLoaded', async () => {
  const report = document.createElement('pre'); report.id = 'health-test-report';
  document.body.appendChild(report);
  const checks = [];
  const assert = (ok, message) => { if (!ok) throw Error(message); checks.push(message); };
  try {
    await loadHealthModel();
    assert(healthModel && !healthFields.disabled, 'model fetch and ready state');
    const metrics = [...document.querySelectorAll('[data-metric]')];
    assert(metrics.length === 5 && metrics.every(c => c.textContent ===
      (c.dataset.metric === 'roc_auc' ? healthModel.metrics[c.dataset.metric].toFixed(3) :
      (healthModel.metrics[c.dataset.metric] * 100).toFixed(1) + '%')), 'metrics from JSON');
    assert(healthFeatureNames.every(name => healthForm.elements.namedItem(name)), '13 form features');
    assert(Object.entries(healthCategoryCodes).every(([name, codes]) => JSON.stringify(
      [...healthForm.elements.namedItem(name).options].filter(o => o.value !== '').map(o => Number(o.value)))
      === JSON.stringify(codes)), 'original categorical mapping');
    const fixtures = __FIXTURES__;
    const maxError = Math.max(...fixtures.map(f => Math.abs(predictHealthProbability(healthModel, f.input).probability - f.probability)));
    assert(maxError < 1e-12, 'JavaScript / existing sklearn coefficients parity on 303 rows and missing row');
    assert(fixtures.every(f => {
      const {contributions, linear} = calculateHealthContributions(healthModel, f.input);
      const reconstructed = contributions.reduce((sum, item) => sum + item.contribution, healthModel.intercept);
      return Math.abs(reconstructed - linear) < 1e-12 &&
        Math.abs(1 / (1 + Math.exp(-linear)) - f.probability) < 1e-12;
    }), 'contributions plus intercept reconstruct score');
    assert([...document.querySelectorAll('[data-cm]')].every(cell => {
      const [a,p] = cell.dataset.cm.split(',').map(Number);
      return Number(cell.textContent) === healthModel.confusion_matrix[a][p];
    }), 'confusion matrix cells from model');
    const rocPoints = document.getElementById('healthRocLine').getAttribute('points').split(' ').map(p=>p.split(',').map(Number));
    assert(rocPoints.length === healthModel.roc_curve.fpr.length && rocPoints.every(([x,y],i) =>
      Math.abs((x-52)/316 - healthModel.roc_curve.fpr[i]) < 1e-12 &&
      Math.abs(1-(y-20)/220 - healthModel.roc_curve.tpr[i]) < 1e-12), 'ROC SVG uses model curve');
    assert(predictHealthProbability(healthModel, {}).imputed.length === 13, 'median imputation');
    const synthetic = {...healthModel, coefficients: Array(13).fill(0), intercept: 0};
    assert(predictHealthProbability(synthetic, {}).probability === 0.5, 'sigmoid zero');
    assert(predictHealthProbability({...synthetic, intercept: 1000}, {}).probability === 1 &&
      predictHealthProbability({...synthetic, intercept: -1000}, {}).probability === 0, 'stable sigmoid extremes');
    let invalid = false;
    try { predictHealthProbability(healthModel, {thal: 1}); } catch { invalid = true; }
    assert(invalid, 'reject wrong thal coding');
    invalid = false;
    try { validateHealthModel({...healthModel, scaler_scale: Array(13).fill(0)}); } catch { invalid = true; }
    assert(invalid, 'reject malformed model');
    const fill = input => healthFeatureNames.forEach(name => {
      healthForm.elements.namedItem(name).value = input[name] == null ? '' : input[name];
    });
    const submit = () => healthForm.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
    for (const positive of [false, true]) {
      const sample = fixtures.find(f => Object.values(f.input).every(v=>v !== null) && (f.probability >= 0.5) === positive);
      fill(sample.input); submit();
      assert(!healthResult.hidden && document.getElementById('healthProbability').textContent ===
        (sample.probability * 100).toFixed(1) + '%', 'render probability ' + positive);
      assert(document.getElementById('healthPredictionMessage').textContent ===
        'Mô hình nghiêng về nhóm '+(positive ? 'bệnh tim' : 'không bệnh tim')+' trong dataset (Class '+Number(positive)+').', 'threshold message ' + positive);
      assert(document.getElementById('healthPredictedClass').textContent === (positive ? 'Bệnh tim (Class 1)' : 'Không bệnh tim (Class 0)') &&
        document.getElementById('healthThreshold').textContent === '50%', 'result class and threshold');
      assert(document.querySelector('.health-class-disclaimer').textContent ===
        'Đây là kết quả phân loại của mô hình trên dữ liệu mẫu, không phải chẩn đoán y khoa.', 'nearby result disclaimer');
      assert(Math.abs(document.getElementById('healthGauge').value - sample.probability * 100) < 1e-10, 'gauge');
    }
    healthForm.elements.namedItem('age').dispatchEvent(new Event('input', {bubbles:true}));
    assert(healthResult.hidden, 'hide stale result after edit');
    healthForm.reset(); submit();
    assert(healthResult.hidden && !healthError.hidden, 'block empty form');
    fill({age:55}); submit();
    assert(healthResult.hidden && document.querySelectorAll('[aria-invalid="true"]').length === 12, 'block missing required fields');
    for (const [name,value] of [['age',0],['age',121],['age',55.5],['oldpeak',-1],['chol',-1]]) {
      fill(fixtures[0].input); healthForm.elements.namedItem(name).value = value; submit();
      assert(healthResult.hidden && !document.getElementById('health-'+name+'-error').hidden, 'inline invalid '+name+':'+value);
    }
    for (let i=0; i<2; i++) {
      document.querySelector('[data-health-sample="'+i+'"]').click();
      assert(healthResult.hidden && healthFeatureNames.every(name => Number(healthForm.elements.namedItem(name).value) === fixtures[i].input[name]), 'sample '+(i+1)+' mapping');
      submit();
      assert(!healthResult.hidden && document.getElementById('healthProbability').textContent ===
        (fixtures[i].probability*100).toFixed(1)+'%', 'sample '+(i+1)+' unchanged prediction');
      const actual = [...document.querySelectorAll('#healthContributionChart li')];
      const expected = calculateHealthContributions(healthModel, fixtures[i].input).contributions.sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution)).slice(0,5);
      assert(actual.length === 5 && actual.every((row,j) => row.dataset.feature === expected[j].feature &&
        Math.abs(Number(row.dataset.contribution)-expected[j].contribution) < 1e-12), 'sample Top 5 sorted');
      assert(actual.every(row => row.querySelector('.health-contribution-bar').classList.contains(
        Number(row.dataset.contribution) >= 0 ? 'positive' : 'negative')), 'contribution direction colors');
      assert(actual.every(row => row.querySelector('.health-feature-name').textContent === healthFeatureDisplayName(row.dataset.feature) &&
        row.title.includes(healthFeatureDisplayName(row.dataset.feature))), 'Vietnamese feature names and tooltips');
      assert(actual.every(row => row.querySelector('small').textContent === (Number(row.dataset.contribution) > 0 ?
        'Đẩy dự đoán về nhóm bệnh tim (Class 1)' : 'Đẩy dự đoán về nhóm không bệnh tim (Class 0)')), 'plain-language contribution directions');
      assert(actual.every(row => {
        const name = row.querySelector('.health-feature-name').getBoundingClientRect();
        const value = row.querySelector('.health-contribution-value').getBoundingClientRect();
        const track = row.querySelector('.health-contribution-track').getBoundingClientRect();
        return name.right <= value.left && name.bottom <= track.top && value.bottom <= track.top;
      }), 'long feature labels do not overlap values or bars');
      assert(document.documentElement.scrollWidth <= innerWidth, 'sample chart has no horizontal overflow');
    }
    const legend = document.querySelector('.health-chart-legend');
    assert(legend.querySelector('.health-positive').textContent.includes('Đẩy về nhóm bệnh tim (Class 1)') &&
      legend.querySelector('.health-negative').textContent.includes('Đẩy về nhóm không bệnh tim (Class 0)'), 'dataset class legend');
    if (innerWidth <= 600) assert(getComputedStyle(legend).flexDirection === 'column', 'mobile readable legend');
    healthForm.reset();
    assert(healthResult.hidden && healthError.hidden && healthFeatureNames.every(n=>healthForm.elements.namedItem(n).value === ''), 'reset clears input and result');
    const originalFetch = window.fetch;
    const originalSend = XMLHttpRequest.prototype.send;
    let predictionRequests = 0;
    window.fetch = (...args) => { predictionRequests++; return originalFetch(...args); };
    XMLHttpRequest.prototype.send = function(...args) { predictionRequests++; return originalSend.apply(this, args); };
    fill(fixtures[0].input); submit();
    await new Promise(resolve => setTimeout(resolve, 50));
    window.fetch = originalFetch;
    XMLHttpRequest.prototype.send = originalSend;
    assert(predictionRequests === 0, 'prediction makes no network request');
    assert(document.documentElement.scrollWidth <= innerWidth, 'no horizontal overflow');
    const columns = getComputedStyle(document.querySelector('.health-form-grid')).gridTemplateColumns.split(' ').length;
    assert(columns === (innerWidth <= 600 ? 1 : 2), 'responsive form columns');
    assert(getComputedStyle(document.querySelector('.health-result-layout')).gridTemplateColumns.split(' ').length === (innerWidth <= 900 ? 1 : 2), 'responsive result dashboard');
    assert(getComputedStyle(document.querySelector('.health-performance-layout')).gridTemplateColumns.split(' ').length === (innerWidth <= 900 ? 1 : 2), 'responsive performance dashboard');
    if (innerWidth <= 600) assert(getComputedStyle(document.querySelector('.health-metrics')).gridTemplateColumns.split(' ').length === 1, 'mobile single-column metrics');
    const homepage = new DOMParser().parseFromString(await (await fetch('./index.html')).text(), 'text/html');
    assert(homepage.querySelector('a[href="health-prediction.html"]'), 'homepage integration');
    const realFetch = window.fetch;
    window.fetch = async () => ({ok:false,status:404}); await loadHealthModel();
    assert(healthFields.disabled && !healthModel, 'model fetch failure blocks prediction');
    window.fetch = realFetch; await loadHealthModel();
    assert(!healthFields.disabled, 'model reload recovery');
    report.textContent = JSON.stringify({ok:true, width:innerWidth, checks:checks.length, maxError});
  } catch (error) {
    report.textContent = JSON.stringify({ok:false,error:error.message,checks});
  }
  window.parent.postMessage(report.textContent, location.origin);
});
"""


def main():
    page = (ROOT / "health-prediction.html").read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(page)
    assert not parser.stack and len(set(parser.ids)) == len(parser.ids)
    assert parser.names == training.FEATURES
    js = (ROOT / "health-prediction.js").read_text(encoding="utf-8")
    inference = re.search(r'function predictHealthProbability\(model, input\) \{.*?\n\}', js, re.S).group()
    assert hashlib.sha256(inference.encode()).hexdigest() == "41e0acc672e5fa183bdc488cad20a9d9c44af183e4bfdb278212ab40f48eda19", "Prediction function changed"
    contribution_calculation = re.search(r'function calculateHealthContributions\(model, input\) \{.*?\n\}', js, re.S).group()
    assert hashlib.sha256(contribution_calculation.encode()).hexdigest() == "c1ed101068bbaf448687f08bdc1e21bfee797756d06dc48f0bda3cf89405226d", "Contribution calculation changed"
    assert not re.search(r"Math\.random|localStorage|sessionStorage|sendBeacon", js)
    model = json.loads((ROOT / "health-model.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((ROOT / "health-model.json").read_bytes()).hexdigest() == "7740ef1389ae1bce4aafdf825d84984f50407294e999f9b2099c9b42012b2f89", "Model JSON, metrics or evaluation data changed"
    original = {k: v for k,v in model.items() if k not in ("confusion_matrix", "roc_curve")}
    assert hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == "82b630b6ba675cfc335afac82357ad3e9c5e209e0d59e30501020f02d0be4abe", "Original model parameters or metrics changed"
    frame = training.load_dataset(ROOT / "data" / "heart.csv")
    x = frame[training.FEATURES]
    y = (frame.target > 0).astype(int)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=.2, random_state=42, stratify=y)
    # Load the existing coefficients into sklearn for independent inference.
    # No fit/retraining: the user's model must remain unchanged.
    classifier = LogisticRegression()
    classifier.classes_ = np.array([0, 1])
    classifier.coef_ = np.array([model["coefficients"]])
    classifier.intercept_ = np.array([model["intercept"]])
    classifier.n_features_in_ = len(model["features"])

    def standardize(values):
        return (values.fillna(model["medians"]).to_numpy() - np.array(model["scaler_mean"])) / np.array(model["scaler_scale"])

    proba = classifier.predict_proba(standardize(x_test))[:, 1]
    predicted = proba >= .5
    assert model["confusion_matrix"] == confusion_matrix(y_test, predicted, labels=[0,1]).tolist()
    fpr, tpr, _ = roc_curve(y_test, proba)
    np.testing.assert_allclose(model["roc_curve"]["fpr"], fpr, atol=1e-12)
    np.testing.assert_allclose(model["roc_curve"]["tpr"], tpr, atol=1e-12)
    assert abs(auc(model["roc_curve"]["fpr"], model["roc_curve"]["tpr"]) - model["metrics"]["roc_auc"]) < 1e-12
    metrics = dict(accuracy=accuracy_score(y_test, predicted), precision=precision_score(y_test, predicted),
                   recall=recall_score(y_test, predicted), f1=f1_score(y_test, predicted), roc_auc=roc_auc_score(y_test, proba))
    for key, value in metrics.items():
        assert abs(model["metrics"][key] - value) < 1e-12, key
    np.testing.assert_allclose(list(model["medians"].values()), x_train.median().to_numpy())
    fixtures = [{"input": {name: None if np.isnan(row[name]) else float(row[name]) for name in training.FEATURES},
                 "probability": float(probability)}
                for (_, row), probability in zip(x.iterrows(), classifier.predict_proba(standardize(x))[:, 1])]
    import pandas as pd
    missing = pd.DataFrame([[np.nan] * 13], columns=training.FEATURES)
    fixtures.append({"input": {}, "probability": float(classifier.predict_proba(standardize(missing))[0, 1])})
    test_script = BROWSER_TEST.replace("__FIXTURES__", json.dumps(fixtures, allow_nan=False))
    test_page = page.replace("</body>", "<script>" + test_script + "</script></body>").encode()
    browser = os.environ.get("HEALTH_TEST_BROWSER") or next((str(p) for p in [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ] if p.exists()), None) or shutil.which("chromium") or shutil.which("google-chrome")
    if not browser:
        raise RuntimeError("Set HEALTH_TEST_BROWSER to an Edge/Chrome/Chromium executable.")
    methods = []

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            methods.append("GET")
            if self.path.startswith("/__health_viewport__.html?width="):
                # Edge has a minimum outer window width. A same-origin iframe
                # supplies the exact viewport, including 320/390px phones.
                width = int(self.path.split("width=")[1])
                content = (
                    '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>'
                    '<pre id="health-test-report"></pre><script>'
                    "addEventListener('message', e => { if(e.origin === location.origin) "
                    "document.getElementById('health-test-report').textContent = e.data; });"
                    f'</script><iframe style="width:{width}px;height:1100px;border:0" '
                    'src="/__health_test__.html"></iframe></body></html>'
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif self.path == "/__health_test__.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(test_page)))
                self.end_headers()
                self.wfile.write(test_page)
            else:
                super().do_GET()

        def do_POST(self):
            methods.append("POST")
            self.send_error(405)

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="health-browser-") as temp:
            for width, height in [(1440, 1000), (768, 1024), (390, 844), (320, 720)]:
                result = subprocess.run([
                    browser, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--disable-background-networking", "--disable-extensions", "--no-default-browser-check",
                    f"--user-data-dir={Path(temp) / str(width)}", f"--window-size={width},{height}",
                    "--virtual-time-budget=15000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/__health_viewport__.html?width={width}",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                match = re.search(r'<pre id="health-test-report">(.*?)</pre>', result.stdout, re.S)
                if not match:
                    raise RuntimeError("Browser did not finish tests: " + result.stderr[-1000:])
                report = json.loads(html.unescape(match.group(1)))
                assert report["ok"], report
                assert report["width"] == width, report
                print(report)
        assert all(method == "GET" for method in methods), "Unexpected upload request"
    finally:
        server.shutdown()
        server.server_close()
    print("PASS: HTML structure, model metrics, sklearn parity, real browser UI and responsive checks.")


if __name__ == "__main__":
    main()
