"""통합반 오프라인 02회차 실습 4 「설비 지식에 안전한 작업 절차 연결하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다.
시작/결과/ 는 02회차 실습 1의 완성본이다. 가이드의 표와 그림의 값은 시작/ · 기록/ · 완성/ 의 파일에서 읽어 옮긴다.
실행: python3 production/labs/_old/도구/가이드_만들기_통합반_오프라인_02회차_실습4.py
"""
import re, html, json, os
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R=LAB+'/통합반_오프라인/02회차_실습4_작업_절차_연결/'
css=re.search(r'<style>(.*?)</style>',open(LAB+'/도구/디자인_샘플.html',encoding='utf-8').read(),re.S).group(1)
css+='''
.step{display:none}.step.on{display:block}
.track i{cursor:pointer}
.hero h1 small{display:block;font-size:15px;font-weight:700;color:var(--sub);letter-spacing:0;margin-bottom:6px}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0 0}
.flow div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 14px;font-size:14.5px;line-height:1.55;position:relative}
.flow b{display:block;font-size:15.5px;margin-bottom:4px}
.flow.six{grid-template-columns:repeat(3,1fr)}
.flow em{font-style:normal;display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:var(--accent);color:#fff;font-weight:800;font-size:13px;margin-bottom:8px}
.sect{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px;margin-bottom:72px}
.sect h2{font-size:20px;margin:0 0 10px}
.sect p{margin:0 0 12px;font-size:16px;color:#333b47}
.tree{font-family:Consolas,"D2Coding",monospace;font-size:14.5px;line-height:1.9;background:#14181f;color:#e8edf5;border-radius:14px;padding:18px 22px;white-space:pre;overflow:auto}
.tree span{color:#8fb4ff}.tree i{color:#8a94a3;font-style:normal}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
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
.csv{font-family:Consolas,"D2Coding",monospace;font-size:13.5px;line-height:1.85;background:#14181f;color:#e8edf5;border-radius:14px;padding:16px 20px;white-space:pre;overflow:auto;margin:14px 0}
.csv mark{background:#5a4a00;color:#ffe680;padding:0 2px;border-radius:3px}
@media(max-width:760px){.flow,.flow.six,.two,.vs,.four{grid-template-columns:1fr}}
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
ICO={'chat':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#6a3fd1"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6a3fd1"/></svg>',
'explorer':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#2f5bea"/></svg>',
'editor':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="12" y="3" width="9" height="16" rx="2" fill="#2f5bea"/></svg>'}
def where(k,label): return f'<span class="where {"w-chat" if k=="chat" else "w-code"}">{ICO[k]}{label}</span>'
cid=[0]
def copy(text,head='Copilot에게 보낼 요청',pre=False,rich=None):
    cid[0]+=1; i=f'c{cid[0]}'
    body=rich if rich else e(text)
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}" id="{i}">{body}</div><div class="copy-foot">붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸</div></div>'
shots=[]
def shot(desc):
    shots.append(desc); n=len(shots)
    return f'<div class="shot"><div><b>사진 {n} — 찍어 주실 화면</b><span>{desc}</span></div></div>'
def write(i,ph): return f'<textarea id="{i}" data-draft="{i}" placeholder="{e(ph)}"></textarea><div class="wfoot"><button data-copy="{i}">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸 · 쓴 글은 이 브라우저에 저장된다</span></div>'
def do(n,k,label,title,body): return f'<section class="do" data-n="{n}">{where(k,label)}<h2>{title}</h2>{body}</section>'
def hero(no,title,lead,facts): return f'<section class="hero"><div class="no">{no}</div><h1>{title}</h1><p>{lead}</p><div class="facts">'+''.join(f'<div><small>{a}</small>{b}</div>' for a,b in facts)+'</div></section>'
def mapbox(k,title,text): return f'<section class="map"><div>{vs(k)}</div><div><h2>{title}</h2>{text}</div></section>'
def nxt(i,label,prev=None):
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 절차의 조건까지 담은 결과/schema.json 과 결과/graph.json, 고장 유형에서 조건까지 따라가는 따라가기.py 와 그 결과 결과/조치_조건.md</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
J=lambda p: json.load(open(R+p,encoding='utf-8'))
def term(text,head='VS Code 터미널에 칠 명령'):
    cid[0]+=1; i=f'c{cid[0]}'
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text" id="{i}" style="font-family:Consolas,monospace">{e(text)}</div><div class="copy-foot">치는 곳 → VS Code 아래쪽 터미널 (메뉴 「터미널 → 새 터미널」)</div></div>'
def out(text): return '<div class="csv" style="white-space:pre-wrap">'+text+'</div>'
def richpre(text,cls):
    ps=text.split('\n\n'); assert len(ps)==len(cls),(len(ps),cls)
    return '\n\n'.join(f'<span class="p-{c}">{e(p)}</span>' for p,c in zip(ps,cls))
def parts(*abc): return '<div class="parts">'+''.join(f'<div class="{k}"><b>{t}</b>{d}</div>' for k,(t,d) in zip('abc',abc))+'</div>'

# ── 시작/ · 기록/ · 완성/ 의 파일에서 옮기는 값 ──
S0=J('시작/결과/schema.json'); G0=J('시작/결과/graph.json')
S3=J('기록/3_schema_after.json'); G4=J('기록/4_graph_after.json')
S=J('완성/결과/schema.json'); G=J('완성/결과/graph.json')
assert S==S3 and G==G4   # 5단계 뒤로는 두 파일이 바뀌지 않는다
RULE=open(R+'시작/.github/copilot-instructions.md',encoding='utf-8').read()
DOC=open(R+'시작/문서/HM-8_쿨러팬_정비매뉴얼.md',encoding='utf-8').read()
dim=lambda t: f'<span style="color:var(--sub)">{t}</span>'
cls=lambda Sx: {c['name']:c for c in Sx['classes']}
rel=lambda Sx: {r['type']:r for r in Sx['relationships']}
cnt=lambda Gx,L: sum(1 for n in Gx['nodes'] if n['labels'][0]==L)
rc=lambda Gx,T: sum(1 for r in Gx['rels'] if r['type']==T)
node=lambda Gx,i: next(n['props'] for n in Gx['nodes'] if n['props']['id']==i)
FM=next(n['props'] for n in G['nodes'] if n['labels'][0]=='FailureMode')
skills=sorted([n['props'] for n in G['nodes'] if n['labels'][0]=='Skill'],key=lambda p:p['sop_id'])
conds=[n['props'] for n in G['nodes'] if n['labels'][0]=='Condition']
KINDS=next(p['values'] for p in cls(S)['Condition']['properties'] if p['name']=='kind')
assert KINDS==['전제 조건','안전 조건','금지 사항']
for k in KINDS: assert f'`{k}`' in RULE
conds.sort(key=lambda c: KINDS.index(c['kind']))
sk_of=lambda cid_: [node(G,r['a']) for r in G['rels'] if r['type']=='HAS_CONDITION' and r['b']==cid_]
co_of=lambda sid: [node(G,r['b']) for r in G['rels'] if r['type']=='HAS_CONDITION' and r['a']==sid]
fmrel=lambda sid: next(r['type'] for r in G['rels'] if r['b']==sid and r['a']==FM['id'])
for c in conds: assert c['text'] in DOC, c
SOPS=re.findall(r'^### (SOP-[A-Z0-9-]+) (.+)$',DOC,re.M); assert len(SOPS)==7
old_skill=next(n['props'] for n in G0['nodes'] if n['labels'][0]=='Skill')
remote=next(c for c in conds if 'REMOTE_AUTO' in c['text']); assert len(sk_of(remote['id']))==3
load60=next(c for c in conds if '60 %' in c['text']); assert len(sk_of(load60['id']))==2
h24=next(c for c in conds if '24시간' in c['text']); loto=next(c for c in conds if 'LOTO' in c['text'])
nocond=[s for s in skills if not co_of(s['id'])]; assert len(nocond)==1
newconv=S['conventions'][len(S0['conventions']):]
assert S['conventions'][:len(S0['conventions'])]==S0['conventions']
KC={'전제 조건':('#eaf0ff','#2f5bea'),'안전 조건':('#e9f6ee','#1f8a4c'),'금지 사항':('#fdecec','#b3261e')}

def target_fig():
    ys={s['id']:34+i*64 for i,s in enumerate(skills)}; yc={c['id']:34+i*64 for i,c in enumerate(conds)}
    H=34+5*64
    o=f'<div class="fig"><svg viewBox="0 0 860 {H}" role="img" aria-label="고장 유형에서 조치를 거쳐 조건까지"><defs><marker id="ta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#8a94a3"/></marker></defs><g font-size="12" text-anchor="middle">'
    fy=H/2
    o+=f'<rect x="6" y="{fy-30}" width="150" height="60" rx="30" fill="#fff" stroke="#8a94a3"/><text x="81" y="{fy-4}" font-weight="700" fill="#333b47">{e(FM["name"])}</text><text x="81" y="{fy+14}" font-size="11" fill="#5b6573">고장 유형</text>'
    for s in skills:
        y=ys[s['id']]; new=s['id']!=old_skill['id']; t=fmrel(s['id'])
        o+=f'<line x1="156" y1="{fy}" x2="268" y2="{y+22}" stroke="#8a94a3" stroke-width="1.4" {"" if t=="MITIGATED_BY" else "stroke-dasharray=\"5 4\""} marker-end="url(#ta)"/>'
        o+=f'<rect x="270" y="{y}" width="230" height="44" rx="10" fill="{"#fff8d6" if new else "#fff"}" stroke="{"#c9a400" if new else "#8a94a3"}"/><text x="385" y="{y+18}" font-weight="700" fill="#333b47">{e(s["name"])}</text><text x="385" y="{y+35}" font-size="11" fill="#5b6573">{s["sop_id"]}</text>'
        for c in co_of(s['id']):
            o+=f'<line x1="500" y1="{y+22}" x2="598" y2="{yc[c["id"]]+22}" stroke="{KC[c["kind"]][1]}" stroke-width="1.4" marker-end="url(#ta)"/>'
    for c in conds:
        y=yc[c['id']]; bg,fg=KC[c['kind']]
        o+=f'<rect x="600" y="{y}" width="254" height="44" rx="8" fill="{bg}" stroke="{fg}"/><text x="727" y="{y+18}" font-weight="700" fill="{fg}">{e(c["name"])}</text><text x="727" y="{y+35}" font-size="11" fill="#333b47">{c["kind"]} · {c["source"]}</text>'
    o+=f'</g></svg><p>완성 폴더의 <code>graph.json</code>을 그린 것이다. 흰 상자 「{e(old_skill["name"])}」만 지난 시간에 있었고, 노란 조치 넷과 오른쪽 조건 다섯, 그 사이의 선이 오늘 더하는 것이다. 실선은 <code>MITIGATED_BY</code>, 점선은 <code>REMEDIED_BY</code>다. 조건의 이름과 식별자는 사람마다 다르게 나올 수 있다.</p></div>'
    return o

def prop_vs_node_fig():
    three=sk_of(remote['id']); t=e(remote['text'])
    o='<div class="fig"><svg viewBox="0 0 860 250" role="img" aria-label="조건을 속성으로 둘 때와 노드로 둘 때"><defs><marker id="pa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#2f5bea"/></marker></defs><g font-size="12" text-anchor="middle">'
    o+='<text x="200" y="20" font-size="14.5" font-weight="800" fill="#1d2430">조치의 속성으로</text><text x="650" y="20" font-size="14.5" font-weight="800" fill="#1d2430">조건 노드로</text><line x1="430" y1="8" x2="430" y2="244" stroke="#dfe4ec" stroke-width="2" stroke-dasharray="5 5"/>'
    for i,s in enumerate(three):
        y=38+i*68
        o+=f'<rect x="20" y="{y}" width="360" height="56" rx="10" fill="#fff" stroke="#8a94a3"/><text x="200" y="{y+20}" font-weight="700" fill="#333b47">{s["sop_id"]} {e(s["name"])}</text><text x="200" y="{y+40}" font-size="10.5" fill="#b3261e">preconditions: 「{t}」</text>'
        o+=f'<rect x="450" y="{y+6}" width="170" height="44" rx="10" fill="#fff" stroke="#8a94a3"/><text x="535" y="{y+33}" font-weight="700" fill="#333b47">{s["sop_id"]}</text><line x1="620" y1="{y+28}" x2="688" y2="{106+ (i-1)*10}" stroke="#2f5bea" stroke-width="1.5" marker-end="url(#pa)"/>'
    o+=f'<rect x="690" y="78" width="160" height="60" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="770" y="102" font-weight="700" fill="#2f5bea">{e(remote["name"])}</text><text x="770" y="122" font-size="11" fill="#333b47">{remote["kind"]} · {remote["source"]}</text>'
    o+='<text x="200" y="240" font-size="12" fill="#5b6573">같은 문장이 세 번 적힌다. 절 번호를 둘 자리가 없다</text><text x="650" y="240" font-size="12" fill="#5b6573">문장은 한 곳에 있고, 세 조치가 함께 가리킨다</text></g></svg><p>지난 시간에 단가를 부품도 공급사도 아닌 관계에 둔 것과 같은 종류의 판단이다. 매뉴얼이 개정되어 이 문장이 바뀔 때, 왼쪽은 세 곳을 고쳐야 하고 오른쪽은 한 곳만 고치면 된다.</p></div>'
    return o

def cls_table():
    rows=''
    for n in ('Skill','Condition'):
        c=cls(S)[n]; old={p['name'] for p in cls(S0)[n]['properties']} if n in cls(S0) else set()
        ps=[]
        for p in c['properties']:
            t=(f'<b>{p["name"]}</b>' if p.get('required') else p['name'])+' '+dim(e(p['type'])+(' ('+', '.join(p['values'])+')' if p.get('values') else ''))
            ps.append(t if p['name'] in old else f'<mark>{t}</mark>')
        rows+=f'<tr><td><code>{c["name"]}</code><br>{c["label_ko"]}'+('' if n in cls(S0) else '<br><mark>새 클래스</mark>')+f'</td><td>{", ".join(ps)}</td></tr>'
    t='<table class="res"><thead><tr><th>클래스</th><th>속성과 자료형 (굵은 것이 필수, 노란 것이 이번에 더한 것)</th></tr></thead><tbody>'+rows+'</tbody></table>'
    rows=''
    for r in S['relationships']:
        if r['type'] in rel(S0) and r['type']!='MITIGATED_BY': continue
        new=r['type'] not in rel(S0)
        rows+=f'<tr><td><code>{r["type"]}</code>'+('<br><mark>새 관계</mark>' if new else '<br>'+dim('이미 있던 것'))+f'</td><td>{" · ".join(r["from"])} → {" · ".join(r["to"])}</td><td>{r["cardinality"]}</td><td>{e(r["description"])}</td></tr>'
    return t+'<table class="res"><thead><tr><th>관계</th><th>시작 → 끝</th><th>카디널리티</th><th>뜻</th></tr></thead><tbody>'+rows+'</tbody></table>'

count_rows=[('Skill','조치',cnt,'절차 한 편이 노드 하나다. 이미 있던 하나에는 <code>sop_id</code>만 더해졌다'),('Condition','조건',cnt,'문장 하나가 노드 하나다. 같은 뜻의 문장은 하나로 모았다'),('MITIGATED_BY','',rc,'HM-8.5의 세 편'),('REMEDIED_BY','',rc,'HM-8.7의 두 편'),('HAS_CONDITION','',rc,'조치에서 조건으로 가는 선')]
count_table='<table class="res"><thead><tr><th>클래스 · 관계</th><th>고치기 전</th><th>고친 뒤</th><th>까닭</th></tr></thead><tbody>'+''.join(f'<tr><td><code>{k}</code></td><td>{f(G0,k)}</td><td><mark>{f(G,k)}</mark></td><td>{why}</td></tr>' for k,_,f,why in count_rows)+f'<tr><td>노드 전체 · 관계 전체</td><td style="white-space:nowrap">{len(G0["nodes"])} · {len(G0["rels"])}</td><td style="white-space:nowrap"><mark>{len(G["nodes"])} · {len(G["rels"])}</mark></td><td>설비, 센서, 부품, 공급사 쪽은 하나도 바뀌지 않았다</td></tr></tbody></table>'
assert len(G['nodes'])-len(G0['nodes'])==cnt(G,'Skill')-1+cnt(G,'Condition')
assert len(G['rels'])-len(G0['rels'])==rc(G,'MITIGATED_BY')-1+rc(G,'REMEDIED_BY')+rc(G,'HAS_CONDITION')
cond_table='<table class="res"><thead><tr><th>구분</th><th>원문 (<code>text</code>)</th><th>절</th><th>이어진 조치</th></tr></thead><tbody>'+''.join(f'<tr><td><b style="color:{KC[c["kind"]][1]}">{c["kind"]}</b></td><td>{e(c["text"])}<br>{dim("<code>"+c["id"]+"</code>")}</td><td>{c["source"]}</td><td>{"<br>".join(s["sop_id"] for s in sorted(sk_of(c["id"]),key=lambda s:s["sop_id"]))}</td></tr>' for c in conds)+'</tbody></table>'

kind_table='<table class="res"><thead><tr><th>구분</th><th>뜻 (규칙 파일)</th><th>매뉴얼에서 찾을 문장의 모습</th></tr></thead><tbody><tr><td><b>전제 조건</b></td><td>그 조치를 시작하기 전에 성립해 있어야 하는 상태</td><td>「~일 때만 한다」, 「~인지 확인한다」</td></tr><tr><td><b>안전 조건</b></td><td>작업자를 지키려고 먼저 해 두는 조치</td><td>정지, LOCAL 전환, 잠금(LOTO)</td></tr><tr><td><b>금지 사항</b></td><td>그 조치를 하는 동안 어떤 경우에도 하지 않는 일</td><td>「~하지 않는다」, 「~는 쓰지 않는다」</td></tr></tbody></table>'
for s in ('그 조치를 시작하기 전에 성립해 있어야 하는 상태','작업자를 지키려고 먼저 해 두는 조치','그 조치를 하는 동안 어떤 경우에도 하지 않는 일'): assert s in RULE

choices=f'''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>어디까지 담을지</b></td><td><mark>1번 줄</mark> 쿨러 냉각 성능 상실에 쓰는 SOP-COOL-11~15 다섯 편. SOP-FAN-11 · 12는 이을 고장 유형이 그래프에 없어 담지 않는다</td><td>일곱 편을 다 담게 한다. 그러면 팬 쪽 두 편을 어느 고장 유형에 이을지를 내가 정해 주어야 하는데, 매뉴얼에는 그 고장 유형의 이름이 없다</td></tr>
<tr><td><b>조치를 나눌지</b></td><td><mark>2번 줄</mark> 당장 유온을 내리는 세 편은 <code>MITIGATED_BY</code>, 원인을 없애는 두 편은 <code>REMEDIED_BY</code></td><td>다섯 편을 모두 <code>MITIGATED_BY</code>로 잇게 한다. 관계가 하나라 단순하지만, 핀 세척이 팬 최대 운전과 같은 종류의 조치로 보인다</td></tr>
<tr><td><b>조건을 어디에 둘지</b></td><td><mark>3번 줄</mark> 조치의 속성이 아니라 <code>Condition</code> 노드로 두고 <code>HAS_CONDITION</code>으로 잇는다(아래 그림)</td><td>조치의 속성 <code>preconditions</code> · <code>safety_conditions</code> · <code>prohibitions</code>에 문장을 넣게 한다. 새 클래스가 없어 간단하지만 절 번호를 둘 자리가 없다</td></tr>
<tr><td><b>여러 곳에 적힌 문장</b></td><td><mark>4번 줄</mark> 같은 뜻이면 조건은 하나. 원문은 조치가 실린 절의 머리글 문장으로 삼는다</td><td>금지와 제한을 모아 둔 HM-8.8의 문장을 원문으로 삼게 한다. 대상 절차의 번호가 적혀 있다는 장점이 있다</td></tr>
<tr><td><b>구분이 갈리는 문장</b></td><td><mark>5번 줄</mark> 말투가 아니라 뜻으로 가른다. REMOTE_AUTO는 전제 조건, 24시간 이내는 금지 사항</td><td>「24시간 이내로 한다」를 담지 않게 한다. 금지라기보다 운전 한도라고 본다면 그쪽이 맞다</td></tr>
<tr><td><b>어느 조치에 이을지</b></td><td><mark>6번 줄</mark> 그 문장이 말하는 조작을 단계에서 실제로 하는 조치에만. 60 %는 부하를 내리는 두 편에만 잇는다</td><td>60 %를 원격 조치 세 편 모두에 잇게 한다. 빠뜨릴 걱정은 줄지만 부하를 건드리지 않는 조치에도 금지가 붙는다</td></tr>
</tbody></table>'''

P1send=P('1_prompt.txt')
HEAD_SENT='먼저 .github/copilot-instructions.md 를 읽고 그 규칙을 따라 줘. 그다음 결과/schema.json, 결과/graph.json 과 문서 폴더의 매뉴얼을 모두 읽어 줘. 그리고 세 가지를 정리해 줘.'
HEAD_GUIDE='이 폴더의 규칙(.github/copilot-instructions.md)과 결과/schema.json, 결과/graph.json, 문서 폴더의 매뉴얼을 모두 읽어 줘. 그리고 세 가지를 정리해 줘.'
assert P1send.startswith(HEAD_SENT); P1=HEAD_GUIDE+P1send[len(HEAD_SENT):]
P2=P('2_prompt.txt'); P3=P('3_prompt.txt'); P4=P('4_prompt.txt'); P5a=P('5a_prompt.txt'); P5b=P('5b_prompt.txt'); P6=P('6_prompt.txt'); P7=P('7_prompt.txt'); P8=P('여유_prompt.txt'); P9=P('여유2_prompt.txt')
CHK3=P('3_check.txt'); CHKB=P('4_check_손으로_틀리게.txt'); NONE=P('6_run_none.txt')
OUT6=P('6_조치_조건_after.md'); OUT=open(R+'완성/결과/조치_조건.md',encoding='utf-8').read().strip()
assert OUT.startswith(OUT6); TAIL=OUT[len(OUT6):].strip(); assert TAIL.startswith('### 조건별로 본 조치')
G9=J('기록/여유2_graph_after.json')

pages=[]
pages.append(hero('준비','<small>통합반 오프라인 2회차 · 실습 4 · 40분</small>설비 지식에<br>안전한 작업 절차를 잇는다','지난 시간에 만든 그래프에는 「쿨러 냉각 성능 상실」이라는 고장 유형과 「팬 최대 운전」이라는 조치가 선 하나로 이어져 있다. 그런데 그 조치를 언제 써도 되는지, 무엇을 하면 안 되는지는 그래프 어디에도 없다. 그것은 매뉴얼의 작업 절차(SOP)에 문장으로 적혀 있다. 오늘은 그 문장을 뽑아 조치에 이어 붙인다.',[('끝나면 남는 것','조건까지 담은 schema.json · graph.json, 따라가기.py와 그 결과'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna)'),('전제','이 회차의 앞 실습에서 스키마와 그래프를 만들었다'),('준비에 쓰는 시간','약 3분')])
+'<section class="sect"><h2>오늘 만드는 것</h2><p>고장 유형에서 조치로, 조치에서 그 조치의 전제 조건 · 안전 조건 · 금지 사항으로 따라갈 수 있는 자료다. 설비, 센서, 부품 쪽은 건드리지 않고 그 위에 더한다.</p>'+target_fig()+'<p style="margin:18px 0 0">손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과를 매뉴얼의 원문과 맞춰 보는 것이다. 순서는 읽게 한다 → 정해 준다 → 계획을 받는다 → 작게 만들고 확인한다 → 되돌려 준다. 그 사이에 손으로 일부러 틀리게 고쳐 보고(4단계), 규칙에 어긋나는 요청을 보내 본다(5단계).</p></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md      <i>← 이 폴더의 규칙</i>\n├─ <span>문서/</span>\n│  └─ HM-8_쿨러팬_정비매뉴얼.md    <i>← 절차가 적힌 원문</i>\n├─ <span>결과/</span>\n│  ├─ schema.json                  <i>← 앞 실습에서 만든 스키마</i>\n│  └─ graph.json                   <i>← 앞 실습에서 만든 그래프</i>\n└─ 검사.py                         <i>← 결과를 스키마와 원문에 대어 보는 프로그램</i></div><p><code>결과</code>의 두 파일은 이 회차 첫 실습의 완성본이다. 내가 그 실습에서 만든 두 파일이 있으면 바꿔 넣어도 되지만, 이름이 다르면 뒤의 표와 맞지 않는다. <b>완성 폴더</b>도 함께 받았다. 막히면 열어서 내 것과 견준다.</p>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 문서, 결과 세 폴더가 펼쳐져 있고 검사.py가 보이게.'))
+do(2,'editor','VS Code · 편집기','매뉴얼에서 절차 한 편을 직접 읽는다','<p><code>문서/HM-8_쿨러팬_정비매뉴얼.md</code>를 연다. <code>## </code>으로 시작하는 줄이 절이고(HM-8.1 ~ HM-8.8), <code>### SOP-</code>로 시작하는 줄이 절차다. 절차는 일곱 편이다. 그 가운데 HM-8.7의 <code>SOP-COOL-14 쿨러 핀 세척</code> 세 줄과, 맨 끝 HM-8.8 「금지와 제한」 세 줄을 읽는다.</p>'+kind_table+'<p>SOP-COOL-14의 세 단계 가운데 어느 문장이 위의 어느 구분에 드는지, 어디에도 들지 않는 문장은 무엇인지를 짚어 본다. 뒤에서 Copilot이 뽑은 것이 맞는지를 가리는 사람은 나다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일의 세 절을 구분해 읽는다',f'<p><code>.github/copilot-instructions.md</code>를 연다. 「하면 안 되는 것」 여덟 줄과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 5단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」 {RULE.split("## 정해져 있지 않은 것")[1].split("## ")[0].count(chr(10)+"- ")}줄은 규칙이 일부러 비워 둔 자리이고, 2단계에서 내가 채운다.</p>')
+nxt(1,'1. 만들기 전에, 먼저 읽게 한다'))

pages.append(hero('1단계','만들기 전에,<br>먼저 읽게 한다','첫 요청이 「조건을 뽑아서 넣어 줘」이면 Copilot은 매뉴얼을 읽자마자 그래프를 고치기 시작한다. 어느 문장을 조건으로 보았는지, 같은 뜻의 문장을 어떻게 처리했는지는 결과를 뜯어보아야 알 수 있다. 그래서 첫 요청은 <b>읽고, 찾은 문장을 원문 그대로 늘어놓으라</b>는 요청으로 한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','절차 일곱 편과 조건 후보 문장이 채팅에 정리되어 있다'),('아직 없어야 하는 것','바뀐 파일')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에서 방식이 <b>에이전트</b>, 모델이 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>'+copy(P1,pre=True,rich=richpre(P1,'abc'))+parts(('무엇을 읽는가','첫 문단. 규칙, 지난 시간의 두 파일, 매뉴얼. 읽을 대상을 내가 정해 준다.'),('어떤 모양으로 답하는가','가운데 세 줄. 「원문 그대로, 절 번호와 함께」라고 적었다. 뒤에서 내가 매뉴얼과 견주려면 문장이 고쳐 쓰이지 않아야 한다.'),('하지 말 것','마지막 줄. 이 한 줄이 없으면 읽자마자 고치기 시작한다.')))
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분 30초쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 절차 일곱 편의 표, 같은 뜻의 문장을 여러 절에서 모은 부분, 답의 끝에서 「정해 주실 것」을 번호로 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')+f'<div class="find"><div><i>①</i><p style="margin:0"><b>그래프에 이미 있는 절차</b><span>절차 {len(SOPS)}편 가운데 지금 그래프에 조치로 들어 있는 것은 「{e(old_skill["name"])}」 하나다. Copilot이 이것을 어느 절차 번호와 같은 것으로 보았는지, 무엇을 보고 그렇게 판단했다고 하는지 읽는다.</span></p></div><div><i>②</i><p style="margin:0"><b>여러 곳에 적힌 같은 뜻의 문장</b><span>운전 모드가 REMOTE_AUTO여야 한다는 말은 매뉴얼의 몇 군데에 있는가. 편집기에서 매뉴얼을 열고 Ctrl+F로 <code>REMOTE_AUTO</code>를 찾아 Copilot이 든 곳과 수가 맞는지 센다. <code>60 %</code>도 같은 방법으로 센다.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 나에게 되묻는 것</b><span>답의 끝에 「정해 주실 것」이 있다. 몇 가지인지 세어 둔다. 다음 단계에서 이 물음에 내가 답한다.</span></p></div></div><div class="note"><b>되묻는 까닭</b>규칙 파일의 「정해져 있지 않은 것」에 「요청에 없으면 정하지 말고 묻는다」고 적어 두었기 때문이다. 이 줄이 없었다면 같은 뜻의 문장을 몇 개의 조건으로 둘지, 60 % 문장을 어느 조치에 이을지를 AI가 알아서 정했을 것이다.</div><div class="if"><div><b>파일이 바뀌어 버렸다면</b>탐색기의 <code>schema.json</code>이나 <code>graph.json</code> 옆에 바뀌었다는 표시(M)가 붙었으면 요청의 마지막 줄이 빠진 것이다. 채팅의 「실행 취소」로 되돌리거나 완성 폴더가 아닌 <b>시작 폴더의 원래 파일</b>을 다시 받아 넣고 요청을 다시 보낸다.</div><div><b>문장이 원문과 다르게 적혀 있다면</b>「다시 해 줘」라고 하지 않는다. 「SOP-COOL-14의 둘째 문장이 원문과 달라. 원문은 "고압수는 쓰지 않는다."야.」처럼 어디가 어떻게 다른지를 말한다.</div></div>')
+nxt(2,'2. 빈자리를 내가 정하고, 계획부터 받는다',0))

pages.append(hero('2단계','빈자리를 내가 정하고,<br>계획부터 받는다','Copilot이 되물은 것이 이 실습의 본론이다. 같은 문장을 조치마다 복사해 둘지 하나로 두고 함께 가리키게 할지, 「~가 아닐 때 쓰지 않는다」를 전제로 볼지 금지로 볼지에 따라 그래프의 모양이 달라진다. 매뉴얼은 사람이 읽으라고 쓴 글이어서 이런 것을 정해 주지 않는다. <b>요청하는 사람이 정한다.</b>',[('걸리는 시간','약 7분'),('이 단계가 끝나면','내 결정이 반영된 계획이 표로 채팅에 있다'),('아직 없어야 하는 것','바뀐 파일')])
+do(1,'chat','이 화면의 표 → Copilot 채팅','여섯 빈자리마다 어느 쪽으로 정할지 고른다','<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다.</p>'+choices+prop_vs_node_fig()+'<div class="note"><b>처음이라면 그대로 보낸다</b>완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 다만 3번 줄을 속성 쪽으로 바꾸면 6 · 7단계의 절 번호와 「조건별로 본 조치」가 나오지 않는다.</div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (1단계와 같은 대화)','고른 답을 보내고, 계획부터 달라고 한다','<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'+copy(P2,pre=True,rich=richpre(P2,'abc'))+parts(('결정 여덟 가지','번호를 붙여 한 줄에 결정 하나씩 적었다. 7번(식별자와 절차 번호)과 8번(이번에 담지 않는 것)은 표에 없는 줄이다. Copilot도 나도 빠뜨린 것을 번호로 짚을 수 있다.'),('결정마다 붙인 까닭','「이을 고장 유형이 그래프에 없으니」, 「수행 단계라서」처럼 까닭을 붙였다. 까닭을 알면 Copilot이 내가 짚지 않은 문장도 같은 기준으로 가른다.'),('계획 먼저, 표로','마지막 문단. 조건을 한 줄에 하나씩 구분 · 원문 · 절 · 이어지는 조치로 달라고 했다. 이 표가 그대로 내가 매뉴얼과 맞춰 볼 대상이 된다.')))
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 세 가지를 찾는다','<p>Copilot은 파일을 고치지 않고 계획을 내놓는다. 「이렇게 넣겠다」와 「이것은 더 정해 달라」가 함께 온다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 조건을 한 줄에 하나씩 적은 표(구분, 원문, 절, 이어지는 조치)와 끝의 「확인이 필요한 것」이 보이게. 다시 물어 온 항목에 테두리를 얹는다.')+f'<div class="find"><div><i>①</i><p style="margin:0"><b>조건의 표</b><span>조건이 몇 줄인가. 완성 폴더에서는 {len(conds)}줄이다. 줄마다 원문 칸의 문장을 매뉴얼의 그 절에서 찾아 짚는다. 「{e(nocond[0]["name"])}」({nocond[0]["sop_id"]})에는 조건이 한 줄도 없는데, 매뉴얼에서 그 절차의 세 단계를 읽고 정말 없는지 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>다시 물어 온 것</b><span>여덟 가지를 정해 주었는데도 갈리는 곳이 남는다. 예: 「설비를 정지하고 … 잠금(LOTO)을 건다」는 한 문장 안에 시작 전의 상태와 작업자를 지키는 조치가 함께 있다. Copilot이 권하는 답이 붙어 있는지 본다.</span></p></div><div><i>③</i><p style="margin:0"><b>이미 있는 약속과 어긋나는 곳</b><span>지난 시간의 <code>conventions</code>에는 「증상, 고장 유형, 원인, 조치는 id 와 name 만 가진다」는 문장이 있다. 오늘 조치에 절차 번호가 붙으면 이 문장이 맞지 않게 된다. 계획이 이것을 어떻게 하겠다고 했는지 찾는다.</span></p></div></div><div class="note"><b>계획부터 받는 까닭</b>계획을 받지 않고 바로 넣게 했다면, 잠금 문장의 구분이나 24시간 문장을 어느 조치에 이을지는 내가 모르는 사이에 정해져 그래프에 들어갔을 것이다. 안전에 관한 자료일수록 그 결정을 누가 내렸는지가 남아야 한다.</div><div class="if"><div><b>계획 없이 파일부터 고쳤다면</b>요청의 마지막 문단이 빠진 것이다. 「실행 취소」로 되돌리고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.</div><div><b>표의 원문이 매뉴얼과 다르다면</b>지금 말한다. 「조건 표 3번째 줄의 원문이 HM-8.5의 문장과 달라. 글자 그대로 옮겨 줘.」 계획에서 고치는 것이 파일을 고친 뒤에 고치는 것보다 싸다.</div></div>')
+nxt(3,'3. 스키마만 먼저 보완한다',1))

pages.append(hero('3단계','스키마만<br>먼저 보완한다','이제 고치게 한다. 다만 스키마와 그래프를 한꺼번에가 아니라 <code>schema.json</code>에서 멈추게 한다. 조건을 받을 자리(클래스, 속성, 관계)가 내가 정한 대로 생겼는지를 먼저 읽고, 그다음에 그 자리에 매뉴얼의 문장을 넣는다. <b>정의가 먼저이고 데이터가 다음이다.</b>',[('걸리는 시간','약 5분'),('이 단계가 끝나면','결과/schema.json에 조건을 받을 자리가 있다'),('아직 바뀌면 안 되는 것','결과/graph.json')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','계획이 물은 것에 답하고, 범위를 정해 준다','<p>완성 폴더를 만들 때 계획이 물어 온 것은 셋이었다: 잠금 문장의 구분, 24시간 문장을 SOP-COOL-12에도 이을지, 조건의 이름. 내 계획이 다른 것을 물었으면 첫 문단을 그 물음에 맞게 고쳐서 보낸다. 물음마다 「권한 대로」 또는 「이렇게」 한마디면 된다.</p>'+copy(P3,pre=True,rich=richpre(P3,'ac'))+parts(('물음에 대한 답','첫 문단. SOP-COOL-12도 팬을 100 %로 올리지만 24시간 문장은 SOP-COOL-11의 단계에만 적혀 있다. 매뉴얼이 적은 곳에만 잇는 쪽을 골랐다. 반대로 고르려면 「SOP-COOL-12에도 이어 줘」라고 쓴다.'),('',''),('범위','둘째 문단. 고칠 파일과 고치지 않을 파일을 둘 다 적었다.')).replace('<div class="b"><b></b></div>',''))
+do(2,'chat','Copilot 채팅','파일을 고쳐도 되는지 물으면, 경로를 읽고 허용한다','<p>누르기 전에 경로가 <code>결과/schema.json</code>인지 읽는다. <code>graph.json</code>이나 <code>문서</code> 폴더의 파일이 적혀 있으면 허용하지 않는다.</p>'+shot('Copilot이 결과/schema.json을 고치면서 허용을 묻거나 변경을 보여 주는 화면. 파일 경로와 「유지/허용」 버튼이 보이게.'))
+do(3,'editor','VS Code · 편집기','고쳐진 <code>schema.json</code>에서 새 자리를 찾는다',f'<p><code>결과/schema.json</code>을 연다. 아래는 완성 폴더의 것이다. 내 것에도 같은 자리가 있는지 본다.</p>'+cls_table()+f'<p><code>conventions</code>의 끝에는 문장이 {len(newconv)}개 늘었다(완성 폴더 기준). 지난 시간의 {len(S0["conventions"])}문장은 한 글자도 바뀌지 않았다. 늘어난 문장 가운데 아래 둘을 찾아 읽는다.</p><ul class="ask"><li><b>중복 처리</b>{e(next(c for c in newconv if c.startswith("같은 뜻의 문장")))}</li><li><b>어긋나게 된 옛 문장</b>{e(next(c for c in newconv if "id 와 name 만 가진다" in c))}</li></ul><p>둘째 문장은 옛 문장을 지우지 않고 무엇이 달라졌는지를 뒤에 적은 것이다. 규칙 파일의 5번이 그렇게 하라고 정해 두었다.</p>')
+do(4,'editor','VS Code · 터미널','검사를 직접 돌려, 지금은 한 건이 걸리는 것을 본다','<p>메뉴의 「터미널 → 새 터미널」로 아래쪽에 터미널을 열고 아래 명령을 친다. <code>검사.py</code>는 그래프가 스키마의 정의에 맞는지, 문장이 매뉴얼의 글자와 같은지를 대어 보는 프로그램이다.</p>'+term('python 검사.py')+'<p>마지막 두 줄이 아래와 같으면 된다.</p>'+out(e(CHK3))+'<p>틀린 것이 아니다. 스키마에서 절차 번호를 필수로 정했는데 그래프의 조치에는 아직 넣지 않았다는 뜻이다. 스키마가 「이 칸은 반드시 있어야 한다」고 정하면, 그 약속을 어긴 데이터가 이렇게 드러난다. 다음 단계에서 없어진다.</p><div class="if"><div><b>python을 찾을 수 없다고 나오면</b><code>python3 검사.py</code> 또는 <code>py 검사.py</code>로 쳐 본다. 그래도 안 되면 강사에게 알린다.</div><div><b>어긋남이 0건이거나 여러 건이면</b>0건이면 <code>sop_id</code>가 필수가 아닌 쪽으로 정해진 것이고, 문제없다. 여러 건이면 줄마다 어느 노드의 무엇인지를 읽고, 그 줄을 그대로 채팅에 붙여 까닭을 묻는다.</div></div>')
+nxt(4,'4. 그래프에 잇고, 원문과 맞춘다',2))

pages.append(hero('4단계','그래프에 잇고,<br>원문과 맞춘다','자리가 생겼으니 매뉴얼의 문장을 넣는다. 넣은 뒤에는 두 가지로 확인한다. 프로그램이 대어 보는 것(스키마에 맞는가, 글자가 원문과 같은가)과 사람이 보아야 하는 것(이 문장이 정말 이 조치의 조건인가)이다. 그리고 <b>손으로 일부러 틀리게 고쳐</b> 검사가 무엇을 잡아내는지 본다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','결과/graph.json에 조치 다섯과 조건이 이어져 있고 검사가 0건이다'),('맞춰 볼 것','조건의 모든 줄 ↔ 매뉴얼 원문')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','그래프에 더하고, 검사까지 돌리게 한다','<p>이번에는 검사를 Copilot에게 시킨다. 터미널 명령을 실행해도 되는지 물으면, 명령이 <code>python 검사.py</code>인지 읽고 허용한다. 규칙 파일은 이 폴더에서 실행해도 되는 명령을 둘로 묶어 두었다.</p>'+copy(P4,pre=True,rich=richpre(P4,'ac'))+shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 검사.py)와 「허용/계속」 버튼이 보이게. 파일을 고칠 때의 「유지/허용」 물음도 뜬다면 한 장 더.')+'<p>둘째 문단의 「고치기 전에 무엇이 어긋났는지부터 말해 줘」는, 검사에 걸렸을 때 AI가 검사를 통과시키려고 데이터를 조용히 맞춰 버리는 일을 막는다.</p>')
+do(2,'chat','Copilot 채팅 · 답','늘어난 수가 계획과 맞는지 본다','<p>답에 검사 프로그램이 센 수가 있다. 아래는 완성 폴더의 수다. 내 계획의 표에서 조치, 조건, 관계를 세어 둔 수와 맞는지 본다.</p>'+count_table)
+do(3,'editor','VS Code · 편집기 (좌우로 나란히)','조건을 한 줄씩 매뉴얼과 맞춘다',f'<p><code>결과/graph.json</code>을 열고 Ctrl+F로 <code>Condition</code>을 찾는다. 매뉴얼을 오른쪽으로 끌어 나란히 둔다. 아래는 완성 폴더의 조건 {len(conds)}줄이다. 글자가 같은지는 검사가 이미 보았다. 사람이 볼 것은 그 다음이다.</p>'+cond_table+f'<div class="find"><div><i>①</i><p style="margin:0"><b>구분이 맞는가</b><span>줄마다 구분 칸을 가리고 원문만 읽은 뒤, 내가 붙였을 구분과 같은지 본다. 「{e(h24["text"])}」는 금지 사항인가. 내가 2단계에서 그렇게 정했기 때문에 그렇게 들어간 것이다.</span></p></div><div><i>②</i><p style="margin:0"><b>이어진 조치가 맞는가</b><span>「{e(load60["text"])}」는 {" · ".join(s["sop_id"] for s in sorted(sk_of(load60["id"]),key=lambda s:s["sop_id"]))}에만 이어져 있다. 매뉴얼에서 두 절차의 단계를 읽고 부하를 내리는 단계가 정말 있는지, SOP-COOL-11에는 없는지 본다.</span></p></div><div><i>③</i><p style="margin:0"><b>빠진 문장이 없는가</b><span>반대 방향으로도 본다. 매뉴얼의 HM-8.5, HM-8.7, HM-8.8을 위에서부터 읽으며 「~하지 않는다」, 「~일 때만」으로 끝나는 문장이 표의 어느 줄에 들어갔는지 짚는다. 어디에도 없는 문장은 같은 뜻의 다른 문장에 모인 것인지, 정말 빠진 것인지 가린다.</span></p></div></div>'+shot('결과/graph.json과 문서/HM-8_쿨러팬_정비매뉴얼.md를 좌우로 나란히 연 VS Code 화면. graph.json 쪽은 Condition 노드 다섯 줄이, 매뉴얼 쪽은 HM-8.5가 보이게.'))
+do(4,'editor','VS Code · 편집기 → 터미널','숫자 하나를 손으로 틀리게 고쳐 본다',f'<p>검사가 통과했다는 말을 믿어도 되는지는, 틀린 것을 넣었을 때 걸리는지를 보아야 안다. <code>결과/graph.json</code>에서 「{e(h24["text"])}」의 <code>24</code>를 <code>48</code>로 고치고 저장한다(Ctrl+S). 누군가 옮겨 적다가 숫자를 잘못 친 경우다. 그다음 터미널에서 검사를 돌린다.</p>'+term('python 검사.py')+out(e(CHKB))+'<p>어느 노드의 어느 칸이 어느 절의 글자와 다른지가 한 줄에 나온다. 확인했으면 편집기에서 Ctrl+Z로 되돌리고 저장한 뒤, 검사를 한 번 더 돌려 <code>어긋남 0건</code>인지 본다.</p><div class="note"><b>검사가 보는 것과 보지 못하는 것</b>검사는 문장이 그 절에 글자 그대로 있는지를 본다. 그 문장이 전제인지 금지인지, 그 조치의 조건이 맞는지는 보지 못한다. 그래서 바로 앞의 할 일(사람이 한 줄씩 맞추기)이 따로 있다.</div><div class="if"><div><b>되돌린 뒤에도 0건이 아니면</b>고친 곳이 덜 돌아간 것이다. 검사가 낸 줄의 글자를 매뉴얼의 그 절에서 복사해 그대로 붙여넣고 저장한다.</div><div><b>Copilot의 검사가 처음부터 0건이 아니었다면</b>답에 무엇이 어긋났다고 적혀 있는지 읽는다. 원문과 글자가 다른 것이면 「그 문장을 매뉴얼의 글자 그대로 다시 옮겨 줘」라고 말한다.</div></div>')
+nxt(5,'5. 규칙을 일부러 건드려 본다',3))

pages.append(hero('5단계','규칙을 일부러<br>건드려 본다','지금까지 Copilot은 규칙 안에서 움직였다. 안전에 관한 자료에서 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 현장에서는 누구나 「이건 당연한 거니까 넣어 줘」, 「급하니까 이번만 빼 줘」라고 말하게 된다. 그 말을 지금 일부러 해 본다. <b>보내기 전에, 들어줄지 멈출지 먼저 짐작해 둔다.</b>',[('걸리는 시간','약 4분'),('이 단계가 끝나면','Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'),('바뀌면 안 되는 것','결과/graph.json, 문서 폴더')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','매뉴얼에 없는 안전 조건을 넣어 달라고 해 본다','<p>압축공기로 세척할 때 보호 안경을 쓰는 것은 옳은 말이다. 다만 이 매뉴얼에는 그 문장이 없다.</p>'+copy(P5a,'Copilot에게 보낼 요청 (규칙에 어긋난다)')+shot('위 요청에 Copilot이 조건을 더하지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 길을 제안하는 부분에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>파일이 그대로인가</b><span>탐색기에서 <code>graph.json</code> 옆의 표시가 새로 바뀌지 않았는지 보고, 파일 안에서 <code>보호 안경</code>을 찾아 없는지 확인한다.</span></p></div><div><i>②</i><p style="margin:0"><b>어느 규칙을 들었는가</b><span>답에 규칙의 번호나 문장이 적혀 있다. 번호를 적어 둔다.</span></p></div><div><i>③</i><p style="margin:0"><b>멈추기만 했는가</b><span>안 된다고만 하지 않고, 이 조건을 담으려면 무엇이 먼저 되어야 하는지를 내놓았는가.</span></p></div></div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','급하다며 조건 하나를 빼 달라고 해 본다','<p>이번에는 넣는 것이 아니라 빼는 쪽이다. 「이번만」, 「나중에 다시 넣을게」라는 말을 붙였다.</p>'+copy(P5b,'Copilot에게 보낼 요청 (규칙에 어긋난다)')+f'<p>답이 오면 <code>graph.json</code>에서 <code>HAS_CONDITION</code>을 찾아 {rc(G,"HAS_CONDITION")}줄(완성 폴더 기준) 그대로인지 센다. 터미널에서 <code>python 검사.py</code>를 돌려 관계의 수를 보아도 된다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p><ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」의 한 줄이다. 괄호 안에 「보호구 착용 등」이라는 말이 든 줄을 찾는다. 몇 번인가.</li><li><b>둘째 요청</b>두 줄에 걸린다. 한 줄은 한번 넣은 조건과 관계를 지우는 일을, 다른 한 줄은 「이번만」이라는 예외를 막는다. 몇 번과 몇 번인가.</li></ul><p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p><div class="note"><b>그래프에서 지운다고 현장이 달라지지 않는다</b>조건을 그래프에서 빼도 매뉴얼의 문장은 그대로다. 달라지는 것은 그래프뿐이고, 이 그래프를 읽는 사람이나 프로그램은 그 조치에 조건이 없다고 잘못 알게 된다. 조건을 바꾸는 길은 매뉴얼을 개정하고, 개정된 문장을 다시 옮기는 것이다. 보호 안경도 마찬가지다.</div><div class="if"><div><b>멈추지 않고 고쳐 버렸다면</b>채팅의 「실행 취소」로 되돌리거나 편집기에서 더해진 줄을 지우고 저장한다. 그다음 「규칙 파일을 다시 읽고, 방금 한 일이 규칙에 맞는지 말해 줘」라고 보낸다. 이 일이 있었다는 것을 강사에게 알린다.</div><div><b>「확인해 주면 하겠다」고 되묻는다면</b>오늘은 확인해 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 밀어붙이면 풀릴 수 있다. 그래서 4단계의 검사처럼 글자를 대어 보는 장치를 따로 둔다.</div></div>')
+nxt(6,'6. 고장 유형에서 조건까지 따라가 본다',4))

pages.append(hero('6단계','고장 유형에서<br>조건까지 따라가 본다','이어 붙인 까닭은 따라가기 위해서다. 「쿨러 냉각 성능 상실」에서 출발해 관계를 두 번 건너면 조치마다의 전제와 금지가 모인다. 앞 실습에서는 그래프 DB에 질의를 보내 이런 길을 따라갔다. 여기서는 같은 일을 하는 작은 프로그램을 만들게 한다. <b>프로그램은 조건을 알지 못하고, 실행할 때마다 그래프를 읽는다.</b>',[('걸리는 시간','약 4분'),('이 단계가 끝나면','따라가기.py와 결과/조치_조건.md가 있다'),('바뀌면 안 되는 것','결과/graph.json')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','무엇을 보려는지 말하고, 보이는 모양을 정해 준다','<p>파일 이름, 실행하는 법, 결과가 쓰이는 곳은 규칙 파일이 정해 두었다. 규칙이 비워 둔 것은 「어떤 순서와 모양으로 보일지」이고, 그것을 내가 정해 보낸다.</p>'+copy(P6,pre=True,rich=richpre(P6,'abc'))+parts(('무엇을 왜 보려는가','첫 문단. 누가 언제 쓰는지를 말했다. 조치를 고르기 전에 보는 것이므로 조치마다 묶여 나와야 한다.'),('보이는 순서와 모양','번호 넷. 3번(조건이 없는 조치도 뺴지 않는다)과 4번(없는 고장 유형을 받았을 때)은 정상이 아닌 경우를 미리 정해 준 것이다.'),('한 번 돌려 보기','마지막 줄. 만들기만 하고 끝내지 않게 한다.')).replace('뺴','빼'))
+do(2,'chat','Copilot 채팅 · 답 → 편집기','결과를 읽는다','<p><code>결과/조치_조건.md</code>를 연다. 아래는 완성 폴더를 만들 때 이 단계에서 나온 결과다.</p>'+out(e(OUT6))+f'<div class="find"><div><i>①</i><p style="margin:0"><b>조건이 없는 조치</b><span>{nocond[0]["sop_id"]} 아래에 「그래프에 이어진 조건 없음」이 있다. 「조건이 없다」가 아니라 「그래프에 이어진 것이 없다」고 적게 했다. 매뉴얼에 적히지 않았을 뿐 현장에 조건이 없다는 뜻은 아니기 때문이다.</span></p></div><div><i>②</i><p style="margin:0"><b>Copilot이 스스로 정한 것</b><span>요청에 적지 않은 것(같은 구분 안의 순서, 없는 고장 유형을 받았을 때 결과 파일을 어떻게 할지 등)을 어떻게 정했는지 답에 밝혔는가.</span></p></div></div>')
+do(3,'editor','VS Code · 터미널','입력을 바꿔 직접 돌려 본다','<p>그래프에 없는 고장 유형을 넣어 본다. 프로그램이 지어내지 않고 없다고 말하는지를 보는 것이다.</p>'+term('python 따라가기.py fm:none')+out(e(NONE))+'<p>인자 없이 <code>python 따라가기.py</code>도 돌려 본다. 지금은 고장 유형이 하나뿐이라 결과가 같다. 그래프에 고장 유형이 늘면 프로그램을 고치지 않아도 그만큼 절이 늘어난다.</p><div class="if"><div><b>프로그램 안에 조건 문장이 적혀 있다면</b><code>따라가기.py</code>를 열어 <code>REMOTE_AUTO</code>를 찾는다. 나오면 규칙에 어긋난다. 「조건의 문장을 프로그램에 적지 말고 graph.json 에서 읽게 고쳐 줘」라고 말한다.</div><div><b>다른 이름의 파일이 생겼다면</b>규칙이 정한 것은 <code>따라가기.py</code>와 <code>결과/조치_조건.md</code> 둘이다. 다른 파일은 지우고 그 이름으로 다시 만들게 한다.</div></div>')
+nxt(7,'7. 아쉬운 곳을 찾아 되돌려 준다',5))

pages.append(hero('7단계','아쉬운 곳을 찾아<br>되돌려 준다','처음 나온 결과가 끝이 아니다. 써 보면 아쉬운 곳이 보이고, 그것을 AI에게 정확히 되돌려 주는 것이 바이브 코딩의 나머지 절반이다. 「좀 더 보기 좋게 해 줘」는 되돌려 주기가 아니다. <b>무엇이, 왜, 어디를, 어디까지</b>를 말한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','내가 짚은 곳이 고쳐진 결과가 있다'),('바뀌면 안 되는 것','결과/schema.json, 결과/graph.json')])
+do(1,'editor','VS Code · 편집기','결과에서 아쉬운 곳을 하나 고른다',f'<p><code>결과/조치_조건.md</code>를 다시 읽는다. 아래는 거리의 예다. 내가 찾은 다른 곳이 있으면 그것을 써도 된다.</p><ul class="ask"><li><b>같은 문장이 세 번 나온다</b>REMOTE_AUTO 전제 조건이 조치 셋에 똑같이 적혀 있다. 조건 노드 하나를 세 조치가 함께 가리키는 것인지, 문장만 같은 노드 셋인지 결과만 보아서는 알 수 없다.</li><li><b>조건 쪽에서 볼 수 없다</b>매뉴얼에서 60 % 문장이 개정되면 어느 조치를 다시 보아야 하는가. 지금 결과는 조치에서 조건으로만 읽힌다.</li><li><b>조치의 수가 한눈에 안 보인다</b>고장 유형 아래에 완화하는 조치가 몇 편이고 원인을 없애는 조치가 몇 편인지 세어야 안다.</li></ul><div class="vs"><div class="bad"><b>막연하게</b><q>결과가 좀 헷갈려. 보기 좋게 정리해 줘.</q>무엇이 헷갈리는지 AI가 짐작해야 한다. 조건의 문장을 줄여 쓰거나 표로 바꾸는 식으로, 내가 바라지 않은 곳까지 바뀐다.</div><div class="good"><b>구체적으로</b><q>REMOTE_AUTO 조건이 세 곳에 되풀이돼서 노드 하나인지 알 수 없어(무엇이). 조건이 바뀌면 어느 조치를 다시 봐야 하는지 알고 싶어(왜). 따라가기.py 를 고쳐서 뒤에 절을 하나 더해 줘(어디를). 앞부분과 graph.json 은 그대로 둬(어디까지).</q></div></div>')
+do(2,'chat','이 화면의 글 칸 → Copilot 채팅 (같은 대화)','네 가지를 넣어 직접 써서 되돌려 준다','<p>오늘 직접 쓰는 요청은 이것 하나다. 무엇이, 왜, 어디를, 어디까지. 네 가지를 넣어 내 말로 쓴다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다.</p>'+write('w7','무엇이 아쉬운지, 왜 아쉬운지(무엇을 알고 싶은지), 어느 파일의 어디를 고칠지, 건드리지 말 곳을 적는다.')+'<details><summary>다 쓴 뒤에 견주어 볼 예</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">정답이 아니라 한 가지 예다. 첫째와 둘째 거리를 함께 고른 경우의 글이고, 완성 폴더는 이 글을 보내 만든 것이다. 내 글에 네 가지가 다 들어 있는지를 보는 데 쓴다.</p>'+copy(P7,'Copilot에게 보낼 요청 (예)',pre=True)+'</details><p style="margin-top:18px">고친 뒤에는 결과의 앞부분이 그대로인지, <code>graph.json</code>과 <code>schema.json</code>에 바뀌었다는 표시가 새로 붙지 않았는지를 본다. 완성 폴더에서는 결과의 끝에 아래 절이 더해졌다.</p>'+out(e(TAIL))+f'<p>한 줄이 조건 노드 하나다. REMOTE_AUTO 줄에 절차 번호가 {len(sk_of(remote["id"]))}개 붙어 있으면 노드 하나를 세 조치가 함께 가리킨다는 뜻이다. 2단계에서 조건을 속성이 아니라 노드로 두기로 한 결정이 여기에서 쓸모를 드러낸다.</p>'+shot('되돌려 준 뒤 Copilot이 따라가기.py의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색으로 표시된 화면).')+'<div class="if"><div><b>요청하지 않은 곳까지 바뀌었다면</b>「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.</div><div><b>Copilot이 되물었다면</b>요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 되묻지 않고 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다.</div></div>')
+'<section class="sect"><h2>시간이 남으면: 완료를 확인하는 기준도 잇는다</h2><p>SOP의 구성요소는 여덟 가지이고 오늘은 그 가운데 셋을 담았다. 「끝났다고 보는 기준」도 같은 방식으로 담을 수 있다. 다만 규칙 파일의 이름 표에는 이것을 받을 이름이 없고, 조건의 구분은 셋뿐이라고 정해져 있다. 아래 요청을 보내고 Copilot이 바로 만드는지, 멈추는지를 본다.</p>'+copy(P8)+f'<p>완성 폴더를 만들 때는 파일을 고치지 않고 새 클래스와 관계의 이름을 제안하며 세 가지를 물어 왔다. 규칙 파일의 「표에 없는 이름이 필요하면 … 제안하고 확인을 받는다」는 줄 때문이다. 물음을 읽고 답을 보내면 그래프에 완료 기준이 더해진다. 아래는 그때 보낸 답이다. 내 물음이 다르면 그에 맞게 고쳐 쓴다.</p>'+copy(P9,'Copilot에게 보낼 요청 (예)')+f'<p style="margin:0">끝나면 검사가 0건인지 본다. 그때의 결과에서는 노드가 {len(G["nodes"])}개에서 {len(G9["nodes"])}개로, 관계가 {len(G["rels"])}개에서 {len(G9["rels"])}개로 늘었고, 완화하는 조치 세 편이 HM-8.6의 회복 판정 문장 하나를 함께 가리켰다. 이 과제의 결과는 완성 폴더에 들어 있지 않다.</p></section>'
+nxt(None,None,6))

names=['준비','1. 읽게 한다','2. 고르고 계획 받기','3. 스키마 보완','4. 그래프에 잇기','5. 규칙 시험','6. 따라가 보기','7. 되돌려 주기']
MIN=[3,5,7,5,7,4,4,5]; assert sum(MIN)==40 and len(MIN)==len(names)==len(pages)
for i,p in enumerate(pages): assert f'약 {MIN[i]}분' in p,i
assert sum(p.count('<textarea') for p in pages)==1
full=''.join(pages)
for w in ('가상','시뮬레이션','/Users/','/private/'): assert w not in full,w
bar='<div class="bar"><div class="bar-in"><b>설비 지식 + 작업 절차 → 조건까지 이어진 그래프</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-02-4-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 '+(names.length-1)+'단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 설비 지식에 안전한 작업 절차 연결하기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
