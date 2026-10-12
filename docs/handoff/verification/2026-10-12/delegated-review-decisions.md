# 사용자 위임 자동검토 — 세 문서 정본 초안

최신 사용자 지시로 원문 대조·검토·적재를 Codex에 명시 위임했다. 실제 검토 신원은 **사용자위임 Codex자동검토**이며 사람이나 특정 직원의 신원을 주장하지 않는다. 이전 감사의 “사람 검토 전 적재 불가”는 이 위임 전 상태의 기록이다. 이번 초안은 root가 실물과 적용 조건을 확인한 뒤 공식 경로로 처리하며, 감사자는 그래프 쓰기나 적재를 수행하지 않았다.

정본 초안은 [delegated-review-draft.json](D:/work/study/hyd-iot-edu/.evidence/final-completion-20261012/delegated-review-draft.json)이다. 한 파일에 `apply_review_records[doc]`를 묶었다. scripts/c3_ingest.apply_review는 문서별 기록 하나를 받으므로 wrapper 전체를 --review에 전달하지 않는다. 실제 source_id/document_id/extraction과 by·warnings_read를 넣었고 reviewed 플래그나 실행 본문을 자동 만들지 않았다.

## 직접 확인한 원문·실행 연결

| 문서 | 실제 제안/원천 연결 | 원문 대조 |
|---|---|---|
| HM-8 | document c2bb4c58-3d7b-4df6-ad4d-1d3023db7755 / extraction394d8cab-ecf9-4927-8b64-8e5116374dc1 | sample의 SHA-256이 archive/proposal의6a1a66a6…와 일치. 인용50개 좌표/문자열, warnings18개 전부 확인 |
| PM-02 | document6c306bfa-7ac2-46a0-b48c-3402a995ab57 / extraction914896d0-e074-4359-a6e9-66be38267201 | sample의 SHA-256이2a757bd4…와 일치. 인용62개 좌표/문자열, warnings23개 전부 확인 |
| PR-07 신규2.4 | documentc8305e9b-b8f1-4261-b6ac-0490e36de173 / extractione7d00281-5325-4b26-ab7f-21e2e31ffd74 | sample의 SHA-256이7cb1c01d…와 일치. 인용41개 좌표/문자열, warnings14개 전부 확인 |

총153개 인용과55개 경고를 확인했다. 적용 후보의 quote는 원문에서 정확히 한 번만 등장한다. `source_decisions`에 세 문서의 절차/관계22개, 규칙18개, 원인5개와 고장 유형2개의 원문 인용·보존 이유·조건을 담았다. evidence=[]와 관측 조건/가중치 미상 사유도 명시했다. 원문에 없는 PLC 허가, evidence 가중치, 역할, 고장 유형, 고정 공급사를 만들지 않았다.

## 현재 적용 후보 — PM의 두 command 제외

| 대상 | 초안 변경 | 실제 원문·Action 계약 |
|---|---|---|
| SOP-PM-12 | actions에서 controlled-stop만 제외. 기존 action:work-order/SOP-PM-12는 유지 | 원문은 생산 중인 오더/설비를 정지하고 이번 차례 패키지의 정비 오더를 발행한다. Action STOP은 actr:pump-drive 대상의 command다. 현장/업무 정지를 원격 PLC 권한으로 번역하지 않으며 kind를control로 바꾸지 않음 |
| SOP-PM2-9 | actions=[]로 원격 LOAD_SET 연결 제외 | 원문은 정비 뒤 부하90%·15분 시운전과 PS1/FS1/VS1 합격 조건이다. 이것을 독립 원격 명령 승인으로 읽지 않음. 90%·15분·센서 기준과 기존 원문 단계는 그대로 보존 |

각 변경은 apply_review의 `links[SOP]={set,quote,reason}` 형식을 따른다. 직접 확인한 원문 quote로 command 번역을 제외하며, 추가 PLC 값이나 승인 역할을 선택하지 않는다. 두 번째 절차의 독립 승인자는 미상인null 그대로다. validator가 이null을maint-mgr로 기본 대체하면 이 초안의 판단과 다르므로 root가 실행 전에 확인해야 한다.

