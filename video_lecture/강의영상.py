"""덱의 슬라이드와 낭독 대본으로 강의 영상을 만든다(슬라이드 그림 + 장별 음성 + 자막).

    python3 video_lecture/강의영상.py <일차 2자리> <첫 장> <끝 장> <목표 초> <출력 폴더> [--voice ID] [--model ID] [--speed 0.8] [--dry]

- 대본: docs/교재/통합반/NN일차/통합반_NN일차_대본*.md 의 `## [SLIDE NN]` 구획
- 슬라이드: 같은 폴더의 PPTX를 LibreOffice로 PDF, pdftoppm으로 그림으로 바꾼다
- 음성: ElevenLabs API(글자별 시간 포함). 장마다 따로 뽑아 저장해 두고, 글·음성·모델·속도가 같으면 다시 뽑지 않는다
- 시간: 장의 음성 길이만큼 그 장의 그림을 보여 준다. 문장 끝·물음 뒤·문단 사이·장 넘김에 쉼을 넣고, 그 쉼의 길이를 조절해 목표 시간에 맞춘다(말의 빠르기는 건드리지 않는다)
- 호흡(--breath): 문장 사이마다 똑같이 쉬지 않고, 이어서 말할 곳은 잇고 말이 한 단락 끝나는 곳에서 쉰다. 어디서 얼마나 쉴지는 video_lecture/쉼_저장/ 에 장마다 적어 둔 단계를 읽는다. 적히지 않은 장이 있으면 빈 자리를 만들어 두고 멈춘다. 이 도구는 OpenAI를 부르지 않는다
- 키: ELEVENLABS_API_KEY 환경변수, 없으면 --env 파일에서 읽는다. 키는 출력하지 않는다
"""
import argparse, base64, glob, hashlib, json, os, re, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("day"); ap.add_argument("first", type=int); ap.add_argument("last", type=int)
ap.add_argument("target", type=float); ap.add_argument("out")
ap.add_argument("--voice", default="nncZBoy1F7bDlybjMjgZ"); ap.add_argument("--model", default="eleven_v4")
ap.add_argument("--speed", type=float, default=0.80); ap.add_argument("--env", default="")
ap.add_argument("--gap", type=float, default=1.6); ap.add_argument("--dry", action="store_true")
ap.add_argument("--polished", action="store_true", help="윤문본(…_윤문.md)을 쓴다"); ap.add_argument("--polished2", action="store_true", help="2차 윤문본(…_윤문2.md)을 쓴다"); ap.add_argument("--tag", default="")
ap.add_argument("--breath", action="store_true", help="쉴 자리를 쉼_저장/ 에서 읽는다")
ap.add_argument("--natural", action="store_true", help="장 안에는 쉼을 넣지 않고 음성 모델이 읽은 그대로 둔다(장 넘김에만 쉼)")
ap.add_argument("--pause-short", dest="pause_short", type=float, default=0.35); ap.add_argument("--pause-mid", dest="pause_mid", type=float, default=0.8); ap.add_argument("--pause-long", dest="pause_long", type=float, default=1.3)
ap.add_argument("--pause-sentence", dest="pause_sentence", type=float, default=0.25); ap.add_argument("--pause-question", dest="pause_question", type=float, default=0.6); ap.add_argument("--pause-para", dest="pause_para", type=float, default=0.9)
a = ap.parse_args()
V4 = bool(re.match(r"eleven_v[34]", a.model))   # 빠르기 설정이 없는 모델. 읽은 그대로 두는 것이 기본이다
if V4 and not a.breath: a.natural = True
OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
CACHE = ROOT / "video_lecture" / "음성_저장"; CACHE.mkdir(exist_ok=True)
DECK = ROOT / "docs" / "교재" / "통합반" / f"{a.day}일차"


def run(*c): return subprocess.run(c, check=True, capture_output=True, text=True).stdout


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k and a.env:
        k = re.search(r"ELEVENLABS_API_KEY=(\S+)", Path(a.env).read_text()).group(1).strip("\"'")
    return k


