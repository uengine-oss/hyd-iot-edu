"""실전반 대본이 통합반 원본 대본의 낭독을 빠뜨리지 않았는지 볼 후보를 뽑는다 — 원본 장 범위의 문장마다 실전 대본 장 범위에서 가장 가까운 문장과 유사도를 찍는다. 판정하지 않는다(「없음 후보」는 사람이 받는 장 · 칸이나 뺀 까닭을 대본 제작 확인용에 적는다).
언제: 실전반 대본 단원을 원본(공통 C-4 · 대본 S-14)에서 가져와 시간에 맞춰 줄인 뒤, 검토에 넘기기 전에.
명령: <py> workspace/강의제작/제작도구/검사/원본대조.py <원본 대본> <원본 장 a-b> <실전 대본> <실전 장 a-b> [문턱=0.6]
"""
import difflib, re, sys
from pathlib import Path


def sections(path, lo, hi):
    text = Path(path).read_text(encoding="utf-8")
    heads = list(re.finditer(r"(?m)^## \[SLIDE (\d+)(?:~(\d+))?\][^\n]*$", text))
    out = []
    for i, h in enumerate(heads):
        a = int(h[1])
        if not lo <= a <= hi:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = re.split(r"(?m)^#{1,2} ", text[h.end():end], maxsplit=1)[0]
        lines = [l for l in body.splitlines() if l.strip() and not l.startswith(">") and l.strip() != "---"]
        for s in re.split(r"(?<=[.!?])\s+", " ".join(lines)):
            s = s.strip()
            if len(s) > 4:
                out.append((a, s))
    return out


def norm(s):
    return re.sub(r"[\s,.「」·]", "", s)


def main():
    src, sr, dst, dr = sys.argv[1:5]
    th = float(sys.argv[5]) if len(sys.argv) > 5 else 0.6
    s_lo, s_hi = map(int, sr.split("-"))
    d_lo, d_hi = map(int, dr.split("-"))
    S = sections(src, s_lo, s_hi)
    D = sections(dst, d_lo, d_hi)
    miss = 0
    for a, s in S:
        best, where, bs = 0.0, None, ""
        ns = norm(s)
        for b, t in D:
            r = difflib.SequenceMatcher(None, ns, norm(t)).ratio()
            if r > best:
                best, where, bs = r, b, t
        mark = "있음" if best >= th else "없음 후보"
        miss += best < th
        print(f"[{mark}] 원본 {a}장 · {best:.2f} → 실전 {where}장 | {s}" + ("" if best >= th else f"\n        가장 가까운 실전 문장: {bs}"))
    print(f"합계: 원본 문장 {len(S)} · 없음 후보 {miss} (문턱 {th})")


main()
