# -*- coding: utf-8 -*-
"""기능 보고서 생성기 — "기존에는 이랬고, 현재는 이렇다" (2026-10-07).

    .venv314/Scripts/python docs/보고서/build_feature_report.py

입력: 포털 캡처 `.evidence/reaudit/a109-report-ui/*.png`(10-07 18:30 실제 화면), 거래 원장 `ledger.json`.
출력: `docs/보고서/2026-10-07_HYD_기능보고.html`(그림 내장, 화면 공유용) + 같은 내용의 `.md`(편집용).
절마다 같은 틀: 번호·제목 → 한 줄 요약 → 실제 화면 → 표(기존/현재/달라진 점/확인 방법) → 화면을 공유하며 그대로 읽을 설명.
수치는 본문 끝 "수치 출처" 표에 적힌 증거 파일에서만 가져왔다. 캡처가 없는 절은 표와 설명만 둔다.
"""
import base64
import html
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / ".evidence/reaudit/a109-report-ui"
OUT = ROOT / "docs/보고서"
TITLE = "HYD 유압설비 AI 운영 시스템 — 기능 보고서: 기존에는 이랬고, 현재는 이렇다"
DATE = "2026-10-07"


def img(name, caption):
    p = CAP / name
    if not p.exists():
        return None
    data = base64.b64encode(p.read_bytes()).decode()
    return {"src": f"data:image/png;base64,{data}", "caption": caption, "file": name}


def ledger_rows():
    p = CAP / "ledger.json"
    if not p.exists():
        return []
    rows = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for t in sorted(rows, key=lambda r: r.get("t") or ""):
        b, a = t.get("before") or {}, t.get("after") or {}
        out.append([t.get("skill", ""), t.get("ref", ""), t.get("by", ""), b.get("status", "—") if b else "— (새 행)",
                    a.get("status", "—"), "있음" if a.get("cancelled_at") else "—", t.get("compensates") or "—"])
    return out


