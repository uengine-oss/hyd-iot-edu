# -*- coding: utf-8 -*-
"""hyd-iot-edu 마스터 가이드 2부(시스템 아키텍처 상세) 본문 생성기.
2026-10-07 사용자 "둘다 마스터가이드" → 별도 문서를 만들지 않고 master_build.py 가 build_html(sec_offset, out=None) 으로 본문을 받아 넣는다.
(옛 설명) docs/시스템_아키텍처.html · .pdf 생성기 (ceco_demo docs/기록/src/arch_gen.py 와 같은 방식).
부품 · 연결을 이 파일 한 곳에 정의하고, 그림(SVG) · 부품 카드 · 연결 목록을 같은 번호로 만든다.
부품 ①~㉑ 은 마스터_가이드(master_arch_svg.py)의 번호와 같다. ㉒~㉖ 은 instance 모드 부품이다.
  python arch_build.py          → HTML + PDF
  python arch_build.py --html   → HTML 만
본문 틀은 arch_tpl.html. PDF 는 Playwright(Chromium) 인쇄: 본문 A4, 전체 그림은 큰 쪽 한 장.
"""
import html, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent
OUT_HTML = DOCS / "시스템_아키텍처.html"
OUT_PDF = DOCS / "시스템_아키텍처.pdf"

CIRC = {i: chr(0x2460 + i - 1) for i in range(1, 21)}
CIRC.update({i: chr(0x3251 + i - 21) for i in range(21, 36)})

# ═════════════════════════ 부품 ═════════════════════════
# key: (번호, 이름, 그림 둘째 줄, 그림 셋째 줄, 구역, 종류, x, y, w, h)
# 구역: plant · ot · dmz · it · ai · biz · inst · ext   종류: normal · once(기동 때 1회) · opt(선택 프로필) · inst(instance 모드) · ext(밖)
PART = {
 "sim":     (1,  "설비 3대 + PLC + 데이터 수집", "plant-sim (Python) · L1", "HYD-01~03 · 20배속 · 65 ℃ 트립", "plant", "normal", 340, 40, 500, 100),
 "emqx":    (2,  "공장 게시판 EMQX", "MQTT 브로커 5.8 · L2", "값 QoS 0 · 상태 QoS 1 retain · 인증 없음", "ot", "normal", 340, 210, 500, 92),
 "fuxa":    (3,  "운전실 화면", "FUXA · SCADA/HMI · L6", "값 · 알람 6개 · 수동 조작", "ot", "normal", 900, 210, 230, 92),
 "gw":      (4,  "명령 게이트웨이", "cmd-gateway (Python)", "내려가는 유일한 문 · 검증 5종", "dmz", "normal", 340, 450, 240, 100),
 "ing":     (5,  "수집 다리", "connect-ingest (Python)", "올라가는 문 · 대기열 2만 건", "dmz", "normal", 600, 450, 240, 100),
 "rp":      (6,  "장부 Redpanda (Kafka)", "v24.2.7 · 토픽 7개 · L3", "온도 1일 · 경보 365일 · 감사 5년", "it", "normal", 340, 640, 500, 100),
 "det":     (7,  "검사관 detector", "Python · L4 (Flink 역할)", "기울기 · 이상 점수 · 패턴", "it", "normal", 40, 640, 250, 100),
 "sink":    (8,  "저장 심부름꾼", "connect-sink (Python) · L5", "토픽 6개 → 표 6개", "it", "normal", 900, 640, 230, 80),
 "tsdb":    (9,  "기록 DB", "TimescaleDB 2.17 (PG16) · L5", "1초 값 3일 · 1분 요약 30일", "it", "normal", 900, 800, 230, 100),
 "graf":    (10, "추세 화면 Grafana", "11.3.0 · L6", "패널 14 · 주석 3종", "it", "normal", 1180, 800, 230, 90),
 "prom":    (11, "감시 Prometheus", "v2.55.1 · 선택(monitor)", "6개 서비스 10초마다", "it", "opt", 1180, 640, 230, 80),
 "neo":     (12, "지식 지도 Neo4j", "5.26 Community · L7", "온톨로지 v2 · 7층 46클래스", "ai", "normal", 40, 1105, 250, 95),
 "agent":   (13, "AI 조사관 agent", "Python · L8 (LangGraph 역할)", "원인 추정 · 조치 카드 · 가드레일", "ai", "normal", 440, 1040, 400, 110),
 "proc":    (14, "업무 진행 process", "Python · L9 (BPMN 엔진 역할)", "사건 · 승인 · 명령 · 재관측 · 작업지시", "biz", "normal", 340, 1320, 500, 110),
 "ent":     (15, "기업 시스템 흉내", "enterprise-sim · L9", "ERP · MES · CMMS · QMS · SCM · EMS", "biz", "normal", 900, 1320, 230, 110),
 "portal":  (16, "담당자 포털", "nginx · 정적 화면 · L9", "메뉴 10개 · 브라우저가 직접 호출", "biz", "normal", 340, 1470, 300, 70),
 "llm":     (17, "LLM API", "밖(인터넷)", "OpenAI 호환 · Anthropic", "ext", "ext", 1372, 1040, 166, 110),
 "finit":   (18, "화면 넣기", "fuxa-init · 기동 때 1회", "", "ot", "once", 900, 325, 230, 55),
 "tinit":   (19, "토픽 만들기", "topic-init · 기동 때 1회", "", "it", "once", 600, 800, 200, 55),
 "seed":    (20, "지식 채우기", "kg-seed · 기동 때 1회", "", "ai", "once", 40, 1040, 190, 50),
 "cons":    (21, "장부 열람 Console", "선택(tools)", "", "it", "opt", 1180, 905, 230, 60),
 "supa":    (22, "업무 기록부 Supabase", "PostgreSQL 54322 · 따로 기동", "인스턴스 · Task · 기업 DB(ent)", "inst", "inst", 340, 1790, 500, 92),
 "entmcp":  (23, "기업 DB 창구", "enterprise-mcp · /mcp 8199", "읽기 도구 10개", "inst", "inst", 900, 1625, 230, 90),
 "dmnmcp":  (24, "판단 엔진 창구", "dmn-mcp · /mcp 8198", "도구 14개 · 쓰기는 1개", "inst", "inst", 40, 1625, 228, 100),
 "worker":  (25, "AI 직원 agent-worker", "Claude Code CLI · 8097", "Task를 집어 수행 · 결과 저장", "inst", "inst", 340, 1615, 500, 130),
 "kgmcp":   (26, "Neo4j MCP", "mcp-neo4j-cypher · 읽기 전용", "", "inst", "inst", 600, 1683, 225, 52),
}
PEOPLE = {  # 번호 없는 사람
 "oper":  ("운전원 (브라우저)", 1180, 236, 170, 36),
 "staff": ("담당자 (브라우저)", 680, 1488, 170, 36),
}
for k, v in PART.items():
    assert len(v) == 10, k
NO = {k: v[0] for k, v in PART.items()}
assert sorted(NO.values()) == list(range(1, 27))

ZONE_NAME = {"plant": "현장", "ot": "OT 공장 망", "dmz": "DMZ 역할", "it": "IT 데이터", "ai": "지식·AI", "biz": "업무·사람", "inst": "instance 모드", "ext": "밖(인터넷)"}

# ═════════════════════════ 연결 ═════════════════════════
# key: (출발=연결을 여는 쪽, 도착(목록이면 여러 곳), 종류, 데이터 방향, 그림 점들 또는 None(작은 표만), 라벨 위치)
# 종류: data(계측·기록) · cmd(명령·실행) · alert(경보 표시) · api(조회·호출) · mon(감시) · once(기동 1회) · human(사람)
# 방향: fwd(여는 쪽 → 받는 쪽) · back(받는 쪽 → 여는 쪽) · both
LINE = [
 ("c_sim_pub",   "sim", "emqx", "data", "fwd",  [(720, 140), (720, 210)], (730, 178)),
 ("c_sim_sub",   "sim", "emqx", "cmd",  "back", [(410, 140), (410, 210)], (420, 178)),
 ("c_fuxa",      "fuxa", "emqx", "data", "both", [(900, 256), (840, 256)], (870, 246)),
 ("c_oper",      "oper", "fuxa", "human", "fwd", [(1180, 254), (1130, 254)], None),
 ("c_finit",     "finit", "fuxa", "once", "fwd", [(1015, 325), (1015, 302)], None),
 ("c_ing_sub",   "ing", "emqx", "data", "back", [(720, 450), (720, 302)], (730, 375)),
 ("c_ing_pub",   "ing", "rp", "data", "fwd",  [(720, 550), (720, 640)], (730, 597)),
 ("c_det",       "det", "rp", "data", "both", [(290, 690), (340, 690)], (315, 676)),
 ("c_det_neo",   "det", "neo", "api", "back", [(265, 740), (265, 1105)], (265, 905)),
 ("c_sink_sub",  "sink", "rp", "data", "back", [(900, 680), (840, 680)], (870, 668)),
 ("c_sink_db",   "sink", "tsdb", "data", "fwd", [(1015, 720), (1015, 800)], (1027, 760)),
 ("c_graf",      "graf", "tsdb", "api", "back", [(1180, 845), (1130, 845)], (1155, 835)),
 ("c_gw_cmd",    "gw", "rp", "cmd", "both", [(410, 550), (410, 640)], (420, 597)),
 ("c_gw_alert",  "gw", "rp", "alert", "back", [(500, 550), (500, 640)], (510, 597)),
 ("c_gw_auto",   "gw", "emqx", "cmd", "fwd", [(410, 450), (410, 302)], (420, 375)),
 ("c_gw_disp",   "gw", "emqx", "alert", "fwd", [(480, 450), (480, 302)], (490, 375)),
 ("c_gw_stat",   "gw", "emqx", "data", "back", [(550, 450), (550, 302)], (560, 375)),
 ("c_ag_alert",  "agent", "rp", "alert", "back", [(820, 1040), (820, 740)], (820, 905)),
 ("c_ag_neo",    "agent", "neo", "api", "back", [(440, 1130), (290, 1130)], (365, 1120)),
 ("c_ag_tsdb",   "agent", "tsdb", "api", "back", [(840, 1065), (1050, 1065), (1050, 900)], (1050, 985)),
 ("c_ag_llm",    "agent", "llm", "api", "both", [(840, 1125), (1372, 1125)], (1300, 1115)),
 ("c_ag_ent",    "agent", "ent", "api", "back", [(800, 1150), (800, 1235), (960, 1235), (960, 1320)], (880, 1225)),
 ("c_ag_proc",   "agent", "proc", "data", "both", [(560, 1150), (560, 1320)], (560, 1235)),
 ("c_ag_ing",    "agent", "ing", "mon", "back", None, None),
 ("c_ag_supa",   "agent", "supa", "api", "back", None, None),
 ("c_proc_rp",   "proc", "rp", "cmd", "both", [(380, 1320), (380, 740)], (380, 905)),
 ("c_proc_tsdb", "proc", "tsdb", "api", "back", [(760, 1320), (760, 1285), (1090, 1285), (1090, 900)], (1090, 1210)),
 ("c_proc_neo",  "proc", "neo", "data", "both", [(340, 1360), (165, 1360), (165, 1200)], (165, 1245)),
 ("c_proc_ent",  "proc", "ent", "cmd", "both", [(840, 1385), (900, 1385)], (870, 1374)),
 ("c_proc_ag",   "proc", "agent", "api", "both", [(680, 1320), (680, 1150)], (680, 1235)),
 ("c_proc_supa", "proc", "supa", "data", "both", [(340, 1410), (320, 1410), (320, 1835), (340, 1835)], (320, 1600)),
 ("c_proc_wk",   "proc", "worker", "mon", "back", None, None),
 ("c_staff",     "staff", "portal", "human", "fwd", [(680, 1506), (640, 1506)], None),
 ("c_browser",   "staff", ["sim", "gw", "det", "agent", "proc", "ent", "graf"], "api", "both", None, None),
 ("c_prom",      "prom", ["ing", "gw", "det", "sink", "agent", "proc"], "mon", "back", None, None),
 ("c_cons",      "cons", "rp", "api", "both", [(1180, 935), (860, 935), (860, 725), (840, 725)], (965, 925)),
 ("c_tinit",     "tinit", "rp", "once", "fwd", [(700, 800), (700, 740)], None),
 ("c_seed",      "seed", "neo", "once", "fwd", [(135, 1090), (135, 1105)], None),
 ("c_ent_supa",  "ent", "supa", "data", "both", [(1130, 1400), (1160, 1400), (1160, 1860), (840, 1860)], (1160, 1580)),
 ("c_wk_supa",   "worker", "supa", "data", "both", [(470, 1745), (470, 1790)], (482, 1768)),
 ("c_wk_llm",    "worker", "llm", "api", "both", [(840, 1640), (870, 1640), (870, 1595), (1455, 1595), (1455, 1150)], (1455, 1380)),
 ("c_wk_dmn",    "worker", "dmnmcp", "api", "both", [(340, 1675), (268, 1675)], (288, 1662)),
 ("c_wk_ent",    "worker", "entmcp", "api", "both", [(840, 1670), (900, 1670)], (870, 1660)),
 ("c_kgmcp_neo", "kgmcp", "neo", "api", "back", None, None),
 ("c_entmcp_supa", "entmcp", "supa", "api", "back", [(1015, 1715), (1015, 1835), (840, 1835)], (1015, 1775)),
 ("c_dmn",       "dmnmcp", ["neo", "tsdb", "proc", "ent", "ing", "prom"], "api", "back", None, None),
]
L = {}
for i, (k, a, b, kind, d, pts, lp) in enumerate(LINE, 1):
    L[k] = dict(key=k, no=i, a=a, b=b, kind=kind, dir=d, pts=pts, lp=lp)
