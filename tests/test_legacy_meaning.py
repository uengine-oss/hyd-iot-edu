"""A9 옛 DB 뜻 복원: observation → agent candidates (grounded) → a person's review → only approved meanings reach the plan/graph."""
import copy
import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import engine, graph_ingest, ingest, legacy_meaning as lm, legacy_meaning_api as api
from procsvc.definition_registry import validate_definition
from procsvc.legacy_meaning_store import LegacyMeaningStore
from worker.runner import Runner
from test_worker import _settings, _fake_exec
from test_instances import rt

SAMPLE = Path(__file__).resolve().parents[1] / 'it/portal/www/samples/legacy-plant-db.sql'
TEXT = SAMPLE.read_text(encoding='utf8')
ONTOLOGY = {'stateVariables': [{'id': 'sv:ps1', 'name': '토출 압력', 'unit': 'bar', 'aliases': ['PS1']},
                               {'id': 'sv:ts1', 'name': '유온', 'unit': '℃', 'aliases': ['TS1']}],
            'measures': [{'id': 'msr:mttr', 'name': '평균 수리 시간', 'unit': 'h', 'aliases': []}],
            'assets': [{'id': 'asset:hyd-01', 'tag': 'HYD-01'}, {'id': 'asset:hyd-02', 'tag': 'HYD-02'}, {'id': 'asset:hyd-03', 'tag': 'HYD-03'}]}
K = lambda t, c: f'public.{t}.{c}'


def _req():
    return lm.request(filename='legacy-plant-db.sql', text=TEXT, tables=ingest.parse_ddl(TEXT), ontology=ONTOLOGY,
                      datasource='legacy-plant', catalog='postgres', by='강사')


def candidates(req=None):
    """An agent answer: three proposals, one honest no-evidence, the rest no-evidence too (a valid, if lazy, answer)."""
    req = req or _req()
    special = {
        K('T_EQP01', 'C_PRS_A'): dict(status='proposed', meaning='토출 압력', unit='bar', link={'kind': 'represents', 'target': 'sv:ps1'},
                                     evidence=[{'kind': 'name', 'text': 'PRS 조각'}, {'kind': 'sample', 'text': '164.1~182.4, 평균 179.6'}],
                                     confidence=0.72, alternatives=['흡입 압력']),
        K('T_EQP01', 'C_TMP_O'): dict(status='proposed', meaning='작동유 온도', unit='℃', link={'kind': 'represents', 'target': 'sv:ts1'},
                                     evidence=[{'kind': 'sample', 'text': '47.5~57.2'}], confidence=0.6),
        K('T_EQP01', 'EQP_CD'): dict(status='proposed', meaning='설비 코드', unit=None, link={'kind': 'asset_key', 'target': None},
                                    evidence=[{'kind': 'sample', 'text': 'HYD-01~03'}, {'kind': 'key', 'text': 'T_EQP00.EQP_CD와 값 겹침(추론)'}],
                                    confidence=0.9),
    }
    items = []
    for c in req['columns']:
        items.append(dict(column=c['key'], **special.get(c['key'], dict(status='no_evidence', meaning=None, unit=None,
                                                                         link={'kind': 'none', 'target': None}, evidence=[],
                                                                         confidence=0.1, reason='이름 조각만으로는 뜻을 정할 수 없음'))))
    return {'items': items, 'summary': '세 열은 근거가 있고 나머지는 근거 없음'}


# ---------------------------------------------------------------- observation
def test_profile_targets_code_named_columns_and_keeps_declared_apart_from_inferred_keys():
    req = _req()
    cols = {c['key']: c for c in req['columns']}
    assert len(cols) == 23 and req['samples'] == {'public.T_EQP00': 4, 'public.T_EQP01': 15, 'public.T_MNT10': 5}
    prs = cols[K('T_EQP01', 'C_PRS_A')]
    assert prs['name']['tokens'] == ['C', 'PRS', 'A'] and prs['samples']['min'] == 164.1 and prs['samples']['max'] == 182.4
    assert cols[K('T_EQP01', 'C_PRS_B')]['samples']['nulls'] == 15            # removed sensor: rows, but no values
    eqp = cols[K('T_EQP01', 'EQP_CD')]['keys']
    assert eqp['declared'] is None and {r['kind'] for r in eqp['inferred']} == {'추론'}      # no FK in the dump; overlap is inferred
    assert cols[K('T_EQP00', 'EQP_CD')]['keys']['primaryKey'] is True
    assert cols[K('T_EQP00', 'EQP_CD')]['assetTags'] == {'matched': 3, 'of': 4}             # HYD-00 is not an asset of the graph
    assert 'assetTags' not in prs                                                             # only text columns are compared to tags


