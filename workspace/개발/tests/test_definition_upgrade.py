"""제공 정의 파일의 판본이 올라갈 때, 이미 옛 판본으로 돌던 업무 DB 에서 process 기동(procsvc/instance_mode.build)이 하는 일.

등록한 정의 판본은 바꿀 수 없으므로(procdb.upsert_proc_def) 정의를 고치면 판본 번호를 올린다. 그 뒤 학생 PC 는 옛 판본이 등록 · 배포돼 있고
옛 판본으로 열린 처리 건이 진행 중인 DB 에서 새 파일로 켜진다. 이 시험은 그 길을 실제 업무 DB(마이그레이션 + 시드를 넣은 버릴 DB)와 실제 기동
함수로 잰다: 옛 정의 파일(낸 그대로의 원문 — data/definitions, 판본 잠금 파일의 지문과 대조)로 한 번 켜고, 지금 정의 파일로 다시 켠다.
바깥(Kafka 감사 · 사건 저장 파일 · 지식 그래프)은 이 길이 쓰지 않는 자리라 연결하지 않는다 — 불리면 그 까닭으로 실패한다.
"""
import hashlib
import json
import shutil
import uuid
from pathlib import Path

import pytest

from conftest import DEFINITIONS, OPERATOR, new_database
from procsvc import bpmn_store, engine, flow_deploy, instance_mode, procdb

DATA = Path(__file__).resolve().parent / 'data' / 'definitions'
OLD = {'anomaly_response_v22.json': 'anomaly_response_2.3.json', 'shift_handover_v1.json': 'shift_handover_1.3.json'}
#: 바로 앞 판본(이름만 화면 용어로 바꾸고 그림을 붙이기 전) — 학생 PC 에 지금 등록돼 있는 판이다
PREVIOUS = {'anomaly_response_v22.json': 'anomaly_response_2.4.json', 'shift_handover_v1.json': 'shift_handover_1.4.json'}
ME = OPERATOR['by']


def _raw(path):
    return json.loads(path.read_text(encoding='utf8'))


def test_옛_판본_자료는_그_판본을_낼_때의_원문_그대로다():
    """시험이 쓰는 옛 정의가 학생 PC 에 실제로 등록돼 있는 원문과 같은지 — 판본 잠금 파일의 지문으로 대조한다."""
    lock = _raw(Path(__file__).resolve().parent / 'definition_versions.lock.json')
    for name in [*OLD.values(), *PREVIOUS.values()]:
        raw = _raw(DATA / name)
        digest = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        assert lock[f"{raw['processDefinitionId']}@{raw['version']}"] == digest, name
    for name, old in [*OLD.items(), *PREVIOUS.items()]:
        assert _raw(DEFINITIONS / name)['version'] != _raw(DATA / old)['version'], f'{name}: 지금 파일이 옛 판본 번호 그대로다'


@pytest.fixture
def boot(pg_dsn, tmp_path, monkeypatch):
    """boot(old=True|False) → 그 정의 파일들로 켠 런타임. 같은 버릴 DB · 같은 사건 사전을 이어 쓴다(process 를 껐다 켠 것과 같다)."""
    dirs = {}
    for key, files in (('old', OLD), ('previous', PREVIOUS)):
        dirs[key] = tmp_path / f'definitions-{key}'
        shutil.copytree(DEFINITIONS, dirs[key])
        for name, old in files.items():
            shutil.copyfile(DATA / old, dirs[key] / name)

    def not_wired(what):
        def call(*a, **k):
            raise AssertionError(f'이 시험의 길은 {what}을(를) 부르지 않는다')
        return call
    ctx = instance_mode.ProcessContext(
        incidents={}, book={}, state={}, time_scale=20.0, persist=lambda: None, audit=lambda *a, **k: None,
        cypher=not_wired('지식 그래프'), exec_skill=not_wired('업무 거래'), approve_incident=not_wired('설비 명령'),
        get_loop=lambda: None, check_approval=not_wired('승인 현재 조건 검사'))
    monkeypatch.setattr(instance_mode, '_runtime', instance_mode._runtime)      # 기동이 바꾸는 모듈 상태 — 시험 뒤 되돌린다
    monkeypatch.setattr(instance_mode, '_ctx', instance_mode._ctx)
    compression = engine.wait_compression()
    with new_database(pg_dsn, schema=True) as dsn:
        def start(old):
            """old: True = 2.3 · 1.3 판(거절 길이 생기기 전), 'previous' = 바로 앞 판, False = 지금 정의 파일."""
            monkeypatch.setattr(instance_mode, 'DEFINITIONS_DIR', dirs['previous' if old == 'previous' else 'old'] if old else DEFINITIONS)
            return instance_mode.build(ctx, repo=procdb.PgRepo(dsn))
        try:
            yield start
        finally:
            engine.configure_wait_compression(compression)


