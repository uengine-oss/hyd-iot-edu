from pathlib import Path
import re
import subprocess
import sys
from app.utils import results as R

HERE = Path(__file__).resolve().parents[2]


def norm(text):
    """답 글자 견주기: 「·」 · 쉼표 · 공백으로 나눈 조각을 정렬해 다시 잇는다(순서 · 띄어쓰기 차이는 같게 본다)."""
    return ' · '.join(sorted(x for x in re.split(r'[·,\s]+', str(text or '')) if x))


def expected_rows(columns, key):
    """기대 답 표의 행. key = 한 행을 가리키는 열들 — 같은 짝이 두 줄이면 결과 화면이 한 줄을 조용히 덮으므로 두 줄 번호를 대고 멈춘다."""
    path = HERE / 'app/features/expected.csv'
    rows = R.read_table(path)
    text, _ = R.read_text(path)
    lines = [i for i, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')][1:]   # 데이터 행의 편집기 줄 번호
    seen = {}
    for line, r in zip(lines, rows):
        empty = [c for c in columns if not r.get(c)]
        if empty:
            raise R.Stop(f'app/features/expected.csv:{line}: 빈 칸 ' + ', '.join(empty))
        k = tuple(r.get(c, '') for c in key)
        if k in seen:
            raise R.Stop(f'app/features/expected.csv:{seen[k]} · {line}: 같은 ({" · ".join(key)}) 「{" · ".join(k)}」가 두 줄입니다 — 한 짝에 한 줄만 씁니다(여러 값은 한 칸에 「 · 」로).')
        seen[k] = line
    return rows


def run_check():
    p = subprocess.run([sys.executable, '-m', 'app.utils.check'], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = (p.stdout + p.stderr).strip()
    return [R.note('python run.py check\n' + text)] if p.returncode == 0 else [R.error('python run.py check — 구조 확인 필요', text)]

from app.utils import model as M

TITLE = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
KEY = ['질문', '물을_값', '항목']   # 기대 답 한 줄을 가리키는 열


def guarded(fn, *a):
    try:
        return fn(*a)
    except M.Stop as e:
        raise R.Stop(str(e))


def sources(previous):
    rows = [(p.name, len(R.read_table(p))) for p in sorted((HERE / 'data').glob('*.csv'))]
    return [R.table('원자료 파일과 행 수(머리줄 뺌)', ['파일', '행'], rows),
            R.note('이번 질문에 쓰는 것은 설비 대장 · 구성 요소 · 센서 · 예비품 · 품번 교차표입니다. 줄은 VS Code에서 열어 보고, 실행한 기능의 결과를 이 화면에서 확인합니다.')]


def expected(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답', '근거'], KEY)
    return [R.table('내가 원자료에서 먼저 적은 기대 답', ['질문', '물을_값', '항목', '기대_답', '근거'], rows)]


def design(previous):
    ids, links, prev = guarded(M.preview_ids)
    out = [R.table('종류와 ID 만드는 법(app/features/design.csv)', ['대상', 'ID_만드는_법'], [(k, v) for k, v in ids.items()]),
           R.table('관계와 방향(app/features/relations.csv)', ['연결', '관계 이름', '시작 → 끝'], [(k, n, f'{a} → {b}') for k, (n, a, b) in links.items()])]
    out.append(R.counts('원자료 행마다 내 ID를 지으면 — 서로 다른 ID 수', [(k, v['개수']) for k, v in prev.items()]))
    clash = [(k, i, ', '.join(f"{v['파일']}:{n}" for n in lines)) for k, v in prev.items() for i, lines in v['겹침'].items()]
    out.append(R.table('ID가 겹치는 원자료 행(이름 묶기 전)', ['대상', 'ID', '행'], clash,
                       note='겹친 ID 하나는 대상 하나가 됩니다. 같은 대상의 겹침인지, 다른 대상을 한 ID로 짓는 것인지는 원자료 줄을 열어 봅니다.'))
    return out


def names(previous):
    info, _ = guarded(M.build, '이름')
    rows = [(code, made_from, made) for code, (made_from, made) in info['구성 요소'].items()]
    n = info['이름']
    return [R.table('내 규칙(same_device · group_name)으로 묶인 이름', ['이름', '행 수', '원자료 이름(설비)'], n['묶음'],
                    note='묶음마다 원자료 이름과 설비를 보고, 같은 장치가 아닌 것이 섞였는지 원자료 줄로 봅니다.'),
            R.table('app/features/name_overrides.csv로 바꾼 이름', ['이름표 행', '원자료 이름', '모델', '규칙대로면', '바꾼 이름'], n['이름표']),
            R.table('다른 이름과 묶이지 않은 원자료 이름(그대로 씀)', ['원자료 행', '설비', '계통', '원자료 이름'], n['그대로'],
                    note='같은 장치인데 규칙이 묶지 못한 이름이면 app/features/name_overrides.csv에 근거와 함께 한 줄을 적습니다.'),
            R.table('설비별 구성 요소 — 원자료 행 수와 만든 대상 수', ['설비', '원자료 행', '만든 구성 요소'], rows),
            R.table('app/features/row_rules.csv · app/features/name_overrides.csv에 적었지만 쓰이지 않은 행', ['파일', '행'], info['unused'] + [(x, '') for x in n['안_쓴_이름표']])]


def sensors(previous):
    info, _ = guarded(M.build, '센서')
    groups = {}
    for sid, code, tag, q, kind in info['센서']:
        groups.setdefault(q, []).append(f'{code}:{tag}')
    kinds = {}
    for *_, kind in info['센서']:
        kinds[kind] = kinds.get(kind, 0) + 1
    q = info['물리량']
    return [R.counts('센서 수와 종류(kind_of)', [('센서', len(info['센서'])), *sorted(kinds.items())]),
            R.table('물리량마다 묶인 센서(same_quantity · quantity_name)', ['물리량', '센서 수', '설비:태그'], [(k, len(v), ' · '.join(sorted(v))) for k, v in sorted(groups.items())]),
            R.table('app/features/quantity_overrides.csv로 바꾼 센서', ['이름표 행', '원자료 행', '설비:태그', '재는것', '규칙대로면', '바꾼 것'], q['이름표']),
            R.table('app/features/quantity_overrides.csv에 적었지만 쓰이지 않은 행', ['행'], [(x,) for x in q['안_쓴_이름표']])]


def units(previous):
    info, _ = guarded(M.build, '단위')
    u = info['단위']
    return [R.table('물리량마다 기준 단위(base_unit)', ['물리량', '원자료에 적힌 단위', '기준 단위', '정한 곳'], u['기준']),
            R.table('단위를 바꾸거나 빈 칸을 채운 센서 행(blank_unit)', ['원자료 행', '센서 ID', '원래 단위', '쓴 단위', '모델의 단위', '원래 정상값 / 한계', '바꾼 정상값 / 한계'], info['변환']),
            R.table('app/features/unit_overrides.csv에 적었지만 쓰이지 않은 행', ['행'], [(x,) for x in u['안_쓴_이름표']])]


def parts(previous):
    info, _ = guarded(M.build, '부품')
    usage = {}
    for code, cname, pid, how in info['이은_부품']:
        usage.setdefault(pid, set()).add(code)
    linked = [x for x in info['물은_행'] if x[4] != '잇지 않음']
    left = [x for x in info['물은_행'] if x[4] == '잇지 않음']
    return [R.table('부품마다 쓰는 설비', ['사내 품번', '설비 수', '설비'], [(p, len(v), ' · '.join(sorted(v))) for p, v in sorted(usage.items())]),
            R.table('내 판단 함수(find_part)가 이은 행', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '이은 품번'], linked),
            R.counts('내 판단 함수(find_part)가 잇지 않은 행', [('교체부품 칸이 빈 행', sum(1 for x in left if x[3] == '(빈칸)')),
                                                            ('교체부품 칸에 글이 있는 행', sum(1 for x in left if x[3] != '(빈칸)'))]),
            R.table('잇지 않은 행', ['원자료 행', '설비', '구성 요소', '교체부품 칸', '정한 것'], left,
                    note='교체부품 칸에 글이 있는데 잇지 않은 행은 그 글과 예비품 목록을 함께 열어 까닭을 봅니다.'),
            R.table('같은 제조사 품번으로 등록된 사내 품번(same_item)', ['제조사 품번', '사내 품번', '한 물품으로'], [(c, ' · '.join(m), '예' if v else '아니오') for c, m, v in info['같은_규격']]),
            R.note('output/schema.json · output/graph.json을 새로 썼습니다.')]


def ask(previous):
    rows = expected_rows(['질문', '물을_값', '기대_답'], KEY)
    got = guarded(M.answers, list(dict.fromkeys((r['질문'], r['물을_값']) for r in rows)))   # 같은 설비를 여러 줄에 적어도 한 번만 묻는다
    key = lambda r: f"{r['질문']} | {r['물을_값']} | {r.get('항목', '')}"
    exp = [{'짝': key(r), '답': norm(r['기대_답'])} for r in rows]
    picked = {}      # 질문 1은 기대 답에 적은 구성 요소만 견준다(항목을 적은 설비)
    for r in rows:
        if str(r['질문']).strip() == '1' and r.get('항목'):
            picked.setdefault(r['물을_값'], set()).add(r['항목'])
    keep = [r for r in got if not (str(r['질문']) == '1' and r['물을_값'] in picked and r['항목'] not in picked[r['물을_값']])]
    act = [{'짝': key(r), '답': norm(r['답'])} for r in keep]
    return [R.compare('기대 답 ↔ 모델에 물은 답(질문 | 물을 값 | 항목)', '짝', exp, act, ['답'],
                      note=(f'질문 1은 기대 답에 적은 구성 요소만 견줍니다(모델이 더 돌려준 구성 요소 {len(got) - len(keep)}줄은 표에 넣지 않음). '
                            '「실제 없음」은 기대 답의 항목 이름이 모델의 이름과 다르거나 모델에 없는 것입니다. 「기대 밖」은 모델이 더 돌려준 항목입니다. '
                            '모델의 답 「없음」은 물은 품번 · 표기 · 설비 · 물리량이 모델에 없다는 뜻이고, 「쓰는 설비 없음」은 부품은 모델에 있지만 그 부품에 이은 구성 요소가 없다는 뜻입니다.'))]


def check(previous):
    return run_check()



COMMANDS = {
    'sources': ('원자료', sources),
    'expected': ('기대 답', expected),
    'design': ('식별자와 관계', design),
    'names': ('장치 이름', names),
    'quantities': ('물리량과 센서', sensors),
    'units': ('단위', units),
    'parts': ('공용 부품과 모델', parts),
    'query': ('질문별 대조', ask),
    'check': ('구조 검사', check),
}
