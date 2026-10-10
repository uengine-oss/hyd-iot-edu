"""일부러 틀린 결과를 넣어 자동 확인이 잡는지 본다.

    python instructor/wrong_results.py

먼저 정답 예로 랩을 완주해 통과 상태를 만든 뒤, 틀린 결과를 하나씩 넣고 그 랩의 확인이 '미통과'로 끝나며
기대한 기준 이름이 미통과 목록에 있는지 본다. 그래프를 건드린 경우는 바로 되돌리고, 마지막에 전체 확인이 다시 통과하는지 본다.
랩용 실행 환경(kit/compose.yaml)이 켜져 있어야 한다.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import labpaths  # noqa: E402,F401
from labkit.graph import graph_session  # noqa: E402
from run_all import LAB_ORDER, LabRun, run_all  # noqa: E402

FAILED_MARK = "[미통과] "


@dataclass
class Wrong:
    lab: str
    what: str                                  # 무엇을 틀리게 했는가
    expect: str                                # 미통과 목록에 있어야 하는 기준 이름의 일부
    files: Callable[[Path], None] | None = None   # 학생 폴더 사본을 고친다
    graph: list[str] | None = None             # 그래프에 돌릴 질의(틀리게)
    undo: list[str] | None = None              # 그래프를 되돌리는 질의
    after: Callable[[LabRun], None] | None = None  # 고친 파일로 프로그램을 다시 돌려야 할 때


def replace(relative: str, old: str, new: str) -> Callable[[Path], None]:
    def apply(project: Path) -> None:
        path = project / relative
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise RuntimeError(f"{relative} 에 바꿀 문장이 없습니다: {old!r}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    return apply


def edit_json(relative: str, change: Callable[[dict], None]) -> Callable[[Path], None]:
    def apply(project: Path) -> None:
        path = project / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return apply


def both(*steps: Callable[[Path], None]) -> Callable[[Path], None]:
    def apply(project: Path) -> None:
        for step in steps:
            step(project)
    return apply


# ── JSON 을 틀리게 고치는 작은 함수들 ─────────────────────────────
def flip_direction(schema: dict) -> None:
    relation = next(r for r in schema["relationships"] if r["type"] == "HAS_COMPONENT")
    relation["from"], relation["to"] = relation["to"], relation["from"]


def drop_unique(schema: dict) -> None:
    next(c for c in schema["classes"] if c["name"] == "Sensor")["unique"] = []


def drop_class(name: str) -> Callable[[dict], None]:
    def change(schema: dict) -> None:
        schema["classes"] = [c for c in schema["classes"] if c["name"] != name]
    return change


def rule(table: dict, rule_id: str) -> dict:
    return next(r for r in table["rules"] if r["id"] == rule_id)


def soften_rule(table: dict) -> None:
    rule(table, "C1")["result"] = "경고"


def shift_boundary(table: dict) -> None:
    rule(table, "C2")["when"][0]["op"] = ">="


def change_quote(data: dict) -> None:
    data["candidates"][1]["quote"] = "방열핀이 막히면 과열된다."


def shift_line(sections: list) -> None:
    sections[1]["lines"][0]["line"] += 1


def adopt(candidate_id: str) -> Callable[[dict], None]:
    def change(review: dict) -> None:
        review[candidate_id] = {"decision": "채택", "reason": "그럴듯하다"}
    return change


def hold(candidate_id: str) -> Callable[[dict], None]:
    def change(review: dict) -> None:
        review[candidate_id] = {"decision": "보류", "reason": "확신이 없다"}
    return change


def invent_cause(answer: dict) -> None:
    answer["causes"].append("냉매 부족")


def tamper_tool_output(answer: dict) -> None:
    answer["tool_calls"][0]["output"]["current"]["value"] = 70.0


def invent_evidence(answer: dict) -> None:
    answer["evidence"].append({"kind": "문서", "doc": "CM-01", "section": "2", "line": 12, "quote": "과열이면 즉시 전원을 끈다."})


def answer_without_ground(answer: dict) -> None:
    answer.update(status="답변", actions=["압축기 교체"], missing=[])


def hide_missing(answer: dict) -> None:
    answer["missing"] = []


def no_tool_answer(answer: dict) -> None:
    answer["tool_calls"] = []


def snack_as_decision(result: dict) -> None:
    result["decisions"].append("간식은 다음 회의에서 다시 이야기한다")


def swap_owner(result: dict) -> None:
    result["todos"][0]["owner"], result["todos"][1]["owner"] = result["todos"][1]["owner"], result["todos"][0]["owner"]


def guess_owner(result: dict) -> None:
    result["todos"][1].update(owner="임수아", unassigned=False)
    result["unassigned_todos"] = result["unassigned_todos"][1:]


def unflag_unassigned(result: dict) -> None:
    result["todos"][2]["unassigned"] = False


def change_old_result(result: dict) -> None:
    result["todos"][0]["due"] = "2026-10-09"


def literal_password(config: dict) -> None:
    config["mcpServers"]["lab-neo4j"]["env"]["NEO4J_PASSWORD"] = "password-in-file"


def fake_row(record: dict) -> None:
    record["calls"][1]["output"].append({"asset": "소형 냉각장치 1호", "component": "압축기", "failure": "과열", "cause": "냉매 부족"})


def read_before_schema(record: dict) -> None:
    record["calls"].reverse()


def drop_action_id(record: dict) -> None:
    record["judge"]["input"]["action_ids"].pop()


def tamper_judgement(record: dict) -> None:
    record["judge"]["output"]["actions"]["ACT-FIN-CLEAN"]["result"] = "허용"


def recommend_excluded(record: dict) -> None:
    record["answer"]["allowed"].append("ACT-FIN-CLEAN")
    record["answer"]["excluded"] = []


def change_condition(record: dict) -> None:
    record["judge"]["input"]["temp_c"] = 55


def notion_token_in_file(config: dict) -> None:
    config["mcpServers"]["notion"]["env"]["NOTION_TOKEN"] = "token-in-file"


def rerun(script: str) -> Callable[[LabRun], None]:
    return lambda lab_run: lab_run.script(script) and None


WRONGS = [
    # 2일차
    Wrong("2-1", "스키마에서 HAS_COMPONENT 방향을 거꾸로", "HAS_COMPONENT 의 방향", edit_json("work/schema.json", flip_direction)),
    Wrong("2-1", "스키마에서 Sensor 의 중복 금지 조건을 뺌", "Sensor 에 중복 금지 조건", edit_json("work/schema.json", drop_unique)),
    Wrong("2-1", "그래프의 Sensor 고유 제약을 지움", "그래프에 Sensor.id 고유 제약",
          graph=["DROP CONSTRAINT sensor_id_unique"],
          undo=["CREATE CONSTRAINT sensor_id_unique IF NOT EXISTS FOR (n:Sensor) REQUIRE n.id IS UNIQUE"]),
    Wrong("2-2", "같은 설비 노드를 한 번 더 만듦(중복 적재)", "Asset 노드에 같은 id 가 두 번 없다",
          graph=["DROP CONSTRAINT asset_id_unique", "CREATE (:Asset {id: 'CL-01', name: '소형 냉각장치 1호', wrong: true})"],
          undo=["MATCH (n:Asset {wrong: true}) DETACH DELETE n",
                "CREATE CONSTRAINT asset_id_unique IF NOT EXISTS FOR (n:Asset) REQUIRE n.id IS UNIQUE"]),
    Wrong("2-2", "같은 관계를 한 번 더 만듦(중복 적재)", "HAS_SENSOR 관계가 같은 쌍에 두 번 없다",
          graph=["MATCH (a:Asset {id: 'CL-01'}), (s:Sensor {id: 'CL-01-FT'}) CREATE (a)-[:HAS_SENSOR {wrong: true}]->(s)"],
          undo=["MATCH ()-[r:HAS_SENSOR {wrong: true}]->() DELETE r"]),
    Wrong("2-2", "적재 프로그램이 관계를 MERGE 가 아니라 CREATE 로 넣음", "다시 넣어도 노드·관계 수가 그대로다",
          replace("work/load_csv.py", "MERGE (a)-[:HAS_COMPONENT]->(c)", "CREATE (a)-[:HAS_COMPONENT {wrong: true}]->(c)"),
          undo=["MATCH ()-[r:HAS_COMPONENT {wrong: true}]->() DELETE r"]),
    Wrong("2-2", "부품과 센서를 잇는 관계 하나를 빼고 적재", "MONITORED_BY 관계가 CSV 와 같다",
          graph=["MATCH (:Component {id: 'CL-02-FAN'})-[r:MONITORED_BY]->(:Sensor {id: 'CL-02-ST-FAN'}) DELETE r"],
          undo=["MATCH (c:Component {id: 'CL-02-FAN'}), (s:Sensor {id: 'CL-02-ST-FAN'}) MERGE (c)-[:MONITORED_BY]->(s)"]),
    Wrong("2-3", "설비를 한정하지 않고 모든 센서를 돌려줌", "그 설비의 센서만 나온다",
          replace("work/find_related.py", "MATCH (a:Asset {id: $id})-[:HAS_SENSOR]->(s:Sensor)", "MATCH (a:Asset)-[:HAS_SENSOR]->(s:Sensor)")),
    Wrong("2-3", "LIMIT 을 무시함", "--limit 1 이면",
          replace("work/find_related.py", "ORDER BY s.id LIMIT $limit", "ORDER BY s.id")),
    Wrong("2-3", "없는 설비 번호에도 found 를 true 로 돌려줌", "없는 설비 번호(CL-99)",
          replace("work/find_related.py", '"found": False, "asset": None', '"found": True, "asset": None')),
    # 3일차
    Wrong("3-1", "결정표의 C1 결과를 제외가 아니라 경고로 적음", "규칙 C1 의 조치와 결과", edit_json("work/decision_table.json", soften_rule)),
    Wrong("3-2", "C2 의 경계를 '보다 높다'가 아니라 '이상'으로 적음(경계값 오판)", "경계값", edit_json("work/decision_table.json", shift_boundary)),
    Wrong("3-2", "규칙이 겹칠 때 덜 조심스러운 결과를 고름", "준비된 입력 '두 조건 겹침' 의 결과",
          replace("work/evaluate.py", "applied = min(matched", "applied = max(matched")),
    Wrong("3-2", "기준에 없는 값도 받아들이고 맞는 규칙이 없으면 허용으로 답함", "기준에 없는 입력(팬 상태 '모름')",
          both(replace("work/evaluate.py", 'if value not in spec["values"]:', "if False:"),
               replace("work/evaluate.py", "        if not matched:\n            raise DecisionError(f\"조치 '{action}' 에 맞는 규칙이 없습니다(입력 {values}).\")",
                       "        if not matched:\n            matched = [{'id': '없음', 'result': '허용', 'reason': '기본값'}]"))),
    Wrong("3-3", "영향 방향 하나를 반대로 넣음", "방향(긍정·부정)이 CSV 와 같다",
          graph=["MATCH (:Action {id: 'ACT-FAN-UP'})-[r:AFFECTS]->(:Measure {id: 'KPI-POWER-COST'}) SET r.effect = '긍정'"],
          undo=["MATCH (:Action {id: 'ACT-FAN-UP'})-[r:AFFECTS]->(:Measure {id: 'KPI-POWER-COST'}) SET r.effect = '부정'"]),
    Wrong("3-3", "계산하지 않은 추정 숫자를 관계에 저장", "추정 숫자를 관계에 사실처럼 저장하지 않았다",
          graph=["MATCH (:Action {id: 'ACT-FAN-UP'})-[r:AFFECTS]->(:Measure {id: 'KPI-POWER-COST'}) SET r.increase_pct = 15"],
          undo=["MATCH (:Action {id: 'ACT-FAN-UP'})-[r:AFFECTS]->(:Measure {id: 'KPI-POWER-COST'}) REMOVE r.increase_pct"]),
    Wrong("3-3", "스키마 파일에 Measure 클래스를 더하지 않음", "스키마에 클래스 Measure", edit_json("work/schema.json", drop_class("Measure"))),
    # 4일차
    Wrong("4-1", "후보의 인용 문장을 원문과 다르게 고쳐 씀", "인용 문장이 모두 그 절", edit_json("work/candidates.json", change_quote)),
    Wrong("4-1", "구간의 줄 번호가 원문과 어긋남", "줄 번호와 원문이 그대로 보존됐다", edit_json("work/sections.json", shift_line)),
    Wrong("4-2", "원문에 없는 문장의 후보(C06)를 채택해 등록", "원문에 없는 연결은 등록하지 않았다",
          edit_json("work/review.json", adopt("C06")), after=rerun("register_candidates.py"),
          undo=["MATCH ()-[r {candidate_id: 'C06'}]->() DELETE r", "MATCH (a:Action {id: 'ACT-REFRIGERANT'}) DETACH DELETE a"]),
    Wrong("4-2", "다른 고장에 잘못 이은 후보(C03)를 검토 기록 없이 그래프에 등록", "채택한 후보만 그래프에 등록됐다",
          graph=["MATCH (c:Cause {id: 'CAUSE-HOSE-LOOSE'}), (f:FailureMode {id: 'FM-OVERHEAT'}) "
                 "CREATE (c)-[:CAUSES {candidate_id: 'C03', doc: 'CM-01', section: '3', line: 20, quote: '호스 연결부 풀림은 누수의 가장 흔한 원인이다.'}]->(f)"],
          undo=["MATCH ()-[r:CAUSES {candidate_id: 'C03'}]->() DELETE r"]),
    Wrong("4-2", "원문으로 확인되는 후보(C02)를 보류", "빠뜨리지 않고 채택했다", edit_json("work/review.json", hold("C02"))),
    Wrong("4-2", "등록한 관계의 출처(원문 문장)를 지움", "C02: 관계에 적힌 출처",
          graph=["MATCH ()-[r {candidate_id: 'C02'}]->() SET r.saved_quote = r.quote REMOVE r.quote"],
          undo=["MATCH ()-[r {candidate_id: 'C02'}]->() SET r.quote = r.saved_quote REMOVE r.saved_quote"]),
    Wrong("4-3", "현재 값으로 가장 이른 측정값을 읽음", "현재 값이 연습용 DB 의 가장 늦은 값과 같다",
          replace("work/lookup.py", "ORDER BY measured_at DESC", "ORDER BY measured_at ASC")),
    Wrong("4-3", "기준을 넘지 않아도 조치를 돌려줌", "CL-02: 현재 값이 기준을 넘긴 고장만 나온다",
          replace("work/lookup.py", 'or not OPERATORS[symptom["operator"]](value, symptom["threshold"])', "")),
    Wrong("4-4", "등록되지 않은 고장에 조치를 지어냄", "근거 없음으로 답한다",
          replace("work/lookup.py", '            return not_found(asset_id, "고장 지식", f"근거 없음: 설비 {asset_id} 에 \'{name}\' 고장으로 등록된 지식이 없습니다.")',
                  '            return {"found": True, "asset_id": asset_id, "failure_mode": name, "symptoms": [], "causes": [], "actions": [{"name": "전원 재시작"}]}')),
    # 5일차
    Wrong("5-1", "초안인데 도구 호출 기록이 들어 있음", "초안은 도구 없이 낸 답이다",
          edit_json("work/agent/answers/draft_q1.json", lambda a: a["tool_calls"].append({"name": "get_related", "input": {}, "output": {}}))),
    Wrong("5-2", "도구 결과에 없는 원인을 답에 더함", "q1: 도구 결과에 없는 원인 · 조치를 답에 쓰지 않았다", edit_json("work/agent/answers/q1.json", invent_cause)),
    Wrong("5-2", "도구 반환값을 고쳐 적음", "q2: 기록된 도구 반환값이 실제로 도구를 다시 불러 나온 값과 같다", edit_json("work/agent/answers/q2.json", tamper_tool_output)),
    Wrong("5-2", "도구 결과에 없는 문장을 근거로 적음", "q1: 근거가 모두 도구 반환값에 있다", edit_json("work/agent/answers/q1.json", invent_evidence)),
    Wrong("5-2", "도구를 부르지 않고 답함", "q1: 도구를 한 번 이상 불렀다", edit_json("work/agent/answers/q1.json", no_tool_answer)),
    Wrong("5-3", "없는 부품에 조치를 지어내 답함", "q3: 근거가 부족해 보류했다", edit_json("work/agent/answers/q3.json", answer_without_ground)),
    Wrong("5-3", "보류하면서 부족한 정보를 적지 않음", "q4: 부족한 정보(missing)를 적었다", edit_json("work/agent/answers/q4.json", hide_missing)),
    Wrong("5-3", "없는 도구를 부르면 예외로 죽음", "도구 호출이 예외 없이 끝난다",
          replace("work/agent/tools.py", "    if name not in HANDLERS:\n        return {\"ok\": False, \"error\": f\"없는 도구입니다: {name}. 쓸 수 있는 도구: {list(HANDLERS)}\"}\n", "")),
    # 6일차
    Wrong("6-1", "미룬 안건을 결정사항에 넣음", "memo2: 결정사항 2개", edit_json("work/meeting/memo2.result.json", snack_as_decision)),
    Wrong("6-1", "담당자를 서로 바꿔 적음", "memo1: 할 일 3개의 담당자와 기한", edit_json("work/meeting/memo1.result.json", swap_owner)),
    Wrong("6-2", "비밀번호를 설정 파일에 직접 적음", "비밀번호 · 토큰을 파일에 직접 적지 않았다", edit_json(".mcp.json", literal_password)),
    Wrong("6-2", "반환값에 없는 줄을 기록에 더함", "기록된 반환값이 같은 질의를 그래프에 직접 돌린 결과와 같다", edit_json("work/mcp/q_relations.json", fake_row)),
    Wrong("6-2", "스키마를 읽기 전에 질의함", "스키마를 먼저 읽고", edit_json("work/mcp/q_relations.json", read_before_schema)),
    Wrong("6-3", "첫 도구가 찾은 조치 하나를 둘째 도구에 넘기지 않음", "둘째 도구의 입력에 그대로 전달됐다", edit_json("work/mcp/chain.json", drop_action_id)),
    Wrong("6-3", "판정 결과를 고쳐 적음", "판단 MCP 를 같은 입력으로 다시 부른 결과와 같다", edit_json("work/mcp/chain.json", tamper_judgement)),
    Wrong("6-3", "제외된 조치를 해도 되는 조치로 답함", "최종 답의 '허용' 조치가 판정과 같다", edit_json("work/mcp/chain.json", recommend_excluded)),
    Wrong("6-3", "질문과 다른 온도를 판단 도구에 보냄", "질문의 운전 조건이 둘째 도구의 입력에 그대로 전달됐다", edit_json("work/mcp/chain.json", change_condition)),
    Wrong("6-4", "담당자 없는 할 일에 담당자를 짐작해 채움", "memo4: 할 일 3개의 담당자와 기한", edit_json("work/meeting/memo4.result.json", guess_owner)),
    Wrong("6-4", "담당자 없는 할 일을 표시하지 않음", "memo4: 담당자가 없는 할 일만 unassigned 가 true 다", edit_json("work/meeting/memo4.result.json", unflag_unassigned)),
    Wrong("6-4", "새 요구를 넣다가 예전 메모의 결과가 바뀜", "memo1: 날짜 · 결정사항 · 할 일이 바꾸기 전과 같다", edit_json("work/meeting/memo1.result.json", change_old_result)),
    Wrong("6-5", "Notion 토큰을 설정 파일에 직접 적음", "notion: 비밀번호 · 토큰을 파일에 직접 적지 않았다", edit_json(".mcp.json", notion_token_in_file)),
    # 7일차
    Wrong("7-1", "작업 가능 시간을 보지 않고 순위를 매김", "작업 가능 시간 30분: 순위가 맞다",
          replace("work/recommend.py", "    if required > available_minutes:", "    if False:")),
    Wrong("7-1", "딱 맞는 시간(90분)을 부족으로 봄(경계값 오판)", "작업 가능 시간 90분: 순위가 맞다",
          replace("work/recommend.py", "    if required > available_minutes:", "    if required >= available_minutes and required > 0:")),
    Wrong("7-1", "결정표에서 제외인 조치를 순위에 넣음", "결정표에서 제외인 조치가 있는 경우: 순위가 맞다",
          replace("work/recommend.py", '    if judgement["result"] == EXCLUDED:', "    if False:")),
    Wrong("7-2", "검토가 무엇이든 통과시킴", "근거가 빠진 추천안: 판정이 '반려' 이다",
          replace("work/review.py", '"verdict": "반려" if findings else "통과"', '"verdict": "통과"')),
    Wrong("7-2", "검토가 결정표 조건을 확인하지 않음", "결정표에서 제외인 조치를 추천한 추천안: 판정이 '반려' 이다",
          replace("work/review.py", '    if judgement["result"] == EXCLUDED:', "    if False:")),
    Wrong("7-2", "검토가 순편익 숫자를 비교표와 맞춰 보지 않음", "순편익 숫자와 순위가 비교표와 다른 추천안: 판정이 '반려' 이다",
          both(replace("work/review.py", '    if item.get("net_benefit_manwon") != true_net:', "    if False:"),
               replace("work/review.py", "    if true_nets != sorted(true_nets, reverse=True):", "    if False:"),
               replace("work/review.py", '    if proposal.get("recommended") != first:', "    if False:"))),
    Wrong("7-3", "작업 가능 시간이 비어도 묻지 않고 120분으로 가정", "작업 가능 시간이 비면 추천하지 않고 멈춘다",
          replace("work/hitl.py", '    if case["available_minutes"] is None:', '    case["available_minutes"] = case["available_minutes"] or 120\n    if case["available_minutes"] is None:')),
    Wrong("7-3", "숫자가 아닌 답을 0분으로 받아들임", "숫자가 아닌 답은 받지 않고 계속 기다린다",
          replace("work/hitl.py", '    if not answer.strip().isdigit():\n        raise ProposalError(f"작업 가능 시간은 0 이상의 정수(분)로 답해 주세요(받은 답 {answer!r}).")\n    minutes = int(answer)',
                  "    minutes = int(answer) if answer.strip().isdigit() else 0")),
]


def run_cypher(statements: list[str] | None) -> None:
    if not statements:
        return
    with graph_session() as session:
        for statement in statements:
            session.run(statement).consume()


def try_wrong(base: Path, wrong: Wrong) -> tuple[bool, str]:
    """틀린 결과 하나를 넣고 확인을 돌린다. (잡았는가, 설명)"""
    with tempfile.TemporaryDirectory(prefix="cooler-lab-wrong-") as folder:
        project = Path(folder) / "project"
        shutil.copytree(base, project)
        lab_run = LabRun(project)
        try:
            if wrong.files:
                wrong.files(project)
            run_cypher(wrong.graph)
            if wrong.after:
                wrong.after(lab_run)
            done = lab_run.check(wrong.lab)
        finally:
            run_cypher(wrong.undo)
    failed = [line.strip()[len(FAILED_MARK):] for line in done.stdout.splitlines() if line.strip().startswith(FAILED_MARK)]
    caught = done.returncode == 1 and any(wrong.expect in name for name in failed)
    return caught, f"종료 코드 {done.returncode}, 미통과 {failed[:4]}{' …' if len(failed) > 4 else ''}" + (f"\n{done.stderr.strip()[-400:]}" if done.returncode not in (0, 1) else "")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cooler-lab-base-") as folder:
        base = Path(folder) / "project"
        base.mkdir()
        results = run_all(base, log=lambda _: None)
        if not all(results.values()):
            raise SystemExit(f"정답 예 완주가 통과하지 않아 시작할 수 없습니다: {[lab for lab, ok in results.items() if not ok]}")
        missed = []
        for wrong in WRONGS:
            caught, detail = try_wrong(base, wrong)
            print(f"[{'잡음' if caught else '놓침'}] 랩 {wrong.lab} · {wrong.what}\n        {detail}")
            if not caught:
                missed.append(wrong)
        lab_run = LabRun(base)
        restored = {lab: lab_run.check(lab).returncode == 0 for lab in LAB_ORDER}
    broken = [lab for lab, ok in restored.items() if not ok]
    print(f"\n틀린 결과 {len(WRONGS)}개 가운데 {len(WRONGS) - len(missed)}개를 잡았습니다." + (f" 놓친 것: {[(w.lab, w.what) for w in missed]}" if missed else ""))
    print("되돌린 뒤 전체 확인: " + ("모두 통과" if not broken else f"미통과 {broken}"))
    raise SystemExit(1 if missed or broken else 0)


if __name__ == "__main__":
    main()
