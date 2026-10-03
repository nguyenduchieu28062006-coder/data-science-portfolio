// ==========================================
// SMART DATA ANALYZER
// ==========================================

const csvFile = document.getElementById("csvFile");

const xColumnSelect =
    document.getElementById("xColumnSelect");

const yColumnSelect =
    document.getElementById("yColumnSelect");

const aggregationSelect =
    document.getElementById("aggregationSelect");

const chartTypeSelect =
    document.getElementById("chartTypeSelect");

const drawChartBtn =
    document.getElementById("drawChartBtn");

const suggestionList =
    document.getElementById("suggestionList");

const suggestionStatus =
    document.getElementById("suggestionStatus");

const chartInsight =
    document.getElementById("chartInsight");


let currentHeaders = [];
let currentRows = [];
let columnInfo = Object.create(null);

let dataChart = null;


// ==========================================
// KIỂM TRA GIÁ TRỊ THIẾU
// ==========================================

function isMissing(value) {

    if (value === undefined || value === null) {
        return true;
    }

    const text =
        String(value).trim().toLowerCase();

    return (
        text === "" ||
        text === "null" ||
        text === "nan" ||
        text === "na" ||
        text === "n/a" ||
        text === "none"
    );
}


// ==========================================
// CHUYỂN DỮ LIỆU SANG SỐ
// ==========================================

function toNumber(value) {

    if (isMissing(value)) {
        return NaN;
    }

    let text =
        String(value).trim();

    // Loại bỏ một số ký hiệu thường gặp
    text = text.replace(
        /[$₫€£%\s]/g,
        ""
    );

    return text === "" ? NaN : Number(text);
}


// ==========================================
// ĐỌC FILE CSV
// ==========================================

let cleaningReport = { missing: 0, duplicates: 0, emptyColumns: 0, emptyRows: 0 };
let uploadedName = "dataset";
let uploadVersion = 0;
const primaryColor = document.getElementById("primaryColor");
const categoryColorMap = new Map();
const autoCategoryColorMap = new Map();
const categoryPalette = [
    "#38bdf8", "#fb923c", "#a78bfa", "#34d399", "#f472b6",
    "#facc15", "#22d3ee", "#f87171", "#a3e635", "#818cf8"
];

function generateCategoryColor(index) {
    if (index < categoryPalette.length) return categoryPalette[index];
    // Golden-angle spacing spreads additional hues across the color wheel.
    const hue = ((index - categoryPalette.length) * 137.508 + 17) % 360;
    const saturation = [0.72, 0.85, 0.64][Math.floor(index / 12) % 3];
    const lightness = [0.65, 0.57, 0.73][Math.floor(index / 36) % 3];
    const amplitude = saturation * Math.min(lightness, 1 - lightness);
    const channel = offset => {
        const position = (offset + hue / 30) % 12;
        const value = lightness - amplitude * Math.max(-1, Math.min(position - 3, 9 - position, 1));
        return Math.round(value * 255).toString(16).padStart(2, "0");
    };
    // Color inputs require hex rather than HSL strings.
    return `#${channel(0)}${channel(8)}${channel(4)}`;
}

function getCategoryColor(column, category) {
    const key = JSON.stringify([column, category]);
    if (categoryColorMap.has(key)) return categoryColorMap.get(key);
    if (!autoCategoryColorMap.has(column)) autoCategoryColorMap.set(column, new Map());
    const colors = autoCategoryColorMap.get(column);
    if (!colors.has(category)) {
        const usedColors = new Set(colors.values());
        let index = colors.size;
        let color = generateCategoryColor(index);
        while (usedColors.has(color)) color = generateCategoryColor(++index);
        colors.set(category, color);
    }
    return colors.get(category);
}
let rawColumnProfile = [];
let cleanedColumnProfile = new Map();
let missingValuesChart = null;
let distributionChart = null;
const distributionColumnSelect = document.getElementById("distributionColumnSelect");

function medianOf(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : sorted[middle - 1] / 2 + sorted[middle] / 2;
}

function countValues(values) {
    const counts = new Map();
    values.forEach(value => counts.set(value, (counts.get(value) || 0) + 1));
    return counts;
}

