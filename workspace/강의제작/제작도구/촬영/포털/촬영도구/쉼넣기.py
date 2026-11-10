"""이미 만든 실습 영상을 다시 찍지 않고 고친다 — 말 사이에 쉼(멈춘 화면 + 무음)을 넣고, 바꾼 큐의 음성을 끼우고, 뺄 화면을 자른다.
언제: 실습 영상의 말이 쉼 없이 붙었을 때(영상.md V-14), 녹화 원본 없이 몇 큐의 말만 바꿀 때(영상 길 18), 여는 부분 같은 화면을 뺄 때.
화면은 그대로 두고 소리와 함께 늘리므로 말과 조작의 싱크가 지켜진다. 자막 · 장(chapter)도 같은 만큼 민다.

명령(저장소 루트에서, <py>는 공통.md 「자료」, P=workspace/강의제작/제작도구/촬영/포털/촬영도구, ffmpeg는 PATH나 환경변수 FFMPEG):
  <py> $P/쉼넣기.py 초안 <영상.mp4> <자막.srt> <계획.json> [--큐 <영상을 만든 판의 큐.json> …]   # 계획 초안(덮어쓰지 않는다)
  <py> $P/쉼넣기.py 바꿈 <계획.json> <큐.json>=<음성 폴더> …                                # 지금 큐 글이 옛 글과 다른 단위에 새글 · 새음성 · 붙임, 큐에 없는 단위에 뺌
  <py> $P/쉼넣기.py 만들기 <계획.json> <출력.mp4>                                          # 한 번 인코딩, 끝나면 스스로 검사
  <py> $P/쉼넣기.py 검사 <영상.mp4> <자막.srt>                                              # 길이 · 자막과 소리 · 붙은 말
  <py> $P/쉼넣기.py 시험                                                                   # 일부러 깨뜨린 입력의 자가시험
  바꾼 큐의 새 음성은 먼저 `$P/voice.py <큐.json> --음성 <그 도구의 음성 폴더> --큐 <id,…>`로 산다(견적 · 승인은 영상 V-4).

계획.json — 「초안」이 자막과 큐에서 만들고, 사람이 읽어 고친다. 경로는 계획 파일 기준 상대 경로도 된다.
  {"영상": …, "자막": …, "쉼": {"큐": 1.0, "결과": 1.5, "전환": 1.8},
   "문장쉼": 0.5,                                   # (선택) 바꾼 큐의 새 음성 안 문장 사이를 이 초 이상으로 벌린다
   "잘라낼": [[시작초, 끝초], …],                    # 옛 시각. 자막이 걸치면 멈춘다. 안에 통째로 든 단위는 함께 빠진다
   "글상자": [{"단위": id, "글": 한 줄}],            # 그 단위의 말이 나오는 동안 화면 아래에 글을 띄운다(화면에 없는 명령 등)
   "단위": [{"id": 큐 id, "구간": 이름, "자막": [첫 번호, 끝 번호](0부터), "글": 옛 글,
            "쉼뒤": "잇기" | "큐" | "결과" | "전환",   # 다음 단위와의 사이. 잇기 = 한 문맥이라 그대로 둔다
            "새글": …, "새음성": mp3, "붙임": "앞" | "뒤",   # 바꾼 큐만. 앞 = 새 말 끝을 옛 말 끝(조작)에 맞춤, 뒤 = 새 말 시작을 옛 말 시작에
            "뺌": true}]}                                  # 말만 뺀다(화면은 둔다)
  초안의 「쉼뒤」: 앞 단위의 구간(segment)이 바뀌면 전환, 앞 단위의 끝 문장이 조작(누르 · 클릭 · 선택 · 입력 …)이면 결과, 그 밖은 큐.
  한 큐 안 문장 사이가 0.3초 미만인 곳은 「읽을 곳」으로 찍는다 — 한 문맥이 아니면 「자막」 묶음을 나눠 단위를 둘로 만든다.

만들기가 하는 일
  1. 바꾼 큐 — 옛 말 자리(첫 자막 −0.05초 ~ 끝 자막 +0.15초, 이웃 말은 건드리지 않음)를 비우고, 새 음성을 옛 말 크기에 맞춰 놓는다.
     새 말이 길어 모자란 시간은 붙임 앞이면 앞 틈에서, 뒤면 뒤 틈에서 화면을 멈춰 만든다.
  2. 쉼 — 단위 사이(새 말 자리 기준)가 「쉼」의 값보다 짧으면 모자란 만큼 넣는다. 이미 긴 사이는 줄이지 않는다.
     넣는 자리는 두 말 사이에서 소리가 조용하고 화면 움직임이 가장 적은 프레임이다(같으면 늦은 쪽 = 조작 결과가 다 뜬 뒤).
     그 프레임을 되풀이하고 같은 길이의 무음을 넣는다.
  3. 자르기 — 프레임 단위로 화면과 소리를 함께 뺀다. 자막 · 장 시각도 옮긴다.
  4. 영상은 select + loop(+ drawtext) 필터로 한 번 인코딩한다(libx264 crf 18, 30 fps, 원본 소리 표본 빈도 · AAC 160k).
  5. 검사 — 소리와 화면 길이 ±0.1초, 프레임 수, 멈춘 자리마다 결과 프레임이 옛 프레임과 같은지(이음새에서 화면이 튀지 않음),
     자막 블록마다 그 안에 말이 있고 시작 0.25초 안에 말이 시작되는지, 블록 사이 0.3초 이상 틈에 말이 없는지, 단위 사이가 쉼 기준 이상인지.
  출력: <출력>.mp4 · <출력>.srt · <출력>_시각.json(옛 → 새 시각: 대본 · 가이드의 영상 시각은 Map.load(이 파일)로 옮긴다)
        · <출력>_이음새.jpg(자른 자리와 움직임 중 멈춘 자리의 앞 · 뒤 장면 — 눈으로 본다).
실패는 좌표를 대고 멈춘다: 겹치거나 거꾸로 가는 자막(번호 · 시각), 영상보다 긴 자막, 없는 음성 파일(단위 id · 경로), 자를 구간에 걸친 자막,
조용한 프레임이 없는 틈(두 단위 id · 시각), 비운 자리 밖에 남은 옛 말, 새 음성에서 문장 사이를 못 찾음, 결과 길이 · 프레임 어긋남.
"""
import json, math, os, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ffmpeg, chapters, write_chapters  # noqa: E402

FPS = 30
LOOP_SHIFT = 1   # 이 ffmpeg 판의 loop start=K는 K-1번 프레임을 되풀이한다 — 「시험」이 확인한다
ACT = re.compile(r'누르|누릅|눌러|클릭|선택|입력|적겠|적어|적을|적습|닫|열겠|열어|엽니다|열게|엔터|가져가|실행|붙여 ?넣|체크|복사|고릅|칠게|쳐 볼|칩니다')
CLASS = ('잇기', '큐', '결과', '전환')
FONTS = ('C:/Windows/Fonts/malgun.ttf', '/usr/share/fonts/malgun/malgun.ttf', '/usr/share/fonts/malgun/MALGUN.TTF')   # 이 PC · 클라우드(렌더환경_클라우드.sh가 넣는 자리)
SCENE = 8.0      # 프레임 차이(96×54 회색 평균 절대차)가 이 값 이상이면 장면 전환 — 04 실측: 창 전환 · 스크롤 · 설치 창 다음 단계는 8~210, 진행 막대 · 커서는 1 아래


