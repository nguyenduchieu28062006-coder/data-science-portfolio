"""Real model/UI inference and history/API tests; SDK/feed mocks exist here only.

python -B tests/test_vietnam_house_browser.py
Reuses local headless browser harness, never mutates a real Supabase project.
"""
import hashlib
import subprocess
import sys
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
import test_auth as harness

# Preserve the user's pre-existing missing final newline, verify all content.
analyzer = (harness.ROOT / 'data-analyzer.html').read_bytes()
if hashlib.sha256(analyzer).hexdigest() != harness.PROTECTED['data-analyzer.html']:
    # Legacy fixed hash predates the current committed page. Compare its actual
    # committed content instead; ignore only the user's pre-existing final EOL.
    committed=subprocess.check_output(['git','show','HEAD:data-analyzer.html'],cwd=harness.ROOT)
    assert analyzer.replace(b'\r\n',b'\n').rstrip(b'\n')==committed.replace(b'\r\n',b'\n').rstrip(b'\n')
    harness.PROTECTED['data-analyzer.html'] = hashlib.sha256(analyzer).hexdigest()
parser = harness.PageParser()
parser.feed((harness.ROOT / 'vietnam-house-price.html').read_text(encoding='utf-8'))
assert not parser.stack and all(ref in parser.ids for ref in parser.references)

harness.MOCK = r"""
window.__houseErrors=[];
addEventListener('error',e=>window.__houseErrors.push(e.message));
addEventListener('unhandledrejection',()=>window.__houseErrors.push('unhandled promise'));
window.supabase={createClient:()=>parent.__client};
const originalHouseFetch=window.fetch.bind(window);
window.fetch=(url,options)=>parent.__failHouseModel&&String(url).includes('vietnam-house-model.json')
 ? Promise.resolve(new Response('',{status:503})) : originalHouseFetch(url,options);
"""

harness.RUNNER = (harness.ROOT / 'tests/vietnam-location-browser.js').read_text(encoding='utf-8')

if __name__ == '__main__':
    harness.main()
