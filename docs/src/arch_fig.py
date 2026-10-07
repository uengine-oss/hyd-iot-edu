# -*- coding: utf-8 -*-
"""시스템_아키텍처 전체 그림(상세판). 상자마다 안쪽 구성(토픽 · 검사 · 표 · 단계 · 도구)을 그림 안에 적는다.
arch_build.py 가 부품 번호 · 연결 정의(PART · L · COL · CIRC)를 넘겨 svg() 를 부른다.
배치: 열(A · S · R · M · X)과 띠(B1~B7). 상자 높이는 안쪽 줄 수로 정하고, 띠 높이는 그 띠의 가장 긴 열로 정한다.
연결 경로는 배치가 끝난 뒤 상자 좌표로 계산한다(ROUTE). ROUTE 에 없는 연결은 상자 위 작은 표로 그린다.
"""
import html, re

# ── 열 ──
COLS = dict(A=(40, 360), S=(470, 700), SL=(470, 340), SR=(830, 340), R=(1230, 380), M=(1660, 330), X=(2050, 300))
W = 2380
LH = 18.5          # 안쪽 줄 간격
HEAD = 60          # 제목 · 제품 줄 · 구분선
GAP = 28           # 같은 열 상자 사이
BAND_TOP = 52      # 띠 제목 아래 첫 상자까지
BAND_BOT = 26
BAND_GAP = 12

# ── 띠 ──
BANDS = [
 ("B1", "L1 · 현장", "설비 3대 + PLC + 수집 장치 (진짜 기계 대신 계산)", "#f3f1ec", "#b9ae98", "#6b604a", True),
 ("B2", "L2 · L6 · OT 공장 망 (ot-net)", "사무실 쪽이 멈춰도 여기는 돈다", "#fcefe2", "#cf8a45", "#9a5a1c", True),
 ("B3", "L3 · DMZ 역할", "두 망(ot-net + it-net)에 동시에 붙은 서비스 2개 · 전용 망 · 방화벽 없음", "#f0ecf8", "#8a76bf", "#5b4691", True),
 ("B4", "L3~L6 · IT 데이터 (it-net)", "장부 · 검사 · 기록 · 화면 · 감시", "#e7f3f6", "#3f8ea3", "#1f6378", True),
 ("B5", "L7 · L8 · 지식과 AI (it-net)", "원인을 찾고 조치를 제안 · 설비에 직접 명령하지 못함", "#ebeffa", "#5a6fbf", "#394b98", False),
 ("B6", "L9 · 업무와 사람 (it-net)", "승인은 사람이 · 회사 시스템 실행", "#f2f4ec", "#7a8a4a", "#56662a", False),
 ("B7", "instance 모드 · 인스턴스와 AI 직원", "cliagents 프로필 + Supabase (compose 기본 구성에는 없음)", "#f6eef3", "#b0739a", "#7d3f66", False),
]

