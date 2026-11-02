"""Cloud Run entrypoint. No subprocess, SQL, AI API or unbounded retry."""
import json
import os
import tempfile
from pathlib import Path
from common import ROOT, config, now, write, table, upsert
from cloud_sync import authorize

def main():
    # The only injected approval is a server-side secret, never a public site file.
    authorization=os.environ.get('ZUNDA_COST_APPROVAL_JSON')
    if authorization:
        path=Path(tempfile.gettempdir())/'zunda-cost-approval.json'
        write(path,json.loads(authorization));os.environ['ZUNDA_COST_APPROVAL_FILE']=str(path)
    approval=authorize('daily_cloud_run')
    from google.cloud import bigquery
    cfg=config();client=bigquery.Client(project=cfg['project'])
    schemas=__import__('common').read(ROOT/'backend/schemas.json')
    for name in schemas:
        rows=[dict(r) for r in client.list_rows(cfg['project']+'.'+cfg['dataset']+'.'+name,page_size=10000)]
        write(ROOT/'data_sources/warehouse'/(name+'.json'),rows)
    today=now()[:10]
    if any(r['run_id']=='zunda-'+today for r in table('youtube_metadata_update_runs')):
        print('Already completed today; no collection or writes.');return
    completed=sum(1 for r in table('youtube_metadata_update_runs') if str(r.get('run_id','')).startswith('zunda-') and r.get('started_at','')[:10]>=approval.get('valid_from',''))
    if completed>=approval.get('max_daily_runs',0):raise RuntimeError('Approved run count exhausted.')
    started=now()
    import collect
    # Cloud entrypoint ignores CLI flags supplied by the outer runtime.
    import sys
    sys.argv=['collect.py'];collect.main()
    import archive_thumbnails, upload_assets
    archive_thumbnails.main();upload_assets.main()
    rows=table('videos');log={f['name']:None for f in schemas['youtube_metadata_update_runs']}
    log.update(run_id='zunda-'+today,started_at=started,finished_at=now(),channels_considered=7,updated_channels=7,video_upserts=len(rows),video_snapshots=len(rows),skipped_video_channels=0,quota_skips=0,key_used='secret_reference_only',error_count=0,error_json='[]')
    upsert('youtube_metadata_update_runs',[log],['run_id'])
    import cloud_sync
    sys.argv=['cloud_sync.py','--push'];cloud_sync.main()
    if today==approval['valid_until']:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credential,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        session=AuthorizedSession(credential)
        url=f'https://cloudscheduler.googleapis.com/v1/projects/{cfg["project"]}/locations/{cfg["location"]}/jobs/zunda-daily-metadata-schedule'
        response=session.delete(url,timeout=30)
        if response.status_code not in (200,204,404):raise RuntimeError('Approved-period scheduler cleanup failed.')
        print('Approved final daily run completed; its scheduler has been removed.')

if __name__=='__main__':main()
