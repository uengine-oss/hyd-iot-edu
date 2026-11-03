"""실습 영상 합성기(포털) — --도구로 다른 도구(VS Code · Notion · ARROWS) work도 합성한다. 그 도구들의 encode.py 사본과 neo4j lesson_pipeline.py는 아직 옛 합성을 쓴다.
구간별 원본 시간을 그대로 두고(배속 · 중간 컷 없음) 구간 경계만 잇는다.
사용(명령은 이 폴더에서, 리눅스 python3 · Windows PYTHONUTF8=1 python):
  encode.py [--도구 <이름>] <출력이름> <명세> … [--silent] [--음성교체 <json>] [--이음새허용 <번호,…>]
  encode.py [--도구 <이름>] --교체 <합성기록.json> <번호>=<명세> … [--영상 <mp4>] [--출력 <이름>] [--음성교체 <json>] [--이음새허용 <번호,…>]
  encode.py [--도구 <이름>] --기록 <verification.json>     옛 합성기가 쓴 verification.json을 합성기록으로 옮긴다(인코딩 없음)
  encode.py --자가시험                                     시험 자료(ffmpeg testsrc 프레임 · 사인음 큐)로 실제 인코딩해 판정, 하나라도 어긋나면 종료 코드 1
  --도구: 그 도구 촬영도구/config.json의 work(녹화 원본) · audio(음성 캐시)를 그 폴더 기준으로 푼다(기본 포털). 출력은 <work>/<출력이름>/.
  명세 = [<도구>:]<take>[@<시작ms>][:<끝ms>] — 도구 접두가 있으면 그 도구 work의 take(포털 합본에 VS Code 구간 같은 섞음). @ · :는 손으로 고를 때만 쓴다:
    오류로 끝난 take는 끝을 꼭 준다(이어 찍었으면 이음새검수.py가 알려 준다). 말 · 조작 도중에서 자르면 멈춘다.
조각: take 하나를 구간(큐 원고의 segment)마다 조각으로 나눈다 — 큐 segment가 바뀌는 첫 큐의 시작(앞 말이 끝나고 쉬는 자리)이 경계다. segment는 timing.json
  큐에 있으면 그것, 없으면 take.sh가 남긴 <work>/run-<take>-record.mjs의 큐 파일에서 찾고, 둘 다 없으면 take 하나가 조각 하나다.
  조각마다 영상만 든 mp4를 고정 설정(30fps · libx264 veryfast · crf · yuv420p, 첫 프레임 IDR)으로 만들어 <work>/조각_저장/<키>.mp4에 두고(이 PC 전용),
  키(take · 범위 · 원본 프레임 · 화살표 · 설정)가 같으면 다시 만들지 않는다. 조각은 -c copy로 잇고 해설은 마지막에 한 번만 넣는다 — 말만 고치면 영상 인코딩 0.
  조각 프레임 수 = round(사용 ms × 30 / 1000). 큐 음성 · 자막 · 시각표는 앞 조각 실제 프레임 합 / 30 위에 놓는다(구간이 늘어도 소리가 밀리지 않는다).
화살표: 구간마다 pointer-start.json mode로 정한다. overlay(페이지 화살표 투명 녹화)면 기록된 이동(출발 · 도착 · 시작 · 계획 길이)으로 30fps마다
  화살표를 그린다(기록된 위치 · 시각 그대로, 두 화살표 없음). 그 도구 config pointer가 overlay인데 overlay가 아닌 구간이면 멈춘다. 화면 내용은 그 시각까지
  받은 마지막 원본 프레임이다 — 원본에 없는 화면을 만들지 않는다. 출력 크기는 첫 원본 JPEG 크기, config viewport · deviceScaleFactor는 화살표 배율에만 쓴다.
고친 음성: 캐시의 글 · 길이가 녹화 때와 다르면(녹화 뒤 대사만 고쳐 다시 만든 음성) 원래 말이 끝나던 자리에 끝나도록 오른쪽에 맞춘다(조작이 말 직후 그대로).
  원래보다 길어 앞 말과 겹치면 앞 말 끝(또는 조각 시작)부터 놓고, 조각 끝을 넘으면 멈춘다. 자막은 고친 글 · 길이로 쓴다. 합성 안에 두 번 이상 나오는 큐 id가
  바뀌었으면 어느 자리인지 알 수 없어 멈춘다 — --음성교체 <json>([{segment(take), time(take ms), file(json 기준), text(선택)}])으로 자리마다 정한다.
이음새 자동 검사(영상 V요-25 · V-179): 조각 경계마다 프레임 간격(영상 시각이 한 프레임씩 이어짐), 소리 튐(경계 앞뒤 급변 · 경계 뒤 큐의 소리 시작 ±1/30초),
  다른 녹화가 만나는 이음새는 앞뒤 화면(1/4로 줄여 값이 12 넘게 바뀐 화소 0.5 % 이하 — 커서 위치만 다를 수 있다. 줄이지 않으면 같은 원본도
  overlay · page 압축 차이로 1.9 %가 난다)과 앞뒤 0.2초 나란히 그림(<출력>/이음새_NN.jpg).
  하나라도 어긋나면 합성기록을 쓰지 않고 멈춘다 — 그림을 보고 이어짐이 맞으면(앱 전환 등) --이음새허용 <번호>로 다시 낸다(조각은 다시 만들지 않는다).
  영상 · 음성 끝 시각은 조각 프레임 합과 0.1초 안(V-184). 출력 mp4가 이미 있으면 멈춘다(새 이름으로).
합성기록 <도구>/합성기록/<출력이름>.json(커밋한다): 구간 · 큐 시각표 · 이동 공백 · 클릭 오차 · 이음새 판정과 조각 키 · 경계 · 프레임 수, 출력 mp4 sha256 · 영상 패킷 수.
  --교체는 그 mp4(work 아래 출력, 다른 자리면 --영상)가 기록의 sha256과 같을 때만 경계에서 잘라 바꾸지 않은 조각으로 쓴다(조각_저장에 있으면 그것) —
  join.py · cut.py · 다시 인코딩한 영상은 경계에 키프레임이 없어 멈춘다. 바꾼 조각만 새로 만든다. 이은 결과의 영상 패킷 수가 조각 프레임 합과 다르면 멈춘다.
다른 곳에서 부르기: from encode import encode; encode(이름, 명세들, work=…, audio=…, crf=18, desc=…, tool_name=…, record_dir=…) — work · audio를 주면
  config 대신 그 폴더를 쓴다(config가 없는 neo4j가 옮겨 올 자리, 아직 부르는 곳 없음)."""
import bisect, hashlib, json, os, re, shutil, subprocess, sys, tempfile, wave
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import TOOLS, tool as find_tool, ffmpeg  # noqa: E402
import measure  # noqa: E402

FPS, SR, TB = 30, 44100, 15360
KEY_VERSION = 1
SAME_PCT = 0.5          # 같은 화면: 값이 12 넘게 바뀐 화소가 이만큼(%) 이하
ONSET = 0.02            # 소리 시작 문턱(전체 크기 비)
ARROW_PTS = [(1, 1), (1, 25), (7, 20), (12, 31), (17, 29), (12, 18), (22, 18)]   # ui.mjs 화살표(SVG viewBox 25x34 → CSS 20x27)
_FF = None


def ff():
    global _FF
    _FF = _FF or ffmpeg()
    return _FF


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def out_of(cmd):
    return subprocess.check_output([str(c) for c in cmd])


def q(p):
    return "'" + str(p).replace("'", "'\\''") + "'"


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def stamp(ms):
    ms = round(ms); m, s = divmod(ms, 60000); return f'{m:02}:{s // 1000:02}.{s % 1000:03}'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


# ── mp4 읽기(ffprobe가 없는 Windows imageio-ffmpeg에서도 같게: ffmpeg -c copy -f framemd5) ──
def packets(mp4, sel='v:0'):
    """(시간 단위 초, [(dts, pts, duration)]) — 디코드 없이 패킷만."""
    txt = out_of([ff(), '-v', 'error', '-i', mp4, '-map', f'0:{sel}', '-c', 'copy', '-f', 'framemd5', '-']).decode()
    tb, rows = None, []
    for l in txt.splitlines():
        if l.startswith('#tb'):
            a, b = l.split(':', 1)[1].strip().split('/'); tb = int(a) / int(b)
        elif l and not l.startswith('#'):
            p = [x.strip() for x in l.split(',')]
            rows.append((int(p[1]), int(p[2]), int(p[3])))
    return tb, rows


