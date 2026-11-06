"""강조까지 입힌 기존 이론 영상에서 바뀐 장만 새로 만들어 바꿔 끼운다. 바뀌지 않은 장의 화면은 다시 인코딩하지 않고, 음성은 사지 않는다.
언제: 한 편에서 몇 장의 낭독이나 화면만 바뀌었을 때, 그 장의 새 음성을 산 뒤(음성사기.py) — 전 장을 다시 굽지 않으려고 쓴다(영상.md 길 12).
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/장바꿔끼우기.py <기존 영상.mp4> <대본.md> <장 번호 …> --출력 <폴더> [--audio-ledger <기록.json>] [--강조 <강조.json>]

- 기존: 영상 옆 `_작업/영상_자막_기록/`의 같은 이름 자막 · 시간표. 강조 설정 기본값은 `제작도구/구성/<과정>/<NN>회차/강조_<영상 이름>.json`.
  음성 · 모델 · 쉼(--pause-*) · 장 넘김(--gap)은 기존 시간표 머리에서 읽는다. 장 번호는 바꿀 구획의 첫 장 번호다.
- 새 장: 강의영상.py의 prepare · encode_row로 장 조각(`조각_저장/합성/`)을, 강조표시.py의 plan · overlay로 그 장의 표시(`조각_저장/강조/`)를 만든다.
  대본의 모든 구획 음성이 음성_저장에 있어야 한다. 없으면 멈춘다 — 바꿀 장이면 먼저 사고, 아니면 그 장의 대본이 영상과 다르다는 뜻이니 그 장도 바꿀 목록에 넣는다.
- 화면: 바뀌지 않은 장은 기존 영상을 장 경계(장 조각 첫 프레임, IDR)에서 무손실로 잘라 쓴다. 기존 영상은 다음 장 그림이 장 경계 약 0.1초 앞에서 뜨므로
  (강조표시.py가 강조 전 영상을 무손실로 자를 때 다음 장 첫 프레임이 딸려 온다), 새 장은 그 넘김 프레임부터 덮는다. 넘김 프레임이 키프레임이 아니면
  앞 장의 마지막 키프레임부터 넘김 프레임 앞까지만 다시 인코딩한다.
- 소리: 기존 소리를 PCM으로 풀어 구획 소리의 시작(구획 첫 자막의 시각 — 장 경계 프레임과 ±20ms 다르다)에서 자르고, 바뀐 구획 자리에 새 소리를 넣어
  AAC 160k로 한 번 인코딩한다. 뒤 구획은 화면과 같은 프레임 수(1프레임 = 1470 표본)만큼 민다.
- 출력(기존 파일은 덮지 않는다): `<출력>/강조/<영상 이름>.mp4`, `<출력>/_작업/영상_자막_기록/<영상 이름>.srt · _시간표.md`(뒤 장 시각을 길이 차이만큼 민다) — 검사 뒤 `입고.py <출력>`으로 바꿔 끼운다.
  `<출력>/이음새/`에 새 이음새마다 앞뒤 0.2초 프레임을 저장한다.
- 검사(V-5 · V-12): 이음새 앞뒤 프레임 차이와 이음새 앞 0.2초의 소리 세기, 소리와 화면 길이, `자막대조.py`, `장넘김_싱크.py`, 바뀐 장 구간의 `말머리_잘림.py`.
- --audio-ledger: 바뀐 장의 음성을 산 기록(음성사기.py). 그 장의 시간표 크레딧 칸을 채운다. 기록에 없는 장(화면만 바뀐 장)은 기존 칸을 둔다.
"""
import argparse, bisect, hashlib, json, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.dont_write_bytecode = True
import 강의영상 as tool  # noqa: E402
import 강조표시 as emph  # noqa: E402

