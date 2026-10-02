const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const http=require('node:http');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(__dirname,'artifacts');fs.mkdirSync(artifacts,{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 let chrome,ws;const failures=[],checks=[];
 const server=http.createServer((req,res)=>{
   const name=decodeURIComponent(req.url.split('?')[0]);const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));
   if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
   fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);res.end();}else{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript; charset=utf-8':file.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8');res.end(data);}});
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 try{
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'zunda-research-qa-'));
  const exe=path.join(process.env.ProgramFiles,'Google','Chrome','Application','chrome.exe');
  chrome=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
  chrome.on('error',e=>failures.push(e.message));
  const active=path.join(profile,'DevToolsActivePort');for(let i=0;i<100&&!fs.existsSync(active);i++)await wait(100);
  const debugPort=Number(fs.readFileSync(active,'utf8').split('\n')[0]);
  const targets=await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json();const target=targets.find(t=>t.type==='page'&&t.url==='about:blank');assert(target,'Dedicated blank target exists');
  ws=new WebSocket(target.webSocketDebuggerUrl);let seq=0;const pending=new Map();
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')failures.push(JSON.stringify(m.params.exceptionDetails));if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(m.error):p.resolve(m.result);}};
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>reject(Error('CDP timeout '+method)),20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const testUrl=process.env.PUBLIC_QA_URL || `http://127.0.0.1:${port}/`;
  await call('Runtime.enable');await call('Page.enable');await call('Page.navigate',{url:testUrl});
  for(let i=0;i<60;i++){if(await evaluate('Boolean(window.RESEARCH_DATA && document.querySelectorAll(".video-card").length)'))break;await wait(100);}
  const check=async(name,expression,test)=>{const v=await evaluate(expression);assert(test(v),`${name}: ${JSON.stringify(v)}`);checks.push(name);};
  await check('initial cards and count','({cards:document.querySelectorAll(".video-card").length,total:DATA.videos.length})',v=>v.cards===36&&v.total>=150);
  await check('unique ids and channels','({unique:new Set(DATA.videos.map(v=>v.id)).size,total:DATA.videos.length,channels:DATA.channels.length})',v=>v.unique===v.total&&v.channels>=12);
  await check('source role filter',`(()=>{$('role').value='source';filterVideos();return {n:state.filtered.length,valid:state.filtered.every(v=>v.role==='source')}})()`,v=>v.n>=6&&v.valid);
  await check('benchmark role filter',`(()=>{$('role').value='benchmark';filterVideos();return {n:state.filtered.length,valid:state.filtered.every(v=>v.role==='benchmark')}})()`,v=>v.n>30&&v.valid);
  await check('suzuki keyword results',`(()=>{$('reset').click();$('query').value=String.fromCodePoint(0x30b9,0x30ba,0x30ad);filterVideos();return state.filtered.map(v=>v.id)})()`,v=>v.includes('PzbaA1FiBkE'));
  await check('compare entity set',`(()=>{$('entitySet').value='komatsu';$('entitySet').dispatchEvent(new Event('change'));chooseView('compare');return document.querySelectorAll('.compare-card').length})()`,v=>v===4);
  await check('benchmark included in topic comparison',`state.compare.includes('LAPxdRluun0')`,Boolean);
  await check('topic comparison uses distinct channels',`new Set(state.compare.map(id=>byId.get(id).channel)).size`,v=>v===4);
  await check('comparison cap',`(()=>{const x=DATA.videos.find(v=>!state.compare.includes(v.id));toggleCompare(x.id);return state.compare.length})()`,v=>v===4);
  await check('save candidate',`(()=>{saveIdea(byId.get('PzbaA1FiBkE'));chooseView('ideas');return notes.ideas.length})()`,v=>v===1);
  await check('duplicate save guarded',`(()=>{saveIdea(byId.get('PzbaA1FiBkE'));return notes.ideas.length})()`,v=>v===1);
  await check('edits persist',`(()=>{const el=document.querySelector('[data-field="shift"]');el.value='QA note';el.dispatchEvent(new Event('input',{bubbles:true}));return JSON.parse(localStorage.getItem(KEY)).ideas[0].shift})()`,v=>v==='QA note');
  await check('safe external urls',`['https://www.youtube.com/watch?v=PzbaA1FiBkE','https://youtu.be/PzbaA1FiBkE','https://evil.example/watch?v=PzbaA1FiBkE','javascript:alert(1)'].map(parseYouTube)`,v=>v[0]===v[1]&&v[2]===null&&v[3]===null);
  await check('reject foreign import url',`(()=>{try{validateNotes({version:1,ideas:[{id:'x',title:'x',url:'javascript:alert(1)'}],videoNotes:{}});return false}catch(e){return true}})()`,Boolean);
  await check('text escaping',`(()=>{const n=notes.ideas[0];n.promise='<img src=x onerror=alert(1)>';renderIdeas();return document.querySelectorAll('#ideaGrid img').length})()`,v=>v===0);
  await call('Page.reload');await wait(400);
  await check('reload preserves notes',`notes.ideas[0].shift`,v=>v==='QA note');
  await check('growth sort uses observed differences',`(()=>{$('reset').click();$('sort').value='growth';filterVideos();return {available:state.filtered[0].deltaPerDay!=null,display:document.querySelectorAll('.growth').length}})()`,v=>v.available&&v.display>0);
  await evaluate(`$('reset').click();notes.ideas=[];persist();updateCounts();`);
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await wait(700);const desktop=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(artifacts,'desktop.png'),Buffer.from(desktop.data,'base64'));
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(200);
  await check('mobile no horizontal overflow','({scroll:document.documentElement.scrollWidth,width:document.documentElement.clientWidth})',v=>v.scroll<=v.width);
  const mobile=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(artifacts,'mobile.png'),Buffer.from(mobile.data,'base64'));
  await check('no secret tokens in bundle',`!JSON.stringify(DATA).match(/AIza|sk-ant-|ghp_/)`,Boolean);
  assert.equal(failures.length,0,'No browser runtime exceptions');
  fs.writeFileSync(path.join(root,'reports','browser-check.json'),JSON.stringify({url:testUrl,passed:checks.length,checks,exceptions:failures,engine:'dedicated headless Chrome / page-scoped CDP',artifacts},null,2));
  console.log(JSON.stringify({passed:checks.length,exceptions:failures.length,artifacts}));
 }finally{if(ws)ws.close();if(chrome)chrome.kill();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
