"""매뉴얼 읽기와 SOP 구조 만들기 — 제공 코드(일반 로직). 고치지 않는다.

매뉴얼의 문장에 번호(줄 또는 줄.문장)를 붙이고, SOP의 번호 줄을 수행 단계로 옮기고, `app/features/`의 표 셋(sop_items · relations · scope)을 읽어
SOP 구조 하나로 묶는다. 원문 인용은 번호로 찾은 문장을 그대로 싣는다. 어느 문장이 어느 항목인지, 어느 설비에 거는지는 표에 적힌 대로만 따른다.
"""
from pathlib import Path
import json
import re

from app.utils.results import Stop, read_text, rel
from app.utils.rules import read_rows, split

HERE = Path(__file__).resolve().parents[2]
DATA, FEATURES = HERE / 'data', HERE / 'app/features'
MANUAL = DATA / 'hm8_manual.md'
ITEMS = ['적용 대상', '작업 전제 조건', '안전 조건', '준비사항', '금지 사항', '제한', '담당 역할', '완료 확인 기준']
RELATIONS = {'MITIGATED_BY': ('고장 유형', 'SOP'), 'REMEDIED_BY': ('고장 유형', 'SOP'), 'ADDRESSES': ('SOP', '원인')}
ITEM_COLUMNS = ['sop_id', '항목', '원문', '규칙']
RELATION_COLUMNS = ['type', 'from', 'to', '원문']
SCOPE_COLUMNS = ['sop_id', '구성_요소', '설비', '까닭']
DECISION_COLUMNS = ['지점', '고른_것', '근거', '바뀌는_답']
SENTENCE = re.compile(r'(?<=\.)\s+')


def manual_lines():
    """매뉴얼 줄 번호 → (절, SOP, 단계 번호 또는 None, 글). 제목 · 빈 줄 · 표 줄은 넣지 않는다."""
    section = sop = None
    out = {}
    for no, line in enumerate(read_text(MANUAL)[0].splitlines(), 1):
        if m := re.match(r'## (HM-\d+\.\d+) ', line):
            section, sop = m.group(1), None
        elif m := re.match(r'### (SOP-[A-Z]+-\d+) ', line):
            sop = m.group(1)
        elif section and line.strip() and not line.startswith(('#', '|')):
            m = re.match(r'(\d+)\. (.+)', line) if sop else None
            out[no] = (section, sop, int(m.group(1)) if m else None, m.group(2) if m else line.lstrip('- ').strip())
    return out


def sentences():
    """문장 목록 — 표의 「원문」 칸에 쓰는 번호와 그 글. 한 줄에 문장이 하나면 번호는 줄, 여럿이면 줄.문장이다."""
    rows = []
    for no, (section, sop, step, text) in manual_lines().items():
        parts = SENTENCE.split(text)
        for i, s in enumerate(parts, 1):
            rows.append({'원문': str(no) if len(parts) == 1 else f'{no}.{i}', '절': section, 'SOP': sop or '', '단계': step or '', '글': s})
    return rows


def quotes(refs, where):
    """원문 번호들 → 그 문장들. 없는 번호면 파일:줄을 짚고 멈춘다."""
    by = {s['원문']: s['글'] for s in sentences()}
    lines = manual_lines()
    out = []
    for ref in refs:
        if ref in by:
            out.append(by[ref])
        elif ref.isdigit() and int(ref) in lines:      # 문장이 여럿인 줄을 줄 번호만으로 가리키면 그 줄 전체
            out.append(lines[int(ref)][3])
        else:
            raise Stop(f'{where}: 원문 번호 「{ref}」가 매뉴얼에 없습니다. python run.py 화면의 「매뉴얼 문장 번호」 표에 있는 번호를 씁니다.')
    return out


def targets():
    return {r['sop_id']: r for r in read_rows(DATA / 'targets.csv')}


