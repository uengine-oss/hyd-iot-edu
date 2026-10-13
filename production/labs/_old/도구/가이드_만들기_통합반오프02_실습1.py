"""통합반 오프라인 02회차 실습 1 「설비 자료로 온톨로지 스키마 완성하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다.
시작/결과/ 는 01회차 실습 2의 완성본이다. 가이드의 표와 그림의 값은 시작/ · 기록/ · 완성/ 의 파일에서 읽어 옮긴다.
실행: python3 production/labs/_old/도구/가이드_만들기_통합반오프02_실습1.py
"""
import re, html, json, os
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R=LAB+'/통합반_오프라인/02회차_실습1_온톨로지_스키마/'
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
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 새 자료에 맞게 보완한 결과/schema.json 과, 그 약속대로 자료를 더한 결과/graph.json. 다음 실습에서 이 두 파일을 그래프 DB에 넣는다</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
J=lambda p: json.load(open(R+p,encoding='utf-8'))

# ── 시작/ · 기록/ · 완성/ 의 파일에서 옮기는 표 ──
S0=J('시작/결과/schema.json'); G0=J('시작/결과/graph.json')     # 지난 시간에 만든 것
S3=J('기록/3_schema_after.json'); G5=J('기록/5_graph_after.json') # 3단계 · 5단계 뒤
S=J('완성/결과/schema.json'); G=J('완성/결과/graph.json')         # 끝난 상태
RULE=open(R+'시작/.github/copilot-instructions.md',encoding='utf-8').read()
dim=lambda t: f'<span style="color:var(--sub)">{t}</span>'
cls=lambda Sx: {c['name']:c for c in Sx['classes']}
rel=lambda Sx: {r['type']:r for r in Sx['relationships']}
cnt=lambda Gx,L: sum(1 for n in Gx['nodes'] if n['labels'][0]==L)
rc=lambda Gx,T: sum(1 for r in Gx['rels'] if r['type']==T)
node=lambda Gx,i: next(n['props'] for n in Gx['nodes'] if n['props']['id']==i)
jd=lambda v: e(json.dumps(v,ensure_ascii=False))

inherit_table=('<table class="res"><thead><tr><th>지난 시간에 만든 것</th><th>들어 있는 것</th><th>새 자료 앞에서 모자란 곳</th></tr></thead><tbody>'
 f'<tr><td>클래스 {len(S0["classes"])}</td><td>'+', '.join(f'<code>{c["name"]}</code>' for c in S0['classes'])+'</td><td>공급사를 받을 클래스가 없다. 설비에는 <code>id</code>와 <code>name</code>뿐이다</td></tr>'
 f'<tr><td>관계 {len(S0["relationships"])}</td><td>'+', '.join(f'<code>{r["type"]}</code>' for r in S0['relationships'][:5])+' 등</td><td>어느 관계에도 <mark>카디널리티</mark>가 없다. 값을 가진 관계도 없다</td></tr>'
 f'<tr><td><code>conventions</code> {len(S0["conventions"])}문장</td><td>식별자를 만드는 규칙, 다른 이름을 <code>aliases</code>에 넣는 규칙, 같은 장치를 노드 하나로 두는 규칙</td><td>새로 들어올 대상의 식별자와 중복 처리 규칙이 없다</td></tr>'
 f'<tr><td><code>graph.json</code></td><td>노드 {len(G0["nodes"])}, 관계 {len(G0["rels"])}</td><td>공급사와 공급 조건이 없다. 한계가 위쪽인지 아래쪽인지는 문장으로만 있다</td></tr>'
 '</tbody></table>')

def cls_table(Sa,Sb,names):
    rows=''
    for n in names:
        c=cls(Sb)[n]; old={p['name'] for p in cls(Sa)[n]['properties']} if n in cls(Sa) else set()
        ps=[]
        for p in c['properties']:
            t=(f'<b>{p["name"]}</b>' if p.get('required') else p['name'])+' '+dim(e(p['type'])+(' ('+', '.join(p['values'])+')' if p.get('values') else ''))
            ps.append(t if p['name'] in old else f'<mark>{t}</mark>')
        rows+=f'<tr><td><code>{c["name"]}</code><br>{c["label_ko"]}'+('' if n in cls(Sa) else '<br><mark>새 클래스</mark>')+f'</td><td>{", ".join(ps)}</td></tr>'
    return '<table class="res"><thead><tr><th>클래스</th><th>속성과 자료형 (굵은 것이 필수, 노란 것이 이번에 더한 것)</th></tr></thead><tbody>'+rows+'</tbody></table>'
def rel_table(Sb):
    rows=''
    for r in Sb['relationships']:
        new=r['type'] not in rel(S0)
        pr=('<br>'+dim('관계의 속성: '+', '.join(p['name'] for p in r['properties']))) if r.get('properties') else ''
        rows+=f'<tr><td><code>{r["type"]}</code>'+('<br><mark>새 관계</mark>' if new else '')+f'</td><td>{" · ".join(r["from"])} → {" · ".join(r["to"])}</td><td><mark>{r["cardinality"]}</mark></td><td>{e(r["description"])}{pr}</td></tr>'
    return '<table class="res"><thead><tr><th>관계</th><th>시작 → 끝</th><th>카디널리티</th><th>뜻</th></tr></thead><tbody>'+rows+'</tbody></table>'
newconv=S3['conventions'][len(S0['conventions']):]
assert S3['conventions'][:len(S0['conventions'])]==S0['conventions']
conv_pick=[c for c in newconv if c.startswith('Supplier 의 접두사') or c.startswith('단가, 불량률')]
assert len(conv_pick)==2
conv_box=''.join(f'<li>{e(c)}</li>' for c in conv_pick)

LABELS=[c['name'] for c in S3['classes']]
count_table=('<table class="res"><thead><tr><th>클래스 · 관계</th><th>고치기 전</th><th>고친 뒤</th><th>까닭</th></tr></thead><tbody>'
 f'<tr><td><code>Supplier</code></td><td>{cnt(G0,"Supplier")}</td><td><mark>{cnt(G5,"Supplier")}</mark></td><td>공급 조건 7줄에 나오는 공급사는 이름이 같으면 노드 하나다</td></tr>'
 f'<tr><td><code>SUPPLIED_BY</code></td><td>{rc(G0,"SUPPLIED_BY")}</td><td><mark>{rc(G5,"SUPPLIED_BY")}</mark></td><td>공급 조건 한 줄이 관계 하나다. 단가, 불량률, 납기는 이 관계의 <code>props</code>에 있다</td></tr>'
 f'<tr><td><code>Component</code></td><td>{cnt(G0,"Component")}</td><td>{cnt(G5,"Component")}</td><td>구성 요소 목록 18줄은 이미 있는 여섯 노드와 같은 대상이다</td></tr>'
 f'<tr><td><code>Sensor</code> · <code>StateVariable</code></td><td style="white-space:nowrap">{cnt(G0,"Sensor")} · {cnt(G0,"StateVariable")}</td><td style="white-space:nowrap">{cnt(G5,"Sensor")} · {cnt(G5,"StateVariable")}</td><td>센서 목록 16줄도 이미 있는 노드와 같은 대상이다</td></tr>'
 f'<tr><td>노드 전체 · 관계 전체</td><td style="white-space:nowrap">{len(G0["nodes"])} · {len(G0["rels"])}</td><td style="white-space:nowrap"><mark>{len(G5["nodes"])} · {len(G5["rels"])}</mark></td><td>늘어난 것은 공급사 {cnt(G5,"Supplier")}과 그 관계 {rc(G5,"SUPPLIED_BY")}뿐이다</td></tr>'
 '</tbody></table>')
