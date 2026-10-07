"""Real sklearn and HTTP/browser QA. Run python -B tests/test_ml_model_comparison.py.
Use --backend-only to omit browser. No external data or writes to old modules.
"""
import base64
import csv
import importlib.util
import io
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import numpy as np
from sklearn.datasets import make_classification, make_regression
from openpyxl import Workbook, load_workbook

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ml_compare', ROOT / 'api/ml-compare.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def csv_text(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def fixture(task='classification', count=120, classes=2, mixed=True):
    if task == 'classification':
        X, y = make_classification(n_samples=count, n_features=4, n_informative=3, n_redundant=0,
                                    n_classes=classes, n_clusters_per_class=1, random_state=47)
    else:
        X, y = make_regression(n_samples=count, n_features=4, noise=15, random_state=47)
    headers = ['x0','x1','x2','x3'] + (['segment','customer_id','event_date'] if mixed else []) + ['target']
    rows = []
    for i, (x, target) in enumerate(zip(X, y)):
        values = list(x)
        if mixed:
            if i % 13 == 0:
                values[0] = ''
            values += ['' if i % 17 == 0 else ['north','south','west'][i % 3], 'C' + str(i), f'2025-{i // 28 + 1:02d}-{i % 28 + 1:02d}']
        rows.append(values + [int(target) if task == 'classification' else target])
    return dict(action='benchmark',csv=csv_text(headers,rows),target='target',task=task,
                features=['x0','x1','x2','x3'] + (['segment'] if mixed else []),split='random')


def excel_fixture(task='classification', mixed=True, multiple=False, count=120):
    payload = fixture(task, mixed=mixed, count=count)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Dữ liệu'
    for row in csv.reader(io.StringIO(payload.pop('csv'))):
        sheet.append([None if value == '' else float(value) if lab.number(value) is not None else value for value in row])
    if multiple:
        other = workbook.create_sheet('Hồi quy')
        for row in csv.reader(io.StringIO(fixture('regression', mixed=False)['csv'])):
            other.append([float(value) if lab.number(value) is not None else value for value in row])
    buffer = io.BytesIO(); workbook.save(buffer); workbook.close()
    payload['xlsx'] = base64.b64encode(buffer.getvalue()).decode('ascii')
    return payload


def weak_fixture():
    payload=fixture('regression',count=60,mixed=False)
    rows=list(csv.reader(io.StringIO(payload['csv'])))
    rng=np.random.default_rng(20)
    for row,value in zip(rows[1:],rng.normal(size=60)):row[-1]=str(value)
    payload['csv']=csv_text(rows[0],rows[1:])
    return payload


def tiny_fixture(task='regression'):
    headers = ['name', 'age', 'score', 'city']
    ages = [31, 24, 42, '', 27, 38, 22, 47, 35, 29, 44]
    scores = [7.1, 4.8, 9.2, 5.7, 8.3, 6.4, 3.9, 7.6, '', 8.7, 5.2]
    rows = [[f'Person-{i}', ages[i], scores[i], ['Hanoi', 'Hue', 'Saigon', 'Danang'][i % 4]] for i in range(11)]
    rows.append(rows[0].copy())
    return dict(action='benchmark', csv=csv_text(headers, rows), task=task,
                target='score' if task=='regression' else 'city',
                features=['age', 'city'] if task=='regression' else ['age', 'score'], split='random')


def linelist_fixture(count=120):
    output = io.StringIO(); writer = csv.writer(output, delimiter=';')
    headers = ['case_id', '', 'latitude', 'age', 'event_date', 'location', 'outcome'] + [f'field_{i}' for i in range(21)]
    writer.writerow(headers)
    rng = np.random.default_rng(17)
    for i in range(count):
        writer.writerow([f'CASE-{i}', f'CODE-{i}', f'{rng.normal(-13, 2):.8f}'.replace('.', ','),
                         f'{rng.uniform(20, 70):.2f}'.replace('.', ','), f'2025-01-{i%28+1:02d}', f'LOC-{i}',
                         ['recovered', 'hospitalized', 'deceased'][i%3]] + [f'cat-{(i+j)%8}' for j in range(21)])
    return dict(action='benchmark', csv=output.getvalue(), target='outcome', task='classification',
                features=['latitude', 'age', 'location', 'field_0'], split='random')


def large_fixture(task='classification', count=6600):
    rng = np.random.default_rng(29)
    output = io.StringIO(); writer = csv.writer(output, delimiter=';')
    headers = ['case_id', 'gender', 'age', 'latitude', 'longitude', 'hospital', 'outcome', 'date_of_outcome', 'time', 'location', ''] + [f'lab_{j}' for j in range(16)] + ['salary']
    writer.writerow(headers)
    for i in range(count):
        age = rng.uniform(18, 80); labs = rng.normal(size=16)
        gender = '' if i % 71 == 0 else ('f' if labs[0] + rng.normal() > 0 else 'm')
        writer.writerow([f'C-{i}', gender, f'{age:.2f}'.replace('.', ','), f'{rng.normal(-13,2):.8f}'.replace('.', ','),
            f'{rng.normal(8,2):.9f}'.replace('.', ','), f'H-{i%12}', ['recovered','admitted','dead'][i%3],
            f'{2020+i//336:04d}-{i//28%12+1:02d}-{i%28+1:02d}', f'{i//60%24:02d}:{i%60:02d}', f'LOC-{i}', ''] +
            [('' if i%97==0 else f'{v:.4f}'.replace('.', ',')) for v in labs] + [f'{age*100+labs[1]*500+rng.normal(0,100):.2f}'.replace('.', ',')])
    target = 'gender' if task == 'classification' else 'salary'
    return dict(action='benchmark', csv=output.getvalue(), task=task, target=target,
        features=['age','latitude','longitude','hospital','outcome'] + [f'lab_{j}' for j in range(16)], split='random')


def dirty_fixture(task='regression', target=None):
    headers = ['employee_name','age','salary','score','city','department','join_date','note','','empty']
    rows = [[f'Person-{i}', '' if i%7==0 else 20+i%27, '--' if i%11==0 else f'{1000+i*13.7:.2f}'.replace('.', ','),
        '' if i%9==0 else (i*17)%100, ['Hue','Hanoi','Saigon'][i%3], ['HR','IT'][i%2], f'2025-01-{i%28+1:02d}', 'NA' if i%3 else 'note', '', ''] for i in range(39)]
    rows.append(rows[0].copy())
    output=io.StringIO(); writer=csv.writer(output,delimiter=';');writer.writerow(headers);writer.writerows(rows)
    return dict(action='benchmark',csv=output.getvalue(),task=task,target=target or ('salary' if task=='regression' else 'department'),
                features=['age','score','city','department','join_date','empty'] if task=='regression' else ['age','score','city','salary','join_date','empty'],split='random')


class Backend(unittest.TestCase):
    def test_numeric_target_column_evidence_and_diagnostics(self):
        p=dict(action='benchmark',csv='x;target\n1;12,5\n2;1,234\n3;13,7\n4;--\n5;bad\n6;NA',target='target',task='regression',features=['x'])
        d=lab.prepare(p)
        self.assertEqual(d['summary']['audit']['numeric_target'], dict(total_rows=6,nonblank_target_rows=4,valid_numeric_target_rows=3,missing_target_rows=2,invalid_numeric_target_rows=1,unique_numeric_target_values=3))
        self.assertIn(1.234,d['y'])
        self.assertIsNone(lab.number('1,234'))

    def test_leakage_structured_exclude_and_confirm_without_422_loop(self):
        p=fixture(); headers,rows,_=lab.load_data(p)
        headers+=['outcome','copy']; rows=[tuple(r)+('known-'+str(i%3),r[-1]) for i,r in enumerate(rows)]
        p['csv']=csv_text(headers,rows);p['features']+=['outcome','copy']
        d=lab.prepare(p);self.assertNotIn('copy',d['names']);self.assertNotIn('outcome',d['names'])
        self.assertTrue(any(m['severity']=='hard' for m in d['leakage']))
        self.assertTrue(any(m['severity']=='warning' for m in d['leakage']))
        d=lab.prepare({**p,'ack_leakage':True});self.assertIn('outcome',d['names']);self.assertNotIn('copy',d['names'])

    def test_date_target_validation_and_time_guard(self):
        p=large_fixture(count=120);p.update(target='date_of_outcome')
        with self.assertRaisesRegex(lab.LabError,'ngày tháng'):lab.prepare(p)
        with self.assertRaisesRegex(lab.LabError,'duration'):lab.prepare({**p,'task':'regression'})
        p.update(target='gender',features=['age','latitude','longitude','time','date_of_outcome','lab_0'])
        d=lab.prepare(p);self.assertNotIn('time',d['names']);self.assertNotIn('date_of_outcome',d['names'])
        self.assertIn('latitude',[d['names'][i] for i in d['numeric']]);self.assertNotIn('gender',d['names'])

    def test_dirty_classification_and_regression(self):
        for task,target in [('classification','department'),('classification','city'),('regression','salary'),('regression','score')]:
            p=dirty_fixture(task,target);p['features']=[f for f in p['features'] if f!=target]
            r=lab.benchmark(p);self.assertTrue(r['models']);self.assertEqual(r['summary']['audit']['duplicates_removed'],1)
            self.assertNotIn('empty',r['methodology']['selected_features'])

    def test_large_gender_and_regression_bounded_partial_leaderboard(self):
        for task in ('classification','regression'):
            p=large_fixture(task,6600 if task=='classification' else 5100)
            r=lab.benchmark(p);self.assertTrue(r['models']);self.assertLess(r['duration_ms'],50000)
            self.assertNotIn(p['target'],r['methodology']['selected_features'])
            self.assertFalse(r['methodology']['test_used_for_selection'])
            self.assertTrue(any(s['status']=='SKIPPED_TIME_BUDGET' for s in r['skipped']))
            self.assertLessEqual(r['methodology']['feature_guard']['estimated_after'],lab.MAX_EXPANDED)

    def test_soft_time_budget_preserves_completed_models(self):
        original=lab.time.perf_counter; started=original(); fits=[0]
        original_fit=lab.fit_with_budget
        def fit(*args):
            result=original_fit(*args);fits[0]+=1;return result
        def clock():
            return original() if fits[0]<6 else started+46
        with patch.object(lab.time,'perf_counter',side_effect=clock), patch.object(lab,'fit_with_budget',side_effect=fit):
            r=lab.benchmark(fixture())
        self.assertTrue(r['models']);self.assertTrue(r['skipped'])

    def test_delimiters_bom_quotes_blank_rows_and_header_fallback(self):
        for delimiter in [',', ';', '\t', '|']:
            with self.subTest(delimiter=delimiter):
                buffer=io.StringIO(); writer=csv.writer(buffer,delimiter=delimiter)
                writer.writerows([[' col ', '', 'col', 'col_2', 'target'], ['1', '2', 'contains'+delimiter+'quoted', '4', 'yes'], ['2'], [], ['3','4','x','5','no']])
                with patch.object(lab.csv.Sniffer,'sniff',side_effect=csv.Error):
                    headers,rows,audit=lab.parse_csv('\ufeff'+buffer.getvalue())
                self.assertEqual(audit['delimiter'],delimiter)
                self.assertEqual(len(headers),len(set(headers)))
                self.assertEqual(headers[:3],['col','unnamed_2','col_2'])
                self.assertEqual(rows[0][2],'contains'+delimiter+'quoted')
                self.assertEqual(audit['blank_rows'],1)
                self.assertEqual(audit['short_rows_padded'],1)
        headers,rows,audit=lab.parse_csv('\ufeff\n\n x ; y \n1;2\n')
        self.assertEqual(headers,['x','y']);self.assertEqual(audit['blank_rows'],2)

    def test_decimal_locales_and_ambiguous_number_never_guessed(self):
        for token,value in [('123.45',123.45),('123,45',123.45),('1,234.56',1234.56),('1.234,56',1234.56),('-13,21573511',-13.21573511),('1.2e2',120)]:
            with self.subTest(token=token):self.assertAlmostEqual(lab.number(token),value)
        self.assertIsNone(lab.number('1,234')); self.assertIsNone(lab.number('1,23,456'))
        headers,rows,audit=lab.parse_csv('value;target\n1,234;yes\n2,345;no\n')
        self.assertEqual(lab.profile(headers,rows,audit)['columns'][0]['kind'],'categorical')
        self.assertEqual(audit['ambiguous_numeric_cells'],2)
        self.assertTrue(audit['warnings'])
        p=linelist_fixture(); data=lab.prepare(p)
        self.assertEqual(data['summary']['audit']['delimiter'],';')
        self.assertGreater(data['summary']['audit']['localized_numeric_cells'],0)
        self.assertIn('unnamed_2',[c['name'] for c in data['summary']['columns']])
        self.assertEqual(data['numeric'],[0,1])
        self.assertEqual(len(lab.benchmark(p)['models']),7)

    def test_twelve_row_regression_cv_only_and_target_cleaning(self):
        result=lab.benchmark(tiny_fixture())
        self.assertEqual(result['evaluation']['tier'],'tiny')
        self.assertEqual(result['evaluation']['mode'],'cv_only')
        self.assertEqual(result['evaluation']['usable_rows'],10)
        self.assertEqual(result['summary']['audit']['duplicates_removed'],1)
        self.assertEqual(result['summary']['audit']['target_rows_removed'],1)
        self.assertEqual(result['selection_source'],'cv_only')
        self.assertEqual(len(result['models']),8)
        self.assertEqual(result['recommended'],result['models'][0]['name'])
        self.assertTrue(all(r['test'] is None and r['generalization_gap'] is None and r['cv_scores'] for r in result['models']))
        self.assertEqual(result['methodology']['test_rows'],0)
        self.assertTrue(any('Đã loại 1 dòng' in w for w in result['warnings']))
        json.dumps(lab.sanitize(result),allow_nan=False)

    def test_twelve_row_multiclass_adapts_folds_and_knn(self):
        p=tiny_fixture('classification'); data=lab.prepare(p); result=lab.benchmark(p)
        self.assertEqual(result['evaluation']['class_count'],4)
        self.assertEqual(result['methodology']['folds'],2)
        self.assertEqual(len(result['models']),7)
        self.assertEqual(result['selection_source'],'cv_only')
        for a,b in data['splits']:
            self.assertEqual(set(data['y'][a]),set(data['y']))
            self.assertFalse(set(a)&set(b))
        knn=next(r for r in result['models'] if r['name']=='K-Nearest Neighbors')
        self.assertLessEqual(knn['hyperparameters']['n_neighbors'],min(len(a) for a,_ in data['splits']))

    def test_extreme_tiny_binary_and_regression_knn_adaptation(self):
        for task in ['classification','regression']:
            p=fixture(task,count=6,mixed=False); result=lab.benchmark(p); data=lab.prepare(p)
            self.assertEqual(result['evaluation']['tier'],'extreme_tiny')
            self.assertEqual(result['selection_source'],'cv_only')
            knn=next(r for r in result['models'] if r['name'] in ('K-Nearest Neighbors','KNN Regressor'))
            self.assertLessEqual(knn['hyperparameters']['n_neighbors'],min(len(a) for a,_ in data['splits']))
            self.assertTrue(any('Dữ liệu rất ít' in w for w in result['warnings']))

    def test_exploratory_singleton_classes_and_two_row_regression(self):
        for task,text in [('classification','x,target\n1,a\n4,b\n2,c\n'),('regression','x,target\n1,2\n3,8\n')]:
            result=lab.benchmark(dict(action='benchmark',csv=text,target='target',task=task,features=['x']))
            self.assertEqual(result['evaluation']['mode'],'exploratory')
            self.assertIsNone(result['recommended'])
            self.assertTrue(result['best_exploratory_model'])
            self.assertEqual(result['selection_source'],'exploratory_train')
            self.assertTrue(all(r['cv_mean'] is None and r['test'] is None and not r['cv_scores'] for r in result['models']))
            self.assertFalse(result['evaluation']['independent_evaluation'])
            self.assertTrue(any('không có đánh giá độc lập' in w for w in result['warnings']))

    def test_small_rare_class_uses_cv_only_instead_of_reject(self):
        p=fixture(count=32,mixed=False); headers,rows,_=lab.load_data(p)
        rows=[tuple(r[:-1])+('rare' if i<2 else 'common',) for i,r in enumerate(rows)]
        p['csv']=csv_text(headers,rows)
        data=lab.prepare(p)
        self.assertEqual(data['evaluation']['mode'],'cv_only')
        self.assertEqual(len(data['splits']),2)
        rows=[tuple(r[:-1])+('rare' if i<3 else 'common',) for i,r in enumerate(rows)]
        p['csv']=csv_text(headers,rows)
        data=lab.prepare(p)
        self.assertEqual(data['evaluation']['mode'],'holdout_cv')
        self.assertEqual(data['evaluation']['label'],f"Small Data {len(data['splits'])}-Fold CV")
        self.assertEqual(len(data['splits']),2)

    def test_model_and_diagnostics_failures_are_isolated_and_sanitized(self):
        with patch.object(lab.LogisticRegression,'fit',side_effect=RuntimeError('PRIVATE_MODEL_ERROR')), self.assertLogs(lab.logger,level='ERROR'):
            result=lab.benchmark(fixture(mixed=False))
        self.assertEqual(len(result['models']),6)
        self.assertEqual(result['skipped'][0]['status'],'FAILED_SAFE')
        self.assertNotIn('PRIVATE_MODEL_ERROR',json.dumps(result))
        original=lab.add_diagnostics
        def fail_one(record,pipe,data):
            if record['name']=='Support Vector Machine':raise RuntimeError('PRIVATE_DIAGNOSTICS')
            return original(record,pipe,data)
        with patch.object(lab,'add_diagnostics',side_effect=fail_one), self.assertLogs(lab.logger,level='ERROR'):
            result=lab.benchmark(fixture(mixed=False))
        self.assertEqual(len(result['models']),7)
        self.assertTrue(any(r.get('diagnostics_status')=='FAILED_SAFE' for r in result['models']))
        self.assertNotIn('PRIVATE_DIAGNOSTICS',json.dumps(result))

    def test_feature_explosion_groups_categories_within_budget(self):
        headers=[f'category_{i}' for i in range(90)]+['target']
        rows=[[f'value-{(j+i*7)%70}' for i in range(90)]+[j%2] for j in range(160)]
        p=dict(action='benchmark',csv=csv_text(headers,rows),target='target',task='classification',features=headers[:-1])
        data=lab.prepare(p)
        self.assertLessEqual(data['expanded_estimate'],lab.MAX_EXPANDED)
        self.assertLess(data['max_categories'],32)
        transformed=lab.preprocessor(data,False).fit_transform(data['X'][data['train']])
        self.assertLessEqual(transformed.shape[1],lab.MAX_EXPANDED)
        self.assertLessEqual(transformed.shape[1]*len(rows),lab.MAX_CELLS)
        self.assertTrue(any('ngân sách' in w or 'gộp category' in w for w in data['warnings']))

    def test_all_missing_feature_dropped_but_impossible_input_clear(self):
        p=tiny_fixture();headers,rows,_=lab.load_data(p);headers+=['empty'];rows=[tuple(r)+(None,) for r in rows]
        p['csv']=csv_text(headers,rows);p['features']+=['empty']
        self.assertNotIn('empty',lab.prepare(p)['names'])
        for text in ['x,target\n1,NA\n2,NA\n','x,target\n1,a\n2,a\n','x,target\n1,a\n']:
            with self.assertRaises(lab.LabError) as error:
                lab.prepare(dict(csv=text,target='target',task='classification',features=['x']))
            self.assertEqual(error.exception.status,422)

    def test_tiny_temporal_cv_keeps_equal_timestamps_together(self):
        p=fixture('regression',count=24);headers,rows,_=lab.load_data(p)
        index=headers.index('event_date')
        rows=[tuple(f'2025-01-{int(i**.5)+1:02d}' if j==index else v for j,v in enumerate(row)) for i,row in enumerate(rows)]
        p.update(csv=csv_text(headers,rows),split='temporal',time_column='event_date')
        data=lab.prepare(p)
        self.assertEqual(data['evaluation']['mode'],'cv_only')
        self.assertEqual(data['cv_name'],'TimeSeriesSplit')
        for a,b in data['splits']:
            earlier={rows[data['train'][i]][index] for i in a}
            later={rows[data['train'][i]][index] for i in b}
            self.assertFalse(earlier&later)
            self.assertLess(max(earlier),min(later))

    def test_numeric_id_target_can_be_chosen_with_warning(self):
        p=fixture('regression',count=24,mixed=False);headers,rows,_=lab.load_data(p)
        headers[-1]='case_id';rows=[tuple(r[:-1])+(str(i+1),) for i,r in enumerate(rows)]
        p.update(csv=csv_text(headers,rows),target='case_id')
        data=lab.prepare(p)
        self.assertTrue(any('Target có dạng ID/ngày' in w for w in data['warnings']))
        self.assertEqual(data['evaluation']['mode'],'cv_only')
        headers,rows,audit=lab.parse_csv(csv_text(['age','city'],[[20+i,['a','b','c','d'][i%4]] for i in range(12)]))
        self.assertFalse(lab.profile(headers,rows,audit)['columns'][0]['id_like'])

    def test_worker_environment_preserves_order_existing_paths_and_separator(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = str(Path(directory) / 'existing')
            with patch.object(lab.sys, 'path', [directory, '', directory, None]), \
                 patch.dict(lab.os.environ, {'PYTHONPATH': os.pathsep.join([existing, directory, '', existing])}):
                before = os.environ.copy()
                env = lab._worker_environment()
                self.assertEqual(env['PYTHONPATH'], os.pathsep.join([directory, existing]))
                self.assertEqual(env['PYTHONPATH'].split(os.pathsep), [directory, existing])
                self.assertEqual(os.environ.copy(), before)
                self.assertEqual({k: v for k, v in env.items() if k != 'PYTHONPATH'},
                                 {k: v for k, v in before.items() if k != 'PYTHONPATH'})

    def test_child_imports_module_from_injected_parent_path(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'worker_runtime_path_probe.py').write_text('VALUE = 47\n', encoding='utf-8')
            with patch.object(lab.sys, 'path', [directory] + sys.path):
                result = subprocess.run([sys.executable, '-B', '-c',
                                         'import worker_runtime_path_probe as probe; print(probe.VALUE)'],
                                        env=lab._worker_environment(), capture_output=True, timeout=15,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout.strip(), b'47')

    def test_worker_exception_logged_and_client_sanitized(self):
        from types import SimpleNamespace
        request = {'action': 'benchmark', 'csv': 'RAW_REQUEST_MUST_NOT_BE_LOGGED'}
        output = io.BytesIO()
        with patch.object(lab.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode()))), \
             patch.object(lab.sys, 'stdout', SimpleNamespace(buffer=output)), \
             patch.object(lab, 'benchmark', side_effect=RuntimeError('PRIVATE_WORKER_FAILURE')), \
             self.assertLogs(lab.logger, level='ERROR') as logs:
            lab.run_worker()
        logged = '\n'.join(logs.output)
        self.assertIn('Traceback', logged)
        self.assertIn('RuntimeError: PRIVATE_WORKER_FAILURE', logged)
        self.assertNotIn('RAW_REQUEST_MUST_NOT_BE_LOGGED', logged)
        response = json.loads(output.getvalue())
        self.assertEqual(response['status'], 500)
        self.assertNotIn('PRIVATE_WORKER_FAILURE', str(response))
        self.assertNotIn('Traceback', str(response))

    def test_worker_startup_stderr_reaches_server_not_client(self):
        completed = subprocess.CompletedProcess([], 1, stdout=b'')
        with patch.object(lab.subprocess, 'run', return_value=completed) as run, \
             self.assertLogs(lab.logger, level='ERROR') as logs:
            with self.assertRaises(lab.LabError) as error:
                lab.dispatch(fixture())
        self.assertIsNone(run.call_args.kwargs['stderr'])
        self.assertEqual(run.call_args.kwargs['env'], lab._worker_environment())
        self.assertEqual(run.call_args.kwargs['timeout'], 55)
        self.assertEqual(error.exception.status, 500)
        self.assertIn('worker exited with code=1', '\n'.join(logs.output))
        self.assertNotIn('Traceback', str(error.exception))

    def test_xlsx_without_pandas_and_excel_empty_cells(self):
        import builtins
        workbook = Workbook(); sheet = workbook.active
        sheet.append([' x ', None, 'target'])
        sheet.append([1, '=1+1', 'yes'])  # Uncached formula is missing with data_only.
        sheet.append([2, '#DIV/0!', 'no'])
        sheet.append([None, None, None])
        sheet.append([3, 'NA', 'yes'])
        sheet.cell(10, 6).value = None  # Formatted trailing blanks are not columns.
        sheet.cell(10, 6).number_format = '0.00'
        buffer = io.BytesIO(); workbook.save(buffer); workbook.close()
        original = builtins.__import__
        def no_pandas(name, *args, **kwargs):
            if name.split('.')[0] == 'pandas':
                raise AssertionError('Production XLSX must not import pandas')
            return original(name, *args, **kwargs)
        with patch.object(builtins, '__import__', no_pandas):
            headers, rows, audit = lab.load_data({'xlsx': base64.b64encode(buffer.getvalue()).decode()})
        self.assertEqual(headers, ['x', 'unnamed_2', 'target'])
        self.assertEqual(rows, [('1', None, 'yes'), ('2', None, 'no'), ('3', None, 'yes')])
        self.assertEqual(audit['blank_rows'], 1)
        self.assertEqual(audit['short_rows_padded'], 0)

    def test_xlsx_stale_dimensions_do_not_truncate_cells(self):
        import zipfile
        payload = excel_fixture()
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload['xlsx']))) as source:
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as dest:
                for entry in source.infolist():
                    content = source.read(entry)
                    if entry.filename == 'xl/worksheets/sheet1.xml':
                        import re
                        content = re.sub(br'<dimension ref="[^"]+"', b'<dimension ref="A1:A1"', content)
                    dest.writestr(entry, content)
        payload['xlsx'] = base64.b64encode(output.getvalue()).decode()
        headers, rows, _ = lab.load_data(payload)
        self.assertEqual(len(headers), 8)
        self.assertEqual(len(rows), 120)

    def test_xlsx_numeric_mixed_missing_and_shared_pipeline(self):
        for task, mixed in [('classification',False),('classification',True),('regression',True)]:
            with self.subTest(task=task,mixed=mixed):
                payload = excel_fixture(task,mixed)
                headers,rows,audit = lab.load_data(payload)
                summary = lab.dispatch({**payload,'action':'inspect','target':'target'})
                self.assertEqual(audit['selected_sheet'],'Dữ liệu')
                self.assertEqual(summary['rows'],120)
                self.assertEqual(summary['columns'][-1]['suggested_task'],task)
                self.assertEqual(summary['missing'] > 0,mixed)
                result = lab.benchmark(payload)
                self.assertEqual(result['selection_source'],'train_cv')
                self.assertEqual(len(result['models']),7 if task=='classification' else 8)
                self.assertFalse(result['raw_file_persisted'])
                self.assertNotIn('xlsx',result)
                self.assertNotIn('preview',result['summary'])

    def test_xlsx_multiple_sheets_and_explicit_selection(self):
        payload = excel_fixture(multiple=True)
        summary = lab.dispatch({**payload,'action':'inspect'})
        self.assertEqual(summary['audit']['sheets'],['Dữ liệu','Hồi quy'])
        self.assertEqual(summary['columns'][-1]['suggested_task'],'classification')
        selected = {**payload,'sheet':'Hồi quy','task':'regression','features':['x0','x1','x2','x3']}
        self.assertEqual(lab.dispatch({**selected,'action':'inspect'})['columns'][-1]['suggested_task'],'regression')
        result = lab.benchmark(selected)
        self.assertEqual(result['summary']['audit']['selected_sheet'],'Hồi quy')
        with self.assertRaises(lab.LabError): lab.load_data({**payload,'sheet':'missing'})
        with self.assertRaises(lab.LabError): lab.prepare({**selected,'target':'absent'})

    def test_xlsx_cleaning_and_native_dates(self):
        from datetime import datetime
        payload=excel_fixture()
        workbook=load_workbook(io.BytesIO(base64.b64decode(payload['xlsx'])))
        sheet=workbook.active
        sheet.cell(2,7,datetime(2025,1,1))
        sheet.append([cell.value for cell in sheet[2]])
        sheet.append([None]*8)
        sheet.append([1,2,3,4,'north','C-missing','2025-12-31',None])
        buffer=io.BytesIO();workbook.save(buffer);workbook.close()
        payload['xlsx']=base64.b64encode(buffer.getvalue()).decode()
        summary=lab.dispatch({**payload,'action':'inspect'})
        self.assertEqual(summary['audit']['duplicates_removed'],1)
        self.assertEqual(summary['audit']['blank_rows'],1)
        self.assertTrue(summary['columns'][5]['id_like'])
        self.assertTrue(summary['columns'][6]['date'])
        self.assertEqual(lab.prepare(payload)['summary']['audit']['target_rows_removed'],1)

    def test_xlsx_invalid_and_resource_limits(self):
        for encoded in ['not base64',base64.b64encode(b'a,b\n1,2').decode(),base64.b64encode(b'PK\x03\x04broken').decode()]:
            with self.assertRaises(lab.LabError) as caught:lab.load_data({'xlsx':encoded})
            self.assertIn(caught.exception.status,(400,422))
            self.assertNotIn('Traceback',str(caught.exception))
        for rows,columns in [(20002,2),(2,101)]:
            workbook=Workbook();sheet=workbook.active
            sheet.cell(rows,columns,'too large')
            buffer=io.BytesIO();workbook.save(buffer);workbook.close()
            with self.assertRaises(lab.LabError) as caught:lab.load_data({'xlsx':base64.b64encode(buffer.getvalue()).decode()})
            self.assertEqual(caught.exception.status,413)
        # All sheets are checked, including sheets not selected by the user.
        workbook=Workbook();workbook.active.append(['x','target']);workbook.active.append([1,0])
        workbook.create_sheet('Oversized').cell(20002,1,'large')
        buffer=io.BytesIO();workbook.save(buffer);workbook.close()
        with self.assertRaises(lab.LabError) as caught:lab.load_data({'xlsx':base64.b64encode(buffer.getvalue()).decode(),'sheet':'Sheet'})
        self.assertEqual(caught.exception.status,413)
        with self.assertRaises(lab.LabError) as caught:lab.load_data({'xlsx':'A'*(4*((lab.MAX_CSV_BYTES+2)//3)+1)})
        self.assertEqual(caught.exception.status,413)

    def test_small_data_and_low_quality_do_not_change_cv_recommendation(self):
        self.assertTrue(any('khá nhỏ' in w for w in lab.prepare(fixture(count=60))['warnings']))
        self.assertEqual(lab.prepare(fixture(count=35))['evaluation']['tier'],'small')
        original=lab.evaluate
        for task in ['classification','regression']:
            def weak_test(pipe,X,y,current_task):
                values,pred,elapsed,curves=original(pipe,X,y,current_task)
                if len(y)==30:values['f1' if current_task=='classification' else 'r2']=.01 if current_task=='classification' else -.5
                return values,pred,elapsed,curves
            with patch.object(lab,'evaluate',weak_test):result=lab.benchmark(fixture(task,mixed=False))
            self.assertEqual(result['quality']['level'],'low')
            self.assertEqual(result['recommended'],result['models'][0]['name'])
            self.assertEqual(result['selection_source'],'train_cv')
            self.assertFalse(result['methodology']['test_used_for_selection'])

        def near_zero(pipe,X,y,current_task):
            values,pred,elapsed,curves=original(pipe,X,y,current_task)
            if len(y)==30:values['r2']=.05
            return values,pred,elapsed,curves
        with patch.object(lab,'evaluate',near_zero):result=lab.benchmark(fixture('regression',mixed=False))
        self.assertEqual(result['quality']['level'],'caution')

    def test_binary_mixed_missing_and_metrics(self):
        payload = fixture()
        result = lab.benchmark(payload)
        self.assertEqual(len(result['models']),7)
        self.assertFalse(result['raw_file_persisted'])
        self.assertNotIn('preview',result['summary'])
        self.assertEqual(result['methodology']['cv'],'StratifiedKFold')
        self.assertEqual(result['methodology']['folds'],5)
        self.assertEqual(result['recommended'],result['models'][0]['name'])
        for model in result['models']:
            self.assertEqual(sum(map(sum,model['confusion']['matrix'])),30)
            self.assertEqual(len(model['cv_scores']),5)
            self.assertTrue(0 <= model['test']['f1'] <= 1)
            self.assertTrue(model['fit_time_ms'] > 0 and model['predict_time_ms'] > 0)
            self.assertTrue(model['model_size_bytes'] > 0)
            self.assertIn('classification_report',model)
            self.assertTrue(model['curves']['roc'] and model['curves']['pr'])
        json.dumps(lab.sanitize(result),allow_nan=False)

    def test_multiclass_numeric(self):
        result=lab.benchmark(fixture(classes=3,mixed=False))
        self.assertEqual(len(result['models']),7)
        for model in result['models']:
            self.assertEqual(len(model['confusion']['labels']),3)
            self.assertIsNone(model['curves'])

    def test_regression(self):
        result=lab.benchmark(fixture('regression'))
        self.assertEqual(len(result['models']),8)
        self.assertEqual(result['methodology']['cv'],'KFold')
        for model in result['models']:
            self.assertAlmostEqual(model['test']['rmse']**2,model['test']['mse'],places=6)
            actual,predicted=model['scatter'][0]
            self.assertAlmostEqual(model['residuals'][0][1],actual-predicted)

    def test_ranking_ignores_test(self):
        rows=[dict(name='A',cv_mean=.8,cv_std=.1,cv_fit_ms=10,test={'f1':.01}),
              dict(name='B',cv_mean=.7,cv_std=.01,cv_fit_ms=1,test={'f1':1})]
        self.assertEqual(lab.rank_models(rows,'classification')[0]['name'],'A')
        rows[0]['test']['f1']=1; rows[1]['test']['f1']=0
        self.assertEqual(lab.rank_models(rows,'classification')[0]['name'],'A')
        rows[0]['cv_mean']=10; rows[1]['cv_mean']=11
        rows[0]['test']={'rmse':999}; rows[1]['test']={'rmse':0}
        self.assertEqual(lab.rank_models(rows,'regression')[0]['name'],'A')

    def test_actual_benchmark_keeps_cv_choice_when_test_winner_changes(self):
        payload=fixture(mixed=False)
        # Full fixture ties NB and SVM on both CV mean and std. Its legitimate
        # timing tie-break can change between runs, unrelated to held-out scores.
        # Use two real estimators with distinct CV scores to isolate this invariant.
        catalogue=[m for m in lab.models('classification') if m[0] in ('Gaussian Naive Bayes','Logistic Regression')]
        with patch.object(lab,'models',return_value=catalogue):baseline=lab.benchmark(payload)
        self.assertNotEqual(baseline['models'][0]['cv_mean'],baseline['models'][1]['cv_mean'])
        winner=baseline['recommended']
        original=lab.evaluate
        def altered(pipe,X,y,task):
            values,pred,time_ms,curves=original(pipe,X,y,task)
            if len(y)==30:
                # Forced held-out ranking contradiction, only in this test.
                values['f1']=0 if type(pipe.named_steps['model']).__name__==baseline['models'][0]['algorithm_type'] else 1
            return values,pred,time_ms,curves
        with patch.object(lab,'evaluate',altered),patch.object(lab,'models',return_value=catalogue):
            result=lab.benchmark(payload)
        self.assertEqual(result['recommended'],winner)
        self.assertEqual(result['models'][0]['test']['f1'],0)
        self.assertEqual(max(r['test']['f1'] for r in result['models']),1)

    def test_preprocessing_fits_train_only_and_inside_folds(self):
        data=lab.prepare(fixture())
        X=data['X'].copy(); train,test=data['train'],data['test']
        X[test,0]=1000000; X[test,4]='TEST_ONLY_CATEGORY'
        p=lab.preprocessor(data,True).fit(X[train])
        numeric=p.named_transformers_['numeric']
        self.assertAlmostEqual(numeric.named_steps['imputer'].statistics_[0],np.nanmedian(np.asarray(X[train,0],dtype=float)))
        self.assertTrue(numeric.named_steps['scaler'].mean_[0] < 100)
        self.assertNotIn('TEST_ONLY_CATEGORY',p.named_transformers_['categorical'].named_steps['onehot'].categories_[0])
        self.assertEqual(p.transform(X[test]).shape[0],len(test))
        a,b=data['splits'][0]; X[train[b],4]='VALIDATION_ONLY'
        folded=lab.preprocessor(data,True).fit(X[train[a]])
        self.assertNotIn('VALIDATION_ONLY',folded.named_transformers_['categorical'].named_steps['onehot'].categories_[0])
        # Observe the real benchmark fit path, including every CV fit and final fit.
        original=lab.ColumnTransformer.fit_transform
        seen=[]
        def spy(transformer,array,*args,**kwargs):
            seen.append(len(array))
            return original(transformer,array,*args,**kwargs)
        with patch.object(lab.ColumnTransformer,'fit_transform',spy):
            lab.benchmark(fixture())
        expected=[len(a) for a,_ in data['splits']]+[len(train)]
        self.assertEqual(seen,expected*7)

    def test_csv_quality(self):
        text='\ufeff a ,a, target\n1,NA,yes\n1,NA,yes\n\n2,null,no\n3\n'
        headers,rows,audit=lab.parse_csv(text)
        self.assertEqual(headers,['a','a_2','target'])
        self.assertEqual(audit['duplicates_removed'],1)
        self.assertEqual(audit['blank_rows'],1)
        self.assertEqual(audit['short_rows_padded'],1)
        self.assertIsNone(rows[-1][-1])
        with self.assertRaises(lab.LabError):lab.parse_csv('a,b\n1,2,3')

    def test_ambiguous_dates_never_onehot(self):
        p=fixture();headers,rows,audit=lab.load_data(p)
        i=headers.index('event_date')
        rows=[tuple('01/02/2025' if j==i else v for j,v in enumerate(r)) for r in rows]
        p['csv']=csv_text(headers,rows);p['features']+=['event_date']
        self.assertTrue(lab.profile(headers,rows,audit)['columns'][i]['date'])
        self.assertNotIn('event_date',lab.prepare(p)['names'])
        extracted=lab.prepare({**p,'date_features':'extract'})
        self.assertNotIn('event_date',extracted['names'])
        self.assertTrue(any('ngày mơ hồ' in w for w in extracted['warnings']))
        self.assertEqual(lab.date('31/12/2025').month,12)
        self.assertEqual(lab.date('12/31/2025').month,12)

    def test_target_validation(self):
        p=fixture()
        for target in ('absent','customer_id','event_date'):
            with self.subTest(target=target),self.assertRaises(lab.LabError):lab.prepare({**p,'target':target})
        for value in ('','same'):
            p['csv']=csv_text(['x','target'],[[i,value] for i in range(60)])
            p['features']=['x']
            with self.assertRaises(lab.LabError):lab.prepare(p)
        with self.assertRaises(lab.LabError):lab.prepare({**fixture(),'features':['target']})
        with self.assertRaises(lab.LabError):lab.prepare({**fixture(),'task':'invalid'})

    def test_id_and_detection(self):
        headers,rows,audit=lab.load_data(fixture())
        summary=lab.profile(headers,rows,audit)
        by_name={c['name']:c for c in summary['columns']}
        self.assertTrue(by_name['customer_id']['id_like'])
        self.assertTrue(by_name['event_date']['date'])
        self.assertEqual(by_name['target']['suggested_task'],'classification')
        self.assertFalse(by_name['x1']['id_like'])
        headers,rows,audit=lab.load_data(fixture('regression'))
        self.assertEqual(lab.profile(headers,rows,audit)['columns'][-1]['suggested_task'],'regression')

    def test_temporal_and_date_features(self):
        p=fixture('regression')
        p.update(split='temporal',time_column='event_date',date_features='extract')
        p['features']+=['event_date']
        data=lab.prepare(p)
        self.assertEqual(data['train'].tolist(),list(range(90)))
        self.assertEqual(data['test'].tolist(),list(range(90,120)))
        for train,valid in data['splits']:self.assertLess(max(train),min(valid))
        self.assertIn('event_date__day_of_week',data['names'])
        result=lab.benchmark(p)
        self.assertEqual(result['methodology']['cv'],'TimeSeriesSplit')
        self.assertEqual(len(result['models']),8)
        p=fixture();p.update(split='temporal',time_column='event_date')
        self.assertEqual(lab.benchmark(p)['methodology']['cv'],'TimeSeriesSplit')
        with self.assertRaises(lab.LabError):lab.prepare({**p,'time_column':'customer_id'})

    def test_small_and_large_guards(self):
        result=lab.benchmark(fixture(count=35,mixed=False))
        self.assertEqual(len(result['models']),7)
        self.assertEqual(len(result['skipped']),0)
        self.assertEqual(lab.prepare(fixture(count=15,mixed=False))['evaluation']['mode'],'cv_only')
        with self.assertRaises(lab.LabError) as error:lab.parse_csv('a,b\n'+'x'*(lab.MAX_CSV_BYTES+1))
        self.assertEqual(error.exception.status,413)
        with self.assertRaises(lab.LabError) as error:lab.parse_csv('a,b\n'+'1,2\n'*20001)
        self.assertEqual(error.exception.status,413)
        with self.assertRaises(lab.LabError):lab.parse_csv(','.join('x'+str(i) for i in range(101))+'\n'+','.join('1' for _ in range(101)))
        with patch.object(lab.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',55)):
            with self.assertRaises(lab.LabError) as error:lab.dispatch(fixture())
            self.assertEqual(error.exception.status,504)

    def test_leakage(self):
        p=fixture();headers,rows,audit=lab.load_data(p)
        headers+=['copy'];rows=[tuple(r)+(r[-1],) for r in rows]
        p['csv']=csv_text(headers,rows);p['features']+=['copy']
        self.assertTrue(lab.leakage_warnings(headers,rows,'target',['copy']))
        data=lab.prepare({**p,'ack_leakage':True})
        self.assertNotIn('copy',data['names'])
        self.assertTrue(any('bản sao của target' in w for w in data['warnings']))
        with self.assertRaises(lab.LabError):lab.prepare({**p,'features':['copy'],'ack_leakage':True})

    def test_high_cardinality_bounded(self):
        p=fixture();headers,rows,audit=lab.load_data(p)
        headers+=['category'];rows=[tuple(r)+('G'+str(i),) for i,r in enumerate(rows)]
        p['csv']=csv_text(headers,rows);p['features']+=['category']
        data=lab.prepare(p);transformed=lab.preprocessor(data,True).fit_transform(data['X'][data['train']])
        self.assertLessEqual(transformed.shape[1],4+3+32)
        self.assertTrue(any('OHE' in w for w in data['warnings']))

    def test_all_demos(self):
        for name in ['iris','wine','breast_cancer','digits','diabetes']:
            with self.subTest(name=name):
                p={'action':'benchmark','demo':name,'target':'target','task':'regression' if name=='diabetes' else 'classification'}
                headers,_,_=lab.load_data(p);p['features']=headers[:-1]
                result=lab.benchmark(p)
                self.assertEqual(len(result['models']),8 if name=='diabetes' else 7)
                print('PASS demo:',name,result['recommended'],flush=True)


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),lab.handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()

    def request(self,body,headers=None,method='POST'):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=65)
        try:
            conn.request(method,'/api/ml-compare',body,headers or {'Content-Type':'application/json'})
            response=conn.getresponse()
            return response.status,json.loads(response.read()),dict(response.getheaders())
        finally:conn.close()

    def test_http_errors_and_privacy(self):
        status,body,headers=self.request(None,method='GET')
        self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertFalse(body['raw_file_persisted'])
        for raw,status in [(b'{',400),(json.dumps({'action':'inspect','csv':'one\n1'}).encode(),400),
                           (json.dumps({**fixture(),'target':'absent'}).encode(),422)]:
            actual,body,_=self.request(raw)
            self.assertEqual(actual,status);self.assertIn('error',body);self.assertNotIn('Traceback',body['error'])
        status,_,_=self.request(None,{'Content-Type':'application/json','Content-Length':str(lab.MAX_REQUEST_BYTES+1)})
        self.assertEqual(status,413)
        status,_,_=self.request(b'x',{'Content-Type':'text/plain'})
        self.assertEqual(status,400)
        status,_,_=self.request(b'',method='PUT')
        self.assertEqual(status,405)

    def test_real_worker_training(self):
        status,result,_=self.request(json.dumps(fixture(mixed=False)).encode())
        self.assertEqual(status,200);self.assertEqual(len(result['models']),7)
        self.assertFalse(result['raw_file_persisted']);self.assertNotIn('csv',result)
        self.assertNotIn('preview',result['summary'])

    def test_deployment_http_fixtures_and_wall_clock(self):
        cases=[('small binary','classification',120,2),
               ('multiclass','classification',150,3),
               ('medium binary','classification',2000,2),
               ('regression','regression',500,2)]
        for name,task,count,classes in cases:
            with self.subTest(case=name):
                payload=fixture(task,count=count,classes=classes,mixed=False)
                started=time.perf_counter()
                status,result,headers=self.request(json.dumps(payload).encode())
                elapsed=time.perf_counter()-started
                self.assertEqual(status,200,result.get('error'))
                self.assertEqual(headers['Content-Type'],'application/json; charset=utf-8')
                self.assertEqual(result['selection_source'],'train_cv')
                self.assertFalse(result['methodology']['test_used_for_selection'])
                self.assertFalse(result['raw_file_persisted'])
                self.assertEqual(len(result['models']),7 if task=='classification' else 8)
                print(json.dumps({'http_fixture':name,'rows':count,'status':status,
                                  'wall_clock_seconds':round(elapsed,3),'benchmark_ms':round(result['duration_ms'],1),
                                  'models':len(result['models']),'skipped':result['skipped']}),flush=True)

    def test_csv_limit_and_sanitized_500_over_http(self):
        payload={'action':'inspect','csv':'a,b\n'+'x'*(lab.MAX_CSV_BYTES+1)}
        status,result,_=self.request(json.dumps(payload).encode())
        self.assertEqual(status,413)
        self.assertIn('2 MiB',result['error'])
        # Deliberate internal failure: error details must not reach the client.
        with patch.object(lab,'dispatch',side_effect=RuntimeError('PRIVATE_INTERNAL_TRACE')), self.assertLogs(lab.logger, level='ERROR') as logs:
            status,result,_=self.request(json.dumps({'action':'inspect','csv':'a,b\n1,2'}).encode())
        self.assertIn('RuntimeError: PRIVATE_INTERNAL_TRACE', '\n'.join(logs.output))
        self.assertIn('Traceback', '\n'.join(logs.output))
        self.assertEqual(status,500)
        self.assertNotIn('PRIVATE_INTERNAL_TRACE',json.dumps(result))
        self.assertNotIn('Traceback',json.dumps(result))

    def test_content_type_contract(self):
        body=json.dumps({'action':'inspect','csv':'a,b\n1,2'}).encode()
        for content_type in ('application/json','Application/JSON','APPLICATION/JSON','APPLICATION/JSON; charset=UTF-8','application/json; charset=utf-8','Application/JSON; charset=UTF-8'):
            with self.subTest(content_type=content_type):
                status,_,_=self.request(body,{'Content-Type':content_type})
                self.assertEqual(status,200)
        status,_,_=self.request(body,{'Content-Type':'application/jsonp'})
        self.assertEqual(status,400)

    def test_excel_http_and_sanitized_invalid_upload(self):
        payload=excel_fixture('regression',multiple=True)
        payload.update(sheet='Hồi quy',features=['x0','x1','x2','x3'])
        status,result,_=self.request(json.dumps(payload).encode())
        self.assertEqual(status,200,result.get('error'))
        self.assertEqual(result['summary']['audit']['selected_sheet'],'Hồi quy')
        self.assertEqual(len(result['models']),8)
        status,result,_=self.request(json.dumps({'action':'inspect','xlsx':'invalid'}).encode())
        self.assertEqual(status,422)
        self.assertNotIn('Traceback',result['error'])

    def test_deployment_source_contract(self):
        from html.parser import HTMLParser
        class References(HTMLParser):
            def __init__(self):super().__init__();self.refs=[]
            def handle_starttag(self,tag,attrs):
                for key,value in attrs:
                    if key in ('src','href') and value and not value.startswith(('#','http')):self.refs.append(value.split('#')[0])
        parser=References();parser.feed((ROOT/'ml-model-comparison.html').read_text(encoding='utf-8'))
        for ref in parser.refs:
            self.assertTrue((ROOT/ref).is_file(),ref)
            self.assertFalse(ref.startswith(('docs/','tests/','scripts/')),ref)
        config=json.loads((ROOT/'vercel.json').read_text())
        self.assertEqual(set(config),{'$schema','functions'})
        self.assertEqual(set(config['functions']),{'api/ml-compare.py'})
        self.assertEqual(config['functions']['api/ml-compare.py']['maxDuration'],60)
        js=(ROOT/'ml-model-comparison.js').read_text(encoding='utf-8')
        self.assertNotIn('http://localhost',js);self.assertNotIn('127.0.0.1',js)
        self.assertTrue(issubclass(lab.handler,lab.BaseHTTPRequestHandler))
        for name in ['api/market-data.js','data-analyzer.js','health-prediction.js','customer-return.js','vietnam-estimate-core.js','auth.js','history.js','supabase-config.js']:
            self.assertEqual((ROOT/name).read_bytes().replace(b'\r\n',b'\n'),subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT).replace(b'\r\n',b'\n'),name)


def browser_checks():
    from test_vietnam_map_online import CDP
    browser=os.environ.get('HEALTH_TEST_BROWSER',r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not Path(browser).exists():raise RuntimeError('Set HEALTH_TEST_BROWSER to Chromium/Edge.')
    output=Path(tempfile.gettempdir())/'ml-model-comparison-qa'
    output.mkdir(exist_ok=True)
    scripts=(ROOT/'tests/ml-model-comparison-browser.js').read_text(encoding='utf-8')
    class Local(lab.handler,SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/api/ml-compare':return lab.handler.do_GET(self)
            return SimpleHTTPRequestHandler.do_GET(self)
        def do_POST(self):
            if self.path!='/api/ml-compare':return self.respond(404,{'error':'Not found'})
            return lab.handler.do_POST(self)
    import functools
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Local,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    process=None
    reports=[]
    try:
        with tempfile.TemporaryDirectory(prefix='ml-comparison-browser-',ignore_cleanup_errors=True) as profile:
            process=subprocess.Popen([browser,'--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            portfile=Path(profile)/'DevToolsActivePort'
            for _ in range(150):
                if portfile.exists():break
                time.sleep(.1)
            port=int(portfile.read_text().splitlines()[0])
            target=json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')))
            cdp=CDP(target['webSocketDebuggerUrl']);cdp.s.settimeout(600);cdp.call('Page.enable')
            def js(code):
                response=cdp.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in response:raise RuntimeError(str(response['exceptionDetails']))
                return response.get('result',{}).get('value')
            for width in [320,390,768,1024,1440]:
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<=390})
                cdp.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/ml-model-comparison.html'})
                for _ in range(150):
                    if js("document.readyState==='complete'&&typeof MLComparison!=='undefined'"):break
                    time.sleep(.05)
                js('window.__mlFixtures={}')
                for name,payload in {'classification':fixture(),'regression':fixture('regression'), 'excel':excel_fixture(multiple=True),'weak':weak_fixture(),
                                     'tinyRegression':tiny_fixture(),'tinyClassification':tiny_fixture('classification'),'semicolon':linelist_fixture(),
                                     'dirty':dirty_fixture(),'gender':large_fixture(count=120),
                                     'exploratory':dict(csv='x,target\n1,a\n4,b\n2,c\n',target='target',task='classification')}.items():
                    js('window.__mlFixtures['+json.dumps(name)+']='+json.dumps(payload))
                if width==390:
                    for name,payload in {'largeClassification':large_fixture(),'largeRegression':large_fixture('regression',5100)}.items():
                        encoded=json.dumps(payload);js('window.__mlChunks=[]')
                        for offset in range(0,len(encoded),16000):js('window.__mlChunks.push('+json.dumps(encoded[offset:offset+16000])+')')
                        js('window.__mlFixtures['+json.dumps(name)+']=JSON.parse(window.__mlChunks.join(""))')
                report=js(scripts);reports.append(report);print(json.dumps(report),flush=True)
                js('scrollTo(0,0)')
                screenshot=cdp.call('Page.captureScreenshot',{'format':'png'})
                (output/f'page-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
                y=js("document.getElementById('results').getBoundingClientRect().top+scrollY")
                screenshot=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':max(0,y),'width':width,'height':1800,'scale':1}})
                (output/f'results-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
            previous=js("['modelA','modelB','detailModel'].map(id=>document.getElementById(id).value)")
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':320,'height':1000,'deviceScaleFactor':1,'mobile':True})
            time.sleep(.3)
            assert js("document.documentElement.scrollWidth<=innerWidth && document.querySelector('#comparisonChart svg').viewBox.baseVal.width<=280")
            assert js("['modelA','modelB','detailModel'].map(id=>document.getElementById(id).value)")==previous
            assert js('window.__mlTestErrors.length')==0
            print('PASS live resize: charts remain readable; model selections preserved.',flush=True)
            cdp.call('Browser.close')
            process.wait(timeout=15)
    finally:
        if process and process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            else:process.kill()
        server.shutdown();server.server_close()
    (output/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print('PASS browser: five viewports. Screenshots:',output)


if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (Backend,HTTP)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():sys.exit(1)
    if '--backend-only' not in sys.argv:browser_checks()
