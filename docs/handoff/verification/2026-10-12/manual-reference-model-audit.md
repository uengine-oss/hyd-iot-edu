# 매뉴얼 원문 보존·기존 Skill 참조·비실행 절차 계약 감사

2026-10-12 Codex Sol 6.1 읽기 감사. 원문 검토와 적재는 사용자가 위임했으며 실제 검토 신원은 `사용자위임 Codex자동검토`다. 이 기록의 설계 판단은 사람 신원을 가정하지 않는다. 초기 감사에서 공유 제품 파일과 실제 그래프는 쓰지 않았다. 후속 구현은 root가 별도로 위임했고 구현·시험 결과를 마지막 절에 추가한다.

## 확인한 실제 충돌

`delegated-review-20261012/existing-procedures-and-ownership.json`의 FAN-11·12와 실제 HM proposal을 대조했다. SOP 번호·각 4단계의 순서와 문자열이 **정확히 일치**한다. proposal의 `existing_skill_id`도 `skill:sop-fan-11/12`다. 그러나 `manual_review.validate`는 이 필드를 checked plan으로 전달하지 않고, `manual_graph.desired`는 항상 `skill_id(p.id)`의 새 소유 노드를 만든다. `_validate_targets`가 기존 Skill과 SOP 번호를 발견해 충돌하는 것은 정상적인 덮어쓰기 방지다. 같은 문서를 새 SOP 번호로 바꾸어 통과시키면 원문과 단일 SOP 계약을 훼손한다.

단계 동일성은 전체 실행 계약 동일성을 뜻하지 않는다. 기존 `HM-8.1` excerpt에는 VS1 **1.2** mm/s가 있고 최신 HM 원문에는 **0.9**가 있다. 기존 노드의 속성·Role·Action·FM 관계와 active Step/Section을 통째로 최신 원문으로 교체하는 것은 별도 개정이며, 이번 재참조만으로 허용되지 않는다. 새 source의 0.9 원문은 새 문서 소유 Section·Step에 보존하고 기존 실행 설명 1.2는 변경하지 않아야 한다. 조회 화면에서도 두 판본의 차이를 표시해야 한다.

COOL-11~15와 seed COOL-01~05는 단순 재사용 대상이 아니다. `instances.cypher:281` 이후 seed에는 같은 유형의 조치가 있지만 번호·문장·출처 절이 다르며 02/03의 승인은 생산관리자다. 최신 HM-8의 12/13은 운전원 승인이다. 같은 개념 후보라는 비교를 기록할 수 있지만, 번호가 다른 절차를 자동 alias로 재사용하거나 중복 실행 Skill을 새로 만드는 결론은 나오지 않는다. 새 원문을 그대로 보존하고 명시적 개정/대체 관계를 검토해야 한다.

기존 seed 지식은 journal 소유가 없다고 무소유인 것이 아니다. HM/PM Cause·FM의 기존 ID와 실행 의미는 seed/admin 소유다. 특히 `cause:particle-contamination`은 현재 prior 0.25와 `fm:oil-degradation` 관계를 가진다. PM-2.10은 작동유 오염을 prior 0.3, 펌프 체적 효율 저하의 원인으로 서술한다. 동일 개념인지·범위가 다른지 판단 없이 기존 prior를 0.3으로 덮거나 새 ID로 충돌을 피해선 안 된다. `card.rank_causes`는 prior를 실제 점수에 사용하므로 수치 변경은 실행 결과 변경이다.

## 원문과 실행을 구별하는 최소 확장

기존 KnowledgeSource·ManualSection·Skill·Step을 유지한다. 새 Procedure/Revision 클래스 묶음을 만들 필요는 없다. 기존 Skill에 새 문서의 source Step을 active `HAS_STEP`로 추가하면 `t2_skills/t3_skills`가 원문 4단계와 기존 4단계를 모두 읽어 카드가 8단계가 된다. 따라서 **`Step-[:DOCUMENTS]->Skill` 관계 한 종류**를 source provenance 전용으로 추가한다. 기존 `HAS_STEP`는 실행 계약의 현재 단계만 가리킨다. 새 source Step은 자신의 `REFERS_TO` Section과 citation/source_id를 유지하고, 정확히 재사용한 경우에만 DOCUMENTS로 기존 Skill을 가리킨다.

