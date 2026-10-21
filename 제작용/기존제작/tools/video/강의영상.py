"""이론 대본 파일 하나를 영상 하나로 만든다(덱의 장 그림 + 장별 음성 + 자막). 대본 파일 하나가 촬영 구간 하나다.

    python3 제작용/기존제작/tools/video/강의영상.py <출력 폴더> <대본 파일 …> [--breath] [--dry] [--voice ID] [--model ID]

- 대본: 산출물/<과정>/이론/NN회차/대본/*.md. `## [SLIDE NN]` 또는 `## [SLIDE NN~MM]` 구획만 읽고, 다른 `#`·`##` 제목에서 그 구획을 끝낸다.
  `>`로 시작하는 줄(제작 표시), `---`, 표 줄, `**`는 낭독하지 않는다
- 슬라이드: 대본 폴더 위의 <과정>_NN일차.pptx를 LibreOffice로 PDF, pdftoppm으로 그림으로 바꾼다. 장 번호가 PPTX 장 수를 넘으면 멈춘다
- 음성: ElevenLabs API(글자별 시간 포함). 장마다 따로 뽑아 저장해 두고, 글·음성·모델·속도가 같으면 다시 뽑지 않는다
- 시간: 장의 음성 길이만큼 그 장의 그림을 보여 준다. `SLIDE NN~MM`처럼 여러 장을 한 구획에서 읽으면 그 시간을 장 수로 나눠 차례로 보여 준다.
  목표 초(--target)를 주지 않으면 쉼의 길이를 늘이거나 줄이지 않는다(기준 51번)
- 호흡(--breath): 어디서 얼마나 쉴지는 쉼_저장/ 에 장마다 적어 둔 단계를 읽는다. 적히지 않은 장이 있으면 빈 자리를 만들어 두고 멈춘다. 이 도구는 OpenAI를 부르지 않는다
- --dry: 파일마다 장 범위·글자 수와 첫 문장 점검(기준 49번)만 찍는다. 음성을 부르지 않으니 돈이 들지 않는다
- 키: ELEVENLABS_API_KEY 환경변수, 없으면 --env 파일에서 읽는다. 키는 출력하지 않는다
"""
import argparse, base64, hashlib, json, os, re, subprocess, sys, urllib.request, urllib.error, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("scripts", nargs="+")
ap.add_argument("--target", type=float, default=0.0)
ap.add_argument("--voice", default="nncZBoy1F7bDlybjMjgZ"); ap.add_argument("--model", default="eleven_v4")
ap.add_argument("--speed", type=float, default=0.80); ap.add_argument("--env", default="")
ap.add_argument("--gap", type=float, default=1.6); ap.add_argument("--dry", action="store_true")
ap.add_argument("--breath", action="store_true", help="쉴 자리를 쉼_저장/ 에서 읽는다")
ap.add_argument("--natural", action="store_true", help="장 안에는 쉼을 넣지 않고 음성 모델이 읽은 그대로 둔다(장 넘김에만 쉼)")
ap.add_argument("--pause-short", dest="pause_short", type=float, default=0.35); ap.add_argument("--pause-mid", dest="pause_mid", type=float, default=0.8); ap.add_argument("--pause-long", dest="pause_long", type=float, default=1.3)
ap.add_argument("--pause-sentence", dest="pause_sentence", type=float, default=0.25); ap.add_argument("--pause-question", dest="pause_question", type=float, default=0.6); ap.add_argument("--pause-para", dest="pause_para", type=float, default=0.9)
a = ap.parse_args()
V4 = bool(re.match(r"eleven_v[34]", a.model))   # 빠르기 설정이 없는 모델. 읽은 그대로 두는 것이 기본이다
if V4 and not a.breath: a.natural = True
CACHE = HERE / "음성_저장"
BAD_START = ("그럼", "그러면", "그래서", "자 ", "자,", "이제", "이어서")   # 기준 49번: 영상은 따로 재생되므로 앞 영상을 받는 말로 시작하지 않는다


def run(*c): return subprocess.run(c, check=True, capture_output=True, text=True).stdout


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k and a.env:
        k = re.search(r"ELEVENLABS_API_KEY=(\S+)", Path(a.env).read_text()).group(1).strip("\"'")
    return k


