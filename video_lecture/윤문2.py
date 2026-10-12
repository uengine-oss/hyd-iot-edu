"""1차 윤문본(`…_윤문.md`)을 한 번 더 다듬는다(gpt-6-astra, Codex 계정으로 부른다). 결과는 `…_윤문2.md`.

    python3 video_lecture/윤문2.py <…_윤문.md> [--slides 첫장 끝장] [--out 폴더]

- 1차와 목적이 다르다. 내용을 더하지 않고, 이미 있는 말과 말 사이가 더 자연스럽게 이어지게 한다. 그만큼 길이는 조금 늘어도 된다(4~5% 안팎). 억지로 늘리지 않는다.
- OpenAI API 키를 쓰지 않는다. 이 PC에 로그인된 Codex(ChatGPT 계정)를 `npx @openai/codex exec`로 부른다.
- 검사: 1차 윤문본의 숫자와 영문·숫자 이름이 모두 남아 있는가, 굵게 표시한 수와 문단 수가 같은가, 길이가 -1%~+9% 안인가(늘지 않은 장은 그대로 받는다).
  네 번 해도 통과하지 못한 장은 1차 윤문본을 그대로 둔다. 결과는 `…_윤문2_보고.json`에 남긴다.
"""
import json, re, subprocess, sys, tempfile, concurrent.futures as cf
from pathlib import Path

args = sys.argv[1:]
files = [x for x in args if x.endswith(".md")]
FIRST, LAST = (int(args[args.index("--slides") + 1]), int(args[args.index("--slides") + 2])) if "--slides" in args else (0, 10**6)
OUTDIR = Path(args[args.index("--out") + 1]) if "--out" in args else None
CODEX = ["npx", "-y", "@openai/codex@0.162.1", "exec", "-m", "gpt-6-astra", "--skip-git-repo-check", "-s", "read-only",
         "-c", "model_reasoning_effort=medium"]
RULES = """아래 낭독 대본의 한 장을 한 번 더 다듬어 주세요. 파일을 읽거나 명령을 실행할 필요는 없습니다. 이 글만 보고 답하면 됩니다.

상황은 이렇습니다. 경남대학교 피지컬AI 사관학교의 제조 AI 과정, 온라인 영상 강의의 낭독 대본입니다. 듣는 사람은 이 분야를 처음 접하는 대학생이고, 강사는 제조 현장과 AI 시스템을 실제로 만들어 온 업계 전문가입니다. 화면에는 슬라이드가 떠 있고, 강사가 그 슬라이드를 넘기며 말로 설명합니다. 이 대본이 그 말이고, 강사의 목소리로 음성이 만들어져 영상에 들어갑니다.

이 대본은 이미 한 번 윤문을 거쳤습니다. 내용도 맞고 말투도 말하는 투입니다. 그런데 들어 보면 문장 하나하나는 괜찮은데 문장과 문장이 아직 따로따로 놓여 있습니다. 한 문장이 끝나고 다음 문장이 그냥 시작됩니다. 사람은 그렇게 말하지 않습니다. 앞에서 한 말을 받아서 다음 말로 넘어가고, 방금 말한 것이 왜 다음 이야기로 이어지는지를 말로 이어 줍니다. 물음을 던졌으면 그 물음을 받아서 답을 꺼내고, 여러 가지를 늘어놓았으면 하나씩 짚어 가며 넘어갑니다.

부탁하는 일은 그 이음매를 살리는 것입니다. 이미 있는 내용과 내용 사이가 자연스럽게 이어지도록 다듬어 주세요. 그러다 보면 글이 조금 길어질 텐데, 그래도 됩니다. 지금보다 4~5%쯤 길어지는 것이 알맞습니다. 다만 억지로 늘리지는 마세요. 이을 데가 많지 않은 장은 조금만 늘거나 거의 그대로여도 괜찮습니다. 길이를 채우는 것보다 자연스러운 것이 먼저입니다.

늘어나는 말은 이음매여야 합니다. 새 내용이 아닙니다.
- 새 사실, 새 예, 새 비유, 새 숫자, 새 이름을 넣지 않습니다. 대본에 없는 것은 말하지 않습니다.
- 같은 말을 되풀이해서 늘리지 않습니다. "정말", "굉장히" 같은 군말로 늘리지도 않습니다.
- 가볍거나 유치해지면 안 됩니다. 듣는 사람은 대학생이고 강사는 전문가입니다.
- 이미 자연스럽게 이어지는 곳은 그대로 둡니다. 모든 문장을 고칠 필요는 없습니다.

지켜야 하는 것:
1. 내용은 그대로입니다. 숫자, 단위, 이름, 정의, 순서와 인과를 바꾸지 않습니다. HYD-01, TS1처럼 영문과 숫자로 된 이름은 글자 그대로 두고, `Broker(브로커)`처럼 영문 뒤에 한글 발음을 붙인 표기와 **굵게** 표시한 곳도 그대로 둡니다(음성 제작에 쓰입니다).
2. 문단 나눔(빈 줄)은 지금 자리를 따릅니다. 문단은 말이 한 단락 끝나는 자리입니다.
3. 앞 장에서 이어받고 다음 장으로 넘어가는 흐름을 살립니다. 앞뒤 장을 참고로 드립니다.

다듬은 그 장의 본문만 답해 주세요. 제목, 설명, 따옴표, 코드 블록을 붙이지 않습니다."""


