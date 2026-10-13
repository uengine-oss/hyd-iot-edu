"""scripts/c3_flows.py 의 A · B · C 흐름을 bpmn.io 가 내보내는 형태(.bpmn + 그림 배치 bpmndi)로 쓴다: draw_flows.py OUT_DIR
요소 id · 이름 · 선은 c3_flows 에서 읽고(손으로 다시 적지 않는다), 자리(좌표)만 여기서 정한다. c3_flows 를 고쳤으면: .venv/bin/python scripts/live/draw_flows.py students/flows (그 뒤 tests/test_student_reference_flows.py)."""
import importlib.util, json, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("c3_flows", ROOT / "scripts" / "c3_flows.py")
c3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c3)
B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"

POOL_X, POOL_Y, LABEL_W = 160, 80, 30
LANES = [("L_person", 140), ("L_agent", 140), ("L_system", 260)]          # 칸 높이
Y_PERSON, Y_AGENT, Y_SYS1, Y_SYS2 = 150, 290, 430, 550                   # 줄 가운데 y
SIZE = {"task": (100, 80), "event": (36, 36), "gateway": (50, 50)}
# 요소 가운데 좌표 (x, y). 승인 단계는 세 흐름이 같은 자리
COMMON = {"Start": (268, Y_AGENT), "T_agent": (380, Y_AGENT), "T_approve": (540, Y_PERSON), "G_approved": (755, Y_PERSON),
          "B_overdue": (560, 190), "T_notice": (560, Y_SYS2), "E_notice": (658, Y_SYS2), "R_rejected": (755, Y_SYS2), "E_rejected": (853, Y_SYS2)}
ROW = lambda ids: {n: (900 + 160 * i, Y_SYS1) for i, n in enumerate(ids)}
CENTER = {"c3_cooling": {**COMMON, "T_cmd": (900, Y_SYS1), "T_reobs": (1060, Y_SYS1), "G_ok": (1200, Y_SYS1), "T_wo": (1340, Y_SYS1),
                         "R_ok": (1500, Y_SYS1), "E_end": (1628, Y_SYS1), "R_fail": (1200, Y_SYS2)},
          "c3_pm": {**COMMON, **ROW(["T_wo", "R_ok"]), "E_end": (1188, Y_SYS1)},
          "c3_spare": {**COMMON, **ROW(["T_po", "T_gr", "R_ok"]), "E_end": (1348, Y_SYS1)}}
# 꺾이는 선의 점(없으면 왼쪽 → 오른쪽 직선). 이름: 출발 변 · 도착 변
BENDS = {"F2": "top-left", "F_approved": "right-top", "F_rejected": "bottom-top", "F_overdue": "bottom-top", "F_no": "bottom-top", "F8": "right-bottom"}
LANE_OF_EXTRA = {"Start": "L_agent", "G_approved": "L_person", "B_overdue": None}   # 이벤트 · 분기가 놓인 칸(경계 이벤트는 칸 목록에 넣지 않는다)


def kind(tag):
    return "task" if tag.endswith("ask") else "gateway" if tag.endswith("Gateway") else "event"


