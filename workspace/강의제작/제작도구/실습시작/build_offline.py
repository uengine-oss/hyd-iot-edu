"""오프라인1 회차 안내 검수본. 정본 및 다른 회차 제공물을 변경하지 않는다.

python build_offline.py --draft 작업/<작업>/오프라인1_제공물검수
04·06 가이드와 사진의 최종 판본 확인 전에는 배포본을 만들지 않는다.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re
from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'workspace/강의제작/산출물'
COURSES = ('통합반', '실전반')
OLD_IDS = {'integrated-01-offline', 'practical-01-offline'}
LABS = ('01일차_실습1_학습노트', '01일차_실습2_실행환경', '01일차_실습3_전체과정관찰', '01일차_실습4_관계그림')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def render():
    source = (HERE/'offline01.md').read_text(encoding='utf-8')
    reference = OUT/'통합반/실습/01회차/랩/01일차_실습4_관계그림/가이드.html'
    css = re.search(r'<style>(.*?)</style>', reference.read_text(encoding='utf-8-sig'), re.S)[1]
    md = MarkdownIt('commonmark', {'html': False}).enable('table')
    chunks = re.split(r'^## (.+)$', source, flags=re.M)
    title = chunks[0].splitlines()[0][2:]
    intro = chunks[0].split('\n', 1)[1]
    links, sections = [], []
    for i in range(1, len(chunks), 2):
        n = (i+1)//2
        heading = html.escape(chunks[i])
        links.append(f'<a href="#step{n}">{n:02} {heading}</a>')
        sections.append(f'<section id="step{n}"><div class="step-head"><span class="number">{n:02}</span><h2>{heading}</h2></div>{md.render(chunks[i+1])}</section>')
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body><div class="shell"><header><div class="eyebrow">오프라인 1회 · 두 과정 공통</div><h1>{html.escape(title)}</h1>{md.render(intro)}</header><div class="layout"><nav aria-label="실습 순서">{"".join(links)}</nav><main>{"".join(sections)}</main></div></div></body></html>'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', required=True, type=Path)
    args = parser.parse_args()
    destination = args.draft.resolve()
    if not destination.is_relative_to((ROOT/'작업').resolve()):
        parser.error('검수 출력은 저장소 작업 폴더에만 둡니다.')
    page = render()
    for course in COURSES:
        write(destination/f'workspace/강의제작/산출물/{course}/실습/01회차/오프라인_가이드.html', page)
    # 코딩랩 목록에는 도구 실습을 넣지 않는다. 다른 회차 항목은 그대로 보존한다.
    removed = {}
    for filename in ('catalog.json', 'package-index.json'):
        data = json.loads((HERE/filename).read_text(encoding='utf-8-sig'))
        removed[filename] = [x for x in data['labs'] if x['id'] in OLD_IDS]
        data['labs'] = [x for x in data['labs'] if x['id'] not in OLD_IDS]
        write(destination/f'workspace/강의제작/제작도구/실습시작/{filename}', json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    evidence = {'status': '검수용·배포 미적용', 'source_sha256': sha(HERE/'offline01.md'), 'removed_from_preview_only': removed,
        'pending': ['04 환경 가이드 최종 사진·HTML 미확인', '06 사건 가이드 원문 검토·적재와 승인 전 근거 확인 단계·사진 미확인', '현장 Notion 접속 불가 시 파일·Git·시간 MCP 대체 절차의 학교 PC 실제 수행 미확인', '실제 학생 받기 및 학교 PC 확인', '원격 게시 판본 확인'],
        'scope': '회차 안내만 생성. 각 실습은 기존 독립 가이드로 연결하며 다음 회차 원본과 구판 원자료는 보존한다.'}
    write(destination/'검수상태.json', json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
    print('오프라인1 회차 안내 2개 및 목록 검수본 생성. 정본 배포 미적용.')

if __name__ == '__main__':
    main()
