"use strict";
(() => {
    const columns = 'id,created_at,model_score,predicted_class,threshold,model_version,input_data';
    // Future modules supply their own loader and renderer; no placeholder records.
    const historyModules = [
        { id: 'health', title: '❤️ Health Prediction', enabled: true, table: 'health_prediction_history', note: 'Đây là kết quả phân loại của mô hình, không phải chẩn đoán y khoa.', clearLabel: 'Health Prediction', load: loadHealth, render: renderHealth },
        { id: 'house-price', title: '🇻🇳 Ước tính giá bất động sản Việt Nam', enabled: true, table: 'house_price_history', note: 'Median giá rao thống kê BETA; chi tiết ghi cấp dữ liệu thực sự sử dụng.', clearLabel: 'Ước tính giá bất động sản', load: loadHouse, render: renderHouse },
        { id: 'churn', title: '👥 Customer Churn Prediction', enabled: false },
        { id: 'sales', title: '📈 Sales Forecasting', enabled: false }
    ];
    const labels = { age: 'Tuổi (năm)', sex: 'Giới tính', cp: 'Loại đau ngực', trestbps: 'Huyết áp nghỉ (mmHg)', chol: 'Cholesterol (mg/dL)', fbs: 'Đường huyết lúc đói > 120 mg/dL', restecg: 'ECG lúc nghỉ', thalach: 'Nhịp tim tối đa (nhịp/phút)', exang: 'Đau thắt ngực khi vận động', oldpeak: 'Mức chênh xuống ST', slope: 'Độ dốc đoạn ST', ca: 'Số mạch chính', thal: 'Kết quả tưới máu' };
    const categories = {
        sex: { 0: 'Nữ', 1: 'Nam' }, cp: { 1: 'Đau thắt ngực điển hình', 2: 'Đau thắt ngực không điển hình', 3: 'Đau không do tim', 4: 'Không triệu chứng' },
        fbs: { 0: 'Không', 1: 'Có' }, exang: { 0: 'Không', 1: 'Có' }, restecg: { 0: 'Bình thường', 1: 'Bất thường ST-T', 2: 'Phì đại thất trái' },
        slope: { 1: 'Dốc lên', 2: 'Phẳng', 3: 'Dốc xuống' }, thal: { 3: 'Bình thường', 6: 'Khiếm khuyết cố định', 7: 'Khiếm khuyết hồi phục' }
    };
    const status = document.getElementById('historyStatus');
    const login = document.getElementById('historyLogin');
    let generation = 0;
    function node(tag, text, className) {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        if (className) element.className = className;
        return element;
    }
    function expired(error) { return error?.status === 401 || ['PGRST301', 'PGRST302', 'bad_jwt', 'session_expired'].includes(error?.code); }
    function requireLogin(text) {
        generation++;
        document.querySelectorAll('[data-history-content]').forEach(element => element.replaceChildren());
        status.textContent = text;
        login.hidden = false;
    }
    async function verifiedClient(user) {
        const client = window.PortfolioAuth.getClient();
        const { data, error } = await client.auth.getUser();
        if (error || !data?.user || data.user.id !== user.id || window.PortfolioAuth.getUser()?.id !== user.id) {
            const failure = new Error('session'); failure.status = 401; throw failure;
        }
        return client;
    }
    async function loadHealth(client, user, offset) {
        return client.from('health_prediction_history').select(columns).eq('user_id', user.id)
            .order('created_at', { ascending: false }).order('id', { ascending: false }).range(offset, offset + 49);
    }
    async function loadHouse(client, user, offset) {
        const response = await client.from('house_price_history').select('id,created_at,predicted_price_vnd,predicted_price_per_m2,province,area_name,property_type,model_version,input_data').eq('user_id', user.id)
            .order('created_at', { ascending: false }).order('id', { ascending: false }).range(offset, offset + 49);
        if (response.error) return response;
        if (!Array.isArray(response.data) || response.data.some(record => !Number.isFinite(record.predicted_price_vnd) || record.predicted_price_vnd <= 0)) {
            // Reject malformed/unrelated rows rather than display manufactured prices.
            return { data: [], error: null };
        }
        return response;
    }
    function houseMoney(value) {
        if (!Number.isFinite(value)) return 'Không có dữ liệu';
        const unit = Math.abs(value) >= 1e9 ? 1e9 : 1e6;
        return (value / unit).toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + (unit === 1e9 ? ' tỷ VNĐ' : ' triệu VNĐ');
    }
    function renderHouse(record, remove) {
        const card = node('article', undefined, 'history-record');
        const date = new Date(record.created_at);
        const dateText = Number.isNaN(date.getTime()) ? 'Không có ngày giờ' : date.toLocaleString('vi-VN');
        card.append(node('h3', dateText), node('p', houseMoney(record.predicted_price_vnd), 'history-score'),
            node('p', `Giá/m²: ${houseMoney(record.predicted_price_per_m2)}/m²`), node('p', `${record.area_name || 'Ước lượng cấp tỉnh'}, ${record.province}`), node('p', `Phiên bản ước tính: ${record.model_version || 'Không có dữ liệu'}`));
        card.append(node('p', `Loại BĐS: ${record.property_type || 'Không có dữ liệu'}`));
        const details = node('details'); details.append(node('summary', 'Xem chi tiết'));
        const metadata = record.input_data?.metadata;
        if (metadata && typeof metadata === 'object') {
            const location = value => [value?.sub_area, value?.ward, value?.province, value?.region].filter(Boolean).join(', ') || 'Không có dữ liệu';
            for (const [label, value] of [['Vị trí đã chọn', location(metadata.selected_location)], ['Vị trí thực sự sử dụng', location(metadata.used_location)],
                ['Resolution', metadata.resolution_level], ['Số mẫu', metadata.sample_count], ['Coverage', metadata.coverage], ['Phương pháp', metadata.estimate_method],
                ['Diện tích (m²)', metadata.area_m2 ?? record.input_data?.inputs?.area_m2], ['Ngày dữ liệu', metadata.latest_data_date || metadata.data_latest_date], ['Lý do fallback', metadata.fallback_reason || 'Không fallback'],
                ['P25–P75 giá rao', houseMoney(metadata.p25_price_vnd)+' – '+houseMoney(metadata.p75_price_vnd)]]) {
                details.append(node('p', label + ': ' + String(value ?? 'Không có dữ liệu')));
            }
        }
        if (metadata?.fallback_reason) card.append(node('p', metadata.resolution_level === 'REGIONAL_ESTIMATE' ? '⚠ Ước lượng từ tỉnh lân cận; dữ liệu trực tiếp tại khu vực còn ít.' : '⚠ Chưa có dữ liệu giá chính xác tại khu vực này. Đây là giá ước lượng.', 'history-disclaimer'));
        const inputs = metadata ? record.input_data.inputs : record.input_data;
        if (!inputs || typeof inputs !== 'object') details.append(node('p', 'Dữ liệu đầu vào không được lưu cho lần dự đoán này.'));
        else {
            const list = node('dl', undefined, 'history-inputs');
            for (const [key, label] of Object.entries({ province: 'Tỉnh / Thành phố', area_name: 'Khu vực lịch sử', property_type: 'Loại BĐS', area_m2: 'Diện tích (m²)', bedrooms: 'Phòng ngủ', bathrooms: 'Phòng tắm' })) {
                const row = node('div'); row.append(node('dt', label), node('dd', inputs[key] == null || inputs[key] === '' ? 'Không có dữ liệu' : String(inputs[key]))); list.append(row);
            }
            details.append(list);
        }
        const button = node('button', 'Xóa', 'history-danger'); button.type = 'button'; button.addEventListener('click', () => remove(record, card, button));
        card.append(details, button); return card;
    }
    function renderHealth(record, remove) {
        const card = node('article', undefined, 'history-record');
        const date = new Date(record.created_at);
        const dateText = Number.isNaN(date.getTime()) ? 'Không có ngày giờ' : date.toLocaleString('vi-VN');
        const score = typeof record.model_score === 'number' && Number.isFinite(record.model_score) ? `${(record.model_score * 100).toFixed(1)}%` : 'Không có dữ liệu';
        const group = record.predicted_class === 1 ? 'Bệnh tim (Class 1)' : record.predicted_class === 0 ? 'Không bệnh tim (Class 0)' : 'Không có dữ liệu';
        card.append(node('h3', dateText), node('p', `Model score: ${score}`, 'history-score'), node('p', `Nhóm dự đoán: ${group}`), node('p', `Model: ${record.model_version || 'Không có dữ liệu'}`));
        const details = node('details');
        details.append(node('summary', 'Xem chi tiết'), node('p', `Ngày giờ: ${dateText}`), node('p', `Model score: ${score}`), node('p', `Predicted class: ${group}`), node('p', `Threshold: ${record.threshold ?? 'Không có dữ liệu'}`), node('p', `Model version: ${record.model_version || 'Không có dữ liệu'}`));
        if (!record.input_data || typeof record.input_data !== 'object') details.append(node('p', 'Dữ liệu đầu vào không được lưu cho lần dự đoán này.'));
        else {
            const list = node('dl', undefined, 'history-inputs');
            Object.entries(labels).forEach(([key, label]) => {
                const row = node('div');
                const value = record.input_data[key];
                row.append(node('dt', label), node('dd', value == null ? 'Không có dữ liệu' : categories[key]?.[value] ?? String(value)));
                list.append(row);
            });
            details.append(list);
        }
        const button = node('button', 'Xóa', 'history-danger'); button.type = 'button';
        button.addEventListener('click', () => remove(record, card, button));
        card.append(details, button);
        return card;
    }
    async function refresh() {
        const token = ++generation;
        const auth = window.PortfolioAuth;
        login.hidden = true;
        const root = document.getElementById('historyModules'); root.replaceChildren();
        const sections = historyModules.map(module => {
            const section = node('section', undefined, 'health-panel history-module');
            section.append(node('h2', module.title));
            const content = node('div'); content.dataset.historyContent = '';
            if (!module.enabled) section.append(node('p', 'Sắp có · Chưa có dữ liệu', 'health-muted'));
            else section.append(content);
            root.append(section);
            return { module, content };
        });
        if (auth?.getStatus() !== 'ready') { status.textContent = 'Supabase chưa sẵn sàng. Vui lòng kiểm tra cấu hình hoặc thử lại.'; return; }
        const user = auth.getUser();
        if (!user) { requireLogin('Bạn cần đăng nhập để xem lịch sử.'); return; }
        status.textContent = '';
        for (const { module, content } of sections.filter(item => item.module.enabled)) {
            const notice = node('p', 'Đang tải lịch sử…'); notice.setAttribute('role', 'status');
            const cards = node('div', undefined, 'history-records');
            const more = node('button', 'Tải thêm'); more.type = 'button'; more.hidden = true;
            const clear = node('button', `Xóa toàn bộ lịch sử ${module.clearLabel}`, 'history-danger'); clear.type = 'button'; clear.hidden = true;
            content.append(node('p', module.note, 'health-muted'), clear, notice, cards, more);
            let offset = 0, busy = false, deleting = false;
            const current = () => token === generation && auth.getUser()?.id === user.id;
            function fail(error, text) {
                if (!current()) return;
                if (expired(error)) requireLogin('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
                else notice.textContent = text;
            }
            async function remove(record, card, button) {
                if (busy || deleting || !current() || !window.confirm(record ? 'Bạn có chắc muốn xóa bản ghi này? Hành động này không thể hoàn tác.' : `Bạn có chắc muốn xóa toàn bộ lịch sử ${module.clearLabel}? Hành động này không thể hoàn tác.`)) return;
                deleting = true; button.disabled = true;
                try {
                    const client = await verifiedClient(user);
                    if (!current()) return;
                    let query = client.from(module.table).delete().eq('user_id', user.id);
                    if (record) query = query.eq('id', record.id);
                    const { data, error } = await query.select('id');
                    if (error) throw error;
                    if (!current()) return;
                    if (record && !data?.some(row => row.id === record.id)) throw new Error('delete_failed');
                    if (!record && cards.children.length && !data?.length) throw new Error('delete_failed');
                    if (record) { card.remove(); offset = Math.max(0, offset - 1); }
                    else { cards.replaceChildren(); offset = 0; more.hidden = true; }
                    clear.hidden = !cards.children.length;
                    notice.textContent = cards.children.length ? 'Đã xóa bản ghi.' : 'Chưa có dữ liệu';
                } catch (error) { fail(error, 'Không thể xóa bản ghi.'); }
                finally { deleting = false; button.disabled = false; }
            }
            async function load() {
                if (busy || deleting || !current()) return;
                busy = true; more.disabled = true;
                try {
                    const client = await verifiedClient(user);
                    if (!current()) return;
                    const { data, error } = await module.load(client, user, offset);
                    if (error) throw error;
                    if (!current()) return;
                    data.forEach(record => cards.append(module.render(record, remove)));
                    offset += data.length;
                    more.hidden = data.length < 50;
                    clear.hidden = !cards.children.length;
                    notice.textContent = cards.children.length ? '' : 'Chưa có dữ liệu';
                } catch (error) { fail(error, 'Không thể tải lịch sử.'); more.hidden = false; more.textContent = 'Thử lại'; }
                finally { busy = false; more.disabled = false; }
            }
            clear.addEventListener('click', () => remove(null, null, clear));
            more.addEventListener('click', load);
            await load();
        }
    }
    addEventListener('portfolio:authchange', refresh);
    Promise.resolve(window.PortfolioAuth?.ready).then(refresh);
})();
