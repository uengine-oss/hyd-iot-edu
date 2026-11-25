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
KIND_COLORS = [
    (('설비', 'Asset'), '#2f6fde'), (('구성 요소', 'Component'), '#e8742c'), (('센서', 'Sensor'), '#0c9aa0'),
    (('물리량', 'Quantity', '상태 변수'), '#7c55e0'), (('부품', 'Part'), '#d2407f'), (('실물', 'Unit'), '#6b8e23'),
    (('공급사', 'Supplier'), '#b7791f'), (('원자료 표',), '#5b6b82'), (('다른 표기', '원자료 이름'), '#8a94a6'),
]
SPARE = ['#3d7a5c', '#a2562c', '#4a5fc1', '#9a3fa8', '#5f7f8f', '#8f6b1f']
STATE_ICON = {'ok': '✓', 'warn': '!', 'bad': '✗', 'info': 'i'}


def e(x):
    return html.escape(str(x))


def color(kind, seen={}):
    for names, c in KIND_COLORS:
        if kind in names:
            return c
    if kind not in seen:
        seen[kind] = SPARE[len(seen) % len(SPARE)]
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
    main, small = 16, 12.5
    size = {}
    for n in nodes:
        w = max(text_w(clip(n['text']), main), text_w(clip(n.get('sub', ''), 36), small)) + 34
        size[n['id']] = (max(84, w), 50 if n.get('sub') else 38)
    step = max(h for _, h in size.values()) + 16
    per_edge = len(links) <= 16
    gap_text = {}
    for l in links:
        if l.get('text'):
            gap_text.setdefault((min(level[l['a']], level[l['b']]), max(level[l['a']], level[l['b']])), []).append(l['text'])
    widest = max([text_w(t, 12) for ts in gap_text.values() for t in ts] or [0])
    if not per_edge:
        widest = max([text_w(' · '.join(dict.fromkeys(ts)), 14) for ts in gap_text.values()] or [0])
    gap = max(150, widest + 70)
    col_w = [max(size[n['id']][0] for n in col) for col in cols]
    top = 46 if not per_edge else 22
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
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8b98ad"/></marker>'
           '<marker id="ahh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#f08c00"/></marker>'
           '<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#d6336c"/></marker></defs>']
    if not per_edge:      # 관계가 많으면 이름을 줄 사이 머리에 한 번만 적는다
        for (a, c), texts in sorted(gap_text.items()):
            if c == a + 1:
                mid = col_x[a] + col_w[a] + gap / 2
                out.append(f'<text class="gh" x="{mid:.0f}" y="20" text-anchor="middle">{e(" · ".join(dict.fromkeys(texts)))} →</text>')
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
            w = text_w(l['text'], 12) + 14
            labels.append(f'<g class="ll {e(mark)}" data-a="{e(l["a"])}" data-b="{e(l["b"])}"><rect x="{lx - w / 2:.0f}" y="{ly - 10:.0f}" width="{w:.0f}" height="20" rx="10"/>'
                          f'<text x="{lx:.0f}" y="{ly + 4:.0f}" text-anchor="middle">{e(l["text"])}</text></g>')
    out += labels
    for n in nodes:
        px, py, w, h = pos[n['id']]
        mark = n.get('mark', '')
        tip = [['종류', n['kind']]] + [[str(k), v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)] for k, v in (n.get('props') or {}).items()]
        g = [f'<g class="n {e(mark)}" data-id="{e(n["id"])}" data-tip="{e(json.dumps(tip, ensure_ascii=False))}" tabindex="0">']
        if mark in ('ask', 'bad', 'new'):
            g.append(f'<rect class="ring" x="{px - 5:.0f}" y="{py - 5:.0f}" width="{w + 10:.0f}" height="{h + 10:.0f}" rx="{(h + 10) / 2:.0f}"/>')
        g.append(f'<rect class="p" x="{px:.0f}" y="{py:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{h / 2:.0f}" fill="{color(n["kind"])}"/>')
        ty = py + (h / 2 + 5.5 if not n.get('sub') else 21)
        g.append(f'<text class="t" x="{px + w / 2:.0f}" y="{ty:.0f}" text-anchor="middle">{e(clip(n["text"]))}</text>')
        if n.get('sub'):
            g.append(f'<text class="s" x="{px + w / 2:.0f}" y="{py + 38:.0f}" text-anchor="middle">{e(clip(n["sub"], 36))}</text>')
        if n.get('badge'):
            bw = text_w(n['badge'], 12) + 14
            g.append(f'<rect class="bd" x="{px + w - bw + 6:.0f}" y="{py - 9:.0f}" width="{bw:.0f}" height="19" rx="9.5"/>'
                     f'<text class="bt" x="{px + w - bw / 2 + 6:.0f}" y="{py + 4.5:.0f}" text-anchor="middle">{e(n["badge"])}</text>')
        g.append('</g>')
        out.append(''.join(g))
    out.append('</svg>')
    kinds = list(dict.fromkeys(n['kind'] for n in nodes))
    legend = '<div class="legend">' + ''.join(f'<span><i style="background:{color(k)}"></i>{e(k)}</span>' for k in kinds)
    marks = {n.get('mark') for n in nodes} | {l.get('mark') for l in links}
    for m, word in (('ask', '물은 값'), ('hit', '따라간 길'), ('bad', '볼 곳'), ('new', '새로 생김'), ('gone', '사라짐'), ('dim', '둘레의 다른 대상')):
        if m in marks:
            legend += f'<span><i class="m-{m}"></i>{e((b.get("marks") or {}).get(m, word))}</span>'
    return legend + '<small>노드에 마우스를 올리면 속성이 보입니다</small></div><div class="gbox">' + ''.join(out) + '</div>'


