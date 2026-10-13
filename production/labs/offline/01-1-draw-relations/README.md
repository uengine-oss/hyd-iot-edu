# 01-1-draw-relations — 설비 이상과 원인 · 조치의 관계 직접 표현하기 (강사용)

통합반 오프라인 1회차 실습 1(40분). 브라우저의 arrows.app에서 쿨러 사건의 대상 여덟 개를 노드와 관계로 그린다. 학생에게 나눠 줄 파일은 없다.

| 파일 | 내용 |
|---|---|
| `runsheet.html` | 촬영 진행표. 강사가 화면 한쪽에 띄워 놓고 직접 말하고 조작하며 찍는다. 읽는 대본이 아니다 |
| `runsheet.json` | 진행표의 내용. 고친 뒤 `python3 ../build_runsheet.py .`로 다시 만든다 |

## 실제로 확인한 것 (2026-10-13)
- arrows.app을 자동 조작으로 열어 확인했다: 첫 화면의 쿠키 안내와 Help 창, 처음부터 놓여 있는 노드 하나, 더블클릭으로 이름 적기(한글), 「Add Node」, 노드 안쪽을 끌면 이동, 테두리 바깥 고리를 끌면 관계와 새 노드 생성, 화살표 더블클릭으로 이름 적기와 오른쪽 칸의 「Type」, 「Reverse」 · 「Duplicate」 · 「Delete」, 노드의 「Labels」, 선택을 풀었을 때의 nodes · relationships 수, 「Download / Export」의 탭(PNG · SVG · Cypher · JSON · URL · GraphQL).
- 노드와 관계의 이름 · 방향은 실습용 온톨로지(`course/labs/offline/05-2-cause-agent/ontology/graph.json`)에 실제로 있는 것이다.

## 확인하지 못한 것
- 여덟 노드와 여덟 관계를 끝까지 그려 본 것은 아니다. 구간별 시간은 추정이다.
- PNG를 실제로 내려받아 열어 보지 않았다. Cypher 탭에 나오는 문장의 내용도 보지 않았다.
- 진행표의 문장은 윤문하지 않은 초안이다.
