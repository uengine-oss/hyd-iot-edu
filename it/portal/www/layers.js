// L9 → L1 layer map (v3 architecture, page 4) with the student-edition component and its entry point.
// health: URL polled every 5 s (JSON /healthz for our services; opaque fetch for third-party UIs).
const H = location.hostname || 'localhost';
const P = (port) => `http://${H}:${port}`;

const LAYERS = [
  { no: 'L9', name: '프로세스 · 승인 · 앱', role: 'HITL 승인 · 역할 기반 전사 판단 승인 · 기업 시스템 실행', zone: 'it', focus: true, comps: [
    { name: 'process (미니 BPMN)', role: '승인 → action.cmd → ACK → 재관측 → 종결', zone: 'it', url: P(8080) + '/docs', health: P(8080) + '/healthz', full: 'Process GPT / Flowable' },
    { name: 'portal (guide-app)', role: '이 화면 · 가이드 카드 승인', zone: 'it', url: P(8088), health: null, full: 'guide-app' },
    { name: 'enterprise-sim (ERP · MES · CMMS · QMS · SCM · EMS)', role: '에이전트가 조회하고 L9가 실행하는 기업 시스템 목업', zone: 'it', url: P(8095) + '/docs', health: P(8095) + '/healthz', full: 'SAP · MES · CMMS · QMS 등' },
  ]},
  { no: 'L8', name: 'AI 에이전트', role: '조치 가이드 + 전사 트레이드오프 판단 (명령 권한 없음)', zone: 'it', focus: true, comps: [
    { name: 'agent', role: '경보 → T1 원인 → 증거 → T2 조치 → T3 전사 판단(ERP·MES 조회, 부서 KPI 비교) → 가드레일', zone: 'it', url: P(8091) + '/docs', health: P(8091) + '/healthz', full: 'LangGraph · MCP(mcp-kg/tsdb/prom/ent) · LiteLLM' },
  ]},
  { no: 'L7', name: '온톨로지 · 원인분석', role: '원인·조치 + 조직·KPI·규정·시스템·스킬 지식', zone: 'it', focus: true, comps: [
    { name: 'Neo4j 지식 그래프', role: '그림 2 스키마 + 전사 확장 · T1/T2/T3 Cypher 템플릿', zone: 'it', url: P(7474) + '/browser/', health: P(7474), full: 'Neo4j + n10s · OWL/SHACL' },
  ]},
  { no: 'L6', name: '관제 · SCADA · 인프라 감시', role: '관제', zone: 'mixed', comps: [
    { name: 'FUXA 웹 SCADA', role: 'P&ID · 알람 · 수동 조작 · 모드 전환', zone: 'ot', url: P(1881), health: P(1881) + '/api/settings', full: 'FUXA' },
    { name: 'Grafana', role: '설비 추세 · 경보/조치 주석', zone: 'it', url: P(3000) + '/d/hyd-trend', health: P(3000) + '/api/health', full: 'Grafana' },
    { name: 'Prometheus', role: '플랫폼 메트릭 (선택 프로필 monitor)', zone: 'it', url: P(9090), health: P(9090) + '/-/ready', optional: true, full: 'Prometheus · Alertmanager · prom-agent' },
  ]},
  { no: 'L5', name: '시계열 저장소', role: '이력 저장', zone: 'it', comps: [
    { name: 'connect-sink', role: 'Kafka → TimescaleDB upsert', zone: 'it', url: P(8094) + '/docs', health: P(8094) + '/healthz', full: 'Kafka Connect JDBC Sink' },
    { name: 'TimescaleDB', role: 'tag_1s · feat_1s · alerts · actions · audit', zone: 'it', url: P(3000) + '/explore', health: null, full: 'TimescaleDB' },
  ]},
  { no: 'L4', name: '스트림 처리 · CEP', role: '실시간 이상 탐지', zone: 'it', comps: [
    { name: 'detector', role: '1 s 특징 · 이상 점수 · CEP RAISE/CLEAR', zone: 'it', url: P(8092) + '/docs', health: P(8092) + '/healthz', full: 'Apache Flink CEP + ONNX' },
  ]},
  { no: 'L3', name: '이벤트 백본', role: '이벤트 장부 · 분배', zone: 'mixed', comps: [
    { name: 'connect-ingest', role: 'OT MQTT → Kafka (↑ 복제만)', zone: 'dmz', url: P(8093) + '/docs', health: P(8093) + '/healthz', full: 'Kafka Connect MQTT Source' },
    { name: 'cmd-gateway', role: 'action.cmd·alerts → OT (검증 5종, ↓ 유일 통로)', zone: 'dmz', url: P(8090) + '/docs', health: P(8090) + '/healthz', full: '명령 게이트웨이' },
    { name: 'Redpanda (Kafka API)', role: 'plant.tag · alerts · action.cmd · audit … (메시지 브라우저 Console은 tools 프로필)', zone: 'it', url: P(8085) + '/topics', health: P(9644) + '/v1/status/ready', full: 'Apache Kafka (KRaft)' },
  ]},
  { no: 'L2', name: 'IoT 미들웨어 · MQTT', role: '디바이스 연결 · 수집', zone: 'ot', comps: [
    { name: 'EMQX', role: 'OT 브로커 · 토픽 plant/{asset}/…', zone: 'ot', url: P(18083), health: P(18083) + '/status', full: 'EMQX · EdgeX Foundry' },
  ]},
  { no: 'L1', name: '센서 네트워크 · 설비', role: '현장 계측 · 구동', zone: 'ot', comps: [
    { name: 'plant-sim (설비 3기 + soft-PLC)', role: '물리 모델 · 인터록 · 운전 모드 · 명령 검증', zone: 'ot', url: P(8000) + '/docs', health: P(8000) + '/healthz', full: '유압설비 · PLC · 고속 DAQ' },
  ]},
];

const API = {
  plant: P(8000), gateway: P(8090), detector: P(8092), agent: P(8091), process: P(8080), grafana: P(3000),
};
