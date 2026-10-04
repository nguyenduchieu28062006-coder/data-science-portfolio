"""Approved adapter -> normalize -> validate -> aggregate -> atomic Supabase RPC.

Raw listings are never inserted into Supabase. No model retraining in this job.
"""
from collections import defaultdict
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import statistics
import sys
from urllib.parse import urlparse
from urllib.request import Request,urlopen
sys.dont_write_bytecode=True
from sources.batdongsan_source import BatdongsanSource
ROOT=Path(__file__).resolve().parents[1]

def normalize_validate(rows,provinces):
    valid=[];invalid=0;seen=set();now=datetime.now(timezone.utc)
    for row in rows:
        try:
            if not isinstance(row,dict) or row.get('transaction_type')!='sale' or row.get('currency')!='VND' or row.get('area_unit')!='m2':raise ValueError()
            if not isinstance(row['listing_id'],(str,int)) or isinstance(row['listing_id'],bool):raise ValueError()
            if isinstance(row['total_price_vnd'],bool) or isinstance(row['area_m2'],bool):raise ValueError()
            key=str(row['listing_id']).strip();price=float(row['total_price_vnd']);area=float(row['area_m2'])
            if not key or key in seen or not math.isfinite(price) or not math.isfinite(area) or price<=0 or area<=0 or not math.isfinite(price/area):raise ValueError()
            if not all(isinstance(row.get(k),str) for k in ['province','area_name','property_type']):raise ValueError()
            province=row['province'].strip();area_name=row['area_name'].strip();kind=row['property_type'].strip()
            if province not in provinces or not area_name or not kind or max(len(area_name),len(kind))>100:raise ValueError()
            posted=datetime.fromisoformat(str(row['date']).replace('Z','+00:00'))
            if posted.tzinfo is None or posted>now:raise ValueError()
            seen.add(key);valid.append({'province':province,'area_name':area_name,'property_type':kind,'price':price,'area':area,'date':posted})
        except (KeyError,ValueError,TypeError,OverflowError):invalid+=1
    return valid,invalid

def quantile(values,q):
    ordered=sorted(values);position=(len(ordered)-1)*q;low=int(position);high=min(low+1,len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(position-low)
def aggregate(rows,source):
    groups=defaultdict(list)
    for r in rows:
        for key in {(r['province'],r['area_name'],r['property_type']),(r['province'],r['area_name'],''),(r['province'],'',r['property_type']),(r['province'],'','')}:
            groups[key].append(r)
    stats=[]
    for (province,area_name,kind),group in groups.items():
        if len(group)<5:continue
        prices=[r['price'] for r in group];n=len(group)
        units=[r['price']/r['area'] for r in group]
        stats.append({'province':province,'area_name':area_name,'property_type':kind,'sample_count':n,
                      'median_price_vnd':statistics.median(prices),'median_price_per_m2':statistics.median([r['price']/r['area'] for r in group]),
                      'p25_price_per_m2':quantile(units,.25),'p75_price_per_m2':quantile(units,.75),
                      'p25':quantile(prices,.25),'p75':quantile(prices,.75),'latest_date':max(r['date'] for r in group).isoformat(),
                      'coverage':'HIGH' if n>=1000 else 'MEDIUM' if n>=200 else 'LOW' if n>=30 else 'INSUFFICIENT'})
    return stats
def publish(stats,source,valid,invalid):
    base=os.environ.get('SUPABASE_URL','');secret=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
    parsed=urlparse(base)
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or not secret:raise RuntimeError('Supabase server credentials are not configured.')
    payload=json.dumps({'stats':stats,'run_source':source,'valid_count':valid,'invalid_count':invalid},allow_nan=False).encode()
    req=Request(base.rstrip('/')+'/rest/v1/rpc/replace_approved_market_stats',data=payload,method='POST',headers={'apikey':secret,'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
    with urlopen(req,timeout=30) as response:response.read(1024)
def main():
    adapter=BatdongsanSource()
    if not adapter.configured():print('No approved live market source configured.');return 0
    try:
        provinces=json.loads((ROOT/'data/vietnam-admin-aliases.json').read_text(encoding='utf-8'))['current_provinces']
        valid,invalid=normalize_validate(adapter.load(),set(provinces));source=os.environ['MARKET_SOURCE_NAME']
        stats=aggregate(valid,source)
        if not stats:print('No sufficient validated market data; existing statistics were not changed.');return 0
        public_rows=[{**r,'area':r['area_name'],'latest_listing_date':r['latest_date'],'source':source,'data_mode':'approved_feed'} for r in stats if r['sample_count']>=30]
        if not public_rows:print('No sufficient validated market data; existing statistics were not changed.');return 0
        # A future district-level feed must not overwrite the verified schema2
        # location statistics used by the estimator. Integration needs its own
        # canonical mapping and quality review before public connection.
        output=ROOT/'data/vietnam-approved-feed-stats.json';temporary=output.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'schema_version':1,'source':source,'live_connected':True,'stats':public_rows},ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
        temporary.replace(output)
        if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_ROLE_KEY'):publish(stats,source,len(valid),invalid)
        print(json.dumps({'status':'success','valid_rows':len(valid),'invalid_rows':invalid,'stats_rows':len(public_rows)}));return 0
    except Exception:
        # Never print feed tokens, endpoint URLs or upstream raw error bodies.
        print('Market sync failed. Check approved feed/schema and server configuration.');return 1
if __name__=='__main__':raise SystemExit(main())
