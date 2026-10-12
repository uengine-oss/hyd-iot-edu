"""통합반 오프라인 02회차 실습 2 「설계한 지식을 그래프 DB에 구현하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
가이드_만들기_통합반오프02_실습1.py 의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다.
시작/지난_시간/ 은 02회차 실습 1의 완성본이다. 가이드의 표 · 그림 · 결과 상자의 값은 시작/ · 기록/ · 완성/ 의 파일에서 읽어 옮긴다.
실행: python3 lab/도구/가이드_만들기_통합반_오프라인_02회차_실습2.py
"""
import re, html, json, os
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R=LAB+'/통합반_오프라인/02회차_실습2_그래프DB_구현/'
css=re.search(r'<style>(.*?)</style>',open(LAB+'/도구/디자인_샘플.html',encoding='utf-8').read(),re.S).group(1)
css+='''
.step{display:none}.step.on{display:block}
.track i{cursor:pointer}
.hero h1 small{display:block;font-size:15px;font-weight:700;color:var(--sub);letter-spacing:0;margin-bottom:6px}
.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:8px 0 0}
.flow div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 14px;font-size:14.5px;line-height:1.55;position:relative}
.flow b{display:block;font-size:15.5px;margin-bottom:4px}
.flow em{font-style:normal;display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--accent);color:#fff;font-weight:800;font-size:13px;margin-bottom:8px}
.sect{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px;margin-bottom:72px}
.sect h2{font-size:20px;margin:0 0 10px}
.sect p{margin:0 0 12px;font-size:16px;color:#333b47}
.tree{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.9;background:#14181f;color:#e8edf5;border-radius:14px;padding:18px 22px;white-space:pre;overflow:auto}
.tree span{color:#8fb4ff}.tree i{color:#8a94a3;font-style:normal}
table.res{width:100%;border-collapse:collapse;font-size:14.5px;line-height:1.6;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid var(--line);margin:18px 0 8px}
table.res th{background:#eef1f5;text-align:left;padding:10px 14px;font-size:13px;white-space:nowrap}
table.res td{padding:10px 14px;border-top:1px solid var(--line);vertical-align:top}
table.res mark{background:#fff1a8;padding:0 3px;border-radius:3px}
table.res code{font-size:13.5px}
table.res td:first-child{white-space:nowrap}
.ask{list-style:none;padding:0;margin:18px 0;display:grid;gap:10px}
.ask li{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ok);border-radius:0 12px 12px 0;padding:12px 18px;font-size:15.5px}
.ask b{display:block}
textarea{width:100%;min-height:200px;border:2px dashed #9bc3ac;border-radius:16px;padding:18px 20px;font:16px/1.8 inherit;font-family:inherit;background:#f7fcf9;resize:vertical;color:var(--ink)}
.wfoot{display:flex;gap:12px;align-items:center;margin:10px 0 0;font-size:14px;color:var(--sub)}
.wfoot button{border:0;background:var(--ok);color:#fff;border-radius:10px;padding:10px 20px;font-weight:700}
details{margin:18px 0 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 20px}
summary{cursor:pointer;font-weight:700;color:var(--accent)}
details .copy{box-shadow:none}
.copy-text.pre{white-space:pre-wrap;font-size:16px;line-height:1.8}
.copy.db{border-color:#0b7285;box-shadow:0 8px 24px rgba(11,114,133,.08)}
.copy.db .copy-top{background:#e3f6f9;color:#0b7285}.copy.db .copy-top button{background:#0b7285}
.copy.db .copy-foot{border-top-color:#c5e8ee;color:#0b7285}
.copy.db .copy-text{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.75;white-space:pre-wrap;word-break:break-all}
.w-db{background:#e3f6f9;color:#0b7285}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:20px 0}
.vs div{border-radius:16px;padding:20px 22px;font-size:15.5px;line-height:1.7}
.vs .bad{background:#fdecec}.vs .good{background:var(--ok-soft)}
.vs b{display:block;margin-bottom:6px}.vs .bad b{color:#b3261e}.vs .good b{color:var(--ok)}
.vs q{display:block;quotes:none;background:#fff;border-radius:10px;padding:10px 14px;margin:8px 0;font-size:15px}
.four{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}
.four div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-size:14.5px}
.four b{display:block;color:var(--accent);font-size:15.5px}
.next a,.back{cursor:pointer}
.fig{margin:18px 0 6px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px}
.fig svg{display:block;width:100%;height:auto}
.fig p{margin:10px 4px 0;font-size:14px;color:var(--sub)}
.csv{font-family:Consolas,"D2Coding",monospace;font-size:13.5px;line-height:1.85;background:#14181f;color:#e8edf5;border-radius:14px;padding:16px 20px;white-space:pre-wrap;word-break:break-all;overflow:auto;margin:14px 0}
.csv mark{background:#5a4a00;color:#ffe680;padding:0 2px;border-radius:3px}
.csv i{color:#8a94a3;font-style:normal}
.csv.err{background:#3a1512;color:#ffd9d4}
.cap{font-size:13.5px;color:var(--sub);margin:-6px 4px 14px}
@media(max-width:760px){.flow,.vs,.four{grid-template-columns:1fr}}
'''
e=html.escape
def vs(hl):
    c=lambda k,on,off: on if hl==k else off
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
BROWSER='''<svg viewBox="0 0 520 320" role="img" aria-label="Neo4j Browser 화면 지도">
<rect x="1" y="1" width="518" height="318" rx="14" fill="#fff" stroke="#cfd6e0" stroke-width="2"/><rect x="1" y="1" width="518" height="30" rx="14" fill="#eef1f5"/><rect x="1" y="18" width="518" height="14" fill="#eef1f5"/>
<circle cx="20" cy="16" r="5" fill="#f26b5e"/><circle cx="37" cy="16" r="5" fill="#f5c04f"/><circle cx="54" cy="16" r="5" fill="#5bc467"/><rect x="80" y="8" width="200" height="16" rx="8" fill="#fff"/><text x="92" y="20" font-size="10" fill="#5b6573">localhost:7474</text>
<rect x="1" y="32" width="38" height="287" fill="#e4e8ee"/><rect x="11" y="46" width="18" height="18" rx="4" fill="#aab4c3"/><rect x="11" y="76" width="18" height="18" rx="4" fill="#c7ceda"/>
<rect x="52" y="44" width="454" height="44" rx="8" fill="#e3f6f9" stroke="#0b7285" stroke-width="3"/><text x="64" y="62" font-size="11" font-weight="800" fill="#0b7285">입력 칸</text><text x="64" y="78" font-size="11" fill="#333b47" font-family="Consolas,monospace">neo4j$ MATCH (n) RETURN count(n)</text>
<circle cx="484" cy="66" r="12" fill="#0b7285"/><path d="M480 60L490 66L480 72z" fill="#fff"/>
<rect x="52" y="100" width="454" height="100" rx="8" fill="#f6f8fa" stroke="#cfd6e0"/><text x="64" y="118" font-size="11" font-weight="800" fill="#5b6573">방금 실행한 것의 결과</text>
<rect x="64" y="128" width="30" height="60" rx="4" fill="#e4e8ee"/><rect x="104" y="130" width="380" height="10" rx="5" fill="#dfe4ec"/><rect x="104" y="150" width="300" height="10" rx="5" fill="#dfe4ec"/><rect x="104" y="170" width="340" height="10" rx="5" fill="#dfe4ec"/>
<rect x="52" y="212" width="454" height="96" rx="8" fill="#f6f8fa" stroke="#cfd6e0"/><text x="64" y="230" font-size="11" font-weight="800" fill="#5b6573">그 앞에 실행한 것의 결과</text><rect x="104" y="244" width="330" height="10" rx="5" fill="#dfe4ec"/><rect x="104" y="264" width="260" height="10" rx="5" fill="#dfe4ec"/></svg>'''
ICO={'chat':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#6a3fd1"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6a3fd1"/></svg>',
'explorer':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#2f5bea"/></svg>',
'editor':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="12" y="3" width="9" height="16" rx="2" fill="#2f5bea"/></svg>',
'db':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#0b7285"/><rect x="4" y="4" width="26" height="5" rx="2" fill="#0b7285"/></svg>'}
def where(k,label): return f'<span class="where {"w-chat" if k=="chat" else "w-db" if k=="db" else "w-code"}">{ICO[k]}{label}</span>'
cid=[0]
def copy(text,head='Copilot에게 보낼 요청',pre=False,rich=None):
    cid[0]+=1; i=f'c{cid[0]}'
    body=rich if rich else e(text)
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}" id="{i}">{body}</div><div class="copy-foot">붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸</div></div>'
def cy(text,head='Neo4j Browser에서 실행할 문장'):
    cid[0]+=1; i=f'c{cid[0]}'
    return f'<div class="copy db"><div class="copy-top"><span>{head}</span><button data-copy="{i}" data-to="db">복사</button></div><div class="copy-text" id="{i}">{e(text.strip())}</div><div class="copy-foot">붙여넣는 곳 → Neo4j Browser 맨 위 입력 칸. 붙여넣은 다음 입력 칸 오른쪽의 실행 단추(▶)를 누른다</div></div>'
shots=[]
def shot(desc):
    shots.append(desc); n=len(shots)
    return f'<div class="shot"><div><b>사진 {n} — 찍어 주실 화면</b><span>{desc}</span></div></div>'
def write(i,ph): return f'<textarea id="{i}" data-draft="{i}" placeholder="{e(ph)}"></textarea><div class="wfoot"><button data-copy="{i}">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸 · 쓴 글은 이 브라우저에 저장된다</span></div>'
def do(n,k,label,title,body): return f'<section class="do" data-n="{n}">{where(k,label)}<h2>{title}</h2>{body}</section>'
def hero(no,title,lead,facts): return f'<section class="hero"><div class="no">{no}</div><h1>{title}</h1><p>{lead}</p><div class="facts">'+''.join(f'<div><small>{a}</small>{b}</div>' for a,b in facts)+'</div></section>'
def mapbox(svg,title,text): return f'<section class="map"><div>{svg}</div><div><h2>{title}</h2>{text}</div></section>'
def nxt(i,label,prev=None):
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 결과 폴더의 Cypher 파일 넷과, 그 파일로 채운 실습용 그래프 DB. 다음 실습에서 이 그래프에 새 설비의 인스턴스를 더한다</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
F=lambda p: open(R+p,encoding='utf-8').read()
J=lambda p: json.load(open(R+p,encoding='utf-8'))
out=lambda f,cls='': f'<div class="csv{" "+cls if cls else ""}">{e(P(f))}</div>'

