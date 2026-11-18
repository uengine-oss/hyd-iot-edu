"""설비 조건별 최적의 조치를 비교하는 판단 기능 만들기 — 기능마다 결과 화면에 보일 표를 만든다(제공 — 고치지 않는다). 판단의 답은 이 파일에 없다."""
from pathlib import Path
import collections
import importlib
import json
import subprocess
import sys

from app.utils import compare as C
from app.utils import rules as R
from app.utils.results import Blank, Stop, compare, counts, note, read_text, rel, table

HERE = Path(__file__).resolve().parents[2]
DATA, FEATURES, OUTPUT = HERE / 'data', HERE / 'app/features', HERE / 'output'
TITLE = '설비 조건별 최적의 조치를 비교하는 판단 기능 만들기'
KINDS = ['정상', '경계', '복수 조건', '모두 제외', '필수값 누락']
EXPECTED_COLUMNS = ['사례_종류', '사례', '후보', '기대_판정', '기대_규칙', '근거']
VERDICTS = ('허용', '제외', '후보 아님')
DECISION_COLUMNS = ['지점', '고른_것', '근거', '바뀌는_답']
ORDER_POINT, STATEMENT_POINT = '쓰는 사람에 따라 갈리는 답', '비교 기준 문장'
NEEDS = {ORDER_POINT: DECISION_COLUMNS[1:], STATEMENT_POINT: ['고른_것', '근거']}      # 비교 기준 문장은 내 말로 쓰는 줄이라 바뀌는_답을 받지 않는다


def criteria_dir():
    """쓰는 조치 기준. `app/features/criteria/`에 decision_table.csv와 sop.json이 둘 다 있으면 그것, 아니면 제공 기준."""
    mine = FEATURES / 'criteria'
    return mine if (mine / 'decision_table.csv').is_file() and (mine / 'sop.json').is_file() else DATA / 'criteria'


def load():
    folder = criteria_dir()
    try:
        doc = json.loads(read_text(folder / 'sop.json')[0])
    except json.JSONDecodeError as e:
        raise Stop(f'{rel(folder / "sop.json")}:{e.lineno}: JSON 꼴이 아닙니다 — {e.msg}') from None
    return doc, R.load_rules(folder / 'decision_table.csv'), R.read_rows(DATA / 'alarms.csv')


def decision(point):
    """decisions.csv에서 그 줄. 채워야 할 칸이 비어 있으면 그 줄을 짚고 멈춘다."""
    path = FEATURES / 'decisions.csv'
    rows = [r for r in R.read_rows(path, DECISION_COLUMNS) if r['지점'] == point]
    if not rows:
        raise Stop(f'{rel(path)}: 「{point}」 줄이 없습니다. 받은 빈 틀의 그 줄을 지우지 않습니다.')
    r = rows[0]
    empty = [c for c in NEEDS[point] if not r[c]]
    if empty:
        how = '내가 고른 것과 이유를 적고' if point == ORDER_POINT else '내 말로 쓴 문장과 읽은 근거 줄을 적고'
        raise Stop(f'{rel(path)}:{r["_line"]}: 「{point}」의 ' + ' · '.join(empty) + f' 칸이 비어 있습니다. {how} 다시 실행합니다.')
    return r


def judged(doc, rules, alarms):
    """경보마다 후보 선택과 판정 — [{'row', 'candidates': [판정 dict], 'not_candidates': [{'sop', 'reason'}]}]."""
    out = []
    for row in alarms:
        picked = R.candidates(row, doc)
        out.append({'row': row, 'candidates': [R.judge(sid, row, rules) for sid, ok, _ in picked if ok],
                    'not_candidates': [{'sop': sid, 'reason': why} for sid, ok, why in picked if not ok]})
    return out