def stream_end(mp4, sel):
    tb, rows = packets(mp4, sel)
    return max(p + d for _, p, d in rows) * tb if rows else 0.0


def sps_pps(mp4):
    """조각을 -c copy로 이을 수 있는지: 첫 프레임의 SPS · PPS(인코더 설정) 묶음의 sha256. 다른 PC · 다른 설정이면 달라진다."""
    raw = out_of([ff(), '-v', 'error', '-i', mp4, '-map', '0:v:0', '-c', 'copy', '-bsf:v', 'h264_mp4toannexb', '-frames:v', '1', '-f', 'h264', '-'])
    units = [u for u in re.split(rb'\x00\x00\x00\x01|\x00\x00\x01', raw) if u]
    return hashlib.sha256(b''.join(u for u in units if u[0] & 31 in (7, 8))).hexdigest()[:16]


def decode_frames(mp4, first, count, W, H):
    """first번부터 count장(영상 프레임 번호)을 RGB 그림으로. passthrough가 없으면 -ss 뒤 첫 장이 한 번 더 나와 한 장씩 밀린다."""
    from PIL import Image
    first = max(0, first)
    raw = out_of([ff(), '-v', 'error', '-ss', f'{(first - 0.5) / FPS:.6f}' if first else '0', '-i', mp4, '-map', '0:v:0', '-fps_mode', 'passthrough', '-frames:v', count,
                  '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    n = W * H * 3
    return [Image.frombytes('RGB', (W, H), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)]


def decode_audio(src, start=None, dur=None):
    import numpy as np
    cmd = [ff(), '-v', 'error'] + (['-ss', f'{max(0.0, start):.6f}'] if start is not None else []) + (['-t', f'{dur:.6f}'] if dur else []) + \
          ['-i', src, '-map', '0:a:0', '-f', 's16le', '-ac', '1', '-ar', SR, '-']
    return np.frombuffer(out_of(cmd), dtype=np.int16).astype(np.float32) / 32768


# ── 검사 함수(이음새검수.py도 같은 정의를 쓴다) ──
def same_screen(a, b):
    """(바뀐 화소 %, 바뀐 영역) — 값이 12 넘게 바뀐 화소. 녹화 프레임에는 커서가 없고, 합성 프레임은 커서 자리만 다르다."""
    from PIL import ImageChops
    diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L').point(lambda v: 255 if v > 12 else 0)
    return round(diff.histogram()[255] / (diff.width * diff.height) * 100, 3), diff.getbbox()


def pop(x, at, sr=SR):
    """소리 튐: 경계 ±3ms 안 이웃 표본 차이가 0.05를 넘고, 경계에서 떨어진 ±20~250ms 표본 차이 99 %값의 3배도 넘으면 튐. (튐, 차이, 기준)"""
    import numpy as np
    d = np.abs(np.diff(x))
    near = d[max(0, at - int(0.003 * sr)):at + int(0.003 * sr)]
    far = np.concatenate([d[:max(0, at - int(0.02 * sr))], d[at + int(0.02 * sr):]])
    jump = float(near.max()) if near.size else 0.0
    ref = float(np.percentile(far, 99)) if far.size else 0.0
    return jump > max(0.05, 3 * ref), round(jump, 4), round(ref, 4)


def onset(x, thr=ONSET):
    """소리가 처음 문턱을 넘는 표본 번호(없으면 None)."""
    import numpy as np
    i = np.flatnonzero(np.abs(x) > thr)
    return int(i[0]) if i.size else None


# ── take 읽기 · 조각 나누기 ──
def tool_of(name, root):
    return find_tool(name, root)


def parse_spec(spec, default, root):
    parts = spec.split(':')
    T = default
    if len(parts) > 1 and (Path(root) / parts[0] / '촬영도구' / 'config.json').is_file():
        T, parts = tool_of(parts[0], root), parts[1:]
    head, end = parts[0], (parts[1] if len(parts) > 1 else '')
    take, _, start = head.partition('@')
    return T, take, float(start) if start else None, float(end) if end else None


def cue_segments(T, take):
    """take.sh가 남긴 실행 파일의 큐 파일 → {큐 id: segment}."""
    r = Path(T.work) / f'run-{take}-record.mjs'
    m = re.search(r"cueFile:'([^']+)'", r.read_text(encoding='utf-8')) if r.is_file() else None
    if m and Path(m.group(1)).is_file():
        return {c['id']: c.get('segment') for c in read(m.group(1)).get('cues', [])}
    return {}


def arrow(scale):
    """화살표를 8배 크게 그려 줄인다(후광 없음, 흰 채움 · 얇은 검은 테두리)."""
    from PIL import Image, ImageDraw
    k = 8; sx, sy = 20 / 25 * scale * k, 27 / 34 * scale * k
    im = Image.new('RGBA', (round(25 * sx) + 4, round(34 * sy) + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(x * sx, y * sy) for x, y in ARROW_PTS], fill=(255, 255, 255, 255), outline=(17, 17, 17, 255), width=round(1.7 * sx))
    return im.resize((round(im.width / k), round(im.height / k)), Image.LANCZOS)


def smooth(t):
    return t * t * (3 - 2 * t)


def pointer_at(ms, motions, start):
    """그 시각의 화살표 위치(CSS px). 이동 중이면 기록된 시작 시각 · 계획 길이로 페이지 애니메이션과 같은 곡선을 따른다."""
    pos = start
    for m in motions:
        g = m.get('glide', m['start'])
        if ms < g:
            break
        u = min(1.0, (ms - g) / m['planned_ms']) if m.get('planned_ms') else 1.0
        a = m['from']
        pos = (a['x'] + (m['x'] - a['x']) * smooth(u), a['y'] + (m['y'] - a['y']) * smooth(u))
    return pos


def plan_spec(spec, default, root, crf, ffv):
    """명세 하나 → 조각 목록(아직 인코딩 안 함)."""
    from PIL import Image
    T, take, start, end = parse_spec(spec, default, root)
    d = Path(T.work) / take
    t = read(d / 'timing.json')
    st = read(d / 'end-state.json') if (d / 'end-state.json').exists() else {}
    ps = read(d / 'pointer-start.json') if (d / 'pointer-start.json').exists() else None
    mode = (ps or {}).get('mode', 'page')
    if T.cfg.get('pointer') == 'overlay' and mode != 'overlay':
        raise RuntimeError(f'{take}: {T.name} config pointer=overlay인데 페이지 화살표를 그대로 녹화한 구간이다(두 화살표가 보인다). config.json pointer를 page로 하거나 다시 녹화한다')
    if t['error'] and end is None:
        raise RuntimeError(f'{take}: 오류로 끝난 take는 끝(:ms)을 준다: {t["error"][:120]}')
    start, end = start or 0.0, end if end is not None else float(t['duration'])
    if not 0 <= start < end <= t['duration'] + 1:
        raise RuntimeError(f'{take}: 범위 {start}~{end}가 녹화 0~{t["duration"]} 밖')
    for a in t['actions']:
        for b in (start, end):
            if a['time'] < b < a['time'] + a['duration']:
                raise RuntimeError(f'{take}: {b}ms가 말 {a["id"]}을 자른다')
            if a.get('actionStart') is not None and a.get('actionEnd') is not None and a['actionStart'] < b < a['actionEnd']:
                raise RuntimeError(f'{take}: {b}ms가 조작 {a["id"]}을 자른다')
    fr = sorted(t['frames'], key=lambda f: f['sourceTimestamp'])
    times = [max(0.0, f['sourceTimestamp'] * 1000 - (t['start'] or 0)) for f in fr]
    if not fr:
        raise RuntimeError(f'{take}: 프레임 없음')
    look = cue_segments(T, take) if any('segment' not in a for a in t['actions']) else {}
    seg = lambda a: a.get('segment', look.get(a['id']))
    inside = [a for a in t['actions'] if start <= a['time'] < end]
    cuts = [start] + [b['time'] for a, b in zip(inside, inside[1:]) if seg(a) is not None and seg(b) is not None and seg(a) != seg(b)] + [end]
    clicks = measure.recorded_clicks(d, st)
    tc = t.get('clicks') or []
    timed = len(tc) == len(clicks) and all('time' in c for c in tc)
    W, H = Image.open(d / fr[0]['file']).size
    scale = None
    if mode == 'overlay':
        vp = T.cfg.get('viewport') or {}
        scale = vp.get('deviceScaleFactor') or (W / vp['width'] if vp.get('width') else 1.0)
    chunks = []
    for i, (f, e) in enumerate(zip(cuts, cuts[1:])):
        n = round((e - f) * FPS / 1000)
        if n <= 0:
            raise RuntimeError(f'{take}: 조각 {f}~{e}ms가 한 프레임보다 짧다')
        idx = [max(0, bisect.bisect_right(times, f + k * 1000 / FPS) - 1) for k in range(n)]
        runs = []
        for j in idx:
            if runs and runs[-1][0] == j:
                runs[-1][1] += 1
            else:
                runs.append([j, 1])
        acts = [a for a in inside if f <= a['time'] < e]
        mots = [m for m in t['motions'] if m.get('glide', m['start']) < e and m['end'] > f]
        last = i == len(cuts) - 2
        cl = [c for c, x in zip(clicks, tc) if f <= x['time'] < e] if timed else (clicks if last else [])
        body = {'v': KEY_VERSION, 'tool': T.name, 'take': take, 'from': f, 'to': e, 'n': n, 'mode': mode, 'W': W, 'H': H, 'crf': crf, 'ff': ffv,
                'runs': [(fr[j]['file'], c, (d / fr[j]['file']).stat().st_size) for j, c in runs]}
        if mode == 'overlay':
            body.update(scale=scale, arrow=ARROW_PTS, pstart=[ps['x'], ps['y']], motions=[m for m in t['motions'] if m.get('glide', m['start']) < e])
        chunks.append(SimpleNamespace(
            key=hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24], tool=T, take=take, dir=d,
            from_ms=f, to_ms=e, frames=n, mode=mode, scale=scale, W=W, H=H, runs=[(fr[j]['file'], c) for j, c in runs], idx=idx, times=times, fr=fr,
            all_motions=t['motions'], pstart=(ps['x'], ps['y']) if ps else None,
            part=seg(acts[0]) if acts else None, audio=T.audio, error=t['error'] if last else None, recorded_ms=t['duration'],
            end_url=st.get('url') if last else None, end_tab=st.get('tab') if last else None,
            edge_age=[round(f - times[idx[0]]), round(f + (n - 1) * 1000 / FPS - times[idx[-1]])],
            cues=[{k: a.get(k) for k in ('id', 'text', 'time', 'duration', 'actionStart', 'actionEnd', 'commit')} | {'segment': seg(a)} for a in acts],
            motions=[{'start': m['start'], 'end': m['end'], 'glide': m.get('glide'), 'planned_ms': m.get('planned_ms'),
                      **dict(zip(('start_delay_ms', 'max_gap_ms'), measure.motion_gaps(m, times))), 'frames': sum(1 for x in times if m.get('glide', m['start']) <= x <= m['end'])}
                     for m in mots if m.get('glide', m['start']) >= f and m['end'] <= e],
            clicks=[{'x': c['x'], 'y': c['y'], 'dx': round(c['px'] - c['x'], 2), 'dy': round(c['py'] - c['y'], 2), 'gliding': c.get('gliding')} for c in cl],
            file=None, new=False))
    return chunks


def encode_chunk(c, crf, cache, log):
    """조각 하나를 영상만 든 mp4로(이미 있으면 그대로)."""
    path = cache / f'{c.key}.mp4'
    if path.exists():
        c.file = path
        return
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache / f'{c.key}.part.mp4'
    # 색 표시를 고정해 두 길(그림 파이프 · JPEG 이어 읽기)의 SPS가 같게 한다 — 다르면 -c copy로 이을 수 없다. 변환은 둘 다 BT.601(JPEG 원본과 같음).
    enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', crf, '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt470bg',
           '-chroma_sample_location', 'left', '-video_track_timescale', TB, '-frames:v', c.frames, '-an', tmp]
    if c.mode == 'overlay':
        from PIL import Image
        ARROW = arrow(c.scale)
        p = subprocess.Popen([str(x) for x in [ff(), '-y', '-v', 'warning', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{c.W}x{c.H}', '-r', FPS, '-i', '-',
                                               '-vf', 'setsar=1'] + enc], stdin=subprocess.PIPE)
        cur, im0 = None, None
        for k, j in enumerate(c.idx):
            f = c.fr[j]['file']
            if f != cur:
                cur, im0 = f, Image.open(c.dir / f).convert('RGB')
            im = im0.copy()
            x, y = pointer_at(c.from_ms + k * 1000 / FPS, c.all_motions, c.pstart)
            im.paste(ARROW, (round(x * c.scale), round(y * c.scale)), ARROW)
            p.stdin.write(im.tobytes())
        p.stdin.close()
        if p.wait():
            raise RuntimeError(f'{c.take}: 조각 인코딩 실패')
    else:
        # 원본 그림 하나가 이어지는 프레임 수만큼 길이를 준다(µs 누적으로 끝이 밀리지 않게). 마지막 그림을 한 번 더 넣어야 마지막 길이가 지켜진다.
        lines, at = [], 0
        for f, cnt in c.runs:
            a, b = round(at * 1e6 / FPS), round((at + cnt) * 1e6 / FPS)
            lines += [f'file {q((c.dir / f).resolve())}', 'option framerate 1000', f'duration {(b - a) / 1e6:.6f}']
            at += cnt
        lines += [lines[-3], 'option framerate 1000', 'duration 0.100000']
        lst = cache / f'{c.key}.concat'
        lst.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        run([ff(), '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', lst, '-vf', f'fps={FPS},setsar=1'] + enc)
        lst.unlink()
    got = len(packets(tmp)[1])
    if got != c.frames:
        raise RuntimeError(f'{c.take}: 조각 프레임 {got} ≠ {c.frames}')
    tmp.replace(path)
    c.file, c.new = path, True


