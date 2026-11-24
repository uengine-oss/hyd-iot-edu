// L9 → L1: 계층의 할 일과 이 시스템의 부품(교재 1회차 02 의 아홉 계층과 같은 이름 · 같은 차례 — 화면은 줄마다 「Layer 9」 … 「Layer 1」을 함께 적는다). 시스템 구성 화면(app.js renderStack)과 상태 확인(pollHealth)이 이 표 하나를 읽는다.
// role = 하는 일, real = 현업에서 같은 자리에 있는 것(화면이 「현업에서는 …」으로 보인다), zone = 영역(ot · dmz · it),
// product = 그 부품을 돌리는 제품 — 이름이 서비스 이름이고 제품이 따로 있는 부품(브로커 둘 · 공장 쪽 브리지 = mosquitto)에만 둔다. 구조 그림의 상자 아랫줄이 이름 대신 이것을 보인다,
// nets = 그 서비스가 붙은 망(compose.yaml 의 networks 그대로 — 판정은 workspace/개발/tests/test_zones.py · test_www_app.py).
// 서비스 주소는 이 파일 하나가 만든다.
//  - API: 화면이 데이터를 읽고 쓰는 길 — 포털과 같은 출처의 /svc/<서비스 이름>(nginx.conf 가 그 서비스로 넘긴다).
//    서비스는 다른 출처 요청을 받지 않는다(CORS 없음). 화면 파일은 `API.process + '/api/…'` 처럼 이 표만 쓴다.
//  - P(port): 사람이 새 탭으로 여는 도구 화면(서비스 문서 · Grafana · FUXA · Neo4j Browser …)과 그 도구들의 켜짐 확인.
//    이 PC에서 다른 프로그램과 겹쳐 옮긴 포트가 있으면 그 포트로 연다("8080=18080 3000=13000", nginx가 화면에 끼워 넣음).
// health: 5초마다 확인하는 주소 — 우리 서비스는 같은 출처 /healthz(JSON), 바깥 도구는 그 포트에 닿는지만(opaque fetch).
// healthOf: 사람이 여는 화면도 상태 주소도 없는 부품(MQTT 브로커 둘 · 공장 쪽 브리지 — 셋 다 관리 화면 · 관리 API 가 없는 mosquitto 다)의 상태를 읽는 길.
//    그 부품에 붙는 우리 서비스들의 /healthz 본문(응답 코드가 503 이어도 본문은 읽는다)을 from 의 주소마다 read 로 읽는다:
//    true = 이어져 있다고 한다, false = 끊겼다고 한다, 그 밖 = 그 서비스는 모른다. 하나라도 true 면 정상, true 없이 false 가 있으면 응답 없음, 아무도 모르면 확인 중.
//    - 공장 브로커(ot-broker): 가상 설비의 mqtt(그 브로커에 바로 붙는다)와, DMZ 의 두 서비스가 들은 브리지의 공장 브로커 쪽 다리(ot_bridge_legs.broker).
//    - DMZ 브로커: 수집 중계 · 명령 관문의 mqtt. - 공장 쪽 브리지: 그 둘이 DMZ 브로커에서 들은 두 다리(하나라도 끊겼으면 끊김).
const H = location.hostname || 'localhost';
const PORT_MAP = Object.fromEntries(String(window.HYD_PORTS_RAW || '').split(/\s+/).filter(Boolean).map(kv => kv.split('=').map(Number)));
const PC_PORT = (port) => PORT_MAP[port] || port;           // compose 의 바깥 포트 번호 → 이 PC 에서 실제로 연 포트
const P = (port) => `http://${H}:${PC_PORT(port)}`;
const SVC = (name) => `/svc/${name}`;
const API = {
  process: SVC('process'), agent: SVC('agent'), ent: SVC('enterprise-sim'), plant: SVC('plant-sim'), detector: SVC('detector'), gateway: SVC('cmd-gateway'),
};

const HEARD = {
  plantBroker: h => h.ot_bridge_legs ? h.ot_bridge_legs.broker : h.mqtt,
  dmzBroker: h => h.mqtt,
  bridge: h => { const l = h.mqtt === true && h.ot_bridge_legs; return !l ? null : (l.broker === false || l.dmz === false) ? false : (l.broker === true && l.dmz === true) ? true : null; },
};
const DMZ_HEALTH = [SVC('connect-ingest') + '/healthz', API.gateway + '/healthz'];

