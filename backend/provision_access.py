"""Provision identities scoped to Zunda; never create service-account keys."""
import json
import time
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common import ROOT, config, credentials, read, write, now
from cloud_sync import authorize

def main():
    approval=authorize('daily_cloud_run');cfg=config();project=cfg['project'];number='570862915709'
    token=credentials().token;changes=[]
    def request(method,url,data=None,allowed=()):
        body=json.dumps(data).encode() if data is not None else None
        try:
            with urlopen(Request(url,data=body,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=45) as r:
                value=r.read();return json.loads(value) if value else {}
        except HTTPError as e:
            if e.code in allowed:return {'http_status':e.code}
            try:error=json.loads(e.read());reason=error.get('error',{}).get('status','unknown')+': '+error.get('error',{}).get('message','')[:700]
            except Exception:reason='unknown'
            raise RuntimeError(f'{method} failed HTTP {e.code}: {reason}') from None
    for api in ('cloudresourcemanager.googleapis.com','iamcredentials.googleapis.com','sts.googleapis.com'):
        url=f'https://serviceusage.googleapis.com/v1/projects/{number}/services/{api}'
        service=request('GET',url)
        if service.get('state')!='ENABLED':
            op=request('POST',url+':enable',{})
            for _ in range(20):
                state=request('GET','https://serviceusage.googleapis.com/v1/'+op['name'])
                if state.get('done'):break
                time.sleep(1)
            if not state.get('done') or state.get('error'):raise RuntimeError('API enable did not succeed.')
            changes.append('enabled '+api)
    accounts={}
    for short in ('zunda-research-runner','zunda-site-reader'):
        email=short+'@'+project+'.iam.gserviceaccount.com'
        account=request('GET',f'https://iam.googleapis.com/v1/projects/{project}/serviceAccounts/{email}',allowed=(404,))
        if account.get('http_status')==404:
            account=request('POST',f'https://iam.googleapis.com/v1/projects/{project}/serviceAccounts',{'accountId':short,'serviceAccount':{'displayName':short}});changes.append('created '+short)
        accounts[short]=email
    runner=accounts['zunda-research-runner'];reader=accounts['zunda-site-reader']
    # Project-level job submission. All dataset data access stays scoped below.
    member='serviceAccount:'+runner
    if '--skip-project-policy' not in sys.argv:
        policy=request('POST',f'https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy',{'options':{'requestedPolicyVersion':3}})
        bindings=policy.setdefault('bindings',[])
        binding=next((b for b in bindings if b['role']=='roles/bigquery.jobUser' and not b.get('condition')),None)
        changed=False
        if binding is None:bindings.append({'role':'roles/bigquery.jobUser','members':[member]});changed=True
        elif member not in binding['members']:binding['members'].append(member);changed=True
        if changed:request('POST',f'https://cloudresourcemanager.googleapis.com/v1/projects/{project}:setIamPolicy',{'policy':policy});changes.append('granted zunda BQ jobUser')
    from google.cloud import bigquery
    client=bigquery.Client(project=project,credentials=credentials());dataset=client.get_dataset(project+'.zunda_all')
    entries=list(dataset.access_entries)
    for email,role in ((runner,'WRITER'),(reader,'READER')):
        if not any(e.entity_id==email and e.role==role for e in entries):entries.append(bigquery.AccessEntry(role,'userByEmail',email));changes.append('scoped dataset '+role+' '+email)
    dataset.access_entries=entries;client.update_dataset(dataset,['access_entries'])
    bucket=cfg['bucket'];policy=request('GET',f'https://storage.googleapis.com/storage/v1/b/{bucket}/iam?optionsRequestedPolicyVersion=3')
    title='zunda_research_prefix';bindings=policy.setdefault('bindings',[])
    if not any(b.get('condition',{}).get('title')==title and member in b.get('members',[]) for b in bindings):
        policy['version']=3;bindings.append({'role':'roles/storage.objectUser','members':[member],'condition':{'title':title,'expression':f'resource.name.startsWith("projects/_/buckets/{bucket}/objects/zunda_research/")'}})
        request('PUT',f'https://storage.googleapis.com/storage/v1/b/{bucket}/iam',policy);changes.append('scoped GCS prefix access')
    pool_id='zunda-github';pool=f'projects/{number}/locations/global/workloadIdentityPools/{pool_id}'
    pool_url='https://iam.googleapis.com/v1/'+pool
    if request('GET',pool_url,allowed=(404,)).get('http_status')==404:
        request('POST',f'https://iam.googleapis.com/v1/projects/{number}/locations/global/workloadIdentityPools?workloadIdentityPoolId={pool_id}',{'displayName':'Zunda GitHub Actions'});changes.append('created keyless identity pool')
    provider=pool+'/providers/github';provider_url='https://iam.googleapis.com/v1/'+provider
    if request('GET',provider_url,allowed=(404,)).get('http_status')==404:
        request('POST',pool_url+'/providers?workloadIdentityPoolProviderId=github',{'displayName':'Zunda repository main only','oidc':{'issuerUri':'https://token.actions.githubusercontent.com'},'attributeMapping':{'google.subject':'assertion.sub','attribute.repository':'assertion.repository'},'attributeCondition':"assertion.repository == 'japonismy/zunda-kikaku-research' && assertion.ref == 'refs/heads/main'"});changes.append('created repository-bound provider')
    saurl=f'https://iam.googleapis.com/v1/projects/{project}/serviceAccounts/{reader}'
    policy=request('POST',saurl+':getIamPolicy',{})
    principal=f'principalSet://iam.googleapis.com/{pool}/attribute.repository/japonismy/zunda-kikaku-research'
    bindings=policy.setdefault('bindings',[])
    if not any(b['role']=='roles/iam.workloadIdentityUser' and principal in b.get('members',[]) for b in bindings):
        bindings.append({'role':'roles/iam.workloadIdentityUser','members':[principal]});request('POST',saurl+':setIamPolicy',{'policy':policy});changes.append('granted keyless reader identity')
    summary={'at':now(),'runner':runner,'reader':reader,'workload_identity_provider':provider,'changes':changes,'service_account_keys_created':0,'other_dataset_permissions_changed':False}
    write(ROOT/'reports/access_setup.json',summary);print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
