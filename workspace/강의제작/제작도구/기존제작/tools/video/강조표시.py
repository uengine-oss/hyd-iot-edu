"""완성된 이론 영상에 강조 표시(손으로 그린 동그라미 · 글씨)를 얹는다. 음성은 그대로 복사하므로 음성 비용이 들지 않는다.

    python 강조표시.py <영상.mp4> <강조.json> <출력.mp4> [--구간 시작초 끝초] [--확인 폴더]

- 자막 · 시간표: `산출물/영상/_작업/영상_자막_기록/<영상 이름>.srt` · `_시간표.md`. 시각: 자막의 문장 시작 + 음성_저장 글자 정렬의 문장 첫 글자부터 낱말까지.
- 강조.json: {"표시": [표시, …]}. 표시 하나:
    {"장": 18, "문장": "자막 문장 그대로", "낱말": "문장 안에서 그리기 시작할 말", "끝문장": "지울 때 시작되는 문장(생략하면 그 장의 말이 끝날 때)",
     "모양": "동그라미", "중심": [x, y], "반지름": [rx, ry]}
    {"장": …, "문장": …, "낱말": …, "모양": "글씨", "글": "포함", "중심": [x, y], "크기": 40}
  좌표는 1920x1080 영상 프레임 기준이다. 본보기: 강조표시_본보기/.
- 찾지 못한 문장 · 낱말, 화면 밖 좌표, 뜻이 둘인 문장은 표시 위치를 적고 멈춘다.
- 글씨 글꼴: 환경변수 `EMPH_FONT`(맑은 고딕 굵게 TTF 경로), 없으면 `C:/Windows/Fonts/malgunbd.ttf`.
- 장 조각: 강조 전 영상을 장 구획(시간표의 행)마다 키프레임에서 무손실로 잘라, 장 조각마다 표시를 얹어 `조각_저장/강조/`에 보관한다.
  조각 이름은 원본 조각 · 그 장의 표시 · 인코딩 설정의 해시라, 다시 돌리면 바뀐 장만 인코딩하고 나머지는 보관본을 이어 붙인다(표시 하나를 고치면 그 장만).
- --구간: 그 시각을 덮는 장 조각만 이어 시험본을 만든다. --확인: 표시가 다 그려진 시점의 프레임을 표시마다 저장한다(가림 · 위치를 눈으로 본다).
"""
import argparse, hashlib, json, math, os, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CACHE = HERE / "음성_저장"
FONT = Path(os.environ.get("EMPH_FONT") or "C:/Windows/Fonts/malgunbd.ttf")
FPS, DRAW, FADE, SS, RED = 30, 0.45, 0.25, 2, (229, 57, 53)
W, H = 1920, 1080
PIECES = HERE / "조각_저장" / "강조"   # 장 조각 보관함 — 저장소에 올리지 않는다(동기화.py SKIP_DIRS). 지워도 다시 만들어진다
VERSION = "장조각-1"   # 조각을 만드는 방법이 바뀌면 올린다(옛 조각을 쓰지 않게)


def stop(msg): sys.exit(f"강조표시: {msg}")


def seconds(s):
    m = re.match(r"(\d+):(\d+):(\d+),(\d+)", s)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000


def read_srt(p):
    out = []
    for b in re.split(r"\n\n+", p.read_text(encoding="utf-8").strip()):
        l = b.split("\n")
        if len(l) >= 3: out.append((seconds(l[1][:12]), seconds(l[1].split("-->")[1].strip()), " ".join(l[2:])))
    return out


def read_slides(p):
    """시간표에서 장 번호 → 시작 초(시간표는 초 단위로 반올림해 적는다)."""
    rows = re.findall(r"^\| (\d+)(?:~\d+)? \| (\d+):(\d+)(?::(\d+))?(?: \(SLIDE[^)]*\))? \|", p.read_text(encoding="utf-8"), flags=re.M)
    table = {}
    for n, a, b, c in rows:
        table[int(n)] = int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
    if not table: stop(f"{p}: 장 시작 표를 읽지 못함")
    return table


def alignments():
    for j in CACHE.glob("*.json"):
        try: d = json.loads(j.read_text(encoding="utf-8"))
        except ValueError: continue
        if isinstance(d, dict) and d.get("characters"): yield j, "".join(d["characters"]), d


