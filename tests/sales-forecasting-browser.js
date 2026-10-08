(async()=>{
  const checks=[],errors=[], $=id=>document.getElementById(id);
  const assert=(value,label)=>{if(!value)throw new Error(label);checks.push(label);};
  window.addEventListener('error',event=>errors.push(event.message));
  window.addEventListener('unhandledrejection',event=>errors.push(String(event.reason)));
  const originalConsole=console.error;console.error=(...args)=>{errors.push(args.join(' '));originalConsole.apply(console,args);};
  const wait=async predicate=>{const start=Date.now();while(!predicate()){if(Date.now()-start>70000)throw new Error('Timed out waiting for result');await new Promise(r=>setTimeout(r,50));}};
  const change=(id,value)=>{$(id).value=String(value);$(id).dispatchEvent(new Event('change',{bubbles:true}));};
  const overflow=()=>assert(document.documentElement.scrollWidth<=innerWidth,'no page overflow at '+innerWidth);
  const upload=async p=>{await SalesForecast.upload(new File([p.csv],'sales.csv',{type:'text/csv'}));assert($('error').hidden,'upload succeeded');};
  const run=async()=>{$('run').click();$('run').click();assert(SalesForecast.state.busy&&$('run').disabled,'duplicate request guard');await wait(()=>!SalesForecast.state.busy);assert($('error').hidden&&!!SalesForecast.state.result,'forecast succeeded');};
  const download=async id=>{
    let blob,filename;const oldURL=URL.createObjectURL,oldClick=HTMLAnchorElement.prototype.click;
    URL.createObjectURL=value=>{blob=value;return oldURL.call(URL,value);};
    HTMLAnchorElement.prototype.click=function(){filename=this.download;};
    try{$(id).click();assert(blob instanceof Blob,'download blob');return{text:await blob.text(),bytes:new Uint8Array(await blob.arrayBuffer()),filename};}
    finally{URL.createObjectURL=oldURL;HTMLAnchorElement.prototype.click=oldClick;}
  };
  overflow();assert($('results').hidden,'results initially hidden');
  $('sample').click();await wait(()=>!SalesForecast.state.busy);
  assert($('error').hidden&&SalesForecast.state.summary.rows===1096,'sample inspected');
  assert(SalesForecast.state.result===null,'no automatic model training');
  assert($('dateColumn').value==='date'&&$('targetColumn').value==='sales','auto suggestions editable');
  $('analyze').click();await wait(()=>!SalesForecast.state.busy);
  assert(!$('analysisPanel').hidden&&SalesForecast.state.result===null,'analysis before modeling');
  assert(!!$('historyChart').querySelector('svg'),'history SVG');
  await run();let result=SalesForecast.state.result;
  assert(result.models.filter(m=>m.status==='SUCCESS').length>=4,'real model comparison');
  assert(!$('results').hidden&&$('leaderboard').textContent.includes('BEST MODEL'),'winner leaderboard');
  assert(!result.evaluation.holdout_used_for_ranking,'holdout separated');
  for(const id of ['historyChart','comparisonChart','validationChart','forecastChart','residualChart','distributionChart'])assert(!!$(id).querySelector('svg'),id+' rendered');
  assert(result.forecast.every(r=>r.lower_95<=r.lower_80&&r.lower_80<=r.forecast&&r.forecast<=r.upper_80&&r.upper_80<=r.upper_95),'interval ordering');
  if(result.feature_importance.length)assert(!$('importancePanel').hidden&&!!$('importanceChart').querySelector('svg'),'importance rendered');
  const chart=$('forecastChart');chart.dispatchEvent(new PointerEvent('pointermove',{clientX:chart.getBoundingClientRect().left+120,clientY:chart.getBoundingClientRect().top+80}));
  assert(!chart.querySelector('.tooltip').hidden,'hover tooltip');
  chart.dispatchEvent(new PointerEvent('pointerleave'));
  const csv=await download('downloadCSV');assert(csv.filename==='sales_forecast.csv'&&csv.bytes[0]===239&&csv.bytes[1]===187&&csv.bytes[2]===191,'CSV UTF-8 BOM');
  assert(csv.text.includes('\r\n')&&csv.text.includes('lower_95'),'CSV CRLF intervals');
  const report=JSON.parse((await download('downloadJSON')).text);assert(report.best_model===result.best_model&&!('csv' in report),'JSON real report without upload');
  assert(SalesForecast.safeCSVCell('=SUM(1,1)').includes("'="),'formula injection guarded');
  $('leaderboard').querySelector('[data-model="Naive Forecast"]').click();assert($('detailModel').value==='Naive Forecast','click model detail');
  overflow();
  if(innerWidth===390){
    for(const name of ['daily','monthly','decimal']){
      await upload(__sfFixtures[name]);change('dateColumn','date');change('targetColumn','sales');
      change('groupColumn','store');await wait(()=>!SalesForecast.state.busy);assert(!$('groupField').hidden&&$('groupValue').value==='North','group chooser');
      change('frequency',name==='monthly'?'monthly':'daily');$('horizon').value='6';await run();
      assert(SalesForecast.state.result.forecast.length===6,name+' horizon');overflow();
    }
    const excel=__sfFixtures.excel;
    const bytes=Uint8Array.from(atob(excel.xlsx),c=>c.charCodeAt(0));await SalesForecast.upload(new File([bytes],'sales.xlsx'));
    assert(!$('sheetField').hidden,'multi-sheet chooser');change('sheet','Monthly');await wait(()=>!SalesForecast.state.busy);
    assert(SalesForecast.state.summary.metadata.sheet==='Monthly','selected sheet inspected');$('horizon').value='6';await run();
    assert(SalesForecast.state.result.frequency.frequency==='monthly','XLSX monthly forecasting');
    await upload(__sfFixtures.tiny);await run();assert(SalesForecast.state.result.evaluation.mode==='exploratory_no_validation','tiny explanatory result');
    assert($('intervalNote').textContent.includes('chưa thể'),'tiny interval honest');
    await upload(__sfFixtures.long);$('horizon').value='12';await run();assert(SalesForecast.state.result.refit_observations===12000,'long full history');
    assert($('historyChart').querySelectorAll('path').length<15,'bounded chart DOM');
    const oldFetch=window.fetch;window.fetch=async()=>new Response(JSON.stringify({error:'CSV vượt giới hạn 2 MiB.'}),{status:413,headers:{'Content-Type':'application/json'}});
    await SalesForecast.inspectSource({csv:'date,sales\n2023-01-01,1'});assert(!$('error').hidden&&$('error').textContent.includes('2 MiB'),'friendly backend error');window.fetch=oldFetch;
    await SalesForecast.upload(new File(['abc'],'bad.txt'));assert($('error').textContent.includes('CSV hoặc XLSX'),'extension validation');
    $('sample').click();await wait(()=>!SalesForecast.state.busy);await run();result=SalesForecast.state.result;
  }
  $('horizon').value='91';$('run').click();assert(!$('error').hidden&&!SalesForecast.state.busy,'invalid horizon inline');
  $('horizon').value='30';$('error').hidden=true;
  SalesForecast.state.result=result;SalesForecast.renderAnalysis(result);SalesForecast.renderResults(result);
  overflow();assert(errors.length===0,'no console or promise errors');
  return{ok:true,width:innerWidth,checks:checks.length,consoleErrors:errors};
})()
