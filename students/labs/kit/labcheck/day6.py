"""6일차 확인: 회의 메모 Skill(6-1) · Neo4j MCP 연결(6-2) · 두 MCP 잇기(6-3) · Skill 에 새 요구 더하기(6-4) · Notion 연결 설정(6-5)."""
from __future__ import annotations

import json
import re

from labcheck import mcpclient
from labcheck.core import Report, need_file, read_json, work_path
from labcheck.day4 import graph_knowledge, names
from labcheck.facts import read_kit_json
from labkit.graph import graph_session, rows
from labkit.settings import project_dir

SKILL_NAME = "meeting-notes"
OUTPUT_COLUMNS = ("결정사항", "담당자", "할 일")
WRITE_WORDS = re.compile(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|LOAD)\b", re.IGNORECASE)
NEO4J_SERVER = "lab-neo4j"
JUDGE_SERVER = "lab-judge"
NOTION_SERVER = "notion"
SCHEMA_TOOL = "get_neo4j_schema"
READ_TOOL = "read_neo4j_cypher"
WRITE_TOOL = "write_neo4j_cypher"
JUDGE_TOOL = "evaluate_actions"
BUCKETS = {"allowed": "허용", "warned": "경고", "excluded": "제외"}
SPEC_PARTS = {"바꿀 것": ("바꿀", "변경"), "지킬 것": ("지킬", "유지"), "상황": ("상황",), "행동": ("행동",), "기대 결과": ("기대",)}


def skill_file():
    return project_dir() / ".claude" / "skills" / SKILL_NAME / "SKILL.md"


def front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    return {key.strip(): value.strip() for key, _, value in (line.partition(":") for line in block.splitlines()) if value}


def load_skill(report: Report) -> str:
    need_file(report, skill_file(), "Skill")
    text = skill_file().read_text(encoding="utf-8")
    meta = front_matter(text)
    report.check(f"Skill 머리말의 name 이 폴더 이름({SKILL_NAME})과 같다", meta.get("name") == SKILL_NAME, f"나온 값 {meta.get('name')!r}")
    report.check("Skill 머리말에 description(언제 쓰는지)이 있다", bool(meta.get("description")), "description 이 없으면 Claude Code 가 이 Skill 을 고르지 못합니다.")
    absent = [column for column in OUTPUT_COLUMNS if column not in text]
    report.check("Skill 에 필수 출력 칸(결정사항 · 담당자 · 할 일)이 적혀 있다", not absent, f"없는 칸: {absent}")
    return text


def matches(todo: dict, wanted: dict) -> bool:
    return (todo.get("owner") == wanted["owner"] and todo.get("due") == wanted["due"]
            and all(word in str(todo.get("task", "")) for word in wanted["keywords"]))


def check_result(report: Report, memo: str, result: dict) -> None:
    wanted = read_kit_json("labcheck/expected/meeting.json")[memo]
    report.equal(f"{memo}: 회의 날짜가 맞다", result.get("date"), wanted["date"])
    decisions = [str(item) for item in result.get("decisions", [])]
    found = all(any(all(word in decision for word in words) for decision in decisions) for words in wanted["decisions"])
    report.check(f"{memo}: 결정사항 {len(wanted['decisions'])}개가 빠짐없이, 다른 것과 섞이지 않고 정리됐다",
                 found and len(decisions) == len(wanted["decisions"]), f"나온 결정사항: {decisions}")
    todos = result.get("todos", [])
    missing = [f"{item['owner'] or '담당자 없음'} · {'/'.join(item['keywords'])} · {item['due']}" for item in wanted["todos"]
               if not any(matches(todo, item) for todo in todos)]
    report.check(f"{memo}: 할 일 {len(wanted['todos'])}개의 담당자와 기한이 메모와 같다", not missing and len(todos) == len(wanted["todos"]),
                 f"할 일 {len(todos)}개. 찾지 못한 것: {missing}")


def result_path(memo: str, folder: str = ""):
    return work_path(f"meeting/{folder}{memo}.result.json")


def lab6_1(report: Report) -> None:
    load_skill(report)
    for memo in ("memo1", "memo2"):
        check_result(report, memo, read_json(report, result_path(memo), f"{memo} 정리 결과"))


def core(result: dict) -> dict:
    """새 요구와 상관없이 그대로여야 하는 부분."""
    todos = sorted((str(todo.get("task")), todo.get("owner"), todo.get("due")) for todo in result.get("todos", []))
    return {"date": result.get("date"), "decisions": result.get("decisions"), "todos": todos}