assert len(G5['nodes'])-len(G0['nodes'])==cnt(G5,'Supplier') and len(G5['rels'])-len(G0['rels'])==rc(G5,'SUPPLIED_BY')
def added_table():
    rows=''
    old={n['props']['id']:n['props'] for n in G0['nodes']}
    for n in G5['nodes']:
        p=n['props']; o=old.get(p['id'])
        if o is None or o==p: continue
        ch=[]
        for k,v in p.items():
            if k not in o: ch.append(f'<code>{k}</code>: {jd(v)}')
            elif v!=o[k]:
                assert isinstance(v,list) and v[:len(o[k])]==o[k]
                ch.append(f'<code>{k}</code>에 '+', '.join(jd(x) for x in v[len(o[k]):]))
        assert all(k in p for k in o)
        rows+=f'<tr><td><code>{p["id"]}</code><br>{e(p["name"])}</td><td>{"<br>".join(ch)}</td></tr>'
    return '<table class="res"><thead><tr><th>이미 있던 노드</th><th>더해진 값</th></tr></thead><tbody>'+rows+'</tbody></table>'
def sup_table(Gx):
    rows=''
    for r in Gx['rels']:
        if r['type']!='SUPPLIED_BY': continue
        a=node(Gx,r['a']); b=node(Gx,r['b']); p=r['props']
        rows+=f'<tr><td><code>{r["a"]}</code><br>{e(a["name"])}</td><td><code>{r["b"]}</code><br>{e(b["name"])}</td><td>{jd(p["price"])}</td><td>{jd(p["fail_rate"])}</td><td>{jd(p["lead_days"])}</td><td>{jd(b["approved"])}</td></tr>'
    return '<table class="res"><thead><tr><th>a (부품)</th><th>b (공급사)</th><th>price</th><th>fail_rate</th><th>lead_days</th><th>공급사의 approved</th></tr></thead><tbody>'+rows+'</tbody></table>'

# 관계 한 줄에서 값을 찾는다(그림에 쓴다)
def sp(part,sup): return next(r['props'] for r in G5['rels'] if r['type']=='SUPPLIED_BY' and r['a']==part and r['b']==sup)
pa,pb,pc=(sp('part:p-pmp-seal','sup:'+x) for x in 'abc')
sa,sb,sc=(node(G5,'sup:'+x) for x in 'abc')
assert (sa['approved'],sb['approved'],sc['approved'])==(True,True,False)

where_fig=f'''<div class="fig"><svg viewBox="0 0 760 300" role="img" aria-label="단가를 적을 수 있는 세 자리">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6573"/></marker></defs>
<g font-size="12.5" font-weight="700" text-anchor="middle">
<text x="125" y="22" font-size="14.5" font-weight="800" fill="#1d2430">① 부품의 속성으로</text>
<rect x="45" y="44" width="160" height="62" rx="12" fill="#fdecec" stroke="#b3261e"/><text x="125" y="68" fill="#333b47">펌프 축 씰 키트</text><text x="125" y="90" font-weight="400" fill="#b3261e">price: {pa["price"]}? {pb["price"]}? {pc["price"]}?</text>
<text x="125" y="130" font-size="12" font-weight="400" fill="#5b6573">칸은 하나인데 값은 셋이다</text>
<text x="380" y="22" font-size="14.5" font-weight="800" fill="#1d2430">② 공급사의 속성으로</text>
<rect x="300" y="44" width="160" height="62" rx="12" fill="#fdecec" stroke="#b3261e"/><text x="380" y="68" fill="#333b47">A정밀</text><text x="380" y="90" font-weight="400" fill="#b3261e">price: {sp("part:p-pmp-seal","sup:a")["price"]}? {sp("part:p-fan-brg","sup:a")["price"]}? {sp("part:p-clr-core","sup:a")["price"]}?</text>
<text x="380" y="130" font-size="12" font-weight="400" fill="#5b6573">부품마다 값이 다르다</text>
<text x="635" y="22" font-size="14.5" font-weight="800" fill="#1d2430">③ 관계의 속성으로</text>
<rect x="555" y="44" width="160" height="62" rx="12" fill="#e9f6ee" stroke="#1f8a4c"/><text x="635" y="68" fill="#1f8a4c">부품 → 공급사</text><text x="635" y="90" font-weight="400" fill="#333b47">짝마다 값 하나</text>
<text x="635" y="130" font-size="12" font-weight="400" fill="#5b6573">아래 그림</text>
<line x1="20" y1="150" x2="740" y2="150" stroke="#dfe4ec" stroke-width="2" stroke-dasharray="5 5"/>
<rect x="40" y="200" width="170" height="44" rx="22" fill="#fff" stroke="#8a94a3"/><text x="125" y="227" fill="#333b47">펌프 축 씰 키트</text>
<rect x="560" y="166" width="170" height="34" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="645" y="188" fill="#2f5bea">A정밀</text>
<rect x="560" y="206" width="170" height="34" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="645" y="228" fill="#2f5bea">B-OEM</text>
<rect x="560" y="246" width="170" height="34" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="645" y="268" fill="#2f5bea">C트레이딩</text>
<g font-weight="400" font-size="12" fill="#333b47"><rect x="318" y="163" width="150" height="22" rx="6" fill="#fff"/><text x="393" y="179">단가 {pa["price"]} · 납기 {pa["lead_days"]}일</text><rect x="318" y="211" width="150" height="22" rx="6" fill="#fff"/><text x="393" y="227">단가 {pb["price"]} · 납기 {pb["lead_days"]}일</text><rect x="318" y="259" width="150" height="22" rx="6" fill="#fff"/><text x="393" y="275">단가 {pc["price"]} · 납기 {pc["lead_days"]}일</text></g></g>
<g stroke="#5b6573" stroke-width="1.6" marker-end="url(#ar)"><line x1="210" y1="214" x2="316" y2="176"/><line x1="210" y1="222" x2="316" y2="222"/><line x1="210" y1="230" x2="316" y2="268"/></g>
<g stroke="#5b6573" stroke-width="1.6" marker-end="url(#ar)"><line x1="468" y1="176" x2="558" y2="182"/><line x1="468" y1="222" x2="558" y2="223"/><line x1="468" y1="268" x2="558" y2="264"/></g>
</svg><p>단가는 부품의 것도 공급사의 것도 아니고 「이 부품을 이 공급사에서 살 때」의 값이다. 그래서 둘을 잇는 관계에 적는다. 지난 시간의 <code>graph.json</code>에서 관계마다 비어 있던 <code>"props": {{}}</code>가 이 값을 받는 자리다.</p></div>'''

