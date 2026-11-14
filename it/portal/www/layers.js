// L9 → L1: 계층의 할 일과 이 시스템의 부품(교재 1회차 02 의 아홉 계층과 같은 이름 · 같은 차례). 시스템 구성 화면(app.js renderStack)과 상태 확인(pollHealth)이 이 표 하나를 읽는다.
// role = 하는 일, real = 현업에서 같은 자리에 있는 것(화면이 「현업에서는 …」으로 보인다), zone = 영역(ot · dmz · it).
// 서비스 주소는 이 파일 하나가 만든다.
//  - API: 화면이 데이터를 읽고 쓰는 길 — 포털과 같은 출처의 /svc/<서비스 이름>(nginx.conf 가 그 서비스로 넘긴다).
//    서비스는 다른 출처 요청을 받지 않는다(CORS 없음). 화면 파일은 `API.process + '/api/…'` 처럼 이 표만 쓴다.
//  - P(port): 사람이 새 탭으로 여는 도구 화면(서비스 문서 · Grafana · FUXA · Neo4j Browser · EMQX …)과 그 도구들의 켜짐 확인.
//    이 PC에서 다른 프로그램과 겹쳐 옮긴 포트가 있으면 그 포트로 연다("8080=18080 3000=13000", nginx가 화면에 끼워 넣음).
// health: 5초마다 확인하는 주소 — 우리 서비스는 같은 출처 /healthz(JSON), 바깥 도구는 그 포트에 닿는지만(opaque fetch).
const H = location.hostname || 'localhost';
const PORT_MAP = Object.fromEntries(String(window.HYD_PORTS_RAW || '').split(/\s+/).filter(Boolean).map(kv => kv.split('=').map(Number)));
const P = (port) => `http://${H}:${PORT_MAP[port] || port}`;
const SVC = (name) => `/svc/${name}`;
const API = {
  process: SVC('process'), agent: SVC('agent'), ent: SVC('enterprise-sim'), plant: SVC('plant-sim'), detector: SVC('detector'), gateway: SVC('cmd-gateway'),
};