# ───────────── 블록 하나 그리기 ─────────────
def chip_of(c):
    if isinstance(c, dict):
        style = f' style="background:{color(c["kind"])};color:#fff;border-color:transparent"' if c.get('kind') else ''
        return f'<span class="chip {e(c.get("mark", ""))}"{style}>{e(c["text"])}' + (f'<small>{e(c["sub"])}</small>' if c.get('sub') else '') + '</span>'
    return f'<span class="chip">{e(c)}</span>'


NONE = '<span class="none">(없음)</span>'


def render_block(b, previous=None, current=None):
    k = b['kind']
    title = f'<h3>{e(b["title"])}</h3>' if b.get('title') else ''
    tail = f'<p class="note">{e(b["note"])}</p>' if b.get('note') else ''
    if k == 'verdict':
        return (f'<div class="verdict v-{e(b["state"])}"><b>{STATE_ICON.get(b["state"], "i")}</b><div><strong>{e(b["text"])}</strong>'
                + (f'<span>{e(b["detail"])}</span>' if b.get('detail') else '') + '</div></div>')
    if k == 'note':
        return f'<p class="note">{e(b["text"])}</p>'
    if k == 'error':
        return f'<div class="err"><b>{e(b.get("title") or "확인 필요")}</b>{e(b["text"])}</div>'
    if k == 'link':
        return f'<a class="btn" href="{e(b["url"])}" target="_blank" rel="noopener">{e(b["text"])} ↗</a>' + tail
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
            style = f' style="border-top-color:{color(c["kind"])}"' if c.get('kind') else ''
            icon = {'ok': '<i class="ic ok">✓</i>', 'bad': '<i class="ic bad">✗</i>', 'warn': '<i class="ic warn">!</i>', 'lock': LOCK, 'open': UNLOCK}.get(c.get('icon'), '')
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
                     f'<div class="bs {"same" if a == c else "diff"}">{"같음 ✓" if a == c else ("+" if c > a else "") + str(c - a)}</div>')
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
            cells = ''.join(f'<td>{chips(x, y) if st == "다름" else chips(x)}</td><td>{chips(y, x) if st == "다름" else chips(y)}</td>' for x, y in r['cells'])
            body += (f'<tr data-st="{e(st)}"><td class="st st-{e(st.split(" ")[0])}"><b>{mark}</b>{e(st)}</td>'
                     f'<td class="key">{"".join(f"<span>{e(p.strip())}</span>" for p in r["key"].split("|") if p.strip())}</td>{cells}</tr>')
        tools = ('<input class="f" placeholder="글자로 거르기">' if len(b['rows']) > 8 else '') + '<button class="t only">같음 줄 숨기기</button>'
        return (title + f'<div class="tallies">{tally or "<span class=tally>견줄 행 없음</span>"}</div>'
                f'<div class="tbl cmp">{tools}<table><thead>{head}</thead><tbody>{body}</tbody></table></div>' + tail)
    if k == 'diff':
        if not b['rows']:
            return title + f'<div class="calm"><b>＝</b>늘어남 · 사라짐 · 값 바뀜 없음 <small>(같은 항목 {b["same"]}개)</small></div>' + tail
        return title + f'<p class="note">같은 항목 {b["same"]}개</p>' + grid(['항목', '바뀜', '전', '후'], b['rows'], [r[1] for r in b['rows']]) + tail
    raise ValueError(f'모르는 블록 종류 {k!r}')


