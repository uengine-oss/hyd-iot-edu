"""결과 화면 그리기 — 실행한 기능이 돌려준 블록(실제 결과)을 output/result.html 한 장으로 그린다. 제공 코드 — 바꾸지 않는다.

순수 HTML · CSS · 작은 자바스크립트와 파이썬 표준 라이브러리만 쓴다(서버 · 설치 · 인터넷 없음). 그림은 직접 배치한 SVG다.
블록 종류: verdict(맨 위 결론) · graph(노드와 관계 그림) · gather(여럿이 하나로 모이는 그림) · cards(카드) · bars(개수 막대) · pair(나란히) · link(단추)
           · table · counts · compare · diff · source · note · error.
"""
import html
import json
import re

FOLD = 30          # 이보다 행이 많은 표는 접어 두고 「모두 보기」로 편다

# 클래스(종류)마다 색 하나 — 어느 화면에서나 같은 색이다. 한국어 이름과 레이블 이름을 같은 색에 둔다.
# 색은 종류를 가르는 작은 띠와 점에만 쓴다(글자는 늘 먹색). 차례는 색각이 달라도 이웃한 색이 갈리도록 정해 둔 것이라 바꾸지 않는다.
KIND_COLORS = [
    (('설비', 'Asset'), '#2a78d6'), (('구성 요소', 'Component'), '#eb6834'), (('센서', 'Sensor'), '#1baf7a'),
    (('실물', 'Unit'), '#eda100'), (('부품', 'Part'), '#e87ba4'), (('물리량', 'Quantity', '상태 변수'), '#008300'),
    (('공급사', 'Supplier'), '#6250d6'), (('원자료 표',), '#898781'),
]
SPARE = ['#e34948', '#898781']
STATE_WORD = {'ok': '맞음', 'warn': '볼 곳 있음', 'bad': '다름', 'info': '결과'}


def e(x):
    return html.escape(str(x))


def color(kind, seen={}):
    for names, c in KIND_COLORS:
        if kind in names:
            return c
    if kind not in seen:
        seen[kind] = SPARE[min(len(seen), len(SPARE) - 1)]      # 정해 둔 색을 다 쓰면 나머지는 회색 하나(색을 지어내지 않는다)
    return seen[kind]


def text_w(s, size):
    """글자 너비 어림 — 한글 · 한자는 글자 크기만큼, 그 밖은 0.6배."""
    return sum(size if ord(ch) > 0x2E80 else size * 0.6 for ch in str(s))


def clip(s, limit=30):
    s = str(s)
    return s if len(s) <= limit else s[:limit - 1] + '…'


def token(c):
    """띄어쓰기 없는 짧은 값(숫자 · 식별자)은 칸 안에서 꺾지 않게 표시한다."""
    s = str(c)
    return ' class="k"' if s and len(s) <= 20 and not any(ch.isspace() for ch in s) else ''


def chips(text, other=None):
    """「 · 」로 이은 값을 조각 배지로. other를 주면 그쪽에 없는 조각을 눈에 띄게 한다."""
    parts = [x.strip() for x in str(text).split('·') if x.strip()]
    if not parts:
        return '<span class="none">(없음)</span>'
    have = None if other is None else {x.strip() for x in str(other).split('·')}
    return ''.join(f'<span class="chip{" off" if have is not None and p not in have else ""}">{e(p)}</span>' for p in parts)


def aligned(expected, actual):
    """기대 답과 실제 답의 조각을 같은 차례로 놓는다 — 같은 값이 같은 자리에 오고, 실제에 빠진 값은 그 자리에 빈 칸, 기대에 없던 값은 뒤에 눈에 띄게."""
    want = [x.strip() for x in str(expected).split('·') if x.strip()]
    have = [x.strip() for x in str(actual).split('·') if x.strip()]
    def key(v):      # 35와 35.0은 같은 값으로 맞춘다(견줌과 같은 잣대)
        try:
            return format(float(v), 'g')
        except ValueError:
            return v
    left, right, rest = '', '', list(have)
    for w in want:
        hit = next((x for x in rest if key(x) == key(w)), None)
        if hit is not None:
            rest.remove(hit)
            left += f'<span class="chip">{e(w)}</span>'
            right += f'<span class="chip">{e(hit)}</span>'
        else:
            left += f'<span class="chip off">{e(w)}</span>'
            right += f'<span class="chip gap" title="실제 답에 없는 값">{e(w)}</span>'
    right += ''.join(f'<span class="chip off">{e(x)}</span>' for x in rest)
    return left or NONE, right or NONE


def grid(columns, rows, marks=None, compare_rows=False):
    big = len(rows) > FOLD
    head = '<tr>' + ''.join(f'<th>{e(c)}</th>' for c in columns) + '</tr>'
    body = ''
    for i, r in enumerate(rows):
        st = marks[i] if marks else ''
        body += f'<tr data-st="{e(st)}">' + ''.join(f'<td class="st st-{e(str(c).split(" ")[0])}">{e(c)}</td>' if (marks and j == 1) else f'<td{token(c)}>{e(c)}</td>'
                                                    for j, c in enumerate(r)) + '</tr>'
    tools = '<input class="f" placeholder="글자로 거르기">' if len(rows) > 8 else ''
    if big:
        tools += f'<button class="t more">모두 보기</button> <small>{len(rows)}행 가운데 {FOLD}행만 보임</small>'
    if compare_rows:
        tools += '<button class="t only">같음 줄 숨기기</button>'
    return f'<div class="tbl">{tools}<table><thead>{head}</thead><tbody>{body}</tbody></table></div>'


