"""실전반 6회차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

그리는 것은 포털에 등록된 수업 흐름 「냉각 긴급 대응」(it/process/procsvc/course_flows.json 의 c3_cooling)이다 —
풀 하나 · 칸 셋 · 시작 1 · 끝 4 · 작업 14 · 배타 분기 4 · 경계 타이머 1. 요소 id 는 그 정의의 id 를 그대로 쓴다.
BPMN 도형(이벤트 · 작업 · 게이트웨이 · 토큰)은 통합반 9일차 figures/만들기_삽화.py 의 함수를, 화풍은 공용 삽화_기본.py 를 쓴다.
작업종류 · 경계타이머는 통합반 9일차 그림과 같은 모양이고 표식만 상자 안쪽으로 옮겼다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "tools" / "deck"))   # 공용 삽화_기본.py
from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, OFF, ON, PALE, WHITE, agent_icon, approve_icon, arrow, g, head, line, path,  # noqa: E402
                    rect, server, svg, 점선_펴기)

_spec = importlib.util.spec_from_file_location("통합9_삽화", HERE.parents[2] / "integrated" / "day09" / "figures" / "만들기_삽화.py")
_b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_b)
# 작업 상자의 표식(톱니 · 사람)이 상자 왼쪽 위 테두리에 닿지 않게 안쪽으로 옮긴다 — 통합반 생성기의 task()가 부르는 함수를 바꿔 끼운다
_gear, _user = _b.gear_mark, _b.user_mark
_b.gear_mark = lambda x, y, st, s=1.0: _gear(x + 7 * s, y + 7 * s, st, s)
_b.user_mark = lambda x, y, st, s=1.0: _user(x + 3 * s, y + 4 * s, st, s)
ev, task, gateway, token = _b.ev, _b.task, _b.gateway, _b.token

# ───────────────────────── 냉각 긴급 대응 전체 ─────────────────────────

LANES = {"person": (10, 120), "agent": (120, 240), "system": (240, 510)}
TW, TH = 90, 48
WIDE = {"T_agent": 110, "T_approve": 100}
N = {"Start": (125, 180), "T_agent": (215, 180), "T_approve": (330, 65), "B_overdue": (300, 89), "G_approved": (430, 65),
     "R_rejected": (430, 285), "E_rejected": (430, 365), "T_notice": (300, 455), "E_notice": (390, 455),
     "G_action": (560, 365), "T_cmd": (645, 285), "T_reobs": (760, 285), "G_ok": (860, 285), "T_wo": (955, 285),
     "R_ok": (1065, 285), "R_kind": (645, 365), "E_kind": (725, 365), "R_fail": (860, 365), "E_end": (1165, 365),
     "T_wo_only": (645, 455), "T_fix": (760, 455), "T_reobs_wo": (875, 455), "G_wo_ok": (980, 455), "R_wo_only": (1075, 455)}
FLOWS = {
    "F1": [(143, 180), (160, 180)],
    "F2": [(215, 156), (215, 65), (280, 65)],
    "F3": [(380, 65), (408, 65)],
    "F_rejected": [(430, 87), (430, 261)],
    "F_rej_end": [(430, 309), (430, 349)],
    "F_overdue": [(300, 107), (300, 431)],
    "F_notice_end": [(345, 455), (374, 455)],
    "F_approved": [(452, 65), (520, 65), (520, 365), (538, 365)],
    "F_control": [(560, 343), (560, 285), (600, 285)],
    "F_other": [(582, 365), (600, 365)],
    "F_kind_end": [(690, 365), (709, 365)],
    "F_work_order": [(560, 387), (560, 455), (600, 455)],
    "F4": [(690, 285), (715, 285)],
    "F5": [(805, 285), (838, 285)],
    "F_yes": [(882, 285), (910, 285)],
    "F6": [(1000, 285), (1020, 285)],
    "F7": [(1110, 285), (1165, 285), (1165, 349)],
    "F_no": [(860, 307), (860, 341)],
    "F8": [(905, 365), (1149, 365)],
    "F_wo_only": [(690, 455), (715, 455)],
    "F_fix": [(805, 455), (830, 455)],
    "F_reobs_wo": [(920, 455), (958, 455)],
    "F_wo_yes": [(1002, 455), (1030, 455)],
    "F_wo_only_end": [(1120, 455), (1165, 455), (1165, 381)],
    "F_wo_no": [(980, 433), (980, 410), (880, 410), (880, 389)],
}
SERVICE = ("R_rejected", "T_notice", "T_cmd", "T_reobs", "T_wo", "R_ok", "R_kind", "R_fail", "T_wo_only", "T_fix",
           "T_reobs_wo", "R_wo_only")
GATEWAYS = ("G_approved", "G_action", "G_ok", "G_wo_ok")
ENDS = ("E_rejected", "E_notice", "E_kind", "E_end")
# 조치 종류 갈림(G_action)과 그 뒤 세 갈래 — 밝힐 때 쓴다
ACTION = set("G_action F_control F_other F_work_order T_cmd F4 T_reobs F5 G_ok F_yes T_wo F6 R_ok F7 F_no R_fail F8 E_end "
             "R_kind F_kind_end E_kind T_wo_only F_wo_only T_fix F_fix T_reobs_wo F_reobs_wo G_wo_ok F_wo_yes R_wo_only "
             "F_wo_only_end F_wo_no".split())


def cooling(tokens=(), hot: set | None = None) -> str:
    """tokens: 토큰을 놓을 요소 id. hot: 진하게 둘 요소 · 선 id 묶음(나머지는 흐리게)."""
    def st(name):
        return ON if hot is None or name in hot else OFF

    o: list[str] = [rect(8, 10, 1184, 500, 4, fill=WHITE), rect(8, 10, 92, 500, 4, fill=LIGHT)]
    for y in (120, 240):
        o.append(line(8, y, 1192, y, sw=3))
    o.append(line(100, 10, 100, 510, sw=3))
    o += g(54, 44, 0.42, approve_icon(-4, 0, ON))
    o += g(54, 160, 0.42, agent_icon(0, 6, ON))
    o += g(54, 355, 0.42, server(0, 0, ON))
    for fid, pts in FLOWS.items():
        s = st(fid)
        o.append(arrow(pts, (BLUE if hot else NAVY) if s is ON else GREY, sw=3.2, size=10))

    def tk(name, marker):
        s = st(name)
        return task(*N[name], WIDE.get(name, TW), TH, s, marker, fill=PALE if name in tokens else WHITE, ms=0.5, r=9)

    o += ev(*N["Start"], 16, "start", st("Start"), "message")
    o += tk("T_agent", None) + tk("T_approve", "user")
    for name in SERVICE:
        o += tk(name, "service")
    for name in GATEWAYS:
        o += gateway(*N[name], 22, st(name))
    for name in ENDS:
        o += ev(*N[name], 16, "end", st(name))
    o += ev(*N["B_overdue"], 16, "boundary", st("B_overdue"), "timer", dashed=True)
    for name in tokens:
        x, y = N[name]
        o += token(x + WIDE.get(name, TW) / 2 - 4, y - TH / 2 + 2, r=10)
    return svg(o)


# ───────────────────────── 승인 뒤 조치 종류로 갈리는 세 갈래(크게) ─────────────────────────

def action_branches() -> str:
    """조치 종류? 갈림에서 나가는 세 갈래: 위 = 설비 명령 있음, 가운데 = 그 밖(기본 흐름), 아래 = 작업지시만."""
    o: list[str] = []
    W2, H2, STEP = 190, 74, 225
    gx, gy = 160, 260
    top, bot = 90, 430
    xs = [360 + STEP * i for i in range(3)]          # 360 · 585 · 810

    def row(y, n, fills=None):
        for i in range(n):
            o.extend(task(xs[i], y, W2, H2, ON, "service", fill=(fills or {}).get(i, WHITE), ms=0.9))
            if i < n - 1:
                o.append(arrow([(xs[i] + W2 / 2, y), (xs[i + 1] - W2 / 2 - 4, y)], NAVY, sw=4, size=12))

    o += gateway(gx, gy, 44, ON)
    o.append(arrow([(20, gy), (gx - 46, gy)], NAVY, sw=4, size=12))
    # 위: 냉각 명령 → 재관측 → 유온 정상?
    o.append(arrow([(gx, gy - 46), (gx, top), (xs[0] - W2 / 2 - 4, top)], NAVY, sw=4, size=12))
    row(top, 2)
    o.append(arrow([(xs[1] + W2 / 2, top), (xs[2] - 40, top)], NAVY, sw=4, size=12))
    o += gateway(xs[2], top, 34, ON)
    # 가운데: 결과 보고 → 실행하지 않음
    o.append(arrow([(gx + 46, gy), (xs[0] - W2 / 2 - 4, gy)], NAVY, sw=4, size=12))
    row(gy, 1, {0: PALE})
    o.append(arrow([(xs[0] + W2 / 2, gy), (xs[1] - 32, gy)], NAVY, sw=4, size=12))
    o += ev(xs[1], gy, 26, "end", ON)
    # 아래: 작업지시 등록 → 정비 수행 → 재관측 → 유온 정상?
    o.append(arrow([(gx, gy + 46), (gx, bot), (xs[0] - W2 / 2 - 4, bot)], NAVY, sw=4, size=12))
    row(bot, 3)
    o.append(arrow([(xs[2] + W2 / 2, bot), (1040, bot)], NAVY, sw=4, size=12))
    o += gateway(1076, bot, 34, ON)
    return svg(o)


# ───────────────────────── 오케스트레이션: 조정자 하나와 수행자 넷 ─────────────────────────

def dashed_arrow(pts, color=BLUE, sw=3.5, size=12):
    """점선 꺾은선 화살표(일을 맡기는 선). 마지막 점에 화살촉."""
    import math
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - size * 0.7 * math.cos(ang), y2 - size * 0.7 * math.sin(ang))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in [*pts[:-1], end])
    return path(d, stroke=color, sw=sw, stroke_dasharray="10 7") + head(x2, y2, ang, color, size)


def orchestra() -> str:
    """왼쪽 조정자에서 버스 한 줄로 오른쪽 수행자 넷에 일을 맡기고(점선), 에이전트의 결과는 위쪽으로 돌아온다(실선). 교차 0."""
    o: list[str] = [rect(14, 14, 400, 492, 14, fill=LIGHT, stroke="none", sw=0), rect(500, 14, 686, 492, 14, fill=LIGHT, stroke="none", sw=0)]
    o.append(rect(70, 220, 300, 120, 14, fill=WHITE))                       # 조정자
    ys = (110, 230, 350, 455)                                              # 에이전트 · 운전원 · 설비 제어 · 정비 시스템
    for y in ys:
        o.append(rect(600, y - 40, 540, 80, 12, fill=WHITE))
    bus = 450
    o.append(path(f"M 370,280 L {bus},280", stroke=BLUE, sw=3.5, stroke_dasharray="10 7"))
    o.append(path(f"M {bus},{ys[0] + 15} L {bus},{ys[-1]}", stroke=BLUE, sw=3.5, stroke_dasharray="10 7"))
    for i, y in enumerate(ys):
        yy = y + 15 if i == 0 else y
        o.append(dashed_arrow([(bus, yy), (600, yy)]))
    o.append(arrow([(700, ys[0] - 40), (700, 40), (220, 40), (220, 220)], NAVY, sw=4, size=12))   # 추천안이 돌아온다
    return svg(o)


def main():
    out = {"냉각흐름.svg": cooling(), "냉각흐름_승인대기.svg": cooling(tokens=("T_approve",)),
           "냉각흐름_조치종류.svg": cooling(hot=ACTION), "조치종류갈림.svg": action_branches(),
           "오케스트레이션.svg": orchestra(), "작업종류.svg": _b.tasks(), "경계타이머.svg": _b.boundary()}
    for name, text in out.items():
        assert "<text" not in text
        text = 점선_펴기(text)   # 빌더(PyMuPDF)는 stroke-dasharray를 실선으로 그린다
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