def split_video(mp4, frames, want, cache):
    """합성기 출력 mp4를 조각 경계(키프레임)에서 -c copy로 잘라, want {조각 번호(0부터): 넣을 자리}만 조각_저장에 옮긴다.
    frames = 기록의 조각별 프레임 수. 잘린 조각 수나 프레임 수가 기록과 다르면(경계에 키프레임 없음) 멈춘다."""
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        cuts = [str(sum(frames[:i + 1])) for i in range(len(frames) - 1)]
        run([ff(), '-v', 'error', '-i', mp4, '-map', '0:v:0', '-c', 'copy', '-f', 'segment', '-segment_format', 'mp4', '-reset_timestamps', '1']
            + (['-segment_frames', ','.join(cuts)] if cuts else []) + [Path(tmp) / '%04d.mp4'])
        got = sorted(Path(tmp).glob('*.mp4'))
        if len(got) != len(frames) or [len(packets(g)[1]) for g in got] != list(frames):
            raise RuntimeError(f'{mp4.name}: 경계에서 자른 조각이 기록({len(frames)}조각, 프레임 {frames})과 다르다 — 경계에 키프레임이 없는 영상(join · cut · 재인코딩)')
        for i, dest in want.items():
            shutil.move(str(got[i]), dest)


# ── 합성 ──
def place_cues(chunks, overrides, ov_base, silent):
    """큐마다 영상 시각에 놓을 자리 · 음성 · 자막 글. 고친 음성은 오른쪽 정렬, 중복 id가 바뀌었는데 자리 지정이 없으면 멈춘다."""
    count = {}
    for c in chunks:
        for a in c.cues:
            count[a['id']] = count.get(a['id'], 0) + 1
    used, rows, cursor, at = set(), [], 0, 0
    for c in chunks:
        c0, c1 = at * 1000 / FPS, (at + c.frames) * 1000 / FPS
        for a in c.cues:
            g0 = c0 + a['time'] - c.from_ms
            r = {**a, 'chunk': c, 'g0': g0, 'g': g0, 'dur': a['duration'], 'say': a['text']}
            if not silent:
                meta_f = Path(c.audio) / f"{a['id']}.json"
                if not meta_f.is_file():
                    raise RuntimeError(f"{c.take}: 음성 캐시 없음 {meta_f} — 그 도구 config audio 자리에 음성을 둔다(ARROWS 옛 PC는 work/audio를 arrows/음성으로 복사)")
                meta = read(meta_f)
                hit = [i for i, o in enumerate(overrides) if o['segment'] == c.take and abs(o['time'] - a['time']) < 5]
                src, text = Path(c.audio) / f"{a['id']}.mp3", meta['text']
                changed = meta['text'] != a['text'] or meta['duration_ms'] != a['duration']
                if hit:
                    o = overrides[hit[0]]; used.add(hit[0])
                    src = (ov_base / o['file']).resolve()
                    side = src.with_suffix('.json')
                    text = o.get('text') or (read(side)['text'] if side.is_file() else a['text'])
                    r['override'] = o['file']
                elif changed and count[a['id']] > 1:
                    raise RuntimeError(f"{c.take} {a['time']}ms: 큐 {a['id']}이 합성 안에 {count[a['id']]}번 나오는데 캐시 음성이 녹화 때와 다르다 — "
                                       '--음성교체로 자리마다 파일을 정한다')
                pcm = out_of([ff(), '-v', 'error', '-i', src, '-f', 's16le', '-ac', '1', '-ar', SR, '-'])
                n = len(pcm) // 2
                r.update(pcm=pcm, src=str(src), lead=None)
                if hit or changed:
                    new = n * 1000 / SR
                    g = max(g0 + a['duration'] - new, cursor * 1000 / SR, c0)
                    if g + new > c1 + 1:
                        raise RuntimeError(f"{c.take}: 고친 음성 {a['id']}이 조각 끝을 넘는다({g + new:.0f} > {c1:.0f}ms)")
                    r.update(g=g, dur=round(new), say=text, revoiced=True)
                s = round(r['g'] / 1000 * SR)
                if s < cursor:
                    raise RuntimeError(f"말이 겹친다: {a['id']}({c.take})")
                cursor = s + n
                r['s'] = s
            rows.append(r)
        at += c.frames
    if len(used) != len(overrides):
        raise RuntimeError('맞는 자리가 없는 음성교체: ' + json.dumps([o for i, o in enumerate(overrides) if i not in used], ensure_ascii=False))
    return rows


