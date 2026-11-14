"""수업 한 바퀴 — 실라버스(정본 엑셀)의 포털 실습 행을 실라버스 순서대로, 학생 한 명이 포털을 누르는 그대로 돌리고 판정한다.

    .venv314/Scripts/python.exe workspace/개발/scripts/class_round.py --out 작업/<날짜>_<제목>/실행/<이름> [--only 01,05] [--from 05] [--headed] [--ai-runs 1|3]

전제: 시작.bat(scripts/start_all.sh)이 「완료」까지 돈 스택(수업 시작 상태 — 처리 건 0), AI 워커 1개. 키 있는 모드(AI_MODE=live)와
키 없는 모드(replay — 강사 녹화 재생) 둘 다 돈다 — 워커 /healthz 의 ai_mode 를 읽어 판정 이름 · 결과에 적는다. 포트는 .hyd-runtime/ports.json.

실습 = 실라버스 행: 실습마다 그 행의 제목(정본 workspace/강의제작/산출물/실라버스/피지컬AI_실라버스_최종본.xlsx — 통합반 온라인 · 실전반 온라인
시트)을 적고, 돌 때 엑셀에서 행 번호 · 구분 · 문장을 읽어 판정 이름 앞에 「[통합 40행 · 실전 35행]」으로 붙인다(행이 옮겨져도 제목으로 찾는다,
못 찾으면 실패로 남긴다). 판정마다 네 축 가운데 하나를 단다(실라버스 세션이 항목별로 답한다):
  ① 지원      — 그 행이 시키는 행동을 화면에서 할 수 있고 결과가 원천(업무 DB · 그래프 · 원문 · 정의)과 맞는다
  ② 끝까지 안전 — 예외 경로(거절 · 권한 · 잘못된 입력 · 되돌리기)가 사람 글로 막히고 원본 · 설비를 바꾸지 않는다
  ③ 키 없는 PC — 키 없는 모드에서 잘못 막히지 않는다(강사 녹화 재생 · 제공 문서 캐시). 키 있는 모드 실행에서는 「측정 안 함」
  ④ 여러 번 · 순서 — 같은 행동을 다시 하거나 순서를 바꿔도 버틴다
AI 단계는 같은 입력으로 3번 돌린다(Round.repeat3). 실행마다 실제 AI · 같은 요청 다시 냄 · 강사 녹화 재생을 처리 건 기록(작업의 세션)에서 읽어
적고, 「3번 같은 …」 일치는 실제 AI 실행끼리만 잰다. AI 결과는 「답이 왔다」가 아니라 내용(원인 · 추천 · 제외 규칙 · 승인 역할 · 근거 수치 ·
학생 문장)을 업무 DB · 그래프 · 원문으로 판정한다.
오류 · 거절은 학생이 읽을 한국어 문장이어야 한다(human_text). 기다림은 일시 오류(연결 · 5xx · 화면 다시 그림)만 다시 시도하고 나머지는 바로 실패.
결과: DIR/results.json · DIR/summary.md(실라버스 행 × 네 축 표) · 실패 화면 DIR/shots/*.png · 실습별 콘솔 오류 · 실패한 요청. 실패가 하나라도 있으면 종료 코드 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "it" / "process"), str(ROOT / "common")]
from procsvc import engine as process_engine  # noqa: E402 — 경계 타이머 배율 · ISO 기간(사람 단계는 벽시계) 정본
from procsvc.handover import AREAS as HANDOVER_AREAS, START_INPUTS as HANDOVER_START  # noqa: E402 — 교대 계약 정본
from procsvc.mcp_registry import BASE_SERVERS  # noqa: E402 — 에이전트가 쓰는 기본 도구 서버 정본

SYLLABUS = ROOT / "workspace/강의제작/산출물/실라버스/피지컬AI_실라버스_최종본.xlsx"
SYLLABUS_SHEETS = {"통합": "통합반 온라인", "실전": "실전반 온라인"}        # 시트 이름 앞부분(시간 표기는 바뀔 수 있다)
SAMPLES = ROOT / "it/portal/www/samples"
AXES = ("① 지원", "② 끝까지 안전", "③ 키 없는 PC", "④ 여러 번 · 순서")
# 선택 도구(Redpanda console · Prometheus)는 기본 구성에 없어 주소 확인이 실패하는 것이 정상이다. 무시할 요청은 이 PC의 바깥 포트로 고른다
OPTIONAL_PORTS = (8085, 9090, 9644)
# 결함 시뮬레이션이 주입하는 외란 → 온톨로지 외란 변수(ot/plant-sim/plantsim/plant.py:15 FAULT_KINDS 주석 — 「주입한 것」이 정답의 출처)
FAULT_DISTURBANCE = {"cooler_degradation": "sv:fouling", "pump_leakage": "sv:leak", "fan_vibration": "sv:bearing-wear"}
NUMERALS = {"하나": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}


# ====================================================================== 순수 판정 함수(테스트: workspace/개발/tests/test_class_round.py)
_RAW_ID = re.compile(r"\b(?:[a-z]+:[a-z0-9][a-z0-9_.-]+|[a-z]+_[a-z0-9_]+|[a-z]+[A-Z][A-Za-z]+|[A-Z]{4,}(?:_[A-Z]+)*)\b")
_RAW_ALLOW = {"HYD", "SCADA", "PLC", "MQTT", "KPI", "BSC", "SOP", "ERP", "CMMS", "DMZ", "TS1", "CE", "PS1", "FS1", "VS1", "REMOTE", "AUTO", "JSON",
              "BPMN", "SKILL", "LOCAL", "MANUAL", "PBL", "MCP", "FUXA"}
_NOT_HUMAN = re.compile(r"Traceback|Exception|\bError\b|Error:|[A-Z][a-z]+Error\b|HTTP(?: Error)? ?[45]\d\d|→ ?[45]\d\d\b|\(\s*[45]\d\d\s*\)"
                        r"|\b[45]\d\d (?:Internal|Not Found|Bad Request|Forbidden|Unauthorized)|\bundefined\b|\bnull\b|(?:^|[\s(:·])NaN(?=$|[\s)·%])"
                        r"|\{\"|\bdetail\s*:|\[object Object\]", re.M)


_PROCEDURE_NO = re.compile(r"\bSOP-[A-Z]+-\d+\b|\bkWh\b")     # 매뉴얼의 절차 번호(SOP-COOL-11)는 학생이 원문과 대조하는 번호, kWh 는 단위 — 화면에 그대로 둔다


def raw_ids(text: str) -> list[str]:
    """학생 글에 섞인 원문 id · 영문 상수 · 코드 이름(camelCase 포함). 매뉴얼 절차 번호는 원문 번호라 세지 않는다."""
    text = _PROCEDURE_NO.sub(" ", text or "")
    return sorted({m for m in _RAW_ID.findall(text) if m.split("_")[0] not in _RAW_ALLOW and not m.startswith(("http:", "https:"))})[:12]


def human_text(text: Any) -> tuple[bool, str]:
    """학생이 읽는 문장인가: 글자이고, 한글 낱말이 둘 이상이고, 영문 예외 · 상태 코드 · 원문 id · 코드 이름이 없어야 한다."""
    if not isinstance(text, str):
        return False, f"글이 아님({type(text).__name__}): {json.dumps(text, ensure_ascii=False, default=str)[:200]}"
    t = text.strip()
    if not t:
        return False, "빈 문구"
    bad = _NOT_HUMAN.search(t)
    if bad:
        return False, f"사람 글이 아님({bad.group(0).strip()}): {t[:200]}"
    ids = raw_ids(t)
    if ids:
        return False, f"원문 id · 코드 이름이 보임({', '.join(ids[:4])}): {t[:200]}"
    if len([w for w in t.split() if re.search(r"[가-힣]", w)]) < 2:
        return False, f"한글 문장이 아님: {t[:200]}"
    return True, t[:200]


def ai_source(session_id: str | None) -> str:
    """작업 결과의 세션 id(worker/ai_replay.py COURSE · REUSE 머리) → 이번 실행이 무엇이었나."""
    s = str(session_id or "")
    if not s:
        return "기록 없음"
    if s.startswith("reuse:"):
        return "같은 요청 다시 냄"
    if s.startswith("replay:"):
        return "강사 녹화 재생"
    return "실제 AI"


def ai3_identity(runs: list[dict], same_keys: tuple[str, ...]) -> list[tuple[str, bool | None, str]]:
    """「3번 같은 <키>」 판정 — 실제 AI 실행끼리만 비교한다. (이름, 통과? | None = 측정 안 함, 메모)."""
    real = [r for r in runs if r.get("ai") == "실제 AI" and not r.get("error")]
    count = ", ".join(f"{k} {sum(1 for r in runs if r.get('ai') == k)}" for k in ("실제 AI", "같은 요청 다시 냄", "강사 녹화 재생", "기록 없음")
                      if any(r.get("ai") == k for r in runs))
    out = []
    for key in same_keys:
        values = [json.dumps(r.get(key), ensure_ascii=False, sort_keys=True, default=str) for r in real]
        if len(real) < 2:
            out.append((f"3번 같은 {key}", None, f"실제 AI 실행이 {len(real)}번뿐이라 일치를 잴 수 없음({count}) — 다시 낸 실행은 앞 결과의 사본이다"))
        else:
            out.append((f"3번 같은 {key}", len(set(values)) == 1, f"실제 AI {len(real)}번: " + " | ".join(v[:200] for v in values)))
    return out


def roles_in_answer(answer: str, expected: dict[str, str], known_roles: set[str]) -> tuple[bool, str]:
    """질문 답의 「각 절차의 승인 역할」이 원문 「승인:」 줄과 같은가. expected = {SOP: 역할 이름}."""
    if not expected:
        return False, "원문에서 승인 역할을 읽지 못함"
    named = {r for r in known_roles if r in (answer or "")}
    want = set(expected.values())
    if len(want) == 1:
        role = next(iter(want))
        ok = role in named and not (named - want)
        return ok, f"원문 {role} · 답에 나온 역할 {sorted(named)}"
    bad = []
    ids = [m.start() for m in re.finditer(r"SOP-[A-Z0-9-]+", answer or "")]
    for sop, role in expected.items():
        at = (answer or "").find(sop)
        nxt = min([i for i in ids if i > at] or [len(answer or "")]) if at >= 0 else -1
        if at < 0 or role not in (answer or "")[at:nxt]:
            bad.append(f"{sop}→{role}")
    return not bad, ("원문과 다른 절차: " + ", ".join(bad)) if bad else f"절차마다 원문 역할 {expected}"


def card_findings(dec: dict, source_approver: dict[str, str]) -> list[str]:
    """판단 카드 내용 판정(빈 목록 = 맞음): 추천 = 실행 가능한 1순위, 제외 카드는 규칙이 있다, 카드 승인 역할 = 원문 「승인:」."""
    bad = []
    opts = dec.get("options") or []
    feasible = sorted((o for o in opts if o.get("feasible")), key=lambda o: o.get("rank") or 99)
    if not opts:
        return ["카드가 없음"]
    if not feasible or dec.get("recommended") != feasible[0]["id"]:
        bad.append(f"추천 {dec.get('recommended')} ≠ 실행 가능한 1순위 {feasible[0]['id'] if feasible else '없음'}")
    for o in opts:
        if not o.get("feasible") and not [v for v in o.get("violations") or [] if v.get("rule")]:
            bad.append(f"{o['id']} 제외인데 규칙이 없음")
        want = source_approver.get(o.get("sopId") or "")
        got = (o.get("approver") or {}).get("name")
        if want and got != want:
            bad.append(f"{o.get('sopId')} 승인 역할 {got} ≠ 원문 {want}")
        if not want:
            bad.append(f"{o.get('sopId')} 원문에 「승인:」 줄이 없음")
    return bad


def purchase_findings(dec: dict, stock: dict) -> list[str]:
    """구매 카드 판정(빈 목록 = 맞음) — 원천과 대조: 추천 공급사는 AVL(ERP 견적), 수량 ≥ 부족 수량(ERP), 단가 · 불량률 = 견적,
    총비용 = 단가 × 수량 + 수량 × 불량률 × 불량 1건 손실 + (불량률이 기준을 넘으면) 전수 검사 비용 — 손실 · 검사 비용 · 기준은 원문(PR-07) 인용에 있는 값."""
    rec = next((o for o in dec.get("options") or [] if o.get("id") == dec.get("recommended")), None)
    if not rec:
        return ["추천 카드가 없음"]
    eco = rec.get("economicComparison") or {}
    policy = eco.get("policy") or {}
    quote = str((policy.get("anchor") or {}).get("quote") or "")
    q = ((dec.get("facts") or {}).get("spare_quotes") or {}).get(eco.get("supplier"))
    qty = eco.get("quantity")
    bad = []
    if not q:
        return [f"공급사 {eco.get('supplier')} 의 견적이 판단 사실에 없음"]
    if not q.get("avl"):
        bad.append(f"공급사 {eco.get('supplier')} 는 AVL 이 아님")
    need = stock.get("need_qty")
    if need is None or qty is None or qty < need:
        bad.append(f"수량 {qty} < 부족 수량 {need}(ERP)")
    if eco.get("unit_price") != q.get("price") or eco.get("fail_rate") != q.get("fail_rate"):
        bad.append(f"단가 · 불량률 {eco.get('unit_price')} · {eco.get('fail_rate')} ≠ 견적 {q.get('price')} · {q.get('fail_rate')}")
    for name, value, text in (("불량 1건 손실", policy.get("loss_per_failure"), f"{policy.get('loss_per_failure')}만 원"),
                              ("전수 검사 비용", policy.get("inspection_cost"), f"{policy.get('inspection_cost')}만 원"),
                              ("검사 기준 불량률", policy.get("inspection_threshold"), f"{round(float(policy.get('inspection_threshold') or 0) * 100)} %")):
        if value is None or text not in quote:
            bad.append(f"{name} {value} 이(가) 원문 인용에 없음")
    if qty is not None and not bad:
        buy = float(qty) * float(q["price"])
        fail = float(qty) * float(q["fail_rate"]) * float(policy["loss_per_failure"])
        insp = float(policy["inspection_cost"]) if float(q["fail_rate"]) > float(policy["inspection_threshold"]) else 0.0
        for name, got, want in (("구매 금액", eco.get("purchase_amount"), buy), ("불량 기대비용", eco.get("expected_failure_cost"), fail),
                                ("검사 비용", eco.get("inspection_cost"), insp), ("총비용", eco.get("total_cost"), buy + fail + insp)):
            if got is None or abs(float(got) - want) > 0.01:
                bad.append(f"{name} {got} ≠ 원문 식 {want:g}")
    return bad


def handover_findings(checks: list[dict], open_orders: list[str], claims_done: bool, claims_arrival: bool, arriving: bool) -> list[str]:
    """교대 인계안 판정(빈 목록 = 맞음) — 업무 DB 원천과 대조: 열린 작업지시가 있는데 메모가 「정비 완료」면 메모 영역은 모순 · 확인 필요,
    도착 예정 부품이 없는데 메모가 「도착 예정」이면 부품 · 메모 영역은 관측(사실 확인됨)이 아님, 열린 작업지시는 모두 적고 없는 번호는 적지 않음."""
    by = {c.get("area"): c for c in checks}
    bad = []
    if set(by) != set(HANDOVER_AREAS):
        bad.append(f"확인 영역 {sorted(by)} ≠ {sorted(HANDOVER_AREAS)}")
    notes, orders, parts = by.get("work_notes") or {}, by.get("work_orders") or {}, by.get("parts") or {}
    if claims_done and open_orders and notes.get("state") == "observed":
        bad.append("메모의 「정비 완료」가 열린 작업지시와 다른데 메모 영역을 사실 확인(observed)으로 둠")
    if claims_arrival and not arriving and "observed" in (parts.get("state"), notes.get("state")):
        bad.append("도착 예정 부품이 없는데 부품 · 메모 영역을 사실 확인(observed)으로 둠")
    text = orders.get("finding") or ""
    missing = [w for w in open_orders if w not in text]
    if missing:
        bad.append(f"열린 작업지시를 빠뜨림: {missing}")
    made_up = sorted(set(re.findall(r"WO-[0-9A-Z-]+", text)) - set(open_orders) - set(re.findall(r"WO-[0-9A-Z-]+", " ".join(open_orders))))
    if made_up and not all(any(m in o for o in open_orders) for m in made_up):
        bad.append(f"이 설비에 없는 작업지시 번호: {made_up}")
    return bad


def source_procedures(text: str) -> dict:
    """원문 Markdown 의 「### SOP-…」 블록 → {sop: {title, steps:[문장], approver}} (번호 목록만 단계 — 추출 지시와 같은 규칙)."""
    out, cur, section_approver = {}, None, None
    for line in text.splitlines():
        m = re.match(r"^###\s+(SOP-[A-Z0-9-]+)\s+(.*)$", line.strip())
        if m:
            cur = out.setdefault(m.group(1), {"title": m.group(2).strip(), "steps": [], "approver": section_approver})
            continue
        if line.startswith("## "):
            cur, section_approver = None, None
            continue
        if cur is None:
            # 절 머리의 「승인은 X이(가) 한다」는 그 절의 절차에 걸린다(HM-8.7 근본 조치)
            sa = re.search(r"승인은\s*(.+?)(?:이|가)\s*한다", line)
            if sa:
                section_approver = sa.group(1).strip()
            continue
        s = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if s:
            cur["steps"].append(s.group(2).strip())
        a = re.match(r"^승인:\s*([^.。]+)", line.strip())
        if a:
            cur["approver"] = a.group(1).strip()
    return out


def timer_wait_s(definition: dict, boundary_id: str, time_scale: float) -> float:
    """정의의 경계 타이머가 실제(벽시계) 몇 초 뒤에 울리나 — 엔진과 같은 규칙(process_engine.timer_scale: 사람 단계는 벽시계)."""
    timer = next(e for e in definition.get("events") or [] if e.get("id") == boundary_id)
    host = next(a for a in definition.get("activities") or [] if a.get("id") == timer.get("attachedTo"))
    return process_engine.iso_duration_seconds(timer["timer"]) / process_engine.timer_scale(host, time_scale)


def select_labs(codes: list[str], only: str, start: str) -> list[str]:
    """--only · --from 이 고른 실습. 없는 번호는 ValueError(판정 0개로 「성공」하지 않게)."""
    picked = [c.strip() for c in only.split(",") if c.strip()]
    unknown = [c for c in picked + ([start] if start else []) if c not in codes]
    if unknown:
        raise ValueError(f"없는 실습 번호 {unknown} — 있는 번호: {', '.join(codes)}")
    chosen = codes[codes.index(start):] if start else list(codes)
    return [c for c in chosen if not picked or c in picked]


def menu_group_count(sentence: str) -> int | None:
    """실라버스 문장의 「<수> 메뉴 묶음」 → 수(없으면 None)."""
    m = re.search(r"(\S+) 메뉴 묶음", sentence or "")
    return NUMERALS.get(m.group(1)) if m else None