function modeOf(values) {
    let value = "Unknown";
    let count = 0;
    countValues(values).forEach((frequency, category) => {
        if (frequency > count) { value = category; count = frequency; }
    });
    return { value, count };
}

function inferColumnType(values) {
    const valid = values.filter(value => !isMissing(value));
    if (!valid.length) return "text";
    const numericCount = valid.filter(value => Number.isFinite(toNumber(value))).length;
    // Infer numbers before considering cardinality or date parsing.
    if (numericCount / valid.length > 0.5) return "numeric";
    const dateCount = valid.filter(value => {
        const text = String(value).trim();
        return !Number.isFinite(toNumber(value)) && /[-/]/.test(text) && Number.isFinite(Date.parse(text));
    }).length;
    if (dateCount / valid.length >= 0.8) return "date";
    const unique = new Set(valid).size;
    return unique <= 20 || unique / valid.length <= 0.5 ? "category" : "text";
}

function cleanDataset(rawHeaders, rawRows) {
    const used = new Set();
    const headers = rawHeaders.map((name, index) => {
        const base = String(name || "").trim().toLowerCase().normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d")
            .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || `column_${index + 1}`;
        let header = base;
        let suffix = 2;
        while (used.has(header)) header = `${base}_${suffix++}`;
        used.add(header);
        return header;
    });
    const report = { missing: 0, duplicates: 0, emptyColumns: 0, emptyRows: 0 };
    const rawProfile = headers.map((header, i) => ({
        header,
        missing: rawRows.reduce((count, row) => count + Number(isMissing(row[i])), 0)
    }));
    let rows = rawRows.map(values => headers.map((_, i) => {
        const value = String(values[i] ?? "").trim();
        return isMissing(value) ? "" : value;
    })).filter(values => {
        if (values.every(isMissing)) { report.emptyRows++; return false; }
        return true;
    });
    const indices = headers.map((_, i) => i).filter(i => rows.some(row => !isMissing(row[i])));
    report.emptyColumns = headers.length - indices.length;
    const keptHeaders = indices.map(i => headers[i]);
    rows = rows.map(row => indices.map(i => row[i]));
    const seen = new Set();
    rows = rows.filter(row => {
        const key = JSON.stringify(row);
        if (seen.has(key)) { report.duplicates++; return false; }
        seen.add(key);
        return true;
    });
    keptHeaders.forEach((_, i) => {
        const observed = rows.map(row => row[i]).filter(value => !isMissing(value));
        const numeric = inferColumnType(observed) === "numeric";
        let replacement = "Unknown";
        if (numeric) {
            replacement = medianOf(observed.map(toNumber).filter(Number.isFinite));
        } else {
            replacement = modeOf(observed).value;
        }
        rows.forEach(row => {
            if (isMissing(row[i]) || (numeric && !Number.isFinite(toNumber(row[i])))) {
                row[i] = replacement;
                report.missing++;
            }
            else if (numeric) row[i] = toNumber(row[i]);
        });
    });
    // Imputation can make previously different rows identical.
    seen.clear();
    rows = rows.filter(row => {
        const key = JSON.stringify(row);
        if (seen.has(key)) { report.duplicates++; return false; }
        seen.add(key);
        return true;
    });
    return { headers: keptHeaders, rows: rows.map(values => Object.fromEntries(keptHeaders.map((header, i) => [header, values[i]]))), report, rawProfile };
}

