"""Displays audit samples for assistant review; raw full texts stay in TEMP."""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
sys.dont_write_bytecode=True
from qmanh_audit_rules import normalize

sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser()
parser.add_argument('group', choices=['SALE_HIGH_CONFIDENCE','RENT_HIGH_CONFIDENCE','AMBIGUOUS'])
parser.add_argument('--start',type=int,default=1)
parser.add_argument('--count',type=int,default=25)
parser.add_argument('--full',action='store_true')
args=parser.parse_args()
cache=Path(tempfile.gettempdir())/'qmanhbeo-v3-source-audit-20261004'
rows=json.loads((cache/'transaction-review-full-text.json').read_text(encoding='utf-8'))
for row in rows:
    rank=row['review_group_rank']
    if row['rule_label']!=args.group or not args.start<=rank<args.start+args.count: continue
    description=' '.join(row['description'].split())
    if args.full:
        evidence=description
    else:
        evidence=description[:150]
        norm=normalize(description)
        spans=[]
        for match in re.finditer(r'\b(?:cho thue|can ban|ban gap|gia ban|gia thue|dang cho thue|can mua|can thue|chuyen nhuong)\b|/\s*thang',norm):
            lo=max(0,match.start()-55);hi=min(len(description),match.end()+70)
            if hi<=150 or any(lo<a[1] for a in spans): continue
            spans.append((lo,hi))
        for lo,hi in spans[:2]: evidence+=' [...] '+description[lo:hi]
    print(json.dumps({'rank':rank,'row':row['source_record_1based'],'id':row['listing_id'],
                      'title':row['title'],'description_evidence':evidence,
                      'full_description_chars':len(description),'price_raw':row['price_raw'],'area':row['area_raw']},ensure_ascii=False))
