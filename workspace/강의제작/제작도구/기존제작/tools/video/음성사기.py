"""이론 대본의 음성만 먼저 산다(영상 · 쉼 · 강조 없음). 강의영상.py의 slides_text · cache_key · tts를 그대로 불러 쓴다. 유료다.
언제: 음성견적.py로 견적을 알린 뒤, 굽기 전에 음성 캐시를 채울 때. 대표 1구획을 먼저 사서(--한도 1) 단가를 잰다.
명령: ELEVENLABS_API_KEY=… <py> workspace/강의제작/제작도구/기존제작/tools/video/음성사기.py <기록.json> <대본 …> --voice <음성 ID> [--한도 N] [--상한 크레딧] [--동시 N]

- 캐시(음성_저장/의 mp3 · json 둘 다)가 있는 구획은 사지 않는다(기록에 credits 0 · 기존). 살 구획이 없으면 키 없이도 끝난다.
- 기록 JSON은 강의영상.py --audio-ledger 꼴({"voice", "completed": {캐시 이름: {"sha", "credits", …}}})이라 그대로 렌더에 넘긴다.
- 실패하면 다시 보내지 않고 새 요청을 멈춘다(영상.md V-4). 실패는 기록의 failed에 남는다.
- 상한: 응답 머리의 character-cost 합 + 다음 글자 수 × 0.6이 상한을 넘으면 그 앞에서 멈춘다.
- 음성 ID는 꼭 준다. 캐시 이름에 들어가고 강의영상.py에도 기본값이 없다(영상.md V-4).
"""
import argparse, hashlib, json, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
import 강의영상 as tool  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("ledger"); ap.add_argument("scripts", nargs="+")
ap.add_argument("--voice", required=True)
ap.add_argument("--한도", dest="limit", type=int, default=0, help="이번에 새로 살 구획 수(0 = 전부)")
ap.add_argument("--상한", dest="cap", type=int, default=80000)
ap.add_argument("--동시", dest="workers", type=int, default=1)
a = ap.parse_args()
tool.a.voice = a.voice   # 모델 · 빠르기는 도구 기본값(eleven_v4 · 0.8) 그대로
tool.CACHE.mkdir(exist_ok=True)
L = Path(a.ledger)
led = json.loads(L.read_text(encoding="utf-8")) if L.exists() else {"voice": a.voice, "model": tool.a.model, "speed": tool.a.speed, "completed": {}, "failed": []}
if (led["voice"], led["model"], led["speed"]) != (a.voice, tool.a.model, tool.a.speed): sys.exit("기록의 음성 · 모델 · 빠르기가 지금과 다르다")
lock, stop = threading.Lock(), threading.Event()


def save():
    tmp = L.with_suffix(".tmp"); tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8"); tmp.replace(L)


jobs, seen = [], set()
for f in a.scripts:
    S = tool.slides_text(f); name = Path(f).resolve(); name = f"{name.parents[3].name}_{name.parents[1].name}_{name.stem}"
    for i, (first, last, t) in enumerate(S):
        h = tool.cache_key(t, a.voice, tool.a.model, tool.a.speed)
        if h in seen: continue
        seen.add(h)
        sl = str(first) if first == last else f"{first}~{last}"
        mp3, js = tool.CACHE / f"{h}.mp3", tool.CACHE / f"{h}.json"
        if mp3.exists() and js.exists():
            led["completed"].setdefault(h, {"sha": hashlib.sha256(mp3.read_bytes()).hexdigest(), "credits": 0, "편": name, "장": sl, "글자": len(t), "기존": True})
            continue
        jobs.append((name, sl, h, t, S[i - 1][2] if i else "", S[i + 1][2] if i + 1 < len(S) else ""))
save()
if a.limit: jobs = jobs[:a.limit]
if jobs and not tool.key(): sys.exit(f"새로 살 구획이 {len(jobs)}개인데 ELEVENLABS_API_KEY가 없다")
spent = sum(v["credits"] for v in led["completed"].values() if not v.get("기존"))
print(f"새로 살 구획 {len(jobs)} · 글자 {sum(len(j[3]) for j in jobs)} · 기록의 지출 {spent}", flush=True)
reserved = 0


def one(job):
    global spent, reserved
    name, sl, h, t, prev, nxt = job
    with lock:
        if stop.is_set(): return
        if spent + reserved + len(t) * 0.6 > a.cap:
            print(f"상한 {a.cap}에 닿아 멈춘다(지출 {spent}, 진행 중 예약 {reserved:.0f}, 다음 {len(t)}자)", flush=True); stop.set(); return
        reserved += len(t) * 0.6
    t0 = time.time()
    try:
        mp3, _, cost = tool.tts(t, prev, nxt)
        ok = (tool.CACHE / f"{h}.json").exists()
        err = None if ok else "json이 없다"
    except BaseException as e:   # tts는 HTTP 오류에 sys.exit를 부른다
        ok, cost, err = False, 0, f"{type(e).__name__}: {e}"[:400]
    with lock:
        reserved -= len(t) * 0.6
        if ok:
            spent += cost
            led["completed"][h] = {"sha": hashlib.sha256(mp3.read_bytes()).hexdigest(), "credits": cost, "편": name, "장": sl, "글자": len(t), "초": round(time.time() - t0, 1)}
            print(f"샀다 {name} 장 {sl} · {len(t)}자 · {cost}크레딧 · {time.time() - t0:.1f}초 · 누계 {spent}", flush=True)
        else:
            led["failed"].append({"편": name, "장": sl, "캐시": h, "글자": len(t), "오류": err, "시각": time.strftime("%H:%M:%S")})
            print(f"실패 {name} 장 {sl}: {err} — 새 요청을 멈춘다(다시 보내지 않는다)", flush=True); stop.set()
        save()


with ThreadPoolExecutor(a.workers) as ex:
    list(ex.map(one, jobs))
print(f"끝 · 이번 기록 지출 합 {spent} · 실패 {len(led['failed'])} · 기록 {len(led['completed'])}구획", flush=True)
sys.exit(1 if led["failed"] or stop.is_set() and not all(j[2] in led["completed"] for j in jobs) else 0)
