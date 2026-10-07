# -*- coding: utf-8 -*-
"""hyd-iot-edu 부록: 저장소 파일에서 빌드 때마다 직접 뽑는 전체 목록. 반환 (html, 대조용 이름 dict)."""
import json, pathlib, re

import arch_inventory as I
from arch_inventory import code, esc, table

ROOT = pathlib.Path(__file__).resolve().parents[2]


def kafka_topics():
    s = (ROOT / "it/redpanda/topics.sh").read_text(encoding="utf-8")
    rows, names = [], []
    for m in re.finditer(r"^create\s+(\S+)\s+(.+?)\s*(#.*)?$", s, re.M):
        names.append(m.group(1))
        rows.append([code(m.group(1)), esc(m.group(2)), "1", "1", esc((m.group(3) or "").lstrip("# "))])
    assert len(names) == len(re.findall(r"^create\s", s, re.M)), "topics.sh 의 create 줄을 다 읽지 못함"
    return table(["토픽", "보존(retention.ms 식)", "파티션", "복제", "주석(원문)"], rows), names


def mqtt_topics():
    s = (ROOT / "common/hydcommon/topics.py").read_text(encoding="utf-8")
    rows, names = [], []
    for m in re.finditer(r"def (mqtt_\w+)\(([^)]*)\)[^:]*:\s*\n(?:\s*\"\"\"[^\n]*\"\"\"\s*\n)?\s*return\s+(f?[\"'][^\n]+)", s):
        pat = m.group(3).strip()
        rows.append([code(m.group(1)), esc(m.group(2)), code(pat)])
        names.append(re.sub(r"^f?[\"']|[\"']$", "", pat))
    assert len(names) == len(re.findall(r"^def mqtt_", s, re.M)), "topics.py 의 mqtt_ 함수를 다 읽지 못함"
    return table(["함수", "인자", "토픽 식(코드 원문)"], rows), names


def schema_json():
    d = json.loads((ROOT / "it/neo4j/v2/schema.json").read_text(encoding="utf-8"))
    lay = {l["id"]: l["name"] for l in d["layers"]}
    t0 = table(["층", "이름", "표준"], [[code(l["id"]), esc(l["name"]), esc(l.get("standard", ""))] for l in d["layers"]])
    t1 = table(["클래스", "한글 이름", "층", "속성"], [[code(c["name"]), esc(c.get("label_ko", "")), esc(lay.get(c.get("layer"), c.get("layer"))),
                                               f'<span class="fld">{esc(", ".join(p["name"] for p in c.get("properties", [])))}</span>'] for c in d["classes"]])
    t2 = table(["관계", "출발", "도착", "수", "설명"], [[code(r["type"]), esc(", ".join(r.get("from", []))), esc(", ".join(r.get("to", []))), esc(r.get("cardinality", "")), esc(r.get("description", ""))] for r in d["relationships"]])
    return d["version"], len(d["layers"]), len(d["classes"]), len(d["relationships"]), t0, t1, t2


def mcp_tools():
    rows = []
    for svc, f in (("dmn-mcp", "it/dmn-mcp/dmn_mcp/server.py"), ("enterprise-mcp", "it/enterprise-mcp/enterprise_mcp/server.py")):
        s = (ROOT / f).read_text(encoding="utf-8")
        for m in re.finditer(r"@mcp\.tool[^\n]*\n(?:\s*@[^\n]*\n)*\s*(?:async\s+)?def\s+(\w+)\(", s):
            line = s.count("\n", 0, m.start()) + 1
            rows.append([esc(svc), code(m.group(1)), f'<span class="ref">{esc(f)}:{line}</span>'])
        assert sum(1 for r in rows if r[0] == esc(svc)) == s.count("@mcp.tool"), f"{f} 의 @mcp.tool 을 다 읽지 못함"
    return table(["MCP 서버", "도구", "코드"], rows), len(rows)