SECTIONS = [
    {
        "no": 1, "title": "사건 한 건의 흐름 — 고정 파이프라인에서 프로세스 인스턴스로",
        "old": "감지→에이전트→카드→승인이 코드에 고정된 한 경로. 사건 단위 기록 없음, 승인 시간초과 없음",
        "new": "경보 1건 = BPMN 정의로 시작되는 프로세스 인스턴스 1건. 작업마다 맡는 쪽·타이머·세대·종료 이벤트가 DB 행으로 남음",
        "summary": "경보 1건이 정의된 업무 프로세스의 인스턴스 1건이 되고, 작업(task)마다 맡는 쪽(에이전트·규칙·사람·설비)이 정해져 끝까지 추적된다.",
        "images": [("process-1440.png", "업무 프로세스 탭 — 등록된 BPMN 정의(설비·탐지 → 에이전트 → 사람 → 프로세스 → 기업 시스템 → 온톨로지 층)"),
                   ("instances-1440.png", "프로세스 인스턴스 탭 — 실시간 에이전트 스트림과 내 할일(todolist)"),
                   ("instance-detail-1440.png", "오늘(10-07 17:12) 실제로 돈 사례 — 작업 흐름·현재 세대 1·승인 전달 상태·기존 조치의 효과 검토")],
        "table": [
            ["기존", "감지 → 에이전트 → 카드 → 승인이 코드에 고정된 한 경로(agent main.py 파이프라인 + process machine.py 상태기계). 사건 단위 기록이 없어 중간에 끊기면 흔적이 남지 않음. 승인 시간초과·자율 실행 미구현(10-03 커밋 메시지의 알려진 한계)."],
            ["현재", "BPMN 정의 등록(판본 고정, 조건 변수·정적 연결성 검사) → 경보가 시작 이벤트(ev:alert)로 인스턴스를 염 → 작업 행: 원인 진단·조치 후보·규정 검토·우선순위(에이전트) / 조치 카드 선택(사람, 10분 경계 타이머 → 상급자) / PLC 명령·재관측·정비 작업지시(프로세스) → 종료 이벤트(ev:closed / ev:escalated). 재작업은 세대(generation)로 이어지고 병렬 분기·합류도 지원."],
            ["달라진 점", "\"무슨 사건이 어느 단계에서 누구 손에 있는가\"가 DB 행(todolist)으로 남고 포털에 그대로 보인다. 서비스가 재시작돼도 사건은 사라지지 않는다."],
            ["확인 방법", "포털 프로세스 인스턴스 탭 / GET /api/instances/{id}(workitems·variables·end_event) / 회귀 효과보상 22/22·병렬 합류 7/7"],
        ],
        "case": {"title": "사례: 인스턴스 anomaly_response.874130b0… (HYD-01 쿨러 성능 저하, 20배속, 2분 만에 완료)", "head": ["세대", "작업", "맡는 쪽", "결과", "걸린 시간"], "rows": [
            ["0", "원인 진단 → 조치 후보 조회 → 규정 검토 → 우선순위·카드 작성", "에이전트(cliagents)", "DONE", "17초"],
            ["0", "조치 카드 선택 (HITL)", "사람(운전원 → 10분 타이머)", "DONE(승인)", "6초"],
            ["0", "PLC 명령 발행 → 재관측(15분)", "프로세스·설비", "명령 ACK, 재관측은 재작업으로 취소", "8초"],
            ["1", "우선순위·카드 작성 → 카드 선택 → PLC 명령 → 재관측(15분) → 정비 작업지시", "에이전트 → 사람 → 프로세스 → CMMS", "DONE, 종료 ev:closed", "1분 26초"],
        ]},
        "narration": [
            "예전에는 경보가 오면 정해진 코드가 카드 하나를 만들고 거기서 끝이었습니다. 지금은 경보 하나가 '사건'이 되어, 그림에 보이는 업무 흐름을 그대로 탑니다.",
            "각 칸이 하나의 작업이고, 누가 맡는지가 정해져 있습니다. 초록은 에이전트, 가운데는 사람, 아래는 프로세스와 기업 시스템입니다. 사람이 10분 안에 카드를 고르지 않으면 타이머가 상급자에게 넘깁니다.",
            "세 번째 화면은 오늘 오후 실제로 돈 사건입니다. 1세대에서 팬 명령을 내리고, 그 효과를 검토한 뒤 2세대로 다시 판단해서 작업지시까지 닫혔습니다. 2분 만에 끝난 건 시뮬레이션이 20배속이기 때문입니다.",
        ],
    },
    {
        "no": 2, "title": "에이전트 작업 — 템플릿 카드에서 실제로 질의하는 에이전트로",
        "old": "고정 카드·템플릿 요약. 데이터 조회·근거 인용 없음",
        "new": "워커(Claude Code·Codex)가 작업을 임대로 집어 가 MCP로 규칙·업무 DB·시계열·PromQL·온톨로지를 실제 조회하고 근거를 붙임. 취소·회수 가능",
        "summary": "에이전트(Claude Code·Codex 워커)가 작업을 집어 가서 MCP로 시계열 SQL·PromQL·Neo4j Cypher·기업 DB를 실제로 조회하고, 그 근거를 카드에 붙인다.",
        "images": [("skills-1440.png", "에이전트 스킬 탭 — 스킬 하나가 SOP 하나(승인 역할·단계·원문 인용 HM-x.x)"),
                   ("decision-1440.png", "조치 판단 규칙 탭 — 같은 이상이라도 운전 모드·팬 누적 시간·예비 펌프 상태에 따라 카드가 달라진다")],
        "table": [
            ["기존", "고정 카드·템플릿 요약. 데이터 조회 없음, 근거 인용 없음. 순위에 납기·품질 미반영."],
            ["현재", "워커가 todolist를 임대(lease, 120초·3회 상한)로 claim → 활동이 선언한 MCP 서버만 연결(작업별 선택) → 질의: 규칙(DMN) · 업무 데이터(ERP/MES/CMMS/QMS/SCM/EMS) · 시계열 SQL · PromQL · 온톨로지 Cypher → 근거·인용을 붙인 카드 제출. 자식 프로세스에 비밀 미전달, 실행 중 취소 API, 데이터 신선도 검사(60초, 시계 오차 2초 허용) 뒤에만 추론."],
            ["달라진 점", "답에 '어느 표·어느 메트릭·어느 규칙'이 붙는다. 워커가 둘이면 서로 다른 작업을 나눠 가져가고, 하나가 죽으면 다른 워커가 이어받는다."],
            ["확인 방법", "GET /api/agent/runs/{id} 단계(alert_policy → freshness → t1_causes → evidence → rank → t2_skills → card → guardrail) / 워커 /health(8097·8098) / 실측: 규칙 질문 15/15, 업무 질문 3/3, 시계열·PromQL 3/3, 전문가 질문 8/8, 임대 회수 6/6, 실행 중 취소 8/8"],
        ],
        "case": {"title": "에이전트가 실제로 하는 조회(사례 기준)", "head": ["단계", "무엇을 어디에 묻나", "결과가 쓰이는 곳"], "rows": [
            ["freshness", "TimescaleDB 최신 TS1 행의 나이 + 수집기 상태", "오래된 데이터면 추론 보류"],
            ["t1_causes · evidence", "Neo4j 온톨로지: 이상 패턴 → 고장 유형 → 원인·증상·증거 구간", "원인 순위"],
            ["t2_skills · rank", "DMN 규칙 + BSC 상충 계산(AFFECTS → INFLUENCES 부호 곱) + 예측 + 선례", "조치 카드 순위"],
            ["업무 사실", "enterprise-mcp(읽기 전용): 납기·계약·재고·공급사·에너지", "순위 역전·대안"],
            ["guardrail · card", "승인 역할·즉시 제어 가능 여부·원문 인용 검사", "사람에게 가는 카드"],
        ]},
        "narration": [
            "에이전트가 '추측'이 아니라 '조회'를 합니다. 이 스킬 화면의 단계마다 매뉴얼 원문 번호가 붙어 있고, 판단 규칙 화면에서는 같은 이상이라도 운전 모드나 팬 누적 시간에 따라 카드가 달라지는 걸 직접 돌려 볼 수 있습니다.",
            "워커는 작업을 '빌려' 갑니다. 120초 안에 갱신하지 않으면 다른 워커가 가져가고, 세 번 실패하면 사람에게 넘어갑니다. 실행 중인 작업은 화면에서 취소할 수 있습니다.",
        ],
    },
    {
        "no": 3, "title": "사람의 승인·제어·복구 — 버튼 하나에서 책임 있는 선택으로",
        "old": "승인 버튼 1개. 거부·권한·되돌림 없음, 종결 시 작업지시 미발행",
        "new": "카드 선택(역할·사유)·시간초과 에스컬레이션·PLC ACK·효과 검토 뒤 재작업 세대·CMMS 작업지시 종결·재시작 복구",
        "summary": "사람은 카드를 고르고(HITL), 역할이 맞아야 하며, 되돌릴 수 없는 효과는 검토해야 재작업이 열린다. 서비스가 재시작돼도 사건은 사람 검토로 넘어간다.",
        "images": [("incidents-1440.png", "이상 확인·조치 탭 — 설비별 상태와 인시던트 목록(종결 / 추가 확인 필요)"),
                   ("scenario-1440.png", "결함 시뮬레이션 탭 — 결함 주입과 센서값·운전 상태 변화(시간 배율 20)")],
        "table": [
            ["기존", "승인 버튼 1개. 거부·권한·되돌림 없음. 트립 리셋 카드 거부·종결 시 CMMS 작업지시 미발행."],
            ["현재", "카드 선택(옵션·사유·검토 영수증) → 승인 역할 미만이면 403 → 선택 시간초과는 상급자로 → PLC 명령은 게이트웨이 검증 뒤 ACK → 재관측 → 효과 목록(되돌릴 수 없는 명령은 '검토 필요') → 검토 뒤 재작업 세대 1(옛 승인 폐기·옛 판단 거부) → CMMS 작업지시로 종결. 프로세스가 재시작되면 진행 중 사건은 '재시작 검토'로 사람에게."],
            ["달라진 점", "사람의 결정이 누가·무슨 역할로·왜 골랐는지 기록되고, 되돌릴 수 없는 효과는 숨기지 않고 검토를 요구한다."],
            ["확인 방법", "회귀 효과보상 22/22(아래 항목이 그대로 시나리오) / 작업지시 전용 카드 19/19"],
        ],
        "case": {"title": "효과보상 회귀 22항목 중 핵심(10-07 17:12 실제 실행)", "head": ["확인한 것", "결과"], "rows": [
            ["첫 승인 접수 → PLC ACK → 재관측", "통과 (CMD-1007-0001)"],
            ["효과 목록에 PLC 명령이 '되돌릴 수 없음·검토 대기'로 뜸", "통과"],
            ["효과 검토 전 재작업 차단 / 승인 역할 미만 검토 403 / 되돌릴 것 없을 때 409", "통과"],
            ["검토 뒤 재작업 허용 → 사건 재개, 옛 명령 대체, 옛 승인 폐기", "통과 (세대 1)"],
            ["새 세대에서 실제 DMN 판단 새로 → 옛 판단 거부 → 두 번째 명령 ACK", "통과 (DEC-1007-026, CMD-1007-0002)"],
            ["실제 CMMS 작업지시로 종결, 그래프 투영 = DB 행", "통과 (WO-1007-6123, ev:closed)"],
            ["기업 원장에서 작업지시 정확 취소·멱등·두 번째 취소 거부", "통과"],
        ]},
        "narration": [
            "승인은 끝이 아니라 시작입니다. 명령을 내렸으면 그 효과가 남고, 다시 하려면 그 효과를 사람이 확인해야 합니다. 역할이 안 맞으면 시스템이 거절합니다.",
            "표의 항목은 제가 쓴 시나리오가 아니라 오늘 오후 실제로 돌린 검사 항목 이름입니다. 22개가 전부 통과했습니다.",
        ],
    },
    {
        "no": 4, "title": "기업 시스템 연계 — 목업 JSON에서 실제 DB와 거래 원장으로",
        "old": "기업 시스템은 고정 딕셔너리 목업. 실행 흔적 없음",
        "new": "Supabase 실제 테이블·멱등 실행·정확 역전, 거래 원장에 변경 전·후 행, SCM 동기화·DDL 드리프트 반영",
        "summary": "ERP·MES·CMMS·QMS·SCM·EMS가 Supabase 실제 테이블이고, 스킬 실행은 거래 원장에 변경 전·후 행과 함께 남는다. DDL이 바뀌면 지식 그래프의 메타데이터가 따라간다.",
        "images": [("home-1440.png", "시스템 아키텍처 탭 — L1 현장 설비부터 L9 승인·실행까지 층별 구성요소")],
        "table": [
            ["기존", "기업 시스템은 고정 딕셔너리 목업(data.py). 실행 흔적 없음."],
            ["현재", "ent.* 테이블 + exec_skill / exec_compensation(멱등·정확 역전·상태 검사) + 거래 원장의 before/after(jsonb). 읽기 전용 MCP(enterprise-mcp·dmn-mcp)로 에이전트가 조회. SCM 공급사 변경 동기화, DDL 드리프트 감지·그래프 반영."],
            ["달라진 점", "'무엇을 어떤 값에서 어떤 값으로 바꿨나'가 감사 가능하고, 취소는 정확히 그 행만 되돌린다."],
            ["확인 방법", "GET 8095 /api/transactions(before/after 열) / 회귀 SCM 동기화 6/6·DDL 드리프트 5/5"],
        ],
        "ledger": True,
        "narration": [
            "작업지시를 만들면 CMMS에 행이 생기고, 취소하면 원장에 '배정됨 → 취소'가 전·후 값으로 남습니다. 위 표는 오늘 실제 원장의 두 줄입니다.",
            "공급사 데이터가 바뀌면 지식 그래프의 공급 관계도 바뀌고, 테이블 구조가 바뀌면 에이전트가 쓰는 메타데이터도 따라갑니다.",
        ],
    },
    {
        "no": 5, "title": "온톨로지 지식과 판단 — 그림용 그래프에서 판단에 쓰는 지식으로",
        "old": "층 사이 연결이 끊기고 검사가 없는 그림용 그래프",
        "new": "단일 스키마(46 클래스·72 관계)로 다섯 층 연결, 상충 계산·감사 22항목·검증 위반 0, 지식 공백 3건 보강",
        "summary": "BSC 전략 → 프로세스 → 리소스 → 설비 진단 → 스킬(SOP)·규칙(DMN) → 외부 변수·예측·사례의 다섯 층이 하나의 스키마로 이어지고, 적재할 때마다 감사기가 검사한다.",
        "images": [("ontology-1440.png", "온톨로지 지식 지도 탭 — 층별 노드와 관계, 이상 패턴을 고르면 진단에서 조치 카드까지의 경로 강조")],
        "table": [
            ["기존", "노드와 관계는 있었지만 층 사이 연결이 끊기고 검사가 없어 그림용에 가까웠다. 순위에 납기·품질 미반영."],
            ["현재", "단일 원본 schema.json(46 클래스·72 관계 유형) → 제약·TTL·에이전트용 DDL 자동 생성. 조치 후보가 어느 KPI를 어느 방향으로 움직이는지를 Skill-AFFECTS→StateVariable-INFLUENCES→Measure 부호 곱으로 계산(상충). 교차 층 감사 질문 22개(고립 노드·역행 관계·출처 없는 입력 등), 속성 선언 검증. 지식 공백 3건(펌프 내부 누설·작동유 열화·과열 정지)은 업계 자료로 답을 정해 넣음."],
            ["달라진 점", "그래프가 '왜 이 조치인가'의 근거를 되돌려 주고, 적재 뒤 감사가 거짓 연결을 잡는다."],
            ["확인 방법", "감사 22/22, 검증 위반 0(3,575 노드·8,889 관계) / 지식→판단 9/9 / 전문가 답 8/8"],
        ],
        "narration": [
            "이 지도는 장식이 아니라 판단기의 입력입니다. 왼쪽 전략 목표에서 오른쪽 예측·사례까지 선이 이어져 있고, 이상 패턴을 고르면 진단에서 조치 카드까지 가는 길이 강조됩니다.",
            "스키마 파일 하나에서 제약과 에이전트용 DDL이 자동으로 나오니, 지식을 바꿔도 세 곳을 따로 고칠 일이 없습니다.",
        ],
    },
    {
        "no": 6, "title": "실시간 모니터링과 이벤트 스트림 — 새로고침에서 밀어 주는 화면으로",
        "old": "정적 표와 주기 새로고침. 에이전트 활동이 보이지 않음",
        "new": "SSE 실시간 스트림(도구 소요시간·작업 전이·사람 선택), 원천과 같은 상태 표시, Grafana 추세",
        "summary": "서버가 이벤트를 밀어 주는 실시간 스트림(도구 소요시간·작업 전이·인스턴스 변화)과 Grafana 추세. 화면의 상태가 원천 데이터와 같다.",
        "images": [("main-1440.png", "실습 홈 — 설비 3기·열린 인시던트·지식 지도 크기·시간 배율, 연결 도식"),
                   ("trends-1440.png", "실시간 모니터링 탭 — 유온 TS1 추세와 경보·조치 전후, 이상 점수, 냉각 효율")],
        "table": [
            ["기존", "정적 표와 주기 새로고침. 에이전트가 무엇을 하는지 보이지 않음."],
            ["현재", "SSE /api/events/stream: 종류별 색(도구·작업·사람·오류·진행)·필터·멈춤, 도구 시작/끝 짝으로 소요시간 표시, 작업 전이 이벤트가 오면 인스턴스 화면 자동 반영. 헤더에 '실시간 연결됨·구성요소 13/14 응답' 같은 원천 상태. Grafana 대시보드 연결."],
            ["달라진 점", "에이전트가 지금 어떤 도구를 몇 초 쓰고 있는지, 사건이 어느 단계로 넘어갔는지가 화면에서 바로 보인다."],
            ["확인 방법", "실시간 스트림 60건 표시(인스턴스 탭) / 회귀 시간 anchor·근거 커버리지 통과 / 사건 120건 화면↔원천 대조(A084)"],
        ],
        "narration": [
            "홈 화면의 숫자는 꾸민 값이 아니라 지금 서비스가 답한 값입니다. 오른쪽 위 '구성요소 13/14 응답'처럼 안 되는 것도 그대로 보여 줍니다.",
            "실시간 스트림을 켜 두면 에이전트가 도구를 쓸 때마다 한 줄씩 올라옵니다. 화면 공유 중에 결함을 주입하면 몇 초 안에 흐름이 시작되는 걸 같이 볼 수 있습니다.",
        ],
    },
    {
        "no": 7, "title": "(독립) 원문 매뉴얼 인제스천 — 손으로 넣던 SOP에서 실물 매뉴얼 추출로",
        "old": "SOP·절차를 손으로 입력, 원문 인용 없음",
        "new": "실물 매뉴얼 PDF를 구간 분할→에이전트 추출→앵커 검증·병합→교정 루프로 적재(80쪽 15분, 10/10)",
        "summary": "제조사 PDF(다이킨 80쪽, 126,168자)를 제목 경계 40,000자 구간으로 나눠 에이전트가 추출하고, 서버가 결정적으로 병합·검증·교정한다.",
        "images": [],
        "table": [
            ["기존", "SOP·절차를 손으로 입력. 원문 인용 없음."],
            ["현재", "원문(PDF·Markdown) 등록 → 페이지 범위 구간 분할 → 구간별 에이전트 추출(절·절차·참고·검토 의견, 원문 문자 위치 앵커) → 서버 병합·중복 제거·앵커 재검증 → 검토 피드백 → 틀린 곳만 다시 추출하는 교정 루프 → 온톨로지 적재(SOP·절차·인용)."],
            ["달라진 점", "스킬 단계마다 원문 번호(HM-7.3 같은)가 붙고, 실물 매뉴얼 80쪽을 15분(워커 2개)에 교정 0회로 넣는다."],
            ["확인 방법", "아래 실측 표 / 왕복(온톨로지 → 문서 → 재추출) 7/7"],
        ],
        "case": {"title": "실측 (10-07)", "head": ["문서", "크기", "구조", "결과", "시간"], "rows": [
            ["HM-9(기존 시험 문서)", "2.3 KB", "통문서", "8/8", "—"],
            ["HM-FULL 2,294줄", "82,795자", "구간 3", "7/8(발췌 4절)", "1,443초(워커 1)"],
            ["HM-FULL3 6,785줄", "246,108자", "구간 7", "7/8, 절 198·SOP 193 전부", "82분(워커 1)"],
            ["다이킨 EHU40 80쪽 PDF 1차", "126,168자", "구간 4(페이지 범위)", "6/8 + 언어 혼재", "27분(워커 2)"],
            ["다이킨 EHU40 2차(정의 1.6)", "같음", "구간 4", "10/10, 교정 0, 소절별 절차 37", "15분(워커 2)"],
            ["온톨로지 역추출 HM-REV", "9,542자", "통문서", "7/7(왕복)", "약 3분"],
        ]},
        "narration": [
            "매뉴얼을 통째로 넣으면 모델 출력 한도에 걸립니다. 그래서 제목 경계로 자르고, 자른 조각마다 추출한 뒤 서버가 글자 위치를 맞춰 다시 붙입니다. 인용이 원문과 한 글자라도 다르면 거절하고 다시 시킵니다.",
            "표의 마지막 줄들은 실제 제조사 매뉴얼입니다. 처음엔 불릿 글자와 번역 섞임으로 두 번 교정이 났고, 규칙을 고친 2차에서는 교정 없이 10개 검사가 전부 통과했습니다.",
        ],
    },
    {
        "no": 8, "title": "(독립) 검증 체계와 참고 제품 대조 — \"돌려 본 것만 됐다\"",
        "old": "단위시험 145, 통합 시험 수동, 참고 레포는 README 수준",
        "new": "라이브 회귀 핵심 12개 전부 통과·단위 1,103, 참고 레포 46/47 본문 대조·격차 7건 반영",
        "summary": "변경 뒤 한 명령으로 도는 라이브 회귀(핵심 12개 전부 통과), 단위시험 1,103, 참고 제품 레포 47개 중 46개 본문 대조·격차 7건 반영.",
        "images": [],
        "table": [
            ["기존", "단위시험 145, 통합 시험은 수동. 참고 레포는 README 수준 조사."],
            ["현재", "run_regression.py: 핵심 묶음 12개(쿨러 42항목·효과보상 22·작업지시 19·DDL·SCM·시간 anchor·근거 커버리지·지식→판단 9·전문가 답 8·병렬 합류 7·감사 22·스키마 검증) + 워커 묶음 6개. 통과는 검사기 자신의 통과 줄로만 판정. 참고 레포는 고정 커밋으로 본문 대조해 채택·보류 근거를 행마다 기록."],
            ["달라진 점", "오늘 회귀가 결함 둘을 실제로 잡았다 — 신선도 검사가 수 ms 음수 시각차를 '신뢰 불가'로 판정하던 것, 재시작 직후 DB 접속 1회 실패로 경보 소비가 영구히 죽던 것. 둘 다 고치고 다시 돌려 통과."],
            ["확인 방법", "아래 회귀 표 / pytest 1,103 passed / REFERENCE_ADOPTION.md 47행"],
        ],
        "case": {"title": "핵심 회귀 12개 최종 결과(10-07)", "head": ["검사", "결과", "소요"], "rows": [
            ["쿨러 열화 시나리오 42항목(단독 재실행)", "42/42", "151초"],
            ["효과 보상·재작업 22항목", "22/22", "164초"],
            ["작업지시 전용 카드 19항목", "19/19", "161초"],
            ["DDL 드리프트 / SCM 동기화", "통과 / 통과", "10초 / 30초"],
            ["시간 anchor / 근거 커버리지", "통과 / 통과", "48초 / 34초"],
            ["지식→판단 9 / 전문가 답 8", "9/9 / 8/8", "35초 / 27초"],
            ["병렬 분기·합류 7 / 온톨로지 감사 22 / 스키마 검증", "7/7 / 22/22 / 위반 0", "11초 / 2초 / 1초"],
        ]},
        "narration": [
            "'된다'는 말은 돌려 본 것에만 씁니다. 이 표의 숫자는 검사기가 스스로 찍은 통과 줄이고, 러너는 그것을 읽기만 합니다.",
            "검증이 실제로 결함을 잡았다는 게 중요합니다. 오늘 두 건은 코드를 읽어서는 못 찾았을 것들이고, 회귀를 돌리다 나왔습니다.",
        ],
    },
]

