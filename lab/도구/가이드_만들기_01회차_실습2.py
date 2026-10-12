# 통합반 오프라인 01회차 실습 2 「같은 기준으로 설비 관계를 구조화하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
# 본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꾸었다.
# 실행: python3 lab/도구/가이드_만들기_01회차_실습2.py  (저장소 맨 위에서)
import re, html, json, os
HERE=os.path.dirname(os.path.abspath(__file__))
R=os.path.join(HERE,'..','통합반_오프라인','01회차_실습2_설비정보_구조화','')
css=re.search(r'<style>(.*?)</style>',open(os.path.join(HERE,'디자인_샘플.html'),encoding='utf-8').read(),re.S).group(1)
css+='''
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
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
table.res{width:100%;border-collapse:collapse;font-size:14.5px;line-height:1.6;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid var(--line);margin:18px 0 8px}
table.res th{background:#eef1f5;text-align:left;padding:10px 14px;font-size:13px}
table.res td{padding:10px 14px;border-top:1px solid var(--line);vertical-align:top}
table.res mark{background:#fff1a8;padding:0 3px;border-radius:3px}
table.res code{font-size:.86em;overflow-wrap:anywhere}
table.res td:first-child code{white-space:nowrap}
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
.fig{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:18px 0 8px}
.fig svg{width:100%;height:auto;display:block}
.fig figcaption,.figcap{font-size:14px;color:var(--sub);margin:10px 4px 0}
figure{margin:0}
@media(max-width:760px){.flow,.two,.vs,.four{grid-template-columns:1fr}}
'''
e=html.escape
def vs(hl):  # VS Code 지도: hl in chat/explorer/editor
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
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 기준을 정한 schema.json, 그 기준대로 채운 graph.json, 두 관계도와의 대조표. schema.json은 이 회차의 마지막 실습에서 다시 쓴다</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()

# ---------- 완성본에서 옮겨 오는 것 ----------
S=json.load(open(R+'완성/결과/schema.json',encoding='utf-8'))
G=json.load(open(R+'완성/결과/graph.json',encoding='utf-8'))
node={n['props']['id']:n for n in G['nodes']}
ncls={}
for n in G['nodes']: ncls[n['labels'][0]]=ncls.get(n['labels'][0],0)+1
nrel={}
for r in G['rels']: nrel[r['type']]=nrel.get(r['type'],0)+1
cls={c['name']:c for c in S['classes']}
rel={r['type']:r for r in S['relationships']}
rows=[[c.strip() for c in l.strip().strip('|').split(' | ')] for l in open(R+'완성/결과/대조표.md',encoding='utf-8') if re.match(r'\|\s*\d+\s*\|',l)]
assert len(rows)==15 and len(G['nodes'])==33 and len(G['rels'])==46
def md(s): return re.sub(r'`([^`]+)`',lambda m:'<code>'+m.group(1)+'</code>',e(s))
def crow(k,mark=False):
    r=rows[k-1]; c=[r[0],md(r[1]),md(r[2]),('<mark>'+e(r[3])+'</mark>') if mark else e(r[3]),md(r[4])]
    return '<tr>'+''.join(f'<td{" style=\"white-space:nowrap\"" if j in (0,3) else ""}>{x}</td>' for j,x in enumerate(c))+'</tr>'
ctable='<table class="res"><thead><tr><th style="white-space:nowrap">번호</th><th>관계도의 화살표</th><th>파일의 표현</th><th>판정</th><th>까닭</th></tr></thead><tbody>'+crow(3)+crow(5,True)+crow(6,True)+crow(13)+'</tbody></table>'
def js1(o): return e(json.dumps(o,ensure_ascii=False))
sensor_def='{\n  "name": "Sensor",\n  "label_ko": '+json.dumps(cls['Sensor']['label_ko'],ensure_ascii=False)+',\n  "description": '+json.dumps(cls['Sensor']['description'],ensure_ascii=False)+',\n  "properties": [\n'+',\n'.join('    '+json.dumps(p,ensure_ascii=False) for p in cls['Sensor']['properties'])+'\n  ]\n}'
rel_def=json.dumps(rel['MEASURES'],ensure_ascii=False)
ts,sv,co=node['sen:ts1']['props'],node['sv:ts1']['props'],node['comp:oil-cooler']['props']
assert any(r['type']=='MOUNTED_ON' and r['a']=='sen:ts1' and r['b']=='comp:oil-cooler' for r in G['rels'])
assert any(r['type']=='MEASURES' and r['a']=='sen:ts1' and r['b']=='sv:ts1' for r in G['rels'])
assert 'limit' not in node['sv:fs1']['props']
def card(x,y,w,lab,pid,lines,fill='#eaf0ff',stroke='#2f5bea'):
    o=f'<rect x="{x}" y="{y}" width="{w}" height="{54+len(lines)*20}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/><text x="{x+14}" y="{y+22}" font-size="11.5" font-weight="700" fill="#5b6573">{lab}</text><text x="{x+14}" y="{y+41}" font-size="14.5" font-weight="800" fill="#14181f" font-family="Consolas,monospace">{e(pid)}</text>'
    for i,l in enumerate(lines): o+=f'<text x="{x+14}" y="{y+61+i*20}" font-size="12.5" fill="#333b47">{e(l)}</text>'
    return o
