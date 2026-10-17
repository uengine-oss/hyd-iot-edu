# 교재 (이론 PPTX 덱)

처음 온 세션은 `문서/교재/1_목적과_방향.md`부터 읽는다. 할 일에 맞는 문서와 스킬을 거기서 고른다.

HYD 제조 AI 교육과정의 이론 교재와 그것을 만드는 재료다. 교재는 통합반 원 덱 하나(1~11회차)이고 모든 반이 같은 덱을 쓴다. 다른 반의 하루치 덱은 그날의 회차 덱들에서 표지를 떼고 이어 붙인 뒤 그날 표지 하나를 붙여 만든다(`문서/교재/2_기준.md` 12번). 장수와 지금 상태는 `문서/교재/3_현황.md`에 있고, `.claude/skills/hyd-course-deck/scripts/장수.py`로 센다. 실라버스는 사용자가 직접 쓰며 기준은 `문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx`다(통합반 1~4회차는 `문서/교재/실라버스/실라버스_1-4일차_확정안.xlsx`와 같다).

```
만들기/decks/
  integrated/day01 … day11/           통합반_NN일차.md(원 덱 원고), figures/(SVG, PNG, CSV와 그리는 스크립트)
  integrated/sample/                  컨펌받은 그림체 샘플(16장)
  practical/ · integrated-offline/ · practical-offline/
                                      옛 조립 방식의 원고와 조립.py(옛 판, 아래 「옛 방식」)

산출물/교재/PPTX/<과정>/              만든 PPTX 38개(통합반 온라인 11개가 새 판, 나머지 27개는 옛 판)
문서/교재/                            기준과 인계 문서, 사실표 넷, 실라버스 둘. 1_목적과_방향.md부터 읽는다
만들기/tools/deck/                    시트.py(묶음 그림), 대본시간.py, 낭독본.py, 대본PDF.py, 노션_스타일맞춤.py
만들기/dist/교재_전체.zip              과정별 폴더에 PPTX 38개
```

## 원본과 산출물

덱 MD(`통합반_NN일차.md`)가 원본이고 PPTX는 거기서 만든다. 그림은 `figures/`의 파이썬 스크립트가 그린다(스크립트는 자기 위치 기준 상대 경로만 쓴다). 저장소의 PPTX는 확정본이므로 덱 MD를 고쳤을 때만 다시 만든다. 빌드 · 검사 · 렌더 · 그림 다시 그리기 · 배포 묶음의 명령은 `문서/교재/4_만드는_법.md` 1부에 있다.

## 옛 방식 (쓰지 않는다)

`practical/`, `integrated-offline/`, `practical-offline/` 아래의 `조립.py` 26개와 `practical/만들기_01일차.py`, `.claude/skills/hyd-course-deck/scripts/재조립.py`는 통합반 덱의 장을 제목으로 찾아 가져오고 문구를 손질하던 도구다. 원 덱의 장 제목이 모두 바뀌어 지금 돌리면 멈춘다. 새 방식으로 하루치 덱을 다시 만든 뒤 지운다(`문서/교재/6_남은_일.md` 0절 4번). 조립 결과 MD(`실전반_0N일차.md`, `<과정>_오프라인_NN회차.md`)도 옛 판이다.

## 스킬

스킬(도구와 형식 문서)은 저장소의 `.claude/skills/`가 유일한 원본이다. 목록과 관계는 `.claude/skills/README.md`에 있다.

- 이 교재에 쓰는 것은 `hyd-course-deck`(절차의 진입점, `scripts/장수.py` · `배포묶음.py`)과 `lecture-deck`(덱 MD → PPTX 도구 `scripts/deck2pptx.py`, 형식 문서 `references/덱MD-PPTX형식.md`)이다. 실습 가이드는 `hyd-lab-guide`다.
- 스킬 문서는 기준을 복사하지 않고 가리킨다. 규칙을 바꿀 때는 `문서/교재/2_기준.md`를 고친다.
