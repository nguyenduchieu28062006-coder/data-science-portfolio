/* Canonical location validation and type-isolated asking-price resolution. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.VietnamHouse=api;})(typeof window==='object'?window:globalThis,function(){
    'use strict';
    const normalize=v=>typeof v==='string'?v.normalize('NFC').trim().replace(/\s+/gu,' ').toLocaleLowerCase('vi-VN'):'';
    const searchFold=v=>normalize(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
    const fields=['province','ward','sub_area','property_type','area_m2'],cache=new WeakMap();
    function exact(list,value,keys){const matches=list.filter(r=>keys.some(k=>normalize(r[k])===normalize(value)));return matches.length===1?matches[0]:null;}
    function validRow(row,minimum){return row&&Number.isInteger(row.sample_count)&&row.sample_count>=minimum&&['median_price_per_m2','p25_price_per_m2','p75_price_per_m2'].every(k=>Number.isFinite(row[k])&&row[k]>0)&&row.p25_price_per_m2<=row.median_price_per_m2&&row.median_price_per_m2<=row.p75_price_per_m2&&Number.isFinite(Date.parse(row.latest_date));}
    function resolve(data,index,input){
        let location_valid=false;
        const no=reason=>({available:false,location_valid,resolution_level:'NONE',reason,live_connected:false});
        if(data?.schema_version!==3||index?.schema_version!==3||!Array.isArray(data.stats)||!Array.isArray(index.provinces)||!Array.isArray(index.wards))return no('unavailable');
        if(!input||['province','ward','sub_area','property_type'].some(k=>typeof(input[k]??'')!=='string'||(input[k]??'').length>200||/[\u0000-\u001f]/.test(input[k]??'')))return no('invalid_parameters');
        if(input.area||input.area_name)return no('unknown_location');
        const province=exact(index.provinces,input.province,['id','name','label','code']);
        if(!province)return no('unknown_location');
        const ward=input.ward?exact(index.wards.filter(w=>w.province===province.id),input.ward,['id','name','code']):null;
        if(input.ward&&!ward)return no('unknown_location');
        location_valid=true;
        const type=exact(index.property_types,input.property_type,['code','label']);
        if(!type||type.status!=='ENABLED')return no('unsupported_property_type');
        const area=input.area_m2;
        if(area!==undefined&&(typeof area!=='number'||!Number.isFinite(area)||area<15||area>1500))return no('invalid_area');
        const typed=(input.sub_area||'').normalize('NFC').trim();
        const sub=typed&&ward?exact(index.sub_areas.filter(s=>s.ward===ward.id),typed,['id','name']):null;
        // Free text is allowed only at optional sub-area level. It never creates
        // a location ID or an exact statistic; it survives for display/history.
        const selected={province:province.name,ward:ward?.name||'',sub_area:sub?.name||typed};
        if(!cache.has(data))cache.set(data,{direct:new Map(data.stats.map(r=>[r.stat_key,r])),regional:new Map((data.regional_stats||[]).map(r=>[[r.province,r.property_type].join('|'),r]))});
        const lookup=cache.get(data),levels=[];
        if(sub)levels.push(['SUB_AREA',ward.id,sub.id]);
        if(ward)levels.push(['WARD',ward.id,'']);
        levels.push(['PROVINCE','','']);
        let row,missing=[];
        if(typed&&!sub)missing.push('no_sub_area_market_data');
        for(const [level,w,s] of levels){
            const candidate=lookup.direct.get([province.id,w,s,type.code].join('|'));
            if(candidate&&candidate.sample_count>=data.thresholds[level]){if(!validRow(candidate,data.thresholds[level]))return no('unavailable');row=candidate;break;}
            if(level!=='PROVINCE')missing.push(candidate?'insufficient_'+level.toLowerCase()+'_samples':'no_'+level.toLowerCase()+'_market_data');
        }
        if(!row){
            const candidate=lookup.regional.get([province.id,type.code].join('|'));
            if(candidate){if(!validRow(candidate,80)||!Array.isArray(candidate.donors)||!candidate.donors.length)return no('unavailable');row=candidate;missing.push('insufficient_province_market_data');}
        }
        if(!row)return no('insufficient_data');
        const usedWard=row.ward?index.wards.find(w=>w.id===row.ward):null,usedSub=row.sub_area?index.sub_areas.find(s=>s.id===row.sub_area):null;
        const used_location={province:row.resolution_level==='REGIONAL_ESTIMATE'?'':province.name,ward:usedWard?.name||'',sub_area:usedSub?.name||''};
        if(row.resolution_level==='REGIONAL_ESTIMATE')used_location.region=row.donors.map(d=>d.province).join(', ');
        const requested=typed?'SUB_AREA':ward?'WARD':'PROVINCE',fallback=requested!==row.resolution_level;
        const response={...row,available:true,location_valid:true,property_type_label:type.label,selected_location:selected,used_location,stats_location:used_location,
            sub_area_input_kind:sub?'KNOWN':typed?'TYPED':'NONE',live_connected:false,estimate_method:row.resolution_level==='REGIONAL_ESTIMATE'?'nearby_provinces_balanced_distance_weighted_quantiles_times_area':'median_price_per_m2_times_area',
            fallback,fallback_reason:fallback?[...new Set(missing)].join(';')||'coarser_statistic':null};
        if(area!==undefined)Object.assign(response,{estimated_price_vnd:area*row.median_price_per_m2,p25_estimated_price_vnd:area*row.p25_price_per_m2,p75_estimated_price_vnd:area*row.p75_price_per_m2});
        return response;
    }
    function validateModel(m){if(m?.schema_version!==5||m.mode!=='VERIFIED MARKET ESTIMATE BETA'||m.model_review?.public_status!=='READY'||m.regressor?.kind!=='market_median'||m.metrics!==null)throw Error('Thống kê BETA không hợp lệ.');return m;}
    function predict(m,input){if(typeof input?.area_m2!=='number'||!Number.isFinite(input.area_m2))throw Error('Diện tích phải trong khoảng 15–1500 m².');const r=resolve(m.statistics_data,m.location_data,input);if(!r.available)throw Error(({unknown_location:'Vui lòng chọn Phường/Xã từ danh sách.',insufficient_data:'Chưa có dữ liệu cùng loại BĐS để ước lượng hợp lý.',unsupported_property_type:'Loại bất động sản chưa đủ dữ liệu xác minh.',invalid_area:'Diện tích phải trong khoảng 15–1500 m².'})[r.reason]||'Không tải được thống kê.');return {...r,total_price_vnd:r.estimated_price_vnd,price_per_m2_vnd:r.median_price_per_m2};}
    function formatPrice(value,digits=2){if(!Number.isFinite(value))return '—';const divisor=Math.abs(value)>=1e9?1e9:1e6;return new Intl.NumberFormat('vi-VN',{maximumFractionDigits:digits}).format(value/divisor)+(divisor===1e9?' tỷ VNĐ':' triệu VNĐ');}
    return Object.freeze({normalize,searchFold,resolve,validateModel,predict,formatPrice,fields});
});