const LAYERS = [
  { name: '프로세스 · 승인 · 앱', role: '권고를 승인하고 조치를 실행', zone: 'it', focus: true, comps: [
    { name: 'process', role: '승인 → 명령 전송 → 결과 확인 → 종결', real: '업무 프로세스 엔진(BPM)', zone: 'it', url: P(8080) + '/docs', health: API.process + '/healthz' },
    { name: 'portal', role: '설비 관찰 · 판단 확인 · 승인을 하는 화면', real: '운영 포털 · 업무 화면', zone: 'it', url: P(8088), health: null },
    { name: 'enterprise-sim', role: '생산 관리 · 정비 관리 · 구매 · 재고 시스템을 모의 실행', real: 'ERP · 정비(CMMS) · 구매 시스템', zone: 'it', url: P(8095) + '/docs', health: API.ent + '/healthz' },
  ]},
  { name: 'AI 에이전트', role: '근거를 조회하고 조치를 권고', zone: 'it', focus: true, comps: [
    { name: 'agent', role: '지식 그래프를 읽어 원인 · 조치 후보 · 부서별 영향을 계산 · 설비를 직접 제어할 권한 없음', real: '의사결정 지원 서비스', zone: 'it', url: P(8091) + '/docs', health: API.agent + '/healthz' },
    // 2026-10-25: 포털의 AI 단계(판단 · 제안, 질문, 매뉴얼 추출)를 하는 AI 에이전트. 꺼지면 그 단계만 멈추므로 상태 점에 보인다
    { name: 'agent-worker', role: 'AI 에이전트 실행 서비스 — 판단 · 제안, 질문 응답, 매뉴얼 추출을 수행', real: 'AI 에이전트 실행 환경', zone: 'it', url: P(8097) + '/healthz', health: SVC('agent-worker') + '/healthz' },
  ]},
  { name: '온톨로지 · 원인분석', role: '서로 다른 분야의 지식을 연결', zone: 'it', focus: true, comps: [
    { name: 'Neo4j', role: '설비 · 고장 · 매뉴얼 · 조치 방법 · 조직의 관계를 저장', real: '그래프 DB(지식 그래프 저장소)', zone: 'it', url: P(7474) + '/browser/', health: P(7474) },
  ]},
  { name: '관제 · SCADA · 인프라 감시', role: '설비 상태와 데이터 추이를 확인', zone: 'mixed', comps: [
    // FUXA 는 기본 서비스다(compose 에 프로필이 없다) — 선택 도구로 표시하지 않는다. 선택 프로필은 monitor(Prometheus)와 tools 뿐이다.
    { name: 'FUXA', role: '설비 감시 · 수동 조작 · 운전 모드 전환', real: 'SCADA · HMI', zone: 'ot', url: P(1881), health: P(1881) + '/api/settings' },
    { name: 'Grafana', role: '센서 추이와 경보 · 조치 이력을 그래프로 표시', real: '분석 · 추이 대시보드', zone: 'it', url: P(3000) + '/d/hyd-trend', health: P(3000) + '/api/health' },
    { name: 'Prometheus', role: '서비스 상태와 처리량 수집', real: '인프라 감시 도구', zone: 'it', url: P(9090), health: P(9090) + '/-/ready', optional: true },
  ]},
  { name: '시계열 저장소', role: '관측값과 사건을 시간순으로 보관', zone: 'it', comps: [
    { name: 'connect-sink', role: '이벤트를 받아 시계열 DB에 기록', real: 'Kafka Connect 같은 싱크 커넥터', zone: 'it', url: P(8094) + '/docs', health: SVC('connect-sink') + '/healthz' },
    { name: 'TimescaleDB (Grafana 탐색 화면에서 조회)', role: '센서값 · 경보 · 명령 · 감사 이력 저장', real: '히스토리언(시계열 DB) — 사이트 히스토리언은 OT 쪽에도 둡니다', zone: 'it', url: P(3000) + '/explore', health: null },
  ]},
  { name: '스트림 처리 · CEP', role: '연속된 데이터에서 이상을 탐지', zone: 'it', comps: [
    { name: 'detector', role: '1초 단위 특징 계산 · 경보 발생과 해제 판정', real: '스트림 처리 · CEP 엔진', zone: 'it', url: P(8092) + '/docs', health: API.detector + '/healthz' },
  ]},
  { name: '이벤트 백본', role: '데이터와 명령을 각 서비스로 전달', zone: 'mixed', comps: [
    { name: 'connect-ingest', role: '현장 MQTT 데이터를 분석망으로 전달', real: 'Kafka Connect 같은 커넥터', zone: 'dmz', url: P(8093) + '/docs', health: SVC('connect-ingest') + '/healthz' },
    { name: 'cmd-gateway', role: '승인된 명령을 검증한 뒤 현장으로 전달', real: 'DMZ의 명령 검증 · 중계 서버', zone: 'dmz', url: P(8090) + '/docs', health: API.gateway + '/healthz' },
    { name: 'Redpanda', role: 'Kafka 호환 이벤트 저장 · 분배', real: 'Apache Kafka(같은 규약)', zone: 'it', url: P(8085) + '/topics', health: P(9644) + '/v1/status/ready', entryHealth: P(8085) },
  ]},
  { name: 'IoT 미들웨어 · MQTT', role: '현장 장치와 메시지를 주고받음', zone: 'ot', comps: [
    { name: 'EMQX', role: '센서값 · 상태 · 명령을 중계하는 MQTT 브로커', real: 'MQTT 브로커(IoT 미들웨어)', zone: 'ot', url: P(18083), health: P(18083) + '/status' },
  ]},
  { name: '센서 네트워크 · 설비', role: '현장을 계측하고 설비를 구동', zone: 'ot', comps: [
    { name: 'plant-sim', role: '가상 유압 설비 3기와 PLC · 센서를 모의 실행', real: '실제 설비 · 센서 · PLC — 안전계장(SIS)은 제어와 따로 둡니다', zone: 'ot', url: P(8000) + '/docs', health: API.plant + '/healthz' },
  ]},
];