HERE = Path(__file__).resolve().parent
G = HERE.parents[3]   # workspace/강의제작
FPS, RATE = emph.FPS, 44100
SPF = RATE // FPS   # 프레임 하나의 표본 수(1470)
ROW = re.compile(r"^\| (\d+)(?:~(\d+))? \| (\d+):(\d+)(?: \(SLIDE (\d+)부터 (\d+):([\d.]+)\))? \| ([\d.]+) \|$")
CREDIT = re.compile(r"^\| (\d+)(?:~\d+)? \| (\d+) \|$")
WAIT = re.compile(r"^\| (\d+) \| (\d\d:\d\d:\d\d,\d{3}) \| (\d\d:\d\d:\d\d,\d{3}) \| (\d+)초 \|$")


def stop(msg): sys.exit(f"장바꿔끼우기: {msg}")


def ff(*c, out=False):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, c)], capture_output=True, check=False)
    if r.returncode: stop(f"ffmpeg 실패: {r.stderr.decode('utf-8', 'replace')[:300]}")
    return r.stdout if out else None


def probe(p, *q):
    return subprocess.run(["ffprobe", "-v", "error", *q, str(p)], capture_output=True, text=True, check=True).stdout


def packets(p):
    return int(probe(p, "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0").strip())


def pcm(src, n, ss=None):
    """src의 소리를 단채널 16비트 PCM으로 풀어 표본 n개에 맞춘다(모자라면 무음으로 채운다 — 장 끝은 장 넘김 쉼이라 무음이다)."""
    raw = ff(*(["-ss", f"{ss:.6f}"] if ss else []), "-i", src, *(["-t", f"{n / RATE:.6f}"] if ss is not None else []),
             "-vn", "-ac", 1, "-ar", RATE, "-f", "s16le", "-", out=True)
    return raw[:2 * n] + b"\0" * max(0, 2 * n - len(raw))


