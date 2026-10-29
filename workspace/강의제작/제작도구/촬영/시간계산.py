"""말 길이 계산 — 실제 강사 복제 음성으로 맞춘 계수 하나(시간계수.json)로 실습 큐와 이론 대본의 시간을 낸다.

모형(계수는 시간계수.json, 실제 음성으로 맞춤):
  말 길이     = a·한글 음절 + b·숫자 + c·영문 글자 + d·문장부호(.?!,)        ← 실제 음성 파일(문장별 길이)로 맞춤
  실습 큐 시간 = 말 길이 + 말 끝 뒤에 넘치는 조작(최소 0.25초 간격)
  넘치는 조작 = e·입력 글자 + f·클릭 + g·끌기 + h·키 + i                    ← 실제 녹화의 '말 끝 → 다음 말 시작'으로 맞춤
  이론 장 시간 = s·(장 본문의 말 길이) + p                                  ← 강사 복제 음성 이론 영상의 장별 음성 시간으로 맞춤(쉼 · 장 넘김 포함)
말하는 동안 하는 조작은 겹치므로 따로 더하지 않는다(합집합 계산). 이론 대본의 장별 시간은 대본시간.py가 이 계수로 낸다.

큐 형식(JSON): {"cues":[{"id","segment","text","ops":[[op, ...인자], ...]}]}
  op 분류: type(인자 글자 수) · key · 끌기(grow/connect/move/drag, layout은 원 수만큼) · 가리키기(point/at, 시간 없음) · 그 밖은 클릭.

사용:
  python 시간계산.py estimate <cues.json> [--target 분]       # 촬영 전 실습 큐 예상
  python 시간계산.py calibrate <근거폴더> [<근거폴더> ...]       # 말 길이 · 조작 계수 다시 맞추기
        근거폴더의 audio/*.json · *.json 중 {"text","duration_ms"}가 있는 문장 음성, 있으면 cues.json + <구간>/timing.json
  python 시간계산.py calibrate-lecture                          # 이론 장 계수 다시 맞추기(로컬 영상 시간표 × 현재 산출물 대본)
  python 시간계산.py check <근거폴더> <구간[:자른ms]> ...        # 찍은 구간과 예상 비교
"""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COEF = HERE / '시간계수.json'
DRAG = {'grow', 'connect', 'move', 'drag'}
POINT = {'point', 'at', 'manual', 'verify'}


def spoken(text):
    """낭독하지 않는 표시를 뺀다: 굵게 표시, 인용 줄(>), 제목 줄, `English(한글 발음)`은 한글 발음만."""
    text = re.sub(r"\*\*|^>.*$|^#.*$", "", text, flags=re.M)
    return re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", text)


def speech_features(text):
    text = spoken(text)
    return [len(re.findall('[가-힣]', text)), len(re.findall('[0-9]', text)), len(re.findall('[A-Za-z]', text)), len(re.findall('[.?!,]', text))]


def speech_seconds(text, k=None):
    k = k or load_coef()
    return sum(a * b for a, b in zip(k['speech'], speech_features(text)))


def slide_seconds(text, k=None):
    """이론 대본 한 장의 예상 시간(초)."""
    k = k or load_coef()
    if 'lecture' not in k:
        raise SystemExit(f'{COEF}: 이론 장 계수(lecture)가 없다. 먼저 calibrate-lecture를 실행한다.')
    return k['lecture']['scale'] * speech_seconds(text, k) + k['lecture']['per_slide']


def script_slides(body):
    """이론 분할 대본 본문 → {장 번호: 본문}. 범위 장(SLIDE 60~61)은 본문을 장 수로 나눠 각 장에 둔다."""
    body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", body, flags=re.M)[0]
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\](.*)$", body, flags=re.M)
    out = {}
    for i in range(1, len(parts), 3):
        a = parts[i].split('~')
        nums = range(int(a[0]), int(a[-1]) + 1)
        for n in nums:
            out[n] = (parts[i + 2], len(nums), parts[i + 1].strip())
    return out


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


