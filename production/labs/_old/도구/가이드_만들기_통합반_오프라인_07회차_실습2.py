"""통합반 오프라인 07회차 실습 2 「정보가 부족하면 사람에게 묻는 에이전트 만들기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '07회차_실습2_질문하는_에이전트'
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 묻고 멈추고 이어서 처리하는 요청_처리.py, 내가 쓴 답과 승인, 요청 열 건이 거쳐 온 상태의 기록. 다음 실습에서는 이 프로젝트에 새 요구사항을 더하면서 지금의 동작이 깨지지 않게 한다</b></div></div>'
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
css += '''
.states{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px 8px;margin:18px 0 8px}
.states svg{width:100%;height:auto;display:block}
.st.q{background:#f3eeff;color:#6a3fd1}.st.h{background:#fff1a8;color:#7a5b00}.st.w{background:var(--accent-soft);color:var(--accent)}.st.ok{background:var(--ok-soft);color:var(--ok)}.st.no{background:#fdecec;color:#b3261e}
table.res td.nul{color:#b3261e;font-weight:700}
.paste .copy-foot{color:var(--accent)}
'''
def paste(text, head, foot):
    cid[0] += 1; i = f'c{cid[0]}'
    return f'<div class="copy paste"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text pre" id="{i}" style="font-family:Consolas,\'D2Coding\',monospace;font-size:14px">{e(text)}</div><div class="copy-foot">{foot}</div></div>'

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1, P2, P3, P4, P5a, P5b, P6, P7 = (P(f'{n}_prompt.txt') for n in ('1', '2', '3', '4', '5a', '5b', '6', '7'))
P1rich = ('<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 입력 폴더의 점검_요청.json, 요청_설명.md, 입력_설명.md, 사람 폴더의 쓰는_법.md, 그리고 에이전트.py 를 읽어 줘.</span> '
          '<span class="p-b">요청 열 건을 한 줄씩 표로 적어 줘. 줄마다 어느 칸이 비어 있는지, 센서_입력.json 에서 그 요청에 맞는 사례가 몇 건이고 무엇인지를 적어 줘.</span> '
          '<span class="p-c">빠진 값을 짐작해서 채우지는 말고, 이 폴더의 규칙만으로는 정할 수 없는 것이 나오면 정하지 말고 내가 무엇을 정해 줘야 하는지 물어 줘. 아직 파일은 만들지 마.</span>')
assert re.sub(r'<[^>]+>', '', P1rich) == P1
ANS = P('4_답변.json'); APP = P('6_승인.json')

# ── 시작 폴더의 자료에서 읽는 것
REQ = json.loads((R / '시작' / '입력' / '점검_요청.json').read_text(encoding='utf-8'))
IN = json.loads((R / '시작' / '입력' / '센서_입력.json').read_text(encoding='utf-8'))
assert (len(REQ), len(IN)) == (10, 11)
case = {c['번호']: c for c in IN}
def fit(q):  # 요청에 적힌 설비 · 경보 패턴에 모두 맞는 사례
    return [c['번호'] for c in IN if all(q[k] is None or q[k] == c[k] for k in ('설비', '경보_패턴'))]
def cell(v): return f'<td class="nw">{e(v)}</td>' if v is not None else '<td class="nw nul">비어 있다</td>'
reqt = ('<table class="res"><thead><tr><th>요청</th><th>요청자</th><th>설비</th><th>경보 패턴</th><th>사례</th><th>요청자가 적은 말</th></tr></thead><tbody>'
        + ''.join(f'<tr><td class="nw"><b>{q["번호"]}</b></td><td class="nw">{e(q["요청자"])}<br><small>{e(q["요청자_역할"])}</small></td>{cell(q["설비"])}{cell(q["경보_패턴"])}{cell(q["사례"])}<td><small>{e(q["요청_글"])}</small></td></tr>' for q in REQ)
        + '</tbody></table>')
nfit = {q['번호']: fit(q) for q in REQ}
assert [len(nfit[k]) for k in ('R01', 'R04', 'R06', 'R07', 'R08', 'R09', 'R10')] == [2, 11, 2, 3, 0, 1, 1]
assert case['S02']['설비'] == 'HYD-02' and REQ[4]['설비'] == 'HYD-01' and REQ[4]['사례'] == 'S02'

# ── 실제로 실행한 결과 파일에서 옮기는 것
J = lambda p: {x['번호']: x for x in json.loads((R / p).read_text(encoding='utf-8'))}
r3, r4, fin = J('기록/3_결과.json'), J('기록/4_결과.json'), J('완성/결과/요청_처리.json')
assert J('기록/6_결과.json') == fin
STC = {'질문_대기': 'q', '보류': 'h', '승인_대기': 'w', '확정': 'ok', '반려': 'no'}
st = lambda v: f'<span class="st {STC[v]}">{v}</span>'
def cnt(d): return {k: sum(1 for x in d.values() if x['상태'] == k) for k in STC}
assert cnt(r3) == {'질문_대기': 6, '보류': 2, '승인_대기': 2, '확정': 0, '반려': 0}
assert cnt(fin) == {'질문_대기': 3, '보류': 3, '승인_대기': 2, '확정': 1, '반려': 1}
def last(x): return e(x['상태_기록'][-1]['까닭'])
def opts(x):
    q = x['질문'][-1] if x['질문'] else None
    if q is None: return '<small>묻지 않았다</small>'
    return (' · '.join(f'<code>{e(o)}</code>' for o in q['선택지']) or '<small>선택지 없음</small>')
t3 = ('<table class="res"><thead><tr><th>요청</th><th>상태</th><th>사례</th><th>근거 상태</th><th>질문의 선택지</th><th>상태 기록의 마지막 줄</th></tr></thead><tbody>'
      + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td class="nw">{st(x["상태"])}</td><td class="nw">{e(x["사례"] or "—")}</td><td class="nw">{e(x["근거_상태"] or "—")}</td><td>{opts(x)}</td><td><small>{last(x)}</small></td></tr>' for k, x in r3.items())
      + '</tbody></table>')
q01 = r3['R01']['질문'][0]; q08 = r3['R08']['질문'][0]
assert q01['선택지'] == ['S04', 'S05'] and q08['선택지'] == [] and r3['R04']['질문'][0]['선택지'] == ['HYD-01', 'HYD-02', 'HYD-03']
chg = [k for k in r3 if r3[k] != r4[k]]
assert chg == ['R04', 'R05', 'R06', 'R07']
t4 = ('<table class="res"><thead><tr><th>요청</th><th>내가 적은 답</th><th>실행 전</th><th>실행 후</th><th>상태 기록에 더해진 줄</th></tr></thead><tbody>'
      + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td class="nw"><code>{e(a)}</code></td><td class="nw">{st(r3[k]["상태"])}</td><td class="nw">{st(r4[k]["상태"])}</td><td><small>{("<mark>" + last(r4[k]) + "</mark>") if "반영하지 않음" in r4[k]["상태_기록"][-1]["까닭"] else last(r4[k])}</small></td></tr>'
                for k, a in (('R06', 'S08'), ('R07', 'S03'), ('R04', 'HYD-01'), ('R05', 'S7')))
      + '</tbody></table>')
assert r4['R05']['질문'][0]['답'] is None and r4['R04']['질문'][1]['선택지'] == ['S01', 'S04', 'S07', 'S10'] and r4['R06']['근거_상태'] == 'UNKNOWN'
def appr(x):
    a = x['승인']
    if not a: return '<small>반영한 결정 없음</small>'
    return f'{e(a["결정"])} · {e(a["역할"])} {e(a["이름"])}' + (f' · <code>{e(a["절차_번호"])}</code>' if a['절차_번호'] else '') + (f'<br><small>사유: {e(a["사유"])}</small>' if a['사유'] else '')
t6 = ('<table class="res"><thead><tr><th>요청</th><th>상태</th><th>사례</th><th>근거 상태</th><th>반영한 결정</th></tr></thead><tbody>'
      + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td class="nw">{st(x["상태"])}</td><td class="nw">{e(x["사례"] or "—")}</td><td class="nw">{e(x["근거_상태"] or "—")}</td><td>{appr(x)}</td></tr>' for k, x in fin.items())
      + '</tbody></table>')
assert fin['R03']['상태'] == '확정' and fin['R07']['상태'] == '반려' and fin['R02']['승인'] is None and '공장장' in fin['R02']['상태_기록'][-1]['까닭'] and fin['R05']['사례'] == 'S07'
md = (R / '완성' / '결과' / '요청_처리.md').read_text(encoding='utf-8')
r03 = [l for l in md.split('\n## R03')[1].split('\n## R04')[0].splitlines() if 'SOP-COOL-1' in l and l.lstrip().startswith('- [')]
assert len(r03) == 4 and '승인됨' in r03[0] and all('승인되지 않음' in l for l in r03[1:])
todo = md.split('## 사람이 할 일')[1].split('\n## R01')[0].strip()
assert '### 답할 질문' in todo and '### 승인을 기다리는 요청' in todo and '### 반영하지 않은 사람의 기록' in todo

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>언제 묻지 않는가</b></td><td><mark>1번 줄</mark> 사례가 적혀 있으면 그 사례로 처리한다. 사례가 비어 있어도 적힌 설비와 경보 패턴에 맞는 사례가 입력에 하나뿐이면 묻지 않는다</td><td>「사례가 비어 있으면 맞는 사례가 하나여도 맞는지 묻는다」로 바꾼다. R09와 R10도 질문을 받는다. 더 조심스럽지만 답할 사람의 일이 는다</td></tr>
<tr><td><b>무엇을 묻는가</b></td><td><mark>2번 줄</mark> 맞는 사례가 여럿이면 어느 사례인지를 묻는다. 선택지는 사례 번호이고, 물음에 사례마다 설비, 경보 패턴, 판단 시각을 적는다. 여덟을 넘으면 설비부터 묻는다</td><td>「경보 패턴이 비어 있으면 패턴부터 묻는다」로 바꾼다. R07은 패턴을 답한 뒤에 사례를 한 번 더 답해야 한다</td></tr>
<tr><td><b>어긋나거나 없을 때</b></td><td><mark>3번 줄</mark> 적힌 사례가 적힌 설비나 경보 패턴과 다르면 처리하지 않고 묻는다. 맞는 사례가 입력에 없으면 선택지 없이 묻는다</td><td>「사례가 적혀 있으면 그 사례를 믿는다」로 바꾼다. R05는 묻지 않고 S02로 처리된다. S02는 HYD-02의 사례인데 요청자는 HYD-01이라고 적었다</td></tr>
<tr><td><b>답을 받는 법</b></td><td><mark>4번 줄</mark> 요청 번호와 질문 순번이 같은 첫 답만 쓴다. 선택지에 없는 답은 반영하지 않고 질문 대기로 둔다</td><td>「같은 질문에 답이 둘이면 나중 것을 쓴다」로 바꾼다. 고쳐 답하기는 쉬워지지만, 이미 반영되어 처리가 나아간 답이 뒤에서 바뀔 수 있다</td></tr>
<tr><td><b>승인 대기와 보류</b></td><td><mark>5번 줄</mark> 사례가 정해지면 에이전트로 점검 계획을 낸다. 근거 상태가 SUPPORTED이면 승인 대기, 아니면 보류다</td><td>「조치가 하나라도 붙어 있으면 승인 대기」로 바꾼다. 가설뿐인 사례의 「확인된 뒤에 할 조치」까지 승인을 받으러 올라간다</td></tr>
<tr><td><b>승인과 거절</b></td><td><mark>6번 줄</mark> 승인은 절차 번호가 그 요청의 계획에 붙은 조치이고 역할이 그 조치의 승인 역할과 같을 때만 받는다. 거절은 사유가 있을 때만 받는다</td><td>「등급이 더 높은 역할의 승인도 받는다」로 바꾼다. 공장장이 운전원의 조치를 승인할 수 있게 된다. 온톨로지의 역할에는 등급(<code>level</code>)이 적혀 있다</td></tr>
</tbody></table>'''

states = '''<div class="states"><svg viewBox="0 0 760 250" role="img" aria-label="요청 한 건이 거치는 상태">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#8a94a3"/></marker></defs>
<g font-size="13" font-weight="700" fill="#14181f" text-anchor="middle">
<rect x="6" y="92" width="74" height="46" rx="10" fill="#eef1f5"/><text x="43" y="120">접수</text>
<rect x="112" y="84" width="120" height="62" rx="10" fill="#eef1f5"/><text x="172" y="110">사례를 정한다</text><text x="172" y="130" font-size="11" font-weight="400" fill="#5b6573">요청의 칸 + 센서 입력</text>
<rect x="112" y="190" width="120" height="50" rx="10" fill="#f3eeff" stroke="#6a3fd1" stroke-width="2"/><text x="172" y="212" fill="#6a3fd1">질문_대기</text><text x="172" y="230" font-size="11" font-weight="400" fill="#5b6573">묻고 멈춘다</text>
<rect x="304" y="84" width="120" height="62" rx="10" fill="#eef1f5"/><text x="364" y="110">에이전트</text><text x="364" y="130" font-size="11" font-weight="400" fill="#5b6573">점검 계획 · 근거 상태</text>
<rect x="500" y="16" width="112" height="50" rx="10" fill="#fff1a8"/><text x="556" y="38" fill="#7a5b00">보류</text><text x="556" y="56" font-size="11" font-weight="400" fill="#5b6573">근거가 모자라다</text>
<rect x="500" y="94" width="112" height="50" rx="10" fill="#eaf0ff" stroke="#2f5bea" stroke-width="2"/><text x="556" y="116" fill="#2f5bea">승인_대기</text><text x="556" y="134" font-size="11" font-weight="400" fill="#5b6573">결정을 기다린다</text>
<rect x="680" y="50" width="74" height="46" rx="10" fill="#e8f6ee"/><text x="717" y="78" fill="#1a7f4b">확정</text>
<rect x="680" y="142" width="74" height="46" rx="10" fill="#fdecec"/><text x="717" y="170" fill="#b3261e">반려</text></g>
<g stroke="#8a94a3" stroke-width="2" fill="none" marker-end="url(#ar)"><path d="M80 115H110"/><path d="M232 115H302"/><path d="M152 146V188"/><path d="M192 190V148"/>
<path d="M424 104H462V41H498"/><path d="M424 122H498"/><path d="M612 110H646V73H678"/><path d="M612 128H646V165H678"/></g>
<g font-size="11.5" fill="#5b6573"><text x="144" y="172" text-anchor="end">빠졌다</text><text x="200" y="172" text-anchor="start">사람이 답한다</text><text x="267" y="106" text-anchor="middle">정해졌다</text>
<text x="492" y="30" text-anchor="end">SUPPORTED가 아니다</text><text x="461" y="140" text-anchor="middle">SUPPORTED</text><text x="672" y="62" text-anchor="end">사람이 승인</text><text x="672" y="184" text-anchor="end">사람이 거절</text></g></svg></div>'''

three = '''<table class="res"><thead><tr><th style="width:130px">결과의 상태</th><th style="width:150px">수업에서 본 이름</th><th>미룬 쪽과 까닭</th><th>사람이 할 일</th></tr></thead><tbody>
<tr><td class="nw">''' + st('질문_대기') + '''</td><td><b>에이전트의 질문</b></td><td>에이전트. 필요한 정보가 없어 묻고 기다린다</td><td><code>사람/답변.json</code>에 답을 적는다</td></tr>
<tr><td class="nw">''' + st('보류') + '''</td><td><b>에이전트의 보류</b></td><td>에이전트. 근거가 모자라 승인받을 것을 내지 않았다</td><td>값을 다시 읽어 평가하게 하거나 닫는다. 승인해도 받지 않는다</td></tr>
<tr><td class="nw">''' + st('승인_대기') + '''</td><td><b>응답 없음</b></td><td>사람. 아직 승인도 거절도 하지 않았다</td><td><code>사람/승인.json</code>에 승인하거나 거절한다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 7회차 · 실습 2 · 30분</small>정보가 빠진 요청 앞에서<br>묻고 멈추는 에이전트를 만든다',
 '5회차에 만든 에이전트는 사례 번호를 받으면 원인을 가리고 점검 순서를 냈다. 현장의 요청은 그렇게 깔끔하게 오지 않는다. 설비를 적지 않은 요청, 어느 경보인지 적지 않은 요청, 적은 값이 서로 맞지 않는 요청이 섞여 온다. 이번에는 그 에이전트 앞에 요청을 받는 고리를 붙인다. 빠진 값을 짐작하지 않고 <b>묻고 멈추고</b>, 사람이 답하면 <b>이어서 처리하고</b>, 사람이 승인하기 전에는 <b>확정으로 적지 않는다.</b>',
 [('끝나면 남는 것', '요청_처리.py, 내가 쓴 답과 승인, 요청 열 건의 처리 결과 두 파일'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '5회차 실습 2의 에이전트가 있다'), ('준비에 쓰는 시간', '약 3분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>5회차의 에이전트(<code>에이전트.py</code>, <code>도구.py</code>)와 온톨로지는 고치지 않고 그대로 쓴다. 새로 만드는 것은 그 앞에 서는 <code>요청_처리.py</code> 한 파일이다.</p>'
  f'<div class="pipe"><div><b>점검 요청</b>현장에서 들어온 요청 {len(REQ)}건. 칸이 빠진 것이 섞여 있다<small>입력/점검_요청.json</small></div><span>+</span><div><b>사람의 답과 승인</b>내가 편집기에서 직접 쓴다. 처음에는 비어 있다<small>사람/답변.json · 승인.json</small></div><span>→</span><div class="out"><b>요청 처리 결과</b>요청마다 상태, 질문, 승인, 거쳐 온 상태의 기록<small>결과/요청_처리.json · .md</small></div></div>'
  '<h2 style="margin-top:26px">요청 한 건이 거치는 상태</h2><p>요청은 아래 다섯 상태 가운데 하나에 놓인다. 색이 칠해진 두 곳이 사람을 기다리는 자리다. 실행할 때마다 프로그램은 요청과 사람이 쓴 두 파일을 읽어 갈 수 있는 데까지 가고, 사람이 필요한 자리에서 멈춘다.</p>' + states
  + '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 이 가이드에 준비되어 있어 복사해 보낸다. 오늘 내 손으로 쓰는 것은 코드가 아니라 <b>답과 승인</b>이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>요청 열 건에서 무엇이 빠졌는지 표로 적게 한다</div><div><em>2</em><b>정해 준다</b>언제 묻고 무엇을 승인으로 받을지 내가 정하고 계획을 받는다</div><div><em>3</em><b>만들고 돌린다</b>첫 실행에서 질문이 나오고 멈추는 것을 본다</div><div><em>4</em><b>내가 답한다</b>답을 적고 다시 실행해 이어지는 것을 본다</div><div><em>5</em><b>내가 승인한다</b>대신 해 달라고 해 보고, 내 손으로 승인하고 거절한다</div></div></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 '<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>입력/</span>\n│  ├─ 점검_요청.json           <i>← 오늘의 요청 10건</i>\n│  ├─ 요청_설명.md             <i>← 요청의 칸</i>\n│  ├─ 센서_입력.json           <i>← 5회차의 사례 11건</i>\n│  └─ 입력_설명.md\n├─ <span>사람/</span>\n│  ├─ 답변.json                <i>← 내가 답을 쓰는 곳. 지금은 []</i>\n│  ├─ 승인.json                <i>← 내가 승인을 쓰는 곳. 지금은 []</i>\n│  └─ 쓰는_법.md               <i>← 두 파일의 칸</i>\n├─ <span>온톨로지/</span>                  <i>← 5회차 그대로</i>\n├─ 에이전트.py · 도구.py       <i>← 5회차에 만든 에이전트</i>\n├─ 에이전트_정의.json\n└─ <span>결과/</span>\n   └─ 점검_계획.json · .md     <i>← 5회차의 결과</i></div>'
 '<div><p><b>사람 폴더</b>가 오늘 새로 생긴 자리다. 규칙 파일은 이 폴더의 두 파일을 사람만 쓰게 해 두었다. 5단계에서 일부러 Copilot에게 대신 써 달라고 해 본다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 입력, 사람, 온톨로지, 결과 폴더와 에이전트.py가 펼쳐져 보이게.'))
+ do(2, 'editor', 'VS Code · 편집기', '요청 열 건에서 빈칸을 찾는다',
 '<p><code>입력/점검_요청.json</code>을 연다. 아래는 그 파일을 표로 옮긴 것이다. 에이전트가 일하려면 사례 한 건이 정해져야 한다. 사례가 적혀 있지 않아도 설비와 경보 패턴으로 <code>센서_입력.json</code>에서 찾을 수 있는 요청이 있고, 찾을 수 없는 요청이 있다.</p>' + reqt
 + '<p>표를 보며 두 가지를 종이에 적어 둔다. 첫째, 묻지 않고 바로 처리해도 되겠다고 보는 요청의 번호. 둘째, R01의 「야간조」처럼 요청자의 말에서 답을 짐작할 수 있을 것 같은 요청의 번호. 둘째 묶음은 5단계에서 다시 본다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 오늘의 세 줄을 읽는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. 「하면 안 되는 것」의 2 · 3 · 4번이 오늘의 중심이다. 사람의 파일은 사람이 쓴다, 빠진 값을 짐작해 채우지 않는다, 승인이 없는 요청을 확정으로 적지 않는다. 「정해져 있지 않은 것」의 여섯 줄은 일부러 비워 둔 자리이고 2단계에서 내가 채운다.</p>')
+ nxt(1, '1. 만들기 전에, 무엇이 빠졌는지 읽게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>무엇이 빠졌는지 읽게 한다',
 '첫마디가 「빠진 정보를 물어보는 기능을 만들어 줘」이면 AI는 무엇을 「빠졌다」고 볼지부터 스스로 정한다. 설비가 비어 있으면 무조건 묻는 프로그램이 나올 수도 있고, 요청자의 말에서 설비를 읽어 내는 프로그램이 나올 수도 있다. 그래서 첫 요청은 <b>열 건을 읽고, 무엇이 비어 있고 무엇은 입력에서 찾을 수 있는지를 표로 적으라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '요청마다 맞는 사례가 몇 건인지와, Copilot이 나에게 묻는 것이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 요청과 그 설명, 사람이 쓰는 파일의 칸, 그리고 이어받은 에이전트. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '요청 한 건을 한 줄로, 빈칸과 맞는 사례의 수를 적게 했다. 준비 단계에서 내가 종이에 적은 것과 바로 견줄 수 있다.'), ('하지 말 것', '짐작해서 채우지 말 것, 정할 수 없으면 정하지 말 것, 파일을 만들지 말 것.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>답이 오는 데 1분쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 요청 열 건의 표와, 답의 끝에서 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('맞는 사례의 수가 갈리는가', f'사례가 비어 있는 요청 가운데 R09와 R10은 맞는 사례가 하나다. R01과 R06은 둘, R07은 셋, R04는 {len(nfit["R04"])}건 모두다. R08은 하나도 없다. R05는 사례가 적혀 있는데 그 사례(S02)의 설비가 요청의 설비와 다르다.'),
        ('요청자의 말로 고르지 않았는가', 'R01의 「야간조」를 보고 야간에 뜬 S05라고 적었다면 규칙의 3번을 어긴 것이다. 그럴듯한 짐작과 사람의 답은 다르다.'),
        ('정하지 않고 되물은 것', '맞는 사례가 하나이면 묻지 않아도 되는지, 여럿이면 무엇을 묻는지, 누구의 승인을 받는지를 스스로 정하지 않고 물었는가. 물음이 몇 묶음인지 세어 둔다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 여섯 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 오늘 만드는 에이전트가 요청 앞에서 할 일을, 지금 Copilot이 내 요청 앞에서 하고 있다.')
 + ifs(('파일이 생겨 버렸다면', '탐색기에 <code>요청_처리.py</code>가 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.'),
       ('표가 내 종이와 다르다면', '「R06에 맞는 사례가 하나라고 했는데, 센서_입력.json에 HYD-02의 COOLER_DEGRADATION 사례는 S02와 S08 둘이야.」처럼 어디가 어떻게 다른지를 말한다.')))
+ nxt(2, '2. 언제 묻고 무엇을 승인으로 받을지 정한다', 0))

# ───────── 2단계
pages.append(hero('2단계', '언제 묻고 무엇을 승인으로<br>받을지 내가 정한다',
 '사람에게 묻는 에이전트를 만들 때 가장 어려운 것은 묻는 기능이 아니라 <b>언제 묻지 않을지</b>다. 무엇이든 묻는 에이전트는 일을 덜어 주지 못하고, 아무것도 묻지 않는 에이전트는 짐작으로 일한다. 승인도 같다. 누구의 어떤 승인을 받아들일지가 정해져 있지 않으면 「승인됨」이라는 글자는 아무것도 보장하지 않는다. 이 경계를 여섯 줄로 정한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '내 결정이 반영된 계획이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '여섯 가지마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abc'))
 + parts(('무엇을 만드는가', '첫 문단. 묻고 멈춘다, 답하면 이어서 처리한다, 승인 전에는 확정으로 적지 않는다. 이 세 마디가 프로그램의 성격이다.'), ('경계 여섯 가지', '둘째 문단. 1~4번이 질문과 답, 5~6번이 승인이다. 번호가 있어 Copilot도 나도 빠뜨린 것을 번호로 짚을 수 있다.'), ('계획 먼저, 권하는 답과 함께', '셋째 문단. 남은 빈자리를 물을 때 권하는 답을 붙이게 했다. 그래야 다음 단계에서 「권한 대로」 한마디로 답할 수 있다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 두 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고 계획을 내놓는다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. 「지금 입력에서 나올 결과」 표와 「정해 주셔야 하는 것」(권하는 답이 붙은 목록)이 보이게. 그 두 곳에 테두리를 얹는다.')
 + find(('지금 입력에서 나올 결과를 예고했는가', '답과 승인이 비어 있는 지금, 열 건이 각각 어느 상태가 될지를 계획에 적었는가. 적혀 있으면 3단계의 실행 결과와 견줄 것이 생긴다.'),
        ('다시 물어 온 것과 권하는 답', '여섯 가지를 정해 주었는데도 빈자리가 더 나온다. 대신 돌린 실행에서는 여덟 가지를 물었다. 첫 단계에 금지 문구가 있는 조치를 승인해도 받을 것인가, 가설인 원인에만 붙은 조치의 승인을 받을 것인가 같은 것이다. 권하는 답을 읽고, 받아들이지 않을 것이 있는지 본다.'))
 + ifs(('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('권하는 답 없이 묻기만 했다면', '「물은 것마다 네가 권하는 답을 하나씩 붙여 줘.」라고 한 줄을 보낸다.')))
+ nxt(3, '3. 만들고, 질문이 나오는 것을 본다', 1))

# ───────── 3단계
pages.append(hero('3단계', '만들고,<br>질문이 나오고 멈추는 것을 본다',
 '이제 만들게 하고 한 번 실행한다. 사람의 두 파일은 아직 비어 있다. 그러니 이번 실행에서 확정되는 요청은 하나도 없어야 하고, 사례를 정할 수 없는 요청은 질문을 낸 채 멈춰 있어야 한다. <b>멈춘 것이 고장이 아니라 설계한 동작</b>인지를 결과에서 읽는다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '요청_처리.py와 결과 두 파일이 있다'), ('바뀌면 안 되는 것', '에이전트.py, 도구.py, 사람 폴더의 두 파일')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 만들어 실행하게 한다',
 '<p>권하는 답을 받아들이지 않을 것이 있으면 보내기 전에 「다만 ○번은 이렇게 해 줘」를 한 줄 더한다.</p>' + copy(P3, pre=True, rich=richpre(P3, 'ab'))
 + parts(('받을 것과 뺄 것', '첫 문단. 권한 답을 받고, 시키지 않은 일은 빼게 한다.'), ('만들 것과 보고받을 모양', '둘째 문단. 실행한 뒤 상태를 표로, 질문은 낸 그대로 적게 했다. 질문의 글을 사람이 읽고 답할 수 있는지를 내가 보아야 하기 때문이다.')))
+ do(2, 'chat', 'Copilot 채팅', '터미널 명령을 실행해도 되는지 물으면, 명령을 읽고 허용한다',
 '<p>Copilot이 <code>python 요청_처리.py</code>를 실행하려 할 때 허락을 구하는 물음이 뜬다. 누르기 전에 명령의 글자를 읽는다. 만드는 데 3분쯤 걸린다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 요청_처리.py)와 「허용/계속」 버튼이 보이게.'))
+ do(3, 'editor', 'VS Code · 편집기', '첫 실행의 결과를 읽는다',
 '<p><code>결과/요청_처리.md</code>를 열어 미리 보기로 본다. 아래는 대신 돌린 실행의 같은 시점 결과다. 2단계의 가운데 칸대로 정했다면 상태가 같아야 한다.</p>' + t3
 + find(('묻지 않고 처리한 넷', 'R02와 R03은 사례가 적혀 있었고, R09와 R10은 맞는 사례가 하나뿐이었다. 상태 기록의 마지막 줄에 그 까닭이 적혀 있는가.'),
        ('사람이 읽고 답할 수 있는 질문인가', f'R01의 질문은 「{e(q01["물음"])}」이다. 선택지 둘의 차이(설비, 판단 시각)가 물음에 적혀 있어, 받는 사람이 다른 파일을 열지 않고 답할 수 있다. R04는 맞는 사례가 여덟을 넘어 설비부터 묻는다.'),
        ('확정이 하나도 없다', f'질문 대기 {cnt(r3)["질문_대기"]}건, 승인 대기 {cnt(r3)["승인_대기"]}건, 보류 {cnt(r3)["보류"]}건이다. R03은 5회차의 쿨러 사건(S01)이고 근거 상태가 SUPPORTED인데도 승인 대기에 머문다. md의 점검 순서와 조치에는 줄마다 「승인 전 · 확정 아님」이 붙어 있다.'),
        ('보류는 질문이 아니다', 'R09와 R10은 정보가 빠진 것이 아니라 에이전트가 낸 근거 상태가 SUPPORTED가 아니다. 사람이 답할 질문이 없고, 승인할 조치도 올라오지 않는다.'))
 + ifs(('에이전트.py가 바뀌었다면', '규칙의 5번에 어긋난다. 「에이전트.py는 이어받은 것이어서 고치지 않기로 했어. 원래대로 돌리고, 필요한 것은 요청_처리.py에서만 해 줘.」라고 말한다. 되돌리기 어려우면 완성 폴더의 같은 파일을 복사해 덮어쓴다.'),
       ('상태가 표와 다르다면', '어느 요청이 어떻게 다른지를 말한다. 「R09가 질문_대기로 나왔어. 맞는 사례가 하나뿐이면 묻지 않기로 했어(1번). 그 경우만 고치고 다시 실행해 줘.」')))
+ nxt(4, '4. 내가 답하고, 이어서 처리되는 것을 본다', 2))

# ───────── 4단계
pages.append(hero('4단계', '내가 답하고,<br>이어서 처리되는 것을 본다',
 '에이전트가 물었으니 이제 사람이 답할 차례다. 답은 채팅에 쓰지 않고 <code>사람/답변.json</code>에 내 손으로 적는다. 채팅은 지나가지만 파일은 남고, 누가 무엇이라고 답했는지가 기록이 된다. 네 건을 답하는데, <b>한 건은 일부러 틀리게 적어</b> 에이전트가 그것을 어떻게 다루는지 본다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '답한 요청이 다음 상태로 넘어가 있고, 전후가 상태 기록에 남아 있다'), ('바뀌면 안 되는 것', '요청_처리.py')])
+ do(1, 'editor', 'VS Code · 편집기', '<code>사람/답변.json</code>에 답 네 건을 적는다',
 '<p><code>사람/답변.json</code>을 연다. <code>[]</code>만 들어 있다. 전부 지우고 아래를 붙여넣어 저장한다(Ctrl+S). 칸의 뜻은 <code>사람/쓰는_법.md</code>에 있다.</p>'
 + paste(ANS, '사람/답변.json에 넣을 내용', '붙여넣는 곳 → 편집기에 연 사람/답변.json (있던 글을 모두 지우고)')
 + '<p style="margin-top:18px">넷째 줄을 본다. R05의 선택지는 <code>S02</code>, <code>S01</code>, <code>S07</code>인데 답이 <code>S7</code>이다. 손으로 적다 보면 생기는 실수를 일부러 넣었다. 고치지 말고 그대로 저장한다.</p>')
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '다시 실행하고, 전후를 견주게 한다',
 '<p>프로그램은 고치지 않는다. 같은 프로그램이 사람의 파일이 달라진 것만으로 다르게 움직이는지를 보는 것이다.</p>' + copy(P4)
 + shot('위 요청에 대한 Copilot의 답. 요청마다 실행 전과 후의 상태를 견준 표와, 반영되지 않은 답(R05의 S7)을 설명하는 부분이 보이게.'))
+ do(3, 'editor', 'VS Code · 편집기', '답한 네 건이 어디로 갔는지 본다',
 '<p><code>결과/요청_처리.md</code>를 다시 연다. 아래는 대신 돌린 실행에서 달라진 네 건이다. 나머지 여섯 건은 3단계와 같아야 한다.</p>' + t4
 + find(('답했더니 또 물었다', 'R04는 설비를 답하자 그 설비의 사례 넷 가운데 어느 것인지를 다시 물었다. 질문은 한 번에 하나이고, 둘째 질문의 순번은 2다.'),
        ('답했는데 승인으로 가지 않았다', 'R06은 사례가 S08로 정해졌지만 보류가 되었다. S08은 값은 있는데 관측이 모자라 가설만 남은 사례다. 사람이 답했다는 것이 근거를 채워 주지는 않는다.'),
        ('틀린 답을 고쳐 주지 않았다', 'R05의 <code>S7</code>은 반영되지 않았고 질문의 답은 비어 있다. Copilot이 「S07을 뜻한 것 같다」고 말하더라도 파일을 고쳐 주지 않았는지 <code>사람/답변.json</code>을 열어 본다.'),
        ('전후가 남았는가', '<code>결과/요청_처리.json</code>에서 R07의 <code>상태_기록</code>을 본다. 접수, 질문 대기, 승인 대기가 차례로 적혀 있고 셋째 줄에 누가 무엇이라고 답했는지가 있다.'))
 + '<section class="sect" style="margin:26px 0 0"><h2>「보류」의 세 가지가 결과의 세 상태다</h2><p>수업에서 현장의 「보류」라는 한 낱말이 세 가지 다른 상황을 가리킨다고 했다. 오늘의 결과에서는 그 셋이 서로 다른 상태로 나뉘어 있다. 누가 미루었는가에 따라 사람이 할 일이 다르기 때문이다.</p>' + three + '</section>'
 + ifs(('실행이 오류로 끝났다면', '답변.json의 모양이 깨진 것이다. 항목 사이의 쉼표, 마지막 항목 뒤에 쉼표가 없는지, 큰따옴표를 본다. 프로그램은 파일을 읽지 못하면 결과를 쓰지 않고 까닭을 내며 멈춘다.'),
       ('Copilot이 S7을 S07로 고쳐 버렸다면', '규칙의 2번에 어긋난다. 고친 것을 되돌리게 하고, 규칙 파일의 2번을 읽어 방금 한 일이 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.')))
+ nxt(5, '5. 답과 승인을 대신 해 달라고 해 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '답과 승인을<br>대신 해 달라고 해 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 어긋나는 일을 시켜 보아야 안다. 답이 오지 않아 일이 멈춰 있을 때, 급한 조치의 승인이 늦어질 때, 누구나 「그건 뻔하니까 네가 넣어 줘」라고 말하게 된다. 그 말을 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 3분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '사람 폴더의 두 파일, 결과의 상태')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '요청자의 말로 답을 대신 써 달라고 해 본다',
 '<p>R01은 아직 답이 없다. 요청 글에 「야간조」라고 적혀 있고, 선택지 둘 가운데 야간에 뜬 것은 S05다. 준비 단계에서 종이에 적어 둔 그 짐작이다.</p>'
 + copy(P5a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 답변.json을 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '<code>사람/답변.json</code>이 4단계에서 내가 저장한 네 줄 그대로인지 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고, 규칙 안에서 같은 목적을 이루는 길을 내놓았는가. 「야간조」라는 말만으로는 설비가 정해지지 않는다는 것까지 짚었는지도 본다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '급하니 승인된 것으로 쳐 달라고 해 본다',
 '<p>R03은 쿨러 사건이다. 근거 상태가 SUPPORTED이고, 팬 최대 운전(SOP-COOL-11)은 운전원이 승인하는 조치다. 승인이 날 것이 뻔해 보인다.</p>'
 + copy(P5b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>결과/요청_처리.json</code>에서 R03의 <code>상태</code>가 <code>승인_대기</code> 그대로인지, <code>사람/승인.json</code>이 <code>[]</code> 그대로인지 본다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 두 줄이다. 사람 폴더의 파일을 누가 쓴다고 적혀 있는가. 요청자가 적은 말에서 값을 미루어 채우는 일을 어떻게 하라고 적혀 있는가. 각각 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 한 줄이다. 근거 상태가 좋다는 것과 급하다는 것이 무엇을 대신하지 못한다고 적혀 있는가. 몇 번인가.</li><li><b>두 답에 함께 나온 줄</b>「요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다.</li></ul>'
 + note('수업에서 본 경계가 여기에 있다', '조회와 계산은 틀려도 다시 하면 되지만, 설비를 바꾸는 결정은 책임질 사람이 정해져 있어야 한다. 첫째 요청을 들어주었다면 사람이 답하지 않은 것이 사람의 답으로 기록되었을 것이고, 둘째 요청을 들어주었다면 승인한 사람이 없는 확정이 남았을 것이다. 둘 다 결과 파일만 보아서는 가려낼 수 없다.')
 + ifs(('멈추지 않고 써 넣어 버렸다면', '편집기에서 사람 폴더의 파일을 직접 되돌려 저장하고, 다시 실행하게 한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(6, '6. 내 손으로 승인하고 거절한다', 4))

# ───────── 6단계
pages.append(hero('6단계', '내 손으로<br>승인하고 거절한다',
 'Copilot이 하지 않은 일을 내가 한다. 승인도 답과 같이 파일에 적는다. 세 가지 결정을 넣는다. 받아들여질 승인 하나, 역할이 맞지 않는 승인 하나, 거절 하나다. 승인이 들어왔다고 다 확정이 되는 것이 아니라, <b>2단계에서 내가 정한 조건에 맞는 승인만</b> 확정이 되는지를 본다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '확정 한 건과 반려 한 건이 있고, 나머지는 사람을 기다리는 상태로 남아 있다')])
+ do(1, 'editor', 'VS Code · 편집기', '틀린 답을 고치고, <code>사람/승인.json</code>에 결정 세 건을 적는다',
 '<p>먼저 <code>사람/답변.json</code>의 넷째 줄에서 <code>"S7"</code>을 <code>"S07"</code>로 고쳐 저장한다. 4단계에서 반영되지 않은 답을 답한 사람이 바로잡는 것이다.</p>'
 '<p>다음으로 <code>사람/승인.json</code>을 열어 <code>[]</code>를 지우고 아래를 붙여넣어 저장한다.</p>'
 + paste(APP, '사람/승인.json에 넣을 내용', '붙여넣는 곳 → 편집기에 연 사람/승인.json (있던 글을 모두 지우고)')
 + '<p style="margin-top:18px">둘째 줄을 본다. SOP-FAN-03(계획 정지와 베어링 교체)은 3단계의 md에서 승인 역할이 공장장이었다. 여기에는 운전원이 승인했다고 적혀 있다.</p>')
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '다시 실행하고, 세 결정이 어떻게 되었는지 듣는다',
 copy(P6)
 + shot('위 요청에 대한 Copilot의 답. 세 결정이 각각 반영되었는지를 적은 표와, 지금 확정인 요청을 적은 부분이 보이게.'))
+ do(3, 'editor', 'VS Code · 편집기', '끝난 상태를 읽는다',
 '<p><code>결과/요청_처리.md</code>를 연다. 아래는 완성 폴더의 결과다.</p>' + t6
 + find(('확정은 승인한 조치 하나다', 'R03의 조치 넷 가운데 승인된 것은 SOP-COOL-11뿐이다. md에서 그 줄에만 「승인됨」과 승인한 사람이 적혀 있고 나머지 셋은 「승인되지 않음」이다.'),
        ('역할이 맞지 않는 승인', f'R02는 승인 대기 그대로이고 <code>승인</code> 칸이 비어 있다. 상태 기록의 마지막 줄 끝에 「{e(fin["R02"]["상태_기록"][-1]["까닭"].split(": ")[-1])}」이라고 적혀 있다. 승인이라는 글자가 파일에 있다는 것과 승인이 받아들여졌다는 것은 다르다.'),
        ('거절은 사유와 함께 남는다', 'R07은 반려가 되었고 거절한 사람과 사유가 <code>승인</code> 칸에 들어 있다. 점검 계획은 지워지지 않고 「승인 전 · 확정 아님」인 채로 남아 있다.'),
        ('고친 답이 반영되었다', 'R05는 사례 S07로 정해져 승인 대기로 넘어갔다.'))
 + '<div class="tree" style="white-space:pre-wrap;font-size:13.5px;margin-top:18px">' + '\n'.join(e(l.strip()).replace('[승인됨', '<b>[승인됨').replace('문태식]', '문태식]</b>') for l in r03) + '</div>'
 + f'<p style="margin-top:18px">끝난 상태는 확정 {cnt(fin)["확정"]}건, 반려 {cnt(fin)["반려"]}건, 승인 대기 {cnt(fin)["승인_대기"]}건, 보류 {cnt(fin)["보류"]}건, 질문 대기 {cnt(fin)["질문_대기"]}건이다. 열 건 가운데 여덟 건이 아직 끝나지 않았다. 4단계의 표로 돌아가, 그 여덟 건마다 다음에 움직여야 하는 사람이 누구인지를 짚어 본다.</p>'
 + ifs(('R02가 확정으로 나왔다면', '2단계에서 6번 줄을 다르게 정했는지 본다. 그대로 보냈는데 확정이 되었다면 「R02의 승인은 역할이 운전원인데 SOP-FAN-03의 승인 역할은 공장장이야. 역할이 같을 때만 받기로 했어. 그 경우만 고치고 다시 실행해 줘.」라고 말한다.'),
       ('실행이 오류로 끝났다면', '승인.json의 쉼표와 큰따옴표를 본다. <code>null</code>에는 따옴표를 붙이지 않는다.')))
+ '<section class="sect" style="margin-top:40px"><h2>시간이 남으면</h2>'
  '<p><b>아쉬운 곳을 찾아 되돌려 준다.</b> <code>결과/요청_처리.md</code>는 요청 번호 순서로 적혀 있다. 지금 내가 답할 질문과 승인할 요청을 찾으려면 열 개의 절을 끝까지 읽어야 한다. 이것을 Copilot에게 말해 고친다. 어떻게 말하느냐에 따라 돌아오는 것이 달라진다.</p>'
  '<div class="vs"><div class="bad"><b>막연하게</b><q>결과 md가 보기 불편해. 고쳐 줘.</q>무엇이 불편한지 AI는 모른다. 대신 돌린 실행에서는 아무것도 고치지 않고, 불편해 보일 만한 곳 다섯을 들어 어느 것이냐고 되물었다. 한 번 더 주고받아야 한다.</div>'
  '<div class="good"><b>구체적으로</b><q>md가 요청 번호 순서로만 적혀 있어서 사람이 할 일이 열 개의 절에 흩어져 있어. 맨 위에 「사람이 할 일」 절을 더해 줘. md를 쓰는 부분만 고치고 json의 칸과 상태를 정하는 부분은 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>사람이 할 일이 열 개의 절에 흩어져 있다</div><div><b>왜</b>답할 질문과 승인할 요청을 찾으려면 끝까지 읽어야 한다</div><div><b>어디를</b>요청_처리.py에서 md를 쓰는 부분</div><div><b>어디까지</b>요청마다의 절, json의 칸, 상태를 정하는 부분은 그대로</div></div>'
  '<p>무엇이, 왜, 어디를, 어디까지. 네 문장을 아래 칸에 내 말로 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.</p>'
  + write('w6', '무엇이 문제인지, 왜 문제인지, 요청_처리.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
  + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P7, pre=True) + '</details>'
  '<p style="margin-top:18px">완성 폴더의 md는 맨 위가 아래와 같이 시작한다. 고친 뒤에는 <code>결과/요청_처리.json</code>이 고치기 전과 같은지도 본다.</p>'
  '<div class="tree" style="white-space:pre-wrap;font-size:13px;line-height:1.7">' + e('## 사람이 할 일\n\n' + todo) + '</div>'
  '<p style="margin-top:22px"><b>남은 질문에 답해 본다.</b> <code>사람/답변.json</code>에 R04의 둘째 질문의 답(<code>"질문": 2</code>, 답 <code>"S04"</code>)을 더하고 터미널에서 <code>python 요청_처리.py</code>를 실행한다. R04는 승인 대기로 넘어간다. 이어서 <code>사람/승인.json</code>에 R04의 SOP-PMP-03을 운전원이 승인했다고 적고 다시 실행해 본다. 받아들여지는가. 상태 기록에 어떤 까닭이 남는가. 5회차의 마지막 단계에서 본 그 절차다.</p>'
  '<p><b>지나간 흔적은 어디에 남는가.</b> 6단계에서 <code>S7</code>을 <code>S07</code>로 고친 뒤 R05의 상태 기록에는 「S7을 반영하지 않음」이라는 줄이 없다. 결과는 실행할 때마다 세 입력 파일에서 처음부터 다시 계산되기 때문이다. 틀린 답이 한 번 들어왔었다는 사실까지 남기려면 무엇이 더 있어야 하는가. 답을 고쳐 쓰지 않고 새 줄로 더하게 하는 방법과, 실행할 때마다 기록을 덧붙여 쌓는 방법을 견주어 본다.</p></section>'
+ nxt(None, None, 5))

names = ['준비', '1. 무엇이 빠졌는지 읽게 한다', '2. 정하고 계획 받기', '3. 만들고 질문 보기', '4. 내가 답하기', '5. 대신 해 달라고 해 보기', '6. 내 손으로 승인하기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>빠진 요청 → 질문 → 답 → 승인</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-07-2-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 6단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 const file=!!b.closest('.paste');try{await navigator.clipboard.writeText(text);say(file?'복사했습니다. 편집기에 연 파일에 붙여넣고 저장하세요.':'복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 정보가 부족하면 묻는 에이전트</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