const LAYERS = [
  { name: '프로세스 · 승인 · 앱', role: '추천안을 승인하고 조치를 실행', zone: 'it', focus: true, comps: [
    { name: 'process', nets: ['it-net', 'sim-net', 'business-db'], role: '승인 → 명령 전송 → 결과 확인 → 종결', real: '업무 프로세스 엔진(BPM)', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.process + '/healthz' },
    { name: 'portal', nets: ['it-net', 'dmz-it-net', 'sim-net'], role: '설비 관찰 · 판단 확인 · 승인을 하는 화면', real: '운영 포털 · 업무 화면', zone: 'it', url: P(8088), health: null },
    { name: 'enterprise-sim', nets: ['it-net', 'business-db'], role: '생산 관리 · 정비 관리 · 구매 · 재고 시스템을 모의 실행', real: 'ERP · 정비(CMMS) · 구매 시스템', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.ent + '/healthz' },
  ]},
  { name: 'AI 에이전트', role: '근거를 조회하고 조치를 추천', zone: 'it', focus: true, comps: [
    { name: 'agent', nets: ['it-net', 'dmz-it-net', 'business-db'], role: '지식 그래프를 읽어 원인 · 조치 후보 · 부서별 영향을 계산 · 설비를 직접 제어할 권한 없음', real: '의사결정 지원 서비스', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.agent + '/healthz' },
    // 2026-10-25: 포털의 AI 단계(판단 · 제안, 질문, 매뉴얼 추출)를 하는 AI 에이전트. 꺼지면 그 단계만 멈추므로 상태 점에 보인다
    { name: 'agent-worker', nets: ['it-net', 'business-db'], role: 'AI 에이전트 실행 서비스 — 판단 · 제안, 질문 응답, 매뉴얼 추출을 수행', real: 'AI 에이전트 실행 환경', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: SVC('agent-worker') + '/healthz' },
  ]},
  { name: '온톨로지 · 원인분석', role: '서로 다른 분야의 지식을 연결', zone: 'it', focus: true, comps: [
    { name: 'Neo4j', nets: ['it-net'], role: '설비 · 고장 · 매뉴얼 · 조치 방법 · 조직의 관계를 저장', real: '그래프 DB(지식 그래프 저장소)', zone: 'it', url: P(7474) + '/browser/', health: P(7474) },
  ]},
  { name: '관제 · SCADA · 인프라 감시', role: '설비 상태와 데이터 추이를 확인', zone: 'mixed', comps: [
    // FUXA 는 기본 서비스다(compose 에 프로필이 없다) — 선택 도구로 표시하지 않는다. 선택 프로필은 monitor(Prometheus)와 tools 뿐이다.
    { name: 'FUXA', nets: ['ot-net'], role: '설비 감시 · 수동 조작 · 운전 모드 전환', real: '운전 화면(SCADA · HMI)', zone: 'ot', url: P(1881), health: P(1881) + '/api/settings' },
    { name: 'Grafana', nets: ['it-net'], role: '센서 추이와 경보 · 조치 이력을 그래프로 표시', real: '분석 · 추이 대시보드', zone: 'it', url: P(3000) + '/d/hyd-trend', health: P(3000) + '/api/health' },
    { name: 'Prometheus', nets: ['it-net', 'dmz-it-net'], role: '서비스 상태와 처리량 수집', real: '인프라 감시 도구', zone: 'it', url: P(9090), health: P(9090) + '/-/ready', optional: true },
  ]},
  { name: '시계열 저장소', role: '관측값과 사건을 시간순으로 보관', zone: 'it', comps: [
    { name: 'connect-sink', nets: ['it-net'], role: '이벤트를 받아 시계열 저장소에 기록', real: 'Kafka Connect 같은 싱크 커넥터', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: SVC('connect-sink') + '/healthz' },
    // url 없음: 사람이 여는 화면이 없는 부품이다 — 시스템 구성 화면은 [열기] 대신 how(무엇으로 들여다보는지)를 보인다
    { name: 'TimescaleDB', nets: ['it-net'], role: '센서값 · 경보 · 명령 · 감사 이력 저장', real: '히스토리언(시계열 저장소) — 사이트 히스토리언은 OT 쪽에도 둡니다', zone: 'it', url: null, how: '여는 화면이 없습니다. 저장된 값은 추이 화면(Grafana)이 읽어 그래프로 보입니다.', health: null },
  ]},
  { name: '스트림 처리 · CEP', role: '연속된 데이터에서 이상을 탐지', zone: 'it', comps: [
    { name: 'detector', nets: ['it-net'], role: '1초 단위 특징 계산 · 경보 발생과 해제 판정', real: '스트림 처리 · CEP 엔진 — 현장(엣지) 쪽에서도 탐지합니다', zone: 'it', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.detector + '/healthz' },
  ]},
  { name: '이벤트 백본', role: '데이터와 명령을 각 서비스로 전달', zone: 'mixed', comps: [
    { name: 'ot-bridge', product: 'mosquitto', nets: ['ot-net', 'ot-dmz-net'], role: '공장 안에서 DMZ 브로커로 먼저 접속해 값을 내보내고, 검증을 통과한 명령을 가져옴 · 바깥에서 들어오는 입구 없음', real: '공장 쪽 엣지 게이트웨이 · 브로커 브리지(바깥으로 나가는 연결만 엽니다)', zone: 'ot', url: null,
      how: '여는 화면이 없습니다. 공장 브로커와 DMZ 브로커 양쪽에 스스로 접속해 있고, 어느 쪽이든 끊기면 수집 중계와 명령 관문이 그 사실을 알립니다.',
      health: 'bridge:ot-bridge', healthOf: { from: DMZ_HEALTH, read: HEARD.bridge } },
    { name: 'connect-ingest', nets: ['ot-dmz-net', 'dmz-it-net'], role: 'DMZ 브로커에 올라온 현장 데이터를 분석망으로 전달 · 공장 안으로는 접속하지 않음', real: 'DMZ 중계 — Kafka Connect 같은 커넥터', zone: 'dmz', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: SVC('connect-ingest') + '/healthz' },
    { name: 'cmd-gateway', nets: ['ot-dmz-net', 'dmz-it-net'], role: '승인된 명령을 검증해 DMZ 브로커에 놓음 · 공장 쪽 브리지가 와서 가져감', real: 'DMZ의 명령 검증 · 중계 서버', zone: 'dmz', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.gateway + '/healthz' },
    { name: 'Redpanda', nets: ['it-net', 'dmz-it-net'], role: 'Kafka 호환 이벤트 저장 · 분배', real: '이벤트 로그 — Apache Kafka(같은 규약)', zone: 'it', url: P(8085) + '/topics', health: SVC('redpanda') + '/v1/status/ready', entryHealth: P(8085) },
  ]},
  { name: 'IoT 미들웨어 · MQTT', role: '현장 장치와 메시지를 주고받음', zone: 'mixed', comps: [
    { name: 'ot-broker', product: 'mosquitto', nets: ['ot-net'], role: '공장 안에서 센서값 · 상태 · 명령을 중계하는 MQTT 브로커 · OT 망에만 붙어 DMZ · IT의 부품은 닿지 못함', real: '공장 안의 MQTT 브로커(IoT 미들웨어)', zone: 'ot', url: null,
      how: '여는 화면이 없습니다. 지나가는 값은 관제 화면에서 봅니다.',
      health: 'mqtt:ot-broker', healthOf: { from: [API.plant + '/healthz', ...DMZ_HEALTH], read: HEARD.plantBroker } },
    { name: 'dmz-broker', product: 'mosquitto', nets: ['ot-dmz-net'], role: '공장이 내보낸 값과 검증을 통과한 명령이 놓이는 자리 · 스스로는 어디에도 접속하지 않고 기다림', real: 'DMZ의 MQTT 브로커(공장이 접속해 오는 쪽)', zone: 'dmz', url: null,
      how: '여는 화면이 없습니다. 공장 쪽 브리지 · 수집 중계 · 명령 관문만 붙고, 이 PC의 프로그램에는 열려 있지 않습니다.',
      health: 'mqtt:dmz-broker', healthOf: { from: DMZ_HEALTH, read: HEARD.dmzBroker } },
  ]},
  { name: '센서 네트워크 · 설비', role: '현장을 계측하고 설비를 구동', zone: 'ot', comps: [
    { name: 'plant-sim', nets: ['ot-net', 'sim-net'], role: '가상 유압 설비 3기와 PLC · 센서 · 값을 내보내는 엣지를 한 프로그램으로 모의 실행', real: '실제 설비 · 센서 · PLC · 엣지 게이트웨이(각각 따로 있는 장치) — 안전계장(SIS)은 제어와 따로 둡니다', zone: 'ot', url: null, how: '여는 화면이 없습니다. 포털 화면이 이 서비스를 불러 씁니다.', health: API.plant + '/healthz' },
  ]},
];