def check_unassigned(report: Report, memo: str, result: dict) -> None:
    todos = result.get("todos", [])
    flags_ok = all(todo.get("unassigned") is (todo.get("owner") is None) for todo in todos)
    report.check(f"{memo}: 담당자가 없는 할 일만 unassigned 가 true 다", flags_ok,
                 f"owner 와 unassigned: {[(todo.get('owner'), todo.get('unassigned')) for todo in todos]}")
    listed = sorted(str(item) for item in result.get("unassigned_todos", []) or [])
    report.equal(f"{memo}: unassigned_todos 에 담당자 없는 할 일이 모두 들어 있다", listed,
                 sorted(str(todo.get("task")) for todo in todos if todo.get("owner") is None))


def lab6_4(report: Report) -> None:
    text = load_skill(report)
    report.check("Skill 에 '담당자가 없는 할 일' 을 표시하는 순서가 더해졌다", "unassigned" in text, "Skill 본문에 새 출력 칸이 없습니다.")
    spec = work_path("meeting/change_spec.md")
    need_file(report, spec, "변경 명세")
    spec_text = spec.read_text(encoding="utf-8")
    absent = [part for part, words in SPEC_PARTS.items() if not any(word in spec_text for word in words)]
    report.check("변경 명세에 바꿀 것 · 지킬 것 · 상황 · 행동 · 기대 결과가 있다", not absent, f"없는 부분: {absent}")
    for memo in ("memo3", "memo4"):
        result = read_json(report, result_path(memo), f"{memo} 정리 결과")
        check_result(report, memo, result)
        check_unassigned(report, memo, result)
    for memo in ("memo1", "memo2"):
        before = read_json(report, result_path(memo, "before/"), f"{memo} 바꾸기 전 결과")
        after = read_json(report, result_path(memo), f"{memo} 정리 결과")
        report.equal(f"{memo}: 날짜 · 결정사항 · 할 일이 바꾸기 전과 같다(기존 동작 유지)", core(after), core(before))
        check_result(report, memo, after)
        check_unassigned(report, memo, after)


def load_server(report: Report, name: str) -> dict:
    config = read_json(report, mcpclient.mcp_config_path(), "MCP 연결 설정(.mcp.json)")
    servers = config.get("mcpServers", {}) if isinstance(config, dict) else {}
    report.require(f".mcp.json 에 {name} 서버가 있다", name in servers, f"있는 서버: {sorted(servers)}")
    literal = mcpclient.literal_values(servers[name])
    secrets = sorted(key for key in literal if any(word in key.upper() for word in ("PASSWORD", "TOKEN", "KEY", "SECRET")))
    report.require(f"{name}: 비밀번호 · 토큰을 파일에 직접 적지 않았다(${{이름}} 자리표시자)", not secrets, f"직접 적힌 값의 이름: {secrets}")
    return servers[name]


def normalized(found: list[dict]) -> list[str]:
    return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) for row in found)


def rerun_query(report: Report, name: str, query: str, recorded: list[dict]) -> list[dict]:
    report.require(f"{name}: 조회만 하는 질의다(쓰기 문법 없음)", bool(query) and not WRITE_WORDS.search(query), f"질의: {query}")
    with graph_session() as session:
        actual = rows(session, query)
    report.check(f"{name}: 기록된 반환값이 같은 질의를 그래프에 직접 돌린 결과와 같다", normalized(recorded) == normalized(actual),
                 f"기록 {len(recorded)}줄 / 그래프 {len(actual)}줄")
    return actual


def lab6_2(report: Report) -> None:
    server = load_server(report, NEO4J_SERVER)
    live = mcpclient.use_server(server, [(SCHEMA_TOOL, {})])
    report.check(f"연결한 서버에 {SCHEMA_TOOL} · {READ_TOOL} 도구가 있다", {SCHEMA_TOOL, READ_TOOL} <= set(live["tools"]), f"서버의 도구: {live['tools']}")
    report.check("조회 전용으로 연결했다(쓰기 도구가 없다)", WRITE_TOOL not in live["tools"], "NEO4J_READ_ONLY 를 true 로 두세요.")
    record = read_json(report, work_path("mcp/q_relations.json"), "MCP 호출 기록")
    calls = record.get("calls", []) if isinstance(record, dict) else []
    order = [call.get("tool") for call in calls]
    report.require(f"스키마를 먼저 읽고({SCHEMA_TOOL}) 그다음 질의했다({READ_TOOL})",
                   SCHEMA_TOOL in order and READ_TOOL in order and order.index(SCHEMA_TOOL) < order.index(READ_TOOL), f"기록된 호출 순서: {order}")
    read_call = next(call for call in calls if call.get("tool") == READ_TOOL)
    query = (read_call.get("input") or {}).get("query", "")
    recorded = read_call.get("output") or []
    rerun_query(report, "설비 질의", query, recorded)
    served = mcpclient.use_server(server, [(READ_TOOL, {"query": query})])["results"][0]
    report.check("같은 질의를 MCP 로 다시 불러도 기록과 같은 값이 온다", normalized(served) == normalized(recorded), f"MCP {len(served)}줄 / 기록 {len(recorded)}줄")
    knowledge = graph_knowledge("CL-01")
    with graph_session() as session:
        components = {row["name"] for row in rows(session, "MATCH (:Asset {id: 'CL-01'})-[:HAS_COMPONENT]->(c) RETURN c.name AS name")}
    text = json.dumps(recorded, ensure_ascii=False)
    absent = sorted(name for name in components | names(knowledge["failures"]["과열"]["CAUSES"]) if name not in text)
    report.check("반환값에 CL-01 의 부품과 과열의 원인이 모두 들어 있다", not absent, f"반환값에 없는 이름: {absent}")


