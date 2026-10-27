"""수업 한 바퀴 — 포털 실습 13개와 「그 밖에」를 실라버스 순서대로, 학생 한 명이 포털을 누르는 그대로 돌린다.

    .venv/bin/python scripts/class_round.py [--out DIR] [--only 01,05] [--from 05] [--headed]

전제: 시작.bat(scripts/start_all.sh)이 「완료」까지 돈 스택, 수업 시작 상태(구조판 지식 · 문서 적재 전 · 처리 건 0),
AI 워커 1개(강의 중계 모델). 포트는 시작 스크립트가 저장한 .hyd-runtime/ports.json 에서 읽는다(포트가 옮겨진 PC 그대로).
판정 규칙(문서/시스템/6_남은_일.md 인계 6절):
  - 조작은 포털 화면 클릭 · 입력으로 한다. API 는 결과 확인(관측)과, 실습 안내가 「검증된 API 절차」로 정한 곳에만 쓴다.
  - 실습마다 정상 경로와 예외 경로(반려 · 거절 · 보류 · 권한 · 잘못된 입력 · 막혔을 때 되돌리기)를 함께 판정한다.
  - AI 단계는 같은 입력으로 3번 돌려 추천 카드 · 승인 역할 · 근거 · 추출 결과 · 소요 시간이 같은 다음 단계를 주는지 본다(Round.repeat3).
  - 오류 · 거절은 학생이 읽을 한국어 문장이어야 한다(영문 예외 · 500 · 빈 화면 · 무한 대기는 실패, Round.human_message).
결과: DIR/results.json(판정 한 줄씩) · DIR/summary.md · 실패 화면 DIR/shots/*.png · 실습별 콘솔 오류 · 실패한 요청.
종료 코드: 실패가 하나라도 있으면 1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
# 선택 도구(FUXA · Redpanda console · Prometheus)는 수업 프로필에 없어 그 주소 확인이 실패하는 것이 정상이다
IGNORED_REQUESTS = (":1881", ":8085", ":9090", ":9644", "favicon.ico")


def host_ports() -> dict[int, int]:
    """시작 스크립트가 고른 바깥 포트(기본 포트 → 이 PC의 포트). 파일이 없으면 기본 포트 그대로."""
    path = ROOT / ".hyd-runtime/ports.json"
    if not path.exists():
        return {}
    return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


@dataclass
class Verdict:
    lab: str
    name: str
    ok: bool
    kind: str            # normal | exception | quality | ai3 | timing
    note: str = ""
    seconds: float | None = None
    shot: str | None = None


@dataclass
class LabLog:
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)


class Round:
    """한 학생의 포털 세션 + 판정 기록. 실습 함수는 lab(r) 꼴로 이것만 받는다."""

    def __init__(self, page, out: Path):
        p = host_ports()
        hp = lambda port: p.get(port, port)                              # noqa: E731
        self.page = page
        self.out = out
        self.portal = f"http://127.0.0.1:{hp(8088)}"
        self.process = f"http://127.0.0.1:{hp(8080)}"
        self.plant = f"http://127.0.0.1:{hp(8000)}"
        self.detector = f"http://127.0.0.1:{hp(8092)}"
        self.agent = f"http://127.0.0.1:{hp(8091)}"
        self.enterprise = f"http://127.0.0.1:{hp(8095)}"
        self.worker = f"http://127.0.0.1:{hp(8097)}"
        self.inbucket = f"http://127.0.0.1:{hp(54324)}"
        self.verdicts: list[Verdict] = []
        self.logs: dict[str, LabLog] = {}
        self.lab = "-"
        self.memo: dict[str, Any] = {}                                    # 실습 사이에 넘길 값(앞 실습이 만든 id 등)
        self.ai_runs = 3                                                  # --ai-runs: 같은 AI 단계 반복 수(1이면 일치 판정은 측정 안 함)
        self.unlock_code = ""                                             # --unlock-code-file: 13 교대 실습을 여는 강사 코드(출력하지 않는다)
        self.not_measured: list[dict] = []                                # 이번 실행이 재지 않은 판정(통과로 세지 않는다)
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self._log().console_errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: self._on_failed(r.url, r.failure or "failed"))
        page.on("response", lambda r: r.status >= 500 and self._on_failed(r.url, f"HTTP {r.status}"))

    # ------------------------------------------------------------------ 기록
    def _log(self) -> LabLog:
        return self.logs.setdefault(self.lab, LabLog())

    def _on_console(self, msg):
        # 예외 경로(잘못된 입력 · 권한 · 중복)는 서버가 4xx 로 거절하는 것이 정상이고, 브라우저가 그 응답을 「Failed to load resource … 4xx」로 찍는다.
        # 그 줄은 판정에서 뺀다(화면 문구는 각 판정이 따로 본다). 5xx · 스크립트 오류는 그대로 센다
        if msg.type == "error" and re.search(r"Failed to load resource: the server responded with a status of 4\d\d", msg.text or ""):
            return
        if msg.type == "error" and not any(s in (msg.location or {}).get("url", "") for s in IGNORED_REQUESTS):
            self._log().console_errors.append(msg.text[:300])

    def _on_failed(self, url: str, why: str):
        if not any(s in url for s in IGNORED_REQUESTS) and "net::ERR_ABORTED" not in str(why):
            self._log().failed_requests.append(f"{why} {url}"[:300])

    def check(self, name: str, ok: bool, note: str = "", kind: str = "normal", seconds: float | None = None) -> bool:
        shot = None
        if not ok:
            shot = self.shot(f"FAIL-{self.lab}-{len(self.verdicts):03d}")
        self.verdicts.append(Verdict(self.lab, name, bool(ok), kind, str(note)[:1500], seconds, shot))
        mark = "통과" if ok else "실패"
        print(f"  [{mark}] {self.lab} {name}" + (f" — {str(note)[:300]}" if note else ""), flush=True)
        return bool(ok)

    def shot(self, name: str) -> str | None:
        path = self.out / "shots" / f"{re.sub(r'[^0-9A-Za-z가-힣_.-]+', '_', name)}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.page.screenshot(path=str(path), full_page=False)
            return str(path.relative_to(self.out))
        except Exception:                                                # 화면이 없을 때도 판정은 남긴다
            return None

    # ------------------------------------------------------------------ 관측(API)
    def api(self, method: str, url: str, body: Any = None, timeout: float = 60) -> tuple[int, Any]:
        """(상태 코드, JSON 또는 본문 글자). 4xx · 5xx 도 예외 없이 돌려준다 — 예외 경로 판정에 쓴다."""
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                code = resp.status
        except urllib.error.HTTPError as e:
            raw, code = e.read(), e.code
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, raw.decode("utf-8", errors="replace")

    def get(self, url: str, timeout: float = 30) -> Any:
        code, body = self.api("GET", url, timeout=timeout)
        if code >= 400:
            raise RuntimeError(f"GET {url} → {code}: {str(body)[:300]}")
        return body

    def wait(self, seconds: float, probe: Callable[[], Any], every: float = 2.0) -> Any:
        """probe 가 참인 값을 낼 때까지 기다린다. 시간이 지나면 None. probe 안의 일시 오류는 다시 시도한다."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = probe()
                if value:
                    return value
            except Exception:
                pass
            time.sleep(every)
        return None

    # ------------------------------------------------------------------ 화면
    def open(self):
        self.page.goto(self.portal + "/", wait_until="domcontentloaded")
        self.page.wait_for_selector("button[data-tab]", timeout=30_000)

    def tab(self, name: str):
        """사이드바의 메뉴(data-tab)를 누른다. 접힌 묶음 안이면 묶음을 먼저 연다."""
        btn = self.page.locator(f"button[data-tab='{name}']").first
        if not btn.is_visible():
            group = btn.locator("xpath=ancestor::*[self::details or contains(@class,'group')][1]")
            try:
                group.locator("summary, .group-toggle, button").first.click(timeout=3000)
            except Exception:
                pass
        btn.click()
        self.page.wait_for_timeout(600)

    def human_message(self, text: str) -> tuple[bool, str]:
        """학생이 읽는 오류 문장인가: 한글이 있고, 영문 예외 · 상태 코드 · 스택 흔적이 없어야 한다."""
        t = (text or "").strip()
        if not t:
            return False, "빈 문구"
        # 상태 코드는 「HTTP 404」 · 「→ 500」 · 「500 Internal」처럼 붙어 나올 때만 본다(1차: 금액 590만 원을 코드로 오판)
        bad = re.search(r"Traceback|Exception|Error:|HTTP(?: Error)? ?[45]\d\d|→ ?[45]\d\d\b|\b[45]\d\d (?:Internal|Not Found|Bad Request|Forbidden|Unauthorized)|undefined|\bnull\b|NaN|\{\"", t)
        if bad:
            return False, f"사람 글이 아님({bad.group(0)}): {t[:200]}"
        if not re.search(r"[가-힣]", t):
            return False, f"한글 없음: {t[:200]}"
        return True, t[:200]

    # ------------------------------------------------------------------ AI 3회
    def repeat3(self, step: str, run_once: Callable[[int], dict], same_keys: tuple[str, ...], limit_s: float | None = None,
                single: int = 0) -> list[dict]:
        """같은 입력으로 AI 단계를 3번 돌린다. run_once(i) 는 {'seconds': 소요, 키: 값 …} 을 낸다.
        same_keys 의 값이 3번 모두 같아야 학생 모두가 같은 다음 단계를 받는다. limit_s 가 있으면 가장 느린 소요 시간이 그 안이어야 한다.
        --ai-runs 1(연속 수업 확인)이면 single 번째 실행 하나만 돌리고, 반복 일치와 나머지 실행의 경로는
        측정하지 않은 것으로 따로 남긴다(통과 아님)."""
        runs = []
        n = self.ai_runs
        for i in (range(3) if n >= 3 else (single,)):
            # 학생마다 워커가 하나다 — 앞 단계의 AI 작업이 아직 돌면 그 뒤에 줄을 서 소요 시간이 부푼다(최종 1차: 질문이 추출 뒤에 줄 섬)
            self.wait(1200, lambda: (self.get(self.worker + "/healthz", timeout=5) or {}).get("runs_in_flight") == 0, every=5)
            t0 = time.monotonic()
            try:
                got = run_once(i) or {}
            except Exception as e:
                got = {"error": f"{type(e).__name__}: {e}"}
            got.setdefault("seconds", round(time.monotonic() - t0, 1))
            runs.append(got)
            print(f"    {step} {i + 1}/{n}: " + json.dumps(got, ensure_ascii=False, default=str)[:400], flush=True)
        (self.out / "ai3").mkdir(parents=True, exist_ok=True)
        (self.out / "ai3" / f"{self.lab}-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', step)}.json").write_text(
            json.dumps(runs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        errors = [r["error"] for r in runs if r.get("error")]
        self.check(f"{step} — {n}번 모두 끝까지", not errors, "; ".join(errors), kind="ai3")
        if n < 3:
            self.not_measured.append(dict(lab=self.lab, name=f"{step} — 3번 같은 {', '.join(same_keys)}",
                                          why=f"--ai-runs {n}: {single + 1}번째 실행만 돌림. 반복 일치·다른 실행의 경로는 재지 않음(기존 증거를 따로 대조)"))
        for key in same_keys if n >= 3 else ():
            values = [json.dumps(r.get(key), ensure_ascii=False, sort_keys=True, default=str) for r in runs]
            self.check(f"{step} — 3번 같은 {key}", len(set(values)) == 1 and not errors, " | ".join(v[:200] for v in values), kind="ai3")
        slowest = max(float(r.get("seconds") or 0) for r in runs)
        if limit_s is not None:
            self.check(f"{step} — 가장 느린 소요 {slowest:.0f}초 ≤ {limit_s:.0f}초", slowest <= limit_s,
                       ", ".join(f"{float(r.get('seconds') or 0):.0f}s" for r in runs), kind="timing", seconds=slowest)
        return runs

    # ------------------------------------------------------------------ 결과
    def write(self) -> int:
        bad = [v for v in self.verdicts if not v.ok]
        log_failures = 0
        for lab, log in self.logs.items():
            if log.console_errors or log.failed_requests:
                log_failures += 1
                bad.append(Verdict(lab, "콘솔 오류 · 실패한 요청", False, "quality"))
        (self.out / "results.json").write_text(json.dumps({
            "verdicts": [asdict(v) for v in self.verdicts],
            "logs": {k: asdict(v) for k, v in self.logs.items()}, "not_measured": self.not_measured}, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# 수업 한 바퀴 결과", "", f"판정 {len(self.verdicts)}개 · 실패 {len([v for v in self.verdicts if not v.ok])}개 · 별도 콘솔/통신 오류 실습 {log_failures}개"
                 + f" · 측정 안 함 {len(self.not_measured)}개(통과 아님)", ""]
        if self.not_measured:
            lines += ["## 측정 안 함(통과로 세지 않음)"] + [f"- [{x['lab']}] {x['name']} — {x['why']}" for x in self.not_measured] + [""]
        for lab in dict.fromkeys(v.lab for v in self.verdicts):
            vs = [v for v in self.verdicts if v.lab == lab]
            lines.append(f"## {lab} — 통과 {sum(v.ok for v in vs)}/{len(vs)}")
            lines += [f"- {'통과' if v.ok else '**실패**'} [{v.kind}] {v.name}" + (f" — {v.note[:300]}" if v.note else "") for v in vs]
            log = self.logs.get(lab)
            if log and (log.console_errors or log.failed_requests):
                lines.append(f"- **콘솔 오류 {len(log.console_errors)} · 실패한 요청 {len(log.failed_requests)}**: "
                             + "; ".join((log.console_errors + log.failed_requests)[:5]))
            lines.append("")
        (self.out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
        return 1 if bad else 0


# ====================================================================== 실습 (실라버스 순서 — 통합반 · 실전반 차시)
LABS: list[tuple[str, str, Callable[[Round], None]]] = []


def lab(code: str, title: str):
    def register(fn):
        LABS.append((code, title, fn))
        return fn
    return register


# ====================================================================== part_A
# part_A — 실습 01 · 02 · 02b · 03 · 03b · 04 · 04b · 08 · 90 · 91 (작성: 서브에이전트 A)
# class_round.py 의 「실습」 절(LABS · lab 정의 뒤)에 그대로 붙여 넣는 몸통이다. 하네스의 lab · Round 만 쓴다.
# import: 하네스 맨 위의 json · re · time · Path 를 그대로 쓴다(추가 import 없음). tempfile 대신 r.out 아래에 파일을 둔다.
# 배치(LABS 는 등록 순서대로 돈다): 01 · 02 · 03 · 04 는 실라버스 자리에, 02b · 03b · 04b 는 문서 적재(05) 바로 뒤에, 08 은 7-1 자리에,
#   90 · 91 은 맨 끝(「그 밖에」)에 붙인다. 02b · 03b · 04b 는 05 가 남긴 적재 상태를 쓴다(구조판에서 부르면 판정이 「적재 전」으로 갈린다).
# 시간 창 근거(TIME_SCALE=20): 승인 지연 PT10M → 실제 30초, A 카드 예측 유효 시뮬레이션 30분 → 실제 90초, 조치 선택 기한 PT10M → 30초.
# 셀렉터는 2026-10-25 라이브 포털(읽기)에서 확인한 것. 상태를 바꾸는 버튼은 코드(it/portal/www)로 확인했고 「# 코드 확인」으로 적었다.

# ====================================================================== A 공용 도우미 (이름 앞 _a_ — 다른 파트와 겹치지 않게)
_A_IDLE_TS1 = 50.0          # [쿨러 복구] 뒤 다음 주입 전: 유온이 경보 해제선(52 ℃) 아래 50 ℃ 밑 + 감지기 IDLE (approval_stage_live.py CLEAR_TS1 과 같음)
_A_RAW_ID = re.compile(r"\b(?:[a-z]+:[a-z0-9][a-z0-9_.-]+|[a-z]+_[a-z0-9_]+|[A-Z]{4,}(?:_[A-Z]+)*)\b")   # 학생 글에 섞인 원문 id · 영문 상수
_A_SECONDS = {"agent": 300, "instance": 180, "close": 240, "idle": 600, "end": 600}   # 20배속에서 넉넉한 상한(관측 최대의 3배 이상, 아래 notes 참고)


def _a_txt(r, sel: str, timeout: int = 3000) -> str:
    """보이는 글자(없으면 '')."""
    try:
        loc = r.page.locator(sel).first
        loc.wait_for(state="attached", timeout=timeout)
        return (loc.inner_text(timeout=timeout) or "").strip()
    except Exception:
        return ""


def _a_all_txt(r, sel: str) -> str:
    """접힌 칸까지 포함한 글자(text_content)."""
    try:
        return " ".join((x or "") for x in r.page.locator(sel).all_text_contents())
    except Exception:
        return ""


def _a_raw_ids(text: str) -> list[str]:
    allow = {"HYD", "SCADA", "PLC", "MQTT", "KPI", "BSC", "SOP", "ERP", "CMMS", "DMZ", "TS1", "CE", "PS1", "FS1", "VS1", "REMOTE", "AUTO"}
    return sorted({m for m in _A_RAW_ID.findall(text or "") if m.split("_")[0] not in allow and not m.startswith(("http:", "https:"))})[:12]


def _a_plant(r) -> dict:
    return r.get(r.plant + "/api/state")["units"]["HYD-01"]


def _a_phase(r) -> str:
    unit = r.get(r.detector + "/api/detector/state")["assets"]["HYD-01"]
    return (unit.get("patterns") or {}).get("COOLER_DEGRADATION", unit).get("phase") or "?"


def _a_idle(r) -> bool:
    u = _a_plant(r)
    return u["tags"]["TS1"] < _A_IDLE_TS1 and float((u.get("disturbances") or {}).get("cooler_health", 1.0)) >= 0.999 and _a_phase(r) == "IDLE"


def _a_view(r, pid: str) -> dict:
    return r.get(f"{r.process}/api/instances/{pid}")


def _a_rows(view: dict) -> dict:
    out: dict = {}
    for w in sorted(view.get("workitems") or [], key=lambda w: str(w.get("start_date") or "")):
        out[w["activity_id"]] = w
    return out


def _a_vars(view: dict) -> dict:
    return {v["key"]: v.get("value") for v in (view.get("instance") or {}).get("variables_data") or []}


def _a_hyd01_running(r) -> list[dict]:
    rows = r.get(f"{r.process}/api/instances?limit=50&status=RUNNING")
    out = []
    for i in rows:
        try:
            if _a_vars(_a_view(r, i["proc_inst_id"])).get("asset") == "HYD-01":
                out.append(i)
        except Exception:
            pass
    return out


def _a_pick_me(r, user_id: str) -> str:
    """내 작업함에서 「나」를 고른다(브라우저 localStorage 만 바뀜 — 서버 상태 아님). user_id '' 이면 「고르기」로 비운다. 고른 표시 이름을 돌려준다."""
    r.tab("inbox")
    sel = "#inboxView select[data-inbox-me]"
    r.page.wait_for_selector(sel, timeout=15_000)
    r.page.select_option(sel, user_id)
    r.page.wait_for_timeout(1200)
    return _a_txt(r, "#shellMe")


def _a_select_instance(r, pid: str) -> bool:
    """처리 건 목록에서 그 처리 건 카드를 누른다(이름이 같은 카드가 여럿이라 상세의 ID 로 맞춘다). 못 찾으면 알림 링크와 같은 주소로 연다."""
    r.tab("instances")
    r.page.wait_for_selector("#instList", timeout=15_000)
    r.wait(15, lambda: r.page.locator("#instList .inst-card").count() > 0, every=1)
    cards = r.page.locator("#instList .inst-card")
    for i in range(min(cards.count(), 8)):
        cards.nth(i).click()
        if r.wait(6, lambda: pid in _a_all_txt(r, "#instDetail"), every=0.5):
            return True
    r.page.evaluate("id => { location.hash = '#/instances/' + encodeURIComponent(id); }", pid)   # 내 작업함 · 알림 링크와 같은 경로(inbox.js route)
    return bool(r.wait(8, lambda: pid in _a_all_txt(r, "#instDetail"), every=0.5))


def _a_degrade(r) -> tuple[str | None, float, str]:
    """[쿨러 열화 주입]을 누르고 새 HYD-01 처리 건을 기다린다. (처리 건 id, 누른 시각 monotonic, 화면 안내 문구)."""
    known = {i["proc_inst_id"] for i in r.get(f"{r.process}/api/instances?limit=100")}
    r.tab("scenario")
    btn = r.page.locator("#units .unit[data-asset='HYD-01'] button[data-act='degrade']")
    btn.wait_for(timeout=15_000)
    t0 = time.monotonic()
    btn.click()
    r.page.wait_for_timeout(1500)
    msg = _a_txt(r, "#scenarioMsg")

    def opened():
        for i in r.get(f"{r.process}/api/instances?limit=100"):
            if i["proc_inst_id"] not in known and _a_vars(_a_view(r, i["proc_inst_id"])).get("asset") == "HYD-01":
                return i["proc_inst_id"]
        return None
    # 경보까지: 열화 → 유온 상승 → 감지기 RAISE. 라이브 관측 약 42초(2026-10-25 14:50:28 → 14:51:10). 상한 180초.
    return r.wait(_A_SECONDS["instance"], opened, every=3), t0, msg


def _a_wait_agent(r, pid: str, limit: float) -> dict:
    """AI 판단 단계(T_agent)가 끝날 때까지: 보류(PENDING+_deferral) · 승인 대기(T_approve IN_PROGRESS) · 실패를 돌려준다."""
    def probe():
        view = _a_view(r, pid)
        rows = _a_rows(view)
        ag, ap = rows.get("T_agent") or {}, rows.get("T_approve") or {}
        if ag.get("status") == "PENDING" and (ag.get("draft") or {}).get("_deferral"):
            return {"outcome": "보류", "view": view, "deferral": ag["draft"]["_deferral"]}
        if ag.get("status") == "DONE" and ap.get("status") == "IN_PROGRESS":
            return {"outcome": "승인 대기", "view": view}
        if ag.get("draft_status") in ("FAILED", "CANCELLED") or view["instance"]["status"] != "RUNNING":
            return {"outcome": f"멈춤({ag.get('status')}/{ag.get('draft_status')}/{view['instance']['status']})", "view": view}
        return None
    return r.wait(limit, probe, every=3) or {"outcome": "시간 초과", "view": _a_view(r, pid)}


def _a_agent_seconds(view: dict) -> float | None:
    """처리 건 시작 → AI 판단 끝(보류 기록 또는 승인 단계 시작)까지 실제 초."""
    from datetime import datetime
    f = lambda s: datetime.fromisoformat(str(s).replace("Z", "+00:00"))       # noqa: E731
    try:
        st = f(view["instance"]["start_date"])
        ev = [e for e in view.get("events") or [] if e.get("event_type") == "task_deferred"]
        if ev:
            return round((f(ev[-1]["timestamp"]) - st).total_seconds(), 1)
        ap = _a_rows(view).get("T_approve") or {}
        ag = _a_rows(view).get("T_agent") or {}
        end = ag.get("end_date") or ap.get("start_date")
        return round((f(end) - st).total_seconds(), 1) if end else None
    except Exception:
        return None


def _a_restore_and_close(r, pid: str | None) -> dict:
    """[쿨러 복구]를 누르고 처리 건이 닫히기 · 설비가 다음 주입을 받을 상태가 되기를 기다린다."""
    r.tab("scenario")
    r.page.locator("#units .unit[data-asset='HYD-01'] button[data-act='restore']").click()
    r.page.wait_for_timeout(1500)
    msg = _a_txt(r, "#scenarioMsg")
    closed = None
    if pid:
        # 복구 → 유온 하강 → 감지기 CLEAR → 사건 RESOLVED_WITHOUT_ACTION → 처리 건 「조치 전 해소」. 관측 42~45초, 상한 240초.
        closed = r.wait(_A_SECONDS["close"], lambda: (lambda v: v if v["instance"]["status"] != "RUNNING" else None)(_a_view(r, pid)), every=3)
    t0 = time.monotonic()
    idle = r.wait(_A_SECONDS["idle"], lambda: _a_idle(r), every=5)
    return {"msg": msg, "closed": closed, "idle": bool(idle), "idle_s": round(time.monotonic() - t0, 1)}


def _a_ensure_idle(r) -> bool:
    """앞 실습이 남긴 HYD-01 처리 건 · 경보가 있으면 화면의 [쿨러 복구]로 정리하고 대기 상태를 기다린다(학생이 따라붙는 길과 같다)."""
    if not _a_hyd01_running(r) and _a_idle(r):
        return True
    for i in _a_hyd01_running(r):
        _a_restore_and_close(r, i["proc_inst_id"])
    return bool(r.wait(_A_SECONDS["idle"], lambda: _a_idle(r), every=5))


# ====================================================================== 01 · 1-2 실행 환경
def _a_header_health(r) -> tuple[int, int, str, str]:
    """상단 「서비스 n/m」(app.js pollHealth): (응답 수, 전체, 점 class, 글자)."""
    text = _a_txt(r, "#healthDots")
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    dot = r.page.locator("#healthDots .dot").first.get_attribute("class") if r.page.locator("#healthDots .dot").count() else ""
    return (int(m.group(1)), int(m.group(2)), dot or "", text) if m else (-1, -1, dot or "", text)


@lab("01", "1-2 실행 환경 — 포털 접속 · 홈 상태 점 · 시스템 구성")
def lab_01_runtime(r: Round):
    # 정상: 포털 접속 → 홈. 상태 점은 5초마다 갱신(app.js pollHealth) — 첫 판정까지 최대 15초 기다린다.
    r.tab("main")
    got = r.wait(15, lambda: (lambda h: h if h[1] > 0 and h[0] == h[1] else None)(_a_header_health(r)), every=1)
    up, total, dot, text = got or _a_header_health(r)
    r.check("홈 상단 상태 점이 모두 초록(서비스 n/n)", bool(got) and "up" in dot, text)
    # 지식 항목 수는 지식 지도 조회가 끝나야 그려진다 — 숫자가 뜰 때까지(final5: 첫 화면에서 빈칸을 읽음)
    r.wait(15, lambda: re.search(r"지식 항목\s*[\d,]+", _a_txt(r, "#mainStats").replace("\n", " ")), every=1)
    stats = _a_txt(r, "#mainStats")
    r.check("홈 요약 카드: 설비 3기 · 시간 배율 20×", "3기" in stats and "20×" in stats, stats.replace("\n", " ")[:200])
    m = re.search(r"지식 항목\s*([\d,]+)\s*연결\s*([\d,]+)", stats.replace("\n", " "))
    r.memo["01_home_knowledge"] = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) if m else None
    g = r.get(r.agent + "/api/ontology/graph?asset=HYD-01")
    r.check("홈 「지식 항목 · 연결」 수 = 지식 지도 API(HYD-01)", bool(m) and r.memo["01_home_knowledge"] == (len(g["nodes"]), len(g["edges"])),
            f"화면 {r.memo['01_home_knowledge']} / API {(len(g['nodes']), len(g['edges']))}")
    scale = r.get(r.plant + "/api/state").get("time_scale")
    shown_scale = _a_all_txt(r, "#scale").strip()                         # 상단 「시뮬레이션 시각」 접힘(details.clock-pop) 안 — text_content 로 읽는다
    r.check("시간 배율 20배(화면 · 설비 API 같음)", shown_scale == "20" and float(scale) == 20.0, f"화면 {shown_scale} · API {scale}")
    live = _a_txt(r, "#mLive", 2000) or _a_all_txt(r, "#mLive")
    r.check("홈 도식의 실시간 유온 줄이 세 설비 값을 보인다", all(a in live for a in ("HYD-01", "HYD-02", "HYD-03")), live[:160])

    # 정상: 「시스템 구성 보기」 버튼 → 시스템 구성. 응답 확인 대상(선택 도구 제외)은 모두 초록, 선택 도구는 「(선택 도구)」로 실패처럼 보이지 않는다.
    r.page.locator("#mainArch").click()
    r.page.wait_for_selector("#stack .comp", timeout=10_000)
    r.page.wait_for_timeout(6000)                                         # 상태 점은 pollHealth 가 채운다(5초 주기)
    comps = r.page.eval_on_selector_all("#stack .comp", "cs => cs.map(c => ({dot: c.querySelector('.dot').className, text: c.innerText.replace(/\\n/g, ' ')}))")
    checked = [c for c in comps if "unknown" not in c["dot"]]            # 응답 확인 대상(FUXA · Prometheus · portal · TimescaleDB 는 확인 안 함 → unknown)
    down = [c["text"][:40] for c in checked if "up" not in c["dot"]]
    r.check("시스템 구성: 응답 확인 대상이 모두 초록", checked and not down, f"확인 {len(checked)}개, 꺼짐 {down}")
    r.check("시스템 구성의 초록 수 = 상단 「서비스 n/n」", len([c for c in checked if 'up' in c['dot']]) == total, f"구성 {len(checked)} · 상단 {total}")
    opt = [c["text"][:40] for c in comps if "선택 도구" in c["text"]]
    r.check("선택 도구(FUXA · Prometheus · Redpanda)는 실패가 아닌 「선택 도구」로 표시", bool(opt) and not any("down" in c["dot"] for c in comps if "선택 도구" in c["text"]),
            "; ".join(opt), kind="quality")
    r.check("pageLocation · 제목이 「시스템 구성」", _a_txt(r, "#pageLocation") == "시스템 구성" and r.page.title().startswith("시스템 구성"), r.page.title())

    # 품질: AI 일꾼(워커)은 상태 점 목록(layers.js)에 없다 — 워커가 꺼져도 홈은 모두 초록인데 AI 단계는 무한 대기한다.
    status = r.get(r.process + "/api/agents/status")
    shown = "일꾼" in _a_all_txt(r, "#view-main") + _a_all_txt(r, "#view-home") + text
    r.check("AI 일꾼(워커) 상태가 홈 · 시스템 구성에 보인다(꺼지면 학생이 알 수 있다)", shown,
            f"워커 연결 {status.get('reachable')} · 화면 표시 {'있음' if shown else '없음 — 처리 건 화면의 접힌 「지금 일하는 AI 일꾼」에만 있음(agentsPanel.js)'}", kind="quality")

    # 예외(실제로 끄지 않는다): 브라우저 안에서만 설비 시뮬레이터 응답을 막아 「서비스 하나가 꺼진 홈」을 본다.
    # page.route 는 이 탭의 요청만 가로챈다 — 서버 상태는 그대로다. 이 사이의 콘솔 · 실패 요청은 모의 기록으로 따로 두고 버린다.
    lab_code, r.lab = r.lab, f"{r.lab}~모의"
    pattern = re.compile(re.escape(r.plant) + r"/(healthz|api/state).*")
    seen: dict = {}
    try:
        r.page.route(pattern, lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"Not Found"}'))
        r.tab("main")
        seen["header"] = r.wait(20, lambda: (lambda h: h if 0 <= h[0] < h[1] else None)(_a_header_health(r)), every=1)
        r.page.wait_for_timeout(2500)
        seen["stats"] = _a_txt(r, "#mainStats")
        seen["live"] = _a_all_txt(r, "#mLive")
        r.tab("scenario")
        r.page.wait_for_timeout(1500)
        seen["scenario"] = _a_txt(r, "#units")
    finally:
        r.page.unroute(pattern)
    r.tab("main")
    back = r.wait(25, lambda: (lambda h: h if h[1] > 0 and h[0] == h[1] else None)(_a_header_health(r)), every=1)
    r.page.wait_for_timeout(1500)
    seen["stats_back"] = _a_txt(r, "#mainStats")
    r.logs.pop(r.lab, None)
    r.lab = lab_code
    h = seen.get("header")
    r.check("(모의) 설비가 꺼지면 상단이 「서비스 n-1/n — 응답 없음: plant-sim」", bool(h) and "응답 없음" in h[3] and "plant" in h[3] and "down" in h[2],
            h[3] if h else "상태 점이 바뀌지 않음", kind="exception")
    ok, why = r.human_message(seen.get("stats", ""))
    r.check("(모의) 홈 요약이 한국어로 「설비 연결 끊김」과 다시 연결 안내", ok and "끊김" in seen.get("stats", "") and "연결되면" in seen.get("stats", ""), why, kind="exception")
    r.check("(모의) 결함 시뮬레이션 화면도 연결 불가를 한국어로 안내(빈 화면 아님)", "연결할 수 없습니다" in seen.get("scenario", ""), seen.get("scenario", "")[:160], kind="exception")
    r.check("(모의) 응답이 돌아오면 새로 고침 없이 모두 초록 · 요약 복귀", bool(back) and "3기" in seen.get("stats_back", ""), seen.get("stats_back", "")[:120], kind="exception")


# ====================================================================== part_D
# part_D — 실습 02 · 03 · 04 · 05b · 08 · 90 · 91 (메인 작성). part_A 의 _a_ 도우미와 part_C 의 _c_ 승인 도우미를 쓴다.

D_AGENT_LIMIT_S = 300        # 학생 진행 기준: AI 판단 한 단계 5분(C_AI_LIMIT_S 와 같다)
D_AGENT_WAIT_S = 600         # 기다림 상한(느린 중계 · PC)


def _d_deferral_panel(r, pid: str) -> str:
    """처리 건 상세의 보류 패널 글자(없으면 '')."""
    _a_select_instance(r, pid)
    r.wait(20, lambda: r.page.locator(f"#instDetail [data-deferral-task]").count() > 0, every=1)
    return _a_all_txt(r, "#instDetail [data-deferral-task]")


def _d_one_a(r, i: int, mode: str) -> dict:
    """쿨러 열화 한 번: 경보 → 처리 건 → AI 판단 → (mode) → 쿨러 복구 · 정리. mode: defer(구조판) · approve · reject · late."""
    if not _a_ensure_idle(r):
        return {"error": "앞 처리 건 · 경보가 정리되지 않아 주입하지 못함"}
    pid, t0, msg = _a_degrade(r)
    if not pid:
        return {"error": f"[쿨러 열화] 뒤 처리 건이 열리지 않음: {msg}"}
    got = _a_wait_agent(r, pid, D_AGENT_WAIT_S)
    view = got["view"]
    out = {"pid": pid, "outcome": got["outcome"], "seconds": _a_agent_seconds(view), "flow": view["instance"]["proc_def_id"]}
    try:
        if got["outcome"] == "보류":
            text = _d_deferral_panel(r, pid)
            ok, why = r.human_message(text)
            if i == 0:
                r.check("보류 안내가 처리 건 화면에 한국어로(무엇이 없어서 멈췄는지)", ok and "보류" in text, why, kind="exception")
                r.check("보류 패널에 [다시 평가]가 있다(따라붙는 길)", r.page.locator("#instDetail [data-reassess]").count() > 0, text[:200], kind="exception")
            out["deferral_status"] = (got.get("deferral") or {}).get("assessment", {}).get("status")
            if mode == "defer" and i == 0:
                # 예외: 사유 없이 [다시 평가] → 한국어 필수 안내
                r.page.fill("#instDetail [data-reassess-reason]", "")
                r.page.click("#instDetail [data-reassess]")
                r.page.wait_for_timeout(800)
                err = _a_all_txt(r, "#instDetail [data-deferral-task] .form-msg")
                ok2, why2 = r.human_message(err)
                r.check("[다시 평가] 사유 빈칸 → 한국어 필수 안내", ok2, why2, kind="exception")
                # 정상: 사유를 넣고 [다시 평가] → 지식이 없으니 다시 보류(같은 결과) 또는 진행
                r.page.fill("#instDetail [data-reassess-by]", "학생 한 명")
                r.page.fill("#instDetail [data-reassess-reason]", "센서 값을 다시 보고 판단해 주세요")
                r.page.click("#instDetail [data-reassess]")
                again = r.wait(D_AGENT_WAIT_S, lambda: (lambda v: v if any(e.get("event_type") == "task_deferred" for e in v.get("events") or []) and
                                                         len([e for e in v.get("events") or [] if e.get("event_type") == "task_deferred"]) >= 2 else None)(_a_view(r, pid)), every=5)
                r.check("[다시 평가] → 원천을 다시 읽고 같은 판정(보류)을 다시 남김", bool(again), "다시 보류 기록 없음" if not again else "다시 보류", kind="exception")
        elif got["outcome"] == "승인 대기":
            dec = _c_decision(r, view)
            card = _c_card(dec)
            out.update({k: card[k] for k in ("recommended", "approver", "evidence")})
            approver = card.get("approver")
            person = C_PEOPLE.get(approver or "", "")
            task = _c_item(view, "운전원 승인") or _a_rows(view).get("T_approve") or {}
            if mode == "late":
                # 승인 지연 알림(PT10M = 실제 30초)과 예측 유효시간(실제 90초)을 지나 승인 → [미리 보기] 길
                time.sleep(100)
                v2 = _a_view(r, pid)
                notice = _a_rows(v2).get("T_notice") or {}
                r.check("승인을 미루면 30초쯤 뒤 「승인 지연 알림」이 나고 승인 단계는 그대로 기다린다",
                        notice.get("status") in ("DONE", "COMPLETED") and (_a_rows(v2).get("T_approve") or {}).get("status") == "IN_PROGRESS",
                        f"알림 {notice.get('status')} · 승인 {(_a_rows(v2).get('T_approve') or {}).get('status')}", kind="exception")
            if mode in ("approve", "late") and i == 0 and approver and approver != "role:operator":
                _c_me(r, "user:kim-op")
                done, text = _c_card_decide(r, pid, task, approve=True)
                ok, why = r.human_message(text)
                r.check(f"승인 역할이 {approver} 인 카드를 운전원이 승인 → 거절 · 한국어 안내", not done and ok, why, kind="exception")
            if not person:
                r.check("추천 카드의 승인 역할을 알 수 있다", False, json.dumps(card, ensure_ascii=False))
            else:
                _c_me(r, person)
                done, text = _c_card_decide(r, pid, task, approve=(mode != "reject"), reason="" if mode != "reject" else "생산 일정상 지금은 안 됩니다")
                out["decided"] = done
                end = _c_wait_end(r, pid, 600)
                rows = _a_rows(end)
                out["end"] = end["instance"]["status"]
                if mode == "reject":
                    r.check("거절 → 결과 보고(거절)로 닫히고 냉각 명령은 나가지 않음",
                            (rows.get("R_rejected") or {}).get("status") in ("DONE", "COMPLETED") and (rows.get("T_cmd") or {}).get("status") not in ("DONE", "COMPLETED"),
                            f"끝 {out['end']} · 거절 보고 {(rows.get('R_rejected') or {}).get('status')} · 명령 {(rows.get('T_cmd') or {}).get('status')}", kind="exception")
                else:
                    ok_end = any((rows.get(k) or {}).get("status") in ("DONE", "COMPLETED") for k in ("R_ok", "R_fail"))
                    r.check("승인 → 냉각 명령 → 재관측 → 결과 보고로 닫힘", ok_end and (rows.get("T_cmd") or {}).get("status") in ("DONE", "COMPLETED"),
                            f"끝 {out['end']} · 명령 {(rows.get('T_cmd') or {}).get('status')} · 정상 {(rows.get('R_ok') or {}).get('status')} · 미달 {(rows.get('R_fail') or {}).get('status')}")
                    out["result"] = "정상" if (rows.get("R_ok") or {}).get("status") in ("DONE", "COMPLETED") else "미달"
        else:
            r.check(f"AI 판단이 보류 또는 승인 대기로 끝남(처리 건 {pid})", False, got["outcome"])
    finally:
        _a_restore_and_close(r, pid)
    return out


# ====================================================================== 02 · 1-3 전체 과정 (수업 시작 상태 = 구조판, 문서 적재 전)
# 수업 시작 상태 = 구조판 + 수업용 기본 지식(시작 스크립트 7/8, 사용자 결정 2026-10-25). 그래서 1-3 전체 과정이 처음부터 승인까지 간다.
# 구조판만의 「보류 → [다시 평가]」 길은 _d_one_a(mode="defer")로 남겨 둔다(지식이 빠진 PC — 93 펌프 · 팬의 보류 뒤 재평가와 같은 화면).
@lab("02", "1-3 전체 과정 — 쿨러 열화 → 경보 → AI 판단 → 승인(잘못된 역할 거절) · 거절 · 지연 알림 → 명령 · 재관측 · 결과 (AI 3회)")
def lab_02_full_flow(r: Round):
    modes = ["approve", "reject", "late"]
    runs = r.repeat3("A 판단", lambda i: _d_one_a(r, i, modes[i]), ("outcome", "recommended", "approver", "evidence"), limit_s=D_AGENT_LIMIT_S)
    r.memo["02_cards"] = runs
    if runs and runs[0].get("approver") and runs[0]["approver"] != "role:operator":
        r.check("추천 카드의 승인 역할이 흐름의 승인 담당(운전원)과 같다 — 다르면 가이드에 「카드의 승인 역할을 보고 「나」를 고른다」가 필요",
                False, f"카드 승인 역할 {runs[0]['approver']} · 흐름 담당 운전원", kind="quality")


# ====================================================================== 03 · 2-2 지식 지도
def _d_onto(r, asset: str = "HYD-01") -> dict:
    r.tab("ontology")
    r.page.select_option("#ontoAsset", asset)
    r.wait(30, lambda: "항목" in _a_txt(r, "#ontoStats"), every=1)
    stats = _a_txt(r, "#ontoStats")
    g = r.get(f"{r.agent}/api/ontology/graph?asset={asset}")
    labels: dict = {}
    for n in g["nodes"]:
        labels[n["label"]] = labels.get(n["label"], 0) + 1
    return {"stats": stats, "nodes": len(g["nodes"]), "edges": len(g["edges"]), "labels": labels, "graph": g}


@lab("03", "2-2 지식 지도 — 설비 선택 → 연결 · 속성 · 방향 (수업 시작 상태: 구조판 + 기본 지식)")
def lab_03_ontology(r: Round):
    o = _d_onto(r)
    m = re.search(r"항목\s*([\d,]+)\s*·\s*연결\s*([\d,]+)", o["stats"])
    r.check("지식 지도 숫자(항목 · 연결) = 그래프 API", bool(m) and (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) == (o["nodes"], o["edges"]),
            f"화면 {o['stats']} / API {o['nodes']}·{o['edges']}")
    r.memo["03_before"] = {k: o[k] for k in ("nodes", "edges", "labels")}
    # 설비 노드를 누르면 오른쪽에 종류 · 속성 · 나가는/들어오는 연결(방향)
    node = r.page.locator("#ontoMap [data-id='asset:hyd-01']").first        # 설비 노드 id(그래프 API) — 화면 이름은 HYD-01
    if node.count():
        node.click()
        r.page.wait_for_timeout(800)
    panel = _a_txt(r, "#ontoNode")
    r.check("설비(HYD-01)를 누르면 종류 · 속성 · 연결 방향(→ 나감 / ← 들어옴)이 보인다", "HYD-01" in panel and ("→" in panel or "←" in panel), panel[:300])
    raw = _a_raw_ids(panel)
    r.check("노드 설명에 학생이 못 읽는 영문 상수 · 원문 id 가 적다", len(raw) <= 3, ", ".join(raw), kind="quality")
    # 연결 하나를 눌러 따라가기
    link = r.page.locator("#ontoNode [data-go]").first
    if link.count():
        target = link.get_attribute("data-go")
        link.click(); r.page.wait_for_timeout(800)
        r.check("연결을 누르면 그 노드로 옮겨 간다", target and target in r.page.content(), target or "")
    # 예외: 없는 이름 검색 → 「검색 결과 0개」(빈 화면 · 오류 아님)
    r.page.fill("#ontoSearch", "없는설비XYZ")
    r.page.wait_for_timeout(800)
    st = _a_txt(r, "#ontoStats")
    r.check("없는 이름을 검색하면 「검색 결과 0개」로 알린다", "검색 결과 0개" in st, st, kind="exception")
    r.page.fill("#ontoSearch", "")
    # 수업용 기본 지식: 쿨러 매뉴얼의 고장 유형 · 원인 · 조치 방법이 이미 보인다(3회차 판단 · What-if 의 전제)
    r.check("기본 지식: 조치 방법(Skill) · 고장 유형 · 원인이 보인다", o["labels"].get("Skill", 0) >= 5 and o["labels"].get("FailureMode", 0) >= 1 and o["labels"].get("Cause", 0) >= 3,
            json.dumps(o["labels"], ensure_ascii=False)[:300])


@lab("05c", "2-2 지식 지도 다시 — 4회차 개정 적재 뒤에도 조치 · 원인 지식이 그대로(줄지 않음)")
def lab_05c_ontology_after(r: Round):
    before = r.memo.get("03_before") or _d_onto(r)
    o = _d_onto(r)
    shrank = {k: (v, o["labels"].get(k, 0)) for k, v in before.get("labels", {}).items() if k in ("Skill", "FailureMode", "Cause", "Rule") and o["labels"].get(k, 0) < v}
    r.check("개정 적재 뒤 조치 방법 · 고장 유형 · 원인 · 규칙이 줄지 않았다", not shrank, json.dumps(shrank or o["labels"], ensure_ascii=False)[:400])


# ====================================================================== 04 · 3-1 조치 판단 규칙 · 손익/What-if · 성과 지표 (구조판 — 적재 전 차시)
def _d_decide(r, **facts) -> str:
    r.tab("decision")
    r.wait(20, lambda: r.page.locator("#decPattern option").count() > 0, every=1)
    r.page.select_option("#decAsset", "HYD-01")
    r.page.select_option("#decPattern", "COOLER_DEGRADATION")
    r.page.select_option("#decMode", facts.get("mode", ""))
    r.page.select_option("#decState", facts.get("state", ""))
    r.page.select_option("#decStandby", facts.get("standby", ""))
    r.page.fill("#decFan", str(facts.get("fan", "")))
    r.page.click("#decRun")
    r.wait(120, lambda: r.page.locator("#decRun").inner_text().strip() != _a_txt(r, "#decRun") or not r.page.locator("#decRun").is_disabled(), every=1)
    r.wait(120, lambda: not r.page.locator("#decRun").is_disabled(), every=1)
    r.page.wait_for_timeout(800)
    return _a_txt(r, "#decResult", 5000)


@lab("04", "3-1 조치 판단 규칙 · 손익/What-if · 성과 지표 — 입력 · 규칙 · 후보 → 시험값 → 허용 · 제외 · 순위 · KPI")
def lab_04_rules_whatif_kpi(r: Round):
    ent_before = r.get(r.enterprise + "/api/state")
    graph_before = r.get(f"{r.agent}/api/ontology/graph?asset=HYD-01")
    base = _d_decide(r)
    ok, why = r.human_message(base)
    r.check("[판단 실행](현재 값) → 결과가 한국어로 보인다(빈 화면 · 영문 오류 아님)", ok, why)
    r.memo["04_base"] = base[:600]
    n_cards = r.page.locator("#decResult .hitl-opts > *").count()
    r.check("조치 후보 카드가 보이거나, 없으면 왜 없는지 안내한다(구조판)", n_cards > 0 or ("없" in base), f"후보 {n_cards} · {base[:200]}")
    # 수업 지식(HM-8)에는 보호 정지 규칙이 없다 — 결과가 같으면 화면이 그 이유를 말해야 한다(2026-10-25 결함: 말없이 같은 결과)
    trip = _d_decide(r, state="TRIP")
    r.check("설비 상태를 「보호 정지」로 바꾸면 결과가 달라지거나, 그 조건을 읽는 규칙이 없다고 알린다", trip != base or "결과에 영향이 없습니다" in trip, trip[:300], kind="exception")
    # HM-8 8절: 원격 조치는 REMOTE_AUTO 일 때만 — 원격 수동이면 원격 제어 후보가 빠져야 한다
    manual = _d_decide(r, mode="REMOTE_MANUAL")
    r.check("운전 모드를 「원격 수동」으로 바꾸면 원격 제어 후보가 빠지거나 제외 사유가 보인다", manual != base and ("제외" in manual or manual.count("점수") < base.count("점수")), manual[:300], kind="exception")
    neg = _d_decide(r, fan=-5)
    ok, why = r.human_message(neg)
    r.check("팬 연속 운전 시간에 음수를 넣으면 한국어로 거절하거나 무시를 알린다", ok, why, kind="exception")
    # 손익 · What-if: 기준 불러오기 → 값 바꿔 보기 → 다시 계산 → 원래대로
    r.tab("whatif")
    r.wait(20, lambda: r.page.locator("#wiPattern option").count() > 0, every=1)
    r.page.select_option("#wiAsset", "HYD-01")
    r.page.select_option("#wiPattern", "COOLER_DEGRADATION")
    r.page.click("#wiLoad")
    r.wait(120, lambda: r.page.locator("[data-wi-tab]").count() > 0 or r.page.locator("#whatifView p.neg").count() > 0, every=1)
    view = _a_txt(r, "#whatifView", 5000)
    loaded = r.page.locator("[data-wi-tab]").count() > 0
    ok, why = r.human_message(view)
    r.check("손익 · What-if 기준을 불러온다(못 하면 한국어로 이유)", loaded or ok, view[:300])
    if loaded:
        r.check("요약에 「원본 그대로」 표시", "원본 그대로" in view, view[:200])
        r.page.locator("[data-wi-tab='values']").click()
        fields = r.page.locator("[data-wi-var]")
        if fields.count():
            fields.first.fill("1")
            r.page.click("#wiTry")
            r.wait(60, lambda: "시험값 1개 적용 중" in _a_txt(r, "#whatifView"), every=1)
            after = _a_txt(r, "#whatifView", 5000)
            r.check("값 하나를 바꿔 다시 계산 → 「시험값 1개 적용 중」 · 원본 그대로", "시험값 1개 적용 중" in after and "원본 그대로" in after, after[:300])
            if r.page.locator("#wiReset").count():
                r.page.click("#wiReset"); r.page.wait_for_timeout(800)
                r.check("[원래대로] → 시험값이 사라진다", "적용 중" not in _a_txt(r, "#whatifView"), "", kind="exception")
        else:
            r.check("「값 바꿔 보기」에 바꿀 수 있는 값이 있다", False, _a_txt(r, "#whatifView")[:300])
    # 성과 지표: 시험 목표 → 시험 판정 → 원래대로
    r.tab("kpi")
    r.wait(30, lambda: r.page.locator("[data-kpi-target]").count() > 0 or "없" in _a_txt(r, "#kpiView"), every=1)
    kpi_before = r.get(r.process + "/api/kpi?period=week") if r.api("GET", r.process + "/api/kpi?period=week")[0] == 200 else None
    tgt = r.page.locator("[data-kpi-target]")
    if tgt.count():
        r.page.wait_for_timeout(2000)                                      # 첫 불러오기가 표를 다시 그리는 동안 칸이 바뀐다(1차: fill 시간 초과)
        fold = r.page.locator("#kpiView details").filter(has_text="목표값 바꿔 보기").first   # 시험 칸은 접혀 있다 — 학생처럼 먼저 연다
        if fold.count() and not fold.evaluate("d => d.open"):
            fold.locator("summary").first.click()
            r.page.wait_for_timeout(500)
        for _ in range(3):
            try:
                r.page.locator("[data-kpi-target]").first.fill("1", timeout=5000)
                break
            except Exception:
                r.page.wait_for_timeout(1500)
        r.page.locator("[data-kpi-trial-run]").first.click()
        r.page.wait_for_timeout(2500)
        txt = _a_txt(r, "#kpiView", 5000)
        ok, why = r.human_message(txt)
        r.check("성과 지표 시험 목표 → [시험 판정] 결과가 보인다", ok and r.page.locator("[data-kpi-trial-reset]").count() > 0, why)
        r.page.locator("[data-kpi-trial-reset]").first.click(); r.page.wait_for_timeout(1500)
    else:
        r.check("성과 지표 화면에 시험 목표 칸이 있다", False, _a_txt(r, "#kpiView")[:300])
    kpi_after = r.get(r.process + "/api/kpi?period=week") if kpi_before is not None else None
    # 업무 DB 의 납기까지 남은 시간(due_in_h · alt_free_h)은 시계와 함께 줄어든다 — 시험값이 바꾼 것만 본다
    def _still(v):
        if isinstance(v, dict):
            return {k: _still(x) for k, x in v.items() if not k.endswith("_in_h") and not k.endswith("_free_h")}
        return [_still(x) for x in v] if isinstance(v, list) else v
    changed = [name for name, same in (
        ("업무 DB", _still(r.get(r.enterprise + "/api/state")) == _still(ent_before)),
        ("지식 그래프", len(r.get(f"{r.agent}/api/ontology/graph?asset=HYD-01")["nodes"]) == len(graph_before["nodes"])),
        ("KPI", kpi_before is None or json.dumps(_still(kpi_before), sort_keys=True) == json.dumps(_still(kpi_after), sort_keys=True))) if not same]
    r.check("시험값 · 시험 목표가 원본(업무 DB · 지식 · KPI)을 바꾸지 않았다", not changed, "바뀐 곳: " + (", ".join(changed) or "없음"), kind="exception")


# ====================================================================== 08 · 7-1 사람의 확인 (적재 뒤 — 승인 대기 건으로)
@lab("08", "7-1 사람의 확인 — 작업함 · 권한 없는 사람 · 「나」 없음 · 권한 있는 사람의 거절")
def lab_08_human(r: Round):
    if not _a_ensure_idle(r):
        r.check("앞 처리 건 정리", False, "쿨러 경보가 풀리지 않음"); return
    pid, _t0, msg = _a_degrade(r)
    if not pid:
        r.check("[쿨러 열화] → 처리 건", False, msg); return
    try:
        got = _a_wait_agent(r, pid, D_AGENT_WAIT_S)
        if got["outcome"] != "승인 대기":
            r.check("승인 대기 건이 생긴다(적재 뒤)", False, got["outcome"]); return
        card = _c_card(_c_decision(r, got["view"]))
        person = C_PEOPLE.get(card.get("approver") or "", "")
        task = _a_rows(got["view"]).get("T_approve") or {}
        # 권한 있는 사람의 작업함에는 보이고, 관계없는 사람(구매 담당)에게는 안 보인다
        _c_me(r, person)
        r.page.wait_for_timeout(1500)
        mine = r.page.locator(f"a.item[data-inbox-link*='{task.get('id')}']").count()
        _c_me(r, "user:jung-buy")
        r.page.wait_for_timeout(1500)
        other = r.page.locator(f"a.item[data-inbox-link*='{task.get('id')}']").count()
        r.check("승인 대기 건이 권한 있는 사람의 작업함에 보인다", mine > 0, f"{person}: {mine}")
        r.check("관계없는 사람(구매 담당)의 작업함에는 보이지 않는다", other == 0, f"jung-buy: {other}", kind="exception")
        done, text = _c_card_decide(r, pid, task, approve=True)
        ok, why = r.human_message(text)
        r.check("권한 없는 사람이 열어 승인 → 막히고 한국어로 이유", not done and ok, why, kind="exception")
        # 「나」를 비우면 승인 · 거절 대신 「나」를 고르라는 안내
        _a_pick_me(r, "")
        _c_open_task(r, pid, task["id"])
        hint = _a_txt(r, "#todoPanel", 5000)
        r.check("「나」를 고르지 않으면 승인 대신 고르라는 안내가 보인다", "나" in hint and r.page.locator("#tdGo").is_disabled(), hint[:300], kind="exception")
        _c_me(r, person)
        done, text = _c_card_decide(r, pid, task, approve=False, reason="부품 확인 후 다시 판단")
        end = _c_wait_end(r, pid, 300)
        rows = _a_rows(end)
        r.check("권한 있는 사람의 거절 → 결과 보고(거절)로 닫힘 · 설비 명령 없음",
                (rows.get("R_rejected") or {}).get("status") in ("DONE", "COMPLETED") and (rows.get("T_cmd") or {}).get("status") not in ("DONE", "COMPLETED"),
                f"{end['instance']['status']} · {text}")
    finally:
        _a_restore_and_close(r, pid)


# ====================================================================== 90 · 그 밖에: 메뉴 순회
@lab("90", "그 밖에 — 포털 모든 메뉴 순회(JS 오류 · 실패한 요청 · 빈 화면 · 영문 오류)")
def lab_90_menu_sweep(r: Round):
    tabs = r.page.eval_on_selector_all("button[data-tab]", "bs => bs.map(b => [b.dataset.tab, b.innerText.trim()])")
    for tab, title in tabs:
        button = r.page.locator(f"button[data-tab='{tab}']").first
        if button.is_disabled():
            # 수업 잠금이 닫은 메뉴(courseAccess.js closedTabs) — 열리지 않는 것이 정상이고, 이유가 사람 글이어야 한다
            ok, why = r.human_message(button.get_attribute("title") or "")
            r.check(f"메뉴 「{title}」 — 수업 잠금으로 꺼짐 · 이유를 알린다", ok and bool(button.get_attribute("title")), why, kind="exception")
            continue
        try:
            r.tab(tab)
            r.page.wait_for_timeout(2500)
            view = r.page.locator(f"#view-{tab}")
            text = view.inner_text(timeout=5000) if view.count() else r.page.locator("main").inner_text()
            bad = re.search(r"Traceback|TypeError|ReferenceError|undefined|\[object Object\]|NaN|Internal Server Error", text)
            r.check(f"메뉴 「{title}」 — 화면이 비지 않고 영문 오류가 없다", len(text.strip()) > 20 and not bad, (bad.group(0) if bad else text[:80]).replace("\n", " "),
                    kind="quality")
        except Exception as e:
            r.check(f"메뉴 「{title}」 열기", False, f"{type(e).__name__}: {e}")


# ====================================================================== 91 · 그 밖에: 구성 내보내기 → 기준으로 되돌리기 → 불러오기
@lab("91", "그 밖에 — 구성 내보내기 → 기준으로 되돌리기(수업 흐름 남김) → 불러오기, 깨진 파일")
def lab_91_config_bundle(r: Round):
    r.tab("admin")
    panel = r.page.locator("#configBundlePanel")                         # 관리 탭의 접힌 칸 — 학생처럼 먼저 연다
    if panel.count() and not panel.evaluate("d => d.open"):
        panel.locator(":scope > summary").click()
    r.page.wait_for_selector("#cfgExport", timeout=15_000)
    with r.page.expect_download(timeout=60_000) as dl:
        r.page.click("#cfgExport")
    path = r.out / "starter.json"
    dl.value.save_as(str(path))
    bundle = json.loads(path.read_text(encoding="utf-8"))
    r.check("[파일 받기] → 내가 만든 구성 파일(비밀값 없음)", isinstance(bundle, dict) and "summary" in bundle and "LLM_API_KEY" not in path.read_text(encoding="utf-8"),
            _a_txt(r, "#cfgExportMsg"))
    agents_before = len(r.get(r.process + "/api/agents")) if r.api("GET", r.process + "/api/agents")[0] == 200 else None
    # 기준으로 되돌리기 → 수업 흐름은 남는다
    r.page.click("#cfgReset")
    r.page.locator("dialog.confirm-dialog button[value=ok]").click()
    r.wait(60, lambda: _a_txt(r, "#cfgResetMsg"), every=1)
    rmsg = _a_txt(r, "#cfgResetMsg")
    ok, why = r.human_message(rmsg)
    routes = _c_routes(r)
    r.check("[기준으로 되돌리기] → 한국어 결과 · 수업 흐름(c3_*)은 경보 경로에 남음", ok and all((routes.get(p) or {}).get("class_flow") for p in ("COOLER_DEGRADATION", "PM_DUE", "SPARE_BELOW_MIN")),
            f"{why} · {json.dumps({p: (routes.get(p) or {}).get('definition') for p in ('COOLER_DEGRADATION', 'PM_DUE', 'SPARE_BELOW_MIN')}, ensure_ascii=False)}")
    # 예외: 깨진 파일
    bad = r.out / "broken.json"
    bad.write_text("{ 이건 JSON 이 아님", encoding="utf-8")
    r.page.set_input_files("#cfgFile", str(bad))
    r.page.wait_for_timeout(800)
    bmsg = _a_txt(r, "#cfgImportMsg")
    r.check("깨진 파일을 고르면 「JSON 파일이 아닙니다」로 막는다", "JSON 파일이 아닙니다" in bmsg, bmsg, kind="exception")
    # 받은 파일 불러오기 → 내가 만든 것이 돌아온다
    r.page.set_input_files("#cfgFile", str(path))
    r.page.wait_for_timeout(800)
    r.page.click("#cfgImport")
    r.page.locator("dialog.confirm-dialog button[value=ok]").click()
    r.wait(180, lambda: (t := _a_txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=2)
    imsg = _a_txt(r, "#cfgImportMsg")
    if r.page.locator("#cfgSkip").count():                                # 비밀값이 필요한 서버가 있으면 건너뛰고 불러오기
        r.page.click("#cfgSkip")
        r.wait(180, lambda: (t := _a_txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=2)
        imsg = _a_txt(r, "#cfgImportMsg")
    # 7회차에 등록한 학생 MCP 서버가 꺼져 있으면 불러오기는 연결 검사에서 멈추고 통째로 되돌린다(설계) — 학생은 안내대로 서버를 켜고 다시 누른다
    down = re.search(r"host\.docker\.internal:(\d+)", imsg) if "연결 검사 실패" in imsg else None
    if down:
        ok, why = r.human_message(imsg)
        r.check("학생 MCP 서버가 꺼져 있으면 → 서버를 켜라는 한국어 안내 · 불러오기 전 상태로 되돌림", ok and "되돌려" in imsg, imsg[:300], kind="exception")
        proc, up = _b_start_mcp(r, _b_student_schema(r), int(down.group(1)))
        try:
            r.check("안내대로 학생 MCP 서버를 켰다", up, down.group(1))
            r.page.click("#cfgImport")
            r.page.locator("dialog.confirm-dialog button[value=ok]").click()
            r.wait(180, lambda: (t := _a_txt(r, "#cfgImportMsg")) and "불러오는 중" not in t and t != imsg, every=2)
            imsg = _a_txt(r, "#cfgImportMsg")
            if r.page.locator("#cfgSkip").count():
                r.page.click("#cfgSkip")
                r.wait(180, lambda: (t := _a_txt(r, "#cfgImportMsg")) and "불러오는 중" not in t, every=2)
                imsg = _a_txt(r, "#cfgImportMsg")
        finally:
            _b_stop_mcp(proc)
    ok, why = r.human_message(imsg)
    agents_after = len(r.get(r.process + "/api/agents")) if agents_before is not None else None
    r.check("받은 파일 [불러오기] → 한국어 결과 · 내가 만든 에이전트 수가 돌아옴", ok and (agents_before is None or agents_after == agents_before),
            f"{why} · 에이전트 {agents_before} → {agents_after}")


# ====================================================================== part_B
# ====================================================================== part B — 실습 05 · 06 · 07 (지식 관리 · 나의 첫 에이전트 · 도구(MCP))
# class_round.py 의 「실습」 절(LABS 정의 뒤)에 그대로 붙인다. 하네스의 lab · Round · ROOT · host_ports 만 쓴다.
# 필요한 import(대부분 class_round.py 머리에 이미 있음): json, re, sys, time, urllib.request, urllib.parse(quote · unquote),
#   difflib(SequenceMatcher), os, secrets, socket, subprocess — 아래 함수 안에서 지역 import 로도 불러 둔다(붙여 넣기만 하면 돈다).
# 셀렉터 표기: 「라이브 확인」 = 2026-10-25 라이브 포털에서 읽기로 본 것, 「코드 확인」 = it/portal/www/*.js 를 읽어 확정했지만
#   상태를 바꿔야 그려지는 것(미리보기 뒤 · 저장 뒤)이라 라이브로 못 본 것. 「# 미확인」 = 코드에서도 확정 못 한 것.
# 시간: 지식 추출 · 질문은 20배속 시간 창(승인 요청 30초 · 예측 유효시간)과 무관하다(사람 승인 단계가 없는 정의:
#   manual_source_extraction · ask_agent). 한도는 「느린 PC에서도 수업 안에 끝나는가」로 잡는다 — 근거는 각 상수 주석.

_B_DOC_DIR = ROOT / "문서/시스템/참조/수업_문서_원문"
_B_DOC_FILES = {"HM-8": "HM-8_cooler-fan-manual.md", "PM-02": "PM-02_powerpack-pm-checklist.md", "PR-07": "PR-07_spare-parts-standard.md"}
# 추출 한 번의 한도: 실측 PR-07 116~141초(3_현황 2절), 워커 실행 한도 1800초(compose CLIAGENTS_RUN_TIMEOUT_SECONDS).
# 교정 1~2회(검사 거부 → AI 재작성)를 넣어 4배 = 600초. 이보다 느리면 50분 실습 안에 세 문서를 못 끝낸다.
_B_EXTRACT_LIMIT_S = 600
# 질문 한 번의 한도: 시간 창 없음(ask_agent 정의에 타이머 없음). A 전체(215~218초)보다 짧아야 수업 흐름이 선다 → 300초.
_B_ASK_LIMIT_S = 300
_B_ASK_LIVE = {"waiting", "running", "submitted", "correcting", "asking"}      # ask.js LIVE 와 같은 낱말
_B_AGENT_NAME = "나의 쿨러 점검 에이전트"                                      # students/_template/agent/goal.md 칸 설명대로
_B_MCP_NAME = "s01-table"                                                     # mcp_registry.NAME_RE: 소문자 · 숫자 · 하이픈
_B_STUDENT = "s01"


# ---------------------------------------------------------------------- 공통 도우미 (part B 전용, 이름 앞 _b_)
def _b_toast_text(r, timeout_s: float = 10) -> str:
    """가장 최근 토스트 문구(ui.js UI.toast: #toastHost .toast). 없으면 ''."""
    loc = r.page.locator("#toastHost .toast")
    try:
        loc.last.wait_for(timeout=timeout_s * 1000)
        return loc.last.inner_text().replace("×", "").strip()
    except Exception:
        return ""


def _b_clear_toasts(r):
    try:
        r.page.evaluate("() => document.querySelectorAll('#toastHost .toast').forEach(n => n.remove())")
    except Exception:
        pass


def _b_source_procedures(text: str) -> dict:
    """원문 Markdown 의 「### SOP-…」 블록 → {sop: {title, steps:[문장], approver}} (번호 목록만 단계로 읽는다 — 추출 지시와 같은 규칙)."""
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^###\s+(SOP-[A-Z0-9-]+)\s+(.*)$", line.strip())
        if m:
            cur = out.setdefault(m.group(1), {"title": m.group(2).strip(), "steps": [], "approver": None})
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is None:
            continue
        s = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if s:
            cur["steps"].append(s.group(2).strip())
        a = re.match(r"^승인:\s*([^.。]+)", line.strip())
        if a:
            cur["approver"] = a.group(1).strip()
    return out


def _b_source_failure_phrases(text: str) -> list[str]:
    """원문이 「X은 …에서 생기는 고장」「X는 …에서 생기며」로 정의한 고장 유형 이름(대상 설비 대조용). HM-8.4 · PM-2.10 꼴."""
    return [m.group(1).strip() for m in re.finditer(r"([가-힣][가-힣 ]{3,30}?)(?:은|는) [가-힣A-Z0-9 ]{1,20}에서 생기", text)]


_B_NEG = ("않", "금지", "아니면", "뒤에만", "에만", "이내", "미만", "이하", "이상", "넘으면")
_B_UNIT = re.compile(r"℃|%|mm/s|mm|bar|l/min|분|시간|만 원|명|개|h\b")


def _b_step_findings(src_step: str, got: str) -> list[str]:
    """원문 단계 vs 추출 단계: 부정 조건 · 수치 · 단위가 빠졌으면 그 종류를 돌려준다(빈 목록 = 맞음)."""
    bad = []
    for w in _B_NEG:
        if w in src_step and w not in got:
            bad.append(f"부정·제한 조건 '{w}' 빠짐")
    for n in re.findall(r"\d+(?:[.,]\d+)?", src_step):
        if n not in got:
            bad.append(f"수치 {n} 빠짐")
    for u in set(_B_UNIT.findall(src_step)):
        if u not in got:
            bad.append(f"단위 {u} 빠짐")
    return bad


def _b_quality(src: dict, preview: dict) -> list[dict]:
    """추출 제안을 원문과 대조: 누락 SOP · 원문에 없는 SOP(오추출) · 단계 수 · 단계 순서 · 부정 조건 · 수치 · 단위.
    정답을 넣지 않는다 — 기준은 원문 파일 자체(_b_source_procedures)다."""
    from difflib import SequenceMatcher
    found = []
    got = {p["id"]: p for p in preview.get("procedures") or []}
    for sop in src:
        if sop not in got:
            found.append({"sop": sop, "order": None, "kind": "누락 절차"})
    for sop, p in got.items():
        if sop not in src:
            # 번호 없는 절의 업무 절차(예: PM-2.9 시운전 확인 → SOP-PM-2-9)는 추출 지시 범위이고 검토본(class-knowledge)에도 있다
            if p.get("section") and re.sub(r"[^A-Z0-9]", "", sop) == "SOP" + re.sub(r"[^A-Z0-9]", "", str(p["section"]).upper()):   # SOP-PM-2-9 · SOP-PR7-7
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
                for why in _b_step_findings(want[i], text):
                    found.append({"sop": sop, "order": s.get("order"), "kind": why, "source": want[i]})
    return found


def _b_preview_summary(preview: dict) -> dict:
    """AI 3회 비교에 쓰는 추출 항목 요약(절차 · 고장 유형 · 원인 · 조치 · 규칙 id/개수)."""
    k = preview.get("knowledge") or {}
    rules = k.get("rules") or []
    cand = sorted({o for x in rules if x.get("table") == "dt:action-candidates" and x.get("effect") == "SELECT" for o in x.get("outputs") or []})
    links = {p["id"]: (preview.get("links") or {}).get(p["id"], p.get("link") or {}) for p in preview.get("procedures") or []}
    return {
        "procedures": sorted(links),
        "steps": {p["id"]: len(p.get("steps") or []) for p in preview.get("procedures") or []},
        "failure_modes": sorted(x.get("id") for x in k.get("failure_modes") or []),
        "causes": sorted(x.get("id") for x in k.get("causes") or []),
        "evidence": len(k.get("evidence") or []),
        "rules": sorted(x.get("id") for x in rules),
        "rule_count": len(rules),
        "candidate_outputs": cand,
        "links_fm": {s: (l or {}).get("failureMode") for s, l in sorted(links.items())},
        "warnings": len(preview.get("warnings") or []),
        "issue_codes": sorted({i.get("code") for i in ((preview.get("validation") or {}).get("issues") or [])}),
        "technical_ready": (preview.get("validation") or {}).get("technical_ready"),
        "coverage": (preview.get("coverage") or {}).get("ratio"),
    }


def _b_source_id_on_screen(r) -> str | None:
    """미리보기의 「보관한 원본 내려받기」 링크에서 원문 판본 id 를 읽는다(hitl.js renderPreview). 코드 확인."""
    from urllib.parse import unquote
    href = r.page.locator("#manualResult a[href*='/original']").first.get_attribute("href") or ""
    m = re.search(r"/sources/([^/]+)/original", href)
    return unquote(m.group(1)) if m else None


def _b_extraction(r, sid: str, inst: str) -> tuple[int, dict]:
    from urllib.parse import quote
    return r.api("GET", f"{r.process}/api/kg/manuals/sources/{quote(sid, safe='')}/extractions/{quote(inst, safe='')}", timeout=60)


def _b_preview_file(r, key: str) -> str | None:
    """지식 관리 → 파일 선택 → (이미 적재된 같은 문서면 「문서 개정」) → 미리보기. 원문 판본 id 를 돌려준다."""
    page = r.page
    r.tab("knowledge")
    page.set_input_files("#manualFile", str(_B_DOC_DIR / _B_DOC_FILES[key]))                     # 라이브 확인
    # 두 번째 실행 PC: 같은 파일이 이미 적재돼 있으면 새 문서가 아니라 그 문서의 개정으로 올린다(hitl.js updateManualDocuments ·
    # c3_ingest.loaded_document 와 같은 계약). 새 문서로 올리면 적재가 SOP 소유권 충돌(409)로 거절된다.
    opts = page.locator("#manualDocumentId option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])")
    rev = [v for v, t in opts if v and _B_DOC_FILES[key] in t and "문서 개정" in t]
    if rev:
        page.select_option("#manualDocumentId", rev[0])
    page.click("#manualPreview")
    page.wait_for_selector("#manualResult .mprev, #manualResult .neg", timeout=60_000)
    if page.locator("#manualResult .neg").count():
        return None
    return _b_source_id_on_screen(r)


def _b_run_extraction(r, key: str, sid: str, i: int) -> dict:
    """[에이전트 추출 요청] → (진행 중에 [추출 진행 · 결과 확인]을 눌러 본다) → 끝나면 결과를 화면에 연다. AI 1회분 요약을 돌려준다."""
    page = r.page
    t0 = time.monotonic()
    page.click("#manualAgentExtract")                                                          # 코드 확인 (미리보기 뒤에 그려짐)
    r.wait(30, lambda: "접수" in page.locator("#manualAgentStatus").inner_text() or "실패" in page.locator("#manualAgentStatus").inner_text(), every=1)
    accepted = page.locator("#manualAgentStatus").inner_text()
    inst = page.input_value("#manualExtractionRuns")                                          # 방금 접수한 작업이 선택된다(sessionStorage)
    progress_texts = []

    def done():
        code, body = _b_extraction(r, sid, inst)
        if code == 200 and (body.get("preview") or body.get("status") in ("FAILED", "CANCELLED")):
            return body
        try:                                                                                   # 학생처럼 중간에 한 번씩 눌러 본다
            page.click("#manualAgentResult")
            page.wait_for_timeout(800)
            progress_texts.append(page.locator("#manualAgentStatus").inner_text())
        except Exception:
            pass
        return None

    # 끝날 때까지 기다린다(워커 실행 한도 1800초). 소요 시간 판정은 repeat3 의 limit_s(_B_EXTRACT_LIMIT_S)가 한다 —
    # 여기서 먼저 끊으면 다음 추출이 아직 도는 앞 추출 뒤에 줄을 서서 시간이 부풀었다(1차 실행)
    body = r.wait(1800, done, every=15) or {}
    seconds = round(time.monotonic() - t0, 1)
    if not body.get("preview"):
        return {"seconds": seconds, "instance": inst, "error": f"추출이 끝나지 않음: 상태 {body.get('status')} · {str(body.get('log') or '')[:200]}",
                "accepted": accepted, "progress": progress_texts[-1:] if progress_texts else []}
    page.click("#manualAgentResult")                                                           # 끝난 결과를 화면에 연다
    r.wait(30, lambda: "에이전트 제안" in page.locator("#manualAgentStatus").inner_text(), every=1)
    src = _b_source_procedures((_B_DOC_DIR / _B_DOC_FILES[key]).read_text(encoding="utf-8"))
    out = {"seconds": seconds, "instance": inst, "accepted": accepted, "progress": progress_texts[:1],
           "corrections": (body.get("corrections") or {}).get("attempts") or 0,
           "correction_reasons": len((body.get("corrections") or {}).get("reasons") or []),
           **_b_preview_summary(body["preview"]),
           "quality": [f"{f['sop']}#{f['order'] or '-'} {f['kind']}" for f in _b_quality(src, body["preview"])]}
    r.memo.setdefault("b_extractions", {}).setdefault(key, []).append(out)
    return out


def _b_review_exceptions(r, key: str):
    """적재 전 예외 경로(화면): 검토 표시 없이 적재 · 고장 유형 비우기 · 빈 단계 · 참고 절차 사용 방식 미선택. 모두 원래 값으로 되돌린다."""
    page = r.page
    msg = lambda: page.locator("#manualMsg").inner_text().strip()                            # noqa: E731
    page.uncheck("#manualReviewed")
    page.click("#manualCommit")
    r.check("검토 표시 없이 적재를 누르면 막고 할 일을 말한다", "검토 완료" in msg(), msg(), kind="exception")
    fms = page.locator("select[data-fm]:not([disabled])")
    if fms.count():
        sel = fms.first
        sop, keep = sel.get_attribute("data-fm"), sel.input_value()
        sel.select_option("")
        page.check("#manualReviewed")
        page.click("#manualCommit")
        r.check("고장 유형을 비우고 적재 → 「고장 유형을 고르세요」로 막음", "고장 유형을 고르세요" in msg() and sop in msg(), msg(), kind="exception")
        sel.select_option(keep)
    steps = page.locator("textarea[data-manual-step]")
    if steps.count():
        ta = steps.first
        keep = ta.input_value()
        ta.fill("")
        r.check("단계를 고치면 검토 표시가 풀리고 다시 검토하라는 문구가 보인다",
                not page.is_checked("#manualReviewed") and page.locator("#manualReviewChanged").is_visible(), "", kind="quality")
        page.check("#manualReviewed")
        page.click("#manualCommit")
        r.wait(30, lambda: msg().startswith("실패") or msg().startswith("적재 완료"), every=1)
        ok, why = r.human_message(msg())
        r.check("빈 단계로 적재 → 서버가 거절하고 한국어로 사유를 말한다", msg().startswith("실패") and "빈 단계" in msg() and ok, why, kind="exception")
        ta.fill(keep)
    kinds = page.locator("select[data-kind]")
    if kinds.count():
        k = kinds.first
        keep = k.input_value()
        k.select_option("reference")
        page.check("#manualReviewed")
        page.click("#manualCommit")
        r.check("참고 절차로 바꾸고 사용 방식을 안 고르면 막는다", "참고 보관" in msg(), msg(), kind="exception")
        k.select_option(keep)
    page.uncheck("#manualReviewed")


def _b_apply_review(r, key: str, preview_body: dict) -> list[str]:
    """학생의 원문 대조 검토를 화면에서 한다: 원문과 다른 단계는 원문 문장으로 고치고(수정), 원문 SOP 목록에 없는 절차는
    「일반 원문 참고 절차 · 실행 후보 제외」로 돌리고(제외), 비어 있는 필수 선택은 원문이 정한 값으로 고른다. 한 일을 돌려준다."""
    page = r.page
    text = (_B_DOC_DIR / _B_DOC_FILES[key]).read_text(encoding="utf-8")
    src = _b_source_procedures(text)
    phrases = _b_source_failure_phrases(text)
    done = []
    for f in _b_quality(src, preview_body):
        if f.get("order") and f.get("source"):
            ta = page.locator(f"textarea[data-manual-step='{f['sop']}'][data-order='{f['order']}']")
            if ta.count():
                ta.fill(f["source"])                                                           # 원문 문장 그대로(번역 · 요약 금지 — 추출 지시와 같은 규칙)
                done.append(f"수정 {f['sop']}#{f['order']}: {f['kind']}")
        elif f["kind"].startswith("원문 SOP 목록에 없는"):
            kind = page.locator(f"select[data-kind='{f['sop']}']")
            if kind.count():
                kind.select_option("reference")
                page.select_option(f"select[data-reference-executable='{f['sop']}']", "false")
                done.append(f"제외 {f['sop']}: 참고 보관 · 실행 후보 제외")
    for sel in page.locator("select[data-fm]:not([disabled])").all():
        sop = sel.get_attribute("data-fm")
        scope = page.locator(f"select[data-manual-scope='{sop}']")
        if scope.count() and scope.input_value() == "purchase":
            continue
        cur = sel.input_value()
        opts = sel.locator("option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])")
        # 대상 설비 대조: 원문이 정의한 고장 유형 이름과 낱말 두 개 이상 겹치는 선택지(원문 HM-8.4 · PM-2.10)
        def overlap(label):
            return max((len(set(p.split()) & set(label.replace("(", " ").split())) for p in phrases), default=0)
        good = [v for v, t in opts if v and overlap(t) >= 2]
        if not cur and good:
            sel.select_option(good[0])
            done.append(f"고장 유형 선택 {sop}: 원문 고장 유형과 맞는 {good[0]}")
        elif cur and good and cur not in good:
            r.check(f"{key} {sop} 대상 설비 — AI 연결 고장 유형이 원문 고장 유형과 다름", False, f"AI {cur} · 원문 {phrases}", kind="quality")
            sel.select_option(good[0])
            done.append(f"고장 유형 교정 {sop}: {cur} → {good[0]}")
    for sel in page.locator("select[data-manual-executable]").all():
        sop = sel.get_attribute("data-manual-executable")
        if page.locator(f"[data-purchase-fields='{sop}']").is_hidden():
            continue
        if not sel.input_value():
            r.check(f"{key} {sop} AI가 구매 절차 사용 방식을 비움 — 학생이 원문으로 골라야 함", False, "", kind="quality")
            steps = " ".join((src.get(sop) or {}).get("steps") or [])
            sel.select_option("true" if "발주서" in steps else "false")                       # 원문 단계에 실행 행위(ERP 발주서 작성)가 있으면 실행 후보
            done.append(f"사용 방식 {sop}: 원문 단계로 판단")
        appr = page.locator(f"select[data-manual-approver='{sop}']")
        want = (src.get(sop) or {}).get("approver")
        if appr.count() and not appr.input_value() and want and sel.input_value() == "true":
            opt = [v for v, t in appr.locator("option").evaluate_all("ns => ns.map(n => [n.value, n.textContent])") if v and t.strip() == want]
            if opt:
                appr.select_option(opt[0])
                done.append(f"승인 역할 {sop}: 원문 「승인: {want}」")
        parts = page.locator(f"select[data-manual-parts='{sop}']")
        if parts.count() and not parts.evaluate("s => s.selectedOptions.length"):
            r.check(f"{key} {sop} AI가 구매 대상 부품을 비움 — 화면에서 골라야 적재된다", False, "원문 PR-7.1 표를 보고 학생이 고르는 칸", kind="quality")
    return done


def _b_commit(r, key: str) -> tuple[bool, str]:
    page = r.page
    page.check("#manualReviewed")
    page.click("#manualCommit")
    r.wait(90, lambda: page.locator('.confirm-dialog[open]').count() or
           page.locator("#manualMsg").inner_text().startswith(("적재 완료", "실패")), every=1)
    dialog=page.locator('.confirm-dialog[open]')
    if dialog.count():
        text=dialog.inner_text()
        # The round re-extracts the same teaching source. Losing existing
        # operational knowledge is a quality failure, not something to approve
        # just to keep later exercises running.
        lost=any(label in text for label in ('조치 방법:', '고장 유형:', '원인:', '진단 근거:', '판단 규칙:', '절차 단계:'))
        r.check(f'{key} 개정 삭제 목록을 확인했다 — 기존 업무 지식 누락 없음', not lost, text, kind='quality')
        dialog.locator('button[value="cancel"]' if lost else 'button[value="ok"]').click()
        if lost:
            return False, '개정 누락을 확인해 적재하지 않음: ' + text
    r.wait(90, lambda: page.locator("#manualMsg").inner_text().startswith(("적재 완료", "실패")), every=1)
    msg = page.locator("#manualMsg").inner_text().strip()
    return msg.startswith("적재 완료"), msg


def _b_current_batch(r, key: str) -> dict | None:
    rows = r.get(f"{r.process}/api/kg/manuals")
    cur = [u for u in rows if u.get("current") and u.get("filename") == _B_DOC_FILES[key]]
    return cur[0] if cur else None


def _b_onto_stats(r) -> str:
    r.tab("ontology")
    r.page.click("#ontoReload")                                                                # 라이브 확인
    r.wait(20, lambda: "항목" in r.page.locator("#ontoStats").inner_text(), every=1)
    return r.page.locator("#ontoStats").inner_text()


def _b_skill_count(stats: str) -> int:
    m = re.search(r"조치 방법 (\d+)", stats)
    return int(m.group(1)) if m else -1


# ---------------------------------------------------------------------- 05
@lab("05", "4회차 매뉴얼 원문과 등록된 지식의 조건 · 출처 대조 (기본 잠금: 제공 문서 보기 · 대조, 추출 · 적재는 교대 실습에서)")
def lab_05_manual_to_knowledge(r: Round):
    """최신 실라버스(통합 18행 · 실전 59행): 새로 추출하지 않고 제공 원문과 시작 때 적재된 검토 지식을 대조한다.
    기본 잠금은 추출 · 임의 적재 · 되돌리기를 막는다(course_access.gate). 막힘도 학생이 읽을 한국어여야 한다."""
    page = r.page
    before = _b_onto_stats(r)
    r.memo["b_skills_before"] = _b_skill_count(before)
    r.check("지식 지도(시작 때 적재한 기본 지식) 읽힘", _b_skill_count(before) > 0, before)
    loaded = {k: _b_current_batch(r, k) for k in ("HM-8", "PM-02", "PR-07")}
    r.memo["b_loaded"] = {k: bool(v) for k, v in loaded.items()}
    r.check("세 제공 문서가 현재 판본으로 적재돼 있다(시작 스크립트 7/8)", all(loaded.values()),
            json.dumps({k: (v or {}).get("batch") for k, v in loaded.items()}, ensure_ascii=False))

    # ---- 예외: 파일 없음 · 잘못된 파일 · 제공하지 않은 문서는 거절되고 보관 원문에 남지 않는다
    r.tab("knowledge")
    total0 = r.get(f"{r.process}/api/kg/manuals/sources?limit=1")["total"]
    page.click("#manualPreview")
    r.check("파일 없이 미리보기 → 「파일을 먼저 선택해 주세요」", "파일을 먼저 선택" in page.locator("#manualResult").inner_text(),
            page.locator("#manualResult").inner_text(), kind="exception")
    bad_files = [("빈 파일", {"name": "empty.md", "mimeType": "text/markdown", "buffer": b""}),
                 ("제공하지 않은 문서", {"name": "my-notes.md", "mimeType": "text/markdown", "buffer": "# 내 메모\n\n1. 팬을 끈다".encode()}),
                 ("PDF 이름의 텍스트", {"name": "fake.pdf", "mimeType": "application/pdf", "buffer": "가짜 PDF".encode()})]
    for label, f in bad_files:
        page.set_input_files("#manualFile", f)
        page.click("#manualPreview")
        page.wait_for_selector("#manualResult .neg, #manualResult .mprev", timeout=30_000)
        text = page.locator("#manualResult").inner_text()
        ok, why = r.human_message(text)
        r.check(f"잘못된 파일 거절 — {label}", "미리보기 실패" in text and ok, why, kind="exception")
    r.check("거절된 파일은 보관 원문에 남지 않는다", r.get(f"{r.process}/api/kg/manuals/sources?limit=1")["total"] == total0, kind="exception")

    # ---- HM-8 제공 원문 열기 → 원문 전체 보기 → 등록된 검토 지식과 대조
    sid = _b_preview_file(r, "HM-8")
    head = page.locator("#manualResult .mprev .muted").first.inner_text() if sid else page.locator("#manualResult").inner_text()
    r.check("HM-8 제공 원문 미리보기(파일 · 글자 수 · 절 · 절차)", bool(sid) and "HM-8_cooler-fan-manual.md" in head and "절 " in head, head)
    if not sid:
        return
    r.memo["b_sid_HM-8"] = sid
    page.click("#manualFullSource")
    r.wait(15, lambda: page.locator("#manualSourceText details").count() > 0, every=1)
    r.check("원문 전체 보기(보관 원문 쪽별)", page.locator("#manualSourceText details").count() >= 1)
    extract = page.locator("#manualAgentExtract")
    r.check("기본 잠금: [추출 제안 준비]는 꺼져 있고 강사 코드가 필요하다고 알린다",
            extract.count() > 0 and extract.is_disabled() and "강사" in (extract.get_attribute("title") or ""),
            extract.get_attribute("title") or "버튼 없음", kind="exception")
    code, body = r.api("POST", f"{r.process}/api/kg/manuals/sources/{urllib.parse.quote(sid, safe='')}/extractions",
                       {"request_id": "00000000-0000-4000-8000-000000000005"})
    detail = (body or {}).get("detail", "") if isinstance(body, dict) else str(body)
    ok, why = r.human_message(detail)
    r.check("화면 밖 추출 요청도 서버가 거절(403 · 한국어, AI 호출 없음)", code == 403 and ok and "강사" in detail, f"{code} {why}", kind="exception")
    r.check("거절된 추출은 처리 건을 만들지 않는다", not (r.get(f"{r.process}/api/kg/manuals/sources/{urllib.parse.quote(sid, safe='')}/extractions?limit=5")
                                                 or {}).get("items"), kind="exception")
    pv = r.get(f"{r.process}/api/kg/manuals/sources/{urllib.parse.quote(sid, safe='')}/preview")
    src = _b_source_procedures((_B_DOC_DIR / _B_DOC_FILES["HM-8"]).read_text(encoding="utf-8"))
    got = {p["id"] for p in pv.get("procedures") or []}
    r.check("원문 대조: 원문의 절차 번호가 미리보기에 모두 있다", set(src) <= got, f"원문 {sorted(src)} · 미리보기 {sorted(got)}", kind="quality")
    hist = page.locator("#manualHistory").inner_text()
    r.check("적재 이력 카드에 HM-8 현재 판본(시작 때 검토본)이 보인다", "HM-8" in hist, hist[:300])
    undo = page.locator("#manualHistory [data-manual-undo]")
    if undo.count():
        undo.first.click(); page.wait_for_timeout(1500)
        r.check("기본 잠금: 기본 지식 되돌리기는 막히고 판본이 그대로", (_b_current_batch(r, "HM-8") or {}).get("batch") == loaded["HM-8"]["batch"],
                page.locator("#manualHistory").inner_text()[:300], kind="exception")

    # ---- 지식 지도: 조치 → 단계 → 근거 매뉴얼 절 → 속한 문서(출처)
    r.tab("ontology")
    page.click("#ontoReload")
    r.wait(20, lambda: page.locator("#ontoMap .o-node").count() > 0, every=1)
    page.fill("#ontoSearch", "팬 최대 운전")
    node = page.locator("#ontoMap .o-node[aria-label*='조치 방법'][aria-label*='팬 최대 운전']").first
    trail = []
    if node.count():
        node.click()
        for rel in ("절차 단계", "근거 매뉴얼", "속한 문서"):
            link = page.locator("#ontoNode li", has_text=rel).locator("a[data-go]").first
            if not link.count():
                break
            trail.append(link.inner_text())
            link.click()
            page.wait_for_timeout(400)
    r.check("지식 지도: 팬 최대 운전 → 단계 → 근거 절 → HM-8 문서(출처)", len(trail) == 3 and "HM-8" in trail[-1], " → ".join(trail))

    # ---- 데이터 연결: 정적 기준(지식) vs 업무 DB · 시계열 DB 현재값
    r.tab("fabric")
    r.wait(15, lambda: page.locator("#fabRun").count(), every=1)
    page.select_option("#fabQuery", label="고온 구간 로트와 실제 유온 기록")
    page.click("#fabRun")
    r.wait(30, lambda: "읽는 중" not in page.locator("#fabRun").inner_text() and page.locator("#fabResult .card").count(), every=1)
    res = page.locator("#fabResult").inner_text()
    r.check("데이터 연결: 업무 DB · 시계열 DB 값이 출처(표 · 열)와 함께", "업무 DB" in res and "시계열 DB" in res and "조회 실패" not in res, res[:500])
    r.check("데이터 연결: 기준(지식 그래프 임계값)과 현재값을 구별해 보인다", "기준" in res, res[:500], kind="quality")


# ---------------------------------------------------------------------- 06
def _b_agents(r) -> list[dict]:
    return r.get(f"{r.process}/api/agents")


def _b_agent_form(r, *, name=None, role=None, goal=None, persona=None, model=None, tools=None) -> str:
    """열린 에이전트 폼 칸을 채우고 저장한다. 폼 오류 문구(없으면 '')를 돌려준다(agents.js formHtml · submitForm). 코드 확인."""
    page = r.page
    form = page.locator("[data-ag-form]")
    form.wait_for(timeout=10_000)
    for key, val in (("name", name), ("role", role), ("goal", goal), ("persona", persona), ("model", model)):
        if val is not None:
            form.locator(f"[data-f='{key}']").fill(val)
    if tools is not None:
        for box in form.locator("input[data-f-tool]").all():
            want = box.get_attribute("value") in tools
            if box.is_checked() != want:
                box.click()
    _b_clear_toasts(r)
    # 앞 저장의 오류 문구가 남아 있으면 그것을 이번 결과로 읽는다 — 지우고 새 결과를 기다린다
    page.evaluate("() => document.querySelectorAll('[data-ag-detail] .form-msg.neg').forEach(n => { n.textContent = ''; n.classList.remove('neg'); })")
    form.locator("button[type=submit]").click()
    r.wait(15, lambda: page.locator("[data-ag-form]").count() == 0 or page.locator("[data-ag-detail] .form-msg.neg").count(), every=0.5)
    err = page.locator("[data-ag-detail] .form-msg.neg")
    return err.first.inner_text().strip() if err.count() else ""


def _b_open_agent_edit(r, agent_id: str):
    r.tab("agents")
    r.page.locator(f"[data-pick-agent='{agent_id}']").first.click()
    r.page.locator("[data-edit-agent]").first.click()


def _b_ask(r, agent_id: str, question: str) -> dict:
    """에이전트에게 질문: 답할 에이전트 고르기 → 질문 → 보내기 → 끝날 때까지 → 화면의 답 · 근거 · 호출 기록 + 서버 판정."""
    page = r.page
    r.tab("ask")
    r.wait(15, lambda: page.locator(f"#askAgent option[value='{agent_id}']").count(), every=1)
    page.select_option("#askAgent", agent_id)                                                   # 라이브 확인
    page.fill("#askText", question)
    seen = set(page.locator(".ask-a a[href^='#/instances/']").evaluate_all("as => as.map(a => a.getAttribute('href'))"))
    t0 = time.monotonic()
    page.click("#askSend")
    # 앞 질문의 답 링크가 화면에 남아 있다 — 이번에 새로 생긴 링크를 기다린다(1차: 첫 링크를 읽어 앞 질문의 답을 이번 답으로 판정)
    href = r.wait(60, lambda: next((h for h in page.locator(".ask-a a[href^='#/instances/']").evaluate_all("as => as.map(a => a.getAttribute('href'))")
                                    if h not in seen), None), every=0.5) or ""
    pid = href.split("/")[2] if href.count("/") >= 2 else ""
    view = r.wait(_B_ASK_LIMIT_S + 60, lambda: (lambda v: v if v.get("state") not in _B_ASK_LIVE else None)(r.get(f"{r.process}/api/ask/{pid}")), every=3) or {}
    seconds = round(time.monotonic() - t0, 1)
    page.wait_for_timeout(2500)                                                                 # 화면 폴링(1.5초)이 끝난 상태를 그릴 시간
    res = view.get("result") or {}
    calls = view.get("tool_calls") or []
    answer = res.get("answer") or res.get("claimed") or ""
    return {"seconds": seconds, "id": pid, "state": view.get("state"), "message": view.get("message"),
            "kind": res.get("kind"), "by": res.get("by"), "verified": res.get("verified") or 0,
            "verified_ok": bool(res.get("verified")),
            "sop_ids": sorted(set(re.findall(r"SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*", answer))),
            "tools": sorted({str(c.get("raw_tool") or c.get("tool")) for c in calls if c.get("ok") and c.get("data")}),
            "calls": len(calls), "answer": answer[:400], "reason": res.get("reason"),
            "screen": page.locator(f".ask-a:has(a[href='{href}'])").first.inner_text()[-1500:] if href and page.locator(f".ask-a:has(a[href='{href}'])").count() else ""}


def _b_check_model_override(r: Round, agent_id: str, course: bool):
    """Check model policy without issuing a question when a course denies the edit."""
    # 수업에서는 모델 변경을 저장 전에 막고, 다른 일반 운영 모드는 기존 실행 시 검사를 유지한다.
    _b_open_agent_edit(r, agent_id)
    err = _b_agent_form(r, model="gpt-9-ultra")
    if course:
        ok, why = r.human_message(err)
        current = next(a for a in _b_agents(r) if a["id"] == agent_id)
        r.check("허용하지 않은 모델은 저장 전에 차단되고 원래 설정을 유지한다",
                "기본 모델" in err and ok and current.get("model") in (None, "", "coding"), why, kind="exception")
        err = _b_agent_form(r, model="")
    else:
        warn = _b_toast_text(r, 3)
        r.check("모양이 맞는 모델 이름은 저장된다(중계 목록은 실행 때 확인)", not err, f"저장 결과 '{err}' · 토스트 '{warn}'", kind="quality")
        bad = _b_ask(r, agent_id, "HYD-01 유온 최근 값은?")
        ok, why = r.human_message(bad.get("message") or bad.get("reason") or "")
        r.check("엉뚱한 모델로 실행 → 무한 대기 없이 실패 · 사람 글로 무엇을 고칠지(모델 칸)", bad.get("state") in ("failed", "done") and bad.get("seconds", 999) <= _B_ASK_LIMIT_S and ok
                and (bad.get("state") != "failed" or "모델 칸" in (bad.get("message") or "")),
                f"{bad.get('state')} · {why}", kind="exception", seconds=bad.get("seconds"))
        _b_open_agent_edit(r, agent_id)
        err = _b_agent_form(r, model="")
    r.check("모델 칸을 비워 되돌림(실행기 기본 모델)", not err and not next(a for a in _b_agents(r) if a["id"] == agent_id).get("model"), err, kind="exception")


@lab("06", "5-1 · 4-1 나의 첫 에이전트 (에이전트 · 에이전트에게 질문)")
def lab_06_first_agent(r: Round):
    page = r.page
    r.tab("agents")
    r.wait(15, lambda: page.locator("[data-new-agent]").count(), every=1)                       # 라이브 확인
    # 이미 확인한 것(인계 4절): 만들기 · 복제 · 빈 폼 — 학생 동선이라 짧게만
    page.click("[data-new-agent]")
    err = _b_agent_form(r)
    r.check("빈 폼 저장 → 「이름 칸을 채워야 합니다」", "이름" in err and "채워야" in err, err, kind="exception")
    err = _b_agent_form(r, name="모델 실험", goal="모델 칸 시험", model="모델 이름!")
    code, access = r.api("GET", f"{r.process}/api/course-access")
    course = code == 200 and isinstance(access, dict) and access.get("capabilities", {}).get("model_settings") is False
    expected = "기본 모델" if course else "모델 이름 모양"
    r.check("허용하지 않은 모델 → 저장 거절 · 사람 글", expected in err and r.human_message(err)[0], err, kind="exception")
    err = _b_agent_form(r, name="냉각 긴급 대응 에이전트", goal="기본 에이전트와 같은 이름", model="")
    r.check("기본 에이전트와 같은 이름 → 거절", "같은 이름" in err, err, kind="exception")

    mine = next((a for a in _b_agents(r) if a.get("name") == _B_AGENT_NAME and a.get("origin") == "user"), None)
    profile = dict(name=_B_AGENT_NAME, role="쿨러 열화 경보를 먼저 보는 점검 담당",
                   goal="쿨러 과열 경보 한 건에 대해 지식 그래프의 원인 · 조치 절차와 센서 기록을 찾아 정리하고, HM-8 매뉴얼 규칙을 지키는 조치 후보 3개를 "
                        "순위와 함께 제안한다. 승인 전에는 조회 · 계산 · 요약만 한다.",
                   persona="근거(조회한 도구와 값)를 먼저 말한다. 조회해서 나오지 않으면 지어내지 않고 모른다고 한다.",
                   model="", tools=["neo4j", "hyd-dmn"])
    if mine:                                                                                    # 두 번째 실행 PC: 같은 이름이 이미 있다 → 중복 거절을 먼저 본다
        err = _b_agent_form(r, **profile)
        r.check("같은 이름 중복 → 거절(두 번째 실행 PC)", "같은 이름" in err, err, kind="exception")
        page.locator("[data-f-cancel]").first.click()
    else:
        err = _b_agent_form(r, **profile)
        r.check("나의 에이전트 저장(이름 · 역할 · 목표 · 성격 · 도구)", not err, err)
        mine = next((a for a in _b_agents(r) if a.get("name") == _B_AGENT_NAME and a.get("origin") == "user"), None)
        page.click("[data-new-agent]")
        err = _b_agent_form(r, **profile)
        r.check("같은 이름으로 한 번 더 → 거절", "같은 이름" in err, err, kind="exception")
        page.locator("[data-f-cancel]").first.click()
    if not mine:
        r.check("나의 에이전트가 목록에 있다", False)
        return
    r.memo["my_agent"] = mine["id"]
    page.locator(f"[data-pick-agent='{mine['id']}']").first.click()
    r.wait(15, lambda: "불러오는 중" not in page.locator("[data-ag-detail]").inner_text(), every=0.5)
    detail = page.locator("[data-ag-detail]").inner_text()
    r.check("상세: 「내가 만든」 · 목표 · 쓰는 도구가 보인다", "내가 만든" in detail and "목표" in detail and "쓰는 도구" in detail, detail[:300])

    # ---- 질문 → 근거 · 호출 기록 (AI 3회: 같은 질문 · 같은 에이전트)
    q = "HM-8 매뉴얼에서 쿨러 냉각 성능 상실의 즉시 완화 조치 절차 번호를 모두 알려 주고, 각 절차의 승인 역할도 알려 줘."
    runs = r.repeat3("나의 에이전트 질문", lambda i: _b_ask(r, mine["id"], q), ("kind", "sop_ids", "verified_ok"), limit_s=_B_ASK_LIMIT_S)
    # 도구 경로(스키마를 한 번 더 보는 등)는 학생의 다음 단계가 아니다 — 같은 답 · 근거면 같다. 차이는 기록만(final2: 셋 중 하나가 시계열 스키마 1회 추가)
    print("    나의 에이전트 질문 도구 경로: " + " | ".join(json.dumps(x.get("tools"), ensure_ascii=False) for x in runs), flush=True)
    last = runs[-1]
    r.check("답 + 근거가 서버 대조(실행 기록)를 통과", last.get("kind") == "answered" and last.get("verified_ok"),
            f"{last.get('kind')} · 근거 {last.get('verified')} · {last.get('reason') or ''}")
    loaded = (r.memo.get("b_loaded") or {}).get("HM-8")
    if loaded:
        src = _b_source_procedures((_B_DOC_DIR / _B_DOC_FILES["HM-8"]).read_text(encoding="utf-8"))
        want = sorted(s for s in src if s.startswith("SOP-COOL-1") and int(s[-1]) <= 3)          # 원문 HM-8.5 절의 SOP(즉시 완화)
        r.check("답의 절차 번호가 원문 HM-8.5(즉시 완화)와 같다", last.get("sop_ids") == want, f"답 {last.get('sop_ids')} · 원문 {want}", kind="quality")
    page.locator(".ask-process summary").first.click()
    proc = page.locator(".ask-process").first.inner_text()
    r.check("처리 과정 · 도구 호출 기록이 화면에 보인다", "도구 호출" in proc and last.get("calls", 0) > 0, proc[:300])
    r.check("근거 접기에 실행한 질의 · 결과가 보인다", page.locator(".ask-a").get_by_text(re.compile("근거 — 실행한 질의")).count() > 0, kind="normal")

    if r.ai_runs < 3:
        # 연속 확인: 이미 실제 Luna 로 검증한 같은 질문은 다시 만들지 않는다(6_남은_일.md 「새 로컬 학생 질문의 정보 없음 실제 검증」)
        r.not_measured.append(dict(lab=r.lab, name="기준 에이전트 비교 · 지식에 없는 질문(고객센터 전화번호)",
                                   why="--ai-runs 1: 같은 질문의 기존 실제 실행 증거(course-model-unknown-question-live)를 재사용, 재생성하지 않음"))
        _b_check_model_override(r, mine["id"], course)
        return

    # ---- 기준 에이전트와 비교(같은 질문을 기본 에이전트에게)
    base = _b_ask(r, "sys:agent", q)
    r.check("기준 에이전트도 같은 질문에 근거 있는 답", base.get("kind") == "answered" and base.get("verified_ok"), base.get("reason") or "")
    r.check("나의 에이전트 vs 기준 에이전트 — 같은 절차 번호", base.get("sop_ids") == last.get("sop_ids"),
            f"나 {last.get('sop_ids')} {last.get('tools')} · 기준 {base.get('sop_ids')} {base.get('tools')}", kind="quality")

    # ---- 근거 없는 질문: 지어내지 않고 모른다고
    unk = _b_ask(r, mine["id"], "HYD-01 쿨러 팬 모터 제조사의 고객센터 전화번호는 무엇인가?")
    r.check("지식에 없는 질문 → 「답할 수 없음」(지어내지 않음)", unk.get("kind") == "unanswerable", f"{unk.get('kind')} · {unk.get('answer')[:200]}", kind="exception")
    if unk.get("reason"):
        ok, why = r.human_message(unk["reason"])
        r.check("답할 수 없음 이유가 사람 글", ok, why, kind="exception")
    r.check("답할 수 없음 카드가 화면에 보인다", "답할 수 없음" in unk.get("screen", ""), unk.get("screen", "")[-200:], kind="exception")

    _b_check_model_override(r, mine["id"], course)
    r.check("질문 화면 에이전트 도구 칩이 사람 이름으로 보인다",
            "도구 표시 이름" not in (r.tab("ask") or page.locator("[data-ask-form]").inner_text()),
            page.locator("[data-ask-form]").inner_text()[:300], kind="quality")       # ask.js:91 UI.toolName(서버 이름) — 라이브에서 「확인 중」 3개


# ---------------------------------------------------------------------- 07
def _b_free_port(start: int = 8311) -> int:
    import socket
    for port in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError("학생 MCP 서버에 쓸 빈 포트가 없습니다")


def _b_student_schema(r) -> str:
    """T3(VS Code 랩)에서 학생이 한 일의 대역: students/_template/table.sql 을 s01 · 새 암호로 실행한다. 상태를 바꾼다(DB 쓰기) —
    메인이 한 바퀴를 돌릴 때만. 지우기: drop schema stu_s01 cascade; drop role stu_s01_reader;"""
    import secrets
    import psycopg
    pw = "stu-" + secrets.token_hex(8)
    sql = (ROOT / "students/_template/table.sql").read_text(encoding="utf-8").replace("s00", _B_STUDENT).replace("change-me", pw)
    db_port = host_ports().get(54322, 54322)
    with psycopg.connect(f"postgresql://postgres:postgres@127.0.0.1:{db_port}/postgres", autocommit=True, connect_timeout=5) as c:
        c.execute(sql)
        c.execute(f"alter role stu_{_B_STUDENT}_reader password '{pw}'")                       # 두 번째 실행: 역할이 이미 있으면 암호만 바꾼다
    return f"postgresql://stu_{_B_STUDENT}_reader:{pw}@127.0.0.1:{db_port}/postgres"


def _b_start_mcp(r, dsn: str, port: int):
    import os
    import subprocess
    env = dict(os.environ, STUDENT_DSN=dsn, STUDENT_SCHEMA=f"stu_{_B_STUDENT}", MCP_PORT=str(port), PYTHONUTF8="1")
    log = open(r.out / f"mcp_table_reader-{port}.log", "ab")
    proc = subprocess.Popen([sys.executable, str(ROOT / "students/_template/mcp_table_reader/server.py")],
                            env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
    ok = r.wait(30, lambda: r.api("GET", f"http://127.0.0.1:{port}/healthz", timeout=3)[1].get("ok"), every=1)
    return proc, bool(ok)


def _b_stop_mcp(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()


def _b_mcp_form(r, *, name: str, url: str, description: str = "", dry: bool = False, edit: bool = False) -> tuple[str, str]:
    """도구 연결 → 운영자 직접 등록 · 연결 설정 → 서버 직접 등록 폼. (폼 오류, 검사 결과 글)을 돌려준다(mcp.js renderForm · submitForm)."""
    page = r.page
    form = page.locator("#mcpForm .mcp-form")
    if not form.count():
        if not page.locator("#mcpOperator").evaluate("d => d.open"):
            page.locator("#mcpOperator > summary").click()                                     # 라이브 확인
        page.click("#mcpAdd")                                                                   # 라이브 확인
        form.wait_for(timeout=5000)
    if not edit:
        form.locator("[data-f='name']").fill(name)
    form.locator("[data-f='url']").fill(url)
    form.locator("[data-f='description']").fill(description)
    _b_clear_toasts(r)
    page.click("#mcpDry" if dry else "#mcpSave")
    r.wait(20, lambda: not page.locator("#mcpForm .mcp-form").count() or not page.locator("#mcpDry").is_disabled(), every=0.5)
    err = page.locator("#mcpForm .form-msg.neg")
    res = page.locator("#mcpFormResult")
    return (err.first.inner_text().strip() if err.count() else ""), (res.first.inner_text().strip() if res.count() else "")


def _b_mcp_select(r, name: str):
    r.tab("mcp")
    page = r.page
    r.wait(15, lambda: page.locator(f"#mcpServers [data-open='{name}']").count(), every=1)
    page.locator(f"#mcpServers [data-open='{name}']").first.click()                            # 「도구 보기」 — 라이브 확인(기준 서버)
    page.locator("#mcpDetail .mcp-detail").wait_for(timeout=10_000)


def _b_mcp_probe(r, name: str) -> str:
    _b_mcp_select(r, name)
    _b_clear_toasts(r)
    r.page.click("#mcpProbe")                                                                   # 「연결 검사」 — 코드 확인
    return _b_toast_text(r, 15)


def _b_mcp_try(r, tool: str, inputs: dict) -> str:
    page = r.page
    btn = page.locator(f"#mcpPane [data-try='{tool}']")
    if btn.inner_text().strip() != "닫기":
        btn.click()
    for k, v in inputs.items():
        page.fill(f"#mcpIn-{k}", v)
    page.click("#mcpCall")
    r.wait(20, lambda: "호출 중" not in page.locator("#mcpResult").inner_text(), every=0.5)
    return page.locator("#mcpResult").inner_text()


@lab("07", "6-1 · 4-4 도구(MCP) 연결 · 써 보기 · 에이전트에 연결")
def lab_07_mcp_tools(r: Round):
    page = r.page
    code, access = r.api("GET", f"{r.process}/api/course-access")
    if code == 200 and isinstance(access, dict) and access.get("capabilities", {}).get("tool_inspection") is True:
        # 학생 화면에서 준비된 조회 경로와 차단 경계를 검사한다. 아래 교재의
        # 개인 서버 등록은 현재 정책과 충돌하므로 성공으로 바꾸지 않는다.
        r.tab("mcp")
        r.wait(20, lambda: page.locator("#mcpServers [data-open='hyd-dmn']").count(), every=0.5)
        servers = r.get(f"{r.process}/api/mcp/servers").get("servers", [])
        names = {server["name"] for server in servers}
        r.check("준비된 조회 서버만 표시", names == {"neo4j", "enterprise", "hyd-dmn"}, str(sorted(names)))
        r.check("서버 관리 화면은 감춰짐", page.locator("#mcpOperator").is_hidden(), kind="exception")
        _b_mcp_select(r, "hyd-dmn")
        page.locator("#mcpPane [data-try='inputs']").wait_for(timeout=15_000)
        shown = page.locator("#mcpPane .mcp-tool").all()
        visible = {item.get_attribute("data-tool") for item in shown}
        r.check("승인된 읽기 목록만 표시", "inputs" in visible and "submit_decision" not in visible and "submit_purchase" not in visible, str(sorted(visible)))
        out = _b_mcp_try(r, "inputs", {})
        r.check("준비된 입력 자료의 실제 조회 결과가 보임", "in:cause" in out, out[:400])
        denied, body = r.api("POST", f"{r.process}/api/mcp/servers/hyd-dmn/tools/submit_decision/call", {"arguments": {}})
        r.check("판단 제출은 직접 API에서도 거절", denied == 403, str(body)[:300], kind="exception")
        registration, body = r.api("POST", f"{r.process}/api/mcp/servers", {"name": _B_MCP_NAME})
        r.check("임의 서버 등록은 현재 수업 정책에서 차단", registration == 403, str(body)[:300], kind="exception")
        # 최신 실라버스(통합 25 · 26행)는 포털에서 준비된 도구 기록만 보고, 개인 MCP 연결은 VS Code 랩에서 한다.
        # 6회차 대본의 포털 등록 문장과의 불일치는 교재 작업의 범위다 — 포털 성공도 실패도 아닌 미정합으로 남긴다.
        r.not_measured.append(dict(lab=r.lab, name="6회차 대본의 포털 개인 서버 등록 단계",
                                   why="최신 실라버스는 포털 등록을 요구하지 않음 · 대본 정합은 교재 작업(미해결)"))
        return
    # ---- 사전 준비 서버 상태(기준 서버는 보기만)
    r.tab("mcp")
    r.wait(20, lambda: page.locator("#mcpServers [data-name]").count() >= 5, every=1)
    page.wait_for_timeout(5000)                                                                 # 서버마다 연결 확인(최대 4초, mcp.js probe)
    cards = page.locator("#mcpServers").inner_text()
    r.check("사전 준비 서버 5개가 연결됨 · 워커에서 실행으로 보인다", cards.count("연결됨") >= 4 and "연결 실패" not in cards, cards[:400])
    _b_mcp_select(r, "enterprise")
    r.check("기준 서버는 고치기 · 지우기 버튼이 없다", page.locator("#mcpEdit, #mcpDelete").count() == 0, kind="exception")
    tools = page.locator("#mcpPane .mcp-tool").count()
    r.check("기준 서버 도구 목록(이름 · 입력 형식)이 보인다", tools > 0, f"도구 {tools}개")

    # ---- 학생 PC: 내 업무 표 + 내 서버 띄우기(README: STUDENT_DSN · STUDENT_SCHEMA · MCP_PORT python server.py)
    try:
        dsn = _b_student_schema(r)
    except Exception as e:
        r.check("T3 학생 업무 표(stu_s01) 준비", False, f"{type(e).__name__}: {e}")
        return
    port = _b_free_port()
    proc, up = _b_start_mcp(r, dsn, port)
    r.check(f"학생 MCP 서버가 내 PC에서 뜬다(포트 {port})", up, f"로그 {r.out}/mcp_table_reader-{port}.log")
    if not up:
        _b_stop_mcp(proc)
        return
    url = f"http://host.docker.internal:{port}/mcp"                                            # README · 폼 안내 문구와 같은 주소
    try:
        # 컨테이너 워커가 학생 PC 서버에 닿는 길: compose agent-worker · process 의 extra_hosts host-gateway (compose.yaml:345 · 405 · 573)
        import subprocess
        worker_id = subprocess.run(["docker", "compose", "ps", "-q", "agent-worker"], cwd=ROOT,
                                   capture_output=True, text=True, timeout=15, check=True).stdout.strip()
        if not worker_id:
            raise RuntimeError("현재 Compose 프로젝트의 agent-worker 컨테이너가 없습니다")
        hosts = subprocess.run(["docker", "inspect", "--format", "{{json .HostConfig.ExtraHosts}}", worker_id],
                               capture_output=True, text=True, timeout=15, check=True).stdout
        r.check("컨테이너 워커에 host.docker.internal → host-gateway 가 있다", "host.docker.internal:host-gateway" in hosts, hosts.strip(), kind="quality")
    except Exception as e:                                                                      # docker 명령이 없는 PC(강의실 Windows 아님)는 판정만 남긴다
        r.check("컨테이너 워커 extra_hosts 확인", False, f"{type(e).__name__}: {e}", kind="quality")

    try:
        # ---- 등록: 예외 먼저(잘못된 이름 · 꺼진 주소 검사만) → 정상 등록 → 중복 · 기준 이름
        servers = {s["name"]: s for s in r.get(f"{r.process}/api/mcp/servers")["servers"]}
        r.tab("mcp")
        err, _ = _b_mcp_form(r, name="S01_Table", url=url, description="내 업무 표 읽기")
        r.check("잘못된 서버 이름 → 거절 · 무엇을 쓸지 말한다", "소문자" in err and r.human_message(err)[0], err, kind="exception")
        err, res = _b_mcp_form(r, name=_B_MCP_NAME, url=f"http://host.docker.internal:{_b_free_port(port + 1)}/mcp", dry=True)
        ok, why = r.human_message(res)
        r.check("꺼진 주소로 연결 검사만 → 실패 사유(연결 거부)가 사람 글", "연결 검사 실패" in res and ok, why, kind="exception")
        if _B_MCP_NAME in servers:                                                              # 두 번째 실행 PC: 이미 있다 → 고치기(새 포트)
            page.locator("#mcpFormClose").click()
            _b_mcp_select(r, _B_MCP_NAME)
            page.click("#mcpEdit")
            err, res = _b_mcp_form(r, name=_B_MCP_NAME, url=url, description="내 업무 표 읽기", edit=True)
            r.check("이미 등록한 내 서버를 고치기(새 주소) → 검사 후 저장", not err, err or res)
        else:
            err, res = _b_mcp_form(r, name=_B_MCP_NAME, url=url, description="내 업무 표 읽기")
            toast = _b_toast_text(r, 5)
            r.check("내 서버 검사 후 등록 → 읽기 도구 3개", not err and "등록했습니다" in toast and "3개" in toast, err or toast)
        err, _ = _b_mcp_form(r, name=_B_MCP_NAME, url=url)
        r.check("같은 이름 중복 등록 → 거절 · 고치기를 쓰라고 말한다", "이미 있습니다" in err, err, kind="exception")
        err, _ = _b_mcp_form(r, name="enterprise", url=url)
        r.check("기준 서버 이름으로 등록 → 거절", "기준" in err, err, kind="exception")
        if page.locator("#mcpFormClose").count():
            page.locator("#mcpFormClose").click()

        # ---- 연결 검사 → 써 보기 → (없는 표 · 틀린 입력) → 호출 기록
        toast = _b_mcp_probe(r, _B_MCP_NAME)
        r.check("내 서버 연결 검사 통과 · 도구 수", "통과" in toast, toast)
        detail = page.locator("#mcpDetail").inner_text()
        r.check("「에이전트 도구로 고를 수 있음」 · 「내가 등록」", "에이전트 도구로 고를 수 있음" in detail, detail[:300])
        out = _b_mcp_try(r, "list_tables", {})
        r.check("써 보기 list_tables → meeting · attendee 표", "meeting" in out and "attendee" in out, out[:300])
        out = _b_mcp_try(r, "read_rows", {"table": "meeting", "limit": "5"})
        r.check("써 보기 read_rows → 행 · 보낸 입력 · 시간", f"{_B_STUDENT}:meeting-q3" in out and "보낸 입력" in out, out[:300])
        out = _b_mcp_try(r, "read_rows", {"table": "no_such_table", "limit": "5"})
        r.check("없는 표 → 도구가 한국어로 거절(있는 표 목록)", "없습니다" in out and "meeting" in out, out[:300], kind="exception")
        chip = page.locator("#mcpResult .chip").first.inner_text() if page.locator("#mcpResult .chip").count() else ""
        r.check("없는 표 결과 칩이 성공(「결과」)이 아니라 오류로 보인다", chip != "결과", f"칩 '{chip}' — 도구가 {{result: error}} 봉투를 돌려도 is_error 가 아니라 초록 칩(mcp.js resultHtml · mcp_check.shape_result)",
                kind="quality")
        out = _b_mcp_try(r, "read_rows", {"table": "meeting", "limit": "abc"})
        r.check("limit 에 글자 → 보내기 전에 「정수여야 합니다」", "정수" in out, out[:200], kind="exception")
        code, body = r.api("POST", f"{r.process}/api/mcp/servers/{_B_MCP_NAME}/tools/drop_tables/call", {"arguments": {}, "timeout": 10, "by": "수업 한 바퀴"})
        # 화면에는 도구 이름을 적는 칸이 없다(목록에서만 고름) → 잘못된 도구 이름은 API 로만 볼 수 있다(관측 보완)
        r.check("없는 도구 이름 → 404 · 한국어 사유", code == 404 and r.human_message(str((body or {}).get("detail")))[0], f"{code} {body}", kind="exception")
        page.click("#mcpDetail [data-mcp-tab='calls']")
        r.wait(10, lambda: "불러오는 중" not in page.locator("#mcpCallList").inner_text(), every=1)
        r.check("호출 기록(에이전트 실행 전): 비어 있음 안내가 사람 글", r.human_message(page.locator("#mcpCallList").inner_text())[0],
                page.locator("#mcpCallList").inner_text()[:200], kind="normal")

        # ---- 기존(내) 에이전트에 연결해 실행(AI 3회) — 컨테이너 워커 → host.docker.internal → 학생 PC 서버
        agent_id = r.memo.get("my_agent")
        if not agent_id:
            r.check("06의 나의 에이전트가 있어야 연결할 수 있다", False)
            return
        _b_open_agent_edit(r, agent_id)
        page.locator("[data-ag-form]").wait_for(timeout=10_000)
        r.check("에이전트 폼 도구 목록에 내 서버가 「연결 확인됨」으로 보인다",
                page.locator(f"[data-ag-form] input[data-f-tool][value='{_B_MCP_NAME}']").count() == 1, kind="normal")
        err = _b_agent_form(r, tools=["neo4j", "hyd-dmn", _B_MCP_NAME])
        r.check("나의 에이전트 도구에 내 서버 붙이기", not err, err)
        q = f"내 업무 표(stu_{_B_STUDENT})에서 회의 {_B_STUDENT}:meeting-q3 에 잡힌 회의실 좌석 수와, 필수 참석자 가운데 아직 응답하지 않은 사람의 이메일을 알려 줘."

        def ask_once(i):
            v = _b_ask(r, agent_id, q)
            used = [t for t in v["tools"] if _B_MCP_NAME in t]
            v.update(student_tool_used=bool(used), answer_has_seats=bool(re.search(r"\b4\s*(?:석|개|명|좌석)?", v["answer"])),
                     answer_has_customer="customer@example.com" in v["answer"])
            return v

        runs = r.repeat3("내 서버를 쓰는 질문", ask_once, ("kind", "student_tool_used", "answer_has_seats", "answer_has_customer"), limit_s=_B_ASK_LIMIT_S)
        last = runs[-1]
        r.check("컨테이너 워커가 학생 PC 서버 도구를 실제로 불렀다", last.get("student_tool_used"), str(last.get("tools")))
        r.check("답이 표의 실제 값(좌석 4 · 무응답 customer@)과 맞고 근거 확인", last.get("answer_has_seats") and last.get("answer_has_customer") and last.get("verified_ok"),
                last.get("answer"), kind="quality")
        _b_mcp_select(r, _B_MCP_NAME)
        page.click("#mcpDetail [data-mcp-tab='calls']")
        r.wait(15, lambda: page.locator("#mcpCallList .mcp-calls li").count(), every=1)
        calls = page.locator("#mcpCallList").inner_text()
        r.check("호출 기록: 도구 이름 · 입력 · 결과 · 처리 건 링크", page.locator("#mcpCallList .mcp-calls li").count() >= 1 and "입력" in calls and "처리 건" in calls, calls[:400])

        # ---- 서버가 꺼진 상태: 검사 실패 사유 · 에이전트가 지어내지 않음 → 다시 켜고 검사(되돌리기)
        _b_stop_mcp(proc)
        toast = _b_mcp_probe(r, _B_MCP_NAME)
        ok, why = r.human_message(toast)
        r.check("서버를 끄고 연결 검사 → 실패(연결 거부) · 사람 글", "실패" in toast and ok, why, kind="exception")
        # 검사 결과로 상세 머리(gateLine)가 다시 그려질 때까지(final5: 토스트 직후 옛 상세를 읽음 — 카드에는 이미 「연결 검사 실패」)
        r.wait(15, lambda: "고를 수 없음" in page.locator("#mcpDetail").inner_text(), every=1)
        r.check("검사 실패 뒤 「에이전트 도구로 고를 수 없음」", "고를 수 없음" in page.locator("#mcpDetail").inner_text(), kind="exception")
        off = _b_ask(r, agent_id, q)
        r.check("서버가 꺼졌을 때 질문 → 표 값을 지어내지 않는다", not ("customer@example.com" in off["answer"] and off.get("kind") == "answered"),
                f"{off.get('kind')} · {off.get('answer')[:200]}", kind="exception")
        proc, up = _b_start_mcp(r, dsn, port)
        toast = _b_mcp_probe(r, _B_MCP_NAME)
        r.check("서버를 다시 켜고 연결 검사 → 다시 통과(뒤처진 학생 따라붙기)", up and "통과" in toast, toast, kind="exception")
    finally:
        _b_stop_mcp(proc)
        # 다음 실습이 꺼진 학생 서버를 붙인 채 에이전트를 돌리지 않게 도구를 뗀다(등록은 남긴다 — 메뉴 순회에서 「연결 거부」 칩으로 보인다)
        if r.memo.get("my_agent"):
            try:
                _b_open_agent_edit(r, r.memo["my_agent"])
                _b_agent_form(r, tools=["neo4j", "hyd-dmn"])
            except Exception:
                pass
        r.memo["b_mcp"] = {"name": _B_MCP_NAME, "port": port, "server_stopped": True}


# ====================================================================== part_C
# part_C — 실습 09 · 10 · 11 · 12 · 13 · 그 밖에 92 · 93 (scripts/class_round.py 의 「실습」 자리에 붙여 넣는 몸통)
#
# 하네스가 이미 가져온 것만 쓴다: json, re, time, urllib.request(→ urllib.parse 도 함께 올라온다), Path, ROOT, Round, lab.
# 따로 import 하지 않는다. 이 파일의 이름은 모두 _c_ 로 시작한다(다른 part 와 겹치지 않게).
#
# 셀렉터는 2026-10-25 라이브 포털(:18088)에서 읽기로 확인했다(notes_C.md (b)). 「# 미확인」 은 코드만 읽고 화면에서 못 본 것.
# 상태를 바꾸는 판정(가져오기 · 등록 · 배포 · 버튼)은 메인의 한 번 실행에서 처음 돈다 — 이 초안은 그 전에 실행해 보지 않았다.
#
# 시간 기준(TIME_SCALE=20):
#   - 승인 지연 타이머 PT10M = 실제 30초(멈추지 않는 점선 타이머: 알림만, 승인 단계는 계속 기다림)
#   - 카드 예측 검토 유효 1800 시뮬레이션 초 = 실제 90초(it/agent/agentsvc/forecasting.py:20). 넘기면 「새 카드 검토가 필요」 → [미리 보기] 뒤 다시 [승인]
#   - AI 판단(워커 · LiteLLM coding): 판단 · 제안 1회 실측 46~79초(scenario_buttons.py A_SEVERITY 주석). 느린 PC 를 보아 기다림은 900초,
#     학생 진행 기준(가장 느린 3회 중 1회)은 300초로 판정한다(C_AI_LIMIT_S).

C_AI_WAIT_S = 900          # 판단 · 제안 결과(카드)까지 기다리는 상한 — 워커 4단계 기준 흐름 회귀가 쓰는 900초와 같다(scenario_pump_fan_test --worker)
C_AI_LIMIT_S = 300         # repeat3 소요 시간 판정 — 수업 진행상 한 단계 5분. 근거: B 의 야간 정비 창(가상 9 h = 실제 27분) 안에 승인까지 끝나야 한다
C_RAISE_WAIT_S = 300       # 쿨러 moderate 열화 → COOLER_DEGRADATION RAISE(20배속, 평형 62.5 ℃ · 경보선 55 ℃) 넉넉히
C_DELAY_NOTICE_S = 30      # PT10M ÷ 20
C_REVIEW_TTL_S = 90        # 1800 시뮬레이션 초 ÷ 20
C_FLOWS = ROOT / "students" / "flows"
C_MAILS = {"production": "production@hyd.local", "supplier": "supplier@hyd.local", "receiving": "receiving@hyd.local"}
C_PEOPLE = {"role:operator": "user:kim-op", "role:prod-mgr": "user:lee-prod", "role:maint-mgr": "user:park-maint",
            "role:purchasing": "user:jung-buy", "role:purchasing-mgr": "user:han-buymgr"}
C_ROLE_NAME = {"운전원": "role:operator", "생산관리자": "role:prod-mgr", "설비보전팀장": "role:maint-mgr", "구매 담당": "role:purchasing",
               "구매팀장": "role:purchasing-mgr"}


# ====================================================================== bpmn.io 꼴 그림 만들기
# 학생이 demo.bpmn.io 에서 새로 그려 [Download BPMN diagram] 으로 받은 파일 모양: 고유 id(Activity_0abc123 · Gateway_ · Event_ · Flow_ ·
# StartEvent_1 · Process_), incoming/outgoing 자식, bpmndi:BPMNDiagram(좌표). students/flows/*.bpmn(T_agent 꼴 id)과 다르다.
# 시작은 bpmn.io 기본값인 빈 시작(메시지 정의 없음) — 그래서 가져오면 시작 조건 기본값이 「사람 입력 · 직접 시작」이 되고,
# 학생이 「경보로 시작」을 직접 골라야 한다(bpmn_import.merge_mapping 513-519).
def _c_fnv(text: str) -> int:
    h = 0xcbf29ce484222325
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def _c_bid(prefix: str, seed: str) -> str:
    """bpmn.io 가 붙이는 꼴의 id: 접두어 + 7글자(첫 글자 0/1, 나머지 base36)."""
    n, digits = _c_fnv(seed), "0123456789abcdefghijklmnopqrstuvwxyz"
    tail = "".join(digits[(n >> (6 * i)) % 36] for i in range(6))
    return f"{prefix}_{n % 2}{tail}"


def _c_esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _c_draw(seed: str, name: str, nodes: list, flows: list, lanes: list | None = None, interrupting_timer: bool = False) -> tuple[str, dict]:
    """nodes = [(key, kind, 이름, 열, 행, 붙을 key)] kind: start · task · userTask · serviceTask · xor · end · timer
    flows = [(key, 출발 key, 도착 key, 선 이름)]  lanes = [(이름, [node key…])] (있으면 풀 하나 + 칸)
    돌려줌: (xml, {key: 생성 id}). interrupting_timer=True 는 bpmn.io 기본 타이머(끊는 경계 이벤트, cancelActivity 속성 없음)."""
    ids = {"__proc": _c_bid("Process", seed), "__defs": _c_bid("Definitions", seed + "d")}
    for k, kind, *_ in nodes:
        ids[k] = ("StartEvent_1" if kind == "start" else
                  _c_bid({"task": "Activity", "userTask": "Activity", "serviceTask": "Activity", "xor": "Gateway"}.get(kind, "Event"), seed + k))
    for k, *_ in flows:
        ids[k] = _c_bid("Flow", seed + k)
    inc, out = {}, {}
    for k, s, t, _n in flows:
        out.setdefault(s, []).append(ids[k]); inc.setdefault(t, []).append(ids[k])
    size = {"start": (36, 36), "end": (36, 36), "timer": (36, 36), "xor": (50, 50)}
    pos = {}
    for k, kind, _nm, col, row, *_ in nodes:
        w, h = size.get(kind, (100, 80))
        pos[k] = (180 + col * 160, 100 + row * 140, w, h)
    body = []
    for k, kind, nm, col, row, *rest in nodes:
        attr = f' name="{_c_esc(nm)}"' if nm else ""
        kids = "".join(f"<bpmn:incoming>{f}</bpmn:incoming>" for f in inc.get(k, [])) + "".join(f"<bpmn:outgoing>{f}</bpmn:outgoing>" for f in out.get(k, []))
        if kind == "start":
            body.append(f'<bpmn:startEvent id="{ids[k]}"{attr}>{kids}</bpmn:startEvent>')
        elif kind == "end":
            body.append(f'<bpmn:endEvent id="{ids[k]}"{attr}>{kids}</bpmn:endEvent>')
        elif kind == "xor":
            body.append(f'<bpmn:exclusiveGateway id="{ids[k]}"{attr}>{kids}</bpmn:exclusiveGateway>')
        elif kind == "timer":
            cancel = "" if interrupting_timer else ' cancelActivity="false"'
            body.append(f'<bpmn:boundaryEvent id="{ids[k]}"{attr}{cancel} attachedToRef="{ids[rest[0]]}">{kids}'
                        f'<bpmn:timerEventDefinition id="{_c_bid("TimerEventDefinition", seed + k)}" /></bpmn:boundaryEvent>')
        else:
            body.append(f'<bpmn:{kind} id="{ids[k]}"{attr}>{kids}</bpmn:{kind}>')
    for k, s, t, nm in flows:
        attr = f' name="{_c_esc(nm)}"' if nm else ""
        body.append(f'<bpmn:sequenceFlow id="{ids[k]}"{attr} sourceRef="{ids[s]}" targetRef="{ids[t]}" />')
    lane_xml, collab, plane_ref = "", "", ids["__proc"]
    if lanes:
        part = _c_bid("Participant", seed)
        collab = f'<bpmn:collaboration id="{_c_bid("Collaboration", seed)}"><bpmn:participant id="{part}" name="{_c_esc(name)}" processRef="{ids["__proc"]}" /></bpmn:collaboration>'
        lane_xml = f'<bpmn:laneSet id="{_c_bid("LaneSet", seed)}">' + "".join(
            f'<bpmn:lane id="{_c_bid("Lane", seed + ln)}" name="{_c_esc(ln)}">' + "".join(f"<bpmn:flowNodeRef>{ids[n]}</bpmn:flowNodeRef>" for n in members) + "</bpmn:lane>"
            for ln, members in lanes) + "</bpmn:laneSet>"
        plane_ref = _c_bid("Collaboration", seed)
    di = []
    for k, (x, y, w, h) in pos.items():
        di.append(f'<bpmndi:BPMNShape id="{ids[k]}_di" bpmnElement="{ids[k]}"><dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /><bpmndi:BPMNLabel /></bpmndi:BPMNShape>')
    for k, s, t, _n in flows:
        (sx, sy, sw, sh), (tx, ty, tw, th) = pos[s], pos[t]
        di.append(f'<bpmndi:BPMNEdge id="{ids[k]}_di" bpmnElement="{ids[k]}"><di:waypoint x="{sx + sw}" y="{sy + sh // 2}" /><di:waypoint x="{tx}" y="{ty + th // 2}" /></bpmndi:BPMNEdge>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
           'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
           f'id="{ids["__defs"]}" targetNamespace="http://bpmn.io/schema/bpmn" exporter="bpmn-js (https://demo.bpmn.io)" exporterVersion="17.11.1">\n'
           f'{collab}<bpmn:process id="{ids["__proc"]}" isExecutable="false">{lane_xml}' + "\n".join(body) + "</bpmn:process>\n"
           f'<bpmndi:BPMNDiagram id="BPMNDiagram_1"><bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{plane_ref}">' + "".join(di)
           + "</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>\n</bpmn:definitions>\n")
    return xml, ids


# 세 흐름의 그림 — 이름은 학생이 새로 붙인 것(참조 파일과 일부 다름), ref 는 students/flows/*.mapping.json 의 키(학생이 표를 보며 고르는 줄)
_C_APPROVAL_PART = [  # 공통 승인 단계: 승인 → 승인?(승인/거절), 점선 타이머 → 지연 알림
    ("P", "userTask", None, 2, 0), ("B", "timer", "승인 지연", 2, 1, "P"), ("N", "serviceTask", "승인 지연 알림", 3, 2), ("EN", "end", "알림", 4, 2),
    ("G1", "xor", "승인?", 3, 0), ("RJ", "serviceTask", "결과 보고: 거절", 4, 1), ("ERJ", "end", "거절 종결", 5, 1)]
C_SPECS = {
    "cooling": {"file": "cooling-emergency", "name": "내 냉각 긴급 대응", "pattern": "COOLER_DEGRADATION", "approver": "운전원",
                "names": {"S": "쿨러 과열 경보", "A": "원인 진단 · 냉각 조치 제안", "P": "운전원 승인", "C": "냉각 명령", "O": "재관측",
                          "G2": "유온 정상?", "W": "작업지시 등록", "ROK": "결과 보고: 정상", "RF": "결과 보고: 미달", "E": "끝"},
                "ref": {"A": "T_agent", "P": "T_approve", "N": "T_notice", "RJ": "R_rejected", "C": "T_cmd", "O": "T_reobs", "W": "T_wo",
                        "ROK": "R_ok", "RF": "R_fail", "B": "B_overdue", "f_ok": "F_approved", "f_rej": "F_rejected", "f_yes": "F_yes", "f_no": "F_no"},
                "tail": [("C", "serviceTask", None, 4, 0), ("O", "serviceTask", None, 5, 0), ("G2", "xor", None, 6, 0), ("W", "serviceTask", None, 7, 0),
                         ("ROK", "serviceTask", None, 8, 0), ("E", "end", None, 9, 0), ("RF", "serviceTask", None, 7, 1)],
                "tail_flows": [("f_ok", "G1", "C", "승인"), ("f4", "C", "O", ""), ("f5", "O", "G2", ""), ("f_yes", "G2", "W", "예"), ("f_no", "G2", "RF", "아니오"),
                               ("f6", "W", "ROK", ""), ("f7", "ROK", "E", ""), ("f8", "RF", "E", "")]},
    "pm": {"file": "pm-planning", "name": "내 정기 정비", "pattern": "PM_DUE", "approver": "설비보전팀장",
           "names": {"S": "정기 점검 요청", "A": "정비 계획 제안", "P": "설비보전팀장 승인", "W": "정비 오더 등록 · 공지 메일", "ROK": "결과 보고", "E": "끝"},
           "ref": {"A": "T_agent", "P": "T_approve", "N": "T_notice", "RJ": "R_rejected", "W": "T_wo", "ROK": "R_ok", "B": "B_overdue",
                   "f_ok": "F_approved", "f_rej": "F_rejected"},
           "tail": [("W", "serviceTask", None, 4, 0), ("ROK", "serviceTask", None, 5, 0), ("E", "end", None, 6, 0)],
           "tail_flows": [("f_ok", "G1", "W", "승인"), ("f4", "W", "ROK", ""), ("f5", "ROK", "E", "")]},
    "spare": {"file": "spare-purchase", "name": "내 예비품 구매", "pattern": "SPARE_BELOW_MIN", "approver": "구매 담당",
              "names": {"S": "재고 보충 요청", "A": "발주안 제안", "P": "구매 담당 승인", "PO": "ERP 발주 · 공급사 메일", "GR": "입고 · 재고 반영",
                        "ROK": "결과 보고", "E": "끝"},
              "ref": {"A": "T_agent", "P": "T_approve", "N": "T_notice", "RJ": "R_rejected", "PO": "T_po", "GR": "T_gr", "ROK": "R_ok", "B": "B_overdue",
                      "f_ok": "F_approved", "f_rej": "F_rejected"},
              "tail": [("PO", "serviceTask", None, 4, 0), ("GR", "serviceTask", None, 5, 0), ("ROK", "serviceTask", None, 6, 0), ("E", "end", None, 7, 0)],
              "tail_flows": [("f_ok", "G1", "PO", "승인"), ("f4", "PO", "GR", ""), ("f5", "GR", "ROK", ""), ("f6", "ROK", "E", "")]},
}


def _c_spec_xml(kind: str, seed: str, interrupting_timer: bool = False) -> tuple[str, dict, dict]:
    """(xml, ids, 단계 이름표 {key: 이름})."""
    sp = C_SPECS[kind]
    names = dict(sp["names"])
    names.setdefault("N", "승인 지연 알림"); names.setdefault("RJ", "결과 보고: 거절")
    nodes = [("S", "start", names["S"], 0, 0), ("A", "task", names["A"], 1, 0)]
    for k, knd, nm, col, row, *att in _C_APPROVAL_PART + sp["tail"]:
        nodes.append((k, knd, names.get(k, nm), col, row, *att))
    flows = [("f1", "S", "A", ""), ("f2", "A", "P", ""), ("f3", "P", "G1", ""), ("f_rej", "G1", "RJ", "거절"), ("frj", "RJ", "ERJ", ""),
             ("fov", "B", "N", ""), ("fne", "N", "EN", "")] + sp["tail_flows"]
    xml, ids = _c_draw(seed, sp["name"], nodes, flows, interrupting_timer=interrupting_timer)
    return xml, ids, {k: n[2] for k, n in zip([n[0] for n in nodes], nodes)}


def _c_mapping(kind: str) -> dict:
    return json.loads((C_FLOWS / f"{C_SPECS[kind]['file']}.mapping.json").read_text(encoding="utf-8"))


# ====================================================================== 화면 조작 도우미 (흐름 가져오기)
def _c_settle(r, ms: int = 900):
    """매핑 화면은 바꿀 때마다 다시 그리고(renderEditor) 0.3초 뒤 서버 검사(POST …/check)로 한 번 더 그릴 수 있다 — 끝날 때까지 기다린다."""
    r.page.wait_for_timeout(ms)


def _c_free_id(r, base: str) -> str:
    """같은 스택에서 다시 돌려도 「새로 그린 흐름」이 되게: 이미 초안이 있으면 뒤에 번호. 학생이 my_cooling 을 쓰는 것과 같은 꼴."""
    for n in range(0, 50):
        cand = base if n == 0 else f"{base}{n + 1}"
        code, _ = r.api("GET", f"{r.process}/api/flows/{cand}")
        if code == 404:
            return cand
    return f"{base}_{int(time.time()) % 100000}"


def _c_import(r, xml: str, file_name: str, def_id: str) -> tuple[str, bool]:
    """[흐름 가져오기] 화면: 파일 고르기 → 흐름 id → [가져오기]. (메시지, 성공?)"""
    r.tab("flows")
    r.page.wait_for_selector("#flowFile", state="attached")
    r.page.set_input_files("#flowFile", files=[{"name": file_name, "mimeType": "application/xml", "buffer": xml.encode("utf-8")}])
    r.page.fill("#flowId", def_id)
    r.page.click("#flowImport")
    msg = r.page.locator("#flowImportMsg")
    r.wait(30, lambda: msg.inner_text().strip() not in ("", "읽는 중…"), every=0.5)
    text = msg.inner_text().strip()
    ok = "form-msg pos" in (msg.get_attribute("class") or "") or text.startswith(("가져옴", "다시 가져옴"))
    if ok:
        r.page.wait_for_selector("#flowEditor #flowCheck")
        _c_settle(r)
    return text, ok


def _c_row(r, step_name: str) -> str:
    """매핑 표에서 「그림의 단계」 이름으로 행을 찾아 task id(data-row)를 돌려준다 — 학생이 이름을 보고 고르는 것과 같다."""
    rows = r.page.locator("#flowEditor table.flow-map tr[data-row]")
    for i in range(rows.count()):
        row = rows.nth(i)
        if row.locator("td[data-label='단계'] b").inner_text().strip() == step_name:
            return row.get_attribute("data-row")
    raise AssertionError(f"매핑 표에 단계 '{step_name}' 이(가) 없습니다")


def _c_set_fields(r, editor, fields: list[dict]):
    """칸 편집기(.field-rows): [+ 칸 추가] → 값 이름 · 화면 이름 · 종류 · 고를 값. fields = [{key, text, type, items?}]."""
    for f in fields:
        editor.locator("[data-add]").click()
        row = editor.locator(".field-row:not(.head)").last
        row.locator("[data-k=key]").fill(f["key"])
        row.locator("[data-k=text]").fill(f.get("text") or f["key"])
        if (f.get("type") or "text") != "text":
            row.locator("select[data-k=type]").select_option(f["type"])
            row = editor.locator(".field-row:not(.head)").last           # 종류를 바꾸면 행을 다시 그린다
        if f.get("items"):
            row.locator("[data-k=items]").fill(", ".join(f["items"]))
    _c_settle(r, 500)


def _c_apply_task(r, step_name: str, m: dict, *, skip_part: bool = False):
    """mapping.json 의 tasks[ref] 한 줄을 화면에 입력: 부품 → 담당(역할 · 에이전트) → 지시문 → 설정(결과 보고 · 메일 · 기타)."""
    tid = _c_row(r, step_name)
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    if not skip_part:
        q(f"select[data-part='{tid}']").select_option(m["part"])
        _c_settle(r)
    if m.get("role"):
        q(f"select[data-role='{tid}']").select_option(label=m["role"])
    if m.get("agent"):
        q(f"select[data-agent='{tid}']").select_option(m["agent"])
    if m.get("instruction") is not None and q(f"textarea[data-instruction='{tid}']").count():
        q(f"textarea[data-instruction='{tid}']").fill(m["instruction"])
    if m.get("inputs") and q(f"input[data-inputs='{tid}']").count():
        q(f"input[data-inputs='{tid}']").fill(", ".join(m["inputs"]))
    if m.get("outputs"):
        _c_set_fields(r, q(f"tr[data-row='{tid}'] textarea[data-outputs='{tid}'] ~ .field-rows").first, m["outputs"])
    if m.get("fields"):
        _c_set_fields(r, q(f"tr[data-row='{tid}'] textarea[data-fields='{tid}'] ~ .field-rows").first, m["fields"])
    for key, val in (m.get("config") or {}).items():
        if key == "mail" and isinstance(val, dict):
            for mk, mv in val.items():
                q(f"[data-mail='{tid}'][data-mail-key='{mk}']").fill(str(mv))
            continue
        box = q(f"[data-service='{tid}'][data-cfg='{key}']")
        if box.count() == 0 and q(f"[data-approval='{tid}'][data-cfg='{key}']").count():
            q(f"[data-approval='{tid}'][data-cfg='{key}']").fill(str(val)); continue
        tag = box.evaluate("e => e.tagName")
        if tag == "SELECT":
            box.select_option(str(val).lower() if isinstance(val, bool) else str(val))
        else:
            box.fill(json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val))
    _c_settle(r, 600)


def _c_apply_start(r, start: dict):
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    if start.get("kind") == "alert":
        q("input[name=flowStart][value=alert]").check(); _c_settle(r)
        for pt in r.page.locator("#flowEditor [data-pattern]").all():   # 처음에는 아무것도 고르지 않는다 — 표의 경보 하나만
            want = pt.get_attribute("data-pattern") in (start.get("patterns") or [])
            if pt.is_checked() != want:
                pt.set_checked(want); _c_settle(r, 500)
    elif start.get("kind") == "human":
        q("input[name=flowStart][value=human]").check(); _c_settle(r)
        if start.get("fields"):
            _c_set_fields(r, q("#flowStartFields ~ .field-rows").first, start["fields"])


def _c_apply_branch(r, gw_name: str, target_name: str, spec: dict, *, flow_id: str | None = None):
    """분기 '<gw_name>' 블록에서 「→ <target_name>」 줄의 조건. spec = {default: true} 또는 {var, op, value}.
    같은 이름의 분기가 여럿이면(교대의 회차별 「검토 결정」) 그림의 연결선 id(flow_id)로 그 줄을 고른다."""
    if flow_id:
        fid = flow_id
    else:
        block = r.page.locator("#flowEditor div.field[data-row]").filter(has_text=f"분기 '{gw_name}'").first
        line = block.locator("tr[data-row]").filter(has_text=f"→ {target_name}").first
        fid = line.get_attribute("data-row")
    q = lambda css: r.page.locator(f"#flowEditor {css}")                 # noqa: E731
    if spec.get("default"):
        q(f"input[data-default='{fid}']").check(); _c_settle(r); return
    q(f"select[data-var='{fid}']").select_option(spec["var"]); _c_settle(r)
    q(f"select[data-op='{fid}']").select_option(spec.get("op") or "==")
    box = q(f"[data-value='{fid}']")
    val = spec.get("value")
    if box.evaluate("e => e.tagName") == "SELECT":
        box.select_option(label=str(val))
    else:
        box.fill("예" if val is True else "아니요" if val is False else str(val))
    _c_settle(r, 500)


def _c_check(r) -> tuple[bool, list[str], str]:
    """[검사] → (통과?, 고칠 곳 줄들, 연결 도구 준비 글)."""
    r.page.click("#flowEditor #flowCheck")
    r.wait(30, lambda: r.page.locator("#flowMsg").inner_text().strip() not in ("", "검사 중…"), every=0.5)
    _c_settle(r, 600)
    passed = r.page.locator("#flowProblems .kv-line.pos").count() > 0
    problems = [x.inner_text().strip() for x in r.page.locator("#flowProblems .flow-problems li").all()]
    deps = " ".join(x.inner_text().strip() for x in r.page.locator("#flowProblems .flow-dependencies").all())
    return passed, problems, deps


def _c_register(r) -> tuple[bool, str, str | None]:
    """[판본 등록] → (등록됨?, #flowMsg 글, 판본)."""
    r.page.click("#flowEditor #flowRegister")
    msg = r.page.locator("#flowMsg")
    r.wait(30, lambda: ("등록" in msg.inner_text()) or "neg" in (msg.get_attribute("class") or ""), every=0.5)
    text = msg.inner_text().strip()
    m = re.search(r"판본 (\S+) 을\(를\) 등록했습니다", text)
    return bool(m), text, (m.group(1) if m else None)


def _c_fill_cooling_like(r, kind: str, names: dict, *, skip: tuple = ()):
    """mapping.json 대로 화면 입력. skip = 일부러 빼 둘 ref(예외 경로: 부품 누락 · 분기 조건 누락)."""
    sp, m = C_SPECS[kind], _c_mapping(kind)
    r.page.locator("#flowEditor #flowName").fill(m.get("name") and sp["name"])
    _c_apply_start(r, m["start"])
    ref = sp["ref"]
    # 승인 단계를 먼저(분기 값 approval 이 그 뒤로 보인다), 그다음 나머지
    order = ["A", "P"] + [k for k in ref if k not in ("A", "P", "B") and not k.startswith("f_")]
    for key in order:
        rk = ref[key]
        if rk in skip or rk not in m["tasks"]:
            continue
        _c_apply_task(r, names[key], m["tasks"][rk])
    if "B_overdue" not in skip:
        r.page.locator("#flowEditor input[data-timer]").first.fill(str(int(re.match(r"PT(\d+)M", m["timers"]["B_overdue"]).group(1))))
        _c_settle(r, 500)
    for fkey, (gw, target) in {"f_ok": ("승인?", names.get(sp["tail_flows"][0][2])), "f_rej": ("승인?", names["RJ"]),
                               "f_yes": ("유온 정상?", names.get("W")), "f_no": ("유온 정상?", names.get("RF"))}.items():
        rk = ref.get(fkey)
        if not rk or rk in skip:
            continue
        _c_apply_branch(r, gw, target, m["flows"][rk])


# ---------------------------------------------------------------------- 배포 · 되돌리기 ([관리] 탭)
def _c_admin_deploy_panel(r):
    r.tab("admin")
    panel = r.page.locator("#definitionDeployPanel")
    if not panel.evaluate("e => e.open"):
        panel.locator(":scope > summary").click()
    else:
        r.page.click("#deployRefresh")
    r.wait(20, lambda: r.page.locator("#deployChoice option").count() > 0 and "불러오는 중" not in r.page.locator("#deployChoice").inner_text(), every=0.5)
    r.page.wait_for_timeout(800)
    return panel


def _c_deploy(r, def_id: str, version: str, *, by: str = "학생 한 명", reason: str = "실습 9-3 내가 그린 흐름 배포") -> tuple[bool, str]:
    _c_admin_deploy_panel(r)
    r.page.locator("#deployChoice").select_option(def_id)
    r.wait(20, lambda: r.page.locator(f"#deployVersions [data-deploy='{version}']").count() > 0, every=0.5)
    r.page.fill("#deployBy", by)
    r.page.fill("#deployReason", reason)
    r.page.evaluate("() => { const m = document.getElementById('deployMessage'); if (m) m.textContent = ''; }")   # 앞 결과를 이번 결과로 읽지 않게
    r.page.click(f"#deployVersions [data-deploy='{version}']")
    msg = r.page.locator("#deployMessage")
    r.wait(30, lambda: msg.inner_text().strip() != "", every=0.5)
    text = msg.inner_text().strip()
    return ("배포" in text and "neg" not in (msg.get_attribute("class") or "")), text


def _c_reset_to_reference(r, by: str = "학생 한 명") -> tuple[bool, str]:
    """[기준 흐름으로 되돌리기] → 확인 대화상자 [되돌리기]. 학생 흐름만 내리고 수업 흐름(c3_*)은 남긴다(flow_deploy.deploy_reset)."""
    _c_admin_deploy_panel(r)
    btn = r.page.locator("#deployResetRef")
    if btn.is_disabled():
        return False, "되돌릴 것이 없음(버튼 꺼짐)"
    r.page.fill("#deployBy", by)
    r.page.evaluate("() => { const m = document.getElementById('deployMessage'); if (m) m.textContent = ''; }")
    btn.click()
    r.page.locator("dialog.confirm-dialog button[value=ok]").click()
    msg = r.page.locator("#deployMessage")
    r.wait(30, lambda: msg.inner_text().strip() != "", every=0.5)
    return "neg" not in (msg.get_attribute("class") or ""), msg.inner_text().strip()


def _c_routes(r) -> dict:
    """경보 패턴 → {definition, version, source, class_flow} (GET /api/flows/deployments)."""
    d = r.get(f"{r.process}/api/flows/deployments")
    return {x["pattern"]: x for x in d.get("routes") or []}


# ---------------------------------------------------------------------- 처리 건 · 승인 도우미
def _c_vars(inst: dict) -> dict:
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or [])}


def _c_view(r, pid: str) -> dict:
    return r.get(f"{r.process}/api/instances/{urllib.parse.quote(pid, safe='')}")


def _c_instance_ids(r) -> set:
    return {i["proc_inst_id"] for i in r.get(f"{r.process}/api/instances?limit=80")}


def _c_new_instance(r, before: set, def_id: str | None, timeout: float) -> dict | None:
    def probe():
        for i in r.get(f"{r.process}/api/instances?limit=80"):
            if i["proc_inst_id"] not in before and (def_id is None or i["proc_def_id"] == def_id):
                return i
        return None
    return r.wait(timeout, probe, every=2)


def _c_item(view: dict, step_name: str) -> dict:
    rows = [w for w in view["workitems"] if w.get("activity_name") == step_name]
    rows.sort(key=lambda w: (w.get("generation") or 0, w.get("start_date") or ""))
    return rows[-1] if rows else {}


def _c_wait_step(r, pid: str, step_name: str, timeout: float) -> tuple[str, dict]:
    """그 단계가 사람 차례(IN_PROGRESS)가 되거나 어디선가 멈출(PENDING · 처리 건 끝) 때까지. ('ready'|'stuck'|'ended'|'timeout', view)."""
    last = {}
    def probe():
        nonlocal last
        v = last = _c_view(r, pid)
        if v["instance"]["status"] != "RUNNING":
            return "ended"
        if _c_item(v, step_name).get("status") == "IN_PROGRESS":
            return "ready"
        if any(w["status"] == "PENDING" for w in v["workitems"]):
            return "stuck"
        return None
    state = r.wait(timeout, probe, every=3)
    return state or "timeout", last


def _c_wait_end(r, pid: str, timeout: float) -> dict:
    return r.wait(timeout, lambda: (v := _c_view(r, pid))["instance"]["status"] != "RUNNING" and v, every=3) or _c_view(r, pid)


def _c_decision(r, view: dict) -> dict:
    did = _c_vars(view["instance"]).get("decision_id")
    return r.get(f"{r.process}/api/decisions/{did}") if did else {}


def _c_card(dec: dict) -> dict:
    """추천 카드 요약 — AI 3회 비교 키. 근거는 「어느 후보가 어떤 규칙으로 제외됐나」(값 · 순서가 아닌 판단 구조)."""
    opts = {o["id"]: o for o in dec.get("options") or []}
    rec = opts.get(dec.get("recommended")) or {}
    eco = rec.get("economicComparison") or {}
    win = rec.get("window") or {}
    return {"recommended": dec.get("recommended"), "approver": (rec.get("approver") or {}).get("id"),
            "evidence": sorted(f"{oid}:{'허용' if o.get('feasible') else '제외'}:{','.join(sorted(v.get('rule') or '' for v in o.get('violations') or []))}"
                               for oid, o in opts.items()),
            "window": win.get("label") or ("즉시" if win.get("immediate") else None),
            "supplier": eco.get("supplier"), "qty": eco.get("quantity"), "amount": eco.get("total_cost")}


def _c_me(r, user_id: str):
    """[내 작업함] → 「나」 고르기(이 브라우저가 기억한다). 승인 · 거절은 「나」가 있어야 된다(instances.js P5)."""
    r.tab("inbox")
    sel = r.page.locator("select[data-inbox-me]")
    r.wait(20, lambda: sel.locator(f"option[value='{user_id}']").count() > 0, every=0.5)
    sel.select_option(user_id)
    r.page.wait_for_timeout(1200)


def _c_open_task(r, pid: str, task_id: str):
    """[내 작업함]의 그 단계 줄을 누른다(주소 #/instances/<pid>/task/<tid>). 줄이 아직 없으면 같은 주소로 연다 — 알림 링크와 같은 길."""
    r.tab("inbox")
    link = r.page.locator(f"a.item[data-inbox-link*='{task_id}']")
    if r.wait(20, lambda: link.count() > 0, every=1):
        link.first.click()
    else:
        r.page.evaluate("h => { location.hash = h }", f"#/instances/{pid}/task/{task_id}")
    r.page.wait_for_selector("#todoPanel section.todo-panel", timeout=30_000)
    r.wait(30, lambda: "불러오는 중" not in r.page.locator("#todoPanel").inner_text(), every=0.5)
    r.page.wait_for_timeout(2500)        # 「나」를 바꾼 뒤 열면 처리 건 화면이 다음 갱신(2초)에 새 「나」로 다시 그린다 — 그 전 버튼을 누르지 않는다


def _c_panel_msg(r) -> str:
    loc = r.page.locator("#todoPanel .form-actions .form-msg")
    return loc.first.inner_text().strip() if loc.count() else ""


def _c_card_decide(r, pid: str, task: dict, approve: bool, reason: str = "") -> tuple[bool, str]:
    """조치 카드 승인 · 거절 패널에서 [승인] 또는 사유 + [거절]. 예측이 오래돼 거절되면 [미리 보기] 뒤 다시 [승인](20배속 90초)."""
    _c_open_task(r, pid, task["id"])
    if reason:
        r.page.fill("#tdReason", reason)
    if not approve:
        r.page.click("#tdRejectCard")
    else:
        go = r.page.locator("#tdGo")
        if go.is_disabled():
            return False, _c_panel_msg(r) or "승인 버튼이 꺼져 있음"
        go.click()
        r.page.wait_for_timeout(2500)
        if r.page.locator("#tdPreviewNow").count():                       # 「새 카드 검토가 필요」 — 화면이 [미리 보기]를 승인 옆에 꺼낸다
            r.page.click("#tdPreviewNow"); r.page.wait_for_timeout(4000)
            r.page.locator("#tdGo").click()
    done = r.wait(60, lambda: _c_item(_c_view(r, pid), task["activity_name"]).get("status") in ("DONE", "COMPLETED", "CANCELLED"), every=2)
    return bool(done), _c_panel_msg(r)


def _c_mail(r, addr: str) -> list[dict]:
    q = urllib.parse.quote(f"to:{addr}")
    return (r.get(f"{r.inbucket}/api/v1/search?query={q}&limit=50") or {}).get("messages") or []


def _c_ent(r) -> dict:
    return r.get(f"{r.enterprise}/api/state")


def _c_unit(r, asset: str, act: str) -> str:
    """[결함 시뮬레이션] 설비 카드의 버튼 → 결과 줄(#scenarioMsg)."""
    r.tab("scenario")
    r.page.wait_for_selector(f"#units .unit[data-asset='{asset}'] button[data-act='{act}']")
    before = r.page.locator("#scenarioMsg").inner_text()
    r.page.locator(f"#units .unit[data-asset='{asset}'] button[data-act='{act}']").first.click()
    r.wait(30, lambda: (t := r.page.locator("#scenarioMsg").inner_text().strip()) and t != before and not t.endswith("처리 중…"), every=0.5)
    return r.page.locator("#scenarioMsg").inner_text().strip()


def _c_biz_chip(r, asset: str) -> str:
    r.tab("scenario")
    r.page.wait_for_timeout(2500)                                         # 시나리오 상태는 폴링으로 다시 읽힌다
    return r.page.locator(f"#units .unit[data-asset='{asset}'] .biz-alert").inner_text().strip()


def _c_build_flow(r, kind: str, base_id: str) -> dict:
    """정상 경로만으로 그림 → 가져오기 → mapping.json 대로 입력 → 검사 → 등록 → 배포. 앞 실습 없이 혼자 돌 때도 쓴다."""
    def_id = _c_free_id(r, base_id)
    xml, ids, names = _c_spec_xml(kind, def_id)
    msg, ok = _c_import(r, xml, f"{def_id}.bpmn", def_id)
    r.check(f"{kind} 그림 가져오기(bpmn.io 꼴 id · 좌표)", ok, msg)
    _c_fill_cooling_like(r, kind, names)
    passed, problems, deps = _c_check(r)
    r.check(f"{kind} 사전 검사 통과", passed, "; ".join(problems) or deps)
    reg, text, ver = _c_register(r)
    r.check(f"{kind} 판본 등록", reg, text)
    dep, dtext = _c_deploy(r, def_id, ver or "1") if reg else (False, "등록 실패로 배포하지 않음")
    r.check(f"{kind} 배포", dep, dtext)
    route = _c_routes(r).get(C_SPECS[kind]["pattern"]) or {}
    r.check(f"{kind} 경보 경로 = 내가 배포한 흐름", route.get("definition") == def_id and route.get("source") == "내가 배포한 흐름", json.dumps(route, ensure_ascii=False))
    return {"def_id": def_id, "version": ver or "1", "names": names, "ids": ids}


# ====================================================================== 09 · 등록된 실행 흐름 비교 (최신 실라버스 통합 31 · 실전 68)
_C_CLASS_STEPS = {"c3_cooling": ("T_agent", "T_approve", "T_cmd", "T_reobs"), "c3_pm": ("T_agent", "T_approve", "T_wo"),
                  "c3_spare": ("T_agent", "T_approve", "T_po", "T_gr")}


def _c_class_definition(r, did: str) -> dict:
    route = next((x for x in r.get(f"{r.process}/api/flows/deployments").get("routes") or [] if x.get("definition") == did), {})
    return r.get(f"{r.process}/api/process/definitions/{did}?version={urllib.parse.quote(str(route.get('version') or '1'))}")


@lab("09", "9-3 · 6-5/6-6 BPMN 비교 — bpmn.io 그림과 포털에 등록된 수업 흐름의 시작 · 에이전트 · 승인 · 명령 · 재관측 연결 (기본 잠금: 학생 등록 막힘)")
def lab_09_flow_import(r):
    """최신 실라버스: 학생은 bpmn.io 로 그리고 등록된 기준 흐름과 비교한다. 기본 잠금은 흐름 등록 · 배포를 막는다(교대 실습만 연다)."""
    routes = _c_routes(r)
    want = {"COOLER_DEGRADATION": "c3_cooling", "PM_DUE": "c3_pm", "SPARE_BELOW_MIN": "c3_spare"}
    r.check("경보 경로: 쿨러 · 정기 점검 · 재고 부족 → 준비된 수업 흐름", all((routes.get(k) or {}).get("definition") == v and (routes.get(k) or {}).get("class_flow") is True
            for k, v in want.items()), json.dumps({k: (routes.get(k) or {}).get("definition") for k in want}, ensure_ascii=False))
    for did, steps in _C_CLASS_STEPS.items():
        d = _c_class_definition(r, did)
        acts = {x.get("id"): x for x in d.get("activities") or []}
        r.check(f"{did}: 등록 흐름에 비교할 작업이 있다({', '.join(steps)})", all(s in acts for s in steps),
                ", ".join(f"{s}={(acts.get(s) or {}).get('name')}" for s in steps))
        approve = acts.get("T_approve") or {}
        r.check(f"{did}: 승인 단계에 담당 역할이 정해져 있다", bool(approve.get("role") or approve.get("roles") or approve.get("lane")),
                json.dumps({k: approve.get(k) for k in ("role", "roles", "lane")}, ensure_ascii=False), kind="quality")
    r.page.wait_for_selector(".rail nav button[data-tab='flows']")
    flows_btn = r.page.locator(".rail nav button[data-tab='flows']")
    r.check("기본 잠금: 「흐름」 메뉴는 꺼져 있고 이유를 알린다", flows_btn.is_disabled() and bool(flows_btn.get_attribute("title")),
            flows_btn.get_attribute("title") or "", kind="exception")
    code, body = r.api("POST", f"{r.process}/api/flows/import", {"xml": "<definitions/>", "filename": "diagram.bpmn"})
    detail = (body or {}).get("detail", "") if isinstance(body, dict) else str(body)
    ok, why = r.human_message(detail)
    r.check("화면 밖 흐름 가져오기 · 등록도 서버가 거절(403 · 한국어)", code == 403 and ok, f"{code} {why}", kind="exception")
    r.check("거절 뒤 경보 경로는 그대로", _c_routes(r) == routes, kind="exception")


# ====================================================================== 10 · 실제 설비 이벤트의 처리 이력 (최신 실라버스 통합 32 · 실전 69)
@lab("10", "9-4 · 6-7 처리 이력 — 준비된 A 처리 건의 판단 → 운전원 승인 → 명령 → 재관측 → 보고를 처리 기록에서 따라가기")
def lab_10_run_my_flow(r):
    """02 에서 끝낸 A 처리 건을 학생이 처리 기록으로 따라간다(새 AI 호출 없음). 02 가 없으면 판정하지 않는다."""
    cards = [c for c in r.memo.get("02_cards") or [] if c.get("pid") and c.get("end")]
    if not cards:
        r.check("앞 실습(02)의 A 처리 건이 있다", False, "02 를 먼저 돌려야 한다(이 실습은 새 처리 건을 만들지 않는다)")
        return
    pid = cards[0]["pid"]
    view = _c_view(r, pid)
    rows = _a_rows(view)
    names = {x["id"]: x.get("name") for x in view["definition"].get("activities") or []}
    done = [k for k in ("T_agent", "T_approve", "T_cmd", "T_reobs") if (rows.get(k) or {}).get("status") in ("DONE", "COMPLETED")]
    r.check("처리 건 상태: 판단 · 승인 · 명령 · 재관측이 모두 끝났다", len(done) == 4 and view["instance"]["status"] == "COMPLETED",
            f"{view['instance']['status']} · 끝난 단계 {done}")
    r.tab("instances"); r.page.locator("#instReload").click(); r.page.wait_for_timeout(1200)
    # 같은 이름의 처리 건이 여럿이다(02 승인 · 08 거절) — 처리 건 id 로 고른다
    card = r.page.locator(f"#instList .inst-card[data-inst='{pid}']").first
    if not card.count():
        r.check("처리 건 목록에서 A 처리 건을 찾는다", False, view["instance"].get("proc_inst_name") or pid); return
    card.click()
    r.page.wait_for_selector("#instDetail [data-inst-tab='record']")
    r.page.locator("#instDetail [data-inst-tab='record']").click(); r.page.wait_for_timeout(1500)
    rec = r.page.locator("#instDetail").inner_text()
    want = [names.get(k) for k in ("T_agent", "T_approve", "T_cmd", "T_reobs") if names.get(k)]
    order = [rec.find(w) for w in want]
    r.check("처리 기록에 단계가 순서대로 보인다(판단 → 승인 → 명령 → 재관측)", all(i >= 0 for i in order) and order == sorted(order),
            ", ".join(f"{w}@{i}" for w, i in zip(want, order)))
    r.check("처리 기록에 승인한 사람이 이름으로 보인다", any(n in rec for n in ("김운전", "이생산")), rec[:300])
    r.check("처리 기록에 결과 보고가 보인다", "결과 보고" in rec or "정상" in rec or "미달" in rec, rec[-300:])


# ====================================================================== 11 · 10-2 · 7-2 정기 점검 (B)
def _c_biz_round(r, kind: str, asset: str, person: str, *, check_effects) -> list[dict]:
    """B · C 공통: 내 흐름 배포 → AI 3회(같은 입력) — 1회 거절(효과 없음), 2회 승인(효과), 3회 「이미 처리됨」 거절 → [초기화] → 다시 → 거절.
    check_effects(stage, before, view) 가 업무 DB · 메일함을 판정한다."""
    sp = C_SPECS[kind]
    # 최신 실라버스(통합 33 · 35, 실전 70 · 72): 포털의 준비된 시나리오 B · C 를 실행한다. 학생 흐름 등록은 기본 잠금이 막는다.
    did = {"pm": "c3_pm", "spare": "c3_spare"}[kind]
    acts = {x.get("id"): x.get("name") for x in _c_class_definition(r, did).get("activities") or []}
    names = {"P": acts.get("T_approve")}
    if not names["P"]:
        r.check(f"{sp['name']}: 준비된 흐름의 승인 단계를 읽었다", False, json.dumps(acts, ensure_ascii=False)[:300]); return []
    _c_me(r, person)

    def run_once(i):
        rec: dict = {}
        if i == 2:
            # 승인으로 처리된 뒤 다시 누르면 거절 — [초기화]로 수업 시작값
            msg = _c_unit(r, asset, "biz-start")
            ok_h, why = r.human_message(msg.replace("실패: ", ""))
            r.check(f"{sp['name']}: 처리된 뒤 다시 누르면 「이미 처리됐습니다 · [초기화]」", msg.startswith("실패:") and "초기화" in msg and ok_h, why, kind="exception")
            msg = _c_unit(r, asset, "biz-reset")
            r.check(f"{sp['name']}: [초기화] → 업무 데이터를 수업 시작값으로", "초기화" in msg and not msg.startswith("실패:"), msg, kind="exception")
            chip = _c_biz_chip(r, asset)
            r.check(f"{sp['name']}: [초기화] 뒤 표시가 다시 켜진다", chip in ("정기 점검 도래", "재고 보충 필요"), chip, kind="exception")
        before = _c_instance_ids(r)
        ent0 = _c_ent(r)
        msg = _c_unit(r, asset, "biz-start")
        inst = _c_new_instance(r, before, None, 60)
        if not inst:
            return {"error": f"처리 건이 열리지 않음: {msg}"}
        rec["definition"] = inst["proc_def_id"]
        t0 = time.monotonic()
        state, view = _c_wait_step(r, inst["proc_inst_id"], names["P"], C_AI_WAIT_S)
        rec["seconds"] = round(time.monotonic() - t0, 1)
        if state != "ready":
            return dict(rec, error=f"승인 차례가 오지 않음({state})")
        card = _c_card(_c_decision(r, view))
        rec.update(card)
        task = _c_item(view, names["P"])
        approver_user = C_PEOPLE.get(card["approver"] or "", person)
        if approver_user != person:
            _c_me(r, approver_user)
        if i == 1:
            if r.ai_runs < 3:   # 한 번만 돌릴 때도 사유 없는 [거절]이 막히는지 승인 전에 본다(제출되지 않는 화면 검사)
                _c_open_task(r, inst["proc_inst_id"], task["id"])
                r.page.fill("#tdReason", "")
                r.page.click("#tdRejectCard"); r.page.wait_for_timeout(600)
                ok_h, why = r.human_message(_c_panel_msg(r))
                r.check(f"{sp['name']}: 사유 없이 [거절] → 「거절 사유를 1~2000자로」", ok_h and "사유" in why, why, kind="exception")
            ok_d, pmsg = _c_card_decide(r, inst["proc_inst_id"], task, approve=True, reason=f"실습 {sp['name']} 승인")
        else:
            if i == 0:   # 거절 사유 없이 [거절] → 화면이 막고 사람 글
                _c_open_task(r, inst["proc_inst_id"], task["id"])
                r.page.fill("#tdReason", "")
                r.page.click("#tdRejectCard"); r.page.wait_for_timeout(600)
                ok_h, why = r.human_message(_c_panel_msg(r))
                r.check(f"{sp['name']}: 사유 없이 [거절] → 「거절 사유를 1~2000자로」", ok_h and "사유" in why, why, kind="exception")
            ok_d, pmsg = _c_card_decide(r, inst["proc_inst_id"], task, approve=False, reason="실습: 이번 회차는 보류합니다")
        if approver_user != person:
            _c_me(r, person)
        fin = _c_wait_end(r, inst["proc_inst_id"], 300)
        rec["outcome"] = (_c_vars(fin["instance"]).get("result_report") or {}).get("outcome")
        check_effects("approve" if i == 1 else "reject", ent0, fin, i)
        return rec

    runs = r.repeat3(f"{sp['name']} 판단 · 제안", run_once, ("definition", "recommended", "approver", "evidence") + (
        ("window",) if kind == "pm" else ("supplier", "qty", "amount")), limit_s=C_AI_LIMIT_S, single=1)
    ok_outcome = "정상" if kind == "pm" else "입고 완료"
    r.check(f"{sp['name']}: 처리 건이 모두 준비된 수업 흐름으로 열렸다", all(x.get("definition") == did for x in runs), str([x.get("definition") for x in runs]))
    r.check(f"{sp['name']}: 카드 승인 역할 = 흐름 승인 담당({sp['approver']})", all(x.get("approver") == C_ROLE_NAME[sp["approver"]] for x in runs if not x.get("error")),
            str([x.get("approver") for x in runs]), kind="ai3")
    r.check(f"{sp['name']}: 거절 → 반려, 승인 → 정상 종결", [x.get("outcome") for x in runs] == (["반려", ok_outcome, "반려"] if r.ai_runs >= 3 else [ok_outcome]),
            str([x.get("outcome") for x in runs]))
    route = _c_routes(r).get(sp["pattern"]) or {}
    r.check(f"{sp['name']}: 실행 뒤에도 경보 경로는 준비된 수업 흐름", route.get("definition") == did and route.get("class_flow") is True, json.dumps(route, ensure_ascii=False))
    return runs


@lab("11", "10-2 · 7-2 정기 점검 — 준비된 시나리오 B: [정기 점검] → 정비 계획 제안 → 설비보전팀장 승인 → 정비 오더 · 생산 공지 · 보고 / 반려 시 오더 없음")
def lab_11_pm(r):
    def effects(stage, ent0, fin, i):
        v = _c_vars(fin["instance"])
        ent1 = _c_ent(r)
        wo0, wo1 = len(ent0["cmms"]["work_orders"]), len(ent1["cmms"]["work_orders"])
        mails = _c_mail(r, C_MAILS["production"])
        if stage == "reject":
            r.check(f"B {i + 1}회 반려 → CMMS 정비 오더가 생기지 않는다", wo1 == wo0 and not (v.get("work_order") or {}).get("ref"), f"{wo0}→{wo1}", kind="exception")
            r.check(f"B {i + 1}회 반려 → 생산팀 공지 메일 없음(이번 처리 건 오더 번호로)", not any((v.get("work_order") or {}).get("ref", "@@") in (m.get("Subject") or "") for m in mails),
                    str(len(mails)), kind="exception")
            pm = r.get(f"{r.enterprise}/cmms/pm_status?asset=HYD-02")["facts"]
            r.check(f"B {i + 1}회 반려 → 정기 점검 도래 표시는 그대로", pm.get("pm_alert") is True, json.dumps({k: pm.get(k) for k in ("pm_alert", "pm_planned_wo")}), kind="exception")
            r.check(f"B {i + 1}회 반려 → 카드 머리 칩 「반려」", _c_biz_chip(r, "HYD-02") == "반려", "", kind="exception")
        else:
            ref = (v.get("work_order") or {}).get("ref")
            r.check("B 승인 → CMMS 정비 오더 1건(처리 건의 오더 번호와 같음)", wo1 == wo0 + 1 and bool(ref) and any(ref in json.dumps(w, ensure_ascii=False) for w in ent1["cmms"]["work_orders"]),
                    f"{wo0}→{wo1} ref={ref}")
            subj = [m.get("Subject") for m in mails if ref and ref in (m.get("Subject") or "")]
            r.check("B 승인 → 생산팀 공지 메일(메일함, 제목에 오더 번호)", bool(subj), str(subj or [m.get("Subject") for m in mails][:3]))
            pm = r.get(f"{r.enterprise}/cmms/pm_status?asset=HYD-02")["facts"]
            r.check("B 승인 → 정기 점검 도래 표시가 꺼짐(이번 회차 오더 있음)", pm.get("pm_alert") is False, json.dumps({k: pm.get(k) for k in ("pm_alert", "pm_planned_wo")}))
            r.check("B 승인 → 카드 머리 칩 「처리됨 · 정상」", "처리됨" in _c_biz_chip(r, "HYD-02"), "")
    _c_biz_round(r, "pm", "HYD-02", "user:park-maint", check_effects=effects)


@lab("12", "10-4 · 7-4 구매 — 준비된 시나리오 C: [재고 보충] → 발주안 제안 → 구매 담당 승인 → ERP 발주 · 공급사 메일 · 입고 · 재고 반영 / 거절 시 발주 차단")
def lab_12_spare(r):
    def effects(stage, ent0, fin, i):
        v = _c_vars(fin["instance"])
        ent1 = _c_ent(r)
        pr0, pr1 = len(ent0["erp"]["purchase_requests"]), len(ent1["erp"]["purchase_requests"])
        gr0, gr1 = len(ent0["erp"]["goods_receipts"]), len(ent1["erp"]["goods_receipts"])
        stock = r.get(f"{r.enterprise}/erp/spare_stock?part=P-PMP-SEAL")["facts"]
        if stage == "reject":
            r.check(f"C {i + 1}회 거절 → ERP 발주 · 입고 없음", pr1 == pr0 and gr1 == gr0 and not v.get("purchase_order"), f"PR {pr0}→{pr1} GR {gr0}→{gr1}", kind="exception")
            r.check(f"C {i + 1}회 거절 → 승인 값(approved_*)이 비어 있다", not any(v.get(k) for k in ("approved_supplier", "approved_qty", "approved_amount")),
                    json.dumps({k: v.get(k) for k in ("approved_supplier", "approved_qty", "approved_amount")}, ensure_ascii=False), kind="exception")
            r.check(f"C {i + 1}회 거절 → 재고 보충 필요 표시 그대로", stock.get("below_reorder_point") is True, json.dumps(stock, ensure_ascii=False)[:200], kind="exception")
        else:
            po = v.get("purchase_order") or {}
            ref = po.get("ref")
            r.check("C 승인 → ERP 발주 1건 · 입고 1건", pr1 == pr0 + 1 and gr1 == gr0 + 1 and bool(ref), f"PR {pr0}→{pr1} GR {gr0}→{gr1} ref={ref}")
            sup = [m.get("Subject") for m in _c_mail(r, C_MAILS["supplier"]) if str(v.get("approved_qty")) in (m.get("Subject") or "")]
            rcv = _c_mail(r, C_MAILS["receiving"])
            r.check("C 승인 → 공급사 · 입고 부서 메일(메일함)", bool(sup) and bool(rcv), f"supplier={sup[:2]} receiving={len(rcv)}")
            r.check("C 승인 → 재고 반영(재주문점 이상, 표시 꺼짐)", stock.get("below_reorder_point") is False and (stock.get("available") or 0) >= (stock.get("reorder_point") or 0),
                    json.dumps({k: stock.get(k) for k in ("on_hand", "available", "on_order", "reorder_point")}))
            r.check("C 승인 → 결과 보고 「입고 완료」 · 카드 칩 「처리됨」", (v.get("result_report") or {}).get("outcome") == "입고 완료" and "처리됨" in _c_biz_chip(r, "HYD-03"), "")
    _c_biz_round(r, "spare", "HYD-03", "user:jung-buy", check_effects=effects)


# ====================================================================== 13 · 두 과정 마지막 적용 — 교대 인수인계
def _h_submit(r, pid, task, user, values, *, expect_done=True):
    """교대 검토는 실제 작업함 폼으로 제출한다. 인수 확인과 정비 완료를 구분한다."""
    _c_me(r, user)
    _c_open_task(r, pid, task['id'])
    form = task.get('form') or {}
    if not form:
        form = r.get(f"{r.process}/api/todolist/{task['id']}").get('form') or {}
    for index, field in enumerate(form.get('fields_json') or []):
        if field['key'] not in values:
            continue
        value = values[field['key']]
        control = r.page.locator(f'#tdField{index}')
        if field['type'] in ('select', 'boolean'):
            control.select_option(str(value).lower() if isinstance(value, bool) else str(value))
        else:
            control.fill(str(value))
    r.page.click('#tdDone')
    if not expect_done:
        r.wait(15, lambda: '설비 조치' in _c_panel_msg(r), every=.5)
        return _c_panel_msg(r)
    return bool(r.wait(45, lambda: _c_item(_c_view(r, pid), task['activity_name']).get('status') == 'DONE', every=2))


def _h_unlock(r) -> bool:
    """마지막 날: 학생이 포털의 「수업 기능」에서 강사 해제 코드를 입력한다(잘못된 코드는 거절). 이미 열려 있으면 그대로 둔다."""
    page = r.page
    if r.get(f"{r.process}/api/course-access").get("unlocked"):
        return True
    if not r.unlock_code:
        r.check("강사 해제 코드로 교대 실습 열기", False, "--unlock-code-file 이 없어 교대 실습을 열 수 없다"); return False
    message = page.locator("#courseUnlockMessage")
    page.locator("#courseAccessPanel summary").click()
    page.fill("#courseUnlockCode", "HYD1.wrong.code-not-signed-by-the-instructor")
    page.click("#courseUnlockGo")
    r.wait(10, lambda: "올바르지" in message.inner_text(), every=0.3)
    ok, why = r.human_message(message.inner_text())
    r.check("잘못된 해제 코드 → 거절 · 한국어", ok and "올바르지" in why and not r.get(f"{r.process}/api/course-access").get("unlocked"), why, kind="exception")
    page.fill("#courseUnlockCode", r.unlock_code)
    page.click("#courseUnlockGo")
    # 서버 저장과 화면 안내는 순서대로 오지 않는다(fresh 실행: 서버는 열렸는데 직전 거절 문구를 읽음) — 둘 다 기다린다
    opened = r.wait(15, lambda: r.get(f"{r.process}/api/course-access").get("unlocked") is True and "열렸습니다" in message.inner_text(), every=0.5)
    r.check("강사 해제 코드 → 교대 실습 열림(화면 안내)", bool(opened), message.inner_text())
    if not opened:
        return False
    page.reload(); page.wait_for_timeout(2000)
    return True


@lab("13", "마지막 적용 · 교대 인수인계 — 보충 자료 → 새 에이전트·스킬 → 두 사람 검토·보완·확인")
def lab_13_shift_handover(r):
    import hashlib
    import xml.etree.ElementTree as ET
    page = r.page
    if not _h_unlock(r):
        return
    # 이미 검토·적재한 동일 승인 자료는 재사용한다. 수업 전체를 초기화하지 않는다.
    before = {x['filename']: x['batch'] for x in r.get(f'{r.process}/api/kg/manuals') if x.get('current')}
    _B_DOC_FILES['HI-01'] = 'HI-01_shift-inspection-supplement.md'
    current = _b_current_batch(r, 'HI-01')
    expected_hash = hashlib.sha256((_B_DOC_DIR / _B_DOC_FILES['HI-01']).read_bytes()).hexdigest()
    if not current or current.get('source_id', '').rsplit(':', 1)[-1] != expected_hash:
        source = _b_preview_file(r, 'HI-01')
        if not source:
            r.check('교대 보충 매뉴얼 미리보기', False); return
        extracted = _b_run_extraction(r, 'HI-01', source, 0)
        r.check('교대 보충 매뉴얼 1회 추출', not extracted.get('error'), extracted.get('error') or '')
        if extracted.get('error'): return
        proposal = _b_extraction(r, source, extracted['instance'])[1].get('preview') or {}
        r.check('교대 보충 절차 원문 대조', not extracted['quality'], str(extracted['quality']), kind='quality')
        if extracted['quality']: return
        _b_apply_review(r, 'HI-01', proposal)
        committed, message = _b_commit(r, 'HI-01')
        r.check('보충 자료를 새 문서로 적재', committed, message)
        if not committed: return
    after = {x['filename']: x['batch'] for x in r.get(f'{r.process}/api/kg/manuals') if x.get('current')}
    r.check('보충 자료 추가가 기존 제조 지식을 초기화하지 않음',
            all(after.get(name) == batch for name, batch in before.items() if name != _B_DOC_FILES['HI-01']), kind='quality')

    # 스킬 · 에이전트 이름만 새로 짓는다(흐름은 ShiftHandover 의 새 판본) — 다시 돌린 PC에서도 이름이 겹치지 않게
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
    if not saved: return
    page.locator('[data-ag-tab="agents"]').click(); page.locator('[data-new-agent]').click()
    page.locator(f'[data-f-skill][value="{skill}"]').check()
    page.locator('[data-f="work_rules"]').select_option('hyd-handover')
    agent_name = '교대 인수인계 ' + sid
    error = _b_agent_form(r, name=agent_name, role='인계안 작성 담당',
        goal='승인된 보충 매뉴얼과 현재 설비·정비·ERP를 대조하여 다음 교대가 확인하고 이어갈 일을 작성한다.',
        persona='불일치와 정보 부족을 숨기지 않고 조회 근거를 남긴다.', model='', tools=['neo4j', 'enterprise', 'hyd-dmn'])
    r.check('학생 교대 에이전트 저장', not error, error)
    mine = next((a for a in _b_agents(r) if a.get('name') == agent_name), None)
    if error or not mine: return

    folder = ROOT/'it/process/definitions'
    xml = (folder/'shift_handover.bpmn').read_text(encoding='utf8')
    mapping = json.loads((folder/'shift_handover.mapping.json').read_text(encoding='utf8'))
    elements = {e.get('id'): e for e in ET.fromstring(xml).iter() if e.get('id')}
    # 안내.html 4절: 흐름 ID는 제공 파일의 ShiftHandover 를 유지한다 — 칸을 비우면 그림의 프로세스 id 다
    message, ok = _c_import(r, xml, 'handover.bpmn', '')
    r.check('교대 BPMN 가져오기', ok, message)
    if not ok: return
    _c_apply_start(r, mapping['start'])
    for key, item in mapping['tasks'].items():
        value = dict(item)
        if 'agent' in value: value['agent'] = mine['id']
        _c_apply_task(r, elements[key].get('name'), value)
    for key, value in mapping['flows'].items():
        flow = elements[key]
        _c_apply_branch(r, elements[flow.get('sourceRef')].get('name'), elements[flow.get('targetRef')].get('name'), value, flow_id=key)
    passed, problems, dependencies = _c_check(r)
    r.check('교대 시작 폼·역할·작업·분기 검사', passed, '; '.join(problems) or dependencies)
    if not passed: return
    registered, message, version = _c_register(r)
    r.check('교대 별도 정의·판본 등록', registered, message)
    if not registered: return
    did = 'ShiftHandover'
    _c_me(r, 'user:kim-op'); r.tab('flows')
    page.locator(f"[data-start='{did}'][data-version='{version}']").click()
    box = page.locator(f"[data-startbox='{did}@{version}']")
    values = dict(asset='HYD-01', shift_label='다음 교대', as_of=datetime.now(timezone.utc).isoformat(),
                  work_notes='작업 메모: 정비 완료라고 전달받음. 부품 도착 예정이라고 전달받음. 실제 열린 작업지시와 현재 재고를 대조해야 함.')
    for key, value in values.items(): box.locator(f"[data-sv='{key}']").fill(value)
    known = _c_instance_ids(r); box.locator('[data-go]').click()
    inst = _c_new_instance(r, known, did, 30)
    r.check('교대 시작 폼으로 한 처리 건 시작', bool(inst))
    if not inst: return
    pid = inst['proc_inst_id']
    for suffix in ('', ' · 보완 1'):
        name = '인계자 검토' + suffix
        state, view = _c_wait_step(r, pid, name, C_AI_LIMIT_S)
        r.check('교대 AI 조회·인계안 작성'+suffix, state == 'ready', state)
        if state != 'ready': return
        data = _c_vars(view['instance'])
        r.check('4영역과 실제 조회 근거 유지'+suffix,
                {c.get('area') for c in data.get('checks', [])} == {'equipment','work_orders','parts','work_notes'}
                and bool(data.get('evidence')), kind='quality')
        if not _h_submit(r, pid, _c_item(view, name), 'user:kim-op',
                         dict(sender_decision='approve', sender_notes='미확인 사항과 원문 조회 근거를 인수자에게 전달합니다.')):
            r.check('인계자 검토 제출'+suffix, False); return
        state, view = _c_wait_step(r, pid, '인수자 확인'+suffix, 30)
        r.check('별도 인수자 차례'+suffix, state == 'ready')
        if state != 'ready': return
        task = _c_item(view, '인수자 확인'+suffix)
        if not suffix:
            ok = _h_submit(r, pid, task, 'user:choi-op', dict(receiver_decision='revise',
                receiver_notes='정비 완료 메모와 열린 작업지시, 입고 예정과 실제 재고를 구분해 다시 확인해 주세요.', communication_only=False))
            r.check('인수자 보완 요청 → 같은 처리 건의 재작성', ok)
            if not ok: return
        else:
            message = _h_submit(r, pid, task, 'user:choi-op', dict(receiver_decision='confirm', receiver_notes='인수 내용 확인', communication_only=False), expect_done=False)
            r.check('설비 조치 완료와 혼동한 확인은 거절', '설비 조치' in message, message, kind='exception')
            ok = _h_submit(r, pid, task, 'user:choi-op', dict(receiver_decision='confirm',
                receiver_notes='인계를 확인하고 미확인 항목은 다음 교대에서 이어 확인합니다.', communication_only=True))
            r.check('인수자가 인계 확인을 기록', ok)
            if not ok: return
    view = _c_wait_end(r, pid, 30)
    end_ids = {e['id'] for e in view['definition']['events'] if e.get('name') == '인수 확인 기록 완료'}
    r.check('인수 확인 종료 기록', view['instance']['status'] == 'COMPLETED' and view['instance'].get('end_event') in end_ids)
    r.check('인계 확인이 설비·발주·정비 실행을 만들지 않음', not view.get('effects'), kind='quality')
    r.memo['c_handover'] = dict(def_id=did, version=version, instance=pid, agent=mine['id'], skill=skill)


# ====================================================================== 92 · B · C [초기화]
@lab("92", "그 밖에 — B · C [초기화](처리 건이 없을 때 · 진행 중일 때)")
def lab_92_biz_reset(r):
    for key, asset, label in (("B", "HYD-02", "정기 점검 도래"), ("C", "HYD-03", "재고 보충 필요")):
        _c_me(r, "user:park-maint" if key == "B" else "user:jung-buy")
        msg = _c_unit(r, asset, "biz-reset")
        r.check(f"{key} [초기화](대기 중) → 수업 시작값", "초기화" in msg and not msg.startswith("실패:"), msg)
        chip = _c_biz_chip(r, asset)
        r.check(f"{key} [초기화] 뒤 표시 「{label}」", label in chip, chip)
        press = r.page.locator(f"#units .unit[data-asset='{asset}'] .biz-press").inner_text()
        r.check(f"{key} 카드에 마지막 누름(누가 · 무엇)이 남는다", "[초기화]" in press, press)
        # 진행 중 [초기화]: 사용자 미정(6_남은_일.md 3절) — 지금 동작을 기록한다. 처리 건은 계속 가고 업무 값만 되돌린다(scenario_buttons 동작)
        before = _c_instance_ids(r)
        _c_unit(r, asset, "biz-start")
        inst = _c_new_instance(r, before, None, 60)
        if not inst:
            r.check(f"{key} [초기화] 시험용 처리 건이 열림", False, ""); continue
        msg = _c_unit(r, asset, "biz-reset")
        ok_h, why = r.human_message(msg.replace("실패: ", ""))
        still = _c_view(r, inst["proc_inst_id"])["instance"]["status"] == "RUNNING"
        r.check(f"{key} 진행 중 [초기화] → 사람 글 응답, 처리 건은 그대로 진행(지금 동작 · 막을지는 사용자 결정)", ok_h and still, why, kind="quality")
        # 뒤처리: 그 처리 건을 거절로 닫는다(열린 B · C 가 A 의 시나리오 시각 기준점을 붙잡지 않게 — scenario_buttons.may_reanchor)
        flow = r.get(f"{r.process}/api/instances/{urllib.parse.quote(inst['proc_inst_id'], safe='')}")
        approve_name = next((a["name"] for a in flow["definition"]["activities"] if a.get("tool") == "formHandler:select_card"), None)
        state, view = _c_wait_step(r, inst["proc_inst_id"], approve_name, C_AI_WAIT_S)
        if state == "ready":
            dec = _c_card(_c_decision(r, view))
            _c_me(r, C_PEOPLE.get(dec["approver"] or "", "user:park-maint"))
            _c_card_decide(r, inst["proc_inst_id"], _c_item(view, approve_name), approve=False, reason="초기화 시험 뒤 닫기")
        elif state == "stuck":                                             # AI 가 보류했다(사유는 처리 건 화면) — 학생은 [단계 닫기]로 닫는다(같은 API)
            held = next(w for w in view["workitems"] if w["status"] == "PENDING")
            print(f"    {key} 시험 처리 건 보류 사유: {str(held.get('log'))[:300]}", flush=True)
            r.api("POST", f"{r.process}/api/todolist/{held['id']}/close", {"by": "user:park-maint", "reason": "초기화 시험 뒤 닫기"})
        r.check(f"{key} 시험 처리 건을 화면에서 닫았다(거절 → 반려 종결 · 보류면 단계 닫기)", _c_wait_end(r, inst["proc_inst_id"], 120)["instance"]["status"] == "COMPLETED", state)


# ====================================================================== 93 · 펌프 · 팬 결함 + [다시 평가] (워커 모드)
def _c_fault_case(r, asset: str, fault: str, pattern: str):
    routes = _c_routes(r)
    expect_def = (routes.get(pattern) or {}).get("definition")
    r.check(f"{pattern} 경보 경로를 화면 표로 확인(기준 흐름이 연다)", expect_def == "anomaly_response" and (routes.get(pattern) or {}).get("reference") is True,
            json.dumps(routes.get(pattern), ensure_ascii=False))
    before = _c_instance_ids(r)
    injected = time.monotonic()
    # 화면에 펌프 · 팬 버튼이 없다(app.js EXPERIMENT 278-280: 쿨러 · B · C 만) → plant-sim 주입 API 로 보완(notes_C (e))
    got = r.api("POST", f"{r.plant}/api/fault", {"asset": asset, "type": fault})
    r.check(f"{asset} {fault} 주입(화면 버튼 없음 — API 보완)", got[0] == 200, str(got)[:200])
    inst = _c_new_instance(r, before, expect_def, 240)
    r.check(f"{pattern} → 처리 건이 기준 흐름으로 열림", bool(inst), "")
    if not inst:
        return
    pid = inst["proc_inst_id"]
    # 4단계 AI(원인 진단 → 후보 → 규정 → 순위) — 보류가 나면 [다시 평가]
    t0 = time.monotonic()
    state, view = _c_wait_step(r, pid, "조치 카드 선택 (HITL)", C_AI_WAIT_S)          # 기준 정의 task:select 이름 # 미확인(화면 이름은 「조치 선택」)
    held = [w for w in view.get("workitems", []) if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")]
    if held:
        w = held[0]
        r.tab("instances"); r.page.locator("#instReload").click(); r.page.wait_for_timeout(1200)
        r.page.locator("#instList .inst-card").filter(has_text=inst["proc_inst_name"]).first.click()
        panel = r.page.locator(f"#instDetail [data-deferral-task='{w['id']}']")
        panel.wait_for(timeout=30_000)
        r.check("보류 단계에 [다시 평가] 패널(보류 이유가 사람 글)", r.human_message(((w.get("draft") or {}).get("_deferral") or {}).get("reason", ""))[0],
                ((w.get("draft") or {}).get("_deferral") or {}).get("reason", "")[:200], kind="exception")
        # 예외 ①: 사유 없이 → 화면이 막음
        panel.locator("[data-reassess-reason]").fill("")
        panel.locator("[data-reassess]").click(); r.page.wait_for_timeout(500)
        ok_h, why = r.human_message(panel.locator(".form-msg").first.inner_text() if panel.locator(".form-msg").count() else "")
        r.check("[다시 평가] 사유 없이 → 필수 입력 안내", ok_h, why, kind="exception")
        # 예외 ②: 사유 2001자 → 서버 거절 문구가 사람 글인가(task_deferral._text 영문 — 의심 결함)
        panel.locator("[data-reassess-reason]").fill("가" * 2001)
        panel.locator("[data-reassess]").click(); r.page.wait_for_timeout(1500)
        ok_h, why = r.human_message(panel.locator(".form-msg").inner_text() if panel.locator(".form-msg").count() else "")
        r.check("[다시 평가] 너무 긴 사유 → 거절 문구가 한국어 사람 글", ok_h and not re.search(r"[A-Za-z]{4,} [a-z]{3,} [a-z]{3,}", why), why, kind="exception")   # final2: 영문 문장 + 한국어 꼬리가 통과했다
        # 새 2분 원천 창을 기다린 뒤(주입 뒤 125초 — scenario_pump_fan_test 와 같은 기준) 다시 평가
        time.sleep(max(0, 125 - (time.monotonic() - injected)))
        panel = r.page.locator(f"#instDetail [data-deferral-task='{w['id']}']")
        panel.locator("[data-reassess-reason]").fill("고장 주입 뒤 새 2분 관측 창으로 다시 평가합니다")
        panel.locator("[data-reassess]").click()
        r.check("[다시 평가] 접수 → 그 단계가 다시 돈다", bool(r.wait(30, lambda: _c_item(_c_view(r, pid), w["activity_name"]).get("status") != "PENDING", every=2)), "",
                kind="exception")
        state, view = _c_wait_step(r, pid, "조치 카드 선택 (HITL)", C_AI_WAIT_S)
    else:
        r.check("원인 진단이 보류 없이 끝남([다시 평가] 경로는 이번에 생기지 않음 — 그대로 기록)", state == "ready", state, kind="quality")
    ai_s = time.monotonic() - t0
    # 수업 지식(HM-8 · PM-02 · PR-07)에 이 고장의 완화 · 근본 조치가 없으면(PM-02 펌프는 예방 정비뿐) 판단 엔진이 NO_FEASIBLE_OPTION 이다 —
    # 그때 맞는 결과는 다시 평가해도 지어내지 않고 다시 보류하는 것(final2: 카드를 기대해 1119초 기다림)
    engine = r.api("POST", f"{r.agent}/api/agent/decide", {"asset": asset, "pattern": pattern, "facts": {}})[1] or {}
    if engine.get("status") == "NO_FEASIBLE_OPTION":
        again = next((w for w in view.get("workitems", []) if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")), None)
        reason = ((again or {}).get("draft") or {}).get("_deferral", {}).get("reason", "")
        ok_h, why = r.human_message(reason)
        r.check(f"{pattern}: 지식에 조치 후보 없음(판단 엔진) → 다시 평가해도 지어내지 않고 보류 · 사람 글", state == "stuck" and bool(again) and ok_h,
                f"{state} {ai_s:.0f}초 · {why}", kind="exception", seconds=ai_s)
        if again:
            r.api("POST", f"{r.process}/api/todolist/{again['id']}/close", {"by": "user:lee-prod", "reason": "수업 지식에 펌프 조치가 없어 닫음"})
        return
    r.check(f"{pattern}: AI 4단계 → 조치 선택 차례", state == "ready", f"{state} {ai_s:.0f}초", seconds=ai_s)
    if state != "ready":
        return
    dec = _c_decision(r, view)
    card = _c_card(dec)
    v = _c_vars(view["instance"])
    r.check(f"{pattern}: 원인 진단이 고장과 맞다", v.get("cause") == {"PUMP_LEAKAGE": "cause:pump-shaft-seal-wear"}.get(pattern),   # 수업용 기본 지식(PM-02)의 원인 id
            str(v.get("cause")), kind="quality")
    r.check(f"{pattern}: 추천 카드가 실행 가능(지는 대안 · 제외 규칙 함께)", bool(card["recommended"]) and len(card["evidence"]) > 1, json.dumps(card, ensure_ascii=False)[:400], kind="quality")
    task = _c_item(view, "조치 카드 선택 (HITL)")
    _c_me(r, C_PEOPLE.get(card["approver"] or "", "user:lee-prod"))
    ok_d, pmsg = _c_card_decide(r, pid, task, approve=True, reason="실습: 추천 조치를 승인합니다")
    r.check(f"{pattern}: 추천 조치 승인", ok_d, pmsg)
    fin = r.wait(420, lambda: (x := _c_view(r, pid))["instance"]["status"] != "RUNNING" and x
                 or (any(w["activity_id"] == "task:escalate" and w["status"] == "IN_PROGRESS" for w in x["workitems"]) and x), every=3) or _c_view(r, pid)
    esc = _c_item(fin, next((w["activity_name"] for w in fin["workitems"] if w["activity_id"] == "task:escalate"), "상급자 호출"))
    if esc.get("status") == "IN_PROGRESS":
        # 효과 확인에서 회복되지 않음 → 책임자 확인(생산관리자)이 화면에서 이어받는다
        _c_me(r, "user:lee-prod")
        _c_open_task(r, pid, esc["id"])
        r.page.locator("#todoPanel textarea, #todoPanel input[id^=tdField]").first.fill("회복되지 않아 다른 조치를 지시합니다")
        r.page.click("#todoPanel #tdDone")
        fin = _c_wait_end(r, pid, 120)
    end = fin["instance"].get("end_event")
    rec = _c_vars(fin["instance"]).get("recovered")
    r.check(f"{pattern}: 처리 건이 끝났고 끝 사건이 재관측과 맞다(회복 → ev:closed, 미회복 → ev:escalated)",
            fin["instance"]["status"] == "COMPLETED" and ((rec is True and end == "ev:closed") or (rec is False and end == "ev:escalated")),
            json.dumps({"end": end, "recovered": rec}, ensure_ascii=False))


@lab("93", "그 밖에 — 펌프 · 팬 결함 실험과 [다시 평가]를 워커 모드(AI)로")
def lab_93_pump_fan(r):
    mode = r.get(f"{r.process}/api/process/mode")
    r.check("워커 모드(AGENT_BRIDGE=off)", mode.get("agent_bridge") == "off", json.dumps(mode, ensure_ascii=False))
    r.tab("scenario")
    # 결함 시뮬레이션 화면에는 펌프 · 팬 결함 버튼이 없다(쿨러 · B · C 만) — 실라버스에 펌프 · 팬 실습이 없다(차이 있음, 유지). 주입은 설비 API 로 한다
    r.page.locator("#btnReset").click()
    r.page.wait_for_timeout(3000)
    r.check("[전체 초기화] → 설비를 정상 운전점으로", "초기화했습니다" in r.page.locator("#scenarioMsg").inner_text(), r.page.locator("#scenarioMsg").inner_text())
    # 펌프 내부 누설: PM-02 기본 지식(원인 · 증거)으로 진단 → (보류면 [다시 평가]) → 추천 → 승인 → 효과 확인
    _c_fault_case(r, "HYD-02", "pump_leakage", "PUMP_LEAKAGE")
    r.tab("scenario"); r.page.click("#btnReset"); r.page.wait_for_timeout(3000)
    # 팬 진동: 수업 문서 셋에는 팬 진동 고장 유형 · 원인이 없다(HM-8은 쿨러 냉각 상실의 원인으로만 팬 구동 불량을 다룬다) — 지어내지 않고
    # 보류하며 무엇이 없는지 사람 글로 말하는가
    before = _c_instance_ids(r)
    got = r.api("POST", f"{r.plant}/api/fault", {"asset": "HYD-03", "type": "fan_vibration"})
    inst = _c_new_instance(r, before, None, 240)
    r.check("팬 진동 주입 → 처리 건이 열림", got[0] == 200 and bool(inst), str(got)[:120])
    if inst:
        pid = inst["proc_inst_id"]
        held = r.wait(C_AI_WAIT_S, lambda: next((w for w in _c_view(r, pid)["workitems"] if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")), None), every=5)
        reason = ((held or {}).get("draft") or {}).get("_deferral", {}).get("reason", "")
        ok_h, why = r.human_message(reason)
        r.check("팬 진동(지식 없음) → 지어내지 않고 보류, 무엇이 없는지 사람 글", bool(held) and ok_h, why, kind="exception")
    r.tab("scenario"); r.page.click("#btnReset"); r.page.wait_for_timeout(3000)


# ---------------------------------------------------------------------- 실행
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / ".evidence/class-round" / time.strftime("%Y%m%d-%H%M%S")))
    ap.add_argument("--only", default="", help="쉼표로 고른 실습 번호만(예: 01,05)")
    ap.add_argument("--from", dest="start", default="", help="이 번호부터 끝까지")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--ai-runs", type=int, choices=(1, 3), default=3,
                    help="AI 단계 반복 수. 1 = 연속 수업 확인(반복 일치는 측정 안 함으로 남김)")
    ap.add_argument("--unlock-code-file", default="", help="강사 해제 코드가 든 파일(13 교대 실습). 코드는 출력 · 결과에 남기지 않는다")
    args = ap.parse_args(argv[1:])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    only = {c.strip() for c in args.only.split(",") if c.strip()}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR", accept_downloads=True)
        page = ctx.new_page()
        page.set_default_timeout(20_000)
        r = Round(page, out)
        r.ai_runs = args.ai_runs
        if args.unlock_code_file:
            r.unlock_code = Path(args.unlock_code_file).read_text(encoding="utf-8").strip()
        r.open()
        started = not args.start
        for code, title, fn in sorted(LABS, key=lambda x: x[0]):
            started = started or code == args.start
            if not started or (only and code not in only):
                continue
            r.lab = code
            print(f"\n== {code} {title}", flush=True)
            t0 = time.monotonic()
            try:
                fn(r)
            except Exception as e:
                r.check("실습이 끝까지 돌았다", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
            print(f"   ({time.monotonic() - t0:.0f}초)", flush=True)
        browser.close()
    rc = r.write()
    log_failures = sum(bool(v.console_errors or v.failed_requests) for v in r.logs.values())
    print(f"\n결과: {out}/summary.md (판정 실패 {sum(not v.ok for v in r.verdicts)}개 · 별도 콘솔/통신 오류 실습 {log_failures}개)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