path_fig=f'''<div class="fig"><svg viewBox="0 0 760 190" role="img" aria-label="둘째 물음의 답이 나오는 길">
<defs><marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6573"/></marker></defs>
<g font-size="12.5" font-weight="700" text-anchor="middle">
<rect x="6" y="70" width="112" height="50" rx="8" fill="#eaf0ff" stroke="#2f5bea"/><text x="62" y="92" fill="#2f5bea">asset:hyd-02</text><text x="62" y="109" font-size="11" font-weight="400" fill="#333b47">code: HYD-02</text>
<rect x="212" y="70" width="136" height="50" rx="25" fill="#fff" stroke="#8a94a3"/><text x="280" y="92" fill="#333b47">comp:main-pump</text><text x="280" y="109" font-size="11" font-weight="400" fill="#333b47">aliases: 유압 펌프 …</text>
<rect x="430" y="70" width="136" height="50" rx="25" fill="#fff" stroke="#8a94a3"/><text x="498" y="92" fill="#333b47">part:p-pmp-seal</text><text x="498" y="109" font-size="11" font-weight="400" fill="#333b47">펌프 축 씰 키트</text>
<rect x="652" y="14" width="102" height="42" rx="8" fill="#e9f6ee" stroke="#1f8a4c"/><text x="703" y="32" fill="#1f8a4c">sup:a</text><text x="703" y="48" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sa["approved"])}</text>
<rect x="652" y="74" width="102" height="42" rx="8" fill="#fff" stroke="#8a94a3"/><text x="703" y="92" fill="#333b47">sup:b</text><text x="703" y="108" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sb["approved"])}</text>
<rect x="652" y="134" width="102" height="42" rx="8" fill="#fdecec" stroke="#b3261e"/><text x="703" y="152" fill="#b3261e">sup:c</text><text x="703" y="168" font-size="11" font-weight="400" fill="#333b47">approved: {jd(sc["approved"])}</text>
<g font-size="10.5" font-weight="400" fill="#5b6573"><text x="165" y="88">HAS_COMPONENT</text><text x="389" y="88">USES_PART</text><text x="604" y="40">price {pa["price"]}</text><text x="612" y="88">price {pb["price"]}</text><text x="604" y="152">price {pc["price"]}</text></g></g>
<g stroke="#5b6573" stroke-width="1.6" marker-end="url(#ar2)"><line x1="118" y1="98" x2="210" y2="98"/><line x1="348" y1="98" x2="428" y2="98"/><line x1="566" y1="86" x2="650" y2="40"/><line x1="566" y1="98" x2="650" y2="96"/><line x1="566" y1="108" x2="650" y2="150"/></g>
</svg><p>둘째 물음의 길을 완성 폴더의 <code>graph.json</code>에서 옮긴 것이다. 설비에서 관계 셋을 따라가 공급사 셋에 닿고, 공급사의 <code>approved</code>로 거른 다음 관계의 <code>price</code>를 견준다. 이 길 가운데 한 군데라도 끊겨 있으면 답이 나오지 않는다.</p></div>'''

def rule_line(start):
    l=next(x for x in RULE.split('\n') if x.startswith(start)); return l
R1=rule_line('1. `자료/`'); R6=rule_line('6. 지난 시간에')
assert '고쳐 달라는 요청을 받아도 고치지 않는다' in R1 and '바꿔 달라는 요청을 받아도 바꾸지 않고' in R6

HEAD='이 폴더의 규칙(.github/copilot-instructions.md)과 결과/schema.json, 결과/graph.json, 자료 폴더의 파일을 모두 읽어 줘.'
tail=P('1_prompt.txt').split('모두 읽어 줘. ',1)[1]
P1=HEAD+' '+tail
a,b=tail.split(' 아직 파일은 고치지 마.')
assert b=='' and a.startswith('읽은 것을 세 가지로')
P1rich=f'<span class="p-a">{e(HEAD)}</span> <span class="p-b">{e(a)}</span> <span class="p-c">아직 파일은 고치지 마.</span>'
P2,P3,P4a,P4b,P5,P6a,P6b,P8=(P(f) for f in ('2_prompt.txt','3_prompt.txt','4a_prompt.txt','4b_prompt.txt','5_prompt.txt','6a_prompt.txt','6b_prompt.txt','여유_prompt.txt'))
def hl(text,*marks):
    h=e(text)
    for s,c in marks:
        assert e(s) in h,s
        h=h.replace(e(s),f'<span class="{c}">{e(s)}</span>')
    return h
P2rich=hl(P2,('바로 고치지 말고, 어떻게 고칠지 단계로 먼저 말해 줘. 내가 확인한 다음에 시작해.','p-c'))
P3rich=hl(P3,('cardinality 는 지금 들어 있는 예제의 수가 아니라 앞으로 있을 수 있는 연결을 기준으로 정한다.','p-b'),('지금은 결과/schema.json 한 파일만 고치고 멈춰. 결과/graph.json 은 아직 고치지 마.','p-c'))
P5rich=hl(P5,('이미 들어 있는 노드와 관계는 지우지 말고, id 도 바꾸지 마.','p-c'),('셋째, 자료의 값을 바꿔 적었거나 여러 줄을 하나로 합쳤거나 버린 곳을 자료의 원래 표현과 함께.','p-b'))
P6rich=hl(P6a,('어느 노드에서 출발해 어느 관계를 따라가 어느 속성에서 답을 읽었는지를 한 줄로 적어 줘.','p-b'),('파일은 고치지 마.','p-c'))
alt=lambda t: f'<q style="display:block;quotes:none;background:#f6f8fa;border-radius:8px;padding:6px 10px;margin:6px 0 0;font-size:14px">{e(t)}</q>'

