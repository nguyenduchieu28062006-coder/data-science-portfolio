"""Real backend + HTTP + Chromium QA; no fixtures stored in project.

python -B tests/test_sales_forecasting.py [--backend-only | --browser-only]
python -B tests/test_sales_forecasting.py --cloud https://preview.vercel.app
"""
import base64
import csv
import functools
import http.client
import http.cookiejar
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import numpy as np
from openpyxl import Workbook

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sales_forecast', ROOT / 'api/sales-forecast.py')
sales = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sales)


def csv_text(headers, rows, delimiter=','):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=delimiter)
    writer.writerow(headers)
    writer.writerows(rows)
    return out.getvalue()


def fixture(count=180, frequency='daily', delimiter=',', decimal_comma=False):
    current = datetime(2021, 1, 1)
    rows = []
    for i in range(count):
        value = round(100 + i * .12 + 20 * np.sin(2 * np.pi * i / sales.PERIOD[frequency]) + 2 * np.cos(i), 2)
        rows.append([current.isoformat(), str(value).replace('.', ',') if decimal_comma else value, 'North'])
        current = sales.next_date(current, frequency)
    return dict(csv=csv_text(['date','sales','store'], rows, delimiter), filename='daily.csv',
                date_column='date', target_column='sales', horizon=12, action='forecast')


def excel_fixture(multiple=False, serial=False):
    wb = Workbook()
    sheet = wb.active
    sheet.title = 'Daily'
    sheet.append(['date','sales','store'])
    from openpyxl.utils.datetime import to_excel
    for i in range(80):
        current = datetime(2023, 1, 1) + timedelta(days=i)
        sheet.append([to_excel(current) if serial else current, 200 + i + i % 7, 'North'])
    if multiple:
        second = wb.create_sheet('Monthly')
        second.append(['date','sales','store'])
        current = datetime(2020, 1, 1)
        for i in range(48):
            second.append([current, 2000 + i * 10 + i % 12 * 8, 'South'])
            current = sales.next_date(current, 'monthly')
    buffer = io.BytesIO()
    wb.save(buffer)
    wb.close()
    return dict(xlsx=base64.b64encode(buffer.getvalue()).decode(), filename='sales.xlsx',
                date_column='date', target_column='sales', horizon=6, action='forecast')


