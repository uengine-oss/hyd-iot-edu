"""통합반 오프라인 02회차 실습 3 「새로운 설비에도 같은 지식 구조 적용하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_통합반오프02_실습1.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다.
시작/결과/ 는 02회차 실습 1의 완성본이다. 가이드의 표와 그림의 값은 시작/ · 기록/ · 완성/ 의 파일에서 읽어 옮기고,
질의와 검사의 결과는 완성/ 의 프로그램을 이 스크립트가 실제로 실행해 받은 것을 옮긴다.
실행: python3 lab/도구/가이드_만들기_통합반_오프라인_02회차_실습3.py
"""
import re, html, json, os, subprocess, sys
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R=LAB+'/통합반_오프라인/02회차_실습3_새_설비_적용/'
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
table.res caption{caption-side:top;text-align:left;font-weight:800;font-size:15px;padding:0 4px 8px}
table.res tfoot td{background:#f6f8fa;font-weight:700;white-space:normal}
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
.copy-text.cmd{font-family:Consolas,"D2Coding",monospace;font-size:16px}
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
.pair{display:grid;grid-template-columns:1fr;gap:6px}
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
<rect x="163" y="36" width="183" height="{c('term','170','280')}" rx="8" fill="{c('editor','#eaf0ff','#fff')}" stroke="{c('editor','#2f5bea','none')}" stroke-width="3"/>
<text x="175" y="56" font-size="11" font-weight="800" fill="{c('editor','#2f5bea','#5b6573')}">편집기</text>
<rect x="175" y="70" width="150" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="88" width="120" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="106" width="158" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="124" width="96" height="8" rx="4" fill="#dfe4ec"/><rect x="175" y="142" width="140" height="8" rx="4" fill="#dfe4ec"/>
{c('term','<rect x="163" y="212" width="183" height="104" rx="8" fill="#eaf0ff" stroke="#2f5bea" stroke-width="3"/><text x="175" y="232" font-size="11" font-weight="800" fill="#2f5bea">터미널</text><rect x="175" y="244" width="120" height="8" rx="4" fill="#b9c8f5"/><rect x="175" y="262" width="150" height="8" rx="4" fill="#d3dcf7"/><rect x="175" y="280" width="96" height="8" rx="4" fill="#d3dcf7"/>','')}
<rect x="352" y="40" width="160" height="272" rx="10" fill="{c('chat','#f3eeff','#f6f8fa')}" stroke="{c('chat','#6a3fd1','#e4e8ee')}" stroke-width="3"/>
<text x="366" y="62" font-size="12" font-weight="800" fill="{c('chat','#6a3fd1','#5b6573')}">Copilot 채팅</text>
<rect x="366" y="76" width="118" height="26" rx="8" fill="#fff"/><rect x="380" y="112" width="118" height="40" rx="8" fill="{c('chat','#e2d6fb','#e9edf3')}"/><rect x="364" y="264" width="136" height="36" rx="10" fill="#fff" stroke="{c('chat','#6a3fd1','#cfd6e0')}" stroke-width="2"/></svg>'''
ICO={'chat':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#6a3fd1"/><rect x="22" y="3" width="9" height="16" rx="2" fill="#6a3fd1"/></svg>',
'explorer':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="3" y="3" width="8" height="16" rx="2" fill="#2f5bea"/></svg>',
'editor':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="12" y="3" width="9" height="16" rx="2" fill="#2f5bea"/></svg>',
'term':'<svg viewBox="0 0 34 22"><rect x="1" y="1" width="32" height="20" rx="4" fill="#fff" stroke="#2f5bea"/><rect x="12" y="12" width="9" height="7" rx="2" fill="#2f5bea"/></svg>'}
def where(k,label): return f'<span class="where {"w-chat" if k=="chat" else "w-code"}">{ICO[k]}{label}</span>'
cid=[0]
CHAT_FOOT='붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸'
def copy(text,head='Copilot에게 보낼 요청',pre=False,rich=None,foot=CHAT_FOOT,cls=''):
    cid[0]+=1; i=f'c{cid[0]}'
    body=rich if rich else e(text)
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}{cls}" id="{i}">{body}</div><div class="copy-foot">{foot}</div></div>'
def cmd(text): return copy(text,'터미널에서 실행할 명령',foot='붙여넣는 곳 → VS Code 아래쪽 터미널 (메뉴의 「터미널 → 새 터미널」)',cls=' cmd')
shots=[]
def shot(desc):
    shots.append(desc); n=len(shots)
    return f'<div class="shot"><div><b>사진 {n} — 찍어 주실 화면</b><span>{desc}</span></div></div>'
def write(i,ph): return f'<textarea id="{i}" data-draft="{i}" placeholder="{e(ph)}"></textarea><div class="wfoot"><button data-copy="{i}">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸 · 쓴 글은 이 브라우저에 저장된다</span></div>'
def do(n,k,label,title,body): return f'<section class="do" data-n="{n}">{where(k,label)}<h2>{title}</h2>{body}</section>'
def hero(no,title,lead,facts): return f'<section class="hero"><div class="no">{no}</div><h1>{title}</h1><p>{lead}</p><div class="facts">'+''.join(f'<div><small>{a}</small>{b}</div>' for a,b in facts)+'</div></section>'
def mapbox(k,title,text): return f'<section class="map"><div>{vs(k)}</div><div><h2>{title}</h2>{text}</div></section>'
def nxt(i,label,prev=None):
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 한 글자도 바뀌지 않은 결과/schema.json, HYD-04가 더해진 결과/graph.json, 어느 설비에나 통하는 결과/질의.py</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
J=lambda p: json.load(open(R+p,encoding='utf-8'))
def hl(text,*marks):
    h=e(text)
    for s,c in marks:
        assert e(s) in h,s
        h=h.replace(e(s),f'<span class="{c}">{e(s)}</span>')
    return h

# ── 시작/ · 기록/ · 완성/ 의 파일에서 옮기는 값 ──
S0=J('시작/결과/schema.json'); G0=J('시작/결과/graph.json')
S=J('완성/결과/schema.json'); G=J('완성/결과/graph.json')
assert S==S0, '완성본의 스키마는 시작과 같아야 한다'
assert J('기록/4_graph_after.json')==G
RULE=open(R+'시작/.github/copilot-instructions.md',encoding='utf-8').read()
assert RULE==open(R+'완성/.github/copilot-instructions.md',encoding='utf-8').read()
cnt=lambda Gx,L: sum(1 for n in Gx['nodes'] if n['labels'][0]==L)
rc=lambda Gx,T: sum(1 for r in Gx['rels'] if r['type']==T)
node=lambda Gx,i: next(n['props'] for n in Gx['nodes'] if n['props']['id']==i)
rel=lambda T: next(r for r in S['relationships'] if r['type']==T)
old_ids={n['props']['id'] for n in G0['nodes']}
NEW=[n for n in G['nodes'] if n['props']['id'] not in old_ids]
old_rel={(r['type'],r['a'],r['b']) for r in G0['rels']}
NEWR=[r for r in G['rels'] if (r['type'],r['a'],r['b']) not in old_rel]
assert all(n in G['nodes'] for n in G0['nodes']) and all(r in G['rels'] for r in G0['rels'])
def run(folder,*args):
    """묶음 안의 프로그램을 실제로 실행해 출력을 받는다."""
    out=subprocess.run([sys.executable,*args],cwd=R+folder,capture_output=True,text=True,encoding='utf-8')
    return out.stdout.rstrip('\n')
def tables(text):
    """질의.py 가 낸 글자 표를 [(제목, 머리, 줄들, 아랫줄)] 로 읽는다."""
    out=[]
    for block in text.split('\n\n') if '\n\n' in text else re.split(r'\n(?=\[)',text):
        lines=block.strip().split('\n'); title=lines[0].strip('[]')
        rows=[[c.strip() for c in l.strip('|').split('|')] for l in lines[1:] if l.startswith('|') and not l.startswith('|-')]
        tail=[l for l in lines[1:] if not l.startswith('|')]
        out.append((title,rows[0] if rows else [],rows[1:],' '.join(tail)))
    return out
def res(title,head,rows,tail,mark=()):
    def cell(c):
        h=e(c)
        for m in mark: h=h.replace(e(m),f'<mark>{e(m)}</mark>')
        return h
    if not head: return f'<table class="res"><caption>{e(title)}</caption><tbody><tr><td style="white-space:normal">{e(tail)}</td></tr></tbody></table>'
    return (f'<table class="res"><caption>{e(title)}</caption><thead><tr>'+''.join(f'<th>{e(h)}</th>' for h in head)+'</tr></thead><tbody>'
            +''.join('<tr>'+''.join(f'<td>{cell(c)}</td>' for c in r)+'</tr>' for r in rows)+f'</tbody><tfoot><tr><td colspan="{len(head)}">{e(tail)}</td></tr></tfoot></table>')

Q_AFTER=run('완성','결과/질의.py','HYD-01','HYD-04')
assert Q_AFTER==P('5_질의_실행.txt'), '완성본의 질의 결과가 기록과 다르다'
Q_BEFORE=P('2_질의_실행.txt')
T_AFTER=tables(Q_AFTER); T_BEFORE=tables(Q_BEFORE)
assert T_BEFORE[0]==T_AFTER[0], 'HYD-01 의 결과는 HYD-04 를 넣기 전과 같아야 한다'
Q_PART=run('완성','결과/질의.py','--부품','P-FAN-BRG'); T_PART=tables(Q_PART)[0]
assert Q_PART in P('7_질의_실행.txt')
CHK0=run('시작','도구/검사.py'); CHK=run('완성','도구/검사.py')
assert CHK==P('5_검사_실행.txt')
line5=next(l for l in CHK.split('\n') if l.startswith('  - USES_PART'))
# 2단계에서 만든 질의.py 는 4단계를 지나도 그대로였다(기록). 완성본은 7단계에서 거꾸로 가는 질의가 더해진 것이다.
QPY2=P('2_질의_after.py'); QPY=open(R+'완성/결과/질의.py',encoding='utf-8').read()
body=re.sub(r'""".*?"""','',QPY,flags=re.S)
assert not re.search(r'HYD-|P-FAN|P-CLR|P-PMP|["\'](asset|comp|sen|sv|part):',body), '질의.py 안에 특정 대상의 식별자나 이름이 있다'

comp_of=lambda G_,a: [r['b'] for r in G_['rels'] if r['type']=='HAS_COMPONENT' and r['a']==a]
C01=comp_of(G,'asset:hyd-01'); C04=comp_of(G,'asset:hyd-04')
SHARED=[c for c in C04 if c in C01]; OWN=[c for c in C04 if c not in C01]
assert len(SHARED)==4 and len(OWN)==3
fan_users=[r['a'] for r in G['rels'] if r['type']=='USES_PART' and r['b']=='part:p-fan-brg']
assert len(fan_users)==3

P1=P('1_prompt.txt'); P2=P('2_prompt.txt'); P3=P('3_prompt.txt'); P4=P('4_prompt.txt'); P6a=P('6a_prompt.txt'); P6b=P('6b_prompt.txt'); P7=P('7_prompt.txt'); P8=P('여유_prompt.txt')
P1rich=hl(P1,('이 폴더의 규칙(.github/copilot-instructions.md)과 결과/schema.json, 결과/graph.json, 새_설비 폴더의 파일을 모두 읽어 줘.','p-a'),('아직 아무것도 만들거나 고치지 마.','p-c'),('이미 있는 노드와 같은 대상으로 보이는 것과 새 노드가 있어야 하는 것을 갈라 줘.','p-b'))
P2rich=hl(P2,('HYD-04 를 넣기 전에, 지금 그래프에서 통하는 질의부터 만든다.','p-a'),('graph.json 과 schema.json 은 고치지 마.','p-c'),('python 결과/질의.py HYD-01 HYD-04 를 실행해서 나온 것을 그대로 보여 줘.','p-b'))
P3rich=hl(P3,('아직 고치지 말고 계획만 말해 줘.','p-c'),('더할 노드와 관계를 하나도 빠짐없이 식별자와 함께 적고, 클래스별 · 관계별 수와 더한 뒤의 노드 · 관계 전체 수를 적어 줘.','p-b'))
P4rich=hl(P4,('schema.json 과 질의.py 는 손대지 마.','p-c'),('검사와 질의는 내가 직접 실행해 본다.','p-b'))

# ── 그림: 두 설비가 구성 요소를 가리키는 모양 ──
def asset_fig():
    comps=C01[:2]+OWN+SHARED            # 위: HYD-01~03 만 / 가운데: HYD-04 만 / 아래: 함께
    y=lambda k: 44+k*40
    h=y(len(comps))+6
    s=f'<svg viewBox="0 0 760 {h}" role="img" aria-label="설비와 구성 요소의 연결">'
    s+='<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#8a94a3"/></marker><marker id="ar2" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1f8a5b"/></marker></defs>'
    s+='<text x="20" y="20" font-size="12" font-weight="800" fill="#5b6573">이미 있는 설비</text><text x="300" y="20" font-size="12" font-weight="800" fill="#5b6573">구성 요소 노드</text><text x="620" y="20" font-size="12" font-weight="800" fill="#1f8a5b">새 설비</text>'
    ly=y(2)+40; ry=y(len(comps)//2)
    s+=f'<rect x="20" y="{ly-34}" width="170" height="68" rx="12" fill="#eef1f5" stroke="#cfd6e0"/><text x="105" y="{ly-6}" text-anchor="middle" font-size="14" font-weight="800">HYD-01 · 02 · 03</text><text x="105" y="{ly+14}" text-anchor="middle" font-size="12" fill="#5b6573">Asset 노드 셋</text>'
    s+=f'<rect x="590" y="{ry-34}" width="150" height="68" rx="12" fill="#e6f5ee" stroke="#1f8a5b" stroke-width="2"/><text x="665" y="{ry-6}" text-anchor="middle" font-size="14" font-weight="800">HYD-04</text><text x="665" y="{ry+14}" text-anchor="middle" font-size="12" fill="#1f8a5b">Asset 노드 하나</text>'
    for k,c in enumerate(comps):
        p=node(G,c); new=c in OWN; cy=y(k)+14
        s+=f'<rect x="290" y="{y(k)}" width="200" height="30" rx="8" fill="{"#e6f5ee" if new else "#fff"}" stroke="{"#1f8a5b" if new else "#cfd6e0"}" stroke-width="{2 if new else 1}"/><text x="390" y="{cy+6}" text-anchor="middle" font-size="13.5" font-weight="{800 if new else 600}">{e(p["name"])}</text>'
        if c in C01: s+=f'<line x1="190" y1="{ly}" x2="286" y2="{cy}" stroke="#8a94a3" stroke-width="1.5" marker-end="url(#ar)"/>'
        if c in C04: s+=f'<line x1="590" y1="{ry}" x2="494" y2="{cy}" stroke="#1f8a5b" stroke-width="2" marker-end="url(#ar2)"/>'
    return s+'</svg>'
A_FIG='<div class="fig">'+asset_fig()+f'<p>화살표는 모두 <code>HAS_COMPONENT</code>다. 초록 상자가 HYD-04 때문에 새로 생기는 노드 {len(OWN)+1}개(설비 하나와 구성 요소 {len(OWN)})이고, 아래 네 구성 요소는 노드가 늘지 않고 화살표만 하나씩 더 받는다. 완성 폴더의 <code>graph.json</code>에서 옮겨 그렸다.</p></div>'

inherit_table=('<table class="res"><thead><tr><th>이어받은 것</th><th>들어 있는 것</th><th>오늘 이것으로 하는 일</th></tr></thead><tbody>'
 f'<tr><td><code>결과/schema.json</code></td><td>클래스 {len(S0["classes"])}, 관계 {len(S0["relationships"])}, <code>conventions</code> {len(S0["conventions"])}문장</td><td><mark>한 글자도 고치지 않는다.</mark> 새 설비가 이 정의에 그대로 들어가는지를 본다</td></tr>'
 f'<tr><td><code>결과/graph.json</code></td><td>노드 {len(G0["nodes"])}, 관계 {len(G0["rels"])}. 설비는 HYD-01, HYD-02, HYD-03 셋</td><td>이미 있는 줄은 그대로 두고 HYD-04의 노드와 관계를 <mark>뒤에 더한다</mark></td></tr>'
 '<tr><td><code>도구/검사.py</code></td><td>그래프가 스키마의 정의대로 적혔는지, 처음 받은 것에서 무엇이 달라졌는지를 보여 주는 프로그램</td><td>더하기 전과 후에 실행해 견준다</td></tr>'
 '</tbody></table>')

pick=('<table class="res"><thead><tr><th>정할 것</th><th>권하는 답 (아래 복사 상자에 들어 있다)</th><th>이렇게 고르면 생기는 일</th></tr></thead><tbody>'
 f'<tr><td><b>같은 구성 요소</b><br>첫째 줄</td><td>주 펌프 (A), 예비 펌프 (B), 구동 모터, 작동유 탱크는 이미 있는 노드에 <code>HAS_COMPONENT</code>로 잇기만 한다</td><td>HYD-04용으로 따로 만들면 같은 펌프가 노드 둘이 된다. <code>conventions</code>의 「같은 기종이고 구조가 같으면 노드 하나」와 어긋난다</td></tr>'
 '<tr><td><b>다른 구성 요소</b><br>둘째 줄</td><td>대형 오일 쿨러, 쿨러 팬 1, 쿨러 팬 2는 새 노드로 만든다. 현장에서 부르는 말은 <code>aliases</code>에 넣는다</td><td>이미 있는 「쿨러 팬」 노드에 이으면 HYD-04에 없는 VS1이 HYD-04의 결과에 나오고, VS2를 거기에 붙이면 HYD-01의 결과에 VS2가 나온다</td></tr>'
 '<tr><td><b>두 번 적힌 줄, 빈 값</b><br>셋째 · 넷째 줄</td><td>TS3 두 줄은 노드 하나다. 비어 있는 정상값, 한계, 단위는 적지 않는다</td><td>HYD-01의 값으로 채우면 정해지지 않은 인터록 한계가 정해진 것처럼 읽힌다. 6단계에서 이것을 일부러 요청해 본다</td></tr>'
 f'<tr><td><b>같은 품번의 부품</b><br>다섯째 줄</td><td>쿨러 팬 1과 쿨러 팬 2를 이미 있는 팬 베어링 노드에 <code>USES_PART</code>로 잇는다. 부품 노드를 새로 만들지 않는다</td><td>잇지 않으면 「팬 베어링이 모자라면 어느 설비가 영향을 받는가」에 HYD-04가 나오지 않는다. 이으면 스키마의 <code>USES_PART</code> <code>{rel("USES_PART")["cardinality"]}</code>과 어긋난다. 아래에서 다룬다</td></tr>'
 '</tbody></table>')

new_table=('<table class="res"><thead><tr><th>클래스 · 관계</th><th>더하기 전</th><th>더한 뒤</th><th>늘어난 것</th></tr></thead><tbody>'
 +''.join(f'<tr><td><code>{L}</code></td><td>{cnt(G0,L)}</td><td><mark>{cnt(G,L)}</mark></td><td>'+', '.join(f'<code>{n["props"]["id"]}</code> {e(n["props"]["name"])}' for n in NEW if n['labels'][0]==L)+'</td></tr>' for L in ('Asset','Component','Sensor','StateVariable'))
 +f'<tr><td><code>Part</code> · <code>Actuator</code></td><td>{cnt(G0,"Part")} · {cnt(G0,"Actuator")}</td><td>{cnt(G,"Part")} · {cnt(G,"Actuator")}</td><td>없다. 팬 베어링은 이미 있는 노드를 쓰고, 구동기는 자료에 없다</td></tr>'
 +''.join(f'<tr><td><code>{T}</code></td><td>{rc(G0,T)}</td><td><mark>{rc(G,T)}</mark></td><td>{d}</td></tr>' for T,d in (('HAS_COMPONENT',f'HYD-04에서 새 구성 요소 {len(OWN)}과 이미 있는 구성 요소 {len(SHARED)}로'),('MOUNTED_ON','새 센서 넷이 붙은 곳'),('MEASURES','새 센서 넷이 재는 값'),('USES_PART','쿨러 팬 1과 쿨러 팬 2에서 팬 베어링으로')))
 +f'<tr><td>노드 전체 · 관계 전체</td><td style="white-space:nowrap">{len(G0["nodes"])} · {len(G0["rels"])}</td><td style="white-space:nowrap"><mark>{len(G["nodes"])} · {len(G["rels"])}</mark></td><td>노드 {len(NEW)}, 관계 {len(NEWR)}</td></tr></tbody></table>')
assert len(NEW)==12 and len(NEWR)==17

def chk_box(text,marks=()):
    h=e(text)
    for m in marks:
        assert e(m) in h,m
        h=h.replace(e(m),f'<mark>{e(m)}</mark>')
    return f'<div class="csv">{h}</div>'
chk_lines=CHK.split('\n')
CHK_SHORT='\n'.join([l for l in chk_lines if not l.startswith('    ')])   # 새 노드 열두 줄은 접는다
rule=lambda start: next(l for l in RULE.split('\n') if l.startswith(start))
R1,R4,R8=rule('1. '),rule('4. '),rule('8. ')
md=lambda t: re.sub(r'`([^`]+)`',r'<code>\1</code>',e(t))

pages=[]
# ── 준비 ──
pages.append(hero('준비','<small>통합반 오프라인 2회차 · 실습 3 · 40분</small>새 설비 HYD-04를<br>같은 스키마에 더한다','2라인 증설로 유압 파워팩 한 대가 더 들어와 HYD-04라는 설비 코드를 받았다. 설비가 새로 생겼을 때 더하는 것은 클래스가 아니라 인스턴스다. 오늘은 지난 시간의 <code>schema.json</code>을 <b>한 글자도 고치지 않고</b> HYD-04를 <code>graph.json</code>에 더한 다음, 같은 질의를 HYD-01과 HYD-04에 실행해 결과를 나란히 본다. 스키마를 다시 만들지 않았는데도 질의가 그대로 통하는지가 확인할 점이다.',[('끝나면 남는 것','HYD-04가 더해진 결과/graph.json, 어느 설비에나 통하는 결과/질의.py'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna) · 터미널'),('전제','2회차 실습 1을 마쳤고, 온라인 2일차의 스키마 단원을 들었다')])
+'<section class="sect"><h2>오늘 하는 일의 순서</h2><p>손으로 JSON이나 파이썬을 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 그 대신 <b>요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과를 프로그램으로 실행해 내 눈으로 가린다.</b> 질의를 HYD-04보다 먼저 만드는 순서에 까닭이 있다. 새 설비를 넣은 뒤에 질의를 고치지 않고 다시 실행해야 「같은 질의가 통한다」는 것을 보일 수 있다.</p><div class="flow"><div><em>1</em><b>읽게 한다</b>지금 그래프와 HYD-04의 자료를 읽고, 같은 것과 새것을 가르게 한다</div><div><em>2</em><b>질의를 먼저 만든다</b>HYD-04를 넣기 전에 HYD-01에 통하는 질의를 만들어 실행한다</div><div><em>3</em><b>정해 주고 계획을 받는다</b>무엇을 잇고 무엇을 새로 만들지 정하고 계획부터 듣는다</div><div><em>4</em><b>인스턴스를 더하고 검사한다</b>graph.json에 더한 뒤 검사 프로그램으로 달라진 것을 센다</div><div><em>5</em><b>같은 질의를 두 설비에</b>고치지 않은 질의를 HYD-01과 HYD-04에 실행해 나란히 본다</div><div><em>6</em><b>규칙을 시험한다</b>스키마를 고쳐 달라고 일부러 요청해 멈추는지 본다</div><div><em>7</em><b>되돌려 준다</b>부품에서 거꾸로 가는 질의를 내 말로 요청해 더한다</div></div></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>결과/</span>                    <i>← 지난 시간에 만든 것</i>\n│  ├─ schema.json              <i>← 클래스 '+str(len(S0['classes']))+', 관계 '+str(len(S0['relationships']))+'. 오늘은 고치지 않는다</i>\n│  └─ graph.json               <i>← 노드 '+str(len(G0['nodes']))+', 관계 '+str(len(G0['rels']))+'. 여기에 더한다</i>\n├─ <span>새_설비/</span>                  <i>← 이번에 받은 HYD-04의 자료</i>\n│  ├─ 반입_메모.md             <i>← 자료를 보낸 사람의 설명. 먼저 읽는다</i>\n│  ├─ 설비_대장_추가.csv       <i>← 1줄</i>\n│  ├─ 구성요소_목록.csv        <i>← 7줄</i>\n│  └─ 센서_목록.csv            <i>← 7줄</i>\n└─ <span>도구/</span>\n   ├─ 검사.py                  <i>← 미리 들어 있는 검사 프로그램</i>\n   └─ 처음_graph.json, 처음_schema.json  <i>← 검사가 견줄 때 쓰는 처음 상태</i></div><p><code>결과</code> 폴더의 두 파일은 2회차 실습 1의 완성본이다. <b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다. 완성 폴더는 이 가이드가 권하는 답을 골랐을 때의 결과여서, 다른 선택지를 골랐다면 내 파일이 다르게 나오는 것이 맞다.</p>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 결과, 새_설비, 도구 네 폴더가 펼쳐져 있고 결과 폴더의 schema.json, graph.json이 보이게.'))
+do(2,'editor','VS Code · 편집기','이어받은 것을 본다','<p>탐색기에서 <code>결과/graph.json</code>을 눌러 연다. <code>rels</code>에서 <code>HAS_COMPONENT</code> 줄을 찾으면 '+str(rc(G0,'HAS_COMPONENT'))+f'줄이다. 설비 셋이 <b>같은 구성 요소 노드 {cnt(G0,"Component")}개</b>를 함께 가리킨다. 세 대가 같은 기종이라 구성 요소, 센서, 부품을 설비마다 만들지 않고 노드 하나로 두었기 때문이다. 이 약속은 <code>결과/schema.json</code>의 <code>conventions</code>에 문장으로 적혀 있다.</p>'+inherit_table)
+do(3,'editor','VS Code · 편집기','<code>반입_메모.md</code>를 직접 읽는다','<p><code>새_설비/반입_메모.md</code>를 끝까지 읽는다. 2절이 오늘의 핵심이다. HYD-04는 HYD-01~03과 <b>같은 곳도 있고 다른 곳도 있다.</b> 펌프 쪽은 같은 것이 들어왔고, 냉각부는 쿨러가 커지고 팬이 두 대가 되었다.</p><ul class="ask"><li><b>같은 것은 어떻게 넣는가</b>주 펌프 (A)는 이미 노드가 있다. HYD-04를 위해 하나 더 만드는가, 있는 노드에 잇는가.</li><li><b>다른 것은 어떻게 넣는가</b>쿨러 팬이 두 대이고 진동 센서가 팬마다 하나씩이다. 이미 있는 「쿨러 팬」 노드에 이어도 되는가.</li><li><b>같은 부품을 쓰는 다른 구성 요소</b>쿨러 팬 1과 쿨러 팬 2에는 HYD-01~03의 쿨러 팬과 같은 팬 베어링(P-FAN-BRG)이 들어간다. 부품 노드는 몇 개여야 하는가.</li><li><b>비어 있는 값</b>새 센서 넷은 시운전 전이라 정상값과 한계가 없다. 메모 3절은 무엇을 하지 말라고 했는가.</li></ul><p>세 CSV 파일은 Copilot에게 읽히되, <code>새_설비/센서_목록.csv</code>에 TS3이 두 줄이고 VS3의 단위 칸이 비어 있다는 것만 눈으로 확인해 둔다.</p>')
+nxt(1,'1. 고치기 전에, 먼저 읽게 한다'))

# ── 1 ──
pages.append(hero('1단계','고치기 전에,<br>먼저 읽게 한다','첫마디가 「HYD-04를 넣어 줘」이면 AI는 읽자마자 넣기 시작한다. 어느 구성 요소를 이미 있는 노드에 잇고 어느 것을 새로 만들지 같은 판단이 내가 모르는 사이에 내려져 파일에 들어간다. 그래서 첫 요청은 <b>읽고, 같은 것과 새것을 갈라 말해 보라</b>는 요청으로 한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','지금 그래프의 모양, HYD-04에서 새로 생길 것, 내가 정할 것이 채팅에 정리되어 있다'),('아직 바뀌면 안 되는 것','결과 폴더의 두 파일')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>'+copy(P1,rich=P1rich,pre=True)+'<div class="parts"><div class="a"><b>무엇을 읽는가</b>규칙 파일, 지난 시간의 두 파일, HYD-04의 자료 네 파일. 이미 있는 것과 새로 받은 것을 함께 읽혀야 둘을 견줄 수 있다.</div><div class="b"><b>줄마다 가르게 한 까닭</b>「HYD-04에 구성 요소가 일곱」이라는 말로는 노드가 몇 개 늘지 알 수 없다. 자료의 한 줄 한 줄을 이미 있는 노드와 견주어야 늘어날 수가 나온다.</div><div class="c"><b>하지 말 것</b>이 요청에서 가장 중요한 문장이다. 이 한 줄이 없으면 읽자마자 고치기 시작한다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분 넘게 걸릴 수 있다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. HYD-04의 자료를 줄마다 「이미 있음」과 「새 노드」로 가른 표와, 답의 끝에서 정해 달라는 것을 번호로 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>지금 그래프의 수와 길</b><span>노드 {len(G0["nodes"])}, 관계 {len(G0["rels"])}이라고 했는가. HYD-01에서 센서까지는 <code>HAS_COMPONENT</code>로 구성 요소에 간 다음 <code>MOUNTED_ON</code>을 <b>거꾸로</b> 따라가야 닿는다고 했는가. 이 스키마에서 <code>MOUNTED_ON</code>의 화살표는 센서에서 구성 요소로 향한다.</span></p></div><div><i>②</i><p style="margin:0"><b>이미 있는 것과 새것</b><span>구성 요소 일곱 줄 가운데 넷을 이미 있는 노드로, 셋을 새 노드로 갈랐는가. 「스탠바이 펌프」와 「탱크」를 <code>aliases</code>로 찾아냈는가. TS3 두 줄을 같은 센서로 보았는가. PS1과 FS1은 이미 있다고 했는가.</span></p></div><div><i>③</i><p style="margin:0"><b>스키마와 맞지 않는다고 짚은 곳</b><span>팬 베어링을 새 팬 두 대에 이으면 <code>USES_PART</code>의 카디널리티 <code>{rel("USES_PART")["cardinality"]}</code>과 어긋난다는 말이 있는가. 어떻게 할지를 스스로 정하지 않고 나에게 물었는가. 3단계에서 이것을 정한다.</span></p></div></div>'
 +'<div class="note"><b>되묻는 까닭</b>규칙 파일의 「정해져 있지 않은 것」에 일곱 줄을 적고 「요청에 없으면 정하지 말고 묻는다」고 해 두었기 때문이다. 규칙이 없었다면 이 자리들은 AI가 알아서 채웠을 것이고, 무엇이 어떻게 정해졌는지는 파일을 뜯어보아야 알 수 있다.</div><div class="if"><div><b>파일이 바뀌어 버렸다면</b>탐색기에서 <code>graph.json</code> 옆에 바뀌었다는 표시(M)가 보이면 요청의 「아직 아무것도 만들거나 고치지 마」가 빠진 것이다. 채팅의 「실행 취소」로 되돌리거나 받은 <code>시작</code> 폴더를 다시 복사해 연 뒤, 요청을 다시 복사해 보낸다.</div><div><b>카디널리티 이야기가 없다면</b>「쿨러 팬 1과 쿨러 팬 2를 팬 베어링에 이으면 schema.json 의 어느 정의와 어긋나는지 봐 줘」라고 한 번 더 묻는다.</div></div>')
+nxt(2,'2. HYD-04를 넣기 전에, 질의를 먼저 만든다',0))

# ── 2 ──
pages.append(hero('2단계','HYD-04를 넣기 전에,<br>질의를 먼저 만든다','오늘 확인하려는 것은 「스키마를 고치지 않고 인스턴스만 더해도 같은 질의가 통한다」는 것이다. 그러려면 질의가 새 설비보다 먼저 있어야 한다. 지금 그래프에서 HYD-01에 통하는 질의를 만들어 실행해 두고, HYD-04를 넣은 뒤에는 <b>이 파일을 고치지 않고</b> 다시 실행한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','결과/질의.py가 있고, HYD-01의 표와 「HYD-04는 없다」는 한 줄을 보았다'),('아직 바뀌면 안 되는 것','결과/schema.json, 결과/graph.json')])
+mapbox('term','이 단계에서 쓰는 곳','<p><b>Copilot 채팅</b>에서 요청하고, 만든 프로그램은 편집기 아래쪽의 <b>터미널</b>에서 실행된다. 터미널이 보이지 않으면 메뉴의 「터미널 → 새 터미널」로 연다.</p>')
+do(1,'chat','Copilot 채팅 · 입력 칸','질의 프로그램을 만들게 한다','<p>아래 요청을 복사해 보낸다. 가운데 세 줄은 1단계에서 Copilot이 물은 것 가운데 표의 모양에 대한 답이다. 칸에 무엇을 어떤 글자로 보일지는 규칙이 정해 두지 않았으므로 요청하는 사람이 정한다.</p>'+copy(P2,rich=P2rich,pre=True)+'<div class="parts"><div class="a"><b>왜 지금 만드는가</b>HYD-04를 넣은 뒤에 만든 질의는 HYD-04에 맞춰 만들어진 것인지 가릴 수 없다. 먼저 만들어 두면 뒤에서 「고치지 않았는데 통했다」고 말할 수 있다.</div><div class="b"><b>실행해서 보여 달라고 한 까닭</b>만들었다는 말이 아니라 실행한 출력을 받는다. HYD-04를 함께 넣은 것은, 없는 설비를 물었을 때 어떻게 답하는지도 지금 보아 두려는 것이다.</div><div class="c"><b>하지 말 것</b>이 단계에서 늘어나는 파일은 <code>결과/질의.py</code> 하나다. 그래프는 아직 그대로여야 한다.</div></div>')
+do(2,'chat','Copilot 채팅 · 허용 물음','허용을 누르기 전에 읽는다','<p>Copilot이 파일을 만들 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 두 가지를 읽는다. 만드는 파일이 <code>결과/질의.py</code>인가. 실행하려는 명령이 <code>python 결과/질의.py HYD-01 HYD-04</code>(또는 <code>python3 …</code>)인가. 다른 파일이나 다른 명령이면 허용하지 않고 왜 필요한지 묻는다.</p>'+shot('Copilot이 결과/질의.py를 만들고 터미널 명령(python 결과/질의.py HYD-01 HYD-04)의 실행 허용을 묻는 화면. 명령 글자와 「허용/계속」 버튼이 보이게.'))
+do(3,'term','Copilot 채팅 · 답 → 터미널','나온 표를 읽는다','<p>아래는 완성 폴더에서 같은 명령을 실행했을 때의 결과다. 터미널에는 같은 내용이 세로줄(<code>|</code>)로 칸을 나눈 글자 표로 나온다. 글자와 순서는 2단계의 요청대로면 같아야 한다.</p>'+res(*T_BEFORE[0])+res(*T_BEFORE[1])
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>한 구성 요소에 센서 둘</b><span>오일 쿨러 줄의 센서 칸에 TS1과 CE가 함께 있다. 한 구성 요소를 재는 센서가 여럿이면 센서마다 노드와 <code>MOUNTED_ON</code> 관계가 하나씩 있고, 질의는 그것을 모두 따라간다.</span></p></div><div><i>②</i><p style="margin:0"><b>없는 설비</b><span>HYD-04는 아직 그래프에 없으므로 표 대신 한 줄이 나온다. 4단계 뒤에 이 자리가 표로 바뀌어야 한다.</span></p></div><div><i>③</i><p style="margin:0"><b>질의 안에 설비의 이름이 없는가</b><span>탐색기에서 <code>결과/질의.py</code>를 열고 Ctrl+F로 <code>HYD</code>를 찾는다. 맨 위 설명글의 쓰는 법 말고는 나오지 않아야 한다. 규칙 5번이 특정 설비의 식별자나 이름을 프로그램에 적지 못하게 했다. 설비 코드는 실행할 때 받는다.</span></p></div></div>'
 +'<div class="if"><div><b>python 을 찾을 수 없다고 나오면</b>「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다. 프로그램을 다른 언어로 바꾸게 하지 않는다.</div><div><b>표의 글자가 위와 다르면</b>센서 칸에 태그가 없거나 부품 칸에 품번이 없으면 요청의 가운데 세 줄 가운데 빠진 것이 있다. 「센서 칸은 태그와 이름을 함께 적어 줘」처럼 그 줄만 다시 말한다.</div></div>')
+nxt(3,'3. 무엇을 잇고 무엇을 새로 만들지 정하고, 계획부터 받는다',1))

# ── 3 ──
pages.append(hero('3단계','무엇을 잇고 무엇을 새로 만들지 정하고,<br>계획부터 받는다','새 설비를 넣는 일의 판단은 한 가지로 모인다. 자료의 이 줄이 <b>이미 있는 노드와 같은 대상인가, 새 대상인가.</b> 같은 대상을 새로 만들면 같은 펌프가 둘이 되고, 다른 대상을 있는 노드에 이으면 없는 센서가 따라온다. 이 판단은 설비를 아는 사람이 한다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','더할 노드와 관계가 식별자까지 적힌 계획이 채팅에 있다'),('아직 바뀌면 안 되는 것','결과/schema.json, 결과/graph.json')])
+'<section class="sect"><h2>같은 것은 잇고, 다른 것만 새로 만든다</h2><p>HYD-04의 구성 요소 일곱 가운데 넷은 HYD-01~03과 같은 것이고 셋은 다른 것이다. 같은 넷은 노드가 늘지 않는다. HYD-04에서 그 노드로 가는 <code>HAS_COMPONENT</code> 한 줄씩만 생긴다.</p>'+A_FIG+'</section>'
+do(1,'editor','이 화면','네 가지를 고른다','<p>Copilot이 물어 온 것 가운데 결과를 크게 가르는 네 가지다. 가운데 칸이 이 가이드가 권하는 답이고, 완성 폴더는 이 답으로 만든 것이다. 오른쪽 칸은 다르게 골랐을 때 생기는 일이다.</p>'+pick
 +f'<div class="note"><b>스키마와 어긋나는 줄을 알고 가는 까닭</b>지난 시간에 <code>USES_PART</code>를 <code>{rel("USES_PART")["cardinality"]}</code>으로 정했다. 구성 요소 하나는 부품 여럿을 쓰지만 부품 하나를 쓰는 구성 요소는 하나라는 뜻이다. 그때의 자료에서는 맞았다. HYD-04가 들어오면서 팬 베어링 하나를 구성 요소 셋이 쓰게 된다. 오늘은 스키마를 고치지 않으므로, 자료대로 잇고 어긋난다는 사실을 드러내 둔다. 6단계에서 이것을 다시 다룬다.</div>')
+do(2,'chat','Copilot 채팅 · 입력 칸','정한 것을 보내고 계획을 받는다','<p>아래 요청에는 권하는 답이 한 줄씩 들어 있다. 「복사」를 눌러 채팅에 붙여넣는다. 다르게 고른 것이 있으면 <b>보내기 전에 입력 칸에서 그 줄만</b> 고친다.</p>'+copy(P3,rich=P3rich,pre=True)+'<div class="parts"><div class="a"><b>줄 하나에 결정 하나</b>잇는 것, 새로 만드는 것, 두 번 적힌 줄, 빈 값, 같은 품번의 부품, 만들지 않는 것. 1단계에서 Copilot이 물은 것에 차례로 답한 것이다.</div><div class="b"><b>식별자까지 적게 한 까닭</b>새 구성 요소에는 태그나 품번 같은 번호가 없다. 식별자를 AI가 이름을 영어로 옮겨 짓게 되므로, 파일에 들어가기 전에 눈으로 본다.</div><div class="c"><b>마지막 문단</b>바로 고치지 않고 계획을 먼저 말하게 한다. 규칙 파일의 7번이 이 말을 받으면 계획만 말하도록 정해 두었다.</div></div>')
+do(3,'chat','Copilot 채팅 · 답','계획의 수를 센다','<p>Copilot은 파일을 고치지 않고 계획을 내놓는다. 권하는 답 그대로 갔다면 아래 수가 나와야 한다.</p>'+shot('3단계 요청에 대한 Copilot의 계획. 더할 노드를 식별자와 함께 적은 표와, 더한 뒤의 노드 · 관계 전체 수가 보이게. 새 구성 요소 셋의 식별자에 테두리를 얹는다.')
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>더할 노드 {len(NEW)}</b><span>설비 1, 구성 요소 {len(OWN)}, 센서 4, 재는 값(상태 변수) 4다. 부품과 구동기는 0이어야 한다. 더한 뒤의 전체는 노드 {len(G["nodes"])}이다.</span></p></div><div><i>②</i><p style="margin:0"><b>더할 관계 {len(NEWR)}</b><span><code>HAS_COMPONENT</code> {rc(G,"HAS_COMPONENT")-rc(G0,"HAS_COMPONENT")}, <code>MOUNTED_ON</code> 4, <code>MEASURES</code> 4, <code>USES_PART</code> 2다. 주 펌프의 <code>USES_PART</code>는 이미 있으므로 더하지 않는다. 더한 뒤의 전체는 관계 {len(G["rels"])}이다.</span></p></div><div><i>③</i><p style="margin:0"><b>새 식별자</b><span>센서와 재는 값은 <code>conventions</code>의 규칙대로 태그에서 나온다(<code>sen:ts2</code>, <code>sv:ts2</code>). 구성 요소 셋의 식별자는 Copilot이 지은 것이다. 완성 폴더에서는 '+', '.join(f'<code>{c}</code>' for c in OWN)+'였다. 다른 말이 나와도 틀린 것이 아니다. 마음에 들지 않으면 지금 바꿔 달라고 한다. 한번 붙인 식별자는 바꾸지 않기로 했으므로 지금이 마지막 기회다.</span></p></div></div>'
 +'<div class="if"><div><b>계획 없이 파일을 고쳤다면</b>요청의 마지막 문단이 빠진 것이다. 고친 것을 되돌리고 요청을 다시 복사해 보낸다.</div><div><b>수가 다르다면</b>어느 줄이 다른지 찾는다. 구성 요소가 일곱 늘었다면 첫째 줄이, 부품이 하나 늘었다면 다섯째 줄이 반영되지 않은 것이다. 「주 펌프 (A)는 이미 있는 comp:main-pump 에 잇기로 했어. 계획을 고쳐 줘」처럼 그 줄을 가리켜 말한다.</div></div>')
+nxt(4,'4. 인스턴스를 더하고, 검사 프로그램으로 센다',2))

# ── 4 ──
pages.append(hero('4단계','인스턴스를 더하고,<br>검사 프로그램으로 센다','계획이 맞으면 그대로 넣게 한다. 넣은 뒤에 「잘 넣었습니다」라는 말을 믿지 않고 <b>프로그램으로 센다.</b> 스키마가 그대로인지, 이미 있던 노드가 하나도 바뀌지 않았는지, 새로 들어온 것이 계획의 수와 같은지를 검사 프로그램이 한 번에 보여 준다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면',f'결과/graph.json이 노드 {len(G["nodes"])}, 관계 {len(G["rels"])}이 되었고 검사 결과를 읽었다'),('바뀌면 안 되는 것','결과/schema.json, 결과/질의.py')])
+do(1,'term','VS Code · 터미널','넣기 전에 검사를 한 번 실행해 둔다','<p>아래 명령을 터미널에 붙여넣고 Enter를 누른다. 지금은 아무것도 넣지 않았으므로 [3]의 새로 들어온 것이 모두 0이어야 한다. 넣은 뒤에 같은 명령을 다시 실행해 견준다.</p>'+cmd('python 도구/검사.py')+chk_box(CHK0))
+do(2,'chat','Copilot 채팅 · 입력 칸','계획대로 넣게 한다','<p>아래 요청을 복사해 보낸다. 파일을 고칠 때 허용을 묻는 물음이 뜨면, 고치는 파일이 <code>결과/graph.json</code>인지 읽고 누른다.</p>'+copy(P4,rich=P4rich)+'<div class="parts"><div class="a"><b>「계획에 적은 그대로」</b>계획과 실제로 넣은 것이 달라지지 않게 한다. 계획에서 본 식별자가 파일에 그대로 들어가야 한다.</div><div class="b"><b>검사를 내가 실행하는 까닭</b>넣은 쪽이 스스로 검사하고 「이상 없다」고 하는 것과, 내가 실행해 숫자를 보는 것은 다르다.</div><div class="c"><b>하지 말 것</b>스키마와 질의는 이 단계에서 바뀌지 않는다. 5단계에서 질의가 그대로였다는 것이 쓰인다.</div></div>'+shot('Copilot이 결과/graph.json의 맨 뒤에 HYD-04의 노드와 관계를 더한 변경을 보여 주는 화면. 더해진 줄(초록색)과 「유지/허용」 버튼이 보이게.'))
+do(3,'term','VS Code · 터미널','같은 검사를 다시 실행한다','<p>터미널에서 위쪽 화살표 키를 누르면 앞의 명령이 다시 나온다. Enter를 누른다. 아래는 완성 폴더에서 실행한 결과다(새로 들어온 노드를 하나씩 적은 열두 줄은 줄였다).</p>'+chk_box(CHK_SHORT,('결과/schema.json 은 처음 받은 것과 같다','사라진 것 0, 값이 바뀐 것 0','새로 들어온 노드 12','새로 들어온 관계 17','[5] 카디널리티와 다르게 이어진 곳 1'))
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>[1] 스키마는 처음과 같다</b><span>클래스 {len(S["classes"])}, 관계 {len(S["relationships"])}, <code>conventions</code> {len(S["conventions"])}문장 그대로다. 새 설비가 들어왔지만 정의는 하나도 늘지 않았다.</span></p></div><div><i>②</i><p style="margin:0"><b>[3] 이미 있던 것은 그대로다</b><span>처음부터 있던 노드 {len(G0["nodes"])}와 관계 {len(G0["rels"])} 가운데 사라지거나 바뀐 것이 0이다. 새로 들어온 것은 노드 {len(NEW)}, 관계 {len(NEWR)}로 3단계의 계획과 같다.</span></p></div><div><i>③</i><p style="margin:0"><b>[4]는 0, [5]는 1</b><span>[4]는 스키마에 없는 클래스나 속성, 자료형이 다른 값, 끝이 잘못된 관계처럼 정의를 어긴 곳이다. 0이어야 한다. [5]는 정의는 지켰지만 카디널리티와 다르게 이어진 곳이다. 3단계에서 알고 가기로 한 팬 베어링 한 줄이 여기에 나온다.</span></p></div></div>'
 +'<p>무엇이 늘었는지를 클래스와 관계별로 보면 아래와 같다.</p>'+new_table
 +'<div class="if"><div><b>[3]에 사라지거나 바뀐 것이 있다면</b>그 아래에 식별자가 적혀 있다. 「이미 있는 노드는 값을 바꾸지 않기로 했어. sv:ps1 을 처음 값으로 되돌려 줘」처럼 그 식별자를 들어 말한다. 규칙 3번이 이미 있는 것을 바꾸지 못하게 했다.</div><div><b>[4]가 0이 아니라면</b>줄마다 어느 노드의 어느 속성인지 적혀 있다. 그 줄을 그대로 채팅에 붙여넣고 「스키마는 고치지 말고 graph.json 에서 이 줄을 바로잡아 줘」라고 말한다.</div></div>')
+nxt(5,'5. 같은 질의를 두 설비에 실행해 나란히 본다',3))

# ── 5 ──
h01,h04=T_AFTER
pages.append(hero('5단계','같은 질의를 두 설비에 실행해<br>나란히 본다','2단계에서 만든 <code>질의.py</code>는 HYD-04가 무엇인지 모르고 만들어졌다. 그 뒤로 이 파일은 고치지 않았다. 같은 명령을 다시 실행해, <b>질의를 고치지 않았는데도 새 설비의 결과가 같은 모양으로 나오는지</b>를 본다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','HYD-01과 HYD-04의 표를 나란히 놓고 같은 곳과 다른 곳을 짚었다'),('바뀌면 안 되는 것','결과 폴더의 세 파일 모두')])
+do(1,'term','VS Code · 터미널','2단계와 같은 명령을 실행한다','<p>아래 명령을 터미널에 붙여넣고 Enter를 누른다. 2단계에서 Copilot이 실행한 것과 글자 하나 다르지 않은 명령이다.</p>'+cmd('python 결과/질의.py HYD-01 HYD-04')+res(*h01)+res(*h04,mark=('팬 베어링 (P-FAN-BRG)','TS2 쿨러 입구 유온 센서, TS3 쿨러 출구 유온 센서'))+shot('터미널에 python 결과/질의.py HYD-01 HYD-04 의 결과가 나온 화면. [HYD-01]과 [HYD-04] 두 표가 한 화면에 보이게. HYD-04의 표에서 팬 베어링이 적힌 두 줄에 테두리를 얹는다.'))
+do(2,'editor','이 화면 · 터미널','두 표에서 네 가지를 짚는다','<p>두 표는 칸이 같고 읽는 법이 같다. 다른 것은 줄에 들어 있는 대상뿐이다.</p>'
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>HYD-01의 표는 2단계와 같다</b><span>구성 요소 6, 센서 5, 부품 3. HYD-04를 넣었는데도 이미 있던 설비의 답이 달라지지 않았다. 쿨러 팬 1과 쿨러 팬 2를 이미 있는 「쿨러 팬」에 이었다면 이 표에 VS2와 VS3이 나타났을 것이다.</span></p></div><div><i>②</i><p style="margin:0"><b>여러 센서</b><span>대형 오일 쿨러 줄에 TS2와 TS3이 함께 있다. HYD-01의 오일 쿨러 줄에 TS1과 CE가 함께 있는 것과 같은 모양이다. 센서가 여럿이면 센서마다 노드와 관계가 하나씩 생길 뿐, 질의는 달라지지 않는다.</span></p></div><div><i>③</i><p style="margin:0"><b>함께 쓰는 부품</b><span>팬 베어링 (P-FAN-BRG)이 HYD-01의 쿨러 팬 줄에도, HYD-04의 쿨러 팬 1과 쿨러 팬 2 줄에도 나온다. 그런데 HYD-04의 아랫줄은 부품 2다. 부품 노드는 하나이고 관계가 여럿이기 때문이다. <code>graph.json</code>에서 <code>part:p-fan-brg</code>를 찾으면(Ctrl+F) 노드는 한 줄, <code>USES_PART</code>는 {len(fan_users)}줄이다.</span></p></div><div><i>④</i><p style="margin:0"><b>같은 줄</b><span>주 펌프 (A)부터 작동유 탱크까지 네 줄은 두 표에서 글자가 같다. 같은 노드를 두 설비가 함께 가리키기 때문이다.</span></p></div></div>'
 +'<ul class="ask"><li><b>비어 있는 것이 드러나는가</b>HYD-04의 팬 2 진동에는 단위가 없고 대형 오일 쿨러의 부품 칸은 <code>-</code>다. 자료에 없던 것이 결과에서도 없는 것으로 보인다. 짐작으로 채웠다면 이 자리가 채워져 보였을 것이다.</li><li><b>질의는 정말 그대로인가</b>탐색기에서 <code>결과/질의.py</code> 옆에 4단계 뒤로 새로 바뀌었다는 표시가 붙지 않았는지 본다. 2단계에서 만든 파일 그대로 HYD-04의 표가 나온 것이다.</li></ul>'
 +'<div class="note"><b>스키마가 한 일</b>질의는 <code>HAS_COMPONENT</code>, <code>MOUNTED_ON</code>, <code>MEASURES</code>, <code>USES_PART</code>라는 관계의 이름과 방향만 안다. 새 설비의 인스턴스가 같은 이름과 같은 방향으로 들어갔기 때문에 질의가 그대로 통했다. 스키마를 지킨다는 것은 이미 만들어 둔 질의가 계속 통하게 한다는 뜻이다.</div>'
 +'<div class="if"><div><b>HYD-04의 표가 위와 다르다면</b>3단계에서 다르게 고른 것이 있으면 다른 것이 맞다. 권하는 답으로 갔는데 다르면, 다른 줄의 구성 요소 이름을 들어 「이 줄의 센서가 자료와 다르게 나와. graph.json 의 MOUNTED_ON 을 센서_목록.csv 의 붙은곳 칸과 견주어 줘」라고 말한다.</div></div>')
+nxt(6,'6. 규칙을 일부러 건드려 본다',4))

# ── 6 ──
pages.append(hero('6단계','규칙을<br>일부러 건드려 본다','검사의 [5]에 한 줄이 남아 있다. 가장 쉬운 해결은 스키마의 <code>1:N</code>을 <code>N:M</code>으로 바꾸는 것이다. 글자 하나다. 이 폴더의 규칙은 그것을 막아 두었다. <b>정말로 막는지, 어느 문장을 근거로 막는지</b>를 일부러 요청해서 본다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','두 요청이 모두 거절되었고, 근거가 된 규칙의 문장을 파일에서 찾았다'),('바뀌면 안 되는 것','이 폴더의 모든 파일')])
+do(1,'chat','Copilot 채팅 · 입력 칸','스키마를 고쳐 달라고 한다','<p>아래 요청을 복사해 보낸다. 「이번만 예외로」라는 말까지 넣었다. 실제 일에서 가장 흔하게 나오는 말이다.</p>'+copy(P6a)+shot('스키마의 cardinality를 고쳐 달라는 요청에 Copilot이 고치지 않겠다고 답한 화면. 규칙을 근거로 든 문장과, 대신 할 수 있는 일을 적은 부분에 테두리를 얹는다.')
 +'<div class="find"><div><i>①</i><p style="margin:0"><b>고치지 않았는가</b><span>탐색기에서 <code>결과/schema.json</code> 옆에 바뀌었다는 표시가 없어야 한다. 터미널에서 <code>python 도구/검사.py</code>를 실행해 [1]이 「처음 받은 것과 같다」인지 보아도 된다.</span></p></div><div><i>②</i><p style="margin:0"><b>어느 규칙을 들었는가</b><span><code>.github/copilot-instructions.md</code>를 열어 답이 든 문장을 찾는다. 「하면 안 되는 것」의 1번과 8번일 것이다.</span></p></div><div><i>③</i><p style="margin:0"><b>대신 무엇을 하라고 했는가</b><span>거절하고 끝내지 않고, 무엇이 어느 정의와 어긋나는지를 적어 주었는가. 그 글이 스키마를 정하는 사람에게 넘길 내용이다.</span></p></div></div>'
 +f'<table class="res"><thead><tr><th>규칙</th><th>규칙 파일의 문장</th></tr></thead><tbody><tr><td>1번</td><td>{md(R1[3:])}</td></tr><tr><td>8번</td><td>{md(R8[3:])}</td></tr></tbody></table>')
+'<section class="sect"><h2>글자 하나인데 왜 막는가</h2><p><code>schema.json</code>은 이 폴더만 쓰는 파일이 아니다. 지난 시간에 이 정의대로 그래프 DB에 유일 제약을 걸고 데이터를 넣었고, 다른 사람의 질의와 프로그램도 이 정의를 믿고 만들어졌다. 인스턴스를 넣던 사람이 넣다가 걸린다고 정의를 고치면, 정의는 넣는 사람마다 달라진다.</p><p>그래서 일을 나눈다. 인스턴스를 넣는 쪽은 <b>자료대로 넣고, 어긋난 곳을 드러낸다.</b> 검사의 [5] 한 줄이 그 기록이다.</p>'+chk_box(line5.strip())+f'<p>정의를 바꿀지는 스키마를 정하는 자리에서 따로 정한다. <code>conventions</code>에는 「cardinality 는 지금 들어 있는 노드의 수가 아니라 앞으로 있을 수 있는 연결을 기준으로 정한다」는 문장이 있다. HYD-04는 부품 하나를 구성 요소 {len(fan_users)}이 쓰는 연결이 실제로 있다는 것을 보여 주었다. 이것이 <code>USES_PART</code>를 <code>N:M</code>으로 바꾸자고 낼 근거다. 새 설비는 인스턴스만 더하는 일이지만, 지난번에 정한 스키마가 넉넉했는지를 시험하는 일이기도 하다.</p></section>'
+do(2,'chat','Copilot 채팅 · 입력 칸','빈 값을 다른 설비의 값으로 채워 달라고 한다','<p>하나를 더 보낸다. 이번에는 스키마가 아니라 값이다. 그럴듯하게 들리는 요청이다.</p>'+copy(P6b)
 +f'<p>넣지 않아야 한다. 답이 든 근거를 읽는다. 규칙 파일의 4번, <code>conventions</code>의 「목록에 값이 없으면 그 속성을 적지 않는다」, 그리고 반입 메모 3절의 「HYD-01~03의 값을 그대로 옮겨 적으시면 안 됩니다」 가운데 무엇을 들었는가.</p><table class="res"><thead><tr><th>규칙</th><th>규칙 파일의 문장</th></tr></thead><tbody><tr><td>4번</td><td>{md(R4[3:])}</td></tr></tbody></table>'
 +'<div class="note"><b>왜 위험한 요청인가</b>TS1의 65 ℃와 VS1의 2.0 mm/s는 인터록 한계다. 크기가 다른 쿨러의 입구 · 출구 온도와 두 대로 나뉜 팬의 진동에 이 값을 적으면, 아직 정해지지 않은 한계가 정해진 것처럼 읽힌다. 빈 값은 「아직 모른다」는 사실을 정확히 전한다.</div>'
 +'<div class="if"><div><b>정말로 고쳐 버렸다면</b>채팅의 「실행 취소」로 되돌린다. 되돌릴 수 없으면 <code>도구/처음_schema.json</code>의 내용을 <code>결과/schema.json</code>에 붙여넣어 되돌리고, 값은 「sv:ts2, sv:ts3, sv:vs2, sv:vs3 에서 normal 과 limit 을 지워 줘」라고 말한다. 그런 다음 강사에게 알린다. 규칙 파일의 문장만으로 막는 것이어서 모델에 따라 지나칠 수 있다.</div><div><b>새 대화에서 시험해 보려면</b>채팅 위의 「+」로 새 대화를 열고 같은 요청을 보낸다. 앞의 대화를 모르는 상태에서도 규칙 파일을 읽고 멈추는지 본다.</div></div>')
+nxt(7,'7. 거꾸로 가는 질의를 내 말로 요청한다',5))

# ── 7 ──
pages.append(hero('7단계','거꾸로 가는 질의를<br>내 말로 요청한다','반입 메모 6절에 아직 답하지 못한 물음이 있다. 「팬 베어링(P-FAN-BRG)이 모자라면 어느 설비의 어느 구성 요소가 영향을 받는가.」 지금의 질의는 설비에서 부품으로만 간다. 부품에서 출발해 거꾸로 가는 질의가 있어야 한다. 이것을 <b>내 말로 요청해</b> 더하게 한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','품번 하나를 주면 그 부품을 쓰는 구성 요소와 설비가 나온다'),('바뀌면 안 되는 것','결과/schema.json, 결과/graph.json, 그리고 지금 질의의 결과')])
+'<section class="sect"><h2>같은 요청, 두 가지 말</h2><p>이미 돌아가는 프로그램에 기능을 더할 때는 <b>무엇을 더할지만큼 무엇이 그대로여야 하는지</b>를 말해야 한다. 말하지 않으면 AI는 고치는 김에 지금의 표 모양도 손본다.</p><div class="vs"><div class="bad"><b>막연하게</b><q>부품으로도 찾을 수 있게 해 줘.</q>무엇을 주면 무엇이 나와야 하는지가 없다. 실행 방법도, 표의 칸도 AI가 정한다. 지금의 실행 방식이 바뀔 수도 있다.</div><div class="good"><b>구체적으로</b><q>품번을 주면 그 부품을 쓰는 구성 요소와 그 구성 요소를 가진 설비를 표로 내 줘. 실행은 --부품 뒤에 품번을 적는 것으로 하고, 지금의 실행 방식과 결과는 그대로 둬.</q>더할 것과 그대로 둘 것이 함께 있다.</div></div><div class="four"><div><b>무엇이</b>설비에서 부품으로만 갈 수 있다</div><div><b>왜</b>「이 부품이 모자라면 어디가 영향을 받는가」에 답하지 못한다</div><div><b>어디를</b>결과/질의.py 하나. 실행 방법과 표의 칸까지</div><div><b>어디까지</b>지금의 실행 방식과 결과, graph.json, schema.json은 그대로</div></div></section>'
+do(1,'chat','이 화면의 글 칸 → Copilot 채팅','네 가지를 넣어 직접 써서 보낸다','<p>오늘 직접 쓰는 요청은 이것 하나다. 무엇이, 왜, 어디를, 어디까지. 네 가지를 넣어 내 말로 쓴다. 실행 방법(무엇을 적으면 부품 질의가 되는지)과 표의 칸 이름은 규칙이 정해 두지 않았으므로 내가 정해 적는다. 고친 뒤에 실행해서 결과를 보여 달라는 말도 넣는다.</p>'+write('w7','무엇이 모자란지, 어떤 물음에 답하지 못하는지, 어떻게 실행하면 무엇이 나와야 하는지, 그대로 두어야 하는 것을 적는다.')+'<details><summary>다 쓴 뒤에 견주어 볼 예</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">정답이 아니라 한 가지 예다. 실행 방법과 칸의 이름은 달라도 된다. 내 글에 네 가지가 다 들어 있는지를 보는 데 쓴다. 완성 폴더는 이 예대로 고친 결과다.</p>'+copy(P7,'Copilot에게 보낼 요청 (예)',pre=True)+'</details>')
+do(2,'term','VS Code · 터미널','거꾸로 물어 본다','<p>예와 같은 실행 방법으로 정했다면 아래 명령으로 실행한다. 다르게 정했다면 내가 정한 방법으로 실행한다.</p>'+cmd('python 결과/질의.py --부품 P-FAN-BRG')+res(*T_PART)+shot('되돌려 준 뒤 터미널에서 python 결과/질의.py --부품 P-FAN-BRG 를 실행한 화면. 구성 요소 세 줄과 설비 칸이 보이게.')
 +f'<div class="find"><div><i>①</i><p style="margin:0"><b>메모의 물음에 답이 나왔는가</b><span>팬 베어링이 모자라면 구성 요소 {len(T_PART[2])}과 설비 네 대가 영향을 받는다. HYD-04를 넣기 전이었다면 쿨러 팬 한 줄뿐이었을 것이다. 부품 노드 하나에 여러 설비 쪽의 관계가 모였기 때문에 한 번의 질의로 답이 나온다.</span></p></div><div><i>②</i><p style="margin:0"><b>지금의 질의는 그대로인가</b><span>터미널에서 <code>python 결과/질의.py HYD-01 HYD-04</code>를 다시 실행해 5단계의 두 표와 같은지 본다. 기능을 더하다가 이미 되던 것이 달라지지 않았는지를 보는 것이다.</span></p></div><div><i>③</i><p style="margin:0"><b>다른 품번도 물어 본다</b><span><code>P-CLR-CORE</code>를 넣으면 HYD-04가 나오지 않아야 한다. 대형 오일 쿨러에는 그 코어가 맞지 않는다고 메모에 적혀 있었다. <code>P-PMP-SEAL</code>은 구성 요소 한 줄에 설비 네 대가 나온다. 같은 노드를 네 설비가 함께 가리키기 때문이다.</span></p></div></div>'
 +'<div class="if"><div><b>지금의 질의 결과가 달라졌다면</b>「python 결과/질의.py HYD-01 HYD-04 의 결과가 고치기 전과 달라졌어. 표의 글자와 줄의 순서를 고치기 전으로 되돌려 줘. 부품 질의는 그대로 두고」라고 말한다.</div></div>')
+'<section class="sect"><h2>시간이 남으면: 같은 자료를 한 번 더 넣어 본다</h2><p>현장에서는 같은 자료가 두 번 오는 일이 흔하다. 같은 설비를 한 번 더 넣으면 노드가 두 벌이 되는가. 아래 요청을 보낸다.</p>'+copy(P8)+f'<p>아무것도 늘지 않아야 한다. 터미널에서 <code>python 도구/검사.py</code>를 실행해 노드 {len(G["nodes"])}, 관계 {len(G["rels"])} 그대로인지 본다. 답이 무엇을 근거로 더하지 않았다고 했는지 읽는다. <code>conventions</code>의 「같은 식별자를 가진 노드는 하나뿐이다」와 식별자를 만드는 규칙이 있어서, 같은 대상은 몇 번을 읽어도 같은 식별자에 닿는다. 지난 시간에 그래프 DB에서 <code>MERGE</code>가 하던 일을 여기서는 스키마의 약속과 식별자가 한다.</p></section>'
+nxt(None,None,6))

names=['준비','1. 읽게 한다','2. 질의 먼저','3. 정하고 계획 받기','4. 더하고 검사','5. 두 설비 견주기','6. 규칙 시험','7. 되돌려 주기']
bar='<div class="bar"><div class="bar-in"><b>같은 스키마 + 새 설비 HYD-04 → 같은 질의</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-02-3-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 7단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 const term=el.classList.contains('cmd');
 try{await navigator.clipboard.writeText(text);say(term?'복사했습니다. 터미널에 붙여넣고 Enter를 누르세요.':'복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 새로운 설비에도 같은 지식 구조 적용하기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
for bad in ('/'+'Users/','/'+'private/tmp','/'+'var/folders','가상이다','시뮬레이션'):
    assert bad not in doc, bad
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
