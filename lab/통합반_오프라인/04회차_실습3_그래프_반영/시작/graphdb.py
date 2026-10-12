"""실습용 그래프 DB(Neo4j)에 Cypher 를 보내는 작은 도구. 파이썬 표준 라이브러리만 쓴다.

주소와 계정은 환경 변수로 바꿀 수 있다. 정하지 않으면 수업 환경의 값을 쓴다.
  NEO4J_HTTP      기본값 http://localhost:7474   (Neo4j Browser 와 같은 주소)
  NEO4J_USER      기본값 neo4j
  NEO4J_PASSWORD  기본값 hydpass123

쓰는 법
  import graphdb
  rows = graphdb.query("MATCH (n) RETURN count(n) AS n")          # 읽기. 행마다 {열 이름: 값}
  stats = graphdb.run_all(["MERGE ...", "MERGE ..."])              # 쓰기. 여러 문장을 한 번에 넣는다
  statements = graphdb.split_statements(open("x.cypher").read())   # 파일의 글을 문장으로 나눈다

run_all 은 문장 전부를 트랜잭션 하나로 보낸다. 한 문장이라도 실패하면 아무것도 들어가지 않는다.
"""

import base64
import json
import os
import urllib.error
import urllib.request

ADDRESS = os.environ.get("NEO4J_HTTP", "http://localhost:7474").rstrip("/")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "hydpass123")
ENDPOINT = ADDRESS + "/db/neo4j/tx/commit"


class GraphError(Exception):
    """그래프 DB 가 문장을 받지 않았거나 그래프 DB 에 닿지 못했다."""


def _post(statements):
    body = json.dumps({"statements": statements}).encode("utf-8")
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json;charset=UTF-8",
            "Authorization": "Basic " + token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise GraphError(f"그래프 DB 가 요청을 받지 않았다({error.code}). 계정과 비밀번호를 확인한다.") from error
    except (urllib.error.URLError, OSError) as error:
        raise GraphError(f"그래프 DB({ADDRESS})에 닿지 못했다. 그래프 DB 가 떠 있는지 확인한다.") from error
    if answer.get("errors"):
        first = answer["errors"][0]
        raise GraphError(f"{first.get('code', '')}: {first.get('message', '')}")
    return answer["results"]


def query(statement, params=None):
    """읽는 문장 하나를 보내고 결과를 행의 목록으로 돌려준다. 행 하나는 {열 이름: 값}이다."""
    result = _post([{"statement": statement, "parameters": params or {}}])[0]
    return [dict(zip(result["columns"], item["row"])) for item in result["data"]]


def run_all(statements, params=None):
    """문장 여러 개를 트랜잭션 하나로 보낸다. 한 문장이라도 실패하면 GraphError 가 나고 아무것도 들어가지 않는다.

    돌려주는 것은 새로 생긴 것의 수다: nodes_created, relationships_created, properties_set, labels_added.
    """
    total = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0, "labels_added": 0}
    if not statements:
        return total
    payload = [{"statement": s, "parameters": params or {}, "includeStats": True} for s in statements]
    for result in _post(payload):
        stats = result.get("stats", {})
        for key in total:
            total[key] += stats.get(key, 0)
    return total


def split_statements(text):
    """Cypher 파일의 글을 문장의 목록으로 나눈다. 문장은 줄 끝의 쌍반점(;)으로 끝난다. // 로 시작하는 줄은 설명이므로 뺀다."""
    statements, lines = [], []
    for line in text.splitlines():
        if line.strip().startswith("//"):
            continue
        lines.append(line)
        if line.rstrip().endswith(";"):
            statement = "\n".join(lines).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            lines = []
    rest = "\n".join(lines).strip()
    if rest:
        statements.append(rest)
    return statements
