"""1차 윤문본(`…_윤문.md`)을 한 번 더 다듬는다(gpt-6-astra, OpenAI API 키로 부른다). 결과는 `…_윤문2.md`.

    python3 video_lecture/윤문2.py --env <키 파일> <…_윤문.md> [--slides 첫장 끝장] [--out 폴더] [--rowfirst-only]

- 1차와 목적이 다르다. 내용을 더하지 않고, 이미 있는 말과 말 사이가 더 자연스럽게 이어지게 한다. 그만큼 길이는 조금 늘어도 된다(4~5% 안팎). 억지로 늘리지 않는다.
- `--env` 파일의 OPENAI_API_KEY로 OpenAI API를 부른다. Codex(ChatGPT 계정)로는 부르지 않는다. 이 키와 gpt-6-astra는 윤문에만 쓴다.
- 장마다 그 일차의 틀(영상 목록, 이 장이 어느 영상의 몇 번째 장인지, 같은 영상 안의 앞뒤 장)을 함께 준다. 영상은 실라버스 행마다 따로 재생되므로, 영상의 첫 장은 앞 영상의 말을 받지 않게 한다.
- 검사: 1차 윤문본의 숫자와 영문·숫자 이름이 모두 남아 있는가, 굵게 표시한 수와 문단 수가 같은가, 길이가 -1%~+9% 안인가(늘지 않은 장은 그대로 받는다).
  네 번 해도 통과하지 못한 장은 1차 윤문본을 그대로 둔다. 결과는 `…_윤문2_보고.json`에 남긴다.
"""
import json, re, sys, urllib.request, concurrent.futures as cf
from pathlib import Path

args = sys.argv[1:]
files = [x for x in args if x.endswith(".md")]
FIRST, LAST = (int(args[args.index("--slides") + 1]), int(args[args.index("--slides") + 2])) if "--slides" in args else (0, 10**6)
OUTDIR = Path(args[args.index("--out") + 1]) if "--out" in args else None
ROWFIRST = "--rowfirst-only" in args   # 이미 만든 2차 윤문본에서, 영상이 시작되는 장(실라버스 행의 첫 장)만 다시 받는다
if "--env" not in args: sys.exit("--env <키 파일> 이 필요하다(OPENAI_API_KEY). 저장소의 .env는 쓰지 않는다.")
KEY = re.search(r"OPENAI_API_KEY=(\S+)", Path(args[args.index("--env") + 1]).read_text()).group(1).strip("\"'")
MODEL = "gpt-6-astra"
RULES = """아래 낭독 대본의 한 장을 한 번 더 다듬어 주세요.

상황은 이렇습니다. 경남대학교 피지컬AI 사관학교의 제조 AI 과정, 온라인 영상 강의의 낭독 대본입니다. 듣는 사람은 이 분야를 처음 접하는 대학생이고, 강사는 제조 현장과 AI 시스템을 실제로 만들어 온 업계 전문가입니다. 화면에는 슬라이드가 떠 있고, 강사가 그 슬라이드를 넘기며 말로 설명합니다. 이 대본이 그 말이고, 강사의 목소리로 음성이 만들어져 영상에 들어갑니다.

이 대본은 이미 한 번 윤문을 거쳤습니다. 내용도 맞고 말투도 말하는 투입니다. 그런데 들어 보면 문장 하나하나는 괜찮은데 문장과 문장이 아직 따로따로 놓여 있습니다. 한 문장이 끝나고 다음 문장이 그냥 시작됩니다. 사람은 그렇게 말하지 않습니다. 앞에서 한 말을 받아서 다음 말로 넘어가고, 방금 말한 것이 왜 다음 이야기로 이어지는지를 말로 이어 줍니다. 물음을 던졌으면 그 물음을 받아서 답을 꺼내고, 여러 가지를 늘어놓았으면 하나씩 짚어 가며 넘어갑니다.

부탁하는 일은 그 이음매를 살리는 것입니다. 이미 있는 내용과 내용 사이가 자연스럽게 이어지도록 다듬어 주세요. 그러다 보면 글이 조금 길어질 텐데, 그래도 됩니다. 지금보다 4~5%쯤 길어지는 것이 알맞습니다. 다만 억지로 늘리지는 마세요. 이을 데가 많지 않은 장은 조금만 늘거나 거의 그대로여도 괜찮습니다. 길이를 채우는 것보다 자연스러운 것이 먼저입니다.

늘어나는 말은 이음매여야 합니다. 새 내용이 아닙니다.
- 새 사실, 새 예, 새 비유, 새 숫자, 새 이름을 넣지 않습니다. 대본에 없는 것은 말하지 않습니다.
- 같은 말을 되풀이해서 늘리지 않습니다. "정말", "굉장히" 같은 군말로 늘리지도 않습니다.
- 가볍거나 유치해지면 안 됩니다. 듣는 사람은 대학생이고 강사는 전문가입니다.
- 이미 자연스럽게 이어지는 곳은 그대로 둡니다. 모든 문장을 고칠 필요는 없습니다.
- 같은 이음말을 가까운 문장에서 되풀이하지 않습니다.

지켜야 하는 것:
1. 내용은 그대로입니다. 숫자, 단위, 이름, 정의, 순서와 인과를 바꾸지 않습니다. HYD-01, TS1처럼 영문과 숫자로 된 이름은 글자 그대로 두고, `Broker(브로커)`처럼 영문 뒤에 한글 발음을 붙인 표기와 **굵게** 표시한 곳도 그대로 둡니다(음성 제작에 쓰입니다).
2. 문단 나눔(빈 줄)은 지금 자리를 따릅니다. 문단은 말이 한 단락 끝나는 자리입니다.
3. 같은 영상 안에서는 앞 장에서 이어받고 다음 장으로 넘어가는 흐름을 살립니다. 영상이 바뀌는 자리에서는 앞 영상의 말을 받지 않습니다. 이 장이 어느 영상의 몇 번째 장인지, 앞뒤에 무엇이 있는지를 아래에 드립니다.

다듬은 그 장의 본문만 답해 주세요. 제목, 설명, 따옴표, 코드 블록을 붙이지 않습니다."""


