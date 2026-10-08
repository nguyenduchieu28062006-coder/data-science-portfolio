"""V1 restore audit and original V1 UI/history suite with V2 map assertions.

Only obsolete province-only map assertions are replaced. All original estimate,
search, scenario, history, API and 250 parity fixture checks run unchanged.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKUP=Path(tempfile.gettempdir())/'realestate-v1-restore-backup'

def original(name):return subprocess.check_output(['git','show','7df25a7:'+name],cwd=ROOT)

def scope_checks():
    exact=['vietnam-estimate-core.js','api/market-data.js','vercel.json','vietnam-house-model.json',
           'data/vietnam-market-stats.json','data/vietnam-location-index.json','vietnam-house-history-save.js','auth.js','history.js']
    for name in exact:
        assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n')==original(name).replace(b'\r\n',b'\n'),name+' differs from V1 Git source'
    page=(ROOT/'vietnam-estimate-page.js').read_text(encoding='utf-8')
    before=original('vietnam-estimate-page.js').decode('utf-8')
    assert page[:page.index('    function mapContext()')].replace('map,mapController,','map,')==before[:before.index('    function syncMap()')],'V1 estimation/result/search/what-if/explorer changed'
    assert page[page.index('    async function load()'):page.index('    window.HousePage=')]==before[before.index('    async function load()'):before.index('    window.HousePage=')],'V1 loading/inputs/search/history events changed'
    html=(ROOT/'vietnam-house-price.html').read_text(encoding='utf-8')
    before_html=original('vietnam-house-price.html').decode('utf-8')
    assert html[:html.index('  <section class="house-panel house-map-panel house-map-card"')].replace('    <script src="vietnam-commune-map.js" defer></script>\n','')==before_html[:before_html.index('        <section class="house-panel house-map-panel"')],'V1 form/result/exploration rebuilt'
    assert html[html.index('        <section class="house-panel"><h2>Phạm vi dữ liệu'):]==before_html[before_html.index('        <section class="house-panel"><h2>Phạm vi dữ liệu'):],'V1 explorer/source/remaining content changed'
    assert (ROOT/'vietnam-house-price.css').read_text(encoding='utf-8').startswith(original('vietnam-house-price.css').decode('utf-8'))
    allowed={'vietnam-estimate-core.js','api/market-data.js','vercel.json','docs/vietnam-public-path-tests.json','vietnam-estimate-page.js','vietnam-house-price.html','vietnam-house-price.css'}
    if (BACKUP/'baseline.json').exists():
        baseline=json.loads((BACKUP/'baseline.json').read_text())
        for name,digest in baseline.items():
            if name not in allowed:assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'Other module changed: '+name
    assert 'weighted_median' not in (ROOT/'vietnam-estimate-core.js').read_text(encoding='utf-8')
    for name in ['api/realestate-import.py','vietnam-realestate-source.js','vietnam-realestate-methodology.html']:
        assert not (ROOT/name).exists(),'Inactive V2 runtime retained: '+name
    print('RESTORE SCOPE PASS: exact Git V1 core/API/data/Auth/History; unchanged V1 form/results/search/scenario/explorer; other modules unchanged',flush=True)

MAP_CHECKS=r"""
  const map=win.HousePage.getMap(),layers=win.HousePage.getProvinceLayers();
  const ms=()=>win.HousePage.getMapState(),cm=code=>win.HousePage.getCommuneLayers().find(x=>x.code===code)?.layer;
  async function readyMap(){for(let i=0;i<250&&ms().load==='LOADING';i++)await tick();assert(ms().load==='READY','verified commune geometry loads');}
  assert(map&&layers.size===34,'V2 visual Leaflet map keeps all 34 real province geometries');
  layers.get('Hà Nội').fire('click');await readyMap();
  assert(doc.getElementById('houseProvince').value==='Hà Nội'&&!doc.getElementById('houseWard').value&&ms().polygon_count===126,'V1 province ID → Hanoi 126 polygons');
  assert(doc.querySelector('#houseMap canvas')&&cm('00466')&&cm('00475'),'Actual V2 polygon canvas and both Hanoi communes preserved');
  cm('00466').fire('mouseover',{latlng:cm('00466').getBounds().getCenter()});
  assert(cm('00466').options.fillOpacity===.35&&cm('00466').getTooltip().getContent().textContent.includes('Phúc Thịnh'),'V2 hover color/commune tooltip');cm('00466').fire('mouseout');
  cm('00466').fire('click');
  assert(doc.getElementById('houseWard').value==='vn_00466'&&doc.getElementById('houseWardSearch').value==='Xã Phúc Thịnh','V2 commune code → exact V1 ward ID');
  doc.getElementById('houseForm').elements.area_m2.value=80;predict();
  const mapped=api.predict(model,{province:'Hà Nội',ward:'vn_00466',sub_area:'',property_type:doc.getElementById('housePropertyType').value,area_m2:80});
  assert(!doc.getElementById('houseResult').hidden&&doc.getElementById('housePrice').textContent===api.formatPrice(mapped.total_price_vnd),'Polygon-selected commune uses unchanged V1 price formula without user comparables');
  doc.getElementById('houseWard').value='vn_00475';event(doc.getElementById('houseWard'),'change');
  assert(ms().selected.commune_code==='00475'&&cm('00475').options.fillOpacity===.5&&map.getBounds().contains(cm('00475').getBounds()),'V1 form → V2 Thu Lam zoom/highlight');
  assert(doc.getElementById('houseResult').hidden,'V1 clears obsolete result on location change');
  doc.getElementById('mapBack').click();
  assert(ms().view==='NATIONAL'&&ms().polygon_count===0&&map.getZoom()===5&&doc.getElementById('houseWard').value==='vn_00475','V2 return to Vietnam retains V1 selection');
  const [province,layer]=[...layers][1];layer.fire('click');await readyMap();
  assert(doc.getElementById('houseProvince').value===province&&!doc.getElementById('houseWard').value,'Switch province resets V1 commune and V2 polygons');
  fill();await readyMap();
  assert(map.getBounds().intersects(layers.get(base.province).getBounds()),'V1 province selection focuses correct V2 geometry');
  const tiles=win.HousePage.getTileLayer();assert(tiles._url.includes('tile.openstreetmap.org/'),'V2 detailed OSM base map configured');
  const onlineBefore=win.HousePage.getTileStatus().loaded;
  tiles.fire('tileerror',{error:Error('simulated OSM outage')});
  assert(doc.getElementById('houseMapStatus').textContent.includes('chưa tải được')&&layers.size===34,'Tile failure retains sourced boundaries and V1 form');
  fill({ward:city[0].ward});checkEstimate();assert(!doc.getElementById('houseEstimate').disabled,'V1 estimate usable during tile outage');
  assert(!doc.getElementById('manualForm')&&!doc.getElementById('comparableFile'),'No V2 sale price/comparable/CSV requirement');
"""

def browser_checks():
    import test_vietnam_house_browser as v1
    # Legacy hard-coded hashes predate committed module changes. Verify HEAD
    # content first and update only the in-memory expectations, never the files.
    for name in v1.harness.PROTECTED:
        current=(ROOT/name).read_bytes()
        assert current.replace(b'\r\n',b'\n').rstrip(b'\n')==original(name).replace(b'\r\n',b'\n').rstrip(b'\n'),name+' changed'
        v1.harness.PROTECTED[name]=hashlib.sha256(current).hexdigest()
    runner=v1.harness.RUNNER
    start=runner.index('  const map=win.HousePage.getMap(),layers=')
    end=runner.index('  // Keyboard canonical search',start)
    v1.harness.RUNNER=runner[:start]+MAP_CHECKS+runner[end:]
    v1.harness.main()

if __name__=='__main__':
    scope_checks()
    if '--browser' in sys.argv:browser_checks()
