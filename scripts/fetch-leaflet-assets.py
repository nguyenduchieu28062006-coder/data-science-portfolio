"""Vendor pinned Leaflet distribution; never access any listing source."""
from pathlib import Path
import urllib.request,hashlib,base64
root=Path(__file__).resolve().parents[1]/'assets/vendor/leaflet'
root.mkdir(parents=True,exist_ok=True)
for name,expected in [('leaflet.js','20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo='),('leaflet.css','p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=')]:
    target=root/name
    content=target.read_bytes() if target.exists() else urllib.request.urlopen('https://unpkg.com/leaflet@1.9.4/dist/'+name,timeout=30).read()
    assert base64.b64encode(hashlib.sha256(content).digest()).decode()==expected
    if not target.exists():target.write_bytes(content)
license_path=root/'LICENSE'
if not license_path.exists():license_path.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/LICENSE',timeout=30).read())
print('Leaflet 1.9.4 assets pinned and verified')
