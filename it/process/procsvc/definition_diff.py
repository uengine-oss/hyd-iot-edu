"""Human-readable comparison of two definition versions (U4, TODO 4).

Product reference: process-gpt-vue3 `src/utils/bpmnDiff.ts` (BpmnChange: added | removed | modified, with per-field before/after
pairs and `flow: {from, to}` for sequence flows) and `views/process-hierarchy/VersionComparison.vue`. HYD definitions are JSON,
not BPMN XML, so the diff walks the JSON collections directly; the output is the same shape so the portal lists it the way
the product does: one line per change, fields underneath as before → after.

compare(a, b) → {'from': {...}, 'to': {...}, 'counts': {'추가','삭제','변경'}, 'changes': [
    {'kind': '단계', 'change': '추가', 'id': 'task:x', 'name': '…', 'text': '단계 "…"(task:x) 추가', 'fields': [{'label','before','after'}],
     'flow': {'from': '…', 'to': '…'}}]}
"""
from __future__ import annotations

import json
from copy import deepcopy

# (collection key, kind label shown to people, field that identifies an element)
COLLECTIONS = (('activities', '단계', 'id'), ('events', '이벤트', 'id'), ('gateways', '분기점', 'id'),
               ('sequences', '연결', 'id'), ('data', '변수', 'name'), ('roles', '역할', 'name'))
FIELD_LABELS = {'name': '이름', 'type': '종류', 'role': '담당 역할', 'tool': '도구', 'agentMode': '에이전트 방식', 'orchestration': '실행 주체',
                'agent': '에이전트', 'inputData': '입력 변수', 'outputData': '출력 변수', 'attachedEvents': '붙은 이벤트', 'description': '설명',
                'agentConfig': '에이전트 설정', 'skills': '스킬', 'inputBindings': '입력 연결', 'condition': '분기 조건', 'source': '출발',
                'target': '도착', 'properties': '속성', 'timer': '시간 제한', 'eventDefinition': '이벤트 정의', 'attachedTo': '붙은 단계',
                'endpoint': '담당자', 'fields_json': '입력 항목', 'processDefinitionName': '정의 이름', 'ontologyRef': '온톨로지 연결',
                'alertPolicy': '경보 정책', 'megaProcessId': '대분류', 'majorProcessId': '중분류', 'contractProvenance': '계약 출처'}
TOP_LEVEL = ('processDefinitionName', 'description', 'ontologyRef', 'alertPolicy', 'megaProcessId', 'majorProcessId')
IGNORED = {'version'}


def _text(value) -> str:
    if value is None:
        return '없음'
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return '예' if value else '아니오'
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _label(key: str) -> str:
    return FIELD_LABELS.get(key, key)


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def _index(raw: dict, collection: str, key: str) -> dict[str, dict]:
    out = {}
    for item in raw.get(collection) or []:
        if isinstance(item, dict) and isinstance(item.get(key), str):
            out[item[key]] = item
    return out


def _node_names(raw: dict) -> dict[str, str]:
    names = {}
    for collection in ('activities', 'events', 'gateways'):
        for item in raw.get(collection) or []:
            if isinstance(item, dict) and item.get('id'):
                names[item['id']] = item.get('name') or item['id']
    return names


def _fields(before: dict, after: dict, ignore=('id', 'name')) -> list[dict]:
    keys = [k for k in list(before) + [k for k in after if k not in before] if k not in ignore]
    return [{'label': _label(k), 'key': k, 'before': _text(before.get(k)), 'after': _text(after.get(k))}
            for k in keys if not _same(before.get(k), after.get(k))]


def _flow(seq: dict, names: dict[str, str]) -> dict:
    return {'from': names.get(seq.get('source'), seq.get('source') or '?'), 'to': names.get(seq.get('target'), seq.get('target') or '?')}


def _describe(kind: str, change: str, ident: str, item: dict, flow: dict | None) -> str:
    if flow:
        return f'{kind} {flow["from"]} → {flow["to"]} ({ident}) {change}'
    name = item.get('name')
    return f'{kind} "{name}"({ident}) {change}' if name and name != ident else f'{kind} {ident} {change}'


