"""Same static display contract as Naresome, joined locally from BQ mirrors."""
import json
from collections import Counter
from datetime import datetime
from common import ROOT, config, table, read, write, now, validate_scope, upsert

def js(name, variable, rows):
    data=json.dumps(rows,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    (ROOT/'data'/name).write_text(f'window.{variable} = '+data+';\n',encoding='utf-8')

def public_asset(uri):
    # GCS backups stay private; publish only explicitly registered public URLs.
    return ''

def build():
    cfg=config(); registry=cfg['channels']; allowed={c['channel_id'] for c in registry}
    channels=table('channels'); current=table('videos'); validate_scope(channels); validate_scope(current)
    channel_map={c['channel_id']:c for c in channels}
    rows={v['video_id']:{**v,'source_type':'archive'} for v in table('videos_archive') if v['channel_id'] in allowed}
    rows.update({v['video_id']:{**v,'source_type':'current'} for v in current})
    # Keep every historical observation. Missing videos do not disappear.
    snapshots={}
    for s in table('video_snapshots'):snapshots.setdefault(s['video_id'],[]).append(s)
    ocr={r['video_id']:r for r in table('thumbnail_ocr')}; assets={r['video_id']:r for r in table('thumbnail_assets')}; scripts={r['video_id']:r for r in table('script_assets')}
    local_assets=read(ROOT/'data_sources/public_asset_links.json',{})
    for vid in read(ROOT/'data/thumbnail_manifest.json',{}):
        local_assets.setdefault(vid,{})['thumbnail_url']='assets/thumbnails/'+vid+'.jpg'
    prior=json.loads((ROOT/'data/catalog.js').read_text(encoding='utf-8').removeprefix('window.RESEARCH_DATA = ').strip().rstrip(';'))
    # Reuse OCR that already exists; no new image analysis.
    cached={v['id']:v for v in prior['videos']}
    status=read(ROOT/'data_sources/warehouse/collection_status.json',{})
    returned=set(status.get('returned_video_ids',[])); complete=status.get('listing_complete',False)
    result=[]; digests=[]
    for vid,row in rows.items():
        if (row.get('duration_sec') or 0)<cfg['min_duration_seconds']:continue
        cid=row['channel_id']; c=channel_map.get(cid,{}); history=sorted(snapshots.get(vid,[]),key=lambda s:s.get('created_at',''))
        text=' '.join(dict.fromkeys(str(ocr.get(vid,{}).get(f) or '').strip() for f in ('combined_text','emphasis_text','narration_text','dialogue_text','top_upper_text','top_lower_text','center_text','bottom_upper_text','bottom_lower_text'))).strip()
        if not text:text=' / '.join(cached.get(vid,{}).get('thumbnailText',[]))
        saved=local_assets.get(vid,{}); ta=assets.get(vid,{}); sa=scripts.get(vid,{})
        item={'video_id':vid,'channel_id':cid,'channel':c.get('title',cid),'title':row.get('title',''),'published_at':row.get('published_at',''),'duration_sec':row.get('duration_sec'),'view_count':row.get('view_count'),'like_count':row.get('like_count'),'comment_count':row.get('comment_count'),'thumbnail_url':row.get('thumbnail_url_max',''),'thumbnail_gcs_uri':'','thumbnail_saved_url':saved.get('thumbnail_url',''),'thumbnail_max_url':f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg','thumbnail_fallback_urls':[saved.get('thumbnail_url',''),row.get('thumbnail_url_max',''),f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'],'youtube_url':f'https://www.youtube.com/watch?v={vid}','fetched_at':row.get('fetched_at',''),'thumbnail_text':text,'thumbnail_analysis':{},'script_asset_available':bool(sa.get('asset_count')),'script_gcs_uri':'','script_csv_url':saved.get('script_csv_url',sa.get('public_csv_url','')),'tags':json.loads(row.get('tags') or '[]'),'relation_type':'competitor','analysis_status':'active','content_category':'zundamon_world_business_dialogue','watch_scope':'full','scope_type':'monitored_channel','content_flags':[],'default_visible':True,'classification_reason':'直接競合の固定チャンネルID台帳','source_type':row['source_type'],'is_archive':row['source_type']=='archive','archive_type':'stopped_channel_archive' if row['source_type']=='archive' else 'current_monitoring','observed_view_count':row.get('view_count'),'observed_like_count':row.get('like_count'),'observed_comment_count':row.get('comment_count'),'observed_at':row.get('fetched_at',''),'max_observed_view_count':row.get('view_count'),'latest_observed_at':row.get('fetched_at',''),'youtube_availability':'public' if vid in returned else 'unavailable' if complete else 'unknown','availability_checked_at':status.get('observed_at',''),'observation_sources':['youtube_api'],'observation_history':[{'observed_at':s.get('created_at',''),'view_count':s.get('view_count'),'like_count':s.get('like_count'),'comment_count':s.get('comment_count'),'source_name':s.get('source','')} for s in history],'thumbnail_backup_gcs_uri':ta.get('gcs_uri',''),'script_backup_gcs_uri':sa.get('gcs_csv_uri','')}
        result.append(item)
        desc=row.get('description','')
        if desc:digests.append({'video_id':vid,'digest':desc[:1600],'chars':len(desc),'language':'ja','source':'youtube_description','fetched_at':row.get('fetched_at','')})
    result.sort(key=lambda v:v['published_at'],reverse=True)
    output_channels=[]
    for entry in registry:
        cid=entry['channel_id']; c=channel_map.get(cid,{}); videos=[v for v in result if v['channel_id']==cid]
        latest=max((v['published_at'] for v in videos),default=''); day=(status.get('observed_at') or now())[:10]
        inactive=bool(latest and (datetime.fromisoformat(day)-datetime.fromisoformat(latest[:10])).days>cfg['inactive_days'])
        lifecycle='過去競合・現在公開なし' if c.get('video_count')==0 else '過去競合・更新停止' if inactive else '競合・更新あり' if latest else '更新状況未確認'
        output_channels.append({'channel_id':cid,'canonical_channel_id':cid,'channel_name':entry['channel_name'],'portal_channel_name':c.get('title',entry['channel_name']),'db_title':c.get('title',''),'handle':c.get('handle',''),'category':entry['category'],'category_label':'指定ベンチマーク' if entry['category']=='direct_a' else '直接競合','relation_type':'competitor','lifecycle':lifecycle,'subscriber_count':c.get('subscriber_count'),'video_count':c.get('video_count'),'portal_video_count':len(videos),'latest_video':latest,'data_status':'DBデータあり' if read(ROOT/'reports/cloud_receipt.json',{}).get('verified') else 'ローカル保存データあり','match_status':'canonical_channel_id','backup_status':'保存済み' if any(v['thumbnail_saved_url'] for v in videos) else '未保全','history_preserved_count':sum(bool(v['observation_history']) for v in videos),'youtube_channel_title':c.get('title',''),'last_synced_at':c.get('last_synced_at','')})
    (ROOT/'data').mkdir(exist_ok=True)
    js('videos.js','VIDEO_DATA',result);js('channels.js','CHANNEL_DATA',output_channels);js('transcripts_light.js','TRANSCRIPT_DATA',digests)
    receipt=read(ROOT/'reports/cloud_receipt.json',{});label='BigQuery保存値から生成。日次実行の有効化状態は運用記録を参照。' if receipt.get('verified') else '取得・表示は整備済み。BigQuery保存・クラウド日次実行は未接続（費用承認待ち）。'
    js('pipeline_status.js','PIPELINE_STATUS',{'source':'bigquery' if receipt.get('verified') else 'local_warehouse','cloud_connected':bool(receipt.get('verified')),'public_label':label})
    summary={'built_at':now(),'channels':len(output_channels),'videos':len(result),'ocr_reused':sum(bool(v['thumbnail_text']) for v in result),'description_digests':len(digests),'saved_thumbnails':sum(bool(v['thumbnail_saved_url']) for v in result),'script_assets':sum(v['script_asset_available'] for v in result),'source':'bigquery' if receipt.get('verified') else 'local_warehouse','listing_complete':complete,'paid_calls':0}
    write(ROOT/'reports/equivalent_build.json',summary); print(json.dumps(summary,ensure_ascii=True));return result,output_channels

if __name__=='__main__':build()
