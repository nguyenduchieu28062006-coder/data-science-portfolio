"""Fetch administrative reference and province geometry once; no market data."""
import sys,json,re,gzip,hashlib,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.local-deps'));sys.dont_write_bytecode=True
from shapely.geometry import shape,mapping
BASE='https://danhmuchanhchinh.nso.gov.vn/DMDVHC.asmx'
CACHE=ROOT/'docs/admin-source';CACHE.mkdir(exist_ok=True)
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Portfolio-reference-builder/1.0'})
    data=urllib.request.urlopen(request,timeout=45).read()
    return gzip.decompress(data) if data[:2]==b'\x1f\x8b' else data
def soap(op):
    target=CACHE/(op+'.xml')
    if not target.exists():
        fields={'DenNgay':'04/10/2026'}
        if op=='DanhMucPhuongXa':fields.update(Tinh='',TenTinh='',QuanHuyen='',TenQuanHuyen='')
        xml='<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><'+op+' xmlns="http://tempuri.org/">'+''.join('<'+k+'>'+v+'</'+k+'>' for k,v in fields.items())+'</'+op+'></soap:Body></soap:Envelope>'
        request=urllib.request.Request(BASE,data=xml.encode(),headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':'http://tempuri.org/'+op})
        target.write_bytes(urllib.request.urlopen(request,timeout=45).read())
    tree=ET.fromstring(target.read_bytes());rows=[]
    for el in tree.iter():
        children=list(el)
        if len(children)>1 and all(not list(c) for c in children):rows.append({c.tag.split('}')[-1]:c.text for c in children})
    return rows
def main():
    for op in ['DanhMucTinh','DanhMucPhuongXa']:
        rows=soap(op);print(op,len(rows),json.dumps(rows[:2],ensure_ascii=True),flush=True)
        (CACHE/(op+'.json')).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
    geometry=ROOT/'data/vietnam-provinces.geojson'
    if geometry.exists():print('Reuse existing province geometry');return
    repo='https://api.github.com/repos/thanglequoc/vietnamese-provinces-database'
    commit=json.loads(fetch(repo+'/commits/master'))['sha']
    directories=[r['name'] for r in json.loads(fetch(repo+'/contents/json/geojson?ref='+commit)) if r['type']=='dir']
    def get_geo(directory):
        url='https://raw.githubusercontent.com/thanglequoc/vietnamese-provinces-database/'+commit+'/json/geojson/'+directory+'/'+directory+'.geojson'
        target=CACHE/(directory+'.geojson')
        if not target.exists():target.write_bytes(fetch(url))
        data=json.loads(target.read_text(encoding='utf-8'));feature=data['features'][0]
        geom=shape(feature['geometry']).simplify(.008,preserve_topology=True)
        return {'type':'Feature','id':feature['id'],'properties':{'province_code':str(feature['id']),'source_url':url},'geometry':mapping(geom)}
    with ThreadPoolExecutor(max_workers=4) as pool:features=list(pool.map(get_geo,directories))
    assert len(features)==34 and len({f['id'] for f in features})==34
    geometry.write_text(json.dumps({'type':'FeatureCollection','features':features},separators=(',',':')),encoding='utf-8')
    (ROOT/'data/vietnam-map-source.json').write_text(json.dumps({'source':'Vietnamese Provinces Database / Vietnam Administrative Units Reference Map','source_url':'https://github.com/thanglequoc/vietnamese-provinces-database/blob/'+commit+'/docs/gis/README.md','revision':commit,'retrieved_at':datetime.now(timezone.utc).isoformat(),'license':'MIT (repository), original geometry source attributed in upstream README','simplification_degrees':.008,'coordinate_system':'WGS84','purpose':'Illustrative province selection; not legal/survey boundary','features':34,'bytes':geometry.stat().st_size},ensure_ascii=False,indent=2),encoding='utf-8')
    license_path=ROOT/'assets/vendor/vietnam-boundaries-LICENSE'
    if not license_path.exists():license_path.write_bytes(fetch('https://raw.githubusercontent.com/thanglequoc/vietnamese-provinces-database/'+commit+'/LICENSE'))
    print('Province geometry',len(features),geometry.stat().st_size,flush=True)
if __name__=='__main__':main()
