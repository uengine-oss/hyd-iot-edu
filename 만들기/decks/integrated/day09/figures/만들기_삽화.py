"""통합반 9일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
BPMN 도형은 표준 기호 모양을 따른다: 이벤트는 원(시작은 가는 테두리, 끝은 굵은 테두리, 경계는 겹테두리),
작업은 모서리가 둥근 사각형, 게이트웨이는 마름모, 시퀀스 흐름은 실선 화살표, 메시지 흐름은 점선 화살표.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon, approve_icon, arrow,
                    bell, circle, gauge, g, line, monitor, path, plc, poly, rect, server, svg)

HERE = Path(__file__).resolve().parent


# ───────────────────────── BPMN 도형 ─────────────────────────

def envelope(cx, cy, w, st: St):
    h = w * 0.68
    return [rect(cx - w / 2, cy - h / 2, w, h, 2, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {cx - w / 2},{cy - h / 2} L {cx},{cy + h * 0.08} L {cx + w / 2},{cy - h / 2}", stroke=st.line, sw=2.5)]


def clock(cx, cy, r, st: St):
    return [circle(cx, cy, r, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {cx},{cy - r * 0.62} L {cx},{cy} L {cx + r * 0.5},{cy + r * 0.22}", stroke=st.line, sw=2.5)]


def ev(cx, cy, r=18, kind="start", st: St = ON, marker=None, dashed=False, fill=None):
    """이벤트. kind: start(가는 테두리) · end(굵은 테두리) · boundary(겹테두리, dashed면 비중단형)."""
    f = fill or st.fill
    if kind == "start":
        o = [circle(cx, cy, r, fill=f, stroke=st.line, sw=3)]
    elif kind == "end":
        o = [circle(cx, cy, r - 2, fill=f, stroke=st.line, sw=max(6.5, r * 0.3))]
    else:
        da = "7 6" if dashed else None
        o = [circle(cx, cy, r, fill=f, stroke=st.line, sw=2.5, stroke_dasharray=da),
             circle(cx, cy, r * 0.76, fill="none", stroke=st.line, sw=2.5, stroke_dasharray=da)]
    if marker == "message":
        o += envelope(cx, cy, r * 1.05, st)
    elif marker == "timer":
        o += clock(cx, cy, r * 0.5, st)
    return o


def user_mark(x, y, st: St, s=1.0):
    return [circle(x + 9 * s, y + 6 * s, 5.5 * s, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {x},{y + 24 * s} Q {x},{y + 13 * s} {x + 9 * s},{y + 13 * s} Q {x + 18 * s},{y + 13 * s} {x + 18 * s},{y + 24 * s} Z",
                 fill=st.fill, stroke=st.line, sw=2.5)]


def gear_mark(x, y, st: St, s=1.0):
    cx, cy, r = x + 11 * s, y + 12 * s, 8 * s
    o = []
    for i in range(8):
        a = math.radians(i * 45)
        o.append(line(cx + r * math.cos(a), cy + r * math.sin(a), cx + (r + 4.5 * s) * math.cos(a), cy + (r + 4.5 * s) * math.sin(a),
                      stroke=st.line, sw=4 * s))
    o += [circle(cx, cy, r, fill=st.fill, stroke=st.line, sw=2.5), circle(cx, cy, r * 0.38, fill=st.line, stroke=st.line, sw=1)]
    return o


def task(cx, cy, w, h, st: St = ON, marker=None, fill=None, ms=1.0, r=12):
    o = [rect(cx - w / 2, cy - h / 2, w, h, r, fill=fill or st.fill, stroke=st.line)]
    if marker == "user":
        o += user_mark(cx - w / 2 + 9, cy - h / 2 + 7, st, ms)
    elif marker == "service":
        o += gear_mark(cx - w / 2 + 6, cy - h / 2 + 4, st, ms)
    return o


def gateway(cx, cy, s=28, st: St = ON, kind="x", fill=None):
    o = [poly([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=fill or st.fill, stroke=st.line, sw=3.5)]
    k = s * 0.36
    if kind == "x":
        o += [line(cx - k, cy - k, cx + k, cy + k, stroke=st.line, sw=max(4, s * 0.14)),
              line(cx + k, cy - k, cx - k, cy + k, stroke=st.line, sw=max(4, s * 0.14))]
    else:
        k = s * 0.48
        o += [line(cx - k, cy, cx + k, cy, stroke=st.line, sw=max(4, s * 0.14)),
              line(cx, cy - k, cx, cy + k, stroke=st.line, sw=max(4, s * 0.14))]
    return o


def msgflow(pts, color=NAVY, sw=3.5):
    """메시지 흐름: 점선, 출발에 빈 원, 도착에 빈 화살촉."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    a1, a2 = ang + math.radians(152), ang - math.radians(152)
    hd = poly([(x2, y2), (x2 + 16 * math.cos(a1), y2 + 16 * math.sin(a1)), (x2 + 16 * math.cos(a2), y2 + 16 * math.sin(a2))],
              fill=WHITE, stroke=color, sw=3)
    return [path(d, stroke=color, sw=sw, stroke_dasharray="10 8"), circle(pts[0][0], pts[0][1], 6, fill=WHITE, stroke=color, sw=3), hd]


