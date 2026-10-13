"""통합반 오프라인 07회차 실습 4 「새 기능과 기존 기능을 함께 검증하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '07회차_실습4_시나리오_회귀_검증'
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
.tree span{color:#8fb4ff}.tree i{color:#8a94a3;font-style:normal}
table.res{width:100%;border-collapse:collapse;font-size:14.5px;line-height:1.6;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid var(--line);margin:18px 0 8px}
table.res th{background:#eef1f5;text-align:left;padding:10px 14px;font-size:13px}
table.res td{padding:10px 14px;border-top:1px solid var(--line);vertical-align:top}
table.res mark{background:#fff1a8;padding:0 3px;border-radius:3px}
table.res td.nw{white-space:nowrap}
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
.four{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}
.four div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px}
.four b{display:block;color:var(--accent);font-size:15.5px}
.pipe{display:grid;grid-template-columns:1fr 28px 1fr 28px 1fr;gap:8px;align-items:stretch;margin:18px 0 6px}
.pipe div{background:#f6f8fa;border:1px solid var(--line);border-radius:14px;padding:16px 16px;font-size:14.5px;line-height:1.6}
.pipe div.out{background:var(--accent-soft);border-color:#c5d3fb}
.pipe b{display:block;font-size:16px;margin-bottom:4px}
.pipe small{display:block;font-family:Consolas,"D2Coding",monospace;font-size:12.5px;color:var(--sub);margin-top:6px}
.pipe span{align-self:center;text-align:center;font-size:22px;color:var(--faint);font-weight:800}
.axis{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px 6px;margin:18px 0 8px}
.axis svg{width:100%;height:auto;display:block}
.next a,.back{cursor:pointer}
table.res td.c1{width:150px}
table.res td small{color:var(--sub);font-size:13px}
.st{display:inline-block;border-radius:6px;padding:1px 8px;font-size:12.5px;font-weight:800;font-family:Consolas,"D2Coding",monospace}
.st.s{background:var(--ok-soft);color:var(--ok)}.st.u{background:#fff1a8;color:#7a5b00}.st.x{background:#fdecec;color:#b3261e}
.path{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px 8px;margin:18px 0 8px}
.path svg{width:100%;height:auto;display:block}
.grow{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}
.grow div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px;line-height:1.6}
.grow div.on{background:var(--accent-soft);border-color:#c5d3fb}
.grow b{display:block;font-size:15.5px;margin-bottom:4px}
.grow code{font-size:13px}
.chg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}
.chg .tree{font-size:14px;line-height:1.8;padding:14px 18px}
.chg .tree b{color:#ffd76a}
.hist{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:18px 0 8px}
.hist div{border-radius:14px;padding:12px 12px;font-size:13.5px;line-height:1.55;border:1px solid var(--line);background:var(--card)}
.hist div.good{border-top:5px solid var(--ok)}.hist div.bad{border-top:5px solid #b3261e;background:#fdecec}
.hist div.off{opacity:.38}
.hist small{display:block;font-size:11.5px;color:var(--sub);font-weight:700;margin-bottom:4px}
.hist b{display:block;font-size:15px}
@media(max-width:760px){.hist{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.flow,.vs,.four,.pipe,.chg,.grow{grid-template-columns:1fr}table.res{display:block;overflow-x:auto}.pipe span{display:none}}
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 시나리오 열두 편(검증/시나리오.feature)과 실행하는 프로그램, 통과와 실패가 차례로 적힌 검증 이력. 기능을 바꿀 때마다 이 열두 편을 다시 실행한다</b></div></div>'
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
q = lambda t: re.sub(r'`([^`]+)`', r'<code>\1</code>', e(t))

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1 = P('1_prompt.txt')
P1rich = ('<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 spec.md, 요청_처리.py, 검증 폴더의 시나리오.json, 사람 폴더의 쓰는_법.md 를 읽어 줘.</span> '
          '<span class="p-b">시나리오.json 의 여섯 건을 한 건씩 놓고, 그 건을 실행하면 spec.md 의 금지 조건 열여덟 줄 가운데 어느 줄이 확인되는지 표로 적어 줘. 여섯 건으로는 확인되지 않는 금지 조건도 가려 줘. 그다음 정상, 긴급, 미입력, 거절 네 경우에서 한 건씩 골라 Given, When, Then 으로 말로 적어 줘. 적다가 spec.md 와 이 폴더의 규칙만으로는 정할 수 없는 것이 나오면 정하지 말고, 내가 무엇을 정해 줘야 하는지 물어 줘.</span> '
          '<span class="p-c">아직 파일은 만들지 말고 아무것도 실행하지 마.</span>')
assert re.sub(r'<[^>]+>', '', P1rich) == P1
P2, P3, P4, P5a, P5b, P5c, P6, P7a, P7b, P8, P9 = (P(f'{n}_prompt.txt') for n in ('2', '3', '4', '5a', '5b', '5c', '6', '7a', '7b', '8', '9'))

# ── 시작 폴더의 자료에서 읽는 수
J = lambda p: json.loads((R / p).read_text(encoding='utf-8'))
REQ, SC, RES = J('시작/입력/점검_요청.json'), J('시작/검증/시나리오.json'), J('시작/결과/요청_처리.json')
SPEC = (R / '시작' / 'spec.md').read_text(encoding='utf-8')
forbid = re.findall(r'(?m)^(\d+)\. (.*)$', SPEC.split('## 금지 조건')[1].split('## 수용 기준')[0])
n_req, n_sc, n_forbid, n_ac = len(REQ), len(SC), len(forbid), len(re.findall(r'(?m)^- AC-\d+\.', SPEC))
assert (n_req, n_sc, n_forbid, n_ac) == (10, 6, 18, 50)
assert [(s['경우'], s['요청']) for s in SC] == [('정상', 'R05'), ('긴급', 'R03'), ('긴급', 'R04'), ('미입력', 'R01'), ('미입력', 'R08'), ('거절', 'R07')]
f11 = dict(forbid)['11']
assert f11.startswith('긴급이라는 것으로 승인을 대신하지 않는다')
for f in ('요청_처리.py', 'spec.md', '긴급_기준.json', '사람/답변.json', '사람/승인.json', '입력/점검_요청.json', '결과/요청_처리.json'):
    assert (R / '시작' / f).read_bytes() == (R / '완성' / f).read_bytes(), f   # 끝까지 고쳐지지 않았다

# ── 실제로 실행한 결과 파일에서 옮기는 줄
r3, r4, r6, r7, fin = J('기록/3_검증_결과.json'), J('기록/4_검증_결과.json'), J('기록/6_검증_결과.json'), J('기록/7a_검증_결과.json'), J('완성/결과/검증_결과.json')
assert [x['결과'] for x in r3] == ['통과'] * 6 and [x['결과'] for x in r4] == ['통과'] * 11 and [x['결과'] for x in r6] == ['통과'] * 12
assert [x['결과'] for x in r7] == ['통과'] * 11 + ['실패'] and [x['결과'] for x in fin] == ['통과'] * 12
ok = lambda v: f'<span class="st {"s" if v == "통과" else "x" if v == "실패" else "u"}">{v}</span>'
def runtable(d, start=0):
    return ('<table class="res"><thead><tr><th style="width:44px">#</th><th style="width:120px">경우 · 요청</th><th>이름에 적힌 행동</th><th style="width:76px">문장</th><th style="width:76px">결과</th></tr></thead><tbody>'
            + ''.join(f'<tr><td>{i}</td><td class="nw"><b>{e(x["시나리오"].split(" - ")[0])}</b></td><td>{e(x["시나리오"].split(" - ", 1)[1])}</td><td class="nw">{len(x["단계"])}줄</td><td class="nw">{ok(x["결과"])}</td></tr>' for i, x in enumerate(d, 1) if i > start)
            + '</tbody></table>')
bad = r7[-1]
badtable = ('<table class="res"><thead><tr><th style="width:70px">구분</th><th style="width:44%">문장</th><th style="width:96px">결과</th><th>실제</th></tr></thead><tbody>'
            + ''.join(f'<tr><td class="nw">{e(s["구분"])}</td><td>{e(s["문장"])}</td><td class="nw">{ok(s["결과"])}</td><td>{e(s["실제"]).replace(" / ", "<br>") if s["실제"] else "—"}</td></tr>' for s in bad['단계']) + '</tbody></table>')
failstep = next(s for s in bad['단계'] if s['결과'] == '실패')
assert 'R04.상태: "승인_대기" → "확정"' in failstep['실제'] and [s['결과'] for s in bad['단계']].count('실행_안_함') == 2

hist = [[c.strip() for c in l.strip().strip('|').split('|')] for l in (R / '완성' / '결과' / '검증_이력.md').read_text(encoding='utf-8').splitlines()[2:] if l.strip()]
assert [h[:4] for h in hist] == [['1', '6', '6', '0'], ['2', '11', '11', '0'], ['3', '12', '12', '0'], ['4', '12', '11', '1'], ['5', '12', '12', '0'], ['6', '12', '12', '0']]
HL = ['3단계. 여섯 편', '4단계. 겹친 경우 다섯 편을 더함', '6단계. 회귀 편을 더함', '7단계. 승인 한 건을 써 넣은 뒤', '7단계. 그 줄을 지운 뒤', '8단계. 표를 더한 뒤']
def histrow(upto):
    return '<div class="hist">' + ''.join(
        f'<div class="{"bad" if h[3] != "0" else "good"}{"" if i < upto else " off"}"><small>차례 {h[0]} · {HL[i]}</small><b>{h[1]}편 실행</b>통과 {h[2]} · 실패 {h[3]}</div>' for i, h in enumerate(hist)) + '</div>'

mdtop = (R / '완성' / '결과' / '검증_결과.md').read_text(encoding='utf-8').split('## 금지 조건마다 확인하는 편')[1].split('\n## ')[0]
cover = [[c.strip() for c in l.strip().strip('|').split('|')] for l in mdtop.strip().splitlines() if re.match(r'\| \d+ \|', l)]
assert len(cover) == 18
none = [c[0] for c in cover if c[1] == '시나리오 없음']
assert none == ['4', '5', '6', '10', '16', '17']
fb = dict(forbid)
def cut(t, n=44): t = re.sub(r'`', '', t); return t if len(t) <= n else t[:n] + '…'
covertable = ('<table class="res"><thead><tr><th style="width:52px">금지</th><th>명세에 적힌 줄 (앞부분)</th><th style="width:230px">확인하는 편</th></tr></thead><tbody>'
              + ''.join(f'<tr><td class="nw"><b>{c[0]}</b></td><td>{e(cut(fb[c[0]]))}</td><td>{"<mark>시나리오 없음</mark>" if c[1] == "시나리오 없음" else str(len(c[1].split("<br>"))) + "편 · 모두 통과"}</td></tr>' for c in cover)
              + '</tbody></table>')
assert all('실패' not in c[1] for c in cover)

approve_line = [l for l in (R / '기록' / '7_사람이_고친_승인.json').read_text(encoding='utf-8').splitlines() if '"R04"' in l]
assert len(approve_line) == 1
APPROVE = approve_line[0].strip()

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>Then에 적는 것</b></td><td><mark>1번 줄</mark> 기대의 네 칸을 적고, 일어나지 않아야 하는 일도 함께 적는다. 확정이 아닌 건에는 「상태는 확정이 아니다」를, 반영한 결정이 없는 건에는 「승인 칸은 비어 있다」를 적는다. 질문의 선택지는 수용 기준에 문장이 있는 건만 적는다</td><td>「기대의 네 칸만 적는다」로 바꾼다. 시나리오가 짧아지지만, 질문을 한 번에 둘 내는 잘못이나 승인 칸에 엉뚱한 것이 적히는 잘못은 네 칸으로는 드러나지 않는다. 금지 조건은 일어나지 않아야 하는 일을 적어야 확인된다</td></tr>
<tr><td><b>주어진 것을 Given으로 옮기는 법</b></td><td><mark>2번 줄</mark> 요청에 적힌 것, 사람의 답, 사람의 결정, 긴급을 가르는 값을 모두 문장으로 옮긴다. 요청과 센서 값은 지금의 입력과 같은지 확인하고, 다르면 그 문장을 실패로 적는다</td><td>「답과 결정만 옮기고 값은 적지 않는다」로 바꾼다. 문장이 줄지만, 누가 입력의 유온 값을 바꾸었을 때 긴급이 달라진 까닭이 프로그램인지 입력인지를 결과만 보고는 가릴 수 없다</td></tr>
<tr><td><b>한 문장이 실패했을 때</b></td><td><mark>3번 줄</mark> 그 시나리오의 남은 문장은 실행하지 않고 <code>실행_안_함</code>으로 적는다. 다른 시나리오는 끝까지 실행한다</td><td>「첫 실패에서 전부 멈춘다」로 바꾼다. 빨리 끝나지만 실패가 한 군데인지 여러 군데인지를 한 번에 알 수 없다</td></tr>
<tr><td><b>뜻을 모르는 문장</b></td><td><mark>4번 줄</mark> 건너뛰지 않고 실패로 적는다</td><td>「건너뛰고 알리기만 한다」로 바꾼다. 문장을 잘못 적은 시나리오가 확인한 것 없이 통과로 남는다</td></tr>
<tr><td><b>원인이 프로그램이 아닐 때</b></td><td><mark>5번 줄</mark> 원인이 시나리오나 <code>spec.md</code>에 있다고 판단되면 아무것도 고치지 않고 근거와 함께 알린다</td><td>「시나리오의 잘못이면 바로 고친다」로 바꾼다. 편하지만, 실패한 시나리오를 통과하도록 고치는 일과 구별하기 어려워진다</td></tr>
</tbody></table>'''

flowsvg = '''<div class="path"><svg viewBox="0 0 760 236" role="img" aria-label="점검 요청 한 건이 지나는 상태">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#8a94a3"/></marker></defs>
<g font-size="13" font-weight="700" fill="#14181f" text-anchor="middle">
<rect x="6" y="84" width="96" height="48" rx="10" fill="#eef1f5"/><text x="54" y="104">점검 요청</text><text x="54" y="121" font-size="10.5" font-weight="400" fill="#5b6573">접수</text>
<rect x="150" y="10" width="150" height="50" rx="10" fill="#fff1a8"/><text x="225" y="31">질문_대기</text><text x="225" y="48" font-size="10.5" font-weight="400" fill="#5b6573">사례가 정해지지 않았다</text>
<rect x="150" y="84" width="150" height="48" rx="10" fill="#eef1f5"/><text x="225" y="104">사례가 정해짐</text><text x="225" y="121" font-size="10.5" font-weight="400" fill="#5b6573">에이전트가 점검 계획을 낸다</text>
<rect x="150" y="160" width="150" height="50" rx="10" fill="#fff1a8"/><text x="225" y="181">보류</text><text x="225" y="198" font-size="10.5" font-weight="400" fill="#5b6573">근거 상태가 SUPPORTED가 아니다</text>
<rect x="350" y="84" width="140" height="48" rx="10" fill="#eaf0ff" stroke="#2f5bea" stroke-width="2"/><text x="420" y="104">승인_대기</text><text x="420" y="121" font-size="10.5" font-weight="400" fill="#5b6573">긴급한 건도 여기서 기다린다</text>
<rect x="560" y="30" width="190" height="50" rx="10" fill="#e8f6ee"/><text x="655" y="51">확정</text><text x="655" y="68" font-size="10.5" font-weight="400" fill="#5b6573">승인 역할의 사람이 승인했다</text>
<rect x="560" y="136" width="190" height="50" rx="10" fill="#fdecec"/><text x="655" y="157">반려</text><text x="655" y="174" font-size="10.5" font-weight="400" fill="#5b6573">사유를 적어 거절했다</text></g>
<g stroke="#8a94a3" stroke-width="2" fill="none" marker-end="url(#ar)"><path d="M102 108H148"/><path d="M102 98H124V35H148"/><path d="M225 60V82"/><path d="M225 132V158"/><path d="M300 108H348"/><path d="M490 100H524V55H558"/><path d="M490 116H524V161H558"/></g>
<g font-size="11" fill="#5b6573"><text x="236" y="75">사람의 답이 오면 이어서</text><text x="380" y="230" text-anchor="middle" font-size="11.5">요청마다 긴급 칸이 붙는다: true · false · 가리지 못하면 null. 긴급은 상태를 바꾸지 않는다</text></g></svg></div>'''

overlap = '''<table class="res"><thead><tr><th style="width:170px">더하는 편</th><th>사람의 답과 결정을 어떻게 바꾸는가</th><th style="width:96px">금지 조건</th><th>여섯 편으로는 보이지 않는 까닭</th></tr></thead><tbody>
<tr><td><b>긴급한 건의 거절</b></td><td>긴급한 R04를 운전원이 사유를 적어 거절한다</td><td class="nw">11 · 15</td><td>거절 편의 R07은 긴급하지 않다</td></tr>
<tr><td><b>긴급한 건의 권한 없는 승인</b></td><td>긴급한 R04의 조치를 승인 역할이 아닌 생산관리자가 승인한다</td><td class="nw">1 · 11</td><td>여섯 편의 승인은 승인 역할의 사람이 한 것 하나뿐이다</td></tr>
<tr><td><b>답이 하나 빠진 건</b></td><td>R04의 질문 1번에만 답하고 2번은 비워 둔다. 후보에 긴급한 S01이 들어 있다</td><td class="nw">12 · 13</td><td>긴급 편의 R04는 답이 다 온 건이다</td></tr>
<tr><td><b>값이 묵은 건</b></td><td>R07의 질문에 S09라고 답한다. 유온 평균은 60.1인데 신선도가 한도를 넘었다</td><td class="nw">7 · 14</td><td>지금의 열 건에는 값을 읽지 못한 요청이 없다</td></tr>
<tr><td><b>선택지에 없는 답</b></td><td>R01의 질문에 선택지에 없는 S06이라고 답한다</td><td class="nw">3</td><td>여섯 편의 답은 모두 받는 답 안에 있다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 7회차 · 실습 4 · 50분</small>명세에 적은 대로 행동하는지를<br>시나리오로 실행해 확인한다',
 '앞 실습에서 <code>spec.md</code>에 긴급 조건을 적고 그 명세대로 프로그램을 고쳤다. 다음 실습에 넘길 입력과 기대 결과 여섯 건도 <code>검증/시나리오.json</code>에 남겼다. 이번에는 그 여섯 건을 Given · When · Then으로 옮겨 실행하고, 경우를 겹친 편을 더하고, 실제로 실패한 것이 있으면 원인부터 따라간 다음, 기존 행동이 그대로인지를 회귀로 확인한다. 무엇이 나와야 통과인지는 <b>명세가 정하고, 나는 그것을 문장으로 옮긴다.</b>',
 [('끝나면 남는 것', '시나리오 열두 편, 실행하는 프로그램, 실행할 때마다 한 줄씩 쌓인 검증 이력'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '온라인 8일차의 행동 검증 단원을 들었다'), ('준비에 쓰는 시간', '약 4분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>프로그램을 새로 만드는 실습이 아니다. 이미 있는 프로그램이 명세대로 행동하는지를 되풀이해 확인할 수 있게 만드는 실습이다.</p>'
  f'<div class="pipe"><div><b>명세와 프로그램</b>금지 조건 {n_forbid}줄, 수용 기준 {n_ac}문장과 그대로 고친 프로그램<small>spec.md · 요청_처리.py</small></div><span>→</span><div><b>시나리오</b>요청 한 건의 한 가지 경우마다 Given · When · Then 한 편, 그리고 그것을 실행하는 프로그램<small>검증/시나리오.feature · 시나리오_실행.py</small></div><span>→</span><div class="out"><b>검증 결과</b>편마다, 문장마다의 통과와 실패. 실행할 때마다 이력 한 줄<small>결과/검증_결과.md · 검증_이력.md</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 시나리오의 문장이 명세의 어느 줄에서 왔는지를 읽고, 통과가 무엇을 말해 주고 무엇을 말해 주지 않는지를 판단하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>앞 실습이 넘긴 여섯 건이 금지 조건의 어느 줄을 확인하는지 대어 보게 한다</div><div><em>2</em><b>정해 준다</b>규칙이 비워 둔 다섯 가지를 정하고 계획을 받는다</div><div><em>3</em><b>실행한다</b>여섯 편을 실행하고, 경우를 겹친 다섯 편을 더해 다시 실행한다</div><div><em>4</em><b>회귀 편을 더한다</b>열 건을 한꺼번에 처리해 변경 전과 견주는 한 편을 더한다</div><div><em>5</em><b>실패의 원인을 듣는다</b>실패가 나면 고치기 전에 원인이 어디에 있는지부터 가린다</div></div>'
  '<p style="margin:18px 0 0">그 사이에 규칙에 어긋나는 요청을 일부러 보내 보고(5단계), 끝에 결과의 아쉬운 곳을 내 말로 되돌려 준다(8단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 앞 실습을 끝까지 마친 상태가 그대로 들어 있고, 규칙 파일만 이번 실습의 것으로 바뀌어 있다.</p>'
 f'<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ spec.md                     <i>← 명세. 금지 조건 {n_forbid}줄, 수용 기준 {n_ac}문장</i>\n├─ 요청_처리.py                <i>← 요청을 받아 묻고, 승인을 기다린다</i>\n├─ 긴급_기준.json              <i>← 긴급의 기준(유온 60 이상)</i>\n├─ 에이전트.py · 도구.py        <i>← 5회차에 만든 원인 추론 에이전트</i>\n├─ <span>입력/</span>                      <i>← 점검 요청 {n_req}건, 센서 입력 11건</i>\n├─ <span>사람/</span>\n│  ├─ 답변.json                <i>← 사람이 쓴 답</i>\n│  └─ 승인.json                <i>← 사람이 쓴 승인과 거절</i>\n├─ <span>검증/</span>\n│  ├─ 시나리오.json            <i>← 앞 실습이 넘긴 입력과 기대 {n_sc}건</i>\n│  ├─ 견주기.py                <i>← 변경 전과 칸마다 대어 본다</i>\n│  └─ <span>변경_전/</span>                <i>← 긴급 조건을 더하기 전의 결과</i>\n├─ <span>결과/</span>                      <i>← 지금의 처리 결과</i>\n└─ <span>온톨로지/</span> · <span>사례/</span>           <i>← 앞 실습에서 쓴 자료. 읽기만 한다</i></div>'
 '<div><p><b>규칙 파일</b>은 Copilot이 이 폴더에서 일할 때 지키는 약속이다. 「하면 안 되는 것」과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 5단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」의 다섯 줄은 일부러 비워 둔 자리이고, 2단계에서 내가 채운다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 입력, 사람, 검증, 결과 폴더와 spec.md, 요청_처리.py가 보이게. 검증 폴더는 펼쳐 둔다.'))
+ do(2, 'editor', 'VS Code · 편집기', '<code>spec.md</code>에서 지킬 것을 읽는다',
 '<p><code>spec.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 바꾼다. 요청 한 건은 아래 길을 간다. 「금지 조건」 절의 열여덟 줄을 읽는다. 앞의 열 줄은 긴급 조건을 더하기 전부터 있던 것이고, 11번부터가 긴급 조건과 함께 더해진 것이다.</p>' + flowsvg
 + f'<p>11번 줄은 이렇게 적혀 있다. 「{q(f11)}」 긴급하다는 것은 받아 보는 사람이 바로 알아보게 한다는 뜻이고, 승인을 건너뛴다는 뜻이 아니다. 오늘 적는 시나리오의 Then은 이런 줄에서 온다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '앞 실습이 넘긴 여섯 건을 본다',
 f'<p><code>검증/시나리오.json</code>을 연다. 한 건의 칸은 <code>경우</code>, <code>요청</code>, <code>주어진_것</code>, <code>기대</code> 넷이다. 정상 한 건(R05), 긴급 두 건(R03 · R04), 미입력 두 건(R01 · R08), 거절 한 건(R07)이다. <code>주어진_것</code>에는 요청에 적힌 것, 사람의 답, 사람의 결정, 긴급을 가르는 값이 들어 있고, <code>기대</code>에는 <code>상태</code>, <code>긴급</code>, <code>사례</code>, <code>근거_상태</code>가 적혀 있다.</p>'
 '<p>R04 건을 찾아 읽는다. 설비도 경보 패턴도 사례도 적히지 않은 요청이 답 두 번으로 사례 S01에 이르렀고, 유온 평균이 60.7이어서 긴급이다. 그런데 사람의 결정은 <code>null</code>이고 기대하는 상태는 <code>승인_대기</code>다. 긴급이면서 승인을 기다리는 건이다.</p>'
 + note('여섯 건이 말해 주는 범위', '여섯 건은 앞 실습에서 프로그램을 고친 뒤 이미 한 번 실행해 본 건이다. 긴급한 건이 거절되면 어떻게 되는지, 값을 읽지 못한 건의 긴급이 무엇으로 적히는지는 여섯 건에 없다. 명세에는 줄이 있는데 아무도 실행해 보지 않은 자리다. 오늘 확인하는 것이 그 부분이다.'))
+ nxt(1, '1. 만들기 전에, 여섯 건과 금지 조건을 대어 보게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>여섯 건과 금지 조건을 대어 보게 한다',
 '첫마디가 「테스트를 만들어 줘」이면 AI는 프로그램을 읽고, 지금 프로그램이 하는 대로를 기대 결과로 적은 시험을 만든다. 그런 시험은 언제나 통과하고 아무것도 확인하지 못한다. 기대 결과는 프로그램이 아니라 명세에서 와야 한다. 그래서 첫 요청은 <b>넘겨받은 여섯 건을 하나씩 놓고, 그 건이 명세의 어느 줄을 확인하는지 대어 보라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '여섯 건과 금지 조건의 대응표, 말로 적은 시나리오 네 편, Copilot의 물음이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙, 명세, 프로그램, 넘겨받은 여섯 건, 사람이 쓰는 두 파일의 칸. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '여섯 건을 금지 조건 열여덟 줄에 대어 보게 했다. 줄마다 대어 보아야 여섯 건으로 확인되지 않는 줄이 드러난다. 그다음 네 경우를 말로 적게 했다.'), ('하지 말 것', '정할 수 없으면 정하지 말 것, 파일을 만들지도 실행하지도 말 것. 이 문장이 없으면 AI는 바로 시험 코드를 쓰고 돌린다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>답이 오는 데 2분 넘게 걸릴 수 있다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 여섯 건을 금지 조건에 대어 본 표, 「여섯 건으로는 확인되지 않는 금지 조건」, 답의 끝에서 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('여섯 건으로 확인되지 않는 줄을 가렸는가', '대신 돌린 실행에서는 어느 건으로도 확인되지 않는 줄을 여덟(4 · 5 · 6 · 7 · 10 · 14 · 16 · 17)로 가렸다. 7번과 14번은 값을 읽지 못한 건이 여섯 건에 없어서이고, 나머지는 결과의 값만 보아서는 알 수 없는 줄이다(파일을 쓰지 않는다, 프로그램 안에 옮겨 적지 않는다). 이 가운데 시나리오로 채울 수 있는 것을 4단계에서 채운다.'),
        ('기대의 네 칸으로 보이는 것과 보이지 않는 것', '<code>기대</code>에는 상태, 긴급, 사례, 근거 상태 네 칸만 있다. 미입력 R01과 R08은 네 칸이 똑같다. 둘의 차이(선택지가 둘인 질문과 선택지가 빈 질문)는 Then을 더 적어야 드러난다는 것을 짚었는지 본다.'),
        ('정하지 않고 되물은 것', '물음이 몇 가지인지 세어 둔다. 대신 돌린 실행에서는 여섯 가지를 물었다. 그 가운데 하나는 「긴급을 가르는 값은 함수에 넘길 길이 없다. Given에 어떻게 둘 것인가」였다. 프로그램이 센서 값을 도구로 직접 읽기 때문이다.'))
 + note('되묻는 까닭', '규칙 파일에 「spec.md에 근거가 없는 기대 결과는 지어내지 않고 묻는다」는 줄이 있고, 「정해져 있지 않은 것」에 다섯 줄을 비워 두었기 때문이다. 이 줄들이 없었다면 AI는 지금 프로그램이 내는 값을 기대 결과로 적었을 것이다.')
 + ifs(('파일이 생기거나 무언가 실행되었다면', '탐색기의 <code>검증</code> 폴더에 새 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.'),
       ('표가 내 생각과 다르다면', '「다시 해 줘」라고 하지 않는다. 「R03으로 금지 11이 확인된다고 했는데, R03은 승인이 실제로 있는 건이야.」처럼 어느 줄이 왜 다른지를 말한다.')))
+ nxt(2, '2. 비워 둔 것을 내가 정하고, 계획부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '비워 둔 것을 내가 정하고,<br>계획부터 받는다',
 '시나리오는 누구나 읽을 수 있는 글이지만, 그 글을 실행하려면 정해야 할 것이 있다. Then에 일어나지 않아야 할 일까지 적을 것인가. 넘겨받은 값이 지금의 입력과 다르면 어떻게 할 것인가. 한 문장이 실패하면 나머지는 어떻게 하는가. 어느 쪽으로 정하느냐에 따라 같은 프로그램이 통과하기도 하고 실패하기도 한다. 그래서 <b>요청하는 사람이 정한다.</b> 기준은 하나다. 어긋난 곳이 통과로 가려지지 않게 한다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '시나리오 여섯 편의 글 전체와, 문장마다 무엇을 부르는지가 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '다섯 빈자리마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 복사 상자의 뒷부분에는 1단계에서 Copilot이 물어 온 것에 대한 답도 들어 있다. 사람의 답과 결정은 <code>사람/</code> 폴더에서 읽지 않고 시나리오에 적힌 것만 넘기게 했다. 그래야 한 편이 다른 편이나 지금의 파일에 기대지 않는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다). 내 답에서 Copilot이 물어 온 것이 이 글의 셋째 문단과 다르면, 내가 받은 물음에 맞게 그 문단을 고친다.</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abbc'))
 + parts(('무엇을 왜 만드는가', '첫 문단. 만들 두 파일을 말하고, 무엇이 가장 중요한지를 적었다. 「통과가 많아 보이게 하는 것이 아니라 어긋난 곳이 드러나게」라는 문장이 있으면 Copilot이 애매한 곳을 엄격한 쪽으로 정한다.'), ('빈자리 다섯 가지와 물음의 답', '번호를 붙여 한 줄에 결정 하나씩 적었다. 그 아래는 1단계에서 물어 온 것의 답이다. 시나리오의 이름을 어떤 꼴로 할지도 여기서 정했다. 이름의 글자로 골라 실행하기 때문이다.'), ('계획 먼저', '마지막 문단. 시나리오의 글 전체를 미리 보여 달라고 했다. 실행하기 전에 내가 읽고 고칠 수 있는 것은 이 글이다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 네 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 시나리오 여섯 편의 글과, 문장의 꼴마다 무엇을 부르고 무엇을 확인하는지가 함께 온다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. 시나리오.feature에 적을 글(R04 편이 보이게), 문장의 꼴과 하는 일을 적은 표, 「확인받고 싶은 것」이 보이게. 아래 네 곳에 테두리를 얹는다.')
 + find(('시나리오의 글이 그대로 읽히는가', '여섯 편 가운데 R04 편을 소리 내어 읽어 본다. 프로그램을 모르는 현장 담당자가 읽고 「그렇게 되어야 맞다」고 말할 수 있는 글인가. 요청 번호, 답, 사람의 이름이 <code>검증/시나리오.json</code>의 것과 같은가.'),
        ('요청_처리.py를 그대로 부르는가', 'When의 문장이 <code>요청_처리.py</code>의 함수를 그대로 부른다고 했는가. 같은 일을 하는 코드를 따로 써서 그것을 확인한다면 아무것도 확인하지 못한다. 사람의 답과 결정을 <code>사람/</code> 폴더에 써 넣지 않고 함수에 넘긴다고 했는지도 본다. 규칙의 10번이 이것을 정한다.'),
        ('Then의 근거를 밝혔는가', 'Then의 줄마다 어디에서 왔는지를 적었는가. 대신 돌린 실행에서는 앞의 네 줄은 넘겨받은 기대, 질문의 선택지는 수용 기준의 번호(AC-11, AC-08 등)라고 밝혔고, 수용 기준에 문장이 없는 것은 적지 않았다.'),
        ('다시 물어 온 것', '인자에 맞는 시나리오가 한 편도 없을 때 어떻게 할지 같은 것이다. 0편을 실행하고 「실패 없음」으로 끝나면 통과처럼 보인다. Copilot이 권하는 답이 함께 적혀 있는지 본다.'))
 + note('계획부터 받는 까닭', '시나리오의 글은 한번 실행되고 나면 「통과한 글」이 되어 다시 읽지 않게 된다. 잘못 적힌 기대 결과를 걸러 낼 수 있는 때는 실행하기 전이다.')
 + ifs(('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('Then에 근거가 적히지 않은 값이 있다면', '「그 값은 spec.md의 어느 줄에서 왔어?」라고 묻는다. 프로그램을 실행해 본 값이라고 답하면 빼게 한다.')))
+ nxt(3, '3. 여섯 편을 적고, 한 번 실행한다', 1))

# ───────── 3단계
pages.append(hero('3단계', '여섯 편을 적고,<br>한 번 실행한다',
 '이제 만들게 한다. 범위는 두 파일과 한 번의 실행까지다. 여기서 가장 중요한 말은 「실패가 나와도 고치지 말라」다. 이 말이 없으면 AI는 실패를 보는 순간 스스로 원인을 짐작해 고치고, 다시 돌리고, 통과한 결과만 가져온다. 무엇이 실패했었는지를 나는 보지 못한다. <b>실행과 수정 사이에는 사람이 있어야 한다.</b>',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '시나리오 여섯 편, 실행하는 프로그램, 검증 결과 두 파일과 이력 한 줄이 있다'), ('고치지 않는 것', '요청_처리.py')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 범위를 정해 준다',
 '<p>계획에 대한 답은 세 마디면 된다. 받을 것, 만들고 실행할 범위, 실패가 나왔을 때 하지 말 것이다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'abc'))
 + parts(('받을 것', 'Copilot이 확인을 구한 것에 답한다. 내 계획의 물음이 이것과 다르면 보내기 전에 첫 문단을 내 물음에 맞게 고친다.'), ('범위', '두 파일을 만들어 한 번만 실행한다. 「한 번만」이 있어야 이력에 한 줄만 남는다.'), ('실패가 나와도', '고치지도, 다시 실행하지도 않게 했다. 무엇이 통과하고 실패했는지만 알려 달라고 했다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 무엇을 하려는지 읽고 허용한다',
 '<p>Copilot이 파일을 만들 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 두 가지를 읽는다. 만드는 파일이 <code>검증/시나리오.feature</code>와 <code>검증/시나리오_실행.py</code>인가. 실행하려는 명령이 <code>python 검증/시나리오_실행.py</code>(또는 <code>python3 …</code>)인가. <code>요청_처리.py</code>나 <code>사람/</code> 폴더의 파일을 고치려 하면 허용하지 않고 왜 필요한지 묻는다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 검증/시나리오_실행.py)와 「허용/계속」 버튼이 보이게. 파일을 만들 때의 「유지/허용」 물음도 뜬다면 한 장 더.'))
+ do(3, 'editor', 'VS Code · 편집기', '결과를 편마다, 문장마다 읽는다',
 '<p><code>결과/검증_결과.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 바꾼다. 아래는 대신 돌린 실행의 결과 파일에서 옮긴 것이다. 여섯 편이 모두 통과했다.</p>' + runtable(r3)
 + find(('문장이 시나리오의 글 그대로인가', '<code>검증/시나리오.feature</code>를 옆에 열어 결과의 문장과 견준다. 결과에 적힌 문장은 실행하는 프로그램이 그 파일에서 읽은 것이다. 빠진 문장이 없는지 편마다 줄 수를 세어 본다.'),
        ('일어나지 않아야 할 일이 확인되었는가', '긴급 R04 편에 「상태는 확정이 아니다」와 「승인 칸은 비어 있다」가 있고 통과했는가. 이 두 줄이 통과했다는 것이 「긴급이라는 것으로 승인을 대신하지 않는다」(금지 11)를 실행으로 본 것이다.'),
        ('이력에 한 줄이 생겼는가', '<code>결과/검증_이력.md</code>에 「1 · 6편 · 통과 6 · 실패 0」 한 줄이 있다. 실행할 때마다 한 줄씩 는다. 지난 줄은 아무도 고치지 않는다.'))
 + note('모두 통과했다면 고칠 것이 없다', '실패가 없는데 일부러 프로그램을 틀리게 만들어 고치는 연습은 하지 않는다. 대신 이 통과가 무엇을 말해 주지 않는지를 따진다. 여섯 편은 앞 실습에서 이미 실행해 본 건이고, 한 편이 한 가지 경우만 본다. 1단계의 표에서 확인되지 않는다고 나온 줄과, 긴급이 다른 경우와 겹치는 자리는 아직 한 번도 실행되지 않았다.')
 + ifs(('python을 찾을 수 없다고 나오면', '「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다.'),
       ('내 실행에서는 실패가 나왔다면', '고치게 하지 말고 그대로 둔다. 어느 편의 어느 문장인지를 적어 두고 4단계까지 마친 다음, 7단계의 첫 요청에서 둘째 문단만 보내 그 편의 원인부터 따라가게 한다.')))
+ nxt(4, '4. 경우를 겹쳐, 다섯 편을 더한다', 2))

# ───────── 4단계
pages.append(hero('4단계', '경우를 겹쳐,<br>다섯 편을 더한다',
 '기능을 하나 더하면 새 기능만 시험하기 쉽다. 그러나 잘못은 새 기능과 기존 기능이 만나는 자리에서 생긴다. 긴급한 건이 거절되면 어떻게 되는가. 긴급한 건을 승인 역할이 아닌 사람이 승인하면 어떻게 되는가. 유온은 기준을 넘었는데 그 값이 묵은 것이면 어떻게 되는가. 입력은 그대로 두고 <b>사람의 답과 결정만 바꿔서</b> 이런 경우를 만든다. 기대 결과는 이번에도 명세에서 온다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '시나리오가 열한 편이 되고, 실제로 실패한 편이 있는지 안다'), ('고치지 않는 것', '요청_처리.py, 입력, 앞의 여섯 편')])
+ '<section class="sect"><h2>더하는 다섯 편</h2><p>앞의 셋은 긴급 조건이 거절 · 승인 · 질문과 겹치는 자리이고, 뒤의 둘은 여섯 건으로 확인되지 않던 금지 조건이다.</p>' + overlap + '</section>'
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '다섯 편을 더하고, 열한 편을 실행하게 한다',
 '<p>편마다 사람이 무엇이라고 답하고 결정했는지, 무엇이 나와야 하는지, 그것이 금지 조건의 몇 번인지를 한 줄씩 적었다. 요청 번호와 사례 번호는 <code>입력/</code>에 있는 것이다.</p>'
 + copy(P4, pre=True, rich=richpre(P4, 'aabc'))
 + parts(('무엇을 더하는가', '첫 문단과 번호가 붙은 다섯 줄. 줄 끝의 괄호가 그 기대 결과의 근거다. 근거를 함께 적어 두면 Copilot이 명세와 어긋나는 기대 결과를 받았을 때 알아챌 수 있다.'), ('어디까지 고치는가', '셋째 문단. 실행하는 프로그램에는 새 문장에 필요한 것만 더하고, 앞의 여섯 편은 건드리지 않게 했다. 내 기대 결과가 명세와 어긋나면 적지 말고 알려 달라는 말도 여기에 있다.'), ('실패가 나와도', '마지막 문단. 3단계와 같다. 한 번만 실행하고, 고치지 않고, 실제로 무엇이 나왔는지만 알린다.')))
+ do(2, 'editor', 'VS Code · 편집기', '열한 편의 결과를 읽는다',
 '<p><code>결과/검증_결과.md</code>를 다시 연다. 아래는 대신 돌린 실행에서 새로 더한 다섯 편의 결과다. 앞의 여섯 편을 더해 열한 편이 모두 통과했다.</p>' + runtable(r4, 6)
 + shot('결과/검증_결과.md의 미리 보기에서 「긴급 R07」 편(값이 묵은 건)의 표. Given의 「TS1 avg 120초 값은 60.1이다」 · 「신선도는 한도를 넘었다」와 Then의 「긴급은 null이다」가 보이게. 그 세 줄에 테두리를 얹는다.')
 + find(('값이 60을 넘는데 긴급이 아닌 건', '열째 편을 문장마다 읽는다. Given에서 유온 평균이 60.1이고 신선도가 한도를 넘었다는 것을 도구로 확인했고, Then에서 긴급이 <code>true</code>도 <code>false</code>도 아닌 <code>null</code>로 나왔다. 명세의 수용 기준에는 「값을 읽지 못한 요청은 지금의 열 건 가운데 없어서 문장이 없다」고 적혀 있다. 그 빈 곳을 처음 실행해 본 것이다.'),
        ('후보에 긴급한 사례가 있어도 미리 가르지 않았는가', '아홉째 편을 본다. R04는 질문 2번의 선택지에 S01이 들어 있다. 그래도 답이 오기 전에는 사례가 <code>null</code>이고 긴급도 <code>null</code>이다.'),
        ('Copilot이 근거를 가려 알렸는가', '대신 돌린 실행에서는 넷째 편의 「근거 상태는 UNKNOWN」이 명세의 문장이 아니라 내가 적어 준 기대라는 것을 알려 왔다. 근거 상태는 에이전트가 내는 값이기 때문이다. 내 요청의 어느 줄이 명세에 근거가 있고 어느 줄이 없는지를 가려 주었는지 본다.'))
 + note('열한 편이 모두 통과했다', '겹친 경우에서도 프로그램은 명세와 어긋나지 않았다. 실패가 없으므로 고칠 것이 없다. 다만 알아 둘 것이 있다. 이 열한 편은 한 번도 실패한 적이 없다. 그래서 프로그램이 어긋났을 때 이 시나리오가 정말 잡아내는지는 아직 모른다. 다음 단계에서 이 물음을 Copilot에게 던져 본다.')
 + ifs(('내 실행에서는 실패한 편이 있다면', '고치게 하지 말고 그대로 둔다. 5단계와 6단계를 마친 다음, 7단계의 첫 요청에서 둘째 문단만 보내 그 편의 원인부터 따라가게 한다. 원인이 프로그램에 있다고 확인되면 「그 부분만 고치고 실패했던 편만 다시 실행해 줘」라고 요청하고, 이어서 전체를 다시 실행한다.'),
       ('Copilot이 기대 결과가 명세와 어긋난다고 알려 왔다면', '그 근거를 읽고 <code>spec.md</code>의 그 줄을 직접 열어 본다. Copilot의 말이 맞으면 내 요청의 그 줄을 고쳐 다시 보낸다.')))
+ nxt(5, '5. 규칙을 일부러 건드려 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '규칙을<br>일부러 건드려 본다',
 '열한 편이 모두 통과한 지금, 급한 사람이 할 법한 말이 둘 있다. 하나는 「시나리오가 진짜 잡는지 보게 프로그램을 잠깐 틀리게 해 봐」이고, 다른 하나는 「긴급한 건은 승인을 기다리지 말게 해 줘」다. 둘 다 그럴듯하게 들린다. 그 말을 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일과 명세의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '요청_처리.py, 시나리오.feature, 검증 이력')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '프로그램을 잠깐 틀리게 고쳐 달라고 해 본다',
 '<p>통과만 보아서는 시나리오를 믿기 어렵다는 것은 옳은 의심이다. 다만 그 의심을 푸는 방법으로 프로그램을 건드리자는 요청이다.</p>'
 + copy(P5a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 프로그램을 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '<code>요청_처리.py</code>가 바뀌지 않았는지, <code>결과/검증_이력.md</code>가 두 줄 그대로인지 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 「잠깐 뺐다가 되돌리는 것」도 그 줄에 해당한다고 했는지 본다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고 길을 내놓았는가. 대신 돌린 실행에서는 프로그램을 실행하지 않고 읽어서 따졌다. 승인 역할을 견주는 줄이 한 군데이고, 그 줄이 없으면 열한 편 가운데 여덟째 한 편만 실패할 것이라고 했다. 그리고 승인을 받아들이는 다섯 조건 가운데 시나리오가 있는 것이 하나뿐이라는 것을 짚었다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '긴급한 건은 승인을 기다리지 않게 해 달라고 해 본다',
 '<p>「긴급한 경보는 빨리 처리되게 해 달라」는 말을 승인 생략으로 읽은 요청이다. 수업에서 본, 한 문장의 세 가지 해석 가운데 하나다.</p>'
 + copy(P5b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>요청_처리.py</code>가 바뀌지 않았는지 본다. 답에 규칙의 줄과 함께 <code>spec.md</code>의 줄이 적혀 있는지 본다. 대신 돌린 실행에서는 금지 조건 11번과 요구사항의 「빨리 처리는 받아 보는 사람이 긴급한 건을 바로 알아보게 하는 데까지다」를 들었고, 고치면 방금 통과한 R04의 편들이 바로 어긋난다고 했다.</p>'
 '<details><summary>하나 더 보내 보려면: 지금 나온 값을 그대로 기대 결과로 옮겨 달라고 한다</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">앞의 둘은 프로그램을 건드렸다. 이번에는 시나리오다. 수용 기준을 하나하나 옮기는 대신 결과 파일의 값을 베껴 시나리오를 늘리자는 요청이다. 보낸 뒤 시나리오가 그대로인지, 규칙 파일의 어느 줄을 들었는지, 그렇게 만든 시나리오가 무엇을 확인하지 못한다고 했는지 본다.</p>' + copy(P5c, 'Copilot에게 보낼 요청 (규칙에 어긋난다)') + '</details>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일과 명세에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>와 <code>spec.md</code>를 차례로 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>규칙 파일의 「하면 안 되는 것」 가운데 한 줄이다. 실패하지 않은 것을 어떻게 하라고 적혀 있는가. 시나리오가 실패를 잡는지 보려고 무엇을 하지 말라고 적혀 있는가. 몇 번인가.</li><li><b>둘째 요청</b>규칙 파일의 두 줄과 <code>spec.md</code>의 금지 조건 한 줄이다. 급하다는 것이 무엇을 대신하지 않는다고 적혀 있는가. 명세에 적혀 있지 않은 변경을 받으면 어떻게 하라고 적혀 있는가.</li><li><b>두 답에 함께 나온 줄</b>「요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('금지 조건이 한 일', '둘째 요청을 막은 것은 Copilot의 조심성이 아니라 명세의 금지 조건이다. 앞 실습에서 긴급 조건을 더하면서 「긴급이라는 것으로 승인을 대신하지 않는다」를 적어 두었기 때문에, 「빨리」를 승인 생략으로 읽는 해석이 요청 단계에서 배제되었다. 요구사항은 늘어나도 금지 조건은 남는다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '<code>요청_처리.py</code>가 바뀌었다면 완성 폴더의 같은 파일을 복사해 덮어쓴다(이 파일은 실습이 끝날 때까지 시작 폴더의 것과 같다). 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 승인 없이 조치를 확정하게 할 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(6, '6. 회귀 편을 더해, 열 건을 한꺼번에 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '회귀 편을 더해,<br>열 건을 한꺼번에 본다',
 '열한 편은 요청을 한 건씩 본다. 그래서 요청의 순서가 그대로인지, 열 건 가운데 확정이 몇 건인지, 긴급 조건을 더하기 전과 달라진 칸이 없는지는 보지 못한다. 무언가를 바꾼 뒤에 기존의 것이 그대로인지를 다시 보는 것이 회귀 시험이다. 앞 실습에서는 <code>검증/견주기.py</code>를 손으로 실행해 그것을 보았다. 이번에는 그 일을 시나리오 한 편으로 만들어, 다른 편과 함께 되풀이해 실행되게 한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '시나리오가 열두 편이 되고 모두 통과한다'), ('바뀌면 안 되는 것', '요청_처리.py, 사람 폴더의 두 파일, 앞의 열한 편')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '회귀 한 편을 더하고, 열두 편 전체를 실행하게 한다',
 '<p>이 편만 <code>사람/</code> 폴더의 답과 결정을 지금 그대로 읽는다. 지금의 열 건을 통째로 처리한 결과를, 긴급 조건을 더하기 전의 결과와 견준다.</p>'
 + copy(P6, pre=True, rich=richpre(P6, 'abbc'))
 + parts(('왜 한 편이 더 필요한가', '첫 문단. 열한 편이 보지 못하는 것을 말했다. 한 건씩 보는 시험과 전체를 보는 시험은 잡는 것이 다르다.'), ('무엇을 적고 어디까지 하는가', '둘째와 셋째 문단. Then의 네 줄마다 근거가 되는 수용 기준과 금지 조건의 번호를 붙였다. 견주는 일은 이미 있는 <code>견주기.py</code>를 그대로 부르게 했다. 같은 일을 하는 코드를 새로 쓰면 그것이 또 하나의 확인되지 않은 프로그램이 된다.'), ('무엇을 실행하는가', '마지막 문단. 열두 편 전체를 한 번 실행한다. 이번에도 실패가 나오면 고치지 않고 알리게 했다.')))
+ do(2, 'editor', 'VS Code · 편집기', '회귀 편의 문장과 이력의 세 줄을 읽는다',
 '<p><code>검증/시나리오.feature</code>의 맨 끝에서 회귀 편을 읽고, <code>결과/검증_이력.md</code>를 연다. 아래는 완성 폴더의 이력에서 옮긴 것이다. 지금은 왼쪽 세 칸까지 와 있다.</p>' + histrow(3)
 + find(('열 건 모두를 견주었는가', '회귀 편의 Then에 「모든 항목에서 긴급을 뺀 일곱 칸은 변경 전 결과의 같은 번호의 항목과 같다」가 있는가. 긴급 조건은 칸 하나를 더할 뿐 기존 칸을 바꾸지 않는다는 금지 조건 15번을 열 건 전부로 본 것이다.'),
        ('견주는 일을 어떻게 불렀는가', 'Copilot의 답에서 <code>견주기.py</code>를 어떻게 썼다고 했는지 읽는다. 대신 돌린 실행에서는 통째로 부르지는 못했고(파일 두 개를 받는 함수여서), 그 안에서 칸을 대어 보는 함수를 그대로 불렀다고 밝혔다. 묻지 않고 정한 판단이라는 것도 스스로 알렸다.'),
        ('이 편은 무엇에 기대고 있는가', '이 편은 지금의 <code>사람/</code> 폴더를 읽는다. 그래서 사람이 답이나 결정을 하나 더 쓰면 이 편의 결과가 달라질 수 있다. 다음 단계에서 그것을 직접 해 본다.'))
 + ifs(('회귀 편이 실패했다면', '고치게 하지 말고 「실제」 칸에 어느 요청의 어느 칸이 다르다고 적혔는지 읽는다. 내가 <code>사람/</code> 폴더의 파일을 고친 적이 있는지 먼저 떠올린다.'),
       ('임시 파일을 만들어도 되느냐고 물었다면', '<code>견주기.py</code>를 통째로 부르려면 결과를 파일로 써야 하기 때문이다. 만들지 않는 쪽으로 답하고, 칸을 대어 보는 함수만 불러 쓰게 한다.')))
+ nxt(7, '7. 사람의 결정을 하나 바꾸고, 실패의 원인을 듣는다', 5))

# ───────── 7단계
pages.append(hero('7단계', '사람의 결정을 하나 바꾸고,<br>실패의 원인을 듣는다',
 '지금까지 실패한 편이 없었다. 프로그램을 일부러 틀리게 만들지는 않는다. 대신 이 폴더에서 사람이 원래 하는 일을 하나 한다. <code>사람/승인.json</code>에 승인 한 건을 써 넣는 것이다. 긴급하면서 승인을 기다리던 R04를 운전원이 승인한다. 프로그램도 시나리오도 그대로인데 회귀 편이 실패한다. 이때 할 일은 고치는 것이 아니라 <b>원인이 어디에 있는지를 먼저 가리는 것</b>이다. 실패한 시나리오가 언제나 프로그램의 잘못을 뜻하지는 않는다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '실패한 까닭이 프로그램이 아니라는 것을 근거와 함께 알고, 이력에 실패와 통과가 차례로 남아 있다'), ('고치지 않는 것', '요청_처리.py, 시나리오.feature')])
+ do(1, 'editor', 'VS Code · 편집기', '<code>사람/승인.json</code>에 승인 한 건을 내 손으로 써 넣는다',
 '<p><code>사람/승인.json</code>을 연다. 마지막 항목(R07의 거절)의 끝에 쉼표를 붙이고, 아래 한 줄을 더해 저장한다(Ctrl+S). 이 파일은 사람이 쓰는 파일이다. Copilot은 읽기만 한다.</p>'
 '<div class="tree" style="white-space:pre-wrap;font-size:13.5px">' + e(APPROVE) + '</div>'
 + note('되돌릴 수 있게', '고치기 전의 파일은 완성 폴더의 <code>사람/승인.json</code>과 같다. 쉼표나 따옴표가 어긋나 헷갈리면 그 파일을 열어 견준다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '전체를 실행하게 하고, 실패하면 원인부터 따라가게 한다',
 '<p>알려 달라는 것은 네 가지다. 기대와 실제, 원인이 있는 곳, 나머지 편이 그대로인 까닭, 통과로 되돌리는 길마다 치르는 값이다.</p>'
 + copy(P7a, pre=True, rich=richpre(P7a, 'ab'))
 + parts(('무엇이 달라졌는가', '첫 문단. 내가 무엇을 바꾸었고 무엇은 그대로인지를 먼저 말했다. 달라진 것을 알려 주어야 원인을 좁힐 수 있다.'), ('고치지 말고 알려 줄 네 가지', '둘째 문단. 원인이 프로그램에 있는지, 시나리오에 있는지, 사람의 결정에 있는지를 가려 달라고 했다. 「읽어 짐작한 것과 실행해 확인한 것을 구분해 달라」는 말이 중요하다. 단정한 것과 확인한 것은 믿을 수 있는 정도가 다르다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '실패한 문장과 원인의 자리를 읽는다',
 '<p>아래는 대신 돌린 실행에서 실패한 회귀 편이다. 열한 편은 그대로 통과했다.</p>' + badtable
 + shot('원인을 따라간 Copilot의 답. 「원인은 요청_처리.py가 아니라 써 넣으신 R04의 승인」이라고 말한 부분과, 「통과로 되돌리는 길」을 견준 표가 보이게.')
 + find(('무엇이 달라졌는가', '「실제」 칸에 R04의 세 칸이 적혀 있다. 상태가 <code>승인_대기</code>에서 <code>확정</code>으로, 승인 칸이 채워졌고, 상태 기록이 한 건 늘었다. 나머지 아홉 건은 달라진 곳이 없다.'),
        ('원인을 어디에 두었는가', '프로그램은 원인이 아니라고 했는가. 승인 역할인 운전원이 확인된 원인의 조치를 승인하면 확정으로 적는 것은 명세 그대로다. 긴급이 승인을 대신한 것도 아니다. 달라진 것은 사람의 결정이고, 회귀 편의 기대가 결정이 세 건이던 때의 결과에 묶여 있었던 것이다.'),
        ('열한 편은 왜 그대로인가', '열한 편은 <code>사람/</code> 폴더를 읽지 않고, 답과 결정을 시나리오의 문장에서 받는다. 2단계에서 그렇게 정했기 때문이다. 그래서 사람의 파일이 바뀌어도 흔들리지 않는다.'),
        ('되돌리는 길마다 무엇을 잃는가', '대신 돌린 실행에서는 길 셋을 견주었다. 승인 줄을 지운다(그 결정이 사라진다). 회귀 편이 사람 폴더를 읽지 않게 고친다(사람의 결정이 바뀌어도 알아채지 못한다). 변경 전 결과를 새로 만든다(프로그램을 자기 결과와 견주게 된다). 기대를 <code>확정</code>으로 바꿔 맞추는 길은 스스로 하지 않겠다고 했는지도 본다.'))
 + note('실패를 보고 바로 프로그램을 고쳤다면', '「R04가 확정으로 나오면 안 된다」고 읽고 프로그램을 고쳤다면, 사람이 승인한 건을 확정으로 적지 않는 프로그램이 되었을 것이다. 명세와 어긋나는 쪽은 프로그램이 아니라 내가 방금 바꾼 입력이었다. 원인을 먼저 듣는 까닭이 여기에 있다.'))
+ do(4, 'editor', '편집기 → Copilot 채팅 (같은 대화)', '승인 줄을 지우고, 전체를 다시 실행하게 한다',
 '<p>그 승인은 회귀 편이 사람의 결정이 달라진 것을 알아채는지 보려고 써 본 것이다. <code>사람/승인.json</code>에서 방금 더한 줄과 그 앞의 쉼표를 지우고 저장한다. 그다음 아래를 보낸다.</p>'
 + copy(P7b, pre=True)
 + '<p style="margin-top:18px"><code>결과/검증_이력.md</code>를 연다. 지금은 다섯째 칸까지 와 있다. 넷째 줄의 실패는 지워지지 않고 남아 있다.</p>' + histrow(5)
 + shot('결과/검증_이력.md의 미리 보기. 다섯 줄(6편 통과, 11편 통과, 12편 통과, 12편 가운데 1편 실패, 12편 통과)이 보이게.')
 + ifs(('다시 실행해도 회귀 편이 실패한다면', '<code>사람/승인.json</code>이 고치기 전과 같지 않은 것이다. 완성 폴더의 같은 파일과 견주어 쉼표와 줄을 맞춘다.'),
       ('Copilot이 승인 줄을 대신 지워 주겠다고 한다면', '받지 않는다. 그 파일은 사람이 쓴다. 규칙의 2번이 그렇게 정했다.')))
+ nxt(8, '8. 아쉬운 곳을 찾아 되돌려 준다', 6))

# ───────── 8단계
pages.append(hero('8단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '열두 편이 모두 통과했다. 그런데 이 결과를 받아 보는 사람의 눈으로 <code>결과/검증_결과.md</code>를 읽으면 아쉬운 곳이 있다. 편마다 통과했는지는 보이지만, 그 편이 금지 조건의 어느 줄을 확인하는지는 보이지 않는다. 그래서 열여덟 줄 가운데 아직 시나리오가 닿지 않는 줄이 무엇인지 이 파일만으로는 알 수 없다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '검증 결과의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>검증 결과가 좀 보기 불편해. 고쳐 줘.</q>무엇이 불편한지 AI는 모른다. 대신 돌린 실행에서는 되묻지 않고 스스로 짐작해, 실행하는 프로그램에서 결과 글을 쓰는 부분을 고쳤다. 맨 위에 편마다 한 줄인 요약과 「실패한 시나리오」 묶음이 나오게 한 것이다. 쓸모없는 변경은 아니지만 내가 바란 것은 아니었다.</div>'
  '<div class="good"><b>구체적으로</b><q>편마다 통과했는지는 보이는데, 그 편이 금지 조건 가운데 어느 줄을 확인하는지는 보이지 않아. 그래서 아직 시나리오가 닿지 않는 줄이 무엇인지 알 수 없어. Scenario: 줄 끝에 확인하는 금지 조건의 번호를 괄호로 적고, 검증_결과.md 의 맨 위에 금지 조건마다 확인하는 편과 결과를 적은 표를 더해 줘. Given, When, Then 의 문장과 json 의 칸, 요청_처리.py 는 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>편이 금지 조건의 어느 줄을 확인하는지 보이지 않는다</div><div><b>왜</b>시나리오가 닿지 않는 줄을 알 수 없다</div><div><b>어디를</b>Scenario: 줄의 끝과, 결과 md를 쓰는 부분</div><div><b>어디까지</b>문장, json의 칸, 요청_처리.py는 그대로</div></div>'
  + note('통과를 더 늘려 달라고 하지 않은 까닭', '「다 통과하게 해 줘」는 이미 이루어졌다. 지금 모자란 것은 통과의 수가 아니라, 이 통과가 명세의 얼마만큼을 덮는지를 아는 것이다. 열두 편이 모두 통과해도 금지 조건의 한 줄에 시나리오가 없으면 그 줄은 확인되지 않은 채로 남는다.') + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 결과에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/검증_결과.md</code>와 <code>결과/검증_이력.md</code>를 다시 본다. 이 결과를 보고 「이 변경을 내보내도 된다」고 판단해야 하는 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>편이 명세의 어느 줄을 확인하는지 보이는가</b>위의 「구체적으로」가 이 경우다.</li><li><b>이력의 줄이 왜 그렇게 나왔는지 남는가</b>넷째 줄의 실패는 내가 승인을 써 넣어 본 것이었다. 이력에는 편의 이름만 있고 까닭이 없다. 한 달 뒤에 이 줄을 보는 사람은 프로그램이 한 번 깨졌다고 읽을 것이다. 다만 이력의 칸은 규칙이 정해 둔 것이다. 규칙 안에서 무엇을 요청할 수 있는가.</li><li><b>인자로 한 편만 고를 수 있는가</b>「R04」를 인자로 주면 이름에 그 글자가 든 편이 모두 실행된다. 한 편만 골라 실행하고 싶을 때 무엇을 바꾸면 되는가.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 모양만 바꾸는 요청이면 「Given, When, Then 의 문장과 요청_처리.py 는 건드리지 마」를 꼭 넣는다.</p>'
 + write('w8', '무엇이 문제인지, 왜 문제인지, 어느 파일의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(편이 확인하는 줄)를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P8, pre=True) + '</details>'
 '<p style="margin-top:18px">고친 뒤에는 두 가지를 본다. 시나리오의 Given · When · Then 문장이 한 글자도 바뀌지 않았는가. 열두 편이 여전히 모두 통과인가. 완성 폴더의 <code>결과/검증_결과.md</code>에는 맨 위에 금지 조건마다의 표가 생겼다. 아래는 그 표를 줄인 것이다.</p>' + covertable
 + shot('되돌려 준 뒤의 결과/검증_결과.md 미리 보기. 맨 위에 생긴 「금지 조건마다 확인하는 편」 표와 「시나리오 없음」 줄이 보이게.')
 + find(('시나리오가 닿지 않는 줄이 드러났는가', f'금지 조건 {" · ".join(none)}번의 여섯 줄에 시나리오가 없다. 파일을 쓰지 않는다, 프로그램 안에 옮겨 적지 않는다, 실행할 때마다 달라지는 값을 적지 않는다 같은 줄이다. 결과의 값을 보는 시나리오로는 확인하기 어려운 줄이고, 다른 방법(프로그램을 읽는 검토, 두 번 실행해 견주기)이 맡아야 한다.'),
        ('번호가 있다고 다 확인된 것인가', '표는 <code>Scenario:</code> 줄에 적힌 번호를 옮긴 것이다. 대신 돌린 실행에서 Copilot은 일부만 확인되는 줄을 스스로 알려 왔다. 14번은 신선도만 보았고(값이 없는 경우와 관측이 모자란 경우는 지금의 입력에 없다), 9번은 상태의 값만 본다. 번호를 적는 것은 사람의 판단이다.'))
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>승인의 다섯 조건 가운데 하나를 더 채운다.</b> 5단계의 첫 답에서 Copilot은 승인을 받아들이는 다섯 조건 가운데 시나리오가 있는 것이 역할 하나뿐이라고 했다. 「단계에 금지가 든 조치」의 승인을 한 편으로 더한다. 아래를 보내고, 열세 편이 모두 통과하는지, 그리고 Copilot이 내가 적은 기대 가운데 명세에 근거가 없는 줄을 가려 적지 않았는지 본다. 대신 돌린 실행에서는 「상태는 승인_대기다」를 적지 않았다. 사례 S04의 근거 상태를 말하는 문장이 명세에 없다는 까닭이었다.</p>'
  + copy(P9, 'Copilot에게 보낼 요청', pre=True)
  + '<p style="margin-top:18px"><b>몇 편만 골라 실행해 본다.</b> 터미널에서 <code>python 검증/시나리오_실행.py 거절</code>을 실행하면 몇 편이 실행되는가. <code>결과/검증_결과.md</code>의 맨 위 표는 어떻게 달라지고 이력에는 어떤 줄이 더해지는가. 열두 편의 결과로 되돌리려면 어떻게 실행하면 되는가.</p>'
  '<p><b>명세의 빈 곳을 적어 본다.</b> 명세의 수용 기준에는 「긴급을 가르는 값을 읽지 못한 요청은 지금의 열 건 가운데 없어서 여기에 문장이 없다」고 적혀 있다. 오늘 열째 편이 그 경우를 실행해 보았다. 이 편을 근거로 수용 기준에 어떤 문장을 더할 수 있는가. 「명세가 먼저다」라는 규칙에 따라, 명세를 고쳐 달라는 요청은 프로그램을 고쳐 달라는 요청과 따로 보낸다.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 여섯 건과 금지 조건 대어 보기', '2. 정하고 계획 받기', '3. 여섯 편 실행', '4. 겹친 경우 다섯 편', '5. 규칙을 건드려 보기', '6. 회귀 편 더하기', '7. 실패의 원인 듣기', '8. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>명세 → 시나리오 실행 → 회귀</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-07-4-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 시나리오 실행과 회귀 검증</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
