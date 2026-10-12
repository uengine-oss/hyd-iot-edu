"""대본 MD의 낭독 시간을 장별로 어림한다.

    python3 docs/교재/도구/대본시간.py <대본.md> [분당 음절 수(기본 260)]

- `## [SLIDE NN] 제목` 아래의 본문만 센다. 인용 줄(>)과 굵게 표시는 뺀다.
- `English(한글 발음)`은 한글 발음만 센다. 숫자는 자리당 1.6음절, 남은 영문은 글자당 0.6음절로 어림한다.
- 분당 음절 수는 가정이다. 실제 음성 파일 하나의 글자 수와 길이로 맞춘 뒤에 쓴다.
"""
import re
import sys


def syllables(text: str) -> float:
    text = re.sub(r"\*\*|^>.*$|^# .*$", "", text, flags=re.M)  # 굵게 표시, 인용 줄, 큰 제목 줄은 세지 않는다
    text = re.sub(r"[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)", r"\1", text)
    return (len(re.findall(r"[가-힣]", text))
            + len(re.findall(r"\d", text)) * 1.6
            + len(re.findall(r"[A-Za-z]", text)) * 0.6)


def main() -> None:
    path = sys.argv[1]
    rate = float(sys.argv[2]) if len(sys.argv) > 2 else 260.0
    body = open(path, encoding="utf-8").read()
    body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", body, flags=re.M)[0]
    parts = re.split(r"^## \[SLIDE ([0-9~]+)\](.*)$", body, flags=re.M)
    total = 0.0
    print(f"| 장 | 음절 | 초 | 제목 |\n|---|---|---|---|")
    for i in range(1, len(parts), 3):
        n = syllables(parts[i + 2])
        total += n
        print(f"| {parts[i]} | {n:.0f} | {n / rate * 60:.0f} | {parts[i + 1].strip()} |")
    print(f"\n합계 {total:.0f}음절 · 분당 {rate:.0f}음절이면 {total / rate:.1f}분")


if __name__ == "__main__":
    main()