def test_columns_with_a_comment_are_not_targets_and_copy_is_reported():
    text = 'CREATE TABLE t (a int, b int);\nCOMMENT ON COLUMN t.a IS \'토출 압력\';\nCOPY t (a, b) FROM stdin;'
    p = lm.profile(ingest.parse_ddl(text), text)
    assert [c['key'] for c in p['columns']] == ['public.t.b'] and any('COPY' in n for n in p['notes'])
    with pytest.raises(ValueError, match='뜻을 복원할 열이 없습니다'):
        lm.request(filename='x.sql', text='CREATE TABLE t (a int);\nCOMMENT ON COLUMN t.a IS \'압력\';', tables=ingest.parse_ddl(
            'CREATE TABLE t (a int);\nCOMMENT ON COLUMN t.a IS \'압력\';'), ontology=ONTOLOGY, datasource='d', catalog='c', by='x')


def test_the_sample_file_carries_no_answer_key():
    """정답 매핑 넣지 않음: no COMMENT, no REFERENCES, no meaning words next to the code names."""
    assert 'COMMENT ON' not in TEXT.upper() and 'REFERENCES' not in TEXT.upper()
    assert not re.search(r'C_PRS_A[^\n]*(압력|pressure)', TEXT, re.I)


# ---------------------------------------------------------------- proposal
def test_definition_is_a_product_shaped_agent_task():
    defn = validate_definition(lm.definition())
    a = defn.activities[lm.ACTIVITY]
    assert a['type'] == 'userTask' and a['agentMode'] == 'COMPLETE' and a['orchestration'] == 'cliagents' and engine.is_agent(a)
    assert defn.raw['forms']['legacy_meanings']['contract'] == lm.CONTRACT


def test_grounded_candidates_pass_in_request_order():
    req = _req()
    bad_order = candidates(req); bad_order['items'].reverse()
    out = lm.validate_candidates(req, bad_order)
    assert [i['column'] for i in out['items']] == [c['key'] for c in req['columns']]


@pytest.mark.parametrize('change, word', [
    (lambda r: r['items'].pop(), '열 수'),
    (lambda r: r['items'][0].update(column='public.T_EQP01.NOPE'), '요청에 없는 열'),
    (lambda r: r['items'].__setitem__(1, dict(r['items'][0])), '두 번'),
    (lambda r: _item(r, 'C_PRS_A').update(confidence=1.5), 'confidence'),
    (lambda r: _item(r, 'C_PRS_A').update(confidence=True), 'confidence'),
    (lambda r: _item(r, 'C_PRS_A').update(link={'kind': 'represents', 'target': 'sv:made-up'}), '목록에 없습니다'),
    (lambda r: _item(r, 'C_PRS_A').update(evidence=[]), '근거가 하나 이상'),
    (lambda r: _item(r, 'C_PRS_A').update(evidence=[{'kind': 'comment', 'text': '주석에 압력'}]), '주석 관찰이 없습니다'),
    (lambda r: _item(r, 'C_PRS_B').update(status='proposed', meaning='보조 압력', unit='bar', link={'kind': 'none', 'target': None},
                                          evidence=[{'kind': 'sample', 'text': '압력 범위'}]), '샘플 값 분포 관찰이 없습니다'),
    (lambda r: _item(r, 'C_PRS_A').update(link={'kind': 'asset_key', 'target': None}), '설비 태그와 하나도'),
    (lambda r: _item(r, 'ST_CD').update(meaning='상태 코드'), '추측으로 채우지'),
    (lambda r: _item(r, 'ST_CD').update(reason=''), 'reason'),
])
def test_ungrounded_or_malformed_candidates_are_refused(change, word):
    bad = candidates(); change(bad)
    with pytest.raises(ValueError, match=word):
        lm.validate_candidates(_req(), bad)


def _item(r, column):
    return next(i for i in r['items'] if i['column'].endswith('.' + column) and 'T_EQP01' in i['column'])


