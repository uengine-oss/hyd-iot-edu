"""통합반 오프라인 04회차 실습 2 「기술 문서에서 필요한 지식 직접 추출하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다.
요청 글은 기록/ 의 원문에서, 표와 수는 완성/ 과 기록/ 의 파일에서 읽어 옮긴다."""
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

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1, P2, P3, P4, P5, P5b, P6a, P6b, P7, PXa, PXb = (P(f'{n}_prompt.txt') for n in ('1', '2', '3', '4', '5', '5b', '6a', '6b', '7', '여유a', '여유b'))
a, rest = P1.split(' 문서마다', 1); b, c = ('문서마다' + rest).split(' 이 폴더의 규칙만으로는', 1)
P1rich = f'<span class="p-a">{e(a)}</span> <span class="p-b">{e(b)}</span> <span class="p-c">{e("이 폴더의 규칙만으로는" + c)}</span>'
assert re.sub(r'<[^>]+>', '', html.unescape(P1rich)) == P1

# ── 완성 폴더와 기록에서 옮기는 값
D = json.loads((R / '완성' / '결과' / '후보.json').read_text(encoding='utf-8'))
C = {x['번호']: x for x in D['후보']}
n_step = sum(len(x.get('단계', [])) for x in D['후보']); n_cond = sum(len(x.get('조건', [])) for x in D['후보'])
n_src = len(D['후보']) + n_step + n_cond + len(D['관계']) + len(D['보류'])
rep4 = P('4_대조_결과.md'); rep5 = P('5_고친_뒤_대조_결과.md'); rep = (R / '완성' / '결과' / '대조_결과.md').read_text(encoding='utf-8')
assert f'검사한 출처: {n_src}건' in rep4 and '어긋난 것: 0건' in rep4 and '어긋난 것: 2건' in rep5
KO = {'Cause': '원인', 'Skill': '조치', 'FailureMode': '고장 유형'}
ctable = ('<table class="res"><thead><tr><th>번호</th><th>클래스</th><th>name</th><th>등록됨</th><th>단계</th><th>조건</th><th>출처의 구간</th></tr></thead><tbody>'
          + ''.join(f'<tr><td class="nw"><b>{x["번호"]}</b></td><td class="nw">{x["클래스"]} ({KO[x["클래스"]]})</td><td>{e(x["name"])}</td><td class="nw">{"<mark>true</mark>" if x["등록됨"] else "false"}</td><td>{len(x.get("단계", [])) or "—"}</td><td>{len(x.get("조건", [])) or "—"}</td><td class="nw">{x["출처"]["구간"]}</td></tr>' for x in D['후보'])
          + '</tbody></table>')
step2 = C['K-004']['단계'][1]; cond1 = C['K-004']['조건'][0]
assert step2['수치'] == [{'값': 100, '단위': '%'}, {'값': 24, '단위': '시간'}] and '아닐 때' in cond1['내용']
def jtree(obj, marks):  # 한 단계 깊이만 줄을 바꿔 적는다(값은 파일의 것 그대로)
    j = lambda v: json.dumps(v, ensure_ascii=False)
    s = e('{\n' + ',\n'.join(f'  {j(k)}: {j(v)}' for k, v in obj.items()) + '\n}', quote=False)
    for m in marks: assert m in s, m; s = s.replace(m, f'<b>{m}</b>')
    return f'<div class="tree wrap">{s}</div>'
rel = next(x for x in D['관계'] if x['a'] == 'cause:ambient-temperature-rise')
hold_by = {}
for h in D['보류']: hold_by[h['출처']['구간']] = hold_by.get(h['출처']['구간'], 0) + 1
n_mit = sum(1 for h in D['보류'] if 'MITIGATED_BY' in h['내용'])
def mdrows(md, head):  # md 의 한 절에서 표의 줄을 뽑는다
    body = md.split(head, 1)[1].split('\n## ', 1)[0]
    return [[c.strip() for c in l.strip().strip('|').split('|')] for l in body.splitlines() if l.startswith('| ') and not l.startswith('| 번호') and not l.startswith('|---')]
bad = mdrows(rep5, '## 어긋난 것'); assert len(bad) == 2
badtable = ('<table class="res"><thead><tr><th>번호</th><th>검사</th><th>까닭</th></tr></thead><tbody>'
            + ''.join(f'<tr><td class="nw"><b>{e(r[0])}</b></td><td class="nw">{e(r[1])}</td><td>{e(r[2]).replace("24분", "<mark>24분</mark>")}</td></tr>' for r in bad) + '</tbody></table>')
read = mdrows(rep, '## 사람이 읽을 곳'); assert len(read) == 6
readtable = ('<table class="res"><thead><tr><th>번호</th><th>내용</th><th>인용</th></tr></thead><tbody>'
             + ''.join(f'<tr><td class="nw"><b>{e(r[0])}</b></td><td>{e(r[1])}</td><td>{e(r[2])}</td></tr>' for r in (read[0], read[1], read[4], read[5])) + '</tbody></table>')
X = json.loads(P('여유_후보.json'))
xs = len(X['후보']) + sum(len(x.get('단계', [])) + len(x.get('조건', [])) for x in X['후보']) + len(X['관계']) + len(X['보류'])
assert f'검사한 출처: {xs}건' in P('여유_대조_결과.md')

