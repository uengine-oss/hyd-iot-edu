"""촬영 대본(정본)에서 읽을 문장만 뽑아 낭독본을 만든다.

    python3 만들기/tools/deck/낭독본.py <대본.md> <낭독본.md>

- 정본의 안내 · 구성표 · 단원 머리(`# [이론] …`) · 블록 표시 줄(`> [핵심]` 등) · 굵게 표시 · `제작 확인용` 절은 뺀다.
- 장마다 `## [SLIDE NN] 제목`과 그 아래 문단만 남긴다. 정본을 고치면 이 도구로 다시 뽑는다(낭독본은 손으로 고치지 않는다).
"""
import re
import sys


def main() -> None:
    src, out = sys.argv[1], sys.argv[2]
    text = open(src, encoding="utf-8").read()
    title = re.match(r"# (.+?) — ", text)
    if not title:
        sys.exit(f"{src}:1: 첫 줄이 '# <회차> — 촬영 대본' 꼴이 아니다")
    body = re.split(r"^# (?:여기까지 작성|촬영 본문 끝)|^## 제작 확인용", text, flags=re.M)[0]
    slides = re.split(r"^(?=## \[SLIDE )", body, flags=re.M)[1:]
    if not slides:
        sys.exit(f"{src}: '## [SLIDE NN]' 머리가 하나도 없다")
    parts = [f"# {title.group(1)} — 낭독 대본\n"]
    for block in slides:
        head, _, rest = block.partition("\n")
        paras = []
        for line in rest.splitlines():
            if line.startswith((">", "# ", "---")):
                continue
            paras.append(line.replace("**", "").rstrip())
        joined = re.sub(r"\n{3,}", "\n\n", "\n".join(paras)).strip()
        if not joined:
            sys.exit(f"{src}: {head.strip()} 아래에 읽을 문장이 없다")
        parts.append(f"{head.strip()}\n\n{joined}\n")
    open(out, "w", encoding="utf-8").write("\n".join(parts))
    print(f"{out}: {len(slides)}장")


if __name__ == "__main__":
    main()
