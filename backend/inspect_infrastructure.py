"""Read control-plane metadata only; never submit SQL, load, export or write jobs."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/infrastructure'
OUT.mkdir(parents=True, exist_ok=True)
PROJECT = 'rugged-destiny-408613'
command = [r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-File', r'C:\Users\admin\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1', 'auth', 'print-access-token', '--account=japonismy@gmail.com']
p = subprocess.run(command, capture_output=True, text=True, env={**os.environ, 'CLOUDSDK_CORE_DISABLE_PROMPTS': '1'}, creationflags=0x08000000)
if p.returncode:
    raise SystemExit('Could not obtain the selected account token.')
token = p.stdout.strip()

def get(url):
    try:
        with urlopen(Request(url, headers={'Authorization': 'Bearer '+token}), timeout=40) as r:
            return json.load(r)
    except HTTPError as e:
        return {'http_error': e.code}

base = f'https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}'
listing = get(base+'/datasets?maxResults=1000')
dataset_ids = [d['datasetReference']['datasetId'] for d in listing.get('datasets', [])]
summary = {'observed_at': datetime.now(timezone.utc).isoformat(), 'project': PROJECT, 'datasets': dataset_ids, 'selected': {}, 'method': 'metadata GET/LIST only; no query jobs; no storage object operations', 'paid_calls': 0}
for dataset in dataset_ids:
    if not any(s in dataset.lower() for s in ('naresome', 'zunda')):
        continue
    tables = get(base+f'/datasets/{dataset}/tables?maxResults=1000')
    detail = []
    for t in tables.get('tables', []):
        tid = t['tableReference']['tableId']
        if tid not in ('channels','videos','video_snapshots','channel_snapshots','thumbnail_ocr','thumbnail_assets','script_assets','youtube_metadata_update_runs','transcripts'):
            continue
        meta = get(base+f'/datasets/{dataset}/tables/{tid}')
        (OUT/f'{dataset}__{tid}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        detail.append({'table':tid,'rows':meta.get('numRows'),'bytes':meta.get('numBytes'),'type':meta.get('type'),'fields':[f['name'] for f in meta.get('schema',{}).get('fields',[])]})
    summary['selected'][dataset] = detail
for service, url, key in [
    ('jobs', f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/asia-northeast1/jobs', 'jobs'),
    ('schedules', f'https://cloudscheduler.googleapis.com/v1/projects/{PROJECT}/locations/asia-northeast1/jobs', 'jobs'),
]:
    raw = get(url)
    # Environment values may contain credentials. Persist only deployment metadata
    # and environment variable names, never values or whole service responses.
    summary[service] = []
    for item in raw.get(key, []):
        name = item.get('name', '')
        if not any(s in name.lower() for s in ('naresome', 'zunda')):
            continue
        containers = item.get('template',{}).get('template',{}).get('containers',[])
        summary[service].append({'name':name,'schedule':item.get('schedule'),'timeZone':item.get('timeZone'),'state':item.get('state'),'uri':item.get('httpTarget',{}).get('uri'),'containers':[{'image':c.get('image'),'env_names':[e['name'] for e in c.get('env',[])]} for c in containers]})
    if 'http_error' in raw:
        summary[service+'_http_error'] = raw['http_error']
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
