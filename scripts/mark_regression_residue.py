"""A6 — 회귀 잔재 표시·정리: 검사기(probe_*·scenario_*·run_scenario*)가 처리 DB에 남긴 처리 건을 찾아 숨긴다.

    .venv/bin/python scripts/mark_regression_residue.py --out .evidence/<A번호>/residue             (기본: 목록·백업만, 바꾸는 것 없음)
    .venv/bin/python scripts/mark_regression_residue.py --out <dir> --legacy                        (이 변경 전 영문·시험 문구로 남은 옛 잔재까지)
    .venv/bin/python scripts/mark_regression_residue.py --out <dir> [--legacy] --apply              (아래 '적용'을 실제로 수행)
    (Windows: . scripts/host_libpq.sh; .venv314/Scripts/python scripts/mark_regression_residue.py …)

찾는 법(내용 기준, 시각 기준이 아님): 검사기는 사람과 같은 API로 승인·제출하므로 처리 DB만 봐서는 사람 것과 구별이 안 된다.
그래서 검사기가 남기는 사유·담당자·메모·정의 이름에 표식 MARKER("[회귀 검사]")를 붙였다(A6). 표식이 events.data, todolist.output/log,
process_approval_outbox(payload·history), process_effect_receipt.request, process_rework_receipt.request, bpm_proc_inst.proc_inst_name 중
한 곳에라도 있는 처리 건을 잔재로 본다. --legacy를 주면 표식 도입 전 검사기가 쓰던 문구 LEGACY(정확한 문자열)도 같은 자리에서 찾는다.
지금 도는 회귀를 건드리지 않도록 RUNNING이면서 --keep-recent-min분 안에 갱신된 처리 건은 뺀다. 시각 경계로 지우려면 기존
cleanup_residue_instances.py(--before, RUNNING만)를 쓴다.

적용(--apply, 메인이 실행): 먼저 backup.json(처리 건·작업 행·그래프 투영)을 쓰고
  1. PG bpm_proc_inst.is_deleted=true, deleted_at=now() — 행은 남긴다(포털 처리 건 목록·내 할일에서 빠짐, 엔진 claim도 건너뜀).
  2. 그 처리 건의 열린 todolist 행 → CANCELLED + log 표시.
  3. Neo4j ProcessInstance와 WorkItem 투영 노드 DETACH DELETE(정의·온톨로지는 손대지 않음).
삭제가 아니라 숨김이다. 되돌리려면 backup.json의 proc_inst_id로 is_deleted=false.

손대지 않고 보고만 하는 것(report.json):
  - process SQLite 스냅숏의 사건(Incident)·판단(Decision): 실행 중 process가 메모리 상태로 덮어쓰므로 여기서 고치지 않는다.
    GET /api/incidents·/api/decisions를 읽어 표식·옛 문구가 든 건수와 id만 적는다(사유 문구에 표식이 보이므로 화면에서 시험임이 드러남).
  - 그래프 선례 DecisionCase: cleanup_residue_cases.py --marker [--legacy]로 정리한다(같은 표식 목록을 이 파일에서 가져다 씀).
  - 검사기가 만든 격리 테넌트(tenants.id != --tenant): 테넌트별 처리 건 수만 적는다. 테넌트 삭제는 cascade 삭제라 사용자에게 묻는다.
  - 검사기가 등록한 정의(proc_def.name에 표식): 목록만. 정의 정리는 cleanup_invalid_definitions.py 쪽 판단.
"""
import argparse
import json
import os
import urllib.request
from pathlib import Path