assert len(L) == len(LINE)

KINDW = {"data": "계측·기록", "cmd": "명령·실행", "alert": "경보 표시", "api": "조회·호출", "mon": "감시", "once": "기동 때 1회", "human": "사람"}
DIRW = {"fwd": "여는 쪽 → 받는 쪽", "back": "받는 쪽 → 여는 쪽", "both": "양쪽"}
COL = dict(data="#1f6f8b", cmd="#d1343f", alert="#7b4fc9", api="#4a5fb5", mon="#7d8890", once="#8f989f", human="#2b2f33")


# ═════════════════════════ 부품 설명: (쉬운 말, 기술 세부 [(항목, 값)], 하는 일 상세) ═════════════════════════
D = {}
D["sim"] = (
 "진짜 유압 설비 세 대 대신 컴퓨터가 기름의 열과 압력을 계산해 흉내 냅니다. 설비 옆 제어기(PLC)와, 센서 값을 모아 보내는 수집 장치까지 한 프로그램에 들어 있습니다. 시간은 20배 빠르게 흐릅니다(현실 1초 = 설비 시간 20초).",
 [("서비스", "plant-sim · 프로필 ot · 망 ot-net"), ("제품", "Python(FastAPI) 자체 구현. 원래 설계의 hyd-sim · soft-PLC · 고속 DAQ · EdgeX 역할"),
  ("포트", "127.0.0.1:8000 (API · 문서 /docs)"), ("메모리 상한", "96 MB"), ("저장", "없음(메모리). 재시작하면 정상 상태로 돌아간다"),
  ("상태 확인", "/healthz · /metrics(게이지 5개)"), ("코드", "ot/plant-sim/plantsim/ — thermal.py(열 모델) · plc.py · plant.py · edge.py · daq.py")],
 "<p><b>설비.</b> HYD-01·02·03 세 대, 구조는 같습니다. 한 대 = 펌프 A와 예비 펌프 B, 구동 모터, 오일 쿨러와 팬, 탱크. 태그 19개: TS1~TS4(℃), PS1~PS6(PS1은 bar), EPS1(kW), FS1(l/min), FS2, VS1(mm/s), 가상 센서 CE·CP·SE, 설정값 FanSpeedSP·LoadSP. 정상 운전점(부하 90 %, 팬 60 %, 쿨러 깨끗함)에서 TS1 약 48 ℃, PS1 182 bar, FS1 9.0, VS1 0.6입니다. 주변 온도는 25 ℃로 고정입니다.</p>"
 "<p><b>PLC(마지막 안전장치).</b> 운전 모드 셋: <code>LOCAL</code> · <code>REMOTE_MANUAL</code> · <code>REMOTE_AUTO</code>(기본값 REMOTE_AUTO, 상태 RUN). 인터록 세 가지는 운전 중에만 판정하고 저절로 풀리지 않습니다: TS1 &gt; 65 ℃(OVERTEMP), PS1 &lt; 130 bar(LOW_PRESSURE), VS1 ≥ 2.0 mm/s(HIGH_VIBRATION). 리셋은 TS1 ≥ 55 ℃면 거부(RESET_TOO_HOT)합니다. 명령은 다섯 단계로 다시 검사합니다: ① 출처와 모드(자동 조치 HITL은 REMOTE_AUTO에서만, FUXA는 LOCAL이 아닐 때만) ② 만료 시각 ③ 최근 명령 ID 32개와 중복 ④ 쓰기 대상과 범위(팬 0~100, 부하 60~100, Reset, PumpSelect 0/1, Stop) ⑤ 트립 중이면 Reset만. 출처는 페이로드가 아니라 <b>토픽</b>으로 정합니다(<code>cmd/auto</code>면 HITL, 그 밖은 FUXA). 운전원이 REMOTE_AUTO에서 손으로 조작하면 모드가 REMOTE_MANUAL로 바뀌어 사람이 AI보다 우선합니다. 결과(ACK)는 status에 cmdId · result(DONE/REJECTED) · reason으로 실립니다.</p>"
 "<p><b>데이터 수집(DAQ).</b> 기본 <code>DAQ_PROFILE=lite</code>: TS1 · CE · PS1 · FS1 · VS1 · LoadSP는 매초, TS2 · PS2~6 · FS2는 30초 하트비트, 나머지는 데드밴드를 넘거나 10초 하트비트일 때만 보냅니다. 파형은 없습니다. <code>full</code>이면 전 태그 1 Hz에 파형(PS1 · EPS1 100 Hz, FS1 10 Hz)을 1초 묶음으로 보냅니다. status는 매초와 이벤트 때 보냅니다.</p>"
 "<p><b>강의 도구(고장 주입).</b> <code>POST /api/fault</code>로 세 가지 고장을 선형으로(기본 300 설비초) 넣습니다: 쿨러 오염 <code>cooler_degradation</code>(냉각 능력 → 43 %, 약 70 ℃로 수렴하며 65 ℃ 트립을 지남), 펌프 누설 <code>pump_leakage</code>(PS1 약 162, FS1 약 7.65, 펌프 B로 바꾸면 회복), 팬 베어링 마모 <code>fan_vibration</code>(VS1 약 1.35, 팬 100 %면 약 2.8로 인터록). <code>restore</code>로 되돌립니다. 그 밖에 <code>/api/state</code> · <code>/api/mode</code> · <code>/api/manual</code> · <code>/api/time_scale</code>(1~200) · <code>/api/reset</code>. 이 API는 인증이 없고 CORS가 전부 열려 있습니다. OT 명령 경로가 아니라 강의용 도구라는 전제입니다.</p>")
D["emqx"] = (
 "공장 안의 게시판입니다. 설비·화면·두 문이 모두 여기에만 연결하고, 칸(토픽)을 구독해 둔 쪽에 새 쪽지를 바로 밀어 줍니다. 보관하는 곳이 아니라 전달하는 곳(생중계)입니다.",
 [("서비스", "emqx · 프로필 ot · 망 ot-net"), ("제품", "EMQX 5.8 (MQTT 브로커)"), ("포트", "127.0.0.1:1883 MQTT · 127.0.0.1:18083 대시보드(비밀번호 public123)"),
  ("메모리 상한", "320 MB"), ("저장", "볼륨 없음. retain된 마지막 상태·경보만 브로커 메모리에"), ("상태 확인", "emqx ctl status (5초, 30회)"), ("인증 · 권한", "<b>없음</b>. 계정·ACL 설정이 없어 누구나 아무 토픽에 쓸 수 있다")],
 "<p>토픽 주소는 <code>plant/{설비키}/…</code>이고 설비키는 <code>hyd01</code>~<code>hyd03</code>입니다. 계측값은 QoS 0(한 번 던지고 확인 안 함), 상태(status)와 경보(alert)는 QoS 1 + retain(칸마다 마지막 한 장을 붙여 둠), 명령은 QoS 1에 retain 금지입니다. 모든 클라이언트가 깨끗한 세션(clean session)이라 끊겨 있던 동안의 값은 모아 두지 않습니다. 전체 토픽 표는 <a href=\"#dict\">데이터 사전</a>에 있습니다.</p>")
D["fuxa"] = (
 "운전원이 보는 공장 안 화면입니다. 값과 알람을 보이고, 운전원이 팬·부하를 손으로 바꾸거나 트립을 풀 수 있습니다. 사무실 쪽이 통째로 멈춰도 이 화면과 수동 조작은 돕니다.",
 [("서비스", "fuxa · 프로필 ot · 망 ot-net"), ("제품", "FUXA (웹 SCADA/HMI), 이미지 태그 latest"), ("포트", "127.0.0.1:1881"), ("메모리 상한", "192 MB"),
  ("저장", "볼륨 없음 → 기동할 때마다 ⑱ 화면 넣기가 프로젝트를 다시 올린다"), ("상태 확인", "없음"), ("코드", "ot/fuxa/build_project.py → project.json")],
 "<p>장치 1개(MQTT 클라이언트 <code>fuxa-ot</code>, <code>mqtt://emqx:1883</code>), 태그 54개(설비당 18: 값 8 · 상태 문구 4 · 경보 2 · 쓰기 3 · 모드 1), 화면 1장(「설비 현황」, 요소 57개). 알람 6개: 설비마다 TS1 높음(60~65 ℃)과 매우 높음(65 ℃ 이상, 「인터록」), IT 경보 표시등(경보 level 2). 수동 조작: 팬 0~100, 부하 60~100, 「정지 해제」(Reset=1), 모드 선택. 펌프 전환·정지는 화면에 없습니다. 값 쓰기는 <code>cmd/manual</code>에 <code>{\"FanSpeedSP\": 80}</code>처럼 값만 보내고, PLC가 cmdId(<code>FUXA-…</code>)를 붙입니다.</p>")
