"use strict";

const healthFeatureNames = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal"
];
const healthCategoryCodes = {
    sex: [0, 1], cp: [1, 2, 3, 4], fbs: [0, 1], restecg: [0, 1, 2],
    exang: [0, 1], slope: [1, 2, 3], ca: [0, 1, 2, 3], thal: [3, 6, 7]
};
const healthFeatureLabels = {
    age: "Tuổi",
    sex: "Giới tính",
    cp: "Loại đau ngực",
    trestbps: "Huyết áp khi nghỉ",
    chol: "Cholesterol",
    fbs: "Đường huyết lúc đói > 120 mg/dL",
    restecg: "Điện tâm đồ lúc nghỉ",
    thalach: "Nhịp tim tối đa đạt được",
    exang: "Đau thắt ngực khi vận động",
    oldpeak: "Mức ST chênh xuống khi vận động",
    slope: "Độ dốc đoạn ST khi vận động",
    ca: "Số mạch vành chính nhìn thấy qua chụp huỳnh quang",
    thal: "Kết quả thal trong bộ dữ liệu tim"
};

function healthFeatureDisplayName(feature) {
    return `${healthFeatureLabels[feature] || feature} (${feature})`;
}
const healthForm = document.getElementById("healthForm");
const healthFields = document.getElementById("healthFields");
const healthStatus = document.getElementById("healthModelStatus");
const healthResult = document.getElementById("healthResult");
const healthError = document.getElementById("healthInputError");
let healthModel = null;
const healthSamples = [
    { age: 63, sex: 1, cp: 1, trestbps: 145, chol: 233, fbs: 1, restecg: 2, thalach: 150, exang: 0, oldpeak: 2.3, slope: 3, ca: 0, thal: 6 },
    { age: 67, sex: 1, cp: 4, trestbps: 160, chol: 286, fbs: 0, restecg: 2, thalach: 108, exang: 1, oldpeak: 1.5, slope: 2, ca: 3, thal: 3 }
];

function validateHealthModel(model) {
    if (model?.schema_version !== 1 || !Array.isArray(model.features) ||
        model.features.length !== healthFeatureNames.length ||
        !model.features.every((name, i) => name === healthFeatureNames[i])) {
        throw new Error("Thứ tự đặc trưng trong model không hợp lệ.");
    }
    for (const key of ["scaler_mean", "scaler_scale", "coefficients"]) {
        if (!Array.isArray(model[key]) || model[key].length !== model.features.length ||
            !model[key].every(Number.isFinite)) throw new Error(`Model thiếu ${key} hợp lệ.`);
    }
    if (model.scaler_scale.some(value => value <= 0) || !Number.isFinite(model.intercept) ||
        !model.features.every(name => Number.isFinite(model.medians?.[name])) || model.threshold !== 0.5) {
        throw new Error("Tham số chuẩn hóa hoặc phân loại không hợp lệ.");
    }
    for (const key of ["accuracy", "precision", "recall", "f1", "roc_auc"]) {
        const value = model.metrics?.[key];
        if (!Number.isFinite(value) || value < 0 || value > 1) throw new Error("Metrics không hợp lệ.");
    }
    for (const [name, codes] of Object.entries(healthCategoryCodes)) {
        if (JSON.stringify(model.category_codes?.[name]) !== JSON.stringify(codes)) {
            throw new Error(`Mã category ${name} không khớp Cleveland.`);
        }
    }
    if (!Number.isInteger(model.training?.train_rows) || !Number.isInteger(model.training?.test_rows) ||
        model.training.train_rows <= 0 || model.training.test_rows <= 0) {
        throw new Error("Thông tin tập đánh giá không hợp lệ.");
    }
    const matrix = model.confusion_matrix;
    if (!Array.isArray(matrix) || matrix.length !== 2 || !matrix.every(row =>
        Array.isArray(row) && row.length === 2 && row.every(value => Number.isInteger(value) && value >= 0)) ||
        matrix.flat().reduce((sum, value) => sum + value, 0) !== model.training.test_rows) {
        throw new Error("Confusion matrix không hợp lệ.");
    }
    const { fpr, tpr } = model.roc_curve || {};
    if (!Array.isArray(fpr) || !Array.isArray(tpr) || fpr.length < 2 || fpr.length !== tpr.length ||
        ![fpr, tpr].every(values => values.every((value, i) => Number.isFinite(value) && value >= 0 && value <= 1 &&
            (i === 0 || value >= values[i - 1])) && values[0] === 0 && values[values.length - 1] === 1)) {
        throw new Error("ROC curve không hợp lệ.");
    }
    const area = fpr.slice(1).reduce((sum, value, i) => sum + (value - fpr[i]) * (tpr[i + 1] + tpr[i]) / 2, 0);
    if (Math.abs(area - model.metrics.roc_auc) > 1e-9) throw new Error("ROC curve không khớp ROC-AUC.");
    return model;
}

