"""SOP 구조 조립 · 설비 모델 ID 잇기 · 출처 대조 — 제공 코드(일반 로직). 고치지 않는다.

학생이 채우는 판단 표(`app/features/condition_classes.csv` · `app/features/relations.csv` · `app/features/equipment_links.csv`)를 읽어 `output/sop.json`을 계약 꼴로 쓴다.
- 수행 단계는 매뉴얼의 번호 줄을 그대로 옮긴다. 조건 · 승인 문장은 판단 표가 가리킨 원문 줄(문장)을 그대로 인용한다.
- 출처(source)는 가리킨 줄이 있는 절 · SOP 단계 · 승인 줄로 적는다.
- 모델 참조는 설비 모델(data/model/graph.json, app/features/model/graph.json이 있으면 그것)에 있는 ID만 쓰고, 찾지 못한 ID는 걸지 않은 대상에 적는다.
어느 문장을 어느 칸에 둘지, 무엇을 잇고 어느 설비에 걸지는 판단 표가 정한다 — 이 파일은 그 답을 갖지 않는다.
"""
from __future__ import annotations

from pathlib import Path
import json
import re

from app.utils.condition_tools import MANUAL, SENTENCE, ContractError, csv_body, export_facts, manual_lines, read_csv, sentences, source_parts, write_text  # noqa: F401  (export_facts · sentences는 결과 화면이 쓴다)

KINDS = ['고장 유형', '종류·코드', '적용', '금지', '제한', '완료', '승인']
CLASS_HEADER = ['sop_id', '칸', '원문', '글', '규칙']
REL_HEADER = ['type', 'from', 'to', '이름', '원문']
LINK_HEADER = ['sop_id', '설비', '구성_요소', '센서', '걸지_않은_까닭']
RELATIONS = {'MITIGATED_BY': ('failure_modes', 'sops'), 'REMEDIED_BY': ('failure_modes', 'sops'), 'ADDRESSES': ('sops', 'causes')}


class Unfilled(Exception):
    """정할 지점이 아직 비어 있음."""


def resolve(lab, refs, where):
    """「원문」 칸(;로 나눈 줄 · 줄.문장 · 파일:줄) → (인용 글 목록, 출처 조각 목록)."""
    lines = manual_lines(lab)
    quotes, sources = [], []
    for ref in [r.strip() for r in refs.split(';') if r.strip()]:
        if ref.startswith('data/'):                       # 「data/파일:줄」도 같은 자리(decisions.csv 근거와 같은 꼴)
            ref = ref[len('data/'):]
        if ref.startswith(MANUAL + ':'):                  # 매뉴얼은 줄 번호만 쓴 것과 같다
            ref = ref[len(MANUAL) + 1:]
        m = re.fullmatch(r'(HM-8\.\d+)(?: (SOP-[A-Z]+-\d+) (?:단계 (\d+)|(승인)))?', ref)
        if m:                                             # 출처 꼴(절 · SOP 단계 · 승인)도 그 줄로 받는다
            hit = [n for n, v in lines.items() if v[0] == m.group(1) and (
                (m.group(2) and v[1] == m.group(2) and v[2] == (int(m.group(3)) if m.group(3) else '승인')) or
                (not m.group(2) and v[1] is None and v[3].startswith(m.group(1))))]
            if not hit:
                raise ContractError(f'{where}: 원문 {ref} — data/{MANUAL}에 그 절 · 단계 · 승인 줄이 없음')
            ref = str(hit[0])
        if ':' in ref:
            name, no = ref.rsplit(':', 1)
            path = Path(lab)/'data'/name
            if not path.is_file() or not no.isdigit() or not 1 <= int(no) <= len(path.read_text(encoding='utf-8').splitlines()):
                raise ContractError(f'{where}: 원문 {ref} — data/{name}에 그 줄이 없음')
            sources.append(f'{name}:{no}')
            continue
        m = re.fullmatch(r'(\d+)(?:\.(\d+))?', ref)
        if not m or int(m.group(1)) not in lines:
            raise ContractError(f'{where}: 원문 {ref} — data/{MANUAL}의 줄(또는 줄.문장) 번호가 아님')
        no, k = int(m.group(1)), m.group(2)
        sec, sop, step, text = lines[no]
        parts = SENTENCE.split(text)
        if k is not None and not 1 <= int(k) <= len(parts):
            raise ContractError(f'{where}: 원문 {ref} — {no}줄에는 문장이 {len(parts)}개')
        quotes.append(parts[int(k) - 1] if k else text)
        sources.append(f'{sec} {sop} 단계 {step}' if isinstance(step, int) else (f'{sec} {sop} 승인' if step == '승인' else sec))
    return quotes, list(dict.fromkeys(sources))


