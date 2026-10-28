"""이론 분할 대본 MD의 낭독 시간을 장별로 낸다 — 실제 강사 복제 음성으로 맞춘 계수(제작용/촬영/시간계수.json)를 쓴다.

    python 제작용/기존제작/tools/deck/대본시간.py <대본.md> [<대본.md> ...]

- 장 시간 = scale·(장 본문의 말 길이) + per_slide. 말 길이와 장 계수는 제작용/촬영/시간계산.py가 맞춘다
  (calibrate: 문장 음성, calibrate-lecture: 이론 영상의 장별 음성 시간). 새 음성이 생기면 다시 맞춘다.
- `## [SLIDE NN] 제목` 아래 본문만 센다. 인용 줄(>) · 굵게 표시 · 제목 줄은 빼고, `English(한글 발음)`은 한글 발음만 센다.
- 낭독 추정이며 조작 · AI 응답 대기 · 학습 대기는 들어 있지 않다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '촬영'))
from 시간계산 import load_coef, script_slides, slide_seconds  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    k = load_coef()
    grand = 0.0
    for path in sys.argv[1:]:
        slides = script_slides(Path(path).read_text(encoding='utf-8'))
        total = 0.0
        print(f"\n{path}\n| 장 | 초 | 제목 |\n|---|---|---|")
        for n, (text, share, title) in sorted(slides.items()):
            sec = slide_seconds(text, k) / share if share > 1 else slide_seconds(text, k)
            total += sec
            print(f"| {n} | {sec:.0f} | {title} |")
        grand += total
        print(f"합계 {total / 60:.1f}분")
    if len(sys.argv) > 2:
        print(f"\n전체 {grand / 60:.1f}분")


if __name__ == "__main__":
    main()