def edge_points(fid, a, b, ka, kb):
    (ax, ay), (bx, by) = a, b
    aw, ah = SIZE[ka]; bw, bh = SIZE[kb]
    side = {"left": lambda x, y, w, h: (x - w // 2, y), "right": lambda x, y, w, h: (x + w // 2, y),
            "top": lambda x, y, w, h: (x, y - h // 2), "bottom": lambda x, y, w, h: (x, y + h // 2)}
    out_side, in_side = BENDS.get(fid, "right-left").split("-")
    p, q = side[out_side](ax, ay, aw, ah), side[in_side](bx, by, bw, bh)
    if p[0] == q[0] or p[1] == q[1]:
        return [p, q]
    corner = (q[0], p[1]) if out_side in ("left", "right") else (p[0], q[1])
    return [p, corner, q]


def draw(did):
    fname, src, mapping = c3.FLOWS[did]
    proc = ET.fromstring(src).find(B + "process")
    pid, pname, pos = proc.get("id"), proc.get("name"), CENTER[did]
    nodes = [(el.tag.replace(B, ""), el) for el in proc if el.tag.replace(B, "") not in ("laneSet", "sequenceFlow")]
    flows = [el for el in proc if el.tag == B + "sequenceFlow"]
    assert {el.get("id") for _, el in nodes} == set(pos), (did, {el.get("id") for _, el in nodes} ^ set(pos))
    kinds = {el.get("id"): kind(tag) for tag, el in nodes}
    lane_nodes = {l.get("id"): [r.text for r in l] for l in proc.find(B + "laneSet")}
    lane_names = {l.get("id"): l.get("name") for l in proc.find(B + "laneSet")}
    y_bands, y = {}, POOL_Y
    for lid, h in LANES:
        y_bands[lid] = (y, y + h); y += h
    for tag, el in nodes:                                       # bpmn.io 는 풀 안의 모든 요소를 칸에 넣는다 — 자리(y)로 칸을 정한다
        nid = el.get("id")
        if tag == "boundaryEvent" or any(nid in v for v in lane_nodes.values()):
            continue
        lid = next(l for l, (y0, y1) in y_bands.items() if y0 <= pos[nid][1] < y1)
        lane_nodes[lid].append(nid)
    for lid, ids in lane_nodes.items():                          # 그린 자리와 칸이 맞는지
        for nid in ids:
            assert y_bands[lid][0] <= pos[nid][1] < y_bands[lid][1], (did, nid, lid)
    right = max(x + SIZE[kinds[n]][0] // 2 for n, (x, _) in pos.items()) + 70
    pool_w, pool_h = right - POOL_X, sum(h for _, h in LANES)
    q = quoteattr
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
         'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
         f'id="Definitions_{did}" targetNamespace="http://bpmn.io/schema/bpmn" exporter="bpmn-js (https://demo.bpmn.io)" exporterVersion="17.11.1">',
         f'  <bpmn:collaboration id="Collaboration_{did}">',
         f'    <bpmn:participant id="Participant_{did}" name={q(pname)} processRef={q(pid)} />',
         '  </bpmn:collaboration>',
         f'  <bpmn:process id={q(pid)} name={q(pname)} isExecutable="false">',
         f'    <bpmn:laneSet id="LaneSet_{did}">']
    for lid, _ in LANES:
        L.append(f'      <bpmn:lane id={q(lid)} name={q(lane_names[lid])}>')
        L += [f'        <bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>' for n in lane_nodes[lid]]
        L.append('      </bpmn:lane>')
    L.append('    </bpmn:laneSet>')
    for tag, el in nodes:
        nid = el.get("id")
        attrs = "".join(f" {k}={q(v)}" for k, v in el.attrib.items())
        L.append(f'    <bpmn:{tag}{attrs}>')
        L += [f'      <bpmn:incoming>{f.get("id")}</bpmn:incoming>' for f in flows if f.get("targetRef") == nid]
        L += [f'      <bpmn:outgoing>{f.get("id")}</bpmn:outgoing>' for f in flows if f.get("sourceRef") == nid]
        L += [f'      <bpmn:{c.tag.replace(B, "")} id={q(c.get("id"))} />' for c in el]
        L.append(f'    </bpmn:{tag}>')
    for f in flows:
        L.append("    <bpmn:sequenceFlow" + "".join(f" {k}={q(v)}" for k, v in f.attrib.items()) + " />")
    L += ['  </bpmn:process>', f'  <bpmndi:BPMNDiagram id="BPMNDiagram_{did}">',
          f'    <bpmndi:BPMNPlane id="BPMNPlane_{did}" bpmnElement="Collaboration_{did}">',
          f'      <bpmndi:BPMNShape id="Participant_{did}_di" bpmnElement="Participant_{did}" isHorizontal="true">',
          f'        <dc:Bounds x="{POOL_X}" y="{POOL_Y}" width="{pool_w}" height="{pool_h}" />', '        <bpmndi:BPMNLabel />', '      </bpmndi:BPMNShape>']
    for lid, h in LANES:
        L += [f'      <bpmndi:BPMNShape id="{lid}_di" bpmnElement="{lid}" isHorizontal="true">',
              f'        <dc:Bounds x="{POOL_X + LABEL_W}" y="{y_bands[lid][0]}" width="{pool_w - LABEL_W}" height="{h}" />', '        <bpmndi:BPMNLabel />',
              '      </bpmndi:BPMNShape>']
    for tag, el in nodes:
        nid, k = el.get("id"), kinds[el.get("id")]
        (x, y), (w, h) = pos[nid], SIZE[k]
        marker = ' isMarkerVisible="true"' if k == "gateway" else ""
        L.append(f'      <bpmndi:BPMNShape id="{nid}_di" bpmnElement="{nid}"{marker}>')
        L.append(f'        <dc:Bounds x="{x - w // 2}" y="{y - h // 2}" width="{w}" height="{h}" />')
        if k != "task" and el.get("name"):
            lw = 14 * len(el.get("name"))
            ly = y - h // 2 - 22 if nid in ("G_approved", "G_ok", "E_end") else y - 2 if nid == "B_overdue" else y + h // 2 + 7
            lx = x + 26 if nid == "B_overdue" else x - lw // 2
            L += ['        <bpmndi:BPMNLabel>', f'          <dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="14" />', '        </bpmndi:BPMNLabel>']
        L.append('      </bpmndi:BPMNShape>')
    for f in flows:
        fid, a, b = f.get("id"), f.get("sourceRef"), f.get("targetRef")
        pts = edge_points(fid, pos[a], pos[b], kinds[a], kinds[b])
        L.append(f'      <bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">')
        L += [f'        <di:waypoint x="{x}" y="{y}" />' for x, y in pts]
        if f.get("name"):
            (x0, y0), (x1, y1) = pts[0], pts[1]
            lx, ly = (x0 + 8, y0 + 12) if x0 == x1 else (x0 + 12, y0 - 18)
            L += ['        <bpmndi:BPMNLabel>', f'          <dc:Bounds x="{lx}" y="{ly}" width="{14 * len(f.get("name"))}" height="14" />', '        </bpmndi:BPMNLabel>']
        L.append('      </bpmndi:BPMNEdge>')
    L += ['    </bpmndi:BPMNPlane>', '  </bpmndi:BPMNDiagram>', '</bpmn:definitions>', '']
    return fname, "\n".join(L), mapping


out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for did in c3.FLOWS:
    fname, text, mapping = draw(did)
    (out / fname).write_text(text, encoding="utf-8")
    (out / fname.replace(".bpmn", ".mapping.json")).write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out / fname)
