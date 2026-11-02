"""Local warehouse utilities. Cloud writes are deliberately separate."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT/'data_sources/warehouse'
CONFIG = ROOT/'backend/config.json'
JST = timezone(timedelta(hours=9))

def now():
    return datetime.now(JST).isoformat(timespec='seconds')

def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def table(name):
    return read(WAREHOUSE/(name+'.json'), [])

def save_table(name, rows):
    write(WAREHOUSE/(name+'.json'), rows)

def upsert(name, rows, keys):
    merged = {tuple(r.get(k) for k in keys):r for r in table(name)}
    for row in rows:
        merged[tuple(row.get(k) for k in keys)] = row
    save_table(name, list(merged.values()))

def config():
    return read(CONFIG)

def validate_scope(rows):
    allowed = {c['channel_id'] for c in config()['channels']}
    unexpected = {r.get('channel_id') for r in rows if r.get('channel_id') not in allowed}
    if unexpected:
        raise ValueError('Channel outside approved registry: '+str(sorted(unexpected)))

def credentials():
    # Cloud runtimes use the explicitly deployed service account. Local Windows
    # uses the named operations account instead of an unrelated cached ADC.
    import os
    if os.name!='nt' or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.environ.get('CLOUD_RUN_JOB'):
        return None
    import subprocess
    from google.oauth2.credentials import Credentials
    command=[r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-File',r'C:\Users\admin\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1','auth','print-access-token','--account=japonismy@gmail.com']
    result=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'CLOUDSDK_CORE_DISABLE_PROMPTS':'1'},creationflags=0x08000000)
    if result.returncode:raise RuntimeError('Selected GCP operations account is unavailable.')
    return Credentials(result.stdout.strip())
