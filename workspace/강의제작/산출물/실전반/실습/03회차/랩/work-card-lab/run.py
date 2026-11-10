"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
import os
import sys
import webbrowser
from app.utils import results
from app.utils import actions
from app.ui.render import page

ROOT = Path(__file__).resolve().parent


def env_twice():
    """.env에 같은 이름이 두 번 있으면(받은 세 줄을 빈 세 줄 위에 붙인 경우) 뒤의 빈 값이 이겨 키가 없는 것처럼 된다 — 줄 번호를 짚고 멈춘다."""
    path = ROOT / '.env'
    if not path.is_file():
        return None
    seen = {}
    for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if '=' in line and not line.strip().startswith('#'):
            seen.setdefault(line.split('=', 1)[0].strip(), []).append(n)
    twice = [f'{" · ".join(map(str, lines))}줄에 {name}' for name, lines in seen.items() if len(lines) > 1]
    return ('.env ' + ', '.join(twice) + '가 두 번 있습니다 — 등호 뒤가 빈 줄을 지우고 받은 세 줄만 남긴 뒤 저장합니다.') if twice else None


def main():
    parser = argparse.ArgumentParser(description=actions.TITLE)
    parser.add_argument('action', nargs='?', default='sources', choices=actions.COMMANDS)
    parser.add_argument('--no-open', action='store_true', help='브라우저를 열지 않습니다')
    args = parser.parse_args()
    title, function = actions.COMMANDS[args.action]
    try:
        twice = env_twice()
        if twice:
            raise results.Stop(twice)
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
    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='\n')
    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(title)
    for block in blocks:
        if block['kind'] in ('note', 'error'):
            print(block.get('title', '') + ('\n' if block.get('title') else '') + block['text'])
        elif block['kind'] == 'table':
            print(f"{block['title']}: {len(block['rows'])}행")
        elif block['kind'] == 'counts':
            print(f"{block['title']}: " + ' · '.join(f'{name} {value}' for name, value in block['items']))
    print('결과: output/result.html' + (' — 열린 화면에서 F5로 새로 고침합니다.' if not first else ''))
    if first and not args.no_open:
        webbrowser.open(target.as_uri())
    return int(any(b['kind'] == 'error' for b in blocks))


if __name__ == '__main__':
    sys.exit(main())
