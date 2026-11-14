"""AI 응답 저장 · 다시 쓰기 — 한 장치(같은 녹화 형식 · 같은 재생기)로 세 모드를 돈다. 문서: workspace/개발/문서/재생모드.md

    AI_MODE=live    키 있는 PC: 실제 AI. 같은 설정 · 같은 입력으로 앞서 성공한 실행이 이 PC에 있으면 그 응답을 다시 쓴다(같은 요청 저장)
    AI_MODE=record  강사: 실제 AI로 실행하고, 점유가 제출 또는 사람 질문으로 끝나면 그 실행을 수업 녹화로 남긴다(근거 부족 보류로 끝난
                  실행은 녹화하지 않는다 — 좋은 녹화를 보류로 덮어 키 없는 학생이 늘 보류를 보게 되던 것, 검진 G1-22)
    AI_MODE=replay  키 없는 PC: CLI · 모델을 부르지 않고 그 수업 AI 자리의 강사 녹화를 낸다

녹화를 찾는 열쇠
  수업 녹화(AI_REPLAY_DIR — 저장소 it/agent-worker/replay/): 서버가 준 수업 AI 자리(정본 procsvc/course_policy, 워커는 process 의 판정 ·
    GET /api/course-access 로만 읽는다 — c3_cooling/T_agent · handover/draft-1~3 · question)와 무엇에 대한 처리 건인가(경보 종류 · 질문 글). 학생이 바꿀 수 있는 작업 이름 · 흐름 id 는 열쇠가 아니다 —
    이름을 바꾼 교대 흐름도 같은 녹화를 낸다. 같은 작업을 새로 하는 실행(재작업 세대 · 보류 뒤 재평가)은 실행 차례 runs[].attempt 로 가린다.
    그 차례의 녹화가 없는 다시 수행(재작업 세대)은 첫 실행을 다시 낸다(Claim._run_for) — 다시 수행은 같은 단계를 같은 입력으로 새로 하는
    것이고(다시 수행의 사유는 AI 입력에 들어가지 않는다 — 새 작업 행), 저장된 응답은 입력이 같으면 같은 답을 내는 것이 본뜻이다. 쓰기 도구는
    이 PC에서 다시 부르므로 등록되는 판단은 지금 값으로 계산된다. 보류 뒤 재평가는 그렇지 않다(조건이 바뀌어 다시 보는 것이라 입력이 다르다).
  같은 요청 저장(이 PC의 <작업 공간>/.ai-cache): 실행에 영향을 주는 것 전부의 해시(정의 · 단계 · 지시 · 입력 · 피드백 · 폼 · 에이전트 설정 ·
    업무 규칙 · 스킬 본문 · 도구 서버 · 모델 — runner._request_key). 하나라도 다르면 새로 실행한다. 결과 검사를 통과해 제출한 실행만
    저장하고, 그 실행의 작업이 지금도 끝남(DONE — 처리 흐름이 결과를 받아들임)일 때만 다시 쓴다. 질문(「에이전트에게 질문」)은 저장하지
    않는다 — 답은 지금의 지식 그래프 · 업무 DB 를 읽어 만들고 그 상태는 열쇠에 없어서, 적재 · 재고가 바뀐 뒤 같은 질문에 옛 답이 나왔다
    (검진 G1-09). 작업 행이 없어졌거나 작업 폴더 보존 기간(72 시간) 동안 다시 쓰이지 않은 저장은 작업 폴더 정리(sweep_cache)가 지운다.

녹화 하나 = 파일 하나(<열쇠>.json.gz). 안에는 실행이 순서대로 있다 — 첫 실행, 같은 세션을 이어 간 실행(사람 답 뒤 · 결과 교정 · 처리 흐름이
결과를 돌려보낸 뒤). 다시 낼 때 이어 하기는 세션 replay:<열쇠>:<순번>(수업 녹화) · reuse:<열쇠>:<순번>(같은 요청)으로 다음 실행을 고른다.
워커가 다시 켜져 같은 작업을 다시 잡으면(임대 만료 뒤 재점유) 끊긴 실행을 처음부터 다시 낸다(resume_after).

다시 낼 때 이 처리 건의 값으로 바꿔 끼우는 것은 처리 건마다 새로 생기는 값(작업 · 처리 건 · 점유 · 경보 id · 시각)뿐이다. 데이터를 고르는
입력(설비 · 부품 · 정비 계획 같은 기준 값)이 녹화와 다르면 바꿔 끼우지 않고 멈춘다 — 다른 설비의 실측을 이 설비 것처럼 보이지 않게.
쓰기 도구(서버가 읽기 전용으로 표시하지 않은 도구 — 판단 등록 submit_decision · submit_purchase)는 이 PC 서버로 다시 부르고, 돌려받은 새 id 를
응답 · 결과 파일에 바꿔 끼운다. 녹화 때 오류였던 쓰기 호출은 다시 부르지 않는다. 녹화가 쓴 도구 서버 · 도구가 지금 단계에 없으면 멈춘다.
다시 부른 쓰기가 「아직 값을 받지 못함」(도구 봉투의 error_kind UNAVAILABLE)이나 「서버에 닿지 못함」으로 안 됐으면 같은 실행 안에서
WRITE_RETRY_WAITS_S 간격으로 다시 부른다 — 아무것도 등록되지 않은 것이 분명한 오류만이다. 그래도 안 되면 지어내지 않고 실패로 둔다.
읽기 도구의 결과는 저장된 것을 그대로 보인다(AI 설명 · 결과 글이 그 결과로 쓰였다). 그 가운데 표(열 이름과 행)를 돌려준 조회는 이 PC의 서버로
다시 불러 저장된 결과와 견주고(「읽기 조회 견주기」 절 — read_gap), 다르거나 견주지 못했으면 멈추지 않고 처리 과정 한 줄로 알린다(notice).

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from cliagents import ExecEvent, ExecEventKind
from hydcommon.data_sources import SOURCES as DATA_SOURCES
from hydcommon.tool_result import UNAVAILABLE
from hydcommon.words import josa
from procsvc import mcp_check

from .bridge import MCP_CONFIG_FILENAME
from .course_access import Stop
from .diagnostics import REDACTED, hide
from .events import skill_files
from .workspace import RESULT_FILE

log = logging.getLogger("worker.ai_replay")
FORMAT = "hyd-ai-replay/3"
COURSE = "replay:"      # 수업 녹화를 다시 낸 세션
REUSE = "reuse:"        # 같은 요청 저장을 다시 쓴 세션
TASK_FILE = "context/task.json"
SWAPS_FILE = "context/ai-replay-swaps.json"     # 이어 하기 실행이 이어 받을 바꿔 끼울 값(저장 id → 이 PC의 새 id)
QUESTION_PREFIX = "질문 "
DEFERRED_MARK = "[DEFERRED]"       # task_deferral.defer 가 작업 log 에 남기는 표시 — 보류 한 번에 하나
COURSE_KEPT = ("submitted", "asked")            # 수업 녹화로 남기는 끝(사람 질문은 그 뒤 이어지는 실행과 한 녹화)
CACHE_KEPT = ("submitted",)                     # 같은 요청 저장으로 남기는 끝
UNCACHED_SLOTS = ("question",)                  # 지금의 지식 · 업무 상태로 답하는 자리 — 같은 요청 저장을 쓰지 않는다(G1-09)
#: 다시 부르는 쓰기 도구(submit_decision · submit_purchase)는 판단 전체를 계산한다 — 원천 읽기 한도(agent mcp_ent 15초) · process 제출
#: 한도(10초)보다 길게 기다린다. 연결 확인용 기본 10초로는 바쁜 PC에서 정상 판단이 「응답하지 않았습니다」로 멈췄다(2026-10-30 테스트 실측).
WRITE_CALL_TIMEOUT_S = 60.0
#: 다시 부른 쓰기 도구가 「다시 시도할 만한 오류」로 안 됐을 때 다음 시도까지 기다리는 벽시계 초(첫 시도 + 이 수만큼 다시). 다시 시도할 만한
#: 오류는 아무것도 등록되지 않은 것이 분명한 둘뿐이다: ① 도구가 UNAVAILABLE 로 답함(판단에 쓸 값을 원천에서 아직 받지 못함 — 판단 서비스는
#: 값을 8초 동안 다시 읽고 나서야 이렇게 답한다, agentsvc/forecasting.SOURCE_REREAD_FOR_S) ② 도구 서버에 닿지 못함(연결 거부 · 주소 못 찾음 ·
#: 연결 자리 없음 — 요청이 서버에 가지 않았다). 시간 초과 · 끊김은 다시 부르지 않는다 — 등록됐는데 답만 못 받았을 수 있고, 그때 다시 부르면
#: process 가 「이 작업의 판단이 이미 있다」로 거절해 엉뚱한 까닭이 남는다. 수집이 잠깐 밀린 한 번이 그 단계의 실패로 굳던 것(2026-11-14
#: 01:01 처리 건)을 막는 값이다: 가장 길게 8 + 5 + 8 + 10 + 8 = 39초 동안 세 번 본다.
WRITE_RETRY_WAITS_S = (5.0, 10.0)
UNREACHED_KINDS = ("refused", "unreachable", "busy")      # mcp_check 의 연결 오류 종류 가운데 요청이 서버에 가지 않은 것


class NotRecorded(Stop):
    """녹화(저장)에 없는 실행 — 문장은 학생이 할 일까지 쓴다(「강사」 · 「녹화」라는 말 없이, 재생 모드가 지원하지 않는 행동으로)."""
    title = "재생 모드에서 지원하지 않는 AI 단계"


class WriteFailed(Stop):
    """AI가 고른 결과를 이 PC에 등록(쓰기 도구)하지 못했다 — 재생 모드가 지원하지 않는 행동이 아니라 이 PC의 지금 상태 때문이다. 문장은 무엇을
    하다가 · 왜 · 다음에 무엇을. 도구의 내부 이름과 응답 원문은 raw(원문 칸)에만 싣는다."""
    title = "AI 판단 등록 실패"


RETRY_STEP = "이 단계 아래의 「다시 수행」으로 이 단계를 다시 실행해 주세요."     # 처리 건 화면의 멈춘 단계 아래 복구 묶음


def _wait(seconds: float, check_stop) -> None:
    """다음 시도까지 기다린다 — 그동안에도 취소 · 임대 갱신(check_stop)은 1초마다 본다."""
    import time
    until = time.monotonic() + seconds
    while (left := until - time.monotonic()) > 0:
        if check_stop:
            check_stop()
        time.sleep(min(1.0, left))


_ERROR_NAME = re.compile(r"\A\s*[A-Za-z_][\w.]*(?:Error|Exception)\s*:\s*")


def _tool_reason(text) -> str:
    """도구가 돌려준 오류 응답에서 사람이 읽는 까닭만(봉투의 message — 판단 서비스가 한국어로 쓴다). 봉투가 아니거나 까닭이 없으면 빈 글."""
    body = _as_json(text)
    reason = body.get("message") if isinstance(body, dict) else None
    reason = _ERROR_NAME.sub("", reason).strip() if isinstance(reason, str) else ""
    return reason.rstrip(" .") if reason else ""


REPLAY = "AI 키가 없을 때 쓰는 재생 모드에서는"   # 벗어난 행동의 안내 첫머리 — 화면에 재생 모드를 밝히는 곳은 이 안내뿐이다


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
        try:
            doc = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        except (OSError, EOFError, UnicodeDecodeError, ValueError) as exc:   # 깨진 gzip · 잘린 파일 · 글자 아님 · JSON 아님
            raise RuntimeError(f"저장된 AI 응답 파일을 읽지 못했습니다({type(exc).__name__}: {exc}): {path}") from exc
        if doc.get("format") != FORMAT:
            raise RuntimeError(f"저장된 AI 응답 파일의 형식이 다릅니다({doc.get('format')} — 지금은 {FORMAT}): {path}")
        return doc

    def load(self, key: str) -> dict | None:
        path = self.file_of(key)
        return self._read(path) if path.is_file() else None

    def delete(self, key: str) -> None:
        self.file_of(key).unlink(missing_ok=True)

    def touch(self, key: str) -> None:
        """다시 쓴 저장의 시각을 지금으로(보존 기간은 마지막으로 쓰인 때부터 — sweep_cache)."""
        self.file_of(key).touch()

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


def partial_chunk(ev) -> bool:
    """CLI 가 토큰마다 보내는 부분 응답 조각(stream_event 의 content_block_delta — 라이브러리가 일부러 UNKNOWN 으로 둔다). 같은 내용이
    완성된 이벤트(설명 글 · 도구 호출)로 다시 오므로 처리 기록 · 화면 어디에도 쓰이지 않는데, 녹화 · 실행 추적의 95 %를 차지했다(검진 G1-08).
    녹화 · 같은 요청 저장 · 실행 추적에 남기지 않고, 옛 녹화를 다시 낼 때도 건너뛴다. 모델 호출 경계(message_start)는 남긴다."""
    kind = ev.kind.value if isinstance(ev, ExecEvent) else ev.get("kind")
    raw = (ev.raw if isinstance(ev, ExecEvent) else ev.get("raw")) or {}
    return kind == ExecEventKind.UNKNOWN.value and isinstance(raw, dict) and raw.get("type") == "stream_event" \
        and (raw.get("event") or {}).get("type") == "content_block_delta"


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
           "events": _joined([_event_dict(ev) for ev in events if ev.kind is not ExecEventKind.THINKING and not partial_chunk(ev)]),
           "result_file": result_path.read_text(encoding="utf-8") if result_path.is_file() else None,
           "context": _task_context(request.workdir)}
    run["tool_outputs_full"] = _persisted_full(run["events"], request.workdir)
    return run


# ---------------------------------------------------------------- 이 처리 건의 값으로 바꿔 끼우기
def _id_like(s: str) -> bool:
    """글 속에서도 바꿔 끼울 값: 공백 없이 5자 이상, 숫자와 숫자 아닌 글자가 함께 있는 것(처리 건 id · 경보 id · 시각)."""
    return len(s) >= 5 and not re.search(r"\s", s) and bool(re.search(r"\d", s)) and bool(re.search(r"\D", s))


#: 데이터를 고르는 입력 — 녹화와 다르면 바꿔 끼우지 않고 멈춘다(다른 설비 · 부품의 실측을 이 처리 건 것처럼 보이지 않게). 이 표 한 곳이 정한다:
#: 값의 모양(공백 없는 코드)으로 가르면 「버튼을 누른 사람」(requested_user) · 짧은 보완 요청 글까지 멈춤 사유가 됐다(검진 G1-03).
FIELD_NAMES = {"asset": "설비", "part_no": "부품 번호", "kit_part_no": "부품 번호", "plan_id": "정비 계획", "bundle_peer": "함께 정비할 설비",
               "pattern": "경보 종류"}


def _flat(text) -> str:
    """사람이 넣은 글을 견줄 때의 꼴 — 띄어쓰기와 끝의 물음표 · 마침표 차이는 같은 글이다(question_case 와 같은 기준)."""
    flat = " ".join(str(text or "").split())
    return flat.rstrip(" ?？.!。") or flat


def typed_gap(old, new) -> list[tuple[str, str]]:
    """저장된 실행의 입력(old)과 이 처리 건의 입력(new)에서 사람이 넣은 글이 다른 것 → [(저장된 글, 지금 글)]. 준비된 설명 · 결과 글은 저장된
    글을 두고 쓰였다(교대 인계안의 「정비 완료 메모와 달리 …」) — 지금 넣은 글이 다르면 그 글은 내 입력에 대한 답이 아니다. 사람이 넣은 글 =
    입력 맨 위의 글 값 가운데 데이터를 고르는 값(FIELD_NAMES — 다르면 멈춘다)도, 처리 건마다 새로 생기는 값(id 모양 — 경보 · 사건 id · 시각,
    바꿔 끼운다)도 아닌 것. 경보 안에 든 값(alert.…)은 시스템이 만든 것이라 보지 않는다."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return []
    out = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if key in FIELD_NAMES or not all(v is None or isinstance(v, str) for v in (a, b)) or _id_like(a or "") or _id_like(b or ""):
            continue
        if _flat(a) != _flat(b):
            out.append((" ".join((a or "").split()), " ".join((b or "").split())))
    return out


