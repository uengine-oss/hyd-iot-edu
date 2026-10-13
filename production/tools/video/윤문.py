"""낭독 대본을 장 단위로 윤문한다(gpt-6-astra). 원본은 그대로 두고 `…_윤문.md`를 새로 쓴다.

    python3 production/tools/video/윤문.py <대본.md> [...] --env <키 파일>

- 장(`## [SLIDE NN]`)마다 앞뒤 장을 참고로 주고 그 장의 본문만 고쳐 받는다.
- 지시는 상황을 알려 주고 맡기는 방식이다(세세한 문체 규칙을 주지 않는다).
- 검사: 원문의 숫자와 영문·숫자 이름이 모두 남아 있는가, 길이(음절)가 ±8% 안인가, 굵게 표시한 정의 문장의 수가 같은가.
  두 번 해도 통과하지 못한 장은 원문을 그대로 둔다. 결과는 `…_윤문_보고.json`에 남긴다.
"""
import json, os, re, sys, urllib.request, concurrent.futures as cf
from pathlib import Path

args = sys.argv[1:]
env = args[args.index("--env") + 1]; files = [x for x in args if x.endswith(".md")]
KEY = re.search(r"OPENAI_API_KEY=(\S+)", Path(env).read_text()).group(1).strip("\"'")
MODEL = "gpt-6-astra"
RULES = """아래 낭독 대본을 윤문해 주세요. 윤문할 글은 온라인 영상 강의의 낭독 대본입니다.

상황은 이렇습니다. 경남대학교 피지컬AI 사관학교의 제조 AI 과정이고, 듣는 사람은 이 분야를 처음 접하는 대학생들입니다. 공장 설비도, 데이터 시스템도, AI 에이전트도 처음 듣는 학생이 많습니다. 강사는 제조 현장과 AI 시스템을 실제로 만들어 온 업계 전문가입니다. 화면에는 슬라이드가 떠 있고, 강사는 그 슬라이드를 넘기며 말로 설명합니다. 이 대본이 그 말입니다. 강사가 자기 목소리로 녹음한 것처럼 음성으로 만들어져 영상에 들어갑니다.

부탁하는 일은 윤문입니다. 지금 대본은 내용은 맞지만 글로 쓴 티가 나고 AI가 쓴 것처럼 고르게 다듬어져 있습니다. 이것을 실제 사람이 말하는 것처럼 바꿔 주세요. 그 분야를 정말 잘 아는 전문가가, 처음 듣는 학생들이 알아듣게 하려고 애쓰면서 차근차근 말하는 느낌이면 좋겠습니다. 말하다가 한 번 짚어 주고, 헷갈릴 만한 데서는 다시 풀어 주고, 중요한 데서는 힘을 주는, 그런 사람의 말입니다. 아나운서의 낭독이나 교과서 문장이 아닙니다. 그렇다고 가볍거나 유치해지면 안 됩니다. 듣는 사람은 대학생이고, 강사는 전문가입니다.

어떻게 고칠지는 맡기겠습니다. 문장을 나누거나 합쳐도 되고, 순서를 바꿔 말해도 되고, 말투를 바꿔도 됩니다.

지켜야 하는 것은 세 가지뿐입니다.
1. 내용은 그대로입니다. 숫자, 단위, 이름, 정의, 순서와 인과를 바꾸지 않고, 없는 사실이나 예를 새로 만들지 않습니다. HYD-01, TS1, SOP-COOL-11처럼 영문과 숫자로 된 이름은 글자 그대로 두고, `Broker(브로커)`처럼 영문 뒤에 한글 발음을 붙인 표기와 **굵게** 표시한 정의도 남겨 둡니다(이 표기는 음성 제작에 쓰입니다).
2. 길이는 원문과 비슷하게 맞춥니다. 수업 시간에 맞춰 분량을 잡아 둔 대본이라, 눈에 띄게 길어지거나 짧아지면 안 됩니다.
3. 앞 장에서 이어받고 다음 장으로 넘어가는 흐름은 살립니다. 앞뒤 장을 참고로 드립니다.

윤문한 그 장의 본문만 돌려주세요. 제목이나 설명은 붙이지 않습니다."""