# ───────────── 노드와 관계 그림 ─────────────
def layers(nodes, links, columns):
    """노드마다 왼쪽에서 몇째 줄에 둘지. columns(종류 차례)를 주면 그 차례, 없으면 관계 방향을 따라 시작 쪽이 왼쪽."""
    if columns:
        return {n['id']: (n['col'] if 'col' in n else columns.index(n['kind']) if n['kind'] in columns else len(columns)) for n in nodes}
    level = {n['id']: n.get('col', 0) for n in nodes}
    for _ in range(len(nodes)):
        moved = False
        for l in links:
            if l['a'] != l['b'] and level[l['b']] < level[l['a']] + 1 and level[l['a']] + 1 < len(nodes):
                level[l['b']] = level[l['a']] + 1
                moved = True
        if not moved:
            break
    return level


def svg_graph(b):
    nodes = b['nodes']
    known = {n['id'] for n in nodes}
    links = [l for l in b['links'] if l['a'] in known and l['b'] in known]
    if not nodes:
        return '<p class="empty">그릴 노드가 없습니다.</p>'
    level = layers(nodes, links, b.get('columns'))
    used = sorted(set(level.values()))
    level = {k: used.index(v) for k, v in level.items()}
    cols = [[n for n in nodes if level[n['id']] == c] for c in range(len(used))]
    near = {}
    for l in links:
        near.setdefault(l['a'], []).append(l['b'])
        near.setdefault(l['b'], []).append(l['a'])
    place = {}
    for sweep in (cols, cols[::-1], cols):      # 이웃의 높이에 맞춰 줄 안의 차례를 정한다(관계가 덜 엇갈리게)
        for col in sweep:
            if place:
                def middle(n):
                    seen = [place[m] for m in near.get(n['id'], []) if m in place and level[m] != level[n['id']]]
                    return sum(seen) / len(seen) if seen else place.get(n['id'], 0.5)
                col.sort(key=middle)
            for i, n in enumerate(col):
                place[n['id']] = (i + 0.5) / len(col)
    main, small = 18, 15.5
    size = {}
    for n in nodes:
        w = max(text_w(clip(n['text']), main), text_w(clip(n.get('sub', ''), 36), small)) + 36
        size[n['id']] = (max(84, w + text_w(n.get('badge', ''), 15) + (18 if n.get('badge') else 0)), 60 if n.get('sub') else 44)
    step = max(h for _, h in size.values()) + 14
    per_edge = len(links) <= 16
    gap_text = {}
    for l in links:
        if l.get('text'):
            gap_text.setdefault((min(level[l['a']], level[l['b']]), max(level[l['a']], level[l['b']])), []).append(l['text'])
    widest = max([text_w(t, 14.5) for ts in gap_text.values() for t in ts] or [0])
    if not per_edge:
        widest = max([text_w(' · '.join(dict.fromkeys(ts)), 15.5) for ts in gap_text.values()] or [0])
    col_w = [max(size[n['id']][0] for n in col) for col in cols]
    gap = max(120, widest + 46)
    if len(cols) > 1:      # 그림이 화면 폭을 넘어 글자가 줄어들지 않게, 줄 사이를 관계 이름이 들어갈 만큼까지만 좁힌다
        gap = max(widest + 18, min(gap, (1420 - sum(col_w) - 24) / (len(cols) - 1)))
    top = 52 if not per_edge else 22
    height = max(len(col) for col in cols) * step + top + 14
    x, pos = 12, {}
    col_x = []
    for c, col in enumerate(cols):
        col_x.append(x)
        free = height - top - 14
        for i, n in enumerate(col):
            w, h = size[n['id']]
            pos[n['id']] = (x, top + free * (i + 0.5) / len(col) - h / 2, w, h)
        x += col_w[c] + gap
    width = x - gap + 12 + (60 if any(level[l['a']] == level[l['b']] for l in links) else 0)
    drawn = all(n.get('at') for n in nodes)      # 그림 도구가 준 자리가 있으면 그 자리대로 놓는다(가장 가까운 두 노드가 겹치지 않을 만큼 늘려서)
    if drawn:
        per_edge = True
        xs, ys = [n['at'][0] for n in nodes], [n['at'][1] for n in nodes]
        need = 1.0
        for i, a in enumerate(nodes):
            for c in nodes[i + 1:]:
                dx, dy = abs(a['at'][0] - c['at'][0]), abs(a['at'][1] - c['at'][1])
                wide, tall = (size[a['id']][0] + size[c['id']][0]) / 2 + 24, 50
                need = max(need, min(wide / dx if dx else 9e9, tall / dy if dy else 9e9))
        need = min(need, 2.4)
        for n in nodes:
            w, h = size[n['id']]
            pos[n['id']] = ((n['at'][0] - min(xs)) * need + 12, (n['at'][1] - min(ys)) * need + 16, w, h)
        width = max(px + w for px, _, w, _ in pos.values()) + 12
        height = max(py + h for _, py, _, h in pos.values()) + 16
    out = [f'<svg class="g" viewBox="0 0 {width:.0f} {height:.0f}" style="max-width:{width:.0f}px" role="img">',
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#a8a69c"/></marker>'
           '<marker id="ahh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2a78d6"/></marker>'
           '<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#d03b3b"/></marker></defs>']
    if not per_edge:      # 관계가 많으면 이름을 줄 사이 머리에 한 번만 적는다
        for (a, c), texts in sorted(gap_text.items()):
            if c == a + 1:
                mid = col_x[a] + col_w[a] + gap / 2
                out.append(f'<text class="gh" x="{mid:.0f}" y="24" text-anchor="middle">{e(" · ".join(dict.fromkeys(texts)))} →</text>')
    labels = []
    for l in links:
        ax, ay, aw, ah = pos[l['a']]
        bx, by, bw, bh = pos[l['b']]
        mark = l.get('mark', '')
        if drawn:      # 가운데에서 가운데로 곧게, 상자 가장자리에서 끊는다
            cx1, cy1, cx2, cy2 = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
            dx, dy = cx2 - cx1, cy2 - cy1
            cut = lambda w, h: min((w / 2 + 3) / abs(dx) if dx else 9e9, (h / 2 + 3) / abs(dy) if dy else 9e9, 0.5)
            t1, t2 = cut(aw, ah), cut(bw, bh)
            x1, y1, x2, y2 = cx1 + dx * t1, cy1 + dy * t1, cx2 - dx * t2, cy2 - dy * t2
            d = f'M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}'
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2
        elif level[l['a']] != level[l['b']]:
            forward = level[l['a']] < level[l['b']]
            x1, y1, x2, y2 = (ax + aw, ay + ah / 2, bx - 3, by + bh / 2) if forward else (ax, ay + ah / 2, bx + bw + 3, by + bh / 2)
            points = []
            for c in range(min(level[l['a']], level[l['b']]) + 1, max(level[l['a']], level[l['b']])):      # 건너뛰는 줄의 노드를 가리지 않게 그 줄의 빈 틈으로 지난다
                xc = col_x[c] + col_w[c] / 2
                yc = y1 + (y2 - y1) * (xc - x1) / (x2 - x1)
                boxes = sorted((pos[n['id']][1], pos[n['id']][1] + pos[n['id']][3]) for n in cols[c])
                if any(top_ - 8 < yc < bottom + 8 for top_, bottom in boxes):
                    free = [boxes[0][0] - 12, boxes[-1][1] + 12] + [(a_[1] + b_[0]) / 2 for a_, b_ in zip(boxes, boxes[1:])]
                    points.append((xc, min(free, key=lambda v: abs(v - yc))))
            points = [(x1, y1)] + (points if forward else points[::-1]) + [(x2, y2)]
            d = f'M{x1:.0f},{y1:.0f}' + ''.join(f' C{(p[0] + q[0]) / 2:.0f},{p[1]:.0f} {(p[0] + q[0]) / 2:.0f},{q[1]:.0f} {q[0]:.0f},{q[1]:.0f}' for p, q in zip(points, points[1:]))
            lx, ly = (points[-2][0] + points[-1][0]) / 2, (points[-2][1] + points[-1][1]) / 2
        else:      # 같은 줄 안의 관계는 오른쪽으로 돌아 들어간다
            x1, y1, x2, y2 = ax + aw, ay + ah / 2, bx + bw + 3, by + bh / 2
            bend = max(x1, x2) + 46
            d = f'M{x1:.0f},{y1:.0f} C{bend:.0f},{y1:.0f} {bend:.0f},{y2:.0f} {x2:.0f},{y2:.0f}'
            lx, ly = bend - 10, (y1 + y2) / 2
        head = {'hit': 'ahh', 'bad': 'ahb'}.get(mark, 'ah')
        out.append(f'<path class="l {e(mark)}" data-a="{e(l["a"])}" data-b="{e(l["b"])}" d="{d}" marker-end="url(#{head})"/>')
        if l.get('text') and (per_edge or abs(level[l['a']] - level[l['b']]) != 1) and not (drawn and abs(x2 - x1) + abs(y2 - y1) < text_w(l['text'], 12) + 30):
            w = text_w(l['text'], 14.5) + 16
            labels.append(f'<g class="ll {e(mark)}" data-a="{e(l["a"])}" data-b="{e(l["b"])}"><rect x="{lx - w / 2:.0f}" y="{ly - 13:.0f}" width="{w:.0f}" height="26" rx="4"/>'
                          f'<text x="{lx:.0f}" y="{ly + 5:.0f}" text-anchor="middle">{e(l["text"])}</text></g>')
    out += labels
    for n in nodes:
        px, py, w, h = pos[n['id']]
        mark = n.get('mark', '')
        tip = [['종류', n['kind']]] + [[str(k), v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)] for k, v in (n.get('props') or {}).items()]
        g = [f'<g class="n {e(mark)}" data-id="{e(n["id"])}" data-tip="{e(json.dumps(tip, ensure_ascii=False))}" tabindex="0">']
        g.append(f'<rect class="p" x="{px:.0f}" y="{py:.0f}" width="{w:.0f}" height="{h:.0f}" rx="7"/>')
        g.append(f'<rect class="band" x="{px + 6:.0f}" y="{py + 7:.0f}" width="6" height="{h - 14:.0f}" rx="3" fill="{color(n["kind"])}"/>')
        left = px + 24
        g.append(f'<text class="t" x="{left:.0f}" y="{py + (h / 2 + 6 if not n.get("sub") else 25):.0f}">{e(clip(n["text"]))}</text>')
        if n.get('sub'):
            g.append(f'<text class="s" x="{left:.0f}" y="{py + 48:.0f}">{e(clip(n["sub"], 36))}</text>')
        if n.get('badge'):
            g.append(f'<text class="bt" x="{px + w - 10:.0f}" y="{py + (h / 2 + 5 if not n.get("sub") else 25):.0f}" text-anchor="end">{e(n["badge"])}</text>')
        g.append('</g>')
        out.append(''.join(g))
    out.append('</svg>')
    kinds = list(dict.fromkeys(n['kind'] for n in nodes))
    legend = '<div class="legend">' + ''.join(f'<span><i style="background:{color(k)}"></i>{e(k)}</span>' for k in kinds)
    marks = {n.get('mark') for n in nodes} | {l.get('mark') for l in links}
    for m, word in (('ask', '물은 값'), ('hit', '따라간 길'), ('bad', '볼 곳'), ('new', '새로 생김'), ('gone', '사라짐'), ('dim', '둘레의 다른 대상')):
        if m in marks:
            legend += f'<span><i class="m-{m}"></i>{e((b.get("marks") or {}).get(m, word))}</span>'
    return legend + '<small>노드에 마우스를 올리면 속성</small></div><div class="gbox">' + ''.join(out) + '</div>'


