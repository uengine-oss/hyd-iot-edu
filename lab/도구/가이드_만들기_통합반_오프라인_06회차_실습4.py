import re, html, json
import os
LAB=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/'
R=LAB+'통합반_오프라인/06회차_실습4_도구_조합/'
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
    h=f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 내가 조건을 정한 work-items 스킬 하나와, 두 회의록의 업무 항목 파일 네 개</b></div></div>'
    if prev is not None: h+=f'<a class="back" data-go="{prev}">← 이전 단계로</a>'
    return h
P=lambda f: open(R+'기록/'+f,encoding='utf-8').read().strip()
def richpre(text,cls):  # 문단마다 밑줄 색을 입힌다(문단 수와 cls 의 길이가 같아야 한다)
    ps=text.split('\n\n'); assert len(ps)==len(cls),(len(ps),cls)
    return '\n\n'.join(f'<span class="p-{c}">{e(p)}</span>' for p,c in zip(ps,cls))
def parts(*abc): return '<div class="parts">'+''.join(f'<div class="{k}"><b>{t}</b>{d}</div>' for k,(t,d) in zip('abc',abc))+'</div>'
def copyto(text,head,foot,pre=True):
    cid[0]+=1; i=f'c{cid[0]}'
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}" id="{i}">{e(text)}</div><div class="copy-foot">{foot}</div></div>'
def term(text): return '<div class="tree" style="margin:14px 0;white-space:pre-wrap">'+e(text)+'</div>'
J=lambda f: json.load(open(R+f,encoding='utf-8'))
P1=P('1_prompt.txt'); P2=P('2_prompt.txt'); P3=P('3_prompt.txt'); P4=P('4_prompt.txt'); P5=P('5_prompt.txt'); P6a=P('6a_prompt.txt'); P6b=P('6b_prompt.txt'); P7=P('7_prompt.txt'); P8=P('8_prompt.txt')
assert P4.replace('회의록_1','회의록_2')==P5
P1rich='<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 스킬(.github/skills/meeting-actions/SKILL.md)을 읽어 줘. 그다음 지금 연결된 filesystem 서버와 git 서버에 어떤 도구가 있는지 보고, 도구마다 무엇을 넘겨야 하는지와 파일을 바꾸는 도구가 있는지를 말해 줘.</span> <span class="p-b">filesystem 서버로 자료 폴더에 무슨 파일이 있는지 살펴보고, git 서버로 자료의 변경 기록이 모두 몇 건인지, 아직 변경 기록에 올라가지 않은 파일이 있는지도 알려 줘.</span> <span class="p-c">아직 파일은 만들지 마.</span>'
assert re.sub(r'<[^>]+>','',P1rich)==P1
res=J('완성/결과/회의록_1_업무항목.json'); res2=J('완성/결과/회의록_2_업무항목.json'); fail2=J('기록/5_회의록_2_업무항목_미완료.json')
N1,N2=len(res['작업']),len(res2['작업']); A1=res['변경확인 집계']; A2=res2['변경확인 집계']; F2=fail2['변경확인 집계']
assert sum(A1.values())==N1 and sum(A2.values())==N2 and F2['미완료']>0 and A2['미완료']==0
prep=P('0_자료_준비_출력.txt'); NC=len(re.findall(r'^[0-9a-f]{7}  ',prep,re.M)); assert f'변경 기록 {NC}건' in prep
gitlog=P('4_git_log_확인.txt'); NS=len(re.findall(r'^2026-',gitlog,re.M))
tools4=[l for l in P('4_tools.txt').split('\n')[1:] if 'mcp__' in l.split(' ')[1]]
mcp4=[l.split(' ')[1] for l in tools4]; FAIL4=sum(1 for l in tools4 if '-> 실패' in l)
cnt4=lambda s: sum(1 for x in mcp4 if x.endswith('__'+s))
WHY={'list_allowed_directories':'서버가 드나들 수 있는 폴더의 자리','read_text_file':'회의록 한 편과 자료/README.md','git_log':'짝이 되는 자료 파일마다 한 번. 그 파일을 건드린 변경의 날짜, 사람, 내용','git_status':'변경 기록에 올라가지 않은 파일','list_directory':'폴더 안의 파일 이름','git_show':'변경 한 건의 내용','git_diff':'아직 올리지 않은 변경','search_files':'낱말이 든 줄 찾기','get_file_info':'파일의 크기와 고친 시각'}
order=[]
for x in mcp4:
    if x not in order: order.append(x)
tooltable='<table class="res"><thead><tr><th style="width:120px">서버</th><th style="width:200px">도구</th><th style="width:70px">횟수</th><th>무엇을 하려고</th></tr></thead><tbody>'+''.join(f'<tr><td>{x.split("__")[1]}</td><td>{x.split("__")[2]}</td><td>{mcp4.count(x)}</td><td>{WHY[x.split("__")[2]]}</td></tr>' for x in order)+'<tr><td>(서버 아님)</td><td>파일 편집</td><td>2</td><td>업무 항목 md와 json을 결과 폴더에 저장</td></tr></tbody></table>'
assert FAIL4==1 and cnt4('read_text_file')==3
def rec(v): return e(v['날짜'])+' '+e(v['사람'])+' — "'+e(v['내용'])+'"'
def row(t,marks=()):
    c=[e(t['할일']),e(t['담당자']),'<br>'.join(e(x) for x in t['자료']) or '없음',e(t['변경확인']),'<br>'.join(rec(v) for v in t['변경기록']) or '없음']
    for m in marks: c[m]='<mark>'+c[m]+'</mark>'
    return '<tr>'+''.join(f'<td>{x}</td>' for x in c)+'</tr>'
pick=lambda d,s: next(t for t in d['작업'] if s in t['할일'])
TH='<table class="res"><thead><tr><th>할일</th><th style="width:92px">담당자</th><th style="width:150px">자료</th><th style="width:86px">변경확인</th><th style="width:34%">변경기록</th></tr></thead><tbody>'
table=TH+row(pick(res,'핀 상태'),(4,))+row(pick(res,'정기 점검표를'),(4,))+row(pick(res,'전원 차단 순서'),(4,))+row(pick(res,'쿨러 팬 모터'),(3,))+row(pick(res,'교육 자료'),(2,3))+'</tbody></table>'
other=[t for t in res['작업'] if any('담당자 아님' in v['사람'] for v in t['변경기록'])]
cmp_rows=''
for a,b in zip(fail2['작업'],res2['작업']):
    assert a['할일']==b['할일']
    if a['변경확인']=='미완료':
        cmp_rows+=f'<tr><td>{e(a["할일"])}</td><td>{"<br>".join(e(x) for x in a["자료"])}</td><td><mark>미완료</mark></td><td><b>{e(b["변경확인"])}</b>'+(''.join('<br>'+rec(v) for v in b['변경기록']))+'</td></tr>'
    else: assert a['변경확인']==b['변경확인']=='자료 없음'