def kv(p,keys): return [f'{k}: {json.dumps(p[k],ensure_ascii=False)}' for k in keys if k in p]
fig_row=f'''<figure class="fig"><svg viewBox="0 0 840 300" role="img" aria-label="목록의 한 줄이 노드 셋과 관계 둘로 나뉜 그림" font-family="Pretendard,Malgun Gothic,Apple SD Gothic Neo,sans-serif">
<defs><marker id="a2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6573"/></marker></defs>
<text x="10" y="20" font-size="12.5" font-weight="700" fill="#5b6573">목록의 8번 줄 (한 줄)</text>
<rect x="10" y="30" width="820" height="46" rx="10" fill="#fff8e1" stroke="#e0b84a" stroke-width="1.5"/>
<text x="26" y="59" font-size="14" fill="#14181f">8 │ HYD-01 │ 계장 │ <tspan font-weight="800" fill="#2f5bea">유온 센서</tspan> │ <tspan font-weight="800" fill="#2f5bea">TS1</tspan> │ <tspan font-weight="800" fill="#14804a">오일 쿨러</tspan> │ <tspan font-weight="800" fill="#b25a00">유온</tspan> │ <tspan font-weight="800" fill="#b25a00">℃</tspan> │ <tspan font-weight="800" fill="#b25a00">48</tspan> │ <tspan font-weight="800" fill="#b25a00">65</tspan> │ 65 ℃에서 인터록</text>
<line x1="120" y1="80" x2="120" y2="128" stroke="#5b6573" stroke-width="1.4" stroke-dasharray="4 4"/><line x1="420" y1="80" x2="420" y2="128" stroke="#5b6573" stroke-width="1.4" stroke-dasharray="4 4"/><line x1="720" y1="80" x2="720" y2="128" stroke="#5b6573" stroke-width="1.4" stroke-dasharray="4 4"/>
<text x="10" y="122" font-size="12.5" font-weight="700" fill="#5b6573">graph.json (노드 셋, 관계 둘)</text>
{card(10,132,220,'Component · '+cls['Component']['label_ko'],co['id'],kv(co,['name','aliases']),'#e8f6ee','#14804a')}
{card(310,132,220,'Sensor · '+cls['Sensor']['label_ko'],ts['id'],kv(ts,['name','tag','virtual']))}
{card(610,132,220,'StateVariable · '+cls['StateVariable']['label_ko'],sv['id'],kv(sv,['name','unit','normal','limit','limit_note']),'#fff4e3','#b25a00')}
<line x1="308" y1="160" x2="234" y2="160" stroke="#5b6573" stroke-width="1.6" marker-end="url(#a2)"/><text x="270" y="180" font-size="10.5" font-weight="700" text-anchor="middle" fill="#2f5bea">MOUNTED_ON</text>
<line x1="532" y1="160" x2="606" y2="160" stroke="#5b6573" stroke-width="1.6" marker-end="url(#a2)"/><text x="570" y="180" font-size="10.5" font-weight="700" text-anchor="middle" fill="#2f5bea">MEASURES</text>
</svg><figcaption>완성 폴더의 <code>graph.json</code>에서 옮긴 것이다. 줄 하나에 섞여 있던 계기, 붙은 곳, 재는 것과 그 값이 노드 셋으로 나뉘었다. 26번, 44번 줄(HYD-02, HYD-03의 TS1)도 이 세 노드를 함께 쓴다. 내 결과는 클래스와 관계의 이름이 다를 수 있다.</figcaption></figure>'''
rel_svg=re.sub(r'<rect width="920" height="620" fill="#fff"/>','',open(R+'시작/자료/관계도/관계도.svg',encoding='utf-8').read()).replace('id="ah"','id="ah0"').replace('url(#ah)','url(#ah0)')
fig_rel=f'<figure class="fig">{rel_svg}<figcaption><code>자료/관계도/관계도.svg</code>. 노드 13개, 화살표 15개다. 노드 안의 작은 글씨는 그릴 때 붙인 종류다.</figcaption></figure>'
fig_layers='''<figure class="fig"><svg viewBox="0 0 840 250" role="img" aria-label="정의와 실제 대상을 두 파일로 나누는 그림" font-family="Pretendard,Malgun Gothic,Apple SD Gothic Neo,sans-serif">
<rect x="10" y="10" width="820" height="100" rx="14" fill="#f3eeff" stroke="#6a3fd1" stroke-width="1.5" stroke-dasharray="6 5"/>
<text x="28" y="36" font-size="13" font-weight="800" fill="#6a3fd1">schema.json — 정의 (클래스와 관계)</text>
<text x="28" y="58" font-size="12.5" fill="#5b6573">어떤 종류의 대상이 있고, 어떤 칸(속성)을 갖고, 무엇과 무엇을 어느 방향으로 잇는가</text>
<rect x="150" y="68" width="150" height="32" rx="8" fill="#fff" stroke="#6a3fd1"/><text x="225" y="89" font-size="13.5" font-weight="700" text-anchor="middle">Sensor · 센서</text>
<rect x="540" y="68" width="170" height="32" rx="8" fill="#fff" stroke="#6a3fd1"/><text x="625" y="89" font-size="13.5" font-weight="700" text-anchor="middle">Component · 구성 요소</text>
<rect x="10" y="140" width="820" height="100" rx="14" fill="#eaf0ff" stroke="#2f5bea" stroke-width="1.5"/>
<text x="28" y="166" font-size="13" font-weight="800" fill="#2f5bea">graph.json — 실제 대상 (노드와 관계)</text>
<text x="28" y="188" font-size="12.5" fill="#5b6573">정의에 맞춰 채운 대상 하나하나. 식별자(id)가 대상을 가리킨다</text>
<rect x="150" y="198" width="150" height="32" rx="16" fill="#fff" stroke="#2f5bea" stroke-width="2"/><text x="225" y="219" font-size="13.5" font-weight="700" text-anchor="middle" font-family="Consolas,monospace">sen:ts1</text>
<rect x="540" y="198" width="170" height="32" rx="16" fill="#fff" stroke="#2f5bea" stroke-width="2"/><text x="625" y="219" font-size="13.5" font-weight="700" text-anchor="middle" font-family="Consolas,monospace">comp:oil-cooler</text>
<line x1="225" y1="198" x2="225" y2="102" stroke="#8a94a3" stroke-width="1.4" stroke-dasharray="4 4"/><line x1="625" y1="198" x2="625" y2="102" stroke="#8a94a3" stroke-width="1.4" stroke-dasharray="4 4"/>
<text x="233" y="130" font-size="12" fill="#5b6573">labels: ["Sensor"]</text><text x="633" y="130" font-size="12" fill="#5b6573">labels: ["Component"]</text>
</svg><figcaption>윗줄이 클래스이고 아랫줄이 인스턴스다. 이 실습은 두 줄을 서로 다른 파일에 적는다. 아랫줄의 식별자는 완성 폴더에서 옮긴 예다.</figcaption></figure>'''

P1=P('1_prompt.txt')
P1rich='<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 자료 폴더의 파일을 모두 읽어 줘.</span> <span class="p-b">목록의 줄을 같은 종류끼리 묶어서, 묶음마다 줄이 몇 개인지와 대표 예를 알려 줘. 같은 대상인데 이름이 다르게 적힌 것, 값이 빠진 것, 관계도에는 있는데 목록에는 없는 것도 따로 정리해 줘.</span> <span class="p-c">아직 파일은 만들지 마.</span>'
assert re.sub(r'<[^>]+>','',P1rich)==P1, 'P1'
P2=P('2_prompt.txt'); P3=P('3_prompt.txt'); P4=P('4_prompt.txt'); P5=P('5_prompt.txt')
V1=P('7_prompt.txt'); V2=P('8_prompt.txt'); V3=P('9_prompt.txt'); PD=P('10_prompt.txt'); PQ=P('11_prompt.txt')
assert len(P2.split('\n\n')[1].split('\n'))==9
# 2조 대조표(완성 폴더)에서 옮겨 오는 줄
rows2=[[c.strip() for c in l.strip().strip('|').split(' | ')] for l in open(R+'완성/결과/대조표_2조.md',encoding='utf-8') if re.match(r'\|\s*\d+\s*\|',l)]
assert len(rows2)==9 and [r[3] for r in rows2].count('방향 반대')==4 and rows2[8][3]=='파일에 없음'
def crow2(k,mark=False):
    r=rows2[k-1]; c=[r[0],md(r[1]),md(r[2]),('<mark>'+e(r[3])+'</mark>') if mark else e(r[3])]
    return '<tr>'+''.join(f'<td{" style=\"white-space:nowrap\"" if j in (0,3) else ""}>{x}</td>' for j,x in enumerate(c))+'</tr>'
ctable2='<table class="res"><thead><tr><th style="white-space:nowrap">번호</th><th>2조 관계도의 화살표</th><th>파일의 표현</th><th>판정</th></tr></thead><tbody>'+crow2(1,True)+crow2(4)+crow2(8,True)+crow2(9,True)+'</tbody></table>'
RULE=open(R+'시작/.github/copilot-instructions.md',encoding='utf-8').read()
def rule(start):
    l=[x for x in RULE.split('\n') if x.startswith(start)]; assert len(l)==1,start; return md(l[0])
co_al=node['comp:oil-cooler']['props']['aliases']; assert '열교환기' in co_al and '오일 온도' in sv['aliases'] and '토출 유량' in node['sv:fs1']['props']['aliases']

