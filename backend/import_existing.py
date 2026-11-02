"""Import previously saved observations and OCR, without new analysis."""
import json
from common import ROOT, config, table, upsert, read

catalog=json.loads((ROOT/'data/catalog.js').read_text(encoding='utf-8').removeprefix('window.RESEARCH_DATA = ').strip().rstrip(';'))
allowed={c['channel_id'] for c in config()['channels']};known={v['video_id'] for v in table('videos')};snapshots=[];ocr=[]
schemas=read(ROOT/'backend/schemas.json')
for v in catalog['videos']:
    if v.get('channelId') not in allowed or v['id'] not in known:continue
    for h in v.get('observations',[]):
        row={f['name']:None for f in schemas['video_snapshots']}
        row.update(video_id=v['id'],snapshot_date=h['date'][:10],view_count=h['views'],source='imported_saved_observation',created_at=h['date'])
        snapshots.append(row)
    if v.get('thumbnailText'):
        row={f['name']:None for f in schemas['thumbnail_ocr']}
        row.update(video_id=v['id'],combined_text=' / '.join(v['thumbnailText']),analyzed_at='2026-09-17',notes='Reused saved OCR; no new OCR call.',error='')
        ocr.append(row)
upsert('video_snapshots',snapshots,['video_id','snapshot_date','source']);upsert('thumbnail_ocr',ocr,['video_id'])
print(json.dumps({'historical_observations_imported':len(snapshots),'existing_ocr_imported':len(ocr),'paid_calls':0}))
