# -*- coding: utf-8 -*-
"""기술 레이어 구조도(설계서 v2 「그림 1」 방식) 렌더러 — hyd-iot-edu · ceco_demo 공용 사본.
레이어 띠(위 → 아래)마다 왼쪽에 층 이름 · 핵심 기능, 오른쪽에 구성요소 카드(컨테이너가 아니라 논리 구성요소).
카드는 열(col) 격자에 놓이고, 화살표는 카드 사이 틈(gutter)과 띠 사이 틈으로 꺾어 지나간다.
화살표마다 번호와 라벨(프로토콜 · 토픽/표)을 붙이고, 같은 번호로 아래 표에 전부 적는다.
데이터: LAYERS = [(id, 'L9', 이름, 핵심 기능, 배경, 테두리, 글자)], CARDS = {id: dict(layer, col, span, title, tech, box, lines, kind)},
        ARROWS = [(번호없이, from, to, kind, label, detail)]
"""
import html, re

KCOL = dict(data="#2563eb", alert="#7c3aed", cmd="#ea580c", ok="#be185d", api="#4b5563", mon="#6b7280", once="#9ca3af", human="#111827", file="#92400e")
KDASH = dict(alert="", mon="3 3", once="7 4", api="5 3", file="2 3")


def esc(t):
    return html.escape(str(t), quote=True)


def tw(t, size):
    return sum(size * (1.0 if ord(ch) > 0x1100 else 0.58) for ch in str(t))


def wrap(t, width, size):
    out, cur = [], ""
    for tok in re.split(r"(\s+)", str(t)):
        if tw(cur + tok, size) <= width:
            cur += tok
            continue
        if cur.strip():
            out.append(cur.rstrip())
        cur = tok.lstrip()
        while tw(cur, size) > width:
            n = max(1, int(len(cur) * width / max(1, tw(cur, size))))
            out.append(cur[:n])
            cur = cur[n:]
    if cur.strip():
        out.append(cur.rstrip())
    return out or [""]


class G:
    LEFT = 230          # 왼쪽 층 이름 칸
    COLW = 214          # 카드 폭(한 칸)
    GUT = 46            # 카드 사이 틈
    PADY = 34           # 띠 안 위아래 여백(위는 제목 없음)
    BANDGAP = 40        # 띠 사이 틈(가로 경로 · 라벨)


def card_h(c):
    n = 0
    n += len(wrap(c["title"], G.COLW * c.get("span", 1) + G.GUT * (c.get("span", 1) - 1) - 20, 13.5))
    body = len(wrap(c.get("tech", ""), G.COLW * c.get("span", 1) - 20, 11)) + sum(len(wrap(x, G.COLW * c.get("span", 1) + G.GUT * (c.get("span", 1) - 1) - 22, 11)) for x in c.get("lines", []))
    return 22 + n * 17 + body * 14 + (18 if c.get("box") else 0) + 8


def layout(LAYERS, CARDS, ncol):
    W = G.LEFT + ncol * (G.COLW + G.GUT) + 110
    y = 10
    band, pos = {}, {}
    for lid, *_ in LAYERS:
        cs = [k for k, c in CARDS.items() if c["layer"] == lid]
        # 같은 칸에 여러 카드면 세로로 쌓는다(row)
        rows = {}
        for k in cs:
            rows.setdefault(CARDS[k].get("row", 0), []).append(k)
        yy = y + G.PADY
        for r in sorted(rows):
            h = max(card_h(CARDS[k]) for k in rows[r])
            for k in rows[r]:
                c = CARDS[k]
                x = G.LEFT + c["col"] * (G.COLW + G.GUT)
                w = G.COLW * c.get("span", 1) + G.GUT * (c.get("span", 1) - 1)
                pos[k] = [x, yy, w, h]
            yy += h + 18
        band[lid] = (y, yy - 18 + G.PADY)
        y = band[lid][1] + G.BANDGAP
    return W, y, band, pos


def gutter_x(i):
    """i 번째 칸 왼쪽 틈 가운데(i=0 이면 첫 칸 왼쪽)."""
    return G.LEFT + i * (G.COLW + G.GUT) - G.GUT / 2


