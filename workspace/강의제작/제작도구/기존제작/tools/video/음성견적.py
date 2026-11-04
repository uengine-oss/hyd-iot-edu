"""이론 대본의 구획을 음성 캐시와 대조해 새로 뽑을 구획 · 글자 수를 낸다. 유료 호출이 없고 키도 쓰지 않는다.

    <py> workspace/강의제작/제작도구/기존제작/tools/video/음성견적.py <대본 파일 …> --voice <음성 ID> [--model ID] [--speed 값]
    <py> workspace/강의제작/제작도구/기존제작/tools/video/음성견적.py --안쓰는것 [<대본 파일 …>] [--지우기]

- 낭독 추출(slides_text) · 캐시 이름(cache_key) · 모델과 빠르기 기본값은 강의영상.py에서 불러 쓴다. 사본 로직이 없어 어긋나지 않는다.
- 음성 ID는 꼭 준다. 캐시 이름에 들어가고 강의영상.py에도 기본값이 없다(영상.md V-4).
- 글 · 음성 · 모델 · 빠르기가 같은 구획은 캐시(mp3 · json 둘 다)를 쓰므로 비용이 없다. 둘 중 하나만 있으면 강의영상.py처럼 새로 뽑는 구획으로 센다.
- 여러 파일에 같은 글이 있으면 한 번만 센다(두 과정이 같은 구획을 함께 쓸 때).
출력은 파일마다 구획 · 새 구획 · 새 글자와 새 구획의 장 번호, 끝에 합계다. 크레딧 단가는 영상.md V-4, 남은 크레딧은 음성키.py.

--안쓰는것: 음성_저장/ · 쉼_저장/ 가운데 쓰이지 않는 항목의 목록 · 개수 · MB만 찍는다(지우지 않는다).
- 쓰는 음성 = 대본 구획의 캐시 이름 + 대응 mp4가 있는 자막에 글이 그대로 든 음성. 대본은 산출물 이론 대본 전부 + 이 PC 작업/ 아래의 `## [SLIDE` 대본
  + 명령줄에 준 대본을 더한 것이다(준 대본이 기본 목록을 대신하지 않는다). 캐시 이름의 음성 · 모델 · 빠르기는 영상 시간표에 적힌 것(+ --voice를 주면 그것).
  자막 · 시간표는 산출물과 작업/ 아래의 `_작업/영상_자막_기록/`(mp4는 그 폴더 둘 위의 `*/<이름>.mp4`)다.
- 쓰는 쉼 = 「문장」을 공백 없이 이은 것이 쓰는 음성 · 대본 구획의 글(공백 없이)과 같은 것.
- --지우기는 그 목록을 실제로 지운다. 다른 세션이 고치는 대본과 아직 바꿔 끼우지 않은 영상이 모두 커밋된 뒤 pull하고 돌린다(그 전에 지우면 그 음성을 다시 산다).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import 강의영상 as tool  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("scripts", nargs="*")
ap.add_argument("--voice")
ap.add_argument("--model", default=tool.ap.get_default("model"))
ap.add_argument("--speed", type=float, default=tool.ap.get_default("speed"))
ap.add_argument("--안쓰는것", dest="unused", action="store_true", help="음성_저장 · 쉼_저장에서 쓰이지 않는 항목을 찍는다")
ap.add_argument("--지우기", dest="delete", action="store_true", help="--안쓰는것의 목록을 지운다")
a = ap.parse_args()
if not a.unused:
    if a.delete:
        ap.error("--지우기는 --안쓰는것과 함께 쓴다")
    if not a.voice:
        ap.error("--voice <음성 ID>가 필요하다(캐시 이름에 들어간다 — 영상.md V-4)")
    if not a.scripts:
        ap.error("대본 파일을 준다")


def norm(s):
    return "".join(s.split())


def unused():
    made = tool.HERE.parents[3] / "산출물"   # workspace/강의제작/산출물
    work = tool.HERE.parents[5] / "작업"
    drafts = [f for f in sorted(work.rglob("*.md")) if re.search(r"^## \[SLIDE [0-9~]+\]", f.read_text(encoding="utf-8", errors="replace"), re.M)] if work.is_dir() else []
    scripts = list(dict.fromkeys(f.resolve() for f in sorted(made.glob("*/이론/*/대본/*.md")) + drafts + [Path(s) for s in a.scripts]))
    sides = [made / "영상" / "_작업" / "영상_자막_기록"] + (sorted({f.parent for f in work.rglob("*.srt")} | {f.parent for f in work.rglob("*_시간표.md")}) if work.is_dir() else [])
    sides = [d for d in sides if d.is_dir() and d.name == "영상_자막_기록" and d.parent.name == "_작업"]
    combos = set()
    for d in sides:
        for t in d.glob("*_시간표.md"):
            m = re.search(r"^- 음성 (\S+) · 모델 (\S+) · (?:빠르기 설정 없음|속도 ([\d.]+))", t.read_text(encoding="utf-8"), re.M)
            if m:
                combos.add((m[1], m[2], float(m[3]) if m[3] else tool.ap.get_default("speed")))
    if a.voice:
        combos.add((a.voice, a.model, a.speed))
    if not combos:
        sys.exit("영상 시간표에서 음성 ID를 찾지 못했다 — --voice로 준다")
    texts = {t for f in scripts for _, _, t in tool.slides_text(f)}
    keep = {tool.cache_key(t, *c) for t in texts for c in combos}
    subs = []
    for d in sides:
        for s in sorted(d.glob("*.srt")):
            if any(d.parent.parent.glob(f"*/{s.stem}.mp4")):
                lines = [x for x in s.read_text(encoding="utf-8").splitlines() if x.strip() and not re.fullmatch(r"\d+|[\d:,]+ --> [\d:,]+", x.strip())]
                subs.append(norm("".join(lines)))
    blob = "\0".join(subs)
    cache, bdir = tool.CACHE, tool.HERE / "쉼_저장"
    used_texts, drop = {norm(t) for t in texts}, []
    for h in sorted({p.stem for p in cache.glob("*.mp3")} | {p.stem for p in cache.glob("*.json")}):
        js = cache / f"{h}.json"
        raw = "".join(json.loads(js.read_text(encoding="utf-8")).get("characters") or []) if js.exists() else ""
        text = norm(raw)
        if h in keep or (text and text in blob):
            used_texts.add(text)
        else:
            drop.append((h, " ".join(raw.split())))
    files = [p for h, _ in drop for p in (cache / f"{h}.mp3", cache / f"{h}.json") if p.exists()]
    pauses = []
    for f in sorted(bdir.glob("*.json")):
        sents = json.loads(f.read_text(encoding="utf-8")).get("문장") or []
        if norm("".join(sents)) not in used_texts:
            pauses.append((f, sents[0] if sents else ""))
    for h, text in drop:
        print(f"음성 {h} · {text[:40]}")
    for f, s in pauses:
        print(f"쉼 {f.name} · {s[:40]}")
    mb = sum(p.stat().st_size for p in files) / 1e6
    print(f"안 쓰는 음성 {len(drop)}쌍({mb:.1f} MB) · 쉼 {len(pauses)}개 — 쓰는 것: 대본 {len(scripts)}개(작업/ {len(drafts)} · 준 것 {len(a.scripts)}) × 음성 {len(combos)}벌, mp4가 있는 자막 {len(subs)}개")
    if a.delete:
        for p in files + [f for f, _ in pauses]:
            p.unlink()
        print(f"지웠다: 파일 {len(files) + len(pauses)}개(지운 것은 git 이력에 있다)")
    else:
        print("지우지 않았다. --지우기는 다른 세션이 고치는 대본과 아직 바꿔 끼우지 않은 영상이 모두 커밋된 뒤 pull하고 돌린다")


if a.unused:
    unused()
    sys.exit()

seen = set()
tot_sec = tot_new = tot_ch = 0
for f in a.scripts:
    sec, new, ch, miss = 0, 0, 0, []
    for first, last, text in tool.slides_text(f):
        sec += 1
        h = tool.cache_key(text, a.voice, a.model, a.speed)
        if (tool.CACHE / f"{h}.mp3").exists() and (tool.CACHE / f"{h}.json").exists():
            continue
        if h in seen:
            continue
        seen.add(h)
        new += 1
        ch += len(text)
        miss.append(str(first) if first == last else f"{first}~{last}")
    print(f"{f}: 구획 {sec} · 새로 {new} · 글자 {ch}" + (f" · 장 {', '.join(miss)}" if miss else ""))
    tot_sec += sec
    tot_new += new
    tot_ch += ch
print(f"합계 구획 {tot_sec} · 새로 {tot_new} · 글자 {tot_ch} (음성 {a.voice} · 모델 {a.model} · 빠르기 {a.speed})")
