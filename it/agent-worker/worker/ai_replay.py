"""AI 응답 저장 · 재생 — API 키(CLI 로그인)가 없는 PC에서도 실습이 끝까지 가도록, AI가 응답할 단계에만 미리 실제 AI로
실행할 때 저장한 응답을 넣는다. 포털 · 설비 · 처리 흐름 · 결과 검사 · 저장은 그대로 실제로 돈다. 문서: 문서/시스템/참조/재생모드.md

    AI_MODE=auto    (기본) 워커가 켜질 때 API 키 · CLI 로그인을 확인해 「없음」이면 replay, 그 밖(있음 · 확인 불가)은 live
    AI_MODE=live    실제 AI(기존 그대로)
    AI_MODE=record  실제 AI로 실행하면서 CLI가 낸 실행 이벤트와 결과 파일을 업무마다 저장한다
    AI_MODE=replay  CLI를 부르지 않고 같은 업무의 저장된 실행 이벤트를 그대로 내보낸다

규칙은 하나다: 업무 이름(작업 단계 이름)이 같으면 저장된 응답을 쓴다. 입력 · 지시문이 저장할 때와 달라도 쓴다.
업무 하나에 파일 하나(AI_REPLAY_DIR/<업무 해시>.json)이고, 그 안에 실행이 순서대로 들어 있다 — 첫 실행, 그리고 같은 세션을
이어 간 실행(사람이 질문에 답한 뒤, 결과 형식 교정). 다시 저장하면 그 업무 파일을 덮어쓴다.
그 업무의 저장 파일이 없으면 지어내지 않고 그 단계를 실패시킨다. 저장된 응답이 이 처리 건의 결과 형식에 맞지 않으면
실제 실행과 같은 형식 검사가 실패시킨다.

갈아 끼우는 곳은 Runner 의 exec_fn(CLI 를 실행해 ExecEvent 를 내보내는 자리) 하나다. 그 뒤는 실제 실행과 같은 코드다.
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
FORMAT = "hyd-ai-replay/2"
MODES = ("auto", "live", "record", "replay")
SESSION_PREFIX = "replay:"
# 저장하면 안 되는 값: 워커가 켜질 때(자식 프로세스용 환경 정리 전) 보이는 키 · 토큰 · 비밀번호 값
_SECRET_VALUES = [v for k, v in os.environ.items() if re.search(r"KEY|TOKEN|SECRET|PASSWORD", k, re.I) and len(v) >= 8]


def resolve_mode(mode: str, login: Callable[[], bool | None]) -> str:
    """auto 를 live/replay 로 정한다. 로그인이 「없음」으로 확인될 때만 replay — 확인할 수 없으면 실제 실행을 막지 않는다."""
    mode = (mode or "auto").strip().lower()
    if mode not in MODES:
        raise ValueError(f"AI_MODE 는 {', '.join(MODES)} 중 하나여야 합니다: {mode}")
    if mode != "auto":
        return mode
    return "replay" if login() is False else "live"


def _prompt_text(request) -> str:
    """긴 프롬프트는 작업 폴더의 파일로 넘어간다(runner._deliver_prompt). 그 경우 파일 본문에서 업무 이름을 읽는다."""
    from .runner import PROMPT_FILE
    path = Path(request.workdir) / PROMPT_FILE
    if PROMPT_FILE in (request.prompt or "") and path.is_file():
        return path.read_text(encoding="utf-8")
    return request.prompt or ""


def step_of(request) -> str:
    """업무 이름(prompt.build 의 「## 업무」). 사람 응답 뒤 · 형식 교정 같은 이어 하기 프롬프트에는 없다."""
    m = re.search(r"## 업무\n(.*?)\n", _prompt_text(request))
    return m.group(1).strip() if m else ""


def _event_dict(ev: ExecEvent) -> dict:
    return dict(asdict(ev), kind=ev.kind.value)


def _event_from(d: dict) -> ExecEvent:
    return ExecEvent(**dict(d, kind=ExecEventKind(d["kind"])))


class Library:
    """업무 하나에 파일 하나: {"format", "step", "recorded_at", "provider", "runs": [{"session_id", "events", "result_file"}, …]}."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def path_of(self, step: str) -> Path:
        return self.root / f"{hashlib.sha256(step.encode('utf-8')).hexdigest()[:16]}.json"

    def _read(self, path: Path) -> dict:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("format") != FORMAT:
            raise RuntimeError(f"저장된 AI 응답 파일의 형식이 다릅니다: {path.name}")
        return doc

    def load(self, step: str) -> dict | None:
        p = self.path_of(step)
        return self._read(p) if p.is_file() else None

    def docs(self) -> list[dict]:
        return [self._read(p) for p in sorted(self.root.glob("*.json"))] if self.root.is_dir() else []

    def _owner_of(self, session: str) -> tuple[dict, int] | None:
        """실제 세션 id 가 어느 업무 파일의 몇 번째 실행인지(이어 하기 저장용)."""
        for doc in self.docs():
            for i, run in enumerate(doc["runs"]):
                if run.get("session_id") == session:
                    return doc, i
        return None

    def save(self, request, events: list[ExecEvent], *, provider_id: str) -> Path | None:
        result_path = Path(request.workdir) / RESULT_FILE
        run = {"session_id": next((ev.session_id for ev in events if ev.session_id), None),
               "events": [_event_dict(ev) for ev in events if ev.kind is not ExecEventKind.THINKING],
               "result_file": result_path.read_text(encoding="utf-8") if result_path.is_file() else None}
        step = step_of(request)
        owner = self._owner_of(request.resume_session) if request.resume_session else None
        if owner is not None:                        # 같은 세션을 이어 간 실행: 그 업무 파일 뒤에 붙인다(그 뒤의 옛 이어 하기는 버린다)
            doc, i = owner
            doc["runs"] = doc["runs"][: i + 1] + [run]
        elif step:                                   # 업무의 첫 실행: 그 업무 파일을 새로 쓴다(다시 저장하면 덮어쓴다)
            doc = {"format": FORMAT, "step": step, "provider": provider_id, "runs": [run]}
        else:
            log.warning("업무 이름도 이어 갈 저장분도 없는 실행이라 AI 응답을 저장하지 않았습니다")
            return None
        doc["recorded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
        if any(v in text for v in _SECRET_VALUES):
            log.error("AI 응답을 저장하지 않았습니다: 키 · 토큰으로 보이는 환경 변수 값이 실행 기록에 있습니다(%s)", doc["step"])
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_of(doc["step"])
        path.write_text(text + "\n", encoding="utf-8")
        log.info("AI 응답 저장: %s · %s (실행 %d개)", path.name, doc["step"], len(doc["runs"]))
        return path

    def find(self, request) -> tuple[dict | None, int]:
        """(업무 파일, 쓸 실행 순번). 이어 하기면 replay:<업무 해시>:<순번> 세션의 다음 실행, 아니면 그 업무의 첫 실행."""
        resume = request.resume_session or ""
        if resume.startswith(SESSION_PREFIX):
            key, _, n = resume[len(SESSION_PREFIX):].rpartition(":")
            p = self.root / f"{key}.json"
            return (self._read(p) if p.is_file() else None), (int(n) + 1 if n.isdigit() else 0)
        step = step_of(request)
        return (self.load(step) if step else None), 0


def recording(inner, library: Library, provider_of: Callable[[object], str]):
    """실제 CLI 실행(inner)을 그대로 흘려보내면서 이벤트를 모아, 실행이 끝나면 저장한다."""
    def run(provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        seen: list[ExecEvent] = []
        gen = (inner(provider, request, env, check_stop=check_stop) if getattr(inner, "accepts_check_stop", False)
               else inner(provider, request, env))
        for ev in gen:
            seen.append(ev)
            yield ev
        library.save(request, seen, provider_id=provider_of(provider))
    run.accepts_check_stop = True
    return run


def replaying(library: Library):
    """CLI 를 부르지 않고 저장된 실행 이벤트를 내보낸다. 결과 파일도 저장 당시 그대로 작업 폴더에 둔다.
    쓴 저장분은 run.last 에 남겨 Runner 가 처리 과정에 한 줄로 알린다(저장된 응답 사이에는 아무것도 끼워 넣지 않는다 —
    끼우면 최종 응답 · 사람 질문 판정이 저장 당시와 달라진다)."""
    def run(provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        run.last = None
        doc, i = library.find(request)
        if doc is None or i >= len(doc["runs"]):
            what = f"「{doc['step']}」의 이어지는 응답" if doc else f"「{step_of(request) or '이 단계'}」 업무"
            yield ExecEvent(kind=ExecEventKind.ERROR, is_error=True,
                            text=f"AI 응답 재생: {what}의 저장된 AI 응답이 없습니다. API 키를 넣으면 실제 AI로 실행합니다.")
            return
        saved = doc["runs"][i]
        if saved.get("result_file") is not None:
            path = Path(request.workdir) / RESULT_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(saved["result_file"], encoding="utf-8")
        session = f"{SESSION_PREFIX}{library.path_of(doc['step']).stem}:{i}"
        run.last = {"step": doc["step"], "recorded_at": doc["recorded_at"]}
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=session)
        for d in saved["events"]:
            if check_stop:
                check_stop()
            yield _event_from(dict(d, session_id=session) if d.get("session_id") else d)
    run.accepts_check_stop = True
    run.last = None
    return run


def used_notice(last: dict | None) -> str | None:
    """처리 과정에 남길 한 줄."""
    return f"AI 응답 재생: 「{last['step']}」 — 미리 저장한 응답입니다({last['recorded_at']}). 지금 AI가 새로 추론한 것이 아닙니다." if last else None
