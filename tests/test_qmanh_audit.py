"""Meaningful audit-rule checks; examples are test fixtures, never training rows."""
import math
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qmanh_audit_rules import classify, parse_prices, text_reference, audit_target


class AuditRules(unittest.TestCase):
    def test_required_money_formats(self):
        for text,total in [('2,7 tỷ',2.7e9),('2.7 tỷ',2.7e9),('2 tỷ 700 triệu',2.7e9),
                           ('850 triệu',850e6),('12 tỷ 500 triệu',12.5e9)]:
            with self.subTest(text=text):
                candidates=parse_prices('Bán nhà giá '+text,'',50)
                self.assertEqual(len(candidates),1)
                self.assertAlmostEqual(candidates[0]['total_equivalent_vnd'],total)

    def test_explicit_per_m2(self):
        candidates=parse_prices('Bán đất giá 65 triệu/m²','',50)
        self.assertEqual(candidates[0]['basis'],'per_m2')
        self.assertEqual(candidates[0]['total_equivalent_vnd'],3.25e9)
        self.assertEqual(audit_target(65,50,candidates)[0],'PRICE_PER_M2')
        self.assertEqual(audit_target(3250,50,candidates)[0],'TOTAL_PRICE')

    def test_unknown_area_does_not_invent_total(self):
        candidates=parse_prices('Bán đất giá 65 triệu/m²','',None)
        self.assertIsNone(text_reference(candidates)[0])

    def test_rental_income_is_not_primary_rent(self):
        label,_=classify('Bán nhà đang cho thuê, dòng tiền ổn định','')
        self.assertEqual(label,'SALE_HIGH_CONFIDENCE')
        candidates=parse_prices('Bán nhà giá 12 tỷ','Đang cho thuê 30 triệu/tháng',50)
        self.assertEqual(len(candidates),1)

    def test_dual_offer_and_wanted_are_ambiguous(self):
        for title in ('Bán hoặc cho thuê nhà','Cần mua nhà','Cần thuê căn hộ'):
            self.assertEqual(classify(title,'')[0],'AMBIGUOUS')

    def test_contradictory_amounts_do_not_pick_best_fit(self):
        candidates=parse_prices('Bán nhà giá 2,7 tỷ hoặc 3,5 tỷ','',50)
        self.assertIsNone(text_reference(candidates)[0])
        self.assertEqual(audit_target(2700,50,candidates)[0],'AMBIGUOUS')

    def test_ambiguous_thousand_separator_not_guessed(self):
        self.assertEqual(parse_prices('Bán nhà giá 2.700 tỷ','',50),[])

    def test_bare_compound_prices(self):
        for text,total in [('7 tỷ 500',7.5e9),('1ty560',1.56e9),('3tỷ450',3.45e9)]:
            self.assertAlmostEqual(text_reference(parse_prices('Giá '+text,'',50))[0],total)

    def test_loan_is_not_sale_price(self):
        self.assertEqual(parse_prices('', 'Căn hộ được vay tối đa 963tr.',82),[])

    def test_collapsed_area_price_is_not_guessed(self):
        self.assertEqual(parse_prices('Căn hộ 2PN89m23.4tỷ','',89),[])

    def test_other_area_units_are_not_total_or_m2(self):
        candidates=parse_prices('Bán vườn giá 190 triệu','Giá 190 triệu/sào',5514.6)
        self.assertIsNone(text_reference(candidates)[0])
        self.assertEqual(audit_target(190,5514.6,candidates)[0],'AMBIGUOUS')
        for suffix in ('/ha','/công','/mét ngang'):
            self.assertEqual(parse_prices('Bán đất giá 65 triệu'+suffix,'',50)[0]['basis'],'other_area_rate')

    def test_vnd_m2_and_conflicting_basis(self):
        candidates=parse_prices('Bán đất giá 30 triệu VND/m²','',40)
        self.assertEqual(audit_target(1200,40,candidates)[0],'TOTAL_PRICE')
        conflict=parse_prices('Bán đất 2 tỷ/m²','Giá 2 tỷ',52)
        self.assertIsNone(text_reference(conflict)[0])

    def test_discount_capital_and_undisclosed_range_not_prices(self):
        for title in ('Giảm 200tr','Vốn 710tr','Bán nhà giá 6 tỷ x'):
            self.assertEqual(parse_prices(title,'',50),[])
        self.assertEqual(text_reference(parse_prices('Bán nhà 4 tầng giá 2 tỷ','',50))[0],2e9)


if __name__=='__main__':
    unittest.main()
