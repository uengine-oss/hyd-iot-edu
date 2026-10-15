"""대본 MD의 낭독 시간을 장별 · 실라버스 행별로 어림하고 배정 시간과 견준다.

    python3 만들기/tools/deck/대본시간.py <대본.md> [분당 음절 수(기본 275)]

- `## [SLIDE NN] 제목` 아래의 본문만 센다. 인용 줄(>)과 굵게 표시는 뺀다.
- `English(한글 발음)`은 한글 발음만 센다. 숫자는 자리당 1.6음절, 남은 영문은 글자당 0.6음절로 어림한다.
- 행은 `# [이론] 제목 · NN분` 머리로 나눈다. 이론 행은 배정 분과 견주고, 회차 합은 이론 행의 배정 합과 견준다
  (2_기준 39 · 40번: 실습을 뺀 이론 합에 맞추고 행 사이는 유연하게 조율한다, 넘친 분은 실습 시간에서 줄인다).
  실습 행은 연결 멘트뿐이라 재기만 한다.
- 분당 275음절은 실측으로 맞춘 값이다: 옛 1일차 강의 영상 9편(강사 복제 음성, 쉼 포함, 합계 6,750초)과
  그 영상을 만든 대본(커밋 295ced0의 `통합반_01일차_대본*_윤문2.md`)을 이 도구로 재면 30,995음절, 분당 276음절
  (이론 행 273 · 275 · 282). 음성 엔진이나 쉼 설정을 바꾸면 다시 맞춘다.
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
    rate = float(sys.argv[2]) if len(sys.argv) > 2 else 275.0
    body = open(path, encoding="utf-8").read()
    body = re.split(r"^# (여기까지 작성|촬영 본문 끝)|^## 제작 확인용", body, flags=re.M)[0]
    rows, row = [], None  # [구분, 제목, 배정 분, 음절]
    total = 0.0
    print(f"| 장 | 음절 | 초 | 제목 |\n|---|---|---|---|")
    for block in re.split(r"^(?=# \[|## \[SLIDE )", body, flags=re.M):
        head = re.match(r"# \[(이론|실습|도입|마무리)\]\s*(.*?)(?:\s*·\s*(\d+)분)?(?:\s*\(.*\))?\s*$", block.split("\n", 1)[0])
        if head:
            row = [head.group(1), head.group(2).strip(), int(head.group(3)) if head.group(3) else None, 0.0]
            rows.append(row)
            continue
        slide = re.match(r"## \[SLIDE ([0-9~]+)\](.*)$", block.split("\n", 1)[0])
        if not slide:
            continue
        n = syllables(block.split("\n", 1)[1] if "\n" in block else "")
        total += n
        if row is not None:
            row[3] += n
        print(f"| {slide.group(1)} | {n:.0f} | {n / rate * 60:.0f} | {slide.group(2).strip()} |")
    print(f"\n합계 {total:.0f}음절 · 분당 {rate:.0f}음절이면 {total / rate:.1f}분")
    theory = [r for r in rows if r[0] == "이론" and r[2]]
    if theory:
        print("\n| 구분 | 행 | 대본 분 | 배정 분 | 차이 |\n|---|---|---|---|---|")
        for kind, title, assigned, n in rows:
            m = n / rate
            diff = f"{m - assigned:+.1f}" if kind == "이론" and assigned else "—"
            print(f"| {kind} | {title} | {m:.1f} | {assigned if assigned else '—'} | {diff} |")
        got = sum(r[3] for r in theory) / rate
        want = sum(r[2] for r in theory)
        print(f"\n이론 합 {got:.1f}분 / 배정 합 {want}분 ({got - want:+.1f}분, {got / want * 100:.0f}%)")


if __name__ == "__main__":
    main()