pages=[]
# ── 준비 ──
pages.append(hero('준비','<small>통합반 오프라인 2회차 · 실습 1 · 40분</small>지난 시간의 schema.json을<br>새 자료로 보완한다','지난 시간에 설비 · 계기 목록을 클래스와 인스턴스로 나누어 <code>schema.json</code>과 <code>graph.json</code>을 만들었다. 오늘은 현장에서 새로 받은 설비 · 구성 요소 · 센서 · 예비품 · 공급 조건 자료를 그 위에 얹는다. 새 자료를 받으려면 속성의 자료형, 식별자, 관계의 방향과 카디널리티, 같은 대상이 두 번 들어가지 않게 하는 규칙을 더 정해야 한다. 파일을 쓰는 일은 Copilot이 하고, <b>무엇을 어디에 둘지는 내가 고른다.</b>',[('끝나면 남는 것','보완한 결과/schema.json, 새 자료를 더한 결과/graph.json'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna)'),('전제','1회차 실습 2를 마쳤고, 온라인 2일차의 스키마 단원을 들었다')])
+'<section class="sect"><h2>오늘 하는 일의 순서</h2><p>손으로 JSON을 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 그 대신 <b>요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과가 자료와 내 결정에 맞는지를 가린다.</b> 여섯 번 요청하고 여섯 번 확인한다.</p><div class="flow six"><div><em>1</em><b>읽게 한다</b>이어받은 것과 새 자료를 읽고 모자란 곳을 말하게 한다</div><div><em>2</em><b>고르고 계획을 받는다</b>되물은 것에 선택지를 골라 답하고 계획부터 듣는다</div><div><em>3</em><b>스키마만 보완한다</b>schema.json 한 파일을 고치게 하고 읽는다</div><div><em>4</em><b>규칙을 시험한다</b>일부러 어긋나는 요청을 보내 멈추는지 본다</div><div><em>5</em><b>자료를 옮긴다</b>새 자료를 graph.json에 더하고 수와 값을 맞춘다</div><div><em>6</em><b>물어 보고 되돌려 준다</b>만든 지식에 질문을 던지고 모자란 곳을 고친다</div></div></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>결과/</span>                    <i>← 지난 시간에 만든 것</i>\n│  ├─ schema.json              <i>← 클래스 '+str(len(S0['classes']))+', 관계 '+str(len(S0['relationships']))+'</i>\n│  └─ graph.json               <i>← 노드 '+str(len(G0['nodes']))+', 관계 '+str(len(G0['rels']))+'</i>\n└─ <span>자료/</span>                    <i>← 이번에 새로 받은 것</i>\n   ├─ 현장_메모.md             <i>← 자료를 보낸 사람의 설명. 먼저 읽는다</i>\n   ├─ 설비_대장.csv            <i>← 설비 3대</i>\n   ├─ 구성요소_목록.csv        <i>← 18줄</i>\n   ├─ 센서_목록.csv            <i>← 16줄</i>\n   ├─ 예비품_목록.csv          <i>← 3줄</i>\n   └─ 공급_조건.csv            <i>← 7줄</i></div><p><code>결과</code> 폴더의 두 파일은 1회차 실습 2의 완성본이다. 지난 시간에 내가 만든 파일이 있으면 그것으로 바꿔 넣어도 된다. 클래스 이름이나 노드의 수가 이 가이드와 달라질 뿐, 하는 일은 같다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다. 완성 폴더는 이 가이드가 권하는 답을 골랐을 때의 결과여서, 다른 선택지를 골랐다면 내 파일이 다르게 나오는 것이 맞다.</p>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 결과, 자료 세 폴더가 펼쳐져 있고 결과 폴더의 schema.json, graph.json이 보이게.'))
+do(2,'editor','VS Code · 편집기','지난 시간에 만든 것에서 모자란 곳을 본다','<p>탐색기에서 <code>결과/schema.json</code>을 눌러 연다. 맨 아래 <code>relationships</code>까지 내려가 관계 한 건을 읽는다. <code>type</code>, <code>from</code>, <code>to</code>, <code>description</code>은 있는데, 한쪽에 몇 개가 이어질 수 있는지를 적는 칸이 없다. 이어서 <code>결과/graph.json</code>의 <code>rels</code>에서 한 줄을 본다. 줄마다 <code>"props": {}</code>가 비어 있다.</p>'+inherit_table)
+do(3,'editor','VS Code · 편집기','새 자료에서 <code>현장_메모.md</code>와 <code>공급_조건.csv</code>를 직접 읽는다','<p><code>자료/현장_메모.md</code>를 끝까지 읽는다. 6절의 「이 정리로 알고 싶은 것」 다섯 가지가 오늘 스키마를 보완하는 기준이다. 이어서 <code>자료/공급_조건.csv</code>를 연다. 지난 시간의 목록에는 없던 자료다.</p><div class="csv">품번,공급사,승인공급사,단가(만원),불량률,납기(일)\n<mark>P-PMP-SEAL</mark>,A정밀 (저가),예,<mark>35</mark>,0.12,2\n<mark>P-PMP-SEAL</mark>,B-OEM (순정),예,<mark>55</mark>,0.02,5\n<mark>P-PMP-SEAL</mark>,C트레이딩 (최저가 · 비승인),<mark>아니오</mark>,<mark>20</mark>,0.30,1\nP-FAN-BRG,A정밀 (저가),예,18,0.10,1\n…</div><ul class="ask"><li><b>같은 부품이 세 줄이다</b>품번은 하나인데 단가가 셋이다. 부품 노드에 <code>price</code> 칸을 하나 두면 어느 값을 적는가.</li><li><b>공급사에는 번호가 없다</b>부품은 품번으로, 센서는 태그로 식별자를 만들었다. 공급사의 식별자는 무엇으로 만드는가.</li><li><b>「예」와 「아니오」</b>승인 여부가 글자로 적혀 있다. 승인 공급사만 고르려면 어떤 자료형이어야 하는가.</li></ul><p>다른 파일은 Copilot에게 읽히되, <code>자료/센서_목록.csv</code>의 HYD-01 줄에 TS1이 두 번 나오고 HYD-02의 PS1 한계가 <code>130 bar</code>로 적혀 있다는 것만 눈으로 확인해 둔다. 4단계에서 이 줄을 쓴다.</p>')
+nxt(1,'1. 고치기 전에, 먼저 읽게 한다'))

# ── 1 ──
pages.append(hero('1단계','고치기 전에,<br>먼저 읽게 한다','첫마디가 「새 자료로 스키마를 보완해 줘」이면 AI는 읽자마자 고치기 시작한다. 단가를 어디에 둘지, 새로 나온 이름을 같은 장치로 볼지 같은 판단이 내가 모르는 사이에 내려져 파일에 들어간다. 그래서 첫 요청은 <b>읽고, 이해한 것을 말해 보라</b>는 요청으로 한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','이어받은 것, 모자란 곳, 내가 정할 것이 채팅에 정리되어 있다'),('아직 바뀌면 안 되는 것','결과/schema.json, 결과/graph.json')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>'+copy(P1,rich=P1rich)+'<div class="parts"><div class="a"><b>무엇을 읽는가</b>규칙 파일, 지난 시간의 두 파일, 새 자료 여섯 파일. 이어받은 것과 새로 받은 것을 함께 읽혀야 둘을 견줄 수 있다.</div><div class="b"><b>어떤 모양으로 답하는가</b>이미 있는 것, 모자란 것, 내가 정할 것. 셋으로 나누게 해야 답이 길어도 어디를 읽을지가 정해진다.</div><div class="c"><b>하지 말 것</b>이 요청에서 가장 중요한 문장이다. 이 한 줄이 없으면 읽자마자 고치기 시작한다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 클래스별 노드 수를 정리한 표와, 답의 끝에서 「정해 주셔야 하는 것」을 번호로 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')+f'<div class="find"><div><i>①</i><p style="margin:0"><b>이어받은 것의 수</b><span>클래스 {len(S0["classes"])}, 관계 {len(S0["relationships"])}, 노드 {len(G0["nodes"])}이라고 했는가. 준비 단계에서 본 수와 같아야 한다. 다르면 다른 파일을 읽은 것이다.</span></p></div><div><i>②</i><p style="margin:0"><b>새 자료에만 있는 표기</b><span>「주 펌프 A」, 「A 펌프」, 「작동유 온도」처럼 지난 시간의 <code>aliases</code>에 없는 말을 찾아냈는가. <code>130 bar</code>, <code>L/min</code>, 빈 단위 칸처럼 값을 적은 방식이 다른 곳도 짚었는가.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 나에게 되묻는 것</b><span>답의 끝에 정해 달라는 목록이 있는가. 공급 조건을 담을지, 단가를 어디에 둘지, 공급사의 식별자를 무엇으로 만들지가 들어 있을 것이다. 몇 가지인지 세어 둔다.</span></p></div></div>'+'<div class="note"><b>되묻는 까닭</b>규칙 파일의 「정해져 있지 않은 것」에 여섯 줄을 적고 「요청에 없으면 정하지 말고 묻는다」고 해 두었기 때문이다. 규칙이 없었다면 이 자리들은 AI가 알아서 채웠을 것이고, 무엇이 어떻게 정해졌는지는 파일을 뜯어보아야 알 수 있다.</div><div class="if"><div><b>파일이 바뀌어 버렸다면</b>탐색기에서 <code>schema.json</code>이나 <code>graph.json</code> 옆에 바뀌었다는 표시(M)가 보이면 요청의 마지막 문장이 빠진 것이다. 채팅의 「실행 취소」로 되돌리거나 받은 <code>시작</code> 폴더를 다시 복사해 연 뒤, 요청을 다시 복사해 보낸다.</div><div><b>되묻는 것이 없다면</b>「보완하기 전에 내가 정해 줘야 하는 것을 번호로 적어 줘」라고 한 번 더 묻는다. 그래도 없으면 다음 단계로 간다. 다음 요청이 그 자리를 모두 정해 준다.</div></div>')
+nxt(2,'2. 선택지를 골라 답하고, 계획부터 받는다',0))