function isHealthMissing(value) {
    return value == null || (typeof value === "number" && Number.isNaN(value)) ||
        ["", "?", "null", "nan", "na", "n/a", "none"].includes(String(value).trim().toLowerCase());
}

function predictHealthProbability(model, input) {
    const imputed = [];
    const values = model.features.map(name => {
        if (isHealthMissing(input[name])) {
            imputed.push(name);
            return model.medians[name];
        }
        const value = Number(input[name]);
        if (!Number.isFinite(value)) throw new Error(`Giá trị ${name} phải là số hữu hạn.`);
        if (healthCategoryCodes[name] && !healthCategoryCodes[name].includes(value)) {
            throw new Error(`Mã ${name} không hợp lệ.`);
        }
        if (!healthCategoryCodes[name] && (value < 0 ||
            (name !== "oldpeak" && (!Number.isInteger(value) || value === 0)) ||
            (name === "age" && value > 120))) {
            throw new Error(`Giá trị ${name} nằm ngoài phạm vi nhập cho phép.`);
        }
        return value;
    });
    const linear = values.reduce((sum, value, i) =>
        sum + model.coefficients[i] * ((value - model.scaler_mean[i]) / model.scaler_scale[i]), model.intercept);
    if (!Number.isFinite(linear)) throw new Error("Giá trị nhập quá lớn để tính dự đoán.");
    // Equivalent sigmoid, evaluated stably for large positive/negative logits.
    const probability = linear >= 0
        ? 1 / (1 + Math.exp(-linear))
        : Math.exp(linear) / (1 + Math.exp(linear));
    return { probability, imputed };
}

function calculateHealthContributions(model, input) {
    const contributions = model.features.map((name, i) => {
        const value = isHealthMissing(input[name]) ? model.medians[name] : Number(input[name]);
        const standardizedValue = (value - model.scaler_mean[i]) / model.scaler_scale[i];
        return { feature: name, standardizedValue, contribution: standardizedValue * model.coefficients[i] };
    });
    const total = contributions.reduce((sum, item) => sum + item.contribution, 0);
    return { contributions, total, linear: model.intercept + total };
}

function signedHealthNumber(value) {
    return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;
}