SOURCES = [
    ["회귀 핵심 12개", ".evidence/reaudit/reg-a102-core, reg-a105-core2(쿨러·SCM), reg-a105-core3(DDL), reg-a108-effect(효과보상)"],
    ["단위시험 1,103", "pytest -q, 2026-10-07 18:25 (docs/handoff/HANDOFF.md A108)"],
    ["병렬 합류 7/7", ".evidence/reaudit/a100-parallel-1/result.json"],
    ["감사 22/22 · 검증 위반 0", ".evidence/reaudit/a101-semantic-1/"],
    ["규칙 15/15 · 업무 3/3 · 시계열 3/3 · 전문가 8/8 · 임대 6/6 · 취소 8/8", "HANDOFF A087 · A081 · A083 · A098 · A097"],
    ["인제스천 실측", "D:/work/작업보고/2026-10-07.md 실측 표, .evidence/reaudit/a094-ingest-real-ehu40-2/"],
    ["참고 레포 46/47", "docs/handoff/REFERENCE_ADOPTION.md, verification/2026-10-07/r13-group1~9"],
    ["거래 원장 두 줄", ".evidence/reaudit/a109-report-ui/ledger.json (10-07 18:45 실제 실행)"],
    ["사례 인스턴스", "GET /api/instances/anomaly_response.874130b0-9264-4017-b0a8-e1aa002aabd8"],
    ["'기존' 상태", "docs/handoff/HANDOFF.md §4 확정 사실(2026-10-03 레포 상태·알려진 한계)"],
]

