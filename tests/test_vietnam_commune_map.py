"""Validate real post-2025 assets and exercise the existing Leaflet/form integration."""
import base64
import functools
import hashlib
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=Path(tempfile.gettempdir())/'vietnam-commune-map-qa'

def assets():
    source=json.loads((ROOT/'data/vietnam-commune-map-source.json').read_text(encoding='utf-8'))
    admin=json.loads((ROOT/'data/vietnam-administrative-v2.json').read_text(encoding='utf-8'))
    assert source['status']=='VERIFIED' and source['license']=='CC BY 4.0'
    assert len(source['provinces'])==34 and source['commune_count']==3321
    seen=set()
    for code,entry in source['provinces'].items():
        data=(ROOT/entry['url']).read_bytes()
        assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
        geo=json.loads(data);expected={w['commune_code']:w for w in admin['communes'] if w['province_code']==code}
        assert geo['administrative_version']==admin['administrative_version'] and geo['province_code']==code
        assert len(geo['features'])==len(expected)==entry['count']
        for f in geo['features']:
            assert f['id'] in expected and f['id'] not in seen
            assert f['properties']['commune_name']==expected[f['id']]['commune_name']
            assert f['properties']['province_code']==code and f['geometry']['type'] in ['Polygon','MultiPolygon']
            seen.add(f['id'])
    assert len(seen)==3321
    assert {x['commune_code'] for x in source['hanoi_checks']}=={'00466','00475'}
    assert all(x['maximum_vertex_to_boundary_deviation_degrees']<.0002 for x in source['hanoi_checks'])
    print('ASSETS PASS: 34 provinces / 3321 unique codes, names, geometry, SHA-256; Hanoi 2025 reference checks',flush=True)

def protected():
    from test_vietnam_restore import scope_checks
    scope_checks()