def verdict_rows(events):
    rows = []
    for e in events:
        rid = e['row']['경보_ID']
        rows += [{'사례 / 후보': f'{rid} / {j["sop"]}', '설비': e['row']['설비'], '판정': j['status'], '규칙': R.rule_ids(j), '판정_상세': R.short(j)} for j in e['candidates']]
        rows += [{'사례 / 후보': f'{rid} / {n["sop"]}', '설비': e['row']['설비'], '판정': '후보 아님', '규칙': '', '판정_상세': f'후보 아님 — {n["reason"]}'} for n in e['not_candidates']]
    return rows


def condition_text(rule):
    return ' 그리고 '.join(f'{c["input"]} {c["operator"]} {c["value"]:g} {c["unit"]}'.strip() if isinstance(c['value'], float) else f'{c["input"]} {c["operator"]} {c["value"]}'
                         for c in rule['conditions'])


def sources(_):
    doc, rules, alarms = load()
    blank = [[r['경보_ID'], r['설비'], ' · '.join(k for k, v in r.items() if k != '_line' and v == '')] for r in alarms if '' in [v for k, v in r.items() if k != '_line']]
    return [table('받은 자료', ['파일', '줄 수'], [[p.relative_to(HERE).as_posix(), len(read_text(p)[0].splitlines())] for p in sorted(DATA.rglob('*')) if p.is_file()]),
            counts(f'쓰는 조치 기준 — {rel(criteria_dir())}', [('SOP', len(doc['sops'])), ('관계', len(doc['relations'])), ('결정표 규칙', len(rules))]),
            table('결정표의 규칙', ['규칙', '결과', '감점(만원)', '적용 대상', '조건', '출처'],
                  [[r['id'], r['result'], '' if r['penalty'] is None else f'{r["penalty"]:g}', ' · '.join(r['targets']), condition_text(r), r['source']] for r in rules],
                  note='조건이 「그리고」로 이어진 규칙은 조건이 모두 맞아야 맞습니다.'),
            table('SOP마다 건 설비', ['SOP', '이름', '종류', '건 설비'], [[s['id'], s['name'], s['kind'], ' · '.join(s['assets']) or '-'] for s in doc['sops']]),
            counts('설비마다 경보 수', sorted(collections.Counter(r['설비'] for r in alarms).items())),
            table('값이 빈 칸이 있는 경보', ['경보', '설비', '빈 칸'], blank)]


def expected_rows():
    rows = R.read_rows(FEATURES / 'expected.csv', EXPECTED_COLUMNS)
    doc, rules, alarms = load()
    ids, sops, known = {r['경보_ID'] for r in alarms}, {s['id'] for s in doc['sops']}, {r['id'] for r in rules}
    for r in rows:
        where = f'app/features/expected.csv:{r["_line"]}'
        if r['사례_종류'] not in KINDS:
            raise Stop(f'{where}: 사례_종류는 ' + ' · '.join(KINDS) + f' 가운데 하나입니다(지금: 「{r["사례_종류"]}」).')
        if r['사례'] not in ids:
            raise Stop(f'{where}: 사례 「{r["사례"]}」가 data/alarms.csv의 경보_ID에 없습니다.')
        if r['후보'] not in sops:
            raise Stop(f'{where}: 후보 「{r["후보"]}」가 조치 기준의 SOP에 없습니다.')
        if r['기대_판정'] not in VERDICTS:
            raise Stop(f'{where}: 기대_판정은 ' + ' · '.join(VERDICTS) + f' 가운데 하나입니다(지금: 「{r["기대_판정"]}」).')
        odd = [x for x in R.split(r['기대_규칙']) if x not in known]
        if odd:
            raise Stop(f'{where}: 기대_규칙 {odd}이 결정표의 rule_id에 없습니다.')
    return rows


def expected(_):
    rows = expected_rows()
    if not rows:
        raise Blank('app/features/expected.csv에 기대 판정이 아직 없습니다.')
    seen = collections.Counter(k for k, _ in {(r['사례_종류'], r['사례']) for r in rows})
    return [table('내가 정한 기대 판정', EXPECTED_COLUMNS, rows),
            counts('사례 종류마다 고른 경보 수', [(k, seen[k]) for k in KINDS])]