# ───────────── 블록 하나 그리기 ─────────────
def chip_of(c):
    if isinstance(c, dict):
        dot = f'<i class="kd" style="background:{color(c["kind"])}"></i>' if c.get('kind') else ''
        return f'<span class="chip {e(c.get("mark", ""))}">{dot}{e(c["text"])}' + (f'<small>{e(c["sub"])}</small>' if c.get('sub') else '') + '</span>'
    return f'<span class="chip">{e(c)}</span>'


NONE = '<span class="none">(없음)</span>'


def render_block(b, previous=None, current=None):
    k = b['kind']
    title = f'<h3>{e(b["title"])}</h3>' if b.get('title') else ''
    tail = f'<p class="note">{e(b["note"])}</p>' if b.get('note') else ''
    if k == 'verdict':
        return (f'<div class="verdict v-{e(b["state"])}"><em><i></i>{STATE_WORD.get(b["state"], "결과")}</em><strong>{e(b["text"])}</strong>'
                + (f'<span>{e(b["detail"])}</span>' if b.get('detail') else '') + '</div>')
    if k == 'note':
        if b.get('fold'):      # 그림과 같은 내용의 원문 글은 접어 둔다
            return f'<details class="fold"><summary>{e(b["fold"])} <small>눌러서 펴기</small></summary><pre class="raw">{e(b["text"])}</pre></details>'
        return f'<p class="note">{e(b["text"])}</p>'
    if k == 'error':
        return f'<div class="err"><b>{e(b.get("title") or "확인 필요")}</b>{e(b["text"])}</div>'
    if k == 'link':
        return f'<a class="btn" href="{e(b["url"])}" target="_blank" rel="noopener">{e(b["text"])} <span>↗</span></a>' + tail
    if k == 'source':
        return title + '<div class="src">' + '\n'.join(f'<b>{n}</b>{e(t)}' for n, t in b['lines']) + '</div>'
    if k == 'graph':
        return title + svg_graph(b) + tail
    if k == 'pair':
        sides = [render_block(x) for x in b['items']]
        wide = any(int(m) > 680 for s in sides for m in re.findall(r'<svg class="g" viewBox="0 0 (\d+) ', s))      # 반 칸에 넣으면 글자가 작아지는 그림은 위아래로 놓는다
        return title + f'<div class="pair{" stack" if wide else ""}">' + ''.join(f'<div>{s}</div>' for s in sides) + '</div>' + tail
    if k == 'gather':
        heads = b['heads']
        rows = ''
        for r in b['rows']:
            rows += (f'<div class="gl">{"".join(chip_of(c) for c in r.get("left", [])) or NONE}</div><div class="ga">→</div>'
                     f'<div class="gm {e(r.get("mark", ""))}">{chip_of(r["mid"])}</div>')
            if len(heads) > 2:
                rows += f'<div class="ga">→</div><div class="gr">{"".join(chip_of(c) for c in r.get("right", [])) or NONE}</div>'
        head = (f'<div class="gh2 gl">{e(heads[0])}</div><div></div><div class="gh2">{e(heads[1])}</div>'
                + (f'<div></div><div class="gh2">{e(heads[2])}</div>' if len(heads) > 2 else ''))
        return title + f'<div class="gather c{len(heads)}">{head}{rows}</div>' + tail
    if k == 'cards':
        out = ''
        for c in b['items']:
            lines = ''.join(f'<li><span>{e(x[0])}</span>{chips(x[1]) if x[1] != "" else ""}</li>' if isinstance(x, (list, tuple)) else f'<li>{e(x)}</li>' for x in c.get('lines', []))
            style = ''
            icon = {'ok': '<i class="dot ok"></i>', 'bad': '<i class="dot bad"></i>', 'warn': '<i class="dot warn"></i>', 'lock': LOCK, 'open': UNLOCK}.get(c.get('icon'), '')
            if c.get('kind'):
                icon += f'<i class="kd" style="background:{color(c["kind"])}"></i>'
            out += (f'<div class="card {e(c.get("state", ""))}"{style}><div class="ch">{icon}<b>{e(c["title"])}</b>'
                    + (f'<span class="badge {e(c.get("state", ""))}">{e(c["badge"])}</span>' if c.get('badge') else '') + '</div>'
                    + (f'<p>{e(c["text"])}</p>' if c.get('text') else '') + (f'<ul>{lines}</ul>' if lines else '') + '</div>')
        return title + f'<div class="cards{" wide" if b.get("wide") else ""}">{out}</div>' + tail
    if k == 'bars':
        top = max([1] + [v for _, a, c in b['items'] for v in (a, c)])
        rows = ''
        for name, a, c in b['items']:
            rows += (f'<div class="bn">{e(name)}</div><div class="bb"><i class="a" style="width:{100 * a / top:.1f}%"></i><em>{e(a)}</em></div>'
                     f'<div class="bb"><i class="b" style="width:{100 * c / top:.1f}%"></i><em>{e(c)}</em></div>'
                     f'<div class="bs {"same" if a == c else "diff"}">{"같음" if a == c else ("+" if c > a else "") + str(c - a)}</div>')
        return title + f'<div class="bars"><div></div><div class="bh"><i class="a"></i>{e(b["heads"][0])}</div><div class="bh"><i class="b"></i>{e(b["heads"][1])}</div><div></div>{rows}</div>' + tail
    if k == 'table':
        body = grid(b['columns'], b['rows']) if b['rows'] else '<p class="empty">행 없음 (0행)</p>'
        if b.get('fold'):
            return f'<details class="fold"><summary>{e(b["title"])} <small>{len(b["rows"])}행 · 눌러서 펴기</small></summary>{body}{tail}</details>'
        return title + body + tail
    if k == 'counts':
        if b.get('fold'):
            return f'<details class="fold"><summary>{e(b["title"])} <small>{len(b["items"])}항목 · 눌러서 펴기</small></summary>{grid(["항목", "개수"], b["items"])}{tail}</details>'
        if len(b['items']) <= 8:
            return title + '<div class="stats">' + ''.join(f'<div><b>{e(v)}</b><span>{e(n)}</span></div>' for n, v in b['items']) + '</div>' + tail
        return title + grid(['항목', '개수'], b['items']) + tail
    if k == 'compare':
        marks = [r['state'] for r in b['rows']]
        tally = ''.join(f'<span class="tally t-{e(s.split(" ")[0])}"><b>{marks.count(s)}</b>{e(s)}</span>' for s in ('같음', '다름', '실제 없음', '기대 밖') if marks.count(s))
        head = '<tr><th>견줌</th><th>' + e('질문 · 입력 · 항목' if b['key'] == '짝' else b['key']) + '</th>' + ''.join(f'<th>{e(c)} — 기대</th><th>{e(c)} — 실제</th>' for c in b['columns']) + '</tr>'
        body = ''
        for r in b['rows']:
            st = r['state']
            mark = '✓' if st == '같음' else '✗' if st == '다름' else '?'
            if b.get('ordered'):      # 차례까지 견주는 표는 적힌 차례 그대로
                cells = ''.join(f'<td>{chips(x, y) if st == "다름" else chips(x)}</td><td>{chips(y, x) if st == "다름" else chips(y)}</td>' for x, y in r['cells'])
            else:
                cells = ''.join('<td>{}</td><td>{}</td>'.format(*aligned(x, y)) for x, y in r['cells'])
            body += (f'<tr data-st="{e(st)}"><td class="st st-{e(st.split(" ")[0])}"><i class="dot"></i>{e(st)}</td>'
                     f'<td class="key">{"".join(f"<span>{e(p.strip())}</span>" for p in r["key"].split("|") if p.strip())}</td>{cells}</tr>')
        tools = ('<input class="f" placeholder="글자로 거르기">' if len(b['rows']) > 8 else '') + '<button class="t only">같음 줄 숨기기</button>'
        return (title + f'<div class="tallies">{tally or "<span class=tally>견줄 행 없음</span>"}</div>'
                f'<div class="tbl cmp">{tools}<table><thead>{head}</thead><tbody>{body}</tbody></table></div>'
                + (f'<details class="hint"><summary>견주는 법</summary><p class="note">{e(b["note"])}</p></details>' if b.get('note') else ''))
    if k == 'diff':
        if not b['rows']:
            return title + f'<div class="calm"><i class="dot ok"></i>늘어남 · 사라짐 · 값 바뀜 없음 <small>(같은 항목 {b["same"]}개)</small></div>' + tail
        return title + f'<p class="note">같은 항목 {b["same"]}개</p>' + grid(['항목', '바뀜', '전', '후'], b['rows'], [r[1] for r in b['rows']]) + tail
    raise ValueError(f'모르는 블록 종류 {k!r}')


