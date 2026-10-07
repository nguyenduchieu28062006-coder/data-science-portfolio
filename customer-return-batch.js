"use strict";
/* Local CSV -> historical features -> unchanged exported model. No network or storage. */
(() => {
    const DAY = 86400000;
    const LIMITS = Object.freeze({ bytes: 25 * 1024 * 1024, rows: 100000, customers: 20000, columns: 100, cell: 10000 });
    const fields = [
        ['customer', 'Mã khách hàng', true, ['customer_id', 'customerid', 'buyer_id', 'buyerid', 'user_id', 'user', 'khach_hang', 'ma_khach_hang', 'username']],
        ['order', 'Mã đơn hàng', true, ['order_id', 'invoice_no', 'invoiceno', 'invoice', 'order_code', 'ma_don_hang']],
        ['date', 'Ngày mua hàng', true, ['order_date', 'invoice_date', 'invoicedate', 'created_at', 'purchase_date', 'ngay_mua', 'ngay_dat_hang']],
        ['quantity', 'Số lượng', true, ['quantity', 'qty', 'so_luong']],
        ['value', 'Giá trị', true, ['unit_price', 'unitprice', 'price', 'amount', 'total', 'order_value', 'revenue', 'gia', 'gia_tri_don']],
        ['country', 'Quốc gia', true, ['country', 'nation', 'quoc_gia']],
        ['product', 'Mã sản phẩm / SKU (cần để dự đoán)', false, ['stockcode', 'stock_code', 'product_id', 'product', 'product_name', 'item', 'description', 'sku', 'san_pham']],
        ['rating', 'Đánh giá sao (tùy chọn)', false, ['rating', 'stars', 'star', 'review_score', 'danh_gia', 'so_sao']],
        ['feedback', 'Phản hồi (tùy chọn)', false, ['review', 'feedback', 'comment', 'review_text', 'phan_hoi', 'nhan_xet']],
        ['status', 'Trạng thái đơn (tùy chọn)', false, ['order_status', 'status', 'trang_thai', 'trang_thai_don']],
    ];
    const fold = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').trim().toLowerCase();
    const headerKey = value => fold(value).replace(/[^a-z0-9]/g, '');
    const pause = () => new Promise(resolve => setTimeout(resolve, 0));
    const checkAbort = signal => { if (signal?.aborted) throw new DOMException('Đã hủy thao tác', 'AbortError'); };
    const roundEven = (value, digits) => {
        const scale = 10 ** digits, x = value * scale, lower = Math.floor(x), fraction = x - lower;
        return (fraction === .5 ? lower + (lower % 2) : Math.round(x)) / scale;
    };
    const addAmount = (group, value) => {
        const adjusted = value - group.correction, total = group.sum + adjusted;
        group.correction = (total - group.sum) - adjusted;
        group.sum = total;
    };

    async function parseCSV(text, signal) {
        if (typeof text !== 'string' || !text.trim()) throw Error('Tệp CSV trống.');
        if (new Blob([text]).size > LIMITS.bytes) throw Error('Tệp vượt giới hạn 25 MB.');
        text = text.replace(/^\uFEFF/, '');
        const separators = { ',': 0, ';': 0, '\t': 0 };
        let quoted = false;
        for (let i = 0; i < text.length; i++) {
            const c = text[i];
            if (c === '"') { if (quoted && text[i + 1] === '"') i++; else quoted = !quoted; }
            else if (!quoted && (c === '\n' || c === '\r')) break;
            else if (!quoted && c in separators) separators[c]++;
        }
        const delimiter = Object.keys(separators).sort((a, b) => separators[b] - separators[a])[0];
        const records = [];
        let row = [], cell = '', inQuote = false, closed = false, blanks = 0;
        function finishCell() { row.push(cell); cell = ''; closed = false; if (row.length > LIMITS.columns) throw Error('CSV có quá 100 cột.'); }
        function finishRow() {
            finishCell();
            if (row.every(value => !value.trim())) blanks++;
            else records.push(row);
            row = [];
            if (records.length > LIMITS.rows + 1) throw Error('CSV vượt giới hạn 100.000 dòng dữ liệu.');
        }
        for (let i = 0; i < text.length; i++) {
            const c = text[i];
            if (inQuote) {
                if (c === '"') {
                    if (text[i + 1] === '"') { cell += '"'; i++; }
                    else { inQuote = false; closed = true; }
                } else cell += c;
            } else if (c === delimiter) finishCell();
            else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; finishRow(); }
            else if (c === '"' && !cell && !closed) inQuote = true;
            else if (c === '"' || (closed && c.trim())) throw Error('CSV có dấu ngoặc kép không hợp lệ. Hãy kiểm tra cấu trúc tệp.');
            else if (!closed) cell += c;
            if (cell.length > LIMITS.cell) throw Error('Một ô CSV vượt 10.000 ký tự.');
            if (i % 65536 === 0) { checkAbort(signal); await pause(); }
        }
        if (inQuote) throw Error('CSV thiếu dấu ngoặc kép đóng.');
        if (cell || row.length || closed) finishRow();
        const headers = records.shift()?.map(value => value.trim());
        if (!headers?.length || headers.some(value => !value) || new Set(headers.map(headerKey)).size !== headers.length) throw Error('Tên cột trống hoặc trùng nhau; hãy sửa header CSV.');
        if (!records.length) throw Error('CSV không có dòng dữ liệu.');
        return { headers, rows: records, blankRows: blanks, delimiter };
    }

    function detectColumns(headers) {
        const mapping = {};
        for (const [key, , , aliases] of fields) {
            const candidates = headers.map((header, index) => aliases.map(headerKey).includes(headerKey(header)) ? index : -1).filter(index => index >= 0);
            mapping[key] = candidates.length === 1 ? candidates[0] : -1;
            // Prefer the real product identifier over a description when both exist.
            if (key === 'product' && candidates.length > 1) mapping[key] = candidates.find(index => ['stockcode', 'sku', 'productid', 'product'].includes(headerKey(headers[index]))) ?? -1;
        }
        return mapping;
    }

    function parseNumber(value, format = 'dot') {
        let text = String(value ?? '').trim();
        const decimal = format === 'comma' ? ',' : '.', group = format === 'comma' ? '.' : ',';
        const escaped = group === '.' ? '\\.' : ',', dec = decimal === '.' ? '\\.' : ',';
        const pattern = new RegExp('^[+-]?(?:\\d+|\\d{1,3}(?:' + escaped + '\\d{3})+)(?:' + dec + '\\d+)?$');
        if (!pattern.test(text)) return NaN;
        text = text.split(group).join('').replace(decimal, '.');
        const number = Number(text);
        return Number.isFinite(number) ? number : NaN;
    }

    function parseDate(value, format = 'ISO') {
        const text = String(value ?? '').trim();
        const pattern = format === 'ISO' ? /^(\d{4})[-/](\d{2})[-/](\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})?)?$/ : /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/;
        const match = text.match(pattern);
        if (!match) return NaN;
        const datePart = text.split(/[T ]/)[0];
        if (datePart.includes('/') && datePart.includes('-')) return NaN;
        const year = Number(match[format === 'ISO' ? 1 : 3]);
        const month = Number(match[format === 'ISO' ? 2 : format === 'DMY' ? 2 : 1]);
        const day = Number(match[format === 'ISO' ? 3 : format === 'DMY' ? 1 : 2]);
        const hour = Number(match[4] || 0), minute = Number(match[5] || 0), second = Number(match[6] || 0);
        const ms = Number((match[7] || '').padEnd(3, '0'));
        if (year < 1900 || year > 9999 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return NaN;
        const timestamp = Date.UTC(year, month - 1, day, hour, minute, second, ms);
        if (new Date(timestamp).getUTCDate() !== day || day < 1) return NaN;
        const offset = format === 'ISO' ? match[8] : '';
        if (offset && offset !== 'Z') {
            const [h, m] = offset.slice(1).split(':').map(Number);
            if (h > 23 || m > 59) return NaN;
            return timestamp - (offset[0] === '+' ? 1 : -1) * (h * 60 + m) * 60000;
        }
        return timestamp;
    }

    const FORMAT_SAMPLE = Object.freeze({ rows: 200, values: 20 });
    function detectFormats(parsed, mapping) {
        // One bounded pass; invalid cells do not vote for a format. Integers are
        // neutral because both number conventions produce the same value.
        let dates = ['ISO', 'DMY', 'MDY'], numbers = ['dot', 'comma'];
        let dateSamples = 0, numberSamples = 0, differentNumbers = false, scannedRows = 0;
        for (const row of parsed.rows.slice(0, FORMAT_SAMPLE.rows)) {
            scannedRows++;
            if (row.length !== parsed.headers.length) continue;
            if (dateSamples < FORMAT_SAMPLE.values && mapping.date >= 0) {
                const candidates = ['ISO', 'DMY', 'MDY'].filter(format => Number.isFinite(parseDate(row[mapping.date], format)));
                if (candidates.length) { dateSamples++; dates = dates.filter(format => candidates.includes(format)); }
            }
            for (const key of ['quantity', 'value']) if (numberSamples < FORMAT_SAMPLE.values && mapping[key] >= 0) {
                const value = row[mapping[key]], dot = parseNumber(value, 'dot'), comma = parseNumber(value, 'comma');
                const candidates = ['dot', 'comma'].filter(format => Number.isFinite(format === 'dot' ? dot : comma));
                if (candidates.length) {
                    numberSamples++; numbers = numbers.filter(format => candidates.includes(format));
                    differentNumbers ||= Number.isFinite(dot) && Number.isFinite(comma) && dot !== comma;
                }
            }
            if (dateSamples >= FORMAT_SAMPLE.values && numberSamples >= FORMAT_SAMPLE.values) break;
        }
        return {
            date: { format: dateSamples && dates.length === 1 ? dates[0] : null, candidates: dates, samples: dateSamples },
            number: { format: numberSamples && numbers.length === 1 ? numbers[0] : numberSamples && numbers.length === 2 && !differentNumbers ? 'dot' : null,
                candidates: numbers, samples: numberSamples, integersOnly: numbers.length === 2 && !differentNumbers },
            scannedRows,
        };
    }

    function resolveFormats(parsed, mapping, options) {
        const detected = detectFormats(parsed, mapping);
        const dateMode = options.dateFormat ?? 'auto', numberMode = options.numberFormat ?? 'auto';
        const dateFormat = dateMode === 'auto' ? detected.date.format : dateMode;
        const numberFormat = numberMode === 'auto' ? detected.number.format : numberMode;
        const errors = [];
        if (!dateFormat) errors.push(detected.date.samples && !detected.date.candidates.length
            ? 'Các định dạng ngày trong mẫu không thống nhất. Vui lòng chọn định dạng ngày hoặc chuẩn hóa tệp.'
            : 'Không thể xác định chắc chắn định dạng ngày. Vui lòng chọn DMY hoặc MDY. Nếu tệp dùng năm/tháng/ngày, chọn ISO.');
        if (!numberFormat) errors.push(detected.number.samples && !detected.number.candidates.length
            ? 'Các định dạng số trong mẫu không thống nhất. Vui lòng chọn định dạng số hoặc chuẩn hóa tệp.'
            : 'Không thể xác định chắc chắn định dạng số. Vui lòng chọn dấu chấm hoặc dấu phẩy thập phân.');
        return { dateMode, numberMode, dateFormat, numberFormat, detected, errors };
    }

    function validateMapping(parsed, mapping) {
        const indices = [];
        for (const [key, label, required] of fields) {
            const index = mapping[key] ?? -1;
            if (required && index === -1) throw Error('Không tìm thấy ' + label.toLowerCase() + '. Hãy ánh xạ cột tương ứng.');
            if (!Number.isInteger(index) || index < -1 || index >= parsed.headers.length) throw Error('Ánh xạ cột không hợp lệ.');
            if (index >= 0) indices.push(index);
        }
        if (new Set(indices).size !== indices.length) throw Error('Một cột không thể ánh xạ cho nhiều trường.');
    }

    async function prepareTransactions(parsed, mapping, options = {}, signal) {
        validateMapping(parsed, mapping);
        const config = { valueKind: 'unit_price', currency: 'GBP', dateFormat: 'auto', numberFormat: 'auto', profile: 'generic', ...options };
        if (!['unit_price', 'line_total'].includes(config.valueKind) || !['GBP', 'VND'].includes(config.currency) || !['auto', 'ISO', 'DMY', 'MDY'].includes(config.dateFormat) || !['auto', 'dot', 'comma'].includes(config.numberFormat) || !['generic', 'uci'].includes(config.profile)) throw Error('Cấu hình tệp không hợp lệ.');
        const rate = config.currency === 'GBP' ? 1 : Number(config.exchangeRate);
        if (!Number.isFinite(rate) || rate <= 0) throw Error('Vui lòng nhập tỷ giá VND cho 1 GBP hợp lệ.');
        const formats = resolveFormats(parsed, mapping, config);
        if (formats.errors.length) throw Error(formats.errors.join(' '));
        Object.assign(config, formats);
        const transactions = [], customers = new Set(), seen = new Set(), ignored = {};
        const descriptionIndex = config.profile === 'uci' ? parsed.headers.findIndex(header => headerKey(header) === 'description') : -1;
        const skip = reason => { ignored[reason] = (ignored[reason] || 0) + 1; };
        let maxDate = -Infinity, invalidRatings = 0;
        for (let i = 0; i < parsed.rows.length; i++) {
            const row = parsed.rows[i], get = key => mapping[key] >= 0 ? String(row[mapping[key]] ?? '').trim() : '';
            const id = get('customer');
            if (id) customers.add(id);
            if (customers.size > LIMITS.customers) throw Error('Tệp vượt giới hạn 20.000 khách hàng.');
            // Descriptive metadata and PII never change transaction identity or
            // model inputs, even if a duplicate carries a different review.
            const fingerprint = JSON.stringify([...['customer', 'order', 'date', 'quantity', 'value', 'country', 'product', 'status'].map(get), descriptionIndex >= 0 ? row[descriptionIndex] : '']);
            if (seen.has(fingerprint)) skip('Dòng trùng chính xác');
            else {
                seen.add(fingerprint);
                const order = get('order'), date = parseDate(get('date'), config.dateFormat), quantity = parseNumber(get('quantity'), config.numberFormat), value = parseNumber(get('value'), config.numberFormat), country = get('country'), product = get('product');
                const status = fold(get('status'));
                if (row.length !== parsed.headers.length) skip('Số ô không khớp header');
                else if (!id || !order || id.length > 200 || order.length > 200) skip('Thiếu hoặc mã khách/đơn quá dài');
                else if (!Number.isFinite(date)) skip('Ngày không hợp lệ');
                else if ((config.profile === 'uci' && /^c/i.test(order)) || ['cancelled', 'canceled', 'refunded', 'huy', 'da huy', 'hoan tien', 'da hoan tien'].includes(status)) skip('Đơn hủy / hoàn tiền');
                else if (!(quantity > 0 && value > 0)) skip('Số lượng / giá trị không dương hoặc không hợp lệ');
                else if (config.profile === 'uci' && mapping.product >= 0 && !/^\d{5}[A-Za-z]?$/.test(product)) skip('StockCode không phải sản phẩm UCI');
                else if (!country || country.length > 100) skip('Quốc gia không hợp lệ');
                else {
                    const amount = (config.valueKind === 'unit_price' ? quantity * value : value) / rate;
                    if (!Number.isFinite(amount) || amount <= 0) skip('Không thể tính tiền sản phẩm');
                    else {
                        const rating = parseNumber(get('rating'), config.numberFormat);
                        if (get('rating') && !(Number.isInteger(rating) && rating >= 1 && rating <= 5)) invalidRatings++;
                        transactions.push({ id, order, date, amount, product, country, rating: Number.isInteger(rating) && rating >= 1 && rating <= 5 ? rating : null, feedback: Boolean(get('feedback')) });
                        maxDate = Math.max(maxDate, date);
                    }
                }
            }
            if (i % 1000 === 0) { checkAbort(signal); await pause(); }
        }
        const audit = { totalRows: parsed.rows.length, inputRows: parsed.rows.length + parsed.blankRows, validRows: transactions.length, ignoredRows: parsed.rows.length - transactions.length, blankRows: parsed.blankRows, invalidRatings, ignored };
        if (!transactions.length) {
            const reasons = Object.entries(ignored).map(([reason, count]) => `${reason}: ${count}`).join('; ');
            const error = Error('Không có đủ giao dịch hợp lệ để phân tích. ' + reasons + '. Kiểm tra ánh xạ cột và định dạng ngày/số.');
            error.audit = audit;
            throw error;
        }
        return { transactions, customers: [...customers], maxDate, config, audit };
    }

    async function analyze(prepared, model, snapshot = prepared.maxDate, signal, progress) {
        if (!Number.isFinite(snapshot)) throw Error('Ngày phân tích không hợp lệ.');
        const groups = new Map(), ratingCounts = [0, 0, 0, 0, 0];
        let ratingSum = 0, ratingCount = 0, feedbackCount = 0, beforeRows = 0;
        for (let i = 0; i < prepared.transactions.length; i++) {
            const t = prepared.transactions[i];
            if (t.date < snapshot) {
                beforeRows++;
                if (!groups.has(t.id)) groups.set(t.id, { invoices: new Map(), orders: new Set(), products: new Set(), sum: 0, correction: 0, lastCountryDate: -Infinity, missingProduct: false, ratings: [] });
                const group = groups.get(t.id);
                group.invoices.set(t.order, Math.min(group.invoices.get(t.order) ?? Infinity, t.date));
                group.missingProduct ||= !t.product;
                if (t.date >= group.lastCountryDate) { group.lastCountryDate = t.date; group.country = t.country; }
                if (t.date >= snapshot - 90 * DAY) { group.orders.add(t.order); group.products.add(t.product); addAmount(group, t.amount); }
                if (t.rating !== null) { ratingCounts[t.rating - 1]++; ratingSum += t.rating; ratingCount++; group.ratings.push(t.rating); }
                if (t.feedback) feedbackCount++;
            }
            if (i % 1000 === 0) { checkAbort(signal); await pause(); }
        }
        const records = [], bands = { HIGH: 0, MEDIUM: 0, LOW: 0 };
        let returnCount = 0, probabilitySum = 0, domainWarnings = 0;
        for (let i = 0; i < prepared.customers.length; i++) {
            const id = prepared.customers[i], group = groups.get(id);
            const record = { customer_id: id, features: null, probability: null, nonReturnProbability: null, classification: null, band: null, status: 'Không đủ dữ liệu', reason: '', rating: null, lastPurchase: null };
            if (!group) record.reason = 'Không có giao dịch hợp lệ trước ngày phân tích';
            else {
                // Training groups invoice dates by min, then first/last invoice.
                const dates = [...group.invoices.values()];
                let first = Infinity, last = -Infinity;
                for (const date of dates) { first = Math.min(first, date); last = Math.max(last, date); }
                record.lastPurchase = new Date(last).toISOString();
                record.rating = group.ratings.length ? group.ratings.reduce((a, b) => a + b, 0) / group.ratings.length : null;
                record.features = { recency_days: Math.floor((snapshot - last) / DAY), tenure_days: Math.floor((snapshot - first) / DAY), orders_90d: group.orders.size, monetary_90d: roundEven(group.sum, 2), products_90d: group.products.size, avg_purchase_gap_days: dates.length > 1 ? roundEven((last - first) / DAY / (dates.length - 1), 4) : 0, country: group.country };
                if (group.missingProduct) { record.features.products_90d = null; record.reason = 'Thiếu mã sản phẩm trong lịch sử; không bịa products_90d'; }
                else try {
                    const prediction = CustomerReturnModel.predict(model, record.features);
                    record.probability = prediction.probability;
                    record.nonReturnProbability = prediction.nonReturnProbability;
                    record.classification = prediction.predictedClass;
                    record.band = prediction.band.toUpperCase();
                    record.status = prediction.predictedClass ? 'Dự đoán quay lại' : 'Nguy cơ không quay lại';
                    bands[record.band]++;
                    returnCount += record.classification;
                    probabilitySum += record.probability;
                    if (prediction.warnings.length) domainWarnings++;
                } catch (error) { record.reason = 'Không thể tính feature hợp lệ: ' + error.message; }
            }
            records.push(record);
            if (i % 100 === 0) { checkAbort(signal); progress?.(i, prepared.customers.length); await pause(); }
        }
        const eligible = records.filter(record => record.probability !== null), count = eligible.length;
        const returnRatio = count ? returnCount / count : 0;
        return { records, snapshot, audit: { ...prepared.audit, beforeRows, atOrAfterSnapshot: prepared.transactions.length - beforeRows }, summary: { total: records.length, eligible: count, insufficient: records.length - count, returnCount, nonReturnCount: count - returnCount, returnRatio, nonReturnRatio: count ? 1 - returnRatio : 0, averageProbability: count ? probabilitySum / count : null, bands, domainWarnings }, ratings: { count: ratingCount, average: ratingCount ? ratingSum / ratingCount : null, lowRatio: ratingCount ? (ratingCounts[0] + ratingCounts[1]) / ratingCount : null, highRatio: ratingCount ? (ratingCounts[3] + ratingCounts[4]) / ratingCount : null, counts: ratingCounts }, feedbackCount, config: prepared.config };
    }

    function actionPlan(result) {
        const s = result.summary;
        const mode = s.eligible === 0 ? 'empty' : s.returnRatio < .45 ? 'retention' : s.returnRatio > .55 ? 'growth' : 'balanced';
        const eligible = result.records.filter(r => r.probability !== null);
        const old = eligible.filter(r => r.features.recency_days >= 60).length;
        const infrequent = eligible.filter(r => r.features.orders_90d <= 1).length;
        const negative = result.ratings.count && result.ratings.lowRatio >= .25;
        const priority = negative ? 'experience' : old > eligible.length / 2 ? 'reactivation' : infrequent > eligible.length / 2 ? 'loyalty' : null;
        const evidence = [negative ? `${(result.ratings.lowRatio * 100).toFixed(1)}% đánh giá hợp lệ ở mức 1–2 sao` : '', old ? `${old} khách đủ dữ liệu có recency từ 60 ngày` : '', infrequent ? `${infrequent} khách đủ dữ liệu có tối đa 1 đơn trong 90 ngày` : ''].filter(Boolean);
        return { mode, priority, evidence };
    }

    const csvCell = value => {
        let text = value == null ? '' : String(value);
        // Guard spreadsheet formulas, including whitespace-prefixed payloads.
        if (/^[\s\uFEFF]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text;
        return '"' + text.replace(/"/g, '""') + '"';
    };
    function exportCSV(result) {
        const columns = ['customer_id', 'return_probability', 'non_return_probability', 'classification', 'prediction', 'band', 'orders_90d', 'monetary_90d_gbp', 'recency_days', 'tenure_days', 'products_90d', 'avg_purchase_gap_days', 'country', 'last_purchase', 'rating_average', 'reason'];
        const rows = result.records.map(r => [r.customer_id, r.probability, r.nonReturnProbability, r.classification, r.status, r.band, r.features?.orders_90d, r.features?.monetary_90d, r.features?.recency_days, r.features?.tenure_days, r.features?.products_90d, r.features?.avg_purchase_gap_days, r.features ? CustomerReturnModel.isVietnam(r.features.country) ? 'Việt Nam' : r.features.country : '', r.lastPurchase, r.rating, r.reason]);
        return '\uFEFF' + [columns, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n');
    }
    const sampleCSV = () => 'customer_id,order_id,order_date,quantity,unit_price,country,product,rating,feedback\r\nDEMO01,O01,2026-01-01,1,20,Vietnam,SKU01,5,"Giao hàng đúng hẹn"\r\nDEMO01,O02,2026-09-20,2,20,Vietnam,SKU02,4,""\r\nDEMO02,O03,2026-02-01,1,12,United Kingdom,SKU03,2,"Cần hỗ trợ sau mua"\r\nDEMO03,O04,2026-10-01,1,15,VN,SKU04,,""\r\n';
    globalThis.CustomerReturnBatch = Object.freeze({ LIMITS, FORMAT_SAMPLE, fields, parseCSV, detectColumns, detectFormats, resolveFormats, parseDate, parseNumber, prepareTransactions, analyze, actionPlan, exportCSV, sampleCSV });

    if (typeof document !== 'undefined') initializeUI();

    function initializeUI() {
        const $ = id => document.getElementById(id);
        if (!$('customerBatchPanel')) return;
        let parsed = null, result = null, controller = null, revision = 0, page = 0, defaultSnapshot = true;
        const tabs = [$('customerSingleTab'), $('customerBatchTab')];
        const panels = [$('customerSinglePanel'), $('customerBatchPanel')];
        function selectTab(index) { tabs.forEach((tab, i) => { tab.setAttribute('aria-selected', String(i === index)); tab.tabIndex = i === index ? 0 : -1; panels[i].hidden = i !== index; }); }
        tabs.forEach((tab, i) => {
            tab.addEventListener('click', () => selectTab(i));
            tab.addEventListener('keydown', e => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) { e.preventDefault(); const next = e.key === 'Home' ? 0 : e.key === 'End' ? 1 : 1 - i; selectTab(next); tabs[next].focus(); } });
        });
        document.querySelector('a[href="#customer-input"]')?.addEventListener('click', () => selectTab(0));
        const node = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; };
        const message = text => { $('customerBatchError').textContent = text; $('customerBatchError').hidden = !text; };
        function clearResult() { result = null; page = 0; $('customerBatchDashboard').hidden = true; $('customerBatchRows').replaceChildren(); $('customerBatchAtRisk').replaceChildren(); $('customerBatchAdvice').replaceChildren(); $('customerBatchDownloadNotice').textContent = ''; }
        const cancel = () => { revision++; controller?.abort(); controller = null; $('customerBatchAnalyze').disabled = false; };
        function config() { return { valueKind: $('customerValueKind').value, currency: $('customerCurrency').value, exchangeRate: $('customerExchangeRate').value, dateFormat: $('customerDateFormat').value, numberFormat: $('customerNumberFormat').value, profile: $('customerSourceProfile').value }; }
        function mapping() { return Object.fromEntries(fields.map(([key]) => [key, Number($('customerMap-' + key).value)])); }
        const dateLabels = { ISO: 'YYYY-MM-DD / YYYY/MM/DD', DMY: 'DD/MM/YYYY / DD-MM-YYYY', MDY: 'MM/DD/YYYY / MM-DD-YYYY' };
        const numberLabels = { dot: '1,234.56', comma: '1.234,56' };
        function formatDescriptions(formats) {
            return [
                formats.dateMode === 'auto' ? `✓ Đã nhận dạng ngày: ${dateLabels[formats.dateFormat]}` : `Định dạng ngày: ${dateLabels[formats.dateFormat]} (do người dùng chọn)`,
                formats.numberMode !== 'auto' ? `Định dạng số: ${numberLabels[formats.numberFormat]} (do người dùng chọn)` : formats.detected.number.integersOnly ? '✓ Đã nhận dạng số: số nguyên, không có dấu phân cách mơ hồ' : `✓ Đã nhận dạng số: ${numberLabels[formats.numberFormat]}`,
            ];
        }
        function refreshFormats() {
            if (!parsed) return null;
            try { validateMapping(parsed, mapping()); }
            catch { $('customerDateDetection').textContent = 'Kiểm tra ánh xạ các cột bắt buộc để nhận dạng ngày.'; $('customerNumberDetection').textContent = 'Kiểm tra ánh xạ các cột bắt buộc để nhận dạng số.'; return null; }
            const formats = resolveFormats(parsed, mapping(), config()), descriptions = formatDescriptions(formats);
            $('customerDateDetection').textContent = formats.dateFormat ? descriptions[0] : formats.errors.find(e => e.includes('ngày'));
            $('customerNumberDetection').textContent = formats.numberFormat ? descriptions[1] : formats.errors.find(e => e.includes('số'));
            $('customerBatchAnalyze').disabled = formats.errors.length > 0;
            if (formats.errors.length) { $('customerBatchStatus').textContent = 'Cần chọn định dạng ngày/số trước khi phân tích.'; return null; }
            return formats;
        }
        function renderMapping() {
            const detected = detectColumns(parsed.headers);
            $('customerColumnMapping').replaceChildren();
            for (const [key, label, required] of fields) {
                const field = node('div', undefined, 'cr-field'), select = node('select'), title = node('label', label + (required ? ' *' : ''));
                select.id = 'customerMap-' + key; title.htmlFor = select.id;
                select.add(new Option(required ? 'Chọn cột bắt buộc' : 'Không có / không sử dụng', '-1'));
                parsed.headers.forEach((header, i) => select.add(new Option(header, String(i))));
                select.value = String(detected[key]); field.append(title, select); $('customerColumnMapping').append(field);
            }
            $('customerValueKind').value = detected.value >= 0 && ['unitprice', 'price', 'gia'].includes(headerKey(parsed.headers[detected.value])) ? 'unit_price' : 'line_total';
            $('customerSourceProfile').value = parsed.headers.some(h => headerKey(h) === 'stockcode') && parsed.headers.some(h => headerKey(h) === 'invoiceno') ? 'uci' : 'generic';
        }
        async function updateDefaultSnapshot() {
            if (!parsed || !refreshFormats() || !defaultSnapshot) return;
            const version = revision;
            controller ??= new AbortController();
            try {
                const prepared = await prepareTransactions(parsed, mapping(), config(), controller.signal);
                if (version === revision && defaultSnapshot) $('customerSnapshot').value = new Date(prepared.maxDate).toISOString().slice(0, 19);
            } catch { if (version === revision && defaultSnapshot) $('customerSnapshot').value = ''; }
        }
        async function loadFile(file) {
            cancel(); clearResult(); message(''); parsed = null;
            $('customerBatchForm').hidden = true;
            $('customerSnapshot').value = ''; defaultSnapshot = true;
            $('customerPurchaseConfirm').checked = false;
            if (!file) { $('customerBatchStatus').textContent = 'Chưa có tệp.'; return; }
            if (!/\.csv$/i.test(file.name)) { message('Chỉ hỗ trợ tệp .csv.'); return; }
            if (file.size > LIMITS.bytes) { message('Tệp vượt giới hạn 25 MB. Hãy chia nhỏ dữ liệu.'); return; }
            const version = revision; controller = new AbortController();
            $('customerBatchStatus').textContent = 'Đang đọc CSV trên thiết bị…';
            try {
                const content = await file.text();
                if (version !== revision) return;
                const nextParsed = await parseCSV(content, controller.signal);
                if (version !== revision) return;
                parsed = nextParsed;
                renderMapping(); $('customerBatchForm').hidden = false;
                $('customerBatchStatus').textContent = `Đã đọc ${parsed.rows.length.toLocaleString('vi-VN')} dòng và ${parsed.headers.length} cột. Kiểm tra mapping, ngày và đơn vị tiền trước khi phân tích.`;
                await updateDefaultSnapshot();
            } catch (error) { if (version === revision && error.name !== 'AbortError') { message(error.message); $('customerBatchStatus').textContent = 'Không đọc được tệp. Hãy kiểm tra và chọn lại.'; } }
        }
        $('customerCsvFile').addEventListener('change', e => loadFile(e.target.files[0]));
        const drop = $('customerDropZone');
        drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('cr-dragging'); });
        drop.addEventListener('dragleave', () => drop.classList.remove('cr-dragging'));
        drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('cr-dragging'); if (e.dataTransfer.files.length !== 1) { message('Vui lòng chọn một tệp CSV mỗi lần.'); return; } loadFile(e.dataTransfer.files[0]); });
        $('customerBatchForm').addEventListener('input', e => {
            cancel(); clearResult(); message('');
            if (e.target.id === 'customerSnapshot') defaultSnapshot = false;
            $('customerExchangeField').hidden = $('customerCurrency').value !== 'VND';
            if (e.target.id !== 'customerSnapshot' && e.target.id !== 'customerPurchaseConfirm') updateDefaultSnapshot();
            else refreshFormats();
        });
        $('customerBatchClear').addEventListener('click', () => { cancel(); clearResult(); parsed = null; $('customerCsvFile').value = ''; $('customerBatchForm').hidden = true; $('customerColumnMapping').replaceChildren(); $('customerDateDetection').textContent = ''; $('customerNumberDetection').textContent = ''; message(''); $('customerBatchStatus').textContent = 'Đã xóa tệp và kết quả khỏi phiên phân tích.'; });
        $('customerBatchForm').addEventListener('submit', async e => {
            e.preventDefault(); cancel(); clearResult(); message('');
            if (!parsed) return;
            if (!$('customerPurchaseConfirm').checked) { message('Hãy xác nhận tệp chứa các dòng sản phẩm và xử lý đơn hủy/hoàn tiền trước khi phân tích.'); $('customerPurchaseConfirm').focus(); return; }
            const model = CustomerReturnPage.getModel();
            if (!model) { message('Mô hình chưa sẵn sàng. Hãy tải lại mô hình trước khi phân tích.'); return; }
            const version = revision; controller = new AbortController(); $('customerBatchAnalyze').disabled = true;
            $('customerBatchStatus').textContent = 'Đang kiểm tra và tổng hợp lịch sử…';
            try {
                const prepared = await prepareTransactions(parsed, mapping(), config(), controller.signal);
                if (version !== revision) return;
                if (!$('customerSnapshot').value && defaultSnapshot) $('customerSnapshot').value = new Date(prepared.maxDate).toISOString().slice(0, 19);
                const snapshot = parseDate($('customerSnapshot').value);
                const nextResult = await analyze(prepared, model, snapshot, controller.signal, (done, total) => { $('customerBatchStatus').textContent = `Đang dự đoán ${done.toLocaleString('vi-VN')} / ${total.toLocaleString('vi-VN')} khách…`; });
                if (version !== revision) return;
                result = nextResult;
                renderDashboard(); $('customerBatchStatus').textContent = 'Đã hoàn tất phân tích trên thiết bị.';
            } catch (error) { if (version === revision && error.name !== 'AbortError') { clearResult(); message(error.message); $('customerBatchStatus').textContent = 'Chưa thể phân tích. Kiểm tra các cột và cấu hình.'; } }
            finally { if (version === revision) { $('customerBatchAnalyze').disabled = false; refreshFormats(); } }
        });

        function renderCleaningSummary() {
            const a = result.audit, reasons = a.ignored;
            const count = key => reasons[key] || 0;
            const counts = [
                ['input', 'Tổng dòng trong tệp (không tính header)', a.inputRows], ['valid', 'Dòng hợp lệ', a.validRows],
                ['blank', 'Dòng trống', a.blankRows], ['duplicate', 'Dòng trùng', count('Dòng trùng chính xác')],
                ['date', 'Ngày không hợp lệ', count('Ngày không hợp lệ')],
                ['number', 'Số lượng / giá không hợp lệ', count('Số lượng / giá trị không dương hoặc không hợp lệ') + count('Không thể tính tiền sản phẩm')],
                ['cancelled', 'Đơn hủy / hoàn tiền', count('Đơn hủy / hoàn tiền')],
                ['id', 'Mã khách / mã đơn không hợp lệ', count('Thiếu hoặc mã khách/đơn quá dài')],
                ['country', 'Quốc gia không hợp lệ', count('Quốc gia không hợp lệ')],
                ['shape', 'Số ô không khớp header', count('Số ô không khớp header')],
                ['product', 'StockCode không phải sản phẩm UCI', count('StockCode không phải sản phẩm UCI')],
                ['rating', 'Đánh giá không hợp lệ (không bỏ giao dịch)', a.invalidRatings], ['ignored', 'Dòng bị bỏ (không gồm dòng trống)', a.ignoredRows],
                ['eligible', 'Khách đủ dữ liệu', result.summary.eligible], ['insufficient', 'Khách không đủ dữ liệu', result.summary.insufficient],
            ];
            $('customerCleaningCounts').replaceChildren(...counts.map(([key, label, value]) => { const row = node('div'); row.dataset.cleaning = key; row.append(node('dt', label), node('dd', value.toLocaleString('vi-VN'))); return row; }));
            $('customerCleaningFormats').textContent = formatDescriptions(result.config).join(' · ');
            $('customerCleaningReconciliation').textContent = `Đối soát: ${a.inputRows} dòng = ${a.validRows} hợp lệ + ${a.ignoredRows} bị bỏ + ${a.blankRows} trống. Mỗi dòng bị bỏ chỉ có một lý do đầu tiên; đánh giá lỗi không cộng vào dòng bị bỏ. Dòng CSV nhiều dòng trong dấu ngoặc kép được tính là một bản ghi.`;
            $('customerCleaningWarning').hidden = !(a.totalRows && a.ignoredRows / a.totalRows > .2);
        }

        function renderDashboard() {
            const s = result.summary;
            $('customerBatchDashboard').hidden = false;
            renderCleaningSummary();
            const explanations = Object.entries(result.audit.ignored).map(([reason, count]) => `${reason}: ${count}`).join('; ');
            $('customerBatchAudit').textContent = `${result.audit.validRows} dòng hợp lệ; ${result.audit.ignoredRows} dòng bỏ qua; ${result.audit.blankRows} dòng trống. ${result.audit.beforeRows} dòng trước mốc; ${result.audit.atOrAfterSnapshot} dòng tại/sau mốc không vào feature. ${s.insufficient} khách không đủ dữ liệu; ${s.domainWarnings} khách có cảnh báo ngoài phạm vi train.${explanations ? ' Lý do bỏ qua: ' + explanations + '.' : ''}`;
            const kpis = [['Tổng số khách hàng', s.total], ['Khách đủ dữ liệu dự đoán', s.eligible], ['Dự đoán quay lại', s.returnCount], ['Nguy cơ không quay lại', s.nonReturnCount], ['Xác suất quay lại trung bình', s.averageProbability === null ? '—' : (s.averageProbability * 100).toFixed(1) + '%']];
            if (result.ratings.count) kpis.push(['Điểm đánh giá trung bình', result.ratings.average.toFixed(2) + '/5']);
            $('customerBatchKpis').replaceChildren(...kpis.map(([label, value]) => { const dl = node('dl', undefined, 'cr-metric'); dl.append(node('dt', label), node('dd', value)); return dl; }));
            const labels = CustomerReturnModel.percentageLabels(s.returnRatio);
            $('customerBatchReturnPercent').textContent = s.eligible ? labels.returned : '—';
            $('customerBatchNonReturnPercent').textContent = s.eligible ? labels.nonReturned : '—';
            $('customerBatchReturnCount').textContent = `${s.returnCount} khách`;
            $('customerBatchNonReturnCount').textContent = `${s.nonReturnCount} khách`;
            $('customerBatchReturnBar').style.width = `${s.returnRatio * 100}%`;
            $('customerBatchNonReturnBar').style.width = `${s.nonReturnRatio * 100}%`;
            $('customerBatchReturnChart').setAttribute('aria-label', s.eligible ? `Dự đoán quay lại ${labels.returned}, ${s.returnCount} khách; nguy cơ không quay lại ${labels.nonReturned}, ${s.nonReturnCount} khách.` : 'Không có khách đủ dữ liệu để tính tỷ lệ dự đoán.');
            $('customerBatchBands').replaceChildren(...Object.entries(s.bands).map(([band, count]) => { const item = node('div', undefined, 'cr-band-column'); item.dataset.band = band; const track = node('div', undefined, 'cr-band-track'), bar = node('span'); bar.style.height = `${s.eligible ? count / s.eligible * 100 : 0}%`; track.append(bar); item.append(node('strong', `${count} khách`), track, node('b', band), node('small', `${s.eligible ? (count / s.eligible * 100).toFixed(1) : '0.0'}%`)); return item; }));
            $('customerBatchRatings').hidden = !result.ratings.count;
            $('customerBatchRatingSummary').textContent = `${result.ratings.count} đánh giá hợp lệ · Trung bình ${result.ratings.average?.toFixed(2) ?? '—'}/5 · 1–2 sao: ${((result.ratings.lowRatio ?? 0) * 100).toFixed(1)}% · 4–5 sao: ${((result.ratings.highRatio ?? 0) * 100).toFixed(1)}%. ${result.audit.invalidRatings} rating trong tệp không hợp lệ, không dùng thống kê. Tính trên dòng sản phẩm trong lịch sử; không phải tỷ lệ khách duy nhất.`;
            $('customerBatchRatingBars').replaceChildren(...result.ratings.counts.map((count, i) => { const item = node('div', undefined, 'cr-rating-row'), track = node('div'), bar = node('span'); bar.style.width = `${result.ratings.count ? count / result.ratings.count * 100 : 0}%`; track.append(bar); item.append(node('b', `${i + 1} sao`), track, node('span', count)); return item; }));
            $('customerBatchFeedback').hidden = !result.feedbackCount;
            $('customerBatchFeedbackSummary').textContent = `${result.feedbackCount} dòng lịch sử sản phẩm có phản hồi không rỗng. Nội dung không được xuất ra CSV kết quả.`;
            renderActions();
            const lowest = result.records.filter(r => r.probability !== null).sort((a, b) => a.probability - b.probability).slice(0, 5);
            $('customerBatchAtRisk').replaceChildren(...lowest.map(r => { const item = node('li'); item.append(node('strong', r.customer_id), node('span', `${(r.probability * 100).toFixed(1)}% · ${r.band}`)); return item; }));
            if (!lowest.length) $('customerBatchAtRisk').append(node('li', 'Không có khách đủ dữ liệu dự đoán.'));
            $('customerBatchSearch').value = ''; $('customerBatchBandFilter').value = ''; $('customerBatchClassFilter').value = ''; page = 0; renderTable();
        }

        function renderActions() {
            const plan = actionPlan(result);
            const titles = { retention: 'Cần ưu tiên chiến lược giữ chân khách hàng', growth: 'Tỷ lệ khách có khả năng quay lại đang chiếm ưu thế.', balanced: 'Cơ cấu khách hàng đang tương đối cân bằng. Nên tập trung nhóm LOW và MEDIUM để cải thiện retention.', empty: 'Chưa đủ dữ liệu để đề xuất theo phân nhóm dự đoán' };
            $('customerBatchActions').dataset.mode = plan.mode;
            $('customerBatchActionTitle').textContent = titles[plan.mode];
            $('customerBatchActionEvidence').textContent = plan.evidence.length ? 'Dữ liệu cho thấy ' + plan.evidence.join('; ') + '. Doanh nghiệp có thể cân nhắc các ưu tiên dưới đây; đây là tín hiệu mô tả.' : 'Gợi ý dựa trên cơ cấu dự đoán; không có bằng chứng rating để đánh giá trải nghiệm.';
            const retention = [
                ['offers', '🎁', 'Ưu đãi cá nhân hóa', 'Phân nhóm khách có nguy cơ cao và thử ưu đãi phù hợp thay vì giảm giá đại trà. Đo tỷ lệ mua lại và biên lợi nhuận.'],
                ['reactivation', '📩', 'Chiến dịch tái kích hoạt', 'Liên hệ khách đã lâu chưa mua bằng kênh được khách đồng ý. So sánh tỷ lệ phản hồi và mua lại với nhóm đối chứng.'],
                ['experience', '⭐', 'Cải thiện trải nghiệm sau mua', result.ratings.count ? 'Xem xét các đánh giá thấp để xác định vấn đề cần xử lý. Rating chỉ là thống kê mô tả, không ảnh hưởng xác suất model.' : 'Thu thập phản hồi trước khi xác định vấn đề trải nghiệm. Tệp không có bằng chứng đánh giá đủ để kết luận khách không hài lòng.'],
                ['loyalty', '🏅', 'Loyalty program', 'Cân nhắc tích điểm, hạng thành viên hoặc ưu đãi cho lần mua tiếp theo. Theo dõi tần suất mua và chi phí chương trình.'],
                ['products', '🎯', 'Gợi ý sản phẩm phù hợp', 'Dựa vào lịch sử mã sản phẩm để thử nhắc mua lại hoặc cross-sell phù hợp. Kiểm tra hiệu quả qua thử nghiệm doanh nghiệp.'],
                ['barriers', '🚚', 'Giảm rào cản mua hàng', 'Kiểm tra phí vận chuyển, giao hàng, thanh toán, hoàn tiền và hỗ trợ sau bán. Tệp giao dịch không tự chứng minh nguyên nhân rời bỏ.'],
            ];
            const growth = [
                ['loyalty', '🏅', 'Duy trì loyalty', 'Ghi nhận lần mua tiếp theo bằng quyền lợi hợp lý, theo dõi biên lợi nhuận và tần suất mua.'],
                ['vip', '💎', 'VIP rewards', 'Thử quyền lợi cho nhóm khách phù hợp với giá trị mua và nguồn lực doanh nghiệp; không mặc định xác suất cao là lợi nhuận cao.'],
                ['products', '🎯', 'Cross-sell cá nhân hóa', 'Gợi ý sản phẩm liên quan từ lịch sử mua, kiểm tra tỷ lệ chuyển đổi với nhóm đối chứng.'],
                ['referral', '↗', 'Referral / giới thiệu', 'Cân nhắc chương trình giới thiệu tự nguyện, đo khách mới và chi phí thưởng.'],
                ['feedback', '💬', 'Thu thập feedback', 'Lắng nghe phản hồi có sự đồng ý để hiểu trải nghiệm; không dùng phản hồi như feature của model hiện tại.'],
                ['experience', '⭐', 'Duy trì trải nghiệm tốt', 'Giữ chất lượng sản phẩm, giao hàng và hỗ trợ nhất quán; kiểm chứng bằng chỉ số vận hành và phản hồi thực tế.'],
            ];
            const advice = plan.mode === 'growth' ? growth : plan.mode === 'empty' ? [] : retention;
            if (plan.priority) advice.sort((a, b) => Number(b[0] === plan.priority) - Number(a[0] === plan.priority));
            $('customerBatchAdvice').replaceChildren(...advice.map(([key, emoji, title, text]) => { const card = node('article', undefined, 'cr-advice-card'); card.dataset.action = key; const icon = node('span', emoji, 'cr-advice-icon'); icon.setAttribute('aria-hidden', 'true'); card.append(icon, node('h4', title), node('p', text)); return card; }));
        }

        function renderTable() {
            if (!result) return;
            const search = $('customerBatchSearch').value.trim().toLowerCase(), band = $('customerBatchBandFilter').value, classification = $('customerBatchClassFilter').value;
            const rows = result.records.filter(r => r.customer_id.toLowerCase().includes(search) && (!band || r.band === band) && (!classification || (classification === 'missing' ? r.probability === null : r.classification !== null && String(r.classification) === classification)));
            rows.sort((a, b) => a.probability === null ? b.probability === null ? 0 : 1 : b.probability === null ? -1 : ($('customerBatchSort').value === 'desc' ? -1 : 1) * (a.probability - b.probability));
            const pages = Math.max(1, Math.ceil(rows.length / 25)); page = Math.min(page, pages - 1);
            $('customerBatchRows').replaceChildren(...rows.slice(page * 25, (page + 1) * 25).map(r => { const tr = node('tr'); const values = [r.customer_id, r.features?.orders_90d ?? '—', r.features?.monetary_90d.toFixed(2) ?? '—', r.lastPurchase ? r.lastPurchase.slice(0, 10) : '—', r.probability === null ? '—' : (r.probability * 100).toFixed(1) + '%', r.band ?? '—', r.reason || r.status, r.rating?.toFixed(2) ?? '—']; values.forEach(value => tr.append(node('td', value))); return tr; }));
            if (!rows.length) { const tr = node('tr'), td = node('td', 'Không có khách khớp bộ lọc.'); td.colSpan = 8; tr.append(td); $('customerBatchRows').append(tr); }
            $('customerBatchPage').textContent = `${rows.length} khách · Trang ${page + 1}/${pages} · 25 khách mỗi trang`;
            $('customerBatchPrev').disabled = page === 0; $('customerBatchNext').disabled = page === pages - 1;
        }
        for (const id of ['customerBatchSearch', 'customerBatchBandFilter', 'customerBatchClassFilter', 'customerBatchSort']) $(id).addEventListener('input', () => { page = 0; renderTable(); });
        $('customerBatchPrev').addEventListener('click', () => { page--; renderTable(); });
        $('customerBatchNext').addEventListener('click', () => { page++; renderTable(); });

        async function download(csv, filename) {
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
            const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
            const mobile = ios || navigator.userAgentData?.mobile || /Android|Mobile/.test(navigator.userAgent);
            if (mobile && navigator.share && navigator.canShare && typeof File === 'function') {
                const file = new File([blob], filename, { type: blob.type });
                if (navigator.canShare({ files: [file] })) {
                    try { await navigator.share({ files: [file], title: filename }); return; }
                    catch (error) { if (error.name === 'AbortError') return; }
                }
            }
            const url = URL.createObjectURL(blob), link = node('a'); link.href = url; link.download = filename;
            if (ios || !('download' in link)) { link.target = '_blank'; link.rel = 'noopener'; }
            document.body.append(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(url), mobile ? 60000 : 5000);
            $('customerBatchDownloadNotice').textContent = ios ? 'Nếu CSV mở ở tab mới, dùng Chia sẻ → Lưu vào Tệp.' : 'Đã tạo CSV kết quả trên thiết bị.';
        }
        function bindDownload(button, content, filename) {
            let touch = null, lastTouch = 0;
            const run = () => { const csv = content(); if (csv) download(csv, filename).catch(() => message('Không thể tải tệp; thử lại bằng trình duyệt hỗ trợ tải CSV.')); };
            // iOS Google browsers require the share/download in the original tap.
            if (/CriOS|GSA\//.test(navigator.userAgent) && (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1))) {
                button.addEventListener('touchstart', e => { touch = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY, time: Date.now() } : null; }, { passive: true });
                button.addEventListener('touchend', e => { const t = e.changedTouches[0]; if (!touch || !t || Date.now() - touch.time > 700 || Math.hypot(t.clientX - touch.x, t.clientY - touch.y) > 10) return; e.preventDefault(); touch = null; lastTouch = Date.now(); run(); }, { passive: false });
            }
            button.addEventListener('click', e => { if (e.detail && Date.now() - lastTouch < 800) return; run(); });
        }
        bindDownload($('customerTemplateDownload'), sampleCSV, 'customer-transactions-template.csv');
        bindDownload($('customerBatchExport'), () => result ? exportCSV(result) : '', 'customer-return-results.csv');
        globalThis.CustomerReturnBatchPage = Object.freeze({ loadFile, getResult: () => result, selectTab });
    }
})();