def test_agent_task_runs_and_candidates_are_read_back(rt, tmp_path):
    runtime, _ = rt
    inst = lm.start(runtime, _req(), str(uuid4()))
    runner = Runner(_settings(tmp_path / 'worker'), runtime.repo, exec_fn=_fake_exec(json.dumps({'meanings': candidates()})),
                    schema_prompt='StateVariable Measure', resolve_provider=lambda _: object())
    assert lm.result(runtime, inst['proc_inst_id'])['candidates'] is None                     # before the agent: nothing to review
    assert runner.poll_once() == 1
    wi = runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    task = json.loads((tmp_path / 'worker' / 'hyd' / wi['id'] / 'context' / 'task.json').read_text(encoding='utf8'))
    assert 'C_PRS_A' in task['query'] and 'sv:ps1' in task['query']                         # the agent sees observation + catalog
    assert runtime.poll_once() == 1
    out = lm.result(runtime, inst['proc_inst_id'])
    assert out['status'] == 'DONE' and len(out['candidates']) == 23
    assert next(c for c in out['candidates'] if c['column'] == K('T_EQP01', 'C_PRS_A'))['link'] == {'kind': 'represents', 'target': 'sv:ps1', 'name': '토출 압력', 'unit': 'bar'}


def test_an_ungrounded_candidate_goes_back_to_the_agent(rt):
    runtime, _ = rt
    inst = lm.start(runtime, _req(), str(uuid4()))
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    bad = candidates(); _item(bad, 'C_PRS_A')['link'] = {'kind': 'represents', 'target': 'sv:made-up'}
    assert runtime.repo.save_task_result(wi['id'], {'meanings': bad}, final=True)
    runtime.poll_once()
    row = runtime.repo.get_workitem(wi['id'])
    assert row['status'] == 'IN_PROGRESS' and row['draft_status'] == 'FB_REQUESTED' and '목록에 없습니다' in row['feedback']['text']
    pending = lm.result(runtime, inst['proc_inst_id'])
    assert pending['candidates'] is None and pending['corrections']['attempts'] == 1
    with pytest.raises(ValueError, match='아직 없습니다'):
        lm.candidates_of(runtime, inst['proc_inst_id'])


# ---------------------------------------------------------------- decision → plan
def _checked():
    req = _req()
    return req, lm.validate_candidates(req, candidates(req))['items']


def _review(decisions, by='강사'):
    req, cands = _checked()
    return lm.validate_review(req, cands, {'by': by, 'decisions': decisions})


APPROVE_PRS = {'column': K('T_EQP01', 'C_PRS_A'), 'verdict': 'APPROVE'}
REJECT_TMP = {'column': K('T_EQP01', 'C_TMP_O'), 'verdict': 'REJECT', 'note': '출구 온도일 수 있음'}
EDIT_KEY = {'column': K('T_EQP01', 'EQP_CD'), 'verdict': 'EDIT', 'meaning': '설비 번호', 'link': {'kind': 'asset_key', 'target': None}}


@pytest.mark.parametrize('body, word', [
    ({'decisions': [APPROVE_PRS]}, '검토자'),
    ({'by': 'x', 'decisions': []}, '하나 이상'),
    ({'by': 'x', 'decisions': [APPROVE_PRS, APPROVE_PRS]}, '두 번'),
    ({'by': 'x', 'decisions': [{'column': K('T_EQP01', 'ST_CD'), 'verdict': 'APPROVE'}]}, '근거 없음 후보는 승인할 수 없습니다'),
    ({'by': 'x', 'decisions': [{'column': K('T_EQP01', 'C_PRS_A'), 'verdict': 'OK'}]}, '결정은'),
    ({'by': 'x', 'decisions': [{'column': K('T_EQP01', 'C_PRS_A'), 'verdict': 'EDIT', 'meaning': ' '}]}, '뜻'),
    ({'by': 'x', 'decisions': [{'column': K('T_EQP01', 'C_PRS_A'), 'verdict': 'EDIT', 'meaning': '압력',
                                'link': {'kind': 'represents', 'target': 'sv:nope'}}]}, '목록에 없습니다'),
    ({'by': 'x', 'decisions': [{'column': 'public.T_EQP01.NOPE', 'verdict': 'REJECT'}]}, '후보에 없는 열'),
])
def test_review_input_is_checked(body, word):
    req, cands = _checked()
    with pytest.raises(ValueError, match=word):
        lm.validate_review(req, cands, body)