CSS = """
:root{--ink:#1b2430;--muted:#5b6675;--line:#dfe4ea;--accent:#1f5fbf;--soft:#f3f6fa;--old:#fff5f2;--new:#eef8f1}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font-family:"Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif;line-height:1.6}
.page{max-width:1180px;margin:0 auto;padding:40px 32px 80px}
header{border-bottom:3px solid var(--accent);padding-bottom:18px;margin-bottom:28px}
header h1{font-size:30px;margin:0 0 6px;letter-spacing:-.3px}header .sub{color:var(--muted);font-size:15px}
.overview{width:100%;border-collapse:collapse;margin:18px 0 40px;font-size:15px}
.overview th,.overview td{border:1px solid var(--line);padding:10px 12px;vertical-align:top;text-align:left}
.overview th{background:var(--soft)}
section{margin:0 0 64px;padding-top:12px;border-top:1px solid var(--line)}
.no{display:inline-block;background:var(--accent);color:#fff;font-weight:700;border-radius:8px;padding:2px 12px;margin-right:10px;font-size:18px}
section h2{font-size:26px;margin:14px 0 8px}
.summary{font-size:18px;color:#243447;background:var(--soft);border-left:5px solid var(--accent);padding:12px 16px;margin:10px 0 22px}
figure{margin:0 0 22px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fafbfc}
figure img{display:block;width:100%;height:auto}
figcaption{padding:8px 12px;font-size:14px;color:var(--muted);border-top:1px solid var(--line)}
table.ba{width:100%;border-collapse:collapse;margin:8px 0 22px;font-size:15.5px}
table.ba td{border:1px solid var(--line);padding:12px 14px;vertical-align:top}
table.ba td:first-child{width:120px;font-weight:700;white-space:nowrap;background:var(--soft)}
table.ba tr.old td{background:var(--old)}table.ba tr.old td:first-child{background:#ffe9e3}
table.ba tr.new td{background:var(--new)}table.ba tr.new td:first-child{background:#dcefe2}
table.case{width:100%;border-collapse:collapse;margin:6px 0 22px;font-size:14.5px}
table.case th,table.case td{border:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left}
table.case th{background:var(--soft)}
h3{font-size:17px;margin:18px 0 6px;color:#243447}
.talk{background:#fffbe6;border:1px solid #f1e3a1;border-radius:10px;padding:16px 20px;margin:6px 0 10px}
.talk p{font-size:18.5px;line-height:1.75;margin:0 0 10px}.talk p:last-child{margin:0}
.talk .lab{font-size:13px;font-weight:700;color:#8a6d00;letter-spacing:.5px;margin-bottom:6px}
footer{color:var(--muted);font-size:13.5px}
@media print{section{break-inside:avoid-page}.page{padding:0}}
"""