# ── 시작/ · 기록/ · 완성/ 의 파일에서 옮기는 값 ──
S=J('시작/지난_시간/schema.json'); G=J('시작/지난_시간/graph.json')
assert S==J('완성/지난_시간/schema.json') and G==J('완성/지난_시간/graph.json')
RULE=F('시작/.github/copilot-instructions.md'); assert RULE==F('완성/.github/copilot-instructions.md')
C1,C2,C3,C4=(F(f'완성/결과/{n}.cypher') for n in ('01_제약','02_적재','03_조회','04_검사'))
NN,NR=len(G['nodes']),len(G['rels'])
cnt=lambda L: sum(1 for n in G['nodes'] if n['labels'][0]==L)
rc=lambda T: sum(1 for r in G['rels'] if r['type']==T)
node=lambda i: next(n for n in G['nodes'] if n['props']['id']==i)
jd=lambda v: e(json.dumps(v,ensure_ascii=False))
stmts=lambda c: [s for s in re.split(r';\s*\n',re.sub(r'(?m)^//.*\n?','',c)) if s.strip()]
assert len(stmts(C1))==len(S['classes'])==11 and len(stmts(C2))==NN+NR==89
assert C2.count('MERGE (n:')==NN and not re.search(r'(?m)^\s*(CREATE|DELETE|DETACH|REMOVE|DROP)\b',C2)
# 실행 결과의 수가 graph.json 과 같은지
cnt_run=P('4_실행_수.txt').split('\n')
assert cnt_run[1]==str(NN) and cnt_run[3]==str(NR)
for l in cnt_run:
    m=re.match(r'"(\w+)", (\d+)$',l)
    if m: assert int(m.group(2))==(cnt(m.group(1)) or rc(m.group(1))),l
assert P('8c_실행_다시_넣은_뒤_수.txt').split('\n')[:4]==cnt_run[:4]
assert P('5_실행_검사.txt')==P('7c_실행_검사_지운_뒤.txt') and len(P('5_실행_검사.txt').split('\n'))==1+len(S['classes'])+len(S['relationships'])
cons=P('3_실행_제약_목록.txt').split('\n')[1:]; assert len(cons)==11

count_table=('<table class="res"><thead><tr><th>클래스 (레이블)</th><th>노드</th><th>관계 유형</th><th>관계</th></tr></thead><tbody>'
 +''.join(f'<tr><td><code>{c["name"]}</code> {c["label_ko"]}</td><td>{cnt(c["name"])}</td><td><code>{r["type"]}</code></td><td>{rc(r["type"])}</td></tr>' for c,r in zip(S['classes'],S['relationships']))
 +f'<tr><td></td><td></td><td><code>{S["relationships"][11]["type"]}</code></td><td>{rc(S["relationships"][11]["type"])}</td></tr>'
 +f'<tr><td><b>합계</b></td><td><mark>{NN}</mark></td><td><b>합계</b></td><td><mark>{NR}</mark></td></tr></tbody></table>')
assert len(S['relationships'])==12

who_table=('<table class="res"><thead><tr><th>스키마가 정한 조건</th><th>이 그래프 DB가 넣는 순간에 막는가</th><th>그래서 오늘 하는 일</th></tr></thead><tbody>'
 '<tr><td>같은 <code>id</code>가 둘 있을 수 없다</td><td><mark>막는다</mark>. 유일 제약을 걸어 두면 된다</td><td>3단계에서 클래스마다 제약을 건다</td></tr>'
 '<tr><td>필수 속성이 있어야 한다</td><td>막지 않는다</td><td rowspan="4">5단계에서 검사 질의를 만들어, 넣은 뒤에 어긋난 것을 찾는다</td></tr>'
 '<tr><td>값이 자료형과 허용값에 맞아야 한다</td><td>막지 않는다</td></tr>'
 '<tr><td>관계의 양 끝이 정해진 클래스여야 한다</td><td>막지 않는다</td></tr>'
 '<tr><td>카디널리티</td><td>막지 않는다</td></tr></tbody></table>')

# 한 줄씩 맞춰 읽는 그림에 쓰는 줄
def gline(i): return next(l.strip().rstrip(',') for l in F('시작/지난_시간/graph.json').split('\n') if f'"id": "{i}"' in l)
def cline(s): return next(l for l in C2.split('\n') if s in l)
gl_node=gline('sen:ts1'); cl_node=cline("MERGE (n:Sensor {id: 'sen:ts1'})")
gl_rel=next(l.strip().rstrip(',') for l in F('시작/지난_시간/graph.json').split('\n') if '"a": "part:p-pmp-seal", "b": "sup:a"' in l)
cl_rel=cline("(a:Part {id: 'part:p-pmp-seal'}), (b:Supplier {id: 'sup:a'})")
read_fig=('<div class="csv"><i>// 지난_시간/graph.json 의 노드 한 줄</i>\n'+e(gl_node)+'\n<i>// 결과/02_적재.cypher 의 그 줄</i>\n'
 +e(cl_node).replace("MERGE (n:Sensor {id: &#x27;sen:ts1&#x27;})","<mark>MERGE (n:Sensor {id: &#x27;sen:ts1&#x27;})</mark>")
 +'\n\n<i>// 지난_시간/graph.json 의 관계 한 줄</i>\n'+e(gl_rel)+'\n<i>// 결과/02_적재.cypher 의 그 줄</i>\n'
 +e(cl_rel).replace('MERGE (a)-[r:SUPPLIED_BY]-&gt;(b)','<mark>MERGE (a)-[r:SUPPLIED_BY]-&gt;(b)</mark>')+'</div>')
assert read_fig.count('<mark>')==2

def sp(part,sup): return next(r['props'] for r in G['rels'] if r['type']=='SUPPLIED_BY' and r['a']==part and r['b']==sup)
pa,pb,pc=(sp('part:p-pmp-seal','sup:'+x) for x in 'abc')
sa,sb,sc=(node('sup:'+x)['props'] for x in 'abc')
path_fig=f'''<div class="fig"><svg viewBox="0 0 760 190" role="img" aria-label="조회 2가 따라가는 길">
<defs><marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6573"/></marker></defs>
<g font-size="12.5" font-weight="700" text-anchor="middle">
<rect x="6" y="70" width="112" height="50" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="62" y="92" fill="#2f5bea">:Asset</text><text x="62" y="109" font-size="11" font-weight="400" fill="#333b47">code: HYD-02</text>
<rect x="212" y="70" width="136" height="50" rx="25" fill="#fff" stroke="#8a94a3"/><text x="280" y="92" fill="#333b47">:Component</text><text x="280" y="109" font-size="11" font-weight="400" fill="#333b47">aliases 에 유압 펌프</text>
<rect x="430" y="70" width="136" height="50" rx="25" fill="#fff" stroke="#8a94a3"/><text x="498" y="92" fill="#333b47">:Part</text><text x="498" y="109" font-size="11" font-weight="400" fill="#333b47">{e(node("part:p-pmp-seal")["props"]["name"])}</text>
<rect x="652" y="14" width="102" height="42" rx="8" fill="#e9f6ee" stroke="#1f8a4c"/><text x="703" y="32" fill="#1f8a4c">sup:a</text><text x="703" y="48" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sa["approved"])}</text>
<rect x="652" y="74" width="102" height="42" rx="8" fill="#fff" stroke="#8a94a3"/><text x="703" y="92" fill="#333b47">sup:b</text><text x="703" y="108" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sb["approved"])}</text>
<rect x="652" y="134" width="102" height="42" rx="8" fill="#fdecec" stroke="#b3261e"/><text x="703" y="152" fill="#b3261e">sup:c</text><text x="703" y="168" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sc["approved"])}</text>
<g font-size="10.5" font-weight="400" fill="#5b6573"><text x="165" y="88">HAS_COMPONENT</text><text x="389" y="88">USES_PART</text><text x="604" y="40">price {pa["price"]}</text><text x="612" y="88">price {pb["price"]}</text><text x="604" y="152">price {pc["price"]}</text></g></g>
<g stroke="#5b6573" stroke-width="1.6" marker-end="url(#ar2)"><line x1="118" y1="98" x2="210" y2="98"/><line x1="348" y1="98" x2="428" y2="98"/><line x1="566" y1="86" x2="650" y2="40"/><line x1="566" y1="98" x2="650" y2="96"/><line x1="566" y1="108" x2="650" y2="150"/></g>
</svg><p>둘째 물음의 길을 <code>graph.json</code>의 값으로 그린 것이다. 지난 시간에는 Copilot이 파일을 읽어 이 길을 따라갔다. 이제는 <code>MATCH</code>에 이 모양을 적으면 그래프 DB가 따라간다. 관계 셋을 이어 적은 것이 화살표 셋이고, <code>WHERE s.approved = true</code>가 빨간 상자를 뺀다.</p></div>'''

who_fig='''<div class="fig"><svg viewBox="0 0 760 200" role="img" aria-label="오늘 누가 무엇을 하는가">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6573"/></marker></defs>
<g font-size="13" font-weight="700" text-anchor="middle">
<rect x="10" y="30" width="150" height="80" rx="12" fill="#f6f8fa" stroke="#8a94a3"/><text x="85" y="58" fill="#333b47">지난_시간/</text><text x="85" y="78" font-size="12" font-weight="400" fill="#333b47">schema.json</text><text x="85" y="95" font-size="12" font-weight="400" fill="#333b47">graph.json</text>
<rect x="210" y="30" width="150" height="80" rx="12" fill="#f3eeff" stroke="#6a3fd1"/><text x="285" y="58" fill="#6a3fd1">Copilot</text><text x="285" y="78" font-size="12" font-weight="400" fill="#333b47">Cypher 파일을 쓴다</text><text x="285" y="95" font-size="12" font-weight="400" fill="#333b47">DB에는 닿지 않는다</text>
<rect x="410" y="30" width="150" height="80" rx="12" fill="#e9f6ee" stroke="#1f8a4c"/><text x="485" y="58" fill="#1f8a4c">나</text><text x="485" y="78" font-size="12" font-weight="400" fill="#333b47">파일을 읽고</text><text x="485" y="95" font-size="12" font-weight="400" fill="#333b47">Browser에 붙여넣는다</text>
<rect x="610" y="30" width="140" height="80" rx="12" fill="#e3f6f9" stroke="#0b7285"/><text x="680" y="58" fill="#0b7285">실습용 그래프 DB</text><text x="680" y="78" font-size="12" font-weight="400" fill="#333b47">문장을 실행하고</text><text x="680" y="95" font-size="12" font-weight="400" fill="#333b47">결과를 돌려준다</text>
<text x="485" y="176" font-size="12" font-weight="400" fill="#5b6573">실행한 결과(수, 오류 글, 나온 행)는 내가 Copilot에게 말로 알려 준다</text></g>
<g stroke="#5b6573" stroke-width="1.6" marker-end="url(#ar)" fill="none"><line x1="160" y1="70" x2="208" y2="70"/><line x1="360" y1="70" x2="408" y2="70"/><line x1="560" y1="70" x2="608" y2="70"/><path d="M680 110 C680 150 600 150 520 150 L330 150 C300 150 285 140 285 114"/></g>
</svg><p>Copilot은 그래프 DB에 접속하지 않는다. 규칙 파일이 그렇게 정해 두었다. 그래서 Copilot이 「이렇게 나올 것이다」라고 하는 말은 파일을 읽어 따져 본 것이고, 정말 그렇게 나오는지는 내가 실행해 보아야 안다.</p></div>'''

