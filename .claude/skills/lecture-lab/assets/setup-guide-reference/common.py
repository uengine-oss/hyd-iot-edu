# -*- coding: utf-8 -*-
import html as _h

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm;
  @top-left { content: "%(doc_short)s"; font-size: 8pt; color: #666; }
  @top-right { content: "%(doc_right)s"; font-size: 8pt; color: #999; }
  @bottom-center { content: counter(page); font-size: 8pt; color: #666; }
}
* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK KR", "Noto Sans KR", sans-serif; font-size: 10pt; line-height: 1.55; color: #222; }
h1 { font-size: 20pt; margin: 0 0 4pt 0; color: #1a3c6e; }
h2 { break-before: page; font-size: 14pt; margin: 18pt 0 6pt 0; color: #1a3c6e; border-left: 5px solid #1a3c6e; padding-left: 8pt; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt 0; color: #333; page-break-after: avoid; break-after: avoid; }
p { margin: 3pt 0 6pt 0; }
.sub { color: #555; font-size: 10pt; margin-bottom: 10pt; }
@page cover { size: A4; margin: 0; @top-left { content: none } @top-right { content: none } @bottom-center { content: none } }
.cover { page: cover; page-break-after: always; width: 210mm; height: 297mm; background: #0f2440; color: #fff; position: relative; overflow: hidden; }
.cover .band { position: absolute; left: 0; top: 0; width: 210mm; height: 6mm; background: linear-gradient(90deg,#4f8ef7,#7ad0ff); }
.cover .deco { position: absolute; right: -40mm; bottom: -40mm; width: 150mm; height: 150mm; border-radius: 50%%; background: #163461; }
.cover .deco2 { position: absolute; right: 10mm; bottom: 10mm; width: 70mm; height: 70mm; border-radius: 50%%; background: #1d4380; }
.cover .series { position: absolute; left: 22mm; top: 40mm; font-size: 11pt; letter-spacing: 2pt; color: #9cc4ff; }
.cover .num { position: absolute; left: 22mm; top: 52mm; font-size: 64pt; font-weight: 700; color: #4f8ef7; line-height: 1; background: none; border-radius: 0; padding: 0; margin: 0; min-width: 0; text-align: left; }
.cover h1 { position: absolute; left: 22mm; top: 86mm; width: 160mm; font-size: 30pt; line-height: 1.25; color: #fff; margin: 0; }
.cover .sub { position: absolute; left: 22mm; top: 128mm; width: 150mm; font-size: 11.5pt; color: #c9d7ec; line-height: 1.6; margin: 0; }
.cover .lead { position: absolute; left: 22mm; top: 158mm; width: 140mm; font-size: 10.5pt; color: #e6eefb; line-height: 1.75; border-left: 3px solid #4f8ef7; padding-left: 10pt; margin: 0; }
.cover .foot { position: absolute; left: 22mm; bottom: 18mm; font-size: 9pt; color: #8fa6c9; }
.cover .lead { font-size: 10pt; margin-top: 8pt; }
table { border-collapse: collapse; width: 100%%; margin: 6pt 0 8pt 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #cfd6df; padding: 4pt 6pt; vertical-align: top; }
th { background: #e9eef5; text-align: left; font-weight: 700; }
.step { margin: 6pt 0 12pt 0; border: 1px solid #d9dee5; border-radius: 4pt; padding: 8pt 10pt; }
.keep { break-inside: avoid; }
.step-head { break-after: avoid; }
h2 + p { break-after: avoid; }
.ok, .warn, .tip, .diff { break-inside: avoid; }
.step-head { display: flex; align-items: center; margin-bottom: 4pt; }
.num { display: inline-block; background: #1a3c6e; color: #fff; font-weight: 700; border-radius: 12pt; min-width: 22pt; text-align: center; padding: 1pt 6pt; margin-right: 8pt; font-size: 10pt; }
.step-title { font-weight: 700; font-size: 11pt; }
.where { display: flex; align-items: flex-start; margin: 4pt 0 6pt 0; background: #f4f7fb; border-radius: 3pt; padding: 5pt 7pt; }
.where svg { flex: 0 0 auto; margin-right: 8pt; }
.where .wtext { font-size: 9.5pt; color: #334; }
.where .wtext b { color: #1a3c6e; }
ol.do { margin: 2pt 0 4pt 0; padding-left: 18pt; break-inside: avoid; }
ol.do li { margin: 2pt 0; }
.fig { text-align: center; margin: 6pt 0 4pt 0; page-break-inside: avoid; }
.fig img { max-width: 100%%; border: 1px solid #c8ced6; }
.fig .cap { font-size: 8.5pt; color: #666; margin-top: 2pt; }
.figrow { display: flex; gap: 8pt; align-items: flex-start; margin: 6pt 0 4pt 0; page-break-inside: avoid; }
.figrow .fig { flex: 1 1 0; margin: 0; min-width: 0; }
.figrow .fig img { width: 100%% !important; height: auto !important; }
.ok { background: #e6f4ea; border-left: 4px solid #2e7d32; padding: 4pt 8pt; margin: 6pt 0 2pt 0; font-size: 10pt; }
.ok b { color: #2e7d32; }
.warn { background: #fdecea; border-left: 4px solid #c62828; padding: 4pt 8pt; margin: 6pt 0 2pt 0; font-size: 10pt; }
.warn b { color: #c62828; }
.tip { background: #fff8e1; border-left: 4px solid #f9a825; padding: 4pt 8pt; margin: 6pt 0 2pt 0; font-size: 10pt; }
.tip b { color: #b26a00; }
.diff { background: #ede7f6; border-left: 4px solid #5e35b1; padding: 4pt 8pt; margin: 6pt 0 2pt 0; font-size: 10pt; }
.diff b { color: #4527a0; }
code, .code { font-family: "Noto Sans Mono CJK KR", "DejaVu Sans Mono", monospace; font-size: 9.5pt; }
code { background: #f1f3f5; padding: 0 3pt; border-radius: 2pt; }
pre { background: #1e2530; color: #e8ecf1; padding: 7pt 9pt; border-radius: 3pt; font-size: 9.5pt; margin: 4pt 0 6pt 0; white-space: pre-wrap; page-break-inside: avoid; }
.flow { display: flex; flex-wrap: wrap; gap: 6pt; margin: 6pt 0 10pt 0; }
.flow .f { background: #e9eef5; border: 1px solid #c5cfdd; border-radius: 3pt; padding: 3pt 8pt; font-size: 9.5pt; }
.flow .arrow { align-self: center; color: #888; }
ul.chk { list-style: none; padding-left: 0; margin: 4pt 0; break-inside: avoid; }
ul.chk li { margin: 2pt 0; }
ul.chk li:before { content: "☐  "; color: #1a3c6e; }
.kbd { display: inline-block; border: 1px solid #999; border-bottom-width: 2px; border-radius: 3px; padding: 0 4px; font-size: 9pt; background: #fafafa; font-family: "DejaVu Sans Mono", monospace; }
.small { font-size: 9pt; color: #666; }
.todo { border: 2px dashed #9aa5b1; color: #3a4654; background: #f7f9fb; padding: 10pt 12pt; text-align: left; font-size: 9.5pt; width: 165mm; margin: 0 auto; }
.todo .ttl { font-weight: 700; color: #6b7785; margin-bottom: 4pt; }
.todo .desc { margin-bottom: 4pt; }
.todo .lnk { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt; color: #1a3c6e; }
.cmd { background: #1e2530; color: #e8ecf1; padding: 7pt 9pt; border-radius: 3pt; margin: 4pt 0 6pt 0; }
.cmd .lbl { font-size: 8.5pt; color: #9cc4ff; margin-bottom: 3pt; }
.cmd pre { margin: 0; padding: 0; background: none; }
"""

# Minimap zones: VS Code window schematic 120x80
# zones: activity(left bar), top(command/search bar), explorer(left side panel), editor(center),
# chat(right panel), chatinput(bottom of chat panel), status(bottom bar), full(whole), dialog(center popup), external(outside VS Code)
def minimap(zone):
    W,H=118,78
    base = []
    base.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="2" fill="#f8fafc" stroke="#9aa5b1"/>')
    base.append(f'<rect x="1" y="1" width="{W-2}" height="8" fill="#e2e8f0"/>')           # top bar
    base.append(f'<rect x="1" y="9" width="10" height="{H-16}" fill="#d9e0e8"/>')         # activity bar
    base.append(f'<rect x="11" y="9" width="24" height="{H-16}" fill="#eef2f6"/>')        # explorer
    base.append(f'<rect x="80" y="9" width="{W-81}" height="{H-16}" fill="#eef2f6"/>')    # chat panel
    base.append(f'<rect x="83" y="{H-24}" width="{W-87}" height="14" rx="1.5" fill="#fff" stroke="#b7c0cb"/>')  # chat input
    base.append(f'<rect x="1" y="{H-7}" width="{W-2}" height="6" fill="#d9e0e8"/>')       # status bar
    hl = {
        'activity': (1,9,10,H-16),
        'top': (1,1,W-2,8),
        'explorer': (11,9,24,H-16),
        'editor': (35,9,45,H-16),
        'chat': (80,9,W-81,H-16),
        'chatinput': (83,H-24,W-87,14),
        'status': (1,H-7,W-2,6),
        'full': (1,1,W-2,H-2),
        'dialog': (28,18,62,42),
        'bottomright': (78,H-30,W-79,23),
    }
    parts = list(base)
    if zone == 'external':
        parts = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="2" fill="#fff" stroke="#9aa5b1" stroke-dasharray="3 2"/>',
                 f'<text x="{W/2}" y="{H/2+4}" font-size="9" text-anchor="middle" fill="#c62828" font-weight="bold">VS Code 밖</text>']
    elif zone == 'browser':
        parts = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="2" fill="#fff" stroke="#9aa5b1" stroke-dasharray="3 2"/>',
                 f'<text x="{W/2}" y="{H/2+4}" font-size="9" text-anchor="middle" fill="#c62828" font-weight="bold">웹 브라우저</text>']
    elif zone == 'terminal':
        parts = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="2" fill="#111" stroke="#9aa5b1"/>',
                 f'<text x="{W/2}" y="{H/2+4}" font-size="9" text-anchor="middle" fill="#fff" font-weight="bold">검은 명령창</text>']
    elif zone in hl:
        x,y,w,h = hl[zone]
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ef4444" fill-opacity="0.28" stroke="#dc2626" stroke-width="1.5"/>')
    return f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'

def esc(s): return _h.escape(s)

def step(n, title, where_zone, where_text, do_items, figs='', ok='', extra=''):
    do_html = ''.join(f'<li>{d}</li>' for d in do_items)
    ok_html = f'<div class="ok"><b>확인</b> · {ok}</div>' if ok else ''
    blocks=[b for b in figs.split('\x00') if b.strip()]
    first=blocks[0] if blocks else ''
    mid=''.join(blocks[1:-1]) if len(blocks)>2 else ''
    last=blocks[-1] if len(blocks)>1 else ''
    if last:
        return f'''<div class="step">
<div class="keep"><div class="step-head"><span class="num">{n}</span><span class="step-title">{title}</span></div>
<ol class="do">{do_html}</ol>
{first}</div>{mid}<div class="keep">{last}{ok_html}{extra}</div></div>'''
    return f'''<div class="step">
<div class="keep"><div class="step-head"><span class="num">{n}</span><span class="step-title">{title}</span></div>
<ol class="do">{do_html}</ol>
{first}{ok_html}{extra}</div></div>'''

def fig(src, cap, w=None, h=None):
    from PIL import Image
    im=Image.open('img/'+src); ar=im.height/im.width
    PW=180.0; PH=150.0
    natural = im.width*25.4/96.0          # 100% scale at 96dpi
    wmm = min(PW, natural)
    if h:
        style=f' style="height:{h};width:auto"'
    elif w:
        style=f' style="width:{w}"'
    elif wmm*ar > PH:
        style=f' style="height:{PH}mm;width:auto"'
    else:
        style=f' style="width:{wmm:.0f}mm"'
    return f'\x00<div class="fig"><img src="img/{src}"{style}/><div class="cap">{cap}</div></div>'

def figrow(*figs):
    return '\x00<div class="figrow">' + ''.join(figs).replace('\x00','') + '</div>'

def warn(t): return f'<div class="warn"><b>주의</b> · {t}</div>'
def tip(t): return f'<div class="tip"><b>팁</b> · {t}</div>'
def diff(t): return f'<div class="diff"><b>화면이 다를 때</b> · {t}</div>'

def page(title_short, right, body):
    css = CSS % {'doc_short': title_short, 'doc_right': right}
    return f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'

def todo_fig(cap, desc='', links=()):
    lk=''.join(f'<div class="lnk">{l}</div>' for l in links)
    return f'\x00<div class="fig"><div class="todo"><div class="ttl">화면 참고</div><div class="desc">{desc}</div>{lk}</div><div class="cap">{cap}</div></div>'

def cover(num, title_html, sub_html, lead_html, foot='2026-09 · Windows 11 기준'):
    return f'''<div class="cover">
<div class="band"></div><div class="deco"></div><div class="deco2"></div>
<div class="series">실습 환경 세팅 문서 · {num} / 4</div>
<div class="num">0{num}</div>
<h1>{title_html}</h1>
<div class="sub">{sub_html}</div>
<div class="lead">{lead_html}</div>
<div class="foot">{foot}</div>
</div>'''