def test_reflection_holds_only_approved_and_edited_and_sql_is_quoted():
    review = _review([APPROVE_PRS, REJECT_TMP, dict(EDIT_KEY, meaning="설비 '번호'")])
    refl = lm.reflection(review)
    assert set(refl) == {K('T_EQP01', 'C_PRS_A'), K('T_EQP01', 'EQP_CD')}                   # rejected and undecided: nothing
    assert refl[K('T_EQP01', 'C_PRS_A')]['comment'] == '토출 압력 (bar)'
    assert lm.counts(review) == {'approved': 1, 'edited': 1, 'rejected': 1}
    assert 'COMMENT ON COLUMN "public"."T_EQP01"."EQP_CD" IS \'설비 \'\'번호\'\'\';' in lm.comment_sql(review)
    rejected = next(d for d in review['decisions'] if d['verdict'] == 'REJECT')
    assert rejected['after'] is None and rejected['before']['meaning'] == '작동유 온도'          # what the AI said stays in the audit


def _plan(review=None, review_id='review:test'):
    tables = ingest.parse_ddl(TEXT)
    refl = lm.apply_comments(tables, review) if review else None
    plan = ingest.plan(tables, filename='legacy-plant-db.sql', batch='ingest:ddl:t', datasource='legacy-plant', catalog='postgres')
    if review:
        lm.apply_links(plan, refl, review_id)
    return {i['column'] if i['table'] == 'T_EQP01' else i['table'] + '.' + i['column']: i for i in plan['inputs']}, plan


def test_before_approval_nothing_of_the_ai_reaches_the_plan():
    inputs, _ = _plan()
    assert inputs['C_PRS_A']['name'] == 'T_EQP01 C_PRS_A' and 'represents' not in inputs['C_PRS_A']
    assert all('meaningReview' not in i and 'represents' not in i and i['assetColumn'] is None for i in inputs.values())


def test_after_review_only_approved_meanings_and_links_are_in_the_plan():
    review = _review([APPROVE_PRS, REJECT_TMP, EDIT_KEY])
    inputs, plan = _plan(review)
    prs = inputs['C_PRS_A']
    assert prs['name'] == '토출 압력 (bar)' and prs['represents'] == 'sv:ps1' and prs['meaningReview'] == 'review:test'
    assert inputs['C_TMP_O']['name'] == 'T_EQP01 C_TMP_O' and 'represents' not in inputs['C_TMP_O']        # rejected
    assert inputs['C_VIB_F']['name'] == 'T_EQP01 C_VIB_F' and 'represents' not in inputs['C_VIB_F']        # undecided
    assert all(i['assetColumn'] == 'EQP_CD' for k, i in inputs.items() if '.' not in k)                      # edited asset key
    assert inputs['T_MNT10.MH_QT']['assetColumn'] is None                                                   # other table untouched
    ingest.validate_plan(plan)
    sql = ingest.tests_to_sql([{'variable': prs['variable'], 'operator': '<', 'value': 165}], {prs['variable']: prs})
    assert 'where "EQP_CD" = %(asset)s' in sql['queries'][0]['sql']                                           # rule → SQL now knows the asset


def _bridge(tmp_path, review):
    store = LegacyMeaningStore(tmp_path / 'lm.sqlite3')
    row = store.add('hyd', 'inst-1', 'wi-1', {'sha256': lm.text_sha256(TEXT), 'filename': 'legacy-plant-db.sql'}, review)
    return api.Bridge(lambda: store, 'hyd'), row


def test_commit_accepts_the_reviewed_plan_and_refuses_what_no_one_approved(tmp_path):
    review = _review([APPROVE_PRS, REJECT_TMP])
    bridge, row = _bridge(tmp_path, review)
    tables = ingest.parse_ddl(TEXT)
    got = bridge.review_for(row['id'], TEXT)
    refl = lm.apply_comments(tables, got['review'])
    plan = ingest.plan(tables, filename='f', batch='ingest:ddl:t', datasource='legacy-plant', catalog='postgres')
    info = bridge.applied(plan, got, refl)
    assert info['applied'] == [K('T_EQP01', 'C_PRS_A')] and info['approved'] == 1 and info['rejected'] == 1
    bridge.check_commit(plan)
    by_col = {i['column']: i for i in plan['inputs'] if i['table'] == 'T_EQP01'}
    for tamper, word in [
        (lambda p: by_col['C_TMP_O'].update(represents='sv:ts1'), '사람이 승인한'),                         # a rejected link smuggled in
        (lambda p: by_col['C_TMP_O'].update(meaningReview=row['id']), '승인하지 않은 열'),
        (lambda p: by_col['C_PRS_A'].update(name='흡입 압력'), '입력 이름'),
        (lambda p: by_col['C_PRS_A'].update(represents='sv:ts1'), '온톨로지 연결'),
        (lambda p: by_col['C_PRS_A'].update(meaningReview='review:none'), '기록이 없습니다'),
    ]:
        saved = copy.deepcopy(plan['inputs'])
        tamper(plan)
        with pytest.raises(ValueError, match=word):
            bridge.check_commit(plan)
        plan['inputs'][:] = saved
        by_col = {i['column']: i for i in plan['inputs'] if i['table'] == 'T_EQP01'}
    with pytest.raises(ValueError, match='다른 DDL'):
        bridge.review_for(row['id'], TEXT + '\n-- changed')


