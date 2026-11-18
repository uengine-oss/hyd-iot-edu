"""작업 절차와 판단 조건을 연결해 조치 기준 만들기 — 기능마다 결과 화면에 보일 표를 만든다(제공 — 고치지 않는다). 판단의 답은 이 파일에 없다."""
from pathlib import Path
import collections
import json
import shutil
import subprocess
import sys

from app.utils import rules as R
from app.utils import sop as S
from app.utils.results import Blank, Stop, compare, counts, note, read_text, table

HERE = Path(__file__).resolve().parents[2]
DATA, FEATURES, OUTPUT = HERE / 'data', HERE / 'app/features', HERE / 'output'
TITLE = '작업 절차와 판단 조건을 연결해 조치 기준 만들기'
EXPECTED_COLUMNS = ['사례', '후보', '기대_판정', '기대_규칙', '근거']
VERDICTS = ('허용', '제외', '후보 아님')
SCOPE_POINT = '적용 범위'


def lines(path):
    return len(read_text(path)[0].splitlines())


def export_rows(section):
    """결정표 내보내기의 한 절 → [dict]."""
    rows, head, now = [], None, None
    for line in read_text(DATA / 'decision_table_export.txt')[0].splitlines():
        if line.startswith('## '):
            now, head = line[3:].strip(), None
        elif now == section and line.strip() and not line.startswith('#'):
            cells = [c.strip() for c in line.split(' | ')]
            if head is None:
                head = cells
            else:
                rows.append(dict(zip(head, cells)))
    return rows


def sources(_):
    assets = S.model()
    files = sorted(p for p in DATA.rglob('*') if p.is_file())
    sops = S.targets()
    return [
        table('받은 자료', ['파일', '줄 수'], [[p.relative_to(HERE).as_posix(), lines(p)] for p in files]),
        table(f'설비 모델의 설비와 구성 요소 — {S.rel(S.model_dir())}', ['설비', '이름', '모델', '상태', '구성 요소'],
              [[i, a['name'], a['model'], a['status'], ' · '.join(a['components'])] for i, a in assets.items()]),
        table('매뉴얼의 SOP와 수행 단계 수', ['SOP', '이름', '종류', '절', '번호 줄 수'],
              [[i, t['name'], t['종류'], t['source_section'], len(S.steps(i))] for i, t in sops.items()]),
        table('매뉴얼 문장 번호 — 표의 「원문」 칸에 이 번호를 씁니다', ['원문', '절', 'SOP', '단계', '글'], S.sentences()),
        counts('판단 시스템 결정표 내보내기', [('결정', len(export_rows('결정'))), ('입력 데이터', len(export_rows('입력 데이터'))), ('규칙', len(export_rows('규칙')))]),
        counts('확인 사례', sorted(collections.Counter(r['설비'] for r in R.read_rows(DATA / 'check_cases.csv')).items())),
    ]


def expected_rows():
    rows = R.read_rows(FEATURES / 'expected.csv', EXPECTED_COLUMNS)
    cases = {r['경보_ID'] for r in R.read_rows(DATA / 'check_cases.csv')}
    known = S.targets()
    for r in rows:
        where = f'app/features/expected.csv:{r["_line"]}'
        if r['사례'] not in cases:
            raise Stop(f'{where}: 사례 「{r["사례"]}」가 data/check_cases.csv의 경보_ID에 없습니다.')
        if r['후보'] not in known:
            raise Stop(f'{where}: 후보 「{r["후보"]}」가 data/targets.csv에 없습니다.')
        if r['기대_판정'] not in VERDICTS:
            raise Stop(f'{where}: 기대_판정은 ' + ' · '.join(VERDICTS) + f' 가운데 하나입니다(지금: 「{r["기대_판정"]}」).')
    return rows


def expected(_):
    rows = expected_rows()
    if not rows:
        raise Blank('app/features/expected.csv에 기대 판정이 아직 없습니다.')
    return [table('내가 정한 기대 판정', EXPECTED_COLUMNS, rows),
            counts('기대 판정 수', sorted(collections.Counter(r['기대_판정'] for r in rows).items()))]


def need(name, what):
    """what = 조사까지 붙인 말(「관계가」)."""
    if not R.read_rows(FEATURES / name):
        raise Blank(f'app/features/{name}에 {what} 아직 없습니다.')