def load_syllabus(path: Path = SYLLABUS) -> dict[str, list[tuple[int, str, str, str]]]:
    """정본 엑셀 → {과정: [(행 번호, 구분, 제목, 상세 문장)]} (통합 · 실전 온라인 시트). 엑셀을 고치지 않는다(읽기 전용)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for course, prefix in SYLLABUS_SHEETS.items():
        sheet = next((ws for ws in wb.worksheets if ws.title.startswith(prefix)), None)
        if sheet is None:
            raise RuntimeError(f"{path.name}: 「{prefix}」 시트가 없습니다 — 시트 이름: {[ws.title for ws in wb.worksheets]}")
        rows = []
        for row in sheet.iter_rows():
            cells = [c for c in row if getattr(c, "value", None) is not None]
            if len(cells) >= 3 and isinstance(cells[0].value, str) and cells[0].value.startswith(("실습", "이론")):
                rows.append((cells[0].row, str(cells[0].value), str(cells[1].value), str(cells[2].value)))
        out[course] = rows
    wb.close()
    return out


def find_row(syllabus: dict, course: str, title: str) -> tuple[int, str, str, str] | None:
    return next((r for r in syllabus.get(course) or [] if r[2].strip() == title.strip()), None)


def uncovered_rows(syllabus: dict, lab_rows: dict[str, list[tuple[str, str]]]) -> list[str]:
    """실라버스의 포털 실습 행 가운데 이 도구의 어느 실습에도 없는 것(새 행이 생기면 여기서 드러난다)."""
    covered = {(c, t.strip()) for rows in lab_rows.values() for c, t in rows}
    return [f"{course} {row}행 「{title}」" for course, rows in syllabus.items() for row, kind, title, _ in rows
            if "포털" in kind and (course, title.strip()) not in covered]


# ====================================================================== 하네스
def host_ports() -> dict[int, int]:
    """시작 스크립트가 고른 바깥 포트(기본 포트 → 이 PC의 포트)."""
    path = ROOT / ".hyd-runtime/ports.json"
    if not path.exists():
        raise RuntimeError(".hyd-runtime/ports.json 이 없습니다 — 시작.bat(scripts/start_all.sh)으로 스택을 먼저 켜세요")
    return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


class HttpStatus(RuntimeError):
    def __init__(self, url, code, body):
        super().__init__(f"GET {url} → {code}: {str(body)[:300]}")
        self.code = code


class ScreenMissing(RuntimeError):
    """화면에 있어야 할 요소가 없다(셀렉터 — 화면이 바뀌었거나 그려지지 않음)."""


def transient(exc: BaseException) -> bool:
    """기다리며 다시 시도해도 되는 일시 오류: 연결 · 시간 초과 · 5xx · 화면 다시 그림. 그 밖(칸 이름 · 형식 변경)은 바로 실패."""
    if isinstance(exc, HttpStatus):
        return exc.code >= 500
    if isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout)) and not isinstance(exc, urllib.error.HTTPError):
        return True
    return type(exc).__module__.startswith("playwright")


@dataclass
class Verdict:
    lab: str
    rows: str
    name: str
    ok: bool
    kind: str            # normal | exception | quality | ai3 | timing
    axis: str
    note: str = ""
    seconds: float | None = None
    shot: str | None = None


@dataclass
class LabLog:
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)


class Round:
    """한 학생의 포털 세션 + 판정 기록. 실습 함수는 lab(r) 꼴로 이것만 받는다."""

    def __init__(self, page, out: Path, syllabus: dict):
        p = host_ports()
        hp = lambda port: p.get(port, port)                              # noqa: E731
        self.page, self.out, self.syllabus = page, out, syllabus
        self.portal = f"http://127.0.0.1:{hp(8088)}"
        self.process = f"http://127.0.0.1:{hp(8080)}"
        self.plant = f"http://127.0.0.1:{hp(8000)}"
        self.detector = f"http://127.0.0.1:{hp(8092)}"
        self.agent = f"http://127.0.0.1:{hp(8091)}"
        self.enterprise = f"http://127.0.0.1:{hp(8095)}"
        self.worker = f"http://127.0.0.1:{hp(8097)}"
        self.inbucket = f"http://127.0.0.1:{hp(54324)}"
        self.ignored = tuple(f":{hp(x)}" for x in OPTIONAL_PORTS) + ("favicon.ico",)
        self.verdicts: list[Verdict] = []
        self.logs: dict[str, LabLog] = {}
        self.lab = "-"
        self.tags: dict[str, str] = {}
        self.memo: dict[str, Any] = {}
        self.ai_runs = 3
        self.ai_mode = "?"
        self.not_measured: list[dict] = []
        self.last_wait_error: BaseException | None = None
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self._log().console_errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda q: self._on_failed(q.url, q.failure or "failed"))
        page.on("response", lambda q: q.status >= 500 and self._on_failed(q.url, f"HTTP {q.status}"))

    # ------------------------------------------------------------------ 기록
    def _log(self) -> LabLog:
        return self.logs.setdefault(self.lab, LabLog())

    def _on_console(self, msg):
        # 예외 경로(잘못된 입력 · 권한 · 중복)는 서버의 4xx 거절이 정상이다 — 브라우저의 「Failed to load resource … 4xx」 줄은 빼고 화면 문구는 판정이 본다
        if msg.type == "error" and re.search(r"Failed to load resource: the server responded with a status of 4\d\d", msg.text or ""):
            return
        if msg.type == "error" and not any(s in (msg.location or {}).get("url", "") for s in self.ignored):
            self._log().console_errors.append(msg.text[:300])

    def _on_failed(self, url: str, why: str):
        if not any(s in url for s in self.ignored) and "net::ERR_ABORTED" not in str(why):
            self._log().failed_requests.append(f"{why} {url}"[:300])

    def check(self, name: str, ok: bool, note: Any = "", kind: str = "normal", seconds: float | None = None, axis: str = AXES[0]) -> bool:
        assert axis in AXES, axis
        shot = None if ok else self.shot(f"FAIL-{self.lab}-{len(self.verdicts):03d}")
        tag = self.tags.get(self.lab, self.lab)
        self.verdicts.append(Verdict(self.lab, tag, name, bool(ok), kind, axis, str(note)[:1500], seconds, shot))
        print(f"  [{'통과' if ok else '실패'}] [{tag}] {axis[0]} {name}" + (f" — {str(note)[:300]}" if note else ""), flush=True)
        return bool(ok)

    def not_measure(self, name: str, why: str, axis: str = AXES[0]):
        assert axis in AXES, axis
        self.not_measured.append(dict(lab=self.lab, rows=self.tags.get(self.lab, self.lab), name=name, axis=axis, why=why))
        print(f"  [측정 안 함] [{self.tags.get(self.lab, self.lab)}] {axis[0]} {name} — {why}", flush=True)

    def evidence(self, name: str, text: Any, why: str, axis: str = AXES[0]):
        """원문 자리 — 도구가 어림 기준 없이 판정할 수 없는 화면 · 답. 원문을 파일로 남기고 통과로 세지 않는다(사람이 읽는다)."""
        path = self.out / "원문" / f"{re.sub(r'[^0-9A-Za-z가-힣_.-]+', '_', f'{self.lab}-{len(self.not_measured):03d}-{name}')[:120]}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.not_measure(name, f"원문 자리 {path.relative_to(self.out)} — {why}", axis=axis)

    def keyless(self, name: str, ok: bool, note: Any = ""):
        """③ 키 없는 PC 판정 — 키 없는 모드(replay) 실행에서만 잰다."""
        if self.ai_mode == "replay":
            return self.check(name, ok, note, kind="exception", axis=AXES[2])
        self.not_measure(name, f"이 실행은 AI_MODE={self.ai_mode} — 키 없는 모드(시작.bat 키 없이) 실행에서 잰다", axis=AXES[2])
        return True

    def human(self, name: str, text: Any, extra: bool = True, axis: str = AXES[1], kind: str = "exception") -> bool:
        ok, why = human_text(text)
        return self.check(name, ok and extra, why, kind=kind, axis=axis)

    def human_message(self, text: Any) -> tuple[bool, str]:
        return human_text(text)

    def shot(self, name: str) -> str | None:
        path = self.out / "shots" / f"{re.sub(r'[^0-9A-Za-z가-힣_.-]+', '_', name)}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.page.screenshot(path=str(path), full_page=False)
            return str(path.relative_to(self.out))
        except Exception as e:                                           # 화면이 없을 때도 판정은 남긴다 — 까닭은 이름에
            return f"화면 저장 실패: {type(e).__name__}"

    # ------------------------------------------------------------------ 관측(API)
    def api(self, method: str, url: str, body: Any = None, timeout: float = 60) -> tuple[int, Any]:
        """(상태 코드, JSON 또는 본문 글자). 4xx · 5xx 도 예외 없이 돌려준다 — 예외 경로 판정에 쓴다."""
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw, code = resp.read(), resp.status
        except urllib.error.HTTPError as e:
            raw, code = e.read(), e.code
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, raw.decode("utf-8", errors="replace")

    def get(self, url: str, timeout: float = 30) -> Any:
        code, body = self.api("GET", url, timeout=timeout)
        if code >= 400:
            raise HttpStatus(url, code, body)
        return body

    def wait(self, seconds: float, probe: Callable[[], Any], every: float = 2.0) -> Any:
        """probe 가 참인 값을 낼 때까지. 시간이 지나면 None(마지막 일시 오류는 self.last_wait_error). 일시 오류만 다시 시도한다."""
        deadline = time.monotonic() + seconds
        self.last_wait_error = None
        while time.monotonic() < deadline:
            try:
                value = probe()
                if value:
                    return value
            except Exception as e:
                if not transient(e):
                    raise
                self.last_wait_error = e
            time.sleep(every)
        return None

    def waited(self) -> str:
        e = self.last_wait_error
        return f" · 마지막 일시 오류 {type(e).__name__}: {str(e)[:200]}" if e else ""

    # ------------------------------------------------------------------ 화면
    def open(self):
        self.page.goto(self.portal + "/", wait_until="domcontentloaded")
        self.page.wait_for_selector("#menuList a[data-tab]", state="attached", timeout=30_000)

    def tab(self, name: str):
        """화면 하나를 학생처럼 연다: 왼쪽 메뉴 줄(#menuList)에서 그 화면의 줄(a[data-tab])을 누른다. 화면이 둘 이상인 메뉴는 접혀 있으면
        메뉴 이름 줄(summary)을 눌러 펼친 뒤 누른다(index.html 주 메뉴 · app.js MENU · renderMenu)."""
        link = self.page.locator(f"#menuList a[data-tab='{name}']")
        link.wait_for(state="attached", timeout=10_000)
        closed = self.page.locator("#menuList details:not([open])", has=link)
        if closed.count():                                                # 접혀 있는 메뉴 — 이름 줄을 눌러 펼친다(화면이 하나뿐인 메뉴는 접기가 없다)
            closed.locator("summary").click()
        link.click()
        if not self.page.locator(f"#view-{name}.active").count():
            raise ScreenMissing(f"메뉴에서 화면 {name} 을(를) 열지 못함")
        self.page.wait_for_timeout(600)

    # ------------------------------------------------------------------ AI 3회
    def repeat3(self, step: str, run_once: Callable[[int], dict], same_keys: tuple[str, ...], limit_s: float | None = None,
                single: int = 0) -> list[dict]:
        """같은 입력으로 AI 단계를 3번. run_once(i) 는 {'seconds', 'ai'(ai_source), 키: 값 …}. 일치는 실제 AI 실행끼리만(ai3_identity).
        --ai-runs 1 이면 single 번째 하나만 돌리고 반복 일치는 측정 안 함. 키 없는 모드에서는 실행마다 녹화가 끝까지 재생되는지가 ③."""
        runs, n = [], self.ai_runs
        for i in (range(3) if n >= 3 else (single,)):
            # 학생마다 워커가 하나다 — 앞 AI 작업이 아직 돌면 그 뒤에 줄을 서 소요 시간이 부푼다
            self.wait(1200, lambda: (self.get(self.worker + "/healthz", timeout=5) or {}).get("runs_in_flight") == 0, every=5)
            t0 = time.monotonic()
            try:
                got = run_once(i) or {}
            except Exception as e:
                got = {"error": f"{type(e).__name__}: {e}"}
            got.setdefault("seconds", round(time.monotonic() - t0, 1))
            got.setdefault("ai", "기록 없음")
            runs.append(got)
            print(f"    {step} {i + 1}/{n} [{got['ai']}]: " + json.dumps(got, ensure_ascii=False, default=str)[:400], flush=True)
        (self.out / "ai3").mkdir(parents=True, exist_ok=True)
        (self.out / "ai3" / f"{self.lab}-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', step)}.json").write_text(
            json.dumps(runs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        errors = [r["error"] for r in runs if r.get("error")]
        self.check(f"{step} — {len(runs)}번 모두 끝까지", not errors, "; ".join(errors), kind="ai3",
                   axis=AXES[3] if len(runs) > 1 else AXES[0])
        sources = [r.get("ai") for r in runs]
        if self.ai_mode == "replay":
            self.keyless(f"{step} — 키 없는 PC에서 강사 녹화가 끝까지 재생됨", not errors and all(s == "강사 녹화 재생" for s in sources),
                         f"실행 출처 {sources}" + (f" · {'; '.join(errors)}" if errors else ""))
            self.not_measure(f"{step} — 3번 같은 {', '.join(same_keys)}", "키 없는 모드: 세 번 모두 같은 녹화의 재생이라 AI 일치를 재지 않는다",
                             axis=AXES[3])
        elif n < 3:
            self.not_measure(f"{step} — 3번 같은 {', '.join(same_keys)}", f"--ai-runs {n}: {single + 1}번째 실행만 돌림", axis=AXES[3])
        else:
            for name, ok, note in ai3_identity(runs, same_keys):
                if ok is None:
                    self.not_measure(f"{step} — {name}", note, axis=AXES[3])
                else:
                    self.check(f"{step} — {name}", ok and not errors, note, kind="ai3", axis=AXES[3])
        if limit_s is not None:
            slowest = max(float(r.get("seconds") or 0) for r in runs)
            self.check(f"{step} — 가장 느린 소요 {slowest:.0f}초 ≤ {limit_s:.0f}초", slowest <= limit_s,
                       ", ".join(f"{float(r.get('seconds') or 0):.0f}s({r.get('ai')})" for r in runs), kind="timing", seconds=slowest)
        return runs

    # ------------------------------------------------------------------ 결과
    def write(self) -> int:
        bad = [v for v in self.verdicts if not v.ok]
        log_failures = 0
        for lab_code, log in self.logs.items():
            if log.console_errors or log.failed_requests:
                log_failures += 1
                bad.append(Verdict(lab_code, self.tags.get(lab_code, lab_code), "콘솔 오류 · 실패한 요청", False, "quality", AXES[1]))
        (self.out / "results.json").write_text(json.dumps({
            "ai_mode": self.ai_mode, "ai_runs": self.ai_runs, "syllabus": str(SYLLABUS.relative_to(ROOT)),
            "labs": [{"lab": c, "rows": self.tags.get(c), "title": t} for c, t, _ in LABS if c in self.tags],
            "verdicts": [asdict(v) for v in self.verdicts], "logs": {k: asdict(v) for k, v in self.logs.items()},
            "not_measured": self.not_measured}, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# 수업 한 바퀴 결과", "", f"AI 모드 {self.ai_mode} · AI 반복 {self.ai_runs} · 판정 {len(self.verdicts)}개 · 실패 "
                 f"{len([v for v in self.verdicts if not v.ok])}개 · 콘솔/통신 오류 실습 {log_failures}개 · 측정 안 함 {len(self.not_measured)}개(통과 아님)", "",
                 "## 실라버스 행 × 네 축 (됨 = 그 축 판정 모두 통과 · 안 됨 = 하나라도 실패 · 확인 못 함 = 판정 없음 또는 측정 안 함만)", "",
                 "| 실습 | 실라버스 행 | " + " | ".join(AXES) + " |", "|---|---|" + "---|" * len(AXES)]
        for code, title, _ in LABS:
            if code not in self.tags:
                continue
            cells = []
            for axis in AXES:
                vs = [v for v in self.verdicts if v.lab == code and v.axis == axis]
                nm = [x for x in self.not_measured if x["lab"] == code and x["axis"] == axis]
                cells.append("안 됨" if any(not v.ok for v in vs) else "됨" if vs else "확인 못 함" + (f"({len(nm)})" if nm else ""))
            lines.append(f"| {code} {title} | {self.tags[code]} | " + " | ".join(cells) + " |")
        lines.append("")
        if self.not_measured:
            lines += ["## 측정 안 함(통과로 세지 않음)"] + [f"- [{x['lab']} · {x['rows']}] {x['axis']} {x['name']} — {x['why']}" for x in self.not_measured] + [""]
        for code in dict.fromkeys(v.lab for v in self.verdicts):
            vs = [v for v in self.verdicts if v.lab == code]
            lines.append(f"## {code} [{self.tags.get(code, code)}] — 통과 {sum(v.ok for v in vs)}/{len(vs)}")
            lines += [f"- {'통과' if v.ok else '**실패**'} {v.axis} [{v.kind}] {v.name}" + (f" — {v.note[:300]}" if v.note else "") for v in vs]
            log = self.logs.get(code)
            if log and (log.console_errors or log.failed_requests):
                lines.append(f"- **콘솔 오류 {len(log.console_errors)} · 실패한 요청 {len(log.failed_requests)}**: " + "; ".join((log.console_errors + log.failed_requests)[:5]))
            lines.append("")
        (self.out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
        return 1 if bad or log_failures else 0


# ====================================================================== 실습 등록(실라버스 순서)
LABS: list[tuple[str, str, Callable[[Round], None]]] = []
LAB_ROWS: dict[str, list[tuple[str, str]]] = {}


def lab(code: str, rows: list[tuple[str, str]], title: str | None = None):
    """실습 하나 = 실라버스 행들. rows = [(과정 '통합' | '실전', 행 제목)] — 비우면 「그 밖에」(실라버스 밖 확인)."""
    def register(fn):
        LABS.append((code, title or rows[0][1], fn))
        LAB_ROWS[code] = rows
        return fn
    return register


def resolve_rows(r: Round, code: str) -> dict[str, tuple[int, str, str, str]]:
    """실습의 실라버스 행을 엑셀에서 찾아 판정 머리표를 만든다. 못 찾으면 실패(행이 바뀌었으면 이 실습의 제목을 고친다)."""
    found, tags = {}, []
    for course, title in LAB_ROWS[code]:
        row = find_row(r.syllabus, course, title)
        if row is None:
            tags.append(f"{course} ?행")
            r.tags[code] = " · ".join(tags)
            r.check(f"실라버스 {SYLLABUS_SHEETS[course]} 에 「{title}」 행이 있다", False, "정본 엑셀에서 찾지 못함 — 행 제목이 바뀌었으면 이 실습의 rows 를 맞춘다")
            continue
        found[course] = row
        tags.append(f"{course} {row[0]}행")
    r.tags[code] = " · ".join(tags) or "그 밖에"
    return found


# ====================================================================== 공용 도우미
_IDLE_TS1 = 50.0          # [쿨러 복구] 뒤 다음 주입 전: 유온이 경보 해제선(52 ℃) 아래 + 감지기 IDLE
SECONDS = {"agent": 900, "instance": 180, "close": 240, "idle": 600}   # 20배속 · 느린 PC 기준 상한(관측 최대의 3배 이상)
AGENT_LIMIT_S = 300       # 학생 진행 기준: AI 한 단계 5분
# 쓰는 사람은 이 PC의 담당자 한 명이고 모든 역할의 구성원이다(it/supabase/seed.sql · migration 000072). 화면에 사람 · 역할 고르기가 없고
# 승인 · 제출 · 닫기 폼은 담당자 id 를 숨은 칸으로 싣는다(www/inbox.js me · ui.js actorInput)
ME = "user:me"
MAILS = {"production": "production@hyd.local", "supplier": "supplier@hyd.local", "receiving": "receiving@hyd.local"}
DOCS = {"HM-8": "HM-8_cooler-fan-manual.md", "PM-02": "PM-02_powerpack-pm-checklist.md", "PR-07": "PR-07_spare-parts-standard.md",
        "HI-01": "HI-01_shift-inspection-supplement.md"}
MY_AGENT = "나의 쿨러 점검 에이전트"
QUESTION = "HM-8 매뉴얼에서 쿨러 냉각 성능 상실의 즉시 완화 조치 절차 번호를 모두 알려 주고, 각 절차의 승인 역할도 알려 줘."
# 질문이 끝난 상태 — 정본은 procsvc.ask._state 의 반환값(서버에 상태 집합 상수가 없다). 끝 상태를 적고 나머지는 기다린다:
# 모르는 새 상태는 「아직 진행」으로 읽혀 시간 초과 실패가 된다(끝난 것으로 읽어 통과하지 않는다). test_class_round 가 _state 를 불러 대조한다.
ASK_END = {"done", "closed", "failed", "broken"}
ASK_LIMIT_S = 300


def txt(r: Round, sel: str, timeout: int = 3000, required: bool = False) -> str:
    """보이는 글자. required 면 없을 때 ScreenMissing(빈 글로 덮지 않는다)."""
    loc = r.page.locator(sel).first
    try:
        loc.wait_for(state="attached", timeout=timeout)
    except Exception as e:
        if required:
            raise ScreenMissing(f"화면에 {sel} 이 없음") from e
        return ""
    return (loc.inner_text(timeout=timeout) or "").strip()


def all_txt(r: Round, sel: str) -> str:
    """접힌 칸까지 포함한 글자(text_content)."""
    return " ".join((x or "") for x in r.page.locator(sel).all_text_contents())


def source_doc(key: str) -> dict:
    return source_procedures((SAMPLES / DOCS[key]).read_text(encoding="utf-8"))


def approvers_of(*keys: str) -> dict[str, str]:
    out = {}
    for k in keys:
        out.update({sop: p["approver"] for sop, p in source_doc(k).items() if p.get("approver")})
    return out


def view_of(r: Round, pid: str) -> dict:
    return r.get(f"{r.process}/api/instances/{urllib.parse.quote(pid, safe='')}")


def rows_of(view: dict) -> dict:
    out: dict = {}
    for w in sorted(view.get("workitems") or [], key=lambda w: str(w.get("start_date") or "")):
        out[w["activity_id"]] = w
    return out


def vars_of(inst: dict) -> dict:
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or [])}


def item_named(view: dict, step_name: str) -> dict:
    rows = [w for w in view["workitems"] if w.get("activity_name") == step_name]
    rows.sort(key=lambda w: (w.get("generation") or 0, w.get("start_date") or ""))
    return rows[-1] if rows else {}


def session_of(w: dict) -> str | None:
    for part in (w.get("output"), w.get("draft")):
        if isinstance(part, dict) and part.get("cliagents_session_id"):
            return part["cliagents_session_id"]
    return None


def step_failure(view: dict, w: dict) -> str | None:
    """AI 단계가 멈췄으면 학생이 처리 건에서 읽는 문장(오류 이벤트의 friendly) — 실패 표시는 draft_status, 작업 status 는 IN_PROGRESS 그대로다."""
    if w.get("draft_status") not in ("FAILED", "CANCELLED"):
        return None
    errs = [e for e in view.get("events") or [] if e.get("todo_id") == w.get("id") and e.get("event_type") == "error"]
    data = (errs[-1].get("data") or {}) if errs else {}
    return data.get("friendly") or data.get("name") or f"(처리 기록에 문장 없음 — draft_status {w.get('draft_status')})"


def step_state(view: dict, step_name: str) -> tuple[str, str]:
    """그 단계의 지금: ('ready' 사람 차례 | 'deferred' 보류 | 'failed' AI 멈춤 | 'ended' 처리 건 끝 | 'running', 문장)."""
    if view["instance"]["status"] != "RUNNING":
        return "ended", view["instance"]["status"]
    if item_named(view, step_name).get("status") == "IN_PROGRESS":
        return "ready", ""
    for w in view["workitems"]:
        if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral"):
            return "deferred", str(((w.get("draft") or {}).get("_deferral") or {}).get("reason") or "")
        failed = step_failure(view, w)
        if failed:
            return "failed", failed
    return "running", ""


def wait_step(r: Round, pid: str, step_name: str, timeout: float) -> tuple[str, str, dict]:
    last = {}

    def probe():
        nonlocal last
        last = view_of(r, pid)
        state, why = step_state(last, step_name)
        return (state, why) if state != "running" else None
    got = r.wait(timeout, probe, every=3)
    return (got[0], got[1], last) if got else ("timeout", "시간 초과" + r.waited(), last)


def wait_end(r: Round, pid: str, timeout: float) -> dict:
    return r.wait(timeout, lambda: (v := view_of(r, pid))["instance"]["status"] != "RUNNING" and v, every=3) or view_of(r, pid)


def decision_of(r: Round, view: dict) -> dict:
    did = vars_of(view["instance"]).get("decision_id")
    return r.get(f"{r.process}/api/decisions/{did}") if did else {}


def card_summary(dec: dict) -> dict:
    """추천 카드 요약 — AI 3회 비교 키(판단 구조: 어느 후보가 어떤 규칙으로 제외됐나)."""
    opts = {o["id"]: o for o in dec.get("options") or []}
    rec = opts.get(dec.get("recommended")) or {}
    eco = rec.get("economicComparison") or {}
    win = rec.get("window") or {}
    return {"recommended": dec.get("recommended"), "approver": (rec.get("approver") or {}).get("id"),
            "evidence": sorted(f"{oid}:{'허용' if o.get('feasible') else '제외'}:{','.join(sorted(v.get('rule') or '' for v in o.get('violations') or []))}"
                               for oid, o in opts.items()),
            "window": win.get("label") or ("즉시" if win.get("immediate") else None),
            "supplier": eco.get("supplier"), "qty": eco.get("quantity"), "amount": eco.get("total_cost")}


def instance_ids(r: Round) -> set:
    return {i["proc_inst_id"] for i in r.get(f"{r.process}/api/instances?limit=100")}


def new_instance(r: Round, before: set, def_id: str | None, timeout: float) -> dict | None:
    def probe():
        for i in r.get(f"{r.process}/api/instances?limit=100"):
            if i["proc_inst_id"] not in before and (def_id is None or i["proc_def_id"] == def_id):
                return i
        return None
    return r.wait(timeout, probe, every=2)


def graph(r: Round, asset: str = "HYD-01") -> dict:
    return r.get(f"{r.agent}/api/ontology/graph?asset={asset}")


def engine_cards(r: Round, facts: dict) -> list[tuple[str, bool]]:
    """판단 엔진(규칙 — AI 아님)의 쿨러 카드: [(이름, 실행 가능)] 순위 순."""
    code, body = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": facts})
    if code != 200:
        raise HttpStatus(f"{r.agent}/api/agent/decide", code, body)
    opts = sorted((body.get("result") or body).get("options") or [], key=lambda o: o.get("rank") or 99)
    return [(o.get("name"), bool(o.get("feasible"))) for o in opts]


def start_knowledge(bundle: Path | None = None) -> dict[str, set[str]]:
    """시작 7단계(class_knowledge.ensure)가 넣는 수업 지식 — 서명 묶음 중 시작 문서(class_knowledge.ORDER)의 실행 절차 번호 · 고장 유형.
    실행 절차 = 고장 유형에 매칭(link.failureMode)되거나 구매 범위(link.scope)가 있고 조치(link.actions)가 있는 절차 — 참고 보관 절차는 뺀다."""
    from portal_names import start_documents
    sops, fms = set(), set()
    for d in start_documents(bundle):
        for p in d["proposal"]["procedures"]:
            link = p.get("link") or {}
            if (link.get("failureMode") or link.get("scope")) and link.get("actions"):
                sops.add(p["id"])
            if link.get("failureMode"):
                fms.add(link["failureMode"])
    return {"sop": sops, "fm": fms}


def expected_causes(g: dict, fault: str) -> set[str]:
    """주입한 외란 변수를 흔드는(DISTURBS) 원인 — 그래프에서 읽는다(정답을 도구에 적지 않는다)."""
    sv = FAULT_DISTURBANCE[fault]
    return {e["from"] for e in g["edges"] if e.get("type") == "DISTURBS" and e.get("to") == sv}


def ent(r: Round) -> dict:
    return r.get(f"{r.enterprise}/api/state")


def mail(r: Round, addr: str) -> list[dict]:
    q = urllib.parse.quote(f"to:{addr}")
    return (r.get(f"{r.inbucket}/api/v1/search?query={q}&limit=50") or {}).get("messages") or []


def routes(r: Round) -> dict:
    """경보 패턴 → {definition, version, source, class_flow} (GET /api/flows/deployments)."""
    return {x["pattern"]: x for x in r.get(f"{r.process}/api/flows/deployments").get("routes") or []}


def class_definition(r: Round, did: str) -> dict:
    route = next((x for x in r.get(f"{r.process}/api/flows/deployments").get("routes") or [] if x.get("definition") == did), {})
    return r.get(f"{r.process}/api/process/definitions/{did}?version={urllib.parse.quote(str(route.get('version') or '1'))}")


def plant_unit(r: Round, asset: str = "HYD-01") -> dict:
    return r.get(r.plant + "/api/state")["units"][asset]


def detector_phase(r: Round, asset: str = "HYD-01", pattern: str = "COOLER_DEGRADATION") -> str:
    patterns = r.get(r.detector + "/api/detector/state")["assets"][asset].get("patterns")
    if not isinstance(patterns, dict) or pattern not in patterns:
        raise RuntimeError(f"감지기 상태에 {asset} {pattern} 패턴이 없음 — /api/detector/state 모양이 바뀌었다")
    return patterns[pattern].get("phase") or "?"


def idle(r: Round, asset: str = "HYD-01") -> bool:
    u = plant_unit(r, asset)
    return u["tags"]["TS1"] < _IDLE_TS1 and float((u.get("disturbances") or {}).get("cooler_health", 1.0)) >= 0.999 and detector_phase(r, asset) == "IDLE"


def running_on(r: Round, asset: str) -> list[dict]:
    rows = r.get(f"{r.process}/api/instances?limit=50&status=RUNNING")
    return [i for i in rows if vars_of(view_of(r, i["proc_inst_id"])["instance"]).get("asset") == asset]


def confirm_ok(r: Round, timeout: float = 5) -> bool:
    """확인 창(ui.js UI.confirm — dialog.confirm-dialog)의 확인 단추를 누른다. 창이 뜨지 않았으면 False."""
    ok = r.page.locator("dialog.confirm-dialog[open] button[value=ok]")
    if not r.wait(timeout, lambda: ok.count() > 0, every=0.3):
        return False
    ok.first.click()
    return True


def select_instance(r: Round, pid: str) -> bool:
    """처리 건 목록에서 그 처리 건 카드(data-inst)를 누른다. 목록에 없으면 알림 링크와 같은 주소로 연다."""
    r.tab("instances")
    r.page.wait_for_selector("#instList", timeout=15_000)
    r.page.locator("#instReload").click()
    r.page.wait_for_timeout(1200)
    card = r.page.locator(f"#instList .inst-card[data-inst='{pid}']").first
    if card.count():
        card.click()
    else:
        r.page.evaluate("id => { location.hash = '#/instances/' + encodeURIComponent(id); }", pid)
    return bool(r.wait(15, lambda: pid in all_txt(r, "#instDetail"), every=0.5))


def open_task(r: Round, pid: str, task_id: str):
    """처리 건 화면 「내가 할 일」의 그 단계 줄(#todoList .item[data-todo-task] — instances.js renderTodo)을 누른다. 옛 「내 작업함」 화면은
    처리 건 화면으로 합쳐졌다(shell.js MOVED). 줄이 아직 없으면 같은 주소로 연다 — 알림 링크와 같은 길."""
    r.tab("instances")
    link = r.page.locator(f"#todoList .item[data-todo-task='{task_id}']")
    if r.wait(20, lambda: link.count() > 0, every=1):
        link.first.click()
    else:
        r.page.evaluate("h => { location.hash = h }", f"#/instances/{pid}/task/{task_id}")
    r.page.wait_for_selector("#todoPanel section.todo-panel", timeout=30_000)
    r.wait(30, lambda: "불러오는 중" not in r.page.locator("#todoPanel").inner_text(), every=0.5)
    r.page.wait_for_timeout(2500)        # 패널은 다음 갱신(2초)에 다시 그린다 — 그 뒤에 누른다


def panel_msg(r: Round) -> str:
    loc = r.page.locator("#todoPanel .form-actions .form-msg")
    return loc.first.inner_text().strip() if loc.count() else ""


def card_decide(r: Round, pid: str, task: dict, approve: bool, reason: str = "") -> tuple[bool, str]:
    """조치 카드 승인 패널에서 [승인] 또는 사유 + [반려](#tdRejectCard). 화면 글만 돌려준다(도구가 대신 채우지 않는다)."""
    open_task(r, pid, task["id"])
    if reason:
        r.page.fill("#tdReason", reason)
    if not approve:
        r.page.click("#tdRejectCard")
    else:
        go = r.page.locator("#tdGo")
        if go.is_disabled():
            return False, panel_msg(r)                                    # 안내 칸이 비면 빈 글 — 까닭 판정이 실패한다(패널 전체 글로 대신하지 않는다)
        go.click()
        r.page.wait_for_timeout(2500)
        if r.page.locator("#tdPreviewNow").count():                       # 「새 카드 검토가 필요」 — 화면이 [미리 보기]를 승인 옆에 꺼낸다
            r.page.click("#tdPreviewNow"); r.page.wait_for_timeout(4000)
            r.page.locator("#tdGo").click()
    done = r.wait(60, lambda: item_named(view_of(r, pid), task["activity_name"]).get("status") in ("DONE", "COMPLETED", "CANCELLED"), every=2)
    return bool(done), panel_msg(r)


def close_step(r: Round, pid: str, wid: str, reason: str) -> str:
    """처리 건 화면의 [단계 닫기](보류 · 멈춘 AI 단계) — 학생이 닫는 길. 닫는 사람은 화면이 담당자 id 를 숨은 칸에 싣는다(ui.js actorInput)."""
    if not select_instance(r, pid):
        raise ScreenMissing(f"처리 건 {pid} 를 열지 못함")
    # [단계 닫기]는 「진행 상황」 탭의 단계 줄에 있다(instances.js stepExtra). 처리 건 화면은 마지막에 고른 탭을 기억해(I.tab) 앞 실습이 연
    # 「처리 기록」 탭이면 단추가 숨어 있다(한바퀴3: 93 시간 초과) — 학생처럼 그 탭을 누른다
    r.page.locator("#instDetail [data-inst-tab='flow']").first.click(); r.page.wait_for_timeout(500)
    btn = r.page.locator(f"#instDetail [data-close-task='{wid}']").first
    if not r.wait(30, lambda: btn.count() > 0, every=1):
        raise ScreenMissing(f"[단계 닫기]가 없음({wid})")
    btn.click()
    who = r.page.locator("#instDetail [data-close-by]")               # 숨은 칸(type=hidden) — 화면이 담당자를 못 읽었으면 비어 있고 그 까닭 한 줄이 옆에 있다
    if who.input_value() != ME:
        raise ScreenMissing(f"[단계 닫기]의 담당자 칸이 담당자({ME})가 아님: {who.input_value()!r} · {txt(r, '#instDetail [data-pick-me]', 500)}")
    r.page.fill("#instDetail [data-close-reason]", reason)
    r.page.locator("#instDetail [data-close-go]").click()
    got = r.wait(30, lambda: next((w["status"] for w in view_of(r, pid)["workitems"] if w["id"] == wid and w["status"] in ("CANCELLED", "DONE")), None), every=2)
    return got or "닫히지 않음"


def unit_button(r: Round, asset: str, act: str) -> str:
    """[결함 시뮬레이션] 설비 카드의 버튼 → 결과 줄(#scenarioMsg)."""
    r.tab("scenario")
    r.page.wait_for_selector(f"#units .unit[data-asset='{asset}'] button[data-act='{act}']")
    before = r.page.locator("#scenarioMsg").inner_text()
    r.page.locator(f"#units .unit[data-asset='{asset}'] button[data-act='{act}']").first.click()
    if act == "biz-reset" and not confirm_ok(r):                          # [초기화]는 되돌릴 수 없어 화면이 먼저 묻는다(app.js — UI.confirm)
        raise ScreenMissing(f"{asset} [초기화]의 확인 창이 뜨지 않음")
    r.wait(30, lambda: (t := r.page.locator("#scenarioMsg").inner_text().strip()) and t != before and not t.endswith("보내는 중"), every=0.5)
    return r.page.locator("#scenarioMsg").inner_text().strip()


def reset_units(r: Round):
    """[전체 초기화] — 설비 3기를 정상 운전점으로. 되돌릴 수 없어 화면이 먼저 묻는다(app.js #btnReset — UI.confirm)."""
    r.tab("scenario")
    r.page.click("#btnReset")
    if not confirm_ok(r):
        raise ScreenMissing("[전체 초기화]의 확인 창이 뜨지 않음")
    r.page.wait_for_timeout(3000)


def biz_chip(r: Round, asset: str) -> str:
    r.tab("scenario")
    r.page.wait_for_timeout(2500)                                         # 시나리오 상태는 폴링으로 다시 읽힌다
    return r.page.locator(f"#units .unit[data-asset='{asset}'] .biz-alert").inner_text().strip()


# ---------------------------------------------------------------------- 쿨러 사건(A)
def degrade(r: Round) -> tuple[str | None, str]:
    """[쿨러 열화 주입] → 새 HYD-01 처리 건. (처리 건 id, 화면 안내)."""
    known = instance_ids(r)
    msg = unit_button(r, "HYD-01", "degrade")

    def opened():
        for i in r.get(f"{r.process}/api/instances?limit=100"):
            if i["proc_inst_id"] not in known and vars_of(view_of(r, i["proc_inst_id"])["instance"]).get("asset") == "HYD-01":
                return i["proc_inst_id"]
        return None
    return r.wait(SECONDS["instance"], opened, every=3), msg


def wait_agent(r: Round, pid: str) -> dict:
    """AI 판단(T_agent)이 끝날 때까지: 보류 · 승인 대기 · 실패(학생 문장) · 멈춤."""
    def probe():
        view = view_of(r, pid)
        rows = rows_of(view)
        ag, ap = rows.get("T_agent") or {}, rows.get("T_approve") or {}
        if ag.get("status") == "PENDING" and (ag.get("draft") or {}).get("_deferral"):
            return {"outcome": "보류", "view": view, "why": ag["draft"]["_deferral"].get("reason")}
        if ag.get("status") == "DONE" and ap.get("status") == "IN_PROGRESS":
            return {"outcome": "승인 대기", "view": view}
        failed = step_failure(view, ag)
        if failed:
            return {"outcome": "실패", "view": view, "why": failed}
        if view["instance"]["status"] != "RUNNING":
            return {"outcome": f"멈춤({ag.get('status')}/{view['instance']['status']})", "view": view}
        return None
    return r.wait(SECONDS["agent"], probe, every=3) or {"outcome": "시간 초과" + r.waited(), "view": view_of(r, pid)}


def agent_seconds(view: dict) -> float | None:
    """처리 건 시작 → AI 판단 끝(보류 기록 또는 승인 단계 시작)까지 실제 초."""
    f = lambda s: datetime.fromisoformat(str(s).replace("Z", "+00:00"))  # noqa: E731
    st = f(view["instance"]["start_date"])
    ev = [e for e in view.get("events") or [] if e.get("event_type") == "task_deferred"]
    if ev:
        return round((f(ev[-1]["timestamp"]) - st).total_seconds(), 1)
    ap, ag = rows_of(view).get("T_approve") or {}, rows_of(view).get("T_agent") or {}
    end = ag.get("end_date") or ap.get("start_date")
    return round((f(end) - st).total_seconds(), 1) if end else None


def restore_and_close(r: Round, pid: str | None) -> dict:
    """[쿨러 복구] → 처리 건이 닫히고 설비가 다음 주입을 받을 상태가 되기를 기다린다."""
    msg = unit_button(r, "HYD-01", "restore")
    closed = None
    if pid:
        closed = r.wait(SECONDS["close"], lambda: (lambda v: v if v["instance"]["status"] != "RUNNING" else None)(view_of(r, pid)), every=3)
    t0 = time.monotonic()
    ok = r.wait(SECONDS["idle"], lambda: idle(r), every=5)
    return {"msg": msg, "closed": closed, "idle": bool(ok), "idle_s": round(time.monotonic() - t0, 1)}


def ensure_idle(r: Round) -> bool:
    """앞 실습이 남긴 HYD-01 처리 건 · 경보가 있으면 화면의 [쿨러 복구]로 정리하고 대기 상태를 기다린다(학생이 따라붙는 길)."""
    if not running_on(r, "HYD-01") and idle(r):
        return True
    for i in running_on(r, "HYD-01"):
        restore_and_close(r, i["proc_inst_id"])
    return bool(r.wait(SECONDS["idle"], lambda: idle(r), every=5))


def a_case(r: Round) -> tuple[str | None, dict]:
    """쿨러 열화 한 건을 승인 대기(또는 멈춤)까지 — 이 실습들이 같이 쓴다. (처리 건, wait_agent 결과)."""
    if not ensure_idle(r):
        return None, {"outcome": "앞 처리 건 · 경보가 정리되지 않아 주입하지 못함"}
    pid, msg = degrade(r)
    if not pid:
        return None, {"outcome": f"[쿨러 열화] 뒤 처리 건이 열리지 않음: {msg}"}
    return pid, wait_agent(r, pid)


def a_content(r: Round, view: dict, dec: dict, label: str, axis: str = AXES[0]):
    """A 판단 내용: 원인 = 주입한 외란을 흔드는 원인(그래프), 카드 구조 · 승인 역할 = 원문(HM-8)."""
    cause = vars_of(view["instance"]).get("cause")
    want = expected_causes(graph(r), "cooler_degradation")
    r.check(f"{label}: AI가 고른 원인이 주입한 쿨러 핀 오염과 같다(그래프 DISTURBS sv:fouling)", cause in want, f"AI {cause} · 기대 {sorted(want)}",
            kind="quality", axis=axis)
    bad = card_findings(dec, approvers_of("HM-8"))
    r.check(f"{label}: 추천 = 실행 가능한 1순위 · 제외 카드에 규칙 · 카드 승인 역할 = 원문 「승인:」", not bad, "; ".join(bad) or json.dumps(card_summary(dec), ensure_ascii=False)[:300],
            kind="quality", axis=axis)


# ---------------------------------------------------------------------- 지식 관리(매뉴얼)
_NEG = ("않", "금지", "아니면", "뒤에만", "에만", "이내", "미만", "이하", "이상", "넘으면")
_UNIT = re.compile(r"℃|%|mm/s|mm|bar|l/min|분|시간|만 원|명|개|h\b")


def step_findings(src_step: str, got: str) -> list[str]:
    """원문 단계 vs 추출 단계: 부정 조건 · 수치 · 단위가 빠졌으면 그 종류(빈 목록 = 맞음)."""
    bad = [f"부정·제한 조건 '{w}' 빠짐" for w in _NEG if w in src_step and w not in got]
    bad += [f"수치 {n} 빠짐" for n in re.findall(r"\d+(?:[.,]\d+)?", src_step) if n not in got]
    bad += [f"단위 {u} 빠짐" for u in set(_UNIT.findall(src_step)) if u not in got]
    return bad


def extraction_quality(src: dict, preview: dict) -> list[dict]:
    """추출 제안을 원문과 대조: 누락 SOP · 원문에 없는 SOP · 단계 수 · 순서 · 부정 조건 · 수치 · 단위. 기준은 원문 파일 자체."""
    from difflib import SequenceMatcher
    found = []
    got = {p["id"]: p for p in preview.get("procedures") or []}
    found += [{"sop": sop, "order": None, "kind": "누락 절차"} for sop in src if sop not in got]
    for sop, p in got.items():
        if sop not in src:
            # 번호 없는 절의 업무 절차(예: PM-2.9 → SOP-PM-2-9)는 추출 지시 범위다
            if p.get("section") and re.sub(r"[^A-Z0-9]", "", sop) == "SOP" + re.sub(r"[^A-Z0-9]", "", str(p["section"]).upper()):
                continue
            found.append({"sop": sop, "order": None, "kind": "원문 SOP 목록에 없는 절차(오추출 후보)"})
            continue
        want = src[sop]["steps"]
        steps = sorted(p.get("steps") or [], key=lambda s: s.get("order") or 0)
        if len(steps) != len(want):
            found.append({"sop": sop, "order": None, "kind": f"단계 수 {len(steps)} ≠ 원문 {len(want)}"})
        starts = [((s.get("anchor") or {}).get("page"), (s.get("anchor") or {}).get("start")) for s in steps]
        if all(x[1] is not None for x in starts) and starts != sorted(starts):
            found.append({"sop": sop, "order": None, "kind": "단계 순서가 원문 위치 순서와 다름"})
        for i, s in enumerate(steps):
            text = s.get("text") or ""
            best = max(range(len(want)), key=lambda j: SequenceMatcher(None, want[j], text).ratio()) if want else None
            if best is not None and best != i and SequenceMatcher(None, want[best], text).ratio() > 0.8:
                found.append({"sop": sop, "order": s.get("order"), "kind": f"단계 순서 바뀜(원문 {best + 1}번 문장)", "source": want[best]})
            if i < len(want):
                found += [{"sop": sop, "order": s.get("order"), "kind": why, "source": want[i]} for why in step_findings(want[i], text)]
    return found


def preview_summary(preview: dict) -> dict:
    k = preview.get("knowledge") or {}
    rules = k.get("rules") or []
    links = {p["id"]: (preview.get("links") or {}).get(p["id"], p.get("link") or {}) for p in preview.get("procedures") or []}
    return {"procedures": sorted(links), "steps": {p["id"]: len(p.get("steps") or []) for p in preview.get("procedures") or []},
            "failure_modes": sorted(x.get("id") for x in k.get("failure_modes") or []), "causes": sorted(x.get("id") for x in k.get("causes") or []),
            "rules": sorted(x.get("id") for x in rules),
            "candidate_outputs": sorted({o for x in rules if x.get("table") == "dt:action-candidates" and x.get("effect") == "SELECT" for o in x.get("outputs") or []}),
            "links_fm": {s: (l or {}).get("failureMode") for s, l in sorted(links.items())}}


def current_batch(r: Round, key: str) -> dict | None:
    cur = [u for u in r.get(f"{r.process}/api/kg/manuals") if u.get("current") and u.get("filename") == DOCS[key]]
    return cur[0] if cur else None


def preview_file(r: Round, key: str) -> str | None:
    """지식 관리 → 파일 선택 → (이미 적재된 같은 문서면 「문서 개정」) → [문서 등록]. 원문 판본 id(화면의 보관 원본 링크)."""
    page = r.page
    r.tab("knowledge")
    opts = page.locator("#manualDocumentId option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])")
    rev = [v for v, t in opts if v and DOCS[key] in t and "문서 개정" in t]
    if rev:
        # 학생 길: 등록된 매뉴얼 카드의 [이 문서 개정]. 앞 미리보기가 화면에 남아 있으면 「등록할 문서」 칸은 잠겨 있고(hitl.js renderPreview),
        # 같은 파일을 다시 골라도 브라우저는 change 를 내지 않아 풀리지 않는다 — 칸을 직접 고르지 않는다(한바퀴3: 잠긴 칸에 select_option 시간 초과)
        page.locator(f"#manualHistory [data-manual-revise='{rev[0]}']").first.click()
    page.set_input_files("#manualFile", str(SAMPLES / DOCS[key]))
    page.click("#manualPreview")
    page.wait_for_selector("#manualResult .mprev, #manualResult .neg", timeout=60_000)
    if page.locator("#manualResult .neg").count():
        return None
    href = page.locator("#manualResult a[href*='/original']").first.get_attribute("href") or ""
    m = re.search(r"/sources/([^/]+)/original", href)
    return urllib.parse.unquote(m.group(1)) if m else None


def extraction(r: Round, sid: str, inst: str) -> tuple[int, dict]:
    q = lambda s: urllib.parse.quote(s, safe="")                          # noqa: E731
    return r.api("GET", f"{r.process}/api/kg/manuals/sources/{q(sid)}/extractions/{q(inst)}", timeout=60)


def run_extraction(r: Round, key: str, sid: str) -> dict:
    """[AI 추출 시작] → 끝나면 화면이 스스로 검토 단계(③)를 연다(hitl.js openResult — 3초마다 확인). 요약 · 원문 대조 · 출처(캐시 · AI)를 돌려준다."""
    page = r.page
    t0 = time.monotonic()
    # 누르면 화면은 「AI 추출을 요청하는 중…」을 보이고, 접수되면 그 추출 작업 id 를 이 브라우저의 요청 기록에 적는다(hitl.js #manualAgentExtract · extractionKey).
    # 접수하지 못하면 「AI 추출을 시작하지 못했습니다: …」로 바뀐다
    requested = "sid => (JSON.parse(sessionStorage.getItem('hyd.manual.extraction.' + sid) || 'null') || {}).instance || ''"
    status = lambda: txt(r, "#manualAgentStatus")                          # noqa: E731
    page.click("#manualAgentExtract")
    r.wait(60, lambda: "요청하는 중" not in status() and (page.evaluate(requested, sid) or "시작하지 못했습니다" in status()), every=1)
    accepted = status()
    inst = page.evaluate(requested, sid)
    if not inst or "시작하지 못했습니다" in accepted:
        return {"seconds": round(time.monotonic() - t0, 1), "instance": inst, "error": f"AI 추출이 접수되지 않음: {accepted}", "accepted": accepted}

    def done():
        code, body = extraction(r, sid, inst)
        if code == 200 and (body.get("preview") or body.get("status") in ("FAILED", "CANCELLED")):
            return body
        return None
    body = r.wait(1800, done, every=10) or {}
    seconds = round(time.monotonic() - t0, 1)
    if not body.get("preview"):
        return {"seconds": seconds, "instance": inst, "error": f"추출이 끝나지 않음: 상태 {body.get('status')} · {str(body.get('log') or '')[:200]}{r.waited()}",
                "accepted": accepted}
    page.wait_for_timeout(4000)                                           # 화면의 다음 확인(3초 주기)이 새 결과로 다시 그릴 시간 — 앞 결과 화면을 새 결과로 읽지 않는다
    if not r.wait(60, lambda: page.locator("#manualCommit").count() > 0 and "AI 추출 결과" in status(), every=1):
        return {"seconds": seconds, "instance": inst, "error": f"추출은 끝났는데 화면이 검토 단계로 넘어가지 않음: {status()}", "accepted": accepted}
    return {"seconds": seconds, "instance": inst, "accepted": accepted, "cache": body.get("cache") or {},
            "corrections": (body.get("corrections") or {}).get("attempts") or 0, **preview_summary(body["preview"]),
            "quality": [f"{f['sop']}#{f['order'] or '-'} {f['kind']}" for f in extraction_quality(source_doc(key), body["preview"])]}


def apply_review(r: Round, key: str, preview_body: dict) -> list[str]:
    """학생의 원문 대조 검토: 원문과 다른 단계는 원문 문장으로, 원문 SOP 목록에 없는 절차는 참고 보관 · 실행 후보 제외로, 빈 필수 선택은 원문 값으로."""
    page = r.page
    text = (SAMPLES / DOCS[key]).read_text(encoding="utf-8")
    src = source_procedures(text)
    phrases = [m.group(1).strip() for m in re.finditer(r"([가-힣][가-힣 ]{3,30}?)(?:은|는) [가-힣A-Z0-9 ]{1,20}에서 생기", text)]
    done = []
    # 절차마다 수정 칸은 「연결 · 단계 수정」에 접혀 있다(hitl.js renderPreview — details.mproc-edit) — 학생처럼 펼친 뒤 고친다(접힌 칸은 누를 수 없다)
    for fold in page.locator("#manualResult details.mproc-edit").all():
        open_fold(fold)
    for f in extraction_quality(src, preview_body):
        if f.get("order") and f.get("source"):
            ta = page.locator(f"textarea[data-manual-step='{f['sop']}'][data-order='{f['order']}']")
            if ta.count():
                ta.fill(f["source"]); done.append(f"수정 {f['sop']}#{f['order']}: {f['kind']}")
        elif f["kind"].startswith("원문 SOP 목록에 없는"):
            kind = page.locator(f"select[data-kind='{f['sop']}']")
            if kind.count():
                kind.select_option("reference")
                page.select_option(f"select[data-reference-executable='{f['sop']}']", "false")
                done.append(f"제외 {f['sop']}")
    for sel in page.locator("select[data-fm]:not([disabled])").all():
        sop = sel.get_attribute("data-fm")
        scope = page.locator(f"select[data-manual-scope='{sop}']")
        if scope.count() and scope.input_value() == "purchase":
            continue
        cur = sel.input_value()
        opts = sel.locator("option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])")
        good = [v for v, t in opts if v and max((len(set(p.split()) & set(t.replace("(", " ").split())) for p in phrases), default=0) >= 2]
        if not cur and good:
            sel.select_option(good[0]); done.append(f"고장 유형 선택 {sop}")
        elif cur and good and cur not in good:
            r.check(f"{key} {sop} AI 연결 고장 유형이 원문 고장 유형과 같다", False, f"AI {cur} · 원문 {phrases}", kind="quality")
            sel.select_option(good[0]); done.append(f"고장 유형 교정 {sop}")
    for sel in page.locator("select[data-manual-executable]").all():
        sop = sel.get_attribute("data-manual-executable")
        if page.locator(f"[data-purchase-fields='{sop}']").is_hidden():
            continue
        if not sel.input_value():
            r.check(f"{key} {sop} AI가 구매 절차 사용 방식을 채웠다", False, "비어 있어 학생이 원문으로 고름", kind="quality")
            sel.select_option("true" if "발주서" in " ".join((src.get(sop) or {}).get("steps") or []) else "false")
        appr = page.locator(f"select[data-manual-approver='{sop}']")
        want = (src.get(sop) or {}).get("approver")
        if appr.count() and not appr.input_value() and want and sel.input_value() == "true":
            opt = [v for v, t in appr.locator("option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])") if v and t.strip() == want]
            if opt:
                appr.select_option(opt[0]); done.append(f"승인 역할 {sop}: 원문 「승인: {want}」")
        parts = page.locator(f"select[data-manual-parts='{sop}']")
        if parts.count() and not parts.evaluate("s => s.selectedOptions.length"):
            r.check(f"{key} {sop} AI가 구매 대상 부품을 채웠다", False, "원문 PR-7.1 표를 보고 학생이 고르는 칸", kind="quality")
    return done


def commit_manual(r: Round, key: str) -> tuple[bool, str]:
    page = r.page
    page.check("#manualReviewed")
    page.click("#manualCommit")
    ended = ("적재 완료", "적재하지 못했습니다")                              # hitl.js manualCommit — 완료 · 서버 거절 문구
    r.wait(90, lambda: page.locator('.confirm-dialog[open]').count() or page.locator("#manualMsg").inner_text().startswith(ended), every=1)
    dialog = page.locator('.confirm-dialog[open]')
    if dialog.count():
        text = dialog.inner_text()
        lost = any(label in text for label in ('조치 방법:', '고장 유형:', '원인:', '진단 근거:', '판단 규칙:', '절차 단계:'))
        r.check(f"{key} 개정 삭제 목록 — 기존 업무 지식 누락 없음", not lost, text, kind="quality", axis=AXES[3])
        dialog.locator('button[value="cancel"]' if lost else 'button[value="ok"]').click()
        if lost:
            return False, '개정 누락을 확인해 적재하지 않음: ' + text
    r.wait(90, lambda: page.locator("#manualMsg").inner_text().startswith(ended), every=1)
    msg = page.locator("#manualMsg").inner_text().strip()
    return msg.startswith("적재 완료"), msg


def ingest_manual(r: Round, key: str, label: str) -> dict | None:
    """제공 문서 한 벌: 문서 등록 → AI 추출(강사 검토 캐시) → 원문 대조 → 검토 → 적재. 실패는 판정으로 남기고 None."""
    sid = preview_file(r, key)
    r.check(f"{label}: {key} 제공 원문 [문서 등록]", bool(sid), txt(r, "#manualResult"))
    if not sid:
        return None
    got = run_extraction(r, key, sid)
    r.check(f"{label}: {key} 추출 제안을 받는다", not got.get("error"), got.get("error") or f"{got.get('seconds')}초")
    if got.get("error"):
        return None
    r.check(f"{label}: 추출 제안이 원문과 맞는다(절차 · 순서 · 조건 · 수치 · 단위)", not got["quality"], str(got["quality"]), kind="quality")
    # ③: 제공 문서는 키와 상관없이 강사 서명 묶음에서 나온다(AI 호출 없음) — 두 모드 모두 재는 축
    r.check(f"{label}: 제공 문서 추출은 강사 검토 캐시에서(AI 없이 — 키 없는 PC에서도 막히지 않음)", bool((got.get("cache") or {}).get("key")),
            json.dumps(got.get("cache"), ensure_ascii=False)[:200], kind="exception", axis=AXES[2])
    proposal = extraction(r, sid, got["instance"])[1].get("preview") or {}
    apply_review(r, key, proposal)
    committed, message = commit_manual(r, key)
    r.check(f"{label}: 검토한 제안을 적재(새 판본)", committed, message)
    return got if committed else None


def onto_stats(r: Round) -> str:
    r.tab("ontology")
    r.page.click("#ontoReload")
    r.wait(20, lambda: "항목" in r.page.locator("#ontoStats").inner_text(), every=1)
    return r.page.locator("#ontoStats").inner_text()


def label_counts(g: dict) -> dict:
    out: dict = {}
    for n in g["nodes"]:
        out[n["label"]] = out.get(n["label"], 0) + 1
    return out


# ---------------------------------------------------------------------- 에이전트 · 질문
def agents(r: Round) -> list[dict]:
    return r.get(f"{r.process}/api/agents")


def agent_form(r: Round, *, name=None, role=None, goal=None, persona=None, tools=None) -> str:
    """열린 에이전트 폼을 채우고 저장한다. 폼 오류 문구(없으면 '')."""
    page = r.page
    form = page.locator("[data-ag-form]")
    form.wait_for(timeout=10_000)
    for key, val in (("name", name), ("role", role), ("goal", goal), ("persona", persona)):
        if val is not None:
            form.locator(f"[data-f='{key}']").fill(val)
    if tools is not None:
        for box in form.locator("input[data-f-tool]").all():
            if box.is_checked() != (box.get_attribute("value") in tools):
                box.click()
    page.evaluate("() => document.querySelectorAll('#toaster .toast').forEach(n => n.remove())")
    page.evaluate("() => document.querySelectorAll('[data-ag-detail] .form-msg.neg').forEach(n => { n.textContent = ''; n.classList.remove('neg'); })")
    form.locator("button[type=submit]").click()
    r.wait(15, lambda: page.locator("[data-ag-form]").count() == 0 or page.locator("[data-ag-detail] .form-msg.neg").count(), every=0.5)
    err = page.locator("[data-ag-detail] .form-msg.neg")
    return err.first.inner_text().strip() if err.count() else ""


MY_PROFILE = dict(name=MY_AGENT, role="쿨러 열화 경보를 먼저 보는 점검 담당",
                  goal="쿨러 과열 경보 한 건에 대해 지식 그래프의 원인 · 조치 절차와 센서 기록을 찾아 정리하고, HM-8 매뉴얼 규칙을 지키는 조치 후보 3개를 "
                       "순위와 함께 제안한다. 승인 전에는 조회 · 계산 · 요약만 한다.",
                  persona="근거(조회한 도구와 값)를 먼저 말한다. 조회해서 나오지 않으면 지어내지 않고 모른다고 한다.",
                  tools=["neo4j", "hyd-dmn"])


def my_agent(r: Round) -> dict | None:
    return next((a for a in agents(r) if a.get("name") == MY_AGENT and a.get("origin") == "user"), None)


def ensure_my_agent(r: Round) -> dict | None:
    """5회차에 만든 나의 에이전트 — 없으면(이 실습만 돌릴 때) 화면에서 같은 설정으로 만든다."""
    mine = my_agent(r)
    if mine:
        return mine
    r.tab("agents")
    r.wait(15, lambda: r.page.locator("[data-new-agent]").count(), every=1)
    r.page.click("[data-new-agent]")
    err = agent_form(r, **MY_PROFILE)
    r.check("앞 실습의 나의 에이전트가 없어 같은 설정으로 만든다", not err, err)
    return my_agent(r)


def ask(r: Round, agent_id: str, question: str) -> dict:
    """에이전트에게 질문: 답할 에이전트 → 질문 → 보내기 → 끝날 때까지 → 화면 답 · 근거 · 호출 기록 + 서버 판정 + 실행 출처."""
    page = r.page
    r.tab("ask")
    r.wait(15, lambda: page.locator(f"#askAgent option[value='{agent_id}']").count(), every=1)
    page.select_option("#askAgent", agent_id)
    page.fill("#askText", question)
    seen = set(page.locator(".ask-a a[href^='#/instances/']").evaluate_all("as => as.map(a => a.getAttribute('href'))"))
    t0 = time.monotonic()
    page.click("#askSend")
    href = r.wait(60, lambda: next((h for h in page.locator(".ask-a a[href^='#/instances/']").evaluate_all("as => as.map(a => a.getAttribute('href'))")
                                    if h not in seen), None), every=0.5) or ""
    pid = href.split("/")[2] if href.count("/") >= 2 else ""
    if not pid:
        return {"seconds": round(time.monotonic() - t0, 1), "error": f"질문이 접수되지 않음: {txt(r, '#askMsg') or txt(r, '[data-ask-form]')[:200]}"}
    view = r.wait(ASK_LIMIT_S + 60, lambda: (lambda v: v if v.get("state") in ASK_END else None)(r.get(f"{r.process}/api/ask/{pid}")), every=3) or {}
    seconds = round(time.monotonic() - t0, 1)
    page.wait_for_timeout(2500)                                           # 화면 폴링(1.5초)이 끝난 상태를 그릴 시간
    res = view.get("result") or {}
    calls = view.get("tool_calls") or []
    answer = res.get("answer") or res.get("claimed") or ""
    inst = view_of(r, pid)
    w = next((x for x in inst["workitems"] if x.get("agent_mode")), {})
    box = page.locator(f".ask-a:has(a[href='{href}'])").first
    return {"seconds": seconds, "id": pid, "state": view.get("state"), "message": view.get("message"), "ai": ai_source(session_of(w)),
            "kind": res.get("kind"), "verified": res.get("verified") or 0, "verified_ok": bool(res.get("verified")),
            "sop_ids": sorted(set(re.findall(r"SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*", answer))),
            "tools": sorted({str(c.get("raw_tool") or c.get("tool")) for c in calls if c.get("ok") and c.get("data")}),
            "calls": len(calls), "answer": answer, "reason": res.get("reason"), "tool_calls": calls,
            "screen": box.inner_text()[-1500:] if href and box.count() else ""}


def known_roles(r: Round) -> set[str]:
    return {n["name"] for n in graph(r)["nodes"] if n["label"] == "Role" and n.get("name")}


# ====================================================================== 01 통합 9 · 실전 9
def header_health(r: Round) -> tuple[int, int, str, str]:
    text = txt(r, "#healthDots")
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    dot = r.page.locator("#healthDots .dot").first.get_attribute("class") if r.page.locator("#healthDots .dot").count() else ""
    return (int(m.group(1)), int(m.group(2)), dot or "", text) if m else (-1, -1, dot or "", text)


@lab("01", [("통합", "실습 환경을 시작하고 HYD 포털 둘러보기"), ("실전", "실습 환경을 시작하고 HYD 포털 둘러보기")])
def lab_01_runtime(r: Round):
    rows = resolve_rows(r, "01")
    r.tab("main")
    got = r.wait(15, lambda: (lambda h: h if h[1] > 0 and h[0] == h[1] else None)(header_health(r)), every=1)
    up, total, dot, text = got or header_health(r)
    r.check("홈 상단 상태 점이 모두 초록(서비스 n/n)", bool(got) and "up" in dot, text)
    r.wait(15, lambda: re.search(r"지식 항목\s*[\d,]+", txt(r, "#mainStats").replace("\n", " ")), every=1)
    stats = txt(r, "#mainStats", required=True)
    m = re.search(r"지식 항목\s*([\d,]+)\s*연결\s*([\d,]+)", stats.replace("\n", " "))
    g = graph(r)
    r.check("홈 요약 카드: 설비 3기 · 시간 배율 20× · 지식 항목 · 연결 = 지식 지도 API", re.search(r"(?<!\d)3기", stats) is not None and "20×" in stats and bool(m)
            and (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) == (len(g["nodes"]), len(g["edges"])),
            f"{stats.replace(chr(10), ' ')[:160]} / API {(len(g['nodes']), len(g['edges']))}")
    scale = r.get(r.plant + "/api/state").get("time_scale")
    shown = all_txt(r, "#scale").strip()
    r.check("시간 배율 20배(화면 · 설비 API 같음)", shown == "20" and float(scale) == 20.0, f"화면 {shown} · API {scale}")
    r.wait(15, lambda: "불러오는 중" not in all_txt(r, "#mLive"), every=1)
    live = all_txt(r, "#mLive")              # 홈 도식의 SVG <text> — HTML 요소가 아니라 inner_text 로는 못 읽는다(한바퀴3: Node is not an HTMLElement)
    r.check("홈 도식의 실시간 유온 줄이 세 설비 값을 보인다", all(a in live for a in ("HYD-01", "HYD-02", "HYD-03")), live[:160])
    # 왼쪽 메뉴: 실라버스 문장이 말한 수만큼 있다(2026-11-14 구조 개편 뒤 메뉴 줄에는 묶음 이름이 아니라 메뉴 여덟이 있다 — 실라버스 문장이 옛 묶음 수면 여기서 드러난다)
    want = menu_group_count((rows.get("통합") or (0, "", "", ""))[3])
    groups = r.page.locator("#menuList [data-menu]").all_inner_texts()
    r.check(f"왼쪽 메뉴의 수가 실라버스 문장의 수({want})와 같다", want is not None and len(groups) == want, f"메뉴 {groups}")
    r.page.locator("#mainArch").click()
    r.page.wait_for_selector("#stack .comp", timeout=10_000)
    r.page.wait_for_timeout(6000)                                         # 상태 점은 pollHealth 가 채운다(5초 주기)
    # 구조 그림의 부품 상자(SVG): data-st = ok · down · wait · opt(선택 도구) · none(상태를 재지 않는 부품), 이름과 하는 일은 <title>(app.js renderStack)
    comps = r.page.eval_on_selector_all("#stack .comp", "cs => cs.map(c => ({st: c.dataset.st, text: c.querySelector('title').textContent}))")
    checked = [c for c in comps if c["st"] in ("ok", "down", "wait")]
    down = [c["text"][:40] for c in checked if c["st"] != "ok"]
    r.check("시스템 구성: 응답 확인 대상이 모두 초록 · 수 = 상단 「서비스 n/n」", bool(checked) and not down and len(checked) == total, f"확인 {len(checked)} · 상단 {total} · 꺼짐 {down}")
    opt = [c["text"][:40] for c in comps if c["st"] == "opt"]
    r.check("시스템 구성의 선택 도구는 빨간 점(down)이 아니라 선택 도구(점선 상자)로 표시", bool(opt) and "선택 도구" in txt(r, "#view-home .sys-bar"),
            "; ".join(opt), kind="quality")
    status = r.get(r.process + "/api/agents/status")
    shown_worker = "AI 에이전트 실행 서비스" in all_txt(r, "#view-main") + all_txt(r, "#view-home") + text          # layers.js agent-worker 칸의 설명
    r.check("홈 · 시스템 구성 화면에 「AI 에이전트 실행 서비스」 칸이 있다", shown_worker, f"워커 연결 {status.get('reachable')}", kind="quality")
    # 예외(실제로 끄지 않는다): 브라우저 안에서만 설비 시뮬레이터 응답을 막아 「서비스 하나가 꺼진 홈」을 본다(이 탭 요청만)
    code, r.lab = r.lab, f"{r.lab}~모의"
    r.tags[r.lab] = r.tags[code]
    seen: dict = {}
    pattern = re.compile(r".*(/svc/plant-sim|:" + str(urllib.parse.urlparse(r.plant).port) + r")/(healthz|api/state).*")
    try:
        r.page.route(pattern, lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"Not Found"}'))
        r.tab("main")
        seen["header"] = r.wait(20, lambda: (lambda h: h if 0 <= h[0] < h[1] else None)(header_health(r)), every=1)
        r.page.wait_for_timeout(2500)
        seen["stats"] = txt(r, "#mainStats")
        r.tab("scenario")
        r.page.wait_for_timeout(1500)
        seen["scenario"] = txt(r, "#units")
    finally:
        r.page.unroute(pattern)
    r.tab("main")
    back = r.wait(25, lambda: (lambda h: h if h[1] > 0 and h[0] == h[1] else None)(header_health(r)), every=1)
    r.page.wait_for_timeout(1500)
    seen["stats_back"] = txt(r, "#mainStats")
    r.logs.pop(r.lab, None)
    r.lab = code
    h = seen.get("header")
    r.check("(모의) 설비가 꺼지면 상단이 「응답 없음: plant-sim」", bool(h) and "응답 없음" in h[3] and "plant" in h[3] and "down" in h[2], h[3] if h else "상태 점이 바뀌지 않음",
            kind="exception", axis=AXES[1])
    r.human("(모의) 홈 요약이 한국어로 「설비 연결 끊김」과 다시 연결 안내", seen.get("stats", ""), "끊김" in seen.get("stats", "") and "연결되면" in seen.get("stats", ""))
    r.check("(모의) 결함 시뮬레이션 화면도 연결 불가를 한국어로 안내", "연결할 수 없습니다" in seen.get("scenario", ""), seen.get("scenario", "")[:160], kind="exception", axis=AXES[1])
    r.check("(모의) 응답이 돌아오면 새로 고침 없이 상단 n/n · 요약에 설비 3기", bool(back) and re.search(r"(?<!\d)3기", seen.get("stats_back", "")) is not None, seen.get("stats_back", "")[:120],
            kind="exception", axis=AXES[3])
    r.keyless("키 없는 PC: AI 에이전트 실행 서비스 상태 API가 「닿음 · 오류 없음」(키가 없어도 꺼진 것으로 나오지 않음)", bool(status.get("reachable")) and not status.get("error"), json.dumps(status, ensure_ascii=False)[:200])


# ====================================================================== 02 통합 10 · 실전 10
def a_once(r: Round, i: int, mode: str) -> dict:
    """쿨러 열화 한 번: 경보 → 처리 건 → AI 판단 → (mode: approve · reject · late) → 명령 · 재관측 · 작업지시 · 보고 → 쿨러 복구."""
    pid, got = a_case(r)
    if not pid:
        return {"error": got["outcome"]}
    view = got["view"]
    w = rows_of(view).get("T_agent") or {}
    out = {"pid": pid, "outcome": got["outcome"], "seconds": agent_seconds(view), "flow": view["instance"]["proc_def_id"], "ai": ai_source(session_of(w))}
    try:
        if got["outcome"] != "승인 대기":
            out["error"] = f"AI 판단이 승인 대기로 끝나지 않음: {got['outcome']} {got.get('why') or ''}"
            if got.get("why"):
                r.human("AI 판단이 멈추면 처리 건에 학생이 읽는 까닭", got["why"])
            return out
        dec = decision_of(r, view)
        card = card_summary(dec)
        out.update({k: card[k] for k in ("recommended", "approver", "evidence")})
        a_content(r, view, dec, f"A 판단 {i + 1}회")
        task = rows_of(view).get("T_approve") or {}
        if mode == "late":
            # 승인 지연 타이머는 사람 단계라 벽시계다 — 정의의 B_overdue · 엔진 규칙에서 기다릴 시간을 읽는다(20배속이 아니다)
            wait_s = timer_wait_s(view["definition"], "B_overdue", float(r.get(r.plant + "/api/state")["time_scale"]))
            open_task(r, pid, task["id"])
            shown = txt(r, "#todoPanel", required=True)
            m = re.search(r"지연 알림까지 (\d+)분", shown)
            r.check("승인 패널의 「지연 알림까지 n분」 = 정의의 승인 지연 기한(벽시계)", bool(m) and abs(int(m.group(1)) * 60 - wait_s) <= 120,
                    f"화면 {m.group(0) if m else '없음'} · 정의 {wait_s:.0f}초", axis=AXES[0])
            notice = r.wait(wait_s + 120, lambda: (rows_of(view_of(r, pid)).get("T_notice") or {}).get("status") in ("DONE", "COMPLETED"), every=10)
            v2 = view_of(r, pid)
            r.check("승인을 미루면 기한 뒤 「승인 지연 알림」이 나고 승인 단계는 그대로 기다린다", bool(notice) and (rows_of(v2).get("T_approve") or {}).get("status") == "IN_PROGRESS",
                    f"알림 {(rows_of(v2).get('T_notice') or {}).get('status')} · 승인 {(rows_of(v2).get('T_approve') or {}).get('status')} · 기다림 {wait_s:.0f}초",
                    kind="exception", axis=AXES[1])
            r.not_measure("카드 예측이 오래돼 [미리 보기] 뒤 승인", "카드 검토 유효시간은 벽시계 1800초(agentsvc/forecasting.py max_review_age_wall_s) — "
                          "한 바퀴에서 30분을 기다리지 않는다", axis=AXES[1])
        if not card.get("approver"):
            out["error"] = f"추천 카드의 승인 역할을 알 수 없음: {json.dumps(card, ensure_ascii=False)[:200]}"
            return out
        done, text = card_decide(r, pid, task, approve=(mode != "reject"), reason="생산 일정상 지금은 안 됩니다" if mode == "reject" else "")
        out["decided"] = done
        end = wait_end(r, pid, 600)
        rows = rows_of(end)
        out["end"] = end["instance"]["status"]
        if mode == "reject":
            r.check("[반려] → 결과 보고(반려) 단계가 끝나고 냉각 명령 단계(T_cmd)는 실행되지 않음", (rows.get("R_rejected") or {}).get("status") == "DONE" and (rows.get("T_cmd") or {}).get("status") != "DONE",
                    f"끝 {out['end']} · 반려 보고 {(rows.get('R_rejected') or {}).get('status')} · 명령 {(rows.get('T_cmd') or {}).get('status')}", kind="exception", axis=AXES[1])
        else:
            ok_end = any((rows.get(k) or {}).get("status") == "DONE" for k in ("R_ok", "R_fail"))
            r.check("승인 → 냉각 명령 단계 끝 · 결과 보고(정상 또는 미달) 단계 끝", ok_end and (rows.get("T_cmd") or {}).get("status") == "DONE",
                    f"끝 {out['end']} · 명령 {(rows.get('T_cmd') or {}).get('status')} · 정상 {(rows.get('R_ok') or {}).get('status')} · 미달 {(rows.get('R_fail') or {}).get('status')}")
            v = vars_of(end["instance"])
            wo = (v.get("work_order") or {}).get("ref")
            orders = [o for o in ent(r)["cmms"]["work_orders"] if o.get("id") == wo]
            r.check("따로 남은 정비 요청: 처리 건의 작업지시가 CMMS에 있고 아직 완료가 아니다(명령 · 회복과 정비 완료는 다른 단계)",
                    bool(wo) and len(orders) == 1 and orders[0].get("status") != "완료", f"{wo} · {json.dumps(orders, ensure_ascii=False)[:200]}")
            out["result"] = "정상" if (rows.get("R_ok") or {}).get("status") == "DONE" else "미달"
            if out["result"] == "정상":
                rep = v.get("result_report") or {}
                r.check("결과 보고 「정상」의 회복 판정(facts.recovered)이 처리 건의 재관측 결과(recovered)와 같이 참", (rep.get("facts") or {}).get("recovered") is True and v.get("recovered") is True,
                        json.dumps(rep.get("facts") or {}, ensure_ascii=False)[:200])
    finally:
        restore_and_close(r, pid)
    return out


@lab("02", [("통합", "설비 이상 발생부터 판단·승인·조치까지 전체 과정 경험하기"), ("실전", "설비 이상 발생부터 판단·승인·조치까지 전체 과정 경험하기")])
def lab_02_full_flow(r: Round):
    resolve_rows(r, "02")
    # 실라버스: 먼저 지식 관리에 설비 매뉴얼을 넣고(추출 · 원문 대조 · 적재) 쿨러 열화로 들어간다 — 시작이 이미 넣었으면 「문서 개정」이다
    ingest_manual(r, "HM-8", "매뉴얼 넣기")
    modes = ["approve", "reject", "late"]
    runs = r.repeat3("A 판단", lambda i: a_once(r, i, modes[i]), ("outcome", "recommended", "approver", "evidence"), limit_s=AGENT_LIMIT_S)
    r.memo["02_cards"] = runs


# ====================================================================== 03 통합 21 · 실전 21
def onto(r: Round, asset: str = "HYD-01") -> dict:
    r.tab("ontology")
    r.page.select_option("#ontoAsset", asset)
    r.wait(30, lambda: "항목" in txt(r, "#ontoStats"), every=1)
    g = graph(r, asset)
    return {"stats": txt(r, "#ontoStats"), "nodes": len(g["nodes"]), "edges": len(g["edges"]), "labels": label_counts(g), "graph": g}


@lab("03", [("통합", "설비 지식의 구조와 연결 관계 탐색하기"), ("실전", "기준 설비 지식의 실제 연결 구조 확인하기")])
def lab_03_ontology(r: Round):
    resolve_rows(r, "03")
    o = onto(r)
    m = re.search(r"항목\s*([\d,]+)\s*·\s*연결\s*([\d,]+)", o["stats"])
    r.check("지식 지도 숫자(항목 · 연결) = 그래프 API", bool(m) and (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) == (o["nodes"], o["edges"]),
            f"화면 {o['stats']} / API {o['nodes']}·{o['edges']}")
    r.memo["03_before"] = {k: o[k] for k in ("nodes", "edges", "labels")}
    r.page.locator("#ontoMap [data-id='asset:hyd-01']").first.click()
    r.page.wait_for_timeout(800)
    panel = txt(r, "#ontoNode", required=True)
    groups = r.page.locator("#ontoNode section.rel-group").count()        # 이어진 항목은 관계 이름 · 종류 이름 묶음으로 보인다(enterprise.js renderNodePanel)
    r.check("설비(HYD-01)를 누르면 종류 · 속성 · 이어진 항목 묶음(관계 이름마다)이 보인다", "HYD-01" in panel and groups > 0, f"묶음 {groups} · {panel[:300]}")
    ids = raw_ids(panel)
    r.evidence("설비 노드 설명에 남은 원문 id · 영문 상수", f"원문 id {ids}\n\n{panel}",
               "노드 자신의 id 줄처럼 의도한 표시와 학생이 못 읽는 찌꺼기를 도구가 가를 정본이 없다", axis=AXES[1])
    link = r.page.locator("#ontoNode [data-go]").first
    target = link.get_attribute("data-go")
    name = next((n["name"] for n in o["graph"]["nodes"] if n["id"] == target), None)
    link.click(); r.page.wait_for_timeout(800)
    after = txt(r, "#ontoNode")
    r.check("연결을 누르면 오른쪽 패널이 그 노드(이름)로 바뀐다", bool(name) and name in after and after != panel, f"{target} → {name} · 패널 {after[:80]}")
    # 실전 21: 한 부품을 사용하는 설비를 찾는다 — 화면 패널의 들어오는 연결과 그래프 API 가 같은가(연결이 있다 ≠ 재고가 있다)
    part = next((e["to"] for e in o["graph"]["edges"] if e["to"].startswith("part:") and e["type"] in ("USES_PART", "HAS_PART", "INVOLVES_PART")), None)
    if part:
        r.page.fill("#ontoSearch", next(n["name"] for n in o["graph"]["nodes"] if n["id"] == part))
        r.page.wait_for_timeout(800)
        r.page.locator(f"#ontoMap [data-id='{part}']").first.click(); r.page.wait_for_timeout(800)
        ptxt = txt(r, "#ontoNode")
        users = {n["name"] for e in o["graph"]["edges"] if e["to"] == part for n in o["graph"]["nodes"] if n["id"] == e["from"]}
        r.check("부품 노드에서 그 부품을 쓰는 쪽(들어오는 연결)이 그래프 API 와 같다", all(u in ptxt for u in users), f"{part} ← {sorted(users)} · 화면 {ptxt[:200]}")
        r.page.fill("#ontoSearch", "")
    else:
        r.check("그래프에 부품 연결이 있다", False, "HYD-01 지도에 part: 로 가는 연결 없음")
    r.page.fill("#ontoSearch", "없는설비XYZ")
    r.page.wait_for_timeout(800)
    st = txt(r, "#ontoStats")
    r.check("없는 이름을 검색하면 「검색 결과 0개」로 알린다", "검색 결과 0개" in st, st, kind="exception", axis=AXES[1])
    r.page.fill("#ontoSearch", "")
    o2 = onto(r)
    r.check("다시 열어도 같은 지도(항목 · 연결 수)", (o2["nodes"], o2["edges"]) == (o["nodes"], o["edges"]), f"{o['nodes']}·{o['edges']} → {o2['nodes']}·{o2['edges']}",
            axis=AXES[3])
    want = start_knowledge()
    listed = r.get(f"{r.process}/api/kg/skills")
    have_sop = {x.get("sopId") for x in listed}
    have_fm = {f["id"] for x in listed for f in x.get("failureModes") or []}
    lack = sorted(want["sop"] - have_sop) + sorted(want["fm"] - have_fm)
    r.check("시작 지식(서명 묶음 HM-8 · PM-02 · PR-07)의 실행 조치 방법 · 고장 유형이 조치 방법 목록에 모두 있다", not lack,
            f"빠짐 {lack}" if lack else f"조치 방법 {len(want['sop'])} · 고장 유형 {len(want['fm'])}")


# ====================================================================== 04 통합 31 · 실전 25 · 실전 32
def decide_screen(r: Round, **facts) -> str:
    r.tab("decision")
    r.wait(20, lambda: r.page.locator("#decPattern option").count() > 0, every=1)
    r.page.select_option("#decAsset", "HYD-01")
    r.page.select_option("#decPattern", "COOLER_DEGRADATION")
    r.page.select_option("#decMode", facts.get("mode", ""))
    r.page.select_option("#decState", facts.get("state", ""))
    r.page.select_option("#decStandby", facts.get("standby", ""))
    r.page.fill("#decFan", str(facts.get("fan", "")))
    r.page.click("#decRun")
    r.wait(120, lambda: not r.page.locator("#decRun").is_disabled(), every=1)
    r.page.wait_for_timeout(800)
    return txt(r, "#decResult", 5000, required=True)


@lab("04", [("통합", "운전 조건과 성과 기준에 따른 조치 결과 비교하기"), ("실전", "포털에서 절차와 판단 조건이 나뉘어 쓰이는 모습 확인하기"),
            ("실전", "운전 조건을 바꿔 조치의 우선순위와 성과 비교하기")])
def lab_04_rules_whatif_kpi(r: Round):
    resolve_rows(r, "04")
    ent_before = ent(r)
    graph_before = graph(r)
    # 조치 방법: 쿨러 조치의 수행 단계 · 담당 · 승인 역할 · 연결된 고장 유형 — 화면 = 지식 API = 원문 HM-8
    r.tab("skills")
    r.wait(20, lambda: r.page.locator("#skillList .row").count() > 0, every=1)
    skills = r.get(f"{r.process}/api/kg/skills")
    src = source_doc("HM-8")
    for sop in ("SOP-COOL-11", "SOP-COOL-14"):
        k = next((x for x in skills if x.get("sopId") == sop), None)
        if not k:
            r.check(f"조치 방법에 {sop} 가 있다", False, "지식 API 에 없음"); continue
        r.page.locator(f"#skillList .row[data-skill='{k['id']}']").first.click()
        r.page.wait_for_timeout(800)
        detail = txt(r, "#skillDetail", required=True)
        want = src.get(sop) or {}
        # 승인 역할: 문서에서 온 조치 방법은 「연결된 지식」의 이름–값 줄(승인 역할)에 글로 있고(고치는 폼이 없다), 화면에서 직접 더한 것만
        # 「이름 · 승인 역할 · 설명 고치기」 접기 안의 고르기 칸(#skRole)에 있다(hitl.js renderSkillDetail)
        fold = r.page.locator("#skillDetail details[data-skill-edit]")
        if fold.count():
            open_fold(fold.first)
            shown_role = r.page.locator("#skRole option:checked").inner_text().strip()
        else:
            shown_role = r.page.evaluate("() => { const dt = [...document.querySelectorAll('#skillDetail dl.kv dt')].find(x => x.textContent.trim() === '승인 역할'); return dt ? dt.nextElementSibling.textContent.trim() : ''; }")
        r.check(f"조치 방법 {sop}: 화면의 수행 단계 수 · 승인 역할 · 고장 유형 = 원문 · 지식", len(k.get("steps") or []) == len(want.get("steps") or [])
                and (k.get("approver") or {}).get("name") == want.get("approver") and shown_role == want.get("approver", "?")
                and all(f["name"] in detail for f in k.get("failureModes") or []) and all(s["text"][:15] in detail for s in k.get("steps") or []),
                f"원문 단계 {len(want.get('steps') or [])} · 승인 {want.get('approver')} / 지식 {len(k.get('steps') or [])} · {(k.get('approver') or {}).get('name')} / 화면 승인 역할 {shown_role} · {detail[:160]}")
    base = decide_screen(r)
    r.human("[모의 판단](현재 값) → 결과가 한국어로 보인다", base, axis=AXES[0], kind="normal")
    n_cards = r.page.locator("#decResult .opts tbody tr").count()      # 조치 후보는 표 한 장(UI.optionsTable)의 줄이다 — 옛 조치 카드(.hitl-opts)는 없어졌다
    api = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {}})[1] or {}
    api_n = len(((api.get("result") or api).get("options")) or [])
    r.check("조치 후보 카드 수 = 판단 엔진 결과(입력 · 적용 규칙 · 후보)", n_cards > 0 and n_cards == api_n, f"화면 {n_cards} · 엔진 {api_n}")
    again = decide_screen(r)
    # 예측값 · 시각은 설비 상태에 따라 움직이므로 숫자만 빼고 화면 전체 글을 견준다(앞부분만 보지 않는다)
    r.check("같은 입력으로 다시 실행하면 화면 결과가 숫자 말고 글자까지 같다(카드 · 순서 · 규칙)", re.sub(r"\d", "", again) == re.sub(r"\d", "", base), again[:200], axis=AXES[3])
    trip = decide_screen(r, state="TRIP")
    eng0 = engine_cards(r, {})
    eng_trip = engine_cards(r, {"plc_state": "TRIP"})
    if eng_trip != eng0:
        gone = [name for name, ok in eng_trip if not ok and (name, True) in eng0]
        r.check("설비 상태 「보호 정지」 → 판단 엔진이 바뀐 결과를 내고 화면도 바뀌며, 새로 제외된 카드 이름이 화면에 있다",
                re.sub(r"\d", "", trip) != re.sub(r"\d", "", base) and all(n in trip for n in gone), f"엔진 새 제외 {gone} · 화면 {trip[:200]}",
                kind="exception", axis=AXES[1])
    else:
        r.check("설비 상태 「보호 정지」 → 판단 엔진 결과가 같으면 화면이 「결과에 영향이 없습니다」로 알린다", "결과에 영향이 없습니다" in trip, trip[:300],
                kind="exception", axis=AXES[1])
    manual = decide_screen(r, mode="REMOTE_MANUAL")
    eng = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"plc_mode": "REMOTE_MANUAL"}})[1] or {}
    excluded = [o for o in ((eng.get("result") or eng).get("options") or []) if not o.get("feasible")]
    r.check("원격 수동이면 원격 제어 후보가 빠지고, 순위가 높아도 금지 조건이면 그 이유(제외 사유)가 결과에 보인다",
            bool(excluded) and all(o["name"] in manual for o in excluded) and "제외" in manual,
            f"엔진 제외 {[o['name'] for o in excluded]} · 화면 {manual[:200]}", kind="exception", axis=AXES[1])
    neg = decide_screen(r, fan=-5)
    code_neg = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"fan100_hours": -5}})[0]
    r.check("팬 연속 운전 시간에 음수 → 판단 엔진이 4xx로 거절하고 화면에 「음수일 수 없습니다」", 400 <= code_neg < 500 and "음수일 수 없습니다" in neg,
            f"엔진 {code_neg} · 화면 {neg[:300]}", kind="exception", axis=AXES[1])
    r.tab("whatif")
    r.wait(20, lambda: r.page.locator("#wiPattern option").count() > 0, every=1)
    r.page.select_option("#wiAsset", "HYD-01")
    r.page.select_option("#wiPattern", "COOLER_DEGRADATION")
    r.page.click("#wiLoad")
    r.wait(120, lambda: r.page.locator("[data-wi-tab]").count() > 0 or r.page.locator("#whatifView p.neg").count() > 0, every=1)
    view = txt(r, "#whatifView", 5000)
    loaded = r.page.locator("[data-wi-tab]").count() > 0
    r.check("손익 · What-if 기준을 불러온다 · 요약에 「원본 그대로」", loaded and "원본 그대로" in view, view[:300])
    if loaded:
        r.page.locator("[data-wi-tab='values']").click()
        fields = r.page.locator("[data-wi-var]")
        if not fields.count():
            r.check("「값 바꿔 보기」에 바꿀 수 있는 값이 있다", False, txt(r, "#whatifView")[:300])
        else:
            for attempt in (1, 2):
                fields.first.fill("1")
                r.page.click("#wiTry")
                r.wait(60, lambda: "시험값 1개 적용 중" in txt(r, "#whatifView"), every=1)
                after = txt(r, "#whatifView", 5000)
                r.check(f"값 하나를 바꿔 다시 계산 → 「시험값 1개 적용 중」 · 원본 그대로({attempt}번째)", "시험값 1개 적용 중" in after and "원본 그대로" in after, after[:300],
                        axis=AXES[0] if attempt == 1 else AXES[3])
                r.page.click("#wiReset"); r.page.wait_for_timeout(800)
                r.check(f"[원래대로] → 시험값이 사라진다({attempt}번째)", "적용 중" not in txt(r, "#whatifView"), "", kind="exception", axis=AXES[1])
    r.tab("kpi")
    r.wait(30, lambda: r.page.locator("[data-kpi-target]").count() > 0 or "없" in txt(r, "#kpiView"), every=1)
    kpi_before = r.get(r.process + "/api/kpi?period=7d")
    if r.page.locator("[data-kpi-target]").count():
        r.page.wait_for_timeout(2000)
        fold = r.page.locator("#kpiView details").filter(has_text="목표값 바꿔 보기").first
        if fold.count() and not fold.evaluate("d => d.open"):
            fold.locator("summary").first.click(); r.page.wait_for_timeout(500)
        r.page.locator("[data-kpi-target]").first.fill("1", timeout=10_000)
        r.page.locator("[data-kpi-trial-run]").first.click()
        r.page.wait_for_timeout(2500)
        r.human("성과 지표 시험 목표 → [시험 판정] 결과가 보인다", txt(r, "#kpiView", 5000), r.page.locator("[data-kpi-trial-reset]").count() > 0, axis=AXES[0], kind="normal")
        r.page.locator("[data-kpi-trial-reset]").first.click(); r.page.wait_for_timeout(1500)
    else:
        r.check("성과 지표 화면에 시험 목표 칸이 있다", False, txt(r, "#kpiView")[:300])
    kpi_after = r.get(r.process + "/api/kpi?period=7d")

    def still(v):          # 업무 DB 의 납기까지 남은 시간은 시계와 함께 줄어든다 — 시험값이 바꾼 것만 본다
        if isinstance(v, dict):
            return {k: still(x) for k, x in v.items() if not k.endswith("_in_h") and not k.endswith("_free_h")}
        return [still(x) for x in v] if isinstance(v, list) else v
    def targets(k):         # 시험 목표가 바꿀 수 있는 것 = 지표마다 목표 · 경고 · 위험선 · 방향. 실적 · 기간 창(최근 7일)은 시계와 함께 움직인다(한바퀴3)
        return sorted((m["id"], m.get("target"), m.get("warn"), m.get("crit"), m.get("direction"))
                      for p in k.get("perspectives") or [] for o in p.get("objectives") or [] for m in o.get("measures") or [])
    changed = [n for n, same in (("업무 DB", still(ent(r)) == still(ent_before)), ("지식 그래프", len(graph(r)["nodes"]) == len(graph_before["nodes"])),
                                 ("KPI 목표", targets(kpi_before) == targets(kpi_after))) if not same]
    r.check("시험값 · 시험 목표를 되돌린 뒤 원본(업무 DB · 지식 · KPI)이 그대로", not changed, "바뀐 곳: " + (", ".join(changed) or "없음"), kind="exception", axis=AXES[1])


