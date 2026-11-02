'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),http=require('node:http');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),artifacts=path.join(__dirname,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 const server=http.createServer((req,res)=>{const name=decodeURIComponent(req.url.split('?')[0]);const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}fs.readFile(file,(e,b)=>{if(e){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript; charset=utf-8':'text/html; charset=utf-8');res.end(b);});});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let chrome,ws;const errors=[],checks=[];
 try{
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'zunda-equivalent-qa-'));
  chrome=spawn(path.join(process.env.ProgramFiles,'Google','Chrome','Application','chrome.exe'),['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
  const active=path.join(profile,'DevToolsActivePort');let port=0;
  for(let i=0;i<100&&!port;i++){try{port=Number(fs.readFileSync(active,'utf8').split('\n')[0])||0;}catch(e){if(!['ENOENT','EBUSY','EACCES'].includes(e.code))throw e;}if(!port)await wait(100);}
  assert(port,'Dedicated headless Chrome became ready');const targets=await(await fetch(`http://127.0.0.1:${port}/json`)).json();const target=targets.find(t=>t.type==='page'&&t.url==='about:blank');
  ws=new WebSocket(target.webSocketDebuggerUrl);let seq=0;const pending=new Map();
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(m.error):p.resolve(m.result);}};
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>reject(Error(method+' timed out')),20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const check=async(name,expression,test=Boolean)=>{const v=await evaluate(expression);assert(test(v),`${name}: ${JSON.stringify(v)}`);checks.push(name);};
  const url=process.env.PUBLIC_QA_URL||`http://127.0.0.1:${server.address().port}/`;
  await call('Runtime.enable');await call('Page.enable');await call('Page.navigate',{url});
  let ready=false;for(let i=0;i<200;i++){try{ready=await evaluate('Boolean(window.VIDEO_DATA&&document.querySelectorAll(".card").length)');}catch(e){if(e.code!==-32000)throw e;}if(ready)break;await wait(100);}assert(ready,'Portal data became ready');
  await check('same card grid and 100-item pagination','document.querySelectorAll(".card").length',v=>v===100);
  await check('seven canonical direct competitors','({n:channels.length,ids:new Set(channels.map(c=>c.channel_id)).size,excluded:channels.some(c=>/応援隊/.test(c.channel_name))})',v=>v.n===7&&v.ids===7&&!v.excluded);
  await check('full public listing rather than latest fifty','videos.length',v=>v>2200);
  await check('no duplicate or out-of-scope video IDs','new Set(videos.map(v=>v.video_id)).size===videos.length&&videos.every(v=>channels.some(c=>c.channel_id===v.channel_id))');
  await check('requested four channels are first','channels.slice(0,4).map(c=>c.channel_id)',v=>v.join(',')==='UCCLJicEOjjzQftcy6ICtbgA,UCEaNC-I0as6FhFHzBgWDxMw,UCF27uipT8xmfaIALkQ14hKA,UCXzt6u4VooLQcyc3-yIFIcw');
  await check('reused OCR remains searchable','videos.filter(v=>v.thumbnail_text).length',v=>v>=69);
  await check('metadata includes likes comments tags','videos.some(v=>v.like_count>0&&v.comment_count>0&&v.tags.length>0)');
  await check('every displayed video has an archived thumbnail URL','videos.every(v=>Boolean(v.thumbnail_saved_url)&&hasArchivedThumbnail(v))');
  await check('public thumbnails use Pages rather than billable GCS delivery','videos.every(v=>v.thumbnail_saved_url.startsWith("assets/thumbnails/")&&!v.thumbnail_saved_url.includes("storage.googleapis.com"))');
  await check('keyword search',`(()=>{document.getElementById('q').value='コマツ';render();return filteredRows.length>0&&filteredRows.every(r=>r.v.title.includes('コマツ')||r.v.thumbnail_text.includes('コマツ')||r.v.tags.some(t=>t.includes('コマツ')))})()`);
  await check('channel filter',`(()=>{document.getElementById('q').value='';channelSelect.value=channels[3].portal_channel_name;render();return filteredRows.length>300&&filteredRows.every(r=>r.v.channel_id===channels[3].channel_id)})()`);
  await check('descending view sort',`(()=>{document.getElementById('sort').value='views_desc';render();return filteredRows.every((r,i,a)=>!i||observedViews(a[i-1].v)>=observedViews(r.v))})()`);
  await check('detail includes metadata and digest',`(()=>{openDetail(filteredRows[0].v);return document.getElementById('dialog').open&&document.getElementById('detailMeta').textContent.includes('公開日')&&document.getElementById('detailScriptText').textContent.length>20})()`);
  await evaluate(`document.getElementById('dialog').close();document.getElementById('resetBtn').click();`);
  await check('load more adds the next hundred',`(()=>{document.getElementById('loadMoreBtn').click();return document.querySelectorAll('.card').length})()`,v=>v===200);
  await check('description is not mislabeled as a saved script',`!hasTranscript({video_id:videos[0].video_id})`);
  await check('cloud connection status is explicit',`document.getElementById('pipelineStatus').textContent.includes('未接続')||window.PIPELINE_STATUS.cloud_connected===true`);
  await check('unknown counts remain unknown',`observedLikes({})===null&&rateText(null,100)==='未取得'`);
  await check('thumbnail fallback terminates',`(()=>{const img=document.createElement('img'),v={thumbnail_url:'https://invalid.example/x.jpg'};applyThumbnail(img,v);for(let i=0;i<5;i++)fallbackImageForVideo(img,v);return img.onerror===null&&img.src.startsWith('data:')})()`);
  await evaluate(`document.getElementById('resetBtn').click()`);
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await wait(700);
  const desktop=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(artifacts,'equivalent-desktop.png'),Buffer.from(desktop.data,'base64'));
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(200);
  await check('mobile has no horizontal overflow','document.documentElement.scrollWidth<=document.documentElement.clientWidth');
  const mobile=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(artifacts,'equivalent-mobile.png'),Buffer.from(mobile.data,'base64'));
  await check('no secret tokens in public data',`!JSON.stringify([channels,videos]).match(/AIza|sk-ant-|ghp_/)`);
  assert.equal(errors.length,0,'Runtime exceptions');const result={url,passed:checks.length,checks,exceptions:errors,engine:'dedicated headless Chrome / page-scoped CDP'};
  fs.writeFileSync(path.join(root,'reports/equivalent-browser-check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{if(ws)ws.close();if(chrome)chrome.kill();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