// 망 여섯(compose.yaml networks 의 이름과 차례). zone = 구조 그림에서 그 망이 놓이는 영역, what = 그 망에 붙는 것.
const NETS = [
  { id: 'ot-net', zone: 'ot', name: 'OT 망', what: '설비 · MQTT 브로커 · 관제 화면 · 공장 쪽 브리지' },
  { id: 'ot-dmz-net', zone: 'dmz', name: '경계 망 1', what: '공장 쪽 브리지 → DMZ 브로커 ← 수집 중계 · 명령 관문. 공장 쪽에서는 브리지만 이 망에 나와 있고, 연결은 브리지가 엽니다' },
  { id: 'dmz-it-net', zone: 'dmz', name: '경계 망 2', what: '수집 중계 · 명령 관문 ↔ 이벤트 저장. 포털 · 판단 서비스는 이 망으로 두 부품의 상태만 읽습니다' },
  { id: 'it-net', zone: 'it', name: 'IT 망', what: '업무 · 분석 · 지식 · AI' },
  { id: 'sim-net', zone: 'side', name: '가상 설비 API 망', what: '흐름 엔진 · 포털 ↔ 가상 설비. 결함 주입 · 현장 패널 조작 · 정비 수행이 이 길로 가고 브로커와 명령 관문을 거치지 않습니다' },
  { id: 'business-db', zone: 'it', name: '업무 DB 망', what: '업무 DB(Supabase) · 메일함 ↔ 그것을 읽고 쓰는 IT 서비스(흐름 엔진 · 업무 시스템 · 판단 서비스 · AI 에이전트 실행 · 도구 서버). PC 의 바깥 포트를 돌지 않고 이 망 안의 이름으로 부릅니다' },
];
// 이 구성이 현업 공장과 다른 곳 — 시스템 구성 화면이 그림 아래에 그대로 보인다(대상을 말하는 문장, 근거는 현업 구조 대조).
const SYS_DIFFS = [
  { icon: 'route', name: '명령 길 밖의 조작', text: '결함 주입 · 현장 패널 조작 · 정비 수행은 가상 설비 API 망으로 설비에 직접 적용됩니다. 바깥에서 생긴 고장과 사람이 현장에서 하는 일을 대신하는 길이라 승인과 명령 관문을 거치지 않습니다.' },
  { icon: 'shield-alert', name: '영역 경계', text: '영역은 망 여섯으로 나뉘고 DMZ의 부품은 경계 망에만 붙습니다. 공장과 DMZ 사이의 연결은 공장 쪽 브리지가 먼저 열고, DMZ · IT의 부품에서 공장 브로커로는 닿는 길이 없습니다. 서비스 · 이벤트 저장 · 시계열 저장소 · 브로커는 이 PC에 입구를 열지 않고, 이 시스템이 여는 것은 포털 · 관제 화면 · 추이 화면 · 지식 그래프 브라우저 넷뿐입니다. 다만 업무 DB 도구(Supabase)는 업무 DB · 메일함 입구를 이 PC의 모든 주소에 열고, 이 PC의 Docker는 PC에 연 입구를 다른 망의 부품에서도 닿게 둡니다. 그래서 공장 · DMZ의 부품도 그 화면 넷과 업무 DB에 닿고(업무 DB는 방화벽이 막지 않으면 같은 망의 다른 PC에서도), 관제 화면으로는 수동 조작 · 운전 모드를, 포털로는 포털이 부르는 서비스를 부를 수 있습니다. 현업은 운전 화면을 공장 안에서 열고 바깥에서는 DMZ의 원격 접속 장치를 거쳐 보며, 영역 사이에 방화벽과 단방향 전송 장치를 두고 사용자 로그인을 둡니다.' },
  { icon: 'lock', name: '인증 · 암호화', text: '포털 · 관제 화면 · 추이 화면 · 지식 그래프 브라우저는 암호화(TLS) 없이 이 PC 안에서만 열리고, 포털에는 사용자 로그인이 없습니다. 업무 DB는 업무 DB 도구의 기본 계정(비밀번호가 알려진 계정)으로 열립니다. 브로커에 붙는 서비스는 비밀번호 없이 이름만 대고, 브로커는 그 이름으로 토픽 규칙을 적용합니다. 이벤트 저장(Redpanda)도 인증이 없어, 거기 붙는 서비스는 명령 관문의 기록과 같은 꼴의 기록을 쓸 수 있습니다 — 다만 설비 명령은 승인할 때 남긴 기록과 맞지 않으면 명령 관문이 설비로 넘기지 않습니다. 현업은 암호화와 인증(인증서 · 비밀번호)을 켭니다.' },
  { icon: 'cpu', name: '설비 · PLC · 엣지', text: '가상 설비 3기와 PLC, 값을 내보내는 엣지가 한 프로그램에서 돕니다. 현업은 따로 있는 장치이고 안전계장(SIS)을 제어와 따로 둡니다.' },
  { icon: 'activity', name: '이상 탐지', text: '탐지는 IT의 이상 탐지 한 곳에서 합니다. 현업은 현장(엣지) 쪽에서도 탐지합니다.' },
  { icon: 'plug', name: '공장 쪽 브리지', text: '공장 쪽 브리지는 끊긴 동안의 값을 쌓아 두지 않습니다. 다시 이어지면 그때부터의 값이 올라갑니다. 현업의 엣지 게이트웨이는 끊긴 동안의 값을 모아 두었다가 이어지면 보냅니다(store and forward).' },
];