csvFile.addEventListener("change", event => {
    const file = event.target.files[0];
    if (!file) return;
    const version = ++uploadVersion;
    document.getElementById("cleaningStatus").textContent = "Đang đọc và làm sạch CSV…";
    Papa.parse(file, {
        header: false,
        skipEmptyLines: false,
        complete(result) {
            if (version !== uploadVersion) return;
            if (result.errors.length || result.data.length < 2 || result.data.slice(1).some(row => row.length > result.data[0].length)) {
                document.getElementById("cleaningStatus").textContent = "CSV không hợp lệ hoặc không có dữ liệu. Dữ liệu trước đó vẫn được giữ lại.";
                return;
            }
            const cleaned = cleanDataset(result.data[0], result.data.slice(1));
            currentHeaders = cleaned.headers;
            currentRows = cleaned.rows;
            cleaningReport = cleaned.report;
            rawColumnProfile = cleaned.rawProfile;
            uploadedName = file.name.replace(/\.csv$/i, "");
            destroyChart();
            categoryColorMap.clear();
            autoCategoryColorMap.clear();
            document.getElementById("categoryColorPanel").hidden = true;
            chartInsight.textContent = "Chưa có biểu đồ.";
            columnInfo = Object.create(null);
            updateOverview();
            showTable();
            analyzeColumns();
            renderDataProfile();
            createColumnOptions();
            document.getElementById("emptyColumnCount").textContent = cleaningReport.emptyColumns;
            document.getElementById("cleaningStatus").textContent = `Đã làm sạch ${currentRows.length} dòng; xóa ${cleaningReport.emptyRows} hàng rỗng. Median dùng cho cột số; mode dùng cho cột text (nếu hòa, chọn giá trị xuất hiện trước).`;
            document.getElementById("downloadCleanCsvBtn").disabled = !currentRows.length;
            createSuggestions();
        },
        error() {
            if (version === uploadVersion) document.getElementById("cleaningStatus").textContent = "Không đọc được file CSV.";
        }
    });
});

document.getElementById("downloadCleanCsvBtn").addEventListener("click", () => {
    if (!currentRows.length) return;
    const csv = Papa.unparse({ fields: currentHeaders, data: currentRows.map(row => currentHeaders.map(header => row[header])) });
    const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8;" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${uploadedName}_clean.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
});

function updateCategoryColors(labels = []) {
    const panel = document.getElementById("categoryColorPanel");
    panel.hidden = !["bar", "pie"].includes(chartTypeSelect.value) || !labels.length;
    const container = document.getElementById("categoryColors");
    container.replaceChildren();
    if (panel.hidden) return;
    labels.forEach(category => {
        const key = JSON.stringify([xColumnSelect.value, category]);
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "color";
        input.value = getCategoryColor(xColumnSelect.value, category);
        input.setAttribute("aria-label", `Màu cho ${category}`);
        input.addEventListener("input", () => {
            categoryColorMap.set(key, input.value);
            if (dataChart) {
                const colors = dataChart.data.labels.map(value => getCategoryColor(xColumnSelect.value, value));
                dataChart.data.datasets[0].backgroundColor = colors;
                dataChart.data.datasets[0].borderColor = colors;
                dataChart.update();
            }
        });
        label.append(input, document.createTextNode(category));
        container.appendChild(label);
    });
}

primaryColor.addEventListener("input", () => { if (dataChart) drawChart(); });
[xColumnSelect, yColumnSelect, aggregationSelect, chartTypeSelect].forEach(select => select.addEventListener("change", () => {
    document.getElementById("categoryColorPanel").hidden = true;
    aggregationSelect.disabled = chartTypeSelect.value === "scatter";
    if (xColumnSelect.value && yColumnSelect.value) drawChart();
}));

// ==========================================
// DATA PROFILE: raw missing counts and cleaned-data statistics
// ==========================================

function formatProfileNumber(value) {
    if (!Number.isFinite(value)) return "—";
    return Number(value.toPrecision(6)).toLocaleString("vi-VN", { maximumFractionDigits: 6 });
}

function buildColumnProfile(header) {
    const type = columnInfo[header].type;
    const values = currentRows.map(row => row[header]).filter(value => !isMissing(value));
    const profile = { type, values, valid: values.length, unique: new Set(values).size,
        cleanMissing: currentRows.length - values.length };
    if (type === "numeric" && values.length) {
        const numbers = values.map(toNumber).filter(Number.isFinite);
        // Welford's algorithm avoids subtracting two large squared sums.
        let mean = 0, squaredDeviations = 0;
        numbers.forEach((value, index) => {
            const delta = value - mean;
            mean += delta / (index + 1);
            squaredDeviations += delta * (value - mean);
        });
        Object.assign(profile, {
            mean, median: medianOf(numbers), std: Math.sqrt(Math.max(0, squaredDeviations / numbers.length)),
            min: numbers.reduce((a, b) => Math.min(a, b), Infinity),
            max: numbers.reduce((a, b) => Math.max(a, b), -Infinity)
        });
    } else if (type === "category" || type === "text") {
        profile.mode = modeOf(values);
    }
    return profile;
}