D["gw"] = (
 "사무실에서 공장으로 내려가는 <b>유일한 문</b>입니다. 승인된 자동 명령과 경보 표시, 이 두 가지만 공장 게시판에 씁니다. 명령은 다섯 가지 검사를 모두 통과해야 내려갑니다.",
 [("서비스", "cmd-gateway · 프로필 detect · 망 <b>ot-net + it-net</b>"), ("제품", "Python 자체 구현(원래 설계도 자체 구현)"), ("포트", "127.0.0.1:8090"),
  ("메모리 상한", "128 MB"), ("저장", "메모리: 최근 명령 ID 256개 · 판정 로그 200건 · 설비별 PLC 모드"), ("상태 확인", "/healthz(Kafka 끊김·소비 루프 죽음이면 503) · /metrics"),
  ("코드", "dmz/cmd-gateway/gw/validate.py(검증 5종) · main.py")],
 "<p><b>검증 5종</b>(<code>validate()</code> 한 함수): ① 스키마(cmdId · asset · incident · source=HITL · actions · approvedBy · expiresAt) ② 허용 목록(FAN_SET · LOAD_SET · RESET · PUMP_SELECT · STOP · FAN_BOOST · REDUCE_LOAD) ③ 만료(expiresAt이 지났으면 거부) ④ 중복(최근 256개) ⑤ 모드 + 속도(설비가 REMOTE_AUTO가 아니면 거부, 전체 합산 초당 2건 초과면 거부). 통과하면 <code>plant/{k}/cmd/auto</code>에 QoS 1로 쓰고 <code>audit</code>에 CMD_FORWARDED를, 거부하면 MQTT로는 아무것도 보내지 않고 CMD_REJECTED(검사 이름·이유)를 남깁니다. 명령 만료 120초는 게이트웨이가 아니라 ⑭ process가 붙입니다.</p>"
 "<p><b>경보 중계.</b> <code>alerts</code>를 받아 <code>plant/{k}/alert</code>에 QoS 1 + retain으로 붙입니다(level: RAISE=2, CLEAR=0, 한글 표시 문구 포함). PLC 모드를 알기 위해 <code>plant/+/status</code>도 구독합니다. 이 서비스는 공장 상태를 바꾸지 않고, 공장 상태를 근거로 거부만 합니다.</p>")
D["ing"] = (
 "공장 게시판을 <b>구독만</b> 하고 사무실 장부에 옮겨 적는, 올라가는 전용 문입니다. 공장 쪽에는 아무것도 쓰지 않습니다(코드에 발행이 없습니다).",
 [("서비스", "connect-ingest · 프로필 backbone · 망 <b>ot-net + it-net</b>"), ("제품", "Python 자체 구현(원래 설계의 Kafka Connect MQTT Source 역할)"), ("포트", "127.0.0.1:8093"),
  ("메모리 상한", "128 MB"), ("저장", "메모리 대기열 20,000건. 디스크 버퍼 없음"), ("상태 확인", "/healthz(항상 200, 내용만 보고) · /metrics · /api/ingest/stats"), ("코드", "dmz/connect-ingest/app/main.py")],
 "<p>구독: <code>plant/+/tag/+</code>(QoS 0) · <code>plant/+/wave/+</code>(QoS 0) · <code>plant/+/status</code>(QoS 1). 쓰기: <code>plant.tag</code> · <code>plant.wave</code> · <code>plant.status</code>, Kafka 키 = 설비키(<code>hyd01</code>). JSON이 아닌 메시지는 버립니다. 대기열이 가득 차면 새 메시지를 버리고 건수(<code>dropped</code>)를 셉니다. 이 건수는 <code>/api/ingest/stats</code>에서만 보이고 Prometheus 지표로는 나가지 않습니다. Kafka 쓰기가 실패한 한 건도 다시 넣지 않아 사라집니다. 지표: <code>ingest_messages_total</code> · <code>ingest_last_event_age_seconds</code> · <code>ingest_queue_depth</code>.</p>")
D["rp"] = (
 "사무실 쪽의 <b>번호 매긴 장부</b>(녹화 서버)입니다. 들어온 순서대로 디스크에 적고, 누가 읽어도 지우지 않습니다. 여러 서비스가 서로 모른 채 같은 기록을 각자 읽습니다.",
 [("서비스", "redpanda · 프로필 backbone · 망 it-net"), ("제품", "Redpanda v24.2.7 (Kafka API 호환), --smp 1 --memory 320M"), ("포트", "127.0.0.1:19092 Kafka(밖에서) · 127.0.0.1:9644 관리"),
  ("메모리 상한", "448 MB"), ("저장", "볼륨 redpanda-data"), ("상태 확인", "rpk cluster health"), ("코드", "it/redpanda/topics.sh(토픽 7개)")],
 "<p>토픽 7개, 모두 파티션 1 · 복제 1. 보존: <code>plant.tag</code> 1일, <code>plant.wave</code> 6시간, <code>plant.status</code> 7일, <code>feat.1s</code> 3일, <code>alerts</code> 365일, <code>action.cmd</code> 365일, <code>audit</code> 5년. 키가 설비라서 한 설비의 값은 들어온 순서대로 읽힙니다. 컨테이너 안에서는 <code>redpanda:9092</code>, 호스트에서는 <code>localhost:19092</code>로 접속합니다. 누가 쓰고 누가 읽는지는 <a href=\"#dict\">데이터 사전</a>의 Kafka 표에 있습니다.</p>")
D["det"] = (
 "장부에 값이 적히는 대로 읽어 이상을 찾는 검사관입니다. 온도가 오르는 중인지, 정상에서 얼마나 벗어났는지, 정해 둔 위험한 조합이 이어지는지를 봅니다. 무엇을 위험한 조합으로 볼지는 지식 지도(Neo4j)에 적힌 정의를 읽어 씁니다.",
 [("서비스", "detector · 프로필 detect · 망 it-net"), ("제품", "Python 자체 구현(원래 설계의 Apache Flink CEP + ONNX 역할)"), ("포트", "127.0.0.1:8092"), ("메모리 상한", "256 MB"),
  ("저장", "볼륨 detector-data: SQLite /data/detector.sqlite3 (체크포인트 · 오프셋 · 경보 outbox, 한 트랜잭션)"), ("상태 확인", "/healthz(Kafka · 패턴 카탈로그 · 소비 루프가 모두 정상일 때만 200)"),
  ("코드", "it/detector/det/ — features.py · pattern_runtime.py · patterns.py · cep.py · observations.py")],
 "<p><b>세 가지 계산.</b> ① 기울기: 설비 시간 60초 창의 선형회귀(TS1 · VS1). ② 이상 점수: 고정 기준(TS1 48±1, CE 84±3, VS1 0.6±0.05)에서 z-점수 셋의 RMS ÷ 4, 최대 1.0. 학습 모델이 아니라 ONNX 오토인코더 자리를 대신하는 계산입니다. ③ 패턴: Neo4j의 <code>AnomalyPattern</code>(detectionMode='held')과 <code>TESTS</code> 관계를 AND로 묶어 판정하고, 해제는 <code>clearRule</code> 식으로 판정합니다.</p>"
 "<p><b>시드된 패턴.</b> 쿨러 열화: TS1&gt;55 · CE&lt;70 · 기울기(TS1)&gt;0 → 해제 TS1&lt;52 · 기울기≤0. 펌프 누설: PS1&lt;165 · FS1&lt;8.0 · LoadSP≥80(+PLC 운전 중) → 해제 PS1≥168 · FS1≥8 또는 LoadSP&lt;80. 팬 진동: VS1&gt;1.2 · 기울기(VS1)&gt;0 → 해제 VS1&lt;1.1. 발화·해제 모두 60 <b>설비초</b> 유지(20배속이면 현실 약 3초). 상태 기계 IDLE → CANDIDATE → RAISED → CLEARING → IDLE. PLC 트립은 별도로 즉시 냅니다(OVERHEAT_TRIP · LOW_PRESSURE_TRIP · HIGH_VIBRATION_TRIP · PLC_TRIP, 심각도 CRITICAL).</p>"
 "<p><b>낡은 값 거르기.</b> 입력이 「보고 주기 + 2초(OBSERVATION_GRACE_S)」보다 오래되면 STALE, 없으면 MISSING, 미래 시각이면 거부합니다. 공백이 길면 기다리던 판정을 취소하지만 이미 RAISED인 경보는 풀지 않습니다. 정의는 기동 때와 15초마다 다시 읽고, 교체는 전부 성공하거나 전부 실패합니다. 재시작 때 시간 배율·수집 프로필이 저장값과 다르면 기동을 거부합니다. 경보는 outbox에 먼저 적고 Kafka 전송이 확인되면 지웁니다(최소 한 번 전달).</p>")
D["sink"] = (
 "장부를 읽어 기록 DB의 표로 옮겨 적는 심부름꾼입니다. DB가 잠깐 죽어도 어디까지 옮겼는지를 DB 안에 같이 적어 두어, 되살아난 뒤 빠뜨리거나 두 번 적지 않습니다.",
 [("서비스", "connect-sink · 프로필 backbone · 망 it-net"), ("제품", "Python 자체 구현(원래 설계의 Kafka Connect JDBC Sink 역할)"), ("포트", "127.0.0.1:8094"),
  ("메모리 상한", "128 MB"), ("저장", "없음(위치는 DB의 sink_offsets 표)"), ("상태 확인", "/healthz(DB · Kafka · 소비 루프 중 하나라도 나쁘면 503)"), ("코드", "it/connect-sink/app/main.py")],
 "<p>토픽 → 표: <code>plant.tag</code> → tag_1s, <code>feat.1s</code> → feat_1s, <code>alerts</code> → alerts(RAISE 추가, CLEAR 갱신), <code>action.cmd</code> → actions, <code>plant.status</code> → actions의 ack_* 칸(cmdId·result가 있고 아직 비어 있는 행만), <code>audit</code> → audit. 한 번에 최대 2,000건을 묶어 읽고, 행과 Kafka 위치를 <b>같은 트랜잭션</b>에 저장한 뒤 Kafka에 확정합니다. 잘못된 레코드는 건너뛰고 오류 수를 셉니다. DB가 끊기면 2초마다 다시 연결해 같은 묶음을 재시도합니다.</p>")
