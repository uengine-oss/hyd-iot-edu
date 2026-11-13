# 09 포털 CSS — 적대적 디자인 · CSS 전수 검사 (읽기 전용, 2026-11-13)

대상: `작업/2026-11-13_포털실습-다시만들기/포털개편/it/portal/www/`의 CSS 16개(브랜치 portal-ux, 미커밋 `enterprise.css` 포함 지금 파일 그대로).
`05_포털화면.md`와 `포털개편_바꿀목록.md`(이번 범위 표 + 참고 A~E)에 이미 있는 것은 다시 적지 않았다. 겹치는 자리는 그 번호를 가리키고 새로 찾은 것만 적었다.
- 이미 있어서 뺀 것: 목록 C의 「글자 크기 8가지 → 다섯 단계」 「`.btn` · `.chip` 규칙이 세 파일」 「주 버튼 그림자 옛 파랑」 「인라인 `style=` 78곳」 「꺼진 버튼 모양 둘」 「주황 세 벌」 「위험 버튼 빨강 채움」, 05의 지도-1(`.kvt` 12px · 영문 키 · nowrap) · 지도-6(옛 `.rels code`) · 조치-1(상세 칸 차례 · 규칙 JSON 접기) · 관리-17(칩 안 문장) · 모니터-1(Grafana 밝은 테마).

화면을 띄우지 않았다. 겉모습 판단은 모두 「코드로 본 추정」이다. 대비는 토큰 색 값으로 WCAG 상대 휘도 식을 계산했다(스크립트로 잰 값, 반투명 색은 흰 바탕에 섞어 계산).

## 1. 읽은 파일

| 파일 | 줄 수 | 읽은 범위 |
|---|---|---|
| `tokens.css` | 44 | 전부 |
| `theme.css` | 637 | 전부 |
| `styles.css` | 1138 | 전부 |
| `main.css` | 218 | 전부 |
| `components.css` | 320 | 전부 |
| `shell.css` | 130 | 전부 |
| `hitl.css` | 322 | 전부 |
| `instances.css` | 92 | 전부 |
| `taskDetail.css` | 38 | 전부 |
| `mcp.css` | 20 | 전부 |
| `kpi.css` | 18 | 전부 |
| `flows.css` | 40 | 전부 |
| `compare.css` | 23 | 전부 |
| `trace.css` | 182 | 전부 |
| `caseRecord.css` | 163 | 전부 |
| `enterprise.css` (미커밋) | 492 | 전부 |
| `index.html` | 395 | 7~22행(시트 읽는 차례), 86~260행(지식 지도 · 조치 방법 · 판단 · 처리 건 · 결함 · 이상 · 모니터링 · 지식 관리 · 관리), 나머지는 검색 |
| `fabric.js` | 191 | 전부(데이터 원천 마크업 확인용) |
| `enterprise.js` | 580 | 225~274행(지식 지도 상세 칸), 나머지는 검색 |
| `hitl.js` | 917 | 160~239행(조치 방법 상세), 쓰는 클래스 전부 검색 |
| `ui.js` | 772 | 305~308 · 449~476 · 574~586 · 617~619행(카드 · 칸 · 접기 · 빈 상태 · 오류 · 토스트 · 확인 대화상자 마크업), 나머지는 검색 |
| 그 밖의 `*.js` | — | 클래스 · `style=` · 변수 이름 검색만 |

시트 읽는 차례(index.html 7~22행): tokens → styles → enterprise → main → hitl → instances → components → taskDetail → mcp → shell → kpi → flows → compare → trace → caseRecord → **theme(맨 끝)**. 그래서 같은 무게의 선택자는 theme.css가 이기고, 앞 파일의 같은 규칙은 죽은 규칙이 된다(아래 13번 · 21번).

## 2. 토큰 요약 — 실제로 어떻게 돼 있나

**글자 크기**: 바탕 `body { font: 14px/1.55 }`(theme.css:41). 토큰은 없고 모두 숫자다. CSS 안의 `font-size` 값과 쓰인 수: 12px 100 · 13px 85 · 11px 41 · 14px 25 · 12.5px 18 · 15px 15 · 11.5px 10 · 13.5px 8 · 18px 6 · 16px 6 · 10px 5 · 10.5px 4 · 22px 3 · 20px 2 · 14.5px 2 · .85em 2 · 42 · 30 · 26 · 24 · 17px · .92em · .88em 각 1. 11px 이하(10 · 10.5 · 11)가 50번, 13px 미만 전체가 178번으로 본문(14px)보다 훨씬 많다. 실제로 이기는 제목 크기: 화면 h1 22 · 상세 h2 18 · 절 h2 15 · 카드 h3 14(아래 22번).

