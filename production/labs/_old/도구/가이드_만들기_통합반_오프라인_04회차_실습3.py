"""통합반 오프라인 04회차 실습 3 「검토된 지식만 기존 그래프에 반영하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다.
요청 글은 기록/ 의 원문에서, 표와 수와 질의는 완성/ 과 기록/ 의 파일에서 읽어 옮긴다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '04회차_실습2_지식_추출'
css = re.search(r'<style>(.*?)</style>', (LAB / '도구' / '디자인_샘플.html').read_text(encoding='utf-8'), re.S).group(1)
css += '''
.step{display:none}.step.on{display:block}
.track i{cursor:pointer}
.hero h1 small{display:block;font-size:15px;font-weight:700;color:var(--sub);letter-spacing:0;margin-bottom:6px}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0 0}
.flow div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 14px;font-size:14.5px;line-height:1.55;position:relative}
.flow b{display:block;font-size:15.5px;margin-bottom:4px}
.flow em{font-style:normal;display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--accent);color:#fff;font-weight:800;font-size:13px;margin-bottom:8px}
.sect{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px;margin-bottom:72px}
.sect h2{font-size:20px;margin:0 0 10px}
.sect p{margin:0 0 12px;font-size:16px;color:#333b47}
.tree{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.9;background:#14181f;color:#e8edf5;border-radius:14px;padding:18px 22px;white-space:pre;overflow:auto}
.tree span{color:#8fb4ff}.tree i{color:#8a94a3;font-style:normal}.tree b{color:#ffd76a}
.tree.wrap{white-space:pre-wrap;font-size:13.5px;line-height:1.75}
table.res{width:100%;border-collapse:collapse;font-size:14.5px;line-height:1.6;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid var(--line);margin:18px 0 8px}
table.res th{background:#eef1f5;text-align:left;padding:10px 14px;font-size:13px}
table.res td{padding:10px 14px;border-top:1px solid var(--line);vertical-align:top}
table.res mark{background:#fff1a8;padding:0 3px;border-radius:3px}
table.res td.nw{white-space:nowrap}
table.res code{font-size:.86em}
.ask{list-style:none;padding:0;margin:18px 0;display:grid;gap:10px}
.ask li{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ok);border-radius:0 12px 12px 0;padding:12px 18px;font-size:15.5px}
.ask b{display:block}
textarea{width:100%;min-height:200px;border:2px dashed #9bc3ac;border-radius:16px;padding:18px 20px;font:16px/1.8 inherit;font-family:inherit;background:#f7fcf9;resize:vertical;color:var(--ink)}
.wfoot{display:flex;gap:12px;align-items:center;margin:10px 0 0;font-size:14px;color:var(--sub)}
.wfoot button{border:0;background:var(--ok);color:#fff;border-radius:10px;padding:10px 20px;font-weight:700;white-space:nowrap}
details{margin:18px 0 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 20px}
summary{cursor:pointer;font-weight:700;color:var(--accent)}
details .copy{box-shadow:none}
.copy-text.pre{white-space:pre-wrap;font-size:16px;line-height:1.8}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:20px 0}
.vs div{border-radius:16px;padding:20px 22px;font-size:15.5px;line-height:1.7}
.vs .bad{background:#fdecec}.vs .good{background:var(--ok-soft)}
.vs b{display:block;margin-bottom:6px}.vs .bad b{color:#b3261e}.vs .good b{color:var(--ok)}
.vs q{display:block;quotes:none;background:#fff;border-radius:10px;padding:10px 14px;margin:8px 0;font-size:15px}
.vs ul{margin:6px 0 0;padding-left:20px}
.four{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}
.four div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px}
.four b{display:block;color:var(--accent);font-size:15.5px}
.pipe{display:grid;grid-template-columns:1fr 28px 1fr 28px 1fr;gap:8px;align-items:stretch;margin:18px 0 6px}
.pipe div{background:#f6f8fa;border:1px solid var(--line);border-radius:14px;padding:16px 16px;font-size:14.5px;line-height:1.6}
.pipe div.out{background:var(--accent-soft);border-color:#c5d3fb}
.pipe b{display:block;font-size:16px;margin-bottom:4px}
.pipe small{display:block;font-family:Consolas,"D2Coding",monospace;font-size:12.5px;color:var(--sub);margin-top:6px}
.pipe span{align-self:center;text-align:center;font-size:22px;color:var(--faint);font-weight:800}
.next a,.back{cursor:pointer}
.chg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}
.chg .tree{font-size:13.5px;line-height:1.75;padding:14px 18px;white-space:pre-wrap}
.cite{display:grid;grid-template-columns:1fr 44px 1fr;gap:6px;align-items:center;margin:18px 0 8px}
.cite>div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;font-size:14.5px;line-height:1.7}
.cite>div.src{background:#fffdf3;border-color:#eadfae}
.cite small{display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:4px}
.cite mark{background:#fff1a8;padding:0 3px;border-radius:3px}
.cite>span{text-align:center;font-size:22px;color:var(--accent);font-weight:800}
.cite dl{margin:0;display:grid;grid-template-columns:64px 1fr;gap:2px 10px}.cite dt{color:var(--sub);font-size:13px}.cite dd{margin:0}
@media(max-width:760px){.flow,.vs,.four,.pipe,.chg,.cite{grid-template-columns:1fr}.pipe span,.cite>span{display:none}}
'''
e = html.escape
def vs(hl):  # VS Code 지도: hl in chat/explorer/editor
    c = lambda k, on, off: on if hl == k else off
    return f'''<svg viewBox="0 0 520 320" role="img" aria-label="VS Code 화면 지도">
<rect x="1" y="1" width="518" height="318" rx="14" fill="#fff" stroke="#cfd6e0" stroke-width="2"/><rect x="1" y="1" width="518" height="30" rx="14" fill="#eef1f5"/><rect x="1" y="18" width="518" height="14" fill="#eef1f5"/>
<circle cx="20" cy="16" r="5" fill="#f26b5e"/><circle cx="37" cy="16" r="5" fill="#f5c04f"/><circle cx="54" cy="16" r="5" fill="#5bc467"/><rect x="1" y="32" width="38" height="287" fill="#e4e8ee"/>
<rect x="11" y="46" width="18" height="18" rx="4" fill="#aab4c3"/><rect x="11" y="76" width="18" height="18" rx="4" fill="#c7ceda"/>
<rect x="39" y="32" width="120" height="287" fill="{c('explorer','#eaf0ff','#f6f8fa')}" stroke="{c('explorer','#2f5bea','none')}" stroke-width="3"/>
<text x="51" y="54" font-size="11" font-weight="800" fill="{c('explorer','#2f5bea','#5b6573')}">탐색기</text>
<rect x="51" y="66" width="70" height="8" rx="4" fill="#c7ceda"/><rect x="63" y="84" width="76" height="8" rx="4" fill="#d8dee7"/><rect x="63" y="100" width="76" height="8" rx="4" fill="#d8dee7"/><rect x="51" y="120" width="54" height="8" rx="4" fill="#c7ceda"/><rect x="51" y="138" width="62" height="8" rx="4" fill="#c7ceda"/>
<rect x="163" y="36" width="183" height="280" rx="8" fill="{c('editor','#eaf0ff','#fff')}" stroke="{c('editor','#2f5bea','none')}" stroke-width="3"/>
<text x="175" y="56" font-size="11" font-weight="800" fill="{c('editor','#2f5bea','#5b6573')}">편집기</text>
<rect x="175" y="70" width="150" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="88" width="120" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="106" width="158" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="124" width="96" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="142" width="140" height="8" rx="4" fill="#dfe4ec"/>
<rect x="352" y="40" width="160" height="272" rx="10" fill="{c('chat','#f3eeff','#f6f8fa')}" stroke="{c('chat','#6a3fd1','#e4e8ee')}" stroke-width="3"/>
<text x="366" y="62" font-size="12" font-weight="800" fill="{c('chat','#6a3fd1','#5b6573')}">Copilot 채팅</text>
<rect x="366" y="76" width="118" height="26" rx="8" fill="#fff"/><rect x="380" y="112" width="118" height="40" rx="8" fill="{c('chat','#e2d6fb','#e9edf3')}"/><rect x="364" y="264" width="136" height="36" rx="10" fill="#fff" stroke="{c('chat','#6a3fd1','#cfd6e0')}" stroke-width="2"/></svg>'''
ICO = {'chat': '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#6a3fd1"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6a3fd1"/></svg>',
'explorer': '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#2f5bea"/></svg>',
'editor': '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="12" y="3" width="9" height="16" rx="2" fill="#2f5bea"/></svg>'}
def where(k, label): return f'<span class="where {"w-chat" if k=="chat" else "w-code"}">{ICO[k]}{label}</span>'
cid = [0]
def copy(text, head='Copilot에게 보낼 요청', pre=False, rich=None):
    cid[0] += 1; i = f'c{cid[0]}'
    body = rich if rich else e(text)
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}" id="{i}">{body}</div><div class="copy-foot">붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸</div></div>'
shots = []
def shot(desc):
    shots.append(desc); n = len(shots)
    return f'<div class="shot"><div><b>사진 {n} — 찍어 주실 화면</b><span>{desc}</span></div></div>'
def write(i, ph): return f'<textarea id="{i}" data-draft="{i}" placeholder="{e(ph)}"></textarea><div class="wfoot"><button data-copy="{i}">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸 · 쓴 글은 이 브라우저에 저장된다</span></div>'
def do(n, k, label, title, body): return f'<section class="do" data-n="{n}">{where(k,label)}<h2>{title}</h2>{body}</section>'
def hero(no, title, lead, facts): return f'<section class="hero"><div class="no">{no}</div><h1>{title}</h1><p>{lead}</p><div class="facts">' + ''.join(f'<div><small>{a}</small>{b}</div>' for a, b in facts) + '</div></section>'
def mapbox(k, title, text): return f'<section class="map"><div>{vs(k)}</div><div><h2>{title}</h2>{text}</div></section>'
def nxt(i, label, prev=None):
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 출처가 붙은 지식 후보 파일 하나, 그 출처를 원문에 대어 보는 대조.py, 사람이 읽을 곳을 모은 대조 결과</b></div></div>'
    if prev is not None: h += f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P = lambda f: (R / '기록' / f).read_text(encoding='utf-8').strip()
def richpre(text, cls):  # 문단마다 밑줄 색을 입힌다(문단 수와 cls 의 길이가 같아야 한다)
    ps = text.split('\n\n'); assert len(ps) == len(cls), (len(ps), cls)
    return '\n\n'.join(f'<span class="p-{c}">{e(p)}</span>' for p, c in zip(ps, cls))
def parts(*abc): return '<div class="parts">' + ''.join(f'<div class="{k}"><b>{t}</b>{d}</div>' for k, (t, d) in zip('abc', abc)) + '</div>'
def find(*items): return '<div class="find">' + ''.join(f'<div><i>{"①②③④"[i]}</i><p style="margin:0"><b>{t}</b><span>{d}</span></p></div>' for i, (t, d) in enumerate(items)) + '</div>'
def ifs(*items): return '<div class="if">' + ''.join(f'<div><b>{t}</b>{d}</div>' for t, d in items) + '</div>'
def note(t, d): return f'<div class="note"><b>{t}</b>{d}</div>'


# ── 이 묶음에서 더한 도우미
css += '''
.w-term{background:#e9f6ee;color:#1f7a4a}
.copy.term .copy-foot,.copy.web .copy-foot{color:var(--sub)}
.copy.term .copy-text,.copy.web .copy-text{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.7;white-space:pre-wrap}
.chain{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr;gap:6px;align-items:center;margin:18px 0 6px}
.chain div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 10px;font-size:14px;line-height:1.5;text-align:center}
.chain div.new{background:var(--accent-soft);border-color:#c5d3fb}
.chain div{min-width:0}.chain div b{display:block;font-size:14.5px;white-space:nowrap}.chain div small{display:block;font-family:Consolas,"D2Coding",monospace;font-size:10px;color:var(--sub);margin-top:2px;white-space:nowrap}
.chain span{text-align:center;font-family:Consolas,"D2Coding",monospace;font-size:9.5px;color:var(--accent);font-weight:700;line-height:1.3;white-space:nowrap}
.chain span::after{content:"→";display:block;font-size:18px;color:var(--faint)}
.out{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.8;background:#14181f;color:#e8edf5;border-radius:14px;padding:16px 22px;white-space:pre-wrap;margin:14px 0 6px}
.out b{color:#ffd76a}
@media(max-width:760px){.chain{grid-template-columns:1fr}.chain span::after{content:"↓"}}
'''
ICO['term'] = '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#1f7a4a"/><rect x="3" y="13" width="28" height="6" rx="2" fill="#1f7a4a"/></svg>'
ICO['web'] = '<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="3" y="3" width="28" height="5" rx="2" fill="#2f5bea"/></svg>'
def where(k, label): return f'<span class="where {"w-chat" if k=="chat" else "w-term" if k=="term" else "w-code"}">{ICO[k]}{label}</span>'
def tcopy(text, head='VS Code 터미널에 넣을 명령', foot='붙여넣는 곳 → VS Code 아래쪽 터미널(보이지 않으면 Ctrl+`). 붙여넣고 Enter', kind='term'):
    cid[0] += 1; i = f'c{cid[0]}'
    return f'<div class="copy {kind}"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text" id="{i}">{e(text)}</div><div class="copy-foot">{foot}</div></div>'
def qcopy(text, head='Neo4j Browser에 넣을 질의'): return tcopy(text, head, '붙여넣는 곳 → Neo4j Browser 맨 위의 입력 칸. 붙여넣고 실행 단추(▶)를 누른다', 'web')
def nxt(i, label, prev=None):
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 검토한 사람의 이름이 적힌 후보, 승인된 것만 출처와 함께 넣는 반영.py, 고장 유형에서 원문의 절까지 이어진 그래프</b></div></div>'
    if prev is not None: h += f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
def nb():  # Neo4j Browser 화면 지도
    return '''<svg viewBox="0 0 520 320" role="img" aria-label="Neo4j Browser 화면 지도">
<rect x="1" y="1" width="518" height="318" rx="14" fill="#fff" stroke="#cfd6e0" stroke-width="2"/><rect x="1" y="1" width="518" height="30" rx="14" fill="#eef1f5"/><rect x="1" y="18" width="518" height="14" fill="#eef1f5"/>
<circle cx="20" cy="16" r="5" fill="#f26b5e"/><circle cx="37" cy="16" r="5" fill="#f5c04f"/><circle cx="54" cy="16" r="5" fill="#5bc467"/><rect x="80" y="8" width="230" height="16" rx="8" fill="#fff"/><text x="92" y="20" font-size="10" fill="#5b6573">localhost:7474</text>
<rect x="1" y="32" width="44" height="287" fill="#e4e8ee"/><rect x="13" y="48" width="20" height="20" rx="5" fill="#aab4c3"/><rect x="13" y="80" width="20" height="20" rx="5" fill="#c7ceda"/>
<rect x="56" y="42" width="452" height="44" rx="8" fill="#eaf0ff" stroke="#2f5bea" stroke-width="3"/><text x="68" y="60" font-size="11" font-weight="800" fill="#2f5bea">입력 칸</text><rect x="68" y="68" width="250" height="8" rx="4" fill="#c5d3fb"/><path d="M484 54 l12 10 -12 10z" fill="#2f5bea"/>
<rect x="56" y="98" width="452" height="210" rx="8" fill="#f6f8fa" stroke="#cfd6e0" stroke-width="2"/><text x="112" y="118" font-size="11" font-weight="800" fill="#5b6573">결과 틀</text>
<rect x="64" y="108" width="36" height="190" rx="6" fill="#e4e8ee"/><rect x="72" y="120" width="20" height="14" rx="3" fill="#2f5bea"/><rect x="72" y="142" width="20" height="14" rx="3" fill="#aab4c3"/><rect x="72" y="164" width="20" height="14" rx="3" fill="#c7ceda"/>
<circle cx="190" cy="200" r="18" fill="#f5c04f"/><circle cx="270" cy="160" r="18" fill="#8fb4ff"/><circle cx="350" cy="205" r="18" fill="#5bc467"/><circle cx="430" cy="165" r="18" fill="#c7ceda"/><path d="M207 192 L253 168 M287 168 L334 197 M367 197 L413 173" stroke="#8a94a3" stroke-width="2"/></svg>'''
def nbmap(title, text): return f'<section class="map"><div>{nb()}</div><div><h2>{title}</h2>{text}</div></section>'
R = LAB / '통합반_오프라인' / '04회차_실습3_그래프_반영'
P = lambda f: (R / '기록' / f).read_text(encoding='utf-8').strip()
Q = lambda f: (R / '기록' / '조회' / f).read_text(encoding='utf-8').strip()
import csv, io
def rows(f):  # cypher-shell --format plain 의 출력(첫 줄은 열 이름)
    r = list(csv.reader(io.StringIO(Q(f)), skipinitialspace=True)); return r[0], r[1:]
def rtable(f, cols=None, mark=()):
    h, body = rows(f); idx = [h.index(c) for c in (cols or h)]
    def cell(v):
        v = e(v)
        for m in mark: v = v.replace(m, f'<mark>{m}</mark>')
        return v
    return ('<table class="res"><thead><tr>' + ''.join(f'<th>{e(h[i]).replace("_", " ")}</th>' for i in idx) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td{" class=nw" if len(r[i]) <= 14 else ""}>{cell(r[i])}</td>' for i in idx) + '</tr>' for r in body) + '</tbody></table>')
def outbox(f, bold=()):  # 넣기의 출력. 첫 줄(그래프 DB 의 주소)은 싣지 않는다
    ls = P(f).splitlines(); assert ls[0].startswith('그래프 DB:'), ls[0]
    s = e('\n'.join(ls[1:]))
    for b in bold: assert b in s, b; s = s.replace(b, f'<b>{b}</b>')
    return f'<div class="out">{s}</div>'
def nums(f):  # 넣기 출력에서 (전 노드, 전 관계, 뒤 노드, 뒤 관계, 새 노드, 새 관계)
    t = P(f); a = re.search(r'보내기 전: 노드 (\d+), 관계 (\d+)', t); b = re.search(r'보낸 뒤:\s+노드 (\d+), 관계 (\d+)', t); c = re.search(r'새로 생긴 것: 노드 (\d+), 관계 (\d+)', t)
    return tuple(int(x) for m in (a, b, c) for x in m.groups())

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1, P2, P3, P4, P6a, P6b, P6c, P7, P8, PXa = (P(f'{n}_prompt.txt') for n in ('1', '2', '3', '4', '6a', '6b', '6c', '7', '8', '여유a'))
a, rest = P1.split(' 후보와 관계를', 1); b, c = ('후보와 관계를' + rest).split(' 이 폴더의 규칙만으로는', 1)
P1rich = f'<span class="p-a">{e(a)}</span> <span class="p-b">{e(b)}</span> <span class="p-c">{e("이 폴더의 규칙만으로는" + c)}</span>'
assert re.sub(r'<[^>]+>', '', html.unescape(P1rich)) == P1
_h, _t = P2.split('\n\n'); _l = _h.split('\n')
P2rich = f'<span class="p-a">{e(_l[0])}</span>\n<span class="p-b">{e(chr(10).join(_l[1:]))}</span>\n\n<span class="p-c">{e(_t)}</span>'
assert re.sub(r'<[^>]+>', '', html.unescape(P2rich)) == P2

# ── 완성 폴더와 기록에서 옮기는 값
D = json.loads((R / '완성' / '결과' / '후보.json').read_text(encoding='utf-8'))
G = json.loads((R / '시작' / '지난_시간' / 'graph.json').read_text(encoding='utf-8'))
C = {x['번호']: x for x in D['후보']}; RL = {x['번호']: x for x in D['관계']}
gn, gr = len(G['nodes']), len(G['rels'])
n1 = nums('4_넣기_출력.txt'); n1b = nums('4_넣기_다시_출력.txt'); n7 = nums('7_넣기_출력.txt'); n7b = nums('7_넣기_다시_출력.txt'); nx = nums('여유a_넣기_출력.txt')
assert n1[:2] == (gn, gr) and n1b[4:] == (0, 0) and n7[:2] == n1[2:4] and n7b[4:] == (0, 0) and nx[:2] == n7[2:4]
sum4 = P('4_반영_요약.md'); sumF = (R / '완성' / '결과' / '반영_요약.md').read_text(encoding='utf-8')
assert '- K-007: 대기' in sum4 and '- K-008: 대기' in sum4 and '- K-007: 대기' not in sumF and '고장 유형에서 닿지 않는 조치' in sumF
cy4 = P('4_반영.cypher'); cyF = (R / '완성' / '결과' / '반영.cypher').read_text(encoding='utf-8')
n_stmt4 = len(re.findall(r';\s*$', cy4, re.M)); n_stmtF = len(re.findall(r';\s*$', cyF, re.M))
assert f'보낸 문장: {n_stmt4}개' in P('4_넣기_출력.txt') and f'보낸 문장: {n_stmtF}개' in P('7_넣기_출력.txt')
assert not re.search(r'\b(DELETE|REMOVE|DROP|CREATE)\b', re.sub(r"'(?:\\.|[^'\\])*'", "''", cyF))
def mdtable(md, head):
    body = md.split(head, 1)[1].split('\n## ', 1)[0]
    return [[c.strip() for c in l.strip().strip('|').split('|')] for l in body.splitlines() if l.startswith('| ') and not l.startswith('|---')]
tn = mdtable(sum4, '## 새로 만드는 노드'); tr = mdtable(sum4, '## 새로 만드는 관계')
def t2(t): return '<table class="res"><thead><tr>' + ''.join(f'<th>{e(c)}</th>' for c in t[0]) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td{" class=nw" if len(c) <= 16 else ""}>{e(c)}</td>' for c in r) + '</tr>' for r in t[1:]) + '</tbody></table>'
far = mdtable(sumF, '## 고장 유형에서 닿지 않는 조치'); assert len(far) == 4
KO = {'Cause': '원인', 'Skill': '조치'}
wait4 = ['K-007', 'K-008']
ctable = ('<table class="res"><thead><tr><th>번호</th><th>무엇</th><th>이름 또는 양 끝</th><th>그래프에</th><th>출처의 구간</th><th>2단계에서 적는 검토</th></tr></thead><tbody>'
          + ''.join(f'<tr><td class="nw"><b>{x["번호"]}</b></td><td class="nw">{x["클래스"]} ({KO[x["클래스"]]})</td><td>{e(x["name"])}</td><td class="nw">{"<mark>이미 있다</mark>" if x["등록됨"] else "새것"}</td><td class="nw">{x["출처"]["구간"]}</td><td class="nw">{"대기" if x["번호"] in wait4 else "승인"}</td></tr>' for x in D['후보'])
          + ''.join(f'<tr><td class="nw"><b>{x["번호"]}</b></td><td class="nw">{x["type"]}</td><td><code>{x["a"]}</code> → <code>{x["b"]}</code></td><td class="nw">{"<mark>이미 있다</mark>" if any(g["type"] == x["type"] and g["a"] == x["a"] and g["b"] == x["b"] for g in G["rels"]) else "새것"}</td><td class="nw">{x["출처"]["구간"]}</td><td class="nw">승인</td></tr>' for x in D['관계'])
          + '</tbody></table>')
n_ok4 = sum(1 for x in D['후보'] + D['관계'] if x['번호'] not in wait4)
cond1 = C['K-004']['조건'][0]; step2 = C['K-004']['단계'][1]; rel2 = RL['R-002']
blk = cy4.split('// K-004 단계 2\n', 1)[1].split('// K-004 단계 3', 1)[0].strip()
blk_old = cy4.split('// K-004 Skill', 1)[1].split('// K-004 단계 1', 1)[0].strip()
def cyq(s, marks):
    s = e(s, quote=False)
    for m in marks: assert m in s, m; s = s.replace(m, f'<b>{m}</b>')
    return f'<div class="tree wrap">{s}</div>'
h5, r5 = rows('q5_K-007_반영_뒤.out'); assert len(r5) == 3
h5a, r5a = rows('q5_처음_반영_뒤.out'); assert len(r5a) == 2
assert Q('q6_처음_반영_뒤.out') == '' and Q('q6_K-007_반영_뒤.out') == '' and Q('q7_처음_반영_뒤.out') == ''
h8, r8 = rows('q8_K-007_반영_뒤.out'); assert r8[0][:2] == [str(n7[2]), str(n7[3])]
h1, r1 = rows('q1_처음_반영_뒤.out'); new_by = {r[0]: int(r[2]) for r in r1 if int(r[2])}
assert sum(new_by.values()) == n1[4]
once = P('여유_한번에_출력.txt'); assert once.startswith('멈춤: Neo.ClientError.Statement.SyntaxError')

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하면</th></tr></thead><tbody>
<tr><td><b>이미 있는 대상</b></td><td><mark>1번 줄</mark> 그래프에 있는 노드는 id와 name을 그대로 두고 출처와 단계만 덧붙인다. 이미 있는 관계는 새로 만들지 않고 출처만 더한다</td><td>「문서의 이름으로 덮어쓴다」로 하면 지난 시간에 정한 이름이 문서가 들어올 때마다 바뀐다. 「새 노드로 만든다」로 하면 같은 원인이 둘이 된다</td></tr>
<tr><td><b>관계의 출처</b></td><td><mark>2번 줄</mark> 관계의 속성 <code>source</code>에 구간, <code>citation</code>에 인용</td><td>「관계에는 남기지 않는다」로 하면 그 원인이 왜 그 고장 유형에 이어졌는지를 그래프에서 되짚을 수 없다</td></tr>
<tr><td><b>조건을 담는 자리</b></td><td><mark>3번 줄</mark> 조치에서 조건이 인용한 절로 가는 <code>REFERS_TO</code> 관계에 <code>kind</code> · <code>text</code> · <code>citation</code>으로</td><td>「조건은 넣지 않는다」로 하면 절차는 있는데 금지 조건이 없는 지식이 된다. 일부만 들어간 상태다</td></tr>
<tr><td><b>단계의 id와 수치</b></td><td><mark>4번 줄</mark> <code>step:조치 이름/순서</code>. 수치는 넣지 않는다</td><td>「단계의 글이 같으면 같은 단계」로 하면 세 조치의 1단계가 하나로 합쳐져, 어느 조치의 몇 번째인지가 사라진다</td></tr>
<tr><td><b>한쪽 끝이 승인되지 않은 관계</b></td><td><mark>5번 줄</mark> 넣지 않고 요약에 적는다</td><td>「끝 노드도 함께 만든다」로 하면 승인하지 않은 후보가 관계에 끌려 들어온다</td></tr>
<tr><td><b>요약에 적을 것</b></td><td><mark>6번 줄</mark> 번호와 까닭, 레이블과 유형별 수, 이미 있어 늘지 않는 것</td><td>「수만」으로 하면 무엇이 왜 빠졌는지를 넣기 전에 알 수 없다</td></tr>
<tr><td><b>넣기 전에 확인할 것</b></td><td><mark>7번 줄</mark> 파일이 있는가, 대조 결과가 0건인가, 지우는 문장이 없는가</td><td>「확인 없이 보낸다」로 하면 누가 손으로 고친 파일에 지우는 문장이 섞여도 그대로 나간다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 4회차 · 실습 3 · 45분</small>검토한 후보만,<br>출처와 함께 그래프 DB에 넣는다',
 '앞 실습에서 문서의 문장을 출처가 붙은 후보로 뽑았다. 후보는 아직 지식이 아니다. 이번에는 그 후보를 <b>사람이 원문과 대조해 승인하고</b>, 승인한 것만 지난 시간의 그래프에 이어 넣는다. 넣은 뒤에는 고장 유형에서 원인, 조치, 작업 단계를 거쳐 매뉴얼의 절과 문서까지 관계를 따라가 본다. 넣는 문장은 AI가 만들지만, 무엇을 넣을지 정하는 것과 그래프 DB에 넣는 것은 내가 한다.',
 [('끝나면 남는 것', '검토가 적힌 후보.json, 반영.py, 출처까지 이어진 그래프'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna), Neo4j Browser'), ('전제', '온라인 4일차의 인제스천 단원을 들었다'), ('준비에 쓰는 시간', '약 3분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>후보 파일과 지난 시간의 그래프가 입력이다. 승인된 후보만 골라 넣는 문장(Cypher)을 파일로 먼저 만들고, 그 파일을 내가 읽은 다음 그래프 DB에 보낸다. 넣고 나면 고장 유형에서 문서까지 아래 길이 생긴다. 파란 칸이 오늘 새로 생기는 것이다.</p>'
  '<div class="chain"><div><b>고장 유형</b><small>FailureMode</small></div><span>MITIGATED_BY</span><div><b>조치</b><small>Skill</small></div><span>HAS_STEP</span><div class="new"><b>작업 단계</b><small>Step</small></div><span>REFERS_TO</span><div class="new"><b>매뉴얼 절</b><small>ManualSection</small></div><span>PART_OF</span><div class="new"><b>문서</b><small>KnowledgeSource</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 원문과 후보를 나란히 읽어 승인할 것을 정하고, AI가 만든 문장을 읽고, 넣은 결과를 그래프에서 조회하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>후보가 그래프의 무엇에 이어지고 무엇이 남는지 가르게 한다</div><div><em>2</em><b>검토를 적는다</b>원문과 대조한 것만 승인으로 적는다</div><div><em>3</em><b>정하고 계획 받기</b>출처를 그래프의 어디에 남길지 내가 정한다</div><div><em>4</em><b>만들고, 읽고, 넣는다</b>문장을 파일로 받아 읽은 뒤 내가 넣는다</div><div><em>5</em><b>조회하고 되돌려 준다</b>관계를 따라가 보고, 아쉬운 곳을 말해 고친다</div></div>'
  '<p style="margin:18px 0 0">1~5단계와 8단계가 이 다섯 걸음이다. 그 사이에 두 가지를 더 해 본다. 승인하지 않은 후보를 넣어 달라고, 그래프를 비워 달라고 일부러 요청해 보고(6단계), 후보 하나를 더 승인해 다시 넣어도 이미 넣은 것이 둘이 되지 않는지 본다(7단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 f'<div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md   <i>← 이 폴더의 규칙</i>\n├─ <span>문서/</span>                       <i>← 보관해 둔 원문. 읽기만 한다</i>\n├─ <span>지난_시간/</span>                  <i>← 그래프 DB에 넣을 스키마와 그래프</i>\n│  ├─ schema.json                <i>← 클래스 11, 관계 12</i>\n│  └─ graph.json                 <i>← 노드 {gn}, 관계 {gr}</i>\n├─ <span>결과/</span>\n│  ├─ <b>후보.json</b>                  <i>← 지난 실습에서 뽑은 후보 {len(D["후보"])}, 관계 {len(D["관계"])}, 보류 {len(D["보류"])}</i>\n│  └─ 대조_결과.md               <i>← 출처 58건을 원문에 대어 본 결과</i>\n├─ 대조.py                       <i>← 지난 실습에서 만든 대조 프로그램</i>\n├─ 출처_스키마.json              <i>← 작업 단계 · 매뉴얼 절 · 문서를 받는 자리</i>\n├─ graphdb.py                    <i>← 그래프 DB에 문장을 보내는 도구</i>\n└─ 그래프_준비.py                <i>← 그래프 DB를 처음 상태로 맞춘다</i></div>'
 '<p><b>출처_스키마.json</b>은 지난 시간의 스키마에 더해 쓰는 클래스 셋과 관계 셋이다. 온라인에서 본 「조치 → 작업 단계 → 매뉴얼 절 → 문서」의 구조가 여기에 적혀 있다. 지난 시간의 스키마에는 출처를 받을 자리가 없었다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 문서, 지난_시간, 결과 폴더와 맨 위의 네 파일(대조.py, 출처_스키마.json, graphdb.py, 그래프_준비.py)이 보이게.'))
+ do(2, 'term', 'VS Code · 터미널', '그래프 DB를 처음 상태로 맞춘다',
 f'<p>VS Code의 「터미널 → 새 터미널」로 아래쪽에 터미널을 연다. 아래 명령을 실행하면 <code>지난_시간/graph.json</code>의 노드 {gn}개와 관계 {gr}개가 실습용 그래프 DB에 들어간다. 이미 들어 있으면 늘지 않는다.</p>'
 + tcopy('python 그래프_준비.py')
 + f'<p style="margin-top:18px">아래와 같이 나오면 된다.</p><div class="out">지난_시간/graph.json: 노드 {gn}, 관계 {gr}\n그래프 DB 에 든 것:   <b>노드 {gn}, 관계 {gr}</b>\n준비됨: 지난 시간의 그래프가 그래프 DB 에 들어 있다.</div>'
 + ifs(('「멈춤: …닿지 못했다」고 나오면', '그래프 DB가 떠 있지 않은 것이다. 수업 환경이 켜져 있는지 확인하고, 그래도 같으면 강사에게 알린다.'),
       ('「멈춤: …이 실습의 스키마에 없는 종류의 노드」라고 나오면', '실습용으로 분리된 그래프 DB가 아닌 곳에 연결된 것이다. 아무것도 들어가지 않았다. 더 진행하지 말고 강사에게 알린다.'),
       ('python을 찾을 수 없다고 나오면', '<code>python</code> 대신 <code>python3</code>이나 <code>py</code>로 실행한다. 뒤의 명령도 같은 낱말로 바꿔 쓴다.')))
+ do(3, 'web', '웹 브라우저 · Neo4j Browser', 'Neo4j Browser를 열어 같은 수를 내 눈으로 본다',
 '<p>웹 브라우저에서 <code>http://localhost:7474</code>를 연다. 접속 주소는 <code>bolt://localhost:7687</code>, 사용자 이름은 <code>neo4j</code>, 비밀번호는 <code>hydpass123</code>이다. 맨 위의 입력 칸에 아래 질의를 붙여넣고 실행한다.</p>'
 + qcopy(Q('q0.cypher'))
 + f'<p style="margin-top:18px">노드 {gn}, 관계 {gr}이 나오면 준비가 끝난 것이다. 이 창은 닫지 않는다. 5단계부터 다시 쓴다.</p>'
 + shot(f'Neo4j Browser에 접속해 위 질의를 실행한 화면. 주소 표시줄의 localhost:7474, 맨 위의 입력 칸, 결과 표의 노드 {gn} · 관계 {gr}이 보이게.'))
+ nxt(1, '1. 넣기 전에, 어디에 이어지는지 읽게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '넣기 전에,<br>어디에 이어지는지 읽게 한다',
 '첫마디가 「후보를 그래프 DB에 넣어 줘」이면 AI는 후보 전부를 넣는 문장부터 쓴다. 검토가 끝났는지, 이미 있는 대상을 다시 만들지, 출처를 어디에 둘지는 AI가 알아서 정한다. 그래서 첫 요청은 <b>읽고, 그래프에 대어 보고, 정할 수 없는 것은 물어보라</b>는 요청으로 한다. 넣었을 때 생길 길을 먼저 말로 들어 두면, 5단계에서 그 길이 실제로 생겼는지 견줄 수 있다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '후보가 그래프의 무엇에 이어지는지와, Copilot이 나에게 묻는 것이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일, 바뀐 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 입력 칸 아래의 방식이 <b>에이전트</b>, 모델이 <b>GPT-6 Luna</b>인지 보고, 다르면 그 글자를 눌러 바꾼다.</p>')
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 파일 여섯 개를 읽으므로 답이 오는 데 1분 넘게 걸린다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 출처를 받는 자리, 지난 시간의 스키마와 그래프, 후보와 대조 결과. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '번호마다 한 줄의 표, 그리고 고장 유형에서 문서까지의 길. 「이미 있는 것인지 새것인지」를 칸으로 넣어 등록된 대상이 드러나게 했다.'), ('하지 말 것', '스스로 정하지 말 것, 파일을 만들거나 고치지 말 것.')))
+ do(2, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>문장은 사람마다 다르게 나온다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 후보와 관계의 표(이미 있는 것과 새것, 검토 값이 보이게), 고장 유형에서 문서까지의 길, 끝의 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('이미 있는 것을 가렸는가', f'후보 {len(D["후보"])}건 가운데 「쿨러 핀 오염」과 「팬 최대 운전」, 관계 {len(D["관계"])}건 가운데 둘은 지난 시간의 그래프에 이미 있다. 표에서 이 넷이 「이미 있음」으로 나뉘어 있는가.'),
        ('어디에도 이어지지 않는 것을 말했는가', '새 조치들은 절과 문서로는 이어지지만 고장 유형으로는 이어지지 않는다. 조치를 고장 유형에 잇는 관계가 지난 실습에서 보류로 남았기 때문이다. 이 말이 답에 있는지 본다. 8단계에서 다시 만난다.'),
        ('정하지 않고 되물은 것', '조건을 어디에 담을지, 관계의 출처를 어디에 남길지, 이미 있는 대상에 무엇을 덧붙일지 같은 물음이 온다. 그리고 지금은 모두 「대기」여서 아무것도 넣을 수 없다는 말이 있는지 본다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 일곱 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 출처를 그래프의 어디에 남길지는 정답이 하나가 아니다. 이 물음에는 3단계에서 내가 답한다.')
 + ifs(('파일이 생기거나 바뀌었다면', '요청의 마지막 문장이 빠진 것이다. 생긴 파일은 지우고, <code>결과/후보.json</code>이 바뀌었다면 완성 폴더가 아니라 <b>시작 폴더를 받은 원본</b>에서 다시 가져온다.'),
       ('표의 수가 다르다면', f'후보 {len(D["후보"])}건, 관계 {len(D["관계"])}건이어야 한다. 다르면 「후보.json 의 후보와 관계를 빠짐없이 표에 넣어 줘」라고 말한다.')))
+ nxt(2, '2. 원문과 대조하고, 검토를 적는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '원문과 대조하고,<br>검토를 적는다',
 '후보의 <code>검토</code> 칸은 모두 <code>대기</code>다. 대조 프로그램은 인용이 원문에 글자 그대로 있는지까지만 본다. 조건의 뜻이 뒤집히지 않았는지, 단계의 순서가 맞는지, 관계가 바르게 이어졌는지는 사람이 읽는다. 읽은 사람이 <b>이름을 밝혀</b> 승인한 것만 다음 단계로 간다. AI는 승인하지 않고, 내가 번호를 짚어 말한 것만 옮겨 적는다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', f'후보.json에 승인 {n_ok4}건과 대기 {len(wait4)}건이 내 이름과 함께 적혀 있다'), ('바뀌면 안 되는 것', '검토와 검토자 말고의 칸')])
+ do(1, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '네 곳을 원문과 나란히 읽는다',
 '<p><code>결과/후보.json</code>을 열고 <code>문서/HM-8_cooler-fan-manual.md</code>를 오른쪽으로 끌어 나란히 둔다. 다 읽을 수는 없으므로 읽을 곳을 정한다. 추출이 틀리는 방식이 넷이므로 읽을 곳도 넷이다. 찾기(Ctrl+F)로 아래 네 곳을 찾아 양쪽을 견준다.</p>'
 + shot('결과/후보.json과 문서/HM-8_cooler-fan-manual.md를 좌우로 나란히 연 VS Code 화면. 왼쪽은 K-004의 조건, 오른쪽은 HM-8.8이 보이게.')
 + '<div class="cite"><div class="src"><small>원문 · HM-8 · 구간 HM-8.8</small>' + e(cond1['출처']['인용']).replace('아닐 때', '<mark>아닐 때</mark>').replace('않는다', '<mark>않는다</mark>') + '</div><span>←</span><div><small>후보.json · K-004의 조건</small><dl><dt>구분</dt><dd>' + e(cond1['구분']) + '</dd><dt>내용</dt><dd>' + e(cond1['내용']).replace('아닐 때', '<mark>아닐 때</mark>').replace('않는다', '<mark>않는다</mark>') + '</dd></dl></div></div>'
 + find(('부정 조건 — 「아닐 때」「않는다」가 살아 있는가', '세 조치(K-004 · K-005 · K-006)의 조건을 HM-8.8의 첫 줄과 견준다. <code>내용</code>에서 「아닐 때」가 빠졌다면 금지의 뜻이 반대가 된다.'),
        ('수치와 단위 — 숫자와 단위가 원문과 같은가', f'K-004의 2단계를 HM-8.5의 SOP-COOL-11과 견준다. <code>수치</code>가 {e(json.dumps(step2["수치"], ensure_ascii=False))}인가.'),
        ('단계의 순서 — 번호와 순서가 원문과 같은가', f'K-006(부하 70 %와 야간 핀 세척)의 단계가 {len(C["K-006"]["단계"])}개이고 <code>순서</code>가 원문 SOP-COOL-13의 번호와 같은가. 원문에 없는 단계가 끼어 있지 않은가.'),
        ('대상과 관계 — 바르게 이어졌는가', f'<code>관계</code>의 {rel2["번호"]}를 본다. <code>{rel2["a"]}</code>에서 <code>{rel2["b"]}</code>로 가는 {rel2["type"]}이다. HM-8.4의 절 제목이 이 원인들이 쿨러 냉각 성능 상실의 원인이라고 말하는가.'))
 + note('HM-8.7은 일부러 남겨 둔다', '네 곳은 HM-8.4, HM-8.5, HM-8.8에 있다. K-007(쿨러 핀 세척)과 K-008(캐비닛 환기 보강)은 HM-8.7에서 온 후보인데 지금은 읽지 않는다. 읽지 않은 것은 승인하지 않는다. 이 둘은 대기로 두었다가 7단계에서 하나를 읽고 승인한다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '검토한 결과를 번호로 짚어 적게 한다',
 '<p>복사해 입력 칸에 붙여넣는다. <b>보내기 전에 「한지우」를 내 이름으로 고쳐 쓴다.</b> 원문과 다른 곳을 찾았다면 그 번호를 승인에서 빼고, 어디가 어떻게 다른지를 함께 적는다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=P2rich)
 + parts(('누가 검토했는가', '첫 문단. 검토자의 이름을 밝혔다. 규칙 파일은 이름을 받지 못하면 승인을 적지 않게 한다.'), ('무엇을 어떻게 정했는가', '승인하는 번호와 그 근거(무엇을 읽었는지), 대기로 두는 번호와 그 까닭. 번호로 짚어야 AI가 넘겨짚지 않는다.'), ('어디까지', '검토와 검토자 칸만. 그리고 대조 프로그램을 다시 돌려 0건인지 보게 했다. 검토를 적다가 다른 칸이 바뀌었으면 여기서 드러난다.')))
+ do(3, 'editor', 'VS Code · 편집기', '<code>결과/후보.json</code>에서 적힌 것을 본다',
 f'<p>허용을 물으면 실행하려는 명령이 <code>python 대조.py</code>인지 읽고 허용한다. 답이 오면 후보 파일에서 <code>"검토"</code>를 찾아(Ctrl+F) 넘겨 본다. 아래 표의 오른쪽 칸과 같아야 한다. 승인 {n_ok4}건에는 바로 아래에 <code>"검토자"</code>가 붙어 있고, 대기 {len(wait4)}건에는 없다.</p>' + ctable
 + ifs(('대기여야 할 것까지 승인으로 바뀌었다면', '「K-007 과 K-008 의 검토를 대기로 되돌리고 검토자 칸을 지워 줘. 내가 승인이라고 말한 번호만 승인이다」라고 말한다.'),
       ('대조 결과가 0건이 아니라면', '검토를 적다가 다른 칸이 바뀐 것이다. 어긋난 번호를 읽고, 무엇을 바꿨는지 물어 되돌리게 한다.')))
+ nxt(3, '3. 출처를 어디에 남길지 정하고, 계획부터 받는다', 1))

# ───────── 3단계
pages.append(hero('3단계', '출처를 어디에 남길지 정하고,<br>계획부터 받는다',
 '승인한 것을 넣기만 하면 되는 것 같지만, 정할 것이 남아 있다. 후보 파일의 출처는 칸 하나였는데 그래프에는 노드와 관계와 속성이 있다. 금지 조건은 어디에 담을지, 이미 있는 노드는 어떻게 할지, 관계의 근거는 어디에 적을지. 기준은 하나다. <b>넣은 뒤에 고장 유형에서 원문의 절까지 관계를 따라 되짚을 수 있어야 한다.</b>',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '몇 개가 새로 생기는지 적힌 계획이 채팅에 있다'), ('아직 없어야 하는 것', '반영.py, 반영.cypher')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '일곱 가지마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 맞는지를 고른다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 5단계의 질의는 가운데 칸의 답으로 만든 것이다. 2번과 3번을 다르게 정하면 5단계의 질의 가운데 <code>source</code>와 <code>kind</code>를 읽는 것이 내 그래프와 맞지 않게 된다. 3번은 온라인에서 본 「절차는 있는데 금지 조건이 없는 상태」를 막는 선택이다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 보내기 전에 그 번호의 줄만 고쳐 쓴다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'abc'))
 + parts(('무엇을 왜 만드는가', '첫 문단. 승인한 것만, 출처와 함께, 되짚을 수 있게. 그리고 문장을 파일로 먼저 받아 내가 읽고 내가 넣겠다고 했다.'), ('일곱 가지 결정', '번호를 붙여 한 줄에 결정 하나씩 적었다. 속성의 이름(<code>source</code>, <code>citation</code>, <code>kind</code>, <code>text</code>)까지 정해 주었다. 이름을 정해 주지 않으면 조회할 때 무엇을 읽어야 할지 알 수 없다.'), ('계획 먼저', '마지막 문단. 레이블과 유형별로 몇 개가 새로 생기는지를 미리 말하게 했다. 수를 알고 있어야 넣은 뒤에 맞는지 알 수 있다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 세 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 아래 수는 같은 요청으로 실제로 받은 계획의 것이다.</p>'
 + shot('3단계 요청에 대한 Copilot의 계획. 새로 생기는 노드와 관계의 수를 레이블과 유형별로 적은 표, 이미 있어 늘지 않는 것, 끝의 「더 정해 주셔야 하는 것」이 보이게. 수의 합계와 다시 물어 온 항목에 테두리를 얹는다.')
 + find(('새로 생기는 수', f'노드 {n1[4]}개, 관계 {n1[5]}개. 그래프 DB에 지금 노드 {gn}, 관계 {gr}이 있으므로 넣은 뒤에는 노드 {n1[2]}, 관계 {n1[3]}이 되어야 한다. 이 두 수를 적어 둔다. 내 검토가 다르면 수도 다르다.'),
        ('이미 있어서 늘지 않는 것', '쿨러 핀 오염과 팬 최대 운전 두 노드, 이미 있는 관계 둘. 이 넷을 <code>MERGE</code>로 새로 만들지 않고 <code>MATCH</code>로 찾아 덧붙이겠다고 하는가.'),
        ('다시 물어 온 것', '일곱 가지를 정해 주어도 빈자리가 더 나온다. 예: 문서에서 온 새 조치들이 고장 유형에서 닿지 않는데 그대로 둘지, 절의 제목에 절 번호를 넣을지, 같은 조치와 같은 절 사이에 관계가 둘 생기면 어떻게 구별할지. 다음 단계의 요청이 이 물음에 답한다.'))
 + ifs(('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('그래프 DB를 조회해 보겠다고 한다면', '허용하지 않는다. 규칙 파일은 그래프 DB에 닿는 일을 사람에게 맡겼다. 지금 들어 있는 수는 내가 준비 단계에서 본 것을 말해 주면 된다.')))
+ nxt(4, '4. 문장을 파일로 받아 읽고, 내가 넣는다', 2))

# ───────── 4단계
pages.append(hero('4단계', '문장을 파일로 받아 읽고,<br>내가 넣는다',
 '이제 만들게 한다. 다만 <b>만드는 일과 넣는 일을 가른다.</b> <code>python 반영.py</code>는 넣을 문장을 <code>결과/반영.cypher</code>에 쓰기만 하고 그래프 DB에는 닿지 않는다. 그 파일을 내가 읽은 다음 <code>python 반영.py 넣기</code>로 내가 보낸다. 넣기는 파일의 문장 전부를 한 번에 보내고, 한 문장이라도 실패하면 아무것도 들어가지 않는다.',
 [('걸리는 시간', '약 9분'), ('이 단계가 끝나면', f'그래프 DB에 노드 {n1[2]}, 관계 {n1[3]}이 들어 있다'), ('바뀌면 안 되는 것', '후보.json, 지난 시간의 노드의 id와 name')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 넣지는 말라고 한다',
 '<p>계획이 다시 물어 온 것은 아래 글에 정해 적어 두었다. 내 계획이 묻지 않은 줄이 섞여 있어도 그대로 보내면 된다. 프로그램 하나를 통째로 쓰므로 2~3분 걸린다.</p>'
 + copy(P4, pre=True, rich=richpre(P4, 'ab'))
 + parts(('받을 것과 내가 정한 다섯', '첫째 줄을 눈여겨본다. 고장 유형에 닿지 않는 조치를 지금 억지로 잇지 않았다. 근거 문장이 없어 보류한 관계를 넣는 사람이 지어 넣으면, 출처 없는 지식이 생긴다.'), ('범위', '파일 하나, 실행은 넣지 않는 쪽만. 넣기는 내가 한다고 다시 적었다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 명령을 읽고 허용한다',
 '<p>Copilot이 파일을 만들 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 실행하려는 명령이 <code>python 반영.py</code>(뒤에 아무것도 붙지 않은 것)인지 읽는다. 뒤에 <code>넣기</code>가 붙어 있거나 <code>그래프_준비.py</code>이면 허용하지 않는다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 반영.py)와 「허용/계속」 버튼이 보이게.'))
+ do(3, 'editor', 'VS Code · 편집기', '<code>결과/반영_요약.md</code>에서 수를 맞춘다',
 f'<p>미리 보기(Ctrl+Shift+V)로 연다. 맨 위에 넣는 번호와 넣지 않는 번호가 있다. 넣지 않는 것에 K-007과 K-008이 「대기」로 적혀 있는지 본다. 그 아래의 두 표가 3단계에서 적어 둔 수와 같은지 견준다. 아래는 실제로 만들어진 요약의 표다.</p>'
 + '<div class="chg"><div>' + t2(tn) + '</div><div>' + t2(tr) + '</div></div>')
+ do(4, 'editor', 'VS Code · 편집기', '<code>결과/반영.cypher</code>를 넣기 전에 읽는다',
 f'<p>문장이 {n_stmt4}개다. 다 읽지 않아도 된다. 아래 세 가지를 찾기(Ctrl+F)로 찾는다. AI가 만든 문장을 그래프 DB에 넣기 전에 읽는 것은 넣는 사람의 일이다.</p>'
 + '<p>새 노드를 만드는 문장은 이렇게 생겼다. 팬 최대 운전의 2단계다.</p>' + cyq(blk, ['MERGE (n:Step {id: \'step:fan-maximum-run/2\'})', 'n._manual_document = \'HM-8\'', 'MERGE (a)-[r:HAS_STEP]-&gt;(b)', 'MERGE (a)-[r:REFERS_TO]-&gt;(b)'])
 + '<p style="margin-top:14px">그래프에 이미 있는 노드는 이렇게 다룬다. 팬 최대 운전 자신이다.</p>' + cyq(blk_old, ['MATCH (a:Skill {id: \'skill:fan-maximum-run\'})'])
 + find(('<code>MERGE</code>의 괄호 안에 id만 있는가', '<code>MERGE (n:Step {id: …})</code>처럼 레이블과 id만 있고 나머지 속성은 <code>SET</code>에 있다. 이래야 같은 문장을 두 번 넣어도 노드가 하나다. <code>CREATE</code>는 파일에 없어야 한다.'),
        ('이미 있는 노드를 새로 만들지 않는가', '<code>skill:fan-maximum-run</code>과 <code>cause:cooler-fin-fouling</code>을 찾는다. <code>MERGE (n:Skill {id: …})</code>가 아니라 <code>MATCH</code>로만 나오고, <code>name</code>을 <code>SET</code>하는 줄이 없어야 한다.'),
        ('넣지 않기로 한 것이 없는가', '<code>cooler-fin-cleaning</code>(쿨러 핀 세척)과 <code>cabinet-ventilation</code>(캐비닛 환기 보강)을 찾는다. 나오지 않아야 한다. <code>DELETE</code>도 찾아본다.'))
 + note('_manual_document', '새로 만드는 노드와 관계마다 <code>_manual_document = \'HM-8\'</code>이 붙어 있다. 어느 문서의 반영이 만든 것인지를 남기는 표시다. 이미 있던 노드에는 붙지 않는다. 이 표시가 있어야 나중에 이 문서에서 온 것만 골라 보거나 되돌릴 수 있다.'))
+ do(5, 'term', 'VS Code · 터미널', '내 손으로 넣는다',
 '<p>터미널에 아래 명령을 넣는다. 이 한 줄이 오늘 그래프 DB를 바꾸는 유일한 명령이다.</p>' + tcopy('python 반영.py 넣기')
 + '<p style="margin-top:18px">아래는 같은 파일을 실제로 넣었을 때의 출력이다. 「보낸 뒤」의 수가 3단계에서 적어 둔 수와 같은지 본다.</p>' + outbox('4_넣기_출력.txt', [f'노드 {n1[2]}, 관계 {n1[3]}'])
 + ifs(('「멈춤: 그래프 DB 에 보내지 않았다」고 나오면', '넣기 전의 세 가지 확인 가운데 하나에 걸린 것이다. 까닭이 함께 적혀 있다. 대조 결과가 0건이 아니면 2단계로, 지우는 문장이 있다면 누가 넣었는지부터 본다.'),
       ('「멈춤: Neo.ClientError…」처럼 오류가 나오면', '문장 하나가 그래프 DB에서 실패한 것이고, 아무것도 들어가지 않았다. 오류 글을 그대로 복사해 Copilot에게 붙여 주고 「반영.py 를 고쳐 반영.cypher 를 다시 만들어 줘」라고 말한다. 고친 뒤 다시 넣는다.'),
       ('수가 계획과 다르다면', '「보내기 전」이 노드 ' + str(gn) + ', 관계 ' + str(gr) + '이 아니었다면 준비 단계의 <code>python 그래프_준비.py</code>를 다시 실행한 뒤 넣는다. 처음 상태로 돌아간다.')))
+ nxt(5, '5. 고장 유형에서 원문의 절까지 따라가 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '고장 유형에서<br>원문의 절까지 따라가 본다',
 '넣었다는 출력만으로는 바르게 들어갔는지 알 수 없다. 넣은 사람이 그래프에서 직접 조회한다. 보는 것은 셋이다. 문서에서 온 것이 <b>지난 시간의 그래프에 이어졌는가</b>, 조치와 원인에서 <b>출처까지 되짚을 수 있는가</b>, <b>금지 조건이 조치와 함께</b> 들어갔는가. 질의는 준비되어 있다. 읽을 것은 결과다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '고장 유형에서 문서까지 이어진 길을 그림과 표로 보았다'), ('쓰는 곳', 'Neo4j Browser')])
+ nbmap('이 단계에서 쓰는 곳', '<p>준비 단계에서 열어 둔 <b>Neo4j Browser</b>다. 맨 위의 <b>입력 칸</b>에 질의를 붙여넣고 실행하면 아래에 <b>결과 틀</b>이 쌓인다. 결과 틀의 왼쪽에서 그래프로 볼지 표로 볼지를 고른다.</p>')
+ do(1, 'web', 'Neo4j Browser', '고장 유형에서 문서까지의 길을 그림으로 본다',
 '<p>아래 질의는 고장 유형에서 출발해 조치, 작업 단계, 매뉴얼 절을 거쳐 문서에 닿는 길을 통째로 돌려준다. 결과가 그래프로 그려진다.</p>' + qcopy(Q('q3p.cypher'))
 + shot('위 질의의 결과를 그래프 보기로 연 Neo4j Browser 화면. 고장 유형 「쿨러 냉각 성능 상실」에서 팬 최대 운전, 작업 단계 셋, 절 HM-8.5, 문서 HM-8까지 이어진 노드와 관계의 이름(MITIGATED_BY, HAS_STEP, REFERS_TO, PART_OF)이 보이게. 작업 단계 하나를 눌러 오른쪽에 citation 속성이 보이면 더 좋다.')
 + '<p style="margin-top:14px">같은 길을 표로 보면 이렇다. 아래 질의를 넣고 결과를 표로 본다. 결과는 실제로 실행해 나온 것이다.</p>' + qcopy(Q('q3.cypher')) + rtable('q3_처음_반영_뒤.out', mark=['24시간 이내'])
 + find(('길이 지난 시간의 그래프에서 시작하는가', '고장 유형과 팬 최대 운전, 그 사이의 <code>MITIGATED_BY</code>는 지난 시간에 넣은 것이다. 거기에 오늘 넣은 작업 단계와 절과 문서가 이어졌다. 문서의 지식이 따로 떠 있지 않고 기존 그래프에 보강된 것이다.'),
        ('인용이 원문의 줄 그대로인가', '「24시간 이내」가 든 줄이 2단계에서 원문과 나란히 읽은 그 줄인가. 조치 방법을 본 사람이 「이 단계는 어디에 적혀 있나」를 물으면 절과 문서를 관계로 답할 수 있다.'),
        ('조치가 하나뿐이다', '문서에서 조치를 셋 넣었는데 이 길에는 팬 최대 운전만 나온다. 왜 그런지는 8단계에서 조회해 본다.')))
+ do(2, 'web', 'Neo4j Browser', '원인의 출처와 금지 조건을 조회한다',
 '<p>원인 쪽이다. 관계의 속성에 남긴 출처(<code>source</code>)와, 원인 노드가 가리키는 절을 함께 읽는다.</p>' + qcopy(Q('q2.cypher')) + rtable('q2_처음_반영_뒤.out', cols=['원인', '관계의_출처', '절', '절_제목'])
 + '<p style="margin-top:18px">원인 셋 가운데 「쿨러 핀 오염」은 지난 시간부터 있던 노드이고 관계도 있었다. 오늘은 그 관계에 출처만 더해졌다. 다음은 금지 조건이다.</p>' + qcopy(Q('q4.cypher')) + rtable('q4_처음_반영_뒤.out', mark=['아닐 때'])
 + '<p style="margin-top:14px">세 조치에 같은 금지가 붙어 있고 모두 HM-8.8을 가리킨다. 절차가 들어가면서 금지 조건도 함께 들어갔다.</p>')
+ do(3, 'web', 'Neo4j Browser', '무엇이 보강되었는지 수로 본다',
 '<p>레이블마다 노드가 몇 개이고 그 가운데 몇 개가 문서에서 왔는지를 센다.</p>' + qcopy(Q('q1.cypher'))
 + f'<p style="margin-top:18px">실제 결과에서 문서에서 온 것이 있는 레이블은 ' + ', '.join(f'{k} {v}' for k, v in new_by.items()) + f'이고 합이 {sum(new_by.values())}이다. 4단계의 요약과 같은 수다. Cause와 Skill은 전체가 3인데 문서에서 온 것은 2다. 나머지 하나씩이 지난 시간부터 있던 쿨러 핀 오염과 팬 최대 운전이다. 설비, 구성 요소, 센서 같은 레이블은 0이다. 문서는 설비의 구조를 새로 알려 주지 않았다.</p>'
 + ifs(('결과가 한 줄도 나오지 않는다면', '3단계에서 2번이나 3번을 다르게 정했다면 <code>source</code>, <code>kind</code>라는 속성이 내 그래프에 없다. 내가 정한 이름으로 질의를 고쳐 실행한다. 그대로 보냈는데도 비어 있다면 <code>결과/반영.cypher</code>에서 그 속성을 찾아본다.'),
       ('그래프가 그려지지 않고 글자만 나온다면', '결과 틀의 왼쪽에서 그래프 보기를 고른다. 노드에 이름이 보이지 않으면 노드를 눌러 오른쪽의 속성에서 <code>name</code>, <code>text</code>, <code>ref</code>를 읽는다.')))
+ nxt(6, '6. 규칙을 일부러 건드려 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 그래프에 넣는 일을 하다 보면 두 가지 유혹이 온다. 검토를 다 못 했지만 틀린 곳은 없을 테니 <b>마저 넣자</b>는 것과, 꼬인 것 같으니 <b>싹 비우고 다시 넣자</b>는 것이다. 둘 다 지금 일부러 요청해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '후보.json, 반영.cypher, 그래프 DB')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '승인하지 않은 후보를 넣어 달라고 해 본다',
 '<p>대조 프로그램이 0건이라고 했다는 그럴듯한 근거를 댄 요청이다.</p>'
 + copy(P6a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 반영.cypher를 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법(원문과 대조한 뒤 번호를 짚어 승인)을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '<code>결과/반영.cypher</code>에서 <code>cooler-fin-cleaning</code>을 찾는다. 여전히 나오지 않아야 한다. <code>결과/후보.json</code>의 K-007과 K-008도 대기 그대로인지 본다.'),
        ('대조 0건을 어떻게 받았는가', '대조 프로그램이 보는 것은 인용이 원문에 있는지까지이고, 뜻이 같은지는 사람이 읽어야 한다는 말을 했는가.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고, 규칙 안에서 같은 목적을 이루는 길(HM-8.7을 원문과 대조한 뒤 번호를 짚어 승인한다)을 내놓았는가.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '그래프 DB를 비우고 다시 넣자고 해 본다',
 '<p>이번에는 그래프 DB 쪽을 건드린다. 실습용 그래프 DB이니 지워도 될 것 같다. 그런데 이 문장이 든 파일이 다른 그래프 DB에서 실행되면 그곳의 지식이 모두 지워진다.</p>'
 + copy(P6b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>결과/반영.cypher</code>의 맨 앞을 본다. <code>DETACH DELETE</code>가 없어야 한다. Copilot이 대신 내놓은 길이 무엇인지도 읽는다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 한 줄이다. 검토가 승인이 아닌 후보를 어떻게 하라고 적혀 있는가. 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 한 줄이다. 처음부터 다시 넣고 싶다는 요청에는 무엇으로 답하라고 적혀 있는가. 몇 번인가.</li><li><b>두 답에 함께 나올 수 있는 줄</b>「채팅에서 요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('승인을 건너뛰면 안 되는 까닭', '추출이 끝난 시점에 지식 그래프는 조금도 바뀌어 있지 않다. 사람이 승인해야 들어간다. 첫째 요청을 들어주었다면 아무도 원문과 대조하지 않은 단계가 출처까지 단 채 그래프에 들어갔을 것이다. 출처가 붙어 있으면 검토된 지식처럼 보인다. 그래서 더 위험하다. 둘째 요청은 4단계에서 정한 「넣기 전의 확인」에도 걸린다. 지우는 문장이 든 파일은 넣기가 보내지 않는다.')
 + ifs(('멈추지 않고 넣는 문장을 만들었다면', '아직 그래프 DB에는 들어가지 않았다. 넣는 것은 나이기 때문이다. 「방금 고친 것을 되돌려 줘」라고 말하고, 규칙 파일을 다시 읽어 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 승인하지 않은 것을 넣어도 된다고 말할 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(7, '7. 하나를 더 승인해, 다시 넣는다', 5))

# ───────── 7단계
pages.append(hero('7단계', '하나를 더 승인해,<br>다시 넣는다',
 '검토는 한 번에 끝나지 않는다. 오늘 읽은 것만 승인하고, 내일 더 읽어 더 넣는다. 그때마다 이미 넣은 것이 둘이 되면 그래프는 쓸 수 없게 된다. <b>같은 것을 다시 넣어도 늘지 않고, 새로 승인한 것만 늘어야 한다.</b> 두 가지를 차례로 해 본다. 아무것도 바꾸지 않고 한 번 더 넣고, 그다음 후보 하나를 더 승인해 넣는다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', f'그래프 DB에 노드 {n7[2]}, 관계 {n7[3]}이 들어 있고, 같은 id의 노드는 하나씩이다'), ('바뀌면 안 되는 것', '반영.py')])
+ do(1, 'term', 'VS Code · 터미널', '아무것도 바꾸지 않고 한 번 더 넣는다',
 '<p>돌리기 전에 짐작해 둔다. 노드가 몇 개가 될까.</p>' + tcopy('python 반영.py 넣기')
 + '<p style="margin-top:18px">아래는 실제 출력이다. 문장은 처음과 똑같이 모두 보냈는데 새로 생긴 노드와 관계가 0이다. <code>MERGE</code>는 이미 있으면 찾기만 하고, 없을 때만 만든다. 속성의 수는 0이 아니다. 같은 값을 다시 적은 것이다.</p>' + outbox('4_넣기_다시_출력.txt', ['노드 0, 관계 0']))
+ do(2, 'editor', 'VS Code · 편집기 (좌우로 나란히)', 'HM-8.7의 SOP-COOL-14를 원문과 나란히 읽는다',
 f'<p>2단계에서 남겨 둔 K-007(쿨러 핀 세척)을 읽는다. <code>결과/후보.json</code>에서 <code>K-007</code>을 찾고, 원문에서 <code>SOP-COOL-14</code>를 찾아 나란히 둔다. 단계가 {len(C["K-007"]["단계"])}개이고 순서가 같은가. 「{e(C["K-007"]["단계"][1]["내용"].split(". ")[1])}」의 부정이 살아 있는가. 「80 % 이상」의 수와 단위가 같은가.</p>')
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', 'K-007만 승인으로 적고, 문장을 다시 만들게 한다',
 '<p>「한지우」를 내 이름으로 고쳐 보낸다. K-008은 읽지 않았으므로 그대로 둔다. 지금 그래프 DB에 든 수를 내가 알려 준다. Copilot은 그래프 DB를 보지 못하기 때문이다.</p>'
 + copy(P7) + '<p style="margin-top:18px">답에서 넣은 뒤의 수를 읽어 적어 둔다. 같은 요청으로 실제로 받은 답은 노드 ' + str(n7[2]) + ', 관계 ' + str(n7[3]) + '이었다.</p>')
+ do(4, 'term', 'VS Code · 터미널 → Neo4j Browser', '다시 넣고, 둘이 된 것이 없는지 조회한다',
 '<p><code>결과/반영_요약.md</code>에서 넣지 않는 것이 K-008 하나로 줄었는지 먼저 본다. 그다음 넣는다.</p>' + tcopy('python 반영.py 넣기')
 + f'<p style="margin-top:18px">아래는 실제 출력이다. 문장은 {n_stmtF}개를 모두 보냈는데 새로 생긴 것은 K-007의 몫뿐이다.</p>' + outbox('7_넣기_출력.txt', [f'노드 {n7[4]}, 관계 {n7[5]}'])
 + '<p style="margin-top:18px">Neo4j Browser에서 같은 id를 가진 노드가 둘 이상인지 조회한다. 한 줄도 나오지 않아야 한다. 실제로 실행했을 때도 결과가 없었다.</p>' + qcopy(Q('q6.cypher'))
 + find(('새로 생긴 것이 K-007의 몫인가', f'노드 {n7[4]}개는 조치 하나, 작업 단계 {len(C["K-007"]["단계"])}개, 절 HM-8.7 하나다. 문서 HM-8은 이미 있어 늘지 않았다.'),
        ('앞에서 넣은 것이 그대로인가', '5단계의 질의 가운데 하나를 다시 실행해 본다(입력 칸에서 위쪽 화살표를 누르면 앞의 질의가 나온다). 팬 최대 운전의 단계가 여전히 셋인가.'))
 + ifs(('새로 생긴 것이 0이라면', '<code>python 반영.py</code>가 다시 실행되지 않아 <code>결과/반영.cypher</code>가 예전 그대로인 것이다. 파일에서 <code>cooler-fin-cleaning</code>을 찾아보고, 없으면 Copilot에게 다시 만들어 달라고 한다.'),
       ('같은 id가 둘 나왔다면', '<code>결과/반영.cypher</code>에서 그 id를 찾아 <code>MERGE</code>의 괄호 안에 id 말고 다른 속성이 들어 있는지 본다. 찾은 것을 Copilot에게 말해 고치게 하고, <code>python 그래프_준비.py</code>로 처음 상태로 돌린 뒤 다시 넣는다.')))
+ nxt(8, '8. 조회에서 본 아쉬운 곳을 되돌려 준다', 6))

# ───────── 8단계
pages.append(hero('8단계', '조회에서 본 아쉬운 곳을,<br>무엇이 왜 문제인지 말한다',
 '5단계의 길에는 조치가 팬 최대 운전 하나뿐이었다. 문서에서 넣은 다른 조치들은 어디에 있는가. 먼저 조회해 확인한다. 그다음 이 사실을 <b>넣기 전에</b> 알 수 있었어야 한다는 것을 프로그램에 되돌려 준다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '반영.py의 한 곳이 내 요청대로 바뀌어 있다')])
+ do(1, 'web', 'Neo4j Browser', '고장 유형에 이어지지 않은 조치를 조회한다',
 '<p>어느 고장 유형에서도 <code>MITIGATED_BY</code>로 이어지지 않는 조치를 찾는다.</p>' + qcopy(Q('q5.cypher')) + rtable('q5_K-007_반영_뒤.out')
 + f'<p style="margin-top:14px">실제 결과다. 문서에서 넣은 조치 {len(r5)}개가 모두 나온다. 절과 문서로는 이어져 있지만, 고장 유형에서 따라가면 닿지 않는다. 지난 실습에서 「이 조치가 어느 고장 유형을 완화하는지 적은 문장이 없다」며 보류한 관계가 바로 이것이다. 틀린 것이 들어간 것은 아니다. 다만 넣는 사람은 이것을 넣기 전에 알았어야 한다.</p>')
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>' + e(P('8_bad_prompt.txt')) + '</q>무엇이 부족한지 AI는 모른다. 짐작으로 여럿을 더하거나, 무엇을 더할지를 되묻는다. 어느 쪽이든 한 번 더 주고받아야 한다.</div>'
  '<div class="good"><b>구체적으로</b><q>넣은 뒤 조회해 보니 문서에서 온 조치 셋이 고장 유형에 이어져 있지 않았어. 요약에는 수만 있어서 넣기 전에는 알 수 없었어. 요약의 끝에 「고장 유형에서 닿지 않는 조치」를 번호, 이름, 까닭으로 모아 줘. 요약을 쓰는 부분만 고치고, 반영.cypher 의 문장과 넣기는 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>조치 셋이 고장 유형에서 닿지 않는다</div><div><b>왜</b>요약에 수만 있어 넣기 전에 알 수 없었다</div><div><b>어디를</b>반영.py에서 요약 md를 쓰는 부분</div><div><b>어디까지</b>반영.cypher의 문장, 넣기는 그대로</div></div></section>'
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 내가 조회에서 본 조치의 이름을 그대로 적는다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 「반영.cypher 의 문장은 건드리지 마」를 꼭 넣는다.</p>'
 + write('w8', '조회에서 무엇을 보았는지, 왜 문제인지, 반영.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P8, pre=True) + '</details>'
 + '<p style="margin-top:18px">고친 뒤에는 <code>결과/반영_요약.md</code>를 다시 연다. 완성 폴더의 요약에는 끝에 아래 절이 생겼다. 까닭은 지난 실습의 보류에 적힌 글이 그대로 옮겨진 것이다.</p>' + t2(far)
 + shot('되돌려 준 뒤 Copilot이 반영.py의 바뀐 부분을 보여 주는 화면(새로 생긴 줄이 초록색으로 표시되고, 문장을 만드는 부분은 바뀌지 않은 것이 보이게).')
 + find(('문장은 그대로인가', f'터미널에서 <code>python 반영.py 넣기</code>를 한 번 더 실행한다. 요약만 고쳤다면 「새로 생긴 것: 노드 0, 관계 0」이고 그래프 DB는 노드 {n7[2]}, 관계 {n7[3]} 그대로다.'),
        ('이 표를 보고 무엇을 할 것인가', '세 조치를 고장 유형에 이을지는 넣는 사람이 정할 수 없다. 근거가 되는 문장이 문서에 있어야 한다. 문서를 관리하는 쪽에 「HM-8.5의 조치가 어느 고장 유형의 것인지 한 줄이 필요하다」고 알리는 것이 이 표의 쓰임이다.'))
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>남은 하나를 마저 읽고 승인한다.</b> 원문에서 SOP-COOL-15를 찾아 K-008(캐비닛 환기 보강)과 나란히 읽은 다음, 아래를 내 이름으로 고쳐 보낸다. 다시 넣으면 무엇이 늘고 무엇이 늘지 않는지 먼저 짐작해 본다.</p>'
  + copy(PXa)
  + f'<p style="margin-top:18px">실제로 해 보면 노드 {nx[4]}, 관계 {nx[5]}가 늘어 노드 {nx[2]}, 관계 {nx[3]}이 된다. 절 HM-8.7은 K-007 때 이미 들어가 있어 늘지 않는다. 「고장 유형에서 닿지 않는 조치」는 넷이 된다. 완성 폴더에는 K-007까지만 들어 있다.</p>'
  '<p><b>넣는 일도 대신 해 달라고 해 본다.</b> 6단계에서 건드리지 않은 줄이 하나 더 있다. 아래를 보내고, Copilot이 규칙 파일의 어느 줄을 들었는지, 번거로움을 줄이는 길로 무엇을 내놓았는지 본다.</p>'
  + copy(P6c, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
  + '<p style="margin-top:18px"><b>문장 하나를 깨뜨려 넣어 본다.</b> 넣기는 문장 전부를 한 번에 보내고, 하나라도 실패하면 아무것도 넣지 않는다고 했다. 정말 그런지 본다. 먼저 <code>python 그래프_준비.py</code>로 그래프 DB를 처음 상태(노드 ' + str(gn) + ', 관계 ' + str(gr) + ')로 돌린다. 그다음 <code>결과/반영.cypher</code>의 아래쪽에서 <code>MERGE</code> 하나를 <code>MERG</code>로 고쳐 저장하고 넣는다. 실제로 해 보면 아래처럼 멈춘다.</p>'
  + f'<div class="out">{e(once.splitlines()[0][:118])} …</div>'
  + f'<p>Neo4j Browser에서 준비 단계의 질의로 수를 센다. 그 앞의 문장들은 멀쩡했는데도 노드 {gn}, 관계 {gr} 그대로다. 절차는 들어갔는데 금지 조건은 빠진 상태가 생기지 않는다. 끝나면 <code>python 반영.py</code>로 파일을 다시 만들고 <code>python 반영.py 넣기</code>로 다시 넣는다.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 읽고 가르게 한다', '2. 검토를 적는다', '3. 정하고 계획 받기', '4. 만들고, 읽고, 넣기', '5. 관계를 따라 조회하기', '6. 규칙을 건드려 보기', '7. 하나 더 승인해 다시 넣기', '8. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>검토한 후보 → 그래프 DB</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-04-3-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. 상자 아래에 적힌 곳에 붙여넣으세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 검토한 지식을 그래프 DB에 반영하기</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
for bad in ('7475', '7688', '/Users/', '/private/tmp', '가상', '시뮬레이션'):
    assert bad not in doc, bad
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창과 웹 브라우저 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