def token(cx, cy, r=13):
    return [circle(cx, cy, r + 6, fill=WHITE, stroke=BLUE, sw=2.5), circle(cx, cy, r - 2, fill=BLUE, stroke=BLUE, sw=1)]


def check_mark(cx, cy, r=22, st: St = ON):
    return [circle(cx, cy, r, fill=SKY if st is ON else WHITE, stroke=st.line, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=st.line, sw=4.5)]


def cross_mark(cx, cy, r=22, st: St = ON):
    return [circle(cx, cy, r, fill=WHITE, stroke=st.line, sw=3.5),
            line(cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36, stroke=st.line, sw=4.5),
            line(cx + r * 0.36, cy - r * 0.36, cx - r * 0.36, cy + r * 0.36, stroke=st.line, sw=4.5)]


def doc_icon(cx, cy, st: St, mark=None):
    o = [path(f"M {cx - 30},{cy - 42} L {cx + 14},{cy - 42} L {cx + 30},{cy - 26} L {cx + 30},{cy + 42} L {cx - 30},{cy + 42} Z",
              fill=st.fill, stroke=st.line),
         path(f"M {cx + 14},{cy - 42} L {cx + 14},{cy - 26} L {cx + 30},{cy - 26}", stroke=st.line, sw=2.5)]
    for dy in (-12, 2, 16):
        o.append(line(cx - 18, cy + dy, cx + 18, cy + dy, stroke=st.line, sw=2.5))
    if mark == "check":
        o += [circle(cx + 22, cy + 30, 16, fill=st.accent, stroke=st.line, sw=3),
              path(f"M {cx + 14},{cy + 30} L {cx + 20},{cy + 36} L {cx + 30},{cy + 24}", stroke=st.line, sw=3.5)]
    elif mark == "wrench":
        o += [circle(cx + 22, cy + 30, 16, fill=st.accent, stroke=st.line, sw=3),
              line(cx + 14, cy + 38, cx + 28, cy + 24, stroke=st.line, sw=4.5)]
    return o