D["tsdb"] = (
 "시간 순으로 쌓이는 값을 오래 보관하는 기록 DB입니다. 1초 값은 3일, 1분 요약은 30일 남고, 경보·명령·감사 표는 지우지 않습니다.",
 [("서비스", "timescaledb · 프로필 backbone · 망 it-net"), ("제품", "TimescaleDB 2.17.2 (PostgreSQL 16), shared_buffers 64MB · 연결 40"), ("포트", "127.0.0.1:5432"),
  ("메모리 상한", "256 MB"), ("저장", "볼륨 tsdb-data"), ("계정", "hyd/hyd(소유자) · grafana(SELECT) · hyd_timeseries_reader(읽기 전용, 5초 제한, 시계열 3표만)"), ("코드", "it/timescaledb/init.sql · reader.sql")],
 "<p>표: tag_1s(시간·설비·이름·값, 6시간 청크) · feat_1s · alerts · actions · audit · sink_offsets, 연속 집계 tag_1m(1분 평균·최소·최대, 1분마다 갱신). 보존: tag_1s · feat_1s 3일, tag_1m 30일, 2시간 뒤 압축. alerts · actions · audit에는 보존 정책이 없습니다.</p>")
D["graf"] = (
 "기록 DB로 온도·냉각 효율·이상 점수의 추세를 그리는 화면입니다. 경보가 난 때(빨강), 풀린 때(초록), 승인한 조치(파랑)를 그래프 위에 표시합니다.",
 [("서비스", "grafana · 프로필 backbone · 망 it-net"), ("제품", "Grafana 11.3.0"), ("포트", "127.0.0.1:3000 (익명 Viewer · admin/admin)"), ("메모리 상한", "192 MB"),
  ("데이터 원천", "TimescaleDB 하나(계정 grafana)"), ("코드", "it/grafana/provisioning · build_dashboard.py")],
 "<p>대시보드 「HYD 설비 추세 · 경보 · 조치」(uid hyd-trend, 5초 갱신, 기본 10분, 설비 선택 변수): 숫자 6 · 시계열 5 · 표 3(경보 이력 · 조치 · 감사 로그) = 패널 14개. 포털 「실시간 모니터링」이 이 화면을 끼워 보여 줍니다(임베딩 허용).</p>")
D["prom"] = (
 "서비스들이 살아 있는지, 수집이 멈추지 않았는지를 10초마다 살피는 감시 장치입니다. 공정 값이 아니라 시스템의 건강을 봅니다. 기본 구성에서는 꺼져 있습니다.",
 [("서비스", "prometheus · 프로필 <b>monitor(선택)</b> · 망 it-net"), ("제품", "Prometheus v2.55.1"), ("포트", "127.0.0.1:9090"), ("메모리 상한", "128 MB"), ("코드", "it/prometheus/prometheus.yml · rules.yml")],
 "<p>수집 대상 6개(10초): connect-ingest · cmd-gateway · detector · connect-sink · agent · process의 <code>/metrics</code>. 규칙 2개: IngestStalled(마지막 수집 30초 초과가 30초 지속) · GatewayRejections(5분에 거부 3건 초과). Alertmanager는 구성돼 있지 않아 규칙은 Prometheus 화면에서만 보입니다. ㉔ 판단 엔진 창구가 PromQL 도구로 이 서버를 조회합니다.</p>")
D["neo"] = (
 "설비·센서·고장·원인·조치 방법(SOP)·규칙·업무 지표가 서로 어떻게 이어지는지 적어 둔 <b>지식 지도</b>(온톨로지)입니다. 검사관은 여기서 「무엇을 이상으로 볼지」를, AI는 「원인 후보와 조치 방법」을 찾습니다.",
 [("서비스", "neo4j · 프로필 knowledge · 망 it-net"), ("제품", "Neo4j 5.26 Community + APOC 플러그인"), ("포트", "127.0.0.1:7474 브라우저 · 127.0.0.1:7687 Bolt (neo4j/hydpass123)"),
  ("메모리 상한", "1.5 GB (힙 128→512 MB, 페이지 캐시 48 MB)"), ("저장", "볼륨 neo4j-data"), ("코드", "it/neo4j/v2/ — schema.json · constraints.cypher · instances.cypher · knowledge_a098.cypher · detector-patterns.cypher · templates/")],
 "<p><b>온톨로지 v2</b>: 7개 층 46개 클래스, 관계 타입 72개. 층: 가치(BSC: 관점 · 전략 목표 · 성과 지표) → 프로세스(BPMN) → 리소스(조직 · 역할 · 시스템 · 설비 · 부품 · 센서 · 구동기) → 설비 진단(ISO 13374: 이상 패턴 · 증상 · 고장 유형 · 원인 · 증거 · 매뉴얼 절) → 스킬 · 규칙(조치 방법 = 스킬 = SOP, DMN 결정 · 규칙 · 입력) → 외부 변수(예측 포함) → 운영 기록(사건 · 판단 기록 · 인제스천 기록). 시드: 이상 패턴 7 · 고장 유형 7 · 원인 8 · 스킬(SOP) 16 · 단계 49 · 규칙 24 등(파일 기준 집계). 기록된 운영 DB 실측은 노드 3,575 · 관계 8,889(매뉴얼 적재 포함).</p>"
 "<p>경로 예: 센서 TS1 ← 증상 「TS1 상승」 ← 이상 패턴 「쿨러 열화」, 증상 → 고장 유형 「냉각 손실」 ← 원인 「쿨러 핀 오염」(사전확률 0.6, 증거 「CE 30초 평균 &lt; 70」), 고장 유형 → 스킬 「팬 최대」(SOP-COOL-01) → 조치 「FAN_SET 100」 → 구동기 「팬」, 스킬 단계 → 매뉴얼 절 HM-7.3. 에이전트용 Cypher 템플릿(t1 원인, t2 스킬, t3 예측 모델)이 이 경로를 따라갑니다.</p>")
D["agent"] = (
 "경보가 나면 깨어나 <b>원인을 조사하고 조치 카드를 쓰는</b> AI 조사관입니다. 설비에 직접 명령할 수 없습니다. 카드를 업무 진행 쪽에 제출할 뿐이고, 사람의 승인과 게이트웨이·PLC 검사를 거쳐야 설비가 움직입니다.",
 [("서비스", "agent · 프로필 agent · 망 it-net"), ("제품", "Python 자체 구현(원래 설계의 LangGraph · MCP 서버 · LiteLLM 역할)"), ("포트", "127.0.0.1:8091"), ("메모리 상한", "192 MB"),
  ("저장", "실행 트레이스는 메모리(재시작하면 사라짐). 제출한 카드는 ⑭에 보존"), ("코드", "it/agent/agentsvc/ — main.py(pipeline) · tools/mcp_*.py · card.py · guardrail.py · llm.py · cards.py · decide.py")],
 "<p><b>legacy 모드 자동 파이프라인</b>(경보 RAISE마다): ① process에 경보 정책 확인(대응 대상이 아니면 보류) ② 신선도: 최신 TS1이 60초 이내이고 수집 다리가 살아 있는지 ③ Neo4j t1 템플릿으로 원인 후보 ④ 원인별 증거 SQL을 기록 DB에 읽기 전용 계정으로(5초 제한, 시계열 3표만) → PASS · FAIL · UNKNOWN ⑤ 점수 = 사전확률 × 통과 가중치 ÷ 전체 가중치, 근거가 모자라면 보류 ⑥ 1순위 원인의 SOP 스킬(t2) ⑦ 카드 조립과 요약 ⑧ 가드레일 ⑨ <code>POST /api/incidents</code>로 제출, 승인 대기가 되면 조치 카드 판단(규칙 · 예측 · BSC 득실 · 선례)을 <code>/api/decisions</code>로 제출.</p>"
 "<p><b>가드레일.</b> 카드에 writes · cmdId · expiresAt · mqtt · topic 같은 명령 필드가 있으면 거부, 근거 인용 누락 · UNKNOWN 증거 · 범위 밖 값 · 신선도 실패도 거부합니다. 조치 카드는 선택 규칙 인용 · 제외 규칙 위반 없음 · 승인 역할 · SOP 단계를 확인합니다.</p>"
 "<p><b>LLM은 요약 세 문장에만</b> 씁니다(카드 밖 내용 추가 금지, 직접 명령 금지, 8초 제한, 재시도 없음). 키가 없거나 실패하면 정해진 문장을 씁니다. 판단(순위 · 규칙 · 승인 역할)은 LLM 없이 계산합니다. <code>PROCESS_MODE=instance</code>면 이 자동 파이프라인은 멈추고, ⑭가 <code>/api/agent/evaluate</code>로 부를 때만 같은 계산을 합니다(AGENT_BRIDGE=legacy).</p>")
D["proc"] = (
 "경보 한 건을 업무 한 건으로 끝까지 끌고 가는 <b>업무 진행표(결재 라인)</b>입니다. AI 카드를 받아 사람에게 보이고, 승인되면 명령을 만들고, 정말 나아졌는지 다시 본 뒤 작업지시를 내고 닫습니다.",
 [("서비스", "process · 프로필 process · 망 it-net"), ("제품", "Python 자체 구현(원래 설계의 Process-GPT · Flowable 역할)"), ("포트", "127.0.0.1:8080"), ("메모리 상한", "512 MB (PROCESS_MEM_LIMIT)"),
  ("저장", "볼륨 process-data: process.sqlite3(사건 · 판단 · 감사) · manuals.sqlite3(매뉴얼 원문). instance 모드는 ㉒ Supabase"), ("코드", "it/process/procsvc/ — definition.py · machine.py · main.py · instance_mode.py · procdb.py · definitions/*.json")],
 "<p><b>legacy 상태 흐름</b>: GUIDE_RECEIVED → AWAITING_APPROVAL → CMD_ISSUED → AWAITING_ACK → ACKED → RE_OBSERVING → RESOLVED → WORK_ORDER_CREATED → CLOSED. 실패 종료: ESCALATED · REJECTED_BY_OPERATOR · RESOLVED_WITHOUT_ACTION. 명령 만료 120초, ACK 대기 30초(없으면 ESCALATED), 재관측 900 설비초 ÷ 배속(20배속이면 45초), 회복 기준(쿨러 TS1&lt;55 · 펌프 PS1≥165 · 팬 VS1&lt;1.2)과 경보 CLEAR가 함께 있어야 RESOLVED. 값은 이미 기준 안인데 CLEAR가 늦으면 1/3 창을 최대 3번 연장합니다. 승인 전에 CLEAR가 오면 조치 없이 해결로 닫습니다. RESOLVED 뒤 ⑮에 CMMS 작업지시를 실행해 실제 번호를 받아야 CLOSED입니다.</p>"
 "<p><b>승인은 카드 단위.</b> 원자 명령 승인 API(<code>/approve</code>)는 항상 409입니다. 담당자는 <code>/api/incidents/{id}/decide</code>로 SOP 조치 카드 하나를 고르고, 팬·부하 값은 카드 범위 안에서만 조정합니다. 명령은 <code>action.cmd</code>에, 모든 단계는 <code>audit</code>에 적습니다.</p>"
 "<p><b>instance 모드</b>(<code>PROCESS_MODE=instance</code>): 경보 RAISE 하나가 정의 <code>anomaly_response_v22.json</code>의 <b>프로세스 인스턴스</b> 하나를 엽니다. 흐름: 경보 → 진단 → 후보 → 규정 확인 → 순위(AI Task) → 선택(운전원 Task, 10분 넘으면 상향) → 제어 분기 → 명령 → 재관측 → 회복 분기 → 작업지시 → 종료. Task는 ㉒의 todolist에 쌓이고, AI Task는 ㉕ AI 직원이 집어 갑니다(워커가 없을 때 AGENT_BRIDGE=legacy면 ⑬ 계산 결과로 대신 채움). 원천 경보는 Supabase inbox를 거쳐 묶음으로 확정합니다. 사건·판단은 Neo4j에도 기록(투영)하고, 매뉴얼 인제스천 API도 여기 있습니다.</p>")
