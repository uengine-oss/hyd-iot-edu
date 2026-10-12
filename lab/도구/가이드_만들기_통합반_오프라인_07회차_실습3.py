"""통합반 오프라인 07회차 실습 3 「새로운 요구사항을 추가해도 기존 기능 유지하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json, subprocess, sys
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '07회차_실습3_명세로_요구사항_추가'
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
.tree b{color:#ffd76a}
.tree.wrap{white-space:pre-wrap;font-size:13.5px;line-height:1.75}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}
.three div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px;line-height:1.6}
.three b{display:block;color:var(--accent);font-size:15.5px;margin-bottom:4px}
.st.w{background:#eef1f5;color:#5b6573}
.copy.term .copy-top{background:#14181f;color:#e8edf5}
.copy.term .copy-text{font-family:Consolas,"D2Coding",monospace;font-size:15px}
@media(max-width:760px){.flow,.vs,.four,.pipe,.chg,.grow,.three{grid-template-columns:1fr}table.res{display:block;overflow-x:auto}.pipe span{display:none}}
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 지금의 동작과 긴급 조건을 함께 적은 spec.md, 긴급_기준.json, 그 명세대로 고친 요청_처리.py와 다시 실행한 결과, 다음 실습에 넘길 검증/시나리오.json. 다음 실습에서 이 여섯 건을 시나리오로 실행한다</b></div></div>'
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
def term(text, head='터미널에서 실행할 명령'):
    cid[0] += 1; i = f'c{cid[0]}'
    return f'<div class="copy term"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text pre" id="{i}">{e(text)}</div><div class="copy-foot">붙여넣는 곳 → VS Code 아래쪽 터미널 (보이지 않으면 메뉴의 「터미널 → 새 터미널」)</div></div>'
def box(text, marks=()):
    t = e(text)
    for m in marks: t = t.replace(e(m), f'<b>{e(m)}</b>')
    return f'<div class="tree wrap">{t}</div>'

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1, P2, P3, P4, P5, P6a, P6b, P7a, P7bad, P7, P8, P9 = (P(f'{n}_prompt.txt') for n in ('1', '2', '3', '4', '5', '6a', '6b', '7a', '7_bad', '7', '8', '9'))
i1, i2 = P1.index('같은 한 문장을'), P1.index('아직 아무')
P1rich = f'<span class="p-a">{e(P1[:i1].rstrip())}</span> <span class="p-b">{e(P1[i1:i2].rstrip())}</span> <span class="p-c">{e(P1[i2:])}</span>'
assert re.sub(r'<[^>]+>', '', P1rich) == e(P1)
CASE = R / '시작' / '사례' / '모호한_요청'
SENT = (CASE / '요청.txt').read_text(encoding='utf-8').strip()
assert SENT in P3 and SENT == P('모호한_요청/v_prompt.txt')

# ── 시작 · 완성 폴더의 파일에서 읽는 것
J = lambda p: json.loads((R / p).read_text(encoding='utf-8'))
REQ = {r['번호']: r for r in J('시작/입력/점검_요청.json')}
IN = {c['번호']: c for c in J('시작/입력/센서_입력.json')}
before = {c['번호']: c for c in J('시작/검증/변경_전/요청_처리.json')}
fin = {c['번호']: c for c in J('완성/결과/요청_처리.json')}
assert J('시작/결과/요청_처리.json') == J('시작/검증/변경_전/요청_처리.json') and len(REQ) == 10 and list(before) == list(REQ)
KEYS7 = ['번호', '상태', '사례', '질문', '근거_상태', '승인', '상태_기록']
assert all(list(c) == KEYS7 for c in before.values())
assert all(list(c) == KEYS7[:2] + ['긴급'] + KEYS7[2:] for c in fin.values())
assert all(fin[k][x] == before[k][x] for k in fin for x in KEYS7)
for f in ('에이전트.py', '도구.py', '에이전트_정의.json', '결과/점검_계획.json', '사람/답변.json', '사람/승인.json', '입력/점검_요청.json'):
    assert (R / '시작' / f).read_bytes() == (R / '완성' / f).read_bytes(), f
CR = J('완성/긴급_기준.json')
assert CR == {'경보_패턴': 'COOLER_DEGRADATION', 'tag': 'TS1', 'aggregate': 'avg', 'windowSeconds': 120, 'expect': 'gte', 'threshold': 60}
assert not (R / '시작' / '긴급_기준.json').exists() and not (R / '시작' / 'spec.md').exists()
def ts1(k): return next(r for r in IN[k]['readings'] if (r['tag'], r['aggregate'], r['windowSeconds']) == ('TS1', 'avg', 120))['value']
STC = {'확정': 's', '승인_대기': 'w', '보류': 'u', '질문_대기': 'u', '반려': 'x'}
st = lambda v: f'<span class="st {STC[v]}">{v}</span>'
cnt = {v: sum(1 for c in before.values() if c['상태'] == v) for v in STC}
assert cnt == {'확정': 1, '승인_대기': 3, '보류': 3, '질문_대기': 2, '반려': 1}
cnt_txt = f'확정 {cnt["확정"]}건, 승인 대기 {cnt["승인_대기"]}건, 보류 {cnt["보류"]}건, 질문 대기 {cnt["질문_대기"]}건, 반려 {cnt["반려"]}건'
urg = lambda v: {True: '<mark>true</mark>', False: 'false', None: '<mark>null</mark>'}[v]
assert [k for k, c in fin.items() if c['긴급'] is True] == ['R03', 'R04'] and [k for k, c in fin.items() if c['긴급'] is None] == ['R01', 'R08']
assert fin['R03']['사례'] == fin['R04']['사례'] == 'S01' and fin['R05']['사례'] == 'S07' and (ts1('S01'), ts1('S07')) == (60.7, 59.4)
assert (fin['R03']['상태'], fin['R04']['상태']) == ('확정', '승인_대기')

def run_cmp(a, b):  # 시작 폴더의 견주기를 실제로 실행해 그 출력을 받는다
    r = subprocess.run([sys.executable, str(R / '시작' / '검증' / '견주기.py'), a, b], cwd=R / '시작', capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr
    return r.stdout.rstrip()
C2 = run_cmp('검증/변경_전/요청_처리.json', '사례/모호한_요청/사본2/요청_처리.json')
C3 = run_cmp('검증/변경_전/요청_처리.json', '사례/모호한_요청/사본3/요청_처리.json')
C3p = run_cmp('결과/점검_계획.json', '사례/모호한_요청/사본3/점검_계획.json')
assert C3.splitlines()[-1] == '요약: 기존 칸이 달라진 항목 0건 · 없어진 칸 0개 · 더해진 칸 0개 · 항목의 순서 같다'
assert C2.splitlines()[-1] == '요약: 기존 칸이 달라진 항목 0건 · 없어진 칸 0개 · 더해진 칸 1개 (인터록_여유) · 항목의 순서 같다'
assert C3p.splitlines()[-1] == '요약: 기존 칸이 달라진 항목 11건 · 없어진 칸 0개 · 더해진 칸 1개 (정지_근접) · 항목의 순서 같다'
def head_tail(t, n=9): L = t.splitlines(); return '\n'.join(L[:n] + ['  …'] + L[-1:])
cmp5 = P('5_견주기.txt'); cmp7 = P('7_손으로_고친_뒤_견주기.txt')
assert cmp5.splitlines()[-1] == cmp7.splitlines()[-1] == '요약: 기존 칸이 달라진 항목 0건 · 없어진 칸 0개 · 더해진 칸 1개 (긴급) · 항목의 순서 같다'
assert '+ 더해진 칸 긴급: true' in cmp7.split('R05')[1].split('R06')[0] and '+ 더해진 칸 긴급: false' in cmp5.split('R05')[1].split('R06')[0]

# 세 사본의 견줌(사례 폴더의 파일에서 읽는다)
def todo(md, head):  # 「사람이 할 일」의 한 묶음에 적힌 요청 번호의 차례
    part = md.split('## 사람이 할 일')[1].split('\n## R01')[0]
    blk = next(b for b in part.split('### ')[1:] if b.startswith(head))
    return re.findall(r'(?m)^- (R\d\d)', blk)
md0 = (R / '시작' / '결과' / '요청_처리.md').read_text(encoding='utf-8')
tools0 = J('시작/에이전트_정의.json')['도구']
def copyinfo(n):
    d = json.loads((CASE / f'사본{n}' / '요청_처리.json').read_text(encoding='utf-8'))
    md = (CASE / f'사본{n}' / '요청_처리.md').read_text(encoding='utf-8')
    add = [k for k in d[0] if k not in KEYS7]
    same = sum(1 for c in d if all(c[k] == before[c['번호']][k] for k in KEYS7))
    files = sorted(f.name for f in (CASE / f'사본{n}').iterdir() if f.name not in ('답.md', '요청_처리.py', '요청_처리.json', '요청_처리.md'))
    tf = CASE / f'사본{n}' / '에이전트_정의.json'
    tools = [t for t in json.loads(tf.read_text(encoding='utf-8'))['도구'] if t not in tools0] if tf.exists() else []
    return dict(add=add, same=same, files=files, tools=tools, q=todo(md, '답할 질문'), a=todo(md, '승인을 기다리는 요청'), order=[c['번호'] for c in d])
c1, c2, c3 = copyinfo(1), copyinfo(2), copyinfo(3)
q0, a0 = todo(md0, '답할 질문'), todo(md0, '승인을 기다리는 요청')
assert (q0, a0) == (['R01', 'R08'], ['R02', 'R04', 'R05'])
assert (c1['add'], c2['add'], c3['add']) == (['긴급'], ['인터록_여유'], []) and c1['same'] == c2['same'] == c3['same'] == 10
assert (c1['q'], c1['a']) == (q0, a0) and (c2['q'], c2['a']) == (['R08', 'R01'], ['R04', 'R05', 'R02']) and (c3['q'], c3['a']) == (q0, ['R04', 'R05', 'R02'])
assert (c1['files'], c2['files'], c3['files']) == ([], ['도구.py', '에이전트_정의.json'], ['도구.py', '에이전트.py', '에이전트_정의.json', '점검_계획.json'])
assert (c2['tools'], c3['tools']) == (['인터록_한계'], ['정지_한계']) and all(c['order'] == list(REQ) for c in (c1, c2, c3))
assert all(c['긴급'] is False for c in json.loads((CASE / '사본1' / '요청_처리.json').read_text(encoding='utf-8')))
assert '_긴급_패턴' in (CASE / '사본1' / '요청_처리.py').read_text(encoding='utf-8')
mk = lambda new, old: (' '.join(new) if new == old else f'<mark>{" ".join(new)}</mark>')
three = ('<table class="res"><thead><tr><th style="width:150px"></th><th>사본 1</th><th>사본 2</th><th>사본 3</th></tr></thead><tbody>'
  '<tr><td><b>긴급의 기준을 둔 곳</b></td><td>프로그램 안의 목록(트립 경보 셋). 지금 요청 가운데 해당하는 것이 없다</td><td>새 도구로 읽은 인터록 한계. 가르는 선은 없고 차례만 매겼다</td><td>새 도구로 읽은 정지 한계. 가르는 선은 없고 차례만 매겼다</td></tr>'
  f'<tr><td><b>요청 결과에 더한 칸</b></td><td><code>긴급</code> (열 건 모두 false)</td><td><mark><code>인터록_여유</code></mark> (칸이 여럿인 묶음)</td><td>없음</td></tr>'
  f'<tr><td><b>「답할 질문」의 차례</b><br><small>고치기 전 {" ".join(q0)}</small></td><td>{mk(c1["q"], q0)}</td><td>{mk(c2["q"], q0)}</td><td>{mk(c3["q"], q0)}</td></tr>'
  f'<tr><td><b>「승인을 기다리는 요청」의 차례</b><br><small>고치기 전 {" ".join(a0)}</small></td><td>{mk(c1["a"], a0)}</td><td>{mk(c2["a"], a0)}</td><td>{mk(c3["a"], a0)}</td></tr>'
  f'<tr><td><b>요청_처리.py 말고 고친 파일</b></td><td>없음</td><td><mark>도구.py, 에이전트_정의.json</mark><br><small>허용 목록에 <code>{c2["tools"][0]}</code></small></td><td><mark>도구.py, 에이전트_정의.json, 에이전트.py, 점검 계획 결과</mark><br><small>허용 목록에 <code>{c3["tools"][0]}</code></small></td></tr>'
  f'<tr><td><b>질문과 승인</b></td><td>기존 일곱 칸이 {c1["same"]}건 모두 그대로</td><td>기존 일곱 칸이 {c2["same"]}건 모두 그대로</td><td>기존 일곱 칸이 {c3["same"]}건 모두 그대로</td></tr>'
  '</tbody></table>')

# 명세에서 옮기는 줄
def spec_lines(path, ids):
    L = (R / path).read_text(encoding='utf-8').splitlines(); out = []
    for i in ids:
        m = [l for l in L if l.startswith(f'- {i}. ') or l.startswith(f'{i}. ')]; assert len(m) == 1, (path, i, len(m)); out.append(m[0].lstrip('- '))
    return '\n'.join(out)
def sect(s, name): return s.split(f'\n## {name}\n')[1].split('\n## ')[0]
spec0, spec1 = (R / '기록' / '2_spec.md').read_text(encoding='utf-8'), (R / '완성' / 'spec.md').read_text(encoding='utf-8')
assert spec1 == (R / '기록' / '4_spec.md').read_text(encoding='utf-8') and '긴급' not in spec0
heads = [l[3:] for l in spec1.splitlines() if l.startswith('## ')]; assert heads == ['요구사항', '입력 계약', '출력 계약', '금지 조건', '수용 기준']
nA = lambda s: len(re.findall(r'(?m)^- AC-\d+\. ', s)); nF = lambda s: len(re.findall(r'(?m)^\d+\. ', sect(s, '금지 조건')))
assert (nF(spec0), nA(spec0), nF(spec1), nA(spec1)) == (10, 37, 18, 50)
F = lambda path, ids: '\n'.join('금지 ' + l for l in spec_lines_f(path, ids))
def spec_lines_f(path, ids):
    L = sect((R / path).read_text(encoding='utf-8'), '금지 조건').splitlines(); out = []
    for i in ids:
        m = [l for l in L if l.startswith(f'{i}. ')]; assert len(m) == 1; out.append(m[0])
    return out
urgent_rule = next(l for l in spec1.splitlines() if l.startswith('- 긴급의 기준은 하나다.'))[2:]
quick_rule = next(l for l in spec1.splitlines() if l.startswith('- 「빨리 처리」는'))[2:]

# 요청 열 건의 표
PAT = {'COOLER_DEGRADATION': '쿨러 성능 저하', 'PUMP_LEAKAGE': '펌프 내부 누설', 'FAN_VIBRATION': '팬 진동 상승', 'OIL_ANALYSIS': '오일 분석'}
SEE0 = {'R01': '맞는 사례가 둘이어서 물었고, 아직 답이 없다', 'R02': '운전원이 올린 승인은 그 조치의 승인 역할(공장장)과 달라 반영되지 않았다', 'R03': '운전원이 SOP-COOL-11을 승인했다',
        'R04': '<b>두 번 묻고 답을 받아 사례가 정해졌다.</b> 결정은 아직 없다', 'R05': '적힌 사례가 적힌 설비와 어긋나 물었고, 답을 받아 S07로 정해졌다', 'R06': '답을 받아 사례는 정해졌으나 근거 상태가 UNKNOWN이다',
        'R07': '생산관리자가 사유를 적어 거절했다', 'R08': '맞는 사례가 없어 선택지 없는 질문을 내고 멈췄다', 'R09': '맞는 근거가 없다(UNSUPPORTED)', 'R10': '증거가 등록되지 않은 원인뿐이다(UNKNOWN)'}
t0 = ('<table class="res"><thead><tr><th style="width:70px">요청</th><th style="width:110px">상태</th><th style="width:70px">사례</th><th>지금의 상태가 된 까닭</th></tr></thead><tbody>'
      + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td class="nw">{st(c["상태"])}</td><td class="nw">{c["사례"] or "<small>미정</small>"}</td><td>{SEE0[k]}</td></tr>' for k, c in before.items()) + '</tbody></table>')
def pat(c): return IN[c['사례']]['경보_패턴'] if c['사례'] else None
SEE1 = {'R01': '<b>가르지 못했다.</b> 요청에 펌프 누설이라고 적혀 있어도 사례가 정해지지 않았다', 'R03': '<b>긴급.</b> 60.7은 60 이상이다. 확정인 것은 승인이 있어서다',
        'R04': '<b>긴급인데 승인 대기다.</b> 같은 사례 S01인데 결정이 없다', 'R05': '<b>기준 곁의 값.</b> 59.4는 60 이상이 아니다', 'R08': '<b>가르지 못했다.</b> 사례가 정해지지 않았다'}
def tcell(c):
    if not c['사례']: return '<small>사례 미정</small>'
    return str(ts1(c['사례'])) if pat(c) == CR['경보_패턴'] else '<small>읽지 않는다</small>'
t1 = ('<table class="res"><thead><tr><th style="width:70px">요청</th><th style="width:150px">사례 · 경보 패턴</th><th style="width:110px">유온 2분 평균</th><th style="width:70px">긴급</th><th style="width:110px">상태</th><th>볼 것</th></tr></thead><tbody>'
      + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td class="nw">{c["사례"] or "—"}<br><small>{PAT[pat(c)] if c["사례"] else ""}</small></td><td class="nw">{tcell(c)}</td><td class="nw">{urg(c["긴급"])}</td><td class="nw">{st(c["상태"])}</td><td>{SEE1.get(k, "경보 패턴이 달라 false다" if pat(c) != CR["경보_패턴"] else "60 미만이다")}</td></tr>' for k, c in fin.items()) + '</tbody></table>')

# 시나리오
SC = J('완성/검증/시나리오.json')
assert [(s['경우'], s['요청']) for s in SC] == [('정상', 'R05'), ('긴급', 'R03'), ('긴급', 'R04'), ('미입력', 'R01'), ('미입력', 'R08'), ('거절', 'R07')]
assert all(list(s) == ['경우', '요청', '주어진_것', '기대'] and list(s['기대']) == ['상태', '긴급', '사례', '근거_상태'] and all(fin[s['요청']][k] == v for k, v in s['기대'].items()) for s in SC)
tsc = ('<table class="res"><thead><tr><th>경우</th><th>요청</th><th>기대하는 상태</th><th>기대하는 긴급</th><th>기대하는 사례</th><th>기대하는 근거 상태</th></tr></thead><tbody>'
       + ''.join(f'<tr><td class="nw"><b>{s["경우"]}</b></td><td class="nw">{s["요청"]}</td><td class="nw">{st(s["기대"]["상태"])}</td><td class="nw">{urg(s["기대"]["긴급"])}</td><td class="nw">{s["기대"]["사례"] or "null"}</td><td class="nw"><code>{s["기대"]["근거_상태"] or "null"}</code></td></tr>' for s in SC) + '</tbody></table>')

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>긴급의 기준</b></td><td><mark>1번 줄</mark> 사례가 정해졌고, 그 사례의 경보 패턴이 쿨러 성능 저하이고, 유온 TS1의 최근 120초 평균이 60 이상이다. 수업에서 본 예와 같은 기준이다</td><td>기준값을 59로 낮추면 R05(사례 S07, 59.4)도 긴급이 된다. 수치 없이 「유온이 높으면」이라고만 적으면 사본 2 · 3처럼 AI가 선을 정하거나 선 없이 차례만 매긴다</td></tr>
<tr><td><b>경보 패턴이 다른 요청</b></td><td><mark>2번 줄</mark> false로 적는다</td><td>「null로 적는다」로 바꾼다. 그러면 null이 「가르지 못했다」와 「볼 대상이 아니다」 두 뜻을 함께 갖게 된다</td></tr>
<tr><td><b>사례가 정해지지 않은 요청</b></td><td><mark>3번 줄</mark> null로 적는다. 요청에 적힌 경보 패턴이나 요청 글로 미리 가르지 않는다. R01과 R08이 여기에 든다</td><td>「요청에 적힌 경보 패턴으로 먼저 가른다」로 바꾸면 빠진 값을 짐작해 채우는 일이 되어 규칙의 3번이 막는다. 고를 수 없는 쪽이다</td></tr>
<tr><td><b>값을 읽지 못한 요청</b></td><td><mark>4번 줄</mark> null로 적고 다른 칸은 건드리지 않는다</td><td>「질문을 하나 더 낸다」로 바꾸면 그 요청의 <code>질문</code>과 <code>상태</code>가 변경 전과 달라진다. 지금의 열 건에는 이 경우가 없어 결과로 확인할 수는 없다</td></tr>
<tr><td><b>긴급일 때 달라지는 것</b></td><td><mark>5번 줄</mark> 긴급 칸과 md의 한 줄뿐이다. 상태, 질문, 승인, 요청의 순서, 「사람이 할 일」의 차례는 그대로다</td><td>이 줄은 그대로 두기를 권한다. 요청의 순서와 md의 다른 줄, 질문과 승인을 줄이는 것은 규칙이 막아 두어 고를 수 없다</td></tr>
<tr><td><b>수용 기준의 예</b></td><td><mark>6번 줄</mark> 긴급이고 확정 R03, 긴급이고 승인 대기 R04, 긴급이 아닌 냉각 경보 R05, 패턴이 다른 R02, 사례 미정 R01</td><td>R05 대신 R07(사례 S03, 58.6)을 적을 수 있다. R05는 기준과 0.6 차이여서 59와 60을 헷갈린 것까지 잡는다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 7회차 · 실습 3 · 50분</small>명세를 먼저 고치고,<br>그 명세대로 새 요구를 더한다',
 f'앞 실습에서 만든 <code>요청_처리.py</code>는 빠진 값이 있으면 사람에게 묻고 멈추고, 답을 받으면 이어서 처리하고, 사람이 승인하기 전에는 확정으로 적지 않는다. 지금 잘 돈다. 여기에 요구 하나가 들어온다. 「{SENT}」 이 한 문장을 그대로 AI에게 넘기면 무엇이 달라지는지를 먼저 보고, 같은 요구를 <b>명세(spec.md)에 먼저 적은 다음</b> 그 명세대로 고친다. 무엇이 긴급인지, 긴급이면 무엇이 달라지고 무엇은 그대로인지는 <b>내가 정한다.</b>',
 [('끝나면 남는 것', 'spec.md, 긴급_기준.json, 고친 요청_처리.py와 다시 실행한 결과, 검증/시나리오.json'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '앞 실습(질문하는 에이전트)을 마쳤다'), ('준비에 쓰는 시간', '약 4분')])
+ '<section class="sect"><h2>오늘 하는 것</h2><p>프로그램을 고치기 전에 문서를 고친다. 문서에는 달라질 것뿐 아니라 <b>달라지면 안 되는 것</b>을 적는다. 고친 뒤에는 그 문서의 문장을 하나씩 결과에 대어 본다. 오늘 지킬 「기존 기능」은 앞 실습에서 내가 만든 질문과 승인의 동작이다.</p>'
  '<div class="pipe"><div><b>지금의 요청 처리</b>요청 열 건, 결과의 칸 일곱. 질문 · 보류 · 승인이 이미 돌아간다<small>요청_처리.py · 결과/요청_처리.json</small></div><span>+</span><div><b>새 요구 한 문장</b>긴급의 기준도, 빨라지는 방법도, 그대로 둘 것도 적혀 있지 않다<small>사례/모호한_요청/요청.txt</small></div><span>→</span><div class="out"><b>명세와 그 명세대로 고친 프로그램</b>칸 하나가 더해지고 일곱 칸은 변경 전과 같다<small>spec.md · 긴급_기준.json · 검증/시나리오.json</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 명세와 결과가 맞는지 판단하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>같은 한 문장으로 고친 세 사본을 읽고 견주게 한다</div><div><em>2</em><b>정해 준다</b>지금의 동작을 명세로 적게 하고, 긴급의 빈자리 여섯을 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>명세가 곧 계획이다. 프로그램보다 먼저 고치고 읽는다</div><div><em>4</em><b>작게 만든다</b>명세대로 고쳐 실행하고, 변경 전과 견준다</div><div><em>5</em><b>되돌려 준다</b>명세와 어긋난 곳을 찾아 어느 쪽을 고칠지 말한다</div></div>'
  '<p style="margin:18px 0 0">1~5단계와 7단계가 이 다섯 걸음이다. 그 사이에 규칙에 어긋나는 요청을 일부러 보내 보고(6단계), 끝으로 다음 실습에 넘길 입력과 기대 결과를 저장한다(8단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 앞 실습을 마친 폴더에 두 폴더(<code>검증</code>, <code>사례</code>)가 더해져 있다.</p>'
 '<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙 (이번 실습의 것)</i>\n├─ 요청_처리.py                <i>← 앞 실습에서 만든 처리 고리</i>\n├─ 에이전트.py · 도구.py · 에이전트_정의.json  <i>← 5회차의 에이전트 (고치지 않는다)</i>\n├─ <span>입력/</span>                      <i>← 점검 요청 10건, 센서 입력 11건</i>\n├─ <span>사람/</span>                      <i>← 사람이 쓰는 답변.json · 승인.json</i>\n├─ <span>온톨로지/</span>\n├─ <span>결과/</span>                      <i>← 지금의 요청_처리 · 점검_계획</i>\n├─ <span>검증/</span>                      <i>← 새로 더해졌다</i>\n│  ├─ 견주기.py                <i>← 두 결과를 칸마다 대어 보는 프로그램</i>\n│  └─ 변경_전/요청_처리.json   <i>← 고치기 전의 결과</i>\n└─ <span>사례/</span>                      <i>← 새로 더해졌다. 한 문장으로 고쳐 본 사본 셋</i></div>'
 '<div><p><b>규칙 파일</b>은 앞 실습의 규칙을 그대로 잇는다. 사람이 쓰는 파일을 대신 쓰지 않는다, 승인 없이 확정으로 적지 않는다, 이어받은 에이전트를 고치지 않는다. 여기에 오늘의 중심인 6번이 더해졌다. 명세에 적히지 않은 변경은 프로그램에 넣지 않는다. 「정해져 있지 않은 것」의 다섯 줄은 일부러 비워 둔 자리다. 3단계에서 Copilot이 이것을 물어 오고 내가 채운다.</p>'
 '<p><b>앞 실습의 끝과 달라진 것은 하나다.</b> <code>사람/답변.json</code>에 R04의 둘째 질문에 대한 답(S01)이 한 건 더 들어와 있다. 그래서 R04가 질문 대기에서 승인 대기로 올라와 있다.</p><p><b>완성 폴더</b>도 함께 받았다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 입력, 사람, 온톨로지, 결과, 검증, 사례 폴더와 요청_처리.py가 보이게. 검증 폴더는 펼쳐 둔다.'))
+ do(2, 'editor', 'VS Code · 편집기', '지금의 결과에서 요청 열 건의 상태를 다시 본다',
 f'<p><code>결과/요청_처리.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 바꾼다. 맨 위에 「사람이 할 일」이 있고 그 아래로 요청마다 한 절이다. 지금은 {cnt_txt}이다. 「사람이 할 일」의 「승인을 기다리는 요청」에 R02, R04, R05가 이 차례로 적혀 있는 것도 보아 둔다. 오늘 고친 뒤에도 이 표와 그 차례가 달라지지 않아야 한다.</p>' + t0)
+ do(3, 'editor', 'VS Code · 터미널', '견주기를 한 번 실행해 본다',
 '<p>메뉴의 「터미널 → 새 터미널」을 누르면 아래쪽에 터미널이 열린다. 아래 명령을 붙여넣고 Enter를 누른다. 견주기는 고치기 전의 결과와 지금의 결과를 요청마다 칸마다 대어 본다. 아직 아무것도 고치지 않았으므로 마지막 줄이 아래와 같아야 한다.</p>'
 + term('python 검증/견주기.py') + box(run_cmp('검증/변경_전/요청_처리.json', '결과/요청_처리.json').splitlines()[-1])
 + ifs(('python을 찾을 수 없다고 나오면', '<code>python</code> 대신 <code>python3</code> 또는 <code>py</code>로 실행한다. 뒤의 단계에서도 같은 것으로 바꿔 쓴다.'), ('파일이 없다고 나오면', '터미널의 위치가 <code>시작</code> 폴더가 아닌 것이다. VS Code에서 연 폴더가 <code>시작</code>인지 본다.')))
+ nxt(1, '1. 같은 한 문장이 만든 세 결과를 견준다'))

# ───────── 1단계
pages.append(hero('1단계', '같은 한 문장이 만든<br>세 결과를 견준다',
 f'<code>사례/</code> 폴더에는 지금의 폴더를 그대로 복사한 사본 셋에 「{SENT}」 한 문장만 보낸 기록이 있다. 규칙 파일과 명세는 넣지 않았다. 세 사본이 받은 문장은 글자 하나 다르지 않다. 내 프로그램을 고치기 전에, <b>그 문장이 정하지 않은 것을 누가 어떻게 정했는지</b>부터 본다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '세 사본이 서로 어떻게 다른지와, 문장에 적혀 있지 않았던 것의 목록이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일, 고친 파일')])
+ do(1, 'editor', 'VS Code · 터미널', '사본 둘을 변경 전과 견준다',
 '<p>한 줄씩 붙여넣어 실행하고, 출력의 맨 아래 「요약」 줄을 본다. 첫 줄은 사본 2의 요청 결과, 둘째 줄은 사본 3의 요청 결과, 셋째 줄은 사본 3의 점검 계획(5회차의 에이전트가 낸 것)이다.</p>'
 + term('python 검증/견주기.py 검증/변경_전/요청_처리.json 사례/모호한_요청/사본2/요청_처리.json\npython 검증/견주기.py 검증/변경_전/요청_처리.json 사례/모호한_요청/사본3/요청_처리.json\npython 검증/견주기.py 결과/점검_계획.json 사례/모호한_요청/사본3/점검_계획.json')
 + '<p style="margin-top:18px">세 실행의 요약 줄은 아래와 같다(이 폴더의 파일로 실행한 출력이다).</p>' + box('사본 2 · 요청 결과\n' + C2.splitlines()[-1] + '\n\n사본 3 · 요청 결과\n' + C3.splitlines()[-1] + '\n\n사본 3 · 점검 계획\n' + C3p.splitlines()[-1], ('더해진 칸 1개 (인터록_여유)', '기존 칸이 달라진 항목 11건', '더해진 칸 1개 (정지_근접)'))
 + find(('사본 3의 요청 결과는 왜 「0건 · 0개」인가', '요청 결과 파일은 글자 하나 바뀌지 않았다. 그런데 셋째 줄을 보면 점검 계획의 사례 열한 건이 모두 달라졌다. 5회차의 에이전트를 고쳐 다시 돌린 것이다. 견주기는 내가 대어 보라고 한 파일만 본다.'),
        ('사본 2는 무엇을 더했는가', '<code>긴급</code>이 아니라 <code>인터록_여유</code>라는 칸이다. 이 결과를 받아 쓰는 사람이나 프로그램은 「긴급한 경보」가 어느 것인지를 여전히 알 수 없다.'),
        ('견주기가 보지 않는 것', '세 줄 모두 json을 댄 것이다. 사람이 읽는 <code>요청_처리.md</code>의 「사람이 할 일」이 어떻게 바뀌었는지는 여기에 나오지 않는다. 다음 할 일에서 Copilot에게 읽게 한다.')))
+ do(2, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다. 앞 실습의 대화가 남아 있으면 새 대화를 연다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸', '세 사본을 읽고 견주게 한다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 답이 오는 데 1분 반쯤 걸린다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일과 지금의 프로그램, 그리고 세 사본의 답 · 고친 프로그램 · 결과. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '표의 줄 넷을 정해 주었다. 긴급의 뜻, 결과의 칸과 차례, 질문과 승인, 고친 파일의 범위다. 수업에서 본 「한 문장의 세 가지 해석」이 실제로 어디에서 갈렸는지를 보려는 것이다.'), ('하지 말 것', '파일을 만들거나 고치지 말 것. 이 문장이 없으면 읽은 김에 고치기 시작한다.')))
+ do(4, 'chat', 'Copilot 채팅 · 답', '답을 아래 표와 맞추고, 문장에 없던 것을 센다',
 '<p>아래 표는 <code>사례/</code> 폴더의 파일에서 옮긴 것이다. Copilot의 표가 이것과 같은 사실을 말하는지 본다. 문장은 사람마다 다르게 나온다.</p>' + three
 + shot('1단계 요청에 대한 Copilot의 답. 세 사본을 견준 표와, 그 아래 「문장에 없어서 사본마다 다르게 정해진 것」 목록이 보이게(길면 두 장).')
 + find(('「긴급한 경보」가 어느 것인지 답이 나왔는가', '사본 1의 기준으로는 지금 요청 가운데 긴급이 하나도 없다. 사본 2와 3은 차례만 매겼을 뿐 얼마부터가 긴급인지는 정하지 않았다. 세 사본 어디에도 「이 요청이 긴급이다」는 없다.'),
        ('사람이 할 일의 차례가 바뀌었는가', '사본 2와 3에서는 승인을 기다리는 요청이 R04, R05, R02의 차례가 되었다. 받은 차례대로 읽던 사람에게는 말없이 바뀐 것이다. 사본 2에서는 답할 질문의 차례도 뒤바뀌었다.'),
        ('고쳐서는 안 되는 것을 고쳤는가', '사본 2는 도구와 허용 목록을, 사본 3은 5회차의 에이전트와 그 점검 계획까지 고쳤다. 앞 실습의 규칙이 「이어받은 에이전트는 고치지 않는다」고 한 것들이다. 사본에는 그 규칙이 없었다.'),
        ('답에 적힌 말과 실제가 같은가', 'Copilot이 사본의 <code>답.md</code>만 믿지 않고 파일을 직접 대어 보았는가. 대신 돌린 실행에서는 사본 3의 답에 <code>에이전트.py</code>를 고쳤다는 말이 빠져 있다는 것을 찾아냈다. 문장에 없어서 다르게 정해진 것은 열두 가지로 모았다.'))
 + note('질문이나 승인을 줄인 사본은 없었다', '수업에서는 「빨리 처리」가 승인 생략으로 읽힐 수 있다고 했다. 이 세 번의 실행에서는 그렇게 읽은 사본이 없고, 기존 일곱 칸은 셋 모두 그대로다. 다만 그렇게 하라고 적어 준 사람은 없다. 사본 1은 답의 끝에서 「그쪽을 뜻한다면 따로 말해 달라」고 물었다. 일어나지 않은 것은 그때의 AI가 조심스러웠기 때문이고, 막아 둔 것은 아니다.')
 + ifs(('파일이 생기거나 바뀌었다면', '요청의 마지막 문장이 빠진 것이다. 터미널에서 <code>python 검증/견주기.py</code>를 실행해 「달라진 항목 0건 · 더해진 칸 0개」인지 보고, 다르면 시작 폴더를 새로 받아 다시 연다.'),
       ('표의 사실이 다르다면', '「다시 해 줘」라고 하지 않는다. 「사본 3이 요청_처리.json을 고쳤다고 했는데 견주기 출력은 0건이야. 다시 봐 줘.」처럼 어디가 어떻게 다른지를 말한다.')))
+ nxt(2, '2. 지금의 동작을 먼저 명세로 적게 한다', 0))

# ───────── 2단계
pages.append(hero('2단계', '지금의 동작을<br>먼저 명세로 적게 한다',
 '새 요구를 적기 전에, 지금 무엇이 돌아가고 있는지를 문서로 만든다. 「기존 기능을 지킨다」고 말하려면 기존 기능이 무엇인지가 적혀 있어야 한다. 앞 실습에서 내가 정한 것들(무엇을 묻는지, 어떤 승인을 받아들이는지)은 지금 프로그램 안에만 있다. 명세의 절은 수업에서 본 다섯이다. 요구사항, 입력 계약, 출력 계약, 금지 조건, 수용 기준. 이번 요청에는 <b>긴급을 한 줄도 적지 않는다.</b>',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '지금의 동작만 적힌 spec.md가 있다'), ('바뀌면 안 되는 것', '프로그램, 결과 파일')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '절마다 무엇을 적을지 정해 주고 명세를 만들게 한다',
 '<p>복사해 보낸다. 답이 오는 데 3분쯤 걸린다. 기다리는 동안 <code>결과/요청_처리.md</code>에서 R04의 「상태 기록」을 읽어 둔다. 접수에서 승인 대기까지 네 줄이다.</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abc'))
 + parts(('무엇을 만드는가', '첫 문단. 지금 하는 일만 적는다고 범위를 그었다. 새 요구와 섞어 쓰면 어느 줄이 원래 있던 약속인지 가릴 수 없게 된다.'), ('절마다 무엇을 적는가', '둘째 문단. 금지 조건에 넣을 세 가지와, 수용 기준에 들어가야 할 일곱 경우를 짚어 주었다. 일곱 경우가 준비 단계에서 본 표의 상태들이다.'), ('어떻게 확인하고 쓰는가', '셋째 문단. 프로그램을 읽은 것만으로 적지 말고 결과의 실제 값과 대어 보게 했다. 망설인 곳을 알려 달라고 한 것은 프로그램 속에 묻힌 결정을 드러내게 하려는 것이다.')))
+ do(2, 'editor', 'VS Code · 편집기', '만들어진 명세에서 네 가지를 찾는다',
 f'<p>탐색기에 <code>spec.md</code>가 생겼다. 열어서 미리 보기로 본다. 문장과 번호는 사람마다 다르게 나온다. 대신 돌린 실행에서는 금지 조건 {nF(spec0)}줄, 수용 기준 {nA(spec0)}문장이었고, 그 가운데 몇 줄이 아래와 같았다.</p>'
 + box(F('기록/2_spec.md', [1, 4]) + '\n' + spec_lines('기록/2_spec.md', ['AC-15', 'AC-26']), ('금지 1.', '금지 4.', 'AC-15.', 'AC-26.'))
 + shot('spec.md의 미리 보기를 연 VS Code 화면. 「금지 조건」 절과 「수용 기준」 절의 앞부분이 보이게.')
 + find(('절이 다섯인가', '요구사항, 입력 계약, 출력 계약, 금지 조건, 수용 기준. 이름과 차례는 규칙 파일이 정해 두었다.'),
        ('금지 조건에 승인과 사람의 파일이 있는가', '「승인이 없는 요청을 확정으로 적지 않는다」와 「사람이 쓰는 두 파일을 쓰지 않는다」가 적혀 있는가. 이 줄들이 뒤에서 「빨리」를 승인 생략으로 읽는 길을 막는다.'),
        ('수용 기준을 내 눈으로 가를 수 있는가', '문장 하나를 골라 <code>결과/요청_처리.json</code>에서 직접 확인해 본다. 예를 들어 「승인 역할이 공장장인 조치를 운전원이 승인한 R02는 확정이 아니라 승인 대기다」. R02의 <code>상태</code>를 찾으면 참인지 거짓인지가 나온다. 「잘 동작한다」처럼 가를 수 없는 문장이 있다면 고쳐 달라고 한다.'),
        ('망설인 곳을 알렸는가', '답의 끝에 「이렇게 적었지만 의도한 것인지 확인해 달라」는 목록이 있는가. 대신 돌린 실행에서는 아홉 가지였다. 「틀린 답을 고치려면 새 항목을 더하는 것이 아니라 첫 항목을 고쳐야 한다」처럼, 앞 실습에서 정해 놓고도 어디에도 적지 않은 것이 드러난다.'))
 + ifs(('긴급에 대한 줄이 들어 있다면', '1단계에서 사례를 읽은 영향이다. 「이번에는 지금 하는 일만 적기로 했어. 긴급에 대한 줄은 모두 빼 줘.」라고 말한다.'),
       ('프로그램이나 결과가 바뀌었다면', '터미널에서 <code>python 검증/견주기.py</code>를 실행한다. 「달라진 항목 0건 · 더해진 칸 0개」가 아니면 무엇을 왜 고쳤는지 묻고 되돌리게 한다.')))
+ nxt(3, '3. 새 요구를 그대로 보내 보고, 빈자리를 내가 정한다', 1))

# ───────── 3단계
pages.append(hero('3단계', '새 요구를 그대로 보내 보고,<br>빈자리를 내가 정한다',
 '이제 그 한 문장을 내 폴더에 보낸다. 사례의 사본과 다른 점은 둘이다. 이 폴더에는 규칙 파일이 있고, 방금 만든 명세가 있다. 같은 문장에 Copilot이 무엇을 하는지를 먼저 보고, 되물어 온 것을 내가 정해 <b>명세에만</b> 적게 한다. 프로그램은 아직 고치지 않는다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', 'spec.md에 긴급 조건이 더해져 있다'), ('바뀌면 안 되는 것', '프로그램, 결과 파일. 긴급_기준.json도 아직 없다')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '사본이 받은 것과 같은 문장을 보낸다',
 '<p>세 사본이 받은 문장 그대로다. 보내기 전에 짐작해 둔다. 사본들처럼 바로 고칠까, 물을까.</p>' + copy(P3)
 + shot('한 문장 요청에 Copilot이 아무것도 고치지 않고 답한 화면. 「정해 주셔야 할 것」 목록과 「규칙이 막는 것」에 테두리를 얹는다.')
 + find(('고치지 않았는가', '답의 끝에 고친 파일이 없다고 적혀 있는가. 탐색기에서 <code>요청_처리.py</code>에 바뀐 표시가 없는지도 본다.'),
        ('무엇을 물었는가', '물음의 수를 센다. 대신 돌린 실행에서는 다섯이었다. 긴급의 기준, 사례가 정해지지 않은 요청, 값을 읽지 못한 요청, 긴급일 때 달라지는 것, 수용 기준의 예다. 규칙 파일의 「정해져 있지 않은 것」 다섯 줄과 같다.'),
        ('「빨리」에서 무엇이 막힌다고 했는가', '질문이나 승인을 줄이는 것, 요청의 순서를 바꾸는 것, 「사람이 할 일」에서 긴급한 요청을 앞으로 올리는 것. 사본 2와 3이 한 일이 셋째에 든다. 그래서 규칙 안에서 「빨리」가 뜻할 수 있는 것이 무엇이라고 했는지 읽는다.')))
+ do(2, 'chat', '이 화면의 표 → Copilot 채팅', '여섯 빈자리마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. Copilot의 첫 물음에 딸려 있던 「경보 패턴이 다른 요청」을 따로 떼어 여섯 줄로 적었다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 명세와 결과는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 5번 줄의 「빨리는 받아 보는 사람이 긴급한 건을 바로 알아보게 하는 데까지다」가 그 한 문장의 「빨리」를 내가 풀이한 것이다.'))
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '정한 것을 보내고, 명세만 고치게 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다). 답이 오는 데 2분쯤 걸린다.</p>'
 + copy(P4, pre=True, rich=richpre(P4, 'ab'))
 + parts(('무엇을 정했는가', '첫 문단. 번호를 붙여 한 줄에 결정 하나씩 적었다. 1번 줄에는 수치와 방향(이상)까지 들어 있다. 3번 줄은 앞 실습의 「빠진 값을 짐작해 채우지 않는다」를 긴급에도 잇는 줄이다.'), ('어디를 어디까지 고치는가', '둘째 문단. 명세만, 그것도 더하기만 하게 했다. 금지 조건은 줄어들면 안 된다고 못 박았다. 요구사항은 요구가 올 때마다 늘어나지만 금지 조건은 남아야 하기 때문이다. 수용 기준에는 「기존 일곱 칸과 순서가 변경 전과 같다」를 견주기로 확인하는 문장을 넣게 했다.')))
+ do(4, 'editor', 'VS Code · 편집기', '명세에 더해진 줄을 읽는다',
 f'<p><code>spec.md</code>를 다시 연다. 프로그램을 고치기 전에 읽는 이 문서가 오늘의 계획서다. 대신 돌린 실행에서는 금지 조건이 {nF(spec0)}줄에서 {nF(spec1)}줄로, 수용 기준이 {nA(spec0)}문장에서 {nA(spec1)}문장으로 늘었다. 아래는 완성 폴더의 <code>spec.md</code>에서 옮긴 몇 줄이다.</p>'
 + box(urgent_rule + '\n' + quick_rule + '\n' + F('완성/spec.md', [11, 13]) + '\n' + spec_lines('완성/spec.md', ['AC-38', 'AC-41', 'AC-42', 'AC-44', 'AC-48']), ('긴급의 기준은 하나다.', '「빨리 처리」는', '금지 11.', '금지 13.', 'AC-38.', 'AC-41.', 'AC-42.', 'AC-44.', 'AC-48.'))
 + shot('긴급 조건이 더해진 spec.md의 미리 보기. 요구사항의 「긴급」 소절(기준 표와 가르는 차례 표)이 보이게.')
 + find(('있던 줄이 줄지 않았는가', '금지 조건의 앞쪽 줄이 그대로 있는가. Copilot이 「고친 줄」을 따로 알렸는가. 대신 돌린 실행에서는 여섯 줄을 고쳤다고 밝혔다. 「칸은 일곱」이 「여덟」이 되는 것처럼 새 칸 때문에 달라질 수밖에 없는 줄들이다.'),
        ('긴급이어도 승인을 기다리는가', '금지 조건에 「긴급이라는 것으로 승인을 대신하지 않는다」가 새로 들어갔는가. 수용 기준에 「긴급이지만 결정이 없는 R04는 확정이 아니라 승인 대기다」가 있는가.'),
        ('확인할 예가 없는 줄이 있는가', '「값을 읽지 못한 요청은 null」은 지금의 열 건으로는 확인할 수 없다. 신선도가 넘은 사례 S09로 정해진 요청이 없기 때문이다. Copilot이 이것을 「비어 있는 곳」으로 알렸는지 본다. 명세에 적었다고 해서 확인된 것은 아니다.'),
        ('정해 주지 않았는데 적은 것', '여섯 가지 밖에서 Copilot이 스스로 적은 것이 있으면 답에 밝혔는가. 대신 돌린 실행에서는 넷이었다. 예: md의 긴급 줄을 「예 · 아니오 · 가리지 못함」으로 적는다. 받을지 말지는 내가 정한다.'))
 + ifs(('프로그램까지 고쳤다면', '요청의 「아직 고치지 마」가 빠진 것이다. 무엇을 고쳤는지 묻고, 명세를 읽을 때까지 프로그램은 원래대로 돌려 달라고 한다.'),
       ('금지 조건이 줄었거나 고쳐 쓰였다면', '어느 줄이 어떻게 달라졌는지를 말하고 되돌리게 한다. 「금지 조건 4번이 없어졌어. 있던 금지 조건은 그대로 두기로 했어.」')))
+ nxt(4, '4. 명세대로 고치고, 변경 전과 견준다', 2))

# ───────── 4단계
pages.append(hero('4단계', '명세대로 고치고,<br>변경 전과 견준다',
 '이제 프로그램을 고친다. 요청은 짧다. 무엇을 어떻게 만들지는 이미 명세에 있기 때문이다. 고친 뒤에는 두 가지로 확인한다. 견주기는 <b>기존 칸이 그대로인지</b>를 보고, 수용 기준은 <b>새 동작이 정한 대로인지</b>를 본다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '결과에 긴급 칸이 더해져 있고, 기존 일곱 칸은 변경 전과 같다'), ('바뀌면 안 되는 것', '에이전트.py, 도구.py, 에이전트_정의.json, 점검 계획, spec.md')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '명세대로 고치고, 실행하고, 대어 보게 한다',
 '<p>3단계에서 Copilot이 스스로 적은 것 가운데 받지 않을 것이 있으면 첫 문장을 고쳐 쓴다. 없으면 그대로 보낸다. 답이 오는 데 2분쯤 걸린다.</p>'
 + copy(P5, pre=True, rich=richpre(P5, 'abc'))
 + parts(('무엇을 기준으로', '첫 문단. 「spec.md대로」 한마디가 요구의 전부다. 한 문장으로 온 요구와 길이는 비슷하지만, 이번에는 그 뒤에 문서가 있다.'), ('어디까지', '둘째 문단. 할 일을 둘로 좁히고, 그 밖을 고쳐야 한다면 멈추고 말하게 했다. 사본 2와 3은 여기서 새 도구를 만들고 에이전트를 고쳤다.'), ('무엇으로 확인하는가', '셋째 문단. 견주기의 출력을 줄이지 말고 보여 달라고 했고, 수용 기준을 문장마다 가르게 했다. 거짓이 나와도 스스로 고치지 말라고 한 것은, 명세가 틀렸는지 프로그램이 틀렸는지를 내가 정해야 하기 때문이다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 무엇을 하려는지 읽고 허용한다',
 '<p>파일을 만들거나 고칠 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 만드는 파일이 <code>긴급_기준.json</code>이고 고치는 파일이 <code>요청_처리.py</code>인가. 실행하려는 명령이 <code>python 요청_처리.py</code>와 <code>python 검증/견주기.py</code>인가. 다른 파일이나 다른 명령이면 허용하지 않고 왜 필요한지 묻는다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 검증/견주기.py)와 「허용/계속」 버튼이 보이게.'))
+ do(3, 'editor', 'VS Code · 터미널', '견주기를 내 손으로 한 번 더 실행한다',
 '<p>Copilot이 보여 준 출력을 믿기 전에 터미널에서 직접 실행한다. 아래는 대신 돌린 실행의 출력 전체다. 1단계의 사본들과 견주어 본다.</p>' + term('python 검증/견주기.py') + box(cmp5, ('항목의 순서: 같다', '더해진 칸 긴급: true', '더해진 칸 긴급: null', cmp5.splitlines()[-1]))
 + find(('기존 칸이 열 건 모두 그대로인가', '줄마다 「기존 칸은 그대로다」. 앞 실습에서 만든 상태, 질문, 승인, 상태 기록이 한 글자도 바뀌지 않았다.'),
        ('더해진 칸이 하나인가', '요약 줄에 「더해진 칸 1개 (긴급)」. 칸의 이름과 값의 종류는 규칙 파일이, 값을 가르는 기준은 내가 정했다.'),
        ('고친 파일이 무엇인가', 'Copilot의 답 끝에서 만든 파일과 고친 파일을 본다. <code>긴급_기준.json</code>, <code>요청_처리.py</code>와 결과 두 파일뿐이어야 한다. 탐색기에서 <code>에이전트.py</code>와 <code>도구.py</code>에 바뀐 표시가 없는지도 본다.'),
        ('수용 기준은 모두 참인가', 'Copilot의 표에서 긴급의 문장들이 모두 참인가. 대신 돌린 실행에서는 열세 문장이 모두 참이었다. 명세에 글자 그대로는 없는데 넣은 것이 있으면 밝혔는지도 본다.'))
 + ifs(('「기존 칸이 달라졌다」가 나온 요청이 있다면', '그 아래 줄에 어느 칸이 무엇에서 무엇으로 바뀌었는지가 적혀 있다. 그대로 Copilot에게 말한다. 「R04의 상태_기록이 달라졌어. 명세는 긴급에 대한 건을 상태 기록에 더하지 않는다고 했어. 그 부분만 되돌려 줘.」'),
       ('도구.py나 에이전트를 고쳤다면', '규칙의 5번과 명세의 금지 조건에 어긋난다. 그 줄을 들어 되돌리게 한다.')))
+ nxt(5, '5. 긴급과 상태를 내 눈으로 맞춘다', 3))

# ───────── 5단계
pages.append(hero('5단계', '긴급과 상태를<br>내 눈으로 맞춘다',
 '견주기가 통과했고 Copilot이 모두 참이라고 했다. 그래도 한 번은 사람이 본다. 볼 곳은 네 요청이다. 긴급이고 확정된 요청, 긴급인데 승인을 기다리는 요청, 기준 바로 곁의 요청, 사례가 정해지지 않은 요청. 같은 사례를 가리키는 두 요청이 <b>승인이 있고 없음에 따라 다른 상태</b>에 있는지를 본다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '긴급의 세 값이 내가 정한 대로 갈렸고, 상태가 하나도 바뀌지 않았다는 것을 안다'), ('맞춰 볼 것', '결과 md ↔ 입력의 값 ↔ 명세의 문장')])
+ do(1, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '열 요청의 긴급을 입력의 값과 맞춘다',
 '<p><code>결과/요청_처리.md</code>의 미리 보기를 왼쪽에, <code>입력/센서_입력.json</code>을 오른쪽에 둔다. 요청마다 「상태」 줄 바로 아래에 「긴급」 줄이 생겼다. 아래는 완성 폴더의 결과와 입력에서 옮긴 것이다.</p>' + t1
 + shot('결과 md의 미리 보기와 입력 json을 좌우로 나란히 연 VS Code 화면. 결과 쪽은 R04의 「상태: 승인_대기」와 그 아래 「긴급」 줄이, 입력 쪽은 S01의 TS1 줄(60.7)이 보이게.')
 + find(('긴급인데 승인 대기인가', 'R03과 R04는 둘 다 사례 S01이고 둘 다 긴급이다. R03은 확정, R04는 승인 대기다. 둘을 가르는 것은 긴급이 아니라 <code>사람/승인.json</code>의 한 줄이다. 「빨리」가 승인을 건너뛰는 뜻으로 구현되지 않았다.'),
        ('기준 곁의 값을 올려 치지 않았는가', 'R05의 사례 S07은 유온 평균이 59.4다. 60 이상이 아니므로 false다.'),
        ('사례가 없는 요청을 미리 가르지 않았는가', 'R01의 요청에는 펌프 누설이라고 적혀 있다. 경보 패턴이 다르니 false라고 적고 싶어지지만, 사례가 정해지지 않았으므로 null이다. 사본 1은 이 경우에 요청에 적힌 패턴으로 가렸다.'),
        ('「사람이 할 일」이 그대로인가', f'md 맨 위의 「승인을 기다리는 요청」이 {", ".join(a0)}의 차례 그대로인가. 상태를 다시 센다. {cnt_txt}이어야 한다.')))
+ do(2, 'editor', 'VS Code · 편집기', '기준이 어디에 적혀 있는지 찾는다',
 '<p>탐색기에 새로 생긴 <code>긴급_기준.json</code>을 연다. 여섯 칸이 명세의 표와 글자까지 같은지 본다.</p>'
 + box(json.dumps(CR, ensure_ascii=False, indent=2), ('"threshold": 60',))
 + '<p style="margin-top:18px">이어서 <code>요청_처리.py</code>를 열고 찾기(Ctrl+F)로 <code>60</code>, <code>COOLER</code>, <code>TS1</code>을 찾는다. 하나도 나오지 않아야 한다. 기준이 프로그램 안에 적혀 있으면, 명세의 숫자를 바꾼 날 프로그램과 명세가 어긋난다. 사본 1이 그렇게 했다. 7단계에서 이 어긋남을 일부러 겪어 본다.</p>'
 + ifs(('프로그램에 60이 적혀 있다면', '「요청_처리.py에 60이 직접 적혀 있어. 명세는 기준을 긴급_기준.json에서 읽으라고 했어. 그 부분을 고쳐 줘.」'),
       ('R01이나 R08이 false로 나왔다면', '「R01의 긴급이 false로 나왔어. 명세는 사례가 정해지지 않은 요청을 null로 적으라고 했어. 그 경우만 고치고 다시 실행해 줘.」')))
+ nxt(6, '6. 규칙을 일부러 건드려 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙과 명세 안에서 움직였다. 정말 막아 주는지는 어긋나는 일을 시켜 보아야 안다. 실제 일터에서 긴급 건이 생기면 누구나 「이건 급하니까 승인은 나중에」, 「문서는 내가 나중에 고칠게」라고 말하게 된다. 그 말을 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일과 명세의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '프로그램, 명세, 결과, 사람 폴더의 두 파일')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '긴급이니 승인을 건너뛰자고 해 본다',
 '<p>R04는 긴급이고 승인을 기다리고 있다. 급한 건을 빨리 끝내고 싶다는 그럴듯한 요청이다.</p>'
 + copy(P6a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 아무것도 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '터미널에서 <code>python 검증/견주기.py</code>를 실행해 요약 줄이 4단계와 같은지 본다. <code>사람/승인.json</code>을 열어 R04의 줄이 생기지 않았는지도 본다.'),
        ('무엇을 들어 멈췄는가', '규칙 파일의 줄과 함께, <b>내가 정한 명세의 줄</b>(긴급이라는 것으로 승인을 대신하지 않는다, R04는 승인 대기다)을 들었는가. 규칙만이 아니라 3단계에서 내가 적게 한 문장이 나를 막는다.'),
        ('멈추기만 했는가', '규칙 안에서 같은 목적을 이루는 길을 내놓았는가. 대신 돌린 실행에서는 R04의 조치 넷과 승인 역할을 표로 보이고, 「승인할 수 있는 사람이 승인.json에 한 줄을 직접 적으면 다음 실행에서 바로 확정된다. 내가 대신 써 넣는 것은 규칙 2가 막는다」고 했다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '순서만 바꾸고 명세는 나중에 고치자고 해 본다',
 '<p>사본 2와 3이 한 일을 내 폴더에 시킨다. 「명세는 나중에」라는 말을 붙였다.</p>'
 + copy(P6b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 견주기를 다시 실행해 「항목의 순서 같다」인지 보고, <code>결과/요청_처리.md</code>의 「승인을 기다리는 요청」이 R02, R04, R05 그대로인지 본다. Copilot이 「명세를 고쳐도 풀리지 않고 규칙 파일을 사람이 고쳐야 풀린다」는 것과, 순서를 바꾸면 수용 기준의 어느 문장이 거짓이 되는지를 짚었는지 읽는다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절에서 승인을 말하는 줄이다. 몇 번인가. 「급하다는 것도 승인을 대신하지 않는다」는 앞 실습의 규칙에 이미 있던 문장이다.</li><li><b>둘째 요청</b>같은 절의 두 줄이다. 요청의 순서를 말하는 줄과, 명세와 프로그램 가운데 무엇이 먼저인지를 말하는 줄이다. 각각 몇 번인가. 「정해져 있는 것」에서 md에 더하는 것을 한 줄로 묶어 둔 문장도 찾는다.</li><li><b>두 답에 함께 나온 줄</b>「요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('수업에서 본 것이 여기에 있다', '요구사항은 변경 요청이 올 때마다 늘어나고, 금지 조건은 그대로 남아 새 요구를 금지에 어긋나게 해석하는 길을 막는다. 1단계의 사본에는 이 줄이 없었다. 승인을 건너뛴 사본이 없었던 것은 그때의 AI가 조심스러웠기 때문이고, 지금 건너뛰지 못하는 것은 문서에 적혀 있기 때문이다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '무엇을 고쳤는지 묻고 되돌리게 한다. <code>사람/승인.json</code>이 바뀌었다면 내 손으로 그 줄을 지운다. 되돌린 뒤 견주기의 요약 줄이 4단계와 같은지 본다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「명세를 먼저 고치면 하겠다」고 한다면', '순서를 바꾸는 것은 규칙의 7번이 막고 있어 명세를 고쳐도 받을 수 없는 일이다. 승인을 건너뛰는 것도 같다. 명세로 정할 수 있는 것과 규칙이 묶어 둔 것이 다르다는 것을 본다.')))
+ nxt(7, '7. 기준을 손으로 어긋나게 고쳐 보고, 되돌려 준다', 5))

# ───────── 7단계
pages.append(hero('7단계', '손으로 어긋나게 고쳐 보고,<br>어느 쪽을 고칠지 말한다',
 '명세와 프로그램은 시간이 지나면 어긋난다. 누군가 급하게 숫자 하나를 손으로 고치고 문서는 그대로 두기 때문이다. 그 일을 지금 내 손으로 해 본다. 어긋남을 무엇이 잡아내고 무엇은 잡아내지 못하는지를 보고, <b>명세와 기준 파일 가운데 어느 쪽을 고칠지</b>를 내 말로 되돌려 준다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '명세와 기준 파일이 다시 같고, 수용 기준이 모두 참이다')])
+ do(1, 'editor', 'VS Code · 편집기와 터미널', '기준값을 손으로 59로 고치고 다시 실행한다',
 '<p><code>긴급_기준.json</code>을 열어 <code>"threshold": 60</code>을 <code>59</code>로 고치고 저장한다(Ctrl+S). <code>spec.md</code>는 건드리지 않는다. 그다음 터미널에서 아래 두 줄을 실행한다.</p>'
 '<div class="chg"><div class="tree">고치기 전\n"expect": "gte",\n"threshold": 60</div><div class="tree">고친 뒤\n"expect": "gte",\n"threshold": <b>59</b></div></div>'
 + term('python 요청_처리.py\npython 검증/견주기.py')
 + '<p style="margin-top:18px">요약 줄은 아래와 같다. 4단계와 글자 하나 다르지 않다.</p>' + box(cmp7.splitlines()[-1])
 + '<p style="margin-top:18px">그런데 출력을 위로 올려 R05를 보면 <code>더해진 칸 긴급: true</code>로 바뀌어 있다. 견주기는 기존 칸이 그대로인지를 볼 뿐, 새 칸의 값이 맞는지는 보지 않는다. 그것을 보는 것은 수용 기준이다.</p>')
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '무엇을 고쳤는지 말하지 않고, 수용 기준에 대어 보게 한다',
 '<p>내가 무엇을 고쳤는지는 알려 주지 않는다. 명세의 문장만으로 찾아내는지를 본다.</p>' + copy(P7a)
 + find(('거짓인 문장을 찾았는가', '대신 돌린 실행에서는 긴급의 열세 문장 가운데 하나가 거짓이었다. 「사례가 S07(59.4)로 정해진 R05는 긴급이 false다」.'),
        ('어디가 어긋났다고 했는가', '명세도 프로그램도 아니고 기준 파일이라고 짚었는가. 프로그램에는 60도 59도 적혀 있지 않고, 파일의 값을 읽어 그대로 대어 볼 뿐이어서 명세대로 움직였다고 했는가.'),
        ('바로잡는 길을 몇 가지 내놓았는가', '둘이어야 한다. 기준 파일을 명세에 맞춰 되돌리는 길과, 기준을 59로 바꾸기로 하고 명세를 먼저 고치는 길이다. 어느 쪽이 맞는지는 Copilot이 알 수 없다. 내가 무엇을 하려던 것인지에 달려 있다.')))
+ '<section class="sect"><h2>같은 어긋남, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>' + e(P7bad) + '</q>어느 쪽이 틀렸는지를 말하지 않았다. 대신 돌린 실행에서 AI는 되묻지 않고 기준 파일을 60으로 되돌렸다. 명세가 먼저라는 규칙이 있어 그쪽을 고른 것이다. 내가 하려던 일이 기준을 59로 낮추는 것이었다면 반대로 고쳐진 셈이다. 답의 끝에는 「이상하다는 것이 R05의 다른 곳을 가리킨 것이었다면 알려 달라」고 적혀 있었다.</div>'
  '<div class="good"><b>구체적으로</b><q>' + e(P7) + '</q>어느 쪽이 맞는지를 내가 정해 말했고, 고칠 곳과 건드리지 말 곳을 그었다. 요청한 한 줄만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>기준 파일의 값이 59여서 R05가 긴급으로 나온다</div><div><b>왜</b>기준을 바꾸기로 정한 적이 없다. 명세가 맞다</div><div><b>어디를</b>긴급_기준.json의 threshold 한 줄</div><div><b>어디까지</b>spec.md와 요청_처리.py는 그대로</div></div></section>'
+ do(3, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '어느 쪽을 고칠지 정해 되돌려 준다',
 '<p>두 길 가운데 하나를 고른다. 기준 파일을 명세에 맞춰 되돌리거나, 기준을 낮추기로 하고 명세부터 고치거나. 무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 기준을 낮추는 쪽을 골랐다면 「spec.md를 먼저 고치고」를 꼭 넣고, R05 대신 「긴급이 아닌 냉각 경보」의 예로 쓸 요청을 정해 준다.</p>'
 + write('w7', '무엇이 어긋나 있는지, 명세와 기준 파일 가운데 어느 쪽이 맞는지와 그 까닭, 어느 파일의 어디를 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">기준 파일을 명세에 맞춰 되돌리는 쪽을 고른 경우의 글이다. 완성 폴더는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P7, pre=True) + '</details>'
 '<p style="margin-top:18px">고친 뒤에는 세 가지를 본다. <code>긴급_기준.json</code>의 기준값이 명세와 같은가. R05의 긴급이 내가 고른 쪽대로인가. 견주기의 요약 줄이 그대로인가.</p>'
 + shot('되돌려 준 뒤 Copilot이 긴급_기준.json의 바뀐 줄을 보여 주는 화면(threshold 줄이 바뀐 표시)과, 거짓이던 문장이 참으로 돌아왔다는 답이 보이게.')
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('기준을 낮추는 쪽을 골랐는데 기준 파일부터 고치려 한다면', '규칙의 6번을 들어 멈추는지 본다. 멈추지 않으면 「명세의 기준 문장과 수용 기준부터 고쳐 줘」라고 말한다. 이 길을 끝까지 가면 내 결과는 완성 폴더와 R05 한 건이 달라진다.')))
+ nxt(8, '8. 다음 실습에 넘길 입력과 기대 결과를 저장한다', 6))

# ───────── 8단계
pages.append(hero('8단계', '다음 실습에 넘길<br>입력과 기대 결과를 저장한다',
 '수용 기준은 지금 Copilot이 한 문장씩 읽고 대어 보았다. 다음 실습에서는 이것을 시나리오로 적어 되풀이해 실행한다. 그때 쓸 재료를 남긴다. 정상, 긴급, 미입력, 거절의 네 경우마다 <b>무엇이 주어졌을 때 무엇이 나와야 하는지</b>를 파일 하나에 적는다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '검증/시나리오.json에 여섯 건이 있다'), ('바뀌면 안 되는 것', '프로그램, 명세, 결과')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '여섯 건을 골라 주고, 기대를 명세에서 적게 한다',
 '<p>어느 요청을 어느 경우의 예로 삼을지는 규칙이 비워 둔 것이어서 내가 정했다. 7단계에서 기준을 59로 낮췄다면 첫째 줄을 고친다. R05가 긴급이 되므로 「정상」의 예를 R02(승인을 기다리는, 경보 패턴이 다른 요청)로 바꾼다.</p>'
 + copy(P8, pre=True, rich=richpre(P8, 'abc'))
 + parts(('무엇을 만드는가', '첫 문단. 파일의 이름과 칸은 규칙 파일이 정해 두었다. 다음 실습이 이 이름으로 찾는다.'), ('어느 요청을', '둘째 문단. 네 경우에 여섯 건이다. 긴급을 둘로 한 것은 승인이 있고 없음에 따라 상태가 갈려서이고, 미입력을 둘로 한 것은 질문의 모양이 달라서다.'), ('기대를 어디에서 가져오는가', '셋째 문단. 결과 파일을 베끼면 프로그램이 틀렸을 때 기대도 함께 틀린다. 그래서 명세에서 먼저 적고 결과와 대어 보게 했다. 다르면 어느 쪽도 고치지 말고 알리게 했다.')))
+ do(2, 'editor', 'VS Code · 편집기', '저장된 기대를 명세와 맞춘다',
 '<p><code>검증/시나리오.json</code>을 연다. 아래는 완성 폴더의 파일에서 옮긴 것이다. 건마다 <code>주어진_것</code>에 요청에 적힌 것, 사람의 답, 사람의 결정, 긴급을 가르는 값이 사실대로 적혀 있는지도 본다.</p>' + tsc
 + shot('검증/시나리오.json을 연 VS Code 화면. R04 건의 주어진_것(사람의 답 두 건, 사람의 결정 null, 긴급을 가르는 값 60.7)과 기대(승인_대기, true)가 보이게.')
 + find(('기대가 결과와 같았는가', 'Copilot이 명세에서 낸 기대와 결과 파일이 모두 같았다고 했는가. 대신 돌린 실행에서는 스물네 칸이 모두 같았다.'),
        ('주어진 것이 사실인가', 'R04의 답 두 건이 <code>사람/답변.json</code>과 같은가. R07의 거절 사유가 <code>사람/승인.json</code>과 글자까지 같은가. 한 건을 골라 직접 찾아본다.'),
        ('없는 것을 알렸는가', '이 여섯 건에 들어 있지 않은 경우를 Copilot이 짚었는가. 대신 돌린 실행에서는 「값을 읽지 못해 긴급이 null인 경우가 없다」고 했다. 다음 실습에서 시나리오를 더할 자리다.'))
 + ifs(('기대와 결과가 다르다고 한다면', '어느 쪽이 맞는지를 명세의 문장으로 따진다. 명세가 맞다면 프로그램을, 명세가 틀렸다면 명세를 먼저 고친다.'),
       ('다른 파일까지 만들었다면', '규칙의 8번(요청받지 않은 파일을 만들지 않는다)을 들어 지우게 한다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>승인을 내 손으로 넣어 R04를 확정시켜 본다.</b> 6단계에서 Copilot은 「승인할 수 있는 사람이 직접 적으면 된다」고 했다. <code>사람/승인.json</code>의 마지막 건 뒤에 쉼표를 붙이고 한 건을 더한다(<code>"요청": "R04", "결정": "승인", "절차_번호": "SOP-COOL-11", "역할": "운전원"</code>과 이름, 사유 <code>null</code>). 저장하고 <code>python 요청_처리.py</code>와 <code>python 검증/견주기.py</code>를 실행한다. R04의 상태가 확정이 되고 긴급은 true 그대로다. 이번에는 견주기가 「기존 칸이 달라진 항목 1건」이라고 한다. 프로그램을 고친 것이 아니라 사람이 쓴 파일이 바뀌었기 때문이다. 견주기는 같은 입력으로 낸 두 결과를 댈 때만 뜻이 있다. 본 뒤에는 더한 건을 지워 되돌린다.</p>'
  '<p><b>기준을 59로 낮추는 길을 끝까지 가 본다.</b> 7단계에서 되돌리는 쪽을 골랐다면, 이번에는 반대쪽이다. 아래를 보내고, 명세에서 몇 줄이 바뀌는지, 고친 직후 어느 문장이 거짓이라고 하는지를 본다. 대신 돌린 실행에서는 방금 저장한 <code>검증/시나리오.json</code>의 첫 건도 새 명세와 어긋나게 되었다고 알려 왔다. 숫자 하나를 바꾸는 일인데 문서 여러 곳이 함께 움직인다.</p>'
  + copy(P9)
  + '<p style="margin-top:18px"><b>사본 1의 프로그램을 읽어 본다.</b> <code>사례/모호한_요청/사본1/요청_처리.py</code>에서 찾기(Ctrl+F)로 <code>_긴급_패턴</code>을 찾는다. 긴급의 기준이 프로그램 안에 적혀 있다. 이 기준을 바꾸려면 누가 무엇을 고쳐야 하는가. 내 폴더에서는 같은 일을 어떻게 하는가.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 세 결과를 견준다', '2. 지금의 동작을 명세로', '3. 빈자리를 정해 명세에', '4. 명세대로 고치고 견주기', '5. 내 눈으로 맞추기', '6. 규칙을 건드려 보기', '7. 어긋남을 되돌려 주기', '8. 기대 결과 저장']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>한 문장의 요구 → 명세 → 기존 기능을 지킨 변경</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-07-3-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();const term=!!b.closest('.term');if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say(term?'복사했습니다. VS Code의 터미널에 붙여넣고 Enter를 누르세요.':'복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 명세를 갱신해 기존 기능을 유지하며 요구사항 추가</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
assert not re.search(r'/(Users|private|var)/', doc) and '임시 폴더' not in doc
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