# ── 2 ──
pick=('<table class="res"><thead><tr><th>정할 것</th><th>권하는 답 (아래 복사 상자에 들어 있다)</th><th>다르게 고르려면</th></tr></thead><tbody>'
 '<tr><td><b>담을 범위</b><br>1번 줄</td><td>현장 메모 6절의 다섯 물음 전부. 다섯째 물음(어느 공급사에서 얼마에)에 답하려면 공급 조건이 있어야 한다</td><td>공급 조건을 빼려면 1번 줄을 아래로 바꾸고 2~4번 줄을 지운다. 그러면 5단계와 6단계의 공급사 부분은 내 파일에 없는 것이 맞다'+alt('1. 답하려는 질문은 현장 메모 6절의 앞 네 가지야. 공급 조건은 이번에는 담지 않는다.')+'</td></tr>'
 '<tr><td><b>단가의 자리</b><br>2번 줄</td><td>공급사는 클래스로, 단가 · 불량률 · 납기는 관계의 속성으로, 승인 여부는 공급사의 속성으로. 위 그림의 ③이다</td><td>같은 공급사라도 부품에 따라 승인 여부가 다를 수 있다고 보면 2번 줄의 한 문장을 바꾼다'+alt('승인 여부도 SUPPLIED_BY 관계의 속성으로 둔다.')+'</td></tr>'
 '<tr><td><b>한계의 방향</b><br>5번 줄</td><td>유온 65는 넘으면 안 되는 값이고 토출 압력 130은 밑돌면 안 되는 값이다. 프로그램이 가릴 수 있게 <code>enum</code> 속성으로 둔다</td><td>지금처럼 사람이 읽는 문장으로만 두려면 5번 줄의 끝 문장을 바꾼다'+alt('한계의 방향은 지금처럼 limit_note 의 문장으로만 둔다.')+'</td></tr>'
 '<tr><td><b>새로 나온 표기</b><br>6번 줄</td><td>「주 펌프 A」, 「A 펌프」, 「작동유 온도」는 노드를 새로 만들지 않고 같은 노드의 <code>aliases</code>에 더한다. 그 말로 물어도 찾을 수 있다</td><td>띄어쓰기와 괄호만 다른 말까지 쌓고 싶지 않으면 그 문장을 바꾼다'+alt("'주 펌프 A', 'A 펌프'는 표기만 다른 것으로 보고 aliases 에 넣지 않는다. '작동유 온도'만 aliases 에 더한다.")+'</td></tr>'
 '</tbody></table>')
pages.append(hero('2단계','선택지를 골라 답하고,<br>계획부터 받는다','Copilot이 되물은 것은 귀찮은 질문이 아니라 이 스키마의 설계 그 자체다. 단가를 부품에 둘지 관계에 둘지, 한계의 방향을 문장으로 둘지 정해진 값으로 둘지에 따라 파일이 달라진다. 정답이 하나가 아니므로 <b>설계하는 사람이 고른다.</b> 기준은 하나다. 이 지식으로 어떤 질문에 답하려는가.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','내가 고른 답이 반영된 계획이 채팅에 있다'),('아직 바뀌면 안 되는 것','결과/schema.json, 결과/graph.json')])
+'<section class="sect"><h2>가장 크게 갈리는 결정: 단가를 어디에 적을 것인가</h2><p>공급 조건 7줄에서 펌프 축 씰 키트는 세 공급사에 한 줄씩 나오고, A정밀은 세 부품에 한 줄씩 나온다. 단가를 적을 수 있는 자리는 셋이다.</p>'+where_fig+'</section>'
+do(1,'editor','이 화면','네 가지를 고른다','<p>Copilot이 물어 온 것 가운데 결과를 크게 가르는 네 가지다. 가운데 칸이 이 가이드가 권하는 답이고, 완성 폴더는 이 답으로 만든 것이다. 처음이면 권하는 답 그대로 간다. 다르게 고르고 싶은 것이 있으면 오른쪽 칸의 문장을 기억해 둔다.</p>'+pick)
+do(2,'chat','Copilot 채팅 · 입력 칸','고른 답을 보낸다','<p>아래 요청에는 권하는 답이 번호마다 한 줄씩 들어 있다. 「복사」를 눌러 채팅에 붙여넣는다. 다르게 고른 것이 있으면 <b>보내기 전에 입력 칸에서 그 줄만</b> 위 표의 문장으로 바꾼다.</p>'+copy(P2,rich=P2rich,pre=True)+'<div class="parts"><div class="a"><b>번호를 붙인 까닭</b>결정 하나가 한 줄이다. Copilot도 나도 빠뜨리지 않고, 나중에 「3번을 바꿀게」라고 가리킬 수 있다.</div><div class="b"><b>3번, 4번, 7번</b>자료형과 필수 여부, 식별자, 카디널리티다. 공급사에는 번호가 없어 이름 맨 앞의 영문자로 식별자를 만들기로 했다. 카디널리티는 값을 정해 주지 않고 까닭과 함께 제안하게 했다.</div><div class="c"><b>마지막 문장</b>바로 고치지 않고 계획을 먼저 말하게 한다. 규칙 파일의 5번이 이 말을 받으면 계획만 말하도록 정해 두었다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 두 가지를 찾는다','<p>Copilot은 파일을 고치지 않고 계획을 내놓는다. 「이렇게 고치겠다」와 「이것은 확인해 달라」가 함께 온다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 관계마다 카디널리티를 제안한 표와, 끝의 「확인해 주실 것」이 보이게. 다시 물어 온 항목에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>카디널리티를 제안한 표</b><span>관계마다 값과 까닭이 적혀 있다. 까닭이 「지금 관계가 하나뿐이어서」인 줄을 찾는다. <code>CAUSES</code>나 <code>MITIGATED_BY</code>처럼 예제가 한 건뿐인 관계가 <code>1:1</code>로 제안되어 있을 것이다. 다음 단계에서 이것을 다룬다.</span></p></div><div><i>②</i><p style="margin:0"><b>다시 물어 온 것</b><span>일곱 가지를 정해 주었는데도 확인해 달라는 것이 더 나온다. 무엇을 물었는지 읽어 둔다. 물음은 사람마다 다르다.</span></p></div></div><div class="note"><b>계획부터 받는 까닭</b>계획을 받지 않고 바로 고치게 했다면, 카디널리티 열두 개는 내가 한 번도 보지 못한 채 파일에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.</div><div class="if"><div><b>계획 없이 파일을 고쳤다면</b>요청의 마지막 문장이 빠진 것이다. 고친 것을 되돌리고 요청을 다시 복사해 보낸다.</div><div><b>계획이 내 답과 다르다면</b>「2번에서 단가는 관계의 속성으로 두기로 했어. 계획에는 Part 의 속성으로 되어 있어.」처럼 번호와 함께 어디가 다른지를 말한다.</div></div>')
+nxt(3,'3. schema.json 한 파일만 먼저 보완한다',1))

