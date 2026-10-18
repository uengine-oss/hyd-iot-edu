"""통합반 4일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
화풍(색 · 선 굵기 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `조각_1일차.py`에서 그대로 가져온다.
앞 일차의 그림을 그대로 다시 쓰는 장은 그 파일을 이 폴더에 복사해 둔다(이 스크립트가 만들지 않는다):
관계.svg · 경로_1~3.svg · 흩어진정보.svg · 원인후보.svg(1일차), 두층_3.svg(2일차), 성과경로_5.svg · 그래프_조치후보_예측유온.png(3일차).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from 조각_1일차 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon,  # noqa: E402
                      approve_icon, arrow, bell, book_icon, circle, cylinder_db, dots, ellipse, equip_mini, fan, g, gauge,
                      graph_icon, head, line, path, plc, radiator, rect, svg)


# ───────────────────────── 작은 그림 조각 (4일차에서 새로 쓰는 것) ─────────────────────────

def doc(cx, cy, st: St, w=64, h=84, lines=5, mark=None):
    """문서 한 장. 오른쪽 위 귀가 접힌다. mark번째 줄을 강조한다."""
    x, y, f = cx - w / 2, cy - h / 2, 16
    o = [path(f"M {x},{y} L {x + w - f},{y} L {x + w},{y + f} L {x + w},{y + h} L {x},{y + h} Z", fill=st.fill, stroke=st.line),
         path(f"M {x + w - f},{y} L {x + w - f},{y + f} L {x + w},{y + f}", stroke=st.line, sw=2.5)]
    step = (h - 34) / max(lines - 1, 1)
    for i in range(lines):
        ly = y + 24 + i * step
        hot = mark is not None and i == mark
        o.append(line(x + 10, ly, x + w - (22 if i == lines - 1 else 10), ly, stroke=BLUE if hot and st is ON else st.line,
                      sw=5 if hot else 2.5))
    return o


def lock(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 9 * s},{cy - 4 * s} L {cx - 9 * s},{cy - 12 * s} A {9 * s} {9 * s} 0 0 1 {cx + 9 * s},{cy - 12 * s} L {cx + 9 * s},{cy - 4 * s}",
                 stroke=st.line, sw=3),
            rect(cx - 14 * s, cy - 4 * s, 28 * s, 22 * s, 4, fill=st.accent, stroke=st.line, sw=3),
            circle(cx, cy + 6 * s, 2.6 * s, fill=st.line, stroke=st.line, sw=1)]


def magnifier(cx, cy, st: St, r=17, check=False):
    o = [circle(cx, cy, r, fill=st.fill, stroke=st.line), line(cx + r * 0.72, cy + r * 0.72, cx + r * 1.55, cy + r * 1.55, stroke=st.line, sw=5)]
    if check:
        o.append(path(f"M {cx - r * 0.45},{cy} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.5},{cy - r * 0.36}", stroke=BLUE if st is ON else st.line, sw=3.5))
    return o


def check_badge(cx, cy, st: St, r=17):
    return [circle(cx, cy, r, fill=st.accent, stroke=st.line),
            path(f"M {cx - r * 0.47},{cy} L {cx - r * 0.1},{cy + r * 0.38} L {cx + r * 0.52},{cy - r * 0.36}", stroke=st.line, sw=4)]


def outline_doc(cx, cy, st: St):
    """구조 분석: 절 제목과 번호 단계가 구분된 문서."""
    w, h = 70, 88
    x, y = cx - w / 2, cy - h / 2
    o = [rect(x, y, w, h, 6, fill=st.fill, stroke=st.line),
         rect(x + 9, y + 11, 34, 9, 3, fill=st.accent, stroke=st.line, sw=2)]
    for k in range(3):
        ly = y + 36 + k * 16
        o += [circle(x + 15, ly, 4.2, fill=st.soft, stroke=st.line, sw=2), line(x + 26, ly, x + w - 10, ly, stroke=st.line, sw=2.5)]
    return o


def id_link(cx, cy, st: St):
    """식별자 매핑: 새 후보(점선 원)가 이미 있는 노드(꼬리표 달린 실선 원)를 가리킨다."""
    o = [circle(cx - 30, cy + 6, 17, fill=st.fill, stroke=st.line, sw=3, stroke_dasharray="6 5"),
         arrow([(cx - 11, cy + 6), (cx + 14, cy + 6)], BLUE if st is ON else st.line, sw=3.5, size=10),
         circle(cx + 32, cy + 6, 17, fill=st.accent, stroke=st.line),
         rect(cx + 14, cy - 34, 36, 15, 4, fill=st.fill, stroke=st.line, sw=2.5),
         line(cx + 32, cy - 19, cx + 32, cy - 11, stroke=st.line, sw=2.5)]
    return o


def quote_doc(cx, cy, st: St):
    """인용 대조: 문서의 한 줄과 돋보기."""
    return doc(cx - 10, cy - 2, st, w=58, h=80, lines=5, mark=2) + magnifier(cx + 22, cy + 20, st, r=15, check=True)


def load_graph(cx, cy, st: St):
    """적재: 그래프 DB로 들어가는 화살표."""
    return g(cx + 6, cy + 8, 0.82, cylinder_db(0, 0, st)[:4], boost=1.1) + [arrow([(cx - 46, cy - 40), (cx - 16, cy - 22)], BLUE if st is ON else st.line, sw=4, size=11)]


def query_graph(cx, cy, st: St):
    return g(cx - 6, cy - 2, 0.9, graph_icon(0, 0, st), boost=1.0) + magnifier(cx + 30, cy + 26, st, r=13)


def grid_icon(cx, cy, st: St, w=44, h=34, hot_col=None):
    """표(결정표 · 업무 DB의 표)."""
    x, y = cx - w / 2, cy - h / 2
    o = [rect(x, y, w, h, 4, fill=st.fill, stroke=st.line, sw=3), rect(x, y, w, h / 3, 4, fill=st.accent, stroke=st.line, sw=3)]
    for k in (1, 2):
        o.append(line(x + w * k / 3, y, x + w * k / 3, y + h, stroke=st.line, sw=2))
    o.append(line(x, y + h * 2 / 3, x + w, y + h * 2 / 3, stroke=st.line, sw=2))
    return o


def bars_icon(cx, cy, st: St):
    o = [line(cx - 20, cy + 16, cx + 20, cy + 16, stroke=st.line, sw=3)]
    for k, hh in enumerate((12, 22, 30)):
        o.append(rect(cx - 16 + k * 12, cy + 16 - hh, 8, hh, 2, fill=st.accent, stroke=st.line, sw=2.5))
    return o


def steps_icon(cx, cy, st: St):
    o = [rect(cx - 20, cy - 18, 40, 36, 5, fill=st.fill, stroke=st.line, sw=3)]
    for k in range(3):
        ly = cy - 9 + k * 9
        o += [circle(cx - 12, ly, 2.4, fill=st.line, stroke=st.line, sw=1), line(cx - 5, ly, cx + 13, ly, stroke=st.line, sw=2.2)]
    return o


# ───────────────────────── 1. 문서가 지식이 되는 일곱 단계 (단계별 강조) ─────────────────────────

def ingest_pipeline(stage: int = 0) -> str:
    """윗줄 네 칸, 아랫줄 세 칸(마지막 칸은 두 칸 너비). 칸마다 위에 그림, 아래에 라벨 자리.
    stage 0: 전체(3 · 4번 칸을 하늘색으로 묶는다). stage 1~7: 그 단계의 칸만 밝히고 나머지는 흐리게."""
    o: list[str] = []
    cw, ch, gap = 272, 220, 24
    x0 = 20
    rows = (44, 296)
    iy = 50          # 칸 위쪽에서 그림 중심까지

    def cell(i):
        return x0 + (i % 4) * (cw + gap), rows[i // 4]

    def st(i):
        return ON if stage in (0, i + 1) else OFF

    for i in range(7):
        x, y = cell(i)
        w = cw * 2 + gap if i == 6 else cw
        if stage == 0:
            if i in (2, 3):
                continue
            o.append(rect(x, y, w, ch, 14, fill=LIGHT, stroke="none", sw=0))
        elif stage == i + 1:
            o.append(rect(x, y, w, ch, 14, fill=PALE, stroke=SKY, sw=3))
        else:
            o.append(rect(x, y, w, ch, 14, fill=LIGHT, stroke="none", sw=0))
    if stage == 0:
        x2, y2 = cell(2)
        o.append(rect(x2, y2, cw * 2 + gap, ch, 14, fill=PALE, stroke=SKY, sw=2.5))
    for i in range(6):
        x, y = cell(i)
        col = BLUE if stage in (0, i + 1, i + 2) else GREY
        if i == 3:      # 윗줄 끝에서 아랫줄 처음으로
            xa = x + cw - 30
            xb = cell(4)[0] + 30
            ym = (rows[0] + ch + rows[1]) / 2
            o.append(arrow([(xa, y + ch + 2), (xa, ym), (xb, ym), (xb, rows[1] - 3)], col, sw=4.5, size=13))
        else:
            o.append(arrow([(x + cw - 10, y + iy), (x + cw + gap + 10, y + iy)], col, sw=4.5, size=13))
    k = 0.8
    parts = [
        lambda t: doc(-6, 0, t, w=60, h=80) + lock(26, 26, t, 1.0),
        lambda t: outline_doc(0, 0, t),
        lambda t: g(0, 6, 0.92, agent_icon(0, 0, t), boost=1.0),
        lambda t: id_link(0, 6, t),
        lambda t: doc(-14, -4, t, w=56, h=78, lines=5, mark=2) + g(20, 18, 0.62, approve_icon(0, 0, t), boost=1.3),
        lambda t: load_graph(0, 0, t),
        lambda t: query_graph(0, 0, t),
    ]
    for i, fn in enumerate(parts):
        x, y = cell(i)
        o += g(x + cw / 2, y + iy, k, fn(st(i)), boost=1.15)
    # 마지막 칸의 오른쪽 절반: 조치 방법에서 근거 문서까지 이어진 모습
    x, y = cell(6)
    t = st(6)
    bx, by = x + cw + gap + cw / 2, y + iy + 4
    o.append(arrow([(bx - 62, by), (bx - 24, by)], t.line, sw=3.5, size=11))
    o.append(arrow([(bx + 24, by), (bx + 60, by)], t.line, sw=3.5, size=11))
    o += [circle(bx - 88, by, 24, fill=t.accent, stroke=t.line, sw=3.5)] + g(bx - 88, by, 0.62, steps_icon(0, 0, t), boost=1.5)
    o += [circle(bx, by, 22, fill=WHITE, stroke=t.line, sw=3.5)]
    o += g(bx + 88, by, 0.72, doc(0, 0, t, lines=4, mark=1), boost=1.2)
    return svg(o)


# ───────────────────────── 2. 인용: 지식 한 건이 원문의 어느 구간을 가리키는가 ─────────────────────────

def citation() -> str:
    o: list[str] = []
    # 보관된 원문(쪽)
    px, py, pw, ph = 70, 60, 470, 420
    o += [rect(px + 14, py + 14, pw, ph, 10, fill=LIGHT, stroke=GREY, sw=2.5), rect(px, py, pw, ph, 10, fill=WHITE)]
    o.append(rect(px + 30, py + 30, 190, 16, 6, fill=NAVY, stroke="none", sw=0))
    ys = [py + 78 + k * 34 for k in range(10)]
    widths = (400, 380, 410, 300, 0, 250, 404, 396, 360, 220)
    hot = 6
    for k, (y, wd) in enumerate(zip(ys, widths)):
        if not wd:
            continue
        if k == 5:
            o.append(rect(px + 30, y - 7, wd, 14, 6, fill=NAVY, stroke="none", sw=0))
        elif k == hot:
            o.append(rect(px + 22, y - 15, wd + 16, 30, 6, fill=PALE, stroke=SKY, sw=3))
            o.append(rect(px + 30, y - 6, wd, 12, 6, fill=BLUE, stroke="none", sw=0))
        else:
            o.append(rect(px + 30, y - 6, wd, 12, 6, fill=GREY, stroke="none", sw=0))
    yh = ys[hot]
    # 구간의 시작과 끝 표시
    for xx in (px + 22, px + 22 + widths[hot] + 16):
        o += [line(xx, yh - 26, xx, yh + 26, stroke=NAVY, sw=3.5), line(xx - 7, yh - 26, xx + 7, yh - 26, stroke=NAVY, sw=3.5),
              line(xx - 7, yh + 26, xx + 7, yh + 26, stroke=NAVY, sw=3.5)]
    # 지식 한 건(조치 방법의 단계)
    nx, ny = 960, 180
    o.append(arrow([(nx - 96, ny + 34), (px + pw + 20, yh)], BLUE, sw=5, size=15))
    o += [circle(nx, ny, 86, fill=SKY, sw=4.5)] + g(nx, ny, 1.9, steps_icon(0, 0, NORM), boost=0.75)
    # 서버의 대조
    mx, my = 760, 400
    o += magnifier(mx, my, ON, r=34, check=True)
    o += dots(mx - 44, my - 26, px + pw - 30, yh + 22, color=GREY, gap=15, r=3)
    return svg(o)


# ───────────────────────── 3. 적재 묶음의 사슬과 되돌리기 ─────────────────────────

def batch_chain() -> str:
    o: list[str] = []
    xs = (200, 600, 1000)
    y, bw, bh = 255, 280, 220
    # 앞 묶음을 가리키는 화살표(새 묶음 → 앞 묶음)
    for a, b in ((1, 0), (2, 1)):
        o.append(arrow([(xs[a] - bw / 2 - 4, y), (xs[b] + bw / 2 + 10, y)], NAVY, sw=4.5, size=14))
    for i, x in enumerate(xs):
        cur = i == 2
        st = ON if cur else NORM
        o.append(rect(x - bw / 2, y - bh / 2, bw, bh, 14, fill=PALE if cur else WHITE, stroke=NAVY, sw=4.5 if cur else 3.5))
        o.append(rect(x - bw / 2, y - bh / 2, bw, 40, 14, fill=SKY if cur else LIGHT, stroke=NAVY, sw=4.5 if cur else 3.5))
        # 적재 전 상태 → 적재 후 상태(작은 그래프 둘)
        o += g(x - 70, y + 6, 0.62, graph_icon(0, 0, NORM), boost=1.2)
        o.append(arrow([(x - 26, y + 6), (x + 22, y + 6)], BLUE if cur else NAVY, sw=3.5, size=10))
        o += g(x + 70, y + 6, 0.62, graph_icon(0, 0, st), boost=1.2)
        o += [circle(x + 104, y - 14, 8, fill=SKY if cur else PALE, stroke=NAVY, sw=2.5)]
        # 묶음 위의 문서 판본
        o += g(x, y - bh / 2 - 44, 0.62, doc(0, 0, st, lines=4), boost=1.3)
        o.append(line(x, y - bh / 2 - 16, x, y - bh / 2 - 2, stroke=NAVY, sw=3))
    # 되돌리기: 가장 새 묶음에서 앞 묶음의 상태로
    xa, xb, yb = xs[2], xs[1], y + bh / 2
    o.append(path(f"M {xa},{yb + 6} C {xa},{yb + 86} {xb + 40},{yb + 86} {xb + 30},{yb + 22}", stroke=BLUE, sw=4.5, stroke_dasharray="10 9"))
    o.append(head(xb + 28, yb + 8, -math.pi / 2 - 0.12, BLUE, 15))
    return svg(o)


# ───────────────────────── 4. 업무 DB: 값이 아니라 값의 자리를 등록한다 ─────────────────────────

def input_slot() -> str:
    o: list[str] = []
    # 업무 DB의 표
    tx, ty, tw, th = 60, 130, 400, 300
    cols, rws = 4, 5
    cwid, rh = tw / cols, th / (rws + 1)
    hot = 2
    o += g(tx + 36, ty - 52, 0.62, cylinder_db(0, 0, NORM)[:4], boost=1.2)
    o.append(rect(tx, ty, tw, th, 10, fill=WHITE))
    o.append(rect(tx, ty, tw, rh, 10, fill=LIGHT))
    o.append(rect(tx + hot * cwid, ty, cwid, th, 4, fill=PALE, stroke=SKY, sw=3))
    for c in range(1, cols):
        o.append(line(tx + c * cwid, ty, tx + c * cwid, ty + th, stroke=GREY, sw=2))
    for r_ in range(1, rws + 1):
        o.append(line(tx, ty + r_ * rh, tx + tw, ty + r_ * rh, stroke=GREY, sw=2))
    for c in range(cols):
        o.append(rect(tx + c * cwid + 16, ty + rh / 2 - 6, cwid - 32, 12, 6, fill=NAVY, stroke="none", sw=0))
        for r_ in range(1, rws + 1):
            o.append(rect(tx + c * cwid + 16, ty + r_ * rh + rh / 2 - 5, (cwid - 32) * (0.5 + 0.1 * ((c + r_) % 4)), 10, 5,
                          fill=BLUE if c == hot else GREY, stroke="none", sw=0))
    # 지식 그래프 쪽: 규칙 → 입력 데이터 → 출처 시스템
    R, I, S = (760, 110), (760, 300), (1060, 300)
    o.append(arrow([(R[0], R[1] + 50), (I[0], I[1] - 66)], NAVY, sw=4.5, size=14))
    o.append(arrow([(I[0] + 62, I[1]), (S[0] - 56, S[1])], NAVY, sw=4.5, size=14))
    o += [circle(*R, 48, fill=WHITE, sw=4)] + g(R[0], R[1] - 2, 1.5, bell(0, 0, ON), boost=0.8)
    o += [circle(*I, 60, fill=SKY, sw=4.5)]
    o += [rect(I[0] - 30, I[1] - 20, 60, 40, 8, fill=WHITE, stroke=NAVY, sw=3.5, stroke_dasharray="8 6")]
    o += [circle(*S, 50, fill=WHITE, sw=4)] + g(S[0], S[1], 0.6, cylinder_db(0, 0, NORM)[:4], boost=1.3)
    # 등록: 열의 위치가 입력 데이터의 속성이 된다
    o.append(arrow([(tx + hot * cwid + cwid / 2, ty - 4), (tx + hot * cwid + cwid / 2, 70), (600, 70), (600, 270), (I[0] - 68, 286)], BLUE, sw=4.5, size=14))
    # 판단 시점의 조회: 값은 표에 남아 있고 그때 읽는다
    o += dots(tx + tw + 10, ty + th - rh * 1.5, I[0] - 40, I[1] + 60, color=NAVY, gap=17, r=3.4)
    return svg(o)


# ───────────────────────── 5. 네 일차의 흐름: 같은 그래프가 자란다 ─────────────────────────

def four_days() -> str:
    o: list[str] = []
    pw, ph, gap, x0, y0 = 240, 340, 28, 14, 70
    P = {"asset": (44, 62), "comp": (120, 62), "sen": (196, 62), "fm": (120, 158), "skill": (120, 256),
         "rule": (198, 256), "kpi": (198, 158), "cause": (42, 158), "doc": (44, 284)}
    r = 19

    def at(px, name):
        x, y = P[name]
        return px + x, y0 + y

    def lk(px, a, b, color=NAVY, sw=3.2, ra=r, rb=r):
        (ax, ay), (bx, by) = at(px, a), at(px, b)
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        return arrow([(ax + ux * (ra + 3), ay + uy * (ra + 3)), (bx - ux * (rb + 5), by - uy * (rb + 5))], color, sw=sw, size=9)

    def node(px, name, new, tag=False):
        x, y = at(px, name)
        out = [circle(x, y, r, fill=SKY if new else WHITE, stroke=NAVY, sw=3.2)]
        if tag:     # 종류 꼬리표(클래스)
            out.append(rect(x - 15, y - r - 13, 30, 10, 4, fill=NAVY if new else GREY, stroke="none", sw=0))
        return out

    for i in range(4):
        px = x0 + i * (pw + gap)
        o.append(rect(px, y0, pw, ph, 14, fill=LIGHT, stroke="none", sw=0))
        if i < 3:
            o.append(arrow([(px + pw + 2, y0 + ph / 2), (px + pw + gap + 2, y0 + ph / 2)], BLUE, sw=5, size=13))

    # 1일차: 손으로 그린 관계 그림(틀이 없다)
    px = x0
    pts = [(60, 80), (172, 66), (118, 172), (56, 266), (186, 260)]
    for a, b in ((0, 2), (1, 2), (2, 3), (2, 4)):
        (ax, ay), (bx, by) = pts[a], pts[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        o.append(arrow([(px + ax + ux * 24, y0 + ay + uy * 24), (px + bx - ux * 27, y0 + by - uy * 27)], NAVY, sw=3.2, size=9))
    for k, (x, y) in enumerate(pts):
        o.append(circle(px + x, y0 + y, 21, fill=SKY if k == 2 else WHITE, stroke=NAVY, sw=3.2, stroke_dasharray="7 5"))

    # 2일차: 종류(클래스)가 붙은 설비 구조
    px = x0 + (pw + gap)
    o += [lk(px, "asset", "comp", BLUE), lk(px, "comp", "sen", BLUE)]
    for n in ("asset", "comp", "sen"):
        o += node(px, n, True, tag=True)
    o += g(px + 120, y0 + 236, 1.0, cylinder_db(0, 0, ON)[:4], boost=1.0)

    # 3일차: 조치 · 규칙 · 성과 지표
    px = x0 + 2 * (pw + gap)
    o += [lk(px, "asset", "comp"), lk(px, "comp", "sen")]
    o += [lk(px, "fm", "comp", BLUE), lk(px, "fm", "skill", BLUE), lk(px, "rule", "skill", BLUE, ra=26), lk(px, "rule", "kpi", BLUE, ra=22, rb=22)]
    for n in ("asset", "comp", "sen"):
        o += node(px, n, False, tag=True)
    o += node(px, "fm", True, tag=False)
    x, y = at(px, "skill")
    o += [circle(x, y, 24, fill=SKY, stroke=NAVY, sw=3.2)] + g(x, y, 0.62, steps_icon(0, 0, NORM), boost=1.5)
    x, y = at(px, "rule")
    o += g(x, y, 0.9, grid_icon(0, 0, ON), boost=1.0)
    x, y = at(px, "kpi")
    o += g(x, y, 0.9, bars_icon(0, 0, ON), boost=1.0)

    # 4일차: 문서에서 온 원인 · 증거와 출처
    px = x0 + 3 * (pw + gap)
    o += [lk(px, "asset", "comp"), lk(px, "comp", "sen"), lk(px, "fm", "comp"), lk(px, "fm", "skill"),
          lk(px, "rule", "skill", ra=26), lk(px, "rule", "kpi", ra=22, rb=22)]
    o.append(lk(px, "cause", "fm", BLUE))
    # 출처 선: 조치 방법과 규칙에서 문서로
    (sx, sy), (dx, dy) = at(px, "skill"), at(px, "doc")
    o += dots(sx - 26, sy + 8, dx + 30, dy + 2, color=BLUE, gap=10, r=2.6)
    for n in ("asset", "comp", "sen"):
        o += node(px, n, False, tag=True)
    o += node(px, "fm", False)
    x, y = at(px, "skill")
    o += [circle(x, y, 24, fill=WHITE, stroke=NAVY, sw=3.2)] + g(x, y, 0.62, steps_icon(0, 0, NORM), boost=1.5)
    x, y = at(px, "rule")
    o += g(x, y, 0.9, grid_icon(0, 0, NORM), boost=1.0)
    x, y = at(px, "kpi")
    o += g(x, y, 0.9, bars_icon(0, 0, NORM), boost=1.0)
    o += node(px, "cause", True)
    x, y = at(px, "doc")
    o += g(x, y, 0.72, doc(0, 0, ON, lines=4, mark=1), boost=1.2)
    o += check_badge(x + 30, y + 30, ON, r=13)

    # 그 뒤: 에이전트
    ax = x0 + 4 * (pw + gap) - gap + 8
    o.append(arrow([(ax, y0 + ph / 2), (ax + 34, y0 + ph / 2)], BLUE, sw=5, size=13))
    o += g(ax + 84, y0 + ph / 2 + 6, 0.86, agent_icon(0, 0, ON), boost=1.0)
    return svg(o)


# ───────────────────────── 6. 원문 한 문장이 지식 후보로 갈라지는 모습 ─────────────────────────

def one_sentence() -> str:
    o: list[str] = []
    o.append(rect(40, 16, 1120, 92, 14, fill=LIGHT, stroke=NAVY, sw=3.5))
    o += g(92, 62, 0.62, doc(0, 0, ON, lines=4, mark=1), boost=1.3)
    S1, S2, F, C = (190, 300), (470, 420), (680, 300), (1010, 300)
    for (x, y), rr in ((S1, 52), (S2, 52), (F, 70), (C, 52)):
        o += dots(x, 116, x, y - rr - 12, color=GREY, gap=14, r=3)
    # 관계: 증상 → 고장 유형 → 구성 요소
    o.append(arrow([(S1[0] + 58, S1[1]), (F[0] - 80, F[1])], NAVY, sw=4.5, size=14))
    ang = math.atan2(F[1] - S2[1], F[0] - S2[0])
    o.append(arrow([(S2[0] + 58 * math.cos(ang), S2[1] + 58 * math.sin(ang)), (F[0] - 80 * math.cos(ang), F[1] - 80 * math.sin(ang))], NAVY, sw=4.5, size=14))
    o.append(arrow([(F[0] + 76, F[1]), (C[0] - 62, C[1])], NAVY, sw=4.5, size=14))
    # 이미 있는 대상: 실선 원 + 식별자 꼬리표 / 새 후보: 하늘색 점선 원
    for (x, y) in (S1, S2, C):
        o.append(circle(x, y, 52, fill=WHITE, sw=4))
        o += [rect(x + 22, y - 74, 52, 20, 5, fill=PALE, stroke=NAVY, sw=2.5), line(x + 34, y - 54, x + 30, y - 46, stroke=NAVY, sw=2.5)]
    o.append(circle(*F, 70, fill=SKY, sw=4.5, stroke_dasharray="12 8"))
    from 조각_1일차 import broken_cooler, thermo
    o += g(S1[0], S1[1], 1.0, thermo(-8, 24, ON, s=0.62, level=0.7) + [arrow([(16, 20), (16, -22)], BLUE, sw=3.5, size=9)], boost=1.0)
    o += gauge(S2[0], S2[1], ON, r=28, hot=True, ang=-140)
    o += g(F[0], F[1], 0.8, broken_cooler(0, 0, NORM), boost=1.0)
    o += g(C[0], C[1], 0.6, radiator(-44, -34, 88, 68, ON, fins=8, r=7), boost=1.3)
    return svg(o)


# ───────────────────────── 7. 세 층: 스키마, 인스턴스 데이터, 값 ─────────────────────────

def three_layers() -> str:
    """위에서 아래로 스키마(점선 상자) · 인스턴스 데이터(원) · 값(원천). 위 두 층이 지식 그래프, 맨 아래는 그래프 밖."""
    from 조각_1일차 import broken_cooler, calendar_icon, dusty_cooler
    o: list[str] = []
    cols = (430, 710, 990)                 # 고장 유형 · 원인 · 증거
    ys = (82, 247, 438)                    # 층의 가운데
    bx, bw, bhs = 250, 936, (144, 150, 140)
    yc, yi, yv = ys[0] + 14, ys[1] - 16, ys[2] - 20   # 클래스 상자 · 인스턴스 원 · 원천 그림의 가운데(이름을 얹을 자리를 둔다)
    for k, (y, bh) in enumerate(zip(ys, bhs)):
        o.append(rect(bx, y - bh / 2, bw, bh, 14, fill=PALE if k == 2 else LIGHT, stroke=SKY if k == 2 else "none", sw=3 if k == 2 else 0))
    # 스키마: 클래스(점선 상자)와 관계 유형 / 인스턴스 데이터: 그 정의에 맞추어 놓인 대상과 관계
    for a, b in ((1, 0), (1, 2)):
        s = 1 if cols[b] > cols[a] else -1
        o.append(arrow([(cols[a] + s * 82, yc), (cols[b] - s * 84, yc)], NAVY, sw=4, size=13))
        o.append(arrow([(cols[a] + s * 48, yi), (cols[b] - s * 50, yi)], NAVY, sw=4, size=13))
    for x in cols:
        o += dots(x, yc + 46, x, yi - 52, color=GREY, gap=12, r=2.8)
        o.append(rect(x - 78, yc - 36, 156, 72, 12, fill=WHITE, stroke=NAVY, sw=4, stroke_dasharray="11 9"))
        o.append(circle(x, yi, 44, fill=WHITE, stroke=NAVY, sw=4))
    o += g(cols[0], yi, 0.56, broken_cooler(0, 0, NORM), boost=1.3)
    o += g(cols[1], yi, 0.56, dusty_cooler(0, 0, NORM), boost=1.3)
    # 증거: 기준값이 그어진 눈금 막대(기준보다 낮은 쪽을 칠했다)
    ex = cols[2]
    o += [rect(ex - 28, yi - 8, 56, 16, 6, fill=WHITE, stroke=NAVY, sw=3), rect(ex - 28, yi - 8, 34, 16, 6, fill=SKY, stroke=NAVY, sw=3),
          line(ex + 6, yi - 20, ex + 6, yi + 20, stroke=NAVY, sw=4)]
    # 값: 그래프 밖의 원천. 증거의 기준에 대는 값은 판단하는 순간에 읽는다
    o += dots(ex, ys[1] + bhs[1] / 2 + 6, ex, yv - 42, color=BLUE, gap=11, r=3.4)
    o += gauge(ex - 56, yv, ON, r=28, hot=True, ang=-140)
    o += g(ex + 40, yv + 2, 0.6, cylinder_db(0, 0, ON)[:4], boost=1.3)
    o += g(cols[1], yv + 2, 0.56, plc(0, 0, NORM), boost=1.3)
    o += g(cols[0], yv + 2, 0.56, calendar_icon(0, 0, NORM), boost=1.3)
    return svg(o)


def main():
    out = {"인제스천_전체.svg": ingest_pipeline(0), **{f"인제스천_{k}.svg": ingest_pipeline(k) for k in range(1, 8)}, "인용.svg": citation(), "적재묶음_사슬.svg": batch_chain(),
           "입력데이터_자리.svg": input_slot(), "네일차_흐름.svg": four_days(), "한문장.svg": one_sentence(),
           "세층.svg": three_layers()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
