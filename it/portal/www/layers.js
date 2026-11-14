// L9 → L1: 계층의 할 일과 이 시스템의 부품(교재 1회차 02 의 아홉 계층과 같은 이름 · 같은 차례). 시스템 구성 화면(app.js renderStack)과 상태 확인(pollHealth)이 이 표 하나를 읽는다.
// role = 하는 일, real = 현업에서 같은 자리에 있는 것(화면이 「현업에서는 …」으로 보인다), zone = 영역(ot · dmz · it),
// nets = 그 서비스가 붙은 망(compose.yaml 의 networks 그대로 — 판정은 workspace/개발/tests/test_zones.py · test_www_app.py).
// 서비스 주소는 이 파일 하나가 만든다.
//  - API: 화면이 데이터를 읽고 쓰는 길 — 포털과 같은 출처의 /svc/<서비스 이름>(nginx.conf 가 그 서비스로 넘긴다).
//    서비스는 다른 출처 요청을 받지 않는다(CORS 없음). 화면 파일은 `API.process + '/api/…'` 처럼 이 표만 쓴다.
//  - P(port): 사람이 새 탭으로 여는 도구 화면(서비스 문서 · Grafana · FUXA · Neo4j Browser …)과 그 도구들의 켜짐 확인.
//    이 PC에서 다른 프로그램과 겹쳐 옮긴 포트가 있으면 그 포트로 연다("8080=18080 3000=13000", nginx가 화면에 끼워 넣음).
// health: 5초마다 확인하는 주소 — 우리 서비스는 같은 출처 /healthz(JSON), 바깥 도구는 그 포트에 닿는지만(opaque fetch).
// healthOf: 사람이 여는 화면도 상태 주소도 없는 부품(MQTT 브로커 — 관리 화면 · 관리 API 는 꺼 두었다)의 상태를 읽는 길.
//    그 브로커에 붙는 우리 서비스들의 /healthz 가 말하는 `mqtt` 값으로 읽는다(하나라도 true 면 브로커는 살아 있다).
const H = location.hostname || 'localhost';
const PORT_MAP = Object.fromEntries(String(window.HYD_PORTS_RAW || '').split(/\s+/).filter(Boolean).map(kv => kv.split('=').map(Number)));
const P = (port) => `http://${H}:${PORT_MAP[port] || port}`;
const SVC = (name) => `/svc/${name}`;
const API = {
  process: SVC('process'), agent: SVC('agent'), ent: SVC('enterprise-sim'), plant: SVC('plant-sim'), detector: SVC('detector'), gateway: SVC('cmd-gateway'),
};