def judge_view(_):
    doc, rules, alarms = load()
    rows = verdict_rows(judged(doc, rules, alarms))
    return [table('경보 · 후보마다 판정과 이유', ['사례 / 후보', '설비', '판정'], [[r['사례 / 후보'], r['설비'], r['판정_상세']] for r in rows]),
            counts('판정 수', sorted(collections.Counter(r['판정'] for r in rows).items()))]


def held(kept):
    """학생이 구현한 함수를 부른다 — 견준 후보 가운데 1순위로 내주지 않고 뒤에 보일 후보와 그 까닭. 아직 빈 틀이면 그렇다고 알린다."""
    sys.path.insert(0, str(HERE))
    try:
        module = importlib.import_module('app.features.compare_rule')
        back = module.hold_back(kept)
    except NotImplementedError:
        raise Blank('app/features/compare_rule.py의 hold_back이 아직 빈 틀입니다.') from None
    if not isinstance(back, dict) or any(k not in {x['sop'] for x in kept} or not isinstance(v, str) or not v.strip() for k, v in back.items()):
        raise Stop('app/features/compare_rule.py: hold_back은 {뒤에 보일 후보 ID: 까닭 글}을 돌려줘야 합니다. 받은 후보에 없는 ID나 빈 까닭이 있습니다.')
    return back


def order(totals, back):
    """내줄 차례 — 뒤로 미루지 않은 후보를 비교값이 작은 차례로, 그 뒤에 미룬 후보를 비교값이 작은 차례로."""
    return sorted(totals, key=lambda s: (s in back, totals[s], s))


def compared():
    """판정에 비교값 · 순위와 내줄 차례를 더한다. 허용된 후보는 경고나 감점이 붙어도 모두 견준다."""
    decision(ORDER_POINT)
    doc, rules, alarms = load()
    events = judged(doc, rules, alarms)
    loaded = C.load()
    for e in events:
        totals = {}
        for j in e['candidates']:
            j['comparison'], j['not_compared'], j['rank'], j['held_back'] = None, None, None, None
            if j['status'] != '허용':
                continue
            values, missing = C.losses(j['sop'], e['row'], sum(h['penalty'] for h in j['hits'] if h['result'] == '감점'), loaded)
            if values is None:
                j['not_compared'] = '값이 없는 칸: ' + ' · '.join(missing)
            else:
                j['comparison'] = values
                totals[j['sop']] = values['비교값']
        by = {j['sop']: j for j in e['candidates']}
        for sop, rank in C.ranked(totals).items():
            by[sop]['rank'] = rank
        kept = [{'sop': s, 'warnings': [h['rule_id'] for h in by[s]['hits'] if h['result'] == '경고'] + [u['rule_id'] for u in by[s]['unknown'] if u['result'] == '경고'],
                 'penalties': [h['rule_id'] for h in by[s]['hits'] if h['result'] == '감점']} for s in totals]
        back = held(kept) if kept else {}
        for sop, why in back.items():
            by[sop]['held_back'] = why
        e['order'] = order(totals, back)
        e['top'] = e['order'][:1]
    return doc, events


def compare_view(_):
    doc, events = compared()
    name = {s['id']: s['name'] for s in doc['sops']}
    rows, tops = [], []
    for e in events:
        rid = e['row']['경보_ID']
        by = {j['sop']: j for j in e['candidates']}
        for j in e['candidates']:
            c = j['comparison']
            place = e['order'].index(j['sop']) + 1 if j['sop'] in e['order'] else ''
            rows.append([rid, j['sop'], R.short(j), *([f'{c[k]:.2f}' for k in (*C.PARTS, '비교값')] if c else [''] * 6), j['rank'] or '', place, j['held_back'] or j['not_compared'] or ''])
        tops.append([rid, e['row']['설비'], e['row']['팬100_연속_h'], ' · '.join(f'{s} {name[s]}' for s in e['top']) or '없음',
                     ' · '.join(R.short(by[s]) for s in e['top']), ' · '.join(s for s in e['order'] if by[s]['held_back']) or '-'])
    return [table('경보마다 1순위로 내줄 후보', ['경보', '설비', '팬100_연속_h', '1순위', '1순위의 판정', '뒤로 미룬 후보'], tops,
                  note='1순위는 내가 정한 기준으로 맨 앞에 내주는 후보입니다. 실행 승인이 아닙니다. 팬100_연속_h가 0보다 크면 그 설비는 팬이 이미 100 %로 돌고 있습니다.'),
            table('후보마다 비교값(만 원)과 순위', ['경보', '후보', '판정', *C.PARTS, '비교값', '비교값 순위', '내줄 차례', '뒤로 미룬 까닭 · 견주지 못한 까닭'], rows)]