# ── 3 ──
pages.append(hero('3단계','schema.json 한 파일만<br>먼저 보완한다','이제 고치게 한다. 다만 스키마와 인스턴스를 한꺼번에가 아니라 <code>schema.json</code>에서 멈추게 한다. 두 파일이 함께 바뀌면, 인스턴스가 이상할 때 약속이 잘못 적힌 것인지 약속은 맞는데 잘못 옮긴 것인지를 가릴 수 없다. <b>약속을 먼저 읽어 확인하고, 그다음에 자료를 옮긴다.</b>',[('걸리는 시간','약 6분'),('이 단계가 끝나면','schema.json에 새 클래스와 관계, 카디널리티, 새 규칙 문장이 들어 있다'),('아직 바뀌면 안 되는 것','결과/graph.json')])
+'<section class="sect"><h2>하나 더 고른다: 카디널리티의 기준</h2><p>계획의 표에서 <code>1:1</code>로 제안된 관계를 다시 본다. 지금 <code>graph.json</code>에는 원인이 하나, 고장 유형이 하나뿐이어서 <code>CAUSES</code>가 한 건이다. 그렇다고 「원인 하나는 고장 유형 하나에만 이어진다」고 약속해도 되는가.</p><div class="vs"><div class="bad"><b>지금 들어 있는 대로</b>예제에 보이는 수를 그대로 적는다. 오늘의 데이터와는 어긋나지 않는다. 다음에 고장 유형이 하나 더 들어오면 스키마를 다시 고쳐야 한다.</div><div class="good"><b>앞으로 있을 수 있는 대로 (권하는 답)</b>스키마는 무엇이 있는가가 아니라 무엇이 있을 수 있는가를 적는다. 원인 하나가 여러 고장을 일으킬 수 있고, 같은 물리량을 재는 센서가 더 달릴 수 있다.</div></div></section>'
+do(1,'chat','Copilot 채팅 · 입력 칸','계획에 답하고, 범위를 정해 준다','<p>아래 요청을 복사해 보낸다. 초록색 문장이 방금 고른 기준이다. 「지금 들어 있는 대로」를 골랐다면 둘째 문단을 지우고 「cardinality 는 제안대로 한다.」 한 줄을 적는다.</p>'+copy(P3,rich=P3rich,pre=True)+'<div class="parts"><div class="a"><b>첫 문장</b>공급사 이름의 괄호 말을 그대로 둘지는 계획에서 되물어 오기 쉬운 것이어서 미리 답해 두었다. 내 계획이 이것을 묻지 않았어도 그대로 보내면 된다.</div><div class="b"><b>「권한 쪽으로 한다」</b>물어 온 것이 사람마다 달라 넣은 문장이다. 내 계획이 물은 것 가운데 다르게 정하고 싶은 것이 있으면 이 문장 뒤에 한 줄을 덧붙인다.</div><div class="c"><b>범위</b>고칠 파일 하나와 고치지 않을 파일 하나를 둘 다 적었다. 「여기까지」를 말하지 않으면 AI는 끝까지 간다.</div></div>')
+do(2,'chat','Copilot 채팅','파일을 고쳐도 되는지 물으면, 파일 이름을 읽고 허용한다','<p>Copilot이 파일을 고치려 할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 고치려는 파일이 <code>결과/schema.json</code> 하나인지 읽는다. <code>graph.json</code>이나 <code>자료</code> 폴더의 파일이 들어 있으면 허용하지 않는다.</p>'+shot('Copilot이 결과/schema.json을 고치면서 허용을 묻거나 변경을 보여 주는 화면. 파일 이름과 「유지/허용」 버튼이 보이게.'))
+do(3,'editor','VS Code · 편집기','보완된 <code>schema.json</code>을 열어 세 곳을 읽는다','<p>이 파일은 AI가 썼지만, 앞으로 이 설비 지식에 들어가는 모든 데이터는 여기 적힌 대로다. 아래 표는 이 가이드가 권하는 답으로 갔을 때 이 단계 뒤의 <code>schema.json</code>에서 옮긴 것이다. 내 것은 달라도 되고, 내가 고른 대로 적혀 있는지를 본다.</p><p><b>첫째, <code>classes</code>.</b> 속성 한 줄은 속성명, 자료형, 필수 여부다. 새 클래스 <code>Supplier</code>가 생겼는가. <code>approved</code>가 글자가 아니라 <code>boolean</code>인가. <code>limit_direction</code>이 <code>enum</code>이고 허용값이 둘인가. 지난 시간의 속성은 하나도 빠지지 않았는가.</p>'+cls_table(S0,S3,['Asset','StateVariable','Supplier'])+'<p><b>둘째, <code>relationships</code>.</b> 화살표는 <code>from</code>에서 <code>to</code>로 향한다. 열두 관계 모두에 카디널리티가 들어갔는가. 왼쪽이 시작 클래스 쪽이다. <code>HAS_COMPONENT</code>가 <code>N:M</code>인 것은 지난 시간에 같은 장치를 노드 하나로 두어 세 설비가 함께 가리키기 때문이다. <code>SUPPLIED_BY</code>에만 관계의 속성이 있는가.</p>'+rel_table(S3)+f'<p><b>셋째, <code>conventions</code>.</b> 지난 시간의 {len(S0["conventions"])}문장은 그대로이고 뒤에 {len(newconv)}문장이 늘었다. 새 문장만 읽고도 다른 사람이 넷째 공급사의 식별자를 만들 수 있어야 한다. 아래는 그 가운데 둘이다.</p><ul class="ask">{conv_box}</ul>'+'<div class="if"><div><b>내가 고른 것과 다르게 적혀 있다면</b>지금 고친다. 「Supplier 의 approved 가 string 으로 되어 있어. 승인 공급사만 고르려고 boolean 으로 정했어. 그 한 줄만 고쳐 줘.」처럼 어디가 어떻게 다른지를 말한다.</div><div><b>graph.json 도 바뀌었다면</b>범위를 적은 마지막 문단이 빠진 것이다. 바뀐 것을 되돌리고 「결과/schema.json 한 파일만」이라고 다시 말한다.</div></div>')
+nxt(4,'4. 규칙이 막아 주는지 시험한다',2))

# ── 4 ──
pages.append(hero('4단계','규칙이 막아 주는지<br>일부러 시험한다','지금까지 Copilot이 자료를 건드리지 않고, 묻고, 계획에서 멈춘 것은 규칙 파일 때문이다. 그런데 규칙이 정말 일하는지는 <b>어긋나는 요청을 보내 보아야</b> 안다. 급할 때 누구나 할 법한 요청 둘을 일부러 보낸다. 고쳐지지 않는 것이 맞는 결과다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','규칙 파일의 어느 줄이 무엇을 막는지 안다'),('바뀌면 안 되는 것','자료 폴더의 파일, 이미 있는 이름')])
+do(1,'chat','Copilot 채팅 · 입력 칸','원본 자료를 고쳐 달라고 해 본다','<p>준비 단계에서 본 센서 목록의 지저분한 줄들이다. 원본을 고쳐 버리면 편할 것 같다. 아래 요청을 그대로 보낸다.</p>'+copy(P4a)+'<div class="find"><div><i>①</i><p style="margin:0"><b>고치지 않았는가</b><span>탐색기에서 <code>자료/센서_목록.csv</code> 옆에 바뀌었다는 표시(M)가 없어야 한다. 파일을 열어 HYD-01의 TS1이 여전히 두 줄인지 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>무엇을 근거로 댔는가</b><span>답에 규칙의 번호나 문장이 나오는가. 그 대신 무엇을 하겠다고 했는가도 읽는다. 원본은 그대로 두고 옮길 때 바로잡는다는 말이 있을 것이다.</span></p></div></div>'+shot('자료를 고쳐 달라는 요청에 Copilot이 고치지 않겠다고 답한 화면. 규칙을 근거로 든 문장에 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','이미 있는 이름을 바꿔 달라고 해 본다','<p>이번에는 이름이다. 지난 시간의 스키마는 품번을 <code>part_no</code>라고 적었다. 다른 곳에서 본 표기대로 바꾸고 싶어질 수 있다. 아래 요청을 보낸다.</p>'+copy(P4b)+'<p>이번에도 고쳐지지 않아야 한다. 답에서 <code>part_no</code>와 <code>label_ko</code>를 지금 어디에서 쓰고 있다고 했는지를 읽는다. 이름 하나가 스키마, 규칙 문장, 노드에 걸쳐 있다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 열고 「하면 안 되는 것」을 읽는다. 방금 두 요청을 막은 줄이 각각 몇 번인지 찾는다. 찾은 다음 아래와 견준다.</p><ul class="ask"><li><b>자료를 고쳐 달라는 요청을 막은 줄</b>'+e(R1).replace('`','')+'</li><li><b>이름을 바꿔 달라는 요청을 막은 줄</b>'+e(R6).replace('`','')+'</li></ul><div class="note"><b>규칙에 까닭까지 적는 까닭</b>두 줄 모두 「하지 않는다」에서 끝나지 않는다. 1번은 그 대신 무엇을 하는지를, 6번은 왜 안 되는지(다음 실습이 이 이름 그대로 그래프 DB에 넣는다)를 적었다. 그래서 AI가 거절만 하지 않고 대신할 방법과 이름이 쓰인 곳을 알려 준다. 사람이 급해서 규칙을 잊어도 규칙 파일이 기억한다.</div><div class="if"><div><b>정말로 고쳐 버렸다면</b>채팅의 「실행 취소」로 되돌린다. 되돌릴 수 없으면 받은 <code>시작</code> 폴더에서 그 파일만 다시 복사해 온다. 그리고 강사에게 알린다. 규칙 파일이 읽히지 않았을 수 있다. 요청 앞에 「이 폴더의 규칙(.github/copilot-instructions.md)을 다시 읽고 답해 줘.」를 붙여 한 번 더 보내 본다.</div><div><b>이름을 정말 바꿔야 한다면</b>규칙을 피해 갈 말을 찾지 않는다. 규칙 파일의 그 줄과, 이 파일을 이어받는 다음 실습을 함께 바꿀 일이다. 혼자 정할 수 없는 일이라는 것을 규칙이 알려 준 것이다.</div></div>')
+nxt(5,'5. 새 자료를 graph.json에 더하고, 자료와 맞춘다',3))

