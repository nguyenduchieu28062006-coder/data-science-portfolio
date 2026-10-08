"""Acquire licensed post-reform boundaries, validate codes, keep geometry unchanged.

Run explicitly to refresh the pinned local snapshot; never runs in the browser/build.
No merging, centroid replacement, or reconstruction from pre-2025 communes.
"""
import concurrent.futures
import hashlib
import json
import math
import os
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(tempfile.gettempdir()) / 'vietnam-commune-map-qa'
SOURCE = 'https://www.tinhthanhpho.com/data/wards-{}.geojson'
REVISION = '8b78ba5118715e1fa81769286724db79346abf52'
ADMIN = json.loads((ROOT/'data/vietnam-administrative-v2.json').read_text(encoding='utf-8'))

def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())

def rings(geometry):
    if geometry['type'] == 'Polygon':
        return geometry['coordinates']
    if geometry['type'] == 'MultiPolygon':
        return [ring for polygon in geometry['coordinates'] for ring in polygon]
    raise ValueError('Only real Polygon/MultiPolygon accepted')

def validate_geometry(geometry):
    for ring in rings(geometry):
        assert len(ring) >= 4 and ring[0] == ring[-1], 'Unclosed/empty polygon'
        assert all(len(p) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)
                   and 100 <= p[0] <= 120 and 7 <= p[1] <= 25 for p in ring), 'Invalid WGS84'
        assert abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))) > 1e-12, 'Zero area'

def load_province(province):
    code = province['province_code']
    path = CACHE/f'tinhthanhpho-wards-{code}.geojson'
    if not path.exists():
        response = requests.get(SOURCE.format(code), timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    raw = path.read_bytes()
    data = json.loads(raw)
    meta = data['metadata']
    assert meta['license'] == 'CC BY 4.0' and meta['publisher'] == 'tinhthanhpho.com'
    assert meta['dataset'] == f'wards-{code}' and meta['data_version'] == '2026.10.8'
    expected = {w['commune_code']:w for w in ADMIN['communes'] if w['province_code'] == code}
    features = []
    seen = set()
    for f in data['features']:
        key = f['properties']['code']
        assert f['id'] == key and key in expected and key not in seen, (code,key,'code mismatch')
        assert normalized(f['properties']['name']) == normalized(expected[key]['commune_name']), (code,key,'name mismatch')
        validate_geometry(f['geometry'])
        seen.add(key)
        features.append({'type':'Feature','id':key,'properties':{
            'province_code':code,'commune_code':key,'commune_name':expected[key]['commune_name']
        },'geometry':f['geometry']})
    assert seen == set(expected), (code,'missing communes')
    result = {'type':'FeatureCollection','province_code':code,'administrative_version':ADMIN['administrative_version'],
              'source_version':meta['data_version'],'features':features}
    encoded = (json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    return code, encoded, {'url':f'data/vietnam-communes/{code}.geojson','count':len(features),
        'bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),
        'source_url':SOURCE.format(code),'original_sha256':hashlib.sha256(raw).hexdigest()}

def distance(point, a, b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
    return math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy)

def verify_hanoi():
    data=json.loads((CACHE/'tinhthanhpho-wards-01.geojson').read_bytes())
    results=[]
    for code,slug in [('00466','phuc_thinh'),('00475','thu_lam')]:
        url=f'https://raw.githubusercontent.com/thanglequoc/vietnamese-provinces-database/{REVISION}/json/geojson/01_ha_noi/wards/{code}_{slug}.geojson'
        path=CACHE/f'upstream-{slug.replace("_","-")}.geojson'
        if not path.exists():
            response=requests.get(url,timeout=60);response.raise_for_status();path.write_bytes(response.content)
        original=json.loads(path.read_bytes())['features'][0]
        reference=next(f for f in data['features'] if f['id']==code)
        assert original['properties']['gisServerId'].startswith('diaphanhanhchinhcapxa_2025.')
        assert original['properties']['fullName']==reference['properties']['name']
        a,b=rings(original['geometry']),rings(reference['geometry'])
        assert len(a)==len(b), 'Polygon islands/holes changed'
        # Bidirectional vertex-to-segment distance permits publisher simplification;
        # it does not create or infer any geometry.
        deviation=max(max(min(distance(p,x,y) for r in dest for x,y in zip(r,r[1:])) for r in src for p in r)
                      for src,dest in [(a,b),(b,a)])
        assert deviation < .0002, (code,'geometry differs from 2025 reference',deviation)
        results.append({'commune_code':code,'commune_name':reference['properties']['name'],
                        'gis_server_id':original['properties']['gisServerId'],'reference_url':url,
                        'reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'maximum_vertex_to_boundary_deviation_degrees':deviation,
                        'reference_area_km2':original['properties']['areaKm2']})
    return results

def main():
    CACHE.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(load_province,ADMIN['provinces']))
    checks=verify_hanoi()
    assert sum(item[2]['count'] for item in results)==3321
    output=ROOT/'data/vietnam-communes';output.mkdir(exist_ok=True)
    for code,encoded,metadata in results:(output/f'{code}.geojson').write_bytes(encoded)
    manifest={'schema_version':1,'status':'VERIFIED','boundary_epoch':'post-reform-2025-07-01',
        'administrative_version':ADMIN['administrative_version'],'source_version':'2026.10.8',
        'retrieved_at':datetime.now(timezone.utc).isoformat(),'publisher':'tinhthanhpho.com',
        'license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/',
        'license_evidence_url':'https://tinhthanhpho.com/dieu-khoan',
        'source_documentation_url':'https://tinhthanhpho.com/api-docs',
        'original_geometry_source':'NXB Tài nguyên Môi trường và Bản đồ Việt Nam / sapnhap.bando.com.vn',
        'original_geometry_via':'thanglequoc/vietnamese-provinces-database',
        'geometry_processing':'Unchanged coordinates from publisher; compact JSON and official code/name join only.',
        'verification_scope':'Published post-2025 reference boundaries for navigation, not cadastral/legal survey certification.',
        'commune_count':3321,'province_count':34,'hanoi_checks':checks,
        'provinces':{code:metadata for code,encoded,metadata in results}}
    (ROOT/'data/vietnam-commune-map-source.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'VERIFIED','count':3321,'bytes':sum(item[2]['bytes'] for item in results),
                      'maximum_province_bytes':max(item[2]['bytes'] for item in results),'hanoi':checks},ensure_ascii=True),flush=True)

if __name__=='__main__':main()