D["ent"] = (
 "주문·납기·재고·정비 이력·품질·공급사·전력 같은 <b>회사 업무 시스템을 흉내 낸</b> 서비스입니다. AI는 읽기만 하고, 사람이 승인한 업무 조치(작업지시·구매요청 등)만 여기서 실행됩니다.",
 [("서비스", "enterprise-sim · 프로필 enterprise · 망 it-net"), ("제품", "Python 자체 구현(원래: SAP ERP · MES · CMMS · QMS · SCM · EMS)"), ("포트", "127.0.0.1:8095"), ("메모리 상한", "96 MB"),
  ("저장", "볼륨 enterprise-data: SQLite 상태. ENTERPRISE_BACKEND=supabase면 ㉒의 ent 스키마가 원천"), ("코드", "it/enterprise-sim/entsim/ — data.py · state.py · supabase_backend.py")],
 "<p>읽기: <code>/mes/orders</code>(주문 · 납기 · 잔량 · 대체 설비) · <code>/erp/contract</code>(지체 위약금 · 고객 등급) · <code>/erp/inventory</code> · <code>/cmms/history</code>(세척 주기 · 비용 · 예비 펌프) · <code>/qms/lots</code>(고온 로트 · 불량 확률) · <code>/scm/suppliers</code>(단가 · 고장률 · 납기) · <code>/ems/demand</code>(계약 전력). 실행: <code>POST /api/exec</code> — 스킬 7종(정비 일정 · 생산 재배정 · 부품 구매 · 로트 보류/해제 · 대체 출하 · 수요 제어)과 되돌리기(보상) 4종, 거래 기록 <code>/api/transactions</code>.</p>")
D["portal"] = (
 "담당자가 브라우저로 여는 창구입니다. 이 서버는 화면 파일만 내줍니다. 화면 안의 스크립트가 <b>브라우저에서 각 서비스를 직접</b> 불러 사건·카드·지식 지도·인스턴스를 보여 주고 승인 버튼을 보냅니다.",
 [("서비스", "portal · 프로필 process · 망 it-net"), ("제품", "nginx 1.27-alpine (정적 파일만, 프록시 설정 없음)"), ("포트", "127.0.0.1:8088"), ("메모리 상한", "32 MB"), ("코드", "it/portal/www/ — index.html · app.js · layers.js · enterprise.js")],
 "<p>메뉴: 실습 홈 · 시스템 아키텍처 · 결함 시뮬레이션 · 이상 확인·조치 · 실시간 모니터링(L1~L6) · 온톨로지 지식 지도 · 에이전트 스킬 · 조치 판단 규칙 · 업무 프로세스 · 프로세스 인스턴스(L7~L9). 브라우저가 부르는 곳: 8000 · 8080 · 8090 · 8091 · 8092 · 8095 · 3000({c:c_browser}). 그래서 이 포털은 그 포트들이 열린 같은 PC의 브라우저에서만 제대로 돕니다.</p>")
D["llm"] = (
 "글을 쓰고 추론하는 외부 AI 서비스입니다. 인터넷 너머에 있고, 키가 있을 때만 씁니다. 두 곳에서 다른 목적으로 부릅니다.",
 [("위치", "밖(인터넷). 키는 .env에만(저장소에 없음)"), ("⑬ agent에서", "카드 요약 3문장. OpenAI 호환 /chat/completions(기본 gpt-4o-mini, OPENAI_BASE_URL로 다른 호환 서버 지정 가능) 또는 Anthropic(기본 claude-sonnet-4-6). 8초 · 600 토큰"),
  ("㉕ AI 직원에서", "Claude Code CLI가 Anthropic API로 작업 전체를 수행(ANTHROPIC_API_KEY, 또는 호스트에서 로그인한 CLI. 호스트 스크립트 기본 모델 opus)")],
 "<p>legacy 모드의 판단(원인 점수 · 카드 순위 · 승인 역할)은 LLM 없이 계산되고, LLM이 없어도 전체 흐름이 돕니다. instance 모드의 AI Task는 LLM(Claude Code)이 도구를 써서 수행하므로 키나 로그인이 있어야 합니다.</p>")
D["finit"] = (
 "기동할 때 운전실 화면의 설정(태그·화면·알람)을 넣고 끝나는 도우미입니다.",
 [("서비스", "fuxa-init · 프로필 ot · 1회(restart no)"), ("제품", "python:3.12-slim, ./ot/fuxa 읽기 전용 마운트"), ("메모리 상한", "64 MB")],
 "<p>FUXA가 뜨기를 최대 180초 기다렸다가 <code>POST /api/project</code>로 project.json을 올리고(5회까지 재시도) 화면 목록으로 반영을 확인합니다. FUXA에 볼륨이 없으므로 FUXA를 다시 만들면 이 도우미도 다시 돌려야 합니다.</p>")
D["tinit"] = (
 "기동할 때 장부의 칸(토픽 7개)을 보존 기간과 함께 만들고 끝나는 도우미입니다.",
 [("서비스", "topic-init · 프로필 backbone · 1회"), ("제품", "redpanda 이미지의 rpk"), ("메모리 상한", "128 MB")],
 "<p>이미 있으면 넘어갑니다. 다시 돌 때 plant.tag · plant.wave · feat.1s · plant.status 네 개는 보존 기간을 다시 맞춥니다(alerts · action.cmd · audit은 처음 값 유지). 여러 서비스가 이 도우미의 성공 완료를 기다렸다가 뜹니다.</p>")
D["seed"] = (
 "기동할 때 지식 지도에 온톨로지를 채우고 끝나는 도우미입니다. 여러 번 돌려도 같은 결과(멱등)입니다.",
 [("서비스", "kg-seed · 프로필 knowledge · 1회"), ("제품", "neo4j 이미지의 cypher-shell, ./it/neo4j 읽기 전용 마운트"), ("메모리 상한", "384 MB"), ("코드", "it/neo4j/seed.sh")],
 "<p>순서: Neo4j를 최대 3분 기다림 → 옛 v1 지식이 있으면 그래프 전체와 제약을 지움 → <code>constraints.cypher</code> → <code>instances.cypher</code> → <code>knowledge_a098.cypher</code> → 라벨별 개수와 「고장 유형 → SOP」 목록 출력. <b>주의</b>: 탐지 정의 보강 파일 <code>detector-patterns.cypher</code>는 이 도우미가 넣지 않습니다(<code>scripts/ontology_v2.py</code>만 넣음). <a href=\"#limits\">알려진 한계</a>를 보세요.</p>")
D["cons"] = (
 "장부의 칸과 쪽지를 눈으로 열어 보는 화면입니다. 기본 구성에서는 꺼져 있습니다.",
 [("서비스", "redpanda-console · 프로필 <b>tools(선택)</b> · 망 it-net"), ("제품", "Redpanda Console v2.7.2"), ("포트", "127.0.0.1:8085"), ("메모리 상한", "128 MB")],
 "<p>토픽 목록과 메시지를 봅니다. 손으로 메시지를 넣을 수도 있습니다(예: 형식이 틀린 <code>action.cmd</code>를 넣으면 게이트웨이 스키마 검사에서 거부되는 것을 볼 수 있습니다).</p>")
D["supa"] = (
 "instance 모드의 <b>업무 기록부</b>입니다. 프로세스 정의, 경보마다 열린 인스턴스, 누가 할 일인지 적힌 Task 목록, 회사 업무 DB(ent)가 여기 있습니다. AI 직원은 이 목록에서 자기 일을 집어 갑니다.",
 [("위치", "compose 밖. <code>cd it/supabase &amp;&amp; supabase start</code>로 호스트에 따로 띄운다. 컨테이너는 host.docker.internal:54322로 접속"),
  ("포트", "API 54321 · DB 54322 · Studio 54323"), ("스키마", "public(업무 엔진) · ent(기업 DB)"), ("계정", "postgres/postgres(로컬) · hyd_enterprise_reader(읽기 전용, 5초 제한)"), ("코드", "it/supabase/ — config.toml · migrations/ · seed.sql")],
 "<p>public 표: tenants(테넌트별 MCP 서버 목록) · users · proc_def(+판본) · form_def · bpm_proc_inst(인스턴스) · todolist(Task) · events · notifications · approval_outbox · source_inbox · effect_receipt 등. 함수: <code>fetch_pending_task</code>(Task 집기, 120초 임대) · <code>save_task_result</code>. ent 스키마: 기업 데이터 표 14개와 읽기 함수. 씨앗 데이터는 테넌트 <code>hyd</code>에 MCP 서버 셋(neo4j · enterprise · hyd-dmn)을 등록합니다.</p>")
D["entmcp"] = (
 "AI 직원이 회사 업무 DB를 <b>읽기만</b> 할 수 있게 열어 둔 창구(MCP 서버)입니다.",
 [("서비스", "enterprise-mcp · 프로필 cliagents · 망 it-net"), ("포트", "127.0.0.1:8199 (/mcp)"), ("메모리 상한", "160 MB"), ("접속", "㉒ ent 스키마, 계정 hyd_enterprise_reader"), ("코드", "it/enterprise-mcp/")],
 "<p>도구 10개: mes_orders · erp_contract · erp_inventory · cmms_history · qms_lots · scm_suppliers · ems_demand · describe_schema · describe_catalog · query(SELECT만, 최대 200행). 표 이름을 몰라도 describe 도구로 구조를 먼저 읽고 질의를 만들 수 있습니다.</p>")
D["dmnmcp"] = (
 "반복되는 판단(규칙·순위·예측)은 정해진 계산으로 하고, AI 직원은 그 계산을 <b>도구로 불러 쓰게</b> 만든 창구입니다. LLM은 자료를 모으고 설명하고, 결정 계산은 이 엔진이 합니다.",
 [("서비스", "dmn-mcp · 프로필 cliagents · 망 it-net"), ("포트", "127.0.0.1:8198 (/mcp)"), ("메모리 상한", "192 MB"), ("접속", "Neo4j · TimescaleDB(읽기 전용 계정) · Prometheus · process · enterprise-sim · connect-ingest"), ("코드", "it/dmn-mcp/ (⑬의 agentsvc 판단 엔진을 감쌈)")],
 "<p>도구 14개: diagnose · dmn_rules · inputs · gather_facts · timeseries_schema · timeseries_query · prometheus_metadata · prometheus_series · prometheus_query · evaluate_cards · forecast_actions · precedents · tradeoffs · submit_decision. 쓰기는 <code>submit_decision</code>(→ ⑭ <code>/api/decisions</code>) 하나뿐입니다.</p>")
