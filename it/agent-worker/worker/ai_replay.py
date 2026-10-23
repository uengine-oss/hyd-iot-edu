"""AI 응답 저장 · 재생 — API 키(CLI 로그인)가 없는 PC에서도 실습이 끝까지 가도록, AI가 응답할 단계에만 미리 실제 AI로
실행할 때 저장한 응답을 넣는다. 포털 · 설비 · 처리 흐름 · 결과 검사 · 저장은 그대로 실제로 돈다. 문서: 문서/시스템/참조/재생모드.md

    AI_MODE=auto    (기본) 워커가 켜질 때 API 키 · CLI 로그인을 확인해 있으면 live, 없으면(확인 불가 포함) replay
    AI_MODE=live    실제 AI(기존 그대로)
    AI_MODE=record  실제 AI로 실행하면서 CLI가 낸 실행 이벤트와 결과 파일을 업무마다 저장한다
    AI_MODE=replay  CLI를 부르지 않고 같은 업무의 저장된 실행 이벤트를 내보낸다

규칙은 하나다: 업무 이름(작업 단계 이름)이 같으면 저장된 응답을 쓴다. 입력 · 지시문이 저장할 때와 달라도 쓴다.
업무 이름은 띄어쓰기 · 대소문자를 무시하고 비교한다. 업무 하나에 파일 하나(AI_REPLAY_DIR/<업무 해시>.json)이고, 그 안에 실행이
순서대로 들어 있다 — 첫 실행, 그리고 같은 세션을 이어 간 실행(사람이 질문에 답한 뒤, 결과 형식 교정). 다시 저장하면 덮어쓴다.
그 업무의 저장 파일이 없으면 지어내지 않고 그 단계를 실패시킨다. 저장된 응답이 결과 형식에 맞지 않으면 실제 실행과 같은
형식 검사가 실패시킨다.

이 처리 건의 값으로 바꿔 끼우기: 저장한 실행의 작업 기록(context/task.json — 처리 건 id · 작업 id · process_scope · 입력 데이터)과
지금 작업 기록을 같은 자리끼리 비교해, 달라진 값을 저장된 응답 · 결과 파일에서 지금 값으로 바꾼다.
쓰기 도구는 다시 부른다: 저장된 AI가 부른 MCP 도구 가운데 서버가 읽기 전용으로 표시하지 않은 것(mcp_check.read_only_verdict —
예: 판단 등록 submit_decision)은 저장된 결과를 쓰지 않고 이 PC의 서버를 바꿔 끼운 입력으로 실제로 부른다. 승인 전 쓰기는
승인 대기 카드 등록뿐이라(문서/시스템/2_기준.md) 처리 건이 믿는 새 id(decision_id)는 이렇게만 생긴다. 그 도구가 돌려준 새 id
(id · *_id 칸)도 저장된 응답에서 바꿔 끼운다. 읽기 도구는 다시 부르지 않고 저장된 결과를 쓴다. 명령형(stdio) 서버는 읽기로 본다
(이 시스템의 명령형 서버는 읽기 전용 neo4j 뿐이고, 학생이 등록한 서버는 읽기 도구만 허용된다).

갈아 끼우는 곳은 Runner 의 exec_fn(CLI 를 실행해 ExecEvent 를 내보내는 자리) 하나다. 그 뒤는 실제 실행과 같은 코드다.
"""
from __future__ import annotations

import copy
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
from procsvc import mcp_check

from . import env_guard
from .bridge import MCP_CONFIG_FILENAME
from .workspace import RESULT_FILE

log = logging.getLogger("worker.ai_replay")
FORMAT = "hyd-ai-replay/2"
MODES = ("auto", "live", "record", "replay")
SESSION_PREFIX = "replay:"
TASK_FILE = "context/task.json"
# 저장하면 안 되는 값: 워커가 켜질 때(자식 프로세스용 환경 정리 전) 보이는 비밀 환경 변수 값 — 워커가 자식 프로세스에서 지우는 이름
# (env_guard: DSN · 비밀번호 · 토큰 · API 키 · HYD_SECRET_*)과, 지우지 않고 CLI 에 넘기는 로그인 키(env_guard.CLI_AUTH_KEEP)
def _secret_env(environ) -> dict[str, str]:
    blocked = set(env_guard.secret_keys(environ))
    return {k: v for k, v in environ.items()
            if (k in blocked or k in env_guard.CLI_AUTH_KEEP or k.upper().startswith(env_guard.SECRET_PREFIX)) and len(v) >= 8}


_SECRET_ENV = _secret_env(os.environ)