**글자 색과 대비**(theme.css:11~14 · 바탕 `--paper` #f9f9f7 · 카드 `--panel` #fff · 옅은 상자 `--surface-soft` #f4f3f0):

| 토큰 | 값 | 흰 카드 | 페이지 바탕 `--paper` | 옅은 상자 `--surface-soft` |
|---|---|---|---|---|
| `--ink` | #0b0b0b | 19.6 | — | — |
| `--ink-2` | #52514e | 7.94 | 7.5 | 7.15 |
| `--ink-3` | #76746e | 4.67 | **4.43** | **4.21** |
| `--ink-4` | #a3a19a | **2.59** | **2.45** | — |
| `--brand` (글자로 쓸 때) | #d97757 | **3.12** | 3.01 | — |
| `--warn` | #b54708 | 5.43 | | |
| `--ok` · `--alarm` · `--accent` | | 5.69 · 6.57 · 7.94 | | |
| 칩 다섯 톤(tokens.css:18~27) | | 모두 6.1 이상 | | |

theme.css:13 주석은 「흰 바탕 4.5:1」이라 적었지만 화면 바탕은 `--paper`, 표 머리 · 옅은 상자는 `--surface-soft`라 회색 글이 그 위에서 4.5에 못 미친다.

**간격**: `--s1 4 · --s2 8 · --s3 12 · --s4 16 · --s6 24 · --s8 32 · --s12 48`(tokens.css), `--s5 20`은 theme.css:34에만. 여백 · 간격에 숫자를 직접 박은 수와 토큰을 쓴 수(파일별 raw/token): caseRecord 85/1 · theme 75/21 · trace 56/12 · enterprise 46/16 · hitl 32/17 · instances 28/2 · components 24/56 · flows 18/0 · taskDetail 15/8 · styles 9/74. 박은 값 가운데 눈금 밖 값(6 · 10 · 14 · 18 · 3 · 5 · 7 · 9 · 22 · 28px)이 약 290번이다.

**모서리**: 토큰 `--radius 12 · --radius-sm 8 · --radius-lg 14`인데 실제 값은 21가지(8px 23 · 10px 12 · 6px 11 · 3px 10 · 4px 9 · 12px 7 · 999px 5 · 5px 2 · 2 · 7 · 9 · 13 · 14 · 16px …).

**색**: CSS 안 16진 색 333개(theme 55 · caseRecord 53 · styles 38 · components 33 · main 31 · instances 29 · hitl 25 · enterprise 23 · trace 23 …). 따뜻한 회색 체계(theme) 위에 옛 파랑 회색(#cbd5e3 · #edf0f5 · #b6c2d4 · #c5cdd8 · #fafbff …)이 남아 있다(18번).

**정의 안 된 변수**: `--surface-2` · `--line` · `--muted` · `--warn-bg` · `--neg`(19번). `--c` · `--spin`은 JS가 넣는다(enterprise.js:213, app.js:445 — 정상).

**어두운 테마**: `prefers-color-scheme` 규칙이 한 줄도 없다. 해당 없음(포털은 밝은 화면 하나다). 홈 그림(`.m-hero`)만 어두운 색을 박아 둔 그림이다.

## 3. 지적 표

무게: **가** = 읽기 어렵거나 깨짐 / **나** = 지저분함.

| 번호 | 무게 | 종류 | 파일:줄 | 원문 조각 | 무엇이 문제인가 | 고치는 길(구체적 CSS) |
|---|---|---|---|---|---|---|
| 1 | 가 | 대비 · 표 | theme.css:517 · styles.css:271-276 | `table th { font-size: 12px; font-weight: 500; color: var(--ink-3); }` + `th { … background: var(--surface-soft); }` | 포털의 **모든 표 머리**가 12px · 굵기 500 · #76746e를 #f4f3f0 위에 쓴다 — 4.21:1. styles.css의 `th { font-weight: 600; color: var(--ink-2) }`는 theme가 덮어 죽었다. 결과 데이터 표(판단 근거 · 처리 기록 · 데이터 원천 · 단계 표) 전부에 걸린다 | `table th { font-size: 12.5px; font-weight: 600; color: var(--ink-2); background: var(--surface-soft); }` (7.15:1). styles.css:271-276은 지운다 |
| 2 | 가 | 깨짐 · 상태 | styles.css:207-209 vs theme.css:310-314 | `.btn.danger:hover { background: #fbe1e6; }` · `.btn.danger { background: #b42318; … color: #fff; }` | 빨강 채움 단추에 마우스를 올리면 바탕만 연분홍이 되고 글자는 흰색 그대로 — **1.23:1, 글자가 사라진다**(무게 0,3,0이 0,2,0을 이긴다, 코드로 본 추정). 쓰는 곳: 확인 대화상자의 위험 단추(ui.js:619 — 지우기 · 되돌리기 확인 전부), [쿨러 열화 주입](app.js:296), 에이전트 · 스킬 [지우기](agents.js:141, 202) | styles.css:207-209를 지운다. 목록 C(위험 동작은 빨간 테두리 보조 단추)를 따르면 theme.css:310을 `.btn.danger { background: #fff; color: var(--alarm); border-color: color-mix(in srgb, var(--alarm) 45%, #fff); } .btn.danger:hover { background: #fef3f2; border-color: var(--alarm); }`(6.05:1). 채움을 남기면 `.btn.danger:hover { background: #912018; border-color: #912018; }` |
| 3 | 가 | 대비(뿌리) | theme.css:13 | `--ink-3: #76746e;      /* … 흰 바탕 4.5:1 로 한 단계 진하게 */` | 회색 보조 글(`.muted` · `.field-hint` · `.card-sub` · 목록 `.sub` · 머리줄 · 메뉴 묶음 이름)이 페이지 바탕에서 4.43, 옅은 상자(`.rel-group` · `.golden-item` · `.card.soft` · `.ap-evidence` · `.stream-row` · 표 머리)에서 4.21이다. 12px 이하 글이 대부분이라 더 읽기 어렵다 | `--ink-3: #6b6964;` 한 줄 — 흰 5.48 · 바탕 5.2 · 옅은 상자 4.94. 다른 규칙은 고칠 필요 없다 |
| 4 | 가 | 대비 · 결과 데이터 | trace.css:71 | `.tr-row time { font-size: 11px; white-space: nowrap; color: var(--ink-4); … }` | 처리 과정 줄마다 앞의 시각이 11px · 2.59:1이다. 「언제 무엇을 했나」를 읽는 자리 | `.tr-row time { font-size: 12px; color: var(--ink-3); }` |
| 5 | 가 | 대비 · 결과 데이터 | instances.css:6 | `.inst-table tr.CANCELLED td { color: #999; }` | 단계 표의 취소된 행 전체가 2.85:1. 무엇이 취소됐는지 읽을 수 없다 | `.inst-table tr.CANCELLED td { color: var(--ink-3); } .inst-table tr.CANCELLED td:first-child { text-decoration: line-through; text-decoration-color: var(--ink-4); }` |
| 6 | 가 | 글자 크기 · 이름 겹침 | instances.css:14 · styles.css:528-541 · instances.js:741 | `.inst-table .log { color: var(--muted, #6b7785); font-size: .85em; max-width: 420px; }` · `.log { font: 12px/1.8 var(--font); … border: 1px solid var(--rule); border-radius: var(--radius); padding: var(--s4); max-height: 240px; overflow: auto; }` · `<td class="log">` | 단계 표의 「기록」 칸(그 단계가 한 일 문장)이 13px × .85 = 약 11px, 색은 정의 안 된 `--muted`의 차가운 회색 폴백이다. 게다가 결함 시뮬레이션 기록 상자용 `.log` 규칙이 이 `td`에도 걸려 표 칸 안에 테두리 · 16px 안쪽 여백 · 최대 240px 스크롤 상자가 생긴다(코드로 본 추정) | 칸 클래스를 `step-log`로 바꾸고(instances.js:741) `.inst-table .step-log { color: var(--ink-2); font-size: 13px; max-width: 48ch; line-height: 1.5; }`. 이름을 그대로 두려면 `.inst-table td.log { border: 0; border-bottom: 1px solid var(--rule); border-radius: 0; padding: 6px 8px; max-height: none; overflow: visible; background: none; }` |
| 7 | 가 | 글자 크기 · 결과 데이터 | caseRecord.css:79 · 82-83 · 91 · 123 · 63 · 119 · 126 · 76 · 153 | `.cr-kv dt { font-size: 11.5px; … }` · `.cr-table { … font-size: 12.5px; } .cr-table th { … font-size: 11.5px; … white-space: nowrap; }` · `.cr-node small { font-size: 10.5px; }` · `.cr-q, .cr-a { … font-size: 10.5px; … }` · `.cr-id { font: 11px/1.4 … }` · `.cr-pre.small { … font-size: 11px; }` | 처리 기록(학생이 결과를 읽는 곳)의 이름표 · 표 · 판단 경로 · 요청/결과 표시가 10.5~12.5px이다. 같은 칸의 값(`.cr-kv dd` 13px)보다 이름표가 두 단계 작다 | `.cr-kv dt { font-size: 12px; color: var(--ink-2); } .cr-table { font-size: 13px; } .cr-table th { font-size: 12px; color: var(--ink-2); } .cr-node small, .cr-q, .cr-a, .cr-sys, .cr-io > span, .cr-id, .cr-ver { font-size: 12px; } .cr-pre, .cr-pre.small { font-size: 12px; }` |
| 8 | 가 | 글자 크기 · nowrap · 결과 데이터 | taskDetail.css:14 · 17 · 33 · 35-36 · theme.css:572-573 | `.td-table { … font-size: 12px; }` · `.td-prose { … font-size: 12px; … }` · `.td-part { … font-size: 12px; white-space: nowrap; }` · `.td-table td:not(:last-child), .td-table th { white-space: nowrap; }` | 단계 상세의 판단 근거 표 · AI 판단 문장 · 조건 · 점수 구성이 12px이고, 표는 마지막 칸 말고 모두 줄을 바꾸지 않는다. 규칙 이름 · 입력 이름이 길면 표가 옆으로 밀려 숫자 칸이 보이지 않는다(코드로 본 추정) | `.td-table, .td-prose, .td-cond, .td-part { font-size: 13px; } .td-prose { line-height: 1.6; }` theme.css:573을 `.td-table td.num, .td-table th { white-space: nowrap; }`로 좁힌다(숫자 칸에만) |
| 9 | 가 | 대비 · 글자로 쓴 브랜드 색 | theme.css:587 · trace.css:21 · 52 | `.ap-kicker { font-size: 12px; font-weight: 600; color: var(--brand); … }` · `.tr-status.run .tr-st { color: var(--brand); }` · `.tr-dur.live { color: var(--brand); … }` | 승인 카드 머리 말 · 처리 과정 요약의 「진행 중」 · 진행 중 걸린 시간이 #d97757 글자 — 3.12:1(12~13px) | 글자용 토큰 `--brand-ink: #a8452a;`(흰 5.92)를 theme `:root`에 더하고 세 곳의 `color`만 바꾼다. 막대 · 테두리의 `--brand`는 그대로 |
| 10 | 가 | 글자 크기 · 결과 데이터 | enterprise.css:379 · styles.css:694-696 · 529 | `.board { … font-size: 12px; }` · `.audit { font-size: 12px; }` · `.log { font: 12px/1.8 var(--font); … }` | 「판단 · 실행 기록」의 기업 시스템 현황 표, 이상 확인 · 판단의 처리 이력, 결함 시뮬레이션의 제어 요청 결과가 모두 12px 바탕이다. 같은 화면의 카드 본문(13px) · 판단 문장(14px)보다 작다 | `.board, .audit { font-size: 13px; } .log { font: 13px/1.7 var(--font); }` |
| 11 | 가 | 글자 크기(규칙 없음) | fabric.js:63-64 · 88-91 · 126-136 (CSS에 규칙 없음) | `` `<small>${esc(a.where)}</small>` `` · `` `<br><small>저장값 ${when(v.anchor)}</small>` `` | 데이터 원천 표 칸 안의 위치 · 사유 · 시각 · 판단 입력이 `<small>`인데 크기 규칙이 없어 브라우저 기본 `smaller`(13px의 약 83%, 약 10.8px)로 보인다. 화면에서 가장 작은 글이 「값이 어디서 왔나」다 | `.compact-table small { display: block; margin-top: 2px; font-size: 12px; color: var(--ink-3); line-height: 1.45; }` |
| 12 | 가 | 깨짐 · 여백 없음 | fabric.js:98-105 · 138-139 · 49-53 · 146 (CSS에 `.fab-body` 규칙 없음) | `` S.el.innerHTML = summary() + tabs + `<div class="fab-body">…` `` · `return S.sources.map(s => … UI.card({ … })).join('')` | 카드(`.card`)에는 바깥 여백이 없고 `.fab-body` · `#fabResult`에 간격 규칙도 없다. 「원천과 표」 탭의 원천 카드 두 장, 「클래스 ↔ 표 · 열」 탭의 카드 두 장, 「두 DB 묶어 보기」의 입력 카드와 결과 카드가 **테두리끼리 붙는다**(코드로 본 추정). 카드 사이 간격 규칙은 처리 건 상세(components.css:223)에만 있다 | `.fab-body, #fabResult { display: flex; flex-direction: column; gap: var(--s4); }` — 더 넓게는 `.shell-mount > .card + .card, .fab-body > .card + .card { margin-top: var(--s4); }` |
| 13 | 나 | 넘침 · nowrap | components.css:39 · styles.css:301 · 1013 · theme.css:331 | `.chip, .state { display: inline-flex; … white-space: nowrap; max-width: 100%; … }` | 칩이 줄을 바꾸지 않는데 넘친 글을 자르지도 않는다(`overflow` 없음). 긴 칩(「읽기 전용 아님」 · 원천 상태 · 뜻 복원 요약 칩 · 역할 이름)이 카드 밖으로 삐져나간다(코드로 본 추정). 처리 기록만 따로 풀었다(caseRecord.css:59) | `.chip { white-space: normal; text-align: left; line-height: 1.35; min-height: 22px; height: auto; padding-block: 2px; }` 그리고 caseRecord.css:59를 지운다. 한 줄로 두려면 `overflow: hidden; text-overflow: ellipsis;` + `title` |
| 14 | 나 | 일관성 · 키-값 목록 | components.css:271-274 · taskDetail.css:13 · components.css:202-204 · compare.css:6-9 · mcp.css:6-8 · caseRecord.css:77-80 · enterprise.css:149-166 · styles.css:492-505 · components.css:75 · 146 | `.meta-list > div { … grid-template-columns: 84px minmax(0, 1fr); … }` · `.td-kv > div { grid-template-columns: 110px … }` · `.hopt .fold-body dl > div { … 120px 1fr; … }` · `.cmp-dl > div { … 4.5em 1fr; … }` · `.mcp-kv { … max-content 1fr; … }` · `.cr-kv dt { font-size: 11.5px; … }` · `.kvt` · `.unit .kv` · `.field.ro .ro-value` · `.kv-line` | 같은 「이름 : 값」을 **열 가지** 꼴로 그린다. 이름 칸 폭이 84px · 110px · 120px · 4.5em(약 58px) · max-content로 다르고, 이름 글은 11.5 · 12 · 13px, 색은 ink-3 · ink-2로 다르다. 84px · 4.5em 칸은 「흐름 식별자」 「조치 식별자」 같은 이름이 두 줄로 꺾인다(코드로 본 추정) | 기준은 `.meta-list` 하나: `.meta-list > div, .td-kv > div, .hopt .fold-body dl > div, .cmp-dl > div { grid-template-columns: minmax(6em, max-content) minmax(0, 1fr); gap: var(--s3); } .meta-list dt, .td-kv dt, .hopt .fold-body dt, .cmp-dl dt, .mcp-kv dt, .cr-kv dt { font-size: 12.5px; color: var(--ink-2); }` 값은 13~14px `--ink`. 쌓는 꼴(`.cr-kv` · `.ro-grid`)은 이름 위 · 값 아래 하나로 |
| 15 | 나 | 일관성 · 표 | styles.css:259-285 · components.css:148-149 · instances.css:11-13 · enterprise.css:308-335 · caseRecord.css:82-86 · taskDetail.css:14 · enterprise.css:393-405 · 472-476 · 149-166 | `th, td { padding: var(--s3) var(--s4); … }` · `.compact-table th, .compact-table td { padding: 6px 10px; }` · `.inst-table th, .inst-table td { padding: 6px 8px; border-bottom: 1px solid var(--line, #e3e7ec); … }` · `.prov th { background: #f6f8fa; }` · `.cr-table th { … padding: 4px 8px; … }` · `.board th { padding: 8px 6px; … }` | 표가 여덟 꼴이다: 칸 안쪽 12/16 · 6/10 · 6/8 · 12 · 4/8 · 8/6 · 3/8px, 머리 바탕 셋(#f4f3f0 · #f6f8fa · 없음), 글자 12 · 12.5 · 13px, 테두리 아래줄만 · 격자(`.prov`) · 점선(`.board td`). 한 화면(지식 관리)에서도 `.prov`(격자)와 `.compact-table`(아래줄)가 섞인다 | 기준 `.compact-table` 하나로: `table { font-size: 13px; } th, td { padding: 8px 12px; border-bottom: 1px solid var(--rule); } th { background: var(--surface-soft); }` 그리고 `.prov` · `.inst-table` · `.cr-table` · `.td-table` · `.board` 의 padding · 머리 바탕 · 테두리 선언을 지운다(글자 크기만 남김). `.board td { border-top: 1px dashed #eef1f4 }`(enterprise.css:416)는 지운다 |
| 16 | 나 | 일관성 · 누르는 칩 | enterprise.css:15-31 · shell.css:127-130 · instances.css:54-55 | `.chiptoggle { … font-size: 12px; … border-radius: 14px; padding: 3px 10px 3px 6px; … }` · `.chip-btn { … height: 30px; padding: 0 12px; … border-radius: 999px; … font-size: 13px; … }` · `.chips.small .chip { cursor: pointer; border: 1px solid transparent; }` | 켜고 끄는 칩이 세 꼴이다 — 지식 지도 층 고르기(모서리 14 · 12px · 높이 약 24), 내 작업함 역할 보기(완전 둥근 · 13px · 30px · 켜짐은 파랑 채움), 실시간 활동 거르기(보통 칩 · 켜짐은 옅은 파랑). 켜짐 표시도 셋이다 | 기준 `.chip-btn`: `.chiptoggle { height: 30px; padding: 0 12px 0 8px; border-radius: 999px; border: 1px solid var(--rule-strong); font-size: 13px; color: var(--ink-2); } .chiptoggle:has(input:checked) { border-color: var(--ink-3); color: var(--ink); } .chiptoggle:has(input:not(:checked)) { opacity: .6; }` 실시간 거르기도 `chip-btn` 클래스로 바꾼다(liveStream.js:219) |
| 17 | 나 | 일관성 · 모서리 | theme.css:219 · 223 · components.css:268 · hitl.css:229-235 · 376(theme) · 460(theme) · trace.css:26 · caseRecord.css:39 | `.card, .detail, .todo-panel, .upload.card { … border-radius: var(--radius); … }` 다음 줄 `.card { … border-radius: var(--radius-sm); … }` · `.msec, .mproc { … border-radius: 6px; … }` · `details.fold { … border-radius: 10px; … }` · `.list .item { … border-radius: 10px; … }` | 카드 8 · 상세 칸 · 설비 카드 · 지식 지도 12 · 접기 · 목록 행 · 처리 과정 단계 10 · 처리 기록 카드 12 · 매뉴얼 절 상자 6px. 특히 `.upload.card`(0,2,0)가 `.card`(0,1,0)를 이겨 **지식 관리의 등록 카드만 12px**, 바로 아래 「등록된 매뉴얼」 카드는 8px이다(코드로 본 추정) | 두 단계로: 바깥 패널(`.detail` · `.unit` · `.onto-map` · `.onto-node` · `.stream-panel`) `var(--radius)` 12, 그 안의 카드 · 접기 · 목록 행 · 표 테두리 · 상자 `var(--radius-sm)` 8, 칩 · 코드 6. theme.css:219에서 `.upload.card`를 빼고, `details.fold` · `.list .item` · `.tr-step` · `.cr-card` · `.msec` · `.mproc` 의 숫자를 `var(--radius-sm)`으로 |
| 18 | 나 | 일관성 · 입력 칸 | styles.css:216-229 · theme.css:412-414 · components.css:68 | `border: 1px solid #cbd5e3;` · `border: 1px solid #d8d7d3; … padding: 0 10px;` · `.field input:not(…) … { … padding: 6px 10px; … border: 1px solid #cbd5e3; }` | 입력 칸 테두리가 두 색이다 — `.field` 안(무게 0,5,1)은 옛 파랑 회색 #cbd5e3, 도구줄 · 목록 머리의 고르기 칸(지식 지도 설비 · 처리 건 상태 등, 0,4,1)은 따뜻한 회색 #d8d7d3. 안쪽 여백도 8/12 · 0/10 · 6/10px 셋 | 한 규칙(theme.css:412-414)만 남긴다: `border: 1px solid var(--rule-strong); padding: 6px 10px; min-height: var(--field-h);` styles.css:216-229와 components.css:68의 border · padding · radius를 지운다 |
| 19 | 나 | 옛 색 하드코딩 | styles.css:278 · 686 · 968 · components.css:27 · 260 · instances.css:59 · enterprise.css:323 · caseRecord.css:76 · 157 · components.css:122 · styles.css:163 · instances.css:29 · 34 | `tbody tr:hover { background: #fafbff; }` · `.summary { … border: 1px solid #dce4ff; … }` · `.ucard.sel { … box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.15); }` · `.card.clickable:hover { border-color: #b8c5e1; }` · `.m-go .card:hover { border-color: #9eafea; }` · `.stream-row:hover { background: #eef2fb; }` · `.prov th { background: #f6f8fa; }` · `.cr-pre { … background: #f8fafc; … }` | 따뜻한 회색 체계(theme) 위에 옛 파랑 계열 색이 곳곳에 남아 표 줄 위에 올리면 푸른 기가 돌고, 카드 테두리가 푸르게 바뀐다(코드로 본 추정) | 올림: `background: rgba(11, 11, 11, .025)`, 테두리: `var(--rule-strong)`, 고른 표시: `box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent)`, 옅은 상자: `var(--surface-soft)` · `var(--paper)`, 회색 점: `var(--ink-4)` |
| 20 | 나 | 정의 안 된 변수 | instances.css:2 · 13 · 14 · 21 · 92 · taskDetail.css:27 · flows.css:7 · 11 | `var(--surface-2, #f3f5f8)` · `var(--line, #d9dee5)` · `var(--line, #e3e7ec)` · `var(--line, #e5e5e5)` · `var(--muted, #6b7785)` · `var(--warn-bg, #fff6dc)` · `var(--neg, #c0392b)` | 없는 토큰을 불러 폴백 숫자가 쓰인다. 같은 `--line`의 폴백이 세 값이고, `--neg`의 폴백 #c0392b는 포털 어디에도 없는 빨강이다(흐름 가져오기 문제 목록 왼쪽 막대) | `--surface-2` → `--surface-soft`, `--line` → `--rule`, `--muted` → `--ink-3`, `--warn-bg` → `--chip-warning-bg`, `--neg` → `--alarm`. 바꾼 뒤 다섯 이름 검색 결과 0 확인 |
| 21 | 나 | `!important` | instances.css:79-81 · trace.css:148 · styles.css:944 · theme.css:548 | `.inst-card.RUNNING { border-left-color: var(--accent) !important; }` · `.stream-list .stream-row { grid-template-columns: 64px 76px minmax(0, 1fr) auto !important; }` · `.scada { grid-template-columns: 1fr !important; }` | 셋은 앞 규칙과 싸우려고 붙였다: `.inst-split .list .item.inst-card`(0,4,0)의 왼쪽 막대, instances.css:58의 같은 격자, 그리고 `.scada`. `.scada`는 components.css:295의 3열(뒤 파일 · 미디어 밖)이 styles.css:1107-1111의 900px 미디어를 덮어 그 미디어가 죽었고, 720px의 `!important`만 일한다 — **720~900px에서는 설비 카드 세 장이 한 줄에 끼어 든다**(코드로 본 추정). (theme.css:548은 처리 흐름 그림 규칙이라 적어만 둔다) | `.inst-split .list .item.inst-card.RUNNING { border-left-color: var(--accent); }`(COMPLETED · CANCELLED 같음)로 바꿔 `!important`를 지운다. trace.css:148의 값을 instances.css:58에 넣고 148을 지운다. components.css:295 바로 뒤에 `@media (max-width: 900px) { .scada { grid-template-columns: 1fr; } }`를 넣고 styles.css:943-945 · 1107-1111을 지운다 |
| 22 | 나 | 위계 · 제목 | theme.css:193 · 194-205 · 230 · components.css:5 · 7 · 10 · 16 · 138 · enterprise.css:136-139 · instances.css:47 · theme.css:611 · hitl.css:312 · 225-227 · shell.css:116 · hitl.js:87 · 199-200 | `.page-head h1, h1 { font-size: 22px; … }` · `h2 { font-size: 15px; … }` · `.card .card-head h3 { font-size: 14px; … }` · `.detail-head h2 { margin: 0; font-size: 18px; }` · `.rr-head h4 { margin: 0; font-size: 15px; … }` · `.onto-node h3 { … font-size: 16px; }` · `<h2 style="font-size:16px">` | 이기는 값으로 보면 h4(결과 보고 15) = h2(절 15) = h3(작업 패널 · 실시간 · 매뉴얼 단계 15) > h3(카드 14)이고, 지식 지도 상세 h3(16)이 절 제목 h2보다 크다. 상세 h2는 18인데 hitl.js:87만 인라인으로 16. 같은 단계 이름이 다른 크기, 다른 단계가 같은 크기다. 목록 C의 다섯 단계를 넣을 때 바꿀 선택자 목록이 필요하다 | C의 단계에 맞춘 선택자: **화면 제목 22** `.page-head h1` / **절 제목 17** `h2.sec, .sec-head h2, .detail-head h2, #instDetail .detail-head h2, .onto-node h3, .ap-title, .confirm-dialog h3` / **카드 제목 15** `.card-title h3, .card .card-head h3, .todo-panel h3, .stream-head h3, .rr-head h4, .mstage-title, .cr-title b, .htitle, .kpi-obj h3, .sec-row h3, .skill-edit h3` / **작은 머리 13 · 600 · ink-2** `.form-section h4, .rel-group h4, .onto-node h4, .kpi-trace h4, .cr-sec-body h6`. 죽은 값(components.css:5 24px · 7 · 10 16px · styles.css:76-82 30px · 929-931 26px)은 지운다 |
| 23 | 나 | 색 유틸이 크기를 바꿈 | styles.css:54-58 | `.muted, .hint { color: var(--ink-3); font-size: 13px; }` | 「회색」 표시가 글자 크기까지 13px로 고정해, 11.5~12.5px 자리에서는 회색 글이 둘레 글보다 커진다. 그래서 `.hopt .hmeta .muted 11.5` · `.ask-q .muted 11.5` · `.hkpi.cond .muted 11.5` · `.stream-head .muted 12` · `.ask-a-head .muted 12.5` 같은 되돌리기 규칙이 생겼다 | `.muted, .hint { color: var(--ink-3); }`(크기 삭제), `.hint { font-size: 13px; margin: var(--s2) 0; }`만 남기고 위 다섯 되돌리기 규칙을 지운다 |
| 24 | 나 | 일관성 · 규칙 표시 | enterprise.css:278-295 · hitl.css:276-278 · 268-269 | `.hard { display: inline-block; font-size: 11px; background: #fde2e5; … border-radius: 3px; …}` · `.hmeta .soft { background: #fff3cd; color: #8a5a00; }` vs `.soft { … color: var(--dmz); … }` | 「제외 · 감점」 표시가 칩(`.chip.tone-danger` · `tone-warning`)과 따로 그려진다 — 모서리 3 vs 6, 글자 11 vs 11.5 vs 12, 노랑 글자색 #8a5a00 vs #986000 두 벌 | 쓰는 곳(hitl.js:204, enterprise.js ruleChip)을 `chip tone-danger sm` · `chip tone-warning sm`으로 바꾸고 `.hard` · `.soft` · `.hmeta .hard/.soft` · `.htitle em.hard/.tx` 규칙을 지운다 |
| 25 | 나 | 초점 표시 | styles.css:962-965 · hitl.css:264 | `.ucard:focus-visible { outline: 2px solid #f5a623; … }` · `.file-picker:focus-within .btn { outline: 3px solid #8298ee; outline-offset: 3px; }` | 포털 초점 색은 `--focus`(#3b78c4, 4.5:1) 하나인데 두 곳만 주황(2.03:1)과 연보라(2.74:1)다 — 둘 다 비글자 기준 3:1 미달. `:focus-within`은 마우스로 눌러도 켜진다 | `.ucard:focus-visible { outline-color: var(--focus); }` · `.file-picker:has(input:focus-visible) .btn { outline: 2px solid var(--focus); outline-offset: 2px; }` |
| 26 | 나 | 없는 클래스 | index.html:126 | `<div class="field wide-2"><label for="decPattern">이상 패턴</label>…` | `wide-2`에 규칙이 없어 「이상 패턴」 고르기가 한 칸 폭이다(뜻은 두 칸) | `.form-grid .wide-2 { grid-column: span 2; } @media (max-width: 640px) { .form-grid .wide-2 { grid-column: 1 / -1; } }` 또는 `wide` |
| 27 | 나 | 간격 눈금 | caseRecord.css 전체(85곳) · theme.css(75) · trace.css(56) · enterprise.css(46) | `.cr-card { … padding: 10px 14px 12px; … }` · `.ap-card { … padding: 16px 18px; margin: 12px 0 16px; … gap: 10px; … }` · `.rr-card { … padding: 14px 16px; margin: 14px 0; … gap: 10px; }` | 카드 안쪽이 10/14 · 16/18 · 14/16 · 12/14 · 7/12px로 카드마다 다르다. 눈금 밖 값(6 · 10 · 14 · 18px)이 약 290번 | 카드 안쪽은 `var(--card-pad)` 하나, 사이 간격은 `var(--s2)` · `var(--s3)` 둘로: `.cr-card, .ap-card, .rr-card, .todo-panel.approve { padding: var(--s3) var(--s4); gap: var(--s2); }` 바깥 여백은 `margin-block: var(--s3)` |
| 28 | 나 | 좁은 폭 | instances.css:58 · trace.css:148 | `.stream-row { display: grid; grid-template-columns: 64px 70px minmax(0, 1fr) auto; … }` | 실시간 활동 줄에 좁은 폭 규칙이 없다. 375px에서 시각 64 · 종류 76 · 걸린 시간 칸 · 간격을 빼면 본문이 약 100px이라 한 글자씩 꺾인다(코드로 본 추정) | `@media (max-width: 640px) { .stream-list .stream-row { grid-template-columns: 52px minmax(0, 1fr); } .stream-row .kind, .stream-row .body, .stream-row .where { grid-column: 2; } .stream-row .dur { grid-column: 2; grid-row: auto; justify-self: start; } }` |
| 29 | 나 | 글자 크기 · 처리 과정 요약 | trace.css:16 · 47 · 105 · 107 | `.tr-status span { font-size: 11px; font-weight: 500; color: var(--ink-3); letter-spacing: .02em; }` · `.tr-act, .tr-gen { font-size: 11px; … }` · `.tr-code-h { … font-size: 11px; … }` | 처리 과정 요약 칸 이름(상태 · 걸린 시간 · 단계 · 도구 호출)과 요청 · 응답 머리가 11px · ink-3(4.43~4.67). Dify 원본의 대문자 이름표 크기를 한글에 그대로 옮겼다 | `.tr-status span, .tr-act, .tr-gen, .tr-code-h, details.tr-code > summary { font-size: 12px; letter-spacing: 0; }` |
| 30 | 나 | 죽은 규칙 · 중복 | 아래 「4. 쓰이지 않는 규칙」의 ② | `.hitl { … border: 1px solid #d9c9f5; … box-shadow: inset 0 3px 0 var(--accent); }`(hitl.css:40) vs `.hitl { … border: 1px solid var(--rule); … box-shadow: none; }`(components.css:205) | 같은 선택자를 뒤 파일이 통째로 덮어, 앞 규칙은 읽어도 아무 일을 하지 않는다. 고칠 사람이 앞 파일을 고치고 「안 바뀐다」를 겪는다 | ②의 앞 규칙을 지우고 뒤 규칙 하나만 남긴다 |

## 4. 지식 쪽 탭 (지식 지도 상세 칸 · 조치 방법 · 지식 관리 · 데이터 원천)

그래프 그림 · 선(`.o-edge` · `.o-node` · `.onto-map` 캔버스)은 다루지 않았다. 아래 번호는 3절과 별개로 센다. 1 · 3 · 11 · 12 · 13 · 15 · 16 · 17번도 이 탭들에 걸린다.

### 4-1. 지식 지도 상세 칸 (`#ontoNode` — enterprise.js:241-264, enterprise.css:119-166 · 480-492)

| 번호 | 무게 | 파일:줄 | 원문 조각 | 무엇이 문제인가 |
|---|---|---|---|---|
| 지-1 | 가 | enterprise.css:149-166 + styles.css:264-285 | `.kvt th { text-align: left; color: var(--ink-3); font-weight: 400; padding: 3px 8px 3px 0; … white-space: nowrap; }` | 지도-1(12px · 영문 키 · nowrap)에 더해: `.kvt th`가 `background`를 지우지 않아 전역 `th { background: var(--surface-soft) }`를 받는다. 왼쪽 안쪽 여백이 0이라 회색 칸 왼쪽 끝에 글자가 붙고, 위아래 3px라 줄이 빽빽하다. 브라우저가 `<tbody>`를 넣으므로 `tbody tr:hover { #fafbff }`의 푸른 올림도 걸린다. 이름표는 회색 칸 위 4.21:1(코드로 본 추정) |
| 지-2 | 나 | enterprise.css:482-489 | `.rel-group { … background: var(--surface-soft); } .rel-group h4 { margin: 0 0 8px; font-size: 13px; … } .rel-note { font-size: 12px; … color: var(--ink-3); }` | 묶음 이름(h4 13px)과 항목 링크(13px)가 같은 크기라 묶음 경계가 약하고, 회색 상자 위 개수 · 관계 이름이 4.21:1이다 |
| 지-3 | 나 | enterprise.css:38-40 · 119-128 · 490 | `#view-ontology { max-width: none; }` · `.onto-node .kv-long { white-space: pre-wrap; … }` | 지식 지도 화면만 1400px 상한이 없어 1920px 화면에서 상세 칸이 약 1600px로 늘고, 긴 설명(`.kv-long`)이 한 줄 150자 넘게 이어진다(코드로 본 추정) |
| 지-4 | 나 | enterprise.css:136-148 | `.onto-node h3 { margin: 2px 0 2px; font-size: 16px; }` · `.o-kind { font-size: 12px; color: var(--ink-2); }` | 항목 이름과 아래 표 사이 여백이 2px + 표 `margin-top: 10px`뿐이고, 종류 표시(설비 · 원인 …)가 이름 바로 위에 붙는다 |

제안 CSS(enterprise.css 끝의 「지식 지도 상세 칸」 묶음을 이것으로 바꾼다):

```css
/* 지식 지도 상세 칸 — 읽기 우선. 그래프 그림 · 선 규칙은 위쪽 그대로 */
.onto-node { font-size: 14px; line-height: 1.6; }
.onto-node .node-head { max-width: 72ch; }
.onto-node .o-kind { font-size: 12px; font-weight: 600; color: var(--ink-3); letter-spacing: .01em; }
.onto-node h3 { margin: 2px 0 var(--s3); font-size: 17px; line-height: 24px; font-weight: 650; }

.kvt { width: 100%; margin: 0; font-size: 13px; border-collapse: collapse; }
.kvt th, .kvt td { background: none; padding: 7px 0; border-bottom: 1px solid var(--rule); vertical-align: top; line-height: 1.5; }
.kvt th { width: 1%; min-width: 6em; max-width: 12em; padding-right: var(--s4); color: var(--ink-2); font-weight: 500; white-space: normal; word-break: keep-all; }
.kvt td { color: var(--ink); overflow-wrap: anywhere; }
.kvt tr:last-child > * { border-bottom: 0; }
.kvt tr:hover { background: none; }
.onto-node .kv-long { max-width: 72ch; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--ink-2); }

.onto-node .node-rels { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--s3); align-content: start; }
.rel-group { margin: 0; padding: var(--s3) var(--s4); border: 1px solid var(--rule); border-radius: var(--radius-sm); background: var(--panel); }
.rel-group h4 { margin: 0 0 var(--s2); padding-bottom: 6px; border-bottom: 1px solid var(--rule); font-size: 12.5px; font-weight: 600; color: var(--ink-2); display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; }
.rel-group h4 .n { font-weight: 500; color: var(--ink-3); font-variant-numeric: tabular-nums; }
.rel-group .rels { margin: 0; padding: 0; list-style: none; display: grid; gap: 2px; font-size: 14px; }
.rel-group .rels li { padding: 2px 0; line-height: 1.5; }
.rel-note { font-size: 12px; font-weight: 400; color: var(--ink-3); }
```

흰 바탕으로 바꾸면 `.rel-note` · `.n`은 4.67:1(3절 3번을 하면 5.48:1)이다. 옛 규칙 enterprise.css:167-179(`.rels` · `.rels li` · `.rels code`)는 위 묶음과 겹치니 지운다(지도-6과 같은 자리).

### 4-2. 조치 방법 (`#skillDetail` — hitl.js:184-216)

| 번호 | 무게 | 파일:줄 | 원문 조각 | 무엇이 문제인가 |
|---|---|---|---|---|
| 지-5 | 나 | hitl.js:199-200 · hitl.css:282 | `` `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">…</h3><ol class="steps">` `` · `.skill-edit ol.steps { margin: 4px 0 8px 18px; padding: 0; font-size: 13px; }` | 「절차」 「연결된 지식」 제목은 인라인 14px(같은 패널의 h2는 18px, 폼 절 제목 h4는 13px). `ol.steps`는 `.skill-edit` 밖에 그려져(hitl.js:208에서 연 `div`가 215에서 닫힌 뒤) hitl.css:282가 한 번도 맞지 않는다 — 절차 목록은 브라우저 기본 여백(왼쪽 40px)으로 보인다 |
| 지-6 | 나 | hitl.js:204 · enterprise.css:278-295 · theme.css:393-404 | `` `<span class="hard">제외 · …${UI.fold('규칙 원문', …, {cls:'small'})}</span>` `` | 11px 인라인 블록 표시 안에 접기(요약 12.5px)가 들어가 표시가 여러 줄 상자로 부푼다(코드로 본 추정, 조치-1의 「JSON 접기」는 내용 지적이고 이것은 모양) |
| 지-7 | 나 | styles.css:552-560 · theme.css:478-483 | `.list .item strong { display: block; font-size: 13px; }` · `.list .item .sub { … font-size: 12px; color: var(--ink-3); … }` | 왼쪽 목록 이름이 13px로 오른쪽 본문(14px)보다 작다. 모든 목록 화면에 같다 |

제안 CSS:

```css
#skillDetail .sub-title { margin: var(--s6) 0 var(--s2); font-size: 15px; font-weight: 600; }   /* hitl.js:199-200의 인라인 style 대신 class="sub-title" */
#skillDetail ol.steps { margin: 0 0 var(--s4); padding-left: 1.4em; display: grid; gap: 6px; font-size: 14px; line-height: 1.6; }
#skillDetail ol.steps .muted { font-size: 12px; }
#skillDetail .kvt td .chip { margin: 0 4px 4px 0; }   /* 지-6: .hard/.soft 대신 chip tone-danger/warning sm, 접기는 칩 밖으로 */
.list .item strong { font-size: 14px; }
.list .item .sub { font-size: 12.5px; }
```

hitl.css:282는 지운다.

### 4-3. 지식 관리 (`#view-knowledge` — index.html:210-244, hitl.css:209-322)

| 번호 | 무게 | 파일:줄 | 원문 조각 | 무엇이 문제인가 |
|---|---|---|---|---|
| 지-8 | 가 | hitl.css:300-301 | `.ddlcols { display: flex; … font-size: .85em; margin-top: 4px; } .ddlcols label { white-space: nowrap; }` | 업무 데이터 연결에서 「어느 열을 쓸지」 고르는 체크 칸 글이 `.msec`(13px)의 .85배 = 약 11px이다. 이 화면에서 학생이 직접 고르는 유일한 칸이 가장 작다 |
| 지-9 | 나 | hitl.css:225-236 · 312 · 321 · 305 · theme.css:398-404 | `.mcols h3 { font-size: 13.5px; … }` · `.msec, .mproc { … border-radius: 6px; padding: 8px 10px; … font-size: 13px; }` · `.mstage-title { margin: 0; font-size: 15px; }` · `.mproc-head > span:first-child { font-size: 14.5px; }` · `.steps3 li { … font-size: 13.5px; }` | 한 화면에 15 · 14.5 · 14 · 13.5 · 13 · 12.5 · 12 · 약 11px 여덟 크기가 있다. 절 · 절차 상자는 모서리 6 · 안쪽 8/10px로 바깥 카드(8 · 16px)보다 빽빽하다 |
| 지-10 | 나 | enterprise.css:308-335 · 448-450 | `.prov { … table-layout: fixed; font-size: 13px; … } .prov th, .prov td { border: 1px solid var(--rule); padding: var(--s3); … } .prov th { background: #f6f8fa; } .prov code { font-size: 11px; …}` | 매뉴얼 등록 이력 · 연결 배치 이력 · DDL 표 → 출처 표 · 뜻 복원 표(hitl.js:418 · 849 · 869, legacyMeaning.js:124)가 칸 폭을 똑같이 나눈다. 짧은 칸(판 · 배치)과 긴 칸(파일 이름 · 설명)이 같은 폭이라 긴 칸만 여러 줄로 꺾이고, 격자 테두리 · 차가운 머리 바탕 · 11px 코드가 다른 표와 다르다(코드로 본 추정) |
| 지-11 | 나 | hitl.css:216-219 · caseRecord.css:66 | `.mprev { border-top: 1px dashed var(--rule); padding-top: 10px; }` | 결과 묶음 경계가 점선이다. 포털의 다른 경계는 실선이라 점선이 「임시 · 미완」처럼 읽힌다 |
| 지-12 | 나 | enterprise.css:180-189 | `pre.tpl { background: #1b2430; color: #dfe5ec; … }` | 「질의 보기」만 어두운 코드 상자다(다른 `pre`는 모두 밝은 `--paper`). A-3대로 개발자 보기로 옮기더라도 모양은 하나로 |

제안 CSS(hitl.css의 매뉴얼 · DDL 묶음):

```css
.mcols { gap: var(--s4); }
.mcols h3 { margin: var(--s2) 0 var(--s2); font-size: 14px; font-weight: 600; }
.msec, .mproc { border: 1px solid var(--rule); border-radius: var(--radius-sm); padding: var(--s3) var(--s4); margin-bottom: var(--s2); font-size: 14px; line-height: 1.6; background: var(--panel); }
.mproc-head > span:first-child { font-size: 15px; font-weight: 600; }
.mstage-title { font-size: 15px; font-weight: 600; }
.steps3 li { font-size: 14px; }
.mprev { border-top: 1px solid var(--rule); margin-top: var(--s4); padding-top: var(--s4); }
.ddlcols { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: var(--s2); font-size: 13px; }
.ddlcols label { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }

.prov { table-layout: auto; width: 100%; font-size: 13px; border-collapse: collapse; background: var(--panel); }
.prov th, .prov td { border: 0; border-bottom: 1px solid var(--rule); padding: 8px 12px; text-align: left; vertical-align: top; }
.prov th { background: var(--surface-soft); color: var(--ink-2); font-weight: 600; font-size: 12.5px; white-space: nowrap; }
.prov td { overflow-wrap: anywhere; word-break: keep-all; }
.prov code { font-size: 12px; background: var(--surface-soft); padding: 1px 5px; border-radius: 4px; }
@media (max-width: 720px) { .prov { min-width: 560px; } }

pre.tpl { background: var(--paper); color: var(--code-fg); border: 1px solid var(--rule); border-radius: var(--radius-sm); }
```

### 4-4. 데이터 원천 (`#fabricView` — fabric.js 전부, 따로 정한 CSS 없음)

| 번호 | 무게 | 파일:줄 | 원문 조각 | 무엇이 문제인가 |
|---|---|---|---|---|
| 지-13 | 나 | fabric.js:86-87 · 115-117 (CSS 규칙 없음) | `` `<h4>${srcChip(id, label)} 연결된 값 ${rows.length}개</h4>` `` · `` `<h4>최신 ${sm.row_count}행</h4>` `` | 맨 `<h4>`라 브라우저 기본(위아래 약 1.33em 여백, 카드 본문 13px 굵게)으로 그려지고, 같은 카드의 `.form-section h4`(13 · 600 · 아래 12px)와 다르다. 칩이 들어가 줄 높이가 어긋난다(코드로 본 추정) |
| 지-14 | 나 | fabric.js:16 · 110-111 · 126 · theme.css:572 | `` const code = (t) => t ? `<code>${esc(t)}</code>` : ''; `` · `.compact-table td … { overflow-wrap: normal; word-break: keep-all; }` | 열 이름 · `표.열` 경로가 바탕 없는 고정폭 글이고, 표 칸이 줄바꿈을 막아 긴 경로가 표를 옆으로 민다. 「어디서 왔나」가 가로 스크롤 뒤로 숨는다 |
| 지-15 | 나 | fabric.js:28-37 · theme.css:256-265 | `` `<b>${s.ok ? '연결됨' : '연결 실패'}</b>` `` · `.stat-cards .card b { font-size: 22px; … }` | 숫자용 큰 글(22px)에 「연결됨 · 없음 · 확인 실패」 같은 낱말이 들어가 요약 카드가 낱말 포스터처럼 보인다. 아래 보조 줄(12px)은 긴 문장이다 |

제안 CSS:

```css
.fab-body, #fabResult { display: flex; flex-direction: column; gap: var(--s4); }      /* 3절 12번 */
.fab-body h4 { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2); margin: var(--s4) 0 var(--s2); font-size: 14px; font-weight: 600; }
.fab-body h4:first-child { margin-top: 0; }
.compact-table code { font-size: 12px; background: var(--surface-soft); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; word-break: normal; }
.compact-table small { display: block; margin-top: 2px; font-size: 12px; color: var(--ink-3); line-height: 1.45; }   /* 3절 11번 */
.fab-body .stat-cards .card b, #fabricView .stat-cards .card b { font-size: 17px; line-height: 24px; }
#fabricView .stat-cards .card small { line-height: 1.45; }
```

## 5. 쓰이지 않는 규칙

판정 방법: CSS 선택자의 클래스 · id를 뽑아 `index.html`의 `class` · `id`와 모든 `*.js`의 문자열(따옴표 · 백틱 안)에서 찾고, 일반 낱말(`scn` · `who` · `action` · `lane` · `state` …)은 `class="…"` · `className` · `classList` · `el('태그', '클래스')` 꼴로 다시 찾았다. 접두어로 만드는 이름(`tr-k-${kind}` · `k-${kind}` · `st-${state}` · `tone-${tone}` · `lane-${lane}`)은 쓰는 것으로 봤다. 서버가 HTML을 주는 곳은 없다(코드로 확인). 화면을 띄워 재지 않았으므로 「쓰는 곳을 찾지 못함」이다.

**① 어디에서도 쓰지 않는 선택자**

| 파일:줄 | 선택자 |
|---|---|
| enterprise.css:193-217 · 441-443 | `.scn` · `.scn.on` · `.scn h3` · `.scn p` (main.js의 `'scn'`은 그림 칸 키) |
| enterprise.css:219-231 | `.dec-head` · `.dec-head h2` |
| enterprise.css:233-255 | `.persp` · `.persp button` · `small` · `.on` |
| enterprise.css:257-277 | `.skills` · `.skills span` · `span i` · `.skills .none` |
| enterprise.css:296-307 | `.drivers` · `.drivers span` |
| enterprise.css:338-345 · 406-411 | `.who` · `.who label` |
| enterprise.css:346-367 · 412-414 · 453-471 · styles.css:286-288 | `.opts` 전체(표 → 카드 꼴 바꾸기 포함) · `.table-scroll .opts` |
| enterprise.css:419-429 | `.linked` · `.linked a` |
| styles.css:91-96 | `.eyebrow` |
| styles.css:289-316 (+ components.css:39 · theme.css:330-331의 `.state`) | `.state` · `.state.CLEARING` · `.state.RUN` · `.state.TRIP` · `.state.RAISED` · `.state.CANDIDATE` |
| styles.css:568-602 | `.lane` · `.lane .st` · `.done` · `.now` · `.fail` · `.lane small` |
| styles.css:643-683 | `.action` · `header` · `.code` · `.param` · `input[type=range]` · `ol` |
| styles.css:717-731 · 940-942 | `#caption` · `body.present #caption` (`present` 클래스를 넣는 코드가 없다 — `<div id="caption">`만 남음) |
| styles.css:1016-1021 · components.css:46-62 | `.chip.trip` · `.chip.raised` · `.chip.candidate` · `.chip.auto` · `.chip.manual` · `.chip.run` · `.chip.inc` (칩은 모두 `UI.chip` → `tone-*`) |
| hitl.css:9-21 | `.bpmn` · `@keyframes bPulse` |
| hitl.css:280-281 | `.dec-run` · `.dec-run input[type=number]` |
| hitl.css:282 | `.skill-edit ol.steps` (마크업이 `.skill-edit` 밖 — 지-5) |
| instances.css:21-22 | `.rework-preview` · `pre` (JS의 `rework-preview`는 API 주소) |
| instances.css:89 | `@keyframes stepGlow` |
| components.css:222 | `.box` |

**② 쓰이지만 뒤 파일이 통째로 덮어 아무 일도 하지 않는 규칙**(앞쪽이 죽음)

| 죽은 규칙 | 이기는 규칙 |
|---|---|
| hitl.css:40-46 `.hitl` | components.css:205 |
| hitl.css:48-58 `.hopt` · 99-102 `.htitle`(14px) · 120-139 `.hbar` · 145-151 `.hkpi span` · 720px 미디어 255-258 `.hopt` | components.css:190 · 192(15px) · 195-197 · 200 (미디어 밖 규칙이 뒤에서 덮어 좁은 폭 규칙도 죽음) |
| styles.css:793-797 1200px 미디어 `.stream-ticker { max-width: 200px; … }` | instances.css:37 `max-width: 320px`(뒤 파일 · 미디어 밖) |
| styles.css:1107-1111 900px 미디어 `.scada` | components.css:295-300 (3절 21번) |
| enterprise.css:368-373 `.boards`(auto-fit 420) · 720px 미디어 445-447 | components.css:208 · 212 |
| hitl.css:210-215 `.upload` | components.css:268 · theme.css:219 |
| instances.css:17 `.todo-panel { margin }` · components.css:220의 radius | theme.css:219(radius 12) |
| instances.css:37 `.stream-ticker`의 배경 · 모서리 | theme.css:554 |
| instances.css:45 `.stream-panel`의 radius · shadow | components.css:216 |
| instances.css:11 `.inst-table { font-size: .88em }` | components.css:224(13px) |
| instances.css:84 `.inst-card .steps`의 margin | theme.css:542 |
| theme.css:543 `.step-chip` | instances.css:85 `.inst-card .step-chip`(무게가 높다) |
| enterprise.css:3-6 `.dot.off` | components.css:145(같은 내용) |
| hitl.css:290 · 293 `.golden-counts` · `.golden-answer` | components.css:291-292(같은 내용) |
| styles.css:76-82 `h1`(30px) · 929-931(720px 26px) | theme.css:193(22px, 미디어 밖이라 좁은 폭에서도 22) |
| components.css:5 `.page-head h1 { font-size: 24px }` | theme.css:193 |
| components.css:7 · 10 `h2.sec` · `.sec-head h2`(16px) | theme.css:205(15px) |
| styles.css:271-276 `th`의 굵기 · 색 | theme.css:517 |
| styles.css:426-434 `.detail`의 padding | theme.css:241-244(20px 22px) |
| theme.css:219의 `.card` 모서리 | 바로 아래 theme.css:220-229 |
| styles.css:216-229 입력 칸의 border · padding | theme.css:412-414(`.field` 밖) · components.css:68(`.field` 안) |
| styles.css:31-34 `button:disabled { opacity: .55 }` | theme.css:327(.45) |

## 6. 인라인 `style=` (목록 C에 수가 있어 대표 자리와 옮길 클래스만)

`style="` 78곳(instances.js 13 · enterprise.js 12 · whatif.js 8 · hitl.js 8 · agents.js 7 · app.js 6 · kpi.js 5 · oilInput.js 4 · taskDetail.js 3 · index.html 3 · 그 밖 6). 그 가운데 그때그때 값이 바뀌어 남겨야 하는 것은 셋뿐이다(enterprise.js:213 `--c`, 270 층 색, 362 점수 막대 폭).

| 자주 쓰는 값 | 수 | 옮길 클래스 |
|---|---|---|
| `margin:0` | 17 | `.summary.prose > p { margin: 0; } .summary.prose > p + p { margin-top: var(--s2); }` |
| `font-size:14px;margin:var(--s4) 0 var(--s2)` 류(h3) | 7(hitl.js:199-200 · enterprise.js:535 · 537 · instances.js:757-758 · 324) | `.sub-title { margin: var(--s6) 0 var(--s2); font-size: 15px; font-weight: 600; } .sub-title:first-child { margin-top: 0; }` |
| `margin-top:var(--s4)` · `var(--s3)` · `var(--s6)` | 14 | `.mt-3 · .mt-4 · .mt-6` 셋, 또는 감싸는 쪽에 `display: grid; gap` |
| `white-space:pre-wrap;overflow-wrap:anywhere` | 4(hitl.js:548 · 580 · 598) | `.pre-line { white-space: pre-wrap; overflow-wrap: anywhere; }` |
| `margin:0 0 var(--s2)` | 5 | `.summary.prose > p:not(:last-child)`로 흡수 |

## 7. 못 읽은 것 · 재지 못한 것

- CSS 16개는 모두 처음부터 끝까지 읽었다.
- `index.html`은 7~22 · 86~260행만 읽고 나머지는 검색했다. JS는 `fabric.js` 전부, `enterprise.js` 225~274행, `hitl.js` 160~239행, `ui.js`의 마크업 함수 자리만 읽고, 나머지는 클래스 · `style=` · 변수 이름 검색으로만 훑었다. 그래서 「쓰이지 않는 규칙」은 문자열 검색 판정이다 — 검색하지 않은 꼴(예: 배열에 클래스 이름 조각을 넣고 이어 붙이는 곳)으로 만드는 이름이 있으면 ①에서 빠져야 할 것이 있을 수 있다.
- 화면을 띄우지 않아 실제 계산된 스타일 · 넘침 · 카드 붙음(12번) · 칩 넘침(13번) · 좁은 폭(28번)은 **미검증**(코드로 본 추정)이다. 확인은 개발자 도구의 계산된 스타일이나 `test_portal_ui.py` 화면 순회 사진(1366 · 1920 · 375)으로 한다.
- 대비는 토큰 값으로 계산했다. 반투명 테두리 · 그림자 · 그라데이션 위의 글자(`.tr-status`의 흰→바탕 그라데이션)는 양 끝 값으로만 어림했다.
- 그래프 그림 · 선(지식 지도 `.o-*` 규칙, 홈 그림 `.m-*`)과 처리 흐름 그림(`.f-*`)의 모양은 범위 밖이라 보지 않았다(21번의 theme.css:548은 `!important` 목록에 적기만 했다).