D["worker"] = (
 "instance 모드의 <b>AI 직원</b>입니다. Task 목록에서 AI 몫의 일을 집어, Claude Code에게 허락된 도구만 주고 수행시킨 뒤 결과를 양식에 맞춰 제출합니다. 질문이 생기면 멈추고 사람의 답을 기다립니다.",
 [("서비스", "agent-worker · 프로필 cliagents · 망 it-net (또는 <code>scripts/run_worker_host.sh</code>로 호스트에서)"), ("포트", "127.0.0.1:8097 (/health · /agents)"), ("메모리 상한", "768 MB"),
  ("저장", "볼륨 worker-data: 작업별 작업공간 · Claude Code 세션(재시작 뒤 이어감)"), ("허용 도구", "Neo4j 스키마·읽기 Cypher · enterprise 전부 · hyd-dmn 전부 · Read · Glob · Grep"), ("코드", "it/agent-worker/worker/ — runner.py · bridge.py · settings.py")],
 "<p>3초마다 <code>fetch_pending_task('cliagents', …)</code> → 작업공간과 테넌트 MCP 목록으로 <code>.mcp.json</code> 작성 → <code>claude</code> CLI를 <code>--allowedTools</code>로 실행(제한 1,800초, 임대 30초마다 갱신) → 결과가 폼 계약에 맞는지 검사, 틀리면 최대 2번 고쳐 달라고 요청 → <code>save_task_result(final)</code>로 저장(워커 저장소의 조건부 UPDATE: 점유자 · IN_PROGRESS · STARTED가 그대로일 때만 쓰고, 점유를 잃었으면 저장하지 않고 취소로 끝냄). 워커가 죽으면 임대가 끝난 작업을 다른 워커가 회수합니다. 호스트 실행 때는 컨테이너 이름을 127.0.0.1로 바꿔 접속합니다(MCP_HOST_REWRITE).</p>")
D["kgmcp"] = (
 "AI 직원이 지식 지도를 읽을 때 쓰는 창구입니다. 작업 때마다 AI 직원 안에서 잠깐 떠서 읽기 전용으로만 질의합니다.",
 [("실행", "uvx mcp-neo4j-cypher, stdio, 읽기 전용(READ_ONLY)"), ("등록", "㉒ tenants.hyd.mcp 씨앗 데이터"), ("허용 도구", "get_neo4j_schema · read_neo4j_cypher")],
 "<p>별도 컨테이너가 아니라 ㉕가 작업마다 띄우는 자식 프로세스입니다. 그래서 그림에서 ㉕ 안에 그렸습니다. Bolt 7687로 ⑫에 붙습니다({c:c_kgmcp_neo}).</p>")
assert set(D) == set(PART), set(D) ^ set(PART)

# ═════════════════════════ 연결 설명: (프로토콜·포트·계정, 실어 나르는 것) ═════════════════════════
C = {}
C["c_sim_pub"] = ("MQTT 3.1.1, emqx:1883, 클라이언트 plant-sim-edge, 인증 없음", "계측 <code>plant/{k}/tag/{이름}</code>(QoS 0) · 파형 <code>wave/…</code>(full일 때) · 상태 <code>status</code>(QoS 1 retain, ACK 포함).")
C["c_sim_sub"] = ("C1과 같은 연결(구독)", "자동 명령 <code>cmd/auto</code> · 수동 명령 <code>cmd/manual</code> · 모드 <code>mode</code>(모두 QoS 1). 연결은 설비 쪽이 열었지만 데이터는 게시판 → 설비로 흐른다.")
C["c_fuxa"] = ("MQTT, 클라이언트 fuxa-ot", "내림: 값 8종 · 상태 문구 · 경보 표시. 올림: 수동 명령(팬 · 부하 · 리셋) · 모드.")
C["c_oper"] = ("HTTP 127.0.0.1:1881 (인증 없음)", "운전원이 화면을 보고 버튼을 누른다.")
C["c_finit"] = ("HTTP POST /api/project (1회)", "build_project.py가 만든 화면 프로젝트.")
C["c_ing_sub"] = ("MQTT, clean session, keepalive 30", "구독 <code>plant/+/tag/+</code> · <code>plant/+/wave/+</code>(QoS 0) · <code>plant/+/status</code>(QoS 1). 게시판에 아무것도 쓰지 않는다.")
C["c_ing_pub"] = ("Kafka redpanda:9092", "<code>plant.tag</code> · <code>plant.wave</code> · <code>plant.status</code>(키 = 설비).")
C["c_det"] = ("Kafka, 그룹 detector, 최신부터, 수동 확정", "읽기: plant.tag · plant.wave · plant.status. 쓰기: feat.1s(TS1마다 1건) · alerts(RAISE/CLEAR · 트립).")
C["c_det_neo"] = ("Bolt 7687, 읽기 트랜잭션 5초", "이상 패턴 정의(detectionMode='held', TESTS 조건, clearRule, 유지 시간). 기동 때와 15초마다.")
C["c_sink_sub"] = ("Kafka, 그룹 connect-sink, 처음부터, 수동 확정, 최대 2,000건 묶음", "plant.tag · feat.1s · alerts · action.cmd · plant.status · audit.")
C["c_sink_db"] = ("PostgreSQL 5432, 계정 hyd", "행과 Kafka 위치(sink_offsets)를 한 트랜잭션에.")
C["c_graf"] = ("PostgreSQL 5432, 계정 grafana(SELECT)", "추세 · 경보 이력 · 조치 · 감사 · 주석 3종.")
C["c_gw_cmd"] = ("Kafka, 그룹 cmd-gateway, 최신부터", "읽기: <code>action.cmd</code>(승인된 명령). 쓰기: <code>audit</code>(CMD_FORWARDED · CMD_REJECTED).")
C["c_gw_alert"] = ("C13과 같은 소비자", "읽기: <code>alerts</code>(공장 화면에 띄울 경보).")
C["c_gw_auto"] = ("MQTT, QoS 1, retain 금지", "검증 5종을 통과한 명령만 <code>plant/{k}/cmd/auto</code> = {cmdId, source:HITL, expiresAt, writes}.")
C["c_gw_disp"] = ("MQTT, QoS 1, retain", "<code>plant/{k}/alert</code> = {alertId, pattern, severity, state, level 2/0, 표시 문구}.")
C["c_gw_stat"] = ("MQTT 구독 QoS 1", "<code>plant/+/status</code>에서 설비별 PLC 모드를 기억해 검사 ⑤에 쓴다.")
C["c_ag_alert"] = ("Kafka, 그룹 agent, 최신부터", "<code>alerts</code> RAISE가 조사를 깨운다. <b>legacy 모드에서만</b>(instance면 자동 파이프라인 정지).")
C["c_ag_neo"] = ("Bolt 7687, 허용된 템플릿만, 5초", "t1 원인 후보 · t2 SOP 스킬 · t3 예측 모델 · 온톨로지 화면용 조회.")
C["c_ag_tsdb"] = ("PostgreSQL, 계정 hyd_timeseries_reader(읽기 전용, 5초)", "신선도(최신 TS1 나이)와 원인별 증거 SQL(tag_1s · feat_1s · tag_1m만).")
C["c_ag_llm"] = ("HTTPS(인터넷), 8초, 재시도 없음", "카드 JSON 일부(경보 · 원인 · 추천 · 신선도) → 한국어 요약 3문장. 실패하면 정해진 문장.")
C["c_ag_ent"] = ("HTTP GET enterprise-sim:8095", "/mes/orders · /erp/contract · /qms/lots · /cmms/history(읽기만).")
C["c_ag_proc"] = ("HTTP process:8080", "agent → process: 경보 정책 확인 · 카드 제출 <code>/api/incidents</code> · 판단 제출 <code>/api/decisions</code> · PLC 상태 조회 <code>/api/plant/{a}/status</code>.")
C["c_ag_ing"] = ("HTTP GET connect-ingest:8093/healthz (그림: 대상 상자의 작은 표)", "수집 다리가 살아 있는지(신선도 판정의 한 조건).")
C["c_ag_supa"] = ("PostgreSQL host.docker.internal:54322, 계정 hyd_enterprise_reader (그림: 작은 표)", "물리 입력 데이터(InputData) 읽기.")
C["c_proc_rp"] = ("Kafka, 그룹 process", "읽기: <code>alerts</code>(RAISE/CLEAR) · <code>plant.status</code>(ACK). 쓰기: <code>action.cmd</code>(만료 120초) · <code>audit</code>.")
C["c_proc_tsdb"] = ("PostgreSQL 5432", "재관측 회복 판정용 최신 태그(tag_1s) 읽기.")
C["c_proc_neo"] = ("Bolt 7687", "사건 · 판단 기록 투영(CaseProjection · Incident · DecisionCase), 지식 관리 API(스킬 편집 · 매뉴얼 적재 · 되돌리기)의 쓰기.")
C["c_proc_ent"] = ("HTTP enterprise-sim:8095", "<code>POST /api/exec</code>(작업지시 · 구매요청 등 승인된 업무 실행) · 거래 기록 조회.")
C["c_proc_ag"] = ("HTTP agent:8091, 90초", "instance 모드 + AGENT_BRIDGE=legacy일 때 <code>/api/agent/evaluate</code>를 불러 AI Task 4개를 그 결과로 채운다.")
C["c_proc_supa"] = ("PostgreSQL host.docker.internal:54322 (PROCESS_REPO=pg)", "정의 · 인스턴스 · todolist · events · inbox · 승인 outbox · 효과 영수증. instance 모드에서.")
C["c_proc_wk"] = ("HTTP WORKER_URL /health · /agents (그림: 작은 표)", "process 워커 상태 API(GET /api/agents/status)가 보는 워커 상태. 감시용(포털 화면에는 없음).")
C["c_staff"] = ("HTTP 127.0.0.1:8088", "포털 화면 파일(HTML · JS)을 받는다.")
C["c_browser"] = ("HTTP, 브라우저 → 127.0.0.1의 각 포트 (그림: 대상 상자의 작은 표)", "8000 고장 주입 · 8090 게이트웨이 로그 · 8092 탐지 상태 · 8091 트레이스 · 온톨로지 · 8080 사건 · 승인 · 인스턴스 · 8095 기업 데이터 · 3000 Grafana 끼워 보기. 서비스들은 CORS를 전부 허용한다.")
C["c_prom"] = ("HTTP 긁기 10초 (그림: 대상 상자의 작은 회색 표)", "6개 서비스의 /metrics. monitor 프로필일 때만.")
C["c_cons"] = ("Kafka redpanda:9092", "토픽 · 메시지 보기와 손으로 넣기. tools 프로필일 때만.")
C["c_tinit"] = ("Kafka 관리 명령 rpk (1회)", "토픽 7개 생성 · 보존 기간 설정.")
C["c_seed"] = ("Bolt cypher-shell (1회)", "제약 → 인스턴스 → 전문가 지식 a098.")
C["c_ent_supa"] = ("PostgreSQL 54322 (ENTERPRISE_BACKEND=supabase일 때)", "ent 스키마 읽기, <code>ent.exec_skill</code> · <code>ent.exec_compensation</code>으로 실행.")
C["c_wk_supa"] = ("PostgreSQL 54322", "<code>fetch_pending_task</code>(안에서 <code>claim_process_workitems</code> RPC로 점유, 임대 120초) · 임대 갱신(<code>renew_task_lease</code>) · <code>save_task_result</code>(점유자 조건부 UPDATE) · <code>record_events_bulk</code> · 테넌트 MCP 목록.")
C["c_wk_llm"] = ("HTTPS(인터넷), Claude Code CLI", "작업 지시 · 도구 호출 결과를 주고받으며 Task를 수행. 제한 1,800초.")
C["c_wk_dmn"] = ("MCP over HTTP, dmn-mcp:8198/mcp", "진단 · 규칙 · 입력 · 사실 수집 · 시계열 · PromQL · 카드 평가 · 예측 · 선례 · 득실 · 판단 제출.")
C["c_wk_ent"] = ("MCP over HTTP, enterprise-mcp:8199/mcp", "기업 데이터 읽기 도구 10개.")
C["c_kgmcp_neo"] = ("Bolt 7687, 읽기 전용 (그림: 작은 표)", "스키마 읽기와 읽기 Cypher.")
C["c_entmcp_supa"] = ("PostgreSQL 54322, 계정 hyd_enterprise_reader", "ent 스키마 SELECT(최대 200행, 5초).")
C["c_dmn"] = ("Bolt · PostgreSQL · HTTP (그림: 대상 상자의 작은 표)", "Neo4j 지식 · 기록 DB(읽기 전용 계정) · process(<code>submit_decision</code>만 쓰기) · enterprise-sim · 수집 다리 상태 · Prometheus.")
assert set(C) == set(L), set(C) ^ set(L)


