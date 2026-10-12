# 완료 정비 영수증 표시 계약

저장된 작업지시·SMTP 본문·결과 보고·과거 평가는 변경하지 않는다. 성공한 WO_CREATE 영수증의 원문 detail이 정확히 `Source-scoped maintenance orders registered`이고 after.plan/after.orders의 설비 및 작업지시 번호가 일치할 때에만 원문 범위의 한국어 설명을 파생한다. 자유문과 미상 영수증은 그대로 표시한다. 보고 요약은 동일 영수증 번호와 알려진 시스템 생성 요약 틀을 확인한 경우에만 표시를 파생한다. 원문 접기는 저장 값을 유지한다.

incident_closed는 이 보고가 수행한 종결 동작 여부다. 현재 사건 상태는 별도 조회 결과로 표시하고 조회 중·실패를 종결로 추정하지 않는다.

새 SQL 058은 056의 ent.exec_skill 본문을 보존하며 미래 생성 detail만 Memory의 한국어와 맞춘다. 기존 거래 갱신이나 재실행은 하지 않는다. 원천 본문과 새 본문에서 해당 표현을 역치환한 결과가 정확히 같음을 검사했다.

참고: ProcessGPT 최신 캐시 docs/en/architecture.md(6ad9db604898efa2c16fa2e364d7317a93a3ee87)의 영속 처리 기록과 도구 실행 분리, ontology-studio frontend/src/features/files/FilePanel.vue(6a229be8dcce2aeb533ecdba360b5b4564ffb777)의 원본과 표시 결과 구분을 직접 검토했다. 한국어 업무 설명은 자체 Memory 생산자 state.py의 기존 의미를 따른다.

검증: 실제 완료 B 영수증, 원문 불변, 미상/불일치 영수증, 자유문, 보고 동작 false와 현재 CLOSED, 조회 실패/대기 경계를 집중 검사한다. 실제 B 결함 PNG는 기존 증거로 보존한다. 라이브 쓰기·LLM·기존 기대값 변경은 하지 않는다.
