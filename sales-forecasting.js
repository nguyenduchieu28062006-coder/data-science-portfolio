'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {source: null, summary: null, analysis: null, result: null, busy: false, horizonTouched: false};
  const nf = new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 2});
  const fmt = value => value == null || !Number.isFinite(value) ? 'N/A' : nf.format(value);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const units = {hourly:'giờ',daily:'ngày',weekly:'tuần',monthly:'tháng',quarterly:'quý'};
  const defaults = {hourly:24,daily:30,weekly:12,monthly:6,quarterly:4};
  const statuses = {SUCCESS:'Thành công',SKIPPED:'Bỏ qua',FAILED_SAFE:'Không hoàn tất',SKIPPED_TIME_BUDGET:'Hết ngân sách thời gian',SKIPPED_INSUFFICIENT_HISTORY:'Thiếu lịch sử'};
  const charts = new Map();
  const dateLabel = value => String(value).slice(0,10);

  function setBusy(value, message = '') {
    state.busy = value;
    document.querySelectorAll('#uploader button,#uploader input,#configPanel button,#configPanel input,#configPanel select,#sheet').forEach(el => {el.disabled = value;});
    $('loading').hidden = !value;
    $('loading').textContent = message;
    $('uploader').setAttribute('aria-busy', String(value));
    $('configPanel').setAttribute('aria-busy', String(value));
  }
  function showError(error) {
    $('error').textContent = error instanceof Error ? error.message : String(error);
    $('error').hidden = false;
    $('error').scrollIntoView({behavior:'smooth',block:'center'});
  }
  async function api(payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch('/api/sales-forecast', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
      const data = await response.json().catch(() => {throw new Error('Dịch vụ chưa trả JSON. Hãy chạy backend hoặc thử lại trên Preview.');});
      if (!response.ok || data.error) throw new Error(data.error || `Dịch vụ trả mã ${response.status}.`);
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Yêu cầu quá thời gian. Hãy giảm dữ liệu hoặc số kỳ dự báo.');
      if (error instanceof TypeError) throw new Error('Không kết nối được backend. Kiểm tra kết nối rồi thử lại.');
      throw error;
    } finally {clearTimeout(timer);}
  }
  function invalidate(includeAnalysis = true) {
    state.result = null;
    $('results').hidden = true;
    if (includeAnalysis) {state.analysis = null; $('analysisPanel').hidden = true;}
    $('error').hidden = true;
  }
  function options(id, names, selected, blank) {
    $(id).replaceChildren();
    if (blank) $(id).add(new Option(blank, ''));
    names.forEach(name => $(id).add(new Option(name, name)));
    if (selected && names.includes(selected)) $(id).value = selected;
  }
  function table(headers, rows) {
    return `<table><thead><tr>${headers.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function metric(label, value, note = '', cls = '') {
    return `<div class="metric"><span>${esc(label)}</span><strong class="${cls}">${esc(value)}</strong>${note ? `<small>${esc(note)}</small>` : ''}</div>`;
  }
  function payload(action) {
    const data = {...state.source,action,date_column:$('dateColumn').value,target_column:$('targetColumn').value,
      date_order:$('dateOrder').value,numeric_format:$('numericFormat').value,frequency:$('frequency').value,
      horizon:Number($('horizon').value),clamp_nonnegative:$('clamp').checked};
    if ($('groupColumn').value) Object.assign(data,{group_column:$('groupColumn').value,group_value:$('groupValue').value});
    return data;
  }
  function renderPreview(data) {
    state.summary = data;
    const names = data.columns.map(c => c.name);
    $('fileSummary').textContent = `${data.metadata.filename} · ${fmt(data.rows)} dòng sau làm sạch cấu trúc · ${names.length} cột${data.metadata.sheet ? ` · Sheet: ${data.metadata.sheet}` : ''}`;
    $('preview').innerHTML = table(data.columns.map(c => `${esc(c.name)}<small>${esc(c.type)}</small>`),data.preview.map(row => row.map(v => esc(v))));
    $('sheetField').hidden = data.metadata.sheets.length < 2;
    options('sheet',data.metadata.sheets,data.metadata.sheet);
    options('dateColumn',names,data.suggested_date,'Chọn thời gian');
    options('targetColumn',names,data.suggested_target,'Chọn doanh số');
    options('groupColumn',names,'','Không sử dụng');
    $('groupField').hidden = true;
    $('groupValue').replaceChildren();
    $('dateOrder').value = 'auto'; $('numericFormat').value = 'auto'; $('frequency').value = 'auto';
    $('horizon').value = '30'; state.horizonTouched = false;
    $('previewPanel').hidden = false; $('configPanel').hidden = false;
  }
  async function inspectSource(source) {
    if (state.busy) return;
    invalidate();
    state.source = null; state.summary = null;
    $('previewPanel').hidden = true; $('configPanel').hidden = true;
    setBusy(true,'Đang đọc dữ liệu, kiểm tra cấu trúc và gợi ý cột…');
    try {
      const summary = await api({...source,action:'inspect'});
      state.source = {...source,...(summary.metadata.sheet ? {sheet:summary.metadata.sheet} : {})};
      renderPreview(summary);
    } catch (error) {showError(error);}
    finally {setBusy(false);}
  }
  async function upload(file) {
    if (!file || state.busy) return;
    try {
      if (!/\.(csv|xlsx)$/i.test(file.name)) throw new Error('Chỉ hỗ trợ tệp CSV hoặc XLSX.');
      if (file.size > 2*1024*1024) throw new Error('Tệp vượt giới hạn 2 MiB.');
      // Read under the same guard, then let inspectSource own the HTTP request.
      setBusy(true,'Đang đọc tệp…');
      const bytes = new Uint8Array(await file.arrayBuffer());
      let source;
      if (/\.xlsx$/i.test(file.name)) {
        let binary = '';
        for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
        source = {xlsx:btoa(binary),filename:file.name};
      } else {
        source = {csv:new TextDecoder('utf-8',{fatal:true}).decode(bytes),filename:file.name};
      }
      setBusy(false);
      await inspectSource(source);
    } catch (error) {setBusy(false);showError(error instanceof TypeError ? new Error('CSV cần mã hóa UTF-8 hoặc UTF-8 BOM.') : error);}
    finally {$('file').value = '';}
  }
  async function updateGroups() {
    invalidate();
    const group = $('groupColumn').value;
    $('groupField').hidden = !group;
    if (!group || !state.source || state.busy) return;
    setBusy(true,'Đang đọc danh sách nhóm…');
    try {
      const response = await api({...state.source,action:'groups',group_column:group});
      options('groupValue',response.values);
    } catch (error) {showError(error);$('groupColumn').value='';$('groupField').hidden=true;}
    finally {setBusy(false);}
  }
  function horizonNote(frequency) {
    $('horizonNote').textContent = `Mỗi bước tương ứng một ${units[frequency] || 'kỳ'} sau tổng hợp.`;
  }
  async function run(action) {
    if (state.busy || !state.source) return;
    $('error').hidden = true;
    const request = payload(action);
    if (!request.date_column || !request.target_column || request.date_column === request.target_column) return showError('Chọn hai cột thời gian và doanh số khác nhau.');
    if (!Number.isInteger(request.horizon) || request.horizon < 1 || request.horizon > 90) return showError('Số kỳ tương lai phải là số nguyên từ 1 đến 90.');
    invalidate(action === 'analyze');
    setBusy(true, action === 'analyze' ? 'Đang chuẩn hóa chuỗi, tổng hợp doanh số và phân tích chất lượng…' : 'Đang chuẩn hóa chuỗi và backtest các mô hình theo thời gian. Sau đó đánh giá holdout, huấn luyện lại và tạo dự báo tương lai…');
    try {
      const result = await api(request);
      state.analysis = result;
      renderAnalysis(result);
      if (action === 'forecast') {state.result=result;renderResults(result);}
      else if (!state.horizonTouched) $('horizon').value=String(defaults[result.frequency.frequency]);
      horizonNote(result.frequency.frequency);
      $(action === 'forecast' ? 'results' : 'analysisPanel').scrollIntoView({behavior:'smooth',block:'start'});
    } catch (error) {showError(error);}
    finally {setBusy(false);}
  }

  function renderAnalysis(data) {
    $('analysisPanel').hidden=false;
    const q=data.quality;
    $('qualityStatus').textContent=q.status;
    $('qualityStatus').classList.toggle('warning-pill',q.status!=='Good');
    $('qualityMetrics').innerHTML=metric('Observations',fmt(q.observations),`${dateLabel(q.start)} → ${dateLabel(q.end)}`)+
      metric('Frequency',units[data.frequency.frequency],`Confidence: ${fmt(data.frequency.confidence*100)}% · interval ${data.frequency.interval}`)+
      metric('Missing periods',fmt(q.missing_periods),'Điền 0 sau tổng hợp SUM')+metric('Mean sales',fmt(q.mean),`Median ${fmt(q.median)} · Std ${fmt(q.std)}`)+
      metric('Min sales',fmt(q.min))+metric('Max sales',fmt(q.max))+metric('Duplicates removed',fmt(q.duplicates_removed),'Loại bản ghi trùng toàn bộ')+metric('Trend direction',q.trend.direction,`${fmt(q.trend.change_per_period)} / kỳ`);
    $('trendSummary').innerHTML=`<p><b>${esc(q.trend.direction)}</b> · ${fmt(q.trend.change_per_period)} mỗi kỳ · Thay đổi theo đường xu hướng: ${fmt(q.trend.overall_percent)}%.</p><p>Mùa vụ: <b>${esc(data.seasonality.status)}</b>. Đây là bằng chứng sơ bộ sau loại xu hướng.</p><p>${data.seasonality.correlations.map(c=>`Lag ${c.lag}: ${fmt(c.correlation)}`).join(' · ') || 'Chưa đủ độ dài để kiểm tra các chu kỳ phù hợp.'}</p>`;
    const c=data.cleaning;
    $('cleaning').innerHTML=[['dòng rỗng',c.empty_rows],['cột rỗng',c.empty_columns],['tiêu đề được chuẩn hóa',c.renamed_headers],['dòng trùng toàn bộ',c.duplicates_removed],['dòng thiếu / sai ngày',c.missing_dates],['dòng thiếu / sai doanh số',c.missing_targets]].map(([label,n])=>`<p>${fmt(n)} ${label}</p>`).join('')+`<p>${fmt(q.aggregated_rows)} bản ghi được gộp về kỳ bằng SUM.</p>`;
    $('warnings').innerHTML=data.warnings.map(w=>`<p>${esc(w)}</p>`).join('');
    $('warnings').hidden=!data.warnings.length;
    $('historyCaption').textContent=`${fmt(q.observations)} kỳ · Giảm điểm chỉ khi vẽ, mô hình dùng toàn bộ chuỗi`;
    lineChart('historyChart',data.series.map(p=>p.date),[{name:'Sales',values:data.series.map(p=>p.sales),color:'#2563eb'}]);
  }
  function renderResults(data) {
    $('results').hidden=false;
    const best=data.models.find(m=>m.name===data.best_model);
    $('evaluationMode').textContent=data.evaluation.mode;
    $('winnerMetrics').innerHTML=metric('BEST MODEL',data.best_model,'Chọn trước khi đánh giá holdout','model-name')+
      metric('Backtest RMSE',fmt(best.backtest?.rmse),`Std ${fmt(best.backtest?.rmse_std)}`)+metric('Improvement vs Naive',`${fmt(best.improvement_vs_naive)}${best.improvement_vs_naive==null?'':'%'}`,'Ngưỡng đáng kể: 5%')+metric('Final holdout RMSE',fmt(best.holdout?.rmse),'Đánh giá riêng, không chọn model');
    $('rankingNote').textContent=`Ranking source: ${data.evaluation.ranking_source} · ${data.evaluation.folds.length} expanding-window fold(s) · Tie-break: MAE. Holdout cuối chuỗi không dùng xếp hạng.${data.partial?' Một số model bị bỏ qua an toàn.':''}`;
    $('leaderboard').innerHTML=`<table><thead><tr>${['Rank','Model','Backtest RMSE','RMSE Std','MAE','sMAPE','Holdout RMSE','vs Naive','Status'].map(s=>`<th scope="col">${s}</th>`).join('')}</tr></thead><tbody>${data.models.map(m=>`<tr class="${m.name===data.best_model?'best-row':''}"><td>${m.rank||'—'}</td><td><button class="model-link" data-model="${esc(m.name)}">${esc(m.name)}</button>${m.name===data.best_model?' <span class="pill">BEST MODEL</span>':''}</td><td>${fmt(m.backtest?.rmse)}</td><td>${fmt(m.backtest?.rmse_std)}</td><td>${fmt(m.backtest?.mae)}</td><td>${fmt(m.backtest?.smape)}</td><td>${fmt(m.holdout?.rmse)}</td><td>${fmt(m.improvement_vs_naive)}${m.improvement_vs_naive==null?'':'%'}</td><td><span class="pill ${m.status==='SUCCESS'?'':'warning-pill'}">${esc(statuses[m.status]||m.status)}</span></td></tr>`).join('')}</tbody></table>`;
    $('leaderboard').querySelectorAll('[data-model]').forEach(button=>button.addEventListener('click',()=>{$('detailModel').value=button.dataset.model;renderDetail();$('modelDetail').scrollIntoView({behavior:'smooth',block:'center'});}));
    barChart('comparisonChart',data.models.filter(m=>m.backtest).map(m=>({label:m.name,value:m.backtest.rmse})),true);
    options('detailModel',data.models.map(m=>m.name),data.best_model);renderDetail();
    const h=data.holdout;
    $('holdoutSummary').textContent=h.metrics ? `Train đến ${dateLabel(data.series[data.evaluation.holdout_start-1].date)}. Holdout bắt đầu ${dateLabel(h.dates[0])} · MAE ${fmt(h.metrics.mae)} · sMAPE ${fmt(h.metrics.smape)}% · MAPE ${fmt(h.metrics.mape)} · R² ${fmt(h.metrics.r2)}.` : 'Chưa có đánh giá holdout độc lập cho chuỗi này.';
    if (h.dates.length) {
      const prior=data.series.slice(Math.max(0,data.evaluation.holdout_start-20),data.evaluation.holdout_start);
      lineChart('validationChart',[...prior.map(p=>p.date),...h.dates],[{name:'Actual',values:[...prior.map(p=>p.sales),...h.actual],color:'#94a3b8'},{name:'Predicted',values:[...prior.map(()=>null),...h.predicted],color:'#2563eb'}],{divider:prior.length,label:'Train | Validation'});
    } else emptyChart('validationChart','Chuỗi quá ngắn để có holdout độc lập.');
    renderForecast(data);
    $('residualStats').innerHTML=metric('Mean residual',fmt(h.mean_residual),'Residual = actual − predicted')+metric('Holdout MAE',fmt(h.metrics?.mae))+metric('Holdout RMSE',fmt(h.metrics?.rmse))+metric('Bias',h.bias||'N/A',h.bias==='underforecast'?'Có xu hướng dự báo thấp':h.bias==='overforecast'?'Có xu hướng dự báo cao':'Chưa có bằng chứng lệch');
    if (h.residuals?.length) {
      lineChart('residualChart',h.dates,[{name:'Residual',values:h.residuals,color:'#06b6d4'}],{zero:true});
      const min=Math.min(...h.residuals),max=Math.max(...h.residuals),bins=Math.min(12,Math.max(3,Math.ceil(Math.sqrt(h.residuals.length)))),step=(max-min||1)/bins;
      const counts=Array(bins).fill(0);h.residuals.forEach(v=>counts[Math.min(bins-1,Math.floor((v-min)/step))]++);
      barChart('distributionChart',counts.map((value,i)=>({label:`${fmt(min+i*step)} → ${fmt(min+(i+1)*step)}`,value})));
    } else {emptyChart('residualChart','Không có residual holdout.');emptyChart('distributionChart','Không có phân phối residual độc lập.');}
    $('importancePanel').hidden=!data.feature_importance.length;
    if (data.feature_importance.length) {barChart('importanceChart',data.feature_importance.map(p=>({label:p.feature,value:p.value})));$('importanceMethod').textContent=data.importance_method;}
  }
  function renderDetail() {
    if (!state.result) return;
    const m=state.result.models.find(m=>m.name===$('detailModel').value);
    if (!m) return;
    $('modelDetail').innerHTML=`<p><b>${esc(m.name)}</b> · ${esc(statuses[m.status]||m.status)}</p><p>Backtest RMSE ${fmt(m.backtest?.rmse)} · MAE ${fmt(m.backtest?.mae)} · sMAPE ${fmt(m.backtest?.smape)}%</p><p>MAPE ${fmt(m.backtest?.mape)} · R² ${fmt(m.backtest?.r2)} · Fit ${fmt(m.fit_time_ms)} ms</p><p>Features: ${esc(m.features.join(', ')||'Không dùng features; baseline từ lịch sử.')}</p><p>Lags: ${esc(m.lags.join(', ')||'—')} · Rolling windows: ${esc(m.rolling_windows.join(', ')||'—')}</p><p>${esc(m.notes||'')}${m.holdout_note?' '+esc(m.holdout_note):''}</p>`;
  }
  function renderForecast(data) {
    const i=data.insights,rows=data.forecast;
    $('forecastCaption').textContent=`${rows.length} ${units[data.frequency.frequency]} tương lai · ${data.forecast_model} · Refit ${fmt(data.refit_observations)} quan sát`;
    $('insights').innerHTML=metric('Expected total sales',fmt(i.total),`${rows.length} kỳ tương lai`)+metric('Average forecast',fmt(i.average))+metric('vs previous equivalent period',`${fmt(i.change_percent)}${i.change_percent==null?'':'%'}`,'So với tổng cùng số kỳ gần nhất')+metric('Forecast reliability',i.reliability,'Heuristic · Không phải xác suất');
    const history=data.series.slice(-Math.max(40,rows.length*2));
    const labels=[...history.map(p=>p.date),...rows.map(p=>p.date)];
    lineChart('forecastChart',labels,[{name:'History',values:[...history.map(p=>p.sales),...rows.map(()=>null)],color:'#94a3b8'},{name:'Forecast',values:[...history.slice(0,-1).map(()=>null),history.at(-1).sales,...rows.map(p=>p.forecast)],color:'#2563eb'}],{divider:history.length,label:'Forecast begins',bands:rows[0].lower_95==null?null:{start:history.length,rows}});
    $('intervalNote').textContent=rows[0].lower_95==null ? 'Không có residual validation độc lập: khoảng dự báo chưa thể ước lượng.' : `Estimated forecast interval · ${data.intervals.residual_count} residual backtest · Các khoảng mở rộng khi vượt ${data.intervals.validated_steps} bước đã kiểm chứng; không bảo đảm coverage 80% / 95%.`;
    $('businessInsights').innerHTML=`<p>Xu hướng lịch sử: <b>${esc(data.quality.trend.direction)}</b>. Tổng doanh số dự kiến ${fmt(i.total)} trong ${rows.length} ${esc(units[data.frequency.frequency])} tiếp theo.</p>${i.change_percent==null?'':`<p>So với ${rows.length} kỳ gần nhất, tổng dự báo ${i.change_percent>=0?'tăng':'giảm'} khoảng <b>${fmt(Math.abs(i.change_percent))}%</b>.</p>`}<p>Kỳ cao nhất: ${dateLabel(i.max_period.date)} (${fmt(i.max_period.forecast)}). Kỳ thấp nhất: ${dateLabel(i.min_period.date)} (${fmt(i.min_period.forecast)}).</p><p>Reliability <b>${esc(i.reliability)}</b> · RMSE / quy mô target ${fmt(i.relative_backtest_rmse==null?null:i.relative_backtest_rmse*100)}% · Backtest std / RMSE ${fmt(i.stability_ratio)}. Khoảng ước lượng phản ánh sai số trong quá khứ; các cú sốc mới có thể nằm ngoài khoảng này.</p>`;
    $('forecastTable').innerHTML=table(['Date','Forecast','Lower 80','Upper 80','Lower 95','Upper 95'],rows.map(r=>[dateLabel(r.date),fmt(r.forecast),fmt(r.lower_80),fmt(r.upper_80),fmt(r.lower_95),fmt(r.upper_95)]));
  }

  // SVG paths keep rendering bounded without adding a chart dependency.
  // All original points remain in state and in backend fitting/exports.
  function sampledIndices(values, limit=700) {
    if (values.length<=limit) return values.map((_,i)=>i);
    const selected=new Set([0,values.length-1]),size=Math.ceil(values.length/(limit/2));
    for (let start=0;start<values.length;start+=size) {
      let min=start,max=start;
      for (let j=start;j<Math.min(start+size,values.length);j++) {if(values[j]<values[min])min=j;if(values[j]>values[max])max=j;}
      selected.add(min);selected.add(max);
    }
    return [...selected].sort((a,b)=>a-b);
  }
  function emptyChart(id,message) {charts.delete(id);$(id).innerHTML=`<div class="chart-empty">${esc(message)}</div>`;}
  function lineChart(id,labels,series,config={}) {
    charts.set(id,{type:'line',labels,series,config});
    drawLine(id,labels,series,config);
  }
  function drawLine(id,labels,series,config) {
    const host=$(id),W=Math.max(260,host.clientWidth),H=host.clientHeight||270;
    const left=W<380?49:64,right=15,top=27,bottom=35,plotW=W-left-right,plotH=H-top-bottom;
    const finite=[];series.forEach(s=>s.values.forEach(v=>{if(v!=null&&Number.isFinite(v))finite.push(v);}));
    if(config.bands)config.bands.rows.forEach(r=>finite.push(r.lower_95,r.upper_95));
    if(!finite.length){emptyChart(id,'Chưa có dữ liệu để vẽ.');return;}
    let min=finite.reduce((a,b)=>Math.min(a,b),Infinity),max=finite.reduce((a,b)=>Math.max(a,b),-Infinity);
    if(config.zero){min=Math.min(0,min);max=Math.max(0,max);}
    const pad=(max-min||Math.max(1,Math.abs(max)*.1))*.12;min-=pad;max+=pad;
    const x=i=>left+i/Math.max(1,labels.length-1)*plotW,y=v=>top+(max-v)/(max-min)*plotH;
    let markup=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(host.getAttribute('aria-label')||id)}"><title>${esc(series.map(s=>s.name).join(' / '))}</title>`;
    for(let i=0;i<=4;i++){const value=min+(max-min)*i/4,py=y(value);markup+=`<path d="M${left} ${py}H${W-right}" stroke="#eef2f7"/><text x="${left-8}" y="${py+3}" text-anchor="end">${esc(nf.format(Math.round(value*100)/100).length>9?new Intl.NumberFormat('vi-VN',{notation:'compact',maximumFractionDigits:1}).format(value):fmt(value))}</text>`;}
    if(config.zero)markup+=`<path d="M${left} ${y(0)}H${W-right}" stroke="#94a3b8" stroke-dasharray="4 4"/>`;
    if(config.bands){const {start,rows}=config.bands;for(const [level,opacity]of[[95,.08],[80,.18]]){const path=rows.map((r,i)=>`${i?'L':'M'}${x(start+i)} ${y(r[`upper_${level}`])}`).join(' ')+rows.map((_,i)=>{const j=rows.length-i-1;return`L${x(start+j)} ${y(rows[j][`lower_${level}`])}`;}).join(' ')+'Z';markup+=`<path d="${path}" fill="#2563eb" fill-opacity="${opacity}"/>`;}}
    for(const s of series){let connected=false,path='';for(const index of sampledIndices(s.values)){const v=s.values[index];if(v==null){connected=false;continue;}path+=`${connected?'L':'M'}${x(index).toFixed(2)} ${y(v).toFixed(2)} `;connected=true;}markup+=`<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.3" stroke-linejoin="round"/>`;}
    if(config.divider!=null){const px=x(config.divider);markup+=`<path d="M${px} ${top}V${H-bottom}" stroke="#94a3b8" stroke-dasharray="4 5"/><text x="${Math.min(W-right,Math.max(left,px))}" y="15" text-anchor="${px>W*.65?'end':'start'}">${esc(config.label||'')}</text>`;}
    const tickCount=W<400?3:5;
    for(let i=0;i<tickCount;i++){const index=Math.round(i/(tickCount-1)*(labels.length-1));markup+=`<text x="${x(index)}" y="${H-10}" text-anchor="${i===0?'start':i===tickCount-1?'end':'middle'}">${esc(dateLabel(labels[index]))}</text>`;}
    markup+='</svg><div class="tooltip" hidden></div>';host.innerHTML=markup;
    const tooltip=host.querySelector('.tooltip');
    host.onpointermove=event=>{const box=host.getBoundingClientRect(),index=Math.max(0,Math.min(labels.length-1,Math.round((event.clientX-box.left-left)/plotW*(labels.length-1))));let text=dateLabel(labels[index]);series.forEach(s=>{if(s.values[index]!=null)text+=`\n${s.name}: ${fmt(s.values[index])}`;});if(config.bands&&index>=config.bands.start){const r=config.bands.rows[index-config.bands.start];if(r)text+=`\n80%: ${fmt(r.lower_80)} → ${fmt(r.upper_80)}\n95%: ${fmt(r.lower_95)} → ${fmt(r.upper_95)}`;}tooltip.textContent=text;tooltip.hidden=false;tooltip.style.left=`${Math.max(0,Math.min(W-220,event.clientX-box.left+12))}px`;tooltip.style.top=`${Math.max(0,event.clientY-box.top-65)}px`;};
    host.onpointerleave=()=>{tooltip.hidden=true;};
  }
  function barChart(id,rows,ascending=false) {charts.set(id,{type:'bar',rows,ascending});drawBars(id,rows,ascending);}
  function drawBars(id,rows,ascending) {
    if(!rows.length){emptyChart(id,'Chưa có kết quả validation để so sánh.');return;}
    const host=$(id),W=Math.max(260,host.clientWidth),H=host.clientHeight||270,left=W<380?112:150,right=58,top=10;
    const max=rows.reduce((m,r)=>Math.max(m,r.value),0)||1,step=(H-20)/rows.length;
    host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img"><title>${esc(id)}</title>${rows.map((r,i)=>{const width=Math.max(1,r.value/max*(W-left-right)),py=top+i*step;return`<text x="${left-9}" y="${py+step*.55}" text-anchor="end">${esc(r.label.length>(W<380?18:25)?r.label.slice(0,W<380?16:23)+'…':r.label)}</text><rect x="${left}" y="${py+step*.15}" width="${width}" height="${Math.min(22,step*.6)}" rx="3" fill="${ascending&&i===0?'#06b6d4':'#2563eb'}" fill-opacity="${ascending&&i===0?'1':'.65'}"><title>${esc(r.label)}: ${fmt(r.value)}</title></rect><text x="${left+width+6}" y="${py+step*.55}">${esc(fmt(r.value))}</text>`;}).join('')}</svg>`;
    host.onpointermove=null;host.onpointerleave=null;
  }
  function safeCSVCell(value) {
    const string=String(value??'');
    // Generated finite numbers can remain numeric, including legitimate returns.
    const safe=typeof value==='number'&&Number.isFinite(value)?string:/^[\s]*[=+\-@\t\r]/.test(string)?`'${string}`:string;
    return `"${safe.replace(/"/g,'""')}"`;
  }
  function forecastCSV(data) {
    const headers=['date','forecast','lower_80','upper_80','lower_95','upper_95'];
    return '\ufeff'+[headers.map(safeCSVCell).join(','),...data.forecast.map(r=>headers.map(k=>safeCSVCell(r[k])).join(','))].join('\r\n')+'\r\n';
  }
  function download(contents,name,type) {
    const url=URL.createObjectURL(new Blob([contents],{type})),link=document.createElement('a');
    link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  $('file').addEventListener('change',()=>upload($('file').files[0]));
  $('sample').addEventListener('click',()=>inspectSource({sample:true}));
  $('sheet').addEventListener('change',()=>{if(state.source)inspectSource({...state.source,sheet:$('sheet').value});});
  $('groupColumn').addEventListener('change',updateGroups);
  for(const id of ['dateColumn','targetColumn','groupValue','dateOrder','numericFormat'])$(id).addEventListener('change',()=>invalidate());
  $('frequency').addEventListener('change',()=>{invalidate();const frequency=$('frequency').value;if(defaults[frequency]){$('horizon').value=String(defaults[frequency]);state.horizonTouched=false;}horizonNote(frequency);});
  $('horizon').addEventListener('input',()=>{state.horizonTouched=true;invalidate(false);});
  $('clamp').addEventListener('change',()=>invalidate(false));
  $('analyze').addEventListener('click',()=>run('analyze'));
  $('run').addEventListener('click',()=>run('forecast'));
  $('detailModel').addEventListener('change',renderDetail);
  $('downloadCSV').addEventListener('click',()=>{if(state.result)download(forecastCSV(state.result),'sales_forecast.csv','text/csv;charset=utf-8');});
  $('downloadJSON').addEventListener('click',()=>{if(state.result)download(JSON.stringify(state.result,null,2),'sales_forecast_report.json','application/json');});
  const zone=$('dropZone');
  ['dragenter','dragover'].forEach(name=>zone.addEventListener(name,event=>{event.preventDefault();if(!state.busy)zone.classList.add('drag');}));
  ['dragleave','drop'].forEach(name=>zone.addEventListener(name,event=>{event.preventDefault();zone.classList.remove('drag');}));
  zone.addEventListener('drop',event=>{if(!state.busy)upload(event.dataTransfer.files[0]);});
  let resizeTimer;
  window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{for(const[id,data]of charts){if(!$(id).getClientRects().length)continue;if(data.type==='line')drawLine(id,data.labels,data.series,data.config);else drawBars(id,data.rows,data.ascending);}},100);});
  fetch('/api/sales-forecast').then(async r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>{$('backendStatus').textContent=data.available?'Backend sẵn sàng':'Backend chưa sẵn sàng';}).catch(()=>{$('backendStatus').textContent='Backend chưa kết nối';$('backendStatus').classList.add('warning-pill');});
  window.SalesForecast={state,upload,inspectSource,run,renderAnalysis,renderResults,forecastCSV,safeCSVCell,sampledIndices};
})();