def failure_modes():
    out = {}
    for r in read_rows(DATA / 'failure_modes.csv'):
        f = out.setdefault(r['failure_mode_id'], {'id': r['failure_mode_id'], 'name': r['name'], 'component': r['component'], 'causes': []})
        f['causes'].append({'id': r['cause_id'], 'name': r['cause_name']})
    return list(out.values())


def model_dir():
    """쓰는 설비 모델. `app/features/model/`에 schema.json과 graph.json이 둘 다 있으면 그 모델, 아니면 제공 모델."""
    mine = FEATURES / 'model'
    return mine if (mine / 'schema.json').is_file() and (mine / 'graph.json').is_file() else DATA / 'model'


def model():
    """설비 모델에서 설비와 그 구성 요소 — {설비 ID: {'name', 'model', 'status', 'components': [이름]}}."""
    path = model_dir() / 'graph.json'
    try:
        graph = json.loads(read_text(path)[0])
    except json.JSONDecodeError as e:
        raise Stop(f'{rel(path)}:{e.lineno}: JSON 꼴이 아닙니다 — {e.msg}') from None
    nodes = {n['props']['id']: n for n in graph['nodes']}
    assets = {i: {'name': n['props'].get('name', ''), 'model': n['props'].get('model', ''), 'status': n['props'].get('status', ''), 'components': []}
              for i, n in nodes.items() if 'Asset' in n['labels']}
    for r in graph['rels']:
        if r['type'] == 'HAS_COMPONENT' and r['a'] in assets and r['b'] in nodes:
            assets[r['a']]['components'].append(nodes[r['b']]['props'].get('name', ''))
    return assets


def steps(sop_id):
    """SOP의 수행 단계 — 매뉴얼의 번호 줄을 그대로 옮긴다."""
    return [{'order': step, 'text': text, 'line': no} for no, (_, sop, step, text) in manual_lines().items() if sop == sop_id and step is not None]


def read_items(rule_ids=None):
    known = targets()
    out = []
    for r in read_rows(FEATURES / 'sop_items.csv', ITEM_COLUMNS):
        where = f'app/features/sop_items.csv:{r["_line"]}'
        sops = split(r['sop_id'])
        bad = [s for s in sops if s not in known]
        if not sops or bad:
            raise Stop(f'{where}: sop_id {bad or "빈 칸"}이 data/targets.csv에 없습니다.')
        if r['항목'] not in ITEMS:
            raise Stop(f'{where}: 항목 「{r["항목"]}」을 읽을 수 없습니다. 쓸 수 있는 항목: ' + ' · '.join(ITEMS))
        refs = split(r['원문'])
        if not refs:
            raise Stop(f'{where}: 원문 칸이 비었습니다. 이 항목의 근거 문장 번호를 적습니다.')
        used = split(r['규칙'])
        if rule_ids is not None:
            gone = [x for x in used if x not in rule_ids]
            if gone:
                raise Stop(f'{where}: 규칙 {gone}이 app/features/decision_table.csv에 없습니다.')
        out.append({'sops': sops, 'item': r['항목'], 'refs': refs, 'text': quotes(refs, where), 'rules': used, 'line': r['_line']})
    return out


def read_relations():
    known, fms = targets(), failure_modes()
    ids = {'고장 유형': {f['id'] for f in fms}, 'SOP': set(known), '원인': {c['id'] for f in fms for c in f['causes']}}
    out, seen = [], set()
    for r in read_rows(FEATURES / 'relations.csv', RELATION_COLUMNS):
        where = f'app/features/relations.csv:{r["_line"]}'
        if r['type'] not in RELATIONS:
            raise Stop(f'{where}: type 「{r["type"]}」을 읽을 수 없습니다. 쓸 수 있는 type: ' + ' · '.join(RELATIONS))
        a, b = RELATIONS[r['type']]
        if r['from'] not in ids[a] or r['to'] not in ids[b]:
            turned = r['from'] in ids[b] and r['to'] in ids[a]
            raise Stop(f'{where}: {r["type"]}은 {a}에서 {b}(으)로 긋습니다. ' + ('from과 to가 거꾸로입니다.' if turned else f'from 「{r["from"]}」 또는 to 「{r["to"]}」가 제공 목록에 없습니다.'))
        key = (r['type'], r['from'], r['to'])
        if key in seen:
            raise Stop(f'{where}: 같은 관계가 두 번 있습니다 — {" ".join(key)}')
        seen.add(key)
        refs = split(r['원문'])
        out.append({'type': r['type'], 'from': r['from'], 'to': r['to'], 'source': refs, 'text': quotes(refs, where)})
    return out


