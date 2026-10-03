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
        text === "n/a"
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
        const numeric = observed.length > 0 && observed.every(value => Number.isFinite(toNumber(value)));
        let replacement = "Unknown";
        if (numeric) {
            const sorted = observed.map(toNumber).sort((a, b) => a - b);
            const middle = Math.floor(sorted.length / 2);
            replacement = sorted.length % 2 ? sorted[middle] : sorted[middle - 1] / 2 + sorted[middle] / 2;
        } else {
            const frequencies = new Map();
            observed.forEach(value => frequencies.set(value, (frequencies.get(value) || 0) + 1));
            let best = 0;
            frequencies.forEach((count, value) => {
                if (count > best) { best = count; replacement = value; }
            });
        }
        rows.forEach(row => {
            if (isMissing(row[i])) { row[i] = replacement; report.missing++; }
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
    return { headers: keptHeaders, rows: rows.map(values => Object.fromEntries(keptHeaders.map((header, i) => [header, values[i]]))), report };
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
            uploadedName = file.name.replace(/\.csv$/i, "");
            destroyChart();
            categoryColorMap.clear();
            document.getElementById("categoryColorPanel").hidden = true;
            chartInsight.textContent = "Chưa có biểu đồ.";
            columnInfo = Object.create(null);
            updateOverview();
            showTable();
            analyzeColumns();
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
        input.value = categoryColorMap.get(key) || primaryColor.value;
        input.setAttribute("aria-label", `Màu cho ${category}`);
        input.addEventListener("input", () => {
            categoryColorMap.set(key, input.value);
            if (dataChart) {
                dataChart.data.datasets[0].backgroundColor = dataChart.data.labels.map(value => categoryColorMap.get(JSON.stringify([xColumnSelect.value, value])) || primaryColor.value);
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


        // ===========================
        // Numeric
        // ===========================

        const numericCount =
            values.filter(
                value =>
                    !isNaN(
                        toNumber(value)
                    )
            ).length;


        const numericRatio =
            values.length === 0
                ? 0
                : numericCount /
                  values.length;


        // ===========================
        // Date
        // ===========================

        let dateCount = 0;


        values.forEach(value => {

            const text =
                String(value);


            // Chỉ kiểm tra ngày nếu
            // có ký tự ngày tháng
            if (
                /[-/]/.test(text) &&
                !isNaN(
                    Date.parse(text)
                )
            ) {

                dateCount++;

            }

        });


        const dateRatio =
            values.length === 0
                ? 0
                : dateCount /
                  values.length;


        // ===========================
        // Xác định loại
        // ===========================

        let type =
            "text";


        if (numericRatio === 1) {

            type =
                "numeric";

        } else if (dateRatio >= 0.8) {

            type =
                "date";

        } else if (
            uniqueValues.size <= 20 ||
            uniqueValues.size /
                Math.max(values.length, 1)
                <= 0.5
        ) {

            type =
                "category";

        }


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
    const colors = labels.map(category => categoryColorMap.get(JSON.stringify([xColumn, category])) || primaryColor.value);
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
                        primaryColor.value,

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