def rule_line(start): return next(x for x in RULE.split('\n') if x.startswith(start))
R4=rule_line('4. 그래프 DB에'); R5=rule_line('5. 노드와 관계를'); R9=rule_line('9. 위의 여덟')
assert '「이번만」이라는 예외도 두지 않는다' in R9 and 'DETACH DELETE' in R4 and 'CREATE' in R5

sent1=P('1_prompt.txt'); HEAD0='먼저 .github/copilot-instructions.md 를 읽고 그 규칙을 따라 줘. 그다음 지난_시간/schema.json 과 지난_시간/graph.json 을 읽어 줘. '
assert sent1.startswith(HEAD0)
HEAD='이 폴더의 규칙(.github/copilot-instructions.md)과 지난_시간/schema.json, 지난_시간/graph.json 을 읽어 줘.'
tail=sent1[len(HEAD0):]; a,b=tail.split(' 아직 파일은 만들지 마.'); assert b=='' and a.startswith('읽은 것을 세 가지로')
P1=HEAD+' '+tail
P1rich=f'<span class="p-a">{e(HEAD)}</span> <span class="p-b">{e(a)}</span> <span class="p-c">아직 파일은 만들지 마.</span>'
P2,P3,P4,P5,P7,P7b,P8a,P8b,P7x=(P(f+'_prompt.txt') for f in ('2','3','4','5','7','7b','8a','8b','7x'))
def hl(text,*marks):
    h=e(text)
    for s,c in marks:
        assert e(s) in h,s
        h=h.replace(e(s),f'<span class="{c}">{e(s)}</span>')
    return h
P2rich=hl(P2,('바로 만들지 말고, 파일 넷을 어떤 차례로 어떻게 만들지 계획부터 말해 줘. 내가 확인한 다음에 시작해.','p-c'))
P3rich=hl(P3,('지금은 결과/01_제약.cypher 한 파일만 만들고 멈춰.','p-c'))
P4rich=hl(P4,('01_제약.cypher 를 실행했어. SHOW CONSTRAINTS 로 보니 lab_ 로 시작하는 유일 제약이 11개 걸려 있어.','p-a'),('만든 다음 graph.json 과 다시 대조해서 문장의 수와, graph.json 과 다르게 적은 곳이 있으면 그곳을 알려 줘.','p-b'))
P5rich=hl(P5,('02_적재.cypher 를 실행했어. 오류는 없었고 MATCH (n) RETURN count(n) 은 36, MATCH ()-[r]->() RETURN count(r) 은 53 이 나왔어.','p-a'),('네가 실행해 본 것이 아니라 graph.json 을 읽어 따져 본 것이라는 점도 파일 맨 위에 밝혀 줘.','p-b'))
BAD=P7x.split('그 규칙을 따라 줘. ',1)[1]
alt=lambda t: f'<q style="display:block;quotes:none;background:#f6f8fa;border-radius:8px;padding:6px 10px;margin:6px 0 0;font-size:14px">{e(t)}</q>'
CNT=P('수_세기.cypher'); Q_EMPTY='MATCH (n) RETURN count(n) AS n;\nSHOW CONSTRAINTS YIELD name RETURN count(*) AS c;'
assert Q_EMPTY in P('0_준비_빈_DB_확인.txt')
Q_SHOW='SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties ORDER BY name;'
ERR=P('6a_실행_오류.txt'); ERRX=P('3x_실행_오류.txt'); assert 'already exists' in ERR and 'Enterprise Edition' in ERRX
run6=P('6c_실행_검사_틀린_데이터.txt'); run7=P('7_실행_검사_6_더한_뒤.txt')
tail6='\n'.join(run6.split('\n')[24:]); row7='\n'.join(run7.split('\n')[-2:])
assert tail6.startswith('id, 노드_수') and row7.startswith('유형, cardinality')
q3=[s.strip() for s in re.split(r'\n\n',C3) if s.strip().startswith('// 조회')]; assert len(q3)==3
q3_3=re.sub(r'(?m)^//.*\n','',q3[2]).strip()
run3=P('5_실행_조회.txt').split('\n'); assert len(run3)==6
c6=C4[C4.index('// 검사 6.'):]; assert len(re.findall(r'(?m)^// 검사 \d\. ',C4))==6

pages=[]
# ── 준비 ──
pages.append(hero('준비','<small>통합반 오프라인 2회차 · 실습 2 · 50분</small>설계한 지식을<br>그래프 DB에 넣고 검사한다','앞의 실습에서 <code>schema.json</code>을 보완하고 그 약속대로 <code>graph.json</code>에 설비, 센서, 부품, 공급사를 적었다. 두 파일은 아직 글자일 뿐이어서 「이 부품을 승인 공급사에서 가장 싸게 사려면」 같은 물음에 스스로 답하지 못한다. 오늘은 이 둘을 Cypher로 옮겨 그래프 DB에 넣고, 넣은 것이 설계한 것과 같은지를 질의로 검사한다. Cypher를 쓰는 일은 Copilot이 하고, <b>실행하기 전에 읽고, 실행하고, 결과를 가리는 일은 내가 한다.</b>',[('끝나면 남는 것',f'결과 폴더의 Cypher 파일 넷, 노드 {NN} · 관계 {NR}이 든 그래프 DB'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna), Neo4j Browser'),('전제','2회차 실습 1을 마쳤고, 온라인 2일차의 Cypher 단원을 들었다')])
+'<section class="sect"><h2>오늘 하는 일의 순서</h2><p>Cypher를 손으로 쓰는 일은 거의 없다. 요청은 이 가이드에 준비되어 있어 복사해 보내고, 만들어진 파일을 읽은 뒤 Neo4j Browser에 붙여넣어 실행한다. 한 번에 다 만들어 한 번에 넣지 않는다. <b>파일 하나를 만들고, 읽고, 실행하고, 수를 센 다음</b> 다음 파일로 간다.</p><div class="flow"><div><em>1</em><b>읽게 한다</b>넣을 것의 수와, DB가 막아 주는 것과 아닌 것을 말하게 한다</div><div><em>2</em><b>정해 주고 계획을 받는다</b>제약, 문장의 모양, 검사할 것을 정해 준다</div><div><em>3</em><b>제약을 건다</b>같은 식별자가 둘 들어오지 못하게 한다</div><div><em>4</em><b>인스턴스를 넣는다</b>문장을 읽고 실행한 뒤 노드와 관계를 센다</div><div><em>5</em><b>조회하고 검사한다</b>관계를 따라 물음에 답하고, 정의와 어긋난 곳을 찾는다</div><div><em>6</em><b>틀린 데이터를 넣어 본다</b>제약이 막는 것과 검사가 잡는 것을 가린다</div><div><em>7</em><b>검사를 되돌려 준다</b>놓친 것을 잡도록 고치게 한다</div><div><em>8</em><b>규칙을 시험하고 다시 넣는다</b>지우지 않고도 다시 넣을 수 있음을 본다</div></div></section>'
+'<section class="sect"><h2>누가 무엇을 하는가</h2><p>오늘은 창을 둘 쓴다. VS Code에서는 Copilot이 Cypher 파일을 쓰고, 웹 브라우저의 Neo4j Browser에서는 내가 그 파일의 문장을 실행한다.</p>'+who_fig+'</section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>지난_시간/</span>               <i>← 앞의 실습에서 만든 것. 읽기만 한다</i>\n│  ├─ schema.json              <i>← 클래스 '+str(len(S['classes']))+', 관계 '+str(len(S['relationships']))+'</i>\n│  └─ graph.json               <i>← 노드 '+str(NN)+', 관계 '+str(NR)+'</i>\n└─ <span>결과/</span>                    <i>← 비어 있다. 오늘 만드는 Cypher 파일이 놓인다</i></div><p><code>지난_시간</code> 폴더의 두 파일은 2회차 실습 1의 완성본이다. 앞의 실습에서 내가 만든 파일이 있으면 그것으로 바꿔 넣어도 된다. 그러면 이 가이드에 적힌 수와 이름이 내 것과 다를 수 있다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태의 Cypher 파일 넷이 들어 있다. 막히면 열어서 내 것과 견준다.</p>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 지난_시간, 결과 세 폴더가 펼쳐져 있고 지난_시간 폴더의 schema.json, graph.json이 보이게.'))
+do(2,'db','웹 브라우저 · Neo4j Browser','실습용 그래프 DB에 들어간다','<p>웹 브라우저의 새 창에서 <code>http://localhost:7474</code>를 연다. 접속 화면이 나오면 사용자 이름 <code>neo4j</code>, 비밀번호 <code>hydpass123</code>을 넣고 들어간다. 강사가 다른 주소나 비밀번호를 알려 주었으면 그것을 쓴다. 오늘 쓰는 것은 수업의 기준 지식이 든 그래프 DB가 아니라 <b>실습용으로 따로 둔 그래프 DB</b>다.</p><p>VS Code 창과 이 창을 화면에 나란히 두거나, Alt+Tab으로 오갈 수 있게 해 둔다.</p>')
+mapbox(BROWSER,'Neo4j Browser에서 쓰는 곳','<p>맨 위의 <b>입력 칸</b>에 Cypher를 적거나 붙여넣고, 오른쪽의 실행 단추(▶)를 누른다. 결과는 입력 칸 아래에 쌓이고, 가장 위의 것이 방금 실행한 것이다.</p><p>결과 상자의 왼쪽에서 표로 볼지 그래프로 볼지를 고른다. 오늘은 대부분 표로 본다.</p>')
+do(3,'db','Neo4j Browser · 입력 칸','넣기 전에, 그래프 DB가 비어 있는지 센다','<p>아래 두 문장을 복사해 입력 칸에 붙여넣고 실행한다. 첫 문장은 들어 있는 노드의 수를, 둘째 문장은 걸려 있는 제약의 수를 센다.</p>'+cy(Q_EMPTY)+'<p>둘 다 <code>0</code>이 나와야 한다.</p>'+shot('Neo4j Browser에 들어간 뒤 위의 두 문장을 실행한 화면. 입력 칸과, 결과에 0이 나온 것이 보이게. 입력 칸과 실행 단추에 빨간 테두리를 얹는다.')+'<div class="if"><div><b>0이 아니라면 여기서 멈춘다</b>이미 무엇인가 들어 있는 그래프 DB다. 수업의 기준 지식이 든 DB일 수 있다. 오늘 넣을 노드의 식별자(<code>asset:hyd-01</code>, <code>sen:ts1</code>, <code>sv:ts1</code> 등)는 기준 지식의 식별자와 겹치므로, 그대로 넣으면 그 노드의 값을 덮어쓴다. 아무것도 실행하지 말고 강사에게 알린다.</div><div><b>접속 화면에서 들어가지지 않는다면</b>주소 끝의 숫자(7474)와 비밀번호를 다시 본다. 그래도 안 되면 강사에게 알린다. 실습용 그래프 DB가 켜져 있지 않을 수 있다.</div></div>')
+do(4,'editor','VS Code · 편집기','넣을 것이 얼마나 되는지 본다',f'<p><code>지난_시간/graph.json</code>을 열어 <code>nodes</code>의 한 줄과 <code>rels</code>의 한 줄을 읽는다. 노드 한 줄이 그래프 DB의 노드 하나가 되고, <code>labels</code>의 클래스 이름이 레이블이 된다. 관계 한 줄은 <code>a</code>에서 <code>b</code>로 가는 관계 하나가 된다. 넣은 뒤에 세어서 맞춰 볼 수는 아래와 같다.</p>'+count_table+f'<p>노드 {NN}개와 관계 {NR}개다. 손으로 넣기에는 많고, 눈으로 훑어 맞았는지 가리기에도 많다. 그래서 넣는 문장은 Copilot에게 쓰게 하고, 맞았는지는 질의로 센다.</p>')
+nxt(1,'1. 만들기 전에, 먼저 읽게 한다'))