def sop_view(_):
    need('sop_items.csv', '조건 문장이')
    items = S.read_items()
    names = S.targets()
    rows = [[' · '.join(x['sops']), x['item'], ' · '.join(x['refs']), ' / '.join(x['text']), ' · '.join(x['rules'])] for x in items]
    per = [[sid, t['name'], ' → '.join(f'{s["order"]}. {s["text"]}' for s in S.steps(sid)),
            ' · '.join(sorted({x['item'] for x in items if sid in x['sops']}, key=S.ITEMS.index)) or '아직 없음'] for sid, t in names.items()]
    used = {ref for x in items for ref in x['refs']}      # 줄 번호만 적은 원문은 그 줄의 문장 모두를 가리킨다
    left = [s for s in S.sentences() if not s['단계'] and s['원문'] not in used and s['원문'].split('.')[0] not in used]
    return [table('조건 문장과 SOP 항목 — 원문 인용은 번호로 찾은 문장 그대로', ['SOP', '항목', '원문', '인용', '규칙'], rows),
            table('SOP마다 수행 단계(매뉴얼의 번호 줄을 옮김)와 채운 항목', ['SOP', '이름', '수행 단계', '채운 항목'], per),
            table('어느 항목에도 넣지 않은 문장(번호 줄 제외)', ['원문', '절', 'SOP', '글'], left,
                  note='설명 문장이라 넣지 않은 것인지, 빠뜨린 조건인지 봅니다.')]


def relations_view(_):
    need('relations.csv', '관계가')
    rel = S.read_relations()
    fms = S.failure_modes()
    name = {**{f['id']: f['name'] for f in fms}, **{c['id']: c['name'] for f in fms for c in f['causes']}, **{i: t['name'] for i, t in S.targets().items()}}
    linked = {r['to'] for r in rel if r['type'] != 'ADDRESSES'}
    causes = [[f['name'], c['name'], ' · '.join(name[r['from']] for r in rel if r['type'] == 'ADDRESSES' and r['to'] == c['id']) or '이은 조치 없음'] for f in fms for c in f['causes']]
    return [table('고장 유형 · 원인 · 조치 관계', ['type', 'from', 'to', '원문', '인용'],
                  [[r['type'], f'{r["from"]} {name[r["from"]]}', f'{r["to"]} {name[r["to"]]}', ' · '.join(r['source']), ' / '.join(r['text'])] for r in rel]),
            table('원인마다 이은 조치', ['고장 유형', '원인', '이 원인에 맞춘 SOP(ADDRESSES)'], causes),
            table('고장 유형에 잇지 않은 SOP', ['SOP', '이름'], [[i, t['name']] for i, t in S.targets().items() if i not in linked],
                  note='비어 있어야 모든 SOP가 어느 고장 유형의 조치인지 정해진 것입니다.')]


def scope_view(_):
    need('scope.csv', '적용 범위가')
    S.decision(SCOPE_POINT)
    scope, assets, names = S.read_scope(), S.model(), S.targets()
    rows = []
    for sid, s in scope.items():
        for a in s['assets']:
            have = [c for c in s['components'] if c in assets[a]['components']]
            lack = [c for c in s['components'] if c not in assets[a]['components']]
            rows.append([sid, names[sid]['name'], a, assets[a]['model'], ' · '.join(have) or '-', ' · '.join(lack) or '-'])
    off = [[sid, names[sid]['name'], ' · '.join(a for a in assets if a not in s['assets']) or '-', s['reason']] for sid, s in scope.items()]
    return [table('SOP를 건 설비 — 그 설비 모델에 SOP가 다루는 구성 요소가 있는가', ['SOP', '이름', '건 설비', '모델', '모델에 있는 구성 요소', '모델에 없는 구성 요소'], rows),
            table('SOP마다 걸지 않은 설비와 적은 까닭', ['SOP', '이름', '걸지 않은 설비', '까닭'], off),
            counts('설비마다 걸린 SOP 수', [(a, sum(a in s['assets'] for s in scope.values())) for a in assets])]