# ====================================================================== 05 통합 39 · 실전 35
@lab("05", [("통합", "현장 매뉴얼에서 판단 근거를 추출하고 검증된 지식으로 등록하기"), ("실전", "현장 매뉴얼을 검토해 근거 있는 지식으로 등록하기")])
def lab_05_manual_to_knowledge(r: Round):
    resolve_rows(r, "05")
    page = r.page
    before = label_counts(graph(r))
    loaded = {k: current_batch(r, k) for k in ("HM-8", "PM-02", "PR-07")}
    r.check("세 제공 문서가 현재 판본으로 적재돼 있다(시작 7단계)", all(loaded.values()), json.dumps({k: (v or {}).get("batch") for k, v in loaded.items()}, ensure_ascii=False))
    r.tab("knowledge")
    total0 = r.get(f"{r.process}/api/kg/manuals/sources?limit=1")["total"]
    page.set_input_files("#manualFile", [])          # 앞 실습(02)이 고른 파일이 이 화면에 남아 있다 — 「파일 없이」는 파일 칸을 비운 뒤다(한바퀴3)
    page.click("#manualPreview")
    r.check("파일 없이 [문서 등록] → 「등록할 파일을 먼저 선택하세요」", "파일을 먼저 선택" in page.locator("#manualResult").inner_text(), page.locator("#manualResult").inner_text(),
            kind="exception", axis=AXES[1])
    for label, f in [("빈 파일", {"name": "empty.md", "mimeType": "text/markdown", "buffer": b""}),
                     ("제공하지 않은 문서", {"name": "my-notes.md", "mimeType": "text/markdown", "buffer": "# 내 메모\n\n1. 팬을 끈다".encode()}),
                     ("PDF 이름의 텍스트", {"name": "fake.pdf", "mimeType": "application/pdf", "buffer": "가짜 PDF".encode()})]:
        page.set_input_files("#manualFile", f)
        page.click("#manualPreview")
        page.wait_for_selector("#manualResult .neg, #manualResult .mprev", timeout=30_000)
        text = page.locator("#manualResult").inner_text()
        r.human(f"잘못된 파일 거절 — {label}", text.replace("문서를 등록하지 못했습니다:", "").strip(), "문서를 등록하지 못했습니다" in text)   # hitl.js #manualPreview
    r.check("거절된 파일은 보관 원문에 남지 않는다", r.get(f"{r.process}/api/kg/manuals/sources?limit=1")["total"] == total0, kind="exception", axis=AXES[1])
    got = ingest_manual(r, "HM-8", "HM-8")
    if not got:
        return
    again = ingest_manual(r, "HM-8", "HM-8 한 번 더(개정)")
    if again:
        r.check("같은 문서를 다시 추출 · 적재해도 같은 제안(절차 · 단계 · 규칙)", {k: again[k] for k in ("procedures", "steps", "rules")} == {k: got[k] for k in ("procedures", "steps", "rules")},
                json.dumps({k: again[k] for k in ("procedures", "steps")}, ensure_ascii=False)[:300], axis=AXES[3])
    hist = page.locator("#manualHistory").inner_text()
    r.check("적재 이력 카드에 HM-8 판본이 보인다", "HM-8" in hist, hist[:300])
    after = label_counts(graph(r))
    shrank = {k: (v, after.get(k, 0)) for k, v in before.items() if k in ("Skill", "FailureMode", "Cause", "Rule") and after.get(k, 0) < v}
    r.check("개정 적재 뒤 조치 방법 · 고장 유형 · 원인 · 규칙이 줄지 않았다", not shrank, json.dumps(shrank or after, ensure_ascii=False)[:300], axis=AXES[3])
    r.tab("ontology")
    page.click("#ontoReload")
    r.wait(20, lambda: page.locator("#ontoMap .o-node").count() > 0, every=1)
    page.fill("#ontoSearch", "팬 최대 운전")
    node = page.locator("#ontoMap .o-node[aria-label*='조치 방법'][aria-label*='팬 최대 운전']").first
    trail = []
    if node.count():
        node.click()
        for rel in ("절차 단계", "근거 매뉴얼", "속한 문서"):
            # 나가는 관계는 관계 이름을 제목으로 한 묶음이다: <section class="rel-group"><h4>관계 이름 <span class="n">수</span>…(enterprise.js renderNodePanel).
            # 들어오는 묶음은 제목이 종류 이름이고 관계 이름은 꼬리표라, 제목이 그 관계 이름으로 시작하는 묶음만 고른다
            group = page.locator("#ontoNode section.rel-group").filter(has=page.locator("h4", has_text=re.compile(rf"^\s*{re.escape(rel)}\s*\d")))
            link = group.locator("a[data-go]").first
            if not link.count():
                break
            trail.append(link.inner_text()); link.click(); page.wait_for_timeout(400)
    r.check("지식 지도: 팬 최대 운전 → 단계 → 근거 절 → HM-8 문서(원문 출처)", len(trail) == 3 and "HM-8" in trail[-1], " → ".join(trail))
    # 실전 35: 데이터 연결에서 설비 · 질문을 골라 질의를 직접 실행 — 문서의 기준값과 업무 DB · 시계열 현재값을 나란히
    fabric_query(r, "데이터 연결")


