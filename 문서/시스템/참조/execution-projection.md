# 실행 그래프의 저장·복구

PostgreSQL의 `bpm_proc_inst`와 `todolist`가 원천이다. Neo4j는 그 시점의 파생 조회 모델이다. API의 그래프 내용은 Neo4j에서 읽으며 원천 DB 값으로 대체하지 않는다.

## 저장과 재시도

마이그레이션 `20261004000011`은 원천 INSERT/UPDATE/DELETE와 같은 트랜잭션에 `execution_projection_outbox` 행을 추가한다. 작업 RPC나 직접 SQL 변경도 포함한다. 원천 트랜잭션이 취소되면 대기 행도 취소된다. 기존 인스턴스는 마이그레이션에서 한 번 재투영 대상으로 등록한다.

인스턴스 모드의 poller는 자신의 tenant에서 한 번에 최대20개 인스턴스를 처리한다. PostgreSQL repeatable-read 트랜잭션에서 대기 행·인스턴스·작업을 읽고 트랜잭션을 닫은 후 Neo4j에 쓴다. 네트워크 전송 중 업무 행을 잠그지 않는다. 전송자끼리의 별도 advisory lock과 Neo4j revision fence로 중복/늦은 쓰기를 제어한다.

Neo4j가 반환한 원천 식별자·revision·payload hash가 모두 일치하는 영수증을 확인한 뒤 **읽었던 대기 행의 정확한 ID들**에 처리 시각을 남긴다. sequence 번호가 작아도 나중에 커밋될 수 있으므로 `id <= 최대값` 방식으로 처리하지 않는다. 일반 전송 실패는 오류·횟수를 남기고5초 뒤 다시 시도한다. 영수증 불일치는 아래 명시적 복구가 필요하다. 전송 중 새 변경은 다음 대기로 남는다. Neo4j 커밋 직후 프로세스가 죽으면 다음 실행에서 같은 원천을 다시 투영한다.

원천이 삭제되거나 `is_deleted=true`면 해당 실행 노드·작업 노드를 그래프에서 제거한다. 별도 `ExecutionProjection` 제어 노드는 마지막 revision을 보존하여 오래된 전송이 삭제된 실행을 다시 만들지 못하게 한다. 이 노드는 업무 지식/새 온톨로지 클래스가 아니다. 고유 제약은 `scripts/ontology_v2.py`가 생성하는 constraints에 포함된다.

## 상태 확인

`GET /api/instances/{id}/graph`의 `projection`에는 `pending`, `last_error`, `last_revision`이 있다. `graph.instance.projection_revision`은 실제 Neo4j 값이다. 그래프 조회 자체가 실패하면 기존 API 오류 경로로 응답한다. 포털 인스턴스의 「그래프 반영 상태」는 선택 실행의 PG 대기와 전체 사건·판단의 SQLite 대기를 구분해서 표시한다. 조회 실패를0건으로 표시하지 않는다.

```sql
select tenant_id, proc_inst_id, count(*) as pending,
       max(last_error) as last_error
from execution_projection_outbox
where processed_at is null
group by tenant_id, proc_inst_id;
```

프로세스 서비스와 Neo4j 연결이 회복되면 일반 전송 오류는 자동 재시도한다. 과거 실패를 숨기기 위해 대기 행을 삭제하지 않는다. 현재 서비스가 처리하지 않는 다른 tenant의 대기 행은 자동 처리되지 않는다. legacy 모드에는 이 PG poller가 없다. 배포 시 SQL 마이그레이션과 Neo4j fence 고유 제약을 먼저 적용한다. 원천/그래프 revision 불일치의 명시적 복구 범위는 아래 A049를 따른다.

## 검증과 남은 경계

A043: 수정 전 복구 누락·오래된 호출 상태 반영 두 실패 재현, 전체657 passed, 실제 PG/Neo4j14항목, 서비스 재시작/API4항목. 실제 검사기 `scripts/probe_execution_projection.py`는 전용 tenant/실행을 보존한다. 합성 업무 fixture이며 Codex·PLC 실행 증거가 아니다.

**pending=0은 그래프의 모든 의미 연결이 맞다는 뜻이 아니다.** 누락된 역할/프로세스 연결은 `warnings`로 남는다. A048의 지식 조인 재확인은 아래 범위로 적용한다. 완료된 outbox 행의 보존/보관 정책은 아직 별도 구현하지 않았다.