def slides_text():
    text = ""
    kind = "_윤문2.md" if a.polished2 else "_윤문.md" if a.polished else ""
    files = [f for f in glob.glob(str(DECK / f"통합반_{a.day}일차_대본*.md")) if (f.endswith(kind) if kind else not re.search(r"_윤문2?\.md$", f))]
    for f in sorted(files, key=lambda x: (len(x), x)):
        s = Path(f).read_text(encoding="utf-8")
        text += re.split(r"^# 촬영 본문 끝.*$", s, flags=re.M)[0]
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\].*$", text, flags=re.M)
    out = []
    for i in range(1, len(parts), 2):
        first = int(parts[i].split("~")[0]); last = int(parts[i].split("~")[-1])
        if first < a.first or last > a.last: continue
        t = re.split(r"^# ", parts[i + 1], flags=re.M)[0]
        t = re.sub(r"^---\s*$|^>.*$", "", t, flags=re.M).replace("**", "")
        t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t).strip()
        if t: out.append((first, last, t))
    return out


def tts(text, prev, nxt):
    h = hashlib.sha1(json.dumps([text, a.voice, a.model, a.speed], ensure_ascii=False).encode()).hexdigest()[:16]
    mp3, js = CACHE / f"{h}.mp3", CACHE / f"{h}.json"
    if mp3.exists() and js.exists(): return mp3, json.loads(js.read_text()), 0
    body = {"text": text, "model_id": a.model, "previous_text": prev[-400:], "next_text": nxt[:400],
            "voice_settings": {"speed": a.speed, "stability": 0.5, "similarity_boost": 0.75}}
    if re.match(r"eleven_v[34]", a.model):   # 이 모델들은 빠르기 설정과 앞뒤 글 참고를 받지 않는다
        body = {"text": text, "model_id": a.model, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{a.voice}/with-timestamps?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), headers={"xi-api-key": key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            cost = int(r.headers.get("character-cost") or 0); d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"음성 생성 오류 {e.code}: {e.read().decode()[:300]}")
    mp3.write_bytes(base64.b64decode(d["audio_base64"])); js.write_text(json.dumps(d.get("alignment") or {}, ensure_ascii=False))
    return mp3, d.get("alignment") or {}, cost


def dur(p): return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)).strip())


S = slides_text()
chars = sum(len(t) for _, _, t in S)
print(f"장 {len(S)}개 · {chars}자 · 목표 {a.target:.0f}초")
if a.dry: sys.exit()

# 1) 슬라이드 그림
img_dir = ROOT / "video_lecture" / "슬라이드" / a.day; img_dir.mkdir(parents=True, exist_ok=True)
pptx = DECK / f"통합반_{a.day}일차.pptx"
stamp = img_dir / "stamp"
if not stamp.exists() or stamp.read_text() != str(pptx.stat().st_mtime):
    for f in img_dir.glob("s-*.png"): f.unlink()
    run("soffice", "--headless", "--convert-to", "pdf", "--outdir", str(img_dir), str(pptx))
    run("pdftoppm", "-r", "150", "-png", str(img_dir / pptx.with_suffix(".pdf").name), str(img_dir / "s"))
    stamp.write_text(str(pptx.stat().st_mtime))
imgs = sorted(img_dir.glob("s-*.png"), key=lambda p: int(p.stem.split("-")[1]))

# 2) 장별 음성
rows, spent = [], 0
for i, (f, l, t) in enumerate(S):
    mp3, al, cost = tts(t, S[i - 1][2] if i else "", S[i + 1][2] if i + 1 < len(S) else "")
    spent += cost; rows.append({"first": f, "last": l, "text": t, "mp3": mp3, "al": al, "d": dur(mp3)})
speech = sum(r["d"] for r in rows)

# 3) 쉼 넣기: 문장 끝, 물음 뒤, 문단 사이, 장이 넘어가는 자리에 말 없는 시간을 넣는다.
#    말의 빠르기는 건드리지 않고, 쉼의 길이만 늘이거나 줄여 목표 시간에 맞춘다.
import wave, array
PS, PQ, PP = a.pause_sentence, a.pause_question, a.pause_para
def cuts(r):
    """(넣을 자리의 초, 종류, 그 자리 앞의 문장) 목록과 마지막 문장. 자리는 문장 끝 글자와 다음 글자 사이의 한가운데."""
    ch, st, en = r["al"].get("characters") or [], r["al"].get("character_start_times_seconds") or [], r["al"].get("character_end_times_seconds") or []
    out, i, b = [], 0, 0
    while i < len(ch):
        if ch[i] in ".?!":
            j = i + 1; para = False
            while j < len(ch) and ch[j] in " \n\"'」)":
                para = para or ch[j] == "\n"; j += 1
            if j < len(ch):
                out.append(((en[i] + st[j]) / 2, "para" if para else ("q" if ch[i] == "?" else "s"), "".join(ch[b:j]).strip())); b = j
            i = j
        else: i += 1
    return out, "".join(ch[b:]).strip()