def syl(t):
    t = re.sub(r"\*\*", "", t); t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return len(re.findall("[가-힣]", t)) + len(re.findall(r"\d", t)) * 1.6 + len(re.findall("[A-Za-z]", t)) * 0.6


def tokens(t): return set(re.findall(r"[A-Za-z][A-Za-z0-9_\-:.]*[A-Za-z0-9]|\d+(?:[.,]\d+)*", t))


OPENERS = r"^(그럼|그러면|그래서|그러니까|자|이제|이어서|다음으로|그리고)[ ,]"


def day_frame(f):
    """그 일차의 모든 대본 파일을 읽어 영상(실라버스 행)과 장의 틀을 만든다: [{no, row, text}], 행 제목 목록."""
    d = Path(f).parent; day = re.search(r"통합반_(\d\d)일차", Path(f).name).group(1)
    fs = sorted([x for x in d.glob(f"통합반_{day}일차_대본*_윤문.md")], key=lambda x: (len(x.name), x.name))
    slides, rows, row = [], [], None
    for x in fs:
        t = x.read_text(encoding="utf-8").partition("\n# 촬영 본문 끝")[0]
        ps = re.split(r"^(# \[.*|## \[SLIDE [0-9~]+\].*)$", t, flags=re.M)
        for i in range(1, len(ps), 2):
            h = ps[i]
            if h.startswith("# ["):
                if "이어짐" not in h: row = re.sub(r"\s*\(대본은[^)]*\)", "", h[2:].strip()); rows.append(row)
                continue
            body = re.sub(r"^---\s*$|^>.*$", "", ps[i + 1], flags=re.M).strip()
            slides.append({"no": re.search(r"\[SLIDE ([0-9~]+)\]", h).group(1), "row": row, "text": body})
    return slides, rows