def person_icon(cx, cy, st: St):
    return [circle(cx, cy - 20, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 34},{cy + 38} Q {cx - 34},{cy + 4} {cx},{cy + 4} Q {cx + 34},{cy + 4} {cx + 34},{cy + 38} Z", fill=st.soft, stroke=st.line)]


def phone_icon(cx, cy, st: St):
    return [rect(cx - 20, cy - 36, 40, 72, 8, fill=st.fill, stroke=st.line), line(cx - 8, cy + 26, cx + 8, cy + 26, stroke=st.line, sw=3),
            rect(cx - 13, cy - 26, 26, 40, 3, fill=st.soft, stroke=st.line, sw=2)]


# ───────────────────────── 1. 추천 이후에 남은 일 / Task와 End-to-End ─────────────────────────

CH_X = (75, 225, 375, 525, 675, 825, 975, 1125)
CH_Y = 215


def chain(stage: str) -> str:
    """stage: 'after'(에이전트 추천까지만 진하게) · 'e2e'(전체를 밝히고 Task와 End-to-End의 범위를 괄호로)."""
    o: list[str] = []

    def st(i):
        if stage == "after":
            return ON if i == 1 else NORM if i == 0 else OFF
        return ON if i == 1 else NORM

    for i in range(7):
        s = st(i + 1)
        c = GREY if s is OFF else NAVY
        o.append(arrow([(CH_X[i] + 56, CH_Y), (CH_X[i + 1] - 58, CH_Y)], c, sw=4, size=12))
    fns = [lambda s: g(0, 0, 1.9, bell(0, -2, s), boost=0.6),
           lambda s: g(0, 0, 0.78, agent_icon(0, 4, s), boost=1.1),
           lambda s: g(0, 0, 0.78, approve_icon(-4, -4, s), boost=1.1),
           lambda s: g(0, 0, 0.62, plc(0, 0, s), boost=1.2),
           lambda s: gauge(0, 0, s, r=30, hot=s is ON, ang=-120),
           lambda s: g(0, 0, 0.7, doc_icon(0, 0, s, "wrench"), boost=1.1),
           lambda s: g(0, 0, 0.7, doc_icon(0, 0, s, "check"), boost=1.1)]
    for i, fn in enumerate(fns):
        s = st(i)
        o.append(circle(CH_X[i], CH_Y, 54, fill=PALE if s is ON else WHITE, stroke=s.line, sw=4 if s is not OFF else 3))
        o += [f'<g transform="translate({CH_X[i]} {CH_Y})">'] + fn(s) + ["</g>"]
    o += ev(CH_X[7], CH_Y, 30, "end", st(7))
    if stage == "e2e":
        def brace(x1, x2, y, up, color, sw):
            t = -14 if up else 14
            return path(f"M {x1},{y + t} L {x1},{y} L {x2},{y} L {x2},{y + t}", stroke=color, sw=sw)
        o.append(brace(CH_X[1] - 58, CH_X[1] + 58, 120, False, BLUE, 5))
        o.append(brace(CH_X[0] - 58, CH_X[7] + 40, 400, True, NAVY, 5))
    return svg(o)


# ───────────────────────── 2. BPM 생애주기 ─────────────────────────

def magnifier(cx, cy, st: St):
    return [circle(cx - 8, cy - 8, 26, fill=st.accent, stroke=st.line), line(cx + 12, cy + 12, cx + 36, cy + 36, stroke=st.line, sw=8)]


def mini_bpmn(cx, cy, st: St):
    return [line(cx - 34, cy, cx + 30, cy, stroke=st.line, sw=3), circle(cx - 40, cy, 9, fill=st.fill, stroke=st.line, sw=3),
            rect(cx - 22, cy - 13, 30, 26, 5, fill=st.accent, stroke=st.line, sw=3),
            poly([(cx + 30, cy - 15), (cx + 45, cy), (cx + 30, cy + 15), (cx + 15, cy)], fill=st.fill, stroke=st.line, sw=3)]


def play_icon(cx, cy, st: St):
    return [circle(cx, cy, 34, fill=st.accent, stroke=st.line), poly([(cx - 10, cy - 17), (cx + 18, cy), (cx - 10, cy + 17)], fill=st.line)]


def improve_icon(cx, cy, st: St):
    o = [rect(cx - 36 + i * 26, cy + 22 - h, 20, h, 3, fill=st.accent if i == 2 else st.soft, stroke=st.line, sw=3) for i, h in enumerate((20, 36, 54))]
    return o + [arrow([(cx - 38, cy - 10), (cx - 6, cy - 34)], BLUE if st is ON else st.line, sw=4, size=11)]


def bpm_cycle() -> str:
    o: list[str] = []
    C = (600, 262)
    pts = [(C[0] + 400 * math.cos(math.radians(a)), C[1] + 190 * math.sin(math.radians(a))) for a in (-90, -18, 54, 126, 198)]
    R = 62
    for i in range(5):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % 5]
        d_ = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / d_, (y2 - y1) / d_
        o.append(arrow([(x1 + ux * (R + 8), y1 + uy * (R + 8)), (x2 - ux * (R + 10), y2 - uy * (R + 10))], BLUE if i == 4 else NAVY, sw=5, size=15))
    icons = [magnifier, mini_bpmn, play_icon, lambda x, y, s: g(x, y, 0.72, monitor(0, 0, s, "chart"), boost=1.1), improve_icon]
    for (x, y), fn in zip(pts, icons):
        o.append(circle(x, y, R, fill=WHITE, sw=4))
        o += fn(x, y, ON)
    return svg(o)


