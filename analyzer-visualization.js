// Presentation only. All values are supplied by the existing analyzer pipeline.
const chartAppearance = Object.freeze({
    ink: "#0F172A", axis: "#475569", grid: "#EEF2F6", white: "#FFFFFF",
    palettes: {
        bi: ["#118DFF", "#E66C37", "#12239E", "#1AAB40", "#E044A7", "#744EC2", "#D9B300", "#197278", "#D64550", "#15A9CB", "#6B007B", "#F2C80F"],
        modern: ["#2563EB", "#EA580C", "#059669", "#9333EA", "#DB2777", "#0891B2", "#CA8A04", "#DC2626"],
        cool: ["#0284C7", "#4338CA", "#0D9488", "#7C3AED", "#0369A1", "#64748B"],
        warm: ["#EA580C", "#BE123C", "#CA8A04", "#9D174D", "#B45309", "#DC2626"],
        pastel: ["#93C5FD", "#FDBA74", "#C4B5FD", "#6EE7B7", "#F9A8D4", "#67E8F9"]
    }
});
const chartKinds = {
    bar: ["▥", "Cột", "So sánh giá trị giữa các nhóm."],
    horizontalBar: ["☰", "Thanh ngang", "Dễ đọc khi tên nhóm dài."],
    line: ["╱", "Đường", "Theo dõi xu hướng theo thời gian hoặc thứ tự có sẵn."],
    area: ["◩", "Miền", "Cùng giá trị với biểu đồ đường, thêm vùng màu phía dưới."],
    pie: ["◕", "Tròn", "So sánh phần trong tổng; cần giá trị không âm."],
    doughnut: ["◎", "Vòng", "Cùng giá trị với biểu đồ tròn, có khoảng trống ở giữa."],
    scatter: ["⠿", "Phân tán", "Chọn hai cột số để xem mối quan hệ, không tổng hợp."],
    treemap: ["▦", "Cây", "Diện tích ô thể hiện giá trị của nhóm; cần giá trị không âm."],
    radar: ["◇", "Radar", "So sánh 3–12 nhóm trên cùng thang giá trị, không chuẩn hóa."],
    polarArea: ["◉", "Vùng cực", "So sánh giá trị không âm bằng diện tích các vùng."]
};
const calculationLabels = { mean: "Trung bình", sum: "Tổng", count: "Số lượng", min: "Nhỏ nhất", max: "Lớn nhất" };
const formatChartValue = value => new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 20 }).format(value);
const compactChartValue = value => new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 }).format(value);
const clipChartLabel = value => String(value).length > 24 ? `${String(value).slice(0, 23)}…` : String(value);
function chartAlpha(hex, alpha) {
    return `${hex}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`;
}
function categoryChart(type) { return ["bar", "horizontalBar", "pie", "doughnut", "treemap", "polarArea"].includes(type); }

