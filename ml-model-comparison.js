'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors = ['#118DFF', '#01B8AA', '#FD625E', '#8B5CF6', '#F2C80F', '#10B981'];
  const state = {csv: null, xlsx: null, sheet: null, fileName: '', demo: null, summary: null, result: null, busy: false, revision: 0, leakage: []};
  const fmt = (value, percent = false) => value == null || !Number.isFinite(value) ? 'N/A' : percent ? (value * 100).toFixed(1) + '%' : Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 3});
  const metric = (value, key) => fmt(value, ['f1','accuracy','precision','recall','f1_weighted','roc_auc','pr_auc','mape'].includes(key));
  const axisFmt = (value, percent=false) => !percent && (Math.abs(value)>=1e6 || Math.abs(value)>0&&Math.abs(value)<.001) ? value.toExponential(1) : fmt(value,percent);
  const options = names => names.map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join('');
  const checkedTask = () => document.querySelector('input[name="task"]:checked')?.value;
  const selectedFeatures = () => [...document.querySelectorAll('#features input:checked')].map(x => x.value);
  const source = () => state.demo ? {demo: state.demo} : state.xlsx ? {xlsx: state.xlsx, sheet: state.sheet} : {csv: state.csv};
  const progress = step => document.querySelectorAll('.steps li').forEach((li, i) => {li.classList.toggle('active', i <= step); if (i === step) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');});
  function error(message) { $('error').textContent = message; $('error').hidden = !message; }
  function busy(value, message = '') {
    state.busy = value; $('loading').hidden = !value; $('loading').textContent = message;
    document.querySelectorAll('#sourcePanel button, #sourcePanel input, #sourcePanel select, #configPanel input, #configPanel select, #configPanel button, #qualityPanel select, #qualityPanel button, .tabs button').forEach(el => el.disabled = value);
    if (!value) $('toConfig').disabled = !$('target').value;
    $('dropZone').setAttribute('aria-disabled', String(value));
  }
  function invalidate() {state.result = null; $('results').hidden = true; error(''); progress($('configPanel').hidden ? 1 : 2);}
  async function api(payload, timeout = 62000) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeout);
    try {
      const body = JSON.stringify(payload);
      if (new TextEncoder().encode(body).length > 4 * 1024 * 1024) throw Error('Request vượt 4 MiB sau mã hóa JSON. Hãy giảm kích thước CSV.');
      const response = await fetch('/api/ml-compare', {method:'POST', headers:{'Content-Type':'application/json'}, body, signal:controller.signal, cache:'no-store'});
      let data;
      try {data = await response.json();} catch {throw Error(response.status === 413 ? 'Tệp quá lớn cho dịch vụ phân tích.' : 'Dịch vụ Python chưa sẵn sàng. Hãy mở trang qua server hỗ trợ /api/ml-compare.');}
      if (!response.ok) throw Error(data.error || ({400:'CSV không hợp lệ.',413:'Tệp quá lớn.',422:'Kiểm tra target và features.',500:'Huấn luyện gặp lỗi.',504:'Huấn luyện quá thời gian.'}[response.status] || 'Dịch vụ tạm thời không khả dụng.'));
      return data;
    } catch (e) {if (e.name === 'AbortError') throw Error('Yêu cầu quá thời gian. Hãy giảm số dòng hoặc features.'); if (e instanceof TypeError) throw Error('Không kết nối được dịch vụ phân tích. Kiểm tra kết nối rồi thử lại.'); throw e;}
    finally {clearTimeout(timer);}
  }
  function table(headers, rows) {return `<thead><tr>${headers.map(h => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody>`;}
  function renderSummary(summary, name) {
    state.summary = summary; state.leakage = []; state.result = null;
    $('qualityPanel').hidden = false; $('configPanel').hidden = true; $('results').hidden = true;
    $('fileName').textContent = name; $('target').innerHTML = '<option value="">— Chọn cột mục tiêu —</option>' + options(summary.columns.map(c => c.name));
    $('targetInfo').textContent = 'Chọn target để xem gợi ý loại bài toán.';
    $('toConfig').disabled = true;
    $('sheetLabel').hidden = !state.xlsx || (summary.audit.sheets || []).length < 2;
    $('sheet').innerHTML = options(summary.audit.sheets || []);
    if (state.xlsx) $('sheet').value = summary.audit.selected_sheet;
    $('smallDataWarning').hidden = summary.rows >= 100;
    $('smallDataWarning').classList.toggle('warning-strong', summary.rows < 50);
    $('smallDataWarning').textContent = summary.rows < 50 ? 'Dữ liệu rất nhỏ (dưới 50 dòng). CV và Test có thể biến động rất mạnh; kết quả chỉ mang tính thăm dò.' : 'Dữ liệu khá nhỏ. Kết quả Cross Validation và Test có thể biến động mạnh.';
    const cards = [['Dòng dùng được',summary.rows],['Cột',summary.columns.length],['Missing',fmt(summary.missing / (summary.rows * summary.columns.length),true)],['Dòng trùng',summary.audit.duplicates_removed],['Numeric',summary.numeric],['Categorical',summary.categorical]];
    $('qualityCards').innerHTML = cards.map(([label,value]) => `<div class="kpi"><b>${esc(value)}</b><span>${label}</span></div>`).join('');
    $('cleaningSummary').textContent = `Đã loại ${summary.audit.duplicates_removed} dòng trùng và ${summary.audit.blank_rows} dòng trắng. ${summary.audit.short_rows_padded} dòng thiếu ô được giữ với missing. ${summary.audit.headers_normalized ? 'Header đã được cắt khoảng trắng/đổi tên trùng.' : ''} Missing được impute trong train, không bịa target.`;
    $('preview').innerHTML = table(summary.columns.map(c => c.name), summary.preview.map(row => row.map(v => v ?? '—')));
    const warnings = summary.columns.filter(c => c.id_like || c.date || c.high_cardinality || c.malformed_numeric).map(c => `${c.name}: ${[c.id_like && 'có vẻ là mã định danh, có thể gây overfitting', c.date && 'ngày ISO tiềm năng', c.high_cardinality && 'nhiều category; đề xuất loại hoặc gộp nhóm hiếm', c.malformed_numeric && `${c.malformed_numeric} ô không phải số, sẽ được coi là missing nếu chọn numeric`].filter(Boolean).join('; ')}`);
    warnings.push('Target candidates: ' + summary.columns.filter(c => c.target_candidate).map(c => c.name).join(', '));
    $('columnWarnings').textContent = warnings.join(' · '); $('columnWarnings').hidden = false;
    document.querySelectorAll('input[name=task]').forEach(r => r.checked = false);
    progress(1);
  }
  async function upload(file) {
    if (!file || state.busy) return;
    error(''); busy(true,'Đang đọc tệp và kiểm tra chất lượng dữ liệu…');
    try {
      if (!/\.(csv|xlsx)$/i.test(file.name)) throw Error('Hãy chọn tệp .csv hoặc .xlsx.');
      if (file.size > 2 * 1024 * 1024) throw Error('Tệp vượt giới hạn 2 MiB.');
      const bytes = new Uint8Array(await file.arrayBuffer());
      let input;
      if (/\.xlsx$/i.test(file.name)) {
        let binary = ''; for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
        input = {xlsx: btoa(binary)};
      } else input = {csv: new TextDecoder('utf-8',{fatal:true}).decode(bytes)};
      const summary = await api({action:'inspect',...input});
      state.csv = input.csv ?? null; state.xlsx = input.xlsx ?? null; state.sheet = summary.audit.selected_sheet ?? null;
      state.fileName = file.name; state.demo = null; state.revision++;
      renderSummary(summary,file.name);
    } catch(e) {error(e instanceof TypeError ? 'CSV phải được mã hóa UTF-8.' : e.message);}
    finally {busy(false);}
  }
  $('sheet').onchange = async () => {
    if (state.busy || !state.xlsx) return;
    const selected = $('sheet').value;
    invalidate(); $('qualityPanel').hidden = true; $('configPanel').hidden = true;
    busy(true,'Đang đọc sheet đã chọn…'); state.revision++;
    try {
      const summary = await api({action:'inspect',xlsx:state.xlsx,sheet:selected});
      state.sheet = selected; renderSummary(summary,state.fileName);
    } catch(e) {error(e.message); $('sheet').value = state.sheet;}
    finally {busy(false);}
  };
  function setMode(demo) {
    if (state.busy) return;
    $('customTab').setAttribute('aria-selected',String(!demo)); $('demoTab').setAttribute('aria-selected',String(demo));
    $('customTab').tabIndex = demo ? -1 : 0; $('demoTab').tabIndex = demo ? 0 : -1;
    $('customSource').hidden = demo; $('demoSource').hidden = !demo;
  }
  $('customTab').onclick = () => setMode(false); $('demoTab').onclick = () => setMode(true);
  document.querySelector('.tabs').addEventListener('keydown', e => {if (['ArrowRight','ArrowLeft','Home','End'].includes(e.key)) {e.preventDefault(); const demo = e.key === 'End' || e.key !== 'Home' && $('customTab').getAttribute('aria-selected') === 'true'; setMode(demo); $(demo?'demoTab':'customTab').focus();}});
  $('csvFile').onchange = e => upload(e.target.files[0]);
  $('dropZone').addEventListener('dragover',e => {e.preventDefault(); if (!state.busy) $('dropZone').classList.add('dragging');});
  $('dropZone').addEventListener('dragleave',() => $('dropZone').classList.remove('dragging'));
  $('dropZone').addEventListener('drop',e => {e.preventDefault(); $('dropZone').classList.remove('dragging'); upload(e.dataTransfer.files[0]);});
  document.querySelectorAll('[data-demo]').forEach(button => button.onclick = async () => {
    if (state.busy) return;
    busy(true,'Đang chuẩn bị dataset mẫu…'); error('');
    try {const demo = button.dataset.demo, summary = await api({action:'inspect',demo}); state.demo = demo; state.csv = null; state.xlsx = null; state.sheet = null; state.revision++; renderSummary(summary,button.textContent.trim());}
    catch(e){error(e.message);} finally{busy(false);}
  });
  $('target').onchange = async () => {
    invalidate(); state.revision++; const revision = state.revision;
    $('configPanel').hidden = true; $('toConfig').disabled = true; $('leakageAck').checked = false;
    document.querySelectorAll('input[name=task]').forEach(r => r.checked = false);
    const info = state.summary?.columns.find(c => c.name === $('target').value);
    if (!info) {$('targetInfo').textContent = 'Chọn target để xem gợi ý loại bài toán.'; return;}
    $('targetInfo').textContent = `Kiểu: ${info.kind} · ${info.unique} unique (${fmt(info.unique_ratio,true)}) · ${info.missing} missing. Loại bài toán được gợi ý: ${info.suggested_task === 'classification' ? 'Classification' : 'Regression'}. Bạn cần xác nhận hoặc đổi bên dưới.`;
    if (info.unique < 2 || info.id_like || info.date) {error('Target chỉ có một giá trị, toàn thiếu hoặc giống ID/ngày. Hãy chọn cột khác.'); return;}
    renderFeatures(); $('toConfig').disabled = false;
    try {const summary = await api({...source(),action:'inspect',target:info.name},15000); if (revision !== state.revision) return; state.leakage = summary.leakage || []; renderLeakage();}
    catch(e) {if (revision === state.revision) error(e.message);}
  };
  function renderFeatures() {
    const columns = state.summary.columns.filter(c => c.name !== $('target').value);
    $('features').innerHTML = columns.map(c => `<label><input type="checkbox" value="${esc(c.name)}" ${!c.id_like && !c.high_cardinality ? 'checked' : ''}> ${esc(c.name)}<small>${[c.kind,c.id_like && '⚠ mã định danh',c.date && 'ngày',c.high_cardinality && '⚠ nhiều category'].filter(Boolean).join(' · ')}</small></label>`).join('');
    const dates = columns.filter(c => c.date).map(c => c.name);
    $('timeColumn').innerHTML = options(dates); $('dateLabel').hidden = !dates.length; $('temporalWarning').hidden = !dates.length;
    $('split').value = 'random'; $('dateFeatures').value = 'drop'; $('timeLabel').hidden = true;
    $('features').onchange = () => {invalidate(); $('leakageAck').checked = false; renderLeakage();};
  }
  function renderLeakage() {
    const features = selectedFeatures();
    const warnings = state.leakage.filter(message => features.some(f => message.startsWith(f + ':')));
    $('leakage').textContent = 'Potential leakage warning · ' + warnings.join(' · '); $('leakage').hidden = !warnings.length; $('leakageAckLabel').hidden = !warnings.length;
  }
  $('toConfig').onclick = () => {$('configPanel').hidden = false; progress(2); $('configPanel').scrollIntoView({behavior:'smooth',block:'start'});};
  $('selectAll').onclick = () => {document.querySelectorAll('#features input').forEach(c => c.checked = true); invalidate(); renderLeakage();};
  $('selectSafe').onclick = () => {document.querySelectorAll('#features input').forEach(c => {const info = state.summary.columns.find(x => x.name === c.value); c.checked = !info.id_like && !info.high_cardinality;}); invalidate(); renderLeakage();};
  document.querySelectorAll('input[name=task]').forEach(r => r.onchange = invalidate);
  ['dateFeatures','timeColumn','leakageAck'].forEach(id => $(id).onchange = invalidate);
  $('split').onchange = () => {$('timeLabel').hidden = $('split').value !== 'temporal'; invalidate();};
  $('run').onclick = async () => {
    if (state.busy) return;
    const task = checkedTask(), features = selectedFeatures();
    if (!task) return error('Hãy xác nhận Classification hoặc Regression.');
    if (!features.length) return error('Hãy chọn ít nhất một feature.');
    if (!$('leakageAckLabel').hidden && !$('leakageAck').checked) return error('Hãy kiểm tra Potential leakage warning và xác nhận nguồn features.');
    if ($('split').value === 'temporal' && !$('timeColumn').value) return error('Temporal split cần cột ngày ISO.');
    invalidate(); progress(3); busy(true,'Đang huấn luyện và đánh giá các mô hình: CV trên train, sau đó đánh giá test…');
    try {
      const result = await api({...source(),action:'benchmark',target:$('target').value,task,features,split:$('split').value,time_column:$('timeColumn').value,date_features:$('dateFeatures').value,ack_leakage:$('leakageAck').checked});
      state.result = result; renderResults(result); progress(4); $('results').scrollIntoView({behavior:'smooth',block:'start'});
    } catch(e) {error(e.message); progress(2);} finally {busy(false);}
  };

  function svg(title, content, width = 600, height = 310) {return `<svg role="img" aria-label="${esc(title)}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">${content}</svg>`;}
  function empty(id,message) {$(id).innerHTML = `<p class="no-chart">${esc(message)}</p>`;}
  function short(name) {return name.replace('Regression','Reg.').replace('Regressor','Reg.').replace('Support Vector Machine','SVM').replace('K-Nearest Neighbors','KNN').replace('Gaussian Naive Bayes','Gaussian NB');}
  function bars(id, labels, series, title, percent = false, std = null) {
    const width=Math.max(260,Math.min(600,$(id).clientWidth||600)),mobile=width<400;
    const left=mobile?112:156,right=15,top=mobile&&series.length>2?52:35,row=48,height=top+labels.length*row+38;
    const vals=series.flatMap(s => s.values).filter(v=>v!=null && Number.isFinite(v));
    let low=Math.min(0,...vals), high=Math.max(percent?1:0,...vals);
    if(std) high=Math.max(high,...series[0].values.map((v,i)=>v+std[i]));
    if(high===low) high=low+1;
    const x=v=>left+(v-low)/(high-low)*(width-left-right), zero=x(0);
    let content='';
    const ticks=mobile?2:4;
    for(let tick=0;tick<=ticks;tick++){const value=low+(high-low)*tick/ticks,at=x(value);content+=`<line x1="${at}" y1="${top-8}" x2="${at}" y2="${height-30}" stroke="#e5ebf2"/><text x="${at}" y="${height-9}" text-anchor="${tick===ticks?'end':tick===0?'start':'middle'}">${esc(axisFmt(value,percent))}</text>`;}
    series.forEach((s,k)=>{const xx=mobile?8+(k%2)*120:Math.max(8,width-series.length*105)+k*105,yy=mobile?5+Math.floor(k/2)*16:5;content+=`<rect x="${xx}" y="${yy}" width="8" height="8" fill="${colors[k]}"/><text class="legend" x="${xx+12}" y="${yy+8}">${esc(s.name)}</text>`;});
    labels.forEach((label,i)=>{
      const y=top+i*row,barHeight=Math.min(12,32/series.length);
      const display=short(label),limit=mobile?18:26;
      content+=`<text x="${left-10}" y="${y+18}" text-anchor="end">${esc(display.length>limit?display.slice(0,limit-1)+'…':display)}<title>${esc(label)}</title></text>`;
      series.forEach((s,k)=>{const v=s.values[i];if(v==null)return;const at=x(v),yy=y+k*(barHeight+2);content+=`<rect x="${Math.min(zero,at)}" y="${yy}" width="${Math.max(1,Math.abs(at-zero))}" height="${barHeight}" rx="2" fill="${colors[k]}"><title>${esc(label)} · ${esc(s.name)}: ${esc(fmt(v,percent))}</title></rect>`;});
      if(std){const v=series[0].values[i],a=x(Math.max(low,v-std[i])),b=x(v+std[i]);content+=`<line x1="${a}" y1="${y+6}" x2="${b}" y2="${y+6}" stroke="#14283f" stroke-width="2"/><text x="${left}" y="${y+35}" class="legend">${esc(fmt(v,percent))} ± ${esc(fmt(std[i],percent))}</text>`;}
    });
    $(id).innerHTML=svg(title,content,width,height);
  }
  function linePlot(id, points, title, xLabel, yLabel, reference = null, scatter = false) {
    if (!points?.length) return empty(id,'Không có dữ liệu khả dụng.');
    const width=Math.max(260,Math.min(600,$(id).clientWidth||600)),height=width<400?280:315,left=55,top=20,bottom=55,right=20;
    let xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
    if(reference==='diagonal'){xmin=ymin=Math.min(xmin,ymin);xmax=ymax=Math.max(xmax,ymax);}
    if(reference==='zero'){ymin=Math.min(0,ymin);ymax=Math.max(0,ymax);}
    if(reference==='unit'||reference==='probability'){xmin=ymin=0;xmax=ymax=1;}
    if(xmin===xmax)xmax=xmin+1;if(ymin===ymax)ymax=ymin+1;
    const x=v=>left+(v-xmin)/(xmax-xmin)*(width-left-right),y=v=>height-bottom-(v-ymin)/(ymax-ymin)*(height-bottom-top);
    let content='';
    const ticks=width<400?2:4;
    for(let i=0;i<=ticks;i++){const xx=xmin+(xmax-xmin)*i/ticks,yy=ymin+(ymax-ymin)*i/ticks;content+=`<line x1="${left}" y1="${y(yy)}" x2="${width-right}" y2="${y(yy)}" stroke="#e5ebf2"/><text x="${left-8}" y="${y(yy)+4}" text-anchor="end">${esc(axisFmt(yy))}</text><text x="${x(xx)}" y="${height-bottom+20}" text-anchor="${i===ticks?'end':i===0?'start':'middle'}">${esc(axisFmt(xx))}</text>`;}
    if(reference==='zero')content+=`<line x1="${left}" y1="${y(0)}" x2="${width-right}" y2="${y(0)}" stroke="#FD625E" stroke-dasharray="5 5"/>`;
    if(reference==='diagonal'||reference==='unit')content+=`<line x1="${x(xmin)}" y1="${y(xmin)}" x2="${x(xmax)}" y2="${y(xmax)}" stroke="#9aa8b9" stroke-dasharray="5 5"/>`;
    content+=scatter?points.map(p=>`<circle cx="${x(p[0])}" cy="${y(p[1])}" r="3" fill="#118DFF" opacity=".65"><title>${esc(fmt(p[0]))}, ${esc(fmt(p[1]))}</title></circle>`).join(''):`<polyline points="${points.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}" fill="none" stroke="#01B8AA" stroke-width="2.5"/>`;
    content+=`<text x="${width/2}" y="${height-6}" text-anchor="middle">${esc(xLabel)}</text><text x="15" y="145" transform="rotate(-90 15 145)" text-anchor="middle">${esc(yLabel)}</text>`;
    $(id).innerHTML=svg(title,content,width,height);
  }
  function renderResults(result) {
    $('results').hidden=false;
    const classification=result.task==='classification',best=result.models[0],key=classification?'f1':'rmse';
    const quality = result.quality;
    $('modelQualityWarning').hidden = !quality || quality.level === 'normal';
    $('modelQualityWarning').classList.toggle('warning-strong', quality?.level === 'low');
    $('modelQualityWarning').textContent = quality && quality.level !== 'normal' ? (quality.level === 'low' ? 'Chất lượng mô hình thấp. ' : 'Khả năng dự đoán còn hạn chế. ') + quality.message : '';
    $('recommendation').innerHTML=`<div><p class="eyebrow">MÔ HÌNH ĐƯỢC ĐỀ XUẤT CHO BỘ DỮ LIỆU NÀY</p><h2>${esc(result.recommended)}</h2><p>Đạt ${classification?'CV F1 Macro cao nhất':'CV RMSE thấp nhất'} trong các model hoàn tất. Khi bằng điểm, ưu tiên CV std thấp, sau đó thời gian CV thấp. Kết quả từ cấu hình baseline, chưa tối ưu toàn diện.</p><p>Model được đề xuất dựa trên Cross Validation để tránh tối ưu theo test set.</p></div><div class="recommendation-metrics"><div><small>CV ${esc(result.primary_metric)}</small><strong>${fmt(best.cv_mean,classification)}</strong><small>± ${fmt(best.cv_std,classification)}</small></div><div><small>Final Test ${esc(result.primary_metric)}</small><strong>${fmt(best.test[key],classification)}</strong><small>Overfit risk · ${esc(best.overfit_risk)}</small></div></div>`;
    $('resultWarnings').textContent=result.warnings.join(' · ');$('resultWarnings').hidden=!result.warnings.length;
    const m=result.methodology;
    $('methodology').textContent=`${m.train_rows} train / ${m.test_rows} test · ${m.cv} ${m.folds} folds · ${m.split} split · Seed ${m.seed} · Preprocessing fit riêng trong mỗi fold. Tổng ${fmt(result.duration_ms/1000)} giây. CV std là độ lệch chuẩn giữa folds.`;
    const headers=classification?['Rank','Model','CV F1','CV Std','Test F1','Accuracy','Precision','Recall','ROC-AUC','Train F1','Fit ms','Predict ms','Overfit risk']:['Rank','Model','CV RMSE','CV Std','Test RMSE','MAE','R²','Train R²','Fit ms','Predict ms','Overfit risk'];
    $('leaderboard').innerHTML=`<thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${result.models.map(r=>{const values=classification?[fmt(r.cv_mean,true),fmt(r.cv_std,true),metric(r.test.f1,'f1'),metric(r.test.accuracy,'accuracy'),metric(r.test.precision,'precision'),metric(r.test.recall,'recall'),metric(r.test.roc_auc,'roc_auc'),metric(r.train.f1,'f1')]:[fmt(r.cv_mean),fmt(r.cv_std),fmt(r.test.rmse),fmt(r.test.mae),fmt(r.test.r2),fmt(r.train.r2)];return `<tr class="${r.name===result.recommended?'recommended':''}"><td>${r.rank}</td><td><button data-model="${esc(r.name)}">${esc(r.name)}</button></td>${[...values,fmt(r.fit_time_ms),fmt(r.predict_time_ms),r.overfit_risk].map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`;}).join('')}</tbody>`;
    $('leaderboard').onclick=e=>{const button=e.target.closest('[data-model]');if(button){$('detailModel').value=button.dataset.model;renderDetail();$('modelDetail').scrollIntoView({behavior:'smooth'});}};
    $('skipped').innerHTML=result.skipped.map(s=>`<p><strong>${esc(s.status)}: ${esc(s.name)}</strong> — ${esc(s.reason)}</p>`).join('');$('skipped').hidden=!result.skipped.length;
    const labels=result.models.map(r=>r.name);
    $('comparisonTitle').textContent=classification?'Accuracy / Precision / Recall / F1 · Test':'MAE / RMSE · Test (đơn vị target)';
    const keys=classification?['accuracy','precision','recall','f1']:['mae','rmse'];
    bars('comparisonChart',labels,keys.map(k=>({name:k.toUpperCase(),values:result.models.map(r=>r.test[k])})),'So sánh hiệu suất trên test',classification);
    bars('stabilityChart',labels,[{name:'CV '+result.primary_metric,values:result.models.map(r=>r.cv_mean)}],'CV mean và độ lệch chuẩn',classification,result.models.map(r=>r.cv_std));
    bars('gapChart',labels,[{name:classification?'Train F1':'Train R²',values:result.models.map(r=>r.train[classification?'f1':'r2'])},{name:classification?'Test F1':'Test R²',values:result.models.map(r=>r.test[classification?'f1':'r2'])}],'Train và Test',classification);
    $('radarPanel').hidden=!classification;
    $('radarChoices').innerHTML=result.models.map((r,i)=>`<label><input type="checkbox" value="${esc(r.name)}" ${i<3?'checked':''}> ${esc(short(r.name))}</label>`).join('');
    $('radarChoices').onchange=e=>{if(document.querySelectorAll('#radarChoices input:checked').length>3){e.target.checked=false;error('Radar chỉ cho phép tối đa 3 model.');}else{error('');renderRadar();}};
    if(classification)renderRadar();
    ['modelA','modelB','detailModel'].forEach(id=>$(id).innerHTML=options(labels));$('modelB').selectedIndex=Math.min(1,labels.length-1);
    renderVersus();renderDetail();
  }
  function renderRadar() {
    const chosen=[...document.querySelectorAll('#radarChoices input:checked')].map(c=>state.result.models.find(r=>r.name===c.value));
    if(!chosen.length)return empty('radarChart','Chọn từ 1 đến 3 model.');
    const keys=['accuracy','precision','recall','f1'];if(chosen.every(r=>r.test.roc_auc!=null))keys.push('roc_auc');
    const width=Math.max(260,Math.min(600,$('radarChart').clientWidth||600)),cx=width/2,cy=145,radius=Math.min(90,width*.27),angle=i=>-Math.PI/2+i*Math.PI*2/keys.length;
    const point=(i,v)=>[cx+Math.cos(angle(i))*radius*v,cy+Math.sin(angle(i))*radius*v];let content='';
    for(let k=1;k<=4;k++){content+=`<polygon points="${keys.map((_,i)=>point(i,k/4).join(',')).join(' ')}" fill="none" stroke="#dce4ee"/><text x="${cx+4}" y="${cy-radius*k/4+10}">${k/4}</text>`;}
    keys.forEach((key,i)=>{const p=point(i,1),label=point(i,1.2);content+=`<line x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}" stroke="#dce4ee"/><text x="${label[0]}" y="${label[1]}" text-anchor="middle">${key.replace('roc_auc','ROC-AUC').toUpperCase()}</text>`;});
    chosen.forEach((r,k)=>{content+=`<polygon points="${keys.map((key,i)=>point(i,r.test[key]).join(',')).join(' ')}" fill="${colors[k]}" fill-opacity=".10" stroke="${colors[k]}" stroke-width="2"/><text x="${cx}" y="${270+k*15}" text-anchor="middle" style="fill:${colors[k]}">${esc(r.name)}</text>`;});
    $('radarChart').innerHTML=svg('Radar metric test thang 0–1, không chuẩn hóa lại',content,width,320);
  }
  function renderVersus() {
    const a=state.result.models.find(r=>r.name===$('modelA').value),b=state.result.models.find(r=>r.name===$('modelB').value),cls=state.result.task==='classification';
    const rows=[['CV '+state.result.primary_metric,fmt(a.cv_mean,cls),fmt(b.cv_mean,cls)],['Final Test',fmt(a.test[cls?'f1':'rmse'],cls),fmt(b.test[cls?'f1':'rmse'],cls)],['CV std',fmt(a.cv_std,cls),fmt(b.cv_std,cls)],['Train / Test gap',fmt(a.generalization_gap),fmt(b.generalization_gap)],['Overfit heuristic',a.overfit_risk,b.overfit_risk],['Fit (ms)',fmt(a.fit_time_ms),fmt(b.fit_time_ms)],['Predict test (ms)',fmt(a.predict_time_ms),fmt(b.predict_time_ms)],['Model size (KiB)',fmt(a.model_size_bytes/1024),fmt(b.model_size_bytes/1024)]];
    $('versus').innerHTML='<table>'+table(['Metric',a.name,b.name],rows)+'</table>';
  }
  $('modelA').onchange=renderVersus;$('modelB').onchange=renderVersus;$('detailModel').onchange=renderDetail;
  function renderDetail() {
    const r=state.result.models.find(m=>m.name===$('detailModel').value),cls=state.result.task==='classification';
    const values=[['CV mean ± std',`${fmt(r.cv_mean,cls)} ± ${fmt(r.cv_std,cls)}`],['Fit time',fmt(r.fit_time_ms)+' ms'],['Predict test',fmt(r.predict_time_ms)+' ms'],['Model size',fmt(r.model_size_bytes/1024)+' KiB']];
    Object.entries(r.test).forEach(([key,value])=>values.push(['Test '+key,metric(value,key)]));
    Object.entries(r.train).forEach(([key,value])=>values.push(['Train '+key,metric(value,key)]));
    $('modelDetail').innerHTML=`<h3>${esc(r.name)} · ${esc(r.algorithm_type)}</h3><p class="muted">Numeric: ${esc(r.preprocessing.numeric)} · Categorical: ${esc(r.preprocessing.categorical)} · Overfit heuristic: ${esc(r.overfit_risk)}</p><div class="detail-metrics">${values.map(([name,value])=>`<div><small>${esc(name)}</small><b>${esc(value)}</b></div>`).join('')}</div><details><summary>Hyperparameters & CV từng fold</summary><p class="hyperparameters">${esc(JSON.stringify(r.hyperparameters))}</p><p class="muted">Fold scores: ${r.cv_scores.map(v=>fmt(v,cls)).join(' · ')}</p></details>`;
    if(cls){
      $('diagnosticTitle').textContent='Confusion matrix · Actual ↓ / Predicted →';
      const {labels,matrix}=r.confusion,max=Math.max(1,...matrix.flat());
      $('diagnosticChart').innerHTML=`<div class="table-scroll" tabindex="0"><table><thead><tr><th>Actual / Predicted</th>${labels.map(l=>`<th>${esc(l)}</th>`).join('')}</tr></thead><tbody>${matrix.map((row,i)=>`<tr><th scope="row">${esc(labels[i])}</th>${row.map(v=>`<td style="background:rgba(17,141,255,${.05+v/max*.65});color:#14283f">${v}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
      $('secondaryTitle').textContent='ROC curve';$('prPanel').hidden=false;
      if(r.curves){linePlot('secondaryChart',r.curves.roc,'ROC curve','False Positive Rate','True Positive Rate','unit');linePlot('prChart',r.curves.pr,'Precision Recall curve','Recall','Precision','probability');}
      else{empty('secondaryChart','ROC curve chỉ hiển thị cho binary với score khả dụng; multiclass AUC hợp lệ được ghi trong metric.');empty('prChart','PR curve không áp dụng cho cấu hình này.');}
      const confused=r.most_confused.map(c=>`${c.actual} → ${c.predicted}: ${c.count}`).join(' · ');
      $('errorAnalysis').textContent=`${r.curves?'Positive class: '+r.curves.positive_class+'. ':''}Các lớp dễ nhầm: ${confused||'không có lỗi trong test này.'}`;
      $('classReport').hidden=false;
      const rows=labels.map(l=>{const item=r.classification_report[l];return[l,fmt(item.precision,true),fmt(item.recall,true),fmt(item['f1-score'],true),item.support];});
      $('classReportTable').innerHTML='<table>'+table(['Class','Precision','Recall','F1','Support'],rows)+'</table>';
    }else{
      $('diagnosticTitle').textContent='Predicted vs Actual · reference y = x';$('secondaryTitle').textContent='Residual = actual − predicted · reference y = 0';
      linePlot('diagnosticChart',r.scatter,'Predicted vs Actual','Actual','Predicted','diagonal',true);linePlot('secondaryChart',r.residuals,'Residual plot','Predicted','Actual − Predicted','zero',true);
      $('prPanel').hidden=true;$('classReport').hidden=true;
      $('errorAnalysis').textContent=`Mean residual: ${fmt(r.error_analysis.mean_residual)} · Largest |residual|: ${fmt(r.error_analysis.largest_absolute_residual)}. Đồ thị hiển thị tối đa 250 mẫu test; metric tính trên toàn bộ test. MAPE chỉ có khi target không chứa giá trị bằng hoặc gần 0.`;
    }
    if(r.importance?.length)bars('importanceChart',r.importance.map(i=>i.feature),[{name:'Global weight',values:r.importance.map(i=>i.value)}],'Độ quan trọng đặc trưng toàn cục');else empty('importanceChart','Thuật toán này không có feature_importances_ hoặc hệ số tuyến tính phù hợp.');
  }
  $('download').onclick=()=>{
    if(!state.result)return;
    const blob=new Blob([JSON.stringify(state.result,null,2)],{type:'application/json;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ml-model-comparison-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  function reportCSV(result) {
    const classification = result.task === 'classification';
    const headers = classification ? ['Rank','Model','CV F1 Macro','CV Std','Test F1 Macro','Accuracy','Precision Macro','Recall Macro','ROC-AUC','Train F1','Fit Time (ms)','Predict Time (ms)','Model Size (bytes)','Overfit Risk','Recommended'] : ['Rank','Model','CV RMSE','CV Std','Test RMSE','MAE','R2','Train R2','Fit Time (ms)','Predict Time (ms)','Model Size (bytes)','Overfit Risk','Recommended'];
    const cell = value => {
      let text = value == null ? '' : String(value);
      if (typeof value === 'string' && /^[\s\uFEFF]*[=+\-@]/.test(text)) text = "'" + text;
      return '"' + text.replace(/"/g,'""') + '"';
    };
    const rows = result.models.map(r => [r.rank,r.name,r.cv_mean,r.cv_std,...(classification ? [r.test.f1,r.test.accuracy,r.test.precision,r.test.recall,r.test.roc_auc,r.train.f1] : [r.test.rmse,r.test.mae,r.test.r2,r.train.r2]),r.fit_time_ms,r.predict_time_ms,r.model_size_bytes,r.overfit_risk,r.name === result.recommended ? 'Yes' : 'No']);
    return '\uFEFF' + [headers,...rows].map(row=>row.map(cell).join(',')).join('\r\n') + '\r\n';
  }
  $('downloadCSV').onclick = () => {
    if (!state.result) return;
    const blob = new Blob([reportCSV(state.result)],{type:'text/csv;charset=utf-8'}), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = 'ml-model-comparison-report.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  let resizeTimer;
  addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{
    if(!state.result)return;
    const selections=['modelA','modelB','detailModel'].map(id=>[id,$(id).value]);
    const radar=[...document.querySelectorAll('#radarChoices input:checked')].map(c=>c.value);
    renderResults(state.result);
    selections.forEach(([id,value])=>$(id).value=value);renderVersus();renderDetail();
    document.querySelectorAll('#radarChoices input').forEach(c=>c.checked=radar.includes(c.value));
    if(state.result.task==='classification')renderRadar();
  },150);});
  fetch('/api/ml-compare',{cache:'no-store'}).then(async response=>{const data=await response.json();if(!response.ok||data.backend!=='scikit-learn')throw Error();$('backendStatus').textContent='● Python / scikit-learn sẵn sàng';$('backendStatus').classList.add('available');}).catch(()=>{$('backendStatus').textContent='Backend chưa kết nối';});
  window.MLComparison={state,upload,api,renderResults,reportCSV};
})();
