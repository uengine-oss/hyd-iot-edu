---
name: hyd-course-deck
description: "HYD 제조 AI 교육과정(통합반 · 실전반, 온라인 · 오프라인)의 이론 교재 PPTX 덱을 만들거나 고치거나 점검하거나 다시 조립하거나 배포 묶음을 만들 때 쓴다. 교재 한 장 고쳐줘, 통합반 N일차 덱, 조립 덱 다시, 전체 점검, 교재 zip에 쓴다. 덱 MD의 형식과 생성 도구는 lecture-deck, 실습 가이드는 hyd-lab-guide."
---

# HYD 교재 덱

이 스킬은 HYD 교재 작업의 진입점이다. 교육 기준은 `문서/교재/2_기준.md`, 작업 순서와 명령은 `문서/교재/4_만드는_법.md`에만 둔다. 아래 경로와 명령은 저장소 루트 기준이다.

## 시작

1. 최신 요청의 수정 범위를 확인하고 `git log --oneline -15` · `git status`로 대조한다.
2. `문서/교재/1_목적과_방향.md`와 `2_기준.md`, `3_현황.md`에서 목적 · 기준 · 현재 산출물을 확인한다. 결정 경위는 `5_결정_기록.md`, 다음 일과 미결은 `6_남은_일.md`다.
3. 해당 실라버스 원문 · 사실표 · 덱 · 대본 · 필요한 코드를 읽는다.
4. 제작 · 다시 짜기는 `4_만드는_법.md` 2부 0절로 진행한다. 세션은 쓰고 다듬는 데까지 하고, 검증 · 피드백 수정은 사용자가 아스트라로 한다(`2_기준.md` 41번). 표기만 다듬는 일과 전개 · 구조를 다시 짜는 일을 구분한다.

## 작업별 경로

| 일 | 정본과 도구 |
|---|---|
| 원 덱(모든 반 공통) | `만들기/decks/integrated/dayNN/통합반_NN일차.md` |
| 덱 형식 · 유형 · 그림 · 검사 | `../lecture-deck/SKILL.md`, `../lecture-deck/references/덱MD-PPTX형식.md` |
| 덱 고치기 · 빌드 · 렌더 · 장수 · 배포 묶음 | `문서/교재/4_만드는_법.md` 1부 |
| 새 제작 · 다시 짜기 | 같은 문서 2부 |
| 대본 길이 · 낭독본 · 대본 PDF | 같은 문서 3부 1절 |
| 실습 · 영상 | `../hyd-lab-guide/SKILL.md`, `../hyd-lecture-video/SKILL.md` |

다른 반의 하루치 덱은 회차 덱의 표지를 떼고 이어 붙여 만든다(`2_기준.md` 12번). 옛 `조립.py` · `재조립.py`는 지금 돌리면 멈추는 옛 방식이다(`6_남은_일.md` 0절 4번).

## 명령

```bash
uv run --no-project --with python-pptx --with pymupdf python .claude/skills/lecture-deck/scripts/deck2pptx.py --check <덱 MD>
uv run --no-project --with python-pptx --with pymupdf python .claude/skills/lecture-deck/scripts/deck2pptx.py <덱 MD> <출력 PPTX> --render <새 렌더 폴더>
python3 만들기/tools/deck/대본시간.py <대본>
python3 만들기/tools/deck/낭독본.py <대본> <낭독본>
python3 .claude/skills/hyd-course-deck/scripts/장수.py --units
python3 .claude/skills/hyd-course-deck/scripts/배포묶음.py --check
```

## 검토와 보고

검토 기준은 `2_기준.md` 9절이다. 화면의 자동 검사, 사실 대조, 단원 전개와 낭독 확인, 렌더 확인을 각각 기록한다. 공통 용어 · 값은 같은 기준 11 · 16번으로 대조한다. 변경 파일 · 근거 · 검사한 범위 · 미확인 · 파생물 갱신 대기를 보고하고, `3_현황.md` · `6_남은_일.md`를 고쳐 쓴다. 커밋 · push는 `2_기준.md` 48번이다.
