'use strict';
const DATA = window.RESEARCH_DATA;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const KEY = 'zunda-research-notes-v1';
const ROLES = {benchmark:'ベンチマーク',competitor:'直接競合',source:'ネタ元候補',reference:'形式参考'};
let notes = {version:1,ideas:[],videoNotes:{}};
let storageAvailable = true;
try { const saved=JSON.parse(localStorage.getItem(KEY) || 'null'); if(saved) notes=validateNotes(saved); } catch(e) { storageAvailable=false; }
const state={view:'videos',compare:[],limit:36,filtered:[]};
const byId = new Map(DATA.videos.map(v=>[v.id,v]));
const channelByName = new Map(DATA.channels.map(c=>[c.name,c]));
const topicName = id => DATA.topics.find(t=>t.id===id)?.name || 'その他';
const num = n => n===null || n===undefined ? '未取得' : Number(n).toLocaleString('ja-JP');
const shortNum = n => n==null ? '未取得' : n>=10000 ? `${(n/10000).toFixed(n>=100000?0:1)}万` : num(n);
const videoUrl = id => `https://www.youtube.com/watch?v=${id}`;
const duration = seconds => seconds ? `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}` : '尺未取得';
const searchUrl = q => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;
function validateNotes(value){
  if(!value || value.version!==1 || !Array.isArray(value.ideas) || typeof value.videoNotes!=='object' || !value.videoNotes) throw Error('形式が違います');
  if(value.ideas.length>3000 || Object.keys(value.videoNotes).length>10000) throw Error('件数が多すぎます');
  const allowed=['id','videoId','url','title','promise','content','shift','status','updated'];
  const ideas=value.ideas.map(row=>{
    if(!row || typeof row.id!=='string' || !row.id || typeof row.title!=='string') throw Error('候補の形式が違います');
    const clean={}; for(const k of allowed) if(typeof row[k]==='string') clean[k]=row[k].slice(0,10000);
    if(clean.url && !parseYouTube(clean.url)) throw Error('YouTube以外のURLが含まれています');
    if(!['候補','調査中','採用','保留'].includes(clean.status)) clean.status='候補';
    return clean;
  });
  const videoNotes={};
  for(const [id,row] of Object.entries(value.videoNotes)){
    if(!/^[\w-]{11}$/.test(id) || !row || typeof row!=='object') continue;
    videoNotes[id]={};for(const k of ['promise','content']) if(typeof row[k]==='string') videoNotes[id][k]=row[k].slice(0,10000);
  }
  return {version:1,ideas,videoNotes};
}
function parseYouTube(raw){
  try{
    const u=new URL(raw);let id='';
    if(u.hostname==='youtu.be') id=u.pathname.split('/')[1];
    else if(['youtube.com','www.youtube.com','m.youtube.com'].includes(u.hostname)) id=u.searchParams.get('v') || u.pathname.match(/^\/(shorts|embed|live)\/([\w-]{11})/)?.[2];
    return /^[\w-]{11}$/.test(id||'') ? id : null;
  }catch(e){return null;}
}
function persist(){
  try{localStorage.setItem(KEY,JSON.stringify(notes));storageAvailable=true;return true;}
  catch(e){storageAvailable=false;toast('ブラウザ保存ができません。メモを書き出して保全してください。');return false;}
}
function toast(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('visible'),3500);}
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function badge(v){return `<span class="badge ${esc(v.role)}">${esc(ROLES[v.role]||ROLES.reference)}</span>`;}
function chooseView(view){state.view=view;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`${view}View`);document.querySelectorAll('.nav-button').forEach(b=>b.classList.toggle('active',b.dataset.view===view));if(view==='channels')renderChannels();if(view==='compare')renderCompare();if(view==='ideas')renderIdeas();}
function updateCounts(){$('compareCount').textContent=state.compare.length;$('savedCount').textContent=notes.ideas.length;}
function filterVideos(){
  const words=$('query').value.trim().toLowerCase().split(/\s+/).filter(Boolean),role=$('role').value,topic=$('topic').value,channel=$('channel').value;
  const days=$('period').value==='all'?Infinity:Number($('period').value),minimum=Number($('minViews').value),today=new Date(`${DATA.built}T00:00:00+09:00`).getTime();
  state.filtered=DATA.videos.filter(v=>{
    const text=`${v.title} ${v.channel} ${(v.thumbnailText||[]).join(' ')}`.toLowerCase();
    if(!words.every(w=>text.includes(w)))return false;
    if(role==='direct'&&!['benchmark','competitor'].includes(v.role))return false;
    if(role!=='all'&&role!=='direct'&&v.role!==role)return false;
    if(topic&&topic!==v.topic||channel&&channel!==v.channel)return false;
    if(minimum>0&&(v.views==null||v.views<minimum))return false;
    if($('hideCompilation').checked&&v.compilation)return false;
    if(days!==Infinity&&(!v.published||(today-new Date(`${v.published}T00:00:00+09:00`).getTime())/86400000>days))return false;
    return true;
  });
  const field={views:'views',daily:'viewsPerDay',relative:'relativeViews',growth:'deltaPerDay'}[$('sort').value];
  state.filtered.sort((a,b)=>field?(b[field]??-1)-(a[field]??-1):String(b.published).localeCompare(String(a.published)));
  const hints={growth:'複数観測がある動画のみ、増加数 ÷ 観測間の日数で比較。初回観測だけの動画は末尾に表示します。',daily:'平均再生／日は累計 ÷ 観測までの日数。直近の増加速度ではありません。',relative:'突出度は収録した同チャンネル通常動画の中央値比。公開日数・サンプル数の差があります。'};
  $('metricHint').textContent=hints[$('sort').value]||'累計再生数は観測時点の保存値です。現在の再生数は動画ページで確認できます。';
  renderVideos();
}
function card(v){
  const saved=notes.ideas.some(n=>n.videoId===v.id),selected=state.compare.includes(v.id);
  return `<article class="video-card" data-id="${v.id}"><a class="thumb-wrap" href="${videoUrl(v.id)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(v.title)}をYouTubeで開く"><img src="https://i.ytimg.com/vi/${v.id}/hqdefault.jpg" loading="lazy" alt="${esc(v.title)}のサムネ"><span class="duration">${duration(v.seconds)}</span></a><div class="card-body"><div class="card-meta">${badge(v)}<span>${esc(topicName(v.topic))}</span></div><h3><button class="title-button" data-action="detail">${esc(v.title)}</button></h3><div class="card-meta"><span>${esc(v.channel)}</span><span>公開 ${esc(v.published||'不明')}</span></div><div class="stats"><strong>${shortNum(v.views)}<small> 回</small></strong>${v.relativeViews?`<small>中央値比 ${v.relativeViews}×</small>`:''}</div><div class="observed">再生数の観測 ${esc(v.observed)}${$('sort').value==='daily'?` · 平均 ${num(v.viewsPerDay)}回／日`:''}</div><div class="ocr">${v.thumbnailText?.length?esc(v.thumbnailText.slice(0,3).join(' / ')):'サムネ文字の保存なし'}</div><div class="card-actions"><button data-action="save" class="${saved?'selected':''}">${saved?'候補に保存済み':'＋ 企画候補'}</button><button data-action="compare" class="${selected?'selected':''}">${selected?'比較から外す':'比較に追加'}</button><button data-action="related">同題材を探す ↗</button></div></div></article>`;
}
function renderVideos(){
  $('resultCount').textContent=`${state.filtered.length}件 / ${DATA.videos.length}件収録`;
  $('videoGrid').innerHTML=state.filtered.slice(0,state.limit).map(card).join('')||'<div class="empty">条件に一致する動画がありません。条件を戻すか、YouTube検索から新しい題材を探してください。</div>';
  for(const el of document.querySelectorAll('#videoGrid [data-id]')){
    const v=byId.get(el.dataset.id);
    if(v.deltaPerDay!=null){const p=document.createElement('div');p.className='growth observed';p.textContent=`観測間 +${num(v.viewDelta)}回（${v.deltaFrom} → ${v.observed}）`;
      el.querySelector('.observed').after(p);}
  }
  $('loadMore').hidden=state.limit>=state.filtered.length;
  document.querySelectorAll('#topicChips .chip').forEach(b=>b.classList.toggle('active',b.dataset.topic===$('topic').value));
  updateCounts();
}
function saveIdea(v){
  if(notes.ideas.some(n=>n.videoId===v.id)){chooseView('ideas');return;}
  const memo=notes.videoNotes[v.id]||{};
  notes.ideas.unshift({id:crypto.randomUUID(),videoId:v.id,url:videoUrl(v.id),title:v.title,promise:memo.promise||'',content:memo.content||'',shift:'',status:'候補',updated:new Date().toISOString()});
  persist();updateCounts();renderVideos();toast('企画候補に保存しました');
}
function toggleCompare(id){
  if(state.compare.includes(id))state.compare=state.compare.filter(x=>x!==id);
  else if(state.compare.length<4)state.compare.push(id);
  else return toast('比較は最大4本です。現在の比較から1本外してください。');
  updateCounts();renderVideos();if(state.view==='compare')renderCompare();
}
function discoveryQuery(v){return v.entities?.length?DATA.entities.find(e=>e.id===v.entities[0])?.name+' 中国':v.title.replace(/【[^】]*】/g,'').slice(0,55);}
function openSearch(q,type='youtube'){window.open(type==='news'?`https://www.google.com/search?tbm=nws&q=${encodeURIComponent(q)}`:searchUrl(q),'_blank','noopener,noreferrer');}
function renderChannels(){
  const rank={benchmark:0,competitor:1,source:2,reference:3};
  $('channelGrid').innerHTML=[...DATA.channels].sort((a,b)=>(rank[a.role]??3)-(rank[b.role]??3)||(b.medianViews??0)-(a.medianViews??0)).map(c=>{
    const url=c.id?`https://www.youtube.com/channel/${c.id}/videos`:searchUrl(c.name);
    return `<article class="channel-card"><span class="badge ${esc(c.role)}">${esc(ROLES[c.role]||ROLES.reference)}</span><h3>${esc(c.name)}</h3><div class="channel-stats"><div><strong>${shortNum(c.medianViews)}</strong><span>収録通常動画の再生中央値</span></div><div><strong>${c.sampleSize}</strong><span>収録通常動画</span></div><div><strong>${c.hits100k}</strong><span>10万回以上</span></div></div><p>${c.role==='source'?'題材・背景・情報の入口。探検隊の実際の参照元と確定したものではありません。':'同じ視聴者・会話劇の見せ方を比較する対象。'}</p><p>再生数の最新観測 ${esc(c.observed||'データ未収録')} · ${c.subscribers!=null?'登録者 '+num(c.subscribers)+'（'+esc(c.subscribersObserved||'2026-09-27')+' 観測）':'登録者未取得'}</p><div class="card-actions"><button data-channel="${esc(c.name)}">収録動画を見る</button><a class="button" href="${url}" target="_blank" rel="noopener noreferrer">チャンネルを開く ↗</a></div></article>`;
  }).join('');
}
function renderCompare(){
  $('compareGrid').innerHTML=state.compare.map(id=>{
    const v=byId.get(id),memo=notes.videoNotes[id]||{};
    return `<article class="compare-card" data-id="${id}"><a href="${videoUrl(id)}" target="_blank" rel="noopener noreferrer"><img src="https://i.ytimg.com/vi/${id}/hqdefault.jpg" alt="${esc(v.title)}のサムネ"></a><div class="compare-body">${badge(v)}<h3>${esc(v.title)}</h3><p>${esc(v.channel)}<br>公開 ${esc(v.published||'不明')}<br>${num(v.views)}回 · 観測 ${esc(v.observed)}<br>尺 ${duration(v.seconds)}</p><div class="ocr">${esc((v.thumbnailText||[]).join(' / '))||'文字の保存なし'}</div><label>サムネの約束・誰が見たくなる？<textarea data-note="promise" placeholder="強気な宣言が裏目に出る / なぜ日本企業は強い？など">${esc(memo.promise||'')}</textarea></label><label>内容・見せ方はどう違う？<textarea data-note="content" placeholder="約束をどの情報で回収？ 会話の面白さ・初心者向けかなど">${esc(memo.content||'')}</textarea></label><div class="card-actions"><button data-action="save">企画候補に保存</button><button data-action="compare">比較から外す</button></div></div></article>`;
  }).join('')||'<div class="empty">動画カードから比較したい動画を追加してください。上の題材セットからも並べられます。</div>';
}
function renderIdeas(){
  $('ideaGrid').innerHTML=notes.ideas.map(n=>`<article class="idea-card" data-idea="${esc(n.id)}"><h3>${esc(n.title)}</h3><a class="source-url" href="${videoUrl(n.videoId||parseYouTube(n.url))}" target="_blank" rel="noopener noreferrer">${esc(n.url)}</a><div class="idea-fields"><label>企画案・仮タイトル<input data-field="title" value="${esc(n.title)}"></label><label>サムネの約束・視聴者が見る理由<textarea data-field="promise" placeholder="どんな期待を持ってクリックする？">${esc(n.promise)}</textarea></label><label>動画内容・使える情報と見せ方<textarea data-field="content" placeholder="何を知れる？ どんな会話・場面が使える？">${esc(n.content)}</textarea></label><label>今回見る理由・ずらすポイント<textarea data-field="shift" placeholder="新しい出来事 / その後 / 未回収の疑問 / 会話劇での見せ方。既出でも後発が伸びる根拠があるか。">${esc(n.shift)}</textarea></label></div><div class="actions"><label>状態<select data-field="status">${['候補','調査中','採用','保留'].map(s=>`<option ${n.status===s?'selected':''}>${s}</option>`).join('')}</select></label><button data-remove-idea="${esc(n.id)}">候補から削除</button></div></article>`).join('')||'<div class="empty">気になった動画を「企画候補」に保存するか、URLから追加してください。</div>';
}
function detail(id){
  const v=byId.get(id);$('detailContent').innerHTML=`<img class="detail-image" src="https://i.ytimg.com/vi/${id}/hqdefault.jpg" alt="${esc(v.title)}のサムネ">${badge(v)}<h2>${esc(v.title)}</h2><p>${esc(v.channel)} · 公開 ${esc(v.published||'不明')} · ${duration(v.seconds)}</p><p><strong>${num(v.views)} 回</strong>（${esc(v.observed)} 観測）</p><div class="detail-label">保存されているサムネ文字</div><p>${esc((v.thumbnailText||[]).join(' / '))||'未取得'}</p><div class="detail-label">同題材の動画を探す</div><div class="detail-tags">${(v.entities||[]).map(key=>`<button data-entity="${key}">${esc(DATA.entities.find(e=>e.id===key)?.name)}</button>`).join('')||'<span>キーワードを拾って検索してください。</span>'}</div><div class="card-actions" data-id="${id}"><a class="button primary" href="${videoUrl(id)}" target="_blank" rel="noopener noreferrer">YouTubeで確認 ↗</a><button data-action="save">企画候補に保存</button><button data-action="compare">比較に追加</button><button data-copy-id="${id}">企画情報をコピー</button></div><p class="observed">動画タイトル・サムネの主張は、事実確認済みの情報ではありません。元記事や一次資料で検証してから企画に使ってください。</p>`;$('detailDialog').showModal();
}
document.addEventListener('click',async event=>{
  const view=event.target.closest('[data-view]');if(view)return chooseView(view.dataset.view);
  const action=event.target.closest('[data-action]');
  if(action){const id=action.closest('[data-id]')?.dataset.id,v=byId.get(id);if(!v)return;if(action.dataset.action==='detail')detail(id);if(action.dataset.action==='save')saveIdea(v);if(action.dataset.action==='compare')toggleCompare(id);if(action.dataset.action==='related')openSearch(discoveryQuery(v));return;}
  const channel=event.target.closest('[data-channel]');if(channel){$('channel').value=channel.dataset.channel;$('role').value='all';$('query').value='';$('topic').value='';$('period').value='all';$('minViews').value='0';filterVideos();chooseView('videos');return;}
  const chip=event.target.closest('[data-topic]');if(chip){$('topic').value=$('topic').value===chip.dataset.topic?'':chip.dataset.topic;state.limit=36;filterVideos();return;}
  const entity=event.target.closest('[data-entity]');if(entity){$('detailDialog').close();$('query').value=DATA.entities.find(e=>e.id===entity.dataset.entity)?.name||'';$('channel').value='';$('role').value='all';$('topic').value='';filterVideos();chooseView('videos');return;}
  const remove=event.target.closest('[data-remove-idea]');if(remove&&confirm('この企画候補とメモを削除しますか？')){notes.ideas=notes.ideas.filter(n=>n.id!==remove.dataset.removeIdea);persist();renderIdeas();updateCounts();return;}
  const copy=event.target.closest('[data-copy-id]');if(copy){const v=byId.get(copy.dataset.copyId);try{await navigator.clipboard.writeText(`${v.title}\n${v.channel}\n${videoUrl(v.id)}\nサムネ文字：${v.thumbnailText.join(' / ')}\n再生数：${num(v.views)}（${v.observed}観測）`);toast('企画情報をコピーしました');}catch(e){toast('コピーできません。動画リンクを開いて確認してください。');}}
});
document.addEventListener('input',event=>{
  const input=event.target;
  if(input.matches('[data-note]')){const id=input.closest('[data-id]').dataset.id;notes.videoNotes[id]??={};notes.videoNotes[id][input.dataset.note]=input.value;persist();}
  if(input.matches('[data-field]')){const n=notes.ideas.find(n=>n.id===input.closest('[data-idea]').dataset.idea);n[input.dataset.field]=input.value;n.updated=new Date().toISOString();persist();}
});
for(const id of ['role','topic','channel','period','minViews','sort','hideCompilation'])$(id).addEventListener('change',()=>{state.limit=36;filterVideos();});
$('query').addEventListener('input',()=>{state.limit=36;filterVideos();});
$('reset').onclick=()=>{$('query').value='';$('role').value='all';$('topic').value='';$('channel').value='';$('period').value='all';$('minViews').value='0';$('sort').value='published';$('hideCompilation').checked=true;state.limit=36;filterVideos();};
$('loadMore').onclick=()=>{state.limit+=36;renderVideos();};
$('youtubeSearch').onclick=()=>openSearch($('query').value.trim()||'中国 日本 海外の反応');
$('newsSearch').onclick=()=>openSearch($('query').value.trim()||'中国 日本 国際情勢','news');
$('closeDetail').onclick=()=>$('detailDialog').close();
$('clearCompare').onclick=()=>{state.compare=[];updateCounts();renderCompare();renderVideos();};
$('entitySet').onchange=()=>{const key=$('entitySet').value;if(!key)return;state.compare=DATA.videos.filter(v=>v.entities?.includes(key)&&!v.compilation).sort((a,b)=>(b.views??0)-(a.views??0)).slice(0,4).map(v=>v.id);updateCounts();renderCompare();renderVideos();};
$('addIdea').onclick=()=>{const url=prompt('参考動画のYouTube URLを貼ってください');if(url===null)return;const id=parseYouTube(url.trim());if(!id)return toast('有効なYouTube動画URLを入力してください');if(byId.has(id))saveIdea(byId.get(id));else{if(notes.ideas.some(n=>n.videoId===id))return toast('すでに保存されています');notes.ideas.unshift({id:crypto.randomUUID(),videoId:id,url:videoUrl(id),title:'新しい企画候補（タイトルを入力）',promise:'',content:'',shift:'',status:'候補',updated:new Date().toISOString()});persist();updateCounts();}renderIdeas();};
$('exportNotes').onclick=()=>download(`zunda-notes-${new Date().toISOString().slice(0,10)}.json`,JSON.stringify(notes,null,2),'application/json');
$('importNotes').onchange=async event=>{const f=event.target.files[0];if(!f)return;try{if(f.size>5*1024*1024)throw Error('5MB以下のファイルを使用してください');const incoming=validateNotes(JSON.parse(await f.text()));const merged=new Map(notes.ideas.map(n=>[n.id,n]));for(const n of incoming.ideas){const old=merged.get(n.id);if(!old||(n.updated||'')>=(old.updated||''))merged.set(n.id,n);}notes.ideas=[...merged.values()];for(const [id,row] of Object.entries(incoming.videoNotes))notes.videoNotes[id]={...(notes.videoNotes[id]||{}),...row};persist();updateCounts();renderIdeas();renderVideos();toast('既存の候補を残してメモを取り込みました');}catch(e){toast(`読み込みできません：${e.message}`);}event.target.value='';};
$('exportCatalog').onclick=()=>{const csvRow=values=>values.map(v=>`"${String(v??'').replace(/"/g,'""').replace(/^[=+@-]/,"'")}"`).join(',');const out=[csvRow(['タイトル','チャンネル','区分','公開日','累計再生数','観測日','尺秒','サムネ文字','URL']),...state.filtered.map(v=>csvRow([v.title,v.channel,ROLES[v.role],v.published,v.views,v.observed,v.seconds,v.thumbnailText.join(' / '),videoUrl(v.id)]))];download('zunda-research.csv','\uFEFF'+out.join('\r\n'),'text/csv;charset=utf-8');};
$('videoCount').textContent=DATA.videos.length;
const observed=[...new Set(DATA.videos.map(v=>v.observed))].sort();$('dataDate').textContent=`保存データ ${observed[0]}〜${observed.at(-1)}`;
for(const t of DATA.topics)$('topic').insertAdjacentHTML('beforeend',`<option value="${t.id}">${esc(t.name)}</option>`);
for(const c of [...DATA.channels].sort((a,b)=>a.name.localeCompare(b.name,'ja')))$('channel').insertAdjacentHTML('beforeend',`<option value="${esc(c.name)}">${esc(c.name)}</option>`);
$('topicChips').innerHTML=DATA.topics.map(t=>`<button class="chip" data-topic="${t.id}">${esc(t.name)}</button>`).join('');
for(const e of DATA.entities)$('entitySet').insertAdjacentHTML('beforeend',`<option value="${e.id}">${esc(e.name)}</option>`);
filterVideos();updateCounts();if(!storageAvailable)toast('保存済みメモを読めませんでした。元データを上書きする前に書き出しを確認してください。');