# ── 1 ──
pages.append(hero('1단계','만들기 전에,<br>먼저 읽게 한다','첫마디가 「이 두 파일을 Cypher로 바꿔 줘」이면 AI는 읽자마자 파일을 쓴다. 어떤 제약을 걸지, 관계의 끝 노드가 없으면 어떻게 할지 같은 판단이 내가 모르는 사이에 내려져 문장에 들어간다. 그래서 첫 요청은 <b>읽고, 이해한 것을 말해 보라</b>는 요청으로 한다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','넣을 것의 수, DB가 막아 주는 것과 아닌 것, 내가 정할 것이 채팅에 정리되어 있다'),('아직 생기면 안 되는 것','결과 폴더의 파일')])
+mapbox(vs('chat'),'이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>'+copy(P1,rich=P1rich)+'<div class="parts"><div class="a"><b>무엇을 읽는가</b>규칙 파일과 지난 시간의 두 파일. 스키마(약속)와 인스턴스 데이터(실제 대상)를 함께 읽혀야 「약속 가운데 무엇을 DB가 지켜 주는가」를 따질 수 있다.</div><div class="b"><b>어떤 모양으로 답하는가</b>넣을 것의 수, 제약과 검사의 구분, 내가 정할 것. 첫째는 넣은 뒤에 맞춰 볼 기준이 되고, 둘째는 오늘 만들 파일의 얼개가 된다.</div><div class="c"><b>하지 말 것</b>이 요청에서 가장 중요한 문장이다. 이 한 줄이 없으면 읽자마자 파일을 쓴다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 클래스별 노드 수와 관계 유형별 관계 수의 표, 제약으로 막는 것과 질의로 검사하는 것을 나눈 부분, 끝에서 「정해 주셔야 하는 것」을 번호로 묻는 부분이 보이게(길면 두세 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')+f'<div class="find"><div><i>①</i><p style="margin:0"><b>넣을 것의 수</b><span>노드 {NN}, 관계 {NR}이라고 했는가. 준비 단계의 표와 클래스별 수까지 같아야 한다. 다르면 다른 파일을 읽었거나 잘못 센 것이다. 이 수가 4단계에서 그래프 DB가 돌려주는 수와 맞춰 볼 기준이다.</span></p></div><div><i>②</i><p style="margin:0"><b>제약으로 막는 것과 질의로 검사하는 것</b><span>식별자의 유일함은 제약으로 막을 수 있다고 했는가. 필수 속성과 자료형을 제약으로 거는 일에 「Enterprise」라는 말을 붙였는가. 관계의 양 끝과 카디널리티는 질의로 검사해야 한다고 했는가.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 나에게 되묻는 것</b><span>답의 끝에 정해 달라는 목록이 있는가. 어떤 제약을 걸지, 문장을 어떻게 묶을지, 관계의 끝 노드가 없을 때 어떻게 할지가 들어 있을 것이다.</span></p></div></div>'+'<p>②를 표로 정리하면 아래와 같다. 온라인에서 본 「온톨로지 스키마와 Neo4j의 대응」 표의 마지막 줄, 식별자의 고유성만 DB 제약으로 옮겨진다는 것이 이것이다. 실습용 그래프 DB는 Neo4j Community 판이어서 유일 제약만 걸 수 있다.</p>'+who_table+'<div class="note"><b>되묻는 까닭</b>규칙 파일의 「정해져 있지 않은 것」에 여섯 줄을 적고 「요청에 없으면 정하지 말고 묻는다」고 해 두었기 때문이다. 규칙이 없었다면 이 자리들은 AI가 알아서 채웠을 것이고, 무엇이 어떻게 정해졌는지는 Cypher를 뜯어보아야 알 수 있다.</div><div class="if"><div><b>파일이 생겨 버렸다면</b>탐색기의 <code>결과</code> 폴더에 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 채팅의 「실행 취소」로 되돌리거나 그 파일을 지운 뒤, 요청을 다시 복사해 보낸다.</div><div><b>되묻는 것이 없다면</b>「Cypher 로 옮기기 전에 내가 정해 줘야 하는 것을 번호로 적어 줘」라고 한 번 더 묻는다. 그래도 없으면 다음 단계로 간다. 다음 요청이 그 자리를 모두 정해 준다.</div></div>')
+nxt(2,'2. 정해 주고, 계획부터 받는다',0))

# ── 2 ──
pick=('<table class="res"><thead><tr><th>정할 것</th><th>권하는 답 (아래 복사 상자에 들어 있다)</th><th>다르게 고르려면</th></tr></thead><tbody>'
 '<tr><td><b>제약의 범위</b><br>2번 줄</td><td>클래스 11개의 <code>id</code>에만 유일 제약을 건다. 스키마가 「같은 식별자를 가진 노드는 하나뿐」이라고 약속한 것이 <code>id</code>이기 때문이다</td><td>태그나 품번이 겹치는 것도 넣는 순간에 막고 싶으면 2번 줄을 바꾼다. 그러면 3단계에서 제약의 수가 11보다 많은 것이 맞다'+alt('2. 유일 제약은 클래스 11개 모두의 id 에 걸고, Sensor 의 tag, Actuator 의 signal, Part 의 part_no, Asset 의 code 에도 건다.')+'</td></tr>'
 f'<tr><td><b>문장의 묶음</b><br>3번 줄</td><td>노드 하나에 문장 하나, 관계 하나에 문장 하나. {NN+NR}문장으로 길어지지만 <code>MERGE</code>, <code>MATCH</code>, <code>SET</code>만으로 읽을 수 있고 <code>graph.json</code>과 한 줄씩 맞춰 볼 수 있다</td><td>파일을 짧게 하려면 3번 줄을 바꾼다. 그러면 4단계의 「한 줄씩 맞춰 읽기」는 내 파일과 모양이 다르다'+alt('3. 같은 클래스의 노드와 같은 유형의 관계는 한 문장으로 묶는다.')+'</td></tr>'
 '<tr><td><b>관계의 끝</b><br>4번 줄</td><td>양 끝을 레이블과 <code>id</code>로 <code>MATCH</code>해 찾고, 없으면 만들지 않는다. 아래 그림의 오른쪽이다</td><td>이 줄은 권하는 답 그대로 두기를 권한다. 6단계에서 그 까닭을 직접 본다</td></tr>'
 '<tr><td><b>검사의 모양</b><br>8번 줄</td><td>어긋난 것만 행으로 낸다. 0행이면 통과여서, 결과를 읽지 않고도 행이 있는지만 보면 된다</td><td>검사할 것을 더하거나 빼려면 (1)~(5) 가운데 줄을 고친다. 7단계에서 하나를 더하게 되므로 지금은 그대로 가도 된다</td></tr>'
 '</tbody></table>')