## 사건·판단의 SQLite 투영 (A044)

`Store.save`는 업무 snapshot과 `case_projection_outbox`를 같은 트랜잭션에 저장한다. outbox 저장에 실패하면 업무 snapshot 변경도 취소된다. 전송 payload는 저장된 snapshot에서 만들며 호출자가 들고 있는 오래된 객체를 직접 투영하지 않는다. 원천 해시가 같은 감사 로그만의 변경에는 새 전송을 만들지 않는다. 기존 SQLite를 처음 열 때 현재 원천을 자동 등록한다.

legacy/instance 모드 양쪽에서 별도 복구 loop가 사건을 먼저, 판단을 다음에 전송한다. 일반 전송 실패는5초 뒤 재시도한다. 전송 중 더 최신 원천이 저장되면 새 대기로 남긴다. `CaseProjection` 제어 노드의 revision은 오래된 쓰기와 삭제 뒤 부활을 막는다. 같은 revision의 재시도는 payload hash도 같을 때만 허용한다.

활성 사건도 현재 상태·이유·실제 명령 참조·업무 참조를 투영한다. 판단은 기존 계약대로 선택된 APPROVED/EXECUTED/PARTIAL만 DecisionCase로 투영하고, 실제 상태를 별도 속성에 둔다. APPROVED를 성공 실행으로 간주하지 않는다. 없는 원천 Incident를 만들어 관계를 채우지 않으며, DecisionCase의 해당 관계는 대기에 남긴다. 사건 원천이 도착하면 재시도하고, 사건 투영 뒤 PG 연결 재투영 등록까지 성공해야 사건 outbox를 처리 완료로 표시한다.

사건 삭제/변경은 의존 판단의 관계도 다시 처리한다. 자산·진단 원인·역할 등 제거되거나 변경된 관계는 옛 값을 남기지 않는다. 없는 지식 노드는 원천을 만들지 않고 그래프 노드의 `projection_warnings`에 남긴다. 기준 Decision 노드가 없어도 다른 관계 기록 전체가 중단되지 않는다.

`GET /api/graph-projections`는 전체 사건·판단 `pending`, 최대100개 대기 원천/오류, 복구 loop의 `worker_running`을 반환한다. 이 API와 포털은 업무 완료 판정이 아니다. 실제 A044 검사에서 명령이 조건 변화로 보류된 실행은 그래프 대기0이어도 업무 `PENDING`으로 남는다.

A044 검증: 전체666 passed, 별도 실제 SQLite/PG/Neo4j16항목, 가동 데이터/API6항목(사건120건 상태 대조 포함), 포털1440/390 화면 확인. 별도 실제 쿨러 경로는 승인 후 현재 예측 악화로 명령이 보류되어 **실패**했다. 강제 종료된 검사기를 정상 완주로 세지 않는다. 새 Codex 실행 증거가 아니다. 상세 원문/다음 복구 작업은 HANDOFF §9 A044 및 A045를 따른다.

## 지식 연결 변경 재확인 (A048)

기본15초 간격으로 투영이 사용하는 지식 노드의 식별자·실제 노드 ID와 `Process/HAS_NODE/FlowNode` 멤버십을 읽는다. 대상은 Asset, AnomalyPattern, Cause, Decision, Skill, Role, System, Process다. 조회 결과가 바뀌면 현재 tenant의 PG 실행 원천과 SQLite 사건/판단의 저장된 snapshot을 다시 투영하도록 등록한다. 알려진 삭제 원천도 포함한다. 버전별 정의, 과거 판단과 승인, 작업 출력은 바꾸거나 재실행하지 않는다. 기존 노드의 이름 등 속성만 변경하면 연결 대상 노드에서 바로 조회된다.

PG 재등록 후 SQLite outbox와 지식 체크포인트를 함께 커밋한다. 두 저장소 사이 중단은 다음 처리에서 PG 등록이 중복될 수 있지만 누락되지 않는다. 그래프 I/O 실패 시 체크포인트를 전진시키지 않는다. 투영 자체가 만든 노드는 변경 감시에서 제외하여 스스로 반복 등록하지 않는다. 현재는 변경된 조인 대상이 있으면 해당 tenant의 알려진 원천 전체를 등록하며, 실제 전달은 기존20건 배치로 처리한다. 데이터가 많으면15초가 전체 반영 완료 시간은 아니다.