def fabric_query(r: Round, label: str):
    page = r.page
    r.tab("fabric")
    r.wait(15, lambda: page.locator("#fabRun").count(), every=1)
    page.locator("[data-fab-tab='join']").first.click()
    page.select_option("#fabQuery", label="고온 구간 로트와 실제 유온 기록")
    page.click("#fabRun")
    r.wait(30, lambda: "읽는 중" not in page.locator("#fabRun").inner_text() and page.locator("#fabResult .card").count(), every=1)
    res = page.locator("#fabResult").inner_text()
    r.check(f"{label}: 질의 직접 실행 — 결과에 「업무 DB」 · 「시계열 DB」 · 「기준」 칸이 함께 나오고 「조회 실패」가 없다", "업무 DB" in res and "시계열 DB" in res
            and "조회 실패" not in res and "기준" in res, res[:500])
    return res


# ====================================================================== 06 통합 40
@lab("06", [("통합", "업무 DB 구조를 지식에 연결하고 현재값과 구분하기")])
def lab_06_legacy_db(r: Round):
    resolve_rows(r, "06")
    page = r.page
    inputs0 = label_counts(graph(r)).get("InputData", 0)
    batches0 = {x.get("batch") for x in r.get(f"{r.process}/api/kg/ingests")}

    def load_once(n: int) -> str | None:
        r.tab("knowledge")
        page.set_input_files("#ddlFile", str(SAMPLES / "legacy-plant-db.sql"))
        page.click("#ddlPreview")
        page.wait_for_selector("#ddlResult .mprev, #ddlResult .neg", timeout=60_000)
        head = txt(r, "#ddlResult .mprev .muted") or txt(r, "#ddlResult")
        tables = re.findall(r'CREATE TABLE "([^"]+)"', (SAMPLES / "legacy-plant-db.sql").read_text(encoding="utf-8"))
        r.check(f"옛 설비 DB 구조 파일 미리보기 — 표 {len(tables)}개({n}번째)", f"테이블 {len(tables)}개" in head, head, axis=AXES[0] if n == 1 else AXES[3])
        # 표마다 출처 시스템을 정하고(미리 고른 값이 없으면 첫 시스템) 연결할 열은 미리 고른 그대로 둔다
        for sel in page.locator("#ddlResult select[data-sys]").all():
            if not sel.input_value():
                opts = [v for v in sel.locator("option").evaluate_all("ns => ns.map(n => n.value)") if v]
                if opts:
                    sel.select_option(opts[0])
        page.click("#ddlReplan")
        r.wait(30, lambda: not page.locator("#ddlCommit").is_disabled(), every=1)
        page.click("#ddlCommit")
        r.wait(60, lambda: txt(r, "#ddlMsg").startswith(("적재했습니다", "적재하지 못했습니다")), every=1)      # hitl.js ddlCommit(ddlSay)
        msg = txt(r, "#ddlMsg")
        r.check(f"표 · 열을 골라 적재({n}번째)", msg.startswith("적재했습니다"), msg, axis=AXES[0] if n == 1 else AXES[3])
        new = {x.get("batch") for x in r.get(f"{r.process}/api/kg/ingests")} - batches0
        return next(iter(new), None) if msg.startswith("적재했습니다") else None

    batch = load_once(1)
    if not batch:
        return
    m = re.search(r"입력 데이터 (\d+)", txt(r, "#ddlMsg"))
    added = int(m.group(1)) if m else -1
    r.check("적재한 입력 데이터 수 = 그래프의 InputData 증가", label_counts(graph(r)).get("InputData", 0) - inputs0 == added, f"화면 {added} · 그래프 {label_counts(graph(r)).get('InputData', 0) - inputs0}")
    links = r.get(f"{r.process}/api/fabric/links")
    legacy = [i for i in links["inputs"] if str(i.get("table") or "").upper().startswith("T_")]
    r.tab("fabric")
    page.locator("[data-fab-tab='links']").first.click(); page.wait_for_timeout(1500)
    for fold in page.locator(".fab-body details").all():   # 상태별 묶음(8개 넘으면 접힘)을 학생처럼 펴서 읽는다 — 접힌 글은 보이는 글이 아니다
        open_fold(fold)
    screen = txt(r, ".fab-body", 5000)
    r.check("데이터 연결: 적재한 표 · 열이 「판단 입력의 원천」에 이어짐(화면 = API)", bool(legacy) and all(f"{i['table']}.{i['column']}" in screen for i in legacy),
            f"{[(i['table'], i['column'], i['state']) for i in legacy][:6]}")
    missing = [i for i in legacy if i.get("state") != "OK"]
    if missing:
        r.human("옛 DB 표가 업무 DB에 없으면 그 까닭이 사람 글로", missing[0].get("reason") or "", axis=AXES[1])
    r.check("클래스 ↔ 표 · 열(설비 · 부품 …)이 살아 있는 카탈로그에 대어 OK", bool(links["classes"]) and all(c["state"] == "OK" for c in links["classes"]),
            str([(c["label"], c["table"], c["state"]) for c in links["classes"]]))
    r.check("옛 DB 표 · 열이 등록 원천(옛 설비 DB)의 살아 있는 표에 이어져 OK", bool(legacy) and not missing
            and all(i.get("datasource") == "hyd-legacy" for i in legacy),
            str([(i['table'], i['column'], i.get('datasource'), i['state']) for i in legacy][:6]))
    page.locator("[data-fab-tab='sources']").first.click(); page.wait_for_timeout(1500)
    # 제공 파일의 첫 표(설비 목록) — 파일의 INSERT 행 수(샘플 한도 5 안)가 화면 샘플 행 수와 같아야 한다
    dump = (SAMPLES / "legacy-plant-db.sql").read_text(encoding="utf-8")
    first_table = re.findall(r'CREATE TABLE "([^"]+)"', dump)[0]
    rows_in_file = len(re.findall(r"^\s+\(", dump.split(f'INSERT INTO "{first_table}"', 1)[1].split("VALUES", 1)[1].split(";", 1)[0], re.M))
    page.locator(f"[data-fab-table='hyd-legacy|{first_table}']").first.click()
    r.wait(20, lambda: re.search(r"최신 \d+행", txt(r, ".fab-body")) is not None, every=1)
    shown = re.search(r"최신 (\d+)행", txt(r, ".fab-body"))
    r.check(f"옛 DB 표({first_table})를 누르면 샘플 행이 보인다 — 파일의 행 {rows_in_file}개", bool(shown) and int(shown.group(1)) == min(rows_in_file, 5),
            txt(r, ".fab-body")[:300])
    fabric_query(r, "현재값과 기준 구분")

    def revert(n: int):
        r.tab("knowledge")
        page.wait_for_selector(f"#ddlHistory [data-clear='{batch_now}']", timeout=15_000)
        open_fold(page.locator("#ddlHistory details").first)             # 되돌리기 단추는 「연결 이력」 접기 안에 있다(hitl.js loadIngests)
        page.locator(f"#ddlHistory [data-clear='{batch_now}']").click()
        if not confirm_ok(r):                                              # 브라우저 확인 창이 아니라 포털 확인 창이다(UI.confirm)
            raise ScreenMissing("[되돌리기]의 확인 창이 뜨지 않음")
        r.wait(30, lambda: txt(r, "#ddlHistoryMsg").startswith(("되돌렸습니다", "되돌리지 못했습니다")), every=1)
        msg = txt(r, "#ddlHistoryMsg")
        left = batch_now in {x.get("batch") for x in r.get(f"{r.process}/api/kg/ingests")}
        r.check(f"연결한 배치를 되돌리면 원래 상태(입력 데이터 수 · 배치 목록)로({n}번째)", msg.startswith("되돌렸습니다") and not left
                and label_counts(graph(r)).get("InputData", 0) == inputs0, f"{msg} · 남음 {left}", kind="exception", axis=AXES[1] if n == 1 else AXES[3])
    batch_now = batch
    revert(1)
    batch_now = load_once(2)
    if batch_now:
        revert(2)
    meaning = page.locator("#legacyMeaning button").first
    if meaning.count() and meaning.is_disabled():
        r.human("옛 DB 뜻 복원(AI)은 수업에서 막히고 까닭이 사람 글로(악용 지점 아님 — PBL 기능)", meaning.get_attribute("title") or "", axis=AXES[1])