LOCK = '<svg class="lock" viewBox="0 0 24 24"><rect x="4" y="10.5" width="16" height="11" rx="2.5"/><path d="M7.5 10.5V7.5a4.5 4.5 0 0 1 9 0v3" fill="none" stroke-width="2.4"/></svg>'
UNLOCK = '<svg class="lock un" viewBox="0 0 24 24"><rect x="4" y="10.5" width="16" height="11" rx="2.5"/><path d="M7.5 10.5V7.5a4.5 4.5 0 0 1 8.6-1.8" fill="none" stroke-width="2.4"/></svg>'

CSS = ':root{--page:#f7f7f5;--surface:#fff;--ink:#0b0b0b;--ink2:#33322f;--muted:#5c5b57;--line:#dddcd5;--line2:#b4b3aa;--wash:#efeee9;--accent:#1f6fd0;--good:#0a8f0a;--goodtext:#006300;--warn:#e89b00;--crit:#cc3333;\n--sans:"Segoe UI","Malgun Gothic",system-ui,-apple-system,sans-serif;--mono:Consolas,"Cascadia Mono","SFMono-Regular",Menlo,"Malgun Gothic",monospace}\n*{box-sizing:border-box}\nbody{margin:0;background:var(--page);color:var(--ink);font:18px/1.6 var(--sans);-webkit-font-smoothing:antialiased}\nmain{max-width:1560px;margin:auto;padding:28px 36px 64px}\nheader{margin-bottom:22px}header small{color:var(--muted);font-size:15px}\nh1{font-size:21px;font-weight:600;margin:0 0 16px;color:var(--ink2)}\nh3{font-size:20px;font-weight:650;margin:0 0 16px;color:var(--ink)}\nsection{margin:16px 0;padding:24px 28px;background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:auto}\nsection.plain{background:none;border:0;padding:0 2px;margin:14px 0}\n.dot{display:inline-block;flex:none;width:12px;height:12px;border-radius:50%;background:var(--line2)}\n.dot.ok{background:var(--good)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--crit)}\n.verdict{padding:4px 0 4px 22px;border-left:5px solid var(--line2)}\n.verdict em{display:flex;align-items:center;gap:8px;font-style:normal;font-size:16px;font-weight:650;color:var(--ink2)}\n.verdict em i{width:12px;height:12px;border-radius:50%;background:var(--accent)}\n.verdict strong{display:block;font-size:38px;font-weight:700;line-height:1.25;letter-spacing:-.02em;margin-top:2px}\n.verdict span{display:block;font-size:20px;color:var(--ink2);margin-top:6px}\n.v-ok{border-color:var(--good)}.v-ok em i{background:var(--good)}.v-warn{border-color:var(--warn)}.v-warn em i{background:var(--warn)}\n.v-bad{border-color:var(--crit)}.v-bad em i{background:var(--crit)}.v-info{border-color:var(--accent)}\n.note{color:var(--ink2);white-space:pre-wrap;margin:14px 0 0;font-size:16.5px;line-height:1.6;max-width:68em}.empty{color:var(--muted);margin:4px 0;font-size:16px}.none{color:var(--muted)}\n.err{border-left:5px solid var(--crit);padding:4px 0 4px 22px;white-space:pre-wrap;font-size:20px;overflow-wrap:anywhere;color:var(--ink)}\n.err b{display:flex;align-items:center;gap:8px;font-size:16px;color:var(--ink2);margin-bottom:6px}.err b::before{content:"";width:12px;height:12px;border-radius:50%;background:var(--crit)}\n.btn{display:inline-flex;gap:8px;padding:9px 16px;border-radius:6px;border:1.5px solid var(--ink2);background:var(--surface);color:var(--ink);text-decoration:none;font-weight:650;font-size:16.5px}\n.btn span{color:var(--muted)}.btn:hover{background:var(--wash)}\n.legend{display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center;margin:0 0 14px;font-size:16px;color:var(--ink2)}.legend span{display:inline-flex;align-items:center;gap:8px}\n.legend i{width:6px;height:18px;border-radius:3px;display:inline-block}.legend small{color:var(--muted);margin-left:auto;font-size:14.5px}\n.legend i.m-ask{background:none;border:2.5px solid var(--ink);width:18px;height:14px;border-radius:4px}.legend i.m-hit{background:var(--accent);height:3.5px;width:26px;border-radius:2px}\n.legend i.m-bad{background:none;border:2.5px solid var(--crit);width:18px;height:14px;border-radius:4px}.legend i.m-new{background:none;border:2.5px solid var(--good);width:18px;height:14px;border-radius:4px}\n.legend i.m-gone{background:none;border:2px dashed var(--line2);width:18px;height:14px;border-radius:4px}.legend i.m-dim{background:var(--line)}\n.gbox{overflow:auto}svg.g{width:100%;height:auto;display:block;margin:auto}\nsvg.g .l{fill:none;stroke:#9a998f;stroke-width:1.4}svg.g .l.hit{stroke:var(--accent);stroke-width:2.6}\nsvg.g .l.bad{stroke:var(--crit);stroke-width:2}svg.g .l.dim{opacity:.4}svg.g .l.gone{stroke-dasharray:5 4}\nsvg.g .ll rect{fill:var(--surface);stroke:none}svg.g .ll text{font:600 14.5px var(--mono);fill:var(--ink2)}svg.g .ll.hit text{fill:var(--accent)}svg.g .ll.dim{opacity:.5}\nsvg.g .gh{font:600 15.5px var(--mono);fill:var(--ink2)}\nsvg.g .n{cursor:default;outline:none}svg.g .n .p{fill:var(--surface);stroke:#8f8e85;stroke-width:1.3}\nsvg.g .n .t{fill:var(--ink);font:650 18px var(--mono)}svg.g .n .s{fill:var(--ink2);font:15.5px var(--sans)}svg.g .n .bt{fill:var(--ink2);font:600 15px var(--mono)}\nsvg.g .n.ask .p{stroke:var(--ink);stroke-width:3}svg.g .n.bad .p{stroke:var(--crit);stroke-width:3}svg.g .n.new .p{stroke:var(--good);stroke-width:3}\nsvg.g .n.dim{opacity:.45}svg.g .n.gone .p{stroke-dasharray:5 4}svg.g .n.gone .t{fill:var(--muted);text-decoration:line-through}svg.g .n.gone .band{opacity:.35}\nsvg.g .n:hover .p,svg.g .n:focus .p{stroke:var(--ink)}\nsvg.g.on .n:not(.hot),svg.g.on .l:not(.hot),svg.g.on .ll:not(.hot){opacity:.18}\n#tip{position:fixed;z-index:9;pointer-events:none;background:var(--ink);color:#fff;border-radius:6px;padding:10px 14px;font:15px/1.6 var(--mono);max-width:520px;display:none;overflow-wrap:anywhere}\n#tip b{color:#c9c7bd;font-weight:normal;margin-right:8px}\n.pair{display:grid;grid-template-columns:1fr 1fr;gap:0}.pair.stack{grid-template-columns:1fr}.pair>div{padding:4px 24px 4px 0;min-width:0}.pair>div+div{border-left:1px solid var(--line);padding:4px 0 4px 24px}\n.pair.stack>div+div{border-left:0;border-top:1px solid var(--line);padding:22px 0 4px;margin-top:18px}.pair h3{font-size:17px;color:var(--ink2);margin-bottom:10px}\n.chip{display:inline-flex;align-items:baseline;gap:7px;margin:3px 6px 3px 0;padding:2px 9px;border-radius:5px;background:var(--wash);font:17px/1.5 var(--mono);white-space:nowrap;color:var(--ink)}\n.chip small{font:14.5px var(--sans);color:var(--ink2)}.chip.off{background:#fde9e9;box-shadow:inset 0 0 0 2px var(--crit);font-weight:650}.chip.past{color:var(--muted);text-decoration:line-through}.chip.gap{background:none;box-shadow:inset 0 0 0 2px var(--crit);color:transparent;border-radius:5px;background-image:repeating-linear-gradient(135deg,#f6caca 0 3px,transparent 3px 7px)}\n.chip .kd{width:5px;height:16px;border-radius:2px;align-self:center;flex:none}\n.gather{display:grid;gap:10px 16px;align-items:center}.gather.c3{grid-template-columns:minmax(0,1.3fr) 26px auto 26px minmax(0,1fr)}.gather.c2{grid-template-columns:minmax(0,1fr) 26px minmax(0,1fr)}\n.gather .gl{text-align:right}.gather .ga{color:var(--muted);font-size:20px;text-align:center}.gather .chip{white-space:normal}\n.gather .gm .chip{font-weight:650;font-size:18px;padding:4px 12px}.gather .gh2{font-size:15px;color:var(--ink2);font-weight:650}.gather .gm.bad .chip{box-shadow:inset 0 0 0 2px var(--crit)}\n.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.cards.wide{grid-template-columns:repeat(auto-fit,minmax(460px,1fr))}\n.card{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 18px;background:var(--surface)}\n.card .ch{display:flex;align-items:center;gap:11px;font-size:18px}.card .ch b{flex:1;min-width:0;overflow-wrap:anywhere;font-weight:600}.card .kd{width:5px;height:20px;border-radius:2px;flex:none}\n.card p{margin:8px 0 0;color:var(--ink2);font-size:16.5px;overflow-wrap:anywhere}\n.card ul{list-style:none;margin:8px 0 0;padding:0}.card li{padding:5px 0 3px;font-size:16.5px;overflow-wrap:anywhere}.card li>span:first-child{display:block;color:var(--muted);font-size:14.5px}.card .chip{white-space:normal}\n.badge{flex:none;font:600 15.5px var(--mono);color:var(--ink2)}.badge.bad{color:var(--crit)}\n.lock{flex:none;width:20px;height:20px;fill:none;stroke:var(--goodtext);stroke-width:2.2}.lock rect{fill:var(--goodtext)}.lock.un{stroke:var(--crit)}.lock.un rect{fill:var(--crit)}\n.bars{display:grid;grid-template-columns:minmax(170px,auto) 1fr 1fr 84px;gap:10px 20px;align-items:center;font-size:16.5px}\n.bars .bh{font-size:15px;color:var(--ink2);font-weight:650}.bars .bh i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:7px}\n.bars i.a{background:#9a998f}.bars i.b{background:var(--accent)}.bars .bn{font-family:var(--mono);white-space:nowrap;color:var(--ink)}\n.bars .bb{display:flex;align-items:center;gap:9px;height:16px}.bars .bb i{display:block;height:14px;border-radius:0 4px 4px 0;min-width:2px}.bars .bb em{font:normal 600 16px var(--mono);color:var(--ink)}\n.bars .bs{font-size:15.5px;color:var(--ink2);display:flex;align-items:center;gap:7px}.bars .bs::before{content:"";width:10px;height:10px;border-radius:50%;background:var(--good)}.bars .bs.diff::before{background:var(--crit)}.bars .bs.diff{font-family:var(--mono);color:var(--ink);font-weight:650}\n.stats{display:flex;flex-wrap:wrap;gap:0}.stats div{flex:1 1 140px;padding:2px 20px 2px 0;margin-right:20px;border-right:1px solid var(--line)}.stats div:last-child{border:0}\n.stats b{display:block;font-size:30px;font-weight:700;line-height:1.25}.stats span{color:var(--ink2);font:15.5px var(--mono);overflow-wrap:anywhere}\n.calm{font-size:18px;color:var(--ink);display:flex;align-items:center;gap:10px}.calm small{color:var(--muted);font-size:15px}\n.tallies{display:flex;gap:22px;flex-wrap:wrap;margin:0 0 12px}.tally{display:inline-flex;align-items:baseline;gap:8px;font-size:17px;color:var(--ink2)}.tally b{font-size:26px;font-weight:700;color:var(--ink)}\n.tally::before{content:"";width:11px;height:11px;border-radius:50%;background:var(--line2);align-self:center}.t-같음::before{background:var(--good)}.t-다름::before,.t-실제::before{background:var(--crit)}.t-기대::before{background:var(--warn)}\n.tbl{overflow:auto}table{border-collapse:collapse;width:100%;font-size:17px}th,td{padding:10px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}\nth{cursor:pointer;white-space:nowrap;color:var(--ink2);font-size:15px;font-weight:650;border-bottom:2px solid var(--line2)}td{overflow-wrap:break-word;word-break:keep-all}td.k{white-space:nowrap;font-family:var(--mono)}tr.hide{display:none}\ntbody tr:last-child td{border-bottom:0}\ntd.st{white-space:nowrap;color:var(--ink);font-weight:600}td.st .dot{margin-right:9px;vertical-align:-1px}.st-같음 .dot{background:var(--good)}.st-다름 .dot,.st-실제 .dot{background:var(--crit)}.st-기대 .dot{background:var(--warn)}\n.cmp td.key span{display:inline-block;margin:2px 6px 2px 0;font:600 17px var(--mono);white-space:nowrap}.cmp td.key span+span::before{content:"/ ";color:var(--line2)}\n.cmp .chip{white-space:normal}.cmp tr[data-st="다름"] td,.cmp tr[data-st="실제 없음"] td{background:#fff8f8}\ninput.f,button.t{font:15.5px var(--sans);color:var(--ink);background:var(--surface);border:1px solid var(--line2);border-radius:6px;padding:6px 12px;margin:0 8px 12px 0}button.t{cursor:pointer}input.f{max-width:100%}\ndetails summary{cursor:pointer}\ndetails.hint{margin-top:10px}details.hint summary{font-size:15px;color:var(--muted)}details.hint p{margin:6px 0 0}\ndetails.more{margin:18px 0 0;border-top:1px solid var(--line);padding-top:14px}details.more>summary{font-weight:650;font-size:17px;color:var(--ink2)}details.more>summary small{font-weight:normal;color:var(--muted);margin-left:8px;font-size:15px}\ndetails.more[open]>summary{margin-bottom:6px}details.more .in{margin:18px 0 0;padding:22px 26px;background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:auto}details.more .in h3{font-size:17.5px}\npre.raw,.src{white-space:pre-wrap;font:15.5px/1.6 var(--mono);color:var(--ink2);margin:0;overflow-wrap:anywhere}.src b{display:inline-block;width:4em;color:var(--muted);font-weight:normal}\n@media(max-width:900px){body{font-size:16px}main{padding:16px 12px}section{padding:16px}.verdict strong{font-size:26px}.pair{grid-template-columns:1fr}.pair>div+div{border-left:0;padding-left:0}.gather.c3,.gather.c2{grid-template-columns:1fr}.gather .gl{text-align:left}.gather .ga{display:none}}'