def read_scope():
    known, assets = targets(), model()
    names = {c for a in assets.values() for c in a['components']}
    out = {}
    for r in read_rows(FEATURES / 'scope.csv', SCOPE_COLUMNS):
        where = f'app/features/scope.csv:{r["_line"]}'
        if r['sop_id'] not in known:
            raise Stop(f'{where}: sop_id 「{r["sop_id"]}」가 data/targets.csv에 없습니다.')
        if r['sop_id'] in out:
            raise Stop(f'{where}: {r["sop_id"]} 줄이 두 번 있습니다. SOP마다 한 줄입니다.')
        linked, parts = split(r['설비']), split(r['구성_요소'])
        gone = [a for a in linked if a not in assets]
        if gone:
            raise Stop(f'{where}: 설비 {gone}이 설비 모델({rel(model_dir())})에 없습니다. 모델에 없는 식별자는 새로 만들지 않습니다.')
        odd = [c for c in parts if c not in names]
        if odd:
            raise Stop(f'{where}: 구성_요소 {odd}이 설비 모델의 구성 요소 이름에 없습니다.')
        if not r['까닭']:
            raise Stop(f'{where}: 까닭 칸이 비었습니다. 이 SOP를 그 설비에 건(또는 걸지 않은) 까닭을 적습니다.')
        out[r['sop_id']] = {'components': parts, 'assets': linked, 'reason': r['까닭']}
    return out


def decision(point):
    """decisions.csv에서 그 지점의 줄. 고른 것 · 근거 · 바뀌는 답이 비어 있으면 그 줄을 짚고 멈춘다."""
    path = FEATURES / 'decisions.csv'
    rows = [r for r in read_rows(path, DECISION_COLUMNS) if r['지점'] == point]
    if not rows:
        raise Stop(f'{rel(path)}: 「{point}」 줄이 없습니다. 받은 빈 틀의 그 줄을 지우지 않습니다.')
    r = rows[0]
    empty = [c for c in DECISION_COLUMNS[1:] if not r[c]]
    if empty:
        raise Stop(f'{rel(path)}:{r["_line"]}: 「{point}」의 ' + ' · '.join(empty) + ' 칸이 비어 있습니다. 선택지와 그 결과를 따져 본 뒤 내가 고른 것과 이유를 적고 다시 실행합니다.')
    return r


def build(rule_ids=None, need_scope=True):
    """표 셋을 읽어 SOP 구조 하나로 묶는다(다음 실습이 읽는 `output/sop.json`의 내용)."""
    known = targets()
    items, relations = read_items(rule_ids), read_relations()
    scope = read_scope() if need_scope else {}
    if need_scope:
        missing = [s for s in known if s not in scope]
        if missing:
            raise Stop('app/features/scope.csv: ' + ' · '.join(missing) + ' 줄이 없습니다. SOP마다 한 줄씩 적습니다.')
    sops = []
    for sid, t in known.items():
        mine = [{'item': x['item'], 'refs': x['refs'], 'text': x['text'], 'rules': x['rules']} for x in items if sid in x['sops']]
        s = scope.get(sid, {'components': [], 'assets': [], 'reason': ''})
        sops.append({'id': sid, 'name': t['name'], 'kind': t['종류'], 'source_section': t['source_section'], 'steps': steps(sid), 'items': mine,
                     'components': s['components'], 'assets': s['assets'], 'scope_reason': s['reason']})
    return {'model': rel(model_dir()), 'failure_modes': failure_modes(), 'sops': sops, 'relations': relations}
