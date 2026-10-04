"""Real wall-clock Edge/OSM test, no virtual-time or synthetic tiles."""
import base64,functools,hashlib,json,os,socket,struct,subprocess,tempfile,threading,time,urllib.request,sys
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1]
class CDP:
    def __init__(self,url):
        from urllib.parse import urlparse
        u=urlparse(url);self.s=socket.create_connection((u.hostname,u.port),5);self.s.settimeout(5)
        key=base64.b64encode(os.urandom(16)).decode();self.s.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        header=b''
        while not header.endswith(b'\r\n\r\n'):header+=self.s.recv(1)
        assert b'101' in header.split(b'\r\n')[0];self.i=0;self.events=[]
    def read(self,n):
        out=b''
        while len(out)<n:
            chunk=self.s.recv(n-len(out))
            if not chunk:raise RuntimeError('CDP closed')
            out+=chunk
        return out
    def recv(self):
        a,b=self.read(2);n=b&127
        if n==126:n=struct.unpack('!H',self.read(2))[0]
        elif n==127:n=struct.unpack('!Q',self.read(8))[0]
        mask=self.read(4) if b&128 else None;raw=self.read(n)
        if mask:raw=bytes(v^mask[i%4] for i,v in enumerate(raw))
        return json.loads(raw)
    def call(self,method,params=None):
        self.i+=1;raw=json.dumps({'id':self.i,'method':method,'params':params or {}}).encode();mask=os.urandom(4);n=len(raw)
        head=bytes([129,128|n]) if n<126 else bytes([129,128|126])+struct.pack('!H',n)
        self.s.sendall(head+mask+bytes(v^mask[i%4] for i,v in enumerate(raw)))
        while True:
            message=self.recv()
            if message.get('id')==self.i:return message.get('result',{})
            self.events.append(message)
    def evaluate(self,expression):return self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True}).get('result',{}).get('value')
def main():
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/supabase-config.js':
                content=b'window.PORTFOLIO_SUPABASE_CONFIG={url:"YOUR_SUPABASE_URL",key:"YOUR_SUPABASE_ANON_KEY"};'
                self.send_response(200);self.send_header('Content-Type','text/javascript');self.end_headers();self.wfile.write(content)
            else:super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start()
    edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    with tempfile.TemporaryDirectory(prefix='vietnam-map-online-',ignore_cleanup_errors=True) as profile:
        page=f'http://127.0.0.1:{server.server_port}/vietnam-house-price.html'
        process=subprocess.Popen([str(edge),'--headless=new','--disable-gpu','--disable-extensions','--disable-background-networking','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',f'--user-data-dir={profile}','--window-size=1440,1000',page],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            portfile=Path(profile)/'DevToolsActivePort';deadline=time.monotonic()+15
            while not portfile.exists() and time.monotonic()<deadline:time.sleep(.2)
            port=portfile.read_text().splitlines()[0]
            target=json.load(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/json/new?{page}',method='PUT')));cdp=CDP(target['webSocketDebuggerUrl'])
            cdp.call('Network.enable');cdp.call('Page.enable')
            deadline=time.monotonic()+35;state=None
            while time.monotonic()<deadline:
                state=cdp.evaluate('window.HousePage ? ({tiles:HousePage.getTileStatus(),geometry:HousePage.getProvinceLayers().size,model:!!HousePage.getModel()}) : null')
                if state and state['tiles']['loaded']>0:break
                if '--geometry-only' in sys.argv and state and state['geometry']==34:break
                time.sleep(.4)
            responses=[e['params']['response'] for e in cdp.events if e.get('method')=='Network.responseReceived' and 'tile.openstreetmap.org/' in e['params']['response']['url']]
            failures=[e['params'].get('errorText') for e in cdp.events if e.get('method')=='Network.loadingFailed']
            report={'state':state,'osm_responses':[{'url':r['url'],'status':r['status'],'mime':r['mimeType']} for r in responses[:5]],'network_failures':failures[:10],
                'online_pass':bool(state and state['tiles']['loaded']>0 and state['geometry']==34),'synthetic_tiles':False,
                'page':cdp.evaluate('({url:location.href,state:document.readyState,title:document.title,status:document.getElementById("houseStatus")?.textContent})')}
            evidence='vietnam-map-geometry-test.json' if '--geometry-only' in sys.argv else 'vietnam-map-online-test.json'
            print(json.dumps(report));(ROOT/'docs'/evidence).write_text(json.dumps(report,indent=2),encoding='utf-8')
            if state:
                cdp.evaluate('document.getElementById("houseMap").scrollIntoView({block:"center",behavior:"instant"})')
                time.sleep(.3)
                image=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data'];(ROOT/'docs/vietnam-public-browser.png').write_bytes(base64.b64decode(image))
            cdp.s.close()
            if '--geometry-only' not in sys.argv:assert report['online_pass'],'Real OSM tiles did not load; see recorded network failures'
        finally:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=10);server.shutdown();server.server_close()
if __name__=='__main__':main()
