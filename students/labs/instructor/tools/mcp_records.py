"""6일차 MCP 랩의 호출 기록 예를 만든다. 프로젝트의 .mcp.json 에 적힌 서버를 실제로 불러 받은 값을 그대로 적는다."""
from __future__ import annotations

import json
from pathlib import Path

from labcheck import mcpclient

RELATIONS_QUESTION = "CL-01 에는 어떤 부품이 있고, 과열의 원인으로 등록된 것은 무엇인가?"
RELATIONS_QUERY = (
    "MATCH (a:Asset {id: 'CL-01'})-[:HAS_COMPONENT]->(c:Component) "
    "OPTIONAL MATCH (a)-[:CAN_HAVE]->(f:FailureMode {name: '과열'})<-[:CAUSES]-(k:Cause) "
    "RETURN a.name AS asset, c.name AS component, f.name AS failure, k.name AS cause ORDER BY component, cause"
)
CHAIN_QUESTION = "CL-01 이 지금 출구 온도 63 ℃, 팬 상태 약함, 부하 85 % 다. 과열을 푸는 조치 가운데 지금 해도 되는 것은 무엇인가?"
CHAIN_CONDITION = {"temp_c": 63, "fan_state": "약함", "load_pct": 85}
CHAIN_QUERY = (
    "MATCH (:Asset {id: 'CL-01'})-[:CAN_HAVE]->(:FailureMode {name: '과열'})-[r:REMEDIED_BY]->(x:Action) "
    "RETURN x.id AS action_id, x.name AS action, r.section AS section, r.line AS line, r.quote AS quote ORDER BY action_id"
)
BUCKETS = {"allowed": "허용", "warned": "경고", "excluded": "제외"}


def servers(project: Path) -> dict:
    return json.loads((project / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]


def relations_record(project: Path) -> dict:
    live = mcpclient.use_server(servers(project)["lab-neo4j"], [("get_neo4j_schema", {}), ("read_neo4j_cypher", {"query": RELATIONS_QUERY})])
    schema, found = live["results"]
    return {"question": RELATIONS_QUESTION, "calls": [
        {"tool": "get_neo4j_schema", "input": {}, "output": schema},
        {"tool": "read_neo4j_cypher", "input": {"query": RELATIONS_QUERY}, "output": found},
    ]}


def chain_record(project: Path) -> dict:
    found = mcpclient.use_server(servers(project)["lab-neo4j"], [("read_neo4j_cypher", {"query": CHAIN_QUERY})])["results"][0]
    sent = {**CHAIN_CONDITION, "action_ids": [row["action_id"] for row in found]}
    judged = mcpclient.use_server(servers(project)["lab-judge"], [("evaluate_actions", sent)])["results"][0]
    answer = {bucket: sorted(action for action, outcome in judged["actions"].items() if outcome["result"] == result)
              for bucket, result in BUCKETS.items()}
    named = {action: outcome["name"] for action, outcome in judged["actions"].items()}
    answer["text"] = (f"지금 해도 되는 조치는 {[named[a] for a in answer['allowed']]}, 주의가 필요한 조치는 {[named[a] for a in answer['warned']]}, "
                      f"하면 안 되는 조치는 {[named[a] for a in answer['excluded']]} 입니다. 근거는 매뉴얼 CM-01 2절과 결정표 판정입니다.")
    return {"question": CHAIN_QUESTION, "condition": CHAIN_CONDITION, "neo4j": {"query": CHAIN_QUERY, "rows": found},
            "judge": {"input": sent, "output": judged}, "answer": answer}