function renderHealthContributions(model, input) {
    const { contributions, total, linear } = calculateHealthContributions(model, input);
    const top = [...contributions].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 5);
    const maximum = Math.max(...top.map(item => Math.abs(item.contribution)), 1e-12);
    const chart = document.getElementById("healthContributionChart");
    chart.replaceChildren();
    top.forEach(item => {
        const row = document.createElement("li");
        row.dataset.feature = item.feature;
        row.dataset.contribution = item.contribution;
        row.title = `${healthFeatureDisplayName(item.feature)}: mức đóng góp ${signedHealthNumber(item.contribution)}`;
        const label = document.createElement("div");
        label.className = "health-contribution-label";
        const name = document.createElement("strong");
        name.className = "health-feature-name";
        name.textContent = healthFeatureLabels[item.feature] || item.feature;
        const technicalName = document.createElement("span");
        technicalName.className = "health-feature-key";
        technicalName.textContent = ` (${item.feature})`;
        name.appendChild(technicalName);
        const value = document.createElement("span");
        value.className = `health-contribution-value ${item.contribution >= 0 ? "health-positive" : "health-negative"}`;
        value.textContent = signedHealthNumber(item.contribution);
        label.append(name, value);
        const track = document.createElement("div");
        track.className = "health-contribution-track";
        track.setAttribute("aria-hidden", "true");
        const bar = document.createElement("span");
        bar.className = `health-contribution-bar ${item.contribution >= 0 ? "positive" : "negative"}`;
        bar.style.width = `${Math.abs(item.contribution) / maximum * 50}%`;
        track.appendChild(bar);
        const direction = document.createElement("small");
        direction.textContent = item.contribution === 0 ? "Không làm nghiêng kết quả mô hình" :
            item.contribution > 0 ? "Đẩy dự đoán về nhóm bệnh tim (Class 1)" :
                "Đẩy dự đoán về nhóm không bệnh tim (Class 0)";
        row.append(label, track, direction);
        chart.appendChild(row);
    });
    document.getElementById("healthLinearSummary").textContent =
        `Intercept ${signedHealthNumber(model.intercept)} + tổng mức đóng góp của 13 đặc trưng ${signedHealthNumber(total)} = linear score ${signedHealthNumber(linear)}. Biểu đồ chỉ hiển thị Top 5.`;
}

function renderHealthPerformance(model) {
    const matrix = model.confusion_matrix;
    const largest = Math.max(...matrix.flat(), 1);
    document.querySelectorAll("[data-cm]").forEach(cell => {
        const [actual, predicted] = cell.dataset.cm.split(",").map(Number);
        const count = matrix[actual][predicted];
        cell.textContent = count;
        const rgb = actual === predicted ? "56, 189, 248" : "251, 146, 60";
        cell.style.backgroundColor = `rgba(${rgb}, ${0.12 + count / largest * 0.3})`;
    });
    document.getElementById("healthConfusionSummary").textContent =
        `${matrix[0][0] + matrix[1][1]}/${model.training.test_rows} mẫu phân loại đúng. Đường chéo: đúng class; ô ngoài đường chéo: nhầm class.`;
    const svg = document.getElementById("healthRocChart");
    svg.replaceChildren();
    const add = (tag, attributes, content) => {
        const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
        for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
        if (content !== undefined) element.textContent = content;
        svg.appendChild(element);
        return element;
    };
    add("title", {}, `ROC-AUC ${model.metrics.roc_auc.toFixed(3)} trên ${model.training.test_rows} mẫu test`);
    add("desc", {}, "Trục ngang: false positive rate. Trục dọc: true positive rate. Đường nét đứt là mốc AUC 0.5.");
    const left = 52, top = 20, width = 316, height = 220;
    [0, 0.5, 1].forEach(tick => {
        const x = left + tick * width, y = top + (1 - tick) * height;
        add("line", { x1: x, y1: top, x2: x, y2: top + height, stroke: "#334155" });
        add("line", { x1: left, y1: y, x2: left + width, y2: y, stroke: "#334155" });
        add("text", { x, y: top + height + 22, "text-anchor": "middle", fill: "#94a3b8", "font-size": 12 }, tick.toFixed(1));
        add("text", { x: left - 10, y: y + 4, "text-anchor": "end", fill: "#94a3b8", "font-size": 12 }, tick.toFixed(1));
    });
    add("line", { x1: left, y1: top + height, x2: left + width, y2: top, stroke: "#94a3b8", "stroke-dasharray": "5 5" });
    const points = model.roc_curve.fpr.map((fpr, i) => `${left + fpr * width},${top + (1 - model.roc_curve.tpr[i]) * height}`).join(" ");
    add("polyline", { id: "healthRocLine", points, fill: "none", stroke: "#38bdf8", "stroke-width": 3, "stroke-linejoin": "round" });
    add("text", { x: left + width / 2, y: 290, "text-anchor": "middle", fill: "#cbd5e1", "font-size": 13 }, "False positive rate (FPR)");
    add("text", { x: 15, y: top + height / 2, transform: `rotate(-90 15 ${top + height / 2})`, "text-anchor": "middle", fill: "#cbd5e1", "font-size": 13 }, "True positive rate (TPR)");
    document.getElementById("healthRocSummary").textContent =
        `ROC-AUC: ${model.metrics.roc_auc.toFixed(3)}. Nét đứt: mốc tham chiếu AUC = 0.5.`;
}

