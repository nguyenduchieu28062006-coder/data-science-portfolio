(async () => {
    const B = CustomerReturnBatch, P = CustomerReturnBatchPage, model = CustomerReturnPage.getModel(), fixture = window.__batchFixture;
    const checks = [], $ = id => document.getElementById(id);
    const assert = (ok, name) => { if (!ok) throw Error(name); checks.push(name); };
    const near = (a, b, tolerance = 1e-12) => Math.abs(a - b) <= tolerance;
    const wait = async test => { for (let i = 0; i < 1000; i++) { if (test()) return; await new Promise(r => setTimeout(r, 10)); } throw Error('Batch UI timed out: ' + $('customerBatchStatus').textContent + ' / ' + $('customerBatchError').textContent); };
    const input = (id, value) => { $(id).value = value; $(id).dispatchEvent(new Event('input', { bubbles: true })); };
    const fails = async (fn, text) => { let error; try { await fn(); } catch (e) { error = e; } assert(error && (!text || error.message.includes(text)), 'expected validation: ' + text); };
    await CustomerReturnPage.ready;
    assert(!$('customerSinglePanel').hidden && $('customerBatchPanel').hidden, 'single mode remains default');
    const high = model.samples.find(s => s.band === 'high').input;
    for (const country of ['Vietnam', 'Viet Nam', 'Việt Nam', 'VN']) {
        const p = CustomerReturnModel.predict(model, { ...high, country });
        assert(Number.isFinite(p.probability) && p.probability >= 0 && p.probability <= 1, 'Vietnam safe ' + country);
        assert(p.probability === CustomerReturnModel.predict(model, { ...high, country: '__UNKNOWN__' }).probability, 'Vietnam all-zero parity ' + country);
    }
    assert([...$('customer-country').options].some(o => o.value === 'Vietnam' && o.textContent === 'Việt Nam'), 'visible Vietnam option');
    document.querySelector('[data-customer-sample="high"]').click(); $('customer-country').value = 'Vietnam'; $('customerForm').requestSubmit();
    assert(CustomerReturnPage.getResult() && !$('customerDomainWarning').hidden, 'Vietnam single form predicts with disclosure');
    $('customerBatchTab').focus(); $('customerBatchTab').dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    assert($('customerSinglePanel').hidden && !$('customerBatchPanel').hidden && $('customerBatchTab').getAttribute('aria-selected') === 'true', 'keyboard mode switch');
    assert($('customerBatchDashboard').hidden && $('customerBatchForm').hidden, 'batch empty state');

    const quote = await B.parseCSV('\uFEFF a ; b ; c \r\n"x;y";"a""b";"multi\nline"\r\n\r\n');
    assert(quote.delimiter === ';' && quote.headers[0] === 'a' && quote.rows[0][0] === 'x;y' && quote.rows[0][1] === 'a"b' && quote.rows[0][2] === 'multi\nline' && quote.blankRows === 1, 'BOM, headers, quoted separators/newlines and blank rows');
    await fails(() => B.parseCSV('a,b\n"unclosed,b'), 'ngoặc kép');
    await fails(() => B.parseCSV('a,a\n1,2'), 'trùng');
    await fails(() => B.parseCSV('a,b\n'), 'dòng dữ liệu');
    await fails(() => B.parseCSV('a,b\n' + 'x'.repeat(B.LIMITS.cell + 1) + ',2'), '10.000');
    assert(B.parseNumber('1,234.56') === 1234.56 && B.parseNumber('1.234,56', 'comma') === 1234.56 && Number.isNaN(B.parseNumber('12oops')) && Number.isNaN(B.parseNumber('1,23')), 'strict number formats');
    assert(Number.isNaN(B.parseDate('2026-02-30')) && Number.isNaN(B.parseDate('01/02/2026')) && B.parseDate('01/02/2026', 'DMY') === Date.UTC(2026, 1, 1) && B.parseDate('01/02/2026', 'MDY') === Date.UTC(2026, 0, 2), 'valid calendar and explicit ambiguous date format');
    assert(B.parseDate('2026-01-01T07:00:00+07:00') === B.parseDate('2026-01-01T00:00:00Z'), 'timezone normalization');
    const parsed = await B.parseCSV(fixture.csv), mapping = B.detectColumns(parsed.headers);
    assert(mapping.customer === 0 && mapping.order === 1 && mapping.date === 2 && mapping.value === 4 && mapping.product === 6 && mapping.rating === 7, 'auto mapping UCI columns');
    const aliases = B.detectColumns(['ma_khach_hang', 'ma_don_hang', 'ngay_mua', 'so_luong', 'gia', 'quoc_gia', 'san_pham', 'danh_gia', 'nhan_xet']);
    assert(Object.values(aliases).slice(0, 9).every((index, i) => index === i), 'Vietnamese aliases');
    assert(B.detectColumns(['customer_id', 'buyer_id']).customer === -1, 'ambiguous auto mapping requires selection');
    await fails(() => B.prepareTransactions(parsed, { ...mapping, customer: -1 }), 'mã khách');
    await fails(() => B.prepareTransactions(parsed, { ...mapping, order: mapping.customer }), 'nhiều trường');
    await fails(() => B.prepareTransactions(parsed, mapping, { currency: 'VND' }), 'tỷ giá');
    const prepared = await B.prepareTransactions(parsed, mapping, { profile: 'uci' });
    const result = await B.analyze(prepared, model, B.parseDate(fixture.snapshot));
    assert(result.audit.ignoredRows === 6 && result.audit.ignored['Dòng trùng chính xác'] === 1 && result.audit.atOrAfterSnapshot === 2, 'dirty/cancel/refund/nonproduct rows and strict snapshot exclusion');
    let maxFeatureError = 0, maxProbabilityError = 0;
    for (const expected of fixture.features) {
        const record = result.records.find(r => r.customer_id === expected.id);
        assert(record?.probability !== null, 'eligible historical customer ' + expected.id);
        for (const key of model.preprocessing.numeric_features) {
            const error = Math.abs(record.features[key] - expected.features[key]); maxFeatureError = Math.max(maxFeatureError, error);
            assert(error < 1e-9, 'Python feature ' + expected.id + '/' + key);
        }
        assert(record.features.country === expected.features.country, 'last historical country');
        maxProbabilityError = Math.max(maxProbabilityError, Math.abs(record.probability - expected.probability));
        assert(near(record.probability, expected.probability), 'Python batch inference ' + expected.id);
        const single = CustomerReturnModel.predict(model, record.features);
        assert(record.probability === single.probability && record.classification === single.predictedClass && record.band === single.band.toUpperCase(), 'single/batch exact probability, class and band');
    }
    assert(result.records.find(r => r.customer_id === 'future-only').probability === null, 'no invented history for future-only customer');
    const missingProduct = await B.analyze(await B.prepareTransactions(parsed, { ...mapping, product: -1 }, { profile: 'uci' }), model, B.parseDate(fixture.snapshot));
    assert(missingProduct.summary.eligible === 0 && missingProduct.summary.insufficient === missingProduct.summary.total, 'missing product never becomes fabricated feature');
    const noRatings = await B.analyze(await B.prepareTransactions(parsed, { ...mapping, rating: -1, feedback: -1 }, { profile: 'uci' }), model, B.parseDate(fixture.snapshot));
    assert(result.records.every((record, i) => record.probability === noRatings.records[i].probability) && noRatings.ratings.count === 0 && noRatings.feedbackCount === 0, 'rating/feedback never influence model');
    const changedMetadata = { ...parsed, rows: parsed.rows.map(row => row.slice()) };
    changedMetadata.rows[changedMetadata.rows.length - 3][mapping.rating] = '1';
    changedMetadata.rows[changedMetadata.rows.length - 3][mapping.feedback] = 'different optional metadata';
    const changedResult = await B.analyze(await B.prepareTransactions(changedMetadata, mapping, { profile: 'uci' }), model, B.parseDate(fixture.snapshot));
    assert(result.records.every((record, i) => record.probability === changedResult.records[i].probability), 'optional metadata cannot change duplicate identity or prediction');
    assert(result.ratings.count > 0 && near(result.ratings.average, result.ratings.counts.reduce((sum, count, i) => sum + count * (i + 1), 0) / result.ratings.count) && result.feedbackCount > 0, 'descriptive ratings and feedback');
    assert(result.summary.returnCount + result.summary.nonReturnCount === result.summary.eligible && near(result.summary.returnRatio + result.summary.nonReturnRatio, 1) && Object.values(result.summary.bands).reduce((a, b) => a + b, 0) === result.summary.eligible, 'classification chart counts and ratios');
    assert(B.actionPlan(result).priority === 'experience', 'low ratings prioritize experience without changing probability');
    assert(B.actionPlan({ ...result, summary: { ...result.summary, returnCount: 2, nonReturnCount: 3, returnRatio: .4 } }).mode === 'retention', 'non-return majority action trigger');
    assert(B.actionPlan({ ...result, summary: { ...result.summary, returnCount: 3, nonReturnCount: 2, returnRatio: .6 } }).mode === 'growth', 'return majority growth trigger');
    assert(B.actionPlan({ ...result, summary: { ...result.summary, returnCount: 50, nonReturnCount: 50, returnRatio: .5 } }).mode === 'balanced', 'balanced wording');

    const exported = await B.parseCSV(B.exportCSV(result));
    assert(exported.rows.length === result.records.length && exported.headers.includes('return_probability') && exported.headers.includes('non_return_probability') && !exported.headers.includes('feedback'), 'safe CSV export schema');
    const formula = exported.rows.find(r => r[0] === "'=1+1");
    assert(formula && Number(formula[1]) >= 0 && Number(formula[1]) <= 1, 'spreadsheet formula injection guarded');
    const vndParsed = await B.parseCSV('customer_id,order_id,order_date,quantity,unit_price,country,product\nV,V1,2026-01-01,2,500000,VN,sku1\nV,V2,2026-09-01,1,1000000,Vietnam,sku2');
    const vnd = await B.analyze(await B.prepareTransactions(vndParsed, B.detectColumns(vndParsed.headers), { currency: 'VND', exchangeRate: 25000 }), model, B.parseDate('2026-10-01'));
    assert(vnd.records[0].features.monetary_90d === 40, 'VND conversion uses user supplied rate');
    const totals = await B.prepareTransactions(vndParsed, B.detectColumns(vndParsed.headers), { valueKind: 'line_total' });
    assert(totals.transactions[0].amount === 500000, 'line totals are not multiplied twice');

    const originalFetch = window.fetch, originalSend = XMLHttpRequest.prototype.send;
    let requests = 0;
    window.fetch = (...args) => { requests++; return originalFetch(...args); };
    XMLHttpRequest.prototype.send = function (...args) { requests++; return originalSend.apply(this, args); };
    try {
        const transfer = new DataTransfer(); transfer.items.add(new File([fixture.csv], 'fixture.csv', { type: 'text/csv' }));
        $('customerCsvFile').files = transfer.files; $('customerCsvFile').dispatchEvent(new Event('change', { bubbles: true }));
        await wait(() => !$('customerBatchForm').hidden && $('customerSnapshot').value);
        assert(B.parseDate($('customerSnapshot').value) === B.parseDate('2011-12-01T00:00:00'), 'default snapshot is latest valid timestamp');
        input('customerSnapshot', '2011-10-01T00:00:00'); $('customerPurchaseConfirm').click();
        $('customerBatchForm').requestSubmit(); await wait(() => P.getResult() || !$('customerBatchError').hidden);
        assert(P.getResult()?.summary.eligible === result.summary.eligible && !$('customerBatchDashboard').hidden, 'real file input to dashboard');
        assert($('customerBatchKpis').children.length === 6 && !$('customerBatchRatings').hidden && !$('customerBatchFeedback').hidden, 'KPI optional analytics rendered');
        assert($('customerBatchBands').children.length === 3 && $('customerBatchAdvice').children.length === 6, 'segmentation and six actions');
        assert($('customerBatchAdvice').firstElementChild.dataset.action === 'experience', 'evidence based card ordering');
        assert(parseFloat($('customerBatchReturnPercent').textContent) + parseFloat($('customerBatchNonReturnPercent').textContent) === 100, 'visible labels total 100 percent');
        assert($('customerBatchAtRisk').children.length === 5, 'top five at risk');
        const create = URL.createObjectURL, click = HTMLAnchorElement.prototype.click;
        const ua = Object.getOwnPropertyDescriptor(navigator, 'userAgent'), share = Object.getOwnPropertyDescriptor(navigator, 'share'), canShare = Object.getOwnPropertyDescriptor(navigator, 'canShare');
        let saved = null, links = 0, shared = null, lastTarget = '';
        try {
            URL.createObjectURL = blob => { saved = blob; return create(blob); };
            HTMLAnchorElement.prototype.click = function () { links++; lastTarget = this.target; };
            Object.defineProperty(navigator, 'userAgent', { value: 'Desktop test', configurable: true });
            $('customerBatchExport').click();
            const csv = await saved.text();
            assert((await B.parseCSV(csv)).rows.length === result.records.length && links === 1, 'desktop CSV download creates safe local blob');
            $('customerTemplateDownload').click();
            assert((await B.parseCSV(await saved.text())).rows.length === 4, 'synthetic template download');
            Object.defineProperty(navigator, 'userAgent', { value: 'Android Mobile', configurable: true });
            Object.defineProperty(navigator, 'canShare', { value: () => true, configurable: true });
            Object.defineProperty(navigator, 'share', { value: async data => { shared = data; }, configurable: true });
            $('customerBatchExport').click(); await new Promise(r => setTimeout(r, 0));
            assert(shared.files[0].name === 'customer-return-results.csv' && links === 2, 'mobile file sharing stays local');
            Object.defineProperty(navigator, 'share', { value: async () => { throw new DOMException('cancel', 'AbortError'); }, configurable: true });
            $('customerBatchExport').click(); await new Promise(r => setTimeout(r, 0));
            assert(links === 2, 'cancel share does not unexpectedly download');
            Object.defineProperty(navigator, 'userAgent', { value: 'iPhone Safari', configurable: true });
            Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
            $('customerBatchExport').click();
            assert(lastTarget === '_blank' && links === 3, 'iOS preview fallback');
        } finally {
            URL.createObjectURL = create; HTMLAnchorElement.prototype.click = click;
            for (const [key, descriptor] of [['userAgent', ua], ['share', share], ['canShare', canShare]]) { if (descriptor) Object.defineProperty(navigator, key, descriptor); else delete navigator[key]; }
        }
        assert(!window.__batchInjected && !$('customerBatchRows').querySelector('img'), 'customer ID rendered as inert text');
        input('customerBatchSearch', 'active-'); assert($('customerBatchRows').children.length === 5, 'search customer IDs');
        input('customerBatchSearch', ''); input('customerBatchBandFilter', 'LOW');
        assert([...$('customerBatchRows').rows].every(r => r.cells[5].textContent === 'LOW'), 'filter band');
        input('customerBatchBandFilter', ''); input('customerBatchClassFilter', '1');
        assert([...$('customerBatchRows').rows].every(r => r.cells[6].textContent === 'Dự đoán quay lại'), 'filter classification');
        input('customerBatchClassFilter', 'missing'); assert([...$('customerBatchRows').rows].some(r => r.cells[4].textContent === '—'), 'filter insufficient');
        input('customerBatchClassFilter', ''); input('customerBatchSort', 'desc');
        const percentages = [...$('customerBatchRows').rows].map(r => parseFloat(r.cells[4].textContent)).filter(Number.isFinite);
        assert(percentages.every((p, i) => !i || p <= percentages[i - 1]), 'sort probability');
        assert(document.documentElement.scrollWidth <= innerWidth, 'batch no global horizontal overflow');
        assert($('customerBatchRows').children.length <= 25 && getComputedStyle($('customerBatchRows').closest('.cr-table-scroll')).overflowX === 'auto', 'table has bounded paging and inner scroll');
        $('customerBatchTab').click(); $('customerSingleTab').click();
        assert(CustomerReturnPage.getResult() && !$('customerSinglePanel').hidden && $('customerBatchPanel').hidden, 'tab preserves single result');
        $('customerBatchTab').click();
        // Mapping from arbitrary names, parsed correctly without vendor schema.
        const manual = fixture.csv.replace('CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice,Country,StockCode,rating,feedback', 'col1,col2,col3,col4,col5,col6,col7,col8,col9');
        await P.loadFile(new File([manual], 'manual.csv'));
        assert($('customerMap-customer').value === '-1', 'unknown headers remain unmapped');
        for (const [key, index] of Object.entries(mapping)) input('customerMap-' + key, index);
        input('customerSourceProfile', 'uci'); input('customerValueKind', 'unit_price'); input('customerSnapshot', '2011-10-01T00:00:00'); $('customerPurchaseConfirm').click();
        $('customerBatchForm').requestSubmit(); await wait(() => P.getResult() || !$('customerBatchError').hidden);
        assert(P.getResult()?.summary.eligible === result.summary.eligible, 'manual mapping complete UI flow');
        input('customerMap-product', -1);
        assert($('customerBatchDashboard').hidden && P.getResult() === null, 'configuration edit clears old dashboard');
        $('customerBatchForm').requestSubmit(); await wait(() => P.getResult() || !$('customerBatchError').hidden);
        assert(P.getResult()?.summary.eligible === 0 && $('customerBatchReturnPercent').textContent === '—' && $('customerBatchActions').dataset.mode === 'empty', 'zero eligible chart does not invent percentages');
        await P.loadFile(new File(['no csv'], 'file.xlsx')); assert(!$('customerBatchError').hidden && $('customerBatchForm').hidden, 'invalid file type inline error');
        await P.loadFile({ name: 'large.csv', size: B.LIMITS.bytes + 1 }); assert($('customerBatchError').textContent.includes('25 MB'), 'file size limit before reading');
        await P.loadFile(new File(['a,b\n"bad'], 'bad.csv')); assert(!$('customerBatchError').hidden, 'malformed file inline error');
        // Cancellation: replacing a file while reading cannot restore its old data.
        const slow = { name: 'slow.csv', size: 1, text: () => new Promise(resolve => setTimeout(() => resolve(fixture.csv), 60)) };
        const loading = P.loadFile(slow); await P.loadFile(new File(['a,b\n1,2'], 'new.csv')); await loading;
        assert($('customerMap-customer').value === '-1', 'new file supersedes pending parse');
    } finally { window.fetch = originalFetch; XMLHttpRequest.prototype.send = originalSend; }
    assert(requests === 0, 'upload/processing use no fetch or XHR');

    let performance = null;
    if (innerWidth === 1440) {
        const lines = ['customer_id,order_id,order_date,quantity,unit_price,country,product'];
        for (let i = 0; i < 5000; i++) for (let j = 0; j < 4; j++) lines.push(`P${i},O${i}-${j},2011-${['01-01', '07-05', '08-10', '09-20'][j]},2,10,${i % 2 ? 'VN' : 'United Kingdom'},SKU${j}`);
        let beats = 0; const timer = setInterval(() => beats++, 10), start = globalThis.performance.now();
        const large = await B.parseCSV(lines.join('\n')), cooked = await B.prepareTransactions(large, B.detectColumns(large.headers)), output = await B.analyze(cooked, model, B.parseDate('2011-10-01'));
        const ms = globalThis.performance.now() - start; clearInterval(timer);
        assert(output.summary.eligible === 5000 && output.audit.totalRows === 20000 && beats > 3, '20000 rows/5000 customers yield to browser');
        performance = { rows: 20000, customers: 5000, processingMs: ms, responsiveTicks: beats };
        await P.loadFile(new File([lines.join('\n')], 'performance.csv')); input('customerSnapshot', '2011-10-01T00:00:00'); $('customerPurchaseConfirm').click(); $('customerBatchForm').requestSubmit();
        await wait(() => P.getResult() || !$('customerBatchError').hidden);
        assert(P.getResult()?.summary.eligible === 5000 && $('customerBatchRows').rows.length === 25, 'large UI renders only one page');
        $('customerBatchNext').click(); assert($('customerBatchPage').textContent.includes('2/200'), 'large pagination');
    }
    // Exercise real business dashboard branches with generated transactions.
    const branch = async growth => {
        const lines = ['customer_id,order_id,order_date,quantity,unit_price,country,product,rating'];
        for (let i = 0; i < 6; i++) {
            lines.push(`T${i},FIRST${i},2011-01-01,1,20,VN,S1,${growth ? 5 : 1}`);
            if (growth) for (let j = 0; j < 15; j++) lines.push(`T${i},LAST${i}-${j},2011-09-${10+j},10,20,VN,S${j},5`);
        }
        await P.loadFile(new File([lines.join('\n')], 'branch.csv')); input('customerSnapshot', '2011-10-01T00:00:00'); $('customerPurchaseConfirm').click(); $('customerBatchForm').requestSubmit(); await wait(() => P.getResult() || !$('customerBatchError').hidden);
        assert(P.getResult() && $('customerBatchActions').dataset.mode === (growth ? 'growth' : 'retention'), 'real business action branch ' + growth);
    };
    await branch(false); await branch(true);
    assert(document.documentElement.scrollWidth <= innerWidth, 'growth dashboard responsive');
    $('customerBatchClear').click(); assert(P.getResult() === null && $('customerBatchDashboard').hidden && $('customerBatchForm').hidden, 'clear removes file/result');
    await branch(true); // Leave a representative dashboard for browser screenshots.
    assert(!window.__batchInjected && window.__customerErrors.length === 0, 'no injected content or runtime errors');
    return { ok: true, width: innerWidth, checks: checks.length, featureSamples: fixture.features.length, maxFeatureError, maxProbabilityError, performance };
})()