def definitions():
    out = []
    for p in sorted((ROOT / "it/process/definitions").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        acts = d.get("activities", [])
        rows = [[code(a.get("id", "")), esc(a.get("name", "")), esc(a.get("type", "")), esc(a.get("role", "")), esc(a.get("tool", "") or a.get("decision", ""))] for a in acts]
        ev = ", ".join(f'{e.get("id")}({e.get("type")})' for e in d.get("events", []))
        gw = ", ".join(f'{g.get("id")}({g.get("type")})' for g in d.get("gateways", []))
        out.append(f'<h4>{code(p.name)} — {esc(d.get("processDefinitionId", ""))} v{esc(d.get("version", ""))} · {esc(d.get("processDefinitionName", ""))}</h4>'
                   f'<p class="meta-note">이벤트: {esc(ev) or "—"} · 게이트웨이: {esc(gw) or "—"} · 흐름 {len(d.get("sequences", []))}개 · 역할 {len(d.get("roles", []))}개 · 데이터 {len(d.get("data", []))}개</p>'
                   + table(["활동", "이름", "종류", "역할", "도구 · 결정"], rows))
    return "".join(out)


def cypher_templates():
    rows = []
    for p in sorted((ROOT / "it/neo4j/templates").glob("*.cypher")):
        first = p.read_text(encoding="utf-8").splitlines()[0] if p.stat().st_size else ""
        rows.append([code(p.name), esc(first.lstrip("/ "))])
    return table(["템플릿", "첫 줄(설명)"], rows)


ROUTE_FILES = [("plant-sim", "ot/plant-sim/plantsim/main.py"), ("connect-ingest", "dmz/connect-ingest/app/main.py"), ("cmd-gateway", "dmz/cmd-gateway/gw/main.py"),
               ("detector", "it/detector/det/main.py"), ("connect-sink", "it/connect-sink/app/main.py"), ("agent", "it/agent/agentsvc/main.py"),
               ("process", "it/process/procsvc/main.py"), ("process", "it/process/procsvc/manual_api.py"), ("process", "it/process/procsvc/instance_mode.py"),
               ("enterprise-sim", "it/enterprise-sim/entsim/main.py"), ("공통(make_app 쓰는 서비스 전부)", "common/hydcommon/service.py")]


def build():
    t_svc, t_vol, t_net, names = I.compose(ROOT / "compose.yaml")
    t_kafka, kafka = kafka_topics()
    t_mqtt, mqtt = mqtt_topics()
    tsdb = I.sql_objects([ROOT / "it/timescaledb/init.sql", ROOT / "it/timescaledb/reader.sql"], ROOT)
    migs = sorted((ROOT / "it/supabase/migrations").glob("*.sql"))
    supa = I.sql_objects(migs, ROOT)
    ver, nl, nc, nr, s0, s1, s2 = schema_json()
    t_mcp, nmcp = mcp_tools()
    rts = I.routes([(a, ROOT / b) for a, b in ROUTE_FILES], ROOT)
    h = (f'<h3 id="ap-svc">compose 서비스 {len(names["services"])}개</h3><p class="meta-note">근거: <code>compose.yaml</code>. 환경변수는 이름만 실었습니다(값 · 키는 싣지 않음).</p>{t_svc}'
         f'<h3 id="ap-vol">볼륨 {len(names["volumes"])}개 · 망 {len(names["networks"])}개</h3>{t_vol}{t_net}'
         f'<h3 id="ap-kafka">Kafka(Redpanda) 토픽 {len(kafka)}개</h3><p class="meta-note">근거: <code>it/redpanda/topics.sh</code> — 모든 토픽 <code>-p 1 -r 1</code>.</p>{t_kafka}'
         f'<h3 id="ap-mqtt">MQTT 토픽 식 {len(mqtt)}개</h3><p class="meta-note">근거: <code>common/hydcommon/topics.py</code>. <code>key</code>는 hyd01 · hyd02 · hyd03.</p>{t_mqtt}'
         f'<h3 id="ap-tsdb">TimescaleDB 객체 {len(tsdb)}개</h3><p class="meta-note">근거: <code>it/timescaledb/init.sql</code> · <code>reader.sql</code>.</p>{I.sql_html(tsdb)}'
         f'<h3 id="ap-supa">Supabase 마이그레이션 {len(migs)}개 · 객체 {len(supa)}개</h3><p class="meta-note">근거: <code>it/supabase/migrations/*.sql</code>(파일 순서 = 적용 순서). 표는 컬럼까지, 함수 · 트리거 · 역할은 이름만.</p>{I.sql_html(supa)}'
         f'<h3 id="ap-onto">Neo4j 온톨로지 스키마 v{esc(ver)} — 층 {nl} · 클래스 {nc} · 관계 {nr}</h3><p class="meta-note">근거: <code>it/neo4j/v2/schema.json</code>.</p>{s0}{s1}{s2}'
         f'<h3 id="ap-cypher">Cypher 템플릿</h3>{cypher_templates()}'
         f'<h3 id="ap-mcp">MCP 도구 {nmcp}개</h3><p class="meta-note">Neo4j MCP(uvx mcp-neo4j-cypher)는 외부 패키지라 이 표에 없습니다.</p>{t_mcp}'
         f'<h3 id="ap-api">HTTP API 경로 {len(rts)}개</h3><p class="meta-note">FastAPI 데코레이터에서 뽑았습니다. 「공통」 두 줄(/healthz · /metrics)은 make_app으로 만든 서비스마다 붙습니다.</p>{I.routes_html(rts)}'
         f'<h3 id="ap-def">프로세스 정의</h3>{definitions()}')
    return h, dict(names, kafka=kafka, mqtt=mqtt)