# 쉼의 단계(문장 사이 자리마다 하나)
# 0 = 잇는다. 쉬지 않고 바로 다음 문장으로 넘어간다(앞 문장을 받아 바로 풀어 주는 말, 나열의 중간).
# 1 = 짧게 쉰다. 같은 이야기 안이지만 한 박자 끊어 주는 곳.
# 2 = 한 호흡 쉰다. 한 가지 이야기가 끝난 곳, 중요한 말을 한 뒤, 물음을 던진 뒤.
# 3 = 크게 쉰다. 화제가 바뀌는 곳. 한 장에 많아야 한두 곳.
# 이 도구는 단계를 스스로 정하지도, 바깥 모델에 묻지도 않는다. 쉼_저장/ 에 적힌 것을 읽기만 한다.
BDIR = ROOT / "video_lecture" / "쉼_저장"


def breath(sents):
    """문장 목록을 받아 쉼_저장/ 에 적힌 단계(사이 자리마다 0~3)를 돌려준다. 아직 적히지 않았으면 빈 자리를 만들어 두고 None."""
    if len(sents) < 2: return []
    h = hashlib.sha1(json.dumps(sents, ensure_ascii=False).encode()).hexdigest()[:16]
    f = BDIR / f"{h}.json"
    if f.exists():
        v = json.loads(f.read_text()).get("쉼")
        if isinstance(v, list) and len(v) == len(sents) - 1 and all(x in (0, 1, 2, 3) for x in v): return v
        return None
    BDIR.mkdir(exist_ok=True); f.write_text(json.dumps({"문장": sents, "쉼": None}, ensure_ascii=False, indent=1), encoding="utf-8")
    return None


LEN = {"s": PS, "q": PQ, "para": PP, 0: 0.0, 1: a.pause_short, 2: a.pause_mid, 3: a.pause_long}
def plen(k):
    """쉼의 길이. 호흡 방식에서는 적어 둔 단계와, 물음 뒤·문단 사이의 최소 쉼 가운데 긴 쪽을 쓴다."""
    return max(LEN[k[0]], {"s": 0.0, "q": PQ, "para": PP}[k[1]]) if isinstance(k, tuple) else LEN[k]
def lv(k): return k[0] if isinstance(k, tuple) else None
for r in rows:
    c, tail = cuts(r); r["cuts"] = [(t, k) for t, k, _ in c]; r["sents"] = [x for _, _, x in c] + [tail]
if a.natural:
    for r in rows: r["cuts"] = []
if a.breath and not a.natural:
    got = [breath(r["sents"]) for r in rows]
    miss = [r["first"] for r, v in zip(rows, got) if v is None]
    if miss:
        sys.exit(f"쉼이 적히지 않은 장이 {len(miss)}곳 있다(SLIDE {', '.join(map(str, miss))}). {BDIR.name}/ 에서 \"쉼\"이 null인 파일을 채운 뒤 다시 돌린다. 음성은 저장돼 있어 다시 만들지 않는다.")
    for r, v in zip(rows, got): r["cuts"] = [(t, (lv, k0)) for (t, k0), lv in zip(r["cuts"], v)]
