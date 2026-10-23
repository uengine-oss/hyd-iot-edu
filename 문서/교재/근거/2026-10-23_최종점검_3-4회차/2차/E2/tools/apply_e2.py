"""E2 손질 적용기 — 제안본 사본에 변경목록의 전→후를 차례로 적용한다.

각 '전' 문자열은 파일 전체에서 정확히 한 번 나와야 하고, 그 위치는 '## [SLIDE 29]' 뒤여야 한다(1~28장 불변).
사용: python3 -I apply_e2.py <파일>
"""
import sys

CHANGES = [
    # (번호, 전, 후)
    (1,
     "따라가 보겠습니다.\n\n이 원리를 확인한 뒤에는 이어질 에이전트 실습 두 개에서 무엇을 만들고 어떤 결과를 확인할지도 함께 살펴보겠습니다.\n",
     "따라가 보겠습니다.\n"),
    (2,
     "두 번까지 시도하라고 작업 지침에 적혀 있습니다.",
     "두 번까지 시도하라는 지침이 작업 규칙에 적혀 있습니다."),
    (3,
     "아래 다섯 칸에 적힌 게 바로 앞에서 본 원인 진단 호출이에요.",
     "아래 다섯 칸에 적힌 게 앞에서 본 그 원인 진단 호출이에요."),
    (4,
     "먼저 도구의 출력과 최종 설명이 같은 뜻인지 봅니다.",
     "거슬러 올라갈 때는 도구의 출력과 최종 설명이 같은 뜻인지부터 봅니다."),
    (5,
     "화면에서 확인된 원인이라고 부르던 것도 이 판정 범위 안에서 읽어야 합니다.",
     "지금까지 확인된 원인이라고 부르던 것도 이 판정 범위 안에서 읽어야 합니다."),
]


def main(path):
    text = open(path, encoding="utf-8").read()
    start = text.index("## [SLIDE 29]")
    for no, before, after in CHANGES:
        n = text.count(before)
        assert n == 1, f"변경 {no}: '전'이 {n}번 나옴"
        pos = text.index(before)
        assert pos > start, f"변경 {no}: 29장 앞에 있음"
        text = text.replace(before, after, 1)
    open(path, "w", encoding="utf-8").write(text)
    print("적용", len(CHANGES), "건")


if __name__ == "__main__":
    main(sys.argv[1])