def resolve_mode(mode: str, login: Callable[[], bool | None]) -> str:
    """auto 를 live/replay 로 정한다. 키 · 로그인이 있다고 확인되면 live, 아니면(없음 · 확인 불가) replay."""
    mode = (mode or "auto").strip().lower()
    if mode not in MODES:
        raise ValueError(f"AI_MODE 는 {', '.join(MODES)} 중 하나여야 합니다: {mode}")
    if mode != "auto":
        return mode
    return "live" if login() is True else "replay"


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


def _key(step: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", "", step).casefold().encode("utf-8")).hexdigest()[:16]


def _event_dict(ev: ExecEvent) -> dict:
    """원문 줄(raw)은 종류를 모르는 이벤트만 쓴다(events.py: 처리 과정의 agent_log) — 나머지는 같은 내용이 칸에 있어 빼고 저장한다."""
    d = dict(asdict(ev), kind=ev.kind.value)
    if ev.kind is not ExecEventKind.UNKNOWN:
        d.pop("raw")
    return d


def _event_from(d: dict) -> ExecEvent:
    return ExecEvent(**dict(d, kind=ExecEventKind(d["kind"])))


def _joined(events: list[dict]) -> list[dict]:
    """이어진 AI 설명 조각(토큰 단위 ASSISTANT_TEXT)을 한 덩이로 — 재생할 때 조각 경계에 걸린 id 도 바꿔 끼울 수 있게."""
    out: list[dict] = []
    for d in events:
        prev = out[-1] if out else None
        if prev and d["kind"] == prev["kind"] == ExecEventKind.ASSISTANT_TEXT.value and d.get("session_id") == prev.get("session_id"):
            prev["text"] = (prev.get("text") or "") + (d.get("text") or "")
        else:
            out.append(dict(d))
    return out


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None


def _task_context(workdir) -> dict:
    """작업 기록(context/task.json)에서 처리 건마다 달라지는 값: 작업 id · 처리 건 id · process_scope · 입력 데이터([InputData])."""
    task = _read_json(Path(workdir) / TASK_FILE) or {}
    query = str(task.get("query") or "")
    inputs = None
    if "[InputData]" in query:
        try:
            inputs = json.JSONDecoder().raw_decode(query.split("[InputData]", 1)[1].lstrip())[0]
        except ValueError:
            inputs = None
    return {"id": task.get("id"), "proc_inst_id": task.get("proc_inst_id"), "process_scope": task.get("process_scope"), "inputs": inputs}


def _secrets_in(workdir) -> dict[str, str]:
    """이 실행에서 CLI 가 받은 비밀값: 워커 환경 변수 + 작업 폴더 .mcp.json 의 env · headers 가운데 비밀 이름(토큰 · 비밀번호 · 인증)."""
    found = dict(_SECRET_ENV)
    servers = (_read_json(Path(workdir) / MCP_CONFIG_FILENAME) or {}).get("mcpServers") or {}
    for name, entry in servers.items():
        for part in ("env", "headers"):
            for k, v in ((entry or {}).get(part) or {}).items():
                if mcp_check.is_secret_key(k) and isinstance(v, str) and len(v) >= 6:
                    found[f"{name}.{part}.{k}"] = v
                    for j, piece in enumerate(v.split()[1:]):     # 「Bearer <토큰>」의 토큰만 응답에 나올 수도 있다
                        if len(piece) >= 8:
                            found[f"{name}.{part}.{k}#{j + 1}"] = piece
    return found


class Library:
    """업무 하나에 파일 하나: {"format", "step", "recorded_at", "provider", "runs": [{"session_id", "events", "result_file", "context"}, …]}."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def path_of(self, step: str) -> Path:
        return self.root / f"{_key(step)}.json"

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
               "events": _joined([_event_dict(ev) for ev in events if ev.kind is not ExecEventKind.THINKING]),
               "result_file": result_path.read_text(encoding="utf-8") if result_path.is_file() else None,
               "context": _task_context(request.workdir)}
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
        leaked = sorted(name for name, v in _secrets_in(request.workdir).items() if v in text)
        if leaked:
            log.error("AI 응답을 저장하지 않았습니다(%s): 비밀값이 실행 기록에 있습니다 — %s", doc["step"], ", ".join(leaked))
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


# ---------------------------------------------------------------- 이 처리 건의 값으로 바꿔 끼우기
def _id_like(s: str) -> bool:
    """글 속에서도 바꿔 끼울 값: 공백 없이 5자 이상, 숫자와 숫자 아닌 글자가 함께 있는 것(처리 건 id · 사건 번호 · 판단 id · 시각)."""
    return len(s) >= 5 and not re.search(r"\s", s) and bool(re.search(r"\d", s)) and bool(re.search(r"\D", s))


class _Swaps:
    def __init__(self):
        self.exact: dict[str, str] = {}
        self.objects: list[tuple[dict, dict]] = []

    def pair(self, old, new) -> None:
        """같은 자리의 저장 값(old)과 지금 값(new)을 짝짓는다. 객체는 통째로, 글은 값끼리. 수 · 참거짓은 짝짓지 않는다."""
        if old == new:
            return
        if isinstance(old, dict) and isinstance(new, dict):
            self.objects.append((copy.deepcopy(old), copy.deepcopy(new)))
            for k in old.keys() & new.keys():
                self.pair(old[k], new[k])
        elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            for a, b in zip(old, new):
                self.pair(a, b)
        elif isinstance(old, str) and isinstance(new, str) and old:
            self.exact.setdefault(old, new)

    def pair_ids(self, old, new) -> None:
        """도구가 새로 만든 것의 id: 같은 자리의 id · *_id · *Id 칸 글이 다르면 짝짓는다."""
        if isinstance(old, dict) and isinstance(new, dict):
            for k in old.keys() & new.keys():
                if (k == "id" or k.endswith("_id") or k.endswith("Id")) and isinstance(old[k], str) and isinstance(new[k], str):
                    if old[k] != new[k]:
                        self.exact[old[k]] = new[k]
                else:
                    self.pair_ids(old[k], new[k])
        elif isinstance(old, list) and isinstance(new, list):
            for a, b in zip(old, new):
                self.pair_ids(a, b)

    def text(self, s: str) -> str:
        if s in self.exact:
            return self.exact[s]
        for old in sorted((o for o in self.exact if _id_like(o)), key=len, reverse=True):
            if old in s:
                s = s.replace(old, self.exact[old])
        return s

    def apply(self, value):
        if isinstance(value, dict):
            for old, new in self.objects:
                if value == old:
                    return copy.deepcopy(new)
            return {k: self.apply(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.apply(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def _mcp_target(tool: str | None) -> tuple[str, str] | None:
    """CLI 가 보고한 MCP 도구 이름 → (서버, 도구). Claude Code: mcp__<서버>__<도구>, 그 밖: <서버>/<도구>."""
    if not tool:
        return None
    if tool.startswith("mcp__") and tool.count("__") >= 2:
        server, _, name = tool[len("mcp__"):].partition("__")
        return server, name
    if "/" in tool:
        server, _, name = tool.partition("/")
        return server, name
    return None


def _as_json(content):
    if isinstance(content, (dict, list)) and not (isinstance(content, list) and content and isinstance(content[0], dict) and "type" in content[0]):
        return content
    if isinstance(content, list):
        content = "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    try:
        return json.loads(content) if isinstance(content, str) and content.strip().startswith(("{", "[")) else None
    except ValueError:
        return None


class _Tools:
    """재생 중 쓰기 도구를 이 PC의 서버로 부른다. 서버 설정은 이번 실행의 작업 폴더 .mcp.json(실제 실행이면 CLI 가 읽을 그 파일)."""

    def __init__(self, workdir):
        self.servers = (_read_json(Path(workdir) / MCP_CONFIG_FILENAME) or {}).get("mcpServers") or {}
        self.listed: dict[str, dict] = {}

    def spec(self, server: str) -> dict:
        if server not in self.servers:
            raise RunError(f"도구 서버 {server} 가 이 단계에 연결돼 있지 않습니다")
        try:
            return mcp_check.normalize(self.servers[server])
        except ValueError as e:
            raise RunError(f"도구 서버 {server} 설정이 올바르지 않습니다: {e}") from None

    def writes(self, server: str, tool: str) -> bool:
        if server not in self.servers:           # 이번 단계에 없는 서버: 다시 부를 수 없으니 저장된 결과를 쓴다(쓰기였다면 결과 검사가 막는다)
            return False
        spec = self.spec(server)
        if spec["transport"] == "stdio":
            return False
        if server not in self.listed:
            out = mcp_check.check(spec)
            if out["status"] != "ok":
                raise RunError(f"도구 서버 {server} 의 도구 목록을 읽지 못했습니다: {out.get('error')}")
            self.listed[server] = {t["name"]: t for t in out["tools"]}
        meta = self.listed[server].get(tool)
        return meta is not None and not meta["callable"]

    def call(self, server: str, tool: str, arguments: dict) -> dict:
        # 승인 뒤 시스템 작업의 쓰기 호출과 같은 함수(입력 형식 검사 포함). 결과 글은 비밀 칸을 가린 것이다.
        out = mcp_check.call_effect(self.spec(server), tool, arguments, max_chars=1_000_000)
        if out["status"] != "ok":
            raise RunError(f"{server}/{tool} 호출 실패: {out.get('error')}")
        return out["result"]


class RunError(Exception):
    pass


def replaying(library: Library):
    """CLI 를 부르지 않고 저장된 실행 이벤트를 내보낸다. 결과 파일도 저장 당시 것을 이 처리 건의 값으로 바꿔 둔다.
    쓴 저장분은 run.last 에 남겨 Runner 가 처리 과정에 한 줄로 알린다(저장된 응답 사이에는 알림을 끼워 넣지 않는다 —
    끼우면 최종 응답 · 사람 질문 판정이 저장 당시와 달라진다)."""
    def run(provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        run.last = None
        doc, i = library.find(request)
        if doc is None or i >= len(doc["runs"]):
            what = f"「{doc['step']}」의 이어지는 응답" if doc else f"「{step_of(request) or '이 단계'}」 업무"
            yield _error(f"{what}의 저장된 AI 응답이 없습니다. API 키를 넣으면 실제 AI로 실행합니다.")
            return
        saved = doc["runs"][i]
        swaps = _Swaps()
        swaps.pair(saved.get("context") or {}, _task_context(request.workdir))
        tools = _Tools(request.workdir)
        session = f"{SESSION_PREFIX}{library.path_of(doc['step']).stem}:{i}"
        run.last = {"step": doc["step"], "recorded_at": doc["recorded_at"], "rerun": []}
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=session)
        events = saved["events"]
        live: dict[str, dict] = {}                   # 다시 부른 쓰기 도구: tool_use_id → 이 PC의 결과
        for n, d in enumerate(events):
            if check_stop:
                check_stop()
            d = dict(d, session_id=session if d.get("session_id") else None,
                     text=swaps.text(d.get("text") or ""), tool_input=swaps.apply(d.get("tool_input")))
            target = _mcp_target(d.get("tool"))
            try:
                if d["kind"] == ExecEventKind.TOOL_START.value and target and tools.writes(*target):
                    result = tools.call(*target, d["tool_input"] if isinstance(d["tool_input"], dict) else {})
                    live[d.get("tool_use_id")] = result
                    run.last["rerun"].append(f"{target[0]}/{target[1]}")
                    if result["is_error"]:
                        raise RunError(f"{target[0]}/{target[1]} 가 오류를 돌려줬습니다: {result['text'][:500]}")
                    recorded = next((e for e in events[n + 1:] if e["kind"] == ExecEventKind.TOOL_END.value
                                     and e.get("tool_use_id") == d.get("tool_use_id")), None)
                    swaps.pair_ids(_as_json(recorded.get("tool_output") if recorded else None), _as_json(result["text"]))
            except RunError as e:
                yield _error(f"「{doc['step']}」에서 저장된 AI가 부른 쓰기 도구를 이 PC에서 다시 부르지 못했습니다 — {e}")
                return
            if d["kind"] == ExecEventKind.TOOL_END.value and d.get("tool_use_id") in live:
                d.update(text=live[d["tool_use_id"]]["text"], tool_output=live[d["tool_use_id"]]["text"], is_error=False)
            else:
                d.update(tool_output=swaps.apply(d.get("tool_output")))
            yield _event_from(d)
        if saved.get("result_file") is not None:     # Runner 는 실행이 끝난 뒤 결과 파일을 읽는다
            parsed = _as_json(saved["result_file"])
            path = Path(request.workdir) / RESULT_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(swaps.apply(parsed), ensure_ascii=False) if parsed is not None else swaps.text(saved["result_file"]),
                            encoding="utf-8")
    run.accepts_check_stop = True
    run.last = None
    return run


def _error(message: str) -> ExecEvent:
    return ExecEvent(kind=ExecEventKind.ERROR, is_error=True, text=f"AI 응답 재생: {message}")


def used_notice(last: dict | None) -> str | None:
    """처리 과정에 남길 한 줄."""
    if not last:
        return None
    rerun = f" 쓰기 도구({', '.join(dict.fromkeys(last['rerun']))})는 이 PC에서 다시 실행했습니다." if last.get("rerun") else ""
    return f"AI 응답 재생: 「{last['step']}」 — 미리 저장한 응답입니다({last['recorded_at']}). 지금 AI가 새로 추론한 것이 아닙니다.{rerun}"