def syl(t):
    t = re.sub(r"\*\*", "", t); t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return len(re.findall("[가-힣]", t)) + len(re.findall(r"\d", t)) * 1.6 + len(re.findall("[A-Za-z]", t)) * 0.6


def tokens(t): return set(re.findall(r"[A-Za-z][A-Za-z0-9_\-:.]*[A-Za-z0-9]|\d+(?:[.,]\d+)*", t))


def ask(prev, cur, nxt, retry=None):
    n = len(cur)
    p = (f"{RULES}\n\n[앞 장의 끝 — 참고만]\n{prev[-500:]}\n\n[다음 장의 처음 — 참고만]\n{nxt[:300]}\n\n"
         f"[다듬을 장 — 공백 포함 {n}자. 결과는 {int(n*1.03)}~{int(n*1.06)}자쯤이 알맞고, 자연스러움이 먼저입니다]\n{cur}")
    if retry: p += f"\n\n[앞서 주신 답]\n{retry[0]}\n\n좋습니다. 다만 {retry[1]} 이 점만 고쳐서 다시 주세요."
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.txt"
        r = subprocess.run(CODEX + ["-o", str(out), "-"], input=p, text=True, capture_output=True, cwd=d, timeout=900)
        if not out.exists(): raise RuntimeError(" ".join(re.findall(r'"message":"([^"]+)"', r.stdout + r.stderr)[-1:]) or "답이 오지 않음")
        return out.read_text(encoding="utf-8").strip()


def check(o, n):
    miss = tokens(o) - tokens(n); extra = tokens(n) - tokens(o); ratio = syl(n) / max(1, syl(o)); bad = []
    if miss: bad.append("이름이나 숫자가 빠졌습니다(" + ", ".join(sorted(miss)[:6]) + ").")
    if extra: bad.append("대본에 없던 이름이나 숫자가 들어갔습니다(" + ", ".join(sorted(extra)[:6]) + "). 빼 주세요.")
    if ratio > 1.09: bad.append(f"지금 {len(n)}자로 {round((ratio-1)*100)}% 길어졌습니다. 이음매가 아닌 말을 덜어 4~5% 안팎으로 맞춰 주세요.")
    if ratio < 0.99: bad.append(f"지금 {len(n)}자로 원래보다 짧아졌습니다. 빠진 말이 없는지 보고 다시 주세요.")
    if o.count("**") != n.count("**"): bad.append("굵게 표시한 곳의 수가 달라졌습니다.")
    if o.count("\n\n") != n.count("\n\n"): bad.append(f"문단 수가 달라졌습니다(원래 {o.count(chr(10)*2)+1}문단). 문단 나눔은 그대로 두세요.")
    return bad


def one(job):
    i, prev, cur, nxt = job
    last, retry = None, None
    for _ in range(4):
        try: new = ask(prev, cur, nxt, retry)
        except Exception as e: last = [f"호출 오류 {str(e)[:80]}"]; continue
        last = check(cur, new)
        if not last: return i, new, "통과", []
        retry = (new, " ".join(last))
    return i, cur, "1차 유지", last


for f in files:
    s = Path(f).read_text(encoding="utf-8")
    head, _, tail = s.partition("\n# 촬영 본문 끝")
    parts = re.split(r"(^## \[SLIDE [0-9~]+\].*$)", head, flags=re.M)
    bodies = []
    for k in range(2, len(parts), 2):
        m = re.match(r"(.*?)(\n---\s*\n?(?:\n# \[.*)?\s*|\n# \[.*\s*)?$", parts[k], flags=re.S)
        no = re.search(r"\[SLIDE ([0-9~]+)\]", parts[k - 1]).group(1)
        bodies.append([k, m.group(1).strip() if m else parts[k].strip(), parts[k], no])
    jobs = [(j, bodies[j - 1][1] if j else "", b[1], bodies[j + 1][1] if j + 1 < len(bodies) else "")
            for j, b in enumerate(bodies) if FIRST <= int(b[3].split("~")[0]) and int(b[3].split("~")[-1]) <= LAST]
    report = []
    with cf.ThreadPoolExecutor(4) as ex:
        for i, new, state, why in ex.map(one, jobs):
            k, old, raw, no = bodies[i]
            parts[k] = raw.replace(old, new, 1) if state == "통과" else raw
            report.append({"장": no, "결과": state, "까닭": why, "1차 음절": round(syl(old)), "2차 음절": round(syl(new))})
    name = Path(f).name.replace("_윤문.md", "_윤문2.md")
    out = (OUTDIR or Path(f).parent) / name; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts) + (("\n# 촬영 본문 끝" + tail) if tail else ""), encoding="utf-8")
    Path(str(out)[:-3] + "_보고.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(r["결과"] == "통과" for r in report); a, b = sum(r["1차 음절"] for r in report), sum(r["2차 음절"] for r in report)
    print(f"{Path(f).name}: {ok}/{len(report)}장 통과 · 음절 {a} → {b} ({(b/max(1,a)-1)*100:+.1f}%)")
