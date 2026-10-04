"use strict";
(() => {
    const button=document.getElementById('houseSave'),checkbox=document.getElementById('houseSaveInputs'),message=document.getElementById('houseSaveMessage'),login=document.getElementById('houseSaveLogin');
    let result=null,pending=false;
    function render(){button.disabled=pending||!result||result.saved;button.textContent=pending?'Đang lưu…':result?.saved?'Đã lưu':'Lưu vào lịch sử';checkbox.disabled=pending||Boolean(result?.saved);}
    function active(snapshot,user){return result===snapshot&&window.PortfolioAuth?.getUser()?.id===user;}
    addEventListener('portfolio:houseprediction',event=>{result={...event.detail,saved:false};checkbox.checked=false;message.textContent='';login.hidden=true;render();});
    addEventListener('portfolio:houseclear',()=>{result=null;checkbox.checked=false;message.textContent='';login.hidden=true;render();});
    addEventListener('portfolio:authchange',()=>{result=null;checkbox.checked=false;message.textContent='Phiên tài khoản đã thay đổi. Dự đoán lại trước khi lưu.';login.hidden=true;render();});
    button.addEventListener('click',async()=>{
        if(pending||!result||result.saved)return;
        const snapshot=result,include=checkbox.checked;pending=true;render();
        try {
            await window.PortfolioAuth?.ready;
            const auth=window.PortfolioAuth,client=auth?.getClient();
            if(auth?.getStatus()!=='ready'||!client){if(result===snapshot)message.textContent='Supabase chưa sẵn sàng. Vui lòng kiểm tra cấu hình.';return;}
            const {data,error}=await client.auth.getUser();
            if(error||!data?.user||auth.getUser()?.id!==data.user.id){if(result===snapshot){message.textContent='Bạn cần đăng nhập để lưu lịch sử.';login.hidden=false;}return;}
            if(!active(snapshot,data.user.id))return;
            const {error:insertError}=await client.from('house_price_history').insert({user_id:data.user.id,
                predicted_price_vnd:snapshot.predicted_price_vnd,predicted_price_per_m2:snapshot.predicted_price_per_m2,
                province:snapshot.province,area_name:snapshot.area_name,property_type:snapshot.property_type,model_version:snapshot.model_version,
                input_data:{metadata:snapshot.metadata,...(include?{inputs:snapshot.input_data}:{})}});
            if(insertError)throw insertError;
            snapshot.saved=true;if(active(snapshot,data.user.id))message.textContent='Đã lưu vào lịch sử.';
        } catch(error){if(result===snapshot){const expired=error?.status===401||['PGRST301','PGRST302'].includes(error?.code);message.textContent=expired?'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.':error?.code==='42P01'||error?.code==='PGRST205'?'Chưa có bảng House Price. Chạy SQL thiết lập trong Supabase rồi thử lại.':'Không thể lưu lịch sử. Vui lòng thử lại.';login.hidden=!expired;}}
        finally{pending=false;render();}
    });
    render();
})();
