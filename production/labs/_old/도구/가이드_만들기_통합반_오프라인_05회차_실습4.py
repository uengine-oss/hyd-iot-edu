"""통합반 오프라인 05회차 실습 4 「품질 문제를 후속 업무로 연결하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '05회차_실습4_품질_대응_카드'
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
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:16px 0 8px;font-size:14.5px;line-height:1.7}
.card b{display:inline-block;min-width:108px;color:var(--sub);font-weight:700}
.card mark{background:#fff1a8;padding:0 3px;border-radius:3px}
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
def copy(text, head='Copilot에게 보낼 요청', pre=False, rich=None, foot='붙여넣는 곳 → Copilot 채팅 맨 아래 입력 칸'):
    cid[0] += 1; i = f'c{cid[0]}'
    body = rich if rich else e(text)
    return f'<div class="copy"><div class="copy-top"><span>{head}</span><button data-copy="{i}">복사</button></div><div class="copy-text{" pre" if pre else ""}" id="{i}">{body}</div><div class="copy-foot">{foot}</div></div>'
shots = []
def shot(desc):
    shots.append(desc); n = len(shots)
    return f'<div class="shot"><div><b>사진 {n} — 찍어 주실 화면</b><span>{desc}</span></div></div>'
def write(i, ph): return f'<textarea id="{i}" data-draft="{i}" placeholder="{e(ph)}"></textarea><div class="wfoot"><button data-copy="{i}">내가 쓴 글 복사</button><span>붙여넣는 곳 → Copilot 채팅 입력 칸 · 쓴 글은 이 브라우저에 저장된다</span></div>'
def do(n, k, label, title, body): return f'<section class="do" data-n="{n}">{where(k,label)}<h2>{title}</h2>{body}</section>'
def hero(no, title, lead, facts): return f'<section class="hero"><div class="no">{no}</div><h1>{title}</h1><p>{lead}</p><div class="facts">' + ''.join(f'<div><small>{a}</small>{b}</div>' for a, b in facts) + '</div></section>'
def mapbox(k, title, text): return f'<section class="map"><div>{vs(k)}</div><div><h2>{title}</h2>{text}</div></section>'
def nxt(i, label, prev=None):
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 도구 넷을 붙인 에이전트(도구.py · 에이전트.py)와 접수 열세 건의 품질 대응 카드 두 파일. 원인이 확인되지 않은 접수는 조사 요청으로 넘어간다</b></div></div>'
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
P1 = P('1_prompt.txt')
P1rich = ('<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 기준 폴더의 두 파일, 접수 폴더의 두 파일, 자료 폴더의 두 파일, 에이전트_정의.json 을 읽어 줘.</span> '
          '<span class="p-b">접수 한 건이 품질 대응 카드가 되기까지 분류 기준의 어느 부분을 어떤 차례로 대는지 한 줄씩 적고, 접수 Q01과 Q03을 손으로 카드로 만들어 표로 적어 줘. 만들다가 기준과 이 폴더의 규칙만으로는 정할 수 없는 것이 나오면 정하지 말고, 내가 무엇을 정해 줘야 하는지 물어 줘.</span> '
          '<span class="p-c">아직 파일은 만들지 마.</span>')
assert re.sub(r'<[^>]+>', '', P1rich) == P1
P2, P3, P4, P5a, P5b, P5c, P6, P7, P8 = (P(f'{n}_prompt.txt') for n in ('2', '3', '4', '5a', '5b', '5c', '6', '7', '8'))
Q13 = (R / '기록' / '7_Q13_붙일_글.txt').read_text(encoding='utf-8').rstrip()

# ── 시작 폴더의 자료에서 읽는 수
K = json.loads((R / '시작' / '기준' / '분류_기준.json').read_text(encoding='utf-8'))
IN = json.loads((R / '시작' / '접수' / '불량_접수.json').read_text(encoding='utf-8'))
LG = json.loads((R / '시작' / '자료' / '원인_분석_대장.json').read_text(encoding='utf-8'))
n_type, n_info, n_in, n_lg = len(K['유형']), len(K['확인_정보']), len(IN), len(LG)
assert (n_type, n_info, n_in, n_lg) == (6, 7, 12, 5)
src = {q['번호']: q for q in IN}
led = {no: l for l in LG for no in l['접수']}
assert Q13.startswith(',') and json.loads('[' + Q13.lstrip(',') + ']')[0]['번호'] == 'Q13'

# ── 실제로 실행한 결과 파일에서 옮기는 줄
J = lambda p: {x['번호']: x for x in json.loads((R / p).read_text(encoding='utf-8'))}
r3, r4, r6, r7, fin = J('기록/3_결과_Q01.json'), J('기록/4_결과.json'), J('기록/6_결과.json'), J('기록/7_결과.json'), J('완성/결과/품질_대응_카드.json')
assert list(r3) == ['Q01'] and len(r4) == len(r6) == 12 and len(r7) == len(fin) == 13 and r7 == fin
core = lambda c: {k: v for k, v in c.items() if k != '호출_기록'}
for k in r6:
    assert core(r6[k]) == core(fin[k]) and r4[k]['품질_유형'] == r6[k]['품질_유형'] and r4[k]['추가_확인_항목'] == r6[k]['추가_확인_항목']
GA = {'시정_조치': 's', '조사_요청': 'u', '재분류': 'x'}
ga = lambda c: f'<span class="st {GA[c["갈래"]]}">{c["갈래"]}</span> {e(c["담당_부서"])}'
typ = lambda c: (f'<b>{c["품질_유형"]["코드"]}</b> {e(c["품질_유형"]["이름"])}' if c['품질_유형']['코드'] != '미분류' else '<b>미분류</b>') + (f'<br><small>{" · ".join(e(x) for x in c["품질_유형"]["단서"])}</small>' if c['품질_유형']['단서'] else '')
need = lambda c: ' · '.join(e(x['항목']) for x in c['추가_확인_항목']) or '<small>없음</small>'
why = lambda c: f'{c["원인_상태"]}<br><small>{c["원인_근거"]["출처"]}</small>'
def card(c, marks=()):
    m = lambda k, s: f'<mark>{s}</mark>' if k in marks else s
    g = c['원인_근거']
    rows = [('품질 유형', f'{c["품질_유형"]["코드"]} / {e(c["품질_유형"]["이름"])} / 단서: {", ".join(e(x) for x in c["품질_유형"]["단서"]) or "없음"}'),
            ('추가 확인 항목', ', '.join(f'{e(x["항목"])} ({e(x["까닭"])})' for x in c['추가_확인_항목']) or '없음'),
            ('원인 상태', m('원인', c['원인_상태'])), ('원인 근거', m('원인', f'{e(g["내용"]) or "없음"} (출처: {g["출처"]})')),
            ('갈래', m('갈래', c['갈래'])), ('담당 부서', m('갈래', e(c['담당_부서']))), ('대응 초안', m('초안', e(c['대응_초안']))),
            ('호출 기록', ' → '.join(f'{h["도구"]}' for h in c['호출_기록']))]
    return f'<div class="card"><div style="font-weight:800;font-size:16px;margin-bottom:6px">{c["번호"]}</div>' + ''.join(f'<div><b>{a}</b>{b}</div>' for a, b in rows) + '</div>'

SEE = {'Q01': '단서가 두 유형에 걸렸다. 치수 불량에 둘, 구매품 불량에 하나(「입고 검사」). 많이 걸린 쪽으로 갔다',
       'Q02': '<b>확정.</b> 검사자가 적은 「방청유 탓으로 보임」이 원인 근거다',
       'Q03': '<b>확정.</b> 로트 번호도 모르는데 생산팀으로 넘어간다. 원인 근거는 고객이 한 말이다',
       'Q04': '<b>확정.</b> 검사자가 「그 때문으로 보임」이라고 적었다',
       'Q05': '<b>확정.</b> 본문에 「원인으로 확인되어」라고 적혀 있다',
       'Q06': '추가 확인 항목이 없다. 본문에서 사진을 말한 문장을 읽어 둔다(8단계)',
       'Q07': '쿨러 코어의 입고 검사다. 단서 셋이 구매품 불량에 걸렸고, 들어온 날짜가 빠졌다',
       'Q08': '사진이 빠졌다. 불량 수량으로 무엇이 잡혔는지는 카드에 보이지 않는다',
       'Q09': 'Q04와 같은 로트다. 본문에 원인을 말한 문장이 없어 갈래가 Q04와 다르다',
       'Q10': '<b>미분류.</b> 걸린 단서가 없다. 불량이 아니라 일정을 묻는 전화다',
       'Q11': '수량과 측정값이 빠졌다. 「도장」이 외관 불량에도 걸렸지만 넷 대 하나다',
       'Q12': '<b>미분류.</b> 외관 불량과 누유 · 기밀 불량의 단서가 하나씩 똑같이 걸렸다'}
allt = ('<table class="res"><thead><tr><th style="width:112px">접수 · 보낸 곳</th><th style="width:140px">품질 유형 · 걸린 단서</th><th style="width:100px">추가 확인 항목</th><th style="width:118px">원인 상태 · 갈래</th><th>볼 것</th></tr></thead><tbody>'
        + ''.join(f'<tr><td><b>{k}</b><br><small>{e(src[k]["보낸_곳"])}</small></td><td>{typ(c)}</td><td>{need(c)}</td><td>{c["원인_상태"]} <small>({c["원인_근거"]["출처"]})</small><br><span class="st {GA[c["갈래"]]}">{c["갈래"]}</span><br><small>{e(c["담당_부서"])}</small></td><td>{SEE[k]}</td></tr>' for k, c in r4.items())
        + '</tbody></table>')
cnt4 = {g: sum(1 for c in r4.values() if c['갈래'] == g) for g in GA}
cnt6 = {g: sum(1 for c in r6.values() if c['갈래'] == g) for g in GA}
cntf = {g: sum(1 for c in fin.values() if c['갈래'] == g) for g in GA}
assert cnt4 == {'시정_조치': 4, '조사_요청': 6, '재분류': 2} and cnt6 == {'시정_조치': 3, '조사_요청': 7, '재분류': 2} and cntf == {'시정_조치': 3, '조사_요청': 8, '재분류': 2}
sure4 = [k for k, c in r4.items() if c['원인_상태'] == '확정']
assert sure4 == ['Q02', 'Q03', 'Q04', 'Q05'] and all(r4[k]['원인_근거']['출처'] == '접수자_의견' for k in sure4)
WHO = {'Q02': '출하 검사를 한 사람', 'Q03': '고객 (전화를 받아 적은 글)', 'Q04': '출하 검사를 한 사람', 'Q05': '공정 검사를 한 사람'}
def ledcell(k):
    l = led.get(k)
    return '<small>대장에 없다</small>' if not l else f'<b>{l["분석_번호"]} · {l["상태"]}</b><br>{e(l["원인"])}'
sure = ('<table class="res"><thead><tr><th style="width:54px">접수</th><th>초안에 「확인된 원인」으로 나간 글</th><th style="width:130px">그 말을 한 사람</th><th>원인 분석 대장에는</th></tr></thead><tbody>'
        + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td><mark>{e(r4[k]["원인_근거"]["내용"])}</mark></td><td>{WHO[k]}</td><td>{ledcell(k)}</td></tr>' for k in sure4) + '</tbody></table>')
chg = [k for k in r4 if (r4[k]['원인_상태'], r4[k]['갈래'], r4[k]['원인_근거']) != (r6[k]['원인_상태'], r6[k]['갈래'], r6[k]['원인_근거'])]
assert chg == ['Q01', 'Q02', 'Q03', 'Q04', 'Q05', 'Q07', 'Q09']
def ar(a, b): return a if a == b else f'{a} → <mark>{b}</mark>'
gtxt = lambda c: f'{e(c["원인_근거"]["내용"]) or "(빈 글)"} <small>({c["원인_근거"]["출처"]})</small>'
difft = ('<table class="res"><thead><tr><th style="width:54px">접수</th><th style="width:120px">원인 상태</th><th style="width:190px">갈래 · 담당</th><th>원인 근거 (출처)</th></tr></thead><tbody>'
         + ''.join(f'<tr><td class="nw"><b>{k}</b></td><td>{ar(r4[k]["원인_상태"], r6[k]["원인_상태"])}</td><td>{ar(r4[k]["갈래"] + " · " + r4[k]["담당_부서"], r6[k]["갈래"] + " · " + r6[k]["담당_부서"])}</td><td>{gtxt(r4[k])}<br>→ {gtxt(r6[k])}</td></tr>' for k in chg) + '</tbody></table>')
assert (r4['Q03']['갈래'], r6['Q03']['갈래'], r6['Q03']['원인_근거']['출처']) == ('시정_조치', '조사_요청', '접수자_의견')
assert (r6['Q01']['원인_상태'], r6['Q04']['원인_근거']['출처'], r6['Q09']['원인_근거']['출처']) == ('확정', '분석_진행', '분석_진행')
q13 = fin['Q13']
assert (q13['품질_유형']['코드'], [x['항목'] for x in q13['추가_확인_항목']], q13['원인_상태'], q13['원인_근거']['출처'], q13['갈래']) == ('QT-01', ['발견한 곳'], '미확정', '접수자_의견', '조사_요청')
md = (R / '완성' / '결과' / '품질_대응_카드.md').read_text(encoding='utf-8')
q06 = [l for l in md.split('## Q06')[1].split('- 원인 상태')[0].splitlines() if l.strip() and not l.startswith('- 품질 유형')]
assert len(q06) == 6 and '사진은 아직 찍지 못했고' in q06[4]
q06html = '\n'.join(('<b>' + e(l) + '</b>') if '사진은 아직' in l else e(l) for l in q06)

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>유형을 고르는 법</b></td><td><mark>1번 줄</mark> 걸린 단서의 가짓수가 가장 많은 유형으로 정한다. 같은 단서가 여러 번 나와도 한 번으로 센다</td><td>「단서가 걸린 유형 가운데 기준에 먼저 적힌 것」으로 바꾼다. 간단하지만 Q07(쿨러 코어의 입고 검사)이 「찍힘」 하나 때문에 외관 불량이 된다. 구매품 불량의 단서 셋은 쓰이지 않는다</td></tr>
<tr><td><b>똑같이 걸리거나 하나도 걸리지 않을 때</b></td><td><mark>2번 줄</mark> 미분류로 두고, 추가 확인 항목에 「품질 유형」 한 건을 넣는다. 까닭에는 똑같이 걸린 유형의 이름을 적는다</td><td>「똑같이 걸리면 기준에 먼저 적힌 유형으로 정한다」로 바꾼다. 미분류가 줄지만 Q12는 외관 불량이 되고, 누유가 날 수 있다는 말은 카드에서 사라진다</td></tr>
<tr><td><b>무엇을 보고 원인을 확정으로 할지</b></td><td><mark>3번 줄</mark> 본문에 원인을 말하는 표현이 든 문장이 있으면 확정, 없으면 미확정으로 한다. 원인 분석 대장을 읽는 도구는 아직 허용 목록에 없다</td><td>「도구를 붙일 때까지 모두 미확정으로 둔다」로 바꾼다. 더 조심스러운 선택이다. 다만 오늘은 가운데 칸으로 가 본다. 이 결정이 어떤 카드를 내는지 4단계에서 내 눈으로 보고, 6단계에서 다시 정한다</td></tr>
<tr><td><b>접수자가 말한 원인을 어디에 둘지</b></td><td><mark>4번 줄</mark> 그 문장을 원인 근거의 내용에 그대로 옮기고, 출처를 「접수자_의견」으로 적는다</td><td>「본문의 원인 문장은 카드에 옮기지 않는다」로 바꾼다. 카드는 짧아지지만, 조사하는 사람이 접수자의 말을 보려면 원문을 다시 찾아야 한다</td></tr>
<tr><td><b>초안에 추가 확인 항목을 어떻게 적을지</b></td><td><mark>5번 줄</mark> 틀에 값을 채운 글 뒤에 「확인 부탁드립니다: 」와 항목의 이름을 붙인다</td><td>「초안에는 넣지 않고 카드의 칸에만 둔다」로 바꾼다. 초안은 틀 그대로가 되지만, 보낸 곳은 무엇을 더 알려 주어야 하는지를 초안에서 알 수 없다</td></tr>
</tbody></table>'''

path = '''<div class="path"><svg viewBox="0 0 760 214" role="img" aria-label="접수 한 건이 카드가 되는 길">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#8a94a3"/></marker></defs>
<g font-size="13" font-weight="700" fill="#14181f" text-anchor="middle">
<rect x="6" y="62" width="104" height="52" rx="10" fill="#eef1f5"/><text x="58" y="84">접수 본문</text><text x="58" y="102" font-size="10.5" font-weight="400" fill="#5b6573">사람이 쓴 글</text>
<rect x="146" y="62" width="124" height="52" rx="10" fill="#eef1f5"/><text x="208" y="84">품질 유형</text><text x="208" y="102" font-size="10.5" font-weight="400" fill="#5b6573">단서를 대어 정한다</text>
<rect x="306" y="62" width="130" height="52" rx="10" fill="#eef1f5"/><text x="371" y="84">추가 확인 항목</text><text x="371" y="102" font-size="10.5" font-weight="400" fill="#5b6573">본문에서 못 찾은 정보</text>
<rect x="472" y="62" width="124" height="52" rx="10" fill="#eaf0ff" stroke="#2f5bea" stroke-width="2"/><text x="534" y="84">원인이</text><text x="534" y="102">확인되었는가</text>
<rect x="632" y="14" width="122" height="52" rx="10" fill="#e8f6ee"/><text x="693" y="36">시정 조치</text><text x="693" y="54" font-size="10.5" font-weight="400" fill="#5b6573">유형의 조치 부서</text>
<rect x="632" y="110" width="122" height="52" rx="10" fill="#fff1a8"/><text x="693" y="132">조사 요청</text><text x="693" y="150" font-size="10.5" font-weight="400" fill="#5b6573">품질팀</text>
<rect x="146" y="156" width="124" height="46" rx="10" fill="#fdecec"/><text x="208" y="176">재분류</text><text x="208" y="193" font-size="10.5" font-weight="400" fill="#5b6573">품질팀</text></g>
<g stroke="#8a94a3" stroke-width="2" fill="none" marker-end="url(#ar)"><path d="M110 88H144"/><path d="M270 88H304"/><path d="M436 88H470"/><path d="M596 78H612V40H630"/><path d="M596 98H612V136H630"/><path d="M208 114V154"/></g>
<g font-size="11.5" fill="#5b6573" text-anchor="middle"><text x="612" y="30">확정</text><text x="612" y="158">미확정</text><text x="252" y="140">정하지 못하면</text></g></svg></div>'''

def grow(n):
    T = [('분류_기준 · 유형_기준 · 대응_틀', '분류 기준을 읽는다. 유형과 단서, 확인 정보, 담당과 틀을 안다', '처음부터 목록에 있다'), ('원인_분석', '원인 분석 대장을 읽는다. 조사가 끝났는지, 확인된 원인이 무엇인지 안다', '6단계에서 내가 목록에 더한다')]
    return '<div class="grow" style="grid-template-columns:repeat(2,1fr)">' + ''.join(f'<div class="{"on" if i < n else ""}"><b>{a}</b>{b}<br><small style="color:var(--sub)">{c}</small></div>' for i, (a, b, c) in enumerate(T)) + '</div>'

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 5회차 · 실습 4 · 50분</small>불량 접수를 품질 대응 카드로<br>바꾸는 에이전트를 만든다',
 '앞의 두 실습에서는 설비 이상의 원인을 가리는 에이전트를 만들고 다듬었다. 이번에는 같은 뼈대를 전혀 다른 일에 쓴다. 고객의 메일, 전화 메모, 검사 기록으로 들어온 불량 접수를 받아, 분류 기준에 대어 품질 유형을 정하고, 모자란 정보와 넘길 부서를 적고, 대응 초안을 쓰는 프로그램이다. 먼저 만들어 돌려 본 다음, 원인이 확인되지 않은 접수를 확인된 것처럼 내보내지 않도록 고친다. 무엇을 보고 원인이 「확정」이라고 할지는 <b>내가 정한다.</b>',
 [('끝나면 남는 것', '도구.py · 에이전트.py, 접수 열세 건의 품질 대응 카드 두 파일'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '온라인 5일차의 에이전트 단원을 들었다'), ('준비에 쓰는 시간', '약 4분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>오늘의 에이전트도 모델을 부르지 않는 작은 파이썬 프로그램이다. 실행 고리와 도구, 허용 목록, 호출 기록이라는 뼈대는 앞 실습과 같고, 읽는 자료와 내는 것이 다르다.</p>'
  f'<div class="pipe"><div><b>분류 기준</b>품질 유형 {n_type}가지, 확인 정보 {n_info}가지, 갈래 셋과 대응 틀<small>기준/분류_기준.json</small></div><span>+</span><div><b>불량 접수</b>나흘 동안 들어온 접수 {n_in}건. 사람이 쓴 글이다<small>접수/불량_접수.json</small></div><span>→</span><div class="out"><b>품질 대응 카드</b>품질 유형, 추가 확인 항목, 담당 부서, 대응 초안<small>결과/품질_대응_카드.json · .md</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 카드가 접수 원문과 맞는지 판단하는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>기준과 접수를 읽고 두 건을 손으로 카드로 만들어 보게 한다</div><div><em>2</em><b>정해 준다</b>규칙이 비워 둔 다섯 가지를 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>바로 만들지 않고 어떻게 할지 먼저 듣는다</div><div><em>4</em><b>작게 만든다</b>한 건을 돌리고, 열두 건을 접수 원문과 맞춘다</div><div><em>5</em><b>되돌려 준다</b>아쉬운 곳은 무엇이 왜 문제인지 말해 고친다</div></div>'
  '<p style="margin:18px 0 0">1~4단계와 8단계가 이 다섯 걸음이다. 그 사이에 세 가지를 더 해 본다. 규칙에 어긋나는 요청을 일부러 보내 보고(5단계), 원인을 대장에서 확인하도록 고치고(6단계), 새로 들어온 접수 한 건을 넣어 다시 돌린다(7단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 '<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙</i>\n├─ <span>기준/</span>\n│  ├─ 분류_기준.json           <i>← 유형, 확인 정보, 갈래와 틀</i>\n│  └─ 읽는_법.md               <i>← 기준을 읽는 법</i>\n├─ <span>접수/</span>\n│  ├─ 불량_접수.json           <i>← 접수 12건</i>\n│  └─ 접수_설명.md             <i>← 칸의 뜻</i>\n├─ <span>자료/</span>\n│  ├─ 원인_분석_대장.json      <i>← 품질팀의 조사 기록 5건</i>\n│  └─ 대장_설명.md             <i>← 칸의 뜻</i>\n├─ 에이전트_정의.json          <i>← 이름, 목표, 부를 수 있는 도구</i>\n└─ <span>결과/</span>                      <i>← 지금은 비어 있다</i></div>'
 '<div><p><b>규칙 파일</b>은 Copilot이 이 폴더에서 일할 때 지키는 약속이다. 「하면 안 되는 것」과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 5단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」의 다섯 줄은 일부러 비워 둔 자리이고, 2단계에서 내가 채운다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 기준, 접수, 자료, 결과 다섯 폴더와 에이전트_정의.json이 펼쳐져 보이게.'))
+ do(2, 'editor', 'VS Code · 편집기', '접수 한 건이 카드가 되는 길을 눈으로 따라간다',
 '<p><code>기준/읽는_법.md</code>를 열어 「유형 한 건」과 「갈래와 대응 틀」을 읽는다. 접수 한 건은 아래 길을 따라 카드가 된다. 길의 끝이 셋으로 갈린다. 원인이 확인된 접수는 그 유형의 조치 부서로, 확인되지 않은 접수는 품질팀의 조사로, 유형조차 정하지 못한 접수는 품질팀의 재분류로 간다.</p>' + path
 + '<p>기준에 적혀 있지 않은 것이 하나 있다. 파란 테두리의 물음, <b>무엇을 보고 원인이 확인되었다고 할 것인가</b>다. <code>읽는_법.md</code>의 맨 아래 「알아 둘 것」에서 그 줄을 찾아 둔다.</p>')
+ do(3, 'editor', 'VS Code · 편집기와 종이', '접수 한 건을 손으로 먼저 카드로 만들어 본다',
 '<p><code>접수/불량_접수.json</code>의 맨 위 <b>Q01</b>은 고객이 보낸 메일이다. 본문을 읽고 종이에 네 가지를 적는다. 어느 유형의 단서가 걸리는가. 그 유형의 확인 정보 가운데 본문에 없는 것이 있는가. 본문에 원인을 말한 문장이 있는가. 어느 갈래로 보내겠는가. 다 적었으면 <code>자료/원인_분석_대장.json</code>을 열어 Q01을 다루는 조사가 있는지도 찾아본다. 뒤에서 에이전트의 카드가 맞는지를 가리는 사람은 나다. 손으로 만든 카드가 하나는 있어야 가릴 수 있다.</p>'
 '<p>끝으로 <code>에이전트_정의.json</code>을 연다. <code>도구</code> 목록에 <code>분류_기준</code>, <code>유형_기준</code>, <code>대응_틀</code> 셋이 있다. 이 목록이 에이전트가 부를 수 있는 도구의 <b>허용 목록</b>이다. 셋 모두 분류 기준을 읽는 도구다. <code>자료/원인_분석_대장.json</code>을 읽는 도구는 아직 없다.</p>'
 + note('적다가 막히는 곳이 있다', 'Q01에는 치수 불량의 단서와 구매품 불량의 단서가 함께 걸린다. 어느 쪽으로 정하는가. 본문에는 원인이 적혀 있지 않은데, 대장을 열어 보면 이 접수의 조사는 끝나 있다. 에이전트는 그것을 알 수 있는가. 2단계에서 내가 정한다.'))
+ nxt(1, '1. 만들기 전에, 읽고 손으로 만들어 보게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>읽고 손으로 만들어 보게 한다',
 '첫마디가 「불량 접수를 분류하는 에이전트를 만들어 줘」이면 AI는 파일을 읽자마자 코드를 쓴다. 단서가 두 유형에 걸리면 어느 쪽으로 할지, 고객이 말한 원인을 어떻게 다룰지를 AI가 알아서 정하고, 그 결정은 코드 속에 묻힌다. 그래서 첫 요청은 <b>읽고, 차례를 말하고, 두 건만 손으로 카드로 만들어 보고, 정할 수 없는 것은 물어보라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 기준을 어떻게 읽었는지와, 나에게 묻는 것이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다. 앞 실습의 대화가 남아 있으면 새 대화를 연다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 기준 · 접수 · 자료의 여섯 파일, 에이전트의 정의. 읽을 대상을 내가 정해 준다.'), ('어떤 모양으로 답하는가', '차례를 한 줄씩 적게 하고, 두 건을 표로 만들어 보게 했다. Q01은 내 종이와 바로 견줄 수 있고, Q03은 정보가 여럿 빠진 전화 메모다.'), ('하지 말 것', '정할 수 없으면 정하지 말 것, 파일을 만들지 말 것. 이 두 문장이 없으면 AI가 빈자리를 스스로 채운다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>답이 오는 데 1~2분 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 차례를 한 줄씩 적은 부분, Q01과 Q03을 손으로 만든 표, 답의 끝에서 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('차례에서 정하지 못한 자리를 짚었는가', '단서를 대는 일과 확인 정보를 찾는 일은 기준에 적힌 대로 할 수 있다. 걸린 유형 가운데 무엇을 고를지와, 무엇을 보고 원인을 확정으로 할지는 「정해져 있지 않다」고 적었는가.'),
        ('Q01이 내 종이와 같은가', 'Q01에는 치수 불량의 단서 둘(공차, 내경)과 구매품 불량의 단서 하나(입고 검사)가 걸린다. 유형을 스스로 골라 적지 않고 비워 두었는가. Q03의 추가 확인 항목이 로트 번호, 불량 수량, 사진 셋인가. 로트 번호를 짐작해 적었다면 규칙을 어긴 것이다.'),
        ('정하지 않고 되물은 것', '물음이 몇 가지인지 세어 둔다. 허용 목록에 원인 분석 대장을 읽는 도구가 없어서 에이전트는 Q01의 조사가 끝났다는 것을 볼 수 없다고 짚었는지도 본다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 다섯 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 이 줄이 없었다면 AI는 가장 흔한 방식으로 알아서 정했을 것이고, 무엇이 어떻게 정해졌는지는 코드를 뜯어보아야 알 수 있다.')
 + ifs(('파일이 생겨 버렸다면', '탐색기에 <code>도구.py</code>나 결과 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.'),
       ('내 종이와 다르다면', '「다시 해 줘」라고 하지 않는다. 「Q03의 추가 확인 항목에 발견한 곳이 들어 있는데, 본문에 조립 라인이라고 적혀 있어.」처럼 어디가 어떻게 다른지를 말한다. 내 종이가 틀렸을 수도 있으므로 기준을 다시 본다.')))
+ nxt(2, '2. 비워 둔 것을 내가 정하고, 계획부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '비워 둔 것을 내가 정하고,<br>계획부터 받는다',
 '분류 기준은 유형마다 단서와 확인 정보를 적어 둘 뿐이다. 두 유형의 단서가 함께 걸린 접수를 어디로 보낼지, 고객이 「그쪽 조립 불량 때문」이라고 한 말을 원인으로 받아 적을지는 어디에도 없다. 이것을 정하는 일이 이 실습의 핵심이다. 정답이 하나가 아니므로 <b>요청하는 사람이 정한다.</b>',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '내 결정이 반영된 계획이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '다섯 빈자리마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다.</p>' + choices
 + note('3번 줄은 일부러 가운데 칸으로 간다', '원인 분석 대장을 읽는 도구가 없는 지금, 에이전트가 볼 수 있는 것은 접수 본문뿐이다. 「본문에 원인이 적혀 있으면 확정」은 현장에서 가장 쉽게 내리는 결정이기도 하다. 먼저 그렇게 만들어 카드를 본다. 완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abbc'))
 + parts(('무엇을 만드는가', '첫 문단. 넣는 것과 나오는 것을 말하고, 무엇이 가장 중요한지를 한 문장으로 적었다. 이 문장이 있으면 Copilot이 요청에 없는 세부를 그 목적에 맞게 정한다.'), ('빈자리 다섯 가지와 범위', '번호를 붙여 한 줄에 결정 하나씩 적었다. 그 아래 문단은 도구를 셋부터 시작한다는 범위다.'), ('계획 먼저', '마지막 문단. 규칙 파일에 「계획을 먼저 말해 달라는 요청을 받으면 계획만 말한다」는 줄이 있어, 이 말을 들으면 만들지 않고 멈춘다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 네 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고 계획을 내놓는다. 「이렇게 만들겠다」와 「이것은 더 정해 달라」가 함께 온다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. 도구.py와 에이전트.py에 둘 것, 3번 결정이 어떤 카드를 내는지 미리 알린 부분, 「더 정해 주셔야 하는 것」이 보이게. 아래 네 곳에 테두리를 얹는다.')
 + find(('도구와 실행 고리를 갈랐는가', '도구는 파일을 읽어 돌려주기만 하고, 세고 고르고 견주는 일은 에이전트 쪽에 둔다고 했는가. 유형의 이름이나 단서, 부서를 코드에 적지 않고 실행할 때마다 기준에서 읽는다고 했는가.'),
        ('3번 결정이 무엇을 내는지 미리 알렸는가', '대신 돌린 실행에서는 「본문만 보고 확정하면 네 건이 시정 조치로 간다」며 접수 번호를 들어 알렸다. 내 계획에도 이런 예고가 있는지 본다. 있다면 그 번호를 적어 둔다. 4단계에서 직접 본다.'),
        ('내가 시키지 않았는데 들어온 일', '예를 들어 허용 목록에 없는 도구의 함수를 미리 써 두겠다는 계획이다. 대신 돌린 실행에서는 「규칙이 도구를 넷이라고 정해 두었으니 원인_분석도 함수로는 써 둔다」고 했다. 할지 말지는 내가 정한다.'),
        ('다시 물어 온 것', '다섯 가지를 정해 주어도 빈자리가 더 나온다. 예: 틀의 원인 자리에 무엇을 넣을지, 문장을 어디서 끊을지, 미분류 카드의 초안에도 「확인 부탁드립니다」를 붙일지. Copilot이 권하는 답이 함께 적혀 있는지 본다.'))
 + note('계획부터 받는 까닭', '계획을 받지 않고 바로 만들게 했다면, 이 결정들은 내가 모르는 사이에 내려져 코드에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.')
 + ifs(('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('3번 결정을 다시 생각해 보라고 한다면', '틀린 말이 아니다. 오늘은 「지금은 그대로 만들고, 카드를 본 뒤에 다시 정할게」라고 답한다. 다음 단계의 복사 상자에 이 말이 들어 있다.')))
+ nxt(3, '3. 도구 셋으로 만들어 한 건만 돌린다', 1))

# ───────── 3단계
pages.append(hero('3단계', '도구 셋으로 만들어<br>한 건만 돌린다',
 '이제 만들게 한다. 범위는 두 파일과 접수 한 건의 실행까지다. 열두 건을 한꺼번에 돌리면 어느 카드가 맞고 어느 카드가 틀렸는지를 한눈에 가리기 어렵다. 내 손으로 이미 만들어 본 Q01 한 건으로 먼저 맞춘다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '도구.py, 에이전트.py와 Q01 한 장의 카드가 있다'), ('아직 하지 않는 것', '원인 분석 대장을 읽는 일 (6단계)')])
+ '<section class="sect"><h2>도구는 허용 목록이 정한다</h2><p>에이전트가 부를 수 있는 도구는 <code>에이전트_정의.json</code>의 목록이 정한다. 지금은 왼쪽 칸만 켜져 있다.</p>' + grow(1) + '</section>'
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 범위를 정해 준다',
 '<p>계획에 대한 답은 세 마디면 된다. 받을 것, 미룰 것, 이번에 만들 범위다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'abc'))
 + parts(('받을 것', 'Copilot이 권한 답을 그대로 받는다. 받고 싶지 않은 제안이 있으면 보내기 전에 「다만 ○번은 이렇게 해 줘」를 한 줄 더한다.'), ('미룰 것', '허용 목록에 없는 도구의 함수는 지금 만들지 않게 했다. 3번 결정에 대한 걱정에는 「카드를 본 뒤에 다시 정한다」고 답했다.'), ('범위', '두 파일을 만들어 한 건을 한 번 실행하는 데서 멈추게 한다. 어디까지인지를 적지 않으면 AI는 스스로 고치고 다시 돌리기를 되풀이한다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 무엇을 하려는지 읽고 허용한다',
 '<p>Copilot이 파일을 만들 때와 터미널에서 명령을 실행할 때 허락을 구하는 물음이 뜰 수 있다. 누르기 전에 두 가지를 읽는다. 만드는 파일이 <code>도구.py</code>와 <code>에이전트.py</code>인가. 실행하려는 명령이 <code>python 에이전트.py Q01</code>(또는 <code>python3 …</code>)인가. 다른 파일이나 다른 명령이면 허용하지 않고 왜 필요한지 묻는다.</p>'
 + shot('Copilot이 터미널 명령 실행의 허용을 묻는 화면. 명령 글자(python 에이전트.py Q01)와 「허용/계속」 버튼이 보이게. 파일을 만들 때의 「유지/허용」 물음도 뜬다면 한 장 더.'))
+ do(3, 'editor', 'VS Code · 편집기', 'Q01 카드를 내 종이와 맞춘다',
 '<p><code>결과/품질_대응_카드.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 바꾼다. 아래가 지금 나와야 하는 카드다(대신 돌린 실행의 결과 파일에서 옮겼다).</p>' + card(r3['Q01'], ('원인', '갈래'))
 + find(('유형이 내 종이와 같은가', '치수 불량의 단서 둘이 걸려 QT-01이 되었다. 구매품 불량에 걸린 「입고 검사」는 한 가지뿐이어서 밀렸다. 1번 줄에서 내가 정한 대로다.'),
        ('원인이 미확정인 까닭을 말할 수 있는가', '본문에 원인을 말한 문장이 없다. 그래서 조사 요청으로 품질팀에 간다. 그런데 준비 단계에서 대장을 열어 보았을 때 이 접수의 조사는 끝나 있었다. 에이전트는 그것을 읽을 도구가 없다. 이 카드는 틀린 것이 아니라, 지금 볼 수 있는 것까지만 말한 카드다.'),
        ('호출 기록이 있는가', '카드의 끝에 「호출 기록」이 있다. <code>분류_기준</code>, <code>유형_기준</code>, <code>대응_틀</code>을 한 번씩 불렀다. 무엇을 물었고 무엇을 받았는지가 적혀 있다.'))
 + ifs(('python을 찾을 수 없다고 나오면', '「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다. 프로그램을 다른 언어로 바꾸게 하지 않는다.'),
       ('Q01이 벌써 확정으로 나왔다면', '에이전트가 허용 목록에 없는 길로 대장을 읽은 것이다. 「원인_분석은 허용 목록에 없어. 대장을 직접 읽는 코드를 빼 줘.」라고 말한다.')))
+ nxt(4, '4. 열두 건을 돌려 접수 원문과 맞춘다', 2))

# ───────── 4단계
pages.append(hero('4단계', '열두 건을 돌려<br>접수 원문과 맞춘다',
 '프로그램이 오류 없이 끝났다는 것은 카드가 맞다는 뜻이 아니다. 열두 건의 접수는 서로 다른 경우를 담고 있다. 단서가 두 유형에 걸리는 것, 로트 번호도 수량도 없는 전화 메모, 불량이 아닌 문의, 그리고 본문에 누군가 원인을 적어 둔 것이다. 맞는지 가리는 일은 AI에게 맡기지 않는다. 특히 <b>「확정」이라고 나온 카드에서, 그 원인을 말한 사람이 누구인지</b>를 본다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '2단계의 3번 결정이 어떤 카드를 냈는지 안다'), ('맞춰 볼 것', '카드 ↔ 접수 본문 ↔ 원인 분석 대장')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '열두 건을 모두 돌리게 한다',
 '<p>프로그램은 고치지 않게 하고, 끝난 뒤에 무엇을 세어 알려 줄지를 정해 준다.</p>' + copy(P4, pre=True, rich=richpre(P4, 'abc'))
 + parts(('확인한 것을 알린다', '첫 문단. Q01을 내가 맞춰 보았다는 것, 3단계의 답에서 Copilot이 스스로 정했다고 알린 것을 받는다는 것을 말한다.'), ('무엇을 하고 무엇을 하지 않는가', '둘째 문단. 실행만 하고 고치지 않는다. 오류가 나도 먼저 알리게 했다. 이 말이 없으면 AI는 오류를 만나는 대로 고쳐 가며 끝까지 간다.'), ('무엇을 세어 알려 주는가', '셋째 문단. 갈래마다의 건수와, 확정인 카드의 번호와 근거. 내가 볼 곳을 미리 좁혀 둔다.')))
+ do(2, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '카드와 접수를 나란히 놓고 표를 따라 내려간다',
 f'<p><code>결과/품질_대응_카드.md</code>의 미리 보기를 왼쪽에, <code>접수/불량_접수.json</code>을 오른쪽에 둔다. 아래는 대신 돌린 실행의 결과에서 옮긴 것이고, 2단계의 가운데 칸대로 정했을 때의 값이다. 시정 조치 {cnt4["시정_조치"]}건, 조사 요청 {cnt4["조사_요청"]}건, 재분류 {cnt4["재분류"]}건이다.</p>' + allt
 + shot('결과 md의 미리 보기와 접수 json을 좌우로 나란히 연 VS Code 화면. 결과 쪽은 Q03 카드의 「원인 근거」와 「대응 초안」이, 접수 쪽은 Q03의 본문이 보이게.')
 + find(('유형이 본문과 맞는가', 'Q07은 쿨러 코어의 입고 검사다. 「찍힘」이 외관 불량에도 걸렸지만 구매품 불량의 단서가 셋이다. Q10과 Q12가 미분류인 까닭이 서로 다른 것도 본다. 하나는 걸린 단서가 없고, 하나는 똑같이 걸렸다.'),
        ('빠진 정보가 정말 빠졌는가', 'Q03 본문에서 로트 번호와 수량을 찾아본다. 「세는 중」, 「현품을 봐야 안다」고만 적혀 있다. 카드의 초안 끝에 「확인 부탁드립니다: 로트 번호, 불량 수량, 사진」이 붙어 있는가.'),
        ('같은 로트인데 갈래가 다르다', 'Q04와 Q09는 같은 로트 L-0930-A17의 출하 검사다. 하나는 시정 조치로 생산팀에, 하나는 조사 요청으로 품질팀에 갔다. 두 본문에서 무엇이 달랐는가.')))
+ do(3, 'editor', 'VS Code · 편집기', '「확정」 네 건의 원인을 대장과 맞춘다',
 '<p><code>자료/원인_분석_대장.json</code>을 연다. 에이전트는 아직 이 파일을 읽지 못하지만 나는 읽을 수 있다. 확정으로 나온 네 건의 카드에서 「대응 초안」을 읽고, 대장에서 그 접수 번호를 찾아 견준다.</p>' + sure
 + find(('누가 한 말인가', '네 건 모두 원인 근거의 출처가 「접수자_의견」이다. 검사한 사람이 「~로 보임」이라고 적은 것, 고객이 전화로 한 말이다. 그 말이 초안에서는 「확인된 원인은 다음과 같습니다」 뒤에 붙어 보낸 곳으로 나간다.'),
        ('대장과 맞는 것은 몇 건인가', 'Q05 하나다. Q02는 조사가 끝났고 원인이 접수자의 말과 다르다. Q04는 조사가 아직 진행이다. Q03은 조사가 열리지도 않았다.'),
        ('거꾸로 놓친 것은 없는가', 'Q01은 조사가 끝났는데 미확정으로 나와 품질팀에 다시 조사를 요청한다. 본문만 보는 에이전트는 양쪽으로 틀린다.'))
 + note('이것이 2단계의 3번 줄이 낸 결과다', '프로그램은 내가 정한 대로 정확히 움직였다. 틀린 것은 결정이다. 접수 본문은 누군가 그렇게 본다는 말이 적힌 곳이고, 원인을 확인하는 곳은 품질팀의 조사다. 6단계에서 이 결정을 고친다.')
 + ifs(('카드가 표와 다르다면', '2단계에서 다르게 정한 줄이 있으면 달라지는 것이 맞다. 그렇지 않다면 어느 접수의 어느 칸이 어떻게 다른지를 말해 고치게 한다.'),
       ('유형의 이름이 코드에 적혀 있다면', '<code>에이전트.py</code>에서 찾기(Ctrl+F)로 <code>QT-0</code>, <code>생산팀</code>, <code>때문</code>을 찾는다. 나온다면 「유형과 부서, 표현은 도구가 돌려준 것만 쓰기로 했어. 그 부분을 고쳐 줘.」라고 말한다.')))
+ nxt(5, '5. 규칙을 일부러 건드려 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 실제 일터에서는 급할 때 누구나 「그 로트일 테니까 채워 넣어」, 「그 정도는 네가 알아서 넣어 줘」라고 말하게 된다. 그 말을 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '접수, 에이전트_정의.json')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '접수에 없는 로트 번호를 채워 달라고 해 본다',
 '<p>Q03은 로트 번호가 없다. 같은 고객이 보낸 Q08에는 같은 품목의 로트 번호가 적혀 있다. 그것일 것이라는, 그럴듯한 짐작이다.</p>'
 + copy(P5a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 접수를 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '<code>접수/불량_접수.json</code>에서 Q03의 본문을 찾아, 로트 번호가 들어가 있지 않은지 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고, 규칙 안에서 같은 목적을 이루는 길을 내놓았는가. 내 짐작이 맞는지도 따져 주었는지 본다. 대신 돌린 실행에서는 Q03이 10월 5일의 전화이고 Q08의 로트는 그 뒤에 도착한 것이어서 날짜가 맞지 않는다고 짚었다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '허용 목록을 대신 고쳐 달라고 해 본다',
 '<p>다음 단계에서는 원인 분석 대장을 읽는 도구를 붙인다. 목록을 고치는 일을 Copilot에게 시켜 본다. 한 줄 고치는 일이 번거롭다는 것은 실제로 나올 법한 불만이다.</p>'
 + copy(P5b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>에이전트_정의.json</code>을 열어 도구가 셋 그대로인지 본다. 답에 「목록을 고친 다음 정해 주어야 하는 것」이 함께 왔다면 읽어 둔다. 다음 단계에서 내가 답한다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 두 줄이다. 접수 폴더를 어떻게 다루라고 적혀 있는가. 접수에 없는 로트 번호를 어떻게 하라고 적혀 있는가. 각각 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 한 줄이다. 도구 목록은 누가 고친다고 적혀 있는가. 몇 번인가.</li><li><b>8번 줄</b>「요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 두 답 어디에도 「이번만 예외라고 확인해 주시면 하겠다」는 말이 없었는지 다시 본다. 이 줄이 없으면 AI는 그렇게 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('수업에서 본 두 가지가 여기에 있다', '첫째 요청을 들어주었다면, 틀렸을지 모르는 로트 번호가 접수 원문에 들어가고 생산팀은 그 로트의 내압 시험을 다시 했을 것이다. 카드는 깔끔해 보여서 받아 보는 사람은 차이를 알 수 없다. 둘째 요청은 권한 제한이다. 허용 목록은 에이전트가 무엇을 부를 수 있는지를 사람이 쥐고 있는 장치이고, 채팅에서 한 말로는 넓어지지 않는다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '접수가 바뀌었다면 그 파일을 열어 되돌리기(Ctrl+Z)로 Q03의 본문을 되돌려 저장한다. 되돌려지지 않으면 강사에게 원본 파일을 받는다. 도구 목록이 바뀌었다면 편집기에서 직접 되돌려 저장한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(6, '6. 원인을 대장에서 확인하도록 고친다', 4))

# ───────── 6단계
pages.append(hero('6단계', '원인을 대장에서<br>확인하도록 고친다',
 '4단계에서 본 대로, 접수자의 말이 「확인된 원인」이 되어 나가는 카드가 넷이었다. 에이전트에게 모자란 것은 원인이 확인되었는지를 읽을 길이다. 그 길을 열고, 2단계의 3번 결정을 다시 내린다. 순서가 중요하다. 먼저 <b>내가</b> 허용 목록에 도구의 이름을 적고, 그다음 Copilot에게 그 도구를 만들게 한다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '원인이 확인되지 않은 접수는 모두 조사 요청으로 가 있다'), ('바뀌면 안 되는 것', '유형, 추가 확인 항목, 카드의 칸 이름')])
+ '<section class="sect"><h2>두 번째 칸을 켠다</h2>' + grow(2) + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '허용 목록에 <code>원인_분석</code>을 내 손으로 더한다',
 '<p><code>에이전트_정의.json</code>을 연다. <code>도구</code> 목록의 <code>"대응_틀"</code> 뒤에 쉼표를 붙이고 한 줄을 더해 저장한다(Ctrl+S). 이름은 한 글자도 다르면 안 된다. 규칙 파일이 도구 넷의 이름을 정해 두었다. 방금 Copilot이 하지 않은 일을 내가 한다.</p>'
 '<div class="chg"><div class="tree">고치기 전\n"도구": [\n  "분류_기준",\n  "유형_기준",\n  "대응_틀"\n]</div><div class="tree">고친 뒤\n"도구": [\n  "분류_기준",\n  "유형_기준",\n  "대응_틀"<b>,</b>\n  <b>"원인_분석"</b>\n]</div></div>')
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '다시 정한 것을 말하고, 고쳐서 실행하게 한다',
 '<p><code>자료/대장_설명.md</code>에는 「상태가 종결이면 조사로 확인한 원인, 진행이면 조사하고 있는 가설」이라고 적혀 있다. 이것을 따라 다섯 줄로 다시 정했다.</p>'
 + copy(P6, pre=True, rich=richpre(P6, 'abcc'))
 + parts(('무엇이 왜 문제였는가', '첫 문단. 목록은 내가 고쳤다는 것, 카드에서 무엇을 보았는지, 그래서 무엇을 바꾸려는지를 말했다. 「원인을 확인하는 곳은 품질팀의 조사」라는 한 문장이 뒤의 다섯 줄의 까닭이다.'), ('다시 정한 다섯 가지', '둘째 문단. 1번 줄이 중심이다. 종결일 때만 확정이다. 3번과 4번 줄은 가설과 접수자의 말을 버리지 않고 카드에 남기되 출처로 가른다. 5번 줄은 그것이 초안으로 나가지 않게 한다.'), ('어디까지 고치는가', '셋째 · 넷째 문단. 유형과 추가 확인 항목을 정하는 부분, 카드의 칸은 그대로 두게 했다. 끝난 뒤에는 바뀐 카드만 앞뒤로 견주어 달라고 했다.')))
+ do(3, 'editor', 'VS Code · 편집기', '바뀐 카드를 앞뒤로 견준다',
 f'<p><code>결과/품질_대응_카드.md</code>를 다시 연다. 아래는 4단계의 결과와 이 단계의 결과를 견준 것이다(둘 다 대신 돌린 실행의 결과 파일에서 옮겼다). 시정 조치가 {cnt4["시정_조치"]}건에서 {cnt6["시정_조치"]}건으로, 조사 요청이 {cnt4["조사_요청"]}건에서 {cnt6["조사_요청"]}건으로 바뀌었다.</p>' + difft
 + shot('6단계 요청에 대한 Copilot의 답. 바뀐 카드를 앞뒤로 견준 표와 「제가 정한 것」이 보이게.')
 + find(('단정하던 카드가 물러섰는가', 'Q03과 Q04가 조사 요청으로 바뀌어 품질팀에 간다. 두 카드의 초안에서 「확인된 원인은」이라는 말이 사라졌는가. 접수자의 말과 조사 중인 가설은 원인 근거 칸에 남아 있고, 출처가 그것이 무엇인지를 말해 준다.'),
        ('확인된 것은 확인된 대로 나가는가', 'Q01은 거꾸로 확정이 되어 생산팀으로 간다. Q02는 확정 그대로지만 원인의 글이 접수자의 말에서 조사 결과로 바뀌었다.'),
        ('같은 로트가 같은 갈래로 갔는가', 'Q04와 Q09가 이제 둘 다 조사 요청이고 근거도 같다. 대장의 한 조사가 두 접수를 다루기 때문이다.'),
        ('바뀌면 안 되는 것이 그대로인가', '열두 건의 유형과 추가 확인 항목이 4단계의 표와 같은가. 미분류 두 건의 호출 기록에 <code>원인_분석</code>이 없는가. Copilot이 스스로 정했다고 밝힌 것(분석 번호를 md의 어디에 넣었는지 등)도 읽는다.'))
 + ifs(('「도구.py에 없는 도구」라며 멈췄다면', '목록에는 더했는데 함수가 아직 없는 것이다. 정상이다. 2번의 요청을 보내면 풀린다.'),
       ('오류가 나며 멈췄다면', '쉼표를 빠뜨렸거나 따옴표가 짝이 맞지 않는 것이다. 고친 줄을 위의 「고친 뒤」와 한 글자씩 견준다.')))
+ nxt(7, '7. 새로 들어온 접수를 넣어 다시 돌린다', 5))

# ───────── 7단계
pages.append(hero('7단계', '새로 들어온 접수를 넣어<br>다시 돌린다',
 '접수는 날마다 들어온다. 열두 건에 맞춘 프로그램이 열세 번째 접수에도 통하는지는 넣어 보아야 안다. 이번 접수에는 앞의 열두 건에서 한 번도 걸리지 않은 단서가 들어 있고, 고객이 원인을 짚어 말한 문장도 있다. 돌리기 전에 <b>카드가 어떻게 나올지 먼저 적어 본다.</b> 프로그램은 한 줄도 고치지 않는다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '접수 열세 건의 카드가 있다'), ('바뀌면 안 되는 것', '도구.py, 에이전트.py')])
+ do(1, 'editor', 'VS Code · 편집기', '접수 파일의 맨 끝에 Q13을 내 손으로 붙여넣는다',
 '<p><code>접수/불량_접수.json</code>을 열고 맨 아래로 내려간다(Ctrl+End). 마지막 접수 Q12를 닫는 <code>}</code>의 바로 뒤, 목록을 닫는 <code>]</code>의 앞에 커서를 두고 아래 글을 붙여넣은 다음 저장한다(Ctrl+S). 글은 쉼표로 시작한다. 그 쉼표가 Q12와 Q13을 잇는다.</p>'
 + copy(Q13, '접수 파일에 붙여넣을 글', pre=True, foot='붙여넣는 곳 → 접수/불량_접수.json 의 맨 끝, 마지막 } 와 ] 사이')
 + shot('접수/불량_접수.json의 맨 끝에 Q13을 붙여넣은 편집기 화면. Q12를 닫는 } 뒤의 쉼표, Q13의 여섯 칸, 맨 끝의 ] 가 보이게. 쉼표와 ] 에 테두리를 얹는다.')
 + '<p style="margin-top:18px">규칙의 1번은 Copilot이 접수 폴더를 고치지 못하게 한다. 새 접수를 넣는 일은 접수를 받는 사람, 곧 나의 일이다.</p>')
+ do(2, 'editor', 'VS Code · 편집기와 종이', '카드가 어떻게 나올지 먼저 적는다',
 '<p>Q13의 본문을 읽고 종이에 네 가지를 적는다. <code>기준/분류_기준.json</code>을 옆에 열어 두고 본다.</p>'
 '<ul class="ask"><li><b>유형</b>본문의 어느 낱말이 어느 유형의 단서인가.</li><li><b>추가 확인 항목</b>그 유형의 확인 정보 넷 가운데 본문에서 찾을 수 없는 것이 있는가. 「장착 자리」는 기준이 적어 둔 발견한 곳의 낱말인가.</li><li><b>원인 상태와 출처</b>고객이 원인을 말했다. 대장에 이 접수의 조사가 있는가. 그러면 상태와 출처는 무엇이 되는가.</li><li><b>갈래와 담당</b>어느 부서로 가는가.</li></ul>')
+ do(3, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '고치지 않고 실행만 하게 한다',
 '<p>먼저 Q13만 돌려 카드를 보고, 그다음 전체를 다시 돌려 결과 파일을 열세 건으로 되돌린다.</p>' + copy(P7)
 + '<p style="margin-top:18px">아래는 대신 돌린 실행의 결과다. 내 종이와 견준다.</p>' + card(q13, ('원인', '갈래'))
 + find(('프로그램을 고치지 않았는데 처리되었는가', '「외경」과 「간섭」은 앞의 열두 건에서 한 번도 걸리지 않은 단서다. 에이전트가 유형과 단서를 코드에 적어 두지 않고 실행할 때마다 기준에서 읽기 때문에, 새 접수도 같은 길로 간다.'),
        ('고객의 말이 초안으로 나가지 않았는가', '「가공 프로그램이 바뀐 탓」이라는 문장은 원인 근거에 접수자 의견으로 남았다. 초안은 조사 요청의 틀 그대로이고, 원인은 아직 확인되지 않았다고 말한다. 4단계의 에이전트였다면 이 카드는 어떻게 나왔겠는가.'),
        ('열세 건으로 돌아왔는가', f'결과 md의 맨 아래에 Q13이 있고 맨 위에 Q01이 있는가. 완성 폴더의 결과는 시정 조치 {cntf["시정_조치"]}건, 조사 요청 {cntf["조사_요청"]}건, 재분류 {cntf["재분류"]}건이다.'))
 + ifs(('JSON을 읽지 못한다는 오류가 나면', '붙여넣은 자리가 어긋난 것이다. Q12의 <code>}</code>와 Q13의 <code>{</code> 사이에 쉼표가 하나 있는지, 맨 끝에 <code>]</code>가 하나 남아 있는지 본다. Copilot에게 접수 파일을 고쳐 달라고 하지 않는다.'),
       ('내 종이와 다르다면', '어느 칸이 다른지를 먼저 본다. 발견한 곳이 추가 확인 항목에 나온 것이 뜻밖이라면, 기준의 낱말 목록을 다시 읽는다. 기준에 없는 낱말은 사람이 보기에 뜻이 같아도 찾지 못한다.')))
+ nxt(8, '8. 아쉬운 곳을 찾아 되돌려 준다', 6))

# ───────── 8단계
pages.append(hero('8단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '갈래가 정한 대로 나왔더라도 실제로 쓰려고 보면 아쉬운 곳이 보인다. Q06을 본다. 본문에는 「사진은 아직 찍지 못했고 내일 보내겠습니다」라고 적혀 있다. 그런데 카드의 추가 확인 항목은 비어 있다. 기준이 사진을 「본문에 그 낱말이 있는가」로 찾게 해 두었고, 낱말은 있기 때문이다. 에이전트가 틀린 것은 아니다. 그러나 카드만 보는 사람은 사진을 이미 받은 줄 안다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '에이전트.py의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>Q06 카드가 좀 이상해. 고쳐 줘.</q>무엇이 이상한지 AI는 모른다. 대신 돌린 실행에서는 아무것도 고치지 않고, 이상해 보이는 곳을 짐작해 이것이냐고 되물었다. 한 번 더 주고받아야 한다. 짐작으로 여러 곳을 한꺼번에 고치는 경우도 있다.</div>'
  '<div class="good"><b>구체적으로</b><q>Q06 본문에는 사진을 아직 찍지 못했다고 적혀 있는데 추가 확인 항목에 사진이 없어. 카드만 보는 사람은 사진을 받은 줄 알아. 찾는 방식은 바꾸지 말고, 결과 md에 찾았다고 친 확인 정보와 그 글자가 든 문장을 함께 적어 줘. md를 쓰는 부분만 고치고 json의 칸과 판단하는 부분은 건드리지 마.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>없다고 적힌 사진이 찾은 것으로 쳐졌다</div><div><b>왜</b>카드만 보는 사람이 이미 받은 줄 안다</div><div><b>어디를</b>에이전트.py에서 md를 쓰는 부분</div><div><b>어디까지</b>json의 칸, 유형 · 추가 확인 항목 · 원인 상태를 정하는 부분, 도구.py는 그대로</div></div>'
  + note('찾는 방식을 바꿔 달라고 하지 않은 까닭', '「못, 아직 같은 말이 있으면 없는 것으로 쳐 줘」가 가장 쉬운 말이다. 그러나 어떤 말이 「없다」는 뜻인지의 기준이 분류 기준에 없다. 그 낱말들을 코드에 적게 하면 규칙의 3번(확인 정보를 프로그램 안에 옮겨 적지 않는다)에 어긋나고, 기준이 적은 찾는 법과 프로그램이 하는 일이 달라진다. 근본적인 해결은 분류 기준에서 사진의 낱말을 고치는 것이고, 그것은 기준을 관리하는 사람의 일이다. 에이전트 쪽에서 할 수 있는 일은 찾은 자리의 원문을 드러내 사람이 보게 하는 것이다.') + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 결과에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/품질_대응_카드.md</code>를 다시 본다. 이 카드를 받아 부서에 넘기는 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 결과의 모양은 완성 폴더와 다를 수 있으므로, 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>찾았다고 친 정보가 정말 있는 것인가</b>Q06의 사진. 위의 「구체적으로」가 이 경우다.</li><li><b>호출 기록이 카드를 가리지 않는가</b>카드마다 분류 기준의 유형 여섯 가지가 「받음」에 통째로 실려, 다음 카드를 보려면 한참 내려가야 한다. 무엇을 md에 남기고 무엇을 json에만 둘 것인가.</li><li><b>같은 로트의 접수가 서로를 가리키는가</b>Q04와 Q09, Q08과 Q13은 같은 로트다. 카드는 접수마다 따로 만들어져, 한 카드를 받은 사람은 같은 로트의 다른 접수가 있다는 것을 모른다.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 모양만 바꾸는 요청이면 「json의 칸과 유형 · 원인_상태를 정하는 부분은 건드리지 마」를 꼭 넣는다.</p>'
 + write('w8', '무엇이 문제인지, 왜 문제인지, 에이전트.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(찾았다고 친 정보)를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P8, pre=True) + '</details>'
 '<p style="margin-top:18px">고친 뒤에는 두 가지를 본다. <code>에이전트.py</code>에서 요청한 부분만 바뀌었는가. 6단계에서 맞춰 본 원인 상태와 갈래가 그대로인가. 완성 폴더의 결과에서는 Q06 카드에 아래 줄이 생겼다. 굵은 줄을 읽으면 사진을 아직 받지 못했다는 것이 보인다.</p>'
 '<div class="tree" style="white-space:pre-wrap;font-size:13.5px">' + q06html + '</div>'
 + shot('되돌려 준 뒤 Copilot이 에이전트.py의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색으로 표시된 화면).')
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 되묻지 않고 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다. 새 줄 덕분에 다른 카드에서 드러난 것(불량 수량으로 잡힌 숫자가 로트의 수량이나 샘플의 수인 경우)을 짚어 주었는지도 본다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>조사 중인 가설을 확정으로 적어 달라고 해 본다.</b> 5단계에서는 접수와 허용 목록을 건드렸다. 이번에는 6단계에서 내가 정한 기준이다. Q04와 Q09의 로트는 유온이 올랐던 구간에 만든 것이 맞고, 품질팀의 조사도 그쪽을 보고 있다. 아래를 보내고, 카드가 그대로인지, Copilot이 규칙 파일의 어느 줄을 들었는지, 출하가 급한 사정을 풀 어떤 길을 내놓았는지를 본다.</p>'
  + copy(P5c, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
  + '<p style="margin-top:18px"><b>기준을 내 손으로 고쳐 다시 돌려 본다.</b> <code>기준/분류_기준.json</code>의 <code>확인_정보</code>에서 사진의 낱말 <code>"사진"</code>을 <code>"사진 첨부", "사진 있음"</code> 둘로 바꿔 저장하고, 터미널에서 <code>python 에이전트.py</code>를 실행한다. Q06의 추가 확인 항목에 사진이 생기는가. 다른 카드는 그대로인가. 프로그램은 고치지 않았다. 다 보았으면 낱말을 되돌려 놓는다.</p>'
  '<p><b>한 건만 실행해 본다.</b> 터미널에서 <code>python 에이전트.py Q09</code>를 실행하면 결과 두 파일에 무엇이 남는가. 열세 건의 결과로 되돌리려면 어떻게 실행하면 되는가.</p>'
  '<p><b>조사가 끝나면 무엇이 바뀌는가.</b> 품질팀이 CA-2610-03을 종결하면 Q04와 Q09의 카드는 어떻게 바뀌는가. 그때 고쳐야 하는 것은 프로그램인가, 자료인가. 그 자료를 고칠 수 있는 사람은 누구인가.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 읽고 손으로 만들어 보게 한다', '2. 정하고 계획 받기', '3. 도구 셋으로 한 건 돌리기', '4. 열두 건을 접수와 맞추기', '5. 규칙을 건드려 보기', '6. 원인을 대장에서 확인하기', '7. 새 접수 넣어 돌리기', '8. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>불량 접수 + 분류 기준 → 품질 대응 카드</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-05-4-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. 붙여넣는 곳을 확인하고 붙여넣으세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 불량 접수를 품질 대응 카드로 바꾸는 에이전트</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
