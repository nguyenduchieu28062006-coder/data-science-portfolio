"use strict";
(() => {
    const $ = id => document.getElementById(id), api = window.VietnamHouse;
    const form = $('houseForm');
    let model = null, original = null, scenario = null, marketRequest = 0;
    function text(id,value) { $(id).textContent = value; }
    function node(tag,value,className) { const n=document.createElement(tag); if(value!==undefined)n.textContent=value; if(className)n.className=className; return n; }
    function numberValue(field) { return field.value === '' ? null : Number(field.value); }
    function inputFromForm() {
        return {province:form.elements.province.value,area_name:form.elements.area_name.value,
            property_type:form.elements.property_type.value,area_m2:numberValue(form.elements.area_m2)};
    }
    function displayedPrice(value,cov) {
        // Avoid apparent precision for sparse/coarse geographic estimates.
        return api.formatPrice(cov && (cov.fallback || cov.level==='LOW') ? Math.round(value/1e8)*1e8 : value);
    }
    function areas() {
        const province=model?.coverage.find(p=>p.name===$('houseProvince').value), search=$('houseAreaSearch').value.trim().toLocaleLowerCase('vi-VN');
        const previous=$('houseArea').value;
        $('houseArea').replaceChildren(new Option('Ước lượng cấp tỉnh',''));
        province?.areas.filter(a=>a.name.toLocaleLowerCase('vi-VN').includes(search)).forEach(a=>{
            const option=new Option(`${a.name} · ${a.sample_count} mẫu${a.supported ? '' : ' · dùng cấp tỉnh'}`,a.name);
            $('houseArea').append(option);
        });
        if([...$('houseArea').options].some(o=>o.value===previous))$('houseArea').value=previous;
        updateCoverage();
    }
    function updateCoverage() {
        if(!model)return;
        const input=inputFromForm(), cov=api.coverageFor(model,input);
        if(!cov.province){++marketRequest;text('houseCoverageHint','Chọn địa phương để xem độ phủ dữ liệu.');text('houseTrainingContext','Chọn khu vực để xem thống kê đã xác minh.');text('houseStaticMarket','Chọn khu vực và loại tài sản để xem thống kê.');return;}
        if(!cov.province.supported)text('houseCoverageHint',`Chưa có đủ dữ liệu cho khu vực này. Tỉnh có ${cov.province.sample_count} mẫu đã xác minh; cần ít nhất 80.`);
        else text('houseCoverageHint',`${cov.count.toLocaleString('vi-VN')} mẫu đã xác minh · ${cov.level}${cov.fallback ? ' · Ước tính sử dụng dữ liệu cấp tỉnh do khu vực chi tiết còn ít mẫu.' : ''}${cov.level==='LOW' ? ' · Dữ liệu khu vực còn hạn chế.' : ''}`);
        const record=cov.fallback ? cov.province : cov.area;
        text('houseTrainingContext',`${cov.fallback ? input.province+' (cấp tỉnh)' : input.area_name}: ${record.sample_count.toLocaleString('vi-VN')} mẫu đã xác minh · Median dữ liệu: ${api.formatPrice(record.median_price_per_m2_vnd,1)}/m² · Ngày mới nhất ${record.latest_date.slice(0,10)}.`);
        updateMarket(input);
    }
    async function updateMarket(input) {
        const token=++marketRequest;
        text('houseMarketStatus','Dữ liệu thị trường cập nhật tự động chưa được kết nối.');
        try {
            const query=new URLSearchParams({province:input.province,area:input.area_name,property_type:input.property_type});
            const response=await fetch('/api/market-data?'+query);
            if(!response.ok)throw Error('static fallback');
            const data=await response.json();
            if(token!==marketRequest)return;
            if(!data.available)throw Error('static fallback');
            showMarket(data);
        } catch {
            try {
                const data=await (await fetch('./data/vietnam-market-stats.json')).json();
                if(token!==marketRequest)return;
                const candidates=[input.area_name,''];
                const row=candidates.map(area=>data.stats.find(r=>r.province===input.province&&r.area===area&&r.property_type===input.property_type)).find(Boolean);
                if(row)showMarket(row);else text('houseStaticMarket','Chưa đủ dữ liệu đã xác minh cho loại tài sản tại khu vực này.');
            } catch {text('houseStaticMarket','Không tải được thống kê khu vực. Dự đoán vẫn chạy độc lập.');}
        }
    }
    function showMarket(data) {
        if(!Number.isInteger(data.sample_count)||data.sample_count<30||!Number.isFinite(data.median_price_per_m2)||!Number.isFinite(data.p25_price_per_m2)||!Number.isFinite(data.p75_price_per_m2))return;
        text('houseStaticMarket',`${data.area||data.province} · ${data.property_type} · Median ${api.formatPrice(data.median_price_per_m2,1)}/m² · P25–P75: ${api.formatPrice(data.p25_price_per_m2,1)} – ${api.formatPrice(data.p75_price_per_m2,1)}/m² · ${data.sample_count.toLocaleString('vi-VN')} mẫu · Ngày dữ liệu mới nhất ${data.latest_listing_date?.slice(0,10)} · ${data.coverage}${data.area?'':' · dùng cấp tỉnh'}`);
    }
    function clear() {
        original=null;scenario=null;$('houseResult').hidden=true;$('houseExploration').hidden=true;$('houseEmptyResult').hidden=false;$('houseInputError').hidden=true;
        window.dispatchEvent(new Event('portfolio:houseclear'));
    }
    function renderContributions(input) {
        $('houseContributions').replaceChildren();
        if(model.mode==='VERIFIED MARKET ESTIMATE BETA') {
            const cov=api.coverageFor(model,input), group=cov.fallback?cov.province:cov.area;
            const facts=[`Loại tài sản: ${input.property_type}`,`Nhóm tham chiếu: ${cov.fallback?input.province:input.area_name}`,`${cov.count.toLocaleString('vi-VN')} mẫu đã xác minh · ${cov.level}`,`Median giá/m²: ${api.formatPrice(group.median_price_per_m2_vnd,1)}/m²`,`Diện tích: ${input.area_m2} m²`];
            facts.forEach(value=>$('houseContributions').append(node('li',value)));
            text('houseReference','Công thức: median giá/m² × diện tích. Đây là cơ sở thống kê, không phải feature contribution của Machine Learning.');return;
        }
        const contributions=api.contributions(model,input).slice(0,5), maximum=Math.max(...contributions.map(c=>Math.abs(c.value)),1);
        for(const c of contributions) {
            const item=node('li'),label=node('div',undefined,'house-contribution-label');
            label.append(node('strong',c.label),node('span',`${c.value>=0?'+':'−'}${api.formatPrice(Math.abs(c.value))}`));
            const track=node('div',undefined,'house-contribution-track'),bar=node('span',undefined,c.value<0?'negative':'');
            bar.style.width=(Math.abs(c.value)/maximum*100)+'%';track.append(bar);
            item.append(label,track,node('small',Math.abs(c.value)<1 ? 'Không đổi so với hồ sơ tham chiếu' : c.value>=0?'↑ Đẩy giá mô hình lên':'↓ Kéo giá mô hình xuống'));
            $('houseContributions').append(item);
        }
        const ref=model.reference_input;
        text('houseReference',`Hồ sơ tham chiếu train: ${ref.area_name}, ${ref.province}, ${ref.area_m2} m². Mức đóng góp phụ thuộc hồ sơ tham chiếu và các trường khác.`);
    }
    function scenarioInput() {
        return {...original.input,area_m2:numberValue($('scenarioArea'))};
    }
    function updateScenario() {
        if(!original)return;
        $('scenarioError').hidden=true;scenario=null;$('houseApplyScenario').disabled=true;
        try {
            const input=scenarioInput(), prediction=api.predict(model,input), delta=prediction.total_price_vnd-original.prediction.total_price_vnd;
            scenario={input,prediction};
            text('scenarioPrice',displayedPrice(prediction.total_price_vnd,prediction.coverage));
            text('scenarioDelta',`${delta>=0?'+':'−'}${api.formatPrice(Math.abs(delta))} (${delta>=0?'+':''}${(delta/original.prediction.total_price_vnd*100).toLocaleString('vi-VN',{maximumFractionDigits:1})}%)`);
            $('houseApplyScenario').disabled=false;
        } catch(error) {
            text('scenarioPrice','—');text('scenarioDelta','—');text('scenarioError',error.message);$('scenarioError').hidden=false;
        }
    }
    function scatter() {
        const svg=$('houseScatter');svg.replaceChildren();
        const samples=model.scatter.filter(r=>r.actual_vnd>0&&r.predicted_vnd>0);
        const low=Math.floor(Math.log10(Math.min(...samples.flatMap(r=>[r.actual_vnd,r.predicted_vnd])))), high=Math.ceil(Math.log10(Math.max(...samples.flatMap(r=>[r.actual_vnd,r.predicted_vnd]))));
        const x=v=>65+(Math.log10(v)-low)/(high-low)*410, y=v=>280-(Math.log10(v)-low)/(high-low)*250;
        function add(tag,attrs,value){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(value!==undefined)e.textContent=value;svg.append(e);}
        add('title',{},'Actual vs Predicted trên mẫu kiểm thử; trục log VNĐ');
        for(let k=low;k<=high;k++){const v=10**k;add('line',{x1:x(v),y1:30,x2:x(v),y2:280,stroke:'#2b4055'});add('line',{x1:65,y1:y(v),x2:475,y2:y(v),stroke:'#2b4055'});add('text',{x:x(v),y:301,fill:'#91a9c4','font-size':11,'text-anchor':'middle'},api.formatPrice(v,0).replace(' VNĐ',''));add('text',{x:59,y:y(v)+4,fill:'#91a9c4','font-size':11,'text-anchor':'end'},api.formatPrice(v,0).replace(' VNĐ',''));}
        add('line',{x1:65,y1:280,x2:475,y2:30,stroke:'#9fe7d6','stroke-dasharray':'6 5','stroke-width':1.5});
        for(const r of samples)add('circle',{cx:x(r.actual_vnd),cy:y(r.predicted_vnd),r:3.3,fill:'#62d8c8',opacity:.48});
        add('text',{x:270,y:331,fill:'#b5c9e2','text-anchor':'middle','font-size':13},'Giá rao trong dataset (VNĐ, log)');
        add('text',{x:13,y:161,transform:'rotate(-90 13 161)',fill:'#b5c9e2','text-anchor':'middle','font-size':13},'Giá dự đoán (VNĐ, log)');
    }
    function renderMetadata() {
        text('houseDataPeriod',model.data_date_info.display);text('houseModelInfo',`${model.model_name} · ${model.model_version}`);
        if(model.mode==='VERIFIED MARKET ESTIMATE BETA') {
            $('housePerformance').hidden=true;
            const facts=[['Dataset',model.dataset_name],['Nguồn / license',`${model.data_source.publisher} · ${model.data_source.license}`],['Dữ liệu',model.data_date_info.display],['Số mẫu đã xác minh',model.sample_count.toLocaleString('vi-VN')],['Phương pháp','Median giá/m² · BETA'],['Gate ML','194/200 = 97% · FAIL · không train']];
            for(const [label,value] of facts){const row=node('div');row.append(node('dt',label),node('dd',value));$('houseSourceFacts').append(row);}
            model.limitations.forEach(l=>$('houseLimitations').append(node('li',l)));
            model.coverage.filter(p=>p.supported).forEach(p=>$('houseProvince').append(new Option(p.name,p.name)));
            model.property_types.forEach(t=>$('housePropertyType').append(new Option(t,t)));
            model.samples.forEach((sample,i)=>{
                const card=node('article',undefined,'house-sample'),input=sample.input;
                card.append(node('strong',input.province),node('p',`${input.area_name} · ${input.property_type} · ${input.area_m2} m²`),node('p',`Giá rao trong nguồn: ${api.formatPrice(sample.listed_price_vnd)}`));
                const button=node('button','Điền mẫu '+(i+1),'house-secondary');button.type='button';button.dataset.houseSample=i;
                button.addEventListener('click',()=>{clear();form.elements.province.value=input.province;$('houseAreaSearch').value='';areas();api.fields.forEach(k=>{form.elements[k].value=input[k]??'';});updateCoverage();text('houseStatus','Đã điền mẫu căn hộ thật. Bấm Ước tính giá để dùng median giá/m².');});card.append(button);$('houseSamples').append(card);
            });return;
        }
        document.querySelectorAll('[data-house-metric]').forEach(e=>{const k=e.dataset.houseMetric;e.textContent=k==='r2'?model.metrics[k].toFixed(3):k==='mape'?(model.metrics[k]*100).toLocaleString('vi-VN',{maximumFractionDigits:1})+'%':api.formatPrice(model.metrics[k]);});
        for(const m of model.model_comparison){const row=node('tr',undefined,m.model_name===model.model_name&&m.target_transform===model.target_transform?'selected':'');row.append(node('td',`${m.model_name} / ${m.target_transform==='log1p_vnd'?'log giá':'giá gốc'}`),node('td',api.formatPrice(m.holdout.mae)),node('td',m.holdout.r2.toFixed(3)));$('houseComparison').append(row);}
        text('houseSplit',`${model.train_rows.toLocaleString('vi-VN')} train / ${model.test_rows.toLocaleString('vi-VN')} test. Temporal split tại ${model.split.cutoff.slice(0,10)} theo ngày publisher; không shuffle timeline. Chọn model trên grouped validation trong train; giữ holdout riêng. ${model.split.limitation}`);
        const facts=[['Dataset',`${model.dataset_name} · ${model.data_source.publisher}`],['License',model.data_source.license+' (publisher khai báo)'],['Data period',model.data_date_info.display],['Model trained date',new Date(model.trained_at).toLocaleString('vi-VN')],['Số mẫu sau cleaning',model.sample_count.toLocaleString('vi-VN')],['Model',`${model.model_name} · ${model.model_version}`]];
        for(const [label,value] of facts){const row=node('div');row.append(node('dt',label),node('dd',value));$('houseSourceFacts').append(row);}
        model.limitations.forEach(l=>$('houseLimitations').append(node('li',l)));
        model.coverage.filter(p=>p.supported).forEach(p=>$('houseProvince').append(new Option(p.name,p.name)));
        model.property_types.forEach(t=>$('housePropertyType').append(new Option(t,t)));
        model.samples.forEach((sample,i)=>{
            const card=node('article',undefined,'house-sample'),input=sample.input;
            card.append(node('strong',input.province),node('p',`${input.area_name} · ${input.property_type} · ${input.area_m2} m² · ${input.bedrooms??'Chưa rõ'} PN · ${input.bathrooms??'Chưa rõ'} phòng tắm`),node('p',`Giá rao trong nguồn: ${api.formatPrice(sample.listed_price_vnd)}`));
            const button=node('button','Điền mẫu '+(i+1),'house-secondary');button.type='button';button.dataset.houseSample=i;
            button.addEventListener('click',()=>{clear();form.elements.province.value=input.province;$('houseAreaSearch').value='';areas();api.fields.forEach(k=>{form.elements[k].value=input[k]??'';});updateCoverage();text('houseStatus','Đã điền mẫu thật từ dataset. Bấm Ước tính giá để chạy mô hình.');});card.append(button);$('houseSamples').append(card);
        });
        scatter();
    }
    form.addEventListener('submit',event=>{
        event.preventDefault();clear();if(!model)return;
        try {
            if(!form.reportValidity())return;
            const input=inputFromForm(), prediction=api.predict(model,input), cov=prediction.coverage;
            original={input,prediction};
            text('housePrice',displayedPrice(prediction.total_price_vnd,cov));text('housePerM2','Giá/m²: '+api.formatPrice(cov.fallback||cov.level==='LOW'?Math.round(prediction.price_per_m2_vnd/1e6)*1e6:prediction.price_per_m2_vnd,1)+'/m²');
            text('houseMaeContext',model.mode==='VERIFIED MARKET ESTIMATE BETA'?'Không áp dụng (BETA)':'± '+api.formatPrice(model.metrics.mae));text('houseResultCoverage',`${cov.level} · ${cov.count.toLocaleString('vi-VN')} mẫu`);
            text('housePredictionNote',`${cov.fallback?'Ước tính sử dụng dữ liệu cấp tỉnh do khu vực chi tiết còn ít mẫu. ':''}${cov.level==='LOW'||cov.fallback?'Dữ liệu khu vực còn hạn chế. Giá hiển thị được làm tròn 100 triệu VNĐ. ':''}Median giá/m² × diện tích; chưa điều chỉnh đặc điểm từng căn hộ. Ước tính thống kê BETA, không thay thế định giá chuyên nghiệp.`);
            $('houseResult').hidden=false;$('houseEmptyResult').hidden=true;$('houseExploration').hidden=false;
            $('scenarioArea').value=input.area_m2; text('scenarioOriginal',displayedPrice(prediction.total_price_vnd,cov));updateScenario();renderContributions(input);updateCoverage();
            window.dispatchEvent(new CustomEvent('portfolio:houseprediction',{detail:{predicted_price_vnd:prediction.total_price_vnd,predicted_price_per_m2:prediction.price_per_m2_vnd,province:input.province,area_name:input.area_name||null,property_type:input.property_type,model_version:model.model_version,input_data:input}}));
        } catch(error){original=null;scenario=null;$('houseResult').hidden=true;$('houseExploration').hidden=true;$('houseEmptyResult').hidden=false;text('houseInputError',error.message);$('houseInputError').hidden=false;}
    });
    form.addEventListener('input',clear);form.addEventListener('reset',()=>{clear();setTimeout(()=>{areas();text('houseTrainingContext','Chọn khu vực để xem thống kê đã xác minh.');},0);});
    $('houseProvince').addEventListener('change',()=>{clear();$('houseAreaSearch').value='';$('houseArea').value='';areas();});
    $('houseArea').addEventListener('change',()=>{clear();updateCoverage();});$('houseAreaSearch').addEventListener('input',areas);
    $('housePropertyType').addEventListener('change',()=>{clear();updateCoverage();});
    $('houseScenarioFields').addEventListener('input',updateScenario);
    $('houseApplyScenario').addEventListener('click',()=>{if(!scenario)return;const point={...scenario.input};clear();api.fields.forEach(k=>{form.elements[k].value=point[k]??'';});form.requestSubmit();});
    async function load() {
        try {const response=await fetch('./vietnam-house-model.json');if(!response.ok)throw Error('model');model=api.validateModel(await response.json());renderMetadata();$('houseFields').disabled=false;text('houseStatus','Ước tính thống kê BETA sẵn sàng · median giá/m² từ căn hộ đã xác minh · không phải Machine Learning Prediction. Đọc giới hạn trước khi dùng kết quả.');}
        catch {model=null;$('houseFields').disabled=true;text('houseStatus','Không tải được thống kê BETA. Hãy dùng HTTP server, kiểm tra kết nối hoặc tải lại trang.');$('houseStatus').classList.add('house-error');}
    }
    window.HousePage = Object.freeze({ready:load(),getModel:()=>model});
})();