def compare(a: dict, b: dict) -> dict:
    """Changes from version a to version b, in the order people read a definition (top level, nodes, flows, variables, roles, forms)."""
    changes: list[dict] = []
    for key in TOP_LEVEL:
        if not _same(a.get(key), b.get(key)):
            changes.append({'kind': '정의', 'change': '변경', 'id': key, 'name': _label(key), 'text': f'{_label(key)} 변경',
                            'fields': [{'label': _label(key), 'key': key, 'before': _text(a.get(key)), 'after': _text(b.get(key))}]})
    names_a, names_b = _node_names(a), _node_names(b)
    for collection, kind, key in COLLECTIONS:
        left, right = _index(a, collection, key), _index(b, collection, key)
        for ident in list(left) + [i for i in right if i not in left]:
            item_a, item_b = left.get(ident), right.get(ident)
            if item_a is not None and item_b is None:
                flow = _flow(item_a, names_a) if collection == 'sequences' else None
                changes.append({'kind': kind, 'change': '삭제', 'id': ident, 'name': item_a.get('name') or ident, 'flow': flow,
                                'text': _describe(kind, '삭제', ident, item_a, flow),
                                'fields': [{'label': _label(k), 'key': k, 'before': _text(v), 'after': '없음'} for k, v in item_a.items() if k != key]})
            elif item_a is None and item_b is not None:
                flow = _flow(item_b, names_b) if collection == 'sequences' else None
                changes.append({'kind': kind, 'change': '추가', 'id': ident, 'name': item_b.get('name') or ident, 'flow': flow,
                                'text': _describe(kind, '추가', ident, item_b, flow),
                                'fields': [{'label': _label(k), 'key': k, 'before': '없음', 'after': _text(v)} for k, v in item_b.items() if k != key]})
            elif not _same(item_a, item_b):
                fields = _fields(item_a, item_b, ignore=(key,))
                flow = _flow(item_b, names_b) if collection == 'sequences' else None
                changes.append({'kind': kind, 'change': '변경', 'id': ident, 'name': item_b.get('name') or item_a.get('name') or ident, 'flow': flow,
                                'text': _describe(kind, '변경: ' + ', '.join(f['label'] for f in fields), ident, item_b, flow), 'fields': fields})
    forms_a, forms_b = a.get('forms') or {}, b.get('forms') or {}
    for form_id in list(forms_a) + [f for f in forms_b if f not in forms_a]:
        fa, fb = forms_a.get(form_id), forms_b.get(form_id)
        if fa is not None and fb is None:
            changes.append({'kind': '폼', 'change': '삭제', 'id': form_id, 'name': form_id, 'text': f'폼 {form_id} 삭제',
                            'fields': [{'label': '입력 항목', 'key': 'fields_json', 'before': _form_text(fa), 'after': '없음'}]})
        elif fa is None and fb is not None:
            changes.append({'kind': '폼', 'change': '추가', 'id': form_id, 'name': form_id, 'text': f'폼 {form_id} 추가',
                            'fields': [{'label': '입력 항목', 'key': 'fields_json', 'before': '없음', 'after': _form_text(fb)}]})
        elif not _same(fa, fb):
            changes.append({'kind': '폼', 'change': '변경', 'id': form_id, 'name': form_id, 'text': f'폼 {form_id} 변경: 입력 항목',
                            'fields': [{'label': '입력 항목', 'key': 'fields_json', 'before': _form_text(fa), 'after': _form_text(fb)}]})
    counts = {'추가': 0, '삭제': 0, '변경': 0}
    for c in changes:
        counts[c['change']] += 1
    return {'from': {'id': a.get('processDefinitionId'), 'version': a.get('version')},
            'to': {'id': b.get('processDefinitionId'), 'version': b.get('version')},
            'counts': counts, 'changes': changes, 'same': not changes}


NODE_COLLECTIONS = ('activities', 'events', 'gateways')


def _nodes(raw: dict) -> dict[str, tuple[str, dict]]:
    return {x['id']: (col, x) for col in NODE_COLLECTIONS for x in raw.get(col) or [] if isinstance(x, dict) and isinstance(x.get('id'), str)}


def _links(raw: dict) -> list[tuple[str, str]]:
    out = [(s.get('source'), s.get('target')) for s in raw.get('sequences') or [] if isinstance(s, dict)]
    out += [(e.get('attachedTo'), e['id']) for e in raw.get('events') or [] if isinstance(e, dict) and e.get('attachedTo') and e.get('id')]
    return out