# ═════════════════════════ 참조 치환 ═════════════════════════
def n(k):
    return f'<a class="nref nz-{PART[k][4]}" href="#p{NO[k]}" title="{html.escape(PART[k][1])}">{CIRC[NO[k]]}</a>'


def nn(k):
    return f'{n(k)}&nbsp;{PART[k][1]}'


def c(k):
    x = L[k]
    return f'<a class="cref k-{x["kind"]}" href="#c{x["no"]}">C{x["no"]}</a>'


def sub(t):
    t = re.sub(r"\{nn:(\w+)\}", lambda m: nn(m.group(1)), t)
    t = re.sub(r"\{n:(\w+)\}", lambda m: n(m.group(1)), t)
    return re.sub(r"\{c:(\w+)\}", lambda m: c(m.group(1)), t)


# ═════════════════════════ 그림 ═════════════════════════
W, H = 1560, 1910
ZONES = [  # y0, y1, x1, 이름, 설명, 배경, 테두리, 글자
 (10, 160, 1552, "L1 · 현장", "설비 3대 + PLC (진짜 기계 대신 계산)", "#f3f1ec", "#b9ae98", "#6b604a"),
 (170, 400, 1552, "L2 · L6 · OT 공장 망 (ot-net)", "사무실 쪽이 멈춰도 여기는 돈다", "#fcefe2", "#cf8a45", "#9a5a1c"),
 (410, 580, 1552, "L3 · DMZ 역할", "두 망에 동시에 붙은 서비스 2개 (전용 망 · 방화벽 없음)", "#f0ecf8", "#8a76bf", "#5b4691"),
 (590, 980, 1552, "L3~L6 · IT 데이터 (it-net)", "장부 · 검사 · 기록 · 화면 · 감시", "#e7f3f6", "#3f8ea3", "#1f6378"),
 (990, 1260, 1345, "L7 · L8 · 지식과 AI (it-net)", "원인을 찾고 조치를 제안", "#ebeffa", "#5a6fbf", "#394b98"),
 (1270, 1560, 1345, "L9 · 업무와 사람 (it-net)", "승인은 사람이", "#f2f4ec", "#7a8a4a", "#56662a"),
 (1570, 1900, 1345, "instance 모드 · 인스턴스와 AI 직원", "cliagents 프로필 + Supabase (기본 구성에는 없음)", "#f6eef3", "#b0739a", "#7d3f66"),
]
STY = dict(data=("", 2.2), cmd=("", 3.0), alert=("7 4", 2.2), api=("", 1.7), mon=("2 4", 1.6), once=("9 5", 1.5), human=("", 1.6))


def esc(t):
    return html.escape(t, quote=True)


def text(x, y, t, size=13, weight=400, fill="#1d2830", anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{esc(t)}</text>'


def tw(t, size):
    return sum(size * (0.98 if ord(ch) > 0x1100 else 0.62) for ch in t)


def shorten(p, which, d):
    p = list(p)
    if which == "end":
        (x0, y0), (x1, y1) = p[-2], p[-1]
    else:
        (x0, y0), (x1, y1) = p[1], p[0]
    ln = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
    nx, ny = x1 - (x1 - x0) / ln * d, y1 - (y1 - y0) / ln * d
    if which == "end":
        p[-1] = (nx, ny)
    else:
        p[0] = (nx, ny)
    return p


def svg():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="hyd-iot-edu 전체 아키텍처: 부품 {len(PART)}개, 연결 {len(L)}개, 현장에서 업무까지 위에서 아래로" class="arch">', "<defs>"]
    for k, col in COL.items():
        o.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    for y0, y1, x1, name, desc, bg, bd, fg in ZONES:
        o.append(f'<rect x="8" y="{y0}" width="{x1 - 8}" height="{y1 - y0}" rx="14" fill="{bg}" stroke="{bd}" stroke-width="1.4"/>')
    # 밖(인터넷) 기둥
    o.append('<rect x="1355" y="990" width="197" height="910" rx="14" fill="#f4f5f6" stroke="#9aa3aa" stroke-width="1.4" stroke-dasharray="6 4"/>')
    o.append(text(1453, 1017, "밖 (인터넷)", 16, 700, "#4b5963", "middle"))
    # 선: 흰 후광 → 선
    drawn = [x for x in L.values() if x["pts"]]
    for x in drawn:
        o.append(f'<polyline points="{" ".join(f"{a},{b}" for a, b in x["pts"])}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round" opacity="0.9"/>')
    for x in drawn:
        p = x["pts"]
        arrow = {"fwd": "end", "back": "start", "both": "both"}[x["dir"]]
        for w in ("start", "end"):
            if arrow in (w, "both"):
                p = shorten(p, w, 7 if w == "start" else 1.5)
        dash, wd = STY[x["kind"]]
        col = COL[x["kind"]]
        m = ""
        if arrow in ("end", "both"):
            m += f' marker-end="url(#a-{x["kind"]})"'
        if arrow in ("start", "both"):
            m += f' marker-start="url(#a-{x["kind"]})"'
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in p)}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linejoin="round"{da}{m}/>')
    # 연 쪽 ●
    for x in drawn:
        if x["kind"] in ("once", "human"):
            continue
        sx, sy = x["pts"][0]
        o.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{COL[x["kind"]]}" stroke="#fff" stroke-width="1.5"/>')
    # 사람
    for k, (t, x, y, w, h) in PEOPLE.items():
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="#2b2f33"/>')
        o.append(text(x + w / 2, y + h / 2 + 5, t, 13, 700, "#ffffff", "middle"))
    # 상자
    for k, (no, title, prod, desc, zone, kind, x, y, w, h) in PART.items():
        stroke, dash, fill = "#9aa7ae", "", "#ffffff"
        if kind == "once":
            stroke, dash, fill = "#8f989f", "6 4", "#fbfcfc"
        elif kind == "opt":
            stroke, dash, fill = "#7d8890", "2 3", "#fbfcfc"
        elif kind == "ext":
            stroke, dash, fill = "#5a6fbf", "4 3", "#f7f8fd"
        elif kind == "inst":
            stroke, fill = "#b0739a", "#ffffff"
        if k == "kgmcp":
            fill, dash = "#fbf5f9", "4 3"
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.4"{da}/>')
        small = w <= 260
        ts = 13.5 if small else 15
        o.append(text(x + 12, y + 22, f"{CIRC[no]} {title}", ts, 700))
        if prod:
            o.append(text(x + 12, y + 40, prod, 12 if small else 12.5, 400, "#4b5963"))
        if desc and h >= 80:
            o.append(text(x + 12, y + 58, desc, 12 if small else 12.5, 400, "#1f6f8b"))
    # 구역 제목(선 위에, 흰 테)
    for y0, y1, x1, name, desc, bg, bd, fg in ZONES:
        o.append(f'<text x="24" y="{y0 + 27}" font-size="17" font-weight="700" fill="{fg}" paint-order="stroke" stroke="{bg}" stroke-width="7" stroke-linejoin="round">{esc(name)}<tspan font-size="13" font-weight="400" fill="#4b5963" dx="10">{esc(desc)}</tspan></text>')
    # 선 번호 표
    for x in drawn:
        if not x["lp"]:
            continue
        mx, my = x["lp"]
        t = f"C{x['no']}"
        w = 10 + tw(t, 10.5)
        col = COL[x["kind"]]
        filled = x["kind"] == "cmd"
        o.append(f'<g><rect x="{mx - w / 2:.1f}" y="{my - 9}" width="{w:.1f}" height="18" rx="9" fill="{col if filled else "#ffffff"}" stroke="{col}" stroke-width="1.2"/>'
                 f'<text x="{mx:.1f}" y="{my + 4}" font-size="10.5" font-weight="700" fill="{"#ffffff" if filled else col}" text-anchor="middle" font-family="JetBrains Mono,Consolas,monospace">{t}</text></g>')
    # 그리지 않은 선: 대상 상자 위 작은 표
    tags = {}
    for x in L.values():
        if x["pts"]:
            continue
        bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
        for b in bs:
            tags.setdefault(b, []).append((f"C{x['no']}", x["kind"]))
        tags.setdefault(x["a"], []).append((f"C{x['no']}" + (" 긁음" if x["kind"] == "mon" and x["a"] == "prom" else " 부름"), x["kind"]))
    for k, lst in tags.items():
        if k in PART:
            bx, by, bw = PART[k][6], PART[k][7], PART[k][8]
        else:
            _, bx, by, bw, _ = PEOPLE[k]
        cx = bx + bw - 4
        for t, kind in reversed(lst):
            w = 10 + tw(t, 9.8)
            col = COL[kind]
            o.append(f'<g><rect x="{cx - w:.1f}" y="{by - 9}" width="{w:.1f}" height="16" rx="8" fill="#ffffff" stroke="{col}" stroke-width="1" stroke-dasharray="{"2 2" if kind == "mon" else ""}"/>'
                     f'<text x="{cx - w / 2:.1f}" y="{by + 3}" font-size="9.8" font-weight="700" fill="{col}" text-anchor="middle" font-family="JetBrains Mono,Consolas,monospace">{esc(t)}</text></g>')
            cx -= w + 4
    # 검사 표시
    for k, t, dx, dy in (("gw", "검사 1 · 게이트웨이", 104, 90), ("sim", "검사 2 · PLC", 392, 90)):
        x0, y0 = PART[k][6] + dx, PART[k][7] + dy
        o.append(f'<g><rect x="{x0}" y="{y0 - 13}" width="{12 + tw(t, 11.5):.0f}" height="19" rx="4" fill="#d1343f"/>'
                 f'<text x="{x0 + 6}" y="{y0 + 1}" font-size="11.5" font-weight="700" fill="#ffffff">{esc(t)}</text></g>')
    o.append("</svg>")
    return "\n".join(o)