# ---------------------------------------------------------------- graph journal: REPRESENTS owned like SOURCED_FROM
class FakeResult:
    def __init__(self, rows=()):
        self.rows = [dict(r) for r in rows]
    def consume(self): return None
    def single(self): return self.rows[0] if self.rows else None
    def data(self): return self.rows
    def __iter__(self): return iter(self.rows)


class FakeGraph:
    """Just enough of Neo4j for graph_ingest's statements (no Neo4j in unit tests); each branch names the statement it serves."""
    def __init__(self):
        self.nodes, self.rels = {}, []
        for nid, label in [('sv:ps1', 'StateVariable'), ('sv:ts1', 'StateVariable')]:
            self.nodes[nid] = {'labels': {label}, 'props': {'id': nid}}

    def execute_write(self, fn): return fn(self)
    def execute_read(self, fn): return fn(self)

    def _set(self, nid, props):
        for k, v in props.items():
            if v is None: self.nodes[nid]['props'].pop(k, None)
            else: self.nodes[nid]['props'][k] = v

    def run(self, q, **p):
        q1 = ' '.join(q.split())
        if q1.startswith('CREATE CONSTRAINT') or q1.startswith('MERGE (n:IngestionControl'):
            return FakeResult()
        m = re.match(r'MATCH \(b:IngestionBatch \{id:\$id\}\) RETURN b\.fingerprint', q1)
        if m:
            n = self.nodes.get(p['id']); return FakeResult([{'fingerprint': n['props']['fingerprint'], 'status': n['props']['status']}] if n else [])
        if q1.startswith('MATCH (b:IngestionBatch {id:$id}) RETURN b.status'):
            n = self.nodes.get(p['id']); return FakeResult([{'status': n['props']['status']}] if n else [])
        if q1.startswith('MATCH (b:IngestionBatch {id:$id}) SET b.status="CLEARED"'):
            self.nodes[p['id']]['props']['status'] = 'CLEARED'; return FakeResult()
        if q1.startswith('CREATE (b:IngestionBatch'):
            self.nodes[p['id']] = {'labels': {'IngestionBatch'}, 'props': {'id': p['id'], 'fingerprint': p['fingerprint'], 'status': 'ACTIVE'}}
            return FakeResult()
        m = re.match(r'MATCH \(n:(\w+) \{id:\$id\}\) SET n\.id=n\.id RETURN properties\(n\) AS p', q1)
        if m:
            n = self.nodes.get(p['id'])
            return FakeResult([{'p': dict(n['props'])}] if n and m.group(1) in n['labels'] else [])
        if q1.startswith('MATCH (:InputData {id:$id})-[r:SOURCED_FROM|REPRESENTS]->(s) RETURN'):
            rows = [{'id': d, 'labels': sorted(self.nodes[d]['labels']), 'props': dict(rp), 'rel': t}
                    for s, t, d, rp in self.rels if s == p['id'] and t in ('SOURCED_FROM', 'REPRESENTS')]
            return FakeResult(sorted(rows, key=lambda r: (r['rel'] != 'SOURCED_FROM', r['id'])))
        m = re.match(r'CREATE \(n:(\w+) \{id:\$id\}\)', q1)
        if m:
            self.nodes[p['id']] = {'labels': {m.group(1)}, 'props': {'id': p['id']}}; return FakeResult()
        if re.match(r'MATCH \(n:\w+ \{id:\$id\}\) SET n \+= \$props', q1):
            self._set(p['id'], p['props']); return FakeResult()
        if re.match(r'MATCH \(n:\w+ \{id:\$id\}\) SET n \+= \$journal', q1):
            self._set(p['id'], p['journal']); return FakeResult()
        if q1.startswith('MATCH (:InputData {id:$id})-[r:SOURCED_FROM|REPRESENTS]->() DELETE r'):
            self.rels = [r for r in self.rels if not (r[0] == p['id'] and r[1] in ('SOURCED_FROM', 'REPRESENTS'))]; return FakeResult()
        m = re.match(r'MATCH \(n:InputData \{id:\$id\}\), \(s:(\w+) \{id:\$source\}\) MERGE \(n\)-\[r:(\w+)\]->\(s\)', q1)
        if m:
            ok = p['source'] in self.nodes and m.group(1) in self.nodes[p['source']]['labels']
            if ok: self.rels.append((p['id'], m.group(2), p['source'], p['props']))
            return FakeResult([{'n': int(ok)}])
        if q1.startswith('MATCH (x {id:$id}) WHERE x:StateVariable OR x:Measure RETURN labels(x)'):
            n = self.nodes.get(p['id'])
            return FakeResult([{'labels': sorted(n['labels'])}] if n and n['labels'] & {'StateVariable', 'Measure'} else [])
        if q1.startswith('MATCH (n:InputData {id:$id}) REMOVE n.sourceBaseComment'):
            self.nodes[p['id']]['props'].pop('sourceBaseComment', None); return FakeResult()
        m = re.match(r'MATCH \(n:(\w+)\) WHERE \$batch IN n\._ingest_batches RETURN n\.id AS id', q1)
        if m:
            return FakeResult(sorted(({'id': k} for k, n in self.nodes.items() if m.group(1) in n['labels']
                                      and p['batch'] in (n['props'].get('_ingest_batches') or [])), key=lambda r: r['id']))
        m = re.match(r'MATCH \(n:\w+ \{id:\$id\}\) SET n\._ingest_history=\$history', q1)
        if m:
            self._set(p['id'], {'_ingest_history': p['history'], '_ingest_batches': p['batches']}); return FakeResult()
        if 'WHERE NOT (type(r) IN ["SOURCED_FROM","REPRESENTS"] AND startNode(r)=n)' in q1:
            return FakeResult([{'n': sum(1 for s, t, d, _ in self.rels if (d == p['id']) or (s == p['id'] and t not in ('SOURCED_FROM', 'REPRESENTS')))}])
        m = re.match(r'MATCH \(n:\w+ \{id:\$id\}\) RETURN labels\(n\) AS labels', q1)
        if m:
            return FakeResult([{'labels': sorted(self.nodes[p['id']]['labels'])}])
        m = re.match(r'MATCH \(n:\w+ \{id:\$id\}\) OPTIONAL MATCH \(n\)-\[r\]-\(\) RETURN count\(r\) AS n', q1)
        if m:
            return FakeResult([{'n': sum(1 for s, _, d, _ in self.rels if p['id'] in (s, d))}])
        m = re.match(r'MATCH \(n:\w+ \{id:\$id\}\) DELETE n', q1)
        if m:
            del self.nodes[p['id']]; return FakeResult()
        raise AssertionError('unexpected statement: ' + q1[:120])

    def rel(self, src, kind):
        return [d for s, t, d, _ in self.rels if s == src and t == kind]