function syncChartControls() {
    const type = chartTypeSelect.value;
    const scatter = type === "scatter";
    document.querySelector('label[for="xColumnSelect"]').textContent = scatter || ["line", "area"].includes(type) ? "Trục X" : type === "bar" ? "Trục X / Nhóm" : "Nhóm";
    document.querySelector('label[for="yColumnSelect"]').textContent = scatter ? "Trục Y" : "Giá trị";
    aggregationSelect.closest(".control-group").hidden = scatter || type === "radar";
    aggregationSelect.disabled = scatter;
    document.getElementById("paletteSelect").closest(".control-group").hidden = !categoryChart(type);
    primaryColor.closest(".control-group").hidden = categoryChart(type);
    document.getElementById("chartTypeHelp").textContent = chartKinds[type][2] + (type === "radar" ? ` Đang dùng phép tính ${calculationLabels[aggregationSelect.value].toLowerCase()} đã chọn.` : "");
    for (const select of [xColumnSelect, yColumnSelect]) {
        for (const option of select.options) {
            option.disabled = scatter && Boolean(option.value) && columnInfo[option.value]?.type !== "numeric";
            if (option.value && columnInfo[option.value]) {
                const typeLabels = { numeric: "Số", date: "Ngày tháng", category: "Nhóm", text: "Văn bản" };
                const text = `${option.value} (${typeLabels[columnInfo[option.value].type]})`;
                if (option.textContent !== text) option.textContent = text;
            }
        }
    }
    document.querySelectorAll("[data-chart-kind]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.chartKind === type)));
}

function setChartHeading(title, subtitle) {
    document.getElementById("chartTitle").textContent = title;
    document.getElementById("chartSubtitle").textContent = subtitle;
    document.getElementById("dataChart").setAttribute("aria-label", `${title}. ${subtitle}`);
}

function clearChartPresentation() {
    document.getElementById("chartLegend").replaceChildren();
    document.getElementById("chartTooltip").hidden = true;
    document.getElementById("chartNotice").textContent = "";
    document.getElementById("chartDataTable").replaceChildren();
}

function renderChartDataPage(page = 0) {
    if (!dataChart) return;
    const container = document.getElementById("chartDataTable");
    container.replaceChildren();
    const dataset = dataChart.data.datasets[0];
    const scatter = chartTypeSelect.value === "scatter";
    const table = document.createElement("table");
    const header = table.createTHead().insertRow();
    [scatter ? xColumnSelect.value : "Nhóm", yColumnSelect.value].forEach(text => {
        const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = text; header.append(cell);
    });
    const body = table.createTBody();
    dataset.data.slice(page * 50, (page + 1) * 50).forEach((value, offset) => {
        const row = body.insertRow();
        row.insertCell().textContent = scatter ? formatChartValue(value.x) : dataChart.data.labels[page * 50 + offset];
        row.insertCell().textContent = formatChartValue(scatter ? value.y : value);
    });
    container.append(table);
    if (dataset.data.length > 50) {
        const navigation = document.createElement("div"); navigation.className = "chart-pagination";
        [["Trước", page - 1, page === 0], ["Sau", page + 1, (page + 1) * 50 >= dataset.data.length]].forEach(([text, next, disabled]) => {
            const button = document.createElement("button"); button.type = "button"; button.textContent = text; button.disabled = disabled;
            button.addEventListener("click", () => renderChartDataPage(next)); navigation.append(button);
        });
        container.append(navigation);
    }
}

function makeCategoryLegend(labels, colors) {
    const legend = document.getElementById("chartLegend");
    if (labels.length > 100) {
        document.getElementById("chartNotice").textContent = "Nhiều nhóm: di chuột vào biểu đồ để xem tên và giá trị. Thanh ngang hoặc biểu đồ cây sẽ dễ đọc hơn.";
        return;
    }
    labels.forEach((label, index) => {
        const item = document.createElement("span");
        const swatch = document.createElement("i");
        swatch.style.backgroundColor = colors[index];
        swatch.setAttribute("aria-hidden", "true");
        item.append(swatch, document.createTextNode(label));
        legend.append(item);
    });
}

function chartOptions(type, xColumn, yColumn, aggregation, datasets) {
    const radial = ["pie", "doughnut", "polarArea", "radar"].includes(type);
    const horizontal = type === "horizontalBar";
    const scatter = type === "scatter";
    const axis = (title, numeric, dimension) => ({
        border: { display: false }, grid: { color: chartAppearance.grid, drawTicks: false },
        title: { display: true, text: title, color: chartAppearance.axis, font: { size: 12, weight: "600" } },
        ticks: { color: chartAppearance.axis, padding: 8, maxRotation: 35, autoSkip: true, autoSkipPadding: 12,
            maxTicksLimit: numeric ? undefined : context => Math.max(2, Math.floor(context.chart[dimension === "x" ? "width" : "height"] / (dimension === "x" ? 90 : 28))),
            callback: numeric ? compactChartValue : function(value) { return clipChartLabel(this.getLabelForValue(value)); } }
    });
    const options = {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: datasets[0].data.length > 150 || matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 400 },
        layout: { padding: 8 }, indexAxis: horizontal ? "y" : "x",
        plugins: {
            legend: { display: datasets.length > 1, position: "bottom", labels: { color: chartAppearance.axis, usePointStyle: true, padding: 18 } },
            tooltip: {
                backgroundColor: chartAppearance.ink, titleColor: chartAppearance.white, bodyColor: chartAppearance.white,
                padding: 12, cornerRadius: 8, boxPadding: 5,
                callbacks: {
                    title: items => scatter ? `${xColumn} / ${yColumn}` : items[0]?.label || "",
                    label: context => scatter
                        ? `${xColumn}: ${formatChartValue(context.raw.x)} · ${yColumn}: ${formatChartValue(context.raw.y)}`
                        : `${calculationLabels[aggregation]} ${yColumn}: ${formatChartValue(context.raw)}`
                }
            }
        },
        scales: radial ? (type === "radar" || type === "polarArea" ? {
            r: { grid: { color: chartAppearance.grid }, angleLines: { color: chartAppearance.grid },
                ticks: { color: chartAppearance.axis, backdropColor: "transparent" },
                pointLabels: { color: chartAppearance.axis, callback: clipChartLabel } }
        } : {}) : {
            x: axis(horizontal ? yColumn : xColumn, horizontal || scatter, "x"),
            y: { ...axis(horizontal ? xColumn : yColumn, !horizontal, "y"), ...(!horizontal && !scatter ? { beginAtZero: true } : {}) }
        }
    };
    if (type === "doughnut") options.cutout = "65%";
    return options;
}