class Parsing(unittest.TestCase):
    def test_csv_comma(self):
        self.assertEqual(len(sales.prepare(fixture())['y']),180)

    def test_csv_semicolon(self):
        self.assertEqual(len(sales.prepare(fixture(delimiter=';'))['y']),180)

    def test_csv_tab(self):
        self.assertEqual(sales.prepare(fixture(delimiter='\t'))['y'][0],102)

    def test_csv_pipe_bom(self):
        p=fixture(delimiter='|'); p['csv']='\ufeff'+p['csv']
        self.assertEqual(sales.prepare(p)['y'][0],102)

    def test_decimal_dot(self):
        self.assertEqual(sales.numeric('1,234.56'),1234.56)
        self.assertEqual(sales.numeric('123.45'),123.45)

    def test_decimal_comma(self):
        p=fixture(delimiter=';',decimal_comma=True)
        self.assertEqual(sales.prepare(p)['y'][0],102)
        self.assertEqual(sales.numeric('1.234,56'),1234.56)
        self.assertEqual(sales.numeric('123,45'),123.45)

    def test_numeric_ambiguity_explicit_choice(self):
        p=fixture(20);p['csv']=p['csv'].replace('102.0','1,234')
        p['csv']=csv_text(['date','sales'],[[f'2023-01-{i+1:02d}','1,234'] for i in range(20)])
        with self.assertRaisesRegex(sales.ForecastError,'định dạng số'): sales.prepare(p)
        self.assertEqual(sales.prepare({**p,'numeric_format':'decimal_dot'})['y'][0],1234)
        self.assertEqual(sales.prepare({**p,'numeric_format':'decimal_comma'})['y'][0],1.234)

    def test_missing_tokens_and_invalid_finite_numbers(self):
        for value in ['', 'NA','N/A','null','None','nan','-','--',float('inf'),'1e100']:
            self.assertIsNone(sales.numeric(value))

    def test_iso_date(self):
        self.assertEqual(sales.parse_date(' 2023-05-01T12:00:00Z ').hour,12)
        self.assertEqual(sales.parse_date('2023/05/01'),datetime(2023,5,1))
        self.assertEqual(sales.parse_date('2023-05'),datetime(2023,5,1))

    def test_day_first(self):
        order,_=sales.date_order(['01/02/2023','19/02/2023'])
        self.assertEqual(sales.parse_date('01/02/2023',order),datetime(2023,2,1))
        self.assertEqual(sales.parse_date('19-02-2023',order),datetime(2023,2,19))

    def test_month_first_evidence(self):
        order,_=sales.date_order(['02/01/2023','02/19/2023'])
        self.assertEqual(sales.parse_date('02/01/2023',order),datetime(2023,2,1))

    def test_ambiguous_date_rejected(self):
        p=fixture(3);p['csv']='date,sales\n01/02/2023,10\n02/02/2023,20\n03/02/2023,30'
        with self.assertRaisesRegex(sales.ForecastError,'mơ hồ'):sales.prepare(p)
        self.assertEqual(sales.prepare({**p,'date_order':'day_first'})['dates'][0],datetime(2023,2,1))

    def test_mixed_date_order_rejected(self):
        with self.assertRaises(sales.ForecastError):sales.date_order(['19/02/2023','02/19/2023'])

    def test_excel_dates(self):
        self.assertEqual(sales.prepare(excel_fixture())['dates'][0],datetime(2023,1,1))

    def test_excel_serial(self):
        self.assertEqual(sales.prepare(excel_fixture(serial=True))['dates'][0],datetime(2023,1,1))

    def test_xlsx_multiple_sheets(self):
        p=excel_fixture(multiple=True)
        self.assertEqual(sales.inspect(p)['metadata']['sheets'],['Daily','Monthly'])
        data=sales.prepare({**p,'sheet':'Monthly'})
        self.assertEqual(data['frequency']['frequency'],'monthly')
        self.assertEqual(len(data['y']),48)
        with self.assertRaises(sales.ForecastError):sales.prepare({**p,'sheet':'Missing'})

    def test_headers_empty_duplicates(self):
        p=dict(csv=' date ,sales,sales,empty\n2023-01-01,1,2,\n2023-01-01,1,2,\n,,,\n2023-01-02,3,4,\n2023-01-03,5,6,')
        names,rows,_,audit=sales.load_table(p)
        self.assertEqual(names,['date','sales','sales_2'])
        self.assertEqual(audit['empty_rows'],1)
        self.assertEqual(audit['empty_columns'],1)
        self.assertEqual(audit['duplicates_removed'],1)
        self.assertEqual(len(rows),3)

    def test_inspect_detection_and_preview(self):
        data=sales.inspect(fixture())
        self.assertEqual(data['suggested_date'],'date')
        self.assertEqual(data['suggested_target'],'sales')
        self.assertEqual(len(data['preview']),10)
        self.assertEqual(data['columns'][0]['type'],'datetime')

    def test_security_limits(self):
        for p in [dict(csv='a,b\n1,2',filename='bad.exe'),dict(xlsx='bad!'),dict(csv='a,b\n1,\x00')]:
            with self.assertRaises(sales.ForecastError):sales.dispatch({**p,'action':'inspect'})
        with self.assertRaises(sales.ForecastError):sales.load_table({'csv':'x'*(sales.MAX_FILE_BYTES+1)})


