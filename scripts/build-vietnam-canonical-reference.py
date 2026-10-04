"""Build canonical administrative index from cached official NSO responses."""
import json,re,unicodedata,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def norm(s):return ' '.join(unicodedata.normalize('NFC',s).split()).casefold()
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def main():
    current=ROOT/'data/vietnam-location-index.json'
    if current.exists() and read('data/vietnam-location-index.json').get('schema_version',0)>=3:
        print('Existing official canonical index reused; no overwrite or source request.');return
    original=ROOT/'docs/archive/beta-location-v2';original.mkdir(parents=True,exist_ok=True)
    for name in ['data/vietnam-location-index.json','data/vietnam-market-stats.json','vietnam-house-model.json','data/vietnam-house-parity-fixtures.json']:
        dst=original/Path(name).name
        if not dst.exists():shutil.copy2(ROOT/name,dst)
    ps=[r for r in read('docs/admin-source/DanhMucTinh.json') if r.get('MaTinh')]
    ws=[r for r in read('docs/admin-source/DanhMucPhuongXa.json') if r.get('MaPhuongXa')]
    assert len(ps)==34 and len(ws)==3321
    names=read('data/vietnam-admin-aliases.json')['current_provinces']
    def pname(full):
        short=re.sub(r'^(Tỉnh|Thành phố)\s+','',full)
        if short=='Hồ Chí Minh':short='TP. Hồ Chí Minh'
        assert short in names,full
        return short
    provinces=[{'id':pname(r['TenTinh']),'name':pname(r['TenTinh']),'label':r['TenTinh'],'code':r['MaTinh'],'level':'PROVINCE'} for r in ps]
    pmap={p['code']:p['id'] for p in provinces}
    wards=[{'id':'vn_'+r['MaPhuongXa'],'code':r['MaPhuongXa'],'name':r['TenPhuongXa'],'label':r['TenPhuongXa'],'province':pmap[r['MaTinh']],'level':'WARD'} for r in ws]
    assert len({r['id'] for r in wards})==3321
    old=read('docs/archive/beta-location-v2/vietnam-location-index.json')
    # Only explicit whole-unit clauses within the unmerged Hanoi province.
    # Stop before any partial-unit clause; split areas cannot be resolved
    # without coordinates. Other provinces remain unassigned, not guessed.
    paras=read('docs/admin-source/merger-paragraphs.json');active=False;mapping={};evidence=[];conflicts=set()
    source='https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm'
    old_hanoi=[w for w in old['wards'] if w['province']=='Hà Nội']
    historical=[r for r in read('docs/admin-source/nso-historical-2025-06-30.json') if r['TenTinh']=='Thành phố Hà Nội']
    current={norm(w['name']):w['id'] for w in wards if w['province']=='Hà Nội'}
    for para in paras:
        para=unicodedata.normalize('NFC',para)
        if para.startswith('Danh sách 126 xã, phường mới của Hà Nội sau sắp xếp'):active=True;continue
        if active and para.startswith('127.'):active=False
        if not active or not re.match(r'^\d+\. Sắp xếp toàn bộ',para):continue
        dest=re.search(r'thành (?:phường|xã) mới có tên gọi là ((?:phường|xã) [^.]+)',para)
        if not dest:continue
        target=current.get(norm(dest[1]))
        if not target:continue
        body=para.split('của ',1)[1].split(' thành ',1)[0]
        body=re.split(r',?\s*(?:và )?một phần|,?\s*(?:và )?phần còn lại',body)[0]
        group=re.match(r'(?:các )?(phường|xã)\s+(.+)',body)
        if not group:continue
        for label in re.split(r',| và ',group[2]):
            label=re.sub(r'^(?:các )?(?:phường|xã)\s+','',label).strip()
            # Entire official historical reference, not uniqueness only in
            # the market subset. Check full prefix AND district context.
            admin_matches=[r for r in historical if norm(r['TenPhuongXa'])==norm(group[1]+' '+label)]
            if len(admin_matches)!=1:continue
            matches=[w for w in old_hanoi if norm(w['name'])==norm(label)]
            if len(matches)!=1:continue
            old_district=re.sub(r'^(Quận|Huyện|Thị xã|Thành phố)\s+','',admin_matches[0]['TenQuanHuyen'])
            if norm(matches[0]['historical_district'])!=norm(old_district):continue
            key=matches[0]['id']
            if key in mapping and mapping[key]!=target:conflicts.add(key)
            mapping[key]=target
            evidence.append({'historical_ward_id':key,'historical_name':matches[0]['name'],'historical_district':matches[0]['historical_district'],'canonical_ward_id':target,'method':'Entire historical unit explicitly included; no partial mapping','source_url':source,'evidence':para})
    for key in conflicts:mapping.pop(key,None)
    evidence=[e for e in evidence if e['historical_ward_id'] in mapping]
    out={'schema_version':3,'source':'Cục Thống kê / official DMDVHC web service','source_url':'https://danhmuchanhchinh.nso.gov.vn/DMDVHC.asmx',
         'retrieved_at':datetime.now(timezone.utc).isoformat(),'admin_version':'NSO snapshot queried as of 2026-10-04; two-tier administration after 2025-07-01',
         'provinces':provinces,'wards':wards,'sub_areas':[],'property_types':old['property_types'],'historical_to_canonical':mapping,
         'mapping_policy':'Only documented complete-unit Hanoi mergers, source names unique within province; partial/split and other historical wards unassigned. No same-name guessing.'}
    (ROOT/'data/vietnam-location-index.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'docs/vietnam-admin-mapping-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Official canonical provinces',len(provinces),'wards',len(wards),'whole-unit mapped historical wards',len(mapping))
if __name__=='__main__':main()