pages.append(hero('2단계','정해 주고,<br>계획부터 받는다','Copilot이 되물은 것은 Cypher 문법의 문제가 아니라 <b>어떻게 넣을 것인가의 설계</b>다. 같은 <code>graph.json</code>도 문장을 어떻게 쓰느냐에 따라, 두 번 넣었을 때 노드가 두 배가 되기도 하고 그대로이기도 하다. 정해 주는 기준은 둘이다. 내가 읽을 수 있는가, 다시 실행해도 같은가.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','내가 정한 것이 반영된 계획이 채팅에 있다'),('아직 생기면 안 되는 것','결과 폴더의 파일')])
+'<section class="sect"><h2>가장 크게 갈리는 결정: 관계의 끝 노드가 없으면</h2><p>관계를 만드는 문장은 먼저 양 끝의 노드를 찾아야 한다. 찾는 낱말이 <code>MERGE</code>인가 <code>MATCH</code>인가에 따라, 끝 노드의 <code>id</code>가 잘못 적혔을 때 일어나는 일이 다르다.</p><div class="vs"><div class="bad"><b>끝 노드도 MERGE로 찾으면</b>없으면 만든다. 잘못 적힌 <code>id</code> 하나만 가진, 이름도 없는 노드가 조용히 생기고 관계가 거기에 이어진다. 엉뚱한 참조가 데이터가 되어 남는다.</div><div class="good"><b>끝 노드를 MATCH로 찾으면 (권하는 답)</b>없으면 찾은 것이 없으므로 관계도 만들어지지 않는다. 오류도 나지 않는다. 그 대신 관계의 수가 모자라게 되므로, 넣은 뒤에 수를 세면 드러난다.</div></div><p>어느 쪽도 넣는 순간에 알려 주지는 않는다. 그래서 넣는 문장과 함께 <b>세고 검사하는 질의</b>를 만든다.</p></section>'
+do(1,'editor','이 화면','네 가지를 고른다','<p>Copilot이 물어 온 것 가운데 결과를 크게 가르는 네 가지다. 가운데 칸이 이 가이드가 권하는 답이고, 완성 폴더는 이 답으로 만든 것이다. 처음이면 권하는 답 그대로 간다.</p>'+pick)
+do(2,'chat','Copilot 채팅 · 입력 칸','정한 것을 보낸다','<p>아래 요청에는 권하는 답이 번호마다 한 줄씩 들어 있다. 「복사」를 눌러 채팅에 붙여넣는다. 다르게 고른 것이 있으면 <b>보내기 전에 입력 칸에서 그 줄만</b> 위 표의 문장으로 바꾼다.</p>'+copy(P2,rich=P2rich,pre=True)+'<div class="parts"><div class="a"><b>1번과 5번</b>1번은 Copilot이 알 수 없는 사실(DB의 종류와 판)을 알려 준 것이다. 5번은 다시 넣을 때의 약속이다. <code>graph.json</code>이 기준이고, DB의 값이 그것과 다르면 덮어쓴다.</div><div class="b"><b>7번의 세 물음</b>지난 시간에 Copilot이 두 파일을 읽어 답했던 물음 그대로다. 이번에는 같은 물음에 그래프 DB가 답하게 한다. 「열교환기」, 「유압 펌프」처럼 대장의 이름이 아닌 말을 무엇으로 찾을지도 정해 주었다.</div><div class="c"><b>마지막 문장</b>바로 만들지 않고 계획을 먼저 말하게 한다. 규칙 파일의 8번이 이 말을 받으면 계획만 말하도록 정해 두었다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 세 가지를 찾는다','<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 파일마다 어떤 문장이 몇 개 들어갈지와 본보기 문장이 함께 온다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 02_적재.cypher의 본보기 문장(MERGE … SET, MATCH … MERGE)과, 끝의 「확인해 주실 것」이 보이게. 본보기 문장의 MERGE 괄호 안과 「확인해 주실 것」에 테두리를 얹는다.')+f'<div class="find"><div><i>①</i><p style="margin:0"><b>본보기 문장의 MERGE</b><span>노드를 만드는 문장에서 <code>MERGE</code>의 괄호 안에 <code>id</code>만 들어 있고 나머지 속성은 <code>SET</code> 뒤에 있는가. 괄호 안에 이름까지 넣으면 이름을 고쳐 다시 넣었을 때 같은 노드를 찾지 못한다.</span></p></div><div><i>②</i><p style="margin:0"><b>문장의 수</b><span>01은 11문장, 02는 {NN+NR}문장(노드 {NN}, 관계 {NR})이라고 했는가.</span></p></div><div><i>③</i><p style="margin:0"><b>스스로 정해 넣은 것</b><span>여덟 가지를 정해 주었는데도 Copilot이 더 정한 것이 있다. 끝에 「확인해 주실 것」으로 적어 온다. 무엇인지 읽어 둔다. 조회의 「기대되는 답」에 「실행 결과가 아니다」라는 말을 붙였는지도 본다.</span></p></div></div><div class="if"><div><b>계획 없이 파일을 만들었다면</b>요청의 마지막 문장이 빠진 것이다. 만든 파일을 지우고 요청을 다시 복사해 보낸다.</div><div><b>계획이 내가 정한 것과 다르다면</b>「4번에서 끝 노드는 MATCH 로 찾기로 했어. 계획에는 MERGE 로 되어 있어.」처럼 번호와 함께 어디가 다른지를 말한다.</div></div>')
+nxt(3,'3. 제약 파일 하나만 만들고, 실행한다',1))

# ── 3 ──
first_con=next(l for l in C1.split('\n') if 'lab_sensor_id' in l)
pages.append(hero('3단계','제약 파일 하나만 만들고,<br>실행한다','넣는 것보다 제약이 먼저다. 노드를 넣은 뒤에 제약을 걸면, 그 사이에 겹친 식별자가 들어왔어도 막을 수 없었던 것이 된다. 그리고 파일 넷을 한꺼번에 만들게 하지 않는다. <b>하나를 만들고, 읽고, 실행해 본 다음</b> 다음으로 간다. 무엇이 잘못되었는지 가릴 수 있는 크기로 나누는 것이다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','그래프 DB에 유일 제약 11개가 걸려 있다'),('아직 생기면 안 되는 것','결과/02_적재.cypher')])
+do(1,'chat','Copilot 채팅 · 입력 칸','계획에 답하고, 범위를 정해 준다','<p>아래 요청을 복사해 보낸다. 내 계획에 고치고 싶은 곳이 있으면 첫 문장 뒤에 한 줄을 덧붙인다.</p>'+copy(P3,rich=P3rich)+'<div class="note"><b>범위를 적는 까닭</b>「여기까지」를 말하지 않으면 AI는 끝까지 간다. 파일 넷이 한꺼번에 생기면 넷을 한꺼번에 읽어야 하고, 실행하다 오류가 나면 어느 파일의 무엇 때문인지부터 찾아야 한다.</div>')
+do(2,'editor','VS Code · 편집기','<code>결과/01_제약.cypher</code>를 열어 읽는다',f'<p>탐색기의 <code>결과</code> 폴더에 파일이 생겼다. 눌러서 연다. 문장이 11개이고 클래스마다 하나씩이다. 한 문장만 읽으면 나머지는 레이블만 다르다.</p><div class="csv">{e(first_con)}</div><ul class="ask"><li><b>CREATE CONSTRAINT lab_sensor_id</b>제약을 만든다. 뒤의 말은 제약의 이름이다. 규칙 파일이 <code>lab_클래스_속성</code> 꼴로 짓게 했다. 여기의 <code>CREATE</code>는 노드가 아니라 제약을 만드는 것이다.</li><li><b>IF NOT EXISTS</b>같은 이름의 제약이 이미 있으면 아무것도 하지 않는다. 이 파일을 두 번 실행해도 오류가 나지 않는다.</li><li><b>FOR (n:Sensor) REQUIRE n.id IS UNIQUE</b><code>Sensor</code> 레이블이 붙은 노드끼리는 <code>id</code>가 겹칠 수 없다. 둥근 괄호와 콜론 뒤의 레이블은 온라인에서 본 노드 표기 그대로다.</li></ul>')
+do(3,'db','VS Code · 편집기 → Neo4j Browser','파일의 문장을 Neo4j Browser에 붙여넣어 실행한다','<p>편집기에서 파일 안을 한 번 누르고 전체를 고른 다음(Ctrl+A) 복사한다(Ctrl+C). Neo4j Browser의 입력 칸을 누르고 붙여넣은 뒤(Ctrl+V) 실행 단추(▶)를 누른다. <code>//</code>로 시작하는 설명 줄은 함께 붙여넣어도 된다.</p><p>이어서 아래 문장으로 걸린 제약을 본다.</p>'+cy(Q_SHOW)+'<p>아래 11행이 나오면 된다. 완성 폴더의 파일을 실행했을 때의 결과다.</p>'+out('3_실행_제약_목록.txt')+shot('Neo4j Browser에서 01_제약.cypher를 실행한 뒤 위의 SHOW CONSTRAINTS 문장을 실행한 화면. 결과 표에 lab_ 로 시작하는 제약 11행이 보이게.')+f'<div class="note"><b>필수 속성은 왜 제약으로 걸지 않는가</b>걸 수 없기 때문이다. 이 그래프 DB에 「센서에는 <code>tag</code>가 있어야 한다」는 제약을 만들려고 하면 아래와 같이 거절된다. 그래서 필수 속성은 5단계의 검사 질의로 본다.<div class="csv err" style="margin-bottom:0">{e(ERRX)}</div></div>'+'<div class="if"><div><b>빨간 오류가 나왔다면</b>오류 글을 그대로 복사해 Copilot에게 붙여넣고 「01_제약.cypher 를 실행했더니 이 오류가 나왔어. 어느 문장의 무엇 때문인지 말하고 그 문장만 고쳐 줘.」라고 한다. 오류 글을 내 말로 줄여 옮기지 않는다.</div><div><b>11행보다 많다면</b>준비 단계에서 제약의 수가 0이 아니었거나, 2단계에서 제약의 범위를 넓게 고른 것이다. 뒤쪽이면 맞는 결과다.</div></div>')
+nxt(4,'4. 넣는 문장을 읽고, 실행하고, 센다',2))