# ── 상자 배치와 안쪽 내용 ──
# key: (띠, 열, 순서, [왼쪽 열 줄], [오른쪽 열 줄] 또는 None)
# 줄 표기: **굵게**  `고정폭`   줄 맨 앞 "  " 는 들여쓰기
BOX = {
 "sim": ("B1", "S", 0, [
   "**열 모델** HYD-01 · 02 · 03 (구조 같음)",
   "  펌프 A + 예비 B · 모터 · 쿨러 + 팬 · 탱크",
   "**태그 19** TS1~4 · PS1~6 · EPS1 · FS1 · FS2",
   "  VS1 · CE · CP · SE(가상 센서)",
   "  FanSpeedSP · LoadSP (설정값)",
   "**정상점** TS1 ≈ 48 ℃ · PS1 182 bar · VS1 0.6",
   "**배속** 현실 1초 = 설비 20초 (1~200)",
   "**강의 API :8000** 고장 주입 · 인증 없음",
   "  쿨러 오염 · 펌프 누설 · 팬 베어링 · restore",
  ], [
   "**PLC 모드** LOCAL · REMOTE_MANUAL · REMOTE_AUTO",
   "**인터록(트립)** TS1 > 65 ℃ · PS1 < 130 bar",
   "  VS1 ≥ 2.0 mm/s · 리셋은 TS1 < 55 ℃에서만",
   "**검사 2** 출처·모드 → 만료 → 중복(최근 32)",
   "  → 범위(팬 0~100 · 부하 60~100)",
   "  → 트립 중이면 Reset만",
   "**사람 우선** 수동 조작 → REMOTE_MANUAL로",
   "**DAQ lite** 6태그 매초 · 보조 30초",
   "  나머지는 값이 변할 때 또는 10초",
   "**ACK** status에 cmdId · DONE/REJECTED · 이유",
  ]),
 "emqx": ("B2", "S", 0, [
   "**↑ 올라가는 칸** (① 설비가 씀)",
   "`plant/{k}/tag/{이름}` QoS 0",
   "`plant/{k}/wave/{센서}` QoS 0 · full만",
   "`plant/{k}/status` QoS 1 · retain · ACK 포함",
   "**{k}** = hyd01 · hyd02 · hyd03",
   "**{센서}** = PS1 · EPS1 · FS1 (파형)",
  ], [
   "**↓ 내려가는 칸** (① 설비가 구독)",
   "`plant/{k}/cmd/auto` QoS 1 ← ④만 씀",
   "`plant/{k}/cmd/manual` · `mode` QoS 1 ← ③",
   "`plant/{k}/alert` QoS 1 · retain ← ④ → ③",
   "**잠금** 계정 · ACL 없음 · 깨끗한 세션",
  ]),
 "fuxa": ("B2", "R", 0, [
   "**태그 54** (설비당 18) · 화면 1장(요소 57)",
   "**알람 6** TS1 높음 60 ℃ · 인터록 65 ℃",
   "  IT 경보 표시등(경보 level 2) × 3대",
   "**조작** 팬 0~100 · 부하 60~100",
   "  정지 해제(Reset) · 모드 선택",
   "**접속** :1881 · 인증 없음",
  ], None),
 "finit": ("B2", "R", 1, ["POST /api/project · 최대 180초 대기 · 5회"], None),
 "gw": ("B3", "SL", 0, [
   "**검사 1** (validate 한 함수)",
   "① 스키마 (source = HITL 등 7필드)",
   "② 허용 목록 7종",
   "  `FAN_SET · LOAD_SET · RESET · STOP`",
   "  `PUMP_SELECT · FAN_BOOST · REDUCE_LOAD`",
   "③ 만료 expiresAt  ④ 중복(최근 256)",
   "⑤ 모드 REMOTE_AUTO + 전체 초당 2건",
   "**통과** → cmd/auto + audit FORWARDED",
   "**거부** → audit REJECTED만",
   "**경보 중계** alerts → alert(retain)",
  ], None),
 "ing": ("B3", "SR", 0, [
   "**구독** tag/+ · wave/+ (QoS 0)",
   "  status (QoS 1)",
   "**쓰기** plant.tag · plant.wave",
   "  plant.status · 키 = 설비",
   "**대기열** 메모리 2만 건",
   "  넘치면 새 값 버림(건수만 셈)",
   "  Kafka 쓰기 실패 1건도 버림",
   "**없는 것** 디스크 버퍼 · 게시판 발행",
   "**접속** :8093 · /healthz 늘 200",
  ], None),
 "rp": ("B4", "S", 0, [
   "**토픽 7** (파티션 1 · 복제 1 · 키 = 설비)",
   "`plant.tag` 1일 · ⑤ → ⑦ ⑧",
   "`plant.wave` 6시간 · ⑤ → ⑦ (full만)",
   "`plant.status` 7일 · ⑤ → ⑦ ⑧ ⑭",
   "`feat.1s` 3일 · ⑦ → ⑧",
  ], [
   "`alerts` 365일 · ⑦ → ④ ⑧ ⑬ ⑭",
   "`action.cmd` 365일 · ⑭ → ④ ⑧",
   "`audit` 5년 · ④ ⑭ → ⑧",
   "**접속** 안 redpanda:9092 · 밖 :19092",
   "**저장** 디스크(볼륨) · 읽어도 안 지움",
  ]),
 "tinit": ("B4", "TI", 1, ["토픽 7개 생성 + 보존 기간 설정"], None),
 "det": ("B4", "A", 0, [
   "**입력** plant.tag · wave · status",
   "**① 기울기** 60설비초 회귀(TS1 · VS1)",
   "**② 이상 점수** z 셋의 RMS ÷ 4 (0~1)",
   "  기준 TS1 48 · CE 84 · VS1 0.6 (고정)",
   "**③ 패턴** ⑫에서 읽음(기동 + 15초마다)",
   "  쿨러 열화 TS1>55 · CE<70 · 오름",
   "  펌프 누설 PS1<165 · FS1<8 · 부하≥80",
   "  팬 진동 VS1>1.2 · 오름",
   "  60설비초 유지 → RAISE · 해제식 → CLEAR",
   "**트립 경보** 과열 · 저압 · 고진동 · PLC",
   "**낡은 값** 보고 주기 + 2초 넘으면 보류",
   "**출력** feat.1s · alerts (outbox 뒤 전송)",
   "**저장** SQLite 체크포인트 · :8092",
  ], None),
 "cons": ("B4", "AN", 1, ["토픽 · 메시지 보기 · 손으로 넣기 · :8085"], None),
 "sink": ("B4", "R", 0, [
   "**옮기기** 토픽 → 표",
   "  plant.tag → tag_1s · feat.1s → feat_1s",
   "  alerts → alerts · action.cmd → actions",
   "  plant.status → actions.ack · audit → audit",
   "**묶음** 최대 2,000건",
   "  행 + Kafka 위치를 한 트랜잭션에",
   "  DB 끊기면 2초마다 재시도 · :8094",
  ], None),
 "tsdb": ("B4", "R", 1, [
   "`tag_1s` 1초 값 · 3일 · 2시간 뒤 압축",
   "`feat_1s` 특징 · 3일",
   "`tag_1m` 1분 평균·최소·최대 · 30일",
   "`alerts` · `actions` · `audit` 영구",
   "**계정** hyd(소유) · grafana(SELECT)",
   "  hyd_timeseries_reader(읽기 전용 5초)",
   "**접속** :5432",
  ], None),
 "prom": ("B4", "M", 0, [
   "대상 6개 /metrics · 10초",
   "규칙 IngestStalled",
   "  · GatewayRejections",
   "Alertmanager 없음 · :9090",
  ], None),
 "graf": ("B4", "M", 1, [
   "대시보드 hyd-trend · 5초 갱신",
   "패널 14: 숫자 6 · 시계열 5 · 표 3",
   "주석 RAISE 빨강 · CLEAR 초록",
   "  · 승인 파랑",
   "익명 Viewer · :3000",
  ], None),
 "seed": ("B5", "A", 0, ["constraints → instances → a098", "detector-patterns는 넣지 않음"], None),
 "neo": ("B5", "A", 1, [
   "**7층 · 46클래스 · 관계 72종**",
   "  가치(BSC) 관점 · 목표 · 지표",
   "  프로세스(BPMN) 흐름 · Task · 분기",
   "  리소스 조직 · 역할 · 설비 · 센서 · 부품",
   "  설비 진단 패턴 · 증상 · 고장 · 원인",
   "  스킬·규칙 SOP · 조치 · DMN 결정·규칙",
   "  외부 변수 · 예측 / 운영 기록",
   "**시드** 패턴 7 · 고장 7 · 원인 8",
   "  SOP 16 · 단계 49 · 규칙 24 · 입력 27",
   "**템플릿** t1 원인 · t2 스킬 · t3 예측",
   "**접속** :7474 · :7687 (Bolt)",
  ], None),
 "agent": ("B5", "AG", 0, [
   "**legacy 자동 순서** (경보 RAISE마다)",
   "1 정책 확인(⑭)",
   "2 신선도: TS1 60초 이내 · ⑤ 생존",
   "3 원인 후보(⑫ t1)",
   "4 증거 SQL(⑨ 읽기 전용) 통과/실패/모름",
   "5 점수 = 사전확률 × 통과 ÷ 전체",
   "6 SOP 스킬(⑫ t2)",
   "7 카드 + 요약(⑰ 선택)",
   "8 가드레일 → 9 제출(⑭) + 카드 순위",
  ], [
   "**가드레일 거부**",
   "  명령 필드(writes · cmdId · topic …)",
   "  근거 누락 · 모름 증거",
   "  범위 밖 값 · 낡은 값",
   "**카드 순위** (LLM 안 씀)",
   "  규칙 선택·제외·감점·경고 · 예측",
   "  BSC 득실 · 선례 · 업무 데이터(⑮)",
   "**LLM** 요약 3문장만 · 8초",
   "  실패하면 정해진 문장",
   "**instance** 자동 정지 → ⑭가 부를 때만",
   "**접속** :8091 · 트레이스는 메모리",
  ]),
 "llm": ("B5", "X", 0, [
   "**⑬에서** 카드 요약 3문장",
   "  OpenAI 호환(기본 gpt-4o-mini)",
   "  또는 Anthropic · 8초 · 600토큰",
   "**㉕에서** Claude Code CLI",
   "  Task 전체 수행 · 1,800초",
   "**키** .env에만",
  ], None),
 "proc": ("B6", "S", 0, [
   "**legacy 사건 흐름**",
   "카드 접수 → 승인 대기 → 명령 발행",
   "→ ACK 대기(30초) → 재관측 → 해결",
   "→ 작업지시(⑮ CMMS) → 종결",
   "실패: 상향 · 운전원 거부 · 조치 없이 해결",
   "**명령** action.cmd · 만료 120초",
   "**재관측** 900설비초 ÷ 배속 · 연장 3번",
   "  회복 TS1<55 · PS1≥165 · VS1<1.2 + CLEAR",
  ], [
   "**승인** 카드 하나 고름(/decide) · /approve 409",
   "**instance** 경보 1건 = 인스턴스 1개",
   "  정의 anomaly_response_v22",
   "  진단 → 후보 → 규정 → 순위(AI)",
   "  → 선택(사람, 10분) → 명령 → 재관측",
   "  → 작업지시 · Task는 ㉒, AI Task는 ㉕",
   "**저장** process.sqlite3 · manuals.sqlite3",
   "**지식 관리** 매뉴얼 원문 · 추출 · 검토 · 적재",
  ]),
 "portal": ("B6", "PO", 1, [
   "메뉴 10: 홈 · 아키텍처 · 결함 시뮬레이션",
   "  이상 확인·조치 · 모니터링 · 지식 지도",
   "  스킬 · 판단 규칙 · 업무 · 인스턴스",
   "nginx는 파일만(:8088) · 브라우저가 직접 호출",
  ], None),
 "ent": ("B6", "R", 0, [
   "**MES** 주문 · 납기 · 잔량 · 대체 설비",
   "**ERP** 계약(위약금 · 등급) · 재고",
   "**CMMS** 세척 주기 · 비용 · 예비 펌프",
   "**QMS** 고온 로트 · 불량 확률 · 클레임",
   "**SCM** 공급사 단가 · 고장률 · 납기",
   "**EMS** 계약 전력 · 수요",
   "**실행** /api/exec 스킬 7 · 되돌리기 4",
   "**원천** memory(SQLite) 또는 ㉒ ent · :8095",
  ], None),
 "dmnmcp": ("B7", "A", 0, [
   "**도구 14**",
   "  diagnose · dmn_rules · inputs",
   "  gather_facts · timeseries_schema",
   "  timeseries_query · prometheus_metadata",
   "  prometheus_series · prometheus_query",
   "  evaluate_cards · forecast_actions",
   "  precedents · tradeoffs",
   "**유일한 쓰기** submit_decision → ⑭",
   "**접속** :8198/mcp",
  ], None),
 "worker": ("B7", "S", 0, [
   "**Task 수행 고리**",
   "1 3초마다 fetch_pending_task('cliagents')",
   "2 작업공간 + .mcp.json(테넌트 MCP)",
   "3 claude --allowedTools (허용 도구만)",
   "4 1,800초 제한 · 30초마다 임대 갱신",
   "5 양식 검사 · 틀리면 2번까지 수정 요청",
   "6 save_task_result · 질문은 사람 대기",
  ], [
   "**허용 도구** Neo4j 스키마·읽기",
   "  enterprise 전부 · hyd-dmn 전부",
   "  Read · Glob · Grep",
   "**실행 위치** 컨테이너(cliagents)",
   "  또는 호스트 run_worker_host.sh",
   "**접속** :8097 /health · /agents",
   "", "", "",
  ]),
 "entmcp": ("B7", "R", 0, [
   "**도구 10** (읽기만)",
   "  mes_orders · erp_contract",
   "  erp_inventory · cmms_history",
   "  qms_lots · scm_suppliers · ems_demand",
   "  describe_schema · describe_catalog",
   "  query (SELECT만 · 200행)",
   "**접속** :8199/mcp · ㉒ ent 읽기 계정",
  ], None),
 "supa": ("B7", "S", 1, [
   "**public** (업무 엔진)",
   "  proc_def · form_def · bpm_proc_inst",
   "  todolist(Task) · events · notifications",
   "  source_inbox · approval_outbox",
   "  effect_receipt · tenants(MCP 목록)",
  ], [
   "**ent** (기업 DB) 14표 + 읽기 함수",
   "**함수** fetch_pending_task(120초 임대)",
   "  · save_task_result",
   "**계정** postgres · hyd_enterprise_reader",
   "**접속** :54321 API · :54322 DB · :54323",
  ]),
}
EXTRA_COLS = dict(TI=(560, 320), AG=(560, 610), PO=(470, 430), AN=(40, 310))
PEOPLE_AT = {"oper": ("R", 0), "staff": ("PO", 1)}   # 옆에 붙일 상자 기준