class Series(unittest.TestCase):
    def test_sort_chronologically(self):
        p=fixture();rows=list(csv.reader(io.StringIO(p['csv'])));p['csv']=csv_text(rows[0],rows[:0:-1])
        dates=sales.prepare(p)['dates']
        self.assertTrue(all(a<b for a,b in zip(dates,dates[1:])))

    def test_duplicate_timestamp_sum(self):
        p=fixture(20);p['csv']+='2021-01-01T00:00:00,5,South\n'
        self.assertEqual(sales.prepare(p)['y'][0],107)

    def test_group_filter_and_values(self):
        p=fixture(20);p['csv']+='2021-01-01T00:00:00,5,South\n'
        self.assertEqual(sales.prepare({**p,'group_column':'store','group_value':'North'})['y'][0],102)
        self.assertEqual(sales.dispatch({**p,'action':'groups','group_column':'store'})['values'],['North','South'])

    def test_daily_frequency(self):self.assertEqual(sales.prepare(fixture())['frequency']['frequency'],'daily')
    def test_weekly_frequency(self):self.assertEqual(sales.prepare(fixture(frequency='weekly'))['frequency']['frequency'],'weekly')
    def test_monthly_frequency(self):self.assertEqual(sales.prepare(fixture(48,frequency='monthly'))['frequency']['frequency'],'monthly')
    def test_hourly_frequency(self):self.assertEqual(sales.prepare(fixture(frequency='hourly'))['frequency']['frequency'],'hourly')
    def test_quarterly_frequency(self):self.assertEqual(sales.prepare(fixture(40,frequency='quarterly'))['frequency']['frequency'],'quarterly')

    def test_missing_period_zero(self):
        p=fixture(20);rows=list(csv.reader(io.StringIO(p['csv'])));del rows[5];p['csv']=csv_text(rows[0],rows[1:])
        data=sales.prepare(p)
        self.assertEqual(data['y'][4],0)
        self.assertEqual(data['quality']['missing_periods'],1)

    def test_missing_targets_drop(self):
        p=fixture(20);rows=list(csv.reader(io.StringIO(p['csv'])));rows[5][1]='NA';p['csv']=csv_text(rows[0],rows[1:])
        data=sales.prepare(p)
        self.assertEqual(data['cleaning']['missing_targets'],1)
        self.assertEqual(data['y'][4],0)

    def test_irregular_override_sum(self):
        p=fixture(120);data=sales.prepare({**p,'frequency':'monthly'})
        self.assertAlmostEqual(float(np.sum(data['y'])),float(np.sum(sales.prepare(p)['y'])))
        self.assertEqual(len(data['y']),4)

    def test_irregular_warning(self):
        p=fixture(20);rows=list(csv.reader(io.StringIO(p['csv'])));rows=[rows[0]]+[r for i,r in enumerate(rows[1:]) if i%3==0 or i%4==0];p['csv']=csv_text(rows[0],rows[1:])
        self.assertTrue(sales.prepare(p)['frequency']['irregular'])

    def test_strong_weekly_seasonality(self):self.assertEqual(sales.prepare(fixture())['seasonality']['status'],'Detected')

    def test_no_seasonality(self):
        p=fixture();rng=np.random.default_rng(9);p['csv']=csv_text(['date','sales'],[[datetime(2023,1,1)+timedelta(days=i),round(v,2)] for i,v in enumerate(rng.normal(100,10,180))])
        self.assertEqual(sales.prepare(p)['seasonality']['status'],'Weak')