# ───────────────────────── 3. BPMN 요소의 세 묶음 ─────────────────────────

def elements() -> str:
    o: list[str] = []
    for x, w in ((14, 470), (500, 300), (816, 370)):
        o.append(rect(x, 70, w, 430, 14, fill=LIGHT, stroke="none", sw=0))
    # 흐름 객체: 이벤트 · 작업 · 게이트웨이
    o += ev(95, 250, 40, "start", ON)
    o += task(248, 250, 150, 96, ON, fill=WHITE)
    o += gateway(410, 250, 52, ON, "x")
    # 연결 객체: 시퀀스 흐름 · 메시지 흐름
    o.append(arrow([(540, 215), (760, 215)], NAVY, sw=5, size=16))
    o += msgflow([(540, 360), (760, 360)])
    # 스윔레인: 풀과 레인
    o += [rect(846, 160, 310, 210, 4, fill=WHITE), rect(846, 160, 34, 210, 4, fill=PALE), line(880, 265, 1156, 265), line(926, 160, 926, 370)]
    o += task(1010, 212, 90, 52, NORM, r=9) + task(1080, 318, 90, 52, NORM, r=9)
    o.append(arrow([(1010, 238), (1010, 318), (1035, 318)], NAVY, sw=3.5, size=11))
    return svg(o)


# ───────────────────────── 4. 긴급 대응 프로세스의 BPMN 그림 ─────────────────────────

LY = {"person": (10, 120), "agent": (120, 260), "system": (260, 510)}
TW, TH = 132, 72
WIDE = {"T_agent": 150}
N = {"Start": (148, 172), "T_agent": (255, 172), "T_approve": (378, 65), "G_approved": (500, 65), "T_cmd": (500, 305),
     "T_reobs": (662, 305), "G_ok": (780, 305), "T_wo": (898, 305), "R_ok": (1048, 305), "E_end": (1158, 305),
     "R_fail": (780, 400), "R_rejected": (581, 400), "E_rejected": (581, 482), "T_notice": (410, 400), "E_notice": (410, 482),
     "B_overdue": (410, 101)}
FLOWS = {
    "F1": ("Start", "T_agent", [(166, 172), (180, 172)]),
    "F2": ("T_agent", "T_approve", [(330, 172), (345, 172), (345, 101)]),
    "F3": ("T_approve", "G_approved", [(444, 65), (472, 65)]),
    "F_approved": ("G_approved", "T_cmd", [(500, 93), (500, 269)]),
    "F_rejected": ("G_approved", "R_rejected", [(528, 65), (581, 65), (581, 364)]),
    "F4": ("T_cmd", "T_reobs", [(566, 305), (596, 305)]),
    "F5": ("T_reobs", "G_ok", [(728, 305), (752, 305)]),
    "F_yes": ("G_ok", "T_wo", [(808, 305), (832, 305)]),
    "F_no": ("G_ok", "R_fail", [(780, 333), (780, 364)]),
    "F6": ("T_wo", "R_ok", [(964, 305), (982, 305)]),
    "F7": ("R_ok", "E_end", [(1114, 305), (1140, 305)]),
    "F8": ("R_fail", "E_end", [(846, 400), (1158, 400), (1158, 323)]),
    "F_rej_end": ("R_rejected", "E_rejected", [(581, 436), (581, 464)]),
    "F_overdue": ("B_overdue", "T_notice", [(410, 119), (410, 364)]),
    "F_notice_end": ("T_notice", "E_notice", [(410, 436), (410, 464)]),
}
PATHS = {
    "approve": "Start F1 T_agent F2 T_approve F3 G_approved F_approved T_cmd F4 T_reobs F5 G_ok F_yes T_wo F6 R_ok F7 E_end",
    "reject": "Start F1 T_agent F2 T_approve F3 G_approved F_rejected R_rejected F_rej_end E_rejected",
    "wait": "Start F1 T_agent F2 T_approve B_overdue F_overdue T_notice F_notice_end E_notice",
    "people": "T_approve G_approved",
}