def view(e):
    return {'id': e['row']['경보_ID'], 'asset': e['row']['설비'],
            'candidates': [{'sop': j['sop'], 'status': j['status'], 'hits': j['hits'], 'unknown': j['unknown'], 'comparison': j['comparison'],
                            'not_compared': j['not_compared'], 'rank': j['rank'], 'held_back': j['held_back']} for j in e['candidates']],
            'not_candidates': e['not_candidates'], 'order': e['order'], 'top': e['top']}


def write(_):
    statement = decision(STATEMENT_POINT)
    doc, events = compared()
    out = {'criteria': rel(criteria_dir()), 'decisions': {ORDER_POINT: decision(ORDER_POINT)['고른_것'], STATEMENT_POINT: statement['고른_것']},
           'events': [view(e) for e in events]}
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / 'judgement.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    with_top = sum(1 for e in events if e['top'])
    return [note('비교 기준 문장: ' + statement['고른_것']),
            counts('output/judgement.json에 쓴 것', [('경보', len(events)), ('1순위가 있는 경보', with_top), ('1순위가 없는 경보', len(events) - with_top)]),
            note('output/judgement.json을 썼습니다. 1순위는 내가 정한 기준으로 맨 앞에 내주는 후보이고 실행 승인이 아닙니다.')]


def cases_view(_):
    exp = expected_rows()
    if not exp:
        raise Blank('app/features/expected.csv에 기대 판정이 아직 없습니다.')
    doc, rules, alarms = load()
    actual = verdict_rows(judged(doc, rules, alarms))
    keys = {f'{r["사례"]} / {r["후보"]}' for r in exp}
    seen = collections.Counter(k for k, _ in {(r['사례_종류'], r['사례']) for r in exp})
    return [compare('사례 대조 — 기대 ↔ 판정', '사례 / 후보', [{'사례 / 후보': f'{r["사례"]} / {r["후보"]}', '판정': r['기대_판정'], '규칙': R.norm_ids(r['기대_규칙'])} for r in exp],
                    [a for a in actual if a['사례 / 후보'] in keys], ['판정', '규칙'],
                    note='규칙 칸은 그 후보에 걸린 규칙 이름입니다(맞은 규칙과 확인되지 않은 조건으로 남은 규칙). 판정이 같아도 걸린 규칙이 다르면 다름입니다.'),
            table('대조한 줄의 판정 이유', ['사례 종류', '사례 / 후보', '판정'],
                  [[r['사례_종류'], f'{r["사례"]} / {r["후보"]}', next(a['판정_상세'] for a in actual if a['사례 / 후보'] == f'{r["사례"]} / {r["후보"]}')] for r in exp]),
            counts('사례 종류마다 대조한 경보 수', [(k, seen[k]) for k in KINDS])]


def check(_):
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    text = (p.stdout + p.stderr).strip()
    if p.returncode:
        raise Stop(text)
    return [note(text)]


COMMANDS = {
    'sources': ('받은 자료', sources),
    'expected': ('기대 판정', expected),
    'judge': ('후보 선택과 판정', judge_view),
    'compare': ('비교값과 내줄 차례', compare_view),
    'write': ('비교 기준 문장과 결과 파일', write),
    'cases': ('사례 대조', cases_view),
    'check': ('구조 검사', check),
}
