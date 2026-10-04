"use strict";
/* Browser inference for the exported sklearn model. No remote prediction calls. */
(() => {
    const fields = ['province', 'area_name', 'property_type', 'area_m2'];
    const labels = {province: 'Tỉnh / Thành phố', area_name: 'Khu vực', property_type: 'Loại bất động sản', area_m2: 'Diện tích', bedrooms: 'Phòng ngủ', bathrooms: 'Phòng tắm'};
    function validateModel(m) {
        if (m?.schema_version === 3 && m.mode === 'VERIFIED MARKET ESTIMATE BETA' && m.model_review?.public_status === 'READY' &&
            m.regressor?.kind === 'market_median' && JSON.stringify(m.features) === JSON.stringify(fields) && m.property_types?.length === 1 &&
            m.property_types[0] === 'Căn hộ chung cư' && Array.isArray(m.coverage) && m.coverage.length && m.coverage.every(p=>
                Number.isInteger(p.sample_count) && p.sample_count>0 && Number.isFinite(p.median_price_per_m2_vnd) && p.median_price_per_m2_vnd>0 &&
                p.supported === (p.sample_count>=80) && Array.isArray(p.areas) && p.areas.every(a=>Number.isInteger(a.sample_count)&&a.sample_count>0&&Number.isFinite(a.median_price_per_m2_vnd)&&a.median_price_per_m2_vnd>0&&a.supported===(a.sample_count>=30)))) return m;
        if (m?.schema_version !== 2 || m.model_review?.public_status !== 'READY' || JSON.stringify(m.features) !== JSON.stringify(fields) ||
            !['ridge','median','gradient_boosting','random_forest'].includes(m.regressor?.kind) ||
            !['raw_vnd','log1p_vnd'].includes(m.target_transform) || !Array.isArray(m.coverage) || !m.coverage.length ||
            !['mae','rmse','r2','mape'].every(k => Number.isFinite(m.metrics?.[k])) ||
            m.preprocessing?.mean?.length !== 5 || m.preprocessing.mean.some(v => !Number.isFinite(v)) ||
            m.preprocessing?.scale?.length !== 5 || m.preprocessing.scale.some(v => !Number.isFinite(v) || v <= 0) ||
            m.preprocessing?.categories?.length !== 3 || !Array.isArray(m.property_types)) throw Error('File mô hình không hợp lệ hoặc chưa được duyệt public.');
        if (m.regressor.trees && !m.regressor.trees.every(t => ['left','right','feature','threshold','value'].every(k => Array.isArray(t[k]) && t[k].length === t.value.length))) throw Error('Cấu trúc cây mô hình không hợp lệ.');
        return m;
    }
    function coverageFor(m, input) {
        const province = m.coverage.find(p => p.name === input.province);
        const area = province?.areas.find(a => a.name === input.area_name);
        return {province, area, fallback: !area?.supported, count: area?.supported ? area.sample_count : province?.sample_count || 0,
            level: area?.supported ? area.coverage : province?.coverage || 'INSUFFICIENT'};
    }
    function validateInput(m, input, strictCoverage = true) {
        const region = coverageFor(m, input);
        if (!region.province || (strictCoverage && !region.province.supported)) throw Error('Model hiện chưa có đủ dữ liệu cho khu vực này.');
        if (typeof input.area_name !== 'string' || input.area_name.length > 100) throw Error('Khu vực không hợp lệ.');
        if (!m.property_types.includes(input.property_type)) throw Error('Loại bất động sản chưa được model hỗ trợ.');
        for (const key of ['area_m2','bedrooms','bathrooms']) {
            const value = input[key];
            if (value == null && key !== 'area_m2') continue;
            const [min,max] = m.input_bounds[key];
            if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max || (key !== 'area_m2' && !Number.isInteger(value))) throw Error(`${labels[key]} phải nằm trong khoảng ${min}–${max}${key === 'area_m2' ? ' m²' : ' và là số nguyên'}.`);
        }
        return region;
    }
    function encode(m, input) {
        const p = m.preprocessing, cov = coverageFor(m, input);
        const category = input.province + '|' + (cov.area?.supported ? input.area_name : '__province__');
        const raw = [Math.log1p(input.area_m2), input.bedrooms ?? p.medians.bedrooms, input.bathrooms ?? p.medians.bathrooms, input.bedrooms == null ? 1 : 0, input.bathrooms == null ? 1 : 0];
        const x = raw.map((v,i) => Math.fround((v-p.mean[i])/p.scale[i]));
        [input.province,category,input.property_type].forEach((value,i) => p.categories[i].forEach(c => x.push(c === value ? 1 : 0)));
        return x;
    }
    function treeValue(tree, x) {
        let node = 0, steps = 0;
        while (tree.left[node] !== -1) {
            node = x[tree.feature[node]] <= tree.threshold[node] ? tree.left[node] : tree.right[node];
            if (++steps > tree.value.length || node < 0 || node >= tree.value.length) throw Error('Không đọc được cây mô hình.');
        }
        return tree.value[node];
    }
    function predict(m, input, strictCoverage = true) {
        validateInput(m,input,strictCoverage);
        if (m.regressor.kind === 'market_median') {
            const cov=coverageFor(m,input), group=cov.fallback?cov.province:cov.area;
            const total=group.median_price_per_m2_vnd*input.area_m2;
            if(!Number.isFinite(total)||total<=0)throw Error('Không đủ thống kê hợp lệ để ước tính.');
            return {total_price_vnd:total,price_per_m2_vnd:group.median_price_per_m2_vnd,coverage:cov};
        }
        const x = encode(m,input), r = m.regressor;
        let score;
        if (r.kind === 'gradient_boosting') score = r.trees.reduce((sum,t) => sum + r.learning_rate * treeValue(t,x),r.base);
        else if (r.kind === 'random_forest') score = r.trees.reduce((sum,t) => sum + treeValue(t,x),0)/r.trees.length;
        else if (r.kind === 'ridge') score = x.reduce((sum,v,i) => sum + v*r.coefficients[i],r.intercept);
        else score = r.value;
        const total = Math.max(0,m.target_transform === 'log1p_vnd' ? Math.expm1(score) : score*1e9);
        if (!Number.isFinite(total) || total <= 0) throw Error('Mô hình không tạo được giá hợp lệ cho thông số này.');
        return {total_price_vnd: total, price_per_m2_vnd: total/input.area_m2, coverage: coverageFor(m,input)};
    }
    function contributions(m,input) {
        // Exact Shapley in VND output space, relative to a real train row.
        // Direction explains this model/reference comparison, never causation.
        const values = [];
        const sizeLimit = 1 << fields.length;
        for (let mask=0;mask<sizeLimit;mask++) {
            const point = {...m.reference_input};
            fields.forEach((key,i) => { if(mask & (1<<i)) point[key]=input[key]; });
            values.push(predict(m,point,false).total_price_vnd);
        }
        const factorial = [1,1,2,6,24,120,720];
        return fields.map((key,i) => {
            let value = 0;
            for (let mask=0;mask<sizeLimit;mask++) if(!(mask & (1<<i))) {
                const size = mask.toString(2).replaceAll('0','').length;
                value += factorial[size]*factorial[fields.length-1-size]/factorial[fields.length] * (values[mask | (1<<i)]-values[mask]);
            }
            return {key,label:labels[key],value};
        }).sort((a,b) => Math.abs(b.value)-Math.abs(a.value));
    }
    function formatPrice(value, digits = 2) {
        if (!Number.isFinite(value)) return '—';
        const divisor = Math.abs(value)>=1e9 ? 1e9 : 1e6;
        return new Intl.NumberFormat('vi-VN',{maximumFractionDigits:digits}).format(value/divisor) + (divisor === 1e9 ? ' tỷ VNĐ' : ' triệu VNĐ');
    }
    window.VietnamHouse = Object.freeze({validateModel,validateInput,coverageFor,predict,contributions,formatPrice,fields,labels});
})();