def _pump_alert():
    return {'alertId': 'ALT-HYD-02-' + uuid.uuid4().hex[:10], 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE', 'state': 'RAISE',
            't': '2026-11-14T00:00:00.000Z', 'severity': 'HIGH'}


def _open(rt):
    """경보 하나로 지금 운영 판본의 처리 건을 연다(경보 접수와 같은 함수 — 운영 판본은 저장소의 배포 표에서 읽는다)."""
    alert = _pump_alert()
    version = rt.repo.deployed_version('anomaly_response', 'hyd')
    return rt.start_definition('anomaly_response', version, alert['alertId'], alert=alert)


def _rejectable(rt, inst):
    defn = rt.definition_for(inst)
    return rt._card_step_rejects(defn, {'activity_id': 'task:select'})


def test_옛_판본만_돌던_DB에서_새_파일로_켜면_새_판본이_운영_판본이_되고_진행_중_처리_건은_옛_판본으로_이어진다(boot):
    old, new = _raw(DATA / OLD['anomaly_response_v22.json'])['version'], _raw(DEFINITIONS / 'anomaly_response_v22.json')['version']
    rt = boot(old=True)
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == old
    running = _open(rt)
    assert running['proc_def_version'] == old and not _rejectable(rt, running)

    rt = boot(old=False)                                                 # 새 정의 파일로 다시 켬(학생 PC 의 git pull 뒤 시작)
    assert rt.base_problem is None and (rt.base_version, rt.defn.raw['version']) == (new, new)
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == new, '사람이 배포한 적 없는 DB 는 새 기준 판본을 운영 판본으로 쓴다'
    assert [d['action'] for d in rt.repo.list_deployments('anomaly_response', 'hyd', limit=2)] == ['seed', 'seed']
    fresh = _open(rt)
    assert fresh['proc_def_version'] == new and _rejectable(rt, fresh), '새로 열리는 처리 건은 거절 길이 있는 판본이다'
    # 진행 중이던 처리 건은 자기 판본 그대로: 정의를 읽을 수 있고, 그 판본의 다음 단계로 나아간다
    still = rt.repo.get_instance(running['proc_inst_id'])
    assert still['proc_def_version'] == old and rt.definition_for(still).raw == _raw(DATA / OLD['anomaly_response_v22.json'])
    consumer = 'upgrade-test:' + uuid.uuid4().hex[:8]
    [wi] = rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=still['proc_inst_id'])
    assert (wi['activity_id'], wi['version']) == ('task:diagnose', old)
    assert rt.repo.save_task_result(wi['id'], {'cause': 'cause:x', 'failure_mode': 'fm:x', 'guide_card': {'summary': '시험'}}, True, consumer)
    rt.poll_once()
    rows = {w['activity_id']: w for w in rt.repo.list_workitems(proc_inst_id=still['proc_inst_id'], limit=None)}
    assert (rows['task:diagnose']['status'], rows['task:candidates']['status'], rows['task:candidates']['version']) == ('DONE', 'IN_PROGRESS', old)
    assert 'task:report-rejected' not in rows, '옛 판본의 처리 건에 새 판본의 단계가 끼지 않는다'
    with pytest.raises(ValueError, match=f'거절 길이 없던 흐름 판본\\(anomaly_response {old}\\)'):
        rt.reject_card(_at_select(rt, still['proc_inst_id']), 'DEC-x', OPERATOR['by'], OPERATOR['role'], '사유')


def _at_select(rt, pid):
    """옛 판본 처리 건의 승인 단계 행 id — 거절 요청이 그 판본의 계약으로 판정되는지만 보려고 그 행을 진행 중으로 둔다(저장소 직접 갱신)."""
    row = next(w for w in rt.repo.list_workitems(proc_inst_id=pid, limit=None) if w['activity_id'] == 'task:select')
    row['status'] = 'IN_PROGRESS'
    rt.repo.update_workitem(row)
    return row['id']