MARKER = '[회귀 검사]'
# 표식 도입(A6) 전 검사기가 처리 DB에 남긴 정확한 문구. 사람이 같은 문장을 칠 가능성이 낮은 것만 둔다
# (fixture·test·again·stale 같은 일반 단어와 이생산·김운전·운전원 같은 시험 인물 이름은 넣지 않는다).
LEGACY = (
    'A032 현장검토 시험', 'A035 operator probe', 'A035 recovery manager', 'A070 probe', 'controlled explicit BSC condition verification',
    'A078 probe', 'A078 restore', 'A078: 회의 L385~404', 'A046 integration reviewer', 'MES changed after delivered consent',
    'A087 probe', 'A087 restore', 'A087: 원천 DDL과 어긋난 바인딩', 'A031-review-probe', '현재 입력으로 팬 95% / 부하 78% 변경안을 검토함',
    'A040 fixture reviewer', 'Re-evaluate current facts with a new producing work item', 'A040 stale requester', 'A039 fixture reviewer',
    'Producer-scope fixture reviewed', 'A063 probe', 'changed producer result', 'A072 probe:', 'fan 100 % confirmed on site',
    'A062 probe', 'shared endpoint rework', 'PG rework reviewer', 'Changed evidence; retire failed consent', 'A064 fixture',
    'A048 explicit fixture completion', 'A048 retained semantic fixture', 'A075 reviewer', 'probe fixture — removed at the end',
    'A031-legacy-probe', 'manual-api-probe', 'A050 contract probe', '검사기가 직접 작성한 계약 검증용 제안', 'PG reviewer',
    'Source ended without issuing command', 'A049 acceptance', 'A069 probe', 'A069 controlled runtime verification', 'A071 probe',
    'new producer value changes separate branch condition', 'A038 measurer', 'A038 checker', 'A038 reviewer', 'A038 rechecker',
    'A038 confirmer', 'Measurement review changed; retain earlier measurement', 'New generation compared with preserved history',
    'PG rework tester', 'Change request after original claim', 'Actual generation checked', 'A037 reviewer', 'A037 confirmer',
    'Rework dependency preview acceptance', 'Confirm changed score', 'A036 provenance reviewer', 'Start input and result provenance acceptance',
    'A047 isolated acceptance', 'A047 HTTP acceptance', 'A033 ACK 검증', 'A033 DB connection probe', 'Transport outage recovered; original alert retained',
    'fixture reviewer', 'A033 Kafka 복구 검증', 'A033 persistence probe', 'Scoped PG write failure and CLEAR process-death verified',
    'changed-action-probe', 'stale-approval-probe', 'stale mode verification', '실제 반례 상태와 명령 거절을 보존하고 시험을 종료함',
    'Explicit fixture: source has no observation', 'PG fixture reviewer', 'Fixture deferral and reassessment complete',
    'A072 run 4 (1x, real Claude Code worker)', 'scenario-test', 'scenario_test', 'probe-manager', 'PG discard probe',
    'Fixture ended; retire failed consent', 'Correct rejected old-decision output', 'A049 operator verification',
    'repair isolated derived fixture after source comparison', 'OP-17',
    'OEM 납기 오더 진행 중 — 생산을 멈추지 않고 유온을', '예비 펌프 정비 완료 상태', '고장 주입 뒤 2분 원천 창을 새로 관측했으므로 재평가를 요청한다',
    '고장 주입 후 실제 2분 원천 창을 새로 관측하여 재평가 요청', '부하 저감으로는 압력이 회복되지 않음. 예비 펌프 전환 지시.',
    '강제 종료 후 설비 상태 확인, 별도 정비 판단 필요', '팬 조치 ACK 접수 중단 후 재시작 검토 경계 확인',
)
DSN = os.environ.get('SUPABASE_DSN', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres')
NEO4J = (os.environ.get('NEO4J_URI', 'bolt://127.0.0.1:7687'), ('neo4j', os.environ.get('NEO4J_PASSWORD', 'hydpass123')))
OPEN = ('TODO', 'IN_PROGRESS', 'SUBMITTED', 'PENDING')

# 처리 건 하나에 대해 '어디에서 어떤 문구로 걸렸나'를 한 줄씩. 텍스트 비교는 strpos(정확한 부분 문자열, 정규식 아님).
HITS_Q = '''
with pats as (select unnest(%(pats)s::text[]) as p),
hits as (
  select e.proc_inst_id, 'events' as src, e.data::text as txt from events e
   where e.proc_inst_id in (select proc_inst_id from bpm_proc_inst where tenant_id=%(t)s)
  union all select w.proc_inst_id, 'todolist', coalesce(w.output::text,'')||' '||coalesce(w.log,'') from todolist w where w.tenant_id=%(t)s
  union all select o.proc_inst_id, 'approval', coalesce(o.payload::text,'')||' '||coalesce(o.history::text,'') from process_approval_outbox o where o.tenant_id=%(t)s
  union all select r.proc_inst_id, 'effect', r.request::text from process_effect_receipt r where r.tenant_id=%(t)s
  union all select r.proc_inst_id, 'rework', r.request::text from process_rework_receipt r where r.tenant_id=%(t)s
  union all select i.proc_inst_id, 'instance_name', coalesce(i.proc_inst_name,'') from bpm_proc_inst i where i.tenant_id=%(t)s
)
select h.proc_inst_id, h.src, p.p as pattern, substr(h.txt, greatest(strpos(h.txt, p.p)-40, 1), 160) as excerpt
  from hits h join pats p on strpos(h.txt, p.p) > 0
'''


def patterns(legacy):
    return [MARKER] + (list(LEGACY) if legacy else [])


def http_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--tenant', default='hyd')
    ap.add_argument('--legacy', action='store_true', help='표식 도입 전 옛 검사기 문구(LEGACY)도 찾는다')
    ap.add_argument('--keep-recent-min', type=int, default=30, help='RUNNING이면서 이 분 안에 갱신된 처리 건은 뺀다(지금 도는 회귀)')
    ap.add_argument('--process-url', default=os.environ.get('PROCESS_URL', 'http://127.0.0.1:8080'))
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--skip-graph', action='store_true', help='Neo4j가 꺼져 있어도 PG 숨김만 적용(투영은 나중에 cleanup_residue_instances.py 방식으로)')
    a = ap.parse_args()
    import psycopg
    from psycopg.rows import dict_row
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pats = patterns(a.legacy)
    report = {'tenant': a.tenant, 'legacy': a.legacy, 'applied': False}
    with psycopg.connect(DSN, autocommit=False, row_factory=dict_row) as db:
        hits = db.execute(HITS_Q, {'pats': pats, 't': a.tenant}).fetchall()
        ids = sorted({h['proc_inst_id'] for h in hits if h['proc_inst_id']})
        rows = db.execute('''select *, (status='RUNNING' and coalesce(updated_at, start_date) > now() - make_interval(mins => %s)) as _recent
                             from bpm_proc_inst where proc_inst_id = any(%s) and tenant_id=%s and not is_deleted order by start_date''',
                          (a.keep_recent_min, ids, a.tenant)).fetchall()
        keep = [r['proc_inst_id'] for r in rows if r['_recent']]
        inst = [{k: v for k, v in r.items() if k != '_recent'} for r in rows if not r['_recent']]
        ids = [i['proc_inst_id'] for i in inst]
        todos = db.execute('select * from todolist where proc_inst_id = any(%s)', (ids,)).fetchall() if ids else []
        defs = db.execute('select id, name, tenant_id, isdeleted from proc_def where strpos(coalesce(name,%s), %s) > 0',
                          ('', MARKER)).fetchall()
        tenants = db.execute('''select t.id, t.name, count(i.proc_inst_id) as instances from tenants t
                                left join bpm_proc_inst i on i.tenant_id=t.id where t.id <> %s group by t.id, t.name order by t.id''',
                             (a.tenant,)).fetchall()
        graph = []
        try:
            from neo4j import GraphDatabase
            with GraphDatabase.driver(NEO4J[0], auth=NEO4J[1], connection_timeout=5) as driver, driver.session() as s:
                graph = s.run('MATCH (p:ProcessInstance) WHERE p.id IN $ids OPTIONAL MATCH (p)<-[:IN_INSTANCE]-(w:WorkItem) '
                              'RETURN p.id AS id, properties(p) AS props, collect(properties(w)) AS workitems', ids=ids).data()
            report['graph'] = {'instances': len(graph), 'workitems': sum(len(g['workitems']) for g in graph)}
        except Exception as e:      # 그래프가 꺼져 있으면 PG 표시만 하고 사유를 남긴다
            report['graph'] = {'error': f'{type(e).__name__}: {e}'[:300]}
        why = {}
        for h in hits:
            if h['proc_inst_id'] in ids:
                why.setdefault(h['proc_inst_id'], []).append({'src': h['src'], 'pattern': h['pattern'], 'excerpt': h['excerpt']})
        backup = {'instances': inst, 'todolist': todos, 'graph': graph}
        (out / 'backup.json').write_text(json.dumps(backup, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        by_def = {}
        for i in inst:
            by_def[i['proc_def_id']] = by_def.get(i['proc_def_id'], 0) + 1
        report.update(residue_instances=len(ids), by_definition=by_def, kept_running_recent=keep,
                      todolist_rows=len(todos), open_todolist=sum(t['status'] in OPEN for t in todos),
                      marked_definitions=defs, isolated_tenants=tenants,
                      matches={k: v[:3] for k, v in why.items()})
        if a.apply and ids and 'error' in report['graph'] and not a.skip_graph:
            raise SystemExit('적용 중단: 그래프 투영을 함께 지울 수 없음 — ' + report['graph']['error'] + ' (Neo4j를 켜거나 --skip-graph)')
        if a.apply and ids:
            n1 = db.execute('update bpm_proc_inst set is_deleted=true, deleted_at=now() where proc_inst_id = any(%s) and not is_deleted',
                            (ids,)).rowcount
            n2 = db.execute("update todolist set status='CANCELLED', end_date=coalesce(end_date, now()), "
                            "log=coalesce(log,'')||'[A6 회귀 잔재 정리: 처리 건 숨김] ' "
                            "where proc_inst_id = any(%s) and status = any(%s)", (ids, list(OPEN))).rowcount
            db.commit()
            n3 = 0
            if graph and not a.skip_graph:
                from neo4j import GraphDatabase
                with GraphDatabase.driver(NEO4J[0], auth=NEO4J[1], connection_timeout=5) as driver, driver.session() as s:
                    n3 = s.run('MATCH (p:ProcessInstance) WHERE p.id IN $ids OPTIONAL MATCH (p)<-[:IN_INSTANCE]-(w:WorkItem) '
                               'WITH p, collect(w) AS ws FOREACH (w IN ws | DETACH DELETE w) DETACH DELETE p RETURN count(p) AS n',
                               ids=ids).single()['n']
            report.update(applied=True, soft_deleted=n1, todolist_cancelled=n2, graph_instances_deleted=n3)
    # process SQLite(사건·판단)는 읽기만 — 실행 중 process가 메모리 상태로 덮어쓰므로 여기서 고치지 않는다
    try:
        incs = http_json(a.process_url + '/api/incidents')
        decs = http_json(a.process_url + '/api/decisions')
        hit = lambda o: any(p in json.dumps(o, ensure_ascii=False) for p in pats)
        report['process_state_report_only'] = {
            'incidents_marked': [i.get('id') for i in incs if hit(i)], 'incidents_total': len(incs),
            'decisions_marked': [d.get('id') for d in decs if hit(d)], 'decisions_total': len(decs)}
    except Exception as e:
        report['process_state_report_only'] = {'error': f'{type(e).__name__}: {e}'[:300]}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('residue_instances', 'by_definition', 'open_todolist', 'applied') if k in report}
                     | {'kept_running_recent': len(keep), 'graph': report.get('graph'),
                        'process_state': {k: (len(v) if isinstance(v, list) else v) for k, v in report['process_state_report_only'].items()}},
                     ensure_ascii=False, default=str))
    if not a.apply:
        print('dry run — 바꾼 것 없음. 목록·근거:', out / 'report.json', '/ 백업:', out / 'backup.json')


if __name__ == '__main__':
    main()
