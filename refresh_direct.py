"""Refresh seven direct competitors using free YouTube Data API list quota.

No paid services, search.list, OCR, retry, or scheduled execution. At most 30
requests; latest 50 uploads per channel plus already catalogued videos.
"""
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
CHANNELS = [
    ('UCCLJicEOjjzQftcy6ICtbgA', 'ずんだ実話', 'benchmark', '指定ベンチマーク。国際情勢・中国・日本企業を扱う会話劇。'),
    ('UCEaNC-I0as6FhFHzBgWDxMw', 'すんだ観察所', 'benchmark', '指定ベンチマーク。提示URLの社会観察所と既存資料の表記をチャンネルIDで照合。'),
    ('UCF27uipT8xmfaIALkQ14hKA', 'ずんだ探検隊', 'benchmark', '指定ベンチマーク。国際比較・企業・技術を人物の会話で説明。'),
    ('UCXzt6u4VooLQcyc3-yIFIcw', '世界まる見えずんだもん', 'benchmark', '指定ベンチマーク。企業・産業・身近な社会の疑問を扱うずんだもん解説。'),
    ('UCEIXrjU4QgbKqZgZO1L9SVA', '天子のワダイ', 'competitor', 'ユーザー提示の @tenko-topic。既存資料でも国際情勢の会話劇比較先。'),
    ('UC9Le1DkKHWTw2KVDtS7Y__g', 'ニッポンすんだ村', 'competitor', 'れもんさんの既存調査にある会話劇比較先。国役・秘書・現場役の構成が近い。'),
    ('UCyJa4OYtGxD8oGkBqiu9oMA', 'えだまめじゃぽん', 'competitor', 'れもんさんの既存調査にある会話劇比較先。同じ企業・国際比較の題材を扱う。'),
]
KEY = os.environ.get('YOUTUBE_API_KEY')
if not KEY and '--cached' not in sys.argv:
    raise SystemExit('YOUTUBE_API_KEY is required in the environment.')
catalog_path = HERE / 'data/catalog.js'
catalog = json.loads(catalog_path.read_text(encoding='utf-8').removeprefix('window.RESEARCH_DATA = ').strip().rstrip(';'))
observed = datetime.now(JST).date().isoformat()
requests = 0

def get(resource, params):
    global requests
    if requests >= 30:
        raise SystemExit('30-request cap reached. No retries.')
    requests += 1
    try:
        with urlopen('https://www.googleapis.com/youtube/v3/' + resource + '?' + urlencode({**params, 'key': KEY}), timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f'YouTube HTTP {error.code}. Stopped without retry.') from None
    except (URLError, TimeoutError):
        raise SystemExit('Network error. Stopped without retry.') from None

def chunks(values):
    for i in range(0, len(values), 50):
        yield values[i:i+50]

def seconds(value):
    match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value)
    return sum(int(n or 0) * f for n, f in zip(match.groups(), (3600, 60, 1))) if match else 0

TOPIC_WORDS = [
    ('auto', ['EV', 'BYD', '自動車', 'ベンツ', 'スズキ', 'トヨタ', '日本車']),
    ('infra', ['ダム', '鉄道', '橋', '工事', '建設', '洪水']),
    ('industry', ['コマツ', '小松', '工場', '技術', '半導体', '撤退', 'エアコン', '企業']),
    ('resources', ['レアアース', 'タングステン', '資源', '輸出', '貿易', 'CPTPP']),
    ('economy', ['GDP', '借金', '銀行', '預金', '経済', 'ゴースト', '不動産', '失業']),
]

cache_path = HERE/'data_sources'/f'direct_{observed}.json'
cached = json.loads(cache_path.read_text(encoding='utf-8')) if '--cached' in sys.argv else None
raw_channels = cached['channels'] if cached else get('channels', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(c[0] for c in CHANNELS)})['items']
channel_by_id = {c['id']: c for c in raw_channels}
if len(channel_by_id) != len(CHANNELS):
    raise SystemExit('Some selected channels were not returned. Kept original catalog.')
selected = {c[0] for c in CHANNELS}
existing = {v['id']: v for v in catalog['videos']}
ids = {v['id'] for v in existing.values() if v.get('channelId') in selected}
for cid, _, _, _ in ([] if cached else CHANNELS):
    playlist = channel_by_id[cid]['contentDetails']['relatedPlaylists']['uploads']
    items = get('playlistItems', {'part': 'contentDetails', 'playlistId': playlist, 'maxResults': 50})['items']
    ids.update(item['contentDetails']['videoId'] for item in items)