FONT = 12.5
SMALL = ("finit", "tinit", "seed", "cons")


def tw(t, size=FONT):
    w = 0.0
    mono = False
    for part in re.split(r"(`)", t):
        if part == "`":
            mono = not mono
            continue
        for ch in part.replace("**", ""):
            if ord(ch) > 0x1100 and ch not in "→←↑↓·≥≤≈×①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖℃":
                w += size * 1.0
            elif ch in "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖℃":
                w += size * 1.0
            else:
                w += size * (0.6 if mono else 0.56)
    return w


def esc(t):
    return html.escape(t, quote=True)


def rich(x, y, t, size=FONT, fill="#24313a"):
    """**굵게** · `고정폭` 를 tspan 으로"""
    ind = 0
    if t.startswith("  "):
        ind, t = 12, t[2:]
    out = [f'<text x="{x + ind}" y="{y}" font-size="{size}" fill="{fill}">']
    bold = mono = False
    for tok in re.split(r"(\*\*|`)", t):
        if tok == "**":
            bold = not bold
            continue
        if tok == "`":
            mono = not mono
            continue
        if not tok:
            continue
        a = ""
        if bold:
            a += ' font-weight="700" fill="#14212a"'
        if mono:
            a += ' font-family="JetBrains Mono,Consolas,monospace" font-size="11.6" fill="#1f5f78"'
        out.append(f"<tspan{a}>{esc(tok)}</tspan>")
    out.append("</text>")
    return "".join(out)


