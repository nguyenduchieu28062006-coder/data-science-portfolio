"""Download a pinned public dataset to TEMP for read-only audit, with SHA256 checks."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = "ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f"
CACHE = Path(tempfile.gettempdir()) / "tinix-transaction-audit" / REVISION


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    with urlopen(f'https://huggingface.co/api/datasets/tinixai/vietnam-real-estates/tree/{REVISION}', timeout=30) as response:
        manifest = json.load(response)
    files = [entry for entry in manifest if entry['path'].endswith('.parquet')]
    assert len(files) == 10

    def download(entry):
        name = entry['path']
        assert Path(name).name == name
        target = CACHE / name
        expected = entry['lfs']['oid']
        if target.exists() and target.stat().st_size == entry['size'] and digest(target) == expected:
            print(f'CACHE VERIFIED {name}', flush=True)
        else:
            partial = target.with_suffix('.partial')
            for attempt in range(4):
                try:
                    offset = partial.stat().st_size if partial.exists() else 0
                    url = f'https://huggingface.co/datasets/tinixai/vietnam-real-estates/resolve/{REVISION}/{name}?download=true&attempt={attempt}'
                    request = Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
                    with urlopen(request, timeout=60) as response:
                        append = offset and response.status == 206
                        with partial.open('ab' if append else 'wb') as output:
                            for chunk in iter(lambda: response.read(2 * 1024 * 1024), b''):
                                output.write(chunk)
                    if partial.stat().st_size != entry['size'] or digest(partial) != expected:
                        raise RuntimeError(f'Integrity check failed for {name}')
                    partial.replace(target)
                    print(f'DOWNLOADED VERIFIED {name} ({entry["size"] / 1e6:.1f} MB)', flush=True)
                    break
                except Exception as error:
                    if attempt == 3:
                        raise RuntimeError(f'Download failed: {name}, {type(error).__name__}') from None
                    print(f'RETRY {name}: {type(error).__name__}', flush=True)
                    time.sleep(1)
        return {'name': name, 'bytes': entry['size'], 'sha256': expected, 'local_cache_path': str(target)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, files))
    output = ROOT / 'docs' / 'tinix-download-manifest.json'
    output.write_text(json.dumps({'dataset': 'tinixai/vietnam-real-estates', 'revision': REVISION,
                                  'cache_only': True, 'files': results}, indent=2) + '\n', encoding='utf-8')
    print('PASS: all ten pinned files match upstream SHA256.', flush=True)


if __name__ == '__main__':
    main()