const LAYERS = [
  { name: '프로세스 · 승인 · 앱', role: '권고를 승인하고 조치를 실행', zone: 'it', focus: true, comps: [
    { name: 'process', nets: ['it-net', 'sim-net'], role: '승인 → 명령 전송 → 결과 확인 → 종결', real: '업무 프로세스 엔진(BPM)', zone: 'it', url: P(8080) + '/docs', health: API.process + '/healthz' },
    { name: 'portal', nets: ['it-net', 'dmz-it-net', 'sim-net'], role: '설비 관찰 · 판단 확인 · 승인을 하는 화면', real: '운영 포털 · 업무 화면', zone: 'it', url: P(8088), health: null },
    { name: 'enterprise-sim', nets: ['it-net'], role: '생산 관리 · 정비 관리 · 구매 · 재고 시스템을 모의 실행', real: 'ERP · 정비(CMMS) · 구매 시스템', zone: 'it', url: P(8095) + '/docs', health: API.ent + '/healthz' },
  ]},
  { name: 'AI 에이전트', role: '근거를 조회하고 조치를 권고', zone: 'it', focus: true, comps: [
    { name: 'agent', nets: ['it-net', 'dmz-it-net'], role: '지식 그래프를 읽어 원인 · 조치 후보 · 부서별 영향을 계산 · 설비를 직접 제어할 권한 없음', real: '의사결정 지원 서비스', zone: 'it', url: P(8091) + '/docs', health: API.agent + '/healthz' },
    // 2026-10-25: 포털의 AI 단계(판단 · 제안, 질문, 매뉴얼 추출)를 하는 AI 에이전트. 꺼지면 그 단계만 멈추므로 상태 점에 보인다
    { name: 'agent-worker', nets: ['it-net'], role: 'AI 에이전트 실행 서비스 — 판단 · 제안, 질문 응답, 매뉴얼 추출을 수행', real: 'AI 에이전트 실행 환경', zone: 'it', url: P(8097) + '/healthz', health: SVC('agent-worker') + '/healthz' },
  ]},
  { name: '온톨로지 · 원인분석', role: '서로 다른 분야의 지식을 연결', zone: 'it', focus: true, comps: [
    { name: 'Neo4j', nets: ['it-net'], role: '설비 · 고장 · 매뉴얼 · 조치 방법 · 조직의 관계를 저장', real: '그래프 DB(지식 그래프 저장소)', zone: 'it', url: P(7474) + '/browser/', health: P(7474) },
  ]},
  { name: '관제 · SCADA · 인프라 감시', role: '설비 상태와 데이터 추이를 확인', zone: 'mixed', comps: [
    // FUXA 는 기본 서비스다(compose 에 프로필이 없다) — 선택 도구로 표시하지 않는다. 선택 프로필은 monitor(Prometheus)와 tools 뿐이다.
    { name: 'FUXA', nets: ['ot-net'], role: '설비 감시 · 수동 조작 · 운전 모드 전환', real: 'SCADA · HMI', zone: 'ot', url: P(1881), health: P(1881) + '/api/settings' },
    { name: 'Grafana', nets: ['it-net'], role: '센서 추이와 경보 · 조치 이력을 그래프로 표시', real: '분석 · 추이 대시보드', zone: 'it', url: P(3000) + '/d/hyd-trend', health: P(3000) + '/api/health' },
    { name: 'Prometheus', nets: ['it-net', 'dmz-it-net'], role: '서비스 상태와 처리량 수집', real: '인프라 감시 도구', zone: 'it', url: P(9090), health: P(9090) + '/-/ready', optional: true },
  ]},
  { name: '시계열 저장소', role: '관측값과 사건을 시간순으로 보관', zone: 'it', comps: [
    { name: 'connect-sink', nets: ['it-net'], role: '이벤트를 받아 시계열 DB에 기록', real: 'Kafka Connect 같은 싱크 커넥터', zone: 'it', url: P(8094) + '/docs', health: SVC('connect-sink') + '/healthz' },
    // url 없음: 사람이 여는 화면이 없는 부품이다 — 시스템 구성 화면은 [열기] 대신 how(무엇으로 들여다보는지)를 보인다
    { name: 'TimescaleDB', nets: ['it-net'], role: '센서값 · 경보 · 명령 · 감사 이력 저장', real: '히스토리언(시계열 DB) — 사이트 히스토리언은 OT 쪽에도 둡니다', zone: 'it', url: null, how: '여는 화면이 없습니다. 저장된 값은 추이 화면(Grafana)이 읽어 그래프로 보입니다.', health: null },
  ]},
  { name: '스트림 처리 · CEP', role: '연속된 데이터에서 이상을 탐지', zone: 'it', comps: [
    { name: 'detector', nets: ['it-net'], role: '1초 단위 특징 계산 · 경보 발생과 해제 판정', real: '스트림 처리 · CEP 엔진 — 현장(엣지) 쪽에서도 탐지합니다', zone: 'it', url: P(8092) + '/docs', health: API.detector + '/healthz' },
  ]},
  { name: '이벤트 백본', role: '데이터와 명령을 각 서비스로 전달', zone: 'mixed', comps: [
    { name: 'connect-ingest', nets: ['ot-dmz-net', 'dmz-it-net'], role: '현장 MQTT 데이터를 분석망으로 전달', real: 'Kafka Connect 같은 커넥터', zone: 'dmz', url: P(8093) + '/docs', health: SVC('connect-ingest') + '/healthz' },
    { name: 'cmd-gateway', nets: ['ot-dmz-net', 'dmz-it-net'], role: '승인된 명령을 검증한 뒤 현장으로 전달', real: 'DMZ의 명령 검증 · 중계 서버', zone: 'dmz', url: P(8090) + '/docs', health: API.gateway + '/healthz' },
    { name: 'Redpanda', nets: ['it-net', 'dmz-it-net'], role: 'Kafka 호환 이벤트 저장 · 분배', real: 'Apache Kafka(같은 규약)', zone: 'it', url: P(8085) + '/topics', health: P(9644) + '/v1/status/ready', entryHealth: P(8085) },
  ]},
  { name: 'IoT 미들웨어 · MQTT', role: '현장 장치와 메시지를 주고받음', zone: 'ot', comps: [
    { name: 'EMQX', nets: ['ot-net', 'ot-dmz-net'], role: '센서값 · 상태 · 명령을 중계하는 MQTT 브로커', real: 'MQTT 브로커(IoT 미들웨어)', zone: 'ot', url: null,
      how: '여는 화면이 없습니다. 관리 화면과 관리 API는 꺼 두었습니다 — 그 길로 보낸 명령은 토픽 규칙과 승인을 거치지 않기 때문입니다. 지나가는 값은 관제 화면(FUXA)에서 봅니다.',
      health: 'mqtt:EMQX', healthOf: { field: 'mqtt', from: [API.plant + '/healthz', SVC('connect-ingest') + '/healthz', API.gateway + '/healthz'] } },
  ]},
  { name: '센서 네트워크 · 설비', role: '현장을 계측하고 설비를 구동', zone: 'ot', comps: [
    { name: 'plant-sim', nets: ['ot-net', 'sim-net'], role: '가상 유압 설비 3기와 PLC · 센서 · 값을 내보내는 엣지를 한 프로그램으로 모의 실행', real: '실제 설비 · 센서 · PLC · 엣지 게이트웨이(각각 따로 있는 장치) — 안전계장(SIS)은 제어와 따로 둡니다', zone: 'ot', url: P(8000) + '/docs', health: API.plant + '/healthz' },
  ]},
];