pages=[]
# ============================== 준비
pages.append(hero('준비','<small>통합반 오프라인 1회차 · 실습 2 · 40분</small>설비 · 계기 목록을<br>클래스, 인스턴스, 식별자로 나눈다','앞 실습에서 그린 관계도는 사람이 보기에는 좋지만, 그리는 사람마다 이름도 모양도 다르다. 두 사람이 따로 적은 것을 합치려면 무엇이 종류(클래스)이고 무엇이 실제 대상(인스턴스)인지, 대상 하나를 무엇으로 가리킬지(식별자)가 같은 기준으로 정해져 있어야 한다. 오늘은 55줄짜리 설비 · 계기 목록을 그 기준으로 나누어 <code>schema.json</code>과 노드 · 관계의 예제로 적고, 관계도와 같은 뜻인지 대조한다.',[('걸리는 시간','준비 3분 · 전체 40분'),('끝나면 남는 것','schema.json, graph.json, 대조표 둘'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna)'),('전제','온라인 1 · 2일차의 온톨로지 단원을 들었다')])
+'<section class="sect"><h2>오늘 하는 일의 순서</h2><p>손으로 JSON을 쓰는 일은 없다. 요청은 이 가이드의 복사 상자에 준비되어 있다. 내가 할 일은 요청을 보내기 전에 <b>왜 그렇게 쓰였는지를 읽고</b>, 갈림길에서 고르고, 돌아온 결과가 맞는지 판단하는 것이다. 파일은 AI가 쓰지만 무엇을 클래스로 두고 무엇을 인스턴스로 둘지는 내가 정한다.</p><div class="flow" style="grid-template-columns:repeat(4,1fr)"><div><em>1</em><b>읽게 한다</b>만들기 전에 목록과 관계도를 읽고 이해한 것을 말하게 한다</div><div><em>2</em><b>정해 준다</b>클래스, 식별자, 값의 자리를 정하고 계획을 받는다</div><div><em>3</em><b>정의만 만든다</b>schema.json 한 파일을 만들고 읽어 본다</div><div><em>4</em><b>채우고 대조한다</b>새 대화에서 노드와 관계를 채우고 관계도와 견준다</div><div><em>5</em><b>규칙을 건드려 본다</b>일부러 어긋나는 요청을 보내 AI가 멈추는 것을 본다</div><div><em>6</em><b>되돌려 준다</b>아쉬운 곳 하나를 내 말로 써서 기준을 고친다</div><div><em>7</em><b>바꿔 돌리고 써 본다</b>다른 조의 관계도로 대조하고, 파일만으로 물음에 답하게 한다</div></div></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md   <i>← 이 폴더의 규칙</i>\n├─ <span>자료/</span>\n│  ├─ 설비_계기_목록.md          <i>← 유압 파워팩 세 대의 목록 55줄</i>\n│  └─ <span>관계도/</span>\n│     ├─ 관계도.svg             <i>← 앞 실습에서 그린 관계도</i>\n│     ├─ 화살표_목록.md          <i>← 그 화살표 15개를 글로 옮긴 것</i>\n│     └─ 화살표_목록_2조.md      <i>← 2조가 따로 그린 관계도 (7단계에서 쓴다)</i>\n└─ <span>결과/</span>                       <i>← 지금은 비어 있다</i></div><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 자료(관계도 폴더까지 펼침), 결과가 보이게.'))
+do(2,'editor','VS Code · 편집기','<code>설비_계기_목록.md</code>를 직접 읽는다','<p>탐색기에서 <code>자료/설비_계기_목록.md</code>를 눌러 연다. 표가 글자로 보여 읽기 어려우면 Ctrl+Shift+V(맥은 Cmd+Shift+V)를 눌러 미리 보기로 본다. 뒤에서 Copilot의 결과가 맞는지를 가리는 사람은 나다. 전부 외울 필요는 없고, 아래 세 가지를 줄 번호로 찾아본다.</p><ul class="ask"><li><b>같은 것이 몇 번 적혀 있는가</b>8번, 26번, 44번 줄은 모두 태그가 TS1이다. 센서는 셋인가, 하나인가.</li><li><b>한 줄에 대상이 몇 개 들어 있는가</b>8번 줄에는 유온 센서(계기), 오일 쿨러(붙은 곳), 유온(재는 것), 48과 65(값)가 함께 있다.</li><li><b>무엇으로 가리킬 것인가</b>2번 줄의 「오일 쿨러」와 20번 줄의 「열교환기」는 같은 장치를 다르게 부른 것이다. 이름으로 가리키면 둘이 된다. 그런데 기계 줄에는 태그가 없다.</li></ul>'+shot('설비_계기_목록.md를 편집기에 열고 미리 보기를 옆에 띄운 화면. 표의 머리줄과 1~18번 줄이 보이게.'))
+do(3,'editor','이 화면의 그림','관계도를 다시 본다','<p>앞 실습에서 arrows.app으로 그린 것과 같은 꼴의 관계도다. <code>관계도.svg</code>는 VS Code에서 열면 글자로 보이므로 아래 그림으로 본다. 화살표 하나하나는 <code>화살표_목록.md</code>에 「시작 노드 → 끝 노드」로 한 줄씩 옮겨져 있다.</p>'+fig_rel+'<p>열세 개 가운데 <b>「센서」</b>와 <b>「65 ℃」</b> 두 노드는 나머지와 성격이 다르다. 무엇이 다른지 한 문장으로 말할 수 있는지 생각해 둔다. 4단계에서 확인한다.</p>')
+do(4,'editor','VS Code · 편집기','규칙 파일의 세 절을 훑는다','<p><code>.github/copilot-instructions.md</code>를 연다. Copilot이 이 폴더에서 일할 때 지키는 약속이고, 세 절로 되어 있다.</p><table class="res"><thead><tr><th>절</th><th>무엇이 적혀 있는가</th><th>오늘 어디에서 만나는가</th></tr></thead><tbody><tr><td style="white-space:nowrap"><b>하면 안 되는 것</b></td><td>여섯 줄. 자료를 고치지 않는다, 없는 값을 지어내지 않는다, 요청을 받아도 예외를 두지 않는다 등</td><td>5단계에서 일부러 건드려 본다</td></tr><tr><td style="white-space:nowrap"><b>정해져 있는 것</b></td><td>만들 파일의 이름과 위치, 파일 안의 칸 이름</td><td>누가 만들어도 파일의 모양이 같아진다</td></tr><tr><td style="white-space:nowrap"><b>정해져 있지 않은 것</b></td><td>여덟 줄. 규칙이 일부러 비워 둔 자리</td><td>2단계에서 내가 채운다</td></tr></tbody></table>')
+nxt(1,'1. 만들기 전에, 먼저 읽게 한다'))

# ============================== 1단계
pages.append(hero('1단계','만들기 전에,<br>먼저 읽게 한다','AI에게 일을 시킬 때 첫마디가 「만들어 줘」이면, AI는 자료를 읽자마자 만들기 시작한다. 55줄을 클래스 몇 개로 나눌지, 세 대의 TS1을 몇 개로 볼지를 AI가 혼자 정해 버린다. 그래서 첫 요청은 <b>읽고, 이해한 것을 말해 보라</b>는 요청으로 한다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','Copilot이 목록과 관계도를 어떻게 이해했는지가 채팅에 정리되어 있다'),('아직 없어야 하는 것','새 파일')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 보내기 전에 세 가지 색이 각각 무슨 일을 하는지 읽는다.</p>'+copy(P1,rich=P1rich)+'<div class="parts"><div class="a"><b>무엇을 읽는가</b>규칙 파일과 자료 폴더. 읽을 대상을 내가 정해 준다.</div><div class="b"><b>어떤 모양으로 답하는가</b>「같은 종류끼리 묶기」가 곧 클래스를 찾는 첫걸음이다. 이름이 다른 것, 빠진 값, 관계도에만 있는 것은 뒤에서 내가 정해야 할 자리다.</div><div class="c"><b>하지 말 것</b>이 요청에서 가장 중요한 문장이다. 이 한 줄이 없으면 읽자마자 만들기 시작한다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분 남짓 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 목록의 묶음 표와, 답의 끝에서 「정해 주셔야 할 것」을 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>묶음과 줄 수</b><span>목록의 「구분」대로 세면 본체 3, 기계 19, 계장 24, 예비품 9줄이다. Copilot이 계장 24줄을 더 잘게 나누었는가. 값을 재는 것, 값을 바꾸는 것, 계산으로 만든 값(CE)이 한 묶음에 섞여 있지 않은가.</span></p></div><div><i>②</i><p style="margin:0"><b>이름이 다른 같은 대상</b><span>HYD-02 줄의 열교환기, 송풍기, 리저버가 HYD-01 줄의 무엇과 같은 장치라고 보았는가. 맨 끝 55번 줄을 어떻게 다루었는가.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 나에게 되묻는 것</b><span>답의 끝에 「정해 주셔야 할 것」이 있는가. 규칙 파일의 여덟 줄 가운데 몇 가지를 물었는지 세어 둔다. 다음 단계에서 이 물음에 답한다.</span></p></div></div><div class="note"><b>되묻는 까닭</b>규칙 파일에 「정해져 있지 않은 것은 스스로 정하지 말고 묻는다」고 적어 두었기 때문이다. 규칙이 없었다면 클래스의 수도 식별자의 모양도 AI가 알아서 정했을 것이고, 무엇이 어떻게 정해졌는지는 파일을 뜯어보아야 알 수 있다.</div><div class="if"><div><b>파일이 생겨 버렸다면</b>탐색기의 <code>결과</code> 폴더에 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.</div><div><b>내가 읽은 것과 다르다면</b>「다시 해 줘」라고 하지 않는다. 「15번 줄의 붙은 곳이 원문과 달라. 목록에는 주 펌프 (A)와 예비 펌프 (B) 두 곳이 적혀 있어.」처럼 어느 줄이 어떻게 다른지를 말한다.</div></div>')
+nxt(2,'2. 빈자리를 정해 주고, 계획부터 받는다',0))

