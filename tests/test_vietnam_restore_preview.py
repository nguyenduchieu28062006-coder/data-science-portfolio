"""Read-only Preview checks; protection bypass stays in memory and same-origin."""
import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from test_sales_forecasting import preview_headers
from test_vietnam_commune_map import browser

ROOT=Path(__file__).resolve().parents[1]

def main(base):
    task_temp=Path(tempfile.gettempdir())/'ml-compare-deployment-tools'
    os.environ['SALES_QA_NODE']=str(task_temp/'node-v22.23.3-win-x64/node.exe')
    os.environ['SALES_QA_VERCEL_CLI']=str(task_temp/'npm-cache/_npx/67eb4586ca667318/node_modules/vercel/dist/vc.js')
    headers=preview_headers(base)
    files=['vietnam-house-price.html','vietnam-house-price.css','vietnam-estimate-core.js','vietnam-estimate-page.js',
           'vietnam-commune-map.js','vietnam-house-history-save.js','vietnam-house-model.json',
           'auth.js','history.js','history.html','data/vietnam-location-index.json','data/vietnam-market-stats.json']
    for name in files:
        with urllib.request.urlopen(urllib.request.Request(base+'/'+name,headers=headers),timeout=40) as r:data=r.read()
        assert hashlib.sha256(data).digest()==hashlib.sha256((ROOT/name).read_bytes()).digest(),'Preview file mismatch: '+name
    print('PREVIEW ASSET PARITY PASS: original V1 estimate/data/Auth/History and integrated V2 map',flush=True)
    stats=json.loads((ROOT/'data/vietnam-market-stats.json').read_text(encoding='utf-8'))
    row=next(r for r in stats['stats'] if r['stat_key']=='Hà Nội|||APARTMENT')
    query=urllib.parse.urlencode({'province':'Hà Nội','ward':'vn_00466','property_type':'APARTMENT','area_m2':'80'})
    with urllib.request.urlopen(urllib.request.Request(base+'/api/market-data?'+query,headers=headers),timeout=40) as r:result=json.load(r)
    assert result['available'] and result['estimated_price_vnd']==row['median_price_per_m2']*80
    assert not result['live_connected'] and result['selected_location']['ward']=='Xã Phúc Thịnh'
    print('PREVIEW V1 API PASS: original price and selected location, no comparables/upload',flush=True)
    browser(base,headers)
    print('PREVIEW TEST PASS',flush=True)

if __name__=='__main__':main(sys.argv[1].rstrip('/'))
