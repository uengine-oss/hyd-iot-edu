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

BOX_COLOR = '#d82929'
BOX_WIDTH = 6        # 네모 굵기(원본 1920 화면 기준)
BOX_GAP = 6          # 대상과 네모 사이 간격. 옆 줄 글자에 걸리면 0까지 줄인다
INK_DROP = 60        # 띠의 바탕(중앙값)보다 이만큼 어두운 점을 글자 · 아이콘으로 본다
MASK_COLOR = '#9a9a9a'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def check_rect(ident, kind, r, im):
    if not (len(r) == 4 and 0 <= r[0] < r[2] <= im.width and 0 <= r[1] < r[3] <= im.height):
        raise ValueError(f'{ident} {kind} 좌표가 화면 밖이거나 뒤집힘: {r}')

def _band_has_ink(gray, box):
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > gray.width or y1 > gray.height:
        return True
    hist = gray.crop(box).histogram(); total = sum(hist); seen = 0; darkest = None
    for v, n in enumerate(hist):
        if n and darkest is None: darkest = v
        seen += n
        if seen*2 > total: return darkest < v - INK_DROP   # v = 띠의 중앙값(바탕)

def draw_boxes(ident, targets, im, cursor=None):
    """대상마다 그 바깥에 빨간 네모를 그린다(가이드 P-8). 네모의 선이 지나는 띠에 글자 · 아이콘이 있으면
    간격을 BOX_GAP에서 0까지 줄이고, 0에서도 걸리면 그 변을 적어 실패한다. 네모끼리 겹쳐도 실패한다.
    cursor는 마우스 포인터 자리다. 포인터는 읽을 글자가 아니므로 그 자리는 글자 검사에서 뺀다."""
    if not targets:
        raise ValueError(f'{ident} 네모가 없다(관찰만 하는 화면에도 볼 곳 하나를 짚는다)')
    gray = im.convert('L'); w = BOX_WIDTH; outer = []; gaps = []
    if cursor:
        check_rect(ident, '포인터', cursor, im)
        ImageDraw.Draw(gray).rectangle([cursor[0], cursor[1], cursor[2]-1, cursor[3]-1], fill=255)
    for k, t in enumerate(targets, 1):
        check_rect(ident, f'네모 {k}', t, im)
        x0, y0, x1, y1 = t; side_gap = {}
        for side in ('위', '아래', '왼쪽', '오른쪽'):
            for g in range(BOX_GAP, -1, -1):
                e = g + w
                band = {'위': (x0-e, y0-e, x1+e, y0-g), '아래': (x0-e, y1+g, x1+e, y1+e),
                        '왼쪽': (x0-e, y0-e, x0-g, y1+e), '오른쪽': (x1+g, y0-e, x1+e, y1+e)}[side]
                if not _band_has_ink(gray, band):
                    side_gap[side] = g; break
            else:
                raise ValueError(f'{ident} 네모 {k} {t}의 {side} 선이 글자 · 아이콘이나 화면 끝에 걸린다 — 대상 좌표를 고친다')
        r = (x0-side_gap['왼쪽']-w, y0-side_gap['위']-w, x1+side_gap['오른쪽']+w, y1+side_gap['아래']+w)
        for j, o in enumerate(outer, 1):
            if r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3]:
                raise ValueError(f'{ident} 네모 {k}와 네모 {j}가 겹친다')
        outer.append(r); gaps.append(side_gap)
    d = ImageDraw.Draw(im)
    for r in outer:
        d.rectangle([r[0], r[1], r[2]-1, r[3]-1], outline=BOX_COLOR, width=w)
    return gaps

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
            for m in p.get('masks', []):
                check_rect(p['id'], '가림', m, im)
                # 이메일은 @부터 뒤를 그 글자 자리에서 가린다(공통 C-7).
                ImageDraw.Draw(im).rectangle([m[0], m[1], m[2]-1, m[3]-1], fill=MASK_COLOR)
            gaps=draw_boxes(p['id'], p['targets'], im, p.get('cursor'))
            if 'crop' in p:
                check_rect(p['id'], '자르기', p['crop'], im)
                im=im.crop(tuple(p['crop']))
            scale=PHOTO_WIDTH/1920   # 자른 사진도 화면 전체 사진과 같은 배율로 줄여 글자 크기를 맞춘다
            im=im.resize((round(im.width*scale), round(im.height*scale)), Image.LANCZOS)
            dest=images/(p['id']+'.jpg'); im.save(dest, 'JPEG', quality=85)
            caption=html.escape(p['caption'])
            block.append(f'<figure><a href="images/{dest.name}" target="_blank"><img src="images/{dest.name}" width="{im.width}" height="{im.height}" alt="{caption}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>')
            provenance.append({**p,'box_gaps':gaps,'raw_sha256':sha(raw),'output_sha256':sha(dest),'raw':raw.relative_to(ROOT).as_posix(),'output':dest.relative_to(ROOT).as_posix()})
        block.append(f'<p class="check"><strong>확인</strong>{markup(s["check"])}</p>')
        if n<len(data['steps']):block.append(f'<a class="next" href="#{data["steps"][n]["id"]}">다음 단계 →</a>')
        block.append('</div>'); group_content.setdefault(s['section'], []).append(''.join(block))
    for group in data['sections']:
        sections.append(f'<section id="part{group["number"]:02}"><div class="step-head"><span class="number">{group["number"]:02}</span><h2>{html.escape(group["title"])}</h2></div>'+''.join(group_content[group['number']])+'</section>')
    sample=ROOT/'workspace/강의제작/산출물/통합반/실습/01회차/랩/01일차_실습4_관계그림/가이드.html'
    css=re.search(r'<style>(.*?)</style>',sample.read_text(encoding='utf-8'),re.S).group(1)
    css+='img{width:auto;max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:16px;line-height:1.7;margin:12px 0}.input{border-left:4px solid #3974a4;background:#edf5fc;padding:14px 18px;margin:18px 0}.input label{font-size:14px;color:#245e8c}.input button{float:right;font:inherit;border:1px solid #8ba9bd;border-radius:6px;background:white;padding:2px 14px;cursor:pointer}h2,.substep{scroll-margin-top:20px}.substep{margin-top:32px;padding-top:12px;border-top:1px solid #dbe5de}.substep h3{font-size:21px;margin:12px 0}.next{display:inline-block;margin-top:16px}#copy-status{position:fixed;bottom:12px;right:12px;background:#213330;color:white;padding:8px 14px;border-radius:8px}#copy-status:empty{display:none}'
    # 진행 순서 목차는 화면에 붙어 있어, 낮은 화면(864px)에서는 뒤 장이 화면 밖으로 밀려 목차로 갈 수 없었다 — 목차 안에서 스크롤한다.
    css+='@media(min-width:851px){nav{max-height:calc(100vh - 60px);overflow-y:auto}}'
    nav=''.join(f'<a href="#part{s["number"]:02}">{s["number"]:02} {html.escape(s["title"])}</a>' for s in data['sections'])
    intro='지식 자산화에서 살펴본 개념·출처·실습 기록을 다시 찾을 수 있게 학습노트를 만듭니다. 홈과 주제 카드 → 하위 페이지 → 주제마다 칸과 카드 그림 → 표로 찾기 → 템플릿 → 내보내기와 다시 열기 순서로 갑니다.'
    doc=f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(data["title"])} · 실습 가이드</title><style>{css}</style></head><body><div class="shell"><header><div class="eyebrow">NOTION · 통합반 / 실전반 공통</div><h1>{html.escape(data["title"])}</h1><p>{intro}</p><p>Notion은 공식 홈페이지에서 Windows 앱을 받아 설치해도 되고, 앱 없이 웹브라우저에서 써도 같습니다. 만든 것은 계정에 저장되니 같은 계정으로 열면 어디서든 이어서 할 수 있습니다. 구글 계정처럼 편한 계정으로 로그인한 화면에서 시작하세요. 입력 글은 사진과 같은 글이 들어가도록 직접 치지 말고 <strong>복사</strong>를 눌러 붙여넣으세요. 사진을 누르면 원래 크기로 보입니다.</p><div class="actions"><a class="button" href="https://www.notion.so" target="_blank" rel="noopener">Notion 열기</a><a class="button secondary" href="#n01">첫 단계</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>{nav}</nav><main>{"".join(sections)}<a class="top" href="#">맨 위로</a></main></div><footer>학습노트 만들기 · 통합반 / 실전반 공통</footer></div><div id="copy-status" role="status" aria-live="polite"></div><script>document.querySelectorAll("[data-copy]").forEach(b=>b.addEventListener("click",async()=>{{let e=document.getElementById(b.dataset.copy);try{{await navigator.clipboard.writeText(e.textContent);document.getElementById("copy-status").textContent="복사했습니다. Notion의 해당 입력칸에 붙여넣으세요."}}catch{{let r=document.createRange();r.selectNodeContents(e);let s=window.getSelection();s.removeAllRanges();s.addRange(r);document.getElementById("copy-status").textContent="선택된 글을 Ctrl+C로 복사해 Notion에 붙여넣으세요."}}}}));</script></body></html>'
    (out/'가이드.html').write_text(doc,encoding='utf-8')
    report={'source_sha256':sha(SOURCE),'builder_sha256':sha(Path(__file__)),'video':data['video'],'video_sha256':data['video_sha256'],'srt_sha256':data['srt_sha256'],'html_sha256':sha(out/'가이드.html'),'sections':len(sections),'steps':len(data['steps']),'photos':provenance,'status':'검수 출력, 정본 미적용'}
    (out.parent/'학생가이드_사진근거.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sections':len(sections),'steps':len(data['steps']),'photos':len(provenance),'html':str(out/'가이드.html')},ensure_ascii=True))

if __name__=='__main__':main()