# ============================== 2단계
dec='<table class="res"><thead><tr><th style="white-space:nowrap">줄</th><th>복사 상자에 든 답과 그 까닭</th><th>다른 길 (그 줄을 이렇게 바꾼다)</th></tr></thead><tbody>'\
'<tr><td style=\"white-space:nowrap\"><b>1</b><br>클래스</td><td><b>여섯으로 나눈다.</b> 계장 24줄 안의 유온 센서와 팬 인버터는 하는 일이 다르다(재는 것 · 바꾸는 것). 「유온」은 센서가 아니라 센서가 재는 물리량이어서 따로 둔다</td><td>목록의 「구분」 넷을 그대로 클래스로 쓴다. 만들기는 쉽지만 유온의 한계 65를 적을 자리가 센서밖에 없다</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>2</b><br>세 대</td><td><b>노드 하나를 세 설비가 함께 가리킨다.</b> 세 대는 같은 기종이다. 따로 만들면 고칠 곳이 세 배가 된다</td><td>설비마다 노드를 따로 만든다. 「HYD-02의 쿨러」를 따로 가리킬 수 있지만 노드가 세 배가 되고, 식별자에 설비 번호가 들어가야 한다</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>3</b><br>식별자</td><td><b>접두사:영문 소문자. 센서는 태그를 쓴다.</b> 이름은 팀마다 다르고 태그는 누가 적어도 같다. 접두사는 같은 태그를 쓰는 센서와 물리량을 갈라 준다</td><td>한글 이름을 그대로 식별자로 쓴다. 읽기는 쉽지만 「오일 쿨러」와 「열교환기」가 둘이 된다</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>4</b><br>다른 이름</td><td><b>노드 하나의 aliases 에 모은다. 55번은 38번과 같은 장치로 본다</b></td><td>55번 줄은 넣지 않고, 확인이 필요하다는 것만 답에 적게 한다</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>5 · 6</b><br>값의 자리</td><td><b>정상과 한계는 상태 변수의 속성. 값이 없으면 속성을 적지 않는다. CE는 센서로 두고 virtual 로 표시한다.</b> 48과 65는 센서 TS1의 성질이 아니라 유온의 성질이다. 센서를 바꿔 달아도 한계는 65다</td><td>정상과 한계를 센서의 속성으로 둔다(이때 1번 줄에서 상태 변수를 빼야 앞뒤가 맞는다)</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>7</b><br>관계</td><td><b>영문 이름과 방향은 AI가 제안하고, 읽은 문장을 함께 받는다.</b> 이름을 내가 지을 필요는 없다. 방향이 맞는지를 내가 읽을 수 있으면 된다</td><td>관계도의 한글 이름을 내가 영문으로 정해 적어 준다</td></tr>'\
'<tr><td style=\"white-space:nowrap\"><b>8 · 9</b><br>범위</td><td><b>관계도에만 있는 증상, 고장 유형, 원인, 조치도 넣는다. 세 대를 모두 넣는다.</b> 넣지 않으면 4단계의 대조에서 화살표 여덟 개가 「파일에 없음」이 된다</td><td>목록에 있는 것만 넣는다 / HYD-01 한 대만 넣는다</td></tr>'\
'</tbody></table>'
pages.append(hero('2단계','빈자리를 정해 주고,<br>계획부터 받는다','Copilot이 되물은 것은 귀찮은 질문이 아니라 온톨로지의 설계 그 자체다. 클래스를 넷으로 둘지 여섯으로 둘지, 세 대의 TS1을 하나로 볼지 셋으로 볼지에 따라 파일이 달라진다. 정답이 하나가 아니므로 <b>설계하는 사람이 정한다.</b> 이 단계의 요청은 그 결정 아홉 줄이다. 글은 준비되어 있으니, 줄마다 무엇을 왜 그렇게 정했는지를 읽고 받아들일지 바꿀지를 고른다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','결정 아홉 줄이 반영된 계획이 채팅에 있다'),('아직 없어야 하는 것','새 파일')])
+'<section class="sect"><h2>정의와 실제 대상을 나누어 적는다</h2><p>관계도에서는 「센서」라는 종류와 「유온 센서 TS1」이라는 실제 대상이 같은 모양의 노드였다. 파일에서는 둘을 다른 곳에 적는다. 이 단계에서 정하는 것은 윗줄의 모양과, 아랫줄의 대상을 가리키는 식별자의 규칙이다.</p>'+fig_layers+'</section>'
+do(1,'editor','이 화면의 표','아홉 줄의 결정을 읽고, 갈림길에서 고른다','<p>아래 표의 「줄」은 다음 할 일의 복사 상자에 든 요청의 번호다. 가운데 칸이 준비된 답이고, 오른쪽 칸이 다른 길이다. 온라인에서 본 HYD의 선택(설비, 구성 요소, 센서, 상태 변수, 부품)과 가운데 칸이 어디가 같고 어디가 다른지도 본다.</p>'+dec+'<div class="note"><b>처음에는 그대로 보내기를 권한다</b>완성 폴더와 다음 회차의 시작 자료가 가운데 칸의 답으로 만들어져 있어서, 그대로 보내면 뒤의 단계에서 가이드의 그림과 내 결과를 바로 견줄 수 있다. 다른 길을 가 보고 싶으면 입력 칸에 붙여넣은 뒤 그 번호의 줄만 고쳐서 보낸다. 그때는 뒤 단계의 수(노드 33개 등)와 식별자가 가이드와 달라진다.</div>')
+do(2,'chat','Copilot 채팅 · 입력 칸','결정 아홉 줄을 보내고, 계획을 먼저 받는다','<p>1단계와 같은 대화에 이어서 보낸다.</p>'+copy(P2,pre=True)+'<div class="parts"><div class="a"><b>번호를 붙였다</b>결정 하나에 한 줄이다. Copilot도 나도 빠뜨린 것을 번호로 짚을 수 있다.</div><div class="b"><b>까닭을 함께 적었다</b>「세 대는 구조가 같으므로」처럼 까닭이 있으면, 규칙이 닿지 않는 곳에서 AI가 같은 방향으로 판단한다.</div><div class="c"><b>마지막 문단</b>바로 만들지 말고 계획을 말하라는 것, 그리고 내가 빠뜨린 결정을 모아서 물으라는 것이다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 세 가지를 찾는다','<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 「이렇게 만들겠다」와 「이것은 정해 달라」가 함께 온다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 식별자 표와 관계 제안 표, 「정해 주셔야 하는 것」이 보이게(길면 두 장). 다시 물어 온 항목에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>식별자 표</b><span>3번 줄의 규칙대로 붙었는가. 규칙이 닿지 않아 Copilot이 고른 것은 어느 것인가. 태그가 없는 장치의 식별자에 쓰인 영어 낱말이 그런 것이다. 이 표를 지우지 말고 둔다. 4단계에서 다시 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>관계를 읽은 문장</b><span>관계마다 「시작은 끝을 ~한다」로 읽어 본다. 화살표의 방향과 문장의 주어가 맞는가. 「고장 유형은 조치로 완화된다」와 「조치는 고장 유형을 완화한다」는 같은 사실이지만 방향이 반대다.</span></p></div><div><i>③</i><p style="margin:0"><b>다시 물어 온 것</b><span>아홉 줄을 정해 주었는데도 빈자리가 더 나온다. 물음마다 Copilot이 권하는 쪽이 적혀 있는지 본다. 그 가운데 <b>한계의 방향</b>(65는 넘으면 안 되고 130은 내려가면 안 된다는 것을 어디에 적을지)과 <b>태그와 신호 이름</b>을 어떤 속성에 적을지에 대한 물음이 있는지 찾는다. 다음 단계에서 이 둘에 답한다.</span></p></div></div><div class="note"><b>계획부터 받는 까닭</b>계획을 받지 않고 바로 만들게 했다면, 이 결정들은 내가 모르는 사이에 내려져 파일에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.</div><div class="if"><div><b>계획이 아니라 파일이 생겼다면</b>마지막 문단이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.</div><div><b>물음에 권하는 쪽이 적혀 있지 않다면</b>「네가 권하는 쪽과 그 까닭을 물음마다 한 줄로 말해 줘」라고 되묻는다. 권하는 쪽을 받더라도 받겠다고 말하는 것은 나다.</div></div>')
+nxt(3,'3. 정의 파일 하나만 먼저 만든다',1))

