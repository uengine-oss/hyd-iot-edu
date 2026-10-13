import re, html, json
import os
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/'
R=LAB+'통합반_오프라인/06회차_실습3_회의록_스킬/'
css=re.search(r'<style>(.*?)</style>',open(LAB+'도구/디자인_샘플.html',encoding='utf-8').read(),re.S).group(1)
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
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 내가 조건을 정한 SKILL.md 하나와, 그 스킬이 만든 작업 목록 네 파일</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
def richpre(text,cls):  # 문단마다 밑줄 색을 입힌다(문단 수와 cls 의 길이가 같아야 한다)
    ps=text.split('\n\n'); assert len(ps)==len(cls),(len(ps),cls)
    return '\n\n'.join(f'<span class="p-{c}">{e(p)}</span>' for p,c in zip(ps,cls))
def parts(*abc): return '<div class="parts">'+''.join(f'<div class="{k}"><b>{t}</b>{d}</div>' for k,(t,d) in zip('abc',abc))+'</div>'
P1="이 폴더의 규칙(.github/copilot-instructions.md)과 회의록 폴더의 파일을 모두 읽어 줘. 회의마다 '정해진 것'과 '정해지지 않은 것'을 나눠서 정리하고, 정해진 것에는 누가 언제까지 하는지가 회의록에 적혀 있는지도 표시해 줘. 아직 파일은 만들지 마."
P1rich='<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 회의록 폴더의 파일을 모두 읽어 줘.</span> <span class="p-b">회의마다 \'정해진 것\'과 \'정해지지 않은 것\'을 나눠서 정리하고, 정해진 것에는 누가 언제까지 하는지가 회의록에 적혀 있는지도 표시해 줘.</span> <span class="p-c">아직 파일은 만들지 마.</span>'
P2=P('2_prompt.txt'); P3=P('3_prompt.txt'); P5a=P('5a_prompt.txt'); P5b=P('5b_prompt.txt'); P6=P('6_prompt.txt'); P6b=P('6b_prompt.txt'); P7=P('7_prompt.txt')
res=json.load(open(R+'완성/결과/회의록_1_작업목록.json',encoding='utf-8'))
res2=json.load(open(R+'완성/결과/회의록_2_작업목록.json',encoding='utf-8'))
def row(k,marks=()):
    t=res['작업'][k]; f=lambda v: e(v)
    c=[f(t['할일']),f(t['담당자']),f(t['완료시점']),'<br>'.join('"'+f(x)[:70]+('…' if len(x)>70 else '')+'"' for x in t['근거'][:2])]
    for m in marks: c[m]='<mark>'+c[m]+'</mark>'
    return '<tr>'+''.join(f'<td>{x}</td>' for x in c)+'</tr>'
pick=lambda s: next(i for i,t in enumerate(res['작업']) if s in t['할일'])
table='<table class="res"><thead><tr><th>할일</th><th style="width:108px">담당자</th><th style="width:128px">완료시점</th><th style="width:36%">근거 (원문)</th></tr></thead><tbody>'+row(pick('정기 점검표'),(0,))+row(pick('쿨러 팬 모터'),(1,2))+row(pick('교육한다'),(1,))+row(pick('품질 검사 결과'),(2,))+row(pick('환기 팬'),(0,))+'</tbody></table>'
care=res['따로 챙길 것']
caretable='<table class="res"><thead><tr><th style="width:110px">묶음</th><th style="width:60px">건수</th><th>모인 작업 (할일 그대로)</th></tr></thead><tbody>'+''.join(f'<tr><td><b>{e(k)}</b></td><td>{len(v)}</td><td>'+('<br>'.join(e(x) for x in v) if v else '없음')+'</td></tr>' for k,v in care.items())+'</tbody></table>'
both=[x for x in care['담당 미정'] if x in care['기한 미정']]
open_=next(m for m in res['미결 안건'] if '경보' in m['안건'])
care2=res2['따로 챙길 것']
N1,N2=len(res['작업']),len(res2['작업'])
choices='''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>값이 없을 때</b></td><td><mark>1번 줄</mark> 담당자나 완료 시점이 회의록에 없으면 「미정」이라고 적는다</td><td>낱말을 바꾼다(예: 「확인 필요」). 빈칸으로 두게 하면 빠뜨린 것인지 없는 것인지 가릴 수 없다</td></tr>
<tr><td><b>날짜가 아닌 표현</b></td><td><mark>2번 줄</mark> 「다음 주 금요일」처럼 하루로 정해지는 것만 날짜로 바꾸고 원래 표현을 괄호로 붙인다. 「이번 주 안」은 그대로 둔다</td><td>모두 원래 표현 그대로 두게 한다. 풀이가 틀릴 일은 없지만 날짜순으로 늘어놓을 수 없다</td></tr>
<tr><td><b>담당이 둘, 같은 일이 두 번</b></td><td><mark>3번 줄</mark> 둘 다 적고 「공동 담당」, 두 번 나온 일은 하나로 합치고 「중복」</td><td>합치지 않고 두 줄에 모두 「중복」을 붙이게 한다. 회의록의 차례가 그대로 남지만 목록이 길어진다</td></tr>
<tr><td><b>결론이 안 난 안건</b></td><td><mark>4번 줄</mark> 작업 목록에 넣지 않고 「미결 안건」으로 따로 둔다</td><td>작업 목록 안에 담당자 「미정」으로 넣게 한다. 한 표에서 다 보이지만 할 일과 논의가 섞인다</td></tr>
<tr><td><b>지난 회의에서 넘어온 일</b></td><td><mark>5번 줄</mark> 끝난 일은 빼고, 안 끝난 일은 넣고 「이월」</td><td>끝난 일도 「완료」로 남기게 한다. 경과는 남지만 다음 행동의 목록이 아니게 된다</td></tr>
</tbody></table>'''

