"""BigQuery mirror transport. SQL is never used.

--pull: free table preview reads and metadata, joined locally.
--plan: local-only import manifest (default).
--push: storage-cost approval required; refuses other datasets and row loss.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime
from common import ROOT, WAREHOUSE, config, read, write, table, now, validate_scope, credentials

KEYS={'channels':['channel_id'],'videos':['video_id'],'videos_archive':['video_id'],'channel_snapshots':['channel_id','snapshot_date','source'],'video_snapshots':['video_id','snapshot_date','source'],'thumbnail_assets':['video_id'],'script_assets':['video_id'],'thumbnail_ocr':['video_id'],'youtube_metadata_update_runs':['run_id']}

def authorize(scope):
    path=os.environ.get('ZUNDA_COST_APPROVAL_FILE','')
    approval=read(__import__('pathlib').Path(path)) if path else None
    if not approval or not approval.get('explicit_user_approval'):
        raise RuntimeError('Explicit cost approval file is required. No cloud writes performed.')
    if scope not in approval.get('scopes',[]):raise RuntimeError('This operation is outside the approved scopes.')
    if approval.get('project')!=config()['project'] or approval.get('dataset')!='zunda_all':raise RuntimeError('Approval target mismatch.')
    if approval.get('valid_until','')<now()[:10]:raise RuntimeError('Cost approval expired.')
    if approval.get('total_cap_jpy',0)<=0:raise RuntimeError('A positive JPY cap is required.')
    return approval

def manifest():
    cfg=config(); schemas=read(ROOT/'backend/schemas.json'); rows=[]
    for name in schemas:
        data=table(name)
        if name in ('channels','videos','videos_archive'):validate_scope(data)
        keys=KEYS[name]; unique={tuple(r.get(k) for k in keys) for r in data}
        if len(unique)!=len(data):raise ValueError('Duplicate natural keys in '+name)
        path=WAREHOUSE/(name+'.json');content=path.read_bytes() if path.exists() else b'[]'
        rows.append({'table':name,'rows':len(data),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    total=sum(r['bytes'] for r in rows)
    if total>50*1024*1024:raise ValueError('Warehouse exceeds initial 50 MiB storage limit.')
    result={'project':cfg['project'],'dataset':cfg['dataset'],'location':cfg['location'],'total_bytes':total,'tables':rows,'sql_jobs':0,'storage_approval_required':True}
    write(ROOT/'reports/cloud_import_plan.json',result);return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pull',action='store_true');parser.add_argument('--push',action='store_true');args=parser.parse_args()
    cfg=config()
    if cfg['dataset']!='zunda_all':raise RuntimeError('Refusing to access another dataset.')
    if not args.pull and not args.push:print(json.dumps(manifest(),ensure_ascii=True,indent=2));return
    if args.push:approval=authorize('bigquery_storage')
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound
    client=bigquery.Client(project=cfg['project'],credentials=credentials());dataset_id=cfg['project']+'.'+cfg['dataset']
    if args.pull:
        schemas=read(ROOT/'backend/schemas.json');downloaded=[]
        # Stage all reads before replacing any local warehouse file.
        staging={}
        for name in schemas:
            try:
                meta=client.get_table(dataset_id+'.'+name)
                if meta.num_bytes>50*1024*1024 or meta.num_rows>200000:raise RuntimeError('Free preview transfer cap exceeded.')
                staging[name]=[dict(r) for r in client.list_rows(meta,page_size=10000)]
            except NotFound:raise RuntimeError('BigQuery is not provisioned; original local warehouse retained.') from None
        for name,rows in staging.items():write(WAREHOUSE/(name+'.json'),rows);downloaded.append({'table':name,'rows':len(rows)})
        current_videos=table('videos')
        latest_observation=max((r.get('fetched_at','') for r in current_videos),default='')
        successful_runs=[r for r in table('youtube_metadata_update_runs') if not r.get('error_count')]
        if successful_runs:
            write(WAREHOUSE/'collection_status.json',{'observed_at':latest_observation,'listing_complete':True,'listed_channels':[c['channel_id'] for c in table('channels')],'returned_video_ids':[r['video_id'] for r in current_videos if r.get('fetched_at')==latest_observation],'source':'verified_bigquery_run_log_and_observation_timestamp'})
        write(ROOT/'reports/bq_pull.json',{'observed_at':now(),'method':'list_rows only; no SQL','tables':downloaded})
        write(ROOT/'reports/cloud_receipt.json',{'verified':True,'observed_at':now(),'project':cfg['project'],'dataset':cfg['dataset'],'tables':downloaded,'method':'list_rows; no SQL'})
        print(json.dumps({'pulled':downloaded,'query_jobs':0}));return
    plan=manifest();schemas=read(ROOT/'backend/schemas.json')
    if plan['total_bytes']>approval.get('max_bq_bytes',0):raise RuntimeError('Approved BQ storage cap would be exceeded.')
    dataset=bigquery.Dataset(dataset_id);dataset.location=cfg['location'];client.create_dataset(dataset,exists_ok=True)
    loaded=[]
    for item in plan['tables']:
        name=item['table'];data=table(name);target=dataset_id+'.'+name
        fields=[bigquery.SchemaField.from_api_repr(f) for f in schemas[name]]
        try:
            prior=client.get_table(target)
            existing=[dict(r) for r in client.list_rows(prior,page_size=10000)]
            required={tuple(r.get(k) for k in KEYS[name]) for r in existing}
            incoming={tuple(r.get(k) for k in KEYS[name]) for r in data}
            if required-incoming:raise RuntimeError('Cloud rows would be lost; pull before collecting: '+name)
        except NotFound:
            client.create_table(bigquery.Table(target,schema=fields))
        # Batch loads have no ingestion processing fee. Stored bytes are billable.
        if data:
            job=client.load_table_from_json(data,target,num_retries=0,job_config=bigquery.LoadJobConfig(schema=fields,write_disposition='WRITE_TRUNCATE'))
            job.result(timeout=180)
        meta=client.get_table(target)
        if meta.num_rows!=len(data):raise RuntimeError('Post-load count mismatch: '+name)
        loaded.append({'table':name,'rows':meta.num_rows,'logical_bytes':meta.num_bytes})
    receipt={'verified':True,'observed_at':now(),'project':cfg['project'],'dataset':cfg['dataset'],'tables':loaded,'approval_task_id':approval['task_id'],'query_jobs':0}
    write(ROOT/'reports/cloud_receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=True))

if __name__=='__main__':main()
