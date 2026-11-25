"""통합02 프로젝트 생성에 쓰는 경로 변환과 제공 런타임. 기존 랩의 계산·검사 알고리즘을 재사용한다."""
from pathlib import Path
import ast
import re

import lab_frame as F

HERE = Path(__file__).resolve().parent
NAMES = {
    '설비_대장.csv': 'equipment.csv', '구성요소_목록.csv': 'components.csv',
    '센서_목록.csv': 'sensors.csv', '예비품_목록.csv': 'spare_parts.csv',
    '품번_교차표.csv': 'part_aliases.csv', '공급_조건.csv': 'supply_terms.csv',
    '승인공급사_목록.csv': 'approved_suppliers.csv', '입고_이력.csv': 'receipts.csv',
    '현장_메모.md': 'field_notes.md', '관계그림.json': 'relationships.json',
    '설계.csv': 'design.csv', '관계.csv': 'relations.csv', '이름.csv': 'name_overrides.csv',
    '물리량.csv': 'quantity_overrides.csv', '단위.csv': 'unit_overrides.csv',
    '행_처리.csv': 'row_rules.csv', '기대_답.csv': 'expected.csv',
    '정한_것.csv': 'decisions.csv', '요구사항.md': 'requirements.md', '검증_기록.md': 'review.md',
    '자료_검토.md': 'provenance.md', '센서_변경.csv': 'sensor_changes.csv',
    '설비_대장_변경.csv': 'equipment_changes.csv', '구성요소_변경.csv': 'component_changes.csv',
}


def convert(text):
    for old, new in sorted(NAMES.items(), key=lambda x: -len(x[0])):
        text = text.replace(old, new).replace(old.replace('.', r'\.'), new.replace('.', r'\.'))
    for old, new in [('결과/내_모델/', 'app/features/model/'), ('입력/자료_변경분/', 'data/changes/'), ('입력/자료/', 'data/'),
                     ('입력/schema.json', 'data/model/schema.json'), ('입력/graph.json', 'data/model/graph.json'),
                     ('입력/', 'data/'), ('자료/', 'data/'), ('결과/schema.json', 'output/schema.json'),
                     ('결과/graph.json', 'output/graph.json'), ('결과/', 'app/features/')]:
        text = text.replace(old, new)
    text = text.replace("'자료'", "'data'").replace("'결과'", "'app/features'")
    text = text.replace('START.md 「학생이 정할 것」의 그 자리 이름', '사람이 결정할 지점의 이름')
    text = text.replace('START.md', '가이드')
    text = text.replace('2026-10-20_수정본', '2026-10-20')
    return fill_term(text)


# 옛 구조의 「정할 자리」(학생이 AI와 채우는 `app/features/`의 파일)를 새 구조의 이름 「빈 틀」로 바꾼다(코딩랩.md K-7 `app/features/`).
# 「정할 지점」은 원자료만으로 정해지지 않아 학생이 근거를 대고 고르는 결정 지점의 이름이라 여기서 만들지 않는다.
# 「자리」는 받침이 없고 「틀」은 ㄹ 받침이라, 바로 뒤(괄호 풀이가 있으면 그 뒤)의 조사를 받침 있는 꼴로 바꾼다.
# 풀이가 「빈 틀」을 되풀이하는 괄호는 겹치지 않게 줄인다.
FILL_TERM = re.compile(r'정할 자리( \(`[^`]*` — 내가 AI와 채우는 빈 틀\)|\([^()]*\))?(를|가|는|와|라|다)?')
AFTER_CONSONANT = {'를': '을', '가': '이', '는': '은', '와': '과', '라': '이라', '다': '이다'}


def fill_term(text):
    def new(m):
        note = m.group(1) or ''
        head = ('빈 틀' + note.replace('채우는 빈 틀)', '채우는 파일)') if note.startswith(' (') else
                '빈 틀' if note == '(빈 틀)' else '빈 틀 파일' if note == '(「제공 빈 틀」 파일)' else '빈 틀' + note)
        return head + AFTER_CONSONANT.get(m.group(2) or '', '')
    return FILL_TERM.sub(new, text)


def extract(source, names):
    tree = ast.parse(source)
    selected = []
    for node in tree.body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign):
            name = next((n.id for n in node.targets if isinstance(n, ast.Name)), None)
        if name in names:
            selected.append(ast.get_source_segment(source, node))
    return '\n\n\n'.join(selected) + '\n'


