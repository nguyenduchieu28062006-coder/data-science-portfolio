"use strict";
(() => {
    const $ = id => document.getElementById(id);
    const form = $('customerForm'), fields = $('customerFields'), result = $('customerResult');
    const status = $('customerModelStatus'), error = $('customerInputError');
    const controls = [...form.querySelectorAll('input[name], select[name]')];
    let model = null, lastResult = null;
    const labels = {
        high: 'Khả năng quay lại cao', medium: 'Cần chăm sóc thêm', low: 'Nguy cơ không quay lại cao'
    };
    const summaries = {
        high: 'Khách hàng này có khả năng quay lại mua hàng ở mức cao theo mô hình.',
        medium: 'Khách hàng này vẫn có khả năng quay lại, nhưng nên được chăm sóc thêm để tăng mức độ gắn bó.',
        low: 'Khách hàng này có nguy cơ không quay lại tương đối cao. Doanh nghiệp nên triển khai chiến lược giữ chân phù hợp.'
    };
    const advice = {
        low: [
            ['🎁', 'Ưu đãi cá nhân hóa', 'Thử một ưu đãi có giới hạn cho nhóm khách ít khả năng mua lại, dựa trên danh mục đã mua. So sánh lợi nhuận tăng thêm với nhóm không nhận ưu đãi để tránh giảm giá vô ích.'],
            ['📩', 'Chiến dịch tái kích hoạt', 'Gửi một lời nhắc có nội dung hữu ích qua kênh khách đã đồng ý nhận liên hệ. Giới hạn tần suất và đo số đơn trong 60 ngày để đánh giá khả năng tái kích hoạt.'],
            ['⭐', 'Cải thiện trải nghiệm sau mua', 'Hỏi ngắn về trải nghiệm đơn gần nhất và xử lý vấn đề nếu khách phản hồi. Mục tiêu là tháo gỡ lý do chưa mua tiếp, thay vì suy đoán rằng khách đang không hài lòng.'],
            ['🎯', 'Gợi ý sản phẩm phù hợp', 'Đề xuất một vài sản phẩm bổ sung cho danh mục từng mua; tránh danh sách đại trà. Đo tỷ lệ mua lại và giá trị đơn để kiểm tra mức độ phù hợp.'],
            ['🏅', 'Chương trình khách hàng thân thiết', 'Giới thiệu quyền lợi dễ hiểu và mốc tích lũy có thể đạt được. Theo dõi số lần mua tiếp để xem chương trình có giúp hình thành thói quen mua hay không.'],
            ['🚚', 'Giảm rào cản quay lại mua', 'Rà soát phí giao hàng, bước thanh toán và chính sách đổi trả. Thử cải thiện từng rào cản, đo tỷ lệ hoàn tất đơn và lợi nhuận trước khi mở rộng.']
        ],
        medium: [
            ['🎁', 'Ưu đãi vừa phải', 'Thử quyền lợi nhỏ như ngưỡng miễn phí giao hàng với nhóm phù hợp. Đặt giới hạn chi phí và kiểm tra số đơn tăng thêm để tránh phụ thuộc vào giảm giá.'],
            ['📩', 'Nhắc mua lại đúng nhịp', 'Dùng chu kỳ mua đã quan sát để chọn thời điểm nhắc, nếu khách cho phép liên hệ. Mục tiêu là giúp khách nhớ nhu cầu mà không gửi quá nhiều thông báo.'],
            ['🎯', 'Sản phẩm đề xuất', 'Chọn một vài sản phẩm liên quan đến các mã hàng từng mua. Thử nghiệm nội dung đề xuất và đo tỷ lệ chuyển thành đơn mua tiếp.'],
            ['🏅', 'Khuyến khích tích lũy loyalty', 'Thông báo rõ quyền lợi và mốc tích lũy tiếp theo, nếu doanh nghiệp có chương trình. Theo dõi tỷ lệ khách đạt mốc bằng một lần mua mới.'],
            ['⭐', 'Khảo sát hài lòng ngắn', 'Xin phản hồi về sản phẩm và trải nghiệm mua bằng vài câu hỏi dễ trả lời. Dùng phản hồi thật để xác định vấn đề cần xử lý và kiểm tra tỷ lệ mua lại sau đó.'],
            ['🤝', 'Chăm sóc cá nhân hóa', 'Ưu tiên một nội dung liên quan tới lịch sử mua và lựa chọn khách đã cung cấp. Giới hạn tần suất, đo tương tác và số đơn để chuyển nhóm cần chăm sóc thành nhóm gắn bó hơn.']
        ],
        high: [
            ['💎', 'Duy trì trải nghiệm tốt', 'Giữ chất lượng sản phẩm, giao hàng và phản hồi nhất quán. Theo dõi tỷ lệ mua lại và phản hồi để bảo vệ trải nghiệm đang giúp khách tiếp tục mua.'],
            ['🎯', 'Cross-sell phù hợp', 'Đề xuất sản phẩm bổ sung cho danh mục khách đã mua. Đánh giá tỷ lệ chấp nhận và sự hài lòng để tăng giá trị giỏ hàng mà không tạo cảm giác bị ép mua.'],
            ['📈', 'Upsell hợp lý', 'Giới thiệu lựa chọn nâng cấp khi có giá trị sử dụng rõ ràng. Đo giá trị đơn và tỷ lệ mua tiếp để tránh đánh đổi quan hệ dài hạn lấy doanh thu ngắn hạn.'],
            ['🏅', 'VIP / loyalty rewards', 'Ưu tiên quyền lợi dịch vụ, tích điểm hoặc trải nghiệm dành cho khách gắn bó. Đo mức sử dụng quyền lợi; tránh giảm giá đại trà cho khách vốn có khả năng mua lại cao.'],
            ['❤️', 'Thu thập feedback', 'Mời khách chia sẻ phản hồi sau mua và cho biết doanh nghiệp đã cải thiện điều gì. Mục tiêu là duy trì đối thoại và phát hiện sớm vấn đề trải nghiệm.'],
            ['🤝', 'Referral / giới thiệu bạn bè', 'Nếu phù hợp, mời khách tham gia chương trình giới thiệu minh bạch và tự nguyện. Theo dõi khách mới và lợi nhuận, đồng thời giữ trải nghiệm tốt cho cả người giới thiệu.']
        ]
    };
    const goals = {
        high: 'Ưu tiên giữ trải nghiệm tốt và tăng giá trị quan hệ, thay vì giảm giá đại trà.',
        medium: 'Ưu tiên tăng mức độ gắn bó bằng nhắc mua đúng nhịp và nội dung phù hợp.',
        low: 'Ưu tiên tìm rào cản và thử tái kích hoạt có kiểm soát; đo hiệu quả trước khi mở rộng.'
    };

    function clearResult() {
        result.hidden = true;
        result.removeAttribute('data-band');
        lastResult = null;
        $('customerAdvice').replaceChildren();
        $('customerFactors').replaceChildren();
        for (const id of ['customerReturnProbability', 'customerNonReturnProbability', 'customerBandBadge', 'customerClassification', 'customerResultSummary', 'customerChartReturnLabel', 'customerChartNonReturnLabel']) $(id).textContent = '';
        $('customerChartTooltip').hidden = true;
        $('customerDomainWarning').hidden = true;
    }

    function clearErrors() {
        error.hidden = true;
        controls.forEach(field => {
            field.removeAttribute('aria-invalid');
            $(field.id + '-error').hidden = true;
            $(field.id + '-error').textContent = '';
        });
    }

    function validateField(field) {
        let message = '';
        if (field.validity.badInput) message = 'Vui lòng nhập một số hợp lệ.';
        else if (field.value.trim() === '') message = 'Vui lòng điền trường này.';
        else if (field.validity.rangeUnderflow || field.validity.rangeOverflow) message = 'Giá trị nằm ngoài phạm vi nhập cho phép.';
        else if (field.validity.stepMismatch) message = field.step === '1' ? 'Vui lòng nhập số nguyên.' : 'Vui lòng dùng số thập phân đúng đơn vị của trường.';
        const note = $(field.id + '-error');
        note.textContent = message;
        note.hidden = !message;
        if (message) field.setAttribute('aria-invalid', 'true');
        else field.removeAttribute('aria-invalid');
        return !message;
    }

    controls.forEach(field => {
        const note = document.createElement('small');
        note.id = field.id + '-error';
        note.className = 'cr-field-error';
        note.hidden = true;
        field.parentElement.appendChild(note);
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), note.id].filter(Boolean).join(' '));
        field.addEventListener('blur', () => validateField(field));
        field.addEventListener('input', () => { if (field.hasAttribute('aria-invalid')) validateField(field); });
    });
    form.addEventListener('input', () => { clearResult(); error.hidden = true; });
    form.addEventListener('change', () => { clearResult(); error.hidden = true; });
    form.addEventListener('reset', () => { clearResult(); clearErrors(); });

    document.querySelectorAll('[data-customer-sample]').forEach(button => button.addEventListener('click', () => {
        if (!model) return;
        const sample = model.samples.find(item => item.band === button.dataset.customerSample);
        if (!sample) return;
        clearResult();
        clearErrors();
        controls.forEach(field => { field.value = sample.input[field.name]; });
        status.textContent = 'Đã điền hồ sơ mẫu ẩn danh từ validation. Bấm dự đoán để xem kết quả.';
    }));

    function renderFactors(prediction) {
        const top = prediction.factors.slice(0, 5);
        const max = Math.max(...top.map(f => Math.abs(f.contribution)), 1e-12);
        const list = $('customerFactors');
        list.replaceChildren();
        for (const factor of top) {
            const item = document.createElement('li');
            item.className = factor.contribution >= 0 ? 'cr-factor-positive' : 'cr-factor-negative';
            item.dataset.feature = factor.feature;
            item.dataset.contribution = factor.contribution;
            const heading = document.createElement('div');
            heading.className = 'cr-factor-heading';
            const name = document.createElement('strong');
            name.textContent = factor.label;
            const value = document.createElement('span');
            value.textContent = `${factor.contribution >= 0 ? '+' : '−'}${Math.abs(factor.contribution).toFixed(3)}`;
            heading.append(name, value);
            const track = document.createElement('div');
            track.className = 'cr-factor-track';
            track.setAttribute('aria-hidden', 'true');
            const bar = document.createElement('span');
            bar.style.width = `${Math.abs(factor.contribution) / max * 100}%`;
            track.appendChild(bar);
            const direction = document.createElement('small');
            direction.textContent = factor.contribution === 0 ? 'Không làm thay đổi điểm mô hình' :
                (factor.contribution > 0 ? '↑ Tăng khả năng quay lại' : '↓ Giảm khả năng quay lại');
            item.append(heading, track, direction);
            list.appendChild(item);
        }
        const method = model.estimator.kind === 'logistic_regression' ? 'Đóng góp từ hệ số Logistic Regression trên đặc trưng đã chuẩn hóa.' :
            'Phân rã theo đường đi qua cây: cộng chênh lệch điểm giữa các nút trên đường tới lá. Đây là giải thích theo đường đi, không phải SHAP.';
        $('customerExplanationNote').textContent = `${method} Các giá trị ở thang ${prediction.explanationUnit === 'log-odds' ? 'log-odds' : 'xác suất'}, không phải phần trăm thay đổi hành vi thực tế.`;
        const total = prediction.factors.reduce((sum, factor) => sum + factor.contribution, 0);
        $('customerExplanationDetail').textContent = `Điểm nền ${prediction.baseline.toFixed(4)} + tổng đóng góp của 7 đặc trưng ${total.toFixed(4)} = ${prediction.explanationScore.toFixed(4)}. Biểu đồ chỉ hiển thị Top 5. ${model.calibration.method === 'sigmoid' ? 'Đã tính cả hệ số sigmoid calibration vào phân rã.' : ''}`;
    }

    function renderAdvice(band) {
        const grid = $('customerAdvice');
        grid.replaceChildren();
        $('customerAdviceGoal').textContent = goals[band];
        for (const [iconText, title, description] of advice[band]) {
            const card = document.createElement('article');
            card.className = 'cr-advice-card';
            const icon = document.createElement('span');
            icon.className = 'cr-advice-icon';
            icon.textContent = iconText;
            icon.setAttribute('aria-hidden', 'true');
            const heading = document.createElement('h4');
            heading.textContent = title;
            const text = document.createElement('p');
            text.textContent = description;
            card.append(icon, heading, text);
            grid.appendChild(card);
        }
    }

    function renderPrediction(prediction) {
        const percentages = CustomerReturnModel.percentageLabels(prediction.probability);
        result.dataset.band = prediction.band;
        $('customerReturnProbability').textContent = percentages.returned;
        $('customerNonReturnProbability').textContent = percentages.nonReturned;
        $('customerBandBadge').textContent = labels[prediction.band];
        $('customerClassification').textContent = `Class ${prediction.predictedClass} · ${prediction.predictedClass ? 'Có mua lại' : 'Chưa mua lại'} trong 60 ngày · Ngưỡng ${(model.threshold * 100).toFixed(1)}%`;
        $('customerResultSummary').textContent = summaries[prediction.band];
        $('customerChartReturnLabel').textContent = percentages.returned;
        $('customerChartNonReturnLabel').textContent = percentages.nonReturned;
        $('customerReturnSegment').style.width = `${prediction.probability * 100}%`;
        $('customerNonReturnSegment').style.width = `${prediction.nonReturnProbability * 100}%`;
        $('customerReturnSegment').setAttribute('aria-label', `Quay lại mua: ${percentages.returned}`);
        $('customerNonReturnSegment').setAttribute('aria-label', `Không quay lại: ${percentages.nonReturned}`);
        $('customerProbabilityChart').setAttribute('aria-label', `Biểu đồ thanh ngang 100%: Quay lại mua ${percentages.returned}; không quay lại mua ${percentages.nonReturned}`);
        $('customerResultModel').textContent = model.model_name;
        const warning = $('customerDomainWarning');
        warning.hidden = prediction.warnings.length === 0;
        warning.textContent = prediction.warnings.length ? `Một số dữ liệu nằm ngoài phạm vi train: ${prediction.warnings.join('; ')}. Kết quả có thể kém tin cậy hơn; cần kiểm chứng trên dữ liệu phù hợp.` : '';
        const caution = $('customerProbabilityCaution');
        caution.hidden = model.evaluation.calibration_status !== 'WARNING';
        caution.textContent = 'Lưu ý: calibration trên test mùa cuối năm chưa đạt; mô hình dự báo thấp hơn tỷ lệ mua lại quan sát. Xem xác suất là ước lượng, cần kiểm chứng trước khi dùng ngân sách. Ba mức chăm sóc là tương đối trong cohort validation.';
        renderFactors(prediction);
        renderAdvice(prediction.band);
        result.hidden = false;
    }

    for (const id of ['customerReturnSegment', 'customerNonReturnSegment']) {
        const segment = $(id);
        const show = () => {
            if (!lastResult) return;
            $('customerChartTooltip').textContent = segment.getAttribute('aria-label');
            $('customerChartTooltip').hidden = false;
        };
        segment.addEventListener('pointerenter', show);
        segment.addEventListener('focus', show);
        segment.addEventListener('click', show);
        segment.addEventListener('pointerleave', () => { if (document.activeElement !== segment) $('customerChartTooltip').hidden = true; });
        segment.addEventListener('blur', () => { $('customerChartTooltip').hidden = true; });
        segment.addEventListener('keydown', event => { if (event.key === 'Escape') $('customerChartTooltip').hidden = true; });
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        clearResult();
        error.hidden = true;
        if (!model) return;
        const invalid = controls.filter(field => !validateField(field));
        if (invalid.length) {
            error.textContent = 'Vui lòng kiểm tra các trường được đánh dấu trước khi dự đoán.';
            error.hidden = false;
            invalid[0].focus();
            return;
        }
        try {
            const input = Object.fromEntries(controls.map(field => [field.name, field.value]));
            const prediction = CustomerReturnModel.predict(model, input);
            renderPrediction(prediction);
            lastResult = prediction;
        } catch (failure) {
            clearResult();
            error.textContent = failure.message;
            error.hidden = false;
        }
    });

    function drawCurve(id, points, title, xLabel, yLabel, color, baseline) {
        const svg = $(id);
        svg.replaceChildren();
        const add = (tag, attrs, text) => {
            const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
            for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
            if (text !== undefined) node.textContent = text;
            svg.appendChild(node);
            return node;
        };
        add('title', {}, title);
        const x = v => 52 + v * 320, y = v => 235 - v * 215;
        for (const tick of [0, .25, .5, .75, 1]) {
            add('line', { x1: x(tick), x2: x(tick), y1: 20, y2: 235, stroke: '#e2e8f0' });
            add('line', { x1: 52, x2: 372, y1: y(tick), y2: y(tick), stroke: '#e2e8f0' });
            add('text', { x: x(tick), y: 253, 'text-anchor': 'middle', fill: '#475569', 'font-size': 11 }, tick.toFixed(2));
            add('text', { x: 43, y: y(tick) + 4, 'text-anchor': 'end', fill: '#475569', 'font-size': 11 }, tick.toFixed(2));
        }
        const basePoints = baseline === 'diagonal' ? [[0, 0], [1, 1]] : [[0, baseline], [1, baseline]];
        add('polyline', { points: basePoints.map(([a, b]) => `${x(a)},${y(b)}`).join(' '), fill: 'none', stroke: '#94a3b8', 'stroke-width': 1.5, 'stroke-dasharray': '5 5' });
        add('polyline', { 'data-curve': id, points: points.map(([a, b]) => `${x(a)},${y(b)}`).join(' '), fill: 'none', stroke: color, 'stroke-width': 3, 'stroke-linejoin': 'round' });
        if (id === 'customerCalibrationChart') points.forEach(([a, b]) => add('circle', { cx: x(a), cy: y(b), r: 4, fill: color, stroke: '#fff', 'stroke-width': 1.5 }));
        add('text', { x: 212, y: 281, 'text-anchor': 'middle', fill: '#475569', 'font-size': 12 }, xLabel);
        add('text', { x: 14, y: 125, transform: 'rotate(-90 14 125)', 'text-anchor': 'middle', fill: '#475569', 'font-size': 12 }, yLabel);
    }

    function renderEvaluation() {
        const evaluation = model.evaluation, metrics = evaluation.metrics;
        const dictionary = [['accuracy', 'Accuracy'], ['precision', 'Precision'], ['recall', 'Recall'], ['f1', 'F1-score'], ['roc_auc', 'ROC-AUC'], ['pr_auc', 'PR-AUC (AP)'], ['brier', 'Brier Score ↓'], ['ece_10_bins', 'Calibration ECE ↓']];
        const grid = $('customerMetrics');
        grid.replaceChildren();
        dictionary.forEach(([key, label]) => {
            const cell = document.createElement('dl');
            cell.className = 'cr-metric';
            const dt = document.createElement('dt');
            dt.textContent = label;
            const dd = document.createElement('dd');
            dd.dataset.customerMetric = key;
            dd.textContent = ['accuracy', 'precision', 'recall', 'f1'].includes(key) ? (metrics[key] * 100).toFixed(1) + '%' : metrics[key].toFixed(3);
            cell.append(dt, dd);
            grid.appendChild(cell);
        });
        const splits = evaluation.split_counts;
        $('customerEvaluationSummary').textContent = `${model.model_name} · Test ${splits.test.rows.toLocaleString('vi-VN')} hồ sơ tại 01/10/2011 · Train ${splits.train.rows.toLocaleString('vi-VN')} hồ sơ tại 01/04 và 01/06/2011. Metrics Precision, Recall và F1 dùng class 1 = có mua lại.`;
        $('customerCalibrationBadge').dataset.status = evaluation.calibration_status;
        $('customerCalibrationBadge').textContent = evaluation.calibration_status === 'PASS' ? 'Calibration đã kiểm tra' : 'Calibration cần thận trọng';
        $('customerCalibrationNote').textContent = `Brier ${metrics.brier.toFixed(3)} (baseline ${evaluation.constant_baseline_brier.toFixed(3)}), ECE ${metrics.ece_10_bins.toFixed(3)}. ${evaluation.calibration_status === 'WARNING' ? 'Xác suất test chưa đạt tiêu chí calibration; xem là ước lượng và cần hiệu chỉnh trên dữ liệu mới.' : 'Đạt tiêu chí ECE ≤ 0.05 và Brier tốt hơn baseline; chưa chứng minh phù hợp mọi doanh nghiệp.'}`;
        document.querySelectorAll('[data-customer-cm]').forEach(cell => {
            const [actual, predicted] = cell.dataset.customerCm.split(',').map(Number);
            cell.textContent = metrics.confusion_matrix[actual][predicted];
        });
        drawCurve('customerCalibrationChart', metrics.bins.map(bin => [bin.predicted, bin.observed]), 'Calibration trên tập test', 'Xác suất dự báo', 'Tỷ lệ mua lại thực tế', '#0f766e', 'diagonal');
        drawCurve('customerRocChart', evaluation.roc_curve.fpr.map((fpr, i) => [fpr, evaluation.roc_curve.tpr[i]]), `ROC-AUC ${metrics.roc_auc.toFixed(3)}`, 'False positive rate', 'True positive rate', '#2563eb', 'diagonal');
        drawCurve('customerPrChart', evaluation.pr_curve.recall.map((recall, i) => [recall, evaluation.pr_curve.precision[i]]), `Average precision ${metrics.pr_auc.toFixed(3)}`, 'Recall', 'Precision', '#7c3aed', splits.test.class_1 / splits.test.rows);
        $('customerDatasetSummary').textContent = `${model.dataset.raw_rows.toLocaleString('vi-VN')} dòng giao dịch gốc, 8 cột; ${model.dataset.clean_rows.toLocaleString('vi-VN')} dòng sản phẩm hợp lệ và ${model.dataset.clean_customers.toLocaleString('vi-VN')} khách sau lọc. Dataset không có target mua lại sẵn; target được tạo bằng cửa sổ giao dịch tương lai 60 ngày.`;
        $('customerSplitSummary').textContent = `Train: 01/04, 01/06/2011. Cohort 01/08/2011 tách theo khách cho calibration (${splits.calibration.rows}) và chọn mô hình/ngưỡng (${splits.selection.rows}). Test: 01/10/2011, cửa sổ kết thúc trước 30/11/2011. Nhãn của mỗi phần hoàn tất trước phần tiếp theo.`;
        const comparison = $('customerComparison');
        comparison.replaceChildren();
        evaluation.model_comparison.forEach(candidate => {
            const row = document.createElement('tr');
            row.dataset.selected = candidate.model === model.model_name;
            [candidate.model + (candidate.model === model.model_name ? ' · Được chọn' : ''), candidate.validation_metrics.roc_auc.toFixed(3), candidate.validation_metrics.pr_auc.toFixed(3), candidate.validation_metrics.f1.toFixed(3), candidate.validation_metrics.brier.toFixed(3), candidate.temporal_stability_auc.toFixed(3)].forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                row.appendChild(td);
            });
            comparison.appendChild(row);
        });
        $('customerSelectionReason').textContent = 'Ưu tiên mô hình dễ triển khai trong browser nếu kết quả validation nằm trong 0.015 ROC-AUC, 0.02 PR-AUC và 0.01 Brier so với tốt nhất. Nếu không có ứng viên đáp ứng, dùng ROC-AUC + PR-AUC − Brier. Test chỉ mở sau khi cố định lựa chọn; cột AUC theo thời gian kiểm tra train tháng 4 → validation tháng 6.';
        $('customerThresholdPolicy').textContent = `Ngưỡng phân loại ${(model.threshold * 100).toFixed(1)}% được chọn để tối đa macro-F1 trên selection với lưới 10–90%, bước 1%; khi bằng nhau ưu tiên gần 50%. Không giả định chi phí giữ chân chưa được đo.`;
        $('customerBandPolicy').textContent = `Mức thấp: dưới ${(model.recommendation_policy.low_upper_exclusive * 100).toFixed(1)}%; mức cao: từ ${(model.recommendation_policy.high_lower_inclusive * 100).toFixed(1)}%; còn lại: cần chăm sóc thêm. Ranh giới lấy từ phân vị 1/3 và 2/3 xác suất selection, mở rộng để nằm hai bên ngưỡng phân loại. Đây là phân nhóm chăm sóc minh họa, không phải ngưỡng ROI đã kiểm chứng.`;
    }

    async function loadModel() {
        fields.disabled = true;
        clearResult();
        try {
            const response = await fetch('./customer-return-model.json', { cache: 'no-cache' });
            if (!response.ok) throw Error('HTTP ' + response.status);
            model = CustomerReturnModel.validateModel(await response.json());
            const country = form.elements.namedItem('country');
            country.replaceChildren(new Option('Chọn quốc gia', ''));
            model.preprocessing.categories.forEach(value => country.add(new Option(value, value)));
            country.add(new Option('Quốc gia khác / chưa quan sát', '__UNKNOWN__'));
            renderEvaluation();
            status.textContent = 'Mô hình đã sẵn sàng. Có thể điền hồ sơ hoặc chọn một mẫu để khám phá.';
            fields.disabled = false;
            return true;
        } catch (failure) {
            model = null;
            status.textContent = 'Không tải được mô hình. Hãy tải lại trang và kiểm tra website được phục vụ qua HTTP cùng customer-return-model.json.';
            $('customerCalibrationBadge').textContent = 'Chưa có đánh giá';
            $('customerMetrics').textContent = 'Không tải được metrics.';
            document.querySelectorAll('[data-customer-cm]').forEach(cell => { cell.textContent = '—'; });
            for (const id of ['customerCalibrationChart', 'customerRocChart', 'customerPrChart', 'customerComparison']) $(id).replaceChildren();
            for (const id of ['customerEvaluationSummary', 'customerCalibrationNote', 'customerDatasetSummary', 'customerSplitSummary', 'customerSelectionReason', 'customerThresholdPolicy', 'customerBandPolicy']) $(id).textContent = '';
            return false;
        }
    }
    window.CustomerReturnPage = Object.freeze({ ready: loadModel(), getModel: () => model, getResult: () => lastResult, reload: loadModel });
})();
