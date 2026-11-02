"""Update archive configuration on the existing immutable image; no new build."""
import json
import time
from urllib.request import Request, urlopen
from common import ROOT, config, credentials, write, now
from cloud_sync import authorize

def main():
    authorize('daily_cloud_run');cfg=config();token=credentials().token
    if cfg['bucket']!='zunda-research-private-570862915709':raise RuntimeError('Private archive migration is not complete.')
    def call(method,url,data=None):
        with urlopen(Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=40) as response:
            body=response.read();return json.loads(body) if body else {}
    resource=f'projects/{cfg["project"]}/locations/{cfg["location"]}/jobs/zunda-daily-metadata'
    base='https://run.googleapis.com/v2/';job=call('GET',base+resource)
    original=job['template']['template']['containers'][0]
    container={k:original[k] for k in ('name','image','env','resources','volumeMounts','workingDir') if k in original}
    env=[e for e in container.get('env',[]) if e['name']!='ZUNDA_ARCHIVE_BUCKET']
    env.append({'name':'ZUNDA_ARCHIVE_BUCKET','value':cfg['bucket']});container['env']=env
    # This is configuration-only initialization of the already built program.
    # Secret values remain server-side references. No extra execution is started.
    code='import json,os,sys;from pathlib import Path;sys.path.insert(0,"/app/backend");p=Path("/app/backend/config.json");c=json.loads(p.read_text());c["bucket"]=os.environ["ZUNDA_ARCHIVE_BUCKET"];p.write_text(json.dumps(c));import run_daily;run_daily.main()'
    container['command']=['python'];container['args']=['-c',code]
    payload={k:job[k] for k in ('name','etag','labels','annotations','binaryAuthorization','launchStage','client','clientVersion','template','functionalType') if k in job}
    payload['template']['template']['containers']=[container]
    # Run v2 Job PATCH replaces the writable configuration and has no field mask.
    # Preserve the complete existing task limits, identity and secret references;
    # never send runExecutionToken/startExecutionToken, which could execute work.
    operation=call('PATCH',base+resource,payload)
    for _ in range(30):
        result=call('GET',base+operation['name'])
        if result.get('done'):break
        time.sleep(1)
    if not result.get('done') or result.get('error'):raise RuntimeError('Runtime configuration update failed.')
    verified=call('GET',base+resource)['template']['template']['containers'][0]
    if not any(e.get('value')==cfg['bucket'] and e['name']=='ZUNDA_ARCHIVE_BUCKET' for e in verified.get('env',[])):raise RuntimeError('Runtime archive setting did not persist.')
    write(ROOT/'reports/private_runtime_update.json',{'at':now(),'job':resource,'bucket':cfg['bucket'],'same_image':verified['image']==original['image'],'new_execution_started':False,'configuration_bootstrap':'sets archive bucket before invoking the verified daily program'})
    print(json.dumps({'private_bucket':cfg['bucket'],'same_image':verified['image']==original['image'],'new_execution_started':False}))

if __name__=='__main__':main()
