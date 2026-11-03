"""완성된 이론 영상에 강조 표시(손으로 그린 동그라미 · 글씨)를 얹는다. 음성은 그대로 복사하므로 음성 비용이 들지 않는다.

    python 강조표시.py <영상.mp4> <강조.json> <출력.mp4> [--구간 시작초 끝초] [--확인 폴더]

- 자막 · 시간표: `산출물/영상/_작업/영상_자막_기록/<영상 이름>.srt` · `_시간표.md`. 시각: 자막의 문장 시작 + 음성_저장 글자 정렬의 문장 첫 글자부터 낱말까지.
- 강조.json: {"표시": [표시, …]}. 표시 하나:
    {"장": 18, "문장": "자막 문장 그대로", "낱말": "문장 안에서 그리기 시작할 말", "끝문장": "지울 때 시작되는 문장(생략하면 그 장의 말이 끝날 때)",
     "모양": "동그라미", "중심": [x, y], "반지름": [rx, ry]}
    {"장": …, "문장": …, "낱말": …, "모양": "글씨", "글": "포함", "중심": [x, y], "크기": 40}
  좌표는 1920x1080 영상 프레임 기준이다. 본보기: 강조표시_본보기/.
- 찾지 못한 문장 · 낱말, 화면 밖 좌표, 뜻이 둘인 문장은 표시 위치를 적고 멈춘다.
- --구간: 그 시각만 잘라 시험본을 만든다. --확인: 표시가 다 그려진 시점의 프레임을 표시마다 저장한다(가림 · 위치를 눈으로 본다).
"""
import argparse, json, math, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CACHE = HERE / "음성_저장"
FONT = Path("C:/Windows/Fonts/malgunbd.ttf")
FPS, DRAW, FADE, SS, RED = 30, 0.45, 0.25, 2, (229, 57, 53)
W, H = 1920, 1080


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
    rows = re.findall(r"^\| (\d+)(?:~\d+)? \| (\d+):(\d+)(?::(\d+))? \|", p.read_text(encoding="utf-8"), flags=re.M)
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
    """문장 첫 글자에서 낱말까지의 초. 같은 문장이 든 캐시가 여럿이면 자막의 문장 길이가 같은 것을 쓴다."""
    k0 = sentence.find(word)
    if k0 < 0: stop(f"{where}: 낱말 「{word}」이 문장 「{sentence}」에 없음")
    for j, full, d in ALIGN:
        i = full.find(sentence)
        if i < 0: continue
        st, en = d["character_start_times_seconds"], d["character_end_times_seconds"]
        if abs((en[i + len(sentence) - 1] - st[i]) - duration) < 0.02: return st[i + k0] - st[i]
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
    t0, t1 = a.span if a.span else (0.0, duration(a.ffmpeg, video))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); rows, last, count = [], None, 0
        for f in range(round((t1 - t0) * FPS)):
            s = state_at(marks, t0 + f / FPS)
            if s == last:
                rows[-1][1] += 1; continue
            png = None
            if s:
                img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
                for i, e, alpha in s: draw_mark(img, marks[i], e, alpha)
                png = tmp / f"{count:05d}.png"; img.resize((W, H), Image.LANCZOS).save(png); count += 1
            rows.append([png, 1]); last = s
        # 표시가 없는 구간과 있는 구간을 따로 인코딩해 잇는다. 영상 전체에 투명 층을 깔면 메모리가 모자란다
        enc = ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage"]
        parts, frame, i = [], 0, 0
        while i < len(rows):
            j = i
            while j < len(rows) and bool(rows[j][0]) == bool(rows[i][0]): j += 1
            n = sum(r[1] for r in rows[i:j]); part = tmp / f"part{len(parts):04d}.mp4"
            cut = ["-ss", f"{t0 + frame / FPS:.5f}", "-t", f"{n / FPS:.5f}", "-i", str(video)]
            if rows[i][0]:
                lst = tmp / f"list{len(parts):04d}.txt"
                body = "".join(f"file '{p.as_posix()}'\nduration {k / FPS:.5f}\n" for p, k in rows[i:j])
                lst.write_text(body + f"file '{rows[j - 1][0].as_posix()}'\n", encoding="utf-8")
                subprocess.run([a.ffmpeg, "-v", "error", "-y", *cut, "-f", "concat", "-safe", "0", "-i", str(lst), "-filter_complex",
                                f"[0:v]fps={FPS}[b];[1:v]fps={FPS},format=rgba[o];[b][o]overlay=eof_action=pass,format=yuv420p[v]", "-map", "[v]", *enc, str(part)], check=True)
            else:
                subprocess.run([a.ffmpeg, "-v", "error", "-y", *cut, "-vf", f"fps={FPS},format=yuv420p", *enc, str(part)], check=True)
            parts.append(part); frame += n; i = j
        joined = tmp / "joined.mp4"; lst = tmp / "parts.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
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
    print(f"출력 {a.out} · 표시 {len(marks)}개")


if __name__ == "__main__":
    main()