class _Swaps:
    def __init__(self):
        self.exact: dict[str, str] = {}
        self.objects: list[tuple[dict, dict]] = []
        self.typed: list[tuple[str, str]] = []      # 사람이 넣은 글이 저장된 실행과 다른 것(typed_gap) — 알림 재료

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
        self.typed = typed_gap(old.get("inputs"), new.get("inputs"))

    def _inputs(self, old, new, step, key=None) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            for k in sorted(old.keys() | new.keys()):
                self._inputs(old.get(k), new.get(k), step, k)
            return
        if old == new or key is None:
            return
        if key in FIELD_NAMES:
            label = FIELD_NAMES[key]
            raise NotRecorded(f"{REPLAY} {josa(f'「{step}」', '을')} {label} {old or '(빈 값)'}인 처리 건으로만 진행할 수 있습니다(지금은 {new or '(빈 값)'}). "
                              f"{josa(label, '을')} {josa(old or '(빈 값)', '으로')} 바꿔 다시 시작해 주세요.")
        if isinstance(old, str) and isinstance(new, str) and old and new:
            # 처리 건마다 달라지는 값(경보 · 사건 id · 시각)과 데이터를 고르지 않는 값(누른 사람 · 보완 요청 글)은 녹화 글 속의 그 값만
            # 이 처리 건의 값으로 바꾼다(글 속 부분 바꾸기는 id 모양 값만 — _Swaps.text)
            self.exact.setdefault(old, new)

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