def table(lab, name, header):
    path = Path(lab)/'app/features'/name
    if not path.is_file():
        raise Unfilled(f'app/features/{name}이 없습니다(받은 ZIP의 빈 틀을 되살립니다)')
    body, skip = csv_body(path)
    head = body.splitlines()[0].strip().split(',') if body.strip() else []
    if head != header:
        raise ContractError(f'app/features/{name}:{skip + 1} 열 이름이 {",".join(header)}가 아님')
    rows = []
    for i, r in enumerate(read_csv(path), start=skip + 2):
        if None in r or any(v is None for v in r.values()):
            raise ContractError(f'app/features/{name}:{i} 칸 수가 열 이름({",".join(header)})과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if any(v.strip() for v in r.values()):
            rows.append((i, r))
    return rows


def graph_ids(lab):
    mine = Path(lab)/'app/features/model/graph.json'
    graph = json.loads((mine if mine.is_file() else Path(lab)/'data/model/graph.json').read_text(encoding='utf-8-sig'))
    return {n['props']['id']: n['labels'][0] for n in graph['nodes']}


def model_refs(lab, sop, rule, kind):
    """equipment_links.csv의 한 절차 → 계약의 model_refs(모델에 있는 ID만)."""
    need = rule.get(sop) or {}
    if not any(need.get(k) for k in ('assets', 'components', 'sensors', 'not_linked')):
        raise Unfilled(f'app/features/equipment_links.csv에 {sop} 행이 없습니다')
    assets = [a for a in need.get('assets', []) if kind.get(a) == 'Asset']

    def ids(names):
        """이름 하나 → 고른 설비마다의 ID. 「fan」은 설비마다 「HYD-01:fan」, 이미 설비 ID가 붙은 「HYD-01:fan」은 그 설비가 고른 설비일 때 그대로."""
        out = []
        for x in names:
            if ':' in x:
                out += [x] if x.split(':', 1)[0] in assets else []
            else:
                out += [f'{a}:{x}' for a in assets]
        return list(dict.fromkeys(out))
    comps, sens = ids(need.get('components', [])), ids(need.get('sensors', []))
    refs = {'assets': assets, 'components': [x for x in comps if kind.get(x) == 'Component'], 'sensors': [x for x in sens if kind.get(x) == 'Sensor']}
    missing = [a for a in need.get('assets', []) if kind.get(a) != 'Asset'] + [x for x in comps + sens if x not in kind] +               [f'{x}({kind[x]} — 자리가 다름)' for x in comps if x in kind and kind[x] != 'Component'] + [f'{x}({kind[x]} — 자리가 다름)' for x in sens if x in kind and kind[x] != 'Sensor']
    note = str(need.get('not_linked', '')).strip()
    refs['not_linked'] = note + (('. ' if note else '') + '모델에서 찾지 못한 ID: ' + ', '.join(missing) if missing else '')
    return refs, missing


def build(lab):
    """판단 표 세 개 → output/sop.json. 돌려주는 값 = (sop 문서, 아직 채우지 않은 곳 목록, 모델에서 찾지 못한 ID 목록)."""
    lab = Path(lab)
    rows = table(lab, 'condition_classes.csv', CLASS_HEADER)
    try:
        rels, rel_error = table(lab, 'relations.csv', REL_HEADER), None
    except ContractError as e:                            # 관계 표의 꼴 오류도 관계 단계에서 보인다
        rels, rel_error = [], str(e)
    if not rows:
        raise Unfilled('app/features/condition_classes.csv에 아직 행이 없습니다')
    targets = read_csv(lab/'data/targets.csv')
    sop_ids = [t['sop_id'] for t in targets]
    fm_names = {r['failure_mode_id']: r['name'] for r in read_csv(lab/'data/failuremodes.csv')}
    rule = {}
    for line, r in table(lab, 'equipment_links.csv', LINK_HEADER):
        split = lambda v: [x.strip() for x in v.split(';') if x.strip()]
        if r['sop_id'].strip() not in sop_ids:
            raise ContractError(f'app/features/equipment_links.csv:{line}: targets.csv에 없는 SOP {r["sop_id"]}')
        if r['sop_id'].strip() in rule:
            raise ContractError(f'app/features/equipment_links.csv:{line}: {r["sop_id"].strip()} 줄이 두 번째입니다 — 절차마다 한 줄')
        rule[r['sop_id'].strip()] = {'assets': split(r['설비']), 'components': split(r['구성_요소']), 'sensors': split(r['센서']), 'not_linked': r['걸지_않은_까닭'].strip()}
    kind_of = graph_ids(lab)
    by = {s: {k: [] for k in KINDS} for s in sop_ids}
    for line, r in rows:
        where = f'app/features/condition_classes.csv:{line}'
        group, k = [x.strip() for x in r['sop_id'].split(';') if x.strip()], r['칸'].strip()   # 같은 칸 · 원문 · 글 · 규칙이 여러 절차에 걸리면 한 줄에 ;로
        if not group:
            raise ContractError(f'{where}: sop_id 칸이 비었습니다')
        for sop in group:
            if sop not in by:
                raise ContractError(f'{where}: targets.csv에 없는 SOP {sop}')
        if len(set(group)) != len(group):
            raise ContractError(f'{where}: sop_id에 같은 SOP가 두 번')
        if k not in KINDS:
            raise ContractError(f'{where}: 칸 「{k}」 — {" · ".join(KINDS)} 가운데 하나')
        for sop in group:
            by[sop][k].append((where, r))
    fms, todo, missing_ids, sops = [], [], [], []
    for t in targets:
        sid, b = t['sop_id'], by[t['sop_id']]
        if not any(b.values()):
            todo.append(f'{sid}: condition_classes.csv에 행이 없음')
            continue
        one = {}
        for k in ('고장 유형', '종류·코드', '승인'):
            if len(b[k]) != 1:
                todo.append(f'{sid}: 「{k}」 행이 {len(b[k])}개(1개여야 함)')
            one[k] = b[k][0] if b[k] else None
        fm = None
        if one['고장 유형']:
            where, r = one['고장 유형']
            fm = r['글'].strip()
            if fm not in fm_names:
                raise ContractError(f'{where}: 고장 유형 {fm}이 data/failuremodes.csv에 없음')
            _, src = resolve(lab, r['원문'], where)
            if fm not in [f['id'] for f in fms]:
                fms.append({'id': fm, 'name': fm_names[fm], 'source': '; '.join(src)})
        kind, codes = None, []
        if one['종류·코드']:
            where, r = one['종류·코드']
            resolve(lab, r['원문'], where)
            text = r['글'].strip()
            if text != '없음':
                if ':' not in text or text.split(':', 1)[0] not in ('control', 'work_order'):
                    raise ContractError(f'{where}: 종류·코드의 글은 「control:코드;코드」 · 「work_order:코드」 · 「없음」 꼴')
                kind, rest = text.split(':', 1)
                codes = [c.strip() for c in rest.split(';') if c.strip()]
        items = {}
        for k, key in (('적용', 'apply_conditions'), ('금지', 'prohibitions'), ('제한', 'prohibitions'), ('완료', 'completion')):
            for where, r in b[k]:
                quotes, src = resolve(lab, r['원문'], where)
                text = r['글'].strip() or ' '.join(quotes)
                if not text:
                    raise ContractError(f'{where}: 매뉴얼 밖 원문만 가리키면 글 칸에 그 조건을 적습니다')
                item = ({'type': k} if key == 'prohibitions' else {}) | {'text': text, 'source': '; '.join(src),
                                                                         'rules': [x.strip() for x in r['규칙'].split(';') if x.strip()]}
                items.setdefault(key, []).append(item)
        approval = {'role': '', 'source': ''}
        if one['승인']:
            where, r = one['승인']
            _, src = resolve(lab, r['원문'], where)
            if not r['글'].strip():
                raise ContractError(f'{where}: 승인 행의 글 칸에 역할을 적습니다(원문에서 찾지 못했으면 「미확인」으로 시작해 찾아본 결과)')
            approval = {'role': r['글'].strip(), 'source': '; '.join(src)}
        steps = [{'order': step, 'text': text, 'source': f'{sec} {sid} 단계 {step}'}
                 for no, (sec, sop, step, text) in manual_lines(lab).items() if sop == sid and isinstance(step, int)]
        try:
            refs, miss = model_refs(lab, sid, rule, kind_of)
            missing_ids += [f'{sid}: {m}' for m in miss]
        except Unfilled as e:
            refs = {'assets': [], 'components': [], 'sensors': [], 'not_linked': ''}
            todo.append(str(e))
        sops.append({'id': sid, 'name': t['name'], 'kind': kind, 'codes': codes, 'source': t['source_section'], 'failure_mode': fm,
                     'model_refs': refs, 'apply_conditions': items.get('apply_conditions', []), 'prohibitions': items.get('prohibitions', []),
                     'steps': steps, 'completion': items.get('completion', []), 'approval': approval})
    causes, relations = [], []
    for line, r in rels:
        where = f'app/features/relations.csv:{line}'
        t = r['type'].strip()
        if t not in RELATIONS:
            todo.append(f'relations.csv 오류 — {where}: type 「{t}」 — {" · ".join(RELATIONS)} 가운데 하나')
            continue
        try:
            _, src = resolve(lab, r['원문'], where)
        except ContractError as e:                        # 관계 칸의 오류는 관계 단계에서 보이게 남긴다(조건 분류 단계를 막지 않음)
            todo.append(f'relations.csv 오류 — {e}')
            continue
        relations.append({'type': t, 'from': r['from'].strip(), 'to': r['to'].strip(), 'source': '; '.join(src)})
        if r['to'].strip().startswith('cause:') and r['to'].strip() not in [c['id'] for c in causes]:
            if not r['이름'].strip():
                raise ContractError(f'{where}: 원인 {r["to"]}의 이름 칸이 비었습니다')
            causes.append({'id': r['to'].strip(), 'name': r['이름'].strip(), 'source': '; '.join(src)})
    if rel_error:
        todo.append(f'relations.csv 오류 — {rel_error}')
    elif not rels:
        todo.append('relations.csv에 아직 행이 없음')
    doc = {'document': {'id': 'HM-8', 'revision': '1.1', 'file': f'data/{MANUAL}'}, 'failure_modes': fms, 'causes': causes, 'sops': sops, 'relations': relations}
    write_text(lab/'output/sop.json', json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    return doc, todo, missing_ids


def trace(lab):
    """sop.json · condition_table.csv의 출처마다 원문 줄을 찾는다 → (행 목록, 짝이 맞지 않는 목록). 매뉴얼 밖 자료(파일:줄)는 그 줄이 있는지만 본다."""
    lab = Path(lab)
    items = []
    doc = json.loads((lab/'output/sop.json').read_text(encoding='utf-8-sig'))
    for s in doc['sops']:
        for key in ('apply_conditions', 'prohibitions', 'steps', 'completion'):
            for i, it in enumerate(s[key], 1):
                items.append((f'{s["id"]} {key}[{i}]', it['text'], it['source']))
        items.append((f'{s["id"]} approval', s['approval']['role'], s['approval']['source']))
    if (lab/'app/features/condition_table.csv').is_file():
        seen, skip = set(), csv_body(lab/'app/features/condition_table.csv')[1]
        for line, r in enumerate(read_csv(lab/'app/features/condition_table.csv'), start=skip + 2):
            if (r['rule_id'], r['action']) not in seen:
                seen.add((r['rule_id'], r['action']))
                items.append((f'조건표 {r["rule_id"]} {r["action"]} (app/features/condition_table.csv:{line})', r['reason'], r['source_section']))
    out, miss = [], []
    for item, text, source in items:
        for part, no, found in source_parts(lab, source):
            out.append({'항목': item, '내용': text, '출처 조각': part, '원문 줄': no or '—', '원문': found})
            if no is None:
                miss.append(f'{item}: {part} — {found}')
    return out, miss