재사용 plan에는 `existing_skill_id`, 대상의 `sopId`, active 단계의 순서·문자열, 대상 계약 해시와 소유 판정을 담는다. 자기 문서가 소유한 새 Step·Section·관계와 참조한 외부 Skill을 journal에서 별도로 기록한다. 외부 Skill은 `nodes/owned_keys`에 넣지 않는다. 이 문서의 `_manual_document`를 기존 Skill/Step에 붙이거나 기존 승인·Action·FM·시스템 관계를 쓰지 않는다.

새 source-backed 절차에는 **명시 `kind=reference`, `executable=false`**를 허용한다. FM·승인 역할이 없거나 현장 확인/회복 판정만 있는 원문도 Step·Section으로 보존할 수 있다. 참고 절차는 실행 시스템, Action, candidate Rule OUTPUTS, 실행 FM 관계를 갖지 않는다. 알려진 source-only 절차를 work_order로 기본 분류하거나 빈 승인자를 maint-mgr로 채우지 않는다. 기존 fault/control/work_order의 FM·승인·실행 요구는 그대로 유지하고 이 명시 reference 분기에만 예외를 둔다.

원문 SOP 번호가 기존 Skill과 다르면 DOCUMENTS 재사용을 거절한다. 내용이 같아 보이는 것만으로 alias를 만들지 않는다. 동일 개념 후보가 발견된 COOL 사례는 source 원문 보존과 실행 개정 결정을 분리하며, root의 검토 기록 없이 새 중복 실행 후보를 활성화하지 않는다. source-only 보관 성공을 실제 조치·정비·발주 완주로 보고하지 않는다.

## 검증과 journal 계약

재사용 검증은 preview와 commit 모두에서 한다. 대상이 유일한 Skill이고 SOP 번호가 정확히 같아야 하며, **현재 active HAS_STEP의 order/text와 source의 전체 단계가 동일**해야 한다. 한 단계 누락·추가·내용 변경·중복 order·다른 SOP·없는 대상은 거절한다. 새 문서의 FM/승인/Action 제안을 외부 Skill에 적용하지 않는다. 그 제안과 기존 실행 계약의 차이는 검토 기록에 남긴다.

계약 해시는 Skill 속성, Role 승인 관계, CONSISTS_OF Action과 값·target, 시스템 수행 관계, FM 연결, active Step 속성과 해당 Section을 포함한 canonical snapshot에서 계산한다. 내부 Neo4j elementId와 CHOSE 같은 실행 이력, 다른 문서의 검증된 DOCUMENTS provenance는 해시 입력에서 제외한다. 그렇지 않으면 정당한 실행 이력 추가가 계약 변경으로 보인다. source 단계 hash와 전체 계약 hash를 구별한다. 전자는 재사용 자격, 후자는 검토 뒤 변경 방지다.

preview가 조회한 해시를 그대로 reviewed plan에 pin하고 commit에서 같은 잠금 안에 다시 읽는다. 해시가 달라졌다고 현재 값을 자동 채워 통과시키지 않는다. 승인이 바뀌거나 Action 값이 바뀌거나 기존 Section excerpt가 바뀌면 원문 Step이 같아도 409로 재검토를 요구한다. reference에 관한 해시·입력·대상을 plan fingerprint와 before/after batch 기록에 포함한다. 같은 batch UUID에 다른 reference 판단은 기존 idempotency 계약대로 거절한다.

## foreign provenance·개정·rollback

현재 `_snapshot`은 소유 노드에 닿는 모든 관계를 journal과 비교하며 `DecisionCase-CHOSE->Skill`, `Incident-DIAGNOSED_AS->Cause`만 HISTORY로 분리한다. 검증 없는 DOCUMENTS incoming을 이 목록에 넣거나 관계 이름만 보고 무시하면 drift 방어가 무너진다. **검증된 외부 source provenance를 HISTORY와 다른 범주로 분리**해야 한다.

