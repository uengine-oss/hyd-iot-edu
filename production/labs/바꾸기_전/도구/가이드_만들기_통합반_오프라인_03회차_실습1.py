"""통합반 오프라인 03회차 실습 1 「조치 절차와 조건을 판단 규칙으로 표현하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
본보기(가이드_만들기_본보기.py)의 스타일과 스크립트를 그대로 쓰고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json, csv
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '03회차_실습1_결정표'
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
.chg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}
.chg .tree{font-size:14px;line-height:1.8;padding:14px 18px}
.chg .tree b{color:#ffd76a}
table.res th{white-space:nowrap}
@media(max-width:760px){.flow,.vs,.four,.pipe,.chg{grid-template-columns:1fr}.pipe span{display:none}}
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 세 문서의 조건 문장을 옮긴 결정표 여섯 행, 경계값 확인 기록, 제외 사유 기록</b></div></div>'
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
P1rich = ('<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 양식/결정표_양식.md, 문서/HM-8_쿨러팬_정비매뉴얼.md 를 읽어 줘.</span> '
          '<span class="p-b">매뉴얼에서 네 조치 후보(SOP-COOL-11~14)를 지금 써도 되는지를 가르는 조건 문장을 찾아서, 절 번호 · 문장 · 견주는 값 · 그 값이 양식의 입력 목록에 있는지를 표로 적어 줘. 조건처럼 보이지만 결정표의 행으로 옮기기 어렵다고 본 문장은 따로 모아 까닭을 한 줄씩 붙여 줘.</span> '
          '<span class="p-c">행으로 옮기려면 내가 정해 줘야 하는 것이 있으면 스스로 정하지 말고 물어 줘. 아직 파일은 만들지 마.</span>')
assert re.sub(r'<[^>]+>', '', P1rich) == P1
P2, P3, P4, P5a, P5b, P6, P7a, P7b, P7c, P8 = (P(f'{n}_prompt.txt') for n in ('2', '3', '4', '5a', '5b', '6', '7a', '7b', '7c', '8'))

# ── 완성 폴더의 결정표(이 실습의 결과)에서 읽는다
rules = list(csv.DictReader((R / '완성' / '결정표' / '결정표.csv').open(encoding='utf-8', newline='')))
assert [r['규칙'] for r in rules] == ['R1', 'R2', 'R3', 'R4', 'R5', 'R6']
def cond(r): return f'<code>{e(r["입력"])} {e(r["비교"])} {e(r["기준값"])}</code>' + (f' {e(r["단위"])}' if r['단위'] else '')
def out(r): return e(r['판정']) + (f' {e(r["감점_만원"])}만 원' if r['감점_만원'] else '')
def dtable(rs, mark=()):
    return ('<table class="res"><thead><tr><th>규칙</th><th>조건</th><th>판정</th><th>대상</th><th>근거 절</th><th>원문</th></tr></thead><tbody>'
            + ''.join(f'<tr><td class="nw"><b>{"<mark>" if r["규칙"] in mark else ""}{e(r["규칙"])}{"</mark>" if r["규칙"] in mark else ""}</b></td><td class="nw">{cond(r)}</td><td class="nw">{out(r)}</td><td class="nw">{e(r["대상"]).replace("SOP-COOL-", "").replace(";", " · ")}</td><td class="nw">{e(r["근거_절"])}</td><td style="font-size:13.5px">{e(r["원문"])}</td></tr>' for r in rs)
            + '</tbody></table>')

# ── 완성 폴더의 경계값 확인에서 줄을 옮긴다
bmd = (R / '완성' / '결과' / '경계값_확인.md').read_text(encoding='utf-8')
brow = [[c.strip() for c in l.strip().strip('|').split('|')] for l in bmd.splitlines() if re.match(r'\| R\d', l)]
assert len(brow) == 12
def btable(ids, markvals=()):
    h = '<table class="res"><thead><tr><th>규칙</th><th>대어 본 값</th><th>조건에 맞는가</th><th>원문으로 읽은 결과</th><th>같은가</th></tr></thead><tbody>'
    for r in brow:
        if r[0] not in ids: continue
        m = r[1] in markvals
        h += '<tr>' + ''.join(f'<td{" class=nw" if i in (0, 1, 4) else ""}>{"<mark>" if m and i == 1 else ""}{e(x)}{"</mark>" if m and i == 1 else ""}</td>' for i, x in enumerate(r)) + '</tr>'
    return h + '</tbody></table>'

# ── 완성 폴더의 제외 사유에서 상황마다 한 줄로 줄여 옮긴다
xmd = (R / '완성' / '결과' / '제외_사유.md').read_text(encoding='utf-8')
situ = {s['번호']: s for s in json.loads((R / '시작' / '입력' / '운전_상황.json').read_text(encoding='utf-8'))['상황']}
xs = {}
for sec in re.split(r'\n## ', xmd)[1:]:
    no = sec.split('\n', 1)[0].strip()
    ex = [[c.strip() for c in l.strip().strip('|').split('|')] for l in sec.splitlines() if l.startswith('| SOP')]
    xs[no] = {'ex': ex, 'left': re.search(r'남는 후보: (.*)', sec).group(1), 'also': (re.search(r'빠진 후보에 함께 걸린 것: (.*)', sec) or [None, ''])[1]}
assert list(xs) == ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'] and xs['S6']['left'] == '없음' and len(xs['S5']['ex']) == 2
sh = lambda t: e(t).replace('SOP-COOL-', '')
def xrow(no, mark=False):
    s = situ[no]; x = xs[no]
    exs = ', '.join(f'{sh(r[0])} ({e(r[1])}, {e(r[3])})' for r in x['ex']) or '없음'
    return f'<tr><td class="nw"><b>{no}</b></td><td>{e(s["plc_mode"])} · {e(s["plc_state"])} · 팬 {s["fan100_hours"]} h</td><td>{"<mark>" if mark else ""}{exs}{"</mark>" if mark else ""}</td><td>{sh(x["left"])}</td></tr>'
xtable = ('<table class="res"><thead><tr><th>상황</th><th>설비의 상태</th><th>빠지는 후보 (걸린 규칙, 대어 본 값)</th><th>남는 후보</th></tr></thead><tbody>'
          + xrow('S1') + xrow('S2') + xrow('S3') + xrow('S4') + xrow('S5', True) + xrow('S6', True) + '</tbody></table>')

choices1 = '''<table class="res"><thead><tr><th style="width:140px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>어느 문장을 옮기는가</b></td><td><mark>1번 줄</mark> 조건과 판정을 함께 말하는 문장만 옮긴다. 절차 안의 확인 단계, 조치 뒤의 회복 판정, 원인을 가리는 문장은 옮기지 않는다</td><td>「판정을 말하지 않는 조건 문장도 경고로 옮긴다」로 바꾼다. 「24시간을 넘으면 팬 수명이 줄어든다」가 행이 되어, 같은 조건을 보는 행이 감점과 경고로 둘이 된다</td></tr>
<tr><td><b>같은 조건이 여러 절에 있을 때</b></td><td><mark>2번 줄</mark> 행은 하나만 둔다. 근거 절과 원문은 판정과 대상을 가장 분명하게 적은 문장의 것으로 한다</td><td>「절마다 행을 둔다」로 바꾼다. 운전 모드의 행이 HM-8.5와 HM-8.8에서 따로 나온다. 빠지는 후보는 같지만 매뉴얼이 개정될 때 고칠 행이 둘이 된다</td></tr>
<tr><td><b>판정을 가리는 낱말</b></td><td><mark>3번 줄</mark> 「쓰지 않는다」는 제외, 「감점해서 비교한다」는 감점, 「다른 조치와 비교한다」는 경고</td><td>「다른 조치와 비교한다」는 판정이 아니라고 보고 옮기지 않는다. 행이 둘로 줄고, 예측 유온이 62.5 ℃인 쿨러 핀 세척에 아무것도 붙지 않는다</td></tr>
<tr><td><b>대상이 분명하지 않을 때</b></td><td><mark>4번 줄</mark> 절차 번호가 적혀 있으면 그 후보에만. 「팬 최대 운전 조치」는 팬을 100 %로 올리는 단계가 있는 절차 모두. 대상을 가리지 않았으면 모든 후보</td><td>「팬 최대 운전 조치는 이름이 같은 SOP-COOL-11뿐」으로 바꾼다. 팬을 똑같이 100 %로 올리는 SOP-COOL-12가 감점 없이 견주어진다</td></tr>
<tr><td><b>입력 목록에 없는 값</b></td><td><mark>5번 줄</mark> 행으로 옮기지 않고, 옮기지 않았다는 것과 까닭을 답에 적게 한다</td><td>이름을 새로 지어 넣는 선택은 없다. 규칙 파일이 막는다. 그 조건을 표에 넣으려면 입력 목록을 맡은 사람에게 값을 받아 올 길부터 요청해야 한다</td></tr>
<tr><td><b>규칙 번호의 순서</b></td><td><mark>6번 줄</mark> 제외, 감점, 경고의 순서로 R1부터</td><td>「문서에 나온 순서」로 바꾼다. 행의 내용은 같고 번호만 달라진다. 다음 실습의 자료와 번호가 어긋난다</td></tr>
</tbody></table>'''

choices2 = '''<table class="res"><thead><tr><th style="width:140px">Copilot이 물은 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>기준값이 문장에 없다</b></td><td><mark>1번 줄</mark> 다른 문서에 있는 수를 적는다. 인터록 한계는 HM-8.3의 65 ℃다. 근거 절과 원문은 SR-04의 문장 그대로 둔다</td><td>「수가 문장에 없으니 옮기지 않는다」로 바꾼다. 유온이 인터록 한계에 닿을 조치를 막는 행이 표에서 사라진다</td></tr>
<tr><td><b>「거부한다」의 판정과 대상</b></td><td><mark>2번 줄</mark> 제외로 옮기고 모든 후보에 댄다. 보호 정지 중에는 네 후보 가운데 어느 것도 고르지 않고 냉각 후 리셋으로 먼저 간다고 본다</td><td>「원격 설비 제어인 셋에만 댄다」로 바꾼다. 「제어 명령」을 글자대로 읽은 것이다. 보호 정지 중에도 쿨러 핀 세척이 후보에 남고, 다음 실습의 결정표와 한 칸이 달라진다</td></tr>
<tr><td><b>HM-3.2의 운전 모드 문장</b></td><td><mark>3번 줄</mark> R1과 같은 조건으로 보고 행을 더하지 않는다</td><td>따로 행을 둔다. 「IT 승인 조치」가 어느 후보인지는 문서에 없으므로 대상을 내가 또 정해야 한다</td></tr>
<tr><td><b>「…할 수 있다」</b></td><td><mark>4번 줄</mark> 위험만 알리는 문장은 경고로 옮긴다. 165 bar 문장도 행으로 더하고 모든 후보에 댄다</td><td>옮기지 않는다. 압력을 보는 행이 하나도 없는 표가 된다</td></tr>
<tr><td><b>같은 판정 안의 번호</b></td><td><mark>5번 줄</mark> 문서를 읽은 순서로 매긴다</td><td>다르게 정해도 번호만 달라진다</td></tr>
</tbody></table>'''

axis = '''<div class="axis"><svg viewBox="0 0 760 150" role="img" aria-label="fan100_hours > 24 의 경계">
<text x="14" y="26" font-size="15" font-weight="800" fill="#14181f">R2  fan100_hours &gt; 24</text><text x="232" y="26" font-size="13" fill="#5b6573">「24시간을 넘겼다면」 — 기준값 자신은 들지 않는다</text>
<line x1="60" y1="78" x2="380" y2="78" stroke="#cfd6e0" stroke-width="6" stroke-linecap="round"/><line x1="380" y1="78" x2="710" y2="78" stroke="#2f5bea" stroke-width="6" stroke-linecap="round"/>
<circle cx="380" cy="78" r="9" fill="#fff" stroke="#2f5bea" stroke-width="4"/>
<circle cx="250" cy="78" r="6" fill="#8a94a3"/><circle cx="510" cy="78" r="6" fill="#2f5bea"/>
<text x="250" y="112" font-size="14" font-weight="700" text-anchor="middle" fill="#14181f">23.9 (바로 아래)</text><text x="250" y="132" font-size="13" text-anchor="middle" fill="#5b6573">맞지 않는다</text>
<text x="380" y="112" font-size="14" font-weight="800" text-anchor="middle" fill="#14181f">24 (기준값 자신)</text><text x="380" y="132" font-size="13" text-anchor="middle" fill="#b3261e">맞지 않는다</text>
<text x="510" y="112" font-size="14" font-weight="700" text-anchor="middle" fill="#14181f">24.1 (바로 위)</text><text x="510" y="132" font-size="13" text-anchor="middle" fill="#2f5bea">맞는다 → 감점 20만 원</text>
<text x="600" y="62" font-size="13" fill="#2f5bea">조건에 맞는 구간</text></svg></div>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 3회차 · 실습 1 · 40분</small>매뉴얼의 조건 문장을<br>결정표의 행으로 옮긴다',
 '조치를 해도 되는지를 가르는 조건은 매뉴얼과 규정의 여러 절에 문장으로 흩어져 있다. 문장으로만 두면 읽는 사람마다 「넘으면」과 「이상이면」을 다르게 읽고, 어느 조치에 대는 말인지도 다르게 읽는다. 오늘은 세 문서의 조건 문장을 Copilot과 함께 결정표의 행으로 옮긴다. 옮기는 손은 Copilot이지만, 어느 문장을 옮기고 무엇으로 읽을지는 <b>내가 정한다.</b>',
 [('끝나면 남는 것', '결정표 여섯 행, 경계값 확인, 제외 사유 기록'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '온라인 3일차의 결정표 단원을 들었다'), ('준비에 쓰는 시간', '약 3분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>문서 셋의 문장이 표 하나가 되고, 그 표를 운전 상황에 대어 본 기록이 남는다. 이 결정표는 실습 3에서 판정 기능이 읽는 표가 된다.</p>'
  '<div class="pipe"><div><b>문서 셋</b>쿨러 팬 정비 매뉴얼, 운전 · 정비 매뉴얼, 설비안전규정<small>문서/</small></div><span>→</span><div class="out"><b>결정표</b>조건 문장 하나가 한 행<small>결정표/결정표.csv</small></div><span>→</span><div><b>두 기록</b>경계에서 맞는지, 어느 조치가 왜 빠지는지<small>결과/경계값_확인.md · 제외_사유.md</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 행을 문서의 문장과 맞춰 보는 것이다.</p>'
  '<div class="flow"><div><em>1</em><b>읽게 한다</b>매뉴얼에서 조건 문장을 찾아 표로 보이게 한다</div><div><em>2</em><b>정해 준다</b>문장이 정하지 않은 여섯 가지를 내가 정한다</div><div><em>3</em><b>계획을 받는다</b>어떤 행이 나올지를 파일보다 먼저 본다</div><div><em>4</em><b>작게 만든다</b>세 행을 만들고 경계에서 원문과 맞춘다</div><div><em>5</em><b>되돌려 준다</b>아쉬운 곳은 무엇이 왜 문제인지 말해 고친다</div></div>'
  '<p style="margin:18px 0 0">1~4단계와 8단계가 이 다섯 걸음이다. 그 사이에 세 가지를 더 해 본다. 같은 방식을 다른 두 문서에 써서 행을 더하고(5단계), 만든 표를 운전 상황 여섯에 대어 제외 사유를 남기고(6단계), 규칙에 어긋나는 요청을 일부러 보내 본다(7단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 '<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md         <i>← 이 폴더의 규칙</i>\n├─ <span>문서/</span>\n│  ├─ HM-8_쿨러팬_정비매뉴얼.md       <i>← 먼저 옮길 문서</i>\n│  ├─ HM_운전정비매뉴얼_발췌.md       <i>← 5단계에서 쓴다</i>\n│  └─ SR-04_설비안전규정_발췌.md      <i>← 5단계에서 쓴다</i>\n├─ <span>양식/</span>\n│  └─ 결정표_양식.md                  <i>← 열, 입력 목록, 판정의 뜻</i>\n├─ <span>입력/</span>\n│  └─ 운전_상황.json                  <i>← 6단계에서 표에 대어 볼 상황 6건</i>\n├─ <span>결정표/</span>                            <i>← 지금은 비어 있다</i>\n└─ <span>결과/</span>                              <i>← 지금은 비어 있다</i></div>'
 '<div><p><b>규칙 파일</b>은 Copilot이 이 폴더에서 일할 때 지키는 약속이다. 「하면 안 되는 것」과 「정해져 있는 것」은 누가 요청해도 바뀌지 않는 자리이고, 7단계에서 일부러 건드려 본다. 「정해져 있지 않은 것」의 일곱 줄은 일부러 비워 둔 자리이고, 2단계와 5단계에서 내가 채운다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 문서, 양식, 입력, 결정표, 결과 여섯 폴더가 보이고 문서 폴더가 펼쳐져 있게.'))
+ do(2, 'editor', 'VS Code · 편집기', '양식에서 열 열 개와 입력 목록을 본다',
 '<p><code>양식/결정표_양식.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 본다. 두 곳만 읽는다.</p>'
 '<ul class="ask"><li><b>표의 열</b>한 행은 조건(입력 · 비교 · 기준값 · 단위), 판정(제외 · 감점 · 경고), 대상(어느 후보에 대는가), 근거(절 번호와 원문)로 이루어진다. 문장 하나를 이 네 조각으로 나누는 것이 오늘의 일이다.</li><li><b>입력 목록</b>조치를 판단하는 때에 실제로 얻을 수 있는 값 아홉 가지다. 문장이 아무리 분명한 조건이어도, 견주는 값이 이 목록에 없으면 표에 넣어도 대어 볼 수가 없다.</li></ul>')
+ do(3, 'editor', 'VS Code · 편집기와 종이', '문장 하나를 손으로 먼저 옮겨 본다',
 '<p><code>문서/HM-8_쿨러팬_정비매뉴얼.md</code>의 맨 아래 <b>HM-8.8 금지와 제한</b>을 연다. 둘째 줄의 뒤 문장을 종이에 네 조각으로 나누어 적는다.</p>'
 '<div class="vs"><div class="good" style="grid-column:1/-1"><b>옮길 문장 (HM-8.8)</b><q>이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다.</q>입력은 목록의 어느 이름인가. 비교 기호는 <code>&gt;</code>인가 <code>&gt;=</code>인가. 판정과 금액은 무엇인가. 대상은 네 후보 가운데 어느 것인가.</div></div>'
 + note('적다가 막히는 곳이 있다', '「팬 최대 운전 조치」는 이름이 「팬 최대 운전」인 SOP-COOL-11만을 가리키는가, 팬을 100 %로 올리는 SOP-COOL-12도 드는가. 문장에는 답이 없다. 막힌 곳에 물음표를 쳐 두고 넘어간다. 2단계에서 내가 정한다.'))
+ nxt(1, '1. 만들기 전에, 조건 문장을 찾게 한다'))

# ───────── 1단계
pages.append(hero('1단계', '만들기 전에,<br>조건 문장을 찾게 한다',
 '첫마디가 「이 매뉴얼로 결정표를 만들어 줘」이면 AI는 문서를 읽자마자 표를 쓴다. 어느 문장을 행으로 삼았는지, 같은 조건이 두 절에 있을 때 어느 쪽을 근거로 골랐는지는 표 속에 묻혀 보이지 않는다. 그래서 첫 요청은 <b>읽고, 조건 문장을 찾아 보여 주고, 정할 수 없는 것은 물어보라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '조건 문장의 목록과 Copilot이 나에게 묻는 것이 채팅에 있다'), ('아직 없어야 하는 것', '새 파일')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 Copilot 아이콘에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽는가', '규칙 파일, 양식, 매뉴얼 하나. 문서 셋을 한꺼번에 주지 않고 하나부터 시작한다. 나머지 둘은 5단계에서 쓴다.'), ('어떤 모양으로 답하는가', '찾은 문장을 절 번호와 함께 표로 보이게 했다. 견주는 값이 입력 목록에 있는지도 묻는다. 옮기기 어려운 문장을 따로 모으게 한 것은, 빠뜨린 것과 일부러 뺀 것을 가르기 위해서다.'), ('하지 말 것', '스스로 정하지 말 것, 파일을 만들지 말 것. 이 두 문장이 없으면 AI가 빈자리를 채워 표부터 쓴다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>답이 오는 데 1분 남짓 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래 세 가지가 내 답에도 있는지를 본다.</p>'
 + shot('위 요청에 대한 Copilot의 답. 조건 문장을 모은 표, 옮기기 어렵다고 본 문장의 표, 답의 끝에서 정해 달라고 묻는 목록이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('같은 조건이 몇 번 나오는가', '운전 모드가 REMOTE_AUTO여야 한다는 조건은 HM-8.5의 본문, 세 절차의 1단계, HM-8.8에 되풀이된다. 24시간도 SOP-COOL-11의 2단계와 HM-8.8에 있다. Copilot의 표에서 이 문장들이 따로따로 보이는지 센다.'),
        ('입력 목록에 없는 값을 가려냈는가', '「펌프 부하를 60 % 미만으로 설정하지 않는다」는 분명한 금지 문장이다. 그런데 견주는 값(부하 설정값)이 입력 목록에 없다. Copilot이 이름을 지어내지 않고 「없음」으로 적었는지 본다.'),
        ('판정하지 않고 되물은 것', '준비에서 내가 물음표를 친 「팬 최대 운전 조치」의 대상을 Copilot도 물었는가. 물음이 몇 가지인지 세어 둔다. 다음 단계에서 이 물음에 내가 답한다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 일곱 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 이 줄이 없었다면 AI는 가장 그럴듯한 쪽으로 알아서 정했을 것이고, 무엇이 어떻게 정해졌는지는 표를 문서와 한 줄씩 견주어야 알 수 있다.')
 + ifs(('파일이 생겨 버렸다면', '탐색기의 <code>결정표</code> 폴더에 파일이 보이면 요청의 마지막 문장이 빠진 것이다. 생긴 파일을 지우고 요청을 다시 복사해 보낸다.'),
       ('되묻는 것이 없다면', '「행으로 옮기려면 내가 정해 줘야 하는 것을 목록으로 물어 줘」라고 한 번 더 보낸다. 그래도 없으면 다음 단계로 가되, 계획에 내가 정하지 않은 것이 들어 있는지를 더 꼼꼼히 읽는다.')))
+ nxt(2, '2. 문장이 정하지 않은 것을 내가 정하고, 나올 행부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '문장이 정하지 않은 것을 내가 정하고,<br>나올 행부터 받는다',
 '매뉴얼은 사람이 읽으라고 쓴 글이다. 같은 조건을 여러 번 적고, 판정을 「비교한다」처럼 에둘러 말하고, 대상을 「조치」라고만 적는다. 표의 칸은 그런 흐릿함을 받아 주지 않는다. 칸마다 값 하나를 적어야 한다. 그 사이를 메우는 결정이 이 실습의 핵심이고, 정답이 하나가 아니므로 <b>요청하는 사람이 정한다.</b>',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '내 결정대로 나올 행이 채팅에 표로 있다'), ('아직 없어야 하는 것', '새 파일')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '여섯 빈자리마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices1
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결정표와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이고, 실습 3이 이어받는 표도 그것이다. 다르게 정하면 내 표가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 다만 왜 그렇게 정했는지를 말할 수 있어야 한다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 나올 행부터 보여 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abbc'))
 + parts(('무엇을 왜 만드는가', '첫 문단. 「누가 대어 보아도 같은 답이 나오게」가 이 표의 목적이다. 목적을 알면 Copilot이 흐릿한 문장 앞에서 짐작하지 않고 묻는다.'), ('빈자리 여섯 가지', '번호를 붙여 한 줄에 결정 하나씩 적었다. Copilot도 나도 어느 결정 때문에 그 행이 나왔는지를 번호로 짚을 수 있다.'), ('계획 먼저', '마지막 문단. 파일보다 표를 먼저 보이게 했고, 기호를 고른 까닭을 원문의 낱말과 함께 적게 했다. 기호는 이 표에서 가장 틀리기 쉬운 칸이다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 세 가지를 찾는다',
 '<p>Copilot은 파일을 만들지 않고, 나올 행을 표로 보여 준다.</p>'
 + shot('2단계 요청에 대한 Copilot의 답. 나올 행의 표, 비교 기호를 고른 까닭, 옮기지 않는 문장의 표, 확인해 달라는 항목이 보이게. 기호의 까닭에 적힌 원문의 낱말(아닐 때 · 넘겼다면 · 이상이면)에 테두리를 얹는다.')
 + find(('기호의 까닭이 원문의 낱말인가', '「넘겼다면」이면 <code>&gt;</code>, 「이상이면」이면 <code>&gt;=</code>, 「아닐 때」이면 <code>!=</code>이다. 까닭이 낱말이 아니라 「보통 그렇게 한다」 같은 말이면 원문을 다시 읽게 한다.'),
        ('옮기지 않는 문장에 까닭이 있는가', '옮기지 않은 문장마다 내가 정한 몇 번 때문인지가 적혀 있는지 본다. 60 % 문장은 5번, 절차의 확인 단계는 1번이어야 한다.'),
        ('다시 확인해 달라는 것', '여섯 가지를 정해 주어도 빈자리가 더 나온다. 예를 들어 「REMOTE_MANUAL이면 내리지 않는다」를 운전 모드 행에 묶어도 되는지. Copilot이 어떻게 했는지와 그 까닭을 읽는다.'))
 + ifs(('나올 행이 내 짐작과 다르다면', '어느 행의 어느 칸이 다른지를 말한다. 「R2의 대상에 SOP-COOL-13이 들어 있어. 13은 팬 속도를 그대로 두는 절차야.」처럼 문서의 문장을 근거로 댄다.'),
       ('계획 없이 파일부터 만들었다면', '요청의 마지막 문단이 빠진 것이다. 생긴 파일을 지우고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.')))
+ nxt(3, '3. 세 행을 만들고 문서와 맞춘다', 1))

# ───────── 3단계
pages.append(hero('3단계', '세 행을 만들고<br>문서와 맞춘다',
 '이제 만들게 한다. 범위는 <code>결정표.csv</code> 한 파일이다. 만든 표가 문서와 같은지는 AI에게 맡기지 않고 내가 본다. 표가 틀렸을 때 그 표로 조치를 가르는 것은 사람이고, 그 책임은 표를 받아들인 사람에게 있다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '결정표 폴더에 세 행짜리 결정표.csv가 있다'), ('맞춰 볼 것', '표의 행 ↔ 매뉴얼의 문장')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 범위를 정해 준다',
 '<p>보여 준 행을 받아들이고 파일 하나만 만들게 한다. 받아들이고 싶지 않은 칸이 있으면 보내기 전에 「다만 R○의 ○○ 칸은 이렇게 해 줘」를 한 줄 더한다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'ac'))
 + '<p style="margin-top:14px">Copilot이 파일을 만들 때 허락을 구하는 물음이 뜰 수 있다. 만드는 파일이 <code>결정표/결정표.csv</code>인지 읽고 허용한다.</p>')
+ do(2, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '표의 행을 매뉴얼의 문장과 한 줄씩 맞춘다',
 '<p><code>결정표/결정표.csv</code>를 열고, <code>문서/HM-8_쿨러팬_정비매뉴얼.md</code>를 오른쪽으로 끌어 나란히 둔다. 아래는 완성 폴더의 세 행이다. 내 표와 견주고, 표의 행마다 매뉴얼에서 그 문장을 찾는다.</p>' + dtable(rules[:3])
 + shot('결정표.csv와 매뉴얼의 HM-8.8을 좌우로 나란히 연 VS Code 화면. 표의 R2 행과 매뉴얼의 「이미 24시간을 넘겼다면…」 문장에 테두리를 얹는다.')
 + find(('원문 칸이 글자 그대로인가', 'R2의 원문을 매뉴얼의 문장과 한 글자씩 견준다. 줄였거나 앞 문장을 이어 붙였다면 규칙에 어긋난다. 근거를 찾으러 온 사람이 문서에서 그 문장을 찾기(Ctrl+F)로 바로 찾을 수 있어야 한다.'),
        ('대상이 내가 정한 대로인가', 'R1은 문장에 적힌 셋, R2는 팬을 100 %로 올리는 단계가 있는 둘, R3은 모든 후보다. 준비에서 물음표를 친 자리가 내 결정대로 채워졌는지 본다.'),
        ('비운 칸이 비어 있는가', '단위가 없는 R1의 단위 칸, 감점이 아닌 R1 · R3의 감점_만원 칸은 비어 있어야 한다. 쉼표가 두 개 이어진 자리가 빈 칸이다.'))
 + ifs(('다른 파일도 생겼다면', '<code>결과</code> 폴더에 파일이 생겼다면 지우고 「결정표.csv 한 파일만」이라고 다시 말한다. 그 파일들은 다음 단계부터 하나씩 만든다.'),
       ('행의 수가 다르다면', '2단계에서 다르게 정했다면 틀린 것이 아니다. 그대로 정했는데 다르다면, 더 있거나 빠진 행이 어느 문장에서 나왔는지를 묻는다.')))
+ nxt(4, '4. 기준값의 곁에서 기호를 확인한다', 2))

# ───────── 4단계
pages.append(hero('4단계', '기준값의 곁에서<br>기호를 확인한다',
 '「넘겼다면」을 <code>&gt;=</code>로 옮겨도 23시간과 30시간에서는 아무 차이가 없다. 잘못은 기준값 자신에서만 드러난다. 그래서 숫자와 견주는 행은 기준값과 그 바로 아래, 바로 위의 세 값을 대어 보고, 표의 기호로 견준 결과가 원문을 읽은 결과와 같은지를 기록으로 남긴다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '결과 폴더에 경계값_확인.md가 있다'), ('바뀌면 안 되는 것', '결정표.csv')])
+ '<section class="sect"><h2>세 값으로 보는 까닭</h2><p>수직선 위에서 조건에 맞는 구간은 기준값에서 시작한다. 기준값 자신이 그 구간에 드는지 아닌지가 기호 하나로 갈린다.</p>' + axis + '</section>'
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '경계값을 대어 본 기록을 만들게 한다',
 '<p>두 가지 방법으로 읽은 결과를 나란히 적게 하는 요청이다.</p>' + copy(P4, pre=True, rich=richpre(P4, 'abc'))
 + parts(('왜 하는가', '첫 문단. 무엇을 확인하려는지와 어디에서 드러나는지를 말했다.'), ('어떻게 대어 보는가', '둘째 문단. 세 값을 어떻게 잡을지(0.1)를 정해 주었고, 한 칸은 표의 기호로, 다른 칸은 표를 보지 않고 원문만 읽어 채우게 했다. 같은 것을 두 번 적게 하지 않으려는 것이다.'), ('다르면 어떻게 하는가', '셋째 문단. 고치지 말고 알리게 했다. 다르다는 것은 표가 틀렸거나 원문이 흐릿하다는 뜻이고, 어느 쪽인지는 사람이 가린다.')))
+ do(2, 'editor', 'VS Code · 편집기', '기준값 자신의 줄을 읽는다',
 '<p><code>결과/경계값_확인.md</code>를 열어 미리 보기로 본다. 아래는 완성 폴더의 기록이다. 노랗게 칠한 줄이 기준값 자신이다.</p>' + btable(('R2', 'R3'), ('24 h', '55 ℃'))
 + find(('24 자신과 55 자신이 서로 다르게 나왔는가', 'R2의 24는 맞지 않고 R3의 55는 맞는다. 둘 다 「기준값 자신」인데 결과가 반대인 것은 원문의 낱말이 「넘겼다면」과 「이상이면」으로 다르기 때문이다.'),
        ('원문의 낱말이 적혀 있는가', '「원문으로 읽은 결과」 칸에 어느 낱말로 그렇게 읽었는지가 있는지 본다. 이 칸이 표의 기호를 그대로 되풀이한 것이면 확인이 되지 않는다.'),
        ('R1은 왜 없는가', 'R1은 숫자가 아니라 글자(REMOTE_AUTO)와 견준다. 바로 아래나 바로 위가 없다. Copilot이 그 까닭을 기록에 적었는지 본다.'))
 + note('기호를 바꾸면 어느 줄이 달라지는가', 'R2의 기호가 <code>&gt;=</code>였다면 24의 줄에서 「조건에 맞는가」는 맞는다, 「원문으로 읽은 결과」는 감점하지 않는다가 되어 「같은가」 칸이 「다르다」로 바뀐다. 이 기록은 그 한 줄을 잡아내려고 만드는 것이다.')
 + ifs(('「다르다」인 줄이 있다면', '그 줄의 원문을 매뉴얼에서 다시 읽는다. 표의 기호가 틀렸다면 「R○의 비교 기호를 원문의 ○○에 맞게 고쳐 줘」라고 요청하고, 확인 기록도 다시 만들게 한다.'),
       ('결정표가 바뀌었다면', '요청의 마지막 문단이 빠진 것이다. 무엇을 바꿨는지 묻고 되돌리게 한다.')))
+ nxt(5, '5. 같은 방식을 다른 두 문서에 쓴다', 3))

# ───────── 5단계
pages.append(hero('5단계', '같은 방식을<br>다른 두 문서에 쓴다',
 '지금의 표는 쿨러 팬 정비 매뉴얼 하나만 본 것이다. 네 후보를 가르는 조건은 다른 문서에도 있다. 설비안전규정에는 유온의 한계가, 운전 · 정비 매뉴얼에는 보호 정지와 압력에 관한 문장이 있다. 앞에서 정한 여섯 가지를 그대로 두고 문서만 바꾸면, 새 문서가 새 물음을 내놓는다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '결정표가 여섯 행이 되고, 온도와 압력과 설비 상태를 함께 본다'), ('바뀌면 안 되는 것', 'R1~R3의 줄')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '나머지 두 문서를 읽고 더할 행을 보이게 한다',
 '<p>1~2단계에서 한 일을 한 번에 시킨다. 정한 것을 다시 적지 않아도 같은 대화여서 Copilot이 기억한다.</p>' + copy(P5a, pre=True, rich=richpre(P5a, 'ab'))
 + shot('위 요청에 대한 Copilot의 답. 더할 행의 후보 표에서 채우지 못한 칸(「물음」이라고 적힌 칸)과, 정해 달라는 목록이 보이게. 채우지 못한 칸에 테두리를 얹는다.')
 + find(('채우지 못한 칸이 있는가', '설비안전규정의 문장은 「인터록 한계 이상이면」이라고만 하고 수를 적지 않았다. 수는 다른 문서인 쿨러 팬 매뉴얼의 HM-8.3에 있다. Copilot이 65를 스스로 적었는가, 비워 두고 물었는가.'),
        ('처음 보는 낱말을 물었는가', '「거부한다」와 「이어질 수 있다」는 2단계에서 정한 세 낱말에 없다. 제외인지 경고인지, 아예 옮기지 않을지를 물었는지 본다.'),
        ('네 후보의 조건이 아닌 문장을 가려냈는가', '예비 펌프 전환, 압력 설정, 리셋의 조건은 분명한 조건 문장이지만 네 후보에 대는 것이 아니다. 옮기지 않는 쪽에 까닭과 함께 있는지 본다.')))
+ do(2, 'chat', '이 화면의 표 → Copilot 채팅 (같은 대화)', '물어 온 것에 답하고 행을 더하게 한다',
 '<p>Copilot의 물음은 사람마다 조금씩 다르게 나오지만 대개 아래 다섯 가지에 든다. 2단계와 같이 가운데 칸이 복사 상자에 적힌 답이다. 내 답에 없는 물음의 줄은 그대로 보내도 해가 없다.</p>' + choices2
 + copy(P5b, pre=True, rich=richpre(P5b, 'bbc'))
 + note('2번 줄은 한 번 더 읽는다', '보호 정지 중에 쿨러 핀 세척까지 후보에서 빼는 것이 맞는가. 문장은 「제어 명령」이라고만 했고, 핀 세척은 사람이 하는 정비 작업이다. 복사 상자의 답은 「보호 정지 중에는 조치를 고르기 전에 냉각 후 리셋이 먼저」라고 보고 넷 모두에 대었다. 문서가 답하지 않는 자리이고, 이런 자리는 표를 쓰는 사람이 아니라 규정을 맡은 사람에게 물어 확정해야 한다.'))
+ do(3, 'editor', 'VS Code · 편집기', '여섯 행이 된 결정표를 본다',
 '<p><code>결정표/결정표.csv</code>를 다시 연다. 아래는 완성 폴더의 여섯 행이고, 노랗게 칠한 번호가 더해진 셋이다.</p>' + dtable(rules, ('R4', 'R5', 'R6'))
 + find(('R1~R3이 그대로인가', '새 행은 R3 뒤에 이어졌고 앞의 세 줄은 한 글자도 바뀌지 않았어야 한다. 규칙 번호는 다른 기록이 가리키는 이름이어서, 행을 더할 때 앞 번호가 바뀌면 그 기록들이 모두 틀린 것이 된다.'),
        ('R4의 65는 어디에 적혀 있는가', '기준값 칸은 65인데 원문 칸에는 수가 없다. 65가 어느 문서에서 왔는지는 <code>결과/경계값_확인.md</code>의 R4 절에 한 줄로 적혀 있는지 본다.'),
        ('R3과 R4가 같은 값을 본다', '둘 다 조치 후 예측 유온을 본다. 55 ℃ 이상이면 경고, 65 ℃ 이상이면 제외다. 예측 유온이 65 ℃인 후보에는 두 행이 함께 맞는다. 그때 어떻게 할지는 이 표에 적혀 있지 않다. 실습 3에서 정한다.'),
        ('165 자신은 어느 쪽인가', '<code>결과/경계값_확인.md</code>에 R4와 R6의 세 값이 더해졌다. R6은 「미만」이어서 165 자신은 맞지 않고 164.9가 맞는다. 조건에 맞는 구간이 기준값의 아래쪽인 행이다.'))
 + ifs(('행이 둘만 더해졌다면', '165 bar 문장을 옮기지 않은 것이다. 4번 줄이 빠졌는지 보고, 「HM-5.2의 165 bar 문장도 경고 행으로 더해 줘」라고 말한다.'),
       ('R1~R3의 번호가 바뀌었다면', '「이미 매긴 번호는 바꾸지 않는다」는 규칙 파일의 줄을 들어 되돌리게 한다.')))
+ nxt(6, '6. 표를 운전 상황에 대어 제외 사유를 남긴다', 4))

# ───────── 6단계
pages.append(hero('6단계', '표를 운전 상황에 대어<br>제외 사유를 남긴다',
 '결정표는 만들어 두는 것으로 끝나지 않는다. 지금의 값을 대어야 답이 나온다. 운전 상황 여섯 건에 표를 대어, 어느 조치가 어느 행에 걸려 빠지는지를 기록으로 남긴다. 조치를 승인하는 사람이 「이 후보는 왜 없는가」를 물었을 때 내놓는 기록이다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '결과 폴더에 제외_사유.md가 있다'), ('바뀌면 안 되는 것', '결정표.csv')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '여섯 상황에 표를 대어 보게 한다',
 '<p>규칙 파일이 비워 둔 마지막 줄(감점이나 경고만 맞은 후보를 어떻게 다룰지)을 이번에는 묻기 전에 요청에 적어 보낸다. 무엇을 물을지 알고 있으면 먼저 정해 주는 편이 빠르다.</p>' + copy(P6, pre=True, rich=richpre(P6, 'abc'))
 + parts(('누가 왜 보는 기록인가', '첫 문단. 읽을 사람과 그 사람의 물음을 말했다. 기록에 무엇을 담을지가 여기서 정해진다.'), ('빈자리를 미리 정한다', '둘째 문단. 감점과 경고만 맞은 후보는 빠지는 것이 아니다. 표에는 넣지 않고 남는 후보에 번호를 붙이게 했다. 남는 후보가 없는 경우의 표기도 정했다.'), ('건드리지 말 곳', '셋째 문단. 대어 보다가 표가 이상해 보여도 표를 고치는 것은 이 요청의 일이 아니다.')))
+ do(2, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '상황마다 빠지는 후보와 남는 후보를 맞춘다',
 '<p><code>결과/제외_사유.md</code>를 미리 보기로 열고 <code>입력/운전_상황.json</code>을 옆에 둔다. 아래는 완성 폴더의 기록을 상황마다 한 줄로 줄인 것이다(절차 번호는 줄여 적었다. 괄호 안은 붙은 감점 · 경고의 규칙이다).</p>' + xtable
 + shot('제외_사유.md의 미리 보기와 운전_상황.json을 좌우로 나란히 연 VS Code 화면. 미리 보기는 S5의 표와 「남는 후보」 줄이 보이게.')
 + find(('S5 — 0.1 ℃가 가른다', '예측 유온 64.9 ℃인 SOP-COOL-11은 남고, 65.0 ℃인 SOP-COOL-12는 빠진다. 4단계의 경계값 확인에서 본 줄이 실제 상황에서 후보를 가르는 모습이다.'),
        ('S6 — 남는 후보가 없다', '설비가 보호 정지(TRIP)여서 R5가 넷 모두에 맞는다. 「남는 후보: 없음」이라고 적혀 있고, 억지로 하나를 남기지 않았는지 본다. 5단계의 2번 줄을 다르게 정했다면 여기에 쿨러 핀 세척이 남는다.'),
        ('S2 — 빠지는 후보는 없지만', '팬이 24.1시간째여서 R2가 맞지만 감점은 제외가 아니다. 표는 비어 있고, 남는 후보의 괄호에 R2가 붙어 있어야 한다.'),
        ('Copilot이 스스로 정한 것', '빠지는 후보가 없는 상황에 무엇을 적었는가. 답의 끝에 「정해 주지 않아 이렇게 했다」는 말이 있는지 읽는다. 스스로 정하되 숨기지 않았는지를 보는 것이다.'))
 + ifs(('내 종이와 다른 줄이 있다면', '「S3의 SOP-COOL-14가 빠졌다고 적혀 있는데, R1의 대상에는 14가 없어.」처럼 상황 번호, 후보, 규칙을 들어 말한다.'),
       ('프로그램을 만들려고 한다면', '허용하지 않는다. 이 폴더의 규칙은 프로그램을 만들지 않게 되어 있다. 여섯 건은 손으로 대어 볼 수 있는 양이다. 수십 건을 되풀이해 대어야 할 때 프로그램이 필요해지고, 그것이 실습 3이다.')))
+ nxt(7, '7. 규칙을 일부러 건드려 본다', 5))

# ───────── 7단계
pages.append(hero('7단계', '규칙을<br>일부러 건드려 본다',
 '지금까지 Copilot은 규칙 안에서 움직였다. 규칙이 정말 막아 주는지는 규칙에 어긋나는 일을 시켜 보아야 안다. 결정표를 다루다 보면 누구나 「현장에서는 그 값이 아니래」, 「원문이 너무 기니까 줄여 줘」라고 말하게 된다. 그 말을 지금 일부러 해 본다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '결정표.csv, 결과의 두 파일')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '문서에 없는 기준값으로 바꿔 달라고 해 본다',
 '<p>현장의 경험을 근거로 댄 그럴듯한 요청이다. 틀린 말이 아닐 수도 있다.</p>'
 + copy(P7a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 결정표를 고치지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('파일이 그대로인가', '편집기에서 <code>결정표/결정표.csv</code>를 열어 R2의 기준값이 24 그대로인지 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고 같은 목적을 이루는 길을 내놓았는가. 기준값만 20으로 바꾸면 같은 행의 원문 칸은 24시간이라고 말하게 된다는 것까지 짚었는지 본다.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '원문 칸을 줄여 달라고 해 본다',
 '<p>이번에는 보기 좋게 하려는 요청이다. 나쁜 뜻이 없어서 더 쉽게 나오는 말이다.</p>'
 + copy(P7b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>결정표/결정표.csv</code>의 원문 칸이 그대로인지 본다. 표를 고치는 대신 Copilot이 무엇을 내놓았는지도 읽는다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절의 한 줄이다. 기준값이 어디에서 나와야 한다고 적혀 있는가. 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 한 줄이다. 원문 칸에 무엇을 어떻게 옮기라고 적혀 있는가. 몇 번인가.</li><li><b>두 답에 함께 나온 줄</b>「요청을 받아도 예외를 두지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('결정표의 값은 문서가 정한다', '기준값을 채팅에서 바꿀 수 있다면, 표의 24가 매뉴얼의 24인지 누군가의 말이었는지를 나중에 아무도 알 수 없다. 현장의 20시간이 옳다면 고칠 곳은 표가 아니라 매뉴얼이다. 매뉴얼이 개정되면 표는 그 문장을 따라 다시 옮기면 된다. 원문 칸을 줄이지 않는 까닭도 같다. 그 칸은 설명이 아니라 문서로 돌아가는 길이다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '방금 고친 것을 되돌려 달라고 말한다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(8, '8. 아쉬운 곳을 찾아 되돌려 준다', 6))

# ───────── 8단계
pages.append(hero('8단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '기록이 정한 대로 나왔더라도 실제로 쓰려고 보면 아쉬운 곳이 보인다. 예를 들어 S4에서 팬 최대 운전은 운전 모드 때문에 빠졌다고만 적혀 있다. 그런데 팬은 30시간째여서 감점 행에도 걸린다. 틀린 기록은 아니지만, 읽는 사람은 운전 모드만 돌아오면 그 조치를 대가 없이 쓸 수 있다고 읽는다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '제외_사유.md의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>제외 사유 기록이 좀 부족해. 다시 해 줘.</q>어디가 부족한지 AI는 모른다. 부족할 만한 곳을 여럿 늘어놓고 되묻거나, 짐작으로 여러 곳을 한꺼번에 바꾼다. 어느 쪽이든 한 번 더 주고받아야 한다.</div>'
  '<div class="good"><b>구체적으로</b><q>S4에서 SOP-COOL-11과 12는 R1에 걸려 빠졌다고만 적혀 있어. 그런데 두 후보는 R2 감점에도 걸려. 표의 여섯 열은 그대로 두고, \'남는 후보\' 줄 아래에 \'빠진 후보에 함께 걸린 것\' 한 줄을 더해 줘. 제외_사유.md 만 고쳐.</q>한 번에 끝나고, 요청한 곳만 바뀐다.</div></div>'
  '<div class="four"><div><b>무엇이</b>빠진 후보에 함께 걸린 감점이 보이지 않는다</div><div><b>왜</b>승인하는 사람이 대가 없이 쓸 수 있다고 읽는다</div><div><b>어디를</b>제외_사유.md의 「남는 후보」 줄 아래</div><div><b>어디까지</b>표의 여섯 열, 결정표, 경계값 확인은 그대로</div></div>'
  + note('「어디까지」에는 규칙도 들어 있다', '함께 걸린 규칙을 표의 열로 더해 달라고 하면 Copilot은 멈춘다. 제외 사유의 표는 열이 여섯으로 정해져 있기 때문이다. 정해진 것을 알고 있으면 처음부터 그 안에서 되는 모양(표 아래의 한 줄)으로 요청할 수 있다.') + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 기록에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/제외_사유.md</code>를 다시 본다. 이 기록을 받아 조치를 승인하는 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 기록의 모양은 완성 폴더와 다를 수 있으므로, 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>빠진 후보에 함께 걸린 감점과 경고가 보이는가</b>S4의 SOP-COOL-11 · 12는 R2에도, S5의 SOP-COOL-12 · 13은 R3에도 걸린다.</li><li><b>남는 후보에 붙은 것이 번호뿐이지 않은가</b>「SOP-COOL-14(R3)」만 보고는 무슨 경고인지 알 수 없다. 결정표를 따로 찾아보아야 한다.</li><li><b>R4의 65 ℃가 어디서 왔는지 이 기록에 있는가</b>S5의 표에는 원문 「인터록 한계 이상이면」만 있고 65라는 수의 출처가 없다.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 「표의 여섯 열은 그대로 두고」와 「결정표는 건드리지 마」를 꼭 넣는다.</p>'
 + write('w8', '무엇이 문제인지, 왜 문제인지, 제외_사유.md의 어느 자리를 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(함께 걸린 감점과 경고)를 고른 경우의 글이다. 완성 폴더의 기록은 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P8, pre=True) + '</details>'
 f'<p style="margin-top:18px">고친 뒤에는 두 가지를 본다. <code>결과/제외_사유.md</code>에서 요청한 줄만 더해졌는가. 6단계에서 맞춰 본 표와 「남는 후보」 줄이 그대로인가. 완성 폴더의 기록에서는 S4에 「{e(xs["S4"]["also"])}」, S5에 「{e(xs["S5"]["also"])}」, S6에 「{e(xs["S6"]["also"])}」이 더해졌다. S4만 예로 들었는데 같은 경우인 S5와 S6에도 줄이 생겼다.</p>'
 + shot('되돌려 준 뒤 Copilot이 제외_사유.md의 바뀐 부분을 보여 주는 화면(더해진 줄이 초록색으로 표시된 화면).')
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다. 되묻지 않고 스스로 정한 것이 있으면 답에 밝혀 두었는지 본다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>정해진 열도 건드려 본다.</b> 7단계에서는 「하면 안 되는 것」을 건드렸다. 이번에는 「정해져 있는 것」이다. 아래를 보내고, 결정표의 열이 열 개 그대로인지, Copilot이 규칙 파일의 어느 줄을 들었는지, 「이번 한 번만」에 어떻게 답했는지를 본다. 열이 하나 늘면 이 표를 읽는 실습 3의 판정 기능이 영향을 받는다.</p>'
  + copy(P7c, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
  + '<p style="margin-top:18px"><b>옮기지 않은 문장을 다시 본다.</b> HM-8.8의 「팬 100 % 연속 운전이 24시간을 넘으면 팬 수명이 줄어든다」는 행이 되지 않았다. 5단계에서 「위험만 알리는 문장은 경고로 옮긴다」고 정했으니 이 문장도 경고 행이 될 수 있다. 행으로 둔다면 대상은 어느 후보이고, 같은 조건의 R2와 함께 맞을 때 표를 읽는 사람은 무엇을 보게 되는가. 두지 않는다면 그 까닭은 무엇인가.</p>'
  '<p><b>60 % 문장의 자리.</b> 「펌프 부하를 60 % 미만으로 설정하지 않는다」는 입력 목록에 값이 없어 표에 들어오지 못했다. 이 조건이 표에 들어오려면 누구에게 무엇을 요청해야 하는가.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 조건 문장을 찾게 한다', '2. 정하고 나올 행 받기', '3. 세 행을 만들어 맞추기', '4. 경계에서 기호 확인하기', '5. 다른 문서로 행 더하기', '6. 제외 사유 남기기', '7. 규칙을 건드려 보기', '8. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>조건 문장 → 결정표</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-03-1-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 조치 조건을 결정표로 옮기기</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