# ====================================================================== 07 통합 50 · 실전 44
@lab("07", [("통합", "업무 에이전트를 구성하고 질문의 도구·근거 확인하기"), ("실전", "업무 에이전트를 구성하고 질문의 도구·근거 확인하기")])
def lab_07_first_agent(r: Round):
    resolve_rows(r, "07")
    page = r.page
    r.tab("agents")
    r.wait(15, lambda: page.locator("[data-new-agent]").count(), every=1)
    # 기준 에이전트의 목표 · 지침 · 사용 도구 읽기
    base_agent = next((a for a in agents(r) if a.get("id") == "agent:cooling"), None)
    page.locator("[data-pick-agent='agent:cooling']").first.click()
    r.wait(15, lambda: "불러오는 중" not in page.locator("[data-ag-detail]").inner_text(), every=0.5)
    d = page.locator("[data-ag-detail]").inner_text()
    r.check("기준 에이전트: 목표 · 지침(실행 지시문) · 쓰는 도구가 보이고 API 와 같다", bool(base_agent) and "목표" in d and "쓰는 도구" in d and "지시문" in all_txt(r, "[data-ag-detail]")
            and (base_agent.get("goal") or "")[:20] in d, d[:300])
    page.click("[data-new-agent]")
    err = agent_form(r)
    r.check("빈 폼 저장 → 「이름 칸을 채워야 합니다」", "이름" in err and "채워야" in err, err, kind="exception", axis=AXES[1])
    form_text = page.locator("[data-ag-form]").inner_text()
    r.check("모델은 고르는 칸 없이 「수업 모델(강사 지정)」로 보인다", page.locator("[data-ag-form] [data-f='model']").count() == 0 and "수업 모델" in form_text, form_text[:200],
            kind="exception", axis=AXES[1])
    err = agent_form(r, name="냉각 긴급 대응 에이전트", goal="기본 에이전트와 같은 이름")
    r.human("기본 에이전트와 같은 이름 → 거절", err, "같은 이름" in err)
    mine = my_agent(r)
    if mine:
        err = agent_form(r, **MY_PROFILE)
        r.human("같은 이름 중복 → 거절(두 번째 실행 PC)", err, "같은 이름" in err, axis=AXES[3])
        page.locator("[data-f-cancel]").first.click()
    else:
        err = agent_form(r, **MY_PROFILE)
        r.check("나의 에이전트 저장(이름 · 역할 · 목표 · 성격 · 도구)", not err, err)
        mine = my_agent(r)
        page.click("[data-new-agent]")
        err = agent_form(r, **MY_PROFILE)
        r.human("같은 이름으로 한 번 더 → 거절", err, "같은 이름" in err, axis=AXES[3])
        page.locator("[data-f-cancel]").first.click()
    if not mine:
        r.check("나의 에이전트가 목록에 있다", False)
        return
    r.memo["my_agent"] = mine["id"]
    page.locator(f"[data-pick-agent='{mine['id']}']").first.click()
    r.wait(15, lambda: "불러오는 중" not in page.locator("[data-ag-detail]").inner_text(), every=0.5)
    detail = page.locator("[data-ag-detail]").inner_text()
    r.check("상세: 「내가 만든」 · 목표 · 쓰는 도구가 보인다", "내가 만든" in detail and "목표" in detail and "쓰는 도구" in detail, detail[:300])
    roles = known_roles(r)
    mitigations = {s["sopId"] for s in r.get(f"{r.process}/api/kg/skills")
                   if any(f.get("id") == "fm:cooler-cooling-loss" and f.get("relation") == "MITIGATED_BY" for f in s.get("failureModes") or [])}
    expected = {sop: p["approver"] for sop, p in source_doc("HM-8").items() if p.get("approver") and sop in mitigations}
    runs = r.repeat3("나의 에이전트 질문", lambda i: ask(r, mine["id"], QUESTION), ("kind", "sop_ids", "verified_ok"), limit_s=ASK_LIMIT_S)
    r.memo["07_ask"] = runs[0]
    # 화면의 질문 칸은 마지막으로 보낸 질문 하나를 보인다(ask.js A.cur) — 화면과 대조할 실행은 끝까지 간 마지막 실행이다(한바퀴3: 첫 실행 21회와
    # 화면의 셋째 실행 18회를 견줬다)
    last = next((x for x in reversed(runs) if not x.get("error")), runs[-1])
    r.check("답 + 근거가 서버 대조(실행 기록)를 통과", last.get("kind") == "answered" and last.get("verified_ok"),
            f"{last.get('kind')} · 근거 {last.get('verified')} · {last.get('reason') or last.get('message') or last.get('error') or ''}", kind="quality")
    r.check("답의 절차 번호 = 원문 HM-8 의 즉시 완화(MITIGATED_BY) 절차", last.get("sop_ids") == sorted(expected), f"답 {last.get('sop_ids')} · 원문 {sorted(expected)}", kind="quality")
    ok, note = roles_in_answer(last.get("answer") or "", expected, roles)
    r.check("답의 각 절차 승인 역할 = 원문 「승인:」 줄", ok, note, kind="quality")
    calls = [c for c in last.get("tool_calls") or [] if c.get("ok") and c.get("data")]
    r.check("처리 과정의 도구 호출마다 입력 · 결과 · 시각이 남는다", bool(calls) and all(c.get("input_text") and c.get("output_text") and c.get("started") for c in calls),
            f"데이터 호출 {len(calls)}개")
    page.locator(".ask-process summary").first.click()
    proc = page.locator(".ask-process").first.inner_text()
    r.check("처리 과정 · 도구 호출 수가 화면에 보인다(= 기록)", f"도구 호출 {last.get('calls')}" in proc.replace("\n", " "), proc[:300])
    base = ask(r, "sys:agent", QUESTION)
    r.check("기준 에이전트도 같은 질문에 근거 있는 답", base.get("kind") == "answered" and base.get("verified_ok"), base.get("reason") or base.get("message") or base.get("error") or "",
            kind="quality")
    r.check("나의 에이전트 vs 기준 에이전트 — 같은 절차 번호", base.get("sop_ids") == last.get("sop_ids"), f"나 {last.get('sop_ids')} · 기준 {base.get('sop_ids')}", kind="quality")
    unk = ask(r, mine["id"], "HYD-01 쿨러 팬 모터 제조사의 고객센터 전화번호는 무엇인가?")
    r.check("지식에 없는 질문 → 「답할 수 없음」(지어내지 않음)", unk.get("kind") == "unanswerable",
            f"{unk.get('kind')} · {unk.get('state')} · {unk.get('message') or ''} · {(unk.get('answer') or '')[:200]}", kind="exception", axis=AXES[1])
    if unk.get("reason"):
        r.human("답할 수 없음 이유가 사람 글", unk["reason"])
    r.check("답할 수 없음 카드가 화면에 보인다", "답할 수 없음" in unk.get("screen", ""), unk.get("screen", "")[-200:], kind="exception", axis=AXES[1])
    for x in (base, unk):
        r.keyless(f"키 없는 PC: 「{x.get('id', '')[:24]}」 질문이 녹화로 끝까지(잘못 막힘 없음)", x.get("ai") == "강사 녹화 재생" and x.get("state") == "done",
                  f"{x.get('ai')} · {x.get('state')} · {x.get('message')}")
    before = next(a for a in agents(r) if a["id"] == mine["id"])
    # 고치기는 모든 칸을 받는다(agent_authoring.AGENT_FIELDS) — 포털 고치기 폼(agents.js openForm)과 같은 칸에 모델만 바꿔 보내야 거절 까닭이
    # 「수업 모델」 하나다(한바퀴3: skills · work_rules 를 빼고 보내 「빠진 칸」 거절을 모델 거절로 잘못 판정)
    code, body = r.api("PUT", f"{r.process}/api/agents/{mine['id']}", {**{k: before.get(k) or "" for k in ("name", "role", "goal", "persona", "work_rules")},
                                                                      "tools": [t.get("name") if isinstance(t, dict) else t for t in before.get("tools") or []
                                                                                if not (isinstance(t, dict) and t.get("registered") is False)],
                                                                      "skills": [x.get("skill_name") if isinstance(x, dict) else x for x in before.get("skills") or []],
                                                                      "model": "gpt-9-ultra"})
    detail = str(body.get("detail") if isinstance(body, dict) else body)
    after = next(a for a in agents(r) if a["id"] == mine["id"])
    r.human("수업 모델 밖 모델을 서버에 직접 보내면 거절되고 원래 설정을 유지한다", detail, 400 <= code < 500 and "수업 모델" in detail and after.get("model") == before.get("model"))
    r.tab("ask")
    r.check("질문 화면 에이전트 도구 칩이 사람 이름으로 보인다", "도구 표시 이름" not in page.locator("[data-ask-form]").inner_text(),
            page.locator("[data-ask-form]").inner_text()[:300], kind="quality")


# ====================================================================== 08 통합 51
@lab("08", [("통합", "센서 변화와 경보 시점을 실시간 화면에서 찾기")])
def lab_08_trends(r: Round):
    resolve_rows(r, "08")
    page = r.page
    pid, got = a_case(r)
    if not pid:
        r.check("[쿨러 열화] → 처리 건", False, got["outcome"]); return
    try:
        view = got["view"]
        alert = vars_of(view["instance"]).get("alert") or {}
        r.tab("trends")
        page.select_option("#selAsset", "HYD-01"); page.wait_for_timeout(1500)
        srcs = {f: page.locator(f"#{f}").get_attribute("src") or "" for f in ("pTs1", "pScore", "pCe")}
        r.check("실시간 모니터링: 그 설비의 유온 · 이상 점수 · 냉각 효율 패널(설비 변수 = HYD-01)", all("var-asset=HYD-01" in s and "panelId=" in s for s in srcs.values()),
                json.dumps(srcs)[:300])
        rendered = {}
        for f in srcs:
            frame = page.frame_locator(f"#{f}")
            try:
                frame.locator("body").wait_for(timeout=20_000)
                r.page.wait_for_timeout(3000)
                rendered[f] = frame.locator("body").inner_text(timeout=10_000)
            except Exception as e:
                rendered[f] = f"패널을 그리지 못함: {type(e).__name__}"
        bad = {f: t[:80] for f, t in rendered.items() if not t.strip() or re.search(r"No data|Panel not found|Dashboard not found|패널을 그리지 못함", t)}
        r.check("세 패널이 데이터와 함께 그려진다(빈 패널 · 「No data」 아님)", not bad, json.dumps(bad, ensure_ascii=False))
        # 경보 시각 · 측정값: 처리 건의 경보(alert.t · evidence)와 설비 회로 화면의 사건 · 처리 기록의 에이전트 근거가 같은 구간인가
        inc = vars_of(view["instance"]).get("incident")
        r.tab("incidents")
        r.page.locator("#btnAllInc").click(); r.page.wait_for_timeout(800)
        item = page.locator(f"#incList .item[data-item-id='{inc}']").first
        r.wait(20, lambda: item.count() > 0, every=1)
        item.click(); page.wait_for_timeout(1500)
        det = all_txt(r, "#incDetail")
        ev = alert.get("evidence") or {}
        r.check("설비 회로: 그 사건 상세가 열리고 사건 경과 · 「기록」 칸과 [이 사건의 처리 건 보기]가 있다(원인 근거는 처리 건 처리 기록 한 곳 — 다음 판정)",
                bool(inc) and "기록" in det and page.locator("#incDetail #btnIncInstance").count() == 1, det[:300])
        card = vars_of(view["instance"]).get("guide_card") or {}
        evs = [e for c in card.get("causes") or [] for e in c.get("evidence") or []]
        alert_t = datetime.fromisoformat(str(alert.get("t")).replace("Z", "+00:00"))
        dec = decision_of(r, view)
        made = datetime.fromisoformat(str(dec.get("created")).replace("Z", "+00:00"))
        r.check("에이전트가 근거로 든 측정값은 경보 뒤 · 판단 전 구간에서 읽은 값", bool(evs) and alert_t <= made and all(e.get("coverage", {}).get("covered") for e in evs[:2]),
                f"경보 {alert_t:%H:%M:%S} · 판단 {made:%H:%M:%S} · 근거 {[(e.get('id'), round(float(e.get('value') or 0), 2)) for e in evs[:3]]}", kind="quality")
        # 원인 근거(진단 카드의 증거)는 설비 회로 화면에 사본을 두지 않는다 — [이 사건의 처리 건 보기] → 처리 건 「처리 기록」 탭에서 본다
        page.locator("#incDetail #btnIncInstance").click()
        r.wait(15, lambda: page.evaluate("() => state.tab") == "instances" and pid in all_txt(r, "#instDetail"), every=0.5)
        page.locator("#instDetail [data-inst-tab='record']").click(); page.wait_for_timeout(1500)
        record = all_txt(r, "#instRecord")
        shown = [e for e in evs[:2] if e.get("name") and e["name"] in record]
        r.check("설비 회로의 [이 사건의 처리 건 보기]로 연 처리 기록의 근거 이름 = 처리 건에 남은 근거(에이전트가 든 측정값)", bool(evs) and len(shown) == len(evs[:2]),
                f"{[(e.get('name'), e.get('value')) for e in evs[:2]]}")
        r.check("경보 근거 값(유온 · 냉각 효율)이 패턴 문장의 기준을 넘었다(함께 움직인 값 ≠ 원인 단정)", float(ev.get("ts1") or 0) > 55 and float(ev.get("ce") or 100) < 70,
                json.dumps(ev, ensure_ascii=False)[:200], kind="quality")
        r.keyless("키 없는 PC: 실시간 패널 · 설비 회로는 AI 없이 그대로 보인다", not bad, "")
        r.tab("trends")                       # 앞 판정이 다른 화면으로 옮겨 갔다 — 설비 고르기는 실시간 모니터링 화면에 있다(한바퀴3)
        page.select_option("#selAsset", "HYD-02"); page.wait_for_timeout(800)
        page.select_option("#selAsset", "HYD-01"); page.wait_for_timeout(800)
        r.check("설비를 바꿨다 돌아와도 패널이 그 설비로 다시 그려진다", "var-asset=HYD-01" in (page.locator("#pTs1").get_attribute("src") or ""), "", axis=AXES[3])
    finally:
        restore_and_close(r, pid)


# ====================================================================== 09 통합 62 · 실전 47
SKILL_MARK = "확인할 항목:"
MY_SKILL = "cooler-evidence-check"


@lab("09", [("통합", "포털에서 스킬을 만들어 에이전트에 붙이고 답의 차이 확인하기"), ("실전", "포털에서 스킬을 만들어 에이전트에 붙여 보기")])
def lab_09_skill(r: Round):
    resolve_rows(r, "09")
    page = r.page
    mine = ensure_my_agent(r)
    if not mine:
        return
    r.tab("agents")
    page.locator('[data-ag-tab="skills"]').click()
    r.wait(15, lambda: page.locator("[data-pick-skill='cooling-emergency-response']").count(), every=1)
    page.locator("[data-pick-skill='cooling-emergency-response']").first.click()
    r.wait(15, lambda: "불러오는 중" not in page.locator("[data-ag-detail]").inner_text(), every=0.5)
    content = r.get(f"{r.process}/api/skills/cooling-emergency-response").get("content") or ""
    doc = all_txt(r, "[data-ag-detail] pre")
    r.check("기준 스킬의 SKILL.md 원문이 화면에 그대로(공백만 빼고 저장본과 글자까지 같다)", bool(content.strip()) and " ".join(doc.split()) == " ".join(content.split()),
            f"화면 {len(doc.strip())}자 · 저장 {len(content.strip())}자")
    taken = {s["skill_name"] for s in r.get(f"{r.process}/api/skills")}
    if MY_SKILL not in taken:
        page.locator("[data-new-skill]").click()
        page.locator('[data-f="skill_name"]').fill(MY_SKILL)
        page.locator('[data-f="description"]').fill("쿨러 이상 답에 근거와 확인할 항목을 꼭 남긴다")
        page.locator('[data-f="content"]').fill(
            f"---\nname: {MY_SKILL}\ndescription: 쿨러 이상 답에 근거와 확인할 항목을 꼭 남긴다\n---\n# 쿨러 이상 답변 점검\n\n"
            "목적: 쿨러 이상 질문의 답이 조회 근거와 다음 확인 사항을 함께 갖게 한다.\n호출 조건: 쿨러 · 유온 · 냉각 효율 질문.\n"
            f"순서: 1. 지식 그래프에서 절차와 승인 역할을 조회한다. 2. 답 끝에 「{SKILL_MARK}」로 시작하는 줄을 두고 현장에서 확인할 것을 적는다.\n"
            "예외: 조회되지 않으면 지어내지 않고 모른다고 한다.\n")
        page.locator("[data-ag-form] button[type='submit']").click()
        r.check("나의 스킬을 새로 써서 저장", bool(r.wait(15, lambda: MY_SKILL in {s["skill_name"] for s in r.get(f"{r.process}/api/skills")}, every=1)), "")
        page.locator("[data-new-skill]").click()
        page.locator('[data-f="skill_name"]').fill(MY_SKILL)
        page.locator('[data-f="content"]').fill(f"---\nname: {MY_SKILL}\n---\n같은 이름")
        page.locator("[data-ag-form] button[type='submit']").click(); page.wait_for_timeout(1500)
        err = txt(r, "[data-ag-detail] .form-msg.neg") or txt(r, "#toaster")
        r.human("같은 이름의 스킬을 또 만들면 거절 · 사람 글", err, axis=AXES[3])
        if page.locator("[data-f-cancel]").count():
            page.locator("[data-f-cancel]").first.click()

    def attach(n: int):
        r.tab("agents"); page.locator('[data-ag-tab="skills"]').click()
        page.locator(f"[data-pick-skill='{MY_SKILL}']").first.click()
        r.wait(15, lambda: page.locator("[data-attach-to], [data-detach]").count(), every=0.5)
        page.select_option("[data-attach-to]", mine["id"])
        page.locator("[data-attach]").click()
        ok = r.wait(15, lambda: any(a["id"] == mine["id"] for a in next(s for s in r.get(f"{r.process}/api/skills") if s["skill_name"] == MY_SKILL)["agents"]), every=1)
        r.check(f"나의 에이전트에 스킬 붙이기({n}번째)", bool(ok), "", axis=AXES[0] if n == 1 else AXES[3])

    def detach(n: int):
        r.tab("agents"); page.locator('[data-ag-tab="skills"]').click()
        page.locator(f"[data-pick-skill='{MY_SKILL}']").first.click()
        btn = page.locator(f"[data-detach='{mine['id']}']")
        r.wait(15, lambda: btn.count(), every=0.5)
        btn.click()
        ok = r.wait(15, lambda: not any(a["id"] == mine["id"] for a in next(s for s in r.get(f"{r.process}/api/skills") if s["skill_name"] == MY_SKILL)["agents"]), every=1)
        r.check(f"스킬 떼기({n}번째)", bool(ok), "", axis=AXES[0] if n == 1 else AXES[3])

    before = r.memo.get("07_ask") or ask(r, mine["id"], QUESTION)
    attach(1)
    withskill = ask(r, mine["id"], QUESTION)
    detach(1)
    without = ask(r, mine["id"], QUESTION)
    attach(2)
    detach(2)
    if r.ai_mode == "live":
        r.check("스킬을 붙인 질문은 새 요청이라 실제 AI로 다시 실행", withskill.get("ai") == "실제 AI", withskill.get("ai"))
        r.check("스킬을 붙인 답은 스킬이 시킨 「확인할 항목:」 줄과 근거를 갖는다(붙이기 전 답과 다름)", SKILL_MARK in (withskill.get("answer") or "")
                and withskill.get("verified_ok") and withskill.get("answer") != before.get("answer"), (withskill.get("answer") or "")[-300:], kind="quality")
        used = [e for e in view_of(r, withskill["id"])["events"] if (e.get("data") or {}).get("type") in ("skill_used", "skills_provided")]
        r.check("처리 과정에 스킬을 읽은 기록이 남는다", bool(used), f"{len(used)}건")
        r.check("스킬을 떼고 다시 물으면 붙이기 전과 같은 요청 — 스킬 줄이 없다", SKILL_MARK not in (without.get("answer") or "") and without.get("kind") == "answered",
                f"{without.get('ai')} · {(without.get('answer') or '')[-200:]}", axis=AXES[3])
    for label, x in (("스킬 붙인 질문", withskill), ("스킬 뗀 질문", without)):
        r.keyless(f"키 없는 PC: {label}이 녹화로 끝까지(잘못 막힘 없음)", x.get("ai") == "강사 녹화 재생" and x.get("state") == "done",
                  f"{x.get('ai')} · {x.get('state')} · {x.get('message')}")


# ====================================================================== 10 통합 63 · 실전 50
def mcp_select(r: Round, name: str):
    r.tab("mcp")
    page = r.page
    r.wait(15, lambda: page.locator(f"#mcpServers [data-open='{name}']").count(), every=1)
    page.locator(f"#mcpServers [data-open='{name}']").first.click()
    page.locator("#mcpDetail .mcp-detail").wait_for(timeout=10_000)