# ============================== 3단계
ans='<table class="res"><thead><tr><th>물음</th><th>복사 상자에 든 답과 그 까닭</th><th>다른 길 (그 줄을 이렇게 바꾼다)</th></tr></thead><tbody>'\
'<tr><td style="white-space:nowrap"><b>한계의 방향</b></td><td><b>목록 비고의 문장을 limit_note 에 그대로 옮긴다.</b> 유온 줄의 비고는 「65 ℃에서 인터록」뿐이어서 위쪽 한계라고는 적혀 있지 않다. 위 · 아래로 나누어 적게 하면 AI가 짐작해야 한다. 규칙은 짐작을 막고 있다</td><td>위쪽 한계인지 아래쪽 한계인지를 적는 속성을 둔다. 이때는 목록에 방향이 적혀 있지 않은 줄을 어떻게 할지도 함께 정해 주어야 한다</td></tr>'\
'<tr><td style="white-space:nowrap"><b>태그와 신호 이름</b></td><td><b>센서는 tag, 구동기는 signal 로 나눈다.</b> 목록이 둘을 다른 말로 부른다. 현장의 말을 속성 이름에 남긴다</td><td>둘 다 tag 로 적는다. 속성이 하나 줄지만 TS1과 FanSpeedSP가 같은 종류의 이름처럼 보인다</td></tr>'\
'<tr><td style="white-space:nowrap"><b>그 밖의 물음</b></td><td><b>Copilot이 권한 쪽으로 한다.</b> 물음의 수와 번호는 사람마다 다르게 나오므로 번호로 답하지 않고 한 줄로 받는다</td><td>권한 것 가운데 받지 않을 것이 있으면 「○○는 권한 것과 달리 …로 한다」를 한 줄 더한다</td></tr>'\
'</tbody></table>'
pages.append(hero('3단계','정의 파일 하나만<br>먼저 만든다','이제 만들게 한다. 다만 한 번에 전부가 아니라 <code>schema.json</code> 한 파일에서 멈추게 한다. 정의와 실제 대상이 한꺼번에 생기면, 결과가 이상할 때 정의가 잘못된 것인지 정의는 맞는데 잘못 채운 것인지를 가릴 수 없다. <b>정의를 먼저 읽어 확인하고, 그다음에 채운다.</b>',[('걸리는 시간','약 5분'),('이 단계가 끝나면','결과/schema.json 한 파일이 있다'),('아직 없어야 하는 것','graph.json, 대조표.md')])
+do(1,'chat','Copilot 채팅 · 입력 칸','계획의 물음에 답하고, 만들 범위를 정해 준다','<p>계획에서 Copilot이 물어 온 것에 답한다. 아래 표가 복사 상자의 앞 세 줄이다.</p>'+ans+copy(P3,pre=True)+'<div class="parts"><div class="a"><b>앞의 세 줄</b>물음에 대한 답이다. 받는 것은 받는다고, 따로 정하는 것은 어떻게 정하는지를 까닭과 함께 적었다.</div><div class="b"><b>둘째 문단: 약속을 파일에 적게 한다</b>식별자의 규칙, 노드를 함께 쓴다는 결정은 지금 대화에만 있다. <code>conventions</code>에 문장으로 적어 두어야 다음 단계에서 이 파일만 보고 노드를 만들 수 있다.</div><div class="c"><b>셋째 문단: 범위</b>이번에 만들 것은 <code>결과/schema.json</code> 한 파일뿐이다.</div></div>')
+do(2,'chat','Copilot 채팅','파일을 만들어도 되는지 물으면, 경로를 읽고 허용한다','<p>Copilot이 파일을 만들려 할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 경로가 <code>결과/schema.json</code>이 맞는지 읽는다. 물음을 읽지 않고 넘기는 버릇은 뒤의 실습에서 문제가 된다.</p>'+shot('Copilot이 schema.json을 만들면서 허용을 묻거나 변경을 보여 주는 화면. 파일 경로와 「유지/허용」 버튼이 보이게.'))
+do(3,'editor','VS Code · 편집기','만들어진 <code>schema.json</code>을 열어 읽는다','<p>탐색기에서 <code>결과/schema.json</code>을 연다. 이 파일은 AI가 썼지만, 앞으로 노드와 관계는 모두 여기 적힌 대로 만들어진다. 네 칸을 차례로 본다.</p><table class="res"><thead><tr><th>칸</th><th>무엇을 보는가</th></tr></thead><tbody><tr><td><code>conventions</code></td><td>2단계의 결정이 문장으로 들어 있는가. 식별자의 규칙, 노드를 함께 쓰는 방식, 다른 이름, 값이 없을 때. 이 문장만 읽고 처음 보는 사람이 같은 식별자를 붙일 수 있겠는가</td></tr><tr><td><code>classes</code></td><td>클래스가 열 개인가(목록의 여섯과 관계도의 넷). 클래스마다 <code>description</code>이 어떤 대상을 받는지 한 줄로 말하는가. 속성 가운데 <code>required</code>가 <code>true</code>인 것은 무엇인가</td></tr><tr><td><code>relationships</code></td><td><code>from</code>에서 <code>to</code>로 읽은 문장이 <code>description</code>과 맞는가</td></tr><tr><td>없어야 하는 것</td><td>HYD-01, TS1, 오일 쿨러 같은 실제 대상. 이 파일은 정의만 담는다</td></tr></tbody></table><p>아래는 완성 폴더의 <code>schema.json</code>에서 클래스 하나와 관계 하나를 옮긴 것이다. 내 파일의 같은 자리와 견준다. 관계의 영문 이름과 <code>required</code>는 내 것과 다를 수 있다.</p><div class="tree" style="white-space:pre-wrap">'+e(sensor_def)+'\n\n'+e(rel_def)+'</div><div class="if"><div><b>정해 준 것과 다르게 적혀 있다면</b>지금 고친다. 「정상값과 한계는 센서가 아니라 상태 변수의 속성으로 두라고 했어. Sensor의 properties에서 그 둘을 빼고 StateVariable로 옮겨 줘. 다른 클래스는 건드리지 마.」처럼 어디가 어떻게 다른지를 말한다.</div><div><b>다른 파일도 생겼다면</b>요청의 셋째 문단이 빠진 것이다. 생긴 파일을 지우고 「schema.json 한 파일만」이라고 다시 말한다.</div></div>')
+nxt(4,'4. 새 대화에서 채우고, 관계도와 대조한다',2))

