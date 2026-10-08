"""A4 (U6) — AI 판단 채점: 경보 판단(원인 · 조치 카드)을 사람이 적은 정답표에 대어 점수를 내고, 실행 단위로 남겨 지식 고치기 전·후를 비교한다.

회의 L136~138: 온톨로지가 잘 구성됐는지는 "그런 상황을 던졌을 때 진단 · 판단을 정확히 하고 액션까지 수행하는지"로 확인한다.
여기서는 그 확인을 반복 가능하게 만든다.

  정답표  **데이터**다. 코드 · 시드 · 파일에 정답이 없다. 강사 · 수강생이 포털(또는 CLI · API)에서 항목을 적어 저장하고, 처음엔 비어 있다.
          항목 = 경보 상황(설비 · 패턴 · 가정 사실) + 기대 원인 · 고장 유형, 1위로 허용되는 조치, 빠져야 할 조치(제외돼야 / 1위면 안 됨),
          근거에 있어야 할 지식 id. validate_item()은 모양만 검사하고, 이름이 지식 그래프에 있는지는 eval_api 가 그래프에 묻는다.
  채점    score_judgement(item, judged) — 순수 함수(A10 이 같은 함수를 쓴다). 원인 적중 · 1위 허용 · 빠질 조치 미추천 · 근거 포함률 → 가중 합(0~100).
          judged 는 normalize_decision()(agent /api/agent/decide 응답 · process 가 받은 판단) 또는 normalize_evaluation()
          (agent /api/agent/evaluate 실행 기록) · worker_judgement()(지난 처리 건의 실제 워커 출력)이 같은 모양으로 만든다.
  반복    aggregate() — 같은 항목 N회의 평균 · 최저 · 최고 · 흔들림(최빈 결과 비율). N회가 모두 같으면 identical=True(결정론 — 1회와 같다).
  전후    compare(run_a, run_b) — 항목별 점수 변화 + knowledge_diff()로 두 실행 사이 지식 그래프에서 끊긴 · 생긴 관계와 바뀐 항목(E5).
순수 로직이다(네트워크 · DB 없음). 저장소(MemoryEvalStore · PgEvalStore)만 I/O 를 한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import threading
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

DEFAULT_WEIGHTS = {'cause': 0.3, 'top': 0.3, 'forbidden': 0.2, 'evidence': 0.2}
FORBIDDEN_EXPECTS = ('excluded', 'not_recommended')
PATHS = ('decide', 'evaluate', 'worker')
MAX_REPEATS = 10
NOT_JUDGED = ('WITHHELD', 'ERROR', 'EMPTY', 'FAILED', 'REJECTED_BY_GUARDRAIL')
ITEM_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,63}$')
PATH_NOTES = {
    'decide': '규칙 판단(agent /api/agent/decide) — LLM 없이 결정론적이다. 같은 지식 · 같은 사실이면 1회로 충분하고, N>1 은 실시간 근거 값이 바뀔 때의 흔들림만 잰다. 정답표의 가정 사실을 그대로 넣는다.',
    'evaluate': '에이전트 읽기 평가(agent /api/agent/evaluate) — 경보 한 건을 전체 파이프라인(근거 조회 → 원인 → 조치 카드 → 가드레일)으로 돌리되 제출하지 않는다. 사실은 지금 설비 · 업무 DB 값이며, 정답표 가정과 다르면 항목에 표시한다.',
    'worker': '지난 처리 건 — 실제 AI 일꾼(워커)이 낸 원인 · 근거와 제출된 조치 판단을 채점한다. 같은 항목에 맞는 처리 건 여러 개는 반복으로 묶어 흔들림을 잰다.',
}
BOOKKEEPING_LABELS = ['ManualIngestionBatch', 'ManualIngestionDocument', 'IngestionBatch', 'IngestionControl', 'KnowledgeEdit']
SNAPSHOT_CAP = 50000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(',', ':'))


def _digest(value, n: int = 12) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()[:n]


# ---------------------------------------------------------------- 정답표 항목 (데이터)
SCORED_FIELDS = ('asset', 'pattern', 'facts', 'expected', 'allowed_top', 'forbidden', 'required_evidence')


def validate_item(item: dict) -> dict:
    """정답표 항목 하나의 모양 검사 → 정리된 항목. 좌표(field)를 붙인 ValueError 로 거부한다 — 빈 정답으로 채점이 '성공'하지 않도록."""
    if not isinstance(item, dict):
        raise ValueError('정답표 항목은 객체여야 합니다')
    iid = str(item.get('id') or '').strip()
    if not ITEM_ID.match(iid):
        raise ValueError('id 는 영문 소문자 · 숫자 · 하이픈 2~64자여야 합니다 (예: cooler-auto)')
    out = {'id': iid}
    for key in ('title', 'asset', 'pattern'):
        v = item.get(key)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f'{key} 가 비어 있습니다')
        out[key] = v.strip()
    facts = item.get('facts', {})
    if not isinstance(facts, dict):
        raise ValueError('facts 는 객체여야 합니다 (가정 사실이 없으면 {})')
    out['facts'] = {str(k): v for k, v in facts.items() if v is not None and v != ''}
    exp = item.get('expected')
    if not isinstance(exp, dict) or not str(exp.get('cause') or '').startswith('cause:') or not str(exp.get('failure_mode') or '').startswith('fm:'):
        raise ValueError('expected 에 원인(cause:…)과 고장 유형(fm:…)이 필요합니다')
    out['expected'] = {'cause': exp['cause'].strip(), 'failure_mode': exp['failure_mode'].strip()}
    allowed = item.get('allowed_top')
    if not isinstance(allowed, list) or not allowed or any(not isinstance(s, str) or not s.startswith('skill:') for s in allowed):
        raise ValueError('allowed_top 은 1위로 허용되는 조치(skill:…) 목록(1개 이상)이어야 합니다')
    out['allowed_top'] = list(dict.fromkeys(s.strip() for s in allowed))
    forbidden = item.get('forbidden') or []
    if not isinstance(forbidden, list):
        raise ValueError('forbidden 은 목록이어야 합니다')
    out['forbidden'] = []
    for j, f in enumerate(forbidden):
        if not isinstance(f, dict) or not str(f.get('skill') or '').startswith('skill:') or f.get('expect') not in FORBIDDEN_EXPECTS:
            raise ValueError(f"forbidden[{j}] 은 {{skill: skill:…, expect: {' | '.join(FORBIDDEN_EXPECTS)}}} 이어야 합니다")
        if f['skill'] in out['allowed_top']:
            raise ValueError(f"forbidden[{j}].skill '{f['skill']}' 이 allowed_top 에도 있습니다")
        if f.get('rule') is not None and not str(f['rule']).startswith('rule:'):
            raise ValueError(f'forbidden[{j}].rule 은 rule:… 이어야 합니다')
        out['forbidden'].append({k: f[k] for k in ('skill', 'expect', 'rule', 'why') if f.get(k)})
    if len({f['skill'] for f in out['forbidden']}) != len(out['forbidden']):
        raise ValueError('forbidden 에 같은 조치가 두 번 있습니다')
    req = item.get('required_evidence')
    if not isinstance(req, list) or not req or any(not isinstance(r, str) or not r.strip() for r in req):
        raise ValueError('required_evidence 는 근거에 있어야 할 지식 id 목록(1개 이상)이어야 합니다')
    out['required_evidence'] = list(dict.fromkeys(r.strip() for r in req))
    out['note'] = str(item.get('note') or '')[:500]
    return out


def item_hash(item: dict) -> str:
    """채점에 쓰이는 필드만의 지문. 정답표를 고친 뒤의 실행과 고치기 전 실행을 비교하면 compare()가 '정답표 바뀜'으로 표시한다."""
    return _digest({k: item.get(k) for k in SCORED_FIELDS})


def referenced_ids(item: dict) -> list[str]:
    """항목이 인용하는 지식 id 전부 (eval_api 가 그래프에 있는지 묻는다). 설비 · 패턴 이름은 agent 가 판단 때 확인한다."""
    out = [item['expected']['cause'], item['expected']['failure_mode'], *item['allowed_top'], *item['required_evidence']]
    for f in item.get('forbidden') or []:
        out.append(f['skill'])
        if f.get('rule'):
            out.append(f['rule'])
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- 판단 결과를 한 모양으로
def _cited_from_options(options: list[dict]) -> set[str]:
    ids: set[str] = set()
    for o in options or []:
        for key in ('selectedBy', 'violations', 'penalties', 'warnings'):
            for r in o.get(key) or []:
                if r.get('rule'):
                    ids.add(r['rule'])
                ids.update(s for s in (r.get('sources') or []) if isinstance(s, str))
        if o.get('sopId'):
            ids.add(o['sopId'])
        for s in o.get('steps') or []:
            m = s.get('manual') if isinstance(s, dict) else None
            if isinstance(m, dict) and m.get('ref'):
                ids.add(m['ref'])
    return ids


def normalize_decision(decision: dict, causes: list[dict] | None = None, extra_cited: list[str] | None = None) -> dict:
    """agent /api/agent/decide 응답(causes 포함) 또는 process 가 받은 조치 판단(book: options · recommended · facts) → 채점 입력.
    원인은 causes[0](점수순)에서, 없으면 판단 origin/facts 의 cause 에서 읽는다."""
    result = decision.get('result') if isinstance(decision.get('result'), dict) else decision
    options = result.get('options') or []
    causes = causes if causes is not None else decision.get('causes') or []
    top = causes[0] if causes else None
    facts = decision.get('facts') or {}
    origin = decision.get('origin') or {}
    cause = (top or {}).get('id') or facts.get('cause') or origin.get('cause')
    fm = (top or {}).get('failureModeId') or facts.get('failure_mode') or origin.get('failureMode')
    cited: set[str] = set()
    for c in causes:
        for e in c.get('evidence') or []:
            if e.get('passed') is True and e.get('id'):
                cited.add(e['id'])
    cited |= _cited_from_options(options)
    rr = result.get('rankRule')
    if isinstance(rr, dict):
        if rr.get('rule'):
            cited.add(rr['rule'])
        cited.update(s for s in (rr.get('sources') or []) if isinstance(s, str))
    for t in result.get('trace') or []:
        if t.get('fired') and t.get('rule'):
            cited.add(t['rule'])
    cited.update(x for x in (extra_cited or []) if isinstance(x, str))
    status = decision.get('status') or ('EVALUATED' if options else 'EMPTY')
    recommended = result.get('recommended') or decision.get('recommended')
    return {'status': status, 'cause': cause, 'failure_mode': fm, 'recommended': recommended,
            'options': [{'id': o.get('id'), 'rank': o.get('rank'), 'feasible': bool(o.get('feasible')), 'score': o.get('score'),
                         'violations': [v.get('rule') for v in o.get('violations') or []]} for o in options],
            'cited': sorted(cited), 'facts_used': {k: v for k, v in facts.items() if k not in ('cause', 'failure_mode')},
            'decision_id': decision.get('id'), 'reason': decision.get('error')}


def normalize_evaluation(run: dict) -> dict:
    """agent /api/agent/evaluate 의 실행 기록(run.to_dict) → 채점 입력. 원인 · 근거는 가이드 카드에서, 조치 순위는 run.evaluation 에서."""
    status = run.get('status')
    if status != 'EVALUATED' or not isinstance(run.get('evaluation'), dict):
        reason = run.get('error') or ((run.get('card') or {}).get('summary')) or '에이전트가 판단을 내지 못했습니다'
        return withheld(f'{status or "상태 없음"}: {reason}', status='WITHHELD' if status in ('WITHHELD', None) else
                        'REJECTED_BY_GUARDRAIL' if status == 'REJECTED_BY_GUARDRAIL' else 'ERROR')
    card = run.get('card') or {}
    j = normalize_decision(run['evaluation'], causes=card.get('causes') or [], extra_cited=card.get('citations') or [])
    j['status'] = 'EVALUATED' if j['options'] else 'EMPTY'
    j['run_id'] = run.get('id')
    return j


def withheld(reason: str, status: str = 'WITHHELD') -> dict:
    return {'status': status, 'cause': None, 'failure_mode': None, 'recommended': None, 'options': [], 'cited': [], 'facts_used': {},
            'decision_id': None, 'reason': reason}


# ---------------------------------------------------------------- 채점 (순수 함수 — A10 이 그대로 쓴다)
def score_judgement(item: dict, judged: dict, weights: dict | None = None) -> dict:
    """정답표 항목 하나 × 판단 하나 → 점수(0~100)와 검사 네 칸. 판단이 없거나(보류 · 오류 · 가드레일) 후보가 비면 0점이다(부분 점수 없음)."""
    w = weights or DEFAULT_WEIGHTS
    exp = item['expected']
    by_id = {o['id']: o for o in judged.get('options') or []}
    rec = judged.get('recommended')
    cause_ok = judged.get('cause') == exp['cause'] and judged.get('failure_mode') == exp['failure_mode']
    top_ok = bool(rec) and rec in item['allowed_top']
    details = []
    for f in item.get('forbidden') or []:
        o = by_id.get(f['skill'])
        if f['expect'] == 'excluded':
            ok = o is None or (not o['feasible'])              # 후보에 없거나(원인 한정으로 걸러짐) 규칙으로 제외됐다
            got = '후보 아님' if o is None else ('제외됨 (' + ', '.join(x for x in o['violations'] if x) + ')' if not o['feasible'] else f"실행 가능 · {o['rank']}위")
        else:
            ok = rec != f['skill']
            got = '1위 추천됨' if rec == f['skill'] else ('후보 아님' if o is None else f"{o['rank']}위")
        details.append({'skill': f['skill'], 'expect': f['expect'], 'rule': f.get('rule'), 'ok': ok, 'got': got})
    forbidden_ratio = (sum(d['ok'] for d in details) / len(details)) if details else 1.0
    cited = set(judged.get('cited') or [])
    found = [e for e in item['required_evidence'] if e in cited]
    missing = [e for e in item['required_evidence'] if e not in cited]
    evidence_ratio = len(found) / len(item['required_evidence'])
    if judged.get('status') in NOT_JUDGED:
        cause_ok = top_ok = False
        forbidden_ratio = evidence_ratio = 0.0
        details = [dict(d, ok=False, got=judged.get('status')) for d in details]
    used = judged.get('facts_used') or {}
    mismatch = [{'key': k, 'want': v, 'got': used.get(k)} for k, v in (item.get('facts') or {}).items() if k in used and used[k] != v]
    score = 100 * (w['cause'] * cause_ok + w['top'] * top_ok + w['forbidden'] * forbidden_ratio + w['evidence'] * evidence_ratio)
    return {'score': round(score, 1), 'status': judged.get('status'), 'reason': judged.get('reason'),
            'outcome': f"{judged.get('cause') or '-'} → {rec or '-'}",
            'checks': {'cause': {'ok': cause_ok, 'got': judged.get('cause'), 'got_failure_mode': judged.get('failure_mode'), 'want': exp['cause'], 'want_failure_mode': exp['failure_mode']},
                       'top': {'ok': top_ok, 'got': rec, 'allowed': list(item['allowed_top']),
                               'order': [f"{o['rank']}. {o['id']}" + ('' if o['feasible'] else ' (제외)') for o in judged.get('options') or []]},
                       'forbidden': {'ok': forbidden_ratio == 1.0, 'ratio': round(forbidden_ratio, 3), 'detail': details},
                       'evidence': {'ok': evidence_ratio == 1.0, 'ratio': round(evidence_ratio, 3), 'found': found, 'missing': missing}},
            'facts_mismatch': mismatch, 'decision_id': judged.get('decision_id'), 'run_id': judged.get('run_id')}


def aggregate(item: dict, judged_runs: list[dict], weights: dict | None = None, *, deterministic: bool = False) -> dict:
    """같은 항목 N회 → 평균 · 최저 · 최고 · 흔들림. identical=True 면 N회가 모두 같은 결과 · 같은 점수(결정론 — 1회와 같다)."""
    if not judged_runs:
        raise ValueError(f"항목 {item['id']} 의 판단 결과가 없습니다")
    runs = [score_judgement(item, j, weights) for j in judged_runs]
    outcomes = Counter(r['outcome'] for r in runs)
    modal, modal_n = outcomes.most_common(1)[0]
    scores = [r['score'] for r in runs]
    last = runs[-1]
    return {'item': item['id'], 'title': item['title'], 'asset': item['asset'], 'pattern': item['pattern'], 'facts': item.get('facts') or {},
            'item_hash': item_hash(item), 'expected': {k: item[k] for k in ('expected', 'allowed_top', 'forbidden', 'required_evidence')},
            'repeats': len(runs), 'score': round(statistics.fmean(scores), 1), 'min': min(scores), 'max': max(scores),
            'stability': round(modal_n / len(runs), 3), 'modal_outcome': modal, 'outcomes': dict(outcomes),
            'identical': len(outcomes) == 1 and min(scores) == max(scores), 'deterministic': deterministic,
            'checks': last['checks'], 'status': last['status'], 'reason': last['reason'], 'facts_mismatch': last['facts_mismatch'],
            'runs': runs}


def summarize(results: list[dict]) -> dict:
    if not results:
        raise ValueError('채점할 항목이 없습니다')
    scores = [r['score'] for r in results]
    return {'items': len(results), 'score': round(statistics.fmean(scores), 1), 'perfect': sum(1 for s in scores if s >= 100),
            'withheld': sum(1 for r in results if r['status'] in NOT_JUDGED),
            'unstable': sum(1 for r in results if r['stability'] < 1.0),
            'cause_hits': sum(1 for r in results if r['checks']['cause']['ok']), 'top_ok': sum(1 for r in results if r['checks']['top']['ok']),
            'forbidden_ok': sum(1 for r in results if r['checks']['forbidden']['ok']), 'evidence_ok': sum(1 for r in results if r['checks']['evidence']['ok'])}


def new_run(*, path: str, by: str, repeats: int, knowledge: dict, results: list[dict], note: str | None = None) -> dict:
    if path not in PATHS:
        raise ValueError(f"path 는 {' | '.join(PATHS)} 중 하나입니다")
    if not isinstance(by, str) or not by.strip():
        raise ValueError('누가 실행했는지(by)가 필요합니다')
    rid = 'EVAL-' + datetime.now(timezone.utc).strftime('%m%d-%H%M%S') + '-' + uuid4().hex[:4]
    return {'id': rid, 'created': _now(), 'by': by.strip()[:120], 'path': path, 'repeats': repeats,
            'golden_version': _digest(sorted(r['item_hash'] for r in results)),
            'knowledge': knowledge, 'summary': summarize(results), 'items': results, 'note': (note or '')[:500]}


# ---------------------------------------------------------------- 지식 상태 (E5: 관계 하나 끊기 · 매뉴얼 하나 더 넣기)
KNOWLEDGE_Q = '''
MATCH (n) WITH count(n) AS nodes
OPTIONAL MATCH ()-[r]->() WITH nodes, count(r) AS rels
OPTIONAL MATCH (k:Skill) WITH nodes, rels, count(k) AS skills
OPTIONAL MATCH (ru:Rule) WITH nodes, rels, skills, count(ru) AS rules
OPTIONAL MATCH (mb:ManualIngestionBatch) WITH nodes, rels, skills, rules, max(mb.createdAt) AS manual_at, count(mb) AS manual_batches
OPTIONAL MATCH (ib:IngestionBatch) WITH nodes, rels, skills, rules, manual_at, manual_batches, max(ib.createdAt) AS ddl_at
OPTIONAL MATCH (e:KnowledgeEdit) WITH nodes, rels, skills, rules, manual_at, manual_batches, ddl_at, max(toString(e.created_at)) AS edit_at, count(e) AS edits
RETURN nodes, rels, skills, rules, manual_at, manual_batches, ddl_at, edit_at, edits
'''
KNOWLEDGE_RELS_Q = '''
MATCH (a)-[r]->(b) WHERE a.id IS NOT NULL AND b.id IS NOT NULL
RETURN a.id AS a, type(r) AS t, b.id AS b
'''
KNOWLEDGE_NODES_Q = '''
MATCH (n) WHERE n.id IS NOT NULL AND NONE(l IN labels(n) WHERE l IN $skip)
RETURN n.id AS id, labels(n) AS labels, properties(n) AS props
'''


def knowledge_state(rows: list[dict], rels: list[dict] | None = None, nodes: list[dict] | None = None) -> dict:
    """그래프 읽은 결과 → 실행에 붙일 지식 상태.
    fingerprint 는 관계 (id)-[유형]->(id) 전부와 항목 속성의 지문이라, 기록이 남지 않는 변경(Neo4j Browser 에서 관계 하나 끊기)도 잡는다.
    snapshot(관계 목록 · 항목별 지문)은 compare()가 무엇이 바뀌었는지 보여 주려고 남긴다. 변경 시각 기록이 없으면 지어내지 않는다."""
    if not rows:
        raise ValueError('지식 그래프에서 상태를 읽지 못했습니다')
    r = rows[0]
    stamps = [str(r[k]) for k in ('manual_at', 'ddl_at', 'edit_at') if r.get(k)]
    rel_keys = sorted({f"{x['a']}|{x['t']}|{x['b']}" for x in rels or []})
    node_fp = {str(x['id']): _digest([sorted(x.get('labels') or []), x.get('props') or {}], 10) for x in nodes or []}
    out = {'nodes': r.get('nodes'), 'relationships': r.get('rels'), 'skills': r.get('skills'), 'rules': r.get('rules'),
           'manual_batches': r.get('manual_batches'), 'edits': r.get('edits'),
           'last_change': max(stamps) if stamps else None, 'last_change_note': None if stamps else '기록된 변경 없음 (초기 적재본 또는 기록 없는 직접 수정)',
           'fingerprint': _digest([rel_keys, sorted(node_fp.items())]) if rels is not None and nodes is not None else None,
           'read_at': _now()}
    if rels is not None and nodes is not None and len(rel_keys) + len(node_fp) <= SNAPSHOT_CAP:
        out['snapshot'] = {'rels': rel_keys, 'nodes': node_fp}
    return out


def public_knowledge(k: dict | None) -> dict:
    return {key: v for key, v in (k or {}).items() if key != 'snapshot'}


def knowledge_diff(a: dict | None, b: dict | None, limit: int = 50) -> dict:
    """두 실행의 지식 상태 차이. 끊긴 · 생긴 관계와 생긴 · 없어진 · 속성이 바뀐 항목(id)."""
    a, b = a or {}, b or {}
    out = {'changed': bool(a.get('fingerprint') and b.get('fingerprint') and a['fingerprint'] != b['fingerprint']),
           'comparable': bool(a.get('fingerprint') and b.get('fingerprint')),
           'nodes': [a.get('nodes'), b.get('nodes')], 'relationships': [a.get('relationships'), b.get('relationships')],
           'last_change': [a.get('last_change'), b.get('last_change')]}
    sa, sb = a.get('snapshot'), b.get('snapshot')
    if not out['comparable']:
        out['note'] = '한쪽 실행에 지식 지문이 없어 바뀐 내용을 비교할 수 없습니다'
        return out
    if not (sa and sb):
        out['note'] = '지식 지문만 비교했습니다 (그래프가 커서 상세 목록은 남기지 않음)'
        return out
    ra, rb = set(sa['rels']), set(sb['rels'])
    na, nb = sa['nodes'], sb['nodes']

    def rel(s):
        x, t, y = s.split('|', 2)
        return {'from': x, 'type': t, 'to': y}
    removed, added = sorted(ra - rb), sorted(rb - ra)
    out.update(removed_rels=[rel(s) for s in removed[:limit]], added_rels=[rel(s) for s in added[:limit]],
               removed_nodes=sorted(set(na) - set(nb))[:limit], added_nodes=sorted(set(nb) - set(na))[:limit],
               changed_nodes=sorted(k for k in set(na) & set(nb) if na[k] != nb[k])[:limit],
               counts={'removed_rels': len(removed), 'added_rels': len(added), 'removed_nodes': len(set(na) - set(nb)),
                       'added_nodes': len(set(nb) - set(na)), 'changed_nodes': sum(1 for k in set(na) & set(nb) if na[k] != nb[k])})
    return out


# ---------------------------------------------------------------- 전후 비교
RUN_HEAD = ('id', 'created', 'by', 'path', 'repeats', 'note', 'summary')


def compare(a: dict, b: dict) -> dict:
    """a = 전(before), b = 후(after). 두 실행에 다 있는 항목만 비교하고 한쪽에만 있는 항목은 따로 적는다.
    정답표 항목을 두 실행 사이에 고쳤으면 golden_changed=True — 점수 변화가 지식 때문인지 정답 때문인지 가린다."""
    ia = {r['item']: r for r in a['items']}
    ib = {r['item']: r for r in b['items']}
    order = [x['item'] for x in b['items']]
    rows = []
    for key in sorted(set(ia) & set(ib), key=order.index):
        ra, rb = ia[key], ib[key]
        changed = [{'check': c, 'before': ra['checks'][c]['ok'], 'after': rb['checks'][c]['ok']}
                   for c in ('cause', 'top', 'forbidden', 'evidence') if ra['checks'][c]['ok'] != rb['checks'][c]['ok']]
        rows.append({'item': key, 'title': rb['title'], 'before': ra['score'], 'after': rb['score'], 'delta': round(rb['score'] - ra['score'], 1),
                     'stability_before': ra['stability'], 'stability_after': rb['stability'],
                     'outcome_before': ra['modal_outcome'], 'outcome_after': rb['modal_outcome'], 'changed': changed,
                     'evidence_lost': [e for e in ra['checks']['evidence']['found'] if e in rb['checks']['evidence']['missing']],
                     'evidence_gained': [e for e in rb['checks']['evidence']['found'] if e in ra['checks']['evidence']['missing']],
                     'golden_changed': ra.get('item_hash') != rb.get('item_hash'),
                     'verdict': 'improved' if rb['score'] > ra['score'] else 'regressed' if rb['score'] < ra['score'] else 'same'})
    kd = knowledge_diff(a.get('knowledge'), b.get('knowledge'))
    return {'before': {**{k: a.get(k) for k in RUN_HEAD}, 'knowledge': public_knowledge(a.get('knowledge'))},
            'after': {**{k: b.get(k) for k in RUN_HEAD}, 'knowledge': public_knowledge(b.get('knowledge'))},
            'rows': rows, 'only_before': sorted(set(ia) - set(ib)), 'only_after': sorted(set(ib) - set(ia)),
            'improved': sum(r['verdict'] == 'improved' for r in rows), 'regressed': sum(r['verdict'] == 'regressed' for r in rows),
            'same': sum(r['verdict'] == 'same' for r in rows), 'golden_changed': [r['item'] for r in rows if r['golden_changed']],
            'delta': round(statistics.fmean([r['after'] for r in rows]) - statistics.fmean([r['before'] for r in rows]), 1) if rows else None,
            'knowledge': kd, 'knowledge_changed': kd['changed']}


# ---------------------------------------------------------------- 실제 워커 경로: 지난 처리 건 고르기
FACT_KEYS = ('plc_mode', 'plc_state', 'standby_ready', 'fan100_hours')


def instance_candidate(inst: dict, decision_lookup) -> dict | None:
    """처리 건 한 건 → 채점 후보 요약. 에이전트 task 출력(cause · decision_id)이 없으면 None."""
    vars_ = {v['key']: v.get('value') for v in (inst.get('variables_data') or []) if isinstance(v, dict) and 'key' in v}
    did = vars_.get('decision_id')
    if not vars_.get('cause') or not did:
        return None
    d = decision_lookup(did) or {}
    return {'instance': inst['proc_inst_id'], 'name': inst.get('proc_inst_name'), 'status': inst.get('status'), 'started': inst.get('start_date'),
            'asset': vars_.get('asset') or d.get('asset'), 'pattern': vars_.get('pattern') or (d.get('origin') or {}).get('pattern') or (d.get('scenario') or {}).get('pattern'),
            'cause': vars_.get('cause'), 'failure_mode': vars_.get('failure_mode'), 'decision_id': did, 'decision_found': bool(d),
            'facts': {k: v for k, v in (d.get('facts') or {}).items() if k in FACT_KEYS},
            'guide_card': vars_.get('guide_card') if isinstance(vars_.get('guide_card'), dict) else None,
            'chosen_skill': vars_.get('chosen_skill')}


def match_item(items: list[dict], candidate: dict) -> dict:
    """처리 건의 설비 · 패턴 · 판단 당시 사실에 맞는 정답표 항목 하나. 둘 이상이거나 없으면 사유를 붙여 거부한다(항목을 직접 고르게)."""
    facts = candidate.get('facts') or {}
    hits = [it for it in items if it['asset'] == candidate.get('asset') and it['pattern'] == candidate.get('pattern')
            and all(facts.get(k) == v for k, v in (it.get('facts') or {}).items() if k in facts)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ValueError(f"처리 건 {candidate.get('instance')} ({candidate.get('asset')} · {candidate.get('pattern')})에 맞는 정답표 항목이 없습니다 — 정답표에 먼저 적으세요")
    raise ValueError(f"처리 건 {candidate.get('instance')} 에 맞는 정답표 항목이 {len(hits)}개입니다 ({', '.join(h['id'] for h in hits)}) — 항목을 직접 고르세요")


def worker_judgement(candidate: dict, decision: dict | None, guide_card: dict | None = None) -> dict:
    """처리 건의 에이전트 task 출력(원인 · 가이드 카드) + process 에 제출된 조치 판단 → 채점 입력. 판단 레코드가 없으면 판단 없음으로 본다."""
    if not decision:
        return withheld(f"판단 {candidate.get('decision_id')} 을 process 에서 찾지 못했습니다", status='EMPTY')
    card = guide_card if isinstance(guide_card, dict) else candidate.get('guide_card')
    causes = [{'id': candidate.get('cause'), 'failureModeId': candidate.get('failure_mode'), 'evidence': []}]
    extra = []
    if isinstance(card, dict):
        extra += [c for c in card.get('citations') or [] if isinstance(c, str)]
        for c in card.get('causes') or []:
            extra += [e['id'] for e in c.get('evidence') or [] if isinstance(e, dict) and e.get('passed') is True and e.get('id')]
    j = normalize_decision(decision, causes=causes, extra_cited=extra)
    j['status'] = 'EVALUATED' if j['options'] else 'EMPTY'
    return j


# ---------------------------------------------------------------- 저장소 (정답표 항목 + 채점 실행)
def _run_head(r: dict) -> dict:
    return {**{k: deepcopy(r.get(k)) for k in (*RUN_HEAD, 'golden_version')}, 'knowledge': public_knowledge(r.get('knowledge'))}


class MemoryEvalStore:
    kind = 'memory'

    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}
        self._golden: dict[str, dict] = {}

    # 정답표
    def golden_list(self) -> list[dict]:
        with self._lock:
            return [deepcopy(v) for v in sorted(self._golden.values(), key=lambda x: x['id'])]

    def golden_get(self, iid: str) -> dict | None:
        with self._lock:
            return deepcopy(self._golden.get(iid))

    def golden_put(self, item: dict, by: str, *, create: bool) -> dict:
        with self._lock:
            exists = item['id'] in self._golden
            if create and exists:
                raise FileExistsError(item['id'])
            if not create and not exists:
                raise KeyError(item['id'])
            rec = {**deepcopy(item), 'item_hash': item_hash(item), 'updated_by': by, 'updated_at': _now()}
            self._golden[item['id']] = rec
            return deepcopy(rec)

    def golden_delete(self, iid: str) -> None:
        with self._lock:
            if self._golden.pop(iid, None) is None:
                raise KeyError(iid)

    # 실행
    def put(self, run: dict) -> None:
        with self._lock:
            if run['id'] in self._runs:
                raise ValueError('같은 실행 id 가 이미 있습니다')
            self._runs[run['id']] = deepcopy(run)

    def get(self, rid: str) -> dict | None:
        with self._lock:
            return deepcopy(self._runs.get(rid))

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [_run_head(r) for r in sorted(self._runs.values(), key=lambda r: r['created'], reverse=True)[:limit]]


class PgEvalStore:
    """Supabase(마이그레이션 20261008000030): judgment_golden_items(정답표 항목, 고치면 덮어씀 · 지문 item_hash)와
    judgment_eval_runs(실행 하나 = 행 하나, 불변). 항목 결과 · 지식 상태는 jsonb."""
    kind = 'supabase'

    def __init__(self, dsn: str, tenant: str = 'hyd'):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
        self._psycopg, self._dict_row, self._Jsonb = psycopg, dict_row, Jsonb
        self.dsn, self.tenant = dsn, tenant

    def _conn(self):
        return self._psycopg.connect(self.dsn, autocommit=True, connect_timeout=5, row_factory=self._dict_row)

    @staticmethod
    def _iso(v):
        if isinstance(v, datetime):
            return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        return v

    def _golden_row(self, r):
        return None if r is None else {**r['item'], 'item_hash': r['item_hash'], 'updated_by': r['updated_by'], 'updated_at': self._iso(r['updated_at'])}

    def golden_list(self) -> list[dict]:
        with self._conn() as c:
            return [self._golden_row(r) for r in c.execute('select * from judgment_golden_items where tenant_id=%s order by id', (self.tenant,)).fetchall()]

    def golden_get(self, iid: str) -> dict | None:
        with self._conn() as c:
            return self._golden_row(c.execute('select * from judgment_golden_items where tenant_id=%s and id=%s', (self.tenant, iid)).fetchone())

    def golden_put(self, item: dict, by: str, *, create: bool) -> dict:
        h = item_hash(item)
        with self._conn() as c:
            if create:
                row = c.execute('''insert into judgment_golden_items (tenant_id, id, item, item_hash, updated_by) values (%s,%s,%s,%s,%s)
                                   on conflict (tenant_id, id) do nothing returning *''', (self.tenant, item['id'], self._Jsonb(item), h, by)).fetchone()
                if row is None:
                    raise FileExistsError(item['id'])
            else:
                row = c.execute('''update judgment_golden_items set item=%s, item_hash=%s, updated_by=%s, updated_at=now()
                                   where tenant_id=%s and id=%s returning *''', (self._Jsonb(item), h, by, self.tenant, item['id'])).fetchone()
                if row is None:
                    raise KeyError(item['id'])
            return self._golden_row(row)

    def golden_delete(self, iid: str) -> None:
        with self._conn() as c:
            if c.execute('delete from judgment_golden_items where tenant_id=%s and id=%s', (self.tenant, iid)).rowcount == 0:
                raise KeyError(iid)

    def put(self, run: dict) -> None:
        with self._conn() as c:
            c.execute('''insert into judgment_eval_runs (id, tenant_id, created_at, created_by, path, repeats, golden_version, knowledge, summary, items, note)
                         values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                      (run['id'], self.tenant, run['created'], run['by'], run['path'], run['repeats'], run['golden_version'],
                       self._Jsonb(run['knowledge']), self._Jsonb(run['summary']), self._Jsonb(run['items']), run.get('note') or ''))

    def _row(self, r: dict | None, with_items: bool) -> dict | None:
        if r is None:
            return None
        out = {'id': r['id'], 'created': self._iso(r['created_at']), 'by': r['created_by'], 'path': r['path'], 'repeats': r['repeats'],
               'golden_version': r['golden_version'], 'knowledge': r['knowledge'], 'summary': r['summary'], 'note': r.get('note') or ''}
        if with_items:
            out['items'] = r['items']
        return out

    def get(self, rid: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute('select * from judgment_eval_runs where id=%s and tenant_id=%s', (rid, self.tenant)).fetchone(), True)

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute('''select id, created_at, created_by, path, repeats, golden_version, knowledge - 'snapshot' as knowledge, summary, note
                                from judgment_eval_runs where tenant_id=%s order by created_at desc limit %s''', (self.tenant, limit)).fetchall()
            return [self._row(r, False) for r in rows]