def mcp_try(r: Round, tool: str, inputs: dict) -> str:
    page = r.page
    btn = page.locator(f"#mcpPane [data-try='{tool}']")
    if btn.inner_text().strip() != "닫기":
        btn.click()
    for k, v in inputs.items():
        page.locator(f".mcp-try [data-key='{k}']").fill(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    page.click("#mcpCall")
    r.wait(30, lambda: "실행하는 중" not in page.locator("#mcpResult").inner_text(), every=0.5)      # mcp.js resultHtml — 기다리는 동안의 글
    return page.locator("#mcpResult").inner_text()


def course_phase(r: Round) -> str:
    """지금 수업 단계 — 서버 정본(GET /api/course-access 의 phase)."""
    code, access = r.api("GET", f"{r.process}/api/course-access")
    phase = access.get("phase") if code == 200 and isinstance(access, dict) else None
    r.check("수업 단계를 서버에서 읽는다", phase in ("course", "pbl"), f"{code} {str(access)[:120]}")
    if phase is None:
        raise RuntimeError(f"수업 단계를 읽지 못함: {code}")
    return phase


@lab("10", [("통합", "포털의 업무 도구를 직접 호출하고 에이전트 근거와 대조하기"), ("실전", "포털의 업무 도구를 직접 호출하고 에이전트 근거와 대조하기")])
def lab_10_mcp_tools(r: Round):
    resolve_rows(r, "10")
    page = r.page
    phase = course_phase(r)
    r.tab("mcp")
    r.wait(20, lambda: page.locator("#mcpServers [data-open='hyd-dmn']").count(), every=0.5)
    names = {s["name"] for s in r.get(f"{r.process}/api/mcp/servers").get("servers", [])}
    # 기본 서버가 모두 있어야 한다 — 학생이 PBL에서 등록한 서버는 더 있어도 된다(같다로 재면 PBL에서 거짓 실패), 수업 단계는 등록이 막혀 기본뿐
    r.check("준비된 서버(에이전트가 쓰는 기본 서버 전부)가 연결 상태와 함께 보인다",
            set(BASE_SERVERS) <= names and (phase == "pbl" or names == set(BASE_SERVERS))
            and all(page.locator(f"#mcpServers [data-name='{n}']").count() for n in names), str(sorted(names)))
    if phase == "course":
        add = page.locator("#mcpAdd")
        why = all_txt(r, "[data-mcp-why]").strip()                      # 운영자 접기 안 — 접혀 있어도 글은 있다
        r.check("수업 단계: 서버 직접 등록 단추는 꺼져 있고 까닭이 보인다", add.is_disabled() and bool(why), why, kind="exception", axis=AXES[1])
        r.human("등록을 막는 까닭이 사람 글", why)
    mcp_select(r, "hyd-dmn")
    page.locator("#mcpPane [data-try='inputs']").wait_for(timeout=15_000)
    listed = r.get(f"{r.process}/api/mcp/servers/hyd-dmn/tools")["tools"]
    shown = {i.get_attribute("data-tool"): i for i in page.locator("#mcpPane .mcp-tool").all()}
    r.check("도구 목록(이름 · 입력 형식)이 API 와 같다", set(shown) == {t["name"] for t in listed}, f"화면 {len(shown)} · API {len(listed)}")
    writes = [t for t in listed if not t.get("callable")]
    wrong = [t["name"] for t in writes if not page.locator(f"#mcpPane .mcp-tool[data-tool='{t['name']}'] [data-try]").is_disabled()]
    r.check("쓰기 도구는 목록에 보이되 [써 보기]가 꺼져 있다(처리 건 안에서 승인 뒤에만)", bool(writes) and not wrong, f"쓰기 {[t['name'] for t in writes]} · 켜진 것 {wrong}",
            kind="exception", axis=AXES[1])
    for t in writes[:1]:
        r.human(f"쓰기 도구 {t['name']} 를 못 쓰는 까닭이 사람 글", page.locator(f"#mcpPane .mcp-tool[data-tool='{t['name']}'] .mcp-why").inner_text())
    out = mcp_try(r, "inputs", {})
    r.check("읽기 도구(입력 자료) [써 보기] → 결과 칸에 그래프의 입력 자료 id(in:cause)가 나온다", "in:cause" in out and "결과" in out, out[:300])
    out2 = mcp_try(r, "inputs", {})
    r.check("같은 읽기 도구를 다시 부르면 결과 칸이 숫자 말고 글자까지 같다", re.sub(r"\d", "", out2.split("보낸 입력")[-1]) == re.sub(r"\d", "", out.split("보낸 입력")[-1]),
            out2[:200], axis=AXES[3])
    # 서버는 「누가」가 빈 요청을 도구를 부르기 전에 400 으로 거절한다(mcp_api · mcp_registry — inbox.actor_or_400). 화면처럼 담당자를 실어 보낸다
    denied, body = r.api("POST", f"{r.process}/api/mcp/servers/hyd-dmn/tools/submit_decision/call", {"arguments": {}, "by": ME})
    r.check("판단 제출은 직접 API에서도 거절", denied == 403, str(body)[:300], kind="exception", axis=AXES[1])
    nobody, body = r.api("POST", f"{r.process}/api/mcp/servers/hyd-dmn/tools/inputs/call", {"arguments": {}})
    r.human("담당자 없이 온 도구 써 보기는 서버가 400 과 사람 글로 거절", (body or {}).get("detail") if isinstance(body, dict) else body, nobody == 400)
    registration, body = r.api("POST", f"{r.process}/api/mcp/servers", {"name": "s01-table", "by": ME})
    if phase == "course":
        r.check("임의 서버 등록은 수업 정책에서 차단(403)", registration == 403, str(body)[:300], kind="exception", axis=AXES[1])
    # 에이전트에게 질문한 뒤 호출 기록에서 도구 이름 · 입력 · 반환값을 찾아 직접 호출 결과와 대조
    # 질문은 이 실습에서 새로 한다 — 07 의 질문은 07 정리(restore)로 지워지고, 그 뒤 실습의 호출이 쌓여 최근 50건 기록 밖으로 밀린다(한바퀴3: 「이 질문 0건」).
    # 대조할 호출은 지식에서 온 근거(절차 · 역할 · 원인 id)를 돌려준 조회다 — 스키마 조회처럼 근거 id 가 없는 호출과 견주지 않는다
    facts = lambda text: set(re.findall(r"SOP-[A-Z0-9-]+|(?:skill|role|fm|cause):[a-z0-9-]+", text or ""))   # noqa: E731
    mine = ensure_my_agent(r)
    asked = ask(r, mine["id"], QUESTION) if mine else {}
    call = next((c for c in asked.get("tool_calls") or [] if str(c.get("raw_tool") or c.get("tool")).endswith("read_neo4j_cypher") and c.get("ok") and c.get("data")
                 and facts(c.get("output_text"))), None)
    if not call:
        r.check("질문의 호출 기록에 지식 그래프 조회가 있다", False, str([c.get("tool") for c in asked.get("tool_calls") or []])[:300]); return
    mcp_select(r, "neo4j")
    page.locator("[data-mcp-tab='calls']").click()
    r.wait(20, lambda: page.locator(".mcp-calls li").count() or "아직" in txt(r, "#mcpPane"), every=1)
    api_calls = r.get(f"{r.process}/api/mcp/calls?server=neo4j&limit=50").get("calls") or []
    mine_calls = [c for c in api_calls if c.get("proc_inst_id") == asked.get("id")]
    r.check("도구 연결 화면의 호출 기록에 그 질문 처리 건의 호출이 있다(도구 이름 · 입력 · 결과 — 화면 줄 수 = 기록)",
            bool(mine_calls) and page.locator(".mcp-calls > li").count() == len(api_calls),
            f"이 질문 {len(mine_calls)}건 · 기록 {len(api_calls)} · 화면 {page.locator('.mcp-calls > li').count()}")
    page.locator("[data-mcp-tab='tools']").click()
    page.locator("#mcpPane [data-try='read_neo4j_cypher']").wait_for(timeout=15_000)
    again = mcp_try(r, "read_neo4j_cypher", {k: v for k, v in (call.get("input") or {}).items() if v is not None})
    r.check("에이전트가 쓴 조회를 화면에서 직접 다시 부르면 같은 반환값(지식에서 온 근거 — 절차 · 역할 · 원인 id)", bool(facts(call.get("output_text")))
            # 질문 기록의 결과 글은 600자 미리보기(ask.py _preview) — 잘린 미리보기면 그 안의 근거가 직접 호출 결과에 모두 있어야 하고, 다 담겼으면 같아야 한다(한바퀴3)
            and (facts(call.get("output_text")) <= facts(again) if str(call.get("output_text") or "").endswith("…") else facts(call.get("output_text")) == facts(again)),
            f"기록 {sorted(facts(call.get('output_text')))[:8]} · 직접 {sorted(facts(again))[:8]}", kind="quality")
    r.keyless("키 없는 PC: 도구 직접 호출은 AI 없이 그대로 된다", "결과" in out, "")
    if phase != "course":
        r.not_measure("PBL 단계 개인 도구 서버 등록 · 써 보기", "학생 랩 시작본 서버가 main 에 없음 — PBL 수업에서 확인")


# ====================================================================== 11 통합 72 · 실전 57
@lab("11", [("통합", "사람의 확인이 실제 업무 결과를 바꾸는 과정 확인하기"), ("실전", "사람 승인에 따라 업무가 달라지는 과정 확인하기")])
def lab_11_human(r: Round):
    resolve_rows(r, "11")
    page = r.page
    pid, got = a_case(r)
    if not pid:
        r.check("[쿨러 열화] → 승인 대기 건", False, got["outcome"]); return
    try:
        if got["outcome"] != "승인 대기":
            r.check("승인 대기 건이 생긴다", False, f"{got['outcome']} {got.get('why') or ''}"); return
        view = got["view"]
        dec = decision_of(r, view)
        card = card_summary(dec)
        task = rows_of(view).get("T_approve") or {}
        inc = vars_of(view["instance"]).get("incident")
        r.tab("incidents")
        page.locator("#btnAllInc").click(); page.wait_for_timeout(800)
        page.locator(f"#incList .item[data-item-id='{inc}']").first.click(); page.wait_for_timeout(1500)
        det = all_txt(r, "#incDetail")
        r.evidence("설비 회로: 승인 전에 학생이 읽는 이 사건의 상세", det, "「읽을 수 있다」는 글의 양 · 낱말로 판정할 수 없다 — 원문을 읽는다")
        # 담당 배정: 사람은 이 PC의 담당자 한 명이고 모든 역할을 맡는다 — 화면에서 사람을 넣고 빼지 않는다(agents.js 「역할」 카드).
        # 이 카드의 승인 역할을 담당자가 맡고 있는지(업무분장 API)와 화면이 그렇게 말하는지 본다
        board = r.get(f"{r.process}/api/agent-assignments")
        members = {x["id"]: {m["id"] for m in x.get("members") or []} for x in board["roles"]}
        r.tab("agents"); page.locator('[data-ag-tab="assign"]').click()
        owned = "모든 역할은 이 PC의 담당자가 맡습니다"
        r.wait(15, lambda: owned in txt(r, "#view-agents"), every=0.5)
        shown = txt(r, "#view-agents", 5000)
        r.check("담당 배정: 「역할」 카드가 모든 역할을 담당자가 맡는다고 보이고, 이 카드의 승인 역할 구성원이 담당자 한 명(업무분장 API)",
                owned in shown and "담당자가 연결되어 있지 않아" not in shown and members.get(card.get("approver")) == {ME},
                f"승인 역할 {card.get('approver')} · 구성원 {sorted(members.get(card.get('approver')) or [])}")
        r.tab("instances")
        row = page.locator(f"#todoList .item[data-todo-task='{task.get('id')}']")
        seen = r.wait(20, lambda: row.count() > 0, every=1)
        row_text = row.first.inner_text() if seen else txt(r, "#todoList")
        r.check("승인 대기 건이 처리 건 화면 「내가 할 일」에 「승인 요청」 줄로 보인다(줄마다 그 일을 맡는 역할 칩 — instances.js renderTodo)", bool(seen) and "승인 요청" in row_text, row_text[:200])
        r.not_measure("권한 없는 사람이 승인 → 막힘 · 사람을 고르지 않았을 때의 안내",
                      "화면에 사람 · 역할 고르기가 없다(쓰는 사람은 담당자 한 명이고 모든 역할의 구성원 — www/inbox.js 머리말). 화면에서 만들 수 없는 길이라 "
                      "서버의 역할 검사(403)는 서버 시험(workspace/개발/tests)이 잰다", axis=AXES[1])
        done, text = card_decide(r, pid, task, approve=False, reason="부품 확인 후 다시 판단")
        end = wait_end(r, pid, 300)
        rows = rows_of(end)
        r.check("[반려] → 결과 보고(반려) 단계가 끝나고 설비 명령 단계(T_cmd)는 실행되지 않음", (rows.get("R_rejected") or {}).get("status") == "DONE" and (rows.get("T_cmd") or {}).get("status") != "DONE",
                f"{end['instance']['status']} · {text}", kind="exception", axis=AXES[1])
        approved = [c for c in r.memo.get("02_cards") or [] if c.get("result")]
        if approved:
            a = vars_of(view_of(r, approved[0]["pid"])["instance"])
            b = vars_of(end["instance"])
            r.check("승인했던 처리 건과 비교: 승인은 명령 · 작업지시, 반려는 둘 다 없음", bool(a.get("work_order")) and a.get("commands") and not b.get("work_order") and not b.get("commands"),
                    f"승인 {bool(a.get('work_order'))} · 반려 {bool(b.get('work_order'))}")
        else:
            r.not_measure("승인했던 처리 건과 비교", "02 를 함께 돌리지 않아 승인 처리 건이 없음")
    finally:
        restore_and_close(r, pid)


# ====================================================================== 12 통합 83 · 실전 62
@lab("12", [("통합", "같은 입력으로 에이전트 판단을 비교하고 기대 결과로 채점하기"), ("실전", "같은 입력으로 판단을 비교하고 기대 결과로 채점하기")])
def lab_12_compare_eval(r: Round):
    resolve_rows(r, "12")
    page = r.page
    mine = ensure_my_agent(r)
    if not mine:
        return
    before = instance_ids(r)
    cmds = lambda: {a: (u.get("status") or {}).get("cmdId") for a, u in r.get(r.plant + "/api/state")["units"].items()}   # noqa: E731 — 설비마다 마지막 명령
    gw0 = cmds()
    r.tab("compare")
    cv = lambda css: page.locator(f"#view-compare {css}")   # noqa: E731
    r.wait(20, lambda: cv("[data-f='scenario']").count(), every=1)
    cv("[data-f='scenario']").select_option("cooler")
    cv("[data-f='a']").select_option("agent:cooling")
    cv("[data-f='b']").select_option(mine["id"])

    def run_trial(label: str, axis: str) -> str:
        cv("[data-act='run']").click()
        r.wait(300, lambda: "시험 중" not in cv("[data-act='run']").inner_text() and (cv(".cmp-headline").count() or cv(".form-msg.neg").count()), every=2)
        out = txt(r, "#view-compare", 5000, required=True)
        ok = cv(".cmp-headline").count() > 0 and "도구 호출 순서" in out and "1순위" in out
        r.check(f"{label}: 결과에 비교 머리줄 · 「1순위」 · 「도구 호출 순서」 칸이 나온다", ok, out[:300], axis=axis)
        trials.append(ok)
        return out
    trials: list[bool] = []
    hist0 = {t.get("id") for t in r.get(f"{r.process}/api/agent-trials?limit=50")}
    run_trial("기준 vs 나의 에이전트", AXES[0])
    hist = [t for t in r.get(f"{r.process}/api/agent-trials?limit=50") if t.get("id") not in hist0]
    open_fold(cv("details:has([data-drop='tool'])").first)      # 「B를 바꿔 보기」 접기는 기본 닫힘(compare.js formCard) — 학생도 펴고 고른다(한바퀴3)
    cv("[data-drop='tool']").first.uncheck()
    page.wait_for_timeout(500)
    out = run_trial("도구 하나를 뺀 변형", AXES[0])
    r.check("뺀 도구가 「뺌」으로 보인다", "뺌" in out, out[:200])
    cv("[data-act='reset']").click(); page.wait_for_timeout(500)
    run_trial("원래대로 다시", AXES[3])
    r.check("시험 비교는 처리 건 · 설비 명령을 만들지 않는다", instance_ids(r) == before and cmds() == gw0,
            f"처리 건 {len(instance_ids(r) - before)} · 마지막 명령 {gw0} → {cmds()}", kind="exception", axis=AXES[1])
    r.check("방금 한 시험이 새 기록으로 남는다(앞 기록 id와 다른 행)", bool(hist), f"새 기록 {len(hist)}")
    # 판단 채점: 기대 판단을 정답표 항목으로 — 기대 원인은 그래프(쿨러 열화가 흔드는 외란의 원인), 원격 수동이면 원격 제어 조치가 빠져야 한다(원문 HM-8 8절)
    r.tab("eval")
    ev = lambda css: page.locator(f"#view-eval {css}")   # noqa: E731
    r.wait(20, lambda: ev("[data-act='new']").count(), every=1)
    cause = sorted(expected_causes(graph(r), "cooler_degradation"))[0]
    remote = [s for s in r.get(f"{r.process}/api/kg/skills") if s.get("kind") == "control" and any(f["id"] == "fm:cooler-cooling-loss" for f in s.get("failureModes") or [])]
    allowed = [s for s in r.get(f"{r.process}/api/kg/skills") if s.get("kind") != "control" and any(f["id"] == "fm:cooler-cooling-loss" for f in s.get("failureModes") or [])]
    item_id = f"class-round-{int(time.time()) % 100000}"
    ev("[data-act='new']").click()
    for key, val in (("title", "쿨러 성능 저하 · 원격 수동(수업 한 바퀴)"), ("id", item_id), ("cause", cause), ("failure_mode", "fm:cooler-cooling-loss"),
                     ("allowed_top", "\n".join(s["id"] for s in allowed)), ("forbidden", "\n".join(f"{s['id']} = 제외" for s in remote)),
                     ("required_evidence", "evd:cooler-fouling-ce-low")):      # 「누가」 칸은 없다 — 화면이 담당자 id 를 싣는다(evaluation.js meId)
        ev(f"[data-f='{key}']").fill(val)
    ev("[data-f='asset']").select_option("HYD-01")
    ev("[data-f='pattern']").select_option("COOLER_DEGRADATION")
    ev("[data-f='plc_mode']").select_option(json.dumps("REMOTE_MANUAL"))     # 가정 사실 고르기 값은 JSON 글(참 · 거짓도 담게 — evaluation.js sel)(한바퀴3)
    ev("[data-act='save']").click()
    saved = r.wait(15, lambda: any(i.get("id") == item_id for i in r.get(f"{r.process}/api/eval/golden").get("items") or []), every=1)
    r.check("정답표 항목을 적어 저장", bool(saved), txt(r, "#view-eval [data-msg='form']"))
    ev("[data-act='new']").click()
    ev("[data-f='forbidden']").fill("이건 형식이 아님")
    ev("[data-f='asset']").select_option("HYD-01")                           # 설비 · 이상 패턴은 미리 골라져 있지 않다 — 고르지 않으면 그 안내가 먼저 나온다(evaluation.js collect)
    ev("[data-f='pattern']").select_option("COOLER_DEGRADATION")
    ev("[data-act='save']").click(); page.wait_for_timeout(800)
    r.human("빠질 조치 줄 형식이 틀리면 사람 글로 막는다", txt(r, "#view-eval [data-msg='form']"))
    ev("[data-act='cancel']").click()
    ev(f"[data-pick='{item_id}']").check()
    ev("[data-f='repeats']").fill("3")
    runs0 = len(r.get(f"{r.process}/api/eval/runs?limit=50"))
    for n in (1, 2):
        ev("[data-act='run']").click()
        r.wait(300, lambda: "채점 완료" in txt(r, "#view-eval [data-msg='run']") or "neg" in (ev("[data-msg='run']").get_attribute("class") or ""), every=2)
        r.check(f"채점 실행({n}번째) → 채점 완료", "채점 완료" in txt(r, "#view-eval [data-msg='run']"), txt(r, "#view-eval [data-msg='run']"), axis=AXES[0] if n == 1 else AXES[3])
    runs = r.get(f"{r.process}/api/eval/runs?limit=50")
    latest = r.get(f"{r.process}/api/eval/runs/{runs[0]['id']}")
    item = next((i for i in latest.get("items") or [] if i.get("item") == item_id), {})
    r.check("채점 기록이 실행마다 남는다", len(runs) - runs0 == 2, f"{runs0} → {len(runs)}")
    r.check("여러 번 채점해도 결과가 매번 같다(규칙 판단 3회 모두 같음)", item.get("identical") is True and item.get("repeats") == 3, json.dumps({k: item.get(k) for k in ("repeats", "identical", "score")}),
            axis=AXES[3])
    eng = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "facts": {"plc_mode": "REMOTE_MANUAL"}})[1] or {}
    opts = {o["id"]: o for o in ((eng.get("result") or eng).get("options") or [])}
    truly = all(not (opts.get(s["id"]) or {}).get("feasible", True) for s in remote)
    fb = (item.get("checks") or {}).get("forbidden") or {}
    r.check("채점의 「빠질 조치」 판정이 판단 엔진 결과와 같다(기대와 다른 항목은 까닭과 함께)", bool(fb) and fb.get("ok") == truly,
            f"채점 {fb.get('ok')} · 엔진 제외 {truly} · {json.dumps(fb.get('detail'), ensure_ascii=False)[:200]}", kind="quality")
    ev(f"[data-run='{runs[0]['id']}']").click(); page.wait_for_timeout(1500)
    detail = txt(r, "#view-eval [data-r='detail']", 5000)
    r.check("실행 기록 화면에 검사 네 칸(원인 · 1위 · 빠질 조치 · 근거)이 보인다", all(w in detail for w in ("원인 적중", "1위 허용", "빠질 조치", "근거")), detail[:300])
    r.check("채점은 처리 건 · 설비 명령을 만들지 않는다", instance_ids(r) == before and cmds() == gw0, "", kind="exception", axis=AXES[1])
    r.keyless("키 없는 PC: 이 실행의 시험 비교 세 번 · 판단 채점 두 번이 끝까지 됐다", len(trials) == 3 and all(trials) and len(runs) - runs0 == 2,
              f"시험 {trials} · 채점 기록 {len(runs) - runs0}")
    ev(f"[data-edit='{item_id}']").click(); page.wait_for_timeout(500)
    ev("details").filter(has_text="이 항목 지우기").locator("summary").click()
    ev("[data-act='delete']").click()
    if not confirm_ok(r):                                                 # 지우기는 먼저 묻는다(evaluation.js — UI.confirm)
        raise ScreenMissing("[지우기]의 확인 창이 뜨지 않음")
    r.check("시험 항목을 지운다(지난 실행 기록은 남음)", bool(r.wait(15, lambda: not any(i.get("id") == item_id for i in r.get(f"{r.process}/api/eval/golden").get("items") or []), every=1)),
            "", axis=AXES[1])


# ====================================================================== 13 통합 98 · 실전 76
CLASS_STEPS = {"c3_cooling": ("T_agent", "T_approve", "T_cmd", "T_reobs"), "c3_pm": ("T_agent", "T_approve", "T_wo"), "c3_spare": ("T_agent", "T_approve", "T_po", "T_gr")}


def import_flow(r: Round, xml: str, file_name: str) -> tuple[str, bool]:
    """[흐름 가져오기]: 파일 고르기 → [가져오기]. 수업 단계에서는 흐름 id 칸이 잠겨 그림의 프로세스 id 를 쓴다. (메시지, 성공?)"""
    r.tab("flows")
    r.page.wait_for_selector("#flowFile", state="attached")
    r.page.set_input_files("#flowFile", files=[{"name": file_name, "mimeType": "application/xml", "buffer": xml.encode("utf-8")}])
    r.page.click("#flowImport")
    msg = r.page.locator("#flowImportMsg")
    r.wait(30, lambda: msg.inner_text().strip() not in ("", "읽는 중…"), every=0.5)
    text = msg.inner_text().strip()
    ok = "form-msg pos" in (msg.get_attribute("class") or "") or text.startswith(("가져왔습니다", "다시 가져왔습니다"))      # flows.js importFlow
    if ok:
        r.page.wait_for_selector("#flowEditor #flowCheck"); r.page.wait_for_timeout(900)
    return text, ok


def structurally_changed(xml: str) -> str:
    """제공 교대 그림에서 연결선 하나를 지운 그림 — 형식은 맞는 BPMN 2.0 이지만 「이름 · 배치만 바꾼 그림」이 아니다."""
    ns = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
    root = ET.fromstring(xml)
    proc = root.find(f"{ns}process")
    flow = proc.findall(f"{ns}sequenceFlow")[-1]
    proc.remove(flow)
    return ET.tostring(root, encoding="unicode")


@lab("13", [("통합", "작성한 BPMN과 등록된 실행 흐름의 연결 비교하기"), ("실전", "작성한 BPMN과 등록된 작업의 실행 연결 비교하기")])
def lab_13_flow_mapping(r: Round):
    resolve_rows(r, "13")
    page = r.page
    rt = routes(r)
    want = {"COOLER_DEGRADATION": "c3_cooling", "PM_DUE": "c3_pm", "SPARE_BELOW_MIN": "c3_spare"}
    r.check("경보 경로: 쿨러 · 정기 점검 · 재고 부족 → 준비된 수업 흐름", all((rt.get(k) or {}).get("definition") == v and (rt.get(k) or {}).get("class_flow") is True for k, v in want.items()),
            json.dumps({k: (rt.get(k) or {}).get("definition") for k in want}, ensure_ascii=False))
    for did, steps in CLASS_STEPS.items():
        acts = {x.get("id"): x for x in class_definition(r, did).get("activities") or []}
        r.check(f"{did}: 등록 흐름에 비교할 작업 · 승인 역할이 있다", all(s in acts for s in steps) and bool((acts.get("T_approve") or {}).get("role")),
                ", ".join(f"{s}={(acts.get(s) or {}).get('name')}" for s in steps))
    # 등록된 냉각 대응 흐름의 [매핑 열기] — 시작 조건 · 에이전트 · 운전원 역할 · 시스템 기능 · 분기 조건을 화면에서 읽는다(= 배포된 정의)
    defn = class_definition(r, "c3_cooling")
    acts = {a["id"]: a for a in defn["activities"]}
    mapping = r.get(f"{r.process}/api/flows/c3_cooling")["mapping"]
    opened: list[bool] = []
    for n in (1, 2):
        r.tab("flows")
        btn = page.locator("#flowList [data-open='c3_cooling']").first
        if not r.wait(15, lambda: btn.count(), every=1):
            r.check("흐름 가져오기 목록에 등록된 냉각 대응 흐름의 [매핑 열기]가 있다", False, txt(r, "#flowList")[:200]); return
        btn.click()
        r.page.wait_for_selector("#flowEditor table.flow-map", timeout=15_000); page.wait_for_timeout(1200)
        start_ok = page.locator("#flowEditor input[name=flowStart][value=alert]").is_checked() and page.locator("#flowEditor [data-pattern='COOLER_DEGRADATION']").is_checked()
        agent = page.locator("#flowEditor select[data-agent='T_agent']").input_value() if page.locator("#flowEditor select[data-agent='T_agent']").count() else None
        role = page.locator("#flowEditor select[data-role='T_approve'] option:checked").inner_text() if page.locator("#flowEditor select[data-role='T_approve']").count() else None
        parts = {t: page.locator(f"#flowEditor select[data-part='{t}']").input_value() for t in mapping["tasks"]
                 if page.locator(f"#flowEditor select[data-part='{t}']").count()}
        conds = {f: page.locator(f"#flowEditor select[data-var='{f}']").input_value() for f, spec in mapping["flows"].items()
                 if not spec.get("default") and page.locator(f"#flowEditor select[data-var='{f}']").count()}
        r.check(f"[매핑 열기]({n}번째): 쿨러 경보 시작 · 진단 에이전트 · 운전원 승인 역할(= 배포된 정의) · 단계별 실행 기능 · 승인/반려 · 회복 분기 조건(= 저장된 매핑)",
                start_ok and agent == acts["T_agent"].get("agent") and (role or "").strip() == acts["T_approve"]["role"]
                and parts == {t: m["part"] for t, m in mapping["tasks"].items()}
                and conds == {f: spec["var"] for f, spec in mapping["flows"].items() if not spec.get("default")},
                f"시작 {start_ok} · 에이전트 {agent} · 역할 {role} · 기능 {parts} · 조건 {conds}", axis=AXES[0] if n == 1 else AXES[3])
        opened.append(bool(start_ok) and bool(parts))
    if course_phase(r) == "course":
        # 강사가 설치한 수업 흐름은 매핑을 읽기만 한다 — [저장 · 검사] · [판본 등록] 단추 대신 그 까닭 한 줄(flows.js actionsHtml class_flow)
        hint = txt(r, "#flowEditor #flowActions .field-hint")
        r.human("수업 흐름 매핑은 저장 단추 없이 읽기만 하고 까닭이 사람 글", hint, page.locator("#flowEditor #flowCheck").count() == 0 and "읽기만" in hint)
        r.check("매핑을 열어 봐도 배포된 수업 흐름 · 저장된 매핑이 그대로", routes(r) == rt and r.get(f"{r.process}/api/flows/c3_cooling")["mapping"] == mapping, "",
                kind="exception", axis=AXES[1])
    # 준비되지 않은 흐름 가져오기: 형식은 맞지만 구조를 바꾼 제공 교대 그림 → 403(수업 경계), 깨진 그림 → 400(형식) — 둘 다 사람 글
    shipped = (ROOT / "it/process/definitions/shift_handover.bpmn").read_text(encoding="utf-8")
    code, body = r.api("POST", f"{r.process}/api/flows/import", {"xml": structurally_changed(shipped), "file_name": "changed.bpmn"})
    detail = (body or {}).get("detail") if isinstance(body, dict) else body
    reason = detail.get("reason") if isinstance(detail, dict) else detail
    if course_phase(r) == "course":
        r.human("수업 단계: 구조를 바꾼 교대 그림은 서버가 거절(403)", reason, code == 403)
    else:                                                                 # PBL 단계는 학생 흐름을 받는다(course_policy — phase.pbl 이면 구조 검사 없음)
        r.check("PBL 단계: 구조를 바꾼 교대 그림을 서버가 받는다(2xx)", 200 <= code < 300, f"{code} {str(body)[:200]}")
    code, body = r.api("POST", f"{r.process}/api/flows/import", {"xml": "<definitions/>", "file_name": "diagram.bpmn"})
    detail = (body or {}).get("detail") if isinstance(body, dict) else body
    reason = detail.get("reason") if isinstance(detail, dict) else detail
    r.human("BPMN 이 아닌 파일은 형식 검사가 거절(400)", reason, code == 400)
    r.check("거절 뒤 경보 경로는 그대로", routes(r) == rt, kind="exception", axis=AXES[1])
    r.keyless("키 없는 PC: 이 실행의 [매핑 열기]가 매번 시작 · 단계 기능을 그렸다", bool(opened) and all(opened), f"열기 {opened}")