class Box:
    def __init__(s, x, y, w, h):
        s.x, s.y, s.w, s.h = x, y, w, h

    @property
    def r(s): return s.x + s.w

    @property
    def b(s): return s.y + s.h

    @property
    def cx(s): return s.x + s.w / 2

    @property
    def cy(s): return s.y + s.h / 2


def layout(PART):
    """띠마다 (열 묶음, 순서)로 쌓는다. S · SL · SR · TI · AG · PO 는 한 묶음(가운데 척추)이라 순서가 같으면 같은 높이에서 시작한다."""
    cols = dict(COLS, **EXTRA_COLS)
    hbox = {}
    for k, (band, col, order, left, right) in BOX.items():
        n = max(len(left), len(right) if right else 0)
        hbox[k] = (34 + n * LH + 10) if k in SMALL else (HEAD + n * LH + 12)
    B, bands = {}, {}
    y = 10
    for bid, *_ in BANDS:
        top = y
        fam_y = {}
        items = sorted((v[2], k) for k, v in BOX.items() if v[0] == bid)
        groups = {}
        for order, k in items:
            col = BOX[k][1]
            fam = "S" if col in ("S", "SL", "SR", "TI", "AG", "PO") else ("A" if col == "AN" else col)
            groups.setdefault((fam, order), []).append(k)
        for (fam, order), ks in sorted(groups.items(), key=lambda kv: kv[0][1]):
            yy = fam_y.get(fam, top + BAND_TOP)
            for k in ks:
                x, w = cols[BOX[k][1]]
                B[k] = Box(x, yy, w, hbox[k])
            fam_y[fam] = max(B[k].b for k in ks) + GAP
        bottom = max(B[k].b for _o, k in items)
        bands[bid] = (top, bottom + BAND_BOT)
        y = bottom + BAND_BOT + BAND_GAP
    return B, bands, y


