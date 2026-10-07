// L9 → L1: layer responsibilities and the components used in this lab.
// health: URL polled every 5 s (JSON /healthz for our services; opaque fetch for third-party UIs).
const H = location.hostname || 'localhost';
const P = (port) => `http://${H}:${port}`;

const LAYERS = [
  { no: 'L9', name: '프로세스 · 승인 · 앱', role: '권고를 승인하고 조치를 실행', zone: 'it', focus: true, comps: [
    { name: 'process', role: '승인 → 명령 전송 → 결과 확인 → 종결', zone: 'it', url: P(8080) + '/docs', health: P(8080) + '/healthz' },
    { name: 'portal', role: '설비 관찰·판단·승인을 수행하는 화면', zone: 'it', url: P(8088), health: null },
    { name: 'enterprise-sim', role: '생산·정비·품질 등 기업 시스템 모의 실행', zone: 'it', url: P(8095) + '/docs', health: P(8095) + '/healthz' },
  ]},
  { no: 'L8', name: 'AI 에이전트', role: '근거를 조회하고 조치를 권고', zone: 'it', focus: true, comps: [
    { name: 'agent', role: '원인·조치·부서별 영향을 비교 · 직접 제어 권한 없음', zone: 'it', url: P(8091) + '/docs', health: P(8091) + '/healthz' },
  ]},
  { no: 'L7', name: '온톨로지 · 원인분석', role: '서로 다른 분야의 지식을 연결', zone: 'it', focus: true, comps: [
    { name: 'Neo4j', role: '설비·고장·매뉴얼·스킬·조직의 관계 저장', zone: 'it', url: P(7474) + '/browser/', health: P(7474) },
  ]},
  { no: 'L6', name: '관제 · SCADA · 인프라 감시', role: '설비 상태와 데이터 추이를 확인', zone: 'mixed', comps: [
    // A122 F10: FUXA is an optional tool — when it is not running the portal shows "선택 도구 꺼짐", not a failure.
    { name: 'FUXA', role: '설비 감시·수동 조작·운전 모드 전환', zone: 'ot', url: P(1881), health: P(1881) + '/api/settings', optional: true },
    { name: 'Grafana', role: '센서 추이와 경보·조치 이력 시각화', zone: 'it', url: P(3000) + '/d/hyd-trend', health: P(3000) + '/api/health' },
    { name: 'Prometheus', role: '서비스 상태와 처리량 수집', zone: 'it', url: P(9090), health: P(9090) + '/-/ready', optional: true },
  ]},
  { no: 'L5', name: '시계열 저장소', role: '관측값과 사건을 시간순으로 보관', zone: 'it', comps: [
    { name: 'connect-sink', role: '이벤트를 받아 시계열 DB에 기록', zone: 'it', url: P(8094) + '/docs', health: P(8094) + '/healthz' },
    { name: 'TimescaleDB', role: '센서값·경보·명령·감사 이력 저장', zone: 'it', url: P(3000) + '/explore', health: null },
  ]},
  { no: 'L4', name: '스트림 처리 · CEP', role: '연속된 데이터에서 이상을 탐지', zone: 'it', comps: [
    { name: 'detector', role: '1초 단위 특징 계산 · 경보 발생·해제 판정', zone: 'it', url: P(8092) + '/docs', health: P(8092) + '/healthz' },
  ]},
  { no: 'L3', name: '이벤트 백본', role: '데이터와 명령을 각 서비스로 전달', zone: 'mixed', comps: [
    { name: 'connect-ingest', role: '현장 MQTT 데이터를 분석망으로 전달', zone: 'dmz', url: P(8093) + '/docs', health: P(8093) + '/healthz' },
    { name: 'cmd-gateway', role: '승인된 명령을 검증한 뒤 현장으로 전달', zone: 'dmz', url: P(8090) + '/docs', health: P(8090) + '/healthz' },
    { name: 'Redpanda', role: 'Kafka 호환 이벤트 저장·분배', zone: 'it', url: P(8085) + '/topics', health: P(9644) + '/v1/status/ready', entryHealth: P(8085), entryName: '메시지 조회 화면' },
  ]},
  { no: 'L2', name: 'IoT 미들웨어 · MQTT', role: '현장 장치와 메시지를 주고받음', zone: 'ot', comps: [
    { name: 'EMQX', role: '센서값·상태·명령을 중계하는 MQTT 브로커', zone: 'ot', url: P(18083), health: P(18083) + '/status' },
  ]},
  { no: 'L1', name: '센서 네트워크 · 설비', role: '현장을 계측하고 설비를 구동', zone: 'ot', comps: [
    { name: 'plant-sim', role: '유압설비 3기·PLC·센서를 모의 실행', zone: 'ot', url: P(8000) + '/docs', health: P(8000) + '/healthz' },
  ]},
];

const API = {
  plant: P(8000), gateway: P(8090), detector: P(8092), agent: P(8091), process: P(8080), grafana: P(3000),
};