class Temporal(unittest.TestCase):
    def test_exclusive_lag_and_rolling_features(self):
        schema=sales.feature_schema('daily',80);y=np.arange(120,dtype=float)
        expected=sales.feature_at(y[:40],datetime(2023,2,10),40,schema)
        changed=y.copy();changed[40:]=1e9
        self.assertEqual(expected,sales.feature_at(changed[:40],datetime(2023,2,10),40,schema))
        values=dict(zip(schema['names'],expected))
        self.assertEqual(values['lag_1'],39)
        self.assertEqual(values['lag_7'],33)
        self.assertEqual(values['rolling_mean_7'],np.mean(y[33:40]))
        self.assertEqual(values['rolling_std_3'],np.std(y[37:40]))

    def test_vectorized_training_features_match_exclusive_prefix(self):
        dates=[datetime(2023,1,1)+timedelta(days=i) for i in range(90)]
        y=np.random.default_rng(5).normal(100,15,90);schema=sales.feature_schema('daily',90)
        class Recorder:
            def fit(self,X,target):self.X=X;self.y=target;return self
        recorder=Recorder()
        with patch.object(sales,'make_estimator',return_value=recorder):sales.fit_model('Ridge Regression',dates,y,schema)
        expected=[sales.feature_at(y[:i],dates[i],i,schema) for i in range(schema['warmup'],90)]
        np.testing.assert_allclose(recorder.X,expected,rtol=1e-10,atol=1e-8)

    def test_walk_forward_and_separate_holdout(self):
        for n,expected in [(18,1),(40,2),(180,3),(500,5)]:
            plan=sales.split_plan(n,12);dates=[datetime(2023,1,1)+timedelta(days=i) for i in range(n)]
            self.assertEqual(len(plan['folds']),expected)
            ends=[]
            for fold in plan['folds']:
                self.assertLess(dates[fold['train_end']-1],dates[fold['validation_start']])
                self.assertLessEqual(fold['validation_end'],plan['holdout_start'])
                ends.append(fold['train_end'])
            self.assertEqual(ends,sorted(set(ends)))

    def test_vectorized_features_unchanged_by_current_and_future_targets(self):
        dates=[datetime(2023,1,1)+timedelta(days=i) for i in range(90)]
        y=np.random.default_rng(7).normal(100,15,90);schema=sales.feature_schema('daily',90)
        class Recorder:
            def fit(self,X,target):self.X=X;return self
        before,after=Recorder(),Recorder()
        with patch.object(sales,'make_estimator',return_value=before):sales.fit_model('Ridge Regression',dates,y,schema)
        changed=y.copy();changed[40:]=1e8
        with patch.object(sales,'make_estimator',return_value=after):sales.fit_model('Ridge Regression',dates,changed,schema)
        np.testing.assert_array_equal(before.X[:41-schema['warmup']],after.X[:41-schema['warmup']])

    def test_recursive_uses_prediction_in_next_step(self):
        schema=sales.feature_schema('daily',30)
        class LagPlusOne:
            def predict(self,X):return X[:,schema['names'].index('lag_1')]+1
        result=sales.recursive_predict('Ridge Regression',LagPlusOne(),list(range(30)),[datetime(2023,2,1)+timedelta(days=i) for i in range(3)],schema,7)
        np.testing.assert_equal(result,[30,31,32])

    def test_rank_not_holdout_and_mae_tie(self):
        a={'name':'A','status':'SUCCESS','backtest':{'rmse':1,'mae':.8},'holdout':{'rmse':100}}
        b={'name':'B','status':'SUCCESS','backtest':{'rmse':2,'mae':.1},'holdout':{'rmse':.01}}
        self.assertEqual(sales.rank_models([b,a])[0]['name'],'A')
        b['backtest']['rmse']=1
        self.assertEqual(sales.rank_models([a,b])[0]['name'],'B')

    def test_future_calendar_dates(self):
        self.assertEqual(sales.next_date(datetime(2024,1,1),'monthly'),datetime(2024,2,1))
        self.assertEqual(sales.next_date(datetime(2024,10,1),'quarterly'),datetime(2025,1,1))
        self.assertEqual(sales.next_date(datetime(2024,2,28),'daily'),datetime(2024,2,29))

    def test_no_shuffle_or_random_split(self):
        source=(ROOT/'api/sales-forecast.py').read_text(encoding='utf-8')
        self.assertNotIn('train_test_split',source)
        self.assertNotIn('KFold',source)
        self.assertIn('early_stopping=False',source)