def word_offset(where, sentence, duration, word):
    """문장 첫 글자에서 낱말까지의 초. 같은 문장이 든 캐시가 여럿이면 자막의 문장 길이가 가장 가까운 것을 쓴다.
    학습 대기 바로 앞 문장은 자막 끝이 대기 시작에서 잘린다. 대기 자리는 말 끝 0.1초 전부터 고르므로 자막이 그만큼 짧을 수 있다."""
    k0 = sentence.find(word)
    if k0 < 0: stop(f"{where}: 낱말 「{word}」이 문장 「{sentence}」에 없음")
    best = None
    for j, full, d in ALIGN:
        i = full.find(sentence)
        if i < 0: continue
        st, en = d["character_start_times_seconds"], d["character_end_times_seconds"]
        gap = abs((en[i + len(sentence) - 1] - st[i]) - duration)
        if gap < 0.12 and (best is None or gap < best[0]): best = (gap, st[i + k0] - st[i])
    if best: return best[1]
    stop(f"{where}: 문장 「{sentence}」의 글자 정렬을 음성_저장에서 찾지 못함")


def find_sentence(where, subs, slides, n, sentence):
    if n not in slides: stop(f"{where}: {n}장이 시간표에 없음")
    later = [s for k, s in slides.items() if k > n]
    lo, hi = slides[n] - 1, (min(later) - 0.5 if later else 1e9)
    hits = [x for x in subs if x[2] == sentence and lo <= x[0] < hi]
    if len(hits) != 1: stop(f"{where}: {n}장에서 문장 「{sentence}」을 {len(hits)}개 찾음(1개여야 함)")
    return hits[0], hi


def plan(cfg, subs, slides):
    marks = []
    for i, m in enumerate(cfg["표시"], 1):
        where = f"표시 {i}"
        for f in ("장", "문장", "낱말", "모양", "중심"):
            if f not in m: stop(f"{where}: 「{f}」 없음")
        need = {"동그라미": "반지름", "글씨": "글"}.get(m["모양"])
        if not need: stop(f"{where}: 모르는 모양 「{m['모양']}」")
        if not m.get(need): stop(f"{where}: 「{need}」 없음")
        x, y = m["중심"]
        if not (0 <= x <= W and 0 <= y <= H): stop(f"{where}: 중심 {m['중심']}이 화면 밖")
        hit, hi = find_sentence(where, subs, slides, m["장"], m["문장"])
        start = hit[0] + word_offset(where, m["문장"], hit[1] - hit[0], m["낱말"])
        if m.get("끝문장"):
            end = find_sentence(where, subs, slides, m["장"], m["끝문장"])[0][0]
        else:
            end = max(s[1] for s in subs if s[0] < hi)
        if end <= start: stop(f"{where}: 지우는 시각이 그리는 시각보다 앞섬")
        marks.append(dict(m, start=start, end=end, seed=i))
    return marks


def stroke(m, n=120):
    """조금 삐뚤게, 시작점을 지나쳐 닫히는 타원."""
    rnd = random.Random(m["seed"]); a0 = rnd.uniform(-2.4, -1.8)
    p1, p2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
    cx, cy = m["중심"]; rx, ry = m["반지름"]; pts = []
    for i in range(n + 1):
        u = i / n; a = a0 + u * 2 * math.pi * 1.07
        w = 1 + 0.035 * math.sin(2 * a + p1) + 0.02 * math.sin(3 * a + p2) + 0.025 * u
        pts.append(((cx + rx * w * math.cos(a)) * SS, (cy + ry * w * math.sin(a)) * SS))
    return pts


def draw_mark(img, m, e, alpha):
    if m["모양"] == "동그라미":
        p = m["_path"]
        ImageDraw.Draw(img).line(p[:max(2, int(e * len(p)))], fill=RED + (alpha,), width=5 * SS, joint="curve")
    else:   # 글씨 — 왼쪽부터 써 나가듯 드러낸다
        font = ImageFont.truetype(str(FONT), m.get("크기", 40) * SS)
        cx, cy = m["중심"][0] * SS, m["중심"][1] * SS
        l, t, r, b = ImageDraw.Draw(img).textbbox((cx, cy), m["글"], font=font, anchor="mm")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((cx, cy), m["글"], font=font, fill=RED + (alpha,), anchor="mm")
        layer.paste((0, 0, 0, 0), (int(l + (r - l) * e), 0, img.size[0], img.size[1]))
        img.alpha_composite(layer)


