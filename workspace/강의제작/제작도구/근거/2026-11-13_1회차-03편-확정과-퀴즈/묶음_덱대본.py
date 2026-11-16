"""사용자에게 확정을 받을 HTML 한 파일을 만든다: 장마다 렌더 그림 + 대본(핵심 · 풀이, `>` 줄은 「읽지 않음」).
옛 판을 주면 바뀐 구획에 「화면 바뀜 · 대본 바뀜 · 옮김 · 새 구획」 표시와 접어 둔 「고치기 전 화면 · 대본」을 넣는다.
화면 바뀜은 `### 화면 내용` 글이 다르거나 렌더 그림이 달라진 장이다(그림 파일만 고친 장도 잡는다).
옛 판에만 있던 구획은 바로 가기 줄 끝에 「없어진 구획」으로 적는다.

명령(저장소 루트에서):
  python3 <이 파일> --출력 작업/<폴더>/X.html --머리 <머리.html> --제목 "<두~네 낱말>" \
     --새렌더 작업/<폴더>/<판>/렌더 --대본 <새 대본.md> [<새 대본.md> …] \
     [--옛덱 <옛 덱 원고.md> --옛렌더 <옛 렌더 폴더> --옛대본 <옛 대본.md> [ …] --장대응 "8:9,9:8"] [--바뀐것만]
- 렌더 폴더에는 s-NN.jpg가 있어야 한다(덱 PDF를 pymupdf로 dpi 100으로 뽑은 것).
- 옛 덱 · 옛 대본은 `git show <커밋>:<경로> > <임시 파일>`로 꺼낸다. --옛대본은 --대본과 같은 차례로 준다.
- --장대응은 「새 장:옛 장」 쌍(장 차례를 옮겼을 때만).
- 머리 글의 {{바뀐장}} · {{바뀐수}}는 바뀐 구획 바로 가기와 그 수로 바뀐다. 머리 글은 손으로 쓴다. 견본:
    <h1>1회차 이론 — (무엇을 고친 판)</h1>
    <div class="n">
    <p>(누가 무슨 기준으로 읽고 몇 곳을 고쳤는지 한두 문장. 바뀐 {{바뀐수}}구획은 「고치기 전 화면 · 대본 보기」로 견준다)</p>
    <ul><li><b>(편 장)</b>: (무엇을 어떻게 바꿨는지 한 줄)</li> …</ul>
    <p><b>정해 주실 것</b>: (물음마다 무엇이고 · 하면 · 안 하면 생기는 일)</p>
    <p><b>남은 확인</b>: 대체 글꼴 렌더라 줄바꿈 · 넘침 판정은 이 PC 몫입니다.</p>
    <p>바뀐 구획 바로 가기: {{바뀐장}}</p>
    </div>
"""
import argparse, base64, html, io, pathlib, re
from PIL import Image, ImageChops

ap = argparse.ArgumentParser()
ap.add_argument('--출력', required=True)
ap.add_argument('--머리', required=True)
ap.add_argument('--제목', required=True)
ap.add_argument('--새렌더', required=True)
ap.add_argument('--대본', nargs='+', required=True)
ap.add_argument('--새덱', default='workspace/강의제작/제작도구/온라인/decks/integrated/day01/통합반_01일차.md')
ap.add_argument('--옛덱')
ap.add_argument('--옛렌더')
ap.add_argument('--옛대본', nargs='*', default=[])
ap.add_argument('--장대응', default='')
ap.add_argument('--바뀐것만', action='store_true')
a = ap.parse_args()
old = bool(a.옛덱)
if old and (not a.옛렌더 or len(a.옛대본) != len(a.대본)):
    raise SystemExit('옛 판을 견주려면 --옛렌더와, --대본과 같은 수의 --옛대본이 있어야 한다')
N2O = {int(x.split(':')[0]): int(x.split(':')[1]) for x in a.장대응.split(',') if x}


def deck_screens(p):
    d = {}
    for b in re.split(r'(?m)^(?=## SLIDE \d\d — )', pathlib.Path(p).read_text(encoding='utf-8')):
        m = re.match(r'## SLIDE (\d\d) — ', b)
        if m:
            s = b.split('### 화면 내용', 1)[1].split('### 화면 구성', 1)[0]
            d[int(m.group(1))] = '\n'.join(l for l in s.splitlines() if not l.startswith('- 노트:')).strip()
    return d


def jpg(p):
    p = pathlib.Path(p)
    if not p.exists():
        raise SystemExit(f'렌더 없음: {p}')
    im = Image.open(p).convert('RGB')
    im = im.resize((1100, int(im.height * 1100 / im.width)))
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=72)
    return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}" alt="">'


def render_differs(a_path, b_path):
    """두 렌더가 눈에 띄게 다른가: 폭 400으로 줄인 흑백에서 40 넘게 달라진 화소가 0.1%를 넘는다."""
    a = Image.open(a_path).convert('L'); b = Image.open(b_path).convert('L')
    size = (400, int(a.height * 400 / a.width))
    d = ImageChops.difference(a.resize(size), b.resize(size))
    return sum(d.histogram()[41:]) > size[0] * size[1] * 0.001