def compose(name, chunks, out, *, crf=18, desc=None, silent=False, overrides=(), ov_base=Path('.'), accept=(), record_dir, origin=None, log=print):
    """조각 목록(인코딩 끝남) → 출력 mp4 · 자막 · 합성기록."""
    import numpy as np
    dest = Path(out.work) / name
    mp4 = dest / f'{name}_1080p.mp4'
    rec_path = Path(record_dir) / f'{name}.json'
    W, H = chunks[0].W, chunks[0].H
    bad = [c.take for c in chunks if (c.W, c.H) != (W, H)]
    if bad:
        raise RuntimeError(f'프레임 크기가 다른 구간: {bad}(첫 구간 {W}x{H})')
    sig = {sps_pps(c.file) for c in chunks}
    if len(sig) > 1:
        raise RuntimeError('조각 인코더 설정(SPS · PPS)이 다르다 — 다른 PC · 다른 ffmpeg로 만든 조각이 섞였다. 조각_저장을 비우고 이 PC에서 다시 합성한다')
    rows = place_cues(chunks, list(overrides), ov_base, silent)
    dest.mkdir(parents=True, exist_ok=True)
    nf = sum(c.frames for c in chunks)
    total = nf / FPS
    lst = dest / '조각.concat'
    lst.write_text(''.join(f'file {q(Path(c.file).resolve())}\n' for c in chunks), encoding='utf-8')
    if silent:
        run([ff(), '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', lst, '-map', '0:v', '-c', 'copy', mp4])
    else:
        wav = dest / 'narration.wav'
        with wave.open(str(wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            cur = 0
            for r in rows:
                w.writeframesraw(b'\0\0' * (r['s'] - cur)); w.writeframesraw(r['pcm']); cur = r['s'] + len(r['pcm']) // 2
            w.writeframesraw(b'\0\0' * max(0, round(total * SR) - cur))
        run([ff(), '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', lst, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', mp4])
        (dest / '자막.srt').write_text('\n\n'.join(f"{i+1}\n00:{stamp(r['g']).replace('.', ',')} --> 00:{stamp(r['g'] + r['dur']).replace('.', ',')}\n{r['say']}"
                                                  for i, r in enumerate(rows)) + '\n', encoding='utf-8')
    lst.unlink()
    run([ff(), '-v', 'error', '-i', mp4, '-f', 'null', '-'])
    tbv, vp = packets(mp4)
    fails = []
    if len(vp) != nf:
        fails.append(f'영상 패킷 {len(vp)} ≠ 조각 프레임 합 {nf}')
    pts = sorted(p for _, p, _ in vp)
    step = round(1 / FPS / tbv)
    steps = [b - a for a, b in zip(pts, pts[1:])]
    if any(s != step for s in steps):
        fails.append(f'프레임 간격이 고르지 않다(최소 {min(steps)} · 최대 {max(steps)}, 기대 {step})')
    ends = {'v': round(max(p + d for _, p, d in vp) * tbv, 3)}
    if not silent:
        ends['a'] = round(stream_end(mp4, 'a:0'), 3)
    for s, e in ends.items():
        if abs(e - total) > 0.1:
            fails.append(f'{s} 끝 {e:.3f}s ≠ 조각 합 {total:.3f}s (V-184)')
    # 이음새
    seams, at = [], 0
    for i, (a, b) in enumerate(zip(chunks, chunks[1:]), 1):
        at += a.frames
        t = at / FPS
        split = a.tool.name == b.tool.name and a.take == b.take and abs(a.to_ms - b.from_ms) < 1e-6
        s = {'번호': i, '시각': stamp(t * 1000), '앞': f'{a.take}@{a.to_ms:.0f}', '뒤': f'{b.take}@{b.from_ms:.0f}', '종류': '같은 녹화 나눔' if split else '이음새',
             '프레임간격_ok': pts[at] - pts[at - 1] == step if at < len(pts) else False, '원본정지_ms': [a.edge_age[1], b.edge_age[0]]}
        if not silent:
            x = decode_audio(mp4, t - 0.25, 0.5)
            p, jump, ref = pop(x, int(min(t, 0.25) * SR))
            near = [r for r in rows if t - 1e-6 <= r['g'] / 1000 < t + 1.0]
            off = []
            for r in near:
                y = decode_audio(mp4, r['g'] / 1000 - 0.1, r['dur'] / 1000 + 0.1)
                k, lead = onset(y), onset(np.frombuffer(r['pcm'], dtype=np.int16).astype(np.float32) / 32768)
                if k is not None and lead is not None:
                    off.append(round((k / SR - 0.1) * 1000 - lead * 1000 / SR, 1))
            s.update(소리튐=p, 표본차=jump, 기준=ref, 소리시작_어긋남_ms=off)
            s['소리_ok'] = not p and all(abs(o) <= 1000 / FPS for o in off)
        if not split:
            fr = decode_frames(mp4, at - 7, 14, W, H)
            if len(fr) >= 8:
                from PIL import Image, ImageDraw
                pct, box = same_screen(*(im.resize((W // 4, H // 4), Image.BOX) for im in fr[6:8]))
                s.update(바뀐화소퍼센트=pct, 바뀐영역=[v * 4 for v in box] if box else None, 화면_ok=pct <= SAME_PCT)
                sheet = Image.new('RGB', (1920, 560), 'white'); dr = ImageDraw.Draw(sheet)
                for j, (im, lab) in enumerate([(fr[0], '-0.2s'), (fr[-1], '+0.2s')]):
                    sheet.paste(im.resize((960, 540)), (j * 960, 20)); dr.text((j * 960 + 5, 3), f'이음새 {i} {stamp(t * 1000)} {lab}', fill='black')
                sheet.save(dest / f'이음새_{i:02}.jpg', quality=85)
                s['그림'] = f'이음새_{i:02}.jpg'
            else:
                s['화면_ok'] = False
        s['허용'] = i in accept
        s['판정'] = '통과' if all(v for k, v in s.items() if k.endswith('_ok')) else ('허용' if s['허용'] else '실패')
        seams.append(s)
    # 기록
    timeline, motions, clicks, segs, at = [], [], [], [], 0
    for c in chunks:
        o = at * 1000 / FPS - c.from_ms
        segs.append({'segment': c.take, 'tool': c.tool.name, 'part': c.part, 'from_ms': c.from_ms, 'used_ms': c.to_ms - c.from_ms, 'start_s': round(at / FPS, 3),
                     'frames': c.frames, 'mode': c.mode, 'recorded_ms': c.recorded_ms, 'error': c.error, 'end_url': c.end_url, 'end_tab': c.end_tab})
        for m in c.motions:
            motions.append({'segment': c.take, 'mode': c.mode, 'start_ms': round(o + m['start']), 'duration_ms': round(m['end'] - m['start']),
                            'planned_ms': m['planned_ms'], 'frames': m['frames'], 'start_delay_ms': m['start_delay_ms'], 'max_gap_ms': m['max_gap_ms']})
        clicks += [{'segment': c.take, **k} for k in c.clicks]
        at += c.frames
    for i, r in enumerate(rows):
        x = {'id': r['id'], 'speech': [stamp(r['g']), stamp(r['g'] + r['dur'])]}
        if r.get('revoiced'):
            x['revoiced'] = r.get('override') or 'cache'
        if r.get('actionStart') is not None:
            o = r['g0'] - r['time']
            x['action'] = [stamp(o + r['actionStart']), stamp(o + r['actionEnd']) if r.get('actionEnd') is not None else None]
            x['commit'] = stamp(o + r['commit']) if r.get('commit') else None
            x['commit_before_speech_end_ms'] = round(r['g'] + r['dur'] - (o + r['commit'])) if r.get('commit') else None
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if nxt and r.get('actionEnd') is not None:
                x['next_speech_after_action_ms'] = round(nxt['g'] - (o + r['actionEnd']))
        timeline.append(x)
    page = [m for m in motions if m['mode'] == 'page']
    report = {'output': mp4.name, 'duration_s': round(total, 3), 'source': desc or f'{W}x{H} JPEG screencast', 'output_fps': FPS,
              'pointer': sorted({c.mode for c in chunks}), 'segments': segs, 'speech_cues': len(rows), 'cue_timeline': timeline, 'clicks': clicks,
              'motion_summary': {'count': len(motions), 'page_count': len(page), 'max_gap_ms_max': max((m['max_gap_ms'] for m in page), default=None),
                                 'start_delay_max_ms': max((m['start_delay_ms'] for m in page if m['start_delay_ms'] is not None), default=None),
                                 'over_100ms': [m for m in page if m['max_gap_ms'] >= 100]},
              'motions': motions, 'decode': 'passed', 'stream_end_s': ends, 'seams': seams, 'voice': '없음(시험)' if silent else 'config audio 캐시',
              'revoiced': [x['id'] for x in timeline if x.get('revoiced')], 'not_verified': ['직접 청취', '사용자 재생 확인']}
    record = {**report, '이름': name, '도구': out.name, 'crf': crf, 'fps': FPS, 'size': [W, H], 'origin': origin,
              '음성교체': [{**o, 'file': os.path.relpath((ov_base / o['file']).resolve(), record_dir)} for o in overrides],
              '조각': [{'키': c.key, '도구': c.tool.name, 'take': c.take, 'from_ms': c.from_ms, 'to_ms': c.to_ms, 'frames': c.frames, 'mode': c.mode,
                        'part': c.part, 'audio': os.path.relpath(c.audio, record_dir) if c.audio else None, 'error': c.error, 'recorded_ms': c.recorded_ms,
                        'end_url': c.end_url, 'end_tab': c.end_tab, 'edge_age': c.edge_age, 'cues': c.cues, 'motions': c.motions, 'clicks': c.clicks}
                       for c in chunks],
              'mp4': {'sha256': sha256(mp4), 'video_packets': len(vp), 'bytes': mp4.stat().st_size}}
    bad_seams = [s for s in seams if s['판정'] == '실패']
    if fails or bad_seams:
        (dest / '합성기록_실패.json').write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        raise RuntimeError('합성 검사 실패 — ' + '; '.join(fails + [f"이음새 {s['번호']}({s['시각']}): " + ', '.join(k for k, v in s.items() if k.endswith('_ok') and not v)
                                                               for s in bad_seams]) + f' — {dest}의 이음새 그림을 보고 맞으면 --이음새허용 <번호>')
    Path(record_dir).mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    log(f"조각 {len(chunks)} · 새로 {sum(c.new for c in chunks)}" + (f" · 영상에서 잘라 옴 {sum(getattr(c, 'cut', False) for c in chunks)}" if any(getattr(c, 'cut', False) for c in chunks) else ''))
    log(json.dumps({k: report[k] for k in ['output', 'duration_s', 'pointer', 'speech_cues']} | {'이음새': [s['판정'] for s in seams], '합성기록': str(rec_path)}, ensure_ascii=False))
    return record


def _out_tool(tool_name, work, audio, root, record_dir):
    if work is not None:
        return SimpleNamespace(name=tool_name or 'neo4j', cfg={}, work=Path(work), audio=Path(audio) if audio else None,
                               record=Path(record_dir) if record_dir else Path(work) / '합성기록')
    return tool_of(tool_name or '포털', root)


def _check_free(T, name, record_dir):
    mp4 = Path(T.work) / name / f'{name}_1080p.mp4'
    rec = Path(record_dir) / f'{name}.json'
    for p in (mp4, rec):
        if p.exists():
            raise FileExistsError(f'기존 결과 보존: {p} — 새 이름으로 합성한다')


def encode(name, specs, work=None, audio=None, crf=18, desc=None, *, tool_name=None, root=TOOLS, silent=False, overrides=None, accept=(), record_dir=None, log=print):
    """명세들 → 조각(바뀐 것만 인코딩) → 출력 · 합성기록. work · audio를 주면 config 대신 그 폴더를 쓴다(neo4j)."""
    T = _out_tool(tool_name, work, audio, root, record_dir)
    record_dir = Path(record_dir) if record_dir else T.record
    _check_free(T, name, record_dir)
    ov, ov_base = (read(overrides), Path(overrides).resolve().parent) if overrides else ([], Path('.'))
    ffv = out_of([ff(), '-version']).decode().splitlines()[0]
    chunks = [c for s in specs for c in plan_spec(s, T, root, crf, ffv)]
    for c in chunks:
        encode_chunk(c, crf, Path(T.work) / '조각_저장', log)
    return compose(name, chunks, T, crf=crf, desc=desc, silent=silent, overrides=ov, ov_base=ov_base, accept=accept, record_dir=record_dir,
                   origin={'명세': list(specs)}, log=log)


def replace(record_path, repl, out_name=None, video=None, *, root=TOOLS, overrides=None, accept=(), log=print):
    """합성기록 하나에서 <번호>=<명세> 조각만 바꿔 다시 낸다. 바꾸지 않은 조각은 조각_저장에서, 없으면 기록의 mp4를 경계에서 잘라 쓴다."""
    record_path = Path(record_path).resolve()
    rec = read(record_path)
    if not rec.get('조각'):
        raise RuntimeError(f'{record_path.name}: 조각 기록이 없는 옛 합성(--기록으로 옮긴 판) — 교체할 수 없다. 전체를 다시 합성한다')
    T = tool_of(rec['도구'], root) if (Path(root) / rec['도구'] / '촬영도구' / 'config.json').is_file() else None
    if T is None:
        raise RuntimeError(f"도구 {rec['도구']}의 config가 없다 — 그 도구의 합성(lesson_pipeline 등)에서 다시 합성한다")
    record_dir = record_path.parent
    name = out_name
    if not name:
        k = 2
        while (Path(T.work) / f"{rec['이름']}-{k}").exists() or (record_dir / f"{rec['이름']}-{k}.json").exists():
            k += 1
        name = f"{rec['이름']}-{k}"
    _check_free(T, name, record_dir)
    ffv = out_of([ff(), '-version']).decode().splitlines()[0]
    cache = Path(T.work) / '조각_저장'
    chunks, keep = [], []
    for i, r in enumerate(rec['조각'], 1):
        if i in repl:
            for c in plan_spec(repl[i], T, root, rec['crf'], ffv):
                encode_chunk(c, rec['crf'], cache, log); chunks.append(c)
            continue
        ct = tool_of(r['도구'], root) if (Path(root) / r['도구'] / '촬영도구' / 'config.json').is_file() else SimpleNamespace(name=r['도구'], cfg={})
        c = SimpleNamespace(key=r['키'], tool=ct, take=r['take'], from_ms=r['from_ms'], to_ms=r['to_ms'], frames=r['frames'], mode=r['mode'],
                            W=rec['size'][0], H=rec['size'][1], part=r['part'], audio=(record_dir / r['audio']).resolve() if r['audio'] else None,
                            error=r['error'], recorded_ms=r['recorded_ms'], end_url=r['end_url'], end_tab=r['end_tab'], edge_age=r['edge_age'],
                            cues=r['cues'], motions=r['motions'], clicks=r['clicks'], file=cache / f"{r['키']}.mp4", new=False, cut=False, index=i - 1)
        chunks.append(c); keep.append(c)
    missing = [c for c in keep if not c.file.exists()]
    if missing:
        mp4 = Path(video) if video else Path(T.work) / rec['이름'] / rec['output']
        if not mp4.is_file():
            raise RuntimeError(f'바꾸지 않을 조각 {len(missing)}개가 조각_저장에 없고 원본 영상도 없다: {mp4} (--영상 <mp4>)')
        if sha256(mp4) != rec['mp4']['sha256']:
            raise RuntimeError(f'{mp4.name}: sha256이 합성기록과 다르다 — 합성기 출력 그대로가 아니다(join · cut · 재인코딩). 교체할 수 없고 전체를 다시 합성한다')
        split_video(mp4, [r['frames'] for r in rec['조각']], {c.index: c.file for c in missing}, cache)
        for c in missing:
            c.cut = True
    # 음성교체: 새로 주면 그것, 아니면 앞 합성에 쓴 것(기록에 합성기록 폴더 기준 상대 경로로 남아 있다)
    ov, ov_base = (read(overrides), Path(overrides).resolve().parent) if overrides else (rec.get('음성교체', []), record_dir)
    return compose(name, chunks, T, crf=rec['crf'], desc=rec.get('source'), silent=rec.get('voice') == '없음(시험)', overrides=ov, ov_base=ov_base,
                   accept=accept, record_dir=record_dir, origin={'교체': record_path.name, '바꾼 조각': {str(k): v for k, v in repl.items()}}, log=log)


def from_verification(vpath, T, record_dir=None):
    """옛 합성기(도구마다 있던 encode.py)의 verification.json → 합성기록. 조각 기록이 없어 --교체는 안 되고, 대본 · 가이드 생성기가 읽는 값만 옮긴다."""
    vpath = Path(vpath).resolve()
    v = read(vpath)
    name = vpath.parent.name
    record_dir = Path(record_dir) if record_dir else T.record
    dest = record_dir / f'{name}.json'
    if dest.exists():
        raise FileExistsError(f'기존 합성기록 보존: {dest}')
    ms = dict(v.get('motion_summary') or {})
    motions = [dict(m) for m in v.get('motions', [])]
    for m in motions:
        if 'max_gap_ms' not in m and 'source_max_gap_ms' in m:
            m['max_gap_ms'] = m.pop('source_max_gap_ms'); m['frames'] = m.pop('source_frames', None)
    if 'max_gap_ms_max' not in ms:
        ms['max_gap_ms_max'] = ms.pop('source_max_gap_ms_max', None)
    if not isinstance(ms.get('over_100ms'), list):
        ms.pop('source_over_100ms', None); ms['over_100ms'] = [m for m in motions if (m.get('max_gap_ms') or 0) >= 100]
    mp4 = vpath.parent / v.get('output', '')
    rec = {**v, 'motions': motions, 'motion_summary': ms, '이름': name, '도구': T.name, '조각': None,
           'origin': {'옮긴 기록': f'{name}/verification.json', '까닭': '옛 합성기 — 조각 경계에 키프레임이 없어 교체 불가'},
           'mp4': {'sha256': sha256(mp4), 'bytes': mp4.stat().st_size} if mp4.is_file() and v.get('output') else None}
    record_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'합성기록 {dest}')
    return rec


# ── 자가시험 ──
def self_test():
    """시험 자료로 실제 인코딩해 판정한다. 어긋나면 False."""
    import numpy as np
    from PIL import Image
    ok, notes = True, []

    def check(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
            notes.append(msg)

    tmp = Path(tempfile.mkdtemp(prefix='합성시험-'))
    root = tmp / '촬영'
    for nm, cfg in [('포털', {'work': '../../work/포털', 'audio': '../음성', 'viewport': {'width': 1280, 'height': 720, 'deviceScaleFactor': 1.5}, 'pointer': 'overlay'}),
                    ('vscode', {'work': '../../work/vscode', 'audio': '../음성', 'viewport': {'width': 2304, 'height': 1296}})]:
        (root / nm / '촬영도구').mkdir(parents=True)
        (root / nm / '음성').mkdir()
        (root / nm / '촬영도구' / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    P, V = tool_of('포털', root), tool_of('vscode', root)
    tone_n = [0]

    def voice(Tl, cid, text, sec, freq=440):
        tone_n[0] += 1
        mp3 = Path(Tl.audio) / f'{cid}.mp3'
        run([ff(), '-y', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency={freq}:duration={sec}', '-af', 'afade=t=in:d=0.005,adelay=40,apad=pad_dur=0.03',
             '-ac', '1', '-ar', SR, '-b:a', '128k', mp3])
        n = len(out_of([ff(), '-v', 'error', '-i', mp3, '-f', 's16le', '-ac', '1', '-ar', SR, '-'])) // 2
        (Path(Tl.audio) / f'{cid}.json').write_text(json.dumps({'id': cid, 'text': text, 'duration_ms': round(n * 1000 / SR)}, ensure_ascii=False), encoding='utf-8')
        return round(n * 1000 / SR)

    def take(Tl, name, sec, cues, overlay, first=None, seed=0, segment_in_actions=True, pstart=(400, 300)):
        d = Path(Tl.work) / name
        (d / 'frames').mkdir(parents=True)
        run([ff(), '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size=1920x1080:rate=20,hue=h={seed * 40}', '-t', sec, '-q:v', '4', '-start_number', '0', d / 'frames/%06d.jpg'])
        files = sorted((d / 'frames').glob('*.jpg'))
        if first is not None:
            shutil.copyfile(first, files[0])
        st0 = 5_000_000.0 + seed * 100_000
        rng = np.random.default_rng(seed)
        times = [0.0] + [k * 50 + float(rng.integers(-12, 12)) for k in range(1, len(files))]
        frames = [{'file': f'frames/{f.name}', 'time': x, 'sourceTimestamp': (st0 + x) / 1000} for f, x in zip(files, times)]
        acts, mots, pos = [], [], {'x': pstart[0], 'y': pstart[1]}
        for cid, seg, at, text in cues:
            dur = read(Path(Tl.audio) / f'{cid}.json')['duration_ms']
            a = {'id': cid, 'text': text, 'time': at, 'duration': dur, 'actionStart': at + 100, 'actionEnd': at + 500, 'commit': at + 450}
            if segment_in_actions:
                a['segment'] = seg
            acts.append(a)
            to = {'x': pos['x'] + 60, 'y': pos['y'] + 25}
            m = {'start': at + 100, 'end': at + 500, 'from': dict(pos), **to, 'planned_ms': 350}
            if overlay:
                m['glide'] = at + 120
            mots.append(m); pos = to
        (d / 'timing.json').write_text(json.dumps({'start': st0, 'frames': frames, 'actions': acts, 'motions': mots, 'clicks': [{'x': m['x'], 'y': m['y'], 'time': m['end']} for m in mots],
                                                   'duration': sec * 1000, 'error': None}), encoding='utf-8')
        (d / 'end-state.json').write_text(json.dumps({'url': 'http://시험/', 'tab': 'home', 'clicks': [{'x': m['x'], 'y': m['y'], 'px': m['x'], 'py': m['y']} for m in mots]}), encoding='utf-8')
        if overlay:
            (d / 'pointer-start.json').write_text(json.dumps({'x': pstart[0], 'y': pstart[1], 'mode': 'overlay'}), encoding='utf-8')
        return d, frames, mots

    def last_src(d, frames, ms):
        xs = [f['time'] for f in frames]
        return d / frames[max(0, bisect.bisect_right(xs, ms - 1000 / FPS) - 1)]['file']

    try:
        for cid, sec, fq in [('A1', .6, 300), ('A2', .5, 350), ('D1', .4, 400), ('B1', .6, 450), ('B2', .6, 500), ('B3', .5, 550), ('B4', .5, 600)]:
            voice(P, cid, f'{cid} 문장', sec, fq)
        for cid, sec, fq in [('V1', .7, 650), ('D1', .4, 400)]:
            voice(V, cid, f'{cid} 문장', sec, fq)
        da, fa, ma = take(P, 'a', 3, [('A1', 1, 300, 'A1 문장'), ('A2', 1, 1200, 'A2 문장'), ('D1', 1, 2000, 'D1 문장')], True, seed=1)
        # b: 구간 2 · 3을 한 녹화로(큐에 segment가 없고 take.sh 실행 파일의 큐 파일에서 찾는다) → 2800ms에서 저절로 나뉜다
        bq = tmp / 'b_큐.json'
        bq.write_text(json.dumps({'cues': [{'id': i, 'segment': s} for i, s in [('B1', 2), ('B2', 2), ('B3', 3), ('B4', 3)]]}), encoding='utf-8')
        db, fb, mb = take(P, 'b', 5, [('B1', 2, 300, 'B1 문장'), ('B2', 2, 1400, 'B2 문장'), ('B3', 3, 2800, 'B3 문장'), ('B4', 3, 3900, 'B4 문장')], True,
                          first=last_src(da, fa, 3000), seed=2, segment_in_actions=False, pstart=(ma[-1]['x'], ma[-1]['y']))
        (Path(P.work) / 'run-b-record.mjs').write_text(f"await take({{mode:'record',name:'b',cueFile:'{bq}',module:'x.mjs'}});\n", encoding='utf-8')
        dv, fv, mv = take(V, 'v', 3, [('V1', 4, 400, 'V1 문장'), ('D1', 4, 1500, 'D1 문장')], False, first=last_src(db, fb, 5000), seed=3)
        db2, _, _ = take(P, 'b2', 3, [('B1', 2, 300, 'B1 문장'), ('B2', 2, 1400, 'B2 문장')], True, first=last_src(da, fa, 3000), seed=4, pstart=(ma[-1]['x'], ma[-1]['y']))
        take(P, 'x', 2, [('A1', 9, 300, 'A1 문장')], True, seed=5)
        logs = []
        lg = lambda m: (logs.append(m), print(m))
        specs = ['a', 'b', 'vscode:v']
        want = [round(3000 * FPS / 1000), round(2800 * FPS / 1000), round(2200 * FPS / 1000), round(3000 * FPS / 1000)]

        # 1. 합성 A: overlay · page, 한 녹화 두 구간, 도구 접두, viewport가 프레임과 다른 config
        ra = encode('시험A', specs, root=root, log=lg)
        A = Path(P.work) / '시험A' / '시험A_1080p.mp4'
        check([c['frames'] for c in ra['조각']] == want, f'조각 프레임 {[c["frames"] for c in ra["조각"]]} ≠ {want}')
        check(ra['mp4']['video_packets'] == sum(want), f"영상 패킷 {ra['mp4']['video_packets']} ≠ {sum(want)}")
        check([c['mode'] for c in ra['조각']] == ['overlay', 'overlay', 'overlay', 'page'], f"화살표 방식 {[c['mode'] for c in ra['조각']]}")
        check(ra['size'] == [1920, 1080], f"출력 크기 {ra['size']}")
        check(logs[-2].startswith('조각 4 · 새로 4'), f'로그 {logs[-2]}')
        check([s['종류'] for s in ra['seams']] == ['이음새', '같은 녹화 나눔', '이음새'] and all(s['판정'] == '통과' for s in ra['seams']), f"이음새 {ra['seams']}")
        if shutil.which('ffprobe'):
            keys = [round(float(x.strip(b',')) * FPS) for x in out_of(['ffprobe', '-v', 'error', '-select_streams', 'v', '-skip_frame', 'nokey', '-show_entries', 'frame=pts_time', '-of', 'csv=p=0', A]).split()]
            bounds = [sum(want[:i]) for i in range(len(want))]
            check(all(b in keys for b in bounds), f'경계 키프레임 {bounds} ⊄ {keys}')
        x = decode_audio(A)
        lead = lambda Tl, cid: onset(decode_audio(Path(Tl.audio) / f'{cid}.mp3')) / SR
        at = 0
        for c in ra['조각']:
            for a in c['cues']:
                exp = at / FPS + (a['time'] - c['from_ms']) / 1000 + lead(V if c['도구'] == 'vscode' else P, a['id'])
                k = onset(x[int((exp - 0.2) * SR):])
                got = (exp - 0.2) + k / SR if k is not None else None
                check(got is not None and abs(got - exp) <= 1 / FPS, f"{a['id']} 소리 시작 {got} ≠ {exp:.3f}")
            at += c['frames']
        check(all(abs(e - sum(want) / FPS) <= 0.1 for e in ra['stream_end_s'].values()), f"끝 시각 {ra['stream_end_s']}")
        f0 = decode_frames(A, 0, 1, 1920, 1080)[0]
        px = f0.getpixel((round(400 * 1.5 + 4), round(300 * 1.5 + 12)))
        check(min(px) > 200, f'화살표가 안 보인다 {px}')
        vf = decode_frames(A, sum(want[:3]) + 5, 1, 1920, 1080)[0]
        src = Image.open(dv / fv[bisect.bisect_right([f['time'] for f in fv], 5 * 1000 / FPS) - 1]['file']).convert('RGB')
        check(same_screen(vf.resize((480, 270), Image.BOX), src.resize((480, 270), Image.BOX))[0] < SAME_PCT, 'page 구간 화면이 원본 프레임과 다르다')
        md5 = lambda f, a=0, n=None: out_of([ff(), '-v', 'error', '-ss', f'{(a - 0.5) / FPS:.6f}' if a else '0', '-i', f, '-map', '0:v'] + (['-frames:v', n] if n else []) + ['-f', 'framemd5', '-']).decode().split('\n')
        h = lambda f, a=0, n=None: [l.split(',')[-1] for l in md5(f, a, n) if l and not l.startswith('#')]

        # 2. 같은 명세를 다른 이름으로 → 새로 0, 영상 같음
        logs.clear(); rb = encode('시험B', specs, root=root, log=lg)
        check(logs[-2].startswith('조각 4 · 새로 0'), f'다시 합성 로그 {logs[-2]}')
        check(h(A) == h(Path(P.work) / '시험B' / '시험B_1080p.mp4'), '다시 합성한 영상 프레임이 다르다')

        # 3. 큐 하나 말만 고침(B2, 짧게) → 새로 0, 오른쪽 정렬
        old = read(Path(P.audio) / 'B2.json')['duration_ms']
        new = voice(P, 'B2', 'B2 고친 문장', .35, 520)
        logs.clear(); rc = encode('시험C', specs, root=root, log=lg)
        check(logs[-2].startswith('조각 4 · 새로 0'), f'말만 고친 합성 로그 {logs[-2]}')
        C = Path(P.work) / '시험C' / '시험C_1080p.mp4'
        exp = sum(want[:1]) / FPS + (1400 + old - new) / 1000 + lead(P, 'B2')
        y = decode_audio(C)
        k = onset(y[int((exp - 0.3) * SR):])
        got = exp - 0.3 + k / SR
        check(abs(got - exp) <= 1 / FPS, f'고친 음성 오른쪽 정렬 {got:.3f} ≠ {exp:.3f}')
        check('B2 고친 문장' in (Path(P.work) / '시험C' / '자막.srt').read_text(encoding='utf-8'), '고친 글이 자막에 없다')
        check(rc['revoiced'] == ['B2'], f"고친 음성 {rc['revoiced']}")

        # 4. --교체: 조각_저장을 비우고 2번(b의 구간 2)을 b2로 → 새로 1, 나머지는 시험A에서 잘라 옴, 바꾸지 않은 조각 프레임 같음
        #    b2는 끝 화면이 b@2800과 다른 녹화라 이음새 2는 화면이 달라 실패가 맞다 — 허용으로 낸다
        shutil.rmtree(Path(P.work) / '조각_저장')
        logs.clear(); re_ = replace(P.record / '시험A.json', {2: 'b2'}, root=root, accept={2}, log=lg)
        E = Path(P.work) / re_['이름'] / f"{re_['이름']}_1080p.mp4"
        check(logs[-2].startswith('조각 4 · 새로 1 · 영상에서 잘라 옴 3'), f'교체 로그 {logs[-2]}')
        ne = [c['frames'] for c in re_['조각']]
        check(re_['mp4']['video_packets'] == sum(ne), '교체 영상 패킷 수')
        for i in (0, 2, 3):
            a0, e0 = sum(want[:i]), sum(ne[:i])
            check(h(A, a0, want[i]) == h(E, e0, ne[i]), f'교체 뒤 바꾸지 않은 조각 {i + 1} 프레임이 다르다')
        try:
            (Path(P.work) / '시험A' / '시험A_1080p.mp4').write_bytes(A.read_bytes() + b'\0')
            shutil.rmtree(Path(P.work) / '조각_저장')
            replace(P.record / '시험A.json', {2: 'b2'}, out_name='시험E2', root=root, log=lambda m: None)
            check(False, '바뀐 영상으로 교체가 멈추지 않았다')
        except RuntimeError as e:
            check('sha256' in str(e), f'바뀐 영상 교체 오류 {e}')

        # 5. 중복 id(D1이 a와 v에)의 캐시 글이 바뀜 → 자리 지정 없이 멈춤, --음성교체로 두 자리 지정하면 통과
        voice(P, 'D1', 'D1 고친 문장', .3, 410); voice(V, 'D1', 'D1 고친 문장', .3, 410)
        try:
            encode('시험D', specs, root=root, log=lambda m: None)
            check(False, '중복 id 변경이 멈추지 않았다')
        except RuntimeError as e:
            check('번 나오는데' in str(e), f'중복 id 오류 {e}')
        ovj = tmp / '음성교체.json'
        shutil.copyfile(Path(P.audio) / 'D1.mp3', tmp / 'd1a.mp3'); shutil.copyfile(Path(V.audio) / 'D1.mp3', tmp / 'd1v.mp3')
        ovj.write_text(json.dumps([{'segment': 'a', 'time': 2000, 'file': 'd1a.mp3', 'text': 'D1 고친 문장'}, {'segment': 'v', 'time': 1500, 'file': 'd1v.mp3'}]), encoding='utf-8')
        rd = encode('시험D', specs, root=root, overrides=ovj, log=lambda m: None)
        check(sorted(rd['revoiced']) == ['B2', 'D1', 'D1'], f"음성교체 결과 {rd['revoiced']}")
        check(not any(os.path.isabs(o['file']) for o in rd['음성교체']), f"음성교체 경로가 이 PC 절대 경로 {rd['음성교체']}")
        rd2 = replace(P.record / '시험D.json', {1: 'a'}, root=root, log=lambda m: None)   # 기록의 음성교체(합성기록 폴더 기준)를 그대로 읽는다
        check(sorted(rd2['revoiced']) == ['B2', 'D1', 'D1'], f"교체 뒤 음성교체 결과 {rd2['revoiced']}")

        # 6. 다른 화면이 만나는 이음새 → 멈춤, --이음새허용이면 통과
        try:
            encode('시험F', ['a', 'x'], root=root, log=lambda m: None)
            check(False, '다른 화면 이음새가 멈추지 않았다')
        except RuntimeError as e:
            check('이음새 1' in str(e) and '화면_ok' in str(e), f'이음새 실패 오류 {e}')
            check((Path(P.work) / '시험F' / '이음새_01.jpg').exists(), '이음새 그림 없음')
        rf = encode('시험F2', ['a', 'x'], root=root, accept={1}, log=lambda m: None)
        check(rf['seams'][0]['판정'] == '허용', f"허용 판정 {rf['seams'][0]['판정']}")

        # 7. 소리 튐 판정: 이어진 사인 · 경계에서 시작하는 사인은 통과, 경계에서 값이 뛰면 튐
        tt = np.arange(SR // 2) / SR
        sine = (0.3 * np.sin(2 * np.pi * 440 * tt)).astype(np.float32)
        at = SR // 4
        check(not pop(sine, at)[0], '이어진 사인을 튐으로 봄')
        start = sine.copy(); start[:at] = 0
        check(not pop(start, at)[0], '경계에서 시작하는 사인을 튐으로 봄')
        step = sine.copy(); step[at:] += 0.5
        check(pop(step, at)[0], '경계 값 뜀을 못 잡음')

        # 8. 옛 verification.json → 합성기록(키 맞춤), 교체는 거절
        old_dir = Path(P.work) / '옛합본'; old_dir.mkdir()
        (old_dir / 'verification.json').write_text(json.dumps({'output': '옛합본_1080p.mp4', 'duration_s': 10.0, 'segments': [{'segment': 'take-n25', 'used_ms': 10000}],
                                                                'speech_cues': 0, 'cue_timeline': [], 'motions': [{'source_max_gap_ms': 120, 'source_frames': 3}],
                                                                'motion_summary': {'count': 1, 'source_max_gap_ms_max': 120, 'source_over_100ms': 1}}), encoding='utf-8')
        rv = from_verification(old_dir / 'verification.json', P)
        check(rv['motion_summary']['max_gap_ms_max'] == 120 and len(rv['motion_summary']['over_100ms']) == 1, f"옮긴 기록 {rv['motion_summary']}")
        try:
            replace(P.record / '옛합본.json', {1: 'a'}, root=root, log=lambda m: None)
            check(False, '옛 기록 교체가 멈추지 않았다')
        except RuntimeError as e:
            check('조각 기록이 없는' in str(e), f'옛 기록 교체 오류 {e}')
        try:
            encode('시험A', specs, root=root, log=lambda m: None)
            check(False, '같은 이름 덮어쓰기가 멈추지 않았다')
        except FileExistsError:
            pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        check(False, f'예외: {e}')
    check(measure.self_test(), 'measure.py 자가시험 실패')
    print(json.dumps({'자가시험': '통과' if ok else '실패', '어긋남': notes, '시험 폴더': str(tmp) if not ok else '지움'}, ensure_ascii=False, indent=1))
    if ok:
        shutil.rmtree(tmp)
    return ok


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if '--자가시험' in argv:
        return 0 if self_test() else 1
    args, opt = [], {}
    it = iter(argv)
    for a in it:
        if a in ('--도구', '--음성교체', '--이음새허용', '--교체', '--기록', '--영상', '--출력'):
            opt[a] = next(it)
        elif a == '--silent':
            opt[a] = True
        else:
            args.append(a)
    accept = {int(x) for x in opt.get('--이음새허용', '').split(',') if x}
    if '--기록' in opt:
        from_verification(opt['--기록'], tool_of(opt.get('--도구', '포털'), TOOLS))
    elif '--교체' in opt:
        repl = {}
        for a in args:
            k, _, v = a.partition('=')
            repl[int(k)] = v
        replace(opt['--교체'], repl, opt.get('--출력'), opt.get('--영상'), overrides=opt.get('--음성교체'), accept=accept)
    else:
        encode(args[0], args[1:], tool_name=opt.get('--도구', '포털'), silent='--silent' in opt, overrides=opt.get('--음성교체'), accept=accept)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