def align_import(a: dict, b: dict) -> dict[str, str]:
    """bpmn.io에서 가져온 흐름 b의 그림 id → 기준 흐름 a의 id (B3 가져오기 결과를 기준과 비교할 때).

    그림의 id(Activity_0diag4n …)는 기준 id(task:diagnose …)와 다르므로 id로 맞추면 전부 "삭제 + 추가"가 된다.
    1) task는 학생이 고른 부품(bpmnImport.mapping.tasks[그림 id].part = 기준 단계 id)으로 맞춘다.
    2) 이벤트 · 분기점은 같은 종류이면서 이미 맞춘 이웃(들어오는 · 나가는 연결, 붙은 단계)이 같은 기준 노드가 하나뿐일 때 맞춘다(반복).
    3) 연결은 양 끝을 맞춘 뒤 (출발, 도착)이 같은 기준 연결로 맞춘다.
    맞출 수 없는 것은 그대로 두어 "추가" · "삭제"로 보인다(억지로 짝짓지 않는다)."""
    tasks = ((b.get('bpmnImport') or {}).get('mapping') or {}).get('tasks') or {}
    na, nb = _nodes(a), _nodes(b)
    ren: dict[str, str] = {}
    for bid, m in tasks.items():
        part = m.get('part') if isinstance(m, dict) else None
        if bid in nb and part in na and na[part][0] == nb[bid][0] and part not in ren.values():
            ren[bid] = part
    for bid in nb:                                       # 그림에서 기준 id를 그대로 쓴 노드
        if bid in na and bid not in ren and bid not in ren.values():
            ren[bid] = bid
    la, lb = _links(a), _links(b)

    def around(links, node, mapper):
        ins = {mapper(s) for s, t in links if t == node and mapper(s)}
        outs = {mapper(t) for s, t in links if s == node and mapper(t)}
        return ins, outs

    changed = True
    while changed:
        changed = False
        taken = set(ren.values())
        for bid, (col, item) in nb.items():
            if bid in ren:
                continue
            b_in, b_out = around(lb, bid, ren.get)
            if not (b_in or b_out):
                continue
            hits = []
            for aid, (acol, aitem) in na.items():
                if aid in taken or acol != col or aitem.get('type') != item.get('type'):
                    continue
                a_in, a_out = around(la, aid, lambda x: x)
                if b_in <= a_in and b_out <= a_out:
                    hits.append(aid)
            if len(hits) == 1:
                ren[bid] = hits[0]; taken.add(hits[0]); changed = True
    seq_a = {}
    for s in a.get('sequences') or []:
        if isinstance(s, dict) and s.get('id'):
            seq_a.setdefault((s.get('source'), s.get('target')), []).append(s['id'])
    for s in b.get('sequences') or []:
        if not isinstance(s, dict) or not s.get('id'):
            continue
        cands = [x for x in seq_a.get((ren.get(s.get('source')), ren.get(s.get('target'))), []) if x not in ren.values()]
        if len(cands) == 1:
            ren[s['id']] = cands[0]
    return {k: v for k, v in ren.items() if k != v}


def _renamed(b: dict, ren: dict[str, str]) -> dict:
    out = deepcopy(b)
    r = lambda x: ren.get(x, x) if isinstance(x, str) else x  # noqa: E731
    for col in NODE_COLLECTIONS + ('sequences',):
        for item in out.get(col) or []:
            if not isinstance(item, dict):
                continue
            for key in ('id', 'source', 'target', 'attachedTo'):
                if key in item:
                    item[key] = r(item[key])
            if isinstance(item.get('attachedEvents'), list):
                item['attachedEvents'] = [r(x) for x in item['attachedEvents']]
    return out


def compare_import(a: dict, b: dict) -> dict:
    """compare(a, b) after aligning b's drawn ids to a's (align_import). Each change keeps the drawn id as drawn_id."""
    ren = align_import(a, b)
    diff = compare(a, _renamed(b, ren))
    back = {v: k for k, v in ren.items()}
    for c in diff['changes']:
        if c['id'] in back:
            c['drawn_id'] = back[c['id']]
    diff['aligned'] = len(ren)
    return diff


def _form_text(form: dict) -> str:
    fields = form.get('fields_json') if isinstance(form, dict) else None
    if not isinstance(fields, list):
        return _text(form)
    return ', '.join(f"{f.get('text') or f.get('key')}({f.get('key')}: {f.get('type')})" for f in fields if isinstance(f, dict)) or '항목 없음'
