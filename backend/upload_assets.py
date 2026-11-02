"""GCS thumbnail backup, explicit storage approval and bounded object count."""
import hashlib
import json
import concurrent.futures
import argparse
from common import ROOT, config, read, write, table, upsert, now, credentials
from cloud_sync import authorize

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='*');args=parser.parse_args()
    approval=authorize('gcs_storage');cfg=config()
    from google.cloud import storage
    manifest=read(ROOT/'reports/thumbnail_manifest.json',[])
    if args.only:
        selected=set(args.only);manifest=[r for r in manifest if r['video_id'] in selected]
        if {r['video_id'] for r in manifest}!=selected:raise RuntimeError('Selected asset not in verified local manifest.')
    current={r['video_id']:r for r in table('thumbnail_assets')}
    combined={**current,**{r['video_id']:r for r in manifest}}
    if len(combined)>approval.get('max_gcs_objects',0):raise RuntimeError('Object count exceeds approval.')
    if sum(r.get('bytes',0) for r in combined.values())>approval.get('max_gcs_bytes',0):raise RuntimeError('Object bytes exceed approval.')
    client=storage.Client(project=cfg['project'],credentials=credentials());bucket=client.bucket(cfg['bucket']);rows=[]
    def upload(row):
        vid=row['video_id'];path=ROOT/'data_sources/assets/thumbnails'/(vid+'.jpg')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Local checksum mismatch before upload.')
        name=cfg['gcs_prefix']+'/thumbnails/'+vid+'.jpg';blob=bucket.blob(name)
        # One upload per file, no retries; generations prevent accidental overwrite.
        # Existing verified objects are reused. IAM and bucket ACL are not changed.
        if blob.exists(retry=None):
            blob.reload(retry=None)
            if blob.metadata and blob.metadata.get('sha256')==row['sha256']:
                return {'video_id':vid,'gcs_uri':f'gs://{cfg["bucket"]}/{name}','bytes':row['bytes'],'error':''}
            raise RuntimeError('Existing GCS asset has different or unknown checksum: '+vid)
        blob.metadata={'sha256':row['sha256'],'task_id':approval['task_id']}
        blob.upload_from_filename(str(path),content_type='image/jpeg',if_generation_match=0,retry=None,timeout=60)
        return {'video_id':vid,'gcs_uri':f'gs://{cfg["bucket"]}/{name}','bytes':row['bytes'],'error':''}
    # Keep only four requests in flight. Stop scheduling immediately after any
    # failure; persist successful rows so a resumed run can reuse each object.
    iterator=iter(manifest)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(upload,row) for row in [next(iterator,None) for _ in range(4)] if row}
        while pending:
            done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                try:rows.append(future.result())
                except Exception:
                    for future_to_cancel in pending:future_to_cancel.cancel()
                    upsert('thumbnail_assets',rows,['video_id'])
                    raise
                if len(rows)%100==0:
                    upsert('thumbnail_assets',rows,['video_id'])
                    print(json.dumps({'verified_or_uploaded':len(rows),'total':len(manifest)}),flush=True)
                row=next(iterator,None)
                if row:pending.add(pool.submit(upload,row))
    upsert('thumbnail_assets',rows,['video_id'])
    write(ROOT/'reports/gcs_receipt.json',{'observed_at':now(),'objects':len(rows),'bytes':sum(r['bytes'] for r in rows),'approval_task_id':approval['task_id'],'public_iam_changed':False})
    print(json.dumps({'uploaded_or_verified':len(rows),'bytes':sum(r['bytes'] for r in rows)}))

if __name__=='__main__':main()