# ═════════════════════════ 본문 조각 ═════════════════════════
def part_cards():
    out = []
    for k, (no, title, prod, desc, zone, kind, *_r) in PART.items():
        easy, spec, more = D[k]
        rel = [x for x in L.values() if x["a"] == k or x["b"] == k or (isinstance(x["b"], list) and k in x["b"])]
        chips = {"once": "기동 때 1회", "opt": "선택 프로필", "inst": "instance 모드", "ext": "밖"}.get(kind, "")
        spec_html = "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in spec)
        out.append(
            f'<article class="part pz-{zone}" id="p{no}">'
            f'<header><span class="pnum">{CIRC[no]}</span><h3>{title}</h3><span class="zchip zc-{zone}">{ZONE_NAME[zone]}</span>'
            + (f'<span class="kchip">{chips}</span>' if chips else "") + "</header>"
            f'<div class="easy"><span class="lane">쉬운 말</span><p>{sub(easy)}</p></div>'
            f'<div class="tech"><span class="lane">기술 세부</span><dl class="spec">{sub(spec_html)}</dl>{sub(more)}</div>'
            f'<p class="rel">닿는 연결: {" ".join(c(x["key"]) for x in rel) if rel else "없음"}</p></article>')
    return "\n".join(out)


def line_rows(routed):
    out = []
    for k, x in L.items():
        bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
        a = nn(x["a"]) if x["a"] in PART else f'<b>{PEOPLE[x["a"]][0]}</b>'
        to = ", ".join(nn(b) if b in PART else PEOPLE[b][0] for b in bs)
        proto, what = C[k]
        shown = "" if k in routed else '<span class="nodraw">그림: 상자 위 작은 표</span>'
        out.append(f'<li class="cline lk-{x["kind"]}" id="c{x["no"]}"><span class="cnum k-{x["kind"]}">C{x["no"]}</span><div>'
                   f'<p class="ends">● {a} <span class="arrow">→</span> {to}</p>'
                   f'<p class="meta"><span>{KINDW[x["kind"]]}</span><span>데이터: {DIRW[x["dir"]]}</span>{shown}</p>'
                   f'<p class="proto">{sub(proto)}</p><p>{sub(what)}</p></div></li>')
    return "\n".join(out)


def check_master_numbers():
    """마스터_가이드 그림(master_arch_svg.py)의 ①~㉑ 번호와 이름이 이 문서와 같은지 확인한다."""
    src = (HERE / "master_arch_svg.py").read_text(encoding="utf-8")
    pairs = re.findall(r'box\("(\w+)", (\d+),', src)
    mp = {k: int(v) for k, v in pairs if int(v) > 0}
    alias = {"emqx": "emqx", "fuxa": "fuxa", "gw": "gw", "ing": "ing", "det": "det", "rp": "rp", "sink": "sink", "tsdb": "tsdb", "prom": "prom",
             "graf": "graf", "cons": "cons", "neo": "neo", "seed": "seed", "agent": "agent", "llm": "llm", "proc": "proc", "ent": "ent", "portal": "portal",
             "finit": "finit", "tinit": "tinit", "sim": "sim"}
    bad = [(k, v, NO.get(alias.get(k, k))) for k, v in mp.items() if NO.get(alias.get(k, k)) != v]
    assert not bad, f"마스터 가이드와 번호 불일치: {bad}"
    return len(mp)


def build_html(sec_offset=0, out=None):
    nmaster = check_master_numbers()
    s = (HERE / "arch_tpl.html").read_text(encoding="utf-8")
    import arch_fig
    fig, routed, overflow, (fw, fh) = arch_fig.svg(PART, L, COL, CIRC, {k: v[0] for k, v in PEOPLE.items()}, KINDW)
    assert not overflow, "그림 글자 넘침: " + "; ".join(f"{k}: {t}" for k, t in overflow)
    pw = 600                                   # 큰 쪽 너비(mm)
    ph = round(pw * fh / fw + 80)              # 제목 · 설명 자리 포함
    # 기술 레이어 구조도 · 시퀀스 · 리니지 · 속 구조
    import arch_layers as AL, arch_layers_hyd as LH, arch_layers_hyd_text as LT, arch_extra as AX, arch_internal as AI, arch_lineage as ALN
    lsvg, (lw, lh) = AL.svg(LH.LAYERS, LH.CARDS, LH.ARROWS, LH.NCOL)
    said = {int(x) for e, _t in LT.LAYER_TEXT.values() for x in re.findall(r"\{a:(\d+)\}", e)}
    assert said == set(range(1, len(LH.ARROWS) + 1)), f"층별 글에 없는 화살표: {sorted(set(range(1, len(LH.ARROWS) + 1)) - said)} · 없는 번호: {sorted(said - set(range(1, len(LH.ARROWS) + 1)))}"
    assert set(LT.LAYER_TEXT) == {x[0] for x in LH.LAYERS}
    ssvg, (sw, sh) = AL.seq_svg(LT.SEQ_LANES, LT.SEQ_PHASES, LT.SEQ)
    assert len(LT.SEQ_STORY) == len(LT.SEQ_PHASES)
    lpw, spw = 560, 420
    lfig, sfig = round((lpw - 16) * lh / lw), round((spw - 16) * sh / sw)
    assert set(LT.LINEAGE_EASY) == set(ALN.LINEAGE), set(LT.LINEAGE_EASY) ^ set(ALN.LINEAGE)
    assert set(LT.INTERNAL_EASY) == set(AI.INTERNAL), set(LT.INTERNAL_EASY) ^ set(AI.INTERNAL)
    nhop = sum(len(d["hops"]) for d in ALN.LINEAGE.values())
    # 부록(코드에서 직접 뽑은 전체 목록)과 누락 대조: compose 서비스 · 볼륨 · 망 · Kafka 토픽은 기술 레이어 구조도에 실제 이름으로 있어야 한다
    import arch_appendix_hyd as APX
    apx, names = APX.build()
    figtxt = " ".join(" ".join([c["title"], c.get("tech", ""), c.get("box", "")] + c.get("lines", [])) for c in LH.CARDS.values()) + " " + " ".join(a[3] + " " + a[4] for a in LH.ARROWS)
    miss = {k: [x for x in names[k] if x not in figtxt] for k in ("services", "volumes", "networks", "kafka")}
    miss["mqtt"] = [t for t in names["mqtt"] if re.sub(r"/?\{\w+\}", "", "/".join(t.split("/")[2:])) not in figtxt]
    assert not any(miss.values()), f"기술 레이어 구조도에 없는 요소: { {k: v for k, v in miss.items() if v} }"
    rep = {"<!--SVG-->": fig, "<!--SVG_OVERVIEW-->": svg().replace('class="arch"', 'class="arch arch-o"').replace('id="a-', 'id="o-').replace("url(#a-", "url(#o-"), "<!--PARTS-->": part_cards(), "<!--LINES-->": line_rows(routed),
           "<!--LEGEND_L-->": AL.legend_html(), "<!--SVG_LAYERS-->": lsvg, "<!--LAYER_TEXT-->": AL.layer_text_html(LH.LAYERS, LH.CARDS, LH.ARROWS, LT.LAYER_TEXT),
           "<!--ARROW_TABLE-->": AL.table(LH.ARROWS, LH.CARDS, LH.LAYERS), "<!--LAYER_TABLE-->": AL.layer_table_html(LT.LAYER_TABLE),
           "<!--SVG_SEQ-->": ssvg, "<!--SEQ_NOTE-->": esc(LT.SEQ_NOTE), "<!--SEQ_STORY-->": AL.seq_story_html(LT.SEQ_PHASES, LT.SEQ, LT.SEQ_STORY),
           "<!--LINEAGE-->": AX.lineage_html(ALN.LINEAGE, easy=LT.LINEAGE_EASY),
           "<!--CAUTION-->": '<ol class="caution">' + "".join(f"<li>{esc(x)}</li>" for x in ALN.CAUTION) + "</ol>",
           "<!--APPENDIX-->": apx,
           "<!--INTERNAL-->": AX.internal_html(AI.INTERNAL, lambda k: f"{CIRC[NO[k]]} {esc(PART[k][1])}", easy=LT.INTERNAL_EASY),
           "{{NP}}": str(len(PART)), "{{NL}}": str(len(L)), "{{POSTER_W}}": str(pw), "{{POSTER_H}}": str(ph),
           "{{FIG_H}}": str(round(pw * fh / fw) - 4),
           "{{LPOSTER_W}}": str(lpw), "{{LPOSTER_H}}": str(lfig + 78), "{{LFIG_H}}": str(lfig - 2),
           "{{SPOSTER_W}}": str(spw), "{{SPOSTER_H}}": str(sfig + 62), "{{SFIG_H}}": str(sfig - 2),
           "{{NLC}}": str(len(LH.CARDS)), "{{NLA}}": str(len(LH.ARROWS)), "{{NLIN}}": str(len(ALN.LINEAGE)), "{{NHOP}}": str(nhop),
           "{{NCAU}}": str(len(ALN.CAUTION)), "{{NINT}}": str(len(AI.INTERNAL))}
    for k, v in rep.items():
        assert k in s, k
        s = s.replace(k, v)
    # 절 번호: h2 순서대로 매기고 {sec:id} 참조를 그 번호로
    secno = {}

    def num(m):
        secno[m.group(1)] = len(secno) + 1 + sec_offset
        return f"{m.group(0)}{secno[m.group(1)]}. "
    s = re.sub(r'<h2 id="([^"]+)"(?: class="[^"]*")?>', num, s)
    s = re.sub(r"\{sec:(\w+)\}", lambda m: str(secno[m.group(1)]), s)
    s = sub(s)
    left = re.findall(r"\{(?:n|nn|c|a|sec):\w+\}|\{\{\w+\}\}|<!--[A-Z_]+-->", s)
    assert not left, left
    ids = set(re.findall(r'id="([^"]+)"', s))
    miss = sorted({h for h in re.findall(r'href="#([^"]+)"', s)} - ids)
    assert not miss, f"없는 앵커: {miss}"
    s = re.sub(r'(<table class="tbl">\s*)(<tr>(?:(?!</tr>).)*?<th>.*?</tr>)', lambda m: m.group(1) + "<thead>" + m.group(2) + "</thead>", s, flags=re.S)
    if out is None:
        return s
    out.write_text(s, encoding="utf-8")
    print(f"HTML {out.name} {len(s.encode())} bytes · 부품 {len(PART)} · 연결 {len(L)} (그림에 선 {len(routed)}, 작은 표 {len(L) - len(routed)}) · 마스터 번호 대조 {nmaster}개 일치 · 그림 {fw}x{fh:.0f}")


def build_pdf():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle")
        pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(800)
        pg.pdf(path=str(OUT_PDF), prefer_css_page_size=True, print_background=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;color:#8a949b;width:100%;text-align:center;font-family:sans-serif"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        b.close()
    print("PDF", OUT_PDF.name, OUT_PDF.stat().st_size, "bytes")


if __name__ == "__main__":
    import master_build
    master_build.build_html()
    if "--html" not in sys.argv:
        master_build.build_pdf()