function clearHealthFieldErrors() {
    healthFeatureNames.forEach(name => {
        healthForm.elements.namedItem(name).removeAttribute("aria-invalid");
        const error = document.getElementById(`health-${name}-error`);
        error.textContent = "";
        error.hidden = true;
    });
}

function validateHealthField(field) {
    const name = field.name;
    let message = "";
    if (field.validity.badInput) message = "Vui lòng nhập một số hữu hạn hợp lệ.";
    else if (field.required && isHealthMissing(field.value)) message = "Vui lòng điền trường bắt buộc này.";
    else if (field.value !== "") {
        const value = Number(field.value);
        if (!Number.isFinite(value)) message = "Giá trị phải là số hữu hạn.";
        else if (healthCategoryCodes[name] && !healthCategoryCodes[name].includes(value)) message = "Vui lòng chọn một giá trị trong danh sách.";
        else if (field.type === "number") {
            if (value < Number(field.min)) message = `Giá trị phải từ ${field.min} trở lên.`;
            else if (field.max && value > Number(field.max)) message = `Giá trị không được vượt quá ${field.max}.`;
            else if (field.step === "1" && !Number.isInteger(value)) message = "Vui lòng nhập số nguyên.";
        }
    }
    const error = document.getElementById(`health-${name}-error`);
    error.textContent = message;
    error.hidden = !message;
    if (message) field.setAttribute("aria-invalid", "true");
    else field.removeAttribute("aria-invalid");
    return !message;
}

healthFeatureNames.forEach(name => {
    const field = healthForm.elements.namedItem(name);
    const error = document.createElement("small");
    error.id = `health-${name}-error`;
    error.className = "health-field-error";
    error.hidden = true;
    field.parentElement.appendChild(error);
    field.setAttribute("aria-describedby", [field.getAttribute("aria-describedby"), error.id].filter(Boolean).join(" "));
    field.addEventListener("blur", () => validateHealthField(field));
    field.addEventListener("input", () => validateHealthField(field));
    field.addEventListener("change", () => { clearHealthResult(); validateHealthField(field); });
});

document.querySelectorAll("[data-health-sample]").forEach(button => button.addEventListener("click", () => {
    const sample = healthSamples[Number(button.dataset.healthSample)];
    clearHealthResult();
    clearHealthFieldErrors();
    healthFeatureNames.forEach(name => { healthForm.elements.namedItem(name).value = sample[name]; });
    healthStatus.textContent = `Đã điền mẫu ${Number(button.dataset.healthSample) + 1} từ Cleveland. Bấm Dự đoán để xem model score.`;
}));

