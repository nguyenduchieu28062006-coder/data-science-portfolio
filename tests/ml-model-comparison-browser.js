(async () => {
  const checks=[],errors=[], $=id=>document.getElementById(id);
  window.__mlTestErrors=errors;
  addEventListener('error',e=>errors.push(e.message));addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
  const assert=(value,message)=>{if(!value)throw Error(message);checks.push(message);};
  const wait=async predicate=>{const started=performance.now();while(!predicate()){if(performance.now()-started>65000)throw Error('UI timeout: '+$('error').textContent);await new Promise(r=>setTimeout(r,50));}};
  const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}));};
  const upload=async csv=>{const dt=new DataTransfer();dt.items.add(new File([csv],'benchmark.csv',{type:'text/csv'}));$('csvFile').files=dt.files;$('csvFile').dispatchEvent(new Event('change',{bubbles:true}));await wait(()=>!MLComparison.state.busy);assert($('error').hidden,'upload no error');};
  const noOverflow=()=>assert(document.documentElement.scrollWidth<=innerWidth,'no global horizontal overflow '+innerWidth);
  const download = async (id,name) => {
    let blob,filename;
    const create=URL.createObjectURL, revoke=URL.revokeObjectURL, click=HTMLAnchorElement.prototype.click;
    URL.createObjectURL=value=>{blob=value;return 'blob:qa';};URL.revokeObjectURL=()=>{};
    HTMLAnchorElement.prototype.click=function(){filename=this.download;};
    try {$(id).click();assert(filename===name,'download filename '+name);return await blob.text();}
    finally {URL.createObjectURL=create;URL.revokeObjectURL=revoke;HTMLAnchorElement.prototype.click=click;}
  };
  await wait(()=>$('backendStatus').classList.contains('available'));
  assert($('customTab').getAttribute('aria-selected')==='true'&&!$('customSource').hidden,'custom CSV primary mode');noOverflow();
  await upload(__mlFixtures.classification.csv);
  assert(!$('qualityPanel').hidden&&$('preview').tBodies[0].rows.length===12,'CSV preview bounded');
  assert($('qualityCards').children.length===6,'data quality cards');
  assert($('target').value==='','target never auto selected');
  change('target','customer_id');assert(!$('toConfig').disabled&&$('targetInfo').textContent.includes('ID/ngày'),'ID target allowed with explicit warning');
  change('target','target');await wait(()=>$('toConfig').disabled===false);await new Promise(r=>setTimeout(r,150));
  assert($('targetInfo').textContent.includes('Classification'),'task detection');$('toConfig').click();
  assert(!$('configPanel').hidden,'wizard configuration');
  assert(!document.querySelector('input[name=task]:checked'),'explicit task confirmation required');
  assert(![...document.querySelectorAll('#features input')].some(c=>c.value==='target'),'target absent from features');
  const idFeature=[...document.querySelectorAll('#features input')].find(c=>c.value==='customer_id');assert(!idFeature.checked&&idFeature.parentElement.textContent.includes('định danh'),'ID warning and excluded by default');
  $('selectAll').click();assert(idFeature.checked,'ID override allowed');$('selectSafe').click();assert(!idFeature.checked,'feature selection safe reset');
  assert(!$('temporalWarning').hidden,'temporal warning visible on random split');
  change('split','temporal');assert(!$('timeLabel').hidden&&$('timeColumn').value==='event_date','temporal controls');change('split','random');assert($('timeLabel').hidden,'random split controls');
  $('run').click();assert(!$('error').hidden,'task confirmation blocks run');
  document.querySelector('input[name=task][value=regression]').click();assert(document.querySelector('input[name=task]:checked').value==='regression','task manual override');
  document.querySelector('input[name=task][value=classification]').click();$('run').click();assert(!$('loading').hidden&&$('run').disabled,'honest loading state');
  await wait(()=>!MLComparison.state.busy);assert($('error').hidden,'classification benchmark no error: '+$('error').textContent);
  assert(!$('results').hidden&&MLComparison.state.result.models.length===7,'classification results');
  assert($('leaderboard').tBodies[0].rows.length===7,'leaderboard');assert(MLComparison.state.result.selection_source==='train_cv','recommendation from CV');
  for(const id of ['comparisonChart','stabilityChart','gapChart','radarChart'])assert($(id).querySelector('svg'),'chart '+id);
  assert($('diagnosticChart').querySelector('table'),'multiclass-capable confusion heatmap');
  assert($('secondaryChart').querySelector('svg')&&$('prChart').querySelector('svg'),'binary ROC and PR');
  assert($('classReportTable').querySelector('table'),'classification report');
  change('detailModel','Random Forest');assert($('modelDetail').textContent.includes('RandomForestClassifier')&&$('importanceChart').querySelector('svg'),'model detail and importance');
  change('modelA','Random Forest');assert($('versus').textContent.includes('Random Forest'),'model vs model');noOverflow();
  const radar=[...document.querySelectorAll('#radarChoices input')];radar[3].click();assert(!radar[3].checked,'radar max three');
  change('split','temporal');assert($('results').hidden&&MLComparison.state.result===null,'configuration change invalidates stale results');
  $('run').click();await wait(()=>!MLComparison.state.busy);assert($('error').hidden&&MLComparison.state.result.methodology.cv==='TimeSeriesSplit','real temporal benchmark');noOverflow();
  await upload(__mlFixtures.regression.csv);change('target','target');await new Promise(r=>setTimeout(r,200));assert($('targetInfo').textContent.includes('Regression'),'regression detection');$('toConfig').click();document.querySelector('input[name=task][value=regression]').click();$('run').click();await wait(()=>!MLComparison.state.busy);
  assert($('error').hidden,'regression benchmark no error: '+$('error').textContent);assert(MLComparison.state.result.models.length===8,'regression models');
  assert($('radarPanel').hidden&&$('prPanel').hidden,'regression-specific UI');
  assert($('diagnosticChart').querySelector('svg')&&$('secondaryChart').querySelector('svg'),'regression scatter and residual');
  assert($('secondaryTitle').textContent.includes('actual')&&$('errorAnalysis').textContent.includes('Mean residual'),'residual convention and error analysis');noOverflow();
  const jsonReport=JSON.parse(await download('download','ml-model-comparison-report.json'));
  assert(jsonReport.recommended===MLComparison.state.result.recommended&&!('csv' in jsonReport),'JSON report contains real result without raw file');
  const csvReport=await download('downloadCSV','ml-model-comparison-report.csv');
  assert(csvReport.includes('CV RMSE')&&csvReport.includes('Model Size (bytes)')&&csvReport.split('\r\n').length===10,'regression CSV report columns and rows');
  assert(MLComparison.reportCSV(MLComparison.state.result).charCodeAt(0)===0xFEFF,'Excel UTF-8 BOM');
  const dangerous=structuredClone(MLComparison.state.result);dangerous.models[0].name='\t=HYPERLINK("bad")';
  assert(MLComparison.reportCSV(dangerous).includes("'\t=HYPERLINK"),'CSV formula injection neutralized');
  assert(MLComparison.reportCSV({...dangerous,models:[{...dangerous.models[0],test:{...dangerous.models[0].test,r2:-.5}}]}).includes('"-0.5"'),'negative numeric CSV metric preserved');
  const excelBytes=Uint8Array.from(atob(__mlFixtures.excel.xlsx),c=>c.charCodeAt(0));
  await MLComparison.upload(new File([excelBytes],'dữ-liệu.xlsx'));assert($('error').hidden,'XLSX upload succeeds');
  assert(!$('sheetLabel').hidden&&$('sheet').options.length===2&&$('sheet').value==='Dữ liệu','multi-sheet selector default and names');noOverflow();
  change('target','target');await new Promise(r=>setTimeout(r,200));$('toConfig').click();document.querySelector('input[name=task][value=classification]').click();$('run').click();await wait(()=>!MLComparison.state.busy);
  assert($('error').hidden&&MLComparison.state.result.models.length===7,'XLSX classification training');
  const classificationCSV=await download('downloadCSV','ml-model-comparison-report.csv');
  assert(classificationCSV.includes('CV F1 Macro')&&classificationCSV.includes('ROC-AUC')&&classificationCSV.includes('Recommended'),'classification CSV columns');
  change('sheet','Hồi quy');await wait(()=>!MLComparison.state.busy);
  assert($('target').value===''&&$('results').hidden&&MLComparison.state.sheet==='Hồi quy','sheet change resets target and stale results');
  change('target','target');await new Promise(r=>setTimeout(r,200));assert($('targetInfo').textContent.includes('Regression'),'selected sheet target detection');$('toConfig').click();document.querySelector('input[name=task][value=regression]').click();$('run').click();await wait(()=>!MLComparison.state.busy);
  assert($('error').hidden&&MLComparison.state.result.models.length===8&&MLComparison.state.result.summary.audit.selected_sheet==='Hồi quy','XLSX regression keeps selected sheet');noOverflow();
  await upload(__mlFixtures.weak.csv);change('target','target');await new Promise(r=>setTimeout(r,200));$('toConfig').click();document.querySelector('input[name=task][value=regression]').click();
  assert(!$('smallDataWarning').hidden&&$('smallDataWarning').textContent.includes('biến động'),'small dataset warning before training');
  $('run').click();await wait(()=>!MLComparison.state.busy);
  assert($('error').hidden&&MLComparison.state.result.methodology.folds===3,'small dataset still uses three CV folds');
  assert(MLComparison.state.result.models[0].test.r2<0&&!$('modelQualityWarning').hidden&&$('modelQualityWarning').textContent.includes('Chất lượng mô hình thấp'),'negative R2 prominent warning from real backend');
  assert(MLComparison.state.result.selection_source==='train_cv','quality warning preserves train CV recommendation');noOverflow();
  const standardResult=MLComparison.state.result;
  for(const [name,payload] of [['tiny regression',__mlFixtures.tinyRegression],['tiny classification',__mlFixtures.tinyClassification],['semicolon CSV',__mlFixtures.semicolon],['exploratory',__mlFixtures.exploratory]]){
    await upload(payload.csv);change('target',payload.target);await new Promise(r=>setTimeout(r,250));$('toConfig').click();
    document.querySelector(`input[name=task][value=${payload.task}]`).click();
    if(!$('leakageAckLabel').hidden&&!$('leakageAck').checked)$('leakageAck').click();
    $('run').click();assert(!$('loading').hidden&&$('run').disabled,name+' button responds');await wait(()=>!MLComparison.state.busy);
    assert($('error').hidden&&MLComparison.state.result.models.length>0,name+' result rendered');
    assert($('evaluationCard').textContent.includes('Chế độ đánh giá'),name+' evaluation mode visible');
    if(name.startsWith('tiny')){
      assert(MLComparison.state.result.selection_source==='cv_only'&&MLComparison.state.result.models.every(r=>r.test===null),name+' no fake test score');
      assert($('evaluationMeta').textContent.includes('không có test set riêng'),name+' no holdout label');
      assert($('diagnosticChart').textContent.includes('Không có test'),name+' diagnostics absent honestly');
    }
    if(name==='semicolon CSV')assert(MLComparison.state.result.summary.audit.delimiter===';'&&$('cleaningSummary').textContent.includes('decimal comma'),'semicolon numeric locale recognized');
    if(name==='exploratory'){
      assert(MLComparison.state.result.recommended===null&&$('recommendation').textContent.includes('TRONG THỬ NGHIỆM NÀY'),'exploratory not strong recommendation');
      assert($('evaluationMeta').textContent.includes('không có đánh giá độc lập'),'exploratory independence label');
    }
    const exported=await download('downloadCSV','ml-model-comparison-report.csv');
    assert(exported.includes('Evaluation Mode')&&exported.includes('Selection Source'),name+' CSV evaluation metadata');
    const report=JSON.parse(await download('download','ml-model-comparison-report.json'));
    assert(report.evaluation.mode===MLComparison.state.result.evaluation.mode,name+' JSON evaluation metadata');
    change('detailModel',MLComparison.state.result.models.at(-1).name);change('modelA',MLComparison.state.result.models.at(-1).name);noOverflow();
  }
  MLComparison.state.result=standardResult;MLComparison.renderResults(standardResult);
  for(const [name,payload] of [['dirty',__mlFixtures.dirty],['large classification',__mlFixtures.largeClassification],['large regression',__mlFixtures.largeRegression]]){
    if(!payload)continue;
    await upload(payload.csv);change('target',payload.target);await new Promise(r=>setTimeout(r,350));$('toConfig').click();
    document.querySelector(`input[name=task][value=${payload.task}]`).click();
    $('run').click();$('run').click();assert(MLComparison.state.busy&&$('run').disabled,name+' duplicate guard');
    if(name.startsWith('large'))assert($('loading').textContent.includes('Dữ liệu lớn'),name+' loading explanation');
    await wait(()=>!MLComparison.state.busy);assert($('error').hidden&&MLComparison.state.result.models.length>0,name+' real result');
    assert(!MLComparison.state.result.methodology.selected_features.includes(payload.target),name+' target excluded');
    if(name.startsWith('large')){
      assert(MLComparison.state.result.skipped.length>0&&!$('skipped').hidden,name+' partial reasons');
      const csv=await download('downloadCSV','ml-model-comparison-report.csv');assert(csv.includes('SKIPPED_TIME_BUDGET')&&csv.includes('Skip Reason'),name+' partial CSV');
    }
    noOverflow();
  }
  await upload(__mlFixtures.gender.csv);change('target','gender');await new Promise(r=>setTimeout(r,350));$('toConfig').click();
  document.querySelector('input[name=task][value=classification]').click();
  const outcome=[...document.querySelectorAll('#features input')].find(c=>c.value==='outcome');outcome.checked=true;outcome.dispatchEvent(new Event('change',{bubbles:true}));
  assert(!$('leakage').hidden&&!$('excludeLeakage').hidden,'structured leakage choices visible');
  $('excludeLeakage').click();await wait(()=>!MLComparison.state.busy);assert($('error').hidden&&!MLComparison.state.result.methodology.selected_features.includes('outcome'),'exclude + continue no 422 loop');
  outcome.checked=true;outcome.dispatchEvent(new Event('change',{bubbles:true}));$('leakageAck').click();$('run').click();await wait(()=>!MLComparison.state.busy);
  assert($('error').hidden&&MLComparison.state.result.methodology.selected_features.includes('outcome'),'confirm + continue heuristic');
  change('target','date_of_outcome');await new Promise(r=>setTimeout(r,350));assert($('targetInfo').textContent.includes('số ngày giữa hai mốc'),'date target explanation');$('toConfig').click();
  document.querySelector('input[name=task][value=classification]').click();$('run').click();await wait(()=>!MLComparison.state.busy);assert(!$('error').hidden&&$('error').textContent.includes('ngày tháng'),'date validation specific');noOverflow();
  MLComparison.state.result=standardResult;MLComparison.renderResults(standardResult);
  // Save the real result only for responsive screenshot replay after error recovery.
  const result=MLComparison.state.result;
  const originalFetch=window.fetch;window.fetch=async()=>new Response(JSON.stringify({error:'CSV quá lớn'}),{status:413,headers:{'Content-Type':'application/json'}});
  await MLComparison.upload(new File(['a,b\n1,2'],'invalid.csv'));assert(!$('error').hidden&&$('error').textContent.includes('CSV quá lớn'),'413 friendly error');window.fetch=originalFetch;
  $('demoTab').click();assert(!$('demoSource').hidden,'dataset sample tab');
  document.querySelector('[data-demo=iris]').click();await wait(()=>!MLComparison.state.busy);assert(MLComparison.state.summary.rows===150&&$('target').value==='','demo real inspect and manual target');
  MLComparison.state.result=result;MLComparison.renderResults(result);noOverflow();
  assert(errors.length===0,'no console or promise errors');
  return {ok:true,width:innerWidth,checks:checks.length,consoleErrors:errors};
})()
