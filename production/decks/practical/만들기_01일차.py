"""실전반 1일차 덱 MD를 통합반 1일차 덱 MD에서 만든다.

실전반 온라인 1일차의 실라버스는 통합반 1일차와 같다. 내용을 두 벌로 관리하지 않도록
통합반 원고에서 문서 제목과 표지의 과정 이름, 그림 경로만 바꿔 낸다. 통합반 1일차를 고치면 이 스크립트를 다시 돌린다.

    python3 production/decks/practical/만들기_01일차.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "integrated" / "day01" / "통합반_01일차.md"
OUT = HERE / "01일차" / "실전반_01일차.md"

text = SRC.read_text(encoding="utf-8")
assert text.count("- 과정: 통합반 1일차") == 1, "표지의 과정 줄을 찾지 못함"
text = text.replace("- 과정: 통합반 1일차", "- 과정: 실전반 1일차")
assert text.startswith("# 통합반 1일차 — "), "문서 제목 줄을 찾지 못함"
text = text.replace("# 통합반 1일차 — ", "# 실전반 1일차 — ", 1)                 # 문서 제목(화면 밖)
text = text.replace("- 그림: figures/", "- 그림: ../../integrated/day01/figures/")   # 그림은 통합반 것을 그대로 쓴다
head = "<!-- 이 파일은 만들기_01일차.py가 통합반 1일차 원고에서 만든다. 직접 고치지 않는다. -->\n"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(head + text, encoding="utf-8")
print(f"{OUT.relative_to(HERE.parent.parent.parent)} 만듦")