def browser(base=None,headers=None):
    from test_vietnam_map_online import CDP
    ARTIFACTS.mkdir(exist_ok=True)
    server=None
    if not base:
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path=='/favicon.ico':
                    self.send_response(204);self.end_headers();return
                super().do_GET()
            def copyfile(self,source,outputfile):
                try:super().copyfile(source,outputfile)
                except (BrokenPipeError,ConnectionResetError):pass  # Expected aborted province request.
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
        threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
    cookies=http.cookiejar.CookieJar()
    if headers:
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        with opener.open(urllib.request.Request(base+'/vietnam-house-price.html',headers={**headers,'x-vercel-set-bypass-cookie':'true'}),timeout=40) as r:r.read()
    script=(ROOT/'tests/vietnam-commune-map-browser.js').read_text(encoding='utf-8')
    process=None;reports=[]
    try:
        with tempfile.TemporaryDirectory(prefix='commune-map-browser-',ignore_cleanup_errors=True) as profile:
            process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless=new','--disable-gpu','--disable-extensions','--disable-background-networking','--no-first-run','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            portfile=Path(profile)/'DevToolsActivePort'
            for _ in range(150):
                if portfile.exists():break
                time.sleep(.1)
            port=int(portfile.read_text().splitlines()[0]);target=json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')))
            cdp=CDP(target['webSocketDebuggerUrl']);cdp.s.settimeout(120);cdp.call('Page.enable');cdp.call('Runtime.enable');cdp.call('Network.enable');cdp.call('Log.enable')
            if cookies:cdp.call('Network.setCookies',{'cookies':[{'name':x.name,'value':x.value,'url':base,'path':x.path,'secure':True,'httpOnly':True} for x in cookies]})
            cdp.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.__mapErrors=[];addEventListener('error',e=>__mapErrors.push(e.message));addEventListener('unhandledrejection',e=>__mapErrors.push(String(e.reason)));const ce=console.error;console.error=(...a)=>{__mapErrors.push(a.map(String).join(' '));ce(...a);};"})
            def js(code):
                r=cdp.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in r:raise RuntimeError(str(r['exceptionDetails']))
                return r.get('result',{}).get('value')
            for width in [320,390,1440]:
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<400})
                cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':width<400})
                cdp.call('Page.navigate',{'url':base+'/vietnam-house-price.html'})
                event_start=len(cdp.events)
                for _ in range(250):
                    if js("document.readyState==='complete'&&!!window.HousePage"):break
                    time.sleep(.1)
                js('HousePage.ready');assert js('!!HousePage.getModel()')
                report=js(script);reports.append(report);print(json.dumps({k:v for k,v in report.items() if k!='render'}),flush=True)
                js("document.getElementById('mapTitle').scrollIntoView({block:'start',behavior:'instant'})")
                time.sleep(.2)
                shot=cdp.call('Page.captureScreenshot',{'format':'png'});(ARTIFACTS/f'map-{width}.png').write_bytes(base64.b64decode(shot['data']))
                # A real pointer/touch hit on an interior point of the downloaded polygon.
                point=js("""(()=>{const map=HousePage.getMap(),g=HousePage.getCommuneLayers().find(x=>x.code==='00466').layer;
                    const bounds=g.getBounds(),r=g.feature.geometry.coordinates[0];
                    function inside(p){let v=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])v=!v;}return v;}
                    const steps=[10,9,11,8,12,7,13,6,14,5,15,4,16,3,17,2,18,1,19];
                    for(const i of steps)for(const j of steps){const lat=bounds.getSouth()+(bounds.getNorth()-bounds.getSouth())*i/20,lng=bounds.getWest()+(bounds.getEast()-bounds.getWest())*j/20;
                    if(!inside([lng,lat]))continue;const q=map.latLngToContainerPoint([lat,lng]),b=map.getContainer().getBoundingClientRect();if(q.x>10&&q.y>10&&q.x<b.width-10&&q.y<b.height-10){window.__tapLatLng=[lat,lng];return{x:b.x+q.x,y:b.y+q.y};}}throw Error('No visible polygon point');})()""")
                js("document.getElementById('houseWard').value='vn_00475';document.getElementById('houseWard').dispatchEvent(new Event('change',{bubbles:true}));HousePage.getMap().fitBounds(HousePage.getCommuneLayers().find(x=>x.code==='00466').layer.getBounds(),{animate:false,padding:[24,24],maxZoom:13});")
                time.sleep(.2)  # Leaflet canvas redraw completes on the next frame.
                # Recompute after zoom/pan; first point above also verifies visible geometry.
                point=js("(()=>{const map=HousePage.getMap();const b=map.getContainer().getBoundingClientRect(),q=map.latLngToContainerPoint(__tapLatLng);return{x:b.x+q.x,y:b.y+q.y};})()")
                if width<400:
                    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
                    cdp.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[point]})
                    cdp.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                else:
                    cdp.call('Input.dispatchMouseEvent',{'type':'mouseMoved',**point})
                    cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**point})
                    cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**point})
                time.sleep(.4)
                assert js("document.getElementById('houseWard').value==='vn_00466'"),'Real pointer/touch did not select Phuc Thinh'
                assert js('!__mapErrors.length'),'Console errors during pointer test'
                errors=[e['params']['entry'] for e in cdp.events[event_start:] if e.get('method')=='Log.entryAdded' and e['params']['entry']['level']=='error' and not e['params']['entry'].get('url','').endswith('/favicon.ico')]
                assert not errors,'Browser console errors: '+str(errors)
                print('REAL POINTER/TAP PASS',width,flush=True)
            cdp.call('Browser.close');process.wait(timeout=15)
    finally:
        if process and process.poll() is None:process.kill()
        if server:server.shutdown();server.server_close()
    (ARTIFACTS/('map-local.json' if server else 'map-cloud.json')).write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print('MAP BROWSER PASS; screenshots/reports:',ARTIFACTS,flush=True)

if __name__=='__main__':
    assets();protected()
    if '--browser' in sys.argv:browser()
    if '--cloud' in sys.argv:
        from test_sales_forecasting import preview_headers
        os.environ['SALES_QA_NODE']=str(Path(tempfile.gettempdir())/'ml-compare-deployment-tools/node-v22.23.3-win-x64/node.exe')
        os.environ['SALES_QA_VERCEL_CLI']=str(Path(tempfile.gettempdir())/'ml-compare-deployment-tools/npm-cache/_npx/67eb4586ca667318/node_modules/vercel/dist/vc.js')
        base=sys.argv[sys.argv.index('--cloud')+1].rstrip('/')
        browser(base,preview_headers(base))
