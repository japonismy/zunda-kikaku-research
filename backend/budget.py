"""Conservative local reservations within the user's task-level JPY cap."""
from common import ROOT, read, write, now

def reserve(scope, amount, operation, details=None):
    ledger=read(ROOT/'reports/cost_ledger.json')
    if not ledger:raise RuntimeError('Cost ledger missing; no paid operation may start.')
    allocation=next((r['max_jpy'] for r in ledger['reservations'] if r['scope']==scope),None)
    if allocation is None:raise RuntimeError('Operation has no approved budget allocation.')
    entries=ledger.setdefault('operations',[])
    used=sum(float(e.get('estimated_max_jpy',0)) for e in entries if e.get('scope')==scope)
    if used+amount>allocation:raise RuntimeError('Scope budget would be exceeded.')
    committed=sum(float(e.get('estimated_max_jpy',0)) for e in entries)
    if committed+amount>ledger['approved_total_jpy']:raise RuntimeError('Total task cap would be exceeded.')
    entry={'id':len(entries)+1,'at':now(),'scope':scope,'operation':operation,'estimated_max_jpy':amount,'status':'reserved_before_request','details':details or {}}
    entries.append(entry);ledger['estimated_used_and_reserved_jpy']=round(committed+amount,3)
    ledger['remaining_task_cap_jpy']=round(ledger['approved_total_jpy']-committed-amount,3)
    write(ROOT/'reports/cost_ledger.json',ledger);return entry['id']

def settle(entry_id, status, details=None):
    ledger=read(ROOT/'reports/cost_ledger.json')
    entry=next(e for e in ledger['operations'] if e.get('id')==entry_id)
    entry.update(status=status,completed_at=now())
    if details:entry['result']=details
    write(ROOT/'reports/cost_ledger.json',ledger)