def sections(p):
    t = pathlib.Path(p).read_text(encoding='utf-8').split('# 촬영 본문 끝')[0]
    parts = re.split(r'(?m)^## \[SLIDE (\d+)(?:~(\d+))?\] (.*)$', t)
    return [(int(parts[i]), int(parts[i + 1]) if parts[i + 1] else None, parts[i + 2], parts[i + 3].split('\n---')[0].strip())
            for i in range(1, len(parts), 4)]


def paras(text):
    h = []
    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para or para.startswith('# '):
            continue
        if para in ('> [핵심]', '> [풀이]'):
            h.append(f'<div class="t">{para[3:-1]}</div>')
        elif para.startswith('>'):
            h.append(f'<div class="w">{html.escape(para.lstrip("> "))} <i>(읽지 않음)</i></div>')
        else:
            h.append(f'<p>{html.escape(para)}</p>')
    return h


DN = deck_screens(a.새덱)
DO = deck_screens(a.옛덱) if old else {}
body, changed = [], []
gone = []
for k, new in enumerate(a.대본):
    olds = {(x, y): (t, s) for x, y, t, s in sections(a.옛대본[k])} if old else {}
    seen = set()
    for x, y, ttl, txt in sections(new):
        nums = list(range(x, y + 1)) if y else [x]
        label = f'{x}~{y}장' if y else f'{x}장'
        badges, scr, txt_changed, otxt = '', [], False, ''
        if old:
            key = (N2O.get(x, x), N2O.get(y, y) if y else None)
            if key not in olds:
                badges = '<span class="b">새 구획</span>'
                changed.append((x, label))
                body.append(f'<h2 id="s{x}">{label} · {html.escape(ttl)} {badges}</h2>')
                body += [jpg(pathlib.Path(a.새렌더) / f's-{n:02d}.jpg') for n in nums]
                body += paras(txt)
                continue
            seen.add(key)
            otxt = olds[key][1]
            scr = [n for n in nums if DN[n] != DO.get(N2O.get(n, n))
                   or render_differs(pathlib.Path(a.새렌더) / f's-{n:02d}.jpg', pathlib.Path(a.옛렌더) / f's-{N2O.get(n, n):02d}.jpg')]
            txt_changed = re.sub(r'\s+', ' ', otxt) != re.sub(r'\s+', ' ', txt)
            if scr:
                badges += '<span class="b">화면 바뀜</span>'
            if txt_changed:
                badges += '<span class="b">대본 바뀜</span>'
            if any(N2O.get(n, n) != n for n in nums):
                badges += f'<span class="b m">옛 {"·".join(str(N2O.get(n, n)) for n in nums)}장에서 옮김</span>'
            if badges:
                changed.append((x, label))
            elif a.바뀐것만:
                continue
            else:
                badges = '<span class="b s">그대로</span>'
        body.append(f'<h2 id="s{x}">{label} · {html.escape(ttl)} {badges}</h2>')
        body += [jpg(pathlib.Path(a.새렌더) / f's-{n:02d}.jpg') for n in nums]
        body += paras(txt)
        if scr or txt_changed:
            body.append('<details><summary>고치기 전 화면 · 대본 보기</summary>')
            body += [jpg(pathlib.Path(a.옛렌더) / f's-{N2O.get(n, n):02d}.jpg') for n in scr]
            body += paras(otxt) if txt_changed else ['<p class="w">대본은 그대로다.</p>']
            body.append('</details>')
    gone += [f'옛 {x}~{y}장' if y else f'옛 {x}장' for (x, y) in olds if (x, y) not in seen]

nav = ' · '.join(f'<a href="#s{x}">{lab}</a>' for x, lab in changed)
if gone:
    nav += ' / 없어진 구획: ' + ' · '.join(gone)
head = pathlib.Path(a.머리).read_text(encoding='utf-8').replace('{{바뀐장}}', nav).replace('{{바뀐수}}', str(len(changed)))
css = ("body{font-family:sans-serif;max-width:1000px;margin:0 auto;padding:16px;line-height:1.75;color:#1b2430;background:#fff}"
       "h1{font-size:22px}h2{font-size:18px;margin:36px 0 8px;border-top:2px solid #1b2f55;padding-top:14px}"
       "img{width:100%;border:1px solid #cfd6df;border-radius:6px;margin:4px 0}p{margin:10px 0}.t{color:#5b6677;font-size:13px;margin-top:14px}"
       ".w{background:#eef4fb;padding:6px 10px;border-radius:4px;font-size:13px;color:#39506e}"
       ".n{background:#fff6dc;padding:10px 12px;border-radius:6px;font-size:14px}.n li{margin:4px 0}"
       ".b{display:inline-block;font-size:12px;background:#ffe2cc;color:#8a3b00;border-radius:10px;padding:1px 8px;margin-left:6px;vertical-align:middle}"
       ".b.m{background:#dfe9ff;color:#1d3f8a}.b.s{background:#e6efe6;color:#2f5a2f}"
       "details{background:#f6f7f9;border-radius:6px;padding:6px 12px;margin:10px 0}summary{cursor:pointer;color:#5b6677;font-size:14px}a{color:#1d4fb8}")
out = pathlib.Path(a.출력)
out.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
               f'<title>{html.escape(a.제목)}</title><style>{css}</style>\n{head}\n' + '\n'.join(body) + '\n', encoding='utf-8')
print(out, out.stat().st_size, '바뀐 구획', len(changed), '없어진 구획', len(gone))