def test_graph_journal_writes_represents_only_for_the_approved_input_and_clear_removes_it():
    review = _review([APPROVE_PRS, REJECT_TMP])
    _, plan = _plan(review)
    plan = {k: plan[k] for k in ('batch', 'filename', 'systems', 'inputs')}
    g = FakeGraph()
    out = graph_ingest.commit(g, plan)
    assert out['inputs'] == len(plan['inputs'])
    ids = {i['column']: i['id'] for i in plan['inputs'] if i['table'] == 'T_EQP01'}
    assert g.rel(ids['C_PRS_A'], 'REPRESENTS') == ['sv:ps1'] and g.nodes[ids['C_PRS_A']]['props']['name'] == '토출 압력 (bar)'
    assert g.rel(ids['C_TMP_O'], 'REPRESENTS') == [] and g.nodes[ids['C_TMP_O']]['props']['name'] == 'T_EQP01 C_TMP_O'
    represents = [(s, d) for s, t, d, _ in g.rels if t == 'REPRESENTS']
    assert represents == [(ids['C_PRS_A'], 'sv:ps1')]                                       # the graph holds one link: the approved one
    assert 'represents' not in g.nodes[ids['C_PRS_A']]['props'] and 'meaningReview' not in g.nodes[ids['C_PRS_A']]['props']
    cleared = graph_ingest.clear(g, plan['batch'])
    assert cleared['deleted'] == len(plan['inputs']) + 1 and not [r for r in g.rels if r[1] == 'REPRESENTS']
    assert 'sv:ps1' in g.nodes                                                            # the ontology node itself is untouched


