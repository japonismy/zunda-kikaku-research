"""One explicit hqdefault attempt for failed max-resolution thumbnail URLs."""
import hashlib
import json
from urllib.request import urlopen
from common import ROOT, table, read, write, upsert, now

def main():
    known={v['video_id']:v for v in table('videos')};rows=[];results=[]
    manifest={r['video_id']:r for r in read(ROOT/'reports/thumbnail_manifest.json',[])}
    candidates=[r for r in table('thumbnail_assets') if r.get('error') and not r.get('gcs_uri')][:10]
    for row in candidates:
        vid=row['video_id'];url=f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'
        if known[vid].get('thumbnail_url_max')==url:continue
        try:
            with urlopen(url,timeout=20) as response:data=response.read(1024*1024+1)
            if len(data)>1024*1024 or not data.startswith(b'\xff\xd8'):raise ValueError('Fallback is not a bounded JPEG.')
            path=ROOT/'data_sources/assets/thumbnails'/(vid+'.jpg');path.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest();manifest[vid]={'video_id':vid,'bytes':len(data),'sha256':digest}
            rows.append({'video_id':vid,'gcs_uri':'','bytes':len(data),'error':''});results.append({'video_id':vid,'status':'recovered','source':url,'sha256':digest,'bytes':len(data)})
        except Exception as error:results.append({'video_id':vid,'status':'unavailable','error':type(error).__name__})
    upsert('thumbnail_assets',rows,['video_id']);write(ROOT/'reports/thumbnail_manifest.json',list(manifest.values()))
    write(ROOT/'reports/thumbnail_fallback_recovery.json',{'at':now(),'results':results,'new_paid_analysis_calls':0})
    print(json.dumps({'results':results,'recovered_ids':[r['video_id'] for r in rows]}))

if __name__=='__main__':main()