def _cards(doc: dict) -> dict[str, dict]:
    """등록된 판단 문서의 카드(submit_decision 은 cards, submit_purchase 는 options) — id 로."""
    return {c["id"]: c for c in (doc.get("options") or doc.get("cards") or []) if isinstance(c, dict) and isinstance(c.get("id"), str)}


def decision_gap(old, new) -> tuple[list[str], list[str]]:
    """녹화 때 등록된 판단(old)과 이 PC가 방금 다시 계산해 등록한 판단(new)의 차이 → (판단이 달라진 것, 수치만 달라진 것). 녹화의 AI 설명 ·
    결과 글은 old 를 말하고 승인 카드는 new 다. 판단이 달라졌으면(권장 카드 · 실행할 수 있는 카드) 그 설명은 이 처리 건의 것이 아니다. 수치는
    업무 값으로 정해지는 구매 수량 · 비교 총비용만 견준다 — 점수 · 예측은 설비 측정값을 따라 실행마다 조금씩 달라 같은 판단에서도 다르다."""
    a, b = _created(old), _created(new)
    if not (isinstance(a, dict) and isinstance(b, dict) and "recommended" in a and "recommended" in b):
        return [], []
    ca, cb = _cards(a), _cards(b)
    name = lambda i: f"「{(ca.get(i) or cb.get(i) or {}).get('name') or i}」"   # noqa: E731
    changed, numbers = [], []
    if a["recommended"] != b["recommended"]:
        changed.append(f"권장 조치가 준비된 판단은 {name(a['recommended'])}인데 지금 계산은 {name(b['recommended'])}입니다")
    ok_a, ok_b = {i for i, c in ca.items() if c.get("feasible")}, {i for i, c in cb.items() if c.get("feasible")}
    if ok_a != ok_b:
        changed.append("실행할 수 있는 후보가 준비된 판단은 " + (", ".join(map(name, sorted(ok_a))) or "없음") + "인데 지금 계산은 "
                       + (", ".join(map(name, sorted(ok_b))) or "없음") + "입니다")
    for i in sorted(ca.keys() & cb.keys(), key=lambda i: ca[i].get("rank") or 0):
        ea, eb = ca[i].get("economicComparison") or {}, cb[i].get("economicComparison") or {}
        parts = [f"{label} {ea[k]:g} → {eb[k]:g}{unit}" for k, label, unit in (("quantity", "수량", "개"), ("total_cost", "비교 총비용", "만 원"))
                 if isinstance(ea.get(k), (int, float)) and isinstance(eb.get(k), (int, float)) and ea[k] != eb[k]]
        if parts:
            numbers.append(f"{name(i)} " + " · ".join(parts))
    return changed, numbers


# ---------------------------------------------------------------- 읽기 조회 견주기
#: 저장된 실행이 한 조회의 결과는 그 실행을 뜬 PC의 그때 값이다. AI 설명 · 결과 글은 그 값을 사실로 적으므로(교대 인계안의 「작업지시 두 건
#: 배정됨」), 이 PC의 지금 값이 다르면 글이 이 PC에 없는 것을 말한다. 그래서 같은 조회를 이 PC에서 다시 불러 견준다. 정한 것:
#:   무엇을  HTTP 도구 서버의 읽기 도구 호출 가운데 저장된 결과가 표(열 이름 columns + 행 rows — HYD 도구 봉투의 document 또는 맨 위)인 것.
#:          구조 설명(스키마 · 목록)은 사실을 적는 값이 아니라 견주지 않는다. 지식 그래프 조회처럼 결과가 표 꼴이 아닌 조회와, 워커 자신의
#:          조회 창구(명령형 — 실행 밖에서 다시 부르는 길이 없다)도 견주지 않는다(한계 — 재생모드.md 3절 4번).
#:   같다    열 이름이 같고, 행의 순서를 무시하고, 시각 칸을 뺀 나머지 값이 모두 같다. 순서는 시각으로 정렬한 조회에서 PC마다 다르고, 시각
#:          (만든 때 · 고친 때 · 측정한 때)은 같은 일을 한 PC끼리도 늘 다르다 — 그것으로 「다름」을 내면 늘 뜨는 거짓 알림이 된다. 번호(정비
#:          요청 번호 등)는 뺄 수 없다: 글이 그 번호를 적고, 이 PC에는 그 번호가 없다.
#:   설비 측정값처럼 늘 달라지는 조회는 따로 가르지 않는다 — 다시 부르면 값이 다르고, 「글 속의 측정값은 준비 당시 값」이라는 알림이 그대로 참이다.
_MOMENT = re.compile(r"\A\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\Z")
_SQL_SOURCE = re.compile(r"\b(from|join)\s+([A-Za-z_][\w.]*)(\s*\()?", re.I)
_SQL_TEXT = re.compile(r"'(?:[^']|'')*'")
_SQL_NAMED = re.compile(r"\b([A-Za-z_]\w*)\s+as\s*(?:not\s+materialized\s*|materialized\s*)?\(", re.I)
_SQL_FROM_INSIDE = ("extract", "substring", "trim", "overlay")     # 이 함수의 괄호 안 FROM 은 자료를 읽는 FROM 이 아니다
MOMENT = "(시각)"


