"""Local public packaging/routes/reference checks, no deploy or network."""
import json,re
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
pages=['index.html','data-analyzer.html','health-prediction.html','vietnam-house-price.html','history.html','login.html','register.html']
class References(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ['href','src'] and value and not value.startswith(('http:','https:','#','mailto:','data:')):self.paths.append(value.split('#')[0].split('?')[0])
result={};references=0
for name in pages:
    source=(ROOT/name).read_text(encoding='utf-8');parser=References();parser.feed(source)
    assert not re.search(r'https?://(?:localhost|127\.0\.0\.1)',source),name
    for ref in parser.paths:assert (ROOT/ref.lstrip('/')).is_file(),(name,ref)
    references+=len(parser.paths);result['/' if name=='index.html' else '/'+name]='PASS'
for name in ['vietnam-estimate-core.js','vietnam-estimate-page.js','vietnam-house-history-save.js','api/market-data.js']:
    source=(ROOT/name).read_text(encoding='utf-8');assert not re.search(r'https?://(?:localhost|127\.0\.0\.1)|(?:service_role|sb_secret_)',source),name
    assert not re.search(r'fetch\([^\n]*\.parquet',source),name
    for ref in re.findall(r"(?:require|fetch)\(['\"]([^'\"]+)['\"]\)",source):
        if ref.startswith(('http:','https:')):continue
        if ref=='./data/vietnam-provinces.geojson':assert (ROOT/ref).is_file()
        elif name.startswith('api/'):assert (ROOT/'api'/ref).resolve().is_file(),ref
result={'public_paths':result,'local_references_checked':references,'production_localhost':False,'parquet_in_browser':False,'frontend_service_role':False,'api_runtime':'Vercel CommonJS handler; actual code evaluated in browser tests, no deployment'}
(ROOT/'docs/vietnam-public-path-tests.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
