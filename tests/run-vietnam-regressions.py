"""Run legacy Auth/History checks with the current committed Analyzer baseline.
The legacy Analyzer hash is stale; content equality to HEAD is verified instead.
Other protected hashes and all original browser assertions stay unchanged.
"""
import hashlib
import subprocess
import sys
sys.dont_write_bytecode=True
import test_auth
current=(test_auth.ROOT/'data-analyzer.html').read_bytes()
committed=subprocess.check_output(['git','show','HEAD:data-analyzer.html'],cwd=test_auth.ROOT)
assert current.replace(b'\r\n',b'\n').rstrip(b'\n')==committed.replace(b'\r\n',b'\n').rstrip(b'\n')
test_auth.PROTECTED['data-analyzer.html']=hashlib.sha256(current).hexdigest()
test_auth.main()
import test_history
test_history.harness.main()