def svg(PART, L, COL, CIRC, PEOPLE_NAMES, KIND_OF):
    B, bands, H = layout(PART)
    # 띠 사이 보정: B4 의 tinit 이 rp 아래, B5 의 agent 가 seed 와 같은 높이에서 시작
    # 사람 알약
    P = {}
    f = B["fuxa"]
    P["oper"] = Box(1690, f.y + 24, 180, 36)
    po = B["portal"]
    P["staff"] = Box(po.r + 50, po.y + 30, 180, 36)
    # 수동 위치 조정: kg MCP 는 worker 안쪽 오른쪽 아래
    wk = B["worker"]
    KG = Box(wk.x + 360, wk.b - 66, 320, 52)

    g = lambda k: B[k] if k in B else (P[k] if k in P else KG)
    ROUTE, LP = {}, {}

    def gap(b1, b2):   # 두 띠 사이 가운데 y
        return (bands[b1][1] + bands[b2][0]) / 2

    sim, emqx, fuxa, finit, gw, ing, rp, det, sink, tsdb, graf, prom, cons, tinit = (B[k] for k in
        ("sim", "emqx", "fuxa", "finit", "gw", "ing", "rp", "det", "sink", "tsdb", "graf", "prom", "cons", "tinit"))
    seed, neo, agent, llm, proc, portal, ent, dmn, supa, entmcp = (B[k] for k in
        ("seed", "neo", "agent", "llm", "proc", "portal", "ent", "dmnmcp", "supa", "entmcp"))
    ROUTE["c_sim_pub"] = [(1000, sim.b), (1000, emqx.y)]
    ROUTE["c_sim_sub"] = [(520, sim.b), (520, emqx.y)]
    ROUTE["c_fuxa"] = [(fuxa.x, emqx.y + 40), (emqx.r, emqx.y + 40)]
    ROUTE["c_oper"] = [(P["oper"].x, P["oper"].cy), (fuxa.r, P["oper"].cy)]
    ROUTE["c_finit"] = [(fuxa.cx, finit.y), (fuxa.cx, fuxa.b)]
    ROUTE["c_ing_sub"] = [(1000, ing.y), (1000, emqx.b)]
    ROUTE["c_ing_pub"] = [(1000, ing.b), (1000, rp.y)]
    ROUTE["c_det"] = [(det.r, rp.y + 40), (rp.x, rp.y + 40)]
    ROUTE["c_det_neo"] = [(380, det.b), (380, neo.y)]
    ROUTE["c_sink_sub"] = [(sink.x, sink.y + 40), (rp.r, sink.y + 40)]
    ROUTE["c_sink_db"] = [(sink.cx, sink.b), (sink.cx, tsdb.y)]
    yg = max(tsdb.y, graf.y) + 30
    assert yg < min(tsdb.b, graf.b) - 10
    ROUTE["c_graf"] = [(graf.x, yg), (tsdb.r, yg)]
    ROUTE["c_gw_cmd"] = [(520, gw.b), (520, rp.y)]
    ROUTE["c_gw_alert"] = [(620, gw.b), (620, rp.y)]
    ROUTE["c_gw_auto"] = [(520, gw.y), (520, emqx.b)]
    ROUTE["c_gw_disp"] = [(620, gw.y), (620, emqx.b)]
    ROUTE["c_gw_stat"] = [(740, gw.y), (740, emqx.b)]
    ROUTE["c_ag_alert"] = [(1140, agent.y), (1140, rp.b)]
    ya = max(neo.y, agent.y) + 30
    assert ya < min(neo.b, agent.b) - 10
    ROUTE["c_ag_neo"] = [(agent.x, ya), (neo.r, ya)]
    ROUTE["c_ag_tsdb"] = [(agent.r, agent.y + 30), (1265, agent.y + 30), (1265, tsdb.b)]
    ROUTE["c_ag_llm"] = [(agent.r, agent.y + 90), (llm.x, agent.y + 90)]
    g56 = gap("B5", "B6")
    ROUTE["c_ag_ent"] = [(1110, agent.b), (1110, g56 - 10), (1300, g56 - 10), (1300, ent.y)]
    ROUTE["c_ag_proc"] = [(700, agent.b), (700, proc.y)]
    ROUTE["c_proc_rp"] = [(500, proc.y), (500, rp.b)]
    ROUTE["c_proc_tsdb"] = [(1150, proc.y), (1150, g56 + 8), (1345, g56 + 8), (1345, tsdb.b)]
    ROUTE["c_proc_neo"] = [(proc.x, proc.y + 40), (230, proc.y + 40), (230, neo.b)]
    ROUTE["c_proc_ent"] = [(proc.r, proc.y + 60), (ent.x, proc.y + 60)]
    ROUTE["c_proc_ag"] = [(860, proc.y), (860, agent.b)]
    ROUTE["c_proc_supa"] = [(proc.x, proc.b - 20), (450, proc.b - 20), (450, supa.cy), (supa.x, supa.cy)]
    ROUTE["c_staff"] = [(P["staff"].x, P["staff"].cy), (portal.r, P["staff"].cy)]
    ROUTE["c_cons"] = [(cons.r, cons.cy), (445, cons.cy), (445, rp.b - 24), (rp.x, rp.b - 24)]
    ROUTE["c_tinit"] = [(tinit.cx, tinit.y), (tinit.cx, rp.b)]
    ROUTE["c_seed"] = [(190, seed.b), (190, neo.y)]
    ROUTE["c_ent_supa"] = [(ent.r, ent.y + 60), (1640, ent.y + 60), (1640, supa.b - 22), (supa.r, supa.b - 22)]
    ROUTE["c_wk_supa"] = [(700, wk.b), (700, supa.y)]
    g67 = gap("B6", "B7")
    ROUTE["c_wk_llm"] = [(wk.r, wk.y + 26), (1195, wk.y + 26), (1195, g67), (2240, g67), (2240, llm.b)]
    ROUTE["c_wk_dmn"] = [(wk.x, wk.y + 40), (dmn.r, wk.y + 40)]
    ROUTE["c_wk_ent"] = [(wk.r, entmcp.y + 50), (entmcp.x, entmcp.y + 50)]
    ROUTE["c_entmcp_supa"] = [(entmcp.cx, entmcp.b), (entmcp.cx, supa.y + 40), (supa.r, supa.y + 40)]
    assert entmcp.b < supa.y + 40 - 10, "entmcp 가 supa 보다 위에 있어야"
    LP.update({"c_ag_neo": 0.72, "c_proc_supa": 0.25, "c_det_neo": 0.5, "c_proc_rp": 0.42, "c_ag_alert": 0.5, "c_wk_llm": 3, "c_proc_tsdb": 3, "c_ag_tsdb": 2, "c_ent_supa": 2})

    # ── 그리기 ──
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="hyd-iot-edu 전체 아키텍처 상세: 부품 26개의 안쪽 구성과 연결 46개" class="arch">', "<defs>"]
    for k, col in COL.items():
        o.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H:.0f}" fill="#ffffff"/>')
    xext = COLS["X"][0] - 22
    for bid, name, desc, bg, bd, fg, full in BANDS:
        y0, y1 = bands[bid]
        x1 = W - 8 if full else xext - 10
        o.append(f'<rect x="8" y="{y0}" width="{x1 - 8}" height="{y1 - y0}" rx="14" fill="{bg}" stroke="{bd}" stroke-width="1.4"/>')
    y5 = bands["B5"][0]
    o.append(f'<rect x="{xext}" y="{y5}" width="{W - 8 - xext}" height="{bands["B7"][1] - y5}" rx="14" fill="#f4f5f6" stroke="#9aa3aa" stroke-width="1.4" stroke-dasharray="6 4"/>')
    o.append(f'<text x="{(xext + W - 8) / 2}" y="{y5 + 30}" font-size="17" font-weight="700" fill="#4b5963" text-anchor="middle">밖 (인터넷)</text>')

    def shorten(p, which, d):
        p = list(p)
        (x0, y0), (x1, y1) = (p[-2], p[-1]) if which == "end" else (p[1], p[0])
        ln = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
        nx, ny = x1 - (x1 - x0) / ln * d, y1 - (y1 - y0) / ln * d
        if which == "end":
            p[-1] = (nx, ny)
        else:
            p[0] = (nx, ny)
        return p

    STY = dict(data=("", 2.4), cmd=("", 3.2), alert=("7 4", 2.4), api=("", 1.8), mon=("2 4", 1.6), once=("9 5", 1.6), human=("", 1.8))
    drawn = [x for x in L.values() if x["key"] in ROUTE]
    for x in drawn:
        o.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in ROUTE[x["key"]])}" fill="none" stroke="#ffffff" stroke-width="8" stroke-linejoin="round" opacity="0.9"/>')
    for x in drawn:
        p = ROUTE[x["key"]]
        arrow = {"fwd": "end", "back": "start", "both": "both"}[x["dir"]]
        for wch in ("start", "end"):
            if arrow in (wch, "both"):
                p = shorten(p, wch, 7 if wch == "start" else 1.5)
        dash, wd = STY[x["kind"]]
        m = (f' marker-end="url(#a-{x["kind"]})"' if arrow in ("end", "both") else "") + (f' marker-start="url(#a-{x["kind"]})"' if arrow in ("start", "both") else "")
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in p)}" fill="none" stroke="{COL[x["kind"]]}" stroke-width="{wd}" stroke-linejoin="round"{da}{m}/>')
    for x in drawn:
        if x["kind"] in ("once", "human"):
            continue
        sx, sy = ROUTE[x["key"]][0]
        o.append(f'<circle cx="{sx}" cy="{sy}" r="5.2" fill="{COL[x["kind"]]}" stroke="#fff" stroke-width="1.5"/>')
    # 사람
    for k, bx in P.items():
        o.append(f'<rect x="{bx.x}" y="{bx.y}" width="{bx.w}" height="{bx.h}" rx="{bx.h / 2}" fill="#2b2f33"/>')
        o.append(f'<text x="{bx.cx}" y="{bx.cy + 5}" font-size="14" font-weight="700" fill="#ffffff" text-anchor="middle">{esc(PEOPLE_NAMES[k])}</text>')
    # 상자
    overflow = []
    for k, (band, col, order, left, right) in BOX.items():
        bx = B[k]
        no, title, prod, _d, zone, kind = PART[k][:6]
        stroke, dash, fill = "#9aa7ae", "", "#ffffff"
        if kind == "once":
            stroke, dash, fill = "#8f989f", "6 4", "#fbfcfc"
        elif kind == "opt":
            stroke, dash, fill = "#7d8890", "2 3", "#fbfcfc"
        elif kind == "ext":
            stroke, dash, fill = "#5a6fbf", "4 3", "#f7f8fd"
        elif kind == "inst":
            stroke = "#b0739a"
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<rect x="{bx.x}" y="{bx.y}" width="{bx.w}" height="{bx.h:.0f}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{da}/>')
        small = k in SMALL
        o.append(f'<text x="{bx.x + 14}" y="{bx.y + 24}" font-size="{15 if small else 17}" font-weight="800" fill="#14212a">{esc(CIRC[no] + " " + title)}</text>')
        if small:
            o.append(f'<text x="{bx.r - 12}" y="{bx.y + 24}" font-size="11.5" fill="#6b7780" text-anchor="end">{esc(prod)}</text>')
            for i, t in enumerate(left):
                o.append(rich(bx.x + 14, bx.y + 30 + (i + 1) * LH, t, 12, "#4b5963"))
                if tw(t, 12) > bx.w - 28:
                    overflow.append((k, t))
            if tw(CIRC[no] + " " + title, 15) + tw(prod, 11.5) > bx.w - 36:
                overflow.append((k, "제목+제품 겹침"))
            continue
        o.append(f'<text x="{bx.x + 14}" y="{bx.y + 43}" font-size="12.5" fill="#4b5963">{esc(prod)}</text>')
        o.append(f'<line x1="{bx.x + 10}" y1="{bx.y + 52}" x2="{bx.r - 10}" y2="{bx.y + 52}" stroke="#e1e6e9" stroke-width="1"/>')
        colw = bx.w if not right else (bx.w - 20) / 2
        for ci, lst in enumerate([left] + ([right] if right else [])):
            x0 = bx.x + 14 + ci * (colw + 10)
            for i, t in enumerate(lst):
                if not t:
                    continue
                o.append(rich(x0, bx.y + HEAD + 8 + i * LH, t))
                if tw(t) + (12 if t.startswith("  ") else 0) > colw - 22:
                    overflow.append((k, t))
        if right:
            xm = bx.x + 14 + colw + 2
            o.append(f'<line x1="{xm}" y1="{bx.y + 62}" x2="{xm}" y2="{bx.b - 10}" stroke="#eef1f3" stroke-width="1"/>')
    # kg MCP (worker 안)
    o.append(f'<rect x="{KG.x}" y="{KG.y}" width="{KG.w}" height="{KG.h}" rx="8" fill="#fbf5f9" stroke="#b0739a" stroke-width="1.3" stroke-dasharray="4 3"/>')
    o.append(f'<text x="{KG.x + 12}" y="{KG.y + 21}" font-size="14" font-weight="800" fill="#14212a">{esc(CIRC[26] + " " + PART["kgmcp"][1])}</text>')
    o.append(rich(KG.x + 12, KG.y + 40, "uvx mcp-neo4j-cypher · stdio · READ_ONLY", 11.8, "#4b5963"))
    # 띠 제목(선 위, 흰 테)
    for bid, name, desc, bg, bd, fg, full in BANDS:
        y0 = bands[bid][0]
        o.append(f'<text x="24" y="{y0 + 30}" font-size="19" font-weight="800" fill="{fg}" paint-order="stroke" stroke="{bg}" stroke-width="8" stroke-linejoin="round">{esc(name)}<tspan font-size="14" font-weight="400" fill="#4b5963" dx="12">{esc(desc)}</tspan></text>')
    # 검사 표시
    for k, t in (("gw", "검사 1"), ("sim", "검사 2 · PLC")):
        bx = B[k]
        w = 16 + tw(t, 12)
        o.append(f'<g><rect x="{bx.r - w - 10:.1f}" y="{bx.y + 9}" width="{w:.1f}" height="21" rx="5" fill="#d1343f"/><text x="{bx.r - w / 2 - 10:.1f}" y="{bx.y + 24}" font-size="12" font-weight="700" fill="#ffffff" text-anchor="middle">{esc(t)}</text></g>')
    # 선 번호 표
    for x in drawn:
        p = ROUTE[x["key"]]
        segs = list(zip(p, p[1:]))
        sel = LP.get(x["key"])
        if isinstance(sel, int):
            (ax, ay), (bx_, by_) = segs[sel - 1]
            mx, my = (ax + bx_) / 2, (ay + by_) / 2
        else:
            s = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            t = sel if isinstance(sel, float) else 0.5
            mx, my = s[0][0] + (s[1][0] - s[0][0]) * t, s[0][1] + (s[1][1] - s[0][1]) * t
        lab = f"C{x['no']}"
        w = 12 + tw(lab, 11)
        col = COL[x["kind"]]
        filled = x["kind"] == "cmd"
        o.append(f'<g><rect x="{mx - w / 2:.1f}" y="{my - 10:.1f}" width="{w:.1f}" height="20" rx="10" fill="{col if filled else "#ffffff"}" stroke="{col}" stroke-width="1.3"/>'
                 f'<text x="{mx:.1f}" y="{my + 4.5:.1f}" font-size="11" font-weight="700" fill="{"#ffffff" if filled else col}" text-anchor="middle" font-family="JetBrains Mono,Consolas,monospace">{lab}</text></g>')
    # 그리지 않은 연결: 상자 위 작은 표
    tags = {}
    for x in L.values():
        if x["key"] in ROUTE:
            continue
        bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
        for b in bs:
            tags.setdefault(b, []).append((f"C{x['no']}", x["kind"]))
        tags.setdefault(x["a"], []).append((f"C{x['no']} " + ("긁음" if x["kind"] == "mon" and x["a"] == "prom" else "부름"), x["kind"]))
    for k, lst in tags.items():
        bx = g(k)
        cx = bx.r - 6
        for t, kind in reversed(lst):
            w = 12 + tw(t, 10.5)
            col = COL[kind]
            o.append(f'<g><rect x="{cx - w:.1f}" y="{bx.y - 10}" width="{w:.1f}" height="18" rx="9" fill="#ffffff" stroke="{col}" stroke-width="1.1"{" stroke-dasharray=\"2 2\"" if kind == "mon" else ""}/>'
                     f'<text x="{cx - w / 2:.1f}" y="{bx.y + 3.5}" font-size="10.5" font-weight="700" fill="{col}" text-anchor="middle">{esc(t)}</text></g>')
            cx -= w + 4
    o.append("</svg>")
    return "\n".join(o), set(ROUTE), overflow, (W, H)
