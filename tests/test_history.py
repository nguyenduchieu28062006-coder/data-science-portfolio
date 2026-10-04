"""History browser tests with an in-memory SDK; no production records are mutated.
Run: python tests/test_history.py
"""
import sys
sys.dont_write_bytecode = True
import test_auth as harness

harness.MOCK = r"""
window.supabase = {createClient: () => parent.__client};
"""
harness.RUNNER = r"""
(async () => {
 const report = document.getElementById('report');
 const checks = [];
 const assert = (ok, name) => { if (!ok) throw Error(name); checks.push(name); };
 const tick = () => new Promise(resolve => setTimeout(resolve, 80));
 let user = null, callback, rows = [], calls = [], failure = false;
 window.__authControl = {configured:true};
 window.__client = {
   auth: {
     onAuthStateChange(fn) {callback=fn;},
     async getSession() {return {data:{session:user ? {user} : null}};},
     async getUser() {return {data:{user}};},
     async signOut() {user=null; callback('SIGNED_OUT',null); return {};}
   },
   from(table) {
     const query={table,filters:[],operation:'load'};
     const chain={
       select(columns) {query.columns=columns;return chain;},
       insert(row) {query.operation='insert';query.row=row;return chain;},
       delete() {query.operation='delete';return chain;},
       eq(key,value) {query.filters.push([key,value]);return chain;},
       order(key,options) {query.order=[key,options];return chain;},
       range(start,end) {query.range=[start,end];return chain;},
       then(resolve,reject) {
         calls.push(query);
         return new Promise(done => setTimeout(() => {
           if(failure) {done({error:{status:500}});return;}
           if(query.operation==='insert') {rows.push({...query.row,id:String(rows.length+1),created_at:new Date().toISOString()});done({});return;}
           const matching=rows.filter(row=>query.filters.every(([key,value])=>row[key]===value));
           if(query.operation==='delete') rows=rows.filter(row=>!matching.includes(row));
           done({data:matching,error:null});
         },30)).then(resolve,reject);
       }
     }; return chain;
   }
 };
 const frame=document.getElementById('frame');
 async function open(page) {
   await new Promise(resolve=>{frame.onload=resolve;frame.src=page;});
   await frame.contentWindow.PortfolioAuth.ready; await tick();
   return frame.contentWindow;
 }
 try {
   let win=await open('history.html');
   assert(calls.length===0 && win.document.getElementById('historyStatus').textContent.includes('đăng nhập'),'guest history never queries');
   win=await open('health-prediction.html'); await win.loadHealthModel();
   const predict=()=>{win.document.querySelector('[data-health-sample="0"]').click();win.document.getElementById('healthForm').requestSubmit();};
   const save=()=>win.document.getElementById('historySave').click();
   predict();save();await tick();
   assert(calls.length===0 && !win.document.getElementById('historySaveLogin').hidden,'guest prediction and login prompt');
   user={id:'user-a',email:'a@example.test'};callback('SIGNED_IN',{user});
   predict();save();save();await tick();await tick();
   assert(rows.length===1 && rows[0].input_data===null && Math.abs(rows[0].model_score-.342)<.001,'single insert, raw score and default null');
   save();await tick();assert(rows.length===1,'saved prediction cannot be inserted twice');
   predict();win.document.getElementById('historySaveInputs').checked=true;save();await tick();await tick();
   assert(rows.length===2 && Object.keys(rows[1].input_data).length===13,'opt-in stores exactly thirteen features');
   predict();failure=true;save();await tick();await tick();
   assert(win.document.getElementById('historySaveMessage').textContent.includes('Không thể lưu')&&!win.document.getElementById('historySave').disabled,'save failure permits retry');failure=false;
   win=await open('history.html');
   assert(win.document.querySelectorAll('.history-record').length===2,'load saved records');
   user={id:'user-b',email:'b@example.test'};callback('SIGNED_IN',{user});await tick();await tick();
   assert(win.document.querySelectorAll('.history-record').length===0,'account switch clears and scopes records (mock only)');
   user={id:'user-a',email:'a@example.test'};callback('SIGNED_IN',{user});await tick();await tick();
   assert(calls.filter(c=>c.operation==='load').every(c=>c.filters.some(([k,v])=>k==='user_id'&&['user-a','user-b'].includes(v))&&c.range[1]===49),'server filters and bounded pagination');
   assert(win.document.body.textContent.includes('Dữ liệu đầu vào không được lưu')&&win.document.body.textContent.includes('Tuổi (năm)'),'details with and without inputs');
   assert(win.document.documentElement.scrollWidth<=win.innerWidth+1,'history viewport fits');
   win.confirm=()=>false;win.document.querySelector('.history-record button').click();await tick();assert(rows.length===2,'delete cancellation');
   win.confirm=()=>true;win.document.querySelector('.history-record button').click();await tick();await tick();assert(rows.length===1&&win.document.querySelectorAll('.history-record').length===1,'delete one updates UI');
   win.document.querySelector('.history-module > div > button').click();await tick();await tick();assert(rows.length===0,'delete all health');
   callback('SIGNED_OUT',null);await tick();assert(win.document.querySelectorAll('.history-record').length===0&&!win.document.getElementById('historyLogin').hidden,'logout clears history');
   report.textContent=JSON.stringify({ok:true,width:Number(new URL(location.href).searchParams.get('width')),checks:checks.length});
 } catch(error) {report.textContent=JSON.stringify({ok:false,error:error.message,checks});}
})();
"""

if __name__ == '__main__':
    harness.main()
