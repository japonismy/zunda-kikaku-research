"""Scope the CI reader to archived images and the runner to its schedule."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common import ROOT, config, credentials, write, now
from cloud_sync import authorize

def main():
    authorize('daily_cloud_run');cfg=config();project=cfg['project'];token=credentials().token
    def request(method,url,data=None,allowed=()):
        try:
            with urlopen(Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=40) as r:
                body=r.read();return json.loads(body) if body else {}
        except HTTPError as e:
            if e.code in allowed:return {'http_status':e.code}
            error=json.loads(e.read()).get('error',{})
            raise RuntimeError(f'HTTP {e.code}: '+error.get('message','')[:700]) from None
    bucket=cfg['bucket'];policy=request('GET',f'https://storage.googleapis.com/storage/v1/b/{bucket}/iam?optionsRequestedPolicyVersion=3')
    member=f'serviceAccount:zunda-site-reader@{project}.iam.gserviceaccount.com';title='zunda_research_readonly_prefix'
    if not any(b.get('condition',{}).get('title')==title for b in policy.get('bindings',[])):
        policy['version']=3;policy.setdefault('bindings',[]).append({'role':'roles/storage.objectViewer','members':[member],'condition':{'title':title,'expression':f'resource.name.startsWith("projects/_/buckets/{bucket}/objects/zunda_research/")'}})
        request('PUT',f'https://storage.googleapis.com/storage/v1/b/{bucket}/iam',policy)
    roleid='zundaScheduleLifecycle';role=f'projects/{project}/roles/{roleid}';url='https://iam.googleapis.com/v1/'+role
    if request('GET',url,allowed=(404,)).get('http_status')==404:
        request('POST',f'https://iam.googleapis.com/v1/projects/{project}/roles',{'roleId':roleid,'role':{'title':'Zunda own schedule cleanup','includedPermissions':['cloudscheduler.jobs.get','cloudscheduler.jobs.delete'],'stage':'GA'}})
    policy=request('POST',f'https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy',{'options':{'requestedPolicyVersion':3}})
    title='zunda_own_schedule_lifecycle';member=f'serviceAccount:zunda-research-runner@{project}.iam.gserviceaccount.com'
    if not any(b.get('condition',{}).get('title')==title for b in policy.get('bindings',[])):
        policy['version']=3;policy.setdefault('bindings',[]).append({'role':role,'members':[member],'condition':{'title':title,'expression':'resource.name.endsWith("/jobs/zunda-daily-metadata-schedule")'}})
        request('POST',f'https://cloudresourcemanager.googleapis.com/v1/projects/{project}:setIamPolicy',{'policy':policy})
    result={'at':now(),'public_image_requests_to_gcs':False,'ci_gcs_reads_bounded_to_bytes':629145600,'cleanup_permission':'get/delete own schedule only','service_account_keys_created':0}
    write(ROOT/'reports/delivery_access.json',result);print(json.dumps(result))

if __name__=='__main__':main()