## 조건부 추가/제외 — 아직 적용 기록에 넣지 않음

PM-02의 기존 cause:particle-contamination은 원문의 fm:volumetric-loss·prior0.3과 seed의 작동유 열화·prior0.25가 같은 ID에 섞이는 문제가 있다. `conditional_changes_not_applied`에는 원래 제안 Cause를 drop하고 문서 소유 cause:pm02-oil-contamination을 add하는 후보를 quote/reason과 함께 담았다. 새 이름·확률·부품·FM 문맥은 모두 PM-2.10의 명시 문장에 근거하며 새 고장 유형이나 evidence 가중치를 추가하지 않는다.

다만 같은 개념의 원인을 중복 생성하는지, 실제 기존 노드와 관계의 의미/소유권이 무엇인지 root의 실제 조회와 도메인 판단이 필요하다. 이 후보는 `apply_review_records`에 병합하지 않았고 현행 seed prior나 다른 문서의 노드를 바꾸지 않는다. root가 이 방식을 채택하면 병합 후 구조/원문/graph를 다시 검증해야 한다.

## root 확인에 따른 마무리 조건

| 묶음 | 원문을 대조해 내린 판단 | 적용 전 조건 |
|---|---|---|
| HM 기존 문서/Skill | COOL-11~15는 원문 번호이고 기존01~05로 바꾸지 않는다. FAN-11/12는 미상 승인/작업지시 발행 방식을 그대로 남긴다 | 실제 `_manual_document`/현재source/doc와 신규preview의doc가 같은지 확인. 다른문서/관리자 소유를 덮지 않으며 기존 Skill 의미를 추정해 다른 FM에 옮기지 않음 |
| HM 회복 판정 | 원문의15분 TS1<55·경보 해제 유지 조건을 보존해야 한다. 현재excerpt에 있으나SOP-HM8-6 steps에는 성공 확인 단계가 빠져 있음 | apply_review는 단계 추가/절차 제외/번호 교정을 지원하지 않음. root가 별도 원문 보존 수정 제안을 준비하고 추출/검토 연결을 재검증 |
| PM 패키지·측정 | 현재 방식 SOP를 특정 누적 패키지로 고정하지 않는다. evidence60초를seed120초/가중치로 대신하지 않는다 | 누적 시행 차례·후보 부하/다른 설비 조건·미명시 감점 지표 입력은 실제 근거가 없으면 추가하지 않음 |
| PR 업무 모델 | FM 없는 발주·정책·검증 절차를 원문대로 보존한다. 새 FM/role을 채워 validator를 통과시키지 않음 | 진행 중인 FM-free 업무 지원에서 graph/schema/후보/시스템/미상 역할이 일관돼야 함 |
| PR 공급사·비용 | OEM/단가 낮은 대체 승인·전체 최단 뒤AVL 검사·구매 담당 승인1회·명시20만원을 보존 | sup:b/sup:a는 현재부품별 실제견적/공급사분류를root가 재대조하기 전 확정하지 않음. 비용20의지표단위/집계를 원문없는빈도계수로 채우지 않음 |

원문과 원자 조치의 대응이 있는 부분만 변경 후보로 삼았다. 현재 proposal의 미상 연결이나 누락을 성공으로 표시하지 않았으며 자동검토 위임을 없는 값을 만들라는 허가로 해석하지 않는다. root는 wrapper의 실행 전 조건과 문서별 객체를 확인한 후 공식 apply_review/preflight/commit을 진행한다.

ProcessGPT 모노레포의 문맥/감사/HITL과 ontology-studio의 source/target_schema/구조 검증 분리를 참고했다. 검토 신원, 원문 좌표, 변경 전후, 실제 source/instance를 함께 남기는 HYD 계약을 지켰으며 참고 제품에 같은 SOP/스키마/정책이 있다고 주장하지 않는다.
