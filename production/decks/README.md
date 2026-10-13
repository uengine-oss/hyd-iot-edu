# 교재 (이론 PPTX 덱)

처음 온 세션은 `문서/교재/1_목적과_방향.md`부터 읽는다. 할 일에 맞는 문서와 스킬을 거기서 고른다.

HYD 제조 AI 교육과정의 이론 교재와 그것을 만드는 기준·도구다. 지금은 온라인 과정의 통합반 1~11일차(98 · 100 · 94 · 64 · 66 · 72 · 57 · 63 · 72 · 61 · 63장)와 실전반 1~8일차(98 · 93 · 75 · 75 · 88 · 66 · 53 · 63장), 오프라인 과정의 통합반 오프라인 1~10회차(40 · 42 · 42 · 54 · 43 · 42 · 62 · 40 · 32 · 53장)와 실전반 오프라인 1~9회차(42 · 43 · 52 · 41 · 41 · 62 · 36 · 31 · 54장)가 있다. 실전반 8일차는 통합반 11일차를 순서 그대로 가져온다. 실전반은 통합반 덱에서 장을 가져와 조립한다(제작 기준 13-1절). 실라버스는 사용자가 직접 쓰며 기준은 `기준/피지컬AI_실라버스_최종본.xlsx`다(통합반 1~4일차는 `기준/1~4일차 실라버스 확정안.xlsx`와 같다). 오프라인 과정(통합반 정규 10회, 실전반 정규 9회)의 덱도 통합반 덱에서 장을 골라 조립한다(제작 기준 13-2절). 실전반 오프라인의 원천도 실전반 온라인 덱이 아니라 통합반 덱이다.

```
production/decks/
  integrated/day01 … day11/           통합반_NN일차.md(원 덱 원고), figures/(SVG, PNG, CSV, 그리는 스크립트), 대본의 원문과 1차 윤문본
  integrated/sample/                  컨펌받은 그림체 샘플(16장)
  integrated/day11/보관/               시연으로 바꾸며 뺀 ProcessGPT 이론 단원의 원고. 덱에 쓰이지 않는다
  practical/만들기_01일차.py            실전반 1일차를 통합반 1일차 원고에서 낸다(실라버스가 같다)
  practical/day02 … day08/            조립.py(가져올 장의 순서표와 손질 목록), 새장_0N일차.md(새로 쓴 장), 실전반_0N일차.md(조립 결과. 직접 고치지 않는다)
  integrated-offline/session01 … 10/  조립.py, 새장_NN회차.md, 통합반_오프라인_NN회차.md(조립 결과. 직접 고치지 않는다)
  practical-offline/session01 … 09/   조립.py, 새장_NN회차.md, 실전반_오프라인_NN회차.md(조립 결과. 직접 고치지 않는다)

course/slides/<과정>/                   만든 PPTX 38개와 노션 실습 덱
문서/교재/                             기준과 인계 문서, 덱 제작 기준, 사실표 넷, 실라버스 둘. 1_목적과_방향.md부터 읽는다
production/tools/deck/                 시트.py(묶음 그림), 노션_스타일맞춤.py, 대본시간.py
production/dist/교재_전체.zip           과정별 폴더에 PPTX 38개. 덱을 다시 빌드하면 다시 만든다
```

도구와 스킬은 저장소 루트의 `.claude/skills/`에 있다(아래 「스킬」 절).

## 원본과 산출물

덱 MD(`통합반_0N일차.md`)가 원본이고 PPTX는 거기서 만든다. 그림은 `figures/`의 파이썬 스크립트가 그린다(스크립트는 자기 위치 기준 상대 경로만 쓴다). 저장소의 PPTX는 확정본이므로 다시 만든 것으로 덮어쓰지 않는다. 덱 MD를 고쳤을 때만 다시 만든다.

## 실전반 덱 다시 만들기

실전반 2~8일차 덱 MD(`실전반_0N일차.md`)는 `조립.py`가 통합반 원고에서 만든 결과이므로 직접 고치지 않는다. 오프라인 과정의 덱 MD(`통합반_오프라인_NN회차.md`, `실전반_오프라인_NN회차.md`)도 같다. 통합반 원고를 고치면 해당 실전반 일차와 오프라인 회차의 조립과 빌드를 다시 한다.