function createProfileChart(canvasId, type, labels, values, label, xTitle) {
    return new Chart(document.getElementById(canvasId).getContext("2d"), {
        type,
        data: { labels, datasets: [{ label, data: values, backgroundColor: "#38bdf8",
            borderColor: "#38bdf8", borderWidth: 1, tension: 0.2 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#e5e7eb" } } },
            scales: {
                x: { title: { display: true, text: xTitle, color: "#cbd5e1" },
                    ticks: { color: "#cbd5e1", maxRotation: 60 }, grid: { color: "#1e293b" } },
                y: { beginAtZero: true, title: { display: true, text: "Số lượng", color: "#cbd5e1" },
                    ticks: { color: "#cbd5e1", precision: 0 }, grid: { color: "#1e293b" } }
            }
        }
    });
}

function renderDataProfile() {
    cleanedColumnProfile = new Map(currentHeaders.map(header => [header, buildColumnProfile(header)]));
    const tbody = document.getElementById("profileTable").querySelector("tbody");
    tbody.replaceChildren();
    rawColumnProfile.forEach(raw => {
        const profile = cleanedColumnProfile.get(raw.header);
        const numeric = profile?.type === "numeric";
        const cells = [raw.header, profile?.type || "Đã xóa (cột rỗng)", profile?.valid || 0,
            raw.missing, profile?.unique || 0,
            ...["mean", "median", "std", "min", "max"].map(key => numeric ? formatProfileNumber(profile[key]) : "—"),
            profile?.mode?.value ?? "—", profile?.mode?.count ?? "—"];
        const tr = document.createElement("tr");
        cells.forEach(value => {
            const td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    if (missingValuesChart) missingValuesChart.destroy();
    missingValuesChart = rawColumnProfile.length ? createProfileChart("missingValuesChart", "bar",
        rawColumnProfile.map(column => column.header), rawColumnProfile.map(column => column.missing),
        "Missing ban đầu (raw)", "Tên cột") : null;
    distributionColumnSelect.replaceChildren();
    currentHeaders.forEach(header => {
        const option = document.createElement("option");
        option.value = header;
        option.textContent = `${header} (${columnInfo[header].type})`;
        distributionColumnSelect.appendChild(option);
    });
    distributionColumnSelect.disabled = !currentHeaders.length;
    distributionColumnSelect.value = currentHeaders[0] || "";
    renderColumnDistribution();
}

function buildHistogram(values) {
    const min = values.reduce((a, b) => Math.min(a, b), Infinity);
    const max = values.reduce((a, b) => Math.max(a, b), -Infinity);
    if (min === max) return { labels: [formatProfileNumber(min)], counts: [values.length] };
    const binCount = Math.min(30, Math.max(1, Math.ceil(Math.sqrt(values.length))));
    const counts = Array(binCount).fill(0);
    const width = (max - min) / binCount;
    values.forEach(value => counts[Math.min(binCount - 1, Math.floor((value - min) / width))]++);
    const labels = counts.map((_, i) => `${formatProfileNumber(min + i * width)} – ${formatProfileNumber(i === binCount - 1 ? max : min + (i + 1) * width)}${i === binCount - 1 ? " (gồm max)" : ""}`);
    return { labels, counts };
}

function buildDateDistribution(values) {
    const times = values.map(value => Date.parse(String(value))).filter(Number.isFinite);
    if (!times.length) return { labels: [], counts: [], unit: "ngày", skipped: values.length };
    const min = times.reduce((a, b) => Math.min(a, b), Infinity);
    const max = times.reduce((a, b) => Math.max(a, b), -Infinity);
    const days = (max - min) / 86400000;
    const unit = days > 365 * 3 ? "năm" : days >= 90 ? "tháng" : "ngày";
    const length = unit === "năm" ? 4 : unit === "tháng" ? 7 : 10;
    const counts = countValues(times.map(time => new Date(time).toISOString().slice(0, length)));
    const labels = [...counts.keys()].sort();
    return { labels, counts: labels.map(label => counts.get(label)), unit, skipped: values.length - times.length };
}

function renderColumnDistribution() {
    if (distributionChart) { distributionChart.destroy(); distributionChart = null; }
    const header = distributionColumnSelect.value;
    const profile = cleanedColumnProfile.get(header);
    const status = document.getElementById("distributionStatus");
    const insight = document.getElementById("profileInsight");
    if (!profile || !profile.valid) {
        status.textContent = "Chưa có dữ liệu sạch để phân tích.";
        insight.textContent = "Không có cột hợp lệ để tạo phân phối.";
        return;
    }
    let labels, counts, type = "bar", description, summary;
    if (profile.type === "numeric") {
        ({ labels, counts } = buildHistogram(profile.values.map(toNumber)));
        description = "Histogram dữ liệu sạch: các khoảng có độ rộng bằng nhau; biên phải chỉ được tính ở khoảng cuối.";
        summary = `${header} có trung bình ${formatProfileNumber(profile.mean)} và median ${formatProfileNumber(profile.median)}.`;
    } else if (profile.type === "date") {
        const distribution = buildDateDistribution(profile.values);
        ({ labels, counts } = distribution);
        type = "line";
        description = `Dữ liệu sạch nhóm theo ${distribution.unit} (UTC); chỉ hiển thị khoảng thời gian có dữ liệu.${distribution.skipped ? ` Bỏ qua ${distribution.skipped} giá trị không đọc được thành ngày.` : ""}`;
        summary = `${header} có ${profile.unique} giá trị khác nhau, trong ${labels.length} nhóm ${distribution.unit}.`;
    } else {
        const frequencies = countValues(profile.values);
        labels = [...frequencies.keys()];
        counts = [...frequencies.values()];
        description = "Số lượng từng category từ dữ liệu sạch.";
        summary = `${header} có ${profile.unique} giá trị khác nhau; ${profile.mode.value} xuất hiện nhiều nhất (${profile.mode.count} lần).`;
    }
    status.textContent = description;
    const missingSummary = profile.cleanMissing ? `${header} còn ${profile.cleanMissing} missing sau làm sạch.` : `${header} không còn missing sau làm sạch.`;
    insight.textContent = `${summary} ${missingSummary}`;
    distributionChart = createProfileChart("distributionChart", type, labels, counts, "Số lượng (dữ liệu sạch)", header);
}

distributionColumnSelect.addEventListener("change", renderColumnDistribution);

// ==========================================
// TỔNG QUAN DỮ LIỆU
// ==========================================

function updateOverview() {

    document.getElementById(
        "rowCount"
    ).textContent =
        currentRows.length;


    document.getElementById(
        "columnCount"
    ).textContent =
        currentHeaders.length;


    document.getElementById("missingCount").textContent = cleaningReport.missing;
    document.getElementById("duplicateCount").textContent = cleaningReport.duplicates;
}

// ==========================================
// HIỂN THỊ BẢNG
// ==========================================

function showTable() {

    const table =
        document.getElementById(
            "dataTable"
        );

    const thead =
        table.querySelector("thead");

    const tbody =
        table.querySelector("tbody");


    thead.innerHTML = "";
    tbody.innerHTML = "";


    // Header
    const headerRow =
        document.createElement("tr");


    currentHeaders.forEach(header => {

        const th =
            document.createElement("th");

        th.textContent =
            header;

        headerRow.appendChild(th);

    });


    thead.appendChild(
        headerRow
    );


    // 10 dòng đầu
    currentRows
        .slice(0, 10)
        .forEach(row => {

            const tr =
                document.createElement("tr");


            currentHeaders.forEach(
                header => {

                    const td =
                        document.createElement(
                            "td"
                        );


                    td.textContent =
                        isMissing(row[header])
                            ? "—"
                            : row[header];


                    tr.appendChild(td);

                }
            );


            tbody.appendChild(tr);

        });

}


// ==========================================
// NHẬN DIỆN KIỂU DỮ LIỆU
// ==========================================

function analyzeColumns() {

    columnInfo = Object.create(null);


    currentHeaders.forEach(header => {

        const values =
            currentRows
                .map(row => row[header])
                .filter(
                    value =>
                        !isMissing(value)
                );


        const uniqueValues =
            new Set(values);


        const type = inferColumnType(values);

        // ===========================
        // Phát hiện ID
        // ===========================

        const normalizedName =
            header
                .toLowerCase()
                .replace(/\s/g, "_");


        const isId =
            normalizedName === "id" ||
            normalizedName.endsWith("_id") ||
            normalizedName.includes(
                "student_id"
            ) ||
            normalizedName.includes(
                "customer_id"
            );


        columnInfo[header] = {

            type: type,

            unique:
                uniqueValues.size,

            isId: isId

        };

    });

}


// ==========================================
// ĐƯA CÁC CỘT VÀO X / Y
// ==========================================

function createColumnOptions() {

    xColumnSelect.innerHTML =
        '<option value="">-- Chọn cột X --</option>';


    yColumnSelect.innerHTML =
        '<option value="">-- Chọn cột Y --</option>';


    currentHeaders.forEach(header => {

        const type =
            columnInfo[header].type;


        const xOption =
            document.createElement(
                "option"
            );

        xOption.value =
            header;

        xOption.textContent =
            `${header} (${type})`;


        xColumnSelect.appendChild(
            xOption
        );


        const yOption =
            document.createElement(
                "option"
            );

        yOption.value =
            header;

        yOption.textContent =
            `${header} (${type})`;


        yColumnSelect.appendChild(
            yOption
        );

    });

}


// ==========================================
// CHỌN CÁCH TỔNG HỢP PHÙ HỢP
// ==========================================

function suggestAggregation(
    columnName
) {

    const name =
        columnName.toLowerCase();


    // Doanh thu / doanh số
    if (
        name.includes("sales") ||
        name.includes("revenue") ||
        name.includes("amount") ||
        name.includes("income") ||
        name.includes("profit") ||
        name.includes("doanh_so") ||
        name.includes("doanh số") ||
        name.includes("doanh_thu") ||
        name.includes("doanh thu")
    ) {

        return "sum";

    }


    // Điểm / tuổi / rating
    if (
        name.includes("score") ||
        name.includes("grade") ||
        name.includes("age") ||
        name.includes("rating") ||
        name.includes("diem") ||
        name.includes("điểm") ||
        name.includes("tuoi") ||
        name.includes("tuổi")
    ) {

        return "mean";

    }


    return "mean";
}


// ==========================================
// TẠO GỢI Ý BIỂU ĐỒ
// ==========================================

function createSuggestions() {

    suggestionList.innerHTML =
        "";


    const suggestions = [];


    const numericColumns =
        currentHeaders.filter(
            header =>
                columnInfo[header].type
                    === "numeric" &&
                !columnInfo[header].isId
        );


    const categoryColumns =
        currentHeaders.filter(
            header => {

                const type =
                    columnInfo[header].type;

                return (
                    (
                        type === "category" ||
                        type === "text"
                    ) &&
                    !columnInfo[header].isId
                );

            }
        );


    const dateColumns =
        currentHeaders.filter(
            header =>
                columnInfo[header].type
                    === "date"
        );


    // ==============================
    // Date + Numeric
    // ==============================

    dateColumns.forEach(x => {

        numericColumns.forEach(y => {

            suggestions.push({

                x: x,

                y: y,

                aggregation:
                    suggestAggregation(y),

                chart:
                    "line",

                title:
                    `${y} theo ${x}`

            });

        });

    });


    // ==============================
    // Category + Numeric
    // ==============================

    categoryColumns.forEach(x => {

        numericColumns.forEach(y => {

            const aggregation =
                suggestAggregation(y);


            let prefix =
                "Trung bình";


            if (
                aggregation === "sum"
            ) {

                prefix =
                    "Tổng";

            }


            suggestions.push({

                x: x,

                y: y,

                aggregation:
                    aggregation,

                chart:
                    "bar",

                title:
                    `${prefix} ${y} theo ${x}`

            });

        });

    });


    // ==============================
    // Numeric + Numeric
    // Scatter
    // ==============================

    for (
        let i = 0;
        i < numericColumns.length;
        i++
    ) {

        for (
            let j = i + 1;
            j < numericColumns.length;
            j++
        ) {

            suggestions.push({

                x:
                    numericColumns[i],

                y:
                    numericColumns[j],

                aggregation:
                    "mean",

                chart:
                    "scatter",

                title:
                    `Mối quan hệ ${numericColumns[i]} và ${numericColumns[j]}`

            });

        }

    }


    if (suggestions.length === 0) {

        suggestionStatus.textContent =
            "Chưa tìm thấy cặp cột phù hợp để gợi ý.";

        return;

    }


    suggestionStatus.textContent =
        "Hệ thống đã phân tích dữ liệu. Bạn có thể chọn một gợi ý hoặc tự chọn X/Y.";


    // Chỉ hiện tối đa 6 gợi ý đầu
    suggestions
        .slice(0, 6)
        .forEach(suggestion => {

            const button =
                document.createElement(
                    "button"
                );


            button.className =
                "suggestion-btn";


            button.textContent =
                suggestion.title;


            button.addEventListener(
                "click",
                function () {

                    applySuggestion(
                        suggestion
                    );

                }
            );


            suggestionList.appendChild(
                button
            );

        });


    // Tự dùng gợi ý đầu tiên
    applySuggestion(
        suggestions[0]
    );

}


// ==========================================
// ÁP DỤNG GỢI Ý
// ==========================================

function applySuggestion(
    suggestion
) {

    xColumnSelect.value =
        suggestion.x;

    yColumnSelect.value =
        suggestion.y;

    aggregationSelect.value =
        suggestion.aggregation;

    chartTypeSelect.value =
        suggestion.chart;


    aggregationSelect.disabled = chartTypeSelect.value === "scatter";
    drawChart();

}


// ==========================================
// NÚT VẼ BIỂU ĐỒ
// ==========================================

drawChartBtn.addEventListener(
    "click",
    drawChart
);


// ==========================================
// VẼ BIỂU ĐỒ
// ==========================================

function drawChart() {

    const xColumn =
        xColumnSelect.value;

    const yColumn =
        yColumnSelect.value;

    const aggregation =
        aggregationSelect.value;

    const chartType =
        chartTypeSelect.value;


    if (
        xColumn === "" ||
        yColumn === ""
    ) {

        alert(
            "Hãy chọn cả trục X và trục Y."
        );

        return;
    }


    if (
        chartType === "scatter"
    ) {

        drawScatterChart(
            xColumn,
            yColumn
        );

        return;
    }


    drawGroupedChart(
        xColumn,
        yColumn,
        aggregation,
        chartType
    );

}


// ==========================================
// BIỂU ĐỒ THEO NHÓM
// ==========================================

function drawGroupedChart(
    xColumn,
    yColumn,
    aggregation,
    chartType
) {

    if (aggregation !== "count" && columnInfo[yColumn].type !== "numeric") {
        alert("Mean, sum, min và max cần trục Y là cột số. Với cột text, hãy chọn count.");
        return;
    }
    const groups = Object.create(null);


    currentRows.forEach(row => {

        const xValue =
            row[xColumn];

        const yValue =
            row[yColumn];


        if (isMissing(xValue)) {
            return;
        }


        if (!groups[xValue]) {

            groups[xValue] = [];

        }


        if (
            aggregation === "count"
        ) {

            if (!isMissing(yValue)) {

                groups[xValue].push(1);

            }

        } else {

            const number =
                toNumber(yValue);


            if (!isNaN(number)) {

                groups[xValue].push(
                    number
                );

            }

        }

    });


    const labels = [];
    const values = [];


    Object.keys(groups).forEach(
        groupName => {

            const groupValues =
                groups[groupName];


            if (
                groupValues.length === 0
            ) {

                return;

            }


            let result;


            if (
                aggregation === "sum"
            ) {

                result =
                    groupValues.reduce(
                        (a, b) => a + b,
                        0
                    );

            }


            if (
                aggregation === "mean"
            ) {

                result =
                    groupValues.reduce(
                        (a, b) => a + b,
                        0
                    ) /
                    groupValues.length;

            }


            if (
                aggregation === "count"
            ) {

                result =
                    groupValues.length;

            }


            if (
                aggregation === "min"
            ) {

                result =
                    Math.min(
                        ...groupValues
                    );

            }


            if (
                aggregation === "max"
            ) {

                result =
                    Math.max(
                        ...groupValues
                    );

            }


            labels.push(
                groupName
            );

            values.push(
                Number(
                    result.toFixed(2)
                )
            );

        }
    );


    destroyChart();


    const ctx =
        document
            .getElementById(
                "dataChart"
            )
            .getContext("2d");


    if (chartType === "pie" && values.some(value => value < 0)) {
        chartInsight.textContent = "Pie cần giá trị không âm. Hãy chọn bar hoặc line.";
        updateCategoryColors();
        return;
    }
    const colors = ["bar", "pie"].includes(chartType)
        ? labels.map(category => getCategoryColor(xColumn, category))
        : primaryColor.value;
    updateCategoryColors(labels);

    dataChart =
        new Chart(ctx, {

            type:
                chartType,

            data: {

                labels:
                    labels,

                datasets: [{

                    label:
                        `${yColumn} theo ${xColumn}`,

                    data:
                        values,

                    backgroundColor:
                        ["bar", "pie"].includes(chartType)
                            ? colors
                            : primaryColor.value,

                    borderColor:
                        ["bar", "pie"].includes(chartType)
                            ? colors
                            : primaryColor.value,

                    borderWidth: 2,

                    tension: 0.25

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio:
                    false,

                plugins: {

                    legend: {

                        labels: {
                            color:
                                "#e5e7eb"
                        }

                    }

                },

                scales:
                    chartType === "pie"
                        ? {}
                        : {

                            x: {
                                ticks: {
                                    color:
                                        "#cbd5e1"
                                }
                            },

                            y: {
                                beginAtZero:
                                    true,

                                ticks: {
                                    color:
                                        "#cbd5e1"
                                }
                            }

                        }

            }

        });


    const aggregationName = {

        mean:
            "Trung bình",

        sum:
            "Tổng",

        count:
            "Số lượng",

        min:
            "Giá trị nhỏ nhất",

        max:
            "Giá trị lớn nhất"

    };


    chartInsight.textContent =

        `${aggregationName[aggregation]} ${yColumn} theo ${xColumn}.`;

}


// ==========================================
// SCATTER PLOT
// ==========================================

function drawScatterChart(
    xColumn,
    yColumn
) {

    if (
        columnInfo[xColumn].type
            !== "numeric" ||
        columnInfo[yColumn].type
            !== "numeric"
    ) {

        alert(
            "Scatter Plot cần cả X và Y đều là dữ liệu số."
        );

        return;
    }


    updateCategoryColors();
    const points = [];


    currentRows.forEach(row => {

        const x =
            toNumber(
                row[xColumn]
            );

        const y =
            toNumber(
                row[yColumn]
            );


        if (
            !isNaN(x) &&
            !isNaN(y)
        ) {

            points.push({
                x: x,
                y: y
            });

        }

    });


    destroyChart();


    const ctx =
        document
            .getElementById(
                "dataChart"
            )
            .getContext("2d");


    dataChart =
        new Chart(ctx, {

            type:
                "scatter",

            data: {

                datasets: [{

                    label:
                        `${xColumn} vs ${yColumn}`,

                    data:
                        points,

                    backgroundColor:
                        primaryColor.value

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio:
                    false,

                plugins: {

                    legend: {

                        labels: {
                            color:
                                "#e5e7eb"
                        }

                    }

                },

                scales: {

                    x: {

                        title: {
                            display:
                                true,

                            text:
                                xColumn,

                            color:
                                "#e5e7eb"
                        },

                        ticks: {
                            color:
                                "#cbd5e1"
                        }

                    },

                    y: {

                        title: {
                            display:
                                true,

                            text:
                                yColumn,

                            color:
                                "#e5e7eb"
                        },

                        ticks: {
                            color:
                                "#cbd5e1"
                        }

                    }

                }

            }

        });


    chartInsight.textContent =

        `Scatter Plot thể hiện mối quan hệ giữa ${xColumn} và ${yColumn}.`;

}


// ==========================================
// HỦY BIỂU ĐỒ CŨ
// ==========================================

function destroyChart() {

    if (dataChart !== null) {

        dataChart.destroy();

        dataChart = null;

    }

}