# ====================================================================== 14 통합 99 · 실전 78
@lab("14", [("통합", "실제 설비 이벤트로 프로세스를 실행하고 처리 이력 확인하기"), ("실전", "실제 설비 이벤트로 프로세스의 처리 결과 검증하기")])
def lab_14_history(r: Round):
    resolve_rows(r, "14")
    page = r.page
    pid, got = a_case(r)
    if not pid:
        r.check("[쿨러 열화] → 처리 건", False, got["outcome"]); return
    try:
        if got["outcome"] != "승인 대기":
            r.check("판단 → 승인 대기", False, f"{got['outcome']} {got.get('why') or ''}"); return
        view = got["view"]
        r.check("처리 건이 어느 흐름 · 판본으로 열렸는지(= 경보 경로의 수업 흐름)", view["instance"]["proc_def_id"] == routes(r)["COOLER_DEGRADATION"]["definition"],
                f"{view['instance']['proc_def_id']} v{view['instance'].get('proc_def_version')}")
        # 다시 수행의 [영향 확인] — 미리 보기만(제출하지 않는다), 승인 대기 중인 처리 건에서
        select_instance(r, pid)
        fold = page.locator("#instDetail details", has_text="다시 수행").first
        if fold.count() and not fold.evaluate("d => d.open"):
            fold.locator("summary").first.click()
        for n, start in ((1, "T_agent"), (2, "T_approve")):
            wid = (rows_of(view_of(r, pid)).get(start) or {}).get("id")
            r.page.wait_for_selector("#rwStart", timeout=15_000)
            page.select_option("#rwStart", wid)
            page.click("#rwPreview")
            r.wait(30, lambda: "영향받는 단계" in txt(r, "#instDetail") or page.locator("#instDetail .neg").count(), every=1)
            pv = r.get(f"{r.process}/api/instances/{urllib.parse.quote(pid, safe='')}/rework-preview?workitem_id={wid}")
            shown = txt(r, "#instDetail", 5000)
            r.check(f"다시 수행 [영향 확인]({start}부터): 영향받는 · 취소될 단계 수가 화면 = 서버", f"영향받는 단계 {len(pv['affected_workitems'])}건" in shown
                    and f"취소될 단계 {len(pv['cancel_workitems'])}건" in shown, shown[shown.find("영향 범위"):][:200], axis=AXES[0] if n == 1 else AXES[3])
        v_after = view_of(r, pid)
        r.check("[영향 확인]은 미리 보기만 — 처리 건 · 단계가 그대로", [(w["id"], w["status"]) for w in v_after["workitems"]] == [(w["id"], w["status"]) for w in view_of(r, pid)["workitems"]]
                and v_after["instance"]["status"] == "RUNNING" and not v_after.get("reworks"), "", kind="exception", axis=AXES[1])
        card_decide(r, pid, rows_of(view).get("T_approve") or {}, approve=True)
        end = wait_end(r, pid, 600)
        rows = rows_of(end)
        names = {x["id"]: x.get("name") for x in end["definition"].get("activities") or []}
        r.check("판단 · 승인 · 명령 · 재관측이 모두 끝났다", end["instance"]["status"] == "COMPLETED" and all((rows.get(k) or {}).get("status") == "DONE" for k in CLASS_STEPS["c3_cooling"]),
                end["instance"]["status"])
        select_instance(r, pid)
        page.locator("#instDetail [data-inst-tab='record']").click(); page.wait_for_timeout(1500)
        rec = page.locator("#instDetail").inner_text()
        order = [rec.find(names[k]) for k in CLASS_STEPS["c3_cooling"]]
        r.check("처리 기록에 단계가 순서대로(판단 → 승인 → 명령 → 재관측)", all(i >= 0 for i in order) and order == sorted(order), str(order))
        r.check("처리 기록에 승인한 사람이 이름으로 보인다", vars_of(end["instance"]).get("approved_by_name", "@@") in rec, vars_of(end["instance"]).get("approved_by_name"))
        wo = (vars_of(end["instance"]).get("work_order") or {}).get("ref")
        wo_row = next((o for o in ent(r)["cmms"]["work_orders"] if o.get("id") == wo), {})
        r.check("명령 처리 · 온도 회복과 작업지시 등록 · 정비 완료를 따로 확인(작업지시는 등록만 — 완료 아님)", vars_of(end["instance"]).get("recovered") is True
                and bool(wo) and wo_row.get("status") != "완료" and wo in rec, f"회복 {vars_of(end['instance']).get('recovered')} · {wo} {wo_row.get('status')}")
        # 처리 기록에서 단계를 펼쳐 도구 호출 원문을 다시 읽는다 — 화면의 원문 = 이벤트 기록
        page.locator("#instDetail [data-cr-all]").click(); page.wait_for_timeout(1500)
        # 보조 작업(쓸 도구 불러오기 · 파일 쓰기 · 명령 실행 — li.minor)은 [보조 작업도 보기] 전에는 숨어 있다(caseRecord.js) — 업무 도구 호출을 연다(한바퀴3)
        # 단계를 펼쳐도 도구 호출은 그 단계의 「도구 호출 n회」 접기(details.cr-tools) 안에 닫혀 있다 — 학생처럼 그 접기를 먼저 편다
        call = page.locator("#instDetail li.cr-r.tool:not(.minor) details.cr-call").first
        if call.count():
            open_fold(call.locator("xpath=ancestor::details[contains(concat(' ', @class, ' '), ' cr-tools ')]").first)
            call.locator(":scope > summary").click(); page.wait_for_timeout(500)
            raw = call.inner_text()
            tool = call.locator("code").first.inner_text()
            starts = [e for e in end["events"] if e["event_type"] == "tool_usage_started" and (e.get("data") or {}).get("tool") == tool]
            inp = json.dumps((starts[0].get("data") or {}).get("input"), ensure_ascii=False, indent=2) if starts else ""
            r.check("처리 기록 단계를 펼치면 도구 호출 원문(요청 원문)이 이벤트 기록과 같다", bool(starts) and all(line.strip() in raw for line in inp.splitlines()[:4]), f"{tool} · {inp[:120]}")
        else:
            r.check("처리 기록에 도구 호출 단계가 있다", False, rec[:200])
        statuses = {c.get("pid"): c.get("end") for c in r.memo.get("02_cards") or []}
        if statuses:
            r.check("승인 대기 · 정상 종료 · 반려로 끝난 처리 건을 처리 건 목록에서 구분", all(view_of(r, p)["instance"]["status"] == s for p, s in statuses.items() if p and s), str(statuses))
        else:
            r.not_measure("앞 처리 건들과 상태 비교", "02 를 함께 돌리지 않음")
        r.keyless("키 없는 PC: 이 처리 건의 판단이 녹화로 끝까지", ai_source(session_of(rows.get("T_agent") or {})) == "강사 녹화 재생", ai_source(session_of(rows.get("T_agent") or {})))
    finally:
        restore_and_close(r, pid)


# ====================================================================== 15 · 16 정비(B) · 구매(C)
def tx_after(r: Round, decision_id: str) -> list[dict]:
    return r.get(f"{r.enterprise}/api/transactions?decision={urllib.parse.quote(decision_id)}") or []


def open_fold(fold) -> None:
    """접기(details) 하나를 편다. 접기 안의 목록(거래마다 details)에도 summary 가 있어 「summary」만으로 고르면 여럿이 걸린다(한바퀴3: 두 번째
    실행부터 strict mode violation) — 이 접기 자신의 summary(:scope > summary)만 누른다."""
    if not fold.evaluate("d => d.open"):
        fold.locator(":scope > summary").click()


def process_screen_shows(r: Round, refs: list[str]) -> tuple[bool, str]:
    """업무 시스템 기록 화면(유압 실습장 메뉴의 process 탭)의 업무 시스템 현황 · 거래(변경 전 · 후)에 그 거래들이 보이는가."""
    r.tab("process")
    r.page.wait_for_timeout(3000)
    # 거래 기록은 표 한 장이고(접기 #txFold 는 없어졌다 — 보기 「거래 기록」이 처음부터 펴져 있다), 줄(details.tx)을 누르면 변경 전 · 후가 그 아래에 열린다.
    # 줄 안의 원문 접기에도 summary 가 있으므로 줄 자신의 summary 만 누른다(open_fold)
    for d in r.page.locator("#txList details.tx").all()[:12]:
        try:
            open_fold(d)
        except Exception as e:
            if not transient(e):
                raise
    text = all_txt(r, "#sysBoards") + " " + all_txt(r, "#txList")
    missing = [x for x in refs if x and x not in text]
    return not missing and "변경 전" in text, f"없음 {missing} · {text[:200]}"


def biz_round(r: Round, kind: str, asset: str, check_effects) -> list[dict]:
    """B · C 공통: AI 3회(같은 입력) — 1회 반려(효과 없음), 2회 승인(효과), 3회 「이미 처리됨」 → [초기화] → 다시 눌러 → 반려."""
    did = {"pm": "c3_pm", "spare": "c3_spare"}[kind]
    label = {"pm": "내 정기 정비", "spare": "내 예비품 구매"}[kind]
    pattern = next((p for p, x in routes(r).items() if x.get("definition") == did), None)
    defn = class_definition(r, did)
    approve = next((x for x in defn.get("activities") or [] if x.get("id") == "T_approve"), {})
    approver = next((x.get("endpoint") for x in defn.get("roles") or [] if x.get("name") == approve.get("role")), None)
    if not approve.get("name") or not approver or not pattern:
        r.check(f"{label}: 준비된 흐름의 승인 단계 · 역할 · 경보 패턴을 읽었다", False, json.dumps(approve, ensure_ascii=False)[:300]); return []
    source = approvers_of("PM-02" if kind == "pm" else "PR-07")

    def run_once(i):
        rec: dict = {}
        if i == 2:
            msg = unit_button(r, asset, "biz-start")
            r.human(f"{label}: 처리된 뒤 다시 누르면 「이미 처리됐습니다 · [초기화]」", msg.replace("실패: ", ""), msg.startswith("실패:") and "초기화" in msg, axis=AXES[3])
            msg = unit_button(r, asset, "biz-reset")
            r.check(f"{label}: [초기화] → 업무 데이터를 수업 시작값으로", "초기화" in msg and not msg.startswith("실패:"), msg, kind="exception", axis=AXES[3])
            chip = biz_chip(r, asset)
            r.check(f"{label}: [초기화] 뒤 표시가 다시 켜진다", chip in ("정기 점검 도래", "재고 보충 필요"), chip, kind="exception", axis=AXES[3])
        before = instance_ids(r)
        ent0 = ent(r)
        msg = unit_button(r, asset, "biz-start")
        inst = new_instance(r, before, None, 60)
        if not inst:
            return {"error": f"처리 건이 열리지 않음: {msg}"}
        pid = inst["proc_inst_id"]
        rec["definition"] = inst["proc_def_id"]
        state, why, view = wait_step(r, pid, approve["name"], SECONDS["agent"])
        rec["seconds"] = agent_seconds(view)          # 처리 건의 실제 시각으로(실습 02와 같은 잣대) — 이 도구가 처리 건을 본 순간부터 재면 짧게 나왔다
        rec["ai"] = ai_source(session_of(rows_of(view).get("T_agent") or {}))
        if state != "ready":
            rec["error"] = f"승인 차례가 오지 않음({state}: {why})"
            # 열린 처리 건을 학생처럼 닫는다 — 다음 실습([초기화] · 재고 표시)이 이 건에 막히지 않게
            open_w = next((w for w in view.get("workitems") or [] if w["status"] in ("PENDING", "IN_PROGRESS") and w.get("agent_mode")), None)
            if view["instance"]["status"] == "RUNNING" and open_w:
                closed = close_step(r, pid, open_w["id"], "수업 한 바퀴: 멈춘 단계를 닫고 다음으로 넘어갑니다")
                rec["closed"] = closed
            return rec
        dec = decision_of(r, view)
        rec.update(card_summary(dec))
        bad = card_findings(dec, source)
        if kind == "spare":
            stock = r.get(f"{r.enterprise}/erp/spare_stock?part={(dec.get('origin') or {}).get('part', {}).get('partNo') or 'P-PMP-SEAL'}")["facts"]
            bad += purchase_findings(dec, stock)
        else:
            biz = r.api("GET", f"{r.enterprise}/cmms/pm_status?asset={asset}")[1].get("facts") or {}
            if not biz.get("pm_alert"):
                bad.append("정기 점검 도래 표시가 없는데 판단이 나옴")
        r.check(f"{label} {i + 1}회: 추천 = 실행 가능한 1순위 · 제외 카드에 규칙 · 승인 역할 = 원문"
                + (" · 공급사(AVL) · 수량 · 총비용(업무 DB · PR-07)" if kind == "spare" else " · 정기 점검 도래 표시가 있음"), not bad, "; ".join(bad) or json.dumps(card_summary(dec), ensure_ascii=False)[:300],
                kind="quality")
        task = item_named(view, approve["name"])
        if i == 0:
            open_task(r, pid, task["id"])
            r.page.fill("#tdReason", "")
            r.page.click("#tdRejectCard"); r.page.wait_for_timeout(600)
            r.human(f"{label}: 사유 없이 [반려] → 「반려 사유를 1~2000자로 적으세요」", panel_msg(r), "반려 사유" in panel_msg(r))      # instances.js rejectCard
        ok_d, pmsg = card_decide(r, pid, task, approve=(i == 1), reason=f"실습 {label} 승인" if i == 1 else "실습: 이번 회차는 보류합니다")
        fin = wait_end(r, pid, 300)
        rec["outcome"] = (vars_of(fin["instance"]).get("result_report") or {}).get("outcome")
        check_effects("approve" if i == 1 else "reject", ent0, fin, i, dec)
        return rec

    runs = r.repeat3(f"{label} 판단 · 제안", run_once, ("definition", "recommended", "approver", "evidence") + (("window",) if kind == "pm" else ("supplier", "qty", "amount")),
                     limit_s=AGENT_LIMIT_S, single=1)
    ok_outcome = "정상" if kind == "pm" else "입고 완료"
    r.check(f"{label}: 처리 건이 모두 준비된 수업 흐름으로 열렸다", all(x.get("definition") == did for x in runs), str([x.get("definition") for x in runs]))
    r.check(f"{label}: 카드 승인 역할 = 흐름 승인 담당({approve.get('role')})", all(x.get("approver") == approver for x in runs if not x.get("error")), str([x.get("approver") for x in runs]))
    r.check(f"{label}: [반려] → 반려, 승인 → 정상 종결", [x.get("outcome") for x in runs] == (["반려", ok_outcome, "반려"] if r.ai_runs >= 3 else [ok_outcome]), str([x.get("outcome") for x in runs]))
    route = routes(r).get(pattern) or {}
    r.check(f"{label}: 실행 뒤에도 경보 경로는 준비된 수업 흐름", route.get("definition") == did and route.get("class_flow") is True, json.dumps(route, ensure_ascii=False), axis=AXES[3])
    return runs


@lab("15", [("통합", "정기 점검 프로세스를 실제 업무로 실행하기"), ("실전", "정비 프로세스를 실행하고 승인 조건 검증하기")])
def lab_15_pm(r: Round):
    resolve_rows(r, "15")

    def effects(stage, ent0, fin, i, dec):
        v = vars_of(fin["instance"])
        ent1 = ent(r)
        wo0, wo1 = len(ent0["cmms"]["work_orders"]), len(ent1["cmms"]["work_orders"])
        mails = mail(r, MAILS["production"])
        pm = r.get(f"{r.enterprise}/cmms/pm_status?asset=HYD-02")["facts"]
        if stage == "reject":
            r.check(f"B {i + 1}회 반려 → CMMS 정비 오더 없음 · 이번 오더 번호의 생산 공지 없음 · 도래 표시 그대로", wo1 == wo0 and not (v.get("work_order") or {}).get("ref")
                    and pm.get("pm_alert") is True and biz_chip(r, "HYD-02") == "반려", f"{wo0}→{wo1} · pm_alert {pm.get('pm_alert')}", kind="exception", axis=AXES[1])
        else:
            ref = (v.get("work_order") or {}).get("ref")
            subj = [m.get("Subject") for m in mails if ref and ref in (m.get("Subject") or "")]
            r.check("B 승인 → CMMS 정비 오더 1건 · 생산팀 공지 메일 · 도래 표시 꺼짐 · 카드 칩 「처리됨」", wo1 == wo0 + 1 and bool(ref) and bool(subj) and pm.get("pm_alert") is False
                    and "처리됨" in biz_chip(r, "HYD-02"), f"{wo0}→{wo1} ref={ref} · {subj[:1]}")
            refs = [ref] + [t.get("ref") or t.get("id") for t in tx_after(r, dec.get("id", "")) if t.get("ref") or t.get("id")][:3]
            ok, note = process_screen_shows(r, [x for x in refs if x])
            r.check("업무 시스템 기록 화면: 업무 시스템 현황 · 거래에 작업지시 · 부품 예약 · 공지의 변경 전 · 후", ok, note)
    biz_round(r, "pm", "HYD-02", effects)


@lab("16", [("통합", "구매 프로세스를 실제 업무로 실행하기"), ("실전", "구매 프로세스를 실행하고 처리 결과 검증하기")])
def lab_16_spare(r: Round):
    resolve_rows(r, "16")

    def effects(stage, ent0, fin, i, dec):
        v = vars_of(fin["instance"])
        ent1 = ent(r)
        pr0, pr1 = len(ent0["erp"]["purchase_requests"]), len(ent1["erp"]["purchase_requests"])
        gr0, gr1 = len(ent0["erp"]["goods_receipts"]), len(ent1["erp"]["goods_receipts"])
        stock = r.get(f"{r.enterprise}/erp/spare_stock?part=P-PMP-SEAL")["facts"]
        if stage == "reject":
            r.check(f"C {i + 1}회 반려 → ERP 발주 · 입고 없음 · 승인 값 비어 있음 · 재고 보충 필요 그대로", pr1 == pr0 and gr1 == gr0 and not v.get("purchase_order")
                    and not any(v.get(k) for k in ("approved_supplier", "approved_qty", "approved_amount")) and stock.get("below_reorder_point") is True,
                    f"PR {pr0}→{pr1} GR {gr0}→{gr1}", kind="exception", axis=AXES[1])
        else:
            ref = (v.get("purchase_order") or {}).get("ref")
            sup = [m.get("Subject") for m in mail(r, MAILS["supplier"]) if str(v.get("approved_qty")) in (m.get("Subject") or "")]
            r.check("C 승인 → ERP 발주 1건 · 입고 1건 · 공급사 · 입고 부서 메일 · 재고 반영(재주문점 이상) · 결과 보고 「입고 완료」",
                    pr1 == pr0 + 1 and gr1 == gr0 + 1 and bool(ref) and bool(sup) and bool(mail(r, MAILS["receiving"])) and stock.get("below_reorder_point") is False
                    and (stock.get("available") or 0) >= (stock.get("reorder_point") or 0) and (v.get("result_report") or {}).get("outcome") == "입고 완료",
                    f"PR {pr0}→{pr1} GR {gr0}→{gr1} ref={ref} · 재고 {json.dumps({k: stock.get(k) for k in ('on_hand', 'available', 'on_order', 'reorder_point')})}")
            ok, note = process_screen_shows(r, [ref])
            r.check("업무 시스템 기록 화면: 발주 · 통지 · 입고 · 재고 반영의 변경 전 · 후", ok, note)
    biz_round(r, "spare", "HYD-03", effects)


# ====================================================================== 17 통합 116~119 · 실전 95~98 교대 인수인계
def h_submit(r: Round, pid, task, values, *, expect_done=True):
    """교대 검토는 실제 작업함 폼으로 제출한다(인계자 · 인수자 역할 모두 담당자가 맡는다 — 제출하는 사람은 화면이 싣는다)."""
    open_task(r, pid, task['id'])
    form = task.get('form') or r.get(f"{r.process}/api/todolist/{task['id']}").get('form') or {}
    for index, f in enumerate(form.get('fields_json') or []):
        if f['key'] not in values:
            continue
        value = values[f['key']]
        control = r.page.locator(f'#tdField{index}')
        if f['type'] in ('select', 'boolean'):
            control.select_option(str(value).lower() if isinstance(value, bool) else str(value))
        else:
            control.fill(str(value))
    r.page.click('#tdDone')
    if not expect_done:
        r.wait(15, lambda: '설비 조치' in panel_msg(r), every=.5)
        return panel_msg(r)
    return bool(r.wait(45, lambda: item_named(view_of(r, pid), task['activity_name']).get('status') == 'DONE', every=2))


def set_fields(r: Round, editor, fields: list[dict]):
    if editor.locator("[data-add]").count() and editor.locator("[data-add]").first.is_disabled():
        # 수업 단계의 제공 교대 흐름: 칸 줄은 제공 연결로 채워져 잠겨 있다(flows.js W3-08) — 바라는 칸 이름이 다 있는지만 본다
        keys = {x.input_value() for x in editor.locator(".field-row:not(.head) [data-k=key]").all()}
        missing = [f["key"] for f in fields if f["key"] not in keys]
        if missing:
            raise ScreenMissing(f"잠긴 칸 줄에 바라는 칸이 없음: {missing} (화면 {sorted(keys)})")
        return
    for f in fields:
        editor.locator("[data-add]").click()
        row = editor.locator(".field-row:not(.head)").last
        row.locator("[data-k=key]").fill(f["key"])
        row.locator("[data-k=text]").fill(f.get("text") or f["key"])
        if (f.get("type") or "text") != "text":
            row.locator("select[data-k=type]").select_option(f["type"])
            row = editor.locator(".field-row:not(.head)").last
        if f.get("items"):
            row.locator("[data-k=items]").fill(", ".join(f["items"]))
    r.page.wait_for_timeout(500)


def map_row(r: Round, step_name: str) -> str:
    rows = r.page.locator("#flowEditor table.flow-map tr[data-row]")
    for i in range(rows.count()):
        row = rows.nth(i)
        if row.locator("td[data-label='단계'] b").inner_text().strip() == step_name:
            return row.get_attribute("data-row")
    raise ScreenMissing(f"매핑 표에 단계 '{step_name}' 이(가) 없습니다")


def apply_task(r: Round, step_name: str, m: dict):
    tid = map_row(r, step_name)
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    part = q(f"select[data-part='{tid}']")
    if part.is_disabled():
        # 수업 단계의 제공 교대 흐름은 흐름 이름과 초안 단계 에이전트만 열린다(flows.js W3-08) — 잠긴 칸은 제공한 값이 바라는 값과 같아야 한다
        if part.input_value() != m["part"]:
            raise ScreenMissing(f"단계 '{step_name}' 의 실행 기능 칸이 잠겼는데 값이 {part.input_value()!r} (바라는 값 {m['part']!r})")
        if m.get("agent") and q(f"select[data-agent='{tid}']").is_enabled():
            q(f"select[data-agent='{tid}']").select_option(m["agent"])
        return
    part.select_option(m["part"]); r.page.wait_for_timeout(900)
    if m.get("role"):
        q(f"select[data-role='{tid}']").select_option(label=m["role"])
    if m.get("agent"):
        q(f"select[data-agent='{tid}']").select_option(m["agent"])
    if m.get("instruction") is not None and q(f"textarea[data-instruction='{tid}']").count():
        q(f"textarea[data-instruction='{tid}']").fill(m["instruction"])
    if m.get("inputs") and q(f"input[data-inputs='{tid}']").count():
        q(f"input[data-inputs='{tid}']").fill(", ".join(m["inputs"]))
    if m.get("outputs"):
        set_fields(r, q(f"tr[data-row='{tid}'] [data-outputs='{tid}'][data-rows-of]").first, m["outputs"])
    if m.get("fields"):
        set_fields(r, q(f"tr[data-row='{tid}'] [data-fields='{tid}'][data-rows-of]").first, m["fields"])
    for key, val in (m.get("config") or {}).items():
        if key == "mail" and isinstance(val, dict):
            for mk, mv in val.items():
                q(f"[data-mail='{tid}'][data-mail-key='{mk}']").fill(str(mv))
            continue
        box = q(f"[data-service='{tid}'][data-cfg='{key}']")
        if box.count() == 0 and q(f"[data-approval='{tid}'][data-cfg='{key}']").count():
            q(f"[data-approval='{tid}'][data-cfg='{key}']").fill(str(val)); continue
        if box.evaluate("e => e.tagName") == "SELECT":
            box.select_option(str(val).lower() if isinstance(val, bool) else str(val))
        else:
            box.fill(json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val))
    r.page.wait_for_timeout(600)


def apply_start(r: Round, start: dict):
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    if start.get("kind") == "human":
        q("input[name=flowStart][value=human]").check(); r.page.wait_for_timeout(900)
        if start.get("fields"):
            set_fields(r, q("#flowStartFields[data-rows-of]").first, start["fields"])


def apply_branch(r: Round, fid: str, spec: dict):
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    if spec.get("default"):
        q(f"input[data-default='{fid}']").check(); r.page.wait_for_timeout(900); return
    var = q(f"select[data-var='{fid}']")
    if var.is_disabled():
        # 수업 단계의 제공 교대 흐름: 분기 칸은 제공 연결로 채워져 잠겨 있다(flows.js W3-08) — 값만 확인한다
        if var.input_value() != spec["var"]:
            raise ScreenMissing(f"분기 '{fid}' 의 값 칸이 잠겼는데 값이 {var.input_value()!r} (바라는 값 {spec['var']!r})")
        return
    var.select_option(spec["var"]); r.page.wait_for_timeout(900)
    q(f"select[data-op='{fid}']").select_option(spec.get("op") or "==")
    box = q(f"[data-value='{fid}']")
    val = spec.get("value")
    if box.evaluate("e => e.tagName") == "SELECT":
        box.select_option(label=str(val))
    else:
        box.fill("예" if val is True else "아니요" if val is False else str(val))
    r.page.wait_for_timeout(500)


def flow_check(r: Round) -> tuple[bool, list[str]]:
    r.page.click("#flowEditor #flowCheck")
    r.wait(30, lambda: r.page.locator("#flowMsg").inner_text().strip() not in ("", "검사 중…"), every=0.5)
    r.page.wait_for_timeout(600)
    return r.page.locator("#flowProblems .kv-line.pos").count() > 0, [x.inner_text().strip() for x in r.page.locator("#flowProblems .flow-problems li").all()]


def flow_register(r: Round) -> tuple[bool, str, str | None]:
    r.page.click("#flowEditor #flowRegister")
    msg = r.page.locator("#flowMsg")
    r.wait(30, lambda: ("등록" in msg.inner_text()) or "neg" in (msg.get_attribute("class") or ""), every=0.5)
    text = msg.inner_text().strip()
    m = re.search(r"판본 (\S+?)(?:을|를) 등록했습니다", text)
    return bool(m), text, (m.group(1) if m else None)


def handover_facts(r: Round, asset: str) -> tuple[list[str], bool]:
    """업무 DB 원천: 그 설비의 열린 작업지시 번호, 도착 예정 부품(발주 중 · 입고 전 구매요청)이 있는가."""
    state = ent(r)
    open_orders = [o["id"] for o in state["cmms"]["work_orders"] if o.get("asset") == asset and o.get("status") not in ("완료", "취소")]
    arriving = any(p.get("asset") == asset and p.get("status") not in ("입고 완료", "취소", "반려") for p in state["erp"]["purchase_requests"])
    return open_orders, arriving


@lab("17", [("통합", "교대 인수인계의 입력과 완료 조건 정의하기"), ("통합", "보충 매뉴얼을 추출 · 검토하여 기존 지식에 추가하기"),
            ("통합", "설비·정비·ERP를 대조하는 인수인계 에이전트 만들기"), ("통합", "교대 인수인계 BPMN을 등록하고 검토·확인 흐름 실행하기"),
            ("실전", "교대 인수인계의 입력과 완료 조건 정의하기"), ("실전", "보충 매뉴얼을 추출 · 검토하여 기존 지식에 추가하기"),
            ("실전", "설비·정비·ERP를 대조하는 인수인계 에이전트 만들기"), ("실전", "교대 인수인계 BPMN을 등록하고 검토·확인 흐름 실행하기")],
     title="교대 인수인계 — 입력 · 완료 조건 → 보충 매뉴얼 → 인수인계 에이전트 → BPMN 등록 · 검토 · 확인")