raw_videos = list(cached['videos']) if cached else []
for batch in ([] if cached else chunks(sorted(ids))):
    raw_videos.extend(get('videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(batch), 'hl': 'ja'})['items'])
snapshot = {'observed': observed, 'channels': raw_channels, 'videos': raw_videos, 'list_requests': requests, 'paid_calls': 0, 'scope': 'latest 50 uploads per selected channel plus cached selected videos'}
(HERE/'data_sources').mkdir(exist_ok=True)
if not cached:
    cache_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')

old_channel_by_id = {c['id']: c for c in catalog['channels'] if c['id']}
result_channels = []
for priority, (cid, alias, role, reason) in enumerate(CHANNELS):
    c = channel_by_id[cid]
    result_channels.append({**old_channel_by_id.get(cid, {}), 'id': cid, 'name': c['snippet']['title'], 'alias': alias, 'role': role, 'priority': priority, 'reason': reason, 'url': f'https://www.youtube.com/channel/{cid}', 'subscribers': int(c['statistics']['subscriberCount']) if 'subscriberCount' in c['statistics'] else None, 'subscribersObserved': observed})
by_channel_id = {c['id']: c for c in result_channels}
result = {}
for v in raw_videos:
    s = v['snippet']; cid = s['channelId']; length = seconds(v['contentDetails']['duration'])
    if cid not in by_channel_id or length <= 180 or s.get('liveBroadcastContent') != 'none':
        continue
    old = existing.get(v['id'], {})
    views = int(v['statistics']['viewCount']) if 'viewCount' in v.get('statistics', {}) else None
    history = list(old.get('observations', []))
    if old.get('observed') and old['observed'] != observed and old.get('views') is not None:
        history.append({'date': old['observed'], 'views': old['views']})
    history = sorted({h['date']: h for h in history if h['date'] < observed}.values(), key=lambda h: h['date'])
    title = s.get('localized', {}).get('title', s['title'])
    row = {**old, 'id': v['id'], 'title': title, 'channel': by_channel_id[cid]['name'], 'channelId': cid, 'published': s['publishedAt'][:10], 'views': views, 'seconds': length, 'observed': observed, 'role': by_channel_id[cid]['role'], 'observations': history, 'thumbnailText': old.get('thumbnailText', []), 'topic': old.get('topic', 'diplomacy'), 'entities': old.get('entities', []), 'compilation': bool(re.search('総集編|まとめ', title))}
    row['topic'] = next((key for key, words in TOPIC_WORDS if any(word.lower() in title.lower() for word in words)), 'diplomacy')
    row['entities'] = sorted(set(old.get('entities', []) + [e['id'] for e in catalog['entities'] if e['name'].lower() in title.lower()]))
    for field in ('viewDelta', 'deltaFrom', 'deltaPerDay', 'relativeViews'):
        row.pop(field, None)
    days = max(1, (datetime.fromisoformat(observed) - datetime.fromisoformat(row['published'])).days)
    row['viewsPerDay'] = round(views/days) if views is not None else None
    if history and views is not None:
        previous = history[-1]; delta = views-previous['views']
        elapsed = (datetime.fromisoformat(observed)-datetime.fromisoformat(previous['date'])).days
        row.update(viewDelta=delta, deltaFrom=previous['date'], deltaPerDay=round(delta/elapsed) if delta >= 0 and elapsed > 0 else None)
    result[row['id']] = row

# Preserve existing source material behind an explicit role filter. Low-priority
# comparison channels from the older study are format references, not direct rivals.
for c in catalog['channels']:
    if c.get('id') not in selected:
        c = {**c, 'role': 'source' if c['role'] == 'source' else 'reference', 'priority': 100}
        result_channels.append(c)
        for v in existing.values():
            if v['channel'] == c['name']:
                result[v['id']] = {**v, 'role': c['role']}
for c in result_channels:
    items = [v for v in result.values() if v['channel'] == c['name'] and not v['compilation']]
    values = [v['views'] for v in items if v['views'] is not None]
    median = statistics.median(values) if values else None
    c.update(sampleSize=len(items), medianViews=median, hits100k=sum(n >= 100000 for n in values), observed=max((v['observed'] for v in items), default=None))
    for v in items:
        v['relativeViews'] = round(v['views']/median, 2) if v['views'] is not None and median else None
catalog.update(built=observed, videos=list(result.values()), channels=result_channels, directScope={'observed': observed, 'latestUploadsPerChannel': 50, 'channelCount': 7, 'excluded': ['Japan応援隊', 'じゃぱん応援隊'], 'note': '直近50投稿と既存収録を統合。180秒以下・ライブを除く。全動画の網羅取得ではありません。'})
catalog['sources'].append({'label': 'YouTube Data API public metadata / seven selected channels / latest 50 uploads plus existing videos', 'date': observed})
encoded = json.dumps(catalog, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
catalog_path.write_text('window.RESEARCH_DATA = ' + encoded + ';\n', encoding='utf-8')
print(json.dumps({'observed': observed, 'direct_channels': [{'name': c['name'], 'videos': c['sampleSize']} for c in result_channels[:7]], 'catalog_videos': len(result), 'list_requests': requests, 'paid_calls': 0}, ensure_ascii=True))