def test_교대_인수인계도_새_판본이_등록되고_옛_판본은_그대로_남는다(boot):
    old, new = _raw(DATA / OLD['shift_handover_v1.json'])['version'], _raw(DEFINITIONS / 'shift_handover_v1.json')['version']
    rt = boot(old=True)
    assert rt.repo.get_proc_def('shift_handover', 'hyd', version=new) is None
    rt = boot(old=False)
    assert rt.repo.get_proc_def('shift_handover', 'hyd', version=old)['definition'] == _raw(DATA / OLD['shift_handover_v1.json'])
    assert rt.repo.get_proc_def('shift_handover', 'hyd', version=new)['definition'] == _raw(DEFINITIONS / 'shift_handover_v1.json')


def _student_version(rt, base_version):
    """사람이 등록한 기준 흐름의 다른 판본 하나(옛 기준 판본을 이름만 바꿔 등록)."""
    raw = dict(_raw(DATA / OLD['anomaly_response_v22.json']), version=base_version + '-student', processDefinitionName='설비 이상 조치 (학생 판)')
    return rt.register_definition(raw)['prod_version']


def test_사람이_다른_판본을_배포해_둔_DB에서는_그_판본을_그대로_쓰고_새_기준_판본은_되돌리기의_목적지로_등록된다(boot):
    old, new = _raw(DATA / OLD['anomaly_response_v22.json'])['version'], _raw(DEFINITIONS / 'anomaly_response_v22.json')['version']
    rt = boot(old=True)
    mine = _student_version(rt, old)
    rt.deploy_definition('anomaly_response', mine, ME, '내 판본으로')
    rt = boot(old=False)
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == mine, '사람이 배포한 판본을 기동이 바꾸지 않는다'
    assert (rt.base_version, rt.base_problem) == (new, None)
    assert rt.repo.get_proc_def('anomaly_response', 'hyd', version=new)['definition'] == _raw(DEFINITIONS / 'anomaly_response_v22.json')
    shown = flow_deploy.routes(rt)
    assert shown['reference'] == {'definition': 'anomaly_response', 'version': new, 'deployed_version': mine, 'name': shown['reference']['name'],
                                  'changed': True} and shown['reset_needed'] is True
    out = flow_deploy.deploy_reset(rt, ME, '기준으로')
    assert [(c['from'], c['to']) for c in out['changes']] == [(mine, new)] and rt.repo.deployed_version('anomaly_response', 'hyd') == new


def test_기준_흐름으로_되돌려_둔_DB는_새_파일로_켜면_새_기준_판본을_따른다(boot):
    """되돌리기는 「기준 판본을 쓴다」는 요청이다. 전에는 되돌린 적 있는 PC 만 옛 기준 판본에 머물러, 한 번 더 되돌려야 새 기준이 됐다."""
    old, new = _raw(DATA / OLD['anomaly_response_v22.json'])['version'], _raw(DEFINITIONS / 'anomaly_response_v22.json')['version']
    rt = boot(old=True)
    mine = _student_version(rt, old)
    rt.deploy_definition('anomaly_response', mine, ME, '내 판본으로')
    flow_deploy.deploy_reset(rt, ME, '기준으로')
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == old
    rt = boot(old=False)
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == new and flow_deploy.routes(rt)['reference']['changed'] is False


# ---------------------------------------------------------------- 그림(정의 옆 .bpmn)과 이름만 바꾼 판본
def _picture(rt, did, version):
    from procsvc.bpmn_store import FlowStore
    return FlowStore(rt.repo, rt.tenant_id).bpmn_of(did, version)


