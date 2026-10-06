"use strict";
/* Pure inference from the exported artifact. No network, storage or UI dependency. */
(() => {
    const sigmoid = value => value >= 0 ? 1 / (1 + Math.exp(-value)) : Math.exp(value) / (1 + Math.exp(value));
    const finiteArray = (values, length) => Array.isArray(values) && values.length === length && values.every(Number.isFinite);
    // Vietnam is not a training category: retain all-zero unseen encoding.
    const isVietnam = value => ['vietnam', 'viet nam', 'vn'].includes(String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase().replace(/\s+/g, ' '));
    const normalizeCountry = value => isVietnam(value) ? '__UNKNOWN__' : String(value).trim();

    function validateModel(model) {
        const pre = model?.preprocessing, estimator = model?.estimator;
        if (model?.schema_version !== 1 || model.horizon_days !== 60 || model.lookback_days !== 90 || !pre || !estimator ||
            !Array.isArray(pre.numeric_features) || pre.numeric_features.length !== 6 || new Set(pre.numeric_features).size !== 6 ||
            pre.numeric_features.join(',') !== 'recency_days,tenure_days,orders_90d,monetary_90d,products_90d,avg_purchase_gap_days' ||
            pre.numeric_transform !== 'log1p' || pre.categorical_feature !== 'country' ||
            !finiteArray(pre.scaler_mean, 6) || !finiteArray(pre.scaler_scale, 6) || pre.scaler_scale.some(v => v <= 0) ||
            !Array.isArray(pre.categories) || !pre.categories.length || pre.categories.some(v => typeof v !== 'string') ||
            new Set(pre.categories).size !== pre.categories.length) throw Error('Model hoặc thông tin tiền xử lý không hợp lệ.');
        const size = 6 + pre.categories.length;
        if (JSON.stringify(pre.feature_order) !== JSON.stringify([...pre.numeric_features, ...pre.categories.map(c => `country=${c}`)])) throw Error('Thứ tự đặc trưng không hợp lệ.');
        if (!(model.threshold > 0 && model.threshold < 1) ||
            !(model.recommendation_policy?.low_upper_exclusive > 0 && model.recommendation_policy.low_upper_exclusive <= model.threshold &&
                model.recommendation_policy.high_lower_inclusive >= model.threshold && model.recommendation_policy.high_lower_inclusive < 1 &&
                model.recommendation_policy.low_upper_exclusive < model.recommendation_policy.high_lower_inclusive)) throw Error('Ngưỡng mô hình không hợp lệ.');
        if (!['none', 'sigmoid'].includes(model.calibration?.method) || !Number.isFinite(model.calibration.intercept) ||
            !Number.isFinite(model.calibration.coefficient) || model.calibration.coefficient <= 0) throw Error('Calibration không hợp lệ.');
        if (estimator.kind === 'logistic_regression') {
            if (!finiteArray(estimator.coefficients, size) || !Number.isFinite(estimator.intercept)) throw Error('Hệ số mô hình không hợp lệ.');
        } else if (['gradient_boosting', 'random_forest'].includes(estimator.kind)) {
            if (!Array.isArray(estimator.trees) || !estimator.trees.length) throw Error('Thiếu cây quyết định.');
            if (estimator.kind === 'gradient_boosting' && (!Number.isFinite(estimator.intercept) || !(estimator.learning_rate > 0))) throw Error('Tham số boosting không hợp lệ.');
            for (const tree of estimator.trees) {
                const n = tree.value?.length;
                if (!n || !['left', 'right', 'feature', 'threshold', 'value'].every(key => finiteArray(tree[key], n))) throw Error('Dữ liệu cây không hợp lệ.');
                for (let i = 0; i < n; i++) {
                    if (tree.left[i] === -1 && tree.right[i] === -1) continue;
                    if (![tree.left[i], tree.right[i]].every(child => Number.isInteger(child) && child > i && child < n) ||
                        !Number.isInteger(tree.feature[i]) || tree.feature[i] < 0 || tree.feature[i] >= size) throw Error('Cấu trúc cây không hợp lệ.');
                }
            }
        } else throw Error('Loại mô hình chưa được hỗ trợ.');
        if (!Array.isArray(model.feature_metadata) || model.feature_metadata.length !== 6 ||
            model.feature_metadata.some((f, i) => f.name !== pre.numeric_features[i] || typeof f.label !== 'string' ||
                !Number.isFinite(f.training_range?.min) || !Number.isFinite(f.training_range?.max))) throw Error('Metadata đặc trưng không hợp lệ.');
        const evaluation = model.evaluation, metrics = evaluation?.metrics, counts = evaluation?.split_counts;
        if (!metrics || !['accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc', 'brier', 'ece_10_bins'].every(key => Number.isFinite(metrics[key]) && metrics[key] >= 0 && metrics[key] <= 1) ||
            !counts || !['train', 'calibration', 'selection', 'test'].every(key => Number.isInteger(counts[key]?.rows) && counts[key].rows > 0 &&
                Number.isInteger(counts[key].class_0) && Number.isInteger(counts[key].class_1) && counts[key].class_0 >= 0 && counts[key].class_1 >= 0 &&
                counts[key].class_0 + counts[key].class_1 === counts[key].rows) ||
            !Array.isArray(metrics.confusion_matrix) || metrics.confusion_matrix.length !== 2 || !metrics.confusion_matrix.every(row => finiteArray(row, 2) && row.every(v => Number.isInteger(v) && v >= 0)) ||
            metrics.confusion_matrix.flat().reduce((sum, value) => sum + value, 0) !== counts.test.rows ||
            !['PASS', 'WARNING'].includes(evaluation.calibration_status) || !Number.isFinite(evaluation.constant_baseline_brier) ||
            !Array.isArray(metrics.bins) || !metrics.bins.length || metrics.bins.some(bin => !Number.isInteger(bin.count) || bin.count <= 0 || !Number.isFinite(bin.predicted) || !Number.isFinite(bin.observed))) throw Error('Dữ liệu đánh giá mô hình không hợp lệ.');
        for (const [curve, x, y] of [[evaluation.roc_curve, 'fpr', 'tpr'], [evaluation.pr_curve, 'recall', 'precision']]) {
            if (!curve || !Array.isArray(curve[x]) || curve[x].length < 2 || !finiteArray(curve[y], curve[x].length) ||
                ![...curve[x], ...curve[y]].every(v => Number.isFinite(v) && v >= 0 && v <= 1)) throw Error('Dữ liệu biểu đồ không hợp lệ.');
        }
        if (!Array.isArray(model.samples) || !['high', 'medium', 'low'].every(band => model.samples.some(sample => sample.band === band)) ||
            !Array.isArray(evaluation.model_comparison) || evaluation.model_comparison.length !== 3) throw Error('Thiếu mẫu hoặc kết quả so sánh.');
        return model;
    }

    function validateInput(model, input) {
        const values = {};
        for (const name of model.preprocessing.numeric_features) {
            const raw = input[name];
            if (raw == null || String(raw).trim() === '') throw Error('Vui lòng điền đầy đủ các trường dữ liệu.');
            const value = Number(raw);
            if (!Number.isFinite(value) || value < 0 || value > 1e9) throw Error('Các giá trị phải là số hữu hạn không âm, trong phạm vi cho phép.');
            if (['recency_days', 'tenure_days', 'orders_90d', 'products_90d'].includes(name) && !Number.isInteger(value)) throw Error('Ngày, số đơn và số sản phẩm phải là số nguyên.');
            values[name] = value;
        }
        if (values.recency_days > values.tenure_days) throw Error('Thời gian từ lần mua gần nhất không thể lớn hơn thời gian đã là khách hàng.');
        if ((values.orders_90d === 0) !== (values.monetary_90d === 0) || (values.orders_90d === 0) !== (values.products_90d === 0)) throw Error('Số đơn, chi tiêu và số sản phẩm trong 90 ngày phải cùng bằng 0 hoặc cùng lớn hơn 0.');
        // The training lookback includes cutoff - 90 days; whole-day recency
        // equal to 90 can therefore have an order exactly on that boundary.
        if (values.recency_days > 90 && values.orders_90d > 0) throw Error('Khách chưa mua trong hơn 90 ngày thì số đơn trong 90 ngày phải bằng 0.');
        if (values.recency_days < 90 && values.orders_90d === 0) throw Error('Nếu lần mua gần nhất chưa tới 90 ngày, cần có ít nhất một đơn trong 90 ngày.');
        // Tenure is whole days, while gaps keep fractional days.
        if (values.avg_purchase_gap_days >= values.tenure_days + 1) throw Error('Khoảng cách trung bình giữa các đơn không thể lớn hơn thời gian đã là khách hàng.');
        if (typeof input.country !== 'string' || !input.country.trim() || input.country.length > 100) throw Error('Vui lòng chọn quốc gia hợp lệ.');
        values.country = input.country.trim();
        return values;
    }

    function predict(model, input) {
        const values = validateInput(model, input), pre = model.preprocessing, estimator = model.estimator;
        const vector = pre.numeric_features.map((name, i) => (Math.log1p(values[name]) - pre.scaler_mean[i]) / pre.scaler_scale[i]);
        const modelCountry = normalizeCountry(values.country);
        vector.push(...pre.categories.map(category => Number(category === modelCountry)));
        const contributions = vector.map(() => 0);
        let raw, baseline;
        if (estimator.kind === 'logistic_regression') {
            baseline = estimator.intercept;
            vector.forEach((value, i) => { contributions[i] = value * estimator.coefficients[i]; });
            raw = contributions.reduce((sum, value) => sum + value, baseline);
        } else {
            // sklearn trees use float32 inputs, including at split boundaries.
            const treeVector = vector.map(Math.fround);
            baseline = estimator.kind === 'gradient_boosting' ? estimator.intercept : 0;
            raw = baseline;
            const weight = estimator.kind === 'gradient_boosting' ? estimator.learning_rate : 1 / estimator.trees.length;
            for (const tree of estimator.trees) {
                baseline += weight * tree.value[0];
                let node = 0;
                while (tree.left[node] !== -1) {
                    const feature = tree.feature[node];
                    const child = treeVector[feature] <= tree.threshold[node] ? tree.left[node] : tree.right[node];
                    contributions[feature] += weight * (tree.value[child] - tree.value[node]);
                    node = child;
                }
                raw += weight * tree.value[node];
            }
        }
        const cal = model.calibration;
        let logit, probability, explanationUnit;
        if (cal.method === 'sigmoid') {
            logit = cal.coefficient * raw + cal.intercept;
            baseline = cal.coefficient * baseline + cal.intercept;
            contributions.forEach((v, i) => { contributions[i] = v * cal.coefficient; });
            probability = sigmoid(logit);
            explanationUnit = 'log-odds';
        } else if (estimator.kind === 'random_forest') {
            probability = raw;
            explanationUnit = 'probability';
        } else {
            logit = raw;
            probability = sigmoid(raw);
            explanationUnit = 'log-odds';
        }
        const factors = pre.numeric_features.map((name, i) => ({ feature: name, label: model.feature_metadata[i].label, contribution: contributions[i] }));
        factors.push({ feature: 'country', label: 'Quốc gia của khách hàng', contribution: contributions.slice(6).reduce((sum, v) => sum + v, 0) });
        factors.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
        const policy = model.recommendation_policy;
        const band = probability < policy.low_upper_exclusive ? 'low' : (probability >= policy.high_lower_inclusive ? 'high' : 'medium');
        const warnings = model.feature_metadata.filter(f => values[f.name] < f.training_range.min || values[f.name] > f.training_range.max).map(f => f.label);
        if (!pre.categories.includes(values.country)) warnings.push('Quốc gia chưa xuất hiện trong tập huấn luyện');
        return { probability, nonReturnProbability: 1 - probability, predictedClass: Number(probability >= model.threshold),
            band, factors, baseline, explanationUnit, explanationScore: logit ?? probability, warnings, values };
    }

    // Round the displayed complement, too: labels always add to exactly 100.0%.
    function percentageLabels(probability) {
        const returnTenths = Math.round(probability * 1000);
        return { returned: (returnTenths / 10).toFixed(1) + '%', nonReturned: ((1000 - returnTenths) / 10).toFixed(1) + '%' };
    }
    globalThis.CustomerReturnModel = Object.freeze({ validateModel, validateInput, predict, percentageLabels, normalizeCountry, isVietnam });
})();
