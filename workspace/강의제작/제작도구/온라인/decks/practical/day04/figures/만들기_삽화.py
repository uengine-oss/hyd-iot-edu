"""실전반 4회차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 통합반 6회차 figures/삽화_기본.py에서 가져온다.
사용: python 만들기_삽화.py   → 이 폴더에 SVG를 쓴다. 유온 빈 구간 그림은 설비유온_그리기.py가 따로 만든다.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'integrated/day06/figures'))
from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, OFF, ON, PALE, SKY, WHITE, agent_icon, arrow, circle, dust, fan, g, line, path,  # noqa: E402
                    poly, radiator, rect, svg)


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def doc(cx, cy, st=ON, w=62, h=78, hot=None):
    """문서: 줄 넷. hot은 강조할 줄 번호."""
    o = [rect(cx - w / 2, cy - h / 2, w, h, 6, fill=st.fill, stroke=st.line)]
    for i, k in enumerate((0.8, 0.62, 0.78, 0.5)):
        y = cy - h / 2 + 18 + i * 15
        x0 = cx - w / 2 + 10
        if i == hot:
            o.append(rect(x0 - 3, y - 6, (w - 14), 12, 4, fill=SKY, stroke='none', sw=0))
        o.append(line(x0, y, x0 + (w - 20) * k, y, stroke=st.line, sw=2.5))
    return o


def model(cx, cy, st=ON):
    """언어 모델: 상자 안의 이어진 점."""
    pts = [(-24, -14), (-24, 14), (0, 0), (24, -14), (24, 14)]
    o = [rect(cx - 46, cy - 34, 92, 68, 14, fill=st.fill, stroke=st.line)]
    for a, b in ((0, 2), (1, 2), (2, 3), (2, 4)):
        o.append(line(cx + pts[a][0], cy + pts[a][1], cx + pts[b][0], cy + pts[b][1], stroke=st.line, sw=2.5))
    for i, (x, y) in enumerate(pts):
        o.append(circle(cx + x, cy + y, 6.5, fill=SKY if i == 2 else WHITE, stroke=st.line, sw=2.5))
    return o


def lens(cx, cy, st=ON, r=19):
    return [line(cx + r * 0.7, cy + r * 0.7, cx + r * 1.55, cy + r * 1.55, stroke=st.line, sw=6),
            circle(cx, cy, r, fill=st.accent, stroke=st.line)]


def bubble(cx, cy, st=ON):
    """질문 말풍선."""
    return [path(f'M {cx - 38},{cy - 26} H {cx + 38} Q {cx + 46},{cy - 26} {cx + 46},{cy - 18} V {cx * 0 + cy + 12} Q {cx + 46},{cy + 20} {cx + 38},{cy + 20} '
                 f'H {cx - 8} L {cx - 22},{cy + 36} L {cx - 22},{cy + 20} H {cx - 38} Q {cx - 46},{cy + 20} {cx - 46},{cy + 12} V {cy - 18} Q {cx - 46},{cy - 26} {cx - 38},{cy - 26} Z',
                 fill=st.fill, stroke=st.line),
            line(cx - 26, cy - 8, cx + 26, cy - 8, stroke=st.line, sw=2.5), line(cx - 26, cy + 6, cx + 8, cy + 6, stroke=st.line, sw=2.5)]


def dial(cx, cy, r, high=None, st=ON):
    """계기. high=False는 낮은 눈금, True는 높은 눈금, None은 아직 읽지 않아 바늘이 없다."""
    stroke = st.line if high is not None else GREY
    o = [circle(cx, cy, r, fill=WHITE, stroke=stroke, sw=3.5)]
    for a, b in ((-0.8, -0.6), (0, -1), (0.8, -0.6)):
        o.append(line(cx + a * r * 0.72, cy + b * r * 0.72, cx + a * r * 0.92, cy + b * r * 0.92, stroke=stroke, sw=2.5))
    if high is not None:
        tx, ty = (0.62, -0.5) if high else (-0.62, -0.5)
        o += [line(cx, cy + 4, cx + tx * r, cy + ty * r, stroke=BLUE if high else NAVY, sw=4), circle(cx, cy + 4, 4, fill=NAVY, stroke=NAVY, sw=1)]
    else:
        for x in (-10, 0, 10):       # 비어 있는 값: 점 셋
            o.append(circle(cx + x, cy + 6, 2.2, fill=GREY, stroke=GREY, sw=1))
    return o


def check(cx, cy, r=26):
    return [circle(cx, cy, r, fill=SKY, stroke=NAVY, sw=3.5),
            path(f'M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}', stroke=NAVY, sw=5)]


def unknown(cx, cy, r=26):
    """확인하지 못한 자리: 회색 고리와 점 셋."""
    return [circle(cx, cy, r, fill=WHITE, stroke=GREY, sw=3.5)] + [circle(cx + x, cy, 3, fill=GREY, stroke=GREY, sw=1) for x in (-10, 0, 10)]


def clock(cx, cy, r=26, st=ON, fill=WHITE):
    return [circle(cx, cy, r, fill=fill, stroke=st.line, sw=3.5), line(cx, cy, cx, cy - r * 0.62, stroke=st.line, sw=4), line(cx, cy, cx + r * 0.46, cy + r * 0.2, stroke=st.line, sw=4)]


def padlock(cx, cy, st=ON):
    return [path(f'M {cx - 15},{cy - 8} V {cy - 20} Q {cx - 15},{cy - 36} {cx},{cy - 36} Q {cx + 15},{cy - 36} {cx + 15},{cy - 20} V {cy - 8}', stroke=st.line, sw=4),
            rect(cx - 25, cy - 8, 50, 38, 7, fill=st.accent, stroke=st.line), circle(cx, cy + 8, 5, fill=WHITE, stroke=st.line, sw=2.5)]


def empty_list(cx, cy, st=ON):
    """머리만 있고 행이 없는 목록."""
    return [rect(cx - 42, cy - 32, 84, 64, 7, fill=st.fill, stroke=st.line), rect(cx - 42, cy - 32, 84, 18, 7, fill=st.accent, stroke=st.line)]


def cut_doc(cx, cy, st=ON):
    """아래가 잘린 문서: 윗줄만 있고 물결 아래가 비었다."""
    o = [path(f'M {cx - 31},{cy + 14} V {cy - 34} Q {cx - 31},{cy - 39} {cx - 26},{cy - 39} H {cx + 26} Q {cx + 31},{cy - 39} {cx + 31},{cy - 34} V {cy + 14} '
              f'Q {cx + 21},{cy + 24} {cx + 10},{cy + 14} Q {cx},{cy + 4} {cx - 10},{cy + 14} Q {cx - 21},{cy + 24} {cx - 31},{cy + 14} Z', fill=st.fill, stroke=st.line)]
    for i, k in enumerate((0.8, 0.6, 0.72)):
        o.append(line(cx - 21, cy - 24 + i * 14, cx - 21 + 42 * k, cy - 24 + i * 14, stroke=st.line, sw=2.5))
    return o


def seg_line(x1, x2, y, color=GREY, on=16, off=12, sw=4):
    """끊어진 선. 렌더에서 실선이 되지 않게 짧은 선 여러 개로 그린다."""
    o, x = [], x1
    while x < x2:
        o.append(line(x, y, min(x + on, x2), y, stroke=color, sw=sw))
        x += on + off
    return o


def seg_box(x, y, w, h, color=GREY, on=16, off=12, sw=3):
    o = seg_line(x, x + w, y, color, on, off, sw) + seg_line(x, x + w, y + h, color, on, off, sw)
    for xx in (x, x + w):
        yy = y
        while yy < y + h:
            o.append(line(xx, yy, xx, min(yy + on, y + h), stroke=color, sw=sw))
            yy += on + off
    return o


# ───────────────────────── 6장: 같은 증상을 가르는 기준과 비어 있는 관측 ─────────────────────────

def start_point() -> str:
    o = [rect(10, 10, 716, 500, 16, fill=LIGHT, stroke='none', sw=0), rect(770, 10, 420, 500, 16, fill=PALE, stroke=SKY, sw=3)]
    # 왼쪽: 증상 하나 → 팬 진동 기준 두 갈래 → 원인 후보 둘
    o += dial(100, 275, 34, high=False)
    o += [path('M 142,275 H 190 C 225,275 215,165 250,165', stroke=NAVY, sw=4), path('M 190,275 C 225,275 215,385 250,385', stroke=NAVY, sw=4)]
    o += dial(300, 165, 34, high=False) + dial(300, 385, 34, high=True)
    o += [arrow([(345, 165), (555, 165)], NAVY, sw=4, size=13), arrow([(345, 385), (555, 385)], NAVY, sw=4, size=13)]
    o += radiator(575, 125, 90, 76, ON, fins=8) + dust(620, 163, ON, s=0.7)
    o += fan(620, 385, 38, ON, hot=True)
    for r_, dx in ((46, 0), (56, 0)):
        o += [path(f'M {620 + r_ * 0.7:.0f},{385 - r_ * 0.7:.0f} A {r_} {r_} 0 0 1 {620 + r_ * 0.7:.0f},{385 + r_ * 0.7:.0f}', stroke=NAVY, sw=3)]
    # 가운데: 그래서 남기는 질문
    o.append(arrow([(730, 260), (768, 260)], BLUE, sw=5, size=14))
    # 오른쪽: 아직 읽지 않은 두 관측
    o += dial(880, 195, 36, high=None) + dial(1080, 195, 36, high=None)
    o += doc(980, 395, ON, w=70, h=86, hot=2)
    return svg(o)


# ───────────────────────── 8장: 모델 응답 · 근거 검색 · 현재 상태 세 줄 ─────────────────────────

def three_lanes() -> str:
    ys = (85, 260, 435)
    o = [rect(10, y - 75, 1180, 150, 14, fill=LIGHT if i != 1 else PALE, stroke='none', sw=0) for i, y in enumerate(ys)]
    # 줄 1: 요청과 문단 → 모델 → 문장
    y = ys[0] - 22
    o += doc(345, y, w=52, h=66) + bubble(420, y)
    o += [arrow([(478, y), (585, y)], NAVY, sw=4, size=12)] + model(640, y)
    o += [arrow([(695, y), (825, y)], NAVY, sw=4, size=12)] + doc(875, y, w=52, h=66)
    # 줄 2: 질문 → 검색 → 구절 → 모델 → 답과 인용
    y = ys[1] - 22
    o += bubble(320, y)
    o += [arrow([(375, y), (430, y)], BLUE, sw=4, size=12)] + doc(475, y, w=52, h=66) + lens(505, y + 16, r=14)
    o += [arrow([(535, y), (600, y)], BLUE, sw=4, size=12)] + doc(645, y, w=52, h=66, hot=1)
    o += [arrow([(678, y), (735, y)], BLUE, sw=4, size=12)] + model(790, y)
    o += [arrow([(845, y), (925, y)], BLUE, sw=4, size=12)] + doc(975, y, w=52, h=66, hot=1)
    # 줄 3: 원문의 기준과 그 시각의 관측은 따로 읽는다
    y = ys[2] - 30
    o += doc(420, y, w=52, h=66, hot=1)
    o += [arrow([(460, y), (800, y)], NAVY, sw=4, size=12)] + dial(850, y, 34, high=None) + clock(925, y, r=22)
    return svg(o)


# ───────────────────────── 65장: 호출 결과 네 갈래와 말할 수 있는 것 ─────────────────────────

def four_results() -> str:
    ys = (86, 200, 314, 428)
    o = [rect(230, y - 50, 960, 100, 12, fill=PALE if i == 0 else LIGHT, stroke='none', sw=0) for i, y in enumerate(ys)]
    # 호출 → 네 갈래
    o += agent_icon(82, 240, ON)
    o += [line(135, 240, 186, 240, stroke=NAVY, sw=4), line(186, ys[0], 186, ys[3], stroke=NAVY, sw=4)]
    for i, y in enumerate(ys):
        o.append(arrow([(186, y), (252, y)], BLUE if i == 0 else NAVY, sw=4, size=12))
    o += empty_list(292, ys[0]) + padlock(292, ys[1] - 2) + clock(292, ys[2], r=30) + cut_doc(292, ys[3] + 4)
    # 결과 → 말할 수 있는 것
    for i, y in enumerate(ys):
        o.append(arrow([(730, y), (802, y)], BLUE if i == 0 else NAVY, sw=4, size=12))
    o += check(840, ys[0]) + unknown(840, ys[1]) + unknown(840, ys[2])
    o += [path(f'M 840,{ys[3] - 24} A 24 24 0 1 1 816,{ys[3]}', stroke=NAVY, sw=4), poly([(816, ys[3] + 9), (808, ys[3] - 6), (824, ys[3] - 6)], fill=NAVY)]
    # 재조회: 결과 일부에서 호출로 돌아온다
    o += [path(f'M 840,{ys[3] + 28} V 500 H 82 V 306', stroke=BLUE, sw=4), poly([(82, 292), (73, 308), (91, 308)], fill=BLUE)]
    return svg(o)


# ───────────────────────── 69장: 예비품 안건의 상태 사슬 ─────────────────────────

def spare_chain() -> str:
    xs = (120, 360, 600, 840, 1080)
    y = 130
    o = [arrow([(150, y), (328, y)], BLUE, sw=5, size=14), arrow([(392, y), (568, y)], BLUE, sw=5, size=14)]
    o += seg_line(632, 806, y) + seg_line(874, 1046, y)
    o += check(xs[0], y, 30) + check(xs[1], y, 30) + clock(xs[2], y, 30, fill=PALE) + unknown(xs[3], y, 30) + unknown(xs[4], y, 30)
    # 아래: 그 상태의 근거 자료
    o += [rect(40, 262, 160, 212, 14, fill=LIGHT, stroke='none', sw=0), rect(280, 262, 400, 212, 14, fill=PALE, stroke=SKY, sw=3)]
    o += doc(120, 316, ON, w=56, h=70) + doc(480, 316, ON, w=56, h=70, hot=2)
    o += seg_box(760, 262, 400, 212) + doc(960, 316, OFF, w=56, h=70)
    for x in xs[:1]:
        o.append(line(x, 164, x, 260, stroke=NAVY, sw=3))
    o += [line(xs[1], 164, xs[1], 260, stroke=NAVY, sw=3), line(xs[2], 164, xs[2], 260, stroke=NAVY, sw=3)]
    for x in xs[3:]:
        yy = 164
        while yy < 258:
            o.append(line(x, yy, x, min(yy + 12, 258), stroke=GREY, sw=3))
            yy += 22
    return svg(o)


def main():
    out = {'점검요청_출발점.svg': start_point(), '모델과_근거검색.svg': three_lanes(), '호출결과_네갈래.svg': four_results(), '예비품_상태사슬.svg': spare_chain()}
    for name, text in out.items():
        assert '<text' not in text
        (HERE / name).write_text(text, encoding='utf-8')
        print('wrote', name)


if __name__ == '__main__':
    main()