def result_sources():
    source = (HERE / 'show_result.py').read_text(encoding='utf-8')
    utilities = ('from pathlib import Path\nimport csv, io, json, re, traceback\n'
                 'HERE = Path(__file__).resolve().parents[2]\n\n' + extract(source, {
                     'Stop', 'Blank', 'rel', 'read_text', 'read_table', 'read_json', 'source_lines',
                     'table', 'counts', 'compare', 'before_after', 'note', 'error', 'where'}))
    utilities = utilities.replace('상태 「비어 있음」.', '해당 조회를 작성한 뒤 실행한다.').replace('정할 자리 파일', '`app/features/` 파일').replace('정할 자리', '`app/features/`의 빈 틀')
    # 블록을 만드는 함수(그림 블록 포함 — result_figures.py)는 results.py에, 그리는 코드(result_view.py)는 render.py에 둔다.
    # 화면은 방금 실행한 기능 하나의 결과만 보이고 단계 띠 · 진척도는 두지 않는다(코딩랩 K-3).
    utilities += (HERE / 'result_figures.py').read_text(encoding='utf-8')
    return utilities, (HERE / 'result_view.py').read_text(encoding='utf-8')


RUN = '''"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
import os
import sys
import webbrowser
from app.utils import actions, results
from app.ui.render import page

''' + F.UTF8_OUT + '''
ROOT = Path(__file__).resolve().parent


def local(exc):
    """멈춘 까닭의 글에서 이 폴더의 절대 경로를 뗀다 — 화면과 터미널에 학생 PC의 경로를 보이지 않고 app/features/… 꼴로 짚는다."""
    text = str(exc)
    for root in (str(ROOT), ROOT.as_posix()):
        text = text.replace(root + os.sep, '').replace(root + '/', '').replace(root, '.')
    for name in ('app', 'data', 'output'):
        text = text.replace(name + os.sep, name + '/')
    return text.replace('features' + os.sep, 'features/').replace('model' + os.sep, 'model/')


def main():
    parser = argparse.ArgumentParser(description=actions.TITLE)
    parser.add_argument('action', nargs='?', default='sources', choices=actions.COMMANDS)
    parser.add_argument('--no-open', action='store_true', help='브라우저를 열지 않습니다')
    args = parser.parse_args()
    title, function = actions.COMMANDS[args.action]
    try:
        blocks = function({})
    except results.Blank as exc:
        blocks = [results.note('아직 비어 있습니다: ' + str(exc))]
    except results.Stop as exc:
        blocks = [results.error('확인 필요', local(exc))]
    except Exception as exc:
        blocks = [results.error('실행 확인 필요 ' + results.where(exc), local(exc))]
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    target = output / 'result.html'
    first = not target.exists()
    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='\\n')
    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
    print(title)
    for block in blocks:
        if block['kind'] in ('note', 'error'):
            print(block.get('title', '') + ('\\n' if block.get('title') else '') + block['text'])
        elif block['kind'] == 'verdict':
            print(block['text'] + (' — ' + block['detail'] if block.get('detail') else ''))
        elif block['kind'] == 'table':
            print(f"{block['title']}: {len(block['rows'])}행")
        elif block['kind'] == 'counts':
            print(' · '.join(f'{name} {value}' for name, value in block['items']))
    print('결과: output/result.html' + (' — 열린 화면에서 F5로 새로 고침합니다.' if not first else ''))
    if first and not args.no_open:
        webbrowser.open(target.as_uri())
    return int(any(b['kind'] == 'error' for b in blocks))


if __name__ == '__main__':
    sys.exit(main())
'''


def model_source():
    text = convert((HERE / 'session2_model_tool.py').read_text(encoding='utf-8'))
    text = text.replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    text = text.replace("OUT = HERE / 'app/features'", "OUT = HERE / 'app/features'\nOUTPUT = HERE / 'output'")
    for name in ('schema.json', 'graph.json'):
        text = text.replace(f"OUT / '{name}'", f"OUTPUT / '{name}'")
    text = text.replace('OUT.mkdir(exist_ok=True)', 'OUTPUT.mkdir(exist_ok=True)')
    text = text.replace('직접 실행하지 않는다 — `python show_result.py`가 단계마다 부른다.', '직접 실행하지 않는다 — 루트 run.py가 요청한 기능을 실행한다.')
    text = re.sub(r'\d+단계:', '', text)
    return text


def actions_source(L):
    import session2_steps
    text = session2_steps.render(L['kind'], L['title'], [s['name'] for s in L['steps']], L.get('change', False))
    text = text.split('STEPS =', 1)[0]
    text = text[text.index('from pathlib import Path'):]
    text = convert(text).replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    text = text.replace('import show_result as R', 'from app.utils import results as R')
    text = text.replace('import model_tool as M', 'from app.utils import model as M')
    text = text.replace('import lab_cypher as C', 'from app.utils import cypher as C')
    old = "[sys.executable, '-X', 'utf8', 'check.py']"
    if text.count(old) != 1:
        raise ValueError('구조 검사를 부르는 줄이 바뀌었습니다 — session2_steps.COMMON의 run_check를 다시 봅니다.')
    text = text.replace(old, "[sys.executable, '-X', 'utf8', '-m', 'app.utils.check']")
    text = text.replace('python check.py', 'python run.py check')
    text = text.replace('결과 화면은 단계마다 다시 씁니다.', '실행한 기능의 결과를 이 화면에서 확인합니다.')
    return text
