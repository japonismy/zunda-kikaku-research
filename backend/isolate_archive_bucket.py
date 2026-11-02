"""Move this task's archive to enforced-private storage, four objects at a time.

Only exact IDs from this task's verified manifest may be moved. Every source
generation is checked, each copy is size/CRC/SHA verified before source removal.
"""
import concurrent.futures
import json
from common import ROOT, config, credentials, read, write, table, upsert, now
from cloud_sync import authorize

def main():
    authorize('gcs_storage');cfg=config()
    from google.cloud import storage
    from google.api_core.exceptions import NotFound
    client=storage.Client(project=cfg['project'],credentials=credentials())
    source_name='senior-share-staging-570862915709';destination_name='zunda-research-private-570862915709'
    source=client.bucket(source_name)
    destination=client.bucket(destination_name)
    try:destination.reload(retry=None)
    except NotFound:
        destination.iam_configuration.uniform_bucket_level_access_enabled=True
        destination.iam_configuration.public_access_prevention='enforced'
        destination.storage_class='STANDARD'
        destination=client.create_bucket(destination,location=cfg['location'],retry=None)
    if destination.iam_configuration.public_access_prevention!='enforced':raise RuntimeError('Private bucket enforcement missing.')
    policy=destination.get_iam_policy(requested_policy_version=3,retry=None)
    bindings=list(policy.bindings)
    for short,role in (('zunda-research-runner','roles/storage.objectUser'),('zunda-site-reader','roles/storage.objectViewer')):
        member=f'serviceAccount:{short}@{cfg["project"]}.iam.gserviceaccount.com'
        if not any(b['role']==role and member in b['members'] for b in bindings):bindings.append({'role':role,'members':{member}})
    policy.bindings=bindings;destination.set_iam_policy(policy,retry=None)
    wanted=read(ROOT/'data/thumbnail_manifest.json');prefix=cfg['gcs_prefix']+'/thumbnails/'
    blobs=list(client.list_blobs(source,prefix=prefix,page_size=1000,max_results=3000,retry=None))
    if any(b.name[len(prefix):-4] not in wanted for b in blobs):raise RuntimeError('Unexpected object in task prefix; no migration started.')
    old=read(ROOT/'reports/private_bucket_migration.json',{'objects':[]})
    completed={r['video_id']:r for r in old['objects']}
    def move(blob):
        vid=blob.name[len(prefix):-4];expected=wanted[vid]
        if blob.size!=expected['bytes'] or (blob.metadata or {}).get('sha256')!=expected['sha256']:raise RuntimeError('Source manifest mismatch.')
        copied=source.copy_blob(blob,destination,new_name=blob.name,if_generation_match=0,if_source_generation_match=int(blob.generation),retry=None,timeout=60)
        if copied.size!=blob.size or copied.crc32c!=blob.crc32c or (copied.metadata or {}).get('sha256')!=expected['sha256']:raise RuntimeError('Copied object verification failed; original retained.')
        blob.delete(if_generation_match=int(blob.generation),retry=None,timeout=30)
        return {'video_id':vid,'bytes':blob.size,'sha256':expected['sha256'],'gcs_uri':f'gs://{destination_name}/{blob.name}','error':''}
    for start in range(0,len(blobs),4):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(move,blobs[start:start+4]))
        for row in results:completed[row['video_id']]=row
        if len(completed)%100<4 or start+4>=len(blobs):
            write(ROOT/'reports/private_bucket_migration.json',{'at':now(),'source_bucket':source_name,'destination_bucket':destination_name,'objects':list(completed.values()),'public_access_prevention':'enforced','active_copy_count_limit':4,'source_soft_delete_days':7})
            print(json.dumps({'migrated_verified':len(completed),'total':len(wanted)}),flush=True)
    if set(completed)!=set(wanted):raise RuntimeError('Incomplete manifest; config retained.')
    upsert('thumbnail_assets',[{k:r[k] for k in ('video_id','gcs_uri','bytes','error')} for r in completed.values()],['video_id'])
    cfg['bucket']=destination_name;write(ROOT/'backend/config.json',cfg)
    print(json.dumps({'private_bucket':destination_name,'objects':len(completed),'bytes':sum(r['bytes'] for r in completed.values()),'pap':'enforced'}))

if __name__=='__main__':main()