# ============================== 4단계
pages.append(hero('4단계','새 대화에서 채우고,<br>관계도와 대조한다','정의에 맞춰 실제 대상을 채운다. 지금까지의 대화에는 정해 준 것이 모두 들어 있어서, 같은 대화에서 채우면 <code>schema.json</code>을 따른 것인지 앞의 대화를 기억해 채운 것인지 구분할 수 없다. <b>새 대화를 열어 파일만으로 채우게 한다.</b> 다른 사람이 내 <code>schema.json</code>을 받아 같은 일을 하는 상황과 같다. 채운 뒤에는 관계도의 화살표 15개와 하나씩 맞대어 본다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','결과/graph.json과 결과/대조표.md가 있다'),('맞춰 볼 것','노드의 수, 빈칸, 식별자, 판정')])
+do(1,'chat','Copilot 채팅 · 새 대화','새 대화를 열고 아래 요청을 보낸다','<p>채팅 위쪽의 「새 채팅」(+) 단추로 새 대화를 연다.</p>'+shot('채팅 위쪽의 새 채팅 단추의 위치. 단추에 빨간 테두리를 얹는다.')+copy(P4)+'<div class="parts"><div class="a"><b>읽을 것을 다시 적었다</b>새 대화는 앞의 대화를 모른다. 규칙, <code>schema.json</code>, 자료를 읽게 한다.</div><div class="b"><b>범위와 파일 하나</b>넣을 범위는 2단계의 8 · 9번 줄과 같다. 그 줄을 바꿔 보냈다면 여기 둘째 문장도 같게 고친다.</div><div class="c"><b>세어 보게 하고, 스스로 정한 것을 밝히게 한다</b>수는 내가 검산할 재료이고, 「네가 정한 것」은 <code>schema.json</code>에 아직 구멍이 있다는 신호다.</div></div><p style="margin-top:16px">1분 남짓 뒤에 <code>결과/graph.json</code>이 생긴다.</p>')
+do(2,'editor','VS Code · 편집기 (좌우로 나란히)','<code>graph.json</code>을 목록과 나란히 놓고 본다','<p><code>결과/graph.json</code>을 열고, <code>자료/설비_계기_목록.md</code>를 오른쪽으로 끌어 나란히 둔다. 목록의 한 줄이 파일에서 어떻게 나뉘었는지를 8번 줄로 따라가 본다.</p>'+fig_row+'<div class="find"><div><i>①</i><p style="margin:0"><b>노드의 수</b><span>목록은 55줄인데 노드는 몇 개인가. 완성 폴더는 노드 '+str(len(G['nodes']))+'개, 관계 '+str(len(G['rels']))+'개다(설비 '+str(ncls['Asset'])+', 구성 요소 '+str(ncls['Component'])+', 센서 '+str(ncls['Sensor'])+'). 세 대가 노드를 함께 쓰므로 센서 노드는 15개가 아니라 5개이고, 설비에서 구성 요소로 가는 관계는 '+str(nrel['HAS_COMPONENT'])+'개(3 × 6)다.</span></p></div><div><i>②</i><p style="margin:0"><b>빈칸</b><span>유량(FS1)의 한계는 목록에 없다. 파일에서 그 속성이 아예 빠져 있는가. <code>0</code>이나 <code>null</code>, 다른 줄에서 가져온 값이 들어가 있으면 지어낸 것이다.</span></p></div><div><i>③</i><p style="margin:0"><b>식별자가 2단계의 표와 같은가</b><span>2단계 계획의 식별자 표와 지금 파일의 <code>id</code>를 견준다. 태그를 쓴 것(<code>sen:ts1</code>)은 같을 것이다. 영어로 옮긴 말을 쓴 것 가운데 달라진 것이 있는가. 있으면 적어 둔다. 6단계의 재료다.</span></p></div></div>'+shot('graph.json과 설비_계기_목록.md 미리 보기를 좌우로 나란히 연 VS Code 화면. graph.json 쪽은 sen:ts1과 sv:ts1 노드가 보이게.'))
+do(3,'chat','Copilot 채팅 · 입력 칸','대조표를 만들게 하고, 판정을 읽는다','<p>같은 대화에 이어서 보낸다. 「고치지 마」로 끝나는 것을 눈여겨본다. 대조는 견주는 일이지 맞추는 일이 아니다. 이 문장이 없으면 AI는 어긋난 곳을 보자마자 파일을 고쳐 「같음」으로 만들어 버릴 수 있다.</p>'+copy(P5)+'<p><code>결과/대조표.md</code>가 생기면 미리 보기로 열어 「판정」 칸을 위에서 아래로 훑는다. 아래는 완성 폴더의 대조표에서 네 줄을 옮긴 것이다.</p>'+ctable+'<div class="find"><div><i>①</i><p style="margin:0"><b>「다르게 표현」이 된 화살표</b><span>완성 폴더에서는 5번과 6번이다. 관계도의 「센서」 노드는 파일에서 노드가 아니라 클래스가 되었고, 「65 ℃」 노드는 노드가 아니라 속성의 값이 되었다. 준비에서 두 노드가 나머지와 다르다고 한 까닭이 이것이다. 종류는 클래스로, 값은 속성으로, 실제 대상만 노드로 적는다.</span></p></div><div><i>②</i><p style="margin:0"><b>「같음」을 믿어도 되는가</b><span>두 줄을 골라 「파일의 표현」에 적힌 관계를 <code>graph.json</code>에서 직접 찾아본다(Ctrl+F로 식별자를 찾는다). 대조표도 AI가 쓴 것이다.</span></p></div></div>'+shot('대조표.md의 미리 보기 화면. 「판정」 칸이 보이고, 「다르게 표현」인 줄에 테두리를 얹는다.')+'<div class="if"><div><b>graph.json을 만들지 않고 되물었다면</b><code>schema.json</code>에 적히지 않은 결정이 남아 있는 것이다. 물음에 답하되, 그 답을 <code>conventions</code>에도 한 문장으로 적어 달라고 함께 말한다.</div><div><b>노드가 설비마다 따로 생겼다면</b><code>conventions</code>에 「노드를 함께 쓴다」가 문장으로 적혀 있는지 본다. 없으면 그 문장을 넣게 하고 <code>graph.json</code>을 다시 만들게 한다.</div></div>')
+nxt(5,'5. 규칙에 어긋나는 요청을 일부러 보내 본다',3))

