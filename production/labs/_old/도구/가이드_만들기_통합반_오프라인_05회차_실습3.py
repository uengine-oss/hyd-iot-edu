"""통합반 오프라인 05회차 실습 3 「여러 증거를 비교해 점검 우선순위 결정하기」의 가이드.html 과 찍어_주실_화면.md 를 만든다.
05회차 실습 2의 스크립트에서 스타일과 도우미를 그대로 가져오고 내용만 바꿨다. 저장소 어디에서 실행해도 된다."""
import re, html, json
from pathlib import Path
LAB = Path(__file__).resolve().parent.parent
R = LAB / '통합반_오프라인' / '05회차_실습3_증거_비교_점검_순서'
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
.chg .tree s{color:#ff9a8f}
table.res td code{font-size:12.5px}
.flow.f4{grid-template-columns:repeat(4,1fr)}
.tag{display:inline-block;border-radius:6px;padding:1px 8px;font-size:12.5px;font-weight:800}
.tag.ok{background:var(--ok-soft);color:var(--ok)}.tag.lack{background:#fff1a8;color:#7a5b00}.tag.clash{background:#fdecec;color:#b3261e}.tag.both{background:#efe6ff;color:#5a2fb8}
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
    h = f'<div class="next"><div><small>다음 단계</small><b>{label}</b></div><a data-go="{i}">다음으로 →</a></div>' if label else '<div class="next"><div><small>끝</small><b>남은 것: 증거가 모자란 것과 어긋난 것을 가려 추가 확인을 요청하는 에이전트(에이전트.py), 열두 사례의 증거 비교표와 점검 계획. 다음 실습에서는 설비가 아닌 품질 불량 접수로 같은 원칙(확정되지 않은 원인을 단정하지 않는다)을 다시 쓴다</b></div></div>'
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
css += '@media(max-width:760px){.flow.f4{grid-template-columns:1fr}}'

# ── 요청 글: 모두 기록/의 원문(시작 폴더의 사본에서 실제로 보낸 글)에서 옮긴다.
P1 = P('1_prompt.txt')
P1rich = ('<span class="p-a">이 폴더의 규칙(.github/copilot-instructions.md)과 에이전트.py, 도구.py, 에이전트_정의.json, 온톨로지 폴더의 읽는_법.md, 입력 폴더의 두 파일을 읽어 줘. 그다음 에이전트.py를 고치지 않고 그대로 한 번 실행해서,</span> '
          '<span class="p-b">새 사례 열두 건이 지금 어떻게 나오는지를 사례마다 한 줄인 표(번호, 경보 패턴, 근거 상태, 원인마다의 구분과 증거의 판정)로 적어 줘. 그 표에서, 지금의 결과가 같은 말(가설, UNKNOWN)로 내고 있지만 받아 본 사람이 이어서 할 일은 서로 다른 사례들을 골라 무엇이 어떻게 다른지 말해 줘.</span> '
          '<span class="p-c">이 폴더의 규칙만으로는 정할 수 없는 것이 나오면 정하지 말고, 내가 무엇을 정해 줘야 하는지 물어 줘. 아직 파일은 고치지 마.</span>')
assert re.sub(r'<[^>]+>', '', P1rich) == P1
P2, P3, P4, P6a, P6b, P8, PX = (P(f'{n}_prompt.txt') for n in ('2', '3', '4', '6a', '6b', '8', '여유'))

# ── 시작 폴더의 자료에서 읽는 수
IN = json.loads((R / '시작' / '입력' / '센서_입력.json').read_text(encoding='utf-8'))
n_case = len(IN); assert n_case == 12
pat = {c['번호']: c['경보_패턴'] for c in IN}
rd = {c['번호']: {(r['tag'], r['aggregate']): r for r in c['readings']} for c in IN}
assert rd['N05'][('PS1', 'avg')]['value'] == 161.8 and rd['N05'][('FS1', 'avg')]['value'] == 8.0
assert rd['N08'][('VS1', 'max-min')]['value'] == 0.31 and rd['N08'][('VS1', 'max-min')]['coverage'] == {'samples': 112, 'max_gap_s': 96.4, 'limit_s': 3, 'covered': False} and rd['N08'][('TS1', 'avg')]['value'] == 49.0

# ── 실제로 실행한 결과 파일에서 옮기는 줄
J = lambda p: {x['번호']: x for x in json.loads((R / p).read_text(encoding='utf-8'))}
r0, r4, r7, fin = J('기록/0_결과_고치기_전.json'), J('기록/4_결과.json'), J('기록/7_결과_센서_도구_뺌.json'), J('완성/결과/점검_계획.json')
for k in r0:  # 규칙 6: 지난 실습에서 정한 것은 그대로다
    assert r0[k]['근거_상태'] == fin[k]['근거_상태'] and r0[k]['후보_원인'] == fin[k]['후보_원인'] and r0[k]['호출_기록'] == fin[k]['호출_기록']
    assert r4[k]['추가_확인'] == fin[k]['추가_확인'] and r4[k]['증거_상황'] == fin[k]['증거_상황']
ST = {'SUPPORTED': 's', 'UNKNOWN': 'u', 'UNSUPPORTED': 'x'}
st = lambda v: f'<span class="st {ST[v]}">{v}</span>'
TG = {'충분': 'ok', '부족': 'lack', '충돌': 'clash', '부족과_충돌': 'both'}
tg = lambda v: f'<span class="tag {TG[v]}">{e(v)}</span>'
cnt = {v: sum(1 for c in fin.values() if c['근거_상태'] == v) for v in ST}
assert cnt == {'SUPPORTED': 5, 'UNKNOWN': 6, 'UNSUPPORTED': 1}
sit = {v: [k for k, c in fin.items() if c['증거_상황'] == v] for v in TG}
assert sit == {'충분': ['N01', 'N02', 'N06'], '부족': ['N08', 'N09', 'N12'], '충돌': ['N03', 'N04', 'N05', 'N07', 'N11'], '부족과_충돌': ['N10']}
n_ask = sum(len(c['추가_확인']) for c in fin.values()); assert n_ask == 10
def split3(c):
    out = []
    for g, lab in (('확인됨', '확인됨'), ('가설', '가설'), ('해당_없음', '해당 없음')):
        ns = [e(x['이름']) for x in c['후보_원인'] if x['구분'] == g]
        if ns: out.append(f'<small>{lab}</small> ' + ' · '.join(ns))
    return '<br>'.join(out)
before = ('<table class="res"><thead><tr><th style="width:200px">사례 · 경보 패턴</th><th style="width:130px">근거 상태</th><th>후보 원인의 구분</th></tr></thead><tbody>'
          + ''.join(f'<tr><td class="nw"><b>{k}</b><br><small>{pat[k]}</small></td><td class="nw">{st(c["근거_상태"])}</td><td>{split3(c)}</td></tr>' for k, c in r0.items()) + '</tbody></table>')
unk = [k for k, c in r0.items() if c['근거_상태'] == 'UNKNOWN']; assert unk == ['N04', 'N05', 'N07', 'N08', 'N09', 'N12'] and len(r0['N09']['점검_순서']) == 6 and len(r0['N12']['점검_순서']) == 4

# 증거_비교.md 의 한 절을 그대로 표로 옮긴다
CMP = (R / '완성' / '결과' / '증거_비교.md').read_text(encoding='utf-8')
assert CMP == (R / '기록' / '3_증거_비교.md').read_text(encoding='utf-8')
def cell(s): return re.sub(r'`([^`]*)`', r'<code>\1</code>', e(s).replace('&lt;br&gt;', '<br>'))
def cmptable(*nos):
    out = '<table class="res"><thead><tr><th style="width:130px">원인</th><th style="width:74px">구분</th><th>맞는 증거</th><th>맞지 않는 증거</th><th>확인하지 못한 증거</th></tr></thead><tbody>'
    for no in nos:
        sec = CMP.split(f'## {no}\n')[1].split('\n## ')[0]
        rows = [l for l in sec.splitlines() if l.startswith('| ') and not l.startswith('| 원인')]
        out += f'<tr><td colspan="5" style="background:#f6f8fa"><b>{no}</b> · {pat[no]}</td></tr>'
        for l in rows:
            c = [x.strip() for x in l.strip().strip('|').split(' | ')]; assert len(c) == 5, l
            out += '<tr>' + ''.join(f'<td>{cell(x)}</td>' for x in c) + '</tr>'
    return out + '</tbody></table>'
assert '받은 값 0.31, 비교하지 않음 · 가장 긴 공백 96.4초 · 한도 3초' in CMP

# 4 · 5단계: 완성 폴더의 결과에서 옮기는 표
def asks(c): return '<br>'.join(f'<small>{e(q["상황"])}</small> {e(q["까닭"].split(":")[0] if q["상황"] == "부족" else ("모두 해당 없음" if "모두 해당_없음" in q["까닭"] else "증거가 갈림"))}' for q in c['추가_확인']) or '<small>없음</small>'
def heads(c): return '<br>'.join(f'{p["순번"]}. {e(p["점검"]["내용"].split(" (cause:")[0])}' for p in c['점검_순서'])
SEE = {'N01': '증거 둘이 모두 맞았다. 견줄 것이 남지 않았다',
       'N02': '<b>원인 둘이 함께 확인되었다.</b> 충돌이 아니다. 사전 확률이 큰 순서로 두 줄이다',
       'N03': '<b>같은 값이 두 원인에서 반대로 읽힌다.</b> 팬 진동 0.97은 팬 구동 불량에는 맞고, 쿨러 핀 오염의 「팬은 정상」에는 어긋난다',
       'N04': '과열로 멈춘 사례다. 냉각 효율 74.2는 70 미만이 아니고, 팬은 정상이다',
       'N05': '<b>기준값과 똑같은 값.</b> 유량 8.0은 「8.0 미만」이 아니다',
       'N06': '저압으로 멈춘 사례다. 압력과 유량이 모두 맞았다',
       'N07': '진동 폭 0.27은 맞고, 「유온은 정상」은 53.8이어서 어긋난다',
       'N08': '<b>값은 있는데 믿지 못한다.</b> 0.31을 받았으나 공백이 96.4초다',
       'N09': '<b>값이 묵었다.</b> 최신 유온이 142초 전의 것이다. 점검 순서가 한 줄이다',
       'N10': '<b>부족과 충돌이 함께 있다.</b> 확인된 원인이 있는데도 캐비닛 온도를 읽지 못했고 쿨러 핀 오염의 증거가 갈렸다',
       'N11': '<b>경보는 떴는데 맞는 증거가 없다.</b> 빈 목록 대신 추가 확인 한 줄이 나온다',
       'N12': '<b>견줄 증거가 등록되어 있지 않다.</b> 원인 넷을 한 건으로 묶어 요청한다'}
allt = ('<table class="res" style="font-size:13.5px"><thead><tr><th style="width:112px">사례 · 상태</th><th style="width:112px">추가 확인</th><th style="width:205px">점검 순서</th><th>볼 것</th></tr></thead><tbody>'
        + ''.join(f'<tr><td class="nw"><b>{k}</b><br>{st(c["근거_상태"])}<br>{tg(c["증거_상황"])}</td><td>{asks(c)}</td><td>{heads(c)}</td><td>{SEE[k]}</td></tr>' for k, c in fin.items())
        + '</tbody></table>')
q08 = fin['N08']['추가_확인'][0]; q05 = fin['N05']['추가_확인'][0]
assert q08['상황'] == '부족' and '확인됨, 아님이면 가설(증거가 갈림)' in q08['요청'] and q05['상황'] == '충돌'
def askbox(no, q): return f'<div class="tree" style="white-space:pre-wrap;font-size:13.5px;margin:10px 0"><b>{no} · {e(q["상황"])}</b>\n대상  {e(", ".join(q["대상"]))}\n까닭  {e(q["까닭"])}\n요청  {e(q["요청"])}</div>'
add03 = fin['N03']['추가_확인'][0]['까닭']; assert '확인된 원인 팬 구동 불량' in add03

# 7단계: 허용 목록에서 센서_집계를 빼고 돌린 결과
assert all(c['근거_상태'] == 'UNKNOWN' and c['증거_상황'] == '부족' and len(c['점검_순서']) == 1 for c in r7.values())
tool_less = [k for k, c in r7.items() if c['추가_확인'][0]['까닭'].startswith('읽는 도구 없음')]; assert len(tool_less) == 11 and r7['N12']['추가_확인'][0]['까닭'].startswith('등록된 증거 없음')
q7 = r7['N01']['추가_확인'][0]

# 8단계: 까닭 글이 고치기 전(4차례)과 뒤(완성)에 어떻게 다른가
w0, w1 = r4['N01']['점검_순서'][0]['까닭'], fin['N01']['점검_순서'][0]['까닭']
assert w0.startswith('확인된 원인이어서 부족을 푸는 추가 확인 다음에 둔다') and w1.startswith('확인된 원인이며 이 사례의 첫 점검이다') and not fin['N01']['추가_확인']
w10 = fin['N10']['점검_순서'][1]['까닭']; assert w10.startswith('확인된 원인이어서 앞의 1번(부족을 푸는 추가 확인) 다음에 둔다')
xq = J('기록/여유_결과.json')['N05']['추가_확인'][0]['까닭']; assert '읽은 값(8.0)과 기준값(8.0)이 같음' in xq

choices = '''<table class="res"><thead><tr><th style="width:150px">규칙이 비워 둔 것</th><th>복사 상자에 적힌 답</th><th>다르게 정하려면</th></tr></thead><tbody>
<tr><td><b>무엇이 부족인가</b></td><td><mark>1번 줄</mark> 「확인하지_못함」인 증거가 있는 원인, 그리고 증거가 한 건도 등록되지 않은 원인이다. 까닭은 신선도 초과, 관측 공백 초과, 값 없음, 등록된 증거 없음의 넷으로 나눠 적는다</td><td>「증거가 등록되지 않은 원인은 부족으로 보지 않는다」로 바꾼다. N12는 부족도 충돌도 아니게 되어 「충분」으로 나온다. 원인 넷 가운데 어느 것도 가리지 못했는데 견줄 것이 없다는 말이 된다</td></tr>
<tr><td><b>무엇이 충돌인가</b></td><td><mark>2번 줄</mark> 한 원인의 증거가 「맞음」과 「아님」으로 갈린 경우, 그리고 경보는 떴는데 후보 원인이 모두 「해당_없음」인 경우다. 원인 둘이 함께 확인된 것은 충돌이 아니다</td><td>「원인 둘이 함께 확인된 것도 충돌로 본다」로 바꾼다. N02에 추가 확인이 붙는다. 그런데 두 원인의 증거는 서로 다른 값(냉각 효율과 팬 진동, 캐비닛 온도)을 보므로, 한쪽이 맞는다고 다른 쪽이 틀리지 않는다</td></tr>
<tr><td><b>확인된 원인이 있는 사례</b></td><td><mark>3번 줄</mark> 확인된 원인이 있어도 남은 것대로 적는다. 부족도 충돌도 없을 때만 「충분」이다</td><td>「확인된 원인이 하나라도 있으면 충분」으로 바꾼다. N03과 N10이 충분이 된다. N10에서는 캐비닛 온도를 읽지 못했다는 사실이 「충분」이라는 말에 묻힌다</td></tr>
<tr><td><b>추가 확인 한 건</b></td><td><mark>4번 줄</mark> 부족은 읽을 값마다 한 건(신선도 초과와 등록된 증거 없음은 사례에 한 건), 충돌은 원인마다 한 건이다. 요청에는 무엇을 다시 확인하면 어느 원인의 구분이 갈리는지를 적고, 온톨로지에 없는 담당자나 절차는 적지 않는다</td><td>「증거마다 한 건」으로 바꾼다. N09는 같은 까닭(값이 묵었다)의 요청이 네 건이 된다. 받는 사람이 할 일은 수집이 되살아났는지 보는 것 하나다</td></tr>
<tr><td><b>점검 순서</b></td><td><mark>5번 줄</mark> 부족을 푸는 추가 확인을 맨 앞에, 다음에 확인된 원인, 그다음 충돌인 원인, 마지막에 그 밖의 가설을 둔다. 줄마다 그 차례에 놓은 까닭을 적는다</td><td>「확인된 원인을 맨 앞에 둔다」로 바꾼다. N10에서 팬 구동 불량의 조치가 먼저 보인다. 대신 아직 읽지 못한 값이 있다는 사실이 둘째 줄로 내려간다</td></tr>
</tbody></table>'''

pages = []
# ───────── 준비
pages.append(hero('준비', '<small>통합반 오프라인 5회차 · 실습 3 · 50분</small>증거를 견주어<br>무엇부터 점검할지 정한다',
 '앞 실습에서 만든 에이전트를 그대로 가져왔다. 이번에는 새 사례 열두 건을 넣는다. 값이 다르고, 지난번에 없던 경보(과열 정지, 저압 정지, 고진동 정지)도 들어 있다. 에이전트는 이번에도 확인되지 않은 원인을 「가설」이라고 낸다. 그런데 가설이라는 한마디에는 서로 다른 사정이 섞여 있다. 값을 읽지 못해서 모르는 것과, 값은 읽었는데 증거끼리 어긋나서 모르는 것이다. 이 둘을 가려 사람에게 무엇을 확인해 달라고 할지를 내게 하고, 점검 순서에 그 까닭을 붙인다. 무엇을 부족이라 하고 무엇을 충돌이라 할지는 <b>내가 정한다.</b>',
 [('끝나면 남는 것', '고친 에이전트.py, 사례 열두 건의 증거 비교표와 점검 계획'), ('쓰는 도구', 'VS Code · Copilot 채팅 (GPT-6 Luna)'), ('전제', '앞 실습(원인을 추론하는 에이전트)을 마쳤다'), ('준비에 쓰는 시간', '약 4분')])
+ '<section class="sect"><h2>오늘 만드는 것</h2><p>에이전트를 새로 만들지 않는다. 지난 실습의 판정 방식(맞음 · 아님 · 확인하지 못함, 확인됨 · 가설 · 해당 없음, 근거의 세 가지 상태)은 한 글자도 바꾸지 않고, 그 위에 세 가지를 얹는다.</p>'
  f'<div class="pipe"><div><b>지난 실습의 에이전트</b>도구 넷과 실행 고리. 판정 방식은 그대로 둔다<small>도구.py · 에이전트.py</small></div><span>+</span><div><b>새 사례</b>경보가 뜬 사례 {n_case}건. 값과 경보의 종류가 지난번과 다르다<small>입력/센서_입력.json</small></div><span>→</span><div class="out"><b>견준 결과</b>증거 비교표, 증거 상황과 추가 확인, 까닭이 붙은 점검 순서<small>결과/증거_비교.md · 점검_계획.json · .md</small></div></div>'
  '<h2 style="margin-top:26px">오늘 하는 일의 순서</h2><p>손으로 코드를 쓰는 일은 없다. 요청은 대부분 이 가이드에 준비되어 있어 복사해 보낸다. 내가 할 일은 그 요청이 왜 그렇게 쓰였는지를 읽고, 돌아온 결과가 맞는지 판단하는 것이다.</p>'
  '<div class="flow f4"><div><em>1</em><b>다른 입력을 넣는다</b>새 사례 열두 건을 지금의 에이전트에 그대로 넣어 본다</div><div><em>2</em><b>증거를 견준다</b>후보마다 맞는 증거와 맞지 않는 증거를 나란히 놓는다</div><div><em>3</em><b>부족과 충돌을 가린다</b>모자라거나 어긋나면 단정하지 않고 추가 확인을 요청한다</div><div><em>4</em><b>점검 순서를 정한다</b>먼저 볼 것부터 차례를 매기고 그 까닭을 적는다</div></div>'
  '<p style="margin:18px 0 0">1단계가 첫 칸, 2~3단계가 둘째 칸, 4~5단계가 셋째와 넷째 칸이다. 그 뒤에 세 가지를 더 해 본다. 규칙에 어긋나는 요청을 일부러 보내 보고(6단계), 값을 읽는 도구를 빼고 돌려 보고(7단계), 아쉬운 곳을 되돌려 준다(8단계).</p></section>'
+ do(1, 'explorer', 'VS Code · 탐색기', '받은 폴더 <code>시작</code>을 VS Code로 연다',
 '<p>VS Code의 「파일 → 폴더 열기」에서 <code>시작</code> 폴더를 고른다. 이 폴더를 신뢰하느냐고 물으면 신뢰한다고 답한다. 왼쪽 탐색기에 아래와 같이 보이면 된다.</p>'
 '<div class="stack"><div class="tree" style="margin-bottom:16px">시작/\n├─ <span>.github/</span>\n│  └─ copilot-instructions.md  <i>← 이 폴더의 규칙 (이번 실습의 것)</i>\n├─ <span>온톨로지/</span>                  <i>← 지난 실습과 같다</i>\n├─ <span>입력/</span>\n│  ├─ 센서_입력.json           <i>← 새 사례 12건 (N01~N12)</i>\n│  └─ 입력_설명.md             <i>← 칸의 뜻</i>\n├─ 도구.py                     <i>← 지난 실습에서 만든 도구 넷</i>\n├─ 에이전트.py                 <i>← 지난 실습에서 만든 실행 고리</i>\n├─ 에이전트_정의.json          <i>← 허용 목록에 도구 넷</i>\n└─ <span>결과/</span>                      <i>← 지금은 비어 있다</i></div>'
 '<div><p><b>규칙 파일</b>은 이번 실습에 맞게 바뀌어 있다. 6번이 새로 생긴 줄이다. 지난 실습에서 정한 판정 방식은 바꾸지 않는다고 적혀 있다. 「정해져 있지 않은 것」의 다섯 줄은 2단계에서 내가 채운다.</p><p><b>완성 폴더</b>도 함께 받았다. 이 실습을 끝까지 마친 상태가 들어 있다. 막히면 열어서 내 것과 견준다.</p></div></div>'
 + shot('시작 폴더를 연 VS Code 화면. 왼쪽 탐색기에 .github, 온톨로지, 입력, 결과 네 폴더와 도구.py, 에이전트.py, 에이전트_정의.json이 보이게.'))
+ do(2, 'editor', 'VS Code · 편집기와 종이', '사례 둘을 손으로 먼저 대어 본다',
 '<p><code>입력/센서_입력.json</code>에서 <b>N05</b>와 <b>N08</b>을 찾는다. 두 사례 모두 후보 원인이 하나이고 증거가 둘이다. 아래 표의 빈 칸을 종이에 채운다. 뒤에서 에이전트의 결과가 맞는지를 가리는 사람은 나다.</p>'
 '<table class="res"><thead><tr><th>사례 · 후보 원인</th><th>증거의 기준</th><th>입력에서 볼 줄</th><th>내 판정</th></tr></thead><tbody>'
 '<tr><td class="nw" rowspan="2"><b>N05</b><br>펌프 축 씰 마모</td><td><code>avg(PS1) 120초 lt 165</code></td><td>PS1 · <code>avg</code>의 <code>value</code></td><td>?</td></tr>'
 '<tr><td><code>avg(FS1) 120초 lt 8.0</code></td><td>FS1 · <code>avg</code>의 <code>value</code></td><td>?</td></tr>'
 '<tr><td class="nw" rowspan="2"><b>N08</b><br>팬 베어링 마모</td><td><code>max-min(VS1) 300초 gt 0.2</code></td><td>VS1 · <code>max-min</code>의 <code>value</code>와 <code>coverage</code></td><td>?</td></tr>'
 '<tr><td><code>avg(TS1) 120초 lt 52</code></td><td>TS1 · <code>avg</code>의 <code>value</code></td><td>?</td></tr></tbody></table>'
 + note('두 사례는 같은 처지인가', '지금의 에이전트는 두 사례를 똑같이 「가설 · UNKNOWN」으로 낸다. 그런데 N05는 값을 모두 읽었고, N08은 값 하나를 믿을 수 없다. 이 결과를 받은 사람이 두 설비에서 할 일은 같은가. 이 물음이 오늘의 실습이다.'))
+ nxt(1, '1. 새 사례를 그대로 넣어 본다'))

# ───────── 1단계
pages.append(hero('1단계', '새 사례를<br>그대로 넣어 본다',
 '고치기 전에 지금의 에이전트가 새 사례를 어떻게 내는지부터 본다. 첫마디가 「증거 충돌을 처리하게 고쳐 줘」이면 AI는 무엇이 충돌인지를 스스로 정해 코드에 넣는다. 그래서 첫 요청은 <b>읽고, 그대로 돌려 보고, 같은 말로 뭉쳐 있는 사례를 찾고, 정할 수 없는 것은 물어보라</b>는 요청으로 한다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', '열두 건의 지금 결과와, Copilot이 나에게 묻는 것이 채팅에 있다'), ('아직 바뀌면 안 되는 것', '에이전트.py')])
+ mapbox('chat', '이 단계에서 쓰는 곳', '<p>VS Code 오른쪽의 <b>Copilot 채팅</b> 한 곳이다. 맨 아래 입력 칸에 요청을 붙여넣고 보낸다.</p>')
+ do(1, 'chat', 'Copilot 채팅', '채팅을 열고, 두 가지를 확인한다',
 '<p>VS Code 오른쪽에 Copilot 채팅이 보이지 않으면 Copilot 아이콘을 눌러 연다. 입력 칸 아래에 두 가지가 적혀 있다. 방식은 <b>에이전트</b>, 모델은 <b>GPT-6 Luna</b>인지 본다. 다르면 그 글자를 눌러 바꾼다. 지난 실습의 대화가 남아 있으면 새 대화를 연다.</p>'
 + shot('Copilot 채팅이 열린 VS Code 전체 화면. 입력 칸 아래의 방식(에이전트)과 모델(GPT-6 Luna) 표시가 보이게. 그 두 곳과 새 대화 버튼에 빨간 테두리를 얹는다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸', '아래 요청을 복사해 그대로 보낸다',
 '<p>「복사」를 누르고, 채팅 입력 칸을 한 번 누른 다음 붙여넣고(Ctrl+V) Enter를 누른다. 실행의 허용을 물으면 명령이 <code>python 에이전트.py</code>(또는 <code>python3 …</code>)인지 읽고 허용한다.</p>' + copy(P1, rich=P1rich)
 + parts(('무엇을 읽고 무엇을 하는가', '규칙 파일과 지난 실습의 두 프로그램, 새 입력을 읽게 하고, 고치지 않은 채로 한 번 실행하게 했다. 고치기 전의 결과가 있어야 고친 뒤와 견줄 수 있다.'), ('어떤 모양으로 답하는가', '사례마다 한 줄인 표를 달라고 했다. 그리고 같은 말로 나왔지만 이어서 할 일이 다른 사례를 고르게 했다. 무엇이 문제인지를 AI의 입으로 먼저 듣는다.'), ('하지 말 것', '정할 수 없으면 정하지 말 것, 파일을 고치지 말 것.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 답에서 세 가지를 찾는다',
 '<p>답이 오는 데 2분쯤 걸린다. 문장은 사람마다 다르게 나오므로 옆 사람과 글자가 같을 필요는 없다. 아래는 고치지 않은 에이전트가 낸 결과다(대신 돌린 실행의 결과 파일에서 옮겼다). 내 답의 표와 견준다.</p>' + before
 + shot('위 요청에 대한 Copilot의 답. 열두 건의 표, 「같은 말인데 이어서 할 일이 다른 사례」를 가른 부분, 답의 끝에서 정해 달라고 묻는 부분이 보이게(길면 두 장). 아래 세 곳에 ①②③ 테두리를 얹는다.')
 + find(('UNKNOWN 여섯 건을 몇 갈래로 갈랐는가', f'UNKNOWN은 {", ".join(unk)}의 여섯 건이다. 값을 읽지 못한 것(N08, N09), 값은 읽었는데 증거가 갈린 것(N04, N05, N07), 견줄 증거가 아예 없는 것(N12)으로 갈랐는가. 준비 단계에서 내가 손으로 본 N05와 N08이 서로 다른 갈래에 들어 있는가.'),
        ('SUPPORTED 안에 남은 가설을 짚었는가', 'N03과 N10은 확인된 원인이 있어 SUPPORTED다. 그런데 쿨러 핀 오염이 가설로 남아 있다. 팬 진동 하나의 값이 팬 구동 불량의 기준(0.9 이상)에는 맞고 쿨러 핀 오염의 기준(0.9 미만)에는 어긋나기 때문이라는 데까지 말했는가.'),
        ('정하지 않고 되물은 것', '무엇이 부족이고 무엇이 충돌인지를 스스로 정하지 않고 물었는가. 물음이 몇 묶음인지 세어 둔다. 원인 둘이 함께 확인된 N02, 경보는 떴는데 맞는 증거가 없는 N11을 어떻게 볼지도 물음에 들어 있는지 본다.'))
 + note('되묻는 까닭', '규칙 파일의 「정해져 있지 않은 것」에 다섯 줄을 적어 두고 「요청에 없으면 정하지 말고 묻는다」고 했기 때문이다. 대신 돌린 실행에서는 다섯 줄이 모두 물음으로 돌아왔고, 기준값과 똑같은 값(N05)을 따로 다룰지처럼 규칙에 없던 물음도 함께 왔다.')
 + ifs(('에이전트.py가 바뀌어 버렸다면', '요청의 마지막 문장이 빠진 것이다. 완성 폴더가 아니라 받은 시작 폴더의 <code>에이전트.py</code>를 다시 복사해 덮어쓰고, 요청을 처음부터 다시 보낸다.'),
       ('python을 찾을 수 없다고 나오면', '「python 대신 python3(또는 py)로 실행해 줘」라고 말한다. 그래도 안 되면 강사에게 알린다.')))
+ nxt(2, '2. 비워 둔 것을 내가 정하고, 계획부터 받는다', 0))

# ───────── 2단계
pages.append(hero('2단계', '비워 둔 것을 내가 정하고,<br>계획부터 받는다',
 '온톨로지는 원인마다 증거의 기준을 적어 둘 뿐이다. 증거가 갈린 원인을 어떻게 부를지, 읽지 못한 값이 있을 때 누구에게 무엇을 물을지, 무엇부터 점검할지는 어디에도 없다. 정답이 하나가 아니므로 <b>요청하는 사람이 정한다.</b> 기준은 하나다. 이 결과를 보고 사람이 설비에 손을 댄다. 모자라거나 어긋난 증거를 두고 원인을 단정하지 않는다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '내 결정이 반영된 계획이 채팅에 있다'), ('아직 바뀌면 안 되는 것', '에이전트.py')])
+ do(1, 'chat', '이 화면의 표 → Copilot 채팅', '다섯 빈자리마다 어느 쪽으로 정할지 고른다',
 '<p>답을 지어 쓸 필요는 없다. 아래 표의 가운데 칸이 다음 할 일의 복사 상자에 이미 적혀 있는 답이고, 오른쪽 칸이 다른 선택과 그 선택이 가져오는 것이다. 줄마다 어느 쪽이 내 일터에 맞는지를 고른다. 오른쪽을 고른 줄이 있으면 번호를 기억해 둔다.</p>' + choices
 + note('처음이라면 그대로 보낸다', '완성 폴더의 결과와 뒤 단계의 표는 가운데 칸의 답으로 만든 것이다. 다르게 정하면 내 결과가 그것과 달라지는데, 틀린 것이 아니라 내가 그렇게 정한 것이다. 수업에서 본 근거의 세 가지 상태 가운데 UNKNOWN(확인하지 못함)과 UNSUPPORTED(맞는 근거 없음)가 여기의 부족과 충돌에 가깝다. 다만 오늘은 사례 하나가 아니라 원인 하나하나에 대어 본다.'))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (1단계와 같은 대화)', '고른 답을 보내고, 계획부터 달라고 한다',
 '<p>복사해 입력 칸에 붙여넣는다. 다르게 정한 줄이 있으면 <b>보내기 전에</b> 입력 칸에서 그 번호의 줄만 고쳐 쓴다. 줄을 바꿀 때는 Shift+Enter를 쓴다(Enter는 보내기다).</p>'
 + copy(P2, pre=True, rich=richpre(P2, 'abbc'))
 + parts(('누가 왜 쓰는가', '첫 문단. 결과를 받는 사람과 그 사람이 알아야 하는 것을 말하고, 가장 중요한 것을 한 문장으로 적었다. 이 문장이 있으면 Copilot이 요청에 없는 세부를 그 목적에 맞게 정한다.'), ('빈자리 다섯 가지', '번호를 붙여 한 줄에 결정 하나씩 적었다. 그 아래 문단은 1단계의 답이 물어 온 것 하나(공백 때문에 비교하지 않은 값을 어디에 보일지)에 대한 답이다.'), ('계획 먼저', '마지막 문단. 규칙 파일에 「계획을 먼저 말해 달라는 요청을 받으면 계획만 말한다」는 줄이 있어, 이 말을 들으면 고치지 않고 멈춘다.')))
+ do(3, 'chat', 'Copilot 채팅 · 답', '돌아온 계획에서 네 가지를 찾는다',
 '<p>Copilot은 파일을 고치지 않고 계획을 내놓는다. 「이렇게 고치겠다」와 「이것은 더 정해 달라」가 함께 온다.</p>'
 + shot('2단계 요청에 대한 Copilot의 계획. 에이전트.py에 더할 것, 「이 계획대로면 나올 결과」 표, 「정해 주셔야 하는 것」이 보이게. 아래 네 곳에 테두리를 얹는다.')
 + find(('지난 실습의 판정을 건드리지 않는가', '증거의 판정, 원인의 구분, 근거 상태를 정하는 부분은 그대로 두고 그 옆에 새 것을 더한다고 했는가. 고친 뒤 고치기 전의 결과와 견주겠다고 했는가. 규칙 6번이 요구하는 것이다.'),
        ('나올 결과를 미리 말했는가', '계획대로 만들면 사례마다 증거 상황이 무엇으로 나올지를 표로 미리 보여 주었는가. N05와 N08이 서로 다른 말로 나오는지 본다. 만들기 전에 틀린 곳을 잡을 수 있는 자리다.'),
        ('내가 시키지 않았는데 들어온 일', '예를 들어 「두 번 실행해 결과가 같은지 확인하겠다」, 「사례 번호 하나로도 실행해 보겠다」 같은 단계다. 나쁜 제안은 아니지만 요청한 적이 없다. 할지 말지는 내가 정한다.'),
        ('다시 물어 온 것', '다섯 가지를 정해 주어도 빈자리가 더 나온다. 대신 돌린 실행에서는 다섯을 더 물었다. 그 가운데 하나는 「값을 읽는 도구가 허용 목록에서 빠졌을 때 까닭을 무엇으로 적을지」였다. 내 계획에도 있는지 찾아 둔다. 7단계에서 그 경우를 직접 만든다.'))
 + note('계획부터 받는 까닭', '계획을 받지 않고 바로 고치게 했다면, 이 결정들은 내가 모르는 사이에 내려져 코드에 들어갔을 것이다. 계획은 AI가 무엇을 스스로 정하려 하는지를 미리 보여 준다.')
 + ifs(('계획 없이 파일부터 고쳤다면', '요청의 마지막 문단이 빠진 것이다. 받은 시작 폴더의 <code>에이전트.py</code>로 되돌리고 복사 상자의 글을 처음부터 끝까지 다시 붙여넣는다.'),
       ('되묻는 것이 하나도 없다면', '그대로 다음 단계로 간다. 다만 계획에 내가 정하지 않은 기준(예: 「기준값에 가까우면」의 폭)이 들어 있지 않은지는 읽어 본다.')))
+ nxt(3, '3. 증거를 견주는 표부터 만든다', 1))

# ───────── 3단계
pages.append(hero('3단계', '증거를 견주는<br>표부터 만든다',
 '계획 전체를 한꺼번에 만들게 하지 않는다. 먼저 판단이 들어가지 않는 것부터 만든다. 후보 원인마다 맞는 증거, 맞지 않는 증거, 확인하지 못한 증거를 한 줄에 나란히 놓은 표다. 부족인지 충돌인지를 말하기 전에, 그 말의 바탕이 되는 사실이 <b>한눈에 견주어지는지</b>부터 본다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '결과 폴더에 증거_비교.md가 있다'), ('바뀌면 안 되는 것', '점검_계획.json · 점검_계획.md의 내용')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획에 답하고, 이번에 만들 범위를 정해 준다',
 '<p>계획에 대한 답은 세 마디다. 받을 것과 정해 줄 것, 뺄 것, 이번에 만들 범위다.</p>'
 + copy(P3, pre=True, rich=richpre(P3, 'abc'))
 + parts(('받을 것과 정해 줄 것', '첫 문단. Copilot이 이렇게 읽었다고 밝힌 것은 그대로 받고, 물어 온 다섯에 하나씩 답했다. 내 계획의 물음이 이와 다르면 보내기 전에 번호와 답을 내 것에 맞게 고친다.'), ('뺄 것', '둘째 문단. 시키지 않은 확인 둘을 뺐다. 결과가 맞는지는 내가 본다. 다만 고치기 전과 견주는 일은 남겼다. 규칙 6번을 지켰는지를 가리는 일이기 때문이다.'), ('범위', '셋째 문단. 파일 하나를 쓰는 부분만 더하고 한 번 실행하는 데서 멈추게 한다. 손대지 말 것을 이름으로 적었다.')))
+ do(2, 'chat', 'Copilot 채팅', '허용을 물으면, 무엇을 하려는지 읽고 허용한다',
 '<p>누르기 전에 두 가지를 읽는다. 고치는 파일이 <code>에이전트.py</code> 하나인가. 실행하려는 명령이 <code>python 에이전트.py</code>인가. <code>도구.py</code>나 입력 파일을 고치려 하면 허용하지 않고 왜 필요한지 묻는다.</p>'
 + shot('Copilot이 에이전트.py의 바뀐 부분을 보여 주며 유지할지 묻는 화면 또는 터미널 명령 실행의 허용을 묻는 화면. 파일 이름(에이전트.py)과 명령 글자(python 에이전트.py)가 보이게.'))
+ do(3, 'editor', 'VS Code · 편집기', '표에서 한 줄을 가로로 읽는다',
 '<p><code>결과/증거_비교.md</code>를 열고 미리 보기(Ctrl+Shift+V)로 바꾼다. 아래는 완성 폴더의 같은 파일에서 두 절을 옮긴 것이다. 준비 단계에서 종이에 적은 N08의 답과 견준다.</p>' + cmptable('N08', 'N10')
 + find(('N08: 값이 있었다는 것이 보이는가', '「확인하지 못한 증거」 칸에 받은 값 0.31과 가장 긴 공백 96.4초, 한도 3초가 함께 적혀 있는가. 0.31은 기준 0.2보다 크다. 그래도 맞는 증거 칸에 들어가 있지 않아야 한다. 300초 가운데 96초가 비어 있는 구간의 폭이기 때문이다.'),
        ('N10: 같은 값이 두 줄에서 반대로 놓였는가', '팬 진동 0.95가 팬 구동 불량의 줄에서는 「맞는 증거」에, 쿨러 핀 오염의 줄에서는 「맞지 않는 증거」에 있다. 한 줄씩 따로 볼 때는 보이지 않던 것이 나란히 놓으니 보인다.'),
        ('지난 결과가 그대로인가', 'Copilot의 답에 고치기 전과 견준 결과가 적혀 있는지 본다. 근거 상태와 후보 원인이 열두 건 모두 같다고 했는가. 탐색기에서 <code>결과/점검_계획.md</code>를 열어 「증거 상황」 같은 새 줄이 아직 없는지도 본다.'))
 + ifs(('표가 깨져 보인다면', '미리 보기가 아니라 원문을 보고 있는 것이다. 파일을 연 채로 Ctrl+Shift+V를 누른다.'),
       ('점검_계획 파일까지 바뀌었다면', '「이번에는 증거_비교.md를 쓰는 부분만 더하기로 했어. 점검_계획 두 파일의 내용이 고치기 전과 같아지게 되돌려 줘.」라고 말한다.')))
+ nxt(4, '4. 부족과 충돌을 가려 추가 확인을 낸다', 2))

# ───────── 4단계
pages.append(hero('4단계', '부족과 충돌을 가려<br>추가 확인을 낸다',
 '표로 사실을 견주었으니 이제 그 위에 판단을 얹는다. 사례마다 증거 상황을 한마디로 적고, 사람에게 확인해 달라고 할 것을 한 건씩 내고, 점검 순서를 내가 정한 차례로 다시 짠다. 에이전트가 스스로 풀 수 없는 것을 <b>풀 수 없다고 말하고, 누가 무엇을 보면 풀리는지를 적어 내게</b> 하는 단계다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '결과에 증거 상황, 추가 확인, 까닭이 붙은 점검 순서가 있다'), ('바뀌면 안 되는 것', '판정, 구분, 근거 상태, 증거_비교.md')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '계획의 나머지를 만들게 한다',
 '<p>무엇을 더하는지, 어디까지 고치는지, 끝난 뒤 무엇을 알려 달라는지를 말한다.</p>' + copy(P4, pre=True, rich=richpre(P4, 'abc'))
 + parts(('무엇을 더하는가', '첫 문단. 결과의 칸 셋(증거_상황, 추가_확인, 점검_순서의 까닭)과, 사람이 읽는 md에도 보이게 하라는 것이다.'), ('어디까지 고치는가', '둘째 문단. 지난 실습의 판정과 방금 만든 비교표는 건드리지 않게 했다.'), ('무엇을 확인하고 알리는가', '셋째 문단. 고치기 전과 견주게 했고, 요청 글을 어떤 틀로 적었는지 밝히게 했다. 요청 글은 내가 문장까지 정해 주지 않은 자리여서, 무엇을 스스로 정했는지를 듣는다.')))
+ do(2, 'editor', 'VS Code · 편집기', '준비 단계의 두 사례가 어떻게 갈렸는지 본다',
 '<p><code>결과/점검_계획.md</code>의 미리 보기에서 N05와 N08을 찾는다. 사례마다 「증거 상황」 한 줄과 「추가 확인」이 생겼다. 완성 폴더의 결과에서는 두 사례의 추가 확인이 아래와 같다.</p>' + askbox('N05', q05) + askbox('N08', q08)
 + shot('Copilot이 추가 확인과 점검 순서를 만든 뒤의 답. 사례마다 증거 상황을 적은 표와 「요청 글을 적은 틀」이 보이게.')
 + find(('같은 가설이 다른 말로 나왔는가', 'N05는 「충돌」, N08은 「부족」이다. 고치기 전의 결과에서는 둘 다 「가설 · UNKNOWN」이었다. 근거 상태와 구분은 지금도 그대로다. 그 옆에 한마디가 더 붙었다.'),
        ('요청이 무엇을 가르는지 말하는가', 'N08의 요청에는 그 값이 맞음이면 「확인됨」, 아님이면 「가설(증거가 갈림)」이 된다고 적혀 있다. 확인하러 가는 사람은 자기가 읽어 올 값 하나에 무엇이 걸려 있는지를 안다.'),
        ('지어낸 것이 없는가', '요청에 담당자의 이름이나 부서, 온톨로지에 없는 확인 절차가 적혀 있지 않은가. 규칙 2번과 내가 4번 줄에서 정한 것이다.'),
        ('Copilot이 스스로 정하고 알린 것', '요청 글의 틀을 몇 가지로 나누었다고 했는가. 그리고 지금의 입력으로는 지나가지 않아 실행으로 확인하지 못한 갈래가 있다고 알렸는가. 대신 돌린 실행에서는 「읽는 도구 없음」 갈래를 그렇게 알렸다.'))
 + ifs(('근거 상태나 구분이 바뀌었다면', '어느 사례가 어떻게 달라졌는지를 말하고, 규칙 6번을 들어 되돌리게 한다. 「N05의 펌프 축 씰 마모가 확인됨으로 바뀌었어. 구분을 정하는 부분은 건드리지 않기로 했어.」'),
       ('증거 상황에 다른 말이 나왔다면', '값은 <code>충분</code>, <code>부족</code>, <code>충돌</code>, <code>부족과_충돌</code> 넷뿐이다. 「보류」 같은 다른 말이 보이면 규칙 파일의 「정해져 있는 것」을 들어 고치게 한다.')))
+ nxt(5, '5. 열두 사례로 결과를 맞춰 본다', 3))

# ───────── 5단계
pages.append(hero('5단계', '열두 사례로<br>결과를 맞춰 본다',
 '프로그램이 오류 없이 끝났다는 것은 결과가 맞다는 뜻이 아니다. 열두 건은 서로 다른 경우를 담도록 짜여 있다. 증거가 깨끗이 맞은 경우, 한 원인 안에서 갈린 경우, 값이 없거나 묵은 경우, 둘이 함께 있는 경우, 경보는 떴는데 맞는 증거가 없는 경우다. 경우마다 <b>어느 사례의 어느 줄을 보면 되는지</b>를 따라가며 내 결과를 맞춘다. 맞는지 가리는 일은 AI에게 맡기지 않는다.',
 [('걸리는 시간', '약 6분'), ('이 단계가 끝나면', '부족과 충돌이 내가 정한 대로 갈렸고 점검 순서의 차례가 맞는지를 안다'), ('맞춰 볼 것', '점검_계획.md ↔ 증거_비교.md ↔ 입력의 값')])
+ do(1, 'editor', 'VS Code · 편집기 (좌우로 나란히)', '점검 계획과 비교표를 나란히 놓고 표를 따라 내려간다',
 f'<p><code>결과/점검_계획.md</code>의 미리 보기를 왼쪽에, <code>결과/증거_비교.md</code>의 미리 보기를 오른쪽에 둔다. 아래는 완성 폴더의 결과에서 옮긴 것이고, 2단계의 가운데 칸대로 정했을 때의 값이다. 충분 {len(sit["충분"])}건, 충돌 {len(sit["충돌"])}건, 부족 {len(sit["부족"])}건, 부족과 충돌 {len(sit["부족과_충돌"])}건이고 추가 확인은 모두 {n_ask}건이다. 굵은 글씨가 붙은 사례부터 본다.</p>' + allt
 + shot('점검_계획.md의 미리 보기와 증거_비교.md의 미리 보기를 좌우로 나란히 연 VS Code 화면. 두 쪽 모두 N10이 보이게(왼쪽은 「추가 확인」과 「점검 순서」, 오른쪽은 표의 세 줄).')
 + find(('N10: 차례가 내가 정한 대로인가', '점검 순서가 네 줄이다. 읽지 못한 캐비닛 온도의 추가 확인, 확인된 팬 구동 불량, 증거가 갈린 쿨러 핀 오염, 값을 기다리는 주변 온도 상승의 차례인가. 확인된 원인의 줄에만 즉시 완화 조치가 붙어 있는가.'),
        ('N03: 갈린 까닭이 적혀 있는가', '추가 확인의 까닭 끝에 한 문장이 덧붙어 있다. 완성 폴더의 결과에서는 이렇다. 「' + e(add03.split('갈림. ')[1]) + '」 내가 2번 줄에서 덧붙여 달라고 한 것이다. 이 문장이 있으면 받은 사람은 팬부터 본다.'),
        ('N09와 N12: 줄을 늘어놓지 않았는가', 'N09는 증거 넷을 하나도 읽지 못했고 N12는 견줄 증거가 없다. 점검 순서가 한 줄씩인가. 고치기 전의 결과에서는 N09가 여섯 줄, N12가 네 줄이었다. 줄 수가 많다고 알려 주는 것이 많은 것은 아니다.'),
        ('근거 상태의 수가 그대로인가', f'SUPPORTED {cnt["SUPPORTED"]}건, UNKNOWN {cnt["UNKNOWN"]}건, UNSUPPORTED {cnt["UNSUPPORTED"]}건이다. 1단계에서 본 표와 같아야 한다. UNKNOWN 여섯 건이 이제 충돌 셋과 부족 셋으로 나뉘어 보인다.')))
+ do(2, 'editor', 'VS Code · 편집기', '프로그램 안에 사례에 맞춘 분기가 없는지 찾아본다',
 '<p><code>에이전트.py</code>를 열고 찾기(Ctrl+F)로 <code>N05</code>, <code>N10</code>, <code>8.0</code>, <code>0.9</code>, <code>cause:</code>를 차례로 찾는다. 하나도 나오지 않아야 한다. 나온다면 열두 건에 맞춰 결과를 꿰어 맞춘 것이고, 내일 들어오는 열세 번째 사례에서는 틀린다.</p>'
 + ifs(('결과가 내가 정한 것과 다르다면', '어느 사례의 무엇이 어떻게 다른지를 말한다. 「N02의 증거 상황이 충돌로 나왔어. 원인 둘이 함께 확인된 것은 충돌이 아니라고 정했어. 그 경우만 고치고 다시 실행해 줘.」'),
       ('사례 번호가 코드에 적혀 있다면', '「에이전트.py에 N10이 직접 적혀 있어. 특정 사례에만 맞춘 분기는 규칙 3번에 어긋나. 그 부분을 모든 사례에 같은 조건으로 고쳐 줘.」')))
+ nxt(6, '6. 규칙을 일부러 건드려 본다', 4))

# ───────── 6단계
pages.append(hero('6단계', '규칙을<br>일부러 건드려 본다',
 '추가 확인은 번거롭다. 현장에 사람을 보내야 하고 답이 올 때까지 판단이 멈춘다. 그래서 급할 때 누구나 「그 정도면 맞다고 치자」, 「값은 있으니 그냥 써」라고 말하게 된다. 그 말을 지금 일부러 해 본다. 규칙이 정말 막아 주는지는 어긋나는 일을 시켜 보아야 안다. 보내기 전에, 해 줄지 멈출지 먼저 짐작해 둔다.',
 [('걸리는 시간', '약 5분'), ('이 단계가 끝나면', 'Copilot이 멈춘 까닭이 규칙 파일의 어느 줄인지 안다'), ('바뀌면 안 되는 것', '입력, 에이전트.py, 결과')])
+ do(1, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '기준값에 걸린 사례를 확인됨으로 올려 달라고 해 본다',
 '<p>N05의 유량은 기준값과 똑같은 8.0이다. 0.1만 낮았어도 확인됨이었다. 추가 확인 없이 끝내고 싶다는 그럴듯한 요청이다.</p>'
 + copy(P6a, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + shot('위 요청에 Copilot이 결과를 바꾸지 않고 규칙을 들어 멈춘 답. 어느 규칙 때문인지 말하는 부분과, 대신 할 수 있는 방법을 제안하는 부분에 테두리를 얹는다.')
 + find(('결과가 그대로인가', '<code>결과/점검_계획.md</code>에서 N05의 펌프 축 씰 마모가 「가설」 그대로인지 본다.'),
        ('어느 규칙을 들었는가', '답에 규칙의 번호나 문장이 적혀 있다. 몇 가지를 들었는지 세어 둔다. 「이번만」이라는 말에 어떻게 답했는지도 본다.'),
        ('확인됨으로 올리면 무엇이 달라지는지 말했는가', '구분이 바뀌면 붙는 조치도 바뀐다. 대신 돌린 실행에서는 확인됨이 되면 즉시 완화 조치 셋이 「확인된 원인의 조치」로 붙고, 그 가운데 하나에는 금지 문구가 있다는 것까지 짚었다. 구분 하나가 현장의 손을 움직인다.'),
        ('멈추기만 했는가', '안 된다고만 하지 않고, 규칙 안에서 같은 목적을 이루는 길(예: 값이 기준값과 같다는 사실을 까닭에 덧붙인다)을 내놓았는가.')))
+ do(2, 'chat', 'Copilot 채팅 · 입력 칸 (같은 대화)', '묵은 값을 그냥 쓰게 입력을 고쳐 달라고 해 본다',
 '<p>N09는 값이 모두 들어 있다. 신선도만 넘었다. 입력의 한 글자만 바꾸면 원인이 나온다.</p>'
 + copy(P6b, 'Copilot에게 보낼 요청 (규칙에 어긋난다)')
 + '<p style="margin-top:18px">답이 오면 <code>입력/센서_입력.json</code>에서 N09의 <code>freshness</code>를 찾아 <code>"ok": false</code> 그대로인지 본다.</p>')
+ do(3, 'editor', 'VS Code · 편집기', '규칙 파일에서 그 줄을 찾는다',
 '<p><code>.github/copilot-instructions.md</code>를 연다. Copilot을 멈추게 한 줄을 내 눈으로 찾는다.</p>'
 '<ul class="ask"><li><b>첫째 요청</b>「하면 안 되는 것」 절에서 비교를 어떻게 하라고 적은 줄, 그리고 지난 실습에서 정한 것을 어떻게 하라고 적은 줄이다. 증거가 어긋난 원인을 어떻게 하지 말라고 적혀 있는가. 각각 몇 번인가.</li><li><b>둘째 요청</b>같은 절의 다른 두 줄이다. 입력 폴더를 어떻게 다루라고 적혀 있는가. 입력에 없는 것을 어떻게 하라고 적혀 있는가. 각각 몇 번인가.</li><li><b>두 답에 함께 나온 줄</b>「요청을 받아도 바꾸지 않고, 이번만이라는 예외도 두지 않는다」는 줄이다. 이 줄이 없으면 AI는 「이번만 예외라고 확인해 주시면 하겠다」고 길을 열어 두기 쉽다.</li></ul>'
 '<p>내가 찾은 줄이 Copilot이 답에서 든 것과 같은지 견준다.</p>'
 + note('수업에서 본 장면이 여기에 있다', '두 요청을 들어주었다면 결과에는 확인된 원인이 하나씩 늘었을 것이다. 겉모습은 증거가 모두 맞았을 때와 같아서, 받아 보는 사람은 차이를 알 수 없다. 값이 들어 있다는 것과 그 값을 믿을 수 있다는 것은 다르다. 신선도와 비교의 방향은 그것을 가르는 약속이고, 급하다는 말로는 풀리지 않는다.')
 + ifs(('멈추지 않고 고쳐 버렸다면', '입력이 바뀌었다면 받은 시작 폴더의 같은 파일을 복사해 덮어쓴다. 그다음 규칙 파일을 다시 읽고 방금 한 일이 규칙에 맞는지 말해 달라고 한다. 이 일이 있었다는 것을 강사에게 알린다.'),
       ('「이번만 예외라고 말해 주면 하겠다」고 한다면', '오늘은 예외를 주지 않는다. 규칙 파일은 잠금장치가 아니라 약속이어서, 요청하는 사람이 예외를 주면 풀린다. 예외를 줄 권한이 나에게 있는지를 먼저 따져야 한다.')))
+ nxt(7, '7. 값을 읽는 도구를 빼고 돌려 본다', 5))

# ───────── 7단계
pages.append(hero('7단계', '값을 읽는 도구를 빼고<br>돌려 본다',
 '지금까지는 증거가 일부만 모자란 경우를 보았다. 이번에는 전부 모자라게 만든다. 허용 목록에서 센서 값을 읽는 도구를 내 손으로 빼고 그대로 실행한다. 에이전트는 후보와 기준은 알지만 값은 하나도 읽지 못한다. 이때 <b>가장 흔한 원인을 적어 내는가, 열두 건 모두에 추가 확인을 내는가.</b> Copilot에게 시키는 일은 없다.',
 [('걸리는 시간', '약 4분'), ('이 단계가 끝나면', '증거가 전부 모자랄 때의 결과를 보았고, 허용 목록은 원래대로 돌아와 있다'), ('끝에 꼭 할 일', '허용 목록을 되돌리고 다시 실행한다')])
+ do(1, 'editor', 'VS Code · 편집기', '허용 목록에서 <code>센서_집계</code>를 내 손으로 뺀다',
 '<p><code>에이전트_정의.json</code>을 연다. <code>도구</code> 목록에서 <code>"센서_집계",</code> 한 줄을 지우고 저장한다(Ctrl+S). 이 목록은 사람이 고치는 것이다. 지난 실습에서는 내가 한 줄씩 더했고, 오늘은 한 줄을 뺀다.</p>'
 '<div class="chg"><div class="tree">고치기 전\n"도구": [\n  "원인_후보",\n  "증거_기준",\n  <s>"센서_집계",</s>\n  "조치_방법"\n]</div><div class="tree">고친 뒤\n"도구": [\n  "원인_후보",\n  "증거_기준",\n  "조치_방법"\n]</div></div>')
+ do(2, 'editor', 'VS Code · 터미널', '터미널에서 직접 실행한다',
 '<p>메뉴의 「터미널 → 새 터미널」을 연다(Ctrl+`). 아래 한 줄을 입력하고 Enter를 누른다. 아무 글자 없이 끝나면 된 것이다.</p>'
 '<div class="tree">python 에이전트.py</div>'
 '<p style="margin-top:14px"><code>결과/점검_계획.md</code>를 다시 연다. 대신 돌린 실행에서는 열두 건이 모두 아래처럼 바뀌었다.</p>'
 '<table class="res"><thead><tr><th>볼 것</th><th>도구가 넷일 때</th><th>센서_집계를 뺐을 때</th></tr></thead><tbody>'
 f'<tr><td><b>근거 상태</b></td><td>SUPPORTED {cnt["SUPPORTED"]} · UNKNOWN {cnt["UNKNOWN"]} · UNSUPPORTED {cnt["UNSUPPORTED"]}</td><td><mark>UNKNOWN {len(r7)}</mark></td></tr>'
 f'<tr><td><b>증거 상황</b></td><td>충분 {len(sit["충분"])} · 충돌 {len(sit["충돌"])} · 부족 {len(sit["부족"])} · 부족과 충돌 {len(sit["부족과_충돌"])}</td><td><mark>부족 {len(r7)}</mark></td></tr>'
 f'<tr><td><b>추가 확인의 까닭</b></td><td>신선도 초과, 관측 공백 초과, 값 없음, 등록된 증거 없음, 증거가 갈림</td><td><mark>읽는 도구 없음 {len(tool_less)}건</mark>, 등록된 증거 없음 1건(N12)</td></tr>'
 f'<tr><td><b>점검 순서</b></td><td>사례마다 한 줄에서 네 줄</td><td>사례마다 추가 확인 한 줄</td></tr>'
 f'<tr><td><b>N01의 호출 기록</b></td><td>{len(fin["N01"]["호출_기록"])}건</td><td>{len(r7["N01"]["호출_기록"])}건 (센서_집계를 부른 줄이 없다)</td></tr></tbody></table>'
 + askbox('N01', q7)
 + shot('에이전트_정의.json에서 센서_집계를 뺀 뒤 터미널에서 python 에이전트.py를 실행한 VS Code 화면. 왼쪽에 고친 json, 아래에 터미널, 오른쪽에 결과 md의 N01(증거 상황 부족, 추가 확인 「읽는 도구 없음」)이 보이게.')
 + find(('지어내지 않았는가', 'N01은 방금 전까지 쿨러 핀 오염이 확인된 사례였다. 값을 읽지 못하자 「가설」로 내려갔고, 사전 확률이 0.6으로 가장 큰데도 확인된 것처럼 적지 않았다.'),
        ('다른 길로 읽지 않았는가', '도구가 목록에 없다고 입력 파일을 직접 열어 값을 읽지 않았다. 호출 기록에 <code>센서_집계</code>가 한 줄도 없는지 본다. 규칙 4번이다.'),
        ('까닭이 사실대로인가', '값이 묵은 것도 아니고 없는 것도 아니다. 읽을 길이 없었다. 까닭이 「신선도 초과」나 「값 없음」이 아니라 「읽는 도구 없음」으로 적혀 있는가. 2단계에서 Copilot이 물었고 3단계에서 내가 정해 준 것이다.')))
+ do(3, 'editor', 'VS Code · 편집기와 터미널', '허용 목록을 되돌리고 다시 실행한다',
 '<p><code>에이전트_정의.json</code>에서 지운 줄을 되살린다(Ctrl+Z를 누르거나 <code>"증거_기준",</code> 아래에 <code>"센서_집계",</code>를 다시 적는다). 저장하고 터미널에서 <code>python 에이전트.py</code>를 한 번 더 실행한다. <code>결과/점검_계획.md</code>의 N01이 다시 「충분」인지 본다.</p>'
 + ifs(('오류가 나며 멈췄다면', '쉼표가 남았거나 빠진 것이다. 목록의 마지막 항목 뒤에는 쉼표가 없어야 하고, 그 앞의 항목들 뒤에는 있어야 한다. 위의 「고친 뒤」와 한 글자씩 견준다.'),
       ('python을 찾을 수 없다고 나오면', '<code>python3 에이전트.py</code> 또는 <code>py 에이전트.py</code>로 실행한다.')))
+ nxt(8, '8. 아쉬운 곳을 찾아 되돌려 준다', 6))

# ───────── 8단계
pages.append(hero('8단계', '아쉬운 곳을 찾아,<br>무엇이 왜 문제인지 말한다',
 '차례와 판정이 정한 대로 나왔더라도 받아 보는 사람의 눈으로 읽으면 아쉬운 곳이 보인다. N01을 본다. 점검 순서가 한 줄뿐인데 그 까닭이 「확인된 원인이어서 부족을 푸는 추가 확인 다음에 둔다」로 시작한다. 이 사례에는 추가 확인이 없다. 차례를 정한 규칙을 그대로 옮겨 적다 보니 그 사례에 없는 것을 말하고 있다. 이때 <b>어떻게 말하느냐</b>에 따라 돌아오는 것이 달라진다. 오늘 내 말로 직접 쓰는 요청은 이 한 번이다.',
 [('걸리는 시간', '약 7분'), ('이 단계가 끝나면', '에이전트.py의 한 곳이 내 요청대로 바뀌어 있다')])
+ '<section class="sect"><h2>같은 문제, 두 가지 말</h2><div class="vs"><div class="bad"><b>막연하게</b><q>N01 점검 순서의 까닭이 좀 이상해. 고쳐 줘.</q>무엇이 이상한지 AI는 모른다. 대신 돌린 실행에서는 「어디가 이상한지 말씀이 없어서 짐작한 두 군데를 고쳤다」며 까닭 글 전체의 짜임을 바꿨다. 내가 생각한 곳이 그 둘 가운데 있었는지, 생각하지 않은 곳까지 바뀌었는지를 다시 읽어 가려야 한다.</div>'
  '<div class="good"><b>구체적으로</b><q>N01의 점검 순서는 한 줄뿐인데 그 까닭이 \'확인된 원인이어서 부족을 푸는 추가 확인 다음에 둔다\'로 시작해. 이 사례에는 추가 확인이 없어서, 받아 본 사람은 없는 추가 확인을 찾게 돼. 까닭의 첫 문장은 실제로 앞에 놓인 줄이 있을 때만 그 줄을 들고, 없으면 이 사례의 첫 점검이라고 적어 줘. 까닭 글을 만드는 부분만 고치고 차례와 추가_확인, 판정하는 부분은 건드리지 마.</q>요청한 곳만 바뀌고, 무엇으로 바뀔지를 내가 정했다.</div></div>'
  '<div class="four"><div><b>무엇이</b>추가 확인이 없는 사례의 까닭이 추가 확인을 든다</div><div><b>왜</b>받아 본 사람이 없는 추가 확인을 찾게 된다</div><div><b>어디를</b>에이전트.py에서 점검 순서의 까닭 글을 만드는 부분</div><div><b>어디까지</b>차례, 추가 확인, 판정, 증거_비교.md는 그대로</div></div>'
  + note('막연한 말이 더 위험한 까닭', '막연하게 말해도 AI는 무언가를 고쳐 온다. 그리고 그 결과는 그럴듯하다. 문제는 내가 무엇을 원했는지를 내가 정하지 않았다는 데 있다. 오늘 내내 한 일(비워 둔 것을 내가 정한다)을 되돌려 줄 때에도 똑같이 한다.') + '</section>'
+ do(1, 'editor', 'VS Code · 편집기', '내 결과에서 아쉬운 곳 하나를 고른다',
 '<p><code>결과/점검_계획.md</code>를 다시 본다. 이 계획을 받아 현장에서 점검하는 사람의 눈으로 읽는다. 아래에서 골라도 되고 스스로 찾아도 된다. 내 결과의 모양은 완성 폴더와 다를 수 있으므로, 내 파일에 실제로 있는 문제를 고른다.</p>'
 '<ul class="ask"><li><b>까닭이 그 사례에 없는 것을 말하지 않는가</b>N01의 첫 줄. 위의 「구체적으로」가 이 경우다.</li><li><b>충돌의 요청이 함께 움직이는 것을 말하는가</b>N03의 요청은 쿨러 핀 오염만 놓고 「팬 진동이 0.9 미만으로 바뀌면 확인됨」이라고 적는다. 그런데 그 값이 그렇게 바뀌면 이미 확인된 팬 구동 불량이 풀린다. 그 사실이 요청에 없다.</li><li><b>어느 사례부터 볼지가 보이는가</b>파일이 사례 번호 순서로 이어진다. 열두 건을 받은 사람이 추가 확인이 걸린 사례를 먼저 찾으려면 끝까지 내려가야 한다. 맨 위에 무엇이 있으면 좋은가.</li></ul>')
+ do(2, 'chat', '이 화면의 글 칸 → Copilot 채팅 (같은 대화)', '네 가지를 넣어 되돌려 준다',
 '<p>무엇이, 왜, 어디를, 어디까지. 네 문장이면 된다. 아래 칸에 쓰고 「내가 쓴 글 복사」를 눌러 채팅에 붙여넣는다. 글만 바꾸는 요청이면 「차례와 추가_확인, 판정하는 부분은 건드리지 마」를 꼭 넣는다.</p>'
 + write('w8', '무엇이 문제인지, 왜 문제인지, 에이전트.py의 어느 부분을 고칠지, 건드리지 말 곳을 적는다.')
 + '<details><summary>글이 나오지 않을 때 그대로 보내도 되는 요청</summary><p style="font-size:15px;color:var(--sub);margin:10px 0 0">첫째 거리(까닭이 없는 것을 말한다)를 고른 경우의 글이다. 완성 폴더의 결과는 이 글을 보내 만든 것이다. 보내기 전에 네 가지가 어느 문장에 있는지 짚어 본다.</p>' + copy(P8, pre=True) + '</details>'
 '<p style="margin-top:18px">고친 뒤에는 두 가지를 본다. <code>에이전트.py</code>에서 요청한 부분만 바뀌었는가. 5단계에서 맞춰 본 증거 상황과 점검 순서의 차례가 그대로인가. 완성 폴더의 결과에서는 까닭이 아래와 같이 바뀌었다.</p>'
 '<div class="tree" style="white-space:pre-wrap;font-size:13.5px">N01 1번 · 고치기 전\n' + e(w0) + '\n\n<b>N01 1번 · 고친 뒤</b>\n' + e(w1) + '\n\n<b>N10 2번 · 고친 뒤</b>\n' + e(w10) + '</div>'
 + shot('되돌려 준 뒤 Copilot이 에이전트.py의 바뀐 부분을 보여 주는 화면(바뀐 줄이 초록색으로 표시된 화면).')
 + ifs(('요청하지 않은 곳까지 바뀌었다면', '「어디까지」가 빠졌거나 흐릿했던 것이다. 바뀐 곳을 들어 원래대로 돌려 달라고 한다. Copilot이 스스로 한 가지를 더 바꾸고 답에 밝혔다면, 받을지 되돌릴지를 내가 정해 답한다.'),
       ('Copilot이 되물었다면', '요청에 정하지 않은 것이 있었다는 뜻이다. 물음에 답하면 된다.')))
+ '<section class="sect"><h2>시간이 남으면</h2>'
  '<p><b>기준값과 똑같은 값이라는 사실을 까닭에 덧붙인다.</b> 6단계에서 Copilot은 N05를 확인됨으로 올리지 않는 대신 규칙 안의 길을 내놓았다. 그 가운데 하나를 실제로 시킨다. 「가깝다」는 폭은 온톨로지에 없으므로 두지 않고, 값이 같은지만 본다. 아래를 보내고 N05의 추가 확인에서 까닭이 어떻게 바뀌는지 본다. 대신 돌린 실행에서는 끝에 이 문장이 붙었다. 「' + e(xq.split('갈림. ')[1]) + '」</p>'
  + copy(PX)
  + '<p style="margin-top:18px"><b>한 건만 실행해 본다.</b> 터미널에서 <code>python 에이전트.py N10</code>을 실행하면 결과 세 파일에 무엇이 남는가. 열두 건의 결과로 되돌리려면 어떻게 실행하면 되는가.</p>'
  '<p><b>추가 확인에 답이 왔다면.</b> N10의 캐비닛 온도를 다시 재어 값이 들어왔다고 하자. 그 값은 어디에 들어가야 하고, 누가 넣어야 하는가. 6단계의 둘째 요청에 Copilot이 내놓은 길을 다시 읽어 본다. N11의 메모에는 「같은 시간대에 금형을 바꾸느라 부하가 낮았다」고 적혀 있다. 에이전트는 메모를 판정에 쓰지 않는다. 추가 확인을 받은 사람은 이 메모를 어떻게 쓰겠는가.</p></section>'
+ nxt(None, None, 7))

names = ['준비', '1. 새 사례를 그대로 넣기', '2. 정하고 계획 받기', '3. 증거 비교표 만들기', '4. 부족과 충돌 가리기', '5. 열두 사례로 맞추기', '6. 규칙을 건드려 보기', '7. 도구를 빼고 돌리기', '8. 되돌려 주기']
assert len(names) == len(pages)
bar = '<div class="bar"><div class="bar-in"><b>증거를 견주어 점검 순서를 정한다</b><div class="track">' + ''.join(f'<i data-go="{i}" title="{n}"></i>' for i, n in enumerate(names)) + '</div><span id="pos"></span></div></div>'
js = '''<script>
const KEY='hyd-off-05-3-';const names=''' + json.dumps(names, ensure_ascii=False) + ''';const t=document.getElementById('toast');let k;
function say(m){t.textContent=m;clearTimeout(k);k=setTimeout(()=>t.textContent='',4000)}
function go(i,scroll){i=Math.max(0,Math.min(names.length-1,+i||0));document.querySelectorAll('.step').forEach((s,j)=>s.classList.toggle('on',j===i));document.querySelectorAll('.track i').forEach((d,j)=>{d.className=j<i?'done':j===i?'now':''});document.getElementById('pos').textContent=names[i]+' · 전체 8단계';history.replaceState(null,'','#'+i);if(scroll)window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go,true)));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const el=document.getElementById(b.dataset.copy);const text=(el.value??el.textContent).trim();if(!text){say('아직 쓴 글이 없습니다. 먼저 내 말로 써 보세요.');el.focus();return}
 try{await navigator.clipboard.writeText(text);say('복사했습니다. Copilot 채팅 입력 칸에 붙여넣고 Enter를 누르세요.')}catch(e){if(el.select)el.select();else{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r)}say('글을 선택해 두었습니다. Ctrl+C로 복사하세요.')}}));
document.querySelectorAll('[data-draft]').forEach(a=>{try{a.value=localStorage.getItem(KEY+a.dataset.draft)||''}catch(e){}a.addEventListener('input',()=>{try{localStorage.setItem(KEY+a.dataset.draft,a.value)}catch(e){}})});
go(location.hash.slice(1));
</script>'''
doc = f'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>실습 가이드 · 여러 증거를 비교해 점검 우선순위 결정하기</title><style>{css}</style></head><body>{bar}<main class="page">' + ''.join(f'<article class="step">{p}</article>' for p in pages) + f'</main><div id="toast" role="status" aria-live="polite"></div>{js}</body></html>'
(R / '가이드.html').write_text(doc, encoding='utf-8')
(R / '찍어_주실_화면.md').write_text('# 찍어 주실 화면\n\n가이드의 빗금 상자 번호와 같다. VS Code 창을 1440 × 900쯤으로 맞춰 찍으면 가이드에 그대로 들어간다.\n\n' + '\n'.join(f'{i+1}. {d}' for i, d in enumerate(shots)) + '\n', encoding='utf-8')
print(len(doc), len(shots), doc.count('<textarea'))
