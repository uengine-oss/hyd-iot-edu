"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
import os
import sys
import webbrowser
from app.utils import actions, results
from app.ui.render import page

# 출력은 늘 UTF-8로 쓴다 — 한국어 Windows에서 AI가 이 명령을 대신 실행하면 파이썬이 cp949로 써서 한글이 깨지고 「—」 같은 글자에서 멈춘다.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding='utf-8')

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
    failed = any(b['kind'] == 'error' for b in blocks)
    saved = output / 'result.json'
    last = json.loads(saved.read_text(encoding='utf-8')).get('last_success') if saved.exists() else None
    if not failed:
        last = {'action': args.action, 'title': title, 'blocks': blocks}
    shown = blocks + ([results.note('아래는 직전에 성공한 「' + last['title'] + '」 실행의 결과입니다. 이번 실행은 위의 확인 필요로 끝났습니다.')] + last['blocks'] if failed and last else [])
    target.write_text(page(actions.TITLE, title, shown), encoding='utf-8', newline='\n')
    saved.write_text(json.dumps({'action': args.action, 'blocks': blocks, 'last_success': last}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(title)
    for block in blocks:
        if block['kind'] in ('note', 'error'):
            print(block.get('title', '') + ('\n' if block.get('title') else '') + block['text'])
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