def esc(s):
    return html.escape(str(s))


def build_html():
    out = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(TITLE)}</title><style>{CSS}</style></head><body><div class='page'>"]
    out.append(f"<header><h1>{esc(TITLE)}</h1><div class='sub'>{DATE} · 실제 화면 캡처(10-07 18:30)와 오늘 돌린 검사 결과만으로 작성 · 절마다 같은 틀: 요약 → 화면 → 기존/현재 표 → 읽을 설명</div></header>")
    out.append("<table class='overview'><tr><th style='width:34px'>#</th><th style='width:30%'>기능 묶음</th><th>기존에는</th><th>현재는</th></tr>")
    for s in SECTIONS:
        out.append(f"<tr><td>{s['no']}</td><td><a href='#s{s['no']}'>{esc(s['title'].split(' — ')[0])}</a></td><td>{esc(s['old'])}</td><td>{esc(s['new'])}</td></tr>")
    out.append("</table>")
    for s in SECTIONS:
        out.append(f"<section id='s{s['no']}'><h2><span class='no'>{s['no']}</span>{esc(s['title'])}</h2><div class='summary'>{esc(s['summary'])}</div>")
        for name, cap in s["images"]:
            im = img(name, cap)
            if im:
                out.append(f"<figure><img src='{im['src']}' alt='{esc(cap)}'><figcaption>{esc(cap)}</figcaption></figure>")
        out.append("<table class='ba'>")
        for i, (k, v) in enumerate(s["table"]):
            cls = "old" if k == "기존" else "new" if k == "현재" else ""
            out.append(f"<tr class='{cls}'><td>{esc(k)}</td><td>{esc(v)}</td></tr>")
        out.append("</table>")
        if s.get("case"):
            c = s["case"]
            out.append(f"<h3>{esc(c['title'])}</h3><table class='case'><tr>" + "".join(f"<th>{esc(h)}</th>" for h in c["head"]) + "</tr>")
            for r in c["rows"]:
                out.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>")
            out.append("</table>")
        if s.get("ledger"):
            rows = ledger_rows()
            if rows:
                out.append("<h3>기업 거래 원장(실제 두 줄) — 스킬 / 참조 / 요청자 / 변경 전 상태 / 변경 후 상태 / cancelled_at / 되돌린 거래</h3><table class='case'><tr><th>스킬</th><th>참조</th><th>요청자</th><th>변경 전</th><th>변경 후</th><th>cancelled_at</th><th>되돌린 거래</th></tr>")
                for r in rows:
                    out.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>")
                out.append("</table>")
        out.append("<div class='talk'><div class='lab'>화면을 공유하며 읽을 설명</div>" + "".join(f"<p>{esc(p)}</p>" for p in s["narration"]) + "</div></section>")
    out.append("<footer><h3>수치 출처</h3><table class='case'><tr><th>수치</th><th>출처</th></tr>" + "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in SOURCES) + "</table>"
               "<p>캡처는 포털(127.0.0.1:8088) 실제 화면이며 수정하지 않았다. 시뮬레이션 환경(시간 배율 20)이라 분 단위 시간은 실제 설비의 20배속이다. 이 문서는 사용자 설명용이며 학생 배포본이 아니다.</p></footer>")
    out.append("</div></body></html>")
    return "".join(out)


