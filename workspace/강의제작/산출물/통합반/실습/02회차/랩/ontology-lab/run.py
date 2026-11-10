"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
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
    except Exception as exc:
        blocks = [results.error('실행 확인 필요 ' + results.where(exc), f'{type(exc).__name__}: {exc}')]
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    target = output / 'result.html'
    first = not target.exists()
    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='\n')
    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(title)
    for block in blocks:
        if block['kind'] in ('note', 'error'):
            print(block['text'])
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