def flow(hot: str | None = None, tokens=(), lane: str | None = None) -> str:
    """긴급 대응 프로세스. hot: 진하게 보일 경로 이름(PATHS) — 나머지는 흐리게. tokens: 토큰을 놓을 요소 id.
    lane: 밝힐 레인 이름."""
    hs = set(PATHS[hot].split()) if hot else None

    def st(name):
        return ON if hs is None or name in hs else OFF

    o: list[str] = []
    # 풀과 레인
    o.append(rect(8, 10, 1184, 500, 4, fill=WHITE))
    for name, (y1, y2) in LY.items():
        if lane == name:
            o.append(rect(100, y1, 1092, y2 - y1, 0, fill=PALE, stroke="none", sw=0))
    o.append(rect(8, 10, 92, 500, 4, fill=LIGHT))
    for y in (120, 260):
        o.append(line(8, y, 1192, y, sw=3))
    o.append(line(100, 10, 100, 510, sw=3))
    o += g(54, 44, 0.42, approve_icon(-4, 0, ON))
    o += g(54, 160, 0.42, agent_icon(0, 6, ON))
    o += g(54, 360, 0.42, server(0, 0, ON))
    # 시퀀스 흐름
    for fid, (_a, _b, pts) in FLOWS.items():
        s = st(fid)
        o.append(arrow(pts, BLUE if hs and s is ON else NAVY if s is ON else GREY, sw=4 if hs and s is ON else 3.2, size=11))
    # 요소
    def tk(name, marker):
        s = st(name)
        return task(*N[name], WIDE.get(name, TW), TH, s, marker, fill=PALE if (hs and s is ON) or name in tokens else WHITE, ms=0.6)

    o += ev(*N["Start"], 18, "start", st("Start"), "message")
    o += tk("T_agent", None) + tk("T_approve", "user")
    for name in ("T_cmd", "T_reobs", "T_wo", "R_ok", "R_fail", "R_rejected", "T_notice"):
        o += tk(name, "service")
    o += gateway(*N["G_approved"], 28, st("G_approved")) + gateway(*N["G_ok"], 28, st("G_ok"))
    for name in ("E_end", "E_rejected", "E_notice"):
        o += ev(*N[name], 18, "end", st(name))
    o += ev(*N["B_overdue"], 18, "boundary", st("B_overdue"), "timer", dashed=True)
    for name in tokens:
        x, y = N[name]
        o += token(x + WIDE.get(name, TW) / 2 - 6, y - TH / 2 + 4) if name.startswith(("T_", "R_")) else token(x, y)
    return svg(o)


# ───────────────────────── 5. 이벤트 ─────────────────────────

def events() -> str:
    o: list[str] = []
    o += ev(220, 215, 78, "start", ON)
    o += ev(600, 215, 78, "start", ON, "message", fill=PALE)
    o += ev(980, 215, 78, "end", ON)
    return svg(o)


# ───────────────────────── 6. 작업의 종류 ─────────────────────────

def tasks() -> str:
    o: list[str] = []
    for x, mk, hot in ((210, None, True), (600, "user", False), (990, "service", False)):
        o += task(x, 200, 290, 170, ON, mk, fill=PALE if hot else WHITE, ms=2.0, r=22)
    return svg(o)


# ───────────────────────── 7. 배타 게이트웨이 ─────────────────────────

def gateway_xor() -> str:
    o: list[str] = []
    o += task(170, 170, 210, 110, NORM, "user", ms=1.3, r=16)
    o.append(arrow([(275, 170), (446, 170)], NAVY, sw=5, size=15))
    o += gateway(520, 170, 72, ON, "x", fill=PALE)
    o.append(arrow([(592, 170), (858, 170)], BLUE, sw=5, size=15))
    o.append(arrow([(520, 242), (520, 410), (858, 410)], NAVY, sw=5, size=15))
    o += task(965, 170, 210, 110, ON, "service", ms=1.3, r=16)
    o += task(965, 410, 210, 110, NORM, "service", ms=1.3, r=16)
    # 기본 흐름 표식(출발 쪽의 빗금)
    o.append(line(510, 268, 532, 250, sw=4))
    return svg(o)