def build_md():
    L = [f"# {TITLE}", "", f"{DATE} · 실제 화면 캡처와 오늘 돌린 검사 결과만으로 작성. 그림은 `.evidence/reaudit/a109-report-ui/`.", "", "| # | 기능 묶음 | 기존에는 | 현재는 |", "|---|---|---|---|"]
    for s in SECTIONS:
        L.append(f"| {s['no']} | {s['title'].split(' — ')[0]} | {s['old']} | {s['new']} |")
    for s in SECTIONS:
        L += ["", f"## {s['no']}. {s['title']}", "", f"**요약:** {s['summary']}", ""]
        for name, cap in s["images"]:
            L.append(f"![{cap}](../../.evidence/reaudit/a109-report-ui/{name})"); L.append(f"*{cap}*"); L.append("")
        L += ["| 구분 | 내용 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in s["table"]] + [""]
        if s.get("case"):
            c = s["case"]; L += [f"### {c['title']}", "", "| " + " | ".join(c["head"]) + " |", "|" + "---|" * len(c["head"])] + ["| " + " | ".join(r) + " |" for r in c["rows"]] + [""]
        if s.get("ledger"):
            rows = ledger_rows()
            if rows:
                L += ["### 기업 거래 원장(실제 두 줄)", "", "| 스킬 | 참조 | 요청자 | 변경 전 | 변경 후 | cancelled_at | 되돌린 거래 |", "|---|---|---|---|---|---|---|"] + ["| " + " | ".join(r) + " |" for r in rows] + [""]
        L += ["**화면을 공유하며 읽을 설명**", ""] + [f"> {p}" for p in s["narration"]] + [""]
    L += ["", "## 수치 출처", "", "| 수치 | 출처 |", "|---|---|"] + [f"| {a} | {b} |" for a, b in SOURCES]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    h = build_html(); (OUT / f"{DATE}_HYD_기능보고.html").write_text(h, encoding="utf-8")
    (OUT / f"{DATE}_HYD_기능보고.md").write_text(build_md(), encoding="utf-8")
    missing = [n for s in SECTIONS for n, _ in s["images"] if not (CAP / n).exists()]
    print("html", len(h) // 1024, "KB; missing images:", missing or "none")
