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
import urllib.request
from dataclasses import asdict, dataclass, field
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
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self._log().console_errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: self._on_failed(r.url, r.failure or "failed"))
        page.on("response", lambda r: r.status >= 500 and self._on_failed(r.url, f"HTTP {r.status}"))

    # ------------------------------------------------------------------ 기록
    def _log(self) -> LabLog:
        return self.logs.setdefault(self.lab, LabLog())

    def _on_console(self, msg):
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
        bad = re.search(r"Traceback|Exception|Error:|HTTP Error \d|\b[45]\d\d\b(?! ?(?:초|분|개|건|%))|undefined|null|NaN|\{\"", t)
        if bad:
            return False, f"사람 글이 아님({bad.group(0)}): {t[:200]}"
        if not re.search(r"[가-힣]", t):
            return False, f"한글 없음: {t[:200]}"
        return True, t[:200]

    # ------------------------------------------------------------------ AI 3회
    def repeat3(self, step: str, run_once: Callable[[int], dict], same_keys: tuple[str, ...], limit_s: float | None = None) -> list[dict]:
        """같은 입력으로 AI 단계를 3번 돌린다. run_once(i) 는 {'seconds': 소요, 키: 값 …} 을 낸다.
        same_keys 의 값이 3번 모두 같아야 학생 모두가 같은 다음 단계를 받는다. limit_s 가 있으면 가장 느린 소요 시간이 그 안이어야 한다."""
        runs = []
        for i in range(3):
            t0 = time.monotonic()
            try:
                got = run_once(i) or {}
            except Exception as e:
                got = {"error": f"{type(e).__name__}: {e}"}
            got.setdefault("seconds", round(time.monotonic() - t0, 1))
            runs.append(got)
            print(f"    {step} {i + 1}/3: " + json.dumps(got, ensure_ascii=False, default=str)[:400], flush=True)
        (self.out / "ai3").mkdir(parents=True, exist_ok=True)
        (self.out / "ai3" / f"{self.lab}-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', step)}.json").write_text(
            json.dumps(runs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        errors = [r["error"] for r in runs if r.get("error")]
        self.check(f"{step} — 3번 모두 끝까지", not errors, "; ".join(errors), kind="ai3")
        for key in same_keys:
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
        for lab, log in self.logs.items():
            if log.console_errors or log.failed_requests:
                bad.append(Verdict(lab, "콘솔 오류 · 실패한 요청", False, "quality"))
        (self.out / "results.json").write_text(json.dumps({
            "verdicts": [asdict(v) for v in self.verdicts],
            "logs": {k: asdict(v) for k, v in self.logs.items()}}, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# 수업 한 바퀴 결과", "", f"판정 {len(self.verdicts)}개 · 실패 {len([v for v in self.verdicts if not v.ok])}개", ""]
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


# ---------------------------------------------------------------------- 실행
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / ".evidence/class-round" / time.strftime("%Y%m%d-%H%M%S")))
    ap.add_argument("--only", default="", help="쉼표로 고른 실습 번호만(예: 01,05)")
    ap.add_argument("--from", dest="start", default="", help="이 번호부터 끝까지")
    ap.add_argument("--headed", action="store_true")
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
        r.open()
        started = not args.start
        for code, title, fn in LABS:
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
    print(f"\n결과: {out}/summary.md (실패 {len([v for v in r.verdicts if not v.ok])}개)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