# ───────────────────────── 8. 풀과 레인 ─────────────────────────

def pool_lane() -> str:
    o: list[str] = []
    o += [rect(40, 30, 1120, 460, 4, fill=WHITE), rect(40, 30, 70, 460, 4, fill=PALE), line(110, 30, 110, 490)]
    o += [line(110, 183, 1160, 183), line(110, 336, 1160, 336), line(330, 30, 330, 490)]
    o += g(220, 100, 0.7, approve_icon(-4, 0, ON), boost=1.1)
    o += g(220, 252, 0.7, agent_icon(0, 6, ON), boost=1.1)
    o += g(220, 405, 0.66, server(0, 0, ON), boost=1.1)
    o += task(500, 260, 190, 84, ON, None, fill=PALE, ms=1.2, r=14)
    o += task(760, 107, 190, 84, ON, "user", ms=1.2, r=14)
    o += task(1020, 413, 190, 84, ON, "service", ms=1.2, r=14)
    o.append(arrow([(595, 260), (760, 260), (760, 149)], NAVY, sw=4.5, size=14))
    o.append(arrow([(855, 107), (1020, 107), (1020, 371)], NAVY, sw=4.5, size=14))
    return svg(o)


# ───────────────────────── 9. 메시지 흐름 ─────────────────────────

def message_flow() -> str:
    o: list[str] = []
    for y in (20, 320):
        o += [rect(40, y, 1120, 180, 4, fill=WHITE), rect(40, y, 70, 180, 4, fill=PALE), line(110, y, 110, y + 180)]
    o += ev(180, 110, 22, "start", ON)
    o += task(380, 110, 200, 84, ON, r=14) + task(780, 110, 200, 84, ON, r=14)
    o += ev(1060, 110, 22, "end", ON)
    o += [arrow([(202, 110), (280, 110)], NAVY, sw=4.5, size=14), arrow([(480, 110), (680, 110)], NAVY, sw=4.5, size=14),
          arrow([(880, 110), (1038, 110)], NAVY, sw=4.5, size=14)]
    o += task(580, 410, 200, 84, ON, r=14)
    o += msgflow([(380, 152), (380, 410), (480, 410)], BLUE, sw=4)
    o += msgflow([(680, 410), (780, 410), (780, 152)], BLUE, sw=4)
    return svg(o)


# ───────────────────────── 10. 경계 타이머: 중단형과 비중단형 ─────────────────────────

def boundary() -> str:
    o: list[str] = []
    for i, x0 in enumerate((30, 630)):
        dashed = i == 1
        o.append(rect(x0, 70, 540, 430, 14, fill=LIGHT, stroke="none", sw=0))
        cx, cy = x0 + 170, 222
        main_on = dashed
        o += task(cx, cy, 220, 120, ON if main_on else OFF, "user", fill=PALE if main_on else WHITE, ms=1.4, r=18)
        o.append(arrow([(cx + 110, cy), (x0 + 500, cy)], NAVY if main_on else GREY, sw=5, size=15))
        o += ev(cx + 50, cy + 60, 30, "boundary", ON, "timer", dashed=dashed)
        o.append(arrow([(cx + 50, cy + 90), (cx + 50, 410), (x0 + 330, 410)], BLUE, sw=5, size=15))
        o += task(x0 + 420, 410, 170, 90, ON, "service", ms=1.2, r=14)
        if not dashed:
            o += cross_mark(cx - 70, cy + 14, 24, ON)
    return svg(o)


# ───────────────────────── 11. 승인을 받는 자리 ─────────────────────────

