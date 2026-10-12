# 교육용 ERP 결손 정정 — 적용 근거 인덱스

앞선 GET에서 필터 master/stock이 없는 사실은 정확했으나 이를 사용자가 제공해야 하는 외부 실제 창고 자료의 결손으로 분류한 것은 잘못이었다. 실제 `it/supabase/seed.sql`·`it/enterprise-sim/entsim/data.py`는 교육용 ERP 출발 데이터를 정의한다. 교육 시나리오에 필요한 정식 fixture를 우리가 준비해야 하며 사용자에게 모르는 재고 자료를 요구하지 않는다. 이 정정은 기존 B 판단·원문을 덮거나 당시 unknown을 성공으로 바꾸는 방식이 아니다.

## 시간 순서와 실제 적용

- [b-data/result.json](b-data/result.json)·[독립 검증 result](b-verification/result.json)은 **공유 운영DB 적용 전** offline/isolated PostgreSQL 검증 시점이다. 그 파일의 shared_DB_changes0·실제B운영미실행 제한은 당시 사실로 보존한다.
- 이후 루트가 공식 migration057을 실제 적용했다. [official-fixture-applied.json](official-fixture-applied.json)은 fixture `B-ERP-20261012-v1`, migration SHA `b8fb2541e153f9b4822749a1328db40d501b7f1778b0e50ee511313a5f7cc857`, 기존 ERP행 불변·반복 적용 불변·기존B/C history 불변을 기록한다. 추가된 교육용 필터 master1행/stock1행의 단가12·실물2는 **명시 교육 설계값**이며 외부 창고 관측이나 PM 원문에서 발견한 수량/가격이 아니다.
- [single-service-deployment.json](single-service-deployment.json)은 enterprise-sim만 배포하고 healthy 확인한 근거다. process를 재시작하지 않았다. [source-delta.json](source-delta.json)은 해당 변경 소스 범위를 남긴다.
- [isolated-db-cleanup.json](isolated-db-cleanup.json)은 분리 검증DB 정리를 기록한다. 기존 운영 DB와 분리된 bootstrap은 [bootstrap.json](b-verification/bootstrap.json)·[bootstrap.log](b-verification/bootstrap.log)·[bootstrap.py](b-verification/bootstrap.py)에 보존한다.

## 시험 원문과 부정 확인

[focused-first.log](b-verification/focused-first.log)은12통과0.89초, [nearest-pg.log](b-verification/nearest-pg.log)은기존 PostgreSQL 관련1통과0.46초다. 별도 범위이며 이전 전체2673/UI18/F27을 재실행한 결과가 아니다. [missing-filter-fault.log](b-verification/missing-filter-fault.log)의1실패0.15초는 필터행을 제거하면 원래 positive acceptance가 production ScopeError로 실패하는 **의도적 fault 검증**이다. 실패를 성공으로 잡아 바꾸지 않았다. [fault script](b-verification/test_missing_filter_fault.py)와 시험/소스 SHA는 result에 남겼다.

## 복사 정확성과 현재 제한

[write-proofs-copy-manifest.json](write-proofs-copy-manifest.json)은16개 명시 파일의 원본 경로/bytes/SHA256와 복사 후 SHA 일치를 기록한다. 운영DB 적용 파일은 [apply-official-fixture.py](apply-official-fixture.py)로 수집·실행 경로를 재검토할 수 있으나 이 문서 작업에서 다시 실행하지 않았다. 큰 현재B GET 원문은 로컬 H에만 남기며 이 인덱스가 전체 업무 JSON을 중복하지 않는다.

현재 실제 B는 사용자 지정 Sol6.1의 별도1회 재평가가 진행 중이다. 이 기록은 fixture 적용과 해당 검증 근거이며 B 승인/오더/공지/완주 결과가 아니다. Google 계정동의·외부 연결·회의 실행도 미완료로 유지한다. 최종 실제 결과의 README/NOW/일일 보고 통합은 루트가 담당한다. 이번 복사는 제품·라이브·NOW·일일 보고·스테이징을 변경하지 않았고 기존 성공/실패 원문을 그대로 보존했다.