function renderGroupedVisualization(ctx, labels, values, xColumn, yColumn, aggregation, type) {
    clearChartPresentation();
    setChartHeading(`${yColumn} theo ${xColumn}`, `${calculationLabels[aggregation]} · Biểu đồ ${chartKinds[type][1].toLowerCase()}`);
    if (!values.length) { chartInsight.textContent = "Không có giá trị phù hợp để vẽ biểu đồ."; updateCategoryColors(); return; }
    if (["pie", "doughnut", "treemap", "polarArea"].includes(type) && (values.some(value => value < 0) || !values.some(value => value > 0))) {
        chartInsight.textContent = "Biểu đồ này cần giá trị không âm và ít nhất một giá trị dương. Hãy chọn cột, thanh ngang hoặc đường.";
        updateCategoryColors(); return;
    }
    if (type === "radar" && (labels.length < 3 || labels.length > 12)) {
        chartInsight.textContent = "Biểu đồ radar phù hợp với 3–12 nhóm. Hãy chọn cột hoặc thanh ngang cho dữ liệu này.";
        updateCategoryColors(); return;
    }
    const colors = categoryChart(type) ? labels.map(category => getCategoryColor(xColumn, category)) : primaryColor.value;
    const datasets = [{ label: `${yColumn} theo ${xColumn}`, data: values,
        backgroundColor: type === "area" || type === "radar" ? chartAlpha(primaryColor.value, 0.2) : colors,
        borderColor: ["pie", "doughnut", "polarArea"].includes(type) ? chartAppearance.white : colors,
        borderWidth: ["line", "area", "radar"].includes(type) ? 2.5 : 1,
        borderRadius: ["bar", "horizontalBar"].includes(type) ? 5 : 0,
        fill: type === "area" || type === "radar", tension: 0.25,
        cubicInterpolationMode: ["line", "area"].includes(type) ? "monotone" : undefined,
        pointRadius: labels.length > 60 ? 0 : 3, pointHoverRadius: 5, pointHitRadius: 8,
        hoverBorderWidth: 2, hoverBorderColor: chartAppearance.ink, maxBarThickness: 56 }];
    dataChart = type === "treemap" ? createAnalyzerTreemap(ctx, labels, values, colors, yColumn, aggregation)
        : new Chart(ctx, { type: type === "area" ? "line" : type === "horizontalBar" ? "bar" : type,
            data: { labels, datasets }, options: chartOptions(type, xColumn, yColumn, aggregation, datasets) });
    updateCategoryColors(labels);
    if (["pie", "doughnut", "polarArea"].includes(type)) makeCategoryLegend(labels, colors);
    if (["pie", "doughnut", "polarArea"].includes(type) && labels.length > 12) document.getElementById("chartNotice").textContent = "Nhiều nhóm: biểu đồ thanh ngang hoặc cây sẽ dễ so sánh hơn. Không có nhóm nào bị gộp hoặc bỏ.";
    chartInsight.textContent = `${calculationLabels[aggregation]} ${yColumn} theo ${xColumn}.`;
    if (document.getElementById("chartDataDetails").open) renderChartDataPage();
}

