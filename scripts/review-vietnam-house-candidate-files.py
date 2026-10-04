"""Bounded source inspection only: no cleaning, training or website changes.

Downloads small, version-pinned public dataset files into TEMP, never listing
websites. A large file is read only as a bounded prefix for schema inspection.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
CACHE=Path(tempfile.gettempdir())/'vietnam-house-source-survey-20261004'
CACHE.mkdir(exist_ok=True)
JOBS=[
    ('cresht2606/vietnam-real-estate-datasets-catalyst',1,'house_buying_dec29th_2025.csv',17517604,'full'),
    ('andyvo1009/real-estate-in-vietnam',1,'sale_real_estate.csv',2523088,'full'),
    ('nguyentiennhan/vietnam-housing-dataset-2024',8,'vietnam_housing_dataset.csv',3532685,'full'),
    ('ladcva/vietnam-housing-dataset-hanoi',1,'VN_housing_dataset.csv',18104039,'full'),
    ('cnglmph/ho-chi-minh-city-real-estate-data-2025',1,'data_public.csv',46033823,'prefix'),
    ('qmanhbeo/vietnamese-real-estate-listings-may-2024',3,'VN-real-estate-Apr-Sept-2025.csv',220057487,'prefix'),
]
MAX_FULL=20*1024*1024
MAX_PREFIX=128*1024


def inspect(job):
    ref,version,filename,expected,scope=job
    url=f'https://www.kaggle.com/api/v1/datasets/download/{ref}/{urllib.parse.quote(filename)}?datasetVersionNumber={version}'
    result={'dataset':ref,'version':version,'filename':filename,'source_url':url,
            'expected_raw_bytes':expected,'scope':scope}
    try:
        assert scope=='prefix' or expected<=MAX_FULL
        req=urllib.request.Request(url,headers={'User-Agent':'dataset-source-review/1.0'})
        with urllib.request.urlopen(req,timeout=40) as response:
            result['content_type']=response.headers.get('Content-Type')
            result['content_length']=response.headers.get('Content-Length')
            # Signed storage URLs are not persisted or printed.
            if scope=='full' and result['content_length']:
                assert int(result['content_length'])<=MAX_FULL,'HTTP file exceeds limit'
            limit=MAX_FULL if scope=='full' else MAX_PREFIX
            payload=response.read(limit+1)
        result['network_bytes_read']=len(payload)
        if scope=='full':
            assert len(payload)<=MAX_FULL,'download exceeds limit'
            if zipfile.is_zipfile(io.BytesIO(payload)):
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    members=[m for m in archive.infolist() if Path(m.filename).name==filename]
                    assert len(members)==1 and members[0].file_size<=MAX_FULL
                    raw=archive.read(members[0])
                result['http_wrapped_zip']=True
            else: raw=payload
            assert len(raw)==expected,(len(raw),expected,raw[:100])
        elif payload.startswith(b'PK\x03\x04'):
            # Decode just the first ZIP member's prefix; no archive extraction.
            header=struct.unpack('<4s5H3I2H',payload[:30])
            method=header[3];name_len=header[-2];extra_len=header[-1]
            offset=30+name_len+extra_len
            assert payload[30:30+name_len].decode('utf-8')==filename
            assert method==8,method
            raw=zlib.decompressobj(-15).decompress(payload[offset:],MAX_PREFIX)
            result['http_wrapped_zip']=True
        else: raw=payload[:MAX_PREFIX]
        target=CACHE/(ref.replace('/','__')+('__prefix__' if scope=='prefix' else '__')+filename)
        target.write_bytes(raw)
        result['local_cache_path']=str(target)
        result['inspection_bytes']=len(raw)
        result['inspection_sha256']=hashlib.sha256(raw).hexdigest()
        result['complete_source_file']=scope=='full'
        result['preview']=raw[:900].decode('utf-8-sig',errors='replace')
    except Exception as error:
        result['error']=f'{type(error).__name__}: {error}'
    return result


def main():
    rows=list(ThreadPoolExecutor(max_workers=5).map(inspect,JOBS))
    (ROOT/'docs/vietnam-house-new-candidates-file-manifest.json').write_text(
        json.dumps({'review_date':'2026-10-04','training_performed':False,'cleaning_performed':False,
                    'max_full_bytes_per_file':MAX_FULL,'max_prefix_network_bytes':MAX_PREFIX+1,'files':rows},
                   ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in rows:
        print(json.dumps(row,ensure_ascii=False))


if __name__=='__main__':
    main()
