"""짝 덱에서 한쪽만 고친 곳 후보: 지우거나 바꾼 낭독 문장이 짝 덱 현재 대본에 글자 그대로 남아 있는지 잰다(판정은 사람이 한다)."""
import glob
import json
import re
import sys

W = sys.argv[1]
PAIR = {"통합반_02": ["실전반_02"], "통합반_03": ["실전반_02", "실전반_03"], "통합반_04": ["실전반_03"], "실전반_02": ["통합반_02", "통합반_03"], "실전반_03": ["통합반_03", "통합반_04"]}


def sents(t):
    t = re.sub(r"\s+", " ", t.replace("\r", " ").replace("\n", " "))
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", t) if len(s.strip()) >= 25]


def narration(name):
    c, n = name.split("_")
    out = {}
    for p in sorted(glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md")):
        slide = None
        for line in open(p, encoding="utf8"):
            m = re.match(r"## \[SLIDE (\d+)", line)
            if m:
                slide = int(m.group(1))
            elif line.startswith("#"):
                slide = None
            elif slide and line.strip() and not line.startswith((">", "|", "---")):
                for s in sents(line):
                    out.setdefault(s, []).append(slide)
    return out


res = {}
for a, others in PAIR.items():
    items = json.load(open(f"{W}/점검/{a}.json", encoding="utf8"))["고칠것"]
    verdict = json.load(open(f"{W}/판정/{a}.json", encoding="utf8"))["판정"]
    for it in items:
        if verdict[it["번호"]]["처리"] == "보류" or not it.get("전") or it["종류"] in ("순서", "나열순서"):
            continue
        after = set(sents(verdict[it["번호"]].get("후", it.get("후") or "")))
        removed = [s for s in sents(it["전"]) if s not in after]
        for b in others:
            nb = narration(b) if b not in res else res[b]
            res[b] = nb
            for s in removed:
                if s in nb:
                    print(f"{it['번호']} {a} 장{it['장']} ↔ {b} 장{nb[s]}: {s[:110]}")