def _table(content) -> tuple[list, list] | None:
    """도구 결과가 표이면 (열 이름, 행). 표가 아니거나 오류 봉투면 None."""
    body = _as_json(content)
    doc = body.get("document") if isinstance(body, dict) and isinstance(body.get("document"), dict) else body
    if not isinstance(doc, dict) or (isinstance(body, dict) and body.get("result") == "error"):
        return None
    columns, rows = doc.get("columns"), doc.get("rows")
    if isinstance(columns, list) and isinstance(rows, list) and all(isinstance(r, list) for r in rows):
        return columns, rows
    return None


def _row_keys(rows: list) -> list[str]:
    """행마다 견줄 글 — 시각 칸은 한 표시로 바꾸고, 순서를 무시하게 정렬한다."""
    return sorted(json.dumps([MOMENT if isinstance(c, str) and _MOMENT.match(c) else c for c in row], ensure_ascii=False, sort_keys=True, default=str)
                  for row in rows)


def read_gap(old: tuple[list, list], new: tuple[list, list]) -> tuple[int, int] | None:
    """저장된 조회 결과(old)와 이 PC에서 방금 다시 조회한 결과(new)가 다르면 (저장된 행 수, 지금 행 수). 같으면(머리의 「같다」) None."""
    (old_columns, old_rows), (new_columns, new_rows) = old, new
    if len(old_rows) != len(new_rows) or old_columns != new_columns or _row_keys(old_rows) != _row_keys(new_rows):
        return len(old_rows), len(new_rows)
    return None


def _inside_function(sql: str, at: int) -> str:
    """sql[at] 을 감싼 가장 안쪽 괄호 바로 앞의 낱말(소문자) — 괄호 밖이거나 낱말이 없으면 빈 글."""
    depth = 0
    for i in range(at - 1, -1, -1):
        if sql[i] == ")":
            depth += 1
        elif sql[i] == "(":
            if depth == 0:
                word = re.search(r"([A-Za-z_]\w*)\s*\Z", sql[:i])
                return word.group(1).lower() if word else ""
            depth -= 1
    return ""


def sql_sources(sql: str) -> list[str]:
    """조회문이 읽은 자료 이름(FROM · JOIN 뒤의 표 이름)을 나온 차례로. 자료가 아닌 것은 뺀다: 글 값 안의 낱말, 함수 안의 FROM
    (EXTRACT(EPOCH FROM 칸) — 칸 이름이 자료 이름으로 잡혔다), 함수를 읽는 FROM(generate_series(…)), 조회문이 스스로 지은 이름(WITH 이름 AS (…))."""
    sql = _SQL_TEXT.sub("''", sql)
    own = {name.lower() for name in _SQL_NAMED.findall(sql)}
    found = []
    for m in _SQL_SOURCE.finditer(sql):
        word, name, call = m.groups()
        if call or name.lower() in own or (word.lower() == "from" and _inside_function(sql, m.start()) in _SQL_FROM_INSIDE):
            continue
        found.append(name)
    return list(dict.fromkeys(found))


def source_label(name: str) -> str | None:
    """자료 이름 <스키마>.<표> 가 기본 제공 데이터 원천의 것이면 그 원천의 이름(「업무 DB」 · 「시계열 DB」 · 「옛 설비 DB」 — 정본
    hydcommon.data_sources.SOURCES, 데이터 원천 화면이 보이는 이름). 표마다의 한국어 이름은 정본이 없다(표 설명이 달린 업무 표는 셋뿐이다)."""
    schema, _, table = name.rpartition(".")
    for source in DATA_SOURCES.values():
        if schema == source["schema"] and table in (source.get("tables") or (table,)):
            return source["label"]
    return None