# ── 5 ──
pages.append(hero('5단계','새 자료를 graph.json에 더하고,<br>자료와 맞춘다','스키마는 무엇이 있을 수 있는가를 정한 것이고, 실제로 무엇이 있는가는 인스턴스 데이터에 담긴다. 3단계에서 확인한 약속대로 새 자료를 <code>graph.json</code>에 더하게 한다. 옮긴 결과가 자료의 뜻과 맞는지는 <b>수를 세고, 달라진 값을 찾아가 보는 것</b>으로 가린다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','graph.json에 공급사와 공급 조건, 설비 코드, 한계의 방향이 들어 있다'),('맞춰 볼 것','노드의 수와 값 ↔ 자료의 줄')])
+do(1,'chat','Copilot 채팅 · 입력 칸','아래 요청을 보낸다','<p>같은 대화에서 이어서 보낸다.</p>'+copy(P5,rich=P5rich)+'<div class="note"><b>끝에 표 셋을 달라고 한 까닭</b>파일은 길고, 바뀐 곳은 흩어져 있다. 수가 어떻게 달라졌는지, 이미 있던 노드에 무엇이 더해졌는지, 자료와 다르게 옮긴 곳이 어디인지를 표로 받으면 내가 열어 볼 곳이 정해진다. 셋째 표는 규칙 파일의 2번이 밝히라고 정해 둔 것이다.</div>')
+do(2,'editor','VS Code · 편집기','수를 센다','<p>Copilot의 첫째 표를 아래와 견준다. 아래는 권하는 답으로 갔을 때의 결과다. 구성 요소 목록 18줄과 센서 목록 16줄을 새로 읽혔는데도 구성 요소와 센서의 노드가 늘지 않았다면, 지난 시간의 중복 처리 규칙이 새 자료에도 통한 것이다.</p>'+count_table+'<div class="if"><div><b>구성 요소나 센서가 늘었다면</b>어느 노드가 새로 생겼는지 찾는다. 「주 펌프 A」가 따로 생겼다면 2단계의 6번 줄이 빠졌거나 바뀐 것이다. 「comp:… 는 comp:main-pump 와 같은 장치야. 현장 메모 3절의 이름 표에 있어. 새 노드를 지우고 그 이름을 aliases 에 더해 줘.」라고 말한다.</div><div><b>파일이 길어 눈으로 세기 어렵다면</b>편집기에서 <code>"Supplier"</code>를 찾으면(Ctrl+F) 몇 건인지 나온다. 한 클래스만은 직접 센다.</div></div>')
+do(3,'editor','VS Code · 편집기 (좌우로 나란히)','공급 조건 7줄을 관계 일곱과 한 줄씩 맞춘다','<p><code>결과/graph.json</code>을 열어 맨 아래의 <code>SUPPLIED_BY</code> 줄들을 찾고, <code>자료/공급_조건.csv</code>를 오른쪽으로 끌어 나란히 둔다. 자료의 한 줄이 관계 한 줄이다.</p>'+sup_table(G5)+'<div class="find"><div><i>①</i><p style="margin:0"><b>수가 수로 들어갔는가</b><span><code>"price": "35"</code>처럼 따옴표가 붙어 있으면 글자다. 수여야 어느 쪽이 싼지 견줄 수 있다. 파일에 <code>0.30</code>으로 적혀 있어도 수로는 위 표의 <code>0.3</code>과 같다.</span></p></div><div><i>②</i><p style="margin:0"><b>「예」와 「아니오」</b><span>공급사 노드 셋의 <code>approved</code>가 <code>true</code>, <code>true</code>, <code>false</code>인가. Copilot의 셋째 표에 글자를 바꿔 적었다는 보고가 있는가.</span></p></div><div><i>③</i><p style="margin:0"><b>방향</b><span><code>a</code>가 부품의 식별자이고 <code>b</code>가 공급사의 식별자인가. 스키마의 <code>from</code>이 <code>Part</code>, <code>to</code>가 <code>Supplier</code>였다.</span></p></div></div>'+shot('결과/graph.json과 자료/공급_조건.csv를 좌우로 나란히 연 VS Code 화면. graph.json에서 SUPPLIED_BY 관계 일곱 줄이 보이게.'))
+do(4,'editor','VS Code · 편집기','이미 있던 노드에 더해진 값을 찾아가 본다','<p>Copilot의 둘째 표에 나온 노드를 <code>graph.json</code>에서 찾아 본다. 아래는 권하는 답으로 갔을 때 값이 더해진 노드다. 여기에 없는 노드는 지난 시간과 글자 하나 다르지 않아야 한다.</p>'+added_table()+'<p>한계의 방향은 센서 목록에 칸이 없다. 현장 메모 4절의 문장에서 왔다. <code>sv:ce</code>와 <code>sv:fs1</code>에는 한계가 없으므로 <code>limit_direction</code>도 없어야 한다. <code>130 bar</code>와 빈 단위 칸은 이미 들어 있는 값을 따르기로 했으니 <code>sv:ps1</code>의 <code>limit</code>은 수 <code>130</code>, <code>sv:vs1</code>의 <code>unit</code>은 <code>mm/s</code> 그대로다.</p>')
+nxt(6,'6. 질문을 던져 보고, 모자란 곳을 되돌려 준다',4))