cmptable='<table class="res"><thead><tr><th>할일</th><th style="width:170px">자료</th><th style="width:110px">서버가 끊겼을 때</th><th style="width:36%">고친 뒤</th></tr></thead><tbody>'+cmp_rows+'</tbody></table>'
ERR=fail2['도구 실패']
still=res['자료가 아직 바뀌지 않은 작업']; still2=res2['자료가 아직 바뀌지 않은 작업']
assert len(still)==A1['변경 없음'] and len(still2)==A2['변경 없음']
stilltable='<table class="res"><thead><tr><th>할일</th><th style="width:120px">담당자</th><th style="width:160px">완료시점</th></tr></thead><tbody>'+''.join(f'<tr><td>{e(x["할일"])}</td><td>{e(x["담당자"])}</td><td>{e(x["완료시점"])}</td></tr>' for x in still)+'</tbody></table>'
choices='''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>언제부터의 변경</b></td><td><mark>1번 줄</mark> 회의가 열린 날부터 본다. 전날까지의 변경은 넣지 않는다</td><td>회의 다음 날부터 보게 한다. 회의 전에 올린 변경이 섞일 일은 없지만, 회의가 끝난 그날 오후에 올린 변경이 빠진다</td></tr>
<tr><td><b>작업과 자료의 짝</b></td><td><mark>2번 줄</mark> 자료/README.md의 표를 보고 짝짓는다. 표에서 찾을 수 없으면 「자료 없음」</td><td>자료 파일의 내용까지 열어 보고 짝짓게 한다. 짝이 늘지만 느려지고, 짐작으로 붙은 짝이 섞인다</td></tr>
<tr><td><b>올라가지 않은 변경</b></td><td><mark>3번 줄</mark> 변경으로 치지 않는다. 그런 파일이 있다는 것만 md 파일의 끝에 따로 적는다</td><td>「변경 있음」으로 치게 한다. 손댄 흔적은 보이지만 누가 언제 바꿨는지는 적을 수 없다</td></tr>
<tr><td><b>바꾼 사람이 담당자와 다를 때</b></td><td><mark>4번 줄</mark> 이름 뒤에 「(담당자 아님)」을 붙인다</td><td>표시하지 않는다. 표는 깔끔해지지만 담당자가 한 일인지 다른 사람이 한 일인지를 이름을 견주어 찾아야 한다</td></tr>
<tr><td><b>도구가 실패했을 때</b></td><td><mark>5번 줄</mark> 멈추지 않는다. 확인하지 못한 항목만 「미완료」로 두고, 실패한 도구와 오류 문장을 파일에 적는다</td><td>실패하면 파일을 만들지 않고 멈추게 한다. 반쯤 채워진 파일이 돌아다닐 일은 없지만, 확인이 필요 없는 항목까지 함께 늦어진다</td></tr>
</tbody></table>'''
flow4='<div class="flow" style="grid-template-columns:repeat(4,1fr)"><div><em>1</em><b>회의록을 읽는다</b>filesystem 서버의 도구로 회의록 한 편을 읽는다</div><div><em>2</em><b>작업을 뽑는다</b>도구 없이, meeting-actions 스킬이 적어 둔 방법으로</div><div><em>3</em><b>변경을 확인한다</b>git 서버의 도구로 자료의 변경 기록을 본다</div><div><em>4</em><b>저장한다</b>업무 항목 두 파일을 결과 폴더에 쓴다</div></div>'
words='<table class="res"><thead><tr><th style="width:110px">변경확인</th><th>뜻</th><th style="width:150px">완성 폴더의 회의록_1</th></tr></thead><tbody>'+''.join(f'<tr><td><b>{k}</b></td><td>{v}</td><td>{A1[k]}건</td></tr>' for k,v in (('변경 있음','회의 뒤에 짝이 되는 자료가 바뀌었다. 일이 끝났다는 뜻은 아니다'),('변경 없음','변경 기록을 확인했고, 바뀐 것이 없다'),('자료 없음','짝이 되는 자료 파일이 없어 확인할 것이 없다'),('미완료','도구가 실패해 확인하지 못했다')))+'</tbody></table>'