class 실패(SystemExit):
    pass


def fail(msg):
    raise 실패(msg)


# ---------- 자막 ----------
def t2s(x):
    h, m, r = x.strip().split(':'); s, ms = r.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def s2t(v):
    v = int(round(max(v, 0) * 1000)); h, v = divmod(v, 3600000); m, v = divmod(v, 60000); s, ms = divmod(v, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def read_srt(p, dur=None):
    out = []
    for b in Path(p).read_text(encoding='utf-8-sig').strip().split('\n\n'):
        L = b.strip().split('\n')
        if len(L) < 3:
            continue
        try:
            a, z = map(t2s, L[1].split(' --> '))
        except Exception:
            fail(f'{p}: 자막 {len(out)}번(파일 번호 {L[0]})의 시각 줄을 읽을 수 없다: {L[1]!r}')
        out.append([a, z, ' '.join(L[2:]).strip()])
    for i, (a, z, _) in enumerate(out):
        if z <= a:
            fail(f'{p}: 자막 {i}번 {s2t(a)} → {s2t(z)} — 끝이 시작보다 빠르다')
        if i and a < out[i - 1][1] - 1e-6:
            fail(f'{p}: 자막 {i - 1}번({s2t(out[i - 1][0])}~{s2t(out[i - 1][1])})과 {i}번({s2t(a)}~)이 겹친다')
    if dur is not None and out and out[-1][1] > dur + 0.05:
        fail(f'{p}: 마지막 자막 {len(out) - 1}번이 {s2t(out[-1][1])}에 끝나는데 영상은 {dur:.3f}초다 — 이 영상의 자막이 아니다')
    return out


def write_srt(p, blocks):
    Path(p).write_text('\n\n'.join(f'{i + 1}\n{s2t(a)} --> {s2t(z)}\n{t}' for i, (a, z, t) in enumerate(blocks)) + '\n', encoding='utf-8')


def sentences(t):
    return [s for s in re.split(r'(?<=[.?!])\s+', t.strip()) if s]


# ---------- 매체 ----------
def probe(p):
    j = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,r_frame_rate,nb_frames,sample_rate',
                                            '-show_entries', 'format=duration', '-of', 'json', str(p)]).decode())
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    return v, a, float(j['format']['duration'])


def decode_audio(p, sr):
    return np.frombuffer(subprocess.check_output([ffmpeg(), '-v', 'error', '-i', str(p), '-map', '0:a:0', '-f', 's16le', '-ac', '1', '-ar', str(sr), '-']),
                         np.int16).astype(np.float32)


def db10(x, sr):
    """10 ms 칸마다 소리 크기(dB, int16 기준)."""
    F = sr // 100; n = len(x) // F
    r = np.sqrt((x[:n * F].reshape(n, F) ** 2).mean(1)) if n else np.zeros(0)
    return 20 * np.log10(r + 1e-3)


def speech_thr(d):
    loud = d[d > d.max() - 40]
    return float(np.median(loud)) - 25