def state_at(marks, t):
    """그 시각의 표시 상태. 같은 상태가 이어지는 동안은 그림 한 장으로 잇는다."""
    out = []
    for i, m in enumerate(marks):
        if t < m["start"] or t > m["end"] + FADE: continue
        e = 1 - (1 - min(1, (t - m["start"]) / DRAW)) ** 2
        alpha = 255 if t <= m["end"] else int(255 * (1 - (t - m["end"]) / FADE))
        out.append((i, round(e, 3), alpha))
    return tuple(out)


def duration(ffmpeg, video):
    out = subprocess.run([ffmpeg, "-i", str(video)], capture_output=True).stderr.decode("utf-8", "replace")
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not d: stop(f"{video}: 길이를 읽지 못함")
    return int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3])


def read_rows(p):
    """시간표의 장 구획 순서대로 (첫 장, 시작 초(초 아래 버림), 음성 초)."""
    rows = re.findall(r"^\| (\d+)(?:~\d+)? \| (\d+):(\d+)(?: \(SLIDE[^)]*\))? \| ([\d.]+) \|", p.read_text(encoding="utf-8"), flags=re.M)
    if not rows: stop(f"{p}: 장 구획 표를 읽지 못함")
    return [(int(n), int(a) * 60 + int(b), float(d)) for n, a, b, d in rows]


def probe_of(ffmpeg):
    q = shutil.which(ffmpeg) or ffmpeg
    return str(Path(q).with_name("ffprobe" + Path(q).suffix)) if os.sep in q or "/" in q else "ffprobe"