def route(a, b, la, lb, band, order, lanes, rowbot, pref_gutter=None):
    """카드 a → b 경로(점 목록).
    같은 띠: 이웃이면 곧게(같은 쌍이 여러 번이면 위아래로 벌림), 사이에 카드가 있으면 띠 아래 여백으로 돈다.
    인접 띠: 겹치는 x 가 있고 막히지 않으면 곧게, 아니면 띠 사이 틈에서 한 번 꺾는다.
    먼 띠: 열 사이 틈(gutter)을 따라 세로로 간다."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, bcx = ax + aw / 2, bx + bw / 2
    pair = tuple(sorted((id(a), id(b))))
    k = lanes.get(("pair", pair), 0)
    lanes[("pair", pair)] = k + 1
    off = (k - 0.5) * 14 if lanes.get(("paircount", pair), 1) > 1 else 0

    def blocked_v(x, y0, y1):
        return any(p[0] - 4 < x < p[0] + p[2] + 4 and not (max(y0, y1) < p[1] - 2 or min(y0, y1) > p[1] + p[3] + 2) for p in ALL if p is not a and p is not b)

    def blocked_h(y, x0, x1):
        return any(p[1] - 2 < y < p[1] + p[3] + 2 and not (max(x0, x1) < p[0] - 2 or min(x0, x1) > p[0] + p[2] + 2) for p in ALL if p is not a and p is not b)

    if la == lb:
        lo, hi = max(ay, by) + 10, min(ay + ah, by + bh) - 10
        y = (lo + hi) / 2 + off if hi > lo else max(ay, by) + 20
        x0, x1 = (ax + aw, bx) if ax + aw <= bx else (ax, bx + bw)
        if not blocked_h(y, x0, x1):
            return [(x0, y), (x1, y)]
        kk = lanes.get(("under", la), 0)
        lanes[("under", la)] = kk + 1
        yu = rowbot[la] + 10 + (kk % 4) * 6
        return [(acx + (kk % 3 - 1) * 12, ay + ah), (acx + (kk % 3 - 1) * 12, yu), (bcx + (kk % 3 - 1) * 12, yu), (bcx + (kk % 3 - 1) * 12, by + bh)]
    down = order[la] < order[lb]
    ys = (ay + ah, by) if down else (ay, by + bh)
    lo, hi = max(ax, bx) + 16, min(ax + aw, bx + bw) - 16
    if hi > lo:
        mid = (lo + hi) / 2 + off
        for x in (mid, mid - 24, mid + 24, lo + 6, hi - 6):
            if lo - 1 <= x <= hi + 1 and not blocked_v(x, *ys):
                return [(x, ys[0]), (x, ys[1])]
    ga = band[la][1] + G.BANDGAP / 2 if down else band[la][0] - G.BANDGAP / 2
    gb = band[lb][0] - G.BANDGAP / 2 if down else band[lb][1] + G.BANDGAP / 2
    sx = acx + off
    ex = bcx + off
    if abs(order[la] - order[lb]) == 1:
        kk = lanes.get(("gap", min(order[la], order[lb])), 0)
        lanes[("gap", min(order[la], order[lb]))] = kk + 1
        gy = ga + ((kk % 5) - 2) * 5
        return [(sx, ys[0]), (sx, gy), (ex, gy), (ex, ys[1])]
    cands = [pref_gutter] if pref_gutter is not None else sorted(range(1, 12), key=lambda i: abs(gutter_x(i) - (acx + bcx) / 2))
    for gi in cands:
        kk = lanes.get(("g", gi), 0)
        gx = gutter_x(gi) + ((kk % 6) - 2.5) * 7
        if pref_gutter is None and blocked_v(gx, ga, gb):
            continue
        lanes[("g", gi)] = kk + 1
        k1 = lanes.get(("gap", order[la], down), 0)
        lanes[("gap", order[la], down)] = k1 + 1
        k2 = lanes.get(("gapb", order[lb], down), 0)
        lanes[("gapb", order[lb], down)] = k2 + 1
        g1 = ga + (k1 % 5 - 2) * 5
        g2 = gb + (k2 % 5 - 2) * 5
        return [(sx, ys[0]), (sx, g1), (gx, g1), (gx, g2), (ex, g2), (ex, ys[1])]
    return [(sx, ys[0]), (ex, ys[1])]


ALL = []


def svg(LAYERS, CARDS, ARROWS, ncol, idp="ly"):
    global ALL
    W, H, band, pos = layout(LAYERS, CARDS, ncol)
    ALL = list(pos.values())
    lay_of = {k: c["layer"] for k, c in CARDS.items()}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" class="layers" role="img" aria-label="기술 레이어 구조도">', "<defs>"]
    for k, col in KCOL.items():
        o.append(f'<marker id="{idp}-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H:.0f}" fill="#ffffff"/>')
    for lid, code, name, func, bg, bd, fg in LAYERS:
        y0, y1 = band[lid]
        o.append(f'<rect x="8" y="{y0}" width="{W - 16}" height="{y1 - y0}" rx="12" fill="{bg}" stroke="{bd}" stroke-width="1.3"/>')
        o.append(f'<rect x="22" y="{y0 + 14}" width="{12 + tw(code, 12.5):.0f}" height="20" rx="5" fill="{fg}"/><text x="28" y="{y0 + 28}" font-size="12.5" font-weight="800" fill="#fff">{esc(code)}</text>')
        for j, t in enumerate(wrap(name, G.LEFT - 40, 15)):
            o.append(f'<text x="22" y="{y0 + 56 + j * 19}" font-size="15" font-weight="800" fill="#14212a">{esc(t)}</text>')
        nl = len(wrap(name, G.LEFT - 40, 15))
        for j, t in enumerate(wrap("▸ " + func, G.LEFT - 40, 12)):
            o.append(f'<text x="22" y="{y0 + 66 + nl * 19 + j * 16}" font-size="12" font-weight="700" fill="{fg}">{esc(t)}</text>')
    # 화살표
    lanes, drawn = {}, []
    order = {lid: i for i, (lid, *_r) in enumerate(LAYERS)}
    rowbot = {lid: band[lid][1] - G.PADY for lid in band}
    for a, b, *_r in ARROWS:
        pr = tuple(sorted((id(pos[a]), id(pos[b]))))
        lanes[("paircount", pr)] = lanes.get(("paircount", pr), 0) + 1
    for i, ar in enumerate(ARROWS, 1):
        a, b, kind, label = ar[:4]
        opt = ar[5] if len(ar) > 5 else {}
        pts = route(pos[a], pos[b], lay_of[a], lay_of[b], band, order, lanes, rowbot, opt.get("g"))
        drawn.append((i, pts, kind, label))
    for i, pts, kind, label in drawn:
        o.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="#fff" stroke-width="6" stroke-linejoin="round" opacity=".85"/>')
    for i, pts, kind, label in drawn:
        col = KCOL[kind]
        d = KDASH.get(kind, "")
        da = f' stroke-dasharray="{d}"' if d else ""
        o.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{col}" stroke-width="{2.4 if kind in ("cmd", "data") else 2}" stroke-linejoin="round"{da} marker-end="url(#{idp}-{kind})"/>')
    # 카드
    for k, c in CARDS.items():
        x, y, w, h = pos[k]
        kind = c.get("kind", "normal")
        stroke, fill, dash, sw = "#94a3b8", "#ffffff", "", 1.3
        if kind == "hl":
            stroke, sw = "#475569", 2
        elif kind == "once":
            stroke, fill, dash = "#9ca3af", "#fbfcfc", "6 4"
        elif kind == "opt":
            stroke, fill, dash = "#9ca3af", "#fbfcfc", "2 3"
        elif kind == "info":
            stroke, fill, dash = "#cbd5e1", "#fbfdff", "4 3"
        elif kind == "ext":
            stroke, fill, dash = "#6366f1", "#f5f6ff", "4 3"
        elif kind == "person":
            stroke, fill, sw = "#111827", "#ffffff", 1.6
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>')
        yy = y + 19
        for t in wrap(c["title"], w - 20, 13.5):
            o.append(f'<text x="{x + w / 2}" y="{yy}" font-size="13.5" font-weight="800" fill="#0f172a" text-anchor="middle">{esc(t)}</text>')
            yy += 17
        for t in wrap(c.get("tech", ""), w - 20, 11):
            o.append(f'<text x="{x + w / 2}" y="{yy}" font-size="11" fill="#475569" text-anchor="middle">{esc(t)}</text>')
            yy += 14
        for ln in c.get("lines", []):
            for t in wrap(ln, w - 22, 11):
                o.append(f'<text x="{x + w / 2}" y="{yy}" font-size="11" fill="#1e293b" text-anchor="middle">{esc(t)}</text>')
                yy += 14
        if c.get("box"):
            bt = c["box"]
            bw = 10 + tw(bt, 9.8)
            assert bw <= w - 6, f"카드 꼬리표가 카드보다 넓음: {k} '{bt}'"
            o.append(f'<rect x="{x + w / 2 - bw / 2:.1f}" y="{y + h - 18}" width="{bw:.1f}" height="14" rx="7" fill="#eef2f7"/><text x="{x + w / 2}" y="{y + h - 7.5}" font-size="9.8" fill="#475569" text-anchor="middle" font-family="JetBrains Mono,Consolas,monospace">{esc(bt)}</text>')
    # 번호 · 라벨(선 위)
    used = []

    def score(mx, my, w):
        sc = 0
        for q in ALL:
            if q[0] - w / 2 < mx < q[0] + q[2] + w / 2 and q[1] - 10 < my < q[1] + q[3] + 10:
                sc += 100
        for ux, uy, uw in used:
            if abs(mx - ux) < (w + uw) / 2 + 4 and abs(my - uy) < 18:
                sc += 60
        return sc

    for i, pts, kind, label in drawn:
        segs = [sg for sg in zip(pts, pts[1:]) if abs(sg[1][0] - sg[0][0]) + abs(sg[1][1] - sg[0][1]) > 6]
        txt = f"{i} {label}"
        w = 12 + tw(txt, 10.5)
        best = None
        for sg in sorted(segs, key=lambda sg: -(abs(sg[1][0] - sg[0][0]) + abs(sg[1][1] - sg[0][1]))):
            for t in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
                mx, my = sg[0][0] + (sg[1][0] - sg[0][0]) * t, sg[0][1] + (sg[1][1] - sg[0][1]) * t
                sc = score(mx, my, w)
                if best is None or sc < best[0]:
                    best = (sc, mx, my)
                if sc == 0:
                    break
            if best and best[0] == 0:
                break
        sc, mx, my = best
        if sc >= 100:
            txt = str(i)
            w = 12 + tw(txt, 10.5)
        used.append((mx, my, w))
        col = KCOL[kind]
        o.append(f'<g><rect x="{mx - w / 2:.1f}" y="{my - 9:.1f}" width="{w:.1f}" height="17" rx="8.5" fill="#fff" stroke="{col}" stroke-width="1.1"/>'
                 f'<text x="{mx:.1f}" y="{my + 3.6:.1f}" font-size="10.5" font-weight="700" fill="{col}" text-anchor="middle">{esc(txt)}</text></g>')
    o.append("</svg>")
    return "\n".join(o), (W, H)


KW = dict(data="데이터(상향)", alert="경보 · 분석", cmd="조치 명령(하향)", ok="승인 · 업무", api="조회 · 호출", mon="감시", once="기동 · 1회", human="사람", file="파일")


def table(ARROWS, CARDS, LAYERS=None):
    lay = {lid: code for lid, code, *_r in (LAYERS or [])}
    rows = []
    for i, ar in enumerate(ARROWS, 1):
        a, b, k, lb, dt = ar[:5]
        la, lb_ = CARDS[a]["layer"], CARDS[b]["layer"]
        ll = f'<span class="lyr">{lay.get(la, la)}{"" if la == lb_ else " → " + lay.get(lb_, lb_)}</span> ' if LAYERS else ""
        rows.append(f'<tr id="la{i}"><td class="c"><span class="abadge" style="--k:{KCOL[k]}">{i}</span></td><td>{ll}{esc(CARDS[a]["title"])} → {esc(CARDS[b]["title"])}</td>'
                    f'<td><span class="kdot" style="background:{KCOL[k]}"></span>{KW[k]}</td><td><b>{esc(lb)}</b></td><td>{esc(dt)}</td></tr>')
    return f'<div class="tscroll"><table class="tbl small"><tr><th>#</th><th>어디서 → 어디로</th><th>종류</th><th>라벨</th><th>무엇이 · 어떻게(프로토콜 · 토픽/표 · 형식)</th></tr>{"".join(rows)}</table></div>'


def legend_html():
    return '<div class="klegend">' + "".join(
        f'<span><svg width="44" height="12" aria-hidden="true"><line x1="2" y1="6" x2="34" y2="6" stroke="{KCOL[k]}" stroke-width="2.4"'
        + (f' stroke-dasharray="{KDASH[k]}"' if KDASH.get(k) else "") + f'/><path d="M34,1.5 L43,6 L34,10.5z" fill="{KCOL[k]}"/></svg>{KW[k]}</span>'
        for k in ("data", "alert", "cmd", "ok", "api", "mon", "once", "human")) + "</div>"


def abadges(t, ARROWS):
    """{a:N} → 그림 번호와 같은 색 동그라미(누르면 화살표 표의 그 줄)."""
    def one(m):
        i = int(m.group(1))
        a, b, k, lb = ARROWS[i - 1][:4]
        return f'<a class="abadge" style="--k:{KCOL[k]}" href="#la{i}" title="{esc(lb)}">{i}</a>'
    return re.sub(r"\{a:(\d+)\}", one, t)


def layer_text_html(LAYERS, CARDS, ARROWS, TEXT):
    out = []
    for lid, code, name, func, bg, bd, fg in LAYERS:
        easy, tech = TEXT[lid]
        cards = [c for c in CARDS.values() if c["layer"] == lid]
        chips = "".join(f'<span class="lcard">{esc(c["title"])}' + (f' <code>{esc(c["box"])}</code>' if c.get("box") else "") + "</span>" for c in cards)
        out.append(f'<article class="lyrsec" id="ly-{lid}" style="--bg:{bg};--bd:{bd};--fg:{fg}">'
                   f'<header><span class="lcode">{esc(code)}</span><h3>{esc(name)}</h3><span class="lfunc">{esc(func)}</span></header>'
                   f'<p class="lcards"><b>이 층의 구성요소 {len(cards)}개</b> {chips}</p>'
                   f'<div class="easy"><span class="lane">쉬운 말</span><p>{abadges(esc(easy), ARROWS)}</p></div>'
                   f'<div class="tech"><span class="lane">기술 세부</span><p>{abadges(esc(tech), ARROWS)}</p></div></article>')
    return "\n".join(out)


def layer_table_html(ROWS):
    head = "<tr><th>층</th><th>핵심 기능</th><th>채택 기술(실제로 돌아가는 것)</th><th>역할</th><th>하지 않는 일</th><th>원래 설계와 다른 점</th></tr>"
    body = "".join("<tr>" + "".join(f"<td>{'<b>' + esc(x) + '</b>' if j == 0 else esc(x)}</td>" for j, x in enumerate(r)) + "</tr>" for r in ROWS)
    return f'<div class="tscroll"><table class="tbl small">{head}{body}</table></div>'


def seq_svg(LANES, PHASES, SEQ, idp="sq"):
    """레이어 간 시퀀스: 세로줄 = 층, 가로 화살표 = 한 단계(번호). 출발 = 도착이면 그 층의 메모 상자."""
    LW, LEFT, TOP, RH, PH = 150, 56, 64, 30, 30
    W = LEFT + LW * len(LANES) + 16
    xi = {lid: LEFT + LW * i + LW / 2 for i, (lid, _n) in enumerate(LANES)}
    rows, y, n = [], TOP, 0
    for p, (pt, ps) in enumerate(PHASES):
        rows.append(("ph", y, pt, ps))
        y += PH
        for st in [s for s in SEQ if s[0] == p]:
            n += 1
            rows.append(("st", y, n, st))
            y += RH
        y += 6
    H = y + 10
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="seq" role="img" aria-label="레이어 간 시퀀스">', "<defs>"]
    for k, col in KCOL.items():
        o.append(f'<marker id="{idp}-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append(f'</defs><rect width="{W}" height="{H}" fill="#fff"/>')
    for lid, nm in LANES:
        x = xi[lid]
        assert tw(nm, 11) <= LW - 18, f"시퀀스 칸 이름이 넘침: {nm}"
        o.append(f'<rect x="{x - LW / 2 + 6}" y="8" width="{LW - 12}" height="44" rx="8" fill="#f8fafc" stroke="#94a3b8"/>'
                 f'<text x="{x}" y="26" font-size="13" font-weight="800" text-anchor="middle" fill="#0f172a">{esc(lid)}</text>'
                 f'<text x="{x}" y="43" font-size="11" text-anchor="middle" fill="#475569">{esc(nm)}</text>'
                 f'<line x1="{x}" y1="52" x2="{x}" y2="{H - 6}" stroke="#cbd5e1" stroke-width="1.4" stroke-dasharray="4 4"/>')
    for r in rows:
        if r[0] == "ph":
            _t, yy, pt, ps = r
            o.append(f'<rect x="6" y="{yy + 3}" width="{W - 12}" height="{PH - 6}" rx="6" fill="#f1f5f9" opacity=".92"/>'
                     f'<text x="16" y="{yy + PH / 2 + 4.5}" font-size="12.5" font-weight="800" fill="#0f172a">{esc(pt)}<tspan font-weight="400" fill="#475569">  —  {esc(ps)}</tspan></text>')
            continue
        _t, yy, n, (p, a, b, lb, k) = r
        cy = yy + RH / 2 + 4
        col = KCOL[k]
        o.append(f'<circle cx="24" cy="{cy - 4}" r="10" fill="{col}"/><text x="24" y="{cy}" font-size="10.5" font-weight="800" text-anchor="middle" fill="#fff">{n}</text>')
        if a == b:
            w = 14 + tw(lb, 11)
            x0 = min(max(xi[a] - w / 2, LEFT), W - 10 - w)
            o.append(f'<rect x="{x0:.1f}" y="{cy - 16}" width="{w:.1f}" height="21" rx="5" fill="#fff" stroke="{col}" stroke-width="1.4"/>'
                     f'<text x="{x0 + w / 2:.1f}" y="{cy - 1.5}" font-size="11" font-weight="700" text-anchor="middle" fill="{col}">{esc(lb)}</text>')
            continue
        x1, x2 = xi[a], xi[b]
        d = KDASH.get(k, "")
        da = f' stroke-dasharray="{d}"' if d else ""
        o.append(f'<line x1="{x1}" y1="{cy + 3}" x2="{x2 - (6 if x2 > x1 else -6)}" y2="{cy + 3}" stroke="{col}" stroke-width="2"{da} marker-end="url(#{idp}-{k})"/>')
        w = 10 + tw(lb, 10.5)
        mx = min(max((x1 + x2) / 2, LEFT + w / 2), W - 10 - w / 2)
        o.append(f'<rect x="{mx - w / 2:.1f}" y="{cy - 13}" width="{w:.1f}" height="14" fill="#fff" opacity=".9"/>'
                 f'<text x="{mx:.1f}" y="{cy - 2}" font-size="10.5" font-weight="600" text-anchor="middle" fill="#1e293b">{esc(lb)}</text>')
    o.append("</svg>")
    return "\n".join(o), (W, H)


def seq_story_html(PHASES, SEQ, STORY):
    out, n = [], 0
    for p, (pt, ps) in enumerate(PHASES):
        steps = [s for s in SEQ if s[0] == p]
        nums = f"{n + 1}~{n + len(steps)}" if len(steps) > 1 else str(n + 1)
        n += len(steps)
        out.append(f'<li><b>{esc(pt)}</b> <span class="snum">그림 {nums}단계</span><p>{esc(STORY[p])}</p></li>')
    return '<ol class="seqstory">' + "".join(out) + "</ol>"