def test_바로_앞_판으로_돌던_DB에서_새_파일로_켜면_정상으로_켜지고_진행_중_처리_건은_앞_판의_이름과_길로_끝까지_간다(boot):
    """2026-11-14: 단계 · 선 · 끝의 이름을 화면 용어로 바꾸고 그림을 붙이며 판본을 올렸다(2.4 → 2.5, 1.4 → 1.5). 같은 번호로 냈다면 이 PC 에서
    process 가 시작하지 못한다. 앞 판으로 열린 처리 건은 앞 판의 정의로 끝나고(이름도 그때 이름), 새로 열리는 처리 건은 새 판이다."""
    previous, new = _raw(DATA / PREVIOUS['anomaly_response_v22.json']), _raw(DEFINITIONS / 'anomaly_response_v22.json')
    rt = boot(old='previous')
    assert rt.repo.deployed_version('anomaly_response', 'hyd') == previous['version']
    running = _open(rt)
    rt = boot(old=False)
    assert rt.base_problem is None and rt.repo.deployed_version('anomaly_response', 'hyd') == new['version']
    assert rt.repo.get_proc_def('shift_handover', 'hyd', version=_raw(DATA / PREVIOUS['shift_handover_v1.json'])['version'])['definition'] \
        == _raw(DATA / PREVIOUS['shift_handover_v1.json'])
    fresh = _open(rt)
    assert fresh['proc_def_version'] == new['version']
    assert {a['id']: a['name'] for a in rt.definition_for(fresh).raw['activities']}['task:work-order'] == '정비 요청 등록'
    # 진행 중이던 처리 건: 앞 판의 정의 그대로 끝까지 — 진단부터 반려(앞 판에도 있는 길)로 끝낸다
    still = rt.repo.get_instance(running['proc_inst_id'])
    assert still['proc_def_version'] == previous['version'] and rt.definition_for(still).raw == previous
    consumer = 'upgrade-test:' + uuid.uuid4().hex[:8]
    outputs = {'task:diagnose': {'cause': 'cause:x', 'failure_mode': 'fm:x', 'guide_card': {'summary': '시험'}}}
    [wi] = rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=still['proc_inst_id'])
    assert (wi['activity_id'], wi['version'], wi['activity_name']) == ('task:diagnose', previous['version'], '원인 진단')
    assert rt.repo.save_task_result(wi['id'], outputs['task:diagnose'], True, consumer)
    rt.poll_once()
    rows = {w['activity_id']: w for w in rt.repo.list_workitems(proc_inst_id=still['proc_inst_id'], limit=None)}
    assert (rows['task:diagnose']['status'], rows['task:candidates']['status'], rows['task:candidates']['version']) == ('DONE', 'IN_PROGRESS', previous['version'])
    old_names = {a['id']: a['name'] for a in previous['activities']}
    assert rows['task:candidates']['activity_name'] == old_names['task:candidates']


def test_새_판본에는_그림이_붙고_그림_파일과_어긋나는_앞_판에는_붙지_않는다(boot):
    """그림 파일(definitions/<정의 id>.bpmn)은 지금 정의의 그림이다. 앞 판(이름이 다르다)과는 어긋나므로 앞 판에는 붙이지 않는다 —
    그 판의 처리 건은 화면이 정의에서 그림을 만든다. 기동은 그림 때문에 멈추지 않는다."""
    rt = boot(old='previous')
    for did, name in (('anomaly_response', 'anomaly_response_v22.json'), ('shift_handover', 'shift_handover_v1.json')):
        assert _picture(rt, did, _raw(DATA / PREVIOUS[name])['version']) is None, '앞 판의 이름과 다른 그림은 붙지 않는다'
    rt = boot(old=False)
    for did, name in (('anomaly_response', 'anomaly_response_v22.json'), ('shift_handover', 'shift_handover_v1.json')):
        raw = _raw(DEFINITIONS / name)
        xml = _picture(rt, did, raw['version'])
        assert xml and 'BPMNDiagram' in xml and '<bpmn:lane ' in xml, did
        assert f'id="{bpmn_store.xid(raw["activities"][0]["id"])}"' in xml and ':draft' not in xml and 'task:' not in xml
        assert _picture(rt, did, _raw(DATA / PREVIOUS[name])['version']) is None
    assert _picture(rt, 'alert_triage', '1.0') is None, '그림 파일을 두지 않은 흐름'
    # 다시 켜도 그대로(같은 그림을 다시 쓰지 않는다)
    from procsvc.bpmn_store import FlowStore
    raw = _raw(DEFINITIONS / 'anomaly_response_v22.json')
    same = bpmn_store.provided_diagram(raw, (DEFINITIONS / 'anomaly_response.bpmn').read_text(encoding='utf-8'))
    assert FlowStore(rt.repo, rt.tenant_id).attach_diagram('anomaly_response', raw['version'], same) is False


def test_학생이_가져온_판본의_그림은_기본_제공_그림으로_덮이지_않는다(boot):
    rt = boot(old=False)
    from procsvc.bpmn_store import FlowStore
    store = FlowStore(rt.repo, rt.tenant_id)
    with rt.repo._conn() as c:
        c.execute("""insert into proc_def_version (arcv_id, proc_def_id, version, version_tag, tenant_id, definition, snapshot, message, origin)
                     values ('mine_1', 'mine', '1', 'hyd-immutable', 'hyd', '{}'::jsonb, '<mine/>', 'test', 'user')""")
    assert store.attach_diagram('mine', '1', '<other/>') is False and store.bpmn_of('mine', '1') == '<mine/>'