choices = '''<table class="res"><thead><tr><th style="width:140px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하면</th></tr></thead><tbody>
<tr><td><b>어디까지 뽑을지</b></td><td><mark>1번 줄</mark> HM-8.4부터 HM-8.8까지만. 쿨러 냉각 성능 상실의 원인, 조치, 금지가 모여 있는 다섯 절이다</td><td>「세 문서를 모두」로 넓히면 답이 길어지고 내가 원문과 맞춰 읽을 양이 몇 배가 된다. 작게 만들어 확인한 뒤에 넓힌다</td></tr>
<tr><td><b>스키마에 자리가 없는 내용</b></td><td><mark>2번 줄</mark> 단계와 조건은 조치 후보의 칸에 담는다. 나머지(사전 확률, 승인하는 사람 등)는 보류에 까닭과 함께 적는다</td><td>「나머지는 버린다」로 하면 파일은 짧아지지만, 지난 시간의 스키마에 무엇이 모자랐는지의 기록이 함께 사라진다</td></tr>
<tr><td><b>두 곳에 적힌 내용</b></td><td><mark>3번 줄</mark> 하나로 둔다. 금지와 제한은 HM-8.8의 문장을 인용해 그 문장이 가리키는 조치에만 붙인다</td><td>「적힌 곳마다 따로 둔다」로 하면 같은 금지가 둘이 된다. 문서가 개정될 때 한쪽만 고쳐지면 서로 어긋난 지식 둘이 남는다</td></tr>
<tr><td><b>같은 대상인지, 새 id</b></td><td><mark>4번 줄</mark> 이름 · 다른 이름 · 태그 · 품번의 글자가 같을 때만 같은 대상이다. 새 id는 지난 시간의 약속(conventions)대로 짓는다</td><td>「뜻이 같으면 같은 대상」으로 하면 「외기 고온」과 「주변 온도 상승」처럼 AI의 짐작으로 합쳐지는 대상이 생긴다</td></tr>
<tr><td><b>근거 문장이 없는 관계</b></td><td><mark>5번 줄</mark> 문장 하나를 인용할 수 없는 관계는 만들지 않고 보류에 적는다</td><td>「글의 흐름으로 이어도 된다」로 하면 관계는 늘지만, 조치를 듣지 않는 원인에 잇는 잘못된 관계 추론이 들어올 자리가 열린다</td></tr>
<tr><td><b>인용을 어디까지 자를지</b></td><td><mark>6번 줄</mark> 번호가 붙은 줄이나 글머리표 줄은 줄 전체를, 문단 안에서는 문장 하나를 그대로</td><td>「필요한 낱말만 짧게」로 하면 「아닐 때」나 「이내」 같은 말이 인용 밖으로 잘려 나가도 알 수 없다</td></tr>
<tr><td><b>수치에 넣을 수</b></td><td><mark>7번 줄</mark> 단위가 붙은 수만. 절 번호와 절차 번호 속의 수는 넣지 않는다</td><td>「수는 모두」로 하면 SOP-COOL-11의 11 같은 번호가 값으로 들어와, 다음 실습에서 걸러 내야 한다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 4회차 · 실습 2 · 40분</small>기술 문서에서 지식 후보를 뽑고<br>후보마다 출처를 붙인다',
 '앞 실습에서는 포털이 매뉴얼에서 뽑아 준 후보를 검토했다. 이번에는 뽑는 쪽을 직접 만든다. 문서를 읽고 원인, 조치, 단계, 조건을 가려내는 일은 AI가 한다. 내가 할 일은 <b>무엇을 어떤 모양으로 뽑을지 정해 주는 것</b>과 <b>뽑힌 것이 원문과 같은지 가리는 것</b>이다. 후보마다 어느 문서의 어느 절 어느 문장에서 왔는지가 붙어 있어야 그 일을 할 수 있다.',
 [('끝나면 남는 것', '출처가 붙은 후보.json, 대조.py, 대조 결과'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '온라인 4일차의 인제스천 단원을 들었다'), ('준비에 쓰는 시간', '약 3분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>보관해 둔 원문과 지난 시간의 스키마 · 그래프가 입력이다. AI가 원문에서 후보를 뽑아 한 파일에 모으고, 작은 프로그램이 그 파일의 출처를 원문에 다시 대어 본다. 지식 그래프는 오늘 바뀌지 않는다. 후보는 검토를 기다리는 제안이다.</p>'
  '<div class="pipe"><div><b>원문과 스키마</b>문서 세 편, 지난 시간의 클래스와 등록된 대상<small>문서/ · 지난_시간/</small></div><span>→</span><div class="out"><b>지식 후보</b>후보 · 관계 · 보류. 하나하나에 문서 식별자, 구간, 인용<small>결과/후보.json</small></div><span>→</span><div><b>대조</b>인용이 원문의 그 절에 있는지 프로그램이 찾는다<small>대조.py → 결과/대조_결과.md</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과를 원문 옆에 놓고 판단하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>문서와 스키마를 읽고, 받을 자리가 있는 것과 없는 것을 가르게 한다</div><div><em>2</em><b>정해 준다</b>규칙이 비워 둔 일곱 가지를 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>몇 건이 나올지 먼저 듣는다</div><div><em>4</em><b>작게 만든다</b>다섯 절만 뽑아 원문과 맞추고, 대조 프로그램을 붙인다</div><div><em>5</em><b>되돌려 준다</b>아쉬운 곳은 무엇이 왜 문제인지 말해 고친다</div></div>'
  '<p style="margin:18px 0 0">1~4단계와 7단계가 이 다섯 걸음이다. 그 사이에 두 가지를 더 해 본다. 후보를 일부러 틀리게 고쳐 프로그램이 무엇을 잡고 무엇을 놓치는지 보고(5단계), 규칙에 어긋나는 요청을 일부러 보내 본다(6단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 '<div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md       <i>← 이 폴더의 규칙</i>\n├─ <span>문서/</span>                           <i>← 보관해 둔 원문. 읽기만 한다</i>\n│  ├─ 문서_목록.csv                  <i>← 문서 식별자 ↔ 파일</i>\n│  ├─ HM-8_cooler-fan-manual.md      <i>← 쿨러 팬 정비 매뉴얼</i>\n│  ├─ PM-02_powerpack-pm-checklist.md <i>← 정기 점검표와 시행 기준</i>\n│  └─ PR-07_spare-parts-standard.md  <i>← 예비품 관리 · 구매 기준서</i>\n├─ <span>지난_시간/</span>                      <i>← 지난 시간에 만든 것. 읽기만 한다</i>\n│  ├─ schema.json                    <i>← 클래스 11, 관계 12</i>\n│  └─ graph.json                     <i>← 노드 36, 관계 53</i>\n└─ <span>결과/</span>                           <i>← 지금은 비어 있다</i></div>'
 '<p><b>규칙 파일</b>은 Copilot이 이 폴더에서 일할 때 지키는 약속이다. 「하면 안 되는 것」과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 6단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」의 여섯 줄은 일부러 비워 둔 자리이고, 2단계와 4단계에서 내가 채운다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 문서, 지난_시간, 결과 네 폴더가 펼쳐져 있고 문서 폴더의 네 파일이 보이게.'))
+ do(2, 'editor', 'VS Code · 편집기', '원문에서 두 문장을 찾아 둔다',
 '<p><code>문서/HM-8_cooler-fan-manual.md</code>를 연다. 절마다 <code>HM-8.5</code> 같은 번호가 붙어 있다. 이 문서들에는 쪽이 없으므로, 오늘은 쪽 대신 <b>절의 번호</b>를 출처의 구간으로 쓴다. 문서 식별자는 파일 이름이 아니라 <code>문서_목록.csv</code>의 첫 칸(<code>HM-8</code>)이다.</p>'
 '<p>아래 두 문장을 찾기(Ctrl+F)로 찾아, 어느 절에 있는지 종이에 적는다. 뒤에서 AI가 뽑은 것이 맞는지를 가리는 사람은 나다. 내 눈으로 원문에서 본 문장이 하나는 있어야 가릴 수 있다.</p>'
 '<ul class="ask"><li><b>「REMOTE_AUTO가 아닐 때 쓰지 않는다」</b>무엇을 쓰지 않는다는 것인가. 「아닐 때」가 빠지면 뜻이 어떻게 되는가.</li><li><b>「24시간 이내로 한다」</b>어느 절차의 몇 단계인가. 같은 24시간이 다른 절에도 나오는가.</li></ul>'
 + note('지난 시간의 스키마는 좁다', '<code>지난_시간/schema.json</code>에서 <code>Skill</code>(조치)을 찾아본다. 속성이 <code>id</code>와 <code>name</code> 둘뿐이다. 매뉴얼에는 조치마다 단계와 조건이 적혀 있는데 받을 속성이 없다. 이것을 어떻게 할지가 오늘 내가 정할 것 가운데 하나다.'))
+ nxt(1, '1. 만들기 전에, 읽고 가르게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>읽고 가르게 한다',
 '첫마디가 「매뉴얼에서 지식을 뽑아 줘」이면 AI는 문서를 읽자마자 JSON을 쓴다. 어디까지 뽑을지, 스키마에 없는 내용을 어디에 둘지, 같은 말이 두 번 나오면 어떻게 할지를 AI가 알아서 정하고, 그 결정은 결과 속에 묻힌다. 그래서 첫 요청은 <b>읽고, 스키마에 대어 보고, 정할 수 없는 것은 물어보라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 문서를 어떻게 읽었는지와, 나에게 묻는 것이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 문서 세 편을 다 읽으므로 답이 오는 데 2분쯤 걸린다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 지난 시간의 두 파일, 문서 폴더. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '문서마다 표 · 단계 · 수와 단위 · 금지 문장이 어느 절에 있는지를 표로 내게 했다. 그다음 다섯 절을 스키마에 대어 보게 했다. 받을 자리가 없는 것이 드러난다.'), ('하지 말 것', '스스로 정하지 말 것, 파일을 만들지 말 것. 이 두 문장이 없으면 AI가 빈자리를 스스로 채운다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 문서별로 절마다 표 · 단계 · 수와 단위 · 금지 문장을 정리한 표, 받을 자리가 없는 것의 목록, 답의 끝에서 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('내가 찾은 두 문장이 표에 있는가', '「REMOTE_AUTO가 아닐 때 쓰지 않는다」가 HM-8.8의 금지 문장으로, 24시간이 HM-8.5와 HM-8.8의 수로 잡혀 있는가. 내 종이와 절 번호가 같은지 견준다.'),
        ('받을 자리가 없는 것을 가렸는가', '작업 단계, 조건, 사전 확률, 승인하는 사람이 「자리가 없는 것」 쪽에 있는가. <code>Skill</code>의 속성이 <code>id</code>와 <code>name</code>뿐이라는 까닭을 들었는가. 스키마에 없는 클래스를 새로 만들겠다고 하지는 않았는가.'),
        ('정하지 않고 되물은 것', '물음이 몇 가지인지 세어 둔다. 열 가지가 넘어도 이상하지 않다. 다음 단계에서 이 물음에 내가 답한다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 여섯 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 이 줄이 없었다면 AI는 가장 흔한 방식으로 알아서 정했을 것이고, 무엇이 어떻게 정해졌는지는 결과 파일을 뜯어보아야 알 수 있다.')
 + ifs(('파일이 생겨 버렸다면', '탐색기의 <code>결과</code> 폴더에 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.'),
       ('절 번호가 내 종이와 다르다면', '「다시 해 줘」라고 하지 않는다. 「24시간 이내로 한다는 HM-8.5의 SOP-COOL-11 2단계에 있어. 표에는 다른 절로 적혀 있어.」처럼 어디가 어떻게 다른지를 말한다. 내 종이가 틀렸을 수도 있으므로 원문을 다시 본다.')))
+ nxt(2, '2. 비워 둔 것을 내가 정하고, 계획부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '비워 둔 것을 내가 정하고,<br>계획부터 받는다',
 '추출에는 정답이 하나가 아닌 결정이 여럿 있다. 어디까지 뽑을지, 스키마가 받지 못하는 내용을 버릴지 남길지, 문장 하나로 근거를 댈 수 없는 관계를 만들지. 이것을 정하는 일이 이 실습의 핵심이고, <b>요청하는 사람이 정한다.</b> 기준은 하나다. 다음 실습에서 내가 원문과 나란히 놓고 검토할 수 있는 모양이어야 한다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '내 결정이 반영된 계획이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '일곱 가지마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 5번과 6번은 온라인에서 본 네 가지 오류 가운데 잘못된 관계 추론과 부정 조건 누락을 미리 막는 선택이다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abc'))
 + parts(('무엇을 왜 만드는가', '첫 문단. 무엇을 뽑는지와, 그것이 다음에 어디에 쓰이는지를 말했다. 「검토한 것만 그래프에 넣는다」는 한마디가 출처를 빠짐없이 붙여야 하는 까닭이 된다.'), ('일곱 가지 결정', '번호를 붙여 한 줄에 결정 하나씩 적었다. Copilot도 나도 빠뜨린 것을 번호로 짚을 수 있다.'), ('계획 먼저', '마지막 문단. 몇 건이 나올지를 미리 말하게 했다. 수를 알고 있어야 만든 뒤에 빠진 것이 있는지 알 수 있다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 세 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 「이렇게 만들겠다」와 「이것은 더 정해 달라」가 함께 온다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. 후보의 표(클래스, 이름, id, 등록됨, 단계와 조건의 수), 관계와 보류의 건수, 끝의 「더 정해 주셔야 하는 것」이 보이게. 새 id의 안과 다시 물어 온 항목에 테두리를 얹는다.')
 + find(('조치와 원인의 수가 원문과 맞는가', 'HM-8.5와 HM-8.7의 절차는 SOP-COOL-11부터 15까지 다섯이고, HM-8.4의 원인은 셋이다. 계획의 후보가 이보다 많다면 괄호 안의 풀이(벨트 슬립, 외기 고온)를 따로 세었는지 본다.'),
        ('등록됨이 true인 것이 있는가', '「팬 최대 운전」과 「쿨러 핀 오염」은 지난 시간의 그래프에 이미 있다. 새 id를 짓지 않고 <code>skill:fan-maximum-run</code>, <code>cause:cooler-fin-fouling</code>을 그대로 가리키는가. 새로 짓는 id는 한번 붙이면 바꾸지 않으므로 지금 읽어 둔다.'),
        ('다시 물어 온 것', '일곱 가지를 정해 주어도 빈자리가 더 나온다. 예: 5번 줄대로 하면 관계가 거의 남지 않는데 그래도 되는지, 조치의 이름은 제목 줄에만 있는데 그 줄을 인용해도 되는지. 다음 단계의 요청이 이 물음에 답한다.'))
 + note('계획부터 받는 까닭', '계획을 받지 않고 바로 만들게 했다면, 이 물음들은 묻히고 AI가 고른 답이 파일에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.')
 + ifs(('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('되묻는 것이 하나도 없다면', '그대로 다음 단계로 간다. 다만 계획에 내가 정하지 않은 대상이나 관계가 들어 있지 않은지는 읽어 본다.')))
+ nxt(3, '3. 후보 파일 하나만 만들고, 네 곳을 원문과 맞춘다', 1))

# ───────── 3단계
pages.append(hero('3단계', '후보 파일 하나만 만들고,<br>네 곳을 원문과 맞춘다',
 '이제 만들게 한다. 범위는 <code>결과/후보.json</code> 한 파일까지다. 만든 뒤에는 AI에게 맞는지 묻지 않고 내가 원문 옆에 놓고 읽는다. 다 읽을 수는 없으므로 읽을 곳을 정한다. 추출이 틀리는 방식이 넷이므로 <b>읽을 곳도 넷</b>이다. 부정 조건, 수치와 단위, 단계의 순서, 대상과 관계.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '결과 폴더에 후보.json이 있고, 네 곳을 내 눈으로 맞춰 보았다'), ('아직 없어야 하는 것', '프로그램')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 범위를 정해 준다',
 '<p>계획이 다시 물어 온 것 가운데 결과의 모양을 바꾸는 넷은 아래 글에 미리 정해 적어 두었다. 내 계획이 묻지 않은 줄이 섞여 있어도 그대로 보내면 된다. 파일 하나를 통째로 쓰므로 2분쯤 걸린다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'ab'))
 + parts(('받을 것과 내가 정한 넷', '나머지는 Copilot이 권한 쪽을 받는다. 넷 가운데 둘째 줄을 눈여겨본다. 원인을 고장 유형에 잇는 관계는 절의 제목이 근거가 되어 만들지만, 조치를 고장 유형에 잇는 관계는 그런 문장이 없어 보류한다. 까닭을 함께 적었다.'), ('범위', '파일 하나를 만들고 수만 알려 달라고 했다. 어디까지인지를 적지 않으면 AI는 검사하는 프로그램까지 스스로 만들기 시작한다. 그것은 다음 단계에서 내가 시킨다.')))
+ do(2, 'editor', 'VS Code · 편집기', '<code>결과/후보.json</code>을 열어 모양을 읽는다',
 f'<p>맨 위의 칸은 넷이다. <code>문서</code>, <code>후보</code>, <code>관계</code>, <code>보류</code>. 칸의 이름은 규칙 파일이 정해 둔 것이어서 누가 만들어도 같다. 완성 폴더의 파일에는 후보 {len(D["후보"])}건, 관계 {len(D["관계"])}건, 보류 {len(D["보류"])}건이 들어 있다. 아래는 그 후보의 목록이다. 내 것은 번호와 id가 다를 수 있다.</p>' + ctable
 + '<p style="margin-top:18px">후보 한 건을 펼치면 아래와 같다. 완성 폴더의 K-004에서 단계 하나를 옮긴 것이다. 노랗게 보이는 세 칸이 오늘의 핵심이다.</p>'
 + jtree(step2, ['"문서"', '"구간"', '"인용"'])
 + '<ul class="ask"><li><b>내용과 인용</b><code>내용</code>은 지식으로 쓸 글이고 <code>인용</code>은 원문의 줄을 번호까지 그대로 옮긴 것이다. 둘이 따로 있어야 나란히 놓고 견줄 수 있다.</li><li><b>수치</b>문장 속의 수와 단위를 따로 꺼내 둔 것이다. 「24시간」이 「24분」으로 옮겨져도 글자만 보아서는 눈에 띄지 않는다.</li><li><b>검토</b>후보마다 <code>"검토": "대기"</code>가 붙어 있다. AI는 승인하지 않는다.</li></ul>')
+ do(3, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '네 곳을 원문과 나란히 읽는다',
 '<p><code>문서/HM-8_cooler-fan-manual.md</code>를 오른쪽으로 끌어 <code>후보.json</code>과 나란히 둔다. 아래 네 곳을 찾기(Ctrl+F)로 찾아 양쪽을 견준다. 표의 값은 완성 폴더의 것이다.</p>'
 + shot('결과/후보.json과 문서/HM-8_cooler-fan-manual.md를 좌우로 나란히 연 VS Code 화면. 왼쪽은 K-004의 조건, 오른쪽은 HM-8.8이 보이게.')
 + '<div class="cite"><div class="src"><small>원문 · HM-8 · 구간 HM-8.8</small>' + e(cond1['출처']['인용']).replace('아닐 때', '<mark>아닐 때</mark>').replace('않는다', '<mark>않는다</mark>') + '</div><span>←</span><div><small>후보.json · K-004의 조건</small><dl><dt>구분</dt><dd>' + e(cond1['구분']) + '</dd><dt>내용</dt><dd>' + e(cond1['내용']).replace('아닐 때', '<mark>아닐 때</mark>').replace('않는다', '<mark>않는다</mark>') + '</dd></dl></div></div>'
 + find(('부정 조건 — 「아닐 때」「않는다」가 살아 있는가', '세 조치(K-004 · K-005 · K-006)의 조건을 본다. <code>내용</code>에서 「아닐 때」가 빠졌다면 금지의 뜻이 반대가 된다. <code>구분</code>이 <code>금지</code>인지도 본다.'),
        ('수치와 단위 — 숫자와 단위가 인용과 같은가', f'K-004의 2단계를 본다. <code>수치</code>가 {e(json.dumps(step2["수치"], ensure_ascii=False))}인가. 같은 줄에 100 %가 두 번 나와도 한 번만 적혔는가.'),
        ('단계의 순서 — 번호와 순서가 원문과 같은가', f'K-006(부하 70 %와 야간 핀 세척)의 단계가 {len(C["K-006"]["단계"])}개이고, <code>순서</code>가 원문 SOP-COOL-13의 번호와 같은가. 원문에 없는 단계가 끼어 있지 않은가.'),
        ('대상과 관계 — 바르게 이어졌는가', f'<code>관계</code>에서 {rel["번호"]}를 본다. <code>{rel["a"]}</code>에서 <code>{rel["b"]}</code>로 가는 {rel["type"]}이고, 끝의 id는 <code>지난_시간/graph.json</code>에 있는 것이다. 조치를 고장 유형에 잇는 MITIGATED_BY는 관계에 없고 보류에 {n_mit}건으로 남아 있다.'))
 + note('보류가 후보보다 많다', f'완성 폴더의 보류 {len(D["보류"])}건은 구간별로 ' + ', '.join(f'{k} {v}건' for k, v in sorted(hold_by.items())) + '이다. 사전 확률, 판정 기준, 승인하는 사람, 회복 판정처럼 지난 시간의 스키마가 받지 못한 내용이다. 버리지 않았으므로, 스키마를 넓힐 때 무엇부터 받을지의 근거가 된다.')
 + ifs(('칸의 이름이나 모양이 다르다면', '<code>출처</code>가 목록으로 되어 있거나 칸 이름이 영어라면 「출처는 객체 하나로, 칸 이름은 규칙 파일의 것 그대로」라고 말한다. 뒤의 대조 프로그램이 이 모양을 읽는다.'),
       ('원문과 다른 곳을 찾았다면', '잘 찾은 것이다. 어느 번호의 어느 칸이 원문의 어느 줄과 어떻게 다른지를 말해 그곳만 고치게 한다. 「전체를 다시 뽑아 줘」라고 하면 이미 맞춰 본 곳까지 바뀐다.')))
+ nxt(4, '4. 출처를 원문에 대어 보는 프로그램을 만든다', 2))

# ───────── 4단계
pages.append(hero('4단계', '출처를 원문에 대어 보는<br>프로그램을 만든다',
 f'방금 네 곳을 읽었다. 그런데 완성 폴더의 후보 파일에는 출처가 {n_src}개 붙어 있다. 인용이 원문의 그 절에 글자 그대로 있는지를 {n_src}번 눈으로 찾을 수는 없다. 글자를 찾는 일은 프로그램이 사람보다 잘한다. <b>프로그램이 가릴 수 있는 것은 프로그램에게 맡기고</b>, 사람은 프로그램이 가리지 못하는 것을 읽는다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '대조.py와 결과/대조_결과.md가 있다'), ('바뀌면 안 되는 것', '후보.json, 문서 폴더')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '무엇을 검사할지 정해 주고, 한 번 돌리게 한다',
 '<p>규칙 파일은 「인용이 그 구간에 있는지」만 반드시 검사하라고 하고, 무엇을 더 볼지는 비워 두었다. 아래 글은 그것을 넷으로 정한 것이다.</p>'
 + copy(P4, pre=True, rich=richpre(P4, 'abc'))
 + parts(('왜 만드는가', '첫 문단. 프로그램의 쓰임새를 말했다. 사람이 읽기 전에 먼저 거르는 도구이지, 사람 대신 승인하는 도구가 아니다.'), ('검사 넷', '1은 인용, 2는 수치, 3과 4는 지난 시간의 스키마와 그래프에 맞는지다. 1번 줄의 「공백만 달라도 어긋난 것」은 내가 정한 엄격함이다. 느슨하게 하려면 이 줄을 고친다.'), ('어디까지', '파일 하나, 실행 한 번. 어긋난 것이 나와도 후보를 고치지 말라고 했다. 어느 쪽이 틀렸는지는 내가 보고 정한다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 무엇을 하려는지 읽고 허용한다',
 '<p>Copilot이 파일을 만들 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 두 가지를 읽는다. 만드는 파일이 <code>대조.py</code>인가. 실행하려는 명령이 <code>python 대조.py</code>(또는 <code>python3 대조.py</code>)인가. 다른 파일이나 다른 명령이면 허용하지 않고 왜 필요한지 묻는다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 대조.py)와 「허용/계속」 버튼이 보이게. 파일을 만들 때의 「유지/허용」 물음도 뜬다면 한 장 더.'))
+ do(3, 'editor', 'VS Code · 편집기', '<code>결과/대조_결과.md</code>를 열어 수를 맞춘다',
 f'<p>미리 보기(Ctrl+Shift+V)로 연다. 완성 폴더에서 이 단계의 결과는 「검사한 출처: {n_src}건, 어긋난 것: 0건」이었다.</p>'
 + find(('검사한 수가 맞는가', f'출처는 후보, 단계, 조건, 관계, 보류에 하나씩 붙는다. 완성 폴더에서는 {len(D["후보"])} + {n_step} + {n_cond} + {len(D["관계"])} + {len(D["보류"])} = {n_src}이다. 내 결과의 수가 내 후보 파일과 맞는지 Copilot의 답에서 본다. 보류의 출처를 빼고 세었다면 검사가 덜 된 것이다.'),
        ('어긋난 것이 있다면', '번호와 까닭을 읽고 원문에서 그 줄을 찾는다. 인용에 글자가 빠졌거나, 구간이 옆 절로 적혔거나, 따옴표나 빈칸이 달라진 경우가 많다. 어느 쪽이 틀렸는지를 내가 확인한 다음 그 항목만 고치게 한다.'),
        ('프로그램에 원문이 옮겨 적혀 있지 않은가', '<code>대조.py</code>를 열고 찾기(Ctrl+F)로 <code>HM-8</code>과 <code>REMOTE_AUTO</code>를 찾는다. 나오지 않아야 한다. 문서의 이름이나 인용문이 프로그램 안에 적혀 있으면 문서가 바뀌는 날부터 쓸 수 없다.'))
 + '<div class="vs"><div class="good"><b>프로그램이 가리는 것</b><ul><li>인용이 원문의 그 절에 글자 그대로 있는가</li><li>수치의 값과 단위가 인용 안에 있는가</li><li>클래스와 관계 이름이 스키마에 있는가</li><li>등록된 대상의 id가 그래프에 있는가</li></ul></div><div class="bad"><b>프로그램이 가리지 못하는 것</b><ul><li>내용의 뜻이 인용과 같은가</li><li>그 인용이 그 관계의 근거가 되는가</li><li>조건이 맞는 조치에 붙었는가</li><li>원문에 있는데 뽑히지 않은 것은 없는가</li></ul></div></div>'
 + ifs(('python을 찾을 수 없다고 나오면', '「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다. 프로그램을 다른 언어로 바꾸게 하지 않는다.'),
       ('후보.json이 바뀌었다면', '어긋난 것을 프로그램이나 Copilot이 스스로 고친 것이다. 무엇을 바꿨는지 묻고 되돌리게 한다. 대조하는 쪽이 대조받는 쪽을 고치면 검사의 뜻이 없다.')))
+ nxt(5, '5. 일부러 틀리게 고쳐, 무엇이 잡히는지 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '일부러 틀리게 고쳐,<br>무엇이 잡히는지 본다',
 '어긋난 것이 0건이라는 결과는 두 가지로 읽힌다. 정말 틀린 곳이 없거나, 프로그램이 틀린 곳을 보지 못하거나. 어느 쪽인지는 틀린 것을 넣어 보아야 안다. 온라인에서 본 오류 둘을 <b>내 손으로</b> 만든다. 단위가 바뀐 수치와, 부정이 빠진 조건이다. 돌리기 전에 어느 것이 잡힐지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '프로그램이 잡는 오류와 놓치는 오류를 보았고, 후보는 원래대로 돌아와 있다'), ('바뀌면 안 되는 것', '대조.py')])
+ do(1, 'editor', 'VS Code · 편집기', '<code>후보.json</code>의 두 곳을 직접 고쳐 저장한다',
 '<p><code>결과/후보.json</code>에서 찾기(Ctrl+F)로 <code>24시간 이내</code>를 찾는다. 「팬 최대 운전」의 2단계에 두 번 나온다. 그 가운데 <code>인용</code> 칸의 것만 고친다.</p>'
 '<div class="chg"><div class="tree">고치기 전 (2단계의 인용)\n…100 % 연속 운전은 <b>24시간</b> 이내로 한다.</div><div class="tree">고친 뒤\n…100 % 연속 운전은 <b>24분</b> 이내로 한다.</div></div>'
 '<p>다음으로 <code>아닐 때</code>를 찾는다. 세 조치의 조건에 나온다. 첫 번째 조치(팬 최대 운전)의 <code>내용</code> 칸만 고치고, 바로 아래의 <code>인용</code>은 그대로 둔다. 저장한다(Ctrl+S).</p>'
 '<div class="chg"><div class="tree">고치기 전 (조건의 내용)\n원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO<b>가 아닐 때</b> 쓰지 않는다.</div><div class="tree">고친 뒤\n원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO<b>일 때</b> 쓰지 않는다.</div></div>'
 '<p>첫째는 단위가 틀리게 옮겨진 인용이고, 둘째는 금지의 뜻이 반대로 뒤집힌 조건이다. 둘째가 그래프에 들어가면 원격 조치를 써도 되는 때에는 못 쓰고, 쓰면 안 되는 때에는 쓰게 된다.</p>')
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '프로그램은 그대로 두고 다시 실행하게 한다',
 '<p>어디를 고쳤는지는 말하지 않는다. 프로그램이 스스로 찾는지를 보려는 것이다.</p>' + copy(P5)
 + '<p style="margin-top:18px"><code>결과/대조_결과.md</code>를 다시 연다. 아래는 같은 두 곳을 고쳤을 때 실제로 나온 「어긋난 것」이다.</p>' + badtable
 + find(('단위 하나가 두 검사에 걸렸다', '고친 인용이 원문 HM-8.5에 없어 인용 검사에 걸렸고, 수치의 「24 시간」이 고친 인용 안에 없어 수치 검사에도 걸렸다. 글자 하나가 달라도 잡힌다.'),
        ('뜻이 뒤집힌 조건은 표에 없다', '어긋난 것은 두 줄뿐이고 둘 다 2단계의 것이다. 「아닐 때」를 지운 조건은 통과했다. 인용이 원문 그대로이기 때문이다. 프로그램은 <code>내용</code>이 <code>인용</code>과 같은 뜻인지를 보지 않는다.'),
        ('Copilot은 무엇이라고 답했는가', '표에 없는 둘째 곳을 Copilot이 답에서 따로 짚었는지 본다. 짚었다면 프로그램이 아니라 Copilot이 파일을 읽고 찾은 것이다. 읽는 일은 늘 일어나지 않고, 대조 결과 파일에는 남지 않는다.')))
+ do(3, 'editor', 'VS Code · 편집기 → Copilot 채팅', '두 곳을 원래대로 되돌리고 한 번 더 실행한다',
 '<p>편집기에서 실행 취소(Ctrl+Z)를 두 번 눌러 <code>24시간</code>과 <code>가 아닐 때</code>로 되돌리고 저장한다. 그다음 아래를 보낸다. 어긋난 것이 다시 0건인지 본다.</p>' + copy(P5b)
 + note('0건의 뜻', '「어긋난 것 0건」은 「틀린 곳이 없다」가 아니라 「프로그램이 볼 수 있는 곳에는 틀린 것이 없다」이다. 인용이 원문에 있는지는 프로그램이 대조하고, 조건과 수치와 순서와 연결이 맞는지는 사람이 검토한다. 그러면 사람은 어디를 읽어야 하는가. 7단계에서 이 물음을 프로그램에 되돌려 준다.')
 + ifs(('두 곳 다 잡히지 않았다면', '파일을 저장하지 않았거나 <code>인용</code>이 아니라 <code>내용</code>의 24시간을 고친 것이다. 편집기 탭의 이름 옆에 동그란 점이 남아 있으면 저장되지 않은 것이다.'),
       ('오류가 나며 멈췄다면', '따옴표나 쉼표를 함께 지운 것이다. 실행 취소로 되돌린 다음 글자만 다시 고친다.')))
+ nxt(6, '6. 규칙을 일부러 건드려 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 문서를 다루는 일터에서는 「현장은 다르게 한다」는 말이 늘 나온다. 그 말을 근거로 원문을 고치거나 원문에 없는 단계를 넣어 달라고 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '문서 폴더, 후보.json')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '원문의 값을 고쳐 달라고 해 본다',
 '<p>현장의 말을 근거로 댄 그럴듯한 요청이다.</p>'
 + copy(P6a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 문서를 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('원문이 그대로인가', '편집기에서 <code>문서/HM-8_cooler-fan-manual.md</code>를 열어 SOP-COOL-11의 2단계가 「24시간 이내」 그대로인지 본다. <code>후보.json</code>의 2단계도 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다. 요청 하나에 원문을 고치는 일과 후보를 원문과 다르게 적는 일이 함께 들어 있었다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고, 규칙 안에서 같은 목적을 이루는 길(예: 문서를 관리하는 쪽에서 개정한 판을 넣어 주면 그 원문에서 다시 뽑는다)을 내놓았는가.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '원문에 없는 단계를 넣어 달라고 해 본다',
 '<p>이번에는 후보 쪽을 건드린다. 다들 하는 일이라는 말은 틀린 말이 아닐 수 있다. 문제는 그 단계에 붙일 원문이 없다는 것이다.</p>'
 + copy(P6b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + f'<p style="margin-top:18px">답이 오면 <code>후보.json</code>에서 「쿨러 핀 세척」의 단계가 {len(C["K-007"]["단계"])}개 그대로인지 본다. 내 파일에서 그 후보의 번호가 K-007이 아니면 요청의 번호를 내 번호로 바꿔 보낸다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 한 줄이다. 문서 폴더를 어떻게 다루라고 적혀 있는가. 원문에 낡은 값이 보이면 어떻게 하라고 했는가. 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 한 줄이다. 「현장에서 늘 하는 일이라고 들은 내용」을 어떻게 하라고 적혀 있는가. 몇 번인가.</li><li><b>두 답에 함께 나온 줄</b>「채팅에서 요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('원문을 지키는 까닭', '대조는 보관된 원문을 기준으로 한다. 원문을 고칠 수 있다면 후보에 맞춰 원문을 바꾸는 것으로 어긋난 것 0건을 만들 수 있고, 그때부터 대조는 아무것도 가리지 못한다. 둘째 요청을 들어주었다면 원문에 없는 단계가 출처를 단 채 후보에 섞였을 것이다. 온라인에서 본 근거 없는 내용 생성이 바로 이것이다. 현장의 말이 옳다면 고칠 곳은 후보가 아니라 문서이고, 그것은 문서를 관리하는 사람의 일이다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '문서가 바뀌었다면 완성 폴더의 <code>문서</code>에서 같은 파일을 가져와 덮어쓴다. <code>후보.json</code>이 바뀌었다면 방금 고친 것을 되돌려 달라고 말한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(7, '7. 아쉬운 곳을 찾아 되돌려 준다', 5))

# ───────── 7단계
pages.append(hero('7단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '대조 프로그램은 시킨 대로 만들어졌다. 그런데 5단계에서 보았듯 뜻이 뒤집힌 조건은 통과하고, 결과 파일은 「어긋난 것 0건」 한 줄뿐이다. 다음 실습에서 이 파일을 들고 검토할 사람은 어디부터 읽어야 할지 알 수 없다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '대조.py의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>대조 결과가 좀 부족해. 더 잘 나오게 해 줘.</q>무엇이 부족한지 AI는 모른다. 짐작으로 검사를 여럿 더하거나, 무엇이 부족한지를 되묻는다. 어느 쪽이든 한 번 더 주고받아야 하고, 정작 내가 아쉬웠던 것은 그대로일 수 있다.</div>'
  '<div class="good"><b>구체적으로</b><q>「어긋난 것 0건」이라고만 나와서, 조건의 내용에서 「가 아닐」을 지웠을 때도 통과했어. 어디를 읽어야 하는지 알 수 없어. 결과 md 의 끝에 부정이나 한계의 말이 든 단계와 조건을 「사람이 읽을 곳」으로 모아 줘. 결과 md 를 쓰는 부분만 고치고, 네 가지 검사와 후보.json 은 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>0건이라고만 나오고 읽을 곳이 보이지 않는다</div><div><b>왜</b>뜻이 뒤집힌 조건이 통과해도 알 수 없다</div><div><b>어디를</b>대조.py에서 결과 md를 쓰는 부분</div><div><b>어디까지</b>네 가지 검사, 어긋난 것의 수, 후보.json은 그대로</div></div>'
  + note('4단계의 요청을 다시 본다', '프로그램을 만들 때 보낸 글에도 이 네 가지가 들어 있었다. 프로그램으로 가릴 수 있는 것은 먼저 거른다(무엇을 · 왜), 대조.py 한 파일(어디를), 후보.json은 고치지 마(어디까지).') + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 대조 결과에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/대조_결과.md</code>와 <code>결과/후보.json</code>을 다시 본다. 이 두 파일을 받아 후보를 하나씩 승인할 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>사람이 읽을 곳이 보이는가</b>부정(「아닐」「않는다」)이나 한계(「미만」「이상」「이내」)의 말이 든 항목이 어디인지, 내용과 인용이 나란히 보이는가.</li><li><b>내용이 인용과 글자가 다른 항목을 알 수 있는가</b>단계와 조건의 <code>내용</code>이 <code>인용</code> 안에 그대로 들어 있지 않은 항목은 누군가 고쳐 쓴 것이다. 그런 항목이 어디인지 보이는가.</li><li><b>보류가 한눈에 보이는가</b>보류가 까닭별로 몇 건인지, 스키마에 무엇이 없어서 남았는지를 표로 볼 수 있는가.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 「후보.json은 건드리지 마」를 꼭 넣는다.</p>'
 + write('w7', '무엇이 문제인지, 왜 문제인지, 대조.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(사람이 읽을 곳)를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P7, pre=True) + '</details>'
 f'<p style="margin-top:18px">고친 뒤에는 <code>결과/대조_결과.md</code>를 다시 연다. 완성 폴더의 결과에는 끝에 「사람이 읽을 곳」이 생겼고, 단계와 조건 {n_step + n_cond}개 가운데 {len(read)}개가 모였다. 아래는 그 가운데 네 줄이다. 5단계에서 내가 뒤집었던 조건이 둘째 줄에 있다.</p>' + readtable
 + shot('되돌려 준 뒤 Copilot이 대조.py의 바뀐 부분을 보여 주는 화면(새로 생긴 줄이 초록색으로 표시되고, 네 가지 검사는 바뀌지 않은 것이 보이게).')
 + find(('검사와 수는 그대로인가', f'맨 위의 「검사한 출처」와 「어긋난 것」의 수가 4단계와 같은가(완성 폴더는 {n_src}건, 0건).'),
        ('빠진 줄은 없는가', '낱말 목록에 없는 말로 적힌 한계는 표에 들지 않는다. 「35 ℃ 아래로 내려왔는지」의 「아래」가 그렇다. Copilot이 답에서 이런 줄을 짚었는지 보고, 프로그램 맨 위의 낱말 목록에 내 손으로 더해 다시 실행해 본다.'))
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 되묻지 않고 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>문서를 하나 더 읽게 한다.</b> 같은 규칙과 같은 대조 프로그램이 다른 문서에도 통하는지 본다. 아래를 보내면 Copilot은 바로 더하지 않고 다시 묻는다. 새 문서에는 새로 정할 것이 있기 때문이다(품번이 없는 부품을 후보로 만들지, 절의 머리글에 적힌 금지를 어느 조치에 붙일지). 답해 주고, 더한 뒤에 대조 결과의 수가 어떻게 늘었는지 본다.</p>'
  + copy(PXa)
  + f'<p style="margin-top:18px">같은 요청을 보내고 물음에 답해 만들어 본 결과는 후보 {len(X["후보"])}건, 관계 {len(X["관계"])}건, 보류 {len(X["보류"])}건이고 검사한 출처는 {xs}건이었다. 이미 붙인 K-001~K-008의 번호와 id는 그대로였다. 완성 폴더에는 HM-8까지만 들어 있다.</p>'
  '<p><b>승인을 대신 해 달라고 해 본다.</b> 6단계에서 건드리지 않은 줄이 하나 더 있다. 아래를 보내고, <code>검토</code> 칸이 <code>대기</code> 그대로인지, Copilot이 규칙 파일의 어느 줄을 들었는지 본다. 5단계에서 본 것을 Copilot이 근거로 드는지도 본다.</p>'
  + copy(PXb, 'Copilot에게 보낼 요청 (규칙에 어긋난다)') + '</section>'
+ nxt(None, None, 6))

names = ['준비', '1. 읽고 가르게 한다', '2. 정하고 계획 받기', '3. 후보를 만들어 원문과 맞추기', '4. 대조 프로그램 만들기', '5. 일부러 틀리게 고쳐 보기', '6. 규칙을 건드려 보기', '7. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>문서 → 지식 후보</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-04-2-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 7단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 기술 문서에서 출처가 붙은 지식 후보 뽑기</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
