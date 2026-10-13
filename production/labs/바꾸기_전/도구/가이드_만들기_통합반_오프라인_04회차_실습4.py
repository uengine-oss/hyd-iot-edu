"""통합반 오프라인 04회차 실습 4 「지식 개정에 따른 변경 결과 확인하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다.
요청 글은 기록/ 의 원문에서, 표와 수는 완성/ 과 기록/ 의 파일에서 읽어 옮긴다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '04회차_실습4_지식_개정'
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
.ver{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0 6px}
.ver>div{border-radius:14px;padding:16px 18px;font-size:14.5px;line-height:1.7;border:1px solid var(--line);background:var(--card)}
.ver>div.old{background:#f6f8fa}.ver>div.new{background:var(--accent-soft);border-color:#c5d3fb}
.ver small{display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:4px}
.ver mark{background:#fff1a8;padding:0 3px;border-radius:3px}
.ver>div.item{grid-column:1 / -1;background:#fffdf3;border-color:#eadfae}
.ver dl{margin:6px 0 0;display:grid;grid-template-columns:64px 1fr;gap:2px 10px}.ver dt{color:var(--sub);font-size:13px}.ver dd{margin:0}
.chain svg{width:100%;height:auto;display:block;margin:14px 0 4px}
@media(max-width:760px){.flow,.vs,.four,.pipe,.chg,.cite,.ver{grid-template-columns:1fr}.pipe span,.cite>span{display:none}}
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 이전 기준과 새 기준이 판본으로 갈린 후보.json, 판본을 보고 대어 보는 대조.py, 기준의 구별 · 중복 · 낡은 인용을 조회하는 개정_조회.py</b></div></div>'
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

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1, P2, P3, P3b, P4, P5, P5b, P5c, P6a, P6b, P7, PXa, PXb = (P(f'{n}_prompt.txt') for n in ('1', '2', '3', '3b', '4', '5', '5b', '5c', '6a', '6b', '7', '여유a', '여유b'))
a, rest = P1.split(' 두 판본 사이에', 1); b, c = ('두 판본 사이에' + rest).split(' 이 폴더의 규칙만으로는', 1)
P1rich = f'<span class="p-a">{e(a)}</span> <span class="p-b">{e(b)}</span> <span class="p-c">{e("이 폴더의 규칙만으로는" + c)}</span>'
assert re.sub(r'<[^>]+>', '', html.unescape(P1rich)) == P1

# ── 시작 · 완성 폴더와 기록에서 옮기는 값
S, W = R / '시작', R / '완성'
rd = lambda p: p.read_text(encoding='utf-8')
D0 = json.loads(rd(S / '결과' / '후보.json')); D = json.loads(rd(W / '결과' / '후보.json'))
def sources(d):  # (지금 기준의 출처들, 이전 기준의 출처들)
    now, old = [], []
    def take(x):
        now.append(x['출처']); old.extend(o['출처'] for o in x.get('이전', []))
    for c in d['후보']:
        take(c)
        for k in ('단계', '조건'):
            for it in c.get(k, []): take(it)
    for x in d['관계']: take(x)
    for x in d['보류']: take(x)
    return now, old
now0, old0 = sources(D0); now, old = sources(D)
n0, n1 = len(now0), len(now) + len(old)
assert not old0 and all('판본' not in s for s in now0)
v_now = {v: sum(1 for s in now if s['판본'] == v) for v in ('1', '2')}; v_old = {v: sum(1 for s in old if s['판본'] == v) for v in ('1', '2')}
assert v_now['1'] + v_now['2'] == len(now) == n0 and v_old['2'] == 0
old_doc = rd(S / '문서' / 'HM-8_cooler-fan-manual.md').splitlines(); new_doc = rd(S / '문서' / 'HM-8_cooler-fan-manual_개정.md').splitlines()
assert len(old_doc) == len(new_doc)
def sect(lines, i): return next(l.split()[1] for l in reversed(lines[:i + 1]) if l.startswith('## '))
changed = [(sect(old_doc, i), o, n) for i, (o, n) in enumerate(zip(old_doc, new_doc)) if o != n]
assert len(changed) == 2 == v_now['2']
mk = lambda s, w: e(s).replace(w, f'<mark>{w}</mark>')
difftable = ('<table class="res"><thead><tr><th>절</th><th>판본 1</th><th>판본 2</th></tr></thead><tbody>'
             + ''.join(f'<tr><td class="nw"><b>{s}</b></td><td>{mk(o, "24시간")}</td><td>{mk(n, "48시간")}</td></tr>' for s, o, n in changed) + '</tbody></table>')
import csv, io
vrows = list(csv.reader(io.StringIO(rd(S / '문서' / '판본_목록.csv'))))
vtable = ('<table class="res"><thead><tr>' + ''.join(f'<th>{e(h)}</th>' for h in vrows[0]) + '</tr></thead><tbody>'
          + ''.join('<tr>' + ''.join(f'<td class="nw">{e(c) or "—"}</td>' for c in r) + '</tr>' for r in vrows[1:]) + '</tbody></table>')
C = {x['번호']: x for x in D['후보']}
st = C['K-004']['단계'][1]; st0 = {x['번호']: x for x in D0['후보']}['K-004']['단계'][1]
assert st['출처']['판본'] == '2' and st['이전'][0]['출처']['판본'] == '1' and st['검토'] == '승인' and st['이전'][0]['내용'] == st0['내용']
assert C['K-004']['검토자'] != st['검토자'] and '48' not in C['K-005']['단계'][1]['내용']
hold_i = next(i for i, h in enumerate(D['보류']) if '이전' in h) + 1
def jtree(obj, marks):  # 한 단계 깊이만 줄을 바꿔 적는다(값은 파일의 것 그대로)
    j = lambda v: json.dumps(v, ensure_ascii=False)
    s = e('{\n' + ',\n'.join(f'  {j(k)}: {j(v)}' for k, v in obj.items()) + '\n}', quote=False)
    for m in marks: assert m in s, m; s = s.replace(m, f'<b>{m}</b>')
    return f'<div class="tree wrap">{s}</div>'
rep = rd(W / '결과' / '대조_결과.md'); q = rd(W / '결과' / '개정_조회.md')
assert f'검사한 출처: {n1}건' in rep and '어긋난 것: 0건' in rep and f'검사한 출처: {n1}건' in P('3_대조_결과.md')
assert '기준이 바뀐 항목: 2건' in q and '중복: 0건' in q and '낡은 인용: 0건' in q
r5 = P('5b_대조_결과.md'); q5 = P('5b_개정_조회.md'); q7 = P('7_번호_겹친_뒤_개정_조회.md')
assert '어긋난 것: 1건' in r5 and '중복: 4건' in q5 and '중복: 1건' in q7
def mdrows(md, head):  # md 의 한 절에서 표의 줄(머리 줄과 구분 줄을 뺀 것)을 뽑는다
    body = md.split(head, 1)[1].split('\n## ', 1)[0]
    rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in body.splitlines() if l.startswith('| ')]
    return rows[0], rows[1:]
def tbl(head, rows, nw=(0,), marks=()):
    def cell(i, c):
        s = e(c)
        for m in marks: s = s.replace(m, f'<mark>{m}</mark>')
        return f'<td class="nw">{s}</td>' if i in nw else f'<td>{s}</td>'
    return ('<table class="res"><thead><tr>' + ''.join(f'<th>{e(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(cell(i, c) for i, c in enumerate(r)) + '</tr>' for r in rows) + '</tbody></table>')
qh, qr = mdrows(q, '## 이전 기준과 새 기준'); assert len(qr) == 4 and '인용' in qh
keep = [qh.index(k) for k in ('번호', '구분', '문서', '판본', '구간', '내용', '검토')]
qtable = tbl([qh[i] for i in keep], [[r[i] for i in keep] for r in qr], nw=(0, 1, 2, 3, 4), marks=('24시간', '48시간'))
bh, br = mdrows(q, '## 판본별 출처'); bytable = tbl(bh, br, nw=(0, 1, 2, 3))
h5, b5 = mdrows(r5, '## 어긋난 것'); assert len(b5) == 1
bad5 = tbl(h5, b5, nw=(0, 1), marks=('판본 `1`', '판본 `2`'))
d5h, d5 = mdrows(q5, '## 중복'); assert len(d5) == 4
dup5 = tbl(d5h, d5, nw=(0,))
q5h, q5r = mdrows(q5, '## 이전 기준과 새 기준'); assert q5r[0][q5h.index('판본')] == q5r[1][q5h.index('판본')] == '1'
d7h, d7 = mdrows(q7, '## 중복'); assert len(d7) == 1
dup7 = tbl(d7h, d7, nw=(0,))

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하면</th></tr></thead><tbody>
<tr><td><b>글이 바뀌지 않은 출처의 판본</b></td><td><mark>1번 줄</mark> 처음 뽑을 때 읽은 판본 「1」로 적는다. 새 판본과 다시 대조하지 않은 것을 새 판본에서 왔다고 적지 않는다</td><td>「새 판본에도 같은 글이 있으면 2로 옮긴다」로 하면 지금 기준이 모두 지금 판본을 가리켜 읽기 쉽다. 대신 그 기준이 어느 판본에서 처음 나왔는지는 사라진다</td></tr>
<tr><td><b>바뀐 문장을 인용한 보류</b></td><td><mark>2번 줄</mark> 단계와 같은 방식으로 한다. 내용과 출처는 판본 2의 글로, 이전 칸에 판본 1의 것을 남긴다</td><td>「보류는 후보가 아니니 그대로 둔다」로 하면 손은 덜 가지만, 지금 판본에 없는 글을 인용한 항목이 파일에 남는다</td></tr>
<tr><td><b>이전 칸에 남길 범위</b></td><td><mark>3번 줄</mark> 바뀐 부분만이 아니라 그 항목의 내용, 수치, 출처 전체를 남긴다</td><td>「바뀐 수만 남긴다」로 하면 파일은 짧아지지만, 이전 기준을 읽으려면 지금 기준의 글에 옛 수를 끼워 맞춰야 한다</td></tr>
<tr><td><b>같은 판본을 다시 반영할 때</b></td><td><mark>4번 줄</mark> 지금 출처가 이미 그 판본이고 인용이 그 판본의 글과 같으면 아무것도 고치지 않는다</td><td>정해 두지 않으면 같은 반영을 두 번 했을 때 이전 칸이 한 건 더 쌓이거나 승인이 대기로 돌아갈 수 있다</td></tr>
<tr><td><b>판본이 적히지 않은 출처</b></td><td><mark>5번 줄</mark> 대조.py는 판본 칸이 없는 출처를 어긋난 것으로 본다</td><td>「판본이 없으면 첫 판본으로 본다」로 하면 빠뜨린 출처가 통과한다. 어느 판본에 대어 보았는지 모르는 검사가 된다</td></tr>
</tbody></table>'''

chain = '''<div class="chain"><svg viewBox="0 0 760 250" role="img" aria-label="문서 식별자 하나에 판본 둘, 한 단계에 이전 기준과 지금 기준">
<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#5b6573"/></marker></defs>
<rect x="250" y="8" width="260" height="38" rx="10" fill="#eef1f5" stroke="#cfd6e0"/><text x="380" y="32" text-anchor="middle" font-size="15" font-weight="800" fill="#1f2630">문서 식별자 HM-8 (바뀌지 않는다)</text>
<rect x="60" y="78" width="270" height="62" rx="12" fill="#f6f8fa" stroke="#cfd6e0" stroke-width="2"/><text x="78" y="102" font-size="14" font-weight="800" fill="#5b6573">판본 1 · 첫 판본</text><text x="78" y="124" font-size="13" fill="#333b47">… 연속 운전은 24시간 이내로 한다.</text>
<rect x="430" y="78" width="270" height="62" rx="12" fill="#eaf0ff" stroke="#2f5bea" stroke-width="2"/><text x="448" y="102" font-size="14" font-weight="800" fill="#2f5bea">판본 2 · 지금 판본</text><text x="448" y="124" font-size="13" fill="#333b47">… 연속 운전은 48시간 이내로 한다.</text>
<line x1="430" y1="109" x2="338" y2="109" stroke="#5b6573" stroke-width="2" marker-end="url(#ar)"/><text x="380" y="100" text-anchor="middle" font-size="12" fill="#5b6573">앞 판본</text>
<line x1="320" y1="46" x2="220" y2="76" stroke="#cfd6e0" stroke-width="2"/><line x1="440" y1="46" x2="540" y2="76" stroke="#cfd6e0" stroke-width="2"/>
<rect x="150" y="178" width="460" height="62" rx="12" fill="#fffdf3" stroke="#eadfae" stroke-width="2"/><text x="380" y="202" text-anchor="middle" font-size="14" font-weight="800" fill="#1f2630">K-004 팬 최대 운전 · 단계 2 (항목은 하나)</text>
<text x="250" y="226" text-anchor="middle" font-size="13" fill="#5b6573">이전: 24시간</text><text x="510" y="226" text-anchor="middle" font-size="13" fill="#2f5bea" font-weight="700">지금: 48시간</text>
<line x1="250" y1="178" x2="210" y2="146" stroke="#5b6573" stroke-width="2" marker-end="url(#ar)"/><line x1="510" y1="178" x2="550" y2="146" stroke="#2f5bea" stroke-width="2" marker-end="url(#ar)"/>
<text x="196" y="168" text-anchor="end" font-size="12" fill="#5b6573">출처</text><text x="566" y="168" font-size="12" fill="#2f5bea">출처</text></svg></div>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 4회차 · 실습 4 · 30분</small>개정된 조건 한 건을 반영하고<br>이전 기준과 새 기준을 출처로 가른다',
 '앞의 두 실습에서 매뉴얼 HM-8을 읽어 지식을 뽑았고, 사람이 검토해 승인했다. 그 매뉴얼이 개정되어 조건 한 건이 바뀌었다. 가장 빠른 길은 지식 파일에서 옛 수를 새 수로 바꿔 쓰는 것이다. 그러면 어제까지 무엇이 기준이었는지, 새 기준이 어느 판본에서 왔는지가 함께 지워진다. 오늘은 <b>이전 기준을 지우지 않고 새 기준을 더해, 두 기준을 출처의 판본으로 가르는 일</b>을 한다.',
 [('끝나면 남는 것', '판본이 적힌 후보.json, 판본을 보는 대조.py, 개정_조회.py와 조회 결과'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '4회차 실습 2 · 3을 마쳤다'), ('준비에 쓰는 시간', '약 2분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>입력은 같은 문서의 두 판본과, 첫 판본에서 뽑아 검토까지 마친 지식 파일이다. 바뀐 조건 한 건을 그 파일에 반영한 다음, 프로그램 둘로 확인한다. 하나는 출처를 그 판본의 원문에 대어 보고, 하나는 이전 기준과 새 기준이 갈려 있는지와 같은 대상이 둘로 들어가지 않았는지를 조회한다.</p>'
  '<div class="pipe"><div><b>두 판본과 지난 결과</b>HM-8의 판본 1과 2, 검토를 마친 지식<small>문서/ · 결과/후보.json</small></div><span>→</span><div class="out"><b>개정이 반영된 지식</b>지금 기준과 이전 기준. 기준마다 문서 식별자, 판본, 구간, 인용<small>결과/후보.json</small></div><span>→</span><div><b>대조와 조회</b>출처가 그 판본에 있는가, 기준이 갈려 있는가, 중복이 없는가<small>대조.py · 개정_조회.py</small></div></div>'
  + chain +
  '<p style="margin:14px 0 0">문서 식별자는 하나이고 판본이 둘이다. 지식 쪽에서도 조치와 단계는 하나이고, 그 안에 이전 기준과 지금 기준이 각자의 출처를 달고 있다. 이 그림이 오늘 끝났을 때의 모양이다.</p>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과를 새 판본 옆에 놓고 판단하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>두 판본에서 달라진 줄과, 그 줄을 인용한 지식을 짚게 한다</div><div><em>2</em><b>정해 준다</b>규칙이 비워 둔 다섯 가지를 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>어느 칸이 어떻게 바뀌는지 먼저 듣는다</div><div><em>4</em><b>작게 만든다</b>한 건을 반영해 원문과 맞추고, 조회 프로그램을 붙인다</div><div><em>5</em><b>되돌려 준다</b>아쉬운 곳은 무엇이 왜 문제인지 말해 고친다</div></div>'
  '<p style="margin:18px 0 0">1~4단계와 7단계가 이 다섯 걸음이다. 그 사이에 두 가지를 더 해 본다. 같은 개정을 한 번 더 반영하고 파일을 일부러 틀리게 고쳐 프로그램이 무엇을 잡는지 보고(5단계), 규칙에 어긋나는 요청을 일부러 보내 본다(6단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 f'<div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md           <i>← 이 폴더의 규칙</i>\n├─ <span>문서/</span>                               <i>← 보관해 둔 원문. 읽기만 한다</i>\n│  ├─ 문서_목록.csv                      <i>← 문서 식별자 ↔ 제목</i>\n│  ├─ <b>판본_목록.csv</b>                      <i>← 문서 식별자 ↔ 판본 ↔ 파일</i>\n│  ├─ HM-8_cooler-fan-manual.md          <i>← HM-8의 판본 1</i>\n│  ├─ <b>HM-8_cooler-fan-manual_개정.md</b>     <i>← HM-8의 판본 2. 오늘 새로 들어왔다</i>\n│  ├─ PM-02_powerpack-pm-checklist.md\n│  └─ PR-07_spare-parts-standard.md\n├─ <span>지난_시간/</span>                          <i>← 스키마와 그래프. 읽기만 한다</i>\n├─ <span>결과/</span>\n│  ├─ 후보.json                          <i>← 판본 1에서 뽑아 검토한 지식. 출처 {n0}건</i>\n│  └─ 대조_결과.md\n└─ 대조.py                               <i>← 출처를 원문에 대어 보는 프로그램</i></div>'
 '<p><code>문서</code> 폴더의 원문과 <code>결과/후보.json</code>, <code>대조.py</code>는 앞 실습의 완성본 그대로다. 새로 들어온 것은 노랗게 보이는 두 파일이다. <b>규칙 파일</b>은 Copilot이 이 폴더에서 지키는 약속이고, <b>완성 폴더</b>에는 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 문서, 지난_시간, 결과 폴더와 대조.py가 보이고 문서 폴더의 여섯 파일이 펼쳐져 있게.'))
+ do(2, 'editor', 'VS Code · 편집기', '판본 목록을 읽고, 달라진 문장 하나를 내 눈으로 찾는다',
 '<p><code>문서/판본_목록.csv</code>를 연다. 한 줄이 판본 하나다.</p>' + vtable
 + '<p style="margin-top:16px">HM-8은 문서 식별자가 하나인데 줄이 둘이다. 둘째 줄의 「앞 판본」이 1을 가리킨다. 어느 줄도 가리키지 않는 판본 2가 <b>지금 판본</b>이다. 파일 이름에 「개정」이 붙어 있지만, 판본을 정하는 것은 파일 이름이 아니라 이 목록이다.</p>'
 '<p>두 HM-8 파일을 좌우로 나란히 열고, 양쪽에서 찾기(Ctrl+F)로 <code>이내로 한다</code>를 찾는다. 어느 절의 어느 절차 몇 단계인지, 수가 무엇에서 무엇으로 바뀌었는지를 종이에 적는다. 같은 수가 문서의 다른 절에도 나오는지도 본다. 뒤에서 AI가 짚은 것이 맞는지를 가리는 사람은 나다.</p>'
 + note('앞 실습에서 들은 말', '4회차 실습 2의 6단계에서 원문의 24시간을 48시간으로 고쳐 달라고 해 보았다. 원문은 고치지 않는 것이 그 폴더의 규칙이었다. 값이 바뀌어야 한다면 문서를 관리하는 쪽에서 개정한 판을 내고, 그 판에서 다시 뽑는 것이 길이다. 오늘 그 개정한 판이 들어왔다.'))
+ nxt(1, '1. 만들기 전에, 달라진 줄을 짚게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>달라진 줄을 짚게 한다',
 '첫마디가 「개정판을 반영해 줘」이면 AI는 두 파일을 읽자마자 지식 파일을 고친다. 무엇이 달라졌다고 보았는지, 그것이 지식의 어느 항목에 닿는다고 보았는지는 고친 결과 속에 묻힌다. 그래서 첫 요청은 <b>달라진 줄과, 그 줄을 인용한 항목을 말해 보라</b>는 요청으로 한다. 고칠 곳의 목록을 먼저 손에 쥔다.',
 [('걸리는 시간', '약 3분'), ('이 단계가 끝나면', '달라진 줄과 고칠 항목의 목록, Copilot이 나에게 묻는 것이 채팅에 있다'), ('아직 바뀌면 안 되는 것', '모든 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 입력 칸 아래의 방식이 <b>에이전트</b>, 모델이 <b>GPT-6 Luna</b>인지 보고, 다르면 그 글자를 눌러 바꾼다.</p>')
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 답이 오는 데 1분쯤 걸린다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 판본 목록, HM-8의 두 판본, 지식 파일. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '달라진 줄을 앞 판본과 새 판본의 글로 나란히 내게 했다. 그다음 그 줄을 인용한 항목을 번호로 짚게 했다. 「같은 수가 들었지만 달라지지 않은 항목」을 따로 물은 것은, 개정이 닿지 않는 곳까지 고치는 일을 미리 막으려는 것이다.'), ('하지 말 것', '스스로 정하지 말 것, 파일을 고치지 말 것. 이 두 문장이 없으면 AI가 빈자리를 스스로 채운다.')))
+ do(2, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다. 표는 두 판본 파일을 줄마다 견준 것이다.</p>' + difftable
 + shot('1단계 요청에 대한 Copilot의 답. 달라진 줄을 판본 1과 판본 2로 나란히 보인 표, 그 줄을 인용한 항목의 번호, 답의 끝에서 정해 달라고 묻는 부분이 보이게. 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('달라진 줄과 조건의 수', f'달라진 줄은 {len(changed)}줄({changed[0][0]}, {changed[1][0]})이고 바뀐 조건은 한 건이다. 팬 100 % 연속 운전의 한도 하나가 두 절에 적혀 있다. 내 종이의 절 번호와 같은지 견준다.'),
        ('고칠 항목', f'달라진 줄을 인용한 항목은 둘이다. K-004(팬 최대 운전)의 단계 2와, <code>보류</code>의 {hold_i}번째 항목. 보류에는 번호 칸이 없어 차례로 짚는다. 이 둘 말고 다른 항목을 고치겠다고 하지는 않았는가.'),
        ('고치지 않을 항목', f'K-005(팬 최대 운전과 부하 80 %)의 단계 2도 팬을 100 %로 올린다. 그 줄은 「{e(C["K-005"]["단계"][1]["출처"]["인용"])}」뿐이고 두 판본에서 글자가 같다. 연속 운전 한도가 원래 적혀 있지 않다. Copilot이 이 항목을 그대로 둔다고 했는지 본다.'))
 + note('되묻는 까닭', '답의 끝에 정해 달라는 물음이 있다. 규칙 파일의 「정해져 있지 않은 것」에 여섯 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 지금의 <code>후보.json</code>에는 출처에 판본 칸이 하나도 없다. 글이 바뀌지 않은 출처에 어느 판본을 적을지가 첫 물음으로 나오기 쉽다.')
 + ifs(('파일이 바뀌어 버렸다면', '요청의 마지막 문장이 빠진 것이다. 무엇을 고쳤는지 묻고 되돌리게 한다. 되돌리기 어려우면 받은 <code>시작</code> 폴더를 새로 풀어 열고, 요청을 처음부터 끝까지 복사해 보낸다.'),
       ('달라진 줄을 다르게 말한다면', '「다시 해 줘」라고 하지 않는다. 「HM-8.5의 SOP-COOL-11 2번 줄과 HM-8.8의 둘째 줄이 달라. 네 표에는 다른 줄이 있어.」처럼 어디가 어떻게 다른지를 말한다.')))
+ nxt(2, '2. 비워 둔 것을 내가 정하고, 계획부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '비워 둔 것을 내가 정하고,<br>계획부터 받는다',
 '개정을 반영하는 일에는 정답이 하나가 아닌 결정이 여럿 있다. 손대지 않은 출처에 어느 판본을 적을지, 이전 기준을 어디까지 남길지, 같은 개정을 두 번 받으면 어떻게 할지. 이것을 정하는 일이 이 실습의 핵심이고, <b>요청하는 사람이 정한다.</b> 기준은 하나다. 개정한 뒤에도 어느 기준이 어느 판본에서 왔는지를 이 파일만 보고 말할 수 있어야 한다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '내 결정이 반영된 계획이 채팅에 있다'), ('아직 바뀌면 안 되는 것', '모든 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '다섯 가지마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과의 수가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 1번을 다르게 정하면 4단계의 「판본별 출처」 표가 달라진다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abc'))
 + parts(('무엇을 왜 하는가', '첫 문단. 반영한 뒤에 무엇을 말할 수 있어야 하는지를 적었다. 이 한 문장이 이전 기준을 지우지 않는 까닭이 된다.'), ('다섯 가지 결정', '번호를 붙여 한 줄에 결정 하나씩 적었다. 까닭을 함께 적은 줄은 Copilot이 비슷한 다른 자리에서도 같은 쪽으로 판단하게 한다.'), ('계획 먼저', '마지막 문단. 어느 칸이 어떻게 바뀌는지와 출처의 수를 미리 말하게 했다. 수를 알고 있어야 고친 뒤에 엉뚱한 곳이 바뀌었는지 알 수 있다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 세 가지를 찾는다',
 '<p>Copilot은 파일을 고치지 않고 계획을 내놓는다. 「이렇게 고치겠다」와 「이것은 더 정해 달라」가 함께 온다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. K-004 단계 2의 칸마다 지금 값과 반영 뒤의 값을 견준 표, 판본별 출처의 수, 끝의 「더 정해 주셔야 할 것」이 보이게. 출처의 수와 다시 물어 온 항목에 테두리를 얹는다.')
 + find(('바뀌는 항목이 둘뿐인가', f'내용과 수치와 인용이 바뀌는 것은 K-004의 단계 2와 보류의 한 항목이다. 나머지 {v_now["1"]}건에는 판본 칸만 더한다고 했는가. K-004라는 후보의 <code>검토</code>와 <code>검토자</code>는 건드리지 않는다고 했는가.'),
        ('출처의 수', f'지금은 {n0}건이다. 반영하면 이전 칸에 남는 출처가 {len(old)}건 생겨 검사할 출처는 {n1}건이 된다. 판본 「2」를 적는 출처는 {v_now["2"]}건뿐이다. 계획의 수가 이와 같은지 본다(1번을 다르게 정했다면 다르다).'),
        ('새 기준의 검토', '바뀐 단계에 <code>검토</code>를 <code>대기</code>로 둔다고 했는가. 지난번에 승인한 사람의 이름을 새 기준에 옮겨 적겠다고 하지는 않았는가. 새 기준은 아직 아무도 원문과 대조하지 않았다.'))
 + note('계획이 다시 묻는 것', '다섯 가지를 정해 주어도 빈자리가 더 나온다. 예: 보류에도 검토 칸을 둘지, 보류의 이전 칸에 수치를 둘지. 보류에는 원래 그 칸들이 없기 때문이다. 다음 단계의 요청이 이 물음에 답한다.')
 + ifs(('계획 없이 파일부터 고쳤다면', '요청의 마지막 문단이 빠진 것이다. 무엇을 고쳤는지 묻고 되돌리게 한 다음, 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('후보를 새로 만들겠다고 한다면', 'K-009 같은 새 번호가 계획에 보이면 그대로 두지 않는다. 「같은 조치니까 K-004 안에서 고쳐야 해. 규칙 4번을 다시 읽어 줘.」라고 말한다.')))
+ nxt(3, '3. 한 건을 반영하고, 새 판본과 맞춘 뒤 승인한다', 1))

# ───────── 3단계
pages.append(hero('3단계', '한 건을 반영하고,<br>새 판본과 맞춘 뒤 승인한다',
 '이제 고치게 한다. 범위는 지식 파일과 대조 프로그램, 두 파일까지다. 대조 프로그램을 함께 고치는 까닭이 있다. 앞 실습의 <code>대조.py</code>는 문서마다 파일이 하나라고 알고 있어서, 판본 2의 문장을 인용한 출처를 판본 1에 대어 보고 틀렸다고 한다. 고친 뒤에는 AI에게 맞는지 묻지 않고 <b>내가 새 판본 옆에 놓고 읽은 다음, 내 이름으로 승인한다.</b>',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '후보.json에 이전 기준과 새 기준이 있고, 새 기준에 내 이름의 승인이 적혀 있다'), ('아직 없어야 하는 것', '조회 프로그램')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 범위를 정해 준다',
 '<p>계획이 다시 물어 온 둘은 아래 글에 미리 정해 적어 두었다. 내 계획이 묻지 않은 줄이 섞여 있어도 그대로 보내면 된다. 파일 둘을 고치고 한 번 실행하므로 1~2분 걸린다. 터미널에서 <code>python 대조.py</code>(또는 <code>python3 대조.py</code>)를 실행해도 되느냐고 물으면, 명령이 그것인지 읽고 허용한다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'ab'))
 + parts(('받을 것과 내가 정한 둘', '보류에는 검토 칸을 두지 않고, 이전 칸에는 지금 항목에 있는 칸만 남긴다. 「없는 수치를 새로 뽑아 적지 말라」는 줄을 눈여겨본다. 개정을 반영하는 일이 새로 추출하는 일로 번지지 않게 막는 줄이다.'), ('범위', '파일 둘, 실행 한 번. 어긋난 것이 나와도 스스로 더 고치지 말라고 했다. 어느 쪽이 틀렸는지는 내가 보고 정한다. 조회 프로그램은 다음 단계에서 따로 시킨다.'))
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 대조.py)와 「허용/계속」 버튼이 보이게.'))
+ do(2, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '고친 단계를 새 판본과 나란히 읽는다',
 '<p><code>결과/후보.json</code>에서 찾기(Ctrl+F)로 <code>48시간</code>을 찾는다. 「팬 최대 운전」의 단계 2다. 오른쪽에는 <code>문서/HM-8_cooler-fan-manual_개정.md</code>의 HM-8.5를 연다. 아래는 완성 폴더의 그 단계다.</p>'
 + jtree(st, ['"출처"', '"이전"', '"검토"', '"검토자"'])
 + shot('결과/후보.json과 문서/HM-8_cooler-fan-manual_개정.md를 좌우로 나란히 연 VS Code 화면. 왼쪽은 K-004 단계 2의 출처와 이전 칸, 오른쪽은 HM-8.5의 SOP-COOL-11이 보이게.')
 + find(('지금 기준이 새 판본의 글자 그대로인가', f'<code>출처</code>의 <code>판본</code>이 「2」이고, <code>인용</code>이 개정판의 그 줄과 번호까지 같은가. <code>수치</code>가 {e(json.dumps(st["수치"], ensure_ascii=False))}인가.'),
        ('이전 기준이 통째로 남았는가', '<code>이전</code>에 한 건이 있고, 그 안의 출처는 <code>판본</code>이 「1」이며 인용은 첫 판본의 글 그대로인가. 왼쪽 파일을 <code>HM-8_cooler-fan-manual.md</code>로 바꿔 열어 견준다.'),
        ('검토가 대기인가', '이 단계 안에 <code>"검토": "대기"</code>가 생겼는가. 이 단계가 딸린 K-004의 <code>검토</code>(승인)와 <code>검토자</code>는 그대로인가. 조치를 승인했던 사람은 24시간이라는 기준을 읽고 승인한 것이다.'),
        ('손대지 않을 곳이 그대로인가', f'<code>"판본": "2"</code>를 찾으면 {v_now["2"]}곳만 나와야 한다. K-005의 단계 2에 48시간이 들어가 있지 않은가.'))
 + f'<p style="margin-top:18px"><code>결과/대조_결과.md</code>도 연다. 완성 폴더에서는 「검사한 출처: {n1}건, 어긋난 것: 0건」이었다. {n0}건에서 {len(old)}건이 는 것은 이전 칸에 남은 출처까지 검사했기 때문이다.</p>')
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '내 이름을 밝혀 새 기준을 승인한다',
 '<p>원문과 같다는 것을 내 눈으로 확인했으면 승인한다. 아래 글의 「서민재」를 <b>내 이름으로 바꿔</b> 보낸다. 원문과 다른 곳을 찾았다면 승인하지 않고, 어느 칸이 어떻게 다른지를 말해 고치게 한다.</p>'
 + copy(P3b)
 + '<p style="margin-top:18px">답이 오면 그 단계의 <code>검토</code>가 <code>승인</code>이 되고 같은 자리에 <code>검토자</code>가 생겼는지 본다. 한 조치 안에 검토한 사람이 둘이 된다. 조치를 승인한 사람과, 개정된 기준을 승인한 사람이다.</p>'
 + note('승인을 AI에게 맡기지 않는 까닭', '규칙 파일 6번은 새 기준의 승인을 「사람이 새 판본과 대조한 뒤 번호를 짚고 자기 이름을 밝힌 때에만」 적게 한다. 대조 프로그램이 0건이라고 해도 그것은 인용이 원문에 있다는 뜻일 뿐, 내용이 인용과 같은 뜻인지는 보지 못한다.')
 + ifs(('이전 칸이 없이 수만 바뀌었다면', '덮어쓴 것이다. 「K-004 단계 2에 이전 칸이 없어. 판본 1의 내용, 수치, 출처를 이전 칸에 남겨 줘.」라고 말한다.'),
       ('어긋난 것이 0건이 아니라면', '번호와 까닭을 읽는다. 「판본 칸이 없다」가 많다면 판본을 적지 않은 출처가 남은 것이다. 어느 번호인지 들어 그 출처에 판본을 적게 한다.')))
+ nxt(4, '4. 반영한 결과를 조회하는 프로그램을 만든다', 2))

# ───────── 4단계
pages.append(hero('4단계', '반영한 결과를 조회하는<br>프로그램을 만든다',
 '방금 한 건을 눈으로 읽었다. 그런데 개정한 뒤에 물어야 할 것은 그 한 건만이 아니다. 같은 조치의 이전 기준과 새 기준이 출처로 갈려 있는가. 반영하다가 같은 대상이 둘로 들어가지 않았는가. 지금 기준인데 지금 판본에는 없는 글을 인용한 것이 남아 있지 않은가. 이 셋은 파일 전체를 훑어야 답할 수 있으므로 <b>프로그램에게 묻는다.</b>',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '개정_조회.py와 결과/개정_조회.md가 있다'), ('바뀌면 안 되는 것', '후보.json, 대조.py')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '무엇을 조회할지 정해 주고, 한 번 돌리게 한다',
 '<p>규칙 파일은 결과 파일의 맨 위 세 줄과 절 셋의 이름까지만 정해 두었다. 무엇을 중복으로 볼지와 표의 칸은 비워 두었다. 아래 글은 그것을 정한 것이다.</p>'
 + copy(P4, pre=True, rich=richpre(P4, 'abc'))
 + parts(('무엇을 확인하려는가', '첫 문단. 조회하려는 물음 셋을 말로 적었다. 프로그램이 무엇에 답해야 하는지를 알아야 표의 모양이 거기에 맞게 나온다.'), ('내가 정한 셋', '1은 중복으로 볼 것 넷, 2는 표의 칸, 3은 절 하나 더. 「판본별 출처」는 2단계에서 1번을 어떻게 정했는지가 그대로 드러나는 표다.'), ('어디까지', '파일 하나, 실행 한 번. 조회하는 프로그램이 지식 파일을 고치면 조회의 뜻이 없다.')))
+ do(2, 'editor', 'VS Code · 편집기', '<code>결과/개정_조회.md</code>를 열어 세 물음의 답을 읽는다',
 '<p>미리 보기(Ctrl+Shift+V)로 연다. 완성 폴더에서 맨 위의 세 줄은 「기준이 바뀐 항목: 2건, 중복: 0건, 낡은 인용: 0건」이었다. 아래는 그 파일의 「이전 기준과 새 기준」 절이다(인용 칸은 자리가 좁아 여기서는 뺐다).</p>' + qtable
 + shot('결과/개정_조회.md를 미리 보기로 연 VS Code 화면. 맨 위의 세 수와 「이전 기준과 새 기준」 표가 보이게. K-004 단계 2의 두 줄에서 판본 칸에 테두리를 얹는다.')
 + find(('두 기준이 출처로 갈리는가', 'K-004 단계 2가 두 줄이다. 이전은 판본 1, 지금은 판본 2. 번호와 구간은 같고 판본만 다르다. 「24시간은 어디에서 온 기준인가」에 이 표의 한 줄로 답할 수 있다.'),
        ('새 기준을 누가 검토했는가', '지금 기준의 검토 칸에 내 이름이 보이는가. 보류는 후보가 아니어서 검토가 비어 있다.'),
        ('표에 인용 칸이 있는가', '복사 상자의 2번 줄에 적은 칸에는 인용이 없다. 그런데 규칙 파일의 「정해져 있는 것」은 기준마다 인용을 함께 적으라고 한다. 완성 폴더의 표에는 인용 칸이 들어 있다. 내 표에는 있는지, Copilot이 답에서 그 까닭을 밝혔는지 본다.'))
 + '<p style="margin-top:18px">끝의 「판본별 출처」 절은 아래와 같았다.</p>' + bytable
 + f'<p style="margin-top:14px">지금 기준의 출처 {len(now)}건 가운데 {v_now["1"]}건이 판본 1을 가리킨다. 그래도 낡은 인용은 0건이다. 그 {v_now["1"]}건의 인용은 지금 판본의 같은 절에도 글자 그대로 있기 때문이다. 개정에서 글이 바뀐 줄을 아직 판본 1로 인용하고 있는 항목이 있었다면 여기에 걸린다.</p>'
 + '<div class="vs"><div class="good"><b>대조.py가 답하는 것</b><ul><li>출처마다 판본이 적혀 있는가</li><li>인용이 그 판본의 그 절에 글자 그대로 있는가</li><li>이전 칸의 출처도 그 판본에 있는가</li></ul></div><div class="good"><b>개정_조회.py가 답하는 것</b><ul><li>기준이 바뀐 항목마다 이전과 지금이 어느 판본인가</li><li>같은 번호, 같은 id, 같은 순서, 같은 관계가 둘인가</li><li>지금 기준이 지금 판본에 없는 글을 인용하는가</li></ul></div></div>'
 + ifs(('python을 찾을 수 없다고 나오면', '「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다.'),
       ('프로그램에 원문이 옮겨 적혀 있다면', '<code>개정_조회.py</code>에서 찾기(Ctrl+F)로 <code>HM-8</code>과 <code>48</code>을 찾는다. 나오지 않아야 한다. 문서의 이름이나 판본의 값이 프로그램 안에 적혀 있으면 다음 개정 때 쓸 수 없다.')))
+ nxt(5, '5. 한 번 더 반영하고, 일부러 틀리게 고쳐 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '한 번 더 반영하고,<br>일부러 틀리게 고쳐 본다',
 '중복 0건이라는 결과는 두 가지로 읽힌다. 정말 둘로 들어간 것이 없거나, 프로그램이 보지 못하거나. 어느 쪽인지는 흔들어 보아야 안다. 먼저 <b>같은 개정을 한 번 더 반영</b>하게 한다. 현장에서 가장 흔한 중복은 같은 판을 두 번 넣는 일이다. 그다음 파일을 <b>내 손으로 틀리게</b> 고쳐, 두 프로그램이 각각 무엇을 잡는지 본다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '같은 반영을 두 번 해도 늘지 않는 것을 보았고, 프로그램이 잡는 것과 잘못 세는 것을 보았다'), ('끝에 원래대로여야 하는 것', '후보.json')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '같은 판본을 한 번 더 반영해 달라고 한다',
 '<p>보내기 전에 짐작해 둔다. 이전 칸에 한 건이 더 쌓일까. 내 승인이 대기로 돌아갈까.</p>' + copy(P5)
 + find(('파일이 그대로인가', f'<code>후보.json</code>에서 <code>"이전"</code>을 찾는다. 여전히 {len(old)}곳이고, 칸마다 한 건씩인가. K-004 단계 2의 <code>검토</code>가 <code>승인</code> 그대로인가.'),
        ('두 프로그램의 수가 같은가', f'완성 폴더에서는 검사한 출처 {n1}건 · 어긋난 것 0건, 기준이 바뀐 항목 2건 · 중복 0건 · 낡은 인용 0건 그대로였다.'),
        ('무엇을 보고 이미 반영되었다고 했는가', '2단계의 4번 줄이 그 기준이다. Copilot이 답에서 그 기준에 대어 본 것을 밝혔는지 본다.')))
+ do(2, 'editor', 'VS Code · 편집기', '<code>후보.json</code>의 두 곳을 직접 고쳐 저장한다',
 '<p>찾기(Ctrl+F)로 <code>"판본": "2"</code>를 찾는다. 처음 나오는 곳이 K-004 단계 2의 지금 출처다. 그곳만 고친다.</p>'
 '<div class="chg"><div class="tree">고치기 전 (K-004 단계 2의 출처)\n"문서": "HM-8", <b>"판본": "2"</b>, "구간": "HM-8.5"</div><div class="tree">고친 뒤\n"문서": "HM-8", <b>"판본": "1"</b>, "구간": "HM-8.5"</div></div>'
 '<p>다음으로 <code>"번호": "K-005"</code>를 찾아 번호만 고치고 저장한다(Ctrl+S).</p>'
 '<div class="chg"><div class="tree">고치기 전\n"번호": <b>"K-005"</b></div><div class="tree">고친 뒤\n"번호": <b>"K-004"</b></div></div>'
 '<p>첫째는 새 기준의 출처를 옛 판본으로 잘못 적은 것이고, 둘째는 서로 다른 조치 둘에 같은 번호가 붙은 것이다.</p>')
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '프로그램은 그대로 두고 다시 실행하게 한다',
 '<p>어디를 고쳤는지는 말하지 않는다.</p>' + copy(P5b)
 + '<p style="margin-top:18px">아래는 같은 두 곳을 고쳤을 때 실제로 나온 결과다. 먼저 <code>결과/대조_결과.md</code>의 「어긋난 것」.</p>' + bad5
 + '<p style="margin-top:18px">다음은 <code>결과/개정_조회.md</code>의 「중복」.</p>' + dup5
 + find(('판본이 틀리면 대조가 잡는다', '48시간이라는 문장은 판본 1에 없다. 대조 프로그램은 그 문장이 판본 2의 같은 절에 있다는 것까지 알려 준다. 조회 결과의 「이전 기준과 새 기준」 표에서는 K-004 단계 2의 이전과 지금이 둘 다 판본 1로 나온다. 출처로 가를 수 없게 된 것이다.'),
        ('낡은 인용은 0건 그대로다', '인용의 글 자체는 지금 판본에 있기 때문이다. 판본을 잘못 적은 것은 대조가, 지금 판본에 없는 글을 인용한 것은 조회가 잡는다. 두 프로그램이 보는 곳이 다르다.'),
        ('중복이 4건이다', '내가 겹치게 한 것은 번호 하나다. 나머지 세 줄을 읽어 본다. 서로 다른 조치의 단계 1 · 2 · 3이 「순서가 같은 단계」로 세어졌다. 이 수를 보고는 같은 대상이 몇 개나 둘로 들어갔는지 말할 수 없다. 7단계에서 이것을 되돌려 준다.')))
+ do(4, 'editor', 'VS Code · 편집기 → Copilot 채팅', '두 곳을 원래대로 되돌리고 한 번 더 실행한다',
 '<p>편집기에서 실행 취소(Ctrl+Z)로 <code>"판본": "2"</code>와 <code>"번호": "K-005"</code>로 되돌리고 저장한다. 그다음 아래를 보낸다. 어긋난 것 0건, 중복 0건으로 돌아왔는지 본다.</p>' + copy(P5c)
 + ifs(('아무것도 잡히지 않았다면', '파일을 저장하지 않은 것이다. 편집기 탭의 이름 옆에 동그란 점이 남아 있으면 저장되지 않은 것이다.'),
       ('내 결과는 중복이 1건이라면', '내 프로그램은 처음부터 단계의 순서를 조치마다 따로 견준 것이다. 잘 만들어진 것이므로 7단계에서는 다른 아쉬운 곳을 고른다.')))
+ nxt(6, '6. 규칙을 일부러 건드려 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 개정을 다루는 일터에서는 「옛 기준은 이제 안 쓰니 지우자」와 「새 기준은 새 항목으로 따로 넣자」는 말이 늘 나온다. 둘 다 깔끔해 보인다. 지금 일부러 그렇게 해 달라고 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 3분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '문서 폴더, 후보.json')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '이전 기준과 옛 판본을 지워 달라고 해 본다',
 '<p>정리하자는 그럴듯한 요청이다.</p>'
 + copy(P6a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 지우지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('세 가지가 모두 그대로인가', '<code>후보.json</code>의 이전 칸, <code>문서/HM-8_cooler-fan-manual.md</code>, <code>판본_목록.csv</code>의 첫 줄. 탐색기와 편집기에서 본다.'),
        ('어느 규칙을 들었는가', '요청 하나에 일이 셋 들어 있었다. 답이 든 규칙의 번호를 적어 둔다.'),
        ('멈추기만 했는가', f'안 된다고만 하지 않고 규칙 안의 길을 내놓았는가. 옛 판본을 지우면 판본 1을 가리키는 출처 {v_now["1"] + v_old["1"]}건을 대어 볼 원문이 없어진다는 것을 짚었는지도 본다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '새 기준을 새 후보로 따로 만들어 달라고 해 본다',
 '<p>이번에는 지우지 않겠다고 물러서면서, 후보를 둘로 나누자고 한다.</p>'
 + copy(P6b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + f'<p style="margin-top:18px">답이 오면 <code>후보.json</code>의 후보가 {len(D["후보"])}건 그대로이고 K-009가 없는지 본다. 이 요청대로 되었다면 번호와 id가 모두 새것이어서, 4단계에서 정한 중복 넷으로는 잡히지 않는다. Copilot이 그 점을 짚었는지 본다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 두 줄이다. 「개정은 덮어쓰기가 아니다」로 시작하는 줄은 몇 번인가. 개정되기 전의 판본을 무엇이라고 부르는 줄은 몇 번인가.</li><li><b>둘째 요청</b>「같은 대상을 둘로 만들지 않는다」로 시작하는 줄이다. 새 번호와 새 id를 어떻게 하라고 적혀 있는가.</li><li><b>두 답에 함께 나온 줄</b>「채팅에서 요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다.</li></ul>'
 + note('지우지 않고, 나누지 않는 까닭', '이전 기준을 지우면 새 기준이 무엇에서 바뀐 것인지를 말할 수 없고, 옛 판본을 지우면 그 판본에서 온 지식을 다시 대조할 수 없다. 같은 조치를 후보 둘로 나누면 원문에는 절차가 하나인데 지식에는 둘이 되어, 어느 쪽이 지금 기준인지를 파일이 말해 주지 못한다. 그래프에 넣으면 같은 대상을 가리키는 노드가 둘이 된다. 기준은 항목 안에서 바뀌고, 무엇이 언제의 기준인지는 출처의 판본이 말한다.')
 + ifs(('멈추지 않고 해 버렸다면', '문서가 지워졌다면 완성 폴더의 <code>문서</code>에서 같은 파일을 가져온다. <code>후보.json</code>이 바뀌었다면 방금 한 것을 되돌려 달라고 말한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다.')))
+ nxt(7, '7. 아쉬운 곳을 찾아 되돌려 준다', 5))

# ───────── 7단계
pages.append(hero('7단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '조회 프로그램은 시킨 대로 만들어졌다. 그런데 5단계에서 번호 하나를 겹치게 했더니 중복이 4건으로 나왔다. 수가 부풀면 조회 결과를 믿고 판단할 수 없다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '개정_조회.py의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>조회 결과가 좀 이상해. 제대로 나오게 해 줘.</q>무엇이 이상한지 AI는 모른다. 짐작이 가는 곳을 고치고, 나머지는 어느 부분이냐고 되묻는다. 짐작이 내가 본 문제와 같았는지는 내가 다시 확인해야 하고, 한 번 더 주고받아야 한다.</div>'
  '<div class="good"><b>구체적으로</b><q>번호 하나를 겹치게 했는데 중복이 4건으로 나왔어. 서로 다른 조치의 단계 셋이 함께 세어졌어. 이러면 몇 개가 둘로 들어갔는지 말할 수 없어. 단계의 순서를 견주는 부분만 고쳐서 후보 한 건 안에서만 찾게 해 줘. 나머지 검사와 결과의 모양은 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>겹친 것은 하나인데 중복이 4건으로 나온다</div><div><b>왜</b>중복의 수로 판단할 수 없게 된다</div><div><b>어디를</b>개정_조회.py에서 단계의 순서를 견주는 부분</div><div><b>어디까지</b>나머지 검사 셋, 결과의 절과 칸, 후보.json, 대조.py는 그대로</div></div></section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 조회 결과에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/개정_조회.md</code>를 다시 본다. 다음 개정이 들어왔을 때 이 파일을 들고 판단할 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>중복의 수를 믿을 수 있는가</b>5단계에서 번호 하나를 겹치게 했을 때 몇 건이 나왔는가. 겹친 것보다 많이 나왔다면 무엇이 함께 세어졌는가.</li><li><b>지금 기준만 따로 읽을 수 있는가</b>이전 기준과 섞이지 않게, 지금 쓰는 기준만 모은 절이 있는가.</li><li><b>무엇이 바뀌었는지가 한눈에 보이는가</b>이전과 지금의 글에서 달라진 낱말(24시간, 48시간)이 어디인지 표에서 바로 보이는가.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 「후보.json과 대조.py는 건드리지 마」를 꼭 넣는다.</p>'
 + write('w7', '무엇이 문제인지, 왜 문제인지, 개정_조회.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(중복의 수)를 고른 경우의 글이다. 완성 폴더의 프로그램은 이 글을 보내 고친 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P7, pre=True) + '</details>'
 '<p style="margin-top:18px">고친 뒤에는 고쳐진 것을 내 손으로 확인한다. 5단계처럼 <code>"번호": "K-005"</code>를 <code>"K-004"</code>로 고쳐 저장하고, VS Code의 터미널(Ctrl+`)에서 <code>python 개정_조회.py</code>를 실행한다. 완성 폴더의 프로그램으로 그렇게 했을 때 「중복」 절은 아래와 같았다. 본 다음에는 번호를 되돌리고 한 번 더 실행한다.</p>' + dup7
 + shot('되돌려 준 뒤 Copilot이 개정_조회.py의 바뀐 부분을 보여 주는 화면(바뀐 줄이 색으로 표시되고, 나머지 검사는 바뀌지 않은 것이 보이게).')
 + find(('맨 위의 세 수는 그대로인가', '번호를 되돌린 뒤의 결과가 4단계와 같은가(완성 폴더는 2건, 0건, 0건).'),
        ('요청한 곳만 바뀌었는가', 'Copilot이 답에서 고친 곳을 밝혔는가. 결과의 절 이름과 표의 칸이 그대로인가.'))
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>같은 수가 다른 곳에도 있는지 묻는다.</b> 개정에서 바뀐 것은 24시간이라는 수다. 같은 수가 다른 문서에도 적혀 있다면 그것도 바뀌어야 하는가. 아래를 보내고, Copilot이 찾은 곳마다 원문의 문장으로 같은 조건인지 다른 조건인지를 가렸는지 본다. <code>문서/PM-02_powerpack-pm-checklist.md</code>에서 <code>24시간</code>을 찾아 내 눈으로도 읽는다.</p>'
  + copy(PXa)
  + '<p style="margin-top:18px"><b>새 기준을 옆의 조치에도 넣어 달라고 해 본다.</b> 6단계에서 건드리지 않은 줄이 하나 더 있다. 아래를 보내고, K-005의 단계 2가 그대로인지, Copilot이 규칙 파일의 어느 줄을 들었는지 본다. 팬을 100 %로 올리는 조치이니 같은 한도가 걸릴 것이라는 짐작은 그럴듯하다. 그 짐작을 적을 원문이 있는지가 문제다.</p>'
  + copy(PXb, 'Copilot에게 보낼 요청 (규칙에 어긋난다)') + '</section>'
+ nxt(None, None, 6))

names = ['준비', '1. 달라진 줄을 짚게 한다', '2. 정하고 계획 받기', '3. 한 건을 반영하고 승인하기', '4. 조회 프로그램 만들기', '5. 다시 반영하고 틀리게 고쳐 보기', '6. 규칙을 건드려 보기', '7. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>개정 → 이전 기준 · 새 기준</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-04-4-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 7단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 개정된 조건을 반영하고 기준을 출처로 가르기</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