허용되는 DOCUMENTS는 다른 ACTIVE 문서 journal이 정확한 Step·edge를 소유하고, Step/Section/source_id/citation이 해당 보관 원문·source hash에 맞으며, 대상 Skill과 문서 tenant·SOP·계약 pin이 확인된 경우뿐이다. `_manual_document` 문자열만 신뢰하지 않는다. journal 없는 edge, 삭제/변형된 Step, 틀린 대상, source 좌표 위조, rolled-back 문서 edge는 일반 foreign drift로 거절한다. 의심스러운 incoming을 삭제해 맞추지 않는다.

참조하는 문서의 개정/rollback은 자신의 Section·source Step·DOCUMENTS edge만 변경한다. 외부 Skill·active Step·seed Section·Role·Action은 unchanged여야 한다. 대상 계약이 달라졌다면 자동 재결합하지 않고 재검토를 요구한다. 대상을 소유한 문서의 개정/rollback은 검증된 참조가 들어오는 노드를 삭제하거나 실행 계약을 변경할 때 의존 문서의 pin을 깨뜨리지 않아야 한다. 의존 참조가 있으면 원자적 거절 또는 명시적으로 검토된 의존 문서 개정을 먼저 처리한다. 단순 조회/소유 판 변경만으로 참조 기록을 지우지 않는다.

기존 CHOSE/DIAGNOSED_AS HISTORY는 현재 보존 계약대로 유지한다. 다만 그래프의 CHOSE는 안정 Skill ID만 가리키며 원문 판본 전체를 담지 않는다(`case_projection.DECISION_CASE_Q`). 원래 결정 저장소의 approved card·steps·policy_sha256·citation이 당시 값을 보존하는지 검증해야 한다. 현재 Skill 화면만 보고 과거 결정 때의 원문·Role을 재구성하지 않는다. 이력 보존과 현재 source 재참조는 서로 다른 계약이다.

## 실행 소비자와 완료 판정

reference 보관을 schema/validator 한 곳에서만 허용하면 충분하지 않다. candidate SELECT OUTPUTS가 reference를 가리키는 것을 거절하고, t2/t3 후보 조회·cards의 scope 필터·권고 guardrail·승인 재조회·실제 서비스 실행에서도 reference 또는 explicit executable=false를 거절해야 한다. 직접 Skill ID로 승인/실행을 요청하는 우회도 막아야 한다. 기존 FM 요구를 전역 optional로 바꾸거나 no-op Action을 넣지 않는다.

PM에서 실제 `PREVENTED_BY`와 source-backed package 후보·승인·WO_CREATE는 별도로 완성해야 한다. PM 시운전/회복 판정 원문을 reference로 저장하는 것만으로 업무 오더를 닫거나 계수기 reset을 완료했다고 할 수 없다. PR 구매 모델의 기존 Part/ERP/supplier_policy/executable 계약은 그대로 보존하며 reference 경계만 공통으로 적용한다. 원문에 없는 supplier·PLC 명령·prior·evidence weight는 만들지 않는다.

“전체 매뉴얼 적재”는 원본 bytes/hash·모든 페이지·source Section/Step·검토 기록 보존과, 실행에 검증된 관계의 활성화를 각각 보고한다. 실행할 수 없는 절차도 보관되지만 실제 A/B/C의 PENDING을 성공으로 바꾸지 않는다. source별 바인딩/비실행/충돌 수, 변경하지 않은 기존 Skill ID·계약 해시, 원문 누락 검사와 되돌리기 결과가 receipt에 필요하다.

## 필요한 회귀 계약

