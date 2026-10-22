"""AI 답 저장 · 재생 — API 키(CLI 로그인)가 없는 학생 PC에서도 실습이 끝까지 가도록, AI가 답할 자리에만 강사가 실제 AI로
실행할 때 저장한 답을 넣는다. 포털 · 설비 · 처리 흐름 · 결과 검사 · 저장은 그대로 실제로 돈다. 문서: 문서/시스템/참조/재생모드.md

    AI_MODE=live    실제 AI(기존 그대로)
    AI_MODE=record  실제 AI로 실행하면서, CLI가 낸 실행 이벤트와 결과 파일을 AI_REPLAY_DIR 에 단계마다 저장한다(강사)
    AI_MODE=replay  CLI를 부르지 않고, 같은 단계의 저장된 실행 이벤트를 그대로 내보낸다
    AI_MODE=auto    (기본) 워커가 켜질 때 CLI 로그인을 확인해 「로그인 없음」이면 replay, 그 밖(로그인 됨 · 확인 불가)은 live

갈아 끼우는 곳은 Runner 의 exec_fn 하나다 — CLI 를 실행해 ExecEvent 를 내보내는 자리. 그 뒤(최종 답 해석, 결과 형식 검사,
사람 질문 · 보류, save_task_result, 처리 과정 이벤트)는 실제 실행과 같은 코드가 처리한다.

저장된 답 찾기:
  1) 같은 지시 · 같은 입력(프롬프트에서 실행마다 바뀌는 id · 시각 · 작업 폴더를 지운 해시)
  2) 같은 단계(업무 이름과 지시문 — 입력 데이터 앞부분 — 의 해시). 입력값이 강사 때와 다를 수 있음을 처리 과정에 남긴다
  3) 사람 답 뒤 이어 하기: 재생 세션(replay:<저장 id>)에 이어지는 저장분
  없으면 지어내지 않고 「저장된 AI 답 없음」 오류로 그 단계를 실패시킨다. 저장된 답이 이 처리 건의 결과 형식에 맞지 않으면
  실제 실행과 같은 형식 검사가 실패시킨다(교정 요청도 저장분이 없으니 실패로 끝난다).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from cliagents import ExecEvent, ExecEventKind

from .workspace import RESULT_FILE

log = logging.getLogger("worker.ai_replay")
FORMAT = "hyd-ai-replay/1"
DEFAULT_DIR = Path(__file__).resolve().parents[1] / "replay"
MODES = ("live", "record", "replay", "auto")
# 저장하면 안 되는 값: 워커가 켜질 때(자식 프로세스용 환경 정리 전) 보이는 키 · 토큰 · 비밀번호 값
_SECRET_VALUES = [v for k, v in os.environ.items() if re.search(r"KEY|TOKEN|SECRET|PASSWORD", k, re.I) and len(v) >= 8]
_VOLATILE = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "<id>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?"), "<시각>"),
    (re.compile(r"\b(ALT|INC|DEC|DEC-EVAL|CMD|WO|RUN)-[0-9A-Za-z-]+"), "<번호>"),
]
NOTICE = ("AI 답 재생: 이 PC에서는 AI 키(CLI 로그인)를 쓸 수 없어, 이 단계는 강사가 실제 AI로 실행할 때 저장한 답을 씁니다. "
          "지금 AI가 새로 추론한 것이 아닙니다. 실제 AI로 하려면 키를 넣고 워커를 다시 켜세요.")


def resolve_mode(mode: str, auth_probe: Callable[[], bool | None]) -> str:
    """auto 를 live/replay 로 정한다. 로그인이 「없음」으로 확인될 때만 replay — 확인할 수 없으면 실제 실행을 막지 않는다."""
    mode = (mode or "auto").strip().lower()
    if mode not in MODES:
        raise ValueError(f"AI_MODE 는 {', '.join(MODES)} 중 하나여야 합니다: {mode}")
    if mode != "auto":
        return mode
    return "replay" if auth_probe() is False else "live"


def _prompt_text(request) -> str:
    """긴 프롬프트는 작업 폴더의 파일로 넘어간다(runner._deliver_prompt). 그 경우 파일 본문으로 비교한다."""
    from .runner import PROMPT_FILE
    path = Path(request.workdir) / PROMPT_FILE
    if PROMPT_FILE in (request.prompt or "") and path.is_file():
        return path.read_text(encoding="utf-8")
    return request.prompt or ""


def _normalize(text: str, workdir: str) -> str:
    out = text.replace(str(workdir), "<작업폴더>")
    for rx, rep in _VOLATILE:
        out = rx.sub(rep, out)
    return re.sub(r"[ \t]+", " ", out).strip()


def keys(request) -> tuple[str, str]:
    """(같은 지시 · 같은 입력 해시, 같은 단계 해시). 단계 = 업무 이름 + 지시문에서 입력 데이터 앞까지."""
    norm = _normalize(_prompt_text(request), request.workdir)
    exact = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
    work = re.search(r"## 업무\n(.*?)(\n## |\Z)", norm, re.S)
    order = re.search(r"## 지시사항\n(.*?)(\[InputData\]|\n## 입력 데이터|\Z)", norm, re.S)
    step_text = ((work.group(1) if work else "") + "\n" + (order.group(1) if order else "")).strip()
    step = hashlib.sha256(step_text.encode("utf-8")).hexdigest()[:24] if step_text else ""
    return exact, step


def _event_dict(ev: ExecEvent) -> dict:
    d = asdict(ev)
    d["kind"] = ev.kind.value
    return d


def _event_from(d: dict) -> ExecEvent:
    d = dict(d)
    d["kind"] = ExecEventKind(d["kind"])
    return ExecEvent(**d)


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)

    def entries(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        out = []
        for p in sorted(self.root.glob("*.json")):
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"저장된 AI 답 파일을 읽을 수 없습니다: {p.name}: {exc}") from exc
            if e.get("format") == FORMAT:
                e["_file"] = p.name
                out.append(e)
        return out

    def find(self, request) -> tuple[dict | None, str]:
        """(저장분, 어떻게 찾았나: exact | step | resume | '')."""
        exact, step = keys(request)
        entries = self.entries()
        resume = request.resume_session or ""
        if resume.startswith("replay:"):
            parent = resume.split(":", 1)[1]
            prior = next((e for e in entries if e["id"] == parent), None)
            follow = [e for e in entries if prior and e.get("resume_of") and e["resume_of"] == prior.get("session_id")]
            if follow:
                return follow[-1], "resume"
        first_runs = [e for e in entries if not e.get("resume_of")]
        for e in reversed(first_runs):
            if e["exact"] == exact:
                return e, "exact"
        for e in reversed(first_runs):
            if step and e["step"] == step:
                return e, "step"
        return None, ""

    def save(self, request, events: list[ExecEvent], *, provider_id: str) -> Path | None:
        exact, step = keys(request)
        session = next((ev.session_id for ev in events if ev.session_id), None)
        result_path = Path(request.workdir) / RESULT_FILE
        entry = {
            "format": FORMAT, "id": hashlib.sha256(f"{exact}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16],
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "provider": provider_id,
            "exact": exact, "step": step, "session_id": session,
            "resume_of": request.resume_session if request.resume_session and not str(request.resume_session).startswith("replay:") else None,
            "step_title": (re.search(r"## 업무\n(.*?)\n", _prompt_text(request)) or [None, ""])[1],
            "events": [_event_dict(ev) for ev in events if ev.kind is not ExecEventKind.THINKING],
            "result_file": result_path.read_text(encoding="utf-8") if result_path.is_file() else None,
        }
        text = json.dumps(entry, ensure_ascii=False, default=str)
        leaked = [i for i, v in enumerate(_SECRET_VALUES) if v in text]
        if leaked:
            log.error("AI 답을 저장하지 않았습니다: 키 · 토큰으로 보이는 환경 변수 값이 실행 기록에 있습니다(%d개)", len(leaked))
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{step[:8] or 'step'}-{exact[:8]}-{entry['id']}.json"
        path.write_text(text, encoding="utf-8")
        log.info("AI 답 저장: %s (%s, 이벤트 %d)", path.name, entry["step_title"], len(entry["events"]))
        return path


def recording(inner, library: Library, provider_of: Callable[[object], str]):
    """실제 CLI 실행(inner)을 그대로 흘려보내면서 이벤트를 모아, 실행이 끝나면 저장한다."""
    def run(provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        seen: list[ExecEvent] = []
        for ev in inner(provider, request, env, check_stop=check_stop):
            seen.append(ev)
            yield ev
        library.save(request, seen, provider_id=provider_of(provider))
    run.accepts_check_stop = True
    return run


def replaying(library: Library):
    """CLI 를 부르지 않고 저장된 실행 이벤트를 내보낸다. 결과 파일도 저장 당시 그대로 작업 폴더에 둔다."""
    def run(provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        entry, how = library.find(request)
        if entry is None:
            msg = ("AI 답 재생: 이 단계의 저장된 AI 답이 없습니다. 강사가 실제 AI로 실행할 때 이 단계가 저장되지 않았거나, "
                   "입력 · 지시가 강사 때와 다릅니다. AI 키를 넣으면 실제 AI로 실행합니다.")
            yield ExecEvent(kind=ExecEventKind.ERROR, text=msg, is_error=True)
            return
        if entry.get("result_file") is not None:
            path = Path(request.workdir) / RESULT_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(entry["result_file"], encoding="utf-8")
        where = {"exact": "강사 때와 같은 지시 · 입력", "step": "같은 단계(입력값은 강사 때와 다를 수 있음)", "resume": "사람 답 뒤 이어 하기(강사가 쓴 답 기준)"}[how]
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=f"replay:{entry['id']}")
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=f"[AI 답 재생 · {entry['recorded_at']} 저장 · {where}] 아래는 강사 실행 때 실제 AI가 낸 내용입니다.\n")
        for d in entry["events"]:
            if check_stop:
                check_stop()
            ev = _event_from(d)
            if ev.session_id:
                ev.session_id = f"replay:{entry['id']}"
            yield ev
    run.accepts_check_stop = True
    return run