def read_subject(server: str, arguments) -> str:
    """알림에서 그 조회를 가리키는 말. 조회문이 입력에 있으면 그 조회가 읽은 자료: 기본 제공 데이터 원천의 표는 원천 이름을 앞에 두고 표 이름을
    괄호에(「업무 DB 조회(ent.work_orders)」 — 처리 과정의 그 조회에 같은 표 이름이 보인다), 그 밖의 표는 표 이름만. 조회문이 없거나 읽은
    자료를 찾지 못하면 도구 서버 이름. 도구의 내부 이름은 쓰지 않는다."""
    texts = [v for v in arguments.values() if isinstance(v, str)] if isinstance(arguments, dict) else []
    names = list(dict.fromkeys(name for text in texts for name in sql_sources(text)))
    if not names:
        return f"「{server}」 조회"
    labels = list(dict.fromkeys(source_label(name) for name in names))
    if len(labels) == 1 and labels[0]:
        return f"{labels[0]} 조회({' · '.join(names)})"
    return " · ".join(names) + " 조회"


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

    def __init__(self, workdir, step: str, check_stop=None):
        self.servers = (_read_json(Path(workdir) / MCP_CONFIG_FILENAME) or {}).get("mcpServers") or {}
        self.step, self.listed, self.check_stop = step, {}, check_stop
        self.unreached: set[str] = set()         # 읽기 조회를 다시 부르다 닿지 못한 서버 — 그 실행의 남은 조회는 기다리지 않고 「견주지 못함」

    def writes(self, server: str, tool: str) -> bool:
        if server not in self.servers:
            raise NotRecorded(f"{REPLAY} {josa(f'「{self.step}」', '을')} 진행하려면 이 단계 에이전트의 도구 서버에 {josa(f'「{server}」', '이')} 있어야 합니다. "
                              f"AI 에이전트 화면에서 이 에이전트의 도구 서버에 {josa(f'「{server}」', '을')} 다시 고른 뒤 {RETRY_STEP}")
        if self.servers[server].get("command"):  # 워커 자신의 조회 창구(질문 · 결과 검사) — 쓰기 도구가 없다
            return False
        try:
            spec = mcp_check.normalize(self.servers[server])
        except ValueError as e:
            raise NotRecorded(f"이 단계 에이전트의 도구 서버 「{server}」 설정이 올바르지 않아 {josa(f'「{self.step}」', '을')} 진행하지 못했습니다 — "
                              "AI 에이전트 › 도구 연결 화면에서 그 서버의 연결 검사를 해 보세요.", raw=f"{server}: {e}") from None
        if server not in self.listed:
            tries = len(WRITE_RETRY_WAITS_S) + 1
            for n in range(tries):
                out = mcp_check.check(spec)
                if out["status"] == "ok" or out.get("error_kind") not in UNREACHED_KINDS or n + 1 == tries:
                    break
                log.info("「%s」 도구 서버 %s 연결 다시 시도 %d/%d — %s", self.step, server, n + 1, tries - 1, out.get("error_kind"))
                _wait(WRITE_RETRY_WAITS_S[n], self.check_stop)
            if out["status"] != "ok":
                tried = f"{tries}번 시도해도 " if out.get("error_kind") in UNREACHED_KINDS else ""
                raise WriteFailed(f"결과를 등록할 도구 서버에 {tried}닿지 못해 {josa(f'「{self.step}」', '을')} 진행하지 못했습니다. 시작.bat을 다시 실행한 뒤 "
                                  f"{RETRY_STEP}", raw=f"{server}: {out.get('error')} ({out.get('error_kind')})")
            self.listed[server] = {t["name"]: t for t in out["tools"]}
        meta = self.listed[server].get(tool)
        if meta is None:
            raise NotRecorded(f"「{self.step}」의 결과를 등록할 도구가 지금 도구 서버에 없어 진행하지 못했습니다. README 「새 판 받기」대로 "
                              "새 판을 받은 뒤 시작.bat을 다시 실행하세요.", raw=f"{server}/{tool}")
        return not meta["callable"]

    def remote(self, server: str) -> bool:
        """실행 밖에서 다시 부를 수 있는 서버인가 — 워커 자신의 조회 창구(명령형)는 아니다."""
        return not self.servers[server].get("command")

    def read(self, server: str, tool: str, arguments: dict) -> tuple[list, list] | None:
        """읽기 도구 하나를 이 PC의 서버로 다시 부른다(써 보기와 같은 함수 — 그 자리에서 읽기 전용 판정을 다시 한다) → 표, 못 받았으면 None.
        견주려는 것일 뿐이라 다시 시도하지 않고 멈추지도 않는다. 닿지 못한 서버는 그 실행에서 다시 부르지 않는다."""
        if server in self.unreached:
            return None
        out = mcp_check.call(mcp_check.normalize(self.servers[server]), tool, arguments, max_chars=1_000_000)
        if out["status"] != "ok":
            if out["status"] == "failed":
                self.unreached.add(server)
            log.info("「%s」 읽기 조회 %s/%s 를 다시 부르지 못했습니다 — %s (%s)", self.step, server, tool, out.get("error"), out.get("error_kind"))
            return None
        result = out["result"]
        if result["is_error"] or result["truncated"]:
            log.info("「%s」 읽기 조회 %s/%s 가 지금은 오류이거나 너무 커서 견주지 못했습니다", self.step, server, tool)
            return None
        return _table(result["text"])

    def call(self, server: str, tool: str, arguments: dict) -> dict:
        """쓰기 도구 하나를 이 PC의 서버로 부른다 → 성공한 결과. 다시 시도할 만한 오류(머리의 WRITE_RETRY_WAITS_S)면 같은 실행 안에서 기다렸다
        다시 부르고, 그 밖의 오류와 끝내 안 된 것은 WriteFailed(지어낸 결과로 메우지 않는다)."""
        spec, where = mcp_check.normalize(self.servers[server]), f"{server}/{tool}"
        tries = len(WRITE_RETRY_WAITS_S) + 1
        for n in range(tries):
            # 승인 뒤 시스템 작업의 쓰기 호출과 같은 함수(입력 형식 검사 포함)
            out = mcp_check.call_effect(spec, tool, arguments, max_chars=1_000_000, timeout=WRITE_CALL_TIMEOUT_S)
            if out["status"] != "ok":
                again, raw = out.get("error_kind") in UNREACHED_KINDS, f"{where}: {out.get('error')} ({out.get('error_kind')})"
            else:
                result = out["result"]
                if not _failed(result["text"], result["is_error"]):
                    return result
                body = _as_json(result["text"])
                again, raw = isinstance(body, dict) and body.get("error_kind") == UNAVAILABLE, f"{where}: {result['text'][:600]}"
            if again and n + 1 < tries:
                log.info("「%s」 쓰기 도구 %s 다시 시도 %d/%d — %s", self.step, where, n + 1, tries - 1, raw[:200])
                _wait(WRITE_RETRY_WAITS_S[n], self.check_stop)
                continue
            tried = f" {tries}번 시도해도 같았습니다." if again else ""
            if out["status"] != "ok":
                if again:
                    raise WriteFailed(f"「{self.step}」의 결과를 등록할 도구 서버에 닿지 못했습니다.{tried} 시작.bat을 다시 실행한 뒤 {RETRY_STEP}",
                                      raw=raw)
                raise WriteFailed(f"「{self.step}」의 결과를 등록하는 동안 도구 서버가 제대로 답하지 않았습니다. 잠시 뒤 "
                                  f"{RETRY_STEP} 같은 일이 되풀이되면 처리 과정의 원문을 시스템 관리자에게 보여 주세요.", raw=raw)
            reason = _tool_reason(result["text"])
            if again:
                raise WriteFailed(f"「{self.step}」의 결과를 등록하지 못했습니다 — {reason or '판단에 쓸 값을 아직 받지 못했습니다'}.{tried} "
                                  f"값이 다시 들어온 뒤 {RETRY_STEP}", raw=raw)
            raise WriteFailed(f"「{self.step}」의 결과를 이 PC에 등록하지 못했습니다" + (f" — {reason}." if reason else ". 처리 과정의 원문을 시스템 관리자에게 "
                              "보여 주세요."), raw=raw)