| 검증 대상 | 합격 조건 |
|---|---|
| FAN 동일 SOP 재참조 | 기존 Skill·active 4단계·기존 Section/Role/Action bytes/속성 unchanged, 새 source 4단계만 DOCUMENTS로 보존 |
| 다름/누락/추가/번호 | 409/검증 거절, source와 기존 그래프 어느 것도 부분 변경 없음 |
| preview 뒤 대상 변경 | 역할·Action 값·active Step·Section 변화마다 pin mismatch, 재검토 없이 자동 통과 불가 |
| source-only | FM/Role 미상 허용, kind reference·executable false, 시스템/Action/Rule 실행 연결 없음 |
| source-only 실행 우회 | candidate Rule·직접 승인·시스템 실행 모두 실패, 기존 fault와 purchase의 기대 그대로 |
| reference 문서 rollback | 소유 source Step/edge만 제거·복원, 외부 Skill/active Step과 HISTORY unchanged |
| 참조 대상 삭제/변경 | 검증된 의존 문서가 있으면 원자적 거절, 외부 edge 무조건 ignore 불가 |
| 위조 provenance | `_manual_document`만 붙인 edge, journal 없는 edge, 변형 인용, 다른 source/tenant가 모두 drift 거절 |
| 여러 문서와 최신 판 | 두 문서 참조·같은 문서 개정·latest-first rollback·replay가 journal pin을 보존 |
| 원문 수치 차이 | 기존 1.2·새 source 0.9 둘 다 보존되고 판본 차이를 조회 가능, prior 0.25 unchanged |

독립 Neo4j의 실제 commit→revision→rollback→negative drift를 root가 순차 실행해 확인해야 한다. unit desired snapshot 비교만으로 실제 원자성·외부 참조 보호를 판정하지 않는다.

## 코드 근거와 참고

- `manual_sources.py`의 `_view/_read/validate_anchor`: original·페이지 text hash와 실제 source 좌표 검증.
- `manual_review.py`의 `validate`: 전체 원문 검증, source-backed plan, 현행 source 승인 fallback과 existing_skill_id 누락 지점.
- `manual_graph.py`의 `desired/_validate_targets/_snapshot/_replace/commit/rollback`: 소유 snapshot·foreign drift·원자적 쓰기·latest-first undo.
- `manual_knowledge.py`의 `validate/graph_semantics/check_graph/desired`: Action·Rule·Cause 소유 및 실행 활성화.
- `kgadmin.py`의 `validate_skill/skill_id`, `skill_graph.py`의 `write`: 단일 SOP·기존 소유권/Role/실행 시스템 기본값.
- `it/neo4j/v2/schema.json`: 기존 HAS_STEP Skill→Step, REFERS_TO Step→ManualSection, DERIVED_FROM은 Rule/AnomalyPattern만 허용. 새 provenance를 기존 DERIVED_FROM에 임의로 넣지 않는다.
- `t2_skills.cypher/t3_skills.cypher`: active HAS_STEP를 곧 카드 단계로 소비하는 쿼리.
- `agentsvc/cards.py`, `guardrail.py`, `approval.py`, `procsvc/case_projection.py`: 후보·승인 당시 계약·Skill 이력의 소비 경로.
- `tests/test_manual_revision_history.py`, `test_manual_revision_http_neo4j.py`: 실행 HISTORY 보존, drop/foreign drift 원자적 거절의 기존 기준.

ProcessGPT monorepo의 `completion_automated-task-execution/spec.md`는 실행 도구와 그 결과/실패 기록을 워크아이템에 명시한다. 원문을 읽었다고 실행 결과를 만들어선 안 된다는 경계로 대조했다. ontology-studio의 `ontology_mcp/sources.py`·`adapters.py`는 실제 읽은 node ID에서 출처를 회수하고 안전한 source record를 돌려준다. 여기서도 실제 source 노드/좌표와 계약 pin으로 출처를 연결하며 명칭만의 추정 연결은 하지 않는다.

## 후속 구현 상태

root가 구현을 위임했고 read_audit가 공유 manual/schema 쓰기 종료를 확인했다. purchase·supplier_policy 변경을 보존한 상태에서 reference 분기와 별도 provenance 검증을 추가했다. 실제 메인 graph 쓰기·배포는 root 소유다.

공유 소스 구현을 완료했다. 새 `manual_references.py`가 explicit reference shape·정확한 기존 SOP/전체 단계 재사용·대상 계약 pin·활성 journal로 검증한 provenance를 담당한다. `manual_review`는 참고 단계가 실제 source quote 안에 있는지도 확인하고 기존 Skill 바인딩은 reference 분기에서만 받는다. source의 미상 승인자는 maint-mgr로 채우지 않는다. source-only 새 Skill은 `kind=reference/executable=false`로 보관하며 실행 연결이 없다. 기존 Skill 재참조는 새 원문 Step을 DOCUMENTS로만 붙이고 기존 노드/active HAS_STEP의 소유권과 값을 바꾸지 않는다.

