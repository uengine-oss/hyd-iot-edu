# vendor — 포털이 싣는 바깥 부품

이 폴더는 `workspace/개발/scripts/portal_vendor.sh` 가 통째로 만든다(손으로 고치지 않는다). 포털은 CDN 을 부르지 않고 이 파일들만 싣는다.
받은 날 2026-11-14. 부품마다 그 폴더에 라이선스 원문과 `VERSION` 이 있다.

| 폴더 | 무엇 | 버전 | 라이선스 | 크기(KB) | 어디에 쓰나 |
|---|---|---|---|---|---|
| basecoat | 화면 키트 Basecoat(shadcn/ui 부품의 HTML 판, nova 모양) | 1.1.0 | MIT | 285 | 단추 · 카드 · 뱃지 · 표 · 폼 · 탭 · 대화상자 · 드롭다운 · 토스트 · 메뉴 줄 · 명령 팔레트 · 빈 상태 · 스켈레톤 |
| pretendard | 한글 글꼴 Pretendard(가변) | 1.3.9 | SIL OFL 1.1 | 2021 | 포털의 모든 글 |
| geist-mono | 고정폭 글꼴 Geist Mono(가변, 라틴) | 5.3.0 | SIL OFL 1.1 | 33 | 숫자 · 코드 · 식별자 |
| lucide | 아이콘 Lucide(124개만 묶음) | 1.72.0 | ISC | 37 | 메뉴 · 단추 · 상태 아이콘 |
| uplot | 차트 uPlot | 1.6.32 | MIT | 61 | 설비 추이 · 성과 지표 |
| bpmn-js | 흐름 그림 보기(NavigatedViewer) | 18.31.1 | bpmn.io(MIT + 표시 유지) | 273 | 처리 건의 진행 길 · 흐름 화면. 그리기는 bpmn.io 에서 한다 |
| bpmn-auto-layout | 흐름 그림 자동 배치(한 파일로 묶음) | 1.3.0 | MIT | 86 | 배치 정보가 없는 BPMN 을 가져왔을 때 |
| cytoscape | 그래프 그림 Cytoscape.js | 3.35.0 | MIT | 441 | 지식 지도 |
| cytoscape-fcose | 그래프 배치 fcose(+ cose-base, layout-base) | 2.2.0 | MIT | 341 | 지식 지도의 배치 |
| marked | 마크다운 → HTML | 18.2.0 | MIT | 57 | 스킬 문서 · 문서 원문 · AI 답 |
| dompurify | HTML 소독 | 3.4.17 | Apache-2.0 | 45 | marked 가 낸 HTML 을 화면에 넣기 전 |
| prism | 구문 강조 Prism(핵심 + json · yaml · python · bash · sql · cypher · xml) | 1.30.0 | MIT | 37 | 도구 호출의 입력 · 출력, 흐름 XML, 질의 |

전체 크기: 3725 KB