# ============================== 5단계
rtab='<table class="res"><thead><tr><th>보낸 요청</th><th>규칙 파일에서 찾을 줄</th><th>어느 절인가</th></tr></thead><tbody>'\
'<tr><td>목록의 줄을 지우고 이름을 고쳐 달라</td><td>'+rule('1. ')+'</td><td style="white-space:nowrap">하면 안 되는 것 1</td></tr>'\
'<tr><td><code>rels</code>, <code>a</code>, <code>b</code>의 이름을 바꿔 달라</td><td>'+rule('- 맨 위의 칸은 둘이다')+'</td><td style="white-space:nowrap">정해져 있는 것</td></tr>'\
'<tr><td>이번만 예외로 해 달라</td><td>'+md(rule('6. ').split('어긋나는 요청')[0].strip())+'</td><td style="white-space:nowrap">하면 안 되는 것 6</td></tr>'\
'</tbody></table>'
pages.append(hero('5단계','규칙에 어긋나는 요청을<br>일부러 보내 본다','지금까지는 규칙 안에서만 요청했다. 그런데 일을 하다 보면 「목록이 지저분하니 원본을 정리해 버리자」「칸 이름을 내 입맛대로 바꾸자」 같은 요청이 나오기 마련이다. 한 사람이 그렇게 하면 옆 사람의 파일과 더는 합쳐지지 않는다. 규칙 파일이 그것을 실제로 막는지, <b>일부러 어긋나는 요청을 보내 확인한다.</b>',[('걸리는 시간','약 4분'),('이 단계가 끝나면','AI가 멈춘 까닭을 규칙 파일의 줄로 짚을 수 있다'),('바뀌면 안 되는 것','자료 폴더, graph.json')])
+do(1,'chat','Copilot 채팅 · 입력 칸','원본 자료를 고쳐 달라고 한다','<p>4단계의 대화에 이어서 보낸다. 2단계에서 「55번 줄은 38번과 같은 장치로 본다」고 정했으니, 아예 목록에서 지우자는 요청이다. 그럴듯하게 들리지만 규칙에 어긋난다.</p>'+copy(V1)+'<p>답에서 세 가지를 찾는다. <b>고치지 않았다</b>는 말이 있는가. <b>어느 규칙 때문인지</b>를 번호나 문장으로 밝혔는가. 규칙 안에서 같은 목적을 이루는 <b>다른 길</b>(원본은 두고 결과 파일에서 같은 노드로 다루기)을 내놓았는가.</p>'+shot('원본 자료를 고쳐 달라는 요청에 Copilot이 고치지 않겠다고 답한 화면. 규칙을 든 문장에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','정해진 칸 이름을 바꿔 달라고 한다','<p>이번에는 파일의 모양을 건드린다. 다른 도구에서 흔히 쓰는 이름으로 바꾸자는 요청이다.</p>'+copy(V2)+'<p>이번에도 멈추는가. 답이 든 규칙이 앞의 것과 같은 줄인가, 다른 줄인가.</p>')
+do(3,'chat','Copilot 채팅 · 입력 칸','한 번 더 밀어 본다','<p>규칙이 말뿐인지 보려면 한 번 더 밀어 보아야 한다.</p>'+copy(V3)+shot('「이번 한 번만 예외로 해 줘」에 대한 Copilot의 답. 예외를 두지 않는다는 규칙을 든 문장에 빨간 테두리를 얹는다.'))
+do(4,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 열어, Copilot이 든 규칙이 실제로 어디에 적혀 있는지 찾는다. 아래는 그 파일에서 옮긴 줄이다.</p>'+rtab+'<p>그리고 정말 바뀌지 않았는지 본다. <code>자료/설비_계기_목록.md</code>의 20번과 55번 줄이 그대로인가. <code>결과/graph.json</code>의 맨 위 칸이 여전히 <code>nodes</code>와 <code>rels</code>인가.</p><div class="note"><b>규칙을 바꾸는 길은 채팅이 아니라 파일이다</b>칸 이름을 정말 바꿔야 한다면 규칙 파일의 그 줄을 고치면 된다. 그러면 이 폴더를 쓰는 모든 사람의 결과가 함께 바뀐다. 채팅에서 한 사람이 「이번만」 하고 바꾸는 것과는 다른 일이다. 2단계에서 내가 정한 여덟 가지는 「정해져 있지 않은 것」이어서 물어 왔고, 방금 건드린 것은 「정해져 있는 것」이어서 멈춘 것이다.</div><div class="if"><div><b>Copilot이 멈추지 않고 고쳐 버렸다면</b>변경을 보여 주는 화면에서 「실행 취소」로 되돌린다. 이미 받아들였다면 완성 폴더의 <code>자료</code>에서 원본을 가져와 덮어쓴다. 그리고 방식이 에이전트인지, 규칙 파일이 <code>.github</code> 폴더에 그대로 있는지를 본다. 강사에게도 알린다.</div><div><b>어느 규칙인지 밝히지 않고 멈췄다면</b>「규칙 파일의 어느 줄 때문인지 그 문장을 그대로 보여 줘」라고 묻는다.</div></div>')
+nxt(6,'6. 아쉬운 곳을 내 말로 되돌려 준다',4))

# ============================== 6단계
bad='식별자가 마음에 안 들어. 다시 만들어 줘.'
good='conventions의 「이름을 영어로 옮긴 짧은 말」은 옮기는 사람마다 낱말이 달라져. 계획 때는 part:pump-seal-kit이었던 부품이 graph.json에서는 part:pump-shaft-seal-kit이 됐어. 같은 대상에 식별자가 둘이면 다른 사람의 파일과 합칠 때 노드가 둘로 갈라져. schema.json의 conventions에서 식별자를 만드는 문장만 고쳐 줘. 부품은 품번을 소문자로 바꿔 적는다. 그다음 graph.json과 대조표.md에서 그 id가 나오는 곳을 맞춰 줘. 클래스, 속성, 관계의 정의는 건드리지 마.'
pages.append(hero('6단계','아쉬운 곳을<br>내 말로 되돌려 준다','규칙은 어긋나는 것을 막아 줄 뿐, 결과를 더 낫게 만들어 주지는 않는다. 그 일은 내가 한다. 오늘 직접 글을 쓰는 곳은 여기 한 곳이다. 아쉬운 곳 하나를 골라 되돌려 주는데, <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','schema.json의 한 곳이 내 요청대로 바뀌어 있다'),('직접 쓰는 글','한 번')])
+'<section class="sect"><h2>같은 문제, 두 가지 말</h2><p>4단계에서 본 것처럼, 「이름을 영어로 옮긴 짧은 말」이라는 약속은 만드는 사람(또는 대화)마다 다른 식별자를 낳는다. 식별자는 하나뿐인 값이어야 하는데 약속이 그것을 지켜 주지 못한다. 이것을 되돌려 준다고 하자.</p><div class="vs"><div class="bad"><b>막연하게</b><q>'+e(bad)+'</q>무엇이 문제인지 AI는 모른다. 식별자를 전부 다른 낱말로 바꾸거나, 무엇을 원하는지 되묻는다. 약속은 그대로이므로 다음에 또 달라진다.</div><div class="good"><b>구체적으로</b><q>'+e(good)+'</q>한 번에 끝나고, 요청한 곳만 바뀐다. 약속이 바뀌었으므로 다음에 만들어도 같은 식별자가 나온다.</div></div><div class="four"><div><b>무엇이</b>같은 부품의 식별자가 두 가지로 나왔다</div><div><b>왜</b>합칠 때 노드가 둘로 갈라진다</div><div><b>어디를</b>graph.json이 아니라 schema.json의 그 문장</div><div><b>어디까지</b>정의는 건드리지 않는다</div></div><div class="note"><b>graph.json이 아니라 schema.json을 고치는 까닭</b><code>graph.json</code>의 식별자만 손으로 고치면 이번 한 번은 맞지만, 다음에 노드를 더할 때 예전 약속대로 다시 어긋난다. 기준을 고치면 그 기준으로 만드는 모든 것에 반영된다. 이 실습의 제목이 「같은 기준으로」인 까닭이다.</div></section>'
+do(1,'chat','이 화면의 글 칸 → Copilot 채팅','아쉬운 곳 하나를 골라, 네 가지를 넣어 쓴다','<p>내 결과에서 하나를 고른다. 4단계에서 적어 둔 달라진 식별자가 있으면 그것으로 한다. 없으면 아래에서 고른다.</p><ul class="ask"><li><b>식별자의 약속</b>태그나 품번처럼 목록에 이미 있는 번호를 쓰면 누가 만들어도 같다. 구동기와 부품의 식별자는 지금 무엇으로 만들어져 있는가.</li><li><b>두 번 적힌 줄</b>55번 줄은 목록에 「확인 필요」라고 적혀 있다. 같은 장치로 합쳤다면, 확인하지 않고 합쳤다는 사실이 파일의 어디에 남아 있는가.</li></ul><p>무엇이, 왜, 어디를, 어디까지. 네 가지를 넣어 쓰고, 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다.</p>'+write('w5','무엇이 문제인지, 왜 문제인지, schema.json의 어느 문장을 고칠지, 건드리지 말 곳을 적는다.')+'<details><summary>다 쓴 뒤에 견주어 볼 예</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">완성 폴더를 만들 때 보낸 글이다. 식별자의 낱말은 내 파일의 것으로 바꿔야 한다. 시간이 모자라면 이 글에서 낱말만 바꿔 보낸다.</p>'+copy(P('6_prompt.txt'),'Copilot에게 보낼 요청 (예)',pre=True)+'</details>')
+do(2,'editor','VS Code · 편집기','바뀐 곳과 바뀌지 않은 곳을 본다','<p>세 곳을 본다. <code>schema.json</code>에서 요청한 문장만 바뀌었는가. <code>graph.json</code>에서 바뀐 <code>id</code>를 쓰는 관계의 <code>a</code>와 <code>b</code>도 함께 바뀌었는가(한쪽만 바뀌면 관계가 없는 노드를 가리킨다). <code>대조표.md</code>의 해당 줄이 맞춰졌는가. 완성 폴더에서는 구동기와 부품의 식별자가 <code>'+e(node['actr:fanspeedsp']['props']['id'])+'</code>, <code>'+e(node['part:p-clr-core']['props']['id'])+'</code>처럼 신호 이름과 품번으로 바뀌었다.</p>'+shot('되돌려 준 뒤 Copilot이 schema.json과 graph.json의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색과 빨간색으로 표시된 화면).')+'<div class="if"><div><b>요청하지 않은 곳까지 바뀌었다면</b>바뀐 줄을 보여 주는 화면에서 그 부분을 되돌리고, 「어디까지」를 더 좁혀 다시 말한다.</div><div><b>고친 뒤에 관계가 끊겼다면</b>「graph.json의 rels에서 a나 b가 nodes에 없는 id인 줄을 찾아 알려 줘」라고 물어 어긋난 줄을 먼저 찾는다.</div></div>')
+nxt(7,'7. 입력을 바꿔 다시 돌리고, 만든 것을 써 본다',5))

