"""Read-only YouTube metadata refresh. API key stays in the environment.
No search.list, no AI services, no retries, and at most 40 list requests.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

HERE=Path(__file__).resolve().parent
key=os.environ.get('YOUTUBE_API_KEY')
if not key:raise SystemExit('Set YOUTUBE_API_KEY in the local environment; never put it in site files.')
source=(HERE/'data/catalog.js').read_text(encoding='utf-8')
catalog=json.loads(source[len('window.RESEARCH_DATA = '):].strip().rstrip(';'))
requests=0

def get(resource,params):
    global requests
    if requests>=40:raise SystemExit('Request cap reached; stopped without retries.')
    requests+=1
    params={**params,'key':key}
    try:
        with urlopen('https://www.googleapis.com/youtube/v3/'+resource+'?'+urlencode(params),timeout=30) as res:return json.load(res)
    except HTTPError as e:
        try:reason=json.loads(e.read()).get('error',{}).get('errors',[{}])[0].get('reason','unknown')
        except Exception:reason='unknown'
        raise SystemExit(f'YouTube HTTP {e.code}: {reason}; stopped without retries.')
    except URLError:raise SystemExit('YouTube network error; stopped without retries.')

def chunks(seq,n=50):
    for i in range(0,len(seq),n):yield seq[i:i+n]

def seconds(value):
    m=re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',value)
    return sum(int(v or 0)*factor for v,factor in zip(m.groups(),[3600,60,1])) if m else 0

videos={}
ids=[v['id'] for v in catalog['videos']]
for batch in chunks(ids):
    for v in get('videos',{'part':'snippet,statistics,contentDetails','id':','.join(batch),'hl':'ja'})['items']:videos[v['id']]=v
roles={c['id']:c['role'] for c in catalog['channels'] if c['id']}
name_roles={c['name']:c['role'] for c in catalog['channels']}
for v in videos.values():
    snippet=v['snippet'];roles.setdefault(snippet['channelId'],name_roles.get(snippet['channelTitle'],'source'))
all_channels=[];new_ids=set(ids)
for batch in chunks(list(roles)):
    raw=get('channels',{'part':'snippet,statistics,contentDetails','id':','.join(batch)})
    for c in raw['items']:
        all_channels.append({'id':c['id'],'name':c['snippet']['title'],'role':roles[c['id']],'subscribers':int(c.get('statistics',{}).get('subscriberCount',0)), 'subscribersObserved':datetime.now(timezone(timedelta(hours=9))).date().isoformat()})
        playlist=c['contentDetails']['relatedPlaylists']['uploads']
        for item in get('playlistItems',{'part':'contentDetails','playlistId':playlist,'maxResults':30})['items']:new_ids.add(item['contentDetails']['videoId'])
for batch in chunks(sorted(new_ids-set(videos))):
    for v in get('videos',{'part':'snippet,statistics,contentDetails','id':','.join(batch),'hl':'ja'})['items']:videos[v['id']]=v
public=[]
for vid,v in videos.items():
    s=v['snippet'];length=seconds(v['contentDetails']['duration'])
    if length<=180 or s.get('liveBroadcastContent')!='none':continue
    public.append({'id':vid,'title':s.get('localized',{}).get('title',s['title']),'channel':s['channelTitle'],'channel_id':s['channelId'],'published':s['publishedAt'],'views':int(v.get('statistics',{}).get('viewCount',0)),'seconds':length})
observed=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
result={'observed':observed,'channels':all_channels,'videos':public,'list_requests':requests,'missing_cached_ids':sorted(set(ids)-set(videos)),'paid_api_calls':0,'method':'YouTube Data API read-only list; no retries; max 40 requests'}
(HERE/'data_sources').mkdir(exist_ok=True)
out=HERE/'data_sources/current.json'
if out.exists():(HERE/'data_sources'/f'previous_{observed}.json').write_bytes(out.read_bytes())
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'videos':len(public),'channels':len(all_channels),'list_requests':requests,'missing_cached_ids':len(result['missing_cached_ids'])}))
