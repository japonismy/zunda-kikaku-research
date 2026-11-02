"""Free YouTube list quota -> local mirrors of the BigQuery tables.

Full uploads listing, current metadata, idempotent daily snapshots. No paid
services, SQL, Cloud Run, retry, search.list or OCR. Cached metadata is reused.
"""
import argparse
import json
import os
import re
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from common import ROOT, config, now, read, write, table, upsert, save_table, validate_scope

def seconds(iso):
    m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',iso)
    return sum(int(n or 0)*f for n,f in zip(m.groups(),(3600,60,1))) if m else 0

def ingest(raw_channels, raw_videos, observed, listing_complete):
    cfg=config(); registry={c['channel_id']:c for c in cfg['channels']}
    channels=[]; videos=[]; channel_snapshots=[]; video_snapshots=[]
    schemas=read(ROOT/'backend/schemas.json')
    for raw in raw_channels:
        cid=raw['id']; s=raw['snippet']; st=raw.get('statistics',{}); entry=registry[cid]
        row={f['name']:None for f in schemas['channels']}
        row.update(channel_id=cid,handle=s.get('customUrl',''),title=s['title'],description=s.get('description',''),subscriber_count=int(st['subscriberCount']) if 'subscriberCount' in st else None,video_count=int(st['videoCount']) if 'videoCount' in st else None,total_view_count=int(st['viewCount']) if 'viewCount' in st else None,published_at=s.get('publishedAt',''),thumbnail_url=s.get('thumbnails',{}).get('high',{}).get('url',''),country=s.get('country',''),uploads_playlist_id=raw['contentDetails']['relatedPlaylists']['uploads'],is_own_channel=0,status='active',status_detail='YouTube public channel returned',last_synced_at=observed,created_at=observed,updated_at=observed,relation_type='competitor',relation_note=entry['reason'],content_category='zundamon_world_business_dialogue',watch_scope='full',analysis_status='active')
        channels.append(row)
        snapshot={f['name']:None for f in schemas['channel_snapshots']}
        snapshot.update(id=None,channel_id=cid,snapshot_date=observed[:10],subscriber_count=row['subscriber_count'],video_count=row['video_count'],total_view_count=row['total_view_count'],source='zunda_daily_metadata',created_at=observed)
        channel_snapshots.append(snapshot)
    for raw in raw_videos:
        s=raw['snippet']; cid=s['channelId']
        if cid not in registry: continue
        st=raw.get('statistics',{}); iso=raw.get('contentDetails',{}).get('duration','')
        row={f['name']:None for f in schemas['videos']}
        row.update(video_id=raw['id'],channel_id=cid,title=s['title'],description=s.get('description',''),published_at=s.get('publishedAt',''),duration_iso=iso,duration_sec=seconds(iso),view_count=int(st['viewCount']) if 'viewCount' in st else None,like_count=int(st['likeCount']) if 'likeCount' in st else None,comment_count=int(st['commentCount']) if 'commentCount' in st else None,thumbnail_url_max=s.get('thumbnails',{}).get('maxres',s.get('thumbnails',{}).get('high',{})).get('url',''),tags=json.dumps(s.get('tags',[]),ensure_ascii=False),category_id=s.get('categoryId',''),thumbnail_local_path='',fetched_at=observed)
        videos.append(row)
        snapshot={f['name']:None for f in schemas['video_snapshots']}
        snapshot.update(id=None,video_id=row['video_id'],snapshot_date=observed[:10],view_count=row['view_count'],like_count=row['like_count'],comment_count=row['comment_count'],source='zunda_daily_metadata',created_at=observed)
        video_snapshots.append(snapshot)
    validate_scope(channels); validate_scope(videos)
    upsert('channels',channels,['channel_id']);upsert('videos',videos,['video_id'])
    upsert('channel_snapshots',channel_snapshots,['channel_id','snapshot_date','source'])
    upsert('video_snapshots',video_snapshots,['video_id','snapshot_date','source'])
    # An unavailable video stays in videos with its last real observation.
    for name in schemas:
        if not (ROOT/'data_sources/warehouse'/f'{name}.json').exists():save_table(name,[])
    write(ROOT/'data_sources/warehouse/collection_status.json',{'observed_at':observed,'listing_complete':listing_complete,'listed_channels':list(registry),'returned_video_ids':[v['video_id'] for v in videos]})
    return {'channels':len(channels),'videos':len(videos),'listing_complete':listing_complete}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cached',action='store_true');args=parser.parse_args()
    cfg=config(); timestamp=now(); path=ROOT/'data_sources'/f'full_youtube_{timestamp[:10]}.json'
    if args.cached or path.exists():
        raw=read(path)
        if raw is None:
            raw=read(ROOT/'data_sources'/f'direct_{timestamp[:10]}.json');raw['listing_complete']=False
        result=ingest(raw['channels'],raw['videos'],raw.get('observed_at',raw.get('observed',timestamp)),raw.get('listing_complete',False))
        print(json.dumps({**result,'api_calls':0,'cache_reused':True}));return
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key:raise SystemExit('YOUTUBE_API_KEY is missing.')
    calls=0
    def get(resource,params):
        nonlocal calls
        if calls>=cfg['max_youtube_requests']:raise RuntimeError('YouTube request cap reached. No retry.')
        calls+=1
        try:
            with urlopen('https://www.googleapis.com/youtube/v3/'+resource+'?'+urlencode({**params,'key':key}),timeout=35) as r:return json.load(r)
        except HTTPError as e:raise RuntimeError(f'YouTube HTTP {e.code}; no retry') from None
        except (URLError,TimeoutError):raise RuntimeError('YouTube network failure; no retry') from None
    # Reuse the same-day channel and video metadata already collected earlier.
    previous=read(ROOT/'data_sources'/f'direct_{timestamp[:10]}.json',{})
    raw_channels=previous.get('channels') or get('channels',{'part':'snippet,statistics,contentDetails','id':','.join(c['channel_id'] for c in cfg['channels'])})['items']
    if {c['id'] for c in raw_channels}!={c['channel_id'] for c in cfg['channels']}:raise RuntimeError('Missing channel; existing warehouse retained')
    ids=set()
    for channel in raw_channels:
        token=''
        while True:
            params={'part':'contentDetails','playlistId':channel['contentDetails']['relatedPlaylists']['uploads'],'maxResults':50}
            if token:params['pageToken']=token
            page=get('playlistItems',params);ids.update(item['contentDetails']['videoId'] for item in page['items'])
            if len(ids)>cfg['max_videos']:raise RuntimeError('Video count cap reached. Existing warehouse retained')
            token=page.get('nextPageToken','')
            if not token:break
    videos={v['id']:v for v in previous.get('videos',[])}
    # Also recheck older saved videos, so removals preserve their latest value.
    ids.update(v['video_id'] for v in table('videos'))
    missing=sorted(ids-set(videos))
    for start in range(0,len(missing),50):
        for v in get('videos',{'part':'snippet,statistics,contentDetails','id':','.join(missing[start:start+50]),'hl':'ja'})['items']:videos[v['id']]=v
    raw={'observed_at':timestamp,'channels':raw_channels,'videos':list(videos.values()),'listing_complete':True,'api_calls':calls,'paid_calls':0}
    write(path,raw)
    result=ingest(raw_channels,raw['videos'],timestamp,True)
    write(ROOT/'reports/collection.json',{**result,'observed_at':timestamp,'api_calls':calls,'paid_calls':0,'raw_source':str(path)})
    print(json.dumps({**result,'api_calls':calls,'paid_calls':0}))

if __name__=='__main__':main()
