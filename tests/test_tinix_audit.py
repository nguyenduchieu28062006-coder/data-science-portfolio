"""Guard cases for transaction intent and text-price audit; no training."""
import sys
from pathlib import Path
import unittest
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.audit-deps'))
sys.path.insert(0,str(Path(tempfile.gettempdir())/'tinix-transaction-audit'/'deps'))
sys.path.insert(0,str(ROOT/'scripts'))
import duckdb
from tinix_audit_rules import classifier_sql, parse_text_prices


class AuditRulesTests(unittest.TestCase):
    def classify(self,title,description):
        con=duckdb.connect()
        con.execute('CREATE TABLE raw(name VARCHAR,description VARCHAR)')
        con.execute('INSERT INTO raw VALUES(?,?)',[title,description])
        result=con.execute(classifier_sql()).fetchone()[-2]
        con.close()
        return result

    def test_sale_with_rental_income(self):
        self.assertEqual(self.classify('Bán nhà quận trung tâm','Nhà đang cho thuê 20 triệu/tháng. Giá bán 5 tỷ.'),'SALE_HIGH_CONFIDENCE')
        self.assertEqual(self.classify('Bán nhà đang cho thuê 20 triệu/tháng','Giá bán 5 tỷ.'),'SALE_HIGH_CONFIDENCE')

    def test_conflicting_primary_offers(self):
        self.assertEqual(self.classify('Bán nhà hoặc cho thuê','Liên hệ để xem nhà.'),'AMBIGUOUS')
        self.assertEqual(self.classify('Bán nhà đẹp','Cho thuê nhà nguyên căn.'),'AMBIGUOUS')
        self.assertEqual(self.classify('Cho thuê căn hộ','Bán căn hộ 5 tỷ.'),'AMBIGUOUS')

    def test_rent_and_non_sale_mentions(self):
        self.assertEqual(self.classify('Cho thuê căn hộ ban công rộng','Nhà đẹp.'),'RENT_HIGH_CONFIDENCE')
        self.assertEqual(self.classify('Căn hộ ban công rộng','Có thể dùng để cho thuê.'),'AMBIGUOUS')
        self.assertEqual(self.classify('Cần thuê nhà','Tìm thuê nhà dài hạn.'),'AMBIGUOUS')
        self.assertEqual(self.classify('Chính chủ bán đất','Đất có sổ.'),'SALE_HIGH_CONFIDENCE')

    def test_text_decimal_composite_unit_price(self):
        for text,expected in [('5 tỷ',5e9),('5.2 tỷ',5.2e9),('5,2 tỷ',5.2e9),('850 triệu',850e6),('5 tỷ 200 triệu',5.2e9),('5ty250',5.25e9),('65 triệu/m2',6.5e9)]:
            with self.subTest(text=text):
                parsed=parse_text_prices('Bán nhà '+text,'',100)
                self.assertTrue(parsed)
                self.assertEqual(parsed[0]['total_equivalent_vnd'],expected)

    def test_rent_deposit_not_sale_price(self):
        self.assertEqual(parse_text_prices('Bán nhà','Đang cho thuê 20 triệu/tháng.',100),[])
        self.assertEqual(parse_text_prices('Bán nhà','Chỉ cần 400 triệu trả trước.',100),[])
        parsed=parse_text_prices('Bán nhà','Đang cho thuê 20 triệu/tháng. Giá bán 5 tỷ.',100)
        self.assertEqual([p['total_equivalent_vnd'] for p in parsed],[5e9])

    @unittest.expectedFailure
    def test_known_unhandled_rental_income_title(self):
        # Frozen v1 missed CCMN and labels the monthly income as rental intent.
        self.assertEqual(self.classify('Bán CCMN Trường Chinh 50m2 90tr/tháng',
            'Nhà mới đẹp. Doanh thu 90tr/tháng. Sổ đỏ chính chủ.'),'SALE_HIGH_CONFIDENCE')

    @unittest.expectedFailure
    def test_known_three_digit_decimal_comma(self):
        # Real validation example; v1 incorrectly treats 1,363 as 1363 billion.
        parsed=parse_text_prices('Chính chủ bán căn OT 38m2 1,363 tỷ','',38)
        self.assertAlmostEqual(parsed[0]['total_equivalent_vnd'],1.363e9)


if __name__=='__main__':
    unittest.main()
