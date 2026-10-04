"use strict";
(() => {
    const $=id=>document.getElementById(id),api=window.VietnamHouse,form=$('houseForm');
    let model,index,stats,coordinates,original,scenario,map,markers=[],pendingSearch=false,searchMatches=[],searchActive=-1,geoData,tileLayer,tilesLoaded=0,tileErrors=0;
    const pendingCombos=new Set(),provinceLayers=new Map(),combos={};
    const text=(id,value)=>{const el=$(id);if(el)el.textContent=value;};
    const node=(tag,value)=>{const el=document.createElement(tag);if(value!==undefined)el.textContent=value;return el;};
    const input=()=>({province:$('houseProvince').value,ward:$('houseWard').value,sub_area:$('houseSubArea').value,property_type:$('housePropertyType').value,area_m2:Number(form.elements.area_m2.value)});
    const locationText=l=>[l.sub_area,l.ward,l.province,l.region].filter(Boolean).join(', ');
    function clear(){original=null;scenario=null;$('houseResult').hidden=true;$('houseExploration').hidden=true;$('houseEmptyResult').hidden=false;$('houseInputError').hidden=true;window.dispatchEvent(new Event('portfolio:houseclear'));}
    function choices(select,items,placeholder,value=''){select.replaceChildren(new Option(placeholder,''));for(const r of items)select.append(new Option(r.label||r.name,r.id));select.value=items.some(r=>r.id===value)?value:'';}
    function wards(value=''){choices($('houseWard'),index.wards.filter(w=>w.province===$('houseProvince').value),'Toàn tỉnh / thành phố',value);subareas();}
    function subareas(value=''){
        $('houseSubArea').value=value;
        const items=index.sub_areas.filter(s=>s.ward===$('houseWard').value),types=new Set(items.map(s=>s.type));
        text('houseSubAreaLabel',items.length&&[...types].every(t=>['PROJECT','BUILDING'].includes(t))?'Dự án / Chung cư / Tòa nhà (không bắt buộc)':'Khu vực chi tiết (không bắt buộc)');
    }
    function setupCombo(name,inputId,listId,items,commit,allowText=false){
        const field=$(inputId),list=$(listId);let matches=[],active=-1;
        const close=()=>{list.hidden=true;field.setAttribute('aria-expanded','false');field.removeAttribute('aria-activedescendant');};
        function render(){const q=api.searchFold(field.value);active=-1;field.removeAttribute('aria-activedescendant');matches=items().filter(r=>api.searchFold(r.label||r.name).includes(q)).slice(0,30);list.replaceChildren();
            if(name==='ward'&&!q){const b=node('button','Toàn tỉnh / thành phố');b.type='button';b.addEventListener('click',()=>choose(null));list.append(b);}
            for(const [i,r] of matches.entries()){const b=node('button',r.label||r.name);b.type='button';b.id=listId+'Option'+i;b.setAttribute('role','option');b.addEventListener('mousedown',e=>e.preventDefault());b.addEventListener('click',()=>choose(r));list.append(b);}
            if(!matches.length)list.append(node('p',allowText?'Tên này sẽ được lưu như khu vực nhập tay; giá dùng cấp cao hơn.':'Không có địa điểm trong danh mục.'));
            list.hidden=false;field.setAttribute('aria-expanded','true');}
        function choose(r){pendingCombos.delete(name);field.value=r?(r.label||r.name):'';close();commit(r);}
        field.addEventListener('focus',render);field.addEventListener('input',()=>{clear();if(!allowText)pendingCombos.add(name);render();$('houseWardError').hidden=!pendingCombos.has('ward');update();});
        field.addEventListener('keydown',e=>{if(e.key==='Escape'){close();return;}if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();if(list.hidden)render();if(matches.length){active=(active+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;field.setAttribute('aria-activedescendant',listId+'Option'+active);[...list.querySelectorAll('[role=option]')].forEach((b,i)=>b.setAttribute('aria-selected',String(i===active)));}}else if(e.key==='Enter'&&!list.hidden){e.preventDefault();if(active>=0)choose(matches[active]);}});
        field.addEventListener('blur',()=>setTimeout(close,150));combos[name]={close,sync(value){field.value=value;pendingCombos.delete(name);close();}};
    }
    function syncCombos(){combos.province?.sync(index.provinces.find(p=>p.id===$('houseProvince').value)?.label||'');combos.ward?.sync(index.wards.find(w=>w.id===$('houseWard').value)?.name||'');$('houseWardSearch').disabled=!$('houseProvince').value;$('houseWardError').hidden=true;}
    function resetSearch(){pendingSearch=false;$('houseAreaSearch').value='';$('houseAreaSearch').removeAttribute('aria-activedescendant');$('houseSearchResults').replaceChildren();$('houseSearchResults').hidden=true;$('houseAreaSearch').setAttribute('aria-expanded','false');text('houseSearchHint','Tìm trong danh sách rồi chọn kết quả; không dùng địa chỉ tự nhập.');}
    function selectLocation(record){if(!record)return;clear();resetSearch();$('houseProvince').value=record.province||record.id;wards(record.level==='WARD'?record.id:record.ward||'');if(record.level==='SUB_AREA')subareas(record.name);syncCombos();update();}
    function search(){
        clear();const q=api.searchFold($('houseAreaSearch').value);pendingSearch=Boolean(q);searchActive=-1;$('houseAreaSearch').removeAttribute('aria-activedescendant');
        text('houseSearchHint',q?'Vui lòng chọn địa điểm từ danh sách.':'Tìm trong danh sách rồi chọn kết quả; không dùng địa chỉ tự nhập.');
        searchMatches=q?[...index.provinces,...index.wards,...index.sub_areas].filter(r=>api.searchFold([r.name,r.province].filter(Boolean).join(' ')).includes(q)).slice(0,30):[];
        const list=$('houseSearchResults');list.replaceChildren();list.hidden=!q;$('houseAreaSearch').setAttribute('aria-expanded',String(Boolean(q)));
        for(const [i,r] of searchMatches.entries()){const button=node('button',(r.label||r.name)+(r.level==='PROVINCE'?'':' · '+r.province));button.type='button';button.id='houseSearchOption'+i;button.setAttribute('role','option');button.addEventListener('click',()=>selectLocation(r));list.append(button);}
        if(q&&!searchMatches.length)list.append(node('p','Không có địa điểm trong dữ liệu.'));
        update();
    }
    function update(){
        if(!model)return;
        const point=input(),r=api.resolve(stats,index,{...point,area_m2:undefined});
        $('houseEstimate').disabled=pendingSearch||pendingCombos.size>0||!r.available;
        const message=!r.available?(r.reason==='insufficient_data'?'Chưa đủ mẫu ở tỉnh này.':r.reason==='unsupported_property_type'?'Loại bất động sản chưa đủ dữ liệu xác minh.':'Chọn địa điểm từ danh sách.'):
            `${r.sample_count.toLocaleString('vi-VN')} mẫu · ${r.coverage} · ${r.resolution_level} · ${locationText(r.used_location)}${r.fallback?' · '+fallbackText(r):''}`;
        text('houseCoverageHint',message);text('houseTrainingContext',message);
        text('houseStaticMarket',r.available?`Median ${api.formatPrice(r.median_price_per_m2,1)}/m² · P25–P75 ${api.formatPrice(r.p25_price_per_m2,1)} – ${api.formatPrice(r.p75_price_per_m2,1)}/m² · Ngày dữ liệu ${r.latest_date}`:'Chưa đủ dữ liệu đã xác minh.');
        syncMap();browse();
    }
    function fallbackText(r){return r.resolution_level==='REGIONAL_ESTIMATE'?'Ước lượng từ '+r.donors.map(d=>d.province).join(', ')+'; cùng loại BĐS, cân bằng số mẫu và khoảng cách.':r.resolution_level==='PROVINCE'?'Ước lượng được tính từ dữ liệu cấp Tỉnh/Thành phố của cùng loại bất động sản.':'Đây là giá ước lượng dựa trên dữ liệu cấp Phường/Xã.';}
    function scenarioUpdate(){if(!original)return;scenario=null;$('houseApplyScenario').disabled=true;$('scenarioError').hidden=true;try{const point={...original.input,area_m2:Number($('scenarioArea').value)},r=api.predict(model,point);scenario={input:point,prediction:r};text('scenarioPrice',api.formatPrice(r.total_price_vnd));text('scenarioDelta',api.formatPrice(r.total_price_vnd-original.prediction.total_price_vnd));$('houseApplyScenario').disabled=false;}catch(e){text('scenarioError',e.message);$('scenarioError').hidden=false;}}
    function estimate(event){event?.preventDefault();clear();if(pendingSearch||pendingCombos.size){text('houseInputError','Vui lòng chọn Phường/Xã từ danh sách.');$('houseInputError').hidden=false;return;}try{
        if(!form.reportValidity())return;const point=input(),r=api.predict(model,point);original={input:point,prediction:r};
        text('housePrice',api.formatPrice(r.total_price_vnd));text('housePerM2','Giá tham khảo/m²: '+api.formatPrice(r.price_per_m2_vnd,1)+'/m²');
        text('houseP25','P25: '+api.formatPrice(r.p25_estimated_price_vnd));text('houseMedian','Median: '+api.formatPrice(r.total_price_vnd));text('houseP75','P75: '+api.formatPrice(r.p75_estimated_price_vnd));
        text('houseResultCoverage',`${r.coverage} · ${r.sample_count.toLocaleString('vi-VN')} mẫu`);text('houseResolution',r.resolution_level);
        text('houseUsedLocation','Vị trí sử dụng: '+locationText(r.used_location));text('houseSelectedLocation','Vị trí đã chọn: '+locationText(r.selected_location));
        text('houseResultType','Loại: '+r.property_type_label);text('houseLatestDate','Dữ liệu mới nhất: '+r.latest_date);
        text('houseEstimateBadge',({SUB_AREA:'Dữ liệu trực tiếp khu vực',WARD:'Ước lượng từ Phường/Xã',PROVINCE:'Ước lượng từ Tỉnh/Thành phố',REGIONAL_ESTIMATE:'Ước lượng khu vực lân cận'})[r.resolution_level]);
        const warn=r.fallback||r.resolution_level==='REGIONAL_ESTIMATE';$('houseEstimateWarning').hidden=!warn;
        text('houseEstimateWarning',r.resolution_level==='REGIONAL_ESTIMATE'?'⚠ Khu vực này hiện có rất ít dữ liệu. Giá dưới đây là ước lượng tham khảo từ các khu vực có dữ liệu tương đồng.':r.resolution_level==='WARD'?'⚠ Chưa có dữ liệu giá chính xác tại khu vực chi tiết này. Đây là giá ước lượng dựa trên dữ liệu cấp Phường/Xã.':'⚠ Chưa có dữ liệu giá chính xác tại khu vực này. Đây là giá ước lượng.');
        text('housePredictionNote',r.fallback?fallbackText(r):`Ước tính dựa trên dữ liệu cấp ${r.resolution_level==='SUB_AREA'?'Dự án / khu vực chi tiết':r.resolution_level==='WARD'?'Phường/Xã':'Tỉnh/Thành phố'}.`);
        $('houseResult').hidden=false;$('houseEmptyResult').hidden=true;$('houseExploration').hidden=false;
        $('houseContributions').replaceChildren(...[locationText(r.used_location),r.sample_count+' mẫu · '+r.coverage,'Median giá/m² × '+point.area_m2+' m²'].map(v=>node('li',v)));
        text('houseReference','Công thức thống kê; không phải mô hình Machine Learning.');$('scenarioArea').value=point.area_m2;text('scenarioOriginal',api.formatPrice(r.total_price_vnd));scenarioUpdate();
        const metadata={selected_location:r.selected_location,used_location:r.used_location,ward:r.ward,sub_area:r.sub_area,property_type:r.property_type,
            resolution_level:r.resolution_level,sample_count:r.sample_count,coverage:r.coverage,estimate_method:r.estimate_method,data_latest_date:r.latest_date,
            stat_key:r.stat_key,fallback_reason:r.fallback_reason,p25_price_vnd:r.p25_estimated_price_vnd,p75_price_vnd:r.p75_estimated_price_vnd,
            selected_province:r.selected_location.province,selected_ward:r.selected_location.ward,selected_sub_area:r.selected_location.sub_area,area_m2:point.area_m2,
            estimated_price_vnd:r.total_price_vnd,median_price_per_m2:r.median_price_per_m2,stats_location_used:r.used_location,latest_data_date:r.latest_date,sub_area_input_kind:r.sub_area_input_kind,donors:r.donors||[]};
        window.dispatchEvent(new CustomEvent('portfolio:houseprediction',{detail:{predicted_price_vnd:r.total_price_vnd,predicted_price_per_m2:r.price_per_m2_vnd,province:point.province,
            area_name:[r.selected_location.sub_area,r.selected_location.ward].filter(Boolean).join(', ').slice(0,100)||null,property_type:r.property_type_label,model_version:model.model_version,input_data:point,metadata}}));
    }catch(e){text('houseInputError',e.message);$('houseInputError').hidden=false;}}
    function browse(){
        const point={province:$('houseBrowseProvince').value||input().province,property_type:$('houseBrowseType').value||input().property_type},filter=$('houseBrowseFilter').value;
        let rows=stats.stats.filter(s=>s.province===point.province&&s.property_type===point.property_type&&s.resolution_level==='WARD');
        const labels=r=>{const l=(r.sub_area?index.sub_areas:index.wards).find(x=>x.id===(r.sub_area||r.ward));return l?.label||l?.name||r.province;};
        rows=rows.filter(r=>!filter||api.searchFold(labels(r)).includes(api.searchFold(filter))).sort((a,b)=>$('houseBrowseSort').value==='price'?b.median_price_per_m2-a.median_price_per_m2:b.sample_count-a.sample_count);
        $('houseBrowseRows').replaceChildren();for(const r of rows.slice(0,100)){const tr=node('tr');for(const v of [labels(r),index.property_types.find(t=>t.code===r.property_type)?.label,api.formatPrice(r.median_price_per_m2,1)+'/m²',String(r.sample_count),r.coverage,r.latest_date.slice(0,10)])tr.append(node('td',v));const button=node('button','Chọn');button.type='button';button.addEventListener('click',()=>{$('housePropertyType').value=r.property_type;selectLocation(index.wards.find(x=>x.id===r.ward));renderMap();});const td=node('td');td.append(button);tr.append(td);$('houseBrowseRows').append(tr);}
        text('houseBrowseCount',rows.length+' nhóm Phường/Xã · hiển thị tối đa 100. '+(!rows.length?'Chưa có statistic xã/phường đã mapping ở tỉnh và loại này; form vẫn có thể dùng tỉnh hoặc ước lượng khu vực.':''));
    }
    function syncMap(){if(!map)return;const selected=$('houseProvince').value;
        provinceLayers.forEach((layer,name)=>layer.setStyle({weight:name===selected?3:1,color:name===selected?'#f4eb95':'#193e54'}));
        const layer=provinceLayers.get(selected);if(layer){map.fitBounds(layer.getBounds(),{padding:[14,14],animate:false,maxZoom:9});text('houseMapSelection','Đang chọn '+selected+'. Chỉ hiển thị ranh giới cấp tỉnh; chọn xã/phường và khu vực chi tiết bằng danh sách.');}
        else if(provinceLayers.size){map.fitBounds(window.L.featureGroup([...provinceLayers.values()]).getBounds(),{padding:[12,12],animate:false});text('houseMapSelection','Chọn một tỉnh trên bản đồ hoặc tìm trong danh sách địa điểm.');}
    }
    function tileStatus(){const online=tilesLoaded>0&&tileErrors===0;text('houseMapStatus',online?'Nền OpenStreetMap đã tải. Ranh giới tỉnh có sẵn tại thiết bị.':'Nền bản đồ trực tuyến chưa tải được. Bạn vẫn có thể chọn địa điểm bằng danh sách.');}
    function renderMap(){if(!map||!geoData)return;provinceLayers.forEach(l=>l.remove());provinceLayers.clear();
        const colors=['#4698bf','#49b6aa','#acb861','#e2a459','#db7274'],bins=[30,50,80,120];
        for(const feature of geoData.features){const province=index.provinces.find(p=>p.code===String(feature.properties.province_code));if(!province)continue;
            const r=api.resolve(stats,index,{province:province.id,property_type:$('housePropertyType').value}),ppm=r.median_price_per_m2/1e6,color=r.available?colors[bins.filter(x=>ppm>=x).length]:'#728195',popup=node('div');
            for(const value of [province.label,index.property_types.find(t=>t.code===$('housePropertyType').value)?.label,r.available?api.formatPrice(r.median_price_per_m2,1)+'/m²':'Chưa đủ dữ liệu cùng loại',r.available?r.sample_count+' mẫu · '+r.coverage:'',r.available?'Ngày tin mới nhất: '+r.latest_date.slice(0,10):'',r.resolution_level==='REGIONAL_ESTIMATE'?'Ước lượng từ tỉnh lân cận; không phải giá trực tiếp trong tỉnh.':''])if(value)popup.append(node('p',value));
            const layer=window.L.geoJSON(feature,{style:{weight:1,color:'#193e54',fillColor:color,fillOpacity:.6}}).addTo(map).bindPopup(popup);
            layer.on('click',()=>selectLocation(province));provinceLayers.set(province.id,layer);
        }
    }
    async function initMap(){if(!window.L){text('houseMapStatus','Không tải được bản đồ. Bạn vẫn có thể chọn vị trí từ danh sách.');return;}
        try{geoData=await fetch('./data/vietnam-provinces.geojson').then(r=>{if(!r.ok)throw Error('map');return r.json();});}catch{text('houseMapStatus','Chưa tải được ranh giới tỉnh. Danh sách địa điểm vẫn hoạt động.');return;}
        map=window.L.map('houseMap',{scrollWheelZoom:false}).setView([16,106],5);
        tileLayer=window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Ranh giới minh họa: bando.com.vn, bản dẫn xuất MIT'});
        tileLayer.on('tileload',()=>{tilesLoaded++;tileErrors=0;tileStatus();});tileLayer.on('tileerror',()=>{tileErrors++;tileStatus();});tileLayer.addTo(map);
        renderMap();syncMap();tileStatus();requestAnimationFrame(()=>map.invalidateSize());new ResizeObserver(()=>map.invalidateSize({pan:false})).observe($('houseMap'));
    }
    async function load(){try{
        const responses=await Promise.all(['./vietnam-house-model.json','./data/vietnam-location-index.json','./data/vietnam-market-stats.json'].map(p=>fetch(p).then(r=>{if(!r.ok)throw Error('data');return r.json();})));
        [model,index,stats]=responses;api.validateModel(model);if(index.schema_version!==3||stats.schema_version!==3)throw Error('schema');
        model.statistics_data=stats;model.location_data=index;
        choices($('houseProvince'),index.provinces,'Chọn tỉnh / thành phố');
        choices($('houseBrowseProvince'),index.provinces,'Theo tỉnh đang chọn');
        for(const t of index.property_types){const option=new Option(t.label+(t.status==='DISABLED'?' — chưa đủ dữ liệu xác minh':''),t.code);option.disabled=t.status!=='ENABLED';$('housePropertyType').append(option);}
        choices($('houseBrowseType'),index.property_types.filter(t=>t.status==='ENABLED').map(t=>({id:t.code,label:t.label})),'Theo loại đang chọn');
        setupCombo('province','houseProvinceSearch','houseProvinceSuggestions',()=>index.provinces,r=>selectLocation(r));
        setupCombo('ward','houseWardSearch','houseWardSuggestions',()=>index.wards.filter(w=>w.province===$('houseProvince').value),r=>{clear();resetSearch();$('houseWard').value=r?.id||'';subareas();syncCombos();update();});
        setupCombo('sub','houseSubArea','houseSubSuggestions',()=>index.sub_areas.filter(s=>s.ward===$('houseWard').value),()=>{clear();resetSearch();update();},true);
        syncCombos();
        text('houseDataPeriod',model.data_date_info.display);text('houseModelInfo','Median giá/m² · '+model.model_version);
        const counts=stats.summary;text('housePublicCoverage',`${stats.verified_rows.toLocaleString('vi-VN')} listing đã lọc · ${counts.enabled_types} loại BĐS bật · ${counts.supported_provinces} tỉnh có listing · ${index.provinces.length} tỉnh/thành và ${index.wards.length.toLocaleString('vi-VN')} xã/phường hợp lệ · ${counts.direct_wards} xã/phường có dữ liệu đã mapping · ${index.sub_areas.length} dự án theo ward · ${counts.eligible_sub_area_stats} nhóm chi tiết đủ mẫu.`);
        for(const t of index.property_types.filter(t=>t.status==='DISABLED'))$('houseTypeLimitations').append(node('li',t.label+': '+t.reason));
        text('houseStatus','VERIFIED MARKET ESTIMATE BETA · thống kê giá rao bán · không phải Machine Learning.');
        for(const [k,v] of [['Nguồn','TiniX AI · CC BY-NC 4.0'],['Dữ liệu',model.data_date_info.display],['Đã xác minh',stats.verified_rows.toLocaleString('vi-VN')],['Ngưỡng mẫu','Dự án 20 · Phường/Xã 30 · Tỉnh 80']]){const row=node('div');row.append(node('dt',k),node('dd',v));$('houseSourceFacts').append(row);}
        model.limitations.forEach(v=>$('houseLimitations').append(node('li',v)));
        model.samples.forEach((s,i)=>{const card=node('article');card.className='house-sample';card.append(node('strong',s.input.province+' · '+index.property_types.find(t=>t.code===s.input.property_type).label),node('p','Giá rao trong nguồn: '+api.formatPrice(s.listed_price_vnd)));const b=node('button','Điền mẫu '+(i+1));b.type='button';b.className='house-secondary';b.dataset.houseSample=i;b.addEventListener('click',()=>{const p=s.input;$('housePropertyType').value=p.property_type;selectLocation(p.sub_area?index.sub_areas.find(x=>x.id===p.sub_area):p.ward?index.wards.find(x=>x.id===p.ward):index.provinces.find(x=>x.id===p.province));form.elements.area_m2.value=p.area_m2;renderMap();update();});card.append(b);$('houseSamples').append(card);});
        $('houseFields').disabled=false;update();await initMap();
    }catch(e){model=null;$('houseFields').disabled=true;text('houseStatus','Không tải được thống kê. Hãy mở bằng HTTP / Live Server và kiểm tra các file dữ liệu.');}}
    form.addEventListener('submit',estimate);form.addEventListener('input',e=>{if(e.target.id!=='houseAreaSearch')clear();});
    form.addEventListener('reset',()=>{clear();setTimeout(()=>{pendingCombos.clear();resetSearch();wards();syncCombos();renderMap();update();},0);});
    $('houseProvince').addEventListener('change',()=>{clear();resetSearch();wards();syncCombos();update();});$('houseWard').addEventListener('change',()=>{clear();resetSearch();subareas();syncCombos();update();});
    $('houseSubArea').addEventListener('change',()=>{clear();resetSearch();update();});$('housePropertyType').addEventListener('change',()=>{clear();renderMap();subareas();update();});
    $('houseAreaSearch').addEventListener('input',search);$('houseAreaSearch').addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();resetSearch();update();}else if(['ArrowDown','ArrowUp'].includes(e.key)&&searchMatches.length){e.preventDefault();searchActive=(searchActive+(e.key==='ArrowDown'?1:-1)+searchMatches.length)%searchMatches.length;$('houseAreaSearch').setAttribute('aria-activedescendant','houseSearchOption'+searchActive);[...$('houseSearchResults').querySelectorAll('button')].forEach((b,i)=>b.setAttribute('aria-selected',String(i===searchActive)));}else if(e.key==='Enter'&&pendingSearch){e.preventDefault();if(searchActive>=0)selectLocation(searchMatches[searchActive]);}});
    $('houseBrowseFilter').addEventListener('input',browse);$('houseBrowseSort').addEventListener('change',browse);
    $('houseBrowseProvince').addEventListener('change',browse);$('houseBrowseType').addEventListener('change',browse);
    $('houseScenarioFields').addEventListener('input',scenarioUpdate);$('houseApplyScenario').addEventListener('click',()=>{if(scenario){form.elements.area_m2.value=scenario.input.area_m2;form.requestSubmit();}});
    window.HousePage=Object.freeze({ready:load(),getModel:()=>model,getMap:()=>map,getProvinceLayers:()=>provinceLayers,getTileLayer:()=>tileLayer,getTileStatus:()=>({loaded:tilesLoaded,errors:tileErrors})});
})();
