"""Store the approved budget in Secret Manager and scope runner access."""
import base64
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common import ROOT, config, credentials, read, write, now
from cloud_sync import authorize

def main():
    approval=authorize('daily_cloud_run');cfg=config();project=cfg['project'];token=credentials().token
    def request(method,url,data=None,allowed=()):
        try:
            with urlopen(Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=45) as response:
                body=response.read();return json.loads(body) if body else {}
        except HTTPError as e:
            if e.code in allowed:return {'http_status':e.code}
            raise RuntimeError(f'Secret Manager control operation failed HTTP {e.code}') from None
    name='zunda-research-cost-approval-20261102';base=f'https://secretmanager.googleapis.com/v1/projects/{project}/secrets/'
    if request('GET',base+name,allowed=(404,)).get('http_status')==404:
        request('POST',f'https://secretmanager.googleapis.com/v1/projects/{project}/secrets?secretId={name}',{'replication':{'userManaged':{'replicas':[{'location':cfg['location']}]}}})
    versions=request('GET',base+name+'/versions?pageSize=10').get('versions',[])
    if not versions:
        payload=base64.b64encode(json.dumps(approval,ensure_ascii=False).encode()).decode()
        request('POST',base+name+':addVersion',{'payload':{'data':payload}})
    member='serviceAccount:zunda-research-runner@'+project+'.iam.gserviceaccount.com'
    for secret in (name,'naresome-youtube-api-key'):
        policy=request('GET',base+secret+':getIamPolicy?options.requestedPolicyVersion=3')
        bindings=policy.setdefault('bindings',[])
        binding=next((b for b in bindings if b['role']=='roles/secretmanager.secretAccessor' and not b.get('condition')),None)
        changed=False
        if binding is None:bindings.append({'role':'roles/secretmanager.secretAccessor','members':[member]});changed=True
        elif member not in binding['members']:binding['members'].append(member);changed=True
        if changed:request('POST',base+secret+':setIamPolicy',{'policy':policy})
    result={'at':now(),'approval_secret':name,'youtube_secret':'naresome-youtube-api-key','runner':member,'api_key_copied_to_local_file':False,'secret_values_logged':False}
    write(ROOT/'reports/secret_setup.json',result);print(json.dumps(result))

if __name__=='__main__':main()