// 망 다섯(compose.yaml networks 의 이름과 차례). zone = 구조 그림에서 그 망이 놓이는 영역, what = 그 망에 붙는 것.
const NETS = [
  { id: 'ot-net', zone: 'ot', name: 'OT 망', what: '설비 · MQTT 브로커 · 관제 화면' },
  { id: 'ot-dmz-net', zone: 'dmz', name: '경계 망 1', what: 'MQTT 브로커 ↔ 수집 중계 · 명령 관문' },
  { id: 'dmz-it-net', zone: 'dmz', name: '경계 망 2', what: '수집 중계 · 명령 관문 ↔ 이벤트 저장. 포털 · 판단 서비스는 이 망으로 두 부품의 상태만 읽습니다' },
  { id: 'it-net', zone: 'it', name: 'IT 망', what: '업무 · 분석 · 지식 · AI' },
  { id: 'sim-net', zone: 'side', name: '가상 설비 API 망', what: '흐름 엔진 · 포털 ↔ 가상 설비. 결함 주입 · 현장 패널 조작 · 정비 수행이 이 길로 가고 브로커와 명령 관문을 거치지 않습니다' },
];
// 이 구성이 현업 공장과 다른 곳 — 시스템 구성 화면이 그림 아래에 그대로 보인다(대상을 말하는 문장, 근거는 현업 구조 대조).
const SYS_DIFFS = [
  { icon: 'route', name: '명령 길 밖의 조작', text: '결함 주입 · 현장 패널 조작 · 정비 수행은 가상 설비 API 망(sim-net)으로 설비에 직접 적용됩니다. 바깥에서 생긴 고장과 사람이 현장에서 하는 일을 대신하는 길이라 승인과 명령 관문을 거치지 않습니다.' },
  { icon: 'shield-alert', name: '영역 경계', text: '영역은 망 다섯으로 나뉘고 DMZ의 두 부품은 경계 망 둘에만 붙습니다. 현업은 영역 사이에 방화벽과 단방향 전송 장치를 둡니다.' },
  { icon: 'lock', name: '인증 · 암호화', text: 'MQTT 브로커 · 관제 화면 · 추이 화면은 암호화(TLS)와 사용자 인증 없이 이 PC 안에서만 열립니다. 현업은 둘 다 켭니다.' },
  { icon: 'cpu', name: '설비 · PLC · 엣지', text: '가상 설비 3기와 PLC, 값을 내보내는 엣지가 한 프로그램(plant-sim)에서 돕니다. 현업은 따로 있는 장치이고 안전계장(SIS)을 제어와 따로 둡니다.' },
  { icon: 'activity', name: '이상 탐지', text: '탐지는 IT의 이상 탐지(detector) 한 곳에서 합니다. 현업은 현장(엣지) 쪽에서도 탐지합니다.' },
  { icon: 'plug', name: '접속 방향', text: '수집 중계와 명령 관문이 현장 브로커에 접속해 주고받습니다. 현업은 공장 쪽이 먼저 여는 방향을 방화벽 규칙으로 지킵니다.' },
];
