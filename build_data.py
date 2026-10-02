"""Build public metadata only from cached research. No paid API calls."""
import csv
import json
import os
import re
import statistics
import sys
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ['ZUNDA_RESEARCH_ROOT'])
ASSETS = Path(os.environ['ZUNDA_THUMB_ROOT'])
PACK = Path(os.environ['ZUNDA_PACK_ROOT'])

def load(path):
    raw = path.read_bytes()
    return json.loads(raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'))

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def jp(s):
    return json.loads('"'+s+'"')

benchmark = jp(r'\u305a\u3093\u3060\u63a2\u691c\u968a')
topics = [
  ('auto', jp(r'\u81ea\u52d5\u8eca\u30fbEV'), ['EV','BYD',jp(r'\u81ea\u52d5\u8eca'),jp(r'\u30d9\u30f3\u30c4'),jp(r'\u30b9\u30ba\u30ad'),jp(r'\u30c8\u30e8\u30bf'),jp(r'\u65e5\u672c\u8eca')]),
  ('infra', jp(r'\u30a4\u30f3\u30d5\u30e9\u30fb\u5efa\u8a2d'), [jp(r'\u30c0\u30e0'),jp(r'\u9244\u9053'),jp(r'\u6a4b'),jp(r'\u5de5\u4e8b'),jp(r'\u5efa\u8a2d'),jp(r'\u6d2a\u6c34')]),
  ('industry', jp(r'\u4f01\u696d\u30fb\u7523\u696d\u30fb\u6280\u8853'), [jp(r'\u30b3\u30de\u30c4'),jp(r'\u5c0f\u677e'),jp(r'\u5de5\u5834'),jp(r'\u6280\u8853'),jp(r'\u534a\u5c0e\u4f53'),jp(r'\u64a4\u9000'),jp(r'\u30a8\u30a2\u30b3\u30f3'),jp(r'\u4f01\u696d')]),
  ('resources', jp(r'\u8cc7\u6e90\u30fb\u8cbf\u6613'), [jp(r'\u30ec\u30a2\u30a2\u30fc\u30b9'),jp(r'\u30bf\u30f3\u30b0\u30b9\u30c6\u30f3'),jp(r'\u8cc7\u6e90'),jp(r'\u8f38\u51fa'),jp(r'\u8cbf\u6613'), 'CPTPP']),
  ('economy', jp(r'\u7d4c\u6e08\u30fb\u66ae\u3089\u3057'), ['GDP',jp(r'\u501f\u91d1'),jp(r'\u9280\u884c'),jp(r'\u9810\u91d1'),jp(r'\u7d4c\u6e08'),jp(r'\u30b4\u30fc\u30b9\u30c8'),jp(r'\u4e0d\u52d5\u7523'),jp(r'\u5931\u696d')]),
  ('diplomacy', jp(r'\u5916\u4ea4\u30fb\u653f\u7b56\u30fb\u793e\u4f1a'), [])
]
entities = [('suzuki',jp(r'\u30b9\u30ba\u30ad')),('komatsu',jp(r'\u30b3\u30de\u30c4')),('benz',jp(r'\u30d9\u30f3\u30c4')),('byd','BYD'),('rare-earth',jp(r'\u30ec\u30a2\u30a2\u30fc\u30b9')),('rail',jp(r'\u9ad8\u901f\u9244\u9053')),('panda',jp(r'\u30d1\u30f3\u30c0')),('dam',jp(r'\u30c0\u30e0')),('aircon',jp(r'\u30a8\u30a2\u30b3\u30f3'))]
database = {}
channels = {}

def add(v, observed):
    vid = v.get('id')
    if not vid or not re.fullmatch(r'[\w-]{11}',vid):
        return
    old = database.get(vid)
    if old and old['observed'] > observed:
        return
    title = v.get('title','')
    name = v.get('channel') or (old or {}).get('channel') or benchmark
    if name == 'benchmark': name=benchmark
    date = str(v.get('published') or v.get('published_at') or v.get('date') or '')[:10]
    database[vid] = {
      'id':vid,'title':title,'channel':name,'channelId':v.get('channel_id','') or (old or {}).get('channelId',''),
      'published':date,'views':int(v['views']) if v.get('views') not in (None,'') else None,
      'seconds':int(v.get('seconds') or 0),'observed':observed,
      'topic':next((key for key,label,words in topics if not words or any(w.lower() in title.lower() for w in words)), 'diplomacy'),
      'entities':[key for key,label in entities if label.lower() in title.lower()],
      'thumbnailText':(old or {}).get('thumbnailText',[]),
      'compilation': bool(re.search(jp(r'\u7dcf\u96c6\u7de8|\u307e\u3068\u3081'),title)),
      'observations': (old or {}).get('observations',[])
    }
    if old and old['views'] is not None and old['observed'] != observed:
        database[vid]['observations'].append({'date':old['observed'],'views':old['views']})

for v in load(ASSETS/'manifest.json'):
    add(v,'2026-09-17')
for v in load(ROOT/'competitors.json')['videos']:
    add(v,'2026-09-27')
for p in ROOT.glob('UC*_raw.json'):
    raw=load(p)
    c=raw['channel']
    channels[c['snippet']['title']]={'id':c['id'],'subscribers':int(c.get('statistics',{}).get('subscriberCount',0)), 'role':'competitor'}
for v in rows(ROOT/'komatsu_metadata.csv'):
    add(v,'2026-09-27')
    channels.setdefault(v['channel'],{'id':'','subscribers':None,'role':'source'})
for v in load(PACK/'latest_listing_20260930.json'):
    if not isinstance(v,dict):continue
    # Cache may use different field names; never substitute missing views with zero.
    vid=v.get('id') or v.get('video_id')
    if vid in database:
        merged=dict(database[vid]); merged.update(v); merged['id']=vid
        if not any(k in v for k in ('views','view_count')): continue
        merged['views']=v.get('views',v.get('view_count'))
        add(merged,'2026-09-30')
for r in rows(ASSETS/'analysis.csv'):
    if r['id'] in database:
        try:database[r['id']]['thumbnailText']=json.loads(r['visible_text'])
        except (ValueError,TypeError):pass

# Public source-channel suggestions, not assertions about actual origin.
for name in [jp(r'\u30cb\u30c3\u30dd\u30f3\u79f0\u8cdb\u30a2\u30ef\u30fc')]:
    channels.setdefault(name,{'id':'','subscribers':None,'role':'source'})
channels[benchmark]['role']='benchmark'
for name in [jp(r'\u3048\u3060\u307e\u3081\u3058\u3083\u307d\u3093')]:
    if name in channels:channels[name]['role']='competitor'
# Apply an optional fresh, bounded public YouTube API snapshot.
current_path=HERE/'data_sources/current.json'
if current_path.exists():
    current=load(current_path)
    for c in current['channels']:
        if c['name'] in channels:
            role=channels[c['name']]['role']
            channels[c['name']]={**channels[c['name']],**c,'role':role}
    for v in current['videos']:
        if v['channel'] in channels:add(v,current['observed'])
# Exclude unrelated food references rather than silently widening the market.
database={vid:v for vid,v in database.items() if v['channel'] in channels}
if 'LAPxdRluun0' in database:
    database['LAPxdRluun0']['entities']=list(set(database['LAPxdRluun0']['entities']+['komatsu']))
    database['LAPxdRluun0']['topic']='industry'
result_channels=[]
for name,c in channels.items():
    items=[v for v in database.values() if v['channel']==name and not v['compilation']]
    values=[v['views'] for v in items if v['views'] is not None]
    median=statistics.median(values) if values else None
    c.update({'name':name,'sampleSize':len(items),'medianViews':median,'hits100k':sum(n>=100000 for n in values),'observed':max((v['observed'] for v in items),default=None)})
    result_channels.append(c)
    for v in items:v['relativeViews']=round(v['views']/median,2) if v['views'] is not None and median else None
for v in database.values():
    v['role']=channels.get(v['channel'],{}).get('role','reference')
    history=sorted(v.get('observations',[]),key=lambda x:x['date'])
    if history and v['views'] is not None:
        previous=history[-1]
        delta=v['views']-previous['views']
        days=(datetime.fromisoformat(v['observed'])-datetime.fromisoformat(previous['date'])).days
        v['viewDelta']=delta
        v['deltaFrom']=previous['date']
        v['deltaPerDay']=round(delta/days) if days>0 and delta>=0 else None
    if v['published']:
        try:age=max(1,(datetime.fromisoformat(v['observed'])-datetime.fromisoformat(v['published'])).days);v['viewsPerDay']=round(v['views']/age) if v['views'] is not None else None
        except ValueError:v['viewsPerDay']=None

dataset={'built':datetime.now().date().isoformat(),'videos':list(database.values()),'channels':result_channels,
 'topics':[{'id':k,'name':n} for k,n,_ in topics], 'entities':[{'id':k,'name':n} for k,n in entities],
 'sources':[{'label':'YouTube Data API public metadata snapshot','date':'2026-09-27'}, {'label':'Saved thumbnail metadata / OCR','date':'2026-09-17'}]}
(HERE/'data').mkdir(exist_ok=True)
(HERE/'reports').mkdir(exist_ok=True)
text=json.dumps(dataset,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
(HERE/'data/catalog.js').write_text('window.RESEARCH_DATA = '+text+';\n',encoding='utf-8')
(HERE/'reports/build.json').write_text(json.dumps({'python':sys.executable,'version':sys.version,'videos':len(database),'channels':len(channels),'has_ocr':sum(bool(v['thumbnailText']) for v in database.values()),'paid_calls':0},indent=2),encoding='utf-8')
print(json.dumps({'videos':len(database),'channels':len(channels),'has_ocr':sum(bool(v['thumbnailText']) for v in database.values())}))
