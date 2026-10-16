"""대본 MD의 낭독 시간을 장별 · 실라버스 행별로 어림하고 배정 시간과 견준다.

    python3 만들기/tools/deck/대본시간.py <대본.md> [분당 음절 수(기본 275)]

- `## [SLIDE NN] 제목` 아래의 본문만 센다. 인용 줄(>)과 굵게 표시는 뺀다.
- `English(한글 발음)`은 한글 발음만 센다. 숫자는 자리당 1.6음절, 남은 영문은 글자당 0.6음절로 어림한다.
- 행은 `# [이론|실습|도입|마무리] 제목 · NN분` 머리로 나눈다(2_기준 32 · 33번).
  이론 합 = 본문 이론 행 + 마무리 행(복습 · 퀴즈)을 한 번씩 더한 값이고, 이론 행의 배정 합과 견준다.
  이론 합이 배정 합보다 10분 넘게 짧으면 「마지노선 미달」로 표시한다(41번). 도입 · 실습 연결은 재기만 한다.
- 학습 대기(51번)는 낭독 밖 제작 표시 `> [대기 N초] 무엇을 보고 판단하나`로 적는다. 장별 · 회차 합을 따로 보이고
  이론 합에는 넣지 않는다(학습 대기로 이론 하한을 채웠다고 하지 않는다). 낭독본 · 영상 도구는 `>` 줄을 읽지 않는다.
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
    rows, row = [], None  # [구분, 제목, 배정 분, 음절, 대기 초]
    total, wait_total = 0.0, 0
    print(f"| 장 | 음절 | 초 | 제목 |\n|---|---|---|---|")
    for block in re.split(r"^(?=# \[|## \[SLIDE )", body, flags=re.M):
        head = re.match(r"# \[(이론|실습|도입|마무리)\]\s*(.*?)(?:\s*·\s*(\d+)분)?(?:\s*\(.*\))?\s*$", block.split("\n", 1)[0])
        if head:
            row = [head.group(1), head.group(2).strip(), int(head.group(3)) if head.group(3) else None, 0.0, 0]
            rows.append(row)
            continue
        slide = re.match(r"## \[SLIDE ([0-9~]+)\](.*)$", block.split("\n", 1)[0])
        if not slide:
            continue
        text = block.split("\n", 1)[1] if "\n" in block else ""
        n = syllables(text)
        wait = sum(int(w) for w in re.findall(r"^>\s*\[대기\s*(\d+)\s*초\]", text, flags=re.M))
        total += n
        wait_total += wait
        if row is not None:
            row[3] += n
            row[4] += wait
        print(f"| {slide.group(1)} | {n:.0f} | {n / rate * 60:.0f}{f' (+대기 {wait}초)' if wait else ''} | {slide.group(2).strip()} |")
    print(f"\n합계 {total:.0f}음절 · 분당 {rate:.0f}음절이면 {total / rate:.1f}분")
    theory = [r for r in rows if r[0] == "이론" and r[2]]
    if theory:
        print("\n| 구분 | 행 | 대본 분 | 배정 분 | 차이 |\n|---|---|---|---|---|")
        for kind, title, assigned, n, _ in rows:
            m = n / rate
            diff = f"{m - assigned:+.1f}" if kind == "이론" and assigned else "—"
            print(f"| {kind} | {title} | {m:.1f} | {assigned if assigned else '—'} | {diff} |")
        body_min = sum(r[3] for r in theory) / rate
        wrap_min = sum(r[3] for r in rows if r[0] == "마무리") / rate
        got = body_min + wrap_min
        want = sum(r[2] for r in theory)
        floor = "충족" if got >= want - 10 else "미달"
        print(f"\n이론 합 {got:.1f}분(본문 {body_min:.1f} + 마무리 복습 · 퀴즈 {wrap_min:.1f}) / 배정 합 {want}분 "
              f"({got - want:+.1f}분, {got / want * 100:.0f}%) · 10분 마지노선 {floor}")
    print(f"학습 대기 합 {wait_total}초({wait_total / 60:.1f}분, 이론 합과 따로 센다)")

if __name__ == "__main__":
    main()