# ============================== 7단계
pages.append(hero('7단계','입력을 바꿔 다시 돌리고,<br>만든 것을 써 본다','파일은 만들어 두려고 만드는 것이 아니다. 같은 기준으로 적었다면 다른 사람이 그린 관계도와도 견줄 수 있어야 하고, 목록을 보지 않은 사람(또는 AI)이 파일만 읽고도 물음에 답할 수 있어야 한다. 두 가지를 해 본다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','결과/대조표_2조.md가 있고, 파일만으로 얻은 답이 채팅에 있다'),('바뀌면 안 되는 것','schema.json, graph.json')])
+do(1,'chat','Copilot 채팅 · 새 대화','2조가 그린 관계도로 대조를 다시 돌린다','<p><code>자료/관계도/화살표_목록_2조.md</code>는 같은 쿨러 사건을 2조가 따로 그린 것이다(노드 11개, 화살표 9개). 화살표의 이름도 방향도 우리 것과 다르다. 새 대화를 열고, 4단계의 대조 요청에서 <b>읽을 목록과 만들 파일의 이름만 바꾼</b> 아래 요청을 보낸다.</p>'+copy(PD)+'<p><code>결과/대조표_2조.md</code>가 생기면 미리 보기로 연다. 이번에는 4단계에서 보지 못한 판정이 나온다. 아래는 완성 폴더에서 네 줄을 옮긴 것이다.</p>'+ctable2+'<div class="find"><div><i>①</i><p style="margin:0"><b>「방향 반대」는 누가 틀린 것인가</b><span>「오일 쿨러는 HYD-01에 속한다」와 「HYD-01은 오일 쿨러를 가진다」는 같은 사실이다. 어느 쪽도 틀리지 않았다. 다만 두 조의 파일을 합치려면 한 방향으로 정해야 하고, 그 방향이 적힌 곳이 <code>schema.json</code>의 <code>from</code>과 <code>to</code>다.</span></p></div><div><i>②</i><p style="margin:0"><b>「파일에 없음」은 어느 쪽을 고쳐야 하는가</b><span>9번 「팬 최대 운전은 팬 속도를 올린다」는 우리 관계도에 없던 화살표다. 2조가 잘못 그린 것인가, 우리 정의에 관계 하나가 빠진 것인가. 조치(Skill)에서 상태 변수(StateVariable)로 가는 관계가 <code>schema.json</code>에 있는지 찾아본다.</span></p></div><div><i>③</i><p style="margin:0"><b>처음의 대조표는 그대로인가</b><span><code>결과/대조표.md</code>가 덮어써지지 않았는지 본다. 규칙 파일에 다른 목록으로 대조할 때는 파일을 따로 만든다고 적혀 있다.</span></p></div></div>'+shot('대조표_2조.md의 미리 보기 화면. 「판정」 칸이 보이고, 「방향 반대」와 「파일에 없음」인 줄에 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 새 대화','목록을 보지 않고, 파일만으로 답하게 한다','<p>새 대화를 하나 더 열어 아래 요청을 보낸다. 생산팀은 장치를 자기들이 부르는 이름으로 묻는다(열교환기, 오일 온도, 토출 유량). 자료 폴더는 읽지 못하게 했으므로, 답은 <code>graph.json</code>에 적힌 것에서만 나와야 한다.</p>'+copy(PQ)+'<div class="find"><div><i>①</i><p style="margin:0"><b>다른 이름으로 물어도 찾았는가</b><span>「열교환기」와 「오일 온도」는 노드의 <code>name</code>이 아니다. 완성 폴더에서는 <code>'+e(co['id'])+'</code>와 <code>'+e(sv['id'])+'</code>의 <code>aliases</code>에 들어 있다. 2단계 4번 줄의 결정이 여기에서 쓰인다.</span></p></div><div><i>②</i><p style="margin:0"><b>HYD-02에서 출발해 어디를 거쳤는가</b><span>설비 → 구성 요소 → 센서 → 상태 변수의 차례로 식별자와 관계 이름이 적혀 있는가. 답 '+str(sv['limit'])+' '+e(sv['unit'])+'는 HYD-02만의 값이 아니라 세 대가 함께 쓰는 노드의 값이다. 2단계 2번 줄의 결정이다.</span></p></div><div><i>③</i><p style="margin:0"><b>없는 값을 없다고 했는가</b><span>유량의 한계는 목록에 없었고, 그래서 파일에도 속성이 없다. 정상값 '+str(node['sv:fs1']['props']['normal'])+'이나 토출 압력의 한계를 끌어다 답했다면 지어낸 것이다.</span></p></div></div>'+shot('파일만으로 답하게 한 요청에 대한 Copilot의 답. 따라간 노드와 관계가 차례로 적힌 부분과, 유량의 한계가 없다고 답한 부분이 보이게.')+'<div class="if"><div><b>열교환기를 찾지 못했다면</b><code>graph.json</code>에서 오일 쿨러 노드의 <code>aliases</code>를 본다. 비어 있으면 2단계 4번 줄의 결정이 <code>conventions</code>에 적히지 않았거나, 채울 때 빠진 것이다.</div><div><b>자료 폴더를 읽고 답했다면</b>파일이 아니라 목록에서 답을 가져온 것이다. 「자료 폴더는 읽지 말고 두 파일만으로 다시 답해 줘」라고 말한다.</div></div>')
+'<section class="sect"><h2>시간이 남으면</h2><p><b>빠진 관계를 정의에 더한다.</b> 2조의 9번 화살표를 받아들이기로 했다면 새 대화에서 아래 요청을 보낸다. 정의를 고치는 일이므로, 보내기 전에 탐색기에서 <code>schema.json</code>과 <code>graph.json</code>을 복사해 다른 이름으로 남겨 둔다. 요청에 관계의 영문 이름이 없으므로 Copilot은 고치지 않고 이름부터 물어 온다. 규칙 파일의 어느 줄 때문인지 짚어 보고, 이름을 정해 준 뒤 2조 대조를 다시 돌려 9번의 판정이 바뀌는지 본다.</p>'+copy(P('12_prompt.txt'))+'<p style="margin-top:16px"></p><p><b>내 관계도로 대조한다.</b> 앞 실습에서 내가 그린 관계도의 화살표를 <code>화살표_목록_2조.md</code>와 같은 표 모양으로 적어 달라고 하고(화살표를 채팅에 불러 준다), 그 목록으로 대조표를 한 번 더 만들게 한다. 자료 폴더에는 새 파일을 만들 수 없으므로 어디에 둘지는 Copilot이 물어 올 것이다.</p><p><b>관계마다 몇 대 몇인지를 적는다.</b> 온라인 2일차에서 본 카디널리티(1:N, N:1, N:M)를 <code>relationships</code>의 칸으로 더하게 한다. 세 설비가 구성 요소 노드 하나를 함께 가리키므로 설비와 구성 요소의 관계는 1:N이 아니다. 그런데 관계의 칸은 규칙 파일의 「정해져 있는 것」이다. Copilot이 어떻게 답하는지 본다.</p><p><code>schema.json</code>은 지우지 않는다. 이 회차의 마지막 실습에서 포털의 지식 지도와 견주어 고친다.</p></section>'
+nxt(None,None,6))

names=['준비','1. 읽게 한다','2. 정하고 계획 받기','3. 정의 파일 만들기','4. 채우고 대조하기','5. 규칙을 건드려 보기','6. 되돌려 주기','7. 바꿔 돌리고 써 보기']
bar='<div class="bar"><div class="bar-in"><b>설비 목록 → 클래스 · 인스턴스 · 식별자</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-01-2-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 7단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 설비 목록을 클래스, 인스턴스, 식별자로 나누기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
