"""Serve immutable thumbnail copies with Pages; bound all GCS reads.

Initial copies reuse local originals. Later updates download at most 20 missing
objects per run, <=600 MiB total over the approved 30 days. Readers of the public
site fetch images from GitHub Pages, never from billable GCS URLs.
"""
import argparse
import hashlib
import json
import shutil
from common import ROOT, config, read, write, table, now, credentials

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed-local',action='store_true');args=parser.parse_args()
    cfg=config();folder=ROOT/'assets/thumbnails';folder.mkdir(parents=True,exist_ok=True)
    registry={r['video_id'] for r in table('videos') if r['channel_id'] in {c['channel_id'] for c in cfg['channels']}}
    inventory=read(ROOT/'data/thumbnail_manifest.json',{})
    if args.seed_local:
        for row in read(ROOT/'reports/thumbnail_manifest.json',[]):
            vid=row['video_id']
            if vid not in registry:raise RuntimeError('Unregistered thumbnail.')
            source=ROOT/'data_sources/assets/thumbnails'/(vid+'.jpg')
            if hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Source checksum mismatch.')
            shutil.copy2(source,folder/(vid+'.jpg'));inventory[vid]={'sha256':row['sha256'],'bytes':row['bytes']}
    else:
        policy=read(ROOT/'backend/public_delivery_policy.json')
        if now()[:10]>policy['valid_until']:raise RuntimeError('Approved GCS transfer period expired.')
        from google.cloud import storage
        client=storage.Client(project=cfg['project'],credentials=credentials());bucket=client.bucket(cfg['bucket'])
        # Verify a changed archive endpoint once under the actual CI identity.
        # Metadata alone confirms access and the stored checksum; no image data
        # transfer is needed for this connection check.
        verified=read(ROOT/'data/archive_access_verified.json',{})
        if verified.get('bucket')!=cfg['bucket'] and inventory:
            vid=sorted(inventory)[0];blob=bucket.blob(cfg['gcs_prefix']+'/thumbnails/'+vid+'.jpg');blob.reload(retry=None,timeout=30)
            if blob.size!=inventory[vid]['bytes'] or (blob.metadata or {}).get('sha256')!=inventory[vid]['sha256']:raise RuntimeError('Archive access/checksum check failed.')
            write(ROOT/'data/archive_access_verified.json',{'bucket':cfg['bucket'],'video_id':vid,'sha256_matches':True,'checked_at':now(),'method':'one metadata GET under CI reader; no image transfer'})
        ledger=read(ROOT/'data/thumbnail_delivery_ledger.json',{'reserved_download_bytes':0,'attempts':[]})
        failed={r['video_id'] for r in ledger['attempts'] if r.get('status')=='failed'}
        missing=[r for r in table('thumbnail_assets') if r['video_id'] in registry and r['video_id'] not in inventory and r['video_id'] not in failed and r.get('gcs_uri') and not r.get('error')]
        for row in missing[:policy['max_objects_per_run']]:
            vid=row['video_id'];maximum=policy['max_object_bytes']
            if row.get('bytes',0)>maximum:continue
            if ledger['reserved_download_bytes']+maximum>policy['max_download_bytes_total']:break
            attempt={'at':now(),'video_id':vid,'reserved_bytes':maximum,'status':'reserved_before_request'}
            ledger['attempts'].append(attempt);ledger['reserved_download_bytes']+=maximum
            write(ROOT/'data/thumbnail_delivery_ledger.json',ledger)
            blob=bucket.blob(cfg['gcs_prefix']+'/thumbnails/'+vid+'.jpg')
            try:
                blob.reload(retry=None,timeout=30)
                data=blob.download_as_bytes(retry=None,timeout=45,if_generation_match=blob.generation)
                digest=hashlib.sha256(data).hexdigest()
                if len(data)>maximum or (blob.metadata or {}).get('sha256')!=digest:raise RuntimeError('GCS checksum/size mismatch.')
                (folder/(vid+'.jpg')).write_bytes(data);inventory[vid]={'sha256':digest,'bytes':len(data)};attempt.update(status='verified',bytes=len(data))
            except Exception as error:
                attempt.update(status='failed',error=type(error).__name__);write(ROOT/'data/thumbnail_delivery_ledger.json',ledger);break
            write(ROOT/'data/thumbnail_delivery_ledger.json',ledger)
    total=sum(r['bytes'] for r in inventory.values())
    if total>800*1024*1024:raise RuntimeError('Pages asset storage cap reached.')
    write(ROOT/'data/thumbnail_manifest.json',inventory)
    print(json.dumps({'public_thumbnail_copies':len(inventory),'bytes':total,'public_delivery':'GitHub Pages; no visitor requests to GCS','seed_from_local':args.seed_local}))

if __name__=='__main__':main()