n = len(rows)
base = sum(plen(k) for r in rows for _, k in r["cuts"]) + a.gap * n
scale = 1.0 if a.target <= 0 else min(2.2, max(0.3, (a.target - speech) / base))
tempo = 1.0
def build(r, path):
    wav = OUT / "tmp.wav"
    run("ffmpeg", "-v", "error", "-y", "-i", str(r["mp3"]), "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(wav))
    with wave.open(str(wav)) as w: fr = w.getframerate(); data = array.array("h", w.readframes(w.getnframes()))
    out, pos, shift, marks = array.array("h"), 0, 0.0, []
    for t, k in r["cuts"]:
        cut = min(len(data), int(t * fr)); out.extend(data[pos:cut]); pos = cut
        add = plen(k) * scale; out.extend(array.array("h", [0]) * int(add * fr)); shift += add; marks.append((t, shift))
    out.extend(data[pos:]); out.extend(array.array("h", [0]) * int(a.gap * scale * fr))
    with wave.open(str(path), "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(fr); w.writeframes(out.tobytes())
    wav.unlink(); return len(out) / fr, marks

# 4) 장별 영상과 자막
segs, srt, clock, k = [], [], 0.0, 0
def ts(x): return f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int(x*1000%1000):03d}"
for r in rows:
    seg = OUT / f"seg_{r['first']:03d}.mp4"; wavp = OUT / f"seg_{r['first']:03d}.wav"
    d, marks = build(r, wavp); r["d2"] = d
    run("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(imgs[r["first"] - 1]), "-i", str(wavp), "-t", f"{d:.3f}",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r", "10", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k", str(seg))
    wavp.unlink(); segs.append(seg)
    def sh(t): return t + max([m[1] for m in marks if m[0] <= t] or [0.0])
    ch, st, en = r["al"].get("characters") or [], r["al"].get("character_start_times_seconds") or [], r["al"].get("character_end_times_seconds") or []
    buf, b0 = "", None
    for c, s0, e0 in zip(ch, st, en):
        if b0 is None and c.strip(): b0 = s0
        buf += c
        if c in ".?!\n" and buf.strip():
            k += 1; srt.append(f"{k}\n{ts(clock + sh(b0))} --> {ts(clock + sh(b0) + (e0 - b0))}\n{buf.strip()}\n"); buf, b0 = "", None
    r["start"] = clock; clock += d
gap = a.gap * scale
name = f"통합반_{a.day}일차_SLIDE{a.first:03d}-{a.last:03d}" + ("_윤문2" if a.polished2 else "_윤문" if a.polished else "") + (a.tag or "")
(OUT / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"), "-c", "copy", str(OUT / f"{name}.mp4"))
for s in segs: s.unlink()
(OUT / "list.txt").unlink()
SIDE = OUT.parent / "_작업" / "영상_자막_기록"; SIDE.mkdir(parents=True, exist_ok=True)   # 영상 폴더에는 영상만 둔다. 자막과 길이 기록은 옆의 _작업 폴더로
(SIDE / f"{name}.srt").write_text("\n".join(srt), encoding="utf-8")
rep = [f"# {name}", "", f"- 음성 {a.voice} · 모델 {a.model} · " + ("빠르기 설정 없음" if V4 else f"속도 {a.speed}"), f"- 글자 {chars}자 · 이번에 쓴 크레딧 {spent}",
       (f"- 말한 시간 합 {speech:.1f}초 · 장 안에는 쉼을 넣지 않음(모델이 읽은 그대로) · 장 넘김 {gap:.2f}초" if a.natural else
        f"- 말한 시간 합 {speech:.1f}초 · 넣은 쉼(자리는 쉼_저장에서 읽음): 잇는 곳 {sum(lv(k) == 0 for r in rows for _, k in r['cuts'])}곳 · 짧게 {sum(lv(k) == 1 for r in rows for _, k in r['cuts'])}곳 {a.pause_short*scale:.2f}초 · 한 호흡 {sum(lv(k) == 2 for r in rows for _, k in r['cuts'])}곳 {a.pause_mid*scale:.2f}초 · 크게 {sum(lv(k) == 3 for r in rows for _, k in r['cuts'])}곳 {a.pause_long*scale:.2f}초 · 물음 뒤 최소 {PQ*scale:.2f}초 · 문단 사이 최소 {PP*scale:.2f}초 · 장 넘김 {gap:.2f}초 (기본값의 {scale:.2f}배)" if a.breath else
        f"- 말한 시간 합 {speech:.1f}초 · 넣은 쉼: 문장 {PS*scale:.2f}초 · 물음 {PQ*scale:.2f}초 · 문단 {PP*scale:.2f}초 · 장 넘김 {gap:.2f}초 (기본값의 {scale:.2f}배)"),
       f"- 영상 길이 {dur(OUT / (name + '.mp4')):.1f}초 · 목표 {a.target:.0f}초", "", "| 장 | 시작 | 음성(초) |", "|---|---|---|"]
rep += [f"| {r['first']}{'~'+str(r['last']) if r['last']!=r['first'] else ''} | {int(r['start']//60)}:{int(r['start']%60):02d} | {r['d2']:.1f} |" for r in rows]
(SIDE / f"{name}_시간표.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
print("\n".join(rep[2:6]))
