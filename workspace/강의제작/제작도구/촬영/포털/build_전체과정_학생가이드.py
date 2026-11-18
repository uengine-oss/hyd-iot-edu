"""1회차 실습3(06 전체과정관찰) 도구 실습의 두 과정 공통 학생 가이드와 한 파일 가이드(<랩>.html)를 만든다.
언제: 원고(학생가이드_원고.md)나 사진(사진_만들기.py가 확정 영상에서 뽑은 것)이 바뀌었을 때.

python build_전체과정_학생가이드.py --draft 작업/<작업>/가이드초안   — 초안만(미확인 사진은 「미촬영」 칸)
python build_전체과정_학생가이드.py --apply                          — 사진 확인이 다 된 뒤 두 과정 랩 폴더 · 한 파일 가이드를 바꿔 끼운다
사진 근거: 같은 폴더 전체과정_학생가이드_사진근거.json. 생김새는 1회차 다른 도구 실습 가이드(실습4 관계그림의 스타일)와 같게 둔다.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys

from markdown_it import MarkdownIt
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LAB = '01일차_실습3_전체과정관찰'
OUTPUTS = ROOT/'workspace/강의제작/산출물'
SOURCE = HERE/'학생가이드_원고.md'
MANIFEST = HERE/'전체과정_학생가이드_사진근거.json'
STYLE = OUTPUTS/'통합반/실습/01회차/랩/01일차_실습4_관계그림/가이드.html'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render():
    text = SOURCE.read_text(encoding='utf-8')
    photos = json.loads(MANIFEST.read_text(encoding='utf-8'))['photos']
    ids = re.findall(r'<!-- PHOTO:([^ ]+) -->', text)
    if len(ids) != len(set(ids)) or set(ids) != set(photos):
        raise ValueError(f'원고와 사진 근거가 다릅니다 — 원고에만 {sorted(set(ids)-set(photos))}, 근거에만 {sorted(set(photos)-set(ids))}')
    unresolved, assets = [], {}

    def photo(match):
        key = match[1]
        item = photos[key]
        if not item.get('verified'):
            unresolved.append(key)
            return f'<aside class="pending">미촬영: {html.escape(item["required_scene"])}<br>확인: {html.escape(item["check"])}</aside>'
        path = ROOT/item['path']
        if not path.is_file() or sha(path) != item['sha256']:
            raise ValueError(f'사진 판본 불일치: {key}')
        # 원본 영상 대조는 사진_만들기.py 몫이다 — 확정 영상은 Release에 있어 사진(제작도구)만으로 다시 만든다
        if not item.get('source_sha256') or item.get('seconds') is None or not item.get('rectangles') or not item.get('caption'):
            raise ValueError(f'출처 · 시각 · 표시 좌표 · 설명 누락: {key}')
        name = path.name
        assets[name] = path
        caption = html.escape(item['caption'])
        with Image.open(path) as image:
            width, height = image.size
        return (f'<figure><a href="images/{html.escape(name)}"><img src="images/{html.escape(name)}" alt="{caption}" width="{width}" height="{height}" '
                f'loading="lazy" style="width:auto;max-width:100%;height:auto"></a><figcaption>{caption}</figcaption></figure>')

    text = re.sub(r'<!-- PHOTO:([^ ]+) -->', photo, text)
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    blocks = re.split(r'^## (.+)$', text, flags=re.M)
    title = blocks[0].splitlines()[0][2:].strip()
    intro = re.sub(r'^# .+\n', '', blocks[0], count=1)
    sections, links = [], []
    for n in range(1, len(blocks), 2):
        step = (n+1)//2
        heading = html.escape(blocks[n].strip())
        sections.append(f'<section id="step{step}"><div class="step-head"><span class="number">{step:02}</span><h2>{heading}</h2></div>{md.render(blocks[n+1])}</section>')
        links.append(f'<a href="#step{step}">{step:02} {heading}</a>')
    css = re.search(r'<style>(.*?)</style>', STYLE.read_text(encoding='utf-8'), re.S)[1]
    extra = '.pending{border:2px dashed #a36b16;padding:18px;background:#fff8e9}table{display:block;overflow-x:auto}header table{background:white}nav{max-height:90vh;overflow:auto}'
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{css}{extra}</style></head><body><div class="shell"><header>'
            f'<div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>{html.escape(title)}</h1>{md.render(intro)}</header>'
            f'<div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>{"".join(links)}</nav><main>{"".join(sections)}'
            f'<a class="top" href="#">맨 위로</a></main></div></div></body></html>')
    return page, assets, unresolved


def write_guide(destination: Path, page: str, assets: dict):
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'가이드.html').write_text(page, encoding='utf-8')
    for name, path in assets.items():
        (destination/'images').mkdir(exist_ok=True)
        shutil.copyfile(path, destination/'images'/name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--draft', type=Path)
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    page, assets, unresolved = render()
    if args.draft:
        destination = args.draft.resolve()
        if not destination.is_relative_to((ROOT/'작업').resolve()):
            parser.error('초안은 이 저장소 작업 폴더에만 저장합니다.')
        write_guide(destination, page, assets)
        print(f'초안 생성: 사진 {len(assets)}개 · 미확인 {len(unresolved)}개. 랩 폴더는 바꾸지 않음.')
        return
    if unresolved:
        parser.error('미확인 사진이 있어 바꿔 끼우지 않습니다: '+', '.join(unresolved))
    sys.path.insert(0, str(HERE.parents[1]/'실습시작'))
    from lab_package import pack_page
    for course in ('통합반', '실전반'):
        lab = OUTPUTS/course/'실습/01회차/랩'/LAB
        shutil.rmtree(lab, ignore_errors=True)   # 랩 폴더에는 가이드와 가이드가 여는 사진만 둔다(가이드 P-13)
        write_guide(lab, page, assets)
        pack_page(lab)
    print('두 과정 가이드 · 한 파일 가이드(<랩>.html) 갱신.')


if __name__ == '__main__':
    main()