def frames_gray(mp4):
    p = subprocess.Popen([ffmpeg(), '-v', 'error', '-i', str(mp4), '-map', '0:v:0', '-vf', 'scale=96:54,format=gray', '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE)
    n = 96 * 54
    while True:
        buf = p.stdout.read(n * 300)
        if not buf:
            break
        yield from np.frombuffer(buf, np.uint8).reshape(-1, n).astype(np.int16)
    p.wait()


def motion(mp4, cache):
    """프레임마다 앞 프레임과의 차이(96×54 회색 평균 절대차). 캐시는 크기 · 수정 시각이 같을 때만 쓴다."""
    st = Path(mp4).stat(); key = f'{st.st_size}-{int(st.st_mtime)}'
    kf = cache.with_suffix('.key')
    if cache.exists() and kf.exists() and kf.read_text() == key:
        return np.load(cache)
    d, prev = [], None
    for row in frames_gray(mp4):
        d.append(0.0 if prev is None else float(np.abs(row - prev).mean())); prev = row
    a = np.array(d, np.float32); np.save(cache, a); kf.write_text(key)
    return a


def thumbs(mp4, idx):
    want, out = set(int(i) for i in idx), {}
    for k, row in enumerate(frames_gray(mp4)):
        if k in want:
            out[k] = row
        if len(out) == len(want):
            break
    return out


# ---------- 초안 ----------
def draft(mp4, srt, plan, cue_files):
    if Path(plan).exists():
        fail(f'{plan}: 이미 있다 — 초안은 덮어쓰지 않는다(사람이 고친 판을 지키려고)')
    _, _, dur = probe(mp4)
    B = read_srt(srt, dur)
    norm = lambda s: re.sub(r'\s', '', s)
    units = []
    if cue_files:
        cues = []
        for f in cue_files:
            j = json.loads(Path(f).read_text(encoding='utf-8')); cues += j['cues'] if isinstance(j, dict) else j
        i = 0
        for c in cues:
            want, acc, a = norm(c['text']), '', i
            while i < len(B) and len(acc) < len(want):
                acc += norm(B[i][2]); i += 1
            if acc != want:
                fail(f'큐 {c["id"]}: 자막 {a}번({s2t(B[a][0]) if a < len(B) else "끝"})부터의 글이 큐 글과 다르다 — {want[:30]!r} ↔ {acc[:30]!r}')
            units.append({'id': c['id'], '구간': str(c.get('segment') or c.get('scene') or ''), '자막': [a, i - 1], '글': c['text']})
        if i != len(B):
            fail(f'자막 {i}번({s2t(B[i][0])})부터 {len(B) - i}개가 어느 큐에도 들지 않는다')
    else:
        units = [{'id': f'b{k}', '구간': '', '자막': [k, k], '글': b[2]} for k, b in enumerate(B)]
    read = []
    for k, u in enumerate(units):
        a, z = u['자막']
        read += [f'{u["id"]} 자막 {j}→{j + 1} {s2t(B[j][1])} 틈 {B[j + 1][0] - B[j][1]:.2f}초' for j in range(a, z) if B[j + 1][0] - B[j][1] < 0.3]
        nx = units[k + 1] if k + 1 < len(units) else None
        last = sentences(u['글'])[-1] if u['글'] else ''
        u['쉼뒤'] = '전환' if nx and u['구간'] and nx['구간'] and u['구간'] != nx['구간'] else ('결과' if ACT.search(last) else '큐')
    Path(plan).write_text(json.dumps({'영상': str(Path(mp4).resolve()), '자막': str(Path(srt).resolve()), '쉼': {'큐': 1.0, '결과': 1.5, '전환': 1.8},
                                      '잘라낼': [], '글상자': [], '단위': units}, ensure_ascii=False, indent=1), encoding='utf-8')
    cnt = {c: sum(u['쉼뒤'] == c for u in units[:-1]) for c in CLASS}
    print(json.dumps({'계획': str(plan), '자막': len(B), '단위': len(units), '쉼뒤': cnt, '읽을 곳(한 큐 안 0.3초 미만)': read}, ensure_ascii=False, indent=1))


# ---------- 만들기 ----------
class Map:
    """옛 시각 → 새 시각. 자른 프레임 [fa, fb)와 넣은 멈춤(프레임 k 뒤에 n장)."""

    def __init__(self, cuts, ins):
        self.cuts = sorted(map(tuple, cuts)); self.ins = sorted(map(tuple, ins))

    def __call__(self, x):
        f = x * FPS; d = 0.0
        for fa, fb in self.cuts:
            if f >= fb:
                d -= fb - fa
            elif f > fa:
                d -= f - fa
        for k, n in self.ins:
            if f >= k + 1:
                d += n
        return x + d / FPS

    def dump(self):
        return {'fps': FPS, '잘라낸 프레임': self.cuts, '멈춤(프레임 뒤에 장수)': self.ins}

    @classmethod
    def load(cls, f):
        j = json.loads(Path(f).read_text(encoding='utf-8'))
        return cls(j['잘라낸 프레임'], j['멈춤(프레임 뒤에 장수)'])


def load_plan(pf):
    pf = Path(pf); P = json.loads(pf.read_text(encoding='utf-8'))
    rel = lambda s: Path(s) if Path(s).is_absolute() else (pf.parent / s).resolve()
    P['영상'], P['자막'] = rel(P['영상']), rel(P['자막'])
    for u in P['단위']:
        if u.get('새음성'):
            u['새음성'] = rel(u['새음성'])
    return P


def voice_info(path, sr, uid):
    """새 음성: 소리, 말 시작 · 끝(파일 안 초), 0.12초 이상 무음 칸들."""
    if not Path(path).is_file():
        fail(f'단위 {uid}: 새 음성 파일이 없다 — {path}')
    x = decode_audio(path, sr); d = db10(x, sr)
    if not len(d) or d.max() < 30:
        fail(f'단위 {uid}: 새 음성 {path}에 소리가 없다')
    thr = speech_thr(d) - 5
    act = np.where(d > thr)[0]; on, off = act[0] / 100, (act[-1] + 1) / 100
    sil, runs, k = d <= thr, [], act[0]
    while k <= act[-1]:
        if sil[k]:
            j = k
            while j <= act[-1] and sil[j]:
                j += 1
            if j - k >= 12:
                runs.append((k / 100, j / 100))
            k = j
        else:
            k += 1
    merged = []                            # 0.12초보다 짧은 소리로 갈라진 무음은 하나로 본다(숨소리 · 입소리)
    for a, b in runs:
        if merged and a - merged[-1][1] < 0.12:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return x, on, off, merged


def limit(x, sr):
    """옛 말 크기에 맞춰 키운 새 음성의 순간 최고점만 −1.5 dBFS 아래로 누른다(ffmpeg alimiter). 합본(join.py)이 맞춘 −16 LUFS 판은
    말 크기를 맞추면 원본 TTS의 최고점이 넘친다 — 이득을 낮추면 새 말만 작게 들린다."""
    if np.abs(x).max() < 27500:
        return x
    raw = np.clip(x / 2, -32768, 32767).astype(np.int16).tobytes()     # 넘치는 값을 잃지 않게 반으로 넣고 limit을 반으로 준다
    o = subprocess.run([ffmpeg(), '-v', 'error', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af',
                        'alimiter=limit=0.42:level=false:latency=1:attack=1:release=20', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-'],
                       input=raw, capture_output=True, check=True).stdout
    y = np.frombuffer(o, np.int16).astype(np.float32) * 2
    return np.concatenate([y, np.zeros(max(0, len(x) - len(y)), np.float32)])[:len(x)]


def widen(x, sr, spans, least):
    """한 큐 안 문장 사이가 least초보다 짧으면 그 사이 가운데에 무음을 넣어 least초로 벌린다(계획의 「문장쉼」, 없으면 0 = 그대로)."""
    if not least or len(spans) < 2:
        return x, spans[-1][1], spans
    out, prev, add, new = [], 0, 0.0, []
    for i, (a, b) in enumerate(spans):
        new.append((a + add, b + add))
        if i + 1 < len(spans):
            gap = spans[i + 1][0] - b
            if gap < least:
                cut = int(round((b + gap / 2) * sr))
                out += [x[prev:cut], np.zeros(int(round((least - gap) * sr)), np.float32)]; prev = cut; add += least - gap
    out.append(x[prev:])
    return np.concatenate(out), new[-1][1], new


def split_times(on, off, runs, sents, uid, path):
    """문장마다 (시작, 끝) — 글자 수 비례 자리 근처(말 길이의 ±25%)에서 가장 긴 무음 칸을 순서대로 고른다(없으면 가장 가까운 칸)."""
    if len(sents) == 1:
        return [(on, off)]
    if len(runs) < len(sents) - 1:
        fail(f'단위 {uid}: 새 음성 {path}에서 문장 사이 무음(0.12초 이상)이 {len(runs)}곳뿐인데 문장은 {len(sents)}개다')
    L = [len(re.sub(r'\s', '', s)) for s in sents]; tot = sum(L); acc = 0; used = -1; cuts = []
    for j in range(len(sents) - 1):
        acc += L[j]; want = on + (off - on) * acc / tot
        ok_i = [i for i in range(len(runs)) if i > used and len(runs) - i >= len(sents) - 1 - j]
        near = [i for i in ok_i if abs(sum(runs[i]) / 2 - want) <= 0.25 * (off - on)]   # 숫자 · 영어는 글자 수보다 길게 읽혀 비례 자리가 빗나간다
        i = max(near, key=lambda i: runs[i][1] - runs[i][0]) if near else min(ok_i, key=lambda i: abs(sum(runs[i]) / 2 - want))
        used = i; cuts.append(runs[i])
    return list(zip([on] + [b for a, b in cuts], [a for a, b in cuts] + [off]))


def build(pf, out):
    P = load_plan(pf); out = Path(out)
    if out.exists():
        fail(f'{out}: 이미 있다 — 출력은 매번 새 이름으로 만든다')
    v, a, dur = probe(P['영상'])
    if not v or not a:
        fail(f'{P["영상"]}: 화면이나 소리 스트림이 없다')
    if v['r_frame_rate'] != '30/1':
        fail(f'{P["영상"]}: {v["r_frame_rate"]} fps — 30 fps 영상만 다룬다')
    NF = int(v['nb_frames']); SR = int(a['sample_rate']); spf = SR // FPS
    B = read_srt(P['자막'], NF / FPS)
    req = {'잇기': 0.0, **P['쉼']}
    U, seen = P['단위'], 0
    for u in U:
        a0, z0 = u['자막']
        if a0 != seen or z0 < a0:
            fail(f'단위 {u["id"]}: 자막 묶음 {u["자막"]} — {seen}번부터 빈틈없이 차례로 묶어야 한다')
        seen = z0 + 1
        if u.get('쉼뒤', '큐') not in CLASS:
            fail(f'단위 {u["id"]}: 쉼뒤 {u.get("쉼뒤")!r}는 {CLASS} 가운데 하나여야 한다')
        if u.get('새음성') and u.get('붙임') not in ('앞', '뒤'):
            fail(f'단위 {u["id"]}: 새음성이 있으면 붙임을 앞 · 뒤로 정한다')
        if u.get('새음성') and u.get('뺌'):
            fail(f'단위 {u["id"]}: 새음성과 뺌을 함께 줄 수 없다')
        u['s'], u['e'] = B[a0][0], B[z0][1]
    if seen != len(B):
        fail(f'단위가 자막 {seen}번부터 {len(B) - seen}개를 덮지 않는다')
    x = decode_audio(P['영상'], SR)
    x = np.concatenate([x, np.zeros(max(0, NF * spf - len(x)), np.float32)])[:NF * spf]
    d0 = db10(x, SR); thr = speech_thr(d0)
    # 자르기
    cuts = []
    for c0, c1 in P.get('잘라낼', []):
        fa, fb = round(c0 * FPS), round(c1 * FPS)
        if not 0 <= fa < fb <= NF:
            fail(f'잘라낼 {c0}-{c1}초가 영상(0-{NF / FPS:.2f}초) 밖이다')
        for i, (s, e, _) in enumerate(B):
            if s < fb / FPS and e > fa / FPS and not (s >= fa / FPS and e <= fb / FPS):
                fail(f'잘라낼 {c0}-{c1}초에 자막 {i}번({s2t(s)}~{s2t(e)})이 걸친다 — 말을 자르게 된다')
        for t in (fa / FPS, fb / FPS):
            if 0 < t < NF / FPS and d0[max(0, int(t * 100) - 2):int(t * 100) + 3].max() >= thr:
                fail(f'잘라낼 {c0}-{c1}초: 자르는 자리 {t:.2f}초에 말소리가 있다')
        cuts.append((fa, fb))
    keep = [u for u in U if not any(u['s'] >= fa / FPS and u['e'] <= fb / FPS for fa, fb in cuts)]
    ids = {u['id'] for u in keep}
    for g in P.get('글상자', []):
        if g['단위'] not in ids:
            fail(f'글상자: 단위 {g["단위"]}가 남는 단위에 없다')
    # 바꾼 · 뺀 단위의 옛 말 비우기
    y = x.copy(); ramp = int(0.01 * SR)

    def mute(a0, z0):
        i0, i1 = max(0, int(a0 * SR)), min(len(y), int(z0 * SR))
        y[i0:i1] = 0
        if i0 - ramp > 0: y[i0 - ramp:i0] *= np.linspace(1, 0, ramp)
        if i1 + ramp < len(y): y[i1:i1 + ramp] *= np.linspace(0, 1, ramp)

    for k, u in enumerate(keep):
        if not (u.get('새음성') or u.get('뺌')):
            continue
        lo = max(u['s'] - 0.05, (keep[k - 1]['e'] + 0.02) if k else 0)
        hi = min(u['e'] + 0.15, (keep[k + 1]['s'] - 0.05) if k + 1 < len(keep) else NF / FPS)
        for t0, t1 in ((lo - 0.3, lo), (hi, hi + 0.3)):
            seg = d0[max(0, int(t0 * 100)):max(0, int(t1 * 100))]
            owner = [w for w in keep if w is not u and w['s'] - 0.1 < t1 and w['e'] + 0.1 > t0]
            if len(seg) and (seg > thr).sum() >= 12 and not owner:
                fail(f'단위 {u["id"]}: 비운 자리({lo:.2f}~{hi:.2f}초) 밖 {t0:.2f}~{t1:.2f}초에 옛 말이 남는다 — 자막 시각을 확인한다')
        od = d0[int(u['s'] * 100):int(u['e'] * 100)]
        u['old_db'] = float(np.median(od[od > thr])) if (od > thr).any() else None
        mute(lo, hi)
    d = db10(y, SR)
    quiet = lambda t, w=0.02: d[max(0, int((t - w) * 100)):int((t + w) * 100) + 1].max(initial=-60) < thr
    # 새 음성
    for u in keep:
        if u.get('새음성'):
            vx, on, off, runs = voice_info(u['새음성'], SR, u['id'])
            ss = sentences(u['새글']); vd = db10(vx, SR)
            g = 10 ** ((u['old_db'] - float(np.median(vd[vd > vd.max() - 30]))) / 20) if u['old_db'] is not None else 1.0
            spans = split_times(on, off, runs, ss, u['id'], u['새음성'])
            vx, off, spans = widen(vx, SR, spans, P.get('문장쉼', 0.0))
            u.update(vx=limit(vx * g, SR), on=on, off=off, ss=ss, gain=g, spans=spans)
    # 틈과 멈출 프레임
    mot = motion(P['영상'], Path(pf).with_name(Path(P['영상']).stem + '_움직임.npy'))
    if len(mot) != NF:
        fail(f'움직임 표 프레임 {len(mot)} ≠ 영상 {NF}')
    cutf = set()
    for fa, fb in cuts:
        cutf.update(range(fa, fb))

    def pick(lo, hi, who):
        best = None
        for k in range(max(1, math.ceil(lo * FPS) - 1), min(NF - 2, int(hi * FPS)) + 1):
            t = (k + 1) / FPS
            if not lo - 1e-9 <= t <= hi + 1e-9 or k in cutf or (k + 1) in cutf or not quiet(t):
                continue
            sc = float(mot[k] + mot[k + 1])
            if best is None or sc <= best[0] + 0.02:
                best = (min(sc, best[0]) if best else sc, k, sc)
        if best is None:
            fail(f'{who}: {lo:.2f}~{hi:.2f}초에 소리가 조용한 프레임이 없다 — 쉼을 넣을 자리가 없다')
        return best[1], best[2]

    def window(lo, hi):
        for fa, fb in cuts:
            if fa / FPS <= lo < fb / FPS:
                lo = fb / FPS
        return lo, hi

    def change_after(t):
        """t 뒤 첫 장면 전환(프레임 차이 SCENE 이상)의 시각. 없으면 영상 끝."""
        f = np.where(mot[int(math.ceil(t * FPS)):] >= SCENE)[0]
        return (int(math.ceil(t * FPS)) + int(f[0])) / FPS if len(f) else NF / FPS

    def change_before(t):
        """t 앞 마지막 장면 전환의 시각(그 프레임부터 새 장면). 없으면 0."""
        f = np.where(mot[:int(t * FPS) + 1] >= SCENE)[0]
        return int(f[-1]) / FPS if len(f) else 0.0

    gaps = []
    for k, u in enumerate(keep):          # 단위 k 앞의 틈
        lo, hi = window(keep[k - 1]['e'] + 0.08 if k else 0.0, u['s'] - 0.05)
        if hi - lo < 0.04:
            lo, hi = window((keep[k - 1]['e'] - 0.03) if k else 0.0, u['s'] + 0.01)
        gaps.append({'lo': lo, 'hi': hi, 'n': 0})
    gaps.append({'lo': keep[-1]['e'] + 0.08, 'hi': NF / FPS - 0.05, 'n': 0})
    # 바꾼 말이 길면 먼저 같은 장면의 말 없는 화면으로 흘려보낸다 — 장면 전환은 넘지 않는다(말과 화면의 차례를 지킨다).
    # 붙임 뒤: 옛 말 시작부터 다음 장면 전환(또는 다음 말) 전까지, 붙임 앞: 앞 장면 전환(또는 앞 말) 뒤부터 옛 말 끝(조작)까지.
    # 모자란 만큼만 그 장면 안의 가장 가만한 프레임에서 멈춘다.
    for k, u in enumerate(keep):
        if not u.get('새음성'):
            continue
        if u['붙임'] == '뒤':
            u['edge'] = min(change_after(u['e']), keep[k + 1]['s'] if k + 1 < len(keep) else NF / FPS)
            g = gaps[k + 1]; g['hi'] = max(g['lo'] + 0.04, min(g['hi'], u['edge'] - 1 / FPS))
        else:
            u['edge'] = max(change_before(u['s']), keep[k - 1]['e'] if k else 0.0)
            g = gaps[k]; g['lo'] = min(g['hi'] - 0.04, max(g['lo'], u['edge']))
    need = set(range(1, len(keep))) | {k for k, u in enumerate(keep) if u.get('새음성') and u['붙임'] == '앞'}         | {k + 1 for k, u in enumerate(keep) if u.get('새음성') and u['붙임'] == '뒤'}
    for k in sorted(need):
        g = gaps[k]; g['who'] = f'{keep[k - 1]["id"] if k else "처음"} ~ {keep[k]["id"] if k < len(keep) else "끝"}'
        g['k'], g['mot'] = pick(g['lo'], g['hi'], g['who']); g['p'] = (g['k'] + 1) / FPS
    mc = Map(cuts, [])                     # 자르기만 넣은 시각
    for k, u in enumerate(keep):
        if u.get('새음성'):
            L = u['off'] - u['on']
            if u['붙임'] == '앞':          # 새 말 시작이 앞 장면 전환(또는 앞 말 끝)보다 앞서지 않게
                g = gaps[k]; g['n'] += max(0, math.ceil((L - (mc(u['e']) - mc(min(u['edge'], g['p'])))) * FPS))
            else:                          # 새 말 끝이 다음 장면 전환(또는 다음 말 시작)을 넘지 않게
                g = gaps[k + 1]; g['n'] += max(0, math.ceil((L - (mc(max(u['edge'], g['p'])) - mc(u['s']))) * FPS))

    def O(k):
        """단위 k 안의 새 시각 = 자르기만 넣은 시각 + 틈 0~k에 넣은 멈춤. 시각이 아니라 틈의 차례로 센다 — 말이 맞닿은 틈에서는
        멈출 프레임이 앞 말 끝보다 조금 앞에 놓일 수 있는데, 시각으로 세면 그 멈춤이 앞 말(붙임 앞)까지 밀어 틈이 벌어지지 않는다."""
        return sum(g['n'] for g in gaps[:k + 1]) / FPS

    def span(k):
        u = keep[k]
        if not u.get('새음성'):
            return mc(u['s']) + O(k), mc(u['e']) + O(k)
        if u['붙임'] == '앞':
            e = mc(u['e']) + O(k); return e - (u['off'] - u['on']), e
        s = mc(u['s']) + O(k); return s, s + (u['off'] - u['on'])

    for k in range(1, len(keep)):
        if keep[k - 1].get('뺌') or keep[k].get('뺌'):
            continue
        c = keep[k - 1].get('쉼뒤', '큐')
        have = span(k)[0] - span(k - 1)[1]
        if have < req[c] - 1e-6:
            gaps[k]['n'] += math.ceil((req[c] - have) * FPS - 1e-6)
    m = Map(cuts, [(g['k'], g['n']) for g in gaps if g['n']])
    order = sorted([g for g in gaps if g['n']], key=lambda g: g['k'])
    # 소리 잇기
    aud, f0 = [], 0

    def keep_frames(s, e):
        segs = [(s, e)]
        for fa, fb in cuts:
            nx = []
            for p, q in segs:
                if fb <= p or fa >= q: nx.append((p, q))
                else:
                    if p < fa: nx.append((p, fa))
                    if fb < q: nx.append((fb, q))
            segs = nx
        return segs

    for g in order:
        aud += [y[p * spf:q * spf] for p, q in keep_frames(f0, g['k'] + 1)]
        aud.append(np.zeros(g['n'] * spf, np.float32)); f0 = g['k'] + 1
    aud += [y[p * spf:q * spf] for p, q in keep_frames(f0, NF)]
    Y = np.concatenate(aud)
    NFo = NF - sum(fb - fa for fa, fb in cuts) + sum(g['n'] for g in order)
    if len(Y) != NFo * spf:
        fail(f'내부 오류: 소리 표본 {len(Y)} ≠ 프레임 {NFo} × {spf}')
    # 새 음성 얹기 · 자막
    blocks, boxes = [], []
    for k, u in enumerate(keep):
        a0, z0 = u['자막']
        if u.get('뺌'):
            continue
        if not u.get('새음성'):
            blocks += [[mc(B[j][0]) + O(k), mc(B[j][1]) + O(k), B[j][2]] for j in range(a0, z0 + 1)]
        else:
            s, e = span(k); T = s - u['on']; i0 = int(round(T * SR))
            if i0 < 0:
                fail(f'단위 {u["id"]}: 새 음성이 영상 처음보다 앞에 놓인다({T:.2f}초)')
            seg = u['vx'][:max(0, len(Y) - i0)]; Y[i0:i0 + len(seg)] += seg
            blocks += [[T + p, T + q, t] for (p, q), t in zip(u['spans'], u['ss'])]   # 새 말은 옛 블록 수와 상관없이 문장마다 한 블록(긴 새 글이 한 블록에 몰리지 않게)
        for gx in P.get('글상자', []):
            if gx['단위'] == u['id']:
                s, e = span(k); boxes.append((s, e + 1.0, gx['글']))
    if np.abs(Y).max() >= 32767:
        fail(f'새 음성을 얹은 소리가 넘친다(최고 {np.abs(Y).max():.0f}) — 이득 {[round(u.get("gain", 1), 2) for u in keep if u.get("새음성")]}')
    # 화면
    tmp = Path(tempfile.mkdtemp(prefix='쉼넣기_', dir=out.parent))
    fc = []
    if cuts:
        fc.append("select='not(" + '+'.join(f'between(n\\,{fa}\\,{fb - 1})' for fa, fb in cuts) + ")'")
    fc.append(f'setpts=N/{FPS}/TB')
    removed = lambda k: sum(min(fb, k + 1) - fa for fa, fb in cuts if fa <= k)
    for g in sorted(order, key=lambda g: -g['k']):
        fc.append(f'loop=loop={g["n"]}:size=1:start={g["k"] - removed(g["k"]) + LOOP_SHIFT}')
    fc.append(f'setpts=N/{FPS}/TB')
    font = next((f for f in FONTS if Path(f).is_file()), None)
    if boxes and not font:
        fail(f'글상자에 쓸 맑은 고딕이 없다 — {" · ".join(FONTS)} 중 하나에 둔다(클라우드는 CLAUDE.md 7절 「덱 렌더」의 글꼴 설치)')
    for i, (s, e, t) in enumerate(boxes):
        (tmp / f'box{i}.txt').write_text(t, encoding='utf-8')
        esc = lambda p: str(p).replace('\\', '/').replace(':', '\\:')
        fc.append(f"drawtext=fontfile='{esc(font)}':textfile='{esc(tmp / f'box{i}.txt')}':fontsize=h/30:fontcolor=white:box=1:boxcolor=black@0.75:"
                  f"boxborderw=18:x=(w-text_w)/2:y=h-text_h-h/12:enable='between(t\\,{s:.3f}\\,{e:.3f})'")
    (tmp / 'fc.txt').write_text('[0:v]' + ','.join(fc) + '[v]', encoding='utf-8')
    wav = tmp / 'a.wav'
    subprocess.run([ffmpeg(), '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', str(wav)],
                   input=np.clip(Y, -32768, 32767).astype(np.int16).tobytes(), check=True)
    chs = [(m(s), m(e), t) for s, e, t in chapters(P['영상'])]
    meta = tmp / '장.txt'; write_chapters(meta, [c for c in chs if c[1] > c[0]])
    subprocess.run([ffmpeg(), '-v', 'error', '-y', '-i', str(P['영상']), '-i', str(wav), '-i', str(meta), '-/filter_complex', str(tmp / 'fc.txt'),
                    '-map', '[v]', '-map', '1:a', '-map_chapters', '2', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-r', str(FPS), '-c:a', 'aac', '-b:a', '160k', '-ar', str(SR), '-ac', '1', '-movflags', '+faststart', str(out)], check=True)
    write_srt(out.with_suffix('.srt'), blocks)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    rec = {'계획': str(Path(pf).resolve()), '원본': str(P['영상']), '원본 프레임': NF, '출력 프레임': NFo, **m.dump(),
           '멈춤': [{'자리': g['who'], '옛 시각': round(g['p'], 3), '초': round(g['n'] / FPS, 3), '움직임': round(g['mot'], 2)} for g in order],
           '바꾼 단위': [{'id': u['id'], '붙임': u['붙임'], '새 말 초': round(u['off'] - u['on'], 2), '옛 말 초': round(u['e'] - u['s'], 2),
                      '이득': round(u['gain'], 2)} for u in keep if u.get('새음성')],
           '뺀 단위': [u['id'] for u in U if u not in keep or u.get('뺌')], '글상자': [[round(s, 2), round(e, 2), t] for s, e, t in boxes]}
    Path(str(out.with_suffix('')) + '_시각.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    res = check(out, out.with_suffix('.srt'), plan=P, keep=keep, rec=rec, m=m, quiet_out=True)
    sheet(out, cuts, order, m)
    print(json.dumps({'출력': str(out), '길이': round(NFo / FPS, 2), '원본 길이': round(NF / FPS, 2), '늘어난 초': round((NFo - NF) / FPS, 2),
                      '멈춤 수': len(order), '바꾼 단위': len(rec['바꾼 단위']), '뺀 단위': len(rec['뺀 단위']), '검사': res}, ensure_ascii=False, indent=1))


def fill(pf, pairs):
    """계획의 단위마다 지금 큐 글을 옛 글(「글」)과 견주어 새글 · 새음성 · 붙임 · 뺌을 다시 채운다(사람이 고친 붙임도 덮는다)."""
    pf = Path(pf); P = json.loads(pf.read_text(encoding='utf-8'))
    now = {}
    for pair in pairs:
        qf, _, vd = pair.partition('=')
        if not vd:
            fail(f'{pair}: <큐.json>=<음성 폴더> 꼴로 준다')
        for c in json.loads(Path(qf).read_text(encoding='utf-8'))['cues']:
            if c['id'] in now:
                fail(f'큐 {c["id"]}가 {now[c["id"]][2]}와 {qf}에 함께 있다')
            now[c['id']] = (c['text'], Path(vd), qf)
    B = read_srt((pf.parent / P['자막']) if not Path(P['자막']).is_absolute() else P['자막'])
    cut = lambda u: any(c0 <= B[u['자막'][0]][0] and B[u['자막'][1]][1] <= c1 for c0, c1 in P.get('잘라낼', []))
    n = d = 0
    for u in P['단위']:
        for k in ('새글', '새음성', '붙임', '뺌'):
            u.pop(k, None)
        if cut(u):
            continue
        if u['id'] not in now:
            u['뺌'] = True; d += 1; continue
        t, vd, _ = now[u['id']]
        if t != u['글']:
            mp3 = vd / f'{u["id"]}.mp3'
            if not mp3.is_file():
                fail(f'단위 {u["id"]}: 글이 바뀌었는데 새 음성 {mp3}가 없다 — voice.py로 먼저 산다')
            got = json.loads(mp3.with_suffix('.json').read_text(encoding='utf-8')).get('text')
            if got != t:
                fail(f'단위 {u["id"]}: {mp3.with_suffix(".json")}의 글이 큐 글과 다르다 — 옛 음성이다, voice.py로 다시 산다')
            u['새글'] = t; u['새음성'] = os.path.relpath(mp3.resolve(), pf.parent.resolve()).replace(os.sep, '/')
            u['붙임'] = '앞' if ACT.search(sentences(t)[-1]) else '뒤'; n += 1
    pf.write_text(json.dumps(P, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'바꿈 {n} · 뺌 {d} {[u["id"] for u in P["단위"] if u.get("뺌")]} · 붙임 앞 {sum(u.get("붙임") == "앞" for u in P["단위"])} — {pf}')


def sheet(out, cuts, order, m):
    """자른 자리와 움직임 중에 멈춘 자리(움직임 1 이상)의 앞 · 뒤 장면을 한 장에."""
    from PIL import Image, ImageDraw
    pts = [('자름', m(fa / FPS)) for fa, fb in cuts] + [(f'멈춤 {g["who"]} 움직임 {g["mot"]:.1f}', m(g['p'])) for g in order if g['mot'] >= 1.0]
    if not pts:
        return
    end = probe(out)[2] - 0.1                # 영상 끝에 놓인 자른 자리에서 끝을 넘어 뽑지 않게
    pts = pts[:40]; S = Image.new('RGB', (960, 180 * len(pts)), 'white'); dr = ImageDraw.Draw(S)
    for r, (lab, t) in enumerate(pts):
        for c, dt in enumerate((-0.2, 0.0, 0.2)):
            f = out.with_name(f'_s{r}{c}.png')
            subprocess.run([ffmpeg(), '-v', 'error', '-y', '-ss', f'{min(end, max(0, t + dt)):.3f}', '-i', str(out), '-frames:v', '1', '-vf', 'scale=320:180',
                            str(f)], check=True)
            S.paste(Image.open(f), (c * 320, r * 180)); f.unlink()
        dr.text((4, r * 180 + 4), f'{t:.2f}s {lab}', fill='red')
    S.save(str(out.with_suffix('')) + '_이음새.jpg', quality=85)


# ---------- 검사 ----------
def check(mp4, srt, plan=None, keep=None, rec=None, m=None, quiet_out=False):
    v, a, _ = probe(mp4)
    NF = int(v['nb_frames']); SR = int(a['sample_rate'])
    x = decode_audio(mp4, SR); va, aa = NF / FPS, len(x) / SR
    bad = []
    if abs(va - aa) > 0.1:
        bad.append(f'길이: 화면 {va:.3f}초 · 소리 {aa:.3f}초 — 0.1초 넘게 다르다')
    if rec and NF != rec['출력 프레임']:
        bad.append(f'프레임: 출력 {NF} ≠ 계획 {rec["출력 프레임"]}')
    B = read_srt(srt, va)
    d = db10(x, SR); thr = speech_thr(d)
    for i, (s, e, t) in enumerate(B):
        seg = d[int(s * 100):int(e * 100)]
        if not len(seg) or (seg > thr).mean() < 0.3:
            bad.append(f'자막 {i}번 {s2t(s)} {t[:20]!r}: 그 안에 말소리가 거의 없다')
        if (d[int(s * 100):int(s * 100) + 25] > thr).sum() == 0:
            bad.append(f'자막 {i}번 {s2t(s)}: 시작 0.25초 안에 말이 시작되지 않는다')
    for i in range(len(B) - 1):
        g0, g1 = B[i][1], B[i + 1][0]
        if g1 - g0 >= 0.3:
            mid = d[int((g0 + 0.1) * 100):int((g1 - 0.08) * 100)]
            if len(mid) and (mid > thr).sum() >= 15:      # 0.15초 넘게 이어지는 소리 = 말(클릭 소리는 짧다)
                bad.append(f'자막 {i}→{i + 1}번 사이 {s2t(g0)}~{s2t(g1)}: 말소리가 있다(자막이 소리와 어긋남)')
    if keep is not None:
        ends, pos = {}, 0
        for u in keep:
            if u.get('뺌'):
                continue
            nb = len(sentences(u['새글'])) if u.get('새음성') else u['자막'][1] - u['자막'][0] + 1
            ends[pos + nb - 1] = u.get('쉼뒤', '큐'); pos += nb
        for i in range(len(B) - 1):
            c = ends.get(i)
            if c and c != '잇기' and B[i + 1][0] - B[i][1] < plan['쉼'][c] - 0.035:
                bad.append(f'자막 {i}→{i + 1}번 {s2t(B[i][1])}: {B[i + 1][0] - B[i][1]:.2f}초 < {c} {plan["쉼"][c]}초')
    else:
        bad += [f'자막 {i}→{i + 1}번 {s2t(B[i][1])}: {B[i + 1][0] - B[i][1]:.2f}초 붙음' for i in range(len(B) - 1) if B[i + 1][0] - B[i][1] < 0.3]
    if rec and plan and rec['멈춤(프레임 뒤에 장수)']:
        want = {(k, n): round(m(k / FPS) * FPS) for k, n in rec['멈춤(프레임 뒤에 장수)']}
        old = thumbs(plan['영상'], [k for k, n in want] + [k + 1 for k, n in want])
        new = thumbs(mp4, [nk + j for (k, n), nk in want.items() for j in (0, n, n + 1)])
        for (k, n), nk in want.items():
            if nk not in new or nk + n + 1 not in new:
                bad.append(f'멈춤 옛 프레임 {k}: 결과 프레임 {nk}을 읽지 못했다'); continue
            e0, e1, e2 = (float(np.abs(new[nk] - old[k]).mean()), float(np.abs(new[nk + n] - old[k]).mean()),
                          float(np.abs(new[nk + n + 1] - old[k + 1]).mean()))
            if max(e0, e1, e2) > 3.0:
                bad.append(f'멈춤 옛 프레임 {k}({k / FPS:.2f}초) → 결과 {nk}~{nk + n}: 프레임이 맞지 않는다(차이 {e0:.1f} · {e1:.1f} · {e2:.1f})')
    out = {'화면 초': round(va, 3), '소리 초': round(aa, 3), '자막': len(B), '문제': len(bad), '문제 목록': bad[:30]}
    if bad:
        if not quiet_out:
            print(json.dumps(out, ensure_ascii=False, indent=1))
        fail(f'{mp4}: 검사 문제 {len(bad)}곳 — 첫 곳: {bad[0]}')
    return out


# ---------- 시험 ----------
def selftest():
    """작은 합성 영상으로 ① loop 필터의 프레임 의미 ② 정상 계획(쉼 · 바꿈 앞/뒤 · 자르기 · 글상자)의 결과 ③ 깨뜨린 입력의 실패 좌표를 본다."""
    import shutil
    ff = ffmpeg(); tmp = Path(tempfile.mkdtemp(prefix='쉼넣기시험_')); ok = []
    try:
        fr = np.stack([np.full((16, 16), i * 10, np.uint8) for i in range(12)])
        o = subprocess.run([ff, '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '16x16', '-r', '30', '-i', '-', '-vf',
                            f"select='not(between(n\\,2\\,3))',setpts=N/30/TB,loop=loop=2:size=1:start={4 + LOOP_SHIFT},setpts=N/30/TB",
                            '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], input=fr.tobytes(), capture_output=True, check=True).stdout
        got = (np.frombuffer(o, np.uint8).reshape(-1, 256)[:, 0] // 10).tolist()
        assert got == [0, 1, 4, 5, 6, 6, 6, 7, 8, 9, 10, 11], f'loop 의미가 바뀌었다: {got} — LOOP_SHIFT를 고친다'
        ok.append('loop 의미')
        SR, N = 44100, 30 * 20
        frames = np.zeros((N, 72, 128), np.uint8)
        for i in range(N):   # 짝수 초는 프레임마다 밝기가 바뀌고(움직임), 홀수 초는 멈춰 있다
            frames[i] = (i * 7) % 250 if (i // 30) % 2 == 0 else ((i // 30) * 30 * 7) % 250
        frames[285:] = 255 - frames[285:]   # 9.5초에 장면 전환(프레임 차이가 크게 튄다)
        talk = [(1.0, 2.5), (2.7, 4.0), (6.0, 7.2), (7.3, 9.0), (12.0, 13.5), (16.0, 18.0)]
        x = np.zeros(N * SR // 30, np.float32); tt = np.arange(len(x)) / SR
        for a0, b0 in talk:
            sl = (tt >= a0) & (tt < b0); x[sl] = 8000 * np.sin(2 * np.pi * 220 * tt[sl])
        vid, wav = tmp / 'v.mp4', tmp / 'v.wav'
        subprocess.run([ff, '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', str(wav)], input=x.astype(np.int16).tobytes(), check=True)
        subprocess.run([ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '128x72', '-r', '30', '-i', '-', '-i', str(wav),
                        '-c:v', 'libx264', '-crf', '10', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', str(vid)], input=frames.tobytes(), check=True)
        srt = tmp / 'v.srt'; write_srt(srt, [[a0, b0, f'문장 {i}.'] for i, (a0, b0) in enumerate(talk)])
        nv = tmp / 'n.wav'; y = np.zeros(int(3.0 * SR), np.float32); ty = np.arange(len(y)) / SR
        for a0, b0 in ((0.05, 1.3), (1.6, 2.95)):
            sl = (ty >= a0) & (ty < b0); y[sl] = 6000 * np.sin(2 * np.pi * 300 * ty[sl])
        subprocess.run([ff, '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', str(nv)], input=y.astype(np.int16).tobytes(), check=True)
        base = {'영상': str(vid), '자막': str(srt), '쉼': {'큐': 1.0, '결과': 1.5, '전환': 1.8}, '잘라낼': [[10.0, 11.5]],
                '글상자': [{'단위': 'D', '글': 'git clone --depth 1 https://example.com/x.git'}],
                '단위': [{'id': 'A', '자막': [0, 1], '글': '문장 0. 문장 1.', '쉼뒤': '큐'},
                         {'id': 'B', '자막': [2, 2], '글': '문장 2.', '쉼뒤': '결과', '새글': '새 첫째. 새 둘째.', '새음성': str(nv), '붙임': '앞'},
                         {'id': 'C', '자막': [3, 3], '글': '문장 3.', '쉼뒤': '전환', '새글': '새 하나. 새 둘.', '새음성': str(nv), '붙임': '뒤'},
                         {'id': 'D', '자막': [4, 4], '글': '문장 4.', '쉼뒤': '큐'},
                         {'id': 'E', '자막': [5, 5], '글': '문장 5.', '쉼뒤': '큐'}]}

        def run(name, plan, expect=None):
            pf = tmp / f'{name}.json'; pf.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
            try:
                build(pf, tmp / f'{name}.mp4')
            except 실패 as e:
                if expect and re.search(expect, str(e)):
                    ok.append(f'{name}: 멈춤 — {str(e)[:80]}'); return
                raise AssertionError(f'{name}: 뜻밖의 실패 {e}')
            if expect:
                raise AssertionError(f'{name}: 실패해야 하는데 통과했다')
            ok.append(f'{name}: 통과')
        run('정상', base)
        S = read_srt(tmp / '정상.srt'); r = json.loads((tmp / '정상_시각.json').read_text(encoding='utf-8'))
        # 바꾼 B · C는 옛 자막이 한 블록이어도 새 글의 문장마다 한 블록이다
        assert [t for _, _, t in S] == ['문장 0.', '문장 1.', '새 첫째.', '새 둘째.', '새 하나.', '새 둘.', '문장 4.', '문장 5.'], S
        gaps = [S[i + 1][0] - S[i][1] for i in range(len(S) - 1)]
        assert gaps[1] >= 0.999 and gaps[3] >= 1.499 and gaps[5] >= 1.799, gaps   # A→B 큐, B→C 결과, C→D 전환
        assert r['원본 프레임'] == N and r['잘라낸 프레임'] == [[300, 345]], r
        ok.append(f'정상 결과: 자막 8 · 쉼 {[round(g, 2) for g in gaps]} · 멈춤 {len(r["멈춤"])} · 글상자 {r["글상자"][0][:2]}')
        cm = Map.load(tmp / '정상_시각.json')
        assert S[5][1] <= cm(9.5) + 0.05, f'붙임 뒤 새 말이 장면 전환을 넘었다: 끝 {S[5][1]:.2f} > 전환 {cm(9.5):.2f}'
        ok.append(f'장면 전환 지킴: C 끝 {S[5][1]:.2f}초 ≤ 전환 {cm(9.5):.2f}초')
        # 맞닿은 말: B 자막 끝 = C 자막 시작(틈 0) — 멈출 프레임이 B 끝보다 앞에 놓여도 B(붙임 앞)와 C 사이가 벌어져야 한다
        s5 = tmp / '맞닿음.srt'; L = [[a0, b0, f'문장 {i}.'] for i, (a0, b0) in enumerate(talk)]; L[2][1] = 7.25; L[3][0] = 7.25; write_srt(s5, L)
        tight = json.loads(json.dumps(base)); tight['자막'] = str(s5); run('맞닿은 말', tight)
        S5 = read_srt(tmp / '맞닿은 말.srt')
        assert S5[4][0] - S5[3][1] >= 1.499, f'맞닿은 말: B→C {S5[4][0] - S5[3][1]:.2f}초'
        ok.append(f'맞닿은 말 결과: B→C {S5[4][0] - S5[3][1]:.2f}초')
        bad = json.loads(json.dumps(base)); bad['단위'][2]['새음성'] = str(tmp / '없음.wav'); run('없는 음성', bad, r'단위 C: 새 음성 파일이 없다')
        s2 = tmp / '겹침.srt'; L = [[a0, b0, f'문장 {i}.'] for i, (a0, b0) in enumerate(talk)]; L[3][0] = 7.0; write_srt(s2, L)
        bad = json.loads(json.dumps(base)); bad['자막'] = str(s2); run('겹치는 큐', bad, r'자막 2번.*3번.*겹친다')
        s3 = tmp / '긴.srt'; write_srt(s3, [[a0 + 5, b0 + 5, f'문장 {i}.'] for i, (a0, b0) in enumerate(talk)])
        bad = json.loads(json.dumps(base)); bad['자막'] = str(s3); run('길이 안 맞는 자막', bad, r'마지막 자막 5번이 00:00:23,000에 끝나는데 영상은 20')
        bad = json.loads(json.dumps(base)); bad['잘라낼'] = [[12.5, 14.0]]; run('말에 걸친 자르기', bad, r'자막 4번\(00:00:12,000')
        # 바꿈: 바뀐 큐(B, 끝 문장이 조작 → 앞) · 그대로인 큐 · 큐에 없는 단위(E → 뺌)를 채우고, 음성 기록 글이 옛 글이면 멈춘다
        vd = tmp / '음성'; vd.mkdir()
        shutil.copy(nv, vd / 'B.mp3'); (vd / 'B.json').write_text(json.dumps({'text': '새 글. 버튼을 누릅니다.'}, ensure_ascii=False), encoding='utf-8')
        cq = tmp / '큐.json'; cq.write_text(json.dumps({'cues': [{'id': i, 'text': t} for i, t in
                                                              (('A', '문장 0. 문장 1.'), ('B', '새 글. 버튼을 누릅니다.'), ('C', '문장 3.'), ('D', '문장 4.'))]},
                                                             ensure_ascii=False), encoding='utf-8')
        fp = tmp / '바꿈.json'
        fp.write_text(json.dumps({**base, '잘라낼': [], '단위': [{k: v for k, v in u.items() if k not in ('새글', '새음성', '붙임')} for u in base['단위']]},
                                 ensure_ascii=False), encoding='utf-8')
        fill(fp, [f'{cq}={vd}'])
        FU = {u['id']: u for u in json.loads(fp.read_text(encoding='utf-8'))['단위']}
        assert FU['B'].get('붙임') == '앞' and (fp.parent / FU['B']['새음성']).resolve() == (vd / 'B.mp3').resolve(), FU['B']
        assert not FU['A'].get('새글') and not FU['C'].get('새글') and FU['E'].get('뺌') is True, FU
        (vd / 'B.json').write_text(json.dumps({'text': '예전 글.'}, ensure_ascii=False), encoding='utf-8')
        try:
            fill(fp, [f'{cq}={vd}']); raise AssertionError('옛 음성을 못 잡았다')
        except 실패 as e:
            assert '옛 음성이다' in str(e), e
        ok.append('바꿈: B 앞 붙임 · E 뺌 · 옛 음성 멈춤')
        global FONTS
        keep_fonts, FONTS = FONTS, (str(tmp / '없는글꼴.ttf'),)
        try:
            run('글꼴 없음', json.loads(json.dumps(base)), r'글상자에 쓸 맑은 고딕이 없다')
        finally:
            FONTS = keep_fonts
        s4 = tmp / '밀린.srt'; write_srt(s4, [[a0 + 0.6, b0 + 0.6, t] for a0, b0, t in S])
        try:
            check(tmp / '정상.mp4', s4, quiet_out=True); raise AssertionError('밀린 자막을 못 잡았다')
        except 실패 as e:
            ok.append(f'밀린 자막: 멈춤 — {str(e)[:80]}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('\n'.join(ok)); print(f'시험 통과 {len(ok)}')


if __name__ == '__main__':
    a = sys.argv[1:]
    try:
        if a[:1] == ['초안'] and len(a) >= 4:
            draft(a[1], a[2], a[3], a[a.index('--큐') + 1:] if '--큐' in a else [])
        elif a[:1] == ['바꿈'] and len(a) >= 3:
            fill(a[1], a[2:])
        elif a[:1] == ['만들기'] and len(a) == 3:
            build(a[1], a[2])
        elif a[:1] == ['검사'] and len(a) == 3:
            print(json.dumps(check(a[1], a[2]), ensure_ascii=False, indent=1))
        elif a[:1] == ['시험']:
            selftest()
        else:
            sys.exit(__doc__)
    except 실패 as e:
        sys.exit(f'멈춤: {e}')
