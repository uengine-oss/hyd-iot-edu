"""통합반 1일차 v3 샘플 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
색은 덱 색만, 선 그림(끝 둥글게), 그라디언트 · 그림자 · 필터 · <text> 없음.
"""
from __future__ import annotations

import math
from pathlib import Path

NAVY, SKY, BLUE, PALE, GREY, LIGHT, WHITE = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#F3F6F9", "#FFFFFF"
W, H = 1200, 520
SW = 3.5
HERE = Path(__file__).resolve().parent


class St:
    def __init__(self, line, fill, accent, soft):
        self.line, self.fill, self.accent, self.soft = line, fill, accent, soft


ON = St(NAVY, WHITE, SKY, PALE)
NORM = St(NAVY, WHITE, PALE, LIGHT)
OFF = St(GREY, WHITE, LIGHT, WHITE)


def el(tag, **kw):
    kw.setdefault("stroke-linecap", "round")
    kw.setdefault("stroke-linejoin", "round")
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items() if v is not None)
    return f"<{tag} {a}/>"


def rect(x, y, w, h, r=0, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("rect", x=x, y=y, width=w, height=h, rx=r, ry=r, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def line(x1, y1, x2, y2, stroke=NAVY, sw=SW, **kw):
    return el("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, stroke_width=sw, fill="none", **kw)


def path(d, stroke=NAVY, sw=SW, fill="none", **kw):
    return el("path", d=d, stroke=stroke, stroke_width=sw, fill=fill, **kw)


def circle(cx, cy, r, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("circle", cx=cx, cy=cy, r=r, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def ellipse(cx, cy, rx, ry, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("ellipse", cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def poly(pts, fill=NAVY, stroke="none", sw=0):
    return el("polygon", points=" ".join(f"{x:.1f},{y:.1f}" for x, y in pts), fill=fill, stroke=stroke, stroke_width=sw)


def head(x, y, ang, color, size=13):
    """(x, y)가 끝점인 화살촉. ang은 진행 방향(라디안)."""
    a1, a2 = ang + math.radians(152), ang - math.radians(152)
    return poly([(x, y), (x + size * math.cos(a1), y + size * math.sin(a1)),
                 (x + size * math.cos(a2), y + size * math.sin(a2))], fill=color)


def arrow(pts, color=NAVY, sw=4, size=13):
    """꺾은선 화살표. 마지막 점에 화살촉."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - size * 0.7 * math.cos(ang), y2 - size * 0.7 * math.sin(ang))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in [*pts[:-1], end])
    return path(d, stroke=color, sw=sw) + head(x2, y2, ang, color, size)


def svg(body: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
            + "\n".join(body) + "\n</svg>\n")


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def gauge(cx, cy, st: St, r=16, hot=False, ang=-50):
    """계기(센서 자리). 원 + 눈금 + 바늘."""
    o = [circle(cx, cy, r, fill=st.accent if hot else st.fill, stroke=st.line)]
    for a in (-150, -90, -30):
        ra = math.radians(a)
        o.append(line(cx + (r - 6) * math.cos(ra), cy + (r - 6) * math.sin(ra),
                      cx + (r - 3) * math.cos(ra), cy + (r - 3) * math.sin(ra), stroke=st.line, sw=2))
    ra = math.radians(ang)
    o.append(line(cx, cy + 2, cx + (r - 6) * math.cos(ra), cy + 2 + (r - 6) * math.sin(ra), stroke=st.line, sw=3))
    return o


def fan(cx, cy, r, st: St, blades=4, rot=20, hot=False):
    o = [circle(cx, cy, r, fill=st.fill, stroke=st.line)]
    for i in range(blades):
        a = rot + i * 360 / blades
        o.append(ellipse(cx, cy - r * 0.52, r * 0.21, r * 0.4, fill=st.accent if hot else st.soft, stroke=st.line, sw=3,
                         transform=f"rotate({a} {cx} {cy})"))
    o.append(circle(cx, cy, r * 0.17, fill=st.line, stroke=st.line, sw=2))
    return o


def radiator(x, y, w, h, st: St, fins=12, r=8):
    o = [rect(x, y, w, h, r, fill=st.fill, stroke=st.line)]
    step = (w - 20) / (fins - 1)
    for i in range(fins):
        fx = x + 10 + i * step
        o.append(line(fx, y + 10, fx, y + h - 10, stroke=GREY if st is not OFF else LIGHT, sw=2))
    return o


def dust(cx, cy, st: St, s=1.0):
    pts = [(-22, -14, 8), (-6, -20, 6), (10, -12, 9), (24, -18, 5), (-16, 4, 7), (2, 2, 10), (20, 6, 7),
           (-8, 20, 6), (12, 22, 8), (-26, 18, 5)]
    return [circle(cx + dx * s, cy + dy * s, rr * s, fill=GREY, stroke=st.line, sw=2) for dx, dy, rr in pts]


def thermo(cx, cy, st: St, s=1.0, level=0.6):
    """온도계. (cx, cy)는 구부 중심."""
    tw, th, br = 13 * s, 78 * s, 15 * s
    o = [rect(cx - tw / 2, cy - th - br * 0.6, tw, th + br, tw / 2, fill=st.fill, stroke=st.line),
         circle(cx, cy, br, fill=st.accent, stroke=st.line)]
    lh = th * level
    o.append(line(cx, cy - br * 0.4, cx, cy - br * 0.6 - lh, stroke=st.accent if st.accent != WHITE else st.line, sw=5 * s))
    return o


def equip_mini(cx, cy, st: St):
    return [rect(cx - 46, cy + 4, 92, 42, 6, fill=st.soft, stroke=st.line),
            path(f"M {cx - 40},{cy + 20} q 10,-6 20,0 t 20,0 t 20,0 t 20,0", stroke=st.line, sw=2),
            rect(cx - 40, cy - 38, 46, 32, 9, fill=st.fill, stroke=st.line),
            line(cx - 28, cy - 31, cx - 28, cy - 13, stroke=st.line, sw=2),
            line(cx - 17, cy - 31, cx - 17, cy - 13, stroke=st.line, sw=2),
            line(cx - 6, cy - 31, cx - 6, cy - 13, stroke=st.line, sw=2),
            line(cx + 6, cy - 22, cx + 14, cy - 22, stroke=st.line, sw=5),
            circle(cx + 28, cy - 22, 15, fill=st.accent, stroke=st.line),
            line(cx + 28, cy - 7, cx + 28, cy + 30, stroke=st.line, sw=4),
            line(cx - 30, cy - 6, cx - 30, cy + 4, stroke=st.line), line(cx - 4, cy - 6, cx - 4, cy + 4, stroke=st.line)]


def plc(cx, cy, st: St):
    o = [line(cx - 60, cy - 30, cx + 60, cy - 30, stroke=st.line, sw=6),
         rect(cx - 48, cy - 44, 96, 88, 6, fill=st.fill, stroke=st.line),
         rect(cx - 48, cy - 44, 26, 88, 6, fill=st.soft, stroke=st.line)]
    for dx in (-22, 2, 26):
        o.append(line(cx + dx, cy - 44, cx + dx, cy + 44, stroke=st.line))
    for i, dx in enumerate((-35, -10, 14, 37)):
        o.append(circle(cx + dx, cy - 28, 4, fill=st.accent if i in (0, 2) else st.fill, stroke=st.line, sw=2))
        for k in range(3):
            o.append(circle(cx + dx, cy + 6 + k * 13, 3, fill=st.fill, stroke=st.line, sw=2))
    return o


def server(cx, cy, st: St):
    o = [rect(cx - 44, cy - 48, 88, 96, 8, fill=st.fill, stroke=st.line)]
    for dy in (-16, 16):
        o.append(line(cx - 44, cy + dy, cx + 44, cy + dy, stroke=st.line))
    for dy in (-32, 0, 32):
        o.append(circle(cx - 28, cy + dy, 5, fill=st.accent, stroke=st.line, sw=2))
        o.append(line(cx - 12, cy + dy, cx + 30, cy + dy, stroke=st.line, sw=3))
    return o


def monitor(cx, cy, st: St, kind="hmi"):
    o = [rect(cx - 58, cy - 46, 116, 76, 7, fill=st.fill, stroke=st.line),
         line(cx, cy + 30, cx, cy + 44, stroke=st.line, sw=5), line(cx - 26, cy + 45, cx + 26, cy + 45, stroke=st.line, sw=5)]
    if kind == "hmi":
        o += [path(f"M {cx - 44},{cy + 10} A 20 20 0 0 1 {cx - 4},{cy + 10}", stroke=st.line),
              line(cx - 24, cy + 10, cx - 12, cy - 6, stroke=st.line, sw=3),
              rect(cx + 8, cy - 32, 12, 48, 3, fill=st.fill, stroke=st.line, sw=2.5),
              rect(cx + 8, cy - 6, 12, 22, 3, fill=st.accent, stroke=st.line, sw=2.5),
              rect(cx + 30, cy - 32, 12, 48, 3, fill=st.fill, stroke=st.line, sw=2.5),
              rect(cx + 30, cy - 20, 12, 36, 3, fill=st.accent, stroke=st.line, sw=2.5)]
    else:
        o += [path(f"M {cx - 44},{cy - 34} L {cx - 44},{cy + 16} L {cx + 46},{cy + 16}", stroke=st.line, sw=2.5),
              path(f"M {cx - 38},{cy + 6} L {cx - 20},{cy + 2} L {cx - 4},{cy - 18} L {cx + 10},{cy - 26} "
                   f"L {cx + 22},{cy - 8} L {cx + 40},{cy - 2}", stroke=BLUE if st is ON else st.line, sw=3.5)]
    return o


def window(cx, cy, st: St, kind="gate"):
    o = [rect(cx - 52, cy - 46, 104, 92, 8, fill=st.fill, stroke=st.line),
         line(cx - 52, cy - 24, cx + 52, cy - 24, stroke=st.line)]
    for dx in (-38, -27, -16):
        o.append(circle(cx + dx, cy - 35, 2.8, fill=st.line, stroke=st.line, sw=1))
    if kind == "gate":      # 벽의 틈으로 한 방향만 지나가는 화살표
        o += [line(cx, cy - 14, cx, cy, stroke=st.line, sw=5), line(cx, cy + 22, cx, cy + 36, stroke=st.line, sw=5),
              arrow([(cx - 36, cy + 11), (cx + 36, cy + 11)], BLUE if st is ON else st.line, sw=4, size=11)]
    else:                   # 기준선을 넘어 오르는 값
        o += [line(cx - 40, cy + 4, cx + 40, cy + 4, stroke=BLUE if st is ON else st.line, sw=2.5, stroke_dasharray="6 6"),
              path(f"M {cx - 40},{cy + 30} L {cx - 20},{cy + 26} L {cx - 2},{cy + 14} L {cx + 16},{cy - 4} L {cx + 38},{cy - 12}",
                   stroke=st.line, sw=3.5),
              circle(cx + 7, cy + 4, 5, fill=st.accent, stroke=st.line, sw=2)]
    return o


def bell(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 13 * s},{cy + 8 * s} Q {cx - 13 * s},{cy - 14 * s} {cx},{cy - 15 * s} "
                 f"Q {cx + 13 * s},{cy - 14 * s} {cx + 13 * s},{cy + 8 * s} L {cx + 18 * s},{cy + 13 * s} "
                 f"L {cx - 18 * s},{cy + 13 * s} Z", fill=st.accent, stroke=st.line, sw=3),
            circle(cx, cy + 19 * s, 3.2 * s, fill=st.line, stroke=st.line, sw=1)]


def logstrip(x, cy, st: St, n=7, cw=24, h=46):
    o = []
    for i in range(n):
        if i == n - 1:
            o.append(rect(x + i * cw, cy - h / 2, cw, h, 3, fill=st.fill, stroke=st.line, sw=2.5, stroke_dasharray="5 5"))
        else:
            o.append(rect(x + i * cw, cy - h / 2, cw, h, 3, fill=st.accent if i == n - 2 else st.soft, stroke=st.line, sw=3))
    return o


def cylinder_db(cx, cy, st: St):
    o = [path(f"M {cx - 42},{cy - 34} L {cx - 42},{cy + 34} A 42 14 0 0 0 {cx + 42},{cy + 34} L {cx + 42},{cy - 34}",
              fill=st.fill, stroke=st.line),
         ellipse(cx, cy - 34, 42, 14, fill=st.accent, stroke=st.line),
         path(f"M {cx - 42},{cy - 10} A 42 14 0 0 0 {cx + 42},{cy - 10}", stroke=st.line),
         path(f"M {cx - 42},{cy + 12} A 42 14 0 0 0 {cx + 42},{cy + 12}", stroke=st.line),
         circle(cx + 36, cy + 34, 17, fill=st.fill, stroke=st.line),
         path(f"M {cx + 36},{cy + 24} L {cx + 36},{cy + 34} L {cx + 44},{cy + 38}", stroke=st.line, sw=3)]
    return o


def pipe(d, inner=PALE, outer=NAVY):
    return [path(d, stroke=outer, sw=12), path(d, stroke=inner, sw=5.5)]


# ───────────────────────── 1. 유압 파워팩 ─────────────────────────

def hyd_unit() -> str:
    o: list[str] = []
    # 작동유 탱크
    o += [rect(70, 330, 400, 150, 12, fill=WHITE), rect(75, 374, 390, 101, 8, fill=PALE, stroke="none", sw=0),
          path("M 75,374 q 15,-8 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0",
               stroke=NAVY, sw=2.5)]
    # 배관: 흡입 · 토출 · 복귀(뜨거운 쪽) · 쿨러 출구
    o += pipe("M 300,318 L 300,448")
    o += pipe("M 300,240 L 300,110 L 760,110")
    o += pipe("M 820,140 L 820,232", inner=SKY)
    o += pipe("M 660,388 L 660,422 L 472,422")
    o += [rect(285, 440, 30, 22, 4, fill=WHITE, sw=3), line(293, 444, 293, 458, sw=2), line(300, 444, 300, 458, sw=2),
          line(307, 444, 307, 458, sw=2)]
    # 흐름 방향
    o += [head(300, 352, -math.pi / 2, NAVY, 12), head(300, 168, -math.pi / 2, NAVY, 12), head(640, 110, 0, NAVY, 12),
          head(820, 216, math.pi / 2, NAVY, 12), head(552, 422, math.pi, NAVY, 12)]
    # 모터와 펌프
    o += [rect(108, 242, 124, 76, 16, fill=WHITE), rect(124, 318, 22, 12, 2, fill=WHITE, sw=3), rect(194, 318, 22, 12, 2, fill=WHITE, sw=3)]
    for fx in (134, 154, 174, 194, 214):
        o.append(line(fx, 254, fx, 306, sw=2.5))
    o += [line(232, 280, 262, 280, sw=9), circle(300, 280, 40, fill=PALE), circle(287, 280, 15, fill=WHITE, sw=3),
          circle(313, 280, 15, fill=WHITE, sw=3)]
    # 부하: 유압 실린더
    o += [rect(760, 80, 200, 60, 8, fill=WHITE), rect(852, 85, 14, 50, 2, fill=NAVY, sw=2), line(866, 110, 1044, 110, sw=10),
          circle(1058, 110, 13, fill=WHITE)]
    # 오일 쿨러
    o += radiator(620, 232, 220, 158, ON, fins=15, r=10)
    o.append(path("M 820,232 L 820,264 L 652,264 A 23 23 0 0 0 652,310 L 808,310 A 23 23 0 0 1 808,356 L 660,356 L 660,388",
                  stroke=NAVY, sw=6))
    # 쿨러 팬과 바람
    o += fan(955, 311, 66, ON)
    for ay in (281, 311, 341):
        o.append(arrow([(884, ay), (850, ay)], SKY, sw=4, size=10))
    # 센서 자리
    o += [line(796, 178, 814, 178, sw=3)] + gauge(780, 178, ON, hot=True)
    o += [line(480, 84, 480, 104, sw=3)] + gauge(480, 68, NORM)
    o += [line(1004, 356, 1036, 384, sw=3)] + gauge(1048, 394, NORM)
    return svg(o)


# ───────────────────────── 2. 데이터 리니지 (단계별 강조) ─────────────────────────

R1, R2 = 200, 365
X = dict(equip=85, plc=245, emqx=410, ingest=607, log=814, det=1085, tsdb=870, graf=1085, fuxa=410)


def lineage(stage: int) -> str:
    states = {
        0: dict(on="equip plc emqx fuxa ingest log tsdb det graf", norm="", aon="all", anorm=""),
        1: dict(on="equip plc emqx", norm="fuxa ingest", aon="eq_plc plc_emqx emqx_fuxa emqx_ing", anorm=""),
        2: dict(on="ingest log", norm="emqx", aon="emqx_ing ing_log", anorm=""),
        3: dict(on="tsdb det", norm="log graf fuxa emqx", aon="log_tsdb log_det", anorm="tsdb_graf emqx_fuxa"),
    }[stage]

    def st(name):
        return ON if name in states["on"].split() else NORM if name in states["norm"].split() else OFF

    def ar(name, pts):
        if states["aon"] == "all" or name in states["aon"].split():
            return arrow(pts, BLUE, sw=5, size=14)
        if name in states["anorm"].split():
            return arrow(pts, NAVY, sw=3, size=11)
        return arrow(pts, GREY, sw=3, size=11)

    o: list[str] = []
    # 영역 띠: OT / DMZ / IT
    o += [rect(14, 8, 486, 504, 14, fill=LIGHT, stroke="none", sw=0),
          rect(514, 8, 186, 504, 14, fill=PALE if stage in (0, 2) else LIGHT, stroke=SKY if stage == 2 else "none", sw=2.5 if stage == 2 else 0),
          rect(714, 8, 472, 504, 14, fill=LIGHT, stroke="none", sw=0)]
    # 화살표(그림 조각보다 먼저)
    o += [ar("eq_plc", [(136, R1), (186, R1)]), ar("plc_emqx", [(302, R1), (358, R1)]),
          ar("emqx_ing", [(460, R1), (548, R1)]), ar("ing_log", [(664, R1), (722, R1)]),
          ar("emqx_fuxa", [(410, R1 + 54), (410, R2 - 54)]),
          ar("log_tsdb", [(870, R1 + 30), (870, R2 - 54)]), ar("log_det", [(904, R1), (1026, R1)]),
          ar("tsdb_graf", [(932, R2), (1020, R2)])]
    o += equip_mini(X["equip"], R1, st("equip"))
    o += plc(X["plc"], R1, st("plc"))
    o += server(X["emqx"], R1, st("emqx"))
    o += monitor(X["fuxa"], R2, st("fuxa"), "hmi")
    o += window(X["ingest"], R1, st("ingest"), "gate")
    o += logstrip(730, R1, st("log"))
    o += cylinder_db(X["tsdb"], R2, st("tsdb"))
    o += window(X["det"], R1, st("det"), "detect")
    o += bell(1163, R1 - 4, st("det"), 0.9)
    o += monitor(X["graf"], R2, st("graf"), "chart")
    return svg(o)


# ───────────────────────── 3. 원인 후보 ─────────────────────────

def causes() -> str:
    o: list[str] = []
    rows = (100, 262, 424)
    # 가지: 맨 위(확인된 원인)만 진하게
    for i, by in enumerate(rows):
        c, sw = (BLUE, 5) if i == 0 else (GREY, 4)
        o.append(path(f"M 196,262 L 250,262 C 310,262 300,{by} 360,{by} L 420,{by}", stroke=c, sw=sw))
        o.append(arrow([(486, by), (566, by)], c, sw=sw, size=13))
    o.append(path("M 196,262 L 250,262", stroke=BLUE, sw=5))
    # 증상: 온도계 + 오르는 화살표
    o += thermo(110, 300, ON, s=1.7, level=0.72)
    o.append(arrow([(166, 290), (166, 176)], BLUE, sw=5, size=14))
    # 가지마다 가르는 센서 자리
    o += gauge(453, rows[0], ON, r=30, hot=True, ang=-140)
    o += gauge(453, rows[1], NORM, r=30, ang=-120)
    o += gauge(453, rows[2], NORM, r=30, ang=-110)
    # 원인 1: 핀이 막힌 쿨러
    o += radiator(582, rows[0] - 46, 116, 92, ON, fins=9)
    o += dust(640, rows[0], ON, 1.25)
    # 원인 2: 흔들리는 팬
    o += fan(640, rows[1], 42, NORM, rot=35)
    for sgn in (-1, 1):
        for k, rr in enumerate((54, 66)):
            a0, a1 = math.radians(-28), math.radians(28)
            x0, y0 = 640 + sgn * rr * math.cos(a0), rows[1] + rr * math.sin(a0)
            x1, y1 = 640 + sgn * rr * math.cos(a1), rows[1] + rr * math.sin(a1)
            o.append(path(f"M {x0:.1f},{y0:.1f} A {rr} {rr} 0 0 {1 if sgn > 0 else 0} {x1:.1f},{y1:.1f}", stroke=NAVY, sw=3))
    # 원인 3: 더운 캐비닛
    cy = rows[2]
    o += [rect(596, cy - 50, 76, 100, 6, fill=WHITE), line(634, cy - 50, 634, cy + 50, sw=2.5)]
    for dy in (-30, -18, -6):
        o += [line(606, cy + dy, 624, cy + dy, sw=2.5), line(644, cy + dy, 662, cy + dy, sw=2.5)]
    o += [circle(628, cy + 12, 2.5, fill=NAVY, sw=1), circle(640, cy + 12, 2.5, fill=NAVY, sw=1)]
    for wx in (690, 708, 726):
        o.append(path(f"M {wx},{cy + 40} q -10,-13 0,-26 t 0,-26 t 0,-26", stroke=NAVY, sw=3))
    return svg(o)


# ───────────────────────── 4. 관계 그림 ─────────────────────────

def relation() -> str:
    o: list[str] = []
    A, B, C, D = (170, 200), (600, 200), (1030, 200), (600, 432)
    o += [arrow([(236, 200), (532, 200)], NAVY, sw=5, size=15), arrow([(964, 200), (668, 200)], NAVY, sw=5, size=15),
          arrow([(600, 268), (600, 370)], NAVY, sw=5, size=15)]
    o += [circle(*A, 60, fill=WHITE), circle(*B, 62, fill=SKY), circle(*C, 60, fill=WHITE), circle(*D, 56, fill=WHITE)]
    # 증상: 오르는 온도
    o += thermo(A[0] - 12, A[1] + 22, ON, s=0.72, level=0.7)
    o.append(arrow([(A[0] + 18, A[1] + 20), (A[0] + 18, A[1] - 30)], BLUE, sw=4, size=11))
    # 고장 유형: 제 구실을 못 하는 쿨러(사선)
    o += radiator(B[0] - 34, B[1] - 26, 68, 52, NORM, fins=7, r=6)
    o.append(line(B[0] - 40, B[1] + 34, B[0] + 40, B[1] - 34, stroke=NAVY, sw=5))
    # 원인: 핀에 낀 오염
    o += radiator(C[0] - 34, C[1] - 26, 68, 52, NORM, fins=7, r=6)
    o += dust(C[0], C[1], ON, 0.72)
    # 조치: 팬
    o += fan(D[0], D[1], 34, ON, rot=20, hot=True)
    return svg(o)



# ───────────────────────── 축소 배치 도우미 ─────────────────────────
import re


def g(cx, cy, k, parts, boost=None):
    """원점 기준으로 그린 조각을 (cx, cy)에 k배로 놓는다. 선 굵기는 너무 가늘어지지 않게 되돌린다."""
    b = boost if boost is not None else min(1 / k, 1.9) * 0.85
    body = "\n".join(parts)
    body = re.sub(r'stroke-width="([\d.]+)"', lambda m: f'stroke-width="{float(m.group(1)) * b:.2f}"', body)
    return [f'<g transform="translate({cx} {cy}) scale({k})">', body, "</g>"]


def graph_icon(cx, cy, st: St):
    pts = [(-30, -22), (32, -30), (4, 6), (-34, 30), (36, 28)]
    o = [line(cx + pts[a][0], cy + pts[a][1], cx + pts[b][0], cy + pts[b][1], stroke=st.line)
         for a, b in ((0, 2), (1, 2), (2, 3), (2, 4), (0, 1))]
    for i, (dx, dy) in enumerate(pts):
        o.append(circle(cx + dx, cy + dy, 13 if i == 2 else 10, fill=st.accent if i == 2 else st.fill, stroke=st.line))
    return o


def agent_icon(cx, cy, st: St):
    return [line(cx, cy - 44, cx, cy - 30, stroke=st.line), circle(cx, cy - 48, 5, fill=st.accent, stroke=st.line, sw=2.5),
            rect(cx - 40, cy - 30, 80, 62, 14, fill=st.fill, stroke=st.line),
            circle(cx - 16, cy - 4, 7, fill=st.accent, stroke=st.line, sw=2.5), circle(cx + 16, cy - 4, 7, fill=st.accent, stroke=st.line, sw=2.5),
            line(cx - 14, cy + 16, cx + 14, cy + 16, stroke=st.line), line(cx - 48, cy - 6, cx - 40, cy - 6, stroke=st.line, sw=5),
            line(cx + 40, cy - 6, cx + 48, cy - 6, stroke=st.line, sw=5)]


def approve_icon(cx, cy, st: St):
    return [circle(cx - 10, cy - 22, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 44},{cy + 38} Q {cx - 44},{cy + 4} {cx - 10},{cy + 4} Q {cx + 24},{cy + 4} {cx + 24},{cy + 38} Z", fill=st.fill, stroke=st.line),
            circle(cx + 30, cy + 20, 19, fill=st.accent, stroke=st.line),
            path(f"M {cx + 21},{cy + 20} L {cx + 28},{cy + 27} L {cx + 40},{cy + 13}", stroke=st.line, sw=4)]


def book_icon(cx, cy, st: St):
    return [path(f"M {cx},{cy - 34} Q {cx - 30},{cy - 48} {cx - 58},{cy - 38} L {cx - 58},{cy + 36} Q {cx - 30},{cy + 26} {cx},{cy + 40} Z", fill=st.fill, stroke=st.line),
            path(f"M {cx},{cy - 34} Q {cx + 30},{cy - 48} {cx + 58},{cy - 38} L {cx + 58},{cy + 36} Q {cx + 30},{cy + 26} {cx},{cy + 40} Z", fill=st.soft, stroke=st.line),
            *[line(cx - 46, cy + dy - 6, cx - 12, cy + dy, stroke=st.line, sw=2.5) for dy in (-18, -4, 10)],
            *[line(cx + 12, cy + dy, cx + 46, cy + dy - 6, stroke=st.line, sw=2.5) for dy in (-18, -4, 10)]]


def calendar_icon(cx, cy, st: St):
    o = [rect(cx - 50, cy - 40, 100, 84, 8, fill=st.fill, stroke=st.line), rect(cx - 50, cy - 40, 100, 24, 8, fill=st.accent, stroke=st.line),
         line(cx - 26, cy - 50, cx - 26, cy - 32, stroke=st.line, sw=5), line(cx + 26, cy - 50, cx + 26, cy - 32, stroke=st.line, sw=5)]
    for r_ in range(3):
        for c_ in range(4):
            hot = (r_, c_) == (1, 2)
            o.append(rect(cx - 38 + c_ * 20, cy - 6 + r_ * 15, 13, 9, 2, fill=st.line if hot else st.soft, stroke=st.line, sw=1.5))
    return o


def cabinet(cx, cy, st: St):
    o = [rect(cx - 38, cy - 50, 76, 100, 6, fill=st.fill, stroke=st.line), line(cx, cy - 50, cx, cy + 50, stroke=st.line, sw=2.5)]
    for dy in (-30, -18, -6):
        o += [line(cx - 28, cy + dy, cx - 10, cy + dy, stroke=st.line, sw=2.5), line(cx + 10, cy + dy, cx + 28, cy + dy, stroke=st.line, sw=2.5)]
    return o


def broken_cooler(cx, cy, st: St):
    return radiator(cx - 44, cy - 34, 88, 68, st, fins=8, r=7) + [line(cx - 52, cy + 44, cx + 52, cy - 44, stroke=st.line, sw=6)]


def dusty_cooler(cx, cy, st: St):
    return radiator(cx - 44, cy - 34, 88, 68, st, fins=8, r=7) + dust(cx, cy, st, 0.95)


def dots(x1, y1, x2, y2, color=GREY, gap=16, r=3.2):
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) // gap))
    return [circle(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n, r, fill=color, stroke="none", sw=0) for i in range(n + 1)]


# ───────────────────────── 5. HYD의 9개 기능 계층 ─────────────────────────

def layers(focus: str) -> str:
    """focus: 'all' 또는 '79'(Layer 7~9 강조)."""
    o: list[str] = []
    top, pitch, hgt = 40, 53, 47
    zones = {9: "I", 8: "I", 7: "I", 6: "OI", 5: "I", 4: "I", 3: "DI", 2: "O", 1: "O"}
    icons = {9: approve_icon, 8: agent_icon, 7: graph_icon, 6: lambda x, y, st: monitor(x, y, st, "hmi"),
             5: cylinder_db, 4: lambda x, y, st: window(x, y, st, "detect"), 3: None, 2: server, 1: equip_mini}
    for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
        o.append(rect(zx - 24, top - 4, 48, pitch * 9 + 2, 12, fill=LIGHT, stroke="none", sw=0))
    for i, n in enumerate(range(9, 0, -1)):
        y = top + i * pitch
        hot = focus == "79" and n >= 7
        dim = focus == "79" and n < 7
        st = ON if hot else NORM if not dim else OFF
        o.append(rect(14, y, 990, hgt, 10, fill=PALE if hot else LIGHT, stroke=SKY if hot else "none", sw=2.5 if hot else 0))
        yc = y + hgt / 2
        if n == 3:
            o += g(58, yc, 0.42, logstrip(-84, 0, st))
        else:
            o += g(58, yc, 0.40, icons[n](0, 0, st))
        for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
            if col in zones[n]:
                o.append(circle(zx, yc, 12, fill=SKY if not dim else GREY, stroke=NAVY if not dim else GREY, sw=3))
            else:
                o.append(circle(zx, yc, 3.5, fill=GREY, stroke="none", sw=0))
    return svg(o)


# ───────────────────────── 8. 흩어진 정보 ─────────────────────────

def scattered() -> str:
    o: list[str] = []
    C = (600, 205)
    spots = {"tsdb": (190, 90), "plc": (190, 335), "book": (985, 90), "cal": (985, 335)}
    for x, y in spots.values():
        dx, dy = C[0] - x, C[1] - y
        d_ = math.hypot(dx, dy)
        o += dots(x + dx * 120 / d_, y + dy * 120 / d_, C[0] - dx * 96 / d_, C[1] - dy * 96 / d_)
    o += [circle(*C, 78, fill=PALE, stroke=NAVY, sw=4)] + g(C[0], C[1] - 4, 2.4, bell(0, 0, ON), boost=0.55)
    o += g(*spots["tsdb"], 1.0, cylinder_db(0, 0, ON))
    o += g(*spots["plc"], 1.05, plc(0, 0, ON))
    o += g(*spots["book"], 1.05, book_icon(0, 0, ON))
    o += g(*spots["cal"], 1.05, calendar_icon(0, 0, ON))
    return svg(o)


# ───────────────────────── 9. 노드 · 관계 · 방향 ─────────────────────────

def node_rel() -> str:
    o: list[str] = []
    A, B = (250, 250), (950, 250)
    o.append(arrow([(366, 250), (834, 250)], NAVY, sw=8, size=24))
    o += [circle(*A, 108, fill=WHITE, sw=5), circle(*B, 108, fill=SKY, sw=5)]
    o += g(*A, 1.5, dusty_cooler(0, 0, ON), boost=0.8)
    o += g(*B, 1.5, broken_cooler(0, 0, NORM), boost=0.8)
    return svg(o)


# ───────────────────────── 10. 질문에 답하는 경로 (단계별 강조) ─────────────────────────

def walk(stage: int) -> str:
    P, S, F, K = (95, 205), (275, 205), (465, 205), (465, 432)
    Cs = [(700, 80), (700, 205), (700, 330)]
    Es = [(865, 80), (865, 205), (865, 330)]

    def stn(name):
        cur = {1: "P S F PS SF", 2: "C0 C1 C2 E0 E1 E2 CF0 CF1 CF2 CE0 CE1 CE2", 3: "K FK C0 E0"}[stage].split()
        done = {1: "", 2: "P S F PS SF", 3: "P S F PS SF CF0 CE0"}[stage].split()
        return ON if name in cur else NORM if name in done else OFF

    def ar(name, pts):
        st = stn(name)
        return arrow(pts, BLUE if st is ON else NAVY if st is NORM else GREY, sw=5 if st is ON else 3.5, size=14 if st is ON else 12)

    o: list[str] = []
    o += [ar("PS", [(143, 205), (225, 205)]), ar("SF", [(323, 205), (407, 205)]), ar("FK", [(465, 261), (465, 380)])]
    for i, (c, e) in enumerate(zip(Cs, Es)):
        ang = math.atan2(F[1] - c[1], F[0] - c[0])
        o.append(ar(f"CF{i}", [(c[0] + 48 * math.cos(ang), c[1] + 48 * math.sin(ang)), (F[0] - 58 * math.cos(ang), F[1] - 58 * math.sin(ang))]))
        o.append(ar(f"CE{i}", [(c[0] + 48, c[1]), (e[0] - 40, e[1])]))

    def node(c, r, name, parts_fn, k, fill_hot=False):
        st = stn(name)
        out = [circle(c[0], c[1], r, fill=(SKY if fill_hot else PALE) if st is ON else WHITE, stroke=st.line, sw=4 if st is not OFF else 3)]
        return out + g(c[0], c[1], k, parts_fn(0, 0, st), boost=1.0 if k > 0.6 else None)

    o += node(P, 46, "P", lambda x, y, st: bell(x, y - 3, st, 1.6), 1.0)
    o += node(S, 46, "S", lambda x, y, st: thermo(x - 8, y + 22, st, s=0.62, level=0.7) + [arrow([(x + 16, y + 18), (x + 16, y - 22)], BLUE if st is ON else st.line, sw=3.5, size=9)], 1.0)
    o += node(F, 54, "F", broken_cooler, 0.62, fill_hot=True)
    o += node(Cs[0], 44, "C0", dusty_cooler, 0.52)
    o += node(Cs[1], 44, "C1", lambda x, y, st: fan(x, y, 46, st, rot=35), 0.62)
    o += node(Cs[2], 44, "C2", cabinet, 0.52)
    for i, e in enumerate(Es):
        st = stn(f"E{i}")
        o += gauge(e[0], e[1], st, r=30, hot=(st is ON and (stage == 3 or i == 0)) or (stage == 3 and i == 0), ang=(-140, -120, -110)[i])
    o += node(K, 48, "K", lambda x, y, st: fan(x, y, 46, st, rot=20, hot=True), 0.7)
    return svg(o)



# ───────────────────────── 11. 계층 그림(줄 수를 줄여 크게) ─────────────────────────

def layer_rows(ns, hot=()) -> str:
    o: list[str] = []
    top = 40
    pitch = (H - top - 4) / len(ns)
    hgt = pitch - 6
    k = min(0.40 * pitch / 53, 0.95)
    zones = {9: "I", 8: "I", 7: "I", 6: "OI", 5: "I", 4: "I", 3: "DI", 2: "O", 1: "O"}
    icons = {9: approve_icon, 8: agent_icon, 7: graph_icon, 6: lambda x, y, st: monitor(x, y, st, "hmi"),
             5: cylinder_db, 4: lambda x, y, st: window(x, y, st, "detect"), 3: None, 2: server, 1: equip_mini}
    ix = 58 if len(ns) > 6 else 78 if len(ns) > 3 else 100
    for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
        o.append(rect(zx - 24, top - 4, 48, pitch * len(ns) + 2, 12, fill=LIGHT, stroke="none", sw=0))
    for i, n in enumerate(ns):
        y = top + i * pitch
        st = ON if n in hot else NORM
        o.append(rect(14, y, 990, hgt, 10, fill=PALE if n in hot else LIGHT, stroke=SKY if n in hot else "none", sw=2.5 if n in hot else 0))
        yc = y + hgt / 2
        if n == 3:
            o += g(ix, yc, k * 1.05, logstrip(-84, 0, st))
        else:
            o += g(ix, yc, k, icons[n](0, 0, st))
        for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
            if col in zones[n]:
                o.append(circle(zx, yc, 12, fill=SKY, stroke=NAVY, sw=3))
            else:
                o.append(circle(zx, yc, 3.5, fill=GREY, stroke="none", sw=0))
    return svg(o)


# ───────────────────────── 12. 설비에서 근거 문서까지의 연결 ─────────────────────────

def connect() -> str:
    o: list[str] = []
    N = {"sen": (200, 110), "comp": (600, 110), "asset": (1000, 110), "sym": (200, 270), "fm": (600, 270),
         "cause": (1000, 270), "skill": (600, 430), "doc": (1000, 430)}
    R = 44

    def link(a, b):
        (ax, ay), (bx, by) = N[a], N[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        ra = 52 if a == "fm" else R
        rb = 52 if b == "fm" else R
        return arrow([(ax + ux * (ra + 4), ay + uy * (ra + 4)), (bx - ux * (rb + 6), by - uy * (rb + 6))], NAVY, sw=4, size=13)

    for a, b in (("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("sym", "fm"), ("fm", "comp"), ("cause", "fm"),
                 ("fm", "skill"), ("skill", "doc")):
        o.append(link(a, b))
    for name, (x, y) in N.items():
        hot = name == "fm"
        o.append(circle(x, y, 52 if hot else R, fill=SKY if hot else WHITE, sw=4))
    o += gauge(*N["sen"], ON, r=26, hot=True)
    o += g(*N["comp"], 0.5, radiator(-44, -34, 88, 68, ON, fins=8, r=7))
    o += g(*N["asset"], 0.62, equip_mini(0, 0, ON), boost=1.2)
    o += g(N["sym"][0], N["sym"][1], 1.0, thermo(-8, 22, ON, s=0.6, level=0.7) + [arrow([(16, 18), (16, -22)], BLUE, sw=3.5, size=9)], boost=1.0)
    o += g(*N["fm"], 0.6, broken_cooler(0, 0, NORM))
    o += g(*N["cause"], 0.5, dusty_cooler(0, 0, ON))
    o += g(*N["skill"], 0.66, fan(0, 0, 46, ON, rot=20, hot=True), boost=1.0)
    o += g(*N["doc"], 0.52, book_icon(0, 0, ON))
    return svg(o)



# ───────────────────────── 13. 같은 그림에서 한 부분만 밝히는 판 ─────────────────────────
# 승인된 그림의 모양은 그대로 두고, 밝히지 않는 조각의 색만 흐리게 바꾼다(다시 그리지 않는다).

def dim(parts):
    out = []
    for p in parts:
        for a, b in ((NAVY, "#D3D9E1"), (BLUE, "#D3D9E1"), (SKY, "#F3F6F9"), (PALE, "#FFFFFF")):
            p = p.replace(a, b)
        out.append(p)
    return out


def pick(focus, name, parts):
    return parts if focus is None or name in focus else dim(parts)


def hyd_unit_f(focus=None) -> str:
    o: list[str] = []
    P = lambda name, parts: o.extend(pick(focus, name, parts))
    P("tank", [rect(70, 330, 400, 150, 12, fill=WHITE), rect(75, 374, 390, 101, 8, fill=PALE, stroke="none", sw=0),
               path("M 75,374 q 15,-8 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0",
                    stroke=NAVY, sw=2.5)])
    P("suction", pipe("M 300,318 L 300,448"))
    P("press", pipe("M 300,240 L 300,110 L 760,110"))
    P("ret", pipe("M 820,140 L 820,232", inner=SKY))
    P("out", pipe("M 660,388 L 660,422 L 472,422"))
    P("suction", [rect(285, 440, 30, 22, 4, fill=WHITE, sw=3), line(293, 444, 293, 458, sw=2), line(300, 444, 300, 458, sw=2),
                  line(307, 444, 307, 458, sw=2)])
    P("suction", [head(300, 352, -math.pi / 2, NAVY, 12)])
    P("press", [head(300, 168, -math.pi / 2, NAVY, 12), head(640, 110, 0, NAVY, 12)])
    P("ret", [head(820, 216, math.pi / 2, NAVY, 12)])
    P("out", [head(552, 422, math.pi, NAVY, 12)])
    pump = [rect(108, 242, 124, 76, 16, fill=WHITE), rect(124, 318, 22, 12, 2, fill=WHITE, sw=3), rect(194, 318, 22, 12, 2, fill=WHITE, sw=3)]
    for fx in (134, 154, 174, 194, 214):
        pump.append(line(fx, 254, fx, 306, sw=2.5))
    pump += [line(232, 280, 262, 280, sw=9), circle(300, 280, 40, fill=PALE), circle(287, 280, 15, fill=WHITE, sw=3),
             circle(313, 280, 15, fill=WHITE, sw=3)]
    P("pump", pump)
    P("load", [rect(760, 80, 200, 60, 8, fill=WHITE), rect(852, 85, 14, 50, 2, fill=NAVY, sw=2), line(866, 110, 1044, 110, sw=10),
               circle(1058, 110, 13, fill=WHITE)])
    P("cooler", radiator(620, 232, 220, 158, ON, fins=15, r=10) + [
        path("M 820,232 L 820,264 L 652,264 A 23 23 0 0 0 652,310 L 808,310 A 23 23 0 0 1 808,356 L 660,356 L 660,388",
             stroke=NAVY, sw=6)])
    fanp = fan(955, 311, 66, ON)
    for ay in (281, 311, 341):
        fanp.append(arrow([(884, ay), (850, ay)], SKY, sw=4, size=10))
    P("fan", fanp)
    P("ts1", [line(796, 178, 814, 178, sw=3)] + gauge(780, 178, ON, hot=True))
    P("ps1", [line(480, 84, 480, 104, sw=3)] + gauge(480, 68, NORM))
    P("vs1", [line(1004, 356, 1036, 384, sw=3)] + gauge(1048, 394, NORM))
    return svg(o)


def lineage_zone(zone: str) -> str:
    """리니지 그림에서 한 보안 영역만 밝힌다. zone: 'OT' | 'IT'."""
    on = {"OT": "equip plc emqx fuxa", "IT": "log tsdb det graf"}[zone].split()
    aon = {"OT": "eq_plc plc_emqx emqx_fuxa", "IT": "log_tsdb log_det tsdb_graf"}[zone].split()
    st = lambda name: ON if name in on else OFF
    ar = lambda name, pts: arrow(pts, BLUE, sw=5, size=14) if name in aon else arrow(pts, GREY, sw=3, size=11)
    o: list[str] = []
    for z, (x, w) in (("OT", (14, 486)), ("DMZ", (514, 186)), ("IT", (714, 472))):
        hot = z == zone
        o.append(rect(x, 8, w, 504, 14, fill=PALE if hot else LIGHT, stroke=SKY if hot else "none", sw=2.5 if hot else 0))
    o += [ar("eq_plc", [(136, R1), (186, R1)]), ar("plc_emqx", [(302, R1), (358, R1)]),
          ar("emqx_ing", [(460, R1), (548, R1)]), ar("ing_log", [(664, R1), (722, R1)]),
          ar("emqx_fuxa", [(410, R1 + 54), (410, R2 - 54)]),
          ar("log_tsdb", [(870, R1 + 30), (870, R2 - 54)]), ar("log_det", [(904, R1), (1026, R1)]),
          ar("tsdb_graf", [(932, R2), (1020, R2)])]
    o += equip_mini(X["equip"], R1, st("equip")) + plc(X["plc"], R1, st("plc")) + server(X["emqx"], R1, st("emqx"))
    o += monitor(X["fuxa"], R2, st("fuxa"), "hmi") + window(X["ingest"], R1, st("ingest"), "gate")
    o += logstrip(730, R1, st("log")) + cylinder_db(X["tsdb"], R2, st("tsdb")) + window(X["det"], R1, st("det"), "detect")
    o += bell(1163, R1 - 4, st("det"), 0.9) + monitor(X["graf"], R2, st("graf"), "chart")
    return svg(o)


def causes_f(focus: int) -> str:
    """원인 후보 그림에서 가지 하나만 밝힌다(0 핀 오염 · 1 팬 구동 불량 · 2 주변 온도 상승)."""
    o: list[str] = []
    rows = (100, 262, 424)
    for i, by in enumerate(rows):
        c, sw = (BLUE, 5) if i == focus else (GREY, 4)
        o.append(path(f"M 196,262 L 250,262 C 310,262 300,{by} 360,{by} L 420,{by}", stroke=c, sw=sw))
        o.append(arrow([(486, by), (566, by)], c, sw=sw, size=13))
    o.append(path("M 196,262 L 250,262", stroke=BLUE, sw=5))
    o += thermo(110, 300, ON, s=1.7, level=0.72)
    o.append(arrow([(166, 290), (166, 176)], BLUE, sw=5, size=14))
    angs = (-140, -120, -110)
    for i, by in enumerate(rows):
        gz = gauge(453, by, ON if i == focus else NORM, r=30, hot=(i == focus), ang=angs[i])
        o += gz if i == focus else dim(gz)
    c0 = radiator(582, rows[0] - 46, 116, 92, ON, fins=9) + dust(640, rows[0], ON, 1.25)
    c1 = fan(640, rows[1], 42, NORM, rot=35)
    for sgn in (-1, 1):
        for rr in (54, 66):
            a0, a1 = math.radians(-28), math.radians(28)
            x0, y0 = 640 + sgn * rr * math.cos(a0), rows[1] + rr * math.sin(a0)
            x1, y1 = 640 + sgn * rr * math.cos(a1), rows[1] + rr * math.sin(a1)
            c1.append(path(f"M {x0:.1f},{y0:.1f} A {rr} {rr} 0 0 {1 if sgn > 0 else 0} {x1:.1f},{y1:.1f}", stroke=NAVY, sw=3))
    cy = rows[2]
    c2 = [rect(596, cy - 50, 76, 100, 6, fill=WHITE), line(634, cy - 50, 634, cy + 50, sw=2.5)]
    for dy in (-30, -18, -6):
        c2 += [line(606, cy + dy, 624, cy + dy, sw=2.5), line(644, cy + dy, 662, cy + dy, sw=2.5)]
    c2 += [circle(628, cy + 12, 2.5, fill=NAVY, sw=1), circle(640, cy + 12, 2.5, fill=NAVY, sw=1)]
    for wx in (690, 708, 726):
        c2.append(path(f"M {wx},{cy + 40} q -10,-13 0,-26 t 0,-26 t 0,-26", stroke=NAVY, sw=3))
    for i, c in enumerate((c0, c1, c2)):
        o += c if i == focus else dim(c)
    return svg(o)


def relation_f(focus: str) -> str:
    """관계 그림에서 한 부분만 밝힌다. 'meet' = 증상 · 원인이 고장 유형에서 만남, 'act' = 조치."""
    A, B, C, D = (170, 200), (600, 200), (1030, 200), (600, 432)
    a1 = [arrow([(236, 200), (532, 200)], NAVY, sw=5, size=15)]
    a2 = [arrow([(964, 200), (668, 200)], NAVY, sw=5, size=15)]
    a3 = [arrow([(600, 268), (600, 370)], NAVY, sw=5, size=15)]
    nA = [circle(*A, 60, fill=WHITE)] + thermo(A[0] - 12, A[1] + 22, ON, s=0.72, level=0.7) + [
        arrow([(A[0] + 18, A[1] + 20), (A[0] + 18, A[1] - 30)], BLUE, sw=4, size=11)]
    nB = [circle(*B, 62, fill=SKY)] + radiator(B[0] - 34, B[1] - 26, 68, 52, NORM, fins=7, r=6) + [
        line(B[0] - 40, B[1] + 34, B[0] + 40, B[1] - 34, stroke=NAVY, sw=5)]
    nC = [circle(*C, 60, fill=WHITE)] + radiator(C[0] - 34, C[1] - 26, 68, 52, NORM, fins=7, r=6) + dust(C[0], C[1], ON, 0.72)
    nD = [circle(*D, 56, fill=WHITE)] + fan(D[0], D[1], 34, ON, rot=20, hot=True)
    on = {"meet": "a1 a2 A B C", "act": "a3 B D"}[focus].split()
    o: list[str] = []
    for name, parts in (("a1", a1), ("a2", a2), ("a3", a3), ("A", nA), ("B", nB), ("C", nC), ("D", nD)):
        o += parts if name in on else dim(parts)
    return svg(o)


def connect_f(focus: str) -> str:
    """연결 그림에서 한쪽만 밝힌다. 'asset' = 설비 · 부품 · 센서 쪽, 'diag' = 증상 · 고장 유형 · 원인 · 조치 · 근거 문서 쪽."""
    N = {"sen": (200, 110), "comp": (600, 110), "asset": (1000, 110), "sym": (200, 270), "fm": (600, 270),
         "cause": (1000, 270), "skill": (600, 430), "doc": (1000, 430)}
    R = 44
    on_nodes = {"asset": "sen comp asset", "diag": "sym fm cause skill doc"}[focus].split()
    on_links = {"asset": [("asset", "comp"), ("comp", "sen")],
                "diag": [("sym", "fm"), ("cause", "fm"), ("fm", "skill"), ("skill", "doc")]}[focus]

    def link(a, b):
        (ax, ay), (bx, by) = N[a], N[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        ra = 52 if a == "fm" else R
        rb = 52 if b == "fm" else R
        return arrow([(ax + ux * (ra + 4), ay + uy * (ra + 4)), (bx - ux * (rb + 6), by - uy * (rb + 6))], NAVY, sw=4, size=13)

    o: list[str] = []
    for a, b in (("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("sym", "fm"), ("fm", "comp"), ("cause", "fm"),
                 ("fm", "skill"), ("skill", "doc")):
        o += [link(a, b)] if (a, b) in on_links else dim([link(a, b)])
    icon = {"sen": gauge(*N["sen"], ON, r=26, hot=True),
            "comp": g(*N["comp"], 0.5, radiator(-44, -34, 88, 68, ON, fins=8, r=7)),
            "asset": g(*N["asset"], 0.62, equip_mini(0, 0, ON), boost=1.2),
            "sym": g(N["sym"][0], N["sym"][1], 1.0, thermo(-8, 22, ON, s=0.6, level=0.7) + [arrow([(16, 18), (16, -22)], BLUE, sw=3.5, size=9)], boost=1.0),
            "fm": g(*N["fm"], 0.6, broken_cooler(0, 0, NORM)),
            "cause": g(*N["cause"], 0.5, dusty_cooler(0, 0, ON)),
            "skill": g(*N["skill"], 0.66, fan(0, 0, 46, ON, rot=20, hot=True), boost=1.0),
            "doc": g(*N["doc"], 0.52, book_icon(0, 0, ON))}
    for name, (x, y) in N.items():
        hot = name == "fm"
        parts = [circle(x, y, 52 if hot else R, fill=SKY if hot else WHITE, sw=4)] + icon[name]
        o += parts if name in on_nodes else dim(parts)
    return svg(o)


def scattered_f(focus: str) -> str:
    """흩어진 정보 그림에서 한 곳만 밝힌다. 'val' = TimescaleDB와 PLC, 'mes' = MES."""
    C = (600, 205)
    spots = {"tsdb": (190, 90), "plc": (190, 335), "book": (985, 90), "cal": (985, 335)}
    on = {"val": "tsdb plc", "mes": "cal"}[focus].split()
    o: list[str] = []
    for x, y in spots.values():
        dx, dy = C[0] - x, C[1] - y
        d_ = math.hypot(dx, dy)
        o += dots(x + dx * 120 / d_, y + dy * 120 / d_, C[0] - dx * 96 / d_, C[1] - dy * 96 / d_)
    o += [circle(*C, 78, fill=PALE, stroke=NAVY, sw=4)] + g(C[0], C[1] - 4, 2.4, bell(0, 0, ON), boost=0.55)
    icons = {"tsdb": g(*spots["tsdb"], 1.0, cylinder_db(0, 0, ON)), "plc": g(*spots["plc"], 1.05, plc(0, 0, ON)),
             "book": g(*spots["book"], 1.05, book_icon(0, 0, ON)), "cal": g(*spots["cal"], 1.05, calendar_icon(0, 0, ON))}
    for name, parts in icons.items():
        o += parts if name in on else dim(parts)
    return svg(o)


NEW_ONLY: set = set()


def main():
    out = {"설비_유압파워팩.svg": hyd_unit(), "리니지_0_전체.svg": lineage(0), "리니지_1_MQTT.svg": lineage(1),
           "리니지_2_DMZ.svg": lineage(2), "리니지_3_저장감지.svg": lineage(3), "원인후보.svg": causes(), "관계.svg": relation(),
           "계층_0_전체.svg": layers("all"), "계층_1_L7-9.svg": layers("79"),
           "흩어진정보.svg": scattered(), "노드관계.svg": node_rel(),
           "경로_1.svg": walk(1), "경로_2.svg": walk(2), "경로_3.svg": walk(3),
           "계층_L1-6.svg": layer_rows([6, 5, 4, 3, 2, 1]), "계층_L7-9.svg": layer_rows([9, 8, 7], hot=(9, 8, 7)), "연결.svg": connect(),
           "설비_1_순환.svg": hyd_unit_f("tank suction press pump load ret out"), "설비_2_냉각.svg": hyd_unit_f("ret cooler fan out"),
           "설비_3_TS1.svg": hyd_unit_f("ret cooler ts1"), "리니지_OT.svg": lineage_zone("OT"), "리니지_IT.svg": lineage_zone("IT"),
           "원인후보_1.svg": causes_f(0), "원인후보_2.svg": causes_f(1), "원인후보_3.svg": causes_f(2),
           "관계_만남.svg": relation_f("meet"), "관계_조치.svg": relation_f("act"), "연결_설비쪽.svg": connect_f("asset"),
           "연결_진단쪽.svg": connect_f("diag"), "흩어진정보_값.svg": scattered_f("val"), "흩어진정보_MES.svg": scattered_f("mes")}
    for name, text in out.items():
        assert "<text" not in text
        if (HERE / name).exists() and name not in NEW_ONLY:
            continue          # 승인된 그림은 다시 쓰지 않는다
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
