"""통합02 프로젝트 생성에 쓰는 경로 변환과 제공 런타임. 기존 랩의 계산·검사 알고리즘을 재사용한다."""
from pathlib import Path
import ast
import re

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
    return text


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
    ui = 'import html\nFOLD = 30\n\n' + extract(source, {'JS', 'e', 'grid', 'render_block'})
    start = ui.index("        key = 'counts:'")
    end = ui.index("    if k == 'compare':", start)
    ui = ui[:start] + "        return title + grid(['항목', '개수'], b['items']) + tail\n" + ui[end:]
    ui = ui.replace("'짝(' + b['key'] + ')'", "('질문 · 입력 · 항목' if b['key'] == '짝' else b['key'])")
    # 표의 실제 비교와 검색을 재사용하고 단계 띠·진척도 페이지는 포함하지 않는다.
    ui += '\nCSS = ' + repr(DARK_CSS) + '\n' + RENDER
    return utilities, ui


DARK_CSS = '''*{box-sizing:border-box}body{margin:0;background:#181b20;color:#e6eaf0;font:16px/1.65 "Malgun Gothic",sans-serif}main{max-width:1240px;margin:auto;padding:30px 24px}h1{font-size:28px;margin:0}h2{font-size:22px}h3{font-size:17px;margin:0 0 14px}section{margin:18px 0;padding:20px;background:#232830;border:1px solid #3b424e;border-radius:10px;overflow:auto}.tbl{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 12px;border-bottom:1px solid #3b424e;text-align:left;vertical-align:top}th{background:#303743;cursor:pointer}td{overflow-wrap:anywhere}tr.hide{display:none}.note,small{color:#b6c1d0}.note,.err{white-space:pre-wrap}.err{border-left:4px solid #ff8e88;padding:12px;background:#422b2d}.st-같음{color:#8cdbbc}.st-다름,.st-실제,.st-사라짐{color:#ffaaa4}.st-기대,.st-늘어남,.st-값{color:#eac77b}input.f,button.t{font:inherit;color:#e6eaf0;background:#303743;border:1px solid #687589;border-radius:6px;padding:5px 10px;margin:0 8px 12px 0}input.f{max-width:100%}.src{white-space:pre-wrap;font-family:Consolas,monospace}.src b{display:inline-block;width:4em;color:#a5b3c5}@media(max-width:600px){main{padding:18px 12px}section{padding:14px}h1{font-size:24px}}'''

DARK_CSS += 'th{white-space:nowrap}td{word-break:keep-all}td[class^="st-"]{white-space:nowrap}.tbl:has(button.only) td:first-child{min-width:210px}'

RENDER = '''
def page(title, action, blocks):
    body = ''.join('<section>' + render_block(b, {}, {}) + '</section>' for b in blocks)
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(action)} · {e(title)}</title><style>{CSS}</style><main><small>{e(title)}</small>'
            f'<h1>{e(action)}</h1>{body}</main>{JS}</html>')
'''

RUN = '''"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
import os
import sys
import webbrowser
from app.utils import actions, results
from app.ui.render import page

ROOT = Path(__file__).resolve().parent


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
        blocks = [results.error('확인 필요', str(exc))]
    except Exception as exc:
        message = str(exc).replace(str(ROOT) + os.sep, '').replace(str(ROOT), '.')   # 학생 PC의 절대 경로를 보이지 않는다
        blocks = [results.error('실행 확인 필요 ' + results.where(exc), message)]
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
    text = text.replace("[sys.executable, 'check.py']", "[sys.executable, '-m', 'app.utils.check']")
    text = text.replace('python check.py', 'python run.py check')
    text = text.replace('결과 화면은 단계마다 다시 씁니다.', '실행한 기능의 결과를 이 화면에서 확인합니다.')
    return text