재투영 시 기존 MAPS_TO를 현재 멤버십에 맞게 교체하고 누락된 의미 FlowNode는 경고로 표시한다. `/api/graph-projections`의 `knowledge`는 마지막 확인 시각, 조회 오류, 관찰한 digest와 큐 등록 체크포인트를 제공한다. 체크포인트는 그래프 전송 완료를 의미하지 않으므로 실행/사건 pending과 warnings를 함께 확인한다.

검증 범위: 전체700·실제SQLite/PG/Neo4j10·가동API6. 누락 지식 추가, 의미 멤버십 제거/복원, 같은 ID 노드 재생성, 저장소 사이 실제 처리기 종료/복구, 판단·동의·작업 원문 불변을 확인했다. 이는 지식 의미의 자동 추론이나 새 에이전트 판단 검증이 아니다. 변경 영향 원천만 선별하는 최적화는 후속이다. 투영 훼손과 revision 불일치는 아래 별도 복구 절차를 사용한다.

## 충돌 보류와 명시적 복구 (A049)

빈 응답 또는 다른 식별자/revision/hash를 반환한 쓰기는 `ProjectionConflict:`로 기록한다. 해당 원천은 대기에 남고 자동 전송이 보류된다. 새 outbox 행이 생겨도 보류를 우회하지 않는다. 더 큰 revision을 자동 발급하여 덮어쓰지 않는다. 포털은 「원천·그래프 비교 필요」로 표시한다. 구버전 fence에 hash가 없는 경우에도 동일 revision 재전송은 성공으로 간주하지 않는다.

운영자는 현재 업무 원천을 권위 있는 데이터로 사용해도 되는지 먼저 비교한다. `inspect`는 업무 원천, 고정된 실행 정의/작업, 그래프와 fence, 대기 오류를 파일로 남긴다. 사건 복구 계획에는 연결된 판단의 원천·그래프도 포함된다. 예시는 실행 인스턴스 대상이며 사건/판단은 `--kind Incident|DecisionCase`를 사용한다.

```powershell
docker compose exec -T process python -m procsvc.projection_repair inspect --kind Execution --id <instance-id> --tenant hyd --file /tmp/repair-plan.json
docker compose cp process:/tmp/repair-plan.json ./repair-plan.json
# 파일의 원천·그래프·의존 판단 범위를 검토한 후, 이 요청에 사용할 UUID를 한 번 생성해 보존한다.
$repairRequest = [guid]::NewGuid().ToString()
docker compose exec -T process python -m procsvc.projection_repair apply --file /tmp/repair-plan.json --by <actor> --reason <reason> --request-id $repairRequest
```

검토 후 원천이나 비교 대상 그래프가 달라졌으면 새로 inspect한다. apply는 업무 원천을 변경하지 않고, 관찰한 fence보다 높은 revision으로 투영을 재등록한다. 삭제 원천의 tombstone도 유지한다. 사건을 다시 만들 때 의존 판단도 재등록하고, 정상 사건 전달이 PG 실행 연결 재등록으로 이어진다. 복구 의도·비교본·요청 UUID·결과는 큐와 같은 저장소 트랜잭션에 남는다. PostgreSQL 원장은 마이그레이션 `20261004000012`, SQLite 원장은 Store 초기화로 생성한다.

`QUEUED`는 접수 결과다. 이후 정상 전송기의 정확한 영수증 확인과 API pending/warnings 및 실제 관계를 확인해야 복구 완료다. 응답을 잃었거나 서비스를 재시작했으면 **동일 계획 파일·actor·reason·요청 UUID**로 apply를 반복하여 저장된 결과를 확인한다. 같은 UUID를 다른 복구 의도에 재사용하면 거절한다.

A049 검증: 전체713 passed/2 warnings, 실제 SQLite 백업 복원·PG/Neo4j 격리 불일치·영수증/삭제/의존 관계11항목, 가동 서비스 CLI·사건 전체 노드 복원·업무 불변·재시작/요청 재전송9항목. PG 검사는 그래프 fence를 앞세운 불일치이며 PG 전체 백업 복원 시험이 아니다. 여러 업무 DB의 완전한 재해 복구나 투영만 훼손된 경우의 자동 탐지를 보장하지 않는다. 새 Codex·PLC 실행 검증도 아니다. 근거는 HANDOFF §9 A049에 있다.