JS = ('<div id="tip"></div><script>'
      'document.querySelectorAll("div.tbl").forEach(function(d){var t=d.querySelector("table"),rs=[].slice.call(t.tBodies[0].rows),'
      'f=d.querySelector("input.f"),m=d.querySelector("button.more"),o=d.querySelector("button.only"),all=!m,only=false;'
      'function show(){var q=f?f.value.trim().toLowerCase():"",n=0;rs.forEach(function(r){var ok=(!q||r.textContent.toLowerCase().indexOf(q)>=0)&&(!only||r.dataset.st!=="같음");'
      'if(ok)n++;r.classList.toggle("hide",!ok||(!all&&n>' + str(FOLD) + '))})}'
      'if(f)f.addEventListener("input",show);if(m)m.addEventListener("click",function(){all=!all;m.textContent=all?"접기":"모두 보기";show()});'
      'if(o)o.addEventListener("click",function(){only=!only;o.textContent=only?"모든 줄 보기":"같음 줄 숨기기";show()});'
      '[].slice.call(t.tHead.rows[0].cells).forEach(function(th,i){th.addEventListener("click",function(){var up=th.dataset.up!=="1";th.dataset.up=up?"1":"0";'
      'rs.sort(function(a,b){var x=a.cells[i].textContent,y=b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);'
      'var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y,"ko");return up?c:-c});rs.forEach(function(r){t.tBodies[0].appendChild(r)});show()})});show()});'
      'var tip=document.getElementById("tip");document.querySelectorAll("svg.g").forEach(function(s){s.querySelectorAll(".n").forEach(function(n){'
      'function on(ev){var id=n.dataset.id;s.classList.add("on");n.classList.add("hot");s.querySelectorAll(".l,.ll").forEach(function(l){if(l.dataset.a===id||l.dataset.b===id){l.classList.add("hot");'
      's.querySelectorAll(".n").forEach(function(x){if(x.dataset.id===l.dataset.a||x.dataset.id===l.dataset.b)x.classList.add("hot")})}});'
      'tip.textContent="";JSON.parse(n.dataset.tip).forEach(function(p){var d=document.createElement("div"),b=document.createElement("b");b.textContent=p[0];d.appendChild(b);d.appendChild(document.createTextNode(p[1]));tip.appendChild(d)});'
      'tip.style.display="block";move(ev)}'
      'function move(ev){var r=n.getBoundingClientRect(),x=ev&&ev.clientX?ev.clientX+16:r.right+8,y=ev&&ev.clientY?ev.clientY+16:r.top;'
      'tip.style.left=Math.max(8,Math.min(x,innerWidth-tip.offsetWidth-8))+"px";tip.style.top=Math.max(8,Math.min(y,innerHeight-tip.offsetHeight-8))+"px"}'
      'function off(){s.classList.remove("on");s.querySelectorAll(".hot").forEach(function(x){x.classList.remove("hot")});tip.style.display="none"}'
      'n.addEventListener("mouseenter",on);n.addEventListener("mousemove",move);n.addEventListener("mouseleave",off);n.addEventListener("focus",on);n.addEventListener("blur",off)})})'
      '</script>')


