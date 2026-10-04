"""Unit checks of input units, exported metadata and approved-feed boundaries.
Only test fixtures are generated here; never uploaded or used to train a model.
"""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import re
import unicodedata
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
trainer=module('house_trainer',ROOT/'scripts/train-vietnam-house-model.py')
market=module('market_update',ROOT/'scripts/update-vietnam-market.py')
from sources.batdongsan_source import BatdongsanSource,NoFeedRedirect
from verified_sale_rules import sale_intent,verified_price,total_prices
from tinix_audit_rules import normalize

class HouseTests(unittest.TestCase):
    def test_new_type_filter_excludes_six_previously_known_failures(self):
        # Compile only pure filters; never open DuckDB or run the one-pass script.
        tree=ast.parse((ROOT/'scripts/build-vietnam-public-types-once.py').read_text(encoding='utf-8'))
        definitions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['norm','classify','price']],type_ignores=[])
        scope={'re':re,'unicodedata':unicodedata,'normalize':normalize,'verified_price':verified_price}
        exec(compile(definitions,'existing-type-filters','exec'),scope)
        samples=json.loads((ROOT/'docs/verified-vietnam-house-quality-sample.json').read_text(encoding='utf-8'))
        review=json.loads((ROOT/'docs/verified-vietnam-house-quality-review.json').read_text(encoding='utf-8'))['review']
        failures=[r for r in review if r['result']=='FAIL'];self.assertEqual(len(failures),6)
        for failure in failures:
            r=samples[failure['sample_index']]
            kind=scope['classify'](r['title'],'Nhà');amount=scope['price'](r['title'],r['description'],r['structured_price_vnd'])
            self.assertTrue(kind is None or amount is None,r['title'])

    def test_verified_total_prices_and_primary_sale_intent(self):
        for text,value in [('5 tỷ',5e9),('5,2 tỷ',5.2e9),('5.2 tỷ',5.2e9),('5 tỷ 200',5.2e9),('5 tỷ 200 triệu',5.2e9),('850 triệu',850e6),('12 tỷ 500',12.5e9)]:
            self.assertEqual(total_prices('Bán nhà '+text,''),[value])
            self.assertEqual(verified_price('Bán nhà '+text,'',str(value)),value)
        for rate in ['30 triệu/m²','30 triệu/m2','1 tỷ/m²','20 triệu/tháng']:
            self.assertIsNone(verified_price('Bán nhà '+rate,'',str(30e6)))
        self.assertFalse(sale_intent('Cho thuê nhà hoặc bán'))
        self.assertFalse(sale_intent('Tìm người thuê căn hộ'))
        self.assertTrue(sale_intent('Chính chủ bán nhà'))
        self.assertEqual(verified_price('Bán nhà 5 tỷ','Đang cho thuê 20 triệu/tháng; giá bán 5 tỷ',5e9),5e9)
        self.assertIsNone(verified_price('Bán nhà 5 tỷ','Giá bán 6 tỷ',5e9))
        self.assertIsNone(verified_price('Bán nhà','',5e9))
        self.assertIsNone(verified_price('Bán nhà 5 tỷ','',5.3e9))

    def test_explicit_units_and_number_conventions(self):
        self.assertEqual(trainer.money('22,96 tỷ'),22960000000)
        self.assertEqual(trainer.money('529 triệu'),529000000)
        self.assertEqual(trainer.money('1.250 triệu'),1250000000)
        self.assertEqual(trainer.area('4.667 m²'),4667)
        self.assertEqual(trainer.area('87,5 m²'),87.5)
        for price in ['thỏa thuận','6350000000','5 nghìn','1200 USD','30 triệu/m²']:
            self.assertIsNone(trainer.money(price))
        self.assertIsNone(trainer.area('87.5 feet2'))

    def test_export_is_consistent_and_not_current_data(self):
        m=json.loads((ROOT/'vietnam-house-model.json').read_text(encoding='utf-8'))
        a=json.loads((ROOT/'data/vietnam-admin-aliases.json').read_text(encoding='utf-8'))
        summary=json.loads((ROOT/'docs/verified-vietnam-house-data-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['raw_rows'],3500744)
        self.assertEqual(summary['raw_rows']-summary['rejected_rows'],summary['verified_rows'])
        self.assertEqual(m['verified_rows'],summary['verified_rows'])
        self.assertEqual(m['model_review']['public_status'],'READY')
        self.assertEqual(summary['quality_gate']['status'],'FAIL');self.assertEqual(summary['quality_gate']['accuracy'],.97)
        self.assertEqual(m['train_rows']+m['test_rows'],0);self.assertIsNone(m['metrics'])
        stats=json.loads((ROOT/'data/vietnam-market-stats.json').read_text(encoding='utf-8'))
        index=json.loads((ROOT/'data/vietnam-location-index.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(p['sample_count'] for p in stats['stats'] if p['resolution_level']=='PROVINCE'),m['sample_count'])
        self.assertTrue(set(p['name'] for p in index['provinces']).issubset(a['current_provinces']))
        self.assertEqual(m['features'],['province','ward','sub_area','property_type','area_m2'])
        self.assertEqual(m['mode'],'VERIFIED MARKET ESTIMATE BETA')
        self.assertEqual(m['target_unit'],'VND')
        self.assertNotIn('Land',m['property_types'])
        self.assertEqual(m['data_source']['dataset'],'tinixai/vietnam-real-estates')
        self.assertEqual(m['data_source']['license'],'CC-BY-NC-4.0')
        self.assertEqual(len(set(r['stat_key'] for r in stats['stats'])),len(stats['stats']))
        for r in stats['stats']:
            self.assertEqual(r['coverage']=='INSUFFICIENT',r['sample_count']<stats['thresholds'][r['resolution_level']])
            self.assertLessEqual(r['p25_price_per_m2'],r['median_price_per_m2'])
            self.assertLessEqual(r['median_price_per_m2'],r['p75_price_per_m2'])
        self.assertEqual([t['code'] for t in index['property_types'] if t['status']=='ENABLED'],['APARTMENT','HOUSE','VILLA','LAND'])
        self.assertEqual(len(index['provinces']),34);self.assertEqual(len(index['wards']),3321)
        self.assertEqual(len({w['id'] for w in index['wards']}),3321)
        for w in index['wards']:self.assertIn(w['province'],a['current_provinces'])
        self.assertEqual(sum(t['verified_rows'] for t in index['property_types']),m['verified_rows'])
        self.assertEqual(len(stats['stats']),len({s['stat_key'] for s in stats['stats']}))
        for r in stats['regional_stats']:
            self.assertEqual(r['coverage'],'ESTIMATED');self.assertGreaterEqual(len(r['donors']),2)
            self.assertAlmostEqual(sum(d['province_weight'] for d in r['donors']),1)
            for d in r['donors']:
                self.assertEqual(d['property_type'],r['property_type']);self.assertGreaterEqual(d['sample_count'],80);self.assertLessEqual(d['distance_km'],500)
            self.assertLessEqual(r['p25_price_per_m2'],r['median_price_per_m2']);self.assertLessEqual(r['median_price_per_m2'],r['p75_price_per_m2'])
        eligible={(s['province'],s['property_type']) for s in stats['stats'] if s['resolution_level']=='PROVINCE' and s['coverage']!='INSUFFICIENT'}
        regional={(s['province'],s['property_type']) for s in stats['regional_stats']}
        self.assertEqual(len(eligible|regional),34*4)

    def record(self,i=0,**changes):
        return {'listing_id':f'TEST-ONLY-{i}','transaction_type':'sale','currency':'VND','area_unit':'m2','total_price_vnd':(i+1)*1e9,'area_m2':100,'province':'Hà Nội','area_name':'TEST ONLY AREA','property_type':'TEST ONLY TYPE','date':'2025-02-01T00:00:00Z',**changes}

    def test_market_rejects_ambiguity_and_never_mixes_rent(self):
        valid,invalid=market.normalize_validate([self.record(),self.record(),self.record(1,transaction_type='rent'),self.record(2,currency='USD'),self.record(3,area_unit='ft2'),self.record(4,total_price_vnd=float('nan')),self.record(5,area_m2=0),self.record(6,listing_id=None),self.record(7,total_price_vnd=True),self.record(8,province='Unknown'),self.record(9,date='2025-02-01'),self.record(10,date='2999-01-01T00:00:00Z'),self.record(11,area_name=None)],{'Hà Nội'})
        self.assertEqual(len(valid),1);self.assertEqual(invalid,12)

    def test_market_aggregates_only_enough_real_valid_records(self):
        valid,invalid=market.normalize_validate([self.record(i) for i in range(5)],{'Hà Nội'})
        stats=market.aggregate(valid,'TEST ONLY')
        self.assertEqual(invalid,0);self.assertEqual(len(stats),4)
        for row in stats:
            self.assertEqual(row['sample_count'],5);self.assertEqual(row['median_price_vnd'],3e9)
            self.assertEqual(row['median_price_per_m2'],3e7);self.assertEqual(row['p25'],2e9);self.assertEqual(row['p75'],4e9)
        self.assertEqual(market.aggregate(valid[:4],'TEST ONLY'),[])

    def test_no_approval_means_no_network_or_database(self):
        output=io.StringIO()
        with patch.dict(os.environ,{},clear=True),patch.object(BatdongsanSource,'load',side_effect=AssertionError('Network forbidden')),patch.object(market,'publish',side_effect=AssertionError('Write forbidden')),redirect_stdout(output):
            self.assertEqual(market.main(),0)
        self.assertEqual(output.getvalue().strip(),'No approved live market source configured.')
        with self.assertRaises(ValueError):NoFeedRedirect().redirect_request(None,None,None,None,None,None)

    def test_incomplete_approval_and_http_or_html_rejected(self):
        with patch.dict(os.environ,{'MARKET_SOURCE_APPROVED':'true'},clear=True):self.assertFalse(BatdongsanSource().configured())
        approved={'MARKET_SOURCE_APPROVED':'true','MARKET_SOURCE_APPROVAL_REFERENCE':'TEST ONLY','MARKET_SOURCE_NAME':'TEST ONLY','APPROVED_MARKET_FEED_URL':'http://test.example/feed'}
        for url in ['http://test.example/feed','https://test.example/listings.html','https://name:password@test.example/feed']:
            with patch.dict(os.environ,{**approved,'APPROVED_MARKET_FEED_URL':url},clear=True),self.assertRaises(ValueError):BatdongsanSource().load()

if __name__=='__main__':unittest.main()
