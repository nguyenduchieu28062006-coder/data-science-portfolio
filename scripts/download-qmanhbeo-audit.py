"""Version-pinned public Kaggle download for source audit only.

Never downloads listing websites; never cleans data or trains a model.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(tempfile.gettempdir())/'qmanhbeo-v3-source-audit-20261004'
CACHE.mkdir(exist_ok=True)
REF = 'qmanhbeo/vietnamese-real-estate-listings-may-2024'
VERSION = 3
FILENAME = 'VN-real-estate-Apr-Sept-2025.csv'
MAX_BYTES = 300 * 1024 * 1024


def metadata(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'dataset-source-audit/1.0'}), timeout=35) as response:
        payload = response.read()
    return {'url': url, 'sha256': hashlib.sha256(payload).hexdigest(), 'response': json.loads(payload)}


def main():
    urls = [f'https://www.kaggle.com/api/v1/datasets/view/{REF}', f'https://www.kaggle.com/api/v1/datasets/list/{REF}']
    items = list(ThreadPoolExecutor(max_workers=2).map(metadata, urls))
    card, listing = [r['response'] for r in items]
    assert card['currentVersionNumber'] == VERSION, 'Current file manifest changed: inspect before download'
    files = listing['datasetFiles']
    assert len(files) == 1 and files[0]['name'] == FILENAME, files
    expected = files[0]['totalBytes']
    assert 0 < expected <= MAX_BYTES
    manifest = {'dataset': REF, 'version': VERSION, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'source_metadata': items, 'file_count': len(files), 'training_performed': False,
                'cleaning_performed': False, 'files': []}
    target = CACHE/FILENAME
    url = f'https://www.kaggle.com/api/v1/datasets/download/{REF}/{FILENAME}?datasetVersionNumber={VERSION}'
    if target.exists() and target.stat().st_size == expected:
        raw_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        print('Using complete cached raw file', flush=True)
    else:
        staging = CACHE/(FILENAME+'.part')
        digest = hashlib.sha256()
        size = 0
        request = urllib.request.Request(url, headers={'User-Agent': 'dataset-source-audit/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response, staging.open('wb') as output:
            assert response.headers.get('Content-Type', '').startswith('text/csv'), 'Unexpected wrapper; inspect before extraction'
            declared = response.headers.get('Content-Length')
            assert declared is None or int(declared) == expected
            while chunk := response.read(1024*1024):
                size += len(chunk)
                assert size <= MAX_BYTES, 'Size bound exceeded'
                output.write(chunk)
                digest.update(chunk)
                if size % (16*1024*1024) == 0:
                    print(f'Downloaded {size:,} of {expected:,} raw bytes', flush=True)
        assert size == expected, (size, expected)
        raw_hash = digest.hexdigest()
        staging.replace(target)
    manifest['files'].append({'filename': FILENAME, 'source_url': url, 'expected_raw_bytes': expected,
                              'actual_raw_bytes': target.stat().st_size, 'sha256': raw_hash,
                              'local_cache_path': str(target), 'complete_source_file': True})
    (ROOT/'docs/qmanhbeo-download-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'file_count': len(files), **manifest['files'][0]}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
