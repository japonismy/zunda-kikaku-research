"""Preserve public thumbnails locally; GCS upload is a separate approved step."""
import concurrent.futures
import hashlib
import json
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from common import ROOT, table, upsert, read, write, config, now

def main():
    folder=ROOT/'data_sources/assets/thumbnails';folder.mkdir(parents=True,exist_ok=True)
    videos=[v for v in table('videos') if (v.get('duration_sec') or 0)>=config()['min_duration_seconds']]
    existing={r['video_id']:r for r in table('thumbnail_assets')}
    total=sum(p.stat().st_size for p in folder.glob('*.jpg'))
    if total>1024*1024*1024:raise RuntimeError('Local archive exceeds the 1 GiB staging limit.')
    def archive(video):
        vid=video['video_id'];p=folder/(vid+'.jpg')
        if p.exists():return {**existing.get(vid,{}),'video_id':vid,'gcs_uri':existing.get(vid,{}).get('gcs_uri',''),'bytes':p.stat().st_size,'error':''}
        if existing.get(vid,{}).get('gcs_uri'):return existing[vid]
        if existing.get(vid,{}).get('error'):return existing[vid]
        url=video.get('thumbnail_url_max') or f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'
        try:
            with urlopen(url,timeout=20) as response:
                data=response.read(1024*1024+1)
            if len(data)>1024*1024:raise ValueError('thumbnail_exceeds_1MiB')
            if not (data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG')):raise ValueError('not_an_image')
            p.write_bytes(data)
            return {'video_id':vid,'gcs_uri':'','bytes':len(data),'error':''}
        except (HTTPError,URLError,TimeoutError,ValueError) as e:
            return {'video_id':vid,'gcs_uri':'','bytes':0,'error':type(e).__name__}
    rows=[]
    # Small worker pool; each source gets one attempt and no conditional retry.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(archive,videos):rows.append(row)
    total=sum(r['bytes'] for r in rows)
    if total>1024*1024*1024:raise RuntimeError('Staging is over the planned cloud storage cap. No upload performed.')
    upsert('thumbnail_assets',rows,['video_id'])
    checksums=[{'video_id':r['video_id'],'bytes':r['bytes'],'sha256':hashlib.sha256((folder/(r['video_id']+'.jpg')).read_bytes()).hexdigest()} for r in rows if r['bytes'] and (folder/(r['video_id']+'.jpg')).exists()]
    write(ROOT/'reports/thumbnail_manifest.json',checksums)
    summary={'observed_at':now(),'saved':sum(not r.get('error') and r.get('bytes',0)>0 for r in rows),'already_in_gcs':sum(bool(r.get('gcs_uri')) for r in rows),'local_files':len(checksums),'failed':sum(bool(r.get('error')) for r in rows),'bytes':total,'paid_calls':0,'location':str(folder)}
    write(ROOT/'reports/thumbnail_archive.json',summary);print(json.dumps(summary,ensure_ascii=True))

if __name__=='__main__':main()