```bash
python3 production/decks/practical/day0N/조립.py
python3 production/decks/integrated-offline/sessionNN/조립.py
python3 production/decks/practical-offline/sessionNN/조립.py
python3 .claude/skills/hyd-course-deck/scripts/재조립.py --day N    # 통합반 N일차를 읽는 스크립트를 모두 돌린다(--dry-run이면 목록만)
```

조립 스크립트는 모두 27개다(`조립.py` 26개와 `practical/만들기_01일차.py`). 순서와 그 뒤의 빌드 · 배포 묶음 · 장수 맞추기는 `문서/교재/4_만드는_법.md` 1부 (나)에 있다.

| 고친 통합반 일차 | 다시 만들 실전반 일차 | 다시 만들 통합반 오프라인 회차 | 다시 만들 실전반 오프라인 회차 |
|---|---|---|---|
| 1 | 1 (`만들기_01일차.py`) | 1 | 1 |
| 2 | 2 | 1 · 2 | 1 |
| 3 | 2 · 3 | 2 · 3 | 2 |
| 4 | 3 | 4 | 3 |
| 5 | 4 | 5 | 4 |
| 6 | 4 | 6 | 5 |
| 7 | 5 | 7 | 6 |
| 8 | 5 | 7 | 4 · 6 |
| 9 | 6 | 8 · 9 | 6 · 7 · 8 |
| 10 | 7 | 9 · 10 | 9 |
| 11 | 8 | 9 · 10 | 8 · 9 |

각 `조립.py`가 읽는 통합반 일차에서 낸 표다(`재조립.py --dry-run`의 출력과 같다). 실전반 오프라인 8회차의 `조립.py`는 통합반 11일차 덱 MD도 읽지만 지금 거기서 가져오는 장은 없다(11일차에서 오던 퀴즈 한 문항을 새 문항으로 바꿨다). 통합반 오프라인 4회차는 실전반 3일차의 새 장(`practical/day03/새장_03일차.md`) 한 장도 가져오므로, 그 파일을 고치면 통합반 오프라인 4회차도 다시 조립한다. 회차별 장수와 원천은 제작 기준 13-2절에 있다.

조립한 뒤에는 아래 「다시 빌드하기」의 방법으로 PPTX를 만든다. 가져오던 장의 제목이 바뀌었으면 스크립트가 멈추므로 `조립.py`의 순서표를 고친다.

## 다시 빌드하기

저장소 루트에서 실행한다. 글자는 모두 고칠 수 있는 텍스트 상자로 나온다.

```bash
# PPTX 만들기 (장수와 규칙 위반을 확인한다)
uv run --no-project --with python-pptx --with pymupdf python .claude/skills/lecture-deck/scripts/deck2pptx.py production/decks/integrated/day04/통합반_04일차.md <출력.pptx>

# 렌더해 보기 (LibreOffice, pdftoppm, 맑은 고딕 필요. 렌더 폴더는 새 이름으로)
... deck2pptx.py <덱.md> <출력.pptx> --render <새 렌더 폴더>
uv run --no-project --with pillow python production/tools/deck/시트.py <렌더 폴더> <출력 접두어> --cols 4 --per 24

# 그림 다시 그리기 (해당 일차의 그림 폴더에서. 삽화는 표준 라이브러리만 쓰고 그래프는 matplotlib을 쓴다)
cd production/decks/integrated/day10/그림 && python3 만들기_삽화.py
cd production/decks/integrated/day03/그림 && uv run --no-project --with matplotlib python 만들기_그래프.py
```

렌더 폴더, 한눈에 보기 그림, 중간 PDF, `__pycache__`는 저장소에 올리지 않는다.

## 스킬

스킬(도구와 형식 문서)은 저장소의 `.claude/skills/`가 유일한 원본이다. 다른 곳에 사본을 두지 않고, 고칠 때는 여기서 고친다. 목록과 서로의 관계는 `.claude/skills/README.md`에 있다.

- 이 교재에 쓰는 것은 `hyd-course-deck`(절차의 요약과 `scripts/재조립.py` · `장수.py` · `배포묶음.py`)과 `lecture-deck`(덱 MD → PPTX 도구 `scripts/deck2pptx.py`, 형식 문서 `references/덱MD-PPTX형식.md`)이다. 실습 가이드는 `hyd-lab-guide`다.
- 스킬 문서는 제작 기준을 복사하지 않고 가리킨다. 규칙을 바꿀 때는 `문서/교재/2_기준.md`를 고친다.