# ── 4 ──
pages.append(hero('4단계','넣는 문장을 읽고,<br>실행하고, 센다','이제 인스턴스를 넣는다. AI가 쓴 문장을 그대로 실행하면, 무엇이 들어갔는지는 실행한 사람도 모른다. 그래서 <b>실행하기 전에 읽는다.</b> 89문장을 다 읽지는 않는다. 노드 한 줄과 관계 한 줄을 <code>graph.json</code>의 그 줄과 맞춰 보고, 나머지는 실행한 뒤에 수로 가린다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면',f'그래프 DB에 노드 {NN}, 관계 {NR}이 들어 있다'),('맞춰 볼 것','그래프 DB가 센 수 ↔ graph.json의 수')])
+do(1,'chat','Copilot 채팅 · 입력 칸','실행한 결과를 알려 주고, 다음 파일을 시킨다','<p>같은 대화에서 이어서 보낸다. 3단계에서 내가 본 제약의 수가 11이 아니었다면 파란 문장의 수를 내 것으로 고쳐 보낸다.</p>'+copy(P4,rich=P4rich)+'<div class="parts"><div class="a"><b>실행한 결과</b>Copilot은 그래프 DB를 보지 못한다. 실행이 되었는지, 무엇이 나왔는지는 내가 말해 주어야 다음 일을 맞게 한다.</div><div class="b"><b>스스로 대조하게 했다</b>만든 파일을 <code>graph.json</code>과 다시 맞춰 보고 다르게 적은 곳을 밝히게 했다. 규칙 파일의 2번이 값을 글자 그대로 옮기게 정해 두었고, 이 문장은 그것을 지켰는지를 답으로 받는 것이다.</div><div class="c"><b>범위</b>이번에도 파일 하나다.</div></div>')
+do(2,'editor','VS Code · 편집기 (좌우로 나란히)','노드 한 줄과 관계 한 줄을 <code>graph.json</code>과 맞춰 읽는다','<p><code>결과/02_적재.cypher</code>를 열고 <code>지난_시간/graph.json</code>을 오른쪽으로 끌어 나란히 둔다. 유온 센서의 줄과, 펌프 축 씰 키트를 A정밀에서 사는 줄을 찾는다(Ctrl+F로 <code>sen:ts1</code>, <code>sup:a</code>). 아래는 완성 폴더의 파일에서 옮긴 것이다.</p>'+read_fig+'<div class="find"><div><i>①</i><p style="margin:0"><b>MERGE의 괄호 안</b><span>노드 줄에서 괄호 안에 레이블과 <code>id</code>만 있는가. <code>name</code>, <code>tag</code>, <code>virtual</code>은 <code>SET</code> 뒤에 있는가. 무엇을 같은 노드로 볼지는 괄호 안에 적은 것으로 정해진다.</span></p></div><div><i>②</i><p style="margin:0"><b>방향</b><span>관계 줄에서 <code>a</code>가 <code>Part</code>, <code>b</code>가 <code>Supplier</code>이고 화살표가 <code>(a)-[…]-&gt;(b)</code>인가. 스키마의 <code>SUPPLIED_BY</code>는 <code>from</code>이 <code>Part</code>, <code>to</code>가 <code>Supplier</code>다. <code>graph.json</code>에는 없던 레이블을 Copilot이 찾아 적었다.</span></p></div><div><i>③</i><p style="margin:0"><b>값의 모양</b><span><code>false</code>와 <code>35</code>에 따옴표가 없는가. 따옴표가 있으면 글자로 들어가 <code>WHERE s.virtual = false</code>나 가장 싼 값을 고르는 일이 되지 않는다. 관계의 값 셋은 관계의 <code>SET</code>에 있는가.</span></p></div></div><p>마지막으로 파일 안에서 <code>CREATE</code>를 찾아본다(Ctrl+F). 한 건도 없어야 한다.</p>')
+do(3,'db','VS Code · 편집기 → Neo4j Browser','파일 전체를 붙여넣어 실행한다',f'<p>3단계와 같은 방법이다. <code>02_적재.cypher</code> 전체를 고르고(Ctrl+A) 복사해 Neo4j Browser의 입력 칸에 붙여넣고 실행한다. 문장이 {NN+NR}개여서 끝나는 데 몇 초 걸린다.</p>'+shot(f'Neo4j Browser에 02_적재.cypher 전체를 붙여넣어 실행한 화면. 문장마다 성공했다는 표시가 줄지어 보이게. 문장의 수({NN+NR})가 보이면 함께.'))
+do(4,'db','Neo4j Browser · 입력 칸','그래프 DB에게 세게 한다','<p>들어간 것을 그래프 DB에게 직접 묻는다. 아래 네 문장을 실행한다. 앞의 둘은 전체 수를, 뒤의 둘은 레이블별 · 관계 유형별 수를 센다.</p>'+cy(CNT)+f'<p>아래와 같이 나오면 된다. 준비 단계의 표, 그리고 1단계에서 Copilot이 센 수와 한 줄씩 맞춘다. 노드 {NN}, 관계 {NR}이다.</p>'+out('4_실행_수.txt')+f'<div class="if"><div><b>관계가 {NR}보다 적다면</b>끝 노드를 찾지 못해 만들어지지 않은 관계가 있다. 관계 유형별 수에서 준비 단계의 표와 다른 줄을 찾고, 「MOUNTED_ON 이 9가 아니라 8이야. 02_적재.cypher 에서 MOUNTED_ON 문장의 양 끝 레이블과 id 를 graph.json 과 다시 대조해 줘.」처럼 유형과 수를 말한다.</div><div><b>빨간 오류가 나왔다면</b>오류 글을 그대로 Copilot에게 붙여넣는다. 고친 파일을 다시 실행해도 된다. 이미 들어간 것이 두 번 들어가지 않는다. 8단계에서 직접 본다.</div></div>')
+nxt(5,'5. 관계를 따라 조회하고, 정의와 맞는지 검사한다',3))

# ── 5 ──
pages.append(hero('5단계','관계를 따라 조회하고,<br>정의와 맞는지 검사한다','수가 맞는 것은 빠진 것이 없다는 뜻일 뿐이다. 관계가 엉뚱한 곳에 이어져 있어도 수는 맞는다. 두 가지를 더 본다. 지난 시간의 물음에 <b>그래프 DB가 관계를 따라가 답하는지</b>, 그리고 들어간 것이 <b>스키마의 정의와 어긋난 곳이 없는지</b>다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','세 물음의 답이 그래프 DB에서 나왔고, 검사 다섯 가지를 통과했다'),('생기는 파일','결과/03_조회.cypher, 결과/04_검사.cypher')])
+do(1,'chat','Copilot 채팅 · 입력 칸','결과를 알려 주고, 두 파일을 시킨다',f'<p>아래 요청을 보낸다. 4단계에서 내가 센 수가 {NN}과 {NR}이 아니었다면 파란 문장의 수를 내 것으로 고친다.</p>'+copy(P5,rich=P5rich)+'<div class="note"><b>「나와야 맞는 것」을 적게 한 까닭</b>질의만 있으면, 실행해서 나온 결과가 맞는지를 가릴 기준이 없다. Copilot이 파일을 읽어 따져 본 답을 설명 줄에 적어 두게 하면, 내가 실행한 결과와 견줄 수 있다. 둘이 다르면 질의가 틀렸거나, 넣은 것이 틀렸거나, 따져 본 것이 틀린 것이다. 어느 쪽이든 찾아볼 곳이 생긴다.</div>')
+do(2,'db','VS Code · 편집기 → Neo4j Browser','조회 질의를 하나씩 실행해 답을 본다',f'<p><code>결과/03_조회.cypher</code>를 연다. 질의가 셋이다. 이번에는 파일 전체가 아니라 <b>질의 하나씩</b>, <code>MATCH</code>부터 쌍반점(<code>;</code>)까지를 끌어서 고르고 복사해 실행한다. 설명 줄의 「나와야 맞는 것」과 결과를 견준다. 완성 폴더의 세 질의를 실행한 결과는 아래와 같다.</p><div class="csv"><i>// 조회 1. 열교환기의 실물 센서와 한계</i>\n{e(run3[0])}\n{e(run3[1])}\n<i>// 조회 2. HYD-02 유압 펌프의 교체 부품을 승인 공급사에서 가장 싸게</i>\n{e(run3[2])}\n{e(run3[3])}\n<i>// 조회 3. 순정 공급사에서 팬 베어링</i>\n{e(run3[4])}\n{e(run3[5])}</div>'+path_fig+'<p>가장 짧은 셋째 질의를 읽어 본다. 온라인에서 본 표기 그대로다.</p>'+f'<div class="csv">{e(q3_3)}</div>'+'<ul class="ask"><li><b>(p:Part {name: \'팬 베어링\'})</b>이름이 팬 베어링인 부품에서 출발한다.</li><li><b>-[r:SUPPLIED_BY]-&gt;</b>관계에도 변수 <code>r</code>을 붙였다. 단가와 납기가 노드가 아니라 관계에 있어서, <code>r.price</code>, <code>r.lead_days</code>로 부른다.</li><li><b>(s:Supplier {grade: \'순정\'})</b>지난 시간의 끝에 더한 <code>grade</code> 속성으로 거른다. 이름의 괄호 안 글자를 읽지 않는다.</li></ul>'+shot('Neo4j Browser에서 조회 2를 실행한 화면. 입력 칸의 질의와, 결과 표의 한 행(펌프 축 씰 키트, P-PMP-SEAL, A정밀 (저가), 35)이 보이게.'))
+do(3,'db','VS Code · 편집기 → Neo4j Browser','검사 질의를 실행한다',f'<p><code>결과/04_검사.cypher</code>를 연다. 검사 1은 수를 내고, 검사 2부터 5까지는 어긋난 것만 행으로 낸다. 조회와 같은 방법으로 검사를 하나씩 실행한다. 검사 1에서는 4단계와 같은 수가 {len(S["classes"])+len(S["relationships"])}행으로 나오고, <b>검사 2부터 5까지는 한 행도 나오지 않아야</b> 한다. 행이 없으면 Neo4j Browser는 표 대신 돌려줄 것이 없다는 말을 보여 준다.</p>'+'<table class="res"><thead><tr><th>검사</th><th>무엇을 찾는가</th><th>스키마의 어느 조건인가</th></tr></thead><tbody><tr><td>검사 2</td><td>같은 <code>id</code>를 가진 노드가 둘 이상인 곳. 레이블이 달라도 잡는다</td><td>고유한 식별자</td></tr><tr><td>검사 3</td><td>필수 속성이 빠진 노드와 관계</td><td>필수 속성</td></tr><tr><td>검사 4</td><td>양 끝의 레이블이 <code>from</code>, <code>to</code>와 다른 관계</td><td>연결 조건</td></tr><tr><td>검사 5</td><td><code>limit_direction</code>, <code>grade</code>의 값이 허용값 밖인 노드</td><td>자료형(enum)</td></tr></tbody></table>'+'<p>검사 3과 4의 질의를 열어 보면 클래스마다의 필수 속성 목록과 관계마다의 <code>from</code>, <code>to</code>가 질의 안에 적혀 있다. <code>schema.json</code>의 정의를 Cypher 안으로 옮겨 놓은 것이다. 스키마가 바뀌면 이 목록도 따라 고쳐야 한다.</p>'+'<div class="if"><div><b>검사 2~5에서 행이 나왔다면</b>그 행이 어긋난 곳이다. 행에 나온 <code>id</code>를 <code>graph.json</code>에서 찾아본다. 파일이 틀렸으면 지난 실습의 것이 틀린 것이고, 파일은 맞는데 DB가 다르면 넣는 문장이 틀린 것이다. 나온 행을 그대로 Copilot에게 붙여넣는다.</div><div><b>문법 오류가 났다면</b>Copilot은 이 질의를 실행해 보지 못하고 썼다. 오류 글과 질의의 번호를 그대로 알려 주고 그 질의만 고치게 한다.</div></div>')
+nxt(6,'6. 일부러 틀린 데이터를 넣어 본다',4))