def pieces(probe, video, rows, total):
    """장 구획마다 [시작, 끝) 초. 강조 전 영상은 강의영상.py가 장 조각을 이어 붙인 것이라 장마다 키프레임에서 시작한다 —
    시간표의 시작(초 아래 버림)부터 1초 안의 마지막 키프레임이 그 장의 시작이다(장 안의 키프레임은 25초 뒤 · 간지 넘김뿐)."""
    out = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout
    keys = sorted(float(x) for x in re.findall(r"\d+\.\d+", out))
    starts = []
    for first, s, _ in rows:
        hit = [k for k in keys if s - 0.05 <= k < s + 1.05]
        if not hit: stop(f"{first}장: 시간표 시작 {s}초에서 1초 안에 키프레임이 없다 — 강의영상.py가 만든 강조 전 영상인지 본다")
        starts.append(max(hit))
    starts[0] = 0.0
    ends = starts[1:] + [total]
    for (first, _, d2), b0, b1 in zip(rows, starts, ends):
        if abs((b1 - b0) - d2) > 0.35: stop(f"{first}장: 조각 길이 {b1 - b0:.2f}초가 시간표 음성 {d2}초와 다르다")
    return [(r[0], b0, b1) for r, b0, b1 in zip(rows, starts, ends)]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("config"); ap.add_argument("out")
    ap.add_argument("--구간", nargs=2, type=float, dest="span"); ap.add_argument("--확인", dest="check")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    video = Path(a.video); rec = video.parent.parent / "_작업" / "영상_자막_기록"
    srt, table = rec / f"{video.stem}.srt", rec / f"{video.stem}_시간표.md"
    for p in (video, srt, table, Path(a.config)):
        if not p.exists(): stop(f"{p}: 파일 없음")
    global ALIGN
    ALIGN = list(alignments())
    subs, slides = read_srt(srt), read_slides(table)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    marks = plan(cfg, subs, slides)
    for m in marks:
        if m["모양"] == "동그라미": m["_path"] = stroke(m)
        print(f"표시 {m['seed']}: {m['장']}장 {m['start']:.2f}~{m['end']:.2f}초 {m['모양']} {m.get('글', '')}")
    probe = probe_of(a.ffmpeg)
    total = duration(a.ffmpeg, video)
    parts = pieces(probe, video, read_rows(table), total)
    if a.span:   # 시험: 그 시각을 덮는 장 조각만
        parts = [x for x in parts if x[2] > a.span[0] and x[1] < a.span[1]]
        if not parts: stop("--구간이 영상 밖이다")
    t0, t1 = parts[0][1], parts[-1][2]
    font = sha(FONT) if any(m["모양"] == "글씨" for m in marks) else ""
    # 키프레임 간격은 강조 전 영상과 같은 25초다(10fps × x264 기본 250) — 30fps 기본 간격(8초)이면 영상 부분이 두 배가 넘어 54분 편이 100 MiB를 넘었다
    enc = ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage", "-g", str(25 * FPS)]
    PIECES.mkdir(parents=True, exist_ok=True)
    made, files = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        blank = tmp / "blank.png"; Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
        for k, (first, b0, b1) in enumerate(parts):
            f0, f1 = round(b0 * FPS), round(b1 * FPS); n = f1 - f0
            src = tmp / f"src{k:03d}.mp4"   # 그 장의 강조 전 영상(키프레임에서 무손실로 자름)
            subprocess.run([a.ffmpeg, "-v", "error", "-y", "-ss", f"{b0 + 0.001:.5f}", "-i", str(video), "-t", f"{b1 - b0 - 0.002:.5f}",
                            "-an", "-c", "copy", str(src)], check=True)
            runs, last = [], None
            for f in range(f0, f1):
                st = state_at(marks, f / FPS)
                if runs and st == last: runs[-1][1] += 1
                else: runs.append([st, 1]); last = st
            sig = [[c, [[marks[i]["모양"], marks[i]["중심"], marks[i].get("반지름"), marks[i].get("글"), marks[i].get("크기"), marks[i]["seed"], e, al]
                        for i, e, al in st]] for st, c in runs]
            key = hashlib.sha1(json.dumps([VERSION, sha(src), n, enc, FPS, font, sig], ensure_ascii=False).encode()).hexdigest()[:20]
            piece = PIECES / f"{key}.mp4"
            if not piece.exists():
                base = f"fps={FPS},tpad=stop=-1:stop_mode=clone"
                if any(st for st, _ in runs):
                    body = ""
                    for j, (st, c) in enumerate(runs):
                        png = blank
                        if st:
                            img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
                            for i, e, al in st: draw_mark(img, marks[i], e, al)
                            png = tmp / f"o{k:03d}_{j:05d}.png"; img.resize((W, H), Image.LANCZOS).save(png)
                        body += f"file '{png.as_posix()}'\nduration {c / FPS:.5f}\n"
                        lastpng = png
                    lst = tmp / f"list{k:03d}.txt"; lst.write_text(body + f"file '{lastpng.as_posix()}'\n", encoding="utf-8")
                    cmd = [a.ffmpeg, "-v", "error", "-y", "-i", str(src), "-f", "concat", "-safe", "0", "-i", str(lst), "-filter_complex",
                           f"[0:v]{base}[b];[1:v]fps={FPS},format=rgba[o];[b][o]overlay=eof_action=pass,format=yuv420p[v]", "-map", "[v]"]
                else:
                    cmd = [a.ffmpeg, "-v", "error", "-y", "-i", str(src), "-vf", f"{base},format=yuv420p"]
                part = tmp / f"p{k:03d}.mp4"
                subprocess.run([*cmd, "-frames:v", str(n), *enc, str(part)], check=True)
                shutil.move(str(part), piece); made += 1
            files.append(piece)
        joined = tmp / "joined.mp4"; lst = tmp / "parts.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in files), encoding="utf-8")
        subprocess.run([a.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
        subprocess.run([a.ffmpeg, "-v", "error", "-y", "-i", str(joined), "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", str(video),
                        "-map", "0:v", "-map", "1:a", "-c", "copy", a.out], check=True)
    got = duration(a.ffmpeg, Path(a.out))
    if abs(got - (t1 - t0)) > 0.2: stop(f"{a.out}: 길이 {got:.2f}초가 기대 {t1 - t0:.2f}초와 다름")
    if a.check:
        c = Path(a.check); c.mkdir(parents=True, exist_ok=True)
        for m in marks:
            t = min(m["start"] + DRAW + 0.1, m["end"])
            if not t0 <= t < t1: continue
            subprocess.run([a.ffmpeg, "-v", "error", "-y", "-ss", f"{t - t0}", "-i", a.out, "-frames:v", "1", str(c / f"표시{m['seed']:02d}.png")], check=True)
    print(f"출력 {a.out} · 표시 {len(marks)}개 · 장 조각 {len(files)}개(새로 만든 것 {made}, 보관함 재사용 {len(files) - made})")


if __name__ == "__main__":
    main()