def approval_block() -> str:
    o: list[str] = []
    o += task(140, 150, 200, 100, NORM, None, ms=1.3, r=16)
    o.append(arrow([(240, 150), (330, 150)], NAVY, sw=4.5, size=14))
    o += task(440, 150, 220, 110, ON, "user", fill=PALE, ms=1.4, r=16)
    o.append(arrow([(550, 150), (640, 150)], NAVY, sw=4.5, size=14))
    o += gateway(700, 150, 60, ON, "x")
    o.append(arrow([(760, 150), (900, 150)], BLUE, sw=4.5, size=14))
    o += task(1010, 150, 220, 100, ON, "service", ms=1.3, r=16)
    o.append(arrow([(700, 210), (700, 400), (790, 400)], NAVY, sw=4.5, size=14))
    o += task(900, 400, 220, 100, ON, "service", ms=1.3, r=16)
    o.append(arrow([(1010, 400), (1110, 400)], NAVY, sw=4.5, size=14))
    o += ev(1140, 400, 28, "end", ON)
    o += ev(500, 205, 28, "boundary", ON, "timer", dashed=True)
    o.append(arrow([(500, 233), (500, 400), (410, 400)], NAVY, sw=4.5, size=14))
    o += task(300, 400, 220, 100, ON, "service", ms=1.3, r=16)
    o.append(arrow([(190, 400), (110, 400)], NAVY, sw=4.5, size=14))
    o += ev(80, 400, 28, "end", ON)
    return svg(o)


# ───────────────────────── 12. 병렬 게이트웨이와 하위 프로세스 ─────────────────────────

def parallel_sub() -> str:
    o: list[str] = []
    o += [rect(14, 70, 600, 430, 14, fill=LIGHT, stroke="none", sw=0), rect(634, 70, 552, 430, 14, fill=LIGHT, stroke="none", sw=0)]
    # 병렬: 갈라짐과 합류
    o += gateway(110, 285, 46, ON, "plus", fill=PALE)
    o += task(314, 190, 170, 84, ON, r=14) + task(314, 380, 170, 84, ON, r=14)
    o += gateway(518, 285, 46, ON, "plus", fill=PALE)
    o += [arrow([(110, 239), (110, 190), (229, 190)], NAVY, sw=4.5, size=14), arrow([(110, 331), (110, 380), (229, 380)], NAVY, sw=4.5, size=14),
          arrow([(399, 190), (518, 190), (518, 239)], NAVY, sw=4.5, size=14), arrow([(399, 380), (518, 380), (518, 331)], NAVY, sw=4.5, size=14)]
    o += [arrow([(30, 285), (64, 285)], NAVY, sw=4.5, size=13), arrow([(564, 285), (604, 285)], NAVY, sw=4.5, size=13)]
    # 하위 프로세스: 접힌 모양과 펼친 모양
    o += task(760, 208, 190, 92, ON, fill=PALE, r=16)
    o += [rect(746, 226, 28, 26, 3, fill=WHITE, sw=3), line(752, 239, 768, 239, sw=3), line(760, 231, 760, 247, sw=3)]
    o.append(path("M 760,256 L 760,300", stroke=BLUE, sw=4, stroke_dasharray="8 7"))
    o += [rect(660, 300, 500, 170, 16, fill=WHITE)]
    o += ev(710, 385, 18, "start", ON) + task(820, 385, 110, 66, ON, r=10) + task(980, 385, 110, 66, ON, r=10) + ev(1110, 385, 18, "end", ON)
    o += [arrow([(728, 385), (765, 385)], NAVY, sw=3.5, size=11), arrow([(875, 385), (925, 385)], NAVY, sw=3.5, size=11),
          arrow([(1035, 385), (1092, 385)], NAVY, sw=3.5, size=11)]
    return svg(o)


# ───────────────────────── 13. 프로세스 정의와 인스턴스 ─────────────────────────

def mini_flow(x, y, st: St, upto=5, tok=None, end=None):
    """작은 흐름 한 줄: 시작 · 작업 셋 · 끝. upto번째까지 지나간 것으로 칠한다."""
    xs = [x, x + 70, x + 160, x + 250, x + 330]
    o = [line(xs[0], y, xs[4], y, stroke=st.line, sw=3)]
    o.append(circle(xs[0], y, 13, fill=st.accent if upto >= 1 else st.fill, stroke=st.line, sw=3))
    for i in (1, 2, 3):
        o.append(rect(xs[i] - 32, y - 20, 64, 40, 7, fill=st.accent if upto > i else st.fill, stroke=st.line, sw=3))
    o.append(circle(xs[4], y, 12, fill=st.accent if upto >= 5 else st.fill, stroke=st.line, sw=6))
    if tok is not None:
        o += token(xs[tok], y + 32, 9)
    return o