def page(title, action, blocks):
    """결론(verdict)이 맨 위, 그 아래 그림과 근거 표. 확인 필요로 끝난 실행은 그 글이 맨 위에 온다."""
    lead = [b for b in blocks[:1] if b['kind'] in ('verdict', 'error')]
    body, more, last = '', [], ''
    for b in blocks[len(lead):]:
        if b.get('fold') and b['kind'] in ('table', 'counts', 'note'):
            if b['kind'] == 'note':
                more.append(f'<div class="in"><h3>{e(b["fold"])}</h3><pre class="raw">{e(b["text"])}</pre></div>')
            else:
                more.append('<div class="in">' + render_block({k: v for k, v in b.items() if k != 'fold'}) + '</div>')
            continue
        plain = b['kind'] in ('verdict', 'note', 'link', 'error')
        part = f'<section{" class=plain" if plain else ""}>' + render_block(b) + '</section>'
        if b['kind'] == 'link':
            last += part
        else:
            body += part
    if more:
        body += f'<details class="more"><summary>자세히 보기 <small>근거 표 · 원문 {len(more)}개</small></summary>{"".join(more)}</details>'
    body += last
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(action)} · {e(title)}</title><style>{CSS}</style><main><header><small>{e(title)}</small>'
            f'<h1>{e(action)}</h1>{"".join(render_block(b) for b in lead)}</header>{body}</main>{JS}</html>')
