"""실습 영상 예상 시간 계산 — 촬영·음성 생성 전에 대본 큐로 길이를 낸다. 모든 도구(ARROWS·Notion·포털 등) 공통.

모형(실측으로 맞춤, 계수는 시간계수.json):
  큐 시간 = 말 길이 + 말 끝 뒤에 넘치는 조작 시간(최소 0.25초 간격)
  말 길이   = a·한글 음절 + b·숫자 + c·영문 글자 + d·문장부호(.?!,)            ← 실제 음성 파일 길이로 맞춤
  넘치는 조작 = e·입력 글자 + f·클릭 + g·끌기 + h·키 + i                    ← 실제 녹화의 '말 끝 → 다음 말 시작'으로 맞춤
말하는 동안 하는 조작은 겹치므로 따로 더하지 않는다(기준_실습대본 「자연스러운 진행과 유연한 조정」의 합집합 계산).

큐 형식(JSON): {"cues":[{"id","segment","text","ops":[[op, ...인자], ...]}]}
  op 분류: type(인자 글자 수) · key · 끌기(grow/connect/move/drag, layout은 원 수만큼) · 가리키기(point/at, 시간 없음) · 그 밖은 클릭.

사용:
  python 시간계산.py estimate <cues.json> [--target 분]     # 촬영 전 예상
  python 시간계산.py calibrate <근거폴더> [<근거폴더> ...]     # 녹화 뒤 계수 다시 맞추기(audio/*.json, <구간>/timing.json, cues.json)
  python 시간계산.py check <근거폴더> <구간[:자른ms]> ...      # 찍은 구간과 예상 비교
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COEF = HERE / '시간계수.json'
DRAG = {'grow', 'connect', 'move', 'drag'}
POINT = {'point', 'at', 'manual', 'verify'}


def speech_features(text):
    return [len(re.findall('[가-힣]', text)), len(re.findall('[0-9]', text)), len(re.findall('[A-Za-z]', text)), len(re.findall('[.?!,]', text))]


def op_features(ops):
    chars = clicks = drags = keys = 0
    for o in ops or []:
        k = o[0]
        if k == 'type':
            chars += len(o[1])
        elif k == 'key':
            keys += 1
        elif k == 'layout':
            drags += len(o[1])
        elif k in DRAG:
            drags += 1
        elif k in POINT:
            pass
        else:
            clicks += 1
    return [chars, clicks, drags, keys]


def load_coef():
    if not COEF.exists():
        raise SystemExit(f'{COEF}: 계수 파일이 없다. 먼저 calibrate를 실행한다.')
    return json.loads(COEF.read_text(encoding='utf-8'))


def cue_seconds(c, k):
    sp = sum(a * b for a, b in zip(k['speech'], speech_features(c['text'])))
    ops = [o for o in c.get('ops') or [] if o[0] != 'at']
    ov = sum(a * b for a, b in zip(k['overflow'][:4], op_features(ops))) + k['overflow'][4] if ops else 0
    return sp, max(0.25, ov)


def estimate(path, target=None):
    k = load_coef()
    cues = json.loads(Path(path).read_text(encoding='utf-8'))['cues']
    segs = {}
    for c in cues:
        sp, ov = cue_seconds(c, k)
        s = segs.setdefault(c['segment'], [0, 0, 0])
        s[0] += sp; s[1] += ov; s[2] += 1
    total = sum(a + b for a, b, _ in segs.values())
    print('| 구간 | 큐 | 말(분) | 조작 넘침(분) | 예상(분) |\n|---|---|---|---|---|')
    for n, (a, b, m) in sorted(segs.items()):
        print(f'| {n} | {m} | {a / 60:.1f} | {b / 60:.1f} | {(a + b) / 60:.1f} |')
    err = k.get('check_error_pct')
    print(f'\n예상 합계 {total / 60:.1f}분(큐 {len(cues)}개)' + (f', 검증 오차 {err:+.1f}%' if err is not None else ''))
    if target:
        diff = total / 60 - target
        print(f'배정 {target}분 대비 {diff:+.1f}분' + (' — 촬영 전에 보강·축소 범위를 정한다' if abs(diff) > target * 0.15 else ''))
    return total


def calibrate(dirs):
    import numpy as np
    sx, sy, ox, oy = [], [], [], []
    for d in map(Path, dirs):
        for f in (d / 'audio').glob('*.json'):
            a = json.loads(f.read_text(encoding='utf-8'))
            sx.append(speech_features(a['text'])); sy.append(a['duration_ms'] / 1000)
        cues = {c['id']: c for c in json.loads((d / 'cues.json').read_text(encoding='utf-8'))['cues']}
        for t in d.glob('*/timing.json'):
            A = json.loads(t.read_text(encoding='utf-8'))['actions']
            for i, a in enumerate(A[:-1]):
                c = cues.get(a['id'])
                ops = [o for o in (c or {}).get('ops') or [] if o[0] != 'at']
                if not c or c['text'] != a['text'] or not ops or any(o[0] in ('layout', 'manual', 'verify', 'choose') for o in ops):
                    continue
                ox.append(op_features(ops) + [1]); oy.append((A[i + 1]['time'] - a['time'] - a['duration']) / 1000)
    sp, *_ = np.linalg.lstsq(np.array(sx, float), np.array(sy), rcond=None)
    ov, *_ = np.linalg.lstsq(np.array(ox, float), np.array(oy), rcond=None)
    k = {'speech': [round(float(x), 4) for x in sp], 'overflow': [round(float(x), 4) for x in ov],
         'speech_samples': len(sy), 'overflow_samples': len(oy), 'sources': [str(Path(d).as_posix()) for d in dirs],
         'note': 'speech=[음절,숫자,영문,부호] 초/개, overflow=[입력글자,클릭,끌기,키,상수] 초'}
    COEF.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(k, ensure_ascii=False))


def check(d, specs):
    k = load_coef()
    d = Path(d)
    cues = {c['id']: c for c in json.loads((d / 'cues.json').read_text(encoding='utf-8'))['cues']}
    pred = act = 0
    for spec in specs:
        seg, _, cut = spec.partition(':')
        t = json.loads((d / seg / 'timing.json').read_text(encoding='utf-8'))
        end = float(cut) if cut else t['duration']
        used = [a for a in t['actions'] if a['time'] < end]
        p = sum(sum(cue_seconds(cues[a['id']] if a['id'] in cues and cues[a['id']]['text'] == a['text'] else {'text': a['text'], 'ops': []}, k)) for a in used)
        print(f'{seg}: 예상 {p:.1f}s / 실제 {end / 1000:.1f}s ({(p - end / 1000) / (end / 1000) * 100:+.1f}%)')
        pred += p; act += end / 1000
    e = (pred - act) / act * 100
    print(f'합계: 예상 {pred / 60:.2f}분 / 실제 {act / 60:.2f}분 ({e:+.1f}%)')
    k['check_error_pct'] = round(e, 1)
    COEF.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    cmd, *rest = sys.argv[1:]
    if cmd == 'estimate':
        tgt = float(rest[rest.index('--target') + 1]) if '--target' in rest else None
        estimate(rest[0], tgt)
    elif cmd == 'calibrate':
        calibrate(rest)
    elif cmd == 'check':
        check(rest[0], rest[1:])
    else:
        raise SystemExit(__doc__)