// Binary spatial partition, using already aggregated values as area weights.
// Only rectangle geometry is scaled; labels and numeric payload are unchanged.
function createAnalyzerTreemap(ctx, labels, values, colors, yColumn, aggregation) {
    const canvas = ctx.canvas;
    const tooltip = document.getElementById("chartTooltip");
    const data = { labels, datasets: [{ data: values, backgroundColor: colors }] };
    let tiles = [];
    const render = () => {
        const rect = canvas.parentElement.getBoundingClientRect();
        const width = Math.max(1, rect.width), height = Math.max(1, rect.height), ratio = devicePixelRatio || 1;
        canvas.style.width = "100%"; canvas.style.height = "100%";
        canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);
        tiles = [];
        const maximum = values.reduce((maximum, value) => Math.max(maximum, value), 0);
        const items = values.map((value, index) => ({ index, weight: value / maximum })).filter(item => item.weight > 0);
        const prefix = [0]; items.forEach(item => prefix.push(prefix[prefix.length - 1] + item.weight));
        const partition = (start, end, x, y, w, h) => {
            if (end - start === 1) { tiles.push({ index: items[start].index, x, y, w, h }); return; }
            const total = prefix[end] - prefix[start], target = prefix[start] + total / 2;
            let lo = start + 1, hi = end - 1;
            while (lo < hi) { const mid = Math.floor((lo + hi) / 2); if (prefix[mid] < target) lo = mid + 1; else hi = mid; }
            const split = lo, fraction = (prefix[split] - prefix[start]) / total;
            if (w >= h) { partition(start, split, x, y, w * fraction, h); partition(split, end, x + w * fraction, y, w * (1 - fraction), h); }
            else { partition(start, split, x, y, w, h * fraction); partition(split, end, x, y + h * fraction, w, h * (1 - fraction)); }
        };
        if (items.length) partition(0, items.length, 0, 0, width, height);
        tiles.forEach(tile => {
            const { index, x, y, w, h } = tile;
            const color = data.datasets[0].backgroundColor[index];
            ctx.fillStyle = color;
            ctx.fillRect(x + 1, y + 1, Math.max(0, w - 2), Math.max(0, h - 2));
            const rgb = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16) / 255)
                .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
            ctx.fillStyle = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722 > 0.179 ? "#0F172A" : "#FFFFFF";
            if (w > 55 && h > 30) {
                ctx.save(); ctx.beginPath(); ctx.rect(x + 8, y + 6, w - 16, h - 12); ctx.clip();
                ctx.font = "600 13px system-ui";
                let text = String(labels[index]);
                while (text.length && ctx.measureText(text + "…").width > w - 20) text = text.slice(0, -1);
                ctx.fillText(text === String(labels[index]) ? text : `${text}…`, x + 10, y + 23);
                if (h > 55) { ctx.font = "12px system-ui"; ctx.fillText(formatChartValue(values[index]), x + 10, y + 44); }
                ctx.restore();
            }
        });
        const zeroCount = values.filter(value => value === 0).length;
        document.getElementById("chartNotice").textContent = zeroCount ? `${zeroCount} nhóm có giá trị 0 nên không có diện tích. Xem tên và giá trị trong bảng dữ liệu biểu đồ.` : "";
    };
    const hover = event => {
        const rect = canvas.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
        const tile = tiles.find(item => x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h);
        tooltip.hidden = !tile;
        if (tile) {
            tooltip.textContent = `${labels[tile.index]} · ${calculationLabels[aggregation]} ${yColumn}: ${formatChartValue(values[tile.index])}`;
            tooltip.style.left = `${Math.max(0, Math.min(x + 12, rect.width - tooltip.offsetWidth))}px`;
            tooltip.style.top = `${Math.max(0, Math.min(y + 12, rect.height - tooltip.offsetHeight))}px`;
        }
    };
    const leave = () => { tooltip.hidden = true; };
    canvas.addEventListener("pointermove", hover); canvas.addEventListener("pointerleave", leave);
    const observer = new ResizeObserver(render); observer.observe(canvas.parentElement); render();
    return { data, update: render, destroy() {
        observer.disconnect(); canvas.removeEventListener("pointermove", hover); canvas.removeEventListener("pointerleave", leave);
        leave(); ctx.clearRect(0, 0, canvas.width, canvas.height); canvas.style.removeProperty("width"); canvas.style.removeProperty("height");
    } };
}

document.addEventListener("DOMContentLoaded", () => {
    // Upload keeps its existing flow; translate newly inserted options in the UI.
    new MutationObserver(syncChartControls).observe(xColumnSelect, { childList: true });
    document.getElementById("chartDataDetails").addEventListener("toggle", event => {
        if (event.target.open) renderChartDataPage();
    });
    const picker = document.getElementById("chartTypePicker");
    Object.entries(chartKinds).forEach(([type, [icon, name, help]]) => {
        const button = document.createElement("button"); button.type = "button"; button.dataset.chartKind = type;
        const symbol = document.createElement("span"); symbol.textContent = icon; symbol.setAttribute("aria-hidden", "true");
        button.append(symbol, document.createTextNode(name)); button.title = help; button.setAttribute("aria-label", `Biểu đồ ${name.toLowerCase()}`);
        button.addEventListener("click", () => { chartTypeSelect.value = type; chartTypeSelect.dispatchEvent(new Event("change")); });
        picker.append(button);
    });
    document.getElementById("paletteSelect").addEventListener("change", () => {
        autoCategoryColorMap.clear(); if (dataChart) drawChart();
    });
    syncChartControls();
});
