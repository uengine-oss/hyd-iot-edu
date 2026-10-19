"""학교PC_설치확인.md → 학교PC_설치확인.html (복사 버튼 · 절 이동 막대 · 체크 표시 · 그림 크게 보기가 있는 웹 페이지).

    python build_html.py             이 폴더에 학교PC_설치확인.html 을 쓴다(브라우저로 더블클릭해 연다. 그림은 img/)
    python build_html.py --fragment  claude.ai 페이지로 올릴 조각(문서 틀 없이)을 표준 출력으로 낸다

필요한 것: pandoc.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / '학교PC_설치확인.md'
OUT = HERE / '학교PC_설치확인.html'
md = SRC.read_text(encoding='utf-8')
md = re.sub(r'^---\n.*?\n---\n', '', md, flags=re.S)          # front matter
md = re.sub(r'^# 학교 PC 설치 · 실행 확인\n', '', md, flags=re.M)  # title goes in header
body = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--wrap=none'],
                      input=md, capture_output=True, text=True, check=True).stdout
body = re.sub(r'<table>', '<div class="tbl"><table>', body).replace('</table>', '</table></div>')
body = body.replace('<img ', '<img loading="lazy" ')
# check boxes on h3/h4 (the things to confirm)
def chk(m):
    tag, attrs, inner = m.group(1), m.group(2), m.group(3)
    hid = re.search(r'id="([^"]+)"', attrs).group(1)
    return (f'<{tag}{attrs}><label class="chk"><input type="checkbox" id="c-{hid}" data-k="{hid}">'
            f'<span class="box" aria-hidden="true"></span><span class="t">{inner}</span></label></{tag}>')
body = re.sub(r'<(h3|h4)([^>]*)>(.*?)</\1>', chk, body)
heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
def short(t):
    t = re.sub('<[^>]+>', '', t)
    return t.split('.')[0] if t[:2] in ('A.', 'B.', 'C.', 'D.', 'E.') else t[:2]
LABELS = ['창 세 가지', '0 설치', 'A 필수', 'B 화면', 'C 막힐 때', 'D 복제', 'E 직접 설치', 'F 미확인']
nav = ''.join(f'<a href="#{i}">{html.escape(LABELS[n] if n < len(LABELS) else short(t))}</a>' for n, (i, t) in enumerate(heads))
lead = '학생 PC 한 대에서 실습 스택이 끝까지 켜지고 도는지 30분 안에 확인하는 순서다. 그림은 2026-10-19 클라우드에서 실제로 진행한 화면이다.'
page = f'''<title>학교 PC 설치 확인</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* 현장 점검표: 한 줄 기둥, 위에 고정된 절 이동 막대, 확인 항목은 체크 칸이 달린 제목. 설비 도장색(강철 청회색)에 안전 주황 하나 */
:root {{
  --bg: #f4f6f8; --surface: #ffffff; --fg: #1b232c; --muted: #5b6876; --line: #d6dde4;
  --accent: #d9601a; --steel: #24486b; --nav: #24486b; --code-bg: #e9eef3; --ok: #1f7a4d; --note: #fff4e8; --note-line: #e8a46a;
  --f-body: "IBM Plex Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  --f-mono: "IBM Plex Mono", "D2Coding", ui-monospace, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #11161b; --surface: #182029; --fg: #e3e8ee; --muted: #9aa7b4; --line: #2c3845;
  --accent: #f08a45; --steel: #8fb4d8; --nav: #1d3550; --code-bg: #222c37; --ok: #4cc28a; --note: #2a2119; --note-line: #9a6638; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #11161b; --surface: #182029; --fg: #e3e8ee; --muted: #9aa7b4; --line: #2c3845;
  --accent: #f08a45; --steel: #8fb4d8; --nav: #1d3550; --code-bg: #222c37; --ok: #4cc28a; --note: #2a2119; --note-line: #9a6638; color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--fg); font: 16px/1.7 var(--f-body); word-break: keep-all; overflow-wrap: anywhere; }}
body::before {{ content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--nav); }}
.wrap {{ max-width: 760px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 0 48px; }}
header.top {{ padding-block: 22px 14px; }}
header.top .kicker {{ font: 500 12px/1 var(--f-mono); letter-spacing: .08em; color: var(--accent); text-transform: uppercase; }}
header.top h1 {{ font-size: 1.6rem; line-height: 1.25; margin: 8px 0 8px; text-wrap: balance; }}
header.top p {{ margin: 0; color: var(--muted); font-size: .95rem; }}
.progress {{ margin-top: 12px; font: 500 13px var(--f-mono); color: var(--muted); font-variant-numeric: tabular-nums; }}
.progress b {{ color: var(--ok); }}
nav.jump {{ position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--nav); display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none;
  padding-left: max(8px, env(safe-area-inset-left, 0px)); padding-right: max(8px, env(safe-area-inset-right, 0px)); }}
nav.jump a {{ color: #fff; text-decoration: none; font: 500 14px var(--f-body); padding: 10px 12px; white-space: nowrap; }}
nav.jump a:focus-visible, nav.jump a:hover {{ background: rgba(255,255,255,.14); }}
h2 {{ font-size: 1.25rem; margin: 40px 0 10px; padding-top: 12px; border-top: 3px solid var(--steel); color: var(--steel); scroll-margin-top: 56px; text-wrap: balance; }}
h3, h4 {{ margin: 28px 0 8px; scroll-margin-top: 56px; line-height: 1.4; }}
h3 {{ font-size: 1.08rem; }} h4 {{ font-size: 1rem; }}
.chk {{ display: flex; gap: 10px; align-items: flex-start; cursor: pointer; }}
.chk input {{ position: absolute; opacity: 0; width: 1px; height: 1px; }}
.chk .box {{ flex: none; width: 24px; height: 24px; margin-top: 1px; border: 2px solid var(--accent); border-radius: 5px; display: grid; place-items: center; background: var(--surface); }}
.chk input:checked + .box {{ background: var(--ok); border-color: var(--ok); }}
.chk input:checked + .box::after {{ content: ""; width: 6px; height: 11px; border: solid var(--surface); border-width: 0 3px 3px 0; transform: rotate(45deg) translate(-1px,-1px); }}
.chk input:focus-visible + .box {{ outline: 3px solid var(--accent); outline-offset: 2px; }}
.chk input:checked ~ .t {{ color: var(--muted); }}
p, li {{ max-width: 68ch; }}
ol, ul {{ padding-left: 1.3em; }} li {{ margin: 4px 0; }}
code {{ font: .88em var(--f-mono); background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }}
pre {{ background: var(--code-bg); padding: 12px 14px; border-radius: 6px; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ margin: 14px 0; padding: 10px 14px; background: var(--note); border-left: 4px solid var(--note-line); border-radius: 0 6px 6px 0; }}
blockquote p {{ margin: 6px 0; }}
figure {{ margin: 12px 0 20px; }}
figure img {{ display: block; width: 100%; max-width: 100%; height: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); cursor: zoom-in; }}
figcaption {{ font-size: .85rem; color: var(--muted); margin-top: 6px; }}
.tbl {{ overflow-x: auto; margin: 12px 0 18px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
th, td {{ text-align: left; vertical-align: top; padding: 8px 10px; border-bottom: 1px solid var(--line); min-width: 7em; }}
th {{ background: var(--code-bg); font-weight: 700; }}
tr:last-child td {{ border-bottom: 0; }}
.zoom {{ position: fixed; inset: 0; z-index: 20; background: rgba(8,12,16,.94); overflow: auto; display: flex; align-items: flex-start; justify-content: center;
  padding: calc(env(safe-area-inset-top, 0px) + 48px) max(8px, env(safe-area-inset-right, 0px)) calc(env(safe-area-inset-bottom, 0px) + 16px) max(8px, env(safe-area-inset-left, 0px)); }}
.zoom img {{ max-width: none; width: 1440px; height: auto; }}
.zoom button {{ position: fixed; top: calc(env(safe-area-inset-top, 0px) + 8px); right: max(8px, env(safe-area-inset-right, 0px)); font: 500 15px var(--f-body);
  background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 8px 14px; }}
pre {{ position: relative; }}
.copy {{ position: absolute; top: 6px; right: 6px; font: 500 13px var(--f-body); background: var(--accent); color: #fff; border: 0; border-radius: 5px; padding: 5px 10px; cursor: pointer; }}
.copy:focus-visible {{ outline: 3px solid var(--steel); outline-offset: 2px; }}
pre:has(.copy) {{ padding-right: 72px; }}
.reset {{ margin-top: 32px; font: 500 14px var(--f-body); background: transparent; color: var(--muted); border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; }}
@media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior: smooth; }} }}
</style>
<header class="wrap top">
  <div class="kicker">HYD Lab · 2026-10-20 학교 점검</div>
  <h1>학교 PC 설치 · 실행 확인</h1>
  <p>{lead}</p>
  <div class="progress" id="progress"></div>
</header>
<nav class="jump" aria-label="절 이동">{nav}</nav>
<main class="wrap">
{body}
<button type="button" class="reset" id="resetChecks">체크 표시 모두 지우기</button>
</main>
<div class="zoom" id="zoom" hidden><button type="button" id="zoomClose">닫기</button><img id="zoomImg" alt=""></div>
<script>
(function () {{
  const KEY = 'hyd-school-check';
  let saved = {{}};
  try {{ saved = JSON.parse(localStorage.getItem(KEY) || '{{}}'); }} catch (e) {{ saved = {{}}; }}
  const boxes = [...document.querySelectorAll('.chk input')];
  const prog = document.getElementById('progress');
  function update() {{
    const n = boxes.filter(b => b.checked).length;
    prog.innerHTML = '확인한 항목 <b>' + n + '</b> / ' + boxes.length;
  }}
  boxes.forEach(b => {{
    b.checked = !!saved[b.dataset.k];
    b.addEventListener('change', () => {{
      saved[b.dataset.k] = b.checked;
      try {{ localStorage.setItem(KEY, JSON.stringify(saved)); }} catch (e) {{}}
      update();
    }});
  }});
  document.getElementById('resetChecks').addEventListener('click', () => {{
    boxes.forEach(b => b.checked = false); saved = {{}};
    try {{ localStorage.removeItem(KEY); }} catch (e) {{}}
    update();
  }});
  update();
  document.querySelectorAll('pre').forEach(pre => {{
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'copy'; btn.textContent = '복사';
    btn.addEventListener('click', () => {{
      const text = pre.querySelector('code') ? pre.querySelector('code').innerText : pre.innerText.replace(/복사(됨)?$/, '');
      const done = () => {{ btn.textContent = '복사됨'; setTimeout(() => btn.textContent = '복사', 1500); }};
      const fallback = () => {{ const r = document.createRange(); r.selectNodeContents(pre.querySelector('code') || pre); const s = getSelection(); s.removeAllRanges(); s.addRange(r); btn.textContent = '길게 눌러 복사'; }};
      try {{ navigator.clipboard.writeText(text.trim()).then(done, fallback); }} catch (e) {{ fallback(); }}
    }});
    pre.appendChild(btn);
  }});
  const zoom = document.getElementById('zoom'), zimg = document.getElementById('zoomImg');
  document.querySelectorAll('figure img').forEach(img => img.addEventListener('click', () => {{
    zimg.src = img.src; zimg.alt = img.alt; zoom.hidden = false;
  }}));
  function close() {{ zoom.hidden = true; zimg.removeAttribute('src'); }}
  document.getElementById('zoomClose').addEventListener('click', close);
  zoom.addEventListener('click', e => {{ if (e.target === zoom) close(); }});
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape' && !zoom.hidden) close(); }});
}})();
</script>
'''
if '--fragment' in sys.argv:
    sys.stdout.write(page)
else:
    OUT.write_text('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
                   '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                   '<style>body{margin:0} img{max-width:100%} [hidden]{display:none!important}</style>\n</head>\n<body>\n'
                   + page + '\n</body>\n</html>\n', encoding='utf-8')
    print(f'{OUT.name} {OUT.stat().st_size // 1024} KB · 그림 {len(set(re.findall(r"src=\"(img/[^\"]+)\"", body)))}장 · 절 {len(heads)}개')