def judged(doc, rules):
    """확인 사례마다 SOP 다섯의 판정 — [{'사례 / 후보', '설비', '판정', '규칙', '판정_상세'}]."""
    out = []
    for row in R.read_rows(DATA / 'check_cases.csv'):
        cands = {sid: (ok, why) for sid, ok, why in R.candidates(row, doc)}
        for sop in doc['sops']:
            ok, why = cands.get(sop['id'], (False, '이 경보의 고장 유형에 잇지 않은 SOP'))
            j = R.judge(sop['id'], row, rules) if ok else None
            out.append({'사례 / 후보': f'{row["경보_ID"]} / {sop["id"]}', '설비': row['설비'], '판정': j['status'] if j else '후보 아님', '규칙': R.rule_ids(j) if j else '',
                        '판정_상세': R.short(j) if j else f'후보 아님 — {why}'})
    return out


def rules_view(_):
    need('decision_table.csv', '규칙이')
    rules = R.load_rules(FEATURES / 'decision_table.csv')
    need('sop_items.csv', '조건 문장이')
    need('relations.csv', '관계가')
    need('scope.csv', '적용 범위가')
    S.decision(SCOPE_POINT)
    doc = S.build({r['id'] for r in rules})
    known = S.targets()
    for r in rules:
        gone = [t for t in r['targets'] if t not in known]
        if gone:
            raise Stop(f'app/features/decision_table.csv:{r["line"]}: 적용_대상 {gone}이 data/targets.csv에 없습니다.')
    tied = collections.Counter(x for s in doc['sops'] for i in s['items'] for x in i['rules'])
    rule_rows = [[r['id'], r['result'], '' if r['penalty'] is None else f'{r["penalty"]:g}', ' · '.join(r['targets']),
                  ' 그리고 '.join(f'{c["input"]} {c["operator"]} {c["value"]:g} {c["unit"]}'.strip() if isinstance(c['value'], float) else f'{c["input"]} {c["operator"]} {c["value"]}' for c in r['conditions']),
                  r['source'], '예' if tied[r['id']] else '아니오'] for r in rules]
    actual = judged(doc, rules)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / 'sop.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    shutil.copyfile(FEATURES / 'decision_table.csv', OUTPUT / 'decision_table.csv')
    blocks = [table('결정표의 규칙', ['규칙', '결과', '감점(만원)', '적용 대상', '조건', '출처', 'SOP 항목에 이어짐'], rule_rows,
                    note='「SOP 항목에 이어짐」이 아니오인 규칙은 sop_items.csv의 규칙 칸에 그 이름을 적어 조건 문장과 잇습니다.'),
              table('확인 사례 · 후보마다 판정', ['사례 / 후보', '설비', '판정'], [[a['사례 / 후보'], a['설비'], a['판정_상세']] for a in actual])]
    exp = expected_rows()
    if exp:
        blocks.append(compare('기대 판정 ↔ 결정표를 댄 판정', '사례 / 후보',
                              [{'사례 / 후보': f'{r["사례"]} / {r["후보"]}', '판정': r['기대_판정'], '규칙': R.norm_ids(r['기대_규칙'])} for r in exp],
                              [a for a in actual if a['사례 / 후보'] in {f'{r["사례"]} / {r["후보"]}' for r in exp}], ['판정', '규칙'],
                              note='규칙 칸은 그 후보에 걸린 규칙 이름입니다(맞은 규칙과 확인되지 않은 조건으로 남은 규칙). 판정이 같아도 걸린 규칙이 다르면 다름입니다.'))
    blocks.append(counts('판정 수', sorted(collections.Counter(a['판정'] for a in actual).items())))
    blocks.append(note('output/sop.json과 output/decision_table.csv를 썼습니다. 판단 기능 만들기 실습이 이 두 파일의 꼴을 그대로 읽습니다.'))
    return blocks


def check(_):
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    text = (p.stdout + p.stderr).strip()
    if p.returncode:
        raise Stop(text)
    return [note(text)]


COMMANDS = {
    'sources': ('받은 자료', sources),
    'expected': ('기대 판정', expected),
    'sop': ('조건 문장과 SOP 항목', sop_view),
    'relations': ('고장 유형 · 원인 · 조치 관계', relations_view),
    'scope': ('적용 범위', scope_view),
    'rules': ('결정표 규칙과 확인 사례 판정', rules_view),
    'check': ('구조 검사', check),
}
