"""AI 응답 저장 · 다시 쓰기 — 한 장치(같은 녹화 형식 · 같은 재생기)로 세 모드를 돈다. 문서: workspace/개발/문서/재생모드.md

    AI_MODE=live    키 있는 PC: 실제 AI. 같은 설정 · 같은 입력으로 앞서 성공한 실행이 이 PC에 있으면 그 응답을 다시 쓴다(같은 요청 저장)
    AI_MODE=record  강사: 실제 AI로 실행하고, 점유가 저장된 결과(제출 · 사람 질문 · 보류)로 끝나면 그 실행을 수업 녹화로 남긴다
    AI_MODE=replay  키 없는 PC: CLI · 모델을 부르지 않고 그 수업 AI 자리의 강사 녹화를 낸다

녹화를 찾는 열쇠
  수업 녹화(AI_REPLAY_DIR — 저장소 it/agent-worker/replay/): 서버가 준 수업 AI 자리(procsvc/course_policy — c3_cooling/T_agent ·
    handover/draft-1~3 · question)와 무엇에 대한 처리 건인가(경보 종류 · 질문 글). 학생이 바꿀 수 있는 작업 이름 · 흐름 id 는 열쇠가 아니다 —
    이름을 바꾼 교대 흐름도 같은 녹화를 낸다. 같은 작업을 새로 하는 실행(재작업 세대 · 보류 뒤 재평가)은 실행 차례 runs[].attempt 로 가린다.
  같은 요청 저장(이 PC의 <작업 공간>/.ai-cache): 실행에 영향을 주는 것 전부의 해시(정의 · 단계 · 지시 · 입력 · 피드백 · 폼 · 에이전트 설정 ·
    업무 규칙 · 스킬 본문 · 도구 서버 · 모델 — Runner._request_material). 하나라도 다르면 새로 실행한다. 결과 검사를 통과해 제출한 실행만
    저장하고, 그 실행의 작업이 지금도 끝남(DONE — 처리 흐름이 결과를 받아들임)일 때만 다시 쓴다.

녹화 하나 = 파일 하나(<열쇠>.json.gz). 안에는 실행이 순서대로 있다 — 첫 실행, 같은 세션을 이어 간 실행(사람 답 뒤 · 결과 교정 · 처리 흐름이
결과를 돌려보낸 뒤). 다시 낼 때 이어 하기는 세션 replay:<열쇠>:<순번>(수업 녹화) · reuse:<열쇠>:<순번>(같은 요청)으로 다음 실행을 고른다.
워커가 다시 켜져 같은 작업을 다시 잡으면(임대 만료 뒤 재점유) 끊긴 실행을 처음부터 다시 낸다(resume_after).

다시 낼 때 이 처리 건의 값으로 바꿔 끼우는 것은 처리 건마다 새로 생기는 값(작업 · 처리 건 · 점유 · 경보 id · 시각)뿐이다. 데이터를 고르는
입력(설비 · 부품 · 정비 계획 같은 기준 값)이 녹화와 다르면 바꿔 끼우지 않고 멈춘다 — 다른 설비의 실측을 이 설비 것처럼 보이지 않게.
쓰기 도구(서버가 읽기 전용으로 표시하지 않은 도구 — 판단 등록 submit_decision · submit_purchase)는 이 PC 서버로 다시 부르고, 돌려받은 새 id 를
응답 · 결과 파일에 바꿔 끼운다. 녹화 때 오류였던 쓰기 호출은 다시 부르지 않는다. 녹화가 쓴 도구 서버 · 도구가 지금 단계에 없으면 멈춘다.

없는 녹화는 지어내지 않고 학생이 알아듣는 말로 멈춘다(NotRecorded — 무엇이 없고 무엇을 하면 되는지). 저장 직전 비밀값은 가린다(diagnostics.hide).
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from cliagents import ExecEvent, ExecEventKind
from procsvc import mcp_check

from .bridge import MCP_CONFIG_FILENAME
from .course_access import Stop
from .diagnostics import REDACTED, hide
from .workspace import RESULT_FILE

log = logging.getLogger("worker.ai_replay")
FORMAT = "hyd-ai-replay/3"
COURSE = "replay:"      # 수업 녹화를 다시 낸 세션
REUSE = "reuse:"        # 같은 요청 저장을 다시 쓴 세션
TASK_FILE = "context/task.json"
SWAPS_FILE = "context/ai-replay-swaps.json"     # 이어 하기 실행이 이어 받을 바꿔 끼울 값(저장 id → 이 PC의 새 id)
QUESTION_PREFIX = "질문 "
DEFERRED_MARK = "[DEFERRED]"       # task_deferral.defer 가 작업 log 에 남기는 표시 — 보류 한 번에 하나
STORED = ("submitted", "asked", "deferred")


class NotRecorded(Stop):
    """녹화(저장)에 없는 실행 — 문장은 학생이 할 일까지 쓴다."""
    title = "AI 응답 재생 범위 밖"


# ---------------------------------------------------------------- 열쇠
def course_key(slot: str, case: str = "") -> str:
    return hashlib.sha256(f"{case}|{slot}".encode("utf-8")).hexdigest()[:16]


def question_case(text: str) -> str:
    """질문은 질문 글로 가린다 — 띄어쓰기와 끝의 물음표 · 마침표 차이는 같은 질문으로 본다."""
    flat = " ".join(str(text).split())
    return QUESTION_PREFIX + (flat.rstrip(" ?？.!。") or flat)


def course_case(slot: str | None, values: dict) -> str:
    """무엇에 대한 처리 건인가: 질문 자리면 질문 글, 경보로 연 처리 건이면 경보 종류(pattern), 그 밖(교대 초안)은 빈 값."""
    if slot == "question":
        return question_case(values.get("question") or "")
    return str(values.get("pattern") or "")


def attempt_of(row: dict) -> tuple[int, int]:
    """이 점유의 실행 차례: (재작업 세대, 이 작업이 지금까지 보류한 횟수 = 몇 번째 재평가인가)."""
    return int(row.get("generation") or 0), str(row.get("log") or "").count(DEFERRED_MARK)


def resume_after(session: str | None, *, reclaimed: bool) -> str | None:
    """앞 점유가 남긴 세션으로 이어 할 때. 다시 낸 세션(replay: · reuse:)인데 이 점유가 임대 만료 뒤 재점유면(워커 재시작 · 끊김) 앞 실행은 끝나지
    않았다 — 다음 실행으로 넘어가지 않고 같은 실행을 처음부터 다시 낸다(<열쇠>:<i> → <열쇠>:<i-1>, i=0 이면 이어 하기 없음)."""
    if not session or not session.startswith((COURSE, REUSE)) or not reclaimed:
        return session
    head, _, n = session.rpartition(":")
    i = int(n) if n.isdigit() else 0
    return f"{head}:{i - 1}" if i > 0 else None


def _attempt(run: dict) -> tuple[int, int]:
    a = run.get("attempt") or {}
    return int(a.get("generation") or 0), int(a.get("reassessment") or 0)


def _attempt_label(attempt) -> str:
    g, n = attempt or (0, 0)
    return " · ".join(([f"재작업 세대 {g}"] if g else []) + ([f"재평가 {n}회째"] if n else []))


# ---------------------------------------------------------------- 저장소
class Library:
    """녹화 파일 묶음: {"format", "slot" | "request", "case", "step", "provider", "recorded_at", "source"?, "runs": [실행 …]}.
    실행 = {"session_id", "events", "result_file", "context", "tool_outputs_full", "attempt"?}."""

    def __init__(self, root: Path, prefix: str = COURSE):
        self.root, self.prefix = Path(root), prefix

    def file_of(self, key: str) -> Path:
        return self.root / f"{key}.json.gz"

    def _read(self, path: Path) -> dict:
        doc = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        if doc.get("format") != FORMAT:
            raise RuntimeError(f"저장된 AI 응답 파일의 형식이 다릅니다({doc.get('format')} — 지금은 {FORMAT}): {path}")
        return doc

    def load(self, key: str) -> dict | None:
        path = self.file_of(key)
        return self._read(path) if path.is_file() else None

    def delete(self, key: str) -> None:
        self.file_of(key).unlink(missing_ok=True)

    def docs(self) -> list[tuple[str, dict]]:
        return [(p.name[: -len(".json.gz")], self._read(p)) for p in sorted(self.root.glob("*.json.gz"))] if self.root.is_dir() else []

    def questions(self) -> list[str]:
        """강의에서 다룬(녹화된) 질문 — 키 없는 PC 의 질문 화면이 예시로 보이고, 다른 질문은 이것을 알려 멈춘다."""
        return [d["case"][len(QUESTION_PREFIX):] for _, d in self.docs() if d.get("slot") == "question"]

    def session(self, key: str, i: int) -> str:
        return f"{self.prefix}{key}:{i}"

    def continuation(self, session: str) -> tuple[str | None, dict | None, int | None]:
        """다시 낸 세션 <prefix><열쇠>:<i> 의 다음 실행(같은 차례일 때만). (열쇠, 녹화, 순번 — 없으면 None)."""
        key, _, n = session[len(self.prefix):].rpartition(":")
        doc = self.load(key) if key else None
        i = int(n) + 1 if n.isdigit() else None
        if doc is None or i is None or i >= len(doc["runs"]) or _attempt(doc["runs"][i]) != _attempt(doc["runs"][i - 1]):
            return key or None, doc, None
        return key, doc, i

    def owner_of(self, session: str) -> tuple[str, dict, int] | None:
        """실제 CLI 세션 id 가 어느 녹화의 몇 번째 실행인지(녹화 중 이어 하기를 같은 파일 뒤에 붙인다). Claude Code 는 이어 해도 세션 id 가
        같으므로 그 세션의 마지막 실행을 고른다."""
        for key, doc in self.docs():
            for i in range(len(doc["runs"]) - 1, -1, -1):
                if doc["runs"][i].get("session_id") == session:
                    return key, doc, i
        return None

    def write(self, key: str, doc: dict, secrets) -> Path:
        doc = hide(dict(doc, format=FORMAT, recorded_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")), secrets)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.file_of(key)
        text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
        path.write_bytes(gzip.compress((text + "\n").encode("utf-8"), mtime=0))      # gzip 머리에 시각을 넣지 않는다
        masked = text.count(REDACTED)
        log.info("AI 응답 저장: %s · %s%s · 실행 %d개%s", path.name, doc.get("slot") or "같은 요청", f" · {doc['case']}" if doc.get("case") else "",
                 len(doc["runs"]), f" · 비밀값 {masked}곳 가림" if masked else "")
        return path


# ---------------------------------------------------------------- 실행 하나 받아 두기
def _event_dict(ev: ExecEvent) -> dict:
    """원문 줄(raw)은 종류를 모르는 이벤트만 쓴다(events.py: 처리 과정의 agent_log) — 나머지는 같은 내용이 칸에 있어 빼고 저장한다."""
    d = dict(asdict(ev), kind=ev.kind.value)
    if ev.kind is not ExecEventKind.UNKNOWN:
        d.pop("raw")
    return d


def _event_from(d: dict) -> ExecEvent:
    return ExecEvent(**dict(d, kind=ExecEventKind(d["kind"])))


_PERSISTED = re.compile(r"\A<persisted-output>\n.*?Full output saved to: (\S+)", re.S)


def _persisted_full(events: list[dict], workdir) -> dict[str, str]:
    """Claude Code 는 큰 도구 결과를 작업 폴더 안 파일로 빼고 AI 에게 안내문과 앞부분만 준다. 다시 낼 때 새 id 를 짝지으려면 원래 결과가
    있어야 하므로 그 파일을 읽어 둔다: {tool_use_id: 원래 결과}. 작업 폴더 밖 경로는 읽지 않는다."""
    root, found = Path(workdir).resolve(), {}
    for d in events:
        m = _PERSISTED.match(d.get("tool_output") or "") if isinstance(d.get("tool_output"), str) else None
        if d["kind"] != ExecEventKind.TOOL_END.value or not m:
            continue
        path = Path(m.group(1)).resolve()
        if root in path.parents and path.is_file():
            found[d.get("tool_use_id")] = path.read_text(encoding="utf-8", errors="replace")
        else:
            log.warning("AI 응답 저장: %s 의 결과가 파일로 빠졌는데 작업 폴더에서 그 파일을 찾지 못했습니다 — %s", d.get("tool"), path)
    return found


def _joined(events: list[dict]) -> list[dict]:
    """이어진 AI 설명 조각(토큰 단위 ASSISTANT_TEXT)을 한 덩이로 — 다시 낼 때 조각 경계에 걸린 id 도 바꿔 끼울 수 있게."""
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


def capture(request, events: list[ExecEvent]) -> dict:
    """스트림 하나가 끝난 바로 뒤의 실행(결과 파일 · 큰 도구 결과도 그때 읽는다 — 교정 실행이 결과 파일을 다시 쓰기 전에)."""
    result_path = Path(request.workdir) / RESULT_FILE
    run = {"session_id": next((ev.session_id for ev in events if ev.session_id), None),
           "events": _joined([_event_dict(ev) for ev in events if ev.kind is not ExecEventKind.THINKING]),
           "result_file": result_path.read_text(encoding="utf-8") if result_path.is_file() else None,
           "context": _task_context(request.workdir)}
    run["tool_outputs_full"] = _persisted_full(run["events"], request.workdir)
    return run


# ---------------------------------------------------------------- 이 처리 건의 값으로 바꿔 끼우기
def _id_like(s: str) -> bool:
    """글 속에서도 바꿔 끼울 값: 공백 없이 5자 이상, 숫자와 숫자 아닌 글자가 함께 있는 것(처리 건 id · 경보 id · 시각)."""
    return len(s) >= 5 and not re.search(r"\s", s) and bool(re.search(r"\d", s)) and bool(re.search(r"\D", s))


CASE_FIELDS = ("alertId", "alert_id", "incident", "t", "as_of")


def _case_value(key: str, value: str) -> bool:
    """입력 가운데 처리 건마다 새로 생기는 값: 경보 · 사건 id, 경보 · 기준 시각(*_at · *_since), 날짜가 박힌 id(MW-HYD-02-N-202610282113)."""
    return key in CASE_FIELDS or key.endswith(("_at", "_since")) or bool(re.search(r"\d{8}", value))


def _selector(value) -> bool:
    """데이터를 고르는 기준 값의 모양: 공백 없는 코드(설비 HYD-01 · 부품 P-PMP-SEAL · 계획 PM-HYD-02-2000 …)."""
    return isinstance(value, str) and bool(value) and not re.search(r"\s", value) and bool(re.search(r"[\d\-_:./]", value))


FIELD_NAMES = {"asset": "설비", "part_no": "부품 번호", "kit_part_no": "부품 번호", "plan_id": "정비 계획", "bundle_peer": "함께 정비할 설비",
               "pattern": "경보 종류"}


class _Swaps:
    def __init__(self):
        self.exact: dict[str, str] = {}
        self.objects: list[tuple[dict, dict]] = []

    def _leaves(self, old, new) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            for k in old.keys() & new.keys():
                self._leaves(old[k], new[k])
        elif isinstance(old, str) and isinstance(new, str) and old and old != new:
            self.exact.setdefault(old, new)

    def pair_case(self, old: dict, new: dict, step: str) -> None:
        """녹화의 작업 기록(old)과 지금 작업 기록(new). 작업 · 처리 건 id · process_scope 는 통째로 · 값끼리 짝짓고, 입력은 처리 건마다 새로 생기는
        칸만 짝짓는다. 데이터를 고르는 기준 값이 다르면 NotRecorded."""
        for k in ("id", "proc_inst_id"):
            self._leaves(old.get(k), new.get(k))
        scope_old, scope_new = old.get("process_scope"), new.get("process_scope")
        if isinstance(scope_old, dict) and isinstance(scope_new, dict) and scope_old != scope_new:
            self.objects.append((copy.deepcopy(scope_old), copy.deepcopy(scope_new)))
            self._leaves(scope_old, scope_new)
        self._inputs(old.get("inputs"), new.get("inputs"), step)

    def _inputs(self, old, new, step, key=None) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            for k in sorted(old.keys() | new.keys()):
                self._inputs(old.get(k), new.get(k), step, k)
            return
        if old == new or key is None:
            return
        if isinstance(old, str) and isinstance(new, str) and _case_value(key, old) and _case_value(key, new):
            self.exact.setdefault(old, new)
        elif _selector(old) or _selector(new):
            label = FIELD_NAMES.get(key, key)
            raise NotRecorded(f"강의 녹화의 「{step}」은 {label} {old or '(빈 값)'} 처리 건으로 만들었습니다(지금은 {new or '(빈 값)'}). "
                              f"키 없는 PC는 녹화와 같은 {label}로만 재생합니다 — {label}을(를) {old or '(빈 값)'}(으)로 해서 다시 시작하세요.")

    def pair_created(self, old, new) -> None:
        """쓰기 도구가 새로 만든 것의 id 만 짝짓는다: 결과 문서 맨 위의 id(submit_decision · submit_purchase 의 document.id)."""
        a, b = _created(old), _created(new)
        if a is not None and b is not None and isinstance(a.get("id"), str) and isinstance(b.get("id"), str) and a["id"] != b["id"]:
            self.exact[a["id"]] = b["id"]

    def text(self, s: str) -> str:
        if s in self.exact:
            return self.exact[s]
        olds = sorted((o for o in self.exact if _id_like(o)), key=len, reverse=True)
        if not olds:
            return s
        # 한 번에 바꾼다: 차례로 replace 하면 A→B, B→A 가 함께 있을 때 둘 다 같은 값이 된다. 긴 값을 먼저 맞춘다.
        return re.sub("|".join(map(re.escape, olds)), lambda m: self.exact[m.group(0)], s)

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
    """CLI 가 보고한 MCP 도구 이름 mcp__<서버>__<도구> → (서버, 도구)."""
    if tool and tool.startswith("mcp__") and tool.count("__") >= 2:
        server, _, name = tool[len("mcp__"):].partition("__")
        return server, name
    return None


def _created(result) -> dict | None:
    if isinstance(result, dict) and result.get("result") == "ok" and isinstance(result.get("document"), dict):
        return result["document"]
    return result if isinstance(result, dict) else None


_ERROR_TEXT = re.compile(r"\A\s*(error\b|mcp error|http [45]\d\d\b)", re.I)


def _failed(output, is_error=False) -> bool:
    if is_error:
        return True
    body = _as_json(output)
    if isinstance(body, dict):
        return body.get("result") == "error" or (bool(body.get("error")) and "id" not in body and "document" not in body)
    return body is None and bool(_ERROR_TEXT.match(_text_of(output)))


def _text_of(content) -> str:
    if isinstance(content, list):
        return "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else ""


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
    """다시 낼 때 쓰기 도구를 이 PC의 서버로 부른다. 서버 설정은 이번 실행의 작업 폴더 .mcp.json(실제 실행이면 CLI 가 읽을 그 파일)."""

    def __init__(self, workdir, step: str):
        self.servers = (_read_json(Path(workdir) / MCP_CONFIG_FILENAME) or {}).get("mcpServers") or {}
        self.step, self.listed = step, {}

    def writes(self, server: str, tool: str) -> bool:
        if server not in self.servers:
            raise NotRecorded(f"강의 녹화의 「{self.step}」은 도구 서버 {server}을(를) 썼는데 지금 이 단계의 에이전트에는 그 서버가 없습니다. "
                              f"[에이전트]에서 이 에이전트의 도구 서버에 {server}을(를) 다시 넣고 실행하세요.")
        try:
            spec = mcp_check.normalize(self.servers[server])
        except ValueError as e:
            raise NotRecorded(f"도구 서버 {server}의 설정이 올바르지 않아 「{self.step}」을 재생하지 못했습니다: {e}") from None
        if spec["transport"] == "stdio":         # 이 시스템의 명령형 서버는 읽기 전용 neo4j 뿐이다
            return False
        if server not in self.listed:
            out = mcp_check.check(spec)
            if out["status"] != "ok":
                raise NotRecorded(f"도구 서버 {server}에 닿지 않아 「{self.step}」을 재생하지 못했습니다. 시작.bat을 다시 실행한 뒤 다시 하세요.")
            self.listed[server] = {t["name"]: t for t in out["tools"]}
        meta = self.listed[server].get(tool)
        if meta is None:
            raise NotRecorded(f"강의 녹화의 「{self.step}」이 쓴 도구 {server}/{tool}이(가) 지금 서버에 없어 재생하지 못했습니다. 강사에게 알려 주세요.")
        return not meta["callable"]

    def call(self, server: str, tool: str, arguments: dict) -> dict:
        # 승인 뒤 시스템 작업의 쓰기 호출과 같은 함수(입력 형식 검사 포함)
        out = mcp_check.call_effect(mcp_check.normalize(self.servers[server]), tool, arguments, max_chars=1_000_000)
        if out["status"] != "ok":
            raise NotRecorded(f"「{self.step}」에서 녹화된 AI가 부른 {server}/{tool}을(를) 이 PC에서 다시 부르지 못했습니다: {out.get('error')}")
        return out["result"]


def play(library: Library, key: str, doc: dict, i: int, request, check_stop, last: dict) -> Iterable[ExecEvent]:
    """녹화의 i번째 실행을 이 처리 건의 값으로 바꿔 끼워 낸다. 결과 파일도 녹화 당시 것을 바꿔 둔다. last 에 알림 재료를 남긴다."""
    saved = doc["runs"][i]
    step = doc.get("step") or "이 단계"
    swaps = _Swaps()
    carried = Path(request.workdir) / SWAPS_FILE
    resumed = bool((request.resume_session or "").startswith(library.prefix))
    if resumed and carried.is_file():        # 이어 하기: 앞 실행이 다시 부른 쓰기 도구의 새 id(판단 id 등)를 이어 받는다
        swaps.exact.update(json.loads(carried.read_text(encoding="utf-8")))
    elif not resumed:
        carried.unlink(missing_ok=True)
    swaps.pair_case(saved.get("context") or {}, _task_context(request.workdir), step)
    tools = _Tools(request.workdir, step)
    session = library.session(key, i)
    last.update(step=step, recorded_at=doc.get("recorded_at"), rerun=[], kept_errors=0, attempt=_attempt_label(_attempt(saved)),
                library=library.prefix)
    yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=session)
    events = saved["events"]
    live: dict[str, dict] = {}
    for n, d in enumerate(events):
        if check_stop:
            check_stop()
        d = dict(d, session_id=session if d.get("session_id") else None,
                 text=swaps.text(d.get("text") or ""), tool_input=swaps.apply(d.get("tool_input")))
        target = _mcp_target(d.get("tool"))
        if d["kind"] == ExecEventKind.TOOL_START.value and target and tools.writes(*target):
            recorded = next((e for e in events[n + 1:] if e["kind"] == ExecEventKind.TOOL_END.value
                             and e.get("tool_use_id") == d.get("tool_use_id")), None)
            old = (saved.get("tool_outputs_full") or {}).get(d.get("tool_use_id")) or (recorded.get("tool_output") if recorded else None)
            if recorded is not None and _failed(old, recorded.get("is_error")):
                # 녹화 때 오류였던 호출: 녹화된 AI 는 그 오류를 보고 고쳐 다시 불렀다 — 저장된 오류를 그대로 보인다
                last["kept_errors"] += 1
                yield _event_from(d)
                continue
            result = tools.call(*target, d["tool_input"] if isinstance(d["tool_input"], dict) else {})
            live[d.get("tool_use_id")] = result
            last["rerun"].append(f"{target[0]}/{target[1]}")
            if _failed(result["text"], result["is_error"]):
                raise NotRecorded(f"「{step}」에서 녹화된 AI가 부른 {target[0]}/{target[1]}이(가) 이 PC에서 거절됐습니다: {result['text'][:300]}")
            old, new = _as_json(old), _as_json(result["text"])
            if old is None and new is not None:
                made = (_created(new) or {}).get("id")
                raise NotRecorded(f"「{step}」의 녹화된 쓰기 결과를 읽을 수 없어 새로 만든 id 를 바꿔 끼우지 못했습니다. 강사에게 알려 주세요"
                                  + (f"(이 PC에는 이미 등록됐습니다 — id {made}, 승인 대기 목록에서 확인하세요)." if made else "."))
            swaps.pair_created(old, new)
            # 바로 남긴다 — Runner 는 결과를 받으면 이 생성기를 끝까지 돌리지 않고 닫을 수 있다
            carried.parent.mkdir(parents=True, exist_ok=True)
            carried.write_text(json.dumps(swaps.exact, ensure_ascii=False), encoding="utf-8")
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


def notice(last: dict | None) -> str | None:
    """처리 과정에 남길 한 줄. 포털 처리 과정은 긴 줄 끝을 「…」로 자르므로 핵심(새 추론 아님)을 앞에 둔다."""
    if not last:
        return None
    rerun = f" 쓰기 도구({', '.join(dict.fromkeys(last['rerun']))})는 이 PC에서 다시 실행했습니다." if last.get("rerun") else ""
    kept = (f" 저장 때 오류였던 쓰기 호출 {last['kept_errors']}건은 다시 부르지 않고 그 오류를 그대로 보였습니다." if last.get("kept_errors") else "")
    if last.get("library") == REUSE:
        return (f"같은 설정 · 같은 입력의 앞선 실행 결과를 다시 썼습니다(새로 추론하지 않음 — {last['recorded_at']} 실행).{rerun}{kept} "
                "새로 추론하게 하려면 입력이나 에이전트 설정을 바꿔 실행하세요.")
    attempt = f" · {last['attempt']}" if last.get("attempt") else ""
    return (f"AI 응답 재생 — 강사가 미리 실행해 둔 응답이며 지금 AI가 새로 추론한 것이 아닙니다(「{last['step']}」{attempt}, {last['recorded_at']} 저장)."
            f"{rerun}{kept} 같은 단계면 같은 응답을 쓰므로 지금의 경보 세기 · 사람의 답이 녹화 때와 달라도 응답은 그대로입니다.")


# ---------------------------------------------------------------- 점유 하나의 AI 응답
class Responses:
    """모드 하나와 녹화 두 묶음(수업 녹화 · 같은 요청 저장). Runner 가 점유마다 claim() 을 받아 그 점유의 스트림을 낸다."""

    def __init__(self, mode: str, *, course: Library, cache: Library | None = None):
        from .settings import MODES
        if mode not in MODES:
            raise ValueError(f"AI_MODE 는 {', '.join(MODES)} 중 하나여야 합니다(지금 {mode!r})")
        self.mode, self.course, self.cache = mode, course, cache if mode == "live" else None

    def claim(self, *, cli, slot: str | None, case: str, attempt: tuple[int, int], request_key: str | None, step: str,
              provider: str, source: dict, accepted: Callable[[dict], bool]) -> Claim:
        return Claim(self, cli=cli, slot=slot, case=case, attempt=attempt, request_key=request_key, step=step,
                     provider=provider, source=source, accepted=accepted)


class Claim:
    def __init__(self, responses: Responses, *, cli, slot, case, attempt, request_key, step, provider, source, accepted):
        self.r, self.cli = responses, cli
        self.slot, self.case, self.attempt, self.request_key = slot, case, tuple(attempt), request_key
        self.step, self.provider, self.source, self.accepted = step, provider, source, accepted
        self.captured: list[tuple[str | None, dict]] = []      # (그 스트림의 resume_session, 실행)
        self.played: str | None = None                         # 이 점유의 첫 스트림을 다시 낸 묶음(COURSE · REUSE)
        self.last: dict = {}
        self.dropped = False                                   # 돌려보내진 같은 요청 저장을 버렸다

    def needs_model(self, request) -> bool:
        """이 스트림이 실제 CLI(관문 토큰)를 부르는가 — 다시 낼 녹화가 있으면 아니다."""
        return self._source(request)[0] == "live"

    def resumable(self, session: str | None) -> str | None:
        """앞 점유가 남긴 세션으로 이어 할지(사람 답이 아닌 이어 하기 — 프롬프트는 전체). 그 모드에서 이어 받을 수 없는 세션이면 이어 하기 없이
        새로 시작한다: 키 없는 PC는 녹화 세션만, 키 있는 PC는 실제 세션과 다시 쓴 응답의 이어지는 실행만. 다시 쓴 응답을 처리 흐름이 돌려보냈는데
        그 이어지는 실행이 저장에 없으면 그 저장을 버리고 실제 AI로 새로 한다(알림에 남긴다)."""
        if not session:
            return None
        if self.r.mode == "replay":
            return session if session.startswith(COURSE) else None
        if session.startswith(COURSE):
            return None
        if session.startswith(REUSE):
            key, _, i = self.r.cache.continuation(session) if self.r.cache is not None else (None, None, None)
            if i is None:
                if key and self.r.cache is not None:
                    self.r.cache.delete(key)
                self.dropped = True
                return None
        return session

    def _source(self, request):
        resume = request.resume_session or ""
        if resume.startswith(COURSE):
            return ("play",) + self.r.course.continuation(resume) + (self.r.course,)
        if resume.startswith(REUSE) and self.r.cache is not None:
            return ("play",) + self.r.cache.continuation(resume) + (self.r.cache,)
        if self.r.mode == "replay":           # 키 없는 PC는 실제 모델을 부르지 않는다 — 녹화가 아닌 세션의 이어 하기는 녹화 밖
            if resume:
                return ("play", None, None, None, self.r.course)
            key = course_key(self.slot, self.case) if self.slot else None
            doc = self.r.course.load(key) if key else None
            i = next((n for n, run in enumerate(doc["runs"]) if _attempt(run) == self.attempt), None) if doc else None
            return ("play", key, doc, i, self.r.course)
        if resume:
            return ("live",)
        if self.r.cache is not None and self.request_key:
            doc = self.r.cache.load(self.request_key)
            if doc is not None:
                if self.accepted(doc.get("source") or {}):
                    return ("play", self.request_key, doc, 0, self.r.cache)
                log.info("같은 요청 저장 %s: 그 실행의 작업이 지금은 끝남이 아니라(돌려보냄 · 재작업 · 초기화) 버리고 새로 실행합니다", self.request_key)
                self.r.cache.delete(self.request_key)
        return ("live",)

    def __call__(self, provider, request, env, *, check_stop=None) -> Iterable[ExecEvent]:
        source = self._source(request)
        if source[0] == "play":
            _, key, doc, i, library = source
            if doc is None or i is None:
                if library is self.r.cache and key:
                    self.r.cache.delete(key)
                raise NotRecorded(self._missing(request, doc, library))
            self.last = {}
            if not request.resume_session:
                self.played = library.prefix
            yield from play(library, key, doc, i, request, check_stop, self.last)
            return
        self.last = {}
        events: list[ExecEvent] = []
        gen = self.cli(provider, request, env, check_stop=check_stop) if getattr(self.cli, "accepts_check_stop", False) \
            else self.cli(provider, request, env)
        for ev in gen:
            events.append(ev)
            yield ev
        self.captured.append((request.resume_session, capture(request, events)))

    accepts_check_stop = True

    def _missing(self, request, doc, library) -> str:
        step = self.step or "이 단계"
        if (request.resume_session or "").startswith(REUSE):
            return (f"앞선 실행 결과를 다시 쓰던 「{step}」에 이어지는 응답이 없어 멈췄습니다. 이 단계를 다시 실행하면 실제 AI로 새로 실행합니다.")
        if request.resume_session:
            return (f"강의 녹화에는 「{step}」의 이어지는 응답(결과를 고쳐 다시 낸 응답 · 사람 답 뒤 이어 한 응답)이 없습니다. "
                    "키 없는 PC는 녹화된 응답까지만 재생합니다 — 이 처리 건은 닫고 새로 시작하세요.")
        if not self.slot:
            return (f"「{step}」은 강의 녹화가 있는 수업 AI 단계가 아니라 키 없는 PC에서는 AI가 하지 않습니다. "
                    "수업에서 준비한 흐름(냉각 · 정기 정비 · 예비품 구매 · 교대 인수인계)과 질문으로 실습하세요.")
        if self.slot == "question":
            asked = library.questions()
            return ("이 PC는 키 없이 강의에서 다룬 질문에만 답합니다. 다룬 질문: " + (" / ".join(f"「{q}」" for q in asked) if asked else "없음")
                    + ". 질문 칸 아래의 질문 단추를 눌러 넣고 보내세요.")
        g, n = self.attempt
        if doc is not None and n:
            return (f"강의 녹화에는 「{step}」을 보류 뒤 다시 평가한 응답이 없습니다(첫 평가까지만 녹화돼 있습니다). "
                    "키 없는 PC에서는 재평가 대신 보류 사유를 확인하고 사람이 처리하세요.")
        if doc is not None and g:
            return (f"강의 녹화에는 「{step}」을 재작업으로 다시 한 응답이 없습니다(첫 작업까지만 녹화돼 있습니다). "
                    "키 없는 PC에서는 재작업 대신 새 처리 건으로 다시 시작하세요.")
        if self.slot.startswith("handover/draft-"):
            drafts = sorted({d["slot"] for _, d in library.docs() if str(d.get("slot") or "").startswith("handover/draft-")})
            return (f"강의 녹화에는 「{step}」의 응답이 없습니다(교대 인계안은 보완 요청 {max(0, len(drafts) - 1)}번까지 녹화돼 있습니다). "
                    "키 없는 PC에서는 그 뒤로 보완 요청 대신 [확인]으로 넘기세요.")
        return (f"강의 녹화에는 이 종류의 처리 건에 대한 「{step}」 응답이 없습니다. 키 없는 PC에서는 수업에서 다룬 경보로 실습하세요.")

    def notice(self) -> str | None:
        if self.dropped and not self.last:
            return "앞서 다시 쓴 같은 요청의 결과를 처리 흐름이 돌려보내, 그 저장을 버리고 실제 AI로 새로 실행했습니다."
        return notice(self.last)

    def keep(self, outcome: str, secrets) -> None:
        """점유가 저장된 결과로 끝났을 때 받아 둔 실행을 남긴다. 실패 · 취소로 끝난 점유는 부르지 않는다(좋은 녹화를 덮지 않는다)."""
        if outcome not in STORED or not self.captured:
            return
        if self.r.mode == "record":
            if not self.slot:
                log.warning("「%s」은 수업 AI 자리가 아니라 녹화하지 않았습니다", self.step)
                return
            for resume, run in self.captured:
                self._keep_course(resume, run, secrets)
        elif self.r.mode == "live" and outcome == "submitted" and self.request_key and self.played is None \
                and self.captured[0][0] is None:      # 이 점유가 새로 시작해 실제 AI로 끝까지 간 실행만
            doc = {"request": self.request_key, "step": self.step, "case": self.case, "provider": self.provider,
                   "source": self.source, "runs": [run for _, run in self.captured]}
            self.r.cache.write(self.request_key, doc, secrets)

    def _keep_course(self, resume, run, secrets) -> None:
        library = self.r.course
        owner = library.owner_of(resume) if resume else None
        if owner is not None:                        # 같은 세션을 이어 간 실행: 그 녹화 뒤에 붙인다(그 뒤의 옛 이어 하기는 버린다)
            key, doc, i = owner
            if doc["runs"][i].get("attempt"):
                run = dict(run, attempt=doc["runs"][i]["attempt"])
            doc["runs"] = doc["runs"][: i + 1] + [run]
        else:
            key = course_key(self.slot, self.case)
            doc = {"slot": self.slot, "case": self.case, "step": self.step, "provider": self.provider, "runs": [run]}
            if self.attempt != (0, 0):
                # 재평가 · 재작업 실행: 같은 녹화에서 앞 차례 실행 뒤에 붙인다(첫 실행을 덮어쓰지 않는다). 이 차례와 그 뒤 차례의 옛 실행은 버린다
                run["attempt"] = {"generation": self.attempt[0], "reassessment": self.attempt[1]}
                old = library.load(key)
                if old is not None:
                    doc = dict(old, runs=[r for r in old["runs"] if _attempt(r) < self.attempt] + [run])
        library.write(key, doc, secrets)


# ---------------------------------------------------------------- 녹화 목록(강사 확인)
def listing(library: Library) -> tuple[list[dict], list[str]]:
    """(녹화마다 한 줄, 녹화가 없는 수업 AI 자리). 자리는 서버의 정본(course_policy.AI_SLOTS)에서 읽는다."""
    from procsvc.course_policy import AI_SLOTS
    rows = []
    for key, doc in library.docs():
        path = library.file_of(key)
        later = [l for l in dict.fromkeys(_attempt_label(_attempt(r)) for r in doc["runs"]) if l]
        rows.append({"file": path.name, "slot": doc.get("slot") or "", "step": doc.get("step") or "", "case": doc.get("case") or "",
                     "runs": len(doc["runs"]), "attempts": later, "recorded_at": doc.get("recorded_at"),
                     "kb": max(1, round(path.stat().st_size / 1024)),
                     "masked": gzip.decompress(path.read_bytes()).decode("utf-8").count(REDACTED),
                     "course": doc.get("slot") in AI_SLOTS.values()})
    missing = sorted(set(AI_SLOTS.values()) - {r["slot"] for r in rows})
    return sorted(rows, key=lambda r: (r["slot"], r["case"])), missing


def main(argv: list[str] | None = None) -> int:
    """python -m worker.ai_replay [폴더] — 수업 녹화 목록과 빠진 수업 AI 자리(있으면 종료 코드 1). 기본 폴더는 AI_REPLAY_DIR."""
    import sys
    from .settings import settings
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else settings.ai_replay_dir
    rows, missing = listing(Library(root))
    print(f"수업 녹화: {root} — {len(rows)}개")
    for r in rows:
        masked = f", 비밀값 가림 {r['masked']}곳" if r["masked"] else ""
        later = f"(그 가운데 {', '.join(r['attempts'])})" if r["attempts"] else ""
        stale = "" if r["course"] else "  ← 수업 AI 자리가 아님(쓰이지 않는 녹화)"
        print(f"  {r['recorded_at']}  {r['slot'] or '-'}  {r['case'] or '-'}  「{r['step']}」  실행 {r['runs']}개{later} · {r['kb']} KB{masked}  ({r['file']}){stale}")
    for slot in missing:
        print(f"  [녹화 없음] {slot} — 키 없는 PC에서 이 자리는 「녹화 범위 밖」으로 멈춥니다")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