class Forecasting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal=sales.forecast(fixture())

    def test_real_seven_models(self):
        self.assertEqual({r['name'] for r in self.normal['models'] if r['status']=='SUCCESS'},set(sales.MODELS))
        self.assertEqual(self.normal['models'][0]['name'],self.normal['best_model'])
        self.assertEqual(self.normal['evaluation']['ranking_source'],'backtest_rmse')

    def test_holdout_mutation_cannot_change_ranking(self):
        p=fixture();rows=list(csv.reader(io.StringIO(p['csv'])))
        cutoff=self.normal['evaluation']['holdout_start']
        for row in rows[cutoff+1:]:row[1]=str(float(row[1])+10000)
        p['csv']=csv_text(rows[0],rows[1:]);changed=sales.forecast(p)
        self.assertEqual(changed['best_model'],self.normal['best_model'])
        self.assertEqual([(r['name'],r['backtest']) for r in changed['models']],[(r['name'],r['backtest']) for r in self.normal['models']])
        self.assertNotEqual(changed['holdout']['metrics']['rmse'],self.normal['holdout']['metrics']['rmse'])

    def test_full_refit_horizon_future_dates(self):
        r=self.normal
        self.assertEqual(r['refit_observations'],180)
        self.assertEqual(len(r['forecast']),12)
        self.assertGreater(r['forecast'][0]['date'],r['series'][-1]['date'])
        self.assertFalse(r['holdout']['used_for_ranking'])

    def test_interval_order_and_quantiles(self):
        for r in self.normal['forecast']:
            self.assertLessEqual(r['lower_95'],r['lower_80'])
            self.assertLessEqual(r['lower_80'],r['forecast'])
            self.assertLessEqual(r['forecast'],r['upper_80'])
            self.assertLessEqual(r['upper_80'],r['upper_95'])
        self.assertFalse(self.normal['intervals']['guaranteed_coverage'])

    def test_baseline_and_warning(self):
        self.assertTrue(any(r['name']=='Naive Forecast' and r['status']=='SUCCESS' for r in self.normal['models']))
        self.assertIsNotNone(sales.baseline_warning(0))
        self.assertIsNone(sales.baseline_warning(10))

    def test_model_failure_isolated_partial(self):
        original=sales.make_estimator
        def fail_one(name):
            if name=='Random Forest':raise RuntimeError('test failure')
            return original(name)
        with patch.object(sales,'make_estimator',side_effect=fail_one):
            with self.assertLogs(sales.logger,level='ERROR'):r=sales.forecast(fixture(80))
        self.assertTrue(r['partial'])
        self.assertEqual(next(m for m in r['models'] if m['name']=='Random Forest')['status'],'FAILED_SAFE')
        self.assertTrue(r['forecast'])

    def test_soft_budget_partial_keeps_baseline(self):
        r=sales.forecast(fixture(),soft_budget=0)
        self.assertEqual(r['forecast_model'],'Naive Forecast')
        self.assertTrue(any(m['status']=='SKIPPED_TIME_BUDGET' for m in r['models']))
        self.assertTrue(r['forecast'])

    def test_tiny_exploratory_no_fabricated_interval(self):
        r=sales.forecast(fixture(6))
        self.assertEqual(r['evaluation']['mode'],'exploratory_no_validation')
        self.assertEqual(r['evaluation']['ranking_source'],'none')
        self.assertIsNone(r['forecast'][0]['lower_95'])
        self.assertFalse(r['holdout']['dates'])

    def test_short_seasonal_safe_skip(self):
        r=sales.forecast(fixture(18,frequency='monthly'))
        self.assertEqual(next(m for m in r['models'] if m['name']=='Seasonal Naive')['status'],'SKIPPED_INSUFFICIENT_HISTORY')
        self.assertEqual(r['evaluation']['ranking_source'],'inner_validation_rmse')

    def test_zero_sales_metrics(self):
        m=sales.metrics([0,0,0],[0,0,0])
        self.assertEqual(m['rmse'],0);self.assertEqual(m['smape'],0)
        self.assertIsNone(m['mape']);self.assertIsNone(m['r2'])
        p=fixture(70);rows=list(csv.reader(io.StringIO(p['csv'])));
        for row in rows[1:]:row[1]=0
        p['csv']=csv_text(rows[0],rows[1:]);r=sales.forecast(p)
        self.assertTrue(all(p['forecast']==0 for p in r['forecast']))

    def test_negative_returns_not_clamped(self):
        p=fixture(6);rows=list(csv.reader(io.StringIO(p['csv'])))
        for row in rows[1:]:row[1]=-10
        p.update(csv=csv_text(rows[0],rows[1:]),clamp_nonnegative=True)
        r=sales.forecast(p)
        self.assertTrue(all(p['forecast']==-10 for p in r['forecast']))

    def test_optional_nonnegative_clamp_reported(self):
        original=sales.recursive_predict
        def force_final_negative(name,model,history,dates,schema,period,deadline=None):
            if len(history)==6:return np.full(len(dates),-5.)
            return original(name,model,history,dates,schema,period,deadline)
        with patch.object(sales,'recursive_predict',side_effect=force_final_negative):
            unclamped=sales.forecast(fixture(6))
            clamped=sales.forecast({**fixture(6),'clamp_nonnegative':True})
        self.assertEqual(unclamped['forecast'][0]['forecast'],-5)
        self.assertEqual(clamped['forecast'][0]['forecast'],0)
        self.assertTrue(any('clipped to zero' in w for w in clamped['warnings']))

    def test_final_refit_failure_falls_back_explicitly(self):
        original=sales.fit_model
        def fail_final(name,dates,y,schema):
            if len(y)==180:raise RuntimeError('refit failure')
            return original(name,dates,y,schema)
        with patch.object(sales,'fit_model',side_effect=fail_final):r=sales.forecast(fixture())
        self.assertEqual(r['best_model'],self.normal['best_model'])
        self.assertEqual(r['forecast_model'],'Naive Forecast')
        self.assertTrue(any('Refit' in w for w in r['warnings']))

    def test_horizon_validation(self):
        for value in [0,91,1.5,True,'30']:
            with self.assertRaises(sales.ForecastError):sales.forecast({**fixture(6),'horizon':value})

    def test_sample_real_training(self):
        r=sales.forecast(dict(sample=True,date_column='date',target_column='sales',horizon=30))
        self.assertEqual(r['refit_observations'],1096)
        self.assertGreaterEqual(sum(m['status']=='SUCCESS' for m in r['models']),4)
        self.assertTrue(r['metadata']['synthetic'])

    def test_long_full_data(self):
        r=sales.forecast(fixture(12000))
        self.assertEqual(r['refit_observations'],12000)
        self.assertEqual(len(r['series']),12000)
        self.assertTrue(r['forecast'])
        print('LONG DATA:',r['duration_ms'],'ms',r['best_model'],flush=True)


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),sales.handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()

    def request(self,payload=None,raw=None,method='POST'):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=65)
        conn.request(method,'/api/sales-forecast',raw if raw is not None else json.dumps(payload).encode() if payload else None,{'Content-Type':'application/json'})
        response=conn.getresponse();body=json.loads(response.read());headers=dict(response.getheaders());conn.close()
        return response.status,body,headers

    def test_real_worker_http(self):
        status,r,headers=self.request(fixture(80))
        self.assertEqual(status,200,r)
        self.assertFalse(r['raw_file_persisted'])
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertTrue(r['forecast'])
        self.assertGreaterEqual(sum(m['status']=='SUCCESS' for m in r['models']),4)

    def test_http_validation_and_no_trace(self):
        for payload in [dict(action='bad'),dict(action='forecast',csv='date,sales\ninvalid,1'),dict(action='forecast',**{'sample':True,'horizon':0})]:
            status,r,_=self.request(payload);self.assertIn(status,(400,422));self.assertNotIn('Traceback',json.dumps(r))
        self.assertEqual(self.request(raw=b'{')[0],400)
        with patch.object(sales,'dispatch',side_effect=RuntimeError('PRIVATE_INTERNAL')):
            with self.assertLogs(sales.logger,level='ERROR'):status,r,_=self.request({'action':'inspect'})
        self.assertEqual(status,500);self.assertNotIn('PRIVATE_INTERNAL',json.dumps(r))

    def test_hard_timeout(self):
        with patch.object(sales.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',55)):
            with self.assertRaises(sales.ForecastError) as ctx:sales.dispatch(fixture())
        self.assertEqual(ctx.exception.status,504)


def preview_headers(base):
    """Use an existing CLI session; never print, persist or export bypass tokens."""
    secret=os.environ.get('VERCEL_AUTOMATION_BYPASS_SECRET')
    cli=os.environ.get('SALES_QA_VERCEL_CLI')
    if not secret and cli:
        node=os.environ.get('SALES_QA_NODE','node')
        completed=subprocess.run([node,cli,'--debug','curl','/api/sales-forecast','--deployment',base,
                                  '--','--silent','--show-error','--fail'],capture_output=True,timeout=30,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        # CLI debug includes credentials. Capture it only in memory; never report
        # the log, including in failures. Extract just the header for this origin.
        debug=completed.stderr.decode('utf-8',errors='replace')
        match=re.search(r'x-vercel-protection-bypass:\s*([A-Za-z0-9._-]+)',debug)
        if match:secret=match[1]
        if completed.returncode and not secret:
            raise RuntimeError('Cannot authenticate protected Preview with Vercel CLI.')
    return {'x-vercel-protection-bypass':secret} if secret else {}


def cloud_checks(base, auth_headers=None):
    cases={'sample':dict(sample=True,date_column='date',target_column='sales',horizon=30,action='forecast'),
           'daily':fixture(),'monthly':fixture(60,frequency='monthly'),'decimal_comma':fixture(delimiter=';',decimal_comma=True),
           'xlsx':excel_fixture(),'multi_sheet':{**excel_fixture(multiple=True),'sheet':'Monthly'},'tiny':fixture(6),'long':fixture(12000)}
    missing=fixture(80);rows=list(csv.reader(io.StringIO(missing['csv'])));del rows[5];missing['csv']=csv_text(rows[0],rows[1:]);cases['missing']=missing
    duplicate=fixture(80);duplicate['csv']+='2021-01-01T00:00:00,5,South\n';cases['duplicate']=duplicate
    reports=[]
    for name,payload in cases.items():
        request=urllib.request.Request(base.rstrip('/')+'/api/sales-forecast',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**(auth_headers or {})})
        start=time.perf_counter()
        with urllib.request.urlopen(request,timeout=70) as response:
            result=json.load(response);assert response.status==200
        assert len(result['forecast'])==payload['horizon']
        assert result['forecast'][0]['date']>result['series'][-1]['date']
        assert not result['evaluation']['holdout_used_for_ranking']
        assert any(m['name']=='Naive Forecast' and m['status']=='SUCCESS' for m in result['models'])
        if name=='sample':assert sum(m['status']=='SUCCESS' for m in result['models'])>=4
        if name!='tiny':assert result['forecast'][0]['lower_95'] is not None
        for row in result['forecast']:
            if row['lower_95'] is not None:assert row['lower_95']<=row['lower_80']<=row['forecast']<=row['upper_80']<=row['upper_95']
        report=dict(case=name,status=200,seconds=round(time.perf_counter()-start,2),model=result['best_model'],models=[(m['name'],m['status']) for m in result['models']])
        reports.append(report);print(json.dumps(report),flush=True)
    out=Path(tempfile.gettempdir())/'sales-forecasting-qa';out.mkdir(exist_ok=True)
    (out/'cloud-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')


def browser_checks(base=None, auth_headers=None):
    from test_vietnam_map_online import CDP
    browser=os.environ.get('HEALTH_TEST_BROWSER',r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    out=Path(tempfile.gettempdir())/'sales-forecasting-qa';out.mkdir(exist_ok=True)
    script=(ROOT/'tests/sales-forecasting-browser.js').read_text(encoding='utf-8')
    server=None
    if not base:
        class Local(sales.handler,SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path.split('?')[0]=='/api/sales-forecast':return sales.handler.do_GET(self)
                return SimpleHTTPRequestHandler.do_GET(self)
            def do_POST(self):return sales.handler.do_POST(self)
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Local,directory=str(ROOT)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
    reports=[];process=None
    cookies=http.cookiejar.CookieJar()
    if base and auth_headers:
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        request=urllib.request.Request(base+'/api/sales-forecast',headers={**auth_headers,'x-vercel-set-bypass-cookie':'true'})
        with opener.open(request,timeout=30) as response:response.read()
    try:
        with tempfile.TemporaryDirectory(prefix='sales-forecast-browser-',ignore_cleanup_errors=True) as profile:
            process=subprocess.Popen([browser,'--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            portfile=Path(profile)/'DevToolsActivePort'
            for _ in range(150):
                if portfile.exists():break
                time.sleep(.1)
            port=int(portfile.read_text().splitlines()[0])
            target=json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')))
            cdp=CDP(target['webSocketDebuggerUrl']);cdp.s.settimeout(600);cdp.call('Page.enable')
            if cookies:
                cdp.call('Network.enable')
                cdp.call('Network.setCookies',{'cookies':[{'name':cookie.name,'value':cookie.value,'url':base,'path':cookie.path,'secure':True,'httpOnly':True} for cookie in cookies]})
            def js(code):
                response=cdp.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in response:raise RuntimeError(str(response['exceptionDetails']))
                return response.get('result',{}).get('value')
            for width in [320,390,768,1024,1440]:
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<=390})
                cdp.call('Page.navigate',{'url':base+'/sales-forecasting.html'})
                for _ in range(150):
                    if js("document.readyState==='complete'&&typeof SalesForecast!=='undefined'"):break
                    time.sleep(.1)
                js('window.__sfFixtures={}')
                fixtures={'daily':fixture(),'monthly':fixture(60,frequency='monthly'),'decimal':fixture(delimiter=';',decimal_comma=True),'excel':excel_fixture(multiple=True),'tiny':fixture(6)}
                if width==390:fixtures['long']=fixture(12000)
                for name,value in fixtures.items():
                    encoded=json.dumps(value);js('window.__sfChunks=[]')
                    for offset in range(0,len(encoded),12000):js('window.__sfChunks.push('+json.dumps(encoded[offset:offset+12000])+')')
                    js('window.__sfFixtures['+json.dumps(name)+']=JSON.parse(window.__sfChunks.join(""))')
                report=js(script);reports.append(report);print(json.dumps(report),flush=True)
                js('scrollTo(0,0)')
                screenshot=cdp.call('Page.captureScreenshot',{'format':'png'});(out/f'hero-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
                y=js("document.getElementById('forecastChart').getBoundingClientRect().top+scrollY-170")
                screenshot=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':max(0,y),'width':width,'height':1400,'scale':1}});(out/f'forecast-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':320,'height':1000,'deviceScaleFactor':1,'mobile':True});time.sleep(.3)
            assert js('document.documentElement.scrollWidth<=innerWidth')
            # Old modules are only loaded, never edited or submitted.
            for page in ['index.html','data-analyzer.html','health-prediction.html','vietnam-house-price.html','customer-return.html','ml-model-comparison.html']:
                cdp.call('Page.navigate',{'url':base+'/'+page})
                for _ in range(100):
                    if js("document.readyState==='complete'"):break
                    time.sleep(.1)
                assert js("document.body.innerText.length>100"),page
                if page=='index.html':
                    assert js("!!document.querySelector('a[href=\"sales-forecasting.html\"]')")
                    assert not js("document.querySelector('a[href=\"sales-forecasting.html\"]').closest('.project-card').innerText.includes('Sắp ra mắt')")
                    js("document.querySelector('a[href=\"sales-forecasting.html\"]').click()")
                    for _ in range(100):
                        if js("location.pathname.endsWith('/sales-forecasting.html')&&typeof SalesForecast!=='undefined'"):break
                        time.sleep(.1)
                    assert js("location.pathname.endsWith('/sales-forecasting.html')")
                    js("document.querySelector('.sf-header a[href=\"index.html#tools\"]').click()")
                    time.sleep(.2);assert js("location.pathname.endsWith('/index.html')")
                print('SMOKE PASS',page,flush=True)
            cdp.call('Browser.close');process.wait(timeout=15)
    finally:
        if process and process.poll() is None:process.kill()
        if server:server.shutdown();server.server_close()
    (out/('cloud-browser-report.json' if server is None else 'browser-report.json')).write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print('BROWSER PASS. Screenshots:',out,flush=True)


if __name__=='__main__':
    if '--cloud' in sys.argv:
        base=sys.argv[sys.argv.index('--cloud')+1]
        auth_headers=preview_headers(base)
        cloud_checks(base,auth_headers);browser_checks(base,auth_headers)
    elif '--browser-only' in sys.argv:browser_checks()
    else:
        suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (Parsing,Series,Temporal,Forecasting,HTTP)])
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():sys.exit(1)
        if '--backend-only' not in sys.argv:browser_checks()