pages=[]
pages.append(hero('준비','<small>통합반 오프라인 6회차 · 실습 4 · 50분</small>회의록 읽기, 변경 확인, 저장을<br>한 요청으로 잇는다','실습 3에서 만든 스킬은 회의록에서 누가 무엇을 언제까지 하는지를 뽑았다. 그런데 회의가 끝나고 며칠 뒤에 궁금한 것은 그다음이다. 그 일에 딸린 자료가 실제로 바뀌었는가. 이것은 회의록에는 없고 자료의 변경 기록에 있다. 오늘은 파일을 읽는 서버, 변경 기록을 보는 서버, 회의록 스킬을 <b>한 번의 요청</b>으로 이어 업무 항목을 만들고, 도중에 도구가 실패하면 어떻게 남겨야 하는지를 직접 겪는다.',[('끝나면 남는 것','내가 조건을 정한 work-items 스킬, 업무 항목 파일 네 개'),('쓰는 도구','VS Code · Copilot 채팅 (GPT-6 Luna) · MCP 서버 둘'),('전제','실습 2에서 서버를 연결해 보았고, 실습 3의 스킬이 있다'),('준비에 쓰는 시간','약 5분')])
+'<section class="sect"><h2>한 요청이 지나가는 길</h2><p>오늘 만드는 것은 아래 네 칸을 차례대로 지나가는 절차다. 1번과 3번은 서버의 도구가 실행하고, 2번은 스킬에 적힌 방법대로 모델이 하며, 4번은 Copilot의 파일 편집이 한다. 차례를 적어 두는 곳이 스킬이고, 실제로 읽고 조회하는 곳이 서버다.</p>'+flow4+'<p style="margin:18px 0 0">앞의 네 단계(읽게 한다, 정해 준다, 계획을 받는다, 작게 만들고 맞춘다)로 이 절차를 만들어 돌린다. 그다음 서버 하나를 일부러 끊어 보고(5단계), 그 상태에서 규칙에 어긋나는 요청을 보내 보고(6단계), 고친 뒤 다시 실행하고(7단계), 아쉬운 곳을 내 말로 되돌려 준다(8단계).</p></section>'
+do(1,'explorer','VS Code · 탐색기','받은 폴더 <code>시작</code>을 VS Code로 연다','<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다.</p><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  ├─ copilot-instructions.md           <i>← 이 폴더의 규칙</i>\n│  └─ skills/meeting-actions/SKILL.md   <i>← 실습 3에서 만든 스킬</i>\n├─ <span>.vscode/</span>\n│  └─ mcp.json                          <i>← 서버 둘의 연결 설정</i>\n├─ <span>회의록/</span>                            <i>← 실습 3의 회의록 두 편</i>\n├─ <span>서버/</span>                              <i>← 실습 2에서 연결해 본 서버 프로그램</i>\n├─ <span>도구/</span>\n│  └─ 자료_준비.py                       <i>← 자료 저장소를 만드는 프로그램</i>\n└─ <span>결과/</span>                              <i>← 지금은 비어 있다</i></div><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p>')
+do(2,'editor','VS Code · 터미널','자료 저장소를 만든다','<p>회의에서 나온 일의 자료(점검표, 절차서, 예비품 목록 등)는 설비보전팀의 저장소에 있고, 누가 고칠 때마다 변경 기록이 한 줄씩 남는다. 그 저장소를 내 PC에 만든다. 「터미널 → 새 터미널」을 열고 아래 명령을 실행한다.</p>'+copyto('python 도구/자료_준비.py','터미널에서 실행할 명령','붙여넣는 곳 → VS Code 아래쪽 터미널',pre=False)+'<p>탐색기에 <code>자료</code> 폴더가 생기고 터미널에 아래와 같이 나온다. 맨 앞의 일곱 글자는 변경 한 건의 번호이고, 누구의 PC에서 만들어도 같다.</p>'+term(prep)+'<ul class="ask"><li><b>변경 기록 '+str(NC)+'건</b>9월 14일부터 10월 12일까지다. 회의록_1의 회의는 10월 6일, 회의록_2의 회의는 10월 8일에 열렸다. 회의보다 앞선 변경이 몇 건인지 세어 둔다.</li><li><b>맨 아래의 <code>?? 교육/</code></b>폴더에는 있지만 변경 기록에는 아직 올라가지 않은 파일이다. 누가 언제 만들었는지는 변경 기록으로 알 수 없다.</li></ul>'+shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, .vscode, 회의록, 도구, 결과, 자료가 보이고 아래 터미널에 자료_준비.py의 출력(변경 기록 10건)이 보이게.')+'<div class="if"><div><b>python을 찾을 수 없다고 나오면</b><code>python</code> 대신 <code>py</code>나 <code>python3</code>으로 바꿔 실행한다.</div><div><b>「자료/ 가 이미 있다」고 나오면</b>이미 만들어진 것이다. 그대로 두고 넘어간다. 처음부터 다시 만들려면 <code>자료</code> 폴더를 지우고 다시 실행한다.</div></div>')
+do(3,'editor','VS Code · 편집기','서버 둘을 시작한다','<p><code>.vscode/mcp.json</code>을 연다. 서버가 둘 적혀 있다. 실습 2에서 연결해 본 것과 같은 서버이고, 프로그램은 <code>서버</code> 폴더에 들어 있다. <code>filesystem</code>은 <code>회의록</code>과 <code>자료</code> 두 폴더의 파일을 읽는 도구를 내준다. <code>--read-only</code>로 띄우므로 쓰는 도구는 목록에 없다. <code>git</code>은 <code>자료</code> 저장소의 변경 기록을 보는 도구를 내준다.</p><p>두 서버 모두 읽기만 한다. 그래서 결과 파일은 서버의 도구가 아니라 Copilot의 파일 편집으로 <code>결과</code> 폴더에 저장된다. 읽어 오는 길과 쓰는 길이 갈려 있는 것이다.</p><p>파일 안의 서버 이름 위에 뜨는 작은 글씨로 두 서버를 각각 시작한다. 둘 다 실행 중으로 바뀌고 도구의 수(5개와 4개)가 보이면 된다. <code>git</code> 서버의 줄 끝에 적힌 <code>${workspaceFolder}/자료</code>가 이 서버가 맡는 저장소의 자리다. 5단계에서 이 낱말을 일부러 틀리게 고쳐 본다.</p>'+shot('.vscode/mcp.json을 연 편집기 화면. 두 서버 이름 위의 시작 · 실행 중 표시와 도구 수가 보이게. git 서버의 저장소 경로 줄에 빨간 테두리를 얹는다.')+'<div class="if"><div><b>서버가 시작되지 않으면</b>표시 옆의 오류 보기를 눌러 출력의 마지막 줄을 읽는다. <code>자료</code> 폴더가 아직 없으면 두 서버 모두 뜨지 않는다. 앞의 명령을 먼저 실행한다.</div></div>')
+do(4,'editor','VS Code · 편집기','규칙 파일에서 세 곳을 읽는다','<p><code>.github/copilot-instructions.md</code>를 연다. 오늘 눈여겨볼 곳은 셋이다.</p><ul class="ask"><li><b>「하면 안 되는 것」 3번</b>회의록과 자료는 <code>filesystem</code> 서버로 읽고, 변경 기록은 <code>git</code> 서버로 확인한다. 결과 파일은 서버의 도구가 아니라 파일 편집으로 저장한다.</li><li><b>「하면 안 되는 것」 4번</b>도구가 실패하면 다른 길로 돌아가지 않고 <code>미완료</code>로 적는다. 5 · 6단계에서 이 줄이 일하는 것을 본다.</li><li><b>「정해져 있지 않은 것」 다섯 줄</b>규칙이 일부러 비워 둔 자리다. 2단계에서 내가 채운다.</li></ul>')
+nxt(1,'1. 만들기 전에, 도구부터 읽게 한다'))

pages.append(hero('1단계','만들기 전에,<br>도구부터 읽게 한다','실습 3에서는 회의록을 먼저 읽게 했다. 오늘은 읽을 것이 하나 더 있다. 연결된 서버에 <b>어떤 도구가 있고 도구마다 무엇을 넘겨야 하는지</b>다. 도구를 모르는 채로 절차를 짜게 하면, 있지도 않은 도구를 부르는 계획이나 서버가 주지 않는 값을 받는다고 여기는 계획이 나온다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','부를 수 있는 도구와 자료의 변경 기록이 채팅에 정리되어 있다'),('아직 없어야 하는 것','새 파일')])
+mapbox('chat','이 단계에서 쓰는 곳','<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 입력 칸 아래의 방식이 <b>에이전트</b>, 모델이 <b>GPT-6 Luna</b>인지 보고, 다르면 그 글자를 눌러 바꾼다.</p>')
+do(1,'chat','Copilot 채팅 · 입력 칸','아래 요청을 복사해 그대로 보낸다','<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 도구를 불러도 되는지 묻는 물음이 뜨면 서버와 도구의 이름을 읽고 허용한다. 두 서버의 도구는 모두 읽는 도구다.</p>'+copy(P1,rich=P1rich)+parts(('무엇을 읽는가','규칙과 스킬, 그리고 두 서버의 도구 목록. 넘길 값과, 파일을 바꾸는 도구가 있는지를 말하게 해서 목록을 제대로 읽었는지를 본다.'),('도구를 한 번씩 써 보게 한다','파일 목록과 변경 기록의 건수는 내가 준비 단계에서 이미 본 값이다. 답이 맞는지를 바로 가릴 수 있다.'),('하지 말 것','읽는 도구만 부르고 멈추게 한다.')))
+do(2,'chat','Copilot 채팅 · 답','돌아온 답에서 네 가지를 찾는다','<p>문장은 사람마다 다르게 나온다. 아래 네 가지가 내 답에도 있는지만 본다.</p>'+shot('위 요청에 대한 Copilot의 답. 두 서버의 도구와 넘길 값을 정리한 부분, 파일을 바꾸는 도구가 없다고 말한 부분, 변경 기록의 건수, 올라가지 않은 파일을 말한 부분이 보이게(길면 두 장).')+'<div class="find"><div><i>①</i><p style="margin:0"><b>도구의 수와 파일을 바꾸는 도구</b><span><code>filesystem</code> 5개, <code>git</code> 4개이고 파일을 바꾸는 도구는 없다고 했는가. 그러면 결과 파일은 무엇으로 저장하는가. 규칙 3번의 마지막 문장이다.</span></p></div><div><i>②</i><p style="margin:0"><b>변경 기록의 건수</b><span>준비 단계의 터미널에서 본 '+str(NC)+'건과 같은가.</span></p></div><div><i>③</i><p style="margin:0"><b>올라가지 않은 파일</b><span><code>교육</code> 폴더의 파일 하나를 찾았는가. 어느 서버의 어느 도구로 알아냈다고 적었는가.</span></p></div><div><i>④</i><p style="margin:0"><b>나에게 되묻는 것</b><span>올라가지 않은 파일을 변경으로 볼지, 언제부터의 변경을 볼지 같은 물음이 답의 끝에 있는가. 다음 단계에서 내가 답한다.</span></p></div></div><div class="note"><b>도구 목록은 누가 알려 주었는가</b>내가 도구의 이름을 적어 준 적은 없다. 채팅이 서버에 연결하면서 목록을 물어 받아 온 것이다. 그래서 서버가 바뀌면 같은 요청의 답도 바뀐다.</div><div class="if"><div><b>서버의 도구가 없다고 하면</b><code>.vscode/mcp.json</code>에서 두 서버가 실행 중인지 다시 본다. 꺼져 있으면 시작하고 같은 요청을 다시 보낸다.</div><div><b>파일이 생겨 버렸다면</b>요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.</div></div>')
+nxt(2,'2. 빈자리를 내가 정하고, 계획부터 받는다',0))