카탈로그의 `skills[].reference_contract`는 `{id,sopId,owner,contract_sha256,steps:[{order,text}],sections:[{id,ref,title,excerpt,source_id?,citation?}]}`를 제공한다. Section은 실제 등록값만 표시하므로 seed의 source_id/citation이 없으면 등록된 기존 설명임을 구분한다. reviewed 입력의 `procedure.existing_skill_id`·`procedure.reference_contract_sha256`를 검증하고, receipt의 `references[SOP]`에 target hash와 `source_steps_sha256`을 별도로 남긴다. 같은 필드를 link에 넣으면 checked procedure로 정규화한다.

현재 provenance 검증은 ACTIVE 문서의 head batch·snapshot·plan fingerprint, 원문 Step/Section/KnowledgeSource 속성, 인용 source_id와 실제 REFERS_TO/PART_OF/DOCUMENTS 관계를 대조한다. DOCUMENTS는 중복이면 거절하고 source 참조 Step이 active HAS_STEP에 섞여도 허용하지 않는다. 검증된 보존 결과는 receipt의 `provenance_kept`로 실행 `history_kept`와 구별한다. 다른 문서가 pin한 소유 Skill의 삭제/실행 계약 개정은 원자적으로 거절한다. source 문서 rollback도 현재 pin과 복원할 이전 plan의 pin을 검사해 오래된 계약으로 자동 복귀하지 않는다.

schema에 DOCUMENTS 한 종류와 reference enum을 추가했고 **46개 클래스/74개 관계**로 정본 산출물을 생성했다. FM 필수의 예외는 명시 reference에만 추가하고 graph integrity는 false·source provenance·실행 연결 없음까지 검사한다. read_audit가 기존 purchase graph 검사에 reference AND executable=false만 연결했으며 Part/supplier_policy의 범위 요구를 유지했다. 그는 t2/t3·cards·guardrail·approval의 비실행 경계를 맡았고, root는 실제 서비스 실행 경계를 맡는다. 이 감사자의 구현만으로 전체 실행 경계 배포가 끝났다고 보고하지 않는다.

초기 범위 회귀는 **147 통과·21 건너뜀, 8.03초, exit 0**였다(`delegated-review-20261012/manual-reference-unit.log/xml`). 당시 독립 Neo4j 환경이 없어 actual 시험은 건너뛰었다. 이후 root가 빈 독립 DB를 제공해 `test_manual_references.py`·`test_manual_revision_history.py`·`test_manual_revision_http_neo4j.py`를 실제 실행했고 **51 통과·건너뜀/실패/오류 0, 21.67초, exit 0**를 확인했다. 정본 근거는 `delegated-review-20261012/pytest-reference-history-approved.log/xml`이다. 이전 reference 단독 33 통과·23.14초 기록도 보존했다.

실제 독립 DB에서 두 source 재참조·원문 개정/rollback·HISTORY 보존, Role/Action/active Section/Step pin drift, 문서 소유 대상 삭제/개정 거절, 위조 태그·중복 DOCUMENTS·source Section/journal 변조·이전 pin 복원 거절을 통과했다. 임시 DB 첫 시작 2회 실패는 root가 원본 로그를 보존했고, tmpfs에서 기본 로그 사전 할당이 공간을 넘긴 문제에는 rotation 크기 16 MiB를 적용했다. transaction logging·preallocation과 검사 기대는 유지했다. 초기 단위 실패(비구매 false의 공통 검사 미연동 등)도 원인을 수정했으며 기대를 낮추지 않았다. **메인 그래프 쓰기는 0**이고 실제 사용자 매뉴얼 적재/배포·A/B/C 완주는 이 독립 시험과 별도로 root가 수행한다. 마지막 schema gen 결과는 46개 클래스/74개 관계이며 소유 경로의 diff whitespace 검사는 통과했다.
