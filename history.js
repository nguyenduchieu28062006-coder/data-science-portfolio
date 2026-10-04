"use strict";
(() => {
    const columns = 'id,created_at,model_score,predicted_class,threshold,model_version,input_data';
    // Future modules supply their own loader and renderer; no placeholder records.
    const historyModules = [
        { id: 'health', title: '❤️ Health Prediction', enabled: true, load: loadHealth, render: renderHealth },
        { id: 'house-price', title: '🏠 House Price Prediction', enabled: false },
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
            const clear = node('button', 'Xóa toàn bộ lịch sử Health Prediction', 'history-danger'); clear.type = 'button'; clear.hidden = true;
            content.append(node('p', 'Đây là kết quả phân loại của mô hình, không phải chẩn đoán y khoa.', 'health-muted'), clear, notice, cards, more);
            let offset = 0, busy = false, deleting = false;
            const current = () => token === generation && auth.getUser()?.id === user.id;
            function fail(error, text) {
                if (!current()) return;
                if (expired(error)) requireLogin('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
                else notice.textContent = text;
            }
            async function remove(record, card, button) {
                if (busy || deleting || !current() || !window.confirm(record ? 'Bạn có chắc muốn xóa bản ghi này? Hành động này không thể hoàn tác.' : 'Bạn có chắc muốn xóa toàn bộ lịch sử Health Prediction? Hành động này không thể hoàn tác.')) return;
                deleting = true; button.disabled = true;
                try {
                    const client = await verifiedClient(user);
                    if (!current()) return;
                    let query = client.from('health_prediction_history').delete().eq('user_id', user.id);
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