def def_inst() -> str:
    o: list[str] = []
    # 정의: 설계도 한 장
    o += [rect(40, 110, 420, 300, 10, fill=PALE), rect(40, 110, 420, 46, 10, fill=NAVY)]
    o += mini_flow(85, 285, St(NAVY, WHITE, WHITE, WHITE), upto=0)
    ys = (138, 290, 442)
    for y in ys:
        o.append(arrow([(462, 260), (560, 260), (560, y), (668, y)], BLUE, sw=4.5, size=14))
    for i, y in enumerate(ys):
        o.append(rect(680, y - 56, 490, 112, 12, fill=WHITE))
    o += mini_flow(730, ys[0] + 16, ON, upto=5) + check_mark(1120, ys[0] + 16, 22)
    o += mini_flow(730, ys[1] + 16, ON, upto=3) + cross_mark(1120, ys[1] + 16, 22)
    o += mini_flow(730, ys[2] + 16, ON, upto=2, tok=2) + clock(1120, ys[2] + 16, 22, ON)
    return svg(o)


# ───────────────────────── 14. AS-IS와 TO-BE ─────────────────────────

def asis_tobe() -> str:
    o: list[str] = []
    o += [rect(14, 60, 1172, 200, 14, fill=LIGHT, stroke="none", sw=0), rect(14, 290, 1172, 220, 14, fill=PALE, stroke="none", sw=0)]
    # AS-IS: 사람이 전화와 기억으로 잇는다(점선, 끊긴 곳)
    xs = (300, 520, 740, 960)
    y = 160
    o += g(300, y, 1.7, bell(0, -2, NORM), boost=0.6)
    o += g(520, y, 0.8, person_icon(0, 0, NORM), boost=1.1)
    o += g(740, y, 0.8, phone_icon(0, 0, NORM), boost=1.1)
    o += g(960, y, 0.8, person_icon(0, 0, NORM), boost=1.1)
    for a, b in zip(xs, xs[1:]):
        o.append(path(f"M {a + 62},{y} L {b - 62},{y}", stroke=NAVY, sw=4, stroke_dasharray="4 12"))
    o.append(path(f"M {xs[3] + 62},{y} L 1130,{y}", stroke=GREY, sw=4, stroke_dasharray="4 12"))
    # TO-BE: 프로세스로 정의된 흐름
    y = 400
    o += ev(300, y, 24, "start", ON, "message")
    o += task(450, y, 150, 80, ON, r=12) + task(660, y, 150, 80, ON, "user", fill=WHITE, r=12)
    o += gateway(810, y, 36, ON, "x") + task(960, y, 150, 80, ON, "service", r=12) + ev(1110, y, 24, "end", ON)
    o += [arrow([(324, y), (375, y)], NAVY, sw=4, size=12), arrow([(525, y), (585, y)], NAVY, sw=4, size=12),
          arrow([(735, y), (774, y)], NAVY, sw=4, size=12), arrow([(846, y), (885, y)], NAVY, sw=4, size=12),
          arrow([(1035, y), (1086, y)], NAVY, sw=4, size=12)]
    return svg(o)


def main():
    out = {"남은일_추천뒤.svg": chain("after"), "남은일_종단.svg": chain("e2e"), "BPM주기.svg": bpm_cycle(), "요소묶음.svg": elements(),
           "흐름_전체.svg": flow(), "흐름_승인.svg": flow("approve"), "흐름_거절.svg": flow("reject"), "흐름_무응답.svg": flow("wait"),
           "흐름_토큰_승인대기.svg": flow(tokens=("T_approve",)), "흐름_토큰_둘.svg": flow(tokens=("T_approve", "T_notice")),
           "이벤트.svg": events(), "작업종류.svg": tasks(), "게이트웨이.svg": gateway_xor(), "풀과레인.svg": pool_lane(),
           "메시지흐름.svg": message_flow(), "경계타이머.svg": boundary(), "승인자리.svg": approval_block(),
           "병렬과하위.svg": parallel_sub(), "정의와인스턴스.svg": def_inst(), "현재와목표.svg": asis_tobe()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
