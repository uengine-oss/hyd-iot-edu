"""녹화 전 계산: 정리 배치(build_ontology의 USER)를 시작 구간 끝 그림 범위에 비율로 맞추고, 원을 옮기는 순서를 정한다.
순서의 조건 — (1) 아직 안 옮긴 원 자리에 놓지 않는다(겹치면 원을 못 찾음) (2) 그림 범위가 줄지 않는다(화면 맞춤 폭주).
build_ontology의 ORDER가 이 조건을 지키는지 검사하고, 지키지 않으면 지키는 순서를 제안한다. 녹화 중에는 순서를 다시 계산하지 않는다.
사용: python plan_order.py <시작 구간 이름(끝 상태를 쓸 녹화 조각)> [원 반지름=47]
"""
import json, math, sys
from pathlib import Path
from common import WORK

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_ontology import USER, ORDER  # noqa: E402

take, R = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 47
g = json.loads((WORK / take / 'end-state.json').read_text(encoding='utf-8'))['graph']['graph']
cur = {n['caption']: (n['position']['x'], n['position']['y']) for n in g['nodes']}
missing = sorted(set(USER) ^ set(cur))
if missing:
    raise SystemExit(f'{take}: 배치 원과 그림 원이 다르다 {missing}')
X = [p[0] for p in cur.values()]; Y = [p[1] for p in cur.values()]; x0, x1, y0, y1 = min(X), max(X), min(Y), max(Y)
ux = [p[0] for p in USER.values()]; uy = [p[1] for p in USER.values()]
T = {c: (x0 + (p[0] - min(ux)) / (max(ux) - min(ux)) * (x1 - x0), y0 + (p[1] - min(uy)) / (max(uy) - min(uy)) * (y1 - y0)) for c, p in USER.items()}


def problem(c, d):
    t = T[c]
    if any(o != c and math.hypot(q[0] - t[0], q[1] - t[1]) < 2 * R + 30 for o, q in d.items()):
        return 'overlap'
    e = dict(d); e[c] = t
    xs = [p[0] for p in e.values()]; ys = [p[1] for p in e.values()]
    if min(xs) > x0 + 1 or max(xs) < x1 - 1 or min(ys) > y0 + 1 or max(ys) < y1 - 1:
        return 'shrink'
    return ''


def check(order):
    d = dict(cur)
    for c in order:
        if math.hypot(d[c][0] - T[c][0], d[c][1] - T[c][1]) < 20:
            continue
        p = problem(c, d)
        if p:
            return c, p
        d[c] = T[c]
    return None


bad = check(ORDER)
if not bad:
    print(json.dumps({'ORDER': 'ok', 'min_center_dist': round(min(math.hypot(T[a][0] - T[b][0], T[a][1] - T[b][1]) for a in T for b in T if a < b))}, ensure_ascii=False))
    sys.exit(0)
pend = [c for c in T if math.hypot(cur[c][0] - T[c][0], cur[c][1] - T[c][1]) >= 20]; order = []; d = dict(cur)
while pend:
    pick = next((c for c in pend if not problem(c, d)), None)
    if pick is None:
        raise SystemExit(f'ORDER 불가: {bad}. 남은 원 {{c: problem(c, d) for c in pend}} = ' + json.dumps({c: problem(c, d) for c in pend}, ensure_ascii=False))
    pend.remove(pick); order.append(pick); d[pick] = T[pick]
print(json.dumps({'ORDER': f'{bad[0]}에서 {bad[1]}', 'suggest': order}, ensure_ascii=False))
sys.exit(1)