def frame_text(slides, rows, no):
    """이 장이 어느 영상의 몇 번째 장인지, 앞뒤에 무엇이 있는지를 글로 만든다. (글, 영상의 첫 장인가)"""
    i = next(k for k, x in enumerate(slides) if x["no"] == no); me = slides[i]
    mine = [k for k, x in enumerate(slides) if x["row"] == me["row"]]; pos = mine.index(i); r = rows.index(me["row"]) if me["row"] in rows else 0
    lines = ["[이 대본의 틀]", "이 일차의 강의는 영상 여러 편으로 나뉘어 있습니다. 아래 목록의 한 줄이 영상 한 편이고, 영상은 한 편씩 따로 재생됩니다."]
    lines += [f"{k+1}. {t}" + ("   ← 지금 다듬는 장이 든 영상" if k == r else "") for k, t in enumerate(rows)]
    lines += ["", f"[이 장의 자리] 이 영상은 장 {len(mine)}개로 되어 있고, 지금 다듬는 장은 그 가운데 {pos+1}번째입니다."]
    first = pos == 0; last = pos == len(mine) - 1
    if first:
        lines.append("이 장에서 영상이 새로 시작합니다. 듣는 사람에게는 이 장의 첫 문장이 영상의 첫마디입니다. 바로 앞에 한 말이 없으니, "
                     "「그럼」「그러면」「그래서」「자」「이제」「이어서」처럼 앞의 말을 받는 낱말로 열지 않습니다. "
                     + (f"앞 영상은 「{rows[r-1]}」이었습니다. 원문이 앞 영상의 내용을 짚으며 시작한다면 그 연결은 살리되, 방금 한 말을 잇는 투가 아니라 지난 영상을 떠올려 주는 투로 씁니다." if r > 0 else "이 영상이 그날의 첫 영상입니다."))
    else:
        lines += ["", "[앞 장의 끝 — 참고만. 같은 영상 안에서 바로 앞에 한 말입니다]", slides[i - 1]["text"][-500:]]
    if last:
        lines += ["", "이 장이 이 영상의 마지막 장입니다. " + (f"다음 영상은 「{rows[r+1]}」입니다. 원문이 다음으로 넘기는 말로 끝난다면 그 말은 살립니다." if r + 1 < len(rows) else "이 영상이 그날의 마지막 영상입니다.")]
    else:
        lines += ["", "[다음 장의 처음 — 참고만. 같은 영상 안에서 바로 이어질 말입니다]", slides[i + 1]["text"][:300]]
    return "\n".join(lines), first


def ask(ctx, cur, retry=None):
    n = len(cur)
    p = (f"{RULES}\n\n{ctx}\n\n"
         f"[다듬을 장 — 공백 포함 {n}자. 결과는 {int(n*1.03)}~{int(n*1.06)}자쯤이 알맞고, 자연스러움이 먼저입니다]\n{cur}")
    if retry: p += f"\n\n[앞서 주신 답]\n{retry[0]}\n\n좋습니다. 다만 {retry[1]} 이 점만 고쳐서 다시 주세요."
    body = {"model": MODEL, "messages": [{"role": "user", "content": p}]}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def check(o, n, first=False):
    miss = tokens(o) - tokens(n); extra = tokens(n) - tokens(o); ratio = syl(n) / max(1, syl(o)); bad = []
    if miss: bad.append("이름이나 숫자가 빠졌습니다(" + ", ".join(sorted(miss)[:6]) + ").")
    if extra: bad.append("대본에 없던 이름이나 숫자가 들어갔습니다(" + ", ".join(sorted(extra)[:6]) + "). 빼 주세요.")
    if ratio > 1.09: bad.append(f"지금 {len(n)}자로 {round((ratio-1)*100)}% 길어졌습니다. 이음매가 아닌 말을 덜어 4~5% 안팎으로 맞춰 주세요.")
    if ratio < 0.99: bad.append(f"지금 {len(n)}자로 원래보다 짧아졌습니다. 빠진 말이 없는지 보고 다시 주세요.")
    if first and re.match(OPENERS, n.strip()): bad.append("영상의 첫 문장이 앞의 말을 받는 낱말로 시작합니다. 영상이 여기서 시작하니 그 낱말 없이 바로 시작해 주세요.")
    if o.count("**") != n.count("**"): bad.append("굵게 표시한 곳의 수가 달라졌습니다.")
    if o.count("\n\n") != n.count("\n\n"): bad.append(f"문단 수가 달라졌습니다(원래 {o.count(chr(10)*2)+1}문단). 문단 나눔은 그대로 두세요.")
    return bad