def lab6_3(report: Report) -> None:
    neo4j_server = load_server(report, NEO4J_SERVER)
    judge_server = load_server(report, JUDGE_SERVER)
    record = read_json(report, work_path("mcp/chain.json"), "두 도구 호출 기록")
    parts = [key for key in ("question", "condition", "neo4j", "judge", "answer") if key not in record] if isinstance(record, dict) else ["전체"]
    report.require("기록에 question · condition · neo4j · judge · answer 가 있다", not parts, f"없는 부분: {parts}")
    found = rerun_query(report, "조치 후보 질의", record["neo4j"].get("query", ""), record["neo4j"].get("rows") or [])
    served = mcpclient.use_server(neo4j_server, [(READ_TOOL, {"query": record["neo4j"].get("query", "")})])["results"][0]
    report.check("조치 후보 질의를 Neo4j MCP 로 다시 불러도 기록과 같다", normalized(served) == normalized(record["neo4j"].get("rows") or []), "기록과 MCP 반환값이 다릅니다.")
    known = {action["id"] for action in graph_knowledge("CL-01")["failures"]["과열"]["REMEDIED_BY"]}
    text = json.dumps(found, ensure_ascii=False)
    candidates = {action for action in known if action in text}
    report.check("첫 도구가 과열의 조치 후보를 찾았다", candidates == known, f"반환값에 있는 조치: {sorted(candidates)} / 그래프의 조치: {sorted(known)}")
    sent = record["judge"].get("input") or {}
    report.equal("첫 도구가 찾은 조치 번호가 둘째 도구의 입력에 그대로 전달됐다", sorted(sent.get("action_ids") or []), sorted(candidates))
    report.equal("질문의 운전 조건이 둘째 도구의 입력에 그대로 전달됐다",
                 {key: sent.get(key) for key in ("temp_c", "fan_state", "load_pct")}, record["condition"])
    live = mcpclient.use_server(judge_server, [(JUDGE_TOOL, sent)])
    report.check(f"판단 MCP 에 {JUDGE_TOOL} 도구가 있다", JUDGE_TOOL in live["tools"], f"서버의 도구: {live['tools']}")
    judged = live["results"][0]
    report.equal("기록된 판정이 판단 MCP 를 같은 입력으로 다시 부른 결과와 같다", record["judge"].get("output"), judged)
    for bucket, result in BUCKETS.items():
        report.equal(f"최종 답의 '{result}' 조치가 판정과 같다", sorted(record["answer"].get(bucket) or []),
                     sorted(action for action, outcome in judged["actions"].items() if outcome["result"] == result))
    report.check("최종 답에 사람이 읽는 문장(text)이 있다", bool(str(record["answer"].get("text", "")).strip()), "answer.text 가 비었습니다.")


def lab6_5(report: Report) -> None:
    server = load_server(report, NOTION_SERVER)
    report.check("Notion 서버를 실행하는 명령이 적혀 있다", bool(server.get("command") or server.get("url")), "command 나 url 이 없습니다.")
    report.check("Notion 토큰이 ${NOTION_TOKEN} 자리표시자로 연결돼 있다", "${NOTION_TOKEN}" in json.dumps(server), "토큰을 받을 자리가 없습니다.")


LABS = {
    "6-1": ("회의 메모를 정리하는 Skill 만들기", lab6_1),
    "6-2": ("관계를 찾는 도구를 MCP 로 연결해 호출하기", lab6_2),
    "6-3": ("지식 조회와 조치 판단을 두 MCP 도구로 잇기", lab6_3),
    "6-4": ("Skill 에 새 요구를 넣고 예전 결과도 유지하기", lab6_4),
    "6-5": ("Notion 자료로 짧은 퀴즈·Q&A 실행하기(연결 설정만 확인)", lab6_5),
}