# ── 6 ──
pages.append(hero('6단계','질문을 던져 보고,<br>모자란 곳을 되돌려 준다','2단계에서 다섯 물음에 답하겠다고 정했다. 파일이 약속대로 만들어진 것과 그 물음에 실제로 답이 나오는 것은 다른 일이다. <b>만든 지식에 질문을 던져</b> 답이 어느 길로 나오는지를 보고, 답이 나오지 않는 곳을 찾아 고치게 한다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','세 물음의 답과 길을 보았고, 모자란 한 곳이 내 요청대로 고쳐져 있다')])
+do(1,'chat','Copilot 채팅 · 입력 칸','세 물음을 던진다','<p>아래 요청을 보낸다. 자료 폴더를 다시 보지 못하게 한 것은, 자료가 아니라 <b>내가 만든 두 파일만으로</b> 답이 나오는지를 보려는 것이다.</p>'+copy(P6a,rich=P6rich,pre=True)+'<div class="parts"><div class="a"><b>물음의 말</b>「열교환기」, 「유압 펌프」는 대장의 이름이 아니라 현장에서 쓰는 말이다. <code>aliases</code>가 일하는지를 함께 본다.</div><div class="b"><b>길을 적게 한 까닭</b>답만 받으면 맞았는지 가릴 방법이 없다. 어느 노드에서 어느 관계를 따라갔는지를 받으면 파일에서 그 길을 따라가 볼 수 있다.</div><div class="c"><b>답할 수 없으면 말하게 했다</b>속성이 없어 이름의 글자를 읽어 답하는 것은 답한 것이 아니다. 그런 곳이 스키마의 모자란 곳이다.</div></div>')
+do(2,'editor','Copilot 채팅 · 답 → 편집기','답의 길을 파일에서 따라가 본다','<p>첫째와 둘째 물음은 속성만으로 답이 나와야 한다. 둘째 물음의 길을 <code>graph.json</code>에서 직접 따라가 본다.</p>'+path_fig+shot('세 물음에 대한 Copilot의 답. 물음마다 답과, 노드와 관계를 따라간 길이 보이게. 셋째 물음에서 「속성만으로는 답할 수 없다」고 한 부분에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>첫째 물음</b><span>「열교환기」로 <code>comp:oil-cooler</code>를 찾았는가. 계산값인 CE를 <code>virtual</code>로 걸러 냈는가. 한계가 위쪽인지를 <code>limit_direction</code>에서 읽었는가, <code>limit_note</code>의 문장에서 읽었는가.</span></p></div><div><i>②</i><p style="margin:0"><b>둘째 물음</b><span>가장 싼 값은 C트레이딩인데 그것을 답으로 내지 않았는가. <code>approved</code>가 글자였다면 이 거르기가 되지 않았을 것이다.</span></p></div><div><i>③</i><p style="margin:0"><b>셋째 물음</b><span>「순정」인지를 어디에서 읽었다고 했는가. <code>Supplier</code>의 속성을 다시 본다. 순정인지 저가인지를 적는 칸이 있는가.</span></p></div></div>')
+'<section class="sect"><h2>같은 문제, 두 가지 말</h2><p>셋째 물음에서 모자란 곳이 드러난다. 공급사가 순정인지 저가인지는 <code>name</code>의 괄호 안에만 있다. 지난 시간에 「(가상)」이라는 말이 센서 이름에만 있던 것과 같은 문제다. 이것을 Copilot에게 되돌려 줄 때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다.</p><div class="vs"><div class="bad"><b>막연하게</b><q>공급사 쪽이 좀 부족해. 보완해 줘.</q>무엇이 문제인지가 글에 없다. AI는 짐작으로 고치거나 무엇을 원하는지 되물을 수밖에 없고, 한 번 더 주고받아야 한다.</div><div class="good"><b>구체적으로</b><q>공급사가 순정인지가 name 의 괄호 안에만 있어서 「순정 공급사에서만 산다면」에 속성으로 답할 수 없어. Supplier 에 그 값을 담는 속성을 더하고 공급사 셋에 채워 줘. name 과 approved 는 건드리지 마.</q>요청한 곳만 바뀐다.</div></div><div class="four"><div><b>무엇이</b>순정인지 저가인지가 이름의 글자로만 있다</div><div><b>왜</b>내가 고른 물음에 속성으로 답하지 못한다</div><div><b>어디를</b>스키마의 Supplier, 그리고 공급사 셋</div><div><b>어디까지</b>name, approved, 다른 클래스와 관계는 그대로</div></div><div class="note"><b>인스턴스가 아니라 스키마부터 고치는 까닭</b><code>graph.json</code>의 공급사 줄에만 값을 적어 넣으면 스키마에 없는 속성이 된다. 다음에 들어오는 공급사에는 그 칸이 없고, 넣는 사람마다 다른 이름으로 적게 된다. 약속을 먼저 고치고 데이터를 약속에 맞춘다.</div></section>'
+do(3,'chat','이 화면의 글 칸 → Copilot 채팅','네 가지를 넣어 직접 써서 되돌려 준다','<p>오늘 직접 쓰는 요청은 이것 하나다. 무엇이, 왜, 어디를, 어디까지. 네 가지를 넣어 내 말로 쓴다. 셋째 물음의 모자란 곳을 써도 되고, Copilot의 답에서 내가 찾은 다른 곳을 써도 된다. 새 속성의 이름은 규칙 파일의 이름 표에 없으므로, 이름과 허용값을 내가 정해 적거나 제안해 달라고 적는다.</p>'+write('w6','무엇이 문제인지, 왜 문제인지(어떤 물음에 답하지 못하는지), 어느 파일의 어디를 고칠지, 건드리지 말 곳을 적는다.')+'<details><summary>다 쓴 뒤에 견주어 볼 예</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">정답이 아니라 한 가지 예다. 속성의 이름과 허용값은 달라도 된다. 내 글에 네 가지가 다 들어 있는지를 보는 데 쓴다. 완성 폴더는 이 예대로 고친 결과다.</p>'+copy(P6b,'Copilot에게 보낼 요청 (예)',pre=True)+'</details>'+f'<p style="margin-top:18px">고친 뒤에는 <code>schema.json</code>에서 <code>Supplier</code>만 바뀌었는지, <code>graph.json</code>의 노드 수({len(G["nodes"])})와 관계 수({len(G["rels"])})가 그대로인지를 본다. 완성 폴더에서는 <code>Supplier</code>에 <code>grade</code> 한 줄이 늘었고 공급사 셋의 값은 {", ".join(jd(node(G,"sup:"+x)["grade"]) for x in "abc")}다. 「최저가 · 비승인」에서 「비승인」은 이미 <code>approved</code>에 있어 옮기지 않았다.</p>'+shot('되돌려 준 뒤 Copilot이 결과/schema.json과 결과/graph.json의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색으로 표시된 화면).'))
+'<section class="sect"><h2>시간이 남으면: 내가 정한 중복 규칙을 시험한다</h2><p>4단계에서는 규칙 파일을 시험했다. 이번에는 <code>schema.json</code>의 <code>conventions</code>에 적힌 중복 처리 규칙이 일하는지를 시험한다. 구성 요소 목록의 HYD-03 줄에는 「리저버」가 있고, <code>graph.json</code>에는 <code>name</code>이 「리저버」인 노드가 없다. 그럴듯한 요청이다.</p>'+copy(P8)+'<p>노드가 새로 생기지 않아야 한다. 탐색기에서 <code>graph.json</code>에 바뀌었다는 표시가 새로 붙지 않았는지 보고, 답이 무엇을 근거로 댔는지 읽는다. <code>conventions</code>의 어느 문장인지, 「리저버」가 지금 어느 노드의 어디에 들어 있는지를 <code>schema.json</code>과 <code>graph.json</code>에서 직접 찾아본다. 규칙 파일은 이 폴더에서 AI가 하면 안 되는 일을 막고, <code>conventions</code>는 이 지식에 같은 대상이 두 번 들어가는 일을 막는다. 둘 다 사람이 글로 적어 둔 약속이다.</p></section>'
+nxt(None,None,5))

names=['준비','1. 읽게 한다','2. 고르고 계획 받기','3. 스키마 보완','4. 규칙 시험','5. 자료 옮기기','6. 묻고 되돌려 주기']
bar='<div class="bar"><div class="bar-in"><b>지난 스키마 + 새 자료 → 보완한 스키마</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-02-1-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 6단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 설비 자료로 온톨로지 스키마 완성하기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