def play(library: Library, key: str, doc: dict, i: int, request, check_stop, last: dict, *, reclaimed: bool = False) -> Iterable[ExecEvent]:
    """녹화의 i번째 실행을 이 처리 건의 값으로 바꿔 끼워 낸다. 결과 파일도 녹화 당시 것을 바꿔 둔다. last 에 알림 재료를 남긴다.
    reclaimed: 워커가 끊긴 뒤 다시 잡은 점유가 같은 실행을 처음부터 다시 내는 것 — 그 실행이 이미 부른 쓰기 도구(판단 등록)는 다시 부르지
    않고 그때 받은 결과를 쓴다(process 는 한 작업 · 세대에 판단 하나만 받는다 — 다시 부르면 409 로 단계가 실패했다, 검진 G1-11)."""
    saved = doc["runs"][i]
    step = doc.get("step") or "이 단계"
    swaps = _Swaps()
    carried = Path(request.workdir) / SWAPS_FILE
    resumed = bool((request.resume_session or "").startswith(library.prefix))
    done: dict[str, str] = {}                # 이 실행이 이미 부른 쓰기 도구의 결과(tool_use_id → 결과 글)
    if (resumed or reclaimed) and carried.is_file():   # 이어 하기 · 재점유: 앞 실행이 부른 쓰기 도구의 새 id 와 결과를 이어 받는다
        held = json.loads(carried.read_text(encoding="utf-8"))
        swaps.exact.update(held["exact"])
        done = dict(held["results"]) if reclaimed and not resumed else {}
    elif not resumed:
        carried.unlink(missing_ok=True)
    swaps.pair_case(saved.get("context") or {}, _task_context(request.workdir), step)
    tools = _Tools(request.workdir, step, check_stop)
    session = library.session(key, i)
    last.update(step=step, recorded_at=doc.get("recorded_at"), rerun=[], kept_errors=0, differs=[], reads=[], typed=swaps.typed, attempt=_attempt_label(_attempt(saved)),
                library=library.prefix, skills=sorted({name for d in saved["events"] if d["kind"] == ExecEventKind.TOOL_START.value
                                                       for name, _ in skill_files(d.get("tool"), d.get("tool_input"))}))
    events = [d for d in saved["events"] if not partial_chunk(d)]
    if not any(d["kind"] == ExecEventKind.RUN_START.value for d in events):    # 녹화에 실행 시작 줄이 있으면 그것 하나만(G1-08)
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=session)
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
            if d.get("tool_use_id") in done:          # 재점유: 끊기기 전에 이미 부른 쓰기 — 그때의 결과
                result = {"text": done[d["tool_use_id"]], "is_error": False}
            else:
                result = tools.call(*target, d["tool_input"] if isinstance(d["tool_input"], dict) else {})
            live[d.get("tool_use_id")] = result
            last["rerun"].append(f"{target[0]}/{target[1]}")
            old, new = _as_json(old), _as_json(result["text"])
            if old is None and new is not None:
                made = (_created(new) or {}).get("id")
                raise NotRecorded(f"「{step}」의 준비된 결과를 읽을 수 없어 이 처리 건의 값으로 바꾸지 못했습니다. README 「새 판 받기」대로 새 판을 받으세요"
                                  + (f"(이 PC에 등록된 판단 {made}은 승인 단계로 넘어가지 않습니다)." if made else "."))
            swaps.pair_created(old, new)
            changed, numbers = decision_gap(old, new)
            if changed and library.prefix == COURSE:
                made = (_created(new) or {}).get("id")
                raise NotRecorded(f"{REPLAY} 「{step}」의 준비된 AI 판단을 이 처리 건에 쓸 수 없습니다. " + " · ".join(changed) + ". "
                                  "설비 · 업무 상태가 준비된 판단 때와 달라 AI 설명과 승인 카드가 서로 다른 조치를 말하게 됩니다. "
                                  "설비 · 업무 상태를 시작 상태로 되돌린 뒤 다시 시작하거나, AI 키를 넣어 실제 AI로 실행해 주세요"
                                  + (f"(지금 계산으로 등록된 판단 {made}은 승인 단계로 넘어가지 않습니다)." if made else "."))
            last["differs"] += numbers
            done[d["tool_use_id"]] = result["text"]
            # 바로 남긴다 — Runner 는 결과를 받으면 이 생성기를 끝까지 돌리지 않고 닫을 수 있고, 워커가 그 사이 죽을 수도 있다
            carried.parent.mkdir(parents=True, exist_ok=True)
            carried.write_text(json.dumps({"exact": swaps.exact, "results": done}, ensure_ascii=False), encoding="utf-8")
        elif d["kind"] == ExecEventKind.TOOL_START.value and target and tools.remote(target[0]):
            # 읽기 조회: 저장된 결과를 그대로 보이되, 표를 돌려준 조회는 이 PC에서 다시 불러 견준다(머리의 「읽기 조회 견주기」)
            recorded = next((e for e in events[n + 1:] if e["kind"] == ExecEventKind.TOOL_END.value
                             and e.get("tool_use_id") == d.get("tool_use_id")), None)
            old = (saved.get("tool_outputs_full") or {}).get(d.get("tool_use_id")) or (recorded.get("tool_output") if recorded else None)
            was = None if recorded is None or _failed(old, recorded.get("is_error")) else _table(swaps.apply(old))
            if was is not None:
                arguments = d["tool_input"] if isinstance(d["tool_input"], dict) else {}
                now = tools.read(*target, arguments)
                last["reads"].append((read_subject(target[0], arguments), read_gap(was, now) if now is not None else False))
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


