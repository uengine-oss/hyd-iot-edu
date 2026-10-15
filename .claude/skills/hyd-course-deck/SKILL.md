---
name: hyd-course-deck
description: "HYD 제조 AI 교육과정(통합반 · 실전반, 온라인 · 오프라인)의 이론 교재 PPTX 덱을 만들거나 고치거나 점검하거나 다시 조립하거나 배포 묶음을 만들 때 쓴다. 교재 한 장 고쳐줘, 통합반 N일차 덱, 조립 덱 다시, 전체 점검, 교재 zip에 쓴다. 덱 MD의 형식과 생성 도구는 lecture-deck, 실습 가이드는 hyd-lab-guide."
---

# HYD 교재 덱

이 스킬은 HYD 교재 작업의 진입점이다. 교육 기준은 `문서/교재/2_기준.md`, 작업 순서는 `문서/교재/4_만드는_법.md`에만 둔다. 아래 경로와 명령은 저장소 루트 기준이다.

## 시작

1. 최신 요청의 수정 범위를 확인하고 `.astra/`를 쓰는 작업은 그 README와 상태에서 재개한다.
2. `문서/교재/1_목적과_방향.md`와 `2_기준.md`, `3_현황.md`에서 목적·기준·현재 산출물을 확인한다. 결정 경위는 `5_결정_기록.md`, 보류와 다음 일은 `6_남은_일.md`다.
3. 해당 실라버스 원문·사실표·덱·대본·필요한 코드를 읽는다. 읽은 버전과 이해가 유지된 범위는 다시 출력하지 않되, 최신 요청이 전체 읽기를 요구하면 따른다.
4. 제작·점검은 `4_만드는_법.md` 2부 0절로 진행한다. 표기만 다듬는 작업과 전개·구조를 다시 만드는 작업을 구분하고, 점검 범위는 `2_기준.md` 45-2번에 둔다.

## 작업별 경로

| 일 | 정본과 도구 |
|---|---|
| 원 덱 | `만들기/decks/integrated/dayNN/통합반_NN일차.md` |
| 덱 형식·유형·그림·검사 | `../lecture-deck/SKILL.md`, `../lecture-deck/references/덱MD-PPTX형식.md` |
| 원 덱 수정과 파생물 갱신 | `문서/교재/4_만드는_법.md` 1부 |
| 새 제작·재구성·종합 점검 | 같은 문서 2부 0~3절 |
| 낭독 대본·윤문 도구 | 같은 문서 3부 2절 |
| 실습·영상 | `../hyd-lab-guide/SKILL.md`, `../hyd-lecture-video/SKILL.md` |

현재 조립 스크립트는 장 제목과 원문 치환에 의존한다. 새 공통 단원 조립으로 전환하기 전의 실행 가능 범위와 보류 대상은 `6_남은_일.md` 0절을 먼저 확인한다. 옛 `새장_*.md`·손질 목록을 새 제작 방식으로 확대하지 않는다.

## 명령

```bash
.venv-deck/bin/python .claude/skills/lecture-deck/scripts/deck2pptx.py --check <덱 MD>
uv run --no-project --with python-pptx --with pymupdf python .claude/skills/lecture-deck/scripts/deck2pptx.py <덱 MD> <출력 PPTX> --render <새 렌더 폴더>
python3 만들기/tools/deck/고칠것넣기.py <고칠것 JSON> <대본> <덱> --dry
python3 만들기/tools/deck/대본시간.py <대본>
python3 .claude/skills/hyd-course-deck/scripts/재조립.py --dry-run
python3 .claude/skills/hyd-course-deck/scripts/배포묶음.py --check
```

명령의 적용·재조립·배포 단계는 `4_만드는_법.md`를 따른다. 시간 도구의 미반영 요구는 `6_남은_일.md`에서 확인한다. 도구가 지원하지 않는 계산을 실행 결과라고 쓰지 않는다.

## 검토와 보고

검토 기준은 `2_기준.md` 16절이다. 화면의 자동 검사, 사실 대조, 단원 전개와 낭독 확인, 렌더 확인을 각각 기록한다. 공통 용어·값·선수 개념은 같은 기준의 83·92번으로 대조한다. 변경 파일·근거·검사한 범위·미확인·파생물 갱신 대기를 보고한다. 승인·작업자·커밋 관련 조건은 같은 기준 12~13절과 최신 사용자 요청을 따른다.