LOCK = '<svg class="lock" viewBox="0 0 24 24"><rect x="4" y="10.5" width="16" height="11" rx="2.5"/><path d="M7.5 10.5V7.5a4.5 4.5 0 0 1 9 0v3" fill="none" stroke-width="2.4"/></svg>'
UNLOCK = '<svg class="lock un" viewBox="0 0 24 24"><rect x="4" y="10.5" width="16" height="11" rx="2.5"/><path d="M7.5 10.5V7.5a4.5 4.5 0 0 1 8.6-1.8" fill="none" stroke-width="2.4"/></svg>'

CSS = '''*{box-sizing:border-box}
body{margin:0;background:#f3f6fb;color:#1c2738;font:17px/1.6 "Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:1480px;margin:auto;padding:26px 28px 60px}
header small{color:#62718a;font-size:15px}h1{font-size:34px;margin:2px 0 14px;letter-spacing:-.5px}
h3{font-size:20px;margin:0 0 12px}section{margin:16px 0;padding:22px 24px;background:#fff;border:1px solid #dde4ef;border-radius:16px;box-shadow:0 1px 3px rgba(20,40,80,.05);overflow:auto}
section.plain{background:none;border:0;box-shadow:none;padding:0 6px;margin:10px 0}
.verdict{display:flex;gap:18px;align-items:center;padding:20px 26px;border-radius:18px;margin:6px 0 4px;border:2px solid}
.verdict>b{flex:none;width:58px;height:58px;border-radius:50%;display:grid;place-items:center;color:#fff;font-size:32px;line-height:1}
.verdict strong{display:block;font-size:30px;line-height:1.3;letter-spacing:-.4px}.verdict span{display:block;font-size:17px;color:#46546b;margin-top:2px}
.v-ok{background:#e9f8ef;border-color:#8fd3a8}.v-ok>b{background:#1f9d57}.v-warn{background:#fff6dd;border-color:#f1cf73}.v-warn>b{background:#e09200}
.v-bad{background:#ffeaee;border-color:#f3a6b6}.v-bad>b{background:#d6336c}.v-info{background:#eaf1ff;border-color:#a9c2f5}.v-info>b{background:#2f6fde;font-family:Georgia,serif;font-style:italic}
.note{color:#52607a;white-space:pre-wrap;margin:10px 0 0;font-size:15.5px}.empty{color:#7b879b;margin:4px 0}.none{color:#9aa5b8}
.err{border-left:6px solid #d6336c;background:#fff0f3;padding:16px 18px;border-radius:10px;white-space:pre-wrap;font-size:17px;overflow-wrap:anywhere}.err b{display:block;font-size:20px;color:#b3214f;margin-bottom:4px}
.btn{display:inline-block;padding:10px 20px;border-radius:999px;background:#1c2738;color:#fff;text-decoration:none;font-weight:bold;font-size:16px}.btn:hover{background:#2f6fde}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;margin:0 0 10px;font-size:15px;color:#3a475c}.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:16px;height:16px;border-radius:50%;display:inline-block}.legend small{color:#8a96aa;margin-left:auto}
.legend i.m-ask{background:#fff;border:3px dashed #f08c00}.legend i.m-hit{background:#f08c00;height:5px;border-radius:3px;width:24px}.legend i.m-bad{background:#fff;border:3px solid #d6336c}
.legend i.m-new{background:#fff;border:3px solid #1f9d57}.legend i.m-gone{background:#c3cad6}.legend i.m-dim{background:#c9d2e0}
.gbox{overflow:auto}svg.g{width:100%;height:auto;display:block;margin:auto}
svg.g .l{fill:none;stroke:#a9b4c6;stroke-width:1.8}svg.g .l.hit{stroke:#f08c00;stroke-width:3.4;stroke-dasharray:9 7;animation:flow 1.1s linear infinite;filter:drop-shadow(0 0 4px rgba(240,140,0,.75))}
svg.g .l.bad{stroke:#d6336c;stroke-width:2.6}svg.g .l.dim{opacity:.35}svg.g .l.gone{stroke-dasharray:4 5;opacity:.6}
@keyframes flow{to{stroke-dashoffset:-16}}
svg.g .ll rect{fill:#fff;stroke:#d5dce8}svg.g .ll text{font-size:12px;fill:#4a5870;font-weight:bold}svg.g .ll.hit rect{stroke:#f08c00;fill:#fff8ea}svg.g .ll.dim{opacity:.4}
svg.g .gh{font-size:14px;fill:#4a5870;font-weight:bold}
svg.g .n{cursor:default;outline:none}svg.g .n .t{fill:#fff;font-size:16px;font-weight:bold}svg.g .n .s{fill:#fff;font-size:12.5px;opacity:.92}
svg.g .n .ring{fill:none;stroke-width:3}svg.g .n.ask .ring{stroke:#f08c00;stroke-dasharray:7 5}svg.g .n.bad .ring{stroke:#d6336c}svg.g .n.new .ring{stroke:#1f9d57}
svg.g .n.dim{opacity:.38}svg.g .n.gone .p{fill:#c3cad6}svg.g .n.gone .t{text-decoration:line-through}
svg.g .n .bd{fill:#1c2738;stroke:#fff;stroke-width:2}svg.g .n .bt{fill:#fff;font-size:12px;font-weight:bold}
svg.g.on .n:not(.hot),svg.g.on .l:not(.hot),svg.g.on .ll:not(.hot){opacity:.16}
#tip{position:fixed;z-index:9;pointer-events:none;background:#1c2738;color:#fff;border-radius:12px;padding:10px 14px;font-size:14px;line-height:1.55;max-width:460px;box-shadow:0 8px 24px rgba(0,0,0,.25);display:none;overflow-wrap:anywhere}
#tip b{color:#9fc0ff;font-weight:normal;margin-right:8px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pair.stack{grid-template-columns:1fr}.pair>div{border:1px solid #e1e7f0;border-radius:14px;padding:16px;background:#fbfcfe;min-width:0}.pair h3{font-size:18px}
.chip{display:inline-flex;align-items:baseline;gap:6px;margin:3px 4px 3px 0;padding:3px 11px;border-radius:999px;background:#eef2f8;border:1px solid #d6deea;font-size:15px;white-space:nowrap}
.chip small{font-size:12px;opacity:.85}.chip.off{background:#ffe3ea;border-color:#f3a6b6;color:#a01646;font-weight:bold}.chip.now{background:#e2f6ea;border-color:#8fd3a8}.chip.past{background:#f1f1f1;border-color:#cfcfcf;color:#666}
.chip.bad{background:#ffe3ea;border-color:#f3a6b6;color:#a01646}
.gather{display:grid;gap:10px 12px;align-items:center}.gather.c3{grid-template-columns:minmax(0,1.3fr) 30px auto 30px minmax(0,1fr)}.gather.c2{grid-template-columns:minmax(0,1fr) 30px minmax(0,1fr)}
.gather .gl{text-align:right;border-right:4px solid #c9d3e2;border-radius:0 14px 14px 0;padding:4px 12px 4px 0}.gather .ga{color:#8b98ad;font-size:24px;text-align:center}
.gather .chip{white-space:normal}.gather .gm .chip{font-size:17px;font-weight:bold;padding:6px 16px}.gather .gh2{font-weight:bold;color:#52607a;font-size:15px;border:0;padding-bottom:0}.gather .gm.bad .chip{outline:3px solid #d6336c;outline-offset:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}.cards.wide{grid-template-columns:repeat(auto-fill,minmax(440px,1fr))}
.card{border:1px solid #dde4ef;border-top:6px solid #c9d3e2;border-radius:14px;padding:14px 16px;background:#fff}.card.ok{border-top-color:#1f9d57}.card.bad{border-top-color:#d6336c;background:#fff7f9}.card.warn{border-top-color:#e09200}
.card .ch{display:flex;align-items:center;gap:10px;font-size:19px}.card .ch b{flex:1;min-width:0;overflow-wrap:anywhere}.card p{margin:8px 0 0;color:#3a475c;font-size:15.5px;overflow-wrap:anywhere}
.card ul{list-style:none;margin:10px 0 0;padding:0}.card li{padding:5px 0;border-top:1px dashed #e3e8f1;font-size:15.5px;overflow-wrap:anywhere}.card li>span:first-child{display:block;color:#62718a;font-size:13.5px}.card .chip{white-space:normal}
.badge{flex:none;padding:2px 12px;border-radius:999px;background:#eef2f8;font-size:14px;font-weight:bold;color:#3a475c}.badge.ok{background:#d9f3e3;color:#12703c}.badge.bad{background:#ffd9e2;color:#a01646}.badge.warn{background:#ffecc0;color:#8a5a00}
.ic{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;color:#fff;font-style:normal;font-weight:bold}.ic.ok{background:#1f9d57}.ic.bad{background:#d6336c}.ic.warn{background:#e09200}
.lock{flex:none;width:30px;height:30px;fill:#1f9d57;stroke:#1f9d57}.lock.un{fill:#d6336c;stroke:#d6336c}
.bars{display:grid;grid-template-columns:minmax(150px,auto) 1fr 1fr 96px;gap:7px 14px;align-items:center;font-size:16px}
.bars .bh{font-weight:bold;color:#52607a;font-size:15px}.bars .bh i{display:inline-block;width:14px;height:14px;border-radius:4px;margin-right:6px;vertical-align:-1px}
.bars i.a{background:#8492aa}.bars i.b{background:#2f6fde}.bars .bn{font-weight:bold;white-space:nowrap}
.bars .bb{display:flex;align-items:center;gap:8px;background:#f1f4f9;border-radius:8px;height:26px;padding-right:8px}.bars .bb i{display:block;height:26px;border-radius:8px;min-width:2px}.bars .bb em{font-style:normal;font-weight:bold;font-size:15px}
.bars .bs{font-weight:bold;font-size:15px;text-align:center;border-radius:999px;padding:1px 0}.bars .bs.same{background:#d9f3e3;color:#12703c}.bars .bs.diff{background:#ffd9e2;color:#a01646}
.stats{display:flex;flex-wrap:wrap;gap:12px}.stats div{flex:1 1 130px;background:#f4f7fc;border:1px solid #e1e7f0;border-radius:14px;padding:12px 16px}.stats b{display:block;font-size:32px;line-height:1.2;color:#2f6fde}.stats span{color:#52607a;font-size:15px;overflow-wrap:anywhere}
.calm{font-size:22px;font-weight:bold;color:#12703c;background:#e9f8ef;border-radius:14px;padding:16px 20px}.calm b{margin-right:10px}.calm small{font-weight:normal;color:#52607a;font-size:15px}
.tallies{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 12px}.tally{display:inline-flex;align-items:baseline;gap:8px;padding:6px 16px;border-radius:14px;background:#eef2f8;font-size:16px;font-weight:bold}.tally b{font-size:28px}
.t-같음{background:#d9f3e3;color:#12703c}.t-다름,.t-실제{background:#ffd9e2;color:#a01646}.t-기대{background:#ffecc0;color:#8a5a00}
.tbl{overflow:auto}table{border-collapse:collapse;width:100%;font-size:15.5px}th,td{padding:9px 12px;border-bottom:1px solid #e3e8f1;text-align:left;vertical-align:top}
th{background:#eef2f8;cursor:pointer;white-space:nowrap;color:#3a475c}td{overflow-wrap:break-word;word-break:keep-all}td.k{white-space:nowrap}tr.hide{display:none}
td.st{white-space:nowrap;font-weight:bold}td.st b{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;color:#fff;margin-right:8px;font-size:17px}
.st-같음{color:#12703c}.st-같음 b{background:#1f9d57}.st-다름,.st-실제,.st-사라짐{color:#a01646}.st-다름 b,.st-실제 b{background:#d6336c}.st-기대,.st-늘어남,.st-값{color:#8a5a00}.st-기대 b{background:#e09200}
.cmp td.key span{display:inline-block;margin:2px 6px 2px 0;padding:2px 10px;border-radius:8px;background:#1c2738;color:#fff;font-size:14.5px;white-space:nowrap}.cmp td.key span:first-child:not(:only-child){background:#5b6b82}
.cmp .chip{white-space:normal}.cmp tr[data-st="다름"] td,.cmp tr[data-st="실제 없음"] td{background:#fff7f9}
input.f,button.t{font:inherit;font-size:15px;color:#1c2738;background:#fff;border:1px solid #c3cddc;border-radius:999px;padding:5px 14px;margin:0 8px 12px 0}button.t{cursor:pointer}input.f{max-width:100%}
details.fold summary{cursor:pointer;font-weight:bold;font-size:17px;color:#3a475c}details.fold summary small{font-weight:normal;color:#8a96aa;margin-left:8px}details.fold[open] summary{margin-bottom:12px}
.src{white-space:pre-wrap;font-family:Consolas,monospace;font-size:15px;background:#f6f8fb;padding:10px;border-radius:10px}.src b{display:inline-block;width:4em;color:#8a96aa;font-weight:normal}
@media(max-width:900px){main{padding:16px 12px}section{padding:16px}h1{font-size:26px}.verdict strong{font-size:22px}.pair{grid-template-columns:1fr}.gather.c3,.gather.c2{grid-template-columns:1fr}.gather .gl{text-align:left;border:0}.gather .ga{display:none}}
@media(prefers-reduced-motion:reduce){svg.g .l.hit{animation:none}}'''

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
    body = ''
    for b in blocks[len(lead):]:
        plain = b['kind'] in ('verdict', 'note', 'link', 'error')
        body += f'<section{" class=plain" if plain else ""}>' + render_block(b) + '</section>'
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(action)} · {e(title)}</title><style>{CSS}</style><main><header><small>{e(title)}</small>'
            f'<h1>{e(action)}</h1>{"".join(render_block(b) for b in lead)}</header>{body}</main>{JS}</html>')
