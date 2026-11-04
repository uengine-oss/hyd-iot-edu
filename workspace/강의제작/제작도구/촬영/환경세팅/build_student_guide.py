"""1회차 공통 환경 가이드. 미확인 사진이 있으면 초안만 만들고 배포를 막는다.

python build_student_guide.py --draft 작업/<작업>/가이드초안
python build_student_guide.py --apply
사진 근거: 같은 폴더 학생가이드_사진근거.json. 원고: 학생가이드.md.
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
LAB = '01일차_실습2_실행환경'
OUTPUTS = ROOT / 'workspace/강의제작/산출물'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render():
    source = (HERE / '학생가이드.md').read_text(encoding='utf-8')
    manifest_path = HERE / '학생가이드_사진근거.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'photos': {}}
    photos = manifest['photos']
    unresolved = []
    assets = {}

    def photo(match):
        key = match[1]
        item = photos.get(key)
        if not item or not item.get('verified'):
            unresolved.append(key)
            planned = item or {}
            scene = html.escape(planned.get('required_scene', key))
            condition = html.escape(planned.get('check', '실제 조작 대상과 완료 상태 확인'))
            expected_path = f'images/{html.escape(key)}.png'
            return f'<aside class="pending">미촬영: {scene}<br>확인: {condition}<br>사진 위치: {expected_path}</aside>'
        path = ROOT / item['path']
        if not path.is_file():
            raise ValueError(f'사진 없음: {key}')
        if sha(path) != item['sha256']:
            raise ValueError(f'사진 판본 불일치: {key}')
        # 원본 영상 대조는 prepare_student_photos.py 몫이다 — 녹화 원본은 작업 폴더에만 있어 사진(제작도구)만으로 다시 만든다
        seconds = item.get('seconds')
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0 or not item.get('rectangles') or not item.get('caption'):
            raise ValueError(f'시각·표시 좌표·설명 누락: {key}')
        name = key + path.suffix
        assets[name] = path
        caption = html.escape(item['caption'])
        with Image.open(path) as image:
            width, height = image.size
        return f'<figure><a href="images/{name}"><img src="images/{name}" alt="{caption}" width="{width}" height="{height}" loading="lazy" style="width:auto;max-width:100%;height:auto"></a><figcaption>{caption}</figcaption></figure>'

    source = re.sub(r'<!-- PHOTO:([a-z-]+) -->', photo, source)
    reference = OUTPUTS / '통합반/실습/01회차/랩/01일차_실습4_관계그림/가이드.html'
    css = re.search(r'<style>(.*?)</style>', reference.read_text(encoding='utf-8'), re.S)[1]
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    blocks = re.split(r'^## (.+)$', source, flags=re.M)
    intro = re.sub(r'^# .+\n', '', blocks[0], count=1)
    sections = []
    links = []
    for n in range(1, len(blocks), 2):
        step = (n+1)//2
        title = html.escape(blocks[n])
        body = md.render(blocks[n+1])
        sections.append(f'<section id="step{step}"><div class="step-head"><span class="number">{step:02}</span><h2>{title}</h2></div>{body}</section>')
        links.append(f'<a href="#step{step}">{step:02} {title}</a>')
    scripts = """
document.querySelectorAll('pre').forEach((pre)=>{
  const code=pre.querySelector('code'); if(!code)return;
  const shell=code.className.includes('powershell')?'PowerShell':code.className.includes('bash')?'Git Bash':'Codex';
  pre.classList.add(shell==='Codex'?'ai-input':'terminal-input');
  const label=document.createElement('div'); label.className='copy-label';
  label.textContent=shell==='Codex'?'AI 채팅 입력':'터미널 명령 · '+shell;
  const button=document.createElement('button');button.type='button';button.textContent='복사';
  const status=document.createElement('span');status.setAttribute('role','status');
  button.onclick=async()=>{const value=code.textContent.trimEnd();if(!value.trim()){status.textContent='복사할 내용이 없습니다.';return;}
    try{await navigator.clipboard.writeText(value);status.textContent=shell+' 입력칸에 붙여넣으세요.';}
    catch{status.textContent='본문을 선택해 직접 복사한 뒤 '+shell+'에 붙여넣으세요.';}};
  label.append(button,status);pre.before(label);
});
"""
    extra = '.pending{border:2px dashed #a36b16;padding:18px;background:#fff8e9}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;border-radius:8px}.terminal-input{background:#edf3ee;border-left:4px solid #216953}.ai-input{background:#eef0ff;border-left:4px solid #5a4eb2}.copy-label{display:flex;flex-wrap:wrap;gap:12px;align-items:center;font-size:14px}.copy-label button{padding:6px 14px}table{display:block;overflow-x:auto}header table{background:white}nav{max-height:90vh;overflow:auto}'
    page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 환경을 시작하고 HYD 포털 둘러보기</title><style>{css}{extra}</style></head><body><div class="shell"><header><div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>실습 환경을 시작하고<br>HYD 포털 둘러보기</h1>{md.render(intro)}</header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>{''.join(links)}</nav><main>{''.join(sections)}<a class="top" href="#">맨 위로</a></main></div></div><script>{scripts}</script></body></html>'''
    return page, assets, unresolved


def write_guide(destination, page, assets):
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
        (destination/'검사.json').write_text(json.dumps({'missing_photos': unresolved, 'source_sha256':sha(HERE/'학생가이드.md'),'status':'미확인' if unresolved else '사진 참조 확인됨'}, ensure_ascii=False,indent=2), encoding='utf-8')
        print(f'초안 생성: {len(assets)}개 사진 · 미확인 {len(unresolved)}개. 배포본 변경 없음.')
        return
    if unresolved:
        parser.error('미확인 사진이 있어 배포하지 않습니다: '+', '.join(unresolved))
    sys.path.insert(0, str(HERE.parents[1]/'실습시작'))
    from lab_package import pack
    for course in ['통합반', '실전반']:
        lab = OUTPUTS/course/'실습/01회차/랩'/LAB
        shutil.rmtree(lab/'images', ignore_errors=True)
        write_guide(lab, page, assets)
        pack(lab)
    print('두 과정 환경 가이드 · ZIP 갱신.')


if __name__ == '__main__':
    main()
