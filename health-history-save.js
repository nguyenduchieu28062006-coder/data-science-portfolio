"use strict";
(() => {
    const button = document.getElementById('historySave');
    const checkbox = document.getElementById('historySaveInputs');
    const message = document.getElementById('historySaveMessage');
    const login = document.getElementById('historySaveLogin');
    let result = null;
    let pending = false;
    function render() {
        button.disabled = pending || !result || result.saved;
        button.textContent = pending ? 'Đang lưu...' : result?.saved ? 'Đã lưu' : 'Lưu vào lịch sử';
        checkbox.disabled = pending || Boolean(result?.saved);
    }
    addEventListener('portfolio:healthprediction', event => {
        result = { ...event.detail, saved: false };
        checkbox.checked = false;
        message.textContent = '';
        login.hidden = true;
        render();
    });
    addEventListener('portfolio:healthclear', () => { result = null; checkbox.checked = false; render(); });
    addEventListener('portfolio:authchange', () => {
        message.textContent = '';
        login.hidden = true;
        render();
    });
    button.addEventListener('click', async () => {
        if (pending || !result || result.saved) return;
        pending = true;
        const snapshot = result;
        const includeInputs = checkbox.checked;
        render();
        try {
            await window.PortfolioAuth?.ready;
            const auth = window.PortfolioAuth;
            const client = auth?.getClient();
            if (auth?.getStatus() !== 'ready' || !client) {
                message.textContent = 'Supabase chưa sẵn sàng. Vui lòng kiểm tra cấu hình hoặc thử lại.';
                return;
            }
            const { data, error: sessionError } = await client.auth.getUser();
            if (sessionError || !data?.user || auth.getUser()?.id !== data.user.id) {
                message.textContent = 'Bạn cần đăng nhập để lưu lịch sử.';
                login.hidden = false;
                return;
            }
            const { error } = await client.from('health_prediction_history').insert({
                user_id: data.user.id, model_score: snapshot.model_score,
                predicted_class: snapshot.predicted_class, threshold: snapshot.threshold,
                model_version: snapshot.model_version, input_data: includeInputs ? snapshot.input_data : null
            });
            if (error) throw error;
            snapshot.saved = true;
            if (result === snapshot && auth.getUser()?.id === data.user.id) message.textContent = 'Đã lưu vào lịch sử.';
        } catch (error) {
            if (result === snapshot) {
                message.textContent = error?.status === 401 || error?.code === 'PGRST301'
                    ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.' : 'Không thể lưu lịch sử. Vui lòng thử lại.';
                login.hidden = !(error?.status === 401 || error?.code === 'PGRST301');
            }
        } finally { pending = false; render(); }
    });
})();