def korea_time(recorded_at: str | None) -> str:
    """녹화 시각(「2026-10-28 12:08 UTC」) → 학생이 읽는 한국 시각(「2026-10-28 21:08」). 읽을 수 없으면 원문."""
    try:
        t = datetime.strptime(str(recorded_at), "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return str(recorded_at)
    return (t + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")


def _counted(lines: list[str]) -> list[str]:
    """같은 줄은 한 번만(몇 번인지 붙여)."""
    return [line + (f"({lines.count(line)}번)" if lines.count(line) > 1 else "") for line in dict.fromkeys(lines)]


def reads_said(last: dict, when: str) -> str:
    """다시 부른 읽기 조회가 저장된 결과와 다르거나 견주지 못했을 때의 말(when: 「준비 당시」 · 「앞선 실행 때」). 모두 같으면 빈 글."""
    reads = last.get("reads") or []      # (가리키는 말, 차이): 차이 = None 같음 · False 견주지 못함 · (저장된 행 수, 지금 행 수) 다름
    gaps = _counted([f"{subject} — " + (f"{when} {gap[0]}건 · 지금 {gap[1]}건" if gap[0] != gap[1] else f"{gap[0]}건으로 같고 값이 다름")
                     for subject, gap in reads if gap])
    unseen = sum(1 for _, gap in reads if gap is False)
    if not gaps and not unseen:
        return ""
    said = f"결과 글 안의 조회 결과는 {when} 값입니다."
    if gaps:
        differing = sum(1 for _, gap in reads if gap)
        said += (f" 같은 조회 {len(reads)}개를 이 PC에서 다시 해 보니 {differing}개가 지금 값과 다릅니다: " + "; ".join(gaps) + ".")
    if unseen:
        said += f" 조회 {unseen}개는 이 PC에서 다시 조회하지 못해 지금 값과 견주지 못했습니다."
    return said + " 결과 글의 값을 쓰기 전에 지금 값을 확인해 주세요."


TYPED_SHOWN = 80      # 알림에 옮겨 적는 입력 글의 길이 — 넘으면 줄인다(전문은 처리 건의 입력에 있다)


def typed_said(last: dict) -> str:
    """사람이 넣은 글이 저장된 실행과 다를 때의 말. 같으면 빈 글."""
    cut = lambda text: f"「{text if len(text) <= TYPED_SHOWN else text[:TYPED_SHOWN] + '…'}」" if text else "(빈 값)"   # noqa: E731
    pairs = last.get("typed") or []
    if not pairs:
        return ""
    return ("결과 글은 준비 당시의 입력을 두고 쓴 것이고, 지금 넣은 입력과 다릅니다: "
            + "; ".join(f"준비 당시 {cut(old)} · 지금 {cut(new)}" for old, new in pairs) + ".")


def notice(last: dict | None, skills: list[str] | None = None) -> str | None:
    """처리 과정에 남길 한 줄. 재생 모드의 평소 실행에는 남기지 않는다 — 화면은 실제 AI 실행과 같고, 안내는 재생 모드가 지원하지 않는
    행동에서만 한다(준비된 글이 이 PC의 지금 값 · 지금 넣은 입력과 다른 것을 두고 쓰인 것도 그 하나다 — differs · reads_said · typed_said). skills: 이번 실행에 붙인 스킬 — 저장된 실행이 연 스킬(last["skills"])과 다를 때만 같은 답임을 말한다(스킬을 붙이고
    뗀 차이를 보려는 실습이 같은 답을 보고 「스킬이 아무 일도 하지 않는다」로 배우지 않게, 실라버스 포털 실습 3번). 수업 기본 스킬
    그대로면 저장된 실행과 같은 구성이라 말하지 않는다."""
    if not last:
        return None
    if last.get("library") == REUSE:
        rerun = f" 쓰기 도구({', '.join(dict.fromkeys(last['rerun']))})는 이 PC에서 다시 실행했습니다." if last.get("rerun") else ""
        kept = (f" 저장 때 오류였던 쓰기 호출 {last['kept_errors']}건은 다시 부르지 않고 그 오류를 그대로 보였습니다." if last.get("kept_errors") else "")
        reads = reads_said(last, "앞선 실행 때")
        return (f"같은 설정 · 같은 입력의 앞선 실행 결과를 다시 썼습니다(새로 추론하지 않음 — {korea_time(last.get('recorded_at'))} 실행).{rerun}{kept} "
                + (reads + " " if reads else "") + "새로 추론하게 하려면 입력이나 에이전트 설정을 바꿔 실행하세요.")
    said, reads, typed = [], reads_said(last, "준비 당시"), typed_said(last)
    if last.get("differs") or reads or typed:
        line = f"{REPLAY} AI 설명과 결과 글은 준비된 것을 그대로 보입니다."
        if typed:
            line += " " + typed
        if last.get("differs"):
            line += f" 그 안의 다음 값은 준비 당시 값이고, 승인 카드의 값이 이 PC의 지금 계산입니다: {'; '.join(last['differs'])}."
        said.append(line + (" " + reads if reads else ""))
    if skills is not None and set(skills) != set(last.get("skills") or ()):
        said.append(f"{REPLAY} 스킬을 붙이거나 떼어도 같은 답을 냅니다(이번 실행의 스킬: {', '.join(skills) or '없음'}). "
                    "스킬을 붙이고 뗀 차이는 실제 AI로 실행할 때 확인할 수 있습니다.")
    return " ".join(said) or None


# ---------------------------------------------------------------- 점유 하나의 AI 응답
class Responses:
    """모드 하나와 녹화 두 묶음(수업 녹화 · 같은 요청 저장). Runner 가 점유마다 claim() 을 받아 그 점유의 스트림을 낸다."""

    def __init__(self, mode: str, *, course: Library, cache: Library | None = None):
        from .settings import MODES
        if mode not in MODES:
            raise ValueError(f"AI_MODE 는 {', '.join(MODES)} 중 하나여야 합니다(지금 {mode!r})")
        self.mode, self.course, self.cache = mode, course, cache if mode == "live" else None

    def claim(self, *, cli, slot: str | None, case: str, attempt: tuple[int, int], request_key: str | None, step: str,
              provider: str, source: dict, accepted: Callable[[dict], bool], reclaimed: bool = False,
              skills: list[str] | None = None) -> Claim:
        return Claim(self, cli=cli, slot=slot, case=case, attempt=attempt, request_key=request_key, step=step,
                     provider=provider, source=source, accepted=accepted, reclaimed=reclaimed, skills=skills)


class Claim:
    def __init__(self, responses: Responses, *, cli, slot, case, attempt, request_key, step, provider, source, accepted,
                 reclaimed=False, skills=None):
        self.r, self.cli = responses, cli
        self.reclaimed, self.skills = reclaimed, list(skills or [])
        if slot in UNCACHED_SLOTS:
            request_key = None              # 지금 상태로 답하는 자리 — 같은 요청 저장을 읽지도 쓰지도 않는다(G1-09)
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
            return ("play", key, doc, self._run_for(doc) if doc else None, self.r.course)
        if resume:
            return ("live",)
        if self.r.cache is not None and self.request_key:
            doc = self.r.cache.load(self.request_key)
            if doc is not None:
                if self.accepted(doc.get("source") or {}):
                    self.r.cache.touch(self.request_key)
                    return ("play", self.request_key, doc, 0, self.r.cache)
                log.info("같은 요청 저장 %s: 그 실행의 작업이 지금은 끝남이 아니라(돌려보냄 · 재작업 · 초기화) 버리고 새로 실행합니다", self.request_key)
                self.r.cache.delete(self.request_key)
        return ("live",)

    def _run_for(self, doc: dict) -> int | None:
        """이 점유의 실행 차례에 낼 저장된 실행의 순번. 그 차례의 실행이 저장돼 있으면 그것. 없는데 다시 수행(재작업 세대, 보류는 없음)이면 첫
        실행 — 다시 수행은 같은 단계를 같은 입력으로 새로 하는 것이라(새 작업 행 · 사유는 AI 입력이 아니다), 입력이 같으면 같은 답을 내는
        저장된 응답의 본뜻 그대로다. 데이터를 고르는 입력이 달라졌으면 play 가 멈추고(FIELD_NAMES), 쓰기 도구는 이 PC에서 다시 불러 지금 값으로
        판단을 등록하며, 그 판단이 저장된 설명과 다르면 그 까닭으로 멈춘다(decision_gap). 보류 뒤 재평가(조건이 바뀌어 다시 보는 것)는
        입력이 다른 실행이라 첫 실행으로 메우지 않는다."""
        runs = [_attempt(run) for run in doc["runs"]]
        if self.attempt in runs:
            return runs.index(self.attempt)
        generation, reassessment = self.attempt
        return runs.index((0, 0)) if generation and not reassessment and (0, 0) in runs else None

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
            yield from play(library, key, doc, i, request, check_stop, self.last, reclaimed=self.reclaimed and not request.resume_session)
            return
        self.last = {}
        events: list[ExecEvent] = []
        gen = self.cli(provider, request, env, check_stop=check_stop) if getattr(self.cli, "accepts_check_stop", False) \
            else self.cli(provider, request, env)
        for ev in gen:
            if not partial_chunk(ev):
                events.append(ev)
            yield ev
        self.captured.append((request.resume_session, capture(request, events)))

    accepts_check_stop = True

    def _missing(self, request, doc, library) -> str:
        step = self.step or "이 단계"
        if (request.resume_session or "").startswith(REUSE):
            return (f"앞선 실행 결과를 다시 쓰던 「{step}」에 이어지는 응답이 없어 멈췄습니다. 이 단계를 다시 실행하면 실제 AI로 새로 실행합니다.")
        if request.resume_session:
            return (f"{REPLAY} 「{step}」에 이어지는 응답(결과를 고쳐 다시 낸 응답 · 사람 답 뒤 이어 한 응답)을 지원하지 않습니다. "
                    "이 처리 건은 닫고 새로 시작해 주세요.")
        # 재생 모드가 답하는 AI 단계의 이름(저장된 응답의 업무 이름 — 질문 자리는 따로 말한다). 손으로 적은 흐름 목록을 두지 않는다
        steps = " · ".join(f"「{name}」" for name in dict.fromkeys(str(d.get("step") or "") for _, d in library.docs() if d.get("slot") != "question") if name)
        if not self.slot:
            return (f"{REPLAY} {josa(f'「{step}」', '을')} 지원하지 않습니다. 재생 모드에서 진행되는 AI 단계는 기본 제공 흐름과 교대 인수인계의 "
                    f"{steps or '(없음)'}, 그리고 질문하기의 준비된 질문입니다.")
        if self.slot == "question":
            asked = library.questions()
            return (f"{REPLAY} 준비된 질문에만 답합니다. 준비된 질문: " + (" / ".join(f"「{q}」" for q in asked) if asked else "없음")
                    + ". 질문 칸 아래의 질문 단추를 눌러 넣고 보내 주세요.")
        g, n = self.attempt
        if doc is not None and n:
            return (f"{REPLAY} {josa(f'「{step}」', '을')} 보류 뒤 다시 평가하는 것을 지원하지 않습니다(첫 평가까지 지원합니다). "
                    "보류 사유를 확인하고 사람이 처리해 주세요.")
        if doc is not None and g:
            return (f"{REPLAY} {josa(f'「{step}」', '을')} 다시 수행하는 데 쓸 첫 실행의 응답이 없습니다. 새 처리 건으로 다시 시작해 주세요.")
        if self.slot.startswith("handover/draft-"):
            drafts = sorted({d["slot"] for _, d in library.docs() if str(d.get("slot") or "").startswith("handover/draft-")})
            return (f"{REPLAY} {josa(f'「{step}」', '을')} 지원하지 않습니다 — 교대 인계안의 보완 요청은 {max(0, len(drafts) - 1)}번까지 지원합니다. "
                    "그 뒤로는 보완 요청 대신 [확인]으로 넘겨 주세요.")
        return (f"{REPLAY} 이 경보로 시작한 처리 건에서는 {josa(f'「{step}」', '을')} 지원하지 않습니다. 재생 모드에서 진행되는 AI 단계는 "
                f"{steps or '(없음)'}입니다.")

    def notice(self) -> str | None:
        if self.dropped and not self.last:
            return "앞서 다시 쓴 같은 요청의 결과를 처리 흐름이 돌려보내, 그 저장을 버리고 실제 AI로 새로 실행했습니다."
        return notice(self.last, self.skills if self.last.get("library") == COURSE else None)

    def keep(self, outcome: str, secrets) -> None:
        """점유가 끝났을 때 받아 둔 실행을 남긴다. 실패 · 취소로 끝난 점유는 부르지 않는다(좋은 녹화를 덮지 않는다)."""
        if not self.captured:
            return
        if self.r.mode == "record":
            if not self.slot:
                log.warning("「%s」은 수업 AI 자리가 아니라 녹화하지 않았습니다", self.step)
                return
            if outcome not in COURSE_KEPT:
                log.warning("「%s」이(가) %s(으)로 끝나 녹화하지 않았습니다 — 수업 녹화는 제출 · 사람 질문으로 끝난 실행만 남깁니다", self.step, outcome)
                return
            for resume, run in self.captured:
                self._keep_course(resume, run, secrets)
        elif self.r.mode == "live" and outcome in CACHE_KEPT and self.request_key and self.played is None \
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


def sweep_cache(cache: Library, workitem_exists: Callable[[str], bool], retention_seconds: float, *, now: float | None = None) -> list[str]:
    """같은 요청 저장 가운데 다시 쓸 수 없는 것을 지운다(검진 G1-09 — 끝없이 쌓였다): ① 그 실행의 작업 행이 더 없음(처리 건을 지웠거나 데이터를
    비움) ② 작업 폴더와 같은 보존 기간(settings.workspace_retention_hours) 동안 쓰이지 않음 — 열쇠에 경보 id · 시각 · 센서 값이 든 처리 건
    (c3 흐름)은 같은 요청이 다시 오지 않아 작업 행이 남아도 다시 쓰이지 않는다. 다시 쓸 때 파일 시각을 새로 한다(Library.touch). 지운 열쇠 목록."""
    import time
    cutoff = (time.time() if now is None else now) - retention_seconds
    removed = []
    for key, doc in cache.docs():
        todo = str((doc.get("source") or {}).get("todo_id") or "")
        if not todo or not workitem_exists(todo) or cache.file_of(key).stat().st_mtime < cutoff:
            cache.delete(key)
            removed.append(key)
    return removed


# ---------------------------------------------------------------- 녹화 목록(강사 확인)
def course_slots(process_url: str) -> list[dict]:
    """수업 AI 자리 [{slot, recorded}] — 정본(procsvc/course_policy)을 process 의 GET /api/course-access 에서 읽는다(워커는 규칙 모듈을
    가져오지 않는다: 워커 이미지에는 그 모듈이 읽는 정의 폴더가 없어 녹화 목록이 죽었다 — 검진 P2-04). recorded=False 는 녹화하지 않고 키 없는
    PC에서 학생 문장으로 멈추기로 한 자리(기록 §2-5 — 교대 보완 2)."""
    import urllib.request
    from .course_access import process_base
    url = process_base(process_url) + "/api/course-access"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            view = json.loads(r.read(1_000_001))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"수업 AI 자리를 process({url})에서 읽지 못했습니다 — 스택이 켜져 있는지 확인하세요: {type(e).__name__}: {e}") from None
    slots = view.get("ai_slots") if isinstance(view, dict) else None
    if not isinstance(slots, list) or any(not isinstance(x, dict) or not isinstance(x.get("slot"), str) or type(x.get("recorded")) is not bool
                                          for x in slots):
        raise RuntimeError(f"process 의 수업 AI 자리(ai_slots) 응답 형식이 올바르지 않습니다: {url}")
    return slots


def listing(library: Library, slots: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """(녹화마다 한 줄, 녹화해야 하는데 없는 자리, 녹화하지 않기로 한 자리). slots = course_slots(...)."""
    course = {x["slot"] for x in slots}
    rows = []
    for key, doc in library.docs():
        path = library.file_of(key)
        later = [l for l in dict.fromkeys(_attempt_label(_attempt(r)) for r in doc["runs"]) if l]
        rows.append({"file": path.name, "slot": doc.get("slot") or "", "step": doc.get("step") or "", "case": doc.get("case") or "",
                     "runs": len(doc["runs"]), "attempts": later, "recorded_at": doc.get("recorded_at"),
                     "kb": max(1, round(path.stat().st_size / 1024)),
                     "masked": gzip.decompress(path.read_bytes()).decode("utf-8").count(REDACTED),
                     "course": doc.get("slot") in course})
    recorded = {r["slot"] for r in rows}
    missing = sorted(x["slot"] for x in slots if x["recorded"] and x["slot"] not in recorded)
    unrecorded = sorted(x["slot"] for x in slots if not x["recorded"])
    return sorted(rows, key=lambda r: (r["slot"], r["case"])), missing, unrecorded


def main(argv: list[str] | None = None) -> int:
    """python -m worker.ai_replay [폴더] — 수업 녹화 목록과 빠진 수업 AI 자리(있으면 종료 코드 1). 기본 폴더는 AI_REPLAY_DIR, 자리는
    PROCESS_URL 의 process 에서 읽는다."""
    import sys
    from .settings import settings
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else settings.ai_replay_dir
    rows, missing, unrecorded = listing(Library(root), course_slots(settings.process_url))
    print(f"수업 녹화: {root} — {len(rows)}개")
    for r in rows:
        masked = f", 비밀값 가림 {r['masked']}곳" if r["masked"] else ""
        later = f"(그 가운데 {', '.join(r['attempts'])})" if r["attempts"] else ""
        stale = "" if r["course"] else "  ← 수업 AI 자리가 아님(쓰이지 않는 녹화)"
        print(f"  {korea_time(r['recorded_at'])}  {r['slot'] or '-'}  {r['case'] or '-'}  「{r['step']}」  실행 {r['runs']}개{later} · {r['kb']} KB{masked}  ({r['file']}){stale}")
    for slot in unrecorded:
        print(f"  [녹화하지 않는 자리] {slot} — 키 없는 PC에서는 학생이 알아듣는 안내로 멈춥니다(정한 것)")
    for slot in missing:
        print(f"  [녹화 없음] {slot} — 녹화해야 하는 자리입니다. 키 없는 PC에서 이 단계는 「{NotRecorded.title}」로 멈춥니다")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