pages.append(hero('2단계','빈자리를 내가 정하고,<br>계획부터 받는다','여러 도구를 잇는 일에는 도구 하나를 쓸 때는 없던 결정이 생긴다. 회의 날짜와 변경 날짜를 어떻게 견줄지, 작업과 자료 파일을 무엇으로 짝지을지, 도구가 실패하면 어디까지 만들지. 규칙 파일은 이 다섯 가지를 비워 두었다. <b>잇는 자리의 결정은 요청하는 사람이 한다.</b>',[('걸리는 시간','약 6분'),('이 단계가 끝나면','도구를 부르는 차례가 적힌 계획이 채팅에 있다'),('아직 없어야 하는 것','새 파일')])
+do(1,'chat','이 화면의 표 → Copilot 채팅','다섯 빈자리마다 어느 쪽으로 정할지 고른다','<p>가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>'+choices+'<div class="note"><b>처음이라면 그대로 보낸다</b>완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다.</div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (1단계와 같은 대화)','고른 답을 보내고, 계획부터 달라고 한다','<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'+copy(P2,pre=True,rich=richpre(P2,'abc'))+parts(('무엇을 잇는가','첫 문단. 읽기, 작업 뽑기, 변경 확인, 저장을 어느 서버와 어느 스킬이 맡는지를 한 문장에 적었다. 이 절차를 담을 스킬의 이름도 여기서 정한다.'),('빈자리 다섯 가지','번호를 붙여 한 줄에 결정 하나씩. 3번처럼 까닭을 함께 적어 두면 요청에 없는 세부를 그 까닭에 맞게 정한다.'),('계획 먼저','마지막 문단. 무엇을 계획에 넣을지도 정했다: 도구를 부르는 차례와 스킬에 적을 것.')))
+do(3,'chat','Copilot 채팅 · 답','돌아온 계획에서 네 가지를 찾는다','<p>Copilot은 파일을 만들지 않고 계획을 내놓는다.</p>'+shot('2단계 요청에 대한 Copilot의 계획. 「도구를 부르는 차례」와 되묻는 항목이 보이게. 변경 기록을 어떻게 나눠 묻는지 적은 줄과, 다시 물어 온 항목에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>도구를 부르는 차례</b><span>회의록 읽기, 자료 목록 읽기, 변경 기록 보기, 저장의 차례로 서버와 도구의 이름이 적혀 있는가. 저장은 서버의 도구가 아니라 파일 편집이라고 적었는가.</span></p></div><div><i>②</i><p style="margin:0"><b>변경 기록을 어떻게 나눠 묻는가</b><span>완성 폴더를 만든 실행에서는 <code>git_log</code>를 한 번에 부르지 않고 짝이 되는 자료 파일마다 따로 부르겠다고 했다. 한 번이 실패해도 그 파일과 짝인 작업만 「미완료」가 되기 때문이라고 까닭을 적었다. 내 계획은 어느 쪽인가.</span></p></div><div><i>③</i><p style="margin:0"><b>도구의 성질을 스스로 알아낸 곳</b><span>예를 들어 「<code>git_log</code>는 건수를 넘기지 않으면 10건만 돌아온다」 같은 문장이다. 지금 변경 기록이 '+str(NC)+'건이어서 드러나지 않았을 뿐, 한 건만 더 있었다면 가장 오래된 변경이 말없이 빠진다.</span></p></div><div><i>④</i><p style="margin:0"><b>다시 물어 온 것</b><span>다섯 가지를 정해 주었는데도 빈자리가 더 나온다. 예: 한 변경이 짝 자료를 둘 바꿨을 때 어떻게 적을지, 짝 자료가 둘인데 한쪽 확인만 실패하면 어떻게 할지, 회의록이나 자료 목록을 읽지 못하면 어디까지 만들지.</span></p></div></div><div class="note"><b>실패의 범위를 미리 묻게 되는 까닭</b>도구를 하나만 쓸 때는 실패하면 그 일이 안 된 것이다. 여럿을 이으면 어느 도구가 실패했느냐에 따라 못 쓰게 되는 항목이 달라진다. 계획에서 이것을 정해 두지 않으면 실패한 날에 AI가 그 자리에서 정한다.</div><div class="if"><div><b>계획 없이 파일부터 만들었다면</b>요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.</div><div><b>도구의 이름이 계획에 없다면</b>「단계마다 어느 서버의 어느 도구를 부르는지 이름을 적어 줘」라고 한 줄 더 보낸다.</div></div>')
+nxt(3,'3. 잇는 차례를 스킬 파일 하나에 적는다',1))

pages.append(hero('3단계','잇는 차례를<br>스킬 파일 하나에 적는다','계획이 채팅에만 있으면 다음 회의록에서는 같은 말을 다시 해야 한다. 그래서 차례와 결정을 <code>work-items</code>라는 스킬 파일에 적어 둔다. 실습 3의 <code>meeting-actions</code>는 고치지 않는다. 새 스킬은 그 스킬을 불러 쓰고, 그 뒤에 잇는 일만 정한다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','.github/skills/work-items/SKILL.md 한 파일이 있다'),('아직 없어야 하는 것','결과 파일')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','계획에 답하고, 범위를 정해 준다','<p>되물은 것에 하나하나 답해도 되지만, 오늘은 Copilot이 권한 쪽을 받고 어떻게 정했는지를 스킬에 적게 한다. 받고 싶지 않은 제안이 있으면 보내기 전에 「다만 ○번은 이렇게 해 줘」를 한 줄 더한다.</p>'+copy(P3,pre=True,rich=richpre(P3,'ab'))+parts(('받을 것과 뺄 것','첫 문단. 권한 쪽을 받되, 정한 내용을 스킬에 남기게 했다. 그래야 다음 할 일에서 내가 읽고 확인할 수 있다. 요청하지 않은 일은 뺀다.'),('범위','둘째 문단. 파일 하나에서 멈추게 한다. 만들 것과 만들지 않을 것을 둘 다 적었다.')))
+do(2,'chat','Copilot 채팅','파일을 만들어도 되는지 물으면, 경로를 읽고 허용한다','<p>경로가 <code>.github/skills/work-items/SKILL.md</code>인지 읽고 허용한다. <code>meeting-actions</code> 폴더의 파일을 고치려 한다면 허용하지 않는다. 규칙이 고치지 않는다고 정한 파일이다.</p>'+shot('Copilot이 work-items의 SKILL.md를 만들면서 허용을 묻거나 변경을 보여 주는 화면. 파일 경로와 「유지/허용」 버튼이 보이게.'))
+do(3,'editor','VS Code · 편집기','만들어진 <code>SKILL.md</code>에서 다섯 곳을 찾는다','<p>탐색기에서 <code>.github/skills/work-items/SKILL.md</code>를 연다. 다음 단계부터 일어나는 일은 모두 여기 적힌 대로다.</p><table class="res"><thead><tr><th style="width:190px">찾을 것</th><th>무엇을 보는가</th></tr></thead><tbody><tr><td><b>절차</b></td><td>번호가 붙은 단계마다 서버와 도구의 이름이 적혀 있는가. 작업을 뽑는 단계는 <code>meeting-actions</code>를 따른다고만 적고 그 내용을 베껴 오지 않았는가</td></tr><tr><td><b>보는 기간</b></td><td>내가 정한 1번(회의가 열린 날부터)이 그대로 적혀 있는가</td></tr><tr><td><b>자료 짝짓기</b></td><td>내가 정한 2번. 표에서 찾을 수 없으면 짐작하지 않는다는 문장이 있는가</td></tr><tr><td><b>도구가 실패하면</b></td><td>어느 호출이 실패하면 어느 항목이 「미완료」가 되는지가 표나 목록으로 적혀 있는가. 5단계에서 이 절이 실제로 쓰인다</td></tr><tr><td><b>결과 파일</b></td><td>파일 이름이 규칙대로 <code>_업무항목</code>인가. 작업 한 건에 <code>자료</code>, <code>변경확인</code>, <code>변경기록</code> 세 칸이 더해졌는가</td></tr></tbody></table><div class="note"><b>스킬과 서버가 맡은 일</b>이 파일에는 도구의 이름과 부르는 차례만 적혀 있다. 변경 기록을 실제로 읽어 오는 일은 이 파일 밖의 <code>git</code> 서버가 한다. 그래서 스킬이 아무리 잘 쓰여 있어도 서버가 연결되어 있지 않으면 그 단계는 실행되지 않는다.</div><div class="if"><div><b>내가 정한 것과 다르게 적혀 있다면</b>지금 고친다. 「보는 기간이 내가 말한 것과 달라. 회의가 열린 날의 변경도 넣으라고 했어. 그 절만 고쳐 줘.」처럼 어디가 어떻게 다른지를 말한다.</div><div><b>결과 파일까지 생겼다면</b>요청의 둘째 문단이 빠진 것이다. 생긴 결과 파일을 지운다.</div></div>')
+nxt(4,'4. 한 요청으로 잇고, 두 원문과 맞춘다',2))

pages.append(hero('4단계','한 요청으로 잇고,<br>두 원문과 맞춘다','이제 한 줄로 시킨다. 지금까지의 대화에는 회의록과 변경 기록을 살펴본 내용이 들어 있으므로 <b>새 대화</b>에서 돌린다. 맞춰 볼 원문은 둘이다. 작업의 근거는 회의록에, 변경기록은 자료 저장소의 변경 기록에 있다.',[('걸리는 시간','약 9분'),('이 단계가 끝나면','결과 폴더에 회의록_1의 업무 항목 파일 두 개가 있다'),('맞춰 볼 것','근거 ↔ 회의록, 변경기록 ↔ 저장소의 변경 기록')])
+do(1,'chat','Copilot 채팅 · 새 대화','새 대화를 열고 한 줄로 시킨다','<p>채팅 위쪽의 「새 채팅」(+) 단추로 새 대화를 연다. 요청에는 어느 스킬로 어느 파일을 처리할지만 남는다. 어느 서버의 어느 도구를 어떤 차례로 부를지는 스킬에 적혀 있다.</p>'+copy(P4)+'<p>도구를 부를 때마다 허용을 묻는 물음이 뜰 수 있다. 서버 이름과 도구 이름을 읽고 허용한다. 두 서버의 도구는 모두 읽는 도구다. 파일을 만들어도 되는지는 맨 끝에 묻는데, 경로가 <code>결과</code> 폴더인지 읽고 허용한다.</p>'+shot('새 대화에서 요청을 보낸 뒤, 채팅에 도구 호출이 차례로 쌓인 화면. filesystem 서버의 읽기, git 서버의 git_log 여러 번과 git_status, 마지막의 파일 만들기가 보이게. 허용을 묻는 물음이 떠 있으면 함께 찍는다.')+'<p>2분쯤 걸린다. 그동안 채팅에 쌓이는 도구 호출을 눈으로 따라간다. 완성 폴더의 결과를 만든 실행에서는 두 서버의 도구가 '+str(len(mcp4))+'번 불렸다.</p>'+tooltable+'<div class="note"><b>실패했다가 다시 불러 성공한 호출</b>위 실행에서 회의록을 읽는 첫 호출은 실패했다. 경로를 <code>회의록/회의록_1.txt</code>로 넘겼는데, 이 서버는 상대경로를 첫째 허용 폴더(<code>회의록</code>)를 기준으로 풀기 때문이다. 오류 문장을 읽고 경로를 바로잡아 같은 도구를 다시 불러 읽었다. 같은 도구로 다시 불러 성공했으면 확인한 것이므로 「미완료」가 아니다. 다른 길로 돌아간 것도 아니다.</div>')
+do(2,'editor','VS Code · 편집기 (좌우로 나란히)','결과를 회의록과 맞춘다','<p><code>결과/회의록_1_업무항목.md</code>를 열고 <code>회의록/회의록_1.txt</code>를 오른쪽에 나란히 둔다. 표의 앞 네 칸은 실습 3의 작업 목록과 같은 방법으로 뽑힌 것이다. <b>근거</b> 칸의 문장 두세 개를 골라 원문에서 찾는다.</p><p>파일 맨 위의 한 줄이 집계다. 완성 폴더의 결과는 작업 '+str(N1)+'건이고 아래와 같이 갈린다.</p>'+words+shot('결과 md 파일과 회의록 원문을 좌우로 나란히 연 VS Code 화면. 결과 파일 맨 위의 집계 줄이 보이게.'))
+do(3,'editor','VS Code · 터미널과 편집기','변경기록을 저장소의 변경 기록과 맞춘다','<p>변경기록 칸은 회의록에 없는 내용이므로 회의록으로는 맞출 수 없다. 터미널에서 저장소의 변경 기록을 직접 뽑아 견준다. 규칙이 터미널을 막은 것은 AI의 일이고, 내가 확인하려고 쓰는 것은 막지 않는다.</p>'+copyto('git -C 자료 log --since=2026-10-06 --date=short --format="%n%ad  %an  %s" --name-only','터미널에서 실행할 명령','붙여넣는 곳 → VS Code 아래쪽 터미널',pre=False)+'<p>회의가 열린 10월 6일부터의 변경 '+str(NS)+'건이 날짜, 사람, 내용, 바뀐 파일의 차례로 나온다. 아래는 완성 폴더의 결과에서 다섯 줄을 뽑은 것이다. 노랗게 칠한 칸을 터미널의 출력과 견준다.</p>'+table+'<div class="find"><div><i>①</i><p style="margin:0"><b>날짜, 사람, 내용이 글자 그대로인가</b><span>변경기록의 문장이 터미널에 나온 문장과 같아야 한다. 다듬어 썼거나 터미널에 없는 변경이 있으면 지어낸 것이다.</span></p></div><div><i>②</i><p style="margin:0"><b>회의 전의 변경이 섞이지 않았는가</b><span>9월의 변경 세 건은 어느 줄에도 없어야 한다. 내가 정한 1번이다.</span></p></div><div><i>③</i><p style="margin:0"><b>「(담당자 아님)」</b><span>정기 점검표는 한서윤이 맡았는데 바꾼 사람은 문태오다. 완성 폴더의 결과에서는 이 표시가 붙은 작업이 '+str(len(other))+'건이다. 「변경 있음」이라고 해서 담당자가 그 일을 끝냈다는 뜻이 아니라는 것을 이 줄들이 보여 준다.</span></p></div><div><i>④</i><p style="margin:0"><b>「변경 없음」과 「자료 없음」</b><span>예비품 두 건은 짝이 되는 목록 파일이 있고 변경 기록을 확인했는데 바뀐 것이 없다. 교육 자료는 짝이 되는 파일이 자료 목록에 없다. 둘은 다른 사실이다.</span></p></div></div><div class="if"><div><b>스킬을 찾지 못한다고 하면</b>요청의 앞에 「.github/skills/work-items/SKILL.md 의 지침대로」를 적어 다시 보낸다.</div><div><b>터미널의 한글이 깨져 보이면</b>준비 단계에서 본 출력과 날짜, 사람, 내용만 견준다. 어느 파일이 바뀌었는지는 완성 폴더의 결과와 견준다.</div></div>')
+nxt(5,'5. 서버 하나를 일부러 끊어 본다',3))

pages.append(hero('5단계','서버 하나를<br>일부러 끊어 본다','지금까지는 도구가 거의 다 응답했다. 실제로는 서버가 뜨지 않거나, 설정의 경로가 틀렸거나, 권한이 없어서 호출이 줄줄이 실패하는 날이 온다. 그때 결과 파일에 무엇이 남는지는 실패시켜 보아야 안다. 가장 흔한 실수를 일부러 한다. <b>설정 파일의 경로를 한 낱말 틀리게 적는다.</b>',[('걸리는 시간','약 6분'),('이 단계가 끝나면','회의록_2의 업무 항목에 「미완료」와 오류 문장이 적혀 있다'),('바뀌면 안 되는 것','회의록_1의 결과')])
+do(1,'editor','VS Code · 편집기','<code>mcp.json</code>에서 저장소 경로를 틀리게 고친다','<p><code>.vscode/mcp.json</code>을 연다. <code>git</code> 서버의 줄 끝에서 <code>자료</code>를 <code>회의록</code>으로 고치고 저장한다(Ctrl+S). 그 폴더는 있지만 저장소가 아니다.</p><div class="vs"><div class="good"><b>고치기 전</b><q>"--repository", "${workspaceFolder}/자료"</q></div><div class="bad"><b>고친 뒤</b><q>"--repository", "${workspaceFolder}/회의록"</q></div></div><p>서버 이름 위의 표시에서 <code>git</code> 서버를 다시 시작한다. 서버는 그대로 뜨고 도구도 4개로 보인다. 폴더가 있기 때문이다. 설정이 틀렸다는 것은 도구를 불러 보아야 드러난다.</p>'+shot('mcp.json에서 git 서버의 저장소 경로를 회의록으로 고친 화면. 고친 낱말에 빨간 테두리를 얹고, 두 서버가 모두 실행 중으로 보이게.'))
+do(2,'chat','Copilot 채팅 · 새 대화','새 대화에서 둘째 회의록을 같은 한 줄로 시킨다','<p>「새 채팅」(+)으로 새 대화를 열고 보낸다. 4단계의 요청과 파일 이름만 다르다. 보내기 전에 짐작해 본다. 파일이 만들어질까, 만들어진다면 몇 건이 채워질까.</p>'+copy(P5)+shot('위 요청에 대한 Copilot의 답. git 서버의 호출이 실패했다고 밝힌 부분과 돌아온 오류 문장, 「미완료」가 몇 건인지 말한 부분에 테두리를 얹는다.'))
+do(3,'editor','VS Code · 편집기','결과 파일에서 실패가 어떻게 적혔는지 본다','<p><code>결과/회의록_2_업무항목.md</code>를 연다. 완성 폴더를 만든 실행에서는 작업 '+str(N2)+'건 가운데 자료 없음 '+str(F2['자료 없음'])+'건, 미완료 '+str(F2['미완료'])+'건이었고, 집계 줄 아래에 이렇게 적혔다.</p>'+term('도구 실패:\n\n'+'\n'.join(f'- {x["도구"]}'+(f' ({x["대상"]})' if x["대상"] else '')+f' — "{x["오류"]}"' for x in ERR))+'<div class="find"><div><i>①</i><p style="margin:0"><b>어느 항목이 「미완료」인가</b><span>짝이 되는 자료가 있는 작업만이다. 변경 기록을 보아야 채울 수 있는 칸이기 때문이다. 그 항목의 <code>자료</code> 칸은 채워져 있고 <code>변경기록</code>만 비어 있다.</span></p></div><div><i>②</i><p style="margin:0"><b>「자료 없음」은 그대로 채워졌는가</b><span>짝 자료가 없는 작업은 <code>git</code> 서버 없이도 가릴 수 있다. 내가 정한 5번(멈추지 않고 나머지는 끝까지)대로다.</span></p></div><div><i>③</i><p style="margin:0"><b>「변경 없음」이 한 건도 없는가</b><span>확인하지 못한 것을 「변경 없음」으로 적으면, 읽는 사람은 확인했는데 바뀐 것이 없다고 받아들인다. 값이 없는 것과 조회에 실패한 것은 다른 사실이다.</span></p></div><div><i>④</i><p style="margin:0"><b>오류 문장이 그대로 적혔는가</b><span>서버가 돌려준 문장이 줄이거나 풀어 쓰지 않은 채로 있어야 한다. 이 문장은 무엇을 고쳐야 하는지를 말해 준다. 채팅의 도구 호출에 터미널의 <code>git</code> 명령이 없는지도 본다. 규칙 4번이다.</span></p></div></div><div class="if"><div><b>「미완료」 없이 다 채워졌다면</b><code>git</code> 서버가 고치기 전의 설정으로 돌고 있는 것이다. <code>mcp.json</code>을 저장했는지, 서버를 다시 시작했는지 본다.</div><div><b>파일을 만들지 않고 멈췄다면</b>스킬의 「도구가 실패하면」 절에 내가 정한 5번이 적혀 있는지 본다. 없으면 그 문장을 넣어 달라고 하고 다시 보낸다.</div></div>')
+nxt(6,'6. 끊긴 채로, 규칙을 건드려 본다',4))

pages.append(hero('6단계','끊긴 채로,<br>규칙을 건드려 본다','「미완료」가 여럿 적힌 파일을 들고 보고하러 가기는 곤란하다. 이럴 때 사람은 두 가지를 떠올린다. 그냥 「변경 없음」으로 채워 달라고 하거나, 서버가 안 되니 다른 방법으로 대신 확인해 달라고 하거나. 둘 다 그럴듯하고, 둘 다 규칙이 막아 둔 일이다. <b>보내기 전에, 들어줄지 멈출지 먼저 짐작해 둔다.</b>',[('걸리는 시간','약 4분'),('이 단계가 끝나면','Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'),('바뀌면 안 되는 것','회의록_2의 결과 파일')])
+do(1,'chat','Copilot 채팅 · 입력 칸 (5단계와 같은 대화)','「미완료」를 「변경 없음」으로 바꿔 달라고 해 본다','<p>서버는 고치지 않은 채로 보낸다.</p>'+copyto(P6a,'Copilot에게 보낼 요청 (규칙에 어긋난다)','붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸',pre=False)+shot('위 요청에 Copilot이 결과 파일을 바꾸지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 길을 제안하는 부분에 테두리를 얹는다.')+'<div class="find"><div><i>①</i><p style="margin:0"><b>파일이 그대로인가</b><span><code>결과/회의록_2_업무항목.md</code>의 집계 줄이 5단계에서 본 수와 같은지 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>어느 규칙을 들었는가</b><span>답에 규칙의 번호나 문장이 적혀 있다.</span></p></div><div><i>③</i><p style="margin:0"><b>규칙 안에서 할 수 있는 길</b><span>서버를 다시 연결한 뒤 다시 실행하자는 제안이 있는가. 지금 파일 그대로 보고하되 실패한 까닭을 함께 말하라는 제안이 있는가.</span></p></div></div>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','터미널로 대신 확인해 달라고 해 본다','<p>이번에는 값을 지어내라는 것이 아니라 다른 도구로 진짜 값을 가져오라는 요청이다. 더 그럴듯하다.</p>'+copyto(P6b,'Copilot에게 보낼 요청 (규칙에 어긋난다)','붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸',pre=False)+'<p>답이 오면 채팅에 터미널 명령이 실행된 흔적이 없는지, 결과 파일이 그대로인지 본다.</p>')
+do(3,'editor','VS Code · 편집기','규칙 파일에서 그 줄을 찾는다','<p><code>.github/copilot-instructions.md</code>를 연다.</p><ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 4번의 마지막 문장이다. 실패를 무엇으로 바꾸어 적지 않는다고 했는가. 「정해져 있는 것」에서 <code>변경 없음</code>의 뜻이 어떻게 적혀 있는지도 함께 읽는다.</li><li><b>둘째 요청</b>같은 4번의 앞 문장이다. 「이번 한 번만」이라는 말은 몇 번 규칙이 막는가.</li></ul><div class="note"><b>둘째 요청은 왜 막아 두었는가</b>터미널로 같은 값을 가져올 수 있는데도 막은 것은, 결과 파일에 적힌 값이 어느 길로 온 것인지가 한 가지여야 하기 때문이다. 어떤 날은 서버로, 어떤 날은 터미널로 채워진 파일은 나중에 값이 이상할 때 어디를 의심해야 할지 알 수 없다. 고칠 곳은 우회로가 아니라 끊긴 서버다.</div><div class="if"><div><b>멈추지 않고 바꿔 버렸다면</b>다음 단계에서 다시 채워지므로 파일은 그대로 둔다. 규칙 파일을 다시 읽고 방금 한 일이 규칙 4번에 맞는지 말해 달라고 하고, 이 일이 있었다는 것을 강사에게 알린다.</div><div><b>「직접 터미널에서 확인하시는 것은 괜찮다」고 한다면</b>맞는 말이다. 4단계에서 내가 한 일이 그것이다. 다만 내가 본 값을 결과 파일에 대신 적어 달라는 것은 다시 규칙 3번에 걸린다.</div></div>')
+nxt(7,'7. 고치고, 미완료만 다시 실행한다',5))

pages.append(hero('7단계','고치고,<br>미완료만 다시 실행한다','실패를 「미완료」로 남겨 둔 까닭은 나중에 채우기 위해서다. 원인을 고친 뒤 다시 실행할 때는 처음부터 전부가 아니라 <b>확인하지 못한 곳만</b> 다시 하게 한다. 이미 맞춰 본 줄이 다시 쓰이면서 달라지는 일을 막는다.',[('걸리는 시간','약 4분'),('이 단계가 끝나면','회의록_2의 결과에 「미완료」가 0건이다'),('바뀌면 안 되는 것','「자료 없음」인 항목의 문장')])
+do(1,'editor','VS Code · 편집기','경로를 되돌리고 서버를 다시 시작한다','<p><code>.vscode/mcp.json</code>의 <code>git</code> 서버 줄에서 <code>회의록</code>을 <code>자료</code>로 되돌리고 저장한다. <code>git</code> 서버를 다시 시작한다. 5단계에서 본 오류 문장이 고칠 곳을 이미 말해 주었다.</p>')
+do(2,'chat','Copilot 채팅 · 입력 칸 (같은 대화)','확인하지 못한 곳만 채우게 한다','<p>무엇을 고쳤는지, 어디를 다시 할지, 어디를 건드리지 말지를 말한다.</p>'+copy(P7)+shot('저장소 경로를 자료로 되돌린 mcp.json과, 「미완료」였던 항목을 채웠다고 답한 Copilot 채팅이 함께 보이는 화면.'))
+do(3,'editor','VS Code · 편집기','채워진 곳과 그대로인 곳을 본다','<p><code>결과/회의록_2_업무항목.md</code>를 다시 연다. 완성 폴더의 결과는 변경 있음 '+str(A2['변경 있음'])+'건, 변경 없음 '+str(A2['변경 없음'])+'건, 자료 없음 '+str(A2['자료 없음'])+'건, 미완료 0건이다.</p>'+cmptable+'<div class="find"><div><i>①</i><p style="margin:0"><b>「미완료」였던 줄만 바뀌었는가</b><span>「자료 없음」인 줄의 할일과 근거가 5단계에서 본 문장 그대로인지 본다.</span></p></div><div><i>②</i><p style="margin:0"><b>실패의 기록이 사라졌는가</b><span>집계 줄 아래의 「도구 호출 실패」가 지워졌거나 비어 있어야 한다. 실패가 풀렸는데 기록이 남아 있으면 읽는 사람이 헷갈린다.</span></p></div><div><i>③</i><p style="margin:0"><b>6단계의 짐작은 맞았는가</b><span>「어차피 바뀐 게 없을 거야」라며 「변경 없음」으로 채우려던 항목들이다. 완성 폴더의 결과에서는 확인해 보니 모두 「변경 있음」이었다. 그때 채웠다면 틀린 보고가 되었다.</span></p></div><div><i>④</i><p style="margin:0"><b>회의 전의 변경이 섞이지 않았는가</b><span>쿨러 핀 점검 기록에는 10월 7일의 변경도 있지만 회의(10월 8일) 전이어서 들어가지 않아야 한다.</span></p></div></div><div class="if"><div><b>여전히 서버가 없다고 하면</b>서버가 실행 중인지 다시 보고, 새 대화를 열어 5단계의 요청을 다시 보낸다. 파일을 통째로 다시 만들게 된다.</div></div>')
+nxt(8,'8. 아쉬운 곳을 찾아 되돌려 준다',6))

pages.append(hero('8단계','아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다','결과가 규칙대로 나왔더라도 실제로 쓰려고 보면 아쉬운 곳이 보인다. 업무 항목 표는 일곱 칸이나 되고, 회의 뒤에 가장 먼저 챙겨야 할 일(자료가 아직 그대로인 일)은 표 안에 흩어져 있다. 틀린 것은 아니지만 쓸모가 모자란다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',[('걸리는 시간','약 6분'),('이 단계가 끝나면','work-items 스킬의 한 곳이 내 요청대로 바뀌어 있다')])
+'<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>표가 보기 불편해. 다시 해 줘.</q>무엇이 불편한지 AI는 모른다. 표의 모양을 제 생각대로 바꾸거나, 변경 확인까지 처음부터 다시 한다.</div><div class="good"><b>구체적으로</b><q>자료가 아직 바뀌지 않은 작업이 한눈에 보이지 않아. 변경 없음인 작업을 따로 모으는 절을 work-items 스킬에 더하고, 두 결과 파일에 그 절만 더해 줘. 작업 표와 meeting-actions 스킬은 건드리지 마.</q>한 번에 끝나고, 도구를 다시 부르지 않는다.</div></div><div class="four"><div><b>무엇이</b>자료가 그대로인 일이 흩어져 있다</div><div><b>왜</b>누구에게 진행을 물어야 하는지 찾기 어렵다</div><div><b>어디를</b>결과 파일이 아니라 스킬</div><div><b>어디까지</b>작업 표와 앞 스킬은 그대로, 변경 확인은 다시 하지 않는다</div></div></section>'
+do(1,'editor','VS Code · 편집기','내 결과에서 아쉬운 곳 하나를 고른다','<p>두 결과 파일을 다시 본다. 아래에서 골라도 되고 스스로 찾아도 된다.</p><ul class="ask"><li><b>자료가 아직 바뀌지 않은 일이 흩어져 있다</b>「변경 없음」인 작업을 담당자, 완료시점과 함께 따로 모으면 누구에게 물어야 하는지가 바로 보인다.</li><li><b>같은 파일을 짝으로 가진 두 작업</b>절차서를 게시하는 일과 전원 차단 순서를 검토하는 일은 같은 파일이 짝이다. 그래서 서로의 변경이 「(담당자 아님)」으로 양쪽에 다 적힌다. 변경의 내용이 그 작업과 맞는 것만 적게 할 것인가.</li><li><b>기한을 넘겨 바뀐 자료</b>완료시점이 날짜로 적힌 작업에서, 변경의 날짜가 그보다 늦으면 표시하게 할 것인가.</li></ul>')
+do(2,'chat','이 화면의 글 칸 → Copilot 채팅 (같은 대화)','네 가지를 넣어 되돌려 준다','<p>무엇이, 왜, 어디를, 어디까지. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 변경 확인을 다시 할 필요가 없는 요청이면 그렇게 적는다. 적지 않으면 도구를 처음부터 다시 부른다.</p>'+write('w8','무엇이 문제인지, 왜 문제인지, work-items 스킬의 어디를 고칠지, 건드리지 말 곳을 적는다.')+'<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>'+copy(P8,'Copilot에게 보낼 요청',pre=True)+'</details><p style="margin-top:18px">고친 뒤에는 <code>work-items/SKILL.md</code>에 새 절이 생겼는지, <code>meeting-actions/SKILL.md</code>는 그대로인지, 두 결과 파일의 작업 표가 바뀌지 않았는지를 본다. 완성 폴더의 회의록_1에는 아래 '+str(len(still))+'건이 모였고, 회의록_2에는 '+(str(len(still2))+'건이 모였다' if still2 else '해당하는 작업이 없어 「없음」으로 적혔다')+'. 건수가 집계 줄의 「변경 없음」과 같아야 한다.</p>'+stilltable+shot('되돌려 준 뒤 Copilot이 work-items의 SKILL.md에서 바뀐 부분을 보여 주는 화면(새로 생긴 절이 초록색으로 표시된 화면).')+'<div class="if"><div><b>도구를 처음부터 다시 불렀다면</b>「어디까지」에 변경 확인을 다시 하지 않는다는 말이 빠진 것이다. 결과는 같아야 하지만 시간이 더 걸린다.</div><div><b>meeting-actions 스킬을 고치려 한다면</b>허용하지 않는다. 규칙이 고치지 않는다고 정한 파일이다. 새 절은 work-items에만 적으라고 다시 말한다.</div></div>')
+'<section class="sect"><h2>시간이 남으면</h2><p>새 대화를 열고 4단계의 요청을 그대로 다시 보낸다. 회의록_1의 결과가 처음부터 다시 만들어지는데, 8단계에서 더한 절이 이번에는 따로 말하지 않아도 나오는지 본다. 작업의 건수나 짝지은 자료가 앞의 결과와 달라진 곳이 있으면, 스킬의 어느 문장이 느슨해서 그런지 찾는다.</p><p style="margin:0">이번에는 <code>filesystem</code> 서버를 멈추고 같은 요청을 보내 본다. 회의록을 읽지 못하면 스킬의 「도구가 실패하면」 절은 어떻게 하라고 적어 두었는가. 실제로 그렇게 되는지 보고, 서버를 다시 시작한다.</p></section>'
+nxt(None,None,7))

names=['준비','1. 도구부터 읽게 한다','2. 정하고 계획 받기','3. 차례를 스킬로','4. 한 요청으로 잇기','5. 서버 끊어 보기','6. 규칙 건드려 보기','7. 고치고 다시 실행','8. 되돌려 주기']
MIN=[5,4,6,6,9,6,4,4,6]; assert sum(MIN)==50 and len(MIN)==len(names)==len(pages)
for i,p in enumerate(pages): assert f'약 {MIN[i]}분' in p,i
assert sum(p.count('<textarea') for p in pages)==1
for w in ('가상','시뮬레이션','바이브'): assert not any(w in p for p in pages),w
bar='<div class="bar"><div class="bar-in"><b>회의록 → 변경 확인 → 업무 항목</b><div class="track">'+''.join(f'<i data-go="{i}" title="{n}"></i>' for i,n in enumerate(names))+'</div><span id="pos"></span></div></div>'
js='''<script>
const KEY='hyd-off-06-4-';const names='''+json.dumps(names,ensure_ascii=False)+''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 '+(names.length-1)+'단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. 상자 아래에 적힌 곳에 붙여넣으세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc=f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 여러 도구를 조합해 업무 결과 완성하기</title><style>{css}</style></head><body>{bar}<main class="page">'+''.join(f'<article class="step">{p}</article>' for p in pages)+f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
open(R+'가이드.html','w',encoding='utf-8').write(doc)
open(R+'찍어_주실_화면.md','w',encoding='utf-8').write('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n'+'\n'.join(f'{i+1}. {d}' for i,d in enumerate(shots))+'\n')
print(len(doc),len(shots))
