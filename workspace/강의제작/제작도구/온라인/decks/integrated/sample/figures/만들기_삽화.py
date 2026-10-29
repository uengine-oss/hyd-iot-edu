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


def main():
    out = {"설비_유압파워팩.svg": hyd_unit(), "리니지_0_전체.svg": lineage(0), "리니지_1_MQTT.svg": lineage(1),
           "리니지_2_DMZ.svg": lineage(2), "리니지_3_저장감지.svg": lineage(3), "원인후보.svg": causes(), "관계.svg": relation()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