pages=[]
pages.append(hero('준비','<small>통합반 오프라인 6회차 · 실습 3 · 50분</small>회의록을 「누가 · 무엇을 · 언제까지」로<br>바꾸는 스킬을 만든다','회의가 끝나면 회의록이 남지만, 회의록은 일을 시키지 않는다. 누가 무엇을 언제까지 해야 하는지는 누군가 다시 읽고 뽑아야 한다. 오늘은 그 일을 Copilot에게 맡긴다. 한 번 부탁하고 끝내는 것이 아니라, 일하는 방법을 <code>SKILL.md</code> 한 파일로 적어 두고 회의록이 바뀌어도 같은 방법으로 처리되게 한다.',[('끝나면 남는 것','두 번 고쳐 쓴 SKILL.md, 작업 목록 파일 네 개'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna)'),('전제','온라인 6일차의 스킬 단원을 들었다'),('준비에 쓰는 시간','약 4분')])
+'<section class="sect"><h2>오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과가 맞는지 판단하는 것이다. 그래서 요청하는 글보다 <b>요청하는 순서</b>가 중요하다. 이 순서는 뒤의 실습에서도 그대로 쓴다.</p><div class="flow"><div><em>1</em><b>읽게 한다</b>만들기 전에 자료를 읽고 이해한 것을 말하게 한다</div><div><em>2</em><b>정해 준다</b>무엇이 나오면 끝인지, 빈자리를 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>바로 만들지 않고 어떻게 할지 먼저 듣는다</div><div><em>4</em><b>작게 만든다</b>파일 하나를 만들고, 돌려 보고, 원문과 맞춘다</div><div><em>5</em><b>되돌려 준다</b>아쉬운 곳은 무엇이 왜 문제인지 말해 고친다</div></div><p style="margin:18px 0 0">1~4단계와 7단계가 이 다섯 걸음이다. 그 사이에 세 가지를 더 해 본다. 규칙에 어긋나는 요청을 일부러 보내 보고(5단계), 스킬에 기능을 하나 더하고(6단계), 같은 스킬을 다른 회의록에 쓴다(8단계).</p></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p><div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>회의록/</span>\n│  ├─ 회의록_1.txt             <i>← 정기 회의록</i>\n│  └─ 회의록_2.txt             <i>← 주간 협의 메모</i>\n└─ <span>결과/</span>                      <i>← 지금은 비어 있다</i></div><div><p><b>규칙 파일</b>은 Copilot이 이 폴더에서 일할 때 지키는 약속이다. 회의록 원문을 고치지 않는다, 없는 값을 지어내지 않는다 같은 것이 적혀 있다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 회의록, 결과 세 폴더가 펼쳐져 보이게.'))
+do(2,'editor','VS Code · 편집기','<code>회의록_1.txt</code>를 직접 훑어 읽는다','<p>탐색기에서 <code>회의록/회의록_1.txt</code>를 눌러 연다. 설비보전팀의 10월 정기 회의록이고 안건이 아홉 개다. 뒤에서 Copilot의 결과가 맞는지를 가리는 사람은 나다. 원문을 모르면 가릴 수 없다.</p><p>읽으면서 안건마다 세 가지를 따져 본다.</p><ul class="ask"><li><b>하기로 한 일인가, 의견만 오간 것인가</b>4번 안건처럼 결론 없이 끝난 것이 있다.</li><li><b>누가 하는가</b>이름이 적혀 있는가. 두 사람인가. 불참한 사람이나 부서 이름만 나오는가.</li><li><b>언제까지인가</b>날짜가 적혀 있는가. 「다음 주 금요일」, 「교육 전까지」처럼 날짜가 아닌 말인가. 아예 없는가.</li></ul><p>셋 가운데 하나라도 답이 회의록에 없는 안건의 번호를 종이에 적어 둔다. 1단계에서 쓴다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일의 세 절을 구분해 읽는다','<p><code>.github/copilot-instructions.md</code>를 연다. 절이 셋이다. 「하면 안 되는 것」과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 5단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」의 다섯 줄은 규칙이 일부러 비워 둔 자리이고, 2단계에서 내가 채운다.</p>')
+nxt(1,'1. 만들기 전에, 먼저 읽게 한다'))