# ── 6 ──
B6=P('6b_막히지_않는_것.cypher')
wrong=('<table class="res"><thead><tr><th>넣어 본 것</th><th>넣는 순간</th><th>검사를 실행하면</th></tr></thead><tbody>'
 '<tr><td>이미 있는 <code>sen:ts1</code>과 같은 <code>id</code>의 센서</td><td><mark>막혔다</mark>. 유일 제약</td><td>들어가지 않았으므로 볼 것이 없다</td></tr>'
 '<tr><td>① <code>tag</code>, <code>virtual</code>이 없는 센서</td><td>들어갔다</td><td>검사 3이 잡았다</td></tr>'
 '<tr><td>② 센서와 같은 <code>id</code>를 가진 구성 요소</td><td>들어갔다. 제약은 레이블마다 따로 본다</td><td>검사 2가 잡았다</td></tr>'
 '<tr><td>③ 끝이 구성 요소인 <code>MEASURES</code></td><td>들어갔다</td><td>검사 4가 잡았다</td></tr>'
 '<tr><td>④ 센서 하나가 상태 변수 둘을 재는 <code>MEASURES</code></td><td>들어갔다</td><td><mark>어느 검사에도 나오지 않았다</mark></td></tr>'
 '<tr><td>⑤ 없는 <code>id</code>(<code>comp:cooler</code>)를 끝으로 적은 <code>MOUNTED_ON</code></td><td>오류 없이 지나갔고, 아무것도 만들어지지 않았다</td><td>잡을 것이 없다. <code>MOUNTED_ON</code>의 수는 9 그대로다</td></tr>'
 '</tbody></table>')
pages.append(hero('6단계','일부러 틀린 데이터를<br>넣어 본다','검사가 0행이라는 것은 두 가지 가운데 하나다. 데이터가 맞거나, 검사가 아무것도 잡지 못하거나. 맞는 데이터만 넣어서는 둘을 가릴 수 없다. 그래서 <b>틀린 데이터를 일부러 넣어</b> 무엇이 넣는 순간에 막히고, 무엇이 검사에서 잡히고, 무엇이 끝내 지나가는지를 본다. 이 단계에서는 Copilot을 쓰지 않는다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','제약이 막는 것, 검사가 잡는 것, 둘 다 놓치는 것을 하나씩 보았다'),('쓰는 곳','Neo4j Browser')])
+do(1,'db','Neo4j Browser · 입력 칸','이미 있는 식별자로 센서를 하나 더 만들어 본다','<p>유온 센서 <code>sen:ts1</code>은 이미 들어 있다. 같은 <code>id</code>로 센서를 하나 더 만드는 문장을 실행한다. <code>CREATE</code>는 이미 있는지를 보지 않고 새로 만드는 낱말이다.</p>'+cy(P('6a_막히는_것.cypher'))+'<p>빨간 오류가 나오고, 아래 글이 들어 있다. 괄호 안의 번호는 사람마다 다르다.</p>'+out('6a_실행_오류.txt','err')+'<p>3단계에서 건 제약 <code>lab_sensor_id</code>가 막은 것이다. 노드는 만들어지지 않았다.</p>'+shot('Neo4j Browser에서 위 CREATE 문장을 실행해 빨간 오류가 난 화면. 오류 글의 already exists 부분이 보이게 테두리를 얹는다.'))
+do(2,'db','Neo4j Browser · 입력 칸','제약이 막지 못하는 틀린 데이터 다섯 가지를 넣는다','<p>이번에는 식별자가 겹치지 않는, 그러나 스키마의 정의와 어긋나는 것들이다. 설명 줄의 번호가 틀린 곳 하나다. 전체를 복사해 실행한다. 이름이 모두 「시험용」으로 시작하게 해 두어 나중에 이것만 골라 지울 수 있다.</p>'+cy(B6)+'<p>오류가 하나도 나지 않는다. 4단계의 「세는 문장」 가운데 앞의 둘을 다시 실행해 보면 노드는 38, 관계는 56이다. 노드 둘과 관계 셋이 늘었다. ⑤의 관계는 만들어지지 않았다.</p>')
+do(3,'db','VS Code · 편집기 → Neo4j Browser','검사 2~5를 다시 실행해, 무엇이 잡혔는지 본다','<p><code>결과/04_검사.cypher</code>의 검사 2, 3, 4, 5를 하나씩 다시 실행한다. 5단계에서는 한 행도 없던 검사에 이번에는 행이 나온다. 완성 폴더를 만들 때 나온 행은 아래와 같다.</p>'+f'<div class="csv"><i>// 검사 2</i>\n'+e(tail6.split('\n')[0])+'\n'+e(tail6.split('\n')[1])+'\n<i>// 검사 3</i>\n'+e(tail6.split('\n')[2])+'\n'+e(tail6.split('\n')[3])+'\n<i>// 검사 4</i>\n'+e(tail6.split('\n')[4])+'\n'+e(tail6.split('\n')[5])+'\n<i>// 검사 5 — 행 없음</i></div>'+'<p>넣어 본 여섯 가지를 한 표로 모으면 아래와 같다.</p>'+wrong+'<div class="note"><b>제약, 검사, 그리고 수</b>유일 제약은 넣는 순간에 막지만 한 레이블 안에서만 본다. 검사 질의는 넣은 뒤에 찾아내지만 질의에 적어 둔 것만 본다. ⑤처럼 만들어지지 않은 관계는 어긋난 데이터가 없어서 검사가 볼 것이 없고, 4단계처럼 넣은 뒤의 수를 넣으려던 수와 맞춰 보아야 드러난다. 세 가지가 서로 다른 구멍을 막는다.</div><div class="if"><div><b>내 검사는 다른 것을 잡았다면</b>검사 질의는 사람마다 다르게 만들어진다. 표의 「검사를 실행하면」 칸을 내 결과로 다시 채워 본다. 잡히지 않은 것이 다음 단계에서 되돌려 줄 것이다.</div><div><b>④가 내 검사에는 잡혔다면</b>2단계에서 검사할 것을 더 넣었거나 Copilot이 넓게 만든 것이다. 다음 단계에서는 표에서 잡히지 않은 다른 줄을 고른다.</div></div>')
+nxt(7,'7. 놓친 것을 잡도록 검사를 되돌려 준다',5))

# ── 7 ──
pages.append(hero('7단계','놓친 것을 잡도록<br>검사를 되돌려 준다','센서 하나가 상태 변수 둘을 재는 데이터가 들어갔는데 어느 검사에도 나오지 않았다. <code>schema.json</code>에는 <code>MEASURES</code>의 카디널리티가 <code>N:1</code>이라고 적혀 있다. 약속은 있는데 지키는지 보는 눈이 없는 것이다. 이것을 Copilot에게 되돌려 주어 검사를 보완하게 한다. <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','04_검사.cypher에 검사가 하나 늘었고, 시험 데이터를 지운 그래프 DB가 다시 깨끗하다')])
+'<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>'+e(BAD)+'</q>무엇이 모자란지가 글에 없다. 이렇게 보냈을 때는 파일이 고쳐지지 않고 「무엇을 더 검사할지」의 후보 아홉 가지가 표로 돌아왔다. 그 가운데서 다시 골라 한 번 더 보내야 한다.</div><div class="good"><b>구체적으로</b><q>센서 하나(sen:test)가 상태 변수 둘에 MEASURES 로 이어진 것은 어느 검사에도 나오지 않았어. MEASURES 의 cardinality 는 N:1 이야. 04_검사.cypher 의 끝에 검사 6을 더해 줘. … 검사 1부터 5까지와 다른 세 파일은 건드리지 마.</q>요청한 검사 하나만 파일 끝에 더해졌다.</div></div><div class="four"><div><b>무엇이</b>센서 하나가 상태 변수 둘을 재는데 어느 검사에도 나오지 않는다</div><div><b>왜</b>스키마의 카디널리티를 어긴 데이터가 들어와도 모르고 지나간다</div><div><b>어디를</b>04_검사.cypher의 끝에 검사 하나</div><div><b>어디까지</b>이미 있는 검사와 다른 세 파일은 그대로</div></div></section>'
+do(1,'chat','이 화면의 글 칸 → Copilot 채팅','네 가지를 넣어 직접 써서 되돌려 준다','<p>오늘 직접 쓰는 요청은 이것 하나다. 무엇이, 왜, 어디를, 어디까지. 네 가지를 넣어 내 말로 쓴다. 6단계에서 내가 넣은 데이터의 <code>id</code>와, 그것이 스키마의 어느 약속을 어겼는지를 적으면 「무엇이」와 「왜」가 채워진다. 새 검사가 무엇을 행으로 내야 하는지도 적는다.</p>'+write('w7','무엇이 잡히지 않았는지(넣은 데이터의 id), 왜 문제인지(스키마의 어느 약속), 어느 파일의 어디에 무엇을 더할지, 건드리지 말 곳을 적는다.')+'<details><summary>다 쓴 뒤에 견주어 볼 예</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">정답이 아니라 한 가지 예다. 내 글에 네 가지가 다 들어 있는지를 보는 데 쓴다. 완성 폴더는 이 예대로 고친 결과다.</p>'+copy(P7,'Copilot에게 보낼 요청 (예)',pre=True)+'</details>')
+do(2,'db','VS Code · 편집기 → Neo4j Browser','더해진 검사를 읽고, 실행한다','<p><code>결과/04_검사.cypher</code>의 맨 아래에 검사가 하나 늘었다. 앞의 검사들이 그대로인지 훑어본 뒤, 새 검사를 복사해 실행한다. 시험 데이터가 아직 들어 있으므로 <b>이번에는 행이 나와야</b> 맞다. 완성 폴더를 만들 때 나온 행은 아래와 같다.</p>'+f'<div class="csv">{e(row7)}</div>'+'<p>Copilot은 파일을 더하면서 「시험 데이터가 들어 있으면 관계의 수가 2인 1행이 나온다」고 했다. 실행해 보니 3이었다. ③에서 넣은, 구성 요소로 가는 <code>MEASURES</code>까지 세었기 때문이다. Copilot이 틀린 질의를 쓴 것이 아니라 따져 본 수가 실제와 달랐던 것이다. <b>따져 본 것과 실행한 것은 다를 수 있고, 그 차이는 실행한 사람만 안다.</b></p>'+'<details><summary>완성 폴더를 만들 때 한 번 더 되돌려 준 것</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">Copilot이 답의 끝에서, 건드리지 말라고 한 범위에 닿을까 봐 파일 맨 위의 설명 줄(「검사 질의 5개」)을 그대로 두었다고 알려 왔다. 실행한 결과와 함께 그 두 줄만 고치게 했다.</p>'+copy(P7b,'Copilot에게 보낸 요청')+'</details>')
+do(3,'db','Neo4j Browser · 입력 칸','시험 데이터를 지우고, 다시 검사한다','<p>틀린 데이터를 넣어 둔 채로 갈 수는 없다. 이름이 「시험용」으로 시작하는 노드와 거기에 이어진 관계만 지운다. 이 문장은 파일로 남기지 않고, 실습용 그래프 DB에 들어와 있는 것을 눈으로 확인한 지금 이 자리에서만 실행한다.</p>'+cy(P('7c_시험_데이터_지우기.cypher'))+f'<p>4단계의 「세는 문장」을 다시 실행해 노드 {NN}, 관계 {NR}으로 돌아왔는지 본다. 이어서 검사 2부터 6까지를 다시 실행한다. 모두 한 행도 나오지 않아야 한다. 틀린 데이터에서는 행이 나오고 맞는 데이터에서는 나오지 않는 것을 둘 다 보았으므로, 이제 이 0행은 믿을 수 있다.</p>'+'<div class="if"><div><b>노드가 36으로 돌아오지 않는다면</b>6단계의 문장을 고쳐 넣어 이름이 「시험용」으로 시작하지 않는 노드가 생긴 것이다. 검사 2, 3에 나온 행의 <code>id</code>가 그 노드다. 강사에게 알리고 그 노드를 함께 지운다.</div><div><b>새 검사가 맞는 데이터에서도 행을 낸다면</b>검사가 지나치게 넓은 것이다. 나온 행을 그대로 Copilot에게 붙여넣고 「이 행은 schema.json 의 cardinality 에 맞는 데이터야. 왜 나왔는지 말하고 검사 6만 고쳐 줘.」라고 한다.</div></div>')
+nxt(8,'8. 규칙을 시험하고, 다시 넣어 본다',6))