def test_graph_journal_refuses_a_link_to_a_node_that_is_not_in_the_graph():
    review = _review([APPROVE_PRS])
    _, plan = _plan(review)
    g = FakeGraph(); del g.nodes['sv:ps1']
    with pytest.raises(graph_ingest.Conflict, match='그래프에 없거나'):
        graph_ingest.commit(g, {k: plan[k] for k in ('batch', 'filename', 'systems', 'inputs')})


def test_history_written_before_a9_still_compares_equal():
    """An input ingested before A9 has a SOURCED_FROM-only journal; re-reading it must not look like someone else's edit."""
    _, plan = _plan()
    plan = {k: plan[k] for k in ('batch', 'filename', 'systems', 'inputs')}
    g = FakeGraph()
    graph_ingest.commit(g, plan)
    nid = plan['inputs'][0]['id']
    hist = json.loads(g.nodes[nid]['props']['_ingest_history'])
    assert all('rel' not in s for s in hist[-1]['state']['sources'])
    graph_ingest.commit(g, dict(plan, batch='ingest:ddl:second'))                          # re-claim: no Conflict


# ---------------------------------------------------------------- HTTP: the AI path must exist; a review is audited per decision
class FakeDriver:
    def __init__(self, fail=False): self.fail = fail
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def session(self): return self
    def run(self, q):
        if self.fail: raise OSError('neo4j down')
        if 'Asset' in q: return FakeResult(ONTOLOGY['assets'])
        return FakeResult([dict(label='StateVariable', **v) for v in ONTOLOGY['stateVariables']]
                          + [dict(label='Measure', **v) for v in ONTOLOGY['measures']])


def _app(runtime, tmp_path, worker=True, graph_fail=False):
    app, audits = FastAPI(), []
    store = LegacyMeaningStore(tmp_path / 'lm.sqlite3')
    api.register(app, driver_factory=lambda: FakeDriver(graph_fail), tenant='hyd', audit=lambda *a: audits.append(a),
                 runtime_factory=lambda: runtime, store_factory=lambda: store,
                 worker_probe=lambda: {'reachable': worker, 'url': 'http://agent-worker:8097', 'error': None if worker else 'ConnectError'})
    return TestClient(app), audits


def test_no_ai_path_is_a_clear_error_not_an_empty_success(rt, tmp_path):
    runtime, _ = rt
    client, _ = _app(None, tmp_path)
    r = client.post('/api/kg/ddl/meanings', json={'filename': 'x.sql', 'text': TEXT})
    assert r.status_code == 503 and 'instance' in r.json()['detail']
    client, audits = _app(runtime, tmp_path, worker=False)
    r = client.post('/api/kg/ddl/meanings', json={'filename': 'x.sql', 'text': TEXT})
    assert r.status_code == 503 and '워커' in r.json()['detail'] and not audits
    assert not [i for i in runtime.repo.list_instances() if i['proc_def_id'] == lm.DEFINITION_ID]     # refused: no task opened
    client, _ = _app(runtime, tmp_path, graph_fail=True)
    r = client.post('/api/kg/ddl/meanings', json={'filename': 'x.sql', 'text': TEXT})
    assert r.status_code == 502 and '온톨로지' in r.json()['detail']


