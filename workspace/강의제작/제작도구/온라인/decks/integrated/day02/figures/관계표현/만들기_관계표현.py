"""통합반 2회차 관계 표현 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: python 만들기_관계표현.py   → 이 폴더에 SVG를 쓴다
원과 화살표는 카디널리티_선언대조.svg와 같은 꼴, 상속 그림의 빈 세모와 칸은 ../만들기_삽화.py의 inherit()와 같은 꼴이다.
"""
from __future__ import annotations

import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLUE, RED, PALE, LINE, PANEL, NAVY, SKY, LIGHT = "#1A6FC4", "#C94D55", "#E7F3FD", "#D3D9E1", "#F3F6FA", "#13294B", "#5CB8F2", "#F3F6F9"


def drawing(nodes, edges, rects=(), extra=(), height=500):
    """nodes = (x, y, r), edges = (시작, 끝, 어긋남 여부). extra는 원과 화살표 위에 그대로 넣는 조각이다."""
    a = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">']
    for x, y, w, h, fill in rects:
        a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{LINE}" stroke-width="2"/>')
    for i, j, bad in edges:
        x, y, r = nodes[i]
        xx, yy, rr = nodes[j]
        dx, dy = xx - x, yy - y
        d = math.hypot(dx, dy)
        ux, uy = dx / d, dy / d
        x, y, xx, yy = x + ux * r, y + uy * r, xx - ux * rr, yy - uy * rr
        col = RED if bad else BLUE
        a.append(f'<path d="M{x},{y} L{xx},{yy}" fill="none" stroke="{col}" stroke-width="2.5"/>')
        a.append(f'<path d="M{xx},{yy} L{xx - 15 * ux + 7 * uy},{yy - 15 * uy - 7 * ux} L{xx - 15 * ux - 7 * uy},{yy - 15 * uy + 7 * ux} Z" fill="{col}"/>')
        if bad:
            mx, my = (x + xx) / 2, (y + yy) / 2
            a.append(f'<path d="M{mx - 7},{my - 7} L{mx + 7},{my + 7} M{mx + 7},{my - 7} L{mx - 7},{my + 7}" fill="none" stroke="{col}" stroke-width="3"/>')
    for x, y, r in nodes:
        a.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{PALE}" stroke="{BLUE}" stroke-width="2"/>')
    a.extend(extra)
    a.append('</svg>')
    return ''.join(a)


def arrow(x, y, xx, yy, col=BLUE, bad=False):
    dx, dy = xx - x, yy - y
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    o = [f'<path d="M{x},{y} L{xx},{yy}" fill="none" stroke="{col}" stroke-width="2.5"/>',
         f'<path d="M{xx},{yy} L{xx - 15 * ux + 7 * uy},{yy - 15 * uy - 7 * ux} L{xx - 15 * ux - 7 * uy},{yy - 15 * uy + 7 * ux} Z" fill="{col}"/>']
    if bad:
        mx, my = (x + xx) / 2, (y + yy) / 2
        o.append(f'<path d="M{mx - 7},{my - 7} L{mx + 7},{my + 7} M{mx + 7},{my - 7} L{mx - 7},{my + 7}" fill="none" stroke="{col}" stroke-width="3"/>')
    return o


def box(x, y, w, h, fill=PALE, stroke=BLUE):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def check(cx, cy, r=17):
    return [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{SKY}" stroke="{NAVY}" stroke-width="2.5"/>',
            f'<path d="M{cx - r * .45},{cy} L{cx - r * .1},{cy + r * .35} L{cx + r * .5},{cy - r * .35}" fill="none" stroke="{NAVY}" stroke-width="3"/>']


def cross(cx, cy, r=17, col=RED):
    k = r * .38
    return [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#FFFFFF" stroke="{col}" stroke-width="2.5"/>',
            f'<path d="M{cx - k},{cy - k} L{cx + k},{cy + k} M{cx + k},{cy - k} L{cx - k},{cy + k}" fill="none" stroke="{col}" stroke-width="3"/>']


def write(name, text):
    (HERE / name).write_text(text, encoding='utf8')


# 조작 관계에 더한 연결과 양쪽에서 센 상대 수(SLIDE 16) — 오른쪽 칸의 두 줄 앞에 위반 표시
nodes16 = [(150, 180, 82), (150, 390, 82), (520, 180, 82), (520, 390, 82)]
edges16 = [(0, 2, False), (1, 3, False), (0, 3, True)]
extra16 = [f'<path d="M700,40 L700,470" fill="none" stroke="{LINE}" stroke-width="2.5"/>'] + cross(730, 175) + cross(730, 365)
write('카디널리티_선언대조.svg', drawing(nodes16, edges16, [(20, 10, 1160, 480, PANEL)], extra=extra16))