# ── 8 ──
pages.append(hero('8단계','규칙을 시험하고,<br>다시 넣어 본다','넣다가 꼬이면 다 지우고 처음부터 다시 넣고 싶어진다. 실습용 DB에서는 그래도 될 것 같다. 그런데 「먼저 다 지운다」는 문장이 파일에 남으면, 그 파일이 다른 그래프 DB에서 실행되는 날 그곳의 지식이 지워진다. 규칙 파일이 이것을 막는지 <b>어긋나는 요청을 보내</b> 확인하고, 지우지 않고도 다시 넣을 수 있다는 것을 직접 본다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','규칙 파일의 어느 줄이 무엇을 막는지 알고, 같은 파일을 다시 실행해도 수가 그대로인 것을 보았다'),('바뀌면 안 되는 것','결과/02_적재.cypher')])
+do(1,'chat','Copilot 채팅 · 입력 칸','먼저 다 지우는 문장을 넣어 달라고 해 본다','<p>급할 때 누구나 할 법한 요청이다. 「이번만」이라는 말까지 붙였다. 아래 요청을 그대로 보낸다.</p>'+copy(P8a)+'<div class="find"><div><i>①</i><p style="margin:0"><b>넣지 않았는가</b><span>탐색기에서 <code>결과/02_적재.cypher</code> 옆에 바뀌었다는 표시(M)가 새로 붙지 않아야 한다. 파일을 열어 맨 위에 <code>DETACH DELETE</code>가 없는지 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>무엇을 근거로 댔는가</b><span>답에 규칙의 번호나 문장이 나오는가. 「이번만」에 대해서는 무엇이라고 했는가.</span></p></div><div><i>③</i><p style="margin:0"><b>그 대신 무엇을 하라고 했는가</b><span>파일을 고치지 않고 그대로 다시 실행하라는 말이 있는가. 아래 3번에서 그것을 해 본다.</span></p></div></div>'+shot('먼저 다 지우는 문장을 넣어 달라는 요청에 Copilot이 넣지 않겠다고 답한 화면. 규칙을 근거로 든 문장과, 대신 다시 실행하라고 한 부분에 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','MERGE를 CREATE로 바꿔 달라고 해 본다','<p>이번에는 그럴듯한 까닭을 붙였다. 유일 제약이 있으니 <code>CREATE</code>로 써도 겹치지 않을 것이라는 말이다. 아래 요청을 보낸다.</p>'+copy(P8b)+'<p>이번에도 파일이 바뀌지 않아야 한다. 답에서 「유일 제약이 있어도 달라지는 것」을 무엇이라고 했는지 읽는다. 6단계의 첫 실험이 그 답이다. 이미 있는 <code>id</code>를 <code>CREATE</code>하면 겹치지는 않지만 오류가 나고, 그 문장은 값을 고쳐 주지도 않는다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 열고 「하면 안 되는 것」을 읽는다. 방금 두 요청을 막은 줄과, 「이번만」을 막은 줄이 각각 몇 번인지 찾는다. 찾은 다음 아래와 견준다.</p><ul class="ask"><li><b>지우는 문장을 막은 줄</b>'+e(R4).replace('`','')+'</li><li><b>CREATE를 막은 줄</b>'+e(R5).replace('`','')+'</li><li><b>「이번만」을 막은 줄</b>'+e(R9).replace('`','')+'</li></ul><div class="note"><b>규칙에 까닭까지 적는 까닭</b>4번과 5번은 「하지 않는다」에서 끝나지 않고 왜 안 되는지와 그 대신 무엇을 하는지를 적었다. 그래서 AI가 거절만 하지 않고 같은 목적을 이루는 길을 내놓는다. 7단계에서 내가 Neo4j Browser에 직접 친 지우는 문장은 이 규칙에 걸리지 않는다. 규칙이 막는 것은 지우는 문장이 <b>파일에 남는 것</b>이다.</div><div class="if"><div><b>정말로 넣어 버렸다면</b>채팅의 「실행 취소」로 되돌리거나, 파일에서 그 문장을 지운다. <b>그 파일을 실행하지 않는다.</b> 그리고 강사에게 알린다. 규칙 파일이 읽히지 않았을 수 있다. 요청 앞에 「이 폴더의 규칙(.github/copilot-instructions.md)을 다시 읽고 답해 줘.」를 붙여 한 번 더 보내 본다.</div><div><b>정말 다 지워야 한다면</b>규칙을 피해 갈 말을 찾지 않는다. 실습용 그래프 DB를 비우는 일은 강사와 함께, 어느 DB에 들어와 있는지를 확인하고 한다.</div></div>')
+do(4,'db','Neo4j Browser · 입력 칸','값 하나를 바꿔 놓고, 같은 파일을 다시 넣는다','<p>지우지 않고 다시 넣어도 되는지를 직접 본다. 먼저 유온 센서의 이름을 그래프 DB에서 다른 말로 바꿔 놓는다. 누군가 손으로 고쳐 버린 셈이다.</p>'+cy(P('8d_이름_바꾸기.cypher'))+f'<div class="csv">{e(P("8d_실행_이름.txt").split(chr(10))[0])}\n{e(P("8d_실행_이름.txt").split(chr(10))[1])}</div>'+'<p>이제 <code>결과/02_적재.cypher</code> 전체를 4단계와 같은 방법으로 <b>한 번 더</b> 붙여넣어 실행한다. 그다음 아래 문장으로 이름을 보고, 4단계의 「세는 문장」으로 수를 센다.</p>'+cy(P('8d_이름_보기.cypher'))+f'<div class="csv">{e(P("8d_실행_이름.txt").split(chr(10))[2])}\n{e(P("8d_실행_이름.txt").split(chr(10))[3])}\n<i>// 세는 문장의 앞의 둘</i>\n{e(chr(10).join(cnt_run[:4]))}</div>'+f'<p>이름은 <code>graph.json</code>의 값으로 돌아왔고, 노드는 {NN}, 관계는 {NR} 그대로다. {NN+NR}문장을 다시 실행했는데 하나도 늘지 않았다. <code>MERGE</code>가 <code>id</code>로 먼저 찾아 있는 노드를 썼고, <code>SET</code>이 값을 덮어썼기 때문이다. 2단계의 5번 줄에서 정한 대로다.</p>')
+'<section class="sect"><h2>시간이 남으면: 넣은 것을 그림으로 본다</h2><p>지금까지는 결과를 표로 보았다. 같은 그래프 DB를 그림으로도 볼 수 있다. 속성이 아니라 길 전체를 돌려받으면 Neo4j Browser가 노드와 관계를 그려 준다. HYD-01에서 구성 요소를 거쳐 센서와 상태 변수까지 가는 길을 본다.</p>'+cy(P('여유_그림.cypher'))+f'<p>결과 상자의 왼쪽에서 그래프 보기를 고른다. 길은 {P("여유_실행_길의_수.txt").split(chr(10))[1]}개이고 센서마다 하나다. 노드를 누르면 속성이 보인다. 화살표의 방향을 따라 읽어 본다. 센서에서 구성 요소로 가는 <code>MOUNTED_ON</code>은 화살표가 거꾸로여서, 질의에서도 <code>&lt;-[:MOUNTED_ON]-</code>로 적었다. 지난 시간에 종이와 파일로 설계한 구조가 이 그림이다.</p>'+shot('Neo4j Browser에서 위 질의를 실행해 그래프 보기로 본 화면. HYD-01, 구성 요소 셋, 센서 다섯, 상태 변수 다섯과 그 사이의 관계가 보이게.')+'</section>'
+nxt(None,None,7))

names=['준비','1. 읽게 한다','2. 정해 주고 계획 받기','3. 제약 걸기','4. 인스턴스 넣기','5. 조회와 검사','6. 틀린 데이터','7. 검사 되돌려 주기','8. 규칙 시험과 다시 넣기']
bar='<div class="bar"><div class="bar-in"><b>스키마 + 인스턴스 → Cypher → 그래프 DB</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-02-2-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 const ok=b.dataset.to==='db'?'복사했습니다. Neo4j Browser의 입력 칸에 붙여넣고 실행 단추를 누르세요.':'복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.';
 try{await navigator.clipboard.writeText(text);say(ok)}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 설계한 지식을 그래프 DB에 구현하기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
for w in ('가상','시뮬레이션','Claude','/Users/','/private/'): assert w not in re.sub(r'냉각 효율 \(가상\)','',doc), w
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창과 웹 브라우저 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