def syl(t):
    t = re.sub(r"\*\*", "", t); t = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", t)
    return len(re.findall("[가-힣]", t)) + len(re.findall(r"\d", t)) * 1.6 + len(re.findall("[A-Za-z]", t)) * 0.6


def tokens(t): return set(re.findall(r"[A-Za-z][A-Za-z0-9_\-:.]*[A-Za-z0-9]|\d+(?:[.,]\d+)*", t))


def ask(prev, cur, nxt, retry=None):
    n = len(cur)
    user = (f"[앞 장의 끝 — 참고만]\n{prev[-500:]}\n\n[다음 장의 처음 — 참고만]\n{nxt[:300]}\n\n"
            f"[윤문할 장 — 공백 포함 {n}자. 결과도 {n}자 안팎({int(n*0.95)}~{int(n*1.05)}자)으로 맞춰 주세요]\n{cur}")
    msgs = [{"role": "system", "content": RULES}, {"role": "user", "content": user}]
    if retry:
        msgs += [{"role": "assistant", "content": retry[0]},
                 {"role": "user", "content": f"좋습니다. 다만 {retry[1]} 말맛은 살리고 이 점만 고쳐서 다시 주세요. 분량은 {int(n*0.95)}~{int(n*1.05)}자입니다."}]
    body = {"model": MODEL, "messages": msgs}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def check(o, n):
    miss = tokens(o) - tokens(n); ratio = syl(n) / max(1, syl(o))
    bad = []
    if miss: bad.append("이름이나 숫자가 빠졌습니다(" + ", ".join(sorted(miss)[:6]) + ").")
    if ratio > 1.07: bad.append(f"지금 {len(n)}자로 원문보다 {round((ratio-1)*100)}% 깁니다. 내용은 빼지 말고 되풀이하는 말을 줄여 주세요.")
    if ratio < 0.93: bad.append(f"지금 {len(n)}자로 원문보다 {round((1-ratio)*100)}% 짧습니다. 빠진 설명이 없는지 보고 채워 주세요.")
    if o.count("**") != n.count("**"): bad.append("굵게 표시한 정의 문장의 수가 원문과 다릅니다.")
    return bad


def one(job):
    i, prev, cur, nxt = job
    last, retry = None, None
    for _ in range(4):
        try: new = ask(prev, cur, nxt, retry)
        except Exception as e: last = [f"호출 오류 {e}"]; continue
        last = check(cur, new)
        if not last: return i, new, "통과", []
        retry = (new, " ".join(last))
    return i, cur, "원문 유지", last


for f in files:
    s = Path(f).read_text(encoding="utf-8")
    head, _, tail = s.partition("\n# 촬영 본문 끝")
    parts = re.split(r"(^## \[SLIDE [0-9~]+\].*$)", head, flags=re.M)
    bodies = []
    for k in range(2, len(parts), 2):
        m = re.match(r"(.*?)(\n---\s*\n?(?:\n# \[.*)?\s*|\n# \[.*\s*)?$", parts[k], flags=re.S)
        bodies.append([k, m.group(1).strip() if m else parts[k].strip(), parts[k]])
    jobs = [(j, bodies[j - 1][1] if j else "", b[1], bodies[j + 1][1] if j + 1 < len(bodies) else "") for j, b in enumerate(bodies)]
    report = []
    with cf.ThreadPoolExecutor(6) as ex:
        for i, new, state, why in ex.map(one, jobs):
            k, old, raw = bodies[i]
            parts[k] = raw.replace(old, new, 1) if state == "통과" else raw
            title = re.search(r"\[SLIDE ([0-9~]+)\]", parts[k - 1]).group(1)
            report.append({"장": title, "결과": state, "까닭": why, "원문 음절": round(syl(old)), "윤문 음절": round(syl(new))})
    out = Path(f).with_name(Path(f).stem + "_윤문.md")
    out.write_text("".join(parts) + (("\n# 촬영 본문 끝" + tail) if tail else ""), encoding="utf-8")
    Path(str(out)[:-3] + "_보고.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(r["결과"] == "통과" for r in report)
    print(f"{Path(f).name}: {ok}/{len(report)}장 통과 · 음절 {sum(r['원문 음절'] for r in report)} → {sum(r['윤문 음절'] for r in report)}")
