"""Build the Notion photo guide in a review directory only; never apply to production."""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[5]
SOURCE = Path(__file__).with_name('학생가이드.json')
PHOTO_WIDTH = 1440   # 화면 전체 사진의 가로 — 글자가 읽히고 158장이 약 12MB(JPEG 85)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def markup(s):
    s = html.escape(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', s).replace('\n', '<br>')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--draft', type=Path, required=True)
    ap.add_argument('--frames', type=Path, required=True)
    args = ap.parse_args()
    args.frames = args.frames.resolve()
    out = args.draft.resolve()
    if not out.is_relative_to((ROOT/'작업').resolve()):
        raise SystemExit('검수 출력은 작업 폴더 안에만 생성합니다.')
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    images = out/'images'; images.mkdir(parents=True, exist_ok=True)
    sections=[]; provenance=[]; group_content={}
    for n, s in enumerate(data['steps'], 1):
        block = [f'<div class="substep" id="{s["id"]}"><h3>{html.escape(s["title"])}</h3>',f'<p>{markup(s["body"])}</p>']
        for j, value in enumerate(s['inputs'], 1):
            ident=f'{s["id"]}-input{j}'
            block.append(f'<div class="input"><label for="{ident}">Notion에 입력할 글 {j}</label><button type="button" data-copy="{ident}">복사</button><pre id="{ident}" tabindex="0">{html.escape(value)}</pre></div>')
        for p in s['photos']:
            raw=args.frames/(p['id']+'.png')
            if not raw.is_file(): raise FileNotFoundError(raw)
            im=Image.open(raw).convert('RGB')
            target=p['target']
            if not (0 <= target[0] < target[2] <= im.width and 0 <= target[1] < target[3] <= im.height):
                raise ValueError(p['id']+' 잘못된 좌표')
            # 화면 전체를 보이고 누를 곳만 네모로 짚는다(2026-11-11 사용자 「전체화면이라던지」 — 단추만 잘라 내면 위치를 찾을 수 없다, 가이드 P-8).
            # 네모는 대상 바깥에 그려 글을 가리지 않는다.
            rect=[target[0]-8,target[1]-8,target[2]+8,target[3]+8]
            ImageDraw.Draw(im).rectangle(rect, outline='#d82929', width=8)
            im=im.resize((PHOTO_WIDTH, round(im.height*PHOTO_WIDTH/im.width)), Image.LANCZOS)
            dest=images/(p['id']+'.jpg'); im.save(dest, 'JPEG', quality=85)
            caption=html.escape(p['caption'])
            block.append(f'<figure><a href="images/{dest.name}" target="_blank"><img src="images/{dest.name}" width="{im.width}" height="{im.height}" alt="{caption}" loading="lazy"></a><figcaption>{caption} · 사진을 누르면 원래 크기로 볼 수 있습니다.</figcaption></figure>')
            provenance.append({**p,'raw_sha256':sha(raw),'output_sha256':sha(dest),'raw':raw.relative_to(ROOT).as_posix(),'output':dest.relative_to(ROOT).as_posix()})
        block.append(f'<p class="check"><strong>확인</strong>{markup(s["check"])}</p>')
        if n<len(data['steps']):block.append(f'<a class="next" href="#{data["steps"][n]["id"]}">다음 단계 →</a>')
        block.append('</div>'); group_content.setdefault(s['section'], []).append(''.join(block))
    for group in data['sections']:
        sections.append(f'<section id="part{group["number"]:02}"><div class="step-head"><span class="number">{group["number"]:02}</span><h2>{html.escape(group["title"])}</h2></div>'+''.join(group_content[group['number']])+'</section>')
    sample=ROOT/'workspace/강의제작/산출물/통합반/실습/01회차/랩/01일차_실습4_관계그림/가이드.html'
    css=re.search(r'<style>(.*?)</style>',sample.read_text(encoding='utf-8'),re.S).group(1)
    css+='img{width:auto;max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:16px;line-height:1.7;margin:12px 0}.input{border-left:4px solid #3974a4;background:#edf5fc;padding:14px 18px;margin:18px 0}.input label{font-size:14px;color:#245e8c}.input button{float:right;font:inherit;border:1px solid #8ba9bd;border-radius:6px;background:white;padding:2px 14px;cursor:pointer}h2,.substep{scroll-margin-top:20px}.substep{margin-top:32px;padding-top:12px;border-top:1px solid #dbe5de}.substep h3{font-size:21px;margin:12px 0}.next{display:inline-block;margin-top:16px}#copy-status{position:fixed;bottom:12px;right:12px;background:#213330;color:white;padding:8px 14px;border-radius:8px}#copy-status:empty{display:none}'
    nav=''.join(f'<a href="#part{s["number"]:02}">{s["number"]:02} {html.escape(s["title"])}</a>' for s in data['sections'])
    intro='지식 자산화에서 살펴본 개념·출처·실습 기록을 다시 찾을 수 있도록 학습노트 홈과 주제 카드를 만듭니다. 빈 페이지에서 시작해 글과 하위 페이지를 연결하고, 표로 찾고, 자신의 주제에 템플릿을 적용한 뒤 저장한 내용을 다시 엽니다.'
    doc=f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(data["title"])} · 실습 가이드</title><style>{css}</style></head><body><div class="shell"><header><div class="eyebrow">NOTION · 통합반 / 실전반 공통</div><h1>{html.escape(data["title"])}</h1><p>{intro}</p><p>Notion에 로그인한 작업 화면에서 시작하세요. 아래 입력 글은 직접 치지 말고 복사해 해당 칸에 붙여넣으세요. 사진 속 날짜는 작성한 날에 따라 달라집니다.</p><div class="actions"><a class="button" href="https://www.notion.so" target="_blank" rel="noopener">Notion 열기</a><a class="button secondary" href="#n01">첫 단계</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>{nav}</nav><main>{"".join(sections)}<a class="top" href="#">맨 위로</a></main></div><footer>학습노트 만들기 · 통합반 / 실전반 공통</footer></div><div id="copy-status" role="status" aria-live="polite"></div><script>document.querySelectorAll("[data-copy]").forEach(b=>b.addEventListener("click",async()=>{{let e=document.getElementById(b.dataset.copy);try{{await navigator.clipboard.writeText(e.textContent);document.getElementById("copy-status").textContent="복사했습니다. Notion의 해당 입력칸에 붙여넣으세요."}}catch{{let r=document.createRange();r.selectNodeContents(e);let s=window.getSelection();s.removeAllRanges();s.addRange(r);document.getElementById("copy-status").textContent="선택된 글을 Ctrl+C로 복사해 Notion에 붙여넣으세요."}}}}));</script></body></html>'
    (out/'가이드.html').write_text(doc,encoding='utf-8')
    report={'source_sha256':sha(SOURCE),'builder_sha256':sha(Path(__file__)),'video':data['video'],'video_sha256':data['video_sha256'],'srt_sha256':data['srt_sha256'],'html_sha256':sha(out/'가이드.html'),'sections':len(sections),'steps':len(data['steps']),'photos':provenance,'status':'검수 출력, 정본 미적용'}
    (out.parent/'학생가이드_사진근거.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sections':len(sections),'steps':len(data['steps']),'photos':len(provenance),'html':str(out/'가이드.html')},ensure_ascii=True))

if __name__=='__main__':main()