def lab_17_shift_handover(r: Round):
    resolve_rows(r, "17")
    page = r.page
    # 116(입력 · 완료 조건 정의)은 119(BPMN 등록 · 실행)보다 앞이다. 흐름 화면의 차례는 가져오기 → 시작 입력 정의(116) → 등록(119)이라 가져오기는
    # 116의 준비이지 119가 아니다 — 아래 「116행: 시작 입력 항목 = 교대 계약」(flow_register 로 등록하기 전에 잰다)으로 판정한다(2026-11-01: 가져오기 전에
    # 목록에 있어야 한다고 본 옛 판정은 가져오기를 119로 잘못 읽었다).
    r.tab("flows")
    before = {x['filename']: x['batch'] for x in r.get(f'{r.process}/api/kg/manuals') if x.get('current')}
    expected_hash = hashlib.sha256((SAMPLES / DOCS['HI-01']).read_bytes()).hexdigest()
    current = current_batch(r, 'HI-01')
    if not current or current.get('source_id', '').rsplit(':', 1)[-1] != expected_hash:
        if not ingest_manual(r, "HI-01", "보충 매뉴얼"):
            return
    after = {x['filename']: x['batch'] for x in r.get(f'{r.process}/api/kg/manuals') if x.get('current')}
    r.check('보충 자료 추가가 기존 제조 지식을 초기화하지 않음', all(after.get(name) == batch for name, batch in before.items() if name != DOCS['HI-01']), kind='quality',
            axis=AXES[3])
    taken = {x['skill_name'] for x in r.get(f'{r.process}/api/skills')}
    sid = next(f'my_shift_handover{n or ""}' for n in range(100) if f'my-shift-handover{n or ""}-review' not in taken)
    skill = sid.replace('_', '-') + '-review'
    r.tab('agents'); page.locator('[data-ag-tab="skills"]').click()
    page.locator('[data-new-skill]').click()
    page.locator('[data-f="skill_name"]').fill(skill)
    page.locator('[data-f="description"]').fill('설비·정비·부품·작업 메모를 대조하는 교대 인수인계')
    page.locator('[data-f="content"]').fill(
        '# 교대 인수인계 검토\n\n작업 메모는 주장이다. 실제 설비 상태, 열린 작업지시, 실제 재고와 입고 예정을 각각 조회한다. '
        'HI-01 보충 매뉴얼의 확인 절차를 참고한다. 정비 완료 메모와 열린 작업지시가 다르면 모순으로 기록한다. '
        '자료가 없으면 확인 필요로 남긴다. 실제 조회 도구·질의·결과를 근거로 남기며 없는 완료를 만들지 않는다. '
        '인수자의 보완 요청을 반영한다. 확인은 인계 기록이며 설비 조치·발주·정비 완료가 아니다. 읽기만 수행한다.')
    page.locator('[data-ag-form] button[type="submit"]').click()
    saved = r.wait(15, lambda: any(x['skill_name'] == skill for x in r.get(f'{r.process}/api/skills')), every=1)
    r.check('학생 교대 스킬 저장', bool(saved))
    if not saved:
        return
    page.locator('[data-ag-tab="agents"]').click(); page.locator('[data-new-agent]').click()
    page.locator(f'[data-f-skill][value="{skill}"]').check()
    page.locator('[data-f="work_rules"]').select_option('hyd-handover')
    agent_name = '교대 인수인계 ' + sid
    error = agent_form(r, name=agent_name, role='인계안 작성 담당', goal='승인된 보충 매뉴얼과 현재 설비·정비·ERP를 대조하여 다음 교대가 확인하고 이어갈 일을 작성한다.',
                       persona='불일치와 정보 부족을 숨기지 않고 조회 근거를 남긴다.', tools=['neo4j', 'enterprise', 'hyd-dmn'])
    r.check('학생 교대 에이전트 저장', not error, error)
    mine = next((a for a in agents(r) if a.get('name') == agent_name), None)
    if error or not mine:
        return
    folder = ROOT / 'it/process/definitions'
    xml = (folder / 'shift_handover.bpmn').read_text(encoding='utf8')
    mapping = json.loads((folder / 'shift_handover.mapping.json').read_text(encoding='utf8'))
    elements = {e.get('id'): e for e in ET.fromstring(xml).iter() if e.get('id')}
    message, ok = import_flow(r, xml, 'handover.bpmn')
    r.check('교대 BPMN 가져오기', ok, message)
    if not ok:
        return
    apply_start(r, mapping['start'])
    keys = [x.input_value() for x in page.locator("#flowEditor #flowStartFields[data-rows-of] .field-row:not(.head) [data-k=key]").all()]
    r.check('116행: 시작 입력 항목(설비 · 교대 · 기준 시각 · 작업 메모) = 교대 계약', set(keys) == set(HANDOVER_START), f"화면 {keys} · 계약 {sorted(HANDOVER_START)}")
    for key, item in mapping['tasks'].items():
        value = dict(item)
        if 'agent' in value:
            value['agent'] = mine['id']
        apply_task(r, elements[key].get('name'), value)
    for key, value in mapping['flows'].items():
        apply_branch(r, key, value)
    passed, problems = flow_check(r)
    r.check('교대 시작 폼·역할·작업·분기 검사', passed, '; '.join(problems))
    if not passed:
        return
    registered, message, version = flow_register(r)
    r.check('교대 별도 정의·판본 등록', registered, message)
    if not registered:
        return
    did = 'ShiftHandover'
    page.locator(f"[data-start='{did}'][data-version='{version}']").click()
    box = page.locator(f"[data-startbox='{did}@{version}']")
    values = dict(asset='HYD-01', shift_label='다음 교대', as_of=datetime.now(timezone.utc).isoformat(),
                  work_notes='작업 메모: 정비 완료라고 전달받음. 부품 도착 예정이라고 전달받음. 실제 열린 작업지시와 현재 재고를 대조해야 함.')
    for key, value in values.items():
        box.locator(f"[data-sv='{key}']").fill(value)
    known = instance_ids(r); box.locator('[data-go]').click()
    inst = new_instance(r, known, did, 30)
    r.check('교대 시작 폼으로 한 처리 건 시작', bool(inst))
    if not inst:
        return
    pid = inst['proc_inst_id']
    for suffix in ('', ' · 보완 1'):
        name = '인계자 검토' + suffix
        state, why, view = wait_step(r, pid, name, AGENT_LIMIT_S * 2)
        r.check('교대 AI 조회·인계안 작성' + suffix, state == 'ready', f"{state} {why}")
        if state != 'ready':
            return
        data = vars_of(view['instance'])
        draft = next(w for w in view['workitems'] if w['activity_id'] == {'': 'task_draft', ' · 보완 1': 'task_draft_r2'}[suffix])
        if ai_source(session_of(draft)) == '강사 녹화 재생':
            # 재생은 강사 PC 에서 저장한 답이라 작업지시 번호 · 수치가 이 PC 와 다르다(설계 — 새로 추론하지 않음). 업무 DB 대조 대신 그 사실을
            # 학생에게 말하는지 본다(2026-11-01 무키 최종 한 바퀴: 녹화 때 번호로 「열린 작업지시를 빠뜨림」을 결함으로 셌다)
            # 재생 안내는 그 처리 건의 처리 기록(이벤트 task_working · notice — 처리 건 화면이 그리는 것)으로 남는다. 문장은 워커가 같은 조회를
            # 이 PC에서 다시 해 견준 결과다(ai_replay.reads_said — 설비 측정값 조회가 있어 교대 인계안에는 늘 붙는다)
            notices = [str((e.get('data') or {}).get('content') or '') for e in r.get(f'{r.process}/api/events?proc_inst_id={pid}&limit=500')
                       if e.get('event_type') == 'task_working' and (e.get('data') or {}).get('type') == 'notice']
            told = any('조회 결과는 준비 당시 값' in n for n in notices)
            r.check('키 없는 PC: 재생한 인계안의 조회 결과가 준비 당시 값이고 이 PC 와 무엇이 다른지 알린다' + suffix, told, (notices[-1] if notices else '재생 안내 없음')[-200:])
        else:
            open_orders, arriving = handover_facts(r, 'HYD-01')
            bad = handover_findings(data.get('checks') or [], open_orders, True, True, arriving)
            r.check('인계안 내용 = 업무 DB(열린 작업지시 · 도착 예정) · 메모 주장은 모순 · 확인 필요로' + suffix, not bad and bool(data.get('evidence')),
                    "; ".join(bad) or json.dumps([(c.get('area'), c.get('state')) for c in data.get('checks') or []], ensure_ascii=False), kind='quality')
        r.keyless('키 없는 PC: 인계안 작성이 녹화로' + suffix, ai_source(session_of(draft)) == '강사 녹화 재생', ai_source(session_of(draft)))
        if suffix:
            queried = [e for e in view['events'] if e.get('todo_id') == draft['id'] and e['event_type'] == 'tool_usage_started'
                       and str((e.get('data') or {}).get('tool', '')).startswith('mcp__enterprise')]
            r.check('보완 1: 인수자의 「다시 확인해 주세요」 뒤 업무 DB를 다시 조회했다', bool(queried), f"업무 DB 조회 {len(queried)}번", kind='quality')
        if not h_submit(r, pid, item_named(view, name), dict(sender_decision='approve', sender_notes='미확인 사항과 원문 조회 근거를 인수자에게 전달합니다.')):
            r.check('인계자 검토 제출' + suffix, False); return
        state, why, view = wait_step(r, pid, '인수자 확인' + suffix, 30)
        r.check('별도 인수자 차례' + suffix, state == 'ready', why)
        if state != 'ready':
            return
        task = item_named(view, '인수자 확인' + suffix)
        if not suffix:
            ok = h_submit(r, pid, task, dict(receiver_decision='revise',
                          receiver_notes='정비 완료 메모와 열린 작업지시, 입고 예정과 실제 재고를 구분해 다시 확인해 주세요.', communication_only=False))
            r.check('인수자 보완 요청 → 같은 처리 건의 재작성', ok, axis=AXES[3])
            if not ok:
                return
        else:
            message = h_submit(r, pid, task, dict(receiver_decision='confirm', receiver_notes='인수 내용 확인', communication_only=False), expect_done=False)
            r.human('설비 조치 완료와 혼동한 확인은 받지 않는다', message, '설비 조치' in message)
            ok = h_submit(r, pid, task, dict(receiver_decision='confirm', receiver_notes='인계를 확인하고 미확인 항목은 다음 교대에서 이어 확인합니다.', communication_only=True))
            r.check('인수자가 인계 확인을 기록', ok)
            if not ok:
                return
    view = wait_end(r, pid, 30)
    end_ids = {e['id'] for e in view['definition']['events'] if e.get('name') == '인수 확인 기록 완료'}
    r.check('인수 확인 종료 기록', view['instance']['status'] == 'COMPLETED' and view['instance'].get('end_event') in end_ids)
    r.check('인계 확인이 설비·발주·정비 실행을 만들지 않음', not view.get('effects'), kind='exception', axis=AXES[1])


# ====================================================================== 90~93 그 밖에(실라버스 밖 확인)
@lab("90", [], title="그 밖에 — 포털 모든 메뉴 순회(JS 오류 · 실패한 요청 · 빈 화면 · 영문 오류)")
def lab_90_menu_sweep(r: Round):
    resolve_rows(r, "90")
    # 화면 목록 = 주 메뉴마다 딸린 화면(data-tabs) 전부(index.html 주 메뉴 한 곳)
    screens = r.page.evaluate("() => hydMenu.list.flatMap(m => m.tabs.map(t => [t, m.name + ' › ' + t]))")
    for tab, title in screens:
        if not r.page.locator(f"#menuList a[data-tab='{tab}']").count():
            r.check(f"메뉴 「{title}」 — 메뉴 줄에 그 화면의 줄이 있다", False, "메뉴 줄에 없음"); continue
        r.tab(tab)
        r.page.wait_for_timeout(2500)
        view = r.page.locator(f"#view-{tab}")
        text = view.inner_text(timeout=5000) if view.count() else r.page.locator("main").inner_text()
        # 그린 값이 없을 때의 흔적만 본다: 낱말로 선 NaN · undefined · [object Object] — 문장 속 기술어(예: 「NaN/Inf를 보존」)는 아님
        bad = re.search(r"Traceback|TypeError|ReferenceError|\bundefined\b|\[object Object\]|(?:^|[\s(:·])NaN(?=$|[\s)·%]|\s*(?:개|건|ms|초|분|℃))|Internal Server Error", text, re.M)
        r.check(f"메뉴 「{title}」 — 화면 글이 20자를 넘고 개발자 오류 흔적(Traceback · TypeError · undefined · [object Object] · 낱말 NaN · Internal Server Error)이 없다", len(text.strip()) > 20 and not bad, (bad.group(0) if bad else text[:80]).replace("\n", " "), kind="quality")


@lab("91", [], title="그 밖에 — 구성 내보내기 → 기준으로 되돌리기(수업 흐름 남김) → 불러오기(수업은 막힘 · PBL 열림), 깨진 파일")
def lab_91_config_bundle(r: Round):
    resolve_rows(r, "91")
    phase = course_phase(r)
    r.tab("admin")
    panel = r.page.locator("#configBundlePanel")
    if not panel.evaluate("d => d.open"):
        panel.locator(":scope > summary").click()
    r.page.wait_for_selector("#cfgExport", timeout=15_000)
    with r.page.expect_download(timeout=60_000) as dl:
        r.page.click("#cfgExport")
    path = r.out / "starter.json"
    dl.value.save_as(str(path))
    bundle = json.loads(path.read_text(encoding="utf-8"))
    r.check("[파일 받기] → 내가 만든 구성 파일(비밀값 없음)", isinstance(bundle, dict) and "summary" in bundle and "LLM_API_KEY" not in path.read_text(encoding="utf-8"), txt(r, "#cfgExportMsg"))
    agents_before = len(agents(r))
    r.page.click("#cfgReset")
    r.page.locator("dialog.confirm-dialog button[value=ok]").click()
    r.wait(60, lambda: txt(r, "#cfgResetMsg"), every=1)
    rt = routes(r)
    r.human("[기준으로 되돌리기] → 한국어 결과 · 수업 흐름(c3_*)은 경보 경로에 남음", txt(r, "#cfgResetMsg"),
            all((rt.get(p) or {}).get("class_flow") for p in ("COOLER_DEGRADATION", "PM_DUE", "SPARE_BELOW_MIN")), axis=AXES[1])
    bad = r.out / "broken.json"
    bad.write_text("{ 이건 JSON 이 아님", encoding="utf-8")
    r.page.set_input_files("#cfgFile", str(bad))
    r.page.wait_for_timeout(800)
    broken = txt(r, "#cfgImportMsg")                                      # configBundle.js — 틀린 자리(한국어) + 「[파일 받기]로 받은 출발본 파일 그대로인지 확인하세요」
    r.human("깨진 파일을 고르면 출발본 파일인지 확인하라는 사람 글로 막는다", broken, "받은 출발본 파일 그대로인지 확인하세요" in broken)
    r.page.set_input_files("#cfgFile", str(path))
    r.page.wait_for_timeout(800)
    button = r.page.locator("#cfgImport")
    if phase == "course":
        reason = button.get_attribute("title") if button.is_disabled() else None
        if reason is None:
            button.click()
            if r.page.locator("dialog.confirm-dialog button[value=ok]").count():
                r.page.locator("dialog.confirm-dialog button[value=ok]").click()
            r.wait(60, lambda: (t := txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=1)
            reason = txt(r, "#cfgImportMsg")
        code, _ = r.api("POST", r.process + "/api/config/import", {"bundle": bundle, "by": ME})
        r.human("수업 단계: [불러오기]는 PBL 에서 연다는 까닭을 사람 글로 · 서버도 거절(403)", reason, "PBL" in (reason or "") and code == 403)
        return
    button.click()
    r.page.locator("dialog.confirm-dialog button[value=ok]").click()
    r.wait(180, lambda: (t := txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=2)
    if r.page.locator("#cfgSkip").count():
        r.page.click("#cfgSkip")
        r.wait(180, lambda: (t := txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=2)
    r.human("받은 파일 [불러오기] → 한국어 결과 · 내가 만든 에이전트 수가 돌아옴", txt(r, "#cfgImportMsg"), len(agents(r)) == agents_before, axis=AXES[3], kind="normal")


def close_instance(r: Round, pid: str, reason: str) -> str:
    """열린 처리 건을 학생처럼 닫는다: 승인 차례면 [반려], 보류 · 멈춘 AI 단계면 [단계 닫기]. 끝 상태를 돌려준다."""
    view = view_of(r, pid)
    approve = next((a["name"] for a in view["definition"]["activities"] if a.get("tool") == "formHandler:select_card"), None)
    state, why, view = wait_step(r, pid, approve, SECONDS["agent"]) if approve else ("running", "", view)
    if state == "ready":
        card_decide(r, pid, item_named(view, approve), approve=False, reason=reason)
    elif state in ("deferred", "failed"):
        w = next(w for w in view["workitems"] if w["status"] in ("PENDING", "IN_PROGRESS") and w.get("agent_mode"))
        close_step(r, pid, w["id"], reason)
    return wait_end(r, pid, 120)["instance"]["status"]


@lab("92", [], title="그 밖에 — B · C [초기화](처리 건이 없을 때 · 진행 중일 때)")
def lab_92_biz_reset(r: Round):
    resolve_rows(r, "92")
    for key, asset, label in (("B", "HYD-02", "정기 점검 도래"), ("C", "HYD-03", "재고 보충 필요")):
        left = running_on(r, asset)
        r.check(f"{key} 시작 전: {asset} 에 열린 처리 건이 없다(앞 실습이 닫았다)", not left, str([i["proc_inst_id"] for i in left]), axis=AXES[3])
        for i in left:                                                    # 남은 건은 학생처럼 닫고 잇는다(닫지 않으면 [초기화]가 거절된다)
            close_instance(r, i["proc_inst_id"], "앞 실습이 남긴 처리 건을 닫습니다")
        msg = unit_button(r, asset, "biz-reset")
        r.check(f"{key} [초기화](대기 중) → 수업 시작값", "초기화" in msg and not msg.startswith("실패:"), msg, axis=AXES[3])
        chip = biz_chip(r, asset)
        r.check(f"{key} [초기화] 뒤 표시 「{label}」", label in chip, chip, axis=AXES[3])
        press = r.page.locator(f"#gwLog .biz-press[data-asset='{asset}']").text_content() or ""      # 화면 아래 「조작 기록」 접기 안(접혀 있어도 글은 있다)
        r.check(f"{key} 설비에서 마지막으로 누른 단추(무엇 · 언제)가 조작 기록에 남는다", "[초기화]" in press, press)      # app.js renderGwLog
        # 진행 중 [초기화]는 거절한다(초기화가 그 처리 건의 발주 · 오더 기록을 바꾸므로 — scenario_buttons) · 처리 건은 그대로 진행
        before = instance_ids(r)
        unit_button(r, asset, "biz-start")
        inst = new_instance(r, before, None, 60)
        if not inst:
            r.check(f"{key} [초기화] 시험용 처리 건이 열림", False, ""); continue
        msg = unit_button(r, asset, "biz-reset")
        r.human(f"{key} 진행 중 [초기화] → 서버가 받지 않음 · 사람 글(끝낸 뒤 누르라는 안내)", msg.replace("실패: ", ""), msg.startswith("실패:") and "진행 중" in msg)
        r.check(f"{key} 진행 중 [초기화]를 받지 않은 뒤에도 처리 건은 그대로 진행", view_of(r, inst["proc_inst_id"])["instance"]["status"] == "RUNNING", "", kind="exception", axis=AXES[1])
        end = close_instance(r, inst["proc_inst_id"], "초기화 시험 뒤 닫기")
        r.check(f"{key} 시험 처리 건을 화면에서 닫았다([반려] → 반려 종결 · 보류면 단계 닫기)", end == "COMPLETED", end, axis=AXES[1])


@lab("93", [], title="그 밖에 — 펌프 · 팬 결함 실험과 [다시 평가]를 워커 모드(AI)로")
def lab_93_pump_fan(r: Round):
    resolve_rows(r, "93")
    if course_phase(r) == "course":
        # 펌프 · 팬 경보는 기준 흐름(anomaly_response)을 연다 — 수업 AI 자리가 아니라 AI 를 부르지 않고 까닭을 남긴다(작업 status 는 IN_PROGRESS, draft_status FAILED)
        reset_units(r)
        before = instance_ids(r)
        got = r.api("POST", f"{r.plant}/api/fault", {"asset": "HYD-02", "type": "pump_leakage"})
        inst = new_instance(r, before, None, 240)
        r.check("펌프 누설 주입 → 처리 건이 열림", got[0] == 200 and bool(inst), str(got)[:120])
        if inst:
            pid = inst["proc_inst_id"]
            got_state = r.wait(SECONDS["agent"], lambda: (lambda v: next(((w, step_failure(v, w)) for w in v["workitems"] if w.get("agent_mode") and step_failure(v, w)), None))(view_of(r, pid)),
                               every=5)
            w, why = got_state or ({}, None)
            r.human("수업 단계: 수업 밖 흐름의 AI 단계는 실행하지 않고 까닭을 사람 글로", why or "", bool(got_state) and w.get("status") != "DONE")
            if w:
                closed = close_step(r, pid, w["id"], "수업 단계에서 실행하지 않는 AI 단계라 닫습니다")
                r.check("멈춘 AI 단계를 처리 건 화면 [단계 닫기]로 닫는다", closed == "CANCELLED", closed, kind="exception", axis=AXES[1])
        reset_units(r)
        return
    reset_units(r)
    r.check("[전체 초기화] → 설비를 정상 운전점으로", "초기화했습니다" in r.page.locator("#scenarioMsg").inner_text(), r.page.locator("#scenarioMsg").inner_text())
    fault_case(r, "HYD-02", "pump_leakage", "PUMP_LEAKAGE")
    reset_units(r)
    # 팬 진동: 수업 문서 셋에 팬 진동 고장 유형 · 원인이 없다 — 지어내지 않고 보류하며 무엇이 없는지 사람 글로 말하는가
    before = instance_ids(r)
    got = r.api("POST", f"{r.plant}/api/fault", {"asset": "HYD-03", "type": "fan_vibration"})
    inst = new_instance(r, before, None, 240)
    r.check("팬 진동 주입 → 처리 건이 열림", got[0] == 200 and bool(inst), str(got)[:120])
    if inst:
        pid = inst["proc_inst_id"]
        held = r.wait(SECONDS["agent"], lambda: next((w for w in view_of(r, pid)["workitems"] if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")), None), every=5)
        r.human("팬 진동(지식 없음) → 지어내지 않고 보류, 무엇이 없는지 사람 글", ((held or {}).get("draft") or {}).get("_deferral", {}).get("reason", ""), bool(held))
        if held:
            close_step(r, pid, held["id"], "수업 지식에 팬 진동 조치가 없어 닫음")
    reset_units(r)


def fault_case(r: Round, asset: str, fault: str, pattern: str):
    rt = routes(r)
    expect_def = (rt.get(pattern) or {}).get("definition")
    r.check(f"{pattern} 경보 경로를 화면 표로 확인(기준 흐름이 연다)", expect_def == "anomaly_response" and (rt.get(pattern) or {}).get("reference") is True, json.dumps(rt.get(pattern), ensure_ascii=False))
    before = instance_ids(r)
    injected = time.monotonic()
    # 결함 시뮬레이션 화면에는 펌프 · 팬 버튼이 없다(쿨러 · B · C 만 — 실라버스에 펌프 · 팬 실습 없음) → 설비 주입 API
    got = r.api("POST", f"{r.plant}/api/fault", {"asset": asset, "type": fault})
    r.check(f"{asset} {fault} 주입", got[0] == 200, str(got)[:200])
    inst = new_instance(r, before, expect_def, 240)
    r.check(f"{pattern} → 처리 건이 기준 흐름으로 열림", bool(inst), "")
    if not inst:
        return
    pid = inst["proc_inst_id"]
    select_name = next(a["name"] for a in class_definition(r, expect_def)["activities"] if a.get("id") == "task:select")
    t0 = time.monotonic()
    state, why, view = wait_step(r, pid, select_name, SECONDS["agent"])
    if state == "deferred":
        w = next(w for w in view["workitems"] if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral"))
        select_instance(r, pid)                                           # [다시 평가]의 「누가」는 화면이 담당자로 싣는다(taskDeferral.js — actorInput)
        panel = r.page.locator(f"#instDetail [data-deferral-task='{w['id']}']")
        panel.wait_for(timeout=30_000)
        r.human("보류 단계에 [다시 평가] 패널(보류 이유가 사람 글)", why)
        panel.locator("[data-reassess-reason]").fill("")
        panel.locator("[data-reassess]").click(); r.page.wait_for_timeout(500)
        r.human("[다시 평가] 사유 없이 → 필수 입력 안내", panel.locator(".form-msg").first.inner_text() if panel.locator(".form-msg").count() else "")
        panel.locator("[data-reassess-reason]").fill("가" * 2001)
        panel.locator("[data-reassess]").click(); r.page.wait_for_timeout(1500)
        long_msg = panel.locator(".form-msg").inner_text() if panel.locator(".form-msg").count() else ""
        r.human("[다시 평가] 너무 긴 사유 → 서버의 거절 문구가 한국어 사람 글", long_msg, "필수 항목" not in long_msg)   # 폼이 막은 문구는 서버 거절이 아니다
        r.wait(max(0, 125 - (time.monotonic() - injected)) + 1, lambda: False, every=5)    # 새 2분 원천 창(주입 뒤 125초)
        panel = r.page.locator(f"#instDetail [data-deferral-task='{w['id']}']")
        panel.locator("[data-reassess-reason]").fill("고장 주입 뒤 새 2분 관측 창으로 다시 평가합니다")
        panel.locator("[data-reassess]").click()
        r.check("[다시 평가] 접수 → 그 단계가 다시 돈다", bool(r.wait(30, lambda: item_named(view_of(r, pid), w["activity_name"]).get("status") != "PENDING", every=2)), "",
                kind="exception", axis=AXES[3])
        state, why, view = wait_step(r, pid, select_name, SECONDS["agent"])
    ai_s = time.monotonic() - t0
    engine = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": asset, "pattern": pattern, "facts": {}})[1] or {}
    if engine.get("status") == "NO_FEASIBLE_OPTION":
        r.human(f"{pattern}: 지식에 조치 후보 없음(판단 엔진) → 다시 평가해도 지어내지 않고 보류 · 사람 글", why, state == "deferred")
        held = next((w for w in view.get("workitems", []) if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")), None)
        if held:
            close_step(r, pid, held["id"], "수업 지식에 펌프 조치가 없어 닫음")
        return
    r.check(f"{pattern}: AI 4단계 → 조치 선택 차례", state == "ready", f"{state} {why} {ai_s:.0f}초", seconds=ai_s)
    if state != "ready":
        return
    dec = decision_of(r, view)
    card = card_summary(dec)
    cause = vars_of(view["instance"]).get("cause")
    r.check(f"{pattern}: 원인 진단이 주입한 외란을 흔드는 원인과 같다(그래프)", cause in expected_causes(graph(r, asset), fault), str(cause), kind="quality")
    r.check(f"{pattern}: 추천 = 실행 가능한 1순위 · 제외 카드에 규칙 · 승인 역할 = 원문, 카드가 둘 이상(지는 대안)", not card_findings(dec, approvers_of("HM-8", "PM-02", "PR-07")) and len(card["evidence"]) > 1,
            json.dumps(card, ensure_ascii=False)[:400], kind="quality")
    task = item_named(view, select_name)
    ok_d, pmsg = card_decide(r, pid, task, approve=True, reason="실습: 추천 조치를 승인합니다")
    r.check(f"{pattern}: 추천 조치 승인", ok_d, pmsg)
    fin = r.wait(420, lambda: (x := view_of(r, pid))["instance"]["status"] != "RUNNING" and x
                 or (any(w["activity_id"] == "task:escalate" and w["status"] == "IN_PROGRESS" for w in x["workitems"]) and x), every=3) or view_of(r, pid)
    esc = next((w for w in fin["workitems"] if w["activity_id"] == "task:escalate"), {})
    if esc.get("status") == "IN_PROGRESS":
        open_task(r, pid, esc["id"])
        r.page.locator("#todoPanel textarea, #todoPanel input[id^=tdField]").first.fill("회복되지 않아 다른 조치를 지시합니다")
        r.page.click("#todoPanel #tdDone")
        fin = wait_end(r, pid, 120)
    end = fin["instance"].get("end_event")
    rec = vars_of(fin["instance"]).get("recovered")
    r.check(f"{pattern}: 처리 건이 끝났고 끝 사건이 재관측과 맞다(회복 → ev:closed, 미회복 → ev:escalated)",
            fin["instance"]["status"] == "COMPLETED" and ((rec is True and end == "ev:closed") or (rec is False and end == "ev:escalated")), json.dumps({"end": end, "recovered": rec}))


# ---------------------------------------------------------------------- 실행
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="결과 폴더 — 열린 작업 폴더 아래(예: 작업/<날짜>_<제목>/실행/한바퀴_키)")
    ap.add_argument("--only", default="", help="쉼표로 고른 실습 번호만(예: 01,05)")
    ap.add_argument("--from", dest="start", default="", help="이 번호부터 끝까지")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--ai-runs", type=int, choices=(1, 3), default=3, help="AI 단계 반복 수. 1 = 연속 수업 확인(반복 일치는 측정 안 함)")
    args = ap.parse_args(argv[1:])
    codes = [c for c, _, _ in sorted(LABS, key=lambda x: x[0])]
    try:
        chosen = select_labs(codes, args.only, args.start)
    except ValueError as e:
        print(f"[멈춤] {e}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    syllabus = load_syllabus()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR", accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(20_000)
        r = Round(page, out, syllabus)
        r.ai_runs = args.ai_runs
        r.ai_mode = (r.get(r.worker + "/healthz", timeout=10) or {}).get("ai_mode") or "?"
        print(f"AI 모드 {r.ai_mode} · 실습 {', '.join(chosen)}", flush=True)
        r.lab, r.tags["00"] = "00", "실라버스 대조"
        missing = uncovered_rows(syllabus, LAB_ROWS)
        r.check("실라버스의 포털 실습 행이 모두 이 도구의 실습에 있다", not missing, "; ".join(missing))
        r.open()
        for code, title, fn in sorted(LABS, key=lambda x: x[0]):
            if code not in chosen:
                continue
            r.lab = code
            print(f"\n== {code} {title}", flush=True)
            t0 = time.monotonic()
            try:
                fn(r)
            except Exception as e:
                r.check("실습이 끝까지 돌았다", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}", axis=AXES[1])
            print(f"   ({time.monotonic() - t0:.0f}초)", flush=True)
        browser.close()
    rc = r.write()
    print(f"\n결과: {out}/summary.md (판정 실패 {sum(not v.ok for v in r.verdicts)}개 · 측정 안 함 {len(r.not_measured)}개)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
