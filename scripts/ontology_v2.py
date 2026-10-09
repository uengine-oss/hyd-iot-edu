"""온톨로지 v2 도구: 스키마 하나(it/neo4j/v2/schema.json)에서 나머지를 만들고, Neo4j에 적재하고, 검사한다.

  python scripts/ontology_v2.py gen                  # constraints.cypher · ontology-schema.ttl(OWL) · schema_prompt.md 생성
  python scripts/ontology_v2.py load     [--uri ...] # 제약 + 인스턴스 적재
  python scripts/ontology_v2.py validate [--uri ...] # 그래프가 스키마를 지키는지 검사 (위반 0건이면 통과)
  python scripts/ontology_v2.py queries  [--uri ...] # queries.cypher의 예시 질의 실행
  python scripts/ontology_v2.py check-extra --extra students/<ID>/schema.json   # 학생 스키마 파일만 검사 (Neo4j 없이)
  python scripts/ontology_v2.py validate --extra students/<ID>/schema.json      # 학생 이름 공간(ns) 노드만, v2 + 학생 스키마로 검사

G4 (전체 과정 랩업, docs/handoff/verification/2026-10-09/capstone-lab.md 3.3 안 다): 학생은 확정 스키마(schema.json)를 고치지 않고
같은 형식의 학생 스키마 파일(students/<ID>/schema.json, "ns": "<ID>")에 업무 고유 클래스 · 관계만 더한다. 검사기는 그 파일을 "추가 층"으로
합쳐 쓴다: v2 클래스 · 관계는 그대로 검사하고, 학생 클래스는 학생 파일로 검사한다. 학생 노드 규칙: ns = "<ID>" 필수, id 는 "<ID>:" 로 시작.
학생 파일의 "ns" 는 필수이고 students/<ID>/ 폴더 이름과 같아야 한다. 그 이름 공간 노드가 0개면 PASS 가 아니라 FAIL(접속 그래프 확인).
학생 스키마는 v2 클래스 · 관계 이름을 다시 정의할 수 없다(공용 사전은 그대로, 내 용어집만 덧댄다).
참고: ProcessGPT ontology-studio 는 스키마 묶음(/api/schemas/{schema_id}, backend/src/modules/ontology/api.py 232~326)을 클래스 이름으로 가른다.
여기서는 v2 상위 클래스(Process · Task · Role · Rule …)를 학생도 쓰므로 클래스 이름이 아니라 노드의 ns 속성으로 가른다(차이 있음, 유지).

기본 접속은 bolt://127.0.0.1:7688 (검증용 별도 Neo4j). 운영 중인 v1 그래프(7687)와 섞지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "it" / "neo4j" / "v2"
SCHEMA = V2 / "schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ G4 학생 이름 공간 (추가 층)
NS_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
NS_PROP = "ns"


def load_extra(path) -> dict:
    """학생 스키마 파일. ns 칸은 필수다(폴더 이름으로 채우지 않는다). students/<폴더>/schema.json 이면 ns 가 폴더 이름과 같아야 한다
    (출발본을 복사하고 ns 를 안 바꾼 실수를 잡는다). '_' 로 시작하는 폴더(출발본 _template)는 예시라 대조하지 않는다.
    형식이 틀리면 파일 좌표가 있는 ValueError."""
    path = Path(path)
    try:
        extra = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path}: 학생 스키마 파일을 읽을 수 없다 — {e}") from e
    if not isinstance(extra, dict):
        raise ValueError(f"{path}: 맨 바깥은 {{\"ns\": …, \"classes\": […], \"relationships\": […]}} 객체여야 한다")
    if not extra.get(NS_PROP):
        raise ValueError(f"{path}: \"ns\" 칸이 없다 — 내 ID 를 적는다 (예: \"ns\": \"s01\")")
    folder = path.resolve().parent
    if folder.parent.name == "students" and not folder.name.startswith("_") and extra[NS_PROP] != folder.name:
        raise ValueError(f"{path}: ns {extra[NS_PROP]!r} 가 폴더 이름 {folder.name!r} 와 다르다 — 출발본의 ns 를 내 ID 로 바꿨는가")
    return extra


def _prop_types(base: dict) -> set[str]:
    """학생 속성 자료형은 v2 가 쓰는 것만 허용한다."""
    return {p["type"] for c in base["classes"] for p in c["properties"]}


def _check_props(name: str, props, allowed_types: set[str]) -> list[str]:
    errs = []
    if not isinstance(props, list):
        return [f"class {name}: properties 는 목록이어야 한다"]
    for i, p in enumerate(props):
        if not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"]:
            errs.append(f"class {name}: properties[{i}] 에 name 이 없다")
            continue
        if p.get("type") not in allowed_types:
            errs.append(f"class {name}.{p['name']}: type {p.get('type')!r} 는 v2 자료형({' · '.join(sorted(allowed_types))})이 아니다")
        elif p["type"] == "enum" and not (isinstance(p.get("values"), list) and p["values"]):
            errs.append(f"class {name}.{p['name']}: enum 은 values 목록이 있어야 한다")
    return errs


def check_extra(base: dict, extra: dict) -> list[str]:
    """학생 스키마 파일 자체의 형식 검사 — 확정 스키마와 같은 형식이고, v2 이름을 다시 정의하지 않는가."""
    errs = []
    ns = extra.get(NS_PROP)
    if not isinstance(ns, str) or not NS_RE.match(ns):
        errs.append(f"ns: 소문자로 시작하는 소문자 · 숫자 · 하이픈 32자 이내여야 한다 (지금 {ns!r})")
    base_classes, base_rels = classes_by_name(base), {r["type"] for r in base["relationships"]}
    layers = {l["id"] for l in base.get("layers") or []}
    cardinalities = {r["cardinality"] for r in base["relationships"]}
    prop_types = _prop_types(base)
    declared = [c for c in extra.get("classes") or [] if isinstance(c, dict)]
    mine = {}
    for c in extra.get("classes") or []:
        name = c.get("name") if isinstance(c, dict) else None
        if not isinstance(name, str) or not re.match(r"^[A-Z][A-Za-z0-9]*$", name):
            errs.append(f"class {name!r}: name 은 대문자로 시작하는 영문 낱말이어야 한다 (예: Meeting)")
            continue
        if name in base_classes:
            errs.append(f"class {name}: 확정 스키마 v2 에 있는 클래스다 — 다시 정의하지 말고 v2 클래스를 그대로 쓴다")
        if name in mine:
            errs.append(f"class {name}: 두 번 정의했다")
        mine[name] = c
        for key in ("label_ko", "layer", "properties"):
            if key not in c:
                errs.append(f"class {name}: {key} 칸이 없다 (확정 스키마와 같은 형식)")
        if c.get("layer") and layers and c["layer"] not in layers:
            errs.append(f"class {name}: layer {c['layer']!r} 는 v2 층({' · '.join(sorted(layers))})이 아니다")
        errs += _check_props(name, c.get("properties") or [], prop_types)
        props = {p.get("name") for p in c.get("properties") or [] if isinstance(p, dict)}
        if not c.get("extends") and not {"id", "name"} <= props:
            errs.append(f"class {name}: id · name 속성이 있어야 한다")
        if NS_PROP in props:
            errs.append(f"class {name}: ns 는 검사기가 모든 학생 노드에 요구하는 칸이라 따로 정의하지 않는다")
        if c.get("extends") and c["extends"] not in base_classes and c["extends"] not in {x.get("name") for x in declared}:
            errs.append(f"class {name}: extends {c['extends']!r} 클래스가 없다")
    known = set(base_classes) | set(mine)
    seen = set()
    for r in extra.get("relationships") or []:
        t = r.get("type") if isinstance(r, dict) else None
        if not isinstance(t, str) or not re.match(r"^[A-Z][A-Z0-9_]*$", t):
            errs.append(f"rel {t!r}: type 은 대문자 · 밑줄 낱말이어야 한다 (예: HAS_AGENDA)")
            continue
        if t in base_rels:
            errs.append(f"rel {t}: 확정 스키마 v2 에 있는 관계다 — v2 끝점 그대로 쓰거나 새 이름을 짓는다")
        if t in seen:
            errs.append(f"rel {t}: 두 번 정의했다")
        seen.add(t)
        for key in ("from", "to", "cardinality"):
            if key not in r:
                errs.append(f"rel {t}: {key} 칸이 없다 (확정 스키마와 같은 형식)")
        if "cardinality" in r and r["cardinality"] not in cardinalities:
            errs.append(f"rel {t}: cardinality {r['cardinality']!r} 는 v2 값({' · '.join(sorted(cardinalities))})이 아니다")
        ends = {}
        for key in ("from", "to"):
            v = r.get(key)
            if key in r and not (isinstance(v, list) and v and all(isinstance(x, str) for x in v)):
                errs.append(f"rel {t}: {key} 는 클래스 이름 목록이어야 한다 (예: [\"Meeting\"]) — 지금 {v!r}")
                v = []
            ends[key] = v or []
        for end in ends["from"] + ends["to"]:
            if end not in known:
                errs.append(f"rel {t}: 끝점 {end} 클래스가 v2 에도 학생 스키마에도 없다")
        if ends["from"] and ends["to"] and not set(ends["from"]) & set(mine) and not set(ends["to"]) & set(mine):
            errs.append(f"rel {t}: 양 끝이 모두 v2 클래스다 — 학생 관계는 한쪽 끝이 내 클래스여야 한다(v2 사이 관계는 확정 스키마 몫)")
    return errs


def merge_schema(base: dict, extra: dict) -> dict:
    """v2 + 학생 스키마(추가 층). base 는 바꾸지 않는다(확정 스키마 변경 0)."""
    out = dict(base)
    out["classes"] = list(base["classes"]) + [dict(c, ns=extra.get(NS_PROP)) for c in extra.get("classes") or []]
    out["relationships"] = list(base["relationships"]) + [dict(r, ns=extra.get(NS_PROP)) for r in extra.get("relationships") or []]
    return out


def ns_rules(records_nodes, ns: str, student_classes) -> list[str]:
    """학생 노드 규칙: 학생 클래스 노드 · ns 를 단 노드 · id 가 '<ns>:' 로 시작하는 노드는 모두 ns = '<ns>' 이고 id 가 '<ns>:' 로 시작한다.
    다른 이름 공간의 노드가 내 클래스 레이블을 쓰면 그 사실 한 줄로만 알린다."""
    errs, prefix, student_classes = [], f"{ns}:", set(student_classes)
    for n in records_nodes:
        props, nid = n["props"], str(n["props"].get("id", "?"))
        other = props.get(NS_PROP)
        if other not in (None, ns):
            if set(n["labels"]) & student_classes:
                errs.append(f"node {nid}: 다른 이름 공간({other})의 노드가 내 클래스를 쓴다")
            elif nid.startswith(prefix):
                errs.append(f"node {nid}: id 는 '{prefix}' 인데 ns 가 {other!r} 다")
            continue
        mine = bool(set(n["labels"]) & student_classes) or other == ns or nid.startswith(prefix)
        if not mine:
            continue
        if other != ns:
            errs.append(f"node {nid}: 학생 노드는 ns = {ns!r} 가 있어야 한다 (지금 {other!r})")
        if not nid.startswith(prefix):
            errs.append(f"node {nid}: 학생 노드 id 는 '{prefix}' 로 시작해야 한다")
    return errs


def scope_to_ns(records_nodes, records_rels, ns: str, student_classes=()):
    """검사 범위: 내 노드(ns · id 접두어 · 학생 클래스)와 그 노드에 닿는 관계. 끝점의 v2 노드(다리 관계)는 레이블로만 검사된다."""
    prefix, student_classes = f"{ns}:", set(student_classes)
    nodes = [n for n in records_nodes if n["props"].get(NS_PROP) == ns or str(n["props"].get("id", "")).startswith(prefix)
             or set(n["labels"]) & student_classes]
    ids = {n["props"].get("id") for n in nodes}
    rels = [r for r in records_rels if r["a"] in ids or r["b"] in ids]
    return nodes, rels


def validate_ns(records_nodes, records_rels, base: dict, extra: dict) -> list[str]:
    """학생 이름 공간 검사: 학생 파일 형식 → 내 노드 · 관계를 v2 + 학생 스키마로 → ns 규칙. ns 속성은 모든 클래스에 허용한다.
    내 노드가 0개면 통과가 아니라 실패다(빈 성공 금지 — 다른 그래프에 붙었거나 적재 전)."""
    errs = check_extra(base, extra)
    if errs:
        return errs
    ns, merged = extra[NS_PROP], merge_schema(base, extra)
    student = [c["name"] for c in extra.get("classes") or []]
    nodes, rels = scope_to_ns(records_nodes, records_rels, ns, student)
    if not nodes:
        return [f"ns {ns}: 이 이름 공간의 노드가 그래프에 0개다 — 적재했는가, 접속(--uri)이 적재한 그래프인가"]
    # 다리 관계의 v2 끝점은 내 범위 밖 노드라 그 노드 자체는 검사하지 않는다(끝점 레이블은 관계 정의로 본다).
    # 출처(SOURCED_FROM · PRODUCES) 검사는 내 입력(InputData)에만 — v2 입력의 출처는 내 조각 밖에 있다.
    errs = validate(nodes, rels, merged, extra_props=(NS_PROP,), input_scope={n["props"].get("id") for n in nodes})
    errs += ns_rules(nodes, ns, student)
    return errs


def classes_by_name(s: dict) -> dict:
    return {c["name"]: c for c in s["classes"]}


def all_props(s: dict, cname: str) -> list[dict]:
    """A class's own properties plus its parent's (extends)."""
    by = classes_by_name(s)
    c = by[cname]
    parent = by[c["extends"]]["properties"] if c.get("extends") else []
    own = {p["name"] for p in c["properties"]}
    return [p for p in parent if p["name"] not in own] + c["properties"]


# ------------------------------------------------------------------ generation
def gen_constraints(s: dict) -> str:
    out = ["// 생성 파일 — scripts/ontology_v2.py gen (원본: schema.json). 직접 고치지 않는다.", ""]
    for c in s["classes"]:
        if c.get("extends"):
            continue  # 부모(FlowNode) 레이블에 건다
        if any(p["name"] == "id" for p in c["properties"]):
            out.append(f"CREATE CONSTRAINT v2_{c['name'].lower()}_id IF NOT EXISTS FOR (n:{c['name']}) REQUIRE n.id IS UNIQUE;")
    searchable = [c["name"] for c in s["classes"] if any(p["name"] == "aliases" for p in c["properties"])]
    out += ["", "// 엔티티 인식(entity resolution)용 전문 검색 색인: 이름과 다른 이름(aliases)",
            f"CREATE FULLTEXT INDEX ont_names IF NOT EXISTS FOR (n:{'|'.join(searchable)}) ON EACH [n.name, n.aliases];",
            "CREATE CONSTRAINT execution_projection_id IF NOT EXISTS FOR (n:ExecutionProjection) REQUIRE n.id IS UNIQUE;",
            "CREATE CONSTRAINT case_projection_id IF NOT EXISTS FOR (n:CaseProjection) REQUIRE n.id IS UNIQUE;", ""]
    return "\n".join(out)


XSD = {"string": "xsd:string", "integer": "xsd:integer", "number": "xsd:decimal", "boolean": "xsd:boolean",
       "datetime": "xsd:dateTime", "enum": "xsd:string", "string[]": "xsd:string", "any": "rdfs:Literal"}


def _ttl_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"@ko'


def _union(names: list[str]) -> str:
    if len(names) == 1:
        return f"hyd:{names[0]}"
    return "[ a owl:Class ; owl:unionOf ( " + " ".join(f"hyd:{n}" for n in names) + " ) ]"


def gen_ttl(s: dict) -> str:
    ns = s["namespace"]
    L = [f"@prefix hyd: <{ns}> .", "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
         "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
         "@prefix dcterms: <http://purl.org/dc/terms/> .", "",
         "# 생성 파일 — scripts/ontology_v2.py gen (원본: it/neo4j/v2/schema.json). 직접 고치지 않는다.",
         "# 관계의 속성(sign, condition 등)은 OWL로 표현하지 않고 rdfs:comment에 적었다 (Neo4j 관계 속성으로 구현).", "",
         f"<{ns.rstrip('#')}> a owl:Ontology ;", f"  rdfs:label {_ttl_str(s['name'])} ;",
         f"  owl:versionInfo \"{s['version']}\" ;", f"  rdfs:comment {_ttl_str(s['description'])} .", "",
         "hyd:layer a owl:AnnotationProperty ; rdfs:label \"계층\"@ko .",
         "hyd:standard a owl:AnnotationProperty ; rdfs:label \"준용 표준\"@ko .",
         "hyd:cardinality a owl:AnnotationProperty ; rdfs:label \"다중도\"@ko .", ""]
    layers = {l["id"]: l for l in s["layers"]}
    L.append("# ---------------------------------------------------------------- classes")
    for c in s["classes"]:
        lines = [f"hyd:{c['name']} a owl:Class ;", f"  rdfs:label \"{c['name']}\" ;",
                 f"  rdfs:comment {_ttl_str(c['description'])} ;", f"  hyd:layer {_ttl_str(layers[c['layer']]['name'])} ;",
                 f"  hyd:standard {_ttl_str(c['standard'])}"]
        if c.get("extends"):
            lines[-1] += " ;"
            lines.append(f"  rdfs:subClassOf hyd:{c['extends']}")
        L.append("\n".join(lines) + " .")
    L += ["", "# ---------------------------------------------------------------- object properties (graph relationships)"]
    for r in s["relationships"]:
        comment = r["description"]
        if r.get("properties"):
            comment += " | 관계 속성: " + ", ".join(p["name"] + (" (필수)" if p.get("required") else "") for p in r["properties"])
        if r.get("endpointPairs"):
            comment += " | 허용된 끝점 쌍: " + ", ".join(f"{a} → {b}" for a, b in r["endpointPairs"])
        L.append("\n".join([f"hyd:{r['type']} a owl:ObjectProperty ;", f"  rdfs:label \"{r['type']}\" ;",
                            f"  rdfs:domain {_union(r['from'])} ;", f"  rdfs:range {_union(r['to'])} ;",
                            f"  hyd:cardinality \"{r['cardinality']}\" ;", f"  rdfs:comment {_ttl_str(comment)} ."]))
    L += ["", "# ---------------------------------------------------------------- datatype properties (node properties)"]
    props: dict[str, dict] = {}
    for c in s["classes"]:
        for p in c["properties"]:
            e = props.setdefault(p["name"], {"classes": [], "type": p["type"], "desc": p.get("description"), "values": p.get("values")})
            e["classes"].append(c["name"])
    for name, e in sorted(props.items()):
        rng = XSD.get(e["type"], "xsd:string")
        desc = e["desc"] or ""
        if e["values"]:
            desc = (desc + " " if desc else "") + "허용값: " + ", ".join(map(str, e["values"]))
        lines = [f"hyd:{name} a owl:DatatypeProperty ;", f"  rdfs:label \"{name}\" ;", f"  rdfs:domain {_union(e['classes'])} ;", f"  rdfs:range {rng}"]
        if desc:
            lines[-1] += " ;"
            lines.append(f"  rdfs:comment {_ttl_str(desc)}")
        L.append("\n".join(lines) + " .")
    return "\n".join(L) + "\n"


def gen_prompt(s: dict) -> str:
    """Compact schema text handed to the agent (the 'DDL' of GraphRAG / Text2Cypher)."""
    by_layer: dict[str, list] = {}
    for c in s["classes"]:
        by_layer.setdefault(c["layer"], []).append(c)
    out = ["# 온톨로지 스키마 (에이전트 제공용)", "",
           "생성 파일이다 (scripts/ontology_v2.py gen, 원본 it/neo4j/v2/schema.json). 에이전트는 이 스키마와 사용자의 질문을 함께 받아 Cypher를 만든다.", "",
           "## 규칙", ""]
    out += [f"- {v}" for v in s["conventions"].values()]
    out += ["- 질문에 나온 말은 먼저 전문 검색 색인으로 노드를 찾는다: `CALL db.index.fulltext.queryNodes('ont_names', $text)`.",
            "- 상충 관계 질문은 `AFFECTS` 한 번 뒤에 `INFLUENCES*`를 따라 `msr:op-profit`까지 가는 경로를 찾고, 경로의 sign을 곱해 방향을 정한다.",
            "- 조치 방법은 Skill이다. 스킬 하나가 SOP 하나이고(sopId, 단계), 고장 유형에 매칭된다: `(:FailureMode)-[:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY]->(:Skill)` (즉시 완화 · 근본 조치 · 예방 조치 = 정기 정비). 근본 조치가 특정 원인에만 맞으면 `(:Skill)-[:ADDRESSES]->(:Cause)`가 있다. 경보(고장) 대응 후보는 MITIGATED_BY · REMEDIED_BY만 따라가고, 정기 정비 도래(PM_DUE) 후보는 PREVENTED_BY 스킬이다.",
            "- 조치 카드의 출처는 `Rule-[:DERIVED_FROM]->`와 `Skill-[:HAS_STEP]->Step-[:REFERS_TO]->ManualSection` 경로다.", ""]
    for l in sorted(s["layers"], key=lambda x: (x["order"], x["id"])):
        out += [f"## {l['name']} — {l['standard']}", "", l["description"], ""]
        for c in by_layer.get(l["id"], []):
            ps = []
            for p in all_props(s, c["name"]):
                t = p["name"] + ("!" if p.get("required") else "")
                if p.get("values"):
                    t += "[" + "|".join(map(str, p["values"])) + "]"
                ps.append(t)
            labels = c["name"] + (":" + c["extends"] if c.get("extends") else "")
            out.append(f"- `(:{labels} {{{', '.join(ps)}}})` {c['description']}")
            for req in c.get("requiredRelationships", []):
                out.append(f"  - 필수: {req['description']} (`{'|'.join(req['type'])}` {req['direction']}, 최소 {req.get('min', 1)})")
        out.append("")
    out += ["## 관계", "", "`!`는 필수 속성이다.", ""]
    for r in s["relationships"]:
        rp = ""
        if r.get("properties"):
            rp = " {" + ", ".join(p["name"] + ("!" if p.get("required") else "") for p in r["properties"]) + "}"
        out.append(f"- `(:{'|'.join(r['from'])})-[:{r['type']}{rp}]->(:{'|'.join(r['to'])})` {r['cardinality']}. {r['description']}")
        if r.get("endpointPairs"):
            out.append("  - 허용된 끝점 쌍: " + ", ".join(f"`{a} → {b}`" for a, b in r["endpointPairs"]) + ". 위 from/to 목록의 모든 조합을 허용하는 것은 아니다.")
    return "\n".join(out) + "\n"


LAYER_COLORS = {"value": "#6d28d9", "process": "#1d4ed8", "resource": "#4b5563", "diagnosis": "#b42318",
                "skill": "#0f766e", "external": "#9a6700", "record": "#7c2d12"}
SVG_COLUMNS = [["value"], ["process"], ["resource"], ["diagnosis"], ["skill"], ["external", "record"]]
DOCS = ROOT / "docs" / "ontology"


def _xml(v: str) -> str:
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def gen_svg(s: dict) -> str:
    """One picture of every class and every relationship of the schema (layers as columns, relationship names on the edges)."""
    BW, BH, COLW, GAPY, TOP, LEFT = 196, 46, 400, 34, 136, 30
    layers = {l["id"]: l for l in s["layers"]}
    pos: dict[str, tuple[float, float]] = {}
    heads = []
    max_y = 0
    for ci, ids in enumerate(SVG_COLUMNS):
        x = LEFT + ci * COLW
        y = TOP
        for lid in ids:
            heads.append((x, y - 16, layers[lid]["name"], LAYER_COLORS[lid]))
            for c in [c for c in s["classes"] if c["layer"] == lid]:
                pos[c["name"]] = (x, y)
                y += BH + GAPY
            y += 52
        max_y = max(max_y, y)
    W, H = LEFT + len(SVG_COLUMNS) * COLW - (COLW - BW) + 110, max_y + 30
    by = classes_by_name(s)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Pretendard, \'Noto Sans KR\', \'Malgun Gothic\', sans-serif">',
           "<defs>",
           '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker>',
           '<marker id="tri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" orient="auto"><path d="M0 0L12 6L0 12z" fill="#fff" stroke="#374151"/></marker>',
           "</defs>",
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="{LEFT}" y="34" font-size="22" font-weight="700" fill="#111827">{_xml(s["name"])} v{_xml(s["version"])} — 클래스 {len(s["classes"])}개 · 관계 {len(s["relationships"])}종</text>',
           f'<text x="{LEFT}" y="58" font-size="13" fill="#4b5563">BSC(관점 · 전략 목표 · 성과 지표) → 프로세스(BPMN) → 리소스 → 설비 진단(ISO 13374) → 조치 방법 = Skill = SOP · 규칙(DMN) → 외부 변수 · 예측 · 운영 기록. 화살표 = 관계 방향, 점선 삼각형 = 상속</text>']
    for x, y, name, col in heads:
        out.append(f'<text x="{x}" y="{y}" font-size="14" font-weight="700" fill="{col}">{_xml(name)}</text>')
    pairs = []
    for r in s["relationships"]:
        for a in r["from"]:
            for b in r["to"]:
                pairs.append((a, b, r["type"]))
    edges, labels = [], []
    same_col_count: dict[str, int] = {}
    for i, (a, b, t) in enumerate(pairs):
        ax, ay = pos[a]
        bx, byy = pos[b]
        col = LAYER_COLORS[by[a]["layer"]]
        if a == b:                                         # self relationship: loop on the right edge
            x0, y0 = ax + BW, ay + BH * 0.35
            pts = ((x0, y0), (x0 + 46, y0 - 26), (x0 + 46, y0 + 30), (x0, y0 + 16))
        elif abs(ax - bx) < 1:                             # same column: arc on the right side
            n = same_col_count[a + b] = same_col_count.get(a + b, 0) + 1
            x0, y0, y1 = ax + BW, ay + BH / 2, byy + BH / 2
            bend = 34 + 14 * (abs(y1 - y0) / (BH + GAPY)) ** 0.5 + 8 * n
            pts = ((x0, y0), (x0 + bend, y0), (x0 + bend, y1), (x0, y1))
        else:
            right = bx > ax
            x0 = ax + (BW if right else 0)
            x1 = bx + (0 if right else BW)
            y0, y1 = ay + BH / 2, byy + BH / 2
            dx = (x1 - x0) * 0.45
            pts = ((x0, y0), (x0 + dx, y0), (x1 - dx, y1), (x1, y1))
        (p0, p1, p2, p3) = pts
        d = f"M{p0[0]:.1f},{p0[1]:.1f} C{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} {p3[0]:.1f},{p3[1]:.1f}"
        edges.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.2" stroke-opacity="0.55" marker-end="url(#arr)"><title>{_xml(a)} -[{_xml(t)}]-> {_xml(b)}</title></path>')
        labels.append((pts, t, col))
    for c in s["classes"]:                                  # inheritance
        if c.get("extends"):
            ax, ay = pos[c["name"]]
            bx, byy = pos[c["extends"]]
            edges.append(f'<path d="M{ax + 18},{ay} L{bx + 18},{byy + BH}" fill="none" stroke="#374151" stroke-dasharray="4 3" marker-end="url(#tri)"/>')
    out += edges
    def bez(pts, u):
        (a0, a1, a2, a3) = pts
        f = lambda i: (1 - u) ** 3 * a0[i] + 3 * (1 - u) ** 2 * u * a1[i] + 3 * (1 - u) * u * u * a2[i] + u ** 3 * a3[i]
        return f(0), f(1)
    boxes = [(x, y, x + BW, y + BH) for (x, y) in pos.values()]
    placed: list[tuple[float, float, float]] = []
    def free(lx, ly, w):
        if any(bx0 - 4 < lx + w / 2 and lx - w / 2 < bx1 + 4 and by0 - 6 < ly and ly - 9 < by1 + 2 for bx0, by0, bx1, by1 in boxes):
            return False
        return all(abs(lx - px) > (w + pw) / 2 + 4 or abs(ly - py) > 11 for px, py, pw in placed)
    for pts, t, col in labels:                             # put each label on its own curve where nothing else is
        w = 6.1 * len(t)
        best = None
        for u in (0.5, 0.4, 0.6, 0.3, 0.7, 0.22, 0.78, 0.15, 0.85):
            lx, ly = bez(pts, u)
            if free(lx, ly, w):
                best = (lx, ly)
                break
        if best is None:
            lx, ly = bez(pts, 0.5)
            for _ in range(14):
                ly += 11
                if free(lx, ly, w):
                    break
            best = (lx, ly)
        placed.append((best[0], best[1], w))
        out.append(f'<text x="{best[0]:.0f}" y="{best[1] + 3:.0f}" font-size="9.5" text-anchor="middle" fill="{col}" stroke="#fff" stroke-width="3" paint-order="stroke">{_xml(t)}</text>')
    for c in s["classes"]:
        x, y = pos[c["name"]]
        col = LAYER_COLORS[c["layer"]]
        dash = ' stroke-dasharray="5 3"' if c.get("abstract") else ""
        out.append(f'<g><rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="7" fill="#fff" stroke="{col}" stroke-width="1.8"{dash}/>'
                   f'<rect x="{x}" y="{y}" width="6" height="{BH}" rx="3" fill="{col}"/>'
                   f'<text x="{x + 14}" y="{y + 19}" font-size="14" font-weight="700" fill="#111827">{_xml(c["name"])}</text>'
                   f'<text x="{x + 14}" y="{y + 37}" font-size="12" fill="#374151">{_xml(c.get("label_ko", ""))}</text>'
                   f'<title>{_xml(c["name"])} ({_xml(c.get("label_ko", ""))}) — {_xml(c["standard"])}</title></g>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def gen_class_table(s: dict) -> str:
    layers = {l["id"]: l["name"] for l in s["layers"]}
    rows = ["| 계층 | 클래스 (영문) | 클래스 (한글) | 준용 표준 |", "|---|---|---|---|"]
    for c in s["classes"]:
        rows.append(f"| {layers[c['layer']]} | {c['name']} | {c.get('label_ko', '')} | {c['standard']} |")
    return "\n".join(rows) + "\n"


def cmd_gen(_args) -> int:
    s = load_schema()
    (V2 / "constraints.cypher").write_text(gen_constraints(s), encoding="utf-8", newline="\n")
    (V2 / "ontology-schema.ttl").write_text(gen_ttl(s), encoding="utf-8", newline="\n")
    (V2 / "schema_prompt.md").write_text(gen_prompt(s), encoding="utf-8", newline="\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "ontology-classes.svg").write_text(gen_svg(s), encoding="utf-8", newline="\n")
    (DOCS / "class-table.md").write_text("# 온톨로지 클래스 (생성 파일 — schema.json)\n\n" + gen_class_table(s), encoding="utf-8", newline="\n")
    print(f"generated constraints.cypher, ontology-schema.ttl, schema_prompt.md, docs/ontology/ontology-classes.svg, class-table.md "
          f"({len(s['classes'])} classes, {len(s['relationships'])} relationships)")
    return 0


# ------------------------------------------------------------------ database
SEED_FILES = ("constraints.cypher", "instances.cypher", "knowledge_a098.cypher", "scenario_structure.cypher", "detector-patterns.cypher")
EDITIONS = ("structure", "full")
EDITION_MARK = "// @edition "


def edition_filter(text: str, edition: str) -> str:
    """확정 TODO C1 시드 두 판: '// @edition full|structure' 표시 바로 뒤의 문장(다음 주석 아닌 줄부터 ';'로 끝나는 줄까지)은
    그 판에서만 남긴다. it/neo4j/edition.sh seed_edition_filter와 같은 규칙이다(tests/test_seed_editions.py가 대조)."""
    if edition not in EDITIONS:
        raise ValueError(f"edition must be one of {EDITIONS}")
    out, pending, active, keep = [], None, False, True
    for line in text.split("\n"):
        trimmed = line.lstrip()
        if not active:
            if trimmed in (EDITION_MARK + "full", EDITION_MARK + "structure"):
                pending = trimmed[len(EDITION_MARK):]
                continue
            if trimmed.startswith("//") or trimmed == "":
                out.append(line)
                continue
            active, keep, pending = True, (pending is None or pending == edition), None
        elif trimmed.startswith("//"):
            if keep:
                out.append(line)
            continue
        if keep:
            out.append(line)
        if line.rstrip().endswith(";"):
            active, keep = False, True
    return "\n".join(out)


def edition_checks(text: str, edition: str) -> list[str]:
    """seed_checks.cypher에서 이 판이 실행할 질의 줄(표시는 바로 뒤의 질의 한 줄에만 적용). edition.sh seed_edition_checks와 같다."""
    out, want = [], None
    for line in text.split("\n"):
        if line in (EDITION_MARK + "full", EDITION_MARK + "structure"):
            want = line[len(EDITION_MARK):]
            continue
        if not line or line.startswith("//"):
            continue
        if want is None or want == edition:
            out.append(line)
        want = None
    return out


def split_statements(text: str) -> list[str]:
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    return [st.strip() for st in re.split(r";\s*\n", body + "\n") if st.strip()]


def driver(args):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(args.uri, auth=(args.user, args.password))


def cmd_load(args) -> int:
    with driver(args) as d, d.session() as ses:
        if args.wipe:
            ses.run("MATCH (n) DETACH DELETE n").consume()
            for r in list(ses.run("SHOW CONSTRAINTS YIELD name RETURN name")):
                ses.run(f"DROP CONSTRAINT `{r['name']}` IF EXISTS").consume()
            for r in list(ses.run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name")):
                ses.run(f"DROP INDEX `{r['name']}` IF EXISTS").consume()
        for f in SEED_FILES:
            sts = split_statements(edition_filter((V2 / f).read_text(encoding="utf-8"), args.edition))
            for i, st in enumerate(sts, 1):
                try:
                    ses.run(st).consume()
                except Exception as e:  # noqa: BLE001
                    print(f"{f} statement {i} failed: {e}\n---\n{st[:400]}")
                    return 1
            print(f"{f}: {len(sts)} statements")
        n = ses.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        r = ses.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"graph: {n} nodes, {r} relationships")
    return 0


def validate(records_nodes, records_rels, s: dict, *, extra_props=(), input_scope=None) -> list[str]:
    """Pure check of graph rows against the schema. Returns a list of violations.
    extra_props (G4): property names allowed on every node (the student namespace's `ns`).
    input_scope (G4): when only one student's slice is checked, the input-source check covers only these node ids
    (a base InputData read by a student task has its source outside the slice) — see validate_ns."""
    by = classes_by_name(s)
    rel_by = {r["type"]: r for r in s["relationships"]}
    errs = []
    for n in records_nodes:
        labels, props, nid = set(n["labels"]), n["props"], n["props"].get("id", "?")
        unknown = labels - set(by)
        if unknown:
            errs.append(f"node {nid}: 스키마에 없는 레이블 {sorted(unknown)}")
        concrete = [l for l in labels if l in by and not by[l].get("abstract")]
        if not concrete:
            errs.append(f"node {nid}: 구체 클래스 레이블이 없다 {sorted(labels)}")
        for l in concrete:
            c = by[l]
            if c.get("extends") and c["extends"] not in labels:
                errs.append(f"node {nid}: {l}는 부모 레이블 {c['extends']}도 달아야 한다")
            for p in all_props(s, l):
                v = props.get(p["name"])
                if p.get("required") and v is None:
                    errs.append(f"node {nid} ({l}): 필수 속성 {p['name']} 없음")
                if v is not None and p.get("values") and p["type"] == "enum" and v not in p["values"]:
                    errs.append(f"node {nid} ({l}): {p['name']}={v!r} 허용값 아님 {p['values']}")
            declared = {p["name"] for p in all_props(s, l)} | set(extra_props)
            for k in props:
                if k not in declared and not any(k in {p["name"] for p in all_props(s, o)} for o in concrete):
                    errs.append(f"node {nid} ({l}): 스키마에 없는 속성 {k}")
    for r in records_rels:
        t = r["type"]
        if t not in rel_by:
            errs.append(f"rel {t}: 스키마에 없는 관계 ({r['a']} → {r['b']})")
            continue
        spec = rel_by[t]
        if not set(r["la"]) & set(spec["from"]) or not set(r["lb"]) & set(spec["to"]):
            errs.append(f"rel {t}: {r['a']}{r['la']} → {r['b']}{r['lb']} 는 허용된 끝점({spec['from']} → {spec['to']})이 아님")
        elif spec.get("endpointPairs") and not any(a in r['la'] and b in r['lb'] for a, b in spec['endpointPairs']):
            errs.append(f"rel {t}: {r['a']} → {r['b']} 는 허용된 끝점 쌍이 아님 {spec['endpointPairs']}")
        for p in spec.get("properties", []):
            v = r["props"].get(p["name"])
            if p.get("required") and v is None:
                errs.append(f"rel {t} ({r['a']} → {r['b']}): 필수 속성 {p['name']} 없음")
            if v is not None and p.get("values") and v not in p["values"]:
                errs.append(f"rel {t} ({r['a']} → {r['b']}): {p['name']}={v!r} 허용값 아님")
        allowed = {p["name"] for p in spec.get("properties", [])}
        for k in r["props"]:
            if k not in allowed:
                errs.append(f"rel {t} ({r['a']} → {r['b']}): 스키마에 없는 관계 속성 {k}")
    # class-level required relationships (e.g. every Skill = SOP has steps and is matched to a FailureMode)
    for n in records_nodes:
        nid = n["props"].get("id")
        for l in n["labels"]:
            for req in by.get(l, {}).get("requiredRelationships", []):
                if any(n["props"].get(k) in v for k, v in req.get("unlessProperty", {}).items()):
                    continue
                if req["direction"] == "out":
                    cnt = sum(1 for r in records_rels if r["a"] == nid and r["type"] in req["type"])
                else:
                    cnt = sum(1 for r in records_rels if r["b"] == nid and r["type"] in req["type"]
                              and (not req.get("fromClass") or req["fromClass"] in r["la"]))
                if cnt < req.get("min", 1):
                    errs.append(f"node {nid} ({l}): 필수 관계 위반 — {req['description']} ({'/'.join(req['type'])} {cnt}개)")
    errs += integrity(records_nodes, records_rels, input_scope=input_scope)
    return errs


def _out(rels, t, a=None):
    return [(r["a"], r["b"], r["props"]) for r in rels if r["type"] == t and (a is None or r["a"] == a)]


def integrity(records_nodes, records_rels, *, input_scope=None) -> list[str]:
    """Cross-layer checks the scenarios rely on (DMN consistency, BPMN data connectivity).
    input_scope: check the "every read input has a source or a producer" rule only for these input ids (None = all)."""
    errs = []
    props = {n["props"].get("id"): n["props"] for n in records_nodes}
    # DMN: a rule's TESTS read inputs its decision declares; the readable 'when' states the same thresholds
    table_of_rule = {b: a for a, b, _ in _out(records_rels, "HAS_RULE")}
    decision_of_table = {b: a for a, b, _ in _out(records_rels, "IMPLEMENTED_BY")}
    for rule, inp, tp in _out(records_rels, "TESTS"):
        var = props.get(inp, {}).get("variable", "?")
        when = props.get(rule, {}).get("when")
        if when is not None:
            val = tp.get("value")
            sval = ("true" if val else "false") if isinstance(val, bool) else (str(int(val)) if isinstance(val, float) and val.is_integer() else str(val))
            if f"{var} {tp.get('operator')}" not in when or sval not in when:
                errs.append(f"rule {rule}: when '{when}' 에 TESTS ({var} {tp.get('operator')} {sval}) 가 드러나지 않는다")
        dec = decision_of_table.get(table_of_rule.get(rule))
        if dec and inp not in {b for _, b, _ in _out(records_rels, "REQUIRES_INPUT", dec)}:
            errs.append(f"decision {dec}: 규칙 {rule}이 검사하는 {inp}를 REQUIRES_INPUT에 선언하지 않았다")
    # BPMN: a businessRule task reads every input its decision requires; every read input has a source or a producer
    produced = {b for _, b, _ in _out(records_rels, "PRODUCES")}
    sourced = {a for a, _, _ in _out(records_rels, "SOURCED_FROM")}
    for task, dec, _ in _out(records_rels, "INVOKES"):
        reads = {b for _, b, _ in _out(records_rels, "READS", task)}
        for _, inp, _ in _out(records_rels, "REQUIRES_INPUT", dec):
            if inp not in reads:
                errs.append(f"task {task}: 부르는 판단 {dec}의 입력 {inp}를 READS로 잇지 않았다")
    for _, inp, _ in _out(records_rels, "READS"):
        if input_scope is not None and inp not in input_scope:
            continue
        if inp not in produced and inp not in sourced:
            errs.append(f"input {inp}: 출처(SOURCED_FROM)도 만드는 작업(PRODUCES)도 없다")
    errs += kpi_role_integrity(records_nodes, records_rels)
    return errs


def kpi_role_integrity(records_nodes, records_rels) -> list[str]:
    """A144 (D02): BSC leading/lagging roles must agree with the strategy-map causality. A lagging (outcome) Measure never
    INFLUENCES a leading (driver) Measure, and every leading Measure reaches some lagging Measure through INFLUENCES
    (a driver that drives no outcome is not a driver). Measures without a role are reported by validate() as a missing
    required property; here they are skipped so one defect is reported once."""
    role = {n["props"].get("id"): n["props"].get("kpiRole") for n in records_nodes if "Measure" in n["labels"]}
    edges = [(a, b) for a, b, _ in _out(records_rels, "INFLUENCES") if a in role and b in role]
    errs = []
    for a, b in edges:
        if role[a] == "lagging" and role[b] == "leading":
            errs.append(f"measure {a}: 후행(lagging) 지표가 선행(leading) 지표 {b}에 INFLUENCES — 전략맵 인과 방향 위반")
    out = {}
    for a, b in edges:
        out.setdefault(a, set()).add(b)
    for m, r in role.items():
        if r != "leading":
            continue
        seen, stack, reached = set(), [m], False
        while stack and not reached:
            cur = stack.pop()
            for nxt in out.get(cur, ()):
                if role.get(nxt) == "lagging":
                    reached = True
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if not reached:
            errs.append(f"measure {m}: 선행(leading) 지표인데 INFLUENCES 경로로 닿는 후행(lagging) 지표가 없다")
    return errs


def usage_report(records_nodes, records_rels, s: dict) -> list[str]:
    """Minimal-set check: schema elements (classes, properties, enum values, relationships, relationship properties)
    that no instance uses. The schema should carry only what the scenarios need."""
    out = []
    for c in s["classes"]:
        if c.get("abstract"):
            continue
        inst = [n["props"] for n in records_nodes if c["name"] in n["labels"]]
        if not inst:
            out.append(f"class {c['name']}")
            continue
        for p in c["properties"]:
            vals = [i[p["name"]] for i in inst if i.get(p["name"]) is not None]
            if not vals:
                out.append(f"property {c['name']}.{p['name']}")
            elif p["type"] == "enum" and p.get("values"):
                unused = [v for v in p["values"] if v not in vals]
                if unused:
                    out.append(f"enum {c['name']}.{p['name']} {unused}")
    for r in s["relationships"]:
        inst = [x["props"] for x in records_rels if x["type"] == r["type"]]
        if not inst:
            out.append(f"relationship {r['type']}")
            continue
        for p in r.get("properties", []):
            if not any(i.get(p["name"]) is not None for i in inst):
                out.append(f"relationship property {r['type']}.{p['name']}")
    return out


def _graph_rows(args):
    with driver(args) as d, d.session() as ses:
        nodes = [{"labels": r["l"], "props": dict(r["p"])} for r in ses.run("MATCH (n) RETURN labels(n) AS l, properties(n) AS p")]
        rels = [{"type": r["t"], "a": r["a"], "b": r["b"], "la": r["la"], "lb": r["lb"], "props": dict(r["p"])} for r in ses.run(
            "MATCH (a)-[x]->(b) RETURN type(x) AS t, a.id AS a, b.id AS b, labels(a) AS la, labels(b) AS lb, properties(x) AS p")]
    return nodes, rels


def _report(errs: list[str], noun: str) -> int:
    for e in errs:
        print(" -", e)
    print("PASS" if not errs else f"FAIL ({len(errs)} {noun})")
    return 0 if not errs else 1


def cmd_check_extra(args) -> int:
    if not args.extra:
        print("check-extra 에는 --extra students/<ID>/schema.json 이 필요하다")
        return 2
    base = load_schema()
    try:
        extra = load_extra(args.extra)
    except ValueError as e:
        return _report([str(e)], "problems")
    errs = check_extra(base, extra)
    print(f"student schema {args.extra}: ns={extra.get(NS_PROP)!r}, {len(extra.get('classes') or [])} classes, "
          f"{len(extra.get('relationships') or [])} relationships (v2 {len(base['classes'])} classes unchanged)")
    return _report(errs, "problems")


def cmd_validate_ns(args) -> int:
    base = load_schema()
    try:
        extra = load_extra(args.extra)
    except ValueError as e:
        return _report([str(e)], "violations")
    nodes, rels = _graph_rows(args)
    errs = validate_ns(nodes, rels, base, extra)
    mine, my_rels = scope_to_ns(nodes, rels, extra[NS_PROP], [c.get("name") for c in extra.get("classes") or [] if isinstance(c, dict)])
    print(f"namespace {extra[NS_PROP]!r} @ {args.uri}: checked {len(mine)} nodes, {len(my_rels)} relationships against v2 + {args.extra}")
    return _report(errs, "violations")


def cmd_validate(args) -> int:
    if getattr(args, "extra", None):
        return cmd_validate_ns(args)
    s = load_schema()
    nodes, rels = _graph_rows(args)
    errs = validate(nodes, rels, s)
    used = {l for n in nodes for l in n["labels"]}
    unused = [c["name"] for c in s["classes"] if c["name"] not in used]
    print(f"checked {len(nodes)} nodes, {len(rels)} relationships against {len(s['classes'])} classes / {len(s['relationships'])} relationship types")
    if unused:
        print("classes with no instance:", unused)
    for e in errs:
        print(" -", e)
    unused_elems = usage_report(nodes, rels, s)
    if unused_elems:
        print(f"minimal-set: {len(unused_elems)} schema elements unused by any instance:")
        for u in unused_elems:
            print("   ·", u)
    else:
        print("minimal-set: every schema element is used by the scenario instances")
    print("PASS" if not errs else f"FAIL ({len(errs)} violations)")
    return 0 if not errs else 1


def parse_queries(text: str) -> list[dict]:
    """queries.cypher blocks: '// @query <name>' then '// @ask <question>' then optional '// @params {...}', then Cypher until the next @query."""
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"\s*//\s*@query\s+(\S+)", line)
        if m:
            cur = {"name": m.group(1), "ask": "", "params": {}, "cypher": []}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"\s*//\s*@ask\s+(.*)", line)
        if m:
            cur["ask"] = m.group(1)
            continue
        m = re.match(r"\s*//\s*@params\s+(.*)", line)
        if m:
            cur["params"] = json.loads(m.group(1))
            continue
        if line.strip().startswith("//"):
            continue
        cur["cypher"].append(line)
    for q in out:
        q["cypher"] = "\n".join(q["cypher"]).strip().rstrip(";")
    return out


def cmd_queries(args) -> int:
    qs = parse_queries((V2 / "queries.cypher").read_text(encoding="utf-8"))
    bad = 0
    with driver(args) as d, d.session() as ses:
        for q in qs:
            if args.only and q["name"] != args.only:
                continue
            rows = [r.data() for r in ses.run(q["cypher"], q["params"])]
            print(f"\n=== {q['name']} — {q['ask']}  ({len(rows)} rows)")
            for r in rows[: args.limit]:
                print("  ", json.dumps(r, ensure_ascii=False, default=str)[:400])
            bad += 0 if rows else 1
    print(f"\n{len(qs)} queries, {bad} empty")
    return 0 if not bad else 1


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "load", "validate", "queries", "check-extra"])
    ap.add_argument("--uri", default=os.getenv("V2_NEO4J_URI", "bolt://127.0.0.1:7688"))
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default=os.getenv("V2_NEO4J_PASSWORD", "hydpass123"))
    ap.add_argument("--wipe", action="store_true", help="load: 적재 전에 그래프를 비운다 (검증용 DB에서만)")
    ap.add_argument("--edition", choices=EDITIONS, default="full", help="load: 시드 판 (structure 수업용 구조판 · full 회귀용 전체판)")
    ap.add_argument("--only", help="queries: 이 이름의 질의만")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--extra", help="validate · check-extra: 학생 스키마 파일(students/<ID>/schema.json) — 그 이름 공간 노드만 v2 + 학생 스키마로 검사 (G4)")
    a = ap.parse_args(argv)
    return {"gen": cmd_gen, "load": cmd_load, "validate": cmd_validate, "queries": cmd_queries, "check-extra": cmd_check_extra}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
