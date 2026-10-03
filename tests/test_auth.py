"""Browser auth regression checks. Supabase is mocked in tests only.

python tests/test_auth.py — uses a temporary server and headless Edge/Chrome.
"""

import functools
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["login.html", "register.html", "forgot-password.html", "reset-password.html"]
PROTECTED = {
    "data-analyzer.html": "12b3b91bf6541deb4dc8f630fb5a4fb25a30f230482a9d1602f3bb3dcf883af5",
    "data-analyzer.js": "29e774d6f97115eba59a8e814f8aec752ab410af917cbb202ef186fee9786063",
    "health-model.json": "7740ef1389ae1bce4aafdf825d84984f50407294e999f9b2099c9b42012b2f89",
    "health-prediction.js": "6ad2ae5c27e654a74c00c45d6010548e578a80b1e8c1af0461e63c96cfd4dff4",
    "train-health-model.py": "e208263785950d35ca58acf24025b6e6c44073d933932b6eefa1f60453856263",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = set()
        self.references = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            assert attrs["id"] not in self.ids
            self.ids.add(attrs["id"])
        if attrs.get("for"):
            self.references.append(attrs["for"])
        if tag not in ("meta", "link", "input", "br", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack.pop() == tag


# Injected into test documents, never shipped in production auth.js.
MOCK = r"""
window.__authErrors = [];
addEventListener('error', e => window.__authErrors.push(e.message));
addEventListener('unhandledrejection', () => window.__authErrors.push('unhandled promise'));
const testControl = parent.__authControl;
if (testControl?.configured) {
  window.supabase = {createClient(url, key, options) {
    testControl.options = options; testControl.creations++;
    let listener;
    const emit = (event, next) => { testControl.session = next; listener?.(event, next); };
    testControl.emit = emit;
    const call = async (name, args, fallback) => {
      testControl.calls.push({name,args});
      if(testControl.hold === name) await new Promise(resolve => testControl.release = resolve);
      const result = testControl.results[name] || fallback;
      if(result.throw) throw result.throw;
      return result;
    };
    return {auth: {
      onAuthStateChange(callback) { listener = callback; return {data:{subscription:{unsubscribe(){}}}}; },
      async getSession() {
        const next = testControl.session;
        queueMicrotask(()=>emit(testControl.recovery ? 'PASSWORD_RECOVERY' : 'INITIAL_SESSION',next));
        return {data:{session:next},error:null};
      },
      async signInWithPassword(args) {
        const result = await call('login',args,{data:{session:testControl.loginSession},error:null});
        if(result.data?.session) emit('SIGNED_IN',result.data.session);
        return result;
      },
      async signUp(args) {
        const result = await call('register',args,{data:{session:null,user:{identities:[{id:'test-identity'}]}},error:null});
        if(result.data?.session) emit('SIGNED_IN',result.data.session);
        return result;
      },
      resetPasswordForEmail(email, args) { return call('forgot',{email,...args},{error:null}); },
      getUser() { return call('verify',{}, {data:{user:testControl.session?.user},error:null}); },
      async updateUser(args) {
        const result = await call('reset',args,{data:{user:testControl.session?.user},error:null});
        if(!result.error) emit('USER_UPDATED',testControl.session);
        return result;
      },
      async signOut(args) {
        const result = await call('logout',args,{error:null});
        if(!result.error) emit('SIGNED_OUT',null);
        return result;
      }
    }};
  }};
}
"""

RUNNER = r"""
(async () => {
  const report = document.getElementById('report');
  const frame = document.getElementById('frame');
  const checks=[];
  const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label);};
  const wait = () => new Promise(resolve=>setTimeout(resolve,25));
  const fakeSession = {user:{id:'00000000-0000-4000-8000-000000000001',email:'portfolio-test@example.com'}};
  const configure=(enabled=false)=>parent.__authControl={configured:enabled,session:null,loginSession:fakeSession,
    results:{},calls:[],creations:0};
  let win, doc, control;
  const open = async (page, enabled=false, setup=()=>{}) => {
    control=configure(enabled);setup(control);
    const loaded=new Promise(resolve=>frame.onload=()=>{
      if(frame.contentWindow.location.pathname===new URL(page,location.href).pathname)resolve();
    });
    frame.src='/'+page;await loaded;
    win=frame.contentWindow;doc=frame.contentDocument;
    await win.PortfolioAuth.ready;
    assert(win.innerWidth===Number(new URL(location.href).searchParams.get('width')),'exact test viewport');
    assert(!win.__authErrors.length,'no uncaught errors on '+page);
    assert(doc.documentElement.scrollWidth<=win.innerWidth,'no overflow on '+page);
    return doc;
  };
  const fill=values=>Object.entries(values).forEach(([name,value])=>doc.getElementById('authForm').elements.namedItem(name).value=value);
  const submit=()=>doc.getElementById('authForm').dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));
  const text=()=>doc.getElementById('authMessage').textContent;
  const valid=()=>fill({email:'portfolio-test@example.com',password:'x'.repeat(12),confirmPassword:'x'.repeat(12)});
  const send=async()=>{submit();await wait();};
  try {
    for(const page of ['login.html','register.html','forgot-password.html','reset-password.html']) {
      await open(page);
      assert(win.PortfolioAuth.getStatus()==='unconfigured','placeholder status '+page);
      assert(doc.getElementById('authStatus').textContent === 'Supabase chưa được cấu hình. Vui lòng thiết lập Project URL và Publishable/Anon Key.','friendly config '+page);
      assert(doc.querySelector('[type=submit]').disabled,'placeholder disables requests '+page);
      assert(!doc.querySelector('script[src*="cdn.jsdelivr"]'),'no SDK request for placeholder '+page);
    }
    await open('login.html',true);
    assert(doc.getElementById('authConfirmedMessage').hidden,'normal login hides confirmation banner');
    await open('login.html?confirmed=0',true);
    assert(doc.getElementById('authConfirmedMessage').hidden,'only confirmed=1 shows success');
    await open('login.html?confirmed=1&return=health-prediction.html#confirmation-test',true);
    const banner=doc.getElementById('authConfirmedMessage');
    assert(!banner.hidden&&banner.dataset.kind==='success'&&banner.textContent==='Email đã được xác nhận thành công. Bạn có thể đăng nhập ngay.','email confirmation success banner');
    assert(!new URL(win.location.href).searchParams.has('confirmed'),'remove confirmation flag');
    assert(new URL(win.location.href).searchParams.get('return')==='health-prediction.html'&&win.location.hash==='#confirmation-test','preserve return and hash');
    assert(!win.PortfolioAuth.getUser()&&!win.PortfolioAuth.getSession()&&control.calls.length===0,'confirmation flag does not authenticate or call login');
    assert(doc.querySelector('[data-auth-user]').hidden&&doc.getElementById('authContinue').hidden&&!doc.querySelector('[type=submit]').disabled,'confirmation remains guest with login available');
    const originalDocument=doc;
    await wait();
    assert(frame.contentDocument===originalDocument&&control.creations===1,'confirmation cleanup does not reload');
    fill({email:'portfolio-test@example.com',password:'x'.repeat(12)});
    doc.getElementById('authEmail').dispatchEvent(new win.Event('input',{bubbles:true}));
    control.results.login={error:{code:'invalid_credentials'}};await send();
    assert(!banner.hidden&&text()==='Email hoặc mật khẩu không chính xác.','confirmation banner survives input and login errors');
    await open('register.html?confirmed=1',true);
    assert(new URL(win.location.href).searchParams.get('confirmed')==='1'&&!win.PortfolioAuth.getUser()&&control.calls.length===0,'confirmation flag only handled on login');
    await open('register.html');
    submit();
    assert(doc.querySelectorAll('[aria-invalid=true]').length===3,'empty registration validation');
    fill({email:'bad',password:'1234567',confirmPassword:'different'});submit();
    assert(doc.getElementById('authEmail-error').textContent==='Email không đúng định dạng.','email format validation');
    assert(doc.getElementById('authPassword-error').textContent==='Mật khẩu phải có ít nhất 8 ký tự.','password minimum validation');
    assert(doc.getElementById('authConfirmPassword-error').textContent==='Mật khẩu nhập lại không khớp.','confirmation validation');
    valid();doc.getElementById('authPassword').dispatchEvent(new win.Event('input',{bubbles:true}));
    assert(doc.getElementById('authPassword-error').hidden && doc.getElementById('authConfirmPassword-error').hidden,'input updates errors');
    const toggle=doc.querySelector('[data-password-toggle="authPassword"]');toggle.click();
    assert(doc.getElementById('authPassword').type==='text'&&toggle.getAttribute('aria-pressed')==='true','password show accessible');
    toggle.click();assert(doc.getElementById('authPassword').type==='password','password hide');
    await open('register.html',true);fill({email:'invalid',password:'short',confirmPassword:'wrong'});await send();
    assert(control.calls.length===0,'invalid form never requests auth');
    valid();await send();
    assert(text()==='Đăng ký thành công. Hãy kiểm tra email để xác nhận tài khoản.','registration email confirmation');
    assert(control.calls[0].args.options.emailRedirectTo==='https://data-science-portfolio-steel.vercel.app/login.html?confirmed=1','signup public callback URL with confirmation flag');
    assert(!doc.getElementById('authPassword').value,'clear password after registration');
    control.results.register={data:{session:null,user:{identities:[]}},error:null};valid();await send();
    assert(text().includes('Nếu email được chấp nhận')&&!text().includes('Tài khoản này đã được đăng ký'),'obfuscated signup stays neutral');
    control.results.register={error:{code:'user_already_exists',message:'RAW_PRIVATE_ERROR'}};valid();await send();
    assert(text()==='Tài khoản này đã được đăng ký. Hãy thử đăng nhập.','explicit duplicate error');
    control.results.register={error:{code:'unknown',message:'RAW_PRIVATE_ERROR'}};await send();
    assert(text()==='Đăng ký không thành công. Vui lòng thử lại.','no raw signup error');
    control.results.register={throw:{name:'TypeError',message:'RAW_PRIVATE_ERROR'}};await send();
    assert(text()==='Không thể kết nối. Vui lòng kiểm tra mạng và thử lại.','network registration error');
    await open('login.html',true);fill({email:'portfolio-test@example.com',password:'x'.repeat(12)});
    for(const code of ['invalid_credentials','user_not_found']) {
      control.results.login={error:{code,message:'RAW_PRIVATE_ERROR'}};await send();
      assert(text()==='Email hoặc mật khẩu không chính xác.','login does not enumerate '+code);
    }
    control.results.login={error:{code:'email_not_confirmed'}};await send();
    assert(text()==='Bạn cần xác nhận email trước khi đăng nhập. Hãy kiểm tra hộp thư.','unconfirmed login');
    control.results.login={error:{code:'other',message:'RAW_PRIVATE_ERROR'}};await send();
    assert(text()==='Đăng nhập không thành công. Vui lòng thử lại.','no raw login error');
    control.hold='login';const before=control.calls.length;submit();submit();
    assert(control.calls.length===before+1 && doc.querySelector('[type=submit]').disabled && doc.getElementById('authForm').getAttribute('aria-busy')==='true','double submit and loading');
    control.release();await wait();assert(!doc.querySelector('[type=submit]').disabled,'restore request button');
    await open('login.html',true,c=>c.session=fakeSession);
    assert(win.PortfolioAuth.getUser().id===fakeSession.user.id&&win.PortfolioAuth.getUser().email===fakeSession.user.email,'SDK user exposed for future history');
    assert([...doc.querySelectorAll('[data-auth-guest]')].every(e=>e.hidden)&&doc.querySelector('[data-auth-email]').textContent===fakeSession.user.email,'restored navbar');
    doc.querySelector('[data-auth-logout]').click();await wait();
    assert(!win.PortfolioAuth.getUser()&&doc.querySelector('[data-auth-email]').textContent===''&&doc.getElementById('authContinue').hidden,'logout clears account UI');
    assert(control.calls.at(-1).args.scope==='local','logout browser scope');
    control.emit('SIGNED_IN',fakeSession);
    assert(doc.querySelector('[data-auth-email]').textContent===fakeSession.user.email,'auth change updates navbar');
    await open('forgot-password.html',true);fill({email:'portfolio-test@example.com'});await send();
    const neutral='Nếu email này được liên kết với một tài khoản, bạn sẽ nhận được hướng dẫn đặt lại mật khẩu.';
    assert(text()===neutral&&control.calls[0].args.redirectTo==='https://data-science-portfolio-steel.vercel.app/reset-password.html','forgot neutral and public reset URL');
    control.results.forgot={error:{code:'user_not_found'}};await send();assert(text()===neutral,'forgot missing account neutral');
    control.results.forgot={throw:{name:'TypeError'}};await send();assert(text().startsWith('Không thể kết nối'),'forgot network failure');
    await open('reset-password.html#type=recovery',true,c=>c.session=fakeSession);
    assert(doc.getElementById('authFields').disabled,'saved login or spoofed type does not authorize recovery');
    fill({password:'x'.repeat(12),confirmPassword:'x'.repeat(12)});await send();
    assert(!control.calls.length&&text().includes('không hợp lệ'),'invalid recovery cannot update');
    await open('reset-password.html',true,c=>{c.session=fakeSession;c.recovery=true;});
    assert(!doc.getElementById('authFields').disabled,'valid recovery event enables form');
    fill({password:'short',confirmPassword:'wrong'});await send();assert(!control.calls.length,'reset validation prevents requests');
    fill({password:'x'.repeat(12),confirmPassword:'x'.repeat(12)});
    control.results.verify={error:{code:'session_expired',status:401}};await send();
    assert(control.calls.every(c=>c.name==='verify')&&text().includes('đã hết hạn'),'expired server verification blocks password update');
    await open('reset-password.html',true,c=>{c.session=fakeSession;c.recovery=true;});
    fill({password:'x'.repeat(12),confirmPassword:'x'.repeat(12)});await send();
    assert(control.calls.map(c=>c.name).join(',')==='verify,reset,logout','verify recovery before update');
    assert(text()==='Mật khẩu đã được cập nhật thành công.'&&!doc.getElementById('authResetSuccess').hidden,'reset success login link');
    assert(!win.PortfolioAuth.getUser()&&doc.getElementById('authFields').disabled,'reset session cleared and form disabled');
    for(const page of ['index.html','health-prediction.html']) {
      await open(page);
      assert([...doc.querySelectorAll('[data-auth-guest]')].every(e=>!e.hidden),'public guest navbar '+page);
      if(page==='health-prediction.html') {
        await win.loadHealthModel();
        for(const [i,score] of [[0,'34.2%'],[1,'99.6%']]) {
          doc.querySelector('[data-health-sample="'+i+'"]').click();
          doc.getElementById('healthForm').dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));
          assert(doc.getElementById('healthProbability').textContent===score&&!doc.getElementById('healthResult').hidden,'guest health sample '+(i+1));
        }
      }
      await open(page,true,c=>c.session=fakeSession);
      assert(doc.querySelector('[data-auth-email]').textContent===fakeSession.user.email,'public restored navbar '+page);
    }
    const navigateLogin=async(returnValue,expected)=>{
      await open('login.html?return='+encodeURIComponent(returnValue),true);
      fill({email:'portfolio-test@example.com',password:'x'.repeat(12)});
      const loaded=new Promise(resolve=>frame.onload=resolve);submit();await loaded;
      assert(frame.contentWindow.location.pathname===expected,'safe redirect '+returnValue);
      await frame.contentWindow.PortfolioAuth.ready;
      assert(frame.contentDocument.querySelector('[data-auth-email]').textContent===fakeSession.user.email,'session after navigation');
    };
    await navigateLogin('health-prediction.html','/health-prediction.html');
    for(const target of ['https://outside.example/path','//outside.example','javascript:alert(1)','login.html','\\\\outside.example','https://user@outside.example/index.html']) {
      await navigateLogin(target,'/index.html');
    }
    await open('register.html?return=health-prediction.html',true,c=>c.results.register={data:{session:fakeSession},error:null});
    valid();const registered=new Promise(resolve=>frame.onload=resolve);submit();await registered;
    assert(frame.contentWindow.location.pathname==='/health-prediction.html','immediate signup session return');
    report.textContent=JSON.stringify({ok:true,width:Number(new URL(location.href).searchParams.get('width')),checks:checks.length});
  } catch(error) {
    report.textContent=JSON.stringify({ok:false,error:error.message,checks});
  }
})();
"""


def main():
    for name, expected in PROTECTED.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name + " changed"
    for page in PAGES:
        parser = PageParser()
        parser.feed((ROOT / page).read_text(encoding="utf-8"))
        assert not parser.stack and all(ref in parser.ids for ref in parser.references), page
    auth = (ROOT / "auth.js").read_text(encoding="utf-8")
    assert not re.search(r"localStorage\s*\.|sessionStorage\s*\.|document\.cookie|console\.(log|error)|\.from\(", auth)
    browser = os.environ.get("HEALTH_TEST_BROWSER") or next((str(p) for p in [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ] if p.exists()), None) or shutil.which("chromium") or shutil.which("google-chrome")
    if not browser:
        raise RuntimeError("Set HEALTH_TEST_BROWSER to an Edge/Chrome/Chromium executable.")

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            url = urlparse(self.path)
            if url.path == "/__auth_test__.html":
                width = int(parse_qs(url.query)["width"][0])
                content = ('<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>'
                           '<pre id="report"></pre>'
                           f'<iframe id="frame" style="width:{width}px;height:1100px;border:0"></iframe>'
                           f'<script>{RUNNER}</script></body></html>').encode()
                mime = "text/html; charset=utf-8"
            elif url.path.endswith(".html") and (ROOT / url.path.lstrip("/")).is_file():
                content = (ROOT / url.path.lstrip("/")).read_text(encoding="utf-8").replace("<head>", "<head><script>" + MOCK + "</script>").encode()
                mime = "text/html; charset=utf-8"
            elif url.path == "/supabase-config.js":
                content = ('window.PORTFOLIO_SUPABASE_CONFIG = parent.__authControl?.configured '
                           '? {url:"https://test.supabase.co",key:"sb_publishable_test_mock"} '
                           ': {url:"YOUR_SUPABASE_URL",key:"YOUR_SUPABASE_ANON_KEY"};').encode()
                mime = "text/javascript; charset=utf-8"
            else:
                super().do_GET()
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            self.send_error(405, "Tests must not send real auth requests")

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="portfolio-auth-test-") as temp:
            for width in [320, 390, 768, 1440]:
                result = subprocess.run([
                    browser, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-background-networking",
                    "--disable-extensions", "--no-default-browser-check", "--window-size=1500,1200",
                    f"--user-data-dir={Path(temp) / str(width)}", "--virtual-time-budget=60000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/__auth_test__.html?width={width}",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                match = re.search(r'<pre id="report">(.*?)</pre>', result.stdout, re.S)
                if not match or not match.group(1):
                    raise RuntimeError("Browser tests did not finish: " + result.stderr[-1000:])
                report = json.loads(html.unescape(match.group(1)))
                assert report["ok"], report
                print(report)
    finally:
        server.shutdown()
        server.server_close()
    print("PASS: auth pages, validation, errors, sessions, navigation, recovery and responsive (mock SDK).")


if __name__ == "__main__":
    main()
