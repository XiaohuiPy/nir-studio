const $=id=>document.getElementById(id);
let worker,ready=false,columns=[],last=null,predRows=null,modelAvailable=false,pending=new Map(),serial=0;
function message(text,error=false){$('log').textContent=text||'';$('log').style.color=error?'#b43b38':'#087e8b'}
function status(text,ok=false){$('status').textContent=text;$('status').style.background=ok?'#e0f4ea':'#fff2d9';$('status').style.color=ok?'#176b48':'#946100'}
function setBusy(b){document.querySelectorAll('button.action').forEach(el=>el.disabled=b||!ready)}
function call(fn,args=[]){return new Promise((resolve,reject)=>{let id=++serial;pending.set(id,{resolve,reject});worker.postMessage({id,fn,args})})}
function parse(s){return JSON.parse(s)}
function table(rows,max=15){if(!rows?.length)return '<p class="muted">暂无数据</p>';let keys=Object.keys(rows[0]);const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');return '<table><thead><tr>'+keys.map(x=>`<th>${esc(x)}</th>`).join('')+'</tr></thead><tbody>'+rows.slice(0,max).map(r=>'<tr>'+keys.map(k=>`<td>${esc(typeof r[k]==='number'?Number(r[k].toFixed(5)):r[k])}</td>`).join('')+'</tr>').join('')+'</tbody></table>'}
function graph(id,traces,layout={}){Plotly.newPlot(id,traces,{template:'plotly_white',margin:{l:58,r:15,t:35,b:55},...layout},{responsive:true,displaylogo:false})}
function plotSpectra(id,d){graph(id,d.curves.map((v,i)=>({x:d.w,y:v,mode:'lines',type:'scatter',line:{width:1},opacity:.6,showlegend:false})),{xaxis:{title:'Wavelength (nm)'},yaxis:{title:'Signal'}})}
async function run(action){setBusy(true);message('');try{await action()}catch(e){console.error(e);message('操作失败：'+(e.message||e),true)}finally{setBusy(false)}}
async function filePayload(file){if(!file)throw Error('请选择文件');if(/\.xlsx?$/i.test(file.name)){let bytes=new Uint8Array(await file.arrayBuffer());let parts=[];for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));return {fn:'load_excel',value:btoa(parts.join(''))}}
return {fn:'load_csv',value:await file.text()}}
async function importData(file){let f=await filePayload(file);let d=parse(await call(f.fn,[f.value]));afterData(d)}
function afterData(d){columns=d.columns;$('dataInfo').textContent=`已导入 ${d.rows} 个样品，${columns.length} 列`;$('preview').innerHTML=table(d.preview);for(let id of ['target','ident'])$(id).replaceChildren();for(let c of columns){$('target').add(new Option(c,c));$('ident').add(new Option(c,c))}
$('ident').add(new Option('(none)','(none)'),0);$('target').value=columns.includes('Reference')?'Reference':columns.at(-1);$('ident').value=columns.includes('Sample ID')?'Sample ID':'(none)';modelAvailable=false;last=null;showSpectrum('rawPlot','None')}
function opts(){let lo=$('low').value,hi=$('high').value;return {target:$('target').value,ident:$('ident').value,algo:$('algo').value,pre:$('pre').value,selection:$('selection').value,k:+$('k').value,comp:+$('comp').value,window:+$('window').value,ratio:+$('ratio').value,folds:+$('folds').value,optimize:$('optimize').checked,low:lo===''?null:+lo,high:hi===''?null:+hi}}
async function showSpectrum(id,pre){if(!columns.length)return;let o=opts();let d=parse(await call('spectrum',[o.target,o.ident,pre,o.window,o.low,o.high]));plotSpectra(id,d)}
function download(name,blob){let u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1500)}
function csv(rows){if(!rows?.length)return '';let keys=Object.keys(rows[0]);const q=x=>'"'+String(x??'').replaceAll('"','""')+'"';return [keys.map(q).join(','),...rows.map(r=>keys.map(k=>q(r[k])).join(','))].join('\r\n')}
function csvDownload(name,rows){download(name,new Blob(['\ufeff'+csv(rows)],{type:'text/csv;charset=utf-8'}))}
function showResults(r){last=r;modelAvailable=true;const fmt=x=>x===null||!Number.isFinite(x)?'—':x.toFixed(4);$('metrics').innerHTML=[['Test R²',r.test.r2],['RMSEP',r.test.rmse],['RMSECV',r.cv.rmse]].map(([n,v])=>`<div class="stat">${n}<strong>${fmt(v)}</strong></div>`).join('');
$('metricTable').innerHTML=table(['train','cv','test'].map(k=>({Dataset:k,R2:r[k].r2,RMSE:r[k].rmse,MAE:r[k].mae,Bias:r[k].bias,RPD:r[k].rpd})));
$('best').textContent='最优参数：'+JSON.stringify(r.best);
let scatter=[],all=[];
for(let [name,color] of [['train','#77b4c0'],['cv','#e6a25d'],['test','#0a7d89']]){let p=r.points[name];scatter.push({x:p.actual,y:p.pred,mode:'markers',type:'scatter',name,marker:{color,size:7,opacity:.75}});all.push(...p.actual,...p.pred)}
let min=Math.min(...all),max=Math.max(...all);scatter.push({x:[min,max],y:[min,max],mode:'lines',name:'Ideal',line:{dash:'dash',color:'#85969a'}});graph('scatter',scatter,{xaxis:{title:'Reference'},yaxis:{title:'Predicted'}});
let p=r.points.test;graph('residual',[{x:p.pred,y:p.pred.map((v,i)=>v-p.actual[i]),mode:'markers',type:'scatter',marker:{color:'#087e8b'}}],{xaxis:{title:'Predicted'},yaxis:{title:'Residual'}});
$('features').textContent=r.selection?'选中波长 (nm)：'+r.selection.wavelengths.map(v=>v.toFixed(2)).join(', '):'未启用波长筛选';
if(r.selection?.scores)graph('vipPlot',[{x:r.selection.scores.map((_,i)=>i+1),y:r.selection.scores,mode:'lines',type:'scatter'}],{xaxis:{title:'Wavelength index'},yaxis:{title:'VIP score'}});
else Plotly.purge('vipPlot');
$('modelInfo').textContent=`模型：${r.algorithm}\n测试 RMSE：${r.test.rmse.toFixed(4)}`;
}
function b64ToBytes(b64){let s=atob(b64),u=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i);return u}
function bytesToB64(bytes){let p=[];for(let i=0;i<bytes.length;i+=32768)p.push(String.fromCharCode(...bytes.subarray(i,i+32768)));return btoa(p.join(''))}
function go(page){document.querySelectorAll('section').forEach(s=>s.classList.toggle('active',s.id===page));document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));if(page==='eval'&&last)requestAnimationFrame(()=>{['scatter','residual','vipPlot'].forEach(id=>{try{Plotly.Plots.resize($(id))}catch{}})})}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>go(b.dataset.page));
$('demo').onclick=()=>run(async()=>afterData(parse(await call('load_demo'))));
$('dataFile').onchange=e=>run(async()=>importData(e.target.files[0]));
$('demoDownload').onclick=()=>run(async()=>{let content=await call('demo_csv');download('nir_demo.csv',new Blob(['\ufeff'+content],{type:'text/csv;charset=utf-8'}))});
$('previewPre').onclick=()=>run(()=>showSpectrum('prePlot',$('pre').value));
$('train').onclick=()=>run(async()=>{let o=opts();if(!columns.length)throw Error('请先导入光谱数据');status('模型训练中…');let r=parse(await call('fit_model',[o.target,o.ident,o.algo,o.pre,o.selection,o.k,o.comp,o.window,o.ratio,o.folds,o.optimize,o.low,o.high]));showResults(r);go('eval');status('计算引擎就绪',true);message('模型训练与评价完成')});
$('downloadTest').onclick=()=>{if(!last)return message('尚未训练模型',true);let p=last.points.test;csvDownload('nir_test_predictions.csv',p.actual.map((v,i)=>({Reference:v,Prediction:p.pred[i],Residual:p.pred[i]-v})))};
$('predictBtn').onclick=()=>run(async()=>{let f=await filePayload($('unknownFile').files[0]);let fn=f.fn==='load_excel'?'predict_excel':'predict_csv';let d=parse(await call(fn,[f.value]));predRows=d.rows;$('predTable').innerHTML=table(predRows,100);message(`完成 ${predRows.length} 个样品的预测`)});
$('downloadPred').onclick=()=>predRows?csvDownload('nir_unknown_predictions.csv',predRows):message('暂无预测结果',true);
$('saveModel').onclick=()=>run(async()=>{let b=await call('export_model');download('nir_model.nir',new Blob([b64ToBytes(b)],{type:'application/octet-stream'}))});
$('loadModel').onclick=()=>run(async()=>{if(!confirm('仅加载自己创建的可信模型文件。确定继续吗？'))return;let f=$('modelFile').files[0];if(!f)throw Error('请选择模型文件');let info=parse(await call('import_model',[bytesToB64(new Uint8Array(await f.arrayBuffer()))]));modelAvailable=true;last=null;$('modelInfo').textContent=JSON.stringify(info,null,2);message('模型已加载，可以进行未知样品预测')});
async function boot(){
try{
worker=new Worker('worker.js');
worker.onmessage=e=>{let d=e.data;if(d.type==='status'){status(d.text,d.ok);return}let p=pending.get(d.id);if(!p)return;pending.delete(d.id);d.error?p.reject(new Error(d.error)):p.resolve(d.result)};
worker.onerror=e=>{status('计算引擎启动失败');message(e.message,true)};
await new Promise((resolve,reject)=>{let timeout=setTimeout(()=>reject(Error('引擎初始化超时，请检查网络/CDN')),180000);worker.addEventListener('message',function handler(e){if(e.data.type==='ready'){clearTimeout(timeout);worker.removeEventListener('message',handler);resolve()}else if(e.data.type==='fatal'){clearTimeout(timeout);reject(Error(e.data.error))}})});
ready=true;setBusy(false);status('计算引擎就绪',true);afterData(parse(await call('load_demo')));message('已自动加载模拟光谱数据，可立即开始建模。');
}catch(e){status('初始化失败');message(e.message,true)}
}
setBusy(true);boot();