def one(job):
    i, ctx, cur, first = job
    last, retry = None, None
    for _ in range(4):
        try: new = ask(ctx, cur, retry)
        except Exception as e: last = [f"호출 오류 {str(e)[:80]}"]; continue
        last = check(cur, new, first)
        if not last: return i, new, "통과", []
        retry = (new, " ".join(last))
    return i, cur, "1차 유지", last


for f in files:
    s = Path(f).read_text(encoding="utf-8")
    head, _, tail = s.partition("\n# 촬영 본문 끝")
    parts = re.split(r"(^## \[SLIDE [0-9~]+\].*$)", head, flags=re.M)
    bodies = []; SL, ROWS = day_frame(f)
    for k in range(2, len(parts), 2):
        m = re.match(r"(.*?)(\n---\s*\n?(?:\n# \[.*)?\s*|\n# \[.*\s*)?$", parts[k], flags=re.S)
        no = re.search(r"\[SLIDE ([0-9~]+)\]", parts[k - 1]).group(1)
        ctx, first = frame_text(SL, ROWS, no)
        bodies.append([k, m.group(1).strip() if m else parts[k].strip(), parts[k], no, first, ctx])
    jobs = [(j, b[5], b[1], b[4]) for j, b in enumerate(bodies)
            if FIRST <= int(b[3].split("~")[0]) and int(b[3].split("~")[-1]) <= LAST and (b[4] or not ROWFIRST)]
    name = Path(f).name.replace("_윤문.md", "_윤문2.md")
    out = (OUTDIR or Path(f).parent) / name; out.parent.mkdir(parents=True, exist_ok=True)
    if ROWFIRST and out.exists():   # 이미 있는 2차 윤문본에서 영상의 첫 장만 다시 받는다
        old2 = re.split(r"(^## \[SLIDE [0-9~]+\].*$)", out.read_text(encoding="utf-8").partition("\n# 촬영 본문 끝")[0], flags=re.M)
        if len(old2) == len(parts): keep = {j for j, _ in enumerate(bodies)} - {j[0] for j in jobs}; parts = [old2[x] if any(bodies[j][0] == x for j in keep) else parts[x] for x in range(len(parts))]
    report = []
    with cf.ThreadPoolExecutor(4) as ex:
        for i, new, state, why in ex.map(one, jobs):
            k, old, raw, no = bodies[i][:4]
            parts[k] = raw.replace(old, new, 1) if state == "통과" else raw
            report.append({"장": no, "결과": state, "까닭": why, "1차 음절": round(syl(old)), "2차 음절": round(syl(new))})
    out.write_text("".join(parts) + (("\n# 촬영 본문 끝" + tail) if tail else ""), encoding="utf-8")
    Path(str(out)[:-3] + ("_보고_첫장.json" if ROWFIRST else "_보고.json")).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(r["결과"] == "통과" for r in report); a, b = sum(r["1차 음절"] for r in report), sum(r["2차 음절"] for r in report)
    print(f"{Path(f).name}: {ok}/{len(report)}장 통과 · 음절 {a} → {b} ({(b/max(1,a)-1)*100:+.1f}%)")