def test_http_flow_request_read_review_and_audit(rt, tmp_path):
    runtime, _ = rt
    client, audits = _app(runtime, tmp_path)
    r = client.post('/api/kg/ddl/meanings', json={'filename': 'legacy-plant-db.sql', 'text': TEXT, 'by': '강사', 'datasource': 'legacy-plant'})
    assert r.status_code == 200, r.text
    pid = r.json()['instance']
    early = client.post(f'/api/kg/ddl/meanings/{pid}/reviews', json={'by': '강사', 'decisions': [APPROVE_PRS]})
    assert early.status_code == 400 and '아직 없습니다' in early.json()['detail']               # nothing to approve before the agent
    wi = runtime.repo.fetch_pending_task('cliagents', 'test-worker')[0]
    pinned = engine.variables(runtime.repo.get_instance(pid))['legacy_request']
    runtime.repo.save_task_result(wi['id'], {'meanings': candidates(pinned)}, final=True)
    runtime.poll_once()
    got = client.get(f'/api/kg/ddl/meanings/{pid}').json()
    assert got['status'] == 'DONE' and len(got['candidates']) == 23 and got['reviews'] == []
    r = client.post(f'/api/kg/ddl/meanings/{pid}/reviews', json={'by': '강사', 'decisions': [APPROVE_PRS, REJECT_TMP]})
    assert r.status_code == 200, r.text
    review = r.json()
    assert review['approved'] == 1 and review['rejected'] == 1 and review['undecided'] == 21
    assert [x['column'] for x in review['reflected']] == [K('T_EQP01', 'C_PRS_A')]
    events = [a[2] for a in audits]
    assert events == ['DDL_MEANING_REQUESTED', 'DDL_MEANING_APPROVED', 'DDL_MEANING_REJECTED', 'DDL_MEANING_REVIEWED']
    rejected = next(a for a in audits if a[2] == 'DDL_MEANING_REJECTED')[3]
    assert rejected['before']['meaning'] == '작동유 온도' and rejected['after'] is None and rejected['note'] == '출구 온도일 수 있음'
    second = client.post(f'/api/kg/ddl/meanings/{pid}/reviews', json={'by': '수강생', 'decisions': [{'column': K('T_EQP01', 'C_PRS_A'), 'verdict': 'REJECT'}]})
    assert second.status_code == 200 and second.json()['reflected'] == []                   # same candidates, a different decision
    assert [x['by'] for x in client.get(f'/api/kg/ddl/meanings/{pid}').json()['reviews']] == ['수강생', '강사']
    assert client.get('/api/kg/ddl/meanings/' + str(uuid4())).status_code == 404


# ---------------------------------------------------------------- the real DDL routes (main.py): preview applies a review, commit checks it
class GraphDriver:
    def __init__(self, graph): self.graph = graph
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def session(self): return GraphSession(self.graph)


class GraphSession:
    def __init__(self, graph): self.graph = graph
    def __enter__(self): return self.graph
    def __exit__(self, *a): return False


def test_ddl_preview_and_commit_routes_reflect_only_the_review(tmp_path, monkeypatch):
    from procsvc import main
    review = _review([APPROVE_PRS, REJECT_TMP])
    bridge, row = _bridge(tmp_path, review)
    graph, audits = FakeGraph(), []
    monkeypatch.setattr(main, '_legacy', bridge)
    monkeypatch.setattr(main, '_q', lambda *a, **k: [])
    monkeypatch.setattr(main, '_kg', lambda: GraphDriver(graph))
    monkeypatch.setattr(main, '_ddl_sync_once', lambda: {'changed': 0})
    monkeypatch.setattr(main, '_audit', lambda *a, **k: audits.append(a))
    client = TestClient(main.app)
    body = {'filename': 'legacy-plant-db.sql', 'text': TEXT, 'datasource': 'legacy-plant', 'catalog': 'postgres'}
    plain = client.post('/api/kg/ddl/preview', json=body).json()
    assert plain['legacy']['targets'] == 23 and 'meaningReview' not in plain
    assert not [i for i in plain['inputs'] if 'represents' in i]                                  # 승인 전 반영 0
    reviewed = client.post('/api/kg/ddl/preview', json=dict(body, meaning_review=row['id'])).json()
    assert reviewed['meaningReview']['applied'] == [K('T_EQP01', 'C_PRS_A')] and reviewed['meaningReview']['rejected'] == 1
    assert [i['column'] for i in reviewed['inputs'] if i.get('represents')] == ['C_PRS_A']
    assert client.post('/api/kg/ddl/preview', json=dict(body, text=TEXT + ' ', meaning_review=row['id'])).status_code == 400
    smuggled = copy.deepcopy(reviewed)
    next(i for i in smuggled['inputs'] if i['column'] == 'C_TMP_O')['represents'] = 'sv:ts1'
    r = client.post('/api/kg/ddl/commit', json=dict(smuggled, by='강사'))
    assert r.status_code == 400 and '승인' in r.json()['detail'] and not graph.rels                  # refused before the graph
    r = client.post('/api/kg/ddl/commit', json=dict(reviewed, by='강사'))
    assert r.status_code == 200, r.text
    assert [(t, d) for s, t, d, _ in graph.rels if t == 'REPRESENTS'] == [('REPRESENTS', 'sv:ps1')]
    assert [a[2] for a in audits] == ['DDL_INGESTED']
