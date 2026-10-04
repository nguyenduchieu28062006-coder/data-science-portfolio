(async()=>{
 const report=document.getElementById('report'),frame=document.getElementById('frame'),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label);},tick=()=>new Promise(r=>setTimeout(r,80));
 let user=null,callback,rows=[],calls=[],failure=false,win,doc;
 window.__authControl={configured:true};
 window.__client={auth:{onAuthStateChange(fn){callback=fn;},async getSession(){return {data:{session:user?{user}:null}};},async getUser(){return {data:{user}};},async signOut(){user=null;callback('SIGNED_OUT',null);return {}; }},
 from(table){const query={table,filters:[],operation:'load'};const chain={select(columns){query.columns=columns;return chain;},insert(row){query.operation='insert';query.row=row;return chain;},delete(){query.operation='delete';return chain;},eq(k,v){query.filters.push([k,v]);return chain;},order(){return chain;},range(a,b){query.range=[a,b];return chain;},then(resolve,reject){calls.push(query);return new Promise(done=>setTimeout(()=>{
   if(failure){done({error:{status:500}});return;}
   if(query.operation==='insert'){rows.push({...query.row,table,id:String(rows.length+1),created_at:new Date().toISOString()});done({error:null});return;}
   const matching=rows.filter(row=>row.table===table&&query.filters.every(([k,v])=>row[k]===v));
   if(query.operation==='delete')rows=rows.filter(row=>!matching.includes(row));done({data:matching,error:null});
 },30)).then(resolve,reject);}};return chain;}};
 async function open(page){await new Promise(r=>{frame.onload=()=>{if(frame.contentWindow.location.pathname==='/'+page)r();};frame.src='/'+page;});win=frame.contentWindow;doc=frame.contentDocument;
  for(let attempt=0;attempt<100&&(!win.PortfolioAuth||(page==='vietnam-house-price.html'&&!win.HousePage));attempt++)await tick();
  assert(Boolean(win.PortfolioAuth),'auth initialized');await win.PortfolioAuth.ready;if(win.HousePage)await win.HousePage.ready;await tick();}
 const event=(element,type)=>element.dispatchEvent(new win.Event(type,{bubbles:true})),sample=(i=0)=>doc.querySelector('[data-house-sample="'+i+'"]').click(),predict=()=>doc.getElementById('houseForm').requestSubmit(),save=()=>doc.getElementById('houseSave').click();
 const section=()=>[...doc.querySelectorAll('.history-module')].find(s=>s.querySelector('h2')?.textContent.includes('bất động sản'));
 try{
  await open('vietnam-house-price.html');const api=win.VietnamHouse,model=win.HousePage.getModel(),index=model.location_data,stats=model.statistics_data;
  assert(model.schema_version===5&&!doc.getElementById('houseFields').disabled,'schema5 statistical BETA loads');
  assert(calls.length===0,'public estimate has no database reads');assert(model.metrics===null&&model.train_rows===0,'no ML training or fabricated metrics');
  assert(index.provinces.length===34&&index.wards.length===3321,'official canonical 34 provinces and 3321 wards');
  assert(doc.getElementById('houseProvince').options.length===35,'province selection includes all official locations');
  assert([...doc.getElementById('housePropertyType').options].filter(o=>!o.disabled).length===4,'4 separately verified types enabled, 2 gated');
  const fixtures=await (await fetch('/data/vietnam-house-parity-fixtures.json')).json();let maxAbsolute=0,fixtureKeys=true;
  for(const f of fixtures.fixtures){const got=api.predict(model,f.input);maxAbsolute=Math.max(maxAbsolute,Math.abs(got.total_price_vnd-f.expected_vnd));fixtureKeys&&=got.stat_key===f.stat_key;}
  assert(fixtures.fixtures.length===250&&fixtureKeys&&maxAbsolute<1,'Python JS 250 retained record estimates and keys agree');
  const base={province:'Hà Nội',property_type:'APARTMENT',area_m2:80},resolution=point=>api.resolve(stats,index,{...base,...point});
  const city=stats.stats.filter(r=>r.province===base.province&&r.property_type==='APARTMENT'&&r.resolution_level==='WARD'&&r.coverage!=='INSUFFICIENT').slice(0,3);
  assert(city.length===3&&new Set(city.map(r=>resolution({ward:r.ward}).stat_key)).size===3,'3 same city wards use 3 independent keys');
  const project=stats.stats.find(r=>r.province===base.province&&r.property_type==='APARTMENT'&&r.resolution_level==='SUB_AREA'&&r.coverage!=='INSUFFICIENT');
  assert(resolution({ward:city[0].ward}).resolution_level==='WARD','valid canonical ward with direct data');
  assert(resolution(project).resolution_level==='SUB_AREA','known project uses direct same type data');
  assert(resolution({ward:city[0].ward,sub_area:'Thôn Đồng'}).resolution_level==='WARD'&&resolution({ward:city[0].ward,sub_area:'Thôn Đồng'}).sub_area_input_kind==='TYPED','optional typed subarea safely falls back ward');
  const noWard=index.wards.find(w=>w.province===base.province&&!stats.stats.some(s=>s.ward===w.id&&s.property_type==='APARTMENT'&&s.resolution_level==='WARD'&&s.coverage!=='INSUFFICIENT'));
  assert(resolution({ward:noWard.id}).location_valid&&resolution({ward:noWard.id}).resolution_level==='PROVINCE','valid unpriced canonical ward falls back province');
  for(const p of [{ward:'abcxyz'},{province:'abcxyz'},{area:'unseen district'}])assert(!resolution(p).location_valid&&resolution(p).reason==='unknown_location','unknown administrative location rejected');
  const regional=stats.regional_stats.find(r=>r.property_type==='APARTMENT');
  assert(resolution({province:regional.province}).coverage==='ESTIMATED'&&resolution({province:regional.province}).resolution_level==='REGIONAL_ESTIMATE','valid sparse province regional estimate transparent');
  assert(stats.regional_stats.every(r=>r.donors.length>=2&&r.donors.every(d=>d.property_type===r.property_type&&d.sample_count>=80&&d.distance_km<=500)),'regional donors same type and documented distance sample thresholds');
  const apt=resolution({ward:city[0].ward}),house=resolution({ward:city[0].ward,property_type:'HOUSE'});
  assert(apt.available&&house.available&&apt.stat_key!==house.stat_key&&apt.median_price_per_m2!==house.median_price_per_m2,'same location different property types remain isolated');
  for(const t of index.property_types.filter(t=>t.status==='DISABLED'))assert(!resolution({property_type:t.code}).available,'disabled type cannot reuse another type price');
  let blocked=true;for(const area of [undefined,null,NaN,0,1501,'80']){try{api.predict(model,{...base,area_m2:area});blocked=false;}catch{}}assert(blocked,'invalid area blocked');
  function fill(point={}){const p={...base,...point};doc.getElementById('housePropertyType').value=p.property_type;event(doc.getElementById('housePropertyType'),'change');doc.getElementById('houseProvince').value=p.province;event(doc.getElementById('houseProvince'),'change');doc.getElementById('houseWard').value=p.ward||'';event(doc.getElementById('houseWard'),'change');doc.getElementById('houseSubArea').value=p.sub_area||'';event(doc.getElementById('houseSubArea'),'change');doc.getElementById('houseForm').elements.area_m2.value=p.area_m2;}
  const checkEstimate=()=>{predict();assert(!doc.getElementById('houseResult').hidden,'result renders');};
  sample();checkEstimate();assert(doc.getElementById('houseP25').textContent.includes('P25')&&doc.getElementById('houseP75').textContent.includes('P75'),'asking price quantile totals displayed');
  assert(!doc.getElementById('houseResultCoverage').textContent.includes('[object'),'coverage remains readable string');
  fill({ward:noWard.id});checkEstimate();assert(!doc.getElementById('houseEstimateWarning').hidden&&doc.getElementById('houseEstimateWarning').textContent.includes('Đây là giá ước lượng'),'province warning next to price visible');
  fill({province:regional.province});checkEstimate();assert(!doc.getElementById('houseEstimateWarning').hidden&&doc.getElementById('houseEstimateBadge').textContent.includes('lân cận')&&doc.getElementById('houseResultCoverage').textContent.includes('ESTIMATED'),'regional warning and badge visible');
  const map=win.HousePage.getMap(),layers=win.HousePage.getProvinceLayers();assert(map&&layers.size===34&&doc.querySelectorAll('.leaflet-overlay-pane path').length>=34,'34 sourced province geometries always visible');
  const [province,layer]=[...layers][1];layer.fire('click');assert(doc.getElementById('houseProvince').value===province&&!doc.getElementById('houseWard').value,'map click selects province without invented ward');
  fill();assert(map.getBounds().intersects(win.HousePage.getProvinceLayers().get(base.province).getBounds()),'province form focuses correct geometry');
  const selectedLayer=win.HousePage.getProvinceLayers().get(base.province);assert(selectedLayer.getLayers()[0].options.weight===3,'selected province highlighted');
  const tiles=win.HousePage.getTileLayer();assert(tiles._url.startsWith('https://tile.openstreetmap.org/'),'OSM HTTPS layer configured');
  const onlineBefore=win.HousePage.getTileStatus().loaded;
  tiles.fire('tileerror',{error:Error('simulated OSM outage')});await tick();
  assert(doc.getElementById('houseMapStatus').textContent.includes('chưa tải được')&&win.HousePage.getProvinceLayers().size===34,'OSM failure keeps real local fallback geometry');
  fill({ward:city[0].ward});checkEstimate();assert(!doc.getElementById('houseEstimate').disabled,'estimate usable during tile outage');
  // Keyboard canonical search; accents are folded only for matching.
  const combo=doc.getElementById('houseWardSearch');combo.value='yen hoa';event(combo,'input');
  assert(doc.getElementById('houseWardSuggestions').textContent.includes('Phường Yên Hòa'),'accentless yen hoa finds canonical ward');
  combo.dispatchEvent(new win.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));combo.dispatchEvent(new win.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  assert(combo.value==='Phường Yên Hòa'&&!doc.getElementById('houseEstimate').disabled,'keyboard chooses exact canonical ward');
  combo.value='phuc th';event(combo,'input');assert(doc.getElementById('houseWardSuggestions').textContent.includes('Xã Phúc Thịnh'),'phuc th finds canonical commune without long scroll');
  combo.value='abcxyz';event(combo,'input');predict();assert(doc.getElementById('houseEstimate').disabled&&doc.getElementById('houseResult').hidden&&!doc.getElementById('houseWardError').hidden,'unselected random ward text rejected inline');
  fill({ward:city[0].ward,sub_area:'Thôn Đồng'});checkEstimate();assert(doc.getElementById('houseSelectedLocation').textContent.includes('Thôn Đồng')&&!doc.getElementById('houseEstimateWarning').hidden,'typed detail retained with ward fallback disclosure');
  save();await tick();await tick();assert(calls.length===0&&!doc.getElementById('houseSaveLogin').hidden,'guest save requires login with no insert');
  const before=doc.getElementById('housePrice').textContent;doc.getElementById('scenarioArea').value=120;event(doc.getElementById('scenarioArea'),'input');assert(doc.getElementById('housePrice').textContent===before,'scenario separate until applied');
  doc.getElementById('houseApplyScenario').click();assert(Number(doc.getElementById('houseForm').elements.area_m2.value)===120,'area only scenario applies');
  user={id:'user-a',email:'a@example.test'};callback('SIGNED_IN',{user});
  fill(project);predict();save();save();await tick();await tick();
  assert(rows.length===1&&rows[0].input_data.metadata.resolution_level==='SUB_AREA'&&!rows[0].input_data.inputs&&rows[0].input_data.metadata.area_m2===80&&rows[0].input_data.metadata.estimated_price_vnd===rows[0].predicted_price_vnd,'direct save mandatory metadata area and price retained with optional form off');
  fill({ward:noWard.id,sub_area:'Thôn Đồng'});predict();save();await tick();await tick();
  assert(rows.length===2&&rows[1].input_data.metadata.selected_sub_area==='Thôn Đồng'&&rows[1].input_data.metadata.resolution_level==='PROVINCE','fallback history stores chosen detail and actual province');
  fill({province:regional.province});predict();save();await tick();await tick();
  assert(rows.length===3&&rows[2].input_data.metadata.donors.length>=2&&rows[2].input_data.metadata.stats_location_used.region,'regional history stores actual donor locations');
  assert(calls.filter(c=>c.operation==='insert').every(c=>c.row.user_id==='user-a'),'inserts use verified owner');
  await open('history.html');assert(section()?.querySelectorAll('.history-record').length===3,'direct province and regional cards render');
  assert(section().textContent.includes('Resolution: SUB_AREA')&&section().textContent.includes('Resolution: PROVINCE')&&section().textContent.includes('Resolution: REGIONAL_ESTIMATE')&&section().textContent.includes('Thôn Đồng'),'history selected versus used locations and resolution');
  assert(doc.documentElement.scrollWidth<=win.innerWidth+1,'history fits viewport');
  const source=await(await fetch('/api/market-data.js')).text();
  async function callApi(query={},method='GET',data=stats){const module={exports:null};new Function('module','require',source)(module,p=>p.includes('core')?api:p.includes('index')?index:data);const result={headers:{}};const res={setHeader(k,v){result.headers[k]=v;},status(code){result.status=code;return this;},json(body){result.body=body;return result;}};await module.exports({method,query},res);return result;}
  assert((await callApi()).body.available===false,'API safe no data');assert((await callApi({},'POST')).status===405,'API GET only');assert((await callApi({province:['bad']})).status===400,'API array parameters rejected');
  for(const r of city){const got=await callApi({province:base.province,ward:r.ward,property_type:'APARTMENT',area_m2:'80'});assert(got.body.stat_key===r.stat_key&&got.body.location_valid&&got.body.stats_location.ward&&got.body.estimated_price_vnd===r.median_price_per_m2*80,'API same city independent statistic');}
  assert((await callApi({...base,ward:'abcxyz',area_m2:'80'})).body.location_valid===false,'API invalid ward rejected');
  assert((await callApi({...base,ward:noWard.id,sub_area:'Thôn Đồng',area_m2:'80'})).body.resolution_level==='PROVINCE','API real unpriced ward fallback');
  assert((await callApi({...base,province:regional.province,area_m2:'80'})).body.coverage==='ESTIMATED','API regional fallback');
  assert((await callApi({...base,area_m2:'0'})).status===400,'API invalid area rejected');assert((await callApi({},'GET',null)).status===503,'API missing aggregate safely unavailable');
  const corrupt={...stats,stats:stats.stats.map(r=>r.stat_key===city[0].stat_key?{...r,median_price_per_m2:NaN}:r)};
  assert((await callApi({...base,ward:city[0].ward,area_m2:'80'},'GET',corrupt)).body.available===false,'API corrupt aggregate rejected');
  await open('vietnam-house-price.html');fill();predict();assert(doc.documentElement.scrollWidth<=win.innerWidth+1,'estimator fits viewport');
  assert(doc.getElementById('houseBrowseRows').children.length>0&&doc.getElementById('houseBrowseRows').textContent.includes('2026'),'explorer actual ward stats with latest date');
  doc.getElementById('houseBrowseType').value='HOUSE';event(doc.getElementById('houseBrowseType'),'change');assert(doc.getElementById('houseBrowseRows').textContent.includes('Nhà riêng')&&!doc.getElementById('houseBrowseRows').textContent.includes('Căn hộ'),'explorer type isolated');
  assert(!win.__houseErrors.length,'no uncaught page errors');
  window.__failHouseModel=true;await open('vietnam-house-price.html');assert(!win.HousePage.getModel()&&doc.getElementById('houseFields').disabled,'data fetch failure safely disables estimate');
  report.textContent=JSON.stringify({ok:true,width:Number(new URL(location.href).searchParams.get('width')),checks:checks.length,parity:{count:fixtures.fixtures.length,maxAbsoluteVnd:maxAbsolute},tileLoadsObserved:onlineBefore,sameCity:city.map(r=>({key:r.stat_key,median:r.median_price_per_m2}))});
 }catch(error){report.textContent=JSON.stringify({ok:false,error:error.message,checks});}
})();