def gray(video, f, count):
    """프레임 f부터 count장을 작은 회색 그림(160×90 바이트열)으로."""
    raw = ff("-ss", at(f), "-i", video, "-frames:v", count, "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "gray", "-", out=True)
    n = 160 * 90
    return [raw[i * n:(i + 1) * n] for i in range(len(raw) // n)]


def at(f):
    """프레임 f를 첫 프레임으로 푸는 -ss 값. ffmpeg는 그 시각을 덮는 프레임부터 내므로 프레임 시작보다 조금 뒤를 준다(앞을 주면 한 프레임 앞부터 나온다)."""
    return f"{(f + 0.25) / FPS:.5f}"


def diff(x, y): return sum(abs(p - q) for p, q in zip(x, y)) / len(x)


def head_values(lines):
    """기존 시간표 머리에서 음성 · 모델 · 쉼 · 장 넘김 값을 읽어 강의영상.py 설정에 넣는다. 돌려준다: 머리에 적힌 크레딧."""
    a = tool.a
    m = re.match(r"^- 음성 (\S+) · 모델 (\S+) · (?:빠르기 설정 없음|속도 ([\d.]+))$", lines[2])
    p = re.search(r"짧게 \d+곳 ([\d.]+)초 · 한 호흡 \d+곳 ([\d.]+)초 · 크게 \d+곳 ([\d.]+)초 · 물음 뒤 최소 ([\d.]+)초 · 문단 사이 최소 ([\d.]+)초 · 장 넘김 ([\d.]+)초 \(기본값의 ([\d.]+)배\)", lines[4])
    c = re.search(r"이번에 쓴 크레딧 (\d+)", lines[3])
    if not (m and p and c and re.search(r"목표 0초$", lines[5])) or p[7] != "1.00":
        stop("기존 시간표 머리가 `강의영상.py --breath`(목표 없음)로 구운 꼴이 아니다 — 이 도구는 그 꼴만 다룬다")
    a.voice, a.model = m[1], m[2]
    if m[3]: a.speed = float(m[3])
    a.pause_short, a.pause_mid, a.pause_long, a.pause_question, a.pause_para, a.gap = map(float, p.groups()[:6])
    a.breath, a.natural, a.target, a.audio_ledger = True, False, 0.0, None
    tool.V4 = bool(re.match(r"eleven_v[34]", a.model))
    return int(c[1])


def main():
    t_start = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("script"); ap.add_argument("slides", nargs="+", type=int)
    ap.add_argument("--출력", dest="out", required=True); ap.add_argument("--강조", dest="config")
    ap.add_argument("--audio-ledger", dest="ledger")
    o = ap.parse_args()
    video = Path(o.video).resolve(); rec = video.parent.parent / "_작업" / "영상_자막_기록"
    srt_old, table_old = rec / f"{video.stem}.srt", rec / f"{video.stem}_시간표.md"
    out = Path(o.out).resolve()
    if out in (video.parent, video.parent.parent): stop("--출력이 기존 영상 자리다. 새 폴더를 주고, 검사 뒤 입고.py로 바꿔 끼운다")
    if not table_old.exists(): stop(f"{table_old}: 없음")
    lines = table_old.read_text(encoding="utf-8").splitlines()
    old_spent = head_values(lines)

    study_waits = {}
    S, pptx, name, probs = tool.check(o.script, study_waits)
    if probs: stop(f"대본 점검: {probs}")
    if name != video.stem: stop(f"대본이 만드는 영상 이름 {name}이 기존 영상 {video.stem}과 다르다")
    course, nn = re.fullmatch(r"(통합반|실전반)_(\d\d)회차_.+", name).groups()
    config = Path(o.config) if o.config else G / "제작도구" / "구성" / course / f"{nn}회차" / f"강조_{name}.json"
    for p in (srt_old, config):
        if not p.exists(): stop(f"{p}: 없음")
    firsts = [f for f, _, _ in S]
    if set(o.slides) - set(firsts): stop(f"대본 구획의 첫 장이 아닌 번호: {sorted(set(o.slides) - set(firsts))}")
    nocache = [f for f, _, t in S if not all((tool.CACHE / (tool.cache_key(t, tool.a.voice, tool.a.model, tool.a.speed) + x)).exists() for x in (".mp3", ".json"))]
    if nocache:
        stop(f"음성 캐시에 없는 구획 {nocache} — 바꿀 장이면 음성사기.py로 먼저 산다. 바꿀 장이 아니면 대본이 기존 영상과 다르니 그 장도 바꿀 목록에 넣는다. 이 도구는 음성을 사지 않는다")

    # 기존 영상의 장 경계: 강조표시.py와 같은 방법(시간표 시작 둘레의 마지막 키프레임)
    total = emph.duration("ffmpeg", video)
    parts = emph.pieces("ffprobe", video, emph.read_rows(table_old), total)
    if [p[0] for p in parts] != firsts: stop("기존 시간표의 구획과 대본의 구획이 다르다 — 구획이 바뀐 편은 강의영상.py로 다시 굽는다")
    n = len(parts)
    F = [round(b0 * FPS) for _, b0, _ in parts] + [packets(video)]
    keys = {round(float(x) * FPS) for x in re.findall(r"\d+\.\d+", probe(video, "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time", "-of", "csv=p=0"))}
    if not set(F[:-1]) <= keys: stop("장 경계가 키프레임이 아닌 곳이 있다 — 강조표시.py가 만든 영상인지 본다")
    swap = [f in o.slides for f in firsts]

    def turn(f):
        """기존 영상에서 장 경계 f 바로 앞의 넘김 프레임(다음 장 그림이 처음 뜬 프레임). 없으면 f."""
        fr = gray(video, f - 8, 8)
        hit = [f - 8 + j for j in range(2, len(fr)) if diff(fr[j - 1], fr[j]) > 1]
        return hit[0] if hit else f

    out.mkdir(parents=True, exist_ok=True)
    (out / "강조").mkdir(exist_ok=True)
    side = out / "_작업" / "영상_자막_기록"; side.mkdir(parents=True, exist_ok=True)
    seam_dir = out / "이음새"; seam_dir.mkdir(exist_ok=True)
    result = out / "강조" / f"{name}.mp4"
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        tmp = Path(tmp); tool.OUT = tmp
        # 1) 새 장 조각(강조 전) — 시간표 머리를 새로 쓰려고 모든 구획의 음성 · 쉼을 읽는다(캐시만 읽는다)
        rows, spent, speech, scale, fixed_wait = tool.prepare(S, name, study_waits)
        if spent: stop("음성을 샀다 — 이 도구는 사지 않는다")   # 위에서 캐시를 확인했으므로 오지 않는다
        imgs = tool.slide_images(pptx)
        # 기존 자막을 장 구획으로 나눈다. 구획의 소리는 장 경계 프레임이 아니라 강조 전 영상의 시계(장 조각 길이의 합)에서 시작하고,
        # 음성의 첫 글자는 늘 0초에 찍히므로(음성_저장 1432개 실측) 구획 첫 자막의 시작이 그 구획 소리의 시작이다.
        old_cues = []
        for b in re.split(r"\n\n+", srt_old.read_text(encoding="utf-8").strip()):
            l = b.split("\n"); s0, e0 = l[1].split(" --> ")
            old_cues.append((bisect.bisect_right([f / FPS - 0.1 for f in F[:-1]], emph.seconds(s0)) - 1, s0, e0, "\n".join(l[2:])))
        clock = [0.0] * n
        for k in range(1, n):
            mine = [emph.seconds(c[1]) for c in old_cues if c[0] == k]
            if not mine: stop(f"{firsts[k]}장의 기존 자막을 찾지 못했다")
            al = rows[k]["al"]; lead = next(s for c, s in zip(al["characters"], al["character_start_times_seconds"]) if c.strip())
            clock[k] = min(mine) + 0.0005 - lead   # 자막 시각은 ms 아래를 버린 값이다
        Gf, segs, newsubs, made_a = [0], {}, {}, 0
        for i in range(n):
            if swap[i]:
                rows[i]["start"] = clock[i] + (Gf[i] - F[i]) / FPS
                seg, new, subs = tool.encode_row(rows[i], imgs, rows[i]["start"], scale, name)
                made_a += new; segs[i] = seg; newsubs[i] = subs
                Gf.append(Gf[i] + round(tool.dur(seg) * FPS))
            else:
                Gf.append(Gf[i] + F[i + 1] - F[i])
        shift = [(Gf[i] - F[i]) / FPS for i in range(n)]

        # 2) 자막: 바뀌지 않은 장은 그대로 두고 뒤로 민다, 바뀐 장은 새로 만든 문장
        cues = []
        for i, s0, e0, t in old_cues:
            if swap[i]: continue
            if shift[i]: s0, e0 = tool.ts(emph.seconds(s0) + shift[i]), tool.ts(emph.seconds(e0) + shift[i])
            cues.append((i, s0, e0, t))
        for i, subs in newsubs.items():
            cues += [(i, tool.ts(s), tool.ts(e), t) for s, e, t in subs]
        cues.sort(key=lambda c: (c[0], emph.seconds(c[1])))
        (side / f"{name}.srt").write_text("\n".join(f"{k}\n{s} --> {e}\n{t}\n" for k, (_, s, e, t) in enumerate(cues, 1)), encoding="utf-8")

        # 3) 시간표: 머리는 새로 쓰고, 표는 바뀌지 않은 장의 줄을 그대로 두고 뒤로 민다
        old_rows, credit, waits = {}, {}, {}
        for line in lines:
            if m := ROW.match(line): old_rows[int(m[1])] = (line, m)
            elif m := CREDIT.match(line): credit[int(m[1])] = int(m[2])
            elif m := WAIT.match(line): waits.setdefault(int(m[1]), []).append((emph.seconds(m[2]), int(m[4])))
        if sorted(old_rows) != firsts: stop("기존 시간표 표의 장이 대본 구획과 다르다")
        led = json.loads(Path(o.ledger).read_text(encoding="utf-8")) if o.ledger else {"voice": tool.a.voice, "completed": {}}
        if led["voice"] != tool.a.voice: stop("음성 기록의 목소리가 기존 영상과 다르다")
        for i in range(n):
            if not swap[i]: continue
            r = rows[i]; item = led["completed"].get(r["mp3"].stem)
            if item and item["sha"] != hashlib.sha256(r["mp3"].read_bytes()).hexdigest(): stop("음성 기록과 현재 MP3 해시가 서로 다르다")
            if credit and item: credit[r["first"]] = int(item["credits"])   # 기록에 없으면 음성이 그대로인 장이라 기존 칸을 둔다
            waits[r["first"]] = [(r["start"] + s, w) for s, w in r["study_intervals"]]
        def rng(r): return f"{r['first']}{'~' + str(r['last']) if r['last'] != r['first'] else ''}"
        table = []
        for i, r in enumerate(rows):
            line, m = old_rows[r["first"]]
            if swap[i]:
                table.append(f"| {rng(r)} | {int(r['start'] // 60)}:{int(r['start'] % 60):02d}" + (f" (SLIDE {r['last']}부터 {int(r['sw'] // 60)}:{r['sw'] % 60:04.1f})" if "sw" in r else "") + f" | {r['d2']:.1f} |")
            elif shift[i]:
                st = Gf[i] / FPS; sw = int(m[6]) * 60 + float(m[7]) + shift[i] if m[5] else None
                table.append(f"| {rng(r)} | {int(st // 60)}:{int(st % 60):02d}" + (f" (SLIDE {r['last']}부터 {int(sw // 60)}:{sw % 60:04.1f})" if m[5] else "") + f" | {m[8]} |")
            else:
                table.append(line)
        length = Gf[-1] / FPS
        rep = tool.report_head(name, S, rows, sum(credit.values()) if credit else old_spent, speech, scale, length) + ["", "| 장 | 시작 | 음성(초) |", "|---|---|---|"] + table
        if credit:
            rep += ["", "| 음성 구획 | 생성 크레딧 |", "|---|---:|"] + [f"| {rng(r)} | {credit[r['first']]} |" for r in rows]
        if fixed_wait:
            rep += ["", f"학습 대기 합계 {fixed_wait}초", "", "| 장 | 대기 시작 | 대기 끝 | 길이 |", "|---|---|---|---|"]
            for i, r in enumerate(rows):
                for s, w in waits.get(r["first"], []):
                    s += 0 if swap[i] else shift[i]
                    rep.append(f"| {r['first']} | {tool.ts(s)} | {tool.ts(s + w)} | {w}초 |")
        (side / f"{name}_시간표.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

        # 4) 새 장의 강조: 새 자막 · 시간표로 강조 설정 전체의 시각을 다시 잡고(표시 번호가 같아 손 그림 모양이 전 장을 구울 때와 같다), 새 장 조각에만 얹는다
        emph.ALIGN = list(emph.alignments())
        marks = emph.plan(json.loads(config.read_text(encoding="utf-8")), emph.read_srt(side / f"{name}.srt"), emph.read_slides(side / f"{name}_시간표.md"))
        for m in marks: m["_path"] = emph.path(m)
        font = emph.font_sig(marks)

        # 5) 화면: 바뀌지 않은 장은 무손실로 자르고, 바뀐 장은 강조를 얹은 새 조각
        plan, seams, made_e, reenc = [], [], 0, 0
        i = 0
        while i < n:
            if swap[i]:
                lead = F[i] - turn(F[i]) if i and not swap[i - 1] else 0
                src = tmp / f"src{i:03d}.mp4"; ff("-i", segs[i], "-an", "-c", "copy", src)
                piece, new = emph.overlay("ffmpeg", src, Gf[i] - lead, Gf[i + 1], marks, font, tmp, i, lead)
                made_e += new; plan.append(piece)
                if i: seams.append((Gf[i] - lead, i, rows[i]["first"], "앞"))
                if i + 1 < n and not swap[i + 1]: seams.append((Gf[i + 1], i + 1, rows[i]["first"], "뒤"))
                i += 1; continue
            j = i
            while j + 1 < n and not swap[j + 1]: j += 1
            fa, fb = F[i], F[j + 1]
            if j + 1 < n:   # 뒤에 바뀐 장이 온다: 넘김 프레임 앞에서 끊는다
                fb = turn(F[j + 1])
                kp = max(k for k in keys if fa <= k <= fb)
                if kp < fb:   # 넘김 프레임이 키프레임이 아니다: 마지막 키프레임부터 다시 인코딩
                    if kp > fa: plan.append(("copy", fa, kp))
                    plan.append(("reenc", kp, fb)); reenc += 1
                    seams.append((kp + Gf[i] - F[i], None, rows[j]["first"], "다시인코딩"))
                    i = j + 1; continue
            plan.append(("copy", fa, fb))
            i = j + 1
        files = []
        for k, p in enumerate(plan):
            if isinstance(p, Path): files.append(p); continue
            kind, fa, fb = p; part = tmp / f"old{k:03d}.mp4"
            if kind == "copy":
                ff(*(["-ss", f"{fa / FPS + 0.001:.5f}"] if fa else []), "-i", video, "-frames:v", fb - fa, "-an", "-c", "copy", part)
            else:
                ff("-ss", at(fa), "-i", video, "-frames:v", fb - fa, *emph.ENC, part)
            if packets(part) != fb - fa: stop(f"기존 영상 {fa}~{fb} 프레임을 자른 조각의 프레임 수가 {packets(part)}다")
            files.append(part)
        lst = tmp / "parts.txt"; lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in files), encoding="utf-8")
        vid = tmp / "video.mp4"; ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid)
        if packets(vid) != Gf[-1]: stop(f"이은 화면이 {packets(vid)}프레임이다(기대 {Gf[-1]})")

        # 6) 소리: 기존 소리를 타임스탬프 틈을 무음으로 채워 풀고(그냥 풀면 장 경계의 틈만큼 앞당겨진다), 구획 소리의 시작 표본에서 잘라
        #    바뀐 구획 자리에 새 조각의 소리를 넣는다. 뒤 구획은 화면과 같은 프레임 수만큼 민다. 그다음 한 번 인코딩한다.
        old = tmp / "old.raw"
        ff("-i", video, "-vn", "-af", "aresample=async=1:min_hard_comp=0.0005:first_pts=0", "-ac", 1, "-ar", RATE, "-f", "s16le", old)
        A = [round(c * RATE) for c in clock] + [old.stat().st_size // 2]
        D = [(Gf[k] - F[k]) * SPF for k in range(n + 1)]
        raw = tmp / "audio.raw"
        with open(raw, "wb") as w, open(old, "rb") as r:
            for i in range(n):
                if swap[i]:
                    w.write(pcm(segs[i], A[i + 1] + D[i + 1] - A[i] - D[i]))
                else:
                    r.seek(2 * A[i]); w.write(r.read(2 * (A[i + 1] - A[i])))
            w.write(b"\0" * 2 * max(0, Gf[-1] * SPF - A[n] - D[n]))   # 끝을 화면 길이까지 무음으로 채운다(기존 영상은 소리가 수십 ms 짧다)
        aud = tmp / "audio.m4a"; ff("-f", "s16le", "-ar", RATE, "-ac", 1, "-i", raw, "-c:a", "aac", "-b:a", "160k", aud)
        ff("-i", vid, "-i", aud, "-map", "0:v", "-map", "1:a", "-c", "copy", result)

        # 7) 검사
        dv, da = (float(probe(result, "-select_streams", s, "-show_entries", "stream=duration", "-of", "csv=p=0")) for s in ("v:0", "a:0"))
        bad = []
        print(f"이음새(프레임 차이: 0.2초 앞~직전 | 직전~이음새 | 이음새~0.2초 뒤 · 소리: 이음새 앞 0.2초 최대 세기 · 이음새 표본 차) — 그림은 {seam_dir}")
        for s, sa, first, where in seams:
            fr = gray(result, s - 6, 13)
            dpre, dcut, dpost = diff(fr[0], fr[5]), diff(fr[5], fr[6]), diff(fr[6], fr[12])
            for off in (-6, -1, 0, 6):
                ff("-ss", at(s + off), "-i", result, "-frames:v", 1, seam_dir / f"{first}장_{where}_{off:+d}.png")
            msg = f"  {first}장 {where} {s / FPS:8.3f}초: 화면 {dpre:.2f} | {dcut:.2f} | {dpost:.2f}"
            if sa is not None:   # 소리 이음새는 그 구획 소리의 시작 표본
                x = pcm(result, int(0.4 * RATE), (A[sa] + D[sa]) / RATE - 0.2)
                v = [int.from_bytes(x[q:q + 2], "little", signed=True) for q in range(0, len(x), 2)]
                peak, jump = max(abs(t) for t in v[:len(v) // 2]), abs(v[len(v) // 2] - v[len(v) // 2 - 1])
                msg += f" · 소리 {peak} · {jump}"
                if peak > tool.QUIET_MAX or jump > 1000: bad.append(f"{first}장 {where} 소리")
            if dpre > 1 or dpost > 1 or (sa is None and dcut > 1): bad.append(f"{first}장 {where} 화면")
            print(msg)
        print(f"소리 {da:.3f}초 · 화면 {dv:.3f}초 · 차 {abs(dv - da):.3f}초")
        if abs(dv - da) > 0.05: bad.append("소리와 화면 길이")
        K = G / "제작도구" / "검사"
        chk = [subprocess.run([sys.executable, str(K / "자막대조.py"), str(side), o.script], capture_output=True, text=True),
               subprocess.run([sys.executable, str(HERE / "검사" / "장넘김_싱크.py"), str(result), str(side / f"{name}_시간표.md")], capture_output=True, text=True)]
        for i in range(n):
            if swap[i] and (i == 0 or not swap[i - 1]):
                j = i
                while j + 1 < n and swap[j + 1]: j += 1
                wav = tmp / f"region{i}.wav"; ff("-ss", f"{max(0, (A[i] + D[i]) / RATE - 0.3):.3f}", "-i", result, "-t", f"{(A[j + 1] + D[j + 1] - A[i] - D[i]) / RATE + 0.3:.3f}", "-vn", wav)
                chk.append(subprocess.run([sys.executable, str(HERE / "검사" / "말머리_잘림.py"), str(wav)], capture_output=True, text=True))
        for c in chk:
            print(c.stdout.strip()[-600:] + c.stderr.strip()[-300:])
        if chk[0].returncode: bad.append("자막대조")
        if not re.search(r"못 맞춘 기대 0 ", chk[1].stdout): bad.append("장넘김_싱크")
        if any(not re.search(r"앞이 말소리인 자리 0\b", c.stdout) for c in chk[2:]): bad.append("말머리_잘림")

    old_len = F[-1] / FPS
    print(f"\n바뀐 장 {[r['first'] for r, s in zip(rows, swap) if s]} · " + " · ".join(f"{rows[i]['first']}장 {(F[i + 1] - F[i]) / FPS:.2f}→{(Gf[i + 1] - Gf[i]) / FPS:.2f}초" for i in range(n) if swap[i]))
    print(f"영상 길이 {old_len:.2f}→{length:.2f}초(차 {length - old_len:+.2f}초) · 새로 만든 조각: 장 조각 {made_a} · 강조 조각 {made_e} · 다시 인코딩한 앞 장 끝 {reenc} · 걸린 시간 {time.time() - t_start:.0f}초")
    print(f"출력 {result}")
    if bad: stop(f"검사에 걸린 것: {bad} — 이음새 그림과 위 출력을 본다")
    print("검사 통과 — 이음새 그림을 눈으로 본 뒤 입고.py로 바꿔 끼운다")


if __name__ == "__main__":
    main()
