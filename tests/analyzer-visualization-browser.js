// Real browser QA. Serve /baseline/ from git HEAD and local cached Chart.js/PapaParse.
(async () => {
    const report = document.getElementById("report"), checks = [], errors = [];
    const assert = (condition, message) => { if (!condition) throw new Error(message); checks.push(message); };
    const equal = (a, b, message) => assert(JSON.stringify(a) === JSON.stringify(b), message);
    const wait = () => new Promise(resolve => setTimeout(resolve, 80));
    const width = Number(new URL(location.href).searchParams.get("width"));
    let win, doc;
    const open = async baseline => {
        const frame = document.createElement("iframe"); frame.style.cssText = `width:${width}px;height:1100px;border:0;display:block`;
        document.body.append(frame);
        await new Promise(resolve => { frame.onload = resolve; frame.src = baseline ? "/baseline/data-analyzer.html" : "/data-analyzer.html"; });
        win = frame.contentWindow; doc = win.document;
        win.alert = message => { win.__lastAlert = message; };
        win.addEventListener("error", event => errors.push(event.message));
        win.addEventListener("unhandledrejection", event => errors.push(String(event.reason)));
        win.__eval = code => win.eval(code);
        return frame;
    };
    const upload = async text => {
        const transfer = new win.DataTransfer();
        transfer.items.add(new win.File([text], "visual-fixture.csv", { type: "text/csv" }));
        doc.getElementById("csvFile").files = transfer.files;
        doc.getElementById("csvFile").dispatchEvent(new win.Event("change"));
        for (let i = 0; i < 100 && !doc.getElementById("cleaningStatus").textContent.startsWith("Đã làm sạch"); i++) {
            // A server round trip lets FileReader finish even under virtual time.
            await fetch("/__qa_tick__", { cache: "no-store" }); await wait();
        }
        assert(doc.getElementById("cleaningStatus").textContent.startsWith("Đã làm sạch"), `CSV upload succeeds (${doc.getElementById("cleaningStatus").textContent})`);
    };
    const draw = (type, aggregation = "sum", x = "group", y = "value") => {
        doc.getElementById("chartTypeSelect").value = type;
        doc.getElementById("aggregationSelect").value = aggregation;
        doc.getElementById("xColumnSelect").value = x;
        doc.getElementById("yColumnSelect").value = y;
        if (win.syncChartControls) win.syncChartControls();
        win.drawChart();
        const data = win.__eval("dataChart && dataChart.data");
        if (data) {
            const chart = win.__eval("dataChart");
            if (chart.options) { chart.stop(); chart.options.animation = false; chart.update("none"); }
        }
        return data && { labels: data.labels || [], values: data.datasets[0].data };
    };
    const download = async () => {
        let blob;
        const create = win.URL.createObjectURL, click = win.HTMLAnchorElement.prototype.click;
        win.URL.createObjectURL = value => { blob = value; return "blob:test-download"; };
        win.HTMLAnchorElement.prototype.click = function() { win.__downloadName = this.download; };
        doc.getElementById("downloadCleanCsvBtn").click();
        win.URL.createObjectURL = create; win.HTMLAnchorElement.prototype.click = click;
        return { text: await blob.text(), name: win.__downloadName };
    };
    const snapshot = () => win.__eval("JSON.stringify({currentHeaders,currentRows,cleaningReport,rawColumnProfile,columnInfo,profile:[...cleanedColumnProfile]})");
    const noOverflow = () => assert(doc.documentElement.scrollWidth <= width + 1, `No page overflow at ${width}`);
    try {
        const fixture = "Group,Value,Other,Join Date,Empty\nA,10,1,2024-01-08,\nB,20,2,2022-03-03,\nC,30,3,2024-05-05,\nA,1.337,4,2024-01-08,\nB,,5,2022-03-03,\nA,10,1,2024-01-08,\n,,,,\n";
        const baseline = await open(true); await upload(fixture);
        const reference = {}, beforeSnapshot = snapshot(), beforeDownload = await download();
        const profileHtml = doc.getElementById("profileTable").textContent;
        const suggestions = doc.getElementById("suggestionList").textContent;
        for (const type of ["bar", "line", "pie"]) for (const aggregation of ["mean", "sum", "count", "min", "max"]) reference[`${type}/${aggregation}`] = draw(type, aggregation);
        reference.scatter = draw("scatter", "mean", "other", "value");
        baseline.style.display = "none";
        await open(false); await upload(fixture);
        assert(doc.querySelector('#yColumnSelect option[value="value"]').textContent === "value (Số)", "Numeric option label in Vietnamese");
        assert(doc.querySelector('#xColumnSelect option[value="join_date"]').textContent === "join_date (Ngày tháng)", "Date option label in Vietnamese");
        equal(snapshot(), beforeSnapshot, "Cleaning, column types and all Data Profile values identical to HEAD");
        equal(doc.getElementById("profileTable").textContent, profileHtml, "Data Profile table unchanged");
        equal(doc.getElementById("suggestionList").textContent, suggestions, "Auto EDA suggestions unchanged");
        equal(await download(), beforeDownload, "Downloaded CSV contents, encoding and filename identical to HEAD");
        for (const type of ["bar", "line", "pie"]) for (const aggregation of ["mean", "sum", "count", "min", "max"]) {
            equal(draw(type, aggregation), reference[`${type}/${aggregation}`], `${type}/${aggregation} exactly matches HEAD`);
            assert(win.__eval("dataChart.options.plugins.legend.display") === false, `${type} single dataset legend hidden`);
        }
        equal(draw("scatter", "mean", "other", "value"), reference.scatter, "Scatter X/Y values identical to HEAD");
        assert(doc.getElementById("aggregationSelect").closest(".control-group").hidden, "Scatter hides calculation field");
        assert(doc.getElementById("paletteSelect").closest(".control-group").hidden, "Scatter hides category palette field");
        assert(doc.querySelector('#xColumnSelect option[value="group"]').disabled, "Scatter field selector disables text columns");
        equal(win.chartOptions("line", "x", "y", "sum", [{data:[]},{data:[]}]).plugins.legend.display, true, "Actual multiple datasets retain series legend");
        for (const aggregation of ["mean", "sum", "count", "min", "max"]) {
            equal(draw("area", aggregation), reference[`line/${aggregation}`], `Area vs Line: ${aggregation}, difference 0`);
            equal(draw("horizontalBar", aggregation), reference[`bar/${aggregation}`], `Horizontal Bar vs Bar: ${aggregation}, difference 0`);
            equal(draw("doughnut", aggregation), reference[`pie/${aggregation}`], `Doughnut vs Pie: ${aggregation}, difference 0`);
            equal(draw("treemap", aggregation), reference[`bar/${aggregation}`], `Treemap vs Bar: ${aggregation}, difference 0`);
            equal(draw("radar", aggregation), reference[`bar/${aggregation}`], `Radar values unchanged: ${aggregation}`);
            assert(doc.getElementById("aggregationSelect").closest(".control-group").hidden && !doc.getElementById("aggregationSelect").disabled, "Radar displays group/value and preserves selected calculation");
            equal(draw("polarArea", aggregation), reference[`bar/${aggregation}`], `Polar Area values unchanged: ${aggregation}`);
        }
        assert(doc.getElementById("chartTypePicker").children.length === 10, "Ten Vietnamese chart buttons");
        doc.querySelector('[data-chart-kind="treemap"]').click();
        assert(doc.querySelector('[data-chart-kind="treemap"]').getAttribute("aria-pressed") === "true", "Chart button selected state");
        assert(doc.querySelector('label[for="xColumnSelect"]').textContent === "Nhóm", "Treemap group label in Vietnamese");
        assert(!doc.getElementById("aggregationSelect").closest(".control-group").hidden, "Grouped chart retains selected calculation");
        assert(doc.getElementById("primaryColor").closest(".control-group").hidden, "Category chart hides unused series color field");
        equal(doc.getElementById("chartTitle").textContent, "value theo group", "Plain text heading outside canvas");
        const canvas = doc.getElementById("dataChart"), rect = canvas.getBoundingClientRect();
        canvas.dispatchEvent(new win.PointerEvent("pointermove", { clientX: rect.left + 10, clientY: rect.top + 10 }));
        assert(!doc.getElementById("chartTooltip").hidden && doc.getElementById("chartTooltip").textContent.includes("A"), "Treemap tooltip shows original category and value");
        draw("pie");
        assert(doc.getElementById("chartLegend").children.length === 3, "One category legend for pie");
        const input = doc.querySelector('#categoryColors input'); input.value = "#abcdef"; input.dispatchEvent(new win.Event("input"));
        equal(win.__eval("dataChart.data.datasets[0].backgroundColor[0]"), "#abcdef", "Category color customization preserved");
        equal(doc.querySelector('#chartLegend i').style.backgroundColor, "rgb(171, 205, 239)", "Category legend color updated consistently");
        doc.getElementById("paletteSelect").value = "warm"; doc.getElementById("paletteSelect").dispatchEvent(new win.Event("change"));
        equal(win.__eval("dataChart.data.datasets[0].backgroundColor[0]"), "#abcdef", "Palette change preserves explicit category override");
        doc.getElementById("primaryColor").value = "#197278";
        draw("line");
        equal(win.__eval("dataChart.data.datasets[0].borderColor"), "#197278", "Primary series color customization preserved");
        doc.getElementById("primaryColor").value = "#118dff";
        draw("bar", "mean", "join_date", "value");
        equal(doc.getElementById("chartLegend").children.length, 0, "Date axis has no duplicate legend");
        noOverflow();
        equal(snapshot(), beforeSnapshot, "All chart rendering and color changes leave source/profile data unchanged");
        for (const count of [1, 5, 20, 200, 1000]) {
            const text = "Group,Value,Other,Join Date\n" + Array.from({length:count}, (_, i) => `Tên nhóm rất dài để kiểm tra nhãn ${i},${i+1},${i+2},2024-01-${String(i%28+1).padStart(2,"0")}`).join("\n");
            await upload(text);
            for (const type of ["bar", "horizontalBar", "line", "area", "pie", "doughnut", "scatter", "treemap", "polarArea"]) {
                const data = draw(type, "sum", type === "scatter" ? "other" : "group");
                assert(data.values.length === count, `${type} preserves ${count} long-label categories/points`);
                noOverflow();
                assert(doc.querySelectorAll('#categoryColors input').length <= 24, "Color controls bounded to 24 per page");
                assert(doc.getElementById("chartLegend").children.length <= 100, "Legend bounded to 100 items");
            }
            if (count === 5) assert(draw("radar").values.length === 5, "Radar renders appropriate group count");
            else if (count === 1 || count === 20) { draw("radar"); assert(win.__eval("dataChart") === null, "Radar reports unsupported group count without changing data"); }
        }
        await upload("Group,Value,Other\nA,10,1\nB,20,2\nC,30,3");
        equal(draw("treemap").values, [10,20,30], "Treemap receives exact 10/20/30 fixture");
        const frame = win.frameElement;
        for (const resizedWidth of [320, 1440, width]) {
            frame.style.width = `${resizedWidth}px`; await fetch("/__qa_tick__", {cache:"no-store"}); await wait();
            for (let tick = 0; tick < 5; tick++) await fetch("/__qa_tick__", {cache:"no-store"});
            assert(doc.documentElement.scrollWidth <= resizedWidth + 1, `Live treemap resize has no overflow at ${resizedWidth}`);
            assert(Math.abs(doc.getElementById("dataChart").getBoundingClientRect().width - doc.querySelector(".chart-box").clientWidth) < 2, "Treemap canvas follows resized container");
        }
        doc.getElementById("chartDataDetails").open = true; await wait();
        assert(doc.querySelectorAll('#chartDataTable tbody tr').length === 3, "Accessible data table includes every fixture category");
        await upload("Group,Value,Other\nA,0,1\nB,20,2\nC,30,3"); draw("treemap"); await wait();
        assert(doc.getElementById("chartNotice").textContent.includes("giá trị 0"), "Zero-area categories explained");
        assert(doc.querySelector('#chartDataTable tbody').textContent.includes("A0"), "Zero category retained in data table");
        await upload("Group,Value,Other\nA,-10,1\nB,20,2\nC,30,3");
        for (const type of ["pie", "doughnut", "treemap", "polarArea"]) { draw(type); assert(win.__eval("dataChart") === null, `${type} rejects negative areas without silently dropping values`); }
        await upload(fixture); draw("area", "mean", "join_date", "value");
        assert(win.__eval("dataChart.data.datasets[0].fill") === true, "Area fill enabled");
        const chart = win.__eval("dataChart");
        chart.setActiveElements([{datasetIndex:0,index:0}]);
        chart.tooltip.setActiveElements([{datasetIndex:0,index:0}], {x:80,y:80}); chart.update("none");
        assert(chart.tooltip.title[0] === "2024-01-08", "Chart.js tooltip preserves full date");
        assert(chart.tooltip.body[0].lines[0].includes("Trung bình"), "Tooltip names selected calculation");
        noOverflow(); equal(errors, [], "No runtime errors");
        const visual = new URL(location.href).searchParams.get("visual");
        if (visual === "treemap" || visual === "bar" || visual === "doughnut") {
            doc.getElementById("paletteSelect").value = "bi";
            await upload("Group,Value,Other\n" + Array.from({length:20}, (_, i) => `Nhóm ${i+1},${(i+1)*10},${i+2}`).join("\n"));
            draw(visual);
        }
        doc.documentElement.style.scrollBehavior = "auto";
        const target = new URL(location.href).searchParams.get("focus") === "controls" ? doc.querySelector(".chart-selector") : doc.querySelector(".analyzer-chart-card");
        win.scrollTo({top: target.getBoundingClientRect().top + win.scrollY - 160, behavior:"instant"});
        await wait();
        report.textContent = JSON.stringify({ok:true,width,checks:checks.length});
    } catch (error) { report.textContent = JSON.stringify({ok:false,width,error:error.message,checks,errors}); }
})();
