"""Inject cancellation into one isolated real Codex work item; preserve evidence.

This tests the worker's DB cancellation signal, not a user-facing cancel API.
The deliberately interrupted instance remains RUNNING with its item CANCELLED.
It is never relabelled COMPLETED. No PLC or enterprise writes are requested.
"""
import json
import subprocess
import time
import uuid

import psycopg
from probe_definition_registry import ROOT, DSN, http
from probe_registered_codex import definition


def powershell(code):
    text = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', code], text=True).strip()
    result = json.loads(text) if text else []
    return result if isinstance(result, list) else [result]


def main():
    did = 'codex-cancel-' + uuid.uuid4().hex[:8]
    out = ROOT / '.evidence/reaudit' / did
    out.mkdir()
    report = {'definition_id': did, 'passed': False}
    def save():
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    raw = definition(did, '1')
    raw['processDefinitionName'] = '실제 Codex 취소 검증: 조회 전용'
    raw['activities'][0]['instruction'] += ' 각 업무 시스템의 관련 테이블도 describe_schema에서 확인하고 읽기 전용 SELECT로 비교한 뒤 최종 집계 결과를 제출하세요.'
    (out / 'definition.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    code, body = http('/api/process/definitions', {'definition': raw})
    assert code == 201, (code, body)
    code, body = http('/api/instances/start', {'definition_id': did, 'version': '1', 'event_id': did})
    assert code == 200, (code, body)
    pid = body['proc_inst_id']; report['instance_id'] = pid; save()
    print('instance', pid, flush=True)
    until = time.monotonic() + 180
    while time.monotonic() < until:
        code, view = http('/api/instances/' + pid)
        assert code == 200
        wi = view['workitems'][0]
        sessions = [e['data']['session_id'] for e in view['events'] if e.get('data', {}).get('session_id')]
        if wi.get('draft_status') == 'STARTED' and sessions:
            break
        if wi['status'] == 'DONE' or wi.get('draft_status') == 'FAILED':
            raise AssertionError('worker finished before cancellation injection')
        time.sleep(.2)
    else:
        raise TimeoutError('no actual CLI session observed')
    wid = wi['id']; report.update(workitem_id=wid, session_id=sessions[-1])
    # Only this workspace's Codex/npm process and descendants. Never the root agent.
    tree = powershell("$all=@(Get-CimInstance Win32_Process); $ids=[System.Collections.Generic.HashSet[int]]::new(); "
        + f"$all | Where-Object {{$_.Name -match '^(codex|node|cmd)\\.exe$' -and $_.CommandLine -like '*{wid}*'}} | ForEach-Object {{[void]$ids.Add([int]$_.ProcessId)}}; "
        + "do {$added=$false; foreach($p in $all){if($ids.Contains([int]$p.ParentProcessId) -and $ids.Add([int]$p.ProcessId)){$added=$true}}} while($added); "
        + "@($all | Where-Object {$ids.Contains([int]$_.ProcessId)} | Select-Object ProcessId,ParentProcessId,Name) | ConvertTo-Json -Compress")
    report['process_tree_before'] = tree; save()
    assert tree, 'no actual Codex process matched the exact workspace'
    with psycopg.connect(DSN, autocommit=True) as c:
        n = c.execute("update todolist set status='CANCELLED' where id=%s and consumer=%s and status='IN_PROGRESS' and draft_status='STARTED'", (wid, wi['consumer'])).rowcount
    report['cancelled_rows'] = n; save(); assert n == 1
    started = time.monotonic()
    while time.monotonic() - started < 30:
        view = http('/api/instances/' + pid)[1]; fresh = view['workitems'][0]
        if fresh.get('consumer') is None and any(e['event_type'] == 'task_cancelled' for e in view['events']):
            break
        time.sleep(.2)
    report['cancel_observed_seconds'] = round(time.monotonic() - started, 3)
    ids = ','.join(str(p['ProcessId']) for p in tree)
    remaining = powershell('$ids=@(' + ids + '); @(Get-CimInstance Win32_Process | Where-Object {$ids -contains $_.ProcessId -or $ids -contains $_.ParentProcessId} | Select-Object ProcessId,ParentProcessId,Name) | ConvertTo-Json -Compress')
    report['remaining_processes'] = remaining
    report['status'] = fresh['status']; report['consumer'] = fresh.get('consumer')
    report['event_types'] = [e['event_type'] for e in view['events']]
    (out / 'instance.json').write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    assert fresh['status'] == 'CANCELLED' and fresh.get('consumer') is None
    assert 'task_cancelled' in report['event_types'] and 'task_completed' not in report['event_types']
    assert not fresh.get('output') and not remaining
    report['passed'] = True; save()
    print('actual Codex DB cancellation and PowerShell process-tree verification PASS', out, flush=True)


if __name__ == '__main__':
    main()