def deck_of(script):
    """대본 폴더 위의 덱 PPTX. 없거나 둘 이상이면 멈춘다."""
    d = list(Path(script).resolve().parent.parent.glob("*_*일차.pptx"))
    if len(d) != 1: sys.exit(f"{script}: 덱 PPTX를 하나로 정하지 못했다({[x.name for x in d]})")
    return d[0]


def deck_count(pptx):
    with zipfile.ZipFile(pptx) as z: return sum(bool(re.fullmatch(r"ppt/slides/slide\d+\.xml", n)) for n in z.namelist())


def slides_text(script):
    """대본의 장 구획을 (첫 장, 끝 장, 낭독할 글) 목록으로 돌려준다."""
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\].*$", Path(script).read_text(encoding="utf-8"), flags=re.M)
    out = []
    for i in range(1, len(parts), 2):
        first = int(parts[i].split("~")[0]); last = int(parts[i].split("~")[-1])
        t = re.split(r"^#{1,2} ", parts[i + 1], flags=re.M)[0]
        t = re.sub(r"^---\s*$|^>.*$|^\|.*$", "", t, flags=re.M).replace("**", "")
        t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        if t: out.append((first, last, t))
    if not out: sys.exit(f"{script}: `## [SLIDE NN]` 구획이 없다")
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


def check(script):
    """파일 하나의 장 구획, 덱, 영상 이름을 정하고 장 번호와 첫 문장을 점검한다. 문제를 글로 돌려준다."""
    S = slides_text(script); pptx = deck_of(script); n = deck_count(pptx); probs = []
    nums = [x for f, l, _ in S for x in range(f, l + 1)]
    if max(nums) > n: probs.append(f"SLIDE {max(nums)}가 덱 {pptx.name}의 {n}장을 넘는다")
    if nums != sorted(nums) or len(set(nums)) != len(nums): probs.append("SLIDE 번호가 겹치거나 거꾸로 간다")
    if S[0][2].startswith(BAD_START): probs.append(f"첫 문장이 이어 받는 말로 시작한다: {S[0][2][:30]}")
    sp = Path(script).resolve()
    name = f"{sp.parents[3].name}_{sp.parents[1].name}_{sp.stem}"   # 예: 통합반_01회차_01_이론_지식자산화
    return S, pptx, name, probs


def make(S, pptx, name):

    # 1) 슬라이드 그림
    img_dir = HERE / "슬라이드" / pptx.stem; img_dir.mkdir(parents=True, exist_ok=True)
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
    BDIR = HERE / "쉼_저장"


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
        shown = imgs[r["first"] - 1:r["last"]]   # SLIDE NN~MM이면 그 시간을 장 수로 나눠 차례로 보여 준다
        ins = [x for img in shown for x in ("-loop", "1", "-t", f"{d / len(shown):.3f}", "-i", str(img))]
        fit = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=10"
        vf = ";".join(f"[{n}:v]{fit}[v{n}]" for n in range(len(shown))) + ";" + "".join(f"[v{n}]" for n in range(len(shown))) + f"concat=n={len(shown)}:v=1:a=0[v]"
        run("ffmpeg", "-v", "error", "-y", *ins, "-i", str(wavp), "-filter_complex", vf, "-map", "[v]", "-map", f"{len(shown)}:a", "-t", f"{d:.3f}",
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


OUT = Path(a.out)
jobs, total, bad = [], 0, 0
for sc in a.scripts:
    S, pptx, name, probs = check(sc)
    chars = sum(len(t) for _, _, t in S); total += chars; bad += bool(probs)
    print(f"{name} · SLIDE {S[0][0]}~{S[-1][1]} · 구획 {len(S)}개 · {chars}자" + "".join(f"\n  ! {p}" for p in probs))
    jobs.append((S, pptx, name))
print(f"합계 {len(jobs)}편 · {total}자")
if bad: sys.exit(f"점검에 걸린 파일이 {bad}개 있다. 고친 뒤 다시 돌린다")
if a.dry: sys.exit()
OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(exist_ok=True)
for job in jobs: make(*job)
