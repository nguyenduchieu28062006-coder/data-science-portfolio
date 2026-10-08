"use strict";
(() => {
    const $ = id => document.getElementById(id);
    const nationalCenter = [16.4, 106.7];
    const provinceStyle = {color:'#2563eb', weight:1.2, fillColor:'#06b6d4', fillOpacity:.15};
    const communeStyle = {color:'#2563eb', weight:1, fillColor:'#38bdf8', fillOpacity:.16};
    const selectedStyle = {color:'#92400e', weight:2.5, fillColor:'#fbbf24', fillOpacity:.5};

    function create({admin, json, context, onProvince, onCommune, fold}) {
        const provinces = new Map(admin.provinces.map(p => [p.province_code, p]));
        const communes = new Map(admin.communes.map(w => [w.commune_code, w]));
        const rows = new Map(admin.provinces.map(p => [p.province_code,
            admin.communes.filter(w => w.province_code === p.province_code)]));
        const provinceLayers = [], communeLayers = new Map(), cache = new Map();
        let map = null, country = null, communeGroup = null, manifest = null;
        let selected = {province_code:'', commune_code:''}, viewProvince = '', generation = 0;
        let request = null, sourceState = 'UNAVAILABLE', loadState = 'NATIONAL';
        let lastRenderMs = 0, geometryRequests = 0, tileLayer = null, tilesLoaded = 0, tileErrors = 0;

        function selectionLabel() {
            const p = provinces.get(selected.province_code), w = communes.get(selected.commune_code);
            return w && w.province_code === p?.province_code
                ? `${w.commune_name} · ${w.commune_code}, ${p.province_name}`
                : p ? `${p.province_name} · Chưa chọn xã/phường` : 'Chưa chọn địa phương';
        }

        function updateSelection() {
            $('mapSelection').textContent = 'Đã chọn: ' + selectionLabel();
            for (const [code, layer] of communeLayers) layer.setStyle(code === selected.commune_code ? selectedStyle : communeStyle);
            for (const button of $('mapCommuneList').querySelectorAll('button')) {
                const active = button.dataset.communeCode === selected.commune_code;
                button.setAttribute('aria-pressed', String(active));
            }
            const layer = communeLayers.get(selected.commune_code);
            if (layer && map) {
                layer.bringToFront();
                map.fitBounds(layer.getBounds(), {padding:[24,24], maxZoom:13, animate:false});
            }
        }

        function renderList() {
            const q = fold($('mapCommuneSearch').value);
            const all = rows.get(viewProvince) || [];
            const visible = all.filter(w => fold(w.commune_name).includes(q) || w.commune_code.includes(q));
            const fragment = document.createDocumentFragment();
            for (const w of visible) {
                const button = document.createElement('button');
                button.type = 'button'; button.className = 'house-map-commune';
                button.dataset.communeCode = w.commune_code;
                button.textContent = `${w.commune_name} · ${w.commune_code}`;
                button.title = `${w.commune_name}, ${provinces.get(viewProvince).province_name}`;
                button.setAttribute('aria-pressed', String(w.commune_code === selected.commune_code));
                button.addEventListener('click', () => chooseCommune(w.commune_code));
                fragment.append(button);
            }
            if (!visible.length) {
                const empty = document.createElement('p');
                empty.textContent = 'Không có xã/phường phù hợp. Thử tên hoặc mã khác.';
                fragment.append(empty);
            }
            $('mapCommuneList').replaceChildren(fragment);
            $('mapCommuneCount').textContent = `${visible.length} / ${all.length} xã/phường/đặc khu`;
        }

        function chooseCommune(code) {
            const w = communes.get(code);
            if (w?.province_code === viewProvince && viewProvince === context().province_code) onCommune(code);
        }

        function clearGeometry() {
            request?.abort(); request = null; ++generation;
            if (map && communeGroup) map.removeLayer(communeGroup);
            communeGroup = null; communeLayers.clear();
        }

        function unavailable(message) {
            loadState = 'UNAVAILABLE';
            $('mapStatus').textContent = message + ' Chọn xã/phường trong danh sách ngay dưới bản đồ; không có polygon thay thế.';
        }

        function national() {
            clearGeometry(); viewProvince = ''; loadState = 'NATIONAL';
            $('mapBack').hidden = true; $('mapCommunePanel').hidden = true;
            $('mapBreadcrumb').textContent = 'Việt Nam · 34 tỉnh/thành';
            $('houseMap').setAttribute('aria-label', 'Bản đồ chọn 34 tỉnh/thành Việt Nam');
            $('mapStatus').textContent = map ? 'Click tỉnh/thành để xem xã/phường. Bản đồ dùng để chọn địa phương, không phải lớp giá.'
                : 'Không tải được bản đồ tỉnh. Các ô chọn địa phương vẫn sử dụng được.';
            $('mapCommuneList').replaceChildren();
            if (map && country) {
                country.addTo(map);
                provinceLayers.forEach(({code,layer}) => layer.setStyle(code === selected.province_code
                    ? {...provinceStyle, fillOpacity:.4} : provinceStyle));
                map.setView(nationalCenter,5,{animate:false});
            }
        }

        function validate(data, code) {
            const expected = rows.get(code), seen = new Set();
            if (data.type !== 'FeatureCollection' || data.province_code !== code ||
                data.administrative_version !== admin.administrative_version ||
                data.source_version !== manifest.source_version || data.features?.length !== expected.length) throw Error('Không khớp danh mục');
            for (const f of data.features) {
                const p = f.properties, w = communes.get(p?.commune_code);
                if (f.type !== 'Feature' || f.id !== p.commune_code || p.province_code !== code ||
                    !w || w.province_code !== code || w.commune_name !== p.commune_name || seen.has(f.id)) throw Error('Mã hành chính không hợp lệ');
                seen.add(f.id);
                const g = f.geometry;
                if (!g || !['Polygon','MultiPolygon'].includes(g.type)) throw Error('Không có ranh giới');
                const polygons = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
                if (!polygons.length) throw Error('Ranh giới rỗng');
                for (const polygon of polygons) {
                    if (!polygon.length) throw Error('Ranh giới rỗng');
                    for (const ring of polygon) {
                        if (ring.length < 4 || ring[0][0] !== ring.at(-1)[0] || ring[0][1] !== ring.at(-1)[1] ||
                            ring.some(p => p.length !== 2 || !p.every(Number.isFinite) || p[0] < 100 || p[0] > 120 || p[1] < 7 || p[1] > 25)) throw Error('Hình học không hợp lệ');
                    }
                }
            }
        }

        async function geometry(code, token) {
            const entry = manifest?.provinces?.[code];
            if (sourceState !== 'VERIFIED' || !entry || entry.count !== rows.get(code).length) {
                unavailable('Cấp xã chưa có bản đồ ranh giới xác minh.'); return;
            }
            if (!map) { unavailable('Bản đồ không sẵn sàng.'); return; }
            loadState = 'LOADING'; $('mapStatus').textContent = 'Đang tải ranh giới xã/phường của tỉnh đang xem…';
            try {
                let data = cache.get(code);
                if (data) { cache.delete(code); cache.set(code,data); }
                else {
                    if (entry.url !== `data/vietnam-communes/${code}.geojson`) throw Error('Nguồn chưa xác minh');
                    const controller = new AbortController(); request = controller;
                    const timer = setTimeout(() => controller.abort(), 15000);
                    let response;
                    try {
                        ++geometryRequests;
                        response = await fetch(entry.url, {signal:controller.signal});
                        if (!response.ok) throw Error('Không tải được ranh giới');
                        const bytes = await response.arrayBuffer();
                        if (bytes.byteLength !== entry.bytes) throw Error('Dữ liệu chưa đầy đủ');
                        const digest = await crypto.subtle.digest('SHA-256',bytes);
                        const hash = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,'0')).join('');
                        if (hash !== entry.sha256) throw Error('Ranh giới không khớp snapshot');
                        data = JSON.parse(new TextDecoder().decode(bytes)); validate(data,code);
                    } finally { clearTimeout(timer); }
                    if (token !== generation) return;
                    cache.set(code,data);
                    if (cache.size > 3) cache.delete(cache.keys().next().value);
                }
                if (token !== generation || code !== viewProvince) return;
                const start = performance.now();
                const group = L.geoJSON(data, {style:communeStyle, smoothFactor:1,
                    onEachFeature:(f,layer) => {
                        const key = f.properties.commune_code, w = communes.get(key);
                        const tooltip = document.createElement('span');
                        tooltip.textContent = `${w.commune_name}, ${provinces.get(code).province_name}`;
                        layer.bindTooltip(tooltip, {sticky:true});
                        layer.on('mouseover', () => layer.setStyle({...selectedStyle,fillOpacity:.35}));
                        layer.on('mouseout', () => layer.setStyle(key === selected.commune_code ? selectedStyle : communeStyle));
                        layer.on('click', () => chooseCommune(key)); communeLayers.set(key,layer);
                    }});
                communeGroup = group; group.addTo(map);
                lastRenderMs = performance.now()-start; loadState = 'READY'; request = null;
                $('mapStatus').textContent = `${rows.get(code).length} ranh giới xã/phường sau sáp nhập 2025 · Di chuột để xem tên, click để chọn.`;
                updateSelection();
            } catch (e) {
                if (token !== generation) return;
                if (communeGroup) map.removeLayer(communeGroup);
                communeGroup = null; communeLayers.clear();
                unavailable('Không tải/kiểm tra được ranh giới xã/phường xác minh của tỉnh này.');
            }
        }

        function province(code) {
            clearGeometry(); viewProvince = code;
            $('mapBack').hidden = false; $('mapCommunePanel').hidden = false;
            $('mapBreadcrumb').textContent = 'Việt Nam → ' + provinces.get(code).province_name;
            $('houseMap').setAttribute('aria-label', `Bản đồ xã/phường ${provinces.get(code).province_name}`);
            $('mapCommuneTitle').textContent = 'Xã/phường · ' + provinces.get(code).province_name;
            $('mapCommuneSearch').value = ''; renderList();
            if (map && country) {
                map.removeLayer(country);
                for (const item of provinceLayers) {
                    map.removeLayer(item.layer);
                    if (item.code === code) {
                        item.layer.setStyle({...provinceStyle,fillOpacity:.08}); item.layer.addTo(map);
                        map.fitBounds(item.layer.getBounds(), {padding:[20,20],maxZoom:8,animate:false});
                    }
                }
            }
            // Catch all failures internally; rapid province changes cannot render stale data.
            void geometry(code,generation);
        }

        function sync(next) {
            const p = provinces.get(next.province_code);
            const w = communes.get(next.commune_code);
            const valid = {province_code:p?.province_code || '', commune_code:w && p && w.province_code === p.province_code ? w.commune_code : ''};
            if (valid.province_code === selected.province_code && valid.commune_code === selected.commune_code && viewProvince === valid.province_code) return;
            selected = valid;
            if (!p) national();
            else if (viewProvince !== p.province_code) province(p.province_code);
            updateSelection();
        }

        $('mapBack').addEventListener('click', national);
        $('mapCommuneSearch').addEventListener('input', renderList);
        const ready = (async () => {
            const [geo, source] = await Promise.allSettled([json('data/vietnam-provinces.geojson'),json('data/vietnam-commune-map-source.json')]);
            if (source.status === 'fulfilled' && source.value.status === 'VERIFIED' &&
                source.value.administrative_version === admin.administrative_version && source.value.commune_count === 3321 &&
                source.value.boundary_epoch === 'post-reform-2025-07-01' && source.value.license === 'CC BY 4.0') {
                manifest = source.value; sourceState = 'VERIFIED';
            }
            if (window.L && geo.status === 'fulfilled') {
                try {
                    map = L.map('houseMap',{scrollWheelZoom:false,preferCanvas:true}).setView(nationalCenter,5);
                    tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
                        maxZoom:18, attribution:'© OpenStreetMap contributors'});
                    tileLayer.on('tileload',()=>{++tilesLoaded;tileErrors=0;});
                    tileLayer.on('tileerror',()=>{++tileErrors;});
                    tileLayer.addTo(map);
                    country = L.geoJSON(geo.value,{style:provinceStyle,onEachFeature:(f,layer) => {
                        const code = f.properties.province_code, p = provinces.get(code);
                        if (!p) return;
                        const label = document.createElement('span'); label.textContent = p.province_name;
                        layer.bindTooltip(label);
                        layer.on('click', () => onProvince(code)); provinceLayers.push({code,layer});
                    }});
                } catch (_) { map = null; }
            }
            national(); selected = {province_code:'',commune_code:''}; sync(context()); return !!map;
        })();
        return Object.freeze({ready,sync,getMap:()=>map,getProvinceLayers:()=>provinceLayers,
            getTileLayer:()=>tileLayer,getTileStatus:()=>({loaded:tilesLoaded,errors:tileErrors}),
            getCommuneLayers:()=>Array.from(communeLayers,([code,layer])=>({code,layer})),
            getState:()=>({view:viewProvince?'PROVINCE':'NATIONAL',province_code:viewProvince,
                selected:{...selected},source:sourceState,load:loadState,polygon_count:communeLayers.size,
                cache_codes:[...cache.keys()],geometry_requests:geometryRequests,last_render_ms:lastRenderMs})});
    }
    window.VietnamCommuneMap = Object.freeze({create});
})();
