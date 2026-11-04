"""옛 PPTX와 새 PPTX를 장별로 견준다: 옛 판에만 · 새 판에만 있는 화면, 같은 화면의 위치가 바뀌었는지. 읽기만 한다.
언제: 덱을 다시 조립한 뒤(특히 오프라인) 손으로 다듬은 곳을 잃지 않았는지 볼 때.
명령: <py> workspace/강의제작/제작도구/검사/옛판비교.py <옛.pptx> <새.pptx>
"""
import re, sys
from pptx import Presentation


def read(p):
    out = []
    for s in Presentation(p).slides:
        items = sorted((sh.left or 0, sh.top or 0, sh.width or 0, sh.height or 0, sh.text_frame.text if sh.has_text_frame else "") for sh in s.shapes)
        out.append(items)
    return out


def key(items):
    return tuple(i[4] for i in items if i[4] and not re.fullmatch(r"\d+", i[4].strip()))


def title(items):
    t = [i[4] for i in items if i[4]]
    return t[0][:30] if t else ""


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = read(sys.argv[1]), read(sys.argv[2])
    ka, kb = [key(x) for x in a], [key(x) for x in b]
    print(len(a), "→", len(b))
    print("옛 판에만 있는 화면(장):", [(i + 1, title(a[i])) for i, k in enumerate(ka) if k not in set(kb)])
    print("새 판에만 있는 화면(장):", [i + 1 for i, k in enumerate(kb) if k not in set(ka)])
    moved = 0
    for i, k in enumerate(kb):
        if k in set(ka):
            j = ka.index(k)
            pa = sorted(x[:4] for x in a[j] if x[4] and not re.fullmatch(r"\d+", x[4].strip()))
            pb = sorted(x[:4] for x in b[i] if x[4] and not re.fullmatch(r"\d+", x[4].strip()))
            moved += pa != pb
            print(f"  같은 화면: 새 {i + 1} = 옛 {j + 1}", "위치 같음" if pa == pb else "위치 다름")
    print("위치 다른 장 수", moved)


if __name__ == "__main__":
    main()