async function loadHealthModel() {
    try {
        const response = await fetch("./health-model.json", { cache: "no-cache" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        healthModel = validateHealthModel(await response.json());
        document.querySelectorAll("[data-metric]").forEach(cell => {
            const key = cell.dataset.metric;
            cell.textContent = key === "roc_auc"
                ? healthModel.metrics[key].toFixed(3)
                : `${(healthModel.metrics[key] * 100).toFixed(1)}%`;
        });
        renderHealthPerformance(healthModel);
        document.getElementById("healthEvaluationInfo").textContent =
            `Đánh giá trên ${healthModel.training.test_rows} mẫu test độc lập; ` +
            `${healthModel.training.train_rows} mẫu train. Chia 80/20 có stratify, random_state = 42. ` +
            "Median và StandardScaler chỉ fit trên tập train.";
        healthStatus.textContent = "Mô hình đã sẵn sàng. Dự đoán được tính trên thiết bị của bạn.";
        healthStatus.classList.remove("health-error");
        healthFields.disabled = false;
    } catch (error) {
        healthModel = null;
        healthFields.disabled = true;
        clearHealthResult();
        document.querySelectorAll("[data-metric], [data-cm]").forEach(cell => { cell.textContent = "—"; });
        document.getElementById("healthRocChart").replaceChildren();
        for (const id of ["healthConfusionSummary", "healthRocSummary"]) document.getElementById(id).textContent = "";
        healthStatus.textContent = "Không tải được mô hình. Hãy tải lại trang và kiểm tra health-model.json được deploy cùng website. Nếu đang mở file trực tiếp, hãy dùng Live Server.";
        healthStatus.classList.add("health-error");
    }
}

healthForm.addEventListener("submit", event => {
    event.preventDefault();
    healthError.hidden = true;
    healthResult.hidden = true;
    if (!healthModel) return;
    try {
        const input = Object.fromEntries(healthFeatureNames.map(name => [name, healthForm.elements.namedItem(name).value]));
        const invalidFields = healthFeatureNames.map(name => healthForm.elements.namedItem(name)).filter(field => !validateHealthField(field));
        if (invalidFields.length) {
            healthError.textContent = `Vui lòng kiểm tra ${invalidFields.length} trường được đánh dấu bên dưới.`;
            healthError.hidden = false;
            invalidFields[0].focus();
            return;
        }
        const { probability, imputed } = predictHealthProbability(healthModel, input);
        document.getElementById("healthProbability").textContent = `${(probability * 100).toFixed(1)}%`;
        document.getElementById("healthGauge").value = probability * 100;
        const predictedClass = probability >= healthModel.threshold ? 1 : 0;
        document.getElementById("healthPredictedClass").textContent = predictedClass === 1
            ? "Bệnh tim (Class 1)" : "Không bệnh tim (Class 0)";
        document.getElementById("healthThreshold").textContent = `${healthModel.threshold * 100}%`;
        document.getElementById("healthPredictionMessage").textContent =
            `Mô hình nghiêng về nhóm ${predictedClass === 1 ? "bệnh tim" : "không bệnh tim"} trong dataset (Class ${predictedClass}).`;
        document.getElementById("healthImputationNote").textContent = imputed.length
            ? `Đã dùng median tập train cho ${imputed.length} đặc trưng chưa nhập: ${imputed.map(healthFeatureDisplayName).join(", ")}. Điền đủ đặc trưng để mô hình phản ánh dữ liệu nhập tốt hơn.`
            : "Đã sử dụng đủ 13 đặc trưng bạn nhập.";
        healthResult.hidden = false;
        renderHealthContributions(healthModel, input);
    } catch (error) {
        healthError.textContent = error.message;
        healthError.hidden = false;
    }
});

function clearHealthResult() {
    healthResult.hidden = true;
    healthError.hidden = true;
    for (const id of ["healthProbability", "healthPredictionMessage", "healthImputationNote"]) {
        document.getElementById(id).textContent = "";
    }
    document.getElementById("healthGauge").value = 0;
    document.getElementById("healthContributionChart").replaceChildren();
    document.getElementById("healthLinearSummary").textContent = "";
    document.getElementById("healthPredictedClass").textContent = "—";
    document.getElementById("healthThreshold").textContent = "—";
}

healthForm.addEventListener("reset", () => { clearHealthResult(); clearHealthFieldErrors(); });
healthForm.addEventListener("input", clearHealthResult);
loadHealthModel();