pages.append(hero('1단계','만들기 전에,<br>먼저 읽게 한다','AI에게 일을 시킬 때 첫마디가 「만들어 줘」이면, AI는 자료를 읽자마자 만들기 시작한다. 잘못 이해한 것이 있어도 그대로 결과물에 들어간다. 그래서 첫 요청은 <b>읽고, 이해한 것을 말해 보라</b>는 요청으로 한다.',[('걸리는 시간','약 5분'),('이 단계가 끝나면','Copilot이 회의록을 어떻게 이해했는지가 채팅에 정리되어 있다'),('아직 없어야 하는 것','새 파일')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+do(1,'chat','Copilot 채팅','채팅을 열고, 두 가지를 확인한다','<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'+shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+do(2,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>'+copy(P1,rich=P1rich)+parts(('무엇을 읽는가','규칙 파일과 회의록 두 편. 읽을 대상을 내가 정해 준다.'),('어떤 모양으로 답하는가','「정해진 것 / 정해지지 않은 것」으로 나누게 했다. 뒤에서 내가 원문과 견주기 쉽다.'),('하지 말 것','이 요청에서 가장 중요한 문장이다. 이 한 줄이 없으면 읽자마자 만들기 시작한다.')))
+do(3,'chat','Copilot 채팅 · 답','돌아온 답에서 세 가지를 찾는다','<p>답이 오는 데 1분쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 회의록_1의 「정해진 것」 정리와, 답의 끝에서 「정해 주셔야 할 것」을 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>담당자나 날짜가 없는 일</b><span>준비 단계에서 내가 적어 둔 안건 번호와 같은가. 예: 3번 안건의 예비품 발주는 담당도 납기도 정해지지 않았다.</span></p></div><div><i>②</i><p style="margin:0"><b>결론이 나지 않은 안건</b><span>4번 「경보 기준 온도」처럼 의견만 오가고 끝난 안건이 「정해진 것」에 섞여 있지 않은가.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 나에게 되묻는 것</b><span>답의 끝에 「정해 주셔야 할 것」이 있는가. 몇 가지인지 세어 둔다. 다음 단계에서 이 물음에 내가 답한다.</span></p></div></div><div class="note"><b>되묻는 까닭</b>규칙 파일에 「정해져 있지 않은 것은 스스로 정하지 말고 묻는다」고 적어 두었기 때문이다. 규칙이 없었다면 이 자리들은 AI가 알아서 채웠을 것이고, 무엇이 어떻게 정해졌는지는 결과를 뜯어보아야 알 수 있다.</div><div class="if"><div><b>파일이 생겨 버렸다면</b>탐색기에 새 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.</div><div><b>내가 읽은 것과 다르다면</b>「다시 해 줘」라고 하지 않는다. 「5번 안건의 담당이 원문과 달라. 원문에는 "한서윤과 오민재가 같이 맡는다."라고 적혀 있어.」처럼 어디가 어떻게 다른지를 말한다.</div></div>')
+nxt(2,'2. 빈자리를 내가 정하고, 계획부터 받는다',0))

pages.append(hero('2단계','빈자리를 내가 정하고,<br>계획부터 받는다','Copilot이 되물은 것은 귀찮은 질문이 아니라 이 스킬의 설계 그 자체다. 담당자가 없는 일을 「미정」이라 적을지 빈칸으로 둘지, 「다음 주 금요일」을 날짜로 바꿀지 그대로 둘지에 따라 결과물이 달라진다. 정답이 하나가 아니므로 <b>요청하는 사람이 정한다.</b> 7일차에 배우는 명세를 작게 미리 써 보는 자리다.',[('걸리는 시간','약 7분'),('이 단계가 끝나면','내 결정이 반영된 계획이 채팅에 있다'),('아직 없어야 하는 것','새 파일')])
+do(1,'chat','이 화면의 표 → Copilot 채팅','다섯 빈자리마다 어느 쪽으로 정할지 고른다','<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>'+choices+'<div class="note"><b>처음이라면 그대로 보낸다</b>완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다.</div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (1단계와 같은 대화)','고른 답을 보내고, 계획부터 달라고 한다','<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'+copy(P2,pre=True,rich=richpre(P2,'abbc'))+parts(('무엇을 만드는가','첫 문단. 스킬의 이름과, 넣는 것과 나오는 것을 말한다. 「요약이 아니라 다음 행동」이라는 한마디가 결과의 성격을 정한다.'),('빈자리 다섯 가지','번호를 붙여 한 줄에 결정 하나씩 적었다. Copilot도 나도 빠뜨린 것을 번호로 짚을 수 있다.'),('계획 먼저','마지막 문단. 규칙 파일에 「계획을 먼저 말해 달라고 하면 계획만 말한다」는 줄이 있어, 이 말을 들으면 만들지 않고 멈춘다.')))
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 두 가지를 찾는다','<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 「이렇게 만들겠다」와 「이것은 정해 달라」가 함께 온다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 「만드는 순서」와 「정해 주셔야 할 것」이 보이게. 요청하지 않았는데 들어온 단계와, 다시 물어 온 항목에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>내가 시키지 않았는데 계획에 들어온 일</b><span>예를 들어 「다 만든 뒤 두 회의록에 미리 적용해 보겠다」 같은 단계다. 나쁜 제안은 아니지만 요청한 적이 없다. 할지 말지는 내가 정한다.</span></p></div><div><i>②</i><p style="margin:0"><b>다시 물어 온 것</b><span>다섯 가지를 정해 주었는데도 빈자리가 더 나온다. 예: 「공동 담당」 표시를 JSON의 어느 칸에 적을지, 「청소 주기를 바꾼다」처럼 할 일이 따로 없는 결정은 어디에 둘지. Copilot이 권하는 답이 함께 적혀 있는지 본다.</span></p></div></div><div class="note"><b>계획부터 받는 까닭</b>계획을 받지 않고 바로 만들게 했다면, 이 결정들은 내가 모르는 사이에 내려져 결과물에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.</div><div class="if"><div><b>계획 없이 파일부터 만들었다면</b>요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.</div><div><b>되묻는 것이 하나도 없다면</b>그대로 다음 단계로 간다. 물을 것이 없을 만큼 정해 주었다는 뜻이다. 다만 계획에 내가 정하지 않은 값이 들어 있지 않은지는 읽어 본다.</div></div>')
+nxt(3,'3. 스킬 파일 하나만 먼저 만든다',1))

pages.append(hero('3단계','스킬 파일 하나만<br>먼저 만든다','이제 만들게 한다. 다만 한 번에 전부가 아니라 <code>SKILL.md</code> 한 파일에서 멈추게 한다. 스킬과 결과 파일이 한꺼번에 생기면, 결과가 이상할 때 스킬이 잘못 쓰인 것인지 스킬은 맞는데 잘못 따른 것인지를 가릴 수 없다. <b>스킬을 먼저 읽어 확인하고, 그다음에 돌린다.</b>',[('걸리는 시간','약 6분'),('이 단계가 끝나면','.github/skills/meeting-actions/SKILL.md 한 파일이 있다'),('아직 없어야 하는 것','결과 파일')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','계획에 답하고, 범위를 정해 준다','<p>계획에 대한 답은 세 마디면 된다. 받을 것, 뺄 것, 이번에 만들 범위다.</p>'+copy(P3,pre=True,rich='<span class="p-a">계획 확인했어. 네가 낸 제안은 모두 그대로 받아들일게.</span> <span class="p-b">다만 내가 요청하지 않은 일이 계획에 들어 있으면 그건 빼 줘.</span>\n\n<span class="p-c">지금은 .github/skills/meeting-actions/SKILL.md 한 파일만 만들고 멈춰. 결과 파일은 아직 만들지 마.</span>')+parts(('받을 것','Copilot이 권한 답을 그대로 받는다. 받고 싶지 않은 제안이 있으면 보내기 전에 「다만 ○번은 이렇게 해 줘」를 한 줄 더한다.'),('뺄 것','앞 단계의 ①에서 찾은, 시키지 않은 일을 뺀다. 무엇인지 하나하나 짚지 않아도 「요청하지 않은 일」이라고 하면 Copilot이 가려낸다.'),('범위','파일 하나에서 멈추게 한다. 만들 것과 만들지 않을 것을 둘 다 적었다.')))
+do(2,'chat','Copilot 채팅','파일을 만들어도 되는지 물으면, 경로를 읽고 허용한다','<p>Copilot이 파일을 만들거나 고치려 할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 경로가 <code>.github/skills/meeting-actions/SKILL.md</code>가 맞는지 읽는다. 물음을 읽지 않고 넘기는 버릇은 뒤의 실습에서 문제가 된다.</p>'+shot('Copilot이 SKILL.md를 만들면서 허용을 묻거나 변경을 보여 주는 화면. 파일 경로와 「유지/허용」 버튼이 보이게.'))
+do(3,'editor','VS Code · 편집기','만들어진 <code>SKILL.md</code>를 열어 읽는다','<p>탐색기에서 <code>.github/skills/meeting-actions/SKILL.md</code>를 연다. 이 파일은 AI가 썼지만, 앞으로 이 스킬이 하는 일은 모두 여기 적힌 대로다. 온라인에서 배운 여섯 가지가 어디에 적혀 있는지 찾는다.</p><table class="res"><thead><tr><th>여섯 가지</th><th>파일에서 찾을 곳</th></tr></thead><tbody><tr><td><b>호출 조건</b></td><td>맨 위 머리말의 <code>description</code>. 어떤 요청에 쓰는 스킬인지가 한 줄로 적혀 있는가</td></tr><tr><td><b>작업 목적</b></td><td>제목 바로 아래 문단. 요약이 아니라 작업 목록이라고 적혀 있는가</td></tr><tr><td><b>입력</b></td><td>무엇을 받는가. 회의록 파일 하나</td></tr><tr><td><b>예외 지침</b></td><td>내가 정한 것들. 「미정」, 「공동 담당」, 「중복」, 「이월」이 내가 보낸 대로 적혀 있는가</td></tr><tr><td><b>순서</b></td><td>번호가 붙은 절차. 읽기에서 결과 파일까지 어떤 차례인가</td></tr><tr><td><b>출력</b></td><td>결과 파일의 이름과 네 칸(할일 · 담당자 · 완료시점 · 근거)</td></tr></tbody></table><div class="if"><div><b>내가 정한 것과 다르게 적혀 있다면</b>지금 고친다. 「완료시점 규칙이 내가 말한 것과 달라. 하루로 정해지지 않는 표현은 원래 표현만 적으라고 했어. 그 부분만 고쳐 줘.」처럼 어디가 어떻게 다른지를 말한다.</div><div><b>다른 파일도 생겼다면</b>요청의 둘째 문단이 빠진 것이다. 생긴 파일을 지우고 「SKILL.md 한 파일만」이라고 다시 말한다.</div></div>')
+nxt(4,'4. 스킬을 돌리고, 원문과 한 줄씩 맞춘다',2))

pages.append(hero('4단계','스킬을 돌리고,<br>원문과 한 줄씩 맞춘다','스킬을 처음 돌린다. 지금까지의 대화에는 회의록을 정리한 내용이 이미 들어 있어서, 같은 대화에서 돌리면 스킬을 따른 것인지 앞의 대화를 기억해 답한 것인지 구분할 수 없다. <b>새 대화를 열어 스킬만으로 돌린다.</b>',[('걸리는 시간','약 7분'),('이 단계가 끝나면','결과 폴더에 작업 목록 파일 두 개가 있다'),('맞춰 볼 것','결과의 모든 줄 ↔ 회의록 원문')])
+do(1,'chat','Copilot 채팅 · 새 대화','새 대화를 열고 스킬을 부른다','<p>채팅 위쪽의 「새 채팅」(+) 단추로 새 대화를 연다. 그다음 아래 요청을 보낸다. 입력 칸에 <code>/</code>를 치면 스킬 이름이 목록에 뜨는데, 거기서 <code>meeting-actions</code>를 골라도 된다.</p>'+copy('meeting-actions 스킬로 회의록/회의록_1.txt 의 작업 목록을 만들어 줘.')+'<p>요청이 한 줄인 까닭은 조건이 모두 스킬에 적혀 있기 때문이다. 요청에는 어느 스킬로 어느 파일을 처리할지만 남는다.</p>'+shot('새 채팅 단추의 위치와, 입력 칸에 / 를 쳤을 때 meeting-actions가 목록에 뜬 화면.')+'<p>1분 남짓 뒤에 <code>결과</code> 폴더에 파일 두 개가 생긴다.</p>')
+do(2,'editor','VS Code · 편집기 (좌우로 나란히)','결과 파일과 회의록을 나란히 놓고 본다','<p><code>결과/회의록_1_작업목록.md</code>를 열고, <code>회의록/회의록_1.txt</code>를 오른쪽으로 끌어 나란히 둔다. 작업 한 줄마다 <b>근거</b> 칸의 문장을 원문에서 찾아 짚는다. 찾을 수 없는 문장이 있다면 AI가 문장을 고쳐 썼거나 지어낸 것이다.</p><p>아래는 완성 폴더의 결과(작업 '+str(N1)+'건)에서 다섯 줄을 뽑은 것이다. 내 결과는 문장도 건수도 다를 수 있다. 노랗게 칠한 칸이 내가 정한 대로 되어 있는지를 본다.</p>'+table+'<div class="find"><div><i>①</i><p style="margin:0"><b>담당자 칸</b><span>회의록에 없는 사람이나 부서(「구매팀」), 불참자(백승우)가 담당자로 들어가 있지 않은가. 없으면 내가 정한 말(미정)로 적혀 있는가.</span></p></div><div><i>②</i><p style="margin:0"><b>완료시점 칸</b><span>날짜로 바꾼 값에 원래 표현이 괄호로 붙어 있는가. 하루로 정해지지 않는 표현을 억지로 날짜로 바꾸지 않았는가.</span></p></div><div><i>③</i><p style="margin:0"><b>표시</b><span>두 사람이 맡은 일, 두 번 나온 일, 지난 회의에서 넘어온 일에 내가 정한 표시가 붙어 있는가. 0번 안건의 이미 끝난 일(유압 호스 교체)은 목록에 없어야 한다.</span></p></div><div><i>④</i><p style="margin:0"><b>미결 안건</b><span>4번 「경보 기준 온도」가 작업 목록이 아니라 미결 안건에 있는가.</span></p></div></div><p>마지막으로 <code>결과/회의록_1_작업목록.json</code>을 열어 작업 한 건의 칸이 <code>할일</code>, <code>담당자</code>, <code>완료시점</code>, <code>근거</code> 넷뿐인지 본다. 이 이름은 규칙 파일이 정해 둔 것이어서 누가 만들어도 같다.</p>'+shot('결과 md 파일과 회의록 원문을 좌우로 나란히 연 VS Code 화면.')+'<div class="if"><div><b>스킬을 찾지 못한다고 하면</b>탐색기에서 <code>.github/skills/meeting-actions/SKILL.md</code>가 그 자리에 있는지 본다. 있으면 요청의 앞에 그 경로를 적어 「이 파일의 지침대로」라고 말한다.</div><div><b>원문에 없는 근거 문장을 찾았다면</b>어느 줄의 어느 문장인지를 적어 둔다. 7단계에서 되돌려 줄 거리가 된다.</div></div>')
+nxt(5,'5. 규칙을 일부러 건드려 본다',3))

pages.append(hero('5단계','규칙을 일부러<br>건드려 본다','지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 실제 일터에서는 급할 때 누구나 「원문 좀 고쳐 줘」, 「칸 이름만 바꿔 줘」라고 말하게 된다. 그 말을 지금 일부러 해 본다. <b>보내기 전에, 고쳐 줄지 멈출지 먼저 짐작해 둔다.</b>',[('걸리는 시간','약 5분'),('이 단계가 끝나면','Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'),('바뀌면 안 되는 것','회의록 원문, 결과 JSON')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (4단계와 같은 대화)','회의록 원문을 고쳐 달라고 해 본다','<p>결과에 「미정」이 많은 것은 3번 안건에 담당과 납기가 없어서다. 회의록에 한 줄만 써 넣으면 결과가 깔끔해진다. 그럴듯한 요청이지만 규칙 두 가지에 걸린다.</p>'+copy(P5a,'Copilot에게 보낼 요청 (규칙에 어긋난다)')+shot('위 요청에 Copilot이 회의록을 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>파일이 그대로인가</b><span>편집기에서 <code>회의록/회의록_1.txt</code>를 열어 3번 안건 끝에 새 줄이 없는지 본다. 결과 파일의 예비품 두 줄도 「미정」 그대로여야 한다.</span></p></div><div><i>②</i><p style="margin:0"><b>어느 규칙을 들었는가</b><span>답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다.</span></p></div><div><i>③</i><p style="margin:0"><b>멈추기만 했는가</b><span>안 된다고만 하지 않고, 규칙 안에서 할 수 있는 길(예: 사람이 회의록에 직접 써 넣은 뒤 결과를 다시 맞춘다)을 내놓았는가.</span></p></div></div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','정해진 칸 이름을 바꿔 달라고 해 본다','<p>이번에는 「하면 안 되는 것」이 아니라 「정해져 있는 것」을 건드린다. 한글 칸 이름이 다른 프로그램에서 불편하다는 것은 실제로 나올 법한 불만이다.</p>'+copy(P5b,'Copilot에게 보낼 요청 (규칙에 어긋난다)')+'<p>답이 오면 <code>결과/회의록_1_작업목록.json</code>을 열어 칸 이름이 <code>할일</code>, <code>담당자</code>, <code>완료시점</code>, <code>근거</code> 그대로인지 본다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p><ul class="ask"><li><b>첫째 요청</b>두 줄에 걸린다. 둘 다 「하면 안 되는 것」 절에 있다. 한 줄은 회의록을 고치는 일을, 다른 한 줄은 회의에서 정하지 않은 담당자와 날짜를 적어 넣는 일을 막는다. 몇 번과 몇 번인가.</li><li><b>둘째 요청</b>「정해져 있는 것」 절의 한 줄이다. 칸 이름 네 낱말이 적힌 줄을 찾는다.</li></ul><p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p><div class="note"><b>막은 것은 파일의 한 줄이다</b>Copilot이 눈치껏 조심한 것이 아니라 규칙 파일에 적힌 문장을 따른 것이다. 그래서 규칙을 바꾸고 싶을 때는 채팅에서 밀어붙이지 않고 규칙 파일을 고친다. 그 변경은 파일에 남아 같이 일하는 사람 모두가 본다. 한글 칸 이름이 정말 불편하다면 그것이 맞는 길이다.</div><div class="if"><div><b>멈추지 않고 고쳐 버렸다면</b>편집기에서 회의록에 더해진 줄을 직접 지우고 저장한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.</div><div><b>「이번만 예외라고 말해 주면 하겠다」고 한다면</b>오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.</div></div>')
+nxt(6,'6. 스킬에 기능을 하나 더한다',4))

pages.append(hero('6단계','스킬에 기능을<br>하나 더한다','스킬은 한 번 쓰고 닫는 파일이 아니다. 쓰다 보면 더 있었으면 하는 것이 생기고, 그때마다 고쳐 키운다. 지금 결과에서 담당자나 기한이 「미정」인 일, 「중복」 표시가 붙은 일은 회의가 끝난 뒤 누군가 다시 챙겨야 하는데, 작업 표 안에 흩어져 있다. <b>이 항목들을 따로 모아 보여 주는 절을 스킬에 더한다.</b>',[('걸리는 시간','약 6분'),('이 단계가 끝나면','결과의 끝에 「따로 챙길 것」 절이 있다'),('바뀌면 안 되는 것','작업 표, 작업 한 건의 네 칸')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','더할 기능을 말하고, 결과를 다시 만들게 한다','<p>기능을 더할 때도 고치는 곳은 결과 파일이 아니라 스킬이다. 결과 파일만 고치면 다음 회의록에서는 새 절이 나오지 않는다.</p>'+copy(P6,pre=True,rich=richpre(P6,'abc'))+parts(('무엇이 왜 필요한가','첫 문단. 무엇을 더할지보다 왜 필요한지를 먼저 말했다. 까닭을 알면 Copilot이 요청에 없는 세부를 그 목적에 맞게 정한다.'),('어떤 모양인가','둘째 문단. 절의 이름, 세 묶음, 한 작업이 두 묶음에 걸릴 때, JSON에 두는 자리까지 정했다. 규칙이 정한 네 칸은 그대로 두라고 적었다.'),('어디를 어디까지','셋째 문단. 스킬을 먼저 고치고 결과를 다시 만드는 차례와, 건드리지 않을 곳을 적었다.')))
+do(2,'editor','VS Code · 편집기','결과의 끝에 생긴 절을 작업 표와 맞춘다','<p><code>결과/회의록_1_작업목록.md</code>를 다시 연다. 맨 끝에 「따로 챙길 것」이 생겼다. 아래는 완성 폴더의 결과다.</p>'+caretable+'<div class="find"><div><i>①</i><p style="margin:0"><b>건수가 작업 표와 맞는가</b><span>작업 표에서 담당자가 「미정」인 줄을 세어 「담당 미정」의 건수와 견준다. 「기한 미정」도 같은 방법으로 센다.</span></p></div><div><i>②</i><p style="margin:0"><b>양쪽에 다 적힌 작업</b><span>담당도 기한도 없는 일은 두 묶음에 모두 있어야 한다. 완성 폴더의 결과에서는 '+str(len(both))+'건이다.</span></p></div><div><i>③</i><p style="margin:0"><b>Copilot이 스스로 정한 것</b><span>「이번 주 안」, 「교육 전까지」처럼 날짜가 아닌 표현으로 적힌 일은 「기한 미정」에 들어 있는가. 요청에 적지 않은 것이어서 Copilot이 정했고, 답에 그렇게 정했다고 밝혔는지 본다.</span></p></div><div><i>④</i><p style="margin:0"><b>JSON</b><span>맨 바깥에 <code>따로 챙길 것</code>이 더해졌고, 작업 한 건의 칸은 여전히 넷인가.</span></p></div></div>')
+do(3,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','남은 어긋남을 맞춘다','<p>앞의 요청에서 「다른 절은 건드리지 마」라고 했다. 그래서 <code>SKILL.md</code>의 절차와 결과 파일의 예시에는 새 절이 빠져 있다. 범위를 좁히면 엉뚱한 곳이 바뀌지 않는 대신, 남는 어긋남은 요청한 사람이 챙겨야 한다. Copilot이 답의 끝에서 이것을 먼저 짚었는지 본 다음 아래를 보낸다.</p>'+copy(P6b)+shot('Copilot이 SKILL.md에 「따로 챙길 것」을 더한 변경 화면. 새로 생긴 절이 초록색으로 표시되고, 다른 절은 바뀌지 않은 것이 보이게.')+'<div class="if"><div><b>작업 표가 바뀌었다면</b>4단계에서 본 줄이 사라지거나 문장이 달라졌다면, 어느 줄이 어떻게 달라졌는지를 말하고 작업 표는 그대로 두라고 다시 요청한다.</div><div><b>새 파일이 생겼다면</b>규칙이 정한 결과 파일은 회의록마다 둘뿐이다. 「따로 챙길 것」이 다른 파일로 나왔다면 지우고, 기존 두 파일의 끝에 넣으라고 말한다.</div></div>')
+nxt(7,'7. 아쉬운 곳을 찾아 되돌려 준다',5))

pages.append(hero('7단계','아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다','결과가 규칙대로 나왔더라도 실제로 쓰려고 보면 아쉬운 곳이 보인다. 예를 들어 미결 안건에 「결론을 내지 못했다」만 실려 있으면, 다음 회의를 준비하는 사람은 누가 어떤 의견이었는지를 알 수 없다. 틀린 것은 아니지만 쓸모가 모자란다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','SKILL.md의 한 곳이 내 요청대로 바뀌어 있다')])
+'<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>미결 안건이 마음에 안 들어. 다시 해 줘.</q>무엇이 문제인지 AI는 모른다. 전체를 다시 쓰거나, 무엇을 원하는지 되묻는다. 한 번 더 주고받아야 한다.</div><div class="good"><b>구체적으로</b><q>미결 안건에 누가 어떤 의견이었는지가 없어서 다음 회의를 준비할 수 없어. 의견을 낸 사람과 그 문장도 근거에 싣도록 SKILL.md의 미결 안건 부분을 고치고, 회의록_1의 결과를 다시 만들어 줘. 다른 절은 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div><div class="four"><div><b>무엇이</b>미결 안건에 의견이 없다</div><div><b>왜</b>다음 회의를 준비할 수 없다</div><div><b>어디를</b>결과 파일이 아니라 스킬의 그 부분</div><div><b>어디까지</b>다른 절은 건드리지 않는다</div></div><div class="note"><b>6단계의 요청을 다시 본다</b>기능을 더할 때 보낸 글에도 이 네 가지가 들어 있었다. 흩어져 있어 한눈에 보이지 않는다(무엇이 · 왜), 스킬에 더한다(어디를), 다른 절은 건드리지 마(어디까지).</div></section>'
+do(1,'editor','VS Code · 편집기','내 결과에서 아쉬운 곳 하나를 고른다','<p>결과 파일을 다시 본다. 사람마다 판단이 갈릴 만한 곳이 있다. 아래에서 골라도 되고 스스로 찾아도 된다. 4단계에서 적어 둔 것이 있으면 그것을 쓴다.</p><ul class="ask"><li><b>미결 안건에 의견이 실려 있는가</b>누가 어떤 의견이었는지가 없으면 다음 회의 준비에 쓸 수 없다.</li><li><b>「필터 망 시험 설치의 결과를 보고한다」의 담당자</b>회의록은 설치와 데이터 정리의 담당만 적었다. 보고의 담당을 「미정」으로 둘 것인가, 결과를 만들기 전에 물어보게 할 것인가.</li><li><b>「기한 미정」의 범위</b>「교육 전까지」, 「게시 전에」처럼 날짜가 없는 일도 따로 챙길 것에 넣을 것인가.</li></ul>')
+do(2,'chat','이 화면의 글 칸 → Copilot 채팅 (같은 대화)','네 가지를 넣어 되돌려 준다','<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다.</p>'+write('w7','무엇이 문제인지, 왜 문제인지, SKILL.md의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')+'<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(미결 안건의 의견)를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>'+copy(P7,'Copilot에게 보낼 요청',pre=True)+'</details><p style="margin-top:18px">고친 뒤에는 <code>SKILL.md</code>에서 요청한 부분만 바뀌었는지, 결과 파일이 고친 스킬대로 다시 만들어졌는지를 본다. 완성 폴더의 결과에서는 미결 안건 「'+e(open_['안건'])+'」의 근거가 한 문장에서 '+str(len(open_['근거']))+'문장으로 늘었고, 의견을 낸 세 사람의 이름이 원문대로 실려 있다.</p>'+shot('되돌려 준 뒤 Copilot이 SKILL.md의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색으로 표시된 화면).')+'<div class="if"><div><b>요청하지 않은 절까지 바뀌었다면</b>「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 절의 이름을 들어 원래대로 돌려 달라고 한다.</div><div><b>Copilot이 되물었다면</b>요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 되묻지 않고 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다.</div></div>')
+nxt(8,'8. 같은 스킬을 다른 회의록에 쓴다',6))

pages.append(hero('8단계','같은 스킬을<br>다른 회의록에 쓴다','스킬을 만든 까닭은 다시 쓰기 위해서다. <code>회의록_2.txt</code>는 첫째 회의록과 모양이 다르다. 번호도 없고, 메모처럼 적혀 있고, 화요일 회의에서 넘어온 일도 섞여 있다. 처음 정한 다섯 가지와 6 · 7단계에서 더하고 고친 것이 여기에도 그대로 통하는지 본다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','결과 폴더에 파일이 네 개 있다')])
+do(1,'chat','Copilot 채팅 · 새 대화','새 대화에서 한 줄로 시킨다','<p>「새 채팅」(+)으로 새 대화를 연다. 앞의 대화에서 주고받은 조건을 Copilot이 기억해 답하는 것이 아니라, 스킬 파일에 적힌 것만으로 돌아가는지를 보려는 것이다. 요청은 4단계와 파일 이름만 다르다.</p>'+copy('meeting-actions 스킬로 회의록/회의록_2.txt 의 작업 목록을 만들어 줘.')+'<p>「미정으로 적어라」, 「따로 챙길 것을 더해라」, 「미결 안건에 의견을 실어라」는 말은 어디에도 없다.</p>')
+do(2,'editor','VS Code · 편집기','결과를 원문과 맞추고, 첫째 결과와 견준다','<p><code>결과/회의록_2_작업목록.md</code>를 원문과 나란히 놓고 본다. 완성 폴더의 결과는 작업 '+str(N2)+'건, 미결 안건 '+str(len(res2['미결 안건']))+'건이다.</p><div class="find"><div><i>①</i><p style="margin:0"><b>처음 정한 다섯 가지</b><span>「미정」, 「공동 담당」, 「이월」, 날짜 표현의 처리가 첫째 회의록 때와 같은 방식인가. 「내일」이 회의 날짜(10월 8일)를 기준으로 풀이되었는가.</span></p></div><div><i>②</i><p style="margin:0"><b>6단계에서 더한 것</b><span>끝에 「따로 챙길 것」이 있는가. 완성 폴더의 결과에서는 담당 미정 '+str(len(care2['담당 미정']))+'건, 기한 미정 '+str(len(care2['기한 미정']))+'건이고 중복은 없다.</span></p></div><div><i>③</i><p style="margin:0"><b>7단계에서 고친 것</b><span>미결 안건 「점검 체크리스트 양식」에 한서윤과 오민재의 의견이 원문대로 실려 있는가.</span></p></div></div><div class="note"><b>한 줄로 충분했던 까닭</b>조건은 요청이 아니라 스킬에 적혀 있다. 그래서 요청은 짧아지고, 결과는 매번 같은 모양으로 나온다. 한 번의 프롬프트와 재사용하는 지침의 차이다.</div>')
+'<section class="sect"><h2>시간이 남으면</h2><p>최근에 참석한 회의나 조별 모임의 메모를 텍스트 파일로 만들어 <code>회의록</code> 폴더에 직접 넣고(이 폴더에 파일을 넣는 것은 사람의 일이다) 스킬을 돌려 본다. 스킬이 묻지 않고 넘어간 곳, 반대로 묻지 않아도 될 것을 물은 곳이 있는지 보고, 있으면 스킬의 어느 절을 고쳐야 하는지 찾는다.</p><p style="margin:0">2단계에서 가운데 칸을 그대로 보냈다면, 표의 오른쪽 칸 가운데 하나(예: 같은 일이 두 번 나와도 합치지 않기)로 스킬을 고쳐 달라고 하고 회의록_1을 다시 돌려 무엇이 달라지는지 본다.</p></section>'
+nxt(None,None,7))

names=['준비','1. 읽게 한다','2. 정하고 계획 받기','3. 스킬 파일 만들기','4. 돌려서 맞추기','5. 규칙 건드려 보기','6. 기능 더하기','7. 되돌려 주기','8. 다시 쓰기']
MIN=[4,5,7,6,7,5,6,6,4]; assert sum(MIN)==50 and len(MIN)==len(names)==len(pages)
for i,p in enumerate(pages[1:],1): assert f'약 {MIN[i]}분' in p,i
assert sum(p.count('<textarea') for p in pages)==1
bar='<div class="bar"><div class="bar-in"><b>회의록 → 작업 목록 스킬</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-06-3-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 '+(names.length-1)+'단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 회의록을 작업 목록으로 바꾸는 스킬</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