def lstsq(X, y):
    """최소제곱(정규방정식, 가우스 소거). 계수가 몇 개뿐이라 numpy 없이 푼다."""
    n = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(n)] + [sum(r[i] * v for r, v in zip(X, y))] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            raise SystemExit(f'최소제곱: {c}번째 특징이 근거에 없어 계수를 정할 수 없다')
        A[c], A[piv] = A[piv], A[c]
        for r in range(n):
            if r != c:
                f = A[r][c] / A[c][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]
    return [A[i][n] / A[i][i] for i in range(n)]


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
    sx, sy, ox, oy = [], [], [], []
    for d in map(Path, dirs):
        if not d.is_dir():
            raise SystemExit(f'{d}: 근거 폴더가 없다')
        for f in sorted(set(d.glob('audio/*.json')) | set(d.glob('*.json'))):
            a = json.loads(f.read_text(encoding='utf-8'))
            if isinstance(a, dict) and isinstance(a.get('text'), str) and isinstance(a.get('duration_ms'), (int, float)) and 'cues' not in a:
                sx.append(speech_features(a['text'])); sy.append(a['duration_ms'] / 1000)
        if not (d / 'cues.json').exists():
            continue
        cues = {c['id']: c for c in json.loads((d / 'cues.json').read_text(encoding='utf-8'))['cues']}
        for t in d.glob('*/timing.json'):
            A = json.loads(t.read_text(encoding='utf-8'))['actions']
            for i, a in enumerate(A[:-1]):
                c = cues.get(a['id'])
                ops = [o for o in (c or {}).get('ops') or [] if o[0] != 'at']
                if not c or c['text'] != a['text'] or not ops or any(o[0] in ('layout', 'manual', 'verify', 'choose') for o in ops):
                    continue
                ox.append(op_features(ops) + [1]); oy.append((A[i + 1]['time'] - a['time'] - a['duration']) / 1000)
    if not sx:
        raise SystemExit('문장 음성(text · duration_ms)이 하나도 없다: ' + ', '.join(dirs))
    sp = lstsq(sx, sy)
    resid_sum = sum(v - sum(a * b for a, b in zip(sp, r)) for r, v in zip(sx, sy))
    old = json.loads(COEF.read_text(encoding='utf-8')) if COEF.exists() else {}
    k = dict(old)
    k.update({'speech': [round(float(x), 4) for x in sp], 'speech_samples': len(sy),
              'speech_error_pct': round(resid_sum / sum(sy) * 100, 2),
              'speech_sources': [str(Path(d).as_posix()) for d in dirs]})
    if oy:
        ov = lstsq(ox, oy)
        k.update({'overflow': [round(float(x), 4) for x in ov], 'overflow_samples': len(oy),
                  'overflow_sources': [str(Path(d).as_posix()) for d in dirs]})
    elif 'overflow' not in k:
        raise SystemExit('조작 계수를 맞출 녹화(cues.json + timing.json)가 없고 이전 계수도 없다')
    else:
        print(f"조작 계수: 이번 근거에 녹화가 없어 이전 값을 유지한다(근거 {k.get('overflow_sources', k.get('sources'))})", file=sys.stderr)
    k.pop('sources', None)
    k['note'] = 'speech=[음절,숫자,영문,부호] 초/개, overflow=[입력글자,클릭,끌기,키,상수] 초, lecture: 장 시간 = scale·말 길이 + per_slide 초'
    COEF.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(k, ensure_ascii=False))


TIMETABLE_DIR = 'workspace/강의제작/산출물/영상/_작업/영상_자막_기록'


def calibrate_lecture():
    """강사 복제 음성 이론 영상의 장별 음성 시간(로컬 영상 시간표 — git이 무시하는 자리)과 현재 산출물 대본의 말 길이로 장 계수를 맞춘다."""
    k = load_coef()
    root = HERE.parents[3]
    tdir = root / TIMETABLE_DIR
    names = sorted(f.name for f in tdir.glob('*_시간표.md')) if tdir.is_dir() else []
    if not names:
        raise SystemExit(f'{tdir}에 시간표가 없다 — 영상을 만든 로컬 영상 폴더가 필요하다')
    px, py, used, skipped = [], [], [], []
    for n in names:
        m = re.match(r'(통합반|실전반)_(\d+)회차_(.+)_시간표\.md$', n)
        script = root / 'workspace/강의제작/산출물' / m.group(1) / '이론' / f'{m.group(2)}회차' / '대본' / f'{m.group(3)}.md' if m else None
        if not script or not script.exists():
            skipped.append(f'{n}: 대응 대본 없음')
            continue
        slides = script_slides(script.read_text(encoding='utf-8'))
        rows = re.findall(r'^\| (\d+) \| [\d:]+ \| ([\d.]+) \|$', (tdir / n).read_text(encoding='utf-8'), flags=re.M)
        hit = 0
        for no, sec in rows:
            s = slides.get(int(no))
            if s is None:
                continue
            px.append(speech_seconds(s[0], k) / s[1]); py.append(float(sec)); hit += 1
        (used if hit else skipped).append(f'{n}: {hit}장' if hit else f'{n}: 맞는 장 없음')
    if len(py) < 20:
        raise SystemExit(f'맞출 장이 {len(py)}개뿐이다: {skipped}')
    s, p = lstsq([[x, 1.0] for x in px], py)
    resid = [v - (s * x + p) for x, v in zip(px, py)]
    mean = sum(resid) / len(resid)
    k['lecture'] = {'scale': round(float(s), 4), 'per_slide': round(float(p), 2), 'slides': len(py),
                    'resid_sd_s': round((sum((r - mean) ** 2 for r in resid) / len(resid)) ** 0.5, 2), 'total_error_pct': round(sum(resid) / sum(py) * 100, 2),
                    'sources': used, 'skipped': skipped, 'timetables': TIMETABLE_DIR}
    COEF.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(k['lecture'], ensure_ascii=False, indent=1))


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
    elif cmd == 'calibrate-lecture':
        calibrate_lecture()
    elif cmd == 'check':
        check(rest[0], rest[1:])
    else:
        raise SystemExit(__doc__)