# 공통 구성 노드와 설비별 노드(SLIDE 17)
assets_l = [(130, 125, 50), (130, 245, 50), (130, 365, 50)]
assets_r = [(735, 125, 50), (735, 245, 50), (735, 365, 50)]
comps_r = [(1040, 125, 56), (1040, 245, 56), (1040, 365, 56)]
nodes = assets_l + [(430, 245, 78)] + assets_r + comps_r
edges = [(0, 3, False), (1, 3, False), (2, 3, False), (4, 7, False), (5, 8, False), (6, 9, False)]
write('공통과_설비별_구성.svg', drawing(nodes, edges, [(20, 10, 550, 480, PALE), (630, 10, 550, 480, PANEL)]))

# 같은 표시와 서로 다른 대상(SLIDE 27)
write('같은표시_다른대상.svg', drawing([(280, 210, 95), (920, 210, 100)], [(0, 1, False)]))

# 표현이 다른 두 기록을 같은 대상으로 볼지 가리는 근거(SLIDE 26)
extra = [box(40, 45, 250, 95), box(40, 205, 250, 95)]
extra += arrow(290, 92, 388, 155) + arrow(290, 252, 388, 190)
extra.append(f'<path d="M520,70 L650,172 L520,274 L390,172 Z" fill="#FFFFFF" stroke="{NAVY}" stroke-width="3"/>')
extra += arrow(650, 172, 800, 95) + arrow(650, 172, 800, 255)
extra += [box(802, 30, 368, 125), box(802, 205, 368, 100, fill=PANEL, stroke=LINE)]
extra.append(f'<path d="M40,348 L1160,348" fill="none" stroke="{LINE}" stroke-width="3"/>')
extra += cross(70, 425, 22) + cross(650, 425, 22)
write('같은대상_판단.svg', drawing([], [], extra=extra))

# 검사 결과와 원래 자료로 정할 일(SLIDE 36)
extra = []
for cy, top, low in ((135, 85, 185), (360, 310, 410)):
    extra += [box(30, cy - 50, 280, 100, fill=PANEL, stroke=LINE), box(390, cy - 42, 250, 84)]
    extra += arrow(310, cy, 390, cy) + arrow(640, cy, 735, top) + arrow(640, cy, 735, low, RED if cy == 135 else BLUE, cy == 135)
    extra += [box(737, top - 38, 435, 76, fill='#FFFFFF'), box(737, low - 38, 435, 76, fill='#FFFFFF', stroke=RED if cy == 135 else BLUE)]
extra.append(f'<path d="M30,248 L1170,248" fill="none" stroke="{LINE}" stroke-width="2.5"/>')
write('오류_원자료_판단.svg', drawing([], [], extra=extra))

# 공유 모델의 경로와 대상 수(SLIDE 54)
nodes = [(130, 90, 55), (130, 250, 55), (130, 410, 55), (500, 250, 90), (920, 250, 90)]
write('공유모델_경로와노드수.svg', drawing(nodes, [(0, 3, False), (1, 3, False), (2, 3, False), (3, 4, False)]))

# 새 질문에 공급사와 승인 여부를 더한 모델(SLIDE 42)
nodes = [(165, 280, 85), (520, 255, 80), (830, 85, 72), (830, 255, 72), (830, 425, 72)]
extra = [f'<path d="M335,20 L335,490" fill="none" stroke="{LINE}" stroke-width="3"/>']
extra += check(935, 85) + check(935, 255) + cross(935, 425)
write('승인공급사_모델.svg', drawing(nodes, [(1, 2, False), (1, 3, False), (1, 4, False)], extra=extra))

# 상속과 관계의 구별(SLIDE 21) — 왼쪽은 상위 클래스 칸과 하위 클래스 칸, 오른쪽은 구성 요소에서 센서로 가는 관계 하나
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 520" width="1200" height="520">']
st = f'stroke="{NAVY}" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"'
o.append(f'<line x1="360" y1="186" x2="360" y2="300" {st}/>')
o.append(f'<polygon points="360.0,156.0 342.0,186.0 378.0,186.0" fill="#FFFFFF" stroke="{NAVY}" stroke-width="4" stroke-linejoin="round"/>')
o.append(f'<rect x="150" y="14" width="420" height="140" rx="14" ry="14" fill="{LIGHT}" stroke="{NAVY}" stroke-width="4"/>')
o.append(f'<rect x="150" y="302" width="420" height="140" rx="14" ry="14" fill="{PALE}" stroke="{SKY}" stroke-width="4"/>')
o.append(f'<path d="M740,30 L740,490" fill="none" stroke="{LINE}" stroke-width="3"/>')
for x in (860, 1080):
    o.append(f'<circle cx="{x}" cy="300" r="62" fill="{PALE}" stroke="{BLUE}" stroke-width="2"/>')
o += arrow(922, 300, 1018, 300)
o.append('</svg>')
write('상속과_관계.svg', ''.join(o))
